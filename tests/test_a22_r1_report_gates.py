import copy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

import numpy as np

from a22_r1.report import decide, method_screening, METHODS
from a22_r1.replay import SCENES, _cached_quadratic_validation, _identity, ReplayContractError

CONFIG=json.loads((Path(__file__).parents[1]/'configs/a22_r1.json').read_text())


def scene_rows(a3=.4,a2=.6):
    rows=[]
    for sid in SCENES:
        for method in METHODS:
            for test in ('A','B'):
                p=a3 if method=='A3' else a2 if method=='A2' else .7
                ratio=1.2/p
                fp=(p*p)/(p*p+1.2**2)
                rows.append(dict(scene=sid,method=method,k=16,test=test,complete=True,
                    nrmse_phys=p,nrmse_prior=1.2,s_sep=ratio,f_truth_phys=.5,
                    f_error_prior=1-fp,q_phys=fp/.5,q_prior=(1-fp)/.5))
    return rows


class GateContracts(unittest.TestCase):
    def test_case_A_still_never_formal_PASS_or_NN(self):
        g=decide(scene_rows(),CONFIG,numerical_complete=True)
        self.assertEqual(g['scientific_case'],'CASE_A_A3_SPLIT_WORKS')
        self.assertFalse(g['formal_PASS']);self.assertEqual(g['NN'],'NOT_RUN')

    def test_A2_equal_is_case_C(self):
        g=decide(scene_rows(a3=.6),CONFIG,numerical_complete=True)
        self.assertEqual(g['scientific_case'],'CASE_C_A2_MATCHES_OR_BEATS_A3')
        self.assertEqual(g['gates']['S2'],'FAIL')

    def test_missing_scene_cannot_be_filtered_for_support(self):
        rows=[r for r in scene_rows() if r['scene']!=2009]
        g=decide(rows,CONFIG,numerical_complete=True)
        self.assertEqual(g['scientific_case'],'INCOMPLETE')
        self.assertFalse(g['bootstrap']['complete'])

    def test_bad_KKT_prerequisite_cannot_pass(self):
        g=decide(scene_rows(),CONFIG,numerical_complete=False)
        self.assertEqual(g['scientific_case'],'INCOMPLETE')

    def test_floor_dependence_is_explicit_not_PASS(self):
        g=decide(scene_rows(),CONFIG,numerical_complete=True,floor_case_count=1)
        self.assertEqual(g['scientific_case'],'INCOMPLETE')

    def test_S4_is_ratio_of_scene_means_and_median_scenes(self):
        rows=scene_rows()
        for row in rows:
            if row['method']=='A3' and row['test']=='B':
                row['nrmse_phys']*=2 if row['scene']==2009 else 1.1
        m=method_screening(rows,'A3',CONFIG)
        self.assertAlmostEqual(m['median_restricted_over_common'],1.1)
        self.assertEqual(m['S4'],'SUPPORT')

    def test_secondary_k_does_not_select_primary(self):
        rows=scene_rows(a3=.6)
        extra=copy.deepcopy(rows)
        for row in extra:
            row['k']=8;row['nrmse_phys']=.0001
        g=decide(rows+extra,CONFIG,numerical_complete=True)
        self.assertEqual(g['scientific_case'],'CASE_C_A2_MATCHES_OR_BEATS_A3')


class CachedQPContracts(unittest.TestCase):
    def setUp(self):
        self.row=dict(scene_id=2001,family='gaussian',direction_id=0,amplitude_level=0,
            amplitude=.01,noise_level=0.,noise_draw=0,intervention='nominal',noise_seed='seed',candidate_index=0)
        self.label=SimpleNamespace(truth=np.zeros(32))
        self.cache=SimpleNamespace(AW=np.eye(32),lam=1.)
        self.geometry=(2*np.eye(32),np.eye(32),np.zeros(32))
        self.d=np.ones(32)
        self.record=dict(case_key=_identity(self.row)['case_key'],status='OK',lambda_value=1.,
            x_hat=np.full(32,.5).tolist(),x_true=np.zeros(32).tolist(),material_normal=np.zeros(32).tolist(),
            qp=dict(quadratic_value=-8.,kkt_relative=0.,feasibility_violation=0.))

    def audit(self):
        return _cached_quadratic_validation(self.record,self.row,self.label,self.cache,CONFIG,self.d,self.geometry)

    def test_valid_point_reused_without_new_solver(self):
        _,audit=self.audit();self.assertEqual(audit['status'],'VALID')

    def test_saved_quadratic_must_match(self):
        self.record['qp']['quadratic_value']=-7.
        with self.assertRaises(ReplayContractError):self.audit()

    def test_normal_not_replaced_by_minus_gradient(self):
        self.record['x_hat'][0]=.6
        self.record['material_normal'][0]=-.2
        self.record['qp']['quadratic_value']=-7.99
        with self.assertRaises(ReplayContractError):self.audit()

    def test_infeasible_point_rejected(self):
        self.record['x_hat'][0]=-.1
        with self.assertRaises(ReplayContractError):self.audit()

    def test_truth_or_lambda_change_rejected(self):
        self.record['lambda_value']=.5
        with self.assertRaises(ReplayContractError):self.audit()


if __name__=='__main__':unittest.main()
