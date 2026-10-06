"""Foreground A21 SSH transport; private connection values never enter artifacts."""
from __future__ import annotations

import argparse
import base64
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import uuid
import zipfile

ROOT = Path(__file__).resolve().parents[1]
REMOTE = 'D:/AI/A21_TWO_SIDED_ANATOMY'
SHARED = 'D:/AI/A20_OPM_IMAGING'
PYTHON = 'D:/python/python.exe'
sys.path.insert(0, str(ROOT / 'src'))


class TransportFailure(RuntimeError):
    pass


def _private_stderr(data):
    if not data:
        return
    directory = ROOT / 'private'
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / ('transport-stderr-' + uuid.uuid4().hex[:12] + '.log')
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'wb') as stream:
        stream.write(data.encode('utf-8', errors='replace') if isinstance(data, str) else data)


def _transport():
    # Existing transport code remains unchanged. Only its subprocess facade is
    # redirected so SSH/SCP stderr and private argument lists cannot be printed.
    path = ROOT / 'tools/remote_jobs.py'
    spec = importlib.util.spec_from_file_location('a21_existing_transport', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    def checked_output(*args, **kwargs):
        kwargs['stderr'] = subprocess.PIPE
        # Windows PowerShell may emit OEM/GBK bytes. Decode display output
        # tolerantly; retain raw stderr only inside the ignored private folder.
        kwargs.pop('text', None)
        kwargs.pop('encoding', None)
        kwargs.pop('errors', None)
        try:
            completed = subprocess.run(*args, stdout=subprocess.PIPE, **kwargs)
            _private_stderr(completed.stderr)
            if completed.returncode:
                raise TransportFailure('Remote command exited with status ' + str(completed.returncode))
            return completed.stdout.decode('utf-8', errors='replace')
        except subprocess.CalledProcessError as error:
            _private_stderr(error.stderr)
            raise TransportFailure('Remote command exited with status ' + str(error.returncode)) from None
        except OSError:
            raise TransportFailure('Remote command could not start') from None
    def checked_run(*args, **kwargs):
        kwargs['stdout'], kwargs['stderr'] = subprocess.PIPE, subprocess.PIPE
        try:
            return subprocess.run(*args, **kwargs)
        except subprocess.CalledProcessError as error:
            _private_stderr(error.stderr)
            raise TransportFailure('Archive transfer exited with status ' + str(error.returncode)) from None
        except OSError:
            raise TransportFailure('Archive transfer could not start') from None
    module.subprocess = SimpleNamespace(check_output=checked_output, run=checked_run)
    return module


def connection():
    if not os.environ.get('A20_SSH_TARGET') or not os.environ.get('A20_SSH_KEY'):
        path = ROOT / 'private/ssh_connection.json'
        if not path.exists():
            raise TransportFailure('Private connection configuration is unavailable')
        try:
            values = json.loads(path.read_text(encoding='utf-8'))
            target = values.get('A20_SSH_TARGET', values.get('target'))
            key = values.get('A20_SSH_KEY', values.get('key', values.get('key_path')))
            if not isinstance(target, str) or not isinstance(key, str) or not target or not key:
                raise ValueError()
        except (ValueError, OSError):
            raise TransportFailure('Private connection configuration is invalid') from None
        os.environ.setdefault('A20_SSH_TARGET', target)
        os.environ.setdefault('A20_SSH_KEY', key)
    return _transport().connection()


def shell(script):
    connection()
    return _transport().shell(script)


def copy(source, destination):
    connection()
    return _transport().copy(source, destination)


def _job(value):
    if not isinstance(value, str) or not re.fullmatch(r'a21-[A-Za-z0-9_-]{1,100}', value):
        raise ValueError('Invalid A21 job ID')
    return value


def deployment_members(root=ROOT):
    """A minimal whitelist: no labels, private files, old receipts or root reports."""
    from a21.budget import load_config
    from a21.cli import canonical_inputs, source_identity
    root = Path(root).resolve()
    config = load_config(root)
    source_identity(root, config, required=True)
    members = set()
    for folder in ('src', 'vendor', 'protocol', 'tests', 'tools'):
        for path in (root / folder).rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts and path.suffix in ('.py', '.md', '.json', '.txt'):
                members.add(path.relative_to(root).as_posix())
    for name in ('a21.json', 'parents.json', 'frozen.json', 'a20_r1.json', 'A21_SOURCE_COMMIT.txt'):
        members.add('configs/' + name)
    for parent in config['parents']:
        for name in ('problem.npz', 'state_17.npz'):
            members.add('data/runtime/' + str(parent) + '/' + name)
    members.add('results/replay/replay.jsonl')
    members.update(item['step_path'] for item in canonical_inputs(root, config))
    # Carry A21-only receipts/registry so remote work cannot reset local billing.
    members.add('results/a21/external_cpu_receipts.json')
    for name in ('results/a21/PREFLIGHT.json', 'results/a21/validation/T0.json'):
        if (root / name).exists():
            members.add(name)
    for path in (root / 'results/jobs').glob('a21-*/job_receipt.json'):
        members.add(path.relative_to(root).as_posix())
    for name in members:
        path = (root / name).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError('Deployment input missing or outside the A21 root')
        if any(part in ('private', 'offline', '.git') for part in Path(name).parts):
            raise ValueError('Forbidden deployment member')
    return sorted(members)


def deploy():
    target, _ = connection()
    members = deployment_members()
    with tempfile.TemporaryDirectory() as directory:
        archive = Path(directory) / 'a21-upload.zip'
        with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as zipped:
            for name in members:
                zipped.write(ROOT / name, name)
        shell("New-Item -ItemType Directory -Force '" + REMOTE + "' | Out-Null")
        copy(archive, target + ':' + REMOTE + '/a21-upload.zip')
        code = f"""import json,pathlib,time,zipfile
r=pathlib.Path(r'{REMOTE}')
meta=dict(status='FAILED',members=0)
try:
 with zipfile.ZipFile(r/'a21-upload.zip') as z:
  bad=[n for n in z.namelist() if n.startswith('/') or '..' in pathlib.PurePosixPath(n).parts or 'private' in pathlib.PurePosixPath(n).parts]
  if bad: raise ValueError('Invalid archive member')
  for member in z.namelist():
   if time.process_time()>25: raise RuntimeError('Bounded extraction allowance exceeded')
   z.extract(member,r)
  meta.update(status='A21_DEPLOYED',members=len(z.namelist()))
except BaseException as error:
 meta['error_type']=type(error).__name__
finally:
 meta['extract_CPU_seconds']=time.process_time()
 print(json.dumps(meta))
"""
        encoded = base64.b64encode(code.encode()).decode()
        extracted = json.loads(shell("& '" + PYTHON + "' -c \"import base64; exec(base64.b64decode('" + encoded + "'))\""))
        if extracted['status'] != 'A21_DEPLOYED':
            error = TransportFailure('Remote extraction failed; its bounded CPU receipt is preserved')
            error.accounting = dict(extract_CPU_seconds=extracted['extract_CPU_seconds'])
            raise error
        print('A21_DEPLOYED ' + str(extracted['members']))
        return dict(member_count=len(members), compressed_bytes=archive.stat().st_size,
                    extract_CPU_seconds=extracted['extract_CPU_seconds'],
                    original_A20_written=False, private_files_transferred=False,
                    old_results_ledgers_transferred=False, deployment_members=members)


def run(stage, job, device, phase='all'):
    _job(job)
    if device not in ('cpu', 'cuda'):
        raise ValueError('Remote device must be explicit')
    if stage not in ('preflight', 'validate', 'anatomy', 'report') or phase not in ('all', 'galerkin', 'petrov'):
        raise ValueError('Unregistered A21 stage or phase')
    args = ['-B', '-u', '-m', 'a21.cli', stage, '--device', device, '--job', job,
            '--root', REMOTE, '--lock-root', SHARED, '--phase', phase]
    encoded_args = ','.join("'" + argument + "'" for argument in args)
    gpu_guard = """
$busy=@(& nvidia-smi --query-compute-apps=pid,process_name --format=csv,noheader)
if($LASTEXITCODE -ne 0) { throw 'GPU inventory failed' }
if($busy.Count -gt 0) { throw 'Existing GPU compute job' }
""" if device == 'cuda' else ''
    script = f"""
$ErrorActionPreference='Stop'
Set-Location '{REMOTE}'
$env:PYTHONPATH='{REMOTE}/src'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:OPENBLAS_NUM_THREADS='1'
$env:OMP_NUM_THREADS='1'
$env:MKL_NUM_THREADS='1'
$env:NUMEXPR_NUM_THREADS='1'
{gpu_guard}
if(Test-Path '{SHARED}/runs/gpu.lock') {{ throw 'Shared A20 physics lock exists' }}
if(Test-Path '{REMOTE}/results/jobs/{job}') {{ throw 'Existing A21 job ID' }}
New-Item -ItemType Directory -Force '{REMOTE}/runs' | Out-Null
& '{PYTHON}' @({encoded_args}) 1>'{REMOTE}/runs/{job}.stdout' 2>'{REMOTE}/runs/{job}.stderr'
$rc=$LASTEXITCODE
Get-Content '{REMOTE}/runs/{job}.stdout' -Tail 6
Get-Content '{REMOTE}/runs/{job}.stderr' -Tail 10
exit $rc
"""
    print(shell(script))
    return dict(stage=stage, job=job, device=device, runtime_phase=phase,
                shared_lock='existing A20 runs/gpu.lock', foreground=True)


def status(job):
    _job(job)
    print(shell(f"""
$p=Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object {{$_.CommandLine -match 'a21[.]cli' -and $_.CommandLine -match '--job +{job}( |$)'}}
if($p) {{$v=Get-Process -Id $p.ProcessId; Write-Output ('RUNNING CPU='+$v.CPU+' RSS='+$v.WorkingSet64)}} else {{Write-Output 'ENDED_OR_NOT_STARTED'}}
if(Test-Path '{REMOTE}/results/jobs/{job}/job_receipt.json') {{Get-Content '{REMOTE}/results/jobs/{job}/job_receipt.json' -Raw}}
Get-Content '{REMOTE}/runs/{job}.stderr' -Tail 10 -ErrorAction SilentlyContinue
"""))
    return dict(job=job, read_only=True)


def _merge_jobs(archive, root):
    """Immutable overlapping job files must agree; preserve local-only files."""
    root = Path(root).resolve()
    with zipfile.ZipFile(archive) as zipped:
        # Check every overlapping immutable job before writing any incoming
        # mutable summary, so a conflict cannot partially replace a report.
        for info in zipped.infolist():
            name = info.filename
            parts = Path(name).parts
            allowed = name.startswith('results/a21/') or (len(parts) >= 4 and parts[:2] == ('results', 'jobs') and parts[2].startswith('a21-'))
            target = (root / name).resolve()
            if not allowed or name.startswith('/') or '..' in parts or '\\' in name or not target.is_relative_to(root):
                raise ValueError('Invalid A21 result archive member')
            if name.startswith('results/jobs/') and target.exists() and target.read_bytes() != zipped.read(info):
                raise ValueError('Immutable A21 job record differs during pull')
        for info in zipped.infolist():
            name = info.filename
            parts = Path(name).parts
            allowed = name.startswith('results/a21/') or (len(parts) >= 4 and parts[:2] == ('results', 'jobs') and parts[2].startswith('a21-'))
            if not allowed or name.startswith('/') or '..' in parts or '\\' in name:
                raise ValueError('Invalid A21 result archive member')
            target = (root / name).resolve()
            if not target.is_relative_to(root):
                raise ValueError('A21 result archive path escapes its root')
            incoming = zipped.read(info)
            if name.endswith('/external_cpu_receipts.json'):
                local = json.loads(target.read_text(encoding='utf-8')) if target.exists() else []
                merged = {}
                for row in local + json.loads(incoming):
                    scope = row['scope']
                    if scope in merged and merged[scope] != row:
                        raise ValueError('Conflicting external A21 accounting scope')
                    merged[scope] = row
                incoming = (json.dumps(list(merged.values()), indent=2, allow_nan=False) + '\n').encode()
            elif name.startswith('results/jobs/') and target.exists():
                if target.read_bytes() != incoming:
                    raise ValueError('Immutable A21 job record differs during pull')
                continue
            elif name.endswith(('COST_LEDGER.jsonl', 'FAILURE_LEDGER.jsonl', 'JOB_LEDGER.jsonl')):
                local = target.read_text(encoding='utf-8').splitlines() if target.exists() else []
                rows = list(dict.fromkeys(local + incoming.decode().splitlines()))
                incoming = ('\n'.join(rows) + ('\n' if rows else '')).encode()
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(incoming)


def pull():
    target, _ = connection()
    code = f"""import json,pathlib,time,zipfile
r=pathlib.Path(r'{REMOTE}')
meta=dict(status='FAILED')
try:
 with zipfile.ZipFile(r/'a21-results.zip','w',zipfile.ZIP_DEFLATED) as z:
  paths=list((r/'results/a21').rglob('*'))
  paths+=list((r/'results/jobs').glob('a21-*/*'))
  for p in paths:
   if time.process_time()>25: raise RuntimeError('Bounded archive CPU allowance exceeded')
   if p.is_file(): z.write(p,p.relative_to(r).as_posix())
 meta.update(status='A21_ARCHIVED',archive_bytes=(r/'a21-results.zip').stat().st_size)
except BaseException as error:
 meta['error_type']=type(error).__name__
finally:
 meta['archive_CPU_seconds']=time.process_time()
 print(json.dumps(meta))
"""
    encoded = base64.b64encode(code.encode()).decode()
    summary = json.loads(shell("& '" + PYTHON + "' -c \"import base64; exec(base64.b64decode('" + encoded + "'))\""))
    if summary['status'] != 'A21_ARCHIVED':
        error = TransportFailure('Remote archive failed; its bounded CPU receipt is preserved')
        error.accounting = dict(archive_CPU_seconds=summary['archive_CPU_seconds'])
        raise error
    with tempfile.TemporaryDirectory() as directory:
        archive = Path(directory) / 'a21-results.zip'
        copy(target + ':' + REMOTE + '/a21-results.zip', archive)
        _merge_jobs(archive, ROOT)
    from a21.budget import history
    (ROOT / 'results/a21/BUDGET_CURRENT.json').write_text(json.dumps(history(ROOT), indent=2, allow_nan=False) + '\n', encoding='utf-8')
    print('A21_RESULTS_SAVED')
    return dict(**summary, original_A20_written=False)


def _child_usage():
    try:
        import resource
        value = resource.getrusage(resource.RUSAGE_CHILDREN)
        return value.ru_utime + value.ru_stime
    except ImportError:
        return 0.0


def _record_transport(action, details, status_value, started, child_before):
    from a21.budget import load_config, register_external
    destination = ROOT / 'results/a21/transport'
    destination.mkdir(parents=True, exist_ok=True)
    identity = 'transport-' + uuid.uuid4().hex[:12]
    remote_cpu = float(details.get('archive_CPU_seconds', 0)) + float(details.get('extract_CPU_seconds', 0))
    cpu = time.process_time() + max(0, _child_usage() - child_before) + remote_cpu
    row = dict(scope=identity, action=action, status=status_value,
               process_cpu_seconds=cpu, remote_archive_CPU_seconds=details.get('archive_CPU_seconds', 0),
               remote_extract_CPU_seconds=details.get('extract_CPU_seconds', 0),
               wall_seconds=time.perf_counter()-started, GPU_seconds=0,
               billing='covered by frozen 30-second setup/transport allowance; measured overage additionally billed',
               measurement='local controller including imports + local child CPU + remote archive process CPU',
               details=details, new_SHA256_checks=0)
    path = destination / (identity + '.json')
    path.write_text(json.dumps(row, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    known = sum(json.loads(p.read_text(encoding='utf-8'))['process_cpu_seconds'] for p in destination.glob('transport-*.json'))
    config = load_config(ROOT)
    registry = json.loads((ROOT/'results/a21/external_cpu_receipts.json').read_text(encoding='utf-8'))
    prior_overage = sum(float(r['process_cpu_seconds']) for r in registry if str(r['scope']).startswith('A21 measured transport overage '))
    extra = max(0.0, known - config['setup_transport_overhead_allowance_CPU_seconds'] - prior_overage)
    if extra:
        register_external(ROOT, 'A21 measured transport overage ' + identity, extra,
                          receipt=path.relative_to(ROOT).as_posix(), config=config)


def main():
    started, child_before = time.perf_counter(), _child_usage()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['deploy', 'run', 'status', 'pull'])
    parser.add_argument('--stage', choices=['preflight', 'validate', 'anatomy', 'report'])
    parser.add_argument('--job')
    parser.add_argument('--device', choices=['cpu', 'cuda'])
    parser.add_argument('--phase', choices=['all', 'galerkin', 'petrov'], default='all')
    args = parser.parse_args()
    if args.action == 'run' and (not args.stage or not args.device or not args.job):
        parser.error('run requires explicit --stage, --device and --job')
    if args.action == 'status' and not args.job:
        parser.error('status requires --job')
    details, result = {}, 'FAILED'
    try:
        from a21.budget import A21Book, load_config
        A21Book(ROOT, load_config(ROOT)).check()
        if args.action == 'deploy':
            details = deploy()
        elif args.action == 'run':
            details = run(args.stage, args.job, args.device, args.phase)
        elif args.action == 'status':
            details = status(args.job)
        else:
            details = pull()
        result = 'COMPLETE'
        return 0
    except TransportFailure as error:
        # These errors contain only a sanitized category/status, never argv.
        details.update(getattr(error, 'accounting', {}))
        print(str(error) + '; pull preserved A21 receipts before judging a remote failure', file=sys.stderr)
        return 2
    except Exception as error:
        print('A21 transport failed: ' + type(error).__name__ + '; private details suppressed', file=sys.stderr)
        return 2
    finally:
        try:
            _record_transport(args.action, details, result, started, child_before)
        except Exception as error:
            print('A21 transport receipt failed: ' + type(error).__name__ + '; private details suppressed', file=sys.stderr)
            return 2


if __name__ == '__main__':
    raise SystemExit(main())
