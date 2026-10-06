"""Accounting, input-header and transport boundaries; no Maxwell or remote job."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import zipfile

import numpy as np

from a20.costs import BudgetExceeded
from a21.budget import A21Book, history, register_external
from a21.cli import canonical_inputs, main as cli_main, npz_headers


PROJECT = Path(__file__).resolve().parents[1]


def config():
    return dict(historical_CPU_seconds=100.0, historical_GPU_seconds=200.0,
                anatomy_CPU_seconds=1200.0, anatomy_GPU_seconds=1200.0,
                anatomy_CPU_reserve_seconds=60.0, anatomy_GPU_reserve_seconds=60.0,
                budget_cpu_seconds=7200.0, budget_gpu_wall_seconds=43200.0,
                cpu_epilogue_reserve_seconds=300.0, gpu_preoperation_reserve_seconds=120.0,
                source_freeze='a' * 40, setup_transport_overhead_allowance_CPU_seconds=30.0,
                parents=[2001, 2005, 2003, 2007, 2013])


def root_files(root, cfg=None):
    cfg = config() if cfg is None else cfg
    (root/'configs').mkdir(parents=True)
    (root/'results/a21').mkdir(parents=True)
    (root/'results/jobs').mkdir(parents=True)
    (root/'configs/a21.json').write_text(json.dumps(cfg))
    (root/'results/a21/external_cpu_receipts.json').write_text('[]')
    return cfg


def receipt(root, job, cpu, gpu=0.0, status='FAILED'):
    path = root/'results/jobs'/job
    path.mkdir(parents=True)
    (path/'job_receipt.json').write_text(json.dumps(dict(process_cpu_seconds=cpu,
                                                       gpu_occupation_seconds=gpu, status=status)))


def load_tool(name):
    spec = importlib.util.spec_from_file_location('a21_test_' + name, PROJECT/'tools'/(name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AccountingTests(unittest.TestCase):
    def test_only_new_inclusive_receipts_and_unique_registry_are_additive(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cfg = root_files(root)
            receipt(root, 'r1-old', 999.0, 888.0)
            receipt(root, 'a21-failed', 3.0, 4.0)
            (root/'results/jobs/a21-failed/cost.jsonl').write_text('{"process_cpu_seconds":5000}\n')
            (root/'COST_LEDGER.jsonl').write_text('original ledger preserved')
            register_external(root, 'controller', 10.0)
            measured = history(root)
            self.assertEqual(measured['a21_cpu'], 13.0)
            self.assertEqual(measured['a21_gpu'], 4.0)
            self.assertEqual(measured['global_cpu'], 113.0)
            self.assertEqual(measured['global_gpu'], 204.0)
            self.assertEqual(measured['jobs'], ['a21-failed'])
            self.assertTrue(measured['nested_spans_not_additive'])
            self.assertEqual((root/'COST_LEDGER.jsonl').read_text(), 'original ledger preserved')

    def test_external_double_registration_and_nonfinite_seconds_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            root_files(root)
            register_external(root, 'paid', 1.0)
            before = (root/'results/a21/external_cpu_receipts.json').read_bytes()
            with self.assertRaises(ValueError):
                register_external(root, 'paid', 1.0)
            with self.assertRaises(ValueError):
                register_external(root, 'nan', float('nan'))
            with self.assertRaises(ValueError):
                register_external(root, 'negative', -1.0)
            self.assertEqual(before, (root/'results/a21/external_cpu_receipts.json').read_bytes())

    def test_cap_is_checked_before_counting_a_physical_action(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cfg = root_files(root)
            register_external(root, 'already paid', 1140.0)
            with patch('a21.budget.time.process_time', return_value=0.0):
                book = A21Book(root, cfg)
                with self.assertRaises(BudgetExceeded):
                    with book.span('L', L_actions=1):
                        self.fail('Action ran after the cap')
            self.assertEqual(book.counts.get('L_actions', 0), 0)

    def test_child_cpu_and_import_cpu_share_the_same_120_second_validation_cap(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cfg = root_files(root)
            with patch('a21.budget.time.process_time', return_value=10.0):
                book = A21Book(root, cfg, job_cpu_limit=120)
                book.add_child_cpu(15.0)
                self.assertEqual(book.receipt()['process_cpu_seconds'], 25.0)
                self.assertEqual(book.remaining_cpu_seconds(), 95.0)
                book.add_child_cpu(95.0)
                with self.assertRaises(BudgetExceeded):
                    book.check()

    def test_nested_spans_do_not_become_extra_billing_and_failure_rows_survive(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cfg = root_files(root)
            clock = [1.0]
            with patch('a21.budget.time.process_time', side_effect=lambda: clock[0]):
                book = A21Book(root, cfg, root/'results/jobs/a21-fixture/cost.jsonl')
                with book.span('outer'):
                    with self.assertRaises(RuntimeError):
                        with book.span('failed_inner', tiny_actions=1):
                            clock[0] = 2.0
                            raise RuntimeError('synthetic failure')
                    clock[0] = 3.0
                item = book.receipt()
            self.assertEqual(item['process_cpu_seconds'], 3.0)
            self.assertEqual(book.counts['tiny_actions'], 1)
            (root/'results/jobs/a21-fixture/job_receipt.json').write_text(json.dumps(item))
            self.assertEqual(history(root)['a21_cpu'], 3.0)
            self.assertIn('failed_inner', (root/'results/a21/FAILURE_LEDGER.jsonl').read_text())
            self.assertFalse((root/'FAILURE_LEDGER.jsonl').exists())

    def test_epilogue_can_use_reserve_without_extending_the_total_cap(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cfg = root_files(root)
            register_external(root, 'near cap', 1180.0)
            with patch('a21.budget.time.process_time', return_value=5.0):
                with self.assertRaises(BudgetExceeded):
                    A21Book(root, cfg).check()
                report = A21Book(root, cfg, epilogue=True)
                report.check()
                report.add_child_cpu(15.0)
                with self.assertRaises(BudgetExceeded):
                    report.check()

    def test_cumulative_historical_cap_is_independent_of_the_new_cap(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cfg = config()
            cfg['historical_CPU_seconds'] = 6899.0
            root_files(root, cfg)
            with patch('a21.budget.time.process_time', return_value=1.0):
                with self.assertRaises(BudgetExceeded):
                    A21Book(root, cfg).check()

    def test_failed_driver_import_is_preserved_and_charged(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            root_files(root)
            with patch('a21.cli._load_integrity', side_effect=ImportError('deliberate synthetic import failure')):
                status = cli_main(['validate', '--root', str(root), '--job', 'a21-import-fixture'])
            self.assertEqual(status, 2)
            saved = json.loads((root/'results/jobs/a21-import-fixture/job_receipt.json').read_text())
            failure = json.loads((root/'results/jobs/a21-import-fixture/result.json').read_text())
            self.assertEqual(failure['error_type'], 'ImportError')
            self.assertGreater(saved['process_cpu_seconds'], 0)
            self.assertTrue(saved['failed_imports_included'])
            self.assertNotIn('A20_SSH_TARGET', saved['environment'])
            self.assertEqual(history(root)['a21_cpu'], saved['process_cpu_seconds'])


class InputAndTransportTests(unittest.TestCase):
    def test_header_reader_rejects_offline_keys_and_object_arrays(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            np.savez(root/'tiny.npz', step=np.zeros(2))
            self.assertEqual(npz_headers(root/'tiny.npz', allowed={'step'})['step']['shape'], [2])
            np.savez(root/'offline.npz', step=np.zeros(2), truth=np.zeros(2))
            with self.assertRaises(ValueError):
                npz_headers(root/'offline.npz', allowed={'step'})
            np.savez(root/'object.npz', step=np.array([{}], dtype=object))
            with self.assertRaises(ValueError):
                npz_headers(root/'object.npz', allowed={'step'})

    def test_failed_subprocess_import_includes_child_cpu_and_keeps_its_log(self):
        tool = load_tool('a21_integrity')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cfg = root_files(root)
            book = A21Book(root, cfg, job_cpu_limit=120)
            command = [sys.executable, '-B', '-c', 'import a21_deliberately_absent_fixture_module']
            row = tool._run_child(root, command, root/'failed_import.log', book, time.perf_counter()+10)
            self.assertEqual(row['status'], 'FAILED')
            self.assertGreater(row['process_cpu_seconds'], 0)
            self.assertEqual(book.child_cpu_seconds, row['process_cpu_seconds'])
            self.assertIn('ModuleNotFoundError', (root/'failed_import.log').read_text())

    def test_deploy_whitelist_excludes_labels_old_receipts_and_private_files(self):
        tool = load_tool('a21_remote_jobs')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cfg = root_files(root)
            for name in ('frozen.json', 'parents.json', 'a20_r1.json'):
                (root/'configs'/name).write_text('{}')
            (root/'configs/A21_SOURCE_COMMIT.txt').write_text('b'*40)
            (root/'private').mkdir()
            (root/'private/connection-fixture.json').write_text('{}')
            (root/'data/offline').mkdir(parents=True)
            (root/'data/offline/labels.npz').write_bytes(b'fixture')
            (root/'results/replay/steps').mkdir(parents=True)
            rows = []
            for parent in cfg['parents']:
                directory_path = root/'data/runtime'/str(parent)
                directory_path.mkdir(parents=True)
                for name in ('problem.npz', 'state_00.npz', 'state_17.npz'):
                    (directory_path/name).write_bytes(b'fixture')
                for kind in ('reference', 'baseline'):
                    filename = str(parent)+'_'+kind+'.npz'
                    (root/'results/replay/steps'/filename).write_bytes(b'fixture')
                    rows.append(dict(parent_object_id=parent, iteration=17, degree=3,
                                     record_kind='shared_reference' if kind=='reference' else 'method',
                                     method='full_GN_reference' if kind=='reference' else 'mixed',
                                     **{('reference_step_path' if kind=='reference' else 'step_path'): 'D:/old/steps/'+filename}))
            (root/'results/replay/replay.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
            receipt(root, 'r1-old', 99)
            receipt(root, 'a21-new', 1)
            members = tool.deployment_members(root)
            self.assertTrue(all('private/' not in name and 'offline/' not in name for name in members))
            self.assertFalse(any('state_00' in name or 'r1-old' in name for name in members))
            self.assertIn('results/jobs/a21-new/job_receipt.json', members)
            self.assertEqual(len([name for name in members if name.startswith('results/replay/steps/')]), 10)
            self.assertEqual(len(canonical_inputs(root, cfg)), 10)
            (root/'results/replay/replay.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows+[rows[0]]))
            with self.assertRaises(ValueError):
                canonical_inputs(root, cfg)

    def test_pull_refuses_conflicting_immutable_job_and_preserves_original_root(self):
        tool = load_tool('a21_remote_jobs')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            root_files(root)
            receipt(root, 'a21-old', 1)
            (root/'COST_LEDGER.jsonl').write_text('original')
            archive = root/'fixture.zip'
            with zipfile.ZipFile(archive, 'w') as zipped:
                zipped.writestr('results/jobs/a21-old/job_receipt.json', '{"process_cpu_seconds":2}')
            with self.assertRaises(ValueError):
                tool._merge_jobs(archive, root)
            self.assertEqual(history(root)['a21_cpu'], 1)
            self.assertEqual((root/'COST_LEDGER.jsonl').read_text(), 'original')
            with zipfile.ZipFile(archive, 'w') as zipped:
                zipped.writestr('results/jobs/r1-old/job_receipt.json', '{}')
            with self.assertRaises(ValueError):
                tool._merge_jobs(archive, root)

    def test_pull_external_union_keeps_local_validation_and_no_double_registration(self):
        tool = load_tool('a21_remote_jobs')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            root_files(root)
            register_external(root, 'local validation', 2)
            local = json.loads((root/'results/a21/external_cpu_receipts.json').read_text())
            remote = dict(scope='remote archive', process_cpu_seconds=3, GPU_seconds=0)
            archive = root/'fixture.zip'
            with zipfile.ZipFile(archive, 'w') as zipped:
                zipped.writestr('results/a21/external_cpu_receipts.json', json.dumps(local+[remote]))
            tool._merge_jobs(archive, root)
            tool._merge_jobs(archive, root)
            self.assertEqual(history(root)['a21_cpu'], 5)

    def test_transport_decodes_non_utf8_and_does_not_expose_private_argv(self):
        tool = load_tool('a21_remote_jobs')
        with patch.object(tool, '_private_stderr') as private:
            adapter = tool._transport()
            completed = subprocess.CompletedProcess(['redacted'], 0, stdout=b'OK\xd5', stderr=b'private stderr')
            with patch.object(tool.subprocess, 'run', return_value=completed):
                self.assertIn('OK', adapter.subprocess.check_output(['ssh', 'private-fixture'], text=True))
            private.assert_called_with(b'private stderr')
            failed = subprocess.CompletedProcess(['private key and host fixture'], 255, stdout=b'', stderr=b'private stderr')
            with patch.object(tool.subprocess, 'run', return_value=failed):
                with self.assertRaises(tool.TransportFailure) as caught:
                    adapter.subprocess.check_output(['private key and host fixture'], text=True)
            self.assertNotIn('private key', str(caught.exception))
            self.assertIn('255', str(caught.exception))


if __name__ == '__main__':
    unittest.main()
