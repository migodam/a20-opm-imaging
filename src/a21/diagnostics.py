"""Frozen real-coordinate GN defect anatomy and solver-aware certificates.

Normal recovery is independent of this module. We verify its representation
and expose numerical feasibility/complementarity separately from stationarity.
No optimizer, damping, feasibility projection, or physical action lives here.
"""
from __future__ import annotations

import numpy as np
from scipy import linalg as la


class ConsistencyFailure(RuntimeError):
    """A frozen model identity, independently checked normal, or bound failed."""


EPS = np.finfo(np.float64).eps
TINY = np.finfo(np.float64).tiny


def _norm(x):
    return float(la.norm(x))


def _ratio(numerator, denominator, resolution):
    return float(numerator / denominator) if denominator > resolution else None


def _audit_normal(audit, A, lower, step, config, label):
    normal = np.asarray(audit['normal'], dtype=float)
    mu = np.asarray(audit['multipliers'], dtype=float)
    values = step if A is None else A @ step
    slack = values - lower
    expected = -mu if A is None else -A.T @ mu
    if normal.shape != step.shape or mu.shape != lower.shape:
        raise ConsistencyFailure(label + '_NORMAL_SHAPE')
    if not all(np.all(np.isfinite(a)) for a in (normal, mu, slack)):
        raise ConsistencyFailure(label + '_NORMAL_NONFINITE')
    representation_error = _norm(normal - expected)
    normal_scale = max(_norm(normal), _norm(expected), TINY)
    representation_allowance = config.get('identity_rtol', 1e-9) * normal_scale + 100 * EPS * max(1., normal_scale)
    violation = max(0., float(-np.min(slack)))
    dual_violation = max(0., float(-np.min(mu)))
    complementarity = np.abs(mu * slack)
    tolerance = config.get('feasibility_tolerance', 1e-8)
    if representation_error > representation_allowance:
        raise ConsistencyFailure(label + '_INVALID_NORMAL_REPRESENTATION')
    if violation > tolerance or dual_violation > 100 * EPS * max(1., _norm(mu)):
        raise ConsistencyFailure(label + '_INVALID_NORMAL_FEASIBILITY_OR_SIGN')
    if np.max(complementarity, initial=0.) > tolerance * max(1., np.max(np.abs(mu), initial=0.)) + representation_allowance:
        raise ConsistencyFailure(label + '_INVALID_NORMAL_COMPLEMENTARITY')
    # A positive inactive slack may be tolerated by the original solver; it
    # cannot be silently treated as an exactly zero normal-cone defect.
    cscale = max(_norm(mu) * max(_norm(values), _norm(lower)), TINY)
    exact_at_roundoff = (violation <= 1000 * EPS * max(1., _norm(values), _norm(lower))
                        and float(np.sum(complementarity)) <= 1000 * EPS * cscale)
    return {'normal': normal, 'multipliers': mu, 'slack': slack,
            'violation': violation, 'dual_violation': dual_violation,
            'complementarity_L1': float(np.sum(complementarity)),
            'complementarity_Linf': float(np.max(complementarity, initial=0.)),
            'normal_representation_error': representation_error,
            'normal_representation_allowance': representation_allowance,
            'normal_valid': True, 'normal_exact_at_roundoff': bool(exact_at_roundoff),
            'active_indices': np.flatnonzero(slack <= tolerance)}


def evaluate(JF, JR, r, lam, ell, sF, sR, auditF, auditR, A, lower, config):
    """Return all scalar metrics and underlying real vectors/matrices.

    With exact feasible normals, E_R <= b_R. For numerical lower constraints,
    c_N = |mu_F*slack_F|_1 + |mu_R*slack_R|_1
          + |mu_F|_1 violation_R + |mu_R|_1 violation_F
    independently bounds (n_F-n_R)^T(s_R-s_F). Thus
    E_R <= (b_R + sqrt(b_R^2+4c_N))/2. We report the prescribed raw bound and
    this separate tolerance allowance; a large allowance is not evidence of
    exact interpolation or a scientifically small endpoint.
    """
    arrays = [np.asarray(v) for v in (JF, JR, r, ell, sF, sR)]
    if any(np.iscomplexobj(v) or not np.all(np.isfinite(v)) for v in arrays):
        raise ConsistencyFailure('ALL_GN_DIAGNOSTICS_REQUIRE_FINITE_REAL_COORDINATES')
    JF, JR, r, ell, sF, sR = [np.asarray(v, dtype=np.float64) for v in arrays]
    p = sF.size
    if JF.shape != JR.shape or JF.shape != (r.size, p) or ell.shape != (p,) or sR.shape != (p,):
        raise ConsistencyFailure('FROZEN_GN_DIMENSION_MISMATCH')
    Lambda = float(lam) * np.eye(p) if np.ndim(lam) == 0 else np.asarray(lam, dtype=float)
    if Lambda.shape != (p, p) or not np.all(np.isfinite(Lambda)):
        raise ConsistencyFailure('INVALID_FROZEN_REGULARIZER')
    HF, HR = JF.T @ JF + Lambda, JR.T @ JR + Lambda
    symmetry = max(_norm(HF-HF.T) / max(_norm(HF), TINY),
                   _norm(HR-HR.T) / max(_norm(HR), TINY),
                   _norm(Lambda-Lambda.T) / max(_norm(Lambda), TINY))
    if symmetry > 1e-12:
        raise ConsistencyFailure('HESSIAN_OR_REGULARIZER_NOT_SYMMETRIC')
    evF, evR, evL = la.eigvalsh(HF), la.eigvalsh(HR), la.eigvalsh(Lambda)
    if evF[0] <= 0 or evR[0] <= 0 or evL[0] < -100 * EPS * max(1., _norm(Lambda)):
        raise ConsistencyFailure('H_NORM_BOUND_INAPPLICABLE_NON_SPD')
    factorR = la.cho_factor(HR)
    factorF = la.cho_factor(HF)
    inv_energy = lambda v: float(np.sqrt(max(0., v @ la.cho_solve(factorR, v))))
    hnorm = lambda v, H: float(np.sqrt(max(0., v @ H @ v)))
    beta = float(la.eigh(HF, HR, eigvals_only=True)[-1])
    nF = _audit_normal(auditF, A, lower, sF, config, 'FULL')
    nR = _audit_normal(auditR, A, lower, sR, config, 'REDUCED')
    eF = r + JF @ sF
    delta_p = (JR-JF) @ sF
    delta_d = (JR-JF).T @ eF
    amplified = JR.T @ delta_p
    eta_sum = delta_d + amplified
    rho_F = JF.T @ eF + Lambda @ sF + ell + nF['normal']
    rho_R = JR.T @ (r+JR@sR) + Lambda @ sR + ell + nR['normal']
    eta_direct = JR.T @ (r+JR@sF) + Lambda @ sF + ell + nF['normal']
    identity_error = eta_direct - rho_F - delta_d - amplified
    identity_scale = max(_norm(eta_direct), _norm(rho_F)+_norm(delta_d)+_norm(amplified), TINY)
    identity_allowance = config.get('identity_rtol', 1e-9)*identity_scale + 100*EPS*max(1., identity_scale)
    if _norm(identity_error) > identity_allowance:
        raise ConsistencyFailure('STATIONARITY_DECOMPOSITION_IDENTITY_VIOLATION')
    gF0, gR0 = JF.T @ r + ell, JR.T @ r + ell
    kkt_F = _norm(rho_F) / max(_norm(gF0), 1e-12)
    kkt_R = _norm(rho_R) / max(_norm(gR0), 1e-12)
    if kkt_F > config.get('qp_kkt_rtol', 1e-8) or kkt_R > config.get('qp_kkt_rtol', 1e-8):
        raise ConsistencyFailure('FULL_OR_REDUCED_KKT_INVALID')
    eta_pair = rho_F + eta_sum - rho_R
    b_R = inv_energy(eta_pair)
    bound_HF = float(np.sqrt(beta) * b_R)
    difference = sR-sF
    error_HR, error_HF = hnorm(difference, HR), hnorm(difference, HF)
    reference_H = hnorm(sF, HF)
    c_N = (nF['complementarity_L1'] + nR['complementarity_L1']
           + float(np.sum(np.abs(nF['multipliers']))) * nR['violation']
           + float(np.sum(np.abs(nR['multipliers']))) * nF['violation'])
    adjusted_R = .5 * (b_R + np.hypot(b_R, 2*np.sqrt(c_N)))
    adjusted_F = float(np.sqrt(beta) * adjusted_R)
    # Fixed before inspecting any new errors. Normative residuals are carried
    # algebraically; this additional term concerns small dense floating-point.
    roundoff_scale = max(reference_H, error_HF, bound_HF,
                         np.sqrt(float(evF[-1])) * max(_norm(sF), _norm(sR)), TINY)
    fp_allowance = config.get('bound_roundoff_rtol', 1e-9)*roundoff_scale + 100*EPS*max(1., roundoff_scale)
    consistent = error_HF <= adjusted_F + fp_allowance
    if not consistent:
        exc = ConsistencyFailure('SOLVER_AWARE_HF_INEQUALITY_VIOLATION')
        exc.details = {'error_HF': error_HF, 'bound_HF': bound_HF,
                       'normal_adjusted_bound_HF': adjusted_F, 'floating_allowance': fp_allowance,
                       'normal_allowance_energy': c_N}
        raise exc
    q = lambda J, s: float(.5*_norm(r+J@s)**2 + ell@s + .5*s@Lambda@s)
    qFref, qRref = q(JF,sF), q(JR,sF)
    gapF, gapR = q(JF,sR)-qFref, qRref-q(JR,sR)
    normal_work = -float(nF['normal'] @ difference)
    rhoF_work = float(rho_F @ difference)
    full_identity = gapF - (.5*error_HF**2 + normal_work + rhoF_work)
    gapscale = max(abs(qFref), abs(q(JF,sR)), .5*error_HF**2, abs(normal_work), abs(rhoF_work), TINY)
    gapallowance = config.get('identity_rtol', 1e-9)*gapscale + 100*EPS*max(1.,gapscale)
    if abs(full_identity) > gapallowance:
        raise ConsistencyFailure('FULL_GAP_NORMAL_WORK_SOLVER_DEFECT_IDENTITY_VIOLATION')
    zero_slack = -np.asarray(lower)
    zero_feasible = bool(np.min(zero_slack) >= -config.get('feasibility_tolerance',1e-8))
    reduction = q(JF,np.zeros(p))-qFref if zero_feasible else None
    reduction_resolution = 100*EPS*max(abs(q(JF,np.zeros(p))),abs(qFref),TINY)
    step_resolution = max(config.get('reference_H_norm_floor',1e-12),
                          100*EPS*np.sqrt(float(evF[-1]))*max(1.,_norm(sF)))
    reference_solver_H_bound = float(np.sqrt(max(0.,rho_F@la.cho_solve(factorF,rho_F))))
    well_scaled = reference_H > step_resolution and reference_solver_H_bound < .05*reference_H
    dp_denom, dd_denom = _norm(JF@sF), _norm(JF.T@eF)
    dp_resolution = config.get('endpoint_denominator_epsilon_multiplier',100)*EPS*max(_norm(JF)*_norm(sF),TINY)
    dd_resolution = config.get('endpoint_denominator_epsilon_multiplier',100)*EPS*max(_norm(JF)*_norm(eF),TINY)
    kkt_scale = _norm(JF.T@eF)+_norm(Lambda@sF)+_norm(ell)+_norm(nF['normal'])
    sum_norms = _norm(delta_d)+_norm(amplified)
    cosine = float(delta_d@amplified/(_norm(delta_d)*_norm(amplified))) if _norm(delta_d)*_norm(amplified)>TINY else None
    material_cosine = float(sF@sR/(_norm(sF)*_norm(sR))) if _norm(sF)*_norm(sR)>TINY else None
    hcosine = float(sF@HF@sR/(hnorm(sF,HF)*hnorm(sR,HF))) if hnorm(sF,HF)*hnorm(sR,HF)>TINY else None
    metrics = {
        'relative_H_step_error': error_HF/reference_H if well_scaled else None,
        'absolute_H_step_error': error_HF, 'H_R_step_error': error_HR,
        'euclidean_step_error': _norm(difference), 'reference_H_norm': reference_H,
        'reference_H_energy': reference_H**2, 'reference_step_norm': _norm(sF),
        'reference_H_resolution': step_resolution, 'reference_solver_H_bound':reference_solver_H_bound,
        'well_scaled_reference': bool(well_scaled), 'relative_H_status':'DEFINED' if well_scaled else 'ILL_SCALED_REFERENCE',
        'epsilon_P':_ratio(_norm(delta_p),dp_denom,dp_resolution),
        'epsilon_D':_ratio(_norm(delta_d),dd_denom,dd_resolution),
        'primal_endpoint_denominator':dp_denom, 'dual_endpoint_denominator':dd_denom,
        'primal_endpoint_resolution':dp_resolution, 'dual_endpoint_resolution':dd_resolution,
        'delta_p_norm':_norm(delta_p), 'delta_d_norm':_norm(delta_d),
        'amplified_primal_norm':_norm(amplified), 'eta_sum_norm':_norm(eta_sum),
        'eta_direct_norm':_norm(eta_direct), 'identity_error_norm':_norm(identity_error),
        'identity_relative_error':_norm(identity_error)/identity_scale,
        'identity_allowance':identity_allowance, 'rho_F_norm':_norm(rho_F),'rho_R_norm':_norm(rho_R),
        'reference_KKT_relative':kkt_F,'reduced_KKT_relative':kkt_R,
        'epsilon_KKT':_ratio(_norm(eta_direct),kkt_scale,100*EPS*max(kkt_scale,TINY)),
        'KKT_scale':kkt_scale, 'normal_F_norm':_norm(nF['normal']), 'normal_R_norm':_norm(nR['normal']),
        'mu':float(evR[0]),'beta':beta,'lambda_min_Lambda':float(evL[0]),
        'lambda_min_HF':float(evF[0]),'lambda_max_HF':float(evF[-1]),
        'lambda_max_HR':float(evR[-1]),'condition_HF':float(evF[-1]/evF[0]),
        'condition_HR':float(evR[-1]/evR[0]),'Hessian_symmetry_error':symmetry,
        'b_solver':b_R,'bound_HF':bound_HF,'bound_ratio':_ratio(error_HF,bound_HF,100*EPS*max(reference_H,TINY)),
        'bound_consistent':bool(consistent),'bound_floating_allowance':fp_allowance,
        'normal_allowance_energy':c_N,'normal_allowance_bound_HF':adjusted_F-bound_HF,
        'normal_adjusted_bound_HF':adjusted_F,'normal_monotonicity_work':float((nF['normal']-nR['normal'])@difference),
        'b_dual':inv_energy(delta_d),'b_primal':inv_energy(amplified),
        'b_stationarity':inv_energy(eta_sum),'cancellation_indicator':_norm(eta_sum)/sum_norms if sum_norms>TINY else None,
        'dual_primal_cosine':cosine,'material_cosine':material_cosine,'H_cosine':hcosine,
        'step_norm_ratio':_ratio(_norm(sR),_norm(sF),step_resolution/np.sqrt(evF[-1])),
        'H_step_norm_ratio':_ratio(hnorm(sR,HF),reference_H,step_resolution),
        'full_quadratic_gap':gapF,'reduced_quadratic_gap':gapR,'normal_work':normal_work,
        'rhoF_work':rhoF_work,'full_gap_identity_error_norm':abs(full_identity),
        'full_gap_identity_allowance':gapallowance,
        'predicted_reduction':reduction,'zero_feasible':zero_feasible,
        'predicted_reduction_well_scaled':bool(reduction is not None and reduction>reduction_resolution),
        'full_gap_over_predicted_reduction':gapF/reduction if reduction is not None and reduction>reduction_resolution else None,
        'full_objective_directional_derivative':float(gF0@sR),
        'q_F_sF':qFref,'q_R_sF':qRref,'q_F_sR':q(JF,sR),'q_R_sR':q(JR,sR),
        'reduced_gap_upper_exact_reference':.5*inv_energy(eta_direct)**2,
        'exact_reference_gap_lower_claimed':False,
        'normals_valid':True,'normal_F_exact_at_roundoff':nF['normal_exact_at_roundoff'],
        'normal_R_exact_at_roundoff':nR['normal_exact_at_roundoff'],
        'feasibility_F':nF['violation'],'feasibility_R':nR['violation'],
        'complementarity_F_L1':nF['complementarity_L1'],'complementarity_R_L1':nR['complementarity_L1'],
        'active_constraints_F':int(len(nF['active_indices'])),'active_constraints_R':int(len(nR['active_indices'])),
        'active_sets_equal':bool(np.array_equal(nF['active_indices'],nR['active_indices'])),
        'H_error_scientific_target_pass':bool(well_scaled and error_HF/reference_H<=config.get('scientific_H_error_target',.05)),
        'no_denominator_floor_used':True,
    }
    vectors = dict(J_F=JF,J_R=JR,H_F=HF,H_R=HR,Lambda=Lambda,r=r,ell=ell,s_F=sF,s_R=sR,e_F=eF,
                   delta_p=delta_p,delta_d=delta_d,amplified_primal=amplified,eta_sum=eta_sum,
                   eta_direct=eta_direct,eta_pair=eta_pair,identity_error=identity_error,
                   rho_F=rho_F,rho_R=rho_R,n_F=nF['normal'],n_R=nR['normal'],
                   multipliers_F=nF['multipliers'],multipliers_R=nR['multipliers'],
                   slack_F=nF['slack'],slack_R=nR['slack'],
                   active_indices_F=nF['active_indices'],active_indices_R=nR['active_indices'])
    return metrics, vectors
