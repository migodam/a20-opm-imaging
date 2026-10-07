"""Metered screening statistics and the preregistered parent entry rule.

This four-scene reducer cannot award formal Gate A PASS. It never calls
Maxwell, generates labels, trains a network, or launches a conditional stage.
"""
from __future__ import annotations

import time
ORIGIN = time.perf_counter()
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from a22.budget import A22Book, load_config, write_json
from a22.cli import register_source_receipts
from a22.statistics import analyze_direction_metrics


def decide(evidence, summary, config, preregistration):
    a3 = next((row for row in evidence['summaries'] if row['method']=='A3'
        and row['family']=='ALL' and row['noise_branch']=='all'
        and row['evidence_scope']=='deployable' and row['evaluation_split']=='held_scene'), None)
    pair = evidence.get('primary_incrementality') or {}
    expected = set(config['screening_scenes'])
    complete = (set(row['scene_id'] for row in summary.get('scenes', [])
                    if row.get('status')=='COMPLETE') == expected
                and summary.get('invalid_count')==0
                and a3 is not None and a3.get('status')=='RECORDED'
                and not pair.get('missing_scene_ids', []))
    rho = None if a3 is None else a3.get('median_scene_spearman')
    improvement = pair.get('relative_MAE_improvement')
    interval = pair.get('absolute_95_percent_interval')
    positive = (complete and rho is not None and improvement is not None
        and rho >= config['gate_A_correlation']
        and improvement >= config['gate_A_mae_improvement'])
    clear_negative = (complete and rho is not None and rho < config['gate_A_correlation']
        and interval is not None and len(interval)==2 and interval[1] <= 0.)
    status = 'POSITIVE' if positive else 'CLEAR_NEGATIVE' if clear_negative else 'PARTIAL'
    gate = 'FAIL' if clear_negative else 'PARTIAL'
    decision = dict(schema='a22.screening.decision.v1', status=status,
        screening_signal_positive=bool(positive), complete_screening=bool(complete),
        median_scene_spearman=rho, relative_MAE_improvement=improvement,
        absolute_95_percent_interval=interval, pair=pair,
        frozen_rule=preregistration['screening_entry_rule'],
        formal_24_scene_gate='NOT_RUN', formal_A_PASS=False,
        scope='four exposed scenes; LOSO screening only, conditional-on-fit scene bootstrap',
        next_action='resolve expansion blockers then run fixed 24-scene Stage A' if positive
                    else 'STOP before expansion, one-shot imaging and NN')
    gates = dict(A=dict(status=gate,
        reason='clear screening failure: weak correlation and nonpositive upper incrementality interval'
                if clear_negative else 'formal 24-scene evidence absent; screening cannot award PASS',
        evidence='results/a22/statistics/STATISTICS_EVIDENCE.json', screening=status),
        B=dict(status='NOT_RUN', reason='A is not formal PASS'),
        C=dict(status='NOT_RUN', reason='one-shot stage not entered'),
        D=dict(status='NOT_RUN', reason='A/B/C not all PASS; NN forbidden'),
        T=dict(status='NOT_ESTABLISHED', reason='no same-quality end-to-end timing comparison'))
    final = dict(schema='a22.gate.decision.v1', authority='parent Codex frozen rules',
        gates=gates, screening=decision,
        stages=dict(A='SCREENING_COMPLETE' if complete else 'PARTIAL', B='NOT_RUN', C='NOT_RUN'),
        trained_NN=False, nonlinear_reconstruction=False, publication='NOT_REQUESTED_LOCAL_ONLY',
        original_theory_and_A17_A21_unchanged=True)
    return decision, final


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--job', required=True)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    config = load_config(root)
    book = A22Book(root, config, stage='exception', job_id=args.job,
                   device='cpu', started_wall=ORIGIN, started_cpu=0.)
    status, detail = 'FAILED', {}
    try:
        register_source_receipts(root)
        with book.span('screening_scene_cluster_statistics', bootstrap_repetitions=2000):
            out = root/'results/a22/stage_a'
            summary = json.loads((out/'RUN_SUMMARY.json').read_text())
            evidence = analyze_direction_metrics(out/'direction_metrics.csv', config,
                mode='screen', scene_manifest=out/'scene_manifest.csv',
                bootstrap_repetitions=2000, seed=config['master_seed']+902,
                output_dir=root/'results/a22/statistics')
            preregistration = json.loads((root/'results/a22/PREREGISTRATION.json').read_text())
            decision, gates = decide(evidence, summary, config, preregistration)
            write_json(root/'results/a22/SCREENING_DECISION.json', decision)
            write_json(root/'results/a22/GATE_DECISION.json', gates)
            detail = dict(status=decision['status'], signal_positive=decision['screening_signal_positive'],
                          median_spearman=decision['median_scene_spearman'],
                          relative_MAE_improvement=decision['relative_MAE_improvement'],
                          gate_A=gates['gates']['A']['status'])
        status = 'COMPLETE'
        print(json.dumps(detail, allow_nan=False))
        return 0
    finally:
        book.finish(status, outcome=detail)


if __name__=='__main__':
    raise SystemExit(main())
