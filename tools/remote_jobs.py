"""Optional SSH transport for one bounded Windows CUDA job, not a service.

Set A20_SSH_TARGET and A20_SSH_KEY in your private environment. Credentials,
host addresses and connection configuration are never stored in the package.
Archive transport uses ZIP integrity only; it performs no new SHA256 checks.
"""
from pathlib import Path
import argparse
import base64
import json
import os
import subprocess
import tempfile
import zipfile

ROOT=Path(__file__).resolve().parents[1]
REMOTE='D:/AI/A20_OPM_IMAGING'
PYTHON='D:/python/python.exe'


def connection():
    return os.environ['A20_SSH_TARGET'], os.environ['A20_SSH_KEY']


def shell(script):
    target,key=connection()
    script="$ProgressPreference='SilentlyContinue';\n"+script
    code=base64.b64encode(script.encode('utf-16le')).decode()
    return subprocess.check_output(['ssh','-i',key,'-o','BatchMode=yes','-o','ConnectTimeout=8',
        '-o','StrictHostKeyChecking=yes',target,'powershell.exe -NoProfile -EncodedCommand '+code],text=True).strip()


def copy(source,dest):
    _,key=connection()
    subprocess.run(['scp','-i',key,'-o','BatchMode=yes','-o','ConnectTimeout=8',
                    '-o','StrictHostKeyChecking=yes',str(source),str(dest)],check=True)


def deploy():
    target,_=connection()
    # Results are retrieved separately; never overwrite earlier remote jobs.
    with tempfile.TemporaryDirectory() as temp:
        archive=Path(temp)/'upload.zip'
        with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
            for directory in ('src','vendor','configs','protocol','data','tests'):
                for path in sorted((ROOT/directory).rglob('*')):
                    if path.is_file() and '__pycache__' not in path.parts and not path.name.endswith('.pyc'):
                        z.write(path,path.relative_to(ROOT).as_posix())
            for name in ('results/EXTERNAL_CPU_RECEIPTS.json','results/SETUP_RECEIPT.json','results/G0_LOCAL.json','results/G0_ALGEBRA.json'):
                if (ROOT/name).exists():
                    z.write(ROOT/name,name)
            # Local CPU jobs are part of the same budget; remote job receipts
            # are never replaced by this transport snapshot.
            for path in (ROOT/'results/jobs').glob('local-*/*'):
                if path.is_file():
                    z.write(path,path.relative_to(ROOT).as_posix())
            # The transport failure never created a remote CLI receipt.
            for path in (ROOT/'results/jobs/g0-real-01').glob('*'):
                if path.is_file():
                    z.write(path,path.relative_to(ROOT).as_posix())
        shell(f"New-Item -ItemType Directory -Force '{REMOTE}' | Out-Null")
        copy(archive,f'{target}:{REMOTE}/upload.zip')
        script=f"import zipfile; z=zipfile.ZipFile(r'{REMOTE}/upload.zip'); z.extractall(r'{REMOTE}'); print('DEPLOYED',len(z.namelist()))"
        encoded=base64.b64encode(script.encode()).decode()
        print(shell(f"& '{PYTHON}' -c \"import base64; exec(base64.b64decode('{encoded}'))\""))


def start(stage,job,parents=None,iterations=None):
    # Exact choices prevent PowerShell injection through job/stage arguments.
    if any(not (c.isalnum() or c in '-_') for c in job):
        raise ValueError('Unsafe job id')
    options=['-m','a20.cli',stage,'--device','cuda','--job',job]
    if parents:
        options+=['--parents']+[str(int(x)) for x in parents]
    if iterations:
        options+=['--iterations']+[str(int(x)) for x in iterations]
    args=','.join("'"+x+"'" for x in options)
    script=f"""
$ErrorActionPreference='Stop'
$env:PYTHONPATH='{REMOTE}/src'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:OPENBLAS_NUM_THREADS='1'
$env:OMP_NUM_THREADS='1'
$env:MKL_NUM_THREADS='1'
$env:NUMEXPR_NUM_THREADS='1'
$busy=@(& nvidia-smi --query-compute-apps=pid,process_name,used_gpu_memory --format=csv,noheader)
if($LASTEXITCODE -ne 0) {{ throw 'GPU inventory failed' }}
if($busy.Count -gt 0) {{ throw 'Existing GPU compute process; no concurrent physics launch' }}
if(Test-Path '{REMOTE}/runs/gpu.lock') {{ throw 'Existing A20 physics lock; inspect current job' }}
New-Item -ItemType Directory -Force '{REMOTE}/runs' | Out-Null
$p=Start-Process -FilePath '{PYTHON}' -ArgumentList @({args}) -WorkingDirectory '{REMOTE}' -RedirectStandardOutput '{REMOTE}/runs/{job}.stdout' -RedirectStandardError '{REMOTE}/runs/{job}.stderr' -PassThru
$p.Id | Set-Content '{REMOTE}/runs/{job}.pid'
Write-Output ('STARTED '+$p.Id)
"""
    print(shell(script))


def run(stage,job,parents=None,iterations=None):
    """Keep SSH attached to the physics process; Windows may kill detached children.

    Use a long-lived terminal session for this command. Another connection can
    inspect the flushed stdout and receipts without terminating this session.
    """
    target,key=connection()
    if any(not (c.isalnum() or c in '-_') for c in job):
        raise ValueError('Unsafe job id')
    options=['-u','-m','a20.cli',stage,'--device','cuda','--job',job]
    if parents:
        options+=['--parents']+[str(int(x)) for x in parents]
    if iterations:
        options+=['--iterations']+[str(int(x)) for x in iterations]
    args=','.join("'"+x+"'" for x in options)
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
$busy=@(& nvidia-smi --query-compute-apps=pid,process_name,used_gpu_memory --format=csv,noheader)
if($LASTEXITCODE -ne 0) {{ throw 'GPU inventory failed' }}
if($busy.Count -gt 0) {{ throw 'Existing GPU compute process; no concurrent physics launch' }}
if(Test-Path '{REMOTE}/runs/gpu.lock') {{ throw 'Existing A20 physics lock; inspect current job' }}
New-Item -ItemType Directory -Force '{REMOTE}/runs' | Out-Null
& '{PYTHON}' @({args}) 1>'{REMOTE}/runs/{job}.stdout' 2>'{REMOTE}/runs/{job}.stderr'
$rc=$LASTEXITCODE
Get-Content '{REMOTE}/runs/{job}.stdout' -Tail 6
Get-Content '{REMOTE}/runs/{job}.stderr' -Tail 20
exit $rc
"""
    encoded=base64.b64encode(script.encode('utf-16le')).decode()
    subprocess.run(['ssh','-i',key,'-o','BatchMode=yes','-o','ConnectTimeout=8',
                    '-o','StrictHostKeyChecking=yes',target,
                    'powershell.exe -NoProfile -EncodedCommand '+encoded],check=True)


def status(job):
    if any(not (c.isalnum() or c in '-_') for c in job):
        raise ValueError('Unsafe job id')
    print(shell(f"""
$p=[int](Get-Content '{REMOTE}/runs/{job}.pid')
$live=Get-Process -Id $p -ErrorAction SilentlyContinue
if($live) {{ Write-Output ('RUNNING CPU='+$live.CPU+' RSS='+$live.WorkingSet64) }} else {{ Write-Output 'ENDED' }}
if(Test-Path '{REMOTE}/results/jobs/{job}/job_receipt.json') {{ Get-Content '{REMOTE}/results/jobs/{job}/job_receipt.json' -Raw }}
Get-Content '{REMOTE}/runs/{job}.stdout' -Tail 6 -ErrorAction SilentlyContinue
Get-Content '{REMOTE}/runs/{job}.stderr' -Tail 12 -ErrorAction SilentlyContinue
"""))


def pull():
    target,_=connection()
    registry=ROOT/'results/EXTERNAL_CPU_RECEIPTS.json'
    local_external=json.loads(registry.read_text()) if registry.exists() else []
    script=f"import zipfile,pathlib; r=pathlib.Path(r'{REMOTE}'); z=zipfile.ZipFile(r/'results_download.zip','w',zipfile.ZIP_DEFLATED); [z.write(p,p.relative_to(r).as_posix()) for p in (r/'results').rglob('*') if p.is_file()]; z.close(); print('ARCHIVED')"
    encoded=base64.b64encode(script.encode()).decode()
    print(shell(f"& '{PYTHON}' -c \"import base64; exec(base64.b64decode('{encoded}'))\""))
    with tempfile.TemporaryDirectory() as temp:
        dest=Path(temp)/'results.zip'
        copy(f'{target}:{REMOTE}/results_download.zip',dest)
        with zipfile.ZipFile(dest) as z:
            z.extractall(ROOT)
    remote_external=json.loads(registry.read_text()) if registry.exists() else []
    merged={}
    for row in remote_external+local_external:
        key=row['scope']
        if key not in merged or row['process_cpu_seconds']>merged[key]['process_cpu_seconds']:
            merged[key]=row
    registry.write_text(json.dumps(list(merged.values()),indent=2)+'\n')
    # A remote ledger cannot erase earlier local/failure receipts.
    ledger=[]
    for path in sorted((ROOT/'results/jobs').glob('*/job_receipt.json')):
        row=json.loads(path.read_text())
        result=path.parent/'result.json'
        if result.exists():
            row['result']=json.loads(result.read_text())
        ledger.append(row)
    (ROOT/'results/JOB_LEDGER.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in ledger))
    print('RESULTS_SAVED')


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('operation',choices=['deploy','start','run','status','pull'])
    p.add_argument('--stage',choices=['algebra','g0-real','replay','a1','a2','noise','timing','evaluate'])
    p.add_argument('--job')
    p.add_argument('--parents',type=int,nargs='*')
    p.add_argument('--iterations',type=int,nargs='*')
    a=p.parse_args()
    if a.operation=='deploy': deploy()
    elif a.operation=='start': start(a.stage,a.job,a.parents,a.iterations)
    elif a.operation=='run': run(a.stage,a.job,a.parents,a.iterations)
    elif a.operation=='status': status(a.job)
    else: pull()
