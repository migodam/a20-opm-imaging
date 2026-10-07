"""Foreground R1 transport using the existing private A22 SSH implementation."""
import argparse
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import time
import uuid
import zipfile
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('a22_existing_transport', ROOT/'tools/a22_remote_jobs.py')
transport = importlib.util.module_from_spec(spec)
spec.loader.exec_module(transport)
transport.REMOTE = 'D:/AI/A22_R1_SUBSPACE_SEPARATION'
REMOTE = transport.REMOTE
sys.path.insert(0, str(ROOT/'src'))
from a22_r1.accounting import external_receipt, paid_history
from a20.costs import write_json


def deploy(connection):
    members = []
    for folder in ('src/a22_r1', 'src/a22', 'src/a20', 'src/a20_r1', 'vendor'):
        members += [p for p in (ROOT/folder).rglob('*.py') if '__pycache__' not in p.parts]
    members += list((ROOT/'data/a22/online').glob('*.npz'))
    members += [ROOT/'configs'/name for name in ('a22.json','a22_portable.json','a22_r1.json','frozen.json','a20_r1.json','parents.json')]
    for sid in (2001,2003,2014,2009):
        folder = ROOT/'results/a22/stage_a'/f'scene_{sid}'
        members += [folder/name for name in ('online_factors.npz','online_split_16.npz','online_provenance.json',
                                            'frozen_online_directions.json','frozen_online_budgets.json')]
    members += [ROOT/'SUBSPACE_SEPARATION_PROTOCOL.md']
    ledger = ROOT/'results/a22_r1/COST_LEDGER.jsonl'
    if ledger.exists(): members.append(ledger)
    relative = [p.relative_to(ROOT).as_posix() for p in members]
    if any('OFFLINE' in p or 'private' in p or 'offline_eval' in p for p in relative):
        raise ValueError('R1_REMOTE_ONLINE_UPLOAD_BOUNDARY_FAILED')
    name = 'r1-online-source-' + uuid.uuid4().hex + '.zip'
    with tempfile.TemporaryDirectory() as d:
        path = Path(d)/name
        with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
            for p, rel in zip(members, relative): z.write(p,rel)
        connection.shell("if(Test-Path '"+transport.SHARED_LOCK+"'){throw 'Shared lock exists'}; New-Item -ItemType Directory -Force '"+REMOTE+"' | Out-Null")
        connection.copy_to(path,name)
        row = transport._python(connection, "import pathlib,zipfile,json,time\nr=pathlib.Path("+repr(REMOTE)+")\nwith zipfile.ZipFile(r/"+repr(name)+") as z:\n for n in z.namelist():\n  if pathlib.PurePosixPath(n).is_absolute() or '..' in pathlib.PurePosixPath(n).parts or ':' in n or 'OFFLINE' in n or 'private' in n: raise ValueError('INVALID_ONLINE_UPLOAD')\n  dest=r/n;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(z.read(n))\nprint(json.dumps(dict(status='DEPLOYED',members="+str(len(relative))+",remote_process_cpu_seconds=time.process_time())))")
    return row


def run(connection, job, stage='freeze'):
    config = json.loads((ROOT/'configs/a22_r1.json').read_text())
    prior = paid_history(ROOT)
    device='cuda' if stage=='freeze' else 'cpu'
    seconds = max(0., (config['gpu_occupation_cap_seconds']-prior['gpu']-10.) if device=='cuda'
                  else config['cpu_cap_seconds']-prior['cpu']-20.)
    if seconds < 30: raise ValueError('R1_RESOURCE_BUDGET_REFUSED')
    code = f"""import json,os,pathlib,subprocess,time,sys
{transport._windows_cpu_source()}
r=pathlib.Path({REMOTE!r}); job={job!r}; origin=time.perf_counter(); stage={stage!r}
if pathlib.Path({transport.SHARED_LOCK!r}).exists(): raise RuntimeError('SHARED_LOCK_EXISTS')
query=subprocess.Popen(['nvidia-smi','--query-compute-apps=pid','--format=csv,noheader'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
qout,qerr=query.communicate(timeout=8); queue_cpu=measured_cpu(query)
if query.returncode or qout.strip(): raise RuntimeError('GPU_QUEUE_NOT_CLEAR')
if stage=='replay':
 # Byte transfer of existing evaluator inputs, after all online scores exist.
 for sid in (2001,2003,2014,2009):
  if json.loads((r/f'results/a22_r1/online/scene_{{sid}}.json').read_text()).get('status')!='COMPLETE': raise RuntimeError('ONLINE_FREEZE_MISSING')
 old=pathlib.Path('D:/AI/A22_THREE_FOLD_OPM/results/a22/stage_a')
 files=[old/'direction_metrics.jsonl']
 for sid in (2001,2003,2014,2009):
  folder=old/f'scene_{{sid}}';files+=list(folder.glob('OFFLINE_label_*.npz'))+[folder/'OFFLINE_J_benchmark.npz']
 for source in files:
  dest=r/'results/a22/stage_a'/source.relative_to(old); data=source.read_bytes()
  if dest.exists() and dest.read_bytes()!=data: raise RuntimeError('IMMUTABLE_OFFLINE_CACHE_CONFLICT')
  if not dest.exists(): dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
env=os.environ.copy();env.update(PYTHONPATH=str(r/'src'),PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
(r/'runs').mkdir(parents=True,exist_ok=True)
timed_out=False
with (r/'runs'/(job+'.stdout')).open('wb') as out,(r/'runs'/(job+'.stderr')).open('wb') as err:
 child=subprocess.Popen([{transport.PYTHON!r},'-B','-u','-m','a22_r1.cli',stage,'--root',{REMOTE!r},'--job',job,'--device',{device!r},'--lock-root',{transport.SHARED!r}],cwd=r,env=env,stdout=out,stderr=err)
 try:
  child.wait(timeout={seconds!r})
 except subprocess.TimeoutExpired:
  timed_out=True;child.kill();child.wait(timeout=5)
 measured_child_cpu=measured_cpu(child)
elapsed=time.perf_counter()-origin
receipt_path=r/'results/a22_r1/jobs'/job/'job_receipt.json'
receipt=json.loads(receipt_path.read_text()) if receipt_path.exists() else None
if timed_out:
 lock=pathlib.Path({transport.SHARED_LOCK!r})
 if lock.exists() and json.loads(lock.read_text()).get('pid')==child.pid: lock.unlink()
row=dict(status='COMPLETE' if child.returncode==0 else 'FAILED',exit_status=child.returncode,timed_out=timed_out,child_stop_confirmed=child.poll() is not None,controller_wall_seconds=elapsed,controller_cpu_seconds=time.process_time(),measured_child_cpu_seconds=measured_child_cpu,child_CPU_measurement_available=child_cpu_measurement_available,job_receipt=receipt,remote_process_cpu_seconds=time.process_time()+queue_cpu)
print(json.dumps(row))
"""
    return transport._python(connection, code, timeout=seconds+30., force_file=True)


def pull(connection):
    name = 'r1-evidence-' + uuid.uuid4().hex + '.zip'
    row = transport._python(connection, "import pathlib,zipfile,json,time\nr=pathlib.Path("+repr(REMOTE)+")\nwith zipfile.ZipFile(r/"+repr(name)+",'w',zipfile.ZIP_DEFLATED) as z:\n for p in (r/'results/a22_r1').rglob('*'):\n  if p.is_file(): z.write(p,p.relative_to(r).as_posix())\n for p in (r/'runs').glob('a22-r1-*'):\n  if p.is_file(): z.write(p,p.relative_to(r).as_posix())\nprint(json.dumps(dict(status='PACKED',remote_process_cpu_seconds=time.process_time())))")
    with tempfile.TemporaryDirectory() as d:
        archive = Path(d)/name
        connection.copy_from(name,archive)
        with zipfile.ZipFile(archive) as z:
            plan = []
            for n in z.namelist():
                if not (n.startswith('results/a22_r1/') or n.startswith('runs/a22-r1-')) or '..' in Path(n).parts or ':' in n:
                    raise ValueError('INVALID_R1_RESULT_MEMBER')
                p=ROOT/n; incoming=z.read(n)
                if p.exists() and p.read_bytes()!=incoming:
                    # Windows CRLF and ZIP metadata are not changes to a freeze.
                    # Scientific values must still agree exactly; no tolerance
                    # or replacement of different arrays is permitted here.
                    if n.endswith('.json'):
                        if json.loads(p.read_text()) == json.loads(incoming.decode()):
                            continue
                    if n.endswith('.npz'):
                        with np.load(p, allow_pickle=False) as old, np.load(io.BytesIO(incoming), allow_pickle=False) as new:
                            same = set(old.files) == set(new.files)
                            if same:
                                for member in old.files:
                                    a,b=old[member],new[member]
                                    equal=(np.array_equal(a,b,equal_nan=True) if a.dtype.kind not in 'US'
                                           else np.array_equal(a,b))
                                    if a.shape!=b.shape or a.dtype!=b.dtype or not equal:
                                        same=False;break
                            if same: continue
                    if n.endswith('COST_LEDGER.jsonl') or n.endswith('FAILURE_LEDGER.jsonl'):
                        local=[json.loads(line) for line in p.read_text().splitlines() if line.strip()]
                        incoming_rows=[json.loads(line) for line in incoming.decode().splitlines() if line.strip()]
                        rows={}
                        for item in local+incoming_rows:
                            key=item.get('receipt_id') or json.dumps(item,sort_keys=True)
                            if key in rows and rows[key]!=item: raise ValueError('CONFLICTING_R1_RECEIPT')
                            rows[key]=item
                        combined=('\n'.join(json.dumps(item) for item in rows.values())+'\n').encode()
                        plan.append((p,combined));continue
                    if n.startswith('results/a22_r1/offline/') or n == 'results/a22_r1/OFFLINE_SPLIT_FREEZE.json':
                        # Retain a platform variant for audit. It cannot replace
                        # the frozen local diagnostic or any online split.
                        variant=ROOT/'results/a22_r1/platform_variants/windows'/n
                        if variant.exists() and variant.read_bytes()!=incoming:
                            raise ValueError('R1_PLATFORM_VARIANT_CONFLICT:'+n)
                        if not variant.exists(): plan.append((variant,incoming))
                        continue
                    raise ValueError('R1_IMMUTABLE_RESULT_CONFLICT:'+n)
                if not p.exists(): plan.append((p,incoming))
            for p,data in plan: p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
    return dict(row,files=len(plan))


def main():
    p=argparse.ArgumentParser()
    p.add_argument('action',choices=('preflight','deploy','run','pull'))
    p.add_argument('--private-config',required=True)
    p.add_argument('--job',default='a22-r1-freeze-001')
    p.add_argument('--stage',choices=('freeze','replay'),default='freeze')
    args=p.parse_args()
    connection=transport.connection(args.private_config,root=ROOT)
    cpu,wall=time.process_time(),time.perf_counter()
    row={'status':'FAILED'}
    try:
        if args.action=='preflight': row=transport.preflight(args.private_config,root=ROOT)
        elif args.action=='deploy': row=deploy(connection)
        elif args.action=='run': row=run(connection,args.job,args.stage)
        else: row=pull(connection)
        status='COMPLETE' if row['status'] not in ('FAILED','FAILED_REMOTE_BOOTSTRAP') else 'FAILED'
    except BaseException as error:
        status='FAILED';row=dict(status=status,error_type=type(error).__name__,error=str(error))
    identity='transport-'+args.action+'-'+uuid.uuid4().hex
    directory=ROOT/'results/a22_r1/transport';directory.mkdir(parents=True,exist_ok=True)
    write_json(directory/(identity+'.json'),row)
    # Run child receipt is additive once; only unbilled controller/tail goes here.
    remote_cpu=row.get('remote_process_cpu_seconds',0.)
    gpu_tail=0.;child_tail=0.
    if args.action=='run':
        paid=row.get('job_receipt') or {}
        gpu_tail=max(0.,row.get('controller_wall_seconds',0.)-paid.get('gpu_occupation_seconds',0.)) if args.stage=='freeze' else 0.
        child_tail=max(0.,row.get('measured_child_cpu_seconds',0.)-paid.get('process_cpu_seconds',0.))
    external_receipt(ROOT,identity,cpu=time.process_time()-cpu+remote_cpu+child_tail,
        wall=time.perf_counter()-wall,gpu=gpu_tail,status=status,
        measurement='local transport CPU + remote controller/query CPU + measured unbilled child CPU tail',detail={'action':args.action,'row':str((directory/(identity+'.json')).relative_to(ROOT))})
    visible=dict(row)
    if 'job_receipt' in visible:
        paid=visible['job_receipt'] or {}
        visible['job_receipt']={key:paid.get(key) for key in ('status','wall_seconds','process_cpu_seconds','gpu_occupation_seconds','counts')}
    print(json.dumps(dict(status=status,action=args.action,detail=visible)))
    return 0 if status=='COMPLETE' else 1


if __name__=='__main__': sys.exit(main())
