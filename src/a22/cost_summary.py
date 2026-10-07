"""Read recorded A22 costs without issuing physics or changing accounting.

Only final job receipts (or a marked live checkpoint) and unique registered
external scopes provide resource charges.  Span rows describe recorded work;
their overlapping CPU/wall times are never added to an inclusive job charge.
This module has no scientific statistics, gate logic, remote or physics API.
"""
from __future__ import annotations

import csv
import json
import math
import os
from pathlib import Path
import re
from tempfile import NamedTemporaryFile
from typing import Mapping


NOT_MEASURED = "NOT_MEASURED"
_JOB_ID = re.compile(r"a22-[A-Za-z0-9_-]{1,100}\Z")
_OLD_SCOPE = re.compile(r"^(?:source[-_: ]+)?a(?:20|21)(?:[-_: ]|$)", re.I)
_RESOURCES = {
    "wall_seconds": ("wall_seconds", "duration_seconds", "inclusive_wall_seconds"),
    "process_cpu_seconds": ("process_cpu_seconds", "CPU_seconds", "cpu_seconds",
                            "charged_cpu_seconds_conservative"),
    "gpu_occupation_seconds": ("gpu_occupation_seconds", "GPU_seconds",
                               "gpu_seconds", "gpu_wall_seconds"),
}
# Aliases name the same recorded quantity; they are selected, never summed.
COUNTER_FIELDS = {
    "F_vectors": ("F_actions", "F_vectors", "F_matvec_rhs"),
    "F_star_vectors": ("F_adjoint_actions", "F_star_vectors", "F_adjoint_rhs"),
    "L_vectors": ("L_actions", "L_vectors", "L_matvec_rhs"),
    "L_star_vectors": ("L_adjoint_actions", "L_star_vectors", "L_adjoint_rhs"),
    "B_vectors": ("B_rhs", "B_vectors", "B_actions"),
    "B_star_vectors": ("B_adjoint_rhs", "B_star_vectors", "B_adjoint_actions"),
    "B_star_voxel_vectors": ("B_adjoint_voxel_rhs", "B_star_voxel_vectors"),
    "compressed_B_current_columns": ("compressed_B_current_columns",),
    "S_vectors": ("S_actions", "S_vectors", "S_rhs"),
    "S_star_vectors": ("S_adjoint_actions", "S_star_vectors", "S_adjoint_rhs"),
    "Maxwell_matvec_rhs_aggregate": ("Maxwell_matvec_rhs", "Maxwell_matvec_RHS"),
    "full_forward_calls": ("full_forward_calls",),
    "full_forward_RHS": ("full_forward_RHS", "full_forward_rhs"),
    "full_tangent_calls": ("full_tangent_calls",),
    "full_tangent_RHS": ("full_tangent_RHS", "full_tangent_rhs"),
    "full_adjoint_calls": ("full_adjoint_calls",),
    "full_adjoint_RHS": ("full_adjoint_RHS", "full_adjoint_rhs"),
    "full_LU_factorizations": ("full_LU_factorizations", "full_lu_factorizations"),
    "retained_LU_factorizations": ("retained_factorizations", "retained_LU_factorizations"),
    "projected_LU_factorizations": ("projected_factorizations", "projected_LU_factorizations"),
    "full_state_backward_residual_L_rhs": ("full_state_backward_residual_L_rhs",),
    "full_state_receiver_rhs": ("full_state_receiver_rhs",),
    "full_state_Goff_rhs": ("full_state_Goff_rhs",),
    "full_tangent_receiver_rhs": ("full_tangent_receiver_rhs",),
    "full_adjoint_receiver_rhs": ("full_adjoint_receiver_rhs",),
    "health_reference_full_RHS": ("health_reference_full_RHS",),
    "health_reference_receiver_RHS": ("health_reference_receiver_RHS",),
    "health_reference_residual_L_rhs": ("health_reference_residual_L_rhs",),
    "new_data_generation_F_calls": ("data_generation_F_calls", "perturbation_F_calls",
                                    "data_F_calls", "generation_F_calls"),
    "new_teacher_labels": ("new_teacher_labels", "new_labels"),
    "shared_cache_hits": ("shared_cache_hits", "shared_cache_hit"),
    "same_material_full_state_cache_hits": ("same_material_full_state_cache_hits",),
    "reduced_core_rhs": ("reduced_core_rhs",),
}
_EXCLUSIVE_FAMILY = ("F_vectors", "F_star_vectors", "L_vectors", "L_star_vectors")
CSV_FIELDS = (
    "record_type", "job_id", "scope", "event", "event_id", "phase", "stage", "role",
    "status", "accounting_status", "source", "source_line", "resource_additive",
    "action_total_authority", "live_checkpoint", "duration_seconds", "wall_seconds",
    "exclusive_wall_seconds", "process_cpu_seconds", "exclusive_process_cpu_seconds",
    "gpu_occupation_seconds", "measurement", "scene_id", "method", "actual_rank",
    "error_type", "error", "expected_unsafe_core", "expectation_origin",
    "cache_hits_json", "cache_hit_recorded", "stage_gpu_seconds_json",
    "exclusive_operator_vectors_recorded", "exclusive_operator_vectors_recording",
    "counter_alias_conflicts_json", "raw_counters_json", "reference_receipt", "duplicate_of",
) + tuple(COUNTER_FIELDS)


def _where(root, path):
    return path.relative_to(root).as_posix()


def _within(root, path):
    return path.resolve().is_relative_to(root)


def _issue(issues, kind, source, **detail):
    issues.append(dict(kind=kind, source=source, **detail))


def _numeric(value, *, counter=False):
    if isinstance(value, bool) or value is None:
        return NOT_MEASURED
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return NOT_MEASURED
    if not math.isfinite(number) or number < 0:
        return NOT_MEASURED
    if counter:
        return int(number) if number == int(number) else NOT_MEASURED
    return number


def _first_number(record, names, *, counter=False):
    for name in names:
        if name in record:
            return _numeric(record[name], counter=counter)
    return NOT_MEASURED


def _json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)


def _safe_value(value):
    """Keep audit JSON serializable; invalid numeric records stay missing."""
    if isinstance(value, Mapping):
        return {str(key): _safe_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe_value(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return NOT_MEASURED
    return value


def _blank(**values):
    result = {key: NOT_MEASURED for key in CSV_FIELDS}
    result.update(resource_additive=False, action_total_authority=False,
                  live_checkpoint=False, duplicate_of=NOT_MEASURED)
    result.update(values)
    return result


def _row(record, *, source, source_line, kind, job=None, scope=None, live=False):
    counts = record.get("counts", record.get("counters", {}))
    counts = counts if isinstance(counts, Mapping) else {}
    outcome = record.get("outcome", {})
    outcome = outcome if isinstance(outcome, Mapping) else {}
    row = _blank(
        record_type=kind, source=source, source_line=source_line,
        job_id=job or record.get("job_id", record.get("job", NOT_MEASURED)),
        scope=scope or record.get("scope", NOT_MEASURED),
        event=record.get("event", kind), event_id=record.get("event_id", NOT_MEASURED),
        phase=record.get("phase", NOT_MEASURED), stage=record.get("stage") or NOT_MEASURED,
        role=record.get("role", NOT_MEASURED), status=record.get("status", NOT_MEASURED),
        accounting_status="RECORDED", live_checkpoint=live,
        measurement=record.get("measurement", NOT_MEASURED),
        scene_id=record.get("scene_id", NOT_MEASURED), method=record.get("method", NOT_MEASURED),
        actual_rank=record.get("actual_rank", record.get("current_rank", NOT_MEASURED)),
        error_type=record.get("error_type", outcome.get("error_type", NOT_MEASURED)),
        error=record.get("error", record.get("reason", outcome.get("error", NOT_MEASURED))),
        reference_receipt=record.get("receipt") or NOT_MEASURED,
        raw_counters_json=_json(_safe_value(dict(counts))),
        stage_gpu_seconds_json=_json(_safe_value(record["stage_gpu_seconds"]))
            if isinstance(record.get("stage_gpu_seconds"), Mapping) else NOT_MEASURED,
    )
    for key, aliases in _RESOURCES.items():
        row[key] = _first_number(record, aliases)
    row["duration_seconds"] = row["wall_seconds"]
    row["exclusive_wall_seconds"] = _first_number(record, ("exclusive_wall_seconds",))
    row["exclusive_process_cpu_seconds"] = _first_number(record, ("exclusive_process_cpu_seconds",))
    conflicts = {}
    for key, aliases in COUNTER_FIELDS.items():
        row[key] = _first_number(counts, aliases, counter=True)
        present = {alias: _numeric(counts[alias], counter=True) for alias in aliases if alias in counts}
        if len(set(present.values())) > 1:
            conflicts[key] = present
    row["counter_alias_conflicts_json"] = _json(conflicts)
    known = [row[key] for key in _EXCLUSIVE_FAMILY if row[key] != NOT_MEASURED]
    if known:
        row["exclusive_operator_vectors_recorded"] = sum(known)
        row["exclusive_operator_vectors_recording"] = "COMPLETE" if len(known) == 4 else "PARTIAL"
    cached = {key: value for key, value in counts.items() if "cache" in str(key).lower()
              and "hit" in str(key).lower()}
    row["cache_hits_json"] = _json(_safe_value(cached))
    if "cache_hit" in record:
        row["cache_hit_recorded"] = record["cache_hit"]
    elif cached:
        numeric = [_numeric(value, counter=True) for value in cached.values()]
        row["cache_hit_recorded"] = any(value != NOT_MEASURED and value > 0 for value in numeric)
    if "expected_unsafe_core" in record:
        row["expected_unsafe_core"] = record["expected_unsafe_core"]
        row["expectation_origin"] = "explicit_record_field"
    elif row["error_type"] == "UnsafeCore" and (
            "expected" in str(row["event"]).lower()
            or _numeric(counts.get("expected_invalid_core_probes"), counter=True) not in (NOT_MEASURED, 0)):
        row["expected_unsafe_core"] = True
        row["expectation_origin"] = "recorded_event_or_counter_and_error_type"
    return row


def _load_object(root, path, issues):
    source = _where(root, path)
    if not _within(root, path):
        _issue(issues, "OUT_OF_SCOPE_PATH", source)
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        _issue(issues, "UNREADABLE_ACCOUNTING_JSON", source, error=str(error))
        return None


def _allowed(record, job=None):
    campaign = record.get("campaign")
    if campaign is not None and str(campaign).upper() != "A22":
        return False
    identity = record.get("job_id", record.get("job", job))
    if identity is not None and (not _JOB_ID.fullmatch(str(identity)) or (job and identity != job)):
        return False
    scope = record.get("scope")
    return not (scope is not None and _OLD_SCOPE.match(str(scope)))


def _resource_summary(rows, key, unresolved, live):
    values = [row[key] for row in rows if row["resource_additive"]]
    known = [value for value in values if value != NOT_MEASURED]
    missing = sum(value == NOT_MEASURED for value in values) + len(unresolved)
    recorded = sum(known) if known else NOT_MEASURED
    complete = bool(values) and missing == 0
    status = "PROVISIONAL" if complete and live else "RECORDED" if complete else "PARTIAL" if known else NOT_MEASURED
    return dict(value=recorded if complete else NOT_MEASURED, recorded_sum=recorded,
                status=status, explicit_record_count=len(known), missing_record_count=missing,
                definition="unique inclusive receipt charges only; span rows excluded")


def _action_summary(authority, field):
    known = [row[field] for row in authority if row[field] != NOT_MEASURED]
    return dict(recorded_sum=sum(known) if known else NOT_MEASURED,
                explicit_record_count=len(known), unrecorded_record_count=len(authority)-len(known),
                status="RECORDED" if known and len(known) == len(authority) else "PARTIAL" if known else NOT_MEASURED)


def summarize_costs(root):
    """Return recorded A22 accounting without writing files or billing work.

    Final ``job_receipt.json`` supersedes ``accounting_checkpoint.json`` for
    the same ``results/jobs/a22-*`` directory.  Job-local ``cost.jsonl`` is
    descriptive; the mirrored global COST/JOB/FAILURE ledgers are not read.
    External receipt references are preserved but never followed/rebilled.
    """
    root = Path(root).resolve()
    rows, sources, issues, excluded, unresolved = [], [], [], [], []
    jobs_root = root / "results/jobs"
    jobs = sorted(jobs_root.glob("a22-*")) if jobs_root.exists() else []
    for directory in jobs:
        job = directory.name
        if not directory.is_dir() or not _JOB_ID.fullmatch(job):
            continue
        if not _within(root, directory) or directory.is_symlink():
            excluded.append(dict(source=_where(root, directory), reason="OUT_OF_SCOPE_JOB_PATH"))
            continue
        final = directory / "job_receipt.json"
        checkpoint = directory / "accounting_checkpoint.json"
        path = final if final.is_file() else checkpoint if checkpoint.is_file() else None
        if path is None:
            unresolved.append(job)
            rows.append(_blank(record_type="missing_job_receipt", job_id=job,
                               event="job_receipt", source=_where(root, directory),
                               accounting_status=NOT_MEASURED, status=NOT_MEASURED))
        else:
            source = _where(root, path)
            sources.append(source)
            record = _load_object(root, path, issues)
            if not isinstance(record, Mapping):
                unresolved.append(job)
                _issue(issues, "JOB_RECEIPT_NOT_OBJECT", source)
                rows.append(_blank(record_type="invalid_job_receipt", job_id=job,
                                   event="job_receipt", source=source,
                                   accounting_status="UNREADABLE", status=NOT_MEASURED))
            elif not _allowed(record, job):
                excluded.append(dict(source=source, reason="NON_A22_OR_MISMATCHED_JOB_RECEIPT"))
                # A conflicting campaign does not authorize its job-local log.
                continue
            else:
                row = _row(record, source=source, source_line=1,
                           kind="job_receipt" if path == final else "job_checkpoint",
                           job=job, live=path != final)
                row.update(resource_additive=True, action_total_authority=True)
                rows.append(row)
        cost_path = directory / "cost.jsonl"
        if not cost_path.is_file():
            continue
        source = _where(root, cost_path)
        if not _within(root, cost_path):
            excluded.append(dict(source=source, reason="OUT_OF_SCOPE_SPAN_PATH"))
            continue
        sources.append(source)
        seen_events = {}
        try:
            with cost_path.open(encoding="utf-8") as stream:
                for number, text in enumerate(stream, 1):
                    if not text.strip():
                        continue
                    try:
                        record = json.loads(text)
                    except ValueError as error:
                        _issue(issues, "UNREADABLE_SPAN_JSON", source, source_line=number, error=str(error))
                        rows.append(_blank(record_type="invalid_span", job_id=job, source=source,
                                           source_line=number, accounting_status="UNREADABLE"))
                        continue
                    if not isinstance(record, Mapping) or not _allowed(record, job):
                        excluded.append(dict(source=source, source_line=number, reason="NON_A22_SPAN"))
                        continue
                    row = _row(record, source=source, source_line=number, kind="span", job=job)
                    event_id = record.get("event_id")
                    if event_id and event_id in seen_events:
                        row.update(record_type="duplicate_span", duplicate_of=seen_events[event_id],
                                   accounting_status="DUPLICATE_EVENT_ID")
                    elif event_id:
                        seen_events[event_id] = source + ":" + str(number)
                    rows.append(row)
        except OSError as error:
            _issue(issues, "UNREADABLE_SPAN_FILE", source, error=str(error))

    external_root = root / "results/a22"
    external_paths = [external_root / "external_cpu_receipts.json",
                      external_root / "external_cpu_receipts.jsonl"]
    directory = external_root / "external_cpu_receipts"
    if directory.is_dir() and _within(root, directory):
        external_paths.extend(sorted(directory.glob("*.json")))
        external_paths.extend(sorted(directory.glob("*.jsonl")))
    seen_scopes = {}
    for path in external_paths:
        if not path.is_file():
            continue
        source = _where(root, path)
        sources.append(source)
        if path.suffix == ".jsonl":
            if not _within(root, path):
                excluded.append(dict(source=source, reason="OUT_OF_SCOPE_EXTERNAL_PATH"))
                continue
            documents = []
            try:
                with path.open(encoding="utf-8") as stream:
                    for number, text in enumerate(stream, 1):
                        if not text.strip():
                            continue
                        try:
                            documents.append((number, json.loads(text)))
                        except ValueError as error:
                            _issue(issues, "UNREADABLE_EXTERNAL_JSON", source, source_line=number, error=str(error))
                            unresolved.append(source + ":" + str(number))
            except OSError as error:
                _issue(issues, "UNREADABLE_EXTERNAL_FILE", source, error=str(error))
                unresolved.append(source)
        else:
            value = _load_object(root, path, issues)
            if isinstance(value, list):
                documents = list(enumerate(value, 1))
            elif isinstance(value, Mapping) and "scope" in value:
                documents = [(1, value)]
            elif isinstance(value, Mapping) and isinstance(value.get("receipts", value.get("external_cpu_receipts")), list):
                documents = list(enumerate(value.get("receipts", value.get("external_cpu_receipts")), 1))
            else:
                _issue(issues, "EXTERNAL_RECEIPT_CONTAINER_NOT_RECOGNIZED", source)
                unresolved.append(source)
                documents = []
        for number, record in documents:
            if not isinstance(record, Mapping) or not _allowed(record):
                excluded.append(dict(source=source, source_line=number, reason="NON_A22_EXTERNAL_RECEIPT"))
                continue
            scope = record.get("scope")
            if not isinstance(scope, str) or not scope:
                _issue(issues, "EXTERNAL_SCOPE_NOT_RECORDED", source, source_line=number)
                unresolved.append(source + ":" + str(number))
                continue
            row = _row(record, source=source, source_line=number,
                       kind="external_receipt", scope=scope)
            row.update(resource_additive=True, action_total_authority=True)
            if scope in seen_scopes:
                previous, original = seen_scopes[scope]
                row.update(resource_additive=False, action_total_authority=False,
                           duplicate_of=previous["source"] + ":" + str(previous["source_line"]))
                if dict(record) == original:
                    row.update(record_type="duplicate_external_receipt", accounting_status="DUPLICATE_SCOPE")
                else:
                    previous.update(resource_additive=False, action_total_authority=False,
                                    accounting_status="CONFLICTING_SCOPE")
                    row.update(record_type="conflicting_external_receipt", accounting_status="CONFLICTING_SCOPE")
                    if scope not in unresolved:
                        unresolved.append(scope)
                    _issue(issues, "CONFLICTING_EXTERNAL_SCOPE", source, source_line=number, scope=scope)
            else:
                seen_scopes[scope] = (row, dict(record))
            rows.append(row)

    authority = [row for row in rows if row["action_total_authority"]]
    live = [row["job_id"] for row in authority if row["live_checkpoint"]]
    resource_totals = {key: _resource_summary(rows, key, unresolved, live) for key in _RESOURCES}
    action_totals = {field: _action_summary(authority, field) for field in COUNTER_FIELDS}
    explicit = [row["exclusive_operator_vectors_recorded"] for row in authority
                if row["exclusive_operator_vectors_recorded"] != NOT_MEASURED]
    action_totals["exclusive_F_Fstar_L_Lstar"] = dict(
        recorded_sum=sum(explicit) if explicit else NOT_MEASURED,
        definition="recorded F + F* + L + L* vectors only; no generic Maxwell aggregate or full solver RHS added",
        explicit_record_count=len(explicit), unrecorded_record_count=len(authority)-len(explicit))
    action_totals["Maxwell_matvec_rhs_aggregate"]["included_in_exclusive_vector_sum"] = False
    action_totals["span_counter_totals_added_to_receipt_totals"] = False
    failure_rows = [dict(job_id=row["job_id"], scope=row["scope"], event=row["event"],
                         status=row["status"], source=row["source"], source_line=row["source_line"],
                         expected_unsafe_core=row["expected_unsafe_core"], error_type=row["error_type"])
                    for row in rows if row["status"] in ("FAILED", "TIMEOUT", "CANCELLED", "BUDGET_REFUSED")]
    cache_rows = [dict(job_id=row["job_id"], event=row["event"], source=row["source"],
                       source_line=row["source_line"], cache_hits=json.loads(row["cache_hits_json"]))
                  for row in rows if row["cache_hits_json"] not in (NOT_MEASURED, "{}")]
    return dict(
        schema="a22.cost_summary.v1", campaign="A22",
        status="ACCOUNTING_ISSUES" if issues or unresolved else "RECORDED_ONLY" if rows else "NO_RECORDED_A22_COSTS",
        rows=rows, row_count=len(rows), source_files=sorted(set(sources)),
        authoritative_record_count=len(authority), live_jobs=live,
        resource_totals=resource_totals, action_accounting=action_totals,
        authoritative_records=[dict(row) for row in authority],
        failed_records=failure_rows, cache_hit_records=cache_rows,
        excluded_records=excluded, issues=issues, unresolved_records=unresolved,
        policy={
            "resource_authority": "one final A22 job receipt or live checkpoint per job plus unique external scopes",
            "spans_are_additional_resource_charges": False,
            "CPU_and_GPU_resources_are_added_together": False,
            "wall_sum_definition": "sum of distinct recorded inclusive charges; not parallel campaign elapsed or deployment latency",
            "generic_Maxwell_rhs_added_to_F_Fstar_L_Lstar": False,
            "counter_aliases_are_summed": False,
            "missing_numeric_fields": NOT_MEASURED,
            "external_receipt_references_followed": False,
            "mirrored_global_ledgers_read": False,
            "old_A20_A21_records_included": False,
            "CPU_contains_recorded_conservative_allowances": "consult each original measurement/status field",
            "A0_A1_A2_separate_deployment_costs": NOT_MEASURED,
            "scientific_statistics_and_gate_decisions": "NOT_ASSESSED_BY_COST_SUMMARY",
        })


def _atomic(path, writer):
    temporary = None
    try:
        with NamedTemporaryFile(mode="w", encoding="utf-8", newline="", dir=path.parent,
                                prefix="." + path.name + ".", delete=False) as stream:
            temporary = Path(stream.name)
            writer(stream)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def export_cost_csv(root):
    """Explicitly export the ledger CSV and ACTION_ACCOUNTING JSON.

    This is called only by the metered parent.  The summary reads accounting
    once; it never writes the authoritative input receipts or global ledger.
    """
    root = Path(root).resolve()
    summary = summarize_costs(root)
    directory = root / "results/a22"
    if not _within(root, directory):
        raise ValueError("COST_SUMMARY_OUTPUT_OUTSIDE_ROOT")
    directory.mkdir(parents=True, exist_ok=True)
    csv_path = directory / "cost_ledger.csv"
    json_path = directory / "ACTION_ACCOUNTING.json"
    for path in (csv_path, json_path):
        if not _within(root, path):
            raise ValueError("COST_SUMMARY_OUTPUT_OUTSIDE_ROOT")
    def write_csv(stream):
        writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(summary["rows"])
    _atomic(csv_path, write_csv)
    accounting = {key: value for key, value in summary.items() if key != "rows"}
    accounting["ledger_csv"] = "results/a22/cost_ledger.csv"
    accounting["ledger_row_count"] = len(summary["rows"])
    def write_accounting(stream):
        json.dump(accounting, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
    _atomic(json_path, write_accounting)
    summary["outputs"] = dict(cost_csv=str(csv_path), action_accounting_json=str(json_path))
    return summary
