"""Bounded A21 entrypoint. Preflight reads headers, never assembles Maxwell."""
from __future__ import annotations

import time
STARTED_WALL = time.perf_counter()

import argparse
import ast
import importlib.util
import json
import math
import os
from pathlib import Path, PureWindowsPath
import re
import struct
import sys
import traceback
import zipfile

from a20.costs import BudgetExceeded, job_lock, plain, write_json
from .budget import A21Book, history, load_config

PARENTS = [2001, 2005, 2003, 2007, 2013]
ARMS_G = ['BASE_G', 'PRIMAL_G', 'DUAL_G', 'BOTH_G', 'RANDOM_G']
ARMS_PG = ['BOTH_PG', 'RANDOM_PG']
RUNTIME_KEYS = {'parent_id', 'points', 'volume', 'data0', 'scale', 'init', 'Q', 'kind',
                'dirs', 'pols', 'receivers', 'obs_basis', 'k', 'historical_exposed'}
STATE_KEYS = {'chi', 'lambda_total', 'ell', 'iteration'}


def safe_environment():
    keys = ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS',
            'NUMEXPR_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS', 'PYTHONDONTWRITEBYTECODE',
            'PYTHONHASHSEED', 'PYTHONPATH')
    result = {key: os.environ.get(key) for key in keys}
    result.update(python=sys.version.split()[0], executable=sys.executable, platform=sys.platform)
    for name in ('numpy', 'scipy', 'torch'):
        module = sys.modules.get(name)
        if module is not None:
            result[name] = getattr(module, '__version__', 'unavailable')
    return result


def source_identity(root, config, *, required=False):
    path = Path(root) / 'configs/A21_SOURCE_COMMIT.txt'
    stamp = path.read_text(encoding='utf-8').strip() if path.exists() else None
    if stamp is not None and not re.fullmatch(r'[0-9a-f]{40,64}', stamp):
        raise ValueError('INVALID_A21_SOURCE_COMMIT_STAMP')
    if required and stamp is None:
        raise ValueError('A21_SOURCE_COMMIT_STAMP_REQUIRED_BEFORE_PHYSICS')
    old_path = Path(root) / 'configs/a20_r1.json'
    original = json.loads(old_path.read_text(encoding='utf-8')).get('source_freeze') if old_path.exists() else None
    return dict(source_commit=stamp, run_commit=stamp,
                source_freeze=config['source_freeze'], original_A20_R1_source_freeze=original,
                source_identity_source='ignored A21_SOURCE_COMMIT.txt' if stamp else 'NO_RUN_COMMIT_STAMP',
                new_SHA256_checks=0)


def npz_headers(path, *, allowed=None):
    """Read only NPY headers from a runtime NPZ, without NumPy or model setup."""
    headers = {}
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            if not info.filename.endswith('.npy') or '/' in info.filename or '\\' in info.filename:
                raise ValueError('NONCANONICAL_NPZ_MEMBER')
            key = info.filename[:-4]
            if key in headers or (allowed is not None and key not in allowed):
                raise ValueError('OFFLINE_UNREGISTERED_OR_DUPLICATE_RUNTIME_KEY')
            with archive.open(info) as stream:
                if stream.read(6) != b'\x93NUMPY':
                    raise ValueError('INVALID_NPY_HEADER_MAGIC')
                version = stream.read(2)
                if version not in (b'\x01\x00', b'\x02\x00', b'\x03\x00'):
                    raise ValueError('UNSUPPORTED_NPY_HEADER_VERSION')
                width = 2 if version[0] == 1 else 4
                size = struct.unpack('<H' if width == 2 else '<I', stream.read(width))[0]
                if size > 16384:
                    raise ValueError('NPY_HEADER_TOO_LARGE')
                header = ast.literal_eval(stream.read(size).decode('utf-8' if version[0] == 3 else 'latin1'))
            dtype, shape = header.get('descr'), header.get('shape')
            if not isinstance(dtype, str) or dtype.lstrip('<>=|').startswith('O'):
                raise ValueError('OBJECT_OR_STRUCTURED_RUNTIME_DTYPE_FORBIDDEN')
            if not isinstance(shape, tuple) or any(not isinstance(x, int) or x < 0 for x in shape):
                raise ValueError('INVALID_RUNTIME_HEADER_SHAPE')
            headers[key] = dict(dtype=dtype, shape=list(shape), fortran_order=bool(header['fortran_order']))
    if allowed is not None and set(headers) != set(allowed):
        raise ValueError('MISSING_RUNTIME_KEYS')
    return headers


def _scalar(path, key):
    with zipfile.ZipFile(path) as archive, archive.open(key + '.npy') as stream:
        if stream.read(6) != b'\x93NUMPY':
            raise ValueError('INVALID_SCALAR_NPY')
        version = stream.read(2)
        width = 2 if version[0] == 1 else 4
        size = struct.unpack('<H' if width == 2 else '<I', stream.read(width))[0]
        if size > 16384:
            raise ValueError('SCALAR_HEADER_TOO_LARGE')
        header = ast.literal_eval(stream.read(size).decode('latin1'))
        if header['shape'] != ():
            raise ValueError('EXPECTED_SCALAR_RUNTIME_FIELD')
        dtype = header['descr']
        if dtype in ('<i8', '<f8'):
            return struct.unpack('<q' if dtype == '<i8' else '<d', stream.read(8))[0]
        if dtype.startswith('<U') and int(dtype[2:]) <= 64:
            return stream.read(4 * int(dtype[2:])).decode('utf-32le').rstrip('\x00')
        if dtype == '|b1':
            return bool(struct.unpack('?', stream.read(1))[0])
        raise ValueError('UNREGISTERED_SCALAR_RUNTIME_DTYPE')


def _inside(root, relative):
    path = (Path(root) / relative).resolve()
    if not path.is_relative_to(Path(root).resolve()):
        raise ValueError('INPUT_PATH_OUTSIDE_A21_ROOT')
    return path


def canonical_inputs(root, config):
    """Return exactly one existing reference and mixed/degree3 baseline per late state."""
    root = Path(root)
    canonical = root / 'results/replay/replay.jsonl'
    indexed = {}
    with canonical.open(encoding='utf-8') as handle:
        for number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            parent, iteration = row.get('parent_object_id'), row.get('iteration')
            if parent not in config['parents'] or iteration != 17:
                continue
            kind = None
            if row.get('record_kind') == 'shared_reference' and row.get('method') == 'full_GN_reference':
                kind = 'reference'
            elif row.get('record_kind') == 'method' and row.get('method') == 'mixed' and row.get('degree') == 3:
                kind = 'baseline'
            if kind:
                indexed.setdefault((parent, kind), []).append((number, row))
    result = []
    for parent in config['parents']:
        for kind in ('reference', 'baseline'):
            matches = indexed.get((parent, kind), [])
            if len(matches) != 1:
                raise ValueError('MISSING_OR_DUPLICATE_CANONICAL_' + kind.upper() + ':' + str(parent))
            number, row = matches[0]
            field = 'reference_step_path' if kind == 'reference' else 'step_path'
            recorded = row.get(field)
            if not isinstance(recorded, str) or not recorded:
                raise ValueError('CANONICAL_STEP_PATH_MISSING')
            name = PureWindowsPath(recorded).name if '\\' in recorded else Path(recorded).name
            candidates = [p for directory in ('steps', 'failed_steps')
                          for p in (root / 'results/replay' / directory).glob(name)]
            if len(candidates) != 1:
                raise ValueError('MISSING_OR_AMBIGUOUS_CANONICAL_STEP_BASENAME')
            path = candidates[0].resolve()
            if not path.is_relative_to(root.resolve()):
                raise ValueError('CANONICAL_STEP_OUTSIDE_ROOT')
            result.append(dict(parent_id=parent, kind=kind, canonical_line=number,
                               row=row, step_path=path.relative_to(root.resolve()).as_posix()))
    return result


def preflight(root, config, book=None):
    root = Path(root).resolve()
    required = dict(parents=PARENTS, iterations=[17], retained_rank=8, current_rank=56,
                    degree=3, arms_G=ARMS_G, arms_PG=ARMS_PG, maximum_reduced_qps=35,
                    precision='complex128/float64', new_sha256_checks=False,
                    allow_petrov_fallback=False, allow_full_fallback=False, offline_oracle_only=True,
                    anatomy_CPU_seconds=1200, anatomy_GPU_seconds=1200,
                    budget_cpu_seconds=7200, budget_gpu_wall_seconds=43200,
                    qp_kkt_rtol=1e-8, scientific_H_error_target=0.05)
    if any(config.get(key) != value for key, value in required.items()):
        raise ValueError('A21_FROZEN_CONSTANT_CONFLICT')
    if config.get('validation_parents') != [PARENTS[0], PARENTS[len(PARENTS)//2], PARENTS[-1]]:
        raise ValueError('A21_VALIDATION_STATE_ORDER_CONFLICT')
    parents = json.loads((root / 'configs/parents.json').read_text(encoding='utf-8'))['parents']
    metadata = {}
    for row in parents:
        parent = row['parent_id']
        if parent in metadata:
            raise ValueError('DUPLICATE_PARENT_MANIFEST_ENTRY')
        metadata[parent] = row
    selected = canonical_inputs(root, config)
    states = []
    for parent in config['parents']:
        if book is not None:
            book.check()
        row = metadata[parent]
        if (row['parameterization'] != 'gaussian' or row['n_current'] != 5184
                or row['p_material'] != 54 or row['sources'] != 6
                or row['receivers'] != 64 or row['frequencies'] != [2.0]):
            raise ValueError('FROZEN_PARENT_METADATA_CONFLICT:' + str(parent))
        runtime = _inside(root, row['runtime_problem'])
        state_rows = [s for s in row['states'] if s['iteration'] == 17]
        if len(state_rows) != 1:
            raise ValueError('MISSING_OR_DUPLICATE_LATE_STATE')
        state = _inside(root, state_rows[0]['runtime_path'])
        ph = npz_headers(runtime, allowed=RUNTIME_KEYS)
        sh = npz_headers(state, allowed=STATE_KEYS)
        shapes = dict(points=[1728, 3], data0=[6, 128], init=[1728], Q=[1728, 27],
                      dirs=[6, 3], pols=[6, 3], receivers=[64, 3], obs_basis=[64, 2, 3])
        if any(ph[key]['shape'] != shape for key, shape in shapes.items()):
            raise ValueError('FROZEN_RUNTIME_SHAPE_CONFLICT:' + str(parent))
        if (sh['chi']['shape'] != [1728] or sh['ell']['shape'] != [54]
                or sh['chi']['dtype'] != '<c16' or sh['ell']['dtype'] != '<f8'):
            raise ValueError('FROZEN_STATE_SHAPE_OR_PRECISION_CONFLICT')
        if (_scalar(runtime, 'parent_id') != parent or _scalar(runtime, 'kind') != 'gaussian'
                or _scalar(runtime, 'k') != 2.0 or _scalar(state, 'iteration') != 17):
            raise ValueError('FROZEN_RUNTIME_SCALAR_CONFLICT')
        damping = _scalar(state, 'lambda_total')
        if not math.isfinite(damping) or damping <= 0:
            raise ValueError('INVALID_FROZEN_REGULARIZER')
        evidence = []
        for item in [x for x in selected if x['parent_id'] == parent]:
            record = item['row']
            expectations = dict(parent_object_id=parent, iteration=17, parameterization='gaussian',
                                n_current=5184, p_material=54, n_source=6, n_receiver=64,
                                frequencies=[2.0], precision='complex128/float64', status='OK')
            if any(record.get(key) != value for key, value in expectations.items()):
                raise ValueError('CANONICAL_ROW_PROVENANCE_CONFLICT')
            if not record.get('backend_commit') or not record.get('run_id'):
                raise ValueError('CANONICAL_CODE_IDENTITY_MISSING')
            if item['kind'] == 'reference':
                if not str(record.get('reference_status', '')).startswith('VERIFIED_'):
                    raise ValueError('UNVERIFIED_EXISTING_REFERENCE')
            elif record.get('rank') != 56 or record.get('seed_budgets') != {'O': 4, 'P': 4, 'M': 4}:
                raise ValueError('CANONICAL_BASELINE_RANK_OR_SEED_CONFLICT')
            headers = npz_headers(root / item['step_path'], allowed={'step'})
            if headers['step']['shape'] != [54] or headers['step']['dtype'] != '<f8':
                raise ValueError('CANONICAL_STEP_SHAPE_OR_PRECISION_CONFLICT')
            evidence.append({k: item[k] for k in ('kind', 'canonical_line', 'step_path')})
        states.append(dict(parent_id=parent, iteration=17,
                           runtime_problem=runtime.relative_to(root).as_posix(),
                           runtime_state=state.relative_to(root).as_posix(),
                           problem_headers=ph, state_headers=sh, canonical_inputs=evidence))
    return dict(status='PASS', scope='runtime headers, small scalars, immutable IDs and unique canonical rows only',
                real_5184_current_physics=False, full_KKT_revalidation='NOT_RUN',
                states=states, **source_identity(root, config), new_physics=False,
                dataset_exposure=config['dataset_exposure'])


def _load_integrity(root):
    spec = importlib.util.spec_from_file_location('a21_integrity_driver', Path(root) / 'tools/a21_integrity.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _safe_failure(error, root):
    stack = []
    for frame in traceback.extract_tb(error.__traceback__):
        path = Path(frame.filename)
        label = path.relative_to(root).as_posix() if path.is_relative_to(root) else path.name
        stack.append(dict(file=label, line=frame.lineno, function=frame.name))
    # Never serialize process arguments or unknown exception objects.
    message = str(error) if isinstance(error, (BudgetExceeded, ValueError, RuntimeError)) else 'See preserved stack locations'
    if any(word in message.lower() for word in ('ssh', 'private/', 'private\\', 'credential', 'password')):
        message = 'Private transport details suppressed'
    return dict(error_type=type(error).__name__, reason=message[:2000], stack=stack)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['preflight', 'validate', 'anatomy', 'report'])
    parser.add_argument('--root', type=Path, default=Path.cwd())
    parser.add_argument('--device', choices=['cpu', 'cuda'], default='cpu')
    parser.add_argument('--job', required=True)
    parser.add_argument('--lock-root', type=Path)
    parser.add_argument('--phase', choices=['all', 'galerkin', 'petrov'], default='all')
    parser.add_argument('--test-pattern', default='test_*.py')
    args = parser.parse_args(argv)
    if not re.fullmatch(r'a21-[A-Za-z0-9_-]{1,100}', args.job):
        raise SystemExit('A21 job IDs must start a21- and use safe characters')
    if args.stage in ('preflight', 'validate', 'report') and args.device != 'cpu':
        raise SystemExit('Header preflight, standalone validation and report use CPU')
    root = args.root.resolve()
    config = load_config(root)
    config['stage'] = args.phase  # Runtime phase, never rewrite the frozen config.
    if '/' in args.test_pattern or '\\' in args.test_pattern or not args.test_pattern.endswith('.py'):
        raise SystemExit('Test patterns are restricted to files under tests')
    config['validation_test_pattern'] = args.test_pattern
    directory = root / 'results/jobs' / args.job
    if directory.exists():
        raise SystemExit('Existing job ID: no replacement or uncharged retry')
    directory.mkdir(parents=True)
    book = A21Book(root, config, directory / 'cost.jsonl', device=args.device,
                   epilogue=args.stage == 'report', job_cpu_limit=120 if args.stage == 'validate' else None)
    book.started_wall = STARTED_WALL
    identity = source_identity(root, config)
    book.metadata = dict(job=args.job, experiment_id=args.job, **identity)
    command = list(sys.orig_argv) if argv is None and hasattr(sys, 'orig_argv') else [sys.executable, '-B', '-m', 'a21.cli', *(argv or [])]
    result, status = dict(status='NOT_RUN'), 'FAILED'
    try:
        with job_lock(args.lock_root or root):
            book.check()
            write_json(directory / 'manifest.json', dict(**book.metadata, stage=args.stage,
                       runtime_phase=args.phase, device=args.device, config=config,
                       budget_prior=book.prior, command=command, environment=safe_environment()))
            if args.stage == 'preflight':
                result = preflight(root, config, book)
                write_json(root / 'results/a21/PREFLIGHT.json', result)
            elif args.stage == 'validate':
                result = _load_integrity(root).run_integrity(root, config, book, args.job)
            elif args.stage == 'anatomy':
                source_identity(root, config, required=True)
                preflight(root, config, book)
                path = root / 'results/a21/validation/T0.json'
                if not path.exists() or json.loads(path.read_text(encoding='utf-8')).get('status') != 'PASS':
                    raise ValueError('A21_SYNTHETIC_T0_REQUIRED_BEFORE_PHYSICS')
                from .anatomy import run_anatomy
                result = run_anatomy(root, config, book, args.job)
            else:
                from .report import run_report
                result = run_report(root, config, book, args.job)
            status = 'COMPLETE'
            if result.get('status') in ('FAILED', 'FAIL', 'T0_FAILED', 'INVALID_INPUT', 'NOT_RUN_INPUT_CONFLICT'):
                status = 'FAILED'
            elif result.get('status') in ('PARTIAL', 'HOLD', 'STOPPED', 'STOPPED_PARTIAL', 'BUDGET_STOP'):
                status = 'PARTIAL'
            book.check()
    except BudgetExceeded as error:
        result = dict(status='BUDGET_STOP', partial_rows_preserved=True, **_safe_failure(error, root))
        status = 'BUDGET_STOP'
    except BaseException as error:
        result = dict(status='FAILED', **_safe_failure(error, root))
        status = 'FAILED'
    finally:
        write_json(directory / 'result.json', result)
        receipt = book.receipt() | dict(job=args.job, stage=args.stage, runtime_phase=args.phase,
                   status=status, command=command, environment=safe_environment(), **identity)
        write_json(directory / 'job_receipt.json', receipt)
        destination = root / 'results/a21'
        destination.mkdir(parents=True, exist_ok=True)
        with (destination / 'JOB_LEDGER.jsonl').open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(plain(receipt | {'stage_result_status': result.get('status')}), allow_nan=False) + '\n')
        if status != 'COMPLETE':
            with (destination / 'FAILURE_LEDGER.jsonl').open('a', encoding='utf-8') as handle:
                handle.write(json.dumps(plain(dict(failure_kind='stage', job=args.job, status=status, result=result)), allow_nan=False) + '\n')
        write_json(destination / 'BUDGET_CURRENT.json', history(root, config))
        print(json.dumps(dict(job=args.job, status=status, stage_status=result.get('status'),
                              CPU=receipt['process_cpu_seconds'], GPU=receipt['gpu_occupation_seconds'])), flush=True)
    return 0 if status == 'COMPLETE' else 2


if __name__ == '__main__':
    raise SystemExit(main())
