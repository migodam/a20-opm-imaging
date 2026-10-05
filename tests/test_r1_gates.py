"""Registered gate/cost/provenance edge cases; synthetic scalars, no physics."""
from copy import deepcopy
import csv
import importlib.util
import json
import sys
import types
from unittest.mock import patch
from pathlib import Path
import tempfile
import unittest

from a20_r1.gates import (DEFAULT_PARENTS, PHASE2_PARENTS, evaluate_anatomy,
                          evaluate_closed_loop, evaluate_history)
from a20_r1.report import rank_action_matching, write_report


def anatomy_fixture():
    rows = []
    for p in DEFAULT_PARENTS:
        for state, iteration in (("early", 0), ("late", 17)):
            for method in ("FIXED-DEEP", "WIDE-M", "CHEAP-TASK", "ORACLE-M"):
                error = ({"FIXED-DEEP": 1., "WIDE-M": .2, "CHEAP-TASK": .25, "ORACLE-M": .2}
                         if state == "late" else {"FIXED-DEEP": .1, "WIDE-M": .1, "CHEAP-TASK": .03, "ORACLE-M": .1})[method]
                rows.append(dict(record_kind="method", method=method, parent_id=p,
                                 state=state, iteration=iteration, status="OK",
                                 reference_valid=True, QP_valid=True,
                                 reference_H_norm_squared=2., H_denominator_floor_used=False,
                                 relative_H_step_error=error, actual_rank=56,
                                 baseline_H_error=1. if state == "late" else .1,
                                 action_fourtuple=[4, 4, 6, 6],
                                 oracle_material_span_capture=1., oracle_qM_source_capture=1.,
                                 oracle_finalZ_source_capture=1., oracle_capture_certified=True))
            rows.append(dict(record_kind="method", method="HISTORY", parent_id=p,
                             state=state, iteration=iteration, status="NOT_RUN"))
    return rows


def protected_fixture(rows, oracle=.2, control=.8):
    for r in rows:
        if r["method"] == "ORACLE-M" and r["state"] == "late":
            r.update(oracle_qM_source_capture=.8, oracle_capture_certified=False)
    original = [r for r in rows if r["method"] == "ORACLE-M"]
    for r in original:
        for method, error in (("PROTECTED-ORACLE", oracle), ("PROTECTED-RANDOM", control)):
            value = dict(r, method=method, relative_H_step_error=error,
                         oracle_qM_source_capture=1., oracle_capture_certified=True,
                         allocation={"O": 3, "P": 3, "M": 6, "degree": 3})
            rows.append(value)
    return rows


def loop_fixture():
    rows = []
    for p in PHASE2_PARENTS:
        for name in ("FULL_GN", "FIXED_OPM", "WIDE-M"):
            adaptive = name == "WIDE-M"
            rows.append(dict(record_kind="run_summary", parent_id=p, method=name,
                             status="OK", QP_valid=True,
                             material_error=.7 if adaptive else 1.,
                             full_objective=11. if adaptive else 10., full_KKT=1e-6,
                             physical_vector_RHS=40 if adaptive else 100,
                             deployment_wall_seconds=12. if adaptive else 10., LU_factorizations=2))
    return rows


class AnatomyGates(unittest.TestCase):
    def setUp(self):
        self.rows = anatomy_fixture()
        self.config = {"parents": list(DEFAULT_PARENTS), "replay_iterations": [0, 17]}

    def gate(self):
        return evaluate_anatomy(self.rows, self.config)

    def change(self, method, state="late", parent=None, **values):
        for r in self.rows:
            if r["method"] == method and r["state"] == state and (parent is None or r["parent_id"] == parent):
                r.update(values)

    def test_complete_A_B_C_and_legal_selection(self):
        g = self.gate()
        self.assertEqual(g["status"], "PASS")
        self.assertEqual(g["selected_method"], "WIDE-M")
        self.assertEqual(g["HISTORY"]["status"], "NOT_RUN_NO_OWN_ACCEPTED_TRAJECTORY")

    def test_oracle_and_history_never_winner(self):
        self.change("ORACLE-M", relative_H_step_error=0.)
        self.change("HISTORY", relative_H_step_error=0., status="OK")
        self.assertEqual(self.gate()["selected_method"], "WIDE-M")

    def test_untriggered_certified_raw_negative_is_legal_kill(self):
        self.change("ORACLE-M", relative_H_step_error=.6)
        g = self.gate()
        self.assertEqual(g["status"], "KILL")
        self.assertFalse(g["A"]["raw_compression_trigger"])
        self.assertEqual(g["mechanism_status"], "C_CERTIFIED_ORACLE_NEGATIVE_KILL")

    def test_negative_rank_difference_three_is_inconclusive(self):
        self.change("ORACLE-M", relative_H_step_error=.6)
        self.change("FIXED-DEEP", actual_rank=53)
        self.assertEqual(self.gate()["mechanism_status"], "D_INCONCLUSIVE")

    def test_incomplete_late_does_not_average_four_survivors(self):
        self.rows = [r for r in self.rows if not (r["method"] == "ORACLE-M" and r["state"] == "late" and r["parent_id"] == DEFAULT_PARENTS[-1])]
        g = self.gate()
        self.assertEqual(g["A"]["status"], "HOLD")
        self.assertIsNone(g["A"]["operative_quality"]["median_H_error"])

    def test_qp_failure_and_missing_reference_are_separate(self):
        self.change("ORACLE-M", parent=DEFAULT_PARENTS[0], status="FAILED", QP_valid=False,
                    reference_valid=False, fullfallback_used=True, relative_H_step_error=0.)
        c = self.gate()["A"]["operative_cohort"]
        self.assertEqual(c["counts"]["method_QP_failed_or_unverified"], 1)
        self.assertEqual(c["counts"]["missing_or_invalid_reference"], 1)
        self.assertEqual(c["counts"]["method_failed"], 1)
        self.assertEqual(c["valid_parent_count"], 4)

    def test_zero_floor_or_tiny_reference_cannot_certify_kill(self):
        for energy, floor in ((0., False), (1e-25, False), (2., True)):
            with self.subTest(energy=energy, floor=floor):
                self.rows = anatomy_fixture()
                self.change("ORACLE-M", relative_H_step_error=.6, reference_H_norm_squared=energy,
                            H_denominator_floor_used=floor)
                self.assertEqual(self.gate()["mechanism_status"], "D_INCONCLUSIVE")

    def test_missing_actual_rank_is_hold(self):
        self.change("ORACLE-M", parent=DEFAULT_PARENTS[0], actual_rank=None)
        self.assertEqual(self.gate()["A"]["status"], "HOLD")

    def test_rank_over_cap_is_hold(self):
        self.change("ORACLE-M", actual_rank=57, relative_H_step_error=.6)
        self.assertEqual(self.gate()["mechanism_status"], "D_INCONCLUSIVE")

    def test_capture_requires_all_three_and_target_norm_valid(self):
        for values in (dict(oracle_material_span_capture=.99),
                       dict(oracle_finalZ_source_capture=.99),
                       dict(oracle_target_norm_floor_used=True)):
            with self.subTest(values=values):
                self.rows = anatomy_fixture()
                self.change("ORACLE-M", **values)
                self.assertEqual(self.gate()["A"]["status"], "HOLD")

    def test_duplicate_is_hold(self):
        self.rows.append(dict(next(r for r in self.rows if r["method"] == "ORACLE-M" and r["state"] == "late")))
        self.assertEqual(self.gate()["A"]["operative_cohort"]["counts"]["duplicate"], 1)

    def test_protected_requires_all_ten_state_pairs(self):
        protected_fixture(self.rows)
        self.rows = [r for r in self.rows if not (r["method"] == "PROTECTED-RANDOM" and r["state"] == "early" and r["parent_id"] == DEFAULT_PARENTS[0])]
        self.assertEqual(self.gate()["A"]["status"], "HOLD")

    def test_protected_operative_not_better_of_raw_and_protected(self):
        self.change("ORACLE-M", relative_H_step_error=.01)
        protected_fixture(self.rows, oracle=.6, control=.9)
        g = self.gate()
        self.assertEqual(g["A"]["operative_method"], "PROTECTED-ORACLE")
        self.assertEqual(g["A"]["raw_quality"]["status"], "PASS")
        self.assertEqual(g["status"], "KILL")

    def test_protected_positive_needs_same_allocation_random_contrast(self):
        protected_fixture(self.rows)
        self.assertEqual(self.gate()["A"]["status"], "PASS")
        self.change("PROTECTED-RANDOM", allocation={"O": 4, "P": 4, "M": 4, "degree": 3})
        self.assertEqual(self.gate()["mechanism_status"], "D_INCONCLUSIVE")

    def test_protected_quality_without_information_contrast_is_hold(self):
        protected_fixture(self.rows, oracle=.2, control=.3)
        self.assertEqual(self.gate()["A"]["operative_quality"]["status"], "PASS")
        self.assertEqual(self.gate()["A"]["protected_attribution"]["status"], "HOLD")

    def test_zero_control_error_does_not_manufacture_reduction(self):
        protected_fixture(self.rows, oracle=0., control=0.)
        self.assertEqual(self.gate()["A"]["protected_attribution"]["reduced_parent_count"], 0)
        self.assertEqual(self.gate()["A"]["status"], "HOLD")

    def test_complete_five_early_is_required_for_same_candidate(self):
        self.rows = [r for r in self.rows if not (r["method"] in ("WIDE-M", "CHEAP-TASK") and r["state"] == "early" and r["parent_id"] == DEFAULT_PARENTS[0])]
        self.assertIsNone(self.gate()["selected_method"])

    def test_candidate_tie_uses_complete_actions_then_stable_id(self):
        self.change("CHEAP-TASK", relative_H_step_error=.2)
        self.change("CHEAP-TASK", action_fourtuple=None)
        self.assertEqual(self.gate()["selected_method"], "WIDE-M")
        self.change("CHEAP-TASK", action_fourtuple=[1, 1, 1, 1])
        self.assertEqual(self.gate()["selected_method"], "CHEAP-TASK")
        self.change("WIDE-M", action_fourtuple=[1, 1, 1, 1])
        self.assertEqual(self.gate()["selected_method"], "CHEAP-TASK")

    def test_shared_rows_do_not_become_failed_experiments(self):
        self.rows.extend([dict(record_kind="reference", method="ORACLE-M", parent_id=2001,
                               state="late", status="FAILED"),
                          dict(record_kind="shared_geometry", status="FAILED")])
        self.assertEqual(self.gate()["status"], "PASS")


class ClosedLoopGates(unittest.TestCase):
    def test_vector_branch_pass_with_wall_fail(self):
        g = evaluate_closed_loop(loop_fixture(), {}, "WIDE-M")
        self.assertEqual(g["status"], "PASS")
        self.assertTrue(g["vector_branch_pass"])
        self.assertFalse(g["wall_branch_pass"])

    def test_wall_branch_or_does_not_require_vector_success(self):
        rows = loop_fixture()
        for r in rows:
            if r["method"] == "WIDE-M":
                r.update(physical_vector_RHS=90, deployment_wall_seconds=8., LU_factorizations=3)
        g = evaluate_closed_loop(rows, {}, "WIDE-M")
        self.assertEqual(g["status"], "PASS")
        self.assertTrue(g["wall_branch_pass"])
        self.assertFalse(g["vector_branch_pass"])

    def test_FULL_cost_comparison_does_not_change_FIXED_gate_denominator(self):
        rows = loop_fixture()
        for r in rows:
            if r["method"] == "FULL_GN":r.update(physical_vector_RHS=50, deployment_wall_seconds=20.)
        g = evaluate_closed_loop(rows, {}, "WIDE-M")
        self.assertEqual(g["status"], "PASS")
        self.assertEqual(g["deployment_gate_denominator_method"], "FIXED-DEEP")
        self.assertAlmostEqual(g["median_physical_vector_RHS_ratio"], .4)
        self.assertAlmostEqual(g["median_adaptive_FULL_physical_vector_RHS_ratio"], .8)
        self.assertAlmostEqual(g["median_adaptive_FULL_deployment_wall_ratio"], .6)

    def test_missing_parent_is_hold_without_partial_median(self):
        rows = [r for r in loop_fixture() if not (r["method"] == "WIDE-M" and r["parent_id"] == PHASE2_PARENTS[0])]
        g = evaluate_closed_loop(rows, {}, "WIDE-M")
        self.assertEqual(g["status"], "HOLD")
        self.assertIsNone(g["median_adaptive_FIXED_material_ratio"])

    def test_bad_single_parent_quality_or_kkt_fails(self):
        for value in (dict(full_objective=11.6), dict(full_KKT=1.2e-6), dict(material_error=1.16)):
            rows = loop_fixture()
            next(r for r in rows if r["method"] == "WIDE-M").update(value)
            self.assertEqual(evaluate_closed_loop(rows, {}, "WIDE-M")["status"], "FAIL")

    def test_attributed_replay_wall_is_not_deployment_wall(self):
        rows = loop_fixture()
        for r in rows:
            if r["method"] == "WIDE-M":
                r.pop("deployment_wall_seconds")
                r.pop("physical_vector_RHS")
                r.update(wall_total_attributed=1., action_fourtuple=[1, 1, 1, 1])
        self.assertEqual(evaluate_closed_loop(rows, {}, "WIDE-M")["status"], "HOLD")

    def test_oracle_closed_loop_not_allowed(self):
        self.assertEqual(evaluate_closed_loop(loop_fixture(), {}, "ORACLE-M")["status"], "NOT_RUN_GATE_CLOSED")

    def test_registered_material_floor_retained(self):
        rows = loop_fixture()
        for r in rows:
            r["material_error"] = 7e-7 if r["method"] == "WIDE-M" else 0.
        g = evaluate_closed_loop(rows, {}, "WIDE-M")
        self.assertEqual(g["material_floor"], 1e-6)
        self.assertAlmostEqual(g["median_adaptive_FIXED_material_ratio"], .7)

    def test_history_control_requires_own_information_and_allocation(self):
        rows = [r for r in loop_fixture() if r["method"] == "FULL_GN"]
        for p in PHASE2_PARENTS:
            for mode in ("ON", "OFF"):
                r = deepcopy(next(r for r in loop_fixture() if r["method"] == "FIXED_OPM" and r["parent_id"] == p))
                r.update(history_mode=mode, material_error=.7 if mode == "ON" else 1.,
                         allocation={"O": 4, "P": 4, "M": 4, "degree": 3}, own_history_validated=True)
                rows.append(r)
        self.assertEqual(evaluate_history(rows, {})["B"], "PASS")
        next(r for r in rows if r.get("history_mode") == "ON").pop("own_history_validated")
        self.assertEqual(evaluate_history(rows, {})["status"], "HOLD")

    def test_snapshot_history_not_own_history_ablation(self):
        self.assertEqual(evaluate_history(anatomy_fixture(), {})["status"], "NOT_RUN")


class StaticReport(unittest.TestCase):
    def test_fourtuple_not_aggregate_or_nominal_budget_matching(self):
        rows = anatomy_fixture()
        for r in rows:
            if r["method"] == "FIXED-DEEP":r["action_fourtuple"] = [100, 0, 0, 0]
            elif r["method"] == "WIDE-M":r["action_fourtuple"] = [0, 100, 0, 0]
        pairs = rank_action_matching(rows, {})
        wide = [r for r in pairs if r["method"] == "WIDE-M"]
        self.assertTrue(all(r["status"] == "ACTUAL_FOURTUPLE_NOT_MATCHED" for r in wide))

    def test_raw_csv_sources_history_and_budget_hooks(self):
        class Book:
            def __init__(self):self.checks = 0
            def check(self):self.checks += 1
        book = Book()
        with tempfile.TemporaryDirectory() as temp:
            result = write_report(temp, anatomy_fixture(), {}, book=book, make_figures=False)
            self.assertGreaterEqual(book.checks, 2)
            self.assertEqual(result["figure_status"], "NOT_RUN_FIGURES_DISABLED")
            self.assertEqual(result["closed_loop"]["status"], "NOT_RUN_NO_CLOSED_LOOP_ROWS")
            with (Path(temp)/"results/a20_r1/report/ANATOMY_RAW.csv").open() as handle:
                raw = list(csv.DictReader(handle))
            self.assertEqual(len(raw), 50)
            self.assertTrue(all(r["oracle_target_E_source_class"] == "OFFLINE_DIAGNOSTIC_ONLY" for r in raw if r["method"] == "ORACLE-M"))
            self.assertTrue(all(r["reported_HISTORY_status"] == "NOT_RUN_NO_OWN_ACCEPTED_TRAJECTORY" for r in raw if r["method"] == "HISTORY"))

    def test_closed_anatomy_reports_phase2_not_run_even_if_rows_supplied(self):
        rows = anatomy_fixture()
        rows = [r for r in rows if r["method"] != "ORACLE-M"]
        with tempfile.TemporaryDirectory() as temp:
            result = write_report(temp, rows, {}, closed_loop_rows=loop_fixture(), make_figures=False)
            self.assertEqual(result["closed_loop"]["status"], "NOT_RUN_GATE_CLOSED")

    def test_budget_stop_between_groups_propagates(self):
        class Book:
            def __init__(self):self.checks = 0
            def check(self):
                self.checks += 1
                if self.checks == 2:raise RuntimeError("FIXTURE_BUDGET_STOP")
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(RuntimeError, "FIXTURE_BUDGET_STOP"):
                write_report(temp, anatomy_fixture(), {}, book=Book(), make_figures=False)
            self.assertFalse((Path(temp)/"results/a20_r1/report/REPORT_MANIFEST.json").exists())

    def test_A_D_plot_groups_and_measured_axes_structure_only(self):
        class Axis:
            def __init__(self):
                self.calls = []
                self.transAxes = object()
            def __getattr__(self, name):
                def call(*args, **kwargs):
                    self.calls.append((name, args, kwargs))
                    return object() if name == "get_xaxis_transform" else None
                return call
        figures = []
        class Figure:
            def __init__(self):
                self.axes = []
                self.saved = []
                figures.append(self)
            def subplots(self, *args):
                n = args[0]*args[1] if len(args) == 2 else 1
                self.axes = [Axis() for _ in range(n)]
                return self.axes[0] if n == 1 else self.axes
            def savefig(self, path, **kwargs):self.saved.append(str(path))
            def clear(self):pass
            def text(self, *args, **kwargs):pass
            def suptitle(self, *args, **kwargs):pass
        with tempfile.TemporaryDirectory() as temp:
            with patch.dict(sys.modules, {"matplotlib": types.ModuleType("matplotlib")}), patch("a20_r1.report._new_figure", Figure):
                result = write_report(temp, anatomy_fixture(), {}, make_figures=True)
            self.assertEqual(set(result["figures"]), {"A", "B", "C", "D", "D_CAPTURE_CERT"})
            for paths in result["figures"].values():
                self.assertEqual({Path(p).suffix for p in paths}, {".png", ".svg"})
            self.assertTrue(all(len(f.saved) == 2 for f in figures))
            a_labels = next(args[1] for name,args,kw in figures[0].axes[0].calls if name == "set_xticks")
            self.assertIn("HISTORY", a_labels)
            self.assertTrue(any("PROTECTED-RANDOM" in value and "offline" in value for value in a_labels))
            self.assertEqual(len(figures[2].axes), 2)
            wide = next(args for name,args,kw in figures[3].axes[0].calls if name == "scatter" and kw.get("label") == "WIDE-M")
            self.assertEqual(wide[0], [1.]*5)
            self.assertEqual(wide[1], [.2]*5)
            manifest = json.loads((Path(temp)/"results/a20_r1/report/REPORT_MANIFEST.json").read_text())
            self.assertEqual(manifest["figure_status"], "GENERATED_RESEARCH_FIGURES")


if __name__ == "__main__":
    unittest.main()
