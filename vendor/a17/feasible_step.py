"""Physical Euclidean projection onto pointwise passive-material constraints.
C3 applies to the GN proposal before projection. The projection is nonexpansive
in the common physical metric, but its relative error is not certified by C3.
"""
import numpy as np
from scipy import linalg as la
from scipy.optimize import minimize, LinearConstraint

def project_step(tan,chi,s):
    q=tan.d//2; out=[]; infos=[]
    for base,x,bound in [(chi.real,s[:q],-.5),(chi.imag,s[q:],0.)]:
        lower=bound-base
        if tan.Q is None:
            z=np.maximum(x,lower*np.sqrt(tan.volume));infos.append(dict(success=True,iterations=0))
        elif np.min(tan.Q@x-lower)>=-1e-11:
            z=x.copy();infos.append(dict(success=True,iterations=0))
        else:
            opt=minimize(lambda z:.5*np.sum((z-x)**2),np.zeros(q),jac=lambda z:z-x,
                constraints=[LinearConstraint(tan.Q,lower,np.inf)],method='SLSQP',
                options=dict(ftol=1e-12,maxiter=200))
            z=opt.x;violation=float(max(0.,-np.min(tan.Q@z-lower)))
            if violation>1e-7:raise RuntimeError('feasible projection failed: '+str(opt.message))
            infos.append(dict(success=bool(opt.success),iterations=int(opt.nit),violation=violation,message=str(opt.message)))
        out.append(z)
    sp=np.concatenate(out)
    return sp,dict(blocks=infos,projection_distance=float(la.norm(sp-s)),proposal_norm=float(la.norm(s)),executed_direction_norm=float(la.norm(sp)),certificate_scope='C3 only unprojected proposal; exact convex projection would transfer an absolute bound, but this numeric projection is not KKT-certified',projection_optimality_certified=False,all_solver_success=bool(all(i['success'] for i in infos)))
