"""Static R1 tables and scientific figures from supplied, already paid rows.

No NPZ, external input, online physics, teacher, or gate recomputation outside
the registered table functions is accessed.  The parent invokes this once with
its CostBook; check/span hooks separate the reporting groups.
"""
from __future__ import annotations

from contextlib import contextmanager
import csv
import json
import math
from pathlib import Path

from .gates import (METHODS, LEGAL_METHODS, action_fourtuple, anatomy_issues,
                    evaluate_anatomy, evaluate_closed_loop, evaluate_history,
                    get, method_id, method_rows, number, parent_id, settings, state_id)


def _plain(value):
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if hasattr(value, "tolist"):
        return _plain(value.tolist())
    if hasattr(value, "item"):
        return _plain(value.item())
    return value


def _json(path, value):
    path.write_text(json.dumps(_plain(value), ensure_ascii=False, allow_nan=False, indent=2)+"\n", encoding="utf-8")


def _csv(path, rows, required=()):
    rows = [_plain(r) for r in rows]
    fields = list(dict.fromkeys(list(required) + sorted({k for r in rows for k in r})))
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: json.dumps(v, ensure_ascii=False, separators=(",", ":"))
                             if isinstance(v, (dict, list)) else v for k, v in r.items()})


@contextmanager
def _group(book, label):
    if book is not None:
        book.check()
    if book is not None and hasattr(book, "span"):
        with book.span("r1_report_"+label):
            yield
    else:
        yield


def evidence_source(row):
    method = method_id(row)
    if method == "HISTORY":
        return "NOT_RUN_FROZEN_SNAPSHOT_HISTORY"
    if method in ("ORACLE-M", "PROTECTED-ORACLE", "PROTECTED-RANDOM"):
        return "OFFLINE_ORACLE_E_OR_MATCHED_DIAGNOSTIC_CONTROL"
    if method == "FIXED-DEEP":
        return "ONLINE_FIXED_BASELINE"
    if method in LEGAL_METHODS:
        return "ONLINE_LEGAL_PROPOSAL"
    if method == "FULL_GN":
        return "FULL_PHYSICS_REFERENCE_TRAJECTORY"
    return "NON_METHOD_OR_UNCLASSIFIED_BOOKKEEPING"


def annotate_rows(rows, config, phase="anatomy"):
    config = settings(config)
    out = []
    for row in rows:
        value = dict(row)
        value["evidence_source_class"] = evidence_source(row)
        value["oracle_target_E_source_class"] = "OFFLINE_DIAGNOSTIC_ONLY" if method_id(row) in (
            "ORACLE-M", "PROTECTED-ORACLE", "PROTECTED-RANDOM") else "NOT_USED"
        if method_id(row) == "HISTORY":
            value["reported_HISTORY_status"] = "NOT_RUN_NO_OWN_ACCEPTED_TRAJECTORY"
            value["gate_issue_classes"] = ["SNAPSHOT_HISTORY_IS_NOT_OWN_ONLINE_HISTORY"]
        elif phase == "anatomy" and row.get("record_kind") in (None, "method") and method_id(row) in METHODS:
            value["gate_issue_classes"] = anatomy_issues(row, config)
        elif phase != "anatomy":
            value["offline_H_diagnostic_status"] = get(row, "reference_status") or "NOT_RECORDED_SEPARATE_FROM_ONLINE_TRAJECTORY"
        out.append(value)
    return out


def rank_action_matching(rows, config):
    """Descriptive pairs use measured four-tuples, not nominal rank/action budgets.

    No bootstrapped significance, oracle ranking, proxy wall, or deployment
    claim is attached to these nearest comparisons.
    """
    config = settings(config)
    rows = method_rows(rows)
    output = []
    for state in ("early", "late"):
        for p in config.get("parents", (2001, 2005, 2003, 2007, 2013)):
            fixed = [r for r in rows if parent_id(r) == p and state_id(r, config) == state and method_id(r) == "FIXED-DEEP"]
            for name in LEGAL_METHODS:
                candidates = [r for r in rows if parent_id(r) == p and state_id(r, config) == state and method_id(r) == name]
                pair = {"parent_id": p, "state": state, "method": name, "control_method": "FIXED-DEEP",
                        "comparison_scope": "ONLINE_LEGAL_ACTUAL_FOURTUPLE_DESCRIPTIVE"}
                if len(fixed) != 1 or len(candidates) != 1:
                    pair["status"] = "MISSING_OR_DUPLICATE_PAIR"
                    output.append(pair)
                    continue
                a, b = candidates[0], fixed[0]
                ca, cb = action_fourtuple(a), action_fourtuple(b)
                pair.update(actual_rank=number(get(a, "actual_rank", "rank")),
                            control_actual_rank=number(get(b, "actual_rank", "rank")),
                            action_fourtuple=ca, control_action_fourtuple=cb,
                            method_issues=anatomy_issues(a, config), control_issues=anatomy_issues(b, config))
                if pair["method_issues"] or pair["control_issues"]:
                    pair["status"] = "INVALID_METHOD_OR_REFERENCE_PAIR"
                elif ca is None or cb is None:
                    pair["status"] = "MISSING_ACTUAL_FOURTUPLE"
                else:
                    gaps = [abs(x-y)/max(x, y) if max(x, y) > 0 else 0. for x, y in zip(ca, cb)]
                    pair["component_relative_gaps"] = gaps
                    pair["maximum_component_relative_gap"] = max(gaps)
                    pair["rank_absolute_difference"] = abs(pair["actual_rank"]-pair["control_actual_rank"])
                    pair["status"] = "ACTUAL_FOURTUPLE_WITHIN_TOLERANCE" if max(gaps) <= config["match_action_tolerance"] else "ACTUAL_FOURTUPLE_NOT_MATCHED"
                output.append(pair)
    for state in ("early", "late"):
        for p in config.get("parents", ()):
            eligible = [x for x in output if x["parent_id"] == p and x["state"] == state and "maximum_component_relative_gap" in x]
            if eligible:
                nearest = min(eligible, key=lambda x: (x["maximum_component_relative_gap"], x["method"]))
                for x in eligible:
                    x["nearest_measured_fourtuple"] = x is nearest
    return output


def _new_figure():
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    figure = Figure(figsize=(10, 5), layout="constrained")
    FigureCanvasAgg(figure)
    return figure


def _save(figure, directory, name):
    paths = []
    for suffix in ("png", "svg"):
        path = directory/(name+"."+suffix)
        figure.savefig(path, dpi=160)
        paths.append(str(path))
    figure.clear()
    return paths


def _metric_figure(rows, config, gate, state, methods, title, limit, show_fixed_relative=True):
    figure = _new_figure()
    ax = figure.subplots()
    invalid = 0
    for index, name in enumerate(methods):
        if name == "HISTORY":
            ax.text(index, .90, "NOT_RUN", transform=ax.get_xaxis_transform(), ha="center", fontsize=8)
            continue
        values = [r for r in method_rows(rows) if method_id(r) == name and state_id(r, config) == state]
        valid = [r for r in values if not anatomy_issues(r, config)]
        invalid += len(values)-len(valid)
        ax.scatter([index]*len(valid), [number(get(r, "relative_H_step_error", "H_error")) for r in valid],
                   marker="x" if "ORACLE" in name else "o", alpha=.8)
        cohort = next((c for c in gate.get("cohorts", []) if c["method"] == name and c["state"] == state), None)
        if cohort and cohort["complete_valid"]:
            ax.plot([index-.18, index+.18], [cohort["median_H_error"]]*2, color="black", lw=2)
        else:
            label = "NOT_RUN" if not values else "incomplete"
            ax.text(index, .98, label, transform=ax.get_xaxis_transform(), ha="center", fontsize=8)
    ax.axhline(limit, color="tab:red", linestyle="--", label="registered absolute threshold")
    fixed = next((c for c in gate.get("cohorts", []) if c["method"] == "FIXED-DEEP" and c["state"] == state), None)
    if show_fixed_relative and fixed and fixed["complete_valid"]:
        relative = (config["early_gate_excess"]+fixed["median_H_error"] if state == "early" else config["legal_gate_baseline_ratio"]*fixed["median_H_error"])
        ax.axhline(relative, color="tab:orange", linestyle=":", label="registered fixed-relative threshold")
    ax.set_xticks(range(len(methods)), [_label(m) for m in methods], rotation=15)
    ax.set_ylabel("relative H step error (unfloored reference)")
    ax.set_title(title)
    ax.grid(axis="y", alpha=.2)
    ax.legend(fontsize=8)
    figure.text(.01, .01, "HISTORY: NOT_RUN. Partial-cohort medians absent. Failed/invalid rows: "+str(invalid)+"; raw CSV retains all rows.", fontsize=8)
    return figure


DISPLAY_METHODS = ("FIXED-DEEP", "WIDE-M", "HISTORY", "CHEAP-TASK", "ORACLE-M",
                   "PROTECTED-ORACLE", "PROTECTED-RANDOM")
FROZEN_SEED_POINTS = {"FIXED-DEEP": (4, 3), "WIDE-M": (16, 1), "CHEAP-TASK": (4, 3),
                      "ORACLE-M": (4, 3), "PROTECTED-ORACLE": (6, 3), "PROTECTED-RANDOM": (6, 3)}


def _label(method):
    return method+(" [offline diagnostic]" if "ORACLE" in method or method == "PROTECTED-RANDOM" else "")


def _width_depth_figure(rows, config):
    figure = _new_figure()
    ax, table_ax = figure.subplots(1, 2, gridspec_kw={"width_ratios": [1, 1.6]})
    table_rows = []
    for method in DISPLAY_METHODS:
        measured = [r for r in method_rows(rows) if method_id(r) == method and state_id(r, config) == "late"
                    and number(get(r, "actual_rank", "rank")) is not None and action_fourtuple(r) is not None]
        if not measured or method not in FROZEN_SEED_POINTS:
            continue
        coordinates = sorted({(number(get(r, "allocation.M", "seed_metadata.allocation.M")) or FROZEN_SEED_POINTS[method][0],
                               number(get(r, "degree", "allocation.degree", "seed_metadata.degree")) or FROZEN_SEED_POINTS[method][1]) for r in measured})
        ax.scatter([x for x, y in coordinates], [y for x, y in coordinates], label=_label(method), s=65)
        ranks = [number(get(r, "actual_rank", "rank")) for r in measured]
        tuples = [action_fourtuple(r) for r in measured]
        ranges = [str(min(v[i] for v in tuples))+".."+str(max(v[i] for v in tuples)) for i in range(4)]
        table_rows.append([method, str(len(measured)), str(int(min(ranks)))+".."+str(int(max(ranks)))]+ranges)
    ax.set_xlabel("requested M width (frozen)")
    ax.set_ylabel("Krylov degree")
    ax.set_title("Built/measured depth-width points")
    ax.grid(alpha=.2)
    if table_rows:
        ax.legend(fontsize=6)
    else:
        ax.text(.5, .5, "NOT_RUN: no measured point", transform=ax.transAxes, ha="center")
    table_ax.set_axis_off()
    table_ax.set_title("Actual late per-parent ranges", fontsize=10)
    if table_rows:
        table = table_ax.table(cellText=table_rows, colLabels=["Method", "n", "U rank", "F", "F*", "L", "L*"],
                               colWidths=[.29, .055, .115, .135, .135, .135, .135],
                               cellLoc="center", bbox=[0, .12, 1, .76])
        table.auto_set_font_size(False)
        table.set_fontsize(6.5)
    else:
        table_ax.text(.5, .5, "NOT_RUN: no actual rank/fourtuple", transform=table_ax.transAxes, ha="center")
    figure.suptitle("B - frozen tested points; HISTORY NOT_RUN; no inferred sweep")
    return figure


def _paired_state_figure(rows, config):
    # Historical function name retained; observations in each panel are independent.
    figure = _new_figure()
    axes = figure.subplots(1, 2)
    parents = tuple(config.get("parents", (2001, 2005, 2003, 2007, 2013)))
    palette = ("#1f77b4", "#ff7f0e", "#7f7f7f", "#2ca02c", "#9467bd", "#8c564b", "#17becf")
    for ax, state in zip(axes, ("early", "late")):
        counts = dict(valid=0, NOT_RUN=0, FAILED=0, missing=0, invalid=0)
        for index, method in enumerate(DISPLAY_METHODS):
            if method == "HISTORY":
                continue
            xs, ys, failed_x, failed_y = [], [], [], []
            for p in parents:
                observed = [r for r in method_rows(rows) if method_id(r) == method and parent_id(r) == p and state_id(r, config) == state]
                if len(observed) != 1:
                    counts["missing"] += 1
                    continue
                row = observed[0]
                error_value = number(get(row, "relative_H_step_error", "H_error"))
                row_status = str(get(row, "status") or "")
                if row_status.startswith("NOT_RUN"):
                    counts["NOT_RUN"] += 1
                elif not anatomy_issues(row, config):
                    xs.append(parents.index(p)); ys.append(error_value)
                    counts["valid"] += 1
                elif row_status.startswith("FAILED") or row_status in ("QP_FAILED", "ERROR"):
                    counts["FAILED"] += 1
                    if error_value is not None and error_value >= 0:
                        failed_x.append(parents.index(p)); failed_y.append(error_value)
                else:
                    counts["invalid"] += 1
            if xs:
                ax.scatter(xs, ys, label=_label(method), color=palette[index], alpha=.8)
            if failed_x:
                ax.scatter(failed_x, failed_y, marker="x", color="red", s=65, label="FAILED diagnostic value")
                for x, y in zip(failed_x, failed_y):
                    ax.annotate(str(parents[x])+" "+method+" FAILED", (x, y), xytext=(5, 7),
                                textcoords="offset pixels", fontsize=6, color="red")
        ax.set_xticks(range(len(parents)), [str(p) for p in parents], rotation=25)
        ax.set_title(state+": observed values independently")
        ax.set_ylabel("relative H step error")
        ax.grid(axis="y", alpha=.2)
        text = "; ".join(k+"="+str(v) for k, v in counts.items())
        if counts["valid"] == 0:
            text = "NO VALID "+state.upper()+" ENDPOINTS\n"+text
        ax.text(.02, .98, text, transform=ax.transAxes, va="top", fontsize=6)
    common = {}
    for ax in axes:
        handles, labels = ax.get_legend_handles_labels()
        for handle, label in zip(handles, labels):
            common.setdefault(label, handle)
    if common:
        figure.legend(list(common.values()), list(common), loc="outside lower center", ncol=2, fontsize=7)
    figure.suptitle("C - observed early versus late; HISTORY NOT_RUN; no paired/aggregate claim")
    return figure


def _capture_error_figure(rows, config):
    figure = _new_figure()
    ax = figure.subplots()
    missing = 0
    for method in DISPLAY_METHODS:
        if method == "HISTORY":
            continue
        points = []
        for row in method_rows(rows):
            if method_id(row) != method or state_id(row, config) != "late":
                continue
            capture = number(get(row, "oracle_finalZ_source_capture", "oracle_Z_source_capture"))
            error = number(get(row, "relative_H_step_error", "H_error"))
            if capture is None or error is None or anatomy_issues(row, config):
                missing += 1
                continue
            points.append((capture, error, parent_id(row)))
        if points:
            ax.scatter([v[0] for v in points], [v[1] for v in points], label=_label(method))
            for x, y, p in points:
                offset = (-32, 10) if p == 2003 else ((9, -15) if p == 2013 else (4, 5))
                if method in ("PROTECTED-ORACLE", "PROTECTED-RANDOM"):
                    shift = 7 if method == "PROTECTED-ORACLE" else -7
                    offset = (offset[0], offset[1]+shift)
                ax.annotate(str(p), (x, y), xytext=offset, textcoords="offset pixels", fontsize=6,
                            ha="right" if offset[0] < 0 else "left",
                            arrowprops={"arrowstyle": "-", "lw": .4, "alpha": .4})
    ax.axvline(config["oracle_capture_threshold"], color="tab:red", ls="--", label="registered capture threshold")
    ax.set_xlabel("current final-Z KB-source capture (OFFLINE diagnostic)")
    ax.set_ylabel("final relative H step error (OFFLINE reference diagnostic)")
    ax.set_title("D - current KB capture versus final H error, by measured method")
    ax.grid(alpha=.2)
    ax.legend(fontsize=7)
    figure.suptitle("HISTORY NOT_RUN; offline reference diagnostic; missing/invalid late points="+str(missing), fontsize=8)
    return figure


def _capture_figure(rows, config):
    figure = _new_figure()
    axes = figure.subplots(1, 3)
    fields = [("material span", ("oracle_material_span_capture", "material_span_capture")),
              ("initial qM KB source", ("oracle_qM_source_capture",)),
              ("final Z KB source", ("oracle_finalZ_source_capture", "oracle_Z_source_capture"))]
    methods = ("ORACLE-M", "PROTECTED-ORACLE", "PROTECTED-RANDOM")
    for ax, (label, names) in zip(axes, fields):
        for i, method in enumerate(methods):
            values = [number(get(r, *names)) for r in method_rows(rows) if method_id(r) == method and state_id(r, config) == "late"]
            values = [v for v in values if v is not None]
            ax.scatter([i]*len(values), [1-v for v in values], marker="x")
        ax.axhline(1-config["oracle_capture_threshold"], ls="--", color="tab:red")
        ax.set_yscale("symlog", linthresh=1e-8)
        ax.set_xticks(range(3), ["raw", "protected", "control"], rotation=20)
        ax.set_title(label)
        ax.grid(axis="y", alpha=.2)
    axes[0].set_ylabel("1 - capture (symlog display; exact zero preserved)")
    figure.suptitle("D - OFFLINE oracle E/KB-source diagnostics; no online oracle trajectory")
    figure.text(.01, .01, "Capture certification requires all three + valid unfloored target. HISTORY: NOT_RUN.", fontsize=8)
    return figure


def _closed_cost_figure(gate):
    figure = _new_figure()
    axes = figure.subplots(1, 3)
    specs = [("adaptive_FIXED_material_ratio", .8, "material ratio"),
             ("physical_vector_RHS_ratio", .5, "paid physical vector RHS ratio"),
             ("deployment_wall_ratio", .8, "deployment wall ratio")]
    for ax, (key, limit, title) in zip(axes, specs):
        rows = [r for r in gate.get("per_parent", []) if number(r.get(key)) is not None]
        ax.bar([str(r["parent_id"]) for r in rows], [r[key] for r in rows])
        ax.axhline(limit, ls="--", color="tab:red")
        ax.set_title(title)
        ax.grid(axis="y", alpha=.2)
    figure.suptitle("E - descriptive three-parent own-trajectory results: "+gate["status"])
    figure.text(.01, .01, "Offline teacher/reference audit cost is separately paid and excluded from deployment wall; missing ratios stay absent.", fontsize=8)
    return figure


def _iteration_points(rows):
    points = []
    for row in rows:
        if method_id(row) not in ("FULL_GN", "FIXED-DEEP")+LEGAL_METHODS:
            continue
        traces = get(row, "iteration_trace", "trajectory_trace", "trace", "iterations")
        if not isinstance(traces, list):
            traces = [row] if row.get("record_kind") in ("iteration", "trajectory_iteration", "accepted_iteration") else []
        for value in traces:
            if not isinstance(value, dict):
                continue
            if value.get("accepted") is False:
                continue
            index = number(get(value, "accepted_index", "iteration", "outer_iteration"))
            if index is None:
                continue
            points.append({"parent_id": parent_id(row), "method": method_id(row), "iteration": index,
                           "full_objective": number(get(value, "full_objective", "objective", "objective_after")),
                           "material_error": number(get(value, "material_error", "material_relative_error", "truth_metrics.material_relative_error")),
                           "truth_source": "OFFLINE_INDEPENDENT_EVALUATION"})
    return points


def _closed_curve_figure(points):
    figure = _new_figure()
    axes = figure.subplots(1, 2)
    keys = sorted({(r["parent_id"], r["method"]) for r in points}, key=lambda x: (str(x[0]), str(x[1])))
    for p, method in keys:
        values = sorted([r for r in points if r["parent_id"] == p and r["method"] == method], key=lambda r: r["iteration"])
        for ax, metric in zip(axes, ("material_error", "full_objective")):
            valid = [r for r in values if r[metric] is not None]
            if valid:
                ax.plot([r["iteration"] for r in valid], [r[metric] for r in valid], marker=".", label=str(p)+" "+str(method))
    axes[0].set_ylabel("reconstruction material error (offline truth)")
    axes[1].set_ylabel("accepted full objective")
    for ax in axes:
        ax.set_xlabel("own accepted iteration")
        ax.grid(alpha=.2)
    if keys:
        axes[1].legend(fontsize=6)
    figure.suptitle("E - own-trajectory reconstruction and objective iteration curves")
    figure.text(.01, .01, "No trajectory interpolation or fabricated missing truth values. Offline truth never enters the online builder.", fontsize=8)
    return figure


def write_report(root, anatomy_rows, config, *, closed_loop_rows=None, history_rows=None,
                 book=None, make_figures=True, output_dir=None, figure_dir=None):
    """Write raw CSV + A-D (conditional E) and return paths/registered gates.

    Figure generation is deliberately lazy; no fixture result can become a
    real-data claim.  A closed anatomy gate forces Phase2 NOT_RUN reporting.
    """
    config = settings(config)
    root = Path(root)
    out = Path(output_dir) if output_dir is not None else root/"results/a20_r1/report"
    figs = Path(figure_dir) if figure_dir is not None else root/"figures/a20_r1"
    out.mkdir(parents=True, exist_ok=True)
    rows = list(anatomy_rows)
    if closed_loop_rows is not None:
        closed_loop_rows = list(closed_loop_rows)
    if history_rows is not None:
        history_rows = list(history_rows)
    paths = []
    with _group(book, "gates_and_raw_csv"):
        anatomy = evaluate_anatomy(rows, config)
        closed = (evaluate_closed_loop(closed_loop_rows, config, anatomy["selected_method"])
                  if closed_loop_rows is not None else {"status": "NOT_RUN_NO_CLOSED_LOOP_ROWS"})
        if anatomy["selected_method"] is None:
            closed = {"status": "NOT_RUN_GATE_CLOSED"}
        history = evaluate_history(history_rows, config) if history_rows is not None and anatomy["selected_method"] is not None else {"status": "NOT_RUN", "B": "NOT_RUN"}
        tables = {"ANATOMY_RAW.csv": annotate_rows(rows, config),
                  "RANK_ACTION_MATCHING.csv": rank_action_matching(rows, config),
                  "CLOSED_LOOP_RAW.csv": annotate_rows(list(closed_loop_rows or []), config, "closed_loop"),
                  "CLOSED_LOOP_COMPARISONS.csv": closed.get("per_parent", []),
                  "CLOSED_LOOP_ITERATIONS.csv": _iteration_points(closed_loop_rows or []),
                  "HISTORY_RAW.csv": annotate_rows(list(history_rows or []), config, "history_ablation")}
        for name, values in tables.items():
            path = out/name
            _csv(path, values, ("method", "parent_id", "status", "evidence_source_class"))
            paths.append(str(path))
        snapshot = {"anatomy": anatomy, "closed_loop": closed, "history": history,
                    "snapshot_HISTORY": "NOT_RUN_NO_OWN_ACCEPTED_TRAJECTORY",
                    "exposure": "historically_exposed_feasibility", "scientific_judgment": "PARENT_ONLY",
                    "oracle_E_policy": "OFFLINE_DIAGNOSTIC_ONLY_NEVER_ONLINE_CANDIDATE",
                    "source_freeze": config.get("source_freeze"), "figures": {}}
        gate_path = out/"REGISTERED_GATES.json"
        _json(gate_path, snapshot)
        paths.append(str(gate_path))
    if not make_figures:
        snapshot["figure_status"] = "NOT_RUN_FIGURES_DISABLED"
    else:
        with _group(book, "figure_setup"):
            try:
                import matplotlib
                plot_available = True
            except ImportError:
                plot_available = False
        if not plot_available:
            snapshot["figure_status"] = "NOT_RUN_MATPLOTLIB_UNAVAILABLE"
        else:
            figs.mkdir(parents=True, exist_ok=True)
            groups = [
                ("A", lambda: _metric_figure(rows, config, anatomy, "late", DISPLAY_METHODS, "A - five-parent primary late H-error; medians only complete cohorts", config["oracle_gate_median"], False)),
                ("B", lambda: _width_depth_figure(rows, config)),
                ("C", lambda: _paired_state_figure(rows, config)),
                ("D", lambda: _capture_error_figure(rows, config)),
                ("D_CAPTURE_CERT", lambda: _capture_figure(rows, config)),
            ]
            if closed_loop_rows is not None and anatomy["selected_method"] is not None:
                iteration_points = _iteration_points(closed_loop_rows)
                if iteration_points:
                    groups.append(("E", lambda: _closed_curve_figure(iteration_points)))
                    snapshot["E_curve_status"] = "SUPPLIED_ITERATION_POINTS_ONLY_MISSING_VALUES_ABSENT"
                else:
                    snapshot["E_curve_status"] = "NOT_RUN_MISSING_ITERATION_CURVES"
                groups.append(("E_COST", lambda: _closed_cost_figure(closed)))
            for name, build in groups:
                with _group(book, "figure_"+name):
                    generated = _save(build(), figs, name)
                    snapshot["figures"][name] = generated
                    paths.extend(generated)
            snapshot["figure_status"] = "GENERATED_RESEARCH_FIGURES"
    with _group(book, "manifest"):
        _json(gate_path, snapshot)
        manifest_path = out/"REPORT_MANIFEST.json"
        manifest = {"status": "STATIC_REPORT_WRITTEN", "paths": paths,
                    "figure_status": snapshot["figure_status"], "figures": snapshot["figures"],
                    "phase2_status": closed["status"], "HISTORY": snapshot["snapshot_HISTORY"],
                    "provided_history_ablation_status": history["status"],
                    "scientific_judgment": "PARENT_ONLY", "no_physics_or_external_data_access": True}
        _json(manifest_path, manifest)
    return {"paths": paths+[str(manifest_path)], "figures": snapshot["figures"],
            "anatomy": anatomy, "closed_loop": closed, "history": history,
            "figure_status": snapshot["figure_status"]}


generate_report = write_report
