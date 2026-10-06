"""Small orchestration fixtures with real failure records and no Maxwell work."""
from __future__ import annotations

from collections import Counter
from contextlib import ExitStack, contextmanager
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from a20.costs import BudgetExceeded
from a20.material import QPFailure
from a20.opm import UnsafeCore
import a21.anatomy as anatomy
from a21.core import AnatomyInputError, RankBudgetInfeasible
from a21.diagnostics import ConsistencyFailure


PROJECT = Path(__file__).resolve().parents[1]
PARENTS = (2001, 2005, 2003, 2007, 2013)
BACKEND_PARENTS = (2001, 2003, 2013)
G_ARMS = ("BASE_G", "PRIMAL_G", "DUAL_G", "BOTH_G", "RANDOM_G")
PG_ARMS = ("BOTH_PG", "RANDOM_PG")


class FixtureBook:
    def __init__(self):
        self.counts, self.walls, self.metadata = Counter(), Counter(), {}
        self.device = "cpu"

    def check(self):
        pass

    @contextmanager
    def span(self, label, **counts):
        self.counts.update(counts)
        yield


class FlowFixture:
    """Pay no physics: only dataflow callbacks and genuine temporary sinks."""
    def __init__(self, root, *, stage="all", failures=None, backend_failure=None):
        self.root, self.events, self.book = Path(root), [], FixtureBook()
        self.failures, self.backend_failure = failures or {}, backend_failure
        self.config = json.loads((PROJECT/"configs/a21.json").read_text()) | {"stage": stage}
        (self.root/"configs").mkdir(parents=True)
        (self.root/"configs/parents.json").write_text(json.dumps({"parents": [{"parent_id": parent} for parent in PARENTS]}))
        self.directory = self.root/"results/a21/anatomy"

    def prepare(self, root, parent, config, book):
        pid = int(parent["parent_id"])
        self.events.append(("prepare", pid))
        return {"metadata": {"parent_id": pid, "schema": "synthetic-flow-only"}}

    def validate(self, case, config, book):
        pid = case["metadata"]["parent_id"]
        self.events.append(("validate", pid))
        if pid == self.backend_failure:
            raise ConsistencyFailure("SYNTHETIC_REGISTERED_BACKEND_FAILURE")
        return {"status": "PASS", "parent_id": pid, "synthetic_flow_fixture": True}

    def save(self, case, directory, book=None):
        metadata = dict(case["metadata"])
        pid = metadata["parent_id"]
        self.events.append(("save", pid))
        path = directory/"caches"/f"{pid}_17.npz"
        path.parent.mkdir(parents=True, exist_ok=True)
        # Only the mocked cache reader opens this token. It is intentionally
        # not a physical matrix or a synthetic stand-in for a real state.
        with path.open("xb") as handle:
            handle.write(b"SYNTHETIC_FLOW_CACHE_TOKEN_NO_PHYSICS\n")
        metadata["cache_path"] = str(path)
        path.with_suffix(".json").write_text(json.dumps(metadata))
        return metadata

    def load(self, path, config):
        path = Path(path)
        metadata = json.loads(path.with_suffix(".json").read_text())
        self.events.append(("load", int(metadata["parent_id"])))
        return {"metadata": metadata, "cache_path": str(path)}

    def evaluate(self, case, arm, config, book, directory, job, run_id):
        pid = case["metadata"]["parent_id"]
        self.events.append(("evaluate", pid, arm))
        failure = self.failures.get((pid, arm))
        status = "OK"
        if isinstance(failure, RankBudgetInfeasible):
            status = "RANK_BUDGET_INFEASIBLE"
        elif isinstance(failure, UnsafeCore):
            status = "UNSAFE_CORE"
        elif isinstance(failure, QPFailure):
            status = "QP_FAILED"
        elif isinstance(failure, BudgetExceeded):
            status = "STOPPED"
        elif failure is not None:
            status = "FAILED"
        attempts = 0 if isinstance(failure, (RankBudgetInfeasible, UnsafeCore)) else 1
        record = {"parent_id": pid, "iteration": 17, "arm": arm, "job": job, "run_id": run_id,
                  "status": status, "consistency_passed": failure is None, "QP_valid": failure is None,
                  "cost": {"counts": {"a21_reduced_qps": attempts}},
                  "synthetic_flow_fixture": True, "truth_or_labels_read": False}
        if failure is not None:
            record["failure_reason"] = type(failure).__name__+": "+str(failure)
        book.counts["a21_reduced_qps"] += attempts
        return record, failure

    def synthetic(self, root, directory, config, book):
        self.events.append(("synthetic",))
        return {"status": "PASS", "synthetic_flow_fixture": True}

    @contextmanager
    def mocks(self, *, forbid_preparation=False, synthetic_failure=None):
        with ExitStack() as stack:
            # A mistaken path to the physical backend must fail the test.
            stack.enter_context(patch.object(anatomy, "Adapter", side_effect=AssertionError("FLOW_FIXTURE_ATTEMPTED_MAXWELL_SETUP")))
            stack.enter_context(patch.object(anatomy, "prepare_case", side_effect=AssertionError("CACHE_ONLY_PG_PREPARED_A_STATE") if forbid_preparation else self.prepare))
            stack.enter_context(patch.object(anatomy, "validate_case", side_effect=AssertionError("CACHE_ONLY_PG_REVALIDATED_PHYSICS") if forbid_preparation else self.validate))
            stack.enter_context(patch.object(anatomy, "_save_case", side_effect=AssertionError("CACHE_ONLY_PG_REWROTE_A_CACHE") if forbid_preparation else self.save))
            stack.enter_context(patch.object(anatomy, "load_cached_case", side_effect=self.load))
            stack.enter_context(patch.object(anatomy, "evaluate_arm", side_effect=self.evaluate))
            stack.enter_context(patch.object(anatomy, "_synthetic_validation", side_effect=synthetic_failure or (AssertionError("CACHE_ONLY_PG_REPEATED_SYNTHETIC_JOB") if forbid_preparation else self.synthetic)))
            yield

    def run(self, job="a21-synthetic-flow"):
        return anatomy.run_anatomy(self.root, self.config, self.book, job)

    def rows(self):
        return [json.loads(line) for line in (self.directory/"rows.jsonl").read_text().splitlines() if line.strip()]

    def latest(self):
        return {(int(row["parent_id"]), row["arm"]): row for row in self.rows()}

    def seed_completed_G(self, *, T0_status="PASS", cap_already_used=False):
        for name in ("caches", "states", "diagnostics", "validation"):
            (self.directory/name).mkdir(parents=True, exist_ok=True)
        for parent in PARENTS:
            backend = {"status": "PASS"} if parent in BACKEND_PARENTS else {"status": "NOT_REQUIRED"}
            self.save({"metadata": {"parent_id": parent, "backend_validation": backend}}, self.directory)
        sink = anatomy._Sink(self.directory, "a21-fixture-prior-G", "fixture-prior")
        for parent in PARENTS:
            for arm in G_ARMS:
                count = 11 if cap_already_used and (parent, arm) == (PARENTS[0], G_ARMS[0]) else 1
                sink.append({"parent_id": parent, "iteration": 17, "arm": arm, "status": "OK",
                             "consistency_passed": True, "QP_valid": True,
                             "cost": {"counts": {"a21_reduced_qps": count}}, "synthetic_flow_fixture": True})
        sink.not_run("REGISTERED_CACHE_ONLY_PG_NOT_YET_RUN")
        (self.directory/"summary.json").write_text(json.dumps({"T0": {"status": T0_status,
            "synthetic": {"status": "PASS"}, "backend": {str(parent): {"status": "PASS"} for parent in BACKEND_PARENTS}}}))
        self.events.clear()


class AnatomyFlowTests(unittest.TestCase):
    def test_fixed_first_middle_last_validation_precedes_all_G_and_all_25_G_precede_PG(self):
        with tempfile.TemporaryDirectory(prefix="a21_flow_order_") as temporary:
            fixture = FlowFixture(temporary)
            with fixture.mocks():
                result = fixture.run()
            preparation = [event[1] for event in fixture.events if event[0] == "prepare"]
            validation = [event[1] for event in fixture.events if event[0] == "validate"]
            self.assertEqual(preparation, [2001, 2003, 2013, 2005, 2007])
            self.assertEqual(validation, list(BACKEND_PARENTS))
            first_evaluation = next(index for index,event in enumerate(fixture.events) if event[0] == "evaluate")
            self.assertTrue(all(fixture.events.index(("validate", parent)) < first_evaluation for parent in BACKEND_PARENTS))
            self.assertTrue(all(fixture.events.index(("save", parent)) < first_evaluation for parent in PARENTS))
            evaluations = [event for event in fixture.events if event[0] == "evaluate"]
            self.assertEqual(len(evaluations), 35)
            self.assertEqual({event[2] for event in evaluations[:25]}, set(G_ARMS))
            self.assertEqual({event[2] for event in evaluations[25:]}, set(PG_ARMS))
            self.assertEqual([event[1] for event in evaluations[::5][:5]], list(PARENTS))
            self.assertEqual(len({(event[1], event[2]) for event in evaluations}), 35)
            self.assertEqual(result["reduced_QPs_attempted"], 35)
            self.assertEqual(result["status"], "COMPLETE")
            self.assertEqual(len(fixture.latest()), 35)

    def test_rank_core_QP_or_consistency_failure_blocks_all_PG_and_preserves_failure(self):
        cases = ((RankBudgetInfeasible("fixture-protected-overflow"), "RANK_BUDGET_INFEASIBLE"),
                 (UnsafeCore("fixture-unsafe-core"), "UNSAFE_CORE"),
                 (QPFailure("fixture-unsolved-QP"), "QP_FAILED"),
                 (ConsistencyFailure("fixture-bound-violation"), "FAILED"))
        for failure, status in cases:
            with self.subTest(status=status), tempfile.TemporaryDirectory(prefix="a21_flow_G_failure_") as temporary:
                fixture = FlowFixture(temporary, failures={(2003, "PRIMAL_G"): failure})
                with fixture.mocks():
                    if isinstance(failure, ConsistencyFailure):
                        with self.assertRaisesRegex(ConsistencyFailure, "fixture-bound"):
                            fixture.run()
                        result = json.loads((fixture.directory/"summary.json").read_text())
                    else:
                        result = fixture.run()
                latest = fixture.latest()
                self.assertEqual(latest[(2003, "PRIMAL_G")]["status"], status)
                self.assertIn(str(failure), latest[(2003, "PRIMAL_G")]["failure_reason"])
                self.assertFalse(result["G_all_five_consistent"])
                self.assertFalse(result["PG_prerequisite_satisfied"])
                self.assertTrue(all(latest[(parent, arm)]["status"] == "NOT_RUN" for parent in PARENTS for arm in PG_ARMS))
                self.assertFalse(any(event[0] == "evaluate" and event[2] in PG_ARMS for event in fixture.events))
                self.assertEqual(len(latest), 35)

    def test_cache_only_PG_reads_existing_banks_without_Adapter_preparation_or_new_T0(self):
        with tempfile.TemporaryDirectory(prefix="a21_flow_cache_only_") as temporary:
            fixture = FlowFixture(temporary, stage="petrov")
            fixture.seed_completed_G()
            prior = (fixture.directory/"rows.jsonl").read_bytes()
            with fixture.mocks(forbid_preparation=True):
                result = fixture.run("a21-synthetic-cache-PG")
            evaluations = [event for event in fixture.events if event[0] == "evaluate"]
            self.assertEqual(len(evaluations), 10)
            self.assertTrue(all(event[2] in PG_ARMS for event in evaluations))
            self.assertEqual([event[1] for event in fixture.events if event[0] == "load"], list(PARENTS))
            self.assertEqual(result["reduced_QPs_attempted"], 35)
            self.assertEqual(result["status"], "COMPLETE")
            self.assertTrue((fixture.directory/"rows.jsonl").read_bytes().startswith(prior))
            self.assertEqual(len(fixture.rows()), 45)  # preserve ten earlier NOT_RUN records
            self.assertEqual(len(fixture.latest()), 35)

    def test_invalid_T0_or_incomplete_G_stops_cache_only_PG_before_any_evaluation(self):
        for cause in ("invalid_T0", "incomplete_G"):
            with self.subTest(cause=cause), tempfile.TemporaryDirectory(prefix="a21_flow_invalid_gate_") as temporary:
                fixture = FlowFixture(temporary, stage="petrov")
                fixture.seed_completed_G(T0_status="FAILED" if cause == "invalid_T0" else "PASS")
                if cause == "incomplete_G":
                    rows = fixture.rows()
                    for row in rows:
                        if (row["parent_id"], row["arm"]) == (2013, "RANDOM_G"):
                            row.update(status="NOT_RUN", consistency_passed=False, QP_valid=False)
                    (fixture.directory/"rows.jsonl").write_text("".join(json.dumps(row)+"\n" for row in rows))
                with fixture.mocks(forbid_preparation=True):
                    with self.assertRaisesRegex(AnatomyInputError, "REQUIRES_COMPLETE_CONSISTENT_G_AND_T0"):
                        fixture.run()
                self.assertFalse(any(event[0] in ("load", "evaluate", "prepare") for event in fixture.events))
                latest = fixture.latest()
                self.assertTrue(all(latest[(parent, arm)]["status"] == "NOT_RUN" for parent in PARENTS for arm in PG_ARMS))
                self.assertEqual(len(latest), 35)

    def test_35_QP_cap_uses_recorded_attempts_and_blocks_a_new_call(self):
        with tempfile.TemporaryDirectory(prefix="a21_flow_QP_cap_") as temporary:
            fixture = FlowFixture(temporary, stage="petrov")
            fixture.seed_completed_G(cap_already_used=True)
            with fixture.mocks(forbid_preparation=True):
                with self.assertRaisesRegex(AnatomyInputError, "QP_CAP_EXHAUSTED"):
                    fixture.run()
            self.assertFalse(any(event[0] == "evaluate" for event in fixture.events))
            result = json.loads((fixture.directory/"summary.json").read_text())
            self.assertEqual(result["reduced_QPs_attempted"], 35)
            self.assertEqual(fixture.latest()[(2001, "BOTH_PG")]["status"], "FAILED")
            self.assertIn("QP_CAP_EXHAUSTED", result["stopped_reason"])

    def test_backend_T0_failure_is_saved_and_blocks_G_and_PG(self):
        with tempfile.TemporaryDirectory(prefix="a21_flow_backend_T0_") as temporary:
            fixture = FlowFixture(temporary, backend_failure=2003)
            with fixture.mocks():
                with self.assertRaisesRegex(ConsistencyFailure, "REGISTERED_BACKEND_FAILURE"):
                    fixture.run()
            self.assertEqual([event[1] for event in fixture.events if event[0] == "prepare"], [2001, 2003])
            self.assertFalse(any(event[0] == "evaluate" for event in fixture.events))
            saved = json.loads((fixture.directory/"caches/2003_17.json").read_text())
            self.assertEqual(saved["backend_validation"]["status"], "FAILED")
            self.assertEqual(fixture.latest()[(2003, "BASE_G")]["status"], "FAILED")
            self.assertEqual(len(fixture.latest()), 35)

    def test_synthetic_T0_failure_prevents_state_preparation_and_retains_full_manifest(self):
        with tempfile.TemporaryDirectory(prefix="a21_flow_synthetic_T0_") as temporary:
            fixture = FlowFixture(temporary)
            with fixture.mocks(synthetic_failure=ConsistencyFailure("fixture-invalid-synthetic-T0")):
                with self.assertRaisesRegex(ConsistencyFailure, "invalid-synthetic"):
                    fixture.run()
            self.assertFalse(any(event[0] in ("prepare", "validate", "evaluate") for event in fixture.events))
            self.assertEqual(len(fixture.latest()), 35)
            self.assertEqual(json.loads((fixture.directory/"summary.json").read_text())["T0"]["status"], "FAILED")

    def test_failed_attempt_is_immutable_and_an_automatic_retry_never_reaches_a_worker(self):
        with tempfile.TemporaryDirectory(prefix="a21_flow_failed_attempt_") as temporary:
            fixture = FlowFixture(temporary, failures={(2001, "PRIMAL_G"): QPFailure("fixture-paid-failure")})
            with fixture.mocks():
                fixture.run("a21-synthetic-first-attempt")
            original = (fixture.directory/"rows.jsonl").read_bytes()
            failed = fixture.latest()[(2001, "PRIMAL_G")]
            self.assertEqual(failed["status"], "QP_FAILED")
            self.assertEqual(failed["cost"]["counts"]["a21_reduced_qps"], 1)
            fixture.events.clear()
            fixture.failures.clear()
            with fixture.mocks():
                with self.assertRaisesRegex(AnatomyInputError, "PREVIOUS_FAILED_ARMS_REQUIRE_EXPLICIT_INSPECTION"):
                    fixture.run("a21-synthetic-forbidden-retry")
            self.assertFalse(any(event[0] in ("prepare", "validate", "evaluate", "load") for event in fixture.events))
            self.assertEqual((fixture.directory/"rows.jsonl").read_bytes(), original)
            self.assertEqual(fixture.latest()[(2001, "PRIMAL_G")], failed)

    def test_budget_stop_retains_paid_attempt_and_all_remaining_state_arm_rows(self):
        with tempfile.TemporaryDirectory(prefix="a21_flow_budget_stop_") as temporary:
            fixture = FlowFixture(temporary, failures={(2005, "DUAL_G"): BudgetExceeded("fixture-budget-stop")})
            with fixture.mocks():
                with self.assertRaisesRegex(BudgetExceeded, "fixture-budget-stop"):
                    fixture.run()
            latest = fixture.latest()
            self.assertEqual(latest[(2005, "DUAL_G")]["status"], "STOPPED")
            self.assertEqual(latest[(2005, "DUAL_G")]["cost"]["counts"]["a21_reduced_qps"], 1)
            self.assertEqual(len(latest), 35)
            self.assertTrue(all(latest[(parent, arm)]["status"] == "NOT_RUN" for parent in PARENTS for arm in PG_ARMS))
            self.assertIn("BudgetExceeded", json.loads((fixture.directory/"summary.json").read_text())["stopped_reason"])


if __name__ == "__main__":
    unittest.main()
