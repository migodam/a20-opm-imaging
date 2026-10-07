"""R1-only inclusive receipts; frozen A22 files are never updated."""
from contextlib import contextmanager
from pathlib import Path
import json
import re
import time

from a20.costs import CostBook, BudgetExceeded, plain, write_json


def append(path, row):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(plain(row), allow_nan=False) + '\n')


def paid_history(root):
    path = Path(root)/'results/a22_r1/COST_LEDGER.jsonl'
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []
    additive = [row for row in rows if row.get('additive_receipt') is True]
    ids = [row['receipt_id'] for row in additive]
    if len(ids) != len(set(ids)):
        raise ValueError('DUPLICATE_R1_INCLUSIVE_RECEIPT')
    return {'cpu': sum(row.get('process_cpu_seconds', 0.) for row in additive),
            'gpu': sum(row.get('gpu_occupation_seconds', 0.) for row in additive),
            'backgrounds': sum(row.get('counts', {}).get('full_forward_calls', 0) for row in additive),
            'new_labels': sum(row.get('counts', {}).get('data_generation_F_calls', 0) for row in additive),
            'receipts': ids}


def external_receipt(root, identity, *, cpu=0., wall=0., gpu=0., counts=None,
                     status='COMPLETE', measurement='measured process CPU', detail=None):
    if min(cpu, wall, gpu) < 0:
        raise ValueError('NEGATIVE_R1_RECEIPT')
    prior = paid_history(root)
    if identity in prior['receipts']:
        raise ValueError('EXTERNAL_R1_RECEIPT_ALREADY_PAID')
    row = dict(event='inclusive_external_receipt', receipt_id=identity, additive_receipt=True,
               process_cpu_seconds=float(cpu), wall_seconds=float(wall), gpu_occupation_seconds=float(gpu),
               counts=counts or {}, status=status, measurement=measurement, detail=detail)
    append(Path(root)/'results/a22_r1/COST_LEDGER.jsonl', row)
    if status != 'COMPLETE':
        append(Path(root)/'results/a22_r1/FAILURE_LEDGER.jsonl', row)
    return row


class R1Book(CostBook):
    def __init__(self, root, config, job, *, device='cpu', started_wall=None):
        if not re.fullmatch(r'a22-r1-[A-Za-z0-9_-]+', job):
            raise ValueError('BAD_R1_JOB_NAME')
        self.root, self.config, self.job = Path(root), config, job
        self.directory = self.root/'results/a22_r1/jobs'/job
        self.directory.mkdir(parents=True, exist_ok=False)
        self.prior = paid_history(root)
        remaining_gpu = min(config['gpu_occupation_cap_seconds'],
                            config['parent_a22_gpu_cap_seconds']-config['historical_a22_gpu_seconds'])
        super().__init__(self.directory/'actions.jsonl', device=device,
                         prior_cpu=self.prior['cpu'], prior_gpu=self.prior['gpu'],
                         cpu_limit=config['cpu_cap_seconds'], gpu_limit=remaining_gpu,
                         cpu_reserve=20., gpu_reserve=10., metadata={'job': job})
        # Import and process startup are paid, rather than excluded from jobs.
        self.started_cpu = 0.
        if started_wall is not None:
            self.started_wall = started_wall
        self._done = False
        write_json(self.directory/'started.json', {'job': job, 'device': device, 'prior': self.prior})

    @contextmanager
    def span(self, label, **counters):
        if counters.get('data_generation_F_calls', 0) or counters.get('new_teacher_labels', 0):
            raise BudgetExceeded('R1_NEW_FULL_WAVE_LABELS_FORBIDDEN')
        if self.prior['backgrounds'] + self.counts.get('full_forward_calls', 0) + counters.get('full_forward_calls', 0) > self.config['known_background_rebuild_cap']:
            raise BudgetExceeded('R1_FOUR_KNOWN_BACKGROUND_CAP')
        if self.phase == 'online' and any(value and ('full_J' in key or 'full_jacobian' in key or 'full_tangent' in key or 'full_adjoint_solve' in key) for key, value in counters.items()):
            raise BudgetExceeded('R1_ONLINE_FULL_DERIVATIVE_FORBIDDEN')
        with super().span(label, **counters) as row:
            yield row

    @contextmanager
    def action_guard(self, action, *, role='online', **metadata):
        if action in ('perturbation_forward', 'data_generation', 'generate_data', 'teacher_label'):
            raise BudgetExceeded('R1_NEW_FULL_WAVE_LABELS_FORBIDDEN')
        if role == 'online' and action in ('truth', 'full_J', 'full_H', 'teacher', 'reference_step'):
            raise BudgetExceeded('R1_FORBIDDEN_ONLINE_INFORMATION')
        yield

    def finish(self, status, detail=None):
        if self._done:
            raise ValueError('R1_JOB_FINISHED_TWICE')
        receipt = dict(self.receipt(), event='inclusive_job_receipt', receipt_id=self.job,
                       additive_receipt=True, status=status, detail=detail,
                       nested_spans_nonadditive=True)
        write_json(self.directory/'job_receipt.json', receipt)
        append(self.root/'results/a22_r1/COST_LEDGER.jsonl', receipt)
        if status != 'COMPLETE':
            append(self.root/'results/a22_r1/FAILURE_LEDGER.jsonl', receipt)
        self._done = True
        return receipt
