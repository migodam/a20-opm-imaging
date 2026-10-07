"""Evaluator input boundary tests using synthetic files and mocked transport.

No original A17 label, Maxwell solve, real private configuration, SSH or SCP is
used.  This source is executed only by the parent's metered unit-test workflow.
"""
from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import zipfile

import numpy as np

from a22 import assets, offline_assets


PROJECT = Path(__file__).resolve().parents[1]
IDS = (2001, 2003, 2014, 2009)


class GuardBook:
    """A record-only fixture; campaign guard enforcement has its own tests."""
    def __init__(self):
        self.role, self.guards, self.counts = "online", [], Counter()

    @contextmanager
    def span(self, label, **counts):
        self.counts.update(counts)
        yield

    @contextmanager
    def action_guard(self, action, *, role, scene_id=None, purpose=None, **counts):
        if action != "truth" or role not in ("offline_label", "offline_evaluation"):
            raise AssertionError("Unexpected evaluator guard")
        self.guards.append(dict(action=action, role=role, scene_id=scene_id))
        previous, self.role = self.role, role
        self.counts.update(counts)
        try:
            yield
        finally:
            self.role = previous


def config(root):
    return dict(screening_scenes=list(IDS), background=[.1, .04],
                source_freeze="unit_fixture", paths={"asset_root": str(root/"source")},
                scene_sources={str(sid): {"source": "scene_"+str(sid)+".npz"} for sid in IDS})


def manifest():
    return dict(schema=offline_assets.SCHEMA, capability="OFFLINE_EVALUATOR_ONLY",
                online_use_allowed=False, allowed_npz_members=["truth"],
                scene_ids=list(IDS), asset_root_relative=offline_assets.RELATIVE_ROOT,
                finite_perturbation_center="actual_object_solver_grid_material",
                scenes=[dict(scene_id=sid, source="scene_"+str(sid)+".npz",
                             solver_n=12, saved_truth_shape=[1728],
                             data_generation_n_declared=14, online_use_allowed=False)
                        for sid in IDS])


def bundle(root):
    directory = root/offline_assets.RELATIVE_ROOT
    directory.mkdir(parents=True)
    labels = {}
    for i, sid in enumerate(IDS):
        truth = np.full(1728, .3+.01*i+.05j, dtype=np.complex128)
        labels[sid] = truth
        np.savez(directory/("scene_"+str(sid)+".npz"), truth=truth)
    (directory/"MANIFEST.json").write_text(json.dumps(manifest()), encoding="utf-8")
    return directory, labels


def tool(name):
    spec = importlib.util.spec_from_file_location("a22_unit_"+name, PROJECT/"tools"/(name+".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class OfflineAssetTests(unittest.TestCase):
    def test_online_only_npz_cannot_prepare_offline_truth(self):
        with tempfile.TemporaryDirectory() as directory:
            root, book = Path(directory), GuardBook()
            cfg = config(root)
            source = root/"source"
            source.mkdir()
            axis = (np.arange(12)+.5)*1.5/12-.75
            points = np.stack(np.meshgrid(axis, axis, axis, indexing="ij"), axis=-1).reshape(-1, 3)
            np.savez(source/"scene_2001.npz", points=points,
                     data0=np.zeros((6, 128), complex), init=np.full(1728, .1+.04j))
            with patch.object(offline_assets, "_atomic_truth") as write_truth:
                with self.assertRaises(KeyError):
                    offline_assets.prepare_offline_screening(root, cfg, book)
                write_truth.assert_not_called()
            self.assertFalse((root/offline_assets.RELATIVE_ROOT).exists())
            self.assertEqual(book.guards, [dict(action="truth", role="offline_label", scene_id=2001)])
            self.assertEqual(book.role, "online")

    def test_evaluator_load_reads_only_truth_under_guard_and_returns_readonly(self):
        with tempfile.TemporaryDirectory() as directory:
            root, book = Path(directory), GuardBook()
            _, labels = bundle(root)
            selected, roles = [], []
            original_load = np.load

            class SelectedArchive:
                def __init__(self, archive):
                    self.archive, self.files = archive, archive.files

                def __enter__(self):
                    self.archive.__enter__()
                    return self

                def __exit__(self, *args):
                    return self.archive.__exit__(*args)

                def __getitem__(self, name):
                    selected.append(name)
                    roles.append(book.role)
                    return self.archive[name]

            with patch.object(offline_assets.np, "load", side_effect=lambda *a, **k: SelectedArchive(original_load(*a, **k))):
                truth = offline_assets.load_evaluation_truth(root, 2001, book)
            np.testing.assert_array_equal(truth, labels[2001])
            self.assertEqual(truth.shape, (1728,))
            self.assertEqual(truth.dtype, np.dtype("complex128"))
            self.assertEqual(selected, ["truth"])
            self.assertEqual(roles, ["offline_evaluation"])
            self.assertFalse(truth.flags.writeable)
            with self.assertRaises(ValueError):
                truth[0] = 99.
            self.assertEqual(book.guards, [dict(action="truth", role="offline_evaluation", scene_id=2001)])
            self.assertEqual(book.role, "online")
            row = manifest()["scenes"][0]
            self.assertEqual((row["solver_n"], row["data_generation_n_declared"]), (12, 14))

    def test_wrong_parent_id_and_extra_npz_key_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root, book = Path(directory), GuardBook()
            target, labels = bundle(root)
            with self.assertRaisesRegex(ValueError, "ONLY_FOUR_FROZEN"):
                offline_assets.load_evaluation_truth(root, 9999, book)
            self.assertEqual(book.guards, [])
            wrong_config = config(root)
            wrong_config["screening_scenes"][-1] = 9999
            with patch.object(assets, "load_offline_scene") as source_loader:
                with self.assertRaisesRegex(ValueError, "ONLY_FOUR_FROZEN"):
                    offline_assets.prepare_offline_screening(root, wrong_config, book)
                source_loader.assert_not_called()
            wrong_label = assets.OfflineScene(2003, labels[2001], {"source_path": "unused"})
            with patch.object(assets, "load_offline_scene", return_value=wrong_label):
                with self.assertRaisesRegex(ValueError, "LABEL_ID_MISMATCH"):
                    offline_assets.prepare_offline_screening(root, config(root), book)
            np.savez(target/"scene_2001.npz", truth=labels[2001], teacher=np.zeros(1))
            with self.assertRaisesRegex(ValueError, "ONLY_TRUTH"):
                offline_assets.load_evaluation_truth(root, 2001, book)
            self.assertEqual(book.role, "online")

    def test_exact_evaluator_deployment_allowlist_and_online_exclusion_with_mocked_transport(self):
        evaluation, remote = tool("a22_evaluation_inputs"), tool("a22_remote_jobs")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target, _ = bundle(root)
            (target/"unregistered_9999.json").write_text("{}", encoding="utf-8")
            (root/"configs").mkdir()
            (root/"configs/a22.json").write_text(json.dumps(config(root)), encoding="utf-8")
            online = root/"data/a22/online"
            online.mkdir(parents=True)
            np.savez(online/"scene_2001.npz", points=np.zeros((1728, 3)),
                     data0=np.zeros((6, 128), complex), init=np.full(1728, .1+.04j))
            expected = tuple("data/a22/offline_eval/scene_"+str(sid)+".npz" for sid in IDS)+("data/a22/offline_eval/MANIFEST.json",)
            self.assertEqual(evaluation.evaluation_members(root), expected)
            online_members = remote.deployment_members(root)
            self.assertIn("data/a22/online/scene_2001.npz", online_members)
            self.assertFalse(any(name.startswith("data/a22/offline_eval/") for name in online_members))
            transferred = []

            def copy_to(archive, relative):
                with zipfile.ZipFile(archive) as zipped:
                    transferred.append((tuple(zipped.namelist()), relative))

            transport = Mock()
            transport.copy_to.side_effect = copy_to
            helper = SimpleNamespace(REMOTE="D:/AI/A22_THREE_FOLD_OPM",
                                     SHARED_LOCK="D:/AI/A20_OPM_IMAGING/runs/gpu.lock",
                                     PrivateTransport=Mock(return_value=transport),
                                     TransportFailure=RuntimeError,
                                     _python=Mock(side_effect=[
                                         dict(status="A22_EVALUATOR_TRANSFER_READY", remote_process_cpu_seconds=.1),
                                         dict(status="A22_OFFLINE_EVALUATION_INPUTS_DEPLOYED", members=5,
                                              files_written=5, files_reused=0, remote_process_cpu_seconds=.2)]))
            private_marker = "unit-private-config-that-is-never-read.json"
            with patch.object(evaluation, "_helper", return_value=helper), \
                 patch("subprocess.run", side_effect=AssertionError("Unit test attempted a real transport")):
                result = evaluation.deploy(private_marker, root=root)
                bad = deepcopy(manifest())
                bad["scenes"][-1]["scene_id"] = 9999
                (target/"MANIFEST.json").write_text(json.dumps(bad), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "OBJECT_SET_CHANGED"):
                    evaluation.deploy(private_marker, root=root)
            helper.PrivateTransport.assert_called_once_with(private_marker, root=root.resolve())
            self.assertEqual(helper._python.call_count, 2)
            transport.shell.assert_not_called()
            self.assertEqual(len(transferred), 1)
            self.assertEqual(transferred[0][0], expected)
            self.assertTrue(transferred[0][1].startswith("data/a22/offline_eval/.transfer/"))
            self.assertFalse(result["online_use_allowed"])
            self.assertFalse(result["private_files_transferred"])
            self.assertFalse(result["original_mixed_npz_transferred"])
            self.assertAlmostEqual(result["remote_process_cpu_seconds"], .3)


if __name__ == "__main__":
    unittest.main()
