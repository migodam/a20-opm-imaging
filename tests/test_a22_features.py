"""Tiny residual/packing boundary tests; source-only worker handoff.

Fixtures below are arbitrary small matrices, not Maxwell evidence.  They
provide only known-anchor residual capabilities and reject access to full
derivatives, offline benchmarks or labels.  No campaign/evaluator is run.
"""
from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
from types import SimpleNamespace
import unittest

import numpy as np

from a20.backend import pack
from a22.features import (build_descriptor_context, direction_descriptor,
                          predict_budget)


_DENIED_FIELDS = frozenset((
    'truth', 'held_truth', 'teacher', 'labels', 'oracle', 'full_J', 'full_H',
    'offline_benchmark', 'reference_step', 'full_state', 'full_tangent_action',
    'full_adjoint_action', 'full_jacobian', 'full_hessian', 'jvp', 'vjp',
))


class _Guarded(SimpleNamespace):
    def __init__(self, **values):
        super().__init__(_offline_accesses=[], **values)

    def __getattribute__(self, name):
        if name in _DENIED_FIELDS:
            object.__getattribute__(self, '_offline_accesses').append(name)
            raise AssertionError('Offline capability requested by feature: ' + name)
        return super().__getattribute__(name)


class _PoisonLabel:
    def __array__(self, *args, **kwargs):
        raise AssertionError('A label was converted into a feature input')


class _Book:
    def __init__(self):
        self.counts = Counter()
        self.operations = []

    @contextmanager
    def span(self, name, **counts):
        self.operations.append(name)
        self.counts.update(counts)
        yield


class _View(_Guarded):
    def B(self, direction):
        self.calls['B'] += 1
        return np.einsum('pnd,dk->pnk', self.Bmat, direction)

    def L_adjoint(self, value):
        self.calls['L_adjoint'] += 1
        return self.L.conj().T @ value

    def S_adjoint(self, value):
        self.calls['S_adjoint'] += 1
        return self.S.conj().T @ value

    def B_adjoint(self, value):
        self.calls['B_adjoint'] += 1
        # A real material chart requires the real Euclidean pullback.
        return np.einsum('pnd,pn->d', self.Bmat.conj(), value).real


class _Projection(_Guarded):
    def check(self):
        self.calls['check'] += 1

    def solve(self, rhs, adjoint=False):
        self.calls['adjoint_solve' if adjoint else 'solve'] += 1
        return np.linalg.solve(self.A.conj().T if adjoint else self.A, rhs)


class _Adapter(_Guarded):
    def whiten(self, value, adjoint=False):
        return self.whitening * value

    def injection_factor(self, material, state):
        self.calls['injection_factor'] += 1
        return self.factor


def _fixture():
    rng = np.random.default_rng(202610077)
    sources, cells, channels, rank, material = 6, 16, 2, 2, 32
    current, volume = 3*cells, .125
    basis, _ = np.linalg.qr(rng.normal(size=(current, rank)) +
                            1j*rng.normal(size=(current, rank)))
    L = np.diag(1. + np.linspace(.02, .07, current) +
                1j*np.linspace(.03, .08, current))
    S = rng.normal(size=(channels, current)) + 1j*rng.normal(size=(channels, current))
    factor = rng.normal(size=(sources, cells, 3)) + 1j*rng.normal(size=(sources, cells, 3))
    material_Q = np.eye(cells) / np.sqrt(volume)
    spatial_B = np.einsum('ptc,td->ptcd', factor, material_Q).reshape(sources, current, 16)
    B = np.concatenate((spatial_B, 1j*spatial_B), axis=2)
    core = basis.conj().T @ L @ basis
    MW = np.einsum('nq,pnd->pqd', basis.conj(), B)
    PMW = np.linalg.solve(core, MW.transpose(1, 0, 2).reshape(rank, -1))
    PMW = PMW.reshape(rank, sources, material).transpose(1, 0, 2)
    raw = np.einsum('mq,pqd->pmd', S @ basis, PMW)
    whitening = 2.5
    AW = whitening * pack(raw)
    book = _Book()
    projection = _Projection(A=core, LZ=L @ basis, SZ=S @ basis, calls=Counter())
    view = _View(Bmat=B, L=L, S=S, calls=Counter())
    physical_model = _Guarded(GS=S, Goff=np.zeros((current, current), complex), N=current // 3)
    chart = _Guarded(Q=material_Q, d=material)
    problem = _Guarded(volume=volume, frequency=1., parent_id=2001)
    adapter = _Adapter(book=book, P=sources, m=channels, n=current, p=material,
                       whitening=whitening, _operator_L=L, model=physical_model,
                       chart=chart, problem=problem, factor=factor, calls=Counter())
    state = _Guarded(field=rng.normal(size=(sources, channels)) +
                           1j*rng.normal(size=(sources, channels)),
                     exciting=rng.normal(size=(sources, current)) +
                              1j*rng.normal(size=(sources, current)))
    anchor = _Guarded(adapter=adapter, state=state,
                      chi=np.full(current // 3, .1 + .04j))
    model = _Guarded(anchor=anchor, projection=projection, basis=basis,
                     view=view, AW=AW, MW=MW, PMW=PMW)
    config = {'tikhonov_relative': 1e-4, 'nuisance_fraction': .35,
              'descriptor_material_pointwise_prior': .25}
    guards = (model, anchor, adapter, state, physical_model, problem, chart,
              projection, view)
    return model, config, guards


class DescriptorImplementationChecks(unittest.TestCase):
    def test_residual_shapes_real_packing_and_complex_adjoint_without_offline_access(self):
        model, config, guards = _fixture()
        context = build_descriptor_context(model, config)
        self.assertEqual(context.B.shape, (6, 48, 32))
        self.assertEqual(context.IR.shape, (6, 48, 32))
        self.assertEqual(context.LH_Q.shape, (48, 2))
        np.testing.assert_allclose(context.IR,
            model.view.Bmat - np.einsum('nq,pqd->pnd', model.projection.LZ, model.PMW),
            atol=1e-12)
        descriptor = direction_descriptor(context, np.eye(32)[:, 0], config)
        self.assertLess(descriptor['transpose_identity_error'], 1e-11)
        self.assertEqual(model.projection.calls['adjoint_solve'], 1)
        self.assertEqual(model.view.calls['S_adjoint'], 1)
        self.assertEqual(model.view.calls['B_adjoint'], 1)
        # Independent complex inner-product form of the registered real pack:
        # each source contributes real channels, then imaginary channels.
        x = np.linspace(-.5, .7, 32)
        h = np.linspace(-1.2, .9, model.AW.shape[0])
        blocks = h.reshape(6, 2, 2)
        cotangent = model.anchor.adapter.whitening * (blocks[:, 0] + 1j*blocks[:, 1])
        raw = np.einsum('mq,pqd,d->pm', model.projection.SZ, model.PMW, x)
        expected = float(np.real(np.sum(cotangent.conj() * raw)))
        self.assertAlmostEqual(float(h @ model.AW @ x), expected, places=10)
        calls = dict(model.view.calls), dict(model.projection.calls), dict(model.anchor.adapter.calls)
        prediction = predict_budget(context, descriptor, .02, 1., 'nominal', config)
        self.assertEqual((dict(model.view.calls), dict(model.projection.calls),
                          dict(model.anchor.adapter.calls)), calls)
        self.assertFalse(prediction['full_reference_or_true_error_used'])
        self.assertFalse(prediction['receiver_or_source_actual_signs_used'])
        self.assertFalse(context.provenance['full_J_full_H_full_adjoint_or_truth_used'])
        self.assertFalse(descriptor['provenance']['full_J_or_labels_used'])
        for guarded in guards:
            self.assertEqual(guarded._offline_accesses, [])

    def test_descriptor_and_prediction_are_independent_of_label_or_full_j_config_fields(self):
        model, config, guards = _fixture()
        config.update(truth=_PoisonLabel(), recovery_labels=_PoisonLabel(), full_J=_PoisonLabel())
        context = build_descriptor_context(model, config)
        v = np.eye(32)[:, 3]
        first = direction_descriptor(context, v, config)
        first_prediction = predict_budget(context, first, .015, 3.,
            'source_amplitude_5pct_receiver_gain_3pct', config)
        config.update(truth=_PoisonLabel(), recovery_labels=_PoisonLabel(), full_J=_PoisonLabel())
        second = direction_descriptor(context, v, config)
        second_prediction = predict_budget(context, second, .015, 3.,
            'source_amplitude_5pct_receiver_gain_3pct', config)
        np.testing.assert_array_equal(first['h'], second['h'])
        for key in ('alpha', 'beta', 'gamma', 'total_gain', 'profile_g', 'attribution',
                    'dual_defect_norm', 'background_calibration_budget'):
            self.assertEqual(first[key], second[key])
        self.assertEqual(first_prediction, second_prediction)
        for guarded in guards:
            self.assertEqual(guarded._offline_accesses, [])

    def test_zero_complex_nonfinite_and_wrong_layout_directions_are_rejected_before_actions(self):
        model, config, _ = _fixture()
        context = build_descriptor_context(model, config)
        operations = list(model.anchor.adapter.book.operations)
        calls = dict(model.view.calls), dict(model.projection.calls), dict(model.anchor.adapter.calls)
        for value in (np.zeros(32), np.ones(31), np.ones(32, complex), np.full(32, np.nan)):
            with self.subTest(value=value), self.assertRaises(ValueError):
                direction_descriptor(context, value, config)
        self.assertEqual(model.anchor.adapter.book.operations, operations)
        self.assertEqual((dict(model.view.calls), dict(model.projection.calls),
                          dict(model.anchor.adapter.calls)), calls)


if __name__ == '__main__':
    unittest.main()
