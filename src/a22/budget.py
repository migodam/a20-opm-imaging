"""A22-only accounting and action gates; historical A21 costs are descriptive.

Only inclusive job/external receipts are additive. Nested spans describe work,
not extra resource charges. CPU is measured without a campaign CPU cap. CUDA
occupancy is inclusive job wall time with independent frozen stage caps.
"""
from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
import json
import math
import os
from pathlib import Path
import re
import time
import uuid

from a20.costs import BudgetExceeded, CostBook, plain


GPU_WALL_CAP = 32400.0
STAGE_GPU_CAPS = {
    'screen_health': 1800.0, 'features': 3600.0, 'direction': 7200.0,
    'image': 5400.0, 'runtime': 7200.0, 'train': 5400.0, 'exception': 1800.0,
}
DATA_GENERATION_F_CAP = 192
NEW_TEACHER_LABEL_CAP = 9
OFFLINE_ROLES = frozenset({'offline_label', 'offline_evaluation', 'reference'})
ROLES = OFFLINE_ROLES | {'online', 'health'}
OFFLINE_ACTIONS = frozenset({
    'full_J', 'full_H', 'full_jacobian', 'full_hessian', 'truth', 'truth_current',
    'truth_material', 's_F', 'e_F', 'full_GN_solution', 'teacher', 'teacher_label',
    'new_teacher_label',
})
GENERATION_ACTIONS = frozenset({
    'perturbation_forward', 'perturbation', 'data_generation',
    'generate_data', 'new_teacher_label', 'health_fd_forward', 'finite_difference_forward',
})
COUNTER_ALIASES = {
    'perturbation_F_calls': 'data_generation_F_calls',
    'data_F_calls': 'data_generation_F_calls',
    'generation_F_calls': 'data_generation_F_calls',
    'new_labels': 'new_teacher_labels',
}

# A watchdog reader can temporarily deny delete/rename sharing on Windows.
# Five attempts have at most 0.15 seconds of backoff, included in job wall time.
_WINDOWS_REPLACE_ERRORS = frozenset({5, 32, 33})
_ATOMIC_REPLACE_RETRY_SECONDS = (0.01, 0.02, 0.04, 0.08)


def write_json(path, value):
    """Atomically publish A22 accounting with bounded Windows sharing retries.

    Readers see an entire old or new snapshot; the target is never unlinked.
    A unique same-directory temporary file also isolates concurrent writers.
    Exhausted or unrelated errors propagate with the old target and temporary
    snapshot intact, retaining the attempted counters as diagnostic evidence.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    temporary.write_text(json.dumps(plain(value), indent=2, allow_nan=False) + '\n',
                         encoding='utf-8')
    for attempt in range(len(_ATOMIC_REPLACE_RETRY_SECONDS) + 1):
        try:
            temporary.replace(path)
            return
        except PermissionError as error:
            if (getattr(error, 'winerror', None) not in _WINDOWS_REPLACE_ERRORS
                    or attempt == len(_ATOMIC_REPLACE_RETRY_SECONDS)):
                raise
            time.sleep(_ATOMIC_REPLACE_RETRY_SECONDS[attempt])


def _seconds(value, name):
    value = float(value)
    if not math.isfinite(value) or value < 0:
        raise ValueError('INVALID_ACCOUNTING_SECONDS:' + name)
    return value


def _counters(values):
    result = Counter()
    for key, value in values.items():
        if isinstance(value, bool):
            raise ValueError('INVALID_ACTION_COUNTER')
        numeric = float(value)
        if not math.isfinite(numeric) or numeric < 0 or numeric != int(numeric):
            raise ValueError('INVALID_ACTION_COUNTER')
        result[COUNTER_ALIASES.get(str(key), str(key))] += int(numeric)
    return dict(result)


def job_id(value):
    if not isinstance(value, str) or not re.fullmatch(r'a22-[A-Za-z0-9_-]{1,100}', value):
        raise ValueError('INVALID_A22_JOB_ID')
    return value


def load_config(root):
    path = Path(root) / 'configs/a22.json'
    return normalize_config(json.loads(path.read_text(encoding='utf-8')) if path.exists() else {})


def normalize_config(config=None):
    """Allow smaller frozen caps, never an extension or transfer between stages."""
    result = dict(config or {})
    limit = result.get('gpu_wall_cap_seconds', result.get('budget_gpu_wall_seconds', GPU_WALL_CAP))
    result['gpu_wall_cap_seconds'] = _seconds(limit, 'A22 GPU cap')
    if result['gpu_wall_cap_seconds'] > GPU_WALL_CAP:
        raise ValueError('A22_GPU_CAP_CANNOT_BE_EXTENDED')
    supplied = result.get('stage_gpu_caps_seconds', result.get('stage_gpu_wall_seconds', {}))
    if not isinstance(supplied, dict) or set(supplied) - set(STAGE_GPU_CAPS):
        raise ValueError('UNREGISTERED_A22_STAGE')
    stage_caps = dict(STAGE_GPU_CAPS)
    for stage, cap in supplied.items():
        stage_caps[stage] = _seconds(cap, stage + ' GPU cap')
        if stage_caps[stage] > STAGE_GPU_CAPS[stage]:
            raise ValueError('A22_STAGE_CAP_CANNOT_BE_EXTENDED')
    result['stage_gpu_caps_seconds'] = stage_caps
    for key, default in (('data_generation_F_cap', DATA_GENERATION_F_CAP),
                         ('new_teacher_label_cap', NEW_TEACHER_LABEL_CAP),
                         ('physical_correction_cap', 1)):
        raw = result.get(key, result.get('perturbation_evaluation_cap', default)
                         if key == 'data_generation_F_cap' else
                         result.get('correction_events', default)
                         if key == 'physical_correction_cap' else default)
        value = _counters({key: raw})[key]
        if value > default:
            raise ValueError('A22_ACTION_CAP_CANNOT_BE_EXTENDED')
        result[key] = value
    result['gpu_stop_reserve_seconds'] = _seconds(result.get('gpu_stop_reserve_seconds', 0), 'GPU stop reserve')
    return result


def _json_rows(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def _append_json(path, row):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(plain(row), allow_nan=False) + '\n')


def _validated_receipt(row):
    row = plain(dict(row))
    identity = job_id(row.get('job_id', row.get('job')))
    if row.get('campaign', 'A22') != 'A22':
        raise ValueError('NON_A22_RECEIPT')
    stage = row.get('stage')
    if stage not in STAGE_GPU_CAPS:
        raise ValueError('UNREGISTERED_A22_STAGE')
    row.update(campaign='A22', job_id=identity, stage=stage)
    row['process_cpu_seconds'] = _seconds(row.get('process_cpu_seconds', 0), 'job CPU')
    row['wall_seconds'] = _seconds(row.get('wall_seconds', 0), 'job wall')
    row['gpu_occupation_seconds'] = _seconds(row.get('gpu_occupation_seconds', 0), 'job GPU')
    if row.get('device', 'cpu') not in ('cpu', 'cuda'):
        raise ValueError('UNREGISTERED_DEVICE')
    if row.get('device', 'cpu') == 'cpu' and row['gpu_occupation_seconds'] != 0:
        raise ValueError('CPU_JOB_CANNOT_BILL_GPU_OCCUPATION')
    row['counts'] = _counters(row.get('counts', {}))
    stage_usage = row.get('stage_gpu_seconds', {stage: row['gpu_occupation_seconds']})
    if not isinstance(stage_usage, dict) or set(stage_usage) - set(STAGE_GPU_CAPS):
        raise ValueError('INVALID_A22_STAGE_ACCOUNTING')
    row['stage_gpu_seconds'] = {key: _seconds(stage_usage.get(key, 0), key + ' GPU') for key in STAGE_GPU_CAPS}
    if not math.isclose(sum(row['stage_gpu_seconds'].values()), row['gpu_occupation_seconds'], rel_tol=1e-9, abs_tol=1e-6):
        raise ValueError('A22_STAGE_GPU_SUM_MUST_EQUAL_INCLUSIVE_JOB')
    corrections = row.get('corrections', {})
    if not isinstance(corrections, dict):
        raise ValueError('INVALID_CORRECTION_RECEIPT')
    row['corrections'] = _counters(corrections)
    return row


def history(root, config=None, *, exclude_job=None):
    """Final receipts supersede live checkpoints; each unique job bills once."""
    root = Path(root)
    config = load_config(root) if config is None else normalize_config(config)
    rows = []
    for directory in sorted((root / 'results/jobs').glob('a22-*')):
        if not directory.is_dir() or directory.name == exclude_job:
            continue
        path = directory / 'job_receipt.json'
        live = False
        if not path.exists():
            path = directory / 'accounting_checkpoint.json'
            live = True
        if path.exists():
            row = _validated_receipt(json.loads(path.read_text(encoding='utf-8')))
            if row['job_id'] != directory.name:
                raise ValueError('A22_RECEIPT_JOB_ID_MISMATCH')
            rows.append((row, live))
    cpu = gpu = wall = 0.0
    stages = Counter({stage: 0.0 for stage in STAGE_GPU_CAPS})
    counts, corrections = Counter(), Counter()
    identities, live_ids = [], []
    for row, live in rows:
        identity = row['job_id']
        if identity in identities:
            raise ValueError('DUPLICATE_A22_JOB_RECEIPT')
        identities.append(identity)
        if live:
            live_ids.append(identity)
        cpu += row['process_cpu_seconds']
        gpu += row['gpu_occupation_seconds']
        wall += row['wall_seconds']
        stages.update(row['stage_gpu_seconds'])
        counts.update(row['counts'])
        corrections.update(row['corrections'])
    registry = root / 'results/a22/external_cpu_receipts.json'
    external = json.loads(registry.read_text(encoding='utf-8')) if registry.exists() else []
    scopes = set()
    for row in external:
        scope = row['scope']
        if not isinstance(scope, str) or not scope or scope in scopes:
            raise ValueError('DUPLICATE_EXTERNAL_ACCOUNTING_SCOPE')
        scopes.add(scope)
        cpu += _seconds(row['process_cpu_seconds'], 'external CPU')
        paid_gpu = _seconds(row.get('gpu_occupation_seconds', row.get('GPU_seconds', 0)), 'external GPU')
        gpu += paid_gpu
        wall += _seconds(row.get('wall_seconds', 0), 'external wall')
        if paid_gpu:
            stage = row.get('stage')
            if stage not in STAGE_GPU_CAPS:
                raise ValueError('EXTERNAL_GPU_REQUIRES_REGISTERED_STAGE')
            stages[stage] += paid_gpu
        counts.update(_counters(row.get('counts', {})))
        corrections.update(_counters(row.get('corrections', {})))
    return dict(a22_cpu=cpu, a22_gpu=gpu, new_CPU_seconds=cpu, new_GPU_seconds=gpu,
                wall_seconds=wall, stage_gpu_seconds=dict(stages), counts=dict(counts),
                corrections=dict(corrections), jobs=identities, live_jobs=live_ids,
                external_scopes=sorted(scopes), CPU_cap=None,
                historical_A21_costs='record only; excluded from A22 limits',
                billing_authority='inclusive A22 job receipts/checkpoints + unique external scopes',
                nested_spans_not_additive=True, CPU_and_GPU_resources_not_summed=True)


def merge_receipt(root, row, config=None):
    """Persist an immutable receipt even when failed work exceeded a hard cap."""
    root = Path(root)
    row = _validated_receipt(row)
    path = root / 'results/jobs' / row['job_id'] / 'job_receipt.json'
    if path.exists():
        prior = _validated_receipt(json.loads(path.read_text(encoding='utf-8')))
        if prior != row:
            raise ValueError('CONFLICTING_IMMUTABLE_A22_RECEIPT')
        return False
    write_json(path, row)
    _append_json(root / 'results/a22/JOB_LEDGER.jsonl', {'event': 'job_finished', **row})
    _append_json(root / 'results/a22/COST_LEDGER.jsonl', {'event': 'job_receipt', **row})
    if row.get('status') in ('FAILED', 'BUDGET_REFUSED', 'TIMEOUT', 'CANCELLED'):
        _append_json(root / 'results/a22/FAILURE_LEDGER.jsonl', dict(failure_kind='job', **row))
    return True


def register_external(root, scope, seconds, *, gpu_seconds=0.0, wall_seconds=0.0,
                      stage=None, counts=None, receipt=None, measurement='measured CPU',
                      status='MEASURED', config=None):
    """Idempotent external accounting. Actual paid overages are never erased."""
    root = Path(root)
    if not isinstance(scope, str) or not scope:
        raise ValueError('INVALID_EXTERNAL_SCOPE')
    gpu = _seconds(gpu_seconds, 'external GPU')
    if gpu and stage not in STAGE_GPU_CAPS:
        raise ValueError('EXTERNAL_GPU_REQUIRES_REGISTERED_STAGE')
    row = dict(scope=scope, process_cpu_seconds=_seconds(seconds, 'external CPU'),
               gpu_occupation_seconds=gpu, wall_seconds=_seconds(wall_seconds, 'external wall'),
               stage=stage, counts=_counters(counts or {}), receipt=receipt,
               measurement=str(measurement), status=str(status))
    path = root / 'results/a22/external_cpu_receipts.json'
    rows = json.loads(path.read_text(encoding='utf-8')) if path.exists() else []
    matches = [existing for existing in rows if existing['scope'] == scope]
    if matches:
        if len(matches) == 1 and matches[0] == row:
            return False
        raise ValueError('CONFLICTING_EXTERNAL_ACCOUNTING_SCOPE')
    rows.append(row)
    write_json(path, rows)
    _append_json(root / 'results/a22/COST_LEDGER.jsonl', dict(event='external_receipt', **row))
    if status in ('FAILED', 'TIMEOUT', 'BUDGET_REFUSED'):
        _append_json(root / 'results/a22/FAILURE_LEDGER.jsonl', dict(failure_kind='external', **row))
    return True


class A22Book(CostBook):
    """Action-entry cap enforcement, paid failures, and inclusive job receipts."""
    def __init__(self, root, config=None, path=None, *, stage='screen_health',
                 job_id=None, device='cpu', role='online', gates=None,
                 cache_sufficient=False, epilogue=False, metadata=None,
                 started_wall=None, started_cpu=0.0, enforce=True):
        if stage not in STAGE_GPU_CAPS or device not in ('cpu', 'cuda') or role not in ROLES:
            raise ValueError('UNREGISTERED_A22_STAGE_DEVICE_OR_ROLE')
        self.root = Path(root)
        self.config = load_config(root) if config is None else normalize_config(config)
        identity = job_id or (metadata or {}).get('job_id') or (metadata or {}).get('job')
        if identity is None and path is not None and Path(path).parent.name.startswith('a22-'):
            identity = Path(path).parent.name
        self.job_id = globals()['job_id'](identity or 'a22-' + uuid.uuid4().hex)
        self.stage, self.job_stage, self.role = stage, stage, role
        self._stage_gpu_paid = Counter({key: 0.0 for key in STAGE_GPU_CAPS})
        self.gates, self.cache_sufficient = dict(gates or {}), bool(cache_sufficient)
        self.corrections = Counter()
        self.child_cpu_seconds = self.live_child_cpu_seconds = 0.0
        self.started_cpu_origin = _seconds(started_cpu, 'CPU origin')
        self.epilogue = bool(epilogue)
        self._finished = None
        import threading
        self._checkpoint_lock = threading.Lock()
        directory = self.root / 'results/jobs' / self.job_id
        directory.mkdir(parents=True, exist_ok=True)
        if (directory / 'job_receipt.json').exists():
            raise ValueError('A22_JOB_ID_ALREADY_FINISHED')
        reservation = directory / 'accounting_started.json'
        try:
            descriptor = os.open(reservation, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            raise ValueError('A22_JOB_ID_ALREADY_RESERVED') from None
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            json.dump(dict(campaign='A22', job_id=self.job_id, stage=stage, device=device,
                           status='STARTED', pid=os.getpid()), stream)
        self.prior = history(self.root, self.config, exclude_job=self.job_id)
        super().__init__(path or directory / 'cost.jsonl', device=device,
                         prior_cpu=0, prior_gpu=self.prior['a22_gpu'],
                         cpu_limit=float('inf'), gpu_limit=self.config['gpu_wall_cap_seconds'],
                         cpu_reserve=0, gpu_reserve=0,
                         metadata={'job_id': self.job_id, 'stage': stage, **(metadata or {})}, enforce=enforce)
        self.started_cpu = self.started_cpu_origin
        if started_wall is not None:
            self.started_wall = float(started_wall)
        self._stage_started_wall = self.started_wall
        _append_json(self.root / 'results/a22/JOB_LEDGER.jsonl',
                     dict(event='job_started', campaign='A22', job_id=self.job_id,
                          stage=stage, device=device, status='STARTED'))
        self._checkpoint()

    def elapsed_cpu(self):
        return max(0.0, time.process_time() - self.started_cpu_origin) + self.child_cpu_seconds + self.live_child_cpu_seconds

    def add_child_cpu(self, seconds):
        self.child_cpu_seconds += _seconds(seconds, 'child CPU')
        self.live_child_cpu_seconds = 0.0
        self._checkpoint()

    def remaining_cpu_seconds(self):
        return float('inf')

    def _current_prior(self):
        return history(self.root, self.config, exclude_job=self.job_id)

    def _stage_usage(self, now=None):
        usage = Counter(self._stage_gpu_paid)
        if self.device == 'cuda':
            usage[self.stage] += max(0.0, (time.perf_counter() if now is None else now) - self._stage_started_wall)
        return dict(usage)

    @contextmanager
    def stage_scope(self, stage):
        """Charge each GPU wall interval to exactly one active budget stage."""
        if stage not in STAGE_GPU_CAPS:
            raise ValueError('UNREGISTERED_A22_STAGE')
        old = self.stage
        now = time.perf_counter()
        if self.device == 'cuda':
            self._stage_gpu_paid[old] += max(0.0, now - self._stage_started_wall)
        self.stage, self._stage_started_wall = stage, now
        self._checkpoint()
        try:
            self.preflight()
            yield
        finally:
            now = time.perf_counter()
            if self.device == 'cuda':
                self._stage_gpu_paid[self.stage] += max(0.0, now - self._stage_started_wall)
            self.stage, self._stage_started_wall = old, now
            self._checkpoint()

    def remaining_gpu_seconds(self):
        prior = self._current_prior()
        stages = self._stage_usage()
        elapsed = sum(stages.values())
        reserve = 0 if self.epilogue else self.config['gpu_stop_reserve_seconds']
        return max(0.0, min(self.config['gpu_wall_cap_seconds'] - prior['a22_gpu'] - elapsed,
                            self.config['stage_gpu_caps_seconds'][self.stage] - prior['stage_gpu_seconds'][self.stage] - stages[self.stage]) - reserve)

    def _refuse(self, reason, **details):
        row = dict(campaign='A22', job_id=self.job_id, stage=self.stage,
                   event='budget_refusal', event_id=uuid.uuid4().hex,
                   status='BUDGET_REFUSED', reason=reason, **details)
        _append_json(self.root / 'results/a22/FAILURE_LEDGER.jsonl', row)
        _append_json(self.root / 'results/a22/COST_LEDGER.jsonl', row)
        raise BudgetExceeded(reason)

    def preflight(self, *, gpu_seconds=0.0, counters=None):
        gpu_seconds = _seconds(gpu_seconds, 'requested GPU wall')
        proposed = _counters(counters or {})
        if not self.enforce:
            return
        prior = self._current_prior()
        if self.device == 'cuda':
            stages = self._stage_usage()
            elapsed = sum(stages.values())
            reserve = 0 if self.epilogue else self.config['gpu_stop_reserve_seconds']
            if prior['a22_gpu'] + elapsed + gpu_seconds + reserve >= self.config['gpu_wall_cap_seconds']:
                self._refuse('A22_TOTAL_GPU_WALL_CAP')
            for stage in STAGE_GPU_CAPS:
                extra = gpu_seconds + reserve if stage == self.stage else 0.0
                used = prior['stage_gpu_seconds'][stage] + stages[stage] + extra
                if ((stage == self.stage and used >= self.config['stage_gpu_caps_seconds'][stage])
                        or (stages[stage] > 0 and used > self.config['stage_gpu_caps_seconds'][stage])):
                    self._refuse('A22_STAGE_GPU_WALL_CAP:' + stage)
        totals = Counter(prior['counts']) + self.counts + Counter(proposed)
        for key, limit_key in (('data_generation_F_calls', 'data_generation_F_cap'),
                               ('new_teacher_labels', 'new_teacher_label_cap')):
            if totals[key] > self.config[limit_key]:
                self._refuse('A22_ACTION_CAP:' + key, counter=key, attempted_total=totals[key])

    def check(self):
        self.preflight()
        # CostBook's memory measurements are retained; its CPU budget is infinite.
        super().check()

    def append(self, row):
        row = plain({'campaign': 'A22', 'job_id': self.job_id, 'stage': self.stage, **row})
        super().append(row)
        _append_json(self.root / 'results/a22/COST_LEDGER.jsonl', row)
        if row.get('status') == 'FAILED':
            _append_json(self.root / 'results/a22/FAILURE_LEDGER.jsonl', dict(failure_kind='nested_span', **row))
        self._checkpoint()

    @contextmanager
    def span(self, label, **counters):
        counters = _counters(counters)
        self.preflight(counters=counters)
        self.check()
        self.synchronize()
        start, cpu = time.perf_counter(), self.elapsed_cpu()
        frame = {'child_wall': 0.0, 'child_cpu': 0.0}
        parent = self.stack[-1] if self.stack else None
        self.stack.append(frame)
        self.counts.update(counters)
        row = dict(event=str(label), phase=self.phase, counters=counters,
                   role=self.role, status='FAILED', **self.metadata)
        row['stage'] = self.stage
        row['event_id'] = uuid.uuid4().hex
        self._checkpoint()
        try:
            yield row
            row['status'] = 'OK'
        except BaseException as error:
            row['error_type'] = type(error).__name__
            raise
        finally:
            # A synchronization failure must not suppress already paid work.
            sync_error = None
            try:
                self.synchronize()
            except BaseException as error:
                sync_error = error
                row.update(status='FAILED', synchronization_error_type=type(error).__name__)
            wall, used_cpu = max(0.0, time.perf_counter()-start), max(0.0, self.elapsed_cpu()-cpu)
            row.update(wall_seconds=wall, exclusive_wall_seconds=max(0.0, wall-frame['child_wall']),
                       process_cpu_seconds=used_cpu, exclusive_process_cpu_seconds=max(0.0, used_cpu-frame['child_cpu']))
            self.stack.pop()
            if parent is not None:
                parent['child_wall'] += wall
                parent['child_cpu'] += used_cpu
            self.walls[str(label)] += row['exclusive_wall_seconds']
            self.append(row)
            if sync_error is not None and 'error_type' not in row:
                raise sync_error

    @contextmanager
    def action_guard(self, action, *, role=None, scene_id=None, method=None,
                     purpose=None, gpu_seconds=0.0, new_label=False, **counters):
        """Backend entry guard. Counters are charged before work, including retries."""
        role = self.role if role is None else role
        if role not in ROLES:
            raise ValueError('UNREGISTERED_ACTION_ROLE')
        if action in OFFLINE_ACTIONS and role not in OFFLINE_ROLES:
            self._refuse('A22_OFFLINE_ACTION_FORBIDDEN_ONLINE:' + str(action))
        if action in ('train', 'mlp_train', 'stage_C', 'stage_c'):
            gate_values = [self.gates.get(key, self.gates.get('Gate ' + key, self.gates.get('gate_' + key))) for key in ('A', 'B', 'C')]
            gate_values = [value.get('status') if isinstance(value, dict) else value for value in gate_values]
            if gate_values != ['PASS', 'PASS', 'PASS'] or not self.cache_sufficient:
                self._refuse('A22_STAGE_C_REQUIRES_ABC_PASS_AND_EXISTING_LEGAL_CACHE')
            if self.stage != 'train':
                self._refuse('A22_TRAIN_REQUIRES_TRAIN_STAGE')
        if action in ('diffusion', 'flow', 'transformer', 'unet_train'):
            self._refuse('A22_UNREGISTERED_TRAINING_ROUTE')
        counters = _counters(counters)
        is_generation = action in GENERATION_ACTIONS or purpose in ('perturbation', 'data_generation', 'new_label') or new_label
        if is_generation:
            explicit = counters.get('data_generation_F_calls')
            counters['data_generation_F_calls'] = int(counters.get('F_calls', 1) if explicit is None else explicit)
        if action == 'new_teacher_label' or new_label:
            if role not in OFFLINE_ROLES:
                self._refuse('A22_NEW_LABEL_REQUIRES_OFFLINE_ROLE')
            counters.setdefault('new_teacher_labels', 1)
        correction_key = None
        if action in ('physical_correction', 'full_wave_correction'):
            if scene_id is None or method is None:
                raise ValueError('CORRECTION_REQUIRES_SCENE_AND_METHOD')
            correction_key = json.dumps([str(scene_id), str(method)], separators=(',', ':'))
            paid = self._current_prior()['corrections'].get(correction_key, 0) + self.corrections[correction_key]
            if paid >= self.config['physical_correction_cap']:
                self._refuse('A22_ONE_PHYSICAL_CORRECTION_CAP')
            counters['physical_corrections'] = counters.get('physical_corrections', 0) + 1
        self.preflight(gpu_seconds=gpu_seconds, counters=counters)
        if correction_key is not None:
            self.corrections[correction_key] += 1
            self._checkpoint()
        old_role = self.role
        self.role = role
        try:
            with self.span(str(action), **counters) as row:
                row.update(action=str(action), role=role, scene_id=scene_id, method=method, purpose=purpose)
                yield row
        finally:
            self.role = old_role

    def receipt(self):
        if self._finished is not None:
            return dict(self._finished)
        receipt = super().receipt()
        now = time.perf_counter()
        stages = self._stage_usage(now)
        receipt.update(campaign='A22', job_id=self.job_id, stage=self.job_stage,
                       active_stage=self.stage, stage_gpu_seconds=stages,
                       wall_seconds=max(0.0, now-self.started_wall),
                       gpu_occupation_seconds=sum(stages.values()),
                       checkpoint_perf_counter=now,
                       process_cpu_seconds=self.elapsed_cpu(),
                       controller_process_cpu_seconds=max(0.0, time.process_time()-self.started_cpu_origin),
                       child_process_cpu_seconds=self.child_cpu_seconds,
                       live_child_process_cpu_seconds=self.live_child_cpu_seconds,
                       corrections=dict(self.corrections), role=self.role, status='RUNNING',
                       CPU_cap=None, gpu_wall_cap_seconds=self.config['gpu_wall_cap_seconds'],
                       stage_gpu_cap_seconds=self.config['stage_gpu_caps_seconds'][self.stage],
                       nested_spans_not_additive=True, failed_imports_included=self.started_cpu_origin == 0,
                       CPU_and_GPU_resources_not_summed=True,
                       historical_A21_costs='record only; excluded from A22 limits',
                       measurement='inclusive measured process CPU + child CPU; CUDA job inclusive wall',
                       new_SHA256_checks=0)
        return receipt

    def _checkpoint(self):
        if self._finished is None and hasattr(self, 'started_wall'):
            with self._checkpoint_lock:
                write_json(self.root / 'results/jobs' / self.job_id / 'accounting_checkpoint.json', self.receipt())

    def finish(self, status='COMPLETE', **details):
        if self._finished is not None:
            return dict(self._finished)
        receipt = self.receipt()
        receipt.update(plain(details))
        receipt['status'] = str(status)
        # No check here: failed/timed-out paid work must remain billable.
        merge_receipt(self.root, receipt, self.config)
        self._finished = receipt
        return dict(receipt)

    @contextmanager
    def watchdog(self, poll_seconds=0.1):
        """Cooperative asynchronous cap check; callers must keep action checks.

        The remote foreground transport additionally terminates the whole process
        at the remaining stage/total wall deadline. Threads cannot stop a CUDA
        kernel safely; this watchdog reports expiry and checks at scope exit.
        """
        import threading
        stopped = threading.Event()
        errors = []
        def monitor():
            while not stopped.wait(max(0.01, float(poll_seconds))):
                try:
                    self.preflight()
                    self._checkpoint()
                except BudgetExceeded as error:
                    errors.append(error)
                    stopped.set()
        worker = threading.Thread(target=monitor, name='a22-budget-watchdog', daemon=True)
        worker.start()
        try:
            yield stopped
        finally:
            stopped.set()
            worker.join(timeout=max(0.1, float(poll_seconds) * 2))
            self._checkpoint()
            if errors:
                raise errors[0]
