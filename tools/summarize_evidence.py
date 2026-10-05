#!/usr/bin/env python3
"""Offline A20 evidence tables/plots; never runs physics or recomputes gates.

Default: frozen.json scope, 2,000 paired parent-cluster bootstrap draws.  Only
logged replay metrics are read; no runtime NPZ, truth labels, or oracle seed
generation is accessed.  A descriptive finite subset is never labeled a gate.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sys
import time

STARTED_WALL = time.perf_counter()
SUCCESS = {"OK", "PASS", "COMPLETE", "SUCCESS", "CAPPED", "CONVERGED_FULL_KKT"}
MISSING = {"", "MISSING", "NOT_RUN", "SKIPPED", "UNAVAILABLE"}
MIXED_ALIASES = {"mixed", "opm", "opm_mixed", "mixed_default", "opm_mixed_default"}
COUNTERS = ("F_actions", "F_adjoint_actions", "L_actions", "L_adjoint_actions",
            "Maxwell_matvec_rhs", "full_forward_RHS", "full_tangent_RHS",
            "full_adjoint_RHS", "reduced_core_rhs", "projected_factorizations",
             "retained_factorizations", "forcing_rhs", "B_rhs", "B_adjoint_rhs")
WALL_PHASES = ("basis", "projection", "QP", "fallback", "audit")
FRONTIER_AXES = ("actual_rank", "online_Maxwell_vector_actions", "feedback_vector_actions")
FRONTIER_LABELS = {"actual_rank": "Actual current rank",
                   "online_Maxwell_vector_actions": "Logged online F/F*/L/L* vector actions",
                   "feedback_vector_actions": "Logged F + F* vector actions"}
ROW_FIELDS = ("row_id", "source", "line", "record_kind", "parent", "state", "parameterization",
              "method", "method_raw", "variant", "degree", "actual_rank",
              "total_seed_rank", "seed_rank_source", "n_current", "rank_fraction",
              "relative_H_step_error", "full_quadratic_gap", "reference_H_energy",
              "wall_seconds", "wall_seconds_scope", "wall_total_attributed", *("wall_"+p for p in WALL_PHASES),
              "basis_time_scope", "shared_state_and_reference_costs_included",
              "online_Maxwell_vector_actions", "basis_Maxwell_vector_actions",
              "feedback_vector_actions", "feedback_vector_actions_scope",
              "full_solver_RHS", "fallback_count", "fullfallback_used", "status", "metric_valid",
              "failed", "invalid", "zero_reference", "missing", "duplicate",
              "oracle", "flags", *COUNTERS)


def finite(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        value = float(value)
    except (ValueError, TypeError, OverflowError):
        return None
    return value if math.isfinite(value) else None


def integer(value):
    number = finite(value)
    return int(number) if number is not None and number == int(number) else None


def ident(value):
    if value is None or isinstance(value, (list, dict)):
        return None
    number = integer(value)
    return str(number) if number is not None else str(value)


def get_path(row, path):
    value = row
    for key in path.split("."):
        if not isinstance(value, dict) or key not in value:
            return None
        value = value[key]
    return value


def first(row, paths):
    for path in paths:
        value = get_path(row, path)
        if value is not None:
            return value
    return None


def read_json(path, issues, *, required=False):
    if not path.exists():
        if required:
            issues.append({"source": str(path), "line": None, "kind": "missing_file", "error": "NOT_RUN"})
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        issues.append({"source": str(path), "line": None, "kind": "invalid_json", "error": str(exc)})
        return None


def read_jsonl(path, issues):
    if not path.exists():
        return []
    rows = []
    try:
        with path.open(encoding="utf-8") as handle:
            for line, text in enumerate(handle, 1):
                if not text.strip():
                    continue
                try:
                    row = json.loads(text)
                    if not isinstance(row, dict):
                        raise ValueError("JSONL row must be an object")
                    rows.append((row, str(path), line))
                except ValueError as exc:
                    issues.append({"source": str(path), "line": line, "kind": "invalid_jsonl", "error": str(exc)})
    except OSError as exc:
        issues.append({"source": str(path), "line": None, "kind": "read_error", "error": str(exc)})
    return rows


def is_method_record(raw):
    """Explicit shared records are accounting context, never experiment cells."""
    return "record_kind" not in raw or raw["record_kind"] == "method"


def select_method_records(records, *, actions=False):
    selected, excluded = [], []
    for raw, source, line in records:
        legacy_action_result = (raw.get("event") is None
                                and first(raw, ("method", "representation", "algorithm")) is not None)
        if is_method_record(raw) and (not actions or "record_kind" in raw or legacy_action_result):
            selected.append((raw, source, line))
        else:
            excluded.append({"source": source, "line": line,
                             "record_kind": raw.get("record_kind", "legacy_action_event"),
                             "parent": ident(first(raw, ("parent_object_id", "parent_id", "parent"))),
                             "state": ident(first(raw, ("iteration", "state_iteration", "replay_iteration"))),
                             "method": raw.get("method"), "status": raw.get("status"),
                             "wall_total_attributed": finite(raw.get("wall_total_attributed")),
                             "counts": raw.get("counts"), "costs": raw.get("costs"),
                             "scope": "retained accounting context; excluded from method samples/failed/missing cells"})
    return selected, excluded


def non_audit_action_counts(raw):
    """Actual disjoint cost ledgers only; basis metadata is not a ledger."""
    costs = raw.get("costs")
    if not isinstance(costs, dict) or not costs:
        return None
    counts = Counter()
    for phase, cost in costs.items():
        if phase == "audit":
            continue
        if not isinstance(cost, dict) or not isinstance(cost.get("counts"), dict):
            return None
        for name in COUNTERS[:4]:
            value = finite(cost["counts"].get(name, 0))
            if value is None or value < 0:
                return None
            counts[name] += value
    return counts


def normalize(raw, source, line, reference_floor=1e-12):
    """Normalize a method sample; return None for an explicit shared record.

    Requested/target rank and basis metadata are never action counts.
    """
    if not is_method_record(raw):
        return None
    method_raw = str(first(raw, ("method", "representation", "algorithm")) or "MISSING")
    method = "mixed" if method_raw.lower() in MIXED_ALIASES else method_raw
    state = first(raw, ("replay_iteration", "state_iteration", "iteration", "outer_iteration", "state_id", "state"))
    variant = first(raw, ("variant", "control_seed", "random_seed", "random_control_seed", "replicate"))
    row = {
        "row_id": f"{source}:{line}", "source": source, "line": line,
        "record_kind": raw.get("record_kind", "legacy_method"),
        "parent": ident(first(raw, ("parent_object_id", "parent_id", "parent"))),
        "state": ident(state), "parameterization": str(first(raw, ("parameterization", "material_kind", "kind")) or "unspecified"),
        "method": method, "method_raw": method_raw,
        "variant": "default" if variant is None else str(variant),
        "degree": integer(first(raw, ("degree", "m"))),
        "actual_rank": integer(first(raw, ("actual_rank", "actualrank", "rank", "basis_info.rank", "basis.rank"))),
        "n_current": integer(first(raw, ("n_current", "current_dimension"))),
        "relative_H_step_error": finite(first(raw, ("relative_H_step_error", "audit.relative_H_step_error", "metrics.relative_H_step_error"))),
        "full_quadratic_gap": finite(first(raw, ("full_quadratic_gap", "audit.full_quadratic_gap"))),
        "reference_H_energy": finite(first(raw, ("reference_H_energy", "audit.reference_H_energy"))),
        "wall_seconds": finite(first(raw, ("wall_total_attributed", "wall_seconds", "wall_total", "total_wall_seconds"))),
        "wall_seconds_scope": ("replay attributed phases including offline audit; not online deployment wall"
                               if raw.get("wall_total_attributed") is not None else "legacy logged wall; attribution scope unavailable"),
        "wall_total_attributed": finite(raw.get("wall_total_attributed")),
        "basis_time_scope": raw.get("basis_time_scope"),
        "shared_state_and_reference_costs_included": raw.get("shared_state_and_reference_costs_included"),
        "online_Maxwell_vector_actions": finite(raw.get("online_Maxwell_vector_actions")),
        "basis_Maxwell_vector_actions": finite(raw.get("basis_Maxwell_vector_actions")),
        "fallback_count": finite(first(raw, ("fallback_count", "fallbacks_count"))),
        "fullfallback_used": bool(raw.get("fullfallback_used", False)),
        "status": str(raw.get("status") or "").upper(),
        "oracle": bool(raw.get("oracle") or raw.get("is_oracle") or raw.get("deployable") is False
                       or "oracle" in method_raw.lower()),
        "failed": False, "invalid": False, "zero_reference": False,
        "missing": False, "duplicate": False, "metric_valid": False,
    }
    flags = []
    for phase in WALL_PHASES:
        row["wall_"+phase] = finite(first(raw, ("wall_"+phase, "costs."+phase+".wall_seconds")))
    seed_rank = first(raw, ("total_seed_rank", "total_seedrank", "seed_rank_total", "seed_total_rank",
                            "basis_info.total_seed_rank", "seeds.total_seed_rank"))
    row["total_seed_rank"] = integer(seed_rank)
    row["seed_rank_source"] = "explicit_total_seed_rank" if row["total_seed_rank"] is not None else "missing"
    # The sum of compressed stream seed ranks is a declared convention; it is
    # not a union rank and is never substituted by requested seed budgets.
    ranks = first(raw, ("actual_seed_ranks", "basis_info.actual_seed_ranks", "basis.actual_seed_ranks"))
    if isinstance(ranks, dict) and ranks:
        values = [integer(v) for v in ranks.values()]
        if all(v is not None and v >= 0 for v in values):
            if row["total_seed_rank"] is not None and row["total_seed_rank"] != sum(values):
                flags.append("invalid_inconsistent_total_and_actual_seed_ranks")
            row["total_seed_rank"] = sum(values)
            row["seed_rank_source"] = "sum_actual_compressed_stream_seed_ranks"
        else:
            flags.append("invalid_actual_stream_seed_rank")
    if row["total_seed_rank"] is None:
        records = first(raw, ("seed_provenance", "seed_records", "basis_info.seed_provenance"))
        if isinstance(records, dict) and records and all(isinstance(v, dict) and integer(v.get("rank")) is not None for v in records.values()):
            row["total_seed_rank"] = sum(integer(v["rank"]) for v in records.values())
            row["seed_rank_source"] = "sum_logged_compressed_stream_seed_ranks"
    if row["total_seed_rank"] is None:
        flags.append("missing_total_seed_rank")
    for name in COUNTERS:
        row[name] = finite(first(raw, (name, "cost.counts."+name, "counts."+name, "action_counts."+name)))
        if row[name] is not None and row[name] < 0:
            flags.append("invalid_counter:"+name)
            row[name] = None
    online_counts = non_audit_action_counts(raw)
    row["feedback_vector_actions"] = (online_counts["F_actions"]+online_counts["F_adjoint_actions"]
                                      if online_counts is not None else None)
    row["feedback_vector_actions_scope"] = ("non-audit attributed method phases"
                                             if online_counts is not None else "MISSING_NO_AUDIT_SEPARATION")
    if row["online_Maxwell_vector_actions"] is None and online_counts is not None:
        row["online_Maxwell_vector_actions"] = sum(online_counts.values())
    for name in ("online_Maxwell_vector_actions", "basis_Maxwell_vector_actions"):
        if row[name] is not None and row[name] < 0:
            flags.append("invalid_counter:"+name)
            row[name] = None
    full_rhs = [row[k] for k in ("full_forward_RHS", "full_tangent_RHS", "full_adjoint_RHS")]
    row["full_solver_RHS"] = sum(full_rhs) if all(v is not None for v in full_rhs) else None
    rank, n = row["actual_rank"], row["n_current"]
    row["rank_fraction"] = rank/n if rank is not None and n is not None and n > 0 else None
    if rank is not None and (rank < 0 or (n is not None and rank > n)):
        flags.append("invalid_actual_rank")
    if row["total_seed_rank"] is not None and row["total_seed_rank"] < 0:
        flags.append("invalid_total_seed_rank")
    if row["parent"] is None or row["state"] is None or method == "MISSING" or row["degree"] is None:
        row["missing"] = True
        flags.append("missing_row_identity")
    if row["status"] in MISSING:
        row["missing"] = True
        flags.append("missing_status_or_not_run")
    elif row["status"] not in SUCCESS and not row["status"].startswith("OK_"):
        row["failed"] = True
        flags.append("failed_status:"+row["status"])
    if raw.get("valid") is False or raw.get("invalid") is True:
        row["invalid"] = True
        flags.append("explicit_invalid")
    if raw.get("representation_eligible") is False:
        row["invalid"] = True
        flags.append("explicit_ineligible_representation")
    reference_norm = finite(first(raw, ("reference_H_norm", "full_step_H_norm")))
    # Energy has squared units: do not compare energy to an unsquared floor.
    if ((row["reference_H_energy"] is not None and row["reference_H_energy"] <= reference_floor**2)
            or (reference_norm is not None and reference_norm <= reference_floor)
            or raw.get("zero_reference") is True):
        row["zero_reference"] = True
        flags.append("zero_reference")
    raw_error = first(raw, ("relative_H_step_error", "audit.relative_H_step_error", "metrics.relative_H_step_error"))
    if raw_error is None:
        row["missing"] = True
        flags.append("missing_relative_H_step_error")
    elif row["relative_H_step_error"] is None or row["relative_H_step_error"] < 0:
        row["invalid"] = True
        flags.append("invalid_relative_H_step_error")
    row["invalid"] |= any(x.startswith("invalid_") for x in flags)
    row["metric_valid"] = not any(row[k] for k in ("failed", "invalid", "zero_reference", "missing"))
    row["flags"] = ";".join(flags)
    return row


def mark_duplicates(rows):
    groups = defaultdict(list)
    for row in rows:
        key = tuple(row.get(k) for k in ("parent", "state", "parameterization", "method", "variant", "degree", "total_seed_rank", "actual_rank"))
        groups[key].append(row)
    for group in groups.values():
        if len(group) > 1:
            for row in group:
                row["duplicate"] = row["invalid"] = True
                row["metric_valid"] = False
                row["flags"] += ";ambiguous_duplicate_cell"


def csv_write(path, rows, fields=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = sorted({key for row in rows for key in row}) or ["status"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, ensure_ascii=False, allow_nan=False) if isinstance(v, (list, dict)) else v for k, v in row.items()})


def expected_scope(config, rows, parent_map=None):
    parents = [ident(p) for p in config.get("parents", [])]
    states = [ident(p) for p in config.get("replay_iterations", [])]
    kinds = sorted({r["parameterization"] for r in rows} | set(parent_map or {})) or ["unspecified"]
    scopes = {}
    for kind in kinds:
        value = (parent_map or {}).get(kind, parents)
        scopes[kind] = ([ident(p) for p in value], states)
    return scopes


def planned_parent_map(config, manifest):
    """Use declared parameterizations, never observed successes, for coverage."""
    if not isinstance(manifest, dict) or not isinstance(manifest.get("parents"), list):
        return None
    parents = {ident(p) for p in config.get("parents", [])}
    scopes = defaultdict(list)
    for row in manifest["parents"]:
        if isinstance(row, dict) and ident(row.get("parent_id")) in parents:
            scopes[str(row.get("parameterization", "unspecified"))].append(ident(row["parent_id"]))
    return dict(scopes) if {p for values in scopes.values() for p in values} == parents else None


def completeness(rows, scopes, degrees):
    grid = []
    for kind, (parents, states) in scopes.items():
        methods = sorted({r["method"] for r in rows if r["parameterization"] == kind} | {"mixed"})
        for method in methods:
            for degree in degrees:
                for parent in parents:
                    for state in states:
                        matches = [r for r in rows if (r["parameterization"], r["method"], r["degree"], r["parent"], r["state"]) == (kind, method, degree, parent, state)]
                        counts = {k: sum(bool(r[k]) for r in matches) for k in ("metric_valid", "failed", "invalid", "zero_reference", "missing", "duplicate", "oracle")}
                        grid.append({"parameterization": kind, "method": method, "degree": degree,
                                     "parent": parent, "state": state, "observed_rows": len(matches),
                                     "missing_cell": not matches, **counts})
    return grid


def degree_summary(rows, grid):
    import numpy as np
    groups = defaultdict(list)
    for cell in grid:
        groups[(cell["parameterization"], cell["method"], cell["degree"])].append(cell)
    result = []
    for (kind, method, degree), cells in sorted(groups.items()):
        all_rows = [r for r in rows if (r["parameterization"], r["method"], r["degree"]) == (kind, method, degree)]
        ranks = sorted({r["total_seed_rank"] for r in all_rows}, key=lambda x: (-1 if x is None else x)) or [None]
        for seed_rank in ranks:
            subset = [r for r in all_rows if r["total_seed_rank"] == seed_rank]
            states = defaultdict(list)
            expected_keys = {(c["parent"], c["state"]) for c in cells}
            for row in subset:
                if row["metric_valid"] and not row["oracle"] and (row["parent"], row["state"]) in expected_keys:
                    states[(row["parent"], row["state"])].append(row["relative_H_step_error"])
            values = [float(np.mean(v)) for v in states.values()]
            observed_keys = {(r["parent"], r["state"]) for r in subset}
            record = {"parameterization": kind, "method": method, "degree": degree,
                      "total_seed_rank": seed_rank, "expected_parent_state_cells": len(cells),
                      "finite_nonoracle_cells": len(values), "missing_cells": len(expected_keys-observed_keys),
                      "observed_rows": len(subset),
                      "median_finite_subset_only": float(np.median(values)) if values else None,
                      "worst_finite_subset_only": max(values) if values else None,
                      "descriptive_only_not_gate": True}
            record.update({k+"_rows": sum(bool(r[k]) for r in subset) for k in ("failed", "invalid", "zero_reference", "missing", "duplicate", "oracle")})
            result.append(record)
    return result


def paired_parent_bootstrap(rows, scopes, *, samples=2000, seed=20261005):
    """Match both ranks per state, aggregate required states, resample parents.

    A partial parent is never treated as complete. Control replicates at the
    same ranks are averaged inside their state before the parent mean. No
    nearest-rank interpolation, truth selection, or independent state draws.
    """
    import numpy as np
    rng = np.random.default_rng(seed)
    details, estimates = [], []
    groups = sorted({(r["parameterization"], r["degree"], r["total_seed_rank"], r["method"])
                     for r in rows if r["method"] != "mixed" and not r["oracle"] and r["degree"] is not None and r["total_seed_rank"] is not None})
    mixed = [r for r in rows if r["method"] == "mixed" and not r["oracle"]]
    for kind, degree, seed_rank, control in groups:
        parents, states = scopes.get(kind, ([], []))
        parent_deltas = []
        for parent in parents:
            state_deltas = []
            for state in states:
                ms = [r for r in mixed if (r["parameterization"], r["degree"], r["total_seed_rank"], r["parent"], r["state"]) == (kind, degree, seed_rank, parent, state)]
                cs = [r for r in rows if (r["parameterization"], r["degree"], r["total_seed_rank"], r["method"], r["parent"], r["state"]) == (kind, degree, seed_rank, control, parent, state) and not r["oracle"]]
                record = {"parameterization": kind, "degree": degree, "total_seed_rank": seed_rank,
                          "control": control, "parent": parent, "state": state,
                          "mixed_rows": len(ms), "control_rows": len(cs), "matched": False,
                           "reason": "missing_mixed" if not ms else "missing_control" if not cs else "pending"}
                if not ms and any((r["parameterization"], r["degree"], r["parent"], r["state"]) == (kind, degree, parent, state) for r in mixed):
                    record["reason"] = "total_seed_rank_unmatched_or_missing"
                if len(ms) != 1:
                    if ms:
                        record["reason"] = "ambiguous_mixed_rows"
                elif not ms[0]["metric_valid"]:
                    record["reason"] = "mixed_failed_invalid_zero_or_missing"
                elif ms[0]["actual_rank"] is None:
                    record["reason"] = "missing_actual_rank"
                else:
                    exact = [r for r in cs if r["actual_rank"] == ms[0]["actual_rank"]]
                    record["actual_rank"] = ms[0]["actual_rank"]
                    record["matched_control_rows"] = len(exact)
                    if not exact:
                        record["reason"] = "actual_rank_unmatched_or_missing"
                    elif any(not r["metric_valid"] for r in exact):
                        record["reason"] = "matched_control_failed_invalid_zero_or_missing"
                    else:
                        mix_error = ms[0]["relative_H_step_error"]
                        control_error = float(np.mean([r["relative_H_step_error"] for r in exact]))
                        delta = mix_error-control_error
                        record.update(matched=True, reason="exact_seed_and_actual_rank_match",
                                      mixed_error=mix_error, control_error=control_error,
                                      difference_mixed_minus_control=delta,
                                      control_replicates_averaged_within_state=len(exact))
                        state_deltas.append(delta)
                details.append(record)
            if states and len(state_deltas) == len(states):
                parent_deltas.append((parent, float(np.mean(state_deltas))))
        values = np.array([v for _, v in parent_deltas], dtype=float)
        record = {"parameterization": kind, "degree": degree, "total_seed_rank": seed_rank,
                  "control": control, "expected_parents": len(parents), "required_states_per_parent": len(states),
                  "complete_paired_parents": len(values), "paired_parent_ids": [p for p, _ in parent_deltas],
                  "missing_or_unusable_parents": [p for p in parents if p not in {p for p, _ in parent_deltas}],
                   "bootstrap_draws": samples, "rng_seed": seed,
                   "bootstrap_draws_executed": samples if len(values) >= 2 else 0,
                   "degenerate_one_parent": len(values) == 1,
                   "overall_significance_claim": False,
                  "unit": "parent_after_mean_of_required_state_paired_differences",
                  "scope": "historically_exposed_feasibility; descriptive; not blind/generalization evidence",
                  "coverage": "COMPLETE" if len(values) == len(parents) and parents else "PARTIAL"}
        if len(values) >= 2:
            draws = values[rng.integers(0, len(values), size=(samples, len(values)))].mean(axis=1)
            record.update(status="DESCRIPTIVE_PARENT_BOOTSTRAP", mean_difference=float(values.mean()),
                          lower_95=float(np.quantile(draws, .025)), upper_95=float(np.quantile(draws, .975)))
        else:
            record.update(status="DEGENERATE_ONE_PARENT_DESCRIPTIVE_NO_INTERVAL" if len(values) == 1 else "INSUFFICIENT_COMPLETE_PAIRED_PARENTS", mean_difference=float(values.mean()) if len(values) else None,
                          lower_95=None, upper_95=None)
        estimates.append(record)
    # Rows lacking a logged seed rank cannot disappear from the pairing ledger.
    for row in rows:
        if not row["oracle"] and row["total_seed_rank"] is None:
            details.append({"parameterization": row["parameterization"], "degree": row["degree"],
                            "parent": row["parent"], "state": row["state"], "control": row["method"],
                            "row_id": row["row_id"], "matched": False, "reason": "missing_total_seed_rank"})
    return details, estimates


def frontier_rows(rows):
    """Empirical nondominance inside one parent/state; never pool scenes."""
    result = []
    for axis in FRONTIER_AXES:
        groups = defaultdict(list)
        for row in rows:
            if row["metric_valid"] and not row["oracle"] and row[axis] is not None:
                groups[(row["parameterization"], row["parent"], row["state"])].append(row)
        for (kind, parent, state), points in groups.items():
            for row in points:
                x, y = row[axis], row["relative_H_step_error"]
                dominated = any(q[axis] <= x and q["relative_H_step_error"] <= y
                                and (q[axis] < x or q["relative_H_step_error"] < y) for q in points)
                result.append({"parameterization": kind, "parent": parent, "state": state,
                               "method": row["method"], "degree": row["degree"], "row_id": row["row_id"],
                               "axis": axis, "cost": x, "relative_H_step_error": y,
                               "nondominated_within_parent_state": not dominated,
                               "full_solver_RHS": row["full_solver_RHS"], "actual_rank": row["actual_rank"],
                               "total_seed_rank": row["total_seed_rank"], "wall_seconds": row["wall_seconds"]})
    return result


def frontier_matches(rows):
    """Separate observed rank/action pairs; no bootstrap or seed-rank waiver."""
    valid = [r for r in rows if r["metric_valid"] and not r["oracle"]]
    matches = []
    for index, left in enumerate(valid):
        for right in valid[index+1:]:
            if (left["parameterization"], left["parent"], left["state"]) != (right["parameterization"], right["parent"], right["state"]) or left["method"] == right["method"]:
                continue
            for axis in FRONTIER_AXES:
                if left[axis] is not None and left[axis] == right[axis]:
                    matches.append({"parameterization": left["parameterization"], "parent": left["parent"], "state": left["state"],
                                    "axis": axis, "matched_cost": left[axis], "left_row_id": left["row_id"], "right_row_id": right["row_id"],
                                    "left_method": left["method"], "right_method": right["method"],
                                    "left_degree": left["degree"], "right_degree": right["degree"],
                                    "left_total_seed_rank": left["total_seed_rank"], "right_total_seed_rank": right["total_seed_rank"],
                                    "difference_left_minus_right": left["relative_H_step_error"]-right["relative_H_step_error"],
                                    "scope": "observed point comparison only; not a strict seed-plus-rank bootstrap pair"})
    return matches


def collect_jobs(root, issues):
    jobs, phases = [], []
    for path in sorted((root/"results/jobs").glob("*/job_receipt.json")):
        raw = read_json(path, issues)
        if not isinstance(raw, dict):
            continue
        row = {"source": str(path), "job": raw.get("job", path.parent.name), "stage": raw.get("stage"),
               "status": raw.get("status"), "process_cpu_seconds": finite(raw.get("process_cpu_seconds")),
               "gpu_occupation_seconds": finite(raw.get("gpu_occupation_seconds")),
               "wall_seconds": finite(raw.get("wall_seconds")), "peak_cpu_rss_bytes": raw.get("peak_cpu_rss_bytes"),
               "peak_gpu_allocated_bytes": raw.get("peak_gpu_allocated_bytes"), "counts": raw.get("counts", {}),
               "exclusive_walls": raw.get("exclusive_walls", {})}
        jobs.append(row)
        # Per-span process_cpu is inclusive and is deliberately not summed.
        grouped = defaultdict(lambda: {"events": 0, "failed_events": 0, "exclusive_wall_seconds": 0., "counters": Counter()})
        for event, _, _ in read_jsonl(path.parent/"cost.jsonl", issues):
            key = (str(event.get("phase", "unspecified")), str(event.get("event", "unspecified")))
            group = grouped[key]
            group["events"] += 1
            group["failed_events"] += event.get("status") not in SUCCESS
            wall = finite(event.get("exclusive_wall_seconds"))
            if wall is not None:
                group["exclusive_wall_seconds"] += wall
            for name, value in (event.get("counters") or {}).items():
                value = finite(value)
                if value is not None:
                    group["counters"][name] += value
        for (phase, event), group in grouped.items():
            phases.append({"job": row["job"], "phase": phase, "event": event, **group})
    return jobs, phases


def gate_rows(root, issues):
    candidates = {"G0_REAL": ["results/G0_REAL.json"], "G0_ALGEBRA": ["results/G0_ALGEBRA.json"],
                  "REPRESENTATION_GATE": ["results/REPRESENTATION_GATE.json"],
                  "A1": ["results/A1/QUALITY_GATE.json", "results/A1/GATE.json", "results/A1_GATE.json"],
                  "A2": ["results/A2/QUALITY_GATE.json", "results/A2/GATE.json", "results/A2_GATE.json"]}
    result = []
    def visit(name, source, value, key=""):
        if isinstance(value, dict):
            for child, item in value.items():
                visit(name, source, item, key+"."+child if key else child)
        else:
            result.append({"gate": name, "source": source, "key": key, "value": value,
                           "provenance": "copied_from_existing_gate_not_recomputed"})
    for name, paths in candidates.items():
        existing = [root/p for p in paths if (root/p).exists()]
        if not existing:
            result.append({"gate": name, "source": paths[0], "key": "status", "value": "MISSING_NOT_RUN",
                           "provenance": "missing_gate_artifact"})
        for path in existing:
            raw = read_json(path, issues)
            if raw is not None:
                visit(name, str(path), raw)
    return result


def make_plots(rows, degrees, frontiers, figure_dir, check_cpu):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as exc:
        return {"status": "PLOTS_UNAVAILABLE", "reason": str(exc), "files": []}
    files = []
    figure_dir.mkdir(parents=True, exist_ok=True)
    kinds = sorted({r["parameterization"] for r in rows})
    if not kinds:
        return {"status": "PLOTS_NOT_RUN_NO_REPLAY", "files": []}
    for kind_index, kind in enumerate(kinds):
        check_cpu()
        fig, ax = plt.subplots(figsize=(8, 5), layout="constrained")
        methods = sorted({r["method"] for r in rows if r["parameterization"] == kind and not r["oracle"]})
        for method in methods:
            records = [d for d in degrees if d["parameterization"] == kind and d["method"] == method]
            seed_ranks = sorted({d["total_seed_rank"] for d in records}, key=lambda x: (-1 if x is None else x))
            for seed_rank in seed_ranks:
                observed = sorted([d for d in records if d["total_seed_rank"] == seed_rank and d["median_finite_subset_only"] is not None], key=lambda x: x["degree"])
                if observed:
                    label = method + f" seeds={seed_rank} (finite subset)"
                    ax.plot([d["degree"] for d in observed], [d["median_finite_subset_only"] for d in observed], marker="o", label=label)
        ax.axhline(.05, color="black", linestyle="--", linewidth=1, label="prespecified 0.05 screening line")
        ax.set(xlabel="Feedback degree", ylabel="Relative H-step error", title=f"Degree comparison: {kind}")
        ax.set_yscale("symlog", linthresh=.001)
        ax.set_ylim(bottom=0.)  # H-norm errors are nonnegative; retain true zeros.
        ax.grid(alpha=.2)
        ax.legend(fontsize=7)
        subset = [r for r in rows if r["parameterization"] == kind]
        counts = {k: sum(bool(r[k]) for r in subset) for k in ("failed", "invalid", "zero_reference", "missing", "oracle")}
        fig.supxlabel("Historical feasibility only; finite subset medians are not gates.\n"+str(counts), fontsize=8)
        base = figure_dir/f"degree_main_{kind_index}"
        for suffix in ("png", "svg"):
            fig.savefig(base.with_suffix("."+suffix), dpi=180)
            files.append(str(base.with_suffix("."+suffix)))
        plt.close(fig)
        for axis in FRONTIER_AXES:
            points = [r for r in frontiers if r["parameterization"] == kind and r["axis"] == axis]
            if not points:
                continue
            scenes = sorted({(r["parent"], r["state"]) for r in rows if r["parameterization"] == kind and r["parent"] is not None and r["state"] is not None})
            if not scenes:
                continue
            columns = min(3, len(scenes))
            height = math.ceil(len(scenes)/columns)
            fig, axes = plt.subplots(height, columns, figsize=(5*columns, 3.6*height), squeeze=False, layout="constrained")
            for ax, (parent, state) in zip(axes.flat, scenes):
                scene_points = [r for r in points if (r["parent"], r["state"]) == (parent, state)]
                for method in methods:
                    sub = [r for r in scene_points if r["method"] == method]
                    if sub:
                        ax.scatter([r["cost"] for r in sub], [r["relative_H_step_error"] for r in sub], s=17, alpha=.65, label=method)
                boundary = sorted([r for r in scene_points if r["nondominated_within_parent_state"]], key=lambda x: x["cost"])
                if boundary:
                    ax.plot([r["cost"] for r in boundary], [r["relative_H_step_error"] for r in boundary], color="black", linewidth=1, alpha=.7)
                ax.axhline(.05, color="gray", linestyle="--", linewidth=.7)
                ax.set(title=f"parent {parent}, state {state}", xlabel=FRONTIER_LABELS[axis], ylabel="Relative H-step error")
                ax.set_yscale("symlog", linthresh=.001)
                ax.set_ylim(bottom=0.)
                ax.grid(alpha=.2)
            for ax in list(axes.flat)[len(scenes):]:
                ax.set_visible(False)
            handles, labels = [], []
            for ax in axes.flat:
                h, l = ax.get_legend_handles_labels()
                for handle, label in zip(h, l):
                    if label not in labels:
                        handles.append(handle); labels.append(label)
            if handles:
                fig.legend(handles, labels, loc="outside upper center", ncol=min(4, len(labels)), fontsize=7)
            fig.supxlabel("Observed within-scene frontier. Failures/missing retained in CSV; no rank interpolation.\nOnline actions exclude audit/shared preparation; full solve RHS and replay attribution are separate.", fontsize=8)
            base = figure_dir/f"frontier_{axis}_{kind_index}"
            for suffix in ("png", "svg"):
                fig.savefig(base.with_suffix("."+suffix), dpi=180)
                files.append(str(base.with_suffix("."+suffix)))
            plt.close(fig)
            check_cpu()
    return {"status": "GENERATED", "files": files, "font_language": "English figure labels; Chinese report"}


def update_receipt(root, record):
    path = root/"research/claim_audit/summary_worker_receipt.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    previous = json.loads(path.read_text()) if path.exists() else {"worker": "claim_audit_summary", "runs": []}
    previous.setdefault("runs", []).append(record)
    previous.update(process_cpu_seconds=sum(r.get("process_cpu_seconds", 0.) for r in previous["runs"]),
                    cpu_budget_seconds=60., gpu_occupation_seconds=0., network_requests=0,
                    physics_runs=0, sha256_checks=0,
                    real_replay_run="NOT_RUN_BY_SUMMARY_TOOL_NO_PHYSICS",
                    real_replay_evidence_read=any(r.get("run_type")=="summarize" and r.get("status")=="COMPLETE" for r in previous["runs"]),
                    measurement="Actual process CPU for each recorded run; process startup/imports included; no network wall charged")
    path.write_text(json.dumps(previous, indent=2, ensure_ascii=False, allow_nan=False)+"\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--replay", type=Path)
    parser.add_argument("--actions", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--figure-dir", type=Path)
    parser.add_argument("--expected-parent-map", type=Path, help="Optional JSON mapping parameterization to its explicitly planned parents")
    parser.add_argument("--bootstrap-samples", type=int, default=2000)
    parser.add_argument("--bootstrap-seed", type=int, default=20261005)
    parser.add_argument("--no-plots", action="store_true")
    args = parser.parse_args(argv)
    if args.bootstrap_samples != 2000:
        parser.error("This bounded worker contract fixes the descriptive bootstrap at 2000 draws")
    root = args.root.resolve()
    output = args.output or root/"results/summary"
    figure_dir = args.figure_dir or root/"figures"
    receipt_path = root/"research/claim_audit/summary_worker_receipt.json"
    previous_cpu = 0.
    if receipt_path.exists():
        previous_cpu = finite(json.loads(receipt_path.read_text()).get("process_cpu_seconds")) or 0.
    def check_cpu():
        if previous_cpu + time.process_time() >= 60:
            raise RuntimeError("SUMMARY_WORKER_CPU_BUDGET_60_SECONDS")
    status, error = "FAILED", None
    try:
        check_cpu()
        issues = []
        config = read_json(root/"configs/frozen.json", issues, required=True) or {}
        replay_path = args.replay or root/"results/replay/replay.jsonl"
        actions_path = args.actions or root/"results/replay/actions.jsonl"
        raw, non_methods = select_method_records(read_jsonl(replay_path, issues))
        selected_source = str(replay_path)
        if not raw:
            actions = read_jsonl(actions_path, issues)
            raw, excluded_actions = select_method_records(actions, actions=True)
            non_methods.extend(excluded_actions)
            selected_source = str(actions_path)
        if not raw:
            issues.append({"source": selected_source, "line": None, "kind": "missing_replay_records", "error": "NOT_RUN"})
        rows = [normalize(r, source, line, config.get("replay_H_relative_floor", 1e-12)) for r, source, line in raw]
        parent_map = (read_json(args.expected_parent_map, issues, required=True) if args.expected_parent_map else
                      planned_parent_map(config, read_json(root/"configs/parents.json", issues)))
        if parent_map:
            declared_kind = {ident(parent): kind for kind, parents in parent_map.items() for parent in parents}
            for row in rows:
                if row["parameterization"] == "unspecified" and row["parent"] in declared_kind:
                    row["parameterization"] = declared_kind[row["parent"]]
        # Include the declared final parameterization in legacy identities.
        mark_duplicates(rows)
        scopes = expected_scope(config, rows, parent_map)
        grid = completeness(rows, scopes, config.get("replay_degrees", list(range(6))))
        degrees = degree_summary(rows, grid)
        pair_details, bootstrap = paired_parent_bootstrap(rows, scopes, samples=2000, seed=args.bootstrap_seed)
        frontiers = frontier_rows(rows)
        frontier_pairs = frontier_matches(rows)
        jobs, phases = collect_jobs(root, issues)
        gates = gate_rows(root, issues)
        output.mkdir(parents=True, exist_ok=True)
        for name, values, fields in (
            ("REPLAY_ROWS.csv", rows, ROW_FIELDS), ("REPLAY_COMPLETENESS.csv", grid, None),
            ("DEGREE_MAIN.csv", degrees, None), ("PAIRED_STATE_DETAILS.csv", pair_details, None),
            ("PAIRED_PARENT_BOOTSTRAP.csv", bootstrap, None), ("FRONTIER_RAW.csv", frontiers, None),
            ("FRONTIER_MATCHED_PAIRS.csv", frontier_pairs, None), ("NON_METHOD_RECORDS.csv", non_methods, None),
            ("JOB_RECEIPTS.csv", jobs, None), ("COST_PHASES.csv", phases, None),
            ("GATE_SNAPSHOT.csv", gates, None), ("INPUT_ISSUES.csv", issues, None)):
            csv_write(output/name, values, fields)
        plots = {"status": "NOT_RUN_BY_OPTION", "files": []} if args.no_plots else make_plots(rows, degrees, frontiers, figure_dir, check_cpu)
        # Figure input CSVs are the actual plotted rows, not smoothed fits.
        if not args.no_plots:
            csv_write(figure_dir/"degree_main_raw.csv", degrees)
            csv_write(figure_dir/"frontier_raw.csv", frontiers)
        counts = {k: sum(bool(r[k]) for r in rows) for k in ("metric_valid", "failed", "invalid", "zero_reference", "missing", "duplicate", "oracle")}
        report = {"status": "EVIDENCE_SUMMARIZED" if rows else "NOT_RUN_NO_REPLAY",
                  "data_scope": config.get("dataset_exposure", "historically_exposed_feasibility"),
                   "selected_replay_source": selected_source, "replay_rows": len(rows), "counts": counts,
                   "non_method_records_retained_separately": len(non_methods),
                   "non_method_record_kinds": dict(Counter(str(r["record_kind"]) for r in non_methods)),
                   "non_method_records_not_failed_or_missing_experiment_cells": True,
                  "counts_overlap": True, "missing_expected_cells": sum(c["missing_cell"] for c in grid),
                  "input_issues": issues, "input_issue_counts": dict(Counter(issue["kind"] for issue in issues)),
                  "bootstrap_draws": 2000, "bootstrap_unit": "parent, after averaging paired required states",
                  "bootstrap_requires_exact_total_seed_rank_and_actual_rank": True,
                   "bootstrap_intervals_are_descriptive_historical_feasibility_only": True,
                   "one_parent_bootstrap_is_degenerate_no_interval_or_overall_significance": True,
                   "rank_only_controls_may_have_no_strict_bootstrap_pairs": True,
                  "science_judgment": "RETAINED_BY_PARENT_NOT_COMPUTED",
                  "existing_gate_artifacts_copied_not_recomputed": True,
                  "plots": plots, "job_count": len(jobs),
                  "job_process_cpu_seconds_all_statuses": sum(r["process_cpu_seconds"] or 0 for r in jobs),
                  "job_gpu_occupation_seconds_all_statuses": sum(r["gpu_occupation_seconds"] or 0 for r in jobs),
                  "receipt_wall_seconds_not_summed_as_deployment_cost": True,
                   "counter_axes": "actual rank; logged online F/F*/L/L* vector RHS; non-audit F/F* separately",
                   "replay_wall_attribution_includes_offline_audit_not_online_deployment": True,
                   "canonical_replay_wall_attribution_excludes_shared_geometry_state_reference_U": True,
                   "legacy_wall_scopes_retained_as_logged": True,
                   "cumulative_basis_attribution_not_summed_across_degrees": True,
                  "scope_by_parameterization": scopes}
        (output/"SUMMARY.json").write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False)+"\n")
        text = ("# A20 机械证据汇总\n\n"
                f"数据范围：{report['data_scope']}。读取 {len(rows)} 条 replay 记录；预定格缺失 {report['missing_expected_cells']}。\n\n"
                f"shared geometry/state/reference/U 与其他非 method 记录共 {len(non_methods)} 条，另留 NON_METHOD_RECORDS.csv；它们不充作失败或缺失实验行。无 record_kind 的 legacy method 记录仍可读取。\n\n"
                "失败、invalid、零参考、缺失、重复、oracle 单独计数；标志可重叠，不能相加当样本数。\n\n"
                + "\n".join(f"- {key}：{value}" for key, value in counts.items()) + "\n\n"
                "配对只采用相同 total seed rank 和 actual rank 的状态；actual_seed_ranks 各压缩流 rank 的和是 total_seed_rank，不以 requested budget 或 joint/basis rank 替代。先平均同父对象所有预定状态差值，完整父对象再做登记的 2000 次 parent bootstrap；控制重复先在状态内汇总。缺一状态的父对象不进入区间，缺失原因保留在 PAIRED_STATE_DETAILS.csv。单 parent（包括 voxel）标 degenerate/descriptive，不给区间或总体显著性；区间仅描述历史可行性，未构成盲测或泛化证据。SOM/random 的 rank-only 匹配可存在，但可能没有严格 seed-plus-rank bootstrap pair，不能补造区间。\n\n"
                "DEGREE_MAIN.csv 的有限子集统计不是 gate；缺失或失败不被成功样本平均掩盖，FAILED 即便记录了 fullfallback_used 也不成为有效 reduced-method 指标。FRONTIER_RAW.csv 和 FRONTIER_MATCHED_PAIRS.csv 保留逐父对象/状态的 rank/action 观测前沿及确实匹配点；未插值、未 padding，也未汇集不同场景。优先使用已记录的 online_Maxwell_vector_actions（F/F*/L/L* 真实 RHS）；非 audit F/F* 单列。无法分离 audit 的 legacy action totals 仍在原 counter 列，不伪充在线 action 前沿。\n\n"
                "wall_total_attributed（保存在 wall_seconds 与同名原列）包含 offline audit，仅是 replay attribution；wall_basis/projection/QP/fallback/audit 各自保留，不等于在线完整部署。共享 geometry/state/reference/U 成本另表保留并由完整 job receipt 计账；逐 degree 的 basis attribution 是累计轨迹，不能再跨 degrees 求和。\n\n"
                "GATE_SNAPSHOT.csv 只复制已有 gate；没有重算 PASS/FAIL。失败 jobs 的资源照样计入 JOB_RECEIPTS.csv；相互嵌套的墙钟与 CPU span 不被重复累加。\n\n"
                f"绘图状态：{plots['status']}。科学解释与最终判断由父线程另写。所有来源错误见 INPUT_ISSUES.csv。\n")
        (output/"SUMMARY_REPORT.md").write_text(text, encoding="utf-8")
        check_cpu()
        status = "COMPLETE"
        print(json.dumps({"status": report["status"], "rows": len(rows), "counts": counts,
                          "missing_cells": report["missing_expected_cells"], "plots": plots["status"],
                          "output": str(output)}, ensure_ascii=False))
    except Exception as exc:
        error = type(exc).__name__+": "+str(exc)
        print(error, file=sys.stderr)
    finally:
        update_receipt(root, {"run_type": "summarize", "completed_utc": datetime.now(timezone.utc).isoformat(),
                             "status": status, "error": error, "process_cpu_seconds": time.process_time(),
                             "wall_seconds": time.perf_counter()-STARTED_WALL, "argv": sys.argv[1:]})
    return 0 if status == "COMPLETE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
