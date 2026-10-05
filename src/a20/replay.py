"""Frozen-state replay over the preserved Maxwell adapter.

Offline labels are opened only in the evaluation routines below. Builders get
only BasisView, never old steps, exact currents, full Jacobians, or truth.
Results are observations; this module does not decide the scientific gates.
"""
from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
import csv
import gc
import json
import time
import uuid

import numpy as np
from scipy import linalg as la

from .backend import Adapter, BasisView, ForbiddenAccess, load_problem, unpack
from .costs import BudgetExceeded, plain, write_json
from .material import QPFailure, kkt, solve_quadratic
from .opm import (FullJacobian, Hierarchy, Projection, ReducedJacobian,
                  SchurFeedback, SeedBundle, UnsafeCore, build_seeds, orth)


_RUNTIME_STATE_KEYS = {'chi', 'lambda_total', 'ell', 'iteration'}
_VECTOR_ACTIONS = ('F_actions', 'F_adjoint_actions', 'L_actions', 'L_adjoint_actions')


def _empty_cost():
    return {'counts': {}, 'exclusive_walls': {}, 'wall_seconds': 0.,
            'process_cpu_seconds': 0.}


def _sum_costs(*costs):
    result = _empty_cost()
    for cost in costs:
        if not cost:
            continue
        for name in ('counts', 'exclusive_walls'):
            for key, value in cost.get(name, {}).items():
                result[name][key] = result[name].get(key, 0) + value
        for name in ('wall_seconds', 'process_cpu_seconds'):
            result[name] += cost.get(name, 0.)
    return result


class _Segment(AbstractContextManager):
    """Capture one stage, including failed work, without overlapping stages."""
    def __init__(self, book, name, *, phase=None):
        self.book, self.name, self.phase = book, name, phase
        self.cost = _empty_cost()

    def __enter__(self):
        self.before = self.book.snapshot()
        self.book.synchronize()
        self.wall, self.cpu = time.perf_counter(), time.process_time()
        self.phase_scope = self.book.scope(self.phase) if self.phase is not None else None
        if self.phase_scope is not None:
            self.phase_scope.__enter__()
        self.span = self.book.span(self.name)
        try:
            self.span.__enter__()
        except BaseException:
            if self.phase_scope is not None:
                self.phase_scope.__exit__(None, None, None)
            raise
        return self

    def __exit__(self, kind, error, trace):
        try:
            return self.span.__exit__(kind, error, trace)
        finally:
            # CostBook.delta does not call check: budget exhaustion must not
            # erase the receipt for the work that exhausted the budget.
            self.cost = self.book.delta(self.before)
            self.cost.update(wall_seconds=time.perf_counter()-self.wall,
                             process_cpu_seconds=time.process_time()-self.cpu)
            if self.phase_scope is not None:
                self.phase_scope.__exit__(kind, error, trace)


def _csv_cell(value):
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(plain(value), separators=(',', ':'), allow_nan=False)
    return value


class _Sink:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.rows_path = self.directory/'replay.jsonl'
        self.fail_path = self.directory/'failures.jsonl'
        self.fail_path.touch(exist_ok=True)
        self.rows = []
        if self.rows_path.exists():
            for line in self.rows_path.read_text(encoding='utf-8').splitlines():
                if line.strip():
                    self.rows.append(json.loads(line))

    def _table(self, path, rows):
        preferred = ['run_id', 'row_id', 'record_kind', 'parent_object_id',
                     'iteration', 'method', 'degree', 'rank', 'status']
        keys = set().union(*(set(row) for row in rows)) if rows else set()
        fields = [key for key in preferred if key in keys] + sorted(keys-set(preferred))
        temporary = path.with_suffix(path.suffix+'.tmp')
        with temporary.open('w', newline='', encoding='utf-8') as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows({key: _csv_cell(value) for key, value in row.items()}
                             for row in rows)
        temporary.replace(path)

    def append(self, row):
        row = plain(row)
        with self.rows_path.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(row, allow_nan=False)+'\n')
        self.rows.append(row)

    def export_tables(self):
        # JSONL is the per-row checkpoint. Export each CSV only once in the
        # epilogue; repeated whole-table rewrites consume the physics budget.
        self._table(self.directory/'REPLAY_RESULTS.csv', self.rows)
        counts = []
        for item in self.rows:
            costs = item.get('costs', {})
            total = item.get('counts', {})
            counts.append({key: item.get(key) for key in
                           ('run_id', 'row_id', 'record_kind', 'parent_object_id',
                            'iteration', 'method', 'degree', 'rank', 'status')} |
                          total | {'costs': costs,
                                   'basis_Maxwell_vector_actions': item.get('basis_Maxwell_vector_actions'),
                                   'online_Maxwell_vector_actions': item.get('online_Maxwell_vector_actions')})
        self._table(self.directory/'ACTION_COUNTS.csv', counts)

    def failure(self, row, error, *, step=None, details=None):
        failure = {key: row.get(key) for key in
                   ('run_id', 'row_id', 'parent_object_id', 'iteration', 'method', 'degree')}
        failure.update(error=type(error).__name__+': '+str(error), details=details)
        if step is not None:
            failure['step_path'] = self.save_step(row, step, failed=True)
        with self.fail_path.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(plain(failure), allow_nan=False)+'\n')
        return failure

    def save_step(self, row, step, *, failed=False):
        directory = self.directory/('failed_steps' if failed else 'steps')
        directory.mkdir(exist_ok=True)
        path = directory/(row['row_id']+'.npz')
        np.savez_compressed(path, step=np.asarray(step, dtype=np.float64))
        return str(path)


def _parents(root, config, requested):
    manifest = json.loads((root/'configs/parents.json').read_text(encoding='utf-8'))
    records = {int(row['parent_id']): row for row in manifest['parents']}
    chosen = config['parents'] if requested is None else requested
    chosen = [int(row['parent_id']) if isinstance(row, dict) else int(row) for row in chosen]
    if any(parent not in config['parents'] or parent not in records for parent in chosen):
        raise ValueError('Parent selection lies outside the frozen manifest')
    if len(chosen) != len(set(chosen)):
        raise ValueError('Duplicate parents are not independent replay objects')
    return [records[parent] for parent in chosen]


def _load_state(root, parent, iteration, chart):
    record = next((s for s in parent['states'] if int(s['iteration']) == iteration), None)
    if record is None:
        raise FileNotFoundError('No registered runtime state for iteration '+str(iteration))
    with np.load(root/record['runtime_path'], allow_pickle=False) as data:
        if set(data.files) != _RUNTIME_STATE_KEYS:
            raise ForbiddenAccess('UNREGISTERED_OR_OFFLINE_RUNTIME_STATE_KEYS')
        x = np.asarray(data['chi'], dtype=np.complex128).copy()
        ell = data['ell'].copy()
        lam, saved_iteration = float(data['lambda_total']), int(data['iteration'])
    if x.shape != (chart.n,) or ell.shape != (chart.d,) or np.iscomplexobj(ell):
        raise ValueError('Runtime state/material chart shape or real-coordinate mismatch')
    if saved_iteration != iteration or lam <= 0 or not np.all(np.isfinite(x)) or not np.all(np.isfinite(ell)):
        raise ValueError('Invalid frozen runtime state')
    return x, lam, np.asarray(ell, dtype=np.float64)


def _base_row(run_id, parent, iteration, config, book, method, degree=None):
    parent_id = int(parent['parent_id'])
    book.metadata.update(run_id=run_id, parent_object_id=parent_id,
                         iteration=iteration, method=method, degree=degree)
    return {'run_id': run_id, 'row_id': f'{run_id}_{parent_id}_{iteration}_{method}_{degree}',
            'experiment_id': book.metadata.get('experiment_id', run_id),
            'record_kind': 'method', 'parent_object_id': parent_id,
            'iteration': iteration, 'method': method, 'degree': degree,
            'parameterization': parent['parameterization'],
            'split': parent.get('split', config.get('dataset_exposure')),
            'backend_commit': book.metadata.get('source_commit',
                                  config.get('backend_commit', book.metadata.get('backend_commit'))),
            'backend_declared_historical_commit': book.metadata.get('backend_declared_historical_commit'),
            'backend_provenance_file': 'vendor/a17/UPSTREAM_PROVENANCE.json',
            'precision': 'complex128/float64', 'n_current': parent['n_current'],
            'p_material': parent['p_material'], 'n_source': parent['sources'],
            'n_receiver': parent['receivers'], 'frequencies': parent['frequencies'],
            'truth_used_in_seed': False, 'previous_reference_step_used_in_seed': False,
            'probe_diagnostics_are_certificate': False,
            'relative_H_step_error': None, 'full_quadratic_gap': None,
            'reference_status': None, 'failure_reason': None,
            'truth_one_step_error': None, 'rank': None, 'status': 'PENDING', 'fail': None,
            'actual_seed_ranks': None, 'actual_joint_seed_rank': None,
            'orthogonality_error': None, 'core_stability': None,
            'primal_probe_relative_residual': None, 'dual_probe_relative_residual': None,
            'fullfallback_used': False, 'fallback_count': 0}


def _cost_fields(row, **costs):
    row['costs'] = costs
    total = _sum_costs(*costs.values())
    row['counts'] = total['counts']
    row['wall_total_attributed'] = total['wall_seconds']
    for name, cost in costs.items():
        row['wall_'+name] = cost['wall_seconds']
    for name in _VECTOR_ACTIONS:
        row[name] = total['counts'].get(name, 0)
    basis = costs.get('basis', _empty_cost())
    online = _sum_costs(*(cost for name, cost in costs.items() if name != 'audit'))
    row['basis_Maxwell_vector_actions'] = sum(basis['counts'].get(k, 0) for k in _VECTOR_ACTIONS)
    row['online_Maxwell_vector_actions'] = sum(online['counts'].get(k, 0) for k in _VECTOR_ACTIONS)
    row['fair_action_metric'] = 'actual vector RHS of F, F*, L, L*; no artificial padding'
    row['shared_state_and_reference_costs_included'] = False
    row['basis_time_scope'] = 'this hierarchy seed construction and extension only; no other degree QP'


@dataclass
class _Reference:
    step: np.ndarray | None
    jstep: np.ndarray | None
    quadratic: float | None
    energy: float | None
    gradient0: np.ndarray
    record: dict


def _relative(value, reference):
    return float(la.norm(value)/max(float(la.norm(reference)), 1e-300))


def _evaluate_saved_reference(path, iteration, chart, x, residual, jac, lam, ell, config, gradient0):
    """Offline evaluation only: check old coordinate packing and stationarity."""
    record = {'saved_status': 'MISSING', 'saved_usable_as_constrained_reference': False}
    try:
        with np.load(path, allow_pickle=False) as data:
            step = data['step_'+str(iteration)].copy()
            physical = data['physical_step_'+str(iteration)].copy()
            old_gradient = data['gradient_'+str(iteration)].copy()
            old_reported = float(data['old_relative_residual_'+str(iteration)])
    except (OSError, KeyError, ValueError) as error:
        record['saved_error'] = type(error).__name__+': '+str(error)
        return None, record
    if (step.shape != (chart.d,) or np.iscomplexobj(step) or
            physical.shape != x.shape or old_gradient.shape != step.shape or
            not np.all(np.isfinite(step)) or not np.all(np.isfinite(physical))):
        record['saved_status'] = 'INVALID_COORDINATES'
        return None, record
    step = np.asarray(step, dtype=np.float64)
    expansion_error = _relative(chart.expand(step)-physical, physical)
    jstep = jac.action(step)
    gradient = jac.pullback(residual+jstep)+lam*step+ell
    audit = kkt(chart, x, step, gradient, tolerance=config['feasibility_tolerance'])
    stationarity = float(la.norm(gradient)/max(float(la.norm(gradient0)), 1e-300))
    constrained_stationarity = audit['stationarity_norm']/max(float(la.norm(gradient0)), 1e-300)
    feasible = audit['violation'] <= config['feasibility_tolerance']
    packing_ok = expansion_error < 1e-9
    usable = feasible and packing_ok and constrained_stationarity <= config['qp_kkt_rtol']
    record.update(saved_physical_expansion_relative_error=expansion_error,
                  saved_physical_coordinates_verified=packing_ok,
                  saved_gradient_relative_error=_relative(old_gradient-gradient0, gradient0),
                  saved_reported_unconstrained_residual=old_reported,
                  saved_unconstrained_stationarity_relative=stationarity,
                  saved_constrained_stationarity_relative=constrained_stationarity,
                  saved_feasibility_violation=audit['violation'], saved_feasible=feasible,
                  saved_active_constraints=audit['active_constraints'],
                  saved_usable_as_constrained_reference=usable,
                  saved_status=('VERIFIED_CONSTRAINED_REFERENCE' if usable else
                                'UNCONSTRAINED_REFERENCE_ONLY' if not feasible else
                                'FEASIBLE_BUT_UNVERIFIED_REFERENCE'))
    return step, record


def _evaluate_reference(path, iteration, adapter, x, residual, jac, lam, ell, config, sink, row):
    """Reuse an audited feasible old step, or pay for the common constrained QP."""
    gradient0 = jac.pullback(residual)+ell
    saved, record = _evaluate_saved_reference(path, iteration, adapter.chart, x,
                                              residual, jac, lam, ell, config, gradient0)
    record['reference_stationarity_denominator'] = float(la.norm(gradient0))
    step = saved if record['saved_usable_as_constrained_reference'] else None
    if step is None:
        record['reference_source'] = 'new_paid_common_constrained_quadratic'
        try:
            step, solution, _ = solve_quadratic(adapter.chart, x, residual, jac,
                                               lam, ell, config, adapter.book)
            record['reference_QP'] = solution
            record['reference_status'] = 'VERIFIED_NEW_CONSTRAINED_REFERENCE'
        except QPFailure as error:
            record.update(reference_status='MISSING_CONSTRAINED_REFERENCE', reference_QP=error.result)
            record['failure'] = sink.failure(row, error, step=error.step, details=error.result)
            record['reference_failure_reason'] = record['failure']['error']
        except Exception as error:
            if isinstance(error, BudgetExceeded):
                raise
            record['reference_status'] = 'MISSING_CONSTRAINED_REFERENCE'
            record['failure'] = sink.failure(row, error)
            record['reference_failure_reason'] = record['failure']['error']
    else:
        record.update(reference_source='audited_saved_step', reference_status='VERIFIED_SAVED_CONSTRAINED_REFERENCE')
    if saved is not None:
        record['saved_step_path'] = sink.save_step(dict(row, row_id=row['row_id']+'_historical'), saved)
    if step is None:
        return _Reference(None, None, None, None, gradient0, record)
    js = jac.action(step)
    quadratic = float(.5*(residual+js)@(residual+js)+ell@step+.5*lam*step@step)
    energy = float(js@js+lam*step@step)
    record['reference_step_path'] = sink.save_step(row, step)
    return _Reference(step, js, quadratic, energy, gradient0, record)


def _evaluate_truth_step(path, chart, x, step, config):
    """Truth is an offline material metric, never a basis-construction input."""
    try:
        with np.load(path, allow_pickle=False) as data:
            truth = data['truth'].copy()
    except (OSError, KeyError, ValueError) as error:
        return {'truth_metric_status': 'NOT_AVAILABLE', 'truth_metric_error': str(error),
                'truth_one_step_error': None}
    if truth.shape != x.shape or not np.all(np.isfinite(truth)):
        return {'truth_metric_status': 'INVALID_LABEL', 'truth_one_step_error': None}
    candidate = x+chart.expand(step)
    denominator = max(float(la.norm(truth)), 1e-300)
    imaginary_floor = config['imaginary_denominator_floor_fraction']*denominator
    return {'truth_metric_status': 'OFFLINE_EVALUATION_ONLY',
            'truth_one_step_error': float(la.norm(candidate-truth)/denominator),
            'truth_before_error': float(la.norm(x-truth)/denominator),
            'truth_one_step_absolute_L2': float(np.sqrt(chart.volume)*la.norm(candidate-truth)),
            'truth_one_step_real_error': float(la.norm(candidate.real-truth.real)/max(float(la.norm(truth.real)), 1e-300)),
            'truth_one_step_imag_error': float(la.norm(candidate.imag-truth.imag)/max(float(la.norm(truth.imag)), imaginary_floor, 1e-300)),
            'truth_one_step_imag_absolute_L2': float(np.sqrt(chart.volume)*la.norm(candidate.imag-truth.imag)),
            'truth_imaginary_denominator_floor': imaginary_floor,
            'truth_metric_scope': 'mass-weighted full physical material; one step, not nonlinear acceptance'}


def _evaluate_full_step(adapter, x, residual, jac, lam, ell, step, reference, config):
    js = jac.action(step)
    gradient = jac.pullback(residual+js)+lam*step+ell
    audit = kkt(adapter.chart, x, step, gradient, tolerance=config['feasibility_tolerance'])
    defect = audit['defect']
    result = {'full_stationarity_defect_norm': float(la.norm(gradient)),
              'full_KKT_defect_norm': audit['stationarity_norm'],
              'full_KKT_relative': audit['stationarity_norm']/max(float(la.norm(reference.gradient0)), 1e-300),
              'full_feasibility_violation': audit['violation'],
              'full_complementarity': audit['complementarity'],
              'KKT_bound_H_error': float(la.norm(defect)/np.sqrt(lam)),
              'KKT_bound_quadratic_gap': float(defect@defect/(2*lam)),
              'reference_status': reference.record['reference_status'],
              'relative_H_step_error': None, 'absolute_H_step_error': None,
              'full_quadratic_gap': None,
              'H_error_scope': 'common full quadratic in physical-L2 real material coordinates'}
    if reference.step is not None:
        delta = step-reference.step
        dj = js-reference.jstep
        energy = max(0., float(dj@dj+lam*delta@delta))
        result.update(absolute_H_step_error=float(np.sqrt(energy)),
                      reference_H_energy=reference.energy, half_H_error_energy=.5*energy,
                      full_quadratic_gap=float(.5*(residual+js)@(residual+js)+ell@step+.5*lam*step@step-reference.quadratic),
                      constrained_quadratic_identity='gap is measured directly; not equated to half H error')
        if reference.energy > config['replay_H_relative_floor']**2:
            result['relative_H_step_error'] = float(np.sqrt(energy/reference.energy))
        else:
            result['relative_H_status'] = 'REFERENCE_ENERGY_BELOW_FROZEN_FLOOR'
    else:
        result['relative_H_status'] = 'MISSING_CONSTRAINED_REFERENCE; no fabricated denominator'
    return result


def _seed_bank(view, schur, config, budgets):
    """Reuse the registered seed recipe; zero-budget channels do no actions."""
    if view.previous is not None:
        raise ForbiddenAccess('Frozen replay cannot use an offline previous step as a seed')
    return build_seeds(view, schur, config, budgets=budgets)


def _independent_krylov_seed(view, schur, config, iteration, rank):
    seed = [int(config['master_seed']), int(view._a.problem.parent_id), iteration, 431]
    rng = np.random.default_rng(np.random.SeedSequence(seed))
    raw = rng.normal(size=(view.n, rank))+1j*rng.normal(size=(view.n, rank))
    raw = schur.project(raw)
    with view.book.span('independent_current_probe_compression', independent_current_probe_columns=rank):
        q, record = orth(raw, against=schur.U, rank=rank, rtol=config['orthogonal_rank_rtol'])
    record.update(requested_rank=rank,
                  provenance='independent complex current probes; ordinary right block Krylov of Schur F',
                  no_truth_or_reference_step=True)
    return SeedBundle({'R': q}, {'R': record}, seed, np.empty((view.chart.d, 0)),
                      np.empty((view.P*2*view.m, 0)))


def _retained(view, config):
    U, rec = orth(view.receiver(config['retained_rank']), rank=config['retained_rank'],
                  rtol=config['orthogonal_rank_rtol'])
    failure = None
    try:
        schur = SchurFeedback(view, U, config)
    except UnsafeCore as error:
        failure = str(error)
        view.book.counts['empty_U_fallbacks'] += 1
        schur = SchurFeedback(view, np.empty((view.n, 0), dtype=np.complex128), config)
    return schur, {'requested_retained_rank': config['retained_rank'],
                   'actual_retained_rank': schur.U.shape[1], 'retained_deflation': rec,
                   'retained_core_stability': schur.stability,
                   'retained_fallback': 'empty_U' if failure else None,
                   'retained_fallback_reason': failure}


def _probe_diagnostics(adapter, x, state, projection, config, iteration):
    seed = [int(config['master_seed']), int(adapter.problem.parent_id), iteration, 809]
    rng = np.random.default_rng(np.random.SeedSequence(seed))
    material = rng.normal(size=(adapter.p, 2))
    material /= np.maximum(la.norm(material, axis=0), 1e-300)
    data = rng.normal(size=(adapter.P*2*adapter.m, 2))
    data /= np.maximum(la.norm(data, axis=0), 1e-300)
    primal_rhs = adapter.apply_B(x, state, material).transpose(1, 0, 2).reshape(adapter.n, -1)
    primal = primal_rhs-adapter.apply_L(x, projection.apply(primal_rhs))
    source_data = unpack(adapter.whiten(data, adjoint=True), adapter.P, adapter.m)
    dual_rhs = adapter.apply_S_adjoint(source_data.transpose(1, 0, 2).reshape(adapter.m, -1))
    dual = dual_rhs-adapter.apply_L_adjoint(x, projection.adjoint(dual_rhs))
    return {'primal_probe_relative_residual': _relative(primal, primal_rhs),
            'dual_probe_relative_residual': _relative(dual, dual_rhs),
            'primal_probe_column_residuals': (la.norm(primal, axis=0)/np.maximum(la.norm(primal_rhs, axis=0), 1e-300)).tolist(),
            'dual_probe_column_residuals': (la.norm(dual, axis=0)/np.maximum(la.norm(dual_rhs, axis=0), 1e-300)).tolist(),
            'diagnostic_probe_rng': seed, 'diagnostic_material_probes': 2,
            'diagnostic_measurement_probes': 2,
            'probe_diagnostics_scope': 'sampled full-L primal/dual residuals; not an operator norm or stopping certificate',
            'probe_diagnostics_are_certificate': False}


def _model_row(sink, row, adapter, x, state, residual, full_jac, reference, lam, ell,
               config, Z, basis_record, basis_cost, labels, retained_record):
    row.update(basis_record | retained_record, rank=Z.shape[1],
               reference_status=reference.record['reference_status'],
               reference_failure_reason=reference.record.get('reference_failure_reason'),
               fallback_count=int(retained_record.get('retained_fallback') is not None))
    projection_cost, qp_cost, audit_cost = _empty_cost(), _empty_cost(), _empty_cost()
    step, projection = None, None
    stage = 'projection'
    segment = _Segment(adapter.book, 'replay_projection')
    try:
        with segment:
            projection = Projection(adapter, x, Z, config)
        projection_cost = segment.cost
        row.update(core_stability=projection.stability,
                   Galerkin_core_stability=projection.galerkin_stability,
                   projection_kind=projection.kind, projection_fallback=projection.fallback)
        row['fallback_count'] += int(projection.fallback is not None)
        stage = 'QP'
        segment = _Segment(adapter.book, 'replay_material_QP')
        with segment:
            reduced = ReducedJacobian(adapter, x, state, projection)
            step, solution, _ = solve_quadratic(adapter.chart, x, residual, reduced,
                                               lam, ell, config, adapter.book)
        qp_cost = segment.cost
        row['QP'] = solution
        row['step_path'] = sink.save_step(row, step)
        stage = 'audit'
        segment = _Segment(adapter.book, 'replay_full_audit', phase='offline_audit')
        with segment:
            row.update(_evaluate_full_step(adapter, x, residual, full_jac, lam, ell,
                                           step, reference, config))
            row.update(_probe_diagnostics(adapter, x, state, projection, config, row['iteration']))
            row.update(_evaluate_truth_step(labels, adapter.chart, x, step, config))
        audit_cost = segment.cost
        row['status'] = ('OK' if reference.step is not None else 'OK_WITHOUT_CONSTRAINED_REFERENCE')
        if reference.step is None:
            row['failure_reason'] = reference.record.get('reference_failure_reason', 'MISSING_CONSTRAINED_REFERENCE')
        if row.get('truth_metric_status') != 'OFFLINE_EVALUATION_ONLY':
            row['status'] += '_TRUTH_UNAVAILABLE'
    except Exception as error:
        # The current segment receipt remains available even when it failed.
        if stage == 'projection':
            projection_cost = segment.cost
        elif stage == 'QP':
            qp_cost = segment.cost
        else:
            audit_cost = segment.cost
        if isinstance(error, QPFailure):
            step = error.step
            row['QP'] = error.result
        failure = sink.failure(row, error, step=step,
                               details=getattr(error, 'result', None))
        row.update(status='BUDGET_STOP' if isinstance(error, BudgetExceeded) else 'FAILED',
                   fail=failure['error'], failure_reason=failure['error'], failure=failure)
        if isinstance(error, UnsafeCore):
            row['full_fallback_required'] = True
            row['fallback_executed'] = False
            row['fallback_reason'] = 'unsafe Galerkin and declared frozen-test Petrov projection'
            row['requested_reduced_rank'] = Z.shape[1]
            row['representation_eligible'] = False
            if 'full' in config.get('fallbacks', []):
                fallback_cost, fallback_audit_cost = _empty_cost(), _empty_cost()
                fallback_segment = _Segment(adapter.book, 'replay_paid_full_fallback', phase='online_full_fallback')
                try:
                    with fallback_segment:
                        # Acquire a fresh paid full J; an offline reference
                        # step/J is never substituted for deployment fallback.
                        fallback_jac = FullJacobian(adapter, x, state)
                        fallback_jac.small_matrix()
                        fallback_step, fallback_qp, _ = solve_quadratic(
                            adapter.chart, x, residual, fallback_jac, lam, ell,
                            config, adapter.book)
                    fallback_cost = fallback_segment.cost
                    row.update(fullfallback_used=True, fallback_executed=True,
                               fallback_status='OK', rank=adapter.n,
                               fallback_QP=fallback_qp,
                               fallback_step_path=sink.save_step(dict(row, row_id=row['row_id']+'_fullfallback'), fallback_step))
                    row['fallback_count'] += 1
                    fallback_segment = _Segment(adapter.book, 'replay_full_fallback_audit', phase='offline_audit')
                    with fallback_segment:
                        row.update(_evaluate_full_step(adapter, x, residual, full_jac,
                                                       lam, ell, fallback_step, reference, config))
                        row.update(_evaluate_truth_step(labels, adapter.chart, x, fallback_step, config))
                    fallback_audit_cost = fallback_segment.cost
                    row['fallback_reporting_scope'] = 'full result retained; reduced representation FAILED even at zero H error'
                except Exception as fallback_error:
                    if row.get('fallback_executed'):
                        fallback_audit_cost = fallback_segment.cost
                    else:
                        fallback_cost = fallback_segment.cost
                    fallback_failure = sink.failure(dict(row, row_id=row['row_id']+'_fullfallback'),
                                                    fallback_error,
                                                    step=getattr(fallback_error, 'step', None),
                                                    details=getattr(fallback_error, 'result', None))
                    row.update(fallback_status='FAILED', fallback_failure=fallback_failure,
                               fullfallback_used=False if not row.get('fallback_executed') else True)
                    if isinstance(fallback_error, BudgetExceeded):
                        row['status'] = 'BUDGET_STOP'
                _cost_fields(row, basis=basis_cost, projection=projection_cost, QP=qp_cost,
                             fallback=fallback_cost, audit=_sum_costs(audit_cost, fallback_audit_cost))
                sink.append(row)
                if row['status'] == 'BUDGET_STOP':
                    raise BudgetExceeded(row.get('fallback_failure', {}).get('error', 'FULL_FALLBACK_BUDGET_STOP'))
                return row
        _cost_fields(row, basis=basis_cost, projection=projection_cost, QP=qp_cost, audit=audit_cost)
        sink.append(row)
        if isinstance(error, BudgetExceeded):
            raise
        return row
    _cost_fields(row, basis=basis_cost, projection=projection_cost, QP=qp_cost, audit=audit_cost)
    sink.append(row)
    return row


class _RankControl:
    def __init__(self, view, config, *, seed=None):
        self.view, self.config, self.seed = view, config, seed
        self.rng = None if seed is None else np.random.default_rng(np.random.SeedSequence(seed))
        self.Z = np.empty((view.n, 0), dtype=np.complex128)
        self.records = []

    def at_rank(self, requested):
        if requested < self.Z.shape[1]:
            raise ValueError('Rank controls must follow the nested main ranks')
        extra = requested-self.Z.shape[1]
        if extra:
            if self.rng is None:
                raw = self.view.receiver(requested)[:, self.Z.shape[1]:]
            else:
                raw = self.rng.normal(size=(self.view.n, extra))+1j*self.rng.normal(size=(self.view.n, extra))
                self.view.book.counts['random_current_probe_columns'] += extra
            with self.view.book.span('rank_control_orthogonalization'):
                added, record = orth(raw, against=self.Z, rank=extra,
                                     rtol=self.config['orthogonal_rank_rtol'])
            self.Z = np.column_stack((self.Z, added))
            self.records.append(record)
        return self.Z.copy(), {'target_rank_from_main': requested,
                                'rank_matches_main': self.Z.shape[1] == requested,
                                'rank_control_deflation': self.records.copy(),
                                'seed_provenance': 'receiver geometry SVD' if self.rng is None else 'fixed independent random current subspace',
                                'seed_rng': self.seed,
                                'orthogonality_error': float(la.norm(self.Z.conj().T@self.Z-np.eye(self.Z.shape[1])))}


def _frontier_records(rows):
    """Only existing equal-rank/equal-vector-action points may be paired."""
    observations = [row for row in rows if row.get('record_kind') == 'method'
                    and row.get('status', '').startswith('OK')
                    and row.get('relative_H_step_error') is not None]
    matches = []
    for index, left in enumerate(observations):
        for right in observations[index+1:]:
            if (left['parent_object_id'], left['iteration']) != (right['parent_object_id'], right['iteration']):
                continue
            if left['method'] == right['method']:
                continue
            rank_equal = left['rank'] == right['rank']
            action_equal = left['online_Maxwell_vector_actions'] == right['online_Maxwell_vector_actions']
            if rank_equal or action_equal:
                matches.append({'left_row_id': left['row_id'], 'right_row_id': right['row_id'],
                                'parent_object_id': left['parent_object_id'], 'iteration': left['iteration'],
                                'actual_rank_matched': rank_equal, 'actual_vector_actions_matched': action_equal,
                                'left_rank': left['rank'], 'right_rank': right['rank'],
                                'left_actions': left['online_Maxwell_vector_actions'],
                                'right_actions': right['online_Maxwell_vector_actions'],
                                'left_H_error': left['relative_H_step_error'],
                                'right_H_error': right['relative_H_step_error'],
                                'comparison_scope': 'observed point only; no padded or inferred matched point'})
    frontier = []
    for row in observations:
        peers = [other for other in observations
                 if (other['parent_object_id'], other['iteration']) == (row['parent_object_id'], row['iteration'])]
        for axis in ('rank', 'online_Maxwell_vector_actions'):
            dominated = any(other[axis] <= row[axis]
                            and other['relative_H_step_error'] <= row['relative_H_step_error']
                            and (other[axis] < row[axis] or other['relative_H_step_error'] < row['relative_H_step_error'])
                            for other in peers)
            frontier.append({'row_id': row['row_id'], 'parent_object_id': row['parent_object_id'],
                             'iteration': row['iteration'], 'axis': axis, 'actual_cost': row[axis],
                             'relative_H_step_error': row['relative_H_step_error'],
                             'nondominated_observation': not dominated})
    return {'matches': matches, 'observed_frontiers': frontier,
            'padding_actions': 0, 'matched_rank_is_never_assumed': True,
            'shared_state_reference_and_retained_setup_are_separate': True,
            'action_metric_limit': 'F/L vector counts do not replace inclusive wall time or full solve RHS'}


def run_replay(root, config, book, device, parents=None, iterations=None):
    """Run the registered two-state pilot, or an explicit frozen subset.

    All physics is paid to the supplied CostBook. The caller owns budget,
    locking, hardware choice, G0 authorization, scientific gates, and release.
    """
    root = Path(root).resolve()
    selected = _parents(root, config, parents)
    degrees = list(config['replay_degrees'])
    selected_iterations = list(config['replay_iterations'] if iterations is None else iterations)
    if any(i not in config['replay_iterations'] for i in selected_iterations):
        raise ValueError('Replay iteration outside frozen selection')
    if degrees != sorted(set(degrees)) or any(d < 0 or d > 5 for d in degrees):
        raise ValueError('Replay degrees must be increasing frozen degrees in 0..5')
    run_id = time.strftime('%Y%m%dT%H%M%S', time.gmtime())+'_'+uuid.uuid4().hex[:8]
    sink = _Sink(root/'results/replay')
    start_row = len(sink.rows)
    stopped, scene_records = None, []
    try:
        for parent in selected:
            setup_row = _base_row(run_id, parent, None, config, book, 'shared_geometry')
            with _Segment(book, 'replay_object_geometry_setup') as segment:
                problem = load_problem(root/parent['runtime_problem'])
                adapter = Adapter(problem, device=device, book=book)
            setup_row.update(record_kind='shared_setup', status='OK')
            _cost_fields(setup_row, geometry=segment.cost)
            sink.append(setup_row)
            for iteration in selected_iterations:
                print(f'REPLAY parent={parent["parent_id"]} iteration={iteration}', flush=True)
                x, lam, ell = _load_state(root, parent, iteration, adapter.chart)
                labels = root/parent['offline_labels']
                shared_row = _base_row(run_id, parent, iteration, config, book, 'shared_full_state')
                with _Segment(book, 'replay_cached_full_state_and_residual') as segment:
                    state = adapter.full_state(x, reuse=True)
                    residual = adapter.residual(state)
                    full_jac = FullJacobian(adapter, x, state)
                    # Full Gaussian J is acquired exactly once and paid here.
                    # Full voxel J/H are never formed.
                    with book.scope('offline_reference'):
                        full_jac.small_matrix()
                shared_row.update(record_kind='shared_state', status='OK',
                                  full_state_residual=None,
                                  full_state_backward_residual_verified_below=1e-9,
                                  full_state_residual_scope='Adapter.full_state checks once; backward action is not repeated for reporting',
                                  data_residual_norm=float(la.norm(residual)), lambda_total=lam,
                                  full_J_cached=adapter.p <= 128, full_voxel_J_or_H_formed=False)
                _cost_fields(shared_row, full_state=segment.cost)
                sink.append(shared_row)
                ref_row = _base_row(run_id, parent, iteration, config, book, 'full_GN_reference')
                with _Segment(book, 'replay_reference_evaluation_and_generation', phase='offline_reference') as segment:
                    reference = _evaluate_reference(labels, iteration, adapter, x, residual,
                                                     full_jac, lam, ell, config, sink, ref_row)
                    if reference.step is not None:
                        ref_row.update(_evaluate_truth_step(labels, adapter.chart, x, reference.step, config))
                ref_row.update(reference.record, record_kind='shared_reference', rank=adapter.n,
                               status='OK' if reference.step is not None else 'FAILED',
                               fail=reference.record.get('reference_failure_reason'),
                               failure_reason=reference.record.get('reference_failure_reason'),
                               reference_H_energy=reference.energy, full_quadratic_value=reference.quadratic)
                _cost_fields(ref_row, reference=segment.cost)
                sink.append(ref_row)
                view = BasisView(adapter, x, state, residual, previous=None)
                retained_row = _base_row(run_id, parent, iteration, config, book, 'shared_retained_receiver_U')
                with _Segment(book, 'replay_retained_Schur_setup') as segment:
                    schur, retained_record = _retained(view, config)
                retained_row.update(retained_record, record_kind='shared_retained', status='OK',
                                    rank=schur.U.shape[1])
                _cost_fields(retained_row, retained=segment.cost)
                sink.append(retained_row)
                main_budget = {name: int(config['seed_rank_'+name]) for name in 'OPM'}
                definitions = [('mixed', main_budget, 'OPM', False),
                               ('O_total4', {'O': 4, 'P': 0, 'M': 0}, 'O', False),
                               ('P_total4', {'O': 0, 'P': 4, 'M': 0}, 'P', False),
                               ('M_total4', {'O': 0, 'P': 0, 'M': 4}, 'M', False),
                               ('OM_total4', {'O': 2, 'P': 0, 'M': 2}, 'OM', False),
                               ('OPM_total4', {'O': 2, 'P': 1, 'M': 1}, 'OPM', False),
                               ('OPM_forward_total12', main_budget, 'OPM', True),
                               ('ordinary_right_block_Krylov12', None, 'R', True)]
                main_ranks = []
                for method, budgets, families, forward_only in definitions:
                    print(f'REPLAY method={method}', flush=True)
                    basis_cost = _empty_cost()
                    first_degree = degrees[0]
                    initial_row = _base_row(run_id, parent, iteration, config, book, method, first_degree)
                    completed_degrees = set()
                    failed_basis_cost = _empty_cost()
                    try:
                        segment = _Segment(book, 'replay_hierarchy_seed')
                        with segment:
                            seeds = (_independent_krylov_seed(view, schur, config, iteration, sum(main_budget.values()))
                                     if budgets is None else _seed_bank(view, schur, config, budgets))
                            hierarchy = Hierarchy(view, schur, seeds, config, families=families,
                                                  forward_only=forward_only)
                        basis_cost = _sum_costs(basis_cost, segment.cost)
                        for degree in degrees:
                            row = _base_row(run_id, parent, iteration, config, book, method, degree)
                            segment = _Segment(book, 'replay_hierarchy_extend')
                            with segment:
                                Z, basis_record = hierarchy.at_degree(degree)
                            basis_cost = _sum_costs(basis_cost, segment.cost)
                            basis_record.update(seed_budgets=budgets or {'independent_current': sum(main_budget.values())},
                                                actual_seed_ranks={key: value.shape[1] for key, value in seeds.blocks.items()},
                                                actual_joint_seed_rank=sum(rec['rank'] for rec in hierarchy.joint_records[:1]),
                                                seed_records=seeds.records, seed_rng=seeds.rng_seed,
                                                forward_only=forward_only,
                                                independent_native_streams=True)
                            if method == 'mixed':
                                main_ranks.append((degree, Z.shape[1]))
                            _model_row(sink, row, adapter, x, state, residual, full_jac,
                                       reference, lam, ell, config, Z, basis_record,
                                       basis_cost, labels, retained_record)
                            completed_degrees.add(degree)
                    except BudgetExceeded:
                        raise
                    except Exception as error:
                        failure = sink.failure(initial_row, error)
                        failed_basis_cost = _sum_costs(basis_cost, segment.cost)
                        for missing_degree in degrees:
                            if missing_degree in completed_degrees:
                                continue
                            failed_row = _base_row(run_id, parent, iteration, config, book, method, missing_degree)
                            failed_row.update(status='FAILED', fail=failure['error'],
                                              failure_reason=failure['error'], failure=failure,
                                              reference_status=reference.record['reference_status'],
                                              hierarchy_failure_prevented_model=True,
                                              seed_budgets=budgets or {'independent_current': sum(main_budget.values())})
                            _cost_fields(failed_row, basis=failed_basis_cost)
                            sink.append(failed_row)
                controls = [('receiver_SOM_rank_control', None)]
                controls += [('random_current_rank_control_'+str(seed),
                              [int(seed), int(parent['parent_id']), iteration, 613])
                             for seed in config['random_control_seeds']]
                for method, seed in controls:
                    control = _RankControl(view, config, seed=seed)
                    basis_cost = _empty_cost()
                    for degree, target_rank in main_ranks:
                        row = _base_row(run_id, parent, iteration, config, book, method, degree)
                        with _Segment(book, 'replay_rank_control_extend') as segment:
                            Z, basis_record = control.at_rank(target_rank)
                        basis_cost = _sum_costs(basis_cost, segment.cost)
                        basis_record.update(seed_budgets={'current_rank': target_rank},
                                            actual_seed_ranks={'current': Z.shape[1]},
                                            actual_joint_seed_rank=Z.shape[1],
                                            main_degree_for_rank_target=degree)
                        _model_row(sink, row, adapter, x, state, residual, full_jac,
                                   reference, lam, ell, config, Z, basis_record,
                                   basis_cost, labels, retained_record)
                for method, reason in [('current_POD', 'No registered object-disjoint current snapshots with acquisition costs'),
                                       ('strong_derivative_goal_aware_ROM', 'No frozen compliant non-oracle construction inputs or acquisition-cost contract')]:
                    row = _base_row(run_id, parent, iteration, config, book, method)
                    row.update(status='NOT_RUN', fail=reason, failure_reason=reason, input_contract_missing=True)
                    _cost_fields(row)
                    sink.append(row)
                scene_records.append({'parent_object_id': parent['parent_id'], 'iteration': iteration,
                                      'reference_status': reference.record['reference_status'],
                                      'main_actual_ranks': main_ranks})
                del view, state, full_jac, reference, schur
            del adapter, problem
            gc.collect()
    except BudgetExceeded as error:
        stopped = type(error).__name__+': '+str(error)
    except Exception as error:
        stopped = type(error).__name__+': '+str(error)
        sink.failure({'run_id': run_id, 'row_id': run_id+'_setup'}, error)
    rows = sink.rows[start_row:]
    sink.export_tables()
    frontiers = _frontier_records(rows)
    write_json(sink.directory/'FAIR_FRONTIERS.json', dict(run_id=run_id, **frontiers))
    failures = [row for row in rows if row['status'] in ('FAILED', 'BUDGET_STOP')]
    summary = {'run_id': run_id, 'status': 'STOPPED_PARTIAL' if stopped else
               'COMPLETE_WITH_FAILURES' if failures else 'COMPLETE_OBSERVATIONS',
               'stopped_reason': stopped, 'method_rows': sum(row['record_kind'] == 'method' for row in rows),
               'failures': len(failures), 'scenes': scene_records,
               'parents_requested': [row['parent_id'] for row in selected],
               'iterations_requested': selected_iterations, 'degrees': degrees,
               'scientific_gate_decision': 'PARENT_REVIEW_REQUIRED',
               'missing_controls': ['current_POD', 'strong_derivative_goal_aware_ROM'],
               'cost_scope': 'shared geometry/state/reference/U charged once; method basis is cumulative seed+extension only',
               'row_costs_must_not_be_summed_across_degrees': True,
               'book_receipt': book.receipt(),
               'artifacts': {'results_csv': str(sink.directory/'REPLAY_RESULTS.csv'),
                             'actions_csv': str(sink.directory/'ACTION_COUNTS.csv'),
                             'rows_jsonl': str(sink.rows_path), 'failures_jsonl': str(sink.fail_path),
                             'fair_frontiers': str(sink.directory/'FAIR_FRONTIERS.json')}}
    write_json(sink.directory/'REPLAY_SUMMARY.json', summary)
    return plain(summary)
