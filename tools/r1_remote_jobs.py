"""One foreground R1 SSH job; existing A20 lock, original evidence retained."""
from pathlib import Path
import argparse
import base64
import json
import os
import subprocess
import tempfile
import zipfile

from remote_jobs import connection, shell, copy

ROOT = Path(__file__).resolve().parents[1]
REMOTE = 'D:/AI/A20_OPM_IMAGING_R1'
SHARED = 'D:/AI/A20_OPM_IMAGING'
PYTHON = 'D:/python/python.exe'


def deploy():
    target, _ = connection()
    with tempfile.TemporaryDirectory() as directory:
        archive = Path(directory)/'r1-upload.zip'
        with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
            for folder in ('src','vendor','configs','protocol','data','tests'):
                for p in (ROOT/folder).rglob('*'):
                    if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc':
                        z.write(p,p.relative_to(ROOT).as_posix())
            for name in ('EXTERNAL_CPU_RECEIPTS.json','BUDGET_FINAL.json','G0_LOCAL.json',
                         'G0_REAL.json','G0_ALGEBRA.json'):
                p=ROOT/'results'/name
                z.write(p,p.relative_to(ROOT).as_posix())
            # Canonical references and old FIXED-DEEP steps only need their
            # existing storage; no full-J/H/current cache is transported.
            for p in (ROOT/'results/replay').rglob('*'):
                if p.is_file() and (p.suffix=='.npz' or p.name=='replay.jsonl'):
                    z.write(p,p.relative_to(ROOT).as_posix())
            for p in (ROOT/'results/jobs').glob('*/job_receipt.json'):
                z.write(p,p.relative_to(ROOT).as_posix())
            # Local R1 checks are already charged and must precede remote work.
            for p in (ROOT/'results/jobs').glob('r1-*/cost.jsonl'):
                z.write(p,p.relative_to(ROOT).as_posix())
            for name in ('external_cpu_receipts.json','PREFLIGHT.json','RUNTIME_PREFLIGHT.json'):
                p=ROOT/'results/a20_r1'/name
                if p.exists(): z.write(p,p.relative_to(ROOT).as_posix())
        shell(f"New-Item -ItemType Directory -Force '{REMOTE}' | Out-Null")
        copy(archive,f'{target}:{REMOTE}/r1-upload.zip')
        code=f"import zipfile; z=zipfile.ZipFile(r'{REMOTE}/r1-upload.zip'); z.extractall(r'{REMOTE}'); print('R1_DEPLOYED',len(z.namelist()))"
        encoded=base64.b64encode(code.encode()).decode()
        print(shell(f"& '{PYTHON}' -c \"import base64; exec(base64.b64decode('{encoded}'))\""))


def run(stage, job, device):
    if not job.startswith('r1-') or any(not(c.isalnum() or c in '-_') for c in job):
        raise ValueError('Invalid job ID')
    target,key=connection()
    args=['-u','-m','a20_r1.cli',stage,'--device',device,'--job',job,'--lock-root',SHARED]
    encoded_args=','.join("'"+x+"'" for x in args)
    script=f"""
$ProgressPreference='SilentlyContinue'
$ErrorActionPreference='Stop'
Set-Location '{REMOTE}'
$env:PYTHONPATH='{REMOTE}/src'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:OPENBLAS_NUM_THREADS='1'
$env:OMP_NUM_THREADS='1'
$env:MKL_NUM_THREADS='1'
$env:NUMEXPR_NUM_THREADS='1'
$busy=@(& nvidia-smi --query-compute-apps=pid,process_name --format=csv,noheader)
if($LASTEXITCODE -ne 0) {{ throw 'GPU inventory failed' }}
if($busy.Count -gt 0) {{ throw 'Existing GPU compute job' }}
if(Test-Path '{SHARED}/runs/gpu.lock') {{ throw 'Shared A20 GPU lock exists' }}
New-Item -ItemType Directory -Force '{REMOTE}/runs' | Out-Null
& '{PYTHON}' @({encoded_args}) 1>'{REMOTE}/runs/{job}.stdout' 2>'{REMOTE}/runs/{job}.stderr'
$rc=$LASTEXITCODE
Get-Content '{REMOTE}/runs/{job}.stdout' -Tail 6
Get-Content '{REMOTE}/runs/{job}.stderr' -Tail 15
exit $rc
"""
    encoded=base64.b64encode(script.encode('utf-16le')).decode()
    completed = subprocess.run(['ssh','-i',key,'-o','BatchMode=yes','-o','ConnectTimeout=8',
                    '-o','StrictHostKeyChecking=yes',target,
                    'powershell.exe -NoProfile -EncodedCommand '+encoded],check=False)
    if completed.returncode:
        # A protocol stop is a nonzero remote job exit. Preserve the pulled
        # receipt without printing private connection arguments in a traceback.
        raise SystemExit('Remote job exit '+str(completed.returncode)+
                         '; pull the immutable receipt before judging the failure')


def status(job):
    if any(not(c.isalnum() or c in '-_') for c in job): raise ValueError('Invalid job')
    print(shell(f"""
$p=Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object {{$_.CommandLine -match 'a20_r1[.]cli' -and $_.CommandLine -match '--job +{job}( |$)'}}
if($p) {{$v=Get-Process -Id $p.ProcessId; Write-Output ('RUNNING CPU='+$v.CPU+' RSS='+$v.WorkingSet64)}} else {{Write-Output 'ENDED_OR_NOT_STARTED'}}
if(Test-Path '{REMOTE}/results/jobs/{job}/job_receipt.json') {{Get-Content '{REMOTE}/results/jobs/{job}/job_receipt.json' -Raw}}
if(Test-Path '{REMOTE}/results/a20_r1/anatomy/rows.jsonl') {{Write-Output ('ROWS='+(@(Get-Content '{REMOTE}/results/a20_r1/anatomy/rows.jsonl').Count))}}
Get-Content '{REMOTE}/runs/{job}.stderr' -Tail 10 -ErrorAction SilentlyContinue
"""))


def pull():
    target,_=connection()
    external=ROOT/'results/a20_r1/external_cpu_receipts.json'
    local=json.loads(external.read_text())
    code=f"""import pathlib,zipfile
r=pathlib.Path(r'{REMOTE}')
z=zipfile.ZipFile(r/'r1-results.zip','w',zipfile.ZIP_DEFLATED)
paths=list((r/'results/a20_r1').rglob('*'))
paths+=list((r/'results/jobs').glob('r1-*/*'))
paths+=[r/n for n in ('GATE_DECISION.json','COST_LEDGER.jsonl','FAILURE_LEDGER.jsonl')]
for p in paths:
 if p.is_file(): z.write(p,p.relative_to(r).as_posix())
z.close()
print('R1_ARCHIVED')
"""
    encoded=base64.b64encode(code.encode()).decode()
    print(shell(f"& '{PYTHON}' -c \"import base64; exec(base64.b64decode('{encoded}'))\""))
    with tempfile.TemporaryDirectory() as directory:
        archive=Path(directory)/'r1-results.zip'
        copy(f'{target}:{REMOTE}/r1-results.zip',archive)
        with zipfile.ZipFile(archive) as z:
            for name in z.namelist():
                if name.startswith('/') or '..' in Path(name).parts: raise ValueError('Invalid archive member')
            z.extractall(ROOT)
    merged={}
    for row in json.loads(external.read_text())+local:
        if row['scope'] not in merged or row['process_cpu_seconds']>merged[row['scope']]['process_cpu_seconds']:
            merged[row['scope']]=row
    external.write_text(json.dumps(list(merged.values()),indent=2)+'\n')
    # The aggregate ledger is a view of immutable job logs, including the
    # local preflight/report. A remote pull must not erase local paid records.
    with (ROOT/'COST_LEDGER.jsonl').open('w',encoding='utf-8') as ledger:
        for p in sorted((ROOT/'results/jobs').glob('r1-*/cost.jsonl')):
            ledger.write(p.read_text(encoding='utf-8'))
    print('R1_RESULTS_SAVED')


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('action',choices=['deploy','run','status','pull'])
    p.add_argument('--stage',choices=['preflight','anatomy','closed-loop','report'])
    p.add_argument('--job')
    p.add_argument('--device',choices=['cpu','cuda'],default='cuda')
    a=p.parse_args()
    if a.action=='deploy': deploy()
    elif a.action=='run': run(a.stage,a.job,a.device)
    elif a.action=='status': status(a.job)
    else: pull()
