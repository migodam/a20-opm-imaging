"""Common SPD material quadratics with feasibility and KKT validation."""
from __future__ import annotations
import numpy as np
from scipy import linalg as la
from scipy.optimize import minimize, LinearConstraint, nnls


class QPFailure(RuntimeError):
    pass


def constraint_map(chart, chi):
    lower = np.concatenate((-.5-chi.real, -chi.imag))
    if chart.Q is None:
        return None, lower*np.sqrt(chart.volume)
    return la.block_diag(chart.Q, chart.Q), lower


def kkt(chart, chi, s, gradient, *, tolerance=1e-8):
    A, lower = constraint_map(chart, chi)
    values = s if A is None else A@s
    slack = values-lower
    active = slack <= tolerance
    multipliers = np.zeros(len(slack))
    if A is None:
        multipliers[active] = np.maximum(gradient[active], 0.)
        normal = -multipliers
    elif np.any(active):
        mu, _ = nnls(A[active].T, gradient, maxiter=max(200, 10*np.count_nonzero(active)))
        multipliers[active] = mu
        normal = -A.T@multipliers
    else:
        normal = np.zeros_like(gradient)
    defect = gradient+normal
    return {'defect': defect, 'normal': normal, 'multipliers': multipliers,
            'stationarity_norm': float(la.norm(defect)),
            'violation': max(0., float(-np.min(slack))),
            'complementarity': float(np.max(abs(multipliers*slack))),
            'dual_violation': max(0., float(-np.min(multipliers))),
            'active_constraints': int(np.count_nonzero(active))}


def solve_quadratic(chart, chi, residual, jacobian, lam, ell, config, book, *, initial=None):
    with book.span('material_subproblem', material_subproblems=1):
        return _solve_quadratic(chart, chi, residual, jacobian, lam, ell, config, book, initial=initial)


def _solve_quadratic(chart, chi, residual, jacobian, lam, ell, config, book, *, initial=None):
    if lam<=0:
        raise ValueError('Positive regularization/LM metric required')
    # Small material spaces use a dense real quadratic. Voxel full GN keeps
    # the original action interface; the reduced model may cache its data map.
    matrix = jacobian.small_matrix() if hasattr(jacobian, 'small_matrix') else jacobian.matrix()
    J = matrix
    g = (jacobian.pullback(residual) if J is None else J.T@residual)+ell
    hv = (lambda s: jacobian.pullback(jacobian.action(s))+lam*s) if J is None else (lambda s: J.T@(J@s)+lam*s)
    A, lower = constraint_map(chart, chi)
    scale = max(float(la.norm(g)), float(lam), 1e-12)
    memo = {}
    def fg(s):
        book.check()
        if 's' not in memo or not np.array_equal(memo['s'], s):
            h = hv(s)
            memo.update(s=s.copy(), fun=float(.5*s@h+g@s)/scale, jac=(h+g)/scale)
        return memo['fun'], memo['jac']
    seed = np.zeros(chart.d) if initial is None else np.asarray(initial).copy()
    unconstrained = None
    if chart.d<=128 and A is not None:
        with book.span('small_material_H_assembly', small_material_H_assemblies=1):
            H = J.T@J+lam*np.eye(chart.d)
        hv = lambda s: H@s
        unconstrained = -la.solve(H, g, assume_a='pos')
        if np.min(A@unconstrained-lower)>=-1e-11:
            seed = unconstrained
            result = {'success': True, 'iterations': 0, 'message': 'Exact feasible SPD solution', 'solver': 'direct-SPD'}
        else:
            if np.min(A@seed-lower)<-1e-10:
                seed = np.zeros(chart.d)
            with book.span('Gaussian_constrained_quadratic'):
                opt = minimize(lambda s: fg(s)[0], seed, jac=lambda s: fg(s)[1],
                    constraints=[LinearConstraint(A, lower, np.inf)], method='SLSQP',
                    options={'ftol': 1e-16, 'maxiter': config.get('qp_maxiter', 200)})
            seed = opt.x
            result = {'success': bool(opt.success), 'iterations': int(opt.nit), 'message': str(opt.message), 'solver': 'SLSQP-common-quadratic'}
    else:
        seed = np.maximum(seed, lower)
        with book.span('voxel_bound_quadratic'):
            opt = minimize(lambda s: fg(s), seed, jac=True, bounds=list(zip(lower, np.full(chart.d, np.inf))),
                           method='L-BFGS-B', options={'ftol': 1e-15, 'gtol': 1e-11,
                            'maxiter': config.get('qp_maxiter', 200), 'maxls': 40, 'maxcor': 20})
        seed = opt.x
        result = {'success': bool(opt.success), 'iterations': int(opt.nit), 'message': str(opt.message), 'solver': 'L-BFGS-B-common-quadratic'}
    gradient = hv(seed)+g
    audit = kkt(chart, chi, seed, gradient, tolerance=config.get('feasibility_tolerance', 1e-8))
    relative = audit['stationarity_norm']/max(float(la.norm(g)), 1e-12)
    result.update(kkt_relative=relative, feasibility_violation=audit['violation'],
                  complementarity=audit['complementarity'], active_constraints=audit['active_constraints'],
                  multiplier_source='nonnegative active constraint least-squares; validated residual',
                  no_post_clipping=True, objective_scale=scale,
                  quadratic_value=float(.5*seed@hv(seed)+g@seed), gradient_norm=float(la.norm(g)))
    book.counts['material_optimizer_iterations'] += result['iterations']
    if audit['violation']>config.get('feasibility_tolerance', 1e-8) or relative>config.get('qp_kkt_rtol', 1e-8):
        error = QPFailure('Constrained QP did not meet registered KKT/feasibility tolerance')
        error.result = result
        error.step = seed
        raise error
    return seed, result, audit['normal']


def full_quadratic_audit(full_jac, residual, lam, ell, s, ref, normal=None):
    """Full H error/gap; constraints use inequalities, not false equalities."""
    ds = s-ref
    js, jref = full_jac.action(s), full_jac.action(ref)
    energy = float((js-jref)@(js-jref)+lam*(ds@ds))
    ref_energy = float(jref@jref+lam*(ref@ref))
    q = full_jac.pullback(residual+js)+lam*s+ell
    if normal is not None:
        q += normal
    phi = lambda step, jstep: float(.5*(residual+jstep)@(residual+jstep)+ell@step+.5*lam*step@step)
    gap = phi(s, js)-phi(ref, jref)
    return {'relative_H_step_error': float(np.sqrt(max(0., energy)/ref_energy)) if ref_energy>1e-24 else None,
            'absolute_H_step_error': float(np.sqrt(max(0., energy))), 'reference_H_energy': ref_energy,
            'full_quadratic_gap': gap, 'half_H_error_energy': .5*energy,
            'full_stationarity_defect_norm': float(la.norm(q)),
            'KKT_bound_H_error': float(la.norm(q)/np.sqrt(lam)),
            'KKT_bound_quadratic_gap': float(q@q/(2*lam)),
            'identity_scope': 'unconstrained equality only; constrained normal yields upper bounds'}
