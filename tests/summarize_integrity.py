#!/usr/bin/env python3
"""Compile existing test receipts; does not execute any physical action."""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'results/tests'

COVERAGE = {
    'complex_L_F_S_current_adjoints': ['complex_current_adjoints_and_metric'],
    'real_B_pullback_and_compressed_injection': ['real_material_B_adjoint_batched_and_compressed'],
    'original_jvp_vjp_adapter_equivalence': ['original_jvp_vjp_equal_adapter_and_factored_actions'],
    'source_frequency_real_packing_and_whitening': [
        'packing_whitening_multiple_sources_and_probe_columns',
        'multi_frequency_stack_uses_distinct_physics_shared_material'],
    'material_metric_and_gauge': ['material_metric_and_real_gauge_covariance',
        'projection_complex_adjoint_and_current_unitary_gauge'],
    'full_objective_and_full_tangent_FD': ['full_tangent_and_full_objective_finite_difference'],
    'frozen_Galerkin_and_Petrov_consistent_derivatives': [
        'fixed_galerkin_reduced_state_derivative_and_native_equivalence',
        'frozen_petrov_derivative_and_moving_least_squares_term'],
    'moving_Galerkin_and_LS_explicit_derivative_terms': [
        'moving_galerkin_basis_requires_explicit_basis_derivative',
        'frozen_petrov_derivative_and_moving_least_squares_term'],
    'A1_A2_tangent_contract_distinction': ['A1_full_state_tangent_distinguished_from_A2_derivative'],
    'exact_Schur_adjoint_resolvent_Galerkin_and_empty_U': [
        'exact_schur_actions_adjoint_resolvent_and_galerkin_equivalence'],
    'zero_seed_budgets_empty_projection_zero_J_deflation_and_nested_streams': [
        'seed_zero_budgets_and_zero_deflated_blocks',
        'real_physical_hierarchy_nested_streams_and_breakdown'],
    'singular_absolute_small_core_rejection_and_named_Petrov_fallback': [
        'singular_and_absolute_small_cores_rejected_and_fallback_named'],
    'constrained_KKT_Gaussian_voxel_and_full_gap_bounds': [
        'constrained_chart_quadratic_KKT_and_full_gap_bound',
        'tiny_voxel_quadratic_KKT_and_constraints'],
    'offline_teacher_payload_and_capability_rejection': [
        'online_payload_and_basis_capability_reject_offline_fields'],
    'material_refresh_cache_invalidation': [
        'material_refresh_invalidates_projection_and_cached_reduced_matrix'],
    'full_physics_state_material_owner_and_reduced_state_guards': [
        'full_tangent_and_adjoint_refuse_wrong_material_state',
        'full_physics_contract_refuses_native_and_adapter_reduced_states',
        'full_physics_rejects_foreign_frequency_and_geometry_models'],
    'budget_refusal_and_failed_action_costs': ['budget_rejection_and_failed_action_accounting'],
    'two_update_FULL_GN_A1_A2_smoke': ['tiny_two_update_nonlinear_full_A1_A2_smoke'],
    'supplied_algebra_delayed_path_and_fake_weak_regressions': [
        'frozen_protocol_algebra_and_counterexample_regressions'],
}


def main():
    paths = sorted(OUT.glob('attempt_*/receipt.json'))
    receipts = [json.loads(path.read_text()) for path in paths]
    latest = paths[-1].parent
    suite = json.loads((latest/'suite.json').read_text())
    cases = {row['test'].rsplit('.', 1)[-1].removeprefix('test_'): row for row in suite['cases']}
    coverage = {name: {'status': 'PASS' if all(cases.get(test, {}).get('status')=='PASS'
                 for test in tests) else 'FAIL_OR_MISSING', 'tests': ['test_'+test for test in tests]}
                for name, tests in COVERAGE.items()}
    metrics = {key: value for row in suite['cases'] for key, value in row.get('metrics', {}).items()}
    numerical = {key: value for key, value in metrics.items() if isinstance(value, float)}
    adjoints = {key: value for key, value in numerical.items() if 'adjoint' in key or 'pullback' in key}
    fds = {key: value for key, value in numerical.items() if key.endswith('_fd')}
    history = []
    for path in paths:
        report = json.loads((path.parent/'suite.json').read_text())
        for row in report['cases']:
            if row['status'] != 'PASS':
                latest_case = cases.get(row['test'].rsplit('.', 1)[-1].removeprefix('test_'), {})
                history.append({'attempt': path.parent.name, 'test': row['test'], 'status': row['status'],
                    'traceback': row.get('traceback'), 'subtest_failures': row.get('subtest_failures', []),
                    'failure_metrics': row.get('metrics', {}),
                    'final_same_test_status': latest_case.get('status', 'MISSING')})
    report = {
        'schema': 'a20.tests.G0_LOCAL.v1',
        'status': 'PASS' if suite['status']=='PASS' and all(row['status']=='PASS' for row in coverage.values()) else 'FAIL',
        'scope': 'Local interface and numerical integrity: real vector-Maxwell DenseDDA, 2^3 cells; separate supplied finite-dimensional algebra.',
        'scientific_scope': 'Does not close G1 representation or G2 total deployment cost; no six-object reconstruction performed by test worker.',
        'fixture': {'grid': [2, 2, 2], 'n_current': 24, 'p_material_chart': 6, 'p_material_voxel': 16,
                    'source_count': 3, 'receiver_count': 4, 'complex_channels_per_source': 8,
                    'real_data_dimension_per_frequency': 48, 'frequencies': [.9, 1.25],
                    'precision': 'complex128/float64', 'device': 'cpu', 'seed': 2026100501,
                    'synthetic_parent_id': 9020, 'whitening_scope': 'scalar normalization and non-diagonal real map; no calibrated covariance claim'},
        'tests': suite['tests'], 'passed': suite['passed'], 'latest_attempt': latest.name,
        'coverage': coverage,
        'numerical': {'maximum_paired_adjoint_relative_error': max(adjoints.values()),
                      'maximum_FD_relative_error': max(fds.values()), 'all_FD_errors': fds,
                      'moving_Galerkin_missing_term_relative_error': metrics['moving_Galerkin_omitted_term_error'],
                      'moving_LS_missing_term_relative_error': metrics['moving_LS_omitted_term_error'],
                      'Schur_Galerkin_equivalence_relative_error': metrics['Schur_Galerkin_equivalence'],
                      'constrained_chart_KKT_relative': metrics['constrained_result']['kkt_relative'],
                      'voxel_KKT_relative': metrics['voxel_result']['kkt_relative']},
        'budgets': {'test_attempt_count': len(receipts), 'cumulative_process_cpu_seconds': sum(row['inclusive_process_cpu_seconds'] for row in receipts),
                    'cumulative_attempt_wall_seconds': sum(row['wall_seconds'] for row in receipts),
                    'hard_cpu_limit_seconds': 120., 'all_attempt_receipts': receipts},
        'historical_failed_test_occurrences': history,
        'pre_execution_review_findings_fixed_by_parent': [
            'small voxel chart.Q=None solver branching', 'same-material cached full_state source selection',
            'ReducedJacobian.matrix cache checks Projection material version'],
        'tests_changed_paths': ['tests/test_backend_integrity.py', 'tests/run_integrity.py', 'tests/summarize_integrity.py'],
        'source_modifications_by_test_worker': [], 'hash_checks': 'NOT_RUN',
        'original_parent_physics': 'NOT_RUN', 'six_parent_physics': 'NOT_RUN',
        'source_fix_ownership': 'Parent Codex; this worker only edited tests and wrote results/tests receipts.',
        'run_command': 'PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONPATH=src "/Volumes/migodam\'s-external-brain/Research/Inv_SLAM/Gaussian/.venv_nn/bin/python" tests/run_integrity.py',
    }
    (OUT/'G0_LOCAL.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    print(f"G0_LOCAL {report['status']}: {suite['passed']}/{suite['tests']}; cumulative test CPU {report['budgets']['cumulative_process_cpu_seconds']:.3f}s")


if __name__ == '__main__':
    main()
