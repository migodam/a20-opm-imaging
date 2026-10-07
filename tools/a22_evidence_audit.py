"""Metered completeness/noise/array export from saved screening records only."""
from __future__ import annotations
import time
ORIGIN = time.perf_counter()
import argparse
import csv
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys
import numpy as np
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from a22.budget import A22Book, load_config, write_json
from a22.cli import register_source_receipts
from a22.evaluate import stage_a_case_key


def true(value):
    return str(value).lower() in ('true', '1')


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--job', required=True)
    args = parser.parse_args(argv)
    config = load_config(ROOT)
    book = A22Book(ROOT, config, stage='exception', job_id=args.job,
                   device='cpu', role='offline_evaluation', started_wall=ORIGIN, started_cpu=0.)
    status, detail = 'FAILED', {}
    try:
        register_source_receipts(ROOT)
        out = ROOT/'results/a22/stage_a'
        with book.span('saved_screening_completeness_and_noise_audit', evidence_audits=1):
            rows = [json.loads(line) for line in (out/'direction_metrics.jsonl').read_text().splitlines()
                    if line.strip()]
            keys = [stage_a_case_key(row) for row in rows]
            if len(keys) != len(set(keys)):
                raise ValueError('DUPLICATE_SCREENING_CASE_KEYS')
            by_scene = Counter(int(row['scene_id']) for row in rows)
            expected_per_scene = (config['finite_screening_directions'] * len(config['amplitude_fractions'])
                * sum(1 if n == 0 else config['noise_draws'] for n in config['noise_levels'])
                * len(config['interventions']))
            if set(by_scene) != set(config['screening_scenes']) or any(n != expected_per_scene for n in by_scene.values()):
                raise ValueError('INCOMPLETE_REGISTERED_SCREENING_GRID')
            if any(not true(row['online_predictions_frozen_before_offline_full_J']) for row in rows):
                raise ValueError('MISSING_ONLINE_BEFORE_OFFLINE_ATTESTATION')
            paired = defaultdict(list)
            for row in rows:
                paired[stage_a_case_key(row)[:-1]].append(row)
            for members in paired.values():
                if ({row['intervention'] for row in members} != set(config['interventions'])
                        or len(members) != len(config['interventions'])
                        or len({row['noise_seed'] for row in members}) != 1):
                    raise ValueError('UNPAIRED_PHYSICAL_CALIBRATION_NOISE_SEEDS')
            # One row represents the common solve; A0-A3 forecast that same
            # error. This export does not invent its unrecorded 32D solution.
            valid = [row for row in rows if row['status'] == 'OK']
            np.savez_compressed(out/'directional_reconstructions.npz',
                case_keys=np.asarray(['|'.join(map(str, stage_a_case_key(row))) for row in valid]),
                true_target_coefficients=np.asarray([float(row['raw_target_coefficient']) for row in valid]),
                estimated_target_coefficients=np.asarray([float(row['raw_target_coefficient'])
                    + float(row['coefficient_signed_error']) for row in valid]),
                signed_target_errors=np.asarray([float(row['coefficient_signed_error']) for row in valid]),
                full_32_coordinate_error_norms=np.asarray([float(row['material_error']) for row in valid]),
                status=np.asarray('OBSERVED_DIRECTIONAL_COEFFICIENT_RECONSTRUCTIONS'),
                full_solution_vectors=np.asarray('NOT_RECORDED; no spatial Stage B images were run'))
            groups = defaultdict(list)
            for row in valid:
                if float(row['noise_level']) > 0:
                    key = tuple(row[name] for name in ('scene_id', 'direction_id', 'amplitude_level',
                                                      'noise_level', 'intervention'))
                    groups[key].append(row)
            noise_rows = []
            for key, members in sorted(groups.items()):
                errors = np.asarray([float(row['coefficient_signed_error']) for row in members])
                level = float(key[3])
                complete = len(members) == config['noise_draws']
                deviation = float(np.std(errors, ddof=1)) if complete and len(errors)>1 else None
                noise_rows.append(dict(zip(('scene_id', 'direction_id', 'amplitude_level',
                    'noise_level', 'intervention'), key), draws=len(members),
                    status='RECORDED' if complete else 'INCOMPLETE',
                    empirical_signed_coefficient_SD=deviation,
                    empirical_gain_per_white_noise_SD=None if deviation is None else deviation/level,
                    regularized_linear_witness_gain=float(members[0]['noise_sd'])/level,
                    interpretation='constrained estimator SD across 16 paired proper-Gaussian noise draws; empirical, not a linear identity'))
            with (out/'noise_amplification.csv').open('w', newline='', encoding='utf-8') as stream:
                writer = csv.DictWriter(stream, fieldnames=list(noise_rows[0]))
                writer.writeheader()
                writer.writerows(noise_rows)
            scene_audits = {str(sid): json.loads((out/f'scene_{sid}'/'OFFLINE_material_model_audit.json').read_text())
                            for sid in config['screening_scenes']}
            labels = []
            for path in sorted(out.glob('scene_*/OFFLINE_label_*.npz')):
                with np.load(path, allow_pickle=False) as archive:
                    labels.append(dict(path=str(path.relative_to(ROOT)),
                        numerical_backward_residual=float(archive['backward_residual'])
                            if 'backward_residual' in archive.files else None,
                        numerical_residual_status='RECORDED' if 'backward_residual' in archive.files else 'LEGACY_NOT_RECORDED',
                        source_contract_status='CURRENT_CONTRACT' if 'cache_schema' in archive.files else 'LEGACY_AW_AND_FREEZE_VALIDATED'))
            detail = dict(status='COMPLETE', raw_rows=len(rows), unique_case_keys=len(set(keys)),
                rows_by_scene=dict(by_scene), expected_rows_per_scene=expected_per_scene,
                invalid_QPs=sum(row['status'] != 'OK' for row in rows),
                actual_current_ranks=sorted({int(row['actual_rank']) for row in rows}),
                historical_exposed_rows=sum(true(row['historical_exposed']) for row in rows),
                full_model_uniform_certificate_rows=sum(true(row['full_model_uniform_certificate']) for row in rows),
                absolute_target_below_relative_floor=sum(abs(float(row['raw_target_coefficient']))
                    < config['material_absolute_floor'] for row in valid),
                primary_metric='absolute directional coefficient error; no relative floor in Gate A',
                covariance_model='proper complex Gaussian: Re/Im variance sigma_complex^2/2',
                paired_calibration_noise_case_groups=len(paired), paired_noise_seed_identity=True,
                noise_groups=len(noise_rows), noise_incomplete_groups=sum(row['status']!='RECORDED' for row in noise_rows),
                scene_model_audits=scene_audits, finite_label_cache=labels,
                cached_clean_label_count=len(labels), new_physics_calls=0,
                directional_array='results/a22/stage_a/directional_reconstructions.npz',
                full_32_solution_vectors='NOT_RECORDED', Stage_B_spatial_images='NOT_RUN')
            write_json(out/'EVIDENCE_COMPLETENESS_AUDIT.json', detail)
        status = 'COMPLETE'
        print(json.dumps({key:detail[key] for key in ('raw_rows','unique_case_keys','invalid_QPs',
            'actual_current_ranks','cached_clean_label_count','noise_groups','noise_incomplete_groups')}, allow_nan=False))
        return 0
    finally:
        book.finish(status, outcome=detail)


if __name__ == '__main__':
    raise SystemExit(main())
