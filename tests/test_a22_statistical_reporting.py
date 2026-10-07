"""Tiny saved-evidence serialization checks; no physics or statistical fitting."""
import csv
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from a22.reporting import _statistical_plot_rows, generate_statistical_plots


def _evidence():
    return {
        "schema": "a22.statistics.evidence.v1", "mode": "screen",
        "methods": ["A0", "A1", "A2", "A3", "full_J", "full_J_total"],
        "evaluated_units": [{
            "scene_id": "2001", "direction_id": "d0", "amplitude": .1,
            "noise_level": 0.0, "intervention": "physics", "family": "gaussian",
            "evidence_scope": "deployable", "evaluation_split": "held_scene",
            "calibration_fold": "2001", "input_rows": 8, "invalid_rows": 0,
            "true_error": 2.0, "group_fields_complete": True,
            "raw_predictions": {"A0": 99.0, "A1": 77.0, "A2": 66.0, "A3": 55.0, "full_J": 44.0, "full_J_total": 33.0},
            "calibrated_predictions": {"A0": 1.0, "A1": 3.0, "A2": 4.0, "A3": 0.0, "full_J": 2.5, "full_J_total": 3.5},
            "method_eligible": {"A0": True, "A1": True, "A2": False, "A3": True, "full_J": True, "full_J_total": True},
            "paired_draw_rows": {"A0": 8, "A1": 8, "A2": 7, "A3": 8, "full_J": 8, "full_J_total": 8}}],
        "per_scene_statistics": [
            {"scene_id": "2001", "method": "A3", "family": "ALL", "noise_branch": "all",
             "evidence_scope": "deployable", "evaluation_split": "held_scene", "MAE": 12.0, "spearman": -.25},
            {"scene_id": "2001", "method": "A3", "family": "gaussian", "noise_branch": "all",
             "evidence_scope": "deployable", "evaluation_split": "held_scene", "MAE": 12.0, "spearman": -.25}],
        "calibration_scales": [{"method": "A3", "scale": .125, "fit_scene_ids": ["2003", "2009", "2014"]}],
        "summaries": [], "paired_scene_bootstrap": [], "primary_incrementality": None,
        "aggregated_units": [], "input_audit": {"historical_exposure": [{"value": "exposed", "count": 8}]}}


class StatisticalReportingTests(unittest.TestCase):
    def test_projection_keeps_saved_calibration_and_offline_scope(self):
        source = _evidence()
        before = json.dumps(source, sort_keys=True)
        rows = _statistical_plot_rows(source)
        self.assertEqual(len(rows), 6)
        a3 = next(row for row in rows if row["method"] == "A3")
        self.assertEqual(a3["calibrated_prediction"], 0.0)
        self.assertEqual(a3["raw_prediction"], 55.0)
        self.assertEqual(a3["input_rows"], 8)
        full = next(row for row in rows if row["method"] == "full_J")
        self.assertEqual(full["method_scope"], "offline_full_J")
        self.assertEqual(full["evidence_scope"], "deployable")
        full_total = next(row for row in rows if row["method"] == "full_J_total")
        self.assertEqual(full_total["method_scope"], "offline_full_J")
        self.assertEqual(full_total["calibrated_prediction"], 3.5)
        self.assertEqual(json.dumps(source, sort_keys=True), before)

    def test_export_uses_saved_statistics_without_raw_reducer(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch("a22.reporting._prediction_stats", side_effect=AssertionError("raw reducer forbidden")):
                result = generate_statistical_plots(root, _evidence(), make_plots=False)
            self.assertEqual(result["selectors"]["evaluation_split"], "held_scene")
            self.assertEqual(result["complete_calibrated_unit_method_pairs"], 5)
            self.assertEqual(result["saved_scene_statistic_rows"], 1)
            self.assertFalse(result["statistical_results_recomputed"])
            self.assertFalse(result["gate_decisions_evaluated_by_reporter"])
            with Path(result["rawdata"]["per_scene_statistics"]).open(newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(rows[0]["MAE"], "12.0")
            self.assertEqual(rows[0]["spearman"], "-0.25")
            self.assertEqual(result["figure_count"], 0)
            self.assertFalse((root / "A22_GATE_DECISION.md").exists())

    def test_missing_saved_evidence_is_not_raw_row_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            screen = root / "results" / "a22" / "screening"
            screen.mkdir(parents=True)
            (screen / "direction_metrics.csv").write_text("scene_id,true_error,pred_A3\n2001,2,2\n")
            result = generate_statistical_plots(root, make_plots=False)
            self.assertEqual(result["status"], "NOT_RUN")
            self.assertEqual(result["complete_calibrated_unit_method_pairs"], 0)
            self.assertEqual(result["saved_scene_statistic_rows"], 0)
            self.assertIn("missing", result["source_error"])
            with self.assertRaisesRegex(ValueError, "A22_STATISTICAL_INPUT"):
                generate_statistical_plots(root, root / "results" / "jobs" / "a21-old" / "STATISTICS_EVIDENCE.json", make_plots=False)


if __name__ == "__main__":
    unittest.main()
