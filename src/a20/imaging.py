"""Common constrained nonlinear loop; A2 differentiates its frozen state.

Offline labels are read by the caller AFTER a run, never by this engine.
The full objective and full KKT audit are paid by every method.
"""
from __future__ import annotations
import time
import numpy as np
from scipy import linalg as la
from .backend import Adapter, BasisView, ReducedState, pack
from .opm import (orth, SchurFeedback, build_seeds, Hierarchy, Projection,
                  ReducedJacobian, FullJacobian, UnsafeCore, BlockStream)
from .material import solve_quadratic, kkt, QPFailure
from .costs import plain


def basis_model(adapter, x, state, residual, previous, method, degree, config):
    view = BasisView(adapter, x, state, residual, previous)
    U = view.receiver(config['retained_rank'])
    retained_fallback = None
    try:
        schur = SchurFeedback(view, U, config)
    except UnsafeCore:
        retained_fallback = 'unsafe_retained_to_empty_U'
        adapter.book.counts['empty_U_fallbacks'] += 1
        U = np.empty((adapter.n, 0), complex)
        schur = SchurFeedback(view, U, config)
    if method.startswith('OPM'):
        seeds = build_seeds(view, schur, config)
        hierarchy = Hierarchy(view, schur, seeds, config)
        Z, info = hierarchy.at_degree(degree)
        info.update(seed_provenance=seeds.records, seed_rng=seeds.rng_seed,
                    retained_fallback=retained_fallback)
    elif method == 'SOM':
        rank = min(adapter.m, len(U)+12*(degree+1))
        Z = view.receiver(rank)
        info = {'degree': None, 'rank': Z.shape[1], 'seed_provenance': 'receiver geometry only'}
    elif method == 'KRYLOV':
        rng = np.random.default_rng(np.random.SeedSequence([config['master_seed'], adapter.problem.parent_id, 731]))
        seed, rec = orth(rng.normal(size=(adapter.n, 12))+1j*rng.normal(size=(adapter.n, 12)), against=U)
        stream = BlockStream(seed, schur.F, adapter.book, config['orthogonal_rank_rtol'])
        for _ in range(degree):
            stream.extend()
        q, deflation = orth(stream.basis, against=U)
        Z = np.column_stack((U, q))
        info = {'degree': degree, 'rank': Z.shape[1], 'seed_provenance': 'independent right current probes, ordinary block Krylov',
                'seed_rng': [config['master_seed'], adapter.problem.parent_id, 731],
                'seed_deflation': rec, 'joint_deflation': deflation,
                'separate_stream_recurrences': stream.recurrence}
    else:
        raise ValueError('Unregistered imaging representation:'+method)
    projection = Projection(adapter, x, Z, config)
    info.update(core=projection.stability, galerkin_core=projection.galerkin_stability,
                projection=projection.kind, fallback=projection.fallback,
                orthogonality_error=float(la.norm(Z.conj().T@Z-np.eye(len(Z.T)))))
    return projection, info


def zero_state(adapter, x):
    """A2 bootstrap: known incident field, zero current; no full-state seed."""
    _, da = __import__('a20_vendor_a9').polarizability(x, adapter.problem.volume, adapter.problem.frequency)
    return ReducedState(x.copy(), np.zeros((adapter.P, adapter.n), complex), adapter.model.incident.copy(),
                        da, np.zeros((adapter.P, adapter.m), complex), adapter.version(x), adapter.model)


def reconstruct(problem, config, book, device, *, method='FULL_GN', degree=0,
                mode='A1', adapter=None, iteration_sink=None, experiment_id=''):
    """One real reconstruction. Caches are tied to unchanged material only."""
    book.synchronize()
    started = time.perf_counter()
    before = book.snapshot()
    setup_start = time.perf_counter()
    a = adapter or Adapter(problem, device=device, book=book)
    setup_wall = time.perf_counter()-setup_start
    x = problem.init.copy()
    previous = None
    predictor = None
    iterations = []
    initial_gradient = None
    status, failure, audit_wall = 'CAPPED', None, 0.
    last_full_kkt = None
    state = None
    fallback_count = 0
    last_info = {'rank': a.n, 'degree': None, 'projection': 'full'}
    try:
        for outer in range(config['max_updates']):
            book.check()
            it_start = time.perf_counter()
            snapshot = book.snapshot()
            # Full nonlinear acceptance and stopping cost cannot be hidden.
            audit_start = time.perf_counter()
            objective, full_r, state = a.full_objective(x, config['prior'], state=state)
            full_jac = FullJacobian(a, x, state)
            physical_z = problem.chart.project(x-problem.init)
            full_gradient = full_jac.pullback(full_r)+config['prior']*physical_z
            current_kkt = kkt(problem.chart, x, np.zeros(a.p), full_gradient,
                              tolerance=config['feasibility_tolerance'])
            if initial_gradient is None:
                initial_gradient = max(current_kkt['stationarity_norm'], 1e-12)
            last_full_kkt = current_kkt['stationarity_norm']/initial_gradient
            audit_wall += time.perf_counter()-audit_start
            if last_full_kkt <= config['common_full_kkt_rtol']:
                status = 'CONVERGED_FULL_KKT'
                break
            lam = config['prior']+config['lm0']*config['lm_decay']**(outer//config['lm_decay_period'])
            ell = config['prior']*physical_z
            r, jac, projection = full_r, full_jac, None
            info = {'rank': a.n, 'degree': None, 'projection': 'full'}
            model_state = state
            fallback_reason = None
            if method != 'FULL_GN':
                try:
                    if mode == 'A2':
                        # Refresh the previous frozen space at this material
                        # for seed injection. Its current never comes from truth
                        # or an exact full-current correction.
                        if predictor is None:
                            seed_state = zero_state(a, x)
                        else:
                            seed_projection = predictor.trial(x)
                            seed_state = a.reduced_state(x, seed_projection)
                        seed_residual = a.residual(seed_state)
                    else:
                        seed_state, seed_residual = state, full_r
                    projection, info = basis_model(a, x, seed_state, seed_residual, previous, method, degree, config)
                    model_state = a.reduced_state(x, projection) if mode == 'A2' else state
                    r = a.residual(model_state) if mode == 'A2' else full_r
                    jac = ReducedJacobian(a, x, model_state, projection)
                    if projection.fallback:
                        fallback_count += 1
                except UnsafeCore as exc:
                    fallback_reason = str(exc)
                    fallback_count += 1
                    book.counts['full_model_fallbacks'] += 1
                    r, jac, projection, model_state = full_r, full_jac, None, state
                    info = {'rank': a.n, 'degree': degree, 'projection': 'full_fallback', 'fallback': fallback_reason}
            try:
                step, qp, normal = solve_quadratic(problem.chart, x, r, jac, lam, ell, config, book)
            except QPFailure as exc:
                if method == 'FULL_GN' or projection is None:
                    raise
                # A failed reduced QP is not salvaged by clipping or a ridge.
                fallback_reason = 'reduced_QP_failed:'+str(exc)
                fallback_count += 1
                book.counts['full_model_fallbacks'] += 1
                r, jac, projection, model_state = full_r, full_jac, None, state
                info = {'rank': a.n, 'degree': degree, 'projection': 'full_fallback',
                        'fallback': fallback_reason, 'failed_reduced_QP': getattr(exc, 'result', {})}
                step, qp, normal = solve_quadratic(problem.chart, x, r, jac, lam, ell, config, book)
            model_jstep = jac.action(step)
            predicted = float(-((jac.pullback(r)+ell)@step+.5*(model_jstep@model_jstep+lam*(step@step))))
            # Armijo slope is the actual full objective derivative.
            slope = float(full_gradient@step)
            if slope >= 0 or not np.isfinite(slope):
                status, failure = 'NON_DESCENT', 'Full objective derivative is nonnegative'
                break
            accepted, trial_logs = False, []
            alpha = 1.
            for trial in range(config['line_trials']):
                book.check()
                candidate = x+alpha*problem.chart.expand(step)
                if a.material_constraints(candidate)['violation'] > config['feasibility_tolerance']:
                    trial_logs.append({'trial': trial, 'alpha': alpha, 'status': 'INFEASIBLE'})
                    alpha *= config['backtracking']
                    continue
                reduced_trial_objective = None
                reduced_trial_status = None
                if mode == 'A2' and projection is not None:
                    try:
                        trial_projection = projection.trial(candidate)
                        trial_reduced = a.reduced_state(candidate, trial_projection)
                        trial_r = a.residual(trial_reduced)
                        trial_z = problem.chart.project(candidate-problem.init)
                        reduced_trial_objective = float(.5*trial_r@trial_r+.5*config['prior']*(trial_z@trial_z))
                        reduced_trial_status = 'COHERENT_FROZEN_BASIS'
                    except UnsafeCore as exc:
                        reduced_trial_status = 'FULL_FALLBACK:'+str(exc)
                        fallback_count += 1
                        book.counts['full_trial_fallbacks'] += 1
                with book.span('full_objective_globalization', globalization_trials=1):
                    trial_objective, trial_full_r, trial_full_state = a.full_objective(candidate, config['prior'])
                accept = trial_objective <= objective+config['armijo']*alpha*slope
                trial_logs.append({'trial': trial, 'alpha': alpha, 'full_objective': trial_objective,
                    'accepted': accept, 'reduced_trial_objective': reduced_trial_objective,
                    'reduced_trial_status': reduced_trial_status})
                if accept:
                    accepted = True
                    break
                alpha *= config['backtracking']
            row = {'experiment_id': experiment_id, 'parent_object_id': problem.parent_id,
                'method': method, 'mode': mode, 'outer_iteration': outer, 'degree': degree if method!='FULL_GN' else None,
                'rank': info['rank'], 'model_refresh': True, 'core': info.get('core'), 'projection': info['projection'],
                'basis_info': info, 'lambda_total': lam, 'full_objective_before': objective,
                'full_KKT_relative_before': last_full_kkt, 'predicted_reduction': predicted,
                'actual_reduction': float(objective-trial_objective) if accepted else None,
                'step_size': alpha if accepted else 0., 'step_norm': float(la.norm(step)),
                'material_step_coefficients': step.tolist(),
                'accepted_material_coefficients': problem.chart.project(candidate-problem.init).tolist() if accepted else None,
                'QP': qp, 'trials': trial_logs, 'accepted': accepted, 'fallback_reason': fallback_reason,
                'wall_seconds': time.perf_counter()-it_start, 'cost': book.delta(snapshot)}
            iterations.append(row)
            if iteration_sink:
                iteration_sink(plain(row))
            last_info = info
            if not accepted:
                status, failure = 'LINE_SEARCH_FAILED', 'No full objective accepted trial'
                break
            previous = alpha*step
            # Preserve only Z,W; the new outer builds new LZ, core and B.
            predictor = projection
            x, state = candidate, trial_full_state
            if outer >= config['small_step_first_iteration'] and la.norm(previous)<config['small_step']:
                # A small step is a stagnation observation, never a full KKT certificate.
                audit_start = time.perf_counter()
                final_jac = FullJacobian(a, x, state)
                final_grad = final_jac.pullback(trial_full_r)+config['prior']*problem.chart.project(x-problem.init)
                final_audit = kkt(problem.chart, x, np.zeros(a.p), final_grad, tolerance=config['feasibility_tolerance'])
                last_full_kkt = final_audit['stationarity_norm']/initial_gradient
                audit_wall += time.perf_counter()-audit_start
                status = 'CONVERGED_FULL_KKT' if last_full_kkt<=config['common_full_kkt_rtol'] else 'STAGNATED_FULL_KKT_NOT_MET'
                break
    except QPFailure as exc:
        status, failure = 'QP_FAILED', {'message': str(exc), 'QP': getattr(exc, 'result', {})}
    # BudgetExceeded is handled by the job owner; preserve iteration JSONL first.
    objective, final_r, state = a.full_objective(x, config['prior'], state=state)
    audit_start = time.perf_counter()
    final_jac = FullJacobian(a, x, state)
    final_gradient = final_jac.pullback(final_r)+config['prior']*problem.chart.project(x-problem.init)
    final_kkt = kkt(problem.chart, x, np.zeros(a.p), final_gradient, tolerance=config['feasibility_tolerance'])
    last_full_kkt = final_kkt['stationarity_norm']/max(initial_gradient or 0., 1e-12)
    audit_wall += time.perf_counter()-audit_start
    book.synchronize()
    costs = book.delta(before)
    row = {'experiment_id': experiment_id, 'parent_object_id': problem.parent_id,
        'split': 'historically_exposed_feasibility', 'method': method, 'mode': mode,
        'parameterization': problem.chart.kind, 'n_current': a.n, 'p_material': a.p,
        'n_source': a.P, 'n_receiver': len(problem.receivers), 'complex_receiver_channels': a.m,
        'real_data_dimension': a.P*2*a.m, 'frequencies': [problem.frequency],
        'noise_seed': None, 'noise_level': 0., 'initial_state_id': 'shared_original_init',
        'degree_policy': 'fixed', 'degree': degree if method!='FULL_GN' else None,
        'seed_budget_O': config['seed_rank_O'] if method.startswith('OPM') else 0,
        'seed_budget_P': config['seed_rank_P'] if method.startswith('OPM') else 0,
        'seed_budget_M': config['seed_rank_M'] if method.startswith('OPM') else 0,
        'rank': last_info['rank'], 'final_full_objective': objective,
        'final_data_residual': float(la.norm(final_r)), 'final_KKT_residual': last_full_kkt,
        'final_feasibility_violation': a.material_constraints(x)['violation'],
        'accepted_updates': len([z for z in iterations if z['accepted']]), 'outer_iterations': len(iterations),
        'wall_total': time.perf_counter()-started, 'wall_setup': setup_wall, 'wall_audit': audit_wall,
        'cost': costs, 'peak_memory': book.receipt(), 'fallback_count': fallback_count,
        'status': status, 'failure': failure, 'solver': 'original direct complex128 LU; zero Krylov solver iterations'}
    row['native_DDA_counters'] = a.model.counters.as_dict()
    row.update(costs['counts'])
    return x, plain(row), iterations, a
