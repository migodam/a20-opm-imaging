"""Frozen Stage-A directions and evaluator-only Maxwell labels.

Online forecasts are finalized before full-J or finite-forward labels. Data
generation does not activate a different Adapter operator, so it cannot borrow
or contaminate the paid known-background projection cache.
"""
from __future__ import annotations

import csv
import gc
import json
from pathlib import Path
import time
import uuid

import numpy as np
from scipy import linalg as la

from a20.backend import pack
from a20.costs import BudgetExceeded, plain, write_json
from a20.material import QPFailure
from .assets import load_online_scene
from .core import build_split, choose_directions, constrained_material_solve, profiled_witness
from .features import build_descriptor_context, direction_descriptor, predict_budget
from .online import build_anchor, build_opm


class ResumeMismatch(ValueError):
    """An existing freeze/cache cannot be used by this registered run."""


def stage_a_case_key(row):
    """Identity of one registered QP case; status is deliberately not a key."""
    integers = []
    for name in ('scene_id', 'direction_id', 'amplitude_level', 'noise_draw'):
        value = row[name]
        if isinstance(value, (bool, str)) or int(value) != value or int(value) < 0:
            raise ResumeMismatch('A22_RESUME_INVALID_CASE_KEY:' + name)
        integers.append(int(value))
    noise = row['noise_level']
    if isinstance(noise, (bool, str)) or not np.isfinite(noise) or noise < 0:
        raise ResumeMismatch('A22_RESUME_INVALID_CASE_KEY:noise_level')
    intervention = row['intervention']
    if not isinstance(intervention, str) or not intervention:
        raise ResumeMismatch('A22_RESUME_INVALID_CASE_KEY:intervention')
    return (*integers[:3], float(noise), integers[3], intervention)


def _read_rows(path):
    path = Path(path)
    if not path.exists():
        return []
    rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
    if any(not isinstance(row, dict) for row in rows):
        raise ResumeMismatch('A22_RESUME_INVALID_JSONL:' + path.name)
    return rows


def _restore_stage_a(out):
    """Retain every attempt, including invalids and failed scene summaries."""
    out = Path(out)
    rows = _read_rows(out/'direction_metrics.jsonl')
    splits = _read_rows(out/'split_metrics.jsonl')
    scenes = _read_rows(out/'scene_metrics.jsonl')
    completed = {stage_a_case_key(row) for row in rows if _case_completed(row)}
    complete_scenes = {int(row['scene_id']) for row in scenes if row.get('status') == 'COMPLETE'}
    return rows, splits, scenes, completed, complete_scenes


def _case_completed(row):
    """A terminal attempt; an INVALID_QP remains statistically ineligible."""
    if row.get('status') == 'INVALID_QP':
        return True
    if row.get('status') != 'OK':
        return False
    # A partially serialized/edited OK row is not evidence of a finished QP.
    required = ('coefficient_error', 'true_error', 'kkt_relative', 'feasibility')
    return all(isinstance(row.get(key), (float, int)) and not isinstance(row[key], bool)
               and np.isfinite(row[key]) for key in required)


def _require_array(actual, expected, name, *, rtol=1e-9):
    actual, expected = np.asarray(actual), np.asarray(expected)
    if (actual.shape != expected.shape or np.iscomplexobj(actual) != np.iscomplexobj(expected)
            or not np.all(np.isfinite(actual)) or not np.all(np.isfinite(expected))):
        raise ResumeMismatch('A22_RESUME_ARRAY_LAYOUT:' + name)
    scale = float(la.norm(expected.ravel()))
    error = float(la.norm((actual-expected).ravel()))
    if error > rtol*scale:
        raise ResumeMismatch('A22_RESUME_ARRAY_MISMATCH:' + name)
    return error/scale if scale else 0.


def _require_frozen(actual, expected, name):
    """Compare JSON semantics without replacing any preexisting evidence."""
    actual, expected = plain(actual), plain(expected)
    if isinstance(expected, dict):
        if not isinstance(actual, dict) or set(actual) != set(expected):
            raise ResumeMismatch('A22_RESUME_FROZEN_KEYS:' + name)
        for key in expected:
            _require_frozen(actual[key], expected[key], name+'.'+key)
    elif isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            raise ResumeMismatch('A22_RESUME_FROZEN_LAYOUT:' + name)
        for i, (old, new) in enumerate(zip(actual, expected)):
            _require_frozen(old, new, name+'.'+str(i))
    elif isinstance(expected, (float, int)) and not isinstance(expected, bool):
        if (isinstance(actual, bool) or not isinstance(actual, (float, int))
                or not np.isfinite(actual) or abs(actual-expected) > 1e-9*abs(expected)):
            raise ResumeMismatch('A22_RESUME_FROZEN_VALUE:' + name)
    elif type(actual) is not type(expected) or actual != expected:
        raise ResumeMismatch('A22_RESUME_FROZEN_VALUE:' + name)


def _scientific_provenance(value):
    operational = {'cost', 'costs', 'inclusive_wall_seconds', 'inclusive_scene_wall_seconds',
                   'process_cpu_seconds', 'exclusive_process_cpu_seconds', 'wall_seconds',
                   'exclusive_wall_seconds', 'exclusive_walls', 'job_id', 'run_id', 'event_id'}
    if isinstance(value, dict):
        return {key: _scientific_provenance(item) for key, item in value.items()
                if key not in operational and not (key == 'cache_identity' and isinstance(item, dict))}
    if isinstance(value, (list, tuple)):
        return [_scientific_provenance(item) for item in value]
    return value


def _freeze_json(path, value, *, resume, audit=None):
    path = Path(path)
    if resume and audit is not None:
        write_json(Path(audit)/(path.stem+'.regenerated.json'), value)
    if resume and path.exists():
        saved = json.loads(path.read_text(encoding='utf-8'))
        if path.name == 'online_provenance.json':
            _require_frozen(_scientific_provenance(saved), _scientific_provenance(value), path.name)
        else:
            _require_frozen(saved, value, path.name)
    else:
        write_json(path, value)


def _validate_split_rows(saved_rows, fresh, *, audit=None):
    """Handle only the two established dimensionless identity residuals."""
    if audit is not None:
        write_json(Path(audit)/('split_'+str(fresh['split_rank'])+'.regenerated.json'), fresh)
    identities = ('orthogonality', 'nuisance_leakage')
    reports = []
    for index, saved in enumerate(saved_rows):
        old, new = dict(saved), dict(fresh)
        report = dict(prior_attempt=index, split_rank=fresh['split_rank'], identity_residuals={})
        for name in identities:
            if name not in old and name not in new:
                continue
            if name not in old or name not in new:
                raise ResumeMismatch('A22_RESUME_SPLIT_IDENTITY_MISSING:' + name)
            values = (old.pop(name), new.pop(name))
            if any(isinstance(value, bool) or not isinstance(value, (float, int))
                   or not np.isfinite(value) or value < 0 or value > 1e-9 for value in values):
                raise ResumeMismatch('A22_RESUME_SPLIT_IDENTITY_FAILED:' + name)
            report['identity_residuals'][name] = dict(saved=values[0], regenerated=values[1],
                absolute_difference=abs(values[0]-values[1]), dimensionless_identity_tolerance=1e-9)
        reports.append(report)
        _require_frozen(old, new, 'split_'+str(fresh['split_rank']))
    if audit is not None:
        write_json(Path(audit)/('split_'+str(fresh['split_rank'])+'_IDENTITY_COMPARISON.json'), reports)


def _cache_contract(model):
    """Known-anchor state/layout only; contains no observation or target label."""
    adapter, problem = model.anchor.adapter, model.anchor.adapter.problem
    return dict(cache_schema=np.asarray('a22_stage_a_anchor_v1'),
        scene_id=np.asarray(problem.parent_id), anchor_material=model.anchor.chi,
        mesh_points=problem.points, cell_volume=np.asarray(problem.volume),
        wavenumber=np.asarray(problem.frequency), chart_Q=adapter.chart.Q,
        source_directions=problem.dirs, source_polarizations=problem.pols,
        receiver_positions=problem.receivers, receiver_basis=problem.obs_basis,
        source_order=np.arange(adapter.P), whitening=np.asarray(adapter.whitening),
        data_layout=np.asarray('source_major_real_then_imaginary'),
        material_layout=np.asarray('real_then_imaginary_volume_orthonormal'),
        anchor_configuration=np.asarray(model.anchor.cache_key.configuration))


def _validate_cache_contract(archive, model, *, legacy_members):
    contract = _cache_contract(model)
    present = set(archive.files)
    if not set(legacy_members) <= present:
        raise ResumeMismatch('A22_RESUME_MISSING_CACHE_MEMBERS')
    contract_present = present.intersection(contract)
    # Legacy label source_order predates the explicit state contract.
    legacy_contract = set(legacy_members).intersection(contract)
    if contract_present <= legacy_contract:
        if present != set(legacy_members):
            raise ResumeMismatch('A22_RESUME_UNRECOGNIZED_LEGACY_CACHE')
        return True
    if not set(contract) <= present:
        raise ResumeMismatch('A22_RESUME_INCOMPLETE_CACHE_CONTRACT')
    allowed = set(legacy_members) | set(contract) | {'backward_residual'}
    if present - allowed:
        raise ResumeMismatch('A22_RESUME_UNEXPECTED_CACHE_MEMBERS')
    for name, expected in contract.items():
        if np.asarray(expected).dtype.kind in 'US':
            if archive[name].shape != np.asarray(expected).shape or not np.array_equal(archive[name], expected):
                raise ResumeMismatch('A22_RESUME_CACHE_CONTRACT:' + name)
        else:
            _require_array(archive[name], expected, 'cache.'+name, rtol=1e-12)
    return False


def _verify_online_factors(path, model):
    with np.load(path, allow_pickle=False) as archive:
        if 'AW' not in archive.files:
            raise ResumeMismatch('A22_RESUME_MISSING_AW')
        relative_error = _require_array(archive['AW'], model.AW, 'AW')
        if 'cache_schema' in archive.files:
            _validate_cache_contract(archive, model, legacy_members=('AW', 'MW', 'PMW'))
    return relative_error


def _load_j_cache(path, model, book, *, online_verified):
    if not online_verified:
        raise ResumeMismatch('A22_RESUME_OFFLINE_BEFORE_ONLINE_FREEZE')
    sid = model.anchor.adapter.problem.parent_id
    with book.scope('offline_evaluation'), book.action_guard('full_J', role='offline_evaluation',
            scene_id=sid, purpose='OFFLINE same-anchor benchmark cache replay'):
        with book.span('a22_offline_J_cache_validation', offline_cache_reads=1, offline_J_cache_reads=1):
            with np.load(path, allow_pickle=False) as archive:
                legacy = _validate_cache_contract(archive, model, legacy_members=('JF',))
                JF = np.array(archive['JF'], copy=True)
            if JF.shape != model.AW.shape or np.iscomplexobj(JF) or not np.all(np.isfinite(JF)):
                raise ResumeMismatch('A22_RESUME_JF_NOT_FINITE_REAL')
        with book.span('a22_offline_J_cache_replay', offline_cache_hits=1, offline_J_cache_hits=1):
            pass
    return JF, legacy


def _load_label_cache(path, model, book, *, coefficients, perturbation_coefficients,
                      original_material, direction, nuisance, amplitude, online_verified):
    if not online_verified:
        raise ResumeMismatch('A22_RESUME_OFFLINE_BEFORE_ONLINE_FREEZE')
    adapter = model.anchor.adapter
    names = ('clean_data', 'coefficients', 'perturbation_coefficients', 'original_material',
             'direction', 'nuisance', 'amplitude', 'source_order')
    with book.scope('offline_label'), book.action_guard('truth', role='offline_label',
            scene_id=adapter.problem.parent_id, purpose='OFFLINE finite label cache replay'):
        with book.span('a22_offline_label_cache_validation', offline_cache_reads=1, offline_label_cache_reads=1):
            with np.load(path, allow_pickle=False) as archive:
                legacy = _validate_cache_contract(archive, model, legacy_members=names)
                for name, expected in dict(coefficients=coefficients,
                        perturbation_coefficients=perturbation_coefficients, original_material=original_material,
                        direction=direction, nuisance=nuisance, amplitude=np.asarray(amplitude),
                        source_order=np.arange(adapter.P)).items():
                    _require_array(archive[name], expected, 'label.'+name)
                raw = np.array(archive['clean_data'], copy=True)
                if raw.shape != (adapter.P, adapter.m) or not np.iscomplexobj(raw) or not np.all(np.isfinite(raw)):
                    raise ResumeMismatch('A22_RESUME_LABEL_DATA_LAYOUT')
                if not np.array_equal(archive['source_order'], np.arange(adapter.P)):
                    raise ResumeMismatch('A22_RESUME_LABEL_SOURCE_ORDER')
                if not legacy and 'backward_residual' not in archive.files:
                    raise ResumeMismatch('A22_RESUME_LABEL_MISSING_BACKWARD_RESIDUAL')
                backward = None if legacy else float(archive['backward_residual'])
                if backward is not None and (not np.isfinite(backward) or backward < 0 or backward > 1e-9):
                    raise ResumeMismatch('A22_RESUME_LABEL_BACKWARD_RESIDUAL')
        with book.span('a22_offline_label_cache_replay', offline_cache_hits=1, offline_label_cache_hits=1):
            pass
    return raw, dict(offline_cache_hit=True, legacy_cache=legacy, backward_residual=backward,
        label_origin='offline full Maxwell finite forward, paid cache replay',
        full_forward_calls=0, source_rhs=0,
        operator_cache_version_preserved=adapter._version == model.projection.material_version)


def _registered_case_rows(sid, direction_id, level_id, config):
    for intervention in config['interventions']:
        for noise in config['noise_levels']:
            for draw in range(1 if not noise else int(config['noise_draws'])):
                yield dict(scene_id=sid, direction_id=direction_id, amplitude_level=level_id,
                           noise_level=float(noise), noise_draw=draw, intervention=intervention)


def _validate_prior_cases(rows, sid, cases, config):
    registered = {}
    for case in cases:
        for amplitude in case['amplitudes']:
            for row in _registered_case_rows(sid, case['direction']['id'], amplitude['level_id'], config):
                registered[stage_a_case_key(row)] = (case['direction'], amplitude)
    for row in rows:
        if int(row['scene_id']) != int(sid):
            continue
        key = stage_a_case_key(row)
        if key not in registered:
            raise ResumeMismatch('A22_RESUME_PRIOR_CASE_NOT_REGISTERED')
        direction, amplitude = registered[key]
        _require_frozen(row['amplitude'], amplitude['amplitude'], 'prior_case.amplitude')
        _require_frozen(row['candidate_index'], direction['candidate_index'], 'prior_case.candidate_index')
        _require_frozen(row['evidence_scope'], 'deployable', 'prior_case.evidence_scope')
        seed = [config['master_seed'], sid, direction['id'], amplitude['level_id'], row['noise_draw'], 661]
        _require_frozen(row['noise_seed'], ':'.join(map(str, seed)), 'prior_case.noise_seed')


def _validate_complete_scene(out, sid, rows, config):
    """A COMPLETE summary alone cannot hide missing case evidence."""
    path = Path(out)/f'scene_{sid}'/'frozen_online_budgets.json'
    if not path.is_file():
        raise ResumeMismatch('A22_RESUME_COMPLETE_SCENE_MISSING_FREEZE')
    budgets = json.loads(path.read_text(encoding='utf-8'))
    expected = {stage_a_case_key(row) for budget in budgets
                for row in _registered_case_rows(sid, budget['direction_id'], budget['amplitude_level'], config)}
    if not expected:
        raise ResumeMismatch('A22_RESUME_COMPLETE_SCENE_EMPTY_FREEZE')
    actual = {stage_a_case_key(row) for row in rows if int(row['scene_id']) == int(sid)
              and _case_completed(row)}
    if expected != actual:
        raise ResumeMismatch('A22_RESUME_COMPLETE_SCENE_MISSING_CASES')


def _append(path, row):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(plain(row), allow_nan=False)+'\n')


def _csv(path, rows):
    if not rows:
        return
    names = list(dict.fromkeys(k for row in rows for k in row if not isinstance(row[k], (dict, list, np.ndarray))))
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=names, extrasaction='ignore')
        writer.writeheader()
        writer.writerows([{k: plain(v) for k, v in row.items() if k in names} for row in rows])


def finite_label(model, coefficients, book, *, material_center=None, purpose='direction_perturbation'):
    """A charged offline full forward; never changes the online operator."""
    adapter = model.anchor.adapter
    with book.scope('offline_label'), book.action_guard('perturbation_forward', role='offline_label',
                           scene_id=adapter.problem.parent_id, purpose=purpose):
        center = model.anchor.chi if material_center is None else np.asarray(material_center, complex)
        chi = center+adapter.chart.expand(np.asarray(coefficients, float))
        if np.min(chi.real)<-.5-1e-8 or np.min(chi.imag)<-1e-8:
            raise ValueError('REGISTERED_PERTURBATION_OUTSIDE_MATERIAL_DOMAIN')
        with book.span('a22_offline_finite_label', full_forward_calls=1, full_forward_RHS=adapter.P,
                       full_LU_factorizations=1, full_state_backward_residual_L_rhs=adapter.P,
                       full_state_receiver_rhs=adapter.P, full_state_Goff_rhs=adapter.P):
            state = adapter.model.state(chi)
            backward = float(state.source_residual())
            if backward>1e-9:
                raise ValueError('A22_LABEL_FULL_FORWARD_BACKWARD_RESIDUAL_FAILED')
            raw = state.field.copy()
    return raw, dict(backward_residual=backward, label_origin='offline full Maxwell finite forward',
                     full_forward_calls=1, source_rhs=adapter.P,
                     operator_cache_version_preserved=adapter._version==model.projection.material_version)


def _registered_perturbation(model, v, direction_id, config):
    rng = np.random.default_rng(np.random.SeedSequence([config['master_seed'],
         model.anchor.adapter.problem.parent_id, int(direction_id), 511]))
    v = np.asarray(v, float)
    n = rng.normal(size=32)
    n -= v*(v@n)
    n /= la.norm(n)
    direction = v+float(config['nuisance_fraction'])*n
    dc = model.anchor.adapter.chart.expand(direction)
    chi0 = model.anchor.chi
    maximum = float(config['physical_amplitude_max'])/max(float(np.max(abs(dc))), 1e-300)
    for component, lower in ((dc.real, -.5), (dc.imag, 0.)):
        negative = component<0
        values = chi0.real if lower<0 else chi0.imag
        if np.any(negative):
            maximum = min(maximum, float(np.min((values[negative]-lower)/(-component[negative]))))
    maximum *= float(config['feasible_amplitude_fraction'])
    if not np.isfinite(maximum) or maximum<=0:
        raise ValueError('NO_POSITIVE_REGISTERED_DIRECTION_AMPLITUDE')
    return n, direction, maximum


def _calibrate_data(raw):
    # Actual physical linear source amplitudes and correlated readout gains.
    # These signs belong to the evaluator, not the descriptor builder.
    p, m = raw.shape
    source = 1.+.05*np.cos(2.*np.pi*(np.arange(p)+.25)/p)
    receiver = 1.+.03*np.sin(2.*np.pi*(np.arange(m)+.125)/m)
    return raw*source[:, None]*receiver[None, :], dict(
        intervention='source_amplitude_5pct_receiver_gain_3pct',
        source_scale=source, receiver_scale=receiver,
        physical_origin='exact linear illumination amplitude and receiver calibration',
        random_factor_matrices=False, additional_Maxwell_forward_calls=0)


def _frozen_direction_cases(model, context, directions, descriptors, config, *, screening):
    """Same registered cases, finalized before the evaluator opens full J."""
    finite_count = int(config['finite_screening_directions'] if screening else
                       config['finite_expansion_directions'])
    cases = []
    for direction, descriptor in zip(directions[:finite_count], descriptors[:finite_count]):
        nuisance, joint, maximum = _registered_perturbation(model, direction['v'], direction['id'], config)
        amplitudes = []
        for level_id, fraction in enumerate(config['amplitude_fractions']):
            amp = maximum*float(fraction)
            predictions = {}
            for intervention in config['interventions']:
                for noise_level in config['noise_levels']:
                    predictions[(intervention, float(noise_level))] = predict_budget(
                        context, descriptor, amp, noise_level, intervention, config)
            amplitudes.append(dict(level_id=level_id, amplitude=amp, predictions=predictions))
        cases.append(dict(direction=direction, descriptor=descriptor, nuisance=nuisance,
                          joint=joint, amplitudes=amplitudes))
    return cases


def _freeze_budget_rows(cases):
    return [dict(direction_id=case['direction']['id'], amplitude=row['amplitude'],
                 amplitude_level=row['level_id'], full_J_read=False, label_read=False,
                 predictions=[dict(intervention=key[0], noise_level=key[1], **value)
                              for key, value in row['predictions'].items()])
            for case in cases for row in case['amplitudes']]


def _anchor_summary_backward_residual(anchor, book):
    cached = anchor.provenance.get('source_backward_residual')
    if cached is not None:
        return float(cached), 'charged_anchor_provenance'
    # The existing anchor contract validates this diagnostic but currently
    # does not expose its numeric value. Any additional request must be paid.
    with book.span('a22_anchor_summary_backward_residual',
                   full_state_backward_residual_L_rhs=anchor.adapter.P):
        return float(anchor.state.source_residual()), 'charged_summary_diagnostic'


def evaluate_recovery(model, observation, config, book, *, basis=None):
    """One deployable constrained material solve; the caller owns truth labels."""
    adapter = model.anchor.adapter
    d = adapter.whiten(pack(observation-model.anchor.state.field))
    A = model.AW if basis is None else model.AW@basis
    solution, qp, normal = constrained_material_solve(A, d, adapter.chart, model.anchor.chi,
        config, book, basis=basis)
    return solution, dict(qp=qp, data_residual=float(la.norm(model.AW@solution-d)),
                         one_material_subproblem=True, correction_events=0,
                         label_or_full_J_read=False, material_normal=normal)


def run_stage_a(root, config, book, *, device='cuda', screening=True, resume=False):
    root = Path(root)
    out = root/'results/a22/stage_a'
    out.mkdir(parents=True, exist_ok=True)
    ids = list(config['screening_scenes']) if screening else sum((list(config['splits'][name])
        for name in ('development', 'calibration', 'evaluation')), [])
    rows, split_rows, scene_rows = [], [], []
    prior_jsonl = out/'direction_metrics.jsonl'
    prior_scenes = out/'scene_metrics.jsonl'
    # Existing screening records are retained when the approved expansion runs.
    existing_ids = set()
    completed_keys = set()
    if resume:
        rows, split_rows, scene_rows, completed_keys, existing_ids = _restore_stage_a(out)
    elif not screening and prior_scenes.exists():
        existing = [json.loads(line) for line in prior_scenes.read_text().splitlines() if line.strip()]
        existing_ids = {int(row['scene_id']) for row in existing if row.get('status')=='COMPLETE'}
        scene_rows.extend(existing)
        if prior_jsonl.exists():
            rows.extend(json.loads(line) for line in prior_jsonl.read_text().splitlines() if line.strip())
        old = out/'split_metrics.jsonl'
        if old.exists():
            split_rows.extend(json.loads(line) for line in old.read_text().splitlines() if line.strip())
    for sid in ids:
        if sid in existing_ids:
            if resume:
                _validate_complete_scene(out, sid, rows, config)
            continue
        scene_start = time.perf_counter()
        scene_row = dict(scene_id=sid, status='STARTED', screening=screening)
        _append(out/'progress.jsonl', scene_row)
        try:
            with book.stage_scope('features' if not screening else 'screen_health'):
                scene = load_online_scene(sid, config, book,
                    stage_a_signal=not screening, explicit_authorization=not screening)
                anchor = build_anchor(scene, config, book, device=device)
                model = build_opm(anchor, config)
                context = build_descriptor_context(model, config)
                directions = choose_directions(model.AW, count=int(config['total_direction_descriptors']))
                descriptors = [direction_descriptor(context, d['v'], config) for d in directions]
                scene_dir = out/f'scene_{sid}'
                scene_dir.mkdir(parents=True, exist_ok=True)
                resume_audit = scene_dir/'resume_audits'/uuid.uuid4().hex if resume else None
                if resume:
                    resume_audit.mkdir(parents=True, exist_ok=False)
                    scene_row['resume_audit'] = str(resume_audit.relative_to(root))
                factor_path = scene_dir/'online_factors.npz'
                prior_cases = [row for row in rows if int(row['scene_id']) == int(sid)] if resume else []
                offline_exists = (scene_dir/'OFFLINE_J_benchmark.npz').exists() or any(scene_dir.glob('OFFLINE_label_*.npz'))
                if resume and (prior_cases or offline_exists):
                    required = ('online_factors.npz', 'online_provenance.json',
                                'frozen_online_directions.json', 'frozen_online_budgets.json')
                    if any(not (scene_dir/name).is_file() for name in required):
                        raise ResumeMismatch('A22_RESUME_INCOMPLETE_ONLINE_FREEZE')
                if resume and factor_path.exists():
                    with book.span('a22_resume_online_factor_check', resume_online_factor_checks=1):
                        np.savez_compressed(resume_audit/'regenerated_online_factors.npz',
                            AW=model.AW, MW=model.MW, PMW=model.PMW, **_cache_contract(model))
                        scene_row['resume_AW_relative_error'] = _verify_online_factors(factor_path, model)
                        write_json(resume_audit/'AW_COMPARISON.json', dict(
                            relative_error=scene_row['resume_AW_relative_error'], tolerance=1e-9,
                            original_preserved=True, online_only=True))
                else:
                    np.savez_compressed(factor_path, AW=model.AW, MW=model.MW, PMW=model.PMW,
                                        **_cache_contract(model))
                _freeze_json(scene_dir/'online_provenance.json', dict(
                    online=dict(scene.provenance), anchor=dict(anchor.provenance), opm=dict(model.provenance),
                    descriptor=dict(context.provenance), raw_data_label_access=False,
                    exact_background_assumed=[.1, .04], direction_selection_uses_truth=False), resume=resume, audit=resume_audit)
                # Freeze all direction choices and predictors before evaluation.
                frozen = []
                for d, desc in zip(directions, descriptors):
                    frozen.append(dict(id=d['id'], candidate_index=d['candidate_index'], v=d['v'],
                        origin=d['origin'], alpha=desc['alpha'], beta=desc['beta'], gamma=desc['gamma'],
                        profile_g=desc['profile_g'], attribution=desc['attribution'],
                        dual_defect_norm=desc['dual_defect_norm'], IR_direction_norm=desc['IR_direction_norm'],
                        full_J_read=False, label_read=False))
                _freeze_json(scene_dir/'frozen_online_directions.json', frozen, resume=resume, audit=resume_audit)
                for rank in config['split_ranks']:
                    split = build_split(model, context.provenance, config, rank=rank)
                    sr = dict(scene_id=sid, family=scene.family, split_rank=rank,
                        status=split.status, actual_current_rank=model.basis.shape[1],
                        **split.certificate)
                    old_splits = [row for row in split_rows if row.get('scene_id') == sid and row.get('split_rank') == rank] if resume else []
                    if old_splits:
                        _validate_split_rows(old_splits, sr, audit=resume_audit)
                    else:
                        split_rows.append(sr)
                        _append(out/'split_metrics.jsonl', sr)
                    split_path = scene_dir/f'online_split_{rank}.npz'
                    if resume and split_path.exists():
                        with np.load(split_path, allow_pickle=False) as archive:
                            for name, value in dict(V_phys=split.Vp, V_prior=split.Vrem, D=split.D).items():
                                _require_array(archive[name], value, 'split.'+name)
                    else:
                        np.savez_compressed(split_path, V_phys=split.Vp, V_prior=split.Vrem, D=split.D)
            with book.stage_scope('direction'):
                cases = _frozen_direction_cases(model, context, directions, descriptors, config,
                                               screening=screening)
                with book.span('a22_online_budget_freeze', online_budget_freezes=1):
                    _freeze_json(scene_dir/'frozen_online_budgets.json', _freeze_budget_rows(cases),
                                 resume=resume, audit=resume_audit)
                if resume:
                    _validate_prior_cases(prior_cases, sid, cases, config)
                online_verified = True
                from .offline_assets import load_evaluation_truth
                center = load_evaluation_truth(root, sid, book)
                base_coeff = anchor.adapter.chart.project(center-anchor.chi)
                outside = center-anchor.chi-anchor.adapter.chart.expand(base_coeff)
                outside_norm = np.sqrt(anchor.adapter.problem.volume)*float(la.norm(outside))
                base_norm = np.sqrt(anchor.adapter.problem.volume)*float(la.norm(center-anchor.chi))
                prior_valid = float(np.max(abs(center-anchor.chi))) <= float(config.get('descriptor_material_pointwise_prior', .25))
                write_json(scene_dir/'OFFLINE_material_model_audit.json', dict(
                    label_center='actual original scene material on solver grid, offline only',
                    base_material_norm=base_norm, W_external_material_norm=outside_norm,
                    W_retained_energy_fraction=float(la.norm(base_coeff)**2/base_norm**2) if base_norm else None,
                    declared_prior_contains_original_center=prior_valid,
                    maximum_original_material_perturbation=float(np.max(abs(center-anchor.chi))),
                    absolute_32_coordinate_errors_are_labels=True,
                    object_observation_generation_grid=scene.geometry.get('truth_n'),
                    new_finite_label_grid=scene.geometry.get('n'),
                    original_cached_data_not_used_as_exact_same_grid_label=True))
                j_path = scene_dir/'OFFLINE_J_benchmark.npz'
                if resume and j_path.exists():
                    JF, legacy_j = _load_j_cache(j_path, model, book, online_verified=online_verified)
                    scene_row['resume_legacy_J_cache'] = legacy_j
                else:
                    with book.scope('offline_evaluation'), book.action_guard('full_J', role='offline_evaluation', scene_id=sid,
                                           purpose='OFFLINE total sensitivity / SVD benchmark'):
                        with book.span('a22_offline_full_J_benchmark', offline_J_builds=1):
                            JF = anchor.adapter.full_tangent_action(anchor.chi, anchor.state, np.eye(32))
                    np.savez_compressed(j_path, JF=JF, **_cache_contract(model))
                full_inverse = la.solve(JF.T@JF+context.lambda_value*np.eye(32), JF.T, assume_a='pos')
                finite_count = int(config['finite_screening_directions'] if screening else config['finite_expansion_directions'])
                scene_failures = sum(row.get('status') != 'OK' for row in prior_cases) if resume else 0
                for case in cases:
                    direction, descriptor = case['direction'], case['descriptor']
                    n, joint = case['nuisance'], case['joint']
                    v = direction['v']
                    full_witness = profiled_witness(JF, v)
                    hF = v@full_inverse
                    htotal = (JF@v)/(float(la.norm(JF@v))**2+context.lambda_value)
                    for amplitude_case in case['amplitudes']:
                        level_id, amp = amplitude_case['level_id'], amplitude_case['amplitude']
                        perturbation_coeff = amp*joint
                        true_coeff = base_coeff+perturbation_coeff
                        predictions = amplitude_case['predictions']
                        case_rows = list(_registered_case_rows(sid, direction['id'], level_id, config))
                        if resume and all(stage_a_case_key(row) in completed_keys for row in case_rows):
                            with book.span('a22_resume_completed_amplitude_skip', resume_completed_QP_skips=len(case_rows)):
                                pass
                            continue
                        label_path = scene_dir/f'OFFLINE_label_d{direction["id"]}_a{level_id}.npz'
                        if resume and label_path.exists():
                            raw, label_meta = _load_label_cache(label_path, model, book,
                                coefficients=true_coeff, perturbation_coefficients=perturbation_coeff,
                                original_material=center, direction=v, nuisance=n, amplitude=amp,
                                online_verified=online_verified)
                        else:
                            raw, label_meta = finite_label(model, perturbation_coeff, book, material_center=center)
                            np.savez_compressed(label_path, clean_data=raw, coefficients=true_coeff,
                                perturbation_coefficients=perturbation_coeff, original_material=center,
                                direction=v, nuisance=n, amplitude=amp,
                                backward_residual=label_meta['backward_residual'], **_cache_contract(model))
                        for intervention in config['interventions']:
                            if intervention=='nominal':
                                clean = raw
                            else:
                                with book.span('a22_physical_calibration_intervention', calibration_transformations=1):
                                    clean, intervention_meta = _calibrate_data(raw)
                                    write_json(scene_dir/f'calibration_d{direction["id"]}_a{level_id}.json', intervention_meta)
                            for noise_level in config['noise_levels']:
                                draws = 1 if not noise_level else int(config['noise_draws'])
                                prediction = predictions[(intervention, float(noise_level))]
                                for draw in range(draws):
                                    key = stage_a_case_key(dict(scene_id=sid, direction_id=direction['id'],
                                        amplitude_level=level_id, noise_level=float(noise_level),
                                        noise_draw=draw, intervention=intervention))
                                    if resume and key in completed_keys:
                                        with book.span('a22_resume_completed_QP_skip', resume_completed_QP_skips=1):
                                            pass
                                        continue
                                    seed = [config['master_seed'], sid, direction['id'], level_id, draw, 661]
                                    rng = np.random.default_rng(np.random.SeedSequence(seed))
                                    # Same realized noise for nominal/intervention, paired evaluation.
                                    noise = float(noise_level)*model.sigma_complex/np.sqrt(2.)*(
                                        rng.normal(size=clean.shape)+1j*rng.normal(size=clean.shape))
                                    observation = clean+noise
                                    row = dict(scene_id=sid, family=scene.family, split='screening' if screening else
                                        next(name for name, values in config['splits'].items() if sid in values),
                                        direction_id=direction['id'], candidate_index=direction['candidate_index'],
                                        amplitude=amp, amplitude_level=level_id, noise_level=float(noise_level), noise_draw=draw,
                                        noise_seed=':'.join(map(str, seed)), intervention=intervention,
                                        actual_current_rank=model.basis.shape[1], actual_rank=model.basis.shape[1],
                                        alpha=descriptor['alpha'], beta=descriptor['beta'], gamma=descriptor['gamma'],
                                        attribution=descriptor['attribution'], profile_g=descriptor['profile_g'],
                                        dual_defect=descriptor['dual_defect_norm'],
                                        full_J_total_gain=float(la.norm(JF@v)), full_J_profile_g=full_witness['g'],
                                        full_J_attribution=full_witness['attribution'],
                                         full_J_tangent_error=float(la.norm((JF-model.AW)@v))/max(float(la.norm(JF@v)),1e-300),
                                         full_J_scope='OFFLINE benchmark only',
                                         online_predictions_frozen_before_offline_full_J=True,
                                        truth_origin='OFFLINE original material plus registered W perturbation',
                                        feature_origin='ONLINE known-background shallow OPM residuals only',
                                        evidence_scope='deployable',
                                        label_origin='OFFLINE original object finite Maxwell data, nuisance joint 32-coordinate solve',
                                        declared_object_prior_contains_center=prior_valid,
                                        W_external_material_norm=outside_norm, original_material_norm=base_norm,
                                        historical_exposed=True, status='OK', finite_domain_feasible=True,
                                        **{k:value for k,value in prediction.items() if not isinstance(value, dict)})
                                    if resume:
                                        row.update(resume_label_cache_hit=label_meta.get('offline_cache_hit', False),
                                                   resume_legacy_label_cache=label_meta.get('legacy_cache', False))
                                    try:
                                        solution, result = evaluate_recovery(model, observation, config, book)
                                        error = float(abs(v@(solution-true_coeff)))
                                        row.update(coefficient_error=error, true_error=error,
                                            relative_true_error=error/max(abs(float(v@true_coeff)),config['material_absolute_floor']),
                                            raw_target_coefficient=float(v@true_coeff), perturbation_amplitude=amp,
                                            material_error=float(la.norm(solution-true_coeff)),
                                            coefficient_signed_error=float(v@(solution-true_coeff)),
                                            kkt_relative=result['qp']['kkt_relative'], feasibility=result['qp']['feasibility_violation'])
                                        backF = JF.T@hF-v
                                        biasF = context.declared_object_radius*la.norm(backF)+amp*(abs(backF@v)+config['nuisance_fraction']*la.norm(backF-v*(backF@v)))
                                        row['pred_full_J'] = float(np.sqrt((float(noise_level)*la.norm(hF))**2+biasF**2))
                                        row['pred_full_J_total'] = float(np.sqrt((float(noise_level)*la.norm(htotal))**2+
                                            ((context.declared_object_radius+amp)*context.lambda_value/(la.norm(JF@v)**2+context.lambda_value))**2))
                                    except QPFailure as exc:
                                        scene_failures += 1
                                        row.update(status='INVALID_QP', coefficient_error=None, true_error=None,
                                                   failure=str(exc), qp_audit=getattr(exc,'result',None))
                                        _append(root/'results/a22/FAILURE_LEDGER.jsonl', row)
                                    rows.append(row)
                                    _append(prior_jsonl, row)
                                    if resume and _case_completed(row):
                                        completed_keys.add(key)
                                    book.check()
                        _csv(out/'direction_metrics.csv', rows)
                backward, backward_origin = _anchor_summary_backward_residual(anchor, book)
                scene_row.update(status='COMPLETE', family=scene.family, actual_rank=model.basis.shape[1],
                    direction_count=finite_count, invalid_QPs=scene_failures,
                    full_J_condition=float(la.svdvals(JF)[0]/la.svdvals(JF)[-1]),
                    shallow_A_condition=float(la.svdvals(model.AW)[0]/la.svdvals(model.AW)[-1]),
                    source_backward_residual=backward, source_backward_residual_origin=backward_origin,
                    descriptor_certificate=context.provenance['certificate_type'])
            del descriptors, context, model, anchor, JF, full_inverse, cases
            gc.collect()
            if device=='cuda':
                import torch
                torch.cuda.empty_cache()
        except BaseException as exc:
            scene_row.update(status='FAILED', error_type=type(exc).__name__, error=str(exc))
            _append(root/'results/a22/FAILURE_LEDGER.jsonl', scene_row)
            scene_rows.append(scene_row)
            _append(prior_scenes, scene_row)
            _csv(out/'direction_metrics.csv', rows)
            _csv(out/'split_metrics.csv', split_rows)
            _csv(out/'scene_metrics.csv', scene_rows)
            raise
        scene_row['inclusive_scene_wall_seconds'] = time.perf_counter()-scene_start
        scene_rows.append(scene_row)
        _append(prior_scenes, scene_row)
        _csv(out/'scene_manifest.csv', scene_rows)
        _csv(out/'scene_metrics.csv', scene_rows)
    _csv(out/'direction_metrics.csv', rows)
    _csv(out/'split_metrics.csv', split_rows)
    write_json(out/'RUN_SUMMARY.json', dict(status='COMPLETE', scene_count=len(scene_rows),
        scenes=scene_rows, screening=screening, invalid_count=sum(r['status']!='OK' for r in rows),
        observations=len(rows), full_J_scope='OFFLINE benchmark, never online prediction',
        actual_label_calls=book.counts.get('data_generation_F_calls',0),
        information_boundary='predictors and direction selection frozen before offline labels'))
    return dict(status='COMPLETE', screening=screening, scene_count=len(scene_rows), rows=len(rows))
