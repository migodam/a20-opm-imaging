"""A22 file-backed reports and static plots; scientific decisions stay external.

The public entry point is ``generate_reports(root, gate_path=None,
output_dir=None, *, make_plots=True, evidence=None)``.  Importing this module
does not read data, run a solver, generate a plot, or write a file.  The parent
must call it inside its CPU/wall accounting interval.

Inputs are restricted to ``results/a22``.  In particular, the cloned A21
``GATE_DECISION.json`` and cost ledger at repository root are never inputs.
Empty, missing, constant, and non-finite data stay explicitly unavailable;
no zero-valued measurements or gate passes are supplied as substitutes.
"""
from __future__ import annotations

import csv
import json
import math
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median
from typing import Any, Mapping


EXPECTED_SCENES = ("2001", "2003", "2014", "2009")
EXPECTED_CONFIG = {"material_model_k": 32, "current_rank_cap": 32, "degree_cap": 1}
METHODS = ("A0", "A1", "A2", "A3")
SCOPES = ("deployable", "oracle_only", "unclassified")
ALIASES = {
    "scene_id": ("scene_id", "parent_id", "object_id", "scene"),
    "direction_id": ("direction_id", "direction", "probe_id"),
    "method": ("method", "diagnostic", "arm", "algorithm"),
    "amplitude": ("amplitude", "perturbation_amplitude", "delta", "step_size"),
    "noise_level": ("noise_level", "noise_fraction", "noise", "sigma"),
    "noise_draw": ("noise_draw", "noise_seed", "realization", "draw"),
    "intervention": ("intervention", "perturbation_type", "condition"),
    "true_error": ("true_error", "true_coefficient_error", "coefficient_error", "recovery_error"),
    "relative_true_error": ("relative_true_error", "relative_coefficient_error", "relative_recovery_error"),
    "physics_projected_error": ("physics_projected_error", "projected_physics_error", "physics_error", "physics_abs_error", "phys_projected_error", "vp_error", "error_phys"),
    "complement_projected_error": ("complement_projected_error", "projected_complement_error", "complement_error", "complement_abs_error", "remaining_abs_error", "rem_projected_error", "prior_error", "vn_error", "error_rem"),
    "physics_per_coordinate_error": ("physics_per_coordinate_error", "physics_per_dimension_error", "physics_normalized_error", "vp_per_coordinate_error"),
    "complement_per_coordinate_error": ("complement_per_coordinate_error", "complement_per_dimension_error", "complement_normalized_error", "vn_per_coordinate_error"),
    "physics_relative_error": ("physics_relative_error", "relative_physics_error", "vp_relative_error"),
    "complement_relative_error": ("complement_relative_error", "relative_complement_error", "vn_relative_error"),
    "retained_truth_energy": ("retained_truth_energy", "relative_retained_truth_energy", "physics_truth_energy_fraction"),
    "actual_rank": ("actual_rank", "current_rank", "q_rank", "rank", "Q_rank"),
    "physics_rank": ("physics_rank", "r", "rank_phys", "vp_rank"),
    "operator_actions": ("operator_actions", "operator_action_count", "operator_rhs", "Maxwell_matvec_rhs", "online_Maxwell_vector_actions"),
    "wall_seconds": ("total_wall_seconds", "total_time", "total_wall_time", "wall_total_seconds", "wall_seconds", "wall_time"),
    "process_cpu_seconds": ("process_cpu_seconds", "cpu_seconds", "cpu_time"),
    "feature_origin": ("feature_origin", "feature_source", "feature_provenance"),
    "label_origin": ("label_origin", "truth_origin", "label_source", "truth_source"),
    "anchor_provenance": ("anchor_provenance", "anchor_origin", "anchor_type", "anchor_kind"),
    "evidence_scope": ("evidence_scope", "deployment_scope", "feature_scope", "scope"),
    "historical_exposure": ("historical_exposure", "historical_exposed", "historically_exposed", "dataset_exposure", "data_exposure"),
    "status": ("status", "run_status", "outcome"),
}
for _method in METHODS:
    ALIASES["pred_" + _method] = (
        "pred_" + _method, "prediction_" + _method,
        _method + "_prediction", _method + "_predicted_error",
        "predicted_error_" + _method, _method + "_prediction_error",
        "pred_" + _method.lower(), _method.lower() + "_predicted_error",
    )

SCHEMA = {
    "schema": "a22.reporting.input.v1",
    "direction_metrics": {
        "row_unit": "scene/direction/amplitude/noise_draw/noise_level/intervention",
        "canonical_columns": [
            "scene_id", "direction_id", "amplitude", "noise_draw", "noise_level",
            "intervention", "true_error", "relative_true_error", "pred_A0",
            "pred_A1", "pred_A2", "pred_A3", "alpha", "beta", "gamma",
            "attribution", "profile_g", "actual_rank", "certificate_type",
            "feature_origin", "label_origin", "truth_origin", "anchor_provenance",
            "evidence_scope", "historical_exposure", "status",
        ],
        "prediction_semantics": "pred_A0..pred_A3 predict coefficient error; they are not residuals of that prediction",
    },
    "split_metrics": {
        "canonical_columns": ["scene_id", "method", "physics_rank", "actual_rank",
            "physics_projected_error", "complement_projected_error",
            "physics_per_coordinate_error", "complement_per_coordinate_error",
            "physics_relative_error", "complement_relative_error", "retained_truth_energy",
            "feature_origin", "label_origin", "anchor_provenance", "evidence_scope",
            "historical_exposure", "certificate_type", "status"],
    },
    "scene_metrics": {
        "canonical_columns": ["scene_id", "method", "family", "split", "anchor_provenance",
            "feature_origin", "label_origin", "evidence_scope", "historical_exposure",
            "full_material_error", "full_wave_discrepancy", "support_iou", "location_error",
            "protected_drift", "success", "first_hit_time", "total_wall_seconds", "status"],
    },
    "cost_ledger": {
        "canonical_columns": ["scene_id", "method", "stage", "operation", "actual_rank",
            "operator_actions", "forward_RHS", "adjoint_RHS", "Q_builds", "outer_iterations",
            "line_search_trials", "rejected_steps", "wall_seconds", "wall_scope",
            "process_cpu_seconds", "temperature", "status"],
        "wall_rule": "nested span walls are never summed or presented as end-to-end time",
    },
    "aliases": ALIASES,
    "missing_rule": "unavailable metric -> NOT_RUN or UNDEFINED, never an invented zero",
    "gate_source": "parent-supplied results/a22/GATE_DECISION.json only",
}


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if hasattr(value, "item"):
        return _plain(value.item())
    return value


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_plain(value), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _field(row: Mapping[str, Any], name: str, default: Any = None) -> Any:
    folded = {str(k).casefold(): v for k, v in row.items()}
    for key in ALIASES.get(name, (name,)):
        if key.casefold() in folded:
            value = folded[key.casefold()]
            if value is not None and str(value).strip() != "":
                return value
    return default


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _num(row: Mapping[str, Any], name: str) -> float | None:
    return _number(_field(row, name))


def _truthy(value: Any) -> bool | None:
    text = str(value).strip().casefold() if value is not None else ""
    if text in ("true", "yes", "1", "exposed", "historically_exposed_feasibility", "historically_exposed"):
        return True
    if text in ("false", "no", "0", "unexposed"):
        return False
    return None


def _scope(row: Mapping[str, Any]) -> str:
    explicit = str(_field(row, "evidence_scope", "")).casefold()
    anchor = str(_field(row, "anchor_provenance", "")).casefold()
    origin = str(_field(row, "feature_origin", "")).casefold()
    if any(token in explicit + " " + anchor for token in ("oracle", "late_gn", "late gn", "truth_near", "truth-near", "near_truth")):
        return "oracle_only"
    if any(token in origin for token in ("full_j", "full_h", "truth_current", "s_f", "e_f", "jf=", "hf=")):
        return "oracle_only"
    if explicit in ("deployable", "online", "deployment", "deployable_maxwell"):
        return "deployable"
    if _truthy(row.get("deployable_features", row.get("deployable"))) is True:
        return "deployable"
    if origin and any(token in anchor for token in ("known_background", "known background", "actual_background", "bp", "eba")):
        return "deployable"
    return "unclassified"


def _read_table(path: Path) -> dict[str, Any]:
    result = {"path": str(path), "status": "NOT_RUN", "columns": [], "rows": [], "error": None}
    if not path.is_file():
        result["error"] = "file missing"
        return result
    try:
        if path.suffix.casefold() == ".jsonl":
            rows = []
            with path.open(encoding="utf-8") as handle:
                for line in handle:
                    if line.strip():
                        value = json.loads(line)
                        if not isinstance(value, dict):
                            raise ValueError("cost JSONL row is not an object")
                        # Keep original fields and expose named counter fields, without
                        # manufacturing a total or summing nested timing spans.
                        flattened = dict(value)
                        for key in ("counts", "counters"):
                            if isinstance(value.get(key), dict):
                                for name, number in value[key].items():
                                    flattened.setdefault(name, number)
                        rows.append(flattened)
            columns = sorted({str(k) for row in rows for k in row})
        else:
            with path.open(newline="", encoding="utf-8-sig") as handle:
                reader = csv.DictReader(handle)
                columns = list(reader.fieldnames or [])
                rows = [dict(row) for row in reader]
            if not columns:
                raise ValueError("CSV header missing")
        result.update(status="RECORDED" if rows else "NOT_RUN", columns=columns, rows=rows)
        if not rows:
            result["error"] = "file has no metric rows"
    except (OSError, ValueError, csv.Error, json.JSONDecodeError) as exc:
        result.update(status="UNREADABLE", error=str(exc), rows=[])
    return result


def _read_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not path.is_file():
        return None, "file missing"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("JSON document is not an object")
        return value, None
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return None, str(exc)


def _gate_name(value: Any) -> str:
    text = str(value).strip().upper().replace(" ", "_").replace("-", "_")
    return text[5:] if text.startswith("GATE_") else text


def _gate_rows(document: Mapping[str, Any] | None) -> list[dict[str, str]]:
    rows = []
    source = document.get("gates", document.get("gate_decisions", document)) if document else {}
    if isinstance(source, list):
        source = {_gate_name(x.get("gate", x.get("name", ""))): x for x in source if isinstance(x, dict)}
    if not isinstance(source, dict):
        source = {}
    normalized = {_gate_name(k): v for k, v in source.items()}
    for gate in ("A", "B", "C", "D", "E", "T"):
        entry = normalized.get(gate)
        if isinstance(entry, dict):
            status = str(entry.get("status", entry.get("decision", "NOT_RUN")))
            reason = entry.get("reason", entry.get("rationale", entry.get("missing_evidence", "")))
            action = entry.get("next_action", entry.get("required_evidence", ""))
        elif entry is not None:
            status, reason, action = str(entry), "parent-supplied status", ""
        else:
            status = "NOT_RUN"
            reason = "No parent decision supplied; report does not evaluate this gate."
            action = "Parent must review the required evidence and provide the decision."
        rows.append({"gate": gate, "status": status or "NOT_RUN", "reason": _short(reason), "next_action": _short(action)})
    return rows


def _stage_status(document: Mapping[str, Any] | None, name: str, gates: list[dict[str, str]]) -> tuple[str, str]:
    stages = document.get("stages", document.get("stage_status", {})) if document else {}
    if isinstance(stages, dict):
        for key in (name, "stage_" + name, "Stage " + name, "Stage_" + name):
            if key in stages:
                entry = stages[key]
                if isinstance(entry, dict):
                    return str(entry.get("status", "NOT_RUN")), _short(entry.get("reason", entry.get("blocked_by", "")))
                return str(entry), "parent-supplied stage status"
    if name in ("B", "C"):
        required = ("A", "B") if name == "B" else ("A", "B", "C")
        unmet = [row["gate"] + "=" + row["status"] for row in gates if row["gate"] in required and row["status"].upper() != "PASS"]
        if unmet:
            return "BLOCKED", "Execution prerequisite requires strict PASS: " + ", ".join(unmet)
    return "NOT_RUN", "No parent stage execution receipt supplied."


def _short(value: Any, limit: int = 1800) -> str:
    text = json.dumps(_plain(value), ensure_ascii=False) if isinstance(value, (dict, list, tuple)) else str(value)
    return text if len(text) <= limit else text[:limit] + " … [full value retained in source JSON]"


def _md(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", "<br>")


def _table(headers: list[str], rows: list[list[Any]]) -> str:
    return "\n".join(["| " + " | ".join(map(_md, headers)) + " |", "| " + " | ".join("---" for _ in headers) + " |"] + ["| " + " | ".join(map(_md, row)) + " |" for row in rows])


def _ranks(values: list[float]) -> list[float]:
    result = [0.] * len(values)
    order = sorted(range(len(values)), key=values.__getitem__)
    start = 0
    while start < len(order):
        stop = start + 1
        while stop < len(order) and values[order[stop]] == values[order[start]]:
            stop += 1
        rank = (start + stop - 1) / 2. + 1.
        for index in order[start:stop]:
            result[index] = rank
        start = stop
    return result


def _spearman(x: list[float], y: list[float]) -> float | None:
    if len(x) < 3 or len(x) != len(y):
        return None
    rx, ry = _ranks(x), _ranks(y)
    mx, my = mean(rx), mean(ry)
    numerator = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    denominator = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return max(-1., min(1., numerator / denominator)) if denominator > 0 else None


def _prediction_stats(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups = defaultdict(list)
    for row in rows:
        groups[(str(_field(row, "scene_id", "MISSING_SCENE_ID")), _scope(row))].append(row)
    output = []
    for (scene, scope), members in sorted(groups.items()):
        for method in METHODS:
            pairs = [(_num(row, "true_error"), _num(row, "pred_" + method)) for row in members]
            pairs = [(truth, pred) for truth, pred in pairs if truth is not None and pred is not None]
            truth = [a for a, _ in pairs]
            prediction = [b for _, b in pairs]
            rho = _spearman(truth, prediction)
            output.append({"scene_id": scene, "evidence_scope": scope, "method": method,
                "rows_with_pairs": len(pairs), "rows_in_scene_scope": len(members),
                "spearman": rho, "MAE": mean(abs(a - b) for a, b in pairs) if pairs else None,
                "spearman_status": "RECORDED_DESCRIPTIVE" if rho is not None else "UNDEFINED",
                "sampling_unit": "scene; directions/amplitudes/noise draws are correlated observations",
                "scope_note": "pooled within this scene and evidence scope; no p-value or independent-draw CI"})
    return output


def _write_csv(path: Path, rows: list[Mapping[str, Any]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: "" if row.get(key) is None else row.get(key) for key in columns})


def _with_scene_metadata(rows: list[dict[str, Any]], scene_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_scene = defaultdict(list)
    for row in scene_rows:
        by_scene[str(_field(row, "scene_id", ""))].append(row)
    output = []
    names = ("feature_origin", "label_origin", "anchor_provenance", "historical_exposure", "evidence_scope")
    for row in rows:
        copy = dict(row)
        candidates = by_scene.get(str(_field(row, "scene_id", "")), [])
        for name in names:
            if _field(copy, name) is not None:
                continue
            values = {_short(_field(candidate, name)) for candidate in candidates if _field(candidate, name) is not None}
            if len(values) == 1:
                copy[name] = next(iter(values))
        output.append(copy)
    return output


def _blocked(ax: Any, title: str, reason: str, status: str = "NOT_RUN") -> None:
    ax.set_axis_off()
    ax.set_title(title)
    ax.text(.5, .55, status, ha="center", va="center", transform=ax.transAxes, fontsize=15, fontweight="bold")
    ax.text(.5, .34, reason, ha="center", va="center", transform=ax.transAxes, fontsize=9, wrap=True)


def _plots(root: Path, tables: Mapping[str, Any], stats: list[dict[str, Any]], stages: Mapping[str, Any], figure_dir: Path) -> list[dict[str, Any]]:
    import matplotlib
    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as plt

    figure_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    markers = {"deployable": "o", "oracle_only": "x", "unclassified": "^"}

    def save(fig: Any, name: str, sources: list[str], status: str, caption: str) -> None:
        fig.text(.5, .015, caption, ha="center", va="bottom", fontsize=8, wrap=True)
        fig.tight_layout(rect=(0, .09, 1, 1))
        png, svg = figure_dir / (name + ".png"), figure_dir / (name + ".svg")
        fig.savefig(png, dpi=160, bbox_inches="tight")
        fig.savefig(svg, bbox_inches="tight")
        plt.close(fig)
        manifest.append({"name": name, "png": str(png), "svg": str(svg), "status": status, "sources": sources, "caption": caption})

    directions = tables["direction_metrics"]["rows"]
    fig, axes = plt.subplots(2, 2, figsize=(10, 8))
    total_pairs = 0
    for ax, method in zip(axes.ravel(), METHODS):
        count = 0
        for scope in SCOPES:
            pairs = [(_num(row, "true_error"), _num(row, "pred_" + method)) for row in directions if _scope(row) == scope]
            pairs = [(a, b) for a, b in pairs if a is not None and b is not None]
            if pairs:
                ax.scatter([a for a, _ in pairs], [b for _, b in pairs], s=16, alpha=.65, marker=markers[scope], label=scope)
                count += len(pairs)
        total_pairs += count
        if count:
            ax.set(title=method + f" ({count} paired rows)", xlabel="Actual coefficient error", ylabel="Predicted coefficient error")
            ax.legend(fontsize=8)
            ax.grid(alpha=.2)
        else:
            _blocked(ax, method, "Actual/predicted coefficient-error pairs unavailable")
    save(fig, "prediction_vs_coefficient_error", [tables["direction_metrics"]["path"]], "RECORDED" if total_pairs else "NOT_RUN", "Raw error pairs; oracle-only and unclassified evidence remain separate. Repeated rows are not independent scenes.")

    fig, axes = plt.subplots(1, 3, figsize=(14, 4.6), squeeze=False)
    valid = 0
    for ax, scope in zip(axes.ravel(), SCOPES):
        members = [row for row in stats if row["evidence_scope"] == scope and row["spearman"] is not None]
        scenes = sorted({row["scene_id"] for row in members})
        if not members:
            _blocked(ax, scope, "Spearman undefined: missing pairs, <3 rows, or constant values")
            continue
        for method in METHODS:
            chosen = [row for row in members if row["method"] == method]
            if chosen:
                ax.scatter([scenes.index(row["scene_id"]) for row in chosen], [row["spearman"] for row in chosen], label=method)
        ax.set_xticks(range(len(scenes)), scenes, rotation=35, ha="right")
        ax.set(title=scope, ylabel="Within-scene Spearman", ylim=(-1.05, 1.05))
        ax.axhline(0, color=".6", linewidth=.7)
        ax.legend(fontsize=8)
        valid += len(members)
    save(fig, "per_scene_spearman", [tables["direction_metrics"]["path"]], "RECORDED_DESCRIPTIVE" if valid else "NOT_RUN", "Correlation is descriptive and pooled within each scene/scope. No p-values, scene-independent noise-draw counts, or invented confidence intervals.")

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.6))
    valid = 0
    for ax, field in zip(axes, ("amplitude", "noise_level")):
        groups = defaultdict(list)
        for row in directions:
            x, y = _num(row, field), _num(row, "true_error")
            if x is not None and y is not None:
                groups[(str(_field(row, "scene_id", "MISSING_SCENE_ID")), _scope(row))].append((x, y))
        if not groups:
            _blocked(ax, "Error versus " + field, "Finite actual-error and condition pairs unavailable")
            continue
        for (scene, scope), pairs in sorted(groups.items()):
            ax.scatter([a for a, _ in pairs], [b for _, b in pairs], s=14, alpha=.55, marker=markers[scope], label=scene + "/" + scope)
            valid += len(pairs)
        ax.set(xlabel=field.replace("_", " "), ylabel="Actual coefficient error")
        ax.legend(fontsize=6)
        ax.grid(alpha=.2)
    save(fig, "error_vs_amplitude_noise", [tables["direction_metrics"]["path"]], "RECORDED" if valid else "NOT_RUN", "Raw finite-amplitude/noise observations; failures with missing errors are retained in the source ledger, not converted to zero.")

    splits = tables["split_metrics"]["rows"]
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    valid = 0
    for ax, suffix, label in zip(axes, ("projected_error", "per_coordinate_error", "relative_error"), ("Absolute projected error", "Per-coordinate error", "Relative projected error")):
        available = []
        for index, row in enumerate(splits):
            phys, rem = _num(row, "physics_" + suffix), _num(row, "complement_" + suffix)
            if phys is not None or rem is not None:
                available.append((index, row, phys, rem))
        if not available:
            _blocked(ax, label, "Requested normalization is absent; no denominator is inferred")
            continue
        for branch, position, color in (("physics", 2, "#2464a3"), ("complement", 3, "#b66c19")):
            values = [(j, entry[position]) for j, entry in enumerate(available) if entry[position] is not None]
            if values:
                ax.scatter([j for j, _ in values], [value for _, value in values], color=color, label=branch)
                valid += len(values)
        labels = [str(_field(row, "scene_id", "?")) + "/" + str(_field(row, "method", "?")) + "/" + _scope(row) for _, row, _, _ in available]
        ax.set_xticks(range(len(labels)), labels, rotation=80, ha="right", fontsize=6)
        ax.set_title(label)
        ax.legend(fontsize=8)
        ax.grid(alpha=.2)
    save(fig, "physics_complement_projected_errors", [tables["split_metrics"]["path"]], "RECORDED" if valid else "NOT_RUN", "Saved projected errors only. Rank, retained truth energy, W-external error, and certificate credibility must be reviewed separately; no separation gate is inferred.")

    costs = [row for table in tables["cost_ledgers"] for row in table["rows"]]
    if not costs:
        costs = tables["scene_metrics"]["rows"]
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.8))
    valid = 0
    for ax, field, label in zip(axes, ("actual_rank", "operator_actions", "wall_seconds"), ("Actual current/Q rank", "Recorded operator actions/RHS", "Recorded wall seconds")):
        values = [(index, _num(row, field)) for index, row in enumerate(costs)]
        values = [(index, value) for index, value in values if value is not None]
        if not values:
            _blocked(ax, label, "Named cost/rank field unavailable; no implicit zero or aggregate")
            continue
        ax.scatter([index for index, _ in values], [value for _, value in values], s=16)
        ax.set(xlabel="Source ledger row index", ylabel=label)
        ax.grid(alpha=.2)
        valid += len(values)
    sources = [table["path"] for table in tables["cost_ledgers"]] or [tables["scene_metrics"]["path"]]
    save(fig, "rank_operator_wall_cost", sources, "RECORDED" if valid else "NOT_RUN", "Recorded rows are not summed. Nested span wall, cold/warm, and end-to-end time remain distinct; this figure establishes no speedup.")

    for stage in ("B", "C"):
        status, reason = stages[stage]
        if status.upper() not in ("RUN", "RUNNING", "COMPLETE", "COMPLETED", "PASS", "PARTIAL"):
            fig, ax = plt.subplots(figsize=(8, 3.2))
            _blocked(ax, "Stage " + stage, reason, status)
            save(fig, "stage_" + stage.lower() + "_status", [], status, "Status card only; no synthetic curve, image, learned output, or zero-valued measurement.")
    return manifest


def generate_reports(root: str | Path | None = None, gate_path: str | Path | None = None,
                     output_dir: str | Path | None = None, *, make_plots: bool = True,
                     evidence: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Render actual A22 CSV/JSON evidence, without changing gate decisions.

    Returns paths, source coverage and missing/undefined counts.  CPU timing
    belongs to the calling parent's accounting interval; no physics is run.
    ``evidence`` may add supplied theory/check/config metadata, never a gate
    pass inferred from a metric.  Missing input files are valid report inputs.
    """
    root = Path(root).resolve() if root is not None else Path(__file__).resolve().parents[2]
    out = Path(output_dir).resolve() if output_dir is not None else root
    a22 = root / "results" / "a22"
    screen = a22 / "screening"
    gate_path = Path(gate_path) if gate_path is not None else a22 / "GATE_DECISION.json"
    if not gate_path.is_absolute():
        gate_path = root / gate_path
    # This guard prevents inherited A20/A21 decisions from the cloned checkout
    # from being substituted for the new parent decision.
    if not gate_path.resolve().is_relative_to(a22.resolve()):
        raise ValueError("A22_GATE_INPUT_MUST_BE_INSIDE_RESULTS_A22")
    document, gate_error = _read_json(gate_path)
    gates = _gate_rows(document)
    stages = {name: _stage_status(document, name, gates) for name in ("A", "B", "C")}
    supplied = dict(evidence or {})
    for name in ("evidence", "metrics", "config", "frozen_config", "thresholds"):
        if document and name in document:
            supplied.setdefault(name, document[name])
    config_path = root / "configs" / "a22.json"
    config, config_error = _read_json(config_path)
    if config is not None:
        supplied.setdefault("configuration", config)

    def locate(name: str) -> Path:
        first, second = screen / (name + ".csv"), a22 / (name + ".csv")
        return first if first.is_file() or not second.is_file() else second

    tables = {name: _read_table(locate(name)) for name in ("direction_metrics", "split_metrics", "scene_metrics")}
    manifest_path = a22 / "scene_manifest.csv"
    if not manifest_path.is_file() and (screen / "scene_manifest.csv").is_file():
        manifest_path = screen / "scene_manifest.csv"
    tables["scene_manifest"] = _read_table(manifest_path)
    scene_metadata = tables["scene_manifest"]["rows"] + tables["scene_metrics"]["rows"]
    for name in ("direction_metrics", "split_metrics"):
        tables[name]["rows"] = _with_scene_metadata(tables[name]["rows"], scene_metadata)
    cost_paths = sorted(path for path in a22.rglob("*")
                        if path.is_file() and path.suffix.casefold() in (".csv", ".jsonl")
                        and any(token in path.name.casefold() for token in ("cost_ledger", "costledger", "costs", "cpu_ledger"))
                        and "reporting" not in path.relative_to(a22).parts) if a22.is_dir() else []
    tables["cost_ledgers"] = [_read_table(path) for path in cost_paths]
    if not cost_paths:
        tables["cost_ledgers"] = [_read_table(a22 / "cost_ledger.csv")]

    report_dir = a22 / "reporting"
    raw_dir = report_dir / "rawdata"
    raw_dir.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)
    copied = []
    all_tables = [(name, tables[name]) for name in ("direction_metrics", "split_metrics", "scene_metrics", "scene_manifest")]
    all_tables += [("cost_ledger_" + str(index), table) for index, table in enumerate(tables["cost_ledgers"])]
    for name, table in all_tables:
        path = Path(table["path"])
        if path.is_file():
            target = raw_dir / (name + path.suffix)
            shutil.copyfile(path, target)
            copied.append({"source": str(path), "copy": str(target), "source_status": table["status"]})
    if gate_path.is_file():
        shutil.copyfile(gate_path, raw_dir / "GATE_DECISION.parent.json")
    _write_json(report_dir / "EXPECTED_METRICS_SCHEMA.json", SCHEMA)
    _write_json(report_dir / "SUPPLIED_EVIDENCE.json", supplied)

    # Make the plotting values inspectable as CSV even when cost receipts use
    # JSONL. Blank means absent/non-finite; every source row retains its index.
    cost_plot_rows = []
    for table in tables["cost_ledgers"]:
        for index, row in enumerate(table["rows"]):
            cost_plot_rows.append({"source": table["path"], "source_row": index,
                "scene_id": _field(row, "scene_id"), "method": _field(row, "method"),
                "actual_rank": _num(row, "actual_rank"),
                "operator_actions": _num(row, "operator_actions"),
                "wall_seconds": _num(row, "wall_seconds"),
                "process_cpu_seconds": _num(row, "process_cpu_seconds"),
                "wall_scope": row.get("wall_scope", "UNDECLARED"),
                "temperature": row.get("temperature", "UNDECLARED"),
                "status": _field(row, "status", "UNDECLARED")})
    _write_csv(raw_dir / "cost_plot_rows.csv", cost_plot_rows,
               ["source", "source_row", "scene_id", "method", "actual_rank", "operator_actions",
                "wall_seconds", "process_cpu_seconds", "wall_scope", "temperature", "status"])

    stats = _prediction_stats(tables["direction_metrics"]["rows"])
    stat_columns = ["scene_id", "evidence_scope", "method", "rows_with_pairs", "rows_in_scene_scope", "spearman", "MAE", "spearman_status", "sampling_unit", "scope_note"]
    _write_csv(raw_dir / "spearman_mae_by_scene.csv", stats, stat_columns)
    # These derived statistics describe observations; there is deliberately no
    # threshold comparison, gate reducer, bootstrap, p-value or route selection.
    summary_stats = []
    for scope in SCOPES:
        for method in METHODS:
            selected = [row for row in stats if row["evidence_scope"] == scope and row["method"] == method]
            correlations = [row["spearman"] for row in selected if row["spearman"] is not None]
            errors = [row["MAE"] for row in selected if row["MAE"] is not None]
            summary_stats.append({"evidence_scope": scope, "method": method,
                "scenes_with_defined_spearman": len(correlations),
                "median_scene_spearman": median(correlations) if correlations else None,
                "scenes_with_defined_MAE": len(errors),
                "equal_scene_mean_MAE": mean(errors) if errors else None,
                "gate_interpretation": "PARENT_ONLY"})
    _write_csv(raw_dir / "prediction_summary_descriptive.csv", summary_stats,
               ["evidence_scope", "method", "scenes_with_defined_spearman", "median_scene_spearman", "scenes_with_defined_MAE", "equal_scene_mean_MAE", "gate_interpretation"])

    figures, plot_error = [], None
    if make_plots:
        try:
            figures = _plots(root, tables, stats, stages, root / "figures" / "a22")
        except (ImportError, OSError, ValueError, RuntimeError) as exc:
            plot_error = str(exc)
    else:
        plot_error = "NOT_RUN: plot generation disabled by caller"
    _write_json(report_dir / "FIGURE_MANIFEST.json", {"schema": "a22.static_figures.v1", "figures": figures, "error": plot_error, "rawdata": copied})

    coverage = [[name, table["status"], len(table["rows"]), table["path"], table["error"] or ""] for name, table in all_tables]
    direction_rows = tables["direction_metrics"]["rows"]
    scopes = Counter(_scope(row) for row in direction_rows)
    scenes = sorted({str(_field(row, "scene_id", "MISSING_SCENE_ID")) for row in direction_rows})
    exposure = Counter(str(_field(row, "historical_exposure", "UNDECLARED")) for row in direction_rows)
    origins = Counter((str(_field(row, "feature_origin", "UNDECLARED")), str(_field(row, "label_origin", "UNDECLARED"))) for row in direction_rows)
    certificate_counts = Counter(str(row.get("certificate_type", "UNDECLARED")) for row in direction_rows)
    observed_checks = []
    for path in sorted(a22.rglob("*.json")) if a22.is_dir() else []:
        if "reporting" in path.relative_to(a22).parts:
            continue
        filename = path.name.casefold()
        if any(token in filename for token in ("verification", "identity", "consistency", "health_check")):
            value, error = _read_json(path)
            observed_checks.append([str(path), str(value.get("status", value.get("result", "STATUS_UNDECLARED"))) if value else "UNREADABLE", error or "saved receipt; scope must follow its source"])

    gate_table = _table(["Gate", "Parent status", "Reason / missing evidence", "Next action"], [[row["gate"], row["status"], row["reason"], row["next_action"]] for row in gates])
    stage_table = _table(["Stage", "Recorded execution status / prerequisite block", "Reason"], [[name, *stages[name]] for name in ("A", "B", "C")])
    source_table = _table(["Source", "Availability", "Rows", "Path", "Missing/error"], coverage)
    prediction_table = _table(["Scope", "Method", "Scenes with defined correlation", "Median scene Spearman", "Equal-scene mean MAE"], [[row["evidence_scope"], row["method"], row["scenes_with_defined_spearman"], _format(row["median_scene_spearman"]), _format(row["equal_scene_mean_MAE"])] for row in summary_stats])
    boundary = (
        "Gate statuses are copied from the parent decision, never derived by this report. "
        "Missing evidence is NOT_RUN/UNDEFINED; report generation is not an experiment. "
        "Provided proofs, identity checks, actual Maxwell evaluation, oracle-only evidence and deployment evidence are distinct. "
        "Historical exposure is preserved; a historical validation label is not a new blind holdout. "
        "Directions, amplitudes and noise draws from one scene are correlated observations. "
        "No scene-cluster confidence interval is invented.\n"
    )
    provenance = _table(["Feature origin", "Label/truth origin", "Rows"], [[feature, label, count] for (feature, label), count in sorted(origins.items())]) if origins else "NOT_RUN: feature/label provenance rows unavailable."
    exposure_text = _table(["Recorded exposure flag", "Direction rows"], [[key, count] for key, count in sorted(exposure.items())]) if exposure else "NOT_RUN: exposure flags unavailable."
    check_table = _table(["Saved check receipt", "Recorded status", "Scope note"], observed_checks) if observed_checks else "NOT_RUN: no A22 identity/Maxwell consistency receipt found."
    evidence_text = _short(supplied, 14000) if supplied else "No parent-supplied evidence summary present."
    figure_text = _table(["Figure", "Evidence/status", "PNG", "SVG"], [[item["name"], item["status"], item["png"], item["svg"]] for item in figures]) if figures else "NOT_RUN: " + (plot_error or "no figure rendering requested")
    categories = _table(["Evidence category", "What this report can establish"], [
        ["Provided theorem/proof text", "Source package derivations are supplied; validity remains subject to parent scientific review. Their presence never closes an experimental gate."],
        ["Identity tests", "Saved A22 check receipts only; tiny algebra and real solver checks must retain their actual scope."],
        ["Actual Maxwell", "Only parent/source-declared full-wave evidence qualifies. Metric-row presence alone does not establish physical provenance."],
        ["Oracle-only", f"{scopes.get('oracle_only', 0)} classified direction rows; separately displayed and excluded from a deployment interpretation."],
        ["Deployable", f"{scopes.get('deployable', 0)} direction rows with declared deployable scope/provenance; parent checks legality and sufficiency."],
        ["Unclassified", f"{scopes.get('unclassified', 0)} direction rows; no deployment or Maxwell claim inferred."],
    ])
    common = f"{boundary}\nParent decision source: `{gate_path}`. Availability: {'RECORDED' if document is not None else 'NOT_RUN'}; {gate_error or 'no parse error'}.\n"
    documents = {
        "A22_IMPLEMENTATION_REPORT.md": f"# A22 implementation report\n\n{common}\n## Implemented reporting scope\n\nStatic CSV/JSON reporting, descriptive within-scene prediction statistics, and PNG/SVG plots. No solver, feature builder, truth simulator, optimizer or NN is invoked. Expected fixed settings: {EXPECTED_CONFIG}; expected screening IDs: {', '.join(EXPECTED_SCENES)}. Actual parent configuration is retained in `results/a22/reporting/SUPPLIED_EVIDENCE.json`.\n\n## Evidence separation\n\n{categories}\n\n## Source coverage\n\n{source_table}\n\n## Parent decisions and stage execution\n\n{gate_table}\n\n{stage_table}\n\n## Remaining implementation/evidence limitations\n\nAbsent metrics, feature/label provenance, scene-cluster intervals, physical check receipts or stage execution receipts remain absent. Existing A21 reports/cost ledgers are excluded from the A22 source search. Full material error, W-external error and normalized projected error are never substituted for each other.\n",
        "A22_RESULTS_LEDGER.md": f"# A22 results ledger\n\n{common}\n## Raw source ledger\n\n{source_table}\n\nObserved direction scene IDs: {', '.join(scenes) if scenes else 'NOT_RUN'}. All metric rows and recorded failure/status fields are retained in raw copies.\n\n## Descriptive predictions\n\n{prediction_table}\n\nThese means weight scenes equally within each evidence scope. Correlation is undefined for fewer than three pairs or constant ranks. MAE comparison is descriptive; no incrementality win or gate pass is inferred.\n\n## Feature/label origin\n\n{provenance}\n\n## Historical exposure\n\n{exposure_text}\n\n## Certificate types\n\n{dict(certificate_counts) if certificate_counts else 'NOT_RUN'}\n\n## Saved checks\n\n{check_table}\n\n## Figure outputs\n\n{figure_text}\n",
        "A22_GATE_DECISION.md": f"# A22 parent gate decision\n\n{common}\n{gate_table}\n\n{stage_table}\n\n## Supplied evidence/configuration\n\n```json\n{evidence_text}\n```\n\nReport statistics do not change this decision. Suggested thresholds in the source package are preregistration candidates, not already-achieved measurements.\n",
        "STAGE_A_REPORT.md": f"# A22 Stage A report\n\n{common}\nStage A execution: {stages['A'][0]}. {stages['A'][1]}\n\n## Evidence inventory\n\n{categories}\n\n{source_table}\n\n## Recoverability observations\n\n{prediction_table}\n\n## Material split evidence\n\nSplit rows: {len(tables['split_metrics']['rows'])}; availability: {tables['split_metrics']['status']}. Raw projected errors, ranks, retained truth energy, eligibility and certificate fields remain in the source CSV. Absence of any required dimension/normalization is not repaired with a guessed denominator.\n\n## Health/identity checks\n\n{check_table}\n\n## Parent gate review\n\n{gate_table}\n\n## Stage B/C\n\n{stage_table}\n\nStage B/C status cards contain no fake images or measurements. A later actual execution receipt is required before either stage is described as run.\n",
        "GATE_REPORT.md": f"# A22 gate report\n\n{common}\n{gate_table}\n\n## Execution prerequisites\n\n{stage_table}\n\nMissing parent evidence/status remains NOT_RUN. Budget exhaustion alone is not a scientific counterexample. Oracle-only results cannot close deployable gates; material/current metrics and certificate credibility must remain declared. No diffusion or NN execution is authorized by this report.\n",
    }
    paths = []
    for name, text in documents.items():
        path = out / name
        path.write_text(text, encoding="utf-8")
        paths.append(str(path))
    result = {"schema": "a22.reporting.result.v1", "status": "REPORTS_WRITTEN",
        "gate_decisions_evaluated_by_reporter": False, "physics_executed": False,
        "report_paths": paths, "report_directory": str(report_dir), "rawdata_directory": str(raw_dir),
        "figure_count": len(figures), "figure_error": plot_error, "source_coverage": coverage,
        "gate_source": str(gate_path), "gate_source_error": gate_error,
        "stage_status": stages, "direction_scenes": scenes, "direction_scope_counts": dict(scopes),
        "prediction_rows": len(stats), "undefined_spearman_rows": sum(row["spearman"] is None for row in stats),
        "CPU_accounting": "Caller must meter the entire generate_reports invocation including source reads and figure writes."}
    _write_json(report_dir / "REPORT_MANIFEST.json", result)
    return result


def _format(value: Any) -> str:
    number = _number(value)
    return f"{number:.6g}" if number is not None else "UNDEFINED / NOT_RUN"


report = generate_reports
render_report = generate_reports
