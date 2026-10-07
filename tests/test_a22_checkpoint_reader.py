"""Prepared checkpoint fixtures; native APIs are fake, no SSH or physics."""
import ctypes
from ctypes import wintypes
import importlib.util
import json
from pathlib import Path
import pathlib
from types import SimpleNamespace
import unittest
from unittest.mock import patch

path = Path(__file__).resolve().parents[1] / 'tools/a22_remote_jobs.py'
spec = importlib.util.spec_from_file_location('a22_reader_transport_test', path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class FakePath:
    def __init__(self, values):
        self.values = iter(values)

    def __truediv__(self, _):
        return self

    def read_bytes(self):
        value = next(self.values)
        if isinstance(value, BaseException):
            raise value
        return value if isinstance(value, bytes) else json.dumps(value).encode('utf-8')


class FakeFunction:
    def __init__(self, action):
        self.action, self.calls = action, []

    def __call__(self, *args):
        self.calls.append(args)
        return self.action(*args)


def functions(values, *, clock=None, windows=False):
    clock = [10.] if clock is None else clock
    stages = ('screen_health', 'features', 'direction', 'image', 'runtime', 'train', 'exception')
    env = dict(r=FakePath(values), job='a22-reader-test', json=json, ctypes=ctypes,
               pathlib=pathlib, os=SimpleNamespace(name='nt' if windows else 'posix'),
               time=SimpleNamespace(perf_counter=lambda: clock[0]),
               origin=5., main_stage='screen_health', STAGE_GPU_CAPS={stage: 100. for stage in stages},
               prior=dict(a22_gpu=0., stage_gpu_seconds={stage: 0. for stage in stages}),
               config=dict(gpu_wall_cap_seconds=100., stage_gpu_caps_seconds={stage: 100. for stage in stages}))
    exec(compile(module._checkpoint_reader_source(), '<reader fixture>', 'exec'), env)
    env['native_checkpoint_bytes'] = env['checkpoint_bytes']
    env['checkpoint_bytes'] = lambda path: path.read_bytes()
    return env


def snapshot():
    return dict(active_stage='direction', stage_gpu_seconds={'direction': 7., 'screen_health': 3.},
                checkpoint_perf_counter=10., counts={'data_generation_F_calls': 5})


class CheckpointReaderTests(unittest.TestCase):
    def test_transient_permission_retains_ledger_and_elapsed_charge(self):
        error = PermissionError('fixture sharing conflict')
        error.winerror = 5
        saved, clock = snapshot(), [10.]
        env = functions([saved, error], clock=clock)
        self.assertEqual(env['checkpoint'](), saved)
        clock[0] = 11.
        self.assertEqual(env['checkpoint'](), saved)
        self.assertEqual(env['checkpoint_read_conflicts'], 1)
        self.assertEqual(env['live_usage'](clock[0], saved), {'direction': 8., 'screen_health': 3.})
        self.assertEqual(saved['counts']['data_generation_F_calls'], 5)

    def test_windows_errno_13_without_winerror_recovers_and_resets_timeout(self):
        saved, clock = snapshot(), [10.]
        updated = dict(saved, checkpoint_perf_counter=11.9)
        env = functions([saved, PermissionError(13, 'fixture private message'), updated,
                         OSError(13, 'fixture CRT denial')], clock=clock, windows=True)
        env['checkpoint']()
        clock[0] = 10.1
        self.assertEqual(env['checkpoint'](), saved)
        clock[0] = 11.9
        self.assertEqual(env['checkpoint'](), updated)
        self.assertIsNone(env['checkpoint_unreadable_since'])
        clock[0] = 13.
        self.assertEqual(env['checkpoint'](), updated)
        self.assertEqual(env['checkpoint_unreadable_since'], 13.)
        self.assertEqual(env['checkpoint_last_read_failure']['error_errno'], 13)
        self.assertIsNone(env['checkpoint_last_read_failure']['error_winerror'])

    def test_persistent_unreadability_times_out_at_two_seconds_with_safe_origin(self):
        saved, clock = snapshot(), [10.]
        env = functions([saved] + [PermissionError(13, 'fixture sensitive message')] * 3,
                        clock=clock, windows=True)
        env['checkpoint']()
        clock[0] = 11.
        env['checkpoint']()
        clock[0] = 12.99
        self.assertEqual(env['checkpoint'](), saved)
        clock[0] = 13.
        with self.assertRaises(TimeoutError):
            try:
                env['checkpoint']()
            except TimeoutError as error:
                # Capture before unittest clears exception tracebacks.
                safe = env['controller_failure'](error)
                raise
        self.assertEqual(safe['error_function'], 'checkpoint')
        self.assertEqual(safe['error_operation'], 'checkpoint')
        self.assertEqual(safe['error_errno'], 13)
        self.assertNotIn('sensitive', json.dumps(safe))
        self.assertEqual(env['last_checkpoint'], saved)
        self.assertEqual(env['live_usage'](13.), {'direction': 10., 'screen_health': 3.})

    def test_unrelated_posix_permission_and_corrupted_json_are_fatal(self):
        env = functions([PermissionError(13, 'ordinary POSIX permission error')])
        with self.assertRaises(PermissionError):
            env['checkpoint']()
        for corrupt in (b'{"counts":', b'{"checkpoint_perf_counter":NaN}', b'[]'):
            with self.subTest(corrupt=corrupt):
                saved = snapshot()
                env = functions([saved, corrupt])
                env['checkpoint']()
                with self.assertRaises(ValueError) as caught:
                    env['checkpoint']()
                safe = env['controller_failure'](caught.exception)
                self.assertEqual(safe['error_operation'], 'checkpoint_json')
                self.assertEqual(env['last_checkpoint'], saved)
                self.assertEqual(env['checkpoint_read_conflicts'], 0)

    def test_startup_missing_still_bills_elapsed_but_later_missing_is_bounded(self):
        clock = [25.]
        env = functions([FileNotFoundError(), snapshot(), FileNotFoundError(), FileNotFoundError()], clock=clock)
        self.assertIsNone(env['checkpoint']())
        self.assertEqual(env['live_usage'](25.), {'screen_health': 20.})
        env['config']['stage_gpu_caps_seconds']['screen_health'] = 22.
        self.assertTrue(env['watchdog_exceeded'](env['live_usage'](25.), 'screen_health'))
        env['checkpoint']()
        clock[0] = 26.
        env['checkpoint']()
        clock[0] = 28.
        with self.assertRaises(TimeoutError):
            env['checkpoint']()

    def test_stage_and_global_caps_keep_advancing_during_stale_reads(self):
        error, clock = PermissionError(13, 'fixture sharing'), [10.]
        env = functions([snapshot(), error, error], clock=clock, windows=True)
        env['checkpoint']()
        clock[0] = 11.
        env['checkpoint']()
        env['prior']['stage_gpu_seconds']['direction'] = 1.
        env['prior']['a22_gpu'] = 1.
        env['config']['stage_gpu_caps_seconds']['direction'] = 12.
        self.assertFalse(env['watchdog_exceeded'](env['live_usage'](11.), 'direction'))
        clock[0] = 12.
        env['checkpoint']()
        self.assertTrue(env['watchdog_exceeded'](env['live_usage'](12.), 'direction'))
        env['config']['stage_gpu_caps_seconds']['direction'] = 100.
        env['config']['gpu_wall_cap_seconds'] = 15.
        self.assertTrue(env['watchdog_exceeded'](env['live_usage'](12.), 'direction'))

    def test_native_handle_allows_read_write_delete_sharing_and_always_closes(self):
        pieces = iter([b'{"counts":', b'{"F_calls":3}}', b''])

        def read(handle, buffer, size, count, overlapped):
            chunk = next(pieces)
            ctypes.memmove(buffer, chunk, len(chunk))
            ctypes.cast(count, ctypes.POINTER(wintypes.DWORD)).contents.value = len(chunk)
            return 1

        kernel = SimpleNamespace(CreateFileW=FakeFunction(lambda *args: 4242),
                                 ReadFile=FakeFunction(read), CloseHandle=FakeFunction(lambda handle: 1))
        env = functions([], windows=True)
        with patch.object(ctypes, 'WinDLL', create=True, return_value=kernel):
            payload = env['native_checkpoint_bytes'](Path('fixture-checkpoint.json'))
        self.assertEqual(json.loads(payload), {'counts': {'F_calls': 3}})
        self.assertEqual(kernel.CreateFileW.calls[0][2], 1 | 2 | 4)
        self.assertEqual(kernel.CreateFileW.calls[0][4], 3)
        self.assertEqual(kernel.CreateFileW.restype, wintypes.HANDLE)
        self.assertEqual(kernel.CloseHandle.calls, [(4242,)])

    def test_native_read_failure_closes_handle_and_records_api_plus_last_frame(self):
        kernel = SimpleNamespace(CreateFileW=FakeFunction(lambda *args: 4242),
                                 ReadFile=FakeFunction(lambda *args: 0), CloseHandle=FakeFunction(lambda handle: 1))
        failure = PermissionError(13, 'fixture secret path must not be shown')
        failure.winerror = 32
        env = functions([], windows=True)
        with patch.object(ctypes, 'WinDLL', create=True, return_value=kernel), \
                patch.object(ctypes, 'get_last_error', create=True, return_value=32), \
                patch.object(ctypes, 'WinError', create=True, return_value=failure):
            with self.assertRaises(PermissionError):
                try:
                    env['native_checkpoint_bytes'](Path('fixture-checkpoint.json'))
                except PermissionError as error:
                    safe = env['controller_failure'](error)
                    raise
        self.assertEqual(kernel.CloseHandle.calls, [(4242,)])
        self.assertEqual(safe['error_function'], 'checkpoint_bytes')
        self.assertEqual(safe['error_operation'], 'ReadFile')
        self.assertEqual(safe['error_errno'], 13)
        self.assertEqual(safe['error_winerror'], 32)
        self.assertNotIn('secret', json.dumps(safe))


if __name__ == '__main__':
    unittest.main()
