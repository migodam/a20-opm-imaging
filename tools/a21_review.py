"""Independent, CPU-only recheck of the already paid A21 saved arrays.

No Adapter, Maxwell operator, full LU, optimizer or truth is imported here.
All failures and CPU are preserved in a unique job, including imports.
"""
from __future__ import annotations
import time
START = time.perf_counter()
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
import numpy as np
from scipy import linalg as la
from a21.budget import A21Book, load_config, history
from a21.cli import source_identity

ARMS = ['BASE_G', 'PRIMAL_G', 'DUAL_G', 'BOTH_G', 'RANDOM_G', 'BOTH_PG', 'RANDOM_PG']


def check_close(a, b, label, tol=1e-9):
    error = float(la.norm(np.asarray(a)-np.asarray(b)))
    scale = max(float(la.norm(a)), float(la.norm(b)))
    allowance = tol*scale + 100*np.finfo(float).eps*max(1., scale)
    if error > allowance:
        raise ValueError(label + '_SAVED_ARRAY_IDENTITY_FAILURE')
    return {'absolute': error, 'scale': scale, 'allowance': allowance}


def audit(root, cfg, book):
    out = root / 'results/a21'
    rows = [json.loads(s) for s in (out/'anatomy/rows.jsonl').read_text().splitlines() if s]
    expected = [(p, a) for p in cfg['parents'] for a in ARMS]
    if len(rows) != 35 or set((v['parent_id'], v['arm']) for v in rows) != set(expected):
        raise ValueError('INCOMPLETE_OR_DUPLICATE_FIVE_STATE_GRID')
    if [(v['parent_id'], v['arm']) for v in rows[:25]] != [(p, a) for p in cfg['parents'] for a in ARMS[:5]]:
        raise ValueError('GALERKIN_BEFORE_PETROV_ORDER_CONFLICT')
    summary = json.loads((out/'anatomy/summary.json').read_text())
    if summary['T0']['status'] != 'PASS' or any(summary['T0']['backend'][str(p)]['status'] != 'PASS' for p in cfg['validation_parents']):
        raise ValueError('REAL_AND_SYNTHETIC_T0_NOT_PASS')
    reports = []
    for pid in cfg['parents']:
        book.check()
        cpath = out/'anatomy/caches'/f'{pid}_17.npz'
        c = dict(np.load(cpath, allow_pickle=False))
        meta = json.loads(cpath.with_suffix('.json').read_text())
        original = np.load(root/'data/runtime'/str(pid)/'state_17.npz', allow_pickle=False)
        check_close(c['x'], original['chi'], 'FROZEN_CHI')
        check_close(c['ell'], original['ell'], 'FROZEN_ELL')
        check_close(c['lam'], original['lambda_total'], 'FROZEN_LAMBDA')
        if meta['reference_repaired']:
            raise ValueError('REFERENCE_REPAIR_REQUIRES_SEPARATE_PARENT_REVIEW')
        saved_reference = np.load(root/'results/replay/steps'/Path(meta['canonical_reference_local_path'].replace('\\', '/')).name, allow_pickle=False)['step']
        check_close(c['sF'], saved_reference, 'RAW_CONSTRAINED_REFERENCE')
        state_rows = [v for v in rows if v['parent_id'] == pid]
        by_arm = {v['arm']: v for v in state_rows}
        for arm, random in [('BOTH_G', 'RANDOM_G'), ('BOTH_PG', 'RANDOM_PG')]:
            for key in ('k_Z', 'k_W', 'retained_rank'):
                if by_arm[arm][key] != by_arm[random][key]:
                    raise ValueError('FIXED_RANK_CONTROL_MISMATCH')
            for side in (['trial_QR'] if arm == 'BOTH_G' else ['trial_QR', 'test_QR']):
                if by_arm[arm][side]['independent_protected_added_rank'] != by_arm[random][side]['independent_protected_added_rank']:
                    raise ValueError('ACTUAL_ADDED_RANK_CONTROL_MISMATCH')
        for row in state_rows:
            if row['status'] != 'OK' or not row['consistency_passed']:
                raise ValueError('NONVALID_EXECUTED_ARM')
            arm = row['arm']
            with book.span('a21_saved_array_review', saved_arm_vector_audits=1):
                v = dict(np.load(out/'anatomy/diagnostics'/f'{pid}_17_{arm}.npz', allow_pickle=False))
                JF, JR, SF, SR, r = (v[k] for k in ['J_F', 'J_R', 's_F', 's_R', 'r'])
                identity = {}
                for key, actual in [('J_F', c['JF']), ('s_F', c['sF']), ('r', c['r']), ('ell', c['ell']), ('Lambda', c['Lambda'])]:
                    identity[key] = check_close(v[key], actual, key)
                for key, J in [('H_F', JF), ('H_R', JR)]:
                    identity[key] = check_close(v[key], J.T@J+v['Lambda'], key)
                    if la.eigvalsh(v[key])[0] <= 0:
                        raise ValueError('NON_SPD_SAVED_HESSIAN')
                TZ, TW = v['TZ'], v['TW']
                identity['Z'] = check_close(v['Z'], c['D']@TZ, 'RAW_QR_TRIAL')
                identity['W'] = check_close(v['W'], c['D']@TW, 'RAW_QR_TEST')
                core = TW.conj().T @ c['DHDL'] @ TZ
                identity['core'] = check_close(v['core'], core, 'CACHED_CORE')
                WB = np.einsum('bk,pbd->pkd', TW.conj(), c['DHB'])
                coeff = la.solve(core, WB.transpose(1, 0, 2).reshape(56, -1)).reshape(56, 6, 54).transpose(1, 0, 2)
                data = np.einsum('mk,pkd->pmd', c['SD']@TZ, coeff)
                rebuilt = np.vstack([part for source in data for part in (source.real, source.imag)])*float(c['whitening'])
                identity['JR_from_paid_images'] = check_close(JR, rebuilt, 'FROZEN_SMALL_MODEL')
                eF = r + JF@SF
                dp, dd = (JR-JF)@SF, (JR-JF).T@eF
                ap = JR.T@dp
                rhoF = JF.T@eF+v['Lambda']@SF+v['ell']+v['n_F']
                rhoR = JR.T@(r+JR@SR)+v['Lambda']@SR+v['ell']+v['n_R']
                eta = rhoF+dd+ap-rhoR
                for key, actual in [('e_F', eF), ('delta_p', dp), ('delta_d', dd), ('amplified_primal', ap), ('rho_F', rhoF), ('rho_R', rhoR), ('eta_pair', eta)]:
                    identity[key] = check_close(v[key], actual, key)
                for suffix, step in [('F', SF), ('R', SR)]:
                    slack = c['A']@step-c['lower']
                    mu = v['multipliers_'+suffix]
                    check_close(v['slack_'+suffix], slack, 'SAVED_SLACK')
                    check_close(v['n_'+suffix], -c['A'].T@mu, 'INDEPENDENT_NORMAL_REPRESENTATION')
                    if np.min(mu) < -100*np.finfo(float).eps or np.min(slack) < -cfg['feasibility_tolerance']:
                        raise ValueError('NORMAL_SIGN_OR_FEASIBILITY')
                HF, HR = v['H_F'], v['H_R']
                beta = float(la.eigh(HF, HR, eigvals_only=True)[-1])
                b = float(np.sqrt(max(0., eta@la.solve(HR, eta, assume_a='pos'))))
                err = float(np.sqrt((SR-SF)@HF@(SR-SF)))
                identity['beta'] = check_close(beta, row['beta'], 'SYMMETRIC_BETA')
                identity['raw_bound'] = check_close(np.sqrt(beta)*b, row['bound_HF'], 'SOLVER_AWARE_BOUND')
                identity['H_error'] = check_close(err, row['absolute_H_step_error'], 'H_ERROR')
                if err > row['normal_adjusted_bound_HF']+row['bound_floating_allowance']:
                    raise ValueError('TRUE_BOUND_VIOLATION')
                q = lambda J,s: .5*np.linalg.norm(r+J@s)**2+v['ell']@s+.5*s@v['Lambda']@s
                gap = q(JF,SR)-q(JF,SF)
                decomposition = .5*err**2-v['n_F']@(SR-SF)+rhoF@(SR-SF)
                identity['full_gap'] = check_close(gap, row['full_quadratic_gap'], 'FULL_GAP')
                identity['full_gap_decomposition'] = check_close(gap, decomposition, 'FULL_GAP_WITH_SOLVER_DEFECT')
                dual_b = np.sqrt(max(0., dd@la.solve(HR,dd,assume_a='pos')))
                solver_b = np.sqrt(max(0., (rhoF-rhoR)@la.solve(HR,rhoF-rhoR,assume_a='pos')))
                reports.append(dict(parent_id=pid, arm=arm, status='PASS', identities=identity,
                                    independent_weighted_solver_defect=float(solver_b),
                                    weighted_solver_to_dual_ratio=float(solver_b/dual_b) if dual_b else None,
                                    vector_file=f'anatomy/diagnostics/{pid}_17_{arm}.npz'))
    return dict(status='PASS', checked_arm_states=len(reports), offline_only=True,
                QP_calls=0, Maxwell_actions=0, full_RHS=0, truth_read=False,
                reports=reports)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--job', required=True)
    args=parser.parse_args()
    if not args.job.startswith('a21-') or not args.job.replace('-', '').replace('_', '').isalnum():
        raise ValueError('INVALID_AUDIT_JOB_ID')
    cfg=load_config(ROOT)
    directory=ROOT/'results/jobs'/args.job
    directory.mkdir(exist_ok=False)
    book=A21Book(ROOT,cfg,directory/'cost.jsonl',device='cpu',epilogue=True,job_cpu_limit=120)
    book.started_wall=START
    identity=source_identity(ROOT,cfg,required=True)
    book.metadata={'job':args.job, **identity}
    status='FAILED'
    try:
        result=audit(ROOT,cfg,book)
        book.check()
        status='COMPLETE'
    except BaseException as error:
        result={'status':'FAILED','error_type':type(error).__name__,'reason':str(error)}
    finally:
        for path, value in [(ROOT/'results/a21/INDEPENDENT_ARRAY_REVIEW.json',result), (directory/'result.json',result)]:
            path.write_text(json.dumps(value,indent=2)+'\n')
        receipt=book.receipt()|identity|{'job':args.job,'status':status,'stage':'offline_saved_array_review','command':sys.argv}
        (directory/'job_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
        (ROOT/'results/a21/BUDGET_CURRENT.json').write_text(json.dumps(history(ROOT),indent=2)+'\n')
        print(json.dumps({'job':args.job,'status':status,'CPU':receipt['process_cpu_seconds'],'GPU':0}))
    return 0 if status=='COMPLETE' else 2


if __name__ == '__main__':
    raise SystemExit(main())
