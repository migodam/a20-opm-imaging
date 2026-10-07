"""Explicit gated A22 entrypoints and inclusive process accounting."""
from __future__ import annotations

import time
PROCESS_WALL = time.perf_counter()

import argparse
from contextlib import nullcontext
import json
import os
from pathlib import Path
import sys
import unittest

from a20.costs import BudgetExceeded, job_lock, plain, write_json
from .assets import load_config
from .budget import A22Book, history, register_external


def register_source_receipts(root):
    """Unique conservative source-work charges, separate from run costs."""
    root = Path(root)
    sources = list((root/'research/delegated').glob('a22-*/*CPU_RECEIPT*.json'))
    shared = root.parents[3]/'research/delegated' if len(root.parents)>3 else None
    if shared is not None and shared.is_dir():
        sources.extend(shared.glob('a22-*/*CPU_RECEIPT*.json'))
    for source in sources:
        row = json.loads(source.read_text())
        charge = next((row[k] for k in ('process_cpu_seconds', 'charged_conservative_cpu_seconds',
                     'charged_cpu_seconds_conservative', 'charged_cpu_seconds') if k in row), None)
        if charge is None:
            raise ValueError('UNREADABLE_SOURCE_CPU_RECEIPT:'+source.name)
        relative = 'research/delegated/'+source.parent.name+'/'+source.name
        scope = 'source-'+str(row.get('scope', source.parent.name+'-'+source.stem))
        register_external(root, scope, float(charge), gpu_seconds=0,
            receipt=relative, measurement='worker measured CPU plus explicitly conservative allowance',
            status='SOURCE_WORK_CONSERVATIVE')


def units(root, config, book, pattern):
    output = Path(root)/'results/a22/unit_validation/unit_tests'
    output.mkdir(parents=True, exist_ok=True)
    os.environ['A20_TEST_OUTPUT'] = str(output/'old_backend')
    suite = unittest.defaultTestLoader.discover(str(Path(root)/'tests'), pattern=pattern)
    with (output/(book.job_id+'.log')).open('w', encoding='utf-8') as stream:
        with book.span('a22_unit_test_suite', unit_test_suites=1):
            result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    summary = dict(status='PASS' if result.wasSuccessful() else 'FAIL', tests_run=result.testsRun,
        failures=len(result.failures), errors=len(result.errors), skipped=len(result.skipped),
        pattern=pattern, log=str((output/(book.job_id+'.log')).relative_to(root)),
        scope='unit and tiny identity fixtures; not Maxwell campaign acceptance')
    write_json(output/(book.job_id+'.json'), summary)
    if not result.wasSuccessful():
        error = AssertionError('A22_UNIT_TESTS_FAILED')
        error.summary = summary
        raise error
    return summary


def portable_config(root, config):
    path = Path(root)/'configs/a22_portable.json'
    if path.exists():
        result = load_config(path)
        result['paths']['asset_root'] = str(Path(root)/'data/a22/online')
        return result
    return config


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=['preflight','prepare','prepare-evaluation','unit','validate','descriptor-validate','screen','pilot',
                                        'one-shot','train','report'])
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--device', choices=['cpu','cuda'], default='cpu')
    parser.add_argument('--job', default=None)
    parser.add_argument('--lock-root', type=Path, default=None)
    parser.add_argument('--pattern', default='test_a22_*.py')
    args = parser.parse_args(argv)
    root = args.root.resolve()
    config = load_config(root/'configs/a22.json')
    stage_map = dict(preflight='screen_health', prepare='screen_health', unit='screen_health',
                     validate='screen_health', screen='screen_health', pilot='features',
                     **{'one-shot':'image'}, train='train', report='exception')
    stage_map.update({'prepare-evaluation':'screen_health','descriptor-validate':'screen_health'})
    stage = os.environ.get('A22_BUDGET_STAGE', stage_map[args.stage])
    started = float(os.environ.get('A22_JOB_WALL_ORIGIN', PROCESS_WALL))
    book = A22Book(root, config, stage=stage, job_id=args.job, device=args.device,
                   started_wall=started, started_cpu=0.)
    status, detail, error = 'FAILED', {}, None
    try:
        register_source_receipts(root)
        with (job_lock(args.lock_root or root) if args.device=='cuda' else nullcontext()):
            write_json(root/'results/jobs'/book.job_id/'environment.json', dict(
                python=sys.version, executable=sys.executable, platform=sys.platform,
                fixed_source=config['source_freeze'], source_identity='frozen Git base plus saved A22 source',
                new_SHA256_checks=0,
                thread_settings={k:os.environ.get(k) for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS',
                     'MKL_NUM_THREADS','VECLIB_MAXIMUM_THREADS')}))
            if args.stage=='preflight':
                detail = dict(status='READY', config=config, accounting=history(root, config),
                              data_members_present=len(list((root/'data/a22/online').glob('*.npz'))))
            elif args.stage=='prepare':
                from .prepare import prepare_screening
                detail = prepare_screening(root, config, book)
            elif args.stage=='prepare-evaluation':
                from .offline_assets import prepare_offline_screening
                detail = prepare_offline_screening(root, config, book)
            elif args.stage=='unit':
                detail = units(root, config, book, args.pattern)
            elif args.stage=='validate':
                from .validation import run_validation
                detail = run_validation(root, config, book, device=args.device)
                from .descriptor_health import run_descriptor_health
                detail['descriptor_health'] = run_descriptor_health(root,config,book,device=args.device)
            elif args.stage=='descriptor-validate':
                from .descriptor_health import run_descriptor_health
                detail = run_descriptor_health(root,config,book,device=args.device)
            elif args.stage in ('screen','pilot'):
                from .evaluate import run_stage_a
                if args.stage=='pilot':
                    decision = json.loads((root/'results/a22/SCREENING_DECISION.json').read_text())
                    if decision.get('screening_signal_positive') is not True:
                        raise BudgetExceeded('A22_EXPANSION_REQUIRES_POSITIVE_SCREENING_DECISION')
                detail = run_stage_a(root, portable_config(root, config), book, device=args.device,
                                     screening=args.stage=='screen')
            elif args.stage in ('one-shot','train'):
                decision = json.loads((root/'results/a22/GATE_DECISION.json').read_text())
                gates = decision.get('gates', {})
                required = ('A',) if args.stage=='one-shot' else ('A','B','C')
                if any(gates.get(k,{}).get('status')!='PASS' for k in required):
                    raise BudgetExceeded('A22_CONDITIONAL_STAGE_REQUIRES_FROZEN_PASS:'+','.join(required))
                raise RuntimeError('CONDITIONAL_IMPLEMENTATION_NOT_FROZEN_YET')
            else:
                from .reporting import generate_reports
                detail = generate_reports(root)
        status = 'COMPLETE'
    except BudgetExceeded as exc:
        status, error = 'BUDGET_REFUSED', exc
        detail = dict(error_type=type(exc).__name__, error=str(exc))
    except BaseException as exc:
        status, error = 'FAILED', exc
        import traceback
        detail = dict(error_type=type(exc).__name__, error=str(exc), traceback=traceback.format_exc(),
                      test_summary=getattr(exc,'summary',None))
    finally:
        write_json(root/'results/jobs'/book.job_id/'outcome.json', {**detail, 'status':status, 'stage':args.stage})
        receipt = book.finish(status, outcome=dict(stage=args.stage, **detail))
    print(json.dumps(plain(dict(status=status, stage=args.stage, job_id=book.job_id,
                               CPU_seconds=receipt['process_cpu_seconds'],
                               GPU_seconds=receipt['gpu_occupation_seconds'],
                               result_status=detail.get('status'), scene_count=detail.get('scene_count'),
                               error=detail.get('error'),
                               outcome_file=str(Path('results/jobs')/book.job_id/'outcome.json'))), allow_nan=False))
    return 0 if error is None else 1


if __name__=='__main__':
    sys.exit(main())
