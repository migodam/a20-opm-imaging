"""Explicit, bounded cached R1 experiment. No automatic expansion or NN."""
import time
PROCESS_WALL = time.perf_counter()

import argparse
from contextlib import nullcontext
import json
from pathlib import Path
import sys
import traceback
import unittest

from a20.costs import BudgetExceeded, job_lock, plain, write_json
from .accounting import R1Book


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('stage', choices=('freeze', 'replay', 'replay-cached', 'unit', 'report'))
    p.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    p.add_argument('--job', required=True)
    p.add_argument('--device', choices=('cpu', 'cuda'), default='cpu')
    p.add_argument('--lock-root', type=Path)
    p.add_argument('--pattern', default='test_a22_r1*.py')
    args = p.parse_args(argv)
    root = args.root.resolve()
    config = json.loads((root/'configs/a22_r1.json').read_text())
    book = R1Book(root, config, args.job, device=args.device, started_wall=PROCESS_WALL)
    status, detail = 'FAILED', {}
    try:
        if args.stage != 'freeze' and args.device != 'cpu':
            raise ValueError('ONLY_MISSING_ANCHOR_AND_DESCRIPTOR_REBUILD_MAY_USE_CUDA')
        with (job_lock(args.lock_root or root) if args.device == 'cuda' else nullcontext()):
            write_json(book.directory/'environment.json', {'python': sys.version, 'platform': sys.platform,
                       'device': args.device, 'source_commit': config['source_commit'], 'new_SHA256_checks': 0})
            if args.stage == 'freeze':
                from .freeze import freeze_scene
                original = json.loads((root/'configs/a22_portable.json').read_text())
                original['paths']['asset_root'] = str(root/'data/a22/online')
                detail['scenes'] = []
                for sid in config['scenes']:
                    detail['scenes'].append(freeze_scene(root, sid, original, book, device=args.device))
            elif args.stage in ('replay','replay-cached'):
                from .replay import run_replay
                source=None
                if args.stage=='replay-cached':
                    source=json.loads((root/'configs/a22_r1_cached_qp_addendum.json').read_text())['common_cases']
                detail = run_replay(root, config, book, cached_common=source)
            elif args.stage == 'unit':
                suite = unittest.defaultTestLoader.discover(str(root/'tests'), pattern=args.pattern)
                with (book.directory/'tests.log').open('w') as stream, book.span('r1_unit_tests', unit_suites=1):
                    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
                detail = dict(tests=result.testsRun, failures=len(result.failures), errors=len(result.errors), skipped=len(result.skipped))
                if not result.wasSuccessful():
                    raise AssertionError('R1_UNIT_TESTS_FAILED')
            else:
                from .report import generate_report
                with book.span('r1_report_and_plots', report_generations=1):
                    detail = generate_report(root, config)
        status = 'COMPLETE'
    except BaseException as error:
        status = 'BUDGET_REFUSED' if isinstance(error, BudgetExceeded) else 'FAILED'
        detail.update(error_type=type(error).__name__, error=str(error), traceback=traceback.format_exc())
    finally:
        write_json(book.directory/'outcome.json', dict(status=status, detail=detail))
        receipt = book.finish(status, detail)
        if args.stage == 'report' and status == 'COMPLETE':
            from .report import cost_summary
            cost_summary(root,config)
    print(json.dumps(plain({'status': status, 'job': args.job, 'CPU_seconds': receipt['process_cpu_seconds'],
                          'GPU_seconds': receipt['gpu_occupation_seconds'], 'detail': detail}), allow_nan=False))
    return 0 if status == 'COMPLETE' else 1


if __name__ == '__main__':
    sys.exit(main())
