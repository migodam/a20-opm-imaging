"""R1 caps layered over unchanged A20 cumulative physical accounting."""
from __future__ import annotations
from contextlib import contextmanager
from pathlib import Path
import json
import time

from a20.costs import CostBook, BudgetExceeded, budget_history, plain
from a20.backend import ForbiddenAccess


def load_config(root):
    root = Path(root)
    base = json.loads((root/'configs/frozen.json').read_text())
    r1 = json.loads((root/'configs/a20_r1.json').read_text())
    return base | r1


def history(root):
    root = Path(root)
    cpu, gpu = budget_history(root)
    cpu += sum(r['process_cpu_seconds'] for r in json.loads(
        (root/'results/EXTERNAL_CPU_RECEIPTS.json').read_text()))
    ext = root/'results/a20_r1/external_cpu_receipts.json'
    external = json.loads(ext.read_text()) if ext.exists() else []
    cpu += sum(r['process_cpu_seconds'] for r in external)
    phases = {p: {'cpu': 0., 'gpu': 0.} for p in ('phase1', 'phase2')}
    for r in external:
        phases[r['phase']]['cpu'] += r['process_cpu_seconds']
    for path in (root/'results/jobs').glob('*/job_receipt.json'):
        r = json.loads(path.read_text())
        if r.get('r1_phase') in phases:
            phases[r['r1_phase']]['cpu'] += r['process_cpu_seconds']
            phases[r['r1_phase']]['gpu'] += r['gpu_occupation_seconds']
    return {'global_cpu': cpu, 'global_gpu': gpu, 'phases': phases,
            'r1_cpu': sum(v['cpu'] for v in phases.values()),
            'r1_gpu': sum(v['gpu'] for v in phases.values())}


def register_external(root, scope, seconds, *, phase='phase1', receipt=None,
                      measurement='inclusive measured process CPU'):
    path = Path(root)/'results/a20_r1/external_cpu_receipts.json'
    rows = json.loads(path.read_text()) if path.exists() else []
    if any(r['scope'] == scope for r in rows):
        raise ValueError('External scope already billed')
    rows.append({'scope': scope, 'phase': phase, 'process_cpu_seconds': float(seconds),
                 'receipt': receipt, 'measurement': measurement})
    path.write_text(json.dumps(rows, indent=2)+'\n')


class R1Book(CostBook):
    def __init__(self, root, config, phase, path, *, device='cpu', epilogue=False):
        self.root, self.config, self.r1_phase = Path(root), config, phase
        self.prior = history(root)
        super().__init__(path, device=device,
            prior_cpu=self.prior['global_cpu'], prior_gpu=self.prior['global_gpu'],
            cpu_limit=config['budget_cpu_seconds'], gpu_limit=config['budget_gpu_wall_seconds'],
            cpu_reserve=config['cpu_epilogue_reserve_seconds'],
            gpu_reserve=config['gpu_preoperation_reserve_seconds'])
        self.started_cpu = 0.  # includes imports in this process
        self.local_reserve = 0. if epilogue else config[phase+'_CPU_reserve']
        self.local_gpu_reserve = 0. if epilogue else config['corrective_GPU_reserve']

    def check(self):
        super().check()
        cpu = time.process_time()-self.started_cpu
        gpu = time.perf_counter()-self.started_wall if self.device == 'cuda' else 0.
        c = self.config
        if self.prior['r1_cpu']+cpu >= c['corrective_CPU_seconds']-self.local_reserve:
            raise BudgetExceeded('R1_TOTAL_CPU_CAP')
        if self.prior['r1_gpu']+gpu >= c['corrective_GPU_seconds']-self.local_gpu_reserve:
            raise BudgetExceeded('R1_TOTAL_GPU_CAP')
        p = self.prior['phases'][self.r1_phase]
        if p['cpu']+cpu >= c[self.r1_phase+'_CPU_seconds']-self.local_reserve:
            raise BudgetExceeded('R1_'+self.r1_phase.upper()+'_CPU_CAP')
        if p['gpu']+gpu >= c[self.r1_phase+'_GPU_seconds']-self.local_gpu_reserve:
            raise BudgetExceeded('R1_'+self.r1_phase.upper()+'_GPU_CAP')

    @contextmanager
    def span(self, label, **counters):
        if self.phase == 'legal_seed' and label in ('full_forward', 'full_tangent', 'full_adjoint'):
            raise ForbiddenAccess('LEGAL_SEED_FULL_PHYSICS_TEACHER_ACCESS:'+label)
        with super().span(label, **counters) as row:
            yield row

    def append(self, row):
        row = plain({'r1_phase': self.r1_phase, **row})
        super().append(row)
        with (self.root/'COST_LEDGER.jsonl').open('a') as f:
            f.write(json.dumps(row, allow_nan=False)+'\n')
        if row.get('status') == 'FAILED':
            with (self.root/'FAILURE_LEDGER.jsonl').open('a') as f:
                f.write(json.dumps({'failure_kind': 'nested_physical_span', **row}, allow_nan=False)+'\n')

    def receipt(self):
        return super().receipt() | {'r1_phase': self.r1_phase,
            'prior_R1_CPU_seconds': self.prior['r1_cpu'], 'prior_R1_GPU_seconds': self.prior['r1_gpu'],
            'r1_phase_caps': {'CPU': self.config[self.r1_phase+'_CPU_seconds'],
                              'GPU': self.config[self.r1_phase+'_GPU_seconds']}}
