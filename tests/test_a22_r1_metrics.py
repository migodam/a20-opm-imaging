"""Synthetic-only tests: never load A22 truth, reconstruction, or physics caches."""

import copy
import json
import unittest

import numpy as np

from a22_r1.metrics import (
    BOOTSTRAP_RESAMPLES,
    BOOTSTRAP_SEED,
    NORM_FLOOR,
    hierarchical_scene_average,
    paired_scene_bootstrap,
    subspace_metrics,
)


def split(k=16):
    return np.eye(32)[:, :k], np.eye(32)[:, k:]


def synthetic_conditions():
    return [
        {"direction": direction, "amplitude": 1.0, "noise": noise,
         "intervention": intervention}
        for direction in range(12)
        for noise in (0.0, 0.1)
        for intervention in ("baseline", "perturbed")
    ]


def synthetic_rows(scene=2001, zero_value=0.0, noisy_value=2.0, method="A3"):
    rows = []
    for condition in synthetic_conditions():
        for draw in range(1 if condition["noise"] == 0 else 16):
            rows.append({
                "scene": scene, "method": method, "k": 16, "test": "A",
                **condition, "noise_draw": draw,
                "nrmse_phys": zero_value if condition["noise"] == 0 else noisy_value,
            })
    return rows


def aggregate(rows, metrics=("nrmse_phys",), groups=None):
    return hierarchical_scene_average(
        rows, metrics, expected_conditions=synthetic_conditions(),
        expected_groups=groups,
    )


class SubspaceMetricTests(unittest.TestCase):
    def test_analytic_known_separation_and_raw_energy_selectivity(self):
        phys, prior = split()
        truth = np.zeros(32)
        truth[[0, 16]] = 1
        estimate = truth.copy()
        estimate[0] += 0.1
        estimate[16] += 0.4
        result = subspace_metrics(estimate, truth, phys, prior)
        self.assertAlmostEqual(result["nrmse_phys"], 0.1)
        self.assertAlmostEqual(result["nrmse_prior"], 0.4)
        self.assertAlmostEqual(result["s_sep"], 4)
        self.assertAlmostEqual(result["f_error_prior"], 16 / 17)
        self.assertAlmostEqual(result["f_truth_phys"], 0.5)
        self.assertAlmostEqual(result["q_phys"], 2 / 17)
        self.assertAlmostEqual(result["q_prior"], 32 / 17)
        self.assertTrue(result["q_identity_applicable"])
        self.assertLess(result["q_identity_residual"], 1e-12)
        self.assertEqual(result["undefined_reasons"], {})
        json.dumps(result, allow_nan=False)

    def test_energy_and_projector_conservation_in_rotated_32d_chart(self):
        rng = np.random.default_rng(92017)
        joint, _ = np.linalg.qr(rng.normal(size=(32, 32)))
        truth = rng.normal(size=32)
        error = rng.normal(size=32)
        for k in (8, 16):
            with self.subTest(k=k):
                result = subspace_metrics(truth + error, truth, joint[:, :k], joint[:, k:])
                for name in ("projector_completeness_residual", "signal_projection_identity_residual",
                             "error_projection_identity_residual", "signal_energy_identity_residual",
                             "error_energy_identity_residual", "q_identity_residual"):
                    self.assertLess(result[name], 1e-12)
                self.assertAlmostEqual(result["f_error_phys"] + result["f_error_prior"], 1)
                self.assertAlmostEqual(result["f_truth_phys"] + result["f_truth_prior"], 1)
                self.assertAlmostEqual(
                    result["s_sep"] ** 2, result["q_prior"] / result["q_phys"]
                )

    def test_frozen_random_subset_projection_matches_direct_coordinates(self):
        rng = np.random.default_rng(20261908)
        selected = np.sort(rng.choice(32, size=8, replace=False))
        remaining = np.setdiff1d(np.arange(32), selected)
        truth = rng.normal(size=32)
        error = rng.normal(size=32)
        result = subspace_metrics(truth + error, truth, np.eye(32)[:, selected],
                                  np.eye(32)[:, remaining])
        self.assertAlmostEqual(result["truth_phys_energy"], float(truth[selected] @ truth[selected]))
        self.assertAlmostEqual(result["error_prior_energy"], float(error[remaining] @ error[remaining]))
        self.assertAlmostEqual(result["nrmse_phys"], np.linalg.norm(error[selected]) /
                               np.linalg.norm(truth[selected]))

    def test_empty_signal_keeps_raw_fractions_and_q_undefined(self):
        phys, prior = split()
        truth = np.zeros(32)
        truth[16] = 1
        estimate = truth.copy()
        estimate[0] = 0.2
        estimate[16] += 0.3
        result = subspace_metrics(estimate, truth, phys, prior)
        self.assertTrue(result["floor_phys_active"])
        self.assertFalse(result["floor_prior_active"])
        self.assertEqual(result["truth_phys_norm"], 0)
        self.assertEqual(result["f_truth_phys"], 0)
        self.assertIsNone(result["q_phys"])
        self.assertAlmostEqual(result["nrmse_phys"], 0.2 / NORM_FLOOR)
        self.assertIsNone(result["q_identity_residual"])
        zero_truth = subspace_metrics(estimate, np.zeros(32), phys, prior)
        for name in ("f_truth_phys", "f_truth_prior", "q_phys", "q_prior"):
            self.assertIsNone(zero_truth[name])
        json.dumps(zero_truth, allow_nan=False)

    def test_zero_error_does_not_manufacture_error_fractions_or_separation(self):
        phys, prior = split()
        truth = np.ones(32)
        result = subspace_metrics(truth, truth, phys, prior)
        self.assertEqual(result["nrmse_phys"], 0)
        self.assertEqual(result["nrmse_prior"], 0)
        for name in ("s_sep", "f_error_phys", "f_error_prior", "q_phys", "q_prior"):
            self.assertIsNone(result[name])

    def test_zero_physics_error_leaves_selectivity_zero_and_separation_undefined(self):
        phys, prior = split()
        truth = np.ones(32)
        estimate = truth.copy()
        estimate[16:] += 0.3
        result = subspace_metrics(estimate, truth, phys, prior)
        self.assertEqual(result["q_phys"], 0)
        self.assertEqual(result["q_prior"], 2)
        self.assertIsNone(result["s_sep"])
        self.assertFalse(result["q_identity_applicable"])

    def test_norm_floor_flags_do_not_change_raw_energy_fractions(self):
        phys, prior = split()
        truth = np.zeros(32)
        truth[0] = NORM_FLOOR / 2
        truth[16] = 2 * NORM_FLOOR
        error = np.zeros(32)
        error[[0, 16]] = NORM_FLOOR
        result = subspace_metrics(truth + error, truth, phys, prior)
        self.assertTrue(result["floor_phys_active"])
        self.assertFalse(result["floor_prior_active"])
        self.assertEqual(result["nrmse_phys_denominator"], NORM_FLOOR)
        self.assertAlmostEqual(result["f_truth_phys"], 1 / 17)
        self.assertAlmostEqual(result["q_phys"], 17 / 2)
        self.assertFalse(result["q_identity_applicable"])
        truth[0] = NORM_FLOOR
        at_floor = subspace_metrics(truth + error, truth, phys, prior)
        self.assertFalse(at_floor["floor_phys_active"])
        self.assertTrue(at_floor["q_identity_applicable"])

    def test_restricted_branch_zero_prior_is_reported_without_filling_prior(self):
        phys, prior = split()
        truth = np.ones(32)
        estimate = np.zeros(32)
        estimate[:16] = 0.9
        result = subspace_metrics(estimate, truth, phys, prior)
        self.assertAlmostEqual(result["nrmse_phys"], 0.1)
        self.assertAlmostEqual(result["nrmse_prior"], 1)
        self.assertAlmostEqual(result["truth_phys_energy"], 16)
        self.assertAlmostEqual(result["error_prior_energy"], 16)

    def test_within_subspace_rotation_does_not_change_metrics(self):
        rng = np.random.default_rng(153)
        phys, prior = split()
        rphys, _ = np.linalg.qr(rng.normal(size=(16, 16)))
        rprior, _ = np.linalg.qr(rng.normal(size=(16, 16)))
        truth, estimate = rng.normal(size=(2, 32))
        original = subspace_metrics(estimate, truth, phys, prior)
        rotated = subspace_metrics(estimate, truth, phys @ rphys, prior @ rprior)
        for name in ("nrmse_phys", "nrmse_prior", "s_sep", "q_phys", "q_prior",
                     "f_error_prior", "f_truth_phys"):
            self.assertAlmostEqual(original[name], rotated[name])

    def test_invalid_chart_inputs_and_noncomplementary_bases_are_rejected(self):
        phys, prior = split()
        good = np.ones(32)
        invalid = [
            (np.ones(31), good, phys, prior),
            (good, np.ones((32, 1)), phys, prior),
            (good.astype(complex), good, phys, prior),
            (np.full(32, np.nan), good, phys, prior),
            (good, np.full(32, np.inf), phys, prior),
            (good, good, phys[:31], prior),
            (good, good, phys[:, :8], prior),
            (good, good, phys * 2, prior),
            (good, good, phys, phys),
            (good, good, phys, prior.astype(complex)),
        ]
        for args in invalid:
            with self.subTest(shapes=[np.shape(arg) for arg in args]):
                with self.assertRaises(ValueError):
                    subspace_metrics(*args)
        invalid_basis = phys.copy()
        invalid_basis[0, 0] = np.nan
        with self.assertRaises(ValueError):
            subspace_metrics(good, good, invalid_basis, prior)
        for value in (0, -1, np.nan, np.inf, True):
            with self.subTest(floor=value), self.assertRaises(ValueError):
                subspace_metrics(good, good, phys, prior, norm_floor=value)


class HierarchicalAverageTests(unittest.TestCase):
    def test_zero_and_16_draw_conditions_are_equally_weighted(self):
        rows = synthetic_rows()
        self.assertEqual(len(rows), 24 + 24 * 16)
        result = aggregate(rows)
        scene = result["scene_rows"][0]
        self.assertTrue(scene["complete"])
        self.assertEqual(scene["expected_condition_count"], 48)
        self.assertEqual(scene["nrmse_phys"], 1)
        self.assertNotAlmostEqual(scene["nrmse_phys"], np.mean([row["nrmse_phys"] for row in rows]))
        self.assertEqual(result["audit"]["missing_noise_draw_count"], 0)
        self.assertEqual(len(result["condition_rows"]), 48)

    def test_noise_draw_mean_is_taken_before_equal_condition_mean(self):
        rows = synthetic_rows()
        for row in rows:
            if row["noise"] != 0:
                row["nrmse_phys"] = float(row["noise_draw"])
        result = aggregate(rows)
        self.assertAlmostEqual(result["scene_rows"][0]["nrmse_phys"], 3.75)
        noisy_means = [row["nrmse_phys"] for row in result["condition_rows"] if row["noise"] != 0]
        self.assertTrue(all(value == 7.5 for value in noisy_means))

    def test_missing_replicate_disables_scene_mean_and_preserves_counts(self):
        rows = synthetic_rows()
        index = next(index for index, row in enumerate(rows) if row["noise"] != 0)
        rows.pop(index)
        result = aggregate(rows)
        self.assertFalse(result["scene_rows"][0]["complete"])
        self.assertIsNone(result["scene_rows"][0]["nrmse_phys"])
        self.assertEqual(result["audit"]["missing_noise_draw_count"], 1)
        self.assertEqual(result["audit"]["missing_condition_count"], 0)

    def test_failed_replicate_is_not_filtered_even_if_it_has_a_numeric_metric(self):
        rows = synthetic_rows()
        rows[0]["status"] = "FAILED"
        result = aggregate(rows)
        self.assertEqual(result["audit"]["failed_replicate_count"], 1)
        self.assertIsNone(result["scene_rows"][0]["nrmse_phys"])
        self.assertFalse(result["scene_rows"][0]["structurally_complete"])

    def test_unknown_status_or_numpy_failure_flag_cannot_create_complete_scene(self):
        for flag in ({"status": "solver_failed"}, {"failed": np.bool_(True)},
                     {"success": np.bool_(False)}):
            with self.subTest(flag=flag):
                rows = synthetic_rows()
                rows[0].update(flag)
                result = aggregate(rows)
                self.assertEqual(result["audit"]["failed_replicate_count"], 1)
                self.assertIsNone(result["scene_rows"][0]["nrmse_phys"])

    def test_undefined_or_nonfinite_metric_propagates_without_filtering(self):
        for undefined in (None, np.nan, np.inf):
            with self.subTest(undefined=undefined):
                rows = synthetic_rows()
                for row in rows:
                    row["q_phys"] = 0.5
                rows[0]["q_phys"] = undefined
                result = aggregate(rows, ("nrmse_phys", "q_phys"))
                scene = result["scene_rows"][0]
                self.assertTrue(scene["structurally_complete"])
                self.assertEqual(scene["nrmse_phys"], 1)
                self.assertIsNone(scene["q_phys"])
                self.assertEqual(scene["undefined_condition_counts"]["q_phys"], 1)
                self.assertFalse(scene["complete"])

    def test_missing_condition_and_entire_group_are_counted(self):
        rows = synthetic_rows()
        omitted = synthetic_conditions()[1]
        rows = [row for row in rows if not all(row[key] == value for key, value in omitted.items())]
        groups = [{"scene": scene, "method": "A3", "k": 16, "test": "A"}
                  for scene in (2001, 2003)]
        result = aggregate(rows, groups=groups)
        first, absent = result["scene_rows"]
        self.assertEqual(first["missing_condition_count"], 1)
        self.assertEqual(absent["missing_condition_count"], 48)
        self.assertEqual(absent["missing_noise_draw_count"], 24 + 24 * 16)
        self.assertIsNone(first["nrmse_phys"])
        self.assertIsNone(absent["nrmse_phys"])
        self.assertEqual(result["audit"]["missing_condition_count"], 49)

    def test_duplicate_draw_invalidates_group_without_double_weighting(self):
        rows = synthetic_rows()
        rows.append(copy.deepcopy(rows[0]))
        result = aggregate(rows)
        self.assertEqual(result["audit"]["duplicate_noise_draw_count"], 1)
        self.assertIsNone(result["scene_rows"][0]["nrmse_phys"])

    def test_explicit_noise_draw_counts_and_nested_metric_values(self):
        rows = synthetic_rows()
        for row in rows:
            row["metrics"] = {"nrmse_phys": row.pop("nrmse_phys")}
        result = hierarchical_scene_average(
            rows, ("nrmse_phys",), expected_conditions=synthetic_conditions(),
            expected_noise_draws={0.0: 1, 0.1: 16},
        )
        self.assertEqual(result["scene_rows"][0]["nrmse_phys"], 1)
        with self.assertRaises(ValueError):
            hierarchical_scene_average(rows, ("nrmse_phys",), expected_noise_draws={0.0: 1})

    def test_inferred_global_missing_conditions_cannot_create_complete_scene(self):
        rows = synthetic_rows()
        condition = synthetic_conditions()[0]
        rows = [row for row in rows if not all(row[key] == value for key, value in condition.items())]
        result = hierarchical_scene_average(rows, ("nrmse_phys",))
        self.assertEqual(result["scene_rows"][0]["missing_condition_count"], 1)
        self.assertFalse(result["scene_rows"][0]["complete"])
        self.assertEqual(result["audit"]["expected_conditions_source"], "inferred_union")


class PairedSceneBootstrapTests(unittest.TestCase):
    def test_four_scene_clusters_match_analytic_resampling_not_replicate_weighting(self):
        scenes = (2001, 2003, 2014, 2009)
        a2 = dict(zip(scenes, (1.0, 2.0, 3.0, 4.0)))
        a3 = dict(zip(scenes, (0.5, 1.0, 1.5, 2.0)))
        result = paired_scene_bootstrap(a3, a2, expected_scenes=scenes)
        self.assertTrue(result["complete"])
        self.assertEqual(result["scene_cluster_count"], 4)
        self.assertEqual(result["resampling_unit"], "scene")
        self.assertEqual(result["n_resamples"], 2000)
        self.assertEqual(result["seed"], 20261911)
        self.assertEqual(result["mean_difference"], 1.25)
        self.assertEqual(result["relative_improvement_of_means"], 0.5)
        self.assertEqual(result["relative_improvement_of_means_ci95"], [0.5, 0.5])
        indices = np.random.default_rng(BOOTSTRAP_SEED).integers(0, 4, size=(BOOTSTRAP_RESAMPLES, 4))
        scene_differences = np.asarray([a2[scene] - a3[scene] for scene in scenes])
        expected = np.quantile(scene_differences[indices].mean(axis=1), [0.025, 0.975])
        np.testing.assert_array_equal(result["mean_difference_ci95"], expected)
        self.assertEqual(result, paired_scene_bootstrap(a3, a2, expected_scenes=scenes))

    def test_hierarchical_scene_means_remain_four_equal_clusters(self):
        scenes = (2001, 2003, 2014, 2009)
        rows = []
        for index, scene in enumerate(scenes):
            rows.extend(synthetic_rows(scene, zero_value=index + 1, noisy_value=index + 1))
        summary = aggregate(rows)
        by_scene = {scene["scene"]: scene["nrmse_phys"] for scene in summary["scene_rows"]}
        self.assertEqual(len(by_scene), 4)
        result = paired_scene_bootstrap(by_scene, {scene: value * 2 for scene, value in by_scene.items()})
        self.assertEqual(result["mean_a3"], 2.5)
        self.assertEqual(result["mean_a2"], 5)
        self.assertEqual(result["relative_improvement_of_means"], 0.5)
        self.assertEqual(result["scene_cluster_count"], 4)

    def test_missing_or_undefined_scene_is_not_filtered_for_a_positive_result(self):
        scenes = (2001, 2003, 2014, 2009)
        a2 = dict.fromkeys(scenes, 1.0)
        for a3 in ({2001: 0.5, 2003: 0.5, 2014: 0.5},
                   {2001: 0.5, 2003: 0.5, 2014: 0.5, 2009: None}):
            with self.subTest(a3=a3):
                result = paired_scene_bootstrap(a3, a2, expected_scenes=scenes)
                self.assertFalse(result["complete"])
                self.assertEqual(result["missing_paired_scene_count"], 1)
                self.assertIsNone(result["mean_difference"])
                self.assertIsNone(result["relative_improvement_of_means_ci95"])
        wrong_count = paired_scene_bootstrap({1: 0.5, 2: 0.5, 3: 0.5}, {1: 1, 2: 1, 3: 1})
        self.assertFalse(wrong_count["complete"])
        self.assertEqual(wrong_count["scene_cluster_count"], 3)
        self.assertEqual(wrong_count["missing_scene_cluster_count"], 1)

    def test_zero_baseline_draws_disable_relative_interval_without_filtering(self):
        scenes = (2001, 2003, 2014, 2009)
        a2 = dict(zip(scenes, (0.0, 0.0, 1.0, 1.0)))
        a3 = dict.fromkeys(scenes, 0.5)
        result = paired_scene_bootstrap(a3, a2, expected_scenes=scenes)
        self.assertTrue(result["complete"])
        self.assertGreater(result["undefined_relative_bootstrap_count"], 0)
        self.assertIsNotNone(result["mean_difference_ci95"])
        self.assertIsNone(result["relative_improvement_of_means_ci95"])
        self.assertIsNone(result["mean_paired_relative_improvement"])

    def test_replicate_arrays_nonfinite_inputs_and_unfrozen_bootstrap_are_rejected(self):
        baseline = dict.fromkeys(range(4), 1.0)
        for invalid in ([0.5] * 16, np.nan, np.inf, -1.0, 1 + 0j, True):
            candidate = dict.fromkeys(range(4), 0.5)
            candidate[0] = invalid
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                paired_scene_bootstrap(candidate, baseline)
        for kwargs in ({"n_resamples": 1999}, {"seed": 0}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                paired_scene_bootstrap(dict.fromkeys(range(4), 0.5), baseline, **kwargs)


if __name__ == "__main__":
    unittest.main()
