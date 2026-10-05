"""Gated, real A1 trajectories with own accepted history and paid offline audits.

This driver neither changes the Maxwell solver nor imports snapshot steps as
history.  Online seed factories receive no reference, labels, or full Jacobian.
"""
from __future__ import annotations

import gc
import json
import time
from pathlib import Path

import numpy as np
from scipy import linalg as la

from a20.backend import load_problem
from a20.cli import append_jsonl, truth_metrics
from a20.costs import BudgetExceeded, plain, write_json
from a20.imaging import reconstruct
from a20.material import QPFailure, solve_quadratic
from a20.opm import FullJacobian
from a20.replay import _Reference, _evaluate_full_step
from .gates import evaluate_anatomy, evaluate_closed_loop, evaluate_history
from .seeds import AcceptedHistory, METHODS, build_model


VECTOR_KEYS = ('F_actions', 'F_adjoint_actions', 'L_actions', 'L_adjoint_actions',
               'full_forward_RHS', 'full_tangent_RHS', 'full_adjoint_RHS',
               'full_state_backward_residual_L_rhs', 'full_state_Goff_rhs')
GOOD_ENGINE_STATUSES = frozenset(('CAPPED', 'CONVERGED_FULL_KKT'))


def read_rows(path):
    path = Path(path)
    return [json.loads(s) for s in path.read_text(encoding='utf-8').splitlines()
            if s.strip()] if path.exists() else []


def subtract_cost(total, offline):
    out = {}
    for key in ('counts', 'exclusive_walls'):
        out[key] = {k: value-offline.get(key, {}).get(k, 0)
                    for k, value in total.get(key, {}).items()}
        if key == 'counts' and any(v < 0 for v in out[key].values()):
            raise ValueError('Negative exclusive online counter after offline subtraction')
    return out


def add_cost(target, value):
    for key in ('counts', 'exclusive_walls'):
        group = target.setdefault(key, {})
        for name, cost in value.get(key, {}).items():
            group[name] = group.get(name, 0)+cost


class OwnPolicy:
    """The immutable method/parent owner validates every supplied history token."""
    def __init__(self, parent, method, *, history_on=True):
        if method not in ('FIXED-DEEP', 'WIDE-M', 'CHEAP-TASK'):
            raise ValueError('Offline diagnostic policy cannot enter closed-loop imaging')
        self.parent, self.method, self.history_on = int(parent), method, bool(history_on)
        self.last_accepted_index = 0
        self.model = None

    def __call__(self, adapter, x, state, residual, previous, method, degree, config):
        if adapter.problem.parent_id != self.parent or method != self.method:
            raise ValueError('Closed-loop policy owner mismatch')
        if degree != METHODS[self.method]['degree']:
            raise ValueError('Closed-loop degree is frozen')
        if previous is not None:
            if not isinstance(previous, AcceptedHistory):
                raise ValueError('Own accepted history token required')
            previous.validated_step(self.parent, self.method, adapter.p)
            if previous.accepted_index <= self.last_accepted_index:
                raise ValueError('History token reused across accepted updates')
            self.last_accepted_index = previous.accepted_index
        physical_z = adapter.chart.project(x-adapter.problem.init)
        ell = config['prior']*physical_z
        self.model = build_model(adapter, x, state, residual, ell, config, self.method,
                                 previous=previous if self.history_on else None)
        return self.model


class OfflineOwnStateAudit:
    """A full reference is paid on this trajectory's current state, then discarded.

    The separate FullJacobian avoids warming the online verifier's matrix.  No
    metric/reference returned by this callback is available to the seed policy.
    """
    def __init__(self, directory, run_id, config, book):
        self.directory, self.run_id = Path(directory), run_id
        self.config, self.book = config, book
        self.total = {'counts': {}, 'exclusive_walls': {}}
        self.rows = []

    def __call__(self, *, adapter, x, state, residual, ell, lam, row, full):
        before = {'counts': dict(self.book.counts), 'exclusive_walls': dict(self.book.walls)}
        started = time.perf_counter()
        out = {'record_kind': 'offline_iteration', 'run_id': self.run_id,
               'parent_object_id': adapter.problem.parent_id,
               'method': row['method'], 'outer_iteration': row['outer_iteration'],
               'source': 'this method own current x; independently paid full constrained quadratic',
               'teacher_used_online': False, 'status': 'PENDING'}
        step = np.asarray(row['material_step_coefficients'], dtype=float)
        try:
            jac = FullJacobian(adapter, x, state)
            with self.book.scope('offline_iteration_reference'):
                if row['method'] == 'FULL_GN':
                    # The identical FULL_GN QP was already paid online. Reuse its
                    # actual step but pay its independent full metric audit.
                    reference_step = step.copy()
                    qp = row['QP']
                else:
                    reference_step, qp, _ = solve_quadratic(adapter.chart, x, residual,
                        jac, lam, ell, self.config, self.book)
                js = jac.action(reference_step)
                gradient0 = jac.pullback(residual)+ell
                energy = float(js@js+lam*(reference_step@reference_step))
                quadratic = float(.5*(residual+js)@(residual+js)+ell@reference_step+
                                  .5*lam*(reference_step@reference_step))
                reference = _Reference(reference_step, js, quadratic, energy, gradient0,
                    {'reference_status':'VERIFIED_OWN_STATE_CONSTRAINED_REFERENCE',
                     'reference_QP':qp})
                out.update(_evaluate_full_step(adapter, x, residual, jac, lam, ell,
                                                step, reference, self.config))
                out.update(status='OK', reference_QP=qp, full_directional_derivative=float(gradient0@step))
                target = self.directory/'offline_steps'/(self.run_id+'_'+str(row['outer_iteration'])+'.npz')
                target.parent.mkdir(exist_ok=True)
                np.savez_compressed(target, step=reference_step, x=x)
                out['reference_path'] = target.relative_to(self.directory).as_posix()
        except BudgetExceeded:
            out.update(status='MISSING_BUDGET', failure='Budget exhausted during offline own-state audit')
            raise
        except Exception as exc:
            out.update(status='MISSING_REFERENCE', failure=type(exc).__name__+': '+str(exc))
            if isinstance(exc, QPFailure):
                out['reference_QP'] = getattr(exc, 'result', {})
            append_jsonl(self.directory/'failures.jsonl',out)
        finally:
            costs = self.book.delta(before)
            add_cost(self.total,costs)
            out['cost'] = costs
            out['wall_seconds'] = time.perf_counter()-started
            append_jsonl(self.directory/'offline_iterations.jsonl',out)
            self.rows.append(plain(out))


def _one(root, directory, parent, method, config, book, device, job, *, history_on=True):
    experiment = f'{job}_{parent}_{method}_{"ON" if history_on else "OFF"}'
    book.metadata.update(parent_object_id=parent, method=method, experiment_id=experiment,
                         history_mode='ON' if history_on else 'OFF')
    before = {'counts':dict(book.counts),'exclusive_walls':dict(book.walls)}
    audit = OfflineOwnStateAudit(directory,experiment,config,book)
    factory = None if method=='FULL_GN' else OwnPolicy(parent,method,history_on=history_on)
    problem = load_problem(root/f'data/runtime/{parent}/problem.npz')
    append_jsonl(directory/'attempts.jsonl',{'run_id':experiment,'parent_object_id':parent,
        'method':method,'history_mode':'ON' if history_on else 'OFF','status':'STARTED'})
    started = time.perf_counter()
    adapter = None
    try:
        x, result, iterations, adapter = reconstruct(problem,config,book,device,
            method=method, degree=0 if method=='FULL_GN' else METHODS[method]['degree'],
            mode='A1', basis_factory=factory, offline_iteration_callback=audit,
            no_full_fallback=True, experiment_id=experiment,
            iteration_sink=lambda value: append_jsonl(directory/'iterations.jsonl',value))
        offline_before = {'counts':dict(book.counts),'exclusive_walls':dict(book.walls)}
        with book.scope('offline_final_image_diagnostic'):
            with book.span('r1_final_truth_metrics'):
                labels = truth_metrics(root,parent,x,config)
                with np.load(root/f'data/offline/{parent}/labels.npz',allow_pickle=False) as f:
                    truth=f['truth'].copy()
                denominator=max(float(la.norm(truth)),1e-300)
                trace=[{'iteration':0,'material_error':float(la.norm(problem.init-truth)/denominator),
                        'full_objective':iterations[0]['full_objective_before'] if iterations else result['final_full_objective'],
                        'source':'OFFLINE image diagnostic only'}]
                for item in iterations:
                    if not item['accepted']:continue
                    accepted=problem.init+problem.chart.expand(np.asarray(item['accepted_material_coefficients']))
                    trace.append({'iteration':item['outer_iteration']+1,
                        'material_error':float(la.norm(accepted-truth)/denominator),
                        'full_objective':item['full_objective_before']-item['actual_reduction'],
                        'degree':item['degree'],'rank':item['rank'],
                        'source':'OFFLINE image diagnostic only'})
        add_cost(audit.total,book.delta(offline_before))
        # The engine's offline receipt also includes the enclosing callback
        # span. Final truth diagnostics remain outside measured deployment.
        online = result['deployment_cost']
        counts = online['counts']
        result.update(record_kind='trajectory',run_id=experiment, method=method,
            engine_status=result['status'], status='OK' if result['status'] in GOOD_ENGINE_STATUSES else 'FAILED',
            QP_valid=all(v['QP']['kkt_relative']<=config['qp_kkt_rtol'] and
                         v['QP']['feasibility_violation']<=config['feasibility_tolerance'] for v in iterations)
                         and result['status'] in GOOD_ENGINE_STATUSES,
            fullfallback_used=counts.get('full_model_fallbacks',0)>0,
            history_mode='ON' if history_on else 'OFF',
            own_history_validated=bool(method!='FULL_GN' and history_on),
            allocation=None if method=='FULL_GN' else METHODS[method].copy(),
            material_error=labels['final_truth_error'], truth_metrics=labels,
            iteration_trace=trace,
            full_objective=result['final_full_objective'], full_KKT=result['final_KKT_residual'],
            deployment_cost=online,
            offline_cost={**audit.total,'scope':'own-state H audit and final truth; inclusive budget'},
            physical_vector_RHS=sum(counts.get(key,0) for key in VECTOR_KEYS),
            physical_vector_count_components={key:counts.get(key,0) for key in VECTOR_KEYS},
            deployment_LU_factorizations=counts.get('full_LU_factorizations',0),
            deployment_wall_seconds=result.get('wall_deployment',result['wall_total']),
            offline_H_diagnostic_available=sum(r['status']=='OK' for r in audit.rows),
            offline_H_diagnostic_missing=sum(r['status']!='OK' for r in audit.rows),
            exposure='historically_exposed_feasibility', no_full_fallback=True)
        target=directory/'final_materials'/(experiment+'.npz')
        target.parent.mkdir(exist_ok=True)
        np.savez_compressed(target,x=x)
        result['final_material_path']=target.relative_to(root).as_posix()
        if result['status']!='OK':append_jsonl(directory/'failures.jsonl',result)
        append_jsonl(directory/'rows.jsonl',result)
        return plain(result)
    except BaseException as exc:
        failure={'record_kind':'trajectory','run_id':experiment,'parent_object_id':parent,
            'method':method,'history_mode':'ON' if history_on else 'OFF',
            'status':'BUDGET_STOP' if isinstance(exc,BudgetExceeded) else 'FAILED',
            'failure':type(exc).__name__+': '+str(exc),'QP_valid':False,
            'cost':book.delta(before),'wall_seconds':time.perf_counter()-started,
            'partial_iterations_preserved':True}
        append_jsonl(directory/'failures.jsonl',failure)
        append_jsonl(directory/'rows.jsonl',failure)
        if isinstance(exc,BudgetExceeded):raise
        return failure
    finally:
        # Real cold trajectories never reuse another object's factorization,
        # selected basis or previous step; release dense buffers before next.
        del adapter, factory, audit
        gc.collect()
        if device=='cuda':
            import torch
            torch.cuda.empty_cache()


def run_closed_loop(root,config,book,device,job):
    root=Path(root)
    directory=root/'results/a20_r1/closed_loop'
    directory.mkdir(parents=True,exist_ok=True)
    anatomy=read_rows(root/'results/a20_r1/anatomy/rows.jsonl')
    gate=evaluate_anatomy(anatomy,config)
    selected=gate.get('selected_method')
    if not selected:
        result={'status':'NOT_RUN_GATE_CLOSED','anatomy_gate':gate,'NN':'NOT_RUN'}
        write_json(directory/'SUMMARY.json',result)
        return result
    if read_rows(directory/'attempts.jsonl'):
        raise ValueError('Closed-loop matrix already started; no silent retry/duplicate trajectory')
    write_json(directory/'manifest.json',{'source_freeze':config['source_freeze'],
        'selected_method':selected,'selection_gate':gate,'parents':config['phase2_parents'],
        'mode':'A1','main_run_cap':9,'conditional_history_run_cap':3,
        'history':'own accepted alpha*step, parent/method/index validated',
        'timing':'one cold trajectory each; rotating method order; no repeated timing campaign',
        'teacher':'own-state offline references, never supplied to seed factory',
        'full_model_rescue':False,'NN':'NOT_RUN'})
    rows=[]
    stopped=False
    methods=['FULL_GN','FIXED-DEEP',selected]
    try:
        for index,parent in enumerate(config['phase2_parents']):
            order=methods[index:]+methods[:index]
            for method in order:
                book.check()
                rows.append(_one(root,directory,parent,method,config,book,device,job))
        main=evaluate_closed_loop(rows,config,selected)
        # Either complete method with joint image/objective/KKT quality may
        # authorize the already registered ON/OFF history control. No extra
        # method/degree is introduced, and all three controls remain budgeted.
        eligible=main.get('quality_pass_all') or main.get('FIXED_quality_pass_all')
        if eligible:
            for parent in config['phase2_parents']:
                book.check()
                rows.append(_one(root,directory,parent,'FIXED-DEEP',config,book,device,job,
                                 history_on=False))
    except BudgetExceeded:
        stopped=True
        raise
    finally:
        main_rows=[r for r in rows if r.get('history_mode')!='OFF']
        result={'status':'STOPPED_PARTIAL' if stopped else 'COMPLETE',
            'selected_method':selected,'attempted_count':len(read_rows(directory/'attempts.jsonl')),
            'completed_rows':len(read_rows(directory/'rows.jsonl')),
            'closed_loop_gate':evaluate_closed_loop(main_rows,config,selected),
            'history_gate':evaluate_history(rows,config),'NN':'NOT_RUN'}
        write_json(directory/'SUMMARY.json',result)
    return result
