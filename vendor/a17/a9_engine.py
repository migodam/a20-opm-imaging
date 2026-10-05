#!/usr/bin/env python3
"""a9_engine.py -- portable dense finite 3D Maxwell DDA research backend (A9).

Scope
-----
Discrete vector Maxwell (DDA / VIE) on a fixed set of N point cells, one
frequency, isotropic local material, free-space background.  Everything here is
a *finite discretisation*: it carries no continuous-Maxwell error certificate
(A9_THEORY_CORE.md sec. 0, sec. 10).  Dense matrices are only intended for
manageable current counts, but the mutual interaction is the full dense
off-diagonal free-space Green operator (no FFT truncation, no sparse
approximation, no Born approximation).

Conventions (fixed once, see A9_THEORY_CORE.md sec. 1)
-----------------------------------------------------
time factor           exp(-i omega t)
material contrast     chi = (eps - eps_b)/eps_b,   N complex numbers
current variable      j (normalised polarisation current / dipole moment p)
dipole moment         p = sqrt(v) c,   c = orthonormal current coordinate
current metric        diag(1/v) (x) I3 in the dipole variable  -> c = p/sqrt(v)
material metric       M_x = v * I on the 2N real coordinates (allRe, allIm)

  E_p = e_p^inc + G_off p_p          (exciting field)
  p_p = a(chi) E_p                   (isotropic local response)
  f_p = G_S^phys p_p = G_recv p_p    (measured field, P illuminations)

In the orthonormal current coordinate c the state equation is
  L c_p = B_p,   L = I - A,   A = diag(a repeated 3) G_off,
  B_p = a (x) e_p^inc / sqrt(v),   G_S = sqrt(v) * G_recv,
exactly as required by A9_THEORY_TO_CODE_SPEC.md.  With a single scalar cell
volume the factor sqrt(v) is a global scale that cancels in A; it is kept
explicit so that the exposed operators match the specification.

Green function provenance
-------------------------
The off-diagonal dyadic Green is *identical* to
`Gaussian/A8/code/full_maxwell.py::FullMaxwell._receiver`

    G(dv) = exp(i k d)/(4 pi d) [ k^2 (I - nn) + (i k/d - 1/d^2)(I - 3 nn) ],
    n = dv/d,   dv = receiver - point   (the dyadic is even in dv)

with a zero diagonal (the self term lives inside the polarizability).  The
polarizability is the CM + radiation-reaction form of A8 `_material` /
A9 core (1.11)

    a  = 3 v chi / (chi + 3 - i 3 c_k v chi),   c_k = k^3/(6 pi),
    da = 9 v / (chi + 3 - i 3 c_k v chi)^2,

whose two-step A8 equivalent is checked in the smoke test.

Public interface
----------------
  DenseDDA(points, volume, k, dirs, pols, receivers, obs_basis, device='cpu')
  model.state(chi, basis=None) -> DDAState
  DDAState.field/.current/.exciting/.jvp/.current_jvp/.vjp/.L/.Lr
  physical_basis(T0, volume) -> QT          (QT^T (v I) QT = I)
  expand(QT, z) -> N complex                (allRe, allIm ordering)
  model.gs_modes() -> compact SVD of G_S
  model.domain_modes(count) -> true right SVD of G_off (small dense tests)
  tsom_basis(Vs, Vd, rank) -> TSOMBasis(.basis, .actualrank, ...)

No full Jacobian is ever formed, no optimiser and no experiment is included.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections import OrderedDict
from contextlib import contextmanager

import numpy as np
from scipy import linalg as sla

__all__ = [
    "Counters",
    "dump_counters",
    "dyadic_green",
    "build_goff",
    "receiver_operator",
    "polarizability",
    "polarizability_jvp",
    "orth",
    "orth_seq",
    "physical_basis",
    "expand",
    "real_material_gradient",
    "tsom_basis",
    "TSOMBasis",
    "DenseDDA",
    "DDAState",
    "ALGEBRA_ATOL",
    "ALGEBRA_RTOL",
    "ORTH_TOL",
]

EPS = float(np.finfo(float).eps)
ALGEBRA_ATOL = 1e-12
ALGEBRA_RTOL = 1e-10
ORTH_TOL = 1e-10


# --------------------------------------------------------------------------- #
# counters / timing
# --------------------------------------------------------------------------- #
class Counters:
    """Call and timing bookkeeping shared by a model and all of its states.

    `totals` holds integer call counters.  The important ones for the A9 cost
    accounting are the solved right-hand-side counts:

        solve_rhs            total solved RHS (all fidelities, forward + adjoint)
        solve_rhs_full       RHS solved against the full 3N x 3N L
        solve_rhs_reduced    RHS solved against a reduced r x r L_r
        solve_rhs_adjoint    RHS solved with the conjugate-transpose operator
        solve_rhs_forward    state RHS
        solve_rhs_tangent    JVP RHS
        solve_calls          number of LAPACK/torch solve calls
        lu_factorizations    number of dense factorisations
        goff_rhs             3N-vectors pushed through G_off / G_off^H

    `timings` accumulates wall seconds per phase and `events` keeps structured
    records (shapes, residuals, device) for later serialisation.
    """

    def __init__(self):
        self.totals = OrderedDict()
        self.timings = OrderedDict()
        self.events = []
        self.created = time.time()

    # -- counters ---------------------------------------------------------- #
    def bump(self, name, n=1):
        n = int(n)
        if n:
            self.totals[name] = self.totals.get(name, 0) + n
        return n

    def add_time(self, name, seconds):
        self.timings[name] = self.timings.get(name, 0.0) + float(seconds)

    def event(self, **kw):
        self.events.append(dict(kw))

    @contextmanager
    def timed(self, name):
        t0 = time.perf_counter()
        try:
            yield
        finally:
            self.add_time(name, time.perf_counter() - t0)

    # -- serialisation ----------------------------------------------------- #
    def as_dict(self):
        return {
            "totals": {k: int(v) for k, v in self.totals.items()},
            "timings_s": {k: round(float(v), 9) for k, v in self.timings.items()},
            "event_count": len(self.events),
            "events": self.events,
        }

    def to_json(self, indent=2):
        return json.dumps(self.as_dict(), indent=indent)

    def summary(self):
        """Compact one-line-per-counter view for worker stdout."""
        return {
            "solve_rhs": self.totals.get("solve_rhs", 0),
            "solve_rhs_full": self.totals.get("solve_rhs_full", 0),
            "solve_rhs_reduced": self.totals.get("solve_rhs_reduced", 0),
            "solve_rhs_adjoint": self.totals.get("solve_rhs_adjoint", 0),
            "solve_calls": self.totals.get("solve_calls", 0),
            "lu_factorizations": self.totals.get("lu_factorizations", 0),
            "goff_rhs": self.totals.get("goff_rhs", 0),
            "wall_seconds": round(float(sum(self.timings.values())), 9),
        }


def _counters_of(source):
    if isinstance(source, Counters):
        return source
    counters = getattr(source, "counters", None)
    if counters is None:
        counters = getattr(getattr(source, "model", None), "counters", None)
    if counters is None:
        raise TypeError("object carries no Counters instance")
    return counters


def dump_counters(source, path=None, indent=2):
    """Serialise counters of a model/state (or a Counters) to JSON.

    Returns the JSON string; writes it to `path` when given.
    """
    text = _counters_of(source).to_json(indent=indent)
    if path is not None:
        with open(path, "w") as fh:
            fh.write(text)
    return text


# --------------------------------------------------------------------------- #
# free-space dyadic Green (A8-identical)
# --------------------------------------------------------------------------- #
def dyadic_green(dv, k):
    """Free-space dyadic Green with the A8 `_receiver` normalisation.

    Parameters
    ----------
    dv : (..., 3) float array
        Receiver minus source displacement(s); `dv = 0` is not allowed (the
        self term belongs to the polarizability).
    k : float
        Background wavenumber.

    Returns
    -------
    (..., 3, 3) complex128 with
        G_cd = exp(i k d)/(4 pi d) [ k^2 (d_cd - n_c n_d)
                                     + (i k/d - 1/d^2)(d_cd - 3 n_c n_d) ].
    """
    dv = np.asarray(dv, dtype=float)
    squeeze = dv.ndim == 1
    if squeeze:
        dv = dv[None, :]
    k = float(k)
    d = np.linalg.norm(dv, axis=-1)
    if np.any(d <= 0.0):
        raise ValueError("dyadic_green: zero separation (self term excluded)")
    inv = 1.0 / d
    n = dv * inv[..., None]
    nn = n[..., :, None] * n[..., None, :]
    eye = np.eye(3)
    pref = np.exp(1j * k * d) * inv / (4.0 * np.pi)
    out = pref[..., None, None] * (
        k * k * (eye - nn)
        + (1j * k * inv - inv * inv)[..., None, None] * (eye - 3.0 * nn)
    )
    return out[0] if squeeze else out


def build_goff(points, k, block=None, counters=None):
    """Dense off-diagonal free-space Green operator G_off (3N x 3N).

    Layout: index 3*i + c is cell i, cartesian component c (cell-major,
    component-minor) -- the same layout as A8 `_receiver` and as `_inc`.
    The diagonal 3x3 blocks are exactly zero.
    """
    pts = np.asarray(points, dtype=float).reshape(-1, 3)
    N = len(pts)
    n = 3 * N
    if block is None:
        # keep the transient (block, N, 3, 3) complex128 buffer below ~50 MB
        block = max(1, int(5.0e7 / (16.0 * 9.0 * max(N, 1))))
    G = np.empty((n, n), dtype=complex)
    for i0 in range(0, N, block):
        i1 = min(N, i0 + block)
        dv = pts[i0:i1, None, :] - pts[None, :, :]
        d = np.linalg.norm(dv, axis=-1)
        safe = d > 0.0
        inv = np.where(safe, 1.0 / np.where(safe, d, 1.0), 0.0)
        nhat = dv * inv[..., None]
        nn = nhat[..., :, None] * nhat[..., None, :]
        eye = np.eye(3)
        pref = np.where(safe, np.exp(1j * k * d) * inv / (4.0 * np.pi), 0.0)
        gb = pref[..., None, None] * (
            k * k * (eye - nn)
            + (1j * k * inv - inv * inv)[..., None, None] * (eye - 3.0 * nn)
        )
        gb = np.where(safe[..., None, None], gb, 0.0)
        # gb is (block, cell_i, c, cell_j, d); put (cell, component) contiguous
        # on each side so that row 3*i+c, column 3*j+d
        G[3 * i0 : 3 * i1, :] = gb.transpose(0, 2, 1, 3).reshape((i1 - i0) * 3, n)
    if counters is not None:
        counters.bump("kernel_build_blocks", int(np.ceil(N / block)))
        counters.bump("kernel_entries", n * n)
    return G


def receiver_operator(points, k, receivers, obs_basis):
    """Observation operator G_recv (2R x 3N), A8 `_receiver` verbatim.

    Row (r, q) is b_q^T G(receiver_r - x_n); `obs_basis` has shape (R, 2, 3).
    """
    pts = np.asarray(points, dtype=float).reshape(-1, 3)
    rec = np.asarray(receivers, dtype=float).reshape(-1, 3)
    bas = np.asarray(obs_basis, dtype=complex).reshape(len(rec), 2, 3)
    rows = []
    for r, b in zip(rec, bas):
        dv = r[None, :] - pts
        d = np.linalg.norm(dv, axis=1)
        if np.any(d <= 0.0):
            raise ValueError("receiver_operator: receiver on a dipole cell")
        nhat = dv / d[:, None]
        nn = nhat[:, :, None] * nhat[:, None, :]
        eye = np.eye(3)
        green = np.exp(1j * k * d)[:, None, None] / (4.0 * np.pi * d[:, None, None]) * (
            k * k * (eye - nn)
            + (1j * k / d - 1.0 / d**2)[:, None, None] * (eye - 3.0 * nn)
        )
        rows.append(np.einsum("qc,ncd->qnd", b, green).reshape(2, -1))
    return np.concatenate(rows, axis=0)


# --------------------------------------------------------------------------- #
# polarizability (CM + radiation reaction)
# --------------------------------------------------------------------------- #
def polarizability(chi, volume, k):
    """Isotropic CM + radiation-reaction polarizability and its chi-derivative.

        a  = 3 v chi / den,   da = 9 v / den^2,
        den = chi + 3 - i 3 c_k v chi,   c_k = k^3/(6 pi)

    Both forms avoid the artificial pole at chi = -3 of the two-step A8
    expression; only den = 0 is a genuine model singularity.  At chi = 0,
    a = 0 and da = v exactly (no division by the contrast).
    """
    chi = np.asarray(chi, dtype=complex).reshape(-1)
    den = chi + 3.0 - 1j * 3.0 * (float(k) ** 3 / (6.0 * np.pi)) * float(volume) * chi
    a = 3.0 * float(volume) * chi / den
    da = 9.0 * float(volume) / den**2
    return a, da


def polarizability_jvp(chi, dchi, volume, k):
    """D a[chi][dchi] = da * dchi, i.e. the material tangent of a(chi)."""
    _, da = polarizability(chi, volume, k)
    return da * np.asarray(dchi, dtype=complex).reshape(-1)


# --------------------------------------------------------------------------- #
# orthonormalisation helpers
# --------------------------------------------------------------------------- #
def column_scale(A):
    """Largest column Euclidean norm of A (0 for an empty matrix)."""
    A = np.asarray(A)
    if A.size == 0:
        return 0.0
    if A.ndim == 1:
        A = A[:, None]
    return float(np.max(np.linalg.norm(A, axis=0)))


def orth(A, rtol=ORTH_TOL, scale=None):
    """Rank-revealing SVD orthonormalisation of complex columns.

    A singular value is kept only when it exceeds `rtol * scale`, where
    `scale` defaults to the largest input column norm.  Passing the scale of
    the *pre-projection* matrix is what turns a numerically residualised block
    (whose own entries are pure round-off) into an empty basis.
    """
    A = np.asarray(A, dtype=complex)
    if A.ndim == 1:
        A = A[:, None]
    if A.size == 0:
        return A.reshape(A.shape[0], 0)
    if scale is None:
        scale = column_scale(A)
    if scale == 0.0:
        return A.reshape(A.shape[0], 0)
    U, s, _ = np.linalg.svd(A, full_matrices=False)
    if s.size == 0:
        return A.reshape(A.shape[0], 0)
    keep = s > rtol * scale
    return U[:, keep]


def orth_seq(V, rtol=ORTH_TOL, scale=None):
    """Order-preserving modified Gram-Schmidt with rank revelation.

    Returns (Q, dropped).  Column j is kept only if the residual norm after
    projecting out the already-kept columns exceeds rtol * scale, with `scale`
    the largest input column norm unless given explicitly.
    """
    V = np.asarray(V, dtype=complex)
    if V.ndim == 1:
        V = V[:, None]
    if scale is None:
        scale = column_scale(V)
    if scale == 0.0:
        return np.zeros((V.shape[0], 0), dtype=complex), list(range(V.shape[1]))
    cols, dropped = [], []
    for j in range(V.shape[1]):
        v = V[:, j].copy()
        for u in cols:
            v -= u * np.vdot(u, v)
        nv = np.linalg.norm(v)
        if nv > rtol * scale:
            cols.append(v / nv)
        else:
            dropped.append(j)
    if cols:
        return np.stack(cols, axis=1), dropped
    return np.zeros((V.shape[0], 0), dtype=complex), dropped


# --------------------------------------------------------------------------- #
# physical material basis
# --------------------------------------------------------------------------- #
def physical_basis(T0, volume, rank_rtol=None, rank_atol=0.0, return_info=False):
    """Weighted rank-revealing material basis (A9 core (1.4)).

    Parameters
    ----------
    T0 : (2N, d) real
        Raw physical tangent columns, real coordinates ordered
        (allRe, allIm) of the complex contrast chi.
    volume : float
        Cell volume; M_x = v I on those coordinates.

    Returns
    -------
    QT : (2N, d_kept) real, with QT^T (v I) QT = I_{d_kept} and
         ran QT = ran T0 up to the numerical rank.  With `return_info=True`
         returns (QT, info) where info records the discarded singular values,
         the rank threshold and the residual invariants.

    The basis never consults any Jacobian: a physically admissible direction is
    not deleted because it happens to be unobservable (A9 sec. 1.4/M01).
    """
    if np.iscomplexobj(T0):
        raise ValueError("physical_basis: T0 must be a real (2N, d) array")
    T0 = np.asarray(T0, dtype=float)
    if T0.ndim == 1:
        T0 = T0[:, None]
    if float(volume) <= 0.0:
        raise ValueError("physical_basis: metric_singular (volume must be > 0)")
    m, d0 = T0.shape
    if m % 2:
        raise ValueError("physical_basis: T0 must have 2N rows (allRe, allIm)")
    N = m // 2
    w = float(np.sqrt(volume))
    U, s, _ = np.linalg.svd(w * T0, full_matrices=False)
    rtol = (max(m, d0) * EPS * 100.0) if rank_rtol is None else float(rank_rtol)
    smax = float(s[0]) if s.size else 0.0
    thr = max(rtol * smax, float(rank_atol))
    keep = s > thr
    QT = U[:, keep] / w
    info = {
        "rank": int(keep.sum()),
        "raw_columns": int(d0),
        "singular_values": s.tolist(),
        "discarded_singular_values": s[~keep].tolist(),
        "rank_threshold": float(thr),
        "rank_rtol": float(rtol),
        "rank_atol": float(rank_atol),
        "weighted_orthogonality_error": float(
            np.max(np.abs(QT.T @ (volume * QT) - np.eye(int(keep.sum()))))
        )
        if keep.any()
        else 0.0,
        "span_residual": float(np.linalg.norm(T0 - QT @ (QT.T @ (volume * T0))))
        / max(float(np.linalg.norm(T0)), 1e-300),
        "flags": [],
        "physical_tangent_id": hashlib.sha1(
            np.ascontiguousarray(QT).tobytes()
        ).hexdigest()[:16],
    }
    if not keep.any():
        info["flags"].append("empty_tangent")
    return (QT, info) if return_info else QT


def expand(QT, z):
    """Material coordinates (allRe, allIm) -> N complex: dchi = zR + i zI.

    `z` is a **real** probe coordinate (d,) or (d, B); a complex input is
    rejected rather than silently truncated, because the admissible material
    coordinate is real by construction (A9 sec. 1.3/1.4).
    """
    QT = np.asarray(QT, dtype=float)
    if np.iscomplexobj(z):
        raise ValueError("expand: z must be real (allRe, allIm) coordinates")
    z = np.asarray(z, dtype=float)
    if QT.ndim != 2 or QT.shape[0] % 2:
        raise ValueError("expand: QT must have 2N rows")
    N = QT.shape[0] // 2
    if z.ndim == 1:
        return QT[:N, :] @ z + 1j * (QT[N:, :] @ z)
    return QT[:N, :] @ z + 1j * (QT[N:, :] @ z)


def real_material_gradient(QT, grad):
    """Complex N-gradient -> real (2N,) gradient: QT^T [Re g; Im g].

    Satisfies grad_real . z = Re vdot(grad, expand(QT, z)) for real z.
    """
    QT = np.asarray(QT, dtype=float)
    g = np.asarray(grad, dtype=complex).reshape(-1)
    return QT.T @ np.concatenate([g.real, g.imag])


def _rank_of(Q):
    return 0 if Q.size == 0 else Q.shape[1]


# --------------------------------------------------------------------------- #
# TSOM retained span
# --------------------------------------------------------------------------- #
class TSOMBasis:
    """Retained TSOM span P = P_S + B_D B_D^*, B_D = orth((I-P_S) V_D)."""

    def __init__(self, basis, actualrank, rank_requested, gs_rank, vd_rank, info):
        self.basis = basis
        self.actualrank = int(actualrank)
        self.rank_requested = int(rank_requested)
        self.gs_rank = int(gs_rank)
        self.vd_rank = int(vd_rank)
        self.info = dict(info)

    def __array__(self, dtype=None):
        return np.asarray(self.basis, dtype=dtype)

    def __len__(self):
        return self.actualrank

    def as_dict(self):
        out = dict(self.info)
        out["actualrank"] = self.actualrank
        out["rank_requested"] = self.rank_requested
        out["gs_rank"] = self.gs_rank
        out["vd_rank"] = self.vd_rank
        return out


def tsom_basis(Vs, Vd, rank, orth_rtol=ORTH_TOL):
    """Retained TSOM span from a GS basis Vs and a domain basis Vd.

    Split of the requested rank: floor(rank/2) columns from Vs (GS side), the
    remainder from the PS-residualised Vd; shortfalls are filled from the
    leftover Vs columns and then from the leftover residualised Vd columns so
    that the span has at most exactly `rank` columns.  Dependent columns are
    dropped and reported through `.actualrank` (which can be < rank when the
    two bases span fewer than `rank` directions in total).

    Columns are always right/current-space vectors from Vs / Vd.  A left-side
    (output) image is never mixed into the retained input span.
    """
    Vs = np.asarray(Vs, dtype=complex)
    Vd = np.asarray(Vd, dtype=complex)
    if Vs.ndim == 1:
        Vs = Vs[:, None]
    if Vd.ndim == 1:
        Vd = Vd[:, None]
    rank = int(rank)
    n = Vs.shape[0]
    gs_scale = column_scale(Vs)
    gd_scale = column_scale(Vd)
    Qs = orth(Vs, orth_rtol, scale=gs_scale) if Vs.size else Vs.reshape(n, 0)
    Qd_full = orth(Vd, orth_rtol, scale=gd_scale) if Vd.size else Vd.reshape(n, 0)
    Ps = Qs @ Qs.conj().T
    Qd = (
        orth(Qd_full - Ps @ Qd_full, orth_rtol, scale=gd_scale)
        if Qd_full.size
        else Qd_full
    )

    gs_split = int(rank // 2)
    take_s = min(gs_split, _rank_of(Qs))
    take_d = min(rank - take_s, _rank_of(Qd))
    order, tags = [], []
    for j in range(take_s):
        order.append(Qs[:, j])
        tags.append("Gs")
    for j in range(take_d):
        order.append(Qd[:, j])
        tags.append("GdResidual")
    j = take_s
    while len(order) < rank and j < _rank_of(Qs):
        order.append(Qs[:, j])
        tags.append("GsFill")
        j += 1
    j = take_d
    while len(order) < rank and j < _rank_of(Qd):
        order.append(Qd[:, j])
        tags.append("GdFill")
        j += 1
    raw = np.stack(order, axis=1) if order else np.zeros((n, 0), complex)
    V, dropped = orth_seq(raw, orth_rtol, scale=max(gs_scale, gd_scale))
    r = _rank_of(V)
    P = V @ V.conj().T
    info = {
        "requested_rank": rank,
        "gs_split": gs_split,
        "gs_available": _rank_of(Qs),
        "gd_residual_available": _rank_of(Qd),
        "gs_columns_taken": tags.count("Gs") + tags.count("GsFill"),
        "gd_residual_columns_taken": tags.count("GdResidual") + tags.count("GdFill"),
        "dropped_columns": len(dropped),
        "tags": tags,
        "flags": [],
        "invariants": {
            "projector_idempotence": float(np.max(np.abs(P @ P - P))) if r else 0.0,
            "ps_bd_orthogonality": float(np.max(np.abs(Qs.conj().T @ Qd)))
            if (_rank_of(Qs) and _rank_of(Qd))
            else 0.0,
            "P_Vs_residual": float(np.linalg.norm(P @ Qs - Qs)) if _rank_of(Qs) else 0.0,
            "P_Vd_residual": float(np.linalg.norm(P @ Qd_full - Qd_full))
            if _rank_of(Qd_full)
            else 0.0,
            "basis_orthonormality": float(np.max(np.abs(V.conj().T @ V - np.eye(r))))
            if r
            else 0.0,
        },
    }
    if r < rank:
        info["flags"].append("rank_shortfall")
    if _rank_of(Qs) + _rank_of(Qd) < rank:
        info["flags"].append("span_deficient")
    return TSOMBasis(V, r, rank, gs_split, _rank_of(Qd), info)


# --------------------------------------------------------------------------- #
# dense linear solver (numpy/scipy or torch complex128)
# --------------------------------------------------------------------------- #
class _Solver:
    """Dense LU factorisation / solves, numpy+scipy or torch complex128."""

    def __init__(self, counters, device="cpu"):
        self.counters = counters
        self.device = str(device).lower()
        self.torch = None
        self.torch_device = None
        if self.device not in ("cpu", "torch", "cuda"):
            raise ValueError("device must be 'cpu', 'torch' or 'cuda'")
        if self.device != "cpu":
            try:
                import torch
            except ImportError as exc:  # pragma: no cover - optional dependency
                raise RuntimeError(f"device={device!r} requires torch (optional)") from exc
            if self.device == "cuda" and not torch.cuda.is_available():
                raise RuntimeError("device='cuda' requested but CUDA is unavailable")
            self.torch = torch
            self.torch_device = torch.device("cuda" if self.device == "cuda" else "cpu")
        counters.event(kind="solver_init", device=self.device, torch=self.torch is not None)

    @property
    def array_module(self):
        return self.torch if self.torch is not None else np

    def _to_device(self, M):
        T = self.torch
        return T.as_tensor(np.asarray(M), dtype=T.complex128, device=self.torch_device)

    def _from_device(self, M):
        return M.detach().to("cpu").numpy()

    def factorize(self, M, label="full"):
        with self.counters.timed("solve_factorize_s"):
            self.counters.bump("lu_factorizations")
            self.counters.bump(f"lu_factorizations_{label}")
            if self.torch is None:
                lu, piv = sla.lu_factor(np.asarray(M))
                return ("numpy", lu, piv)
            lu, piv = self.torch.linalg.lu_factor(self._to_device(M))
            return ("torch", lu, piv)

    def solve(self, fac, B, trans=0, matrix=None, label="full"):
        """Solve M X = B (trans=0) or M^H X = B (trans=2)."""
        B = np.asarray(B)
        if B.ndim == 1:
            B = B[:, None]
        k = int(B.shape[1])
        with self.counters.timed("solve_s"):
            self.counters.bump("solve_calls")
            self.counters.bump("solve_rhs", k)
            self.counters.bump(f"solve_rhs_{label}", k)
            fidelity = "full" if str(label).startswith("full") else "reduced"
            self.counters.bump(f"solve_rhs_{fidelity}", k)
            if "adjoint" in label:
                self.counters.bump("solve_rhs_adjoint", k)
            if fac[0] == "numpy":
                X = sla.lu_solve(fac[1:], B, trans=trans)
            else:
                T = self.torch
                if trans == 0:
                    out = T.linalg.lu_solve(fac[1], fac[2], self._to_device(B))
                else:
                    out = T.linalg.lu_solve(fac[1], fac[2], self._to_device(B), adjoint=True)
                X = self._from_device(out)
        return X


# --------------------------------------------------------------------------- #
# model
# --------------------------------------------------------------------------- #
class DenseDDA:
    """Dense finite 3D Maxwell DDA model (fixed geometry, one frequency).

    Parameters
    ----------
    points : (N, 3) float
    volume : float                       cell volume (uniform, scalar)
    k : float                            background wavenumber
    dirs : (P, 3) float                  incidence directions (unit, propagation)
    pols : (P, 3) complex                incidence polarisations
    receivers : (R, 3) float
    obs_basis : (R, 2, 3) complex        two readout functionals per receiver
    device : {'cpu', 'torch', 'cuda'}    'cpu' = numpy/scipy; 'torch'/'cuda' use
                                         torch complex128 for LU and solves
    """

    def __init__(
        self,
        points,
        volume,
        k,
        dirs,
        pols,
        receivers,
        obs_basis,
        device="cpu",
        block=None,
        counters=None,
    ):
        t0 = time.perf_counter()
        self.counters = Counters() if counters is None else counters
        self.points = np.asarray(points, dtype=float).reshape(-1, 3)
        self.N = int(len(self.points))
        self.volume = float(volume)
        self.k = float(k)
        if not self.volume > 0.0:
            raise ValueError("DenseDDA: volume must be > 0 (material metric M_x = v I)")
        if not np.all(np.isfinite(self.points)):
            raise ValueError("DenseDDA: non-finite point coordinates")
        self.dirs = np.asarray(dirs, dtype=float).reshape(-1, 3)
        self.pols = np.asarray(pols, dtype=complex).reshape(-1, 3)
        if len(self.dirs) != len(self.pols):
            raise ValueError("dirs and pols must have the same length")
        self.P = int(len(self.dirs))
        self.receivers = np.asarray(receivers, dtype=float).reshape(-1, 3)
        self.obs_basis = np.asarray(obs_basis, dtype=complex).reshape(len(self.receivers), 2, 3)
        self.R = int(len(self.receivers))
        self.m = 2 * self.R
        self.n = 3 * self.N
        self.device = str(device).lower()
        self.solver = _Solver(self.counters, device=self.device)
        if self.n == 0:
            raise ValueError("DenseDDA: empty point set")

        with self.counters.timed("kernel_build_s"):
            self.Goff = build_goff(self.points, self.k, block=block, counters=self.counters)
        with self.counters.timed("observation_build_s"):
            self.GS = float(np.sqrt(self.volume)) * receiver_operator(
                self.points, self.k, self.receivers, self.obs_basis
            )
        self.GD = self.volume * self.Goff  # physical current-density Green (A9 1.6)
        self.incident = self._incident_fields()
        self._gs_svd = None
        self._domain_svd = None
        self.counters.event(
            kind="model_init",
            N=self.N,
            P=self.P,
            R=self.R,
            m=self.m,
            volume=self.volume,
            k=self.k,
            device=self.device,
            wall_s=time.perf_counter() - t0,
        )

    # -- construction helpers --------------------------------------------- #
    def _incident_fields(self):
        """(P, 3N) plane-wave incident fields, cell-major / component-minor."""
        phase = np.exp(1j * self.k * (self.points @ self.dirs.T))  # (N, P)
        inc = phase.T[:, :, None] * self.pols[:, None, :]  # (P, N, 1) * (P, 1, 3)
        return inc.reshape(self.P, self.n)

    # -- operators --------------------------------------------------------- #
    def goff_apply(self, X, adjoint=False):
        """Apply G_off (or G_off^H) to columns of X, counting RHS."""
        X = np.asarray(X, complex)
        squeeze = X.ndim == 1
        if squeeze:
            X = X[:, None]
        self.counters.bump("goff_rhs", X.shape[1])
        out = self.Goff.conj().T @ X if adjoint else self.Goff @ X
        return out[:, 0] if squeeze else out

    def A_matrix(self, chi):
        """A = diag(a repeated 3) G_off in the orthonormal current coordinate."""
        a, _ = polarizability(chi, self.volume, self.k)
        return np.repeat(a, 3)[:, None] * self.Goff

    def L(self, chi):
        """Full L = I - A (diagnostic; states expose the same as `state.L`)."""
        n = self.n
        return np.eye(n, dtype=complex) - self.A_matrix(chi)

    # -- spectral objects -------------------------------------------------- #
    def gs_modes(self):
        """Compact (thin) SVD of G_S: U (m,s), s (s,), V (3N,s)."""
        if self._gs_svd is None:
            with self.counters.timed("gs_svd_s"):
                U, s, Vh = np.linalg.svd(self.GS, full_matrices=False)
            self._gs_svd = {"U": U, "s": s, "V": Vh.conj().T, "nullspace_basis": None}
            self.counters.bump("gs_svd")
        return dict(self._gs_svd)

    def domain_modes(self, count=None):
        """True right SVD of G_off (small dense tests only).

        The retained *input* directions are right singular vectors of the
        physical Green operator G_off (3N x 3N, the field produced by a unit
        dipole current).  Eigenvectors of G_D are deliberately not used: G_off
        is complex symmetric, not Hermitian, so its eigenvectors are neither
        orthogonal nor the correct retained subspace (A9 sec. 6, sec. 10.3).

        Returns {'U', 's', 'V'} for G_off plus 's_Gd' = volume * s, the
        singular values of G_D = v * G_off (a scalar multiple leaves the right
        singular vectors unchanged).
        """
        if self._domain_svd is None:
            if self.n > 4000:
                raise ValueError(
                    "domain_modes: dense SVD is only for small tests "
                    f"(3N = {self.n})"
                )
            with self.counters.timed("domain_svd_s"):
                U, s, Vh = np.linalg.svd(self.Goff, full_matrices=False)
            self._domain_svd = {"U": U, "s": s, "V": Vh.conj().T, "s_Gd": self.volume * s}
            self.counters.bump("domain_svd")
            self.counters.event(
                kind="domain_svd",
                n=self.n,
                operator="Goff",
                sigma_max=float(s[0]) if s.size else 0.0,
                sigma_min=float(s[-1]) if s.size else 0.0,
                normality_defect=float(
                    np.linalg.norm(self.Goff.conj().T @ self.Goff - self.Goff @ self.Goff.conj().T)
                    / max(float(np.linalg.norm(self.Goff)) ** 2, 1e-300)
                ),
            )
        out = dict(self._domain_svd)
        if count is not None:
            k = int(count)
            out = {key: (val[:k] if key in ("s", "s_Gd") else val[:, :k]) for key, val in out.items()}
        return out

    @staticmethod
    def tsom_basis(Vs, Vd, rank, orth_rtol=ORTH_TOL):
        return tsom_basis(Vs, Vd, rank, orth_rtol=orth_rtol)

    # -- state ------------------------------------------------------------- #
    def state(self, chi, basis=None):
        return DDAState(self, chi, basis=basis)

    # -- bookkeeping ------------------------------------------------------- #
    def counters_dict(self):
        return self.counters.as_dict()

    def dump_counters(self, path=None, indent=2):
        return dump_counters(self, path, indent=indent)

    def __repr__(self):
        return (
            f"DenseDDA(N={self.N}, P={self.P}, m={self.m}, volume={self.volume:g}, "
            f"k={self.k:g}, device='{self.device}')"
        )


# --------------------------------------------------------------------------- #
# state (full or frozen-reduced)
# --------------------------------------------------------------------------- #
class DDAState:
    """Forward state plus analytic material JVP/VJP for a frozen basis.

    Full state (basis=None)
        L c_p = B_p,           L = I - A,   B_p = a (x) e_p^inc / sqrt(v)
        K_p(z) = L^{-1} (da dchi (x) E_p) / sqrt(v)
        J_p(z) = G_S K_p(z)

    Frozen reduced state (basis = V, V^H V = I_r)
        L_r = I_r - V^H A V,   c^r_p = V L_r^{-1} V^H B_p
        E^r_p = e_p^inc + G_off (sqrt(v) c^r_p)
        K^r_p(z) = V L_r^{-1} V^H (da dchi (x) E^r_p) / sqrt(v)     (9.1)
        J^r_p(z) = G_S K^r_p(z)

    The reduced tangent is built from the *reduced* exciting field, i.e. it is
    the derivative of the actual reduced forward map with the basis frozen
    before and after the perturbation (A9 sec. 8.1); it is not G_S P K_full.
    The basis is stored on the object and never adapted by any derivative call.
    """

    def __init__(self, model, chi, basis=None):
        t0 = time.perf_counter()
        self.model = model
        self.counters = model.counters
        self.chi = np.asarray(chi, dtype=complex).reshape(-1).copy()
        if self.chi.shape != (model.N,):
            raise ValueError(f"chi must have shape ({model.N},)")
        V = None if basis is None else np.asarray(basis, dtype=complex)
        if V is not None:
            if V.ndim == 1:
                V = V[:, None]
            if V.shape[0] != model.n:
                raise ValueError(f"basis must have {model.n} rows")
            gram = V.conj().T @ V
            r = V.shape[1]
            err = float(np.max(np.abs(gram - np.eye(r)))) if r else 0.0
            if err > 1e-8:
                raise ValueError(
                    "basis must be complex orthonormal (V^H V = I); "
                    f"deviation {err:g}. Use a9_engine.orth() first."
                )
        # frozen for the lifetime of the state: every derivative call reads it
        # and never adapts, rotates or re-selects it
        self._basis = V
        self.reduced = self.basis is not None
        self.rstate = 0 if self.basis is None else int(self.basis.shape[1])
        self.sqrt_v = float(np.sqrt(model.volume))

        with self.counters.timed("state_material_s"):
            self.a, self.da = polarizability(self.chi, model.volume, model.k)
        self.a_rep = np.repeat(self.a, 3)
        self.da_rep = np.repeat(self.da, 3)
        with self.counters.timed("state_matrix_s"):
            self.A = self.a_rep[:, None] * model.Goff
        self._L = None
        self._Lr = None

        # ---- forward solve ------------------------------------------------- #
        B_inc = (self.a_rep[None, :] * model.incident) / self.sqrt_v  # (P, n)
        if self.reduced:
            V = self.basis
            self.Lr = np.eye(self.rstate, dtype=complex) - V.conj().T @ (self.A @ V)
            fac = model.solver.factorize(self.Lr, label="reduced")
            rhs = V.conj().T @ B_inc.T  # (r, P)
            coeff = model.solver.solve(fac, rhs, label="reduced_forward")
            current = (V @ coeff).T
            self._Lr_factor = fac
        else:
            L = self._full_L()
            self._L_factor = model.solver.factorize(L, label="full")
            current = model.solver.solve(self._L_factor, B_inc.T, label="full_forward").T
        self.current = current  # (P, 3N) orthonormal current coordinate c = p/sqrt(v)
        self.p = self.sqrt_v * current
        with self.counters.timed("state_exciting_s"):
            self.exciting = model.incident + model.goff_apply(self.p.T).T
        with self.counters.timed("state_field_s"):
            self.field = current @ model.GS.T
        self.counters.event(
            kind="state",
            reduced=self.reduced,
            rstate=self.rstate,
            wall_s=time.perf_counter() - t0,
            field_shape=list(self.field.shape),
        )

    # -- exposed operators ------------------------------------------------- #
    @property
    def basis(self):
        """Frozen retained current basis (None for the full state)."""
        return self._basis

    def _full_L(self):
        if self._L is None:
            n = self.model.n
            self._L = np.eye(n, dtype=complex) - self.A
            self.counters.bump("full_L_materializations")
        return self._L

    @property
    def L(self):
        """Full L = I - A in orthonormal current coordinates (diagnostic)."""
        return self._full_L()

    @property
    def field_shape(self):
        return self.field.shape

    # -- residual diagnostics --------------------------------------------- #
    def source_residual(self):
        """Relative residual of the state equation actually solved."""
        if self.reduced:
            V = self.basis
            B_inc = (self.a_rep[None, :] * self.model.incident) / self.sqrt_v
            rhs = V.conj().T @ B_inc.T
            lhs = self.Lr @ (V.conj().T @ self.current.T)
            return float(np.linalg.norm(lhs - rhs) / max(np.linalg.norm(rhs), 1e-300))
        B_inc = ((self.a_rep[None, :] * self.model.incident) / self.sqrt_v).T
        lhs = self._full_L() @ self.current.T
        return float(np.linalg.norm(lhs - B_inc) / max(np.linalg.norm(B_inc), 1e-300))

    def full_equation_residual(self):
        """Relative residual of the reduced current in the FULL state equation.

        This is the reduced-vs-full dynamics gap e_p^state of A9 sec. 9.4; it is
        zero for the full state by construction.
        """
        B_inc = ((self.a_rep[None, :] * self.model.incident) / self.sqrt_v).T
        lhs = self._full_L() @ self.current.T
        return float(np.linalg.norm(lhs - B_inc) / max(np.linalg.norm(B_inc), 1e-300))

    # -- tangent ----------------------------------------------------------- #
    def _as_rows(self, dchi):
        dchi = np.asarray(dchi, dtype=complex)
        if dchi.ndim == 1:
            return dchi.reshape(-1, 1), True
        if dchi.ndim != 2:
            raise ValueError("dchi must be (N,) or (N, B)")
        if dchi.shape[0] != self.model.N:
            raise ValueError(f"dchi must have {self.model.N} rows")
        return dchi, False

    def _tangent_rhs(self, dchi):
        """(P, 3N, B) tangent injection from the state's own exciting field."""
        dchi, squeezed = self._as_rows(dchi)
        w = (self.da_rep[:, None] * np.repeat(dchi, 3, axis=0)) / self.sqrt_v  # (n,B)
        return np.einsum("pc,cb->pcb", self.exciting, w), dchi.shape[1], squeezed

    def current_jvp(self, dchi):
        """Material JVP -> induced current perturbation (P, 3N[, B])."""
        t0 = time.perf_counter()
        rhs, ncols, squeezed = self._tangent_rhs(dchi)
        P, n = self.model.P, self.model.n
        self.counters.bump("jvp_calls")
        if self.reduced:
            V = self.basis
            red = np.einsum("nr,pnb->rpb", V.conj(), rhs).reshape(self.rstate, P * ncols)
            coeff = self.model.solver.solve(
                self._Lr_factor, red, label="reduced_tangent"
            )  # (r, P*B), p-major / column-minor
            K = np.einsum("nr,rm->nm", V, coeff).reshape(n, P, ncols)
            out = K.transpose(1, 0, 2)
        else:
            # RHS matrix has one column per (illumination, probe) pair
            R = rhs.transpose(1, 0, 2).reshape(n, P * ncols)
            X = self.model.solver.solve(self._L_factor, R, label="full_tangent")
            out = X.reshape(n, P, ncols).transpose(1, 0, 2)
        self.counters.add_time("jvp_s", time.perf_counter() - t0)
        self.counters.bump("jvp_rhs", P * ncols)
        return out[:, :, 0] if squeezed else out

    def jvp(self, dchi):
        """Material JVP -> measured field perturbation (P, m[, B])."""
        t0 = time.perf_counter()
        K = self.current_jvp(dchi)
        squeezed = K.ndim == 2
        K3 = K[:, :, None] if squeezed else K
        out = np.einsum("oc,pcb->pob", self.model.GS, K3)
        self.counters.add_time("field_jvp_s", time.perf_counter() - t0)
        return out[:, :, 0] if squeezed else out

    def vjp(self, cotangent):
        """Adjoint of the JVP: cotangent (P, m) -> complex gradient (N,).

        Satisfies Re vdot(grad, dchi) = Re vdot(cotangent, jvp(dchi)); the two
        complex vectors are in fact equal under vdot for every dchi.  The
        corresponding real material-coordinate gradient of `expand(QT, z)` is
        `real_material_gradient(QT, grad)`.
        """
        t0 = time.perf_counter()
        cot = np.asarray(cotangent, dtype=complex)
        if cot.shape != (self.model.P, self.model.m):
            raise ValueError(f"cotangent must have shape ({self.model.P}, {self.model.m})")
        self.counters.bump("vjp_calls")
        y = np.einsum("oc,po->pc", self.model.GS.conj(), cot)  # G_S^H cot (P,n)
        if self.reduced:
            V = self.basis
            rhs = V.conj().T @ y.T  # (r, P)
            coeff = self.model.solver.solve(
                self._Lr_factor, rhs, trans=2, matrix=self.Lr, label="reduced_adjoint"
            )
            u = (V @ coeff).T  # (P, n)
        else:
            u = self.model.solver.solve(
                self._L_factor,
                y.T,
                trans=2,
                matrix=self.L,
                label="full_adjoint",
            ).T  # (P, n)
        # (D~^H u)_l = conj(da_l) sum_{p,j} conj(E^exc_{p,lj}) u_{p,lj} / sqrt(v)
        inner = np.einsum(
            "pnc,pnc->n",
            self.exciting.reshape(self.model.P, self.model.N, 3).conj(),
            u.reshape(self.model.P, self.model.N, 3),
        )
        grad = self.da.conj() * inner / self.sqrt_v
        self.counters.add_time("vjp_s", time.perf_counter() - t0)
        return grad

    # -- misc -------------------------------------------------------------- #
    @property
    def exciting_field(self):
        return self.exciting

    def __repr__(self):
        kind = f"reduced(r={self.rstate})" if self.reduced else "full"
        return (
            f"DDAState({kind}, P={self.model.P}, m={self.model.m}, "
            f"N={self.model.N})"
        )
