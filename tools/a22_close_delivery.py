"""Close local delivery accounting and export recorded costs, without physics."""
from __future__ import annotations
import time
ORIGIN = time.perf_counter()
import argparse
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from a22.budget import A22Book, history, load_config, register_external, write_json
from a22.cli import register_source_receipts
from a22.cost_summary import export_cost_csv


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--job', required=True)
    args = parser.parse_args(argv)
    config = load_config(ROOT)
    book = A22Book(ROOT, config, stage='exception', job_id=args.job,
                   device='cpu', started_wall=ORIGIN, started_cpu=0.)
    status, detail = 'FAILED', {}
    try:
        register_source_receipts(ROOT)
        with book.span('verify_local_delivery_prerequisites', delivery_reviews=1):
            gate = json.loads((ROOT/'results/a22/GATE_DECISION.json').read_text())
            audit = json.loads((ROOT/'results/a22/stage_a/EVIDENCE_COMPLETENESS_AUDIT.json').read_text())
            if (gate['gates']['A']['status'] not in ('PARTIAL','FAIL')
                    or gate['screening']['screening_signal_positive']
                    or not gate['screening']['complete_screening']):
                raise ValueError('STOP_DELIVERY_REQUIRES_COMPLETED_NONPOSITIVE_SCREENING')
            if audit['raw_rows'] != 2112 or audit['invalid_QPs'] != 0:
                raise ValueError('FINAL_DELIVERY_GRID_MISMATCH')
            if any(not (ROOT/name).is_file() for name in (
                'START_HERE.md','A22_IMPLEMENTATION_REPORT.md','A22_RESULTS_LEDGER.md',
                'A22_GATE_DECISION.md','A22_COMMANDS_AND_SEEDS.md')):
                raise ValueError('MISSING_MAIN_DELIVERY_DOCUMENT')
            detail = dict(scope='completed four-scene screening; full route stopped at Gate A',
                publication='LOCAL_ONLY_NOT_REQUESTED', stage_B='NOT_RUN', stage_C='NOT_RUN',
                neural_training=False, large_campaign=False, new_physics_calls=0)
            # Reserve the short post-receipt file export/source-control review
            # explicitly. It is a conservative CPU charge, never measured CPU.
            register_external(ROOT, 'a22-final-file-export-and-local-git-review', 10.,
                gpu_seconds=0., status='SOURCE_WORK_CONSERVATIVE',
                measurement='explicit 10-second conservative CPU allowance for post-receipt cost/document export and local Git verification; no physics/GPU')
        status = 'COMPLETE'
    finally:
        book.finish(status, outcome=detail)
    tail = time.process_time()
    costs = export_cost_csv(ROOT)
    totals = history(ROOT, config)
    manifest = dict(schema='a22.local.delivery.v1', source_base=config['source_freeze'],
        branch='a22-three-fold-opm', delivery_commit_reference='Git HEAD after local delivery commit; actual SHA in final response',
        status='COMPLETE_LOCAL_STOP_AT_PARTIAL_GATE_A', gates=gate['gates'],
        exposure='four historically exposed scenes; not a blind validation',
        known_background=config['background'], material_real_dimension=32, degree=1,
        actual_current_rank=32, scenes=config['screening_scenes'], clean_labels=32,
        recovery_case_rows=2112, statistical_scene_clusters=4, empirical_indicator=True,
        full_model_uniform_certificate=False, original_theory_and_backend_frozen=True,
        full_32_solution_vectors='NOT_RECORDED', spatial_one_shot_reconstructions='NOT_RUN',
        cost_summary_status=costs['status'], live_accounting_jobs=costs['live_jobs'],
        accounting_issues=costs['issues'], unresolved_accounting_records=costs['unresolved_records'],
        charged_CPU_seconds=totals['a22_cpu'], CUDA_related_occupation_seconds=totals['a22_gpu'],
        CUDA_occupation_limit_seconds=config['gpu_wall_cap_seconds'],
        stage_GPU_seconds=totals['stage_gpu_seconds'],
        generation_full_wave_evaluations=totals['counts'].get('data_generation_F_calls',0),
        generation_full_wave_limit=config['perturbation_evaluation_cap'],
        new_scene_labels=totals['counts'].get('new_teacher_labels',0),
        CPU_contains_explicit_conservative_allowances=True,
        CPU_and_GPU_are_not_added_together=True, nested_spans_not_additive=True,
        old_A20_A21_costs_excluded=True, publication='LOCAL_ONLY', trained_NN=False,
        nonlinear_reconstruction=False, operator_action_details='ACTION_ACCOUNTING.json',
        post_receipt_CPU_allowance_seconds=10.,
        measured_post_receipt_export_CPU_seconds=time.process_time()-tail)
    write_json(ROOT/'results/a22/FINAL_DELIVERY_MANIFEST.json', manifest)
    if time.process_time()-tail > 10.:
        raise RuntimeError('POST_RECEIPT_EXPORT_EXCEEDED_CONSERVATIVE_CPU_ALLOWANCE')
    print(json.dumps({key:manifest[key] for key in ('status','cost_summary_status',
        'live_accounting_jobs','charged_CPU_seconds','CUDA_related_occupation_seconds',
        'generation_full_wave_evaluations','new_scene_labels')}, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
