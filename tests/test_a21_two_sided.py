"""Small independent material-quadratic checks; no Maxwell state is opened."""
from __future__ import annotations

import itertools
import unittest
from unittest.mock import patch

import numpy as np
from scipy import linalg as la

from a21.diagnostics import ConsistencyFailure, evaluate


CONFIG = {"identity_rtol": 1e-9, "bound_roundoff_rtol": 1e-9,
          "qp_kkt_rtol": 1e-8, "feasibility_tolerance": 1e-8,
          "reference_H_norm_floor": 1e-12,
          "endpoint_denominator_epsilon_multiplier": 100,
          "scientific_H_error_target": .05}


def lower_qp(H, g, lower):
    """Enumerate all faces of a tiny lower-box QP, independently of A20."""
    p = len(g)
    candidates = []
    for flags in itertools.product((False, True), repeat=p):
        active = np.flatnonzero(flags)
        free = np.flatnonzero(np.logical_not(flags))
        s = np.array(lower, copy=True)
        if free.size:
            s[free] = la.solve(H[np.ix_(free, free)], -g[free]-H[np.ix_(free, active)]@s[active], assume_a="pos")
        gradient = H@s+g
        if np.min(s-lower) < -1e-11 or (active.size and np.min(gradient[active]) < -1e-10):
            continue
        if free.size and la.norm(gradient[free]) > 1e-9:
            continue
        mu = np.zeros(p)
        mu[active] = gradient[active]
        candidates.append((float(.5*s@H@s+g@s), s, {"normal": -mu, "multipliers": mu}))
    if not candidates:
        raise AssertionError("tiny enumerator found no feasible KKT point")
    _, step, audit = min(candidates, key=lambda value: value[0])
    return step, audit


def unconstrained(J, r, lam, ell):
    p = J.shape[1]
    regularizer = lam*np.eye(p) if np.ndim(lam) == 0 else lam
    s = -la.solve(J.T@J+regularizer, J.T@r+ell, assume_a="pos")
    return s, {"normal": np.zeros(p), "multipliers": np.zeros(p)}


class TwoSidedDiagnostics(unittest.TestCase):
    def evaluate(self, JF, JR, r, lam, ell, sF=None, sR=None, auditF=None, auditR=None,
                 *, A=None, lower=None, config=None):
        p = JF.shape[1]
        if sF is None:
            sF, auditF = unconstrained(JF, r, lam, ell)
        if sR is None:
            sR, auditR = unconstrained(JR, r, lam, ell)
        if lower is None:
            lower = np.full(p, -1e7)
        return evaluate(JF, JR, r, lam, ell, sF, sR, auditF, auditR, A, lower, CONFIG | (config or {}))

    def test_primal_exact_does_not_preserve_material_dual_or_step(self):
        JF = np.array([[1., 0.], [0., 1.], [0., 0.]])
        JR = np.array([[1., 0.], [0., 0.], [0., 1.]])
        r, ell = np.array([-2., 0., 8.]), np.zeros(2)
        metrics, vectors = self.evaluate(JF, JR, r, 1., ell)
        np.testing.assert_allclose(vectors["s_F"], [1., 0.], atol=1e-14)
        np.testing.assert_allclose(vectors["s_R"], [1., -4.], atol=1e-14)
        self.assertEqual(metrics["epsilon_P"], 0.)
        np.testing.assert_allclose(vectors["delta_d"], [0., 8.], atol=1e-14)
        self.assertEqual(float(vectors["e_F"]@vectors["delta_p"]), 0.)
        self.assertAlmostEqual(metrics["relative_H_step_error"], 4.)
        self.assertAlmostEqual(metrics["bound_ratio"], 1.)

    def test_pre_step_dual_interpolation_is_the_wrong_target(self):
        JF = np.array([[1., 0.], [0., 1.], [0., 0.]])
        JR = np.array([[1., 1.], [0., 1.], [0., 1.]])
        r, ell = np.array([-2., 0., 2.]), np.zeros(2)
        metrics, vectors = self.evaluate(JF, JR, r, 1., ell)
        np.testing.assert_allclose(JR.T@r, JF.T@r, atol=1e-14)
        np.testing.assert_allclose(JR@vectors["s_F"], JF@vectors["s_F"], atol=1e-14)
        np.testing.assert_allclose(vectors["delta_d"], [0., 1.], atol=1e-14)
        np.testing.assert_allclose(vectors["s_R"], [8/7, -2/7], atol=1e-14)
        self.assertAlmostEqual(metrics["relative_H_step_error"], np.sqrt(5)/7)

    def test_active_lower_box_gap_needs_normal_work(self):
        JF, JR, r, ell = np.ones((1, 1)), -np.ones((1, 1)), np.ones(1), np.zeros(1)
        lower = np.zeros(1)
        sF, auditF = lower_qp(JF.T@JF+np.eye(1), JF.T@r, lower)
        sR, auditR = lower_qp(JR.T@JR+np.eye(1), JR.T@r, lower)
        metrics, vectors = self.evaluate(JF, JR, r, 1., ell, sF, sR, auditF, auditR, lower=lower)
        self.assertAlmostEqual(metrics["full_quadratic_gap"], .75)
        self.assertAlmostEqual(.5*metrics["absolute_H_step_error"]**2, .25)
        self.assertAlmostEqual(metrics["normal_work"], .5)
        self.assertLess(metrics["full_gap_identity_error_norm"], 1e-14)
        self.assertIsNone(metrics["relative_H_step_error"])
        np.testing.assert_allclose(vectors["n_F"], [-1.], atol=1e-14)

    def test_full_gap_retains_nonzero_reference_solver_work(self):
        JF, JR, r, ell = np.ones((1, 1)), -np.ones((1, 1)), np.ones(1), np.zeros(1)
        eps = 2e-9
        sF, sR = np.array([eps]), np.array([.5+eps/4])
        auditF = {"normal": np.array([-1.]), "multipliers": np.array([1.])}
        auditR = {"normal": np.zeros(1), "multipliers": np.zeros(1)}
        metrics, vectors = self.evaluate(JF, JR, r, 1., ell, sF, sR, auditF, auditR, lower=np.zeros(1))
        d = sR-sF
        measured = .5*(r+JF@sR)@(r+JF@sR)+.5*sR@sR-(.5*(r+JF@sF)@(r+JF@sF)+.5*sF@sF)
        rhs = .5*d@vectors["H_F"]@d-vectors["n_F"]@d+vectors["rho_F"]@d
        self.assertGreater(abs(metrics["rhoF_work"]), 1e-10)
        self.assertAlmostEqual(measured, rhs, places=14)
        self.assertAlmostEqual(metrics["full_quadratic_gap"], rhs, places=14)
        self.assertFalse(metrics["normal_F_exact_at_roundoff"])

    def test_inexact_solvers_use_vector_defects_in_the_HR_bound(self):
        JF = np.array([[1., .4], [.3, .8], [0., .2]])
        JR = np.array([[.8, -.2], [.7, .5], [.1, .3]])
        r, ell, lam = np.array([-.5, 1., .7]), np.array([.1, -.2]), .3
        sF, auditF = unconstrained(JF, r, lam, ell)
        sR, auditR = unconstrained(JR, r, lam, ell)
        sF += np.array([1e-6, -2e-6])
        sR += np.array([-3e-6, 1e-6])
        metrics, vectors = self.evaluate(JF, JR, r, lam, ell, sF, sR, auditF, auditR,
                                         config={"qp_kkt_rtol": 1e-3})
        d = sR-sF
        direct = -(JR.T@JR+lam*np.eye(2))@d
        np.testing.assert_allclose(vectors["eta_pair"], direct, atol=1e-14)
        self.assertAlmostEqual(metrics["b_solver"], np.sqrt(d@vectors["H_R"]@d), places=13)
        self.assertGreater(metrics["rho_F_norm"], 0.)
        self.assertGreater(metrics["rho_R_norm"], 0.)
        self.assertTrue(metrics["bound_consistent"])

    def test_numerical_inactive_multiplier_has_a_separate_normal_allowance(self):
        J = np.zeros((1, 1))
        lower = np.array([.1])
        sF, sR = np.array([.1]), np.array([.1+1e-9])
        ell, r = np.array([.9]), np.zeros(1)
        auditF = {"normal": np.array([-1.]), "multipliers": np.array([1.])}
        auditR = {"normal": -(sR+ell), "multipliers": sR+ell}
        metrics, vectors = self.evaluate(J, J, r, 1., ell, sF, sR, auditF, auditR, lower=lower)
        self.assertLess(metrics["bound_HF"], 1e-14)
        self.assertGreater(metrics["absolute_H_step_error"], metrics["bound_HF"])
        expected = float(np.sum(abs(vectors["multipliers_F"]*vectors["slack_F"]))+
                         np.sum(abs(vectors["multipliers_R"]*vectors["slack_R"])))
        self.assertAlmostEqual(metrics["normal_allowance_energy"], expected, places=17)
        self.assertGreater(metrics["normal_adjusted_bound_HF"], metrics["absolute_H_step_error"])
        self.assertFalse(metrics["normal_R_exact_at_roundoff"])
        self.assertTrue(metrics["bound_consistent"])
        self.assertFalse(metrics["zero_feasible"])
        self.assertIsNone(metrics["predicted_reduction"])

    def test_linear_constraint_allowance_includes_both_cross_violations(self):
        eps = 1e-9
        A = np.array([[1., 0.], [0., 1.], [1., 1.]])
        J = np.eye(2)
        sF, sR = np.array([-eps, eps]), np.array([eps, -eps])
        mu = np.array([1., 1., 0.])
        audit = {"normal": -A.T@mu, "multipliers": mu}
        metrics, vectors = self.evaluate(J, J, np.zeros(2), 1., np.ones(2), sF, sR, audit, audit,
                                         A=A, lower=np.zeros(3))
        expected = (np.sum(abs(mu*vectors["slack_F"]))+np.sum(abs(mu*vectors["slack_R"]))+
                    np.sum(abs(mu))*metrics["feasibility_R"]+np.sum(abs(mu))*metrics["feasibility_F"])
        self.assertAlmostEqual(expected, 8*eps, places=17)
        self.assertAlmostEqual(metrics["normal_allowance_energy"], expected, places=17)

    def test_both_small_endpoint_ratios_can_have_large_curvature_amplification(self):
        eps = 1e-6
        JF = np.array([[1., 0.], [0., 1.], [0., 0.]])
        JR = np.array([[1., 0.], [0., 0.], [0., eps]])
        metrics, vectors = self.evaluate(JF, JR, np.array([-2., 0., 1.]), np.diag([1., eps**2]), np.zeros(2))
        self.assertEqual(metrics["epsilon_P"], 0.)
        self.assertAlmostEqual(metrics["epsilon_D"], eps, places=13)
        self.assertAlmostEqual(metrics["mu"], 2*eps**2, places=20)
        self.assertGreater(metrics["relative_H_step_error"], 3e5)
        np.testing.assert_allclose(vectors["s_R"], [1., -500000.], rtol=1e-13)
        self.assertTrue(metrics["bound_consistent"])
        self.assertLessEqual(metrics["absolute_H_step_error"], metrics["bound_HF"]*(1+1e-12))

    def test_zero_and_nearzero_denominators_remain_undefined(self):
        JF, JR = np.array([[1., 0.], [0., 0.]]), np.eye(2)
        metrics, _ = self.evaluate(JF, JR, np.array([0., 1.]), 1., np.zeros(2))
        self.assertIsNone(metrics["epsilon_P"])
        self.assertIsNone(metrics["epsilon_D"])
        self.assertIsNone(metrics["relative_H_step_error"])
        self.assertFalse(metrics["predicted_reduction_well_scaled"])
        self.assertIsNone(metrics["full_gap_over_predicted_reduction"])
        self.assertGreater(metrics["absolute_H_step_error"], 0.)
        tiny, _ = self.evaluate(np.ones((1, 1)), np.ones((1, 1)), np.array([-2e-13]), 1., np.zeros(1))
        self.assertFalse(tiny["well_scaled_reference"])
        self.assertIsNone(tiny["relative_H_step_error"])
        self.assertEqual(tiny["absolute_H_step_error"], 0.)
        self.assertTrue(tiny["no_denominator_floor_used"])

    def test_exact_interpolation_is_sufficient_but_not_necessary_under_constraints(self):
        JF, JR, r, ell = np.ones((1, 1)), 2*np.ones((1, 1)), np.ones(1), np.zeros(1)
        sF = sR = np.zeros(1)
        auditF = {"normal": np.array([-1.]), "multipliers": np.array([1.])}
        auditR = {"normal": np.array([-2.]), "multipliers": np.array([2.])}
        metrics, _ = self.evaluate(JF, JR, r, 1., ell, sF, sR, auditF, auditR, lower=np.zeros(1))
        self.assertEqual(metrics["absolute_H_step_error"], 0.)
        self.assertEqual(metrics["delta_d_norm"], 1.)
        self.assertTrue(metrics["normals_valid"])

    def test_invalid_normal_sign_representation_and_interior_work_are_rejected(self):
        J, r, ell, lower = np.ones((1, 1)), np.ones(1), np.zeros(1), np.zeros(1)
        good = {"normal": np.array([-1.]), "multipliers": np.array([1.])}
        bads = [({"normal": np.ones(1), "multipliers": np.ones(1)}, "REPRESENTATION"),
                ({"normal": np.ones(1), "multipliers": -np.ones(1)}, "SIGN"),
                ({"normal": -1.4*np.ones(1), "multipliers": 1.4*np.ones(1)}, "COMPLEMENTARITY")]
        for bad, message in bads:
            with self.subTest(message=message):
                sF = np.array([.2]) if message == "COMPLEMENTARITY" else np.zeros(1)
                with self.assertRaisesRegex(ConsistencyFailure, message):
                    self.evaluate(J, J, r, 1., ell, sF, np.zeros(1), bad, good, lower=lower)

    def test_unresolved_solver_and_nonpositive_curvature_are_rejected(self):
        J, r, ell = np.ones((1, 1)), np.array([-1.]), np.zeros(1)
        zero = {"normal": np.zeros(1), "multipliers": np.zeros(1)}
        with self.assertRaisesRegex(ConsistencyFailure, "KKT_INVALID"):
            self.evaluate(J, J, r, 1., ell, np.array([.2]), np.array([.5]), zero, zero)
        with self.assertRaisesRegex(ConsistencyFailure, "NON_SPD"):
            self.evaluate(np.zeros((1, 1)), np.zeros((1, 1)), np.zeros(1), 0., ell,
                          np.zeros(1), np.zeros(1), zero, zero)

    def test_bound_tripwire_rejects_a_fault_injected_inverse_energy(self):
        # A mathematically valid SPD problem cannot violate the certificate.
        # Deliberately corrupt the inverse-energy computation to ensure that
        # a measured violation is not silently promoted to a passing row.
        JF, JR, r, ell = np.ones((1, 1)), 2*np.ones((1, 1)), np.array([-1.]), np.zeros(1)
        with patch("a21.diagnostics.la.cho_solve", side_effect=lambda factor, value: np.zeros_like(value)):
            with self.assertRaisesRegex(ConsistencyFailure, "HF_INEQUALITY_VIOLATION") as context:
                self.evaluate(JF, JR, r, 1., ell)
        self.assertGreater(context.exception.details["error_HF"], 0.)
        self.assertEqual(context.exception.details["bound_HF"], 0.)


if __name__ == "__main__":
    unittest.main()
