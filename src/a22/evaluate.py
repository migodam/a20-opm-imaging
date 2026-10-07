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

import numpy as np
from scipy import linalg as la

from a20.backend import pack
from a20.costs import BudgetExceeded, plain, write_json
from a20.material import QPFailure
from .assets import load_online_scene
from .core import build_split, choose_directions, constrained_material_solve, profiled_witness
from .features import build_descriptor_context, direction_descriptor, predict_budget
from .online import build_anchor, build_opm


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


def run_stage_a(root, config, book, *, device='cuda', screening=True):
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
    if not screening and prior_scenes.exists():
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
                np.savez_compressed(scene_dir/'online_factors.npz', AW=model.AW, MW=model.MW, PMW=model.PMW)
                write_json(scene_dir/'online_provenance.json', dict(
                    online=dict(scene.provenance), anchor=dict(anchor.provenance), opm=dict(model.provenance),
                    descriptor=dict(context.provenance), raw_data_label_access=False,
                    exact_background_assumed=[.1, .04], direction_selection_uses_truth=False))
                # Freeze all direction choices and predictors before evaluation.
                frozen = []
                for d, desc in zip(directions, descriptors):
                    frozen.append(dict(id=d['id'], candidate_index=d['candidate_index'], v=d['v'],
                        origin=d['origin'], alpha=desc['alpha'], beta=desc['beta'], gamma=desc['gamma'],
                        profile_g=desc['profile_g'], attribution=desc['attribution'],
                        dual_defect_norm=desc['dual_defect_norm'], IR_direction_norm=desc['IR_direction_norm'],
                        full_J_read=False, label_read=False))
                write_json(scene_dir/'frozen_online_directions.json', frozen)
                for rank in config['split_ranks']:
                    split = build_split(model, context.provenance, config, rank=rank)
                    sr = dict(scene_id=sid, family=scene.family, split_rank=rank,
                        status=split.status, actual_current_rank=model.basis.shape[1],
                        **split.certificate)
                    split_rows.append(sr)
                    _append(out/'split_metrics.jsonl', sr)
                    np.savez_compressed(scene_dir/f'online_split_{rank}.npz', V_phys=split.Vp,
                                        V_prior=split.Vrem, D=split.D)
            with book.stage_scope('direction'):
                cases = _frozen_direction_cases(model, context, directions, descriptors, config,
                                               screening=screening)
                with book.span('a22_online_budget_freeze', online_budget_freezes=1):
                    write_json(scene_dir/'frozen_online_budgets.json', _freeze_budget_rows(cases))
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
                with book.scope('offline_evaluation'), book.action_guard('full_J', role='offline_evaluation', scene_id=sid,
                                       purpose='OFFLINE total sensitivity / SVD benchmark'):
                    with book.span('a22_offline_full_J_benchmark', offline_J_builds=1):
                        JF = anchor.adapter.full_tangent_action(anchor.chi, anchor.state, np.eye(32))
                np.savez_compressed(scene_dir/'OFFLINE_J_benchmark.npz', JF=JF)
                full_inverse = la.solve(JF.T@JF+context.lambda_value*np.eye(32), JF.T, assume_a='pos')
                finite_count = int(config['finite_screening_directions'] if screening else config['finite_expansion_directions'])
                scene_failures = 0
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
                        raw, label_meta = finite_label(model, perturbation_coeff, book, material_center=center)
                        np.savez_compressed(scene_dir/f'OFFLINE_label_d{direction["id"]}_a{level_id}.npz',
                            clean_data=raw, coefficients=true_coeff, perturbation_coefficients=perturbation_coeff,
                            original_material=center, direction=v, nuisance=n,
                            amplitude=amp, source_order=np.arange(6))
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
                                        label_origin='OFFLINE original object finite Maxwell data, nuisance joint 32-coordinate solve',
                                        declared_object_prior_contains_center=prior_valid,
                                        W_external_material_norm=outside_norm, original_material_norm=base_norm,
                                        historical_exposed=True, status='OK', finite_domain_feasible=True,
                                        **{k:value for k,value in prediction.items() if not isinstance(value, dict)})
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
