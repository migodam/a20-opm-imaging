"""Pure online/validation interface fixtures; no physical solver is constructed.

The metered run_validation entrypoint performs the actual DenseDDA fixture once.
These tests deliberately mock physical construction and its orchestration.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from contextlib import contextmanager
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np

from a20.backend import ForbiddenAccess, pack, unpack
from a22 import assets, online, validation


class FixtureBook:
    """Event-only unit fixture, not a substitute for campaign budget tests."""
    def __init__(self):
        self.counts, self.walls, self.events = Counter(), defaultdict(float), []
        self.role, self.phase = "online", "unit"

    @contextmanager
    def scope(self, phase):
        previous, self.phase = self.phase, phase
        try:
            yield
        finally:
            self.phase = previous

    @contextmanager
    def span(self, label, **counts):
        self.counts.update(counts)
        row = dict(label=label, counts=counts, role=self.role, status="FAILED")
        self.events.append(row)
        try:
            yield row
            row["status"] = "OK"
        finally:
            pass

    @contextmanager
    def action_guard(self, action, *, role=None, **options):
        previous = self.role
        self.role = previous if role is None else role
        metadata = {k: options.pop(k) for k in ("scene_id", "method", "purpose") if k in options}
        if action == "perturbation_forward":
            options["data_generation_F_calls"] = options.get("F_calls", 1)
        try:
            with self.span(action, **options) as row:
                row.update(metadata)
                yield row
        finally:
            self.role = previous

    def finish(self, *args, **kwargs):
        raise AssertionError("Validation must not finish the caller-owned book")


def fixture():
    config = assets.load_config()
    problem, _ = validation.tiny_problem(config)
    return config, problem


def mock_adapter(problem, book=None):
    result = SimpleNamespace(problem=problem, chart=problem.chart,
                             book=book or FixtureBook(), P=6, m=128,
                             n=3*problem.chart.n, p=32, whitening=2.,
                             _operator_L=np.eye(3*problem.chart.n), _version=7,
                             _full_cache=object(), B_calls=0)
    result.whiten = lambda value, adjoint=False: float(result.whitening)*value

    def compressed_B(chi, state, Z):
        result.B_calls += 1
        return np.zeros((result.P, Z.shape[1], result.p), complex)

    result.compressed_B = compressed_B
    return result


def mock_anchor_opm():
    config, problem = fixture()
    adapter = mock_adapter(problem)
    key = online._identity(adapter, problem.init, config)
    anchor = online.Anchor(adapter, SimpleNamespace(), problem.init.copy(), {}, key, {})
    Z = np.eye(adapter.n, dtype=complex)[:, :3]
    projection = SimpleNamespace(kind="galerkin", fallback=None, Z=Z, W=Z.copy(),
                                 SZ=np.zeros((adapter.m, 3), complex),
                                 check=lambda: None, solve=lambda rhs: rhs.copy())
    model = online.OPMModel(anchor, None, None, None, projection, Z,
                            np.empty((6, 3, 32)), np.empty((6, 3, 32)),
                            np.empty((1536, 32)), {}, {})
    return config, adapter, anchor, model


class OnlineTests(unittest.TestCase):
    def test_fixed_patch_geometry_metric_and_real_coordinate_order(self):
        _, problem = fixture()
        chart = problem.chart
        self.assertEqual(chart.d, 32)
        self.assertEqual(chart.Q.shape, (64, 16))
        np.testing.assert_allclose(problem.volume*chart.Q.T@chart.Q, np.eye(16), atol=1e-14)
        coefficients = np.eye(32)
        physical = chart.expand(coefficients)
        np.testing.assert_array_equal(physical[:, :16], chart.Q)
        np.testing.assert_array_equal(physical[:, 16:], 1j*chart.Q)
        np.testing.assert_allclose(chart.project(physical), np.eye(32), atol=1e-14)
        self.assertEqual(assets.COARSE_INDICES, tuple(range(8))+tuple(range(16, 24)))
        with self.assertRaisesRegex(ValueError, "PATCH_"):
            assets.fixed_patch_chart(np.array(np.meshgrid([-1., 1.], [-1., 1.], [-1., 1.])).T.reshape(-1, 3), 1.)

    def test_acquisition_six_sources_and_128_complex_channels(self):
        dirs, pols, receivers, obs = assets.acquisition_geometry(dict(rotation=.37, receiver_count=64))
        self.assertEqual(dirs.shape, (6, 3))
        self.assertEqual(pols.shape, (6, 3))
        self.assertEqual(receivers.shape, (64, 3))
        self.assertEqual(obs.shape, (64, 2, 3))
        np.testing.assert_allclose(np.sum(dirs*pols, axis=1), 0., atol=1e-14)
        np.testing.assert_allclose(np.linalg.norm(receivers, axis=1), 5., atol=1e-14)
        np.testing.assert_allclose(np.einsum("rci,rdi->rcd", obs, obs),
                                   np.broadcast_to(np.eye(2), (64, 2, 2)), atol=1e-14)

    def test_online_loader_reads_only_selected_members(self):
        config, problem = fixture()
        reads = []

        class Archive:
            files = ["points", "data0", "init", "truth", "held_truth", "Q", "scale", "scene_json"]

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def __getitem__(self, name):
                reads.append(name)
                allowed = {"points": problem.points, "data0": problem.data, "init": problem.init}
                if name not in allowed:
                    raise AssertionError("Forbidden online archive member: "+name)
                return allowed[name]

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"selected.npz"
            path.write_bytes(b"unit archive marker")
            config = {**config, "paths": {"asset_root": directory},
                      "scene_sources": {"2001": dict(source="selected.npz", n=4)}}
            with patch.object(assets.np, "load", return_value=Archive()):
                scene = assets.load_online_scene(2001, config)
        self.assertEqual(reads, ["points", "data0", "init"])
        self.assertEqual(scene.provenance["offline_members_loaded"], [])
        for field in ("truth", "teacher", "labels", "full_J", "full_H", "held_truth"):
            with self.assertRaises(ForbiddenAccess):
                getattr(scene, field)

    def test_online_loader_rejects_background_source_mismatch(self):
        config, problem = fixture()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"source.npz"
            np.savez(path, points=problem.points, data0=problem.data, init=problem.init+.01j)
            config = {**config, "paths": {"asset_root": directory},
                      "scene_sources": {"2001": dict(source="source.npz", n=4)}}
            with self.assertRaisesRegex(ValueError, "DECLARED_BACKGROUND"):
                assets.load_online_scene(2001, config)

    def test_new_scene_recipe_is_dormant_without_both_explicit_flags(self):
        config, _ = fixture()
        for stage_signal, explicit in ((False, False), (True, False), (False, True)):
            with self.assertRaises(ForbiddenAccess):
                assets.generate_new_scene_recipe(2020, config, stage_a_signal=stage_signal,
                                                 explicit_authorization=explicit)
        recipes = assets.new_scene_recipes(config)
        self.assertEqual([row["scene_id"] for row in recipes], list(range(2020, 2025))+list(range(2031, 2035)))
        self.assertTrue(all(row["status"] == "NOT_GENERATED" for row in recipes))

    def test_source_major_pack_and_explicit_source_permutation(self):
        raw = np.arange(12).reshape(3, 4)+1j*(100+np.arange(12).reshape(3, 4))
        expected = np.concatenate([np.r_[row.real, row.imag] for row in raw])
        np.testing.assert_array_equal(pack(raw), expected)
        np.testing.assert_array_equal(unpack(expected, 3, 4), raw)
        permutation = [2, 0, 1]
        indices = np.arange(24).reshape(3, 8)[permutation].ravel()
        np.testing.assert_array_equal(pack(raw[permutation]), expected[indices])

    def test_zero_factor_signatures_are_undefined_without_epsilon(self):
        _, adapter, _, model = mock_anchor_opm()
        factors = online.material_features(model)
        self.assertEqual(factors.MW.shape, (6, 3, 32))
        self.assertEqual(factors.PMW.shape, (6, 3, 32))
        self.assertEqual(factors.AW.shape, (1536, 32))
        self.assertEqual(adapter.B_calls, 1)
        np.testing.assert_array_equal(factors.signatures["alpha"], np.zeros(32))
        self.assertTrue(np.isnan(factors.signatures["beta"]).all())
        self.assertTrue(np.isnan(factors.signatures["gamma"]).all())
        self.assertEqual(set(factors.signatures["branches"]), {"zero_injection"})
        self.assertFalse(factors.provenance["full_J_or_H_used"])

    def test_feature_contract_rejects_wrong_material_basis_or_Petrov(self):
        _, adapter, _, model = mock_anchor_opm()
        for W in (np.zeros((32, 32)), np.eye(32, dtype=complex), np.eye(32)[:, :31]):
            with self.assertRaises(ValueError):
                online.material_features(model, W)
        model.projection.kind = "frozen_test_petrov_qr"
        with self.assertRaisesRegex(ValueError, "DECLARED_GALERKIN"):
            online.material_features(model)
        self.assertEqual(adapter.B_calls, 0)

    def test_whitening_material_geometry_and_configuration_invalidate_cache(self):
        config, adapter, anchor, model = mock_anchor_opm()
        original = anchor.cache_key
        adapter.whitening *= 1.01
        self.assertNotEqual(online._identity(adapter, anchor.chi, config), original)
        with self.assertRaisesRegex(ValueError, "CACHE_CHANGED"):
            online.material_features(model)
        adapter.whitening /= 1.01
        anchor.chi = anchor.chi+1e-5
        with self.assertRaisesRegex(ValueError, "CACHE_CHANGED"):
            online.material_features(model)
        anchor.chi = adapter.problem.init.copy()
        old_frequency = adapter.problem.frequency
        adapter.problem.frequency += .01
        self.assertNotEqual(online._identity(adapter, anchor.chi, config), original)
        adapter.problem.frequency = old_frequency
        self.assertNotEqual(online._identity(adapter, anchor.chi, {**config, "master_seed": 20261008}), original)
        self.assertEqual(adapter.B_calls, 0)

    def test_restricted_view_and_probes_do_not_expose_observations_or_teacher(self):
        config, adapter, anchor, _ = mock_anchor_opm()
        adapter.problem.data = np.full((6, 128), 1e5+1e4j)
        view = online.RestrictedBuilderView(anchor)
        np.testing.assert_array_equal(view.r, np.zeros(1536))
        for field in ("full_J", "full_H", "teacher", "truth", "full_state", "adapter", "state"):
            with self.assertRaises(ForbiddenAccess):
                getattr(view, field)
        with self.assertRaises(ForbiddenAccess):
            getattr(view._a, "full_tangent_action")
        material, measurement, seed = online._fixed_probes(view, config)
        adapter.problem.data = np.zeros((6, 128), complex)
        other = online._fixed_probes(online.RestrictedBuilderView(anchor), config)
        np.testing.assert_array_equal(material, other[0])
        np.testing.assert_array_equal(measurement, other[1])
        self.assertEqual(seed, other[2])
        self.assertEqual(measurement.shape, (1536, 4))

    def test_builder_passes_explicit_fixed_O_probes_and_disables_fallback(self):
        config, adapter, anchor, _ = mock_anchor_opm()
        view = SimpleNamespace(book=adapter.book, _a=SimpleNamespace(problem=SimpleNamespace(parent_id=9022)),
                               chart=adapter.chart, P=6, m=128, n=adapter.n,
                               receiver=lambda rank: np.eye(adapter.n, dtype=complex)[:, :rank])
        received = {}

        def seeds(view_arg, feedback, config_arg, *, material_probes, measurement_probes):
            received.update(material=material_probes, measurement=measurement_probes)
            return SimpleNamespace(records={key: {} for key in "OPM"})

        def projection(adapter_arg, chi, basis, config_arg, *, allow_petrov):
            received["allow_petrov"] = allow_petrov
            return SimpleNamespace(fallback=None, stability={"safe": True})

        basis = np.eye(adapter.n, dtype=complex)[:, :32]
        features = online.MaterialFeatures(np.zeros((6, 32, 32)), np.zeros((6, 32, 32)),
                                            np.zeros((1536, 32)), np.eye(32), {}, {}, {})
        with patch.object(online, "RestrictedBuilderView", return_value=view), \
             patch.object(online, "SchurFeedback", side_effect=lambda v, U, c: SimpleNamespace(U=U)), \
             patch.object(online, "build_seeds", side_effect=seeds), \
             patch.object(online, "Hierarchy", return_value=SimpleNamespace(at_degree=lambda d: (basis, {}))), \
             patch.object(online, "Projection", side_effect=projection), \
             patch.object(online, "material_features", return_value=features):
            model = online.build_opm(anchor, config)
        self.assertEqual(received["measurement"].shape, (1536, 4))
        self.assertEqual(received["material"].shape, (32, 4))
        self.assertFalse(received["allow_petrov"])
        self.assertFalse(model.provenance["measurement_dependent_Q"])


class ValidationInterfaceTests(unittest.TestCase):
    def test_FD_forward_is_guarded_charged_and_does_not_activate_adapter(self):
        _, problem = fixture()
        book = FixtureBook()
        adapter = mock_adapter(problem, book)
        cache, version, trial = adapter._full_cache, adapter._version, problem.init+.001
        calls = []

        def state(chi):
            calls.append(chi.copy())
            return SimpleNamespace(field=np.zeros((6, 128)), source_residual=lambda: 0.)

        adapter.model = SimpleNamespace(state=state)
        adapter.full_state = lambda *args: self.fail("FD activated a new Adapter material")
        validation._health_forward(adapter, trial, book)
        np.testing.assert_array_equal(calls[0], trial)
        self.assertIs(adapter._full_cache, cache)
        self.assertEqual(adapter._version, version)
        self.assertEqual(book.counts["data_generation_F_calls"], 1)
        self.assertEqual(book.counts["full_forward_calls"], 1)
        self.assertEqual(book.counts["full_LU_factorizations"], 1)
        for counter in ("full_forward_RHS", "full_state_backward_residual_L_rhs",
                        "full_state_receiver_rhs", "full_state_Goff_rhs"):
            self.assertEqual(book.counts[counter], 6)
        self.assertEqual(book.events[0]["role"], "health")
        self.assertEqual(book.role, "online")

    def test_FD_failed_backward_residual_retains_prepaid_action(self):
        _, problem = fixture()
        book, adapter = FixtureBook(), mock_adapter(problem)
        adapter.model = SimpleNamespace(state=lambda chi: SimpleNamespace(source_residual=lambda: 2e-9))
        with self.assertRaisesRegex(ValueError, "BACKWARD_RESIDUAL"):
            validation._health_forward(adapter, problem.init, book)
        self.assertEqual(book.counts["full_forward_RHS"], 6)
        self.assertEqual(book.counts["data_generation_F_calls"], 1)
        self.assertTrue(all(row["status"] == "FAILED" for row in book.events))

    @staticmethod
    def provided_fixture(root):
        directory = root/"protocol/a22/verification"
        directory.mkdir(parents=True)
        for name, variable, result in validation._PROVIDED:
            (directory/(name+".py")).write_text(
                "from pathlib import Path\nimport json\n"+variable+" = Path(__file__).parent\n"
                "def main():\n    ("+variable+" / '"+result+"').write_text(json.dumps({'fixture': True}))\n"
                "    print('pure verifier fixture')\n", encoding="utf-8")
            (directory/result).write_text("original protocol evidence\n", encoding="utf-8")
        return directory

    def test_supplied_verifier_output_redirection_preserves_protocol_json(self):
        book = FixtureBook()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self.provided_fixture(root)
            rows = validation._run_provided(root, book)
            for name, _, result in validation._PROVIDED:
                self.assertEqual((source/result).read_text(), "original protocol evidence\n")
                output = root/"results/a22/validation/theory"/name
                self.assertEqual(json.loads((output/result).read_text()), {"fixture": True})
                self.assertEqual((output/"stdout.txt").read_text(), "pure verifier fixture\n")
            self.assertTrue(all(row["original_protocol_result_preserved"] for row in rows))
        guards = [row for row in book.events if row["label"] == "full_J"]
        self.assertTrue(guards)
        self.assertTrue(all(row["role"] == "offline_evaluation" for row in guards))
        self.assertEqual(book.counts["data_generation_F_calls"], 6)

    def test_validation_orchestration_writes_report_and_preserves_book_lifetime(self):
        book = FixtureBook()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(validation, "_run_provided", return_value=[{"status": "PASS"}]), \
                 patch.object(validation, "run_backend_health", return_value={"status": "PASS", "checks": []}) as backend:
                report = validation.run_validation(root, {"source_freeze": "fixed-source"}, book)
            backend.assert_called_once()
            saved = json.loads((root/"results/a22/validation/HEALTH.json").read_text())
            self.assertEqual(saved["status"], "PASS")
            self.assertFalse(saved["scientific_gates_adjudicated"])
            self.assertFalse(saved["caller_book_finished"])
            self.assertEqual(report["count_delta"]["validation_runs"], 1)
            with self.assertRaises(FileExistsError):
                validation.run_validation(root, {}, book)
        self.assertEqual(book.role, "online")
        self.assertEqual(book.phase, "unit")

    def test_failed_validation_saves_partial_checks_and_rethrows(self):
        failure = validation.HealthFailure("deliberate_fixture", [{"name": "deliberate_fixture", "status": "FAIL"}])
        with tempfile.TemporaryDirectory() as directory:
            root, book = Path(directory), FixtureBook()
            with patch.object(validation, "_run_provided", return_value=[]), \
                 patch.object(validation, "run_backend_health", side_effect=failure):
                with self.assertRaises(validation.HealthFailure):
                    validation.run_validation(root, {}, book)
            saved = json.loads((root/"results/a22/validation/HEALTH.json").read_text())
            self.assertEqual(saved["status"], "FAILED")
            self.assertEqual(saved["backend"]["checks"], failure.health_checks)
            self.assertFalse(saved["caller_book_finished"])


if __name__ == "__main__":
    unittest.main()
