"""Regression for a vanishing stationarity scale in offline reporting."""
import unittest

from a21.report import annotate_rows
from test_a21_core import report_fixture


class ReportAllowanceTests(unittest.TestCase):
    config = {"parents": [2001], "iterations": [17], "current_rank": 56,
              "retained_rank": 8, "identity_rtol": 1e-9}

    def test_exact_oracle_small_absolute_defect_survives_relative_quotient(self):
        records = report_fixture()
        records[0].update(identity_error_norm=2e-16, identity_allowance=2e-14,
                          identity_relative_error=1e-3)
        row = annotate_rows(records, self.config)[0]
        self.assertTrue(row["assessable"])
        self.assertEqual(row["identity_validation_source"],
                         "SAVED_ABSOLUTE_ERROR_AND_FROZEN_ALLOWANCE")

    def test_relative_quotient_cannot_hide_absolute_allowance_violation(self):
        records = report_fixture()
        records[0].update(identity_error_norm=3e-14, identity_allowance=2e-14,
                          identity_relative_error=1e-12)
        row = annotate_rows(records, self.config)[0]
        self.assertFalse(row["assessable"])
        self.assertIn("DEFECT_IDENTITY_NOT_VALIDATED", row["report_issue_classes"])

    def test_raw_and_allowance_adjusted_ratios_remain_distinct(self):
        records = report_fixture()
        records[0].update(absolute_H_step_error=1e-8, bound_HF=1e-11,
                          bound_ratio=1000., normal_adjusted_bound_HF=2e-8,
                          bound_floating_allowance=1e-9)
        row = annotate_rows(records, self.config)[0]
        self.assertEqual(row["bound_ratio"], 1000.)
        self.assertAlmostEqual(row["extended_bound_ratio"], 1e-8/2.1e-8)


if __name__ == "__main__":
    unittest.main()
