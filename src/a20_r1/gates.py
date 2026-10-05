"""R1 registered evidence gates; pure tables only, no physics or label access.

Rows carry already measured metrics.  Missing evidence is never replaced by a
denominator floor, a successful fallback, a rank proxy, or a partial-cohort mean.
Anatomy HISTORY and every oracle are excluded from legal candidate selection.
"""
from __future__ import annotations

import json
import math
from statistics import median


METHODS = ("FIXED-DEEP", "WIDE-M", "CHEAP-TASK", "ORACLE-M",
           "PROTECTED-ORACLE", "PROTECTED-RANDOM", "HISTORY")
LEGAL_METHODS = ("WIDE-M", "CHEAP-TASK")
DEFAULT_PARENTS = (2001, 2005, 2003, 2007, 2013)
PHASE2_PARENTS = (2001, 2007, 2013)
DEFAULTS = dict(oracle_gate_median=.30, oracle_gate_parent_ratio=.5,
                oracle_gate_min_parents=4, legal_gate_median=.50,
                legal_gate_baseline_ratio=.30, early_gate_absolute=.05,
                early_gate_excess=.02, oracle_capture_threshold=1-1e-8,
                current_rank_cap=56, negative_kill_rank_tolerance=2,
                match_action_tolerance=.1, closed_loop_quality_ratio=1.15,
                closed_loop_improvement_ratio=.8, closed_loop_vector_ratio=.5,
                closed_loop_wall_ratio=.8)


def get(row, *names):
    for name in names:
        value = row
        for part in name.split("."):
            if not isinstance(value, dict) or part not in value:
                value = None
                break
            value = value[part]
        if value is not None:
            return value
    return None


def number(value):
    if isinstance(value, bool):
        return None
    try:
        value = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return value if math.isfinite(value) else None


def settings(config):
    out = dict(DEFAULTS)
    out.update(config or {})
    return out


def parent_id(row):
    value = number(get(row, "parent_object_id", "parent_id"))
    return int(value) if value is not None and value.is_integer() else None


def method_id(row):
    name = get(row, "method", "chosen_method")
    if name in ("ADAPTIVE_OPM", "ADAPTIVE"):
        declared = get(row, "chosen_method", "selected_method", "policy_method")
        return declared if declared in LEGAL_METHODS else name
    return {"FIXED_OPM": "FIXED-DEEP", "FULL-GN": "FULL_GN",
            "FULLGN": "FULL_GN"}.get(name, name)


def method_rows(rows):
    return [r for r in rows if isinstance(r, dict) and
            r.get("record_kind") in (None, "method", "run_summary", "trajectory")]


def state_id(row, config):
    state = get(row, "state", "state_kind")
    if state in ("early", "late"):
        return state
    value = number(get(row, "iteration", "accepted_iteration"))
    iterations = config.get("replay_iterations", (0, 17))
    if value == iterations[0]:
        return "early"
    if value == iterations[-1]:
        return "late"
    return None


def action_fourtuple(row):
    """Only the actual exclusive F/F*/L/L* RHS tuple, never an aggregate proxy."""
    value = get(row, "action_fourtuple")
    if isinstance(value, dict):
        value = [value.get(k) for k in ("F", "F*", "L", "L*")]
    if value is None:
        counts = get(row, "proposal_action_counts")
        if isinstance(counts, dict):
            value = [counts.get(k) for k in ("F", "F*", "L", "L*")]
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return None
    values = [number(v) for v in value]
    if any(v is None or v < 0 or not v.is_integer() for v in values):
        return None
    return tuple(int(v) for v in values)


def anatomy_issues(row, config):
    issues = []
    if row is None:
        return ["MISSING_METHOD_ROW"]
    if get(row, "status") not in ("OK", "OK_TRUTH_UNAVAILABLE"):
        issues.append("METHOD_FAILED_OR_NOT_RUN")
    if get(row, "reference_valid") is not True:
        issues.append("REFERENCE_MISSING_OR_INVALID")
    if get(row, "reference_QP_valid", "reference_qp_valid") is False:
        issues.append("REFERENCE_QP_FAILED")
    if get(row, "QP_valid", "qp_valid") is not True:
        issues.append("METHOD_QP_FAILED_OR_UNVERIFIED")
    if get(row, "fullfallback_used", "full_fallback_used") is True:
        issues.append("FULL_FALLBACK_NOT_VALID_METHOD_EVIDENCE")
    energy = number(get(row, "reference_H_norm_squared", "reference_h_energy"))
    if energy is None:
        issues.append("REFERENCE_DENOMINATOR_MISSING")
    elif energy <= 0:
        issues.append("ZERO_OR_INVALID_REFERENCE_DENOMINATOR")
    elif energy <= 1e-24:
        issues.append("REFERENCE_DENOMINATOR_BELOW_REGISTERED_NORM_FLOOR")
    if get(row, "H_denominator_floor_used", "denominator_floor_used") is not False:
        issues.append("DENOMINATOR_FLOOR_OR_UNVERIFIED")
    error = number(get(row, "relative_H_step_error", "H_error"))
    if error is None or error < 0:
        issues.append("H_METRIC_MISSING_OR_INVALID")
    rank = number(get(row, "actual_rank", "rank"))
    if rank is None or rank < 0 or not rank.is_integer():
        issues.append("ACTUAL_RANK_MISSING_OR_INVALID")
    elif rank > config["current_rank_cap"]:
        issues.append("ACTUAL_RANK_EXCEEDS_CAP")
    if get(row, "baseline_reproduction_valid") is False:
        issues.append("BASELINE_REPRODUCTION_FAILED")
    return issues


def _cohort(rows, method, state, parents, config):
    selected = {p: [] for p in parents}
    for row in rows:
        p = parent_id(row)
        if p in selected and method_id(row) == method and state_id(row, config) == state:
            selected[p].append(row)
    issues = []
    valid = []
    counts = {"missing": 0, "duplicate": 0, "method_failed": 0,
              "missing_or_invalid_reference": 0, "method_QP_failed_or_unverified": 0,
              "reference_QP_failed": 0, "denominator_invalid_or_unverified": 0,
              "rank_invalid_or_missing": 0, "invalid_metric": 0}
    for p, values in selected.items():
        if len(values) != 1:
            kind = "MISSING_METHOD_ROW" if not values else "DUPLICATE_METHOD_ROW"
            counts["missing" if not values else "duplicate"] += 1
            issues.append({"parent_id": p, "issues": [kind], "row_count": len(values)})
            continue
        row = values[0]
        bad = anatomy_issues(row, config)
        for label, prefixes in {
            "method_failed": ("METHOD_FAILED", "FULL_FALLBACK"),
            "missing_or_invalid_reference": ("REFERENCE_MISSING",),
            "method_QP_failed_or_unverified": ("METHOD_QP",),
            "reference_QP_failed": ("REFERENCE_QP",),
            "denominator_invalid_or_unverified": ("REFERENCE_DENOMINATOR", "ZERO_OR", "DENOMINATOR"),
            "rank_invalid_or_missing": ("ACTUAL_RANK",),
            "invalid_metric": ("H_METRIC",),
        }.items():
            if any(x.startswith(prefixes) for x in bad):
                counts[label] += 1
        if bad:
            issues.append({"parent_id": p, "issues": bad, "row_count": 1})
        else:
            valid.append(row)
    complete = len(valid) == len(parents) and not issues
    return {"method": method, "state": state, "status": "VALID" if complete else "HOLD",
            "complete_valid": complete, "expected_parent_count": len(parents),
            "valid_parent_count": len(valid), "counts": counts, "issues": issues,
            "median_H_error": median(number(get(r, "relative_H_step_error", "H_error"))
                                      for r in valid) if complete else None,
            "rows": valid}


def _public(cohort):
    return {k: v for k, v in cohort.items() if k != "rows"}


def _capture(row, config):
    values = [number(get(row, "oracle_material_span_capture", "material_span_capture")),
              number(get(row, "oracle_qM_source_capture")),
              number(get(row, "oracle_finalZ_source_capture", "oracle_Z_source_capture"))]
    explicit = get(row, "oracle_capture_certified")
    # A false bit also preserves target-norm/floor invalidity supplied by anatomy.
    return explicit is True and get(row, "oracle_target_norm_floor_used") is not True and get(row, "oracle_target_norm_valid") is not False and all(v is not None and v >= config["oracle_capture_threshold"]
                                   for v in values)


def _allocation(row):
    value = get(row, "allocation", "seed_metadata.allocation", "seed_info.allocation",
                "seed_rank_metadata.allocation")
    if not isinstance(value, (dict, list, tuple)) or not value:
        return None
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _oracle_quality(cohort, baseline, config):
    if not cohort["complete_valid"] or not baseline["complete_valid"]:
        return {"status": "HOLD", "median_H_error": None, "reduced_parent_count": None}
    fixed = {parent_id(r): number(get(r, "relative_H_step_error", "H_error"))
             for r in baseline["rows"]}
    count = sum(number(get(r, "relative_H_step_error", "H_error")) <=
                config["oracle_gate_parent_ratio"] * fixed[parent_id(r)]
                for r in cohort["rows"])
    passed = cohort["median_H_error"] <= config["oracle_gate_median"] and count >= config["oracle_gate_min_parents"]
    return {"status": "PASS" if passed else "FAIL", "median_H_error": cohort["median_H_error"],
            "reduced_parent_count": count, "required_parent_count": config["oracle_gate_min_parents"]}


def evaluate_anatomy(rows, config):
    """Return A/B/C, an online legal winner, and an operational mechanism status."""
    config = settings(config)
    parents = tuple(config.get("parents", DEFAULT_PARENTS))
    if len(parents) != 5 or len(set(parents)) != 5:
        return {"status": "HOLD", "A": {"status": "HOLD"}, "B": {"status": "HOLD"},
                "C": {"status": "HOLD"}, "selected_method": None,
                "mechanism_status": "D_INCONCLUSIVE", "issues": ["REGISTERED_FIVE_PARENT_COHORT_INVALID"],
                "HISTORY": {"status": "NOT_RUN_NO_OWN_ACCEPTED_TRAJECTORY"}}
    rows = method_rows(rows)
    cohorts = {(m, s): _cohort(rows, m, s, parents, config)
               for m in METHODS if m != "HISTORY" for s in ("early", "late")}
    fixed = cohorts["FIXED-DEEP", "late"]
    raw = cohorts["ORACLE-M", "late"]
    raw_values = [r for r in rows if method_id(r) == "ORACLE-M" and
                  parent_id(r) in parents and state_id(r, config) == "late"]
    trigger = any((v := number(get(r, "oracle_qM_source_capture"))) is not None and
                  v < config["oracle_capture_threshold"] for r in raw_values)
    raw_capture_missing = any(number(get(r, "oracle_qM_source_capture")) is None for r in raw_values)
    operative_name = "PROTECTED-ORACLE" if trigger else "ORACLE-M"
    operative = cohorts[operative_name, "late"]
    required_protected = [(m, s) for m in ("PROTECTED-ORACLE", "PROTECTED-RANDOM")
                          for s in ("early", "late")] if trigger else []
    protected_complete = all(cohorts[key]["complete_valid"] for key in required_protected)
    capture_complete = operative["complete_valid"] and all(_capture(r, config) for r in operative["rows"])
    quality = _oracle_quality(operative, fixed, config)
    raw_quality = _oracle_quality(raw, fixed, config)
    attribution = {"status": "NOT_RUN_NOT_REQUIRED", "same_allocation": None,
                   "reduced_parent_count": None}
    if trigger:
        control = cohorts["PROTECTED-RANDOM", "late"]
        if protected_complete:
            cr = {parent_id(r): r for r in control["rows"]}
            same = all(_allocation(r) is not None and _allocation(r) == _allocation(cr[parent_id(r)])
                       for r in operative["rows"])
            count = sum(number(get(cr[parent_id(r)], "relative_H_step_error", "H_error")) > 0 and number(get(r, "relative_H_step_error", "H_error")) <=
                        config["oracle_gate_parent_ratio"] * number(get(cr[parent_id(r)], "relative_H_step_error", "H_error"))
                        for r in operative["rows"])
            attribution = {"status": "PASS" if same and count >= config["oracle_gate_min_parents"] else "HOLD",
                           "same_allocation": same, "reduced_parent_count": count,
                           "required_parent_count": config["oracle_gate_min_parents"]}
        else:
            attribution["status"] = "HOLD"
    rank_match = False
    if operative["complete_valid"] and fixed["complete_valid"]:
        fr = {parent_id(r): number(get(r, "actual_rank", "rank")) for r in fixed["rows"]}
        rank_match = all(abs(number(get(r, "actual_rank", "rank"))-fr[parent_id(r)]) <=
                         config["negative_kill_rank_tolerance"] for r in operative["rows"])
    certified = fixed["complete_valid"] and operative["complete_valid"] and capture_complete and protected_complete
    if not trigger and raw_capture_missing:
        certified = False
    if not certified:
        a_status = "HOLD"
        mechanism = "D_INCONCLUSIVE"
    elif quality["status"] == "FAIL":
        a_status = "FAIL" if rank_match else "HOLD"
        mechanism = "C_CERTIFIED_ORACLE_NEGATIVE_KILL" if rank_match else "D_INCONCLUSIVE"
    elif trigger and attribution["status"] != "PASS":
        a_status, mechanism = "HOLD", "D_INCONCLUSIVE"
    else:
        a_status, mechanism = "PASS", "A_ORACLE_REPAIR_GATE_PASS"
    legal_b, legal_c = {}, {}
    early_fixed = cohorts["FIXED-DEEP", "early"]
    candidates = []
    candidate_order = []
    for name in LEGAL_METHODS:
        late, early = cohorts[name, "late"], cohorts[name, "early"]
        b = "HOLD" if not late["complete_valid"] or not fixed["complete_valid"] else (
            "PASS" if late["median_H_error"] <= config["legal_gate_median"] and
            late["median_H_error"] <= config["legal_gate_baseline_ratio"] * fixed["median_H_error"] else "FAIL")
        c = "HOLD" if not early["complete_valid"] or not early_fixed["complete_valid"] else (
            "PASS" if early["median_H_error"] <= config["early_gate_absolute"] or
            early["median_H_error"] <= early_fixed["median_H_error"] + config["early_gate_excess"] else "FAIL")
        legal_b[name] = {"status": b, "median_H_error": late["median_H_error"], "cohort": _public(late)}
        legal_c[name] = {"status": c, "median_H_error": early["median_H_error"], "cohort": _public(early)}
        if b == c == "PASS":
            tuples = [action_fourtuple(r) for r in late["rows"] + early["rows"]]
            complete_actions = all(v is not None for v in tuples)
            total = sum(sum(v) for v in tuples) if complete_actions else None
            key = (late["median_H_error"], not complete_actions, total if total is not None else math.inf, name)
            candidates.append((key, name))
            candidate_order.append({"method": name, "late_median_H_error": late["median_H_error"],
                                    "proposal_actions_complete": complete_actions,
                                    "proposal_vector_RHS_sum": total})
    candidates.sort()
    survivor = candidates[0][1] if candidates else None
    selected = survivor if a_status == "PASS" else None
    if a_status == "PASS" and selected:
        mechanism = "A_AND_LEGAL_B_C_PASS"
    b_status = "PASS" if any(v["status"] == "PASS" for v in legal_b.values()) else (
        "HOLD" if any(v["status"] == "HOLD" for v in legal_b.values()) else "FAIL")
    c_status = "PASS" if any(v["status"] == "PASS" for v in legal_c.values()) else (
        "HOLD" if any(v["status"] == "HOLD" for v in legal_c.values()) else "FAIL")
    return {"status": "PASS" if selected else ("KILL" if mechanism.startswith("C_") else "HOLD"),
            "A": {"status": a_status, "operative_method": operative_name,
                  "raw_compression_trigger": trigger, "raw_quality": raw_quality,
                  "operative_quality": quality, "capture_certified_all_late": capture_complete,
                  "protected_all_ten_state_pairs_complete_valid": protected_complete if trigger else None,
                  "protected_attribution": attribution, "negative_rank_matched": rank_match,
                  "operative_cohort": _public(operative), "baseline_cohort": _public(fixed)},
            "B": {"status": b_status, "methods": legal_b},
            "C": {"status": c_status, "methods": legal_c},
            "selected_method": selected, "legal_B_C_survivor": survivor,
            "candidate_order": sorted(candidate_order, key=lambda x: (x["late_median_H_error"],
                                    not x["proposal_actions_complete"], x["proposal_vector_RHS_sum"] if x["proposal_vector_RHS_sum"] is not None else math.inf, x["method"])),
            "mechanism_status": mechanism,
            "HISTORY": {"status": "NOT_RUN_NO_OWN_ACCEPTED_TRAJECTORY", "legal_candidate": False},
            "cohorts": [_public(cohorts[key]) for key in cohorts],
            "phase2": {"status": "ELIGIBLE" if selected else "NOT_RUN_GATE_CLOSED"},
            "scientific_judgment": "PARENT_ONLY", "exposure": "historically_exposed_feasibility"}


def _run_issues(row):
    if row is None:
        return ["MISSING_RUN_ROW"]
    issues = []
    if get(row, "status") not in ("OK", "PASS", "CONVERGED", "MAX_ITERATIONS"):
        issues.append("RUN_FAILED_OR_NOT_RUN")
    if get(row, "QP_valid", "qp_valid") is not True:
        issues.append("METHOD_QP_FAILED_OR_UNVERIFIED")
    if get(row, "fullfallback_used", "full_fallback_used") is True:
        issues.append("FULL_FALLBACK_NOT_VALID_METHOD_EVIDENCE")
    for name, aliases in {"material": ("material_error", "truth_metrics.material_relative_error", "material_relative_error"),
                          "objective": ("full_objective", "objective", "final_full_objective"),
                          "KKT": ("full_KKT", "full_kkt", "KKT", "kkt", "final_full_KKT")}.items():
        value = number(get(row, *aliases))
        if value is None or value < 0:
            issues.append(name+"_MISSING_OR_INVALID")
    return issues


def _run_metric(row, kind):
    return number(get(row, *{"material": ("material_error", "truth_metrics.material_relative_error", "material_relative_error"),
                             "objective": ("full_objective", "objective", "final_full_objective"),
                             "KKT": ("full_KKT", "full_kkt", "KKT", "kkt", "final_full_KKT")}[kind]))


def _quality(row, full, config):
    if _run_issues(row) or _run_issues(full):
        return None
    return (_run_metric(row, "material") <= config["closed_loop_quality_ratio"] * max(1e-6, _run_metric(full, "material")) and
            _run_metric(row, "objective") <= config["closed_loop_quality_ratio"] * _run_metric(full, "objective") and
            _run_metric(row, "KKT") <= max(1e-6, config["closed_loop_quality_ratio"] * _run_metric(full, "KKT")))


def _run_map(rows, methods, parents):
    mapping, issues = {}, []
    for p in parents:
        for name in methods:
            values = [r for r in rows if parent_id(r) == p and method_id(r) == name]
            if len(values) != 1:
                issues.append({"parent_id": p, "method": name,
                               "issues": ["MISSING_RUN_ROW" if not values else "DUPLICATE_RUN_ROW"]})
                continue
            mapping[p, name] = values[0]
            bad = _run_issues(values[0])
            if bad:issues.append({"parent_id": p, "method": name, "issues": bad})
    return mapping, issues


def _ratio(numerator, denominator):
    return numerator/denominator if numerator is not None and denominator is not None and numerator >= 0 and denominator > 0 else None


def _physical_work(row):
    value = number(get(row, "physical_vector_RHS", "online_physical_vector_RHS", "deployment_vector_RHS"))
    if value is not None and value >= 0 and value.is_integer():
        return value
    # Anatomy F/F*/L/L* alone cannot substitute for a closed-loop full-physics ledger.
    return None


def _deployment_wall(row):
    return number(get(row, "deployment_wall_seconds", "deploy_wall", "wall_deployment",
                      "costs.deployment.wall_seconds"))


def _lu(row):
    return number(get(row, "LU_factorizations", "lu_factorizations", "deployment_LU_factorizations",
                      "costs.deployment.LU_factorizations"))


def evaluate_closed_loop(rows, config, selected_method=None):
    config = settings(config)
    parents = tuple(config.get("phase2_parents", PHASE2_PARENTS))
    if selected_method not in LEGAL_METHODS:
        return {"status": "NOT_RUN_GATE_CLOSED", "selected_method": None, "issues": ["NO_LEGAL_ANATOMY_WINNER"]}
    if len(parents) != 3 or set(parents) != set(PHASE2_PARENTS):
        return {"status": "HOLD", "issues": ["REGISTERED_PHASE2_COHORT_INVALID"]}
    rows = method_rows(rows)
    mapping, issues = _run_map(rows, ("FULL_GN", "FIXED-DEEP", selected_method), parents)
    per_parent = []
    for p in parents:
        full, fixed, adaptive = (mapping.get((p, m)) for m in ("FULL_GN", "FIXED-DEEP", selected_method))
        if any(_run_issues(r) for r in (full, fixed, adaptive)):
            continue
        quality = _quality(adaptive, full, config)
        material = _run_metric(adaptive, "material") / max(1e-6, _run_metric(fixed, "material"))
        wr = _ratio(_physical_work(adaptive), _physical_work(fixed))
        wall = _ratio(_deployment_wall(adaptive), _deployment_wall(fixed))
        al, fl = _lu(adaptive), _lu(fixed)
        full_lu = _lu(full)
        per_parent.append({"parent_id": p, "quality_pass": quality,
                           "FIXED_full_quality_pass": _quality(fixed, full, config),
                           "adaptive_FIXED_material_ratio": material, "physical_vector_RHS_ratio": wr,
                           "deployment_wall_ratio": wall, "LU_no_increase": None if al is None or fl is None or al < 0 or fl < 0 else al <= fl,
                           "adaptive_FULL_material_ratio": _run_metric(adaptive, "material")/max(1e-6, _run_metric(full, "material")),
                           "adaptive_FULL_objective_ratio": _ratio(_run_metric(adaptive, "objective"), _run_metric(full, "objective")),
                           "adaptive_FULL_KKT_ratio_unfloored": _ratio(_run_metric(adaptive, "KKT"), _run_metric(full, "KKT")),
                           "adaptive_FULL_physical_vector_RHS_ratio": _ratio(_physical_work(adaptive), _physical_work(full)),
                           "adaptive_FULL_deployment_wall_ratio": _ratio(_deployment_wall(adaptive), _deployment_wall(full)),
                           "adaptive_FULL_LU_no_increase": None if al is None or full_lu is None or al < 0 or full_lu < 0 else al <= full_lu})
    complete = len(per_parent) == 3 and not issues
    material_median = median(r["adaptive_FIXED_material_ratio"] for r in per_parent) if complete else None
    vector_complete = complete and all(r["physical_vector_RHS_ratio"] is not None and r["LU_no_increase"] is not None for r in per_parent)
    wall_complete = complete and all(r["deployment_wall_ratio"] is not None for r in per_parent)
    vector_median = median(r["physical_vector_RHS_ratio"] for r in per_parent) if vector_complete else None
    wall_median = median(r["deployment_wall_ratio"] for r in per_parent) if wall_complete else None
    vector_pass = vector_complete and vector_median <= config["closed_loop_vector_ratio"] and all(r["LU_no_increase"] for r in per_parent)
    wall_pass = wall_complete and wall_median <= config["closed_loop_wall_ratio"]
    quality_pass = complete and all(r["quality_pass"] for r in per_parent)
    fixed_quality = complete and all(r["FIXED_full_quality_pass"] for r in per_parent)
    improvement_pass = complete and material_median <= config["closed_loop_improvement_ratio"]
    if not complete:
        status = "HOLD"
    elif not quality_pass or not improvement_pass:
        status = "FAIL"
    elif vector_pass or wall_pass:
        status = "PASS"
    else:
        status = "FAIL" if vector_complete and wall_complete else "HOLD"
    return {"status": status, "selected_method": selected_method, "parents": list(parents),
            "quality_pass_all": quality_pass, "material_improvement_pass": improvement_pass,
            "FIXED_quality_pass_all": fixed_quality,
            "joint_quality_history_eligible": quality_pass and fixed_quality,
            "history_quality_eligible": quality_pass or fixed_quality,
            "median_adaptive_FIXED_material_ratio": material_median,
            "deployment_status": "PASS" if vector_pass or wall_pass else ("FAIL" if vector_complete and wall_complete else "HOLD"),
            "vector_branch_complete": vector_complete, "vector_branch_pass": vector_pass,
            "median_physical_vector_RHS_ratio": vector_median,
            "wall_branch_complete": wall_complete, "wall_branch_pass": wall_pass,
            "median_deployment_wall_ratio": wall_median, "per_parent": per_parent, "issues": issues,
            "median_adaptive_FULL_physical_vector_RHS_ratio": median(r["adaptive_FULL_physical_vector_RHS_ratio"] for r in per_parent) if complete and all(r["adaptive_FULL_physical_vector_RHS_ratio"] is not None for r in per_parent) else None,
            "median_adaptive_FULL_deployment_wall_ratio": median(r["adaptive_FULL_deployment_wall_ratio"] for r in per_parent) if complete and all(r["adaptive_FULL_deployment_wall_ratio"] is not None for r in per_parent) else None,
            "deployment_gate_denominator_method": "FIXED-DEEP",
            "additional_cost_denominator_method": "FULL_GN",
            "material_floor": 1e-6, "offline_reference_cost_not_in_deployment": True,
            "scientific_judgment": "PARENT_ONLY", "inference": "DESCRIPTIVE_THREE_HISTORICAL_PARENTS"}


def evaluate_history(rows, config):
    """Conditional same-FIXED ON/OFF ablation, never snapshot HISTORY evidence."""
    config = settings(config)
    rows = method_rows(rows)
    parents = tuple(config.get("phase2_parents", PHASE2_PARENTS))
    if len(parents) != 3 or set(parents) != set(PHASE2_PARENTS):
        return {"status": "HOLD", "B": "HOLD", "issues": ["REGISTERED_PHASE2_COHORT_INVALID"]}
    history = [r for r in rows if method_id(r) == "FIXED-DEEP" and get(r, "history_mode") in ("ON", "OFF")]
    if not history:
        return {"status": "NOT_RUN", "B": "NOT_RUN", "issues": ["NO_CONTROLLED_OWN_HISTORY_ABLATION"]}
    fulls = [r for r in rows if method_id(r) == "FULL_GN"]
    mapping, issues = {}, []
    for p in parents:
        for mode in ("ON", "OFF", "FULL"):
            values = [r for r in (fulls if mode == "FULL" else history) if parent_id(r) == p and
                      (mode == "FULL" or get(r, "history_mode") == mode)]
            if len(values) != 1:
                issues.append({"parent_id": p, "mode": mode, "issues": ["MISSING_RUN_ROW" if not values else "DUPLICATE_RUN_ROW"]})
            else:
                mapping[p, mode] = values[0]
                bad = _run_issues(values[0])
                if bad:issues.append({"parent_id": p, "mode": mode, "issues": bad})
    ratios = []
    quality = []
    if not issues and len(mapping) == 9:
        for p in parents:
            on, off, full = (mapping[p, m] for m in ("ON", "OFF", "FULL"))
            if get(on, "own_history_validated", "history_ownership_valid") is not True:
                issues.append({"parent_id": p, "issues": ["OWN_ACCEPTED_HISTORY_PROVENANCE_UNVERIFIED"]})
            a, b = _allocation(on), _allocation(off)
            if a is None or b is None or a != b:
                issues.append({"parent_id": p, "issues": ["SAME_FIXED_ALLOCATION_UNVERIFIED"]})
            quality.extend([_quality(on, full, config), _quality(off, full, config)])
            ratios.append(_run_metric(on, "material")/max(1e-6, _run_metric(off, "material")))
    complete = not issues and len(ratios) == 3
    value = median(ratios) if complete else None
    passed = complete and all(quality) and value <= config["closed_loop_improvement_ratio"]
    return {"status": "PASS" if passed else ("HOLD" if not complete else "FAIL"),
            "B": "PASS" if passed else ("HOLD" if not complete else "FAIL"),
            "median_history_ON_OFF_material_ratio": value, "quality_pass_all": complete and all(quality),
            "parents": list(parents), "issues": issues, "material_floor": 1e-6,
            "scientific_judgment": "PARENT_ONLY", "snapshot_HISTORY_used": False}
