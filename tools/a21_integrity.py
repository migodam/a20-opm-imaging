"""CPU-only synthetic/unit validation, with imports and failed attempts charged."""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time


def _usage():
    try:
        import resource
        value = resource.getrusage(resource.RUSAGE_CHILDREN)
        return value.ru_utime + value.ru_stime
    except ImportError:
        return None


def _windows_handle(pid):
    if sys.platform != 'win32':
        return None
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel.OpenProcess.restype = wintypes.HANDLE
    handle = kernel.OpenProcess(0x1000, False, pid)
    return (kernel, handle) if handle else None


def _windows_cpu(handle):
    if handle is None:
        return None
    import ctypes
    from ctypes import wintypes
    kernel, process = handle
    kernel.GetProcessTimes.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.FILETIME),
                                      ctypes.POINTER(wintypes.FILETIME), ctypes.POINTER(wintypes.FILETIME),
                                      ctypes.POINTER(wintypes.FILETIME))
    kernel.GetProcessTimes.restype = wintypes.BOOL
    creation, exit_time, system, user = [wintypes.FILETIME() for _ in range(4)]
    if not kernel.GetProcessTimes(process, creation, exit_time, system, user):
        return None
    ticks = lambda value: (value.dwHighDateTime << 32) + value.dwLowDateTime
    return (ticks(system) + ticks(user)) / 10000000.0


def _close_windows(handle):
    if handle is not None:
        from ctypes import wintypes
        kernel, process = handle
        kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
        kernel.CloseHandle(process)


def _live_cpu(pid, handle):
    windows = _windows_cpu(handle)
    if windows is not None:
        return windows
    try:
        import psutil
        value = psutil.Process(pid).cpu_times()
        return value.user + value.system
    except (ImportError, ProcessLookupError):
        return 0.0
    except Exception:
        # A process may finish between polling and querying its CPU counter.
        return 0.0


def _run_child(root, command, output, book, deadline):
    from a20.costs import BudgetExceeded
    book.check()
    remaining = min(book.remaining_cpu_seconds(), 120.0)
    if remaining <= 1.0:
        raise BudgetExceeded('A21_INSUFFICIENT_VALIDATION_CPU_RESERVE')
    env = os.environ.copy()
    for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS',
                'NUMEXPR_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS'):
        env[key] = '1'
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['PYTHONPATH'] = str(Path(root) / 'src')
    # Child validation never needs private connection configuration.
    env.pop('A20_SSH_TARGET', None)
    env.pop('A20_SSH_KEY', None)
    env['CUDA_VISIBLE_DEVICES'] = ''
    options = {}
    if os.name == 'posix':
        def limit_cpu():
            import resource
            seconds = max(1, math.floor(remaining))
            resource.setrlimit(resource.RLIMIT_CPU, (seconds, seconds))
        options['preexec_fn'] = limit_cpu
    before = _usage()
    started = time.perf_counter()
    handle = process = None
    timed_out = False
    failure = None
    with output.open('w', encoding='utf-8') as stream:
        try:
            process = subprocess.Popen(command, cwd=root, env=env, stdout=stream,
                                       stderr=subprocess.STDOUT, **options)
            handle = _windows_handle(process.pid)
            while process.poll() is None:
                book.live_child_cpu_seconds = _live_cpu(process.pid, handle)
                book.check()
                if time.perf_counter() >= deadline:
                    timed_out = True
                    raise BudgetExceeded('A21_VALIDATION_WALL_CAP_120_SECONDS')
                time.sleep(0.05)
            process.wait()
        except BaseException as error:
            failure = error
            if process is not None and process.poll() is None:
                process.kill()
                process.wait()
        finally:
            after = _usage()
            windows_cpu = _windows_cpu(handle)
            _close_windows(handle)
            elapsed = time.perf_counter() - started
            if before is not None and after is not None:
                cpu, measurement = max(0.0, after - before), 'terminated child user + system CPU, including imports'
            elif windows_cpu is not None:
                cpu, measurement = windows_cpu, 'GetProcessTimes child user + kernel CPU, including imports'
            else:
                # Single-thread validation: wall is a conservative allowance,
                # explicitly distinguished from a measured CPU counter.
                cpu, measurement = elapsed, 'conservative single-thread child wall allowance; CPU counter unavailable'
            book.add_child_cpu(cpu)
            row = dict(command=command, returncode=process.returncode if process else None,
                       wall_seconds=elapsed, process_cpu_seconds=cpu, measurement=measurement,
                       status='TIMEOUT' if timed_out else 'FAILED' if failure or not process or process.returncode else 'PASS',
                       log=output.relative_to(root).as_posix(), GPU_seconds=0)
            output.with_suffix('.json').write_text(json.dumps(row, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    if failure is not None:
        raise failure
    book.check()
    return row


def run_integrity(root, config, book, job):
    root = Path(root)
    destination = root / 'results/a21/validation' / job
    if destination.exists():
        raise ValueError('VALIDATION_ATTEMPT_ALREADY_EXISTS')
    destination.mkdir(parents=True)
    source = root / 'protocol/a21/validation/validate_two_sided.py'
    copied = destination / 'validate_two_sided.py'
    shutil.copy2(source, copied)
    result = dict(status='FAILED', job=job, real_5184_current_physics=False,
                  online_descent_experiment='NOT_RUN', new_SHA256_checks=0,
                  original_package_validation_evidence_preserved=True,
                  source_protocol_script=source.relative_to(root).as_posix(),
                  copied_synthetic_script=copied.relative_to(root).as_posix(),
                  copied_synthetic_results=(destination / 'results.json').relative_to(root).as_posix(),
                  maximum_controller_plus_child_CPU_seconds=120,
                  maximum_wall_seconds=120, children=[])
    deadline = book.started_wall + 120.0
    pattern = config.get('validation_test_pattern', 'test_*.py')
    complete = pattern == 'test_*.py'
    try:
        with book.span('synthetic_and_unit_validation', validation_attempts=1):
            commands = [
                [sys.executable, '-B', str(copied)],
                [sys.executable, '-B', '-m', 'unittest', 'discover', '-s', 'tests', '-p', pattern, '-v'],
            ]
            for index, command in enumerate(commands, 1):
                row = _run_child(root, command, destination / ('child_' + str(index) + '.log'), book, deadline)
                result['children'].append(row)
                if row['status'] != 'PASS':
                    break
            passed = len(result['children']) == 2 and all(row['status'] == 'PASS' for row in result['children'])
            result.update(status='PASS' if passed else 'FAILED', complete_unittest_discovery=complete,
                          test_pattern=pattern, controller_plus_child_CPU_seconds=book.elapsed_cpu(),
                          copied_synthetic_results=(destination / 'results.json').relative_to(root).as_posix())
    finally:
        # A stopped child may raise after saving its receipt. Include that
        # receipt in the attempt manifest even when the call did not return.
        result['children'] = [json.loads(path.read_text(encoding='utf-8'))
                              for path in sorted(destination.glob('child_*.json'))]
        result['controller_plus_child_CPU_seconds'] = book.elapsed_cpu()
        result['source_commit'] = book.metadata.get('source_commit')
        result['source_freeze'] = config.get('source_freeze')
        (destination / 'attempt.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n', encoding='utf-8')
        # A selected development subset cannot unlock physical execution.
        t0 = dict(result, status='PASS' if result['status'] == 'PASS' and complete else 'INCOMPLETE' if result['status'] == 'PASS' else 'FAILED',
                  attempt=destination.relative_to(root).as_posix())
        (destination / 'T0.json').write_text(json.dumps(t0, indent=2, allow_nan=False) + '\n', encoding='utf-8')
        if complete:
            (root / 'results/a21/validation/T0.json').write_text(json.dumps(t0, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--job', required=True)
    parser.add_argument('--pattern', default='test_*.py')
    args = parser.parse_args()
    sys.path.insert(0, str(args.root.resolve() / 'src'))
    from a21.cli import main as cli_main
    return cli_main(['validate', '--root', str(args.root.resolve()), '--device', 'cpu',
                     '--job', args.job, '--test-pattern', args.pattern])


if __name__ == '__main__':
    raise SystemExit(main())
