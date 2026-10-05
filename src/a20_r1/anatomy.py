"""Registered R1 snapshot anatomy; observations and accounting, never gates.

The only teacher is the existing canonical constrained reference.  Its step
is opened and revalidated in an offline scope, and is passed only to the two
explicit oracle policies.  Candidate QPs use the unchanged A20 solver.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import csv
import gc
import json
import time
import uuid

import numpy as np
from scipy import linalg as la

from a20.backend import Adapter, BasisView, load_problem
from a20.costs import BudgetExceeded, plain, write_json
from a20.material import QPFailure, kkt, solve_quadratic
from a20.opm import FullJacobian
from a20.replay import (_Reference, _Segment, _empty_cost, _sum_costs,
                        _load_state, _evaluate_full_step, _evaluate_truth_step)


PARENTS = (2001, 2005, 2003, 2007, 2013)
ITERATIONS = (0, 17)
CANONICAL_METHODS = ('FIXED-DEEP', 'WIDE-M', 'CHEAP-TASK', 'ORACLE-M')
PROTECTED_METHODS = ('PROTECTED-ORACLE', 'PROTECTED-RANDOM')
ORACLES = frozenset(('ORACLE-M', 'PROTECTED-ORACLE'))
VECTOR_KEYS = ('F_actions', 'F_adjoint_actions', 'L_actions', 'L_adjoint_actions')
DEGREES = {'FIXED-DEEP': 3, 'WIDE-M': 1, 'CHEAP-TASK': 3, 'ORACLE-M': 3,
           'PROTECTED-ORACLE': 3, 'PROTECTED-RANDOM': 3}
BASELINE_METRICS = ('relative_H_step_error', 'absolute_H_step_error',
                    'reference_H_energy', 'full_quadratic_gap',
                    'full_stationarity_defect_norm', 'full_KKT_defect_norm',
                    'full_KKT_relative', 'truth_one_step_error',
                    'truth_one_step_absolute_L2', 'truth_one_step_real_error',
                    'truth_one_step_imag_error')


class AnatomyInputError(ValueError):
    """An existing input is missing, ambiguous, or fails its frozen audit."""


class BaselineConflict(AnatomyInputError):
    """Stop the remaining campaign when the original baseline cannot reproduce."""


def _identity(row):
    return (int(row.get('parent_object_id', row.get('parent_id'))),
            int(row['iteration']), row['method'])


class _Sink:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory/'rows.jsonl'
        self.failure_path = self.directory/'failures.jsonl'
        self.failure_path.touch(exist_ok=True)
        self.rows = []
        self.attempts = set()
        if self.path.exists():
            with self.path.open(encoding='utf-8') as handle:
                for line in handle:
                    if line.strip():
                        row = json.loads(line)
                        self.rows.append(row)
                        if row.get('record_kind') == 'method':
                            key = _identity(row)
                            if key in self.attempts:
                                raise AnatomyInputError('DUPLICATE_EXISTING_MODEL_ATTEMPT:'+str(key))
                            self.attempts.add(key)

    def reject_existing(self, cases):
        wanted = {(p, i, m) for p, i in cases
                  for m in CANONICAL_METHODS+PROTECTED_METHODS+('HISTORY',)}
        overlap = self.attempts & wanted
        if overlap:
            raise AnatomyInputError('DUPLICATE_STATE_MODEL_ATTEMPT:'+str(sorted(overlap)))

    def append(self, row):
        row = plain(row)
        if row.get('record_kind') == 'method':
            key = _identity(row)
            if key in self.attempts:
                raise AnatomyInputError('DUPLICATE_STATE_MODEL_ATTEMPT:'+str(key))
            self.attempts.add(key)
        with self.path.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(row, allow_nan=False)+'\n')
            handle.flush()
        self.rows.append(row)

    def save_step(self, row, step, *, failed=False):
        directory = self.directory/('failed_steps' if failed else 'steps')
        directory.mkdir(exist_ok=True)
        path = directory/(row['row_id']+'.npz')
        if path.exists():
            raise AnatomyInputError('DUPLICATE_CANDIDATE_STEP_PATH:'+str(path))
        np.savez_compressed(path, step=np.asarray(step, dtype=np.float64))
        return str(path)

    def failure(self, row, error, *, step=None, details=None):
        record = {k: row.get(k) for k in ('job', 'run_id', 'row_id',
                   'parent_object_id', 'iteration', 'method', 'record_kind')}
        record.update(error=type(error).__name__+': '+str(error), details=details)
        if step is not None:
            failed_row = dict(row, row_id=row['row_id']+'_failure_'+uuid.uuid4().hex[:6])
            record['failed_step_path'] = self.save_step(failed_row, step, failed=True)
        with self.failure_path.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(plain(record), allow_nan=False)+'\n')
            handle.flush()
        return record

    def export(self):
        # JSONL is the immediate checkpoint; CSV is serialized once in epilogue.
        fields = sorted(set().union(*(set(r) for r in self.rows))) if self.rows else []
        path = self.directory/'ANATOMY_RESULTS.csv'
        temporary = path.with_suffix('.csv.tmp')
        with temporary.open('w', newline='', encoding='utf-8') as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows({k: json.dumps(v, allow_nan=False) if isinstance(v, (dict, list)) else v
                              for k, v in r.items()} for r in self.rows)
        temporary.replace(path)


def _canonical_index(path):
    """Index exactly the existing reference and original mixed12 degree3 rows."""
    index = {}
    with Path(path).open(encoding='utf-8') as handle:
        for number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            pid, iteration = row.get('parent_object_id'), row.get('iteration')
            if pid not in PARENTS or iteration not in ITERATIONS:
                continue
            kind = None
            if row.get('record_kind') == 'shared_reference' and row.get('method') == 'full_GN_reference':
                kind = 'reference'
            elif (row.get('record_kind') == 'method' and row.get('method') == 'mixed'
                  and row.get('degree') == 3):
                kind = 'baseline'
            if kind is not None:
                index.setdefault((int(pid), int(iteration), kind), []).append((number, row))
    return index


def _unique(index, parent, iteration, kind):
    matches = index.get((parent, iteration, kind), [])
    if len(matches) != 1:
        raise AnatomyInputError(('MISSING_' if not matches else 'DUPLICATE_')+
                                'CANONICAL_'+kind.upper()+':'+str((parent, iteration)))
    return matches[0]


def _resolve_step(canonical, recorded):
    """Windows/remote absolute paths are provenance, never executable inputs.

    Only the recorded basename in the canonical steps/failed_steps folders is
    admissible.  A second copy is ambiguous even if one absolute path exists.
    """
    if not isinstance(recorded, str) or not recorded:
        raise AnatomyInputError('MISSING_RECORDED_STEP_PATH')
    parts = recorded.replace('\\', '/').split('/')
    registered = [p for p in parts[:-1] if p in ('steps', 'failed_steps')]
    if len(registered) != 1 or not parts[-1].endswith('.npz'):
        raise AnatomyInputError('UNREGISTERED_STEP_DIRECTORY:'+recorded)
    directory = Path(canonical).parent
    matches = [directory/name/parts[-1] for name in ('steps', 'failed_steps')
               if (directory/name/parts[-1]).is_file()]
    if len(matches) != 1:
        raise AnatomyInputError(('MISSING_' if not matches else 'AMBIGUOUS_')+
                                'RECORDED_STEP_BASENAME:'+parts[-1])
    if matches[0].parent.name != registered[0]:
        raise AnatomyInputError('RECORDED_STEP_DIRECTORY_MISMATCH:'+parts[-1])
    return matches[0]


def _read_step(path, dimension):
    with np.load(path, allow_pickle=False) as data:
        if set(data.files) != {'step'}:
            raise AnatomyInputError('NONCANONICAL_CANDIDATE_STEP_KEYS')
        value = data['step'].copy()
    if value.shape != (dimension,) or np.iscomplexobj(value) or not np.all(np.isfinite(value)):
        raise AnatomyInputError('INVALID_REAL_MATERIAL_STEP')
    return np.asarray(value, dtype=np.float64)


def _canonical_provenance(saved, parent, iteration, config):
    expected = {'parent_object_id': int(parent['parent_id']), 'iteration': iteration,
                'parameterization': parent['parameterization'], 'n_current': parent['n_current'],
                'p_material': parent['p_material'], 'n_source': parent['sources'],
                'n_receiver': parent['receivers'], 'frequencies': parent['frequencies'],
                'precision': config['precision']}
    mismatches = {key: {'expected': value, 'recorded': saved.get(key)}
                  for key, value in expected.items() if saved.get(key) != value}
    if mismatches or not saved.get('backend_commit') or not saved.get('run_id'):
        error = AnatomyInputError('CANONICAL_STATE_OR_BACKEND_PROVENANCE_MISMATCH')
        error.details = mismatches
        raise error


def _row(run_id, job, parent, iteration, method, *, kind='method', suffix=''):
    pid = int(parent['parent_id'])
    return {'schema': 'a20.r1.anatomy.v1', 'run_id': run_id, 'job': job,
            'row_id': f'{run_id}_{pid}_{iteration}_{method}{suffix}',
            'record_kind': kind, 'parent_object_id': pid, 'parent_id': pid,
            'iteration': iteration, 'state': 'late' if iteration == 17 else 'early',
            'method': method, 'degree': DEGREES.get(method),
            'status': 'PENDING', 'failure_reason': None, 'reference_valid': False,
            'QP_valid': False, 'relative_H_step_error': None, 'rank': None,
            'actual_rank': None, 'baseline_H_error': None,
            'dataset_exposure': 'historically_exposed_feasibility',
            'parameterization': parent.get('parameterization'),
            'oracle_only': method in ORACLES, 'legal_candidate': method not in ORACLES and method != 'HISTORY',
            'truth_used_in_seed': False, 'full_reference_used': method in ORACLES,
            'previous_accepted_step_used': False, 'full_fallback_used': False,
            'fullfallback_used': False, 'teacher_regenerated': False,
            'H_denominator_floor_used': False, 'scientific_gate_computed': False}


def _metadata(book, row):
    book.metadata.update(run_id=row['run_id'], job=row['job'],
                         parent_object_id=row['parent_object_id'],
                         iteration=row['iteration'], method=row['method'],
                         degree=row.get('degree'))


def _stage(book, row, label, phase, costs, key, operation):
    _metadata(book, row)
    book.metadata['stage'] = label
    segment = _Segment(book, label, phase=phase)
    try:
        book.check()
        with segment:
            return operation()
    finally:
        costs[key] = segment.cost


def _cost_row(row, costs):
    actual = _sum_costs(*costs.values())
    row.update(costs=costs, counts=actual['counts'], charged_actual_cost=actual)


def _revalidate_reference(canonical, saved, adapter, x, residual, jac, lam, ell, config):
    """Revalidate a saved constrained teacher; no optimization is available here."""
    if saved.get('status') != 'OK' or not str(saved.get('reference_status', '')).startswith('VERIFIED_'):
        raise AnatomyInputError('CANONICAL_REFERENCE_NOT_VERIFIED')
    path = _resolve_step(canonical, saved.get('reference_step_path'))
    step = _read_step(path, adapter.p)
    gradient0 = jac.pullback(residual)+ell
    js = jac.action(step)
    audit = kkt(adapter.chart, x, step, jac.pullback(residual+js)+lam*step+ell,
                tolerance=config['feasibility_tolerance'])
    denominator = float(la.norm(gradient0))
    relative = audit['stationarity_norm']/max(denominator, 1e-12)
    energy = float(js@js+lam*step@step)
    prior_gradient = config['prior']*adapter.chart.project(x-adapter.problem.init)
    ell_error = float(la.norm(ell-prior_gradient))
    ell_denominator = float(la.norm(prior_gradient))
    ell_valid = ell_error <= 1e-12 if ell_denominator == 0 else ell_error/ell_denominator <= 1e-9
    record = {'reference_status': 'REVALIDATED_EXISTING_CONSTRAINED_REFERENCE',
              'reference_source': 'canonical_existing_constrained_step',
              'reference_recorded_step_path': saved.get('reference_step_path'),
              'reference_step_path': str(path), 'reference_row_id': saved.get('row_id'),
              'reference_KKT_relative': relative, 'reference_KKT_denominator': denominator,
              'reference_feasibility_violation': audit['violation'],
              'reference_complementarity': audit['complementarity'],
              'reference_active_constraints': audit['active_constraints'],
              'reference_QP_original': saved.get('reference_QP'),
              'reference_QP_valid': relative <= config['qp_kkt_rtol'] and audit['violation'] <= config['feasibility_tolerance'],
              'reference_H_norm_squared': energy, 'reference_H_energy': energy,
              'reference_H_norm': float(np.sqrt(max(0., energy))),
              'reference_H_floor': config['replay_H_relative_floor'],
              'reference_H_nonzero_valid': energy > config['replay_H_relative_floor']**2,
              'runtime_ell_prior_gradient_valid': ell_valid,
              'runtime_ell_prior_gradient_absolute_error': ell_error,
              'reference_valid': False, 'teacher_regenerated': False}
    valid = (record['reference_QP_valid'] and record['reference_H_nonzero_valid'] and ell_valid
             and np.isfinite(energy))
    if not valid:
        error = AnatomyInputError('EXISTING_REFERENCE_KKT_FEASIBILITY_OR_H_FLOOR_INVALID')
        error.details = record
        raise error
    record['reference_valid'] = True
    quadratic = float(.5*(residual+js)@(residual+js)+ell@step+.5*lam*step@step)
    return _Reference(step, js, quadratic, energy, gradient0, record)


def _metric_comparison(actual, saved, config):
    """No zero substitution: exact zeros require exact numerical equality."""
    comparisons = {}
    for key in BASELINE_METRICS:
        old, new = saved.get(key), actual.get(key)
        finite = (isinstance(old, (int, float)) and isinstance(new, (int, float))
                  and np.isfinite(old) and np.isfinite(new))
        if not finite:
            comparisons[key] = {'valid': False, 'reason': 'MISSING_OR_NONFINITE_METRIC'}
        elif old == 0:
            comparisons[key] = {'valid': new == 0, 'saved': old, 'recomputed': new,
                                'relative_error': None, 'zero_reference': True}
        else:
            error = float(abs(new-old)/abs(old))
            comparisons[key] = {'valid': error <= config['baseline_reproduction_rtol'],
                                'saved': old, 'recomputed': new, 'relative_error': error,
                                'zero_reference': False}
    return all(c['valid'] for c in comparisons.values()), comparisons


def _capture(target, span, floor, rtol):
    """Squared orthogonal-projection energy fraction, with an explicit floor."""
    target, span = np.asarray(target), np.asarray(span)
    if target.ndim == 1:
        target = target[:, None]
    if span.ndim != 2 or span.shape[0] != target.shape[0]:
        raise AnatomyInputError('CAPTURE_SPAN_SHAPE_MISMATCH')
    norm = float(la.norm(target))
    if not np.all(np.isfinite(target)) or not np.all(np.isfinite(span)):
        raise AnatomyInputError('NONFINITE_CAPTURE_INPUT')
    rank = span.shape[1]
    if rank and la.norm(span.conj().T@span-np.eye(rank)) > 1e-8:
        u, sv, _ = la.svd(span, full_matrices=False)
        rank = int(np.count_nonzero(sv > rtol*max(float(la.norm(span)), float(sv[0]))))
        span = u[:, :rank]
    if norm <= floor:
        return {'valid': False, 'capture': None, 'amplitude_capture': None,
                'relative_residual': None, 'target_norm': norm, 'floor': floor,
                'span_rank': rank, 'reason': 'TARGET_NORM_AT_OR_BELOW_FLOOR'}
    projection = span@(span.conj().T@target)
    energy = float(la.norm(projection)**2/norm**2)
    return {'valid': True, 'capture': energy, 'amplitude_capture': float(np.sqrt(max(0., energy))),
            'relative_residual': float(la.norm(target-projection)/norm),
            'target_norm': norm, 'floor': floor, 'span_rank': rank,
            'definition': 'squared Frobenius projection energy fraction; no denominator substitution'}


def _material_span(model, rtol):
    span = getattr(model, 'material_span', None)
    if span is not None:
        span = np.asarray(span)
    else:
        probes = np.asarray(model.seeds.material_probes)
        if np.iscomplexobj(probes) or probes.ndim != 2:
            raise AnatomyInputError('MATERIAL_PROBES_ARE_NOT_REAL_COORDINATES')
        if not probes.shape[1]:
            return probes.copy()
        u, sv, _ = la.svd(probes, full_matrices=False)
        rank = int(np.count_nonzero(sv > rtol*max(float(la.norm(probes)), float(sv[0]))))
        span = u[:, :rank]
    if np.iscomplexobj(span):
        raise AnatomyInputError('MATERIAL_SPAN_ARE_NOT_REAL_COORDINATES')
    return span


def _pair_metrics(step, reference, jac, lam, true_gradient0, floor):
    sm, fm = float(la.norm(step)), float(la.norm(reference.step))
    js, jf = jac.action(step), reference.jstep
    sh2, fh2 = float(js@js+lam*step@step), reference.energy
    sh, fh = float(np.sqrt(max(0., sh2))), float(np.sqrt(max(0., fh2)))
    material_valid, h_valid = sm > floor and fm > floor, sh > floor and fh > floor
    h_cosine = float((js@jf+lam*step@reference.step)/(sh*fh)) if h_valid else None
    h_angle = float(np.arccos(np.clip(h_cosine, -1., 1.))) if h_valid else None
    return {'material_cosine_valid': material_valid,
            'material_cosine': float(step@reference.step/(sm*fm)) if material_valid else None,
            'material_norm_ratio_valid': fm > floor,
            'material_norm_ratio': sm/fm if fm > floor else None,
            'candidate_material_norm': sm, 'reference_material_norm': fm,
            'H_cosine_valid': h_valid,
            'H_cosine': h_cosine, 'H_angle_radians': h_angle,
            'H_angle_degrees': float(np.degrees(h_angle)) if h_valid else None,
            'H_norm_ratio_valid': fh > floor,
            'H_norm_ratio': sh/fh if fh > floor else None,
            'candidate_H_norm': sh, 'reference_H_norm': fh,
            'full_objective_slope': float(true_gradient0@step),
            'full_objective_slope_valid': bool(np.all(np.isfinite(true_gradient0))),
            'full_objective_slope_scope': 'true full objective gradient at frozen x; LM curvature excluded',
            'pair_metric_denominator_floor': floor}


@dataclass
class _Case:
    parent: dict
    iteration: int
    adapter: object
    x: np.ndarray
    state: object
    residual: np.ndarray
    lam: float
    ell: np.ndarray
    full_jac: object
    reference: object
    baseline: dict
    baseline_step: object
    baseline_valid: bool
    costs: dict
    labels_path: Path
    revisit: bool = False
    schur: object = None
    bank: object = None
    target: object = None
    scaffold: object = None


def _shared_record(sink, row, costs, key, operation, book, phase):
    try:
        value = _stage(book, row, 'anatomy_'+key, phase, costs, key, operation)
        row['status'] = 'OK'
        return value
    except BaseException as error:
        row.update(status='STOPPED' if isinstance(error, BudgetExceeded) else 'FAILED',
                   failure_reason=type(error).__name__+': '+str(error))
        row['failure'] = sink.failure(row, error, details=getattr(error, 'details', None))
        raise
    finally:
        _cost_row(row, {key: costs.get(key, _empty_cost())})
        sink.append(row)


def _prepare_case(root, config, book, device, parent, iteration, canonical, index,
                  sink, run_id, job, *, revisit=False):
    pid, costs = int(parent['parent_id']), {}
    suffix = '_protected_revisit' if revisit else ''
    reference_number, reference_row = _unique(index, pid, iteration, 'reference')
    _canonical_provenance(reference_row, parent, iteration, config)
    geometry_row = _row(run_id, job, parent, iteration, 'shared_geometry', kind='shared_setup', suffix=suffix)
    def geometry():
        problem = load_problem(root/parent['runtime_problem'])
        if problem.parent_id != pid or problem.chart.kind == 'voxel' or problem.chart.Q is None:
            raise AnatomyInputError('R1_REQUIRES_REGISTERED_GAUSSIAN_CHART')
        return Adapter(problem, device=device, book=book)
    adapter = _shared_record(sink, geometry_row, costs, 'geometry', geometry, book, 'shared_setup')
    state_row = _row(run_id, job, parent, iteration, 'shared_full_state', kind='shared_state', suffix=suffix)
    def load_current():
        x, lam, ell = _load_state(root, parent, iteration, adapter.chart)
        state = adapter.full_state(x, reuse=True)
        residual = adapter.residual(state)
        state_row.update(lambda_total=lam, data_residual_norm=float(la.norm(residual)),
                         full_state_residual_verified_below=1e-9,
                         source_residual_repeated_for_reporting=False,
                         protected_revisit_full_state_paid=revisit)
        return x, lam, ell, state, residual
    x, lam, ell, state, residual = _shared_record(sink, state_row, costs, 'full_state', load_current, book, 'shared_state')
    jac = FullJacobian(adapter, x, state)
    ref_record = _row(run_id, job, parent, iteration, 'existing_full_GN_reference', kind='shared_reference', suffix=suffix)
    def audit_reference():
        jac.small_matrix()  # once, paid; never given to an online seed builder
        ref = _revalidate_reference(canonical, reference_row, adapter, x, residual, jac, lam, ell, config)
        ref_record.update(ref.record, canonical_line_number=reference_number,
                          full_quadratic_value=ref.quadratic)
        return ref
    reference = _shared_record(sink, ref_record, costs, 'reference', audit_reference, book, 'offline_reference')
    baseline, baseline_step, baseline_valid = {}, None, False
    legacy_row = _row(run_id, job, parent, iteration, 'saved_original_mixed12_degree3', kind='shared_baseline', suffix=suffix)
    def audit_legacy():
        number, saved = _unique(index, pid, iteration, 'baseline')
        _canonical_provenance(saved, parent, iteration, config)
        if (saved.get('status') != 'OK' or saved.get('fullfallback_used')
            or saved.get('seed_budgets') != {'O': 4, 'P': 4, 'M': 4}):
            raise AnatomyInputError('INVALID_CANONICAL_FIXED_BASELINE')
        path = _resolve_step(canonical, saved.get('step_path'))
        step = _read_step(path, adapter.p)
        values = _evaluate_full_step(adapter, x, residual, jac, lam, ell, step, reference, config)
        values.update(_evaluate_truth_step(root/parent['offline_labels'], adapter.chart, x, step, config))
        valid, differences = _metric_comparison(values, saved, config)
        legacy_row.update(values, baseline_metrics_reproduction_valid=valid,
                          baseline_metric_comparison=differences, canonical_line_number=number,
                          baseline_original_row_id=saved.get('row_id'), baseline_saved_step_path=str(path),
                          baseline_recorded_step_path=saved.get('step_path'),
                          baseline_saved_H_error=saved.get('relative_H_step_error'))
        legacy_row['baseline_provenance'] = {k: saved.get(k) for k in
                                             ('run_id', 'backend_commit', 'seed_rng', 'seed_budgets', 'rank')}
        if not valid:
            legacy_row.update(status='FAILED', failure_reason='CANONICAL_BASELINE_METRIC_REPRODUCTION_MISMATCH')
        return saved, step, valid
    try:
        baseline, baseline_step, baseline_valid = _stage(book, legacy_row, 'anatomy_saved_baseline_audit',
                                                        'offline_audit', costs, 'baseline', audit_legacy)
        if legacy_row['status'] == 'PENDING':
            legacy_row['status'] = 'OK'
        if not baseline_valid:
            legacy_row['failure'] = sink.failure(legacy_row, AnatomyInputError(legacy_row['failure_reason']),
                                                 details=legacy_row.get('baseline_metric_comparison'))
    except BudgetExceeded as error:
        legacy_row.update(status='STOPPED', failure_reason=str(error))
        legacy_row['failure'] = sink.failure(legacy_row, error)
        raise
    except Exception as error:
        legacy_row.update(status='FAILED', failure_reason=type(error).__name__+': '+str(error))
        legacy_row['failure'] = sink.failure(legacy_row, error)
    finally:
        _cost_row(legacy_row, {'baseline': costs.get('baseline', _empty_cost())})
        sink.append(legacy_row)
    return _Case(parent, iteration, adapter, x, state, residual, lam, ell, jac,
                 reference, baseline, baseline_step, baseline_valid, costs,
                 root/parent['offline_labels'], revisit=revisit)


def _initialize_basis(case, config, book, sink, run_id, job, build_schur, paired_probe_bank,
                      *, revisit=False):
    suffix = '_protected_revisit' if revisit else ''
    row = _row(run_id, job, case.parent, case.iteration, 'shared_schur_and_bank', kind='shared_basis', suffix=suffix)
    view = BasisView(case.adapter, case.x, case.state, case.residual, previous=None)
    def setup():
        case.schur = _stage(book, row, 'anatomy_shared_schur', 'legal_seed', case.costs, 'schur',
                            lambda: build_schur(case.adapter, case.x, case.state, case.residual, config))
        case.bank = _stage(book, row, 'anatomy_shared_probe_bank', 'legal_seed', case.costs, 'bank',
                           lambda: paired_probe_bank(view, config))
        row.update(retained_info=getattr(case.schur, 'r1_info', {}),
                   actual_retained_rank=case.schur.U.shape[1],
                   common_probe_bank_paired=True)
    try:
        setup()
        row['status'] = 'OK'
    except BaseException as error:
        row.update(status='STOPPED' if isinstance(error, BudgetExceeded) else 'FAILED', failure_reason=str(error))
        row['failure'] = sink.failure(row, error)
        raise
    finally:
        _cost_row(row, {k: case.costs.get(k, _empty_cost()) for k in ('schur', 'bank')})
        sink.append(row)


def _ensure_target(case, book, sink, run_id, job, source_target_block):
    if case.target is not None:
        return
    # Acquire this offline diagnostic only after a candidate QP was attempted.
    # It is cached for this state, never supplied to the legal policy API.
    view = BasisView(case.adapter, case.x, case.state, case.residual, previous=None)
    suffix = '_protected_revisit' if case.revisit else ''
    target_row = _row(run_id, job, case.parent, case.iteration, 'shared_offline_KB_target', kind='shared_audit', suffix=suffix)
    def target():
        block = source_target_block(view, case.schur, case.reference.step)
        target_row.update(KB_target_norm=float(la.norm(block)), source_columns=block.shape[1],
                          offline_target_passed_to_legal_builder=False)
        return block
    case.target = _shared_record(sink, target_row, case.costs, 'target', target, book, 'offline_audit')


def _audit_model(case, model, step, config):
    ref, floor = case.reference, config['replay_H_relative_floor']
    material = _capture(ref.step, _material_span(model, config['orthogonal_rank_rtol']),
                        floor, config['orthogonal_rank_rtol'])
    q_m = model.seeds.blocks.get('M', np.empty((case.adapter.n, 0), dtype=np.complex128))
    q_capture = _capture(case.target, q_m, floor, config['orthogonal_rank_rtol'])
    z_capture = _capture(case.target, model.projection.Z, floor, config['orthogonal_rank_rtol'])
    captures = {'material': material, 'qM_KB_source': q_capture, 'finalZ_KB_source': z_capture}
    valid = all(c['valid'] and c['capture'] >= config['oracle_capture_threshold'] for c in captures.values())
    tangent = model.jacobian.action(ref.step)
    tangent_norm = float(la.norm(ref.jstep))
    values = {'material_span_capture': material['capture'],
              'oracle_material_span_capture': material['capture'],
              'oracle_qM_source_capture': q_capture['capture'],
              'oracle_Z_source_capture': z_capture['capture'],
              'oracle_finalZ_source_capture': z_capture['capture'],
              'capture_diagnostics': captures, 'capture_inputs_valid': all(c['valid'] for c in captures.values()),
              'oracle_target_norm_valid': all(c['valid'] for c in captures.values()),
              'oracle_target_norm_floor_used': not all(c['valid'] for c in captures.values()),
              'oracle_capture_certified': valid, 'oracle_capture_threshold': config['oracle_capture_threshold'],
              'KB_target_norm': q_capture['target_norm'], 'KB_target_nonzero_valid': q_capture['valid'],
              'reference_tangent_error_valid': tangent_norm > floor,
              'reference_tangent_error': float(la.norm(tangent-ref.jstep)/tangent_norm) if tangent_norm > floor else None,
              'reference_tangent_absolute_error': float(la.norm(tangent-ref.jstep)),
              'reference_full_data_tangent_norm': tangent_norm,
              'capture_and_tangent_scope': 'offline diagnostic only; no seed feedback; J_m sF versus J_F sF'}
    if step is not None:
        values.update(_evaluate_full_step(case.adapter, case.x, case.residual, case.full_jac,
                                          case.lam, case.ell, step, ref, config))
        true_g0 = case.full_jac.pullback(case.residual)+config['prior']*case.adapter.chart.project(case.x-case.adapter.problem.init)
        values.update(_pair_metrics(step, ref, case.full_jac, case.lam, true_g0, floor))
        z = case.adapter.chart.project(case.x-case.adapter.problem.init)
        values['full_objective_at_frozen_state'] = float(.5*case.residual@case.residual+.5*config['prior']*z@z)
    return values


def _model_costs(row, model, own, case):
    build = own.get('build', _empty_cost())
    info = model.info if model is not None else {}
    # Shared bank/Schur were always supplied to build_model.  Their measured
    # outer segments include CPU/time absent from a plain CostBook.delta.
    # CHEAP requires the FIXED basis/projection but not its candidate QP or J.
    scaffold_cost = _empty_cost()
    if row['method'] == 'CHEAP-TASK' and case.scaffold is not None:
        scaffold_cost = case.scaffold.info.get('driver_build_cost',
                                               case.scaffold.info.get('noncommon_cost', _empty_cost()))
    standalone_builder = _sum_costs(case.costs.get('schur'), case.costs.get('bank'),
                                    build, scaffold_cost)
    own_matrix = own.get('matrix', _empty_cost())
    standalone = _sum_costs(case.costs.get('geometry'), case.costs.get('full_state'),
                            standalone_builder, own_matrix, own.get('QP'))
    incremental = _sum_costs(build, own_matrix, own.get('QP'))
    actual = _sum_costs(*own.values())
    proposal = {key: int(standalone['counts'].get(key, 0)) for key in VECTOR_KEYS}
    row.update(costs={'charged_incremental_stages': own,
                      'shared_case': case.costs, 'standalone': standalone,
                      'deployment_incremental': incremental,
                      'offline_audit': own.get('audit', _empty_cost()),
                      'paid_D_scaffold_build': scaffold_cost,
                      'native_builder_standalone_delta': info.get('standalone_cost')},
               charged_actual_cost=actual, counts=actual['counts'],
               proposal_action_counts=proposal,
               action_fourtuple=[proposal[key] for key in VECTOR_KEYS],
               action_fourtuple_order=['F', 'F*', 'L', 'L*'],
               proposal_Maxwell_vector_actions=sum(proposal.values()),
               actual_action_counts={key: int(actual['counts'].get(key, 0)) for key in VECTOR_KEYS},
               deployment_wall_seconds=standalone['wall_seconds'],
               basis_construction_wall_seconds=standalone_builder['wall_seconds'],
               incremental_basis_wall_seconds=build['wall_seconds'],
               basis_time_scope='shared Schur/bank plus this seed/hierarchy/projection build and needed paid CHEAP scaffold; excludes material matrix, QP and offline audit',
               material_matrix_wall_seconds=own_matrix['wall_seconds'],
               QP_wall_seconds=own.get('QP', _empty_cost())['wall_seconds'],
               offline_audit_wall_seconds=own.get('audit', _empty_cost())['wall_seconds'],
               standalone_cost=standalone, shared_creation_costs_attributed=True,
               D_scaffold_is_free=False,
               D_scaffold_matrix_required=False,
               D_scaffold_gradient_scope='ReducedJacobian.pullback uses S*/core*/B*; FIXED matrix acquisition is not needed',
               cost_scope='shared case created once; standalone logical attribution does not add to global CostBook',
               online_proposal=not row['oracle_only'])


def _run_model(case, method, config, book, sink, run_id, job, build_model, source_target_block):
    row = _row(run_id, job, case.parent, case.iteration, method)
    row.update(reference_valid=True, reference_status=case.reference.record['reference_status'],
               reference_QP_valid=True, reference_H_norm_squared=case.reference.energy,
               reference_H_norm=float(np.sqrt(case.reference.energy)),
               reference_step_path=case.reference.record['reference_step_path'],
               baseline_H_error=case.baseline.get('relative_H_step_error'),
               baseline_metrics_reproduction_valid=case.baseline_valid,
               backend_commit=book.metadata.get('source_commit'), no_full_fallback=True)
    costs, model, step = {}, None, None
    try:
        def construct():
            if method == 'CHEAP-TASK' and case.scaffold is None:
                raise AnatomyInputError('MISSING_PAID_FIXED_SCAFFOLD')
            return build_model(case.adapter, case.x, case.state, case.residual, case.ell,
                               config, method, reference_step=case.reference.step.copy() if method in ORACLES else None,
                               previous=None, scaffold=case.scaffold if method == 'CHEAP-TASK' else None,
                               schur=case.schur, bank=case.bank)
        model = _stage(book, row, 'anatomy_model_build',
                       'offline_oracle_seed' if method in ORACLES else 'legal_seed', costs, 'build', construct)
        model.info['driver_build_cost'] = costs['build']
        rank = int(model.projection.Z.shape[1])
        row.update(model_info=model.info, rank=rank, actual_rank=rank,
                   allocation=model.info.get('allocation'),
                   actual_seed_ranks=model.info.get('actual_seed_ranks',
                                                    {k: v.shape[1] for k, v in model.seeds.blocks.items()}),
                   projection_kind=model.projection.kind,
                   projection_fallback=model.projection.fallback,
                   core_stability=model.projection.stability,
                   actual_retained_rank=model.schur.U.shape[1],
                   orthogonality_error=float(la.norm(model.projection.Z.conj().T@model.projection.Z-np.eye(rank))))
        if rank > config['current_rank_cap']:
            raise AnatomyInputError('ACTUAL_CURRENT_RANK_EXCEEDS_FROZEN_CAP')
        if method == 'FIXED-DEEP':
            case.scaffold = model
        _stage(book, row, 'anatomy_material_data_matrix',
               'offline_oracle_candidate' if method in ORACLES else 'online', costs, 'matrix', model.jacobian.matrix)
        model.info['driver_material_matrix_cost'] = costs['matrix']
        try:
            step, solution, _ = _stage(book, row, 'anatomy_candidate_QP',
                    'offline_oracle_candidate' if method in ORACLES else 'online', costs, 'QP',
                    lambda: solve_quadratic(case.adapter.chart, case.x, case.residual,
                                           model.jacobian, case.lam, case.ell, config, book))
            row.update(QP=solution, QP_valid=True, status='OK')
        except QPFailure as error:
            step = getattr(error, 'step', None)
            row.update(status='QP_FAILED', QP=getattr(error, 'result', None),
                       failure_reason=type(error).__name__+': '+str(error), QP_valid=False)
            row['failure'] = sink.failure(row, error, step=step, details=getattr(error, 'result', None))
        _ensure_target(case, book, sink, run_id, job, source_target_block)
        def audit():
            values = _audit_model(case, model, step, config)
            if step is not None:
                values.update(_evaluate_truth_step(case.labels_path,
                                                   case.adapter.chart, case.x, step, config))
            return values
        row.update(_stage(book, row, 'anatomy_model_offline_audit', 'offline_audit', costs, 'audit', audit))
        if method == 'FIXED-DEEP':
            metric_valid, differences = _metric_comparison(row, case.baseline, config)
            old_norm = float(la.norm(case.baseline_step)) if case.baseline_step is not None else None
            if old_norm is None or step is None:
                step_error, step_valid = None, False
            elif old_norm == 0:
                step_error, step_valid = None, bool(np.array_equal(step, case.baseline_step))
            else:
                step_error = float(la.norm(step-case.baseline_step)/old_norm)
                step_valid = step_error <= config['baseline_reproduction_rtol']
            valid = case.baseline_valid and metric_valid and step_valid and row['QP_valid']
            row.update(baseline_reproduction_valid=valid, baseline_step_reproduction_valid=step_valid,
                       baseline_step_relative_error=step_error, baseline_step_saved_norm=old_norm,
                       baseline_model_metric_comparison=differences,
                       baseline_reproduction_rtol=config['baseline_reproduction_rtol'])
            if not valid and row['status'] == 'OK':
                row.update(status='FAILED', failure_reason='FIXED_BASELINE_STEP_OR_METRIC_REPRODUCTION_MISMATCH')
                row['failure'] = sink.failure(row, AnatomyInputError(row['failure_reason']),
                                             step=step, details=differences)
    except BaseException as error:
        row.update(status='STOPPED' if isinstance(error, BudgetExceeded) else 'FAILED',
                   failure_reason=type(error).__name__+': '+str(error))
        row['failure'] = sink.failure(row, error, step=getattr(error, 'step', step),
                                      details=getattr(error, 'result', None))
        if isinstance(error, BudgetExceeded):
            raise
    finally:
        if step is not None:
            row['step_path'] = sink.save_step(row, step, failed=row['status'] != 'OK')
        row['model_built'] = model is not None
        _model_costs(row, model, costs, case)
        sink.append(row)
    return row


def _blocked_rows(parent, iteration, methods, error, sink, run_id, job, *, case=None,
                  reference_record=None, baseline_H_error=None, status=None):
    for method in methods:
        key = (int(parent['parent_id']), iteration, method)
        if key in sink.attempts:
            continue
        row = _row(run_id, job, parent, iteration, method)
        record = case.reference.record if case is not None else reference_record
        reference_valid = record is not None and bool(record.get('reference_valid'))
        row.update(status=status or ('FAILED' if reference_valid else 'INVALID_REFERENCE'),
                   failure_reason=type(error).__name__+': '+str(error), model_built=False,
                   reference_valid=reference_valid,
                   reference_status=record['reference_status'] if reference_valid else 'MISSING_OR_INVALID_EXISTING_REFERENCE')
        if reference_valid:
            row.update(reference_H_norm_squared=record['reference_H_norm_squared'],
                       reference_H_norm=record['reference_H_norm'],
                       reference_QP_valid=True,
                       baseline_H_error=case.baseline.get('relative_H_step_error') if case is not None else baseline_H_error)
        row['failure'] = sink.failure(row, error, details=getattr(error, 'details', None))
        row.update(costs={}, counts={}, proposal_action_counts=None, action_fourtuple=None)
        sink.append(row)


def run_anatomy(root, config, book, device, job):
    """Run the frozen 40-model anatomy and its conditional 20-model guard.

    This function performs paid physics only when explicitly called by the
    parent CLI.  BudgetExceeded is re-raised after durable partial output.
    Revisited earlier states acquire fresh paid adapters/states; no retained
    GPU model, hidden full-model rescue, or teacher regeneration is used.
    """
    from .seeds import build_model, build_schur, paired_probe_bank, source_target_block

    root = Path(root).resolve()
    config = dict(config)
    if tuple(config['parents']) != PARENTS or set(config['replay_iterations']) != set(ITERATIONS):
        raise AnatomyInputError('R1_ANATOMY_FROZEN_PARENT_OR_STATE_SELECTION_CHANGED')
    if config['replay_H_relative_floor'] != 1e-12 or config['qp_kkt_rtol'] != 1e-8:
        raise AnatomyInputError('R1_REFERENCE_FLOOR_OR_KKT_TOLERANCE_CHANGED')
    if not config.get('no_full_fallback', False) or config['current_rank_cap'] != 56:
        raise AnatomyInputError('R1_FROZEN_RANK_OR_NO_RESCUE_CONTRACT_CHANGED')
    job = str(job.get('job_id', job.get('id', job))) if isinstance(job, dict) else str(job)
    run_id = time.strftime('%Y%m%dT%H%M%S', time.gmtime())+'_'+uuid.uuid4().hex[:8]
    # Late-first ordering discovers the registered guard before early states.
    cases = [(pid, iteration) for iteration in (17, 0) for pid in PARENTS]
    sink = _Sink(root/'results/a20_r1/anatomy')
    sink.reject_existing(cases)
    start = len(sink.rows)
    canonical = root/'results/replay/replay.jsonl'
    setup_costs, stopped, failure, guard = {}, None, None, False
    guard_sources, indeterminate, protected_completed = [], [], set()
    failed_states = {}
    conflict_state, conflict_reference = None, None
    summary = None
    try:
        setup_row = _row(run_id, job, {'parent_id': 0}, 17, 'canonical_preflight', kind='shared_setup')
        def preflight():
            manifest = json.loads((root/'configs/parents.json').read_text(encoding='utf-8'))
            records = {int(r['parent_id']): r for r in manifest['parents']}
            if any(pid not in records or records[pid]['parameterization'] != 'gaussian' for pid in PARENTS):
                raise AnatomyInputError('MISSING_REGISTERED_GAUSSIAN_PARENT')
            return records, _canonical_index(canonical)
        parents, index = _shared_record(sink, setup_row, setup_costs, 'preflight', preflight, book, 'shared_setup')
        for pid, iteration in cases:
            row = _row(run_id, job, parents[pid], iteration, 'HISTORY')
            row.update(status='NOT_RUN', failure_reason='NO_OWN_ACCEPTED_TRAJECTORY_IN_SOURCE_SNAPSHOT',
                       legal_candidate=False, costs={}, counts={}, model_built=False,
                       previous_source='NOT_AVAILABLE; no saved full/FIXED step is substituted')
            sink.append(row)
        for pid, iteration in cases:
            case = None
            print(f'ANATOMY parent={pid} iteration={iteration}', flush=True)
            try:
                case = _prepare_case(root, config, book, device, parents[pid], iteration,
                                     canonical, index, sink, run_id, job)
                if not case.baseline_valid:
                    conflict_state, conflict_reference = (pid, iteration), plain(case.reference.record)
                    raise BaselineConflict('SAVED_FIXED_BASELINE_METRICS_NOT_REPRODUCED:'+str((pid, iteration)))
                _initialize_basis(case, config, book, sink, run_id, job, build_schur,
                                  paired_probe_bank)
                for method in CANONICAL_METHODS:
                    row = _run_model(case, method, config, book, sink, run_id, job, build_model, source_target_block)
                    if method == 'FIXED-DEEP' and not row.get('baseline_reproduction_valid', False):
                        conflict_state, conflict_reference = (pid, iteration), plain(case.reference.record)
                        raise BaselineConflict('FIXED_BASELINE_STEP_OR_METRICS_NOT_REPRODUCED:'+str((pid, iteration)))
                    if method == 'ORACLE-M' and iteration == 17:
                        capture = row.get('oracle_qM_source_capture')
                        if capture is None or not row.get('KB_target_nonzero_valid', False):
                            indeterminate.append({'parent_object_id': pid, 'iteration': iteration,
                                                  'reason': 'RAW_ORACLE_TARGET_CAPTURE_UNAVAILABLE'})
                        elif capture < config['oracle_capture_threshold']:
                            guard = True
                            guard_sources.append({'parent_object_id': pid, 'iteration': iteration,
                                                  'oracle_qM_source_capture': capture})
                if guard:
                    for method in PROTECTED_METHODS:
                        _run_model(case, method, config, book, sink, run_id, job, build_model, source_target_block)
                    protected_completed.add((pid, iteration))
            except BudgetExceeded:
                raise
            except BaselineConflict:
                raise
            except Exception as error:
                _blocked_rows(parents[pid], iteration, CANONICAL_METHODS, error, sink, run_id, job, case=case)
                # Keep plain failure data, never a traceback retaining a GPU model.
                failed_states[(pid, iteration)] = {'error': type(error).__name__+': '+str(error),
                    'reference_record': plain(case.reference.record) if case is not None else None,
                    'baseline_H_error': case.baseline.get('relative_H_step_error') if case is not None else None}
                if guard:
                    _blocked_rows(parents[pid], iteration, PROTECTED_METHODS, error, sink, run_id, job, case=case)
                    protected_completed.add((pid, iteration))
            finally:
                case = None
                gc.collect()
        if guard:
            # Only states completed before the first late trigger are revisited.
            for pid, iteration in cases:
                if (pid, iteration) in protected_completed:
                    continue
                if (pid, iteration) in failed_states:
                    previous_failure = failed_states[(pid, iteration)]
                    error = AnatomyInputError('PRIOR_SHARED_STATE_FAILURE:'+previous_failure['error'])
                    _blocked_rows(parents[pid], iteration, PROTECTED_METHODS, error, sink, run_id, job,
                                  reference_record=previous_failure['reference_record'],
                                  baseline_H_error=previous_failure['baseline_H_error'])
                    protected_completed.add((pid, iteration))
                    continue
                case = None
                print(f'ANATOMY protected-revisit parent={pid} iteration={iteration}', flush=True)
                try:
                    case = _prepare_case(root, config, book, device, parents[pid], iteration,
                                         canonical, index, sink, run_id, job, revisit=True)
                    if not case.baseline_valid:
                        conflict_state, conflict_reference = (pid, iteration), plain(case.reference.record)
                        raise BaselineConflict('SAVED_FIXED_BASELINE_METRICS_NOT_REPRODUCED:'+str((pid, iteration)))
                    _initialize_basis(case, config, book, sink, run_id, job, build_schur,
                                      paired_probe_bank, revisit=True)
                    for method in PROTECTED_METHODS:
                        _run_model(case, method, config, book, sink, run_id, job, build_model, source_target_block)
                    protected_completed.add((pid, iteration))
                except BudgetExceeded:
                    raise
                except BaselineConflict:
                    raise
                except Exception as error:
                    _blocked_rows(parents[pid], iteration, PROTECTED_METHODS, error, sink, run_id, job, case=case)
                    protected_completed.add((pid, iteration))
                finally:
                    case = None
                    gc.collect()
    except BudgetExceeded as error:
        stopped = type(error).__name__+': '+str(error)
        raise
    except BaselineConflict as error:
        failure = type(error).__name__+': '+str(error)
        for pid, iteration in cases:
            same_state = (pid, iteration) == conflict_state
            _blocked_rows(parents[pid], iteration, CANONICAL_METHODS+(PROTECTED_METHODS if guard else ()),
                          error, sink, run_id, job,
                          reference_record=conflict_reference if same_state else None, status='NOT_RUN')
    except BaseException as error:
        failure = type(error).__name__+': '+str(error)
        raise
    finally:
        new_rows = sink.rows[start:]
        models = [r for r in new_rows if r.get('record_kind') == 'method' and r.get('method') != 'HISTORY']
        expected = 60 if guard else 40
        summary = {'schema': 'a20.r1.anatomy.summary.v1', 'job': job, 'run_id': run_id,
                   'status': 'STOPPED' if stopped else 'FAILED' if failure or any(r['status'] != 'OK' for r in models) else 'COMPLETE',
                   'stop_reason': stopped, 'failure_reason': failure,
                   'baseline_input_conflict_state': list(conflict_state) if conflict_state is not None else None,
                   'rows_path': str(sink.path), 'failures_path': str(sink.failure_path),
                   'canonical_input': str(canonical), 'canonical_models_expected': 40,
                   'models_expected': expected, 'model_rows_written': len(models),
                   'models_built': sum(bool(r.get('model_built')) for r in models),
                   'model_status_counts': {s: sum(r['status'] == s for r in models) for s in sorted({r['status'] for r in models})},
                   'protected_guard_triggered': guard, 'protected_guard_sources': guard_sources,
                   'protected_guard_indeterminate': indeterminate,
                   'protected_state_pairs_written': len(protected_completed),
                   'state_order': [[p, i] for p, i in cases],
                   'teacher_regenerated': False, 'scientific_gate_computed': False,
                   'shared_preflight_cost': setup_costs,
                   'cost_ledger_authority': 'parent CostBook events; logical standalone attribution is not additional billing'}
        sink.export()
        summary['budget_receipt'] = book.receipt()
        summary['budget_receipt_scope'] = 'snapshot after CSV export; parent final job receipt also includes summary serialization and imports'
        write_json(sink.directory/'ANATOMY_SUMMARY.json', summary)
    return summary
