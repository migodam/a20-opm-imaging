"""Transport command-length fixtures. All SSH/SCP boundaries are fake."""
from __future__ import annotations

import ast
import base64
import importlib.util
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch


PROJECT = Path(__file__).resolve().parents[1]


def load_tool():
    spec = importlib.util.spec_from_file_location('a22_length_fixture',PROJECT/'tools/a22_remote_jobs.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeTransport:
    def __init__(self, response='{"status":"FIXTURE_OK"}'):
        self.response = response
        self.shell_calls = []
        self.uploads = []

    def shell(self, script, *, timeout=None):
        self.shell_calls.append((script,timeout))
        return '' if 'New-Item' in script else self.response

    def copy_to(self, source, name):
        path = Path(source)
        self.uploads.append(dict(name=name,local_path=path,source=path.read_text(encoding='utf-8')))


class TransportLengthTests(unittest.TestCase):
    def test_short_command_keeps_inline_path_and_json_result(self):
        tool, transport = load_tool(), FakeTransport()
        row = tool._python(transport,"print('short')",timeout=23)
        self.assertEqual(row,dict(status='FIXTURE_OK'))
        self.assertEqual(transport.uploads,[])
        self.assertEqual(len(transport.shell_calls),1)
        script, timeout = transport.shell_calls[0]
        self.assertIn(' -B -c ',script)
        self.assertEqual(timeout,23)
        self.assertLessEqual(len(tool._powershell_command(script)),tool.MAX_INLINE_COMMAND_CHARS)

    def test_long_command_uploads_accounted_bootstrap_then_uses_short_invocation(self):
        tool, transport = load_tool(), FakeTransport()
        code = '#'+('long_source_'*1200)+"\nprint('long')\n"
        row = tool._python(transport,code,timeout=41)
        self.assertEqual(row['status'],'FIXTURE_OK')
        self.assertEqual(len(transport.uploads),1)
        uploaded = transport.uploads[0]
        self.assertRegex(uploaded['name'],r'^a22-transport-code-[0-9a-f]{32}\.py$')
        self.assertFalse(uploaded['local_path'].exists())
        ast.parse(uploaded['source'])
        self.assertIn('_a22_remote_process_origin=time.perf_counter()',uploaded['source'])
        self.assertIn('remote_process_cpu_seconds=time.process_time()',uploaded['source'])
        self.assertIn(base64.b64encode(code.encode()).decode(),uploaded['source'])
        self.assertEqual(len(transport.shell_calls),2)
        setup, invocation = (call[0] for call in transport.shell_calls)
        self.assertIn("New-Item -ItemType Directory -Force 'D:/AI/A22_THREE_FOLD_OPM'",setup)
        self.assertIn("D:/python/python.exe' -B 'D:/AI/A22_THREE_FOLD_OPM/"+uploaded['name'],invocation)
        self.assertNotIn(' -c ',invocation)
        self.assertEqual(transport.shell_calls[-1][1],41)
        self.assertTrue(all(len(tool._powershell_command(script))<=tool.MAX_INLINE_COMMAND_CHARS
                            for script,_ in transport.shell_calls))

    def test_threshold_checks_encoded_windows_length_rather_than_source_length(self):
        tool, transport = load_tool(), FakeTransport()
        code = '#'+('x'*2500)+"\nprint('small source large command')\n"
        self.assertLess(len(code),tool.MAX_INLINE_COMMAND_CHARS)
        tool._python(transport,code)
        self.assertEqual(len(transport.uploads),1)

    def test_forced_file_uses_unique_names_and_never_transfers_private_configuration(self):
        tool, transport = load_tool(), FakeTransport()
        tool._python(transport,"print('controller')",force_file=True)
        tool._python(transport,"print('controller')",force_file=True)
        names = [item['name'] for item in transport.uploads]
        self.assertEqual(len(names),2)
        self.assertEqual(len(set(names)),2)
        for item in transport.uploads:
            self.assertNotIn('A20_SSH_KEY',item['source'])
            self.assertNotIn('A20_SSH_TARGET',item['source'])
            self.assertNotIn('ssh_connection.json',item['source'])

    def test_run_controller_is_always_forced_to_file(self):
        tool, transport = load_tool(), FakeTransport()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'configs').mkdir()
            (root/'configs/a22.json').write_text('{}')
            with patch.object(tool,'connection',return_value=transport), patch.object(tool,'_python',return_value=dict(status='COMPLETE')) as remote:
                tool.run('screen','a22-length-unit','cpu','not_read_fixture',root=root)
            self.assertIs(remote.call_args.kwargs['force_file'],True)

    def test_transfer_failure_preserves_failure_without_falling_back_to_long_inline(self):
        tool, transport = load_tool(), FakeTransport()
        with patch.object(transport,'copy_to',side_effect=tool.TransportFailure('Fixture transfer failed')):
            with self.assertRaises(tool.TransportFailure):
                tool._python(transport,'#'+('x'*10000),force_file=True)
        self.assertEqual(len(transport.shell_calls),1)
        self.assertIn('New-Item',transport.shell_calls[0][0])

    def test_uploaded_script_still_uses_sanitized_json_parser(self):
        tool, transport = load_tool(), FakeTransport('banner\n{"status":"REMOTE_SAFE"}')
        self.assertEqual(tool._python(transport,'print(1)',force_file=True)['status'],'REMOTE_SAFE')
        transport.response = 'malformed output'
        with self.assertRaises(tool.TransportFailure) as caught:
            tool._python(transport,'print(1)',force_file=True)
        self.assertEqual(str(caught.exception),'Remote response was not a sanitized receipt')


if __name__=='__main__':
    unittest.main()
