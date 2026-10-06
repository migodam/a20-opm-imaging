#!/usr/bin/env python3
"""Synthetic checks of first-order interpolation at a feasible NON-optimal point.
This does not execute an online A20/A21 experiment or nonlinear reconstruction.
Run: python validation/validate_online_descent.py
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
from validate_two_sided import cn, pack, protected_basis, box_qp

ROOT = Path(__file__).resolve().parent

def run(seed: int) -> dict:
    rng = np.random.default_rng(seed)
    n, p, m, ns, k = 28, 4, 6, 2, 8
    A = cn(rng, (n, n))
    L = np.eye(n) + 0.5 * A / np.linalg.norm(A, 2)
    B = [cn(rng, (n, p))/np.sqrt(n) for _ in range(ns)]
    S = [cn(rng, (m, n))/np.sqrt(n) for _ in range(ns)]
    # General real measurement transformation, not a complex-linear shortcut.
    D = np.eye(2*ns*m) + 0.02*rng.standard_normal((2*ns*m, 2*ns*m))
    Jc = np.vstack([Sa@np.linalg.solve(L, Ba) for Sa, Ba in zip(S, B)])
    JF = D @ pack(Jc)
    r = rng.standard_normal(2*ns*m)
    Lam = np.diag(rng.uniform(0.2, 0.6, p))
    ell = 0.3*rng.standard_normal(p)
    lo, hi = np.full(p, -0.5), np.full(p, 0.7)
    u = rng.uniform(lo, hi)
    if seed % 2 == 0:
        u[0] = lo[0]
    if seed % 3 == 0:
        u[2] = hi[2]
    e = r + JF@u
    packed_adjoint = D.T @ e
    ec = packed_adjoint[:ns*m] + 1j*packed_adjoint[ns*m:]
    X = np.column_stack([np.linalg.solve(L, Ba@u) for Ba in B])
    Y = np.column_stack([np.linalg.solve(L.conj().T,
        S[a].conj().T@ec[a*m:(a+1)*m]) for a in range(ns)])
    filler = np.linalg.qr(cn(rng, (n, n)))[0]
    Q = protected_basis([filler[:, :2], X, Y], filler, k)
    R = Q@np.linalg.solve(Q.conj().T@L@Q, Q.conj().T)
    JR = D@pack(np.vstack([Sa@R@Ba for Sa, Ba in zip(S, B)]))
    HF, HR = JF.T@JF + Lam, JR.T@JR + Lam
    gF, gR = JF.T@r + ell, JR.T@r + ell
    v, _ = box_qp(HR, gR, lo, hi)
    d = v-u
    gradF, gradR = HF@u+gF, HR@u+gR
    pullback = sum((B[a].conj().T@Y[:, a]).real for a in range(ns))
    primal_error = float(np.linalg.norm((JR-JF)@u))
    gradient_error = float(np.linalg.norm(gradF-gradR))
    whitening_error = float(np.linalg.norm(pullback-JF.T@e))
    value_error = float(abs(0.5*np.linalg.norm(r+JR@u)**2-
                            0.5*np.linalg.norm(r+JF@u)**2))
    descent_violation = float(gradF@d + d@HR@d)
    scale = max(1.0, abs(float(gradF@d)), float(d@HR@d))
    assert max(primal_error, gradient_error, whitening_error, value_error) < 1e-10
    assert descent_violation <= 1e-10*scale
    assert np.linalg.norm(d) > 1e-8
    alpha = min(1.0, -float(gradF@d)/float(d@HF@d))
    change = float(alpha*(gradF@d) + 0.5*alpha**2*(d@HF@d))
    assert alpha > 0 and change < 0
    assert np.all(u+alpha*d >= lo-1e-12) and np.all(u+alpha*d <= hi+1e-12)
    return dict(seed=seed, primal_error=primal_error,
                gradient_error=gradient_error, value_error=value_error,
                whitening_adjoint_error=whitening_error,
                descent_violation=descent_violation,
                alpha=alpha, full_frozen_quadratic_change=change)

if __name__ == '__main__':
    rows = [run(i) for i in range(200, 232)]
    summary = dict(cases=len(rows),
        max_primal_error=max(r['primal_error'] for r in rows),
        max_gradient_error=max(r['gradient_error'] for r in rows),
        max_value_error=max(r['value_error'] for r in rows),
        max_whitening_adjoint_error=max(r['whitening_adjoint_error'] for r in rows),
        max_descent_violation=max(r['descent_violation'] for r in rows),
        min_alpha=min(r['alpha'] for r in rows),
        max_full_quadratic_change=max(r['full_frozen_quadratic_change'] for r in rows))
    result = dict(scope='synthetic complex systems; no A20 data; no nonlinear imaging',
                  summary=summary, rows=rows)
    (ROOT/'online_descent_results.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(summary, indent=2))
    print('PASS: all first-order interpolation, whitening and feasible descent checks')
