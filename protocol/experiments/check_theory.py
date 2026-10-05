#!/usr/bin/env python3
"""Reproducible algebra checks. NOT a validated 3-D Maxwell imaging benchmark.
Run: OPENBLAS_NUM_THREADS=1 python experiments/check_theory.py
Requires NumPy only. Fixed random seeds; no training data or external services.
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np


def adj(a: np.ndarray) -> np.ndarray:
    return a.conj().T


def orth(a: np.ndarray, tol: float = 1e-12) -> np.ndarray:
    if a.shape[1] == 0:
        return a.copy()
    u, s, _ = np.linalg.svd(a, full_matrices=False)
    return u[:, s > tol * max(s[0], 1e-30)]


def rel(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.linalg.norm(a-b) / max(np.linalg.norm(a), np.linalg.norm(b), 1e-14))


def invsqrt(h: np.ndarray) -> np.ndarray:
    w, v = np.linalg.eigh(h)
    if w.min() <= 0:
        raise ValueError('Expected positive definite matrix')
    return (v / np.sqrt(w)) @ adj(v)


def cx(rng: np.random.Generator, *shape: int) -> np.ndarray:
    return rng.standard_normal(shape) + 1j*rng.standard_normal(shape)


def run() -> dict:
    metrics: dict[str, list[float]] = {}
    def put(name: str, value: float) -> None:
        metrics.setdefault(name, []).append(float(value))
    for seed in range(20):
        rng = np.random.default_rng(260005 + seed)
        n, r, p, d = 64, 5, 8, 9
        f = cx(rng, n, n)
        f *= 0.85/np.linalg.norm(f, 2)
        l = np.eye(n) - f
        u = orth(cx(rng, n, r))
        # Explicit complement only for small verification; production uses projectors.
        _, _, vh = np.linalg.svd(adj(u), full_matrices=True)
        w = adj(vh)[..., r:]
        ru = u @ np.linalg.solve(adj(u)@l@u, adj(u))
        t = (np.eye(n)-ru@l)@w
        k = adj(w)@(np.eye(n)-l@ru)
        a = adj(w)@l@t
        fe = adj(w)@f@w + adj(w)@f@u@np.linalg.solve(np.eye(r)-adj(u)@f@u, adj(u)@f@w)
        put('schur_feedback_identity', rel(a, np.eye(n-r)-fe))
        put('full_resolvent_schur_identity', rel(np.linalg.inv(l), ru+t@np.linalg.solve(a,k)))
        s = cx(rng, d, n)/np.sqrt(n)
        b = cx(rng, n, p)/np.sqrt(n)
        c, ni = s@t, k@b
        q = orth(np.column_stack([ni[:, :2], adj(c)[:, :2], fe@ni[:, :2], adj(fe)@adj(c)[:, :2]]))
        aq = adj(q)@a@q
        xq = q@np.linalg.solve(aq, adj(q)@ni)
        zq = q@np.linalg.solve(adj(aq), adj(q)@adj(c))
        rn, rc = ni-a@xq, adj(c)-adj(a)@zq
        defect = c@np.linalg.solve(a,ni) - c@xq
        dual = adj(rc)@np.linalg.solve(a,rn)
        put('dual_residual_defect_identity', rel(defect, dual))
        put('dual_residual_bound_ratio', np.linalg.norm(defect,2)/(np.linalg.norm(rc,2)*np.linalg.norm(np.linalg.inv(a),2)*np.linalg.norm(rn,2)))
        z = np.column_stack([u, w@q])
        rz = z@np.linalg.solve(adj(z)@l@z, adj(z))
        rs = ru+t@q@np.linalg.solve(aq,adj(q)@k)
        put('galerkin_schur_equivalence', rel(rz,rs))
        # Full complex data, REAL material variables: use realification.
        jc = s@np.linalg.solve(l,b)
        jmc = s@rz@b
        j = np.vstack([jc.real,jc.imag])
        jm = np.vstack([jmc.real,jmc.imag])
        rr = rng.standard_normal(2*d)
        lam = np.eye(p)*0.4
        ell = rng.standard_normal(p)*0.1
        h, hm = j.T@j+lam, jm.T@jm+lam
        g, gm = j.T@rr+ell, jm.T@rr+ell
        sf, sm = -np.linalg.solve(h,g), -np.linalg.solve(hm,gm)
        dd = j-jm
        residual = h@sm+g
        rhs = jm.T@dd@sm+dd.T@(rr+jm@sm)+dd.T@dd@sm
        put('gn_stationarity_defect_identity', rel(residual,rhs))
        gap = 0.5*(sm-sf)@h@(sm-sf)
        gap_q = 0.5*residual@np.linalg.solve(h,residual)
        put('gn_exact_gap_relative_error', abs(gap-gap_q)/max(gap,1e-14))
        eps = np.linalg.norm((jm-j)@invsqrt(h),2)
        eta = np.linalg.norm(invsqrt(h)@(hm-h)@invsqrt(h),2)
        put('hessian_relative_bound_ratio', eta/(2*eps+eps*eps))
        # Exact step innovation with frozen state, residual and regularizer.
        perturb = 0.02*rng.standard_normal(jm.shape)
        jn = jm+perturb
        hn = jn.T@jn+lam
        sn = -np.linalg.solve(hn,jn.T@rr+ell)
        innovation_rhs = -(jm.T@perturb@sm+perturb.T@(rr+jm@sm)+perturb.T@perturb@sm)
        put('degree_step_innovation_identity', rel(hn@(sn-sm),innovation_rhs))
        # Gauge covariance.
        v = np.linalg.qr(cx(rng,q.shape[1],q.shape[1]))[0]
        qv = q@v
        r1 = q@np.linalg.solve(adj(q)@a@q,adj(q))
        r2 = qv@np.linalg.solve(adj(qv)@a@qv,adj(qv))
        put('unitary_gauge_resolvent_identity',rel(r1,r2))
        # Conditional prior-safe bound in whitened material coordinates.
        am = rng.standard_normal((11,7))
        _, sv, vv = np.linalg.svd(am,full_matrices=False)
        ww = vv.T[:, -2:]
        ee = 0.03*rng.standard_normal(am.shape)
        tau = sv[-2]
        lhs = np.linalg.norm((am+ee)@ww,2)
        bound = tau+np.linalg.norm(ee@ww,2)
        put('prior_safe_restricted_bound_ratio',lhs/bound)
    # Double-sided moment matching: m=2 means moments k=0,...,5 exact.
    rng = np.random.default_rng(6105)
    n, m = 72, 2
    f = cx(rng,n,n); f *= 0.9/np.linalg.norm(f,2)
    b, c = cx(rng,n,2), cx(rng,3,n)
    columns=[]; right=b.copy(); left=adj(c).copy()
    for _ in range(m+1):
        columns.extend([right,left]); right=f@right; left=adj(f)@left
    q=orth(np.column_stack(columns)); h=adj(q)@f@q
    moment_errors=[]
    for degree in range(9):
        full=c@np.linalg.matrix_power(f,degree)@b
        red=c@q@np.linalg.matrix_power(h,degree)@adj(q)@b
        moment_errors.append(rel(full,red))
    # Delayed feedback: several identical reduced steps but a nonzero exact step.
    n=7; f=np.diag(np.ones(n-1)*0.8,k=-1)
    b=np.eye(n)[:,[0]]; c=np.eye(n)[[-1],:]
    delayed=[]
    for m in range(4):
        cols=[]; br=b.copy(); cl=c.T.copy()
        for _ in range(m+1):
            cols.extend([br,cl]); br=f@br; cl=f.T@cl
        q=orth(np.column_stack(cols)); a=np.eye(n)-f
        j=float((c@q@np.linalg.solve(q.T@a@q,q.T@b)).item())
        step=j/(j*j+0.1)
        delayed.append({'degree':m,'rank':int(q.shape[1]),'J':j,'step':step})
    jfull=float((c@np.linalg.solve(np.eye(n)-f,b)).item())
    # Nonnormal eigenvalues alone can be useless.
    fn=np.array([[0.0,100.0],[0.0,0.0]])
    nonnormal={'spectral_radius':0.0,'resolvent_norm':float(np.linalg.norm(np.linalg.inv(np.eye(2)-fn),2))}
    # Galerkin can break down even when full L is invertible.
    l=np.array([[0.,1.],[-1.,0.]])
    galerkin_breakdown={'full_determinant':float(np.linalg.det(l)), 'reduced_entry':float(l[0,0])}
    # Full-operator approximation cannot be inferred from exact task transfer.
    pmat=np.diag([1.,0.,0.,0.])
    fullnorm={'task_error':0.0,'operator_error':float(np.linalg.norm(np.eye(4)-pmat,2))}
    # Apparent weak space can be entirely a ROM artifact.
    jfullmat=np.eye(2); jlow=np.diag([1.,0.]); weak=np.array([0.,1.])
    falseweak={'reduced_data_change':float(np.linalg.norm(jlow@weak)), 'full_data_change':float(np.linalg.norm(jfullmat@weak))}
    # Variance is not monotone in approximation fidelity.
    aa=np.array([0.1,0.2,0.4,0.8,1.0]); lam=0.1; sigma=0.1
    bias=(aa/(aa*aa+lam)-1.0)**2
    var=sigma*sigma*aa*aa/(aa*aa+lam)**2
    risk=[{'a_m':float(a),'bias_squared':float(b),'variance':float(v),'risk':float(b+v)} for a,b,v in zip(aa,bias,var)]
    # Frozen reduced-state derivative test for L(x)=I-diag(x)G.
    rng=np.random.default_rng(888); n=17
    gg=cx(rng,n,n); gg*=0.3/np.linalg.norm(gg,2)
    inc=cx(rng,n); obs=cx(rng,5,n)
    z=orth(cx(rng,n,7)); x=rng.uniform(0.1,0.7,n)
    direction=rng.standard_normal(n); direction/=np.linalg.norm(direction)
    def state(xx: np.ndarray, zz: np.ndarray) -> np.ndarray:
        ll=np.eye(n)-xx[:,None]*gg
        return zz@np.linalg.solve(adj(zz)@ll@zz,adj(zz)@(xx*inc))
    l=np.eye(n)-x[:,None]*gg; jr=state(x,z)
    inj=(inc+gg@jr)*direction
    tangent=obs@z@np.linalg.solve(adj(z)@l@z,adj(z)@inj)
    epsfd=1e-6
    fd=obs@(state(x+epsfd*direction,z)-state(x-epsfd*direction,z))/(2*epsfd)
    derivative_error=rel(tangent,fd)
    # A moving basis has additional derivative terms.
    zzpert=cx(rng,n,z.shape[1]); zzpert*=0.4/np.linalg.norm(zzpert)
    yp=obs@state(x+epsfd*direction,orth(z+epsfd*zzpert))
    ym=obs@state(x-epsfd*direction,orth(z-epsfd*zzpert))
    moving_error=rel(tangent,(yp-ym)/(2*epsfd))
    summary={name:{'max':max(v),'min':min(v),'trials':len(v)} for name,v in metrics.items()}
    for name, values in metrics.items():
        if name.endswith('_identity') or name.endswith('_relative_error') or name=='galerkin_schur_equivalence':
            assert max(values)<1e-10,(name,max(values))
        if name.endswith('_bound_ratio'):
            assert max(values)<=1+1e-10,(name,max(values))
    assert max(moment_errors[:6])<1e-10
    assert derivative_error<1e-7
    assert moving_error>1e-3
    assert all(abs(row['step'])<1e-12 for row in delayed[:3]) and delayed[3]['step']>0.1
    return {'scope':'Synthetic finite-dimensional algebra only. Not A17/A18/A19 replay, not a 3-D Maxwell reconstruction benchmark.',
            'random_trials':20,'checks':summary,'two_sided_moment_relative_errors_k_0_to_8':moment_errors,
            'delayed_feedback':delayed,'delayed_feedback_full_J':jfull,
            'nonnormal_counterexample':nonnormal,'galerkin_breakdown':galerkin_breakdown,
            'global_norm_counterexample':fullnorm,'false_weak_counterexample':falseweak,
            'scalar_bias_variance_counterexample':risk,'frozen_basis_derivative_relative_error':derivative_error,
            'moving_basis_missing_derivative_relative_error':moving_error,'status':'ALL ASSERTIONS PASSED'}


if __name__=='__main__':
    result=run()
    dest=Path(__file__).resolve().parent/'results.json'
    dest.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))
