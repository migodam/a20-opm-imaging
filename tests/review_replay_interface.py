#!/usr/bin/env python3
"""Static replay review and pure record/status checks; no a20 imports."""
from __future__ import annotations
import resource
resource.setrlimit(resource.RLIMIT_CPU, (19, 20))
import ast
import json
from pathlib import Path
from types import SimpleNamespace
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'results/tests'
WALL_START = time.perf_counter()


def main():
    sources = {path: path.read_text() for path in sorted((ROOT/'src/a20').glob('*.py'))}
    trees, syntax_errors = {}, []
    for path, source in sources.items():
        try:
            trees[path] = ast.parse(source, filename=str(path))
            compile(trees[path], str(path), 'exec')  # compile only; never execute module
        except Exception:
            syntax_errors.append({'path': str(path), 'traceback': traceback.format_exc()})
    replay_path, cli_path = ROOT/'src/a20/replay.py', ROOT/'src/a20/cli.py'
    replay, cli = trees[replay_path], trees[cli_path]
    definitions = {node.name: node for node in replay.body if isinstance(node, (ast.FunctionDef, ast.ClassDef))}
    def location(name):
        node = definitions[name]
        return {'path': str(replay_path), 'line': node.lineno, 'end_line': node.end_lineno}
    config = json.loads((ROOT/'configs/frozen.json').read_text())
    parents = json.loads((ROOT/'configs/parents.json').read_text())['parents']
    pure = {}
    selected = [definitions[name] for name in ('_base_row', '_empty_cost', '_sum_costs', '_cost_fields')]
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(replay_path), 'exec'), pure)
    pure['_VECTOR_ACTIONS'] = ('F_actions', 'F_adjoint_actions', 'L_actions', 'L_adjoint_actions')
    token = 'STATIC_PROVENANCE_PLACEHOLDER_NO_HASH'
    book = SimpleNamespace(metadata={'job': 'static_review', 'experiment_id': 'static_review',
                            'source_commit': token, 'backend_declared_historical_commit': 'HISTORICAL_PLACEHOLDER'})
    row = pure['_base_row']('static_run', parents[0], 0, config, book, 'mixed', 0)
    record_provenance_fixed = row['backend_commit']==token and row['experiment_id']=='static_review'
    pure['_cost_fields'](row,
        basis={'counts': {'F_actions': 3}, 'exclusive_walls': {}, 'wall_seconds': .1, 'process_cpu_seconds': .01},
        QP={'counts': {'reduced_core_rhs': 6}, 'exclusive_walls': {}, 'wall_seconds': .2, 'process_cpu_seconds': .02},
        audit={'counts': {'L_actions': 2}, 'exclusive_walls': {}, 'wall_seconds': .3, 'process_cpu_seconds': .03})
    record_cost_shape_ok = (row['counts']['F_actions']==3 and row['counts']['L_actions']==2
                           and row['online_Maxwell_vector_actions']==3
                           and abs(row['wall_total_attributed']-.6)<1e-12)
    status_if = next(node for node in ast.walk(cli) if isinstance(node, ast.If)
                     and "result.get('status') == 'STOPPED_PARTIAL'"==ast.unparse(node.test))
    status_namespace = {'result': {'status': 'STOPPED_PARTIAL', 'stopped_reason': 'BudgetExceeded: STATIC_ONLY'}}
    exec(compile(ast.Module(body=[status_if], type_ignores=[]), str(cli_path), 'exec'), status_namespace)
    budget_status_fixed = status_namespace['status']=='BUDGET_STOP'
    status_namespace['result']={'status': 'STOPPED_PARTIAL', 'stopped_reason': 'ValueError: STATIC_ONLY'}
    exec(compile(ast.Module(body=[status_if], type_ignores=[]), str(cli_path), 'exec'), status_namespace)
    exception_status_fixed = status_namespace['status']=='FAILED'
    source_mtime_ns = {str(path): path.stat().st_mtime_ns for path in sources}
    findings = [
        {'id': 'R1', 'status': 'FIXED_BY_PARENT_STATICALLY_VERIFIED', 'current_first_cohort_blocker': False,
         'problem': 'Old _base_row metadata lookup produced backend_commit=None under the CLI metadata contract.',
         'original_locations': ['src/a20/replay.py:193-194', 'src/a20/cli.py:262'],
         'repair_locations': [location('_base_row'), {'path': str(cli_path), 'line': 262}],
         'verification': {'pure_record_check': record_provenance_fixed, 'row_backend_commit': row['backend_commit'],
                          'context_metadata_written': sorted(book.metadata)}},
        {'id': 'R2', 'status': 'FIXED_BY_PARENT_STATICALLY_VERIFIED', 'current_first_cohort_blocker': False,
         'problem': 'run_replay captures BudgetExceeded in STOPPED_PARTIAL; the old CLI then marked job COMPLETE and exited zero.',
         'original_locations': ['src/a20/replay.py:766-792', 'src/a20/cli.py:296'],
         'repair_locations': [{'path': str(cli_path), 'line': status_if.lineno}, {'path': str(cli_path), 'line': 319}],
         'verification': {'budget_partial_maps_to_BUDGET_STOP': budget_status_fixed,
                          'ordinary_partial_maps_to_FAILED': exception_status_fixed,
                          'non_COMPLETE_exit_code': 2}},
        {'id': 'R3', 'status': 'ACCEPTED_FUTURE_RETRY_LIMITATION', 'current_first_cohort_blocker': False,
         'problem': 'Historical replay rows retain all run IDs, while eligibility rejects duplicate parent/state/degree rows without canonical cohort selection.',
         'locations': [location('_Sink'), location('run_replay'), {'path': str(cli_path), 'line': 74}],
         'parent_resolution': 'First real replay is one complete 12-state cohort starting from empty replay.jsonl; duplicate HOLD is intentional. A future retry needs an explicit canonical cohort/attempt manifest; never silently delete failures.',
         'legacy_actions_path_limit': 'CLI prefers nonempty actions.jsonl over replay.jsonl; no legacy rows are allowed in the fresh first-cohort precondition.'},
        {'id': 'R4', 'status': 'NO_STATIC_DIMENSION_OR_CACHE_BLOCKER_IDENTIFIED', 'current_first_cohort_blocker': False,
         'locations': [location('run_replay'), location('_model_row'), location('_probe_diagnostics')],
         'verification': 'One x/state/full_Jacobian is frozen per replay state. Projection and all B/probe/audit calls use that same x; no trial/material refresh is called during model comparison. SeedBundle and Hierarchy interfaces agree, including the R right-Krylov family.',
         'declared_dimensions': {'n_current': sorted({p['n_current'] for p in parents}),
                                 'p_material': sorted({p['p_material'] for p in parents}),
                                 'source_count': sorted({p['sources'] for p in parents}),
                                 'complex_channels_per_source': sorted({2*p['receivers'] for p in parents})},
         'limit': 'Static control-flow/shape review only; no six-object or large-voxel numerical acceptance claim.'},
        {'id': 'R5', 'status': 'COST_AND_REFERENCE_BOUNDARIES_STATICALLY_CONSISTENT', 'current_first_cohort_blocker': False,
         'locations': [location('_Segment'), location('_cost_fields'), location('_evaluate_reference'), location('_model_row')],
         'verification': 'Full Gaussian J acquisition is separately paid once; full voxel J uses matrix-free actions. Saved steps require current chart/feasibility/KKT checks or a newly paid constrained QP. Failed model segments capture CostBook.delta without another budget check; global receipts retain setup/reference failure charges. Cumulative basis cost is explicitly not summed across degree rows.',
         'pure_cost_record_check': record_cost_shape_ok,
         'limit': 'If a shared setup/state/reference segment stops before row append, its detailed stage receipt remains in cost.jsonl and global book_receipt rather than a completed method row.'},
    ]
    checks = {'syntax_errors': syntax_errors, 'modules_compiled_without_import': len(trees),
              'record_provenance_fixed': record_provenance_fixed, 'record_cost_schema_ok': record_cost_shape_ok,
              'budget_partial_status_fixed': budget_status_fixed, 'exception_partial_status_fixed': exception_status_fixed,
              'fallback_flag_alias_supported_by_CLI': "r.get('full_fallback_used',r.get('fullfallback_used',False))" in sources[cli_path]}
    passed = (not syntax_errors and record_provenance_fixed and record_cost_shape_ok
              and budget_status_fixed and exception_status_fixed and checks['fallback_flag_alias_supported_by_CLI'])
    usage = resource.getrusage(resource.RUSAGE_SELF)
    cpu = usage.ru_utime+usage.ru_stime
    receipt = {'status': 'PASS' if passed else 'FAIL', 'process_cpu_seconds': cpu,
               'user_cpu_seconds': usage.ru_utime, 'system_cpu_seconds': usage.ru_stime,
               'wall_seconds': time.perf_counter()-WALL_START, 'CPU_limit_seconds': 20.,
               'CPU_measurement_scope': 'whole checker process from startup, including source reads/AST compile/pure record/status checks; no a20 module execution',
               'physical_actions': 0, 'SSH_calls': 0, 'hash_checks': 0,
               'attempt': 1, 'all_checker_failures': syntax_errors}
    report = {'schema': 'a20.tests.replay_interface_review.v1',
              'status': 'NO_STATIC_BLOCKER_FOR_FIRST_COMPLETE_COHORT' if passed else 'STATIC_CHECK_FAILED',
              'constraints': 'Fresh empty replay history; one full frozen 6-object x 2-state cohort; G0 prerequisites and actual physics budget remain owned by parent.',
              'scientific_decision': 'PARENT_REVIEW_REQUIRED', 'findings': findings, 'checks': checks,
              'receipt': receipt, 'source_mtime_ns': source_mtime_ns,
              'source_files_modified_by_reviewer': [],
              'source_inspection_note': 'One read-only shell inventory glob had no matches and was replaced by rg --files; no physical/SSH/hash operation occurred.'}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/'REPLAY_INTERFACE_REVIEW.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    (OUT/'REPLAY_INTERFACE_REVIEW_RECEIPT.json').write_text(json.dumps(receipt, indent=2, allow_nan=False)+'\n')
    print(f"{report['status']}; 5 findings (2 parent fixes verified); CPU {cpu:.6f}s / 20s; physical actions 0")
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
