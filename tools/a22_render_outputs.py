"""Metered artifact rendering from saved A22 evidence; no physics or fitting."""
from __future__ import annotations
import time
ORIGIN = time.perf_counter()
import argparse
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from a22.budget import A22Book, load_config
from a22.cli import register_source_receipts
from a22.reporting import generate_reports, generate_statistical_plots


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--job', required=True)
    args = parser.parse_args(argv)
    book = A22Book(ROOT, load_config(ROOT), stage='exception', job_id=args.job,
                   device='cpu', started_wall=ORIGIN, started_cpu=0.)
    status, detail = 'FAILED', {}
    try:
        register_source_receipts(ROOT)
        with book.span('render_saved_screening_evidence', report_renders=1):
            raw = generate_reports(ROOT)
            canonical = generate_statistical_plots(ROOT,
                ROOT/'results/a22/statistics/STATISTICS_EVIDENCE.json')
            detail = dict(raw_artifacts=raw, statistical_artifacts=canonical,
                          physics_calls=0, new_calibration_fits=0, new_bootstrap_draws=0,
                          main_documents='parent Chinese scientific review follows rendering')
        status = 'COMPLETE'
        print(json.dumps(dict(status=status, job_id=args.job,
            statistical_figures='figures/a22/statistical', physics_calls=0)))
        return 0
    finally:
        book.finish(status, outcome=detail)


if __name__ == '__main__':
    raise SystemExit(main())
