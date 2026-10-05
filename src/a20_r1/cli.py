"""Frozen R1 stage owner: all launches carry original and corrective budgets."""
from __future__ import annotations
import time
STARTED_WALL = time.perf_counter()
from pathlib import Path
import argparse
import json
import subprocess
import traceback

from a20.costs import BudgetExceeded, job_lock, plain, write_json
from .budget import R1Book, history, load_config


def rows_from(root):
    path = Path(root)/'results/a20_r1/anatomy/rows.jsonl'
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


def source_identity(root):
    stamp = Path(root)/'configs/SOURCE_COMMIT.txt'
    if stamp.exists():
        return stamp.read_text().strip()
    return subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()


def preflight(root, config):
    root = Path(root)
    old = json.loads((root/'results/BUDGET_FINAL.json').read_text())
    assert abs(old['charged_CPU_seconds']-config['historical_CPU_seconds']) < 1e-6
    assert abs(old['charged_GPU_occupation_seconds']-config['historical_GPU_seconds']) < 1e-6
    for name, expected in [('G0_REAL.json','PASS'), ('G0_LOCAL.json','PASS'),
                           ('G0_ALGEBRA.json','ALL ASSERTIONS PASSED')]:
        assert json.loads((root/'results'/name).read_text())['status'] == expected, name
    assert config['parents'] == [2001,2005,2003,2007,2013]
    assert config['replay_iterations'] == [0,17]
    assert config['qp_kkt_rtol'] == 1e-8 and config['retained_rank'] == 8
    assert config['max_updates'] == 18 and config['line_trials'] == 24
    assert config['no_full_fallback'] and not config['new_sha256_checks']
    for parent in config['parents']:
        for name in ('problem.npz','state_00.npz','state_17.npz'):
            assert (root/'data/runtime'/str(parent)/name).is_file()
    if (root/'.git').exists():
        subprocess.run(['git','diff','--quiet',config['source_freeze'],'--',
            'src/a20/backend.py','src/a20/opm.py','src/a20/material.py','vendor/a17',
            'configs/frozen.json','data/runtime','data/offline'], cwd=root, check=True)
    return {'status':'PASS','physical_primitives_unchanged':True,
            'original_G0_reused':True,'reference_regeneration':False,
            'source_freeze':config['source_freeze'],'new_SHA256_checks':0,
            'history_snapshot':'NOT_RUN_NO_OWN_ACCEPTED_TRAJECTORY'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['preflight','anatomy','closed-loop','report'])
    parser.add_argument('--root', type=Path, default=Path.cwd())
    parser.add_argument('--device', choices=['cpu','cuda'], default='cpu')
    parser.add_argument('--job', required=True)
    parser.add_argument('--lock-root', type=Path)
    args = parser.parse_args()
    if not args.job.startswith('r1-') or any(not (x.isalnum() or x in '-_') for x in args.job):
        raise SystemExit('R1 job IDs must start r1- and use safe characters')
    root = args.root.resolve()
    config = load_config(root)
    phase = 'phase2' if args.stage == 'closed-loop' else 'phase1'
    directory = root/'results/jobs'/args.job
    if directory.exists():
        raise SystemExit('Existing job ID: no replacement or uncharged retry')
    directory.mkdir(parents=True)
    book = R1Book(root,config,phase,directory/'cost.jsonl',device=args.device,
                  epilogue=args.stage == 'report')
    book.started_wall = STARTED_WALL
    book.metadata = {'job':args.job,'experiment_id':args.job,
                     'source_commit':source_identity(root),'source_freeze':config['source_freeze']}
    result, status = {'status':'NOT_RUN'}, 'FAILED'
    try:
        with job_lock(args.lock_root or root):
            book.check()
            if args.device == 'cuda':
                import torch
                torch.set_num_threads(1)
            write_json(directory/'manifest.json',{
                **book.metadata,'stage':args.stage,'device':args.device,'config':config,
                'budget_prior':book.prior,'dataset':'historically_exposed_feasibility'})
            if args.stage == 'preflight':
                result = preflight(root,config)
                write_json(root/'results/a20_r1/PREFLIGHT.json',result)
            elif args.stage == 'anatomy':
                if json.loads((root/'results/a20_r1/PREFLIGHT.json').read_text())['status'] != 'PASS':
                    raise RuntimeError('R1_PREFLIGHT_REQUIRED')
                from .anatomy import run_anatomy
                result = run_anatomy(root,config,book,args.device,args.job)
            elif args.stage == 'closed-loop':
                from .closed_loop import run_closed_loop
                result = run_closed_loop(root,config,book,args.device,args.job)
            else:
                from .report import write_report
                rows = rows_from(root)
                path=root/'results/a20_r1/closed_loop/rows.jsonl'
                closed=[json.loads(s) for s in path.read_text().splitlines() if s.strip()] if path.exists() else []
                result = write_report(root,rows,config,book=book,
                    closed_loop_rows=[r for r in closed if r.get('history_mode')!='OFF'] or None,
                    history_rows=closed or None)
                write_json(root/'GATE_DECISION.json',{'anatomy':result['anatomy'],
                    'closed_loop':result['closed_loop'],'history':result['history'],
                    'scientific_judgment':'PARENT_REVIEW_PENDING'})
            status = 'COMPLETE'
            if result.get('status') in ('STOPPED_PARTIAL','BUDGET_STOP','HOLD'):
                status = 'BUDGET_STOP' if 'Budget' in str(result) else 'PARTIAL'
            elif result.get('status') in ('FAILED','STOPPED','NOT_RUN_INPUT_CONFLICT'):
                status='FAILED'
    except BudgetExceeded as error:
        result = {'status':'HOLD','reason':str(error),'partial_rows_preserved':True}
        status = 'BUDGET_STOP'
    except BaseException as error:
        result = {'status':'FAILED','error':type(error).__name__+': '+str(error)}
        (directory/'failure.txt').write_text(traceback.format_exc())
        traceback.print_exc()
    finally:
        write_json(directory/'result.json',result)
        receipt = book.receipt() | {'job':args.job,'stage':args.stage,'status':status,
                                  'source_commit':book.metadata['source_commit']}
        write_json(directory/'job_receipt.json',receipt)
        with (root/'results/a20_r1/JOB_LEDGER.jsonl').open('a') as f:
            f.write(json.dumps(plain(receipt|{'result':result}),allow_nan=False)+'\n')
        if status != 'COMPLETE':
            with (root/'FAILURE_LEDGER.jsonl').open('a') as f:
                f.write(json.dumps(plain({'failure_kind':'stage','job':args.job,
                    'status':status,'result':result,'receipt':receipt}),allow_nan=False)+'\n')
        budget = history(root)
        write_json(root/'results/a20_r1/BUDGET_CURRENT.json',budget)
        print(json.dumps(plain({'job':args.job,'status':status,'stage_status':result.get('status'),
                  'model_rows_written':result.get('model_rows_written'),
                  'CPU':receipt['process_cpu_seconds'],'GPU':receipt['gpu_occupation_seconds']})),flush=True)
    return 0 if status == 'COMPLETE' else 2


if __name__ == '__main__':
    raise SystemExit(main())
