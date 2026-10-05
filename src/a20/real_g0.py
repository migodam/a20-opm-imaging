"""Paid original-state adapter integrity checks; not reconstruction results."""
from pathlib import Path
import json
import time
import traceback
import numpy as np
from scipy import linalg as la
from .backend import Adapter, BasisView, load_problem, pack, unpack
from .opm import SchurFeedback, Hierarchy, build_seeds, Projection, ReducedJacobian, orth
from .costs import write_json, plain, BudgetExceeded


def relative(a,b):
    return float(la.norm(np.asarray(a)-np.asarray(b))/max(la.norm(a),la.norm(b),1e-30))


def run_real_g0(root,config,book,device):
    root=Path(root)
    dest=root/'results/g0_real'
    dest.mkdir(parents=True,exist_ok=True)
    rows=[]
    for parent in (2001,2005):
        started=time.perf_counter()
        before=book.snapshot()
        row={'parent_object_id':parent,'iteration':0,'status':'FAIL','precision':'complex128/float64'}
        book.metadata.update(parent_object_id=parent,stage='G0_REAL')
        print('G0_REAL parent='+str(parent),flush=True)
        try:
            with book.scope('G0_physical_integrity'):
                p=load_problem(root/f'data/runtime/{parent}/problem.npz')
                with np.load(root/f'data/runtime/{parent}/state_00.npz',allow_pickle=False) as f:
                    x=f['chi'].copy()
                a=Adapter(p,device=device,book=book)
                state=a.full_state(x)
                rng=np.random.default_rng(np.random.SeedSequence([config['master_seed'],parent,7001]))
                d=rng.normal(size=a.p); d/=la.norm(d)
                dc=p.chart.expand(d)
                w=rng.normal(size=a.P*2*a.m); w/=la.norm(w)
                jd=a.full_tangent_action(x,state,d)
                adj=a.full_adjoint_action(x,state,w)
                checks={'full_real_J_adjoint':relative(float(w@jd),float(d@adj))}
                with book.span('original_native_tangent_equivalence',full_tangent_RHS=a.P, full_tangent_calls=1):
                    native=a.whiten(pack(state.jvp(dc)))
                with book.span('original_native_adjoint_equivalence',full_adjoint_RHS=a.P, full_adjoint_calls=1):
                    native_adj=p.chart.adjoint(state.vjp(unpack(a.whiten(w,True),a.P,a.m)))
                checks.update(original_J_equivalence=relative(jd,native),original_adjoint_equivalence=relative(adj,native_adj))
                v=rng.normal(size=(a.n,2))+1j*rng.normal(size=(a.n,2))
                c=rng.normal(size=(a.n,2))+1j*rng.normal(size=(a.n,2))
                y=rng.normal(size=(a.m,2))+1j*rng.normal(size=(a.m,2))
                for name,forward,backward in [('L',a.apply_L,a.apply_L_adjoint),('F',a.apply_F,a.apply_F_adjoint)]:
                    checks[name+'_adjoint']=relative(np.vdot(c,forward(x,v)),np.vdot(backward(x,c),v))
                checks['S_adjoint']=relative(np.vdot(y,a.apply_S(v)),np.vdot(a.apply_S_adjoint(y),v))
                bv=rng.normal(size=(a.P,a.n))+1j*rng.normal(size=(a.P,a.n))
                checks['B_real_adjoint']=relative(np.vdot(bv,a.apply_B(x,state,d)).real,d@a.apply_B_adjoint(x,state,bv))
                view=BasisView(a,x,state,a.residual(state))
                U=view.receiver(config['retained_rank'])
                schur=SchurFeedback(view,U,config)
                seeds=build_seeds(view,schur,config)
                Z,basis=Hierarchy(view,schur,seeds,config).at_degree(1)
                projection=Projection(a,x,Z,config)
                q=Z[:,U.shape[1]:]
                tq=schur.T(q)
                aq=q.conj().T@a.apply_L(x,tq)
                checks['Schur_operator_equivalence']=relative(aq,q.conj().T@(q-schur.F(q)))
                rhs=a.apply_B(x,state,d).T
                direct=projection.apply(rhs)
                eliminated=schur.R_U(rhs)+tq@la.solve(aq,q.conj().T@schur.K(rhs))
                if projection.kind!='galerkin':
                    raise ValueError('Original-state G0 Galerkin equivalence needs a safe Galerkin core; named fallback retained in logs')
                checks['Schur_Galerkin_resolvent_equivalence']=relative(direct,eliminated)
                checks['Schur_feedback_adjoint']=relative(np.vdot(c,schur.F(v)),np.vdot(schur.F_adjoint(c),v))
                steps=[1e-3,1e-4,1e-5,1e-6]
                full_fd=[]
                for h in steps:
                    plus=a.full_state(x+h*dc).field
                    minus=a.full_state(x-h*dc).field
                    full_fd.append({'h':h,'relative_error':relative(jd,a.whiten(pack((plus-minus)/(2*h))))})
                # Reset the core at the exact base material. All trials below
                # freeze this Z and W; they do not silently rebuild a hierarchy.
                projection=Projection(a,x,Z,config)
                reduced=a.reduced_state(x,projection)
                jm=ReducedJacobian(a,x,reduced,projection)
                tangent=jm.action(d)
                checks['reduced_J_real_adjoint']=relative(w@tangent,d@jm.pullback(w))
                b=a.forcing(x)
                coeff=projection.solve(Z.conj().T@b)
                residual=b-projection.LZ@coeff
                E=rng.normal(size=Z.shape)+1j*rng.normal(size=Z.shape)
                E-=Z@(Z.conj().T@E); E*=.3/la.norm(E)
                LE=a.apply_L(x,E)
                moving_current=E@coeff+Z@projection.solve(E.conj().T@residual-Z.conj().T@LE@coeff)
                moving=tangent+a.whiten(pack(a.apply_S(moving_current).T))
                reduced_fd=[]
                for h in steps:
                    rp=a.reduced_state(x+h*dc,projection.trial(x+h*dc)).field
                    rm=a.reduced_state(x-h*dc,projection.trial(x-h*dc)).field
                    reduced_fd.append({'h':h,'relative_error':relative(tangent,a.whiten(pack((rp-rm)/(2*h))))})
                h=1e-5
                Zp=orth(Z+h*E)[0]; Zm=orth(Z-h*E)[0]
                mp=a.reduced_state(x+h*dc,Projection(a,x+h*dc,Zp,config,allow_petrov=False)).field
                mm=a.reduced_state(x-h*dc,Projection(a,x-h*dc,Zm,config,allow_petrov=False)).field
                moving_fd=a.whiten(pack((mp-mm)/(2*h)))
                checks['moving_Galerkin_correct_extra_terms']=relative(moving,moving_fd)
                row['moving_Galerkin_omitted_term_relative_error']=relative(tangent,moving_fd)
                # A frozen-test Petrov QR contract is checked separately from
                # moving least squares, whose derivative was tested in G0_LOCAL.
                with book.span('G0_frozen_test_Petrov_QR'):
                    W=la.qr(projection.LZ,mode='economic')[0]
                petrov=Projection(a,x,Z,config,test=W,allow_petrov=False)
                pstate=a.reduced_state(x,petrov)
                ptangent=ReducedJacobian(a,x,pstate,petrov).action(d)
                pf=a.reduced_state(x+h*dc,petrov.trial(x+h*dc)).field
                mf=a.reduced_state(x-h*dc,petrov.trial(x-h*dc)).field
                checks['frozen_test_Petrov_FD']=relative(ptangent,a.whiten(pack((pf-mf)/(2*h))))
                row.update(checks=checks,full_FD=full_fd,frozen_reduced_FD=reduced_fd,
                           basis=basis,seed_provenance=seeds.records,source_count=a.P,
                           receiver_positions=len(p.receivers),complex_receiver_channels=a.m)
                # Stable central-difference platform requires two consecutive
                # tested steps. We retain all four errors, including truncation.
                stable=lambda series:any(series[i]['relative_error']<1e-5 and series[i+1]['relative_error']<1e-5 for i in range(len(series)-1))
                algebra=[v for k,v in checks.items() if 'FD' not in k and 'correct_extra_terms' not in k]
                ok=(max(algebra)<1e-9 and stable(full_fd) and stable(reduced_fd)
                    and checks['moving_Galerkin_correct_extra_terms']<1e-5 and checks['frozen_test_Petrov_FD']<1e-5)
            with book.scope('offline_G0_saved_chart_audit'):
                with book.span('saved_chart_expansion_check'):
                    with np.load(root/f'data/offline/{parent}/labels.npz',allow_pickle=False) as f:
                        gauge=relative(p.chart.expand(f['step_0']),f['physical_step_0'])
                    row['saved_step_physical_chart_relative_error']=gauge
                    ok=ok and gauge<1e-9
            row['status']='PASS' if ok else 'FAIL'
            row['native_DDA_counters']=a.model.counters.as_dict()
        except BudgetExceeded:
            row.update(status='HOLD',reason='Budget stop; original-state G0 incomplete')
            raise
        except Exception as exc:
            row.update(status='FAIL',error=type(exc).__name__+': '+str(exc),traceback=traceback.format_exc())
        finally:
            row.update(wall_seconds=time.perf_counter()-started,cost=book.delta(before))
            write_json(dest/f'{parent}.json',row)
            rows.append(plain(row))
    return {'status':'PASS' if len(rows)==2 and all(r['status']=='PASS' for r in rows) else 'FAIL',
            'scope':'two original historical states; not imaging fidelity or speed',
            'parents':[2001,2005],'rows':rows,'thresholds':{'adjoint_equivalence':1e-9,'FD_platform':1e-5}}
