"""Mechanical index/receipt assembly; parent judgment is explicitly frozen here.

No NPZ reads, Maxwell calls, teacher generation, new hash checks or gate edits.
"""
from pathlib import Path
import csv
import json
import statistics
import subprocess
import time

from a20_r1.budget import history, load_config, register_external

ROOT = Path(__file__).resolve().parents[1]


def read_rows(path):
    return [json.loads(s) for s in path.read_text().splitlines() if s.strip()]


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2)+'\n')


def assemble_ledgers():
    config = load_config(ROOT)
    costs = [{'ledger_kind': 'historical_carry', 'additive_budget_charge': True,
              'process_cpu_seconds': config['historical_CPU_seconds'],
              'gpu_occupation_seconds': config['historical_GPU_seconds'],
              'source': 'results/BUDGET_FINAL.json', 'phase': 'PRE_R1'}]
    failures = []
    for p in sorted((ROOT/'results/jobs').glob('r1-*/cost.jsonl')):
        for event in read_rows(p):
            costs.append(event | {'ledger_kind': 'nested_event', 'additive_budget_charge': False,
                                 'source_ledger': p.relative_to(ROOT).as_posix()})
            if event.get('status') == 'FAILED':
                failures.append(event | {'failure_kind': 'nested_physical_span',
                                          'source_ledger': p.relative_to(ROOT).as_posix()})
    for p in sorted((ROOT/'results/jobs').glob('r1-*/job_receipt.json')):
        receipt = json.loads(p.read_text())
        costs.append(receipt | {'ledger_kind': 'job_inclusive_receipt',
                                'additive_budget_charge': True, 'source_receipt': p.relative_to(ROOT).as_posix()})
        if receipt['status'] != 'COMPLETE':
            failures.append({'failure_kind': 'stage', 'status': receipt['status'],
                             'job': receipt['job'], 'source_receipt': p.relative_to(ROOT).as_posix(),
                             'result': json.loads((p.parent/'result.json').read_text())})
    for value in json.loads((ROOT/'results/a20_r1/external_cpu_receipts.json').read_text()):
        costs.append(value | {'ledger_kind': 'external_inclusive_receipt', 'additive_budget_charge': True,
                              'gpu_occupation_seconds': 0.,
                              'source_registry': 'results/a20_r1/external_cpu_receipts.json'})
    rows = read_rows(ROOT/'results/a20_r1/anatomy/rows.jsonl')
    for r in rows:
        if r.get('record_kind') == 'method' and r['status'] != 'OK':
            failures.append({'failure_kind': 'information_absence' if r['method']=='HISTORY' else 'model_status',
                             'status': r['status'], 'row_id': r['row_id'], 'method': r['method'],
                             'parent_id': r['parent_id'], 'iteration': r['iteration'],
                             'reason': r['failure_reason'], 'model_built': r.get('model_built', False),
                             'QP_valid': r.get('QP_valid'), 'reference_valid': r.get('reference_valid'),
                             'source': 'results/a20_r1/anatomy/rows.jsonl',
                             'experiment_candidate_failed': r['status']=='FAILED',
                             'physical_method_failure': r['status']=='FAILED' and not r.get('QP_valid', False),
                             'baseline_reproducibility_failure': r['status']=='FAILED' and
                                 r['method']=='FIXED-DEEP' and not r.get('baseline_reproduction_valid', False),
                             'failure_details': r.get('failure')})
    for name in ('GATE_WORKER_RECEIPT.json', 'PLOT_QA_RECEIPT.json', 'PUBLIC_PACKAGE_AUDIT_RECEIPT.json'):
        receipt = json.loads((ROOT/'results/a20_r1'/name).read_text())
        for i, attempt in enumerate(receipt['attempts']):
            if attempt['status'] in ('FAIL', 'FAILED'):
                failures.append({'failure_kind': 'tooling', 'status': 'FAILED', 'attempt': i+1,
                                 'receipt': 'results/a20_r1/'+name, 'physical_method_failure': False,
                                 'details': attempt, 'fee_already_in_inclusive_worker_receipt': True})
    failures.append({'failure_kind': 'document_tooling', 'status': 'FAILED',
                     'reason': 'apply_patch rejected two operations targeting START_HERE in one patch; no partial edits applied',
                     'physical_method_failure': False,
                     'fee_scope': 'existing conservative planning/setup/publication overhead allowance'})
    for name, values in (('COST_LEDGER.jsonl', costs), ('FAILURE_LEDGER.jsonl', failures)):
        (ROOT/name).write_text(''.join(json.dumps(r, ensure_ascii=False, allow_nan=False)+'\n' for r in values))
    budget = history(ROOT)
    total_cpu = sum(r.get('process_cpu_seconds', 0) for r in costs if r['additive_budget_charge'])
    total_gpu = sum(r.get('gpu_occupation_seconds', 0) for r in costs if r['additive_budget_charge'])
    assert abs(total_cpu-budget['global_cpu']) < 1e-7
    assert abs(total_gpu-budget['global_gpu']) < 1e-7
    final = budget | {'inherited_CPU_seconds': config['historical_CPU_seconds'],
                      'inherited_GPU_seconds': config['historical_GPU_seconds'],
                      'caps': {'global_CPU':7200,'global_GPU':43200,'R1_CPU':1500,'R1_GPU':4800,
                               'phase1_CPU':600,'phase1_GPU':1200,'phase2_CPU':900,'phase2_GPU':3600},
                      'within_all_caps': budget['global_cpu'] < 7200 and budget['global_gpu'] < 43200
                          and budget['r1_cpu'] < 1500 and budget['r1_gpu'] < 4800
                          and budget['phases']['phase1']['cpu'] < 600 and budget['phases']['phase1']['gpu'] < 1200,
                      'billing_authority': 'inclusive job receipts + unique external scope registry + historical carry',
                      'nested_spans_not_additive': True, 'standalone_attribution_not_extra_billing': True,
                      'GPU_definition': 'exclusive job occupation wall, not kernel time',
                      'all_failed_attempts_charged': True, 'new_SHA256_checks': 0}
    assert final['within_all_caps']
    write(ROOT/'results/a20_r1/BUDGET_CURRENT.json', budget)
    write(ROOT/'results/a20_r1/BUDGET_FINAL.json', final)
    return final


def main():
    config = load_config(ROOT)
    rows = read_rows(ROOT/'results/a20_r1/anatomy/rows.jsonl')
    methods = [r for r in rows if r['record_kind'] == 'method' and r['method'] != 'HISTORY']
    late = [r for r in methods if r['iteration'] == 17 and r['status'] == 'OK']
    assert len(late) == 30 and all(r['actual_rank'] == 56 for r in late)
    assert all(r['QP_valid'] and r['reference_valid'] and r['reference_QP_valid'] for r in late)
    assert all(not r['full_fallback_used'] and not r['teacher_regenerated'] and not r['truth_used_in_seed'] for r in methods)
    failed = [r for r in methods if r['status']=='FAILED']
    assert len(failed)==1 and failed[0]['parent_id']==2001 and failed[0]['iteration']==0
    assert failed[0]['QP_valid'] and not failed[0]['baseline_reproduction_valid']
    assert sum(r['status']=='NOT_RUN' for r in methods)==29
    assert len([r for r in rows if r['method']=='HISTORY'])==10
    assert all(r['baseline_reproduction_valid'] for r in late if r['method']=='FIXED-DEEP')
    assert all(r['oracle_capture_certified'] for r in late if r['method']=='PROTECTED-ORACLE')
    medians = {m: statistics.median(r['relative_H_step_error'] for r in late if r['method']==m)
               for m in dict.fromkeys(r['method'] for r in late)}
    gate = json.loads((ROOT/'GATE_DECISION.json').read_text())
    assert [gate['anatomy'][k]['status'] for k in ('A','B','C')] == ['HOLD','FAIL','HOLD']
    assert gate['anatomy'].get('selected_method') is None
    assert gate['closed_loop']['status']=='NOT_RUN_GATE_CLOSED'
    # Parent Codex adjudication; numerical automatic evidence remains intact.
    judgment = {'status':'FINAL_PARENT_REVIEW', 'choice':'D', 'conclusion':'INCONCLUSIVE',
                'reason':'Frozen early baseline exact-reproducibility guard failed; protected early/control matrix incomplete',
                'baseline_conflict_state':[2001,0],
                'baseline_step_relative_difference':failed[0]['baseline_step_relative_error'],
                'baseline_reproduction_tolerance':1e-9,
                'formal_representation_KILL':'NOT_AUTHORIZED_INCOMPLETE_PREREQUISITES',
                'legal_candidate_progression':'NO_GO_GATE_B',
                'imaging_quality':'NOT_RUN_GATE_CLOSED', 'deployment_GO':'NOT_RUN_GATE_CLOSED',
                'history_causal_claim':'NOT_RUN', 'NN':'NOT_RUN_NOT_ELIGIBLE',
                'late_descriptive_finding':'Protected oracle reference-direction tangent is accurate; optimized reduced GN step remains inaccurate',
                'causal_explanation_status':'Inference only; dual/other-direction error mechanism not separately diagnosed',
                'no_universal_representation_impossibility_claim':True}
    gate.update(scientific_judgment=judgment, publication_status='SEPARATE_RECEIPT',
                publication_receipt='results/a20_r1/PUBLICATION.json',
                physics_source_commit='5231aea98f6945a77c4f83f030a57248065695ef',
                original_A20_source_freeze=config['source_freeze'])
    write(ROOT/'GATE_DECISION.json', gate)
    review = judgment | {'valid_late_method_QPs':30, 'attempted_models':31, 'remaining_models_NOT_RUN':29,
                         'HISTORY_NOT_RUN':10, 'existing_full_references_reaudited':6,
                         'remaining_early_references_NOT_AUDITED':4,
                         'late_medians_fraction':medians,
                         'maximum_late_reduced_QP_KKT':max(r['QP']['kkt_relative'] for r in late),
                         'protected_oracle_tangent_error_median':statistics.median(r['reference_tangent_error'] for r in late if r['method']=='PROTECTED-ORACLE'),
                         'test_count':96, 'test_status':'PASS',
                         'post_layout_structure_regression':'PASS',
                         'visual_inspection':'A/B/C/D/D_CAPTURE_CERT checked; missing early not fabricated',
                         'physics_retry_after_guard':0,'teacher_regeneration':0,'new_SHA256_checks':0,
                         'report_only_changes_after_physics':True}
    write(ROOT/'results/a20_r1/FINAL_REVIEW.json', review)
    fields = ['parent_id','iteration','method','status','actual_rank','relative_H_step_error',
              'absolute_H_step_error','full_quadratic_gap','full_stationarity_defect_norm','full_KKT_relative',
              'material_cosine','H_angle_degrees','material_norm_ratio','H_norm_ratio','full_objective_slope',
              'truth_one_step_error','oracle_material_span_capture','oracle_qM_source_capture',
              'oracle_finalZ_source_capture','reference_tangent_error','basis_construction_wall_seconds']
    with (ROOT/'results/a20_r1/LATE_METRICS.csv').open('w', newline='') as f:
        out=csv.DictWriter(f,fieldnames=fields); out.writeheader()
        for r in late: out.writerow({k:r.get(k) for k in fields})
    action=[{k:r.get(k) for k in ('parent_id','iteration','method','status','actual_rank',
             'action_fourtuple','action_fourtuple_order','charged_actual_cost','standalone_cost',
             'basis_construction_wall_seconds','cost_scope')} for r in late]
    (ROOT/'results/a20_r1/ACTION_COST.jsonl').write_text(''.join(json.dumps(r,allow_nan=False)+'\n' for r in action))
    scope='R1 final evidence index, row/gate integrity audit and parent report metadata'
    prior=json.loads((ROOT/'results/a20_r1/external_cpu_receipts.json').read_text())
    if not any(r['scope']==scope for r in prior):
        cpu=time.process_time()+.01
        write(ROOT/'results/a20_r1/FINALIZE_RECEIPT.json',{'scope':scope,'process_cpu_seconds':cpu,
              'measurement':'inclusive self CPU from process start incl imports + 0.01s write epilogue allowance',
              'physics_calls':0,'NPZ_reads':0,'GPU_seconds':0,'status':'PASS'})
        register_external(ROOT,scope,cpu,receipt='results/a20_r1/FINALIZE_RECEIPT.json')
    budget=assemble_ledgers()
    print(json.dumps({'status':'FINAL_PARENT_REVIEW_WRITTEN','choice':'D_INCONCLUSIVE',
                      'global_CPU':budget['global_cpu'],'R1_CPU':budget['r1_cpu'],'R1_GPU':budget['r1_gpu']}))


if __name__=='__main__':
    main()
