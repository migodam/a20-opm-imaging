"""Paid frozen-backend convention checks; these never solve another QP."""
from __future__ import annotations

import numpy as np
from scipy import linalg as la
from a20.backend import pack, unpack
from .diagnostics import ConsistencyFailure


def _relative(a, b):
    return float(la.norm(np.asarray(a)-np.asarray(b))/max(float(la.norm(a)),float(la.norm(b)),np.finfo(float).tiny))


def _dot_error(lhs, rhs, scale):
    return float(abs(lhs-rhs)/max(abs(lhs),abs(rhs),float(scale),np.finfo(float).tiny))


def validate_case(case, config, book):
    """Independent action/adjoint tests at registered first/middle/last IDs."""
    a, x, state = case['adapter'], case['x'], case['state']
    JF, r, sF = case['JF'], case['r'], case['sF']
    X, Y = case['X'], case['Y']
    fp, fd = case['primal_forcing'], case['dual_forcing']
    seed = [20261006, int(a.problem.parent_id), 17, 2191]
    rng = np.random.default_rng(np.random.SeedSequence(seed))
    tol = config['backend_consistency_rtol']
    checks = {}
    with book.span('a21_real_backend_validation'):
        source_values = rng.normal(size=(a.P,a.m,2)) + 1j*rng.normal(size=(a.P,a.m,2))
        checks['pack_unpack'] = _relative(unpack(pack(source_values),a.P,a.m),source_values)
        perm = np.array([5,0,3,1,4,2])
        checks['source_permutation'] = _relative(pack(source_values[perm]),pack(source_values).reshape(a.P,2*a.m,2)[perm].reshape(-1,2))
        u, v = rng.normal(size=(2,a.P*2*a.m))
        checks['whitening_transpose'] = _dot_error(u@a.whiten(v),a.whiten(u,adjoint=True)@v,la.norm(u)*la.norm(a.whiten(v)))
        d = rng.normal(size=a.p)
        c = rng.normal(size=a.chart.n)+1j*rng.normal(size=a.chart.n)
        expanded, pulled = a.chart.expand(d), a.chart.adjoint(c)
        checks['real_material_chart_adjoint'] = _dot_error(np.real(np.vdot(expanded,c)),d@pulled,la.norm(expanded)*la.norm(c))
        checks['volume_material_metric'] = abs(a.problem.volume*np.vdot(expanded,expanded).real-d@d)/max(float(d@d),np.finfo(float).tiny)
        currents = rng.normal(size=(a.P,a.n))+1j*rng.normal(size=(a.P,a.n))
        bd, bt = a.apply_B(x,state,d), a.apply_B_adjoint(x,state,currents)
        checks['B_real_adjoint'] = _dot_error(np.real(np.vdot(bd,currents)),d@bt,la.norm(bd)*la.norm(currents))
        current = rng.normal(size=a.n)+1j*rng.normal(size=a.n)
        receiver = rng.normal(size=a.m)+1j*rng.normal(size=a.m)
        sv, sh = a.apply_S(current), a.apply_S_adjoint(receiver)
        checks['S_conjugate_adjoint'] = _dot_error(np.real(np.vdot(sv,receiver)),np.real(np.vdot(current,sh)),la.norm(sv)*la.norm(receiver))
        lv, lh = a.apply_L(x,current), a.apply_L_adjoint(x,current[::-1])
        checks['L_conjugate_adjoint'] = _dot_error(np.vdot(lv,current[::-1]),np.vdot(current,lh),la.norm(lv)*la.norm(current))
        fv, fh = a.apply_F(x,current), a.apply_F_adjoint(x,current[::-1])
        checks['F_conjugate_adjoint'] = _dot_error(np.vdot(fv,current[::-1]),np.vdot(current,fh),la.norm(fv)*la.norm(current))
        full_dots, action_matches, adjoint_matches = [], [], []
        for _ in range(2):
            direction = rng.normal(size=a.p)
            direction /= la.norm(direction)
            cotangent = rng.normal(size=JF.shape[0])
            cotangent /= la.norm(cotangent)
            action = a.full_tangent_action(x,state,direction)
            adjoint = a.full_adjoint_action(x,state,cotangent)
            full_dots.append(_dot_error(cotangent@action,direction@adjoint,la.norm(cotangent)*la.norm(action)+la.norm(direction)*la.norm(adjoint)))
            action_matches.append(_relative(action,JF@direction))
            adjoint_matches.append(_relative(adjoint,JF.T@cotangent))
        checks['full_real_dot'] = max(full_dots)
        checks['full_J_action_assembly'] = max(action_matches)
        checks['full_J_adjoint_assembly'] = max(adjoint_matches)
        LX, LHY = a.apply_L(x,X), a.apply_L_adjoint(x,Y)
        checks['primal_oracle_solve_residual'] = _relative(LX,fp)
        checks['dual_oracle_solve_residual'] = _relative(LHY,fd)
        measured = a.whiten(pack(a.apply_S(X).T))
        pulled_oracle = a.apply_B_adjoint(x,state,Y.T)
        checks['primal_oracle_endpoint'] = _relative(measured,JF@sF)
        checks['dual_oracle_endpoint'] = _relative(pulled_oracle,JF.T@(r+JF@sF))
        baseline = case.get('baseline')
        U = case.get('U')
        LZ = case.get('baseline_LZ')
        if baseline is not None and U is not None and LZ is not None:
            kU=U.shape[1]
            V=baseline[:,kU:]
            LU,LV=LZ[:,:kU],LZ[:,kU:]
            AU=U.conj().T@LU
            factorU=la.lu_factor(AU)
            T_V=V-U@la.lu_solve(factorU,U.conj().T@LV)
            coarse=U@la.lu_solve(factorU,U.conj().T@currents.T)
            K_rhs=currents.T-LU@la.lu_solve(factorU,U.conj().T@currents.T)
            schur_core=V.conj().T@(LV-LU@la.lu_solve(factorU,U.conj().T@LV))
            schur=coarse+T_V@la.solve(schur_core,V.conj().T@K_rhs)
            projected=baseline@la.solve(baseline.conj().T@LZ,baseline.conj().T@currents.T)
            checks['retained_Schur_full_core_identity']=_relative(schur,projected)
        else:
            raise ConsistencyFailure('REAL_BACKEND_SCHUR_CHECK_REQUIRES_BASELINE_AND_IMAGES')
    failures = {k:value for k,value in checks.items() if value>tol}
    oracle_failures = {k:checks[k] for k in ('primal_oracle_solve_residual','dual_oracle_solve_residual') if checks[k]>config['oracle_backward_rtol']}
    if failures or oracle_failures:
        exc=ConsistencyFailure('REAL_BACKEND_CONVENTION_OR_ADJOINT_FAILURE')
        exc.details={'checks':checks,'failures':failures,'oracle_failures':oracle_failures,'seed':seed}
        raise exc
    return {'status':'PASS','parent_id':int(a.problem.parent_id),'iteration':17,
            'seed':seed,'checks':checks,'backend_consistency_rtol':tol,
            'full_oracle_backward_rtol':config['oracle_backward_rtol'],
            'material_coordinates':a.p,'sources':a.P,'complex_receivers_per_source':a.m,
            'real_measurements':JF.shape[0],'physical_actions_charged':True,
            'source_layout':'source-major Re128 then Im128',
            'no_additional_QP':True}
