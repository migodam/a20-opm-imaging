"""Prepared CPU-only statistics fixtures; no physics, neural fit, SSH, or GPU."""
from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from a22.statistics import (
    FULL_J, FULL_J_TOTAL,
    aggregate_direction_rows, analyze_direction_metrics, analyze_rows,
    failure_auc, fit_nonnegative_scale, paired_scene_bootstrap,
)


def config():
    return dict(screening_scenes=[1,2,3,4], bootstrap_repetitions=20,
                master_seed=20261007,
                splits=dict(development=[1,2],calibration=[3],evaluation=[4,5]))


def row(scene, direction, *, error=None, draw=0, noise=1, family='gaussian', **extra):
    result = dict(scene_id=scene,direction_id=direction,amplitude=0.1,
                  noise_level=noise,noise_draw=draw,intervention='nominal',
                  true_error=float(direction) if error is None else error,
                  pred_A0=float(direction),pred_A1=float(direction),
                  pred_A2=float(direction),pred_A3=float(direction),
                  family=family,evidence_scope='deployable',
                  feature_origin='bounded OPM actions',label_origin='offline coefficient error',
                  anchor_provenance='known_background',certificate_type='empirical_indicator',
                  status='OK')
    result.update(extra)
    return result


def find_scene(evidence, scene, method='A3', branch='all', family='ALL', split='held_scene'):
    return next(item for item in evidence['per_scene_statistics']
                if item['scene_id']==str(scene) and item['method']==method
                and item['noise_branch']==branch and item['family']==family
                and item['evaluation_split']==split and item['evidence_scope']=='deployable')


class CalibrationTests(unittest.TestCase):
    def test_scale_is_zero_intercept_ls_and_outliers_are_not_removed(self):
        fit = fit_nonnegative_scale([(1,1),(2,2),(3,100)])
        self.assertAlmostEqual(fit['scale'],305/14)
        self.assertEqual(fit['parameter_count'],1)
        self.assertEqual(fit['intercept'],0)
        self.assertEqual(fit['outlier_filter'],'NONE')
        self.assertEqual(fit_nonnegative_scale([(1,0),(2,0)])['scale'],0)

    def test_missing_negative_and_zero_forecasts_stay_unavailable(self):
        fit = fit_nonnegative_scale([(None,1),(1,-1),(float('nan'),3),(0,2)])
        self.assertIsNone(fit['scale'])
        self.assertEqual(fit['fit_units'],1)
        self.assertEqual(fit['missing_fit_units'],3)
        self.assertIn('UNIDENTIFIABLE',fit['reason'])

    def test_leave_one_scene_out_never_fits_the_held_scene(self):
        factors = {1:1,2:2,3:3,4:100}
        rows = [row(scene,direction,error=factors[scene]*direction)
                for scene in factors for direction in (1,2,3)]
        evidence = analyze_rows(rows,config(),bootstrap_repetitions=0)
        held = next(item for item in evidence['calibration_scales']
                    if item['fold']=='4' and item['method']=='A3')
        self.assertEqual(held['fit_scene_ids'],['1','2','3'])
        self.assertAlmostEqual(held['scale'],2)
        self.assertAlmostEqual(find_scene(evidence,4)['MAE'],196)
        self.assertIsNone(evidence['gate_decisions'])

    def test_formal_calibration_and_evaluation_never_refit_development_scale(self):
        rows = [row(scene,direction,error=(2 if scene in (1,2) else 100)*direction)
                for scene in range(1,6) for direction in (1,2,3)]
        first = analyze_rows(rows,config(),mode='formal',bootstrap_repetitions=0)
        changed = [dict(item,true_error=1000000) if item['scene_id'] in (3,4,5) else item for item in rows]
        second = analyze_rows(changed,config(),mode='formal',bootstrap_repetitions=0)
        first_scales = [item['scale'] for item in first['calibration_scales']]
        self.assertEqual(first_scales,[item['scale'] for item in second['calibration_scales']])
        self.assertTrue(all(item['fit_scene_ids']==['1','2'] for item in first['calibration_scales']))
        self.assertTrue(all(abs(value-2)<1e-12 for value in first_scales))
        self.assertEqual(first['primary_incrementality']['evaluation_split'],'evaluation')
        self.assertFalse(any(item['evaluation_split']=='development' for item in first['paired_scene_bootstrap']))

    def test_full_j_total_formal_scale_is_development_only_and_capacity_matched(self):
        rows = [row(scene,direction,error=(2 if scene in (1,2) else 100)*direction,
                    draw=draw,pred_full_J=direction,
                    pred_full_J_total=multiplier*direction)
                for scene in range(1,6) for direction in (1,2,3)
                for draw,multiplier in ((0,0.5),(1,1.5))]
        first = analyze_rows(rows,config(),mode='formal',bootstrap_repetitions=20,seed=7)
        changed = [dict(item,true_error=1000000,pred_full_J_total=5000000)
                   if item['scene_id'] in (3,4,5) else item for item in rows]
        second = analyze_rows(changed,config(),mode='formal',bootstrap_repetitions=20,seed=7)
        fits = [item for item in first['calibration_scales'] if item['method']==FULL_J_TOTAL]
        self.assertEqual(len(fits),3)
        self.assertEqual([item['scale'] for item in fits],
                         [item['scale'] for item in second['calibration_scales'] if item['method']==FULL_J_TOTAL])
        for fit in fits:
            self.assertAlmostEqual(fit['scale'],2)
            self.assertEqual(fit['fit_scene_ids'],['1','2'])
            self.assertEqual(fit['fit_units'],6)
            self.assertEqual(fit['parameter_count'],1)
            self.assertEqual(fit['intercept'],0)
            self.assertEqual(fit['method_scope'],'offline_full_J')
        self.assertAlmostEqual(find_scene(first,3,FULL_J_TOTAL,split='calibration')['MAE'],196)
        online = [{key:value for key,value in item.items() if key!='pred_full_J_total'} for item in rows]
        reference = analyze_rows(online,config(),mode='formal',bootstrap_repetitions=20,seed=7)
        self.assertEqual(first['paired_scene_bootstrap'],reference['paired_scene_bootstrap'])
        self.assertEqual(first['primary_incrementality'],reference['primary_incrementality'])

    def test_frozen_scene_split_overlap_is_rejected(self):
        cfg = config()
        cfg['splits']['evaluation'] = [2,4]
        with self.assertRaises(ValueError):
            analyze_rows([],cfg,mode='formal')


class UnitAndScopeTests(unittest.TestCase):
    def test_noise_draws_are_averaged_before_calibration_and_spearman(self):
        rows = [row(scene,direction,error=multiplier*direction,draw=draw)
                for scene in (1,2,3,4) for direction in (1,2,3)
                for draw,multiplier in ((0,1),(1,3))]
        evidence = analyze_rows(rows,config(),bootstrap_repetitions=0)
        observed = find_scene(evidence,1)
        self.assertEqual(observed['units'],3)
        self.assertEqual(observed['paired_units'],3)
        self.assertEqual(observed['spearman'],1)
        self.assertAlmostEqual(observed['MAE'],0)
        self.assertEqual(len(evidence['aggregated_units']),12)
        first = evidence['aggregated_units'][0]
        self.assertEqual(first['input_rows'],2)
        self.assertEqual(first['true_error'],2)

    def test_a_failed_draw_never_becomes_a_coverage_success(self):
        rows = [row(scene,direction,error=2*direction)
                for scene in (1,2,3,4) for direction in (1,2,3)]
        rows.append(row(1,1,error=0,draw=1,status='FAILED'))
        evidence = analyze_rows(rows,config(),bootstrap_repetitions=0)
        observed = find_scene(evidence,1)
        self.assertEqual(observed['units'],3)
        self.assertEqual(observed['paired_units'],2)
        self.assertEqual(observed['invalid_units'],1)
        self.assertEqual(observed['coverage'],1)
        self.assertAlmostEqual(observed['coverage_all_attempted_units'],2/3)
        self.assertEqual(observed['status'],'PARTIAL')

    def test_missing_prediction_is_not_zero_error_and_common_pairs_stay_paired(self):
        rows = [row(scene,direction,error=2*direction)
                for scene in (1,2,3,4) for direction in (1,2,3)]
        for item in rows:
            if item['scene_id']==4:
                item['pred_A2'] = None
        evidence = analyze_rows(rows,config(),bootstrap_repetitions=0)
        absent = find_scene(evidence,4,'A2')
        self.assertIsNone(absent['MAE'])
        self.assertIsNone(absent['raw_MAE'])
        self.assertIsNone(absent['coverage'])
        self.assertEqual(evidence['primary_incrementality']['paired_scenes'],3)
        self.assertEqual(evidence['primary_incrementality']['missing_scene_ids'],['4'])

    def test_raw_evidence_survives_unidentifiable_zero_forecast_scale(self):
        rows = [row(scene,direction,error=direction,pred_A0=0)
                for scene in (1,2,3,4) for direction in (1,2,3)]
        evidence = analyze_rows(rows,config(),bootstrap_repetitions=0)
        observed = find_scene(evidence,1,'A0')
        self.assertIsNone(observed['MAE'])
        self.assertEqual(observed['raw_MAE'],2)
        self.assertEqual(observed['raw_coverage'],0)
        self.assertEqual(observed['raw_paired_units'],3)

    def test_zero_noise_and_family_are_reported_without_recalibration(self):
        rows = [row(scene,direction,error=2*direction,noise=noise,
                    family='shell' if scene==4 else 'gaussian')
                for scene in (1,2,3,4) for direction in (1,2,3) for noise in (0,1)]
        evidence = analyze_rows(rows,config(),bootstrap_repetitions=0)
        self.assertEqual(find_scene(evidence,4,branch='noise_zero',family='shell')['paired_units'],3)
        self.assertEqual(find_scene(evidence,4,branch='noise_positive',family='shell')['paired_units'],3)
        held_scales = [item for item in evidence['calibration_scales'] if item['fold']=='4']
        self.assertEqual(len(held_scales),4)
        self.assertTrue(all(abs(item['scale']-2)<1e-12 for item in held_scales))

    def test_full_j_baseline_is_offline_and_certificate_values_are_unchanged(self):
        certificate = 'deterministic_model_components_Gaussian_noise_sd'
        rows = [row(scene,direction,error=2*direction,pred_full_J=direction,
                    certificate_type=certificate)
                for scene in (1,2,3,4) for direction in (1,2,3)]
        evidence = analyze_rows(rows,config(),bootstrap_repetitions=0)
        self.assertIn('full_J',evidence['methods'])
        observed = find_scene(evidence,1,'full_J')
        self.assertEqual(observed['method_scope'],'offline_full_J')
        self.assertTrue(all(item['value']==certificate for item in observed['certificate_types']))
        self.assertIn(evidence['primary_incrementality']['stronger_point_baseline'],('A1','A2'))
        self.assertFalse(evidence['input_audit']['covariance_or_confidence_coverage_claim'])

    def test_full_j_total_loso_averages_draws_and_preserves_official_incrementality(self):
        rows = [row(scene,direction,error=4*direction,draw=draw,noise=noise,
                    family='shell' if scene==4 else 'gaussian',
                    pred_A1=scene*direction,pred_A2=direction+scene,
                    pred_A3=2*direction,pred_full_J=2*direction)
                for scene in (1,2,3,4) for direction in (1,2,3)
                for noise in (0,1) for draw in (0,1)]
        reference = analyze_rows(rows,config(),bootstrap_repetitions=20,seed=11)
        augmented = [dict(item,pred_full_J_total=(0.5 if item['noise_draw']==0 else 1.5)*item['direction_id'])
                     for item in rows]
        evidence = analyze_rows(augmented,config(),bootstrap_repetitions=20,seed=11)
        self.assertEqual(evidence['methods'],['A0','A1','A2','A3',FULL_J,FULL_J_TOTAL])
        self.assertEqual(len(evidence['aggregated_units']),24)
        held = next(item for item in evidence['calibration_scales']
                    if item['fold']=='4' and item['method']==FULL_J_TOTAL)
        # Draw-level LS would yield 3.2 here; mean-before-fit gives 4.
        self.assertAlmostEqual(held['scale'],4)
        self.assertEqual(held['fit_units'],18)
        self.assertEqual(held['fit_scene_ids'],['1','2','3'])
        self.assertEqual(held['parameter_count'],1)
        observed = find_scene(evidence,4,FULL_J_TOTAL,family='shell')
        self.assertEqual(observed['paired_units'],6)
        self.assertAlmostEqual(observed['MAE'],0)
        self.assertEqual(observed['spearman'],1)
        self.assertEqual(observed['coverage'],1)
        for branch in ('noise_zero','noise_positive'):
            self.assertEqual(find_scene(evidence,4,FULL_J_TOTAL,branch=branch,family='shell')['paired_units'],3)
        for table in ('calibration_scales','per_scene_statistics','summaries'):
            offline = [item for item in evidence[table] if item['method'] in (FULL_J,FULL_J_TOTAL)]
            self.assertTrue(offline)
            self.assertTrue(all(item['method_scope']=='offline_full_J' for item in offline))
        self.assertEqual(evidence['paired_scene_bootstrap'],reference['paired_scene_bootstrap'])
        self.assertEqual(evidence['primary_incrementality'],reference['primary_incrementality'])
        self.assertIsNone(evidence['gate_decisions'])

    def test_missing_total_draw_does_not_drop_profiled_witness_or_online_pairs(self):
        rows = [row(scene,direction,error=2*direction,draw=draw,pred_full_J=direction)
                for scene in (1,2,3,4) for direction in (1,2,3) for draw in (0,1)]
        reference = analyze_rows(rows,config(),bootstrap_repetitions=20,seed=13)
        augmented = [dict(item,pred_full_J_total=10*item['direction_id']) for item in rows]
        augmented[0]['pred_full_J_total'] = None
        evidence = analyze_rows(augmented,config(),bootstrap_repetitions=20,seed=13)
        total = find_scene(evidence,1,FULL_J_TOTAL)
        self.assertEqual(total['units'],3)
        self.assertEqual(total['paired_units'],2)
        self.assertEqual(total['missing_or_invalid_units'],1)
        self.assertEqual(find_scene(evidence,1,FULL_J)['paired_units'],3)
        unit = next(item for item in evidence['aggregated_units']
                    if item['scene_id']=='1' and item['direction_id']=='1')
        self.assertEqual(unit['raw_predictions'][FULL_J],1)
        self.assertEqual(unit['raw_predictions'][FULL_J_TOTAL],10)
        self.assertFalse(unit['method_eligible'][FULL_J_TOTAL])
        self.assertTrue(unit['method_eligible'][FULL_J])
        self.assertEqual(evidence['paired_scene_bootstrap'],reference['paired_scene_bootstrap'])
        self.assertEqual(evidence['primary_incrementality'],reference['primary_incrementality'])
        only_total = [{key:value for key,value in item.items() if key!='pred_full_J'} for item in augmented]
        self.assertEqual(aggregate_direction_rows(only_total)['methods'],['A0','A1','A2','A3',FULL_J_TOTAL])

    def test_oracle_features_do_not_calibrate_deployable_features(self):
        deployable = [row(scene,direction,error=2*direction)
                      for scene in (1,2,3,4) for direction in (1,2,3)]
        oracle = [dict(item,true_error=100*item['direction_id'],feature_origin='full_J oracle')
                  for item in deployable]
        evidence = analyze_rows(deployable+oracle,config(),bootstrap_repetitions=0)
        scales = [item['scale'] for item in evidence['calibration_scales'] if item['evidence_scope']=='deployable']
        self.assertTrue(all(abs(value-2)<1e-12 for value in scales))
        self.assertEqual(evidence['primary_incrementality']['evidence_scope'],'deployable')


class BootstrapAndAUCTests(unittest.TestCase):
    def test_paired_scene_bootstrap_has_reproducible_positive_improvement_sign(self):
        pairs = [dict(scene_id=1,A1=4,A2=3,A3=2),dict(scene_id=2,A1=6,A2=5,A3=3)]
        first = paired_scene_bootstrap(pairs,repetitions=200,seed=11)
        self.assertEqual(first,paired_scene_bootstrap(pairs,repetitions=200,seed=11))
        self.assertEqual(first['stronger_point_baseline'],'A2')
        self.assertEqual(first['absolute_MAE_improvement'],1.5)
        self.assertEqual(first['relative_MAE_improvement'],0.375)
        self.assertEqual(first['improvement_probability'],1)
        self.assertLessEqual(first['absolute_95_percent_interval'][0],1.5)
        self.assertGreaterEqual(first['absolute_95_percent_interval'][1],1.5)

    def test_stronger_baseline_is_reselected_inside_each_cluster_draw(self):
        pairs = [dict(scene_id=1,A1=1,A2=9,A3=0.5),dict(scene_id=2,A1=9,A2=1,A3=0.5)]
        result = paired_scene_bootstrap(pairs,repetitions=200,seed=7)
        self.assertGreater(result['baseline_selection_counts']['A1'],0)
        self.assertGreater(result['baseline_selection_counts']['A2'],0)
        self.assertEqual(sum(result['baseline_selection_counts'].values()),200)
        self.assertFalse(result['calibration_refit_in_bootstrap'])

    def test_zero_baseline_and_single_scene_do_not_get_invented_relative_intervals(self):
        pairs = [dict(scene_id=1,A1=0,A2=0,A3=1),dict(scene_id=2,A1=0,A2=0,A3=1)]
        result = paired_scene_bootstrap(pairs,repetitions=20)
        self.assertIsNone(result['relative_MAE_improvement'])
        self.assertIsNone(result['relative_95_percent_interval'])
        self.assertEqual(result['relative_valid_draws'],0)
        self.assertEqual(result['improvement_probability'],0)
        self.assertEqual(paired_scene_bootstrap(pairs[:1])['repetitions_performed'],0)
        with self.assertRaises(ValueError):
            paired_scene_bootstrap([pairs[0],pairs[0]])

    def test_auc_requires_both_classes_and_preserves_mixed_draw_classes(self):
        self.assertIsNone(failure_auc([0.1,0.9],[0,0])['value'])
        self.assertIsNone(failure_auc([0.1,0.9],[1,1])['value'])
        self.assertEqual(failure_auc([0.1,0.9],[0,1])['value'],1)
        self.assertEqual(failure_auc([0.1,0.9],[1,0])['value'],0)
        self.assertEqual(failure_auc([1,1],[0,1])['value'],0.5)
        self.assertEqual(failure_auc([0.1,0.9],[0.25,0.75])['value'],0.75)
        self.assertEqual(failure_auc([0.1,0.9],[0,1],unit_weights=[2,3])['value'],1)
        with self.assertRaises(ValueError):
            failure_auc([1,2],[1])

    def test_missing_failure_labels_are_not_invented_from_error(self):
        rows = [row(scene,direction,error=100*direction)
                for scene in (1,2,3,4) for direction in (1,2,3)]
        result = analyze_rows(rows,config(),bootstrap_repetitions=0)
        item = find_scene(result,1)
        self.assertIsNone(item['failure_AUC'])
        self.assertEqual(item['failure_AUC_status'],'UNDEFINED')


class CSVTests(unittest.TestCase):
    def test_reporting_aliases_and_missing_source_are_explicit(self):
        alias = dict(scene=1,direction=1,delta=0.1,sigma=0,condition='nominal',
                     coefficient_error=2,A0_predicted_error=1,A1_predicted_error=1,
                     A2_predicted_error=1,A3_predicted_error=1,status='OK')
        aggregated = aggregate_direction_rows([alias])
        self.assertEqual(aggregated['units'][0]['true_error'],2)
        self.assertEqual(aggregated['units'][0]['noise_level'],0)
        with tempfile.TemporaryDirectory() as directory:
            evidence = analyze_direction_metrics(Path(directory)/'missing.csv',config(),bootstrap_repetitions=0)
            self.assertEqual(evidence['status'],'NOT_RUN')
            self.assertEqual(evidence['input_audit']['source_status'],'MISSING')
            self.assertIsNone(evidence['gate_decisions'])

    def test_saved_evidence_contains_no_nan_or_gate_verdict(self):
        rows = [row(scene,direction,error=2*direction)
                for scene in (1,2,3,4) for direction in (1,2,3)]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root/'direction_metrics.csv'
            with path.open('w',newline='') as stream:
                writer = csv.DictWriter(stream,fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
            evidence = analyze_direction_metrics(path,config(),bootstrap_repetitions=0,output_dir=root/'evidence')
            saved = json.loads((root/'evidence/STATISTICS_EVIDENCE.json').read_text())
            self.assertEqual(saved['schema'],'a22.statistics.evidence.v1')
            self.assertIsNone(saved['gate_decisions'])
            self.assertNotIn('NaN',(root/'evidence/STATISTICS_EVIDENCE.json').read_text())
            self.assertIn('per_scene_statistics.csv',evidence['artifact_paths'])


if __name__=='__main__':
    unittest.main()
