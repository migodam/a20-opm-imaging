"""Real nonlinear adapter over the preserved A17/A9 vector Maxwell DDA."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import importlib.util
import sys
import numpy as np
from scipy import linalg as la
from .costs import CostBook

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location('a20_vendor_a9', ROOT/'vendor/a17/a9_engine.py')
kernel = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = kernel
_spec.loader.exec_module(kernel)


class ForbiddenAccess(RuntimeError):
    pass


def pack(value):
    """Original A17 per-illumination Re/Im ordering."""
    a = np.asarray(value)
    if a.ndim == 2:
        return np.concatenate((a.real, a.imag), axis=1).reshape(-1)
    return np.concatenate((a.real, a.imag), axis=1).reshape(-1, a.shape[-1])


def unpack(value, sources, receivers):
    a = np.asarray(value)
    if np.iscomplexobj(a):
        raise ValueError('Data cotangent is REAL')
    if a.ndim == 1:
        a = a.reshape(sources, 2*receivers)
        return a[:, :receivers] + 1j*a[:, receivers:]
    a = a.reshape(sources, 2*receivers, -1)
    return a[:, :receivers] + 1j*a[:, receivers:]


@dataclass(slots=True)
class MaterialChart:
    volume: float
    n: int
    Q: np.ndarray | None
    kind: str

    @property
    def q(self):
        return self.n if self.Q is None else self.Q.shape[1]

    @property
    def d(self):
        return 2*self.q

    def expand(self, z):
        z = np.asarray(z)
        if np.iscomplexobj(z) or z.shape[0] != self.d:
            raise ValueError('REAL material coordinates required')
        c = z[:self.q] + 1j*z[self.q:]
        return c/np.sqrt(self.volume) if self.Q is None else self.Q@c

    def adjoint(self, g):
        c = g/np.sqrt(self.volume) if self.Q is None else self.Q.T@g
        return np.concatenate((c.real, c.imag), axis=0)

    def project(self, dc):
        return self.volume*self.adjoint(dc)


@dataclass(slots=True)
class Problem:
    parent_id: int
    points: np.ndarray
    volume: float
    data: np.ndarray
    scale: float
    init: np.ndarray
    chart: MaterialChart
    dirs: np.ndarray
    pols: np.ndarray
    receivers: np.ndarray
    obs_basis: np.ndarray
    frequency: float

    def __getattr__(self, name):
        if name in ('truth', 'teacher', 'full_J', 'full_H', 'reference_step', 'labels'):
            raise ForbiddenAccess('OFFLINE_FIELD_IN_ONLINE_PROBLEM:'+name)
        raise AttributeError(name)


RUNTIME_KEYS = {'parent_id', 'points', 'volume', 'data0', 'scale', 'init', 'Q', 'kind',
                'dirs', 'pols', 'receivers', 'obs_basis', 'k', 'historical_exposed'}


def load_problem(path):
    with np.load(path, allow_pickle=False) as f:
        if set(f.files)-RUNTIME_KEYS:
            raise ForbiddenAccess('ONLINE_FILE_CONTAINS_OFFLINE_OR_UNREGISTERED_KEYS')
        a = {k: f[k].copy() for k in f.files}
    Q = a['Q'] if a['Q'].size else None
    n = len(a['points'])
    volume = float(a['volume'])
    if Q is not None and la.norm(volume*Q.T@Q-np.eye(Q.shape[1])) > 1e-10:
        raise ValueError('Material chart metric mismatch')
    chart = MaterialChart(volume, n, Q, str(a['kind']))
    return Problem(int(a['parent_id']), a['points'], volume, a['data0'], float(a['scale']),
                   a['init'], chart, a['dirs'], a['pols'], a['receivers'], a['obs_basis'], float(a['k']))


class Adapter:
    """L/F are complex current actions; B* is a REAL material pullback.

    The current metric is Euclidean in c=p/sqrt(v). MaterialChart restores
    the saved volume-orthonormal Q exactly, without recomputing SVD gauges.
    Whitening is a real map applied AFTER packing; raw S stays physical.
    """
    def __init__(self, problem, *, device='cpu', book=None, whitening=None):
        self.problem = problem
        self.chart = problem.chart
        self.book = book or CostBook(device=device, enforce=False)
        self.device = device
        with self.book.span('physical_geometry_setup'):
            self.model = kernel.DenseDDA(problem.points, problem.volume, problem.frequency,
                problem.dirs, problem.pols, problem.receivers, problem.obs_basis, device=device)
        self.P = self.model.P
        self.m = self.model.m
        self.n = self.model.n
        self.p = self.chart.d
        self.whitening = 1/problem.scale if whitening is None else np.asarray(whitening, float)
        self._operator_chi = None
        self._operator_L = None
        self._operator_gpu = None
        self._version = 0
        self._full_cache = None

    def whiten(self, w, adjoint=False):
        if np.ndim(self.whitening) == 0:
            return float(self.whitening)*w
        return (self.whitening.T if adjoint else self.whitening)@w

    def _activate(self, x, state=None):
        x = np.asarray(x, complex)
        if self._operator_chi is not None and np.array_equal(x, self._operator_chi):
            return
        with self.book.span('material_operator_refresh', material_operator_refreshes=1):
            self._operator_L = state.L if state is not None else self.model.L(x)
            self._operator_chi = x.copy()
            self._version += 1
            self._operator_gpu = None
            if self.device == 'cuda':
                import torch
                self._operator_gpu = torch.as_tensor(self._operator_L, device='cuda', dtype=torch.complex128)
                self.book.counts['L_upload_bytes'] += self._operator_L.nbytes

    def _apply(self, x, v, adjoint, role):
        self._activate(x)
        v = np.asarray(v, complex)
        columns = 1 if v.ndim == 1 else v.shape[1]
        counters = {role+'_actions': columns, 'Maxwell_matvec_rhs': columns}
        with self.book.span(role, **counters):
            if self.device == 'cuda':
                import torch
                a = torch.as_tensor(np.ascontiguousarray(v), device='cuda', dtype=torch.complex128)
                op = self._operator_gpu.mH if adjoint else self._operator_gpu
                z = (op@a).cpu().numpy()
                self.book.counts['operator_transfer_bytes'] += 2*v.nbytes
            else:
                z = self._operator_L.conj().T@v if adjoint else self._operator_L@v
            return v-z if role.startswith('F') else z

    def apply_L(self, x, v):
        return self._apply(x, v, False, 'L')

    def apply_L_adjoint(self, x, v):
        return self._apply(x, v, True, 'L_adjoint')

    def apply_F(self, x, v):
        return self._apply(x, v, False, 'F')

    def apply_F_adjoint(self, x, v):
        return self._apply(x, v, True, 'F_adjoint')

    def apply_S(self, v):
        columns = 1 if v.ndim == 1 else v.shape[1]
        with self.book.span('S', S_actions=columns):
            return self.model.GS@v

    def apply_S_adjoint(self, w):
        columns = 1 if w.ndim == 1 else w.shape[1]
        with self.book.span('S_adjoint', S_adjoint_actions=columns):
            return self.model.GS.conj().T@w

    def forcing(self, x):
        with self.book.span('illumination_forcing', forcing_rhs=self.P):
            a, _ = kernel.polarizability(x, self.problem.volume, self.problem.frequency)
            return (self.model.incident*np.repeat(a, 3)[None, :]/np.sqrt(self.problem.volume)).T

    def full_state(self, x, source=None, frequency=None, *, reuse=False):
        if frequency is not None and frequency != self.problem.frequency:
            raise ValueError('Frequency has a distinct Green/receiver model; stack separate adapters')
        if reuse and self._full_cache is not None and np.array_equal(x, self._full_cache.chi):
            self.book.counts['same_material_full_state_cache_hits'] += 1
            return self._full_cache if source is None else self._full_cache.current[int(source)].copy()
        with self.book.span('full_forward', full_forward_calls=1, full_forward_RHS=self.P,
                            full_LU_factorizations=1, full_state_backward_residual_L_rhs=self.P,
                            full_state_receiver_rhs=self.P, full_state_Goff_rhs=self.P):
            state = self.model.state(x)
            residual = state.source_residual()
            if residual > 1e-9:
                raise ValueError('Full state backward residual exceeds 1e-9')
        self._full_cache = state
        self._activate(x, state)
        return state if source is None else state.current[int(source)].copy()

    def reduced_state(self, x, reduced):
        if reduced.material_version != self.version(x):
            raise ValueError('Reduced core is stale for this trial')
        with self.book.span('reduced_forward', reduced_forward_RHS=self.P, reduced_state_Goff_rhs=self.P):
            current = reduced.apply(self.forcing(x)).T
            exciting = self.model.incident + self.model.goff_apply((np.sqrt(self.problem.volume)*current).T).T
            a, da = kernel.polarizability(x, self.problem.volume, self.problem.frequency)
            return ReducedState(np.asarray(x).copy(), current, exciting, da,
                                current@self.model.GS.T, self._version, self.model)

    def version(self, x):
        self._activate(x)
        return self._version

    def injection_factor(self, x, state):
        if not np.array_equal(x, state.chi):
            raise ValueError('B/state material mismatch')
        if state.model is not self.model:
            raise ValueError('B/state source/frequency/geometry mismatch')
        return state.exciting.reshape(self.P, self.model.N, 3)*state.da[None, :, None]/np.sqrt(self.problem.volume)

    def apply_B(self, x, state, d):
        d = np.asarray(d)
        if np.iscomplexobj(d):
            raise ValueError('Material direction must be REAL')
        one = d.ndim == 1
        dc = self.chart.expand(d)
        dc = dc[:, None] if one else dc
        with self.book.span('B', B_rhs=self.P*dc.shape[1]):
            factor = self.injection_factor(x, state)
            z = np.einsum('ptc,tb->ptcb', factor, dc).reshape(self.P, self.n, -1)
            return z[:, :, 0] if one else z

    def apply_B_adjoint(self, x, state, v):
        one = v.ndim == 2
        v = v[:, :, None] if one else v
        with self.book.span('B_adjoint', B_adjoint_rhs=self.P*v.shape[2]):
            factor = self.injection_factor(x, state)
            g = np.einsum('ptc,ptcb->tb', factor.conj(), v.reshape(self.P, self.model.N, 3, -1))
            z = self.chart.adjoint(g)
            return z[:, 0] if one else z

    def compressed_B(self, x, state, Z):
        """Z*B through real pullbacks, never an n_current x p full Jacobian."""
        with self.book.span('compressed_injection', compressed_B_current_columns=self.P*Z.shape[1]):
            f = self.injection_factor(x, state)
            c = np.einsum('qtc,ptc->pqt', Z.conj().T.reshape(Z.shape[1], self.model.N, 3), f)
            if self.chart.Q is None:
                c /= np.sqrt(self.problem.volume)
            else:
                c = c@self.chart.Q
            return np.concatenate((c, 1j*c), axis=2)

    def full_tangent_action(self, x, state, d):
        if not np.array_equal(x, state.chi):
            raise ValueError('Full tangent state/material mismatch')
        if getattr(state, 'reduced', False):
            raise ValueError('Full tangent requires a full state')
        if state.model is not self.model:
            raise ValueError('Full tangent source/frequency/geometry mismatch')
        self.book.check()
        columns = 1 if d.ndim == 1 else d.shape[1]
        with self.book.span('full_tangent', full_tangent_calls=1, full_tangent_RHS=self.P*columns,
                            full_tangent_receiver_rhs=self.P*columns):
            out = state.jvp(self.chart.expand(d))
            return self.whiten(pack(out))

    def full_adjoint_action(self, x, state, w):
        if not np.array_equal(x, state.chi):
            raise ValueError('Full adjoint state/material mismatch')
        if getattr(state, 'reduced', False):
            raise ValueError('Full adjoint requires a full state')
        if state.model is not self.model:
            raise ValueError('Full adjoint source/frequency/geometry mismatch')
        if w.ndim != 1:
            return np.column_stack([self.full_adjoint_action(x, state, w[:, i]) for i in range(w.shape[1])])
        with self.book.span('full_adjoint', full_adjoint_calls=1, full_adjoint_RHS=self.P,
                            full_adjoint_receiver_rhs=self.P):
            z = unpack(self.whiten(w, adjoint=True), self.P, self.m)
            return self.chart.adjoint(state.vjp(z))

    def residual(self, state):
        return self.whiten(pack(state.field-self.problem.data))

    def full_objective(self, x, prior=1e-5, *, state=None):
        if state is None:
            state = self.full_state(x)
        if getattr(state, 'reduced', False):
            raise ValueError('Full objective requires a full state')
        if state.model is not self.model:
            raise ValueError('Full objective source/frequency/geometry mismatch')
        if not np.array_equal(x, state.chi):
            raise ValueError('Objective state mismatch')
        r = self.residual(state)
        z = self.chart.project(np.asarray(x)-self.problem.init)
        return float(.5*r@r+.5*prior*z@z), r, state

    def material_constraints(self, x):
        return {'real_lower': -.5, 'imag_lower': 0.,
                'violation': max(0., float(-.5-np.min(x.real)), float(-np.min(x.imag))),
                'chart': self.chart}

    def counters_and_timers(self):
        return {'adapter': self.book.receipt(), 'native_DDA': self.model.counters.as_dict()}


@dataclass(slots=True)
class ReducedState:
    chi: np.ndarray
    current: np.ndarray
    exciting: np.ndarray
    da: np.ndarray
    field: np.ndarray
    version: int
    model: object

    @property
    def reduced(self):
        return True


class BasisView:
    """Builder capability. No full solutions, J/H, old step or truth."""
    __slots__ = ('_a', 'x', '_state', 'r', 'previous', 'chart', 'book', 'P', 'm', 'n')

    def __init__(self, adapter, x, state, residual, previous=None):
        self._a = adapter
        self.x = np.asarray(x).copy()
        self._state = state
        self.r = residual.copy()
        self.previous = previous
        self.chart = adapter.chart
        self.book = adapter.book
        self.P, self.m, self.n = adapter.P, adapter.m, adapter.n

    def F(self, v):
        return self._a.apply_F(self.x, v)

    def F_adjoint(self, v):
        return self._a.apply_F_adjoint(self.x, v)

    def L(self, v):
        return self._a.apply_L(self.x, v)

    def L_adjoint(self, v):
        return self._a.apply_L_adjoint(self.x, v)

    def S(self, v):
        return self._a.apply_S(v)

    def S_adjoint(self, v):
        return self._a.apply_S_adjoint(v)

    def B(self, d):
        return self._a.apply_B(self.x, self._state, d)

    def B_adjoint(self, v):
        return self._a.apply_B_adjoint(self.x, self._state, v)

    def forcing(self):
        return self._a.forcing(self.x)

    def receiver(self, rank):
        with self.book.span('receiver_geometry_SVD', receiver_SVD_builds=int(self._a.model._gs_svd is None)):
            return self._a.model.gs_modes()['V'][:, :rank].copy()

    def __getattr__(self, name):
        if name in ('teacher', 'truth', 'full_J', 'full_H', 'full_current', 'current_correction',
                    'full_state', 'reference_step', 'old_anchor', 'labels'):
            raise ForbiddenAccess('FORBIDDEN_BASIS_FIELD:'+name)
        raise AttributeError(name)
