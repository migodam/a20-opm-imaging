"""Measurement-independent shallow OPM and real material factors for A22.

Only the declared known-background anchor uses a full forward state.  Basis
construction and material features use L/F, S, B and reduced core actions; no
full tangent, full adjoint, full Jacobian, Hessian or oracle is available to
the builder view.  Invalid cores propagate unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import time
from types import SimpleNamespace
from typing import Any, Mapping

import numpy as np

from a20.backend import Adapter, ForbiddenAccess, Problem, pack
from a20.opm import Hierarchy, Projection, SchurFeedback, build_seeds
from .assets import OnlineScene, load_config


_FORBIDDEN = frozenset(("teacher", "truth", "labels", "full_J", "full_H",
    "full_jacobian", "full_hessian", "full_current", "reference_step", "oracle",
    "full_state", "full_tangent_action", "full_adjoint_action", "current_correction",
    "old_anchor", "adapter", "state"))


def _readonly(value, dtype=None):
    result = np.array(value, dtype=dtype, copy=True)
    result.flags.writeable = False
    return result


def _config(config):
    result = dict(load_config() if config is None else config)
    expected = {"material_dimension": 32, "retained_rank": 8,
                "seed_rank_O": 4, "seed_rank_P": 4, "seed_rank_M": 4,
                "degree": 1, "current_rank": 32}
    if any(result.get(key) != value for key, value in expected.items()):
        raise ValueError("FROZEN_A22_SHALLOW_CONFIGURATION_CHANGED")
    if (result.get("allow_petrov_fallback", False) or result.get("allow_full_fallback", False)
            or result.get("measurement_dependent_Q", False)):
        raise ValueError("A22_ONLINE_BUILDER_FORBIDS_FALLBACK_OR_DATA_DEPENDENT_Q")
    if result.get("precision", "complex128/float64") != "complex128/float64":
        raise ValueError("A22_PRECISION_CHANGED")
    return result


def _cost_start(book):
    return time.perf_counter(), time.process_time(), {
        "counts": dict(book.counts), "exclusive_walls": dict(book.walls)}


def _cost_end(book, started):
    wall, cpu, old = started
    return {"counts": {key: int(value - old["counts"].get(key, 0))
                       for key, value in book.counts.items()},
            "exclusive_walls": {key: float(value - old["exclusive_walls"].get(key, 0.))
                                for key, value in book.walls.items()},
            "inclusive_wall_seconds": time.perf_counter() - wall,
            "process_cpu_seconds": time.process_time() - cpu}


@dataclass(frozen=True, slots=True)
class CacheIdentity:
    """Exact byte equality identity, deliberately without any integrity hash."""
    material: bytes
    geometry: tuple[bytes, ...]
    chart: bytes
    whitening: bytes
    configuration: str


def _array_identity(value):
    array = np.ascontiguousarray(value)
    header = repr((array.dtype.str, array.shape)).encode("ascii")
    return header + b"\0" + array.tobytes()


def _identity(adapter, chi, config):
    problem = adapter.problem
    geometry = tuple(_array_identity(value) for value in (
        problem.parent_id, problem.points, problem.volume, problem.frequency, problem.dirs,
        problem.pols, problem.receivers, problem.obs_basis))
    keys = ("schema", "source_freeze", "master_seed", "precision", "material_dimension",
            "retained_rank", "seed_rank_O", "seed_rank_P", "seed_rank_M", "degree",
            "current_rank", "orthogonal_rank_rtol", "core_relative_sigma_floor",
            "core_absolute_scaled_sigma_floor", "core_condition_cap", "noise_reference_fraction",
            "background", "measurement_dependent_Q", "allow_petrov_fallback", "allow_full_fallback")
    signature = json.dumps({key: config.get(key) for key in keys}, sort_keys=True, separators=(",", ":"))
    return CacheIdentity(_array_identity(chi), geometry, _array_identity(adapter.chart.Q),
                         _array_identity(adapter.whitening), signature)


@dataclass(slots=True)
class Anchor:
    adapter: Adapter
    state: Any
    chi: np.ndarray
    provenance: Mapping[str, Any]
    cache_key: CacheIdentity
    cost: Mapping[str, Any]

    @property
    def sigma_complex(self):
        return float(self.provenance["sigma_complex_reference"])


@dataclass(slots=True)
class MaterialFeatures:
    MW: np.ndarray
    PMW: np.ndarray
    AW: np.ndarray
    W: np.ndarray
    signatures: Mapping[str, Any]
    provenance: Mapping[str, Any]
    cost: Mapping[str, Any]

    def __getitem__(self, key):
        if key in ("MW", "PMW", "AW", "W", "signatures", "provenance", "cost"):
            return getattr(self, key)
        raise KeyError(key)


@dataclass(slots=True)
class OPMModel:
    anchor: Anchor
    view: Any
    feedback: SchurFeedback
    hierarchy: Hierarchy
    projection: Projection
    basis: np.ndarray
    MW: np.ndarray
    PMW: np.ndarray
    AW: np.ndarray
    provenance: Mapping[str, Any]
    cost: Mapping[str, Any]

    @property
    def sigma_complex(self):
        return self.anchor.sigma_complex


class _AdapterFacade:
    """Only compatibility members used by immutable a20.opm are exposed."""
    __slots__ = ("__adapter", "problem")

    def __init__(self, adapter):
        self.__adapter = adapter
        self.problem = SimpleNamespace(parent_id=adapter.problem.parent_id)

    @property
    def _operator_L(self):
        # SchurFeedback uses the declared full L norm for core safety, not a
        # full derivative.  L is already paid by anchor construction.
        return self.__adapter._operator_L

    def whiten(self, value, adjoint=False):
        return self.__adapter.whiten(value, adjoint=adjoint)

    def __getattr__(self, name):
        raise ForbiddenAccess("RESTRICTED_A22_ADAPTER_CAPABILITY:" + name)


class RestrictedBuilderView:
    __slots__ = ("__adapter", "__state", "_a", "x", "r", "previous",
                 "chart", "book", "P", "m", "n")

    def __init__(self, anchor):
        adapter = anchor.adapter
        self.__adapter, self.__state = adapter, anchor.state
        self._a = _AdapterFacade(adapter)
        self.x = _readonly(anchor.chi, complex)
        # No measured residual is needed by the declared fixed probes.  An
        # accidental future default-probe call cannot insert measurement data.
        self.r = _readonly(np.zeros(adapter.P * 2 * adapter.m), float)
        self.previous = None
        self.chart, self.book = adapter.chart, adapter.book
        self.P, self.m, self.n = adapter.P, adapter.m, adapter.n

    def F(self, value):
        return self.__adapter.apply_F(self.x, value)

    def F_adjoint(self, value):
        return self.__adapter.apply_F_adjoint(self.x, value)

    def L(self, value):
        return self.__adapter.apply_L(self.x, value)

    def L_adjoint(self, value):
        return self.__adapter.apply_L_adjoint(self.x, value)

    def S(self, value):
        return self.__adapter.apply_S(value)

    def S_adjoint(self, value):
        return self.__adapter.apply_S_adjoint(value)

    def B(self, direction):
        return self.__adapter.apply_B(self.x, self.__state, direction)

    def B_adjoint(self, value):
        return self.__adapter.apply_B_adjoint(self.x, self.__state, value)

    def forcing(self):
        return self.__adapter.forcing(self.x)

    def receiver(self, rank):
        adapter = self.__adapter
        with self.book.span("receiver_geometry_SVD", receiver_SVD_builds=int(adapter.model._gs_svd is None)):
            return adapter.model.gs_modes()["V"][:, :rank].copy()

    def __getattr__(self, name):
        if name in _FORBIDDEN or name.startswith("_state") or name.startswith("_adapter"):
            raise ForbiddenAccess("RESTRICTED_A22_BUILDER_CAPABILITY:" + name)
        raise AttributeError(name)


def build_anchor(scene, config=None, book=None, *, device="cpu"):
    """One known-background prediction; observed data never sets its noise RMS."""
    config = _config(config)
    if device not in ("cpu", "cuda"):
        raise ValueError("UNREGISTERED_A22_DEVICE")
    if not isinstance(scene, (OnlineScene, Problem)):
        raise ForbiddenAccess("ANCHOR_REQUIRES_ONLINE_SCENE_OR_LABEL_FREE_PROBLEM")
    problem = scene.problem if isinstance(scene, OnlineScene) else scene
    if problem.chart.d != 32 or problem.chart.Q is None or np.iscomplexobj(problem.chart.Q):
        raise ValueError("A22_FIXED_PATCH32_CHART_REQUIRED")
    metric_error = float(np.linalg.norm(problem.volume * problem.chart.Q.T @ problem.chart.Q - np.eye(16)))
    if metric_error > 1e-10:
        raise ValueError("A22_PHYSICAL_MATERIAL_METRIC_MISMATCH")
    background = complex(*config["background"])
    if not np.allclose(problem.init, background, rtol=0., atol=1e-14):
        raise ValueError("ANCHOR_BACKGROUND_IS_NOT_DECLARED_GEOMETRY_OWNED_BACKGROUND")
    fraction = float(config["noise_reference_fraction"])
    if not np.isfinite(fraction) or fraction <= 0:
        raise ValueError("POSITIVE_NOISE_REFERENCE_FRACTION_REQUIRED")
    if book is None:
        raise ValueError("A22_LEDGER_REQUIRED_BEFORE_ANCHOR_PHYSICS")
    started = _cost_start(book)
    with book.span("a22_geometry_owned_anchor", anchor_constructions=1):
        adapter = Adapter(problem, device=device, book=book, whitening=1.)
        if adapter.P != 6:
            raise ValueError("A22_ANCHOR_REQUIRES_SIX_SOURCES")
        chi = np.full(problem.chart.n, background, dtype=np.complex128)
        state = adapter.full_state(chi)
        with book.span("a22_known_background_noise_reference", noise_reference_predictions=1):
            reference_rms = float(np.linalg.norm(state.field) / np.sqrt(state.field.size))
            sigma_complex = fraction * reference_rms
            if not np.isfinite(sigma_complex) or sigma_complex <= 0:
                raise ValueError("KNOWN_BACKGROUND_PREDICTION_HAS_ZERO_OR_INVALID_NOISE_REFERENCE")
            adapter.whitening = float(np.sqrt(2.) / sigma_complex)
    provenance = {"anchor_origin": "known_geometry_owned_uniform_background",
        "background": [background.real, background.imag], "late_state_oracle_used": False,
        "truth_or_labels_read": False, "full_derivatives_used": False,
        "noise_reference_origin": "known_background_predicted_complex_data_RMS",
        "reference_complex_data_RMS": reference_rms, "noise_reference_fraction": fraction,
        "sigma_complex_reference": sigma_complex,
        "noise_definition": "E[abs(n_complex)^2]=sigma_complex_reference^2",
        "real_noise_variance": sigma_complex**2 / 2., "whitening": "sqrt(2)/sigma_complex_reference",
        "data_RMS_from_observations_used": False, "source_count": adapter.P,
        "data_pack": "per source real channels then imaginary; source-major",
        "current_units": "c = dipole / sqrt(cell_volume), Euclidean current metric",
        "material_units": "volume-orthonormal fixed mesh patch coefficients, real then imaginary",
        "source_freeze": config.get("source_freeze"), "new_integrity_hash_checks": 0}
    if isinstance(scene, OnlineScene):
        provenance["asset_provenance"] = dict(scene.provenance)
    chi = _readonly(chi)
    return Anchor(adapter, state, chi, provenance, _identity(adapter, chi, config), _cost_end(book, started))


def _fixed_probes(view, config):
    seed = [int(config["master_seed"]), int(view._a.problem.parent_id)]
    rng = np.random.default_rng(np.random.SeedSequence(seed))
    material = rng.normal(size=(view.chart.d, int(config["seed_rank_M"])))
    lengths = np.linalg.norm(material, axis=0)
    if np.any(lengths == 0):
        raise ValueError("FIXED_MATERIAL_PROBE_HAS_ZERO_NORM")
    material /= lengths
    # Explicit probes bypass a20.build_seeds' residual replacement default.
    measurement = rng.normal(size=(view.P * 2 * view.m, int(config["seed_rank_O"])))
    return material, measurement, seed


def material_features(opm, W=None):
    """Return MW, PMW and packed real AW using only compressed B/core/S images."""
    if not isinstance(opm, OPMModel):
        raise ValueError("A22_OPM_MODEL_REQUIRED")
    anchor, projection = opm.anchor, opm.projection
    adapter, book = anchor.adapter, anchor.adapter.book
    if (projection.kind != "galerkin" or projection.fallback is not None
            or not np.array_equal(projection.W, projection.Z)):
        raise ValueError("A22_FACTORS_REQUIRE_THE_DECLARED_GALERKIN_MODEL")
    projection.check()
    config_signature = json.loads(anchor.cache_key.configuration)
    if _identity(adapter, anchor.chi, config_signature) != anchor.cache_key:
        raise ValueError("A22_ANCHOR_MATERIAL_GEOMETRY_WHITENING_CACHE_CHANGED")
    W = np.eye(adapter.p) if W is None else np.asarray(W)
    if (np.iscomplexobj(W) or W.ndim != 2 or W.shape[0] != adapter.p
            or W.shape[1] != 32 or not np.all(np.isfinite(W))):
        raise ValueError("A22_MATERIAL_W_MUST_BE_FINITE_REAL_P_BY_32")
    W = np.asarray(W, dtype=np.float64)
    if np.linalg.norm(W.T @ W - np.eye(32)) > 1e-10:
        raise ValueError("A22_MATERIAL_W_IS_NOT_PHYSICAL_COORDINATE_ORTHONORMAL")
    started = _cost_start(book)
    with book.span("a22_material_factor_actions", material_feature_builds=1):
        compressed = adapter.compressed_B(anchor.chi, anchor.state, projection.Z)
        MW = np.einsum("pqd,dk->pqk", compressed, W)
        q = projection.Z.shape[1]
        solved = projection.solve(MW.transpose(1, 0, 2).reshape(q, adapter.P * 32))
        PMW = solved.reshape(q, adapter.P, 32).transpose(1, 0, 2)
        raw = np.einsum("mq,pqk->pmk", projection.SZ, PMW)
        AW = adapter.whiten(pack(raw))
        alpha = np.linalg.norm(MW, axis=(0, 1))
        propagated = np.linalg.norm(PMW, axis=(0, 1))
        detected = np.linalg.norm(AW, axis=0)
        beta = np.full(32, np.nan)
        gamma = np.full(32, np.nan)
        np.divide(propagated, alpha, out=beta, where=alpha != 0)
        np.divide(detected, propagated, out=gamma, where=propagated != 0)
    provenance = {"M_definition": "Q_current^* B(anchor) W; all six source blocks",
        "P_definition": "(Q_current^* L(anchor) Q_current)^-1; same LU for action and adjoint",
        "O_definition": "real-whitened source-major pack of S Q_current",
        "MW_shape": list(MW.shape), "PMW_shape": list(PMW.shape), "AW_shape": list(AW.shape),
        "current_metric": "Euclidean in dipole/sqrt(volume)",
        "material_metric": "Euclidean in volume-orthonormal patch coordinates",
        "direct_retained_path": "U is included in full current basis Q_current",
        "factor_values_are_complex_until_data_pack": True,
        "full_J_or_H_used": False, "certificate_type": "empirical_indicator",
        "zero_denominator_policy": "undefined NaN plus explicit branch label; no epsilon floor"}
    signatures = {"alpha": _readonly(alpha), "beta": _readonly(beta), "gamma": _readonly(gamma),
        "total_gain": _readonly(detected),
        "branches": tuple("zero_injection" if alpha[i] == 0 else
                          "zero_propagated" if propagated[i] == 0 else "defined" for i in range(32))}
    return MaterialFeatures(_readonly(MW), _readonly(PMW), _readonly(AW), _readonly(W),
                            signatures, provenance, _cost_end(book, started))


def build_opm(anchor, config=None):
    """Build U8/O4/P4/M4 degree1 once; no rank search or automatic fallback."""
    config = _config(config)
    if not isinstance(anchor, Anchor):
        raise ValueError("A22_GEOMETRY_OWNED_ANCHOR_REQUIRED")
    adapter, book = anchor.adapter, anchor.adapter.book
    if _identity(adapter, anchor.chi, config) != anchor.cache_key:
        raise ValueError("ANCHOR_CONFIG_MATERIAL_GEOMETRY_OR_WHITENING_CHANGED")
    started = _cost_start(book)
    with book.span("a22_fixed_shallow_opm", opm_constructions=1):
        view = RestrictedBuilderView(anchor)
        U = view.receiver(int(config["retained_rank"]))
        if U.shape[1] != 8:
            raise ValueError("A22_RETAINED_GEOMETRY_RANK_BELOW_DECLARED_EIGHT")
        feedback = SchurFeedback(view, U, config)
        with book.span("a22_measurement_independent_probe_bank", fixed_probe_bank_builds=1):
            material, measurement, seed = _fixed_probes(view, config)
        seeds = build_seeds(view, feedback, config, material_probes=material,
                            measurement_probes=measurement)
        for family in "OPM":
            seeds.records[family]["measurement_independent"] = True
        seeds.records["O"]["provenance"] = "fixed independent real whitened-data probes, no observed residual replacement"
        hierarchy = Hierarchy(view, feedback, seeds, config)
        basis, info = hierarchy.at_degree(1)
        if basis.shape[1] > 32:
            raise ValueError("A22_CURRENT_RANK_CAP_EXCEEDED")
        projection = Projection(adapter, anchor.chi, basis, config, allow_petrov=False)
        provenance = {"construction": "fixed U8 O4 P4 M4 degree1, actual rank may deflate",
            "measurement_dependent_Q": False, "measurement_probes_origin": "fixed independent RNG; no residual",
            "probe_seed": seed, "probe_source_count_before_compression": adapter.P,
            "seed_records": seeds.records, "hierarchy": info,
            "retained_rank": U.shape[1], "actual_current_rank": basis.shape[1], "current_rank_cap": 32,
            "direct_retained_path_included": True, "retained_fallback": None,
            "projection_fallback": projection.fallback, "core_stability": projection.stability,
            "material_dimension": adapter.p, "source_count": adapter.P,
            "complex_channels_per_source": adapter.m,
            "cache_identity": "exact anchored material/geometry/chart/whitening/config equality; no hash",
            "source_freeze": config.get("source_freeze"), "new_integrity_hash_checks": 0,
            "full_derivatives_or_oracles_used": False}
        model = OPMModel(anchor, view, feedback, hierarchy, projection, _readonly(basis),
                         np.empty((adapter.P, basis.shape[1], 32), complex),
                         np.empty((adapter.P, basis.shape[1], 32), complex),
                         np.empty((adapter.P * 2 * adapter.m, 32), float), provenance, {})
        features = material_features(model)
        model.MW, model.PMW, model.AW = features.MW, features.PMW, features.AW
        model.provenance = {**provenance, "material_features": dict(features.provenance),
                            "factor_signatures": features.signatures}
    model.cost = _cost_end(book, started)
    return model
