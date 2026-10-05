"""No physics: complete-cohort reference and actual-failure gate regression."""
import json
from pathlib import Path
import tempfile
import unittest

from a20.cli import eligibility


class ReferenceGateTests(unittest.TestCase):
    def setUp(self):
        self.config = {'parents': [2001, 2005, 2003, 2007, 2010, 2013],
                       'replay_iterations': [0, 17], 'live_degrees': [0, 1, 2, 3],
                       'replay_median_H_error_gate': 0.05}
        self.rows = [dict(parent_object_id=p, iteration=i, degree=d,
                          method='mixed', status='OK', relative_H_step_error=0.01,
                          reference_status='VERIFIED_NEW_CONSTRAINED_REFERENCE')
                     for p in self.config['parents'] for i in (0, 17) for d in range(4)]

    def decision(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            folder = root/'results/replay'
            folder.mkdir(parents=True)
            (folder/'replay.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in self.rows))
            return eligibility(root, self.config)

    def test_complete_valid_reference_passes(self):
        self.assertEqual(self.decision()['status'], 'PASS')

    def test_failed_solver_and_missing_reference_stays_hold(self):
        for row in self.rows:
            if row['parent_object_id'] == 2010:
                row.update(status='FAILED', relative_H_step_error=None,
                           reference_status='MISSING_CONSTRAINED_REFERENCE')
        result = self.decision()
        self.assertEqual(result['status'], 'HOLD')
        self.assertEqual(result['eligible'], [])
        for result in result['degrees'].values():
            self.assertEqual(result['method_validation_status'], 'FAIL')
            self.assertEqual(result['observed_failures'], 2)
            self.assertEqual(len(result['missing_reference_states']), 2)
            self.assertIsNone(result['median_relative_H_step_error'])

    def test_actual_failure_with_valid_reference_remains_fail(self):
        for row in self.rows:
            if row['parent_object_id'] == 2010:
                row.update(status='FAILED', relative_H_step_error=None)
        self.assertEqual(self.decision()['status'], 'FAIL')

    def test_missing_state_is_hold(self):
        self.rows = [r for r in self.rows if r['parent_object_id'] != 2010]
        self.assertEqual(self.decision()['status'], 'HOLD')

    def test_duplicate_state_is_hold(self):
        self.rows.extend([r.copy() for r in self.rows if r['parent_object_id'] == 2010])
        self.assertEqual(self.decision()['status'], 'HOLD')


if __name__ == '__main__':
    unittest.main()
