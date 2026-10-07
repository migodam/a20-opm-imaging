"""Pure unittest budget/transport fixtures; no Maxwell, SSH, or CUDA execution."""
from __future__ import annotations

from contextlib import ExitStack
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from a20.costs import BudgetExceeded, CostBook
from a22.budget import (
    A22Book, GPU_WALL_CAP, STAGE_GPU_CAPS, history, merge_receipt,
    normalize_config, register_external, write_json,
)


PROJECT = Path(__file__).resolve().parents[1]


def config(**updates):
    result = dict(gpu_wall_cap_seconds=GPU_WALL_CAP,
                  stage_gpu_caps_seconds=dict(STAGE_GPU_CAPS),
                  perturbation_evaluation_cap=192, new_teacher_label_cap=9,
                  correction_events=0)
    result.update(updates)
    return result


def root_files(root, cfg=None):
    (root / 'configs').mkdir(parents=True, exist_ok=True)
    (root / 'configs/a22.json').write_text(json.dumps(config() if cfg is None else cfg))
    return root


def receipt(job, *, cpu=0.0, gpu=0.0, stage='direction', counts=None, status='FAILED', stages=None):
    row = dict(campaign='A22', job_id=job, stage=stage,
               device='cuda' if gpu else 'cpu', process_cpu_seconds=cpu,
               wall_seconds=max(cpu, gpu), gpu_occupation_seconds=gpu,
               counts=counts or {}, corrections={}, status=status)
    if stages is not None:
        row['stage_gpu_seconds'] = stages
    return row


def gpu_unit_clock(wall, cpu=None):
    """Mock CUDA boundaries and timers. The unit suite never imports CUDA."""
    stack = ExitStack()
    stack.enter_context(patch('a22.budget.time.perf_counter', side_effect=lambda: wall[0]))
    stack.enter_context(patch('a22.budget.time.process_time', side_effect=lambda: 0.0 if cpu is None else cpu[0]))
    stack.enter_context(patch.object(A22Book, 'synchronize', return_value=None))
    stack.enter_context(patch.object(CostBook, 'check', return_value=None))
    return stack


def load_transport():
    spec = importlib.util.spec_from_file_location('a22_unit_transport', PROJECT / 'tools/a22_remote_jobs.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def windows_sharing_error(code=5):
    error = PermissionError('simulated Windows sharing or delete access denial')
    error.winerror = code
    return error


class AtomicAccountingTests(unittest.TestCase):
    def test_transient_windows_reader_contention_keeps_complete_snapshots(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'accounting_checkpoint.json'
            old, new = {'counts': {'F_calls': 1}}, {'counts': {'F_calls': 2}}
            target.write_text(json.dumps(old))
            original_replace = Path.replace
            attempts = []

            def held_reader(temporary, destination):
                # The simulated reader observes the original complete document
                # until a successful atomic replacement; no truncated target.
                self.assertEqual(json.loads(target.read_text()), old)
                self.assertEqual(json.loads(temporary.read_text()), new)
                attempts.append(temporary)
                if len(attempts) < 3:
                    raise windows_sharing_error(5 if len(attempts) == 1 else 32)
                return original_replace(temporary, destination)

            with patch.object(Path, 'replace', held_reader), patch('a22.budget.time.sleep') as sleep:
                write_json(target, new)
            self.assertEqual(json.loads(target.read_text()), new)
            self.assertEqual(len(attempts), 3)
            self.assertEqual(len(set(attempts)), 1)
            self.assertFalse(attempts[0].exists())
            self.assertEqual(sleep.call_count, 2)

    def test_persistent_windows_contention_is_bounded_and_retains_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'accounting_checkpoint.json'
            target.write_text('{"counts":{"F_calls":1}}')
            failure = windows_sharing_error(33)
            with patch.object(Path, 'replace', side_effect=failure) as replace, patch('a22.budget.time.sleep') as sleep:
                with self.assertRaises(PermissionError) as raised:
                    write_json(target, {'counts': {'F_calls': 2}})
            self.assertIs(raised.exception, failure)
            self.assertEqual(replace.call_count, 5)
            self.assertEqual(sleep.call_count, 4)
            self.assertLessEqual(sum(call.args[0] for call in sleep.call_args_list), 0.151)
            self.assertEqual(json.loads(target.read_text()), {'counts': {'F_calls': 1}})
            pending = list(target.parent.glob(target.name + '.*.tmp'))
            self.assertEqual(len(pending), 1)
            self.assertEqual(json.loads(pending[0].read_text()), {'counts': {'F_calls': 2}})
            # A subsequent writer has its own temporary path and cannot erase
            # the exhausted attempt's diagnostic snapshot.
            write_json(target, {'counts': {'F_calls': 3}})
            self.assertTrue(pending[0].exists())
            self.assertEqual(json.loads(target.read_text()), {'counts': {'F_calls': 3}})

    def test_unrelated_filesystem_errors_are_not_retried(self):
        for error in (PermissionError('actual permission denial'), FileNotFoundError('missing directory')):
            with self.subTest(error=type(error).__name__), tempfile.TemporaryDirectory() as directory:
                target = Path(directory) / 'accounting_checkpoint.json'
                target.write_text('{"old":true}')
                with patch.object(Path, 'replace', side_effect=error) as replace, patch('a22.budget.time.sleep') as sleep:
                    with self.assertRaises(type(error)):
                        write_json(target, {'new': True})
                self.assertEqual(replace.call_count, 1)
                sleep.assert_not_called()
                self.assertEqual(json.loads(target.read_text()), {'old': True})

    def test_retry_does_not_repeat_failed_physics_or_reset_call_cap(self):
        with tempfile.TemporaryDirectory() as directory:
            root = root_files(Path(directory), config(perturbation_evaluation_cap=1))
            book = A22Book(root, job_id='a22-checkpoint-retry')
            original_replace = Path.replace
            attempts, physical_calls = [], []

            def held_checkpoint(temporary, destination):
                attempts.append(temporary)
                if len(attempts) <= 2:
                    raise windows_sharing_error()
                return original_replace(temporary, destination)

            with patch.object(Path, 'replace', held_checkpoint), patch('a22.budget.time.sleep'):
                with self.assertRaisesRegex(RuntimeError, 'physical failure'):
                    with book.action_guard('data_generation', F_calls=1):
                        physical_calls.append('attempt')
                        raise RuntimeError('physical failure')
            with self.assertRaises(BudgetExceeded):
                with book.action_guard('data_generation', F_calls=1):
                    self.fail('Sharing retry reset the paid failed-call cap')
            paid = book.finish('FAILED')
            self.assertEqual(physical_calls, ['attempt'])
            self.assertEqual(paid['counts']['F_calls'], 1)
            self.assertEqual(paid['counts']['data_generation_F_calls'], 1)
            self.assertEqual(history(root)['counts']['data_generation_F_calls'], 1)

    def test_retry_backoff_remains_paid_gpu_wall_and_cannot_extend_stage_cap(self):
        with tempfile.TemporaryDirectory() as directory:
            caps = dict(STAGE_GPU_CAPS, direction=0.02)
            root = root_files(Path(directory), config(stage_gpu_caps_seconds=caps))
            wall = [100.0]
            original_replace = Path.replace
            attempts = []

            def held_checkpoint(temporary, destination):
                attempts.append(temporary)
                if len(attempts) <= 2:
                    raise windows_sharing_error()
                return original_replace(temporary, destination)

            def elapsed_backoff(seconds):
                wall[0] += seconds

            with gpu_unit_clock(wall):
                book = A22Book(root, job_id='a22-checkpoint-wall', stage='direction', device='cuda')
                with patch.object(Path, 'replace', held_checkpoint), patch('a22.budget.time.sleep', side_effect=elapsed_backoff):
                    book._checkpoint()
                with self.assertRaises(BudgetExceeded):
                    book.check()
                paid = book.finish('BUDGET_REFUSED')
            self.assertAlmostEqual(paid['gpu_occupation_seconds'], 0.03)
            self.assertAlmostEqual(paid['stage_gpu_seconds']['direction'], 0.03)
            self.assertEqual(paid['process_cpu_seconds'], 0)
            self.assertAlmostEqual(history(root)['a22_gpu'], 0.03)


class BudgetTests(unittest.TestCase):
    def test_frozen_caps_cannot_expand_or_borrow(self):
        self.assertEqual(sum(STAGE_GPU_CAPS.values()), GPU_WALL_CAP)
        for override in (dict(gpu_wall_cap_seconds=32401),
                         dict(stage_gpu_caps_seconds={'direction': 7201}),
                         dict(perturbation_evaluation_cap=193),
                         dict(new_teacher_label_cap=10), dict(correction_events=2)):
            with self.assertRaises(ValueError):
                normalize_config(config(**override))

    def test_a21_historical_costs_are_record_only_and_cpu_has_no_cap(self):
        with tempfile.TemporaryDirectory() as directory:
            root = root_files(Path(directory), config(historical_CPU_seconds=1e10, historical_GPU_seconds=1e10))
            old = root / 'results/jobs/a21-old'
            old.mkdir(parents=True)
            (old / 'job_receipt.json').write_text(json.dumps(dict(process_cpu_seconds=1e10, gpu_occupation_seconds=1e10)))
            register_external(root, 'new A22 CPU', 1e9)
            with patch('a22.budget.time.process_time', return_value=1e8):
                book = A22Book(root, job_id='a22-cpu-no-cap')
                book.check()
                book.finish()
            measured = history(root)
            self.assertEqual(measured['a22_cpu'], 1.1e9)
            self.assertEqual(measured['a22_gpu'], 0)
            self.assertIsNone(measured['CPU_cap'])
            self.assertEqual(measured['jobs'], ['a22-cpu-no-cap'])

    def test_stage_budget_refuses_before_an_action_is_counted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = root_files(Path(directory))
            merge_receipt(root, receipt('a22-near-stage', gpu=7199))
            wall = [100.0]
            with gpu_unit_clock(wall):
                book = A22Book(root, stage='direction', job_id='a22-refused', device='cuda')
                with self.assertRaises(BudgetExceeded):
                    book.preflight(gpu_seconds=1)
                wall[0] += 1
                with self.assertRaises(BudgetExceeded):
                    with book.span('never_started', F_calls=1):
                        self.fail('Action ran after stage cap')
                self.assertEqual(book.counts.get('F_calls', 0), 0)
                book.finish('BUDGET_REFUSED')
            self.assertIn('A22_STAGE_GPU_WALL_CAP', (root / 'results/a22/FAILURE_LEDGER.jsonl').read_text())

    def test_global_budget_refusal_is_independent_of_active_stage(self):
        with tempfile.TemporaryDirectory() as directory:
            root = root_files(Path(directory), config(gpu_wall_cap_seconds=10))
            merge_receipt(root, receipt('a22-prior-gpu', gpu=9, stage='features'))
            wall = [100.0]
            with gpu_unit_clock(wall):
                book = A22Book(root, job_id='a22-global-refused', stage='direction', device='cuda')
                with self.assertRaises(BudgetExceeded):
                    book.preflight(gpu_seconds=1)

    def test_failed_generation_and_retries_are_charged_before_work(self):
        with tempfile.TemporaryDirectory() as directory:
            root = root_files(Path(directory), config(perturbation_evaluation_cap=2))
            book = A22Book(root, job_id='a22-failed-generation', stage='direction', role='offline_label')
            with self.assertRaises(RuntimeError):
                with book.action_guard('perturbation_forward', F_calls=1):
                    raise RuntimeError('fixture failure')
            with book.action_guard('perturbation_forward', F_calls=1):
                pass
            with self.assertRaises(BudgetExceeded):
                with book.action_guard('perturbation_forward', F_calls=1):
                    self.fail('Third generation call ran')
            final = book.finish('FAILED')
            self.assertEqual(final['counts']['data_generation_F_calls'], 2)
            self.assertEqual(history(root)['counts']['data_generation_F_calls'], 2)
            self.assertIn('RuntimeError', (root / 'results/a22/FAILURE_LEDGER.jsonl').read_text())
            self.assertNotIn('fixture failure', (root / 'results/a22/FAILURE_LEDGER.jsonl').read_text())

    def test_generation_cap_is_global_across_jobs_and_health_fd_calls(self):
        with tempfile.TemporaryDirectory() as directory:
            root = root_files(Path(directory), config(perturbation_evaluation_cap=2))
            merge_receipt(root, receipt('a22-first-scene', counts={'data_generation_F_calls': 1}))
            book = A22Book(root, job_id='a22-health-fd', stage='screen_health', role='health')
            with book.action_guard('health_fd_forward', F_calls=1):
                pass
            with self.assertRaises(BudgetExceeded):
                with book.action_guard('data_generation', F_calls=1):
                    self.fail('Generation cap was reset at stage entry')
            book.finish()
            self.assertEqual(history(root)['counts']['data_generation_F_calls'], 2)

    def test_new_teacher_labels_spend_both_label_and_generation_caps(self):
        with tempfile.TemporaryDirectory() as directory:
            root = root_files(Path(directory), config(new_teacher_label_cap=1))
            book = A22Book(root, job_id='a22-new-label', role='offline_label')
            with self.assertRaises(RuntimeError):
                with book.action_guard('new_teacher_label', F_calls=2):
                    raise RuntimeError('failed label is still paid')
            with self.assertRaises(BudgetExceeded):
                with book.action_guard('new_teacher_label'):
                    self.fail('Second label was admitted')
            measured = book.finish('FAILED')
            self.assertEqual(measured['counts']['new_teacher_labels'], 1)
            self.assertEqual(measured['counts']['data_generation_F_calls'], 2)

    def test_live_checkpoint_retains_started_actions_without_final_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = root_files(Path(directory))
            book = A22Book(root, job_id='a22-live-counter')
            with book.action_guard('data_generation'):
                live = history(root)
                self.assertEqual(live['counts']['data_generation_F_calls'], 1)
                self.assertEqual(live['live_jobs'], ['a22-live-counter'])
            book.finish()
            self.assertEqual(history(root)['live_jobs'], [])

    def test_duplicate_job_receipt_is_idempotent_and_conflict_preserves_original(self):
        with tempfile.TemporaryDirectory() as directory:
            root = root_files(Path(directory))
            row = receipt('a22-duplicate', cpu=3, gpu=4, counts={'F_calls': 2})
            self.assertTrue(merge_receipt(root, row))
            self.assertFalse(merge_receipt(root, row))
            with self.assertRaises(ValueError):
                merge_receipt(root, dict(row, process_cpu_seconds=4))
            measured = history(root)
            self.assertEqual(measured['a22_cpu'], 3)
            self.assertEqual(measured['a22_gpu'], 4)
            self.assertEqual(measured['counts']['F_calls'], 2)
            self.assertEqual(len((root / 'results/a22/JOB_LEDGER.jsonl').read_text().splitlines()), 1)

    def test_unique_job_ids_are_reserved_persistently(self):
        with tempfile.TemporaryDirectory() as directory:
            root = root_files(Path(directory))
            first = A22Book(root, job_id='a22-reserved')
            with self.assertRaises(ValueError):
                A22Book(root, job_id='a22-reserved')
            first.finish()
            with self.assertRaises(ValueError):
                A22Book(root, job_id='a22-reserved')

    def test_nested_spans_do_not_double_bill_cpu_or_gpu(self):
        with tempfile.TemporaryDirectory() as directory:
            root = root_files(Path(directory))
            wall, cpu = [100.0], [0.0]
            with gpu_unit_clock(wall, cpu):
                book = A22Book(root, stage='image', job_id='a22-nested', device='cuda')
                with book.span('outer'):
                    wall[0], cpu[0] = 102, 1
                    with book.span('inner', F_calls=1):
                        wall[0], cpu[0] = 105, 3
                    wall[0], cpu[0] = 108, 4
                row = book.finish()
            self.assertEqual(row['process_cpu_seconds'], 4)
            self.assertEqual(row['gpu_occupation_seconds'], 8)
            self.assertEqual(sum(row['exclusive_walls'].values()), 8)
            spans = [json.loads(line) for line in (root / 'results/jobs/a22-nested/cost.jsonl').read_text().splitlines()]
            self.assertEqual(sum(span['exclusive_process_cpu_seconds'] for span in spans), 4)
            self.assertEqual(sum(span['process_cpu_seconds'] for span in spans), 6)
            self.assertEqual(history(root)['a22_cpu'], 4)
            self.assertEqual(history(root)['a22_gpu'], 8)
            self.assertTrue(row['CPU_and_GPU_resources_not_summed'])

    def test_stage_scopes_are_exclusive_and_job_gpu_is_inclusive_once(self):
        with tempfile.TemporaryDirectory() as directory:
            root = root_files(Path(directory))
            wall = [100.0]
            with gpu_unit_clock(wall):
                book = A22Book(root, stage='screen_health', job_id='a22-stage-scopes', device='cuda')
                wall[0] = 102
                with book.stage_scope('features'):
                    wall[0] = 105
                    with book.stage_scope('direction'):
                        wall[0] = 109
                    wall[0] = 110
                wall[0] = 111
                row = book.finish()
            self.assertEqual(row['gpu_occupation_seconds'], 11)
            self.assertEqual(row['stage_gpu_seconds']['screen_health'], 3)
            self.assertEqual(row['stage_gpu_seconds']['features'], 4)
            self.assertEqual(row['stage_gpu_seconds']['direction'], 4)
            self.assertEqual(sum(row['stage_gpu_seconds'].values()), 11)
            self.assertEqual(history(root)['stage_gpu_seconds'], row['stage_gpu_seconds'])

    def test_feature_scope_cannot_borrow_unused_direction_time(self):
        with tempfile.TemporaryDirectory() as directory:
            caps = dict(STAGE_GPU_CAPS, features=5)
            root = root_files(Path(directory), config(stage_gpu_caps_seconds=caps))
            wall = [100.0]
            with gpu_unit_clock(wall):
                book = A22Book(root, stage='direction', job_id='a22-no-borrow', device='cuda')
                with book.stage_scope('features'):
                    wall[0] = 105
                    with self.assertRaises(BudgetExceeded):
                        book.check()
                row = book.finish('BUDGET_REFUSED')
            self.assertEqual(row['stage_gpu_seconds']['features'], 5)
            self.assertEqual(row['stage_gpu_seconds']['direction'], 0)

    def test_finished_stage_does_not_reset_or_block_another_stage(self):
        with tempfile.TemporaryDirectory() as directory:
            root = root_files(Path(directory))
            merge_receipt(root, receipt('a22-feature-cap', gpu=3600, stage='features'))
            wall = [100.0]
            with gpu_unit_clock(wall):
                book = A22Book(root, stage='direction', job_id='a22-after-features', device='cuda')
                book.check()
                with self.assertRaises(BudgetExceeded):
                    with book.stage_scope('features'):
                        self.fail('Already spent stage budget was reset')

    def test_stage_gpu_accounting_must_sum_to_inclusive_job(self):
        with tempfile.TemporaryDirectory() as directory:
            root = root_files(Path(directory))
            with self.assertRaises(ValueError):
                merge_receipt(root, receipt('a22-bad-stage-sum', gpu=3, stages={'direction': 2}))
            with self.assertRaises(ValueError):
                merge_receipt(root, dict(receipt('a22-cpu-with-gpu', gpu=1), device='cpu'))

    def test_cpu_and_child_cpu_are_measured_without_gpu_occupation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = root_files(Path(directory))
            with patch('a22.budget.time.process_time', return_value=5):
                book = A22Book(root, job_id='a22-cpu-child')
                book.add_child_cpu(3)
                self.assertEqual(book.receipt()['process_cpu_seconds'], 8)
                self.assertEqual(book.receipt()['gpu_occupation_seconds'], 0)
                self.assertEqual(book.remaining_cpu_seconds(), float('inf'))
                row = book.finish()
                self.assertEqual(book.finish(), row)

    def test_offline_actions_are_refused_online_and_accepted_only_with_offline_role(self):
        with tempfile.TemporaryDirectory() as directory:
            root = root_files(Path(directory))
            book = A22Book(root, job_id='a22-feature-boundary')
            for action in ('full_J', 'full_H', 'truth_current', 's_F', 'e_F', 'teacher'):
                with self.assertRaises(BudgetExceeded):
                    with book.action_guard(action):
                        self.fail('Offline label leaked into online builder')
                with book.action_guard(action, role='offline_label'):
                    pass
            with self.assertRaises(BudgetExceeded):
                with book.action_guard('full_J', role='health'):
                    self.fail('Full J became a health feature')
            with book.action_guard('full_state', F_calls=1):
                pass
            self.assertEqual(book.counts['F_calls'], 1)
            self.assertEqual(book.counts.get('data_generation_F_calls', 0), 0)

    def test_corrections_are_disabled_by_default_and_one_failed_attempt_is_not_retried(self):
        with tempfile.TemporaryDirectory() as directory:
            root = root_files(Path(directory))
            blocked = A22Book(root, job_id='a22-correction-disabled', stage='image')
            with self.assertRaises(BudgetExceeded):
                with blocked.action_guard('physical_correction', scene_id=1, method='two-shot'):
                    self.fail('Unauthorized correction ran')
            enabled = A22Book(root, config(correction_events=1), job_id='a22-correction-once', stage='image')
            with self.assertRaises(RuntimeError):
                with enabled.action_guard('physical_correction', scene_id=1, method='two-shot'):
                    raise RuntimeError('failed correction')
            with self.assertRaises(BudgetExceeded):
                with enabled.action_guard('physical_correction', scene_id=1, method='two-shot'):
                    self.fail('Failed correction was retried for free')
            self.assertEqual(enabled.counts['physical_corrections'], 1)

    def test_stage_c_requires_all_three_passes_and_sufficient_existing_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            root = root_files(Path(directory))
            for index, (gates, cache) in enumerate((({'A': 'PASS', 'B': 'PARTIAL', 'C': 'PASS'}, True),
                                                     ({'A': 'PASS', 'B': 'PASS', 'C': 'PASS'}, False))):
                book = A22Book(root, job_id='a22-train-blocked-' + str(index), stage='train', gates=gates, cache_sufficient=cache)
                with self.assertRaises(BudgetExceeded):
                    with book.action_guard('train'):
                        self.fail('Blocked C stage trained')
            permitted = A22Book(root, job_id='a22-train-fixture', stage='train',
                                gates={'A': 'PASS', 'B': 'PASS', 'C': 'PASS'}, cache_sufficient=True)
            with permitted.action_guard('train', optimizer_steps=1):
                pass
            with self.assertRaises(BudgetExceeded):
                with permitted.action_guard('diffusion'):
                    self.fail('Diffusion enabled by unrelated gates')

    def test_external_receipts_are_idempotent_and_invalid_measurements_do_not_write(self):
        with tempfile.TemporaryDirectory() as directory:
            root = root_files(Path(directory))
            self.assertTrue(register_external(root, 'controller', 2, counts={'data_generation_F_calls': 1}))
            self.assertFalse(register_external(root, 'controller', 2, counts={'data_generation_F_calls': 1}))
            before = (root / 'results/a22/external_cpu_receipts.json').read_bytes()
            for value in (float('nan'), -1, float('inf')):
                with self.assertRaises(ValueError):
                    register_external(root, 'invalid', value)
            with self.assertRaises(ValueError):
                register_external(root, 'controller', 3)
            self.assertEqual(before, (root / 'results/a22/external_cpu_receipts.json').read_bytes())
            self.assertEqual(history(root)['a22_cpu'], 2)


class TransportTests(unittest.TestCase):
    def test_deployment_excludes_a21_labels_private_values_and_old_ledgers(self):
        tool = load_transport()
        with tempfile.TemporaryDirectory() as directory:
            root = root_files(Path(directory))
            for name in ('src/a22/tiny.py', 'src/a20/shared.py', 'src/a21/oracle.py',
                         'vendor/backend.py', 'data/a22/online/scene.npz',
                         'data/a22/offline/scene.npz', 'private/ssh_connection.json',
                         'results/a21/rawdata/full_J.npy', 'COST_LEDGER.jsonl'):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b'fixture')
            members = tool.deployment_members(root)
            self.assertIn('src/a22/tiny.py', members)
            self.assertIn('src/a20/shared.py', members)
            self.assertIn('data/a22/online/scene.npz', members)
            self.assertFalse(any('/a21/' in name or '/offline/' in name or 'private/' in name for name in members))
            self.assertNotIn('COST_LEDGER.jsonl', members)

    def test_pull_is_idempotent_for_jobs_external_scopes_and_jsonl_events(self):
        tool = load_transport()
        with tempfile.TemporaryDirectory() as directory:
            root = root_files(Path(directory))
            register_external(root, 'local', 2)
            local = json.loads((root / 'results/a22/external_cpu_receipts.json').read_text())
            remote = dict(scope='remote', process_cpu_seconds=3, gpu_occupation_seconds=0,
                          wall_seconds=0, stage=None, counts={}, receipt=None, measurement='fixture', status='MEASURED')
            archive = root / 'results.zip'
            row = receipt('a22-pulled', cpu=4, counts={'F_calls': 2})
            with zipfile.ZipFile(archive, 'w') as zipped:
                zipped.writestr('results/jobs/a22-pulled/job_receipt.json', json.dumps(row))
                zipped.writestr('results/a22/external_cpu_receipts.json', json.dumps(local + [remote]))
                zipped.writestr('results/a22/COST_LEDGER.jsonl', json.dumps(dict(event='tiny', event_id='one', F_calls=2)))
            tool._merge_jobs(archive, root)
            tool._merge_jobs(archive, root)
            measured = history(root)
            self.assertEqual(measured['a22_cpu'], 9)
            self.assertEqual(measured['counts']['F_calls'], 2)
            rows = [json.loads(line) for line in (root / 'results/a22/COST_LEDGER.jsonl').read_text().splitlines()]
            self.assertEqual(sum(row.get('event_id') == 'one' for row in rows), 1)

    def test_conflicting_pull_cannot_replace_a_summary_before_receipt_validation(self):
        tool = load_transport()
        with tempfile.TemporaryDirectory() as directory:
            root = root_files(Path(directory))
            row = receipt('a22-immutable', cpu=1)
            merge_receipt(root, row)
            summary = root / 'results/a22/GATE_REPORT.md'
            summary.write_text('original')
            archive = root / 'conflict.zip'
            with zipfile.ZipFile(archive, 'w') as zipped:
                zipped.writestr('results/a22/GATE_REPORT.md', 'incoming')
                zipped.writestr('results/jobs/a22-immutable/job_receipt.json', json.dumps(dict(row, process_cpu_seconds=2)))
            with self.assertRaises(ValueError):
                tool._merge_jobs(archive, root)
            self.assertEqual(summary.read_text(), 'original')
            self.assertEqual(history(root)['a22_cpu'], 1)

    def test_pull_rejects_old_jobs_traversal_symlinks_and_private_outputs(self):
        tool = load_transport()
        with tempfile.TemporaryDirectory() as directory:
            root = root_files(Path(directory))
            archive = root / 'invalid.zip'
            for name in ('results/jobs/a21-old/job_receipt.json', '../escape.json',
                         'results/a22/private/connection.json', 'results/a22/../../configs/a22.json'):
                with zipfile.ZipFile(archive, 'w') as zipped:
                    zipped.writestr(name, '{}')
                with self.assertRaises(ValueError):
                    tool._merge_jobs(archive, root)
            with zipfile.ZipFile(archive, 'w') as zipped:
                entry = zipfile.ZipInfo('results/a22/link')
                entry.create_system = 3
                entry.external_attr = (0o120777 << 16)
                zipped.writestr(entry, 'outside')
            with self.assertRaises(ValueError):
                tool._merge_jobs(archive, root)

    def test_failed_transport_does_not_expose_or_store_private_arguments(self):
        tool = load_transport()
        with tempfile.TemporaryDirectory() as directory:
            root = root_files(Path(directory))
            private = root / 'private/connection.json'
            private.parent.mkdir()
            private.write_text(json.dumps(dict(A20_SSH_TARGET='private-host-fixture', A20_SSH_KEY='private-key-fixture')))
            adapter = tool.connection(private, root=root)
            failed = subprocess.CompletedProcess(['redacted'], 255, stdout=b'', stderr=b'private-host-fixture private-key-fixture')
            with patch.object(tool.subprocess, 'run', return_value=failed):
                with self.assertRaises(tool.TransportFailure) as caught:
                    adapter.shell('fixture')
            self.assertIn('255', str(caught.exception))
            self.assertNotIn('private-host-fixture', str(caught.exception))
            self.assertNotIn('private-key-fixture', str(caught.exception))
            self.assertEqual(list(private.parent.iterdir()), [private])

    def test_explicit_private_config_is_required_and_never_exported_to_environment(self):
        tool = load_transport()
        with tempfile.TemporaryDirectory() as directory:
            root = root_files(Path(directory))
            public = root / 'configs/connection.json'
            public.write_text(json.dumps(dict(target='fixture', key='fixture')))
            with self.assertRaises(tool.TransportFailure):
                tool.connection(public, root=root)
            with patch.dict(tool.os.environ, {}, clear=True):
                private = root / 'private/connection.json'
                private.parent.mkdir()
                private.write_text(json.dumps(dict(A20_SSH_TARGET='fixture', A20_SSH_KEY='fixture')))
                tool.connection(private, root=root)
                self.assertNotIn('A20_SSH_TARGET', tool.os.environ)
                self.assertNotIn('A20_SSH_KEY', tool.os.environ)

    def test_launch_contract_uses_shared_lock_explicit_cli_and_parent_wall_origin(self):
        tool = load_transport()
        source = tool._launch_code('screen', 'a22-unit-job', 'cuda', 'direction')
        self.assertIn('D:/AI/A22_THREE_FOLD_OPM', source)
        self.assertIn('D:/AI/A20_OPM_IMAGING/runs/gpu.lock', source)
        self.assertIn('D:/python/python.exe', source)
        self.assertIn('A22_JOB_WALL_ORIGIN', source)
        self.assertIn('stage_gpu_caps_seconds', source)
        self.assertIn('child.kill()', source)
        self.assertNotIn('A20_SSH_TARGET', source)
        self.assertNotIn('Get-Content', source)


if __name__ == '__main__':
    unittest.main()
