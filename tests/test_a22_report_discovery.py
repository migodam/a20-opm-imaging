"""Tiny file-discovery fixtures; plots, physics and statistics are not run."""
import csv
import json
from pathlib import Path
import tempfile
import unittest

from a22.reporting import generate_reports, generate_statistical_plots


def _csv(path, columns, row):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerow(row)


class ReportDiscoveryTests(unittest.TestCase):
    def test_raw_defaults_prefer_stage_a_for_metrics_and_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            a22 = root / "results/a22"
            for location, sid in ((a22, "root_old"), (a22 / "screening", "screen_old"),
                                  (a22 / "stage_a", "2001")):
                _csv(location / "direction_metrics.csv", ["scene_id", "true_error", "pred_A3", "evidence_scope"],
                     dict(scene_id=sid, true_error=2.0, pred_A3=1.0, evidence_scope="deployable"))
                _csv(location / "split_metrics.csv", ["scene_id", "status"], dict(scene_id=sid, status="TANGENT_CANDIDATE"))
                _csv(location / "scene_metrics.csv", ["scene_id", "status"], dict(scene_id=sid, status="STARTED"))
                _csv(location / "scene_manifest.csv", ["scene_id", "historical_exposure"],
                     dict(scene_id=sid, historical_exposure="historically_exposed_feasibility"))
            result = generate_reports(root, make_plots=False)
            self.assertEqual(result["direction_scenes"], ["2001"])
            coverage = {row[0]: row for row in result["source_coverage"]}
            for name in ("direction_metrics", "split_metrics", "scene_metrics", "scene_manifest"):
                self.assertEqual(Path(coverage[name][3]), a22 / "stage_a" / (name + ".csv"))
            self.assertFalse(result["gate_decisions_evaluated_by_reporter"])

    def test_statistical_defaults_prefer_canonical_statistics_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            a22 = root / "results/a22"
            for location, mode in ((a22, "formal"), (a22 / "screening", "formal"),
                                   (a22 / "statistics", "screen")):
                location.mkdir(parents=True, exist_ok=True)
                (location / "STATISTICS_EVIDENCE.json").write_text(json.dumps({
                    "schema": "a22.statistics.evidence.v1", "mode": mode, "methods": [],
                    "evaluated_units": [], "per_scene_statistics": [], "paired_scene_bootstrap": []}))
            result = generate_statistical_plots(root, make_plots=False)
            self.assertEqual(Path(result["source"]), a22 / "statistics/STATISTICS_EVIDENCE.json")
            self.assertEqual(result["selectors"]["evaluation_split"], "held_scene")
            self.assertEqual(result["figure_count"], 0)
            self.assertFalse(result["statistical_results_recomputed"])

    def test_missing_defaults_remain_not_run_at_canonical_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            raw = generate_reports(root, make_plots=False)
            direction = next(row for row in raw["source_coverage"] if row[0] == "direction_metrics")
            self.assertEqual(direction[1], "NOT_RUN")
            self.assertEqual(Path(direction[3]), root / "results/a22/stage_a/direction_metrics.csv")
            stats = generate_statistical_plots(root, make_plots=False)
            self.assertEqual(stats["status"], "NOT_RUN")
            self.assertEqual(Path(stats["source"]), root / "results/a22/statistics/STATISTICS_EVIDENCE.json")
            self.assertEqual(stats["complete_calibrated_unit_method_pairs"], 0)


if __name__ == "__main__":
    unittest.main()
