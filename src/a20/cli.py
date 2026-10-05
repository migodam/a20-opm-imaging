"""Bounded, resumable jobs. No scheduler, teacher service, or hash checker."""
from __future__ import annotations
import time
STARTED_WALL = time.perf_counter()
import argparse
import csv
import importlib.util
import json
from pathlib import Path
import subprocess
import traceback
from .costs import CostBook, BudgetExceeded, job_lock, budget_history, plain, write_json


def append_jsonl(path, row):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as f:
        f.write(json.dumps(plain(row), allow_nan=False)+'\n')


def source_commit(root):
    stamp = root/'configs/SOURCE_COMMIT.txt'
    if stamp.exists():
        return stamp.read_text(encoding='utf-8').strip()
    return subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()


def metadata(root, args, config):
    import platform
    import numpy as np
    import scipy
    result = {'experiment_id': args.job, 'source_commit': source_commit(root),
        'backend_declared_historical_commit': 'e17f9de3469964c8f4cd1b1c967d2e2f14b3d277',
        'backend_origin': 'preserved A17 EXCHANGE_R1 vendor A9 DenseDDA; parent source is not a Git checkout',
        'precision': config['precision'], 'dataset_exposure': config['dataset_exposure'],
        'python': platform.python_version(), 'numpy': np.__version__, 'scipy': scipy.__version__,
        'device': args.device, 'threads': 1, 'stage': args.stage,
        'frozen_config': config,
        'selected_parents': args.parents, 'selected_iterations': args.iterations,
        'commands': ['PYTHONPATH=src python -m a20.cli '+args.stage+' --device '+args.device+' --job '+args.job],
        'new_SHA256_checks': 0, 'NN_training': False, 'solver_acceleration': False}
    if args.device=='cuda':
        import torch
        result.update(torch=torch.__version__, cuda=torch.version.cuda,
                      gpu=torch.cuda.get_device_name(0), gpu_memory_bytes=torch.cuda.get_device_properties(0).total_memory)
    return result


def read_rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line.strip()] if Path(path).exists() else []


def truth_metrics(root, parent, x, config):
    # Explicit evaluator capability, invoked only after an online run.
    import numpy as np
    from scipy import linalg as la
    with np.load(root/f'data/offline/{parent}/labels.npz', allow_pickle=False) as f:
        truth = f['truth'].copy()
    with np.load(root/f'data/runtime/{parent}/problem.npz', allow_pickle=False) as f:
        volume = float(f['volume'])
    diff = x-truth
    total = float(la.norm(diff)/max(la.norm(truth), 1e-300))
    real = float(la.norm(diff.real)/max(la.norm(truth.real), 1e-300))
    imag_den = max(la.norm(truth.imag), config['imaginary_denominator_floor_fraction']*la.norm(truth), 1e-300)
    return {'final_truth_error': total, 'final_real_error': real,
        'final_imag_error': float(la.norm(diff.imag)/imag_den),
        'final_material_absolute_error': float(np.sqrt(volume)*la.norm(diff)),
        'imaginary_denominator': float(imag_den), 'imaginary_absolute_error': float(np.sqrt(volume)*la.norm(diff.imag)),
        'absolute_error_metric': 'physical L2, sqrt(volume)*Euclidean contrast norm',
        'imaginary_denominator_floored': bool(la.norm(truth.imag)<imag_den)}


def eligibility(root, config):
    import numpy as np
    rows = read_rows(root/'results/replay/actions.jsonl')
    if not rows:
        rows = read_rows(root/'results/replay/replay.jsonl')
    # Accept both documented worker schema names; never infer missing rows.
    answer = {'status': 'HOLD', 'eligible': [], 'degrees': {}, 'expected_states': 12}
    for degree in config['live_degrees']:
        subset = [r for r in rows if r.get('method') in ('mixed', 'OPM', 'OPM_MIXED', 'mixed_default')
                  and r.get('degree')==degree]
        good = [r for r in subset if r.get('status') in ('OK', 'PASS', 'COMPLETE')
                and r.get('relative_H_step_error') is not None]
        vals = [r['relative_H_step_error'] for r in good]
        if len(good)==12:
            median = float(np.median(vals))
            ok = median<=config['replay_median_H_error_gate']
            decision = 'PASS' if ok else 'FAIL'
            if ok:
                answer['eligible'].append(degree)
        else:
            median, decision = None, 'HOLD'
        answer['degrees'][str(degree)] = {'status': decision, 'valid_states': len(good),
            'median_relative_H_step_error': median, 'worst_relative_H_step_error': float(max(vals)) if vals else None}
    if all(r['status']!='HOLD' for r in answer['degrees'].values()):
        answer['status'] = 'PASS' if answer['eligible'] else 'FAIL'
    elif answer['eligible']:
        answer['status'] = 'PARTIAL_WITH_ELIGIBLE'
    write_json(root/'results/REPRESENTATION_GATE.json', answer)
    return answer


def quality_gate(root, config, mode='A1'):
    import numpy as np
    rows = read_rows(root/f'results/{mode}/runs.jsonl')
    refs = {r['parent_object_id']: r for r in rows if r['method']=='FULL_GN' and r.get('cache_mode','cold')=='cold'}
    if mode=='A2':
        refs = {r['parent_object_id']: r for r in read_rows(root/'results/A1/runs.jsonl')
                if r['method']=='FULL_GN' and r.get('cache_mode','cold')=='cold'}
    methods = sorted({r['method'] for r in rows if r['method']!='FULL_GN'})
    decisions = {}
    for method in methods:
        sub = [r for r in rows if r['method']==method and r.get('cache_mode','cold')=='cold']
        comparison, failures = [], []
        for r in sub:
            ref = refs.get(r['parent_object_id'])
            if ref is None:
                continue
            if r['status'] not in ('CAPPED','CONVERGED_FULL_KKT') or ref['status'] not in ('CAPPED','CONVERGED_FULL_KKT'):
                failures.append(r['parent_object_id'])
            error, reference = r['final_truth_error'], ref['final_truth_error']
            comparison.append({'parent': r['parent_object_id'],
                'excess': (error-reference)/max(reference,config['reference_error_floor']),
                'absolute_error_difference': error-reference, 'wall_ratio': r['wall_total']/ref['wall_total'],
                'rank_fraction': r['rank']/r['n_current']})
        if len(comparison)!=6:
            status='HOLD'
        else:
            status='PASS' if (not failures and np.median([r['excess'] for r in comparison])<=config['final_median_excess_gate']
                and max(r['excess'] for r in comparison)<=config['final_worst_excess_gate']
                and max(r['rank_fraction'] for r in comparison)<=config['rank_fraction_target']) else 'FAIL'
        decisions[method] = {'status': status, 'pairs': comparison, 'failed_parents': failures,
            'median_wall_ratio': float(np.median([r['wall_ratio'] for r in comparison])) if comparison else None}
    write_json(root/f'results/{mode}/QUALITY_GATE.json', decisions)
    return decisions


def run_images(root, config, book, args):
    import numpy as np
    from .backend import load_problem
    from .imaging import reconstruct
    gate = eligibility(root, config)
    if not gate['eligible']:
        return {'status':'NOT_RUN', 'reason':'No registered degree 0-3 passed complete replay', 'replay_gate':gate}
    algebra = root/'results/G0_REAL.json'
    if not algebra.exists() or json.loads(algebra.read_text())['status']!='PASS':
        return {'status':'NOT_RUN', 'reason':'Real G0 prerequisite not passed'}
    if args.stage=='a1':
        degree_for_controls = min(gate['eligible'])
        jobs = [('FULL_GN',0)]+[(f'OPM_d{d}',d) for d in gate['eligible']]+[('SOM',degree_for_controls),('KRYLOV',degree_for_controls)]
        mode='A1'
    else:
        mode='A2'
        quality = quality_gate(root,config,'A1')
        passing = [(name,d['median_wall_ratio']) for name,d in quality.items() if name.startswith('OPM') and d['status']=='PASS']
        if not passing:
            return {'status':'NOT_RUN','reason':'No A1 OPM quality survivor'}
        chosen = min(passing,key=lambda x:(x[1],x[0]))[0]
        jobs=[(chosen,int(chosen.split('_d')[1]))]
    dest=root/f'results/{mode}'
    dest.mkdir(parents=True,exist_ok=True)
    done = {(r['parent_object_id'],r['method']) for r in read_rows(dest/'runs.jsonl')}
    for parent in config['parents']:
        for method,degree in jobs:
            if (parent,method) in done:
                continue
            problem=load_problem(root/f'data/runtime/{parent}/problem.npz')
            book.metadata.update(parent_object_id=parent, method=method, mode=mode)
            print(f'{mode} parent={parent} method={method} degree={degree}',flush=True)
            with book.scope('online_'+mode):
                x,row,iterations,_=reconstruct(problem,config,book,args.device,method=method,degree=degree,mode=mode,
                    iteration_sink=lambda r:append_jsonl(dest/'iterations.jsonl',r), experiment_id=args.job)
            with book.scope('offline_evaluation'):
                with book.span('offline_truth_metrics'):
                    row.update(truth_metrics(root,parent,x,config))
            row.update(cache_mode='cold', backend_commit=source_commit(root))
            append_jsonl(dest/'runs.jsonl',row)
            np.savez_compressed(dest/f'{parent}_{method}_reconstruction.npz',chi=x)
    return {'status':'COMPLETE','quality_gate':quality_gate(root,config,mode)}


def run_optional(root, config, book, args):
    from .robustness import run_noise, run_warm_timing
    a1=quality_gate(root,config,'A1')
    candidates=[(name,int(name.split('_d')[1]),'A1',decision['median_wall_ratio'])
                for name,decision in a1.items() if name.startswith('OPM_d') and decision['status']=='PASS']
    # A2 must have passed A1, and must itself have complete quality evidence.
    if candidates:
        a2=quality_gate(root,config,'A2')
        candidates += [(name,int(name.split('_d')[1]),'A2',decision['median_wall_ratio'])
                       for name,decision in a2.items() if name.startswith('OPM_d') and decision['status']=='PASS']
    if not candidates:
        return {'status':'NOT_RUN','reason':'No complete OPM nonlinear quality survivor'}
    method,degree,mode,_=min(candidates,key=lambda r:(r[3],r[1],r[2]))
    if args.stage=='timing':
        # Warm repeats cannot silently enlarge the approved A1 42-run matrix.
        base=len(read_rows(root/'results/A1/runs.jsonl'))
        additional_a1=12 if mode=='A1' else 6
        if base+additional_a1>42:
            return {'status':'NOT_RUN','reason':'A1 42-run cap leaves insufficient complete warm pairs; G2 remains HOLD',
                    'A1_runs':base,'required_additional_A1':additional_a1}
        return run_warm_timing(root,config,book,args.device,args.job,method,degree,mode)
    return run_noise(root,config,book,args.device,args.job,method,degree,mode)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage',choices=['algebra','g0-real','replay','a1','a2','noise','timing','evaluate'])
    parser.add_argument('--root',type=Path,default=Path.cwd())
    parser.add_argument('--device',choices=['cpu','cuda'],default='cpu')
    parser.add_argument('--job',required=True)
    parser.add_argument('--parents',type=int,nargs='*')
    parser.add_argument('--iterations',type=int,nargs='*')
    args=parser.parse_args()
    if not args.job or any(not (c.isalnum() or c in '-_') for c in args.job):
        raise SystemExit('Job IDs may contain only letters, numbers, dash and underscore')
    root=args.root.resolve()
    config=json.loads((root/'configs/frozen.json').read_text(encoding='utf-8'))
    prior_cpu,prior_gpu=budget_history(root)
    external=root/'results/EXTERNAL_CPU_RECEIPTS.json'
    if external.exists():
        prior_cpu+=sum(r['process_cpu_seconds'] for r in json.loads(external.read_text()))
    jobdir=root/'results/jobs'/args.job
    if jobdir.exists():
        raise SystemExit('Job ID exists; retries require a new ID and retain failed receipt')
    jobdir.mkdir(parents=True)
    book=CostBook(jobdir/'cost.jsonl',device=args.device,prior_cpu=prior_cpu,prior_gpu=prior_gpu,
        cpu_limit=config['budget_cpu_seconds'],gpu_limit=config['budget_gpu_wall_seconds'],
        cpu_reserve=config['cpu_epilogue_reserve_seconds'],gpu_reserve=config['gpu_preoperation_reserve_seconds'])
    book.started_cpu=0.0  # include Python/library imports in this process
    book.started_wall=STARTED_WALL
    result,status={'status':'NOT_RUN'},'FAILED'
    try:
        with job_lock(root):
            if args.device=='cuda':
                import torch
                torch.set_num_threads(1)
            manifest=metadata(root,args,config)
            write_json(jobdir/'manifest.json',manifest)
            book.metadata={'job':args.job,'source_commit':manifest['source_commit']}
            book.check()
            if args.stage=='algebra':
                spec=importlib.util.spec_from_file_location('a20_theory_check',root/'protocol/experiments/check_theory.py')
                module=importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                with book.scope('algebra_audit'):
                    with book.span('supplied_algebra_checks'):
                        result=module.run()
                write_json(root/'results/G0_ALGEBRA.json',result)
            elif args.stage in ('g0-real','replay'):
                if args.stage=='g0-real':
                    from .real_g0 import run_real_g0
                    local = root/'results/G0_LOCAL.json'
                    algebra = root/'results/G0_ALGEBRA.json'
                    if not local.exists() or json.loads(local.read_text())['status']!='PASS':
                        raise RuntimeError('G0_LOCAL_NOT_PASSED')
                    if not algebra.exists() or json.loads(algebra.read_text())['status']!='ALL ASSERTIONS PASSED':
                        raise RuntimeError('SUPPLIED_ALGEBRA_NOT_PASSED')
                    result=run_real_g0(root,config,book,args.device)
                    write_json(root/'results/G0_REAL.json',result)
                else:
                    from .replay import run_replay
                    passed=root/'results/G0_REAL.json'
                    if not passed.exists() or json.loads(passed.read_text())['status']!='PASS':
                        raise RuntimeError('G0_REAL_NOT_PASSED; imaging/replay is gate-closed')
                    result=run_replay(root,config,book,args.device,parents=args.parents,iterations=args.iterations)
                    result['representation_gate']=eligibility(root,config)
            elif args.stage in ('a1','a2'):
                result=run_images(root,config,book,args)
            elif args.stage in ('noise','timing'):
                result=run_optional(root,config,book,args)
            else:
                result={'replay':eligibility(root,config),'A1':quality_gate(root,config,'A1'),'A2':quality_gate(root,config,'A2')}
            status='COMPLETE'
    except BudgetExceeded as exc:
        result={'status':'HOLD','reason':str(exc),'missing':'Unfinished actions retained; no borrowing or uncharged restart'}
        status='BUDGET_STOP'
    except BaseException as exc:
        result={'status':'FAILED','error':type(exc).__name__+': '+str(exc)}
        (jobdir/'failure.txt').write_text(traceback.format_exc(),encoding='utf-8')
        traceback.print_exc()
    finally:
        write_json(jobdir/'result.json',result)
        receipt=book.receipt()
        receipt.update(status=status,job=args.job,stage=args.stage,prior_cpu_seconds=prior_cpu,prior_gpu_seconds=prior_gpu,
                       CPU_limit=config['budget_cpu_seconds'],GPU_limit=config['budget_gpu_wall_seconds'])
        write_json(jobdir/'job_receipt.json',receipt)
        append_jsonl(root/'results/JOB_LEDGER.jsonl',{**receipt,'result':result})
        brief = result if len(json.dumps(plain(result)))<3000 else {'status':result.get('status'),
            'keys':list(result),'full_result':'results/jobs/'+args.job+'/result.json'}
        print(json.dumps(plain({'job':args.job,'status':status,'result':brief,'CPU':receipt['process_cpu_seconds'],
                               'GPU':receipt['gpu_occupation_seconds']}),ensure_ascii=False),flush=True)
    return 0 if status=='COMPLETE' else 2


if __name__=='__main__':
    raise SystemExit(main())
