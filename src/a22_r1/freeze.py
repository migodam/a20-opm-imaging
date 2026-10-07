"""Freeze exact A22-R1 online splits without opening evaluator information.

The parent supplies the existing CostBook and authorizes any known-background
cache recovery. This module does not create a budget policy, run on import,
read offline labels/J, recalibrate scores, or alter the frozen A22 builders.
"""
from __future__ import annotations

from contextlib import nullcontext
from dataclasses import fields
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
import time
import uuid

import numpy as np
from scipy import linalg as la

from a20.costs import plain
from a22.assets import SCREENING_IDS, load_online_scene
from a22.budget import write_json
from a22.evaluate import _cache_contract, _freeze_budget_rows, _frozen_direction_cases
from a22.features import build_descriptor_context, direction_descriptor, predict_budget
from a22.online import build_anchor, build_opm


SCHEMA = "a22_r1.online_freeze.v1"
RELATIVE_TOLERANCE = 1e-9
METRIC_TOLERANCE = 1e-10
IDENTITY_ATOL = 1e-10
SCORE_CONTEXT = {
    "amplitude": 0.0,
    "noise_level": 1.0,
    "intervention": "nominal",
    "orientation": "ascending",
    "tie_breaker": "common_basis_index",
    "score_source": "unchanged a22.features.predict_budget pred_A1/pred_A2/pred_A3",
    "calibration": "none",
}
_IDENTITY_FIELDS = frozenset({
    "transpose_identity_error", "orthogonality", "nuisance_leakage",
    "attribution_error", "physical_metric_error", "backward_error",
})
_FROZEN_DESCRIPTOR_FIELDS = (
    "alpha", "beta", "gamma", "profile_g", "attribution",
    "dual_defect_norm", "IR_direction_norm",
)
_COMMON_DESCRIPTOR_FIELDS = (
    "h_norm", "bias_target", "bias_nuisance", "total_gain", "profile_g",
    "attribution", "alpha", "beta", "gamma", "psi_norm", "dual_defect_norm",
    "adj_coeff_norm", "IR_direction_norm", "IR_nuisance_norm",
    "propagated_direction_norm", "nuisance_propagation_norm",
    "background_calibration_budget", "background_agnostic_budget",
    "W_external_witness_norm", "transpose_identity_error", "unidentifiable",
)
_FORBIDDEN_COUNTERS = (
    "full_tangent_calls", "full_tangent_RHS", "full_adjoint_calls",
    "full_adjoint_RHS", "offline_J_builds", "offline_label_reads",
    "data_generation_F_calls", "new_teacher_labels",
)


class OnlineFreezeMismatch(ValueError):
    """Frozen physics/descriptor identity failed; no usable freeze is published."""


class _Audit:
    def __init__(self):
        self.comparisons = []
        self.tiny_identity_allowances = []

    def array(self, actual, expected, name, *, rtol=RELATIVE_TOLERANCE):
        actual, expected = np.asarray(actual), np.asarray(expected)
        if (actual.shape != expected.shape
                or np.iscomplexobj(actual) != np.iscomplexobj(expected)
                or not np.all(np.isfinite(actual))
                or not np.all(np.isfinite(expected))):
            raise OnlineFreezeMismatch("ARRAY_LAYOUT_OR_FINITENESS:" + name)
        scale = float(la.norm(expected.ravel()))
        error = float(la.norm((actual - expected).ravel()))
        permitted = rtol * scale
        record = dict(name=name, kind="array", shape=list(expected.shape),
                      absolute_error=error, reference_norm=scale,
                      relative_error=error / scale if scale else (0.0 if error == 0 else None),
                      relative_tolerance=rtol, passed=error <= permitted)
        self.comparisons.append(record)
        if not record["passed"]:
            raise OnlineFreezeMismatch("ARRAY_IDENTITY:" + name)

    def json(self, actual, expected, name):
        actual, expected = plain(actual), plain(expected)
        if isinstance(expected, dict):
            if not isinstance(actual, dict) or set(actual) != set(expected):
                raise OnlineFreezeMismatch("JSON_KEYS:" + name)
            for key in expected:
                self.json(actual[key], expected[key], name + "." + str(key))
        elif isinstance(expected, list):
            if not isinstance(actual, list) or len(actual) != len(expected):
                raise OnlineFreezeMismatch("JSON_LAYOUT:" + name)
            for index, (fresh, saved) in enumerate(zip(actual, expected)):
                self.json(fresh, saved, name + "." + str(index))
        elif isinstance(expected, (int, float)) and not isinstance(expected, bool):
            if (isinstance(actual, bool) or not isinstance(actual, (int, float))
                    or not np.isfinite(actual) or not np.isfinite(expected)):
                raise OnlineFreezeMismatch("JSON_NUMERIC_LAYOUT:" + name)
            error, scale = abs(actual - expected), abs(expected)
            permitted = RELATIVE_TOLERANCE * scale
            allowance = False
            if (name.rsplit(".", 1)[-1] in _IDENTITY_FIELDS
                    and scale <= IDENTITY_ATOL and error > permitted
                    and abs(actual) <= IDENTITY_ATOL and error <= IDENTITY_ATOL):
                permitted, allowance = IDENTITY_ATOL, True
                self.tiny_identity_allowances.append(dict(
                    name=name, actual=actual, expected=expected,
                    absolute_error=error, absolute_tolerance=IDENTITY_ATOL,
                    reason="explicit near-zero dimensionless identity residual"))
            record = dict(name=name, kind="scalar", absolute_error=error,
                          reference_abs=scale, relative_tolerance=RELATIVE_TOLERANCE,
                          relative_error=error / scale if scale else (0.0 if error == 0 else None),
                          tiny_identity_allowance=allowance, passed=error <= permitted)
            self.comparisons.append(record)
            if not record["passed"]:
                raise OnlineFreezeMismatch("JSON_NUMERIC_IDENTITY:" + name)
        elif type(actual) is not type(expected) or actual != expected:
            raise OnlineFreezeMismatch("JSON_VALUE:" + name)

    def report(self):
        relative = [row["relative_error"] for row in self.comparisons
                    if row.get("relative_error") is not None
                    and not row.get("tiny_identity_allowance", False)]
        return dict(relative_tolerance=RELATIVE_TOLERANCE,
                    comparison_count=len(self.comparisons),
                    maximum_relative_error=max(relative, default=0.0),
                    tiny_identity_allowance_used=bool(self.tiny_identity_allowances),
                    tiny_identity_allowances=self.tiny_identity_allowances,
                    comparisons=self.comparisons)


def _read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _cost_delta(book, counts, walls, started_wall, started_cpu):
    return dict(
        counts={key: int(value - counts.get(key, 0)) for key, value in book.counts.items()},
        exclusive_walls={key: float(value - walls.get(key, 0.0))
                         for key, value in book.walls.items()},
        inclusive_wall_seconds=time.perf_counter() - started_wall,
        process_cpu_seconds=time.process_time() - started_cpu,
        additive_resource_authority=False,
        resource_authority="parent job receipt; these scene deltas are diagnostic",
    )


def _json_array(value):
    return np.asarray(json.dumps(plain(value), sort_keys=True, allow_nan=False))


def _atomic_npz(path, values):
    path = Path(path)
    temporary = None
    try:
        with NamedTemporaryFile(mode="wb", dir=path.parent,
                                prefix="." + path.name + ".", delete=False) as handle:
            temporary = Path(handle.name)
            np.savez_compressed(handle, **values)
        if path.exists():
            raise OnlineFreezeMismatch("OUTPUT_ALREADY_EXISTS:" + str(path))
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _check_metric(matrix, name, *, volume=1.0, complex_metric=False):
    matrix = np.asarray(matrix)
    transpose = matrix.conj().T if complex_metric else matrix.T
    error = float(la.norm(volume * transpose @ matrix - np.eye(matrix.shape[1])))
    if not np.isfinite(error) or error > METRIC_TOLERANCE:
        raise OnlineFreezeMismatch("METRIC_IDENTITY:" + name)
    return error


def freeze_scene(root, sid, config, book, device="cpu"):
    """Recover unchanged known-background features and freeze 32 exact scores.

    ``config`` is the parent-relocated frozen A22 configuration, not a new R1
    score configuration. Original caches always remain untouched. Returns
    ``{receipt, paths}``; the final manifest is published only after all checks.
    A caller must not begin evaluator reads before this manifest is COMPLETE.
    """
    if book is None:
        raise ValueError("A22_R1_REQUIRES_PARENT_COST_BOOK")
    sid, root = int(sid), Path(root).resolve()
    if sid not in SCREENING_IDS or sid not in config["screening_scenes"]:
        raise ValueError("A22_R1_UNREGISTERED_SCREENING_SCENE")
    if int(config["total_direction_descriptors"]) != 8 or int(config["finite_screening_directions"]) != 4:
        raise ValueError("A22_R1_LEGACY_DIRECTION_COUNTS_CHANGED")
    original = root / "results/a22/stage_a" / f"scene_{sid}"
    output = root / "results/a22_r1/online"
    paths = dict(npz=output / f"scene_{sid}.npz",
                 manifest=output / f"scene_{sid}.json",
                 reproduction_audit=output / f"scene_{sid}.reproduction.json")
    if paths["npz"].exists() or paths["manifest"].exists():
        raise OnlineFreezeMismatch("A22_R1_FREEZE_ALREADY_EXISTS:" + str(sid))
    required = ("online_factors.npz", "online_split_16.npz", "online_provenance.json",
                "frozen_online_directions.json", "frozen_online_budgets.json")
    if any(not (original / name).is_file() for name in required):
        raise OnlineFreezeMismatch("A22_R1_MISSING_ORIGINAL_ONLINE_FREEZE:" + str(sid))
    output.mkdir(parents=True, exist_ok=True)
    before_counts, before_walls = dict(book.counts), dict(book.walls)
    started_wall, started_cpu = time.perf_counter(), time.process_time()
    audit = _Audit()
    phase = "ORIGINAL_ONLINE_READ"
    guard = (book.action_guard("a22_r1_online_freeze", role="online", scene_id=sid,
                               purpose="recover_unchanged_known_background_cache")
             if hasattr(book, "action_guard") else
             book.span("a22_r1_online_freeze", online_freezes=1))
    try:
        with guard, book.scope("online") if hasattr(book, "scope") else nullcontext():
            with book.span("a22_r1_original_online_read", original_online_freeze_reads=1):
                saved_directions = _read_json(original / "frozen_online_directions.json")
                saved_budgets = _read_json(original / "frozen_online_budgets.json")
                saved_provenance = _read_json(original / "online_provenance.json")
                with np.load(original / "online_split_16.npz", allow_pickle=False) as archive:
                    common = np.column_stack((archive["V_phys"], archive["V_prior"])).copy()
            if common.shape != (32, 32) or np.iscomplexobj(common) or not np.all(np.isfinite(common)):
                raise OnlineFreezeMismatch("A22_R1_COMMON_FRAME_LAYOUT")
            frame_error = _check_metric(common, "saved_common_frame")
            for index in range(32):
                pivot = int(np.argmax(abs(common[:, index])))
                if common[pivot, index] < 0:
                    raise OnlineFreezeMismatch("A22_R1_SAVED_FRAME_SIGN_CHANGED")
            if len(saved_directions) != 8 or len(saved_budgets) != 8:
                raise OnlineFreezeMismatch("A22_R1_LEGACY_FREEZE_COUNTS")
            if sorted({int(row["direction_id"]) for row in saved_budgets}) != [0, 1, 2, 3]:
                raise OnlineFreezeMismatch("A22_R1_LEGACY_BUDGET_DIRECTION_IDS")
            for row in saved_directions + saved_budgets:
                if row.get("full_J_read") is not False or row.get("label_read") is not False:
                    raise OnlineFreezeMismatch("A22_R1_ORIGINAL_ONLINE_BOUNDARY_FAILED")

            phase = "KNOWN_BACKGROUND_CACHE_RECOVERY"
            scene = load_online_scene(sid, config, book)
            anchor = build_anchor(scene, config, book, device=device)
            model = build_opm(anchor, config)
            if model.basis.shape[1] != 32 or model.AW.shape != (1536, 32):
                raise OnlineFreezeMismatch("A22_R1_CURRENT_RANK_OR_DATA_LAYOUT_CHANGED")
            spatial_error = _check_metric(anchor.adapter.chart.Q, "spatial_chart", volume=scene.problem.volume)
            current_error = _check_metric(model.basis, "current_basis", complex_metric=True)
            audit.json(anchor.sigma_complex, saved_provenance["anchor"]["sigma_complex_reference"],
                       "anchor.sigma_complex_reference")
            audit.json(anchor.adapter.whitening, np.sqrt(2.0) / anchor.sigma_complex,
                       "anchor.whitening_definition")
            audit.json(model.basis.shape[1], saved_provenance["opm"]["actual_current_rank"],
                       "opm.actual_current_rank")

            phase = "ORIGINAL_FACTOR_IDENTITY"
            contract = _cache_contract(model)
            with book.span("a22_r1_factor_identity", original_online_factor_checks=1):
                with np.load(original / "online_factors.npz", allow_pickle=False) as archive:
                    members = set(archive.files)
                    factors = {"AW", "MW", "PMW"}
                    if members not in (factors, factors | set(contract)):
                        raise OnlineFreezeMismatch("A22_R1_FACTOR_CACHE_MEMBER_CONTRACT")
                    saved_factors = {}
                    for key in ("AW", "MW", "PMW"):
                        saved_factors[key] = archive[key].copy()
                        audit.array(getattr(model, key), saved_factors[key], "factor." + key)
                    legacy_factor_contract = members == factors
                    if not legacy_factor_contract:
                        for key, expected in contract.items():
                            saved = archive[key]
                            if np.asarray(expected).dtype.kind in "US":
                                if saved.shape != np.asarray(expected).shape or not np.array_equal(saved, expected):
                                    raise OnlineFreezeMismatch("A22_R1_FACTOR_CACHE_STRING:" + key)
                            else:
                                audit.array(saved, expected, "cache_contract." + key)
            context = build_descriptor_context(model, config)
            audit.json(context.lambda_value, saved_provenance["descriptor"]["regularization"],
                       "descriptor.regularization")
            audit.json(context.provenance, saved_provenance["descriptor"], "descriptor.provenance")

            phase = "LEGACY_DESCRIPTOR_AND_BUDGET_REPRODUCTION"
            legacy_descriptors = []
            for index, direction in enumerate(saved_directions):
                if int(direction["id"]) != index:
                    raise OnlineFreezeMismatch("A22_R1_LEGACY_DIRECTION_ORDER")
                descriptor = direction_descriptor(context, np.asarray(direction["v"], float), config)
                legacy_descriptors.append(descriptor)
                audit.array(descriptor["v"], direction["v"], f"legacy_direction.{index}.v")
                for key in _FROZEN_DESCRIPTOR_FIELDS:
                    audit.json(descriptor[key], direction[key], f"legacy_direction.{index}." + key)
            legacy_cases = _frozen_direction_cases(model, context, saved_directions,
                                                   legacy_descriptors, config, screening=True)
            reproduced_budgets = _freeze_budget_rows(legacy_cases)
            audit.json(reproduced_budgets, saved_budgets, "legacy_budgets")
            reproduction = dict(schema=SCHEMA, scene_id=sid, status="COMPLETE",
                                legacy_direction_count=8, legacy_budget_direction_count=4,
                                amplitude_count=2, noise_count=3, intervention_count=2,
                                legacy_factor_contract=legacy_factor_contract,
                                original_preserved=True, full_J_read=False, truth_read=False,
                                **audit.report())
            write_json(paths["reproduction_audit"], reproduction)

            phase = "COMMON_32_DIRECTION_SCORE_FREEZE"
            score_values = {method: [] for method in ("A1", "A2", "A3")}
            common_descriptors, common_predictions = [], []
            for index in range(32):
                descriptor = direction_descriptor(context, common[:, index], config)
                prediction = predict_budget(context, descriptor, 0.0, 1.0, "nominal", config)
                for method in score_values:
                    score = prediction["pred_" + method]
                    if score is None or not np.isfinite(score) or score < 0:
                        raise OnlineFreezeMismatch(f"A22_R1_UNDEFINED_SCORE:{method}:{index}")
                    score_values[method].append(float(score))
                common_descriptors.append(dict(common_basis_index=index, **{
                    key: descriptor[key] for key in _COMMON_DESCRIPTOR_FIELDS}))
                common_predictions.append(dict(common_basis_index=index, **prediction))
                book.check()
            scores = {method: np.asarray(values, dtype=np.float64)
                      for method, values in score_values.items()}
            orders = {method: np.argsort(values, kind="stable") for method, values in scores.items()}
            scalar_context = {field.name: getattr(context, field.name) for field in fields(context)
                              if field.name not in {"model", "B", "IR", "LH_Q", "provenance"}}
            scalar_context["provenance"] = dict(context.provenance)
            basis_provenance = dict(
                source="exact saved online_split_16.npz concatenated V_phys,V_prior",
                candidate_count=32, current_rank=32, retained_rank=8,
                seed_ranks={"O": 4, "P": 4, "M": 4}, degree=1,
                k_primary=16, k_secondary=[8], material_dimension=32,
                common_frame_metric_error=frame_error, spatial_metric_error=spatial_error,
                current_metric_error=current_error, source_freeze=config["source_freeze"],
                probe_seed=model.provenance["probe_seed"], full_J_used=False,
                truth_used=False, score_context=dict(SCORE_CONTEXT))
            cost = _cost_delta(book, before_counts, before_walls, started_wall, started_cpu)
            for counter in _FORBIDDEN_COUNTERS:
                if cost["counts"].get(counter, 0) != 0:
                    raise OnlineFreezeMismatch("A22_R1_FORBIDDEN_ONLINE_COUNTER:" + counter)
            if cost["counts"].get("direction_descriptor_builds", 0) != 40:
                raise OnlineFreezeMismatch("A22_R1_DESCRIPTOR_ACTION_COUNT")
            if cost["counts"].get("descriptor_predictions", 0) != 80:
                raise OnlineFreezeMismatch("A22_R1_BUDGET_PREDICTION_COUNT")

            phase = "ONLINE_CACHE_PUBLICATION"
            original_sigma = float(saved_provenance["anchor"]["sigma_complex_reference"])
            original_lambda = float(saved_provenance["descriptor"]["regularization"])
            arrays = {
                **contract,
                "schema": np.asarray(SCHEMA), "scene_id": np.asarray(sid),
                **saved_factors,
                "background_field": anchor.state.field,
                "Q_spatial": anchor.adapter.chart.Q,
                "anchor_chi": anchor.chi,
                "whitening": np.asarray(np.sqrt(2.0) / original_sigma),
                "sigma_complex": np.asarray(original_sigma), "common_V": common,
                "lambda_value": np.asarray(original_lambda),
                "descriptor_sigma_complex": np.asarray(anchor.sigma_complex),
                "descriptor_lambda_value": np.asarray(context.lambda_value),
                "tikhonov_relative": np.asarray(config["tikhonov_relative"]),
                "feasibility_tolerance": np.asarray(config["feasibility_tolerance"]),
                "qp_kkt_rtol": np.asarray(config["qp_kkt_rtol"]),
                "qp_maxiter": np.asarray(config["qp_maxiter"]),
                "context_json": _json_array(scalar_context), "config_json": _json_array(config),
                "score_context_json": _json_array(SCORE_CONTEXT),
                "basis_provenance_json": _json_array(basis_provenance),
                "common_descriptors_json": _json_array(common_descriptors),
                "common_predictions_json": _json_array(common_predictions),
                **{"score_" + method: values for method, values in scores.items()},
                **{"order_" + method: values for method, values in orders.items()},
            }
            with book.span("a22_r1_online_cache_write", r1_online_cache_writes=1):
                _atomic_npz(paths["npz"], arrays)
        cost = _cost_delta(book, before_counts, before_walls, started_wall, started_cpu)
        receipt = dict(schema=SCHEMA, scene_id=sid, family=scene.family, status="COMPLETE",
                       device=device, cost=cost, scores=dict(SCORE_CONTEXT),
                       context=scalar_context, basis_provenance=basis_provenance,
                       original_factor_identity_verified=True,
                       legacy_descriptor_budget_reproduction_verified=True,
                       legacy_factor_contract=legacy_factor_contract,
                       factors_stored_from="original frozen online factor cache, after identity validation",
                       scores_computed_from="unchanged rebuilt known-background model",
                       replay_sigma_complex=original_sigma, replay_lambda_value=original_lambda,
                       tiny_identity_allowance_used=bool(audit.tiny_identity_allowances),
                       online_only=True, full_J_read=False, truth_read=False,
                       new_full_wave_labels=0, new_integrity_hash_checks=0,
                       artifacts={key: str(value.relative_to(root)) for key, value in paths.items()})
        write_json(paths["manifest"], receipt)
        return dict(receipt=receipt, paths={key: str(value) for key, value in paths.items()})
    except BaseException as error:
        failure_path = output / f"scene_{sid}.failure.{uuid.uuid4().hex}.json"
        failure = dict(schema=SCHEMA, scene_id=sid, status="FAILED", phase=phase,
                       error_type=type(error).__name__, error=str(error),
                       cost=_cost_delta(book, before_counts, before_walls, started_wall, started_cpu),
                       original_preserved=True, usable_freeze_published=False,
                       online_only=True, full_J_read=False, truth_read=False,
                       new_integrity_hash_checks=0, **audit.report())
        try:
            write_json(failure_path, failure)
            error.r1_failure_audit = str(failure_path)
        except BaseException:
            # Preserve the original scientific/budget error even if reporting fails.
            pass
        raise
