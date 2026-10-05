"""Mechanically decisive boundaries of the parent R1 launch/trajectory driver."""
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch
import numpy as np

from a20.costs import BudgetExceeded
from a20.backend import ForbiddenAccess
from a20_r1.budget import R1Book, history, register_external
from a20_r1.closed_loop import OwnPolicy, subtract_cost, VECTOR_KEYS
from a20_r1.seeds import AcceptedHistory


class BudgetDriverTests(unittest.TestCase):
    def _root(self, root):
        (root/'results/jobs/old').mkdir(parents=True)
        (root/'results/a20_r1').mkdir(parents=True)
        (root/'results/jobs/old/job_receipt.json').write_text(json.dumps(
            {'process_cpu_seconds':100.,'gpu_occupation_seconds':200.}))
        (root/'results/EXTERNAL_CPU_RECEIPTS.json').write_text('[{"process_cpu_seconds": 20}]')
        (root/'results/a20_r1/external_cpu_receipts.json').write_text('[]')

    def _config(self):
        return dict(budget_cpu_seconds=7200,budget_gpu_wall_seconds=43200,
            cpu_epilogue_reserve_seconds=0,gpu_preoperation_reserve_seconds=0,
            phase1_CPU_reserve=0,phase2_CPU_reserve=0,corrective_GPU_reserve=0,
            corrective_CPU_seconds=1500,corrective_GPU_seconds=4800,
            phase1_CPU_seconds=600,phase1_GPU_seconds=1200,
            phase2_CPU_seconds=900,phase2_GPU_seconds=3600)

    def test_inherited_accounting_and_no_reset_or_double_register(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);self._root(root)
            register_external(root,'implementation-check',3.)
            self.assertEqual(history(root)['global_cpu'],123.)
            self.assertEqual(history(root)['global_gpu'],200.)
            self.assertEqual(history(root)['phases']['phase1']['cpu'],3.)
            with self.assertRaises(ValueError):register_external(root,'implementation-check',3.)

    def test_phase_cap_blocks_before_physical_action(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);self._root(root)
            register_external(root,'already-paid-phase1',600.)
            book=R1Book(root,self._config(),'phase1',None)
            with self.assertRaises(BudgetExceeded):
                with book.span('L',L_actions=1):pass
            self.assertEqual(book.counts.get('L_actions',0),0)

    def test_teacher_full_tangent_denied_by_execution_capability(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);self._root(root)
            book=R1Book(root,self._config(),'phase1',None)
            with book.scope('legal_seed'):
                with self.assertRaises(ForbiddenAccess):
                    with book.span('full_adjoint',full_adjoint_RHS=6):pass
            self.assertEqual(book.counts.get('full_adjoint_RHS',0),0)

    def test_oracle_never_enters_closed_loop(self):
        with self.assertRaises(ValueError):OwnPolicy(2001,'ORACLE-M')

    def test_same_history_cannot_be_reused_as_new_accepted_update(self):
        class Chart:
            def project(self,value):return value
        class Adapter:
            p=2;chart=Chart()
            problem=type('P',(),{'parent_id':2001,'init':np.zeros(2)})()
        policy=OwnPolicy(2001,'FIXED-DEEP')
        previous=AcceptedHistory(2001,'FIXED-DEEP',1,np.array([.25,.5]))
        with patch('a20_r1.closed_loop.build_model',return_value='model'):
            self.assertEqual(policy(Adapter(),np.ones(2),None,np.zeros(1),previous,
                'FIXED-DEEP',3,{'prior':1.}),'model')
            with self.assertRaises(ValueError):
                policy(Adapter(),np.ones(2),None,np.zeros(1),previous,
                    'FIXED-DEEP',3,{'prior':1.})

    def test_exclusive_vector_receipt_does_not_include_aggregate_matvec(self):
        self.assertNotIn('Maxwell_matvec_rhs',VECTOR_KEYS)
        self.assertNotIn('full_tangent_receiver_rhs',VECTOR_KEYS)
        online=subtract_cost({'counts':{'L_actions':10,'full_tangent_RHS':12}},
                             {'counts':{'full_tangent_RHS':6}})
        self.assertEqual(sum(online['counts'].get(k,0) for k in VECTOR_KEYS),16)
        with self.assertRaises(ValueError):subtract_cost({'counts':{'L_actions':1}},
                                                        {'counts':{'L_actions':2}})


if __name__=='__main__':unittest.main()
