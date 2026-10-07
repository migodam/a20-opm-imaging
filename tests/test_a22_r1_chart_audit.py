"""Synthetic chart-exterior audit tests; no physical action or experiment data."""

import csv
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import numpy as np

from a22_r1 import chart_audit
from a22_r1.replay import ReplayContractError, SCENES


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def make_fixture(root, *, zero_material=False):
    volume = 0.25
    Q = np.zeros((1728, 16))
    Q[:16] = 2 * np.eye(16)
    anchor = np.full(1728, 0.1 + 0.04j)
    base_coefficients = np.zeros(32)
    outside = np.zeros(1728, dtype=complex)
    if not zero_material:
        base_coefficients[[0, 16]] = [1.0, 0.5]
        outside[20] = 1.0 + 2.0j
    center = anchor + Q @ (base_coefficients[:16] + 1j * base_coefficients[16:]) + outside
    families = ("gaussian", "gaussian", "asymmetric", "shell")
    records = []
    for sid, family in zip(SCENES, families):
        online = root / "results/a22_r1/online"
        online.mkdir(parents=True, exist_ok=True)
        write_json(online / f"scene_{sid}.json", {"schema": "a22_r1.online_freeze.v1", "status": "COMPLETE"})
        # Object members are deliberate sentinels: loading these unused data,
        # score, or AW fields with allow_pickle=False would fail the test.
        np.savez(online / f"scene_{sid}.npz", Q_spatial=Q, anchor_chi=anchor,
                 cell_volume=np.asarray(volume), AW=np.asarray([{"unused": "AW"}], dtype=object),
                 score_A3=np.asarray([{"unused": "score"}], dtype=object))
        offline = root / "data/a22/offline_eval"
        offline.mkdir(parents=True, exist_ok=True)
        np.savez(offline / f"scene_{sid}.npz", truth=center)
        records.append(dict(scene_id=sid, family=family, source=f"scene_{sid}.npz", solver_n=12,
                            saved_truth_shape=[1728], data_generation_n_declared=14, online_use_allowed=False))
        old = root / f"results/a22/stage_a/scene_{sid}"
        old.mkdir(parents=True, exist_ok=True)
        for direction in range(4):
            for level in range(2):
                amplitude = 0.1 * (level + 1)
                perturbation = np.zeros(32)
                if not zero_material:
                    perturbation[direction] = amplitude
                    perturbation[16 + direction] = amplitude / 2
                np.savez(old / f"OFFLINE_label_d{direction}_a{level}.npz",
                    original_material=center, perturbation_coefficients=perturbation,
                    coefficients=base_coefficients + perturbation, amplitude=np.asarray(amplitude),
                    chart_Q=Q, anchor_material=anchor,
                    clean_data=np.asarray([{"unused": "clean data"}], dtype=object))
    write_json(root / "data/a22/offline_eval/MANIFEST.json", dict(
        schema="a22.offline_screening_evaluation.v1", capability="OFFLINE_EVALUATOR_ONLY",
        online_use_allowed=False, allowed_npz_members=["truth"], scene_ids=list(SCENES), scenes=records))
    write_json(root / "results/a22_r1/SPLIT_FREEZE.json", {
        "schema": "a22_r1.split_freeze.v1", "status": "COMPLETE", "scenes": list(SCENES)})
    return Q, volume, center


class PureChartDecompositionTests(unittest.TestCase):
    def test_mass_energy_projection_and_real_then_imaginary_coordinates(self):
        volume = 0.25
        Q = np.zeros((32, 16))
        Q[:16] = 2 * np.eye(16)
        delta = np.zeros(32, dtype=complex)
        delta[0] = 2 + 2j
        delta[16] = 4
        row, coefficients, outside = chart_audit._decomposition(delta, Q, volume)
        self.assertEqual(coefficients[0], 1)
        self.assertEqual(coefficients[16], 1)
        self.assertEqual(row["in_chart_energy"], 2)
        self.assertEqual(row["chart_exterior_energy"], 4)
        self.assertEqual(row["total_delta_energy"], 6)
        self.assertEqual(row["chart_retained_energy_fraction"], 1 / 3)
        self.assertEqual(row["chart_exterior_energy_fraction"], 2 / 3)
        self.assertEqual(outside[16], 4)
        self.assertTrue(row["identity_checks_pass"])
        self.assertEqual(row["outside_projected_coefficient_norm"], 0)
        self.assertEqual(row["mass_inner_product_inside_outside_abs"], 0)
        self.assertTrue(row["chart_exterior_is_not_in_chart_prior"])

    def test_rotated_mass_orthonormal_chart_preserves_energy_identity(self):
        rng = np.random.default_rng(20261913)
        Q, _ = np.linalg.qr(rng.normal(size=(40, 16)))
        Q = Q / np.sqrt(0.125)
        delta = rng.normal(size=40) + 1j * rng.normal(size=40)
        row, coefficients, outside = chart_audit._decomposition(delta, Q, 0.125)
        self.assertTrue(row["identity_checks_pass"])
        self.assertLess(row["mass_energy_identity_absolute_residual"], 1e-12)
        self.assertLess(row["outside_projected_coefficient_norm"], 1e-12)
        self.assertAlmostEqual(float(coefficients @ coefficients), row["in_chart_energy"])
        self.assertAlmostEqual(0.125 * float(np.vdot(outside, outside).real), row["chart_exterior_energy"])

    def test_zero_delta_keeps_energy_fractions_undefined(self):
        Q = np.eye(32)[:, :16]
        row, coefficients, _ = chart_audit._decomposition(np.zeros(32, dtype=complex), Q, 1.0)
        self.assertTrue(row["zero_delta_energy"])
        self.assertIsNone(row["chart_retained_energy_fraction"])
        self.assertIsNone(row["chart_exterior_energy_fraction"])
        self.assertIsNone(row["mass_energy_identity_relative_residual"])
        np.testing.assert_array_equal(coefficients, np.zeros(32))
        json.dumps(row, allow_nan=False)

    def test_invalid_mass_metric_dimensions_real_material_and_nonfinite_are_rejected(self):
        Q = np.eye(32)[:, :16]
        delta = np.ones(32, dtype=complex)
        invalid = [(delta, Q * 2, 1), (delta, Q[:, :8], 1), (delta, Q.astype(complex), 1),
                   (np.ones(32), Q, 1), (np.full(32, np.nan + 1j), Q, 1), (delta, Q, 0)]
        for args in invalid:
            with self.subTest(shapes=[np.shape(value) for value in args]), self.assertRaises(chart_audit.ChartAuditError):
                chart_audit._decomposition(*args)


class CachedChartAuditTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="a22-r1-chart-synthetic-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def test_global_barrier_precedes_all_chart_and_material_cache_reads(self):
        with mock.patch.object(chart_audit, "_read_truth") as truth:
            with mock.patch.object(chart_audit, "_online_chart") as online:
                with self.assertRaisesRegex(ReplayContractError, "FREEZE_REQUIRED_BEFORE_OFFLINE_READ"):
                    chart_audit.build_chart_audit(self.root)
                truth.assert_not_called()
                online.assert_not_called()

    def test_complete_fixture_writes_36_rows_and_retains_every_input_file(self):
        make_fixture(self.root)
        before = {path: path.read_bytes() for path in self.root.rglob("*") if path.is_file()}
        result = chart_audit.build_chart_audit(self.root)
        self.assertEqual(result["status"], "COMPLETE")
        self.assertEqual(result["raw_row_count"], 36)
        self.assertEqual(result["original_scene_count"], 4)
        self.assertEqual(result["finite_labels_per_scene"], 8)
        self.assertEqual(result["counts"]["finite_label_cache_reads"], 32)
        original_rows = [row for row in result["rows"] if row["kind"] == "ORIGINAL_SCENE_MATERIAL"]
        self.assertEqual(len(original_rows), 4)
        self.assertTrue(all(abs(row["chart_retained_energy_fraction"] - 0.5) < 1e-12 for row in original_rows))
        finite = [row for row in result["rows"] if row["kind"] == "FINITE_PERTURBATION_LABEL"]
        self.assertEqual(len(finite), 32)
        for row in finite:
            self.assertTrue(row["label_identity_checks_pass"])
            self.assertLess(row["stored_coefficient_projection_error_norm"], 1e-12)
            self.assertLess(row["perturbation_chart_exterior_energy"], 1e-25)
            self.assertLess(row["exterior_change_mass_norm"], 1e-12)
            self.assertIn("independent full perturbed material vector not cached", row["perturbed_material_origin"])
        for path, content in before.items():
            self.assertEqual(path.read_bytes(), content, str(path))
        created = {path.relative_to(self.root).as_posix() for path in self.root.rglob("*")
                   if path.is_file() and path not in before}
        self.assertEqual(created, {"results/a22_r1/CHART_EXTERIOR_RAW.json", "results/a22_r1/CHART_EXTERIOR_RAW.csv"})
        csv_rows = list(csv.DictReader(io.StringIO((self.root / result["artifacts"]["csv"]).read_text())))
        self.assertEqual(len(csv_rows), 36)
        self.assertEqual(json.loads((self.root / result["artifacts"]["json"]).read_text()), result)
        json.dumps(result, allow_nan=False)

    def test_matching_existing_raw_artifacts_are_reused_without_changes(self):
        make_fixture(self.root)
        first = chart_audit.build_chart_audit(self.root)
        paths = [self.root / path for path in first["artifacts"].values()]
        before = {path: path.read_bytes() for path in paths}
        second = chart_audit.build_chart_audit(self.root)
        self.assertEqual(first, second)
        for path, content in before.items():
            self.assertEqual(path.read_bytes(), content)

    def test_corrupted_stored_coefficients_produce_identity_mismatch_with_all_rows(self):
        make_fixture(self.root)
        path = self.root / "results/a22/stage_a/scene_2001/OFFLINE_label_d0_a0.npz"
        with np.load(path, allow_pickle=False) as archive:
            values = {name: archive[name].copy() for name in archive.files if name != "clean_data"}
        values["coefficients"][0] += 0.25
        np.savez(path, **values)
        result = chart_audit.build_chart_audit(self.root)
        self.assertEqual(result["status"], "IDENTITY_MISMATCH")
        self.assertEqual(len(result["rows"]), 36)
        failed = [row for row in result["rows"] if row.get("label_identity_checks_pass") is False]
        self.assertEqual(len(failed), 1)
        self.assertAlmostEqual(failed[0]["stored_coefficient_projection_error_norm"], 0.25)
        self.assertFalse(failed[0]["label_identity_checks"]["stored_coefficients_match_material_projection"])

    def test_changed_material_center_is_refused(self):
        make_fixture(self.root)
        path = self.root / "results/a22/stage_a/scene_2001/OFFLINE_label_d0_a0.npz"
        with np.load(path, allow_pickle=False) as archive:
            values = {name: archive[name].copy() for name in archive.files if name != "clean_data"}
        values["original_material"][30] += 0.2
        np.savez(path, **values)
        with self.assertRaisesRegex(chart_audit.ChartAuditError, "label.original_material"):
            chart_audit.build_chart_audit(self.root)

    def test_conflicting_existing_csv_is_not_overwritten(self):
        make_fixture(self.root)
        result = chart_audit.build_chart_audit(self.root)
        path = self.root / result["artifacts"]["csv"]
        path.write_text("conflicting frozen audit\n")
        with self.assertRaisesRegex(chart_audit.ChartAuditError, "EXISTING_RAW_CSV_CONFLICT"):
            chart_audit.build_chart_audit(self.root)
        self.assertEqual(path.read_text(), "conflicting frozen audit\n")

    def test_empty_original_and_finite_material_are_reported_without_fraction_epsilon(self):
        make_fixture(self.root, zero_material=True)
        result = chart_audit.build_chart_audit(self.root)
        self.assertEqual(result["status"], "COMPLETE")
        self.assertTrue(all(row["chart_retained_energy_fraction"] is None for row in result["rows"]))
        self.assertTrue(all(summary["finite_retained_energy_fraction_min"] is None
                            for summary in result["per_scene_summary"]))


if __name__ == "__main__":
    unittest.main()
