"""Independent A21 accounting; historical A20 receipts are never rewritten."""
from __future__ import annotations

import json
import math
from pathlib import Path
import time

from a20.costs import BudgetExceeded, CostBook, plain


def load_config(root):
    return json.loads((Path(root) / 'configs/a21.json').read_text(encoding='utf-8'))


def _seconds(value, name):
    value = float(value)
    if not math.isfinite(value) or value < 0:
        raise ValueError('INVALID_ACCOUNTING_SECONDS:' + name)
    return value


def history(root, config=None):
    """Only inclusive A21 job receipts and unique external scopes are additive."""
    root = Path(root)
    config = load_config(root) if config is None else config
    cpu = gpu = 0.0
    jobs = []
    for path in sorted((root / 'results/jobs').glob('a21-*/job_receipt.json')):
        row = json.loads(path.read_text(encoding='utf-8'))
        cpu += _seconds(row['process_cpu_seconds'], 'job CPU')
        gpu += _seconds(row.get('gpu_occupation_seconds', 0), 'job GPU')
        jobs.append(path.parent.name)
    path = root / 'results/a21/external_cpu_receipts.json'
    external = json.loads(path.read_text(encoding='utf-8')) if path.exists() else []
    scopes = set()
    for row in external:
        scope = row['scope']
        if scope in scopes:
            raise ValueError('DUPLICATE_EXTERNAL_ACCOUNTING_SCOPE')
        scopes.add(scope)
        cpu += _seconds(row['process_cpu_seconds'], 'external CPU')
        gpu += _seconds(row.get('GPU_seconds', 0), 'external GPU')
    inherited_cpu = _seconds(config['historical_CPU_seconds'], 'historical CPU')
    inherited_gpu = _seconds(config['historical_GPU_seconds'], 'historical GPU')
    return dict(a21_cpu=cpu, a21_gpu=gpu, new_CPU_seconds=cpu, new_GPU_seconds=gpu,
                global_cpu=inherited_cpu + cpu, global_gpu=inherited_gpu + gpu,
                historical_CPU_seconds=inherited_cpu, historical_GPU_seconds=inherited_gpu,
                jobs=jobs, external_scopes=sorted(scopes),
                billing_authority='inclusive A21 job receipts + unique external scopes + frozen historical carry',
                nested_spans_not_additive=True)


def register_external(root, scope, seconds, *, gpu_seconds=0.0, receipt=None,
                      measurement='inclusive measured controller CPU', status='MEASURED',
                      config=None):
    root = Path(root)
    config = load_config(root) if config is None else config
    cpu = _seconds(seconds, 'external CPU')
    gpu = _seconds(gpu_seconds, 'external GPU')
    prior = history(root, config)
    if scope in prior['external_scopes']:
        raise ValueError('EXTERNAL_SCOPE_ALREADY_BILLED')
    if prior['a21_cpu'] + cpu > config['anatomy_CPU_seconds']:
        raise BudgetExceeded('A21_TOTAL_CPU_CAP')
    if prior['a21_gpu'] + gpu > config['anatomy_GPU_seconds']:
        raise BudgetExceeded('A21_TOTAL_GPU_CAP')
    if prior['global_cpu'] + cpu > config['budget_cpu_seconds']:
        raise BudgetExceeded('A20_CUMULATIVE_CPU_CAP')
    if prior['global_gpu'] + gpu > config['budget_gpu_wall_seconds']:
        raise BudgetExceeded('A20_CUMULATIVE_GPU_CAP')
    path = root / 'results/a21/external_cpu_receipts.json'
    rows = json.loads(path.read_text(encoding='utf-8')) if path.exists() else []
    rows.append(dict(scope=str(scope), process_cpu_seconds=cpu, GPU_seconds=gpu,
                     receipt=receipt, measurement=measurement, status=status))
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(rows, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    temporary.replace(path)


class A21Book(CostBook):
    """Charge imports, report/failure work, and validation child CPU exactly once."""
    def __init__(self, root, config, path=None, *, device='cpu', epilogue=False,
                 job_cpu_limit=None):
        if device not in ('cpu', 'cuda'):
            raise ValueError('UNREGISTERED_DEVICE')
        self.root, self.config = Path(root), config
        self.prior = history(root, config)
        super().__init__(path, device=device,
                         prior_cpu=self.prior['global_cpu'], prior_gpu=self.prior['global_gpu'],
                         cpu_limit=config['budget_cpu_seconds'],
                         gpu_limit=config['budget_gpu_wall_seconds'],
                         cpu_reserve=0 if epilogue else config['cpu_epilogue_reserve_seconds'],
                         gpu_reserve=0 if epilogue else config['gpu_preoperation_reserve_seconds'])
        # Python process CPU begins at zero, before imports, including failed imports.
        self.started_cpu = 0.0
        self.child_cpu_seconds = 0.0
        self.live_child_cpu_seconds = 0.0
        self.local_cpu_reserve = 0 if epilogue else config['anatomy_CPU_reserve_seconds']
        self.local_gpu_reserve = 0 if epilogue else config['anatomy_GPU_reserve_seconds']
        self.job_cpu_limit = job_cpu_limit

    def elapsed_cpu(self):
        return time.process_time() + self.child_cpu_seconds + self.live_child_cpu_seconds

    def remaining_cpu_seconds(self):
        used = self.elapsed_cpu()
        values = [self.config['anatomy_CPU_seconds'] - self.local_cpu_reserve - self.prior['a21_cpu'] - used,
                  self.cpu_limit - self.cpu_reserve - self.prior_cpu - used]
        if self.job_cpu_limit is not None:
            values.append(float(self.job_cpu_limit) - used)
        return max(0.0, min(values))

    def add_child_cpu(self, seconds):
        self.child_cpu_seconds += _seconds(seconds, 'validation child CPU')
        self.live_child_cpu_seconds = 0.0

    def check(self):
        # The parent primitive also records RSS and CUDA peak memory. Its CPU
        # check omits child CPU, so the cumulative check below includes it.
        super().check()
        if not self.enforce:
            return
        cpu = self.elapsed_cpu()
        gpu = time.perf_counter() - self.started_wall if self.device == 'cuda' else 0.0
        if self.prior_cpu + cpu >= self.cpu_limit - self.cpu_reserve:
            raise BudgetExceeded('A20_CUMULATIVE_CPU_CAP_WITH_RESERVE')
        if self.prior['a21_cpu'] + cpu >= self.config['anatomy_CPU_seconds'] - self.local_cpu_reserve:
            raise BudgetExceeded('A21_TOTAL_CPU_CAP_WITH_RESERVE')
        if self.prior['a21_gpu'] + gpu >= self.config['anatomy_GPU_seconds'] - self.local_gpu_reserve:
            raise BudgetExceeded('A21_TOTAL_GPU_CAP_WITH_RESERVE')
        if self.job_cpu_limit is not None and cpu >= self.job_cpu_limit:
            raise BudgetExceeded('A21_VALIDATION_CPU_CAP_120_SECONDS')

    def append(self, row):
        row = plain({'campaign': 'A21', **row})
        super().append(row)
        destination = self.root / 'results/a21'
        destination.mkdir(parents=True, exist_ok=True)
        with (destination / 'COST_LEDGER.jsonl').open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(row, allow_nan=False) + '\n')
        if row.get('status') == 'FAILED':
            with (destination / 'FAILURE_LEDGER.jsonl').open('a', encoding='utf-8') as handle:
                handle.write(json.dumps({'failure_kind': 'nested_span', **row}, allow_nan=False) + '\n')

    def receipt(self):
        receipt = super().receipt()
        receipt['process_cpu_seconds'] = self.elapsed_cpu()
        receipt.update(controller_process_cpu_seconds=time.process_time(),
                       child_process_cpu_seconds=self.child_cpu_seconds,
                       prior_A21_CPU_seconds=self.prior['a21_cpu'],
                       prior_A21_GPU_seconds=self.prior['a21_gpu'],
                       historical_CPU_seconds=self.prior['historical_CPU_seconds'],
                       historical_GPU_seconds=self.prior['historical_GPU_seconds'],
                       A21_CPU_cap=self.config['anatomy_CPU_seconds'],
                       A21_GPU_cap=self.config['anatomy_GPU_seconds'],
                       nested_spans_not_additive=True, failed_imports_included=True,
                       measurement='inclusive controller process CPU since startup + terminated child CPU; imports and failures included',
                       new_SHA256_checks=0)
        return receipt
