"""Paired/protected R1 policy tests on explicit six-source linear operators.

No parent data, truth, teacher, reference file, remote service, or large mesh
is opened.  Full actions are denied by the test adapter, including CHEAP.
"""
from dataclasses import replace
from types import SimpleNamespace
from contextlib import contextmanager
import unittest
from unittest.mock import patch
import numpy as np
from scipy import linalg as la

from a20.backend import BasisView, ForbiddenAccess
from a20.costs import BudgetExceeded, CostBook
from a20.opm import Hierarchy, Projection, ReducedJacobian, UnsafeCore, build_seeds, orth
from a20.material import QPFailure
from a20 import imaging
from a20_r1.seeds import (AcceptedHistory, METHODS, ProbeBank, build_model,
                          build_schur, paired_probe_bank, source_target_block, PolicyModel)


CONFIG = {'retained_rank': 0, 'master_seed': 20261005,
          'orthogonal_rank_rtol': 1e-10,
          'seed_rank_O': 4, 'seed_rank_P': 4, 'seed_rank_M': 4}
METRICS = {}


class GuardBook(CostBook):
    def __init__(self):
        super().__init__(enforce=False)
        self.observed = []

    @contextmanager
    def span(self, label, **counters):
        self.observed.append((label, self.phase))
        if self.phase == 'legal_seed' and label in ('full_forward', 'full_tangent', 'full_adjoint'):
            raise ForbiddenAccess('FULL_ACTION_IN_LEGAL_SEED')
        with super().span(label, **counters) as row:
            yield row


class LinearAdapter:
    """Complex128, n64, d8, P6; independently identifiable source targets."""
    def __init__(self, *, zero=False, parent=9201):
        self.n, self.p, self.P, self.m = 64, 8, 6, 5
        self.chart = SimpleNamespace(d=self.p)
        self.problem = SimpleNamespace(parent_id=parent)
        self.book = GuardBook()
        rng = np.random.default_rng(90201)
        self.GS = np.zeros((self.m, self.n), complex) if zero else (
            rng.normal(size=(self.m, self.n))+1j*rng.normal(size=(self.m, self.n))) / 10
        self.model = SimpleNamespace(_gs_svd=None)
        def gs_modes():
            if self.model._gs_svd is None:
                self.model._gs_svd = {'V': la.svd(self.GS, full_matrices=False)[2].conj().T}
            return self.model._gs_svd
        self.model.gs_modes = gs_modes
        self._operator_L = np.diag(1-np.linspace(.001, .08, self.n)).astype(complex)
        self._version = 1
        self.x = np.full(4, .3+.04j)
        self.state = SimpleNamespace(chi=self.x.copy(), model=self.model)
        self.Btensor = np.zeros((self.P, self.n, self.p), complex)
        if not zero:
            for source in range(self.P):
                self.Btensor[source, source, 0] = 1.
                for probe in range(1, self.p):
                    self.Btensor[source, 6+source*(self.p-1)+probe-1, probe] = 3.+.2j*source
        self.force = np.zeros((self.n, self.P), complex) if zero else (
            rng.normal(size=(self.n, self.P))+1j*rng.normal(size=(self.n, self.P))) / 10
        self.r = rng.normal(size=self.P*2*self.m)
        self.full_queries = []

    def version(self, x):
        if not np.array_equal(x, self.x):
            self.x = np.asarray(x).copy()
            self._version += 1
        return self._version

    def injection_factor(self, x, state):
        if not np.array_equal(x, state.chi) or state.model is not self.model:
            raise ValueError('B state owner/material mismatch')
        return np.ones((self.P, self.n))

    def apply_L(self, x, v):
        self.version(x)
        with self.book.span('L', L_actions=v.shape[1]):
            return self._operator_L@v

    def apply_L_adjoint(self, x, v):
        self.version(x)
        with self.book.span('L_adjoint', L_adjoint_actions=v.shape[1]):
            return self._operator_L.conj().T@v

    def apply_F(self, x, v):
        with self.book.span('F', F_actions=v.shape[1]):
            return v-self._operator_L@v

    def apply_F_adjoint(self, x, v):
        with self.book.span('F_adjoint', F_adjoint_actions=v.shape[1]):
            return v-self._operator_L.conj().T@v

    def apply_S(self, v):
        with self.book.span('S', S_actions=v.shape[1]):
            return self.GS@v

    def apply_S_adjoint(self, v):
        with self.book.span('S_adjoint', S_adjoint_actions=v.shape[1]):
            return self.GS.conj().T@v

    def apply_B(self, x, state, d):
        self.injection_factor(x, state)
        with self.book.span('B', B_probes=1 if d.ndim == 1 else d.shape[1]):
            return np.einsum('snp,p...->sn...', self.Btensor, d)

    def apply_B_adjoint(self, x, state, value):
        self.injection_factor(x, state)
        with self.book.span('B_adjoint', B_adjoint_probes=value.shape[-1]):
            return np.einsum('snp,snk->pk', self.Btensor.conj(), value).real

    def forcing(self, x):
        with self.book.span('illumination_forcing', forcing_rhs=self.P):
            return self.force.copy()

    def whiten(self, value, adjoint=False):
        return value

    def compressed_B(self, x, state, Z):
        return np.einsum('rn,snp->srp', Z.conj().T, self.Btensor)

    def _deny(self, name):
        self.full_queries.append(name)
        raise ForbiddenAccess('FORBIDDEN_FULL_OR_TRUTH:'+name)

    def full_adjoint_action(self, *args):
        return self._deny('full_adjoint')

    def full_tangent_action(self, *args):
        return self._deny('full_tangent')

    def full_state(self, *args):
        return self._deny('full_state')

    def __getattr__(self, name):
        if name in ('truth', 'teacher', 'full_J', 'full_H', 'reference_step', 'labels'):
            return self._deny(name)
        raise AttributeError(name)


class R1SeedsTests(unittest.TestCase):
    def setUp(self):
        self.a = LinearAdapter()
        self.x = self.a.x.copy()
        self.state = self.a.state
        self.r = self.a.r.copy()
        self.ell = np.linspace(-.002, .003, self.a.p)

    def model(self, method, **kwargs):
        return build_model(self.a, self.x, self.state, self.r, self.ell, CONFIG, method, **kwargs)

    def test_exact_legacy_rng_seeds_and_projection(self):
        view = BasisView(self.a, self.x, self.state, self.r)
        schur = build_schur(self.a, self.x, self.state, self.r, CONFIG)
        legacy = build_seeds(view, schur, CONFIG)
        bank = paired_probe_bank(view, CONFIG)
        fixed = self.model('FIXED-DEEP', schur=schur, bank=bank)
        np.testing.assert_array_equal(fixed.seeds.material_probes, legacy.material_probes)
        np.testing.assert_array_equal(fixed.seeds.measurement_probes, legacy.measurement_probes)
        for key in 'OPM':
            np.testing.assert_array_equal(fixed.seeds.blocks[key], legacy.blocks[key])
        Z, _ = Hierarchy(view, schur, legacy, CONFIG).at_degree(3)
        np.testing.assert_array_equal(fixed.projection.Z, Z)
        METRICS['legacy_frozen_probe_and_Z_max_absolute_error'] = 0.
        canonical = ReducedJacobian(self.a, self.x, self.state, Projection(self.a, self.x, Z, CONFIG))
        np.testing.assert_allclose(fixed.jacobian.matrix(), canonical.matrix(), rtol=0, atol=0)
        self.assertEqual(fixed.info['requested_rank_bound'], 48)
        self.assertEqual(len(fixed.info['probe_source_mapping']), 24)

    def test_wide_prefix_and_observation_pairing(self):
        view = BasisView(self.a, self.x, self.state, self.r)
        bank = paired_probe_bank(view, CONFIG)
        fixed = self.model('FIXED-DEEP', bank=bank)
        wide = self.model('WIDE-M', bank=bank)
        np.testing.assert_array_equal(wide.seeds.material_probes[:, :4], fixed.seeds.material_probes)
        np.testing.assert_array_equal(wide.seeds.measurement_probes, fixed.seeds.measurement_probes)
        rng = np.random.default_rng(np.random.SeedSequence(bank.extra_rng_seed))
        extra = rng.normal(size=(self.a.p, 12))
        extra /= np.maximum(la.norm(extra, axis=0), 1e-300)
        np.testing.assert_array_equal(wide.seeds.material_probes[:, 4:], extra)
        self.assertEqual(wide.info['allocation']['degree'], 1)
        self.assertEqual(len(wide.info['probe_source_mapping']), 96)

    def test_legacy_and_typed_own_history_seeds_and_hierarchy_are_exact(self):
        step = np.random.default_rng(321).normal(size=self.a.p)*.003
        history = AcceptedHistory(self.a.problem.parent_id, 'FIXED-DEEP', 3, step)
        view = BasisView(self.a, self.x, self.state, self.r, step)
        schur = build_schur(self.a, self.x, self.state, self.r, CONFIG)
        legacy = build_seeds(view, schur, CONFIG)
        hooked = self.model('FIXED-DEEP', previous=history, schur=schur)
        np.testing.assert_array_equal(hooked.seeds.material_probes, legacy.material_probes)
        for key in 'OPM':
            np.testing.assert_array_equal(hooked.seeds.blocks[key], legacy.blocks[key])
        Z, _ = Hierarchy(view, schur, legacy, CONFIG).at_degree(3)
        np.testing.assert_array_equal(hooked.projection.Z, Z)
        METRICS['legacy_history_probe_and_Z_max_absolute_error'] = 0.

    def test_six_source_loss_counterexample_and_complete_protection(self):
        target = np.eye(self.a.p)[0]
        raw = self.model('ORACLE-M', reference_step=target)
        protected = self.model('PROTECTED-ORACLE', reference_step=target)
        view = BasisView(self.a, self.x, self.state, self.r)
        KB = source_target_block(view, protected.schur, target)
        self.assertEqual(KB.shape, (64, 6))
        self.assertEqual(np.linalg.matrix_rank(KB), 6)
        loss = la.norm(KB-raw.qM@(raw.qM.conj().T@KB))/la.norm(KB)
        self.assertGreater(loss, .3)
        error = la.norm(KB-protected.qM@(protected.qM.conj().T@KB))/la.norm(KB)
        self.assertLess(error, 1e-12)
        METRICS['six_source_raw_M4_relative_loss'] = float(loss)
        METRICS['six_source_protected_M6_relative_loss'] = float(error)
        METRICS['six_source_raw_M4_energy_capture'] = raw.info['target_capture']['capture']
        METRICS['six_source_protected_M6_energy_capture'] = protected.info['target_capture']['capture']
        self.assertEqual(protected.seeds.records['M']['protected_rank'], 6)
        self.assertEqual(protected.qM.shape[1], 6)
        self.assertEqual(protected.info['allocation'], {'O': 3, 'P': 3, 'M': 6, 'degree': 3})
        self.assertFalse(protected.info['no_truth_or_reference_step'])
        self.assertTrue(protected.seeds.records['M']['full_reference_used'])
        self.assertTrue(protected.seeds.records['O']['no_truth_or_reference_step'])
        self.assertFalse(protected.info['truth_used'])

    def test_protected_rank_overallocation_is_invalid_and_paid(self):
        self.a.P = 7
        extra = np.zeros((1, self.a.n, self.a.p), complex)
        extra[0, 6, 0] = 1.
        self.a.Btensor = np.concatenate((self.a.Btensor, extra), axis=0)
        self.a.force = np.column_stack((self.a.force, np.zeros(self.a.n)))
        self.r = np.r_[self.r, np.zeros(2*self.a.m)]
        with self.assertRaisesRegex(ValueError, 'rank exceeds M allocation'):
            self.model('PROTECTED-ORACLE', reference_step=np.eye(self.a.p)[0])
        self.assertEqual(self.a.book.counts['seed_M_input_rhs'], 42)
        self.assertGreater(self.a.book.counts['B_probes'], 0)
        self.assertEqual(self.a.full_queries, [])

    def test_protected_random_uses_identical_all_source_rule(self):
        protected = self.model('PROTECTED-RANDOM')
        view = BasisView(self.a, self.x, self.state, self.r)
        KB = source_target_block(view, protected.schur, protected.seeds.material_probes[:, 0])
        self.assertLess(la.norm(KB-protected.qM@(protected.qM.conj().T@KB)), 1e-12)
        self.assertEqual(protected.seeds.records['M']['protected_rank'], 6)
        self.assertTrue(protected.info['no_truth_or_reference_step'])
        self.assertFalse(protected.info['full_reference_used'])

    def test_cheap_reduced_gradient_denies_full_and_keeps_previous_slot(self):
        fixed = self.model('FIXED-DEEP')
        expected = fixed.jacobian.pullback(self.r)+self.ell
        fixed.jacobian.matrix()  # A preceding FIXED QP has warmed this object.
        history = AcceptedHistory(self.a.problem.parent_id, 'CHEAP-TASK', 2, np.arange(1., 9.))
        with patch.object(fixed.jacobian, 'pullback', side_effect=AssertionError('borrowed warm Jacobian')):
            cheap = self.model('CHEAP-TASK', scaffold=fixed, schur=fixed.schur, previous=history)
        np.testing.assert_allclose(cheap.seeds.material_probes[:, 0], -expected/la.norm(expected), atol=1e-14)
        np.testing.assert_allclose(cheap.seeds.material_probes[:, 1], history.step/la.norm(history.step), atol=0)
        self.assertEqual(cheap.info['previous_probe_slot'], 1)
        self.assertEqual(cheap.info['task_probe_slot'], 0)
        self.assertEqual(cheap.info['previous_owner']['accepted_index'], 2)
        self.assertIsNotNone(cheap.info['previous_capture'])
        self.assertEqual(self.a.full_queries, [])
        paid = cheap.info['actual_cost']['counts']
        self.assertEqual(paid['r1_cheap_gradients'], 1)
        self.assertGreater(paid['B_adjoint_probes'], 0)
        self.assertGreater(paid['reduced_core_rhs'], 0)
        self.assertGreater(cheap.info['standalone_cost']['counts']['F_actions'], paid['F_actions'])
        summed = {}
        for component in cheap.info['cost_components'].values():
            for key, value in component['counts'].items():
                summed[key] = summed.get(key, 0)+value
        self.assertEqual(summed, paid)
        self.assertTrue(all(phase == 'legal_seed' for label, phase in self.a.book.observed
                            if label == 'r1_cheap_reduced_gradient'))
        for timing in ('wall_seconds', 'process_cpu_seconds'):
            actual = cheap.info['actual_cost'][timing]
            scaffold_noncommon = fixed.info['noncommon_cost'][timing]
            common = fixed.schur.r1_info['creation_cost'][timing]
            self.assertGreater(actual, 0.)
            self.assertGreater(scaffold_noncommon, 0.)
            self.assertGreater(common, 0.)
            self.assertAlmostEqual(cheap.info['standalone_cost'][timing],
                                   actual+common+scaffold_noncommon, places=12)
            self.assertAlmostEqual(scaffold_noncommon,
                fixed.info['actual_cost'][timing]
                -fixed.info['cost_components']['schur'][timing]
                -fixed.info['cost_components']['bank'][timing], places=12)
            self.assertGreater(cheap.info['cost_components']['bank'][timing], 0.)
        internal = self.model('CHEAP-TASK')
        self.assertFalse(internal.info['reused']['scaffold'])
        self.assertEqual(internal.info['standalone_cost'], internal.info['actual_cost'])
        self.assertGreater(internal.info['cost_components']['cheap_scaffold']['wall_seconds'], 0.)
        METRICS['cheap_internal_scaffold_time_counted_once'] = True
        METRICS['cheap_reused_scaffold_common_times_counted_once'] = True

    def test_oracle_and_legal_capability_denial(self):
        for method in set(METHODS)-{'ORACLE-M', 'PROTECTED-ORACLE'}:
            with self.assertRaisesRegex(ForbiddenAccess, 'REFERENCE_STEP_FORBIDDEN'):
                self.model(method, reference_step=np.zeros(self.a.p))
        with self.assertRaisesRegex(ValueError, 'explicit reference_step'):
            self.model('ORACLE-M')
        with self.assertRaisesRegex(ValueError, 'Unregistered'):
            self.model('UNREGISTERED')
        self.model('ORACLE-M', reference_step=np.zeros(self.a.p))
        self.assertTrue(any(phase == 'offline_oracle_seed' for _, phase in self.a.book.observed))
        self.assertEqual(self.a.full_queries, [])

    def test_history_copy_validation_and_owner_rejection(self):
        original = np.arange(self.a.p, dtype=float)
        history = AcceptedHistory(self.a.problem.parent_id, 'FIXED-DEEP', 1, original)
        original[:] = -20
        np.testing.assert_array_equal(history.step, np.arange(self.a.p))
        with self.assertRaises(ValueError):
            history.step[0] = 12
        with self.assertRaisesRegex(ValueError, 'accepted_index'):
            AcceptedHistory(self.a.problem.parent_id, 'FIXED-DEEP', 0, original)
        with self.assertRaisesRegex(ValueError, 'finite'):
            AcceptedHistory(self.a.problem.parent_id, 'FIXED-DEEP', 1, np.full(self.a.p, np.nan))
        with self.assertRaisesRegex(ForbiddenAccess, 'OWNED_ACCEPTED_HISTORY'):
            self.model('FIXED-DEEP', previous=original)
        for bad in (replace(history, parent=999), replace(history, method='CHEAP-TASK')):
            with self.assertRaisesRegex(ForbiddenAccess, 'OWNER_MISMATCH'):
                self.model('FIXED-DEEP', previous=bad)
        with self.assertRaisesRegex(ValueError, 'dimension mismatch'):
            self.model('FIXED-DEEP', previous=replace(history, step=np.zeros(3)))
        fixed = self.model('FIXED-DEEP', previous=history)
        self.assertEqual(fixed.info['previous_probe_slot'], 0)
        expected = history.step/la.norm(history.step)
        expected /= max(la.norm(expected), 1e-300)
        np.testing.assert_array_equal(fixed.seeds.material_probes[:, 0], expected)

    def test_cache_owner_material_residual_and_bank_rejection(self):
        view = BasisView(self.a, self.x, self.state, self.r)
        bank = paired_probe_bank(view, CONFIG)
        with self.assertRaisesRegex(ValueError, 'owner/dimension/RNG'):
            self.model('FIXED-DEEP', bank=replace(bank, parent=9211))
        with self.assertRaisesRegex(ValueError, 'M16/O4'):
            replace(bank, material_probes=np.zeros((self.a.p, 4)))
        fixed = self.model('FIXED-DEEP', bank=bank)
        with self.assertRaisesRegex(ValueError, 'state'):
            build_model(self.a, self.x, self.state, self.r+1, self.ell, CONFIG, 'CHEAP-TASK', scaffold=fixed)
        self.a.version(self.x+.01)
        with self.assertRaisesRegex(ValueError, 'invalidated'):
            self.model('FIXED-DEEP', schur=fixed.schur)

    def test_zero_target_history_and_empty_projection_without_padding(self):
        zero = LinearAdapter(zero=True)
        history = AcceptedHistory(zero.problem.parent_id, 'FIXED-DEEP', 1, np.zeros(zero.p))
        model = build_model(zero, zero.x, zero.state, zero.r, np.zeros(zero.p), CONFIG,
                            'FIXED-DEEP', previous=history)
        self.assertEqual(model.projection.Z.shape, (zero.n, 0))
        self.assertEqual(model.info['actual_seed_ranks'], {'O': 0, 'P': 0, 'M': 0})
        self.assertIsNone(model.info['previous_probe_slot'])
        np.testing.assert_array_equal(model.jacobian.action(np.ones(zero.p)), np.zeros_like(zero.r))
        np.testing.assert_array_equal(model.jacobian.pullback(zero.r), np.zeros(zero.p))
        np.testing.assert_array_equal(model.jacobian.matrix(), np.zeros((len(zero.r), zero.p)))
        oracle = self.model('PROTECTED-ORACLE', reference_step=np.zeros(self.a.p))
        self.assertEqual(oracle.seeds.records['M']['protected_rank'], 0)
        self.assertTrue(oracle.info['target_capture']['zero'])
        self.assertIsNone(oracle.info['target_capture']['capture'])

    def test_budget_stop_before_seed_work_cannot_query_full(self):
        self.a.book.enforce = True
        self.a.book.cpu_limit = 0.
        self.a.book.cpu_reserve = 0.
        with self.assertRaises(BudgetExceeded):
            self.model('CHEAP-TASK')
        self.assertEqual(self.a.full_queries, [])


class ImagingHookTests(unittest.TestCase):
    """Control-flow doubles only: no Maxwell or numerical QP is run."""
    def setUp(self):
        self.a = LinearAdapter()
        self.a.chart.kind = 'interface_double'
        self.a.chart.project = lambda x: np.r_[x.real, x.imag]
        self.a.chart.expand = lambda s: s[:4]+1j*s[4:]
        self.a.problem.init = self.a.x.copy()
        self.a.problem.chart = self.a.chart
        self.a.problem.receivers = np.zeros((3, 3))
        self.a.problem.frequency = 2.
        self.a.model.counters = SimpleNamespace(as_dict=lambda: {})
        self.a.material_constraints = lambda x: {'violation': 0., 'feasible': True}
        self.current = None
        def objective(x, prior, state=None):
            if self.current is None or state is not None:
                self.current = x.copy()
            value = 100.+sum(x.real)
            if state is None and la.norm((x-self.current).real) > .015:
                value += 1.  # Forces a rejected alpha=1 then accepted alpha=.5.
            return value, np.ones(60), SimpleNamespace(chi=x.copy(), model=self.a.model)
        self.a.full_objective = objective
        self.config = dict(CONFIG, max_updates=2, prior=1e-5, lm0=.01, lm_decay=.3,
            lm_decay_period=3, feasibility_tolerance=1e-8, common_full_kkt_rtol=1e-6,
            line_trials=24, armijo=1e-4, backtracking=.5,
            small_step_first_iteration=9, small_step=1e-6)
        self.seen = []
        self.callback_phases = []

    class Jacobian:
        def __init__(self, *args):
            pass

        def pullback(self, r):
            return np.ones(8)

        def action(self, d):
            return np.zeros(60)

    def factory(self, adapter, x, state, residual, previous, method, degree, config):
        self.seen.append(previous)
        projection = SimpleNamespace(fallback=None, Z=np.ones((64, 1)))
        return PolicyModel(projection, self.Jacobian(), None, None,
            {'rank': 1, 'projection': 'galerkin', 'method_id': 'FIXED-DEEP',
             'allocation': METHODS['FIXED-DEEP'].copy()})

    def callback(self, *, adapter, x, state, residual, ell, lam, row, full):
        self.callback_phases.append(adapter.book.phase)
        self.assertTrue(row['acceptance_pending'])
        self.assertIsNone(row['accepted'])
        np.testing.assert_array_equal(x, state.chi)
        # Mutating these copied inputs/return must not become online history.
        x[:] = 100
        row['material_step_coefficients'][:] = [90]*8
        return np.full(8, 90.)

    def run_loop(self, step=None, **kwargs):
        step = -np.ones(8)*.01 if step is None else step
        with patch.object(imaging, 'FullJacobian', self.Jacobian), patch.object(imaging, 'kkt',
                return_value={'stationarity_norm': 1.}), patch.object(imaging, 'solve_quadratic',
                return_value=(step, {'stationarity_relative': 0.}, None)):
            return imaging.reconstruct(self.a.problem, self.config, self.a.book, 'cpu',
                method='FIXED-DEEP', degree=3, adapter=self.a, **kwargs)

    def test_hook_owned_history_callback_isolation_and_default_factory(self):
        x, run, rows, _ = self.run_loop(basis_factory=self.factory,
            offline_iteration_callback=self.callback, no_full_fallback=True)
        self.assertEqual(len(self.seen), 2)
        self.assertIsNone(self.seen[0])
        self.assertIsInstance(self.seen[1], AcceptedHistory)
        self.assertEqual(self.seen[1].accepted_index, 1)
        self.assertEqual(self.seen[1].method, 'FIXED-DEEP')
        np.testing.assert_array_equal(self.seen[1].step, -np.ones(8)*.005)
        self.assertTrue(all(z == 'offline_iteration_audit' for z in self.callback_phases))
        self.assertTrue(all(row['accepted'] for row in rows))
        self.assertTrue(all(row['step_size'] == .5 for row in rows))
        self.assertEqual(run['seed_budget_M'], 4)
        self.assertEqual(run['accepted_updates'], 2)
        self.assertGreaterEqual(run['wall_total'], run['wall_deployment'])
        self.assertEqual(run['offline_audit_cost']['counts']['offline_iteration_audits'], 2)
        self.assertEqual(run['deployment_cost']['counts']['offline_iteration_audits'], 0)
        self.assertTrue(np.all(x.real < 1))
        # The untouched default path still calls the legacy basis function
        # and passes its original ndarray previous to the next outer step.
        seen = []
        def legacy_basis(*args):
            seen.append(args[4])
            return SimpleNamespace(fallback=None), {'rank': 1, 'projection': 'galerkin'}
        with patch.object(imaging, 'basis_model', legacy_basis), patch.object(imaging, 'ReducedJacobian', self.Jacobian):
            self.run_loop()
        self.assertIsNone(seen[0])
        self.assertIsInstance(seen[1], np.ndarray)

    def test_offline_failure_is_missing_and_budget_failure_propagates(self):
        def failure(**kwargs):
            raise RuntimeError('missing offline reference')
        _, run, rows, _ = self.run_loop(basis_factory=self.factory,
            offline_iteration_callback=failure, no_full_fallback=True)
        self.assertEqual(run['accepted_updates'], 2)
        self.assertTrue(all(row['offline_diagnostic']['status'] == 'DIAGNOSTIC_MISSING' for row in rows))
        def budget(**kwargs):
            raise BudgetExceeded('offline hard cap')
        with self.assertRaisesRegex(BudgetExceeded, 'hard cap'):
            self.run_loop(basis_factory=self.factory, offline_iteration_callback=budget)

    def test_non_descent_hook_emits_rejected_trace_without_history(self):
        emitted = []
        _, run, rows, _ = self.run_loop(step=np.ones(8)*.01, basis_factory=self.factory,
            offline_iteration_callback=self.callback, iteration_sink=emitted.append)
        self.assertEqual(run['status'], 'NON_DESCENT')
        self.assertEqual(run['accepted_updates'], 0)
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(emitted), 1)
        self.assertFalse(rows[0]['accepted'])
        self.assertEqual(rows[0]['step_size'], 0.)
        self.assertEqual(rows[0]['trials'], [])
        self.assertEqual(rows[0]['proposal_status'], 'NON_DESCENT')
        self.assertEqual(self.seen, [None])

    def test_no_full_fallback_for_unsafe_core_and_failed_reduced_qp(self):
        with patch.object(imaging, 'basis_model', side_effect=UnsafeCore('test unsafe')):
            _, run, rows, _ = self.run_loop(no_full_fallback=True)
        self.assertEqual(run['status'], 'UNSAFE_CORE')
        self.assertEqual(run['fallback_count'], 0)
        self.assertEqual(rows, [])
        with patch.object(imaging, 'FullJacobian', self.Jacobian), patch.object(imaging, 'kkt',
                return_value={'stationarity_norm': 1.}), patch.object(imaging, 'solve_quadratic',
                side_effect=QPFailure('test QP')) as solve:
            _, run, rows, _ = imaging.reconstruct(self.a.problem, self.config, self.a.book, 'cpu',
                method='FIXED-DEEP', adapter=self.a, basis_factory=self.factory, no_full_fallback=True)
        self.assertEqual(run['status'], 'QP_FAILED')
        self.assertEqual(solve.call_count, 1)
        self.assertEqual(run['fallback_count'], 0)
        self.assertEqual(rows, [])


if __name__ == '__main__':
    unittest.main()
