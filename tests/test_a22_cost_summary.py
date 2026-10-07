"""Small recorded-accounting fixtures; worker has not executed these tests."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from a22.cost_summary import NOT_MEASURED, export_cost_csv, summarize_costs


def _json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row)+"\n" for row in rows), encoding="utf-8")


def _receipt(job="a22-example", **extra):
    record = dict(campaign="A22", job_id=job, status="FAILED", stage="features",
                  wall_seconds=12., process_cpu_seconds=10., gpu_occupation_seconds=4.,
                  counts={"F_actions":3, "F_adjoint_actions":2, "L_actions":1,
                          "L_adjoint_actions":4, "Maxwell_matvec_rhs":10,
                          "B_rhs":6, "B_adjoint_rhs":6, "S_actions":2,
                          "S_adjoint_actions":2, "full_forward_RHS":6,
                          "full_LU_factorizations":1, "data_generation_F_calls":1,
                          "same_material_full_state_cache_hits":1})
    record.update(extra)
    return record


class CostSummaryChecks(unittest.TestCase):
    def test_only_unique_A22_receipts_charge_resources_and_generic_rhs_is_not_added(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            directory = root / "results/jobs/a22-example"
            _json(directory / "job_receipt.json", _receipt())
            _json(directory / "accounting_checkpoint.json", _receipt(process_cpu_seconds=999.))
            _json(root / "results/jobs/a21-old/job_receipt.json", _receipt("a21-old", process_cpu_seconds=1e6))
            _json(root / "results/jobs/a22-foreign/job_receipt.json", _receipt("a22-foreign", campaign="A21", process_cpu_seconds=1e6))
            _json(root / "COST_LEDGER.json", {"process_cpu_seconds":1e6})
            # The mirror must never charge the same job again.
            _jsonl(root / "results/a22/COST_LEDGER.jsonl", [dict(event="job_receipt", **_receipt())])
            _jsonl(directory / "cost.jsonl", [
                dict(campaign="A22", job_id="a22-example", event="outer", status="OK",
                     wall_seconds=12., process_cpu_seconds=10., counters={}),
                dict(campaign="A22", job_id="a22-example", event="inner", status="OK",
                     wall_seconds=8., process_cpu_seconds=8., counters={"F_actions":3}),
                dict(campaign="A22", job_id="a22-example", event="a22_expected_core_rejection",
                     event_id="unsafe-1", status="FAILED", error_type="UnsafeCore",
                     process_cpu_seconds=.5, counters={"expected_invalid_core_probes":1}),
            ])
            external = dict(scope="a22-source", process_cpu_seconds=2., wall_seconds=1.,
                            gpu_occupation_seconds=0., status="SOURCE_WORK_CONSERVATIVE", counts={})
            _json(root / "results/a22/external_cpu_receipts.json", [external, dict(external),
                dict(scope="source-a21-old", campaign="A21", process_cpu_seconds=1e6)])
            summary = summarize_costs(root)
            self.assertEqual(summary["resource_totals"]["process_cpu_seconds"]["value"], 12.)
            self.assertEqual(summary["resource_totals"]["gpu_occupation_seconds"]["value"], 4.)
            self.assertEqual(summary["resource_totals"]["wall_seconds"]["value"], 13.)
            actions = summary["action_accounting"]
            self.assertEqual(actions["F_vectors"]["recorded_sum"], 3)
            self.assertEqual(actions["exclusive_F_Fstar_L_Lstar"]["recorded_sum"], 10)
            self.assertEqual(actions["Maxwell_matvec_rhs_aggregate"]["recorded_sum"], 10)
            self.assertFalse(actions["Maxwell_matvec_rhs_aggregate"]["included_in_exclusive_vector_sum"])
            self.assertFalse(actions["span_counter_totals_added_to_receipt_totals"])
            unsafe = next(row for row in summary["rows"] if row["event_id"] == "unsafe-1")
            self.assertEqual(unsafe["status"], "FAILED")
            self.assertTrue(unsafe["expected_unsafe_core"])
            self.assertFalse(unsafe["resource_additive"])
            self.assertTrue(summary["cache_hit_records"])
            self.assertEqual(sum(row["record_type"] == "duplicate_external_receipt" for row in summary["rows"]), 1)

    def test_checkpoint_is_provisional_and_conflicting_external_scope_does_not_choose_a_cost(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            _json(root / "results/jobs/a22-live/accounting_checkpoint.json",
                  _receipt("a22-live", status="RUNNING", process_cpu_seconds=5.,
                           wall_seconds=5., gpu_occupation_seconds=0.))
            first = summarize_costs(root)
            self.assertEqual(first["resource_totals"]["process_cpu_seconds"]["value"], 5.)
            self.assertEqual(first["resource_totals"]["process_cpu_seconds"]["status"], "PROVISIONAL")
            self.assertEqual(first["live_jobs"], ["a22-live"])
            _json(root / "results/a22/external_cpu_receipts.json", [
                dict(scope="a22-conflict", process_cpu_seconds=1., gpu_occupation_seconds=0.),
                dict(scope="a22-conflict", process_cpu_seconds=2., gpu_occupation_seconds=0.),
            ])
            summary = summarize_costs(root)
            self.assertEqual(summary["resource_totals"]["process_cpu_seconds"]["value"], NOT_MEASURED)
            self.assertEqual(summary["resource_totals"]["process_cpu_seconds"]["recorded_sum"], 5.)
            self.assertTrue(any(issue["kind"] == "CONFLICTING_EXTERNAL_SCOPE" for issue in summary["issues"]))

    def test_missing_receipt_never_promotes_span_CPU_to_job_cost_and_export_marks_missing(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            _jsonl(root / "results/jobs/a22-unfinished/cost.jsonl", [
                dict(campaign="A22", job_id="a22-unfinished", event="nested_only",
                     status="FAILED", process_cpu_seconds=3., counters={"L_actions":2}),
            ])
            summary = export_cost_csv(root)
            self.assertEqual(summary["resource_totals"]["process_cpu_seconds"]["value"], NOT_MEASURED)
            self.assertEqual(summary["resource_totals"]["gpu_occupation_seconds"]["value"], NOT_MEASURED)
            csv_path = root / "results/a22/cost_ledger.csv"
            json_path = root / "results/a22/ACTION_ACCOUNTING.json"
            with csv_path.open(newline="") as stream:
                rows = list(csv.DictReader(stream))
            span = next(row for row in rows if row["event"] == "nested_only")
            self.assertEqual(span["process_cpu_seconds"], "3.0")
            self.assertEqual(span["full_adjoint_RHS"], NOT_MEASURED)
            accounting = json.loads(json_path.read_text())
            self.assertFalse(accounting["policy"]["CPU_and_GPU_resources_are_added_together"])
            self.assertEqual(accounting["policy"]["A0_A1_A2_separate_deployment_costs"], NOT_MEASURED)
            self.assertNotIn("rows", accounting)


if __name__ == "__main__":
    unittest.main()
