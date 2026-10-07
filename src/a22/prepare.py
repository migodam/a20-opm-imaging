"""Prepare the four online screening assets, without any physics actions.

Importing this module prepares nothing.  The caller must invoke
``prepare_screening(root, config, book)`` inside its metered workflow.  The
only input capability is ``assets.load_online_scene``; no source NPZ is
copied and no offline/evaluator loader is called.
"""
from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Mapping

import numpy as np

from . import assets


SCREENING_IDS = (2001, 2003, 2014, 2009)
ONLINE_MEMBERS = ("points", "data0", "init")
PUBLIC_GEOMETRY_FIELDS = (
    "family", "rotation", "n", "truth_n", "edge", "wavenumber",
    "background", "init", "partial", "source_split", "receiver_count",
)
RELATIVE_ASSET_ROOT = "data/a22/online"
_OFFLINE_CONFIG_FIELDS = frozenset((
    "truth", "held_truth", "teacher", "labels", "full_j", "full_h",
    "reference_step", "oracle", "offline_labels", "label_path",
    "labels_path", "truth_path", "teacher_path",
))


def _check_online_configuration(value):
    """Reject offline payload/path fields rather than redeploying them."""
    if isinstance(value, Mapping):
        for key in value:
            if str(key).lower() in _OFFLINE_CONFIG_FIELDS:
                raise ValueError("OFFLINE_FIELD_IN_PORTABLE_CONFIGURATION:" + str(key))
        for item in value.values():
            _check_online_configuration(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _check_online_configuration(item)


def _inside(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root):
        raise ValueError("PORTABLE_OUTPUT_OUTSIDE_IMPLEMENTATION_ROOT")
    return path


def _atomic_npz(path, arrays):
    temporary = None
    try:
        with NamedTemporaryFile(mode="wb", dir=path.parent,
                                prefix="." + path.name + ".", delete=False) as output:
            temporary = Path(output.name)
            # Explicit keyword members, never a whole source-archive mapping.
            np.savez(output, points=arrays["points"], data0=arrays["data0"],
                     init=arrays["init"])
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _atomic_json(path, value):
    temporary = None
    try:
        with NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                prefix="." + path.name + ".", delete=False) as output:
            temporary = Path(output.name)
            json.dump(value, output, indent=2, sort_keys=True, allow_nan=False)
            output.write("\n")
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _public_record(online):
    record = {key: deepcopy(online.geometry[key]) for key in PUBLIC_GEOMETRY_FIELDS}
    if int(record["n"]) != 12 or int(record["truth_n"]) != 14:
        raise ValueError("A22_SCREENING_DISCRETIZATION_CHANGED")
    return record


def _online_arrays(online, geometry):
    # Each attribute belongs to the explicit online capability.  Do not read
    # archive members, scene definitions, old charts, scales or evaluator data.
    arrays = {
        "points": np.array(online.points, copy=True),
        "data0": np.array(online.data, copy=True),
        "init": np.array(online.problem.init, copy=True),
    }
    if arrays["points"].shape != (int(geometry["n"])**3, 3):
        raise ValueError("PORTABLE_SCREENING_MESH_LAYOUT_MISMATCH")
    if arrays["init"].shape != (len(arrays["points"]),):
        raise ValueError("PORTABLE_SCREENING_INITIAL_LAYOUT_MISMATCH")
    data = arrays["data0"]
    if data.ndim != 2 or data.shape[0] != 6 or data.shape[1] % 2:
        raise ValueError("PORTABLE_SCREENING_OBSERVATION_LAYOUT_MISMATCH")
    if not geometry["partial"] and data.shape[1] != 2*int(geometry["receiver_count"]):
        raise ValueError("PORTABLE_SCREENING_RECEIVER_LAYOUT_MISMATCH")
    return arrays


def _manifest_record(scene_id, filename, geometry, arrays):
    points, data, initial = (arrays[key] for key in ONLINE_MEMBERS)
    cells = len(points)
    return {
        "scene_id": scene_id,
        "source": filename,
        "family": str(geometry["family"]),
        "public_geometry": deepcopy(geometry),
        "selected_online_members": list(ONLINE_MEMBERS),
        "offline_members_loaded": [],
        "offline_labels_deployed": False,
        "source_archive_copied": False,
        "historical_exposure": "historically_exposed_feasibility",
        "blind_holdout": False,
        "truth_n": int(geometry["truth_n"]),
        "solver_n": int(geometry["n"]),
        "truth_cell_count_declared": int(geometry["truth_n"])**3,
        "solver_cell_count": cells,
        "discretization_mismatch": True,
        "discretization_note": (
            "Original acquisition declares truth_n=14, while the portable "
            "solver points use n=12. Preparation preserves this forward-model "
            "discretization difference; no truth array or truth simulation "
            "was used to prepare the asset."
        ),
        "layout": {
            "points": {"shape": list(points.shape), "dtype": str(points.dtype)},
            "data0": {"shape": list(data.shape), "dtype": str(data.dtype)},
            "init": {"shape": list(initial.shape), "dtype": str(initial.dtype)},
            "source_count": 6,
            "complex_channels_per_source": data.shape[1],
            "receiver_positions": data.shape[1] // 2,
            "polarizations_per_receiver": 2,
            "packed_real_dimension": 2*data.size,
            "data_order": "illumination-major; each source real channels then imaginary channels",
            "source_order": "for i in range(3), for j in range(3), i != j",
            "solver_complex_current_dimension": 3*cells,
            "material_real_dimension": 32,
            "material_order": "16 real patch coefficients followed by 16 imaginary patch coefficients",
            "material_basis_rebuilt_from_known_points_only": True,
        },
    }


def prepare_screening(root, config, book):
    """Write a portable, online-only screening bundle and return its config.

    ``root`` is the implementation directory.  ``book`` must expose ``span``;
    all asset reads use the existing metered whitelist loader, and all writes
    have their own spans.  The passed configuration and ``configs/a22.json``
    are unchanged.  Only four source assets are read; no physics, offline
    labels, scene generation, tests or integrity hashes are invoked.

    ``paths.asset_root`` in the returned/saved config is an absolute *local*
    path because the existing asset resolver resolves relative paths against
    the current working directory.  A remote CLI must reassign it to
    ``execution_root / 'data/a22/online'`` before loading a scene.
    """
    with book.span("a22_portable_preparation_setup", portable_prepare_calls=1):
        root = Path(root).resolve()
        if not root.is_dir():
            raise FileNotFoundError(root)
        if tuple(int(value) for value in config.get("screening_scenes", ())) != SCREENING_IDS:
            raise ValueError("ONLY_FOUR_FROZEN_SCREENING_SCENES_CAN_BE_PREPARED")
        _check_online_configuration(config)
        portable = deepcopy(config)
        asset_root = _inside(root, RELATIVE_ASSET_ROOT)
        config_path = _inside(root, "configs/a22_portable.json")
        manifest_path = _inside(root, RELATIVE_ASSET_ROOT + "/MANIFEST.json")
        portable["paths"]["asset_root"] = str(asset_root)
        # Drop every non-screening source declaration from the portable config.
        portable["scene_sources"] = {}
        portable["portable_assets"] = {
            "scope": "four_screening_scenes_online_only",
            "asset_root_relative": RELATIVE_ASSET_ROOT,
            "manifest_relative": RELATIVE_ASSET_ROOT + "/MANIFEST.json",
            "config_relative": "configs/a22_portable.json",
            "scene_ids": list(SCREENING_IDS),
            "offline_labels_deployed": False,
            "requires_asset_root_relocation_on_remote": True,
        }

    # Complete every whitelist read/layout validation before writing a bundle.
    # These four small online payloads contain no old material/truth arrays.
    prepared = []
    for scene_id in SCREENING_IDS:
        online = assets.load_online_scene(scene_id, config=config, book=book)
        with book.span("a22_portable_online_asset_layout", portable_layout_checks=1):
            if int(online.scene_id) != scene_id:
                raise ValueError("PORTABLE_SCREENING_SCENE_ID_MISMATCH")
            geometry = _public_record(online)
            arrays = _online_arrays(online, geometry)
            filename = "scene_" + str(scene_id) + ".npz"
            portable["scene_sources"][str(scene_id)] = dict(geometry, source=filename)
            prepared.append((scene_id, filename, geometry, arrays))

    manifest = {
        "schema": "a22.portable_screening_online.v1",
        "status": "PREPARED_ONLINE_ASSETS_ONLY",
        "asset_root_relative": RELATIVE_ASSET_ROOT,
        "local_asset_root_absolute": str(asset_root),
        "portable_config_relative": "configs/a22_portable.json",
        "remote_relocation": "Set config.paths.asset_root to execution_root/data/a22/online before loading",
        "input_capability": "assets.load_online_scene",
        "allowed_npz_members": list(ONLINE_MEMBERS),
        "allowed_geometry_fields": list(PUBLIC_GEOMETRY_FIELDS),
        "scene_ids": list(SCREENING_IDS),
        "historical_exposure": "historically_exposed_feasibility",
        "offline_labels_deployed": False,
        "physics_actions": 0,
        "new_integrity_hash_checks": 0,
        "scientific_gate_status": "NOT_ASSESSED_BY_PREPARATION",
        "scenes": [_manifest_record(*item) for item in prepared],
    }
    for _, filename, _, arrays in prepared:
        with book.span("a22_portable_online_asset_write", portable_online_asset_writes=1):
            asset_root.mkdir(parents=True, exist_ok=True)
            _atomic_npz(_inside(root, RELATIVE_ASSET_ROOT + "/" + filename), arrays)
    with book.span("a22_portable_metadata_write", portable_manifest_writes=1,
                   portable_config_writes=1):
        config_path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_json(manifest_path, manifest)
        _atomic_json(config_path, portable)
    return portable
