"""Small matrix/API regressions, not Maxwell or scientific gate evidence.

Source handoff only: the worker has not executed these tests.  The parent
owns the metered invocation.  No data files, truth scene, remote service,
solver campaign, network, hash or learned model is accessed here.
"""
from __future__ import annotations

from collections import defaultdict
from contextlib import contextmanager
import unittest
from unittest import mock

import numpy as np

from a22 import core
from a22.core import (build_split, choose_directions,
                      constrained_material_solve, profiled_witness)


class _PairedChart:
    """Euclidean real/imag chart for a small declared voxel material model."""
    def __init__(self, cells, volume=1.):
        self.n = cells
        self.d = 2 * cells
        self.volume = float(volume)
        self.Q = None

    def expand(self, value):
        return (value[:self.n] + 1j * value[self.n:]) / np.sqrt(self.volume)


class _Book:
    def __init__(self):
        self.counts = defaultdict(int)
        self.operations = []

    @contextmanager
    def span(self, name, **counts):
        self.operations.append(name)
        for key, value in counts.items():
            self.counts[key] += value
        yield


class ProfiledWitnessChecks(unittest.TestCase):
    def test_bright_nearly_aliased_direction_has_small_profile_gain_and_large_variance(self):
        epsilon = 1e-3
        A = np.array([[1., 1.], [0., epsilon]])
        witness = profiled_witness(A, np.array([1., 0.]))
        self.assertEqual(witness['status'], 'OK')
        self.assertAlmostEqual(witness['total_gain'], 1.)
        self.assertAlmostEqual(witness['g'], epsilon / np.sqrt(1 + epsilon**2), places=10)
        np.testing.assert_allclose(A.T @ witness['h'], [1., 0.], atol=2e-10)
        # For this registered two-column example the exact unbiased witness
        # is [1,-1/epsilon]; its noise variance is an independent closed form.
        sigma = .05
        expected_variance = sigma**2 * (1 + 1 / epsilon**2)
        observed_variance = sigma**2 * (witness['h'] @ witness['h'])
        np.testing.assert_allclose(observed_variance, expected_variance, rtol=2e-10)
        self.assertGreater(observed_variance, 1e5 * sigma**2)

    def test_zero_direction_and_zero_response_do_not_create_a_finite_witness(self):
        zero_direction = profiled_witness(np.eye(3), np.zeros(3))
        self.assertEqual(zero_direction['status'], 'ZERO_DIRECTION')
        self.assertIsNone(zero_direction['h'])
        self.assertIsNone(zero_direction['attribution'])
        zero_response = profiled_witness(np.zeros((2, 3)), np.array([1., 0., 0.]))
        self.assertEqual(zero_response['status'], 'UNIDENTIFIABLE')
        self.assertIsNone(zero_response['h'])
        self.assertIsNone(zero_response['attribution'])
        self.assertEqual(zero_response['g'], 0.)

    def test_full_nuisance_witness_is_normal_to_nuisance_and_returns_target(self):
        rng = np.random.default_rng(202610071)
        A = rng.normal(size=(7, 4))
        v = rng.normal(size=4)
        v /= np.linalg.norm(v)
        witness = profiled_witness(A, v)
        self.assertEqual(witness['status'], 'OK')
        self.assertEqual(witness['N'].shape, (4, 3))
        np.testing.assert_allclose(witness['N'].T @ v, 0., atol=1e-13)
        np.testing.assert_allclose((A @ witness['N']).T @ witness['h'], 0., atol=1e-11)
        np.testing.assert_allclose(A.T @ witness['h'], v, atol=1e-11)
        reference = A @ np.linalg.solve(A.T @ A, v)
        np.testing.assert_allclose(witness['h'], reference, atol=1e-11)
        self.assertLessEqual(witness['attribution'], 1 + 1e-12)

    def test_individually_bright_bad_span_counterexample_is_not_identifiable(self):
        A = np.array([[1., 1.]])
        for index in range(2):
            v = np.eye(2)[:, index]
            self.assertEqual(np.linalg.norm(A @ v), 1.)
            witness = profiled_witness(A, v)
            self.assertEqual(witness['status'], 'UNIDENTIFIABLE')
            self.assertIsNone(witness['h'])
        np.testing.assert_allclose(A @ (np.array([1., -1.]) / np.sqrt(2)), 0., atol=1e-14)
        self.assertEqual(np.linalg.matrix_rank(A @ np.eye(2)), 1)
        with self.assertRaises(ValueError):
            build_split({'AW': A}, {}, rank=2)


class MaterialSplitChecks(unittest.TestCase):
    def test_svd_block_noise_shrinkage_and_full_complement_are_explicit(self):
        singular = np.array([4., 2., .5, .1])
        A = np.diag(singular)
        relative_lambda = 1e-3
        split = build_split({'AW': A}, {'certificate_type': 'empirical_indicator'},
                            {'tikhonov_relative': relative_lambda}, rank=2)
        lam = relative_lambda * singular[0]**2
        self.assertEqual(split.status, 'TANGENT_CANDIDATE')
        self.assertEqual(split.rank, 2)
        np.testing.assert_allclose(split.Vp.T @ split.Vrem, 0., atol=1e-13)
        np.testing.assert_allclose(split.Vp @ split.Vp.T + split.Vrem @ split.Vrem.T, np.eye(4), atol=1e-13)
        np.testing.assert_allclose(split.D @ A @ split.Vrem, 0., atol=1e-13)
        expected_shrinkage = np.diag(singular[:2]**2 / (singular[:2]**2 + lam))
        np.testing.assert_allclose(split.D @ A @ split.Vp, expected_shrinkage, atol=1e-12)
        expected_noise_gain = max(singular[:2] / (singular[:2]**2 + lam))
        self.assertAlmostEqual(split.certificate['noise_gain'], expected_noise_gain, places=12)
        self.assertEqual(split.certificate['regularization'], lam)
        self.assertFalse(split.certificate['full_model_certified'])
        self.assertEqual(split.certificate['certificate_type'], 'empirical_indicator')
        self.assertEqual(split.eligibility, ['finite_amplitude_unvalidated'] * 2)

    def test_rectangular_split_keeps_material_null_space_in_full_nuisance(self):
        A = np.array([[2., 0., 0.], [0., 1., 0.]])
        split = build_split({'AW': A}, {}, rank=1)
        self.assertEqual(split.Vp.shape, (3, 1))
        self.assertEqual(split.Vrem.shape, (3, 2))
        full = np.column_stack((split.Vp, split.Vrem))
        np.testing.assert_allclose(full.T @ full, np.eye(3), atol=1e-13)
        np.testing.assert_allclose(full @ full.T, np.eye(3), atol=1e-13)
        np.testing.assert_allclose(split.D @ A @ split.Vrem, 0., atol=1e-12)

    def test_zero_model_split_remains_invalid_and_unresolved(self):
        split = build_split({'AW': np.zeros((4, 4))}, {}, rank=2)
        self.assertEqual(split.status, 'INVALID_BLOCK')
        self.assertEqual(split.certificate['sigma_min'], 0.)
        self.assertEqual(split.eligibility, ['model_unresolved'] * 2)

    def test_internal_factor_gauge_preserves_product_and_material_split(self):
        rng = np.random.default_rng(202610072)
        O = rng.normal(size=(7, 5))
        P = rng.normal(size=(5, 5))
        M = rng.normal(size=(5, 4))
        left, _ = np.linalg.qr(rng.normal(size=(5, 5)))
        right, _ = np.linalg.qr(rng.normal(size=(5, 5)))
        A = O @ P @ M
        transformed = (O @ left.T) @ (left @ P @ right.T) @ (right @ M)
        np.testing.assert_allclose(transformed, A, atol=2e-13)
        old = build_split({'AW': A}, {}, rank=2)
        new = build_split({'AW': transformed}, {}, rank=2)
        np.testing.assert_allclose(old.Vp @ old.Vp.T, new.Vp @ new.Vp.T, atol=2e-10)
        np.testing.assert_allclose(old.Vp @ old.D, new.Vp @ new.D, atol=2e-10)
        self.assertAlmostEqual(old.certificate['noise_gain'], new.certificate['noise_gain'], places=9)

    def test_real_coordinate_gauge_preserves_projector_and_lifted_decoder(self):
        rng = np.random.default_rng(202610073)
        A = np.vstack((np.diag([3., 3., 1., .2]), np.zeros((2, 4))))
        rotation, _ = np.linalg.qr(rng.normal(size=(4, 4)))
        old = build_split({'AW': A}, {}, rank=2)
        new = build_split({'AW': A @ rotation}, {}, rank=2)
        lifted = rotation @ new.Vp
        np.testing.assert_allclose(old.Vp @ old.Vp.T, lifted @ lifted.T, atol=2e-10)
        np.testing.assert_allclose(old.Vp @ old.D, lifted @ new.D, atol=2e-10)


class RestrictedMaterialQuadraticChecks(unittest.TestCase):
    def test_general_real_32_coordinate_basis_mixes_re_im_and_keeps_physical_bounds(self):
        cells = 32
        chart = _PairedChart(cells, volume=.125)
        angles = np.r_[np.full(cells // 2, np.pi / 4), np.full(cells // 2, -np.pi / 4)]
        basis = np.zeros((chart.d, cells))
        for index, angle in enumerate(angles):
            basis[index, index] = np.cos(angle)
            basis[cells + index, index] = np.sin(angle)
        A = np.eye(cells)
        data = np.r_[-np.ones(cells // 2), np.ones(cells // 2)]
        chi0 = np.full(cells, .1 + .04j)
        lam = .05
        config = {'feasibility_tolerance': 1e-8, 'qp_kkt_rtol': 1e-8, 'qp_maxiter': 300}
        book = _Book()
        step, audit, normal = constrained_material_solve(A, data, chart, chi0, config, book, basis=basis, lam=lam)
        coefficients = basis.T @ step
        # The diagonal data quadratic has independent scalar coordinates, but
        # each scalar controls both real and imaginary material components.
        real_lower = (-.5 - chi0.real) * np.sqrt(chart.volume)
        imag_lower = -chi0.imag * np.sqrt(chart.volume)
        low = real_lower / np.cos(angles)
        high = np.full(cells, np.inf)
        positive = np.sin(angles) > 0
        low[positive] = np.maximum(low[positive], imag_lower[positive] / np.sin(angles[positive]))
        high[~positive] = imag_lower[~positive] / np.sin(angles[~positive])
        reference = np.minimum(np.maximum(data / (1 + lam), low), high)
        np.testing.assert_allclose(coefficients, reference, atol=2e-8)
        np.testing.assert_allclose(step, basis @ coefficients, atol=2e-12)
        material = chi0 + chart.expand(step)
        self.assertGreaterEqual(float(np.min(material.real)), -.5 - 3e-8)
        self.assertGreaterEqual(float(np.min(material.imag)), -3e-8)
        np.testing.assert_allclose((A.T @ A + lam * np.eye(cells)) @ coefficients - A.T @ data + normal, 0., atol=2e-7)
        self.assertTrue(audit['no_post_clipping'])
        self.assertTrue(audit['no_jitter_or_pseudoinverse'])
        self.assertEqual(audit['lambda_value'], lam)
        self.assertLessEqual(audit['kkt_relative'], config['qp_kkt_rtol'])
        self.assertEqual(book.counts['material_subproblems'], 1)

    def test_failed_kkt_validation_is_not_rescued_by_jitter_or_pseudoinverse(self):
        chart = _PairedChart(1)
        lam = .125
        config = {'feasibility_tolerance': 1e-8, 'qp_kkt_rtol': 1e-8}
        # Inject a wrong unconstrained linear solution. It is feasible but
        # nonstationary; objective termination or an added ridge cannot accept it.
        with mock.patch.object(core.la, 'solve', return_value=np.zeros(2)) as solve:
            with mock.patch.object(core.la, 'pinv', side_effect=AssertionError('pseudoinverse rescue is forbidden')):
                with self.assertRaises(core.QPFailure) as caught:
                    constrained_material_solve(np.eye(2), np.ones(2), chart,
                                               np.array([.1 + .1j]), config, _Book(), lam=lam)
        self.assertEqual(solve.call_count, 1)
        audit = caught.exception.result
        self.assertGreater(audit['kkt_relative'], config['qp_kkt_rtol'])
        self.assertEqual(audit['lambda_value'], lam)
        self.assertTrue(audit['no_jitter_or_pseudoinverse'])


class DirectionSelectionChecks(unittest.TestCase):
    def test_selection_is_deterministic_and_independent_of_truth_or_recovery_labels(self):
        rng = np.random.default_rng(202610074)
        A = rng.normal(size=(40, 32))
        first = choose_directions(A, descriptors={'truth': np.zeros(32), 'true_error': np.zeros(32), 'recovery_labels': np.arange(32)}, count=8)
        second = choose_directions(A, descriptors={'truth': rng.normal(size=32), 'true_error': np.full(32, 1e6), 'recovery_labels': np.arange(31, -1, -1)}, count=8)
        self.assertEqual(len(first), 8)
        self.assertEqual([row['candidate_index'] for row in first], [row['candidate_index'] for row in second])
        for a, b in zip(first, second):
            np.testing.assert_array_equal(a['v'], b['v'])
            self.assertFalse(a['selection_uses_labels'])
            self.assertIn(a['origin'], ('canonical_patch', 'small_A_SVD'))
            self.assertAlmostEqual(np.linalg.norm(a['v']), 1., places=12)

    def test_rectangular_candidate_pool_does_not_index_absent_svd_vectors(self):
        A = np.array([[3., 0., 0., 0.], [0., 2., 0., 0.], [0., 0., 1., 0.]])
        selected = choose_directions(A, count=4)
        self.assertEqual(len(selected), 4)
        for row in selected:
            self.assertEqual(row['v'].shape, (4,))
            self.assertTrue(np.isfinite(row['v']).all())
            self.assertFalse(row['selection_uses_labels'])


if __name__ == '__main__':
    unittest.main()
