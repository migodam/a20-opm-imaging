"""Cached material decomposition into the frozen chart and its exterior.

This evaluator-only audit constructs no physics, solve, score, or split. A
finite label's material is recovered from its stored generator recipe, not
from a separately saved full perturbed material field. Exterior energy is a
mesh-space quantity and is never assigned to the prior subspace inside W.
"""

from __future__ import annotations

import csv
import io
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from a22.offline_assets import _read_truth, _root, _validate_manifest
from .replay import SCENES, _immutable_json, _require_evaluation_freeze


SCHEMA = "a22_r1.chart_exterior_audit.v1"
IDENTITY_RTOL = 1e-9
IDENTITY_ATOL = 1e-12
CELL_COUNT = 1728
SPATIAL_DIMENSION = 16
MATERIAL_DIMENSION = 32


class ChartAuditError(ValueError):
    """A cache layout or material identity does not match the frozen chart."""


def _finite_array(value: Any, shape: tuple[int, ...], name: str, *, complex_value: bool):
    array = np.asarray(value)
    if array.dtype.kind not in "fci":
        raise ChartAuditError("CHART_AUDIT_ARRAY_LAYOUT:" + name)
    if (array.shape != shape or np.iscomplexobj(array) != complex_value
            or not np.all(np.isfinite(array))):
        raise ChartAuditError("CHART_AUDIT_ARRAY_LAYOUT:" + name)
    return np.array(array, dtype=complex if complex_value else float, copy=True)


def _positive_scalar(value: Any, name: str):
    array = np.asarray(value)
    if array.shape != () or array.dtype.kind not in "fi":
        raise ChartAuditError("CHART_AUDIT_SCALAR_LAYOUT:" + name)
    scalar = float(array)
    if not math.isfinite(scalar) or scalar <= 0:
        raise ChartAuditError("CHART_AUDIT_POSITIVE_SCALAR:" + name)
    return scalar


def _close(actual: np.ndarray, expected: np.ndarray, name: str):
    difference = float(np.linalg.norm(actual - expected))
    tolerance = IDENTITY_ATOL + IDENTITY_RTOL * float(np.linalg.norm(expected))
    if difference > tolerance:
        raise ChartAuditError("CHART_AUDIT_CACHE_IDENTITY:" + name)
    return difference


def _energy(vector: np.ndarray, volume: float):
    with np.errstate(over="ignore", invalid="ignore"):
        result = float(volume * np.vdot(vector, vector).real)
    if not math.isfinite(result) or result < 0:
        raise ChartAuditError("CHART_AUDIT_NONFINITE_ENERGY")
    return result


def _ratio(numerator: float, denominator: float):
    return numerator / denominator if denominator > 0 else None


def _decomposition(delta: Any, Q: Any, volume: Any):
    """Pure mass-orthogonal decomposition in real/imaginary chart coordinates."""
    Q = np.asarray(Q)
    if Q.ndim != 2 or Q.shape[1] != SPATIAL_DIMENSION:
        raise ChartAuditError("CHART_AUDIT_SPATIAL_DIMENSION_MUST_BE_16")
    Q = _finite_array(Q, Q.shape, "Q", complex_value=False)
    volume = _positive_scalar(volume, "volume")
    gram_error = float(np.linalg.norm(volume * Q.T @ Q - np.eye(SPATIAL_DIMENSION)))
    if not math.isfinite(gram_error) or gram_error > IDENTITY_RTOL:
        raise ChartAuditError("CHART_AUDIT_MASS_METRIC_CHANGED")
    delta = _finite_array(delta, (Q.shape[0],), "delta", complex_value=True)
    complex_coefficients = volume * (Q.T @ delta)
    coefficients = np.r_[complex_coefficients.real, complex_coefficients.imag]
    inside = Q @ complex_coefficients
    outside = delta - inside
    total_energy = _energy(delta, volume)
    inside_energy = _energy(inside, volume)
    outside_energy = _energy(outside, volume)
    coefficient_energy = _energy(coefficients, 1.0)
    orthogonality = volume * np.vdot(inside, outside)
    outside_coefficients = volume * (Q.T @ outside)
    outside_projected_norm = float(np.linalg.norm(outside_coefficients))
    reconstruction_residual = math.sqrt(_energy(delta - inside - outside, volume))
    energy_residual = abs(total_energy - inside_energy - outside_energy)
    coefficient_energy_residual = abs(inside_energy - coefficient_energy)
    norm = math.sqrt(total_energy)
    energy_tolerance = IDENTITY_ATOL + IDENTITY_RTOL * total_energy
    norm_tolerance = IDENTITY_ATOL + IDENTITY_RTOL * norm
    checks = {
        "mass_orthonormal_chart": gram_error <= IDENTITY_RTOL,
        "material_decomposition": reconstruction_residual <= norm_tolerance,
        "mass_energy_partition": energy_residual <= energy_tolerance,
        "coefficient_field_energy_identity": coefficient_energy_residual <= energy_tolerance,
        "inside_outside_mass_orthogonality": abs(orthogonality) <= energy_tolerance,
        "outside_projects_to_zero": outside_projected_norm <= norm_tolerance,
    }
    checks = {name: bool(value) for name, value in checks.items()}
    row = dict(
        cell_volume=volume, cell_count=Q.shape[0], spatial_dimension=SPATIAL_DIMENSION,
        material_dimension=MATERIAL_DIMENSION, material_coordinate_order="16_real_then_16_imaginary",
        projected_coefficients=coefficients.tolist(),
        delta_mass_norm=norm, total_delta_energy=total_energy,
        in_chart_mass_norm=math.sqrt(inside_energy), in_chart_energy=inside_energy,
        coefficient_energy=coefficient_energy,
        chart_exterior_mass_norm=math.sqrt(outside_energy), chart_exterior_energy=outside_energy,
        chart_retained_energy_fraction=_ratio(inside_energy, total_energy),
        chart_exterior_energy_fraction=_ratio(outside_energy, total_energy),
        zero_delta_energy=total_energy == 0,
        chart_metric_residual=gram_error,
        material_decomposition_mass_residual=reconstruction_residual,
        material_decomposition_relative_residual=_ratio(reconstruction_residual, norm),
        mass_energy_identity_absolute_residual=energy_residual,
        mass_energy_identity_relative_residual=_ratio(energy_residual, total_energy),
        coefficient_field_energy_identity_absolute_residual=coefficient_energy_residual,
        mass_inner_product_inside_outside_real=float(orthogonality.real),
        mass_inner_product_inside_outside_imaginary=float(orthogonality.imag),
        mass_inner_product_inside_outside_abs=float(abs(orthogonality)),
        outside_projected_coefficient_norm=outside_projected_norm,
        identity_absolute_tolerance=IDENTITY_ATOL, identity_relative_tolerance=IDENTITY_RTOL,
        identity_energy_tolerance=energy_tolerance, identity_norm_tolerance=norm_tolerance,
        identity_checks=checks, identity_checks_pass=all(checks.values()),
        chart_exterior_is_not_in_chart_prior=True,
    )
    return row, coefficients, outside


def _online_chart(root: Path, sid: int):
    manifest_path = root / f"results/a22_r1/online/scene_{sid}.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != "a22_r1.online_freeze.v1" or manifest.get("status") != "COMPLETE":
        raise ChartAuditError("CHART_AUDIT_ONLINE_CACHE_NOT_COMPLETE")
    path = root / f"results/a22_r1/online/scene_{sid}.npz"
    with np.load(path, allow_pickle=False) as archive:
        Q = _finite_array(archive["Q_spatial"], (CELL_COUNT, SPATIAL_DIMENSION), "Q_spatial", complex_value=False)
        anchor = _finite_array(archive["anchor_chi"], (CELL_COUNT,), "anchor_chi", complex_value=True)
        volume = _positive_scalar(archive["cell_volume"], "cell_volume")
    if not np.allclose(anchor, 0.1 + 0.04j, rtol=0, atol=1e-14):
        raise ChartAuditError("CHART_AUDIT_KNOWN_BACKGROUND_CHANGED")
    return Q, anchor, volume, path


def _csv_text(rows: list[dict[str, Any]]):
    fields = list(dict.fromkeys(key for row in rows for key in row))
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fields)
    writer.writeheader()
    for row in rows:
        writer.writerow({key: json.dumps(value, sort_keys=True, allow_nan=False)
                         if isinstance(value, (dict, list, tuple)) else value
                         for key, value in row.items()})
    return stream.getvalue()


def build_chart_audit(root: str | Path) -> dict[str, Any]:
    """Audit four original materials and 8 finite labels per scene from caches.

    Requires the global online split freeze before any material-cache read.
    Writes only ``results/a22_r1/CHART_EXTERIOR_RAW.json`` and ``.csv``. The
    caller meters inclusive process cost and integrates its separate receipt.
    Matching existing outputs are reusable; different outputs are refused.
    """
    root = Path(root).resolve()
    _require_evaluation_freeze(root)
    _, offline_directory = _root(root)
    manifest = _validate_manifest(json.loads((offline_directory / "MANIFEST.json").read_text(encoding="utf-8")))
    rows: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    for sid in SCENES:
        Q, anchor, volume, online_path = _online_chart(root, sid)
        original_path = offline_directory / f"scene_{sid}.npz"
        original_material = _read_truth(original_path)
        record = next(item for item in manifest["scenes"] if item["scene_id"] == sid)
        base, base_coefficients, base_outside = _decomposition(original_material - anchor, Q, volume)
        original_row = dict(scene=sid, family=record["family"], kind="ORIGINAL_SCENE_MATERIAL",
            direction=None, amplitude_level=None, physical_amplitude=None,
            material_source=str(original_path.relative_to(root)),
            online_chart_source=str(online_path.relative_to(root)),
            material_definition="delta=original_material-known_background",
            stored_coefficients=None, stored_coefficient_projection_error_norm=None, **base)
        rows.append(original_row)
        finite_rows = []
        for direction in range(4):
            for amplitude_level in range(2):
                label_path = root / (f"results/a22/stage_a/scene_{sid}/"
                                    f"OFFLINE_label_d{direction}_a{amplitude_level}.npz")
                with np.load(label_path, allow_pickle=False) as archive:
                    label_center = _finite_array(archive["original_material"], (CELL_COUNT,),
                                                 "label.original_material", complex_value=True)
                    perturbation_coefficients = _finite_array(archive["perturbation_coefficients"],
                        (MATERIAL_DIMENSION,), "label.perturbation_coefficients", complex_value=False)
                    stored_coefficients = _finite_array(archive["coefficients"],
                        (MATERIAL_DIMENSION,), "label.coefficients", complex_value=False)
                    amplitude = _positive_scalar(archive["amplitude"], "label.amplitude")
                    if "chart_Q" in archive.files:
                        cached_Q = _finite_array(archive["chart_Q"], Q.shape, "label.chart_Q", complex_value=False)
                        _close(cached_Q, Q, "label.chart_Q")
                    if "anchor_material" in archive.files:
                        cached_anchor = _finite_array(archive["anchor_material"], anchor.shape,
                                                     "label.anchor_material", complex_value=True)
                        _close(cached_anchor, anchor, "label.anchor_material")
                center_error = _close(label_center, original_material, "label.original_material")
                perturbation = Q @ (perturbation_coefficients[:16] + 1j * perturbation_coefficients[16:])
                perturbation_row, projected_perturbation, perturbation_outside = _decomposition(perturbation, Q, volume)
                full_row, projected_full, full_outside = _decomposition(label_center + perturbation - anchor, Q, volume)
                projection_error = float(np.linalg.norm(projected_full - stored_coefficients))
                addition_error = float(np.linalg.norm(stored_coefficients - base_coefficients - perturbation_coefficients))
                perturbation_projection_error = float(np.linalg.norm(projected_perturbation - perturbation_coefficients))
                outside_change_norm = math.sqrt(_energy(full_outside - base_outside, volume))
                coefficient_tolerance = IDENTITY_ATOL + IDENTITY_RTOL * float(np.linalg.norm(stored_coefficients))
                perturbation_tolerance = IDENTITY_ATOL + IDENTITY_RTOL * float(np.linalg.norm(perturbation_coefficients))
                label_checks = dict(
                    stored_coefficients_match_material_projection=projection_error <= coefficient_tolerance,
                    stored_coefficients_equal_base_plus_perturbation=addition_error <= coefficient_tolerance,
                    perturbation_coefficients_match_projection=perturbation_projection_error <= perturbation_tolerance,
                    perturbation_confined_to_chart=math.sqrt(_energy(perturbation_outside, volume)) <= perturbation_tolerance,
                    exterior_retained_from_original=outside_change_norm <= full_row["identity_norm_tolerance"],
                )
                finite = dict(scene=sid, family=record["family"], kind="FINITE_PERTURBATION_LABEL",
                    direction=direction, amplitude_level=amplitude_level, physical_amplitude=amplitude,
                    material_source=str(label_path.relative_to(root)),
                    online_chart_source=str(online_path.relative_to(root)),
                    material_definition="delta=stored_original_material+Q_expand(stored_perturbation_coefficients)-known_background",
                    perturbed_material_origin="stored_generator_recipe; independent full perturbed material vector not cached",
                    stored_coefficients=stored_coefficients.tolist(),
                    stored_coefficient_projection_error_norm=projection_error,
                    stored_coefficient_addition_error_norm=addition_error,
                    stored_perturbation_coefficients=perturbation_coefficients.tolist(),
                    projected_perturbation_coefficients=projected_perturbation.tolist(),
                    perturbation_coefficient_projection_error_norm=perturbation_projection_error,
                    original_material_mass_difference=math.sqrt(volume) * center_error,
                    perturbation_mass_norm=perturbation_row["delta_mass_norm"],
                    perturbation_energy=perturbation_row["total_delta_energy"],
                    perturbation_in_chart_energy=perturbation_row["in_chart_energy"],
                    perturbation_chart_exterior_energy=perturbation_row["chart_exterior_energy"],
                    perturbation_chart_exterior_fraction=perturbation_row["chart_exterior_energy_fraction"],
                    exterior_change_mass_norm=outside_change_norm,
                    exterior_energy_difference_from_original=full_row["chart_exterior_energy"] - base["chart_exterior_energy"],
                    label_identity_checks=label_checks, label_identity_checks_pass=all(label_checks.values()),
                    **full_row)
                finite_rows.append(finite)
                rows.append(finite)
        retained_fractions = [item["chart_retained_energy_fraction"] for item in finite_rows
                              if item["chart_retained_energy_fraction"] is not None]
        summaries.append(dict(scene=sid, family=record["family"], original=original_row,
            finite_label_count=len(finite_rows),
            finite_retained_energy_fraction_min=min(retained_fractions, default=None),
            finite_retained_energy_fraction_max=max(retained_fractions, default=None),
            maximum_finite_stored_projection_error=max(item["stored_coefficient_projection_error_norm"] for item in finite_rows),
            maximum_exterior_change_mass_norm=max(item["exterior_change_mass_norm"] for item in finite_rows),
            all_identity_checks_pass=base["identity_checks_pass"] and all(
                item["identity_checks_pass"] and item["label_identity_checks_pass"] for item in finite_rows)))
    json_path = root / "results/a22_r1/CHART_EXTERIOR_RAW.json"
    csv_path = root / "results/a22_r1/CHART_EXTERIOR_RAW.csv"
    result = dict(schema=SCHEMA,
        status="COMPLETE" if all(item["all_identity_checks_pass"] for item in summaries) else "IDENTITY_MISMATCH",
        scope="OFFLINE_IN_CHART_VERSUS_CHART_EXTERIOR_AUDIT", scenes=list(SCENES), rows=rows,
        per_scene_summary=summaries, original_scene_count=4, finite_labels_per_scene=8,
        raw_row_count=len(rows),
        decomposition="chi=known_background+Q(x_real+i*x_imag)+chi_outside_W",
        physical_norm="cell_volume*sum(abs(delta_chi)**2); volume*Q.T*Q=I16",
        chart_exterior_is_not_in_chart_prior=True,
        finite_material_provenance="stored original_material + Q expansion of stored perturbation_coefficients; no independent full perturbed material vector",
        no_physical_actions=True, new_Maxwell_actions=0, new_labels=0, new_scores=0,
        counts=dict(online_chart_cache_reads=4, original_material_cache_reads=4, finite_label_cache_reads=32),
        artifacts=dict(json=str(json_path.relative_to(root)), csv=str(csv_path.relative_to(root))))
    csv_value = _csv_text(rows)
    if csv_path.exists():
        with csv_path.open("r", encoding="utf-8", newline="") as stream:
            if stream.read() != csv_value:
                raise ChartAuditError("CHART_AUDIT_EXISTING_RAW_CSV_CONFLICT")
    _immutable_json(json_path, result)
    if not csv_path.exists():
        with csv_path.open("x", encoding="utf-8", newline="") as stream:
            stream.write(csv_value)
    return result
