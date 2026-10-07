"""A controlled stop cannot target a different job, module or root."""
import importlib.util
from pathlib import Path
import unittest

path = Path(__file__).resolve().parents[1]/'tools/a22_remote_jobs.py'
spec = importlib.util.spec_from_file_location('a22_stop_transport_test', path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class StopOwnerTests(unittest.TestCase):
    def test_exact_registered_job_and_module(self):
        line = 'D:/python/python.exe -B -u -m a22.cli screen --root D:/AI/A22_THREE_FOLD_OPM --device cuda --job a22-cuda-screen-001'
        self.assertTrue(module._screen_owner_matches(line, module.REMOTE, 'a22-cuda-screen-001'))
        self.assertFalse(module._screen_owner_matches(line, module.REMOTE, 'a22-cuda-screen'))
        self.assertFalse(module._screen_owner_matches(line, module.REMOTE, 'a22-cuda-screen-002'))
        self.assertFalse(module._screen_owner_matches(line.replace('a22.cli', 'a21.cli'), module.REMOTE, 'a22-cuda-screen-001'))

    def test_root_prefix_and_other_stage_refused(self):
        line = 'D:/python/python.exe -m a22.cli screen-resume --root "D:\\AI\\A22_THREE_FOLD_OPM" --job a22-owned'
        self.assertTrue(module._screen_owner_matches(line, module.REMOTE, 'a22-owned'))
        self.assertFalse(module._screen_owner_matches(line.replace('OPM"', 'OPM_OTHER"'), module.REMOTE, 'a22-owned'))
        self.assertFalse(module._screen_owner_matches(line.replace('screen-resume', 'validate'), module.REMOTE, 'a22-owned'))
        self.assertFalse(module._screen_owner_matches('', module.REMOTE, 'a22-owned'))
