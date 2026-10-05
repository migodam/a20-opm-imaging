#!/usr/bin/env python3
"""Bounded G0 runner: per-case receipts plus inclusive attempt CPU accounting."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time
import traceback
import unittest

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'results/tests'
TOTAL_CPU_LIMIT = 120.


def dump(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, allow_nan=False)+'\n')


class Receipts(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.rows = []
        self.current = None

    def startTest(self, test):
        super().startTest(test)
        self.current = dict(test=test.id(), status='PASS')
        self.cpu = time.process_time()
        self.wall = time.perf_counter()

    def addError(self, test, error):
        super().addError(test, error)
        self.current.update(status='ERROR', traceback=''.join(traceback.format_exception(*error)))

    def addFailure(self, test, error):
        super().addFailure(test, error)
        self.current.update(status='FAIL', traceback=''.join(traceback.format_exception(*error)))

    def addSubTest(self, test, subtest, error):
        super().addSubTest(test, subtest, error)
        if error:
            self.current.update(status='FAIL')
            self.current.setdefault('subtest_failures', []).append(dict(
                subtest=str(subtest), traceback=''.join(traceback.format_exception(*error))))

    def stopTest(self, test):
        self.current.update(process_cpu_seconds=time.process_time()-self.cpu,
                            wall_seconds=time.perf_counter()-self.wall,
                            metrics=getattr(test, 'metrics', {}))
        if hasattr(test, 'book'):
            self.current['cost_receipt'] = test.book.receipt()
        self.rows.append(self.current)
        with (Path(os.environ['A20_TEST_OUTPUT'])/'cases.jsonl').open('a') as handle:
            handle.write(json.dumps(self.current, allow_nan=False)+'\n')
        super().stopTest(test)


def worker(cpu_cap, pattern):
    cap = max(1, int(cpu_cap))
    resource.setrlimit(resource.RLIMIT_CPU, (cap, cap))
    suite = unittest.defaultTestLoader.discover(str(ROOT/'tests'), pattern=pattern)
    runner = unittest.TextTestRunner(resultclass=Receipts, verbosity=1)
    result = runner.run(suite)
    dest = Path(os.environ['A20_TEST_OUTPUT'])
    dump(dest/'suite.json', dict(tests=result.testsRun,
         passed=sum(row['status']=='PASS' for row in result.rows),
         failures=len(result.failures), errors=len(result.errors),
         status='PASS' if result.wasSuccessful() else 'FAIL', cases=result.rows))
    return 0 if result.wasSuccessful() else 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--worker', action='store_true')
    parser.add_argument('--cpu-cap', type=float, default=30.)
    parser.add_argument('--pattern', default='test_*.py')
    args = parser.parse_args()
    if args.worker:
        return worker(args.cpu_cap, args.pattern)
    OUT.mkdir(parents=True, exist_ok=True)
    prior = [json.loads(path.read_text()) for path in sorted(OUT.glob('attempt_*/receipt.json'))]
    used = sum(row['inclusive_process_cpu_seconds'] for row in prior)
    remaining = TOTAL_CPU_LIMIT-used
    if remaining < 2.:
        print('TEST_CPU_BUDGET_REFUSED')
        return 2
    attempt = OUT/f'attempt_{len(prior)+1:03d}'
    attempt.mkdir()
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', OPENBLAS_NUM_THREADS='1',
               OMP_NUM_THREADS='1', PYTHONPATH='src', A20_TEST_OUTPUT=str(attempt))
    cap = min(args.cpu_cap, remaining-1.)
    start_wall = time.perf_counter()
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    command = [sys.executable, str(Path(__file__).resolve()), '--worker',
               '--cpu-cap', str(cap), '--pattern', args.pattern]
    timed_out = False
    with (attempt/'stdout_stderr.log').open('w') as log:
        try:
            run = subprocess.run(command, cwd=ROOT, env=env, stdout=log,
                                 stderr=subprocess.STDOUT, timeout=55.)
            code = run.returncode
        except subprocess.TimeoutExpired:
            code, timed_out = 124, True
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    child_cpu = after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime
    inclusive_cpu = time.process_time()+child_cpu
    receipt = dict(attempt=attempt.name, command=command, environment={key:env[key]
                   for key in ('PYTHONDONTWRITEBYTECODE', 'OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'PYTHONPATH')},
                   returncode=code, timeout=timed_out, wall_seconds=time.perf_counter()-start_wall,
                   child_cpu_seconds=child_cpu, runner_cpu_seconds=time.process_time(),
                   inclusive_process_cpu_seconds=inclusive_cpu,
                   previous_cpu_seconds=used, cumulative_cpu_seconds=used+inclusive_cpu,
                   cpu_limit_seconds=TOTAL_CPU_LIMIT, worker_hard_cpu_cap_seconds=int(cap),
                   peak_child_rss=after.ru_maxrss,
                   scope='tiny 2^3 3-D DenseDDA G0 only; no six-object experiment, no hash')
    dump(attempt/'receipt.json', receipt)
    summary = json.loads((attempt/'suite.json').read_text()) if (attempt/'suite.json').exists() else {}
    dump(OUT/'LATEST.json', dict(receipt=receipt, summary=summary))
    print(f"{summary.get('status', 'INCOMPLETE')}: {summary.get('passed', 0)}/{summary.get('tests', 0)} tests; "
          f"attempt CPU {inclusive_cpu:.3f}s; cumulative CPU {used+inclusive_cpu:.3f}/120s; {attempt}")
    return code


if __name__ == '__main__':
    sys.exit(main())
