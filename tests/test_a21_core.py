"""Tiny cached projection and report-gate checks; no Maxwell solve or truth."""
from __future__ import annotations

from contextlib import contextmanager
import itertools
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
from scipy import linalg as la

from a20.backend import MaterialChart, pack, unpack
from a20.material import kkt, solve_quadratic
from a20.opm import UnsafeCore
from a21.core import (AnatomyInputError, CachedJacobian, MatrixJacobian,
                      RankBudgetInfeasible, SharedBank, baseline_basis,
                      independent_addition_rank, ordered_protected_basis, random_bank)
from a21.diagnostics import evaluate
from a21.report import ARMS, annotate_rows, evaluate_report_gates, write_report


CONFIG = {"orthogonal_rank_rtol": 1e-10, "core_relative_sigma_floor": 1e-10,
          "core_absolute_scaled_sigma_floor": 1e-10, "core_condition_cap": 1e10,
          "qp_kkt_rtol": 1e-8, "qp_maxiter": 200, "feasibility_tolerance": 1e-8,
          "identity_rtol": 1e-9, "bound_roundoff_rtol": 1e-9,
          "reference_H_norm_floor": 1e-12, "backend_consistency_rtol": 1e-9,
          "endpoint_denominator_epsilon_multiplier": 100, "scientific_H_error_target": .05}


class TinyBook:
    """Count small cached work without physical setup or external outputs."""
    def __init__(self):
        from collections import Counter
        self.counts = Counter()
        self.events = []

    def check(self):
        pass

    @contextmanager
    def span(self, label, **counts):
        self.counts.update(counts)
        self.events.append(label)
        yield


def complex_normal(rng, shape):
    return (rng.normal(size=shape)+1j*rng.normal(size=shape))/np.sqrt(2.)


def direct_pack_sources(values):
    """Independent definition: each source's real channels, then imaginary."""
    return np.vstack([np.vstack((value.real, value.imag)) for value in values])


def lower_solution(H, g, lower):
    candidates = []
    p = len(g)
    for flags in itertools.product((False, True), repeat=p):
        active, free = np.flatnonzero(flags), np.flatnonzero(np.logical_not(flags))
        step = lower.copy()
        if len(free):
            step[free] = la.solve(H[np.ix_(free, free)], -g[free]-H[np.ix_(free, active)]@step[active], assume_a="pos")
        gradient = H@step+g
        if np.min(step-lower) < -1e-10 or (len(active) and np.min(gradient[active]) < -1e-10):
            continue
        if len(free) and la.norm(gradient[free]) > 1e-9:
            continue
        mu = np.zeros(p)
        mu[active] = gradient[active]
        candidates.append((float(.5*step@H@step+g@step), step, {"normal": -mu, "multipliers": mu}))
    if not candidates:
        raise AssertionError("independent enumerator found no KKT point")
    _, step, audit = min(candidates, key=lambda value: value[0])
    return step, audit


def fixture(seed=2106):
    rng = np.random.default_rng(seed)
    n, p, m, P, k = 24, 4, 5, 3, 10
    perturbation = complex_normal(rng, (n, n))
    L = np.eye(n)+.35*perturbation/la.norm(perturbation, 2)
    S = complex_normal(rng, (m, n))/np.sqrt(n)
    Bs = [complex_normal(rng, (n, p))/np.sqrt(n) for _ in range(P)]
    # Deliberately nonsymmetric, source-coupled real whitening detects whether
    # its transpose is used in the complex lifting of a data cotangent.
    whitening = np.eye(2*P*m)+.2*rng.normal(size=(2*P*m, 2*P*m))/np.sqrt(2*P*m)
    JF = whitening@direct_pack_sources([S@la.solve(L, B) for B in Bs])
    r, sf, lam = rng.normal(size=2*P*m), np.array([-.4, .2, .3, -.1]), .4
    normal = np.array([-.3, 0., 0., 0.])
    ell = -JF.T@(r+JF@sf)-lam*sf-normal
    eF = r+JF@sf
    lifted = whitening.T@eF
    ec = [lifted[a*2*m:a*2*m+m]+1j*lifted[a*2*m+m:(a+1)*2*m] for a in range(P)]
    X = np.column_stack([la.solve(L, B@sf) for B in Bs])
    Y = np.column_stack([la.solve(L.conj().T, S.conj().T@value) for value in ec])
    baseline = la.qr(complex_normal(rng, (n, n)), mode="economic")[0]
    U = baseline[:, :2]
    D = np.column_stack((U, X, Y, baseline[:, 2:]))
    bank = SharedBank(D=D, LD=L@D, SD=S@D,
                      DHB=np.stack([D.conj().T@B for B in Bs]),
                      whitening=whitening, L_scale=la.norm(L, 2),
                      parent_id=2001, source_count=P, data_channels=m)
    return dict(rng=rng, L=L, S=S, Bs=Bs, bank=bank, JF=JF, r=r, sf=sf, lam=lam,
                ell=ell, normal=normal, X=X, Y=Y, k=k, p=p, m=m, P=P,
                protected_primal=list(range(2+P)), protected_dual=list(range(2))+list(range(2+P, 2+2*P)),
                protected_both=list(range(2+2*P)), fillers=list(range(2+2*P, D.shape[1])))


class CachedCoreTests(unittest.TestCase):
    def basis(self, case, indices):
        return ordered_protected_basis(case["bank"].D, indices, case["fillers"], case["k"], retained_count=2)

    def test_real_packing_whitening_tied_adjoint_matches_independent_resolvent(self):
        case, book = fixture(), TinyBook()
        trial, test = self.basis(case, case["protected_primal"]), self.basis(case, case["protected_dual"])
        projection = case["bank"].project(trial, test, CONFIG, book)
        jacobian = CachedJacobian(case["bank"], projection)
        Z, W, L = trial.Z, test.Z, case["L"]
        R = Z@la.solve(W.conj().T@L@Z, W.conj().T)
        direct = case["bank"].whitening@direct_pack_sources([case["S"]@R@B for B in case["Bs"]])
        np.testing.assert_allclose(jacobian.matrix(), direct, rtol=2e-12, atol=2e-13)
        direction = case["rng"].normal(size=(case["p"], 3))
        cotangent = case["rng"].normal(size=(case["JF"].shape[0], 2))
        np.testing.assert_allclose(jacobian.action(direction), direct@direction, rtol=2e-12, atol=2e-13)
        np.testing.assert_allclose(jacobian.pullback(cotangent), direct.T@cotangent, rtol=2e-12, atol=2e-13)
        np.testing.assert_allclose(jacobian.pullback(cotangent[:, 0]), direct.T@cotangent[:, 0], rtol=2e-12, atol=2e-13)
        lhs, rhs = cotangent[:, 0]@jacobian.action(direction[:, 0]), direction[:, 0]@jacobian.pullback(cotangent[:, 0])
        self.assertAlmostEqual(lhs, rhs, places=12)
        current_rhs = complex_normal(case["rng"], (len(L), 3))
        np.testing.assert_allclose(projection.apply(current_rhs), R@current_rhs, rtol=2e-12, atol=2e-13)
        np.testing.assert_allclose(projection.adjoint(current_rhs), R.conj().T@current_rhs, rtol=2e-12, atol=2e-13)
        lifted = case["bank"].whitening.T@cotangent[:, 0]
        P, m = case["P"], case["m"]
        ec = [lifted[a*2*m:a*2*m+m]+1j*lifted[a*2*m+m:(a+1)*2*m] for a in range(P)]
        wrong = sum((B.T@R.T@case["S"].T@value).real for B, value in zip(case["Bs"], ec))
        self.assertGreater(la.norm(wrong-direct.T@cotangent[:, 0]), .01)
        self.assertEqual(book.counts["L_actions"], 0)
        self.assertEqual(projection.kind, "petrov")

    def test_source_permutation_requires_permuted_whitening_on_both_sides(self):
        case, book = fixture(), TinyBook()
        basis = self.basis(case, case["protected_both"])
        original = CachedJacobian(case["bank"], case["bank"].project(basis, basis, CONFIG, book)).matrix()
        permutation, P, m = np.array([2, 0, 1]), case["P"], case["m"]
        indices = np.arange(2*P*m).reshape(P, 2*m)[permutation].reshape(-1)
        Q = np.eye(2*P*m)[indices]
        bank = case["bank"]
        permuted = SharedBank(bank.D, bank.LD, bank.SD, bank.DHB[permutation],
                              Q@bank.whitening@Q.T, bank.L_scale, source_count=P, data_channels=m)
        result = CachedJacobian(permuted, permuted.project(basis, basis, CONFIG, book)).matrix()
        np.testing.assert_allclose(result, Q@original, rtol=2e-12, atol=2e-13)
        values = complex_normal(case["rng"], (P, m, 3))
        np.testing.assert_array_equal(pack(values[permutation]), Q@pack(values))
        np.testing.assert_array_equal(unpack(pack(values), P, m), values)
        # Keeping a source-coupled whitening fixed under reordered sources is
        # a detectable convention error, even if each single-source solve is sound.
        wrong = SharedBank(bank.D, bank.LD, bank.SD, bank.DHB[permutation], bank.whitening, bank.L_scale)
        wrong_result = CachedJacobian(wrong, wrong.project(basis, basis, CONFIG, book)).matrix()
        self.assertGreater(la.norm(wrong_result-Q@original), .01)

    def test_full_source_primal_dual_protection_preserves_constrained_G_and_PG_minimizer(self):
        case, book = fixture(), TinyBook()
        lower = np.full(case["p"], -.4)
        sF, auditF = lower_solution(case["JF"].T@case["JF"]+case["lam"]*np.eye(case["p"]), case["JF"].T@case["r"]+case["ell"], lower)
        np.testing.assert_allclose(sF, case["sf"], rtol=1e-12, atol=1e-13)
        self.assertGreater(auditF["multipliers"][0], 0.)
        both, primal, dual = [self.basis(case, case[key]) for key in ("protected_both", "protected_primal", "protected_dual")]
        for arm, trial, test in (("BOTH_G", both, both), ("BOTH_PG", primal, dual)):
            with self.subTest(arm=arm):
                projection = case["bank"].project(trial, test, CONFIG, book)
                JR = CachedJacobian(case["bank"], projection).matrix()
                sR, auditR = lower_solution(JR.T@JR+case["lam"]*np.eye(case["p"]), JR.T@case["r"]+case["ell"], lower)
                ef = case["r"]+case["JF"]@sF
                np.testing.assert_allclose(JR@sF, case["JF"]@sF, rtol=2e-11, atol=2e-13)
                np.testing.assert_allclose(JR.T@ef, case["JF"].T@ef, rtol=2e-11, atol=2e-13)
                np.testing.assert_allclose(sR, sF, rtol=2e-11, atol=2e-12)
                metrics, _ = evaluate(case["JF"], JR, case["r"], case["lam"], case["ell"], sF, sR, auditF, auditR, np.eye(case["p"]), lower, CONFIG)
                self.assertTrue(metrics["bound_consistent"])
                self.assertLess(metrics["relative_H_step_error"], 1e-8)
                self.assertGreater(la.norm(JR-case["JF"]), .01)
                self.assertFalse(np.allclose(JR.T@JR, case["JF"].T@case["JF"], rtol=1e-3, atol=1e-3))

    def test_same_constraint_QP_solver_agrees_with_independent_active_face_solution(self):
        case, book = fixture(), TinyBook()
        chart = MaterialChart(1., 2, np.eye(2), "gaussian")
        chi = np.array([-.1+.4j, -.1+.4j])
        step, result, normal = solve_quadratic(chart, chi, case["r"], MatrixJacobian(case["JF"]),
                                               case["lam"], case["ell"], CONFIG, book)
        np.testing.assert_allclose(step, case["sf"], rtol=1e-9, atol=1e-10)
        np.testing.assert_allclose(normal, case["normal"], rtol=1e-8, atol=1e-10)
        gradient = case["JF"].T@(case["r"]+case["JF"]@step)+case["lam"]*step+case["ell"]
        audit = kkt(chart, chi, step, gradient)
        self.assertLess(audit["stationarity_norm"], 1e-8)
        self.assertLess(audit["violation"], 1e-9)
        self.assertTrue(result["no_post_clipping"])

    def test_entire_source_bank_is_protected_before_large_fillers_and_rank_is_not_grown(self):
        eye = np.eye(8, dtype=complex)
        # Source 2 repeats source 0. Every independent direction, including a
        # small source direction, survives later high-energy baseline columns.
        sources = np.column_stack((eye[:, 2], 1e-8*eye[:, 3], eye[:, 2]))
        fillers = 1e8*eye[:, 4:]
        D = np.column_stack((eye[:, :2], sources, fillers))
        protected = list(range(5))
        basis = ordered_protected_basis(D, protected, list(range(5, 9)), 6, retained_count=2)
        residual = sources-basis.Z@(basis.Z.conj().T@sources)
        self.assertLess(la.norm(residual), 1e-14)
        self.assertEqual(basis.metadata["accepted_source_indices"], [0, 1, 2, 3])
        self.assertEqual(basis.metadata["accepted_filler_indices"], [5, 6])
        self.assertEqual(basis.metadata["retained_rank"], 2)
        self.assertEqual(basis.metadata["independent_protected_added_rank"], 2)
        self.assertEqual(independent_addition_rank(eye[:, :2], sources), 2)
        self.assertTrue(basis.metadata["protected_columns_never_truncated"])
        with self.assertRaisesRegex(RankBudgetInfeasible, "RANK_BUDGET") as context:
            ordered_protected_basis(D, protected, [], 3, retained_count=2)
        self.assertEqual(context.exception.details["protected_rank"], 4)
        with self.assertRaisesRegex(RankBudgetInfeasible, "INSUFFICIENT"):
            ordered_protected_basis(D[:, :5], protected, [], 5, retained_count=2)
        # Protecting the sum loses a source direction and is not equivalent.
        summed = np.sum(sources, axis=1, keepdims=True)
        self.assertEqual(independent_addition_rank(eye[:, :2], summed), 1)

    def test_ordered_QR_preserves_coordinates_and_frozen_filler_priority(self):
        rng = np.random.default_rng(91)
        D = complex_normal(rng, (14, 18))
        protected, fillers = [0, 3, 5], [9, 7, 6, 8, 10, 11]
        basis = ordered_protected_basis(D, protected, fillers, 6, retained_count=1)
        again = ordered_protected_basis(D, protected, fillers, 6, retained_count=1)
        np.testing.assert_array_equal(basis.Z, again.Z)
        np.testing.assert_array_equal(basis.T, again.T)
        np.testing.assert_allclose(D@basis.T, basis.Z, rtol=1e-12, atol=1e-13)
        np.testing.assert_allclose(basis.Z.conj().T@basis.Z, np.eye(6), rtol=1e-12, atol=1e-13)
        self.assertEqual(basis.metadata["accepted_source_indices"], protected)
        self.assertEqual(basis.metadata["accepted_filler_indices"], fillers[:3])
        with self.assertRaisesRegex(AnatomyInputError, "INDICES"):
            ordered_protected_basis(D, [0, 0], [], 2)

    def test_shared_operator_cache_is_reused_and_baseline_gauge_is_preserved(self):
        case, book = fixture(), TinyBook()
        bank = case["bank"]
        ids = [0, 1]+case["fillers"][:case["k"]-2]
        baseline = baseline_basis(bank, ids, retained_count=2)
        np.testing.assert_array_equal(baseline.Z, bank.D[:, ids])
        np.testing.assert_array_equal(bank.D@baseline.T, baseline.Z)
        shared_core = bank.DHDL.copy()
        for indices in (case["protected_primal"], case["protected_dual"], case["protected_both"]):
            basis = self.basis(case, indices)
            projection = bank.project(basis, basis, CONFIG, book)
            np.testing.assert_allclose(projection.A, basis.Z.conj().T@case["L"]@basis.Z, rtol=2e-12, atol=2e-13)
            np.testing.assert_allclose((bank.LD@basis.T), case["L"]@basis.Z, rtol=2e-12, atol=2e-13)
            jacobian = CachedJacobian(bank, projection)
            jacobian.matrix()
            before = dict(book.counts)
            jacobian.matrix()
            self.assertEqual(dict(book.counts), before)
        np.testing.assert_array_equal(bank.DHDL, shared_core)
        self.assertEqual(book.counts["L_actions"], 0)
        self.assertEqual(book.counts["full_forward_calls"], 0)
        self.assertEqual(book.counts["full_adjoint_calls"], 0)
        foreign = fixture(seed=2107)["bank"]
        with self.assertRaisesRegex(AnatomyInputError, "OWNER_MISMATCH"):
            CachedJacobian(foreign, projection)

    def test_singular_and_absolute_small_cores_are_failed_instances_without_fallback(self):
        book = TinyBook()
        eye = np.eye(5, dtype=complex)
        for label, L in (("singular", np.diag([1., 0., 1., 1., 1.])),
                         ("absolute-small", np.diag([1e-12, 1e-12, 1., 1., 1.]))):
            with self.subTest(label=label):
                bank = SharedBank(eye, L@eye, eye[:2], np.zeros((1, 5, 2), complex), 1., la.norm(L, 2))
                basis = ordered_protected_basis(eye, [0, 1], [], 2)
                with self.assertRaisesRegex(UnsafeCore, "UNSAFE") as context:
                    bank.project(basis, basis, CONFIG, book)
                self.assertFalse(context.exception.details["safe"])
        self.assertEqual(book.counts["petrov_fallbacks"], 0)
        self.assertEqual(book.counts["fullfallback_used"], 0)

    def test_wrong_source_counts_whitening_and_complex_material_are_rejected(self):
        case, book = fixture(), TinyBook()
        bank = case["bank"]
        with self.assertRaisesRegex(AnatomyInputError, "SOURCE"):
            SharedBank(bank.D, bank.LD, bank.SD, bank.DHB, bank.whitening, bank.L_scale, source_count=2)
        with self.assertRaisesRegex(AnatomyInputError, "WHITENING"):
            SharedBank(bank.D, bank.LD, bank.SD, bank.DHB, np.eye(3), bank.L_scale)
        basis = self.basis(case, case["protected_both"])
        jacobian = CachedJacobian(bank, bank.project(basis, basis, CONFIG, book))
        with self.assertRaisesRegex(AnatomyInputError, "REAL"):
            jacobian.action(np.ones(case["p"], complex))

    def test_random_controls_reproduce_frozen_independent_namespaces_without_global_RNG(self):
        seed = [20261006, 2001, 17, 2101]
        state = np.random.get_state()
        first = random_bank(18, 6, seed)
        repeat = random_bank(18, 6, seed)
        different_parent = random_bank(18, 6, [20261006, 2003, 17, 2101])
        different_trial = random_bank(18, 6, [20261006, 2001, 17, 2102])
        different_test = random_bank(18, 6, [20261006, 2001, 17, 2103])
        np.testing.assert_array_equal(first, repeat)
        self.assertEqual(first.dtype, np.complex128)
        self.assertEqual(first.shape, (18, 6))
        for other in (different_parent, different_trial, different_test):
            self.assertGreater(la.norm(first-other), 1.)
        after = np.random.get_state()
        self.assertEqual(state[0], after[0])
        np.testing.assert_array_equal(state[1], after[1])
        self.assertEqual(state[2:], after[2:])
        self.assertEqual(random_bank(18, 0, seed).shape, (18, 0))


def report_fixture():
    rows = []
    for parent in (2001, 2005, 2003, 2007, 2013):
        for arm in ARMS:
            error = .001 if arm in ("BOTH_G", "BOTH_PG") else .3
            rows.append({"parent_id": parent, "iteration": 17, "arm": arm, "status": "OK",
                         "reference_valid": True, "bound_consistent": True, "identity_relative_error": 1e-12,
                         "reference_H_norm": 1., "well_scaled_reference": True,
                         "relative_H_step_error": error, "absolute_H_step_error": error,
                         "core_safe": True, "tied_adjoint_error": 1e-12, "action_matrix_error": 1e-12, "pullback_matrix_error": 1e-12,
                         "reference_KKT_relative": 1e-12, "reduced_KKT_relative": 1e-12,
                         "normal_F_valid": True, "normal_R_valid": True,
                         "k_Z": 56, "k_W": 56, "retained_rank": 8,
                         "trial_QR": {"independent_protected_added_rank": 12},
                         "test_QR": {"independent_protected_added_rank": 12},
                         "b_dual": .3, "b_primal": 1e-12, "bound_HF": error*1.1,
                         "normal_allowance_bound_HF": 0., "normal_adjusted_bound_HF": error*1.1})
    return rows


class ReportEvidenceTests(unittest.TestCase):
    config = CONFIG | {"parents": [2001, 2005, 2003, 2007, 2013], "iterations": [17]}

    def gate(self, rows, t0=None):
        return evaluate_report_gates(annotate_rows(rows, self.config), self.config, t0=t0 or {"status": "PASS"})

    def test_all_five_consistent_causal_controls_needed_for_provisional_full_support(self):
        gate = self.gate(report_fixture())
        self.assertEqual(gate["status"], "FULL_MEASURED_SUPPORT_PENDING_CODEX_REVIEW")
        self.assertEqual(gate["final_scientific_status"], "CODEX_REVIEW_REQUIRED")
        self.assertEqual(gate["online_speedup"], "NOT_MEASURED_NO_CLAIM")

    def test_random_success_and_primal_success_preserve_alternative_explanations(self):
        rows = report_fixture()
        for row in rows:
            if row["arm"] in ("PRIMAL_G", "RANDOM_G"):
                row["relative_H_step_error"] = .001
        gate = self.gate(rows)
        self.assertEqual(gate["status"], "FIVE_STATE_FIDELITY_WITH_UNRESOLVED_CAUSAL_ATTRIBUTION")
        self.assertTrue(all(state["alternative_explanations"] for state in gate["T1"]["states"]))

    def test_missing_illscaled_unsafe_or_duplicate_state_is_never_averaged_away(self):
        for kind in ("missing", "illscaled", "unsafe", "duplicate"):
            with self.subTest(kind=kind):
                rows = report_fixture()
                target = next(row for row in rows if row["parent_id"] == 2013 and row["arm"] == "BOTH_G")
                if kind == "missing":
                    rows.remove(target)
                elif kind == "illscaled":
                    target.update(well_scaled_reference=False, reference_H_norm=1e-30)
                elif kind == "unsafe":
                    target.update(status="UNSAFE_CORE", core_safe=False)
                else:
                    rows.append(dict(target))
                complete = annotate_rows(rows, self.config)
                self.assertEqual(len(complete), 35)
                gate = evaluate_report_gates(complete, self.config, t0={"status": "PASS"})
                self.assertEqual(gate["status"], "PARTIAL_MEASURED_SUPPORT")
                self.assertFalse(gate["T1"]["all_five_BOTH_G_pass"])

    def test_T0_unresolved_and_consistency_failure_cannot_be_scientific_pass(self):
        self.assertEqual(self.gate(report_fixture(), {"status": "NOT_RUN"})["status"], "T0_UNRESOLVED")
        rows = report_fixture()
        rows[0].update(status="CONSISTENCY_FAILED", bound_consistent=False)
        self.assertEqual(self.gate(rows)["status"], "IMPLEMENTATION_INCONSISTENCY_STOP_AND_DEBUG")

    def test_not_run_to_one_terminal_result_is_lifecycle_but_two_executions_are_duplicate(self):
        rows = report_fixture()
        target = rows[-1]
        rows.insert(0, dict(target, status="NOT_RUN", job="a21-g-stage", run_id="registered-first"))
        completed = annotate_rows(rows, self.config)
        matching = next(row for row in completed if row["parent_id"] == target["parent_id"] and row["arm"] == target["arm"])
        self.assertTrue(matching["assessable"])
        self.assertEqual(len(matching["record_lifecycle"]), 2)
        self.assertEqual(matching["status"], "OK")
        rows.append(dict(target))
        matching = annotate_rows(rows, self.config)[-1]
        self.assertIn("DUPLICATE_STATE_ARM", matching["report_issue_classes"])

    def test_actual_engine_scalar_names_and_saved_cost_are_preserved(self):
        rows = report_fixture()
        row = rows[0]
        row["core"] = {"safe": row.pop("core_safe"), "condition": 2., "sigma_min": .5}
        row["tied_adjoint_relative_error"] = row.pop("tied_adjoint_error")
        row["action_matrix_relative_error"] = row.pop("action_matrix_error")
        row["pullback_matrix_relative_error"] = row.pop("pullback_matrix_error")
        row.pop("normal_F_valid")
        row.pop("normal_R_valid")
        row["normals_valid"] = True
        row["current_basis_memory_bytes"] = 1000
        row["cost"] = {"inclusive_wall_seconds": .2, "process_cpu_seconds": .1,
                       "counts": {"L_actions": 0}, "exclusive_walls": {"a21_arm_protected_QR": .03}}
        converted = annotate_rows(rows, self.config)[0]
        self.assertTrue(converted["assessable"])
        self.assertEqual(converted["core_condition"], 2.)
        self.assertEqual(converted["basis_memory_bytes"], 1000)
        self.assertEqual(converted["process_cpu_seconds"], .1)
        self.assertEqual(converted["total_wall_seconds"], .2)
        self.assertEqual(converted["QR_seconds"], .03)

    def test_claimed_T0_pass_still_requires_registered_backend_context(self):
        incomplete = {"status": "PASS", "synthetic": {"status": "PASS"}, "backend": {"2001": {"status": "PASS"}}}
        self.assertEqual(self.gate(report_fixture(), incomplete)["status"], "T0_UNRESOLVED")

    def test_nominal_rank_does_not_replace_independent_control_rank_or_retained_budget(self):
        rows = report_fixture()
        for row in rows:
            if row["arm"] == "RANDOM_G":
                row["trial_QR"]["independent_protected_added_rank"] = 11
        gate = self.gate(rows)
        self.assertEqual(gate["status"], "FIVE_STATE_FIDELITY_WITH_UNRESOLVED_CAUSAL_ATTRIBUTION")
        self.assertFalse(gate["T1"]["all_five_causal_pattern"])
        rows = report_fixture()
        for row in rows:
            if row["arm"] == "BOTH_G" and row["parent_id"] == 2001:
                row["k_Z"] = row["k_W"] = 57
        self.assertEqual(self.gate(rows)["status"], "PARTIAL_MEASURED_SUPPORT")

    def test_missing_output_report_writes_complete_blocked_table_without_physics(self):
        with tempfile.TemporaryDirectory(prefix="a21_report_fixture_") as temporary:
            root = Path(temporary)
            (root/"results/a21").mkdir(parents=True)
            (root/"results/a21/external_cpu_receipts.json").write_text("[]\n")
            result = write_report(root, self.config, make_figures=False)
            gate = result["gate_decision"]
            self.assertEqual(gate["expected_state_arm_count"], 35)
            self.assertEqual(gate["complete_output_count"], 0)
            self.assertEqual(gate["status"], "T0_UNRESOLVED")
            self.assertEqual(len(list((root/"results/a21/per_state").glob("*.json"))), 5)
            report = (root/"results/a21/A21_ORACLE_REPORT.md").read_text()
            self.assertLess(report.index("T0:"), report.index("T1:"))
            self.assertIn("MISSING_OUTPUT", report)
            self.assertIn("normal work", report)
            self.assertIn("ORACLE/OFFLINE", report)
            self.assertFalse(json.loads((root/"results/a21/REPORT_MANIFEST.json").read_text())["truth_access"])

    def test_available_NPZ_with_missing_diagnostic_vectors_cannot_pass_the_gate(self):
        with tempfile.TemporaryDirectory(prefix="a21_incomplete_vector_fixture_") as temporary:
            root = Path(temporary)
            anatomy = root/"results/a21/anatomy"
            (anatomy/"caches").mkdir(parents=True)
            (anatomy/"diagnostics").mkdir()
            rows = report_fixture()
            (anatomy/"rows.jsonl").write_text("".join(json.dumps(row)+"\n" for row in rows))
            (anatomy/"summary.json").write_text(json.dumps({"status": "COMPLETE", "T0": {"status": "PASS"}}))
            (root/"results/a21/external_cpu_receipts.json").write_text("[]\n")
            for parent in self.config["parents"]:
                np.savez(anatomy/"caches"/f"{parent}_17.npz", D=np.eye(2), LD=np.eye(2))
                for arm in ARMS:
                    np.savez(anatomy/"diagnostics"/f"{parent}_17_{arm}.npz", s_F=np.ones(2))
            result = write_report(root, self.config, make_figures=False)
            self.assertFalse(result["gate_decision"]["T1"]["all_five_BOTH_G_pass"])
            state = json.loads((root/"results/a21/per_state/2001_17.json").read_text())
            self.assertTrue(all("DIAGNOSTIC_VECTOR_SET_INCOMPLETE" in row["report_issue_classes"] for row in state["arms"]))


if __name__ == "__main__":
    unittest.main()
