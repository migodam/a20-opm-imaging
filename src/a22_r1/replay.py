"""Cached A22-R1 replay with a frozen split and exact original small QP.

This module never constructs Maxwell operators or labels. Every online split
is persisted before evaluator-only caches or original errors are opened. One
common 32D constrained estimate per case supplies every Test A projection;
Test B uses the same quadratic, physical constraints and full-scene lambda.
"""
from __future__ import annotations

from collections import Counter
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import datetime, timezone
import csv
import gzip
import itertools
import json
from pathlib import Path
import time
from typing import Any, Mapping
import uuid

import numpy as np
from scipy import linalg as la
from scipy.optimize import nnls

from a20.backend import MaterialChart, pack
from a20.costs import plain
from a20.material import QPFailure, constraint_map
from a22.core import constrained_material_solve
from a22.evaluate import _calibrate_data, stage_a_case_key
from .metrics import subspace_metrics


SCENES = (2001, 2003, 2014, 2009)
ONLINE_METHODS = ("RANDOM", "A1", "A2", "A3")
OFFLINE_METHOD = "OFFLINE_FULL_J"


class ReplayContractError(ValueError):
    """A saved input or freeze does not satisfy the preregistered replay."""


class ReplayReproductionError(RuntimeError):
    """Common estimates did not reproduce the frozen Stage A diagnostics."""

    def __init__(self, summary: dict[str, Any]):
        super().__init__("A22_R1_COMMON_REPRODUCTION_FAILED; Test B was not run")
        self.result = summary


@dataclass(frozen=True)
class OnlineCache:
    scene: int
    AW: np.ndarray
    background: np.ndarray
    chart: MaterialChart
    anchor: np.ndarray
    whitening: float
    sigma: float
    lam: float
    common_V: np.ndarray
    scores: Mapping[str, np.ndarray]
    declared_object_radius: float
    manifest_path: Path
    cache_path: Path


@dataclass(frozen=True)
class Split:
    scene: int
    method: str
    k: int
    order: np.ndarray
    phys: np.ndarray
    prior: np.ndarray
    seed: tuple[int, int] | None = None


@dataclass(frozen=True)
class Label:
    clean: np.ndarray
    truth: np.ndarray
    direction: np.ndarray
    amplitude: float
    path: Path


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _rel(path: Path, root: Path) -> str:
    """Portable artifact references, independent of the solve platform."""
    return path.relative_to(root).as_posix()


def _encoded(value: Any) -> str:
    return json.dumps(plain(value), sort_keys=True, allow_nan=False)


def _immutable_json(path: Path, value: Any) -> None:
    """Retain an existing semantic freeze; never replace a different result."""
    value = plain(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if _json(path) != value:
            raise ReplayContractError("IMMUTABLE_JSON_MISMATCH:" + str(path))
        return
    with path.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def _immutable_npz(path: Path, arrays: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        with np.load(path, allow_pickle=False) as archive:
            if set(archive.files) != set(arrays):
                raise ReplayContractError("IMMUTABLE_ARRAY_MEMBERS:" + str(path))
            for name, expected in arrays.items():
                expected = np.asarray(expected)
                actual = archive[name]
                equal = (actual.shape == expected.shape and actual.dtype == expected.dtype
                         and np.array_equal(actual, expected, equal_nan=True)
                         if actual.dtype.kind not in "US" else
                         actual.shape == expected.shape and actual.dtype == expected.dtype
                         and np.array_equal(actual, expected))
                if not equal:
                    raise ReplayContractError("IMMUTABLE_ARRAY_MISMATCH:" + str(path) + ":" + name)
        return
    with path.open("xb") as stream:
        np.savez_compressed(stream, **arrays)


def _append(path: Path, record: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(_encoded(record) + "\n")


def _csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    fields = list(dict.fromkeys(name for row in rows for name in row))
    with path.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({name: _encoded(value) if isinstance(value, (dict, list, tuple, np.ndarray))
                             else plain(value) for name, value in row.items()})


def _scope(book: Any, role: str):
    return book.scope(role) if hasattr(book, "scope") else nullcontext()


def _relative_close(actual: np.ndarray, expected: np.ndarray, rtol: float, name: str) -> None:
    if actual.shape != expected.shape or np.iscomplexobj(actual) != np.iscomplexobj(expected):
        raise ReplayContractError("CACHE_LAYOUT:" + name)
    if not np.all(np.isfinite(actual)) or not np.all(np.isfinite(expected)):
        raise ReplayContractError("CACHE_NONFINITE:" + name)
    scale = float(la.norm(expected.ravel()))
    difference = float(la.norm((actual - expected).ravel()))
    if difference > rtol * scale:
        raise ReplayContractError("CACHE_IDENTITY:" + name)


def _scalar(value: Any, name: str, *, positive: bool = True) -> float:
    raw = np.asarray(value)
    if raw.shape != () or raw.dtype.kind not in "fi":
        raise ReplayContractError("CACHE_SCALAR_LAYOUT:" + name)
    result = float(raw)
    if not np.isfinite(result) or (result <= 0 if positive else result < 0):
        raise ReplayContractError("CACHE_SCALAR_VALUE:" + name)
    return result


def _scene_ids(config: Mapping[str, Any]) -> tuple[int, ...]:
    ids = tuple(int(sid) for sid in config.get("scenes", config.get("scene_ids", SCENES)))
    if len(ids) != 4 or set(ids) != set(SCENES):
        raise ReplayContractError("ONLY_FOUR_FROZEN_SCREENING_SCENES_ARE_ALLOWED")
    return ids


def _require_evaluation_freeze(root: Path) -> None:
    """An offline cache read needs the complete global online split receipt."""
    path = root / "results/a22_r1/SPLIT_FREEZE.json"
    if not path.is_file():
        raise ReplayContractError("ONLINE_SPLIT_FREEZE_REQUIRED_BEFORE_OFFLINE_READ")
    freeze = _json(path)
    if (freeze.get("schema") != "a22_r1.split_freeze.v1" or freeze.get("status") != "COMPLETE"
            or set(freeze.get("scenes", ())) != set(SCENES)):
        raise ReplayContractError("GLOBAL_ONLINE_SPLIT_FREEZE_NOT_COMPLETE")
    for sid in SCENES:
        manifest = root / f"results/a22_r1/online/scene_{sid}.json"
        if not manifest.is_file() or _json(manifest).get("status") != "COMPLETE":
            raise ReplayContractError("ALL_ONLINE_SCENES_MUST_BE_FROZEN_BEFORE_EVALUATION")


def _load_online(root: Path, sid: int, config: Mapping[str, Any]) -> OnlineCache:
    """Read online members only; reject a cache different from frozen A22."""
    directory = root / "results/a22_r1/online"
    manifest_path = directory / f"scene_{sid}.json"
    cache_path = directory / f"scene_{sid}.npz"
    manifest = _json(manifest_path)
    if (manifest.get("schema") != "a22_r1.online_freeze.v1"
            or manifest.get("status") != "COMPLETE"):
        raise ReplayContractError("ONLINE_FREEZE_NOT_COMPLETE:" + str(sid))
    score_contract = manifest.get("scores", {})
    for name, expected in {"amplitude": 0, "noise_level": 1, "intervention": "nominal",
                           "orientation": "ascending", "tie_breaker": "common_basis_index"}.items():
        if score_contract.get(name) != expected:
            raise ReplayContractError("UNREGISTERED_SCORE_CONTRACT:" + str(sid) + ":" + name)
    required = {"AW", "background_field", "Q_spatial", "cell_volume", "anchor_chi",
                "whitening", "sigma_complex", "common_V", "context_json",
                "score_A1", "score_A2", "score_A3"}
    with np.load(cache_path, allow_pickle=False) as archive:
        if not required <= set(archive.files):
            raise ReplayContractError("MISSING_ONLINE_CACHE_MEMBERS:" + str(sid))
        values = {name: np.array(archive[name], copy=True) for name in required}
        orders = {method: np.array(archive["order_" + method], copy=True)
                  for method in ONLINE_METHODS[1:] if "order_" + method in archive.files}
    rtol = float(config.get("identity_rtol", 1e-9))
    provenance = _json(root / f"results/a22/stage_a/scene_{sid}/online_provenance.json")
    old_sigma = float(provenance["anchor"]["sigma_complex_reference"])
    old_lam = float(provenance["descriptor"]["regularization"])
    sigma = _scalar(values["sigma_complex"], "sigma_complex")
    whitening = _scalar(values["whitening"], "whitening")
    if abs(sigma - old_sigma) > rtol * old_sigma:
        raise ReplayContractError("NOISE_REFERENCE_CHANGED:" + str(sid))
    if abs(whitening - np.sqrt(2.) / sigma) > rtol * whitening:
        raise ReplayContractError("WHITENING_CHANGED:" + str(sid))
    AW = values["AW"]
    with np.load(root / f"results/a22/stage_a/scene_{sid}/online_factors.npz", allow_pickle=False) as old:
        _relative_close(AW, old["AW"], rtol, f"scene_{sid}.AW")
    if AW.shape != (1536, 32) or np.iscomplexobj(AW):
        raise ReplayContractError("AW_MUST_BE_REAL_1536_BY_32")
    background, Q, anchor, V = (values[name] for name in
                                ("background_field", "Q_spatial", "anchor_chi", "common_V"))
    if (background.shape != (6, 128) or not np.iscomplexobj(background)
            or not np.all(np.isfinite(background))):
        raise ReplayContractError("BACKGROUND_DATA_LAYOUT:" + str(sid))
    if Q.shape != (1728, 16) or np.iscomplexobj(Q) or not np.all(np.isfinite(Q)):
        raise ReplayContractError("FIXED_MATERIAL_CHART_LAYOUT:" + str(sid))
    if (anchor.shape != (1728,) or not np.iscomplexobj(anchor)
            or not np.allclose(anchor, .1 + .04j, rtol=0, atol=1e-14)):
        raise ReplayContractError("ANCHOR_MATERIAL_CHANGED:" + str(sid))
    volume = _scalar(values["cell_volume"], "cell_volume")
    if la.norm(volume * Q.T @ Q - np.eye(16)) > 1e-9:
        raise ReplayContractError("MATERIAL_METRIC_CHANGED:" + str(sid))
    if V.shape != (32, 32) or np.iscomplexobj(V) or la.norm(V.T @ V - np.eye(32)) > 1e-9:
        raise ReplayContractError("COMMON_BASIS_NOT_ORTHONORMAL:" + str(sid))
    with np.load(root / f"results/a22/stage_a/scene_{sid}/online_split_16.npz", allow_pickle=False) as old:
        if not np.array_equal(V, np.column_stack((old["V_phys"], old["V_prior"]))):
            raise ReplayContractError("COMMON_BASIS_MUST_BE_EXACT_SAVED_SPLIT16:" + str(sid))
    context = json.loads(str(values["context_json"].item()))
    radius = _scalar(context["declared_object_radius"], "declared_object_radius")
    scores = {}
    for method in ONLINE_METHODS[1:]:
        score = values["score_" + method]
        if score.shape != (32,) or np.iscomplexobj(score) or not np.all(np.isfinite(score)):
            raise ReplayContractError("INVALID_FROZEN_DIRECTION_SCORE:" + str(sid) + ":" + method)
        order = np.argsort(score, kind="stable")
        if method in orders and not np.array_equal(orders[method], order):
            raise ReplayContractError("SCORE_ORDER_CHANGED:" + str(sid) + ":" + method)
        scores[method] = score
    # Original sigma and lambda define exact Stage A observation/QP replay.
    # The cache's whitening/AW are identity-validated rather than renormalized.
    return OnlineCache(sid, AW, background, MaterialChart(volume, len(Q), Q, "a22_fixed_patch32"),
                       anchor, whitening, old_sigma, old_lam, V, scores, radius,
                       manifest_path, cache_path)


def _split(cache: OnlineCache, method: str, order: np.ndarray, k: int,
           seed: tuple[int, int] | None = None) -> Split:
    order = np.asarray(order, dtype=np.int64)
    if not np.array_equal(np.sort(order), np.arange(32)):
        raise ReplayContractError("SPLIT_ORDER_NOT_A_PERMUTATION")
    return Split(cache.scene, method, k, order, cache.common_V[:, order[:k]],
                 cache.common_V[:, order[k:]], seed)


def _freeze_online_splits(root: Path, config: Mapping[str, Any], book: Any):
    """Require all four online receipts before freezing any evaluation split."""
    ids = _scene_ids(config)
    k_values = tuple(int(k) for k in config.get("k_values", (16, 8)))
    if set(k_values) != {8, 16} or len(k_values) != 2 or int(config.get("primary_k", 16)) != 16:
        raise ReplayContractError("FROZEN_K_SET_IS_PRIMARY_16_SECONDARY_8")
    for sid in ids:
        manifest = _json(root / f"results/a22_r1/online/scene_{sid}.json")
        if manifest.get("status") != "COMPLETE":
            raise ReplayContractError("ALL_ONLINE_SCENES_MUST_BE_FROZEN_BEFORE_EVALUATION")
    started = time.perf_counter()
    with book.span("a22_r1_online_split_freeze", split_freezes=1,
                   online_split_constructions=len(ids) * len(ONLINE_METHODS) * len(k_values)):
        caches = {sid: _load_online(root, sid, config) for sid in ids}
        splits: dict[int, list[Split]] = {sid: [] for sid in ids}
        records = []
        for sid, cache in caches.items():
            seed = (int(config.get("random_seed", 20261910)), sid)
            orders = {"RANDOM": np.random.default_rng(np.random.SeedSequence(seed)).permutation(32)}
            orders.update({method: np.argsort(score, kind="stable") for method, score in cache.scores.items()})
            arrays: dict[str, Any] = {"common_V": cache.common_V}
            for method in ONLINE_METHODS:
                arrays["order_" + method] = np.asarray(orders[method], np.int64)
                for k in k_values:
                    selected = _split(cache, method, orders[method], k, seed if method == "RANDOM" else None)
                    splits[sid].append(selected)
                    arrays[f"V_phys_{method}_k{k}"] = selected.phys
                    arrays[f"V_prior_{method}_k{k}"] = selected.prior
                    records.append(dict(scene=sid, method=method, k=k,
                        indices_phys=selected.order[:k].tolist(), indices_prior=selected.order[k:].tolist(),
                        random_seed=selected.seed, score_orientation="ascending" if method != "RANDOM" else None,
                        tie_breaker="common_basis_index", selection_uses_truth=False,
                        selection_uses_full_J=False, online_cache=_rel(cache.cache_path, root),
                        online_manifest=_rel(cache.manifest_path, root)))
            _immutable_npz(root / f"results/a22_r1/online/splits/scene_{sid}.npz", arrays)
        freeze = dict(schema="a22_r1.split_freeze.v1", status="COMPLETE", scenes=list(ids),
            k_values=list(k_values), primary_k=16, common_basis="exact_saved_online_split16_columns",
            random_rule="default_rng(SeedSequence([random_seed,scene_id])).permutation(32); nested k subsets",
            scores=dict(amplitude=0., noise_level=1., intervention="nominal", orientation="ascending",
                        calibration="NONE", tie_breaker="common_basis_index"), definitions=records,
            original_labels_opened=False, original_reconstruction_errors_opened=False,
            full_J_used_online=False)
        freeze_path = root / "results/a22_r1/SPLIT_FREEZE.json"
        _immutable_json(freeze_path, freeze)
    return caches, splits, freeze_path, time.perf_counter() - started


def _freeze_offline_splits(root: Path, config: Mapping[str, Any], book: Any,
                           caches: Mapping[int, OnlineCache], splits: dict[int, list[Split]]) -> tuple[Path | None, float]:
    _require_evaluation_freeze(root)
    if not config.get("include_offline_full_j", True):
        return None, 0.
    started = time.perf_counter()
    records = []
    # This separate diagnostic is frozen before observations/errors are read.
    with _scope(book, "offline_evaluation"), book.span("a22_r1_offline_full_J_split_freeze",
            offline_J_cache_reads=len(caches), offline_split_constructions=2 * len(caches)):
        for sid, cache in caches.items():
            book.check()
            path = root / f"results/a22/stage_a/scene_{sid}/OFFLINE_J_benchmark.npz"
            with np.load(path, allow_pickle=False) as archive:
                JF = np.array(archive["JF"], copy=True)
            if JF.shape != cache.AW.shape or np.iscomplexobj(JF) or not np.all(np.isfinite(JF)):
                raise ReplayContractError("OFFLINE_J_LAYOUT:" + str(sid))
            HF = JF.T @ JF + cache.lam * np.eye(32)
            hF = JF @ la.solve(HF, cache.common_V, assume_a="pos")
            backF = JF.T @ hF - cache.common_V
            score = np.sqrt(np.sum(hF * hF, axis=0)
                            + (cache.declared_object_radius * la.norm(backF, axis=0)) ** 2)
            order = np.argsort(score, kind="stable")
            arrays = {"score": score, "order": np.asarray(order, np.int64), "common_V": cache.common_V}
            for k in config.get("k_values", (16, 8)):
                selected = _split(cache, OFFLINE_METHOD, order, int(k))
                splits[sid].append(selected)
                arrays[f"V_phys_k{k}"], arrays[f"V_prior_k{k}"] = selected.phys, selected.prior
                records.append(dict(scene=sid, method=OFFLINE_METHOD, k=int(k), scope="OFFLINE_ORACLE_DIAGNOSTIC",
                    indices_phys=order[:int(k)].tolist(), indices_prior=order[int(k):].tolist(),
                    source=_rel(path, root), selection_uses_truth=False,
                    selection_uses_full_J=True, amplitude=0., noise_level=1., intervention="nominal",
                    full_scene_lambda=cache.lam, declared_object_radius=cache.declared_object_radius))
            _immutable_npz(root / f"results/a22_r1/offline/scene_{sid}_split.npz", arrays)
        freeze_path = root / "results/a22_r1/OFFLINE_SPLIT_FREEZE.json"
        _immutable_json(freeze_path, dict(schema="a22_r1.offline_split_freeze.v1", status="COMPLETE",
            label="OFFLINE / ORACLE DIAGNOSTIC", deployable=False, definitions=records,
            formula="hF=JF solve(JF.T JF+lambda I,v); score=sqrt(||hF||^2+(radius ||JF.T hF-v||)^2)",
            existing_full_J_only=True, new_Maxwell_actions=0, original_errors_opened=False))
    return freeze_path, time.perf_counter() - started


def _registered_rows(root: Path, original: Mapping[str, Any], ids: tuple[int, ...]) -> list[dict[str, Any]]:
    _require_evaluation_freeze(root)
    path = root / "results/a22/stage_a/direction_metrics.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    keys = [stage_a_case_key(row) for row in rows]
    if len(keys) != len(set(keys)):
        raise ReplayContractError("DUPLICATE_ORIGINAL_CASE_KEYS")
    expected = set()
    for sid, direction, amplitude, intervention, noise in itertools.product(ids,
            range(int(original["finite_screening_directions"])), range(len(original["amplitude_fractions"])),
            original["interventions"], original["noise_levels"]):
        for draw in range(1 if float(noise) == 0 else int(original["noise_draws"])):
            expected.add((sid, direction, amplitude, float(noise), draw, intervention))
    if set(keys) != expected or len(expected) != 2112:
        raise ReplayContractError("ORIGINAL_SCREENING_CASE_GRID_IS_NOT_THE_FROZEN_2112_CASES")
    if any(row.get("status") != "OK" for row in rows):
        raise ReplayContractError("ORIGINAL_TERMINAL_FAILURE_MUST_REMAIN_STATISTICALLY_INELIGIBLE")
    for row in rows:
        seed = [int(original["master_seed"]), int(row["scene_id"]), int(row["direction_id"]),
                int(row["amplitude_level"]), int(row["noise_draw"]), 661]
        if row["noise_seed"] != ":".join(map(str, seed)):
            raise ReplayContractError("ORIGINAL_NOISE_SEED_MISMATCH")
    return sorted(rows, key=stage_a_case_key)


def _load_label(root: Path, row: Mapping[str, Any], cache: OnlineCache, book: Any) -> Label:
    _require_evaluation_freeze(root)
    path = root / (f"results/a22/stage_a/scene_{cache.scene}/"
                   f"OFFLINE_label_d{int(row['direction_id'])}_a{int(row['amplitude_level'])}.npz")
    with _scope(book, "offline_evaluation"), book.span("a22_r1_cached_label_read", offline_label_cache_reads=1):
        with np.load(path, allow_pickle=False) as archive:
            clean, truth, direction = (np.array(archive[name], copy=True)
                                       for name in ("clean_data", "coefficients", "direction"))
            amplitude = float(archive["amplitude"])
            order = archive["source_order"]
            if not np.array_equal(order, np.arange(6)):
                raise ReplayContractError("LABEL_SOURCE_ORDER_CHANGED")
            if "cache_schema" in archive.files:
                _relative_close(archive["chart_Q"], cache.chart.Q, 1e-12, "label.chart_Q")
                _relative_close(archive["anchor_material"], cache.anchor, 1e-12, "label.anchor_material")
    if (clean.shape != (6, 128) or not np.iscomplexobj(clean) or not np.all(np.isfinite(clean))
            or truth.shape != (32,) or np.iscomplexobj(truth) or not np.all(np.isfinite(truth))
            or direction.shape != (32,) or np.iscomplexobj(direction) or not np.all(np.isfinite(direction))):
        raise ReplayContractError("CACHED_LABEL_LAYOUT")
    if amplitude != float(row["amplitude"]):
        raise ReplayContractError("CACHED_LABEL_AMPLITUDE_CHANGED")
    return Label(clean, truth, direction, amplitude, path)


def _data(row: Mapping[str, Any], label: Label, cache: OnlineCache, original: Mapping[str, Any]) -> np.ndarray:
    intervention = row["intervention"]
    if intervention == "nominal":
        clean = label.clean
    elif intervention == "source_amplitude_5pct_receiver_gain_3pct":
        clean = _calibrate_data(label.clean)[0]
    else:
        raise ReplayContractError("UNREGISTERED_CALIBRATION_INTERVENTION")
    seed = [int(original["master_seed"]), cache.scene, int(row["direction_id"]),
            int(row["amplitude_level"]), int(row["noise_draw"]), 661]
    rng = np.random.default_rng(np.random.SeedSequence(seed))
    noise = float(row["noise_level"]) * cache.sigma / np.sqrt(2.) * (
        rng.normal(size=clean.shape) + 1j * rng.normal(size=clean.shape))
    return cache.whitening * pack(clean + noise - cache.background)


def _identity(row: Mapping[str, Any]) -> dict[str, Any]:
    return dict(scene=int(row["scene_id"]), scene_id=int(row["scene_id"]), family=row["family"],
        direction=int(row["direction_id"]), direction_id=int(row["direction_id"]),
        amplitude=int(row["amplitude_level"]), amplitude_level=int(row["amplitude_level"]),
        physical_amplitude=float(row["amplitude"]), noise=float(row["noise_level"]),
        noise_level=float(row["noise_level"]), noise_draw=int(row["noise_draw"]),
        intervention=row["intervention"], noise_seed=row["noise_seed"],
        candidate_index=int(row["candidate_index"]), historical_exposed=True,
        case_key="|".join(map(str, stage_a_case_key(row))))


def _failure(root: Path, record: Mapping[str, Any], exc: BaseException) -> None:
    _append(root / "results/a22_r1/FAILURE_LEDGER.jsonl", dict(record,
        status="INVALID_QP" if isinstance(exc, QPFailure) else "FAILED",
        error_type=type(exc).__name__, error=str(exc), qp_audit=getattr(exc, "result", None),
        clipping=False, fallback=False, terminal=True))


def _solve(A: np.ndarray, d: np.ndarray, cache: OnlineCache, original: Mapping[str, Any],
           book: Any, *, basis: np.ndarray | None = None):
    name = "a22_r1_common_32D_solve" if basis is None else "a22_r1_restricted_physics_solve"
    started, cpu = time.perf_counter(), time.process_time()
    counters = {"cached_small_solves": 1,
                "common_32D_solves" if basis is None else "restricted_physics_solves": 1}
    with _scope(book, "offline_evaluation"), book.span(name, **counters):
        solution, qp, normal = constrained_material_solve(A, d, cache.chart, cache.anchor,
            original, book, basis=basis, lam=cache.lam)
    return solution, qp, normal, time.perf_counter() - started, time.process_time() - cpu


def _reproduce(solution: np.ndarray, label: Label, row: Mapping[str, Any], scale: float):
    error = solution - label.truth
    actual = dict(signed_target_error=float(label.direction @ error),
                  material_error=float(la.norm(error)), raw_target_coefficient=float(label.direction @ label.truth),
                  coefficient_error=float(abs(label.direction @ error)))
    original = dict(signed_target_error=float(row["coefficient_signed_error"]),
                    material_error=float(row["material_error"]), raw_target_coefficient=float(row["raw_target_coefficient"]),
                    coefficient_error=float(row["coefficient_error"]))
    tolerance = scale * max(1., abs(original["material_error"]))
    differences = {key: abs(actual[key] - original[key]) for key in actual}
    flags = {key: value <= tolerance for key, value in differences.items()}
    return actual, dict(status="MATCH" if all(flags.values()) else "MISMATCH",
        tolerance=tolerance, tolerance_rule="reproduction_atol_scale * max(1,abs(saved material_error))",
        actual=actual, saved=original, absolute_differences=differences, quantity_matches=flags)


def _metric_record(row: Mapping[str, Any], selected: Split, test: str,
                   solution: np.ndarray, truth: np.ndarray, config: Mapping[str, Any]):
    record = dict(_identity(row), method=selected.method, k=selected.k, test=test, status="OK",
        split_scope="OFFLINE_ORACLE_DIAGNOSTIC" if selected.method == OFFLINE_METHOD else "ONLINE_LEGAL",
        chart_dimension=32, actual_current_rank=32, full_scene_lambda=True,
        random_seed=selected.seed, split_indices_phys=selected.order[:selected.k].tolist(),
        split_indices_prior=selected.order[selected.k:].tolist())
    record.update(subspace_metrics(solution, truth, selected.phys, selected.prior,
            norm_floor=float(config.get("norm_floor", 1e-6)),
            orthonormal_atol=float(config.get("identity_rtol", 1e-9))))
    return record


def _expected_conditions(original: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [dict(direction=direction, amplitude=amplitude, noise=float(noise), intervention=intervention)
            for direction, amplitude, noise, intervention in itertools.product(
                range(int(original["finite_screening_directions"])), range(len(original["amplitude_fractions"])),
                original["noise_levels"], original["interventions"])]


def _cached_quadratic_validation(record, row, label, cache, original, d, geometry):
    """Audit a saved original-solver point, without solving another image.

    The normal is saved from the original solve, not set to minus its gradient.
    Cone membership uses exact duplicate constraint rows only; no objective or
    tolerance changes. This path requires an explicit pre-outcome addendum.
    """
    if (record.get('case_key') != _identity(row)['case_key'] or record.get('status') != 'OK'
            or record.get('lambda_value') != cache.lam):
        raise ReplayContractError('CACHED_COMMON_CASE_OR_LAMBDA_CHANGED')
    x, truth, normal = (np.asarray(record[name], float) for name in ('x_hat','x_true','material_normal'))
    if any(a.shape != (32,) or not np.all(np.isfinite(a)) for a in (x, truth, normal)):
        raise ReplayContractError('CACHED_COMMON_VECTOR_INVALID')
    if not np.array_equal(truth, label.truth):
        raise ReplayContractError('CACHED_COMMON_TRUTH_COEFFICIENTS_CHANGED')
    H, C, lower = geometry
    g = -cache.AW.T @ d
    slack = C @ x-lower
    feasibility = max(0., float(-np.min(slack)))
    gradient = H @ x+g
    relative = float(la.norm(gradient+normal))/max(float(la.norm(g)), 1e-12)
    ftol, ktol = float(original.get('feasibility_tolerance',1e-8)), float(original.get('qp_kkt_rtol',1e-8))
    active = np.flatnonzero(slack <= ftol)
    if len(active):
        mu, cone_error = nnls(C[active].T, -normal, maxiter=max(200,10*len(active)))
        complementarity = float(np.max(abs(mu*slack[active])))
    else:
        cone_error, complementarity = float(la.norm(normal)), 0.
    cone_relative = float(cone_error)/max(1.,float(la.norm(normal)))
    quadratic = float(.5*x@H@x+g@x)
    saved = float(record['qp']['quadratic_value'])
    qdiff = abs(quadratic-saved)/max(1.,abs(saved))
    valid = (feasibility <= ftol and relative <= ktol
             and float(record['qp']['kkt_relative']) <= ktol
             and float(record['qp']['feasibility_violation']) <= ftol
             and cone_relative <= 1e-9 and qdiff <= 1e-9)
    audit = dict(status='VALID' if valid else 'INVALID', feasibility_violation=feasibility,
                 kkt_relative=relative, normal_cone_relative=cone_relative,
                 complementarity=complementarity, quadratic=quadratic,
                 saved_quadratic=saved, quadratic_relative_difference=qdiff,
                 normal_source='original_saved_solver_normal_not_minus_gradient',
                 unchanged_original_KKT_tolerance=ktol, unchanged_feasibility_tolerance=ftol)
    if not valid:
        error=ReplayContractError('CACHED_COMMON_FROZEN_QP_VALIDATION_FAILED')
        error.result=audit
        raise error
    return x, audit


def run_replay(root: str | Path, config: Mapping[str, Any], book: Any, *, cached_common=None) -> dict[str, Any]:
    """Execute the registered cache-only tests after all online freezes exist.

    Only a successful immutable REPLAY_SUMMARY can be reused automatically.
    Failed attempts retain full per-case JSONL, failure ledgers and any saved
    vectors. An exact common-reconstruction reproduction gate precedes Test B.
    The parent owns scene aggregation, interpretation and screening gates.
    """
    root = Path(root).resolve()
    started, cpu = time.perf_counter(), time.process_time()
    try:
        original = _json(root / "configs/a22.json")
        ids = _scene_ids(config)
        if original["master_seed"] != 20261007 or tuple(original["screening_scenes"]) != SCENES:
            raise ReplayContractError("ORIGINAL_A22_SCREENING_PROTOCOL_CHANGED")
        if config.get("small_solve_lambda", "original_full_AW_lambda_for_all_restrictions") != "original_full_AW_lambda_for_all_restrictions":
            raise ReplayContractError("RESTRICTED_REGULARIZATION_MUST_USE_ORIGINAL_FULL_SCENE_LAMBDA")
        caches, splits, online_freeze, split_seconds = _freeze_online_splits(root, config, book)
        offline_freeze, offline_seconds = _freeze_offline_splits(root, config, book, caches, splits)
        summary_path = root / "results/a22_r1/REPLAY_SUMMARY.json"
        if summary_path.exists():
            saved = _json(summary_path)
            if saved.get("status") != "COMPLETE" or saved.get("config") != plain(dict(config)):
                raise ReplayContractError("EXISTING_REPLAY_SUMMARY_HAS_DIFFERENT_OR_INCOMPLETE_CONTRACT")
            if saved.get('common_reproduction',{}).get('common_source') != cached_common:
                raise ReplayContractError('EXISTING_REPLAY_HAS_DIFFERENT_COMMON_ACCEPTANCE_CONTRACT')
            return dict(saved, cached_complete_replay=True)
    except BaseException as exc:
        _failure(root, dict(phase="PRE_REPLAY_CONTRACT", common_cases_attempted=0,
                           Test_B_started=False, gate_decision="INCOMPLETE"), exc)
        raise
    attempt_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:12]
    out = root / "results/a22_r1/replay" / attempt_id
    out.mkdir(parents=True, exist_ok=False)
    _immutable_json(out / "REPLAY_CONTRACT.json", dict(config=dict(config), original_config=original,
        online_split_freeze=_rel(online_freeze, root),
        offline_split_freeze=_rel(offline_freeze, root) if offline_freeze else None,
        no_new_Maxwell_actions=True, no_new_labels=True, full_scene_lambda_for_every_solve=True,
        one_common_32D_solution_per_case=True, split_freeze_before_original_errors=True))
    full_records: list[dict[str, Any]] = []
    metric_records: list[dict[str, Any]] = []
    labels: dict[tuple[int, int, int], Label] = {}
    estimates: dict[tuple[Any, ...], np.ndarray] = {}
    qp_full: dict[tuple[Any, ...], dict[str, Any]] = {}
    restricted_rows: dict[tuple[int, str, int], list[dict[str, Any]]] = {}
    rows: list[dict[str, Any]] = []
    try:
        # Both online and offline split manifests now exist. Original errors
        # below are used exclusively for reproducibility, never for rankings.
        rows = _registered_rows(root, original, ids)
        source_records, geometries = {}, {}
        if cached_common is not None:
            addendum = _json(root/'configs/a22_r1_cached_qp_addendum.json')
            if (not addendum.get('registered_before_split_outcome_metrics')
                    or addendum['common_cases'] != str(cached_common)
                    or addendum['historical_scalar_reproduction'] != 'FAILED_RETAINED'
                    or any(addendum.get(name) is not False for name in
                           ('solver_tolerance_change','score_change','physics_change'))):
                raise ReplayContractError('CACHED_COMMON_ADDENDUM_NOT_FROZEN')
            with _scope(book,'offline_evaluation'), book.span('r1_cached_common_archive_read',cached_common_archive_reads=1):
                source_path=root/cached_common
                stream=(source_path.open(encoding='utf-8') if source_path.exists()
                        else gzip.open(str(source_path)+'.gz','rt',encoding='utf-8'))
                with stream:
                    source_rows=[json.loads(line) for line in stream if line.strip()]
            source_records={record['case_key']: record for record in source_rows}
            if len(source_rows)!=2112 or len(source_records)!=2112:
                raise ReplayContractError('CACHED_COMMON_ARCHIVE_MUST_HAVE_ALL_2112_UNIQUE_CASES')
            for sid, cache in caches.items():
                C, lower=constraint_map(cache.chart,cache.anchor)
                _, first=np.unique(np.column_stack((C,lower)),axis=0,return_index=True)
                first=np.sort(first)
                H=cache.AW.T@cache.AW+cache.lam*np.eye(32)
                if la.eigvalsh(H)[0] <= 0:
                    raise ReplayContractError('CACHED_COMMON_HESSIAN_NOT_SPD')
                geometries[sid]=(H,C[first],lower[first])
            _immutable_json(out/'EXPLICIT_CACHED_QP_ADDENDUM.json',dict(addendum,
                source_common_cases=cached_common, no_common_QP_rerun=True,
                historical_scalar_gate='FAILED_RETAINED', validation='original_frozen_QP_contract'))
        for row in rows:
            book.check()
            sid = int(row["scene_id"])
            cache = caches[sid]
            label_key = (sid, int(row["direction_id"]), int(row["amplitude_level"]))
            if label_key not in labels:
                labels[label_key] = _load_label(root, row, cache, book)
            label = labels[label_key]
            d = _data(row, label, cache, original)
            record = dict(_identity(row), test="COMMON_32D_REPRODUCTION", method="COMMON_32D",
                          k=32, lambda_value=cache.lam, x_true=label.truth.tolist())
            try:
                if cached_common is None:
                    solution, qp, normal, wall, solve_cpu = _solve(cache.AW, d, cache, original, book)
                else:
                    start, start_cpu=time.perf_counter(),time.process_time()
                    with _scope(book,'offline_evaluation'),book.span('r1_saved_common_QP_validation',cached_common_validations=1):
                        source=source_records[record['case_key']]
                        solution, audit=_cached_quadratic_validation(source,row,label,cache,original,d,geometries[sid])
                    qp, normal=source['qp'],np.asarray(source['material_normal'],float)
                    wall, solve_cpu=time.perf_counter()-start,time.process_time()-start_cpu
                    record.update(cached_QP_validation=audit,common_solution_source=cached_common,
                                  new_common_QP_solve=False)
                actual, reproduction = _reproduce(solution, label, row,
                    float(config.get("reproduction_atol_scale", config.get("reproduction_atol", 1e-8))))
                record.update(status="OK", x_hat=solution.tolist(), qp=qp, material_normal=normal.tolist(),
                    solve_wall_seconds=wall, solve_process_cpu_seconds=solve_cpu,
                    data_residual=float(la.norm(cache.AW @ solution - d)),
                    reproduction=reproduction, **actual)
                key = stage_a_case_key(row)
                estimates[key], qp_full[key] = solution, qp
                if reproduction["status"] != "MATCH" and cached_common is None:
                    _append(root / "results/a22_r1/FAILURE_LEDGER.jsonl", dict(_identity(row),
                        status="REPRODUCTION_MISMATCH", terminal=True, method="COMMON_32D", test="REPRODUCTION",
                        reproduction=reproduction, no_Test_B_before_global_reproduction=True))
            except QPFailure as exc:
                record.update(status="INVALID_QP", x_hat=None, qp=getattr(exc, "result", None),
                              reproduction=dict(status="INVALID_QP"), error=str(exc))
                _failure(root, record, exc)
            full_records.append(record)
            _append(out / "COMMON_32D_CASES.jsonl", record)
            book.check()
        _csv(out / "COMMON_32D_CASES.csv", full_records)
        keys = np.asarray([record["case_key"] for record in full_records])
        full_status = np.asarray([record["status"] for record in full_records])
        _immutable_npz(out / "COMMON_32D_SOLUTIONS.npz", dict(case_keys=keys, status=full_status,
            x_hat=np.asarray([record["x_hat"] if record["x_hat"] is not None else np.full(32, np.nan)
                              for record in full_records], dtype=np.float64),
            x_true=np.asarray([record["x_true"] for record in full_records], dtype=np.float64),
            qp_json=np.asarray([_encoded(record["qp"]) for record in full_records]),
            reproduction_json=np.asarray([_encoded(record["reproduction"]) for record in full_records]),
            scene=np.asarray([record["scene"] for record in full_records], dtype=np.int64),
            lambda_value=np.asarray([record["lambda_value"] for record in full_records], dtype=np.float64),
            full_solution_vectors=np.asarray("RECORDED_IN_FROZEN_32D_MATERIAL_CHART")))
        reproduction_counts = Counter(record["reproduction"]["status"] for record in full_records)
        reproduction_summary = dict(schema="a22_r1.common_reproduction.v1",
            status="MATCH" if reproduction_counts == {"MATCH": 2112} else "FAILED",
            registered_cases=2112, attempted_cases=len(full_records), counts=dict(reproduction_counts),
            absolute_tolerance_scale=float(config.get("reproduction_atol_scale", 1e-8)),
            max_absolute_differences={quantity: max((record["reproduction"].get("absolute_differences", {}).get(quantity, 0.)
                for record in full_records), default=None) for quantity in
                ("signed_target_error", "material_error", "raw_target_coefficient", "coefficient_error")},
            full_solution_archive=_rel(out / "COMMON_32D_SOLUTIONS.npz", root),
            Test_B_started=False, split_tuning=False)
        if cached_common is not None:
            reproduction_summary.update(historical_scalar_gate='FAILED_RETAINED',
                explicit_pre_outcome_addendum='REPRODUCTION_CONFLICT_ADDENDUM.md',
                cached_QP_contract='ALL_2112_VALID', new_common_QP_solves=0,
                common_source=cached_common,
                validation_maxima={name:max(value['cached_QP_validation'][name] for value in full_records)
                    for name in ('kkt_relative','feasibility_violation','normal_cone_relative','quadratic_relative_difference')})
        _immutable_json(out / "COMMON_REPRODUCTION.json", reproduction_summary)
        if reproduction_summary["status"] != "MATCH" and cached_common is None:
            raise ReplayReproductionError(dict(reproduction_summary, attempt_path=_rel(out, root)))
        # Test A and B see the same selected bases, observations and true chart
        # coefficients. No full 32D solve is repeated in this second pass.
        for row in rows:
            book.check()
            cache = caches[int(row["scene_id"])]
            key = stage_a_case_key(row)
            label = labels[(cache.scene, int(row["direction_id"]), int(row["amplitude_level"]))]
            full = estimates[key]
            d = _data(row, label, cache, original)
            for selected in splits[cache.scene]:
                book.check()
                common = _metric_record(row, selected, "A", full, label.truth, config)
                common.update(lambda_value=cache.lam, qp=qp_full[key],
                              reproduction_status='MATCH' if cached_common is None else 'STRICT_SCALAR_FAIL_FROZEN_QP_VALID',
                              common_full_solution_shared=True, prior_filled_by_NN=False)
                metric_records.append(common)
                _append(out / "PER_CASE_SPLIT_METRICS.jsonl", common)
                restricted = dict(_identity(row), method=selected.method, k=selected.k, test="B",
                    split_scope="OFFLINE_ORACLE_DIAGNOSTIC" if selected.method == OFFLINE_METHOD else "ONLINE_LEGAL",
                    lambda_value=cache.lam, prior_component="ZERO_BACKGROUND", correction_events=0,
                    full_projection_nrmse_phys=common["nrmse_phys"], random_seed=selected.seed,
                    split_indices_phys=selected.order[:selected.k].tolist(),
                    split_indices_prior=selected.order[selected.k:].tolist())
                vector = dict(case_key=common["case_key"], x_true=label.truth.tolist(), x_hat=None)
                try:
                    estimate, qp, normal, wall, solve_cpu = _solve(cache.AW @ selected.phys, d,
                        cache, original, book, basis=selected.phys)
                    restricted.update(_metric_record(row, selected, "B", estimate, label.truth, config))
                    restricted.update(qp=qp, material_normal=normal.tolist(),
                        solve_wall_seconds=wall, solve_process_cpu_seconds=solve_cpu,
                        data_residual=float(la.norm(cache.AW @ estimate - d)),
                        prior_coefficient_norm=float(la.norm(selected.prior.T @ estimate)),
                        restricted_over_common_nrmse_phys=(restricted["nrmse_phys"] / common["nrmse_phys"]
                                                         if common["nrmse_phys"] > 0 else None))
                    vector.update(status="OK", x_hat=estimate.tolist(), a_phys=(selected.phys.T @ estimate).tolist(),
                                  qp=qp, material_normal=normal.tolist())
                except QPFailure as exc:
                    restricted.update(status="INVALID_QP", qp=getattr(exc, "result", None), error=str(exc))
                    vector.update(status="INVALID_QP", a_phys=None, qp=getattr(exc, "result", None))
                    _failure(root, restricted, exc)
                restricted_rows.setdefault((cache.scene, selected.method, selected.k), []).append(vector)
                _append(out / "RESTRICTED_SOLUTION_VECTORS.jsonl", dict(_identity(row), method=selected.method,
                    k=selected.k, test="B", **{name: value for name, value in vector.items() if name != "case_key"}))
                metric_records.append(restricted)
                _append(out / "PER_CASE_SPLIT_METRICS.jsonl", restricted)
                book.check()
        _csv(out / "PER_CASE_SPLIT_METRICS.csv", metric_records)
        for (sid, method, k), vectors in restricted_rows.items():
            _immutable_npz(out / f"scene_{sid}_{method}_k{k}_RESTRICTED.npz", dict(
                case_keys=np.asarray([value["case_key"] for value in vectors]),
                status=np.asarray([value["status"] for value in vectors]),
                x_hat=np.asarray([value["x_hat"] if value["x_hat"] is not None else np.full(32, np.nan)
                                  for value in vectors], dtype=np.float64),
                x_true=np.asarray([value["x_true"] for value in vectors], dtype=np.float64),
                a_phys=np.asarray([value["a_phys"] if value["a_phys"] is not None else np.full(k, np.nan)
                                   for value in vectors], dtype=np.float64),
                qp_json=np.asarray([_encoded(value["qp"]) for value in vectors]),
                split_order=np.asarray(next(selected.order for selected in splits[sid]
                                             if selected.method == method and selected.k == k), dtype=np.int64),
                random_seed=np.asarray([int(config.get("random_seed", 20261910)), sid]
                                       if method == "RANDOM" else [-1, -1], dtype=np.int64),
                k=np.asarray(k), lambda_value=np.asarray(caches[sid].lam), prior_component=np.asarray("ZERO_BACKGROUND")))
        expected_groups = [dict(scene=sid, method=selected.method, k=selected.k, test=test)
                           for sid in ids for selected in splits[sid] for test in ("A", "B")]
        invalid_restricted = sum(record["test"] == "B" and record["status"] != "OK" for record in metric_records)
        summary = dict(schema="a22_r1.replay_summary.v1", status="COMPLETE", config=dict(config),
            run_id=attempt_id, attempt_path=_rel(out, root), scenes=list(ids),
            common_32D_solves=len(full_records), common_reproduction=reproduction_summary,
            new_common_32D_solves=len(full_records) if cached_common is None else 0,
            cached_common_32D_reuses=len(full_records) if cached_common is not None else 0,
            restricted_physics_solves=sum(len(values) for values in restricted_rows.values()),
            invalid_restricted_QPs=invalid_restricted, split_metric_rows=len(metric_records),
            metric_rows_per_case=2 * len(splits[ids[0]]), expected_conditions=_expected_conditions(original),
            expected_groups=expected_groups, case_metric_path=_rel(out / "PER_CASE_SPLIT_METRICS.jsonl", root),
            case_metric_csv=_rel(out / "PER_CASE_SPLIT_METRICS.csv", root),
            full_solution_path=_rel(out / "COMMON_32D_SOLUTIONS.npz", root),
            restricted_vector_jsonl=_rel(out / "RESTRICTED_SOLUTION_VECTORS.jsonl", root),
            online_split_freeze=_rel(online_freeze, root),
            offline_split_freeze=_rel(offline_freeze, root) if offline_freeze else None,
            costs=dict(online_split_wall_seconds=split_seconds, offline_split_wall_seconds=offline_seconds,
                       cached_replay_wall_seconds=time.perf_counter() - started,
                       cached_replay_process_cpu_seconds=time.process_time() - cpu,
                       construction_cost_source="historical A22 ledger; no OPM rebuild inside replay"),
            new_Maxwell_actions=0, new_fullwave_labels=0, NN="NOT_RUN", gate_decision="PARENT_REVIEW_REQUIRED")
        _immutable_json(out / "REPLAY_SUMMARY.json", summary)
        _immutable_json(summary_path, summary)
        return summary
    except BaseException as exc:
        failure = dict(status="FAILED", run_id=attempt_id, attempt_path=_rel(out, root),
            common_cases_attempted=len(full_records), split_metric_rows_recorded=len(metric_records),
            error_type=type(exc).__name__, error=str(exc),
            replay_wall_seconds=time.perf_counter() - started,
            replay_process_cpu_seconds=time.process_time() - cpu,
            terminal=True, new_Maxwell_actions=0, new_fullwave_labels=0, gate_decision="INCOMPLETE")
        _immutable_json(out / "ATTEMPT_FAILURE.json", failure)
        _failure(root, failure, exc)
        raise
