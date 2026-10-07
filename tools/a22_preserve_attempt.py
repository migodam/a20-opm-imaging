"""Metered immutable preservation of an interrupted A22 screening attempt."""
from __future__ import annotations
import time
ORIGIN = time.perf_counter()
import argparse
import json
from pathlib import Path
import shutil
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from a22.budget import A22Book, load_config, write_json
from a22.cli import register_source_receipts


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--job', required=True)
    args = parser.parse_args(argv)
    book = A22Book(ROOT, load_config(ROOT), stage='exception', job_id=args.job,
                   device='cpu', started_wall=ORIGIN, started_cpu=0.)
    status, detail = 'FAILED', {}
    try:
        register_source_receipts(ROOT)
        receipt = json.loads((ROOT/'results/jobs'/args.attempt/'job_receipt.json').read_text())
        if receipt['status'] != 'FAILED':
            raise ValueError('PRESERVATION_REQUIRES_FAILED_PAID_ATTEMPT')
        target = ROOT/'results/a22/attempt_archive'/args.attempt
        if target.exists():
            raise ValueError('ATTEMPT_ARCHIVE_ALREADY_EXISTS')
        source = ROOT/'results/a22/stage_a'
        with book.span('preserve_failed_attempt_artifacts', archive_copies=1):
            shutil.copytree(source, target/'stage_a')
            rows = [json.loads(line) for line in (source/'direction_metrics.jsonl').read_text().splitlines()
                    if line.strip()]
            detail = dict(event_id=args.attempt+'-controller-read-failure', campaign='A22',
                job_id=args.attempt, status='INFRASTRUCTURE_FAILURE', error_type='PermissionError',
                cause='Windows watchdog checkpoint read; retry handler required native delete-sharing reader',
                committed_rows=len(rows), invalid_QPs=sum(row.get('status') != 'OK' for row in rows),
                source_archive=str((target/'stage_a').relative_to(ROOT)),
                scientific_gate_failure=False,
                paid_receipt='results/jobs/'+args.attempt+'/job_receipt.json',
                restart_reuses_cached_labels=True)
            write_json(target/'PRESERVATION.json', detail)
            with (ROOT/'results/a22/FAILURE_LEDGER.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(detail, allow_nan=False)+'\n')
        status = 'COMPLETE'
        print(json.dumps(detail))
        return 0
    finally:
        book.finish(status, outcome=detail)


if __name__ == '__main__':
    raise SystemExit(main())
