"""Small algebra and 3-D vector coupled-dipole checks, not a validation campaign.
Run: OPENBLAS_NUM_THREADS=1 python verification/verify_theory.py
Dependencies: numpy, scipy. All seeds are fixed; no training or GPU work.
"""
from pathlib import Path
import json
import numpy as np
from numpy.linalg import norm, solve, svd
from scipy.linalg import orth

RNG = np.random.default_rng(20261007)
OUT = Path(__file__).resolve().parent

def rel(a, b):
    return float(norm(a-b)/max(norm(a), norm(b), 1e-30))

def cm(shape):
    return (RNG.normal(size=shape)+1j*RNG.normal(size=shape))/np.sqrt(2)

def algebra_checks():
    results = {}
    n, p, m, q = 13, 7, 9, 6
    L = np.eye(n)+0.12*cm((n,n))
    B, S = cm((n,p)), cm((m,n))
    Q = orth(cm((n,q)))
    R = Q@solve(Q.conj().T@L@Q, Q.conj().T)
    J = S@solve(L,B); A = S@R@B
    Idef = B-L@R@B; Odef = S-S@R@L
    results['two_sided_defect_relative_error'] = rel(J-A, Odef@solve(L,Idef))
    results['RLR_relative_error'] = rel(R@L@R,R)
    h, v = cm((m,)), RNG.normal(size=p)
    dh = Odef.conj().T@h
    actual = abs(np.vdot(h,(J-A)@v))
    bound = norm(dh)*norm(solve(L,np.eye(n)),2)*norm(Idef@v)
    results['two_sided_defect_bound_ratio'] = float(actual/bound)

    eps = 1e-3
    M = np.diag([eps,1.,1.]); P = np.diag([1.,eps,1.]); O = np.diag([1.,1.,eps])
    results['same_information_distinct_mechanisms'] = {
        'alpha': np.linalg.norm(M,axis=0).tolist(),
        'beta': (np.linalg.norm(P@M,axis=0)/np.linalg.norm(M,axis=0)).tolist(),
        'gamma': (np.linalg.norm(O@P@M,axis=0)/np.linalg.norm(P@M,axis=0)).tolist(),
        'singular_values': svd(O@P@M,compute_uv=False).tolist(),
        'delta_M_1e-3_output_diagonal': np.diag(O@P@(1e-3*np.eye(3))).tolist(),
        'delta_O_1e-3_output_diagonal': np.diag((1e-3*np.eye(3))@P@M).tolist()}
    # Non-orthogonal coordinate gauges must carry transformed metrics.
    T = np.diag([100.,0.1,2.]); Mt=solve(T,M); Pt=solve(T,P@T); Ot=O@T
    results['gauge_same_product_error'] = rel(O@P@M,Ot@Pt@Mt)
    results['gauge_raw_injection_change'] = float(norm(Mt[:,0])/norm(M[:,0]))
    Gt = T.T@T
    results['gauge_metric_injection_error'] = float(abs(np.sqrt(Mt[:,0]@Gt@Mt[:,0])-norm(M[:,0])))

    J2=np.array([[1.,1.],[0.,eps]])
    j, K=J2[:,0], J2[:,1:]
    Pi=np.eye(2)-K@np.linalg.pinv(K)
    g=norm(Pi@j); witness=(Pi@j)/(g*g)
    noise=1e-3*RNG.normal(size=(2,100000))
    results['aliasing']={'column_norms':norm(J2,axis=0).tolist(), 'profile_sensitivity':float(g),
        'witness':witness.tolist(),'witness_attribution_error':rel(J2.T@witness,np.array([1.,0.])),
        'predicted_variance':float(1e-6/(g*g)), 'empirical_variance':float(np.var(witness@noise))}
    J1=np.array([[1.,1.]])
    Jother=np.array([[1.,-1.]])
    Js=np.vstack([J1,Jother]); Ks=Js[:,1:]
    results['frequency_shared_nuisance']={'single_profile_sensitivity':[0.,0.],
      'stack_profile_sensitivity':float(norm((np.eye(2)-Ks@np.linalg.pinv(Ks))@Js[:,0]))}

    # Exact finite-perturbation factor budget, not merely first order.
    Lq=np.eye(5)+0.1*RNG.normal(size=(5,5)); Pq=solve(Lq,np.eye(5))
    Mq=RNG.normal(size=(5,4)); Oq=RNG.normal(size=(6,5))
    h=RNG.normal(size=6); x=RNG.normal(size=4); x/=norm(x)
    dL=RNG.normal(size=(5,5)); dL*=0.03/norm(dL,2)
    dM=RNG.normal(size=(5,4)); dM*=0.02/norm(dM,2)
    dO=RNG.normal(size=(6,5)); dO*=0.04/norm(dO,2)
    z=Pq@Mq@x; w=Pq.T@Oq.T@h
    zbar=(norm(z)+norm(Pq,2)*norm(dM,2)*norm(x))/(1-norm(Pq,2)*norm(dL,2))
    bound=norm(w)*norm(dM,2)*norm(x)+(norm(w)*norm(dL,2)+norm(h)*norm(dO,2))*zbar
    measured=abs(h@((Oq+dO)@solve(Lq+dL,Mq+dM)-Oq@Pq@Mq)@x)
    results['factor_finite_perturbation_bound_ratio']=float(measured/bound)

    # Strongly nonlinear map with an exactly affine observable coordinate.
    F=lambda a,b: np.array([a,b+b**3])
    H=np.array([[1.,0.]])
    vals=[abs(float((H@F(a,b))[0])-a) for a,b in RNG.normal(size=(100,2))*3]
    results['common_dual_one_shot_max_error']=float(max(vals))
    # Orthogonal material correction need not be a data-null correction.
    F2=lambda a,b: np.array([a+b*b])
    results['nonlinear_prior_leak']={'protected_coordinate_change':0.,'first_order_leak':0.,
                                   'correction_norm':0.5,'actual_data_change':float(F2(1.,.5)[0]-F2(1.,0.)[0])}
    f=lambda x:x/(1-.4*x)
    truth=1.; shot=f(truth)
    results['one_shot_curvature_failure']={'truth':truth,'data':f(truth), 'J0':1., 'one_shot':shot,
        'absolute_error':abs(shot-truth),'final_forward_residual':abs(f(shot)-f(truth))}
    # A reduced null direction can be full-model bright.
    L=np.eye(2); B=np.eye(2); S=np.eye(2); Q=np.array([[1.],[0.]])
    A=S@Q@Q.T@B
    results['rom_weak_is_not_physics_weak']={'reduced_sensitivity':float(norm(A[:,1])),
                                         'full_sensitivity':float(norm((S@B)[:,1]))}
    # Check noncommuting intermediate Grams.
    M=np.array([[1.,.2],[0.,1.]])
    P=np.array([[1.,4.],[0.,1.]])
    GM=M.T@M; GT=(P@M).T@(P@M)
    results['intermediate_gram_commutator_norm']=float(norm(GM@GT-GT@GM))
    return results

def maxwell_checks():
    """Eight isotropic polarizable particles; 24 complex current components.
    Radiation-corrected Clausius-Mossotti polarizability, k=2*pi, exp(-iwt).
    This is a small coupled-dipole model, NOT a grid-converged continuum solver.
    """
    from itertools import product
    k=2*np.pi
    pos=np.array(list(product([-.09,.09],repeat=3)))
    N=len(pos); nc=3*N; volume=.08**3
    def dyad(r):
        R=norm(r); u=r/R
        return np.exp(1j*k*R)/(4*np.pi*R)*(
            (k*k+1j*k/R-1/(R*R))*np.eye(3)+
            (-k*k-3j*k/R+3/(R*R))*np.outer(u,u))
    G=np.zeros((nc,nc),complex)
    for i in range(N):
        for j in range(N):
            if i!=j:G[3*i:3*i+3,3*j:3*j+3]=dyad(pos[i]-pos[j])
    dirs=np.array([[1.,0.,0.],[0.,1.,0.],[0.,0.,1.]])
    pols=np.array([[0.,1.,0.],[0.,0.,1.],[1.,0.,0.]])
    Einc=np.column_stack([(np.exp(1j*k*(pos@d))[:,None]*pol).ravel() for d,pol in zip(dirs,pols)])
    # Receivers sample all three electric components; correlated redundancy is not a noise model.
    recdirs=np.array([[1.,.3,.4],[1.,-.3,.4],[1.,.3,-.4],[1.,-.3,-.4],[-.7,1.,.5],[-.7,-1.,-.5]])
    recdirs/=norm(recdirs,axis=1)[:,None]
    S=np.zeros((3*len(recdirs),nc),complex)
    for r,loc in enumerate(2.5*recdirs):
        for j in range(N): S[3*r:3*r+3,3*j:3*j+3]=dyad(loc-pos[j])
    def state(x):
        c=x+0.03j
        a0=3*volume*c/(c+3)
        da0=9*volume/(c+3)**2
        rad=k**3/(6*np.pi)
        alpha=a0/(1-1j*rad*a0)
        da=da0/(1-1j*rad*a0)**2
        X=np.repeat(alpha,3); L=np.eye(nc)-X[:,None]*G
        cur=solve(L,X[:,None]*Einc)
        E=Einc+G@cur
        Bs=[]
        for t in range(Einc.shape[1]):
            B=np.zeros((nc,N),complex)
            for j in range(N):B[3*j:3*j+3,j]=da[j]*E[3*j:3*j+3,t]
            Bs.append(B)
        y=(S@cur).T.ravel()
        J=np.vstack([S@solve(L,B) for B in Bs])
        return y,J,L,Bs
    x0=np.linspace(.8,1.4,N)
    y,J,L,Bs=state(x0)
    v=RNG.normal(size=N);v/=norm(v)
    h=1e-5
    fd=(state(x0+h*v)[0]-state(x0-h*v)[0])/(2*h)
    # Known-background shallow physical seeds. No truth or optimization iterates.
    seed=np.column_stack([Bs[0]@cm((N,3)),Bs[1]@cm((N,2)),S.conj().T@cm((S.shape[0],4))])
    seed=seed/np.maximum(norm(seed,axis=0),1e-30)
    F=np.eye(nc)-L
    Q=orth(np.column_stack([seed,F@seed]))
    R=Q@solve(Q.conj().T@L@Q,Q.conj().T)
    A=np.vstack([S@R@B for B in Bs])
    Odef=S-S@R@L
    JD=np.vstack([Odef@solve(L,B-L@R@B) for B in Bs])
    Jr=np.vstack([J.real,J.imag]); Ar=np.vstack([A.real,A.imag])
    U,ss,Vh=svd(Ar,full_matrices=False); r=4
    Vp=Vh[:r].T; Vn=Vh[r:].T
    D=(Vh[:r]@np.linalg.pinv(Ar))
    data=[]
    for amp in [.005,.02,.08,.32]:
        dx=amp*v; dy=state(x0+dx)[0]-y
        dr=np.r_[dy.real,dy.imag]
        ahat=D@dr; atrue=Vp.T@dx
        nonlinear=norm(dy-J@dx)
        err=norm(ahat-atrue)
        pred=norm(D,2)*(norm((Jr-Ar)@dx)+nonlinear)
        data.append({'amplitude':amp,'tangent_remainder':float(nonlinear),
                     'physics_coefficient_error':float(err),'one_shot_bound':float(pred),
                     'bound_ratio':float(err/pred)})
    return {'n_particles':N,'complex_current_dimension':nc,'complex_data_dimension':int(J.shape[0]),
            'opm_rank':int(Q.shape[1]),'derivative_relative_error':rel(fd,J@v),
            'two_sided_defect_relative_error':rel(J-A,JD),
            'reduced_J_relative_error':rel(J,A),
            'singular_values_reduced_real_J':ss.tolist(),
            'one_shot_tests':data,
            'warning':'Algebra/derivative sanity checks only; not evidence that project imaging Gates A-C pass.'}

def main():
    result={'seed':20261007,'algebra':algebra_checks(),'maxwell_tiny':maxwell_checks()}
    a=result['algebra'];m=result['maxwell_tiny']
    assert a['two_sided_defect_relative_error']<1e-12
    assert a['gauge_same_product_error']<1e-12
    assert a['factor_finite_perturbation_bound_ratio']<=1+1e-12
    assert a['two_sided_defect_bound_ratio']<=1+1e-12
    assert m['derivative_relative_error']<1e-6
    assert m['two_sided_defect_relative_error']<1e-10
    assert all(x['bound_ratio']<=1+1e-9 for x in m['one_shot_tests'])
    (OUT/'results.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))

if __name__=='__main__': main()
