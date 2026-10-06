"""Ordered task protection and tied projections from one frozen raw bank.

No operation in this module creates a Maxwell workspace.  A basis is stored
both as physical current columns and as coordinates in the shared bank, so
all arms reuse its previously paid operator images and compressed injections.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy import linalg as la

from a20.backend import pack, unpack
from a20.opm import UnsafeCore, core_stability


class AnatomyInputError(ValueError):
    """A frozen input, layout, or cached-state identity is invalid."""


class RankBudgetInfeasible(ValueError):
    """The fixed rank cannot contain every independent protected column."""


@dataclass
class ProtectedBasis:
    Z: np.ndarray
    T: np.ndarray
    metadata: dict[str, Any]


def _complex_matrix(value, name):
    value = np.asarray(value, dtype=np.complex128)
    if value.ndim != 2 or not np.all(np.isfinite(value)):
        raise AnatomyInputError("INVALID_COMPLEX_MATRIX:" + name)
    return value


def _real(value, name):
    value = np.asarray(value)
    if np.iscomplexobj(value) or not np.all(np.isfinite(value)):
        raise AnatomyInputError("INVALID_REAL_ARRAY:" + name)
    return np.asarray(value, dtype=np.float64)


def _indices(value, columns, name):
    result = [int(i) for i in value]
    if len(set(result)) != len(result) or any(i < 0 or i >= columns for i in result):
        raise AnatomyInputError("INVALID_BANK_INDICES:" + name)
    return result


def _ordered_columns(D, protected_indices, filler_indices, target_rank, rtol,
                     retained_count):
    """Double MGS, carrying exactly the same arithmetic in raw coordinates."""
    n, b = D.shape
    protected_indices = _indices(protected_indices, b, "protected")
    filler_indices = _indices(filler_indices, b, "fillers")
    if not 0 <= retained_count <= len(protected_indices) or not 0 < rtol < 1:
        raise AnatomyInputError("INVALID_QR_RANK_CONVENTION")
    qs, ts, accepted, deflated, filled = [], [], [], [], []
    retained_rank = 0

    def append(index, protected, ordinal):
        nonlocal retained_rank
        q = D[:, index].copy()
        t = np.zeros(b, dtype=np.complex128)
        t[index] = 1.0
        raw_norm = float(la.norm(q))
        if qs:
            Z, T = np.column_stack(qs), np.column_stack(ts)
            for _ in range(2):
                coeff = Z.conj().T @ q
                q -= Z @ coeff
                t -= T @ coeff
        norm = float(la.norm(q))
        threshold = rtol * raw_norm
        if raw_norm == 0.0 or norm <= threshold:
            deflated.append({"index": index, "protected": protected,
                             "raw_norm": raw_norm, "residual_norm": norm,
                             "threshold": threshold})
            return
        qs.append(q / norm)
        ts.append(t / norm)
        if protected:
            accepted.append(index)
            if ordinal < retained_count:
                retained_rank += 1
        else:
            filled.append(index)

    # Visit all protected columns before checking the budget.  No top-k or
    # later compression is allowed to remove an independent protected vector.
    for ordinal, index in enumerate(protected_indices):
        append(index, True, ordinal)
    protected_rank = len(qs)
    if target_rank is not None and protected_rank > target_rank:
        error = RankBudgetInfeasible("RANK_BUDGET_INFEASIBLE")
        error.details = {"protected_rank": protected_rank, "target_rank": target_rank,
                         "retained_rank": retained_rank, "accepted_source_indices": accepted}
        raise error
    used = set(protected_indices)
    for ordinal, index in enumerate(filler_indices):
        if target_rank is not None and len(qs) >= target_rank:
            break
        if index not in used:
            append(index, False, ordinal)
            used.add(index)
    if target_rank is not None and len(qs) != target_rank:
        error = RankBudgetInfeasible("INSUFFICIENT_INDEPENDENT_BASELINE_FILLERS")
        error.details = {"actual_rank": len(qs), "target_rank": target_rank,
                         "protected_rank": protected_rank, "retained_rank": retained_rank}
        raise error
    Z = np.column_stack(qs) if qs else np.empty((n, 0), np.complex128)
    T = np.column_stack(ts) if ts else np.empty((b, 0), np.complex128)
    reconstruction = float(la.norm(D @ T - Z))
    scale = float(la.norm(Z))
    orthogonality = float(la.norm(Z.conj().T @ Z - np.eye(Z.shape[1])))
    metadata = {"rank": Z.shape[1], "protected_rank": protected_rank,
                "retained_rank": retained_rank,
                "independent_protected_added_rank": protected_rank - retained_rank,
                "requested_protected_columns": len(protected_indices),
                "accepted_source_indices": accepted, "accepted_filler_indices": filled,
                "deflated_columns": deflated, "source_order_preserved": True,
                "protected_columns_never_truncated": True,
                "coordinate_reconstruction_error": reconstruction,
                "coordinate_reconstruction_relative_error": reconstruction / scale if scale else 0.,
                "orthogonality_error": orthogonality, "reorthogonalization_passes": 2}
    # A coordinate transform with destructive cancellation is an input/numeric
    # inconsistency, not permission to recompute Maxwell images for this arm.
    if reconstruction > 100 * rtol * max(scale, np.finfo(float).tiny):
        error = AnatomyInputError("RAW_BANK_COORDINATE_RECONSTRUCTION_FAILED")
        error.details = metadata
        raise error
    if orthogonality > max(100 * rtol, 1e-12):
        error = AnatomyInputError("PROTECTED_QR_ORTHOGONALITY_FAILED")
        error.details = metadata
        raise error
    return ProtectedBasis(Z, T, metadata)


def ordered_protected_basis(D, protected_indices, filler_indices, target_rank,
                            rtol=1e-10, retained_count=0):
    """Protect in source order, then fill in the frozen priority order.

    ``retained_count`` denotes the leading U columns in protected_indices.
    ``target_rank=None`` measures independent protection without filling.
    """
    D = _complex_matrix(D, "D")
    if target_rank is not None and (int(target_rank) != target_rank or target_rank < 0):
        raise AnatomyInputError("INVALID_TARGET_RANK")
    return _ordered_columns(D, protected_indices, filler_indices,
                            None if target_rank is None else int(target_rank),
                            float(rtol), int(retained_count))


def independent_addition_rank(U, additions, rtol=1e-10):
    U, additions = _complex_matrix(U, "U"), _complex_matrix(additions, "additions")
    if U.shape[0] != additions.shape[0]:
        raise AnatomyInputError("PROTECTED_BANK_CURRENT_DIMENSION_MISMATCH")
    D = np.column_stack((U, additions))
    result = ordered_protected_basis(D, range(D.shape[1]), [], None, rtol, U.shape[1])
    return result.metadata["independent_protected_added_rank"]


def random_bank(n, count, seed):
    """Predeclared complex Gaussian columns; no outcome-dependent redraws."""
    if int(n) != n or int(count) != count or n <= 0 or count < 0:
        raise AnatomyInputError("INVALID_RANDOM_BANK_DIMENSION")
    rng = np.random.default_rng(np.random.SeedSequence([int(v) for v in seed]))
    value = rng.normal(size=(int(n), int(count))) + 1j*rng.normal(size=(int(n), int(count)))
    if count:
        value /= la.norm(value, axis=0)
    return np.asarray(value, dtype=np.complex128)


def baseline_basis(bank, baseline_indices, retained_count=0):
    """Keep the original baseline columns exactly, without another gauge."""
    indices = _indices(baseline_indices, bank.D.shape[1], "baseline")
    T = np.eye(bank.D.shape[1], dtype=np.complex128)[:, indices]
    Z = bank.D[:, indices].copy()
    orthogonality = float(la.norm(Z.conj().T @ Z - np.eye(len(indices))))
    if orthogonality > 1e-8:
        raise AnatomyInputError("FROZEN_BASELINE_NOT_ORTHONORMAL")
    return ProtectedBasis(Z, T, {"rank": len(indices), "protected_rank": retained_count,
        "retained_rank": retained_count, "independent_protected_added_rank": 0,
        "accepted_source_indices": indices[:retained_count],
        "accepted_filler_indices": indices[retained_count:], "deflated_columns": [],
        "coordinate_reconstruction_error": 0., "coordinate_reconstruction_relative_error": 0.,
        "orthogonality_error": orthogonality, "original_baseline_gauge_preserved": True})


@dataclass
class SharedBank:
    D: np.ndarray
    LD: np.ndarray
    SD: np.ndarray
    DHB: np.ndarray
    whitening: Any
    L_scale: float
    parent_id: int = 0
    iteration: int = 17
    source_count: int | None = None
    data_channels: int | None = None

    def __post_init__(self):
        self.D = _complex_matrix(self.D, "D")
        self.LD = _complex_matrix(self.LD, "LD")
        self.SD = _complex_matrix(self.SD, "SD")
        self.DHB = np.asarray(self.DHB, dtype=np.complex128)
        self.whitening = _real(self.whitening, "whitening")
        n, b = self.D.shape
        if self.LD.shape != (n, b) or self.SD.shape[1] != b:
            raise AnatomyInputError("SHARED_OPERATOR_IMAGE_SHAPE_MISMATCH")
        if self.DHB.ndim != 3 or self.DHB.shape[1] != b or not np.all(np.isfinite(self.DHB)):
            raise AnatomyInputError("SHARED_COMPRESSED_B_SHAPE_MISMATCH")
        P, _, p = self.DHB.shape
        m = self.SD.shape[0]
        if p <= 0 or P <= 0 or m <= 0:
            raise AnatomyInputError("EMPTY_SOURCE_OR_MATERIAL_LAYOUT")
        if self.source_count is not None and int(self.source_count) != P:
            raise AnatomyInputError("SHARED_SOURCE_ORDER_DIMENSION_MISMATCH")
        if self.data_channels is not None and int(self.data_channels) != m:
            raise AnatomyInputError("SHARED_RECEIVER_DIMENSION_MISMATCH")
        if self.whitening.ndim not in (0, 2) or (self.whitening.ndim == 2 and
                self.whitening.shape != (P * 2 * m, P * 2 * m)):
            raise AnatomyInputError("REAL_PACKED_WHITENING_SHAPE_MISMATCH")
        if not np.isfinite(self.L_scale) or self.L_scale <= 0:
            raise AnatomyInputError("INVALID_FULL_OPERATOR_SCALE")
        self.source_count, self.data_channels = P, m
        self.material_dimension = p
        self.DHDL = self.D.conj().T @ self.LD

    def whiten(self, value, adjoint=False):
        value = _real(value, "packed data")
        if self.whitening.ndim == 0:
            return float(self.whitening) * value
        return (self.whitening.T if adjoint else self.whitening) @ value

    def project(self, trial, test, config, book):
        return CachedProjection(self, trial, test, config, book)


class CachedProjection:
    """One square, explicitly named core; its adjoint uses the same LU."""
    def __init__(self, bank, trial, test, config, book):
        self.bank, self.book = bank, book
        self.trial, self.test = trial, test
        self.Z, self.W = trial.Z, test.Z
        self.TZ, self.TW = trial.T, test.T
        b = bank.D.shape[1]
        if (self.TZ.shape != (b, self.Z.shape[1]) or self.TW.shape != (b, self.W.shape[1])
                or self.Z.shape[0] != bank.D.shape[0] or self.W.shape[0] != bank.D.shape[0]
                or self.Z.shape[1] != self.W.shape[1]):
            raise AnatomyInputError("SQUARE_PROJECTED_CORE_COORDINATE_MISMATCH")
        for label, Z, T in (("TRIAL", self.Z, self.TZ), ("TEST", self.W, self.TW)):
            scale = max(float(la.norm(Z)), np.finfo(float).tiny)
            if (not np.all(np.isfinite(Z)) or not np.all(np.isfinite(T))
                    or la.norm(bank.D@T-Z) > 100*config.get("orthogonal_rank_rtol", 1e-10)*scale
                    or la.norm(Z.conj().T@Z-np.eye(Z.shape[1])) > 1e-8):
                raise AnatomyInputError(label+"_BASIS_SHARED_BANK_COORDINATE_OR_ORTHOGONALITY_MISMATCH")
        with book.span("a21_shared_image_projection", shared_image_projection_assemblies=1):
            self.A = self.TW.conj().T @ bank.DHDL @ self.TZ
            self.SZ = bank.SD @ self.TZ
            self.WB = np.einsum("bk,pbd->pkd", self.TW.conj(), bank.DHB)
            self.stability = core_stability(self.A, bank.L_scale, config)
            self.singular_values = la.svdvals(self.A)
        if not self.stability["safe"]:
            error = UnsafeCore("UNSAFE_PROJECTED_CORE; no shift, fallback or pseudoinverse")
            error.details = {**self.stability, "singular_values": self.singular_values.tolist()}
            error.core = self.A.copy()
            raise error
        with book.span("a21_projected_core_factorization", projected_factorizations=1):
            self.factor = la.lu_factor(self.A)
        self.kind = "galerkin" if trial is test else "petrov"
        self.fallback = None
        self.max_primal_solve_backward_residual = 0.
        self.max_adjoint_solve_backward_residual = 0.
        self.solve_residual_records = []
        self.solve_residual_rtol = config.get("backend_consistency_rtol", 1e-9)

    def solve(self, rhs, adjoint=False):
        rhs = np.asarray(rhs, dtype=np.complex128)
        columns = 1 if rhs.ndim == 1 else rhs.shape[1]
        if rhs.ndim not in (1, 2) or rhs.shape[0] != self.A.shape[0] or not np.all(np.isfinite(rhs)):
            raise AnatomyInputError("PROJECTED_CORE_RHS_DIMENSION_OR_FINITE_CHECK_FAILED")
        with self.book.span("a21_reduced_core_adjoint_solve" if adjoint else "a21_reduced_core_solve",
                            reduced_core_rhs=columns):
            value = la.lu_solve(self.factor, rhs, trans=2 if adjoint else 0)
            operator = self.A.conj().T if adjoint else self.A
            denominator = float(la.norm(operator)*la.norm(value)+la.norm(rhs))
            residual = float(la.norm(operator@value-rhs))
            relative = residual/denominator if denominator else (0. if residual == 0 else float("inf"))
        key = "max_adjoint_solve_backward_residual" if adjoint else "max_primal_solve_backward_residual"
        setattr(self, key, max(getattr(self, key), relative))
        self.solve_residual_records.append({"adjoint": bool(adjoint), "RHS": columns,
                                            "backward_relative": relative, "absolute": residual})
        if not np.isfinite(relative) or relative > self.solve_residual_rtol:
            raise AnatomyInputError("PROJECTED_CORE_SOLVE_BACKWARD_RESIDUAL_FAILED")
        return value

    def apply(self, rhs):
        return self.Z @ self.solve(self.W.conj().T @ rhs)

    def adjoint(self, rhs):
        return self.W @ self.solve(self.Z.conj().T @ rhs, True)


class CachedJacobian:
    """Real material action and pullback from the same measured core."""
    def __init__(self, bank, projection, book=None):
        if projection.bank is not bank:
            raise AnatomyInputError("JACOBIAN_SHARED_BANK_OWNER_MISMATCH")
        self.bank, self.projection = bank, projection
        self.book = book or projection.book
        self._matrix = None

    def action(self, direction):
        d = _real(direction, "material direction")
        one = d.ndim == 1
        d = d[:, None] if one else d
        if d.ndim != 2 or d.shape[0] != self.bank.material_dimension:
            raise AnatomyInputError("JACOBIAN_REAL_MATERIAL_DIMENSION_MISMATCH")
        P, m, k = self.bank.source_count, self.bank.data_channels, self.projection.Z.shape[1]
        rhs = np.einsum("pkd,db->pkb", self.projection.WB, d)
        coeff = self.projection.solve(rhs.transpose(1, 0, 2).reshape(k, -1))
        coeff = coeff.reshape(k, P, d.shape[1]).transpose(1, 0, 2)
        data = np.einsum("mk,pkb->pmb", self.projection.SZ, coeff)
        value = self.bank.whiten(pack(data))
        return value[:, 0] if one else value

    def pullback(self, cotangent):
        w = _real(cotangent, "data cotangent")
        one = w.ndim == 1
        w = w[:, None] if one else w
        P, m, k = self.bank.source_count, self.bank.data_channels, self.projection.Z.shape[1]
        if w.ndim != 2 or w.shape[0] != P * 2 * m:
            raise AnatomyInputError("JACOBIAN_REAL_DATA_DIMENSION_MISMATCH")
        data = unpack(self.bank.whiten(w, adjoint=True), P, m)
        rhs = np.einsum("mk,pmb->kpb", self.projection.SZ.conj(), data)
        coeff = self.projection.solve(rhs.reshape(k, -1), True).reshape(k, P, w.shape[1])
        value = np.einsum("pkd,kpb->db", self.projection.WB.conj(), coeff).real
        return value[:, 0] if one else value

    def matrix(self):
        if self._matrix is None:
            with self.book.span("a21_reduced_material_data_matrix",
                                compressed_material_columns=self.bank.material_dimension):
                self._matrix = self.action(np.eye(self.bank.material_dimension))
        return self._matrix

    def small_matrix(self):
        return self.matrix()


class MatrixJacobian:
    """Only the existing trusted material solver consumes this real matrix."""
    def __init__(self, matrix):
        self._matrix = _real(matrix, "Jacobian")
        if self._matrix.ndim != 2:
            raise AnatomyInputError("INVALID_MATERIAL_DATA_MATRIX")

    def matrix(self):
        return self._matrix

    def small_matrix(self):
        return self._matrix

    def action(self, direction):
        return self._matrix @ _real(direction, "material direction")

    def pullback(self, cotangent):
        return self._matrix.T @ _real(cotangent, "data cotangent")
