"""In-chart subspace metrics and scene-cluster summaries for A22-R1.

All coefficient vectors and basis columns must already use the frozen,
mass-orthonormal 32-real-dimensional chart. This module does not construct a
split, select a basis, run physics, or make a gate decision. ``None`` denotes an
undefined statistic; an epsilon is never added to an energy fraction.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Hashable, Mapping, Sequence
import math
from typing import Any

import numpy as np


CHART_DIMENSION = 32
NORM_FLOOR = 1e-6
CONDITIONS_PER_SCENE = 48
BOOTSTRAP_RESAMPLES = 2000
BOOTSTRAP_SEED = 20261911
SCENE_CLUSTERS = 4
CONDITION_KEYS = ("direction", "amplitude", "noise", "intervention")
SCENE_GROUP_KEYS = ("scene", "method", "k", "test")
DEFAULT_METRICS = (
    "nrmse_phys", "nrmse_prior", "s_sep", "f_error_prior",
    "f_truth_phys", "q_phys", "q_prior",
)


def _real_array(value: Any, name: str, ndim: int) -> np.ndarray:
    raw = np.asarray(value)
    if np.iscomplexobj(raw):
        raise ValueError(f"{name} must contain real chart coefficients")
    try:
        array = np.asarray(value, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a real numeric array") from exc
    if array.ndim != ndim:
        raise ValueError(f"{name} must have {ndim} dimensions")
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{name} contains nonfinite values")
    return array


def _positive_scalar(value: Any, name: str) -> float:
    if isinstance(value, (bool, np.bool_)) or np.asarray(value).ndim != 0:
        raise ValueError(f"{name} must be a finite positive scalar")
    try:
        scalar = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be a finite positive scalar") from exc
    if not math.isfinite(scalar) or scalar <= 0:
        raise ValueError(f"{name} must be a finite positive scalar")
    return scalar


def _energy(vector: np.ndarray) -> float:
    with np.errstate(over="ignore", invalid="ignore"):
        value = float(np.dot(vector, vector))
    if not math.isfinite(value):
        raise ValueError("Derived chart energy is nonfinite")
    return value


def _fraction(numerator: float, denominator: float) -> float | None:
    return numerator / denominator if denominator > 0 else None


def _selectivity(error_fraction: float | None,
                 truth_fraction: float | None) -> float | None:
    if error_fraction is None or truth_fraction is None or truth_fraction <= 0:
        return None
    return error_fraction / truth_fraction


def subspace_metrics(
    x_hat: Any,
    x_true: Any,
    v_phys: Any,
    v_prior: Any,
    *,
    norm_floor: float = NORM_FLOOR,
    orthonormal_atol: float = 1e-9,
) -> dict[str, Any]:
    """Measure one estimate in a supplied complementary split of the fixed chart.

    ``v_phys`` and ``v_prior`` have shapes ``(32, k)`` and ``(32, 32-k)``.
    Columns must be orthonormal and jointly span the chart. The same function
    applies to the common full solve in Test A or a restricted estimate in Test
    B; the caller must retain the test label. The declared norm floor affects
    only NRMSE denominators. Coverage, error fractions, and q use raw energies.
    """
    floor = _positive_scalar(norm_floor, "norm_floor")
    tolerance = _positive_scalar(orthonormal_atol, "orthonormal_atol")
    estimate = _real_array(x_hat, "x_hat", 1)
    truth = _real_array(x_true, "x_true", 1)
    phys = _real_array(v_phys, "v_phys", 2)
    prior = _real_array(v_prior, "v_prior", 2)
    if estimate.shape != (CHART_DIMENSION,) or truth.shape != (CHART_DIMENSION,):
        raise ValueError("x_hat and x_true must each have exactly 32 coefficients")
    if phys.shape[0] != CHART_DIMENSION or prior.shape[0] != CHART_DIMENSION:
        raise ValueError("Subspace bases must each have exactly 32 rows")
    if phys.shape[1] + prior.shape[1] != CHART_DIMENSION:
        raise ValueError("The two subspace dimensions must sum to 32")
    joint = np.column_stack((phys, prior))
    gram_error = joint.T @ joint - np.eye(CHART_DIMENSION)
    if not np.all(np.isfinite(gram_error)) or not np.allclose(
        gram_error, 0.0, rtol=0.0, atol=tolerance
    ):
        raise ValueError("The supplied bases are not orthonormal complements")

    with np.errstate(over="ignore", invalid="ignore"):
        error = estimate - truth
        error_phys = phys @ (phys.T @ error)
        error_prior = prior @ (prior.T @ error)
        truth_phys = phys @ (phys.T @ truth)
        truth_prior = prior @ (prior.T @ truth)
    energies = {
        "error": _energy(error),
        "error_phys": _energy(error_phys),
        "error_prior": _energy(error_prior),
        "truth": _energy(truth),
        "truth_phys": _energy(truth_phys),
        "truth_prior": _energy(truth_prior),
    }
    norms = {name: math.sqrt(value) for name, value in energies.items()}
    phys_floor = norms["truth_phys"] < floor
    prior_floor = norms["truth_prior"] < floor
    phys_denominator = max(norms["truth_phys"], floor)
    prior_denominator = max(norms["truth_prior"], floor)
    nrmse_phys = norms["error_phys"] / phys_denominator
    nrmse_prior = norms["error_prior"] / prior_denominator
    s_sep = nrmse_prior / nrmse_phys if nrmse_phys > 0 else None
    f_error_phys = _fraction(energies["error_phys"], energies["error"])
    f_error_prior = _fraction(energies["error_prior"], energies["error"])
    f_truth_phys = _fraction(energies["truth_phys"], energies["truth"])
    f_truth_prior = _fraction(energies["truth_prior"], energies["truth"])
    q_phys = _selectivity(f_error_phys, f_truth_phys)
    q_prior = _selectivity(f_error_prior, f_truth_prior)

    undefined: dict[str, str] = {}
    if s_sep is None:
        undefined["s_sep"] = "physics NRMSE is zero"
    if energies["error"] == 0:
        for name in ("f_error_phys", "f_error_prior"):
            undefined[name] = "total in-chart error energy is zero"
    if energies["truth"] == 0:
        for name in ("f_truth_phys", "f_truth_prior"):
            undefined[name] = "total in-chart truth energy is zero"
    for name, value, signal_energy in (
        ("q_phys", q_phys, energies["truth_phys"]),
        ("q_prior", q_prior, energies["truth_prior"]),
    ):
        if value is None:
            undefined[name] = (
                "subspace truth energy is zero" if signal_energy == 0
                else "a required raw energy fraction is undefined"
            )

    identity_applicable = (
        not phys_floor and not prior_floor and s_sep is not None
        and q_phys is not None and q_phys > 0 and q_prior is not None
    )
    q_ratio = q_prior / q_phys if identity_applicable else None
    s_sep_squared = s_sep * s_sep if identity_applicable else None
    q_identity_residual = (
        abs(s_sep_squared - q_ratio) if identity_applicable else None
    )
    if not identity_applicable:
        undefined["q_identity_residual"] = (
            "NRMSE norm floor is active" if phys_floor or prior_floor
            else "separation or a nonzero physics selectivity is undefined"
        )

    result: dict[str, Any] = {
        "chart_dimension": CHART_DIMENSION,
        "k": int(phys.shape[1]),
        "prior_dimension": int(prior.shape[1]),
        "norm_floor": floor,
        "floor_phys_active": bool(phys_floor),
        "floor_prior_active": bool(prior_floor),
        "nrmse_phys_denominator": phys_denominator,
        "nrmse_prior_denominator": prior_denominator,
        "nrmse_phys": nrmse_phys,
        "nrmse_prior": nrmse_prior,
        "s_sep": s_sep,
        "f_error_phys": f_error_phys,
        "f_error_prior": f_error_prior,
        "f_truth_phys": f_truth_phys,
        "f_truth_prior": f_truth_prior,
        "q_phys": q_phys,
        "q_prior": q_prior,
        "basis_orthonormality_residual": float(np.linalg.norm(gram_error)),
        "projector_completeness_residual": float(np.linalg.norm(
            phys @ phys.T + prior @ prior.T - np.eye(CHART_DIMENSION)
        )),
        "signal_projection_identity_residual": float(np.linalg.norm(
            truth_phys + truth_prior - truth
        )),
        "error_projection_identity_residual": float(np.linalg.norm(
            error_phys + error_prior - error
        )),
        "signal_energy_identity_residual": abs(
            energies["truth_phys"] + energies["truth_prior"] - energies["truth"]
        ),
        "error_energy_identity_residual": abs(
            energies["error_phys"] + energies["error_prior"] - energies["error"]
        ),
        "q_identity_applicable": bool(identity_applicable),
        "q_identity_s_sep_squared": s_sep_squared,
        "q_identity_q_prior_over_q_phys": q_ratio,
        "q_identity_residual": q_identity_residual,
        "undefined_reasons": undefined,
    }
    result.update({f"{name}_energy": value for name, value in energies.items()})
    result.update({f"{name}_norm": value for name, value in norms.items()})
    for name, value in result.items():
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError(f"Derived statistic {name} is nonfinite")
    return result


def _key(record: Mapping[str, Any], fields: Sequence[str]) -> tuple[Any, ...]:
    try:
        values = tuple(record[field] for field in fields)
    except KeyError as exc:
        raise ValueError(f"Record is missing required key {exc.args[0]}") from exc
    if any(not isinstance(value, Hashable) for value in values):
        raise ValueError("Grouping keys must be hashable scalar values")
    return values


def _condition_key(value: Mapping[str, Any] | Sequence[Any]) -> tuple[Any, ...]:
    if isinstance(value, Mapping):
        return _key(value, CONDITION_KEYS)
    if isinstance(value, (str, bytes)) or len(value) != len(CONDITION_KEYS):
        raise ValueError("Expected conditions require four condition keys")
    record = dict(zip(CONDITION_KEYS, value))
    return _key(record, CONDITION_KEYS)


def _expected_draw_count(noise: Any, specification: Mapping[Any, int] | None) -> int:
    if specification is None:
        noiseless = noise == 0 or str(noise).lower() in {
            "0", "0.0", "zero", "none", "noiseless"
        }
        return 1 if noiseless else 16
    if noise not in specification:
        raise ValueError(f"No preregistered noise-draw count for {noise!r}")
    value = specification[noise]
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)):
        raise ValueError("Expected noise-draw counts must be positive integers")
    if value <= 0:
        raise ValueError("Expected noise-draw counts must be positive integers")
    return int(value)


def _failed_row(row: Mapping[str, Any]) -> bool:
    status = str(row.get("status", "ok")).strip().lower()
    return (
        bool(row.get("failed", False)) or not bool(row.get("success", True))
        or status not in {"ok", "success", "complete", "completed", "valid", "ran", "run", "pass"}
    )


def _metric_value(row: Mapping[str, Any], name: str) -> float | None:
    nested = row.get("metrics", {})
    value = row[name] if name in row else nested.get(name) if isinstance(nested, Mapping) else None
    if value is None or isinstance(value, (bool, np.bool_)):
        return None
    if np.iscomplexobj(value) or np.asarray(value).ndim != 0:
        return None
    try:
        scalar = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return scalar if math.isfinite(scalar) else None


def hierarchical_scene_average(
    rows: Sequence[Mapping[str, Any]],
    metric_names: Sequence[str] = DEFAULT_METRICS,
    *,
    expected_conditions: Sequence[Mapping[str, Any] | Sequence[Any]] | None = None,
    expected_noise_draws: Mapping[Any, int] | None = None,
    expected_groups: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Average noise draws, then equally weight the frozen 48 conditions.

    Each input row requires ``scene, direction, amplitude, noise, intervention,
    method, k, test, noise_draw``. Metrics may be flat or under ``metrics``.
    Supply ``expected_conditions`` (48 unique direction/amplitude/noise/
    intervention tuples) and ``expected_groups`` (scene/method/k/test) to detect
    cases or entire groups absent from the input. Without these, expectations
    use the observed union and report that they were inferred; the required
    count remains 48. Noiseless conditions expect one draw and other noise
    conditions 16, unless an explicit frozen count mapping is provided.

    Missing, duplicated, failed, excess, or unexpected rows make the affected
    scene unavailable. An undefined metric propagates to that scene's metric,
    rather than being omitted from its mean. Other fully defined metrics may
    still be reported. Status defaults to ``ok``; only ``ok, success, complete,
    completed, valid, ran, run, pass`` are accepted as successful. Other states
    remain failed in the audit. All counts remain in the returned audit.
    """
    names = tuple(metric_names)
    if not names or len(set(names)) != len(names) or any(
        not isinstance(name, str) or not name for name in names
    ):
        raise ValueError("metric_names must contain unique nonempty names")
    grouped: dict[tuple[Any, ...], dict[tuple[Any, ...], list[Mapping[str, Any]]]] = (
        defaultdict(lambda: defaultdict(list))
    )
    observed_conditions: set[tuple[Any, ...]] = set()
    for row in rows:
        group = _key(row, SCENE_GROUP_KEYS)
        condition = _key(row, CONDITION_KEYS)
        _key(row, ("noise_draw",))
        grouped[group][condition].append(row)
        observed_conditions.add(condition)
    if expected_conditions is None:
        conditions = set(observed_conditions)
        inferred_condition_shortfall = max(CONDITIONS_PER_SCENE - len(conditions), 0)
    else:
        listed_conditions = [_condition_key(value) for value in expected_conditions]
        conditions = set(listed_conditions)
        if len(listed_conditions) != CONDITIONS_PER_SCENE or len(conditions) != CONDITIONS_PER_SCENE:
            raise ValueError("Exactly 48 unique frozen conditions must be supplied")
        inferred_condition_shortfall = 0
    if expected_groups is None:
        groups = set(grouped)
    else:
        listed_groups = [_key(group, SCENE_GROUP_KEYS) for group in expected_groups]
        groups = set(listed_groups)
        if len(groups) != len(listed_groups):
            raise ValueError("expected_groups must be unique")
        if set(grouped) - groups:
            raise ValueError("Input includes a scene/method/k/test group outside the frozen plan")

    condition_rows: list[dict[str, Any]] = []
    scene_rows: list[dict[str, Any]] = []
    for group in sorted(groups, key=repr):
        group_records = grouped.get(group, {})
        observed = set(group_records)
        unexpected = observed - conditions
        group_condition_rows: list[dict[str, Any]] = []
        for condition in sorted(conditions | unexpected, key=repr):
            condition_records = group_records.get(condition, [])
            expected_draws = _expected_draw_count(condition[2], expected_noise_draws)
            draws = [row["noise_draw"] for row in condition_records]
            unique_draws = set(draws)
            duplicates = len(draws) - len(unique_draws)
            missing_draws = max(expected_draws - len(unique_draws), 0)
            excess_draws = max(len(unique_draws) - expected_draws, 0)
            failed = sum(_failed_row(row) for row in condition_records)
            structurally_complete = (
                not missing_draws and not excess_draws and not duplicates and not failed
                and condition not in unexpected
            )
            item: dict[str, Any] = dict(zip(SCENE_GROUP_KEYS, group))
            item.update(zip(CONDITION_KEYS, condition))
            item.update({
                "expected_noise_draws": expected_draws,
                "observed_noise_draws": len(unique_draws),
                "input_row_count": len(condition_records),
                "missing_noise_draw_count": missing_draws,
                "excess_noise_draw_count": excess_draws,
                "duplicate_noise_draw_count": duplicates,
                "failed_replicate_count": failed,
                "unexpected_condition": condition in unexpected,
                "structurally_complete": structurally_complete,
                "undefined_metric_counts": {},
            })
            for name in names:
                values = [None if _failed_row(row) else _metric_value(row, name)
                          for row in condition_records]
                undefined_count = sum(value is None for value in values)
                item["undefined_metric_counts"][name] = undefined_count
                item[name] = (
                    math.fsum(values) / expected_draws
                    if structurally_complete and not undefined_count else None
                )
            item["metrics_complete"] = all(item[name] is not None for name in names)
            item["complete"] = structurally_complete and item["metrics_complete"]
            group_condition_rows.append(item)
            condition_rows.append(item)

        missing_conditions = len(conditions - observed) + inferred_condition_shortfall
        structural = (
            len(conditions) == CONDITIONS_PER_SCENE and not missing_conditions
            and not unexpected and all(item["structurally_complete"]
                                       for item in group_condition_rows)
        )
        scene: dict[str, Any] = dict(zip(SCENE_GROUP_KEYS, group))
        scene.update({
            "expected_condition_count": CONDITIONS_PER_SCENE,
            "observed_condition_count": len(observed),
            "missing_condition_count": missing_conditions,
            "unexpected_condition_count": len(unexpected),
            "inferred_unknown_condition_count": inferred_condition_shortfall,
            "missing_noise_draw_count": sum(item["missing_noise_draw_count"]
                                            for item in group_condition_rows),
            "excess_noise_draw_count": sum(item["excess_noise_draw_count"]
                                           for item in group_condition_rows),
            "duplicate_noise_draw_count": sum(item["duplicate_noise_draw_count"]
                                              for item in group_condition_rows),
            "failed_replicate_count": sum(item["failed_replicate_count"]
                                          for item in group_condition_rows),
            "structurally_complete": structural,
            "undefined_condition_counts": {},
        })
        for name in names:
            values = [item[name] for item in group_condition_rows]
            scene["undefined_condition_counts"][name] = sum(value is None for value in values)
            scene[name] = (
                math.fsum(values) / CONDITIONS_PER_SCENE
                if structural and all(value is not None for value in values) else None
            )
        scene["metrics_complete"] = all(scene[name] is not None for name in names)
        scene["complete"] = structural and scene["metrics_complete"]
        scene_rows.append(scene)
    audit = {
        "expected_conditions_per_scene": CONDITIONS_PER_SCENE,
        "expected_conditions_source": "explicit" if expected_conditions is not None else "inferred_union",
        "expected_groups_source": "explicit" if expected_groups is not None else "observed_groups",
        "input_row_count": len(rows),
        "scene_group_count": len(scene_rows),
        "complete_scene_group_count": sum(scene["complete"] for scene in scene_rows),
        "incomplete_scene_group_count": sum(not scene["complete"] for scene in scene_rows),
        "missing_condition_count": sum(scene["missing_condition_count"] for scene in scene_rows),
        "missing_noise_draw_count": sum(scene["missing_noise_draw_count"] for scene in scene_rows),
        "excess_noise_draw_count": sum(scene["excess_noise_draw_count"] for scene in scene_rows),
        "duplicate_noise_draw_count": sum(scene["duplicate_noise_draw_count"] for scene in scene_rows),
        "failed_replicate_count": sum(scene["failed_replicate_count"] for scene in scene_rows),
        "unexpected_condition_count": sum(scene["unexpected_condition_count"] for scene in scene_rows),
    }
    return {"scene_rows": scene_rows, "condition_rows": condition_rows, "audit": audit}


def paired_scene_bootstrap(
    a3_by_scene: Mapping[Any, float | None],
    a2_by_scene: Mapping[Any, float | None],
    *,
    expected_scenes: Sequence[Any] | None = None,
    n_resamples: int = BOOTSTRAP_RESAMPLES,
    seed: int = BOOTSTRAP_SEED,
) -> dict[str, Any]:
    """Paired equal-scene bootstrap of NRMSE improvement, over four clusters.

    Inputs must already be scene means, not replicate arrays. Positive
    ``mean_difference`` means A3 has smaller NRMSE than A2. Relative improvement
    is ``1 - mean(A3) / mean(A2)``; paired relative mean/median are additionally
    reported without substituting either for this point estimate. The frozen
    2000 resamples and seed are enforced. Any absent/undefined scene disables
    the summary and interval rather than filtering the scene out.
    """
    if n_resamples != BOOTSTRAP_RESAMPLES or seed != BOOTSTRAP_SEED:
        raise ValueError("A22-R1 bootstrap is frozen at 2000 resamples and seed 20261911")
    union = set(a3_by_scene) | set(a2_by_scene)
    scenes = list(expected_scenes) if expected_scenes is not None else sorted(union, key=repr)
    if len(set(scenes)) != len(scenes):
        raise ValueError("Expected scene identifiers must be unique")
    if expected_scenes is not None and union - set(scenes):
        raise ValueError("Bootstrap inputs include a scene outside the frozen plan")

    def validate_values(values: Mapping[Any, float | None]) -> dict[Any, float | None]:
        parsed: dict[Any, float | None] = {}
        for scene in scenes:
            value = values.get(scene)
            if value is None:
                parsed[scene] = None
                continue
            if np.iscomplexobj(value) or isinstance(value, (bool, np.bool_)) or np.asarray(value).ndim != 0:
                raise ValueError("Bootstrap inputs must be scalar scene-level NRMSE values")
            scalar = float(value)
            if not math.isfinite(scalar) or scalar < 0:
                raise ValueError("Bootstrap NRMSE values must be finite and nonnegative")
            parsed[scene] = scalar
        return parsed

    a3 = validate_values(a3_by_scene)
    a2 = validate_values(a2_by_scene)
    missing_a3 = [scene for scene in scenes if a3[scene] is None]
    missing_a2 = [scene for scene in scenes if a2[scene] is None]
    missing_pairs = [scene for scene in scenes if a3[scene] is None or a2[scene] is None]
    cluster_count_valid = len(scenes) == SCENE_CLUSTERS
    complete = cluster_count_valid and not missing_pairs
    result: dict[str, Any] = {
        "resampling_unit": "scene",
        "expected_scene_cluster_count": SCENE_CLUSTERS,
        "scene_cluster_count": len(scenes),
        "missing_scene_cluster_count": max(SCENE_CLUSTERS - len(scenes), 0),
        "excess_scene_cluster_count": max(len(scenes) - SCENE_CLUSTERS, 0),
        "scene_ids": scenes,
        "n_resamples": BOOTSTRAP_RESAMPLES,
        "seed": BOOTSTRAP_SEED,
        "confidence_level": 0.95,
        "interval_kind": "paired scene percentile bootstrap",
        "complete": complete,
        "missing_a3_scene_count": len(missing_a3),
        "missing_a2_scene_count": len(missing_a2),
        "missing_paired_scene_count": len(missing_pairs),
        "missing_a3_scenes": missing_a3,
        "missing_a2_scenes": missing_a2,
        "mean_a3": None,
        "mean_a2": None,
        "mean_difference": None,
        "relative_improvement_of_means": None,
        "mean_paired_relative_improvement": None,
        "median_paired_relative_improvement": None,
        "mean_difference_ci95": None,
        "relative_improvement_of_means_ci95": None,
        "undefined_relative_bootstrap_count": 0,
    }
    if not complete:
        result["unavailable_reason"] = (
            "exactly four scene clusters are required" if not cluster_count_valid
            else "at least one preregistered scene is missing or undefined"
        )
        return result
    candidate = np.asarray([a3[scene] for scene in scenes], dtype=float)
    baseline = np.asarray([a2[scene] for scene in scenes], dtype=float)
    mean_candidate = float(np.mean(candidate))
    mean_baseline = float(np.mean(baseline))
    result["mean_a3"] = mean_candidate
    result["mean_a2"] = mean_baseline
    result["mean_difference"] = mean_baseline - mean_candidate
    if mean_baseline > 0:
        result["relative_improvement_of_means"] = 1.0 - mean_candidate / mean_baseline
    if np.all(baseline > 0):
        paired = 1.0 - candidate / baseline
        result["mean_paired_relative_improvement"] = float(np.mean(paired))
        result["median_paired_relative_improvement"] = float(np.median(paired))
    indices = np.random.default_rng(BOOTSTRAP_SEED).integers(
        0, SCENE_CLUSTERS, size=(BOOTSTRAP_RESAMPLES, SCENE_CLUSTERS)
    )
    candidate_means = np.mean(candidate[indices], axis=1)
    baseline_means = np.mean(baseline[indices], axis=1)
    differences = baseline_means - candidate_means
    result["mean_difference_ci95"] = np.quantile(differences, [0.025, 0.975]).tolist()
    undefined_count = int(np.count_nonzero(baseline_means == 0))
    result["undefined_relative_bootstrap_count"] = undefined_count
    if undefined_count == 0:
        improvements = 1.0 - candidate_means / baseline_means
        result["relative_improvement_of_means_ci95"] = np.quantile(
            improvements, [0.025, 0.975]
        ).tolist()
    else:
        result["relative_interval_unavailable_reason"] = (
            "a sampled scene cluster has zero mean A2 NRMSE; no resamples were filtered"
        )
    return result
