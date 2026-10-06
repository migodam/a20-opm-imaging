"""Static, offline A21 anatomy reporting from already paid saved outputs.

This module never reconstructs a Maxwell model, repeats a QP, loads truth, or
promotes an oracle experiment to an online performance result.  Its automatic
classifications describe measured evidence; Codex owns the scientific review.
"""
from __future__ import annotations

from contextlib import contextmanager
import csv
import json
import math
from pathlib import Path
import zipfile


ARMS = ("BASE_G", "PRIMAL_G", "DUAL_G", "BOTH_G", "RANDOM_G", "BOTH_PG", "RANDOM_PG")
DEFAULT_PARENTS = (2001, 2005, 2003, 2007, 2013)
SUCCESS_STATUSES = {"OK", "PASS", "COMPLETE", "COMPLETED", "SUCCESS"}

# These columns retain absolute scale and both stationarity contributions.
# Nested raw records are also exported, so additions to the engine schema are
# preserved without requiring a report change.
METRICS = (
    "relative_H_step_error", "absolute_H_step_error", "absolute_HR_step_error",
    "absolute_l2_step_error", "reference_H_norm", "well_scaled_reference",
    "epsilon_P", "epsilon_D", "delta_p_norm", "delta_d_norm",
    "primal_denominator", "dual_denominator", "primal_denominator_status",
    "dual_denominator_status", "amplified_primal_norm", "eta_sum_norm",
    "eta_direct_norm", "eta_scale", "epsilon_KKT", "cancellation_indicator",
    "b_dual", "b_primal", "rho_F_norm", "rho_R_norm", "normal_F_norm",
    "normal_R_norm", "reference_KKT_relative", "reduced_KKT_relative",
    "identity_error_norm", "identity_relative_error", "mu", "lambda_min_Lambda",
    "beta", "b_solver", "bound_HF", "bound_ratio", "bound_consistent",
    "normal_allowance_energy", "normal_allowance_bound_HF", "normal_adjusted_bound_HF", "extended_bound_ratio",
    "full_quadratic_gap", "reduced_quadratic_gap", "normal_work",
    "rho_F_work", "full_gap_identity_error_norm", "predicted_reduction",
    "predicted_reduction_status", "relative_full_gap", "zero_feasible",
    "full_primal_backward_error", "full_adjoint_backward_error",
    "tied_adjoint_error", "action_matrix_error", "pullback_matrix_error", "k_Z", "k_W", "union_rank",
    "retained_rank", "primal_protected_added_rank", "dual_protected_added_rank",
    "basis_memory_bytes", "trial_basis_memory_bytes", "test_basis_memory_bytes",
    "core_sigma_min", "core_sigma_max", "core_condition", "core_safe",
    "core_factorization_residual", "core_solve_residual", "projection_kind",
    "full_forward_RHS", "full_adjoint_RHS", "L_actions", "L_adjoint_actions",
    "setup_seconds", "QR_seconds", "projection_seconds", "QP_seconds",
    "total_wall_seconds", "process_cpu_seconds", "GPU_seconds",
    "primal_capture_trial_relative", "primal_capture_test_relative",
    "dual_capture_trial_relative", "dual_capture_test_relative",
    "coordinate_transform_memory_bytes", "shared_state_forward_oracle_RHS",
    "shared_state_adjoint_oracle_RHS", "shared_state_full_tangent_RHS",
)

ALIASES = {
    "absolute_HR_step_error": ("H_R_step_error",),
    "absolute_l2_step_error": ("euclidean_step_error",),
    "primal_denominator": ("primal_endpoint_denominator",),
    "dual_denominator": ("dual_endpoint_denominator",),
    "rho_F_work": ("rhoF_work",),
    "relative_full_gap": ("full_gap_over_predicted_reduction",),
    "eta_scale": ("KKT_scale",),
    "core_sigma_min": ("sigma_min",), "core_sigma_max": ("sigma_max",),
    "core_condition": ("condition",), "core_safe": ("safe",),
    "tied_adjoint_error": ("tied_adjoint_relative_error",),
    "action_matrix_error": ("action_matrix_relative_error",),
    "pullback_matrix_error": ("pullback_matrix_relative_error",),
    "basis_memory_bytes": ("current_basis_memory_bytes",),
    "total_wall_seconds": ("inclusive_wall_seconds", "wall_seconds"),
    "GPU_seconds": ("gpu_occupation_seconds",),
}


def _plain(value):
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        return "NaN" if math.isnan(value) else ("+Infinity" if value > 0 else "-Infinity")
    if hasattr(value, "tolist"):
        return _plain(value.tolist())
    if hasattr(value, "item"):
        return _plain(value.item())
    return value


def _json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_plain(value), indent=2, ensure_ascii=False, allow_nan=False)+"\n", encoding="utf-8")


def _number(value):
    if isinstance(value, bool):
        return None
    try:
        value = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return value if math.isfinite(value) else None


def _get(record, *keys, default=None):
    containers = [record]
    for name in ("scalars", "metrics", "diagnostics", "costs", "cost", "metadata", "core", "stability", "core_stability", "actual_cost"):
        part = record.get(name)
        if isinstance(part, dict):
            containers.append(part)
    for key in keys:
        for part in containers:
            if key in part and part[key] is not None:
                return part[key]
    return default


def _identity(row):
    parent = _get(row, "parent_id", "parent_object_id", "state_id")
    iteration = _get(row, "iteration", default=17)
    try:
        parent, iteration = int(parent), int(iteration)
    except (TypeError, ValueError, OverflowError):
        return None
    arm = str(_get(row, "arm", "method", default=""))
    return parent, iteration, arm


def _csv(path, rows, required=()):
    rows = [_plain(row) for row in rows]
    fields = list(dict.fromkeys(list(required)+sorted({key for row in rows for key in row})))
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(value, ensure_ascii=False, separators=(",", ":"))
                             if isinstance(value, (dict, list)) else value for key, value in row.items()})


@contextmanager
def _group(book, label):
    if book is not None:
        book.check()
    if book is not None and hasattr(book, "span"):
        with book.span("a21_report_"+label):
            yield
    else:
        yield


def _read_json(path, issues):
    if not path.exists():
        issues.append({"path": str(path), "issue": "MISSING_OUTPUT"})
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as error:
        issues.append({"path": str(path), "issue": "UNREADABLE_OUTPUT", "error": str(error)})
        return None


def _read_rows(path, issues):
    if not path.exists():
        issues.append({"path": str(path), "issue": "MISSING_OUTPUT"})
        return []
    rows = []
    try:
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                if not isinstance(row, dict):
                    raise ValueError("row is not an object")
                rows.append(row)
            except ValueError as error:
                issues.append({"path": str(path), "line": lineno, "issue": "UNREADABLE_ROW", "error": str(error)})
    except OSError as error:
        issues.append({"path": str(path), "issue": "UNREADABLE_OUTPUT", "error": str(error)})
    return rows


def _npz_layout(path):
    """Read array headers only; large current banks are never materialized."""
    if not path.exists():
        return {"path": str(path), "status": "MISSING_OUTPUT"}
    import numpy as np
    result = {"path": str(path), "status": "AVAILABLE", "file_bytes": path.stat().st_size, "arrays": {}}
    try:
        with zipfile.ZipFile(path) as archive:
            for name in archive.namelist():
                if not name.endswith(".npy"):
                    continue
                with archive.open(name) as handle:
                    version = np.lib.format.read_magic(handle)
                    if version == (1, 0):
                        shape, fortran, dtype = np.lib.format.read_array_header_1_0(handle)
                    else:
                        shape, fortran, dtype = np.lib.format.read_array_header_2_0(handle)
                result["arrays"][name[:-4]] = {"shape": list(shape), "dtype": str(dtype), "fortran_order": bool(fortran)}
    except (ValueError, OSError, zipfile.BadZipFile, EOFError) as error:
        result.update(status="UNREADABLE_OUTPUT", error=str(error))
    return result


def _artifact_path(root, row, keys, fallback):
    saved = _get(row, *keys)
    if saved:
        candidate = Path(str(saved))
        if not candidate.is_absolute():
            candidate = root/candidate
        if candidate.exists():
            return candidate
    return root/fallback


def annotate_rows(rows, config, *, artifact_audits=None):
    """Return the complete registered state-by-arm grid, retaining failures."""
    expected = [(int(parent), int(iteration), arm) for parent in config.get("parents", DEFAULT_PARENTS)
                for iteration in config.get("iterations", (17,)) for arm in ARMS]
    groups = {}
    for row in rows:
        identity = _identity(row)
        if identity is not None:
            groups.setdefault(identity, []).append(row)
    output = []
    for parent, iteration, arm in expected:
        originals = groups.get((parent, iteration, arm), [])
        executed = [value for value in originals if str(value.get("status", "")).upper() != "NOT_RUN"]
        row = dict(executed[-1] if executed else originals[-1]) if originals else {}
        row.update(parent_id=parent, iteration=iteration, arm=arm,
                   evidence_scope="ORACLE_OFFLINE_FROZEN_QUADRATIC",
                   dataset_exposure=config.get("dataset_exposure", "historically_exposed_feasibility"),
                   final_scientific_review="CODEX_REVIEW_REQUIRED")
        issues = []
        if not originals:
            row["status"] = "MISSING_OUTPUT"
            issues.append("MISSING_OUTPUT")
        elif len(executed) > 1:
            issues.append("DUPLICATE_STATE_ARM")
            row["duplicate_count"] = len(executed)
        if len(originals) > 1:
            row["record_lifecycle"] = originals
            row["record_lifecycle_policy"] = "NOT_RUN_TO_ONE_TERMINAL_EXECUTION_ALLOWED_NO_EXECUTED_RETRY"
        provenance = {}
        if artifact_audits is not None:
            provenance = artifact_audits.get((parent, iteration, arm), {}).get("provenance") or {}
        if _get(row, "reference_valid", "full_reference_valid") is None and provenance:
            row["reference_valid"] = bool(provenance.get("reference_raw_constrained_QP_step") is True and
                _number(provenance.get("reference_KKT_relative")) is not None and
                _number(provenance.get("reference_KKT_relative")) <= config.get("qp_kkt_rtol", 1e-8))
            row["reference_validation_source"] = "SAVED_CACHE_PROVENANCE_AND_ARM_NORMAL_KKT_AUDIT"
        for key in METRICS:
            row[key] = _get(row, key, *ALIASES.get(key, ()))
        counts = row.get("cost", {}).get("counts", {})
        walls = row.get("cost", {}).get("exclusive_walls", {})
        if row.get("cost"):
            row["QR_seconds"] = walls.get("a21_arm_protected_QR")
            row["projection_seconds"] = sum(_number(value) or 0. for key, value in walls.items()
                                           if key.startswith("a21_shared_image_projection") or key.startswith("a21_projected_core"))
            row["QP_seconds"] = sum(_number(value) or 0. for key, value in walls.items()
                                   if any(token in key for token in ("material_subproblem", "constrained_QP", "constrained_quadratic", "KKT_polish")))
            for name in ("L_actions", "L_adjoint_actions", "full_forward_RHS", "full_adjoint_RHS"):
                row[name] = counts.get(name, 0)
        for task in ("primal", "dual"):
            oracle = row.get(task+"_oracle_backward", {})
            if isinstance(oracle, dict) and oracle:
                row["full_"+("primal" if task == "primal" else "adjoint")+"_backward_error"] = oracle.get("relative")
            for side in ("trial", "test"):
                capture = row.get(task+"_capture_"+side, {})
                if isinstance(capture, dict):
                    row[task+"_capture_"+side+"_relative"] = capture.get("aggregate_relative_residual")
        if provenance:
            row["shared_state_preparation_cost"] = provenance.get("preparation_cost")
            row["shared_state_forward_oracle_RHS"] = provenance.get("source_count")
            row["shared_state_adjoint_oracle_RHS"] = provenance.get("source_count")
            row["shared_state_full_tangent_RHS"] = provenance.get("preparation_cost", {}).get("counts", {}).get("full_tangent_RHS")
            row["shared_cost_policy"] = "SHARED_PER_STATE_NONADDITIVE_ACROSS_ARMS"
        for task in ("primal", "dual"):
            row[task+"_denominator_status"] = "DEFINED" if _number(row.get("epsilon_"+("P" if task == "primal" else "D"))) is not None else "UNDEFINED_OR_ILL_SCALED"
        row["predicted_reduction_status"] = ("DEFINED" if row.get("predicted_reduction_well_scaled") is True
                                              else "UNDEFINED_OR_ILL_SCALED" if row.get("zero_feasible") is True
                                              else "ZERO_BASELINE_NOT_FEASIBLE_OR_NOT_RECORDED")
        if row.get("core_primal_solve_backward_residual") is not None or row.get("core_adjoint_solve_backward_residual") is not None:
            row["core_solve_residual"] = max(_number(row.get("core_primal_solve_backward_residual")) or 0.,
                                             _number(row.get("core_adjoint_solve_backward_residual")) or 0.)
        status = str(_get(row, "status", default="STATUS_NOT_RECORDED")).upper()
        row["status"] = status
        if status not in SUCCESS_STATUSES:
            issues.append(status)
        if _get(row, "reference_valid", "full_reference_valid") is not True:
            issues.append("REFERENCE_NOT_VALIDATED")
        if _get(row, "bound_consistent") is not True:
            issues.append("BOUND_CONSISTENCY_NOT_VALIDATED")
        identity_error = _number(_get(row, "identity_relative_error"))
        if identity_error is None or identity_error > config.get("identity_rtol", 1e-9):
            issues.append("DEFECT_IDENTITY_NOT_VALIDATED")
        reference_scale = _number(_get(row, "reference_H_norm"))
        well_scaled = _get(row, "well_scaled_reference") is True
        if reference_scale is None or reference_scale <= config.get("reference_H_norm_floor", 1e-12):
            well_scaled = False
        row["well_scaled_reference"] = well_scaled
        if not well_scaled:
            issues.append("ILL_SCALED_REFERENCE_H_NORM")
        if _number(_get(row, "relative_H_step_error")) is None:
            issues.append("UNDEFINED_RELATIVE_H_ERROR")
        if _get(row, "core_safe", "safe") is not True:
            issues.append("CORE_NOT_VALIDATED_SAFE")
        target_rank = config.get("current_rank", 56)
        if _number(row.get("k_Z")) != target_rank or _number(row.get("k_W")) != target_rank:
            issues.append("FIXED_CURRENT_RANK_NOT_MATCHED")
        if _number(row.get("retained_rank")) != config.get("retained_rank", 8):
            issues.append("RETAINED_CURRENT_RANK_NOT_MATCHED")
        tolerance = config.get("backend_consistency_rtol", 1e-9)
        for field in ("tied_adjoint_error", "action_matrix_error", "pullback_matrix_error"):
            value = _number(_get(row, field))
            if value is None or value > tolerance:
                issues.append(field.upper()+"_NOT_VALIDATED")
        for field in ("reference_KKT_relative", "reduced_KKT_relative"):
            value = _number(_get(row, field))
            if value is None or value > config.get("qp_kkt_rtol", 1e-8):
                issues.append(field.upper()+"_NOT_VALIDATED")
        normals_valid = _get(row, "normals_valid") is True or (
            _get(row, "normal_F_valid", "full_normal_valid") is True and
            _get(row, "normal_R_valid", "reduced_normal_valid") is True)
        if not normals_valid:
            issues.append("NORMALS_NOT_VALIDATED")
        if artifact_audits is not None:
            audit = artifact_audits.get((parent, iteration, arm), {})
            row["artifact_audit"] = audit
            if audit.get("cache", {}).get("status") != "AVAILABLE":
                issues.append("CACHE_OUTPUT_MISSING_OR_UNREADABLE")
            if audit.get("diagnostics", {}).get("status") != "AVAILABLE":
                issues.append("DIAGNOSTIC_VECTORS_MISSING_OR_UNREADABLE")
            elif status in SUCCESS_STATUSES:
                required_vectors = {"s_F", "s_R", "n_F", "n_R", "H_F", "H_R", "delta_p", "delta_d", "rho_F", "rho_R", "eta_pair"}
                missing = required_vectors-set(audit["diagnostics"].get("arrays", {}))
                if missing:
                    row["missing_diagnostic_vectors"] = sorted(missing)
                    issues.append("DIAGNOSTIC_VECTOR_SET_INCOMPLETE")
        row["report_issue_classes"] = sorted(set(issues))
        row["assessable"] = not issues
        value = _number(row.get("relative_H_step_error"))
        row["meets_5pct_H_gate"] = bool(row["assessable"] and value <= config.get("scientific_H_error_target", .05))
        row["ratio_policy"] = "NO_DENOMINATOR_FLOOR_FOR_GATES"
        output.append(row)
    return output


def _control_match(oracle, control, *, petrov=False):
    sides = ("trial_QR", "test_QR") if petrov else ("trial_QR",)
    for side in sides:
        a = _number(oracle.get(side, {}).get("independent_protected_added_rank"))
        b = _number(control.get(side, {}).get("independent_protected_added_rank"))
        if a is None or b is None or a != b:
            return False
    return all(_number(oracle.get(field)) == _number(control.get(field))
               for field in ("k_Z", "k_W", "retained_rank"))


def _state_interpretation(state_rows, config):
    arms = {row["arm"]: row for row in state_rows}
    target = config.get("scientific_H_error_target", .05)
    both, primal, random = (arms[name] for name in ("BOTH_G", "PRIMAL_G", "RANDOM_G"))
    # This deliberately records a conservative sufficient causal pattern.  It
    # does not turn a weighted defect upper bound into a necessity theorem.
    dual = _number(primal.get("b_dual"))
    amplified = _number(primal.get("b_primal"))
    dual_relevant = bool(primal["assessable"] and dual is not None and amplified is not None and
                         dual > amplified and dual > config.get("reference_H_norm_floor", 1e-12) and
                         _number(primal.get("relative_H_step_error")) > target)
    random_matches = _control_match(both, random)
    random_discriminates = bool(random["assessable"] and random_matches and not random["meets_5pct_H_gate"])
    full_pattern = both["meets_5pct_H_gate"] and dual_relevant and random_discriminates
    alternatives = []
    if primal["meets_5pct_H_gate"]:
        alternatives.append("PRIMAL_G_ALREADY_PASSES_CHECK_INDIRECT_DUAL_CAPTURE_OR_OLD_PRIMAL_DEFECT")
    if arms["DUAL_G"]["meets_5pct_H_gate"]:
        alternatives.append("DUAL_G_PASSES_RESIDUAL_PULLBACK_MAY_DOMINATE_THIS_TASK")
    if random["meets_5pct_H_gate"]:
        alternatives.append("RANDOM_G_PASSES_ORACLE_SPECIFIC_EXPLANATION_WEAKLY_DISCRIMINATED")
    if not random_matches:
        alternatives.append("RANDOM_G_INDEPENDENT_PROTECTED_ADDITION_MATCH_NOT_VALIDATED")
    if both["meets_5pct_H_gate"] and not arms["BOTH_PG"]["meets_5pct_H_gate"]:
        alternatives.append("GALERKIN_FIDELITY_DOES_NOT_ESTABLISH_THIS_PETROV_INSTANCE")
    if not both["well_scaled_reference"]:
        alternatives.append("PERCENTAGE_GATE_UNASSESSABLE_USE_ABSOLUTE_SCALE_AND_FULL_GAP")
    if any(("CONSISTENCY" in row["status"] and "FAIL" in row["status"]) or row.get("bound_consistent") is False or
           "ConsistencyFailure" in str(row.get("failure_reason", "")) for row in state_rows):
        status = "IMPLEMENTATION_INCONSISTENCY"
    elif not both["assessable"]:
        if any("RANK" in issue or "CORE" in issue for issue in both["report_issue_classes"]):
            status = "RANK_OR_CORE_LIMITATION"
        else:
            status = "UNASSESSABLE_OR_BLOCKED"
    elif full_pattern:
        status = "MEASURED_GALERKIN_CAUSAL_PATTERN_PRESENT_REVIEW_REQUIRED"
    elif both["meets_5pct_H_gate"]:
        status = "GALERKIN_FIDELITY_WITH_UNRESOLVED_OR_ALTERNATIVE_ATTRIBUTION"
    elif all(_number(both.get(field)) is not None and _number(both[field]) <= target for field in ("epsilon_P", "epsilon_D")):
        status = "CONDITIONING_LIMITED_APPROXIMATION_CANDIDATE_REVIEW_REQUIRED"
    else:
        status = "MEASURED_BOTH_G_TARGET_NOT_MET"
    pg, pg_control = arms["BOTH_PG"], arms["RANDOM_PG"]
    pg_matches = _control_match(pg, pg_control, petrov=True)
    pg_status = ("PG_INSTANCE_PASSES_WITH_RANDOM_DISCRIMINATION" if pg["meets_5pct_H_gate"] and pg_control["assessable"] and pg_matches and not pg_control["meets_5pct_H_gate"]
                 else "PG_AND_RANDOM_BOTH_PASS" if pg["meets_5pct_H_gate"] and pg_control["meets_5pct_H_gate"]
                 else "PG_INSTANCE_TARGET_NOT_MET" if pg["assessable"] else "PG_INSTANCE_UNASSESSABLE_OR_NOT_RUN")
    return {"status": status, "BOTH_G_pass": both["meets_5pct_H_gate"],
            "PRIMAL_G_relevant_dual_contribution": dual_relevant,
            "RANDOM_G_independent_protected_additions_matched": random_matches,
            "RANDOM_G_does_not_explain_result": random_discriminates,
            "full_causal_pattern": full_pattern, "alternative_explanations": alternatives,
            "petrov_instance_status": pg_status,
            "RANDOM_PG_independent_protected_additions_matched": pg_matches,
            "petrov_advantage": "NOT_ESTABLISHED_BY_FROZEN_ORACLE_FIDELITY",
            "final_scientific_review": "CODEX_REVIEW_REQUIRED"}


def evaluate_report_gates(rows, config, *, t0=None):
    """Conservative automatic evidence classification, never final review."""
    t0 = dict(t0 or {})
    t0_status = str(t0.get("status", "NOT_RECORDED")).upper()
    t0_pass = t0_status in SUCCESS_STATUSES or t0_status in {"ALL_ASSERTIONS_PASSED", "ALL ASSERTIONS PASSED"}
    if "backend" in t0 or "synthetic" in t0:
        t0_pass = bool(t0_pass and isinstance(t0.get("synthetic"), dict) and t0["synthetic"].get("status") == "PASS" and
                       all(t0.get("backend", {}).get(str(parent), {}).get("status") == "PASS"
                           for parent in config.get("validation_parents", (2001, 2003, 2013))))
    states = []
    for parent in config.get("parents", DEFAULT_PARENTS):
        for iteration in config.get("iterations", (17,)):
            state_rows = [row for row in rows if row["parent_id"] == parent and row["iteration"] == iteration]
            states.append({"parent_id": parent, "iteration": iteration, **_state_interpretation(state_rows, config)})
    inconsistent = any(state["status"] == "IMPLEMENTATION_INCONSISTENCY" for state in states)
    all_pass = len(states) == 5 and all(state["BOTH_G_pass"] for state in states)
    all_pattern = len(states) == 5 and all(state["full_causal_pattern"] for state in states)
    if inconsistent:
        status = "IMPLEMENTATION_INCONSISTENCY_STOP_AND_DEBUG"
    elif not t0_pass:
        status = "T0_UNRESOLVED"
    elif all_pass and all_pattern:
        status = "FULL_MEASURED_SUPPORT_PENDING_CODEX_REVIEW"
    elif all_pass:
        status = "FIVE_STATE_FIDELITY_WITH_UNRESOLVED_CAUSAL_ATTRIBUTION"
    elif any(state["BOTH_G_pass"] for state in states):
        status = "PARTIAL_MEASURED_SUPPORT"
    else:
        status = "NEGATIVE_OR_UNASSESSABLE_FIVE_STATE_RESULT"
    return {"schema": "a21.report_gates.v1", "status": status,
            "T0": {**t0, "reported_pass": t0_pass}, "T1": {"states": states,
                "all_five_BOTH_G_pass": all_pass, "all_five_causal_pattern": all_pattern,
                "target_relative_HF_error": config.get("scientific_H_error_target", .05)},
            "provisional_label": "LATE_GN_TWO_SIDED_FIDELITY_CONFIRMED" if status == "FULL_MEASURED_SUPPORT_PENDING_CODEX_REVIEW" else status,
            "final_scientific_status": "CODEX_REVIEW_REQUIRED",
            "T2": "NOT_RUN_NOT_AUTHORIZED", "online_speedup": "NOT_MEASURED_NO_CLAIM",
            "nonlinear_imaging_success": "NOT_MEASURED_NO_CLAIM", "truth_evaluation": "NOT_ACCESSED",
            "evidence_scope": "ORACLE_OFFLINE_FROZEN_QUADRATIC",
            "dataset_exposure": config.get("dataset_exposure", "historically_exposed_feasibility")}


def _runtime_info(root, summary, issues):
    receipts = []
    seen = set()
    candidates = list((root/"results/jobs").glob("a21-*/job_receipt.json"))
    for directory in (root/"results/a21/jobs", root/"results/a21/receipts"):
        candidates.extend(directory.glob("*/job_receipt.json"))
        candidates.extend(directory.glob("*.json"))
    for path in candidates:
        value = _read_json(path, issues)
        if not isinstance(value, dict):
            continue
        receipt_text = " ".join(str(value.get(key, "")) for key in ("scope", "job_id", "a21_phase", "r1_phase", "command", "task"))
        if "a21" not in (str(path)+receipt_text).lower():
            continue
        if str(path) in seen:
            continue
        seen.add(str(path))
        receipts.append({"path": str(path), "receipt": value})
    external_path = root/"results/a21/external_cpu_receipts.json"
    external = _read_json(external_path, issues)
    external = external if isinstance(external, list) else []
    return {"summary_runtime": {key: value for key, value in summary.items()
             if any(token in key.lower() for token in ("cost", "cpu", "gpu", "runtime", "timing", "budget", "receipt", "job"))},
            "driver_receipts": receipts, "external_cpu_receipt_path": str(external_path),
            "external_cpu_receipts": external,
            "external_cpu_seconds": sum(_number(value.get("process_cpu_seconds")) or 0. for value in external),
            "cost_policy": "DRIVER_RECEIPTS_AUTHORITATIVE_SHARED_COSTS_NOT_MULTIPLIED_PER_ARM",
            "online_speedup": "NOT_MEASURED_NO_CLAIM"}


def _display(value):
    value = _number(value)
    return "undefined" if value is None else f"{value:.5g}"


def _worst_source(row, task, side):
    capture = row.get(task+"_capture_"+side, {})
    values = capture.get("per_source_relative_residual", []) if isinstance(capture, dict) else []
    if not values or any(_number(value) is None for value in values):
        return None
    return max(float(value) for value in values)


def _markdown(rows, gate, summary, runtime, artifacts, figures):
    lines = ["# A21 Oracle Anatomy Report", "", "## T0: algebra and implementation consistency", "",
             f"Recorded status: `{gate['T0'].get('status', 'NOT_RECORDED')}`. Automatically accepted as resolved: `{gate['T0']['reported_pass']}`.", "",
             "T0 concerns packing, whitening, tied adjoints, source order, constrained KKT, the two-sided theorem, defect identities and solver-aware bounds. Synthetic tests establish implementation checks; the real cached-state checks must also be recorded before physical interpretation.", "",
             "## T1: complete frozen five-state diagnosis", "", f"Provisional measured classification: `{gate['status']}`. Final scientific interpretation: `CODEX_REVIEW_REQUIRED`.", "",
             "The table retains every registered state and arm. Percentages use the unmodified reference H norm; an ill-scaled denominator or unavailable diagnostic makes the gate unassessable. No surviving-state median replaces missing states.", "",
             "| State | Arm | Status | Assessable | H_F error | Absolute H_F error | Reference H norm | Raw H_F bound | Normal-adjusted bound | Consistency |", 
             "|---|---|---|---|---:|---:|---:|---:|---:|---|"]
    for row in rows:
        lines.append(f"| {row['parent_id']}/{row['iteration']} | {row['arm']} | {row['status']} | {row['assessable']} | {_display(row.get('relative_H_step_error'))} | {_display(row.get('absolute_H_step_error'))} | {_display(row.get('reference_H_norm'))} | {_display(row.get('bound_HF'))} | {_display(row.get('normal_adjusted_bound_HF'))} | {row.get('bound_consistent')} |")
    lines.extend(["", "### Stationarity, curvature and full quadratic gap", "",
                  "The saved metrics retain the primal endpoint, material-vector dual endpoint, amplified primal contribution, their vector sum, cancellation, both solver defects, scaled stationarity, the two Hessians, mu and beta. The raw solver-aware bound and the normal-allowance bound are distinct.", "",
                  "The full-gap identity is evaluated with both normal work and rho_F work: `q_F(s_R)-q_F(s_F) = 0.5 ||s_R-s_F||_HF^2 - n_F^T(s_R-s_F) + rho_F^T(s_R-s_F)`. Predicted-reduction ratios are undefined when their declared denominator is negligible.", "",
                  "| State | Arm | Primal defect | Dual defect | Amplified primal | eta sum | b_dual | b_primal | rho_F | rho_R | mu | beta | Full gap | Normal work | rho_F work |", 
                  "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"])
    for row in rows:
        values = [row.get(key) for key in ("delta_p_norm", "delta_d_norm", "amplified_primal_norm", "eta_sum_norm", "b_dual", "b_primal", "rho_F_norm", "rho_R_norm", "mu", "beta", "full_quadratic_gap", "normal_work", "rho_F_work")]
        lines.append("| "+f"{row['parent_id']}/{row['iteration']} | {row['arm']} | "+" | ".join(_display(value) for value in values)+" |")
    lines.extend(["", "Per-source values and their defined/ill-scaled flags are preserved in each capture record. Aggregate capture never substitutes for all source columns.", "",
                  "| State | Arm | Primal trial aggregate | Primal trial worst source | Dual test aggregate | Dual test worst source | Full primal residual | Full adjoint residual |", 
                  "|---|---|---:|---:|---:|---:|---:|---:|"])
    for row in rows:
        values = [row.get("primal_capture_trial_relative"), _worst_source(row, "primal", "trial"),
                  row.get("dual_capture_test_relative"), _worst_source(row, "dual", "test"),
                  row.get("full_primal_backward_error"), row.get("full_adjoint_backward_error")]
        lines.append("| "+f"{row['parent_id']}/{row['iteration']} | {row['arm']} | "+" | ".join(_display(value) for value in values)+" |")
    lines.extend(["", "### Mechanism and Petrov architecture", "",
                  "Automatic full support requires all five well-scaled BOTH_G states at or below 5%, all required consistency checks, a failing PRIMAL_G with a measured relevant weighted dual contribution, and a failing rank-matched RANDOM_G. This is a conservative evidence pattern for Codex review. Exact current capture alone is not a step theorem.", "",
                  "| State | Provisional mechanism status | PRIMAL dual evidence | RANDOM_G discriminates | Petrov instance | Alternative explanations |", 
                  "|---|---|---|---|---|---|"])
    for state in gate["T1"]["states"]:
        lines.append(f"| {state['parent_id']}/{state['iteration']} | {state['status']} | {state['PRIMAL_G_relevant_dual_contribution']} | {state['RANDOM_G_does_not_explain_result']} | {state['petrov_instance_status']} | {'; '.join(state['alternative_explanations']) or 'none recorded'} |")
    lines.extend(["", "Petrov fidelity is assessed separately. Equal k_Z and k_W do not mean equal basis memory; a Petrov arm stores two bases. A frozen-step oracle pass establishes no online advantage, nonlinear reconstruction success or cost benefit.", "",
                  "### Current solves, core, rank, memory and paid cost", "",
                  "Per-source and aggregate primal/dual capture residuals, source ordering, oracle backward errors, core singular values/condition/factorization residual, actual ranks and memory, operator calls and RHS counts remain in the CSV and per-state JSON. Shared state setup is billed once in driver receipts; per-arm deltas are not a standalone deployment wall time.", "",
                  "| State | Arm | k_Z | k_W | Union rank | Basis bytes | Core sigma_min | Core condition | Forward RHS | Adjoint RHS | CPU seconds | Wall seconds |", 
                  "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"])
    for row in rows:
        values = [row.get(key) for key in ("k_Z", "k_W", "union_rank", "basis_memory_bytes", "core_sigma_min", "core_condition", "full_forward_RHS", "full_adjoint_RHS", "process_cpu_seconds", "total_wall_seconds")]
        lines.append("| "+f"{row['parent_id']}/{row['iteration']} | {row['arm']} | "+" | ".join(_display(value) for value in values)+" |")
    lines.extend(["", "## Completeness, runtime and output provenance", "",
                  f"Saved engine summary status: `{summary.get('status', 'NOT_RECORDED')}`. A budget stop, failure, missing cache, missing vector output or duplicate record is retained as an explicit limitation.", "",
                  f"External CPU receipt total: {_display(runtime['external_cpu_seconds'])} seconds; {len(runtime['driver_receipts'])} saved A21 driver receipts found. The runtime JSON preserves receipts, caps, environment details and summary timing fields as recorded.", "",
                  "Run information is descriptive of the saved receipts. This report performs no Maxwell solve, QP, truth evaluation, online benchmark or NN work. All measured rows are `ORACLE/OFFLINE` and the dataset is historically exposed feasibility data.", "",
                  "## Artifacts", "", "- `A21_METRICS.csv`: complete state-by-arm metrics, blocked rows and raw nested fields.",
                  "- `per_state/*.json`: state-by-arm measurements, provisional interpretation and vector/cache layouts.",
                  "- `GATE_DECISION.json`: T0/T1 evidence classification and explicit review boundary.",
                  "- `rawdata/`: verbatim source rows, input/output completeness, saved runtime and figure source tables."])
    for name, paths in figures.items():
        if isinstance(paths, list):
            lines.append(f"- `{name}`: "+", ".join(f"`{Path(path).name}`" for path in paths))
    if artifacts:
        lines.extend(["", "Output limitations:"])
        for issue in artifacts:
            lines.append("- "+json.dumps(_plain(issue), ensure_ascii=False))
    lines.extend(["", "T2: `NOT_RUN_NOT_AUTHORIZED`. Codex final scientific assessment remains authoritative.", ""])
    return "\n".join(lines)


def _figures(rows, output, config):
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    output.mkdir(parents=True, exist_ok=True)
    state_ids = list(dict.fromkeys((row["parent_id"], row["iteration"]) for row in rows))
    figures, source = {}, {}
    specifications = [
        ("A21_HF_ERROR_AND_BOUNDS", (("relative_H_step_error", "measured HF error"), ("relative_bound_HF", "raw solver-aware bound"), ("relative_normal_bound_HF", "normal-adjusted bound")), "H_F error / reference H norm", True),
        ("A21_WEIGHTED_STATIONARITY", (("b_dual", "dual defect in HR inverse norm"), ("b_primal", "amplified primal in HR inverse norm"), ("b_solver", "combined solver-aware residual")), "absolute HR inverse norm", False),
        ("A21_ENDPOINTS_AND_SCALE", (("epsilon_P", "primal endpoint error"), ("epsilon_D", "dual endpoint error"), ("reference_H_norm", "absolute reference H norm")), "unfloored ratios and declared H scale", False),
        ("A21_CONDITIONING", (("mu", "minimum HR eigenvalue"), ("beta", "HF/HR metric amplification"), ("core_condition", "projected current core condition")), "measured curvature and core scale", False),
        ("A21_NORMAL_WORK", (("full_quadratic_gap", "measured full quadratic gap"), ("normal_work", "full normal work"), ("rho_F_work", "full solver defect work")), "full quadratic terms (absolute)", False),
        ("A21_BASIS_MEMORY", (("basis_memory_bytes", "actual total basis bytes"),), "basis memory (bytes)", False),
    ]
    for name, fields, ylabel, gate_line in specifications:
        figure = Figure(figsize=(14, 8), layout="constrained")
        FigureCanvasAgg(figure)
        axes = list(figure.subplots(2, 3).flat)
        points = []
        for ax, (parent, iteration) in zip(axes, state_ids):
            state = {row["arm"]: row for row in rows if row["parent_id"] == parent and row["iteration"] == iteration}
            for series, (key, label) in enumerate(fields):
                xs, ys = [], []
                for index, arm in enumerate(ARMS):
                    row = state[arm]
                    value = _number(row.get(key))
                    if value is not None:
                        xs.append(index+(series-(len(fields)-1)/2)*.12)
                        ys.append(value)
                    points.append({"parent_id": parent, "iteration": iteration, "arm": arm,
                                   "metric": key, "value": value, "status": row["status"], "assessable": row["assessable"]})
                ax.plot(xs, ys, linestyle="none", marker=("o", "x", "+")[series % 3], label=label, alpha=.8)
            for index, arm in enumerate(ARMS):
                row = state[arm]
                if not row["assessable"]:
                    ax.text(index, .96, "blocked" if row["status"] not in SUCCESS_STATUSES else "unassessable",
                            transform=ax.get_xaxis_transform(), ha="center", rotation=90, fontsize=6, va="top")
            if gate_line:
                ax.axhline(config.get("scientific_H_error_target", .05), color="tab:red", linestyle="--", label="5% scientific gate")
            ax.set_yscale("symlog", linthresh=1e-12)
            ax.set_xticks(range(len(ARMS)), ARMS, rotation=45, fontsize=7)
            ax.set_title(f"State {parent}, iteration {iteration}")
            ax.set_ylabel(ylabel, fontsize=8)
            ax.grid(alpha=.2)
        for ax in axes[len(state_ids):]:
            ax.set_visible(False)
        if figure.axes:
            handles, labels = figure.axes[0].get_legend_handles_labels()
            figure.legend(handles, labels, loc="lower right", fontsize=8)
        figure.suptitle(name.replace("A21_", "A21 ").replace("_", " ")+" — ORACLE/OFFLINE; review required", fontsize=12)
        paths = []
        for extension in ("png", "svg"):
            path = output/(name+"."+extension)
            figure.savefig(path, dpi=150)
            paths.append(str(path))
        figure.clear()
        figures[name] = paths
        source[name] = points
    return figures, source


def write_report(root, config=None, *, book=None, make_figures=True, t0=None):
    """Read saved A21 anatomy and emit a complete reviewable local report."""
    root = Path(root).resolve()
    if config is None:
        config = json.loads((root/"configs/a21.json").read_text(encoding="utf-8"))
    config = dict(config)
    out = root/"results/a21"
    source = out/"anatomy"
    rawdata, states_out = out/"rawdata", out/"per_state"
    issues, paths = [], []
    out.mkdir(parents=True, exist_ok=True)
    with _group(book, "load_saved_outputs"):
        rows = _read_rows(source/"rows.jsonl", issues)
        summary_path = source/"summary.json"
        if not summary_path.exists() and (source/"ANATOMY_SUMMARY.json").exists():
            summary_path = source/"ANATOMY_SUMMARY.json"
        summary = _read_json(summary_path, issues) or {}
        if not isinstance(summary, dict):
            issues.append({"path": str(summary_path), "issue": "SUMMARY_NOT_AN_OBJECT"})
            summary = {}
        t0 = t0 or summary.get("T0") or summary.get("t0")
        local_t0_path = out/"validation/T0.json"
        local_t0 = _read_json(local_t0_path, issues) if local_t0_path.exists() else None
        layout_cache, artifact_audits, provenance_cache = {}, {}, {}
        for parent in config.get("parents", DEFAULT_PARENTS):
            for iteration in config.get("iterations", (17,)):
                state_rows = [row for row in rows if _identity(row) and _identity(row)[:2] == (parent, iteration)]
                for arm in ARMS:
                    arm_rows = [row for row in state_rows if _identity(row)[2] == arm]
                    row = arm_rows[0] if arm_rows else {}
                    cache_path = _artifact_path(root, row, ("cache_path", "shared_cache_path"), f"results/a21/anatomy/caches/{parent}_{iteration}.npz")
                    diagnostic_path = _artifact_path(root, row, ("diagnostic_path", "diagnostics_path", "vector_path"), f"results/a21/anatomy/diagnostics/{parent}_{iteration}_{arm}.npz")
                    for path in (cache_path, diagnostic_path):
                        if path not in layout_cache:
                            layout_cache[path] = _npz_layout(path)
                    provenance_path = cache_path.with_suffix(".json")
                    if provenance_path not in provenance_cache:
                        provenance_cache[provenance_path] = _read_json(provenance_path, issues) if provenance_path.exists() else None
                    artifact_audits[(parent, iteration, arm)] = {"cache": layout_cache[cache_path], "diagnostics": layout_cache[diagnostic_path],
                                                               "provenance": provenance_cache[provenance_path]}
        runtime = _runtime_info(root, summary, issues)
    with _group(book, "tables_and_gates"):
        annotated = annotate_rows(rows, config, artifact_audits=artifact_audits)
        for row in annotated:
            denominator = _number(row.get("reference_H_norm"))
            for key, bound in (("relative_bound_HF", "bound_HF"), ("relative_normal_bound_HF", "normal_adjusted_bound_HF")):
                numerator = _number(row.get(bound))
                row[key] = numerator/denominator if row["well_scaled_reference"] and numerator is not None else None
        gate = evaluate_report_gates(annotated, config, t0=t0)
        gate["local_driver_validation"] = {"path": str(local_t0_path), "result": local_t0,
                                           "context": "LOCAL_SYNTHETIC_DRIVER_CHECK_SEPARATE_FROM_CACHED_REAL_STATE_T0"}
        gate["engine_summary_status"] = summary.get("status", "NOT_RECORDED")
        gate["execution_limitations"] = {"stopped_reason": summary.get("stopped_reason"),
                                        "status_counts": summary.get("status_counts"),
                                        "missing_or_blocked_rows": [{"parent_id": row["parent_id"], "iteration": row["iteration"],
                                            "arm": row["arm"], "status": row["status"], "issues": row["report_issue_classes"]}
                                            for row in annotated if not row["assessable"]]}
        gate["input_issues"] = issues
        gate["complete_output_count"] = sum(row["status"] != "MISSING_OUTPUT" for row in annotated)
        gate["expected_state_arm_count"] = len(annotated)
        _csv(out/"A21_METRICS.csv", annotated, ("parent_id", "iteration", "arm", "status", "assessable", "report_issue_classes")+METRICS)
        _csv(rawdata/"SOURCE_ROWS.csv", rows)
        _json(rawdata/"SOURCE_ROWS.json", rows)
        _json(rawdata/"ENGINE_SUMMARY.json", summary)
        _json(rawdata/"LOCAL_DRIVER_T0.json", {"path": str(local_t0_path), "result": local_t0})
        _json(rawdata/"RUNTIME_RECEIPTS.json", runtime)
        _json(rawdata/"OUTPUT_COMPLETENESS.json", {"issues": issues, "arrays": list(layout_cache.values()),
              "unregistered_records": [row for row in rows if _identity(row) not in {(value["parent_id"], value["iteration"], value["arm"]) for value in annotated}]})
        for state in gate["T1"]["states"]:
            state_rows = [row for row in annotated if row["parent_id"] == state["parent_id"] and row["iteration"] == state["iteration"]]
            path = states_out/f"{state['parent_id']}_{state['iteration']}.json"
            _json(path, {"schema": "a21.state_report.v1", "interpretation": state, "arms": state_rows})
            paths.append(str(path))
        paths.extend(str(out/name) for name in ("A21_METRICS.csv", "GATE_DECISION.json", "A21_ORACLE_REPORT.md"))
    figures = {}
    if make_figures:
        with _group(book, "figures"):
            try:
                figures, figure_source = _figures(annotated, out/"figures", config)
                for name, points in figure_source.items():
                    _csv(rawdata/(name+".csv"), points, ("parent_id", "iteration", "arm", "metric", "value", "status", "assessable"))
                paths.extend(path for group in figures.values() for path in group)
                gate["figure_status"] = "GENERATED_FROM_SAVED_MEASUREMENTS"
            except ImportError as error:
                gate["figure_status"] = "NOT_RUN_MATPLOTLIB_UNAVAILABLE"
                gate["figure_error"] = str(error)
    else:
        gate["figure_status"] = "NOT_RUN_FIGURES_DISABLED"
    with _group(book, "manifest"):
        gate["figures"] = figures
        _json(out/"GATE_DECISION.json", gate)
        (out/"A21_ORACLE_REPORT.md").write_text(_markdown(annotated, gate, summary, runtime, issues, figures), encoding="utf-8")
        _json(out/"REPORT_MANIFEST.json", {"schema": "a21.report_manifest.v1", "status": "STATIC_LOCAL_REPORT_WRITTEN",
              "paths": paths, "source_rows": str(source/"rows.jsonl"), "source_summary": str(summary_path),
              "figures": figures, "figure_status": gate["figure_status"], "no_physics_rerun": True,
              "truth_access": False, "scientific_judgment": "CODEX_REVIEW_REQUIRED"})
    return {"paths": paths+[str(out/"REPORT_MANIFEST.json")], "gate_decision": gate, "figures": figures,
            "figure_status": gate["figure_status"]}


generate_report = write_report


def run_report(root, config, book, job):
    """CLI adapter; the enclosing driver bills imports/report CPU inclusively."""
    result = write_report(root, config, book=book)
    return {"status": "COMPLETE", "job": job, **result}
