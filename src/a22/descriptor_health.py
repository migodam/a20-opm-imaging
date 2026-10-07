"""Small paid backend identity checks for the registered forecasting code."""
from pathlib import Path
import numpy as np
from scipy import linalg as la
from a20.backend import kernel, pack
from a20.costs import write_json
from .validation import tiny_problem
from .online import build_anchor, build_opm
from .features import build_descriptor_context, direction_descriptor, predict_budget
from .evaluate import finite_label, evaluate_recovery


def run_descriptor_health(root, config, book, *, device='cpu'):
    output = Path(root)/'results/a22/validation/descriptor_health'/f'{book.job_id}.json'
    if output.exists():
        raise FileExistsError('DESCRIPTOR_HEALTH_OUTPUT_EXISTS')
    checks = []
    report = dict(status='FAILED', evidence='tiny DenseDDA only, no project gate', checks=checks)
    def close(name, observed, expected, tolerance=1e-9):
        error = float(la.norm(np.ravel(observed-expected)))/max(float(la.norm(np.ravel(expected))),1e-30)
        checks.append(dict(name=name, relative_error=error, tolerance=tolerance,
                           status='PASS' if error<=tolerance else 'FAIL'))
        if error>tolerance:
            raise AssertionError(name)
    try:
        problem, _ = tiny_problem(config)
        anchor = build_anchor(problem, config, book, device=device)
        model = build_opm(anchor, config)
        context = build_descriptor_context(model, config)
        v = np.zeros(32)
        v[1] = 1.
        desc = direction_descriptor(context, v, config)
        predictions = [predict_budget(context,desc,a,0.,'nominal',config) for a in (.001,.004,.01)]
        with book.scope('offline_evaluation'), book.action_guard('full_J',role='offline_evaluation'):
            J = anchor.adapter.full_tangent_action(anchor.chi, anchor.state, np.eye(32))
            rhs = context.IR.transpose(1,0,2).reshape(anchor.adapter.n,-1)
            with book.span('a22_descriptor_health_defect_reference',
                           health_reference_full_RHS=6*32, health_reference_receiver_RHS=6*32):
                residual_solution = anchor.adapter.model.solver.solve(anchor.state._L_factor,
                    rhs, label='full_health_defect')
                paired = context.model.view.S(residual_solution).reshape(128,6,32).transpose(1,0,2)
                # O_R L^-1 I_R = S X - S Q P Q* L X.
                coeff = model.projection.solve(model.basis.conj().T@(anchor.state.L@residual_solution))
                correction = model.projection.SZ@coeff
                correction = correction.reshape(128,6,32).transpose(1,0,2)
                paired = anchor.adapter.whiten(pack(paired-correction))
                book.counts['health_reference_residual_L_rhs'] += 6*32
            close('actual_two_sided_defect_identity', paired, J-model.AW)
        volume,k = problem.volume,problem.frequency
        c=1.-1j*3.*k**3/(6.*np.pi)*volume
        exact=-18.*volume*c/(3.+c*anchor.chi)**3
        eps=1e-5
        finite=(kernel.polarizability(anchor.chi+eps,volume,k)[1]-
                kernel.polarizability(anchor.chi-eps,volume,k)[1])/(2*eps)
        close('actual_polarizability_second_derivative',finite,exact,1e-7)
        measurements=[]
        for amplitude, forecast in zip((.001,.004,.01), predictions):
            raw, _ = finite_label(model, amplitude*v, book, purpose='descriptor_health_finite')
            tangent_remainder=anchor.adapter.whiten(pack(raw-anchor.state.field))-J@(amplitude*v)
            scalar=float(abs(desc['h']@tangent_remainder))
            measurements.append(dict(amplitude=amplitude,
                task_remainder=scalar, paired_nonlinear_budget=forecast['paired_nonlinear_budget'],
                certificate_type=forecast['certificate_type']))
            if forecast['region_model_components_valid'] and scalar>forecast['paired_nonlinear_budget']*(1.+1e-9):
                raise AssertionError('TASK_NONLINEAR_COMPONENT_BOUND_VIOLATED')
            solution,audit = evaluate_recovery(model,raw,config,book)
            if audit['qp']['kkt_relative']>config['qp_kkt_rtol']:
                raise AssertionError('COMMON_MATERIAL_SOLVE_KKT')
        report.update(status='PASS', predictions_frozen_before_J=True,
            current_rank=model.basis.shape[1], nonlinear_measurements=measurements,
            region_uniform_project_certificate=False, context_provenance=context.provenance)
        return report
    except BaseException as error:
        report.update(error_type=type(error).__name__, error=str(error))
        raise
    finally:
        write_json(output,report)
