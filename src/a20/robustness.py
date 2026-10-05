"""Conditionally invoked, bounded noise and warm-timing evidence collection.

The parent CLI owns quality gates and remaining-budget authorization. Importing
this module performs no experiment. It neither makes a scientific decision nor
enlarges the frozen matrices (24 noise attempts, 12 warm attempts, retries included).
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace
import json
from pathlib import Path
import re
import time

import numpy as np

from .costs import BudgetExceeded, plain, write_json

NOISE_PARENTS = (2007, 2010)
FROZEN_PARENTS = (2001, 2005, 2003, 2007, 2010, 2013)
NOISE_LEVELS = (.01, .03)
GOOD_RUN_STATUSES = {'CAPPED', 'CONVERGED_FULL_KKT'}
HELD_RECEIVER_GAP = {
    'status': 'NOT_RUN',
    'reason': 'The registered load_problem runtime contract has no held receiver geometry/observations; no external input or offline label is used to invent one.',
}


def _dependencies():
    # CLI imports this module when dispatching these optional stages.
    from .backend import Adapter, load_problem, pack
    from .imaging import reconstruct
    from .cli import append_jsonl, truth_metrics
    return Adapter, load_problem, pack, reconstruct, append_jsonl, truth_metrics


def _read_rows(path):
    if not path.exists():
        return []
    rows = []
    for number, text in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        if text.strip():
            row = json.loads(text)
            if not isinstance(row, dict):
                raise ValueError(f'Invalid retained result object at {path}:{number}')
            rows.append(row)
    return rows


def _token(value):
    return re.sub(r'[^A-Za-z0-9_.-]+', '_', str(value))


def _selection(config, chosen_method, chosen_degree, chosen_mode):
    if chosen_method == 'FULL_GN' or not (str(chosen_method).startswith('OPM') or chosen_method in ('SOM', 'KRYLOV')):
        raise ValueError('The selected comparator must be an existing non-full imaging method')
    if isinstance(chosen_degree, bool) or int(chosen_degree) != chosen_degree or not 0 <= int(chosen_degree) <= 5:
        raise ValueError('Selected degree must be a frozen integer 0..5')
    if chosen_mode not in ('A1', 'A2'):
        raise ValueError('Selected imaging mode must be A1 or A2')
    parents = list(config['parents'])
    if len(parents) != len(set(parents)) or not set(parents).issubset(FROZEN_PARENTS):
        raise ValueError('This optional implementation cannot introduce new or duplicate parents')
    return parents


def _snapshot(book):
    # No budget-checking accessor here: failure epilogues must still retain the
    # already charged counters after a BudgetExceeded raised inside an attempt.
    return {'counts': dict(book.counts), 'exclusive_walls': dict(book.walls)}


@contextmanager
def _metadata(book, **values):
    old = dict(book.metadata)
    book.metadata.update(values)
    try:
        yield
    finally:
        book.metadata.clear()
        book.metadata.update(old)


def _manifest(dest, spec):
    path = dest/'manifest.json'
    if path.exists():
        previous = json.loads(path.read_text(encoding='utf-8'))
        if previous != plain(spec):
            raise ValueError('Retained optional-stage manifest differs; no silent rescope or matrix expansion')
    else:
        write_json(path, spec)


def _fixed_radius_noise(clean_data, level, seed):
    """Circular normal direction, then fixed global relative-radius scaling."""
    clean = np.asarray(clean_data, complex)
    norm = float(np.linalg.norm(clean))
    if not np.isfinite(norm) or norm <= 0:
        raise ValueError('Noise relative radius is undefined for zero/nonfinite clean data norm')
    if level not in NOISE_LEVELS:
        raise ValueError('Only frozen relative noise levels 0.01/0.03 are permitted')
    rng = np.random.default_rng(np.random.SeedSequence(seed))
    direction = (rng.normal(size=clean.shape)+1j*rng.normal(size=clean.shape))/np.sqrt(2.)
    radius = float(np.linalg.norm(direction))
    if not np.isfinite(radius) or radius <= 0:
        raise ValueError('Invalid circular noise direction norm')
    noise = direction*(float(level)*norm/radius)
    noise_norm = float(np.linalg.norm(noise))
    return noise, clean+noise, {
        'clean_global_data_norm': norm, 'noise_global_data_norm': noise_norm,
        'achieved_relative_noise_norm': noise_norm/norm,
        'achieved_SNR_db': float(20*np.log10(norm/noise_norm)),
        'noise_seed': list(seed), 'noise_level': float(level),
        'noise_distribution': 'circular complex normal direction followed by fixed global radius scaling',
        'fixed_norm_rescaling_is_not_independent_Gaussian_likelihood': True,
    }


def _save_or_check_draw(path, noise, noisy_data, metadata, scale):
    allowed = {'noise', 'data_noisy', 'seed', 'noise_level', 'clean_scale',
               'achieved_relative_noise_norm', 'achieved_SNR_db'}
    if path.exists():
        with np.load(path, allow_pickle=False) as saved:
            if set(saved.files) != allowed:
                raise ValueError('Noise observation archive has unregistered keys')
            if (not np.array_equal(saved['seed'], metadata['noise_seed'])
                    or not np.array_equal(saved['noise'], noise)
                    or not np.array_equal(saved['data_noisy'], noisy_data)
                    or float(saved['clean_scale']) != float(scale)
                    or float(saved['noise_level']) != metadata['noise_level']
                    or float(saved['achieved_relative_noise_norm']) != metadata['achieved_relative_noise_norm']
                    or float(saved['achieved_SNR_db']) != metadata['achieved_SNR_db']):
                raise ValueError('Retained observation draw or clean scaling changed; no silent replacement')
        return 'REUSED_IDENTICAL_OBSERVATION_DRAW'
    np.savez_compressed(path, noise=noise, data_noisy=noisy_data,
                        seed=np.asarray(metadata['noise_seed'], dtype=np.int64),
                        noise_level=metadata['noise_level'], clean_scale=float(scale),
                        achieved_relative_noise_norm=metadata['achieved_relative_noise_norm'],
                        achieved_SNR_db=metadata['achieved_SNR_db'])
    return 'SAVED_OBSERVATIONS_ONLY'


def _key(parent, method, degree, mode, level=None, realization=None):
    return json.dumps([int(parent), str(method), int(degree), str(mode), level, realization], separators=(',', ':'))


def _pending(key, attempts, results, retry_failed):
    seen = [row for row in attempts if row.get('attempt_key') == key]
    returned = [row for row in results if row.get('attempt_key') == key]
    if not seen and not returned:
        return True
    if not retry_failed:
        return False
    # An explicitly requested retry still consumes the SAME overall cap.
    return not any(row.get('status') in GOOD_RUN_STATUSES for row in returned)


def _native_snapshot(adapter):
    values = adapter.model.counters.as_dict()
    return {'totals': dict(values.get('totals', {})), 'timings_s': dict(values.get('timings_s', {})),
            'event_count': values.get('event_count', 0)}


def _native_delta(after, before):
    return {'totals': {k: v-before['totals'].get(k, 0) for k, v in after['totals'].items()},
            'timings_s': {k: v-before['timings_s'].get(k, 0.) for k, v in after['timings_s'].items()},
            'event_count': after['event_count']-before['event_count']}


def _clear_material_cache(adapter):
    """Keep static Goff/GS/receiver SVD only, never a previous state's LU/J/B."""
    for name in ('_full_cache', '_operator_chi', '_operator_L', '_operator_gpu'):
        if not hasattr(adapter, name):
            raise ValueError('Warm adapter contract changed: missing material cache field '+name)
        setattr(adapter, name, None)
    adapter._version += 1
    # DenseDDA._Solver returns LU factors to DDAState and does not cache them.
    # Clearing the state's owner removes access to those factors for the next run.


def _attempt(root, config, book, device, deps, problem, method, degree, mode,
             dest, run_id, base, stage, adapter=None, clean_data=None):
    _, _, pack, reconstruct, append_jsonl, truth_metrics = deps
    before = _snapshot(book)
    wall_start = time.perf_counter()
    native_before = _native_snapshot(adapter) if adapter is not None else None
    row = dict(base)
    raised = None
    row.update(run_id=run_id, parent_object_id=problem.parent_id, method=method,
               degree=degree if method != 'FULL_GN' else None, mode=mode,
               comparison_chosen_mode=base['comparison_chosen_mode'],
               source_commit=book.metadata.get('source_commit'),
               reconstruction_started=False, held_truth_receiver_residual=dict(HELD_RECEIVER_GAP))
    try:
        with _metadata(book, run_id=run_id, parent_object_id=problem.parent_id, method=method,
                       robustness_stage=stage, mode=mode), book.scope('online_'+stage):
            with book.span(stage+'_reconstruction_attempt', **{stage+'_reconstruction_attempts': 1}):
                row['reconstruction_started'] = True
                x, result, iterations, used_adapter = reconstruct(
                    problem, config, book, device, method=method, degree=degree, mode=mode,
                    adapter=adapter, experiment_id=run_id,
                    iteration_sink=lambda value: append_jsonl(dest/'iterations.jsonl', {**value, 'run_id': run_id, **base}))
        row.update(result)
        row.update(base, run_id=run_id, reconstruction_started=True,
                   online_reconstruction_status=result.get('status'))
        with _metadata(book, run_id=run_id, parent_object_id=problem.parent_id, method=method), book.scope('offline_'+stage+'_evaluation'):
            if clean_data is not None:
                with book.span('noise_clean_noisy_residual_metrics'):
                    # This state was paid by reconstruct. A missing same-x cache
                    # invokes an explicitly counted full solve, never an oracle.
                    state = used_adapter.full_state(x, reuse=True)
                    raw_clean = state.field-clean_data
                    raw_noisy = state.field-problem.data
                    row.update(final_clean_data_residual_norm=float(np.linalg.norm(raw_clean)),
                               final_noisy_data_residual_norm=float(np.linalg.norm(raw_noisy)),
                               final_clean_whitened_residual_norm=float(np.linalg.norm(used_adapter.whiten(pack(raw_clean)))),
                               final_noisy_whitened_residual_norm=float(np.linalg.norm(used_adapter.whiten(pack(raw_noisy)))),
                               residual_metric_state='same-x final full state, paid by reconstruction or explicitly counted metric solve')
            with book.span(stage+'_offline_truth_metrics'):
                row.update(truth_metrics(root, problem.parent_id, x, config))
        row['offline_evaluation_status'] = 'COMPLETE'
    except BaseException as exc:
        row.setdefault('online_reconstruction_status', row.get('status'))
        row.update(status='BUDGET_STOP' if isinstance(exc, BudgetExceeded) else 'INTERRUPTED' if not isinstance(exc, Exception) else 'FAILED_EXCEPTION',
                   failure=type(exc).__name__+': '+str(exc),
                   attempt_elapsed_wall_seconds=time.perf_counter()-wall_start)
        row.setdefault('offline_evaluation_status', 'NOT_COMPLETED')
        if isinstance(exc, BudgetExceeded) or not isinstance(exc, Exception):
            raised = exc
    finally:
        if adapter is not None:
            row['native_DDA_counters_delta_for_this_run'] = _native_delta(_native_snapshot(adapter), native_before)
            row['native_DDA_counters_in_reconstruct_are_cumulative_for_shared_static_model'] = True
        row['attempt_cost_including_wrapper_and_offline_evaluation'] = book.delta(before)
        row['held_truth_receiver_residual'] = dict(HELD_RECEIVER_GAP)
        row['offline_labels_access_scope'] = 'truth_metrics called only after reconstruct returned; never supplied to online problem/basis'
        row['science_judgment'] = 'NOT_COMPUTED_PARENT_OWNED'
    return plain(row), raised


def run_noise(root, config, book, device, job, chosen_method, chosen_degree, chosen_mode):
    """At most 24 total attempts: 2 parents x 2 levels x 3 draws x 2 methods."""
    root = Path(root)
    parents = _selection(config, chosen_method, chosen_degree, chosen_mode)
    if not set(NOISE_PARENTS).issubset(parents):
        raise ValueError('Frozen noise parents 2007/2010 must be in the declared runtime parent scope')
    deps = _dependencies()
    _, load_problem, _, _, append_jsonl, _ = deps
    dest = root/'results/noise'
    dest.mkdir(parents=True, exist_ok=True)
    _manifest(dest, {'stage': 'noise', 'parents': list(NOISE_PARENTS), 'levels': list(NOISE_LEVELS),
                     'realizations': [0, 1, 2], 'master_seed': config['master_seed'],
                     'chosen_method': chosen_method, 'chosen_degree': int(chosen_degree), 'chosen_mode': chosen_mode,
                     'attempt_cap_including_failures_and_explicit_retries': 24,
                     'invocation_gate_owner': 'parent CLI', 'split': 'historically_exposed_feasibility'})
    attempts = _read_rows(dest/'attempts.jsonl')
    results = _read_rows(dest/'runs.jsonl')
    retry = bool(config.get('robustness_retry_failed', False))
    methods = [('FULL_GN', 0, 'A1'), (chosen_method, int(chosen_degree), chosen_mode)]
    attempted_now, retained_failures = 0, []
    for parent in NOISE_PARENTS:
        pending = [(level, realization, method, degree, mode)
                   for level in NOISE_LEVELS for realization in range(3) for method, degree, mode in methods
                   if _pending(_key(parent, method, degree, mode, level, realization), attempts, results, retry)]
        if not pending:
            continue
        if len(attempts) >= 24:
            break
        try:
            with _metadata(book, parent_object_id=parent), book.scope('online_noise_preparation'), book.span('noise_runtime_observation_input', noise_runtime_reads=1):
                clean_problem = load_problem(root/f'data/runtime/{parent}/problem.npz')
        except BaseException as exc:
            append_jsonl(dest/'preparation.jsonl', {'job': job, 'parent_object_id': parent, 'status': 'FAILED', 'failure': type(exc).__name__+': '+str(exc)})
            if isinstance(exc, BudgetExceeded) or not isinstance(exc, Exception):
                raise
            for level, realization, method, degree, mode in pending:
                row = {'job': job, 'parent_object_id': parent, 'method': method, 'mode': mode,
                       'degree': degree, 'noise_level': level, 'realization': realization,
                       'attempt_key': _key(parent, method, degree, mode, level, realization),
                       'status': 'NOT_RUN_RUNTIME_INPUT_FAILED', 'failure': type(exc).__name__+': '+str(exc),
                       'reconstruction_started': False, 'held_truth_receiver_residual': dict(HELD_RECEIVER_GAP)}
                append_jsonl(dest/'runs.jsonl', row); results.append(row); retained_failures.append(row)
            continue
        for level in NOISE_LEVELS:
            for realization in range(3):
                pair = [(method, degree, mode) for method, degree, mode in methods
                        if _pending(_key(parent, method, degree, mode, level, realization), attempts, results, retry)]
                if not pair or len(attempts) >= 24:
                    continue
                seed = [config['master_seed'], parent, int(level*100), realization, 909]
                draw_file = dest/f'noise_draw_p{parent}_level{int(level*100):02d}_r{realization}.npz'
                before_draw = _snapshot(book)
                draw_started = time.perf_counter()
                try:
                    with _metadata(book, parent_object_id=parent, noise_level=level, realization=realization), book.scope('online_noise_observation_preparation'), book.span('noise_fixed_radius_draw', noise_draw_preparations=1):
                        noise, noisy_data, noise_meta = _fixed_radius_noise(clean_problem.data, level, seed)
                        archive_status = _save_or_check_draw(draw_file, noise, noisy_data, noise_meta, clean_problem.scale)
                except BaseException as exc:
                    append_jsonl(dest/'preparation.jsonl', {'job': job, 'parent_object_id': parent, 'noise_level': level,
                                 'realization': realization, 'status': 'FAILED', 'failure': type(exc).__name__+': '+str(exc),
                                 'cost': book.delta(before_draw)})
                    if isinstance(exc, BudgetExceeded) or not isinstance(exc, Exception):
                        raise
                    for method, degree, mode in pair:
                        row = {'job': job, 'parent_object_id': parent, 'method': method, 'mode': mode, 'degree': degree,
                               'noise_level': level, 'realization': realization,
                               'attempt_key': _key(parent, method, degree, mode, level, realization),
                               'status': 'NOT_RUN_DRAW_PREPARATION_FAILED', 'failure': type(exc).__name__+': '+str(exc),
                               'reconstruction_started': False, 'held_truth_receiver_residual': dict(HELD_RECEIVER_GAP)}
                        append_jsonl(dest/'runs.jsonl', row); results.append(row); retained_failures.append(row)
                    continue
                append_jsonl(dest/'draw_receipts.jsonl', {'job': job, 'parent_object_id': parent, 'realization': realization,
                             **noise_meta, 'draw_file': str(draw_file), 'archive_status': archive_status,
                             'wall_seconds': time.perf_counter()-draw_started, 'cost': book.delta(before_draw),
                             'paired_methods': [method for method, _, _ in pair], 'observation_only_archive': True})
                # Replacing only measured data preserves original clean scale,
                # geometry, init, and material chart; no truth field can enter.
                noisy_problem = replace(clean_problem, data=noisy_data.copy())
                for method, degree, mode in pair:
                    if len(attempts) >= 24:
                        break
                    run_id = f'{_token(job)}_noise_p{parent}_l{int(level*100)}_r{realization}_{_token(method)}_attempt{len(attempts)+1}'
                    base = {'job': job, 'attempt_key': _key(parent, method, degree, mode, level, realization),
                            'realization': realization, 'comparison_chosen_mode': chosen_mode, **noise_meta,
                            'noise_draw_file': str(draw_file), 'original_clean_scale': float(clean_problem.scale),
                            'whitening_policy': 'unchanged original clean-data scale, not a recalibrated Gaussian covariance',
                            'paired_observation_draw': True, 'full_reference_mode': 'A1',
                            'split': 'historically_exposed_feasibility'}
                    marker = {**base, 'run_id': run_id, 'parent_object_id': parent, 'method': method, 'degree': degree,
                              'mode': mode, 'status': 'ATTEMPT_REQUESTED', 'job': job}
                    append_jsonl(dest/'attempts.jsonl', marker); attempts.append(marker)
                    book.counts['noise_attempt_requests_including_retries'] += 1
                    row, raised = _attempt(root, config, book, device, deps, noisy_problem, method, degree, mode,
                                           dest, run_id, base, 'noise', clean_data=clean_problem.data)
                    append_jsonl(dest/'runs.jsonl', row); results.append(row); attempted_now += 1
                    if row['status'] not in GOOD_RUN_STATUSES:
                        retained_failures.append(row)
                    if raised is not None:
                        raise raised
    return {'status': 'BOUNDED_NOISE_FINISHED', 'attempts_this_call': attempted_now, 'attempts_retained_total': len(attempts),
            'attempt_cap': 24, 'failed_or_not_run_this_call': len(retained_failures),
            'historical_split': True, 'held_truth_receiver_residual': dict(HELD_RECEIVER_GAP),
            'scientific_gate_decision': 'NOT_COMPUTED_PARENT_OWNED', 'output': str(dest)}


def run_warm_timing(root, config, book, device, job, chosen_method, chosen_degree, chosen_mode):
    """One full/chosen pair per declared parent, only static geometry/SVD warm."""
    root = Path(root)
    parents = _selection(config, chosen_method, chosen_degree, chosen_mode)
    deps = _dependencies()
    Adapter, load_problem, _, _, append_jsonl, _ = deps
    dest = root/'results/timing'
    dest.mkdir(parents=True, exist_ok=True)
    _manifest(dest, {'stage': 'warm_timing', 'parents': parents, 'chosen_method': chosen_method,
                     'chosen_degree': int(chosen_degree), 'chosen_mode': chosen_mode,
                     'attempt_cap_including_failures_and_explicit_retries': 12,
                     'prefill': 'static geometry plus receiver SVD only', 'invocation_gate_owner': 'parent CLI',
                     'inference_scope': 'single paired timing per historical parent; descriptive only; no overall confidence'})
    attempts = _read_rows(dest/'attempts.jsonl')
    results = _read_rows(dest/'runs.jsonl')
    retry = bool(config.get('robustness_retry_failed', False))
    methods = [('FULL_GN', 0, 'A1'), (chosen_method, int(chosen_degree), chosen_mode)]
    attempted_now, failures = 0, 0
    for parent in parents:
        pair = [(method, degree, mode) for method, degree, mode in methods
                if _pending(_key(parent, method, degree, mode), attempts, results, retry)]
        pair = pair[:max(0, 12-len(attempts))]
        if not pair:
            continue
        prefill_id = f'{_token(job)}_warm_prefill_p{parent}_after{len(attempts)}'
        before_prefill = _snapshot(book)
        prefill_started = time.perf_counter()
        cpu_started = time.process_time()
        try:
            with _metadata(book, parent_object_id=parent, prefill_id=prefill_id), book.scope('online_warm_prefill'):
                with book.span('warm_runtime_observation_input', warm_runtime_reads=1):
                    problem = load_problem(root/f'data/runtime/{parent}/problem.npz')
                book.synchronize()
                geometry_start = time.perf_counter()
                with book.span('warm_static_geometry_prefill', warm_geometry_prefills=1):
                    adapter = Adapter(problem, device=device, book=book)
                book.synchronize()
                geometry_wall = time.perf_counter()-geometry_start
                svd_start = time.perf_counter()
                with book.span('warm_static_receiver_GSVD_prefill', warm_receiver_SVD_prefills=1):
                    adapter.model.gs_modes()
                book.synchronize()
                svd_wall = time.perf_counter()-svd_start
            prefill_wall = time.perf_counter()-prefill_started
            common_wall = max(0., prefill_wall-svd_wall)
            prefill = {'job': job, 'parent_object_id': parent, 'prefill_id': prefill_id, 'status': 'PAID_PREFILL_COMPLETE',
                       'wall_prefill_seconds': prefill_wall, 'wall_geometry_seconds': geometry_wall,
                       'wall_receiver_SVD_seconds': svd_wall, 'wall_common_input_geometry_overhead_seconds': common_wall,
                       'process_cpu_seconds': time.process_time()-cpu_started, 'cost': book.delta(before_prefill),
                       'actual_amortization_run_limit': 2, 'no_material_state_LU_or_Jacobian_prefilled': True}
            append_jsonl(dest/'prefill.jsonl', prefill)
        except BaseException as exc:
            append_jsonl(dest/'prefill.jsonl', {'job': job, 'parent_object_id': parent, 'prefill_id': prefill_id,
                         'status': 'FAILED_PREFILL', 'failure': type(exc).__name__+': '+str(exc),
                         'cost': book.delta(before_prefill), 'wall_prefill_seconds': time.perf_counter()-prefill_started})
            if isinstance(exc, BudgetExceeded) or not isinstance(exc, Exception):
                raise
            for method, degree, mode in pair:
                row = {'job': job, 'parent_object_id': parent, 'method': method, 'mode': mode, 'degree': degree,
                       'attempt_key': _key(parent, method, degree, mode), 'prefill_id': prefill_id,
                       'status': 'NOT_RUN_PREFILL_FAILED', 'failure': type(exc).__name__+': '+str(exc),
                       'reconstruction_started': False, 'cache_mode': 'warm_static_only'}
                append_jsonl(dest/'runs.jsonl', row); results.append(row); failures += 1
            continue
        current_rows = []
        raised_after_pair = None
        try:
            for method, degree, mode in pair:
                _clear_material_cache(adapter)
                run_id = f'{_token(job)}_warm_p{parent}_{_token(method)}_attempt{len(attempts)+1}'
                base = {'job': job, 'attempt_key': _key(parent, method, degree, mode), 'prefill_id': prefill_id,
                        'comparison_chosen_mode': chosen_mode, 'cache_mode': 'warm_static_only',
                        'split': 'historically_exposed_feasibility', 'static_caches_reused': ['Goff', 'GS', 'receiver_geometry_SVD'],
                        'material_LU_current_Jacobian_cache_reused': False,
                        'restarts_from_original_init': True, 'wall_total_excludes_prefill': True,
                        'wall_prefill_seconds': prefill_wall,
                        'inference_scope': 'one paired timing per parent; descriptive only; no overall confidence'}
                marker = {**base, 'run_id': run_id, 'parent_object_id': parent, 'method': method, 'degree': degree,
                          'mode': mode, 'status': 'ATTEMPT_REQUESTED'}
                append_jsonl(dest/'attempts.jsonl', marker); attempts.append(marker)
                book.counts['warm_attempt_requests_including_retries'] += 1
                row, raised = _attempt(root, config, book, device, deps, problem, method, degree, mode,
                                       dest, run_id, base, 'warm', adapter=adapter)
                row['receiver_SVD_cache_used_this_run'] = bool(row.get('attempt_cost_including_wrapper_and_offline_evaluation', {}).get('exclusive_walls', {}).get('receiver_geometry_SVD', 0.) > 0.)
                append_jsonl(dest/'attempt_results.jsonl', row)
                current_rows.append(row); attempted_now += 1
                if row['status'] not in GOOD_RUN_STATUSES:
                    failures += 1
                if raised is not None:
                    raised_after_pair = raised
                    break
        finally:
            _clear_material_cache(adapter)
            actual = sum(bool(row.get('reconstruction_started')) for row in current_rows)
            svd_users = sum(bool(row.get('receiver_SVD_cache_used_this_run')) for row in current_rows)
            unallocated = (common_wall if not actual else 0.)+(svd_wall if not svd_users else 0.)
            allocation = {'prefill_id': prefill_id, 'parent_object_id': parent, 'actual_amortization_run_count': actual,
                          'actual_receiver_SVD_consuming_run_count': svd_users, 'maximum_actual_amortization_runs': 2,
                          'failed_attempts_are_retained_and_charged': True, 'unallocated_prefill_wall_seconds_still_charged': unallocated,
                          'allocation_policy': 'common input/geometry divided across actual started runs; receiver SVD only across observed receiver-SVD users; unused prefill remains charged',
                          'wall_prefill_seconds': prefill_wall, 'actual_run_ids': [row['run_id'] for row in current_rows]}
            append_jsonl(dest/'amortization.jsonl', allocation)
            for row in current_rows:
                common_share = common_wall/actual if actual and row.get('reconstruction_started') else 0.
                svd_share = svd_wall/svd_users if svd_users and row.get('receiver_SVD_cache_used_this_run') else 0.
                share = common_share+svd_share
                row.update(actual_amortization_run_count=actual, actual_receiver_SVD_consuming_run_count=svd_users,
                           actual_paid_prefill_share_wall_seconds=share,
                           unallocated_prefill_wall_seconds_still_charged=unallocated,
                           wall_total_plus_unamortized_prefill_seconds=(row['wall_total']+prefill_wall) if row.get('wall_total') is not None else None,
                           wall_total_plus_actual_paid_prefill_share_seconds=(row['wall_total']+share) if row.get('wall_total') is not None else None,
                           amortization_policy=allocation['allocation_policy'])
                append_jsonl(dest/'runs.jsonl', row); results.append(row)
        if raised_after_pair is not None:
            raise raised_after_pair
    return {'status': 'BOUNDED_WARM_TIMING_FINISHED', 'attempts_this_call': attempted_now, 'attempts_retained_total': len(attempts),
            'attempt_cap': 12, 'failed_or_not_run_this_call': failures,
            'scientific_gate_decision': 'NOT_COMPUTED_PARENT_OWNED',
            'inference_scope': 'single paired timing per historical parent; descriptive only; no overall confidence', 'output': str(dest)}
