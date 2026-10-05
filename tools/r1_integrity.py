"""Retain every integrity attempt, including imports and failed assertions."""
from pathlib import Path
import time
import json
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'results/a20_r1/tests'
DEST.mkdir(parents=True,exist_ok=True)
attempt=len(list(DEST.glob('attempt_*.json')))+1
stem='attempt_'+str(attempt)
started=time.perf_counter()
before=0.  # Include controller imports before the first executable statement.
try:
    import resource
    child_before=resource.getrusage(resource.RUSAGE_CHILDREN)
except ImportError:
    child_before=None
with (DEST/(stem+'.log')).open('w') as output:
    command=[sys.executable,'-B','-m','unittest','discover','-s','tests','-p','test_*.py','-v']
    run=subprocess.run(command,cwd=ROOT,stdout=output,stderr=subprocess.STDOUT)
from a20_r1.budget import register_external
cpu=time.process_time()-before
if child_before is not None:
    child_after=resource.getrusage(resource.RUSAGE_CHILDREN)
    cpu+=child_after.ru_utime+child_after.ru_stime-child_before.ru_utime-child_before.ru_stime
receipt={'scope':'R1 complete integrity '+stem,'status':'PASS' if run.returncode==0 else 'FAIL',
    'returncode':run.returncode,'wall_seconds':time.perf_counter()-started,
    'process_cpu_seconds':cpu,'measurement':'controller + child CPU, imports and failures included',
    'GPU_seconds':0,'phase':'phase1','command':command,'real_5184_current_physics':False,
    'log':(DEST/(stem+'.log')).relative_to(ROOT).as_posix()}
(DEST/(stem+'.json')).write_text(json.dumps(receipt,indent=2)+'\n')
register_external(ROOT,receipt['scope'],cpu,receipt=receipt['log'].replace('.log','.json'))
print(json.dumps(receipt),flush=True)
raise SystemExit(run.returncode)
