"""Explicit, foreground A22 transport with private SSH inputs and paid failures.

The private configuration is a required external/ignored path. It is never
copied, printed, written into receipts, or exported to the environment.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path, PurePosixPath
import stat
import subprocess
import sys
import tempfile
import time
import uuid
import zipfile

ROOT = Path(__file__).resolve().parents[1]
REMOTE = 'D:/AI/A22_THREE_FOLD_OPM'
SHARED = 'D:/AI/A20_OPM_IMAGING'
SHARED_LOCK = SHARED + '/runs/gpu.lock'
PYTHON = 'D:/python/python.exe'
MAX_INLINE_COMMAND_CHARS = 7000
CLI_STAGES = {
    'preflight': 'screen_health', 'validate': 'screen_health',
    'screen': 'direction', 'screen-resume': 'direction', 'pilot': 'direction', 'one-shot': 'image',
    'train': 'train', 'report': 'exception',
}
sys.path.insert(0, str(ROOT / 'src'))


class TransportFailure(RuntimeError):
    """Messages deliberately contain no command arguments or connection values."""


def _powershell_command(script):
    encoded = base64.b64encode(("$ProgressPreference='SilentlyContinue';\n" + script).encode('utf-16le')).decode()
    return 'powershell.exe -NoProfile -EncodedCommand ' + encoded


def _job(value):
    from a22.budget import job_id
    return job_id(value)


def _private_stderr(data, root=ROOT):
    # SSH/SCP diagnostic text can repeat private arguments. Retain only the
    # sanitized category/status receipt; never print or store the raw text.
    return None


class PrivateTransport:
    def __init__(self, private_config, *, root=ROOT):
        self.root = Path(root).resolve()
        try:
            path = Path(private_config).expanduser().resolve()
            if path.is_relative_to(self.root) and 'private' not in path.relative_to(self.root).parts:
                raise ValueError('Configuration must be external or under ignored private/')
            values = json.loads(path.read_text(encoding='utf-8'))
            target = values.get('A20_SSH_TARGET', values.get('target'))
            key = values.get('A20_SSH_KEY', values.get('key', values.get('key_path')))
            if not isinstance(target, str) or not isinstance(key, str) or not target or not key:
                raise ValueError('Missing private fields')
            if any(character in target + key for character in ('\n', '\r', '\0')) or target.startswith('-'):
                raise ValueError('Invalid private fields')
        except (TypeError, ValueError, OSError):
            raise TransportFailure('Private connection configuration is unavailable or invalid') from None
        self._target, self._key = target, key

    def _checked(self, argv, *, category, timeout=None):
        try:
            completed = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       timeout=timeout, check=False)
        except subprocess.TimeoutExpired as error:
            _private_stderr(error.stderr, self.root)
            raise TransportFailure(category + ' timed out; private details suppressed') from None
        except OSError:
            raise TransportFailure(category + ' could not start; private details suppressed') from None
        _private_stderr(completed.stderr, self.root)
        if completed.returncode:
            raise TransportFailure(category + ' exited with status ' + str(completed.returncode))
        output = completed.stdout
        return output.decode('utf-8', errors='replace') if isinstance(output, bytes) else str(output or '')

    def shell(self, script, *, timeout=None):
        return self._checked(['ssh', '-i', self._key, '-o', 'BatchMode=yes',
                              '-o', 'ConnectTimeout=8', '-o', 'StrictHostKeyChecking=yes',
                              self._target, _powershell_command(script)],
                             category='Remote command', timeout=timeout).strip()

    def copy_to(self, source, remote_name):
        return self._checked(['scp', '-i', self._key, '-o', 'BatchMode=yes',
                              '-o', 'ConnectTimeout=8', '-o', 'StrictHostKeyChecking=yes',
                              str(source), self._target + ':' + REMOTE + '/' + remote_name],
                             category='Archive transfer')

    def copy_from(self, remote_name, destination):
        return self._checked(['scp', '-i', self._key, '-o', 'BatchMode=yes',
                              '-o', 'ConnectTimeout=8', '-o', 'StrictHostKeyChecking=yes',
                              self._target + ':' + REMOTE + '/' + remote_name, str(destination)],
                             category='Archive transfer')


def connection(private_config, *, root=ROOT):
    return PrivateTransport(private_config, root=root)


def _controller_error_source():
    """Only fixed function names and numeric OS codes may cross the boundary."""
    return """def controller_failure(error,function=None):
 trace=error.__traceback__
 while trace is not None and trace.tb_next is not None: trace=trace.tb_next
 name=trace.tb_frame.f_code.co_name if trace is not None else function
 return dict(error_type=type(error).__name__,error_function=name or 'foreground_controller',error_operation=getattr(error,'_a22_controller_function',None),error_errno=getattr(error,'errno',None) if isinstance(getattr(error,'errno',None),int) else None,error_winerror=getattr(error,'winerror',None) if isinstance(getattr(error,'winerror',None),int) else None)
"""


def _python(transport, code, *, timeout=None, force_file=False):
    encoded = base64.b64encode(code.encode('utf-8')).decode()
    bootstrap = """import time
_a22_remote_process_origin=time.perf_counter()
import base64,json
%s
try:
 exec(base64.b64decode('%s'))
except BaseException as error:
 failed=controller_failure(error)
 failed.update(status='FAILED_REMOTE_BOOTSTRAP',remote_process_cpu_seconds=time.process_time(),remote_wall_seconds=time.perf_counter()-_a22_remote_process_origin)
 print(json.dumps(failed))
""" % (_controller_error_source(), encoded)
    wrapped = base64.b64encode(bootstrap.encode('utf-8')).decode()
    inline = "& '" + PYTHON + "' -B -c \"import base64; exec(base64.b64decode('" + wrapped + "'))\""
    # Compare the command actually delivered to Windows, after PowerShell's
    # UTF-16/base64 expansion. The short Python source itself is not the limit.
    if force_file or len(_powershell_command(inline)) > MAX_INLINE_COMMAND_CHARS:
        name = 'a22-transport-code-' + uuid.uuid4().hex + '.py'
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / name
            source.write_text(bootstrap, encoding='utf-8')
            transport.shell("$ErrorActionPreference='Stop'; New-Item -ItemType Directory -Force '" + REMOTE + "' | Out-Null")
            transport.copy_to(source, name)
            output = transport.shell("& '" + PYTHON + "' -B '" + REMOTE + '/' + name + "'; exit $LASTEXITCODE", timeout=timeout)
    else:
        output = transport.shell(inline, timeout=timeout)
    try:
        # Child output stays in job logs. Only this small sanitized JSON crosses
        # the display boundary; warnings/banners are never printed by the helper.
        row = json.loads(output.splitlines()[-1])
        if not isinstance(row, dict):
            raise ValueError()
        return row
    except (IndexError, ValueError):
        raise TransportFailure('Remote response was not a sanitized receipt') from None


def deployment_members(root=ROOT):
    """Whitelist A22/shared physics, online inputs, and A22-only accounting."""
    root = Path(root).resolve()
    members = set()
    for folder in ('src/a22', 'src/a20', 'src/a20_r1', 'vendor', 'protocol/a22'):
        for path in (root / folder).rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts and path.suffix in ('.py', '.md', '.json', '.txt'):
                members.add(path.relative_to(root).as_posix())
    for folder, pattern in (('tools', 'a22*.py'), ('tests', 'test_a22*.py')):
        for path in (root / folder).glob(pattern):
            if path.is_file():
                members.add(path.relative_to(root).as_posix())
    for name in ('a22.json', 'a22_portable.json', 'frozen.json', 'parents.json', 'a20_r1.json'):
        path = root / 'configs' / name
        if path.exists():
            members.add(path.relative_to(root).as_posix())
    if 'configs/a22.json' not in members:
        raise ValueError('MISSING_A22_FROZEN_CONFIG')
    for path in (root / 'data/a22/online').rglob('*'):
        if path.is_file() and path.suffix in ('.npz', '.json', '.csv'):
            members.add(path.relative_to(root).as_posix())
    for name in ('external_cpu_receipts.json', 'COST_LEDGER.jsonl', 'FAILURE_LEDGER.jsonl', 'JOB_LEDGER.jsonl'):
        path = root / 'results/a22' / name
        if path.exists():
            members.add(path.relative_to(root).as_posix())
    for path in (root / 'results/jobs').glob('a22-*/*'):
        if path.is_file() and path.name in ('job_receipt.json', 'accounting_checkpoint.json', 'accounting_started.json'):
            members.add(path.relative_to(root).as_posix())
    for name in members:
        path = (root / name).resolve()
        if not path.is_relative_to(root) or not path.is_file() or (root / name).is_symlink():
            raise ValueError('DEPLOYMENT_INPUT_MISSING_OR_OUTSIDE_A22_ROOT')
        if any(part in ('private', 'offline', '.git', 'a21') for part in PurePosixPath(name).parts):
            raise ValueError('FORBIDDEN_A22_DEPLOYMENT_MEMBER')
        if name.startswith('data/') and not name.startswith('data/a22/online/'):
            raise ValueError('ONLY_A22_ONLINE_DATA_MAY_BE_DEPLOYED')
    return sorted(members)


def _windows_cpu_source():
    """Shared generated-code CPU reader; failure is explicitly marked partial."""
    return """child_cpu_measurement_available=True
def measured_cpu(process):
 global child_cpu_measurement_available
 try:
  import ctypes
  from ctypes import wintypes
  read=ctypes.WinDLL('kernel32',use_last_error=True).GetProcessTimes
  read.argtypes=[wintypes.HANDLE]+[ctypes.POINTER(wintypes.FILETIME)]*4
  read.restype=wintypes.BOOL
  creation,exit_time,kernel,user=[wintypes.FILETIME() for _ in range(4)]
  ok=read(wintypes.HANDLE(int(process._handle)),ctypes.byref(creation),ctypes.byref(exit_time),ctypes.byref(kernel),ctypes.byref(user))
  if ok: return ((kernel.dwHighDateTime<<32)+kernel.dwLowDateTime+(user.dwHighDateTime<<32)+user.dwLowDateTime)/1e7
 except Exception:
  pass
 child_cpu_measurement_available=False
 return 0.0
"""


def _checkpoint_reader_source():
    """Native Windows delete-sharing reads plus bounded stale-snapshot fallback."""
    return _controller_error_source() + """last_checkpoint=None
checkpoint_read_conflicts=0
checkpoint_unreadable_since=None
checkpoint_last_read_failure=None
CHECKPOINT_UNREADABILITY_SECONDS=2.0
def reject_nonfinite_json(value):
 raise ValueError('CHECKPOINT_NONFINITE_JSON')
def checkpoint_bytes(path):
 if os.name!='nt': return pathlib.Path(path).read_bytes()
 from ctypes import wintypes
 kernel=ctypes.WinDLL('kernel32',use_last_error=True)
 create,read,close=kernel.CreateFileW,kernel.ReadFile,kernel.CloseHandle
 create.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]
 create.restype=wintypes.HANDLE
 read.argtypes=[wintypes.HANDLE,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(wintypes.DWORD),ctypes.c_void_p]
 read.restype=wintypes.BOOL
 close.argtypes=[wintypes.HANDLE]
 close.restype=wintypes.BOOL
 def failure(function):
  error=ctypes.WinError(ctypes.get_last_error())
  error._a22_controller_function=function
  return error
 FILE_SHARE_READ,FILE_SHARE_WRITE,FILE_SHARE_DELETE=1,2,4
 handle=create(str(path),0x80000000,FILE_SHARE_READ|FILE_SHARE_WRITE|FILE_SHARE_DELETE,None,3,0x80,None)
 if handle in (-1,ctypes.c_void_p(-1).value): raise failure('CreateFileW')
 failed=True
 try:
  buffer=ctypes.create_string_buffer(65536)
  chunks=[]
  while True:
   count=wintypes.DWORD()
   if not read(handle,buffer,len(buffer),ctypes.byref(count),None): raise failure('ReadFile')
   if count.value==0: break
   chunks.append(buffer.raw[:count.value])
  payload=b''.join(chunks)
  failed=False
  return payload
 finally:
  if not close(handle) and not failed: raise failure('CloseHandle')
def checkpoint():
 global last_checkpoint,checkpoint_read_conflicts,checkpoint_unreadable_since,checkpoint_last_read_failure
 path=r/'results/jobs'/job/'accounting_checkpoint.json'
 try:
  payload=checkpoint_bytes(path)
 except OSError as error:
  missing=isinstance(error,FileNotFoundError)
  # A not-yet-created startup checkpoint is still protected by inclusive wall
  # caps. Once any snapshot/error appears, missing reads are bounded too.
  if missing and last_checkpoint is None and checkpoint_unreadable_since is None: return None
  transient=missing or getattr(error,'winerror',None) in (5,32,33) or os.name=='nt' and getattr(error,'errno',None)==13
  if not transient: raise
  checkpoint_read_conflicts+=1
  checkpoint_last_read_failure=controller_failure(error,'checkpoint_bytes')
  now=time.perf_counter()
  if checkpoint_unreadable_since is None: checkpoint_unreadable_since=now
  if now-checkpoint_unreadable_since>=CHECKPOINT_UNREADABILITY_SECONDS:
   expired=TimeoutError('CHECKPOINT_UNREADABLE_FOR_2_SECONDS')
   expired._a22_controller_function='checkpoint'
   expired.errno=getattr(error,'errno',None)
   expired.winerror=getattr(error,'winerror',None)
   raise expired from error
  return last_checkpoint
 try:
  saved=json.loads(payload,parse_constant=reject_nonfinite_json)
  if not isinstance(saved,dict): raise ValueError('CHECKPOINT_MUST_BE_JSON_OBJECT')
 except (ValueError,UnicodeError) as error:
  error._a22_controller_function='checkpoint_json'
  raise
 last_checkpoint=saved
 checkpoint_unreadable_since=None
 return last_checkpoint
def live_usage(now,saved=None):
 saved=last_checkpoint if saved is None else saved
 if not saved: return {main_stage:max(0.0,now-origin)}
 usage=dict(saved.get('stage_gpu_seconds',{main_stage:saved.get('gpu_occupation_seconds',0)}))
 active=saved.get('active_stage',main_stage)
 usage[active]=usage.get(active,0)+max(0.0,now-saved.get('checkpoint_perf_counter',now))
 return usage
def watchdog_exceeded(usage,active):
 total=prior['a22_gpu']+sum(usage.values())
 exceeded=total>=config['gpu_wall_cap_seconds']-2
 return exceeded or any((usage.get(stage,0)>0 or stage==active) and prior['stage_gpu_seconds'][stage]+usage.get(stage,0)>=config['stage_gpu_caps_seconds'][stage]-2 for stage in STAGE_GPU_CAPS)
"""


def preflight(private_config, *, root=ROOT):
    transport = connection(private_config, root=root)
    code = f"""import importlib,json,pathlib,platform,subprocess,time
row=dict(status='A22_REMOTE_PREFLIGHT',python=platform.python_version(),runtime_versions={{}},remote_child_process_cpu_seconds=0.0)
{_windows_cpu_source()}
def metered_query(arguments):
 process=subprocess.Popen(arguments,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 try:
  output,errors=process.communicate(timeout=8)
 except subprocess.TimeoutExpired:
  process.kill()
  output,errors=process.communicate()
 finally:
  row['remote_child_process_cpu_seconds']+=measured_cpu(process)
 return subprocess.CompletedProcess(arguments,process.returncode,output,errors)
for name in ('numpy','scipy','torch'):
 try:
  module=importlib.import_module(name)
  row['runtime_versions'][name]=str(getattr(module,'__version__','UNKNOWN'))
 except Exception:
  row['runtime_versions'][name]='UNAVAILABLE'
row['shared_lock_exists']=pathlib.Path(r'{SHARED_LOCK}').exists()
row['GPU_name']='UNAVAILABLE'
row['queue_busy']=None
try:
 names=metered_query(['nvidia-smi','--query-gpu=name','--format=csv,noheader'])
 busy=metered_query(['nvidia-smi','--query-compute-apps=pid','--format=csv,noheader'])
 if names.returncode==0:
  row['GPU_name']=names.stdout.decode('utf-8',errors='replace').strip()[:160]
 if busy.returncode==0:
  row['queue_busy']=bool(busy.stdout.strip())
except Exception:
 pass
row['remote_controller_process_cpu_seconds']=time.process_time()
row['remote_process_cpu_seconds']=row['remote_controller_process_cpu_seconds']+row['remote_child_process_cpu_seconds']
row['child_CPU_measurement_available']=child_cpu_measurement_available
print(json.dumps(row))
"""
    row = _python(transport, code, timeout=60)
    if row.get('status') != 'A22_REMOTE_PREFLIGHT':
        error = TransportFailure('Remote preflight failed; paid import CPU receipt preserved')
        error.accounting = row
        raise error
    return row


def _path_valid(name):
    parts = PurePosixPath(name).parts
    return bool(parts) and not name.startswith('/') and '\\' not in name and ':' not in name and '..' not in parts


def _jsonl_union(local, incoming):
    merged, identities = [], {}
    for line in (local + '\n' + incoming).splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        canonical = json.dumps(row, sort_keys=True, separators=(',', ':'), allow_nan=False)
        identity = row.get('event_id') or canonical
        if identity in identities:
            if identities[identity] != canonical:
                raise ValueError('CONFLICTING_A22_LEDGER_EVENT')
            continue
        identities[identity] = canonical
        merged.append(canonical)
    return ('\n'.join(merged) + ('\n' if merged else '')).encode('utf-8')


def _merge_jobs(archive, root):
    """Validate the whole archive before writing; receipts merge exactly once."""
    from a22.budget import _validated_receipt, _seconds, _counters, STAGE_GPU_CAPS
    root = Path(root).resolve()
    planned, names = [], set()
    with zipfile.ZipFile(archive) as zipped:
        for info in zipped.infolist():
            name, parts = info.filename, PurePosixPath(info.filename).parts
            allowed = name.startswith('results/a22/') or (len(parts) >= 4 and parts[:2] == ('results', 'jobs') and parts[2].startswith('a22-'))
            target = (root / name).resolve()
            if (not allowed or not _path_valid(name) or name in names or info.is_dir()
                    or any(part in ('private', 'offline', '.git', '.env') for part in parts)
                    or stat.S_ISLNK(info.external_attr >> 16) or not target.is_relative_to(root)):
                raise ValueError('INVALID_A22_RESULT_ARCHIVE_MEMBER')
            names.add(name)
            incoming = zipped.read(info)
            local = target.read_bytes() if target.exists() else b''
            if name.endswith('/job_receipt.json'):
                parsed = _validated_receipt(json.loads(incoming))
                if parsed['job_id'] != parts[2]:
                    raise ValueError('A22_RECEIPT_JOB_ID_MISMATCH')
                if local and _validated_receipt(json.loads(local)) != parsed:
                    raise ValueError('CONFLICTING_IMMUTABLE_A22_RECEIPT')
                if local:
                    continue
            elif name.endswith('/external_cpu_receipts.json'):
                union = {}
                for row in (json.loads(local) if local else []) + json.loads(incoming):
                    identity = row['scope']
                    if not isinstance(identity, str) or not identity:
                        raise ValueError('INVALID_EXTERNAL_A22_SCOPE')
                    _seconds(row['process_cpu_seconds'], 'external CPU')
                    _seconds(row.get('wall_seconds', 0), 'external wall')
                    gpu = _seconds(row.get('gpu_occupation_seconds', row.get('GPU_seconds', 0)), 'external GPU')
                    if gpu and row.get('stage') not in STAGE_GPU_CAPS:
                        raise ValueError('EXTERNAL_GPU_REQUIRES_REGISTERED_STAGE')
                    _counters(row.get('counts', {}))
                    if identity in union and union[identity] != row:
                        raise ValueError('CONFLICTING_EXTERNAL_A22_RECEIPT')
                    union[identity] = row
                incoming = (json.dumps(list(union.values()), indent=2, allow_nan=False)+'\n').encode()
            elif name.endswith(('COST_LEDGER.jsonl', 'FAILURE_LEDGER.jsonl', 'JOB_LEDGER.jsonl', '/cost.jsonl')):
                incoming = _jsonl_union(local.decode('utf-8'), incoming.decode('utf-8'))
            elif name.endswith('/accounting_checkpoint.json'):
                parsed = _validated_receipt(json.loads(incoming))
                if parsed['job_id'] != parts[2]:
                    raise ValueError('A22_CHECKPOINT_JOB_ID_MISMATCH')
                if local:
                    previous = _validated_receipt(json.loads(local))
                    if (parsed['process_cpu_seconds'] < previous['process_cpu_seconds']
                            or parsed['gpu_occupation_seconds'] < previous['gpu_occupation_seconds']
                            or any(parsed['counts'].get(key, 0) < value for key, value in previous['counts'].items())):
                        continue  # Never roll a live accounting snapshot backwards.
            elif name.startswith('results/jobs/') and local:
                if local != incoming:
                    raise ValueError('CONFLICTING_IMMUTABLE_A22_JOB_ARTIFACT')
                continue
            planned.append((target, incoming))
    for target, incoming in planned:
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + '.a22-transfer.tmp')
        temporary.write_bytes(incoming)
        temporary.replace(target)
    return len(planned)


def deploy(private_config, *, root=ROOT):
    root = Path(root)
    members = deployment_members(root)
    transport = connection(private_config, root=root)
    name = 'a22-upload-' + uuid.uuid4().hex + '.zip'
    with tempfile.TemporaryDirectory() as directory:
        archive = Path(directory) / name
        with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as zipped:
            for member in members:
                zipped.write(root / member, member)
        transport.shell("if(Test-Path '" + SHARED_LOCK + "'){throw 'Shared GPU lock exists'}; New-Item -ItemType Directory -Force '" + REMOTE + "' | Out-Null")
        transport.copy_to(archive, name)
        code = f"""import json,pathlib,sys,time,zipfile
r=pathlib.Path(r'{REMOTE}')
row=dict(status='FAILED',members=0)
try:
 if pathlib.Path(r'{SHARED_LOCK}').exists(): raise RuntimeError('SHARED_LOCK_EXISTS')
 sys.path.insert(0,str(r/'src'))
 plan=[]
 with zipfile.ZipFile(r/'{name}') as z:
  for entry in z.infolist():
   n=entry.filename
   parts=pathlib.PurePosixPath(n).parts
   if n.startswith('/') or ':' in n or chr(92) in n or '..' in parts or any(p in ('private','offline','a21') for p in parts): raise ValueError('FORBIDDEN_ARCHIVE_MEMBER')
   if n.startswith('data/') and not n.startswith('data/a22/online/'): raise ValueError('ONLY_A22_ONLINE_DATA_MAY_BE_DEPLOYED')
   dest=r/n
   data=z.read(entry)
   if n.startswith('results/jobs/') and dest.exists():
    if dest.read_bytes()!=data: raise ValueError('IMMUTABLE_REMOTE_JOB_CONFLICT')
    continue
   if n.startswith('results/a22/') and dest.exists():
    if n.endswith('external_cpu_receipts.json'):
     merged={{}}
     for item in json.loads(dest.read_bytes())+json.loads(data):
      key=item['scope']
      if key in merged and merged[key]!=item: raise ValueError('EXTERNAL_RECEIPT_CONFLICT')
      merged[key]=item
     data=(json.dumps(list(merged.values()),indent=2)+'\\n').encode()
    elif n.endswith('.jsonl'):
     rows=list(dict.fromkeys(dest.read_text().splitlines()+data.decode().splitlines()))
     data=('\\n'.join(rows)+'\\n').encode()
   plan.append((dest,data))
  for dest,data in plan:
   dest.parent.mkdir(parents=True,exist_ok=True)
   dest.write_bytes(data)
  row.update(status='A22_DEPLOYED',members=len(z.infolist()))
except BaseException as error:
 row['error_type']=type(error).__name__
finally:
 row['remote_process_cpu_seconds']=time.process_time()
 print(json.dumps(row))
"""
        row = _python(transport, code)
        row.update(member_count=len(members), compressed_bytes=archive.stat().st_size,
                   private_files_transferred=False, original_A20_A21_written=False)
        if row['status'] != 'A22_DEPLOYED':
            error = TransportFailure('Remote A22 deployment failed; paid extraction receipt preserved')
            error.accounting = row
            raise error
        return row


def _launch_code(stage, job, device, budget_stage):
    """Build a bounded controller; it never prints child logs or private inputs."""
    args = ['-B', '-u', '-m', 'a22.cli', stage, '--root', REMOTE,
            '--lock-root', SHARED, '--device', device, '--job', job]
    return f"""import ctypes,json,os,pathlib,subprocess,sys,time,uuid
origin=globals().get('_a22_remote_process_origin',time.perf_counter())
r=pathlib.Path(r'{REMOTE}')
sys.path.insert(0,str(r/'src'))
from a22.budget import load_config,history,merge_receipt,register_external,write_json,STAGE_GPU_CAPS
config=load_config(r)
prior=history(r,config)
job={job!r}
device={device!r}
main_stage={budget_stage!r}
row=dict(status='FAILED',job_id=job,device=device,stage=main_stage)
child=None
child_cpu=0.0
launch_query_cpu=0.0
{_windows_cpu_source()}
{_checkpoint_reader_source()}
try:
 if pathlib.Path(r'{SHARED_LOCK}').exists(): raise RuntimeError('SHARED_LOCK_EXISTS')
 if (r/'results/jobs'/job/'accounting_started.json').exists() or (r/'results/jobs'/job/'job_receipt.json').exists(): raise RuntimeError('JOB_ID_ALREADY_RESERVED')
 if device=='cuda':
  query=subprocess.Popen(['nvidia-smi','--query-compute-apps=pid','--format=csv,noheader'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
  try:
   busy_output,busy_errors=query.communicate(timeout=8)
  except subprocess.TimeoutExpired:
   query.kill()
   busy_output,busy_errors=query.communicate()
  finally:
   launch_query_cpu=measured_cpu(query)
  if query.returncode!=0 or busy_output.strip(): raise RuntimeError('GPU_QUEUE_NOT_CLEAR')
  if config['gpu_wall_cap_seconds']-prior['a22_gpu']<=2 or config['stage_gpu_caps_seconds'][main_stage]-prior['stage_gpu_seconds'][main_stage]<=2: raise RuntimeError('BUDGET_REFUSED')
 env=os.environ.copy()
 env.update(PYTHONPATH=str(r/'src'),PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1',A22_JOB_WALL_ORIGIN=str(origin),A22_BUDGET_STAGE=main_stage)
 (r/'runs').mkdir(parents=True,exist_ok=True)
 with (r/'runs'/ (job+'.stdout')).open('wb') as out,(r/'runs'/ (job+'.stderr')).open('wb') as err:
  child=subprocess.Popen([{PYTHON!r}]+{args!r},cwd=r,env=env,stdout=out,stderr=err)
  while child.poll() is None:
   child_cpu=max(child_cpu,measured_cpu(child))
   if device=='cuda':
    saved_checkpoint=checkpoint()
    usage=live_usage(time.perf_counter(),saved_checkpoint)
    active=(saved_checkpoint or {{}}).get('active_stage',main_stage)
    exceeded=watchdog_exceeded(usage,active)
    if exceeded:
     child.kill()
     child.wait(timeout=2)
     row['status']='TIMEOUT'
     break
   time.sleep(0.1)
  child_cpu=max(child_cpu,measured_cpu(child))
  row['exit_status']=child.returncode
  if row['status']!='TIMEOUT': row['status']='COMPLETE' if child.returncode==0 else 'FAILED'
except BaseException as error:
 row.update(controller_failure(error))
 if child is not None and child.poll() is None:
  child_cpu=max(child_cpu,measured_cpu(child))
  try:
   child.kill()
   child.wait(timeout=2)
  except BaseException as stop_error:
   row.update(status='STOP_UNCONFIRMED',stop_error_type=type(stop_error).__name__)
  child_cpu=max(child_cpu,measured_cpu(child))
finally:
 now=time.perf_counter()
 receipt_path=r/'results/jobs'/job/'job_receipt.json'
 try:
  saved=checkpoint()
 except BaseException as error:
  saved=last_checkpoint
  row['checkpoint_read_error']=True
  row['checkpoint_read_failure']=controller_failure(error,'checkpoint')
 child_ended=child is None or child.poll() is not None
 if child is not None and child_ended and not receipt_path.exists():
  saved=saved or dict(campaign='A22',job_id=job,stage=main_stage,device=device,counts={{}},corrections={{}},process_cpu_seconds=0)
  usage=live_usage(now,saved or {{}}) if device=='cuda' else {{s:0.0 for s in STAGE_GPU_CAPS}}
  saved.update(status=row['status'],wall_seconds=now-origin,gpu_occupation_seconds=sum(usage.values()),stage_gpu_seconds=usage,process_cpu_seconds=max(saved.get('process_cpu_seconds',0),child_cpu),watchdog_termination=row['status']=='TIMEOUT',child_CPU_measurement_available=child_cpu_measurement_available)
  merge_receipt(r,saved,config)
 if not child_ended:
  row['status']='STOP_UNCONFIRMED'
  saved=saved or dict(campaign='A22',job_id=job,stage=main_stage,device=device,counts={{}},corrections={{}},process_cpu_seconds=0,active_stage=main_stage)
  usage=live_usage(now,saved) if device=='cuda' else {{s:0.0 for s in STAGE_GPU_CAPS}}
  saved.update(status='STOP_UNCONFIRMED',wall_seconds=now-origin,gpu_occupation_seconds=sum(usage.values()),stage_gpu_seconds=usage,process_cpu_seconds=max(saved.get('process_cpu_seconds',0),child_cpu),checkpoint_perf_counter=now,child_stop_confirmed=False,child_CPU_measurement_available=child_cpu_measurement_available)
  write_json(r/'results/jobs'/job/'accounting_checkpoint.json',saved)
 if receipt_path.exists() and child is not None:
  paid=json.loads(receipt_path.read_text())
  overhead=max(0.0,now-origin-paid.get('gpu_occupation_seconds',0)) if device=='cuda' else 0.0
  child_tail=max(0.0,child_cpu-paid.get('process_cpu_seconds',0))
  register_external(r,'remote-launch-'+job,time.process_time()+launch_query_cpu+child_tail,gpu_seconds=overhead,wall_seconds=max(0.0,now-origin-paid.get('wall_seconds',0)),stage=main_stage,status=row['status'],measurement='remote foreground controller + queue-query CPU + measured child CPU tail; GPU inclusive tail beyond job receipt')
  row.update(child_CPU_tail_seconds=child_tail,child_CPU_tail_already_billed=True)
 elif not child_ended:
  register_external(r,'remote-controller-'+job,time.process_time()+launch_query_cpu,status='STOP_UNCONFIRMED',measurement='remote controller + queue-query CPU; live GPU/child CPU retained in checkpoint')
 else:
  register_external(r,'remote-attempt-'+uuid.uuid4().hex,time.process_time()+launch_query_cpu,gpu_seconds=now-origin if device=='cuda' else 0,wall_seconds=now-origin,stage=main_stage,status=row['status'],measurement='failed remote foreground preflight/controller + queue-query CPU and associated GPU wall')
 row.update(remote_process_cpu_seconds=time.process_time()+launch_query_cpu,remote_controller_CPU_already_billed=True,foreground=True,shared_lock='common A20 GPU lock',child_process_CPU_seconds=child_cpu,queue_query_CPU_seconds=launch_query_cpu,child_CPU_measurement_available=child_cpu_measurement_available,child_stop_confirmed=child_ended,checkpoint_transient_read_conflicts=checkpoint_read_conflicts,checkpoint_last_read_failure=checkpoint_last_read_failure,checkpoint_unreadable_seconds=max(0.0,time.perf_counter()-checkpoint_unreadable_since) if checkpoint_unreadable_since is not None else 0.0,checkpoint_unreadability_limit_seconds=CHECKPOINT_UNREADABILITY_SECONDS,checkpoint_reader='windows-share-read-write-delete' if os.name=='nt' else 'posix-read-bytes')
 print(json.dumps(row))
"""


def run(stage, job, device, private_config, *, root=ROOT, budget_stage=None):
    from a22.budget import STAGE_GPU_CAPS, history, load_config
    _job(job)
    if stage not in CLI_STAGES or device not in ('cpu', 'cuda'):
        raise ValueError('UNREGISTERED_A22_CLI_STAGE_OR_DEVICE')
    budget_stage = budget_stage or CLI_STAGES[stage]
    if budget_stage not in STAGE_GPU_CAPS:
        raise ValueError('UNREGISTERED_A22_BUDGET_STAGE')
    root = Path(root)
    config, prior = load_config(root), history(root)
    if job in prior['jobs']:
        raise ValueError('A22_JOB_ID_ALREADY_BILLED')
    if device == 'cuda' and (prior['a22_gpu'] >= config['gpu_wall_cap_seconds']
                             or prior['stage_gpu_seconds'][budget_stage] >= config['stage_gpu_caps_seconds'][budget_stage]):
        from a20.costs import BudgetExceeded
        raise BudgetExceeded('A22_REMOTE_PREFLIGHT_GPU_BUDGET_REFUSAL')
    transport = connection(private_config, root=root)
    row = _python(transport, _launch_code(stage, job, device, budget_stage), force_file=True)
    if row['status'] != 'COMPLETE':
        if row['status'] == 'FAILED_REMOTE_BOOTSTRAP' and device == 'cuda':
            row.update(remote_unbilled_GPU_seconds=row.get('remote_wall_seconds', 0),
                       remote_unbilled_GPU_stage=budget_stage)
        error = TransportFailure('Remote A22 job did not complete; pull its paid receipts')
        error.accounting = row
        raise error
    return row


def status(job, private_config, *, root=ROOT):
    _job(job)
    transport = connection(private_config, root=root)
    code = f"""import json,pathlib,subprocess,time
r=pathlib.Path(r'{REMOTE}')
path=r/'results/jobs'/{job!r}/'job_receipt.json'
row=dict(status='ENDED_OR_NOT_STARTED',job_id={job!r},shared_lock_exists=pathlib.Path(r'{SHARED_LOCK}').exists(),receipt_available=path.exists())
if path.exists():
 saved=json.loads(path.read_text())
 row.update(status=saved.get('status'),stage=saved.get('stage'),process_cpu_seconds=saved.get('process_cpu_seconds'),gpu_occupation_seconds=saved.get('gpu_occupation_seconds'),counts=saved.get('counts',{{}}))
elif (r/'results/jobs'/{job!r}/'accounting_checkpoint.json').exists():
 row['status']='STARTED_RECEIPT_NOT_FINAL'
 saved=json.loads((r/'results/jobs'/{job!r}/'accounting_checkpoint.json').read_text())
 row.update(stage=saved.get('active_stage'),process_cpu_seconds=saved.get('process_cpu_seconds'),gpu_occupation_seconds=saved.get('gpu_occupation_seconds'),counts=saved.get('counts',{{}}))
progress=r/'results/a22/stage_a/progress.jsonl'
if progress.exists():
 lines=progress.read_text().splitlines()
 if lines: row['stage_a_latest_progress']=json.loads(lines[-1])
row['remote_process_cpu_seconds']=time.process_time()
print(json.dumps(row))
"""
    row = _python(transport, code, timeout=30)
    if row.get('status') == 'FAILED_REMOTE_BOOTSTRAP':
        error = TransportFailure('Remote status failed; paid import CPU receipt preserved')
        error.accounting = row
        raise error
    return row


def _screen_owner_matches(line, root, job):
    import shlex
    try:
        args = [part.strip('"') for part in shlex.split(line, posix=False)]
        module = args.index('-m')
        return (args[module+1] == 'a22.cli' and args[module+2] in ('screen','screen-resume')
                and args[args.index('--job')+1] == job
                and args[args.index('--root')+1].replace(chr(92),'/').casefold()
                    == str(root).replace(chr(92),'/').casefold())
    except (ValueError, IndexError):
        return False


def stop(job, private_config, *, root=ROOT):
    """Stop only a confirmed A22 lock owner; never clear an unknown lock."""
    _job(job)
    import inspect
    transport = connection(private_config, root=root)
    code = f'''import json,pathlib,subprocess,time
r=pathlib.Path(r'{REMOTE}')
lock=pathlib.Path(r'{SHARED_LOCK}')
job={job!r}
row=dict(status='REFUSED',job_id=job)
query_cpu=0.0
{_windows_cpu_source()}
{inspect.getsource(_screen_owner_matches)}
def command(args):
 global query_cpu
 p=subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 try:
  out,err=p.communicate(timeout=10)
 except subprocess.TimeoutExpired:
  p.kill()
  p.communicate()
  raise RuntimeError('CONTROL_QUERY_TIMEOUT')
 finally:
  query_cpu+=measured_cpu(p)
 if p.returncode: raise RuntimeError('CONTROL_QUERY_FAILED')
 return out.decode('utf-8-sig',errors='replace').strip()
try:
 if not lock.exists(): raise RuntimeError('NO_LOCK_TO_STOP')
 owner=json.loads(lock.read_text())
 pid=int(owner['pid'])
 probe=command(['powershell.exe','-NoProfile','-Command',f'Get-CimInstance Win32_Process -Filter "ProcessId = {{pid}}" | Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress'])
 process=json.loads(probe) if probe else None
 line=(process or {{}}).get('CommandLine','').replace(chr(92),'/')
 if process:
  if not _screen_owner_matches(line,r,job): raise RuntimeError('LOCK_OWNER_IS_NOT_REQUESTED_A22_SCREEN')
  row['owner_identity_confirmed']=True
  command(['taskkill.exe','/PID',str(pid),'/T','/F'])
 else:
  started=json.loads((r/'results/jobs'/job/'accounting_started.json').read_text())
  paid=json.loads((r/'results/jobs'/job/'job_receipt.json').read_text())
  if started.get('pid')!=pid or paid.get('job_id')!=job or paid.get('status') not in ('FAILED','TIMEOUT','BUDGET_REFUSED'): raise RuntimeError('ENDED_JOB_AND_LOCK_IDENTITY_NOT_CONFIRMED')
  row.update(owner_identity_confirmed=True,already_ended_paid_job=True)
 ended=False
 for attempt in range(30):
  probe=command(['powershell.exe','-NoProfile','-Command',f'Get-CimInstance Win32_Process -Filter "ProcessId = {{pid}}" | Select-Object ProcessId | ConvertTo-Json -Compress'])
  if not probe or probe=='null':
   ended=True
   break
  time.sleep(.1)
 if not ended: raise RuntimeError('REQUESTED_CHILD_STOP_UNCONFIRMED')
 deadline=time.perf_counter()+20
 while True:
  queue=command(['nvidia-smi','--query-compute-apps=pid','--format=csv,noheader'])
  if not queue: break
  if any(line.strip()!=str(pid) for line in queue.splitlines()): raise RuntimeError('OTHER_GPU_OWNER_AFTER_STOP')
  if time.perf_counter()>=deadline: raise RuntimeError('GPU_QUEUE_NOT_CLEAR_AFTER_STOP')
  time.sleep(.1)
 if json.loads(lock.read_text())!=owner: raise RuntimeError('LOCK_OWNER_CHANGED')
 lock.unlink()
 row.update(status='A22_OWN_SCREEN_STOPPED',child_stop_confirmed=True,gpu_queue_empty=True,stale_own_lock_removed=True,
   reason='exact redundant material-constraint representation and cached continuation; no physics protocol change')
except BaseException as error:
 row['error_type']=type(error).__name__
 if isinstance(error,RuntimeError): row['error_code']=str(error)
finally:
 row.update(remote_process_cpu_seconds=time.process_time()+query_cpu,control_query_CPU_seconds=query_cpu,
            child_CPU_measurement_available=child_cpu_measurement_available)
 print(json.dumps(row))
'''
    row = _python(transport, code, force_file=True)
    if row['status'] != 'A22_OWN_SCREEN_STOPPED':
        error = TransportFailure('Requested A22 stop was not confirmed; lock preserved')
        error.accounting = row
        raise error
    return row


def pull(private_config, *, root=ROOT):
    root = Path(root)
    transport = connection(private_config, root=root)
    name = 'a22-results-' + uuid.uuid4().hex + '.zip'
    code = f"""import json,pathlib,time,zipfile
r=pathlib.Path(r'{REMOTE}')
row=dict(status='FAILED')
try:
 with zipfile.ZipFile(r/'{name}','x',zipfile.ZIP_STORED) as z:
  paths=list((r/'results/a22').rglob('*'))+list((r/'results/jobs').glob('a22-*/*'))
  for path in paths:
   if path.is_file() and not path.is_symlink() and not path.name.endswith('.tmp'):
    z.write(path,path.relative_to(r).as_posix())
 row.update(status='A22_ARCHIVED',archive_bytes=(r/'{name}').stat().st_size)
except BaseException as error:
 row['error_type']=type(error).__name__
finally:
 row['remote_process_cpu_seconds']=time.process_time()
 print(json.dumps(row))
"""
    row = _python(transport, code)
    if row['status'] != 'A22_ARCHIVED':
        error = TransportFailure('Remote archive failed; paid CPU receipt preserved')
        error.accounting = row
        raise error
    with tempfile.TemporaryDirectory() as directory:
        archive = Path(directory) / name
        transport.copy_from(name, archive)
        row['merged_files'] = _merge_jobs(archive, root)
    from a22.budget import history, write_json
    write_json(root/'results/a22/BUDGET_CURRENT.json', history(root))
    row.update(status='A22_RESULTS_SAVED',original_A20_A21_written=False)
    return row


def _child_usage():
    try:
        import resource
        usage = resource.getrusage(resource.RUSAGE_CHILDREN)
        return usage.ru_utime + usage.ru_stime
    except ImportError:
        return 0.0


def _record_transport(root, action, details, status_value, started, child_before):
    from a22.budget import register_external, write_json
    root = Path(root)
    identity = 'a22-transport-' + uuid.uuid4().hex
    remote = 0.0 if details.get('remote_controller_CPU_already_billed') else float(details.get('remote_process_cpu_seconds', 0))
    failed_gpu = float(details.get('remote_unbilled_GPU_seconds', 0))
    cpu = time.process_time() + max(0.0, _child_usage() - child_before) + remote
    row = dict(scope=identity, action=action, status=status_value,
               process_cpu_seconds=cpu, wall_seconds=time.perf_counter()-started,
               remote_process_cpu_seconds=remote, GPU_seconds=failed_gpu,
               measurement='local process startup/import CPU + local child CPU + unbilled remote transport CPU',
               details=details, new_SHA256_checks=0)
    path = root / 'results/a22/transport' / (identity + '.json')
    write_json(path, row)
    register_external(root, identity, cpu, wall_seconds=row['wall_seconds'],
                      gpu_seconds=failed_gpu, stage=details.get('remote_unbilled_GPU_stage'),
                      receipt=path.relative_to(root).as_posix(), status=status_value,
                      measurement=row['measurement'])


def main(argv=None):
    started, child_before = time.perf_counter(), _child_usage()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('preflight', 'deploy', 'run', 'status', 'stop', 'pull'))
    parser.add_argument('--private-config', required=True)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--stage', choices=tuple(CLI_STAGES))
    parser.add_argument('--budget-stage', choices=('screen_health', 'features', 'direction', 'image', 'runtime', 'train', 'exception'))
    parser.add_argument('--job')
    parser.add_argument('--device', choices=('cpu', 'cuda'))
    args = parser.parse_args(argv)
    if args.action == 'run' and (args.stage is None or args.job is None or args.device is None):
        parser.error('run requires explicit --stage, --job and --device')
    if args.action in ('status','stop') and args.job is None:
        parser.error('status/stop requires --job')
    details, result = {}, 'FAILED'
    try:
        if args.action == 'run':
            details = run(args.stage, args.job, args.device, args.private_config, root=args.root, budget_stage=args.budget_stage)
        elif args.action in ('status','stop'):
            details = globals()[args.action](args.job, args.private_config, root=args.root)
        else:
            details = globals()[args.action](args.private_config, root=args.root)
        result = 'COMPLETE'
        print(json.dumps(details, allow_nan=False))
        return 0
    except TransportFailure as error:
        details.update(getattr(error, 'accounting', {}))
        print(str(error), file=sys.stderr)
        return 2
    except Exception as error:
        print('A22 transport failed: ' + type(error).__name__ + '; private details suppressed', file=sys.stderr)
        return 2
    finally:
        try:
            _record_transport(args.root, args.action, details, result, started, child_before)
        except Exception as error:
            print('A22 transport accounting failed: ' + type(error).__name__ + '; private details suppressed', file=sys.stderr)
            return 2


if __name__ == '__main__':
    raise SystemExit(main())
