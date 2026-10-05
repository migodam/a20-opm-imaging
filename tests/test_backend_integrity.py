"""G0 integrity on a real, tiny 3-D vector-Maxwell DenseDDA.

These are interface/algebra checks, not six-object imaging evidence. No saved
parent payload, truth, teacher, hash, external service, or GPU is used.
Run through tests/run_integrity.py for inclusive CPU receipts and failure logs.
"""
from __future__ import annotations

from dataclasses import replace
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

import numpy as np
from scipy import linalg as la

from a20.backend import (Adapter, BasisView, ForbiddenAccess, MaterialChart,
                         Problem, kernel, load_problem, pack, unpack)
from a20.costs import BudgetExceeded, CostBook
from a20.material import QPFailure, constraint_map, full_quadratic_audit, kkt, solve_quadratic
from a20.opm import (BlockStream, FullJacobian, Hierarchy, Projection,
                     ReducedJacobian, SchurFeedback, UnsafeCore, build_seeds,
                     core_stability, orth)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = Path(os.environ.get('A20_TEST_OUTPUT', ROOT / 'results/tests/manual'))
CONFIG = json.loads((ROOT / 'configs/frozen.json').read_text())
SEED = 2026100501


def cx(rng, *shape):
    return rng.normal(size=shape) + 1j * rng.normal(size=shape)


def fixture(*, frequency=.9, voxel=False, whitening=None, book=None):
    """2^3 cells, three transverse complex illuminations, four receivers."""
    spacing = .3
    points = np.stack(np.meshgrid(*[np.array([-.5, .5]) * spacing] * 3,
                                 indexing='ij'), axis=-1).reshape(-1, 3)
    volume = spacing ** 3
    dirs = np.eye(3)
    pols = np.array([[0, 1, .2j], [.3j, 0, 1], [1, .1j, 0]], complex)
    receivers = np.array([[1.6, .2, .1], [-1.2, 1.3, .5],
                          [.2, -1.5, 1.2], [.4, .8, -1.7]])
    obs_basis = []
    for position in receivers:
        normal = position / la.norm(position)
        tangent = np.cross(normal, np.array([0., 0., 1.]))
        tangent /= la.norm(tangent)
        obs_basis.append([tangent, np.cross(normal, tangent)])
    Q = None
    if not voxel:
        Q = la.qr(np.column_stack((np.ones(8), points[:, 0], points[:, 1])),
                  mode='economic')[0] / np.sqrt(volume)
    chart = MaterialChart(volume, 8, Q, 'tiny_voxel' if voxel else 'tiny_chart')
    x = .35 + .05 * points[:, 0] + .02 * points[:, 1]
    x = x + 1j * (.04 + .003 * points[:, 1])
    problem = Problem(9020, points, volume, np.zeros((3, 8), complex), .2,
                      x.copy(), chart, dirs, pols, receivers,
                      np.asarray(obs_basis), frequency)
    adapter = Adapter(problem, device='cpu', book=book, whitening=whitening)
    return adapter, x


class IntegrityTests(unittest.TestCase):
    def setUp(self):
        self.rng = np.random.default_rng(SEED)
        self.metrics = {'scope': '2^3 real vector-Maxwell algebra only',
                        'precision': 'complex128/float64', 'seed': SEED}
        self.config = dict(CONFIG, seed_rank_O=1, seed_rank_P=1, seed_rank_M=1,
                           retained_rank=2)
        self.book = CostBook(OUTPUT / 'actions' / (self._testMethodName + '.jsonl'),
                             cpu_limit=100., cpu_reserve=0., enforce=True,
                             metadata={'test': self.id(), 'grid': '2^3'})
        self.a, self.x = fixture(book=self.book)
        self.state = self.a.full_state(self.x)

    def close(self, name, a, b, tolerance=1e-9):
        a, b = np.asarray(a), np.asarray(b)
        self.assertEqual(a.shape, b.shape, name)
        error = float(la.norm((a-b).ravel()) /
                      max(la.norm(a.ravel()), la.norm(b.ravel()), 1e-30))
        self.metrics[name] = error
        self.assertLess(error, tolerance, (name, error))

    def basis(self, rank=5):
        return orth(cx(self.rng, self.a.n, rank))[0]

    def direction(self):
        d = self.rng.normal(size=self.a.p)
        return d / la.norm(d)

    def view(self, state=None):
        state = self.state if state is None else state
        return BasisView(self.a, self.x, state, self.a.residual(state))

    def data_fd(self, make_state, d, h=1e-6):
        dc = self.a.chart.expand(d)
        plus = make_state(self.x+h*dc).field
        minus = make_state(self.x-h*dc).field
        return self.a.whiten(pack((plus-minus)/(2*h)))

    def test_complex_current_adjoints_and_metric(self):
        v, w = cx(self.rng, self.a.n, 3), cx(self.rng, self.a.n, 3)
        for name, action, pullback in (
            ('L', self.a.apply_L, self.a.apply_L_adjoint),
            ('F', self.a.apply_F, self.a.apply_F_adjoint)):
            self.close(name+'_adjoint', np.vdot(w, action(self.x, v)),
                       np.vdot(pullback(self.x, w), v))
        y = cx(self.rng, self.a.m, 3)
        self.close('S_adjoint', np.vdot(y, self.a.apply_S(v)),
                   np.vdot(self.a.apply_S_adjoint(y), v))
        self.close('L_plus_F_identity', self.a.apply_L(self.x, v)+self.a.apply_F(self.x, v), v)
        self.close('physical_current_metric', np.sum(abs(np.sqrt(self.a.problem.volume)*v)**2)/self.a.problem.volume,
                   np.sum(abs(v)**2))

    def test_real_material_B_adjoint_batched_and_compressed(self):
        d = self.rng.normal(size=(self.a.p, 3))
        v = cx(self.rng, self.a.P, self.a.n, 3)
        b = self.a.apply_B(self.x, self.state, d)
        bt = self.a.apply_B_adjoint(self.x, self.state, v)
        self.assertFalse(np.iscomplexobj(bt))
        self.close('B_real_adjoint', np.vdot(v, b).real, np.sum(d*bt))
        self.close('B_vector_batched_equivalence', b[:, :, 0], self.a.apply_B(self.x, self.state, d[:, 0]))
        Z = self.basis()
        compressed = self.a.compressed_B(self.x, self.state, Z)
        expected = np.einsum('rn,pnk->prk', Z.conj().T,
                             self.a.apply_B(self.x, self.state, np.eye(self.a.p)))
        self.close('compressed_B', compressed, expected)
        self.assertGreater(la.norm(b[0]-b[1]), 1e-4)
        with self.assertRaisesRegex(ValueError, 'REAL'):
            self.a.apply_B(self.x, self.state, d.astype(complex))
        with self.assertRaisesRegex(ValueError, 'mismatch'):
            self.a.apply_B(self.x+.001, self.state, d)

    def test_original_jvp_vjp_equal_adapter_and_factored_actions(self):
        d = self.rng.normal(size=(self.a.p, 3))
        out = self.a.full_tangent_action(self.x, self.state, d)
        self.close('native_adapter_jvp', out, self.a.whiten(pack(self.state.jvp(self.a.chart.expand(d)))))
        b = self.a.apply_B(self.x, self.state, d)
        current = la.solve(self.state.L, b.transpose(1, 0, 2).reshape(self.a.n, -1))
        current = current.reshape(self.a.n, self.a.P, 3).transpose(1, 0, 2)
        field = np.einsum('mn,pnk->pmk', self.a.model.GS, current)
        self.close('L_inverse_B_S_factorization', out, self.a.whiten(pack(field)))
        w = self.rng.normal(size=self.a.P*2*self.a.m)
        expected = self.a.chart.adjoint(self.state.vjp(unpack(self.a.whiten(w, adjoint=True), self.a.P, self.a.m)))
        adjoint = self.a.full_adjoint_action(self.x, self.state, w)
        self.close('native_adapter_vjp', adjoint, expected)
        self.close('full_realified_J_adjoint', w@out[:, 0], d[:, 0]@adjoint)
        full = FullJacobian(self.a, self.x, self.state)
        matrix = full.small_matrix()
        self.close('full_matrix_action', matrix@d, out)
        self.close('full_matrix_pullback', matrix.T@w, adjoint)

    def test_full_tangent_and_full_objective_finite_difference(self):
        d = self.direction()
        tangent = self.a.full_tangent_action(self.x, self.state, d)
        self.close('full_tangent_fd', tangent, self.data_fd(self.a.full_state, d), 1e-7)
        prior = .07
        objective, residual, _ = self.a.full_objective(self.x, prior, state=self.state)
        dc, h = self.a.chart.expand(d), 1e-6
        fp = self.a.full_objective(self.x+h*dc, prior)[0]
        fm = self.a.full_objective(self.x-h*dc, prior)[0]
        grad = self.a.full_adjoint_action(self.x, self.state, residual)
        self.close('full_objective_fd', (fp-fm)/(2*h), d@grad, 1e-7)
        self.assertTrue(np.isfinite(objective))
        offset = self.x+.002*self.a.chart.expand(self.direction())
        _, rr, ss = self.a.full_objective(offset, prior)
        fp = self.a.full_objective(offset+h*dc, prior)[0]
        fm = self.a.full_objective(offset-h*dc, prior)[0]
        gradient = (self.a.full_adjoint_action(offset, ss, rr)+
                    prior*self.a.chart.project(offset-self.a.problem.init))
        self.close('full_objective_nonzero_prior_fd', (fp-fm)/(2*h), d@gradient, 1e-7)

    def test_packing_whitening_multiple_sources_and_probe_columns(self):
        values = np.arange(24).reshape(3, 8) + 1j*(100+np.arange(24).reshape(3, 8))
        expected = np.concatenate([np.r_[row.real, row.imag] for row in values])
        self.close('packing_explicit_illumination_major', pack(values), expected)
        self.close('packing_inverse', unpack(pack(values), 3, 8), values)
        probes = np.stack((values, 2*values, 3j*values), axis=-1)
        self.close('packing_probe_columns', pack(probes), np.column_stack([pack(probes[..., k]) for k in range(3)]))
        self.close('packing_batched_inverse', unpack(pack(probes), 3, 8), probes)
        with self.assertRaisesRegex(ValueError, 'REAL'):
            unpack(pack(values).astype(complex), 3, 8)
        dim = len(expected)
        W = np.diag(np.linspace(.6, 1.7, dim)) + .05*np.diag(np.ones(dim-1), -1)
        a, x = fixture(whitening=W, book=self.book)
        state = a.full_state(x)
        d, w = self.direction(), self.rng.normal(size=dim)
        j = a.full_tangent_action(x, state, d)
        self.close('non_diagonal_whitening', j, W@pack(state.jvp(a.chart.expand(d))))
        self.close('non_diagonal_whitened_adjoint', w@j, d@a.full_adjoint_action(x, state, w))
        self.close('whitening_pair', w@a.whiten(expected), a.whiten(w, adjoint=True)@expected)

    def test_multi_frequency_stack_uses_distinct_physics_shared_material(self):
        dim = self.a.P*2*self.a.m
        second, x = fixture(frequency=1.25, whitening=np.diag(np.linspace(.7, 1.4, dim)), book=self.book)
        state2 = second.full_state(x)
        d = self.direction()
        actions = [a.full_tangent_action(x, state, d) for a, state in ((self.a, self.state), (second, state2))]
        stacked = np.concatenate(actions)
        w = self.rng.normal(size=2*dim)
        pullback = (self.a.full_adjoint_action(x, self.state, w[:dim])+
                    second.full_adjoint_action(x, state2, w[dim:]))
        self.close('frequency_stack_adjoint', w@stacked, d@pullback)
        explicit = np.vstack((FullJacobian(self.a, x, self.state).small_matrix(),
                              FullJacobian(second, x, state2).small_matrix()))
        self.close('frequency_stack_material_map', explicit@d, stacked)
        self.assertGreater(la.norm(self.a.model.Goff-second.model.Goff), 1e-3)
        self.assertGreater(la.norm(self.state.field-state2.field), 1e-4)
        with self.assertRaisesRegex(ValueError, 'distinct'):
            self.a.full_state(x, frequency=1.25)
        for p in range(self.a.P):
            self.close('source_selection_'+str(p), self.a.full_state(x, source=p, reuse=True), self.state.current[p])
        self.metrics['stack_scope'] = 'explicit concatenate and sum, no production multifrequency driver claimed'

    def test_material_metric_and_real_gauge_covariance(self):
        d, g = self.direction(), cx(self.rng, 8)
        for voxel in (False, True):
            a, _ = fixture(voxel=voxel, book=self.book)
            z = self.rng.normal(size=a.p)
            dc = a.chart.expand(z)
            self.close('material_norm_'+str(voxel), a.chart.volume*np.vdot(dc, dc).real, z@z)
            self.close('material_project_'+str(voxel), a.chart.project(dc), z)
            self.close('material_adjoint_'+str(voxel), np.vdot(g, dc).real, z@a.chart.adjoint(g))
        O = la.qr(self.rng.normal(size=(self.a.chart.q, self.a.chart.q)))[0]
        chart2 = replace(self.a.chart, Q=self.a.chart.Q@O)
        a2 = Adapter(replace(self.a.problem, chart=chart2), book=self.book)
        state2 = a2.full_state(self.x)
        transform = la.block_diag(O.T, O.T)
        self.close('material_gauge_physical', chart2.expand(transform@d), self.a.chart.expand(d))
        self.close('material_gauge_J', a2.full_tangent_action(self.x, state2, transform@d),
                   self.a.full_tangent_action(self.x, self.state, d))
        w = self.rng.normal(size=self.a.P*2*self.a.m)
        self.close('material_gauge_pullback', a2.full_adjoint_action(self.x, state2, w),
                   transform@self.a.full_adjoint_action(self.x, self.state, w))

    def test_fixed_galerkin_reduced_state_derivative_and_native_equivalence(self):
        Z, d = self.basis(), self.direction()
        projection = Projection(self.a, self.x, Z, self.config, allow_petrov=False)
        reduced = self.a.reduced_state(self.x, projection)
        J = ReducedJacobian(self.a, self.x, reduced, projection)
        tangent = J.action(d)
        native = self.a.model.state(self.x, basis=Z)
        self.close('native_reduced_current', reduced.current, native.current)
        self.close('native_reduced_field', reduced.field, native.field)
        self.close('native_reduced_jvp', tangent, self.a.whiten(pack(native.jvp(self.a.chart.expand(d)))))
        w = self.rng.normal(size=self.a.P*2*self.a.m)
        self.close('native_reduced_vjp', J.pullback(w), self.a.chart.adjoint(native.vjp(unpack(self.a.whiten(w, adjoint=True), self.a.P, self.a.m))))
        self.close('reduced_real_adjoint', w@tangent, d@J.pullback(w))
        self.close('reduced_material_matrix_action', J.matrix()@d, tangent)
        def trial(xx):
            return self.a.reduced_state(xx, projection.trial(xx))
        self.close('frozen_Galerkin_fd', tangent, self.data_fd(trial, d), 1e-7)

    def test_frozen_petrov_derivative_and_moving_least_squares_term(self):
        Z, d = self.basis(), self.direction()
        LZ = self.a.apply_L(self.x, Z)
        W = la.qr(LZ, mode='economic')[0]
        projection = Projection(self.a, self.x, Z, self.config, test=W)
        reduced = self.a.reduced_state(self.x, projection)
        J = ReducedJacobian(self.a, self.x, reduced, projection)
        tangent = J.action(d)
        w = self.rng.normal(size=self.a.P*2*self.a.m)
        self.close('frozen_Petrov_adjoint', w@tangent, d@J.pullback(w))
        self.close('frozen_Petrov_matrix', J.matrix()@d, tangent)
        self.close('frozen_Petrov_fd', tangent,
                   self.data_fd(lambda xx: self.a.reduced_state(xx, projection.trial(xx)), d), 1e-7)
        # Moving W=L(x)Z has an additional residual-weighted derivative.
        self.a.version(self.x)
        b = self.a.forcing(self.x)
        L = self.a.apply_L(self.x, np.eye(self.a.n))
        coefficients = la.lstsq(L@Z, b)[0]
        current = Z@coefficients
        residual = b-L@current
        dc = self.a.chart.expand(d)
        _, da = kernel.polarizability(self.x, self.a.problem.volume, self.a.problem.frequency)
        LdotZ = -np.repeat(da*dc, 3)[:, None]*(self.a.model.Goff@Z)
        injection = self.a.apply_B(self.x, reduced, d).T
        normal = LZ.conj().T@LZ
        frozen_coeffdot = la.solve(normal, LZ.conj().T@injection)
        missing_coeffdot = la.solve(normal, LdotZ.conj().T@residual)
        exact = self.a.whiten(pack(self.a.apply_S(Z@(frozen_coeffdot+missing_coeffdot)).T))
        frozen = self.a.whiten(pack(self.a.apply_S(Z@frozen_coeffdot).T))
        h = 1e-6
        fields = []
        for xx in (self.x+h*dc, self.x-h*dc):
            LL = self.a.apply_L(xx, np.eye(self.a.n))
            cc = la.lstsq(LL@Z, self.a.forcing(xx))[0]
            fields.append(self.a.apply_S(Z@cc).T)
        fd = self.a.whiten(pack((fields[0]-fields[1])/(2*h)))
        self.close('moving_LS_correct_fd', exact, fd, 1e-7)
        omitted = float(la.norm(frozen-fd)/la.norm(fd))
        self.metrics['moving_LS_omitted_term_error'] = omitted
        self.assertGreater(omitted, 1e-5)

    def test_moving_galerkin_basis_requires_explicit_basis_derivative(self):
        Z, d = self.basis(), self.direction()
        Zdot = cx(self.rng, *Z.shape)
        Zdot -= Z@(Z.conj().T@Zdot)
        Zdot *= .3/la.norm(Zdot)
        projection = Projection(self.a, self.x, Z, self.config, allow_petrov=False)
        reduced = self.a.reduced_state(self.x, projection)
        frozen = ReducedJacobian(self.a, self.x, reduced, projection).action(d)
        b = self.a.forcing(self.x)
        L = self.a.apply_L(self.x, np.eye(self.a.n))
        coefficient = la.solve(Z.conj().T@L@Z, Z.conj().T@b)
        residual = b-L@Z@coefficient
        correction = Zdot@coefficient + Z@la.solve(Z.conj().T@L@Z,
                     Zdot.conj().T@residual-Z.conj().T@L@Zdot@coefficient)
        exact = frozen+self.a.whiten(pack(self.a.apply_S(correction).T))
        dc, h = self.a.chart.expand(d), 1e-6
        fields = []
        for sign in (1., -1.):
            xx = self.x+sign*h*dc
            ZZ = orth(Z+sign*h*Zdot)[0]
            pp = Projection(self.a, xx, ZZ, self.config, allow_petrov=False)
            fields.append(self.a.reduced_state(xx, pp).field)
        fd = self.a.whiten(pack((fields[0]-fields[1])/(2*h)))
        self.close('moving_Galerkin_correct_fd', exact, fd, 1e-7)
        omitted = float(la.norm(frozen-fd)/la.norm(fd))
        self.metrics['moving_Galerkin_omitted_term_error'] = omitted
        self.assertGreater(omitted, 1e-5)

    def test_A1_full_state_tangent_distinguished_from_A2_derivative(self):
        Z, d = self.basis(), self.direction()
        projection = Projection(self.a, self.x, Z, self.config, allow_petrov=False)
        reduced = self.a.reduced_state(self.x, projection)
        A1 = ReducedJacobian(self.a, self.x, self.state, projection).action(d)
        A2 = ReducedJacobian(self.a, self.x, reduced, projection).action(d)
        fd = self.data_fd(lambda xx: self.a.reduced_state(xx, projection.trial(xx)), d)
        self.close('A2_is_frozen_reduced_derivative', A2, fd, 1e-7)
        difference = float(la.norm(A1-fd)/la.norm(fd))
        self.metrics['A1_is_not_A2_derivative'] = difference
        self.assertGreater(difference, 1e-5)

    def test_projection_complex_adjoint_and_current_unitary_gauge(self):
        Z = self.basis()
        V = la.qr(cx(self.rng, Z.shape[1], Z.shape[1]))[0]
        b, w = cx(self.rng, self.a.n, 3), cx(self.rng, self.a.n, 3)
        for petrov in (False, True):
            W = la.qr(self.a.apply_L(self.x, Z), mode='economic')[0] if petrov else None
            p = Projection(self.a, self.x, Z, self.config, test=W, allow_petrov=False)
            p2 = Projection(self.a, self.x, Z@V, self.config,
                            test=None if W is None else W@V, allow_petrov=False)
            self.close('projection_adjoint_'+str(petrov), np.vdot(w, p.apply(b)), np.vdot(p.adjoint(w), b))
            self.close('current_gauge_projection_'+str(petrov), p.apply(b), p2.apply(b))
            reduced = self.a.reduced_state(self.x, p)
            reduced2 = self.a.reduced_state(self.x, p2)
            self.close('current_gauge_state_'+str(petrov), reduced.field, reduced2.field)
            d = self.direction()
            self.close('current_gauge_tangent_'+str(petrov), ReducedJacobian(self.a, self.x, reduced, p).action(d),
                       ReducedJacobian(self.a, self.x, reduced2, p2).action(d))

    def test_exact_schur_actions_adjoint_resolvent_and_galerkin_equivalence(self):
        view = self.view()
        U = self.basis(2)
        feedback = SchurFeedback(view, U, self.config)
        L = self.a.apply_L(self.x, np.eye(self.a.n))
        F = np.eye(self.a.n)-L
        P = np.eye(self.a.n)-U@U.conj().T
        R = U@la.solve(U.conj().T@L@U, U.conj().T)
        explicit = P@F@P+P@F@U@la.solve(U.conj().T@L@U, U.conj().T@F@P)
        v, w = cx(self.rng, self.a.n, 3), cx(self.rng, self.a.n, 3)
        self.close('Schur_F_eff', feedback.F(v), explicit@v)
        self.close('Schur_F_eff_adjoint', feedback.F_adjoint(w), explicit.conj().T@w)
        self.close('Schur_adjoint_pair', np.vdot(w, feedback.F(v)), np.vdot(feedback.F_adjoint(w), v))
        self.close('Schur_T', feedback.T(v), (np.eye(self.a.n)-R@L)@P@v)
        self.close('Schur_K', feedback.K(v), P@(np.eye(self.a.n)-L@R)@v)
        for name in ('T', 'K'):
            self.close('Schur_'+name+'_adjoint', np.vdot(w, getattr(feedback, name)(v)),
                       np.vdot(getattr(feedback, name+'_adjoint')(w), v))
        complement = la.null_space(U.conj().T)
        A = np.eye(complement.shape[1])-complement.conj().T@feedback.F(complement)
        schur_inverse = R+feedback.T(complement)@la.solve(A, complement.conj().T@feedback.K(np.eye(self.a.n)))
        self.close('full_Schur_resolvent', schur_inverse, la.solve(L, np.eye(self.a.n)))
        Q = orth(cx(self.rng, self.a.n, 4), against=U)[0]
        Z = np.column_stack((U, Q))
        reduced = R+feedback.T(Q)@la.solve(np.eye(Q.shape[1])-Q.conj().T@feedback.F(Q),
                                          Q.conj().T@feedback.K(np.eye(self.a.n)))
        galerkin = Projection(self.a, self.x, Z, self.config, allow_petrov=False).apply(np.eye(self.a.n))
        self.close('Schur_Galerkin_equivalence', reduced, galerkin)
        empty = SchurFeedback(view, np.empty((self.a.n, 0), complex), self.config)
        self.close('empty_U_F', empty.F(v), self.a.apply_F(self.x, v))
        self.close('empty_U_T', empty.T(v), v)
        self.close('empty_U_K', empty.K(v), v)
        self.close('empty_U_R', empty.R_U(v), np.zeros_like(v))

    def test_seed_zero_budgets_and_zero_deflated_blocks(self):
        zero = np.zeros_like(self.x)
        state = self.a.full_state(zero)
        view = BasisView(self.a, zero, state, np.zeros(self.a.P*2*self.a.m))
        feedback = SchurFeedback(view, np.empty((self.a.n, 0), complex), self.config)
        seeds = build_seeds(view, feedback, self.config,
                            material_probes=np.zeros((self.a.p, 1)),
                            measurement_probes=np.zeros((self.a.P*2*self.a.m, 1)))
        self.assertEqual({k: z.shape[1] for k, z in seeds.blocks.items()}, {'O': 0, 'P': 0, 'M': 0})
        h = Hierarchy(view, feedback, seeds, self.config)
        for degree in range(4):
            Z, diagnostic = h.at_degree(degree)
            self.assertEqual(Z.shape, (self.a.n, 0))
            self.assertEqual(diagnostic['orthogonality_error'], 0.)
        self.metrics['zero_seed_diagnostics'] = seeds.records
        empty_projection = Projection(self.a, zero, Z, self.config, allow_petrov=False)
        rhs = cx(self.rng, self.a.n, 2)
        self.close('empty_projection_apply', empty_projection.apply(rhs), np.zeros_like(rhs))
        self.close('empty_projection_adjoint', empty_projection.adjoint(rhs), np.zeros_like(rhs))
        empty_state = self.a.reduced_state(zero, empty_projection)
        self.close('empty_projection_state', empty_state.field, np.zeros((self.a.P, self.a.m), complex))
        empty_J = ReducedJacobian(self.a, zero, empty_state, empty_projection)
        d = self.direction()
        dim = self.a.P*2*self.a.m
        self.close('empty_projection_J_matrix', empty_J.matrix(), np.zeros((dim, self.a.p)))
        self.close('empty_projection_J_action', empty_J.action(d), np.zeros(dim))
        self.close('empty_projection_J_batched_action', empty_J.action(np.eye(self.a.p)), np.zeros((dim, self.a.p)))
        self.close('empty_projection_J_pullback', empty_J.pullback(self.rng.normal(size=dim)), np.zeros(self.a.p))
        self.metrics['empty_projected_core_shape'] = list(empty_projection.A.shape)
        before = dict(self.book.counts)
        zero_budgets = build_seeds(view, feedback, self.config, budgets={'O': 0, 'P': 0, 'M': 0})
        self.assertTrue(all(z.shape[1] == 0 for z in zero_budgets.blocks.values()))
        for counter in ('B_rhs', 'S_adjoint_actions', 'forcing_rhs'):
            self.assertEqual(self.book.counts[counter], before.get(counter, 0), counter)
        q, diagnostic = orth(np.zeros((self.a.n, 3)))
        self.assertEqual(q.shape[1], 0)
        self.assertEqual(diagnostic['deflated'], 3)
        v = self.basis(1)
        q, diagnostic = orth(np.column_stack((v, v, 2*v)))
        self.assertEqual(q.shape[1], 1)
        self.assertEqual(diagnostic['deflated'], 2)

    def test_real_physical_hierarchy_nested_streams_and_breakdown(self):
        feedback = SchurFeedback(self.view(), self.basis(2), self.config)
        seeds = build_seeds(self.view(), feedback, self.config)
        hierarchy = Hierarchy(self.view(), feedback, seeds, self.config)
        previous = np.empty((self.a.n, 0), complex)
        for degree in range(3):
            Z, diagnostic = hierarchy.at_degree(degree)
            self.close('nested_prefix_'+str(degree), Z[:, :previous.shape[1]], previous)
            self.assertLess(diagnostic['orthogonality_error'], 1e-9)
            self.assertFalse(diagnostic['joint_core_is_single_Hessenberg'])
            self.assertEqual(set(diagnostic['separate_stream_recurrences']), set('OPM'))
            previous = Z.copy()
        with self.assertRaisesRegex(ValueError, 'monotonically'):
            hierarchy.at_degree(1)
        F = self.a.apply_F(self.x, np.eye(self.a.n))
        _, eigvec = la.eig(F)
        stream = BlockStream(orth(eigvec[:, :1])[0], lambda v: self.a.apply_F(self.x, v), self.book, 1e-10)
        stream.extend()
        self.assertEqual(stream.blocks[-1].shape[1], 0)
        count = self.book.counts['F_actions']
        stream.extend()
        self.assertTrue(stream.recurrence[-1]['breakdown'])
        self.assertEqual(self.book.counts['F_actions'], count)
        self.metrics['hierarchy_diagnostics'] = diagnostic

    def test_singular_and_absolute_small_cores_rejected_and_fallback_named(self):
        self.assertFalse(core_stability(np.diag([1., 0.]), 1., self.config)['safe'])
        tiny = core_stability(np.eye(2)*1e-12, 1., self.config)
        self.assertEqual(tiny['condition'], 1.)
        self.assertFalse(tiny['safe'])
        self.metrics['well_conditioned_absolute_small_core'] = tiny
        Z = self.basis(4)
        LZ = self.a.apply_L(self.x, Z)
        W = la.qr(LZ, mode='economic')[0]
        Wnull = la.null_space(LZ.conj().T)[:, :Z.shape[1]]
        for label, WW in (('singular', Wnull), ('absolute_small', Wnull+1e-12*W)):
            with self.assertRaisesRegex(UnsafeCore, 'UNSAFE'):
                Projection(self.a, self.x, Z, self.config, test=WW)
            self.metrics[label+'_physical_projected_sigma'] = float(la.svdvals(WW.conj().T@LZ)[-1])
        scale = max(1., la.norm(self.a._operator_L))
        gal_low = la.svdvals(Z.conj().T@LZ)[-1]/scale
        qr_low = la.svdvals(LZ)[-1]/scale
        self.assertGreater(qr_low-gal_low, 1e-8)
        config = dict(self.config, core_absolute_scaled_sigma_floor=(gal_low+qr_low)/2)
        p = Projection(self.a, self.x, Z, config)
        self.assertEqual(p.kind, 'frozen_test_petrov_qr')
        self.assertEqual(p.fallback, 'unsafe_Galerkin_to_frozen_Petrov')
        self.assertFalse(p.galerkin_stability['safe'])
        self.assertTrue(p.stability['safe'])
        self.assertGreaterEqual(self.book.counts['petrov_fallbacks'], 1)

    def test_constrained_chart_quadratic_KKT_and_full_gap_bound(self):
        full = FullJacobian(self.a, self.x, self.state)
        J = full.small_matrix()
        lam = .5
        H = J.T@J+lam*np.eye(self.a.p)
        A, lower = constraint_map(self.a.chart, self.x)
        target = self.a.chart.project(-1j*self.x.imag)
        mu = np.r_[np.zeros(8), np.full(8, .001)]
        ell = -H@target+A.T@mu
        residual = np.zeros(J.shape[0])
        try:
            s, result, normal = solve_quadratic(self.a.chart, self.x, residual, full, lam, ell, self.config, self.book)
        except QPFailure as error:
            self.metrics['QP_failure_result'] = error.result
            self.metrics['QP_failure_step_error'] = float(la.norm(error.step-target))
            raise
        self.close('constrained_known_step', s, target, 1e-7)
        audit = kkt(self.a.chart, self.x, s, H@s+ell)
        self.assertLess(audit['stationarity_norm'], 1e-8)
        self.assertLess(audit['violation'], 1e-8)
        self.assertLess(audit['complementarity'], 1e-8)
        self.assertEqual(audit['dual_violation'], 0.)
        self.assertGreater(result['active_constraints'], 0)
        self.assertTrue(result['no_post_clipping'])
        feasible = .8*s
        gap = full_quadratic_audit(full, residual, lam, ell, feasible, s,
                                   kkt(self.a.chart, self.x, feasible, H@feasible+ell)['normal'])
        self.assertGreater(gap['full_quadratic_gap'], gap['half_H_error_energy'])
        self.assertLessEqual(gap['absolute_H_step_error'], gap['KKT_bound_H_error']+1e-9)
        self.assertLessEqual(gap['full_quadratic_gap'], gap['KKT_bound_quadratic_gap']+1e-9)
        self.metrics['constrained_result'] = result
        self.metrics['full_constrained_audit'] = gap

    def test_tiny_voxel_quadratic_KKT_and_constraints(self):
        a, x = fixture(voxel=True, book=self.book)
        state = a.full_state(x)
        full = FullJacobian(a, x, state)
        J = full.small_matrix()
        lam = .5
        H = J.T@J+lam*np.eye(a.p)
        target = a.chart.project(-1j*x.imag)
        mu = np.r_[np.zeros(8), np.full(8, .003)]
        ell = -H@target+mu
        s, result, _ = solve_quadratic(a.chart, x, np.zeros(J.shape[0]), full, lam, ell, self.config, self.book)
        self.close('voxel_known_step', s, target, 1e-7)
        self.assertLess(result['kkt_relative'], self.config['qp_kkt_rtol'])
        updated = x+a.chart.expand(s)
        self.assertLess(a.material_constraints(updated)['violation'], 1e-8)
        with self.assertRaisesRegex(ValueError, 'Positive'):
            solve_quadratic(a.chart, x, np.zeros(J.shape[0]), full, 0., ell, self.config, self.book)
        self.metrics['voxel_result'] = result

    def test_online_payload_and_basis_capability_reject_offline_fields(self):
        view = self.view()
        for name in ('teacher', 'truth', 'full_J', 'full_H', 'reference_step', 'labels'):
            with self.subTest(field=name):
                with self.assertRaises(ForbiddenAccess):
                    getattr(self.a.problem, name)
                with self.assertRaises(ForbiddenAccess):
                    getattr(view, name)
        for name in ('full_current', 'current_correction', 'full_state', 'old_anchor'):
            with self.assertRaises(ForbiddenAccess):
                getattr(view, name)
        p = self.a.problem
        payload = dict(parent_id=p.parent_id, points=p.points, volume=p.volume,
                       data0=p.data, scale=p.scale, init=p.init, Q=p.chart.Q,
                       kind=p.chart.kind, dirs=p.dirs, pols=p.pols,
                       receivers=p.receivers, obs_basis=p.obs_basis, k=p.frequency)
        OUTPUT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='online_contract_', dir=OUTPUT) as temp:
            path = Path(temp)/'online.npz'
            np.savez(path, **payload)
            loaded = load_problem(path)
            self.close('online_chart_preserved', loaded.chart.Q, p.chart.Q)
            for name in ('teacher', 'truth', 'full_J', 'full_H', 'reference_step', 'unregistered'):
                np.savez(path, **payload, **{name: np.array([0.])})
                with self.assertRaisesRegex(ForbiddenAccess, 'OFFLINE_OR_UNREGISTERED'):
                    load_problem(path)
            np.savez(path, **dict(payload, Q=2*p.chart.Q))
            with self.assertRaisesRegex(ValueError, 'metric mismatch'):
                load_problem(path)

    def test_material_refresh_invalidates_projection_and_cached_reduced_matrix(self):
        Z = self.basis()
        p = Projection(self.a, self.x, Z, self.config, allow_petrov=False)
        reduced = self.a.reduced_state(self.x, p)
        J = ReducedJacobian(self.a, self.x, reduced, p)
        J.matrix()
        version = self.a.version(self.x)
        self.a.version(self.x+.001)
        self.assertGreater(self.a._version, version)
        with self.assertRaisesRegex(ValueError, 'invalidated'):
            J.matrix()
        with self.assertRaisesRegex(ValueError, 'invalidated'):
            p.apply(cx(self.rng, self.a.n))
        refreshed = p.trial(self.x)
        state2 = self.a.reduced_state(self.x, refreshed)
        self.close('fresh_trial_after_invalidated_cache', state2.field, reduced.field)
        self.assertIs(self.a.full_state(self.x, reuse=True), self.state)
        old_calls = self.book.counts['full_forward_calls']
        chosen = self.a.full_state(self.x, source=1, reuse=True)
        self.close('full_cache_source_selection', chosen, self.state.current[1])
        self.assertEqual(self.book.counts['full_forward_calls'], old_calls)
        with self.assertRaisesRegex(ValueError, 'mismatch'):
            self.a.full_objective(self.x+.001, state=self.state)

    def test_full_tangent_and_adjoint_refuse_wrong_material_state(self):
        d, w = self.direction(), self.rng.normal(size=self.a.P*2*self.a.m)
        for name, argument in (('full_tangent_action', d), ('full_adjoint_action', w)):
            with self.subTest(action=name):
                with self.assertRaisesRegex(ValueError, 'mismatch'):
                    getattr(self.a, name)(self.x+.001, self.state, argument)

    def test_full_physics_contract_refuses_native_and_adapter_reduced_states(self):
        Z = self.basis()
        p = Projection(self.a, self.x, Z, self.config, allow_petrov=False)
        states = {'adapter': self.a.reduced_state(self.x, p),
                  'native': self.a.model.state(self.x, basis=Z)}
        d, w = self.direction(), self.rng.normal(size=self.a.P*2*self.a.m)
        for kind, state in states.items():
            for name, argument in (('full_tangent_action', d), ('full_adjoint_action', w)):
                with self.subTest(state=kind, action=name):
                    with self.assertRaisesRegex(ValueError, 'full state'):
                        getattr(self.a, name)(self.x, state, argument)
            with self.subTest(state=kind, action='full_objective'):
                with self.assertRaisesRegex(ValueError, 'full state'):
                    self.a.full_objective(self.x, state=state)

    def test_full_physics_rejects_foreign_frequency_and_geometry_models(self):
        frequency, _ = fixture(frequency=1.25, book=self.book)
        geometry = Adapter(replace(self.a.problem, receivers=self.a.problem.receivers+.03), book=self.book)
        d, w = self.direction(), self.rng.normal(size=self.a.P*2*self.a.m)
        for model in (frequency, geometry):
            state = model.full_state(self.x)
            for name, argument in (('full_tangent_action', d), ('full_adjoint_action', w)):
                with self.subTest(frequency=model.problem.frequency, action=name):
                    with self.assertRaises(ValueError):
                        getattr(self.a, name)(self.x, state, argument)
            with self.assertRaises(ValueError):
                self.a.full_objective(self.x, state=state)
            Z = self.basis()
            projected = Projection(model, self.x, Z, self.config, allow_petrov=False)
            foreign_reduced = model.reduced_state(self.x, projected)
            for injected_state in (state, foreign_reduced):
                with self.subTest(frequency=model.problem.frequency,
                                  injection_state=type(injected_state).__name__):
                    with self.assertRaisesRegex(ValueError, 'mismatch'):
                        self.a.apply_B(self.x, injected_state, d)
                    with self.assertRaisesRegex(ValueError, 'mismatch'):
                        self.a.apply_B_adjoint(self.x, injected_state, cx(self.rng, self.a.P, self.a.n))

    def test_budget_rejection_and_failed_action_accounting(self):
        blocked = CostBook(prior_cpu=1., cpu_limit=.5, cpu_reserve=.1)
        with self.assertRaisesRegex(BudgetExceeded, 'CPU_LIMIT'):
            Adapter(self.a.problem, book=blocked)
        self.assertEqual(blocked.events, 0)
        self.assertEqual(dict(blocked.counts), {})
        before = dict(self.book.counts)
        with self.assertRaisesRegex(RuntimeError, 'injected'):
            with self.book.span('injected_failed_action', rejected_trials=1):
                self.a.apply_L(self.x, cx(self.rng, self.a.n, 2))
                raise RuntimeError('injected test failure')
        self.assertEqual(self.book.counts['rejected_trials']-before.get('rejected_trials', 0), 1)
        self.assertEqual(self.book.counts['L_actions']-before.get('L_actions', 0), 2)
        rows = [json.loads(line) for line in self.book.path.read_text().splitlines()]
        row = next(row for row in reversed(rows) if row['event']=='injected_failed_action')
        self.assertEqual(row['status'], 'FAILED')
        self.assertGreater(row['process_cpu_seconds'], 0.)
        self.assertLessEqual(row['exclusive_wall_seconds'], row['wall_seconds'])
        self.assertLessEqual(sum(self.book.walls.values()), self.book.receipt()['wall_seconds']+1e-6)
        self.metrics['failed_action_receipt'] = row

    def test_tiny_two_update_nonlinear_full_A1_A2_smoke(self):
        from a20.imaging import reconstruct
        config = dict(self.config, max_updates=2, lm0=2., retained_rank=2)
        for method, mode in (('FULL_GN', 'A1'), ('OPM', 'A1'), ('OPM', 'A2')):
            with self.subTest(method=method, mode=mode):
                a, x = fixture(book=self.book)
                initial = a.full_objective(x, config['prior'])[0]
                xhat, result, iterations, _ = reconstruct(a.problem, config, self.book, 'cpu',
                                     method=method, mode=mode, degree=0, adapter=a)
                self.metrics[method+'_'+mode] = {'run': result, 'iterations': iterations}
                self.assertIsNone(result['failure'])
                self.assertLessEqual(result['final_full_objective'], initial+1e-12)
                self.assertLess(a.material_constraints(xhat)['violation'], 1e-8)
                self.assertTrue(iterations)
                self.assertTrue(all(row['accepted'] for row in iterations))
                self.assertTrue(all(row['actual_reduction']>0 for row in iterations))
                if mode == 'A2':
                    self.assertTrue(all(trial.get('reduced_trial_status')=='COHERENT_FROZEN_BASIS'
                                        for row in iterations for trial in row['trials']))


class SuppliedCounterexamples(unittest.TestCase):
    def test_frozen_protocol_algebra_and_counterexample_regressions(self):
        spec = importlib.util.spec_from_file_location('a20_frozen_theory_checks', ROOT/'protocol/experiments/check_theory.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        result = module.run()  # no script-mode write to protocol/experiments
        self.metrics = {'theory': result}
        self.assertEqual(result['status'], 'ALL ASSERTIONS PASSED')
        self.assertTrue(all(abs(row['step'])<1e-12 for row in result['delayed_feedback'][:3]))
        self.assertGreater(result['delayed_feedback'][3]['step'], .1)
        self.assertEqual(result['false_weak_counterexample']['reduced_data_change'], 0.)
        self.assertEqual(result['false_weak_counterexample']['full_data_change'], 1.)


if __name__ == '__main__':
    unittest.main()
