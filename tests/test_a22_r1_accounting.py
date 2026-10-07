import json
from pathlib import Path
import tempfile
import unittest

from a20.costs import BudgetExceeded
from a22_r1.accounting import R1Book, external_receipt, paid_history


class AccountingBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.config = dict(cpu_cap_seconds=1800., gpu_occupation_cap_seconds=600.,
            parent_a22_gpu_cap_seconds=32400., historical_a22_gpu_seconds=1350.71388,
            known_background_rebuild_cap=4)

    def tearDown(self):
        self.tmp.cleanup()

    def book(self, job='a22-r1-test'):
        return R1Book(self.root,self.config,job)

    def test_nested_spans_are_not_additive_receipts(self):
        book=self.book()
        with book.span('parent'):
            with book.span('child', small_QPs=1): pass
        receipt=book.finish('COMPLETE')
        paid=paid_history(self.root)
        self.assertEqual(paid['receipts'], ['a22-r1-test'])
        self.assertEqual(paid['cpu'], receipt['process_cpu_seconds'])
        self.assertEqual(receipt['counts']['small_QPs'],1)

    def test_new_labels_refused_before_count(self):
        book=self.book()
        with self.assertRaises(BudgetExceeded):
            with book.span('bad',data_generation_F_calls=1): self.fail('entered')
        self.assertEqual(book.counts.get('data_generation_F_calls',0),0)
        book.finish('COMPLETE')

    def test_four_background_limit_includes_paid_previous_job(self):
        book=self.book()
        with book.span('registered_known_anchor',full_forward_calls=4): pass
        book.finish('COMPLETE')
        next_book=self.book('a22-r1-second')
        with self.assertRaises(BudgetExceeded):
            with next_book.span('fifth',full_forward_calls=1): self.fail('entered')
        next_book.finish('BUDGET_REFUSED')
        self.assertEqual(paid_history(self.root)['backgrounds'],4)

    def test_teacher_and_full_j_are_not_online_capabilities(self):
        book=self.book()
        for action in ('truth','full_J','full_H','teacher','reference_step'):
            with self.assertRaises(BudgetExceeded):
                with book.action_guard(action): self.fail('entered')
        with book.action_guard('full_J',role='offline_evaluation'): pass
        with self.assertRaises(BudgetExceeded):
            with book.span('bad',full_J_material_directions=32): self.fail('entered')
        book.finish('COMPLETE')

    def test_duplicate_external_receipt_cannot_reset_budget(self):
        external_receipt(self.root,'source',cpu=2.)
        with self.assertRaises(ValueError): external_receipt(self.root,'source',cpu=2.)
        self.assertEqual(paid_history(self.root)['cpu'],2.)

    def test_same_job_output_is_not_overwritten(self):
        book=self.book();book.finish('COMPLETE')
        with self.assertRaises(FileExistsError): self.book()

    def test_budget_exhaustion_blocks_new_work(self):
        external_receipt(self.root,'already-paid',cpu=1800.)
        book=self.book()
        with self.assertRaises(BudgetExceeded):
            with book.span('work'): self.fail('entered')
        book.finish('BUDGET_REFUSED')


if __name__=='__main__': unittest.main()
