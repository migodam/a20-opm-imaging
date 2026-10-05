"""Mixed, degree-nested Schur-feedback representation and stable projections."""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from scipy import linalg as la
from .backend import pack


class UnsafeCore(RuntimeError):
    pass


def orth(X, *, against=None, rank=None, rtol=1e-10):
    X = np.asarray(X, complex)
    if X.ndim == 1:
        X = X[:, None]
    if not X.shape[1]:
        return X.copy(), {'input_columns': 0, 'rank': 0, 'deflated': 0, 'scale': 0.}
    scale = float(la.norm(X))
    Y = X.copy()
    if against is not None and against.shape[1]:
        for _ in range(2):
            Y -= against@(against.conj().T@Y)
    u, sv, _ = la.svd(Y, full_matrices=False)
    threshold = rtol*max(scale, float(sv[0]) if len(sv) else 0.)
    keep = int(np.count_nonzero(sv>threshold))
    if rank is not None:
        keep = min(keep, rank)
    Q = u[:, :keep]
    return Q, {'input_columns': X.shape[1], 'rank': keep,
               'deflated': X.shape[1]-keep, 'scale': scale,
               'threshold': threshold, 'singular_values': sv.tolist()}


def core_stability(A, scale, config):
    sv = la.svdvals(A)
    if not len(sv):
        return {'safe': True, 'sigma_min': None, 'sigma_max': None, 'condition': 1.,
                'absolute_scaled_sigma_min': None, 'relative_sigma_min': None}
    low, high = float(sv[-1]), float(sv[0])
    relative = low/high if high else 0.
    scaled = low/max(1., scale)
    condition = high/low if low else float('inf')
    safe = (relative>config.get('core_relative_sigma_floor', 1e-10)
            and scaled>config.get('core_absolute_scaled_sigma_floor', 1e-10)
            and condition<config.get('core_condition_cap', 1e10))
    return {'safe': safe, 'sigma_min': low, 'sigma_max': high,
            'condition': condition, 'relative_sigma_min': relative,
            'absolute_scaled_sigma_min': scaled, 'scale_definition': 'max(1, full L Frobenius norm)'}


class SchurFeedback:
    """Exact F_eff on the complement; one physical action per application."""
    def __init__(self, view, U, config):
        self.view, self.U = view, np.asarray(U, complex)
        self.config = config
        self.book = view.book
        if la.norm(U.conj().T@U-np.eye(U.shape[1]))>1e-9:
            raise ValueError('Retained current basis not orthonormal')
        self.scale = float(la.norm(view._a._operator_L))
        if U.shape[1]:
            self.FU = view.F(U)
            self.FHU = view.F_adjoint(U)
            self.A = np.eye(U.shape[1])-U.conj().T@self.FU
            self.stability = core_stability(self.A, self.scale, config)
            if not self.stability['safe']:
                raise UnsafeCore('RETAINED_U_CORE_UNSAFE; empty U is the declared fallback')
            with self.book.span('retained_core_factorization', retained_factorizations=1):
                self.factor = la.lu_factor(self.A)
            self.PFU = self.project(self.FU)
            self.PFHU = self.project(self.FHU)
        else:
            self.A = np.empty((0, 0), complex)
            self.FU = self.FHU = self.PFU = self.PFHU = U.copy()
            self.factor = None
            self.stability = {'safe': True, 'condition': 1., 'empty_U': True}

    def project(self, v):
        return v-self.U@(self.U.conj().T@v) if self.U.shape[1] else v.copy()

    def coarse(self, rhs, adjoint=False):
        return la.lu_solve(self.factor, rhs, trans=2 if adjoint else 0)

    def R_U(self, v, adjoint=False):
        if not self.U.shape[1]:
            return np.zeros_like(v)
        return self.U@self.coarse(self.U.conj().T@v, adjoint)

    def F(self, v):
        v = self.project(v)
        fv = self.view.F(v)
        y = self.project(fv)
        if self.U.shape[1]:
            y += self.PFU@self.coarse(self.U.conj().T@fv)
        return self.project(y)

    def F_adjoint(self, v):
        v = self.project(v)
        fv = self.view.F_adjoint(v)
        y = self.project(fv)
        if self.U.shape[1]:
            y += self.PFHU@self.coarse(self.U.conj().T@fv, True)
        return self.project(y)

    def T(self, v):
        if not self.U.shape[1]:
            return v.copy()
        v = self.project(v)
        return v-self.R_U(self.view.L(v))

    def T_adjoint(self, v):
        if not self.U.shape[1]:
            return v.copy()
        return self.project(v-self.view.L_adjoint(self.R_U(v, True)))

    def K(self, v):
        if not self.U.shape[1]:
            return v.copy()
        return self.project(v-self.view.L(self.R_U(v)))

    def K_adjoint(self, v):
        if not self.U.shape[1]:
            return v.copy()
        v = self.project(v)
        return v-self.R_U(self.view.L_adjoint(v), True)


@dataclass
class SeedBundle:
    blocks: dict
    records: dict
    rng_seed: list
    material_probes: np.ndarray
    measurement_probes: np.ndarray


def build_seeds(view, schur, config, *, budgets=None, material_probes=None,
                measurement_probes=None):
    budgets = budgets or {k: config['seed_rank_'+k] for k in 'OPM'}
    seed = [config.get('master_seed', 20261005), view._a.problem.parent_id]
    rng = np.random.default_rng(np.random.SeedSequence(seed))
    p = view.chart.d
    if material_probes is None:
        material_probes = rng.normal(size=(p, budgets['M']))
        if budgets['M'] and view.previous is not None and la.norm(view.previous)>1e-12:
            material_probes[:, 0] = view.previous/la.norm(view.previous)
        material_probes /= np.maximum(la.norm(material_probes, axis=0), 1e-300)
    if measurement_probes is None:
        measurement_probes = rng.normal(size=(view.P*2*view.m, budgets['O']))
        if budgets['O']:
            measurement_probes[:, 0] = view.r
    from .backend import unpack
    # All source injections precede any seed-rank compression.
    bm = np.empty((view.n, 0), complex)
    bo = np.empty((view.n, 0), complex)
    bp = np.empty((view.n, 0), complex)
    if budgets['M']:
        bm = view.B(material_probes)
        bm = bm.transpose(1, 0, 2).reshape(view.n, -1)
        bm = schur.K(bm)
    if budgets['O']:
        oy = unpack(view._a.whiten(measurement_probes, adjoint=True), view.P, view.m)
        so = view.S_adjoint(oy.transpose(1, 0, 2).reshape(view.m, -1))
        bo = schur.T_adjoint(so)
    if budgets['P']:
        bp = schur.K(view.forcing())
    blocks, records = {}, {}
    for name, value in (('O', bo), ('P', bp), ('M', bm)):
        with view.book.span('seed_'+name+'_compression', **{'seed_'+name+'_input_rhs': value.shape[1]}):
            q, rec = orth(value, against=schur.U, rank=budgets[name],
                          rtol=config.get('orthogonal_rank_rtol', 1e-10))
        rec.update(source_count=view.P, requested_rank=budgets[name],
                   provenance={'O': 'measured residual plus independent whitened data probes, C*',
                               'P': 'all known illumination forcing, Kb',
                               'M': 'real physical-L2 material probes and prior accepted step, KB'}[name],
                   original_column_norms=la.norm(value, axis=0).tolist(),
                   no_truth_or_reference_step=True)
        blocks[name], records[name] = q, rec
    return SeedBundle(blocks, records, seed, material_probes, measurement_probes)


class BlockStream:
    """Propagate only own Arnoldi block; never a joint-compressed remainder."""
    def __init__(self, initial, action, book, rtol):
        self.action, self.book, self.rtol = action, book, rtol
        self.blocks = [initial]
        self.basis = initial.copy()
        self.recurrence = []

    def extend(self):
        last = self.blocks[-1]
        if not last.shape[1]:
            self.blocks.append(last.copy())
            self.recurrence.append({'breakdown': True, 'new_rank': 0})
            return
        raw = self.action(last)
        with self.book.span('native_stream_orthogonalization'):
            q, rec = orth(raw, against=self.basis, rtol=self.rtol)
        self.recurrence.append({'new_rank': q.shape[1], 'deflation': rec,
            'arnoldi_tail_norm': float(la.norm(raw-self.basis@(self.basis.conj().T@raw)-q@(q.conj().T@raw)))})
        self.blocks.append(q)
        self.basis = np.column_stack((self.basis, q))


class Hierarchy:
    def __init__(self, view, schur, seeds, config, families='OPM', forward_only=False):
        self.view, self.schur, self.seeds, self.config = view, schur, seeds, config
        self.families = families
        self.streams = {}
        for family in families:
            action = schur.F_adjoint if family=='O' and not forward_only else schur.F
            self.streams[family] = BlockStream(seeds.blocks[family], action, view.book,
                                              config.get('orthogonal_rank_rtol', 1e-10))
        self.degree = -1
        self.Q = np.empty((view.n, 0), complex)
        self.layers = []
        self.joint_records = []

    def at_degree(self, degree):
        if degree < self.degree:
            raise ValueError('Hierarchy grows monotonically; store earlier models explicitly')
        while self.degree < degree:
            if self.degree>=0:
                for stream in self.streams.values():
                    stream.extend()
            self.degree += 1
            raw = np.column_stack([self.streams[f].blocks[-1] for f in self.families])
            against = np.column_stack((self.schur.U, self.Q))
            with self.view.book.span('joint_orthogonalization'):
                q, rec = orth(raw, against=against, rtol=self.config.get('orthogonal_rank_rtol', 1e-10))
            self.Q = np.column_stack((self.Q, q))
            self.layers.extend([self.degree]*q.shape[1])
            self.joint_records.append(rec)
        Z = np.column_stack((self.schur.U, self.Q))
        return Z.copy(), {'degree': degree, 'rank': Z.shape[1], 'added_rank': self.Q.shape[1],
                         'degree_layers': self.layers.copy(), 'joint_deflation': self.joint_records.copy(),
                         'separate_stream_recurrences': {k: s.recurrence.copy() for k, s in self.streams.items()},
                         'orthogonality_error': float(la.norm(Z.conj().T@Z-np.eye(Z.shape[1]))),
                         'joint_core_is_single_Hessenberg': False}


class Projection:
    """Galerkin or explicitly frozen-test Petrov; no pseudo-inverse."""
    def __init__(self, adapter, x, Z, config, *, test=None, allow_petrov=True):
        self.adapter, self.x, self.Z, self.config = adapter, np.asarray(x).copy(), Z.copy(), config
        self.material_version = adapter.version(x)
        self.book = adapter.book
        self.LZ = adapter.apply_L(x, Z)
        self.SZ = adapter.apply_S(Z)
        self.scale = float(la.norm(adapter._operator_L))
        self.kind = 'galerkin' if test is None else 'frozen_test_petrov_qr'
        self.W = Z.copy() if test is None else test.copy()
        self.A = self.W.conj().T@self.LZ
        self.galerkin_stability = core_stability(Z.conj().T@self.LZ, self.scale, config)
        self.stability = core_stability(self.A, self.scale, config)
        self.fallback = None
        if not self.stability['safe'] and test is None and allow_petrov:
            with self.book.span('frozen_test_petrov_QR', petrov_fallbacks=1):
                self.W, R = la.qr(self.LZ, mode='economic')
            if self.W.shape[1] != Z.shape[1] or not core_stability(R, self.scale, config)['safe']:
                raise UnsafeCore('Petrov QR trial images rank-deficient')
            self.kind = 'frozen_test_petrov_qr'
            self.fallback = 'unsafe_Galerkin_to_frozen_Petrov'
            self.A = self.W.conj().T@self.LZ
            self.stability = core_stability(self.A, self.scale, config)
        if not self.stability['safe']:
            raise UnsafeCore('UNSAFE_PROJECTED_CORE; no damping or pseudo-inverse')
        with self.book.span('projected_core_factorization', projected_factorizations=1):
            self.factor = la.lu_factor(self.A)

    def check(self):
        if self.material_version != self.adapter.version(self.x):
            # Another trial may have been activated. Re-activate this exact
            # material, but never borrow another material's cached operator.
            raise ValueError('Projection cache invalidated by material refresh')

    def solve(self, rhs, adjoint=False):
        columns = 1 if rhs.ndim == 1 else rhs.shape[1]
        with self.book.span('reduced_core_adjoint_solve' if adjoint else 'reduced_core_solve',
                            reduced_core_rhs=columns):
            return la.lu_solve(self.factor, rhs, trans=2 if adjoint else 0)

    def apply(self, rhs):
        self.check()
        return self.Z@self.solve(self.W.conj().T@rhs)

    def adjoint(self, rhs):
        self.check()
        return self.W@self.solve(self.Z.conj().T@rhs, True)

    def trial(self, x):
        # The test basis is frozen for Petrov trials. For Galerkin W=Z.
        return Projection(self.adapter, x, self.Z, self.config,
                          test=self.W if self.kind!='galerkin' else None,
                          allow_petrov=False)


class ReducedJacobian:
    def __init__(self, adapter, x, state, projection):
        self.adapter, self.x, self.state, self.projection = adapter, np.asarray(x).copy(), state, projection
        self._matrix = None

    def action(self, d):
        one = d.ndim == 1
        b = self.adapter.apply_B(self.x, self.state, d)
        b = b[:, :, None] if one else b
        out = self.projection.apply(b.transpose(1, 0, 2).reshape(self.adapter.n, -1))
        out = self.adapter.apply_S(out).reshape(self.adapter.m, self.adapter.P, -1).transpose(1, 0, 2)
        data = self.adapter.whiten(pack(out))
        return data[:, 0] if one else data

    def pullback(self, w):
        from .backend import unpack
        one = w.ndim == 1
        w = w[:, None] if one else w
        data = unpack(self.adapter.whiten(w, adjoint=True), self.adapter.P, self.adapter.m)
        rhs = self.adapter.apply_S_adjoint(data.transpose(1, 0, 2).reshape(self.adapter.m, -1))
        z = self.projection.adjoint(rhs).reshape(self.adapter.n, self.adapter.P, -1).transpose(1, 0, 2)
        out = self.adapter.apply_B_adjoint(self.x, self.state, z)
        return out[:, 0] if one else out

    def matrix(self):
        self.projection.check()
        if self._matrix is None:
            with self.adapter.book.span('reduced_material_data_matrix', compressed_material_columns=self.adapter.p):
                b = self.adapter.compressed_B(self.x, self.state, self.projection.W)
                coeff = self.projection.solve(b.transpose(1, 0, 2).reshape(self.projection.Z.shape[1], self.adapter.P*self.adapter.p))
                coeff = coeff.reshape(self.projection.Z.shape[1], self.adapter.P, self.adapter.p).transpose(1, 0, 2)
                out = np.einsum('mr,prk->pmk', self.projection.SZ, coeff)
                self._matrix = self.adapter.whiten(pack(out))
        return self._matrix


class FullJacobian:
    def __init__(self, adapter, x, state):
        self.adapter, self.x, self.state = adapter, np.asarray(x).copy(), state
        self._matrix = None

    def action(self, d):
        if self._matrix is not None:
            return self._matrix@d
        return self.adapter.full_tangent_action(self.x, self.state, d)

    def pullback(self, w):
        if self._matrix is not None:
            return self._matrix.T@w
        return self.adapter.full_adjoint_action(self.x, self.state, w)

    def small_matrix(self):
        if self.adapter.p>128:
            return None
        if self._matrix is None:
            self._matrix = self.adapter.full_tangent_action(self.x, self.state, np.eye(self.adapter.p))
        return self._matrix
