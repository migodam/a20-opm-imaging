"""Static A22-R1 figures from parent-supplied scene-cluster summaries only.

No reconstruction, truth, Jacobian, cache or results file is read here.
``render_plots`` performs no gate decision and returns absolute artifact paths.
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path
import shutil

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np


SCENES = (2001, 2003, 2014, 2009)
METHODS = ("RANDOM", "A1", "A2", "A3", "OFFLINE_FULL_J")
COLORS = {"RANDOM": "#77828c", "A1": "#2873b8", "A2": "#d88025",
          "A3": "#1b8b65", "OFFLINE_FULL_J": "#9560ad"}
MARKERS = {2001: "o", 2003: "s", 2014: "^", 2009: "D"}
SCENE_COLORS = {2001: "#216f9f", 2003: "#d67b28", 2014: "#7661a5", 2009: "#15927b"}
LABELS = {**{method: method for method in METHODS},
          "OFFLINE_FULL_J": "FULL-J (OFFLINE diagnostic)"}
METRICS = ("nrmse_phys", "nrmse_prior", "s_sep", "f_error_phys", "f_error_prior",
           "f_truth_phys", "f_truth_prior", "qphys", "qprior")
FOOTER = ("Four historically exposed scene clusters: 2001, 2003, 2014, 2009. "
          "Known background χ₀ = 0.1 + 0.04i; fixed 32D material chart.\n"
          "All plotted errors and energy fractions are in-chart. "
          "FULL-J is an OFFLINE diagnostic only; no formal validation is implied.\n"
          "A1/A2/A3 select the same direction sets in this screening; coincident markers are retained.")


def _number(value):
    if isinstance(value, bool):
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _normalize(rows):
    normalized, seen = [], set()
    for raw in rows:
        row = dict(raw)
        row["scene"] = int(row.get("scene", row.get("scene_id")))
        row["k"] = int(row["k"])
        row["test"] = str(row["test"]).upper()
        row["method"] = str(row["method"])
        if row["scene"] not in SCENES or row["method"] not in METHODS:
            raise ValueError("A22_R1_UNREGISTERED_PLOT_SCENE_OR_METHOD")
        if row["k"] not in (8, 16) or row["test"] not in ("A", "B"):
            raise ValueError("A22_R1_UNREGISTERED_PLOT_K_OR_TEST")
        row["qphys"] = row.get("qphys", row.get("q_phys"))
        row["qprior"] = row.get("qprior", row.get("q_prior"))
        if row.get("status") == "COMPLETE":
            key = (row["scene"], row["method"], row["k"], row["test"])
            if key in seen:
                raise ValueError("A22_R1_PLOTS_REQUIRE_ONE_ROW_PER_SCENE_CLUSTER:" + str(key))
            seen.add(key)
        for name in METRICS:
            row[name] = _number(row.get(name))
        normalized.append(row)
    return sorted(normalized, key=lambda row: (
        row["test"], row["k"], METHODS.index(row["method"]), SCENES.index(row["scene"])))


def _csv(path, rows):
    rows = [dict(row) for row in rows]
    names = list(dict.fromkeys(key for row in rows for key in row))
    if not names:
        names = ["status"]
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=names)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(value, sort_keys=True, default=str)
                             if isinstance(value, (dict, list, tuple)) else value
                             for key, value in row.items()})


def _lookup(rows):
    return {(row["scene"], row["method"], row["k"], row["test"]): row
            for row in rows if row.get("status") == "COMPLETE"}


def _record(data, plot, panel, row, x, y, x_metric, y_metric, *, statistic="scene", n=1):
    data.append(dict(plot=plot, panel=panel, scene=row.get("scene", ""),
                     method=row["method"], k=row["k"], test=row["test"],
                     x_metric=x_metric, y_metric=y_metric, x=x, y=y,
                     statistic=statistic, scene_clusters=n,
                     source="parent-supplied within-scene replicate average",
                     full_J_scope="OFFLINE diagnostic" if row["method"] == "OFFLINE_FULL_J" else "online-legal"))


def _decorate(fig, title, *, subtitle=None, extra_footer=None, right=0.77):
    fig.suptitle(title, x=0.075, y=0.97, ha="left", fontsize=15, weight="bold")
    if subtitle:
        fig.text(0.075, 0.91, subtitle, ha="left", fontsize=10, color="#45535e")
    fig.text(0.075, 0.035, FOOTER + ("\n" + extra_footer if extra_footer else ""),
             ha="left", va="bottom", fontsize=8, color="#45535e")
    fig.subplots_adjust(left=0.09, right=right, top=0.84, bottom=0.22 if extra_footer else 0.18,
                        wspace=0.31)


def _methods_legend(fig, *, y=0.84):
    handles = [Line2D([], [], color=COLORS[method], marker="o", linestyle="",
                      label=LABELS[method], markersize=7) for method in METHODS]
    fig.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.79, y),
               frameon=False, fontsize=9)
    scenes = [Line2D([], [], color="#394651", marker=MARKERS[scene], linestyle="",
                     label=str(scene), markersize=7) for scene in SCENES]
    fig.legend(handles=scenes, title="Exposed scene clusters", loc="upper left",
               bbox_to_anchor=(0.79, y - 0.29), frameon=False, fontsize=9, title_fontsize=9)


def _empty(ax, message="No COMPLETE scene metrics available"):
    ax.text(0.5, 0.5, message, transform=ax.transAxes, ha="center", va="center", fontsize=10)


def _point(ax, x, y, row, *, annotate=True, method_offset=None):
    method, scene = row["method"], row["scene"]
    ax.scatter(x, y, color=COLORS[method], marker=MARKERS[scene], s=48,
               alpha=0.86, edgecolor="white", linewidth=0.45, zorder=3)
    if annotate:
        offset = method_offset or ((4, 5), (4, -10), (-26, 4), (-26, -11), (5, 12))[METHODS.index(method)]
        ax.annotate(str(scene), (x, y), xytext=offset, textcoords="offset points",
                    fontsize=7, color=COLORS[method], alpha=0.95)


def _square_limits(ax, points):
    upper = max((max(x, y) for x, y in points), default=1.0)
    upper = max(upper * 1.15, 1e-6)
    ax.set_xlim(0.0, upper)
    ax.set_ylim(0.0, upper)
    return upper


def _scatter_plot(plot, lookup, data, x_metric, y_metric, *, title, xlabel, ylabel,
                  fractions=False, restricted=False):
    fig, ax = plt.subplots(figsize=(12, 7))
    points = []
    for method in METHODS:
        for scene in SCENES:
            row = lookup.get((scene, method, 16, "A"))
            if row is None:
                continue
            other = lookup.get((scene, method, 16, "B")) if restricted else row
            if other is None:
                continue
            x, y = row[x_metric], other[y_metric]
            if x is None or y is None:
                continue
            _point(ax, x, y, row)
            points.append((x, y))
            _record(data, plot, "main", row, x, y, x_metric,
                    "test_B." + y_metric if restricted else y_metric)
    if fractions:
        ax.set_xlim(0, 1.02)
        ax.set_ylim(0, 1.02)
        upper = 1.0
    else:
        upper = _square_limits(ax, points)
    ax.plot([0, upper], [0, upper], color="#8b969e", linestyle="--", linewidth=1,
            label="Equal fractions" if fractions else "Equal NRMSE")
    if plot == "A":
        ax.plot([0, upper / 2], [0, upper], color="#b56749", linestyle=":", linewidth=1,
                label="S_sep = 2 screening threshold")
    if restricted:
        ax.plot([0, upper / 1.25], [0, upper], color="#b56749", linestyle=":", linewidth=1.3,
                label="Restricted / projected = 1.25")
    if not points:
        _empty(ax)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(alpha=0.15)
    ax.legend(loc="upper left", frameon=False, fontsize=8)
    extra = ("Test B sets the prior component to zero: prior NRMSE = 1 by construction. "
             "Test B S_sep is not separation evidence." if restricted else None)
    _decorate(fig, title, subtitle="Primary k = 16; one point per scene cluster and split method.",
              extra_footer=extra)
    _methods_legend(fig)
    return fig


def _selectivity(lookup, data):
    fig, axes = plt.subplots(1, 2, figsize=(14, 7))
    for ax, metric, threshold, title in zip(
            axes, ("qphys", "qprior"), (0.7, 1.3), ("Physics selectivity q_phys", "Prior selectivity q_prior")):
        present = 0
        for index, method in enumerate(METHODS):
            values = []
            for offset, scene in zip((-0.18, -0.06, 0.06, 0.18), SCENES):
                row = lookup.get((scene, method, 16, "A"))
                if row is None or row[metric] is None:
                    continue
                value = row[metric]
                _point(ax, index + offset, value, row, annotate=False)
                ax.annotate(str(scene), (index + offset, value), xytext=(0, 6),
                            textcoords="offset points", fontsize=6.5, ha="center", color=COLORS[method])
                values.append(value)
                _record(data, "C", metric, row, index + offset, value, "method_position", metric)
                present += 1
            if values:
                median = float(np.median(values))
                ax.plot([index - 0.26, index + 0.26], [median, median],
                        color="#263641", linewidth=2.3, zorder=4)
                _record(data, "C", metric, dict(method=method, k=16, test="A"),
                        index, median, "method_position", metric, statistic="median_scene", n=len(values))
        ax.axhline(1.0, color="#9ca5aa", linestyle="--", linewidth=1, label="Signal-proportional error (q = 1)")
        ax.axhline(threshold, color="#b56749", linestyle=":", linewidth=1.3,
                   label=f"Screening threshold {threshold:g}")
        ax.set_xticks(range(len(METHODS)), ["RANDOM", "A1", "A2", "A3", "FULL-J\nOFFLINE"], fontsize=9)
        ax.set_xlim(-0.5, 4.5)
        ax.set_ylim(bottom=0)
        ax.set_title(title, fontsize=11)
        ax.set_ylabel("Error-energy share / truth-energy share")
        ax.grid(axis="y", alpha=0.15)
        ax.legend(loc="upper left", frameon=False, fontsize=7)
        if not present:
            _empty(ax)
    _decorate(fig, "C · Normalized error selectivity", right=0.94,
              subtitle="Test A, k = 16. Markers are four scene clusters; dark bars are scene medians.")
    return fig


def _paired(lookup, data):
    fig, axes = plt.subplots(1, 2, figsize=(12, 7))
    for ax, metric, title in zip(axes, ("nrmse_phys", "s_sep"),
                               ("Physics NRMSE (lower is better)", "Separation ratio (higher is better)")):
        present = 0
        for index, scene in enumerate(SCENES):
            pair = [lookup.get((scene, method, 16, "A")) for method in ("A2", "A3")]
            if any(row is None or row[metric] is None for row in pair):
                continue
            values = [row[metric] for row in pair]
            ax.plot([0, 1], values, color=SCENE_COLORS[scene], marker=MARKERS[scene],
                    linewidth=1.5, markersize=7, alpha=0.9, label=str(scene))
            ax.annotate(str(scene), (1, values[1]), xytext=(6, (index - 1.5) * 7),
                        textcoords="offset points", fontsize=8, color=SCENE_COLORS[scene])
            for x, row, value in zip((0, 1), pair, values):
                _record(data, "D", metric, row, x, value, "A2_A3_position", metric)
            present += 1
        ax.set_xticks((0, 1), ("A2", "A3"))
        ax.set_xlim(-0.15, 1.4)
        ax.set_ylim(bottom=0)
        ax.set_title(title, fontsize=11)
        ax.set_ylabel("NRMSE" if metric == "nrmse_phys" else "NRMSE_prior / NRMSE_phys")
        ax.grid(axis="y", alpha=0.15)
        if metric == "s_sep":
            ax.axhline(2.0, color="#b56749", linestyle=":", linewidth=1.1,
                       label="S_sep = 2 screening threshold")
        if not present:
            _empty(ax, "No COMPLETE paired scene metrics available")
        ax.legend(loc="lower left", title="Exposed clusters", frameon=False, fontsize=8, title_fontsize=8)
    _decorate(fig, "D · A2 versus A3 paired scene comparison", right=0.94,
              subtitle="Test A, primary k = 16. Each connected pair is one independent scene cluster.")
    return fig


def _robustness(lookup, data):
    fig, axes = plt.subplots(1, 3, figsize=(16, 7))
    metrics = ("nrmse_phys", "s_sep", "f_truth_phys")
    titles = ("Physics NRMSE", "Separation ratio", "Physics truth-energy coverage")
    for ax, metric, title in zip(axes, metrics, titles):
        present = 0
        for method_index, method in enumerate(METHODS):
            medians, locations = [], []
            shift = (method_index - 2) * 0.065
            for x, k in enumerate((8, 16)):
                values = []
                for scene_index, scene in enumerate(SCENES):
                    row = lookup.get((scene, method, k, "A"))
                    if row is None or row[metric] is None:
                        continue
                    value = row[metric]
                    location = x + shift + (scene_index - 1.5) * 0.012
                    _point(ax, location, value, row, annotate=False)
                    values.append(value)
                    _record(data, "E", metric, row, location, value, "k_position", metric)
                    present += 1
                if values:
                    median = float(np.median(values))
                    medians.append(median)
                    locations.append(x + shift)
                    _record(data, "E", metric, dict(method=method, k=k, test="A"),
                            x + shift, median, "k_position", metric,
                            statistic="median_scene", n=len(values))
            if medians:
                ax.plot(locations, medians, color=COLORS[method], marker="_", markersize=15,
                        linewidth=1.8, linestyle="--" if method == "OFFLINE_FULL_J" else "-", zorder=4)
        ax.set_xticks((0, 1), ("k = 8\nsecondary", "k = 16\nprimary"))
        ax.set_xlim(-0.3, 1.3)
        ax.set_ylim(bottom=0)
        if metric == "f_truth_phys":
            ax.set_ylim(0, 1.02)
            ax.axhline(0.35, color="#b56749", linestyle=":", linewidth=1,
                       label="k = 16 screening coverage 0.35")
        elif metric == "s_sep":
            ax.axhline(2, color="#b56749", linestyle=":", linewidth=1,
                       label="k = 16 screening S_sep = 2")
        ax.set_title(title, fontsize=11)
        ax.grid(axis="y", alpha=0.15)
        if not present:
            _empty(ax)
        if metric != "nrmse_phys":
            ax.legend(loc="upper left", frameon=False, fontsize=7)
    _decorate(fig, "E · Frozen k = 8 / 16 robustness check", right=0.80,
              subtitle="Test A. Points are scene clusters; lines connect scene medians. No k is selected from this plot.")
    _methods_legend(fig)
    return fig


def render_plots(root, scene_rows, comparison_rows):
    """Render A-F PNG/SVG and exact plot-data CSV from passed rows.

    Scene rows must already average replicates within each of the four scenes.
    Duplicate COMPLETE scene/method/k/test rows are rejected. Comparison rows
    are exported verbatim for traceability and never used to decide a gate.
    Returns ``{figures, data_csv, comparison_csv, scene_csv, manifest}``.
    """
    root = Path(root).resolve()
    rows = _normalize(list(scene_rows))
    comparisons = [dict(row) for row in comparison_rows]
    lookup = _lookup(rows)
    directory = root / "figures/A22_R1"
    audit_directory = root / "research/delegated/a22-r1-plots"
    directory.mkdir(parents=True, exist_ok=True)
    audit_directory.mkdir(parents=True, exist_ok=True)
    data, figures = [], {}
    builders = {
        "A": lambda: _scatter_plot("A", lookup, data, "nrmse_phys", "nrmse_prior",
                                   title="A · Common one-shot reconstruction error localization",
                                   xlabel="Physics-subspace NRMSE", ylabel="Prior-subspace NRMSE"),
        "B": lambda: _scatter_plot("B", lookup, data, "f_truth_phys", "f_error_phys",
                                   title="B · Truth-energy share versus error-energy share",
                                   xlabel="Truth-energy fraction in V_phys", ylabel="Error-energy fraction in V_phys",
                                   fractions=True),
        "C": lambda: _selectivity(lookup, data),
        "D": lambda: _paired(lookup, data),
        "E": lambda: _robustness(lookup, data),
        "F": lambda: _scatter_plot("F", lookup, data, "nrmse_phys", "nrmse_phys",
                                   title="F · Restricted physics branch versus full 32D projection",
                                   xlabel="Test A: projected full-32D physics NRMSE",
                                   ylabel="Test B: restricted physics NRMSE", restricted=True),
    }
    with plt.rc_context({"font.family": "DejaVu Sans", "font.size": 10,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "svg.fonttype": "none", "savefig.facecolor": "white"}):
        for letter, builder in builders.items():
            fig = builder()
            try:
                paths = {kind: directory / f"{letter}.{kind}" for kind in ("png", "svg")}
                fig.savefig(paths["png"], dpi=180, bbox_inches="tight")
                fig.savefig(paths["svg"], bbox_inches="tight")
                figures[letter] = {kind: str(path) for kind, path in paths.items()}
            finally:
                plt.close(fig)
    data_path = audit_directory / "PLOT_DATA.csv"
    comparison_path = audit_directory / "COMPARISON_ROWS.csv"
    scene_path = audit_directory / "SCENE_ROWS.csv"
    _csv(data_path, data)
    _csv(comparison_path, comparisons)
    _csv(scene_path, rows)
    shutil.copyfile(data_path, directory / "PLOT_DATA.csv")
    manifest_path = audit_directory / "PLOT_MANIFEST.json"
    manifest = dict(
        schema="a22_r1.static_plots.v1", status="COMPLETE", figures=figures,
        plot_record_count=len(data), supplied_scene_row_count=len(rows),
        complete_scene_row_count=len(lookup), scene_clusters=list(SCENES),
        primary_k=16, secondary_k=8, known_background=[0.1, 0.04],
        scope="fixed 32D chart; four historically exposed scene clusters",
        full_J_scope="OFFLINE diagnostic only", gate_decision_performed=False,
        evaluator_files_read=False,
        test_B_prior_nrmse="1 by construction; Test B S_sep is not separation evidence",
        missing_or_nonfinite_metrics=[
            dict(scene=row["scene"], method=row["method"], k=row["k"], test=row["test"],
                 metric=metric) for row in rows if row.get("status") == "COMPLETE"
            for metric in METRICS if row[metric] is None],
        data_csv=str(data_path), comparison_csv=str(comparison_path), scene_csv=str(scene_path),
    )
    manifest_path.write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    shutil.copyfile(manifest_path, directory / "PLOT_MANIFEST.json")
    return dict(figures=figures, data_csv=str(data_path), comparison_csv=str(comparison_path),
                scene_csv=str(scene_path), manifest=str(manifest_path))
