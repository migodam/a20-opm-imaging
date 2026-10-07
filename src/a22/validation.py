"""Metered A22 implementation health checks, separate from scientific gates.

Importing this module performs no model construction or validation.  The caller
owns the ledger lifetime.  Full derivatives are evaluator-only diagnostics;
the online builder continues to use its restricted L/S/B capability view.
"""
from __future__ import annotations

from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import sys
import time
import uuid

import numpy as np
from scipy import linalg as la

from a20.backend import ForbiddenAccess, Problem, pack, unpack
from a20.opm import Projection, SchurFeedback, UnsafeCore, core_stability, orth
from .assets import acquisition_geometry, fixed_patch_chart
from .core import constrained_material_solve
from .online import (
    _fixed_probes, build_anchor, build_opm, material_features,
)


class HealthFailure(RuntimeError):
    """A failed implementation check, with already completed evidence attached."""

    def __init__(self, name, checks):
        super().__init__("A22_HEALTH_CHECK_FAILED:" + name)
        self.health_checks = list(checks)


def _plain(value):
    if isinstance(value, np.ndarray):
        return _plain(value.tolist())
    if isinstance(value, np.generic):
        return _plain(value.item())
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def _relative(left, right):
    left, right = np.asarray(left), np.asarray(right)
    scale = max(float(la.norm(left)), float(la.norm(right)))
    difference = float(la.norm(left - right))
    return difference / scale if scale else difference


def _dot_error(left, right, scale):
    difference = float(abs(left - right))
    return difference / float(scale) if scale else difference


class _Checks:
    def __init__(self):
        self.rows = []

    def error(self, name, error, tolerance, **evidence):
        passed = bool(np.isfinite(error) and error <= tolerance)
        self.rows.append(dict(name=name, error=float(error), tolerance=float(tolerance),
                              status="PASS" if passed else "FAIL", **_plain(evidence)))
        if not passed:
            raise HealthFailure(name, self.rows)
        return error

    def condition(self, name, value, **evidence):
        self.error(name, 0. if value else 1., 0., **evidence)

    def metric(self, name, value, **evidence):
        self.rows.append(dict(name=name, value=_plain(value), status="RECORDED",
                              accuracy_gate=False, **_plain(evidence)))


def tiny_problem(config, *, n=4):
    """Known mesh with 64 physical cells, 32 real material coordinates, six sources.

    This is a finite DDA health fixture, not a continuum convergence study.  Its
    measurement placeholder is unused by the known-background anchor and basis.
    """
    if n != 4:
        raise ValueError("A22_HEALTH_MESH_IS_FROZEN_AT_FOUR_CELLS_PER_AXIS")
    edge = 1.5
    axis = (np.arange(n) + .5) * (edge / n) - edge / 2.
    points = np.stack(np.meshgrid(axis, axis, axis, indexing="ij"), axis=-1).reshape(-1, 3)
    volume = (edge / n)**3
    chart, provenance = fixed_patch_chart(points, volume)
    geometry = dict(n=n, edge=edge, wavenumber=2., rotation=.37,
                    receiver_count=64, partial=False, background=list(config["background"]))
    dirs, pols, receivers, obs = acquisition_geometry(geometry)
    background = complex(*config["background"])
    problem = Problem(9022, points, volume, np.zeros((6, 128), complex), 1.,
                      np.full(n**3, background, complex), chart, dirs, pols,
                      receivers, obs, geometry["wavenumber"])
    return problem, dict(geometry=geometry, material_chart=provenance,
                         fixture="known_geometry_only_DenseDDA_4x4x4", labels_used=False)


def _health_forward(adapter, chi, book):
    """Pay an FD state without changing Adapter's active anchor or cache version."""
    with book.action_guard("perturbation_forward", role="health",
                           scene_id=adapter.problem.parent_id, purpose="perturbation"):
        with book.span("full_forward", full_forward_calls=1,
                       full_forward_RHS=adapter.P, full_LU_factorizations=1,
                       full_state_backward_residual_L_rhs=adapter.P,
                       full_state_receiver_rhs=adapter.P, full_state_Goff_rhs=adapter.P):
            state = adapter.model.state(np.asarray(chi, complex))
            residual = float(state.source_residual())
            if not np.isfinite(residual) or residual > 1e-9:
                raise ValueError("A22_HEALTH_FORWARD_BACKWARD_RESIDUAL_EXCEEDS_1E_9")
            return state


def _pack_checks(checks, rng, sources=6, receivers=128):
    raw = rng.normal(size=(sources, receivers, 3)) + 1j*rng.normal(size=(sources, receivers, 3))
    expected = np.vstack([np.vstack((raw[p].real, raw[p].imag)) for p in range(sources)])
    checks.error("source_major_real_imag_pack", _relative(pack(raw), expected), 0.)
    checks.error("pack_unpack_three_columns", _relative(unpack(pack(raw), sources, receivers), raw), 0.)
    checks.error("pack_unpack_one_column", _relative(unpack(pack(raw[:, :, 0]), sources, receivers), raw[:, :, 0]), 0.)
    permutation = np.array([5, 2, 0, 4, 1, 3])
    indices = np.arange(sources * 2 * receivers).reshape(sources, 2 * receivers)[permutation].ravel()
    checks.error("source_permutation_pack", _relative(pack(raw[permutation]), pack(raw)[indices]), 0.)
    weights = np.linspace(.7, 1.3, sources * 2 * receivers)
    checks.error("source_permutation_whitening", _relative(
        weights[indices, None] * pack(raw[permutation]),
        (weights[:, None] * pack(raw))[indices]), 0., whitening="diagonal real data fixture")
    # Explicitly compare the legacy all-Re/all-Im convention through its known
    # permutation, never by assuming the two conventions have identical order.
    legacy = np.vstack((raw.real.reshape(sources * receivers, 3),
                        raw.imag.reshape(sources * receivers, 3)))
    legacy_indices = np.concatenate([
        np.r_[np.arange(p*receivers, (p+1)*receivers),
              np.arange(sources*receivers+p*receivers, sources*receivers+(p+1)*receivers)]
        for p in range(sources)])
    checks.error("legacy_pack_explicit_permutation", _relative(legacy[legacy_indices], pack(raw)), 0.)


def _noise_checks(checks, rng, anchor):
    unit_noise = (rng.normal(size=100000) + 1j*rng.normal(size=100000))/np.sqrt(2.)
    real_variance = float(np.var(unit_noise.real))
    imag_variance = float(np.var(unit_noise.imag))
    cross = float(np.mean(unit_noise.real * unit_noise.imag))
    checks.error("proper_complex_real_variance_half", abs(real_variance/.5-1.), .02,
                 empirical_variance=real_variance, samples=len(unit_noise))
    checks.error("proper_complex_imag_variance_half", abs(imag_variance/.5-1.), .02,
                 empirical_variance=imag_variance, samples=len(unit_noise))
    checks.error("proper_complex_cross_moment", abs(cross)/.5, .02, empirical_cross_moment=cross)
    checks.error("proper_complex_whitening_scale", _relative(
        np.asarray(anchor.adapter.whitening), np.sqrt(2.)/anchor.sigma_complex), 1e-14,
        reference_origin=anchor.provenance["noise_reference_origin"])
    whitened = anchor.adapter.whitening * anchor.sigma_complex * unit_noise
    checks.error("whitened_real_variance_one", abs(float(np.var(whitened.real))-1.), .02)
    checks.error("whitened_imag_variance_one", abs(float(np.var(whitened.imag))-1.), .02)


def _qp_check(checks, chart, chi, config, book):
    # The first imaginary coarse coordinate has positive injection only in its
    # own octant.  Its exact one-dimensional feasible lower bound is public.
    basis = np.eye(chart.d)[:, [chart.q]]
    coefficient_column = chart.Q[:, 0]
    positive = coefficient_column > 0
    lower = float(np.max(-chi.imag[positive]/coefficient_column[positive]))
    data = np.array([2.*lower-1.])
    lam = 1.
    step, audit, normal = constrained_material_solve(
        np.ones((1, 1)), data, chart, chi, config, book, basis=basis, lam=lam)
    exact = max(float(data[0]/(1.+lam)), lower)
    checks.error("coefficient_QP_active_bound", abs(float(basis[:, 0]@step)-exact), 1e-9,
                 coefficient_lower_bound=lower, bound_active=True)
    checks.error("coefficient_QP_KKT", audit["kkt_relative"], 1e-8,
                 audit=audit, coefficient_normal=normal)
    checks.error("coefficient_QP_physical_feasibility", max(
        0., float(-np.min((chi+chart.expand(step)).imag)),
        float(-.5-np.min((chi+chart.expand(step)).real))), 1e-8)


def run_backend_health(config, book, *, device="cpu"):
    """Run the single physical health fixture once, with every action charged."""
    checks, rng = _Checks(), np.random.default_rng(20261007)
    before = dict(book.counts)
    problem, fixture = tiny_problem(config)
    try:
        with book.span("a22_backend_health", backend_health_runs=1):
            anchor = build_anchor(problem, config, book, device=device)
            opm = build_opm(anchor, config)
            adapter, state, chi, projection = anchor.adapter, anchor.state, anchor.chi, opm.projection
            version_before_fd = adapter._version
            cached_before_fd = adapter._full_cache
            checks.condition("health_fixture_dimensions", adapter.P == 6 and adapter.m == 128
                             and adapter.p == 32 and adapter.model.N == 64,
                             physical_cells=adapter.model.N, complex_current_dimension=adapter.n,
                             real_material_dimension=adapter.p, sources=adapter.P,
                             complex_channels_per_source=adapter.m)
            checks.error("volume_material_metric", float(la.norm(
                problem.volume*problem.chart.Q.T@problem.chart.Q-np.eye(16))), 1e-10)
            checks.condition("no_projection_fallback", projection.kind == "galerkin"
                             and projection.fallback is None and opm.feedback.U.shape[1] == 8
                             and 8 <= opm.basis.shape[1] <= 32)
            _pack_checks(checks, rng)
            _noise_checks(checks, rng, anchor)

            v = rng.normal(size=32)
            v /= la.norm(v)
            with book.action_guard("full_J", role="offline_evaluation", purpose="health_derivative"):
                JF = adapter.full_tangent_action(chi, state, np.eye(32))
                w = rng.normal(size=adapter.P*2*adapter.m)
                gradient = adapter.full_adjoint_action(chi, state, w)
            checks.error("full_JVP_VJP_real_dot", _dot_error(
                float((JF@v)@w), float(v@gradient),
                max(la.norm(JF@v)*la.norm(w), la.norm(v)*la.norm(gradient))), 1e-9)
            h = 1e-5
            direction = adapter.chart.expand(v)
            plus = _health_forward(adapter, chi+h*direction, book)
            minus = _health_forward(adapter, chi-h*direction, book)
            finite_difference = adapter.whiten(pack((plus.field-minus.field)/(2.*h)))
            checks.error("full_material_central_FD", _relative(finite_difference, JF@v), 1e-5,
                         coefficient_step=h, perturbation_forwards=2)
            checks.condition("FD_preserves_anchor_operator_cache", adapter._version == version_before_fd
                             and adapter._full_cache is cached_before_fd
                             and np.array_equal(adapter._operator_chi, chi))
            projection.check()

            x = rng.normal(size=(adapter.n, 3))+1j*rng.normal(size=(adapter.n, 3))
            z = rng.normal(size=x.shape)+1j*rng.normal(size=x.shape)
            Lx, Lhz = adapter.apply_L(chi, x), adapter.apply_L_adjoint(chi, z)
            checks.error("L_complex_adjoint_dot", _dot_error(np.vdot(z, Lx), np.vdot(Lhz, x),
                         max(la.norm(z)*la.norm(Lx), la.norm(Lhz)*la.norm(x))), 1e-9)
            s = rng.normal(size=(adapter.m, 3))+1j*rng.normal(size=(adapter.m, 3))
            Sx, Shs = adapter.apply_S(x), adapter.apply_S_adjoint(s)
            checks.error("S_complex_adjoint_dot", _dot_error(np.vdot(s, Sx), np.vdot(Shs, x),
                         max(la.norm(s)*la.norm(Sx), la.norm(Shs)*la.norm(x))), 1e-9)
            material_directions = rng.normal(size=(32, 3))
            current_cotangent = rng.normal(size=(adapter.P, adapter.n, 3)) + 1j*rng.normal(size=(adapter.P, adapter.n, 3))
            Bd = adapter.apply_B(chi, state, material_directions)
            Bhy = adapter.apply_B_adjoint(chi, state, current_cotangent)
            checks.error("B_real_material_adjoint_dot", _dot_error(
                np.vdot(current_cotangent, Bd).real, np.vdot(Bhy, material_directions).real,
                max(la.norm(current_cotangent)*la.norm(Bd), la.norm(Bhy)*la.norm(material_directions))), 1e-9)

            B = adapter.apply_B(chi, state, np.eye(32)).transpose(1, 0, 2).reshape(adapter.n, adapter.P*32)
            RB = projection.apply(B)
            compressed = opm.MW.transpose(1, 0, 2).reshape(opm.basis.shape[1], adapter.P*32)
            checks.error("compressed_material_injection", _relative(compressed, opm.basis.conj().T@B), 1e-9)
            raw_reduced = adapter.apply_S(RB).reshape(adapter.m, adapter.P, 32).transpose(1, 0, 2)
            checks.error("material_factors_equal_action_product", _relative(adapter.whiten(pack(raw_reduced)), opm.AW), 1e-9)
            Rprobe = projection.apply(x)
            checks.error("RLR_equals_R", _relative(projection.apply(adapter.apply_L(chi, Rprobe)), Rprobe), 1e-9)

            V = opm.basis[:, opm.feedback.U.shape[1]:]
            checks.condition("nonempty_declared_Schur_complement", V.shape[1] > 0)
            effective_core = np.eye(V.shape[1])-V.conj().T@opm.feedback.F(V)
            effective_rhs = V.conj().T@opm.feedback.K(B)
            with book.span("a22_health_Schur_core", health_Schur_factorizations=1,
                           health_Schur_core_rhs=effective_rhs.shape[1]):
                schur_coeff = la.solve(effective_core, effective_rhs)
            direct = opm.feedback.R_U(B)
            via_schur = direct+opm.feedback.T(V)@schur_coeff
            checks.error("Schur_equals_full_Galerkin_retaining_direct_path", _relative(via_schur, RB), 1e-9,
                         retained_direct_norm=float(la.norm(direct)), retained_rank=8)

            injection_defect = B-adapter.apply_L(chi, RB)
            with book.action_guard("full_J", role="offline_evaluation", purpose="health_defect_identity"):
                with book.span("a22_health_full_defect_solve", health_reference_full_RHS=B.shape[1],
                               health_reference_backward_residual_L_rhs=B.shape[1]):
                    full_defect = adapter.model.solver.solve(
                        state._L_factor, injection_defect, label="full_health_defect")
                    solve_residual = _relative(adapter.apply_L(chi, full_defect), injection_defect)
            checks.error("full_defect_solve_backward_residual", solve_residual, 1e-9)
            two_sided_current = full_defect-projection.apply(adapter.apply_L(chi, full_defect))
            two_sided_raw = adapter.apply_S(two_sided_current).reshape(adapter.m, adapter.P, 32).transpose(1, 0, 2)
            two_sided_data = adapter.whiten(pack(two_sided_raw))
            checks.error("two_sided_defect_identity", _relative(JF-opm.AW, two_sided_data), 1e-9)
            checks.metric("full_J_vs_shallow_ROM_relative_error", _relative(JF, opm.AW),
                          label="descriptive finite-DDA tangent metric; no reconstruction accuracy gate")

            # A real orthogonal gauge changes coefficients and factors together.
            gauge, _ = la.qr(rng.normal(size=(32, 32)))
            gauged = material_features(opm, gauge)
            checks.error("material_gauge_product_covariance", _relative(gauged.AW, opm.AW@gauge), 1e-9)

            material_probe, measurement_probe, seed = _fixed_probes(opm.view, config)
            old_data = adapter.problem.data
            try:
                adapter.problem.data = rng.normal(size=old_data.shape)+1j*rng.normal(size=old_data.shape)
                repeated = build_opm(anchor, config)
                other_material, other_measurement, other_seed = _fixed_probes(repeated.view, config)
            finally:
                adapter.problem.data = old_data
            checks.error("fixed_O_probes_independent_of_observed_data", _relative(measurement_probe, other_measurement), 0., probe_seed=seed)
            checks.error("fixed_M_probes_independent_of_observed_data", _relative(material_probe, other_material), 0.)
            checks.condition("fixed_probe_seed_independent_of_data", seed == other_seed)
            checks.error("current_subspace_independent_of_observed_data", _relative(
                opm.basis@opm.basis.conj().T, repeated.basis@repeated.basis.conj().T), 1e-9)

            zero_basis, zero_info = orth(np.zeros((adapter.n, 4)), rtol=config["orthogonal_rank_rtol"])
            checks.condition("zero_seed_deflates_without_floor", zero_basis.shape[1] == 0
                             and zero_info["rank"] == 0 and zero_info["scale"] == 0.)
            checks.condition("zero_core_is_unsafe", not core_stability(np.zeros((8, 8)), 1., config)["safe"])
            bad_config = {**config, "core_relative_sigma_floor": 2.}
            rejected_projection = rejected_retained = False
            try:
                with book.span("a22_expected_projected_core_rejection", expected_invalid_core_probes=1):
                    Projection(adapter, chi, opm.basis, bad_config, allow_petrov=False)
            except UnsafeCore:
                rejected_projection = True
            try:
                with book.span("a22_expected_retained_core_rejection", expected_invalid_core_probes=1):
                    SchurFeedback(opm.view, opm.feedback.U, bad_config)
            except UnsafeCore:
                rejected_retained = True
            checks.condition("invalid_cores_propagate_without_fallback", rejected_projection and rejected_retained,
                             expected_unsafe_core_rejections=2, empty_U_fallback_used=False)
            checks.condition("no_Petrov_fallback_charged", book.counts.get("petrov_fallbacks", 0) == before.get("petrov_fallbacks", 0))

            for name in ("full_J", "full_H", "teacher", "truth", "full_state", "full_tangent_action", "full_adjoint_action"):
                try:
                    getattr(opm.view, name)
                except ForbiddenAccess:
                    denied = True
                else:
                    denied = False
                checks.condition("restricted_builder_denies_"+name, denied)

            old_whitening = adapter.whitening
            try:
                adapter.whitening = np.asarray(old_whitening)*1.01
                try:
                    material_features(opm)
                except ValueError as error:
                    white_rejected = "CACHE_CHANGED" in str(error)
                else:
                    white_rejected = False
            finally:
                adapter.whitening = old_whitening
            checks.condition("whitening_change_invalidates_factors", white_rejected)
            old_chi = anchor.chi
            try:
                anchor.chi = old_chi+1e-4
                try:
                    material_features(opm)
                except ValueError as error:
                    material_rejected = "CACHE_CHANGED" in str(error)
                else:
                    material_rejected = False
            finally:
                anchor.chi = old_chi
            checks.condition("anchor_material_change_invalidates_factors", material_rejected)
            _qp_check(checks, adapter.chart, chi, config, book)
            projection.check()
        return dict(status="PASS", checks=checks.rows, fixture=fixture,
                    rank=int(opm.basis.shape[1]), factor_shapes=dict(MW=list(opm.MW.shape),
                    PMW=list(opm.PMW.shape), AW=list(opm.AW.shape)),
                    anchor_provenance=dict(anchor.provenance),
                    count_delta={key: int(value-before.get(key, 0)) for key, value in book.counts.items()},
                    native_DDA=adapter.model.counters.as_dict(),
                    scientific_gates_adjudicated=False, expected_unsafe_core_rejections=2)
    except BaseException as error:
        if not hasattr(error, "health_checks"):
            error.health_checks = list(checks.rows)
        raise


_PROVIDED = (
    ("verify_theory", "OUT", "results.json"),
    ("verify_additional", "out", "additional_results.json"),
)


def _run_provided(root, book, *, output_directory=None):
    """Run unchanged supplied verifier entrypoints with output globals redirected."""
    root = Path(root)
    destination = (Path(output_directory) if output_directory is not None else root/"results/a22/validation")/"theory"
    rows = []
    for name, output_global, result_name in _PROVIDED:
        source = root/"protocol/a22/verification"/(name+".py")
        if not source.is_file():
            raise FileNotFoundError(source)
        output = destination/name
        output.mkdir(parents=True, exist_ok=False)
        original_result = source.parent/result_name
        original_bytes = original_result.read_bytes() if original_result.exists() else None
        module_name = "a22_supplied_"+name+"_"+uuid.uuid4().hex
        spec = importlib.util.spec_from_file_location(module_name, source)
        if spec is None or spec.loader is None:
            raise ImportError("Cannot load provided verifier "+str(source))
        module = importlib.util.module_from_spec(spec)
        stdout = io.StringIO()
        row = dict(name=name, source=str(source), output_directory=str(output),
                   execution_device="cpu", status="FAILED", original_protocol_result_preserved=False)
        try:
            sys.modules[module_name] = module
            # Supplied toy verifier has seven states, three sources, eight
            # material columns, and six FD/finite-amplitude perturbations.
            # These declared counts are charged conservatively before execution.
            counters = (dict(provided_toy_state_evaluations=7,
                             provided_toy_full_LU_factorizations=31,
                             provided_toy_forward_RHS=21,
                             provided_toy_material_RHS=168,
                             provided_toy_defect_RHS=24) if name == "verify_theory" else {})
            with book.action_guard("full_J", role="offline_evaluation", purpose="provided_theory_diagnostics"):
                with book.span("a22_provided_"+name, provided_verifier_runs=1, **counters):
                    with redirect_stdout(stdout):
                        spec.loader.exec_module(module)
                        setattr(module, output_global, output)
                        if name == "verify_theory":
                            with book.action_guard("perturbation_forward", role="offline_evaluation",
                                                   purpose="perturbation", F_calls=6):
                                module.main()
                        else:
                            module.main()
            result = json.loads((output/result_name).read_text(encoding="utf-8"))
            preserved = (original_result.read_bytes() if original_result.exists() else None) == original_bytes
            if not preserved:
                raise RuntimeError("PROVIDED_PROTOCOL_RESULT_WAS_MODIFIED")
            row.update(status="PASS", result_path=str(output/result_name), result=result,
                       original_protocol_result_preserved=True,
                       count_origin="source-static complete execution counts, conservatively prepaid")
            rows.append(row)
        except BaseException as error:
            row.update(error_type=type(error).__name__, error=str(error))
            rows.append(row)
            error.provided_theory_checks = rows
            raise
        finally:
            (output/"stdout.txt").write_text(stdout.getvalue(), encoding="utf-8")
            (output/"execution.json").write_text(json.dumps(_plain(row), indent=2, allow_nan=False), encoding="utf-8")
            sys.modules.pop(module_name, None)
    return rows


def run_validation(root, config, book, device="cpu") -> dict:
    """Execute and save health evidence; never finish the caller-owned ledger.

    Failure evidence is persisted before re-raising.  Existing validation output
    is refused so that a retry cannot conceal or overwrite its predecessor.
    """
    root = Path(root)
    directory = (root/"results/a22/validation_cuda"/book.job_id if device == "cuda"
                 else root/"results/a22/validation")
    if directory.exists():
        raise FileExistsError("A22_VALIDATION_OUTPUT_ALREADY_EXISTS:"+str(directory))
    before_counts = dict(book.counts)
    start_wall, start_cpu = time.perf_counter(), time.process_time()
    report = dict(schema="a22.validation.v1", status="FAILED", device=device,
                  source_freeze=config.get("source_freeze"),
                  scientific_gates_adjudicated=False,
                  claim="implementation health only; no continuum or recovery acceptance",
                  theory=[], backend=None)
    try:
        with book.scope("health"), book.action_guard("a22_validation", role="health", validation_runs=1):
            directory.mkdir(parents=True, exist_ok=False)
            report["theory"] = _run_provided(root, book, output_directory=directory)
            report["backend"] = run_backend_health(config, book, device=device)
            report["status"] = "PASS"
            return report
    except BaseException as error:
        report.update(error_type=type(error).__name__, error=str(error))
        if hasattr(error, "provided_theory_checks"):
            report["theory"] = error.provided_theory_checks
        if hasattr(error, "health_checks"):
            report["backend"] = dict(status="FAILED", checks=error.health_checks)
        raise
    finally:
        report.update(inclusive_wall_seconds=time.perf_counter()-start_wall,
                      controller_process_cpu_seconds=time.process_time()-start_cpu,
                      CPU_accounting="caller ledger includes child CPU and all nested work",
                      count_delta={key: int(value-before_counts.get(key, 0)) for key, value in book.counts.items()},
                      caller_book_finished=False)
        if directory.is_dir():
            (directory/"HEALTH.json").write_text(json.dumps(_plain(report), indent=2, allow_nan=False), encoding="utf-8")
