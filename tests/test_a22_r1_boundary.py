"""Independent synthetic boundary checks; never run Maxwell or real replay data.

Temporary cache files reproduce only array layout, not experiment labels.
The original A22 source comparison reads Python source bytes, never its data.
"""

import ast
from collections import Counter
from contextlib import contextmanager, redirect_stderr, redirect_stdout
import inspect
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import numpy as np

from a20.costs import BudgetExceeded
from a20.material import QPFailure
from a22_r1 import accounting, cli, freeze, replay
from a22_r1.metrics import hierarchical_scene_average


ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT.parent / "three_fold_opm/implementation"
BOOK_CONFIG = {
    "cpu_cap_seconds": 160.0,
    "gpu_occupation_cap_seconds": 1000.0,
    "parent_a22_gpu_cap_seconds": 2000.0,
    "historical_a22_gpu_seconds": 0.0,
    "known_background_rebuild_cap": 4,
    "source_commit": "synthetic-boundary-fixture",
}
SCORE_CONTRACT = dict(amplitude=0.0, noise_level=1.0, intervention="nominal",
                      orientation="ascending", tie_breaker="common_basis_index")


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


class RecordingBook:
    """Synthetic bookkeeping only; no physics-capable methods."""

    def __init__(self):
        self.counts = Counter()
        self.events = []
        self.phase = "online"

    @contextmanager
    def scope(self, role):
        previous = self.phase
        self.phase = role
        try:
            yield
        finally:
            self.phase = previous

    @contextmanager
    def span(self, name, **counters):
        self.counts.update(counters)
        item = dict(event=name, phase=self.phase, counters=counters, status="FAILED")
        self.events.append(item)
        try:
            yield item
            item["status"] = "OK"
        except BaseException as error:
            item["error"] = type(error).__name__
            raise

    def check(self):
        return None


def fixture_scene(root, sid=2001):
    old = root / f"results/a22/stage_a/scene_{sid}"
    online = root / "results/a22_r1/online"
    old.mkdir(parents=True, exist_ok=True)
    online.mkdir(parents=True, exist_ok=True)
    AW = np.zeros((1536, 32))
    AW[:32] = np.eye(32)
    Q = np.zeros((1728, 16))
    Q[:16] = np.eye(16)
    common = np.roll(np.eye(32), 7, axis=0)
    scores = {
        "A1": np.zeros(32),
        "A2": np.arange(32, dtype=float)[::-1],
        "A3": np.tile(np.asarray([1.0, 1.0, 0.0, 0.0]), 8),
    }
    values = dict(AW=AW, background_field=np.zeros((6, 128), dtype=complex),
        Q_spatial=Q, cell_volume=np.asarray(1.0),
        anchor_chi=np.full(1728, 0.1 + 0.04j),
        whitening=np.asarray(np.sqrt(2.0) / 0.25), sigma_complex=np.asarray(0.25),
        common_V=common, context_json=np.asarray(json.dumps({"declared_object_radius": 1.0})),
        # Deliberately different: replay must use original provenance's lambda.
        lambda_value=np.asarray(777.0),
        **{"score_" + method: score for method, score in scores.items()},
        **{"order_" + method: np.argsort(score, kind="stable") for method, score in scores.items()})
    np.savez(online / f"scene_{sid}.npz", **values)
    np.savez(old / "online_factors.npz", AW=AW)
    np.savez(old / "online_split_16.npz", V_phys=common[:, :16], V_prior=common[:, 16:])
    write_json(old / "online_provenance.json", {
        "anchor": {"sigma_complex_reference": 0.25}, "descriptor": {"regularization": 0.125}})
    write_json(online / f"scene_{sid}.json", {
        "schema": "a22_r1.online_freeze.v1", "status": "COMPLETE", "scores": SCORE_CONTRACT})
    return values


def global_freeze(root, status="COMPLETE"):
    for sid in replay.SCENES:
        path = root / f"results/a22_r1/online/scene_{sid}.json"
        if not path.exists():
            write_json(path, {"status": "COMPLETE"})
    write_json(root / "results/a22_r1/SPLIT_FREEZE.json", {
        "schema": "a22_r1.split_freeze.v1", "status": status, "scenes": list(replay.SCENES)})


def case_row(noise=0.0, draw=0):
    seed = [20261007, 2001, 0, 0, draw, 661]
    return dict(scene_id=2001, family="synthetic", direction_id=0, amplitude_level=0,
        amplitude=0.2, noise_level=noise, noise_draw=draw, intervention="nominal",
        noise_seed=":".join(map(str, seed)), candidate_index=0)


class TemporaryFixture(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="a22-r1-synthetic-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)


class SourceAndFreezeTests(TemporaryFixture):
    def test_original_a22_python_sources_are_byte_unchanged_without_hashes(self):
        self.assertTrue(ORIGINAL.is_dir(), "Frozen source checkout is required for the byte comparison")
        for package in ("a20", "a20_r1", "a21", "a22"):
            expected = {path.relative_to(ORIGINAL): path.read_bytes()
                        for path in (ORIGINAL / "src" / package).rglob("*.py")}
            current = {path.relative_to(ROOT): path.read_bytes()
                       for path in (ROOT / "src" / package).rglob("*.py")}
            self.assertTrue(expected, package)
            self.assertEqual(current.keys(), expected.keys(), package)
            for path in expected:
                self.assertEqual(current[path], expected[path], str(path))

    def test_freeze_candidate_copy_is_exact_original_split_concatenation(self):
        tree = ast.parse(inspect.getsource(freeze.freeze_scene))
        assignments = [node for node in ast.walk(tree) if isinstance(node, ast.Assign)
                       and any(isinstance(target, ast.Name) and target.id == "common"
                               for target in node.targets)]
        self.assertEqual(len(assignments), 1)
        expected = ast.parse('np.column_stack((archive["V_phys"], archive["V_prior"])).copy()',
                             mode="eval").body
        self.assertEqual(ast.dump(assignments[0].value), ast.dump(expected))
        archive = {"V_phys": np.eye(32)[:, :16], "V_prior": np.eye(32)[:, 16:]}
        value = eval(compile(ast.Expression(assignments[0].value), "<synthetic-common-copy>", "eval"),
                     {"np": np, "archive": archive})
        np.testing.assert_array_equal(value, np.eye(32))
        archive["V_phys"][0, 0] = 2
        self.assertEqual(value[0, 0], 1)

    def test_freeze_audit_rejects_hidden_epsilon_but_discloses_identity_allowance(self):
        audit = freeze._Audit()
        with self.assertRaises(freeze.OnlineFreezeMismatch):
            audit.array(np.asarray([1e-14]), np.asarray([0.0]), "zero_physical_factor")
        with self.assertRaises(freeze.OnlineFreezeMismatch):
            audit.json(1e-14, 0.0, "descriptor.regularization")
        audit = freeze._Audit()
        audit.json(1e-11, 0.0, "descriptor.transpose_identity_error")
        report = audit.report()
        self.assertTrue(report["tiny_identity_allowance_used"])
        self.assertEqual(len(report["tiny_identity_allowances"]), 1)
        self.assertEqual(report["tiny_identity_allowances"][0]["absolute_tolerance"], 1e-10)

    def test_freeze_preconditions_fail_before_any_background_builder(self):
        with mock.patch.object(freeze, "build_anchor", side_effect=AssertionError("physics forbidden")) as build:
            with self.assertRaisesRegex(ValueError, "REQUIRES_PARENT_COST_BOOK"):
                freeze.freeze_scene(self.root, 2001, {}, None)
            config = {"screening_scenes": list(replay.SCENES), "total_direction_descriptors": 9,
                      "finite_screening_directions": 4}
            with self.assertRaisesRegex(ValueError, "LEGACY_DIRECTION_COUNTS_CHANGED"):
                freeze.freeze_scene(self.root, 2001, config, RecordingBook())
            build.assert_not_called()

    def test_new_modules_have_no_neural_training_or_nonlinear_solver_calls(self):
        forbidden_roots = {"torch", "tensorflow", "keras", "sklearn", "diffusers"}
        forbidden_calls = {"fit", "fit_transform", "train", "training_step", "gauss_newton",
                           "run_dbim", "generate_data", "teacher_label", "perturbation_forward"}
        for module in (accounting, freeze, replay, cli):
            tree = ast.parse(inspect.getsource(module))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    self.assertFalse({alias.name.split(".")[0] for alias in node.names} & forbidden_roots)
                elif isinstance(node, ast.ImportFrom):
                    self.assertNotIn((node.module or "").split(".")[0], forbidden_roots)
                elif isinstance(node, ast.Call):
                    name = (node.func.id if isinstance(node.func, ast.Name)
                            else node.func.attr if isinstance(node.func, ast.Attribute) else "")
                    self.assertNotIn(name, forbidden_calls)
                    if module is replay:
                        self.assertNotIn(name, {"build_anchor", "build_opm", "build_problem", "run_forward"})

    def test_online_freeze_npz_reads_name_only_original_online_members(self):
        tree = ast.parse(inspect.getsource(freeze.freeze_scene))
        loads = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Attribute) and node.func.attr == "load"
                 and isinstance(node.func.value, ast.Name) and node.func.value.id == "np"]
        names = {node.args[0].right.value for node in loads if isinstance(node.args[0], ast.BinOp)
                 and isinstance(node.args[0].right, ast.Constant)}
        self.assertEqual(names, {"online_split_16.npz", "online_factors.npz"})
        for node in loads:
            self.assertTrue(any(item.arg == "allow_pickle" and isinstance(item.value, ast.Constant)
                                and item.value.value is False for item in node.keywords))

    def test_cli_refuses_nn_and_unregistered_stage_before_loading_any_config(self):
        for stage in ("nn", "train", "diffusion", "expand"):
            with self.subTest(stage=stage), mock.patch.object(cli, "R1Book") as book:
                with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                    cli.main([stage, "--root", str(self.root), "--job", "a22-r1-synthetic"])
                self.assertEqual(error.exception.code, 2)
                book.assert_not_called()


class CacheAndSplitTests(TemporaryFixture):
    def test_cache_load_reuses_exact_basis_aw_sigma_and_original_lambda(self):
        values = fixture_scene(self.root)
        cache = replay._load_online(self.root, 2001, {})
        np.testing.assert_array_equal(cache.common_V, values["common_V"])
        np.testing.assert_array_equal(cache.AW, values["AW"])
        self.assertEqual(cache.sigma, 0.25)
        self.assertEqual(cache.whitening, np.sqrt(2) / 0.25)
        self.assertEqual(cache.lam, 0.125)
        self.assertNotEqual(cache.lam, float(values["lambda_value"]))
        self.assertEqual(cache.chart.Q.shape, (1728, 16))
        values["common_V"][0, 0] = 100
        self.assertNotEqual(cache.common_V[0, 0], 100)

    def test_cache_layout_source_order_and_factor_identity_are_rejected(self):
        for change, expected in (
            (lambda values: values.update(background_field=np.zeros((128, 6), dtype=complex)), "BACKGROUND_DATA_LAYOUT"),
            (lambda values: values["AW"].__setitem__((0, 0), 2.0), "CACHE_IDENTITY"),
            (lambda values: values.update(order_A1=np.arange(32)[::-1]), "SCORE_ORDER_CHANGED"),
            (lambda values: values.update(common_V=np.eye(32)), "COMMON_BASIS_MUST_BE_EXACT"),
        ):
            with self.subTest(expected=expected):
                values = fixture_scene(self.root)
                change(values)
                np.savez(self.root / "results/a22_r1/online/scene_2001.npz", **values)
                with self.assertRaisesRegex(replay.ReplayContractError, expected):
                    replay._load_online(self.root, 2001, {})

    def test_score_ties_are_stable_and_random_k_subspaces_are_nested(self):
        original_bytes = {}
        for sid in replay.SCENES:
            fixture_scene(self.root, sid)
            directory = self.root / f"results/a22/stage_a/scene_{sid}"
            original_bytes.update({path: path.read_bytes() for path in directory.iterdir()})
        book = RecordingBook()
        config = dict(scenes=list(replay.SCENES), k_values=[16, 8], primary_k=16, random_seed=20261910)
        caches, selected, path, _ = replay._freeze_online_splits(self.root, config, book)
        frozen = json.loads(path.read_text())
        self.assertEqual(frozen["status"], "COMPLETE")
        self.assertFalse(frozen["original_labels_opened"])
        self.assertFalse(frozen["full_J_used_online"])
        for sid in replay.SCENES:
            by_method_k = {(item.method, item.k): item for item in selected[sid]}
            np.testing.assert_array_equal(by_method_k[("A1", 16)].order, np.arange(32))
            expected_a3 = np.argsort(caches[sid].scores["A3"], kind="stable")
            np.testing.assert_array_equal(by_method_k[("A3", 16)].order, expected_a3)
            expected_random = np.random.default_rng(np.random.SeedSequence([20261910, sid])).permutation(32)
            eight, sixteen = by_method_k[("RANDOM", 8)], by_method_k[("RANDOM", 16)]
            np.testing.assert_array_equal(eight.order, expected_random)
            np.testing.assert_array_equal(eight.phys, sixteen.phys[:, :8])
            self.assertEqual(eight.seed, (20261910, sid))
            for item in selected[sid]:
                np.testing.assert_array_equal(item.phys, caches[sid].common_V[:, item.order[:item.k]])
                np.testing.assert_array_equal(item.prior, caches[sid].common_V[:, item.order[item.k:]])
        for path, value in original_bytes.items():
            self.assertEqual(path.read_bytes(), value, str(path))

    def test_unregistered_k_set_and_primary_k_are_refused_before_cache_load(self):
        for config in ({"k_values": [8, 12, 16]}, {"k_values": [8, 12]},
                       {"k_values": [8, 16], "primary_k": 8}):
            with self.subTest(config=config), mock.patch.object(replay, "_load_online") as load:
                with self.assertRaisesRegex(replay.ReplayContractError, "FROZEN_K_SET"):
                    replay._freeze_online_splits(self.root, config, RecordingBook())
                load.assert_not_called()

    def test_all_four_online_manifests_precede_any_split_cache_read(self):
        for sid in replay.SCENES:
            write_json(self.root / f"results/a22_r1/online/scene_{sid}.json", {"status": "COMPLETE"})
        write_json(self.root / "results/a22_r1/online/scene_2009.json", {"status": "FAILED"})
        with mock.patch.object(replay, "_load_online", side_effect=AssertionError("cache read forbidden")) as load:
            with self.assertRaisesRegex(replay.ReplayContractError, "ALL_ONLINE_SCENES"):
                replay._freeze_online_splits(self.root, {}, RecordingBook())
            load.assert_not_called()
        self.assertFalse((self.root / "results/a22_r1/SPLIT_FREEZE.json").exists())

    def test_invalid_permutation_and_different_semantic_freeze_are_not_repaired(self):
        fixture_scene(self.root)
        cache = replay._load_online(self.root, 2001, {})
        with self.assertRaisesRegex(replay.ReplayContractError, "NOT_A_PERMUTATION"):
            replay._split(cache, "A3", np.zeros(32, dtype=int), 16)
        path = self.root / "semantic.json"
        replay._immutable_json(path, {"score": 1})
        before = path.read_bytes()
        with self.assertRaisesRegex(replay.ReplayContractError, "IMMUTABLE_JSON_MISMATCH"):
            replay._immutable_json(path, {"score": 2})
        self.assertEqual(path.read_bytes(), before)
        arrays = self.root / "semantic.npz"
        replay._immutable_npz(arrays, {"basis": np.eye(2)})
        before = arrays.read_bytes()
        with self.assertRaisesRegex(replay.ReplayContractError, "IMMUTABLE_ARRAY_MISMATCH"):
            replay._immutable_npz(arrays, {"basis": 2 * np.eye(2)})
        self.assertEqual(arrays.read_bytes(), before)


class OfflineAndDataBoundaryTests(TemporaryFixture):
    def test_offline_helpers_refuse_before_any_evaluator_file_read(self):
        calls = [
            lambda: replay._freeze_offline_splits(self.root, {}, RecordingBook(), {}, {}),
            lambda: replay._registered_rows(self.root, {}, replay.SCENES),
            lambda: replay._load_label(self.root, {}, mock.Mock(scene=2001), RecordingBook()),
        ]
        for call in calls:
            with self.subTest(call=call), mock.patch.object(replay.np, "load") as load:
                with self.assertRaisesRegex(replay.ReplayContractError, "FREEZE_REQUIRED_BEFORE_OFFLINE_READ"):
                    call()
                load.assert_not_called()

    def test_pending_global_or_individual_online_receipt_blocks_offline_access(self):
        global_freeze(self.root, "PENDING")
        with self.assertRaisesRegex(replay.ReplayContractError, "GLOBAL_ONLINE_SPLIT_FREEZE_NOT_COMPLETE"):
            replay._require_evaluation_freeze(self.root)
        global_freeze(self.root)
        write_json(self.root / "results/a22_r1/online/scene_2014.json", {"status": "FAILED"})
        with self.assertRaisesRegex(replay.ReplayContractError, "ALL_ONLINE_SCENES"):
            replay._require_evaluation_freeze(self.root)

    def test_nominal_whitened_source_packing_matches_per_source_real_then_imaginary(self):
        fixture_scene(self.root)
        cache = replay._load_online(self.root, 2001, {})
        real = np.arange(6 * 128).reshape(6, 128)
        clean = real.astype(complex) + 1j * (real + 1000)
        label = replay.Label(clean, np.zeros(32), np.eye(32)[:, 0], 0.2, self.root / "synthetic.npz")
        result = replay._data(case_row(), label, cache, {"master_seed": 20261007})
        expected = np.asarray([entry for source in clean
                               for entry in list(source.real) + list(source.imag)]) * cache.whitening
        self.assertEqual(result.shape, (1536,))
        np.testing.assert_array_equal(result, expected)

    def test_noise_recipe_is_repeatable_and_draw_seed_changes_observation(self):
        fixture_scene(self.root)
        cache = replay._load_online(self.root, 2001, {})
        clean = np.ones((6, 128), dtype=complex)
        label = replay.Label(clean, np.zeros(32), np.eye(32)[:, 0], 0.2, self.root / "synthetic.npz")
        row = case_row(noise=0.5, draw=3)
        result = replay._data(row, label, cache, {"master_seed": 20261007})
        repeated = replay._data(row, label, cache, {"master_seed": 20261007})
        np.testing.assert_array_equal(result, repeated)
        self.assertFalse(np.array_equal(result, replay._data(case_row(noise=0.5, draw=4), label,
                                                           cache, {"master_seed": 20261007})))
        rng = np.random.default_rng(np.random.SeedSequence([20261007, 2001, 0, 0, 3, 661]))
        noise = 0.5 * 0.25 / np.sqrt(2) * (rng.normal(size=(6, 128)) + 1j * rng.normal(size=(6, 128)))
        observation = clean + noise
        expected = np.concatenate([np.r_[source.real, source.imag] for source in observation]) * cache.whitening
        np.testing.assert_array_equal(result, expected)

    def test_label_source_order_contract_is_checked_and_original_fixture_bytes_retained(self):
        fixture_scene(self.root)
        global_freeze(self.root)
        cache = replay._load_online(self.root, 2001, {})
        path = self.root / "results/a22/stage_a/scene_2001/OFFLINE_label_d0_a0.npz"
        values = dict(clean_data=np.zeros((6, 128), dtype=complex), coefficients=np.zeros(32),
                      direction=np.eye(32)[:, 0], amplitude=np.asarray(0.2), source_order=np.arange(6))
        np.savez(path, **values)
        original_bytes = path.read_bytes()
        book = RecordingBook()
        loaded = replay._load_label(self.root, case_row(), cache, book)
        self.assertEqual(loaded.clean.shape, (6, 128))
        self.assertEqual(path.read_bytes(), original_bytes)
        self.assertEqual(book.counts["offline_label_cache_reads"], 1)
        self.assertEqual(book.events[0]["phase"], "offline_evaluation")
        values["source_order"] = np.arange(6)[::-1]
        np.savez(path, **values)
        with self.assertRaisesRegex(replay.ReplayContractError, "LABEL_SOURCE_ORDER_CHANGED"):
            replay._load_label(self.root, case_row(), cache, book)


class SolveAccountingAndFailureTests(TemporaryFixture):
    def test_metric_record_merges_chart_metadata_without_duplicate_keyword_failure(self):
        fixture_scene(self.root)
        cache = replay._load_online(self.root, 2001, {})
        selected = replay._split(cache, "A3", np.arange(32), 16)
        truth = np.ones(32)
        result = replay._metric_record(case_row(), selected, "A", truth + 0.1, truth, {})
        self.assertEqual(result["status"], "OK")
        self.assertEqual(result["chart_dimension"], 32)
        self.assertEqual(result["k"], 16)
        self.assertEqual(result["test"], "A")
        self.assertAlmostEqual(result["nrmse_phys"], 0.1)
        self.assertAlmostEqual(result["nrmse_prior"], 0.1)

    def test_original_lambda_is_explicit_in_common_and_restricted_solver_calls(self):
        fixture_scene(self.root)
        cache = replay._load_online(self.root, 2001, {})
        original = {"tikhonov_relative": 999.0}
        basis = cache.common_V[:, :16]
        book = RecordingBook()
        with mock.patch.object(replay, "constrained_material_solve",
                               return_value=(np.zeros(32), {"status": "OK"}, np.zeros(32))) as solve:
            replay._solve(cache.AW, np.zeros(1536), cache, original, book)
            replay._solve(cache.AW @ basis, np.zeros(1536), cache, original, book, basis=basis)
        self.assertEqual(solve.call_count, 2)
        for call in solve.call_args_list:
            self.assertEqual(call.kwargs["lam"], 0.125)
            self.assertIs(call.args[4], original)
        self.assertIsNone(solve.call_args_list[0].kwargs["basis"])
        self.assertIs(solve.call_args_list[1].kwargs["basis"], basis)
        self.assertEqual(book.counts["cached_small_solves"], 2)
        self.assertEqual(book.counts["common_32D_solves"], 1)
        self.assertEqual(book.counts["restricted_physics_solves"], 1)

    def test_qp_failure_is_terminal_counted_and_never_retried_or_clipped(self):
        fixture_scene(self.root)
        cache = replay._load_online(self.root, 2001, {})
        book = RecordingBook()
        failure = QPFailure("synthetic infeasible QP")
        failure.result = {"valid": False, "reason": "synthetic"}
        with mock.patch.object(replay, "constrained_material_solve", side_effect=failure) as solve:
            with self.assertRaises(QPFailure):
                replay._solve(cache.AW[:, :16], np.zeros(1536), cache, {}, book,
                              basis=cache.common_V[:, :16])
            solve.assert_called_once()
        self.assertEqual(book.counts["cached_small_solves"], 1)
        self.assertEqual(book.counts["restricted_physics_solves"], 1)
        self.assertEqual(book.events[0]["status"], "FAILED")
        replay._failure(self.root, {"method": "A3", "test": "B"}, failure)
        rows = [json.loads(line) for line in (self.root / "results/a22_r1/FAILURE_LEDGER.jsonl").read_text().splitlines()]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "INVALID_QP")
        self.assertTrue(rows[0]["terminal"])
        self.assertFalse(rows[0]["clipping"])
        self.assertFalse(rows[0]["fallback"])
        self.assertEqual(rows[0]["qp_audit"], failure.result)

    def test_inclusive_receipts_are_unique_and_failed_job_is_paid(self):
        accounting.external_receipt(self.root, "synthetic-cost", cpu=0.1, wall=0.2)
        with self.assertRaisesRegex(ValueError, "ALREADY_PAID"):
            accounting.external_receipt(self.root, "synthetic-cost", cpu=0.1)
        book = accounting.R1Book(self.root, BOOK_CONFIG, "a22-r1-synthetic-failed")
        with self.assertRaises(QPFailure):
            with book.span("synthetic_small_failure", cached_small_solves=1):
                raise QPFailure("synthetic")
        result = book.finish("FAILED", {"synthetic": True})
        self.assertEqual(result["counts"]["cached_small_solves"], 1)
        self.assertTrue(result["additive_receipt"])
        self.assertTrue(result["nested_spans_nonadditive"])
        failure = json.loads((self.root / "results/a22_r1/FAILURE_LEDGER.jsonl").read_text().splitlines()[0])
        self.assertEqual(failure["receipt_id"], "a22-r1-synthetic-failed")
        self.assertEqual(failure["status"], "FAILED")
        with self.assertRaisesRegex(ValueError, "FINISHED_TWICE"):
            book.finish("FAILED")

    def test_online_full_derivative_and_new_label_counters_are_refused_before_body(self):
        book = accounting.R1Book(self.root, BOOK_CONFIG, "a22-r1-synthetic-guards")
        counters = ("full_J_builds", "full_tangent_calls", "full_tangent_RHS",
                    "full_adjoint_calls", "full_adjoint_RHS", "data_generation_F_calls", "new_teacher_labels")
        for counter in counters:
            with self.subTest(counter=counter):
                body_entered = False
                with self.assertRaises(BudgetExceeded):
                    with book.span("synthetic_forbidden", **{counter: 1}):
                        body_entered = True
                self.assertFalse(body_entered)
                self.assertEqual(book.counts[counter], 0)

    def test_known_background_cap_and_forbidden_online_actions_are_terminal(self):
        book = accounting.R1Book(self.root, BOOK_CONFIG, "a22-r1-synthetic-action-guards")
        book.prior["backgrounds"] = 4
        with self.assertRaisesRegex(BudgetExceeded, "FOUR_KNOWN_BACKGROUND_CAP"):
            with book.span("synthetic_background", full_forward_calls=1):
                self.fail("Known-background cap did not stop the action")
        for action in ("truth", "full_J", "full_H", "teacher", "reference_step",
                       "perturbation_forward", "generate_data", "teacher_label"):
            with self.subTest(action=action), self.assertRaises(BudgetExceeded):
                with book.action_guard(action, role="online"):
                    self.fail("Forbidden action guard yielded")

    def test_cli_failure_finishes_a_failed_receipt_without_invoking_real_replay(self):
        write_json(self.root / "configs/a22_r1.json", BOOK_CONFIG)
        with mock.patch.object(replay, "run_replay", side_effect=QPFailure("synthetic terminal")) as run:
            with redirect_stdout(io.StringIO()):
                result = cli.main(["replay", "--root", str(self.root), "--job", "a22-r1-synthetic-cli"])
            run.assert_called_once()
        self.assertEqual(result, 1)
        receipt = json.loads((self.root / "results/a22_r1/COST_LEDGER.jsonl").read_text().splitlines()[0])
        self.assertEqual(receipt["status"], "FAILED")
        self.assertEqual(receipt["detail"]["error_type"], "QPFailure")
        self.assertTrue((self.root / "results/a22_r1/FAILURE_LEDGER.jsonl").exists())

    def test_invalid_qp_and_unknown_status_invalidate_metric_groups(self):
        conditions = [dict(direction=direction, amplitude=amplitude, noise=noise, intervention=intervention)
                      for direction in range(4) for amplitude in (0, 1)
                      for noise in (0.0, 0.5, 1.0) for intervention in ("nominal", "calibrated")]
        for status in ("INVALID_QP", "solver_unknown"):
            rows = []
            for condition in conditions:
                for draw in range(1 if condition["noise"] == 0 else 16):
                    rows.append(dict(scene=2001, method="A3", k=16, test="B", noise_draw=draw,
                                     nrmse_phys=0.1, status="OK", **condition))
            rows[0]["status"] = status
            with self.subTest(status=status):
                result = hierarchical_scene_average(rows, ("nrmse_phys",), expected_conditions=conditions,
                    expected_groups=[dict(scene=2001, method="A3", k=16, test="B")])
                self.assertEqual(result["audit"]["failed_replicate_count"], 1)
                self.assertFalse(result["scene_rows"][0]["complete"])
                self.assertIsNone(result["scene_rows"][0]["nrmse_phys"])


if __name__ == "__main__":
    unittest.main()
