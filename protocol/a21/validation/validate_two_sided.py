#!/usr/bin/env python3
"""Standalone algebra tests, NOT the A20 Maxwell backend or its five late states.
Requires numpy and scipy. Uses exact active-set enumeration only for p=4 tests.
Run: python validation/validate_two_sided.py
"""
from __future__ import annotations
import itertools
import json
from pathlib import Path
import numpy as np
from scipy.linalg import eigh

ROOT = Path(__file__).resolve().parent
EPS = np.finfo(float).eps

def cn(rng, shape):
    return (rng.standard_normal(shape) + 1j*rng.standard_normal(shape))/np.sqrt(2.0)

def pack(z):
    return np.concatenate([z.real, z.imag], axis=0)

def normh(x, H):
    return float(np.sqrt(max(0.0, np.real(x.conj() @ H @ x))))

def normhi(x, H):
    return normh(x, np.linalg.solve(H, np.eye(len(x))))

def protected_basis(blocks, fillers, k, tol=1e-12):
    """Double MGS, never truncate an independent protected direction."""
    n = fillers.shape[0]
    cols = []
    def add(v):
        v = np.array(v, dtype=complex, copy=True)
        nv = np.linalg.norm(v)
        if nv == 0:
            return False
        for _ in range(2):
            if cols:
                Q = np.column_stack(cols)
                v -= Q @ (Q.conj().T @ v)
        if np.linalg.norm(v) <= tol*nv:
            return False
        cols.append(v/np.linalg.norm(v))
        return True
    for block in blocks:
        for v in block.T:
            add(v)
    if len(cols) > k:
        raise ValueError('Protected subspace exceeds fixed rank budget')
    for v in fillers.T:
        if len(cols) == k:
            break
        add(v)
    if len(cols) != k:
        raise ValueError('Insufficient independent fillers')
    return np.column_stack(cols).reshape(n, k)

def box_qp(H, g, lower, upper):
    """Global solution of a tiny SPD box QP by enumerating every face."""
    p = len(g)
    best = None
    for status in itertools.product((-1, 0, 1), repeat=p):
        status = np.asarray(status)
        fixed = np.flatnonzero(status != 0)
        free = np.flatnonzero(status == 0)
        s = np.zeros(p)
        s[status == -1] = lower[status == -1]
        s[status == 1] = upper[status == 1]
        if len(free):
            rhs = -g[free] - H[np.ix_(free, fixed)] @ s[fixed]
            s[free] = np.linalg.solve(H[np.ix_(free, free)], rhs)
        if np.any(s < lower - 1e-10) or np.any(s > upper + 1e-10):
            continue
        grad = H @ s + g
        if np.any(grad[status == -1] < -1e-9):
            continue
        if np.any(grad[status == 1] > 1e-9):
            continue
        if len(free) and np.max(np.abs(grad[free])) > 1e-8:
            continue
        obj = float(0.5*s@H@s + g@s)
        if best is None or obj < best[0]:
            best = (obj, s, -grad)
    if best is None:
        raise RuntimeError('Tiny QP did not find a feasible KKT point')
    return best[1], best[2]

def valid_box_normal(s, grad, lower, upper, tol=1e-10):
    n = np.zeros_like(s)
    lo = np.abs(s-lower) <= tol
    hi = np.abs(s-upper) <= tol
    n[lo] = np.minimum(-grad[lo], 0)
    n[hi] = np.maximum(-grad[hi], 0)
    return n

def run_random_trial(seed, ns=2):
    rng = np.random.default_rng(seed)
    n, p, m = (28 if ns == 2 else 40), 4, 7
    k = 8 if ns == 2 else 16
    D = cn(rng, (n, n))
    L = np.eye(n) + 0.45*D/np.linalg.norm(D, 2)
    B = [cn(rng, (n, p))/np.sqrt(n) for _ in range(ns)]
    S = [cn(rng, (m, n))/np.sqrt(n) for _ in range(ns)]
    Jc = np.vstack([Sa @ np.linalg.solve(L, Ba) for Sa, Ba in zip(S, B)])
    JF = pack(Jc)
    r = rng.standard_normal(2*ns*m)
    Lambda = np.diag(rng.uniform(0.2, 0.8, p))
    lower, upper = np.full(p, -0.4), np.full(p, 0.7)
    sf = np.array([-0.4, 0.2, 0.7, -0.1])
    nf = np.array([-0.3, 0, 0.5, 0])
    ef = r + JF @ sf
    ell = -JF.T @ ef - Lambda @ sf - nf
    HF = JF.T @ JF + Lambda
    sf_check, _ = box_qp(HF, JF.T@r+ell, lower, upper)
    assert np.linalg.norm(sf_check-sf) < 1e-11
    ec = ef[:ns*m] + 1j*ef[ns*m:]
    X = np.column_stack([np.linalg.solve(L, Ba@sf) for Ba in B])
    Y = np.column_stack([np.linalg.solve(L.conj().T, S[a].conj().T@ec[a*m:(a+1)*m]) for a in range(ns)])
    pullback = sum((B[a].conj().T @ Y[:, a]).real for a in range(ns))
    packing_error = float(np.linalg.norm(pullback - JF.T@ef))
    fill = np.linalg.qr(cn(rng, (n, n)))[0]
    U = fill[:, :2]
    Q0 = protected_basis([U], fill, k)
    QP = protected_basis([U, X], fill, k)
    QD = protected_basis([U, Y], fill, k)
    QPD = protected_basis([U, X, Y], fill, k)
    configs = {'BASE_G': (Q0,Q0), 'PRIMAL_G': (QP,QP), 'DUAL_G': (QD,QD),
               'BOTH_G': (QPD,QPD), 'BOTH_PG': (QP,QD)}
    rows=[]
    for method, (Z, W) in configs.items():
        core = W.conj().T @ L @ Z
        R = Z @ np.linalg.solve(core, W.conj().T)
        JRc = np.vstack([Sa@R@Ba for Sa,Ba in zip(S,B)])
        JR = pack(JRc)
        HR = JR.T@JR + Lambda
        sr, nr = box_qp(HR, JR.T@r+ell, lower, upper)
        dp = (JR-JF)@sf
        dd = (JR-JF).T@ef
        eta = JR.T@(r+JR@sf)+Lambda@sf+ell+nf
        identity_err = np.linalg.norm(eta-dd-JR.T@dp)
        d = sr-sf
        b = normhi(eta, HR)
        beta = float(eigh(HF, HR, eigvals_only=True)[-1])
        step_r = normh(d, HR)
        step_f = normh(d, HF)
        grad_at_sf = JR.T@(r+JR@sf)+Lambda@sf+ell
        gap_r = float(-grad_at_sf@d - 0.5*d@HR@d)
        gap_f = float(-nf@d + 0.5*d@HF@d)
        gf_bound = normhi(nf,HR)*b + 0.5*beta*b*b
        scale = max(1.0, b*b, abs(gap_r), gf_bound, step_r, step_f)
        tol = 1e-9*scale
        assert identity_err < 1e-9*max(1., np.linalg.norm(eta))
        assert step_r <= b + tol
        assert step_f <= np.sqrt(beta)*b + tol
        assert gap_r <= 0.5*b*b + tol
        assert gap_r >= 0.5*step_r**2 - tol
        assert gap_f <= gf_bound + tol
        assert abs(gap_f - (0.5*d@HF@d-nf@d)) < tol
        v = rng.standard_normal(JR.shape[0])
        lifted = v[:ns*m] + 1j*v[ns*m:]
        tied = sum((B[a].conj().T@R.conj().T@S[a].conj().T@lifted[a*m:(a+1)*m]).real for a in range(ns))
        tied_error = float(np.linalg.norm(tied-JR.T@v)/max(1.,np.linalg.norm(tied)))
        assert tied_error < 1e-11
        # Inexact-reference and inexact-reduced-solver inequality.
        shf = np.clip(sf + 1e-4*rng.standard_normal(p), lower, upper)
        shr = np.clip(sr + 1e-4*rng.standard_normal(p), lower, upper)
        ghf = HF@shf+JF.T@r+ell
        nhf = valid_box_normal(shf, ghf, lower, upper)
        rf = ghf+nhf
        ghr = HR@shr+JR.T@r+ell
        nhr = valid_box_normal(shr, ghr, lower, upper)
        rr = ghr+nhr
        eph = r+JF@shf
        dph = (JR-JF)@shf
        ddh = (JR-JF).T@eph
        inexact_bound = normhi(rf+ddh+JR.T@dph-rr, HR)
        assert normh(shr-shf,HR) <= inexact_bound + 1e-9*max(1., inexact_bound)
        rows.append(dict(seed=seed,ns=ns,method=method,rank_Z=k,rank_W=k,
            primal_rel=float(np.linalg.norm(dp)/np.linalg.norm(JF@sf)),
            dual_rel=float(np.linalg.norm(dd)/np.linalg.norm(JF.T@ef)),
            step_rel_HF=step_f/normh(sf,HF),eta_norm=float(np.linalg.norm(eta)),
            defect_identity_abs=float(identity_err),bound_HR=b,step_HR=step_r,
            bound_HF=float(np.sqrt(beta)*b),step_HF=step_f,mu=float(np.linalg.eigvalsh(HR)[0]),
            beta=beta,gap_R=gap_r,gap_F=gap_f,gap_R_upper=0.5*b*b,gap_F_upper=gf_bound,
            core_condition=float(np.linalg.cond(core)),packing_error=packing_error,
            tied_adjoint_rel=tied_error,
            jacobian_rel=float(np.linalg.norm(JR-JF)/np.linalg.norm(JF)),
            primal_capture_res=float(np.linalg.norm(X-Z@(Z.conj().T@X))/np.linalg.norm(X)),
            dual_capture_res=float(np.linalg.norm(Y-W@(W.conj().T@Y))/np.linalg.norm(Y))))
        if method in ('BOTH_G','BOTH_PG'):
            assert rows[-1]['step_rel_HF'] < 1e-8
            assert rows[-1]['primal_rel'] < 1e-9
            assert rows[-1]['dual_rel'] < 1e-9
    # Schur trial/test lifting equivalence.
    U = fill[:,:2]
    P = np.eye(n)-U@U.conj().T
    RU = U@np.linalg.solve(U.conj().T@L@U,U.conj().T)
    T=(np.eye(n)-RU@L)@P
    K=P@(np.eye(n)-L@RU)
    AS=P@L@T
    V = QP[:,2:]
    Q = QD[:,2:]
    Rs = RU+T@V@np.linalg.solve(Q.conj().T@AS@V,Q.conj().T@K)
    Rc = QP@np.linalg.solve(QD.conj().T@L@QP,QD.conj().T)
    schur_rel=float(np.linalg.norm(Rs-Rc)/np.linalg.norm(Rc))
    assert schur_rel < 1e-10
    return rows, schur_rel

def counterexamples():
    out={}
    JF=np.array([[1.,0.],[0.,1.],[0.,0.]])
    JR=np.array([[1.,0.],[0.,0.],[0.,1.]])
    La=np.eye(2); r=np.array([-2.,0.,8.]); sf=np.array([1.,0.])
    sr=-np.linalg.solve(JR.T@JR+La,JR.T@r)
    ef=r+JF@sf
    out['primal_exact_step_wrong']=dict(sf=sf.tolist(),sr=sr.tolist(),
        delta_p=((JR-JF)@sf).tolist(),delta_d=((JR-JF).T@ef).tolist(),
        relative_HF_error=normh(sr-sf,JF.T@JF+La)/normh(sf,JF.T@JF+La))
    # Matching the pullback of r is not matching the pullback of post-step e_F.
    JRpre=np.array([[1.,1.],[0.,1.],[0.,1.]])
    rpre=np.array([-2.,0.,2.]); sfpre=np.array([1.,0.]); efpre=rpre+JF@sfpre
    srpre=-np.linalg.solve(JRpre.T@JRpre+np.eye(2),JRpre.T@rpre)
    out['pre_step_residual_is_wrong_dual_target']=dict(
        primal_error=float(np.linalg.norm((JRpre-JF)@sfpre)),
        pre_step_pullback_error=float(np.linalg.norm((JRpre-JF).T@rpre)),
        correct_post_step_dual_error=float(np.linalg.norm((JRpre-JF).T@efpre)),
        sf=sfpre.tolist(),sr=srpre.tolist(),
        relative_HF_error=float(np.linalg.norm(srpre-sfpre)))
    ep=1e-6; La=np.diag([1.,ep**2]); r=np.array([-2.,0.,1.])
    JR=np.array([[1.,0.],[0.,0.],[0.,ep]])
    HF=JF.T@JF+La; HR=JR.T@JR+La
    sf=-np.linalg.solve(HF,JF.T@r); sr=-np.linalg.solve(HR,JR.T@r)
    ef=r+JF@sf; eta=(JR-JF).T@ef+JR.T@((JR-JF)@sf)
    beta=float(eigh(HF,HR,eigvals_only=True)[-1]); b=normhi(eta,HR)
    out['small_relative_errors_large_step']=dict(primal_relative=0.,
        dual_relative=float(np.linalg.norm((JR-JF).T@ef)/np.linalg.norm(JF.T@ef)),
        mu=float(np.linalg.eigvalsh(HR)[0]),relative_HF_error=normh(sr-sf,HF)/normh(sf,HF),
        absolute_HF_error=normh(sr-sf,HF),certified_HF_bound=float(np.sqrt(beta)*b),
        sr=sr.tolist(),beta=beta)
    z=np.array([[1.],[0.]]); w=np.array([[0.],[1.]])
    out['captured_but_singular_PG']=dict(primal_capture=1.,dual_capture=1.,
        core=float((w.T@z)[0,0]))
    out['constrained_full_gap_normal_work']=dict(sf=0.,sr=0.5,HF=2.,nf=-1.,
        full_gap=0.75,half_squared_HF_error=0.25,normal_work=0.5)
    # Both minimizers are 0 on C=[0,infinity), but dual interpolation fails.
    out['two_sided_sufficient_not_necessary']=dict(JF=1.,JR=2.,r=1.,Lambda=1.,
        sf=0.,sr=0.,nf=-1.,nr=-2.,delta_p=0.,delta_d=1.)
    return out

def main():
    rows=[]; schur=[]
    for seed in range(21, 37):
        a,b=run_random_trial(seed,2);rows.extend(a);schur.append(b)
    a,b=run_random_trial(101,6);rows.extend(a);schur.append(b)
    summary={}
    for method in sorted({x['method'] for x in rows}):
        rr=[x for x in rows if x['method']==method]
        summary[method]={
            'cases':len(rr),
            'max_primal_relative':max(x['primal_rel'] for x in rr),
            'max_dual_relative':max(x['dual_rel'] for x in rr),
            'max_HF_step_relative':max(x['step_rel_HF'] for x in rr),
            'median_HF_step_relative':float(np.median([x['step_rel_HF'] for x in rr])),
            'median_J_relative':float(np.median([x['jacobian_rel'] for x in rr])),
            'max_core_condition':max(x['core_condition'] for x in rr)}
    result={'scope':'synthetic complex linear systems with real material variables, active box constraints; not A20 data',
            'random_problems':17,'configurations':len(rows),
            'summary':summary,'max_defect_identity_abs':max(x['defect_identity_abs'] for x in rows),
            'max_real_pullback_abs':max(x['packing_error'] for x in rows),
            'max_tied_adjoint_rel':max(x['tied_adjoint_rel'] for x in rows),
            'max_schur_petrov_relative':max(schur),
            'counterexamples':counterexamples(),'rows':rows}
    (ROOT/'results.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='rows'},indent=2))
    print('All algebra, KKT, norm-bound, and gap assertions passed.')

if __name__=='__main__':
    main()
