"""A9 experiment contracts. All probe coordinates are real physical L2 coordinates."""
import json, time, hashlib, platform, sys
from pathlib import Path
import numpy as np
from scipy.linalg import svd, block_diag
from scipy.optimize import brentq
from scipy.sparse.linalg import LinearOperator, cg

def dump(p,x):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    def conv(a):
        if isinstance(a,np.ndarray):return a.tolist()
        if isinstance(a,np.generic):return a.item()
        if isinstance(a,complex):return [a.real,a.imag]
        raise TypeError(type(a).__name__)
    t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(x,indent=2,default=conv));t.replace(p)

def provenance(out,config):
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    dump(out/'config.json',config)
    dump(out/'environment.json',dict(python=sys.version,executable=sys.executable,platform=platform.platform(),host=platform.node(),numpy=np.__version__,created_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())))
    sources={}
    for p in Path(__file__).parent.glob('*.py'):
        raw=p.read_bytes();sources[p.name]=hashlib.sha256(raw).hexdigest();dest=out/'source_snapshot'/p.name;dest.parent.mkdir(exist_ok=True);dest.write_bytes(raw)
    dump(out/'source_manifest.json',sources)

def fibonacci(n):
    z=1-2*(np.arange(n)+.5)/n;a=np.arange(n)*np.pi*(3-np.sqrt(5))
    return np.c_[np.sqrt(1-z*z)*np.cos(a),np.sqrt(1-z*z)*np.sin(a),z]

def acquisition(tx=6,rx=24,rotation=0.):
    dirs=fibonacci(tx);pol=np.cross(dirs,[0.,0.,1.]);pol/=np.linalg.norm(pol,axis=1)[:,None]
    rr=fibonacci(rx);c,s=np.cos(rotation),np.sin(rotation);rr=rr@np.array([[c,-s,0],[s,c,0],[0,0,1]])
    b1=np.cross(rr,[0.,0.,1.]);b1/=np.linalg.norm(b1,axis=1)[:,None];b2=np.cross(rr,b1)
    return dirs,pol,5*rr,np.stack([b1,b2],axis=1)

def grid(n,edge=1.5):
    h=edge/n;x=(np.arange(n)+.5)*h-edge/2
    return np.stack(np.meshgrid(x,x,x,indexing='ij'),-1).reshape(-1,3),h**3

def contrast(points,seed,strength=1.,family=0):
    rng=np.random.default_rng(seed);p=np.asarray(points);out=np.full(len(p),.06)
    if family==0:
        for i in range(3):
            center=rng.uniform(-.35,.35,3);axis=rng.uniform(.16,.30,3)
            out+=rng.uniform(.6,1.2)*np.exp(-.5*np.sum(((p-center)/axis)**2,axis=1))
    elif family==1:
        for i in range(2):
            center=rng.uniform(-.3,.3,3);axis=rng.uniform(.2,.4,3)
            rho=np.sum(((p-center)/axis)**2,axis=1)
            out+=rng.uniform(.8,1.2)*np.maximum(1-rho,0)**2
    else:
        p=p-rng.uniform(-.08,.08,3)
        out+=.65*(np.abs(p[:,0]+.18)<.23)*(np.abs(p[:,1])<.4)*(np.abs(p[:,2]-.08)<.35)
        out+=.9*np.exp(-np.sum(((p-[.3,.1,-.15])/.23)**2,axis=1))
    return strength*out+1j*(.025+.04*strength*out)

def haar(n):
    if n&(n-1):raise ValueError('Haar control requires power-of-two grid')
    H=np.ones((1,1));size=1
    while size<n:
        H=np.vstack([np.kron(H,[1,1]),np.kron(np.eye(size),[1,-1])*np.sqrt(size)])
        size*=2
    return H/np.sqrt(n)

class Tangent:
    def __init__(self,points,volume,kind='voxel'):
        self.n=len(points);self.volume=volume;self.kind=kind;self.Q=None
        if kind!='voxel':
            n=round(self.n**(1/3))
            if kind=='gaussian':
                centers=np.stack(np.meshgrid(*([np.linspace(-.45,.45,3)]*3),indexing='ij'),-1).reshape(-1,3)
                T=np.exp(-np.sum((points[:,None,:]-centers[None,:,:])**2,axis=-1)/(2*.28**2))
            elif kind in ['wavelet','wavelet_full']:
                H=haar(n).T;c=n if kind=='wavelet_full' else min(3,n)
                T=np.einsum('ia,jb,kc->ijkabc',H[:,:c],H[:,:c],H[:,:c]).reshape(self.n,c**3)
            else:raise ValueError(kind)
            U,s,_=svd(np.sqrt(volume)*T,full_matrices=False);cut=100*np.finfo(float).eps*max(T.shape)*s[0]
            self.Q=U[:,s>cut]/np.sqrt(volume)
        self.d=2*(self.n if self.Q is None else self.Q.shape[1])
    def expand(self,z):
        z=np.asarray(z);h=self.d//2;c=z[:h]+1j*z[h:]
        return c/np.sqrt(self.volume) if self.Q is None else self.Q@c
    def adjoint(self,g):
        c=g/np.sqrt(self.volume) if self.Q is None else self.Q.T@g
        return np.concatenate([c.real,c.imag],axis=0)
    def project(self,dc):return self.volume*self.adjoint(dc)

def trace_factors(M,ntest,alpha=.02,stages=4):
    c=2*np.log(2*stages*ntest/alpha)/M
    fa=lambda u:np.expm1(-u)+u-c
    fb=lambda u:np.expm1(u)-u-c
    hi=1.
    while fa(hi)<0:hi*=2
    a=np.exp(-brentq(fa,0,hi,xtol=1e-14))
    hi=1.
    while fb(hi)<0:hi*=2
    b=np.exp(brentq(fb,0,hi,xtol=1e-14))
    return a,b

def orth(A):
    U,s,_=svd(A,full_matrices=False)
    return U[:,s>max(A.shape)*np.finfo(float).eps*100*(s[0] if len(s) else 1)]

def probe_bank(state,tangent,V,sigma,seed,count=64,law='gaussian'):
    rng=np.random.default_rng(seed);z=rng.normal(size=(tangent.d,count)) if law=='gaussian' else rng.choice([-1.,1.],size=(tangent.d,count))
    t=time.perf_counter();K=state.current_jvp(tangent.expand(z));amps=np.einsum('ni,pnk->pik',V.conj(),K)
    ys=np.sum(abs(amps)**2,axis=0);q=ys.mean(axis=1);C=np.einsum('pik,pjk->ij',amps,amps.conj())/count
    return dict(q=q,tau=sigma*sigma*q,samples=ys,C=C,wall_s=time.perf_counter()-t,K=K,z=z,law=law,seed=seed)

def choose(bank,sigma,r,alpha=.02):
    records=[];s=len(sigma);r=min(r,s)
    for M in [8,16,32,64]:
        if M>bank['samples'].shape[1]:break
        q=bank['samples'][:,:M].mean(axis=1);a,b=trace_factors(M,s,alpha)
        tau=q*sigma**2;idx=np.argsort(-tau,kind='stable')[:r];rest=np.setdiff1d(np.arange(s),idx)
        lo=tau/b;hi=tau/a;margin=float(np.min(lo[idx])-np.max(hi[rest])) if len(rest) else None
        records.append(dict(M=M,margin=margin,interval_lower=lo,interval_upper=hi))
        if not len(rest) or margin>0:break
    separated=not len(rest) or margin>0
    return idx,dict(samples=M,ideal_exact_oracle_interval_separated=separated,ranking_status='numerical_enclosure_unverified' if separated else 'unresolved',alpha=alpha,scope='per_linearization_all_stages; no roundoff enclosure',history=records)

def step(state,tangent,data,scale,lam=1e-3,reg_coeff=None,max_cg=60):
    r=(state.field-data)/scale;reg_coeff=np.zeros(tangent.d) if reg_coeff is None else reg_coeff
    grad=tangent.adjoint(state.vjp(r/scale))+lam*reg_coeff
    def mv(z):return tangent.adjoint(state.vjp(state.jvp(tangent.expand(z))/scale**2))+lam*z
    H=LinearOperator((tangent.d,tangent.d),matvec=mv,dtype=float);history=[]
    def callback(x):history.append(float(np.linalg.norm(x)))
    t=time.perf_counter();z,info=cg(H,-grad,rtol=1e-4,atol=0,maxiter=max_cg,callback=callback)
    return z,dict(cg_info=int(info),cg_iterations=len(history),normal_residual=float(np.linalg.norm(mv(z)+grad)),gradient_norm=float(np.linalg.norm(grad)),wall_s=time.perf_counter()-t)

def angle(a,b):
    den=np.linalg.norm(a)*np.linalg.norm(b)
    return None if den<1e-25 else float(np.degrees(np.arccos(np.clip(np.real(np.vdot(a,b))/den,-1,1))))
