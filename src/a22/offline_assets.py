"""Explicit evaluator-only labels for the four historically exposed objects.

The solver-grid material is a target label and the center for offline finite
perturbations.  The online anchor remains the declared uniform background.
No label paths or values are added to online configuration or builder inputs.
"""
from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

import numpy as np

from . import assets


SCREENING_IDS = (2001, 2003, 2014, 2009)
RELATIVE_ROOT = "data/a22/offline_eval"
SCHEMA = "a22.offline_screening_evaluation.v1"
SOLVER_N = 12
DATA_GENERATION_N = 14
NPZ_MEMBERS = ("truth",)


def _scene_id(value):
    scene_id = int(value)
    if scene_id not in SCREENING_IDS:
        raise ValueError("ONLY_FOUR_FROZEN_OFFLINE_SCREENING_OBJECTS_ARE_ALLOWED")
    return scene_id


def _root(root):
    root = Path(root).resolve()
    if not root.is_dir():
        raise FileNotFoundError(root)
    directory = root
    for part in RELATIVE_ROOT.split("/"):
        directory = directory/part
        if directory.is_symlink():
            raise ValueError("OFFLINE_EVALUATOR_NAMESPACE_MUST_NOT_BE_A_SYMLINK")
    return root, directory


def _truth(value):
    truth = np.asarray(value)
    if truth.shape != (SOLVER_N**3,) or not np.iscomplexobj(truth):
        raise ValueError("OFFLINE_TRUTH_MUST_BE_COMPLEX_SOLVER_N12_MATERIAL")
    if not np.all(np.isfinite(truth)):
        raise ValueError("NONFINITE_OFFLINE_EVALUATION_TRUTH")
    result = np.array(truth, dtype=np.complex128, copy=True)
    result.flags.writeable = False
    return result


def _read_truth(path):
    if path.is_symlink():
        raise ValueError("OFFLINE_EVALUATOR_MEMBER_MUST_NOT_BE_A_SYMLINK")
    with np.load(path, allow_pickle=False) as archive:
        if set(archive.files) != set(NPZ_MEMBERS) or len(archive.files) != 1:
            raise ValueError("OFFLINE_EVALUATOR_NPZ_MUST_CONTAIN_ONLY_TRUTH")
        return _truth(archive["truth"])


def _atomic_json(path, value):
    temporary = None
    try:
        with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                prefix="."+path.name+".", delete=False) as output:
            temporary = Path(output.name)
            json.dump(value, output, indent=2, sort_keys=True, allow_nan=False)
            output.write("\n")
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _atomic_truth(path, truth):
    temporary = None
    try:
        with NamedTemporaryFile("wb", dir=path.parent, prefix="."+path.name+".",
                                delete=False) as output:
            temporary = Path(output.name)
            np.savez(output, truth=truth)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _record(scene_id, offline, config):
    geometry = deepcopy(assets.KNOWN_GEOMETRY[scene_id])
    declared = config.get("scene_sources", {}).get(str(scene_id), {})
    geometry.update(declared)
    if int(geometry["n"]) != SOLVER_N or int(geometry["truth_n"]) != DATA_GENERATION_N:
        raise ValueError("OFFLINE_SCREENING_DISCRETIZATION_CHANGED")
    if (list(geometry["background"]) != list(config["background"])
            or list(geometry["init"]) != list(config["background"])):
        raise ValueError("OFFLINE_SOURCE_BACKGROUND_DISAGREES_WITH_ONLINE_KNOWN_BACKGROUND")
    source_root = Path(config["paths"]["asset_root"]).resolve()
    source_path = Path(offline.provenance["source_path"]).resolve()
    if not source_path.is_relative_to(source_root):
        raise ValueError("OFFLINE_LABEL_SOURCE_IS_OUTSIDE_DECLARED_A17_ROOT")
    return dict(
        scene_id=scene_id, family=str(geometry["family"]),
        source="scene_"+str(scene_id)+".npz",
        source_archive_relative=source_path.relative_to(source_root).as_posix(),
        source_selected_members=["truth"], target_label_members=["truth"],
        target_label_origin="original_A17_object_material_on_solver_grid",
        target_label_role="offline_finite_perturbation_center_and_evaluation_target_only",
        online_anchor_origin="known_geometry_owned_uniform_background",
        online_anchor_background=list(config["background"]),
        solver_n=SOLVER_N, solver_cell_count=SOLVER_N**3,
        saved_truth_shape=[SOLVER_N**3], saved_truth_dtype="complex128",
        data_generation_n_declared=DATA_GENERATION_N,
        data_generation_cell_count_declared=DATA_GENERATION_N**3,
        discretization_mismatch=True,
        discretization_note=("Observed data declares a truth-generation grid n=14; "
            "the original saved truth member is checked to be material on solver n=12. "
            "These inputs preserve that distinction and do not regenerate measurements."),
        historical_exposure="historically_exposed_feasibility", blind_holdout=False,
        online_use_allowed=False, source_archive_copied=False,
        held_truth_loaded=False, old_material_chart_loaded=False,
    )


def _validate_manifest(manifest):
    if (manifest.get("schema") != SCHEMA or manifest.get("capability") != "OFFLINE_EVALUATOR_ONLY"
            or manifest.get("online_use_allowed") is not False
            or manifest.get("allowed_npz_members") != ["truth"]
            or tuple(manifest.get("scene_ids", ())) != SCREENING_IDS):
        raise ValueError("INVALID_OFFLINE_EVALUATOR_MANIFEST")
    rows = manifest.get("scenes", [])
    if len(rows) != len(SCREENING_IDS) or tuple(row.get("scene_id") for row in rows) != SCREENING_IDS:
        raise ValueError("OFFLINE_EVALUATOR_MANIFEST_OBJECT_SET_CHANGED")
    for row in rows:
        if (row.get("source") != "scene_"+str(row["scene_id"])+".npz"
                or row.get("solver_n") != SOLVER_N or row.get("saved_truth_shape") != [SOLVER_N**3]
                or row.get("data_generation_n_declared") != DATA_GENERATION_N
                or row.get("online_use_allowed") is not False):
            raise ValueError("OFFLINE_EVALUATOR_MANIFEST_LAYOUT_CHANGED")
    return manifest


def prepare_offline_screening(root, config, book) -> dict:
    """Copy only four guarded truth members to a separate immutable label bundle.

    No model is constructed.  Existing identical prepared inputs are reusable;
    conflicting assets or provenance are refused.  The caller owns the ledger
    and integrates this function into its already metered prepare CLI stage.
    """
    if book is None:
        raise ValueError("A22_LEDGER_REQUIRED_FOR_OFFLINE_LABEL_READS")
    if tuple(config.get("screening_scenes", ())) != SCREENING_IDS:
        raise ValueError("ONLY_FOUR_FROZEN_SCREENING_SCENES_CAN_BE_PREPARED_OFFLINE")
    if list(config["background"]) != [.1, .04]:
        raise ValueError("FROZEN_OFFLINE_SOURCE_BACKGROUND_CHANGED")
    root, directory = _root(root)
    prepared = []
    for scene_id in SCREENING_IDS:
        with book.action_guard("truth", role="offline_label", scene_id=scene_id,
                               purpose="offline_evaluator_input", offline_screening_truth_reads=1):
            offline = assets.load_offline_scene(scene_id, config=config, book=book)
            if int(offline.scene_id) != scene_id:
                raise ValueError("OFFLINE_SCREENING_LABEL_ID_MISMATCH")
            truth = _truth(offline.truth)
            prepared.append((_record(scene_id, offline, config), truth))
    manifest = dict(
        schema=SCHEMA, status="PREPARED_OFFLINE_EVALUATOR_INPUTS",
        capability="OFFLINE_EVALUATOR_ONLY", online_use_allowed=False,
        asset_root_relative=RELATIVE_ROOT, scene_ids=list(SCREENING_IDS),
        allowed_npz_members=["truth"], input_capability="assets.load_offline_scene",
        output_capability="offline_assets.load_evaluation_truth",
        deployment_route="explicit evaluator-input transfer; excluded from online data whitelist",
        finite_perturbation_center="actual_object_solver_grid_material",
        online_anchor="uniform_known_background_0.1+0.04i",
        historically_exposed=True, blind_holdout=False, physics_actions=0,
        new_integrity_hash_checks=0, original_mixed_npz_transferred=False,
        source_freeze=config.get("source_freeze"),
        scientific_gates_adjudicated=False, scenes=[record for record, _ in prepared])
    _validate_manifest(manifest)
    manifest_path = directory/"MANIFEST.json"
    with book.span("a22_offline_evaluator_existing_bundle_check", offline_bundle_conflict_checks=1):
        if manifest_path.is_symlink():
            raise ValueError("OFFLINE_EVALUATOR_MANIFEST_MUST_NOT_BE_A_SYMLINK")
        if manifest_path.exists() and json.loads(manifest_path.read_text(encoding="utf-8")) != manifest:
            raise ValueError("IMMUTABLE_OFFLINE_EVALUATION_MANIFEST_CONFLICT")
    # Validate every existing member before any writes.  Even these comparison
    # reads remain explicitly offline; equality is semantic, never a digest.
    for record, truth in prepared:
        path = directory/record["source"]
        if path.exists() or path.is_symlink():
            with book.action_guard("truth", role="offline_label", scene_id=record["scene_id"],
                                   purpose="offline_prepared_input_check", offline_existing_truth_checks=1):
                if not np.array_equal(_read_truth(path), truth):
                    raise ValueError("IMMUTABLE_OFFLINE_EVALUATION_TRUTH_CONFLICT")
    for record, truth in prepared:
        path = directory/record["source"]
        if path.exists():
            continue
        with book.span("a22_offline_evaluator_asset_write", offline_evaluation_asset_writes=1):
            directory.mkdir(parents=True, exist_ok=True)
            _atomic_truth(path, truth)
    if not manifest_path.exists():
        with book.span("a22_offline_evaluator_manifest_write", offline_evaluation_manifest_writes=1):
            directory.mkdir(parents=True, exist_ok=True)
            _atomic_json(manifest_path, manifest)
    return manifest


def load_evaluation_truth(root, sid, book) -> np.ndarray:
    """Evaluator-only guarded load; returns readonly complex solver-n12 material."""
    if book is None:
        raise ValueError("A22_LEDGER_REQUIRED_FOR_OFFLINE_EVALUATOR_READS")
    scene_id = _scene_id(sid)
    _, directory = _root(root)
    with book.action_guard("truth", role="offline_evaluation", scene_id=scene_id,
                           purpose="offline_evaluator_target", offline_evaluation_truth_reads=1):
        path = directory/"MANIFEST.json"
        if path.is_symlink():
            raise ValueError("OFFLINE_EVALUATOR_MANIFEST_MUST_NOT_BE_A_SYMLINK")
        manifest = _validate_manifest(json.loads(path.read_text(encoding="utf-8")))
        record = next(row for row in manifest["scenes"] if row["scene_id"] == scene_id)
        return _read_truth(directory/record["source"])
