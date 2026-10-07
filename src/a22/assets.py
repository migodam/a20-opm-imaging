"""Selected A17 observations and geometry-only A22 material coordinates.

No loader constructs Maxwell operators.  Online reads request individual NPZ
members, never ``dict(np.load(...))``; truth has a separate offline capability.
New-scene recipes are dormant until the caller supplies both required flags.
"""
from __future__ import annotations

from contextlib import nullcontext
from dataclasses import dataclass
from pathlib import Path
import ast
import json
from typing import Any, Mapping

import numpy as np

from a20.backend import ForbiddenAccess, MaterialChart, Problem


ROOT = Path(__file__).resolve().parents[2]
SCREENING_IDS = (2001, 2003, 2014, 2009)
COARSE_INDICES = tuple(range(8)) + tuple(range(16, 24))
_FORBIDDEN = frozenset(("truth", "teacher", "labels", "full_J", "full_H",
                        "reference_step", "oracle", "held_truth"))

# Acquisition constants from the original A17 input scene manifests.  The
# component geometries and old material chart are deliberately absent.
KNOWN_GEOMETRY = {
    2001: {"family": "gaussian", "rotation": 3.7107292183472715,
           "source": "EXCHANGE_R1/inputs/object_2001/common_data.npz"},
    2003: {"family": "gaussian", "rotation": 1.7496260542933944,
           "source": "CLOSURE_R1/inputs/object_2003/common_data.npz"},
    2014: {"family": "asymmetric", "rotation": 2.1650255968898984,
           "source": "EXCHANGE_R1/inputs/object_2014/common_data.npz"},
    2009: {"family": "shell", "rotation": 2.560051713861531,
           "source": "CLOSURE_R1/inputs/object_2009/common_data.npz"},
}
for _record in KNOWN_GEOMETRY.values():
    _record.update(n=12, truth_n=14, edge=1.5, wavenumber=2.,
                   background=[.1, .04], init=[.1, .04], partial=False,
                   source_split="validation", receiver_count=64)


def _readonly(value, dtype=None):
    result = np.array(value, dtype=dtype, copy=True)
    result.flags.writeable = False
    return result


@dataclass(frozen=True, slots=True)
class OnlineScene:
    scene_id: int
    family: str
    problem: Problem
    geometry: Mapping[str, Any]
    provenance: Mapping[str, Any]
    coarse_indices: tuple[int, ...] = COARSE_INDICES

    @property
    def points(self):
        return self.problem.points

    @property
    def data(self):
        return self.problem.data

    @property
    def chart(self):
        return self.problem.chart

    def __getattr__(self, name):
        if name in _FORBIDDEN:
            raise ForbiddenAccess("OFFLINE_FIELD_IN_A22_ONLINE_SCENE:" + name)
        raise AttributeError(name)


@dataclass(frozen=True, slots=True)
class OfflineScene:
    """Explicit evaluator-only labels; never an argument to online builders."""
    scene_id: int
    truth: np.ndarray
    provenance: Mapping[str, Any]


def load_config(path=None):
    return json.loads(Path(path or ROOT / "configs/a22.json").read_text(encoding="utf-8"))


def _span(book, label, **counts):
    return nullcontext() if book is None else book.span(label, **counts)


def _source(scene_id, config, *, stage_a_signal=False, explicit_authorization=False):
    sid = int(scene_id)
    defaults = KNOWN_GEOMETRY.get(sid)
    declared = config.get("scene_sources", {}).get(str(sid), {})
    if defaults is None:
        if not stage_a_signal or not explicit_authorization:
            raise ForbiddenAccess("A22_NONSCREENING_ASSET_REQUIRES_EXPLICIT_STAGE_A_SIGNAL")
        if not declared:
            raise FileNotFoundError("No declared A22 source and public geometry for scene " + str(sid))
        record = dict(declared)
    else:
        record = dict(defaults)
        record.update(declared)
    allowed = {"family", "rotation", "source", "n", "truth_n", "edge", "wavenumber",
               "background", "init", "partial", "source_split", "receiver_count"}
    if set(record) - allowed:
        raise ForbiddenAccess("UNREGISTERED_OR_OFFLINE_GEOMETRY_FIELDS")
    asset_root = Path(config["paths"]["asset_root"]).resolve()
    path = (asset_root / record.pop("source")).resolve()
    if not path.is_relative_to(asset_root):
        raise ForbiddenAccess("A22_ASSET_PATH_OUTSIDE_DECLARED_ROOT")
    if not path.is_file():
        raise FileNotFoundError(path)
    return path, record


def fixed_patch_chart(points, volume):
    """Eight octants plus eight centered x-sign details, independent of data.

    H is Euclidean-orthonormal; Q=H/sqrt(v), so v Q.T Q=I.  Real material
    coordinates are [16 real coefficients, 16 imaginary coefficients].
    """
    points = np.asarray(points, dtype=np.float64)
    if points.ndim != 2 or points.shape[1] != 3 or not np.all(np.isfinite(points)):
        raise ValueError("FINITE_3D_MESH_REQUIRED")
    volume = float(volume)
    if not np.isfinite(volume) or volume <= 0:
        raise ValueError("POSITIVE_CELL_VOLUME_REQUIRED")
    center = .5 * (points.min(axis=0) + points.max(axis=0))
    bits = points >= center
    octants = 4 * bits[:, 0].astype(int) + 2 * bits[:, 1].astype(int) + bits[:, 2].astype(int)
    H = np.zeros((len(points), 16), dtype=np.float64)
    counts = []
    for octant in range(8):
        index = np.flatnonzero(octants == octant)
        if len(index) < 2:
            raise ValueError("PATCH_DETAIL_REQUIRES_TWO_CELLS_IN_EVERY_OCTANT")
        H[index, octant] = 1. / np.sqrt(len(index))
        xs = points[index, 0]
        split = .5 * (float(xs.min()) + float(xs.max()))
        detail = np.where(xs >= split, 1., -1.)
        detail -= detail.mean()
        length = float(np.linalg.norm(detail))
        if length == 0:
            raise ValueError("PATCH_X_DETAIL_IS_RANK_DEFICIENT")
        H[index, 8 + octant] = detail / length
        counts.append(len(index))
    metric_error = float(np.linalg.norm(H.T @ H - np.eye(16)))
    if metric_error > 1e-10:
        raise ValueError("FIXED_PATCH_MATERIAL_METRIC_MISMATCH")
    Q = _readonly(H / np.sqrt(volume))
    chart = MaterialChart(volume, len(points), Q, "a22_fixed_patch32")
    return chart, {"basis_source": "known_mesh_only", "spatial_columns": 16,
        "real_dimension": 32, "order": "octants0:8,x_details8:16; real_then_imag",
        "octant_cell_counts": counts, "physical_metric": "volume * Q.T @ Q = I",
        "physical_metric_error": metric_error, "coarse_indices": list(COARSE_INDICES),
        "truth_fitting": False, "data_fitting": False}


def acquisition_geometry(geometry):
    """Exact A17 scenes.acquisition / A10 balanced geometry, without imports."""
    count = int(geometry.get("receiver_count", 64))
    angle = float(geometry["rotation"])
    z = 1. - 2. * (np.arange(count) + .5) / count
    phase = np.arange(count) * np.pi * (3. - np.sqrt(5.))
    rr = np.column_stack((np.sqrt(1. - z*z) * np.cos(phase),
                          np.sqrt(1. - z*z) * np.sin(phase), z))
    co, si = np.cos(angle), np.sin(angle)
    rotation = np.array([[co, -si, 0.], [si, co, 0.], [0., 0., 1.]])
    # A9 acquisition rotates receiver rows by R; A16 scenes rotates source
    # rows by R.T.  Preserve this distinction and original six-source order.
    rr = rr @ rotation
    b1 = np.cross(rr, [0., 0., 1.])
    b1 /= np.linalg.norm(b1, axis=1)[:, None]
    obs = np.stack((b1, np.cross(rr, b1)), axis=1)
    dirs, pols = [], []
    for i in range(3):
        for j in range(3):
            if i != j:
                dirs.append(np.eye(3)[i])
                pols.append(np.eye(3)[j])
    receivers = 5. * rr
    if bool(geometry.get("partial", False)):
        keep = receivers[:, 0] >= 0
        receivers, obs = receivers[keep], obs[keep]
    return (np.asarray(dirs) @ rotation.T, np.asarray(pols) @ rotation.T,
            receivers, obs)


def load_online_scene(scene_id, config=None, book=None, *, stage_a_signal=False,
                      explicit_authorization=False):
    config = load_config() if config is None else config
    path, geometry = _source(scene_id, config, stage_a_signal=stage_a_signal,
                             explicit_authorization=explicit_authorization)
    with _span(book, "a22_selected_online_asset_read", online_asset_reads=1):
        with np.load(path, allow_pickle=False) as archive:
            required = ("points", "data0", "init")
            if any(key not in archive.files for key in required):
                raise ValueError("A17_COMMON_DATA_MISSING_ONLINE_MEMBER")
            # Do not touch truth, held_truth, scale, scene_json or old tangent Q.
            arrays = {key: archive[key].copy() for key in required}
    points = arrays["points"]
    data = arrays["data0"]
    initial = arrays["init"]
    if any(not np.all(np.isfinite(v)) for v in (points, data, initial)):
        raise ValueError("NONFINITE_ONLINE_ASSET")
    expected_background = complex(*config["background"])
    source_background = complex(*geometry["background"])
    if (expected_background != source_background or complex(*geometry["init"]) != source_background
            or initial.shape != (len(points),)
            or np.max(np.abs(initial - source_background)) > 1e-14):
        raise ValueError("DECLARED_BACKGROUND_DISAGREES_WITH_ORIGINAL_GENERATIVE_SOURCE")
    n = int(geometry["n"])
    if points.shape != (n**3, 3):
        raise ValueError("KNOWN_MESH_SHAPE_MISMATCH")
    volume = (float(geometry["edge"]) / n)**3
    with _span(book, "a22_known_geometry_patch_chart", material_basis_builds=1):
        chart, basis_provenance = fixed_patch_chart(points, volume)
        dirs, pols, receivers, obs = acquisition_geometry(geometry)
    if data.shape != (6, 2 * len(receivers)):
        raise ValueError("SIX_SOURCE_RECEIVER_LAYOUT_MISMATCH")
    problem = Problem(int(scene_id), _readonly(points, float), volume, _readonly(data, complex),
                      1., _readonly(initial, complex), chart, _readonly(dirs, float),
                      _readonly(pols, complex), _readonly(receivers, float),
                      _readonly(obs, complex), float(geometry["wavenumber"]))
    provenance = {"source_path": str(path), "selected_online_members": ["points", "data0", "init"],
        "offline_members_loaded": [], "old_material_chart_loaded": False,
        "old_objective_scale_loaded": False, "source_background_verified": True,
        "source_geometry_origin": "A17 frozen input scene manifests, acquisition constants only",
        "acquisition_origin": "A16 scenes.acquisition + A10 balanced + A9 acquisition",
        "source_order": "for i in range(3), for j in range(3), i != j",
        "data_order": "illumination-major; each source real channels then imaginary channels",
        "source_count": 6, "complex_channels_per_source": data.shape[1],
        "historical_exposure": "historically_exposed_feasibility",
        "material_basis": basis_provenance, "new_integrity_hash_checks": 0}
    return OnlineScene(int(scene_id), str(geometry["family"]), problem, geometry, provenance)


def load_offline_scene(scene_id, config=None, book=None, *, stage_a_signal=False,
                       explicit_authorization=False):
    config = load_config() if config is None else config
    path, _ = _source(scene_id, config, stage_a_signal=stage_a_signal,
                      explicit_authorization=explicit_authorization)
    with _span(book, "a22_separate_offline_label_read", offline_label_reads=1):
        with np.load(path, allow_pickle=False) as archive:
            truth = archive["truth"].copy()
    if truth.ndim != 1 or not np.all(np.isfinite(truth)):
        raise ValueError("INVALID_OFFLINE_TRUTH")
    return OfflineScene(int(scene_id), _readonly(truth, complex),
        {"source_path": str(path), "selected_members": ["truth"],
         "capability": "OFFLINE_EVALUATOR_ONLY", "historical_exposure": "historically_exposed_feasibility"})


def new_scene_recipes(config=None):
    """Frozen descriptors only: no generation, arrays, physics or seed calls."""
    config = load_config() if config is None else config
    expected = {sid: "asymmetric" for sid in range(2020, 2025)}
    expected.update({sid: "shell" for sid in range(2031, 2035)})
    rows = config["new_scenes"]
    if len(rows) != len(expected) or {int(row["id"]): row["family"] for row in rows} != expected:
        raise ValueError("NEW_SCENE_IDS_OR_FAMILIES_CHANGED")
    result = []
    for family in ("asymmetric", "shell"):
        family_rows = sorted((r for r in rows if r["family"] == family), key=lambda r: int(r["id"]))
        for offset, row in enumerate(family_rows):
            sid = int(row["id"])
            split = next((name for name, ids in config["splits"].items() if sid in ids), None)
            if split is None:
                raise ValueError("NEW_SCENE_HAS_NO_DECLARED_SPLIT")
            result.append({"scene_id": sid, "family": family, "j": 10 + offset, "split": split,
                "representation": "voxel", "registered_seed": int(row["seed"]),
                "generator": "EXCHANGE_R1/vendor/Gaussian/A16/CURRENT_SELECTION_R1/code/scenes.py:make_scene",
                "rng_protocol": "unchanged original seed('geometry', split, family, j)",
                "status": "NOT_GENERATED", "requires": ["stage_a_signal", "explicit_generation_authorization"]})
    return result


def generate_new_scene_recipe(scene_id, config=None, *, stage_a_signal=False,
                              explicit_authorization=False):
    """Generate only an offline continuous-scene descriptor after authorization.

    The original SHA-based RNG is retained as an algorithmic seed, not an
    integrity check.  No Maxwell call, dataset write or truth array occurs.
    """
    if not stage_a_signal or not explicit_authorization:
        raise ForbiddenAccess("NEW_SCENE_GENERATION_REQUIRES_EXPLICIT_STAGE_A_SIGNAL")
    config = load_config() if config is None else config
    recipe = next((r for r in new_scene_recipes(config) if r["scene_id"] == int(scene_id)), None)
    if recipe is None:
        raise ValueError("UNREGISTERED_NEW_SCENE_ID")
    source = Path(config["paths"]["asset_root"]) / recipe["generator"].split(":", 1)[0]
    module = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    # Execute only the unchanged pure generator functions; skip source imports,
    # CLI, integrity helpers, material rendering and acquisition/model creation.
    selected = [node for node in module.body if isinstance(node, ast.FunctionDef)
                and node.name in ("seed", "_component", "make_scene")]
    if {node.name for node in selected} != {"seed", "_component", "make_scene"}:
        raise ValueError("ORIGINAL_SCENE_GENERATOR_FUNCTIONS_MISSING")
    import hashlib
    namespace = {"np": np, "hashlib": hashlib}
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(source), "exec"), namespace)
    scene = namespace["make_scene"](recipe["family"], recipe["j"], recipe["split"],
                                    recipe["scene_id"], recipe["representation"])
    if list(scene["background"]) != list(config["background"]):
        raise ValueError("NEW_SCENE_BACKGROUND_PROTOCOL_MISMATCH")
    return {"scene": scene, "recipe": recipe, "capability": "OFFLINE_GENERATIVE_DESCRIPTOR",
            "physics_generated": False, "new_integrity_hash_checks": 0}
