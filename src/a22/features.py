"""Registered shallow-model error budgets; no full derivative or label queries.

All four predictors see the same geometry, anchor and fixed material map. The
regularized witness is common to A1--A3. Calibration does not turn an indicator
into a uniform Maxwell certificate.
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np
from scipy import linalg as la

from a20.backend import unpack, pack
from .core import profiled_witness


def _rnorm_complex_map(matrix):
    """Norm from REAL material coordinates into complex current blocks."""
    a = np.asarray(matrix).reshape(-1, matrix.shape[-1])
    return float(la.norm(np.concatenate((a.real, a.imag), axis=0), 2))


@dataclass
class DescriptorContext:
    model: object
    B: np.ndarray
    IR: np.ndarray
    LH_Q: np.ndarray
    lambda_value: float
    material_norm: float
    propagated_norm: float
    injection_defect_norm: float
    observation_norm: float
    full_observation_norm: float
    observation_defect_norm_bound: float
    propagation_norm: float
    background_F_norm_bound: float
    full_L_minimum_bound: float | None
    Goff_norm_bound: float
    voxel_injection_norm: float
    declared_object_radius: float
    provenance: dict


def build_descriptor_context(model, config):
    """Paid primal/dual *residual* actions, not full primal/dual solves."""
    adapter, book = model.anchor.adapter, model.anchor.adapter.book
    projection, Q = model.projection, model.basis
    projection.check()
    with book.span('a22_descriptor_residual_cache', descriptor_cache_builds=1):
        B = model.view.B(np.eye(32))
        IR = B - np.einsum('nq,pqd->pnd', projection.LZ, model.PMW)
        LH_Q = model.view.L_adjoint(Q)
        Pnorm = float(la.norm(projection.solve(np.eye(Q.shape[1])), 2))
        Mnorm = _rnorm_complex_map(model.MW)
        Cnorm = _rnorm_complex_map(model.PMW)
        IRnorm = _rnorm_complex_map(IR)
        Onorm = float(adapter.whitening) * float(la.norm(projection.SZ, 2))
        # ||S-S R L|| <= ||S|| + ||S Q|| ||P|| ||Q* L||.
        Snorm = float(adapter.whitening) * float(la.norm(adapter.model.GS, 2))
        Odef = Snorm + Onorm * Pnorm * float(la.norm(LH_Q, 2))
        # A cheap sufficient Neumann test. It is allowed to be inconclusive.
        # The paid full L is a known-background operator, NOT a material J/H.
        absolute = np.abs(adapter._operator_L)
        diag = np.diag_indices_from(absolute)
        absolute[diag] = np.abs(1. - np.diag(adapter._operator_L))
        Fbound = float(np.sqrt(absolute.sum(axis=0).max() * absolute.sum(axis=1).max()))
        margin = 1. - Fbound
        alpha = margin if margin > 0. else None
        del absolute
        factor = adapter.injection_factor(model.anchor.chi, model.anchor.state)
        voxel_B_norm = float(np.max(np.sqrt(np.sum(abs(factor)**2, axis=(0, 2)))/np.sqrt(adapter.problem.volume)))
        object_radius = float(config.get('descriptor_material_pointwise_prior', .25))*np.sqrt(
            adapter.problem.volume*adapter.model.N)
        absolute = np.abs(adapter.model.Goff)
        Gbound = float(np.sqrt(absolute.sum(axis=0).max() * absolute.sum(axis=1).max()))
        del absolute
    provenance = {
        'origin': 'known_background_OPM_and_residual_actions',
        'full_J_full_H_full_adjoint_or_truth_used': False,
        'IR_definition': 'B - L Q (Q* L Q)^-1 Q* B, six source blocks',
        'OR_dual_definition': 'S_white* h - L* Q (Q* L Q)^-* Q* S_white* h',
        'full_L_margin_origin': '1 - sqrt(norm1(F) normInf(F)), sufficient only',
        'full_L_minimum_bound': alpha,
        'background_F_norm_bound': Fbound,
        'missing_positive_margin': alpha is None,
        'polarizability_nonlinearity_included': True,
        'certificate_type': 'empirical_indicator',
        'model_component_certificate_type': 'deterministic_bound' if alpha is not None else 'empirical_indicator',
        'physical_calibration_budget': 'source amplitude 5%, receiver gain 3%, same Maxwell source/receiver layout',
        'regularization': float(config['tikhonov_relative']) * float(la.svdvals(model.AW)[0]**2),
        'declared_material_pointwise_prior': float(config.get('descriptor_material_pointwise_prior', .25)),
        'declared_material_radius': object_radius,
        'W_external_response': 'known-background voxel injection residual, no truth projection used',
        'calibration_capacity': 'one nonnegative multiplicative coefficient per method, same fit scenes',
    }
    return DescriptorContext(model, B, IR, LH_Q,
        provenance['regularization'], Mnorm, Cnorm, IRnorm, Onorm, Snorm, Odef,
        Pnorm, Fbound, alpha, Gbound, voxel_B_norm, object_radius, provenance)


def _dual_residual(context, h):
    model = context.model
    adapter, projection = model.anchor.adapter, model.projection
    observation = unpack(adapter.whiten(h, adjoint=True), adapter.P, adapter.m)
    rhs = model.view.S_adjoint(observation.T)
    coeff = projection.solve(model.basis.conj().T @ rhs, adjoint=True)
    psi = model.basis @ coeff
    defect = rhs - context.LH_Q @ coeff
    return psi.T, defect.T, coeff


def _polar_remainder_radius(context, radius):
    """Actual CM/radiation-reaction second derivative, over a material ball.

    a''=-18 v c/(3+c chi)^3, c=1-i 3 k^3 v/(6 pi). The
    denominator lower bound is explicit. An unavailable full-region resolvent
    is recorded as unavailable instead of being filled by a hidden constant.
    """
    model, anchor = context.model, context.model.anchor
    adapter, state = anchor.adapter, anchor.state
    v, k = adapter.problem.volume, adapter.problem.frequency
    c = 1.-1j*3.*k**3/(6.*np.pi)*v
    row_norm = la.norm(adapter.chart.Q, axis=1)
    # The object prior is a declared physical cell-amplitude scale, not the
    # realized truth norm. Target/nuisance perturbations add the W-ball radius.
    prior = context.declared_object_radius/np.sqrt(v*adapter.model.N)
    dchi_radius = prior+row_norm*radius
    den_min = np.abs(3.+c*anchor.chi)-abs(c)*dchi_radius
    if np.min(den_min) <= 0:
        return {'status': 'POLARIZABILITY_REGION_POLE_NOT_EXCLUDED', 'bound': None}
    first = 9.*v/den_min**2
    second = 18.*v*abs(c)/den_min**3
    exciting = state.exciting.reshape(adapter.P, adapter.model.N, 3)
    weight = np.sum(abs(exciting)**2, axis=(0, 2))/v
    polar = float(np.sqrt(np.sum(weight*(.5*second*dchi_radius**2)**2)))
    injection = float(np.sqrt(np.sum(weight*(first*dchi_radius)**2)))
    delta_L = float(np.max(first*dchi_radius))*context.Goff_norm_bound
    margin = context.full_L_minimum_bound
    resolvent_margin = None if margin is None else margin-delta_L
    if resolvent_margin is not None and resolvent_margin > 0:
        remainder = polar + delta_L*injection/resolvent_margin
        status = 'REGISTERED_REGION_BOUND'
    else:
        # A deployable indicator, with the missing stability premise explicit.
        # No full solve, inverse, or pseudoinverse is used to manufacture it.
        remainder = polar + delta_L*injection
        status = 'EMPIRICAL_REMAINDER_INDICATOR_NO_REGION_RESOLVENT'
    return dict(status=status, bound=remainder, polarizability_second_term=polar,
                feedback_remainder_term=remainder-polar,
                minimum_denominator=float(np.min(den_min)), delta_L_bound=delta_L,
                region_resolvent_margin=resolvent_margin,
                certificate_type='deterministic_bound' if status=='REGISTERED_REGION_BOUND' else 'empirical_indicator')


def direction_descriptor(context, v, config):
    """A direction descriptor is frozen BEFORE any recovery label exists."""
    model, book = context.model, context.model.anchor.adapter.book
    adapter = model.anchor.adapter
    A = model.AW
    if np.iscomplexobj(v):
        raise ValueError('A22_DIRECTION_MUST_BE_REAL')
    v = np.asarray(v, float)
    if v.shape != (A.shape[1],) or not np.all(np.isfinite(v)):
        raise ValueError('A22_DIRECTION_LAYOUT_OR_FINITENESS_FAILED')
    length = float(la.norm(v))
    if length == 0:
        raise ValueError('A22_DESCRIPTOR_REQUIRES_NONZERO_DIRECTION')
    v = v/length
    with book.span('a22_direction_descriptor', direction_descriptor_builds=1):
        witness = profiled_witness(A, v)
        h = A @ la.solve(A.T@A+context.lambda_value*np.eye(32), v, assume_a='pos')
        psi, dual, adj_coeff = _dual_residual(context, h)
        back = A.T@h-v
        N = witness['N']
        MWv = np.einsum('pqd,d->pq', model.MW, v)
        PMWv = np.einsum('pqd,d->pq', model.PMW, v)
        IRv = np.einsum('pnd,d->pn', context.IR, v)
        IRn = np.einsum('pnd,dk->pnk', context.IR, N)
        a, z, response = float(la.norm(MWv)), float(la.norm(PMWv)), float(la.norm(A@v))
        dual_material = model.view.B_adjoint(psi)
        # Pull back into the *voxel mass metric* and remove the fixed W span.
        # This is a B* action at the paid anchor, not a full J* solve.
        with book.span('a22_W_external_injection_pullback', B_adjoint_voxel_rhs=adapter.P):
            factor = adapter.injection_factor(model.anchor.chi, model.anchor.state)
            gv = np.einsum('ptc,ptc->t', factor.conj(), psi.reshape(adapter.P, adapter.model.N, 3))
            gv /= np.sqrt(adapter.problem.volume)
            Hspatial = np.sqrt(adapter.problem.volume)*adapter.chart.Q
            outside = gv-Hspatial@(Hspatial.T@gv)
        transpose_error = float(la.norm(dual_material-A.T@h))/max(1., float(la.norm(A.T@h)))
        if transpose_error > 1e-9:
            raise ValueError('A22_REAL_WHITENED_REDUCED_ADJOINT_IDENTITY_FAILED')
        h0 = (A@v)/(response**2+context.lambda_value)
        # Background calibration intercept respects correlated source blocks.
        bg = model.anchor.adapter.whiten(pack(model.anchor.state.field))
        hblock = h.reshape(6, 2, model.anchor.adapter.m)
        bgblock = bg.reshape(6, 2, model.anchor.adapter.m)
        background_budget = .05*float(np.sum(abs(np.sum(hblock*bgblock, axis=(1, 2)))))
        background_budget += .03*float(np.sum(abs(np.sum(hblock*bgblock, axis=(0, 1)))))
        background_budget += .0015*float(la.norm(h)*la.norm(bg))
    return dict(v=v, N=N, h=h, h0=h0, h_norm=float(la.norm(h)),
        bias_target=float(abs(back@v)), bias_nuisance=float(la.norm(N.T@back)),
        total_gain=response, profile_g=float(witness['g']), attribution=witness['attribution'],
        profile_noise_gain=None if witness['h'] is None else float(la.norm(witness['h'])),
        alpha=a, beta=z/a if a else None, gamma=response/z if z else None,
        psi_norm=float(la.norm(psi)), dual_defect_norm=float(la.norm(dual)),
        adj_coeff_norm=float(la.norm(adj_coeff)),
        IR_direction_norm=float(la.norm(IRv)), IR_nuisance_norm=_rnorm_complex_map(IRn),
        propagated_direction_norm=z, nuisance_propagation_norm=context.propagated_norm,
        background_calibration_budget=background_budget,
        background_agnostic_budget=.0815*float(la.norm(h)*la.norm(bg)),
        transpose_identity_error=transpose_error,
        W_external_witness_norm=float(la.norm(outside)),
        provenance={'full_J_or_labels_used': False, 'witness_origin': 'common regularized shallow AW',
                    'profile_origin': 'complete complement, no noisy-mode deletion'},
        unidentifiable=witness['status']!='OK')


def predict_budget(context, descriptor, amplitude, noise_level, intervention, config):
    """Absolute coefficient-error budgets, and separated components."""
    book = context.model.anchor.adapter.book
    with book.span('a22_budget_prediction', descriptor_predictions=1):
        a = abs(float(amplitude))
        eta = float(config['nuisance_fraction'])
        perturbation_radius = a*np.sqrt(1.+eta**2)
        prior_radius = context.declared_object_radius
        rho = prior_radius+perturbation_radius
        noise = float(noise_level)*descriptor['h_norm']
        back_norm = np.sqrt(descriptor['bias_target']**2+descriptor['bias_nuisance']**2)
        bias = prior_radius*back_norm+a*(descriptor['bias_target']+eta*descriptor['bias_nuisance'])
        ir_radius = prior_radius*context.injection_defect_norm+a*(descriptor['IR_direction_norm']+eta*descriptor['IR_nuisance_norm'])
        alpha = context.full_L_minimum_bound
        divisor = alpha if alpha is not None else 1.
        rom2 = descriptor['h_norm']*context.observation_defect_norm_bound*ir_radius/divisor
        rom3 = descriptor['dual_defect_norm']*ir_radius/divisor
        nonlinear = _polar_remainder_radius(context, perturbation_radius)
        if nonlinear['bound'] is None:
            non2 = non3 = None
        else:
            S = context.full_observation_norm
            non2 = descriptor['h_norm']*S/divisor*nonlinear['bound']
            non3 = (descriptor['psi_norm']+descriptor['dual_defect_norm']/divisor)*nonlinear['bound']
        calibration = intervention!='nominal'
        fac2 = fac3 = 0.
        ext2 = descriptor['h_norm']*context.full_observation_norm*context.voxel_injection_norm*prior_radius/divisor
        ext3 = (descriptor['W_external_witness_norm']+
            context.voxel_injection_norm*descriptor['dual_defect_norm']/divisor)*prior_radius
        if calibration:
            ext2 *= 1.0815
            ext3 *= 1.0815
        if calibration:
            fac2 = .0815*descriptor['h_norm']*context.observation_norm*context.propagation_norm*context.material_norm*rho
            epsM, epsO = .05*context.material_norm, .03*context.observation_norm
            zbar = prior_radius*context.propagated_norm+a*(descriptor['propagated_direction_norm']+eta*descriptor['nuisance_propagation_norm'])+context.propagation_norm*epsM*rho
            fac3 = epsM*descriptor['adj_coeff_norm']*rho+epsO*descriptor['h_norm']*zbar
            fac2 += descriptor['background_agnostic_budget']
            fac3 += descriptor['background_calibration_budget']
        A0 = np.sqrt((float(noise_level)*la.norm(descriptor['h0']))**2 +
                     ((prior_radius+a)*context.lambda_value/(descriptor['total_gain']**2+context.lambda_value))**2)
        A1 = np.sqrt(noise**2+bias**2)
        # Norm budgets are forecasts, not observed-error fitting targets.
        A2 = None if non2 is None else np.sqrt(noise**2+(bias+rom2+non2+fac2+ext2)**2)
        A3 = None if non3 is None else np.sqrt(noise**2+(bias+rom3+non3+fac3+ext3)**2)
        valid = alpha is not None and nonlinear['status']=='REGISTERED_REGION_BOUND'
        return dict(pred_A0=float(A0), pred_A1=float(A1), pred_A2=None if A2 is None else float(A2),
                    pred_A3=None if A3 is None else float(A3), noise_sd=noise, attribution_bias_budget=bias,
                    unstructured_ROM_budget=rom2, paired_ROM_budget=rom3,
                    unstructured_nonlinear_budget=non2, paired_nonlinear_budget=non3,
                    unstructured_factor_budget=fac2, structured_factor_budget=fac3,
                    unstructured_W_external_budget=ext2, paired_W_external_budget=ext3,
                    declared_object_material_radius=prior_radius,
                    material_radius=rho, nonlinear=nonlinear,
                    certificate_type='empirical_indicator',
                    full_model_uniform_certificate=False,
                    region_model_components_valid=valid,
                    uniform_certificate_limitation='original object may exceed declared 0.25 pointwise prior; checked only offline',
                    receiver_or_source_actual_signs_used=False,
                    full_reference_or_true_error_used=False)
