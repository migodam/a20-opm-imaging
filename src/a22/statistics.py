"""Scene-based A22 prediction evidence. This module never decides a gate.

One nonnegative, zero-intercept least-squares scale per method is fitted on
noise-draw-averaged units. Screening uses leave-one-scene-out; formal analysis
fits only frozen development scenes and never tunes on calibration/evaluation.
All inference intervals resample paired scenes, not directions or noise draws.
Importing this module reads/writes no files and invokes no physics or training.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import csv
import json
import math
from pathlib import Path
import random
from statistics import mean, median

from a22.reporting import METHODS, _field, _scope, _spearman


FULL_J = 'full_J'
FULL_J_ALIASES = ('pred_full_J', 'prediction_full_J', 'full_J_prediction',
                  'full_J_predicted_error', 'predicted_error_full_J',
                  'pred_fullJ', 'pred_J_full')
FULL_J_TOTAL = 'full_J_total'
FULL_J_TOTAL_ALIASES = ('pred_full_J_total', 'prediction_full_J_total',
                       'full_J_total_prediction', 'full_J_total_predicted_error',
                       'predicted_error_full_J_total', 'pred_fullJ_total',
                       'pred_J_full_total')
OFFLINE_FULL_J_METHODS = {FULL_J: FULL_J_ALIASES, FULL_J_TOTAL: FULL_J_TOTAL_ALIASES}
NOISE_BRANCHES = ('all', 'noise_zero', 'noise_positive')


def _number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _nonnegative(value):
    value = _number(value)
    return value if value is not None and value >= 0 else None


def _boolean(value):
    if value is None:
        return None
    text = str(value).strip().casefold()
    if text in ('1', 'true', 'yes', 'failure', 'failed'):
        return True
    if text in ('0', 'false', 'no', 'success', 'succeeded'):
        return False
    return None


def _invalid(row):
    status = str(_field(row, 'status', '')).strip().upper()
    if status.startswith(('FAIL', 'INVALID', 'ERROR', 'NOT_RUN', 'BUDGET', 'TIMEOUT',
                          'CANCEL', 'NON_CONVERG', 'NONCONVERG', 'NOT_CONVERG',
                          'REJECT', 'MISSING', 'UNDEFINED', 'NOT_COMPLETED',
                          'PARTIAL', 'INCOMPLETE')):
        return True
    return any(_boolean(row.get(key)) is False for key in ('valid', 'row_valid', 'label_valid', 'prediction_valid') if key in row)


def _prediction(row, method):
    if method in OFFLINE_FULL_J_METHODS:
        folded = {str(key).casefold(): value for key, value in row.items()}
        value = next((folded[key.casefold()] for key in OFFLINE_FULL_J_METHODS[method]
                      if key.casefold() in folded and str(folded[key.casefold()]).strip()), None)
    else:
        value = _field(row, 'pred_' + method)
    if value is None and str(_field(row, 'method', '')).casefold() == method.casefold():
        value = row.get('predicted_error', row.get('prediction'))
    return _nonnegative(value)


def _failure_label(row):
    """Only explicit labels; no post hoc threshold is invented from errors."""
    for key in ('failure', 'failure_label', 'recovery_failure'):
        if key in row and _boolean(row[key]) is not None:
            return int(_boolean(row[key])), key
    if 'success' in row and _boolean(row['success']) is not None:
        # Boolean success has its ordinary meaning, independent of text labels
        # accepted by the failure parser above.
        value = str(row['success']).strip().casefold()
        success = value in ('1', 'true', 'yes', 'success', 'succeeded')
        return int(not success), 'success'
    return None, None


def fit_nonnegative_scale(pairs):
    """Fit y = scale*x by unweighted LS, no intercept or outlier removal.

    Pairs are (forecast, absolute coefficient error). Invalid pairs are counted
    as missing, never treated as zero. Each caller-supplied pair is one already
    averaged scene/direction/amplitude/noise/intervention unit.
    """
    supplied = list(pairs)
    valid = [(x, y) for raw_x, raw_y in supplied
             if (x := _nonnegative(raw_x)) is not None and (y := _nonnegative(raw_y)) is not None]
    result = dict(scale=None, status='UNDEFINED', fit_units=len(valid),
                  missing_fit_units=len(supplied)-len(valid), parameter_count=1,
                  intercept=0.0, loss='unweighted squared absolute coefficient error',
                  outlier_filter='NONE', unit='noise-draw mean')
    if not valid:
        result['reason'] = 'NO_VALID_FIT_PAIRS'
        return result
    x_max, y_max = max(x for x, _ in valid), max(y for _, y in valid)
    if x_max == 0:
        result['reason'] = 'ALL_FORECASTS_ZERO_SCALE_UNIDENTIFIABLE'
        return result
    if y_max == 0:
        scale = 0.0
    else:
        normalized = [(x/x_max,y/y_max) for x,y in valid]
        denominator = math.fsum(x*x for x, _ in normalized)
        numerator = math.fsum(x*y for x, y in normalized)
        scale = (y_max/x_max) * (numerator/denominator)
    if not math.isfinite(scale):
        result['reason'] = 'NONFINITE_SCALE'
        return result
    result.update(scale=max(0.0, scale), status='FITTED', reason=None)
    return result


def failure_auc(scores, failure_fractions, *, unit_weights=None):
    """Weighted ROC AUC from explicit noise-draw labels, equal weight per unit.

    A unit's positive weight is its observed failure fraction and its negative
    weight is one minus that fraction. This preserves both classes in mixed
    noise-draw units without choosing an arbitrary majority-vote threshold.
    It is descriptive; correlated draws are not independent inference samples.
    Optional weights let pooled reports give each scene the same total weight.
    """
    scores, failure_fractions = list(scores), list(failure_fractions)
    if len(scores) != len(failure_fractions):
        raise ValueError('AUC_SCORE_LABEL_LENGTH_MISMATCH')
    weights = [1.0]*len(scores) if unit_weights is None else list(unit_weights)
    if len(weights) != len(scores):
        raise ValueError('AUC_UNIT_WEIGHT_LENGTH_MISMATCH')
    pairs = [(score, fraction, weight) for raw_score, raw_fraction, raw_weight in zip(scores, failure_fractions, weights)
             if (score := _nonnegative(raw_score)) is not None
             and (fraction := _number(raw_fraction)) is not None and 0 <= fraction <= 1
             and (weight := _nonnegative(raw_weight)) is not None and weight>0]
    positive = math.fsum(fraction*weight for _, fraction, weight in pairs)
    negative = math.fsum((1-fraction)*weight for _, fraction, weight in pairs)
    result = dict(value=None, status='UNDEFINED', units=len(pairs),
                  positive_failure_mass=positive, negative_failure_mass=negative,
                  definition=('equal-unit' if unit_weights is None else 'supplied-unit-weight') + ' ROC AUC; mixed draw classes retained as fractions',
                  inferential_claim='NONE')
    if positive <= 0 or negative <= 0:
        result['reason'] = 'BOTH_POSITIVE_AND_NEGATIVE_FAILURE_LABELS_REQUIRED'
        return result
    numerator = math.fsum(w*p*v*(1-q)*(1.0 if a>b else 0.5 if a==b else 0.0)
                          for a, p, w in pairs for b, q, v in pairs)
    result.update(value=numerator/(positive*negative), status='RECORDED_DESCRIPTIVE', reason=None)
    return result


def _catalog(values):
    """Keep supplied values verbatim; count labels without upgrading credibility."""
    counts = Counter()
    originals = {}
    for value in values:
        key = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
        counts[key] += 1
        originals[key] = value
    return [dict(value=originals[key], count=counts[key]) for key in sorted(counts)]


def _scene_metadata(rows, manifest):
    metadata = defaultdict(lambda: defaultdict(list))
    for row in list(manifest or []) + rows:
        scene = str(_field(row, 'scene_id', '')).strip()
        if not scene:
            continue
        for key in ('family', 'split', 'historical_exposure'):
            if row.get(key) is not None and str(row[key]).strip():
                metadata[scene][key].append(row[key])
    result = {}
    for scene, values in metadata.items():
        families = sorted({str(value) for value in values['family']})
        result[scene] = dict(family=families[0] if len(families)==1 else 'UNDECLARED' if not families else 'CONFLICTING_FAMILY',
                             supplied_family_values=families,
                             supplied_split_values=sorted({str(value) for value in values['split']}),
                             historical_exposure=_catalog(values['historical_exposure']))
    return result


def aggregate_direction_rows(rows, *, scene_manifest=None):
    """Average draws before fitting/evaluation; partial units stay unavailable."""
    rows = [dict(row) for row in rows]
    metadata = _scene_metadata(rows, scene_manifest)
    methods = list(METHODS)
    for method, aliases in OFFLINE_FULL_J_METHODS.items():
        columns = {name.casefold() for name in aliases}
        if any(any(str(key).casefold() in columns for key in row)
               or str(_field(row, 'method', '')).casefold() == method.casefold() for row in rows):
            methods.append(method)
    grouped = defaultdict(list)
    missing_group_fields = Counter()
    for index, row in enumerate(rows):
        fields = {key: _field(row, key) for key in ('scene_id', 'direction_id', 'amplitude', 'noise_level', 'intervention')}
        missing = [key for key, value in fields.items() if value is None or str(value).strip()=='']
        missing_group_fields.update(missing)
        scene = str(fields['scene_id']) if 'scene_id' not in missing else 'MISSING_SCENE_ID:' + str(index)
        direction = str(fields['direction_id']) if 'direction_id' not in missing else 'MISSING_DIRECTION_ID:' + str(index)
        amplitude, noise = _number(fields['amplitude']), _nonnegative(fields['noise_level'])
        if amplitude is None and 'amplitude' not in missing:
            missing.append('amplitude')
            missing_group_fields['amplitude'] += 1
        if noise is None and 'noise_level' not in missing:
            missing.append('noise_level')
            missing_group_fields['noise_level'] += 1
        intervention = str(fields['intervention']) if 'intervention' not in missing else 'UNDECLARED'
        key = (_scope(row), scene, direction, amplitude, noise, intervention)
        grouped[key].append((row, missing))
    units = []
    for key, members in sorted(grouped.items(), key=lambda item: str(item[0])):
        scope, scene, direction, amplitude, noise, intervention = key
        targets = [_nonnegative(_field(row, 'true_error')) for row, _ in members if not _invalid(row)]
        valid_targets = [target for target in targets if target is not None]
        labels = [_failure_label(row) for row, _ in members if not _invalid(row)]
        known_labels = [label for label, _ in labels if label is not None]
        complete_label = len(known_labels) == len(members)
        unit = dict(scene_id=scene, direction_id=direction, amplitude=amplitude,
                    noise_level=noise, intervention=intervention, evidence_scope=scope,
                    family=metadata.get(scene, {}).get('family', 'UNDECLARED'),
                    input_rows=len(members), invalid_rows=sum(_invalid(row) for row, _ in members),
                    missing_target_rows=len(members)-len(valid_targets),
                    group_fields_complete=all(not missing for _, missing in members),
                    true_error=mean(valid_targets) if valid_targets else None,
                    failure_fraction=mean(known_labels) if complete_label and known_labels else None,
                    failure_label_complete=complete_label,
                    failure_label_origins=sorted({origin for _, origin in labels if origin is not None}),
                    certificate_types=_catalog(row.get('certificate_type') for row, _ in members),
                    status_values=_catalog(_field(row, 'status') for row, _ in members),
                    raw_predictions={}, method_eligible={}, paired_draw_rows={})
        for method in methods:
            pairs = [(_nonnegative(_field(row, 'true_error')), _prediction(row, method))
                     for row, _ in members if not _invalid(row)]
            valid = [(target, forecast) for target, forecast in pairs if target is not None and forecast is not None]
            unit['raw_predictions'][method] = mean(forecast for _, forecast in valid) if valid else None
            unit['paired_draw_rows'][method] = len(valid)
            unit['method_eligible'][method] = len(valid)==len(members) and unit['group_fields_complete']
        units.append(unit)
    return dict(units=units, methods=methods, scene_metadata=metadata,
                input_rows=len(rows), invalid_input_rows=sum(_invalid(row) for row in rows),
                missing_group_fields=dict(missing_group_fields),
                certificate_types=_catalog(row.get('certificate_type') for row in rows),
                historical_exposure=_catalog(_field(row, 'historical_exposure') for row in rows),
                feature_origins=_catalog(_field(row, 'feature_origin') for row in rows),
                label_origins=_catalog(_field(row, 'label_origin') for row in rows))


def _frozen_scenes(config, mode):
    if mode == 'screen':
        if 'screening_scenes' not in config:
            raise ValueError('SCREENING_REQUIRES_FROZEN_SCENE_IDS')
        result = {'held_scene': [str(scene) for scene in config['screening_scenes']]}
    elif mode == 'formal':
        splits = config.get('splits', {})
        if not all(key in splits for key in ('development', 'calibration', 'evaluation')):
            raise ValueError('FORMAL_REQUIRES_FROZEN_DEVELOPMENT_CALIBRATION_EVALUATION')
        result = {key: [str(scene) for scene in splits[key]] for key in ('development', 'calibration', 'evaluation')}
    else:
        raise ValueError('UNREGISTERED_STATISTICS_MODE')
    flattened = [scene for scenes in result.values() for scene in scenes]
    if len(flattened) != len(set(flattened)):
        raise ValueError('FROZEN_SCENE_SPLITS_OVERLAP_OR_REPEAT')
    return result


def _calibrate(units, methods, frozen, mode):
    calibrations, evaluated = [], []
    scopes = sorted({unit['evidence_scope'] for unit in units} or {'deployable'})
    for scope in scopes:
        members = [unit for unit in units if unit['evidence_scope']==scope]
        folds = [(held, [scene for scene in frozen['held_scene'] if scene!=held], [held], 'held_scene')
                 for held in frozen['held_scene']] if mode=='screen' else [
                     ('development_fit', frozen['development'], scenes, split)
                     for split, scenes in frozen.items()]
        # In formal mode each split deliberately reuses the identical development
        # fitting data; neither calibration nor test outcomes can alter the fit.
        fit_cache = {}
        for fold, fit_scenes, evaluate_scenes, split in folds:
            scales = {}
            for method in methods:
                cache_key = (tuple(fit_scenes), method)
                if cache_key not in fit_cache:
                    fit_units = [unit for unit in members if unit['scene_id'] in fit_scenes and unit['method_eligible'][method]]
                    fit = fit_nonnegative_scale((unit['raw_predictions'][method], unit['true_error']) for unit in fit_units)
                    fit.update(method=method, evidence_scope=scope,
                               method_scope='offline_full_J' if method in OFFLINE_FULL_J_METHODS else scope,
                               fit_scene_ids=sorted({unit['scene_id'] for unit in fit_units}),
                               requested_fit_scene_ids=list(fit_scenes),
                               missing_fit_scene_ids=sorted(set(fit_scenes)-{unit['scene_id'] for unit in fit_units}),
                               capacity='one scalar per method', label_target='absolute coefficient error')
                    fit_cache[cache_key] = fit
                fit = fit_cache[cache_key]
                scales[method] = fit['scale']
                calibrations.append(dict(fit, fold=fold, evaluation_split=split,
                                         evaluate_scene_ids=list(evaluate_scenes),
                                         held_out=mode=='screen' or split!='development'))
            for unit in members:
                if unit['scene_id'] not in evaluate_scenes:
                    continue
                forecasts = {}
                for method in methods:
                    scale, raw = scales[method], unit['raw_predictions'][method]
                    value = scale*raw if scale is not None and raw is not None and unit['method_eligible'][method] else None
                    forecasts[method] = value if value is not None and math.isfinite(value) else None
                evaluated.append(dict(unit, calibrated_predictions=forecasts, evaluation_split=split,
                                      calibration_fold=fold, in_sample=mode=='formal' and split=='development'))
    return calibrations, evaluated


def _in_branch(unit, branch):
    return (branch=='all' or branch=='noise_zero' and unit['noise_level']==0
            or branch=='noise_positive' and unit['noise_level'] is not None and unit['noise_level']>0)


def _scene_stats(members, method, **labels):
    raw_valid = [unit for unit in members if unit['method_eligible'][method]]
    valid = [unit for unit in members if unit['method_eligible'][method]
             and unit['calibrated_predictions'][method] is not None]
    target = [unit['true_error'] for unit in valid]
    forecast = [unit['calibrated_predictions'][method] for unit in valid]
    raw = [unit['raw_predictions'][method] for unit in raw_valid]
    raw_target = [unit['true_error'] for unit in raw_valid]
    covered = sum(error<=prediction for error, prediction in zip(target, forecast))
    classification = [unit for unit in valid if unit['failure_label_complete'] and unit['failure_fraction'] is not None]
    auc = failure_auc([unit['calibrated_predictions'][method] for unit in classification],
                      [unit['failure_fraction'] for unit in classification])
    return dict(labels, method=method, method_scope='offline_full_J' if method in OFFLINE_FULL_J_METHODS else labels['evidence_scope'],
                units=len(members), paired_units=len(valid), raw_paired_units=len(raw_valid), missing_or_invalid_units=len(members)-len(valid),
                invalid_units=sum(unit['invalid_rows']>0 for unit in members),
                spearman=_spearman(target, forecast), raw_spearman=_spearman(raw_target, raw),
                MAE=mean(abs(error-prediction) for error, prediction in zip(target, forecast)) if valid else None,
                raw_MAE=mean(abs(error-prediction) for error, prediction in zip(raw_target, raw)) if raw_valid else None,
                coverage=covered/len(valid) if valid else None,
                raw_coverage=mean(error<=prediction for error, prediction in zip(raw_target, raw)) if raw_valid else None,
                coverage_all_attempted_units=covered/len(members) if members else None,
                coverage_definition='observed mean absolute error <= predicted budget; empirical, not certified confidence coverage',
                all_attempted_coverage_definition='confirmed covered units / all attempted units; unresolved means not confirmed, not a measured violation',
                failure_AUC=auc['value'], failure_AUC_status=auc['status'],
                failure_AUC_definition=auc['definition'],
                classification_units=auc['units'], positive_failure_mass=auc['positive_failure_mass'],
                negative_failure_mass=auc['negative_failure_mass'],
                certificate_types=[item for unit in members for item in unit['certificate_types']],
                status='RECORDED' if valid and len(valid)==len(members) else 'PARTIAL' if valid else 'NOT_RUN')


def _quantile(values, probability):
    ordered = sorted(values)
    if not ordered:
        return None
    location = probability*(len(ordered)-1)
    lower, upper = math.floor(location), math.ceil(location)
    return ordered[lower]+(ordered[upper]-ordered[lower])*(location-lower)


def paired_scene_bootstrap(scene_mae, *, repetitions=2000, seed=20261007):
    """A3 versus stronger A1/A2, reselecting the stronger baseline per draw."""
    if not isinstance(repetitions, int) or isinstance(repetitions, bool) or repetitions<0:
        raise ValueError('INVALID_BOOTSTRAP_REPETITIONS')
    pairs = [row for row in scene_mae if all(_nonnegative(row.get(method)) is not None for method in ('A1','A2','A3'))]
    if len({str(row['scene_id']) for row in pairs}) != len(pairs):
        raise ValueError('BOOTSTRAP_SCENE_IDS_MUST_BE_UNIQUE')
    result = dict(status='UNDEFINED', scene_ids=[str(row['scene_id']) for row in pairs],
                  paired_scenes=len(pairs), repetitions_requested=repetitions, repetitions_performed=0,
                  seed=int(seed), sampling_unit='scene, paired across A1/A2/A3',
                  scene_weighting='equal scene mean MAE on common complete units',
                  sign='positive differences mean lower A3 MAE',
                  baseline_rule='min(mean A1 MAE, mean A2 MAE), reselected in every bootstrap sample',
                  calibration_refit_in_bootstrap=False,
                  interval_scope='conditional on saved LOSO/development fits; retraining uncertainty is not included',
                  absolute_MAE_improvement=None, relative_MAE_improvement=None,
                  absolute_95_percent_interval=None, relative_95_percent_interval=None,
                  improvement_probability=None, relative_valid_draws=0,
                  baseline_selection_counts={'A1':0, 'A2':0}, inferential_claim='pilot scene-cluster interval; no gate decision')
    if not pairs:
        result['reason'] = 'NO_COMMON_VALID_SCENE_PAIRS'
        return result
    def difference(sample):
        errors = {method: mean(float(row[method]) for row in sample) for method in ('A1','A2','A3')}
        stronger = 'A1' if errors['A1']<=errors['A2'] else 'A2'
        baseline = errors[stronger]
        delta = baseline-errors['A3']
        return delta, delta/baseline if baseline>0 else None, stronger, errors
    point, relative, baseline, errors = difference(pairs)
    result.update(absolute_MAE_improvement=point, relative_MAE_improvement=relative,
                  stronger_point_baseline=baseline, paired_equal_scene_MAE=errors)
    if len(pairs)<2 or repetitions==0:
        result['reason'] = 'AT_LEAST_TWO_PAIRED_SCENES_AND_POSITIVE_REPETITIONS_REQUIRED'
        return result
    rng = random.Random(int(seed))
    absolute_draws, relative_draws = [], []
    for _ in range(repetitions):
        delta, fraction, stronger, _ = difference([pairs[rng.randrange(len(pairs))] for _ in pairs])
        absolute_draws.append(delta)
        if fraction is not None:
            relative_draws.append(fraction)
        result['baseline_selection_counts'][stronger] += 1
    result.update(status='RECORDED_SCENE_CLUSTER_BOOTSTRAP', reason=None,
                  repetitions_performed=repetitions, relative_valid_draws=len(relative_draws),
                  absolute_95_percent_interval=[_quantile(absolute_draws,0.025), _quantile(absolute_draws,0.975)],
                  relative_95_percent_interval=[_quantile(relative_draws,0.025), _quantile(relative_draws,0.975)] if relative_draws else None,
                  improvement_probability=mean(value>0 for value in absolute_draws))
    return result


def analyze_rows(rows, config, *, mode='screen', scene_manifest=None,
                 bootstrap_repetitions=None, seed=None):
    """Return statistical evidence only, retaining declared missing/invalid data."""
    rows = [dict(row) for row in rows]
    frozen = _frozen_scenes(config, mode)
    aggregated = aggregate_direction_rows(rows, scene_manifest=scene_manifest)
    methods = aggregated['methods']
    calibrations, evaluated = _calibrate(aggregated['units'], methods, frozen, mode)
    count = int(config.get('bootstrap_repetitions',2000)) if bootstrap_repetitions is None else bootstrap_repetitions
    rng_seed = int(config.get('master_seed',20261007)) if seed is None else int(seed)
    scene_stats, summary, bootstraps = [], [], []
    primary_split = 'held_scene' if mode=='screen' else 'evaluation'
    for split, requested_scenes in frozen.items():
        scopes = sorted({unit['evidence_scope'] for unit in evaluated if unit['evaluation_split']==split} or {'deployable'})
        for scope in scopes:
            selected = [unit for unit in evaluated if unit['evaluation_split']==split and unit['evidence_scope']==scope]
            families = ['ALL']+sorted({unit['family'] for unit in selected})
            for family in families:
                family_units = [unit for unit in selected if family=='ALL' or unit['family']==family]
                expected = list(requested_scenes) if family=='ALL' else [scene for scene in requested_scenes
                    if aggregated['scene_metadata'].get(scene,{}).get('family')==family]
                for branch in NOISE_BRANCHES:
                    units = [unit for unit in family_units if _in_branch(unit,branch)]
                    grouped = defaultdict(list)
                    for unit in units:
                        grouped[unit['scene_id']].append(unit)
                    current = []
                    for scene in sorted(set(expected)|set(grouped)):
                        for method in methods:
                            item = _scene_stats(grouped.get(scene,[]), method,
                                                scene_id=scene, family=family,
                                                scene_family=aggregated['scene_metadata'].get(scene,{}).get('family','UNDECLARED'),
                                                noise_branch=branch,
                                                evidence_scope=scope, evaluation_split=split)
                            scene_stats.append(item)
                            current.append(item)
                    for method in methods:
                        members = [item for item in current if item['method']==method]
                        available = [item for item in members if item['MAE'] is not None]
                        rho = [item['spearman'] for item in members if item['spearman'] is not None]
                        scene_auc = [item['failure_AUC'] for item in members if item['failure_AUC'] is not None]
                        classification = [unit for unit in units if unit['method_eligible'][method]
                            and unit['calibrated_predictions'][method] is not None and unit['failure_label_complete']
                            and unit['failure_fraction'] is not None]
                        scene_counts = Counter(unit['scene_id'] for unit in classification)
                        pooled_auc = failure_auc([unit['calibrated_predictions'][method] for unit in classification],
                            [unit['failure_fraction'] for unit in classification],
                            unit_weights=[1/scene_counts[unit['scene_id']] for unit in classification])
                        summary.append(dict(method=method, method_scope='offline_full_J' if method in OFFLINE_FULL_J_METHODS else scope,
                            family=family, noise_branch=branch, evidence_scope=scope,evaluation_split=split,
                            requested_scene_ids=expected, available_scene_ids=[item['scene_id'] for item in available],
                            missing_scene_ids=sorted(set(expected)-{item['scene_id'] for item in available}),
                            scenes_with_defined_spearman=len(rho), median_scene_spearman=median(rho) if rho else None,
                            equal_scene_MAE=mean(item['MAE'] for item in available) if available else None,
                            equal_scene_coverage=mean(item['coverage'] for item in available) if available else None,
                            scenes_with_defined_failure_AUC=len(scene_auc),
                            equal_scene_mean_failure_AUC=mean(scene_auc) if scene_auc else None,
                            pooled_failure_AUC=pooled_auc['value'], pooled_failure_AUC_status=pooled_auc['status'],
                            pooled_failure_AUC_weighting='equal scene; each complete unit weight 1 / classified units in its scene',
                            equal_scene_coverage_all_attempted=mean(item['coverage_all_attempted_units'] for item in members
                                if item['coverage_all_attempted_units'] is not None) if any(item['coverage_all_attempted_units'] is not None for item in members) else None,
                            status='RECORDED' if available and len(available)==len(expected) and all(item['status']=='RECORDED' for item in available) else 'PARTIAL' if available else 'NOT_RUN'))
                    if split=='development':
                        continue  # No held-out inference is reported on fit data.
                    paired = []
                    for scene, scene_units in sorted(grouped.items()):
                        common = [unit for unit in scene_units if all(unit['method_eligible'][method]
                                  and unit['calibrated_predictions'][method] is not None for method in ('A1','A2','A3'))]
                        if common:
                            paired.append(dict(scene_id=scene, units=len(common), **{method:
                                mean(abs(unit['true_error']-unit['calibrated_predictions'][method]) for unit in common)
                                for method in ('A1','A2','A3')}))
                    bootstrap = paired_scene_bootstrap(paired,repetitions=count,seed=rng_seed)
                    bootstrap.update(family=family,noise_branch=branch,evidence_scope=scope,evaluation_split=split,
                                     requested_scene_ids=expected, missing_scene_ids=sorted(set(expected)-{item['scene_id'] for item in paired}),
                                     paired_scene_MAE=paired)
                    bootstraps.append(bootstrap)
    primary = next((item for item in bootstraps if item['family']=='ALL' and item['noise_branch']=='all'
                    and item['evidence_scope']=='deployable' and item['evaluation_split']==primary_split), None)
    expected_ids = {scene for scenes in frozen.values() for scene in scenes}
    audit = {key:value for key,value in aggregated.items() if key not in ('units','methods')}
    audit.update(requested_scene_splits=frozen, observed_scene_ids=sorted({unit['scene_id'] for unit in aggregated['units']}),
                 unused_scene_ids=sorted({unit['scene_id'] for unit in aggregated['units']}-expected_ids),
                 aggregation_unit='scene/scope/direction/amplitude/noise_level/intervention; mean across draws',
                 incomplete_units_policy='retained in audit; not counted as a paired success or coverage success',
                 classification_policy='explicit failure/success labels only; mixed draw labels retained as fractions',
                 covariance_or_confidence_coverage_claim=False)
    return dict(schema='a22.statistics.evidence.v1', mode=mode,
                status='RECORDED_EVIDENCE' if rows else 'NOT_RUN', methods=methods,
                gate_decisions=None, gate_authority='parent Codex only',
                recipe='LOSO single nonnegative scale' if mode=='screen' else 'development-only single nonnegative scale; calibration untuned',
                input_audit=audit, aggregated_units=aggregated['units'], evaluated_units=evaluated,
                calibration_scales=calibrations, per_scene_statistics=scene_stats,
                summaries=summary, paired_scene_bootstrap=bootstraps, primary_incrementality=primary)


def _read_csv(path):
    path = Path(path)
    if not path.is_file():
        return [], 'MISSING'
    try:
        with path.open(newline='',encoding='utf-8-sig') as stream:
            reader = csv.DictReader(stream)
            if not reader.fieldnames:
                return [], 'EMPTY_HEADER'
            return [dict(row) for row in reader], 'AVAILABLE'
    except (OSError,UnicodeError,csv.Error) as error:
        return [], 'UNREADABLE:' + type(error).__name__


def write_statistics(output_dir, evidence):
    """Save evidence artifacts; caller owns its CPU receipt and gate judgment."""
    directory = Path(output_dir)
    directory.mkdir(parents=True,exist_ok=True)
    paths = {}
    for name, payload in (('STATISTICS_EVIDENCE.json',evidence),
                          ('PAIRED_SCENE_BOOTSTRAP.json',evidence['paired_scene_bootstrap']),
                          ('STATISTICS_INPUT_AUDIT.json',evidence['input_audit'])):
        path = directory/name
        path.write_text(json.dumps(payload,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')
        paths[name] = str(path)
    for name,key in (('per_scene_statistics.csv','per_scene_statistics'),
                     ('calibration_scales.csv','calibration_scales'),
                     ('statistics_summary.csv','summaries')):
        path = directory/name
        rows = evidence[key]
        columns = sorted({column for row in rows for column in row})
        with path.open('w',newline='',encoding='utf-8') as stream:
            writer = csv.DictWriter(stream,fieldnames=columns)
            writer.writeheader()
            for row in rows:
                writer.writerow({column:json.dumps(value,ensure_ascii=False) if isinstance(value,(dict,list)) else '' if value is None else value
                                 for column,value in row.items()})
        paths[name] = str(path)
    return paths


def analyze_direction_metrics(csv_path, config, *, mode='screen', scene_manifest=None,
                              bootstrap_repetitions=None, seed=None, output_dir=None):
    """Read the caller's A22 direction CSV and optionally save statistical evidence."""
    rows, source_status = _read_csv(csv_path)
    if isinstance(scene_manifest,(str,Path)):
        manifest, manifest_status = _read_csv(scene_manifest)
    else:
        manifest, manifest_status = scene_manifest, 'SUPPLIED_ROWS' if scene_manifest is not None else 'NOT_SUPPLIED'
    evidence = analyze_rows(rows,config,mode=mode,scene_manifest=manifest,
                            bootstrap_repetitions=bootstrap_repetitions,seed=seed)
    evidence['input_audit'].update(source_path=str(Path(csv_path)),source_status=source_status,
                                   supplied_columns=sorted({str(key) for row in rows for key in row}),
                                   scene_manifest_status=manifest_status)
    if output_dir is not None:
        evidence['artifact_paths'] = write_statistics(output_dir,evidence)
    return evidence
