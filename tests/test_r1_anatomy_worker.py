"""Tiny control-flow fixtures: identity data maps, never a Maxwell solve."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np
from scipy import linalg as la

from a20.backend import MaterialChart
from a20.costs import BudgetExceeded, CostBook
from a20.material import QPFailure
import a20_r1.anatomy as anatomy
import a20_r1.seeds as seeds


ROOT = Path(__file__).resolve().parents[1]
RESIDUAL = np.array([-.4, -.2])
INIT = np.array([.4+.2j])
REDUCED_J = .97*np.eye(2)
CHART = MaterialChart(1., 1, np.ones((1, 1)), 'gaussian')


class FakeAdapter:
    def __init__(self, problem, *, device, book):
        self.problem, self.chart, self.book = problem, CHART, book
        self.p, self.n, self.P, self.m = 2, 64, 1, 1
        self.model = object()
        with book.span('fixture_geometry', fixture_geometry=1):
            pass

    def full_state(self, x, *, reuse):
        with self.book.span('fixture_full_state', full_forward_calls=1):
            return SimpleNamespace(chi=x.copy(), model=self.model,
                                   iteration=int(round((x[0].real-.4)/.001)))

    def residual(self, state):
        with self.book.span('fixture_residual', fixture_residuals=1):
            return RESIDUAL.copy()

    def full_tangent_action(self, x, state, value):
        with self.book.span('fixture_full_J', full_tangent_RHS=value.shape[1]):
            return value.copy()


class FakeJacobian:
    def __init__(self, adapter, method):
        self.adapter, self.method, self.warm = adapter, method, False

    def matrix(self):
        if not self.warm:
            with self.adapter.book.span('fixture_reduced_matrix', compressed_material_columns=2):
                self.warm = True
        return REDUCED_J.copy()

    def action(self, value):
        return REDUCED_J@value


class Fixture:
    def __init__(self, root, *, guard=False, mismatch=False, zero_ref=False,
                 budget=False, qp_failure=False):
        self.root = Path(root)
        self.guard, self.budget, self.qp_failure = guard, budget, qp_failure
        self.calls, self.qp_calls = [], 0
        self.config = json.loads((ROOT/'configs/frozen.json').read_text())
        self.config.update(json.loads((ROOT/'configs/a20_r1.json').read_text()))
        (self.root/'configs').mkdir()
        replay = self.root/'results/replay'
        (replay/'steps').mkdir(parents=True)
        (replay/'failed_steps').mkdir()
        parents, canonical = [], []
        for pid in anatomy.PARENTS:
            parent = {'parent_id': pid, 'parameterization': 'gaussian', 'n_current': 64,
                      'p_material': 2, 'sources': 1, 'receivers': 1, 'frequencies': [2.],
                      'runtime_problem': f'data/{pid}/problem.npz',
                      'offline_labels': f'data/{pid}/labels.npz', 'states': []}
            directory = self.root/'data'/str(pid)
            directory.mkdir(parents=True)
            np.savez(directory/'problem.npz', parent_id=pid)
            np.savez(directory/'labels.npz', truth=np.array([.8+.5j]))
            for iteration in anatomy.ITERATIONS:
                x = INIT+iteration*.001
                ell = self.config['prior']*CHART.project(x-INIT)
                reference_step = -(RESIDUAL+ell)/2
                fixed_step = -la.solve(REDUCED_J.T@REDUCED_J+np.eye(2),
                                      REDUCED_J.T@RESIDUAL+ell, assume_a='pos')
                if mismatch and pid == 2001 and iteration == 17:
                    fixed_step = fixed_step+np.array([.02, 0.])
                state_path = f'data/{pid}/state_{iteration:02}.npz'
                np.savez(self.root/state_path, chi=x, lambda_total=1., ell=ell, iteration=iteration)
                parent['states'].append({'iteration': iteration, 'runtime_path': state_path})
                common = {'run_id': 'fixture-canonical', 'backend_commit': 'fixture-declared',
                          'parent_object_id': pid, 'iteration': iteration,
                          'parameterization': 'gaussian', 'n_current': 64, 'p_material': 2,
                          'n_source': 1, 'n_receiver': 1, 'frequencies': [2.],
                          'precision': 'complex128/float64', 'status': 'OK'}
                ref_name, fixed_name = f'{pid}_{iteration}_reference.npz', f'{pid}_{iteration}_fixed.npz'
                saved_ref = np.zeros(2) if zero_ref and pid == 2001 and iteration == 17 else reference_step
                np.savez(replay/'steps'/ref_name, step=saved_ref)
                np.savez(replay/'steps'/fixed_name, step=fixed_step)
                reference = anatomy._Reference(reference_step, reference_step.copy(),
                    float(.5*(RESIDUAL+reference_step)@(RESIDUAL+reference_step)+ell@reference_step+.5*reference_step@reference_step),
                    float(2*reference_step@reference_step), RESIDUAL+ell,
                    {'reference_status': 'VERIFIED_NEW_CONSTRAINED_REFERENCE'})
                dummy_jac = SimpleNamespace(action=lambda v: v, pullback=lambda v: v)
                dummy_adapter = SimpleNamespace(chart=CHART)
                metrics = anatomy._evaluate_full_step(dummy_adapter, x, RESIDUAL, dummy_jac, 1., ell,
                                                      fixed_step, reference, self.config)
                metrics.update(anatomy._evaluate_truth_step(directory/'labels.npz', CHART, x, fixed_step, self.config))
                canonical.append(dict(common, record_kind='shared_reference', method='full_GN_reference',
                    reference_status='VERIFIED_NEW_CONSTRAINED_REFERENCE',
                    reference_step_path='D:\\fixture\\results\\replay\\steps\\'+ref_name,
                    reference_QP={'kkt_relative': 0.}))
                canonical.append(dict(common, **metrics, record_kind='method', method='mixed', degree=3,
                    seed_budgets={'O': 4, 'P': 4, 'M': 4}, seed_rng=[20261005, pid], rank=56,
                    step_path='D:\\fixture\\results\\replay\\steps\\'+fixed_name))
            parents.append(parent)
        (self.root/'configs/parents.json').write_text(json.dumps({'parents': parents}))
        (replay/'replay.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in canonical))
        self.book = CostBook(device='cpu', enforce=False, metadata={'source_commit': 'fixture-worker'})

    def load(self, path):
        with np.load(path, allow_pickle=False) as data:
            pid = int(data['parent_id'])
        return SimpleNamespace(parent_id=pid, chart=CHART, init=INIT.copy())

    def schur(self, adapter, x, state, residual, config):
        before = adapter.book.snapshot()
        with adapter.book.span('fixture_schur', F_actions=8, F_adjoint_actions=8):
            U = np.eye(64, dtype=complex)[:, :8]
        return SimpleNamespace(U=U, r1_info={'creation_cost': adapter.book.delta(before)})

    def bank(self, view, config):
        with view.book.span('fixture_bank', r1_probe_banks=1):
            return object()

    def target(self, view, schur, value):
        self.assert_qp_attempted_before_target()
        with view.book.span('fixture_offline_target', B_rhs=1, L_actions=1):
            return np.eye(64, dtype=complex)[:, 8:9]

    def assert_qp_attempted_before_target(self):
        if self.qp_calls == 0:
            raise AssertionError('Offline target was acquired before any candidate QP')

    def build(self, adapter, x, state, residual, ell, config, method, **kwargs):
        reference = kwargs['reference_step']
        assert (reference is not None) == (method in anatomy.ORACLES)
        assert kwargs['previous'] is None
        assert (kwargs['scaffold'] is not None) == (method == 'CHEAP-TASK')
        self.calls.append((adapter.problem.parent_id, state.iteration, method, reference is not None))
        before = adapter.book.snapshot()
        with adapter.book.span('fixture_build', F_actions=1, L_actions=2):
            if self.budget and method == 'FIXED-DEEP':
                raise BudgetExceeded('FIXTURE_STOP_AFTER_CHARGED_ACTION')
            allocation = seeds.METHODS[method].copy()
            target_index = 9 if self.guard and method == 'ORACLE-M' and state.iteration == 17 and adapter.problem.parent_id == 2005 else 8
            columns = [target_index]+[k for k in range(10, 10+allocation['M']-1)]
            blocks = {'M': np.eye(64, dtype=complex)[:, columns],
                      'O': np.eye(64, dtype=complex)[:, :allocation['O']],
                      'P': np.eye(64, dtype=complex)[:, :allocation['P']]}
            projection = SimpleNamespace(Z=np.eye(64, dtype=complex)[:, :56], kind='galerkin',
                                         fallback=None, stability={'safe': True})
        actual = adapter.book.delta(before)
        return SimpleNamespace(projection=projection, jacobian=FakeJacobian(adapter, method),
            seeds=SimpleNamespace(blocks=blocks, material_probes=np.tile(np.eye(2), (1, 8))),
            schur=kwargs['schur'], material_span=np.eye(2),
            info={'allocation': allocation, 'actual_seed_ranks': {k: v.shape[1] for k, v in blocks.items()},
                  'actual_cost': actual, 'noncommon_cost': actual, 'standalone_cost': actual})

    def solve(self, chart, x, residual, jacobian, lam, ell, config, book):
        self.qp_calls += 1
        if self.qp_failure and jacobian.method == 'ORACLE-M':
            with book.span('fixture_failed_QP', F_actions=3):
                error = QPFailure('FIXTURE_QP_FAILURE')
                error.step = np.array([.1, .05])
                error.result = {'kkt_relative': .5, 'feasibility_violation': 0.}
                raise error
        return self.original_solve(chart, x, residual, jacobian, lam, ell, config, book)

    def run(self):
        self.original_solve = anatomy.solve_quadratic
        with patch.object(anatomy, 'Adapter', FakeAdapter), patch.object(anatomy, 'load_problem', self.load), \
             patch.object(seeds, 'build_model', self.build), patch.object(seeds, 'build_schur', self.schur), \
             patch.object(seeds, 'paired_probe_bank', self.bank), patch.object(seeds, 'source_target_block', self.target), \
             patch.object(anatomy, 'solve_quadratic', self.solve), contextlib.redirect_stdout(io.StringIO()):
            return anatomy.run_anatomy(self.root, self.config, self.book, 'cpu', 'r1-fixture')

    def rows(self):
        return [json.loads(line) for line in (self.root/'results/a20_r1/anatomy/rows.jsonl').read_text().splitlines()]


class AnatomyWorkerTests(unittest.TestCase):
    canonical_evidence = []

    def test_all_ten_real_canonical_keys_provenance_and_registered_paths_readonly(self):
        config = json.loads((ROOT/'configs/frozen.json').read_text())
        config.update(json.loads((ROOT/'configs/a20_r1.json').read_text()))
        parents = {p['parent_id']: p for p in json.loads((ROOT/'configs/parents.json').read_text())['parents']}
        path = ROOT/'results/replay/replay.jsonl'
        index = anatomy._canonical_index(path)
        for pid in anatomy.PARENTS:
            for iteration in anatomy.ITERATIONS:
                ref_number, ref = anatomy._unique(index, pid, iteration, 'reference')
                fixed_number, fixed = anatomy._unique(index, pid, iteration, 'baseline')
                for row in (ref, fixed):
                    anatomy._canonical_provenance(row, parents[pid], iteration, config)
                    self.assertEqual(row['status'], 'OK')
                self.assertEqual(fixed['seed_budgets'], {'O': 4, 'P': 4, 'M': 4})
                self.assertEqual(fixed['seed_rng'], [config['master_seed'], pid])
                ref_path = anatomy._resolve_step(path, ref['reference_step_path'])
                fixed_path = anatomy._resolve_step(path, fixed['step_path'])
                self.canonical_evidence.append({'parent': pid, 'iteration': iteration,
                    'reference_line': ref_number, 'fixed_line': fixed_number,
                    'reference_status': ref['reference_status'], 'fixed_rank': fixed['rank'],
                    'reference_basename': ref_path.name, 'fixed_basename': fixed_path.name,
                    'backend_declared_commit': ref['backend_commit']})

    def test_energy_capture_and_zero_floor_no_substitution(self):
        span = np.array([[1.], [0.]])
        value = anatomy._capture(np.array([1., 2.]), span, 1e-12, 1e-10)
        self.assertAlmostEqual(value['capture'], .2)
        self.assertIsNone(anatomy._capture(np.zeros(2), span, 1e-12, 1e-10)['capture'])
        ref = anatomy._Reference(np.array([1., 0.]), np.array([1., 0.]), 0., 2., np.ones(2), {})
        values = anatomy._pair_metrics(np.array([0., 1.]), ref, SimpleNamespace(action=lambda x: x), 1., np.ones(2), 1e-12)
        self.assertAlmostEqual(values['H_angle_degrees'], 90.)

    def test_ambiguous_basename_and_duplicate_index_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'replay.jsonl'
            for folder in ('steps', 'failed_steps'):
                (Path(tmp)/folder).mkdir()
                (Path(tmp)/folder/'same.npz').touch()
            with self.assertRaises(anatomy.AnatomyInputError):
                anatomy._resolve_step(path, 'D:\\old\\steps\\same.npz')
        with self.assertRaises(anatomy.AnatomyInputError):
            anatomy._unique({(2001, 17, 'reference'): [(1, {}), (2, {})]}, 2001, 17, 'reference')

    def test_canonical_40_and_duplicate_attempt_denial(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Fixture(tmp)
            result = f.run()
            self.assertEqual(result['status'], 'COMPLETE', result)
            self.assertEqual(result['model_rows_written'], 40)
            self.assertEqual(f.qp_calls, 40)
            rows = [r for r in f.rows() if r['record_kind'] == 'method' and r['method'] != 'HISTORY']
            self.assertTrue(all(r['reference_valid'] and r['QP_valid'] for r in rows))
            self.assertTrue(all(Path(r['step_path']).is_file() for r in rows))
            cheap = next(r for r in rows if r['method'] == 'CHEAP-TASK')
            fixed = next(r for r in rows if r['method'] == 'FIXED-DEEP')
            self.assertGreater(cheap['proposal_action_counts']['F_actions'], fixed['proposal_action_counts']['F_actions'])
            self.assertEqual(f.book.counts['full_forward_calls'], 10)
            before = dict(f.book.counts)
            with self.assertRaises(anatomy.AnatomyInputError):
                f.run()
            self.assertEqual(dict(f.book.counts), before)

    def test_conditional_60_revisit_paid_and_oracle_capability_isolated(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Fixture(tmp, guard=True)
            result = f.run()
            self.assertEqual(result['status'], 'COMPLETE', result)
            self.assertEqual(result['models_built'], 60)
            self.assertEqual(result['protected_state_pairs_written'], 10)
            self.assertEqual(f.qp_calls, 60)
            self.assertEqual(f.book.counts['full_forward_calls'], 11)
            self.assertEqual(f.book.counts['fixture_geometry'], 11)
            protected = [r for r in f.rows() if r['method'] == 'PROTECTED-ORACLE']
            self.assertEqual(len(protected), 10)
            self.assertTrue(all(r['oracle_capture_certified'] for r in protected))
            self.assertTrue(all(r['allocation'] == {'O': 3, 'P': 3, 'M': 6, 'degree': 3} for r in protected))
            self.assertTrue(all((m in anatomy.ORACLES) == reference for _, _, m, reference in f.calls))

    def test_baseline_conflict_stops_campaign_without_relaxing_metrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Fixture(tmp, mismatch=True)
            result = f.run()
            self.assertEqual(result['status'], 'FAILED')
            self.assertEqual(result['models_built'], 1)
            self.assertEqual(result['model_rows_written'], 40)
            self.assertEqual(f.qp_calls, 1)
            self.assertEqual(result['model_status_counts'], {'FAILED': 1, 'NOT_RUN': 39})

    def test_zero_invalid_reference_never_regenerated(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Fixture(tmp, zero_ref=True)
            result = f.run()
            self.assertEqual(result['status'], 'FAILED')
            self.assertEqual(f.qp_calls, 36)
            invalid = [r for r in f.rows() if r['record_kind'] == 'method' and r['status'] == 'INVALID_REFERENCE']
            self.assertEqual(len(invalid), 4)
            self.assertTrue(all(r['relative_H_step_error'] is None for r in invalid))
            self.assertFalse(result['teacher_regenerated'])

    def test_failed_QP_retains_step_actions_and_capture(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Fixture(tmp, qp_failure=True)
            result = f.run()
            self.assertEqual(result['status'], 'FAILED')
            rows = [r for r in f.rows() if r['method'] == 'ORACLE-M']
            self.assertTrue(all(r['status'] == 'QP_FAILED' and not r['QP_valid'] for r in rows))
            self.assertTrue(all(r['oracle_qM_source_capture'] is not None for r in rows))
            self.assertTrue(all(r['costs']['charged_incremental_stages']['QP']['counts']['F_actions'] == 3 for r in rows))
            self.assertTrue(all(Path(r['step_path']).is_file() for r in rows))

    def test_budget_failure_flushes_partial_and_rethrows(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Fixture(tmp, budget=True)
            with self.assertRaises(BudgetExceeded):
                f.run()
            result = json.loads((Path(tmp)/'results/a20_r1/anatomy/ANATOMY_SUMMARY.json').read_text())
            self.assertEqual(result['status'], 'STOPPED')
            stopped = next(r for r in f.rows() if r['method'] == 'FIXED-DEEP')
            self.assertEqual(stopped['status'], 'STOPPED')
            self.assertEqual(stopped['counts']['F_actions'], 1)
            self.assertEqual(stopped['costs']['charged_incremental_stages']['build']['counts']['L_actions'], 2)


if __name__ == '__main__':
    unittest.main()
