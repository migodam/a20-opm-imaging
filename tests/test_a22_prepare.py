"""Small portable-asset boundary regressions; worker execution is NOT_RUN.

Only generated test fixtures are written/read.  The online source loader is
mocked, so these tests cannot access A17 archives or execute physics.
"""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest import mock

import numpy as np

from a22 import assets, prepare


class _Book:
    def __init__(self):
        self.operations = []

    @contextmanager
    def span(self, name, **counts):
        self.operations.append((name, counts))
        yield


def _config():
    return {
        "screening_scenes": list(prepare.SCREENING_IDS),
        "background": [.1, .04],
        "paths": {"asset_root": "/not-opened/source-assets", "theory_package": "protocol/a22"},
        "scene_sources": {"2005": {"source": "not-deployed.npz"}},
        "material_dimension": 32,
    }


def _online_fixture(scene_id, *, config, book):
    geometry = dict(assets.KNOWN_GEOMETRY[scene_id])
    geometry.pop("source")
    # Metadata outside the geometry whitelist must never be copied.  It is a
    # sentinel string, not an offline array; real loader geometry is stricter.
    geometry["unregistered_component_metadata"] = "must-not-be-deployed"
    return SimpleNamespace(
        scene_id=scene_id,
        geometry=geometry,
        points=np.zeros((12**3, 3), dtype=np.float64),
        data=np.full((6, 128), scene_id + .5j, dtype=np.complex128),
        problem=SimpleNamespace(init=np.full(12**3, .1 + .04j, dtype=np.complex128)),
    )


class PortableScreeningChecks(unittest.TestCase):
    def test_portable_files_are_exact_online_whitelist_and_original_config_is_unchanged(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            config = _config()
            original = deepcopy(config)
            (root / "configs").mkdir()
            source_config = root / "configs/a22.json"
            source_text = json.dumps(config, sort_keys=True)
            source_config.write_text(source_text)
            book = _Book()
            with mock.patch.object(assets, "load_online_scene", side_effect=_online_fixture) as loader:
                portable = prepare.prepare_screening(root, config, book)
            self.assertEqual(config, original)
            self.assertEqual(source_config.read_text(), source_text)
            self.assertEqual([call.args[0] for call in loader.call_args_list], list(prepare.SCREENING_IDS))
            for call in loader.call_args_list:
                self.assertIs(call.kwargs["config"], config)
                self.assertIs(call.kwargs["book"], book)
            asset_root = root / "data/a22/online"
            self.assertTrue(Path(portable["paths"]["asset_root"]).is_absolute())
            self.assertEqual(Path(portable["paths"]["asset_root"]), asset_root)
            self.assertEqual(set(portable["scene_sources"]), {str(sid) for sid in prepare.SCREENING_IDS})
            expected_geometry = set(prepare.PUBLIC_GEOMETRY_FIELDS) | {"source"}
            for sid in prepare.SCREENING_IDS:
                record = portable["scene_sources"][str(sid)]
                self.assertEqual(set(record), expected_geometry)
                self.assertEqual(record["source"], f"scene_{sid}.npz")
                with np.load(asset_root / record["source"], allow_pickle=False) as archive:
                    self.assertEqual(set(archive.files), {"points", "data0", "init"})
                    self.assertEqual(archive["points"].shape, (1728, 3))
                    np.testing.assert_array_equal(archive["data0"], np.full((6, 128), sid + .5j))
                    np.testing.assert_array_equal(archive["init"], np.full(1728, .1 + .04j))
            self.assertEqual(json.loads((root / "configs/a22_portable.json").read_text()), portable)
            manifest = json.loads((asset_root / "MANIFEST.json").read_text())
            self.assertEqual(manifest["scene_ids"], list(prepare.SCREENING_IDS))
            self.assertFalse(manifest["offline_labels_deployed"])
            self.assertEqual(manifest["physics_actions"], 0)
            self.assertEqual(manifest["historical_exposure"], "historically_exposed_feasibility")
            for row in manifest["scenes"]:
                self.assertEqual((row["truth_n"], row["solver_n"]), (14, 12))
                self.assertTrue(row["discretization_mismatch"])
                self.assertFalse(row["blind_holdout"])
                self.assertEqual(row["offline_members_loaded"], [])
                self.assertEqual(row["layout"]["packed_real_dimension"], 1536)
            writes = [name for name, _ in book.operations if name == "a22_portable_online_asset_write"]
            self.assertEqual(len(writes), 4)

    def test_absolute_local_asset_root_resolves_from_a_different_working_directory(self):
        previous_cwd = Path.cwd()
        with TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            with mock.patch.object(assets, "load_online_scene", side_effect=_online_fixture):
                portable = prepare.prepare_screening(root, _config(), _Book())
            other = root / "unrelated-working-directory"
            other.mkdir()
            try:
                os.chdir(other)
                for sid in prepare.SCREENING_IDS:
                    path, geometry = assets._source(sid, portable)
                    self.assertEqual(path, root / f"data/a22/online/scene_{sid}.npz")
                    self.assertEqual(geometry["n"], 12)
                    self.assertEqual(geometry["truth_n"], 14)
            finally:
                os.chdir(previous_cwd)

    def test_non_screening_ids_and_offline_configuration_are_rejected_before_reads_or_writes(self):
        bad_scene_config = _config()
        bad_scene_config["screening_scenes"].append(2005)
        offline_config = _config()
        offline_config["offline_labels"] = {"truth_path": "must-not-read-or-deploy.npz"}
        for config in (bad_scene_config, offline_config):
            with self.subTest(config=config), TemporaryDirectory() as temporary:
                root = Path(temporary).resolve()
                with mock.patch.object(assets, "load_online_scene") as loader:
                    with self.assertRaises(ValueError):
                        prepare.prepare_screening(root, config, _Book())
                loader.assert_not_called()
                self.assertFalse((root / "data/a22/online").exists())
                self.assertFalse((root / "configs/a22_portable.json").exists())


if __name__ == "__main__":
    unittest.main()
