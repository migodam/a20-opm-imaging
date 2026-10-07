"""Small real material geometry. No full physics or evaluator fields here."""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np
from scipy import linalg as la
from scipy.optimize import minimize, LinearConstraint, nnls
from a20.material import QPFailure, constraint_map


def profiled_witness(A, v, nuisance=None, *, rtol=1e-10):
    A, v = np.asarray(A, float), np.asarray(v, float)
    if v.ndim != 1 or A.shape[1] != len(v):
        raise ValueError('REAL_DIRECTION_LAYOUT')
    nv = la.norm(v)
    if nv == 0:
        return {'status': 'ZERO_DIRECTION', 'g': 0., 'h': None, 'attribution': None}
    v = v/nv
    N = la.null_space(v[None, :]) if nuisance is None else np.asarray(nuisance, float)
    if N.shape[0] != len(v) or la.norm(N.T@v) > 1e-9:
        raise ValueError('NUISANCE_TARGET_NOT_ORTHOGONAL')
    j = A@v
    K = A@N
    if K.shape[1]:
        U, s, _ = la.svd(K, full_matrices=False)
        rank = int(np.count_nonzero(s > rtol*s[0])) if len(s) and s[0] else 0
        U = U[:, :rank]
        q = j-U@(U.T@j)
        # Reprojection removes accumulated nuisance roundoff.
        q -= U@(U.T@q)
    else:
        rank, q = 0, j.copy()
    g, total = float(la.norm(q)), float(la.norm(j))
    zero_tolerance = 100*np.finfo(float).eps*max(float(la.norm(A)), total)
    h = q/(g*g) if g > zero_tolerance else None
    return {'status': 'OK' if h is not None else 'UNIDENTIFIABLE', 'g': g,
            'h': h, 'q': q, 'v': v, 'N': N, 'nuisance_rank': rank,
            'total_gain': total, 'attribution': g/total if total else None,
            'backward_error': float(la.norm(A.T@h-v)) if h is not None else None,
            'nuisance_leakage': float(la.norm(K.T@h)) if h is not None else None,
            'rank_rule': 'numerical range, not removal of noisy nuisance modes'}


@dataclass
class MaterialSplit:
    Vp: np.ndarray
    Vrem: np.ndarray
    D: np.ndarray
    rank: int
    status: str
    certificate: dict
    eligibility: list[str]


def build_split(features, declared_uncertainty, config=None, *, rank=None):
    """SVD candidates followed by a complete-complement block check.

    This does not certify full Maxwell fidelity; that provenance is separate.
    """
    config = config or {}
    A = np.asarray(features.AW if hasattr(features, 'AW') else features['AW'], float)
    r = int(rank if rank is not None else config.get('split_rank', 8))
    if not 0 < r < A.shape[1]:
        raise ValueError('NONTRIVIAL_SPLIT_REQUIRED')
    _, s, Vt = la.svd(A, full_matrices=A.shape[0] < A.shape[1])
    V = Vt.T
    # Deterministic signs; degenerate-block invariance is tested through projectors.
    for k in range(V.shape[1]):
        i = int(np.argmax(abs(V[:, k])))
        if V[i, k] < 0:
            V[:, k] *= -1
    Vp, Vn = V[:, :r], V[:, r:]
    K = A@Vn
    if K.shape[1]:
        Uk, sk, _ = la.svd(K, full_matrices=False)
        rk = int(np.count_nonzero(sk > config.get('orthogonal_rank_rtol', 1e-10)*sk[0])) if len(sk) and sk[0] else 0
        Uk = Uk[:, :rk]
        Ap = A@Vp
        G = Ap-Uk@(Uk.T@Ap)
    else:
        rk, Uk, G = 0, np.empty((A.shape[0], 0)), A@Vp
    sg = la.svdvals(G)
    lam = float(config.get('tikhonov_relative', 1e-4))*float(s[0]**2)
    if lam <= 0 or not len(sg) or sg[-1] <= 100*np.finfo(float).eps*max(1., float(sg[0])):
        return MaterialSplit(Vp, Vn, np.zeros((r, A.shape[0])), r, 'INVALID_BLOCK',
                             {'sigma_min': float(sg[-1]) if len(sg) else None}, ['model_unresolved']*Vn.shape[1])
    with_matrix = la.solve(G.T@G+lam*np.eye(r), G.T, assume_a='pos')
    D = with_matrix-(with_matrix@Uk)@Uk.T
    cert = dict(sigma_min=float(sg[-1]), sigma_max=float(sg[0]), regularization=lam,
                noise_gain=float(la.norm(D, 2)), nuisance_leakage=float(la.norm(D@K)),
                attribution_error=float(la.norm(D@A-Vp.T)), orthogonality=float(la.norm(Vp.T@Vn)),
                nuisance_rank=rk, full_model_certified=False,
                certificate_type=declared_uncertainty.get('certificate_type', 'empirical_indicator'))
    reasons = ['finite_amplitude_unvalidated']*Vn.shape[1]
    return MaterialSplit(Vp, Vn, D, r, 'TANGENT_CANDIDATE', cert, reasons)


def _normal(A, lower, step, gradient, tolerance):
    slack = A@step-lower
    active = np.flatnonzero(slack <= tolerance)
    mu = np.zeros(len(slack))
    if len(active):
        value, _ = nnls(A[active].T, gradient, maxiter=max(200, 10*len(active)))
        mu[active] = value
    normal = -A.T@mu
    return normal, dict(violation=max(0., float(-np.min(slack))),
                       complementarity=float(np.max(abs(mu*slack))),
                       multipliers=mu, active=active,
                       defect=gradient+normal)


def constrained_material_solve(A, d, chart, chi0, config, book, *, basis=None, lam=None):
    """Same SPD quadratic / SLSQP / active-equation KKT contract, in any basis.

    The material basis is a declared restriction, not a changed material bound.
    """
    A, d = np.asarray(A, float), np.asarray(d, float)
    V = np.eye(chart.d) if basis is None else np.asarray(basis, float)
    if la.norm(V.T@V-np.eye(V.shape[1])) > 1e-9:
        raise ValueError('MATERIAL_BASIS_NOT_ORTHONORMAL')
    Am, lower = constraint_map(chart, chi0)
    Am = np.eye(chart.d) if Am is None else Am
    C = Am@V
    n = V.shape[1]
    if A.shape[1] != n:
        raise ValueError('COEFFICIENT_JACOBIAN_LAYOUT')
    scaleA = float(la.svdvals(A)[0]) if A.size else 0.
    lam = float(lam if lam is not None else config.get('tikhonov_relative', 1e-4)*scaleA**2)
    if lam <= 0:
        raise QPFailure('ZERO_MODEL_NO_POSITIVE_REGISTERED_REGULARIZATION')
    H, g = A.T@A+lam*np.eye(n), -A.T@d
    tol, ktol = config.get('feasibility_tolerance', 1e-8), config.get('qp_kkt_rtol', 1e-8)
    objective_scale = max(float(la.norm(g)), lam, 1e-12)
    with book.span('a22_material_subproblem', material_subproblems=1):
        unconstrained = -la.solve(H, g, assume_a='pos')
        result = {'iterations': 0, 'solver': 'direct-SPD',
                  'original_inequality_count': int(len(lower)),
                  'solver_inequality_count': 0}
        if np.min(C@unconstrained-lower) >= -1e-11:
            x = unconstrained
        else:
            fun = lambda x: float(.5*x@H@x+g@x)/objective_scale
            jac = lambda x: (H@x+g)/objective_scale
            # Only exactly equal coefficient/bound rows are redundant.
            # Include the bound in equality; retain original first-occurrence
            # order and the full C/lower below for feasibility and KKT audits.
            _, first = np.unique(np.column_stack((C, lower)), axis=0, return_index=True)
            first = np.sort(first)
            opt = minimize(fun, np.zeros(n), jac=jac,
                           constraints=[LinearConstraint(C[first], lower[first], np.inf)], method='SLSQP',
                           options={'ftol': 1e-16, 'maxiter': config.get('qp_maxiter', 200)})
            x = opt.x
            result.update(iterations=int(opt.nit), solver='SLSQP-common-quadratic', solver_success=bool(opt.success),
                          solver_inequality_count=int(len(first)))
        gradient = H@x+g
        normal, audit = _normal(C, lower, x, gradient, tol)
        relative = float(la.norm(audit['defect']))/max(float(la.norm(g)), 1e-12)
        if relative > ktol:
            active = audit['active']
            if len(active):
                _, rr, piv = la.qr(C[active].T, mode='economic', pivoting=True)
                diag = abs(np.diag(rr))
                r = int(np.count_nonzero(diag > 1e-12*max(1., float(la.norm(C[active])))))
                idx = active[piv[:r]]
                E = C[idx]
                KKT = np.block([[H, -E.T], [-E, np.zeros((r, r))]])
                candidate = la.solve(KKT, np.r_[-g, -lower[idx]], assume_a='sym')[:n]
            else:
                candidate = unconstrained
            cn, ca = _normal(C, lower, candidate, H@candidate+g, tol)
            cr = float(la.norm(ca['defect']))/max(float(la.norm(g)), 1e-12)
            if ca['violation'] <= tol and cr < relative and (.5*candidate@H@candidate+g@candidate) <= (.5*x@H@x+g@x)+100*np.finfo(float).eps*max(1., abs(.5*x@H@x+g@x)):
                x, normal, audit, relative = candidate, cn, ca, cr
                result['validated_active_equations'] = True
        book.counts['material_optimizer_iterations'] += result['iterations']
        result.update(kkt_relative=relative, feasibility_violation=audit['violation'],
                      complementarity=audit['complementarity'], lambda_value=lam,
                      quadratic_value=float(.5*x@H@x+g@x), no_post_clipping=True,
                      no_jitter_or_pseudoinverse=True)
        if audit['violation'] > tol or relative > ktol:
            error = QPFailure('A22_COEFFICIENT_QP_KKT_OR_FEASIBILITY_FAILED')
            error.result = result
            raise error
        return V@x, result, normal


def choose_directions(A, descriptors=None, count=8):
    """A fixed candidate pool and deterministic strata; never uses recovery labels."""
    p = A.shape[1]
    _, _, Vt = la.svd(A, full_matrices=A.shape[0] < A.shape[1])
    candidates = [np.eye(p)[:, j] for j in range(p)]
    candidates += [Vt[j].copy() for j in (0, min(7, p-1), min(15, p-1), p-1)]
    rows = []
    for i, v in enumerate(candidates):
        w = profiled_witness(A, v)
        rows.append((i, v, w['total_gain'], w['attribution'] or 0., w['g']))
    # Strong/weak response, high/low attribution, coarse/detail and SVD controls.
    picks = [max(rows, key=lambda r:(r[2], -r[0])), min(rows, key=lambda r:(r[2], r[0])),
             max(rows, key=lambda r:(r[3], -r[0])), min(rows, key=lambda r:(r[3], r[0])),
             rows[0], rows[min(8, p-1)], rows[p], rows[-1]]
    selected = []
    for row in picks+rows:
        v = row[1]
        if not any(abs(v@u['v']) > 1-1e-10 for u in selected):
            selected.append({'id': len(selected), 'candidate_index': row[0], 'v': v,
                             'origin': 'canonical_patch' if row[0]<p else 'small_A_SVD',
                             'selection_uses_labels': False})
        if len(selected) == count:
            break
    return selected
