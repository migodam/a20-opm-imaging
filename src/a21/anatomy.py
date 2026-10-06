"""Five immutable late states, one shared cache each, then G before PG.

This driver never reads offline labels or evaluates truth.  The original A20
physics and constrained optimizer are imported unchanged.  Cached Petrov
execution only opens the small shared images, not a full Maxwell workspace.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import gc
import json
import time
import uuid

import numpy as np
from scipy import linalg as la

from a20.backend import Adapter, BasisView, MaterialChart, load_problem, unpack
from a20.costs import BudgetExceeded, plain, write_json
from a20.material import QPFailure, constraint_map, kkt, solve_quadratic
from a20.opm import FullJacobian, Hierarchy, Projection, SchurFeedback, UnsafeCore, build_seeds
from a20.replay import _load_state
from a20_r1.anatomy import _canonical_index, _canonical_provenance, _read_step, _resolve_step, _unique
from a20_r1.seeds import paired_probe_bank

from .core import (AnatomyInputError, CachedJacobian, MatrixJacobian,
                   RankBudgetInfeasible, SharedBank, baseline_basis,
                   independent_addition_rank, ordered_protected_basis, random_bank)
from .diagnostics import ConsistencyFailure, evaluate
from .validation import validate_case


PARENTS = (2001, 2005, 2003, 2007, 2013)
ITERATION = 17
ARMS_G = ("BASE_G", "PRIMAL_G", "DUAL_G", "BOTH_G", "RANDOM_G")
ARMS_PG = ("BOTH_PG", "RANDOM_PG")
ARMS = ARMS_G + ARMS_PG
CACHE_SCHEMA = "a21.frozen_shared_cache.v1"
SIGNATURE_KEYS = (
    "precision", "parents", "iterations", "validation_parents", "degree", "current_rank",
    "retained_rank", "seed_rank_O", "seed_rank_P", "seed_rank_M", "master_seed", "prior",
    "orthogonal_rank_rtol", "core_relative_sigma_floor", "core_absolute_scaled_sigma_floor",
    "core_condition_cap", "qp_kkt_rtol", "qp_maxiter", "feasibility_tolerance",
    "baseline_reproduction_rtol", "backend_consistency_rtol", "oracle_backward_rtol",
    "identity_rtol", "bound_roundoff_rtol", "normal_allowance_formula",
    "reference_H_norm_floor", "random_master_seed", "random_G_seed_suffix",
    "random_PG_trial_seed_suffix", "random_PG_test_seed_suffix", "source_freeze",
)


def _signature(config):
    return {key: plain(config[key]) for key in SIGNATURE_KEYS}


def _check_config(config):
    if (tuple(config["parents"]) != PARENTS or tuple(config["iterations"]) != (ITERATION,)
            or tuple(config["validation_parents"]) != (PARENTS[0], PARENTS[2], PARENTS[-1])
            or tuple(config["arms_G"]) != ARMS_G or tuple(config["arms_PG"]) != ARMS_PG
            or config["current_rank"] != 56 or config["retained_rank"] != 8
            or config["degree"] != 3 or config["maximum_reduced_qps"] != 35
            or config.get("allow_petrov_fallback") or config.get("allow_full_fallback")
            or config["precision"] != "complex128/float64"):
        raise AnatomyInputError("A21_FROZEN_SCOPE_OR_NO_FALLBACK_CONTRACT_CHANGED")
    _signature(config)


def _snapshot(book):
    # Final failure persistence must remain possible after the budget check
    # rejects further scientific work.
    return {"counts": dict(book.counts), "walls": dict(book.walls)}


def _cost_delta(book, old, started):
    return {"counts": {k: int(v - old["counts"].get(k, 0)) for k, v in book.counts.items()
                       if v != old["counts"].get(k, 0)},
            "exclusive_walls": {k: float(v - old["walls"].get(k, 0.)) for k, v in book.walls.items()
                                if v != old["walls"].get(k, 0.)},
            "inclusive_wall_seconds": time.perf_counter() - started[0],
            "process_cpu_seconds": time.process_time() - started[1]}


def _save_npz(path, arrays):
    """Write once, atomically, without charging avoidable compression CPU."""
    path = Path(path)
    if path.exists():
        raise AnatomyInputError("IMMUTABLE_ARRAY_OUTPUT_ALREADY_EXISTS:" + str(path))
    temporary = path.with_suffix(path.suffix + ".tmp")
    if temporary.exists():
        raise AnatomyInputError("PARTIAL_ARRAY_OUTPUT_REQUIRES_INSPECTION:" + str(temporary))
    with temporary.open("xb") as handle:
        np.savez(handle, **arrays)
    temporary.replace(path)


def _enrich_audit(chart, x, step, gradient, config):
    audit = kkt(chart, x, step, gradient, tolerance=config["feasibility_tolerance"])
    A, lower = constraint_map(chart, x)
    values = step if A is None else A @ step
    audit["slack"] = values - lower
    audit["active_indices"] = np.flatnonzero(audit["slack"] <= config["feasibility_tolerance"])
    audit["complementarity_L1"] = float(np.sum(np.abs(audit["multipliers"] * audit["slack"])))
    return audit


def _residual_report(image, forcing):
    residual = image - forcing
    source_abs = la.norm(residual, axis=0)
    source_den = la.norm(forcing, axis=0)
    total_abs, total_den = float(la.norm(residual)), float(la.norm(forcing))
    relative = [float(a / d) if d > 0 else (0. if a == 0 else None)
                for a, d in zip(source_abs, source_den)]
    return {"absolute": total_abs, "forcing_norm": total_den,
            "relative": total_abs / total_den if total_den > 0 else (0. if total_abs == 0 else None),
            "per_source_absolute": source_abs.tolist(), "per_source_forcing_norm": source_den.tolist(),
            "per_source_relative": relative}


def _check_backward(report, tolerance, label):
    values = [report["relative"]] + report["per_source_relative"]
    if any(value is None or value > tolerance for value in values):
        error = ConsistencyFailure(label + "_ORACLE_BACKWARD_ERROR")
        error.details = report
        raise error


def _random_bank(n, columns, config, pid, suffix):
    seed = [int(config["random_master_seed"]), int(pid), ITERATION, int(suffix)]
    return random_bank(n, columns, seed), seed


def _case_metadata(parent, reference, baseline, reference_path, baseline_path, config):
    return {"schema": CACHE_SCHEMA, "parent_id": int(parent["parent_id"]), "iteration": ITERATION,
            "runtime_problem": parent["runtime_problem"],
            "runtime_state": next(s["runtime_path"] for s in parent["states"] if s["iteration"] == ITERATION),
            "canonical_reference_row_id": reference["row_id"],
            "canonical_reference_recorded_path": reference["reference_step_path"],
            "canonical_reference_local_path": str(reference_path),
            "canonical_reference_backend_commit": reference["backend_commit"],
            "canonical_baseline_row_id": baseline["row_id"],
            "canonical_baseline_recorded_path": baseline["step_path"],
            "canonical_baseline_local_path": str(baseline_path),
            "canonical_baseline_backend_commit": baseline["backend_commit"],
            "canonical_baseline_definition": "original mixed O4/P4/M4 degree3",
            "reconstructed_baseline_definition": "R1 direct receiver U8 O4/P4/M4 degree3 previous=None",
            "retained_gauge_difference_disclosed": True,
            "reference_raw_constrained_QP_step": True, "line_search_scaling": None,
            "truth_or_labels_read": False, "dataset_exposure": "historically_exposed_feasibility",
            "config_signature": _signature(config), "config_source_freeze": config["source_freeze"]}


def prepare_case(root, parent, config, book):
    """Prepare one live frozen state; caller validates and then discards it."""
    root, pid = Path(root), int(parent["parent_id"])
    started, old = (time.perf_counter(), time.process_time()), _snapshot(book)
    canonical = root / "results/replay/replay.jsonl"
    index = _canonical_index(canonical)
    _, saved_reference = _unique(index, pid, ITERATION, "reference")
    _, saved_baseline = _unique(index, pid, ITERATION, "baseline")
    for row in (saved_reference, saved_baseline):
        _canonical_provenance(row, parent, ITERATION, config)
        if row.get("status") != "OK":
            raise AnatomyInputError("CANONICAL_REFERENCE_OR_BASELINE_NOT_OK")
    if (not str(saved_reference.get("reference_status", "")).startswith("VERIFIED_")
            or saved_baseline.get("projection_kind") != "galerkin"
            or saved_baseline.get("projection_fallback") or saved_baseline.get("retained_fallback")
            or saved_baseline.get("fullfallback_used") or saved_baseline.get("rank") != config["current_rank"]
            or saved_baseline.get("seed_budgets") != {"O": 4, "P": 4, "M": 4}
            or saved_baseline.get("seed_rng") != [config["master_seed"], pid]):
        raise AnatomyInputError("CANONICAL_BASELINE_PROJECTION_OR_SEED_CONFLICT")
    reference_path = _resolve_step(canonical, saved_reference["reference_step_path"])
    baseline_path = _resolve_step(canonical, saved_baseline["step_path"])
    metadata = _case_metadata(parent, saved_reference, saved_baseline, reference_path, baseline_path, config)
    metadata.update(engine_source_commit=book.metadata.get("source_commit"), preparation_job=book.metadata.get("job"),
                    device=book.device, retained_fallback=None, projection_fallback=None,
                    unsafe_core_fallback_attempted=False)
    with book.scope("offline_reference"):
        problem = load_problem(root / parent["runtime_problem"])
        if problem.parent_id != pid or problem.chart.kind != "gaussian" or problem.chart.Q is None:
            raise AnatomyInputError("FROZEN_GAUSSIAN_PROBLEM_IDENTITY_MISMATCH")
        adapter = Adapter(problem, device=book.device, book=book)
        if (adapter.n != parent["n_current"] or adapter.p != parent["p_material"]
                or adapter.P != 6 or adapter.m != 128 or adapter.p != 54):
            raise AnatomyInputError("FROZEN_SIX_SOURCE_LAYOUT_OR_COORDINATE_MISMATCH")
        x, lam, ell = _load_state(root, parent, ITERATION, adapter.chart)
        state = adapter.full_state(x, reuse=True)  # exactly one full state/LU
        r = adapter.residual(state)
        full_jacobian = FullJacobian(adapter, x, state)
        JF = full_jacobian.small_matrix().copy()  # one 6*54 RHS batch
        sF = _read_step(reference_path, adapter.p)
        baseline_s = _read_step(baseline_path, adapter.p)
        gradient0 = JF.T @ r + ell
        auditF = _enrich_audit(adapter.chart, x, sF, JF.T @ (r + JF @ sF) + lam * sF + ell, config)
        relative = auditF["stationarity_norm"] / max(float(la.norm(gradient0)), np.finfo(float).tiny)
        metadata["reference_repaired"] = False
        if relative > config["qp_kkt_rtol"] or auditF["violation"] > config["feasibility_tolerance"]:
            if not config.get("reference_repair_allowed_same_quadratic"):
                raise AnatomyInputError("FULL_REFERENCE_KKT_INVALID_REPAIR_DISABLED")
            original = sF.copy()
            with book.span("a21_same_frozen_reference_repair", reference_repair_qps=1):
                sF, qp, _ = solve_quadratic(adapter.chart, x, r, MatrixJacobian(JF), lam, ell, config, book)
            auditF = _enrich_audit(adapter.chart, x, sF, JF.T @ (r + JF @ sF) + lam * sF + ell, config)
            relative = auditF["stationarity_norm"] / max(float(la.norm(gradient0)), np.finfo(float).tiny)
            metadata.update(reference_repaired=True, reference_repair_QP=qp,
                            reference_repair_absolute_step_difference=float(la.norm(sF-original)))
        if relative > config["qp_kkt_rtol"] or auditF["violation"] > config["feasibility_tolerance"]:
            error = ConsistencyFailure("FULL_REFERENCE_CONSTRAINED_KKT_INVALID")
            error.details = {"KKT_relative": relative, "violation": auditF["violation"]}
            error.vectors = {"x": x, "Q": adapter.chart.Q, "JF": JF, "r": r, "sF": sF, "ell": ell,
                             "lam": lam, "normalF": auditF["normal"], "multipliersF": auditF["multipliers"],
                             "slackF": auditF["slack"]}
            raise error
        ell_expected = config["prior"] * adapter.chart.project(x - problem.init)
        ell_error = float(la.norm(ell - ell_expected))
        ell_scale = float(la.norm(ell_expected))
        if ell_error > (config["backend_consistency_rtol"] * ell_scale if ell_scale else 1e-12):
            raise AnatomyInputError("FROZEN_ELL_MATERIAL_SCALING_MISMATCH")
        metadata.update(reference_KKT_relative=relative, reference_active_constraints=int(auditF["active_constraints"]),
                        material_dimension=adapter.p, current_dimension=adapter.n, cells=adapter.chart.n,
                        source_count=adapter.P, complex_channels_per_source=adapter.m, real_measurements=r.size,
                        lambda_total=lam, ell_prior_gradient_absolute_error=ell_error,
                        oracle_precision="complex128", material_precision="float64")

    # This is the R1 baseline path, including its direct receiver-U gauge.  Use
    # the immutable seed/hierarchy code but explicitly forbid projection rescue.
    with book.scope("offline_baseline_reproduction"):
        view = BasisView(adapter, x, state, r, previous=None)
        # Exact direct R1 receiver gauge, with no construction of its legacy
        # empty-U rescue even on a failed retained core.
        with book.span("a21_retained_schur_setup", retained_setups=1):
            schur = SchurFeedback(view, view.receiver(config["retained_rank"]), config)
        if schur.U.shape[1] != config["retained_rank"]:
            raise AnatomyInputError("A21_RETAINED_RANK_MISMATCH")
        bank = paired_probe_bank(view, config)
        observation = bank.measurement_probes[:, :4].copy()
        observation[:, 0] = r
        seeds = build_seeds(view, schur, config, budgets={"O": 4, "P": 4, "M": 4},
                            material_probes=bank.material_probes[:, :4].copy(), measurement_probes=observation)
        hierarchy = Hierarchy(view, schur, seeds, config)
        baseline, baseline_info = hierarchy.at_degree(config["degree"])
        if baseline.shape[1] != config["current_rank"]:
            raise RankBudgetInfeasible("FROZEN_BASELINE_ACTUAL_RANK_DIFFERS_FROM_56")
        if baseline_info["degree_layers"] != saved_baseline.get("degree_layers"):
            raise AnatomyInputError("FROZEN_BASELINE_DEGREE_PRIORITY_MISMATCH")
        baseline_projection = Projection(adapter, x, baseline, config, allow_petrov=False)
        U = schur.U.copy()
        priority = np.asarray(sorted(range(U.shape[1], baseline.shape[1]),
            key=lambda i: (baseline_info["degree_layers"][i-U.shape[1]], i)), dtype=np.int64)
        metadata.update(baseline_info=baseline_info, baseline_seed_rng=list(bank.rng_seed),
                        baseline_projection="galerkin", baseline_retained_rank=U.shape[1],
                        baseline_core=baseline_projection.stability,
                        baseline_priority="earlier degree followed by reconstructed stored column index")

    with book.scope("offline_oracle"):
        primal_forcing = adapter.apply_B(x, state, sF).T
        eF = r + JF @ sF
        dual_data = unpack(adapter.whiten(eF, adjoint=True), adapter.P, adapter.m)
        dual_forcing = adapter.apply_S_adjoint(dual_data.T)
        with book.span("a21_full_oracle_primal", full_oracle_RHS=adapter.P,
                       full_oracle_primal_RHS=adapter.P, full_oracle_primal_solve_calls=1):
            X = state.model.solver.solve(state._L_factor, primal_forcing, trans=0, label="full_oracle_primal")
        with book.span("a21_full_oracle_adjoint", full_oracle_RHS=adapter.P,
                       full_oracle_adjoint_RHS=adapter.P, full_oracle_adjoint_solve_calls=1):
            Y = state.model.solver.solve(state._L_factor, dual_forcing, trans=2, label="full_oracle_adjoint")
        LX, LHY = adapter.apply_L(x, X), adapter.apply_L_adjoint(x, Y)
        primal_backward, dual_backward = _residual_report(LX, primal_forcing), _residual_report(LHY, dual_forcing)
        try:
            _check_backward(primal_backward, config["oracle_backward_rtol"], "PRIMAL")
            _check_backward(dual_backward, config["oracle_backward_rtol"], "DUAL")
        except ConsistencyFailure as error:
            error.vectors = {"X": X, "Y": Y, "LX": LX, "LHY": LHY,
                             "primal_forcing": primal_forcing, "dual_forcing": dual_forcing,
                             "JF": JF, "r": r, "sF": sF, "x": x, "ell": ell, "lam": lam}
            raise
        metadata.update(primal_oracle_backward=primal_backward, dual_oracle_backward=dual_backward,
                        full_oracle_unique_RHS=2*adapter.P,
                        full_oracle_rhs_accounting="CostBook aggregate only; native counters are the same solves, not additional RHS")

    with book.scope("offline_shared_bank"):
        rtol = config["orthogonal_rank_rtol"]
        rank_X = independent_addition_rank(U, X, rtol)
        rank_Y = independent_addition_rank(U, Y, rtol)
        rank_XY = independent_addition_rank(U, np.column_stack((X, Y)), rtol)
        RG, seed_G = _random_bank(adapter.n, rank_XY, config, pid, config["random_G_seed_suffix"])
        RZ, seed_Z = _random_bank(adapter.n, rank_X, config, pid, config["random_PG_trial_seed_suffix"])
        RW, seed_W = _random_bank(adapter.n, rank_Y, config, pid, config["random_PG_test_seed_suffix"])
        for label, random, expected in (("G", RG, rank_XY), ("PG_trial", RZ, rank_X), ("PG_test", RW, rank_Y)):
            if independent_addition_rank(U, random, rtol) != expected:
                raise RankBudgetInfeasible("FROZEN_RANDOM_BANK_INDEPENDENT_RANK_MISMATCH:"+label)
        blocks = [("baseline", baseline), ("X", X), ("Y", Y), ("randomG", RG),
                  ("randomPG_trial", RZ), ("randomPG_test", RW)]
        groups, start = {}, 0
        for name, block in blocks:
            groups[name] = list(range(start, start+block.shape[1]))
            start += block.shape[1]
        groups["U"] = list(range(U.shape[1]))
        D = np.column_stack([block for _, block in blocks])
        # Reuse the baseline image and the measured primal solve image.  The
        # common-space dual columns need L Y, in addition to their L* residual.
        LY = adapter.apply_L(x, Y)
        random_all = np.column_stack((RG, RZ, RW))
        Lrandom = adapter.apply_L(x, random_all) if random_all.shape[1] else random_all.copy()
        LD = np.column_stack((baseline_projection.LZ, LX, LY, Lrandom))
        added = D[:, baseline.shape[1]:]
        Sadded = adapter.apply_S(added) if added.shape[1] else np.empty((adapter.m, 0), complex)
        SD = np.column_stack((baseline_projection.SZ, Sadded))
        DHB = adapter.compressed_B(x, state, D)
        shared = SharedBank(D, LD, SD, DHB, adapter.whitening, float(la.norm(state.L)),
                            pid, ITERATION, adapter.P, adapter.m)
        illumination_forcing = adapter.forcing(x)
        A, lower = constraint_map(adapter.chart, x)
        metadata.update(groups=groups, oracle_independent_added_ranks={"X": rank_X, "Y": rank_Y, "XY": rank_XY},
                        random_seeds={"G": seed_G, "PG_trial": seed_Z, "PG_test": seed_W},
                        random_matching="actual independent additions relative to retained U",
                        shared_bank_columns=D.shape[1], shared_image_scope="all G/PG arms use the same D/LD/SD/DHB",
                        operator_images_use_measured_LX=True, no_oracle_residual_erased=True)
    metadata["preparation_cost"] = _cost_delta(book, old, started)
    return {"adapter": adapter, "x": x, "state": state, "JF": JF, "r": r, "sF": sF,
            "lam": lam, "ell": ell, "auditF": auditF, "A": A, "lower": lower,
            "X": X, "Y": Y, "LX": LX, "LHY": LHY, "primal_forcing": primal_forcing,
            "dual_forcing": dual_forcing, "forcing": illumination_forcing, "U": U,
            "baseline": baseline, "baseline_LZ": baseline_projection.LZ,
            "baseline_projection": baseline_projection, "baseline_s": baseline_s,
            "priority": priority, "groups": groups, "bank": shared, "metadata": metadata,
            "randomG": RG, "randomPG_trial": RZ, "randomPG_test": RW, "chart": adapter.chart,
            "config": config}


def _save_case(case, directory, book):
    pid = case["metadata"]["parent_id"]
    path = directory / "caches" / f"{pid}_{ITERATION}.npz"
    adapter, state, bank = case["adapter"], case["state"], case["bank"]
    arrays = {key: case[key] for key in ("x", "JF", "r", "sF", "ell", "X", "Y", "LX", "LHY",
        "primal_forcing", "dual_forcing", "forcing", "U", "baseline", "baseline_LZ", "baseline_s",
        "priority", "randomG", "randomPG_trial", "randomPG_test", "A", "lower")}
    arrays.update(Q=adapter.chart.Q, volume=adapter.chart.volume, kind=adapter.chart.kind,
                  points=adapter.problem.points, init=adapter.problem.init, dirs=adapter.problem.dirs,
                  pols=adapter.problem.pols, receivers=adapter.problem.receivers,
                  obs_basis=adapter.problem.obs_basis, frequency=adapter.problem.frequency,
                  data0=adapter.problem.data, scale=adapter.problem.scale, whitening=adapter.whitening,
                  B_factor=adapter.injection_factor(case["x"], state),
                  lam=case["lam"], Lambda=case["lam"]*np.eye(adapter.p),
                  HF=case["JF"].T@case["JF"]+case["lam"]*np.eye(adapter.p),
                  normalF=case["auditF"]["normal"], multipliersF=case["auditF"]["multipliers"],
                  slackF=case["auditF"]["slack"], active_indicesF=case["auditF"]["active_indices"],
                  D=bank.D, LD=bank.LD, SD=bank.SD, DHB=bank.DHB, DHDL=bank.DHDL,
                  L_scale=bank.L_scale, parent_id=pid, iteration=ITERATION,
                  source_count=adapter.P, data_channels=adapter.m,
                  config_signature=json.dumps(_signature(case["config"]), sort_keys=True))
    started, old = (time.perf_counter(), time.process_time()), _snapshot(book)
    with book.span("a21_shared_cache_save", shared_cache_writes=1,
                   shared_cache_input_bytes=sum(np.asarray(v).nbytes for v in arrays.values())):
        _save_npz(path, arrays)
    metadata = dict(case["metadata"], cache_path=str(path), cache_bytes=path.stat().st_size,
                    cache_compression="none", immutable_write_once=True,
                    dense_L_persisted=False, raw_S_persisted=False,
                    L_identity="frozen runtime problem/state plus declared source commit; same live L for all paid images",
                    L_images_and_scale_persisted=True, cache_write_cost=_cost_delta(book, old, started))
    write_json(path.with_suffix(".json"), metadata)
    return metadata


def load_cached_case(path, config):
    """Load small shared caches; no full L, LU, or Maxwell workspace exists here."""
    path = Path(path)
    metadata = json.loads(path.with_suffix(".json").read_text())
    if metadata.get("schema") != CACHE_SCHEMA or metadata.get("config_signature") != _signature(config):
        raise AnatomyInputError("FROZEN_CACHE_CONFIG_OR_SCHEMA_MISMATCH")
    pid = int(metadata["parent_id"])
    if pid not in PARENTS or metadata.get("iteration") != ITERATION:
        raise AnatomyInputError("FROZEN_CACHE_STATE_IDENTITY_MISMATCH")
    required = ("x", "Q", "volume", "kind", "JF", "r", "sF", "lam", "ell", "A", "lower",
                "X", "Y", "U", "baseline", "baseline_s", "priority", "normalF", "multipliersF", "slackF",
                "active_indicesF", "D", "LD", "SD", "DHB", "whitening", "L_scale", "parent_id",
                "iteration", "source_count", "data_channels", "config_signature")
    with np.load(path, allow_pickle=False) as data:
        if any(key not in data.files for key in required):
            raise AnatomyInputError("FROZEN_CACHE_MISSING_REQUIRED_ARRAY")
        arrays = {key: data[key].copy() for key in required}
    if (int(arrays["parent_id"]) != pid or int(arrays["iteration"]) != ITERATION
            or json.loads(str(arrays["config_signature"])) != _signature(config)):
        raise AnatomyInputError("FROZEN_CACHE_ARRAY_METADATA_IDENTITY_MISMATCH")
    chart = MaterialChart(float(arrays["volume"]), len(arrays["x"]), arrays["Q"], str(arrays["kind"]))
    if (chart.kind != "gaussian" or chart.d != 54 or chart.n != 1728
            or la.norm(chart.volume*chart.Q.T@chart.Q-np.eye(chart.q)) > 1e-10
            or arrays["JF"].shape != (1536, 54) or arrays["r"].shape != (1536,)
            or arrays["sF"].shape != (54,) or arrays["ell"].shape != (54,)
            or int(arrays["source_count"]) != 6 or int(arrays["data_channels"]) != 128):
        raise AnatomyInputError("FROZEN_CACHE_REAL_COORDINATE_OR_SOURCE_LAYOUT_MISMATCH")
    for key in ("JF", "r", "sF", "ell", "A", "lower", "normalF", "multipliersF", "slackF"):
        if np.iscomplexobj(arrays[key]) or not np.all(np.isfinite(arrays[key])):
            raise AnatomyInputError("FROZEN_CACHE_REQUIRES_FINITE_REAL_MATERIAL_ARRAY:"+key)
    A, lower = constraint_map(chart, arrays["x"])
    if not np.array_equal(A, arrays["A"]) or not np.array_equal(lower, arrays["lower"]):
        raise AnatomyInputError("FROZEN_CACHE_CONSTRAINT_PARAMETERIZATION_MISMATCH")
    lam = float(arrays["lam"])
    if lam <= 0 or not np.isfinite(lam):
        raise AnatomyInputError("FROZEN_CACHE_INVALID_LM_REGULARIZER")
    # The full normal is frozen with the reference. Never recover a new NNLS
    # normal merely because another stage opened the same cache.
    gradientF = arrays["JF"].T@(arrays["r"]+arrays["JF"]@arrays["sF"])+lam*arrays["sF"]+arrays["ell"]
    actual_slack = A@arrays["sF"]-lower
    normal_error = float(la.norm(arrays["normalF"]+A.T@arrays["multipliersF"]))
    slack_error = float(la.norm(actual_slack-arrays["slackF"]))
    numerical_allowance = 100*np.finfo(float).eps*max(1.,float(la.norm(actual_slack)),float(la.norm(arrays["normalF"])))
    if normal_error > numerical_allowance or slack_error > numerical_allowance or np.min(arrays["multipliersF"]) < 0:
        raise AnatomyInputError("FROZEN_CACHE_NORMAL_OR_SLACK_REPRESENTATION_INVALID")
    defectF = gradientF+arrays["normalF"]
    auditF = {"normal": arrays["normalF"], "multipliers": arrays["multipliersF"], "slack": arrays["slackF"],
              "active_indices": arrays["active_indicesF"], "defect": defectF,
              "stationarity_norm": float(la.norm(defectF)),
              "violation": max(0.,float(-np.min(actual_slack))),
              "dual_violation": max(0.,float(-np.min(arrays["multipliersF"]))),
              "complementarity": float(np.max(np.abs(arrays["multipliersF"]*actual_slack))),
              "complementarity_L1": float(np.sum(np.abs(arrays["multipliersF"]*actual_slack))),
              "active_constraints": len(arrays["active_indicesF"])}
    relativeF = auditF["stationarity_norm"]/max(float(la.norm(arrays["JF"].T@arrays["r"]+arrays["ell"])),np.finfo(float).tiny)
    if relativeF > config["qp_kkt_rtol"] or auditF["violation"] > config["feasibility_tolerance"]:
        raise AnatomyInputError("FROZEN_CACHE_FULL_REFERENCE_KKT_INVALID")
    bank = SharedBank(arrays["D"], arrays["LD"], arrays["SD"], arrays["DHB"], arrays["whitening"],
                      float(arrays["L_scale"]), pid, ITERATION, 6, 128)
    if (bank.D.shape[0] != 5184 or bank.material_dimension != 54
            or arrays["baseline"].shape != (5184, 56)
            or arrays["U"].shape != (5184, 8)
            or not np.array_equal(bank.D[:, metadata["groups"]["baseline"]], arrays["baseline"])
            or not np.array_equal(arrays["baseline"][:, :8], arrays["U"])):
        raise AnatomyInputError("FROZEN_CACHE_BASIS_OR_CURRENT_IDENTITY_MISMATCH")
    groups = metadata["groups"]
    grouped = [i for label in ("baseline","X","Y","randomG","randomPG_trial","randomPG_test") for i in groups[label]]
    if (grouped != list(range(bank.D.shape[1])) or groups["U"] != list(range(8))
            or len(groups["X"]) != 6 or len(groups["Y"]) != 6
            or not np.array_equal(bank.D[:,groups["X"]],arrays["X"])
            or not np.array_equal(bank.D[:,groups["Y"]],arrays["Y"])):
        raise AnatomyInputError("FROZEN_CACHE_RAW_BANK_SOURCE_MAPPING_MISMATCH")
    expected_priority = sorted(range(8,56),key=lambda i:(metadata["baseline_info"]["degree_layers"][i-8],i))
    if arrays["priority"].tolist() != expected_priority:
        raise AnatomyInputError("FROZEN_CACHE_BASELINE_DEGREE_COLUMN_PRIORITY_MISMATCH")
    return {**arrays, "lam": lam, "chart": chart, "auditF": auditF, "bank": bank,
            "metadata": metadata, "groups": metadata["groups"], "config": config, "cache_path": str(path)}


def _capture(current, basis, config):
    norms = la.norm(current, axis=0)
    errors = la.norm(current-basis@(basis.conj().T@current), axis=0)
    aggregate_norm = float(la.norm(current))
    aggregate_error = float(la.norm(current-basis@(basis.conj().T@current)))
    resolution = config["endpoint_denominator_epsilon_multiplier"]*np.finfo(float).eps*aggregate_norm
    return {"aggregate_absolute_residual": aggregate_error, "aggregate_current_norm": aggregate_norm,
            "aggregate_relative_residual": aggregate_error/aggregate_norm if aggregate_norm > resolution else None,
            "per_source_absolute_residual": errors.tolist(), "per_source_current_norm": norms.tolist(),
            "per_source_relative_residual": [float(e/n) if n > resolution else None for e,n in zip(errors,norms)],
            "per_source_defined": [bool(n > resolution) for n in norms], "denominator_resolution": resolution}


def _bases(case, arm, config):
    bank, groups = case["bank"], case["groups"]
    U, filler, rank, rtol = groups["U"], case["priority"].tolist(), config["current_rank"], config["orthogonal_rank_rtol"]
    if arm == "BASE_G":
        trial = baseline_basis(bank, groups["baseline"], len(U))
        return trial, trial
    if arm in ARMS_G:
        additions = {"PRIMAL_G": groups["X"], "DUAL_G": groups["Y"],
                     "BOTH_G": groups["X"]+groups["Y"], "RANDOM_G": groups["randomG"]}[arm]
        trial = ordered_protected_basis(bank.D, U+additions, filler, rank, rtol, len(U))
        return trial, trial
    additions_Z = groups["X"] if arm == "BOTH_PG" else groups["randomPG_trial"]
    additions_W = groups["Y"] if arm == "BOTH_PG" else groups["randomPG_test"]
    return (ordered_protected_basis(bank.D, U+additions_Z, filler, rank, rtol, len(U)),
            ordered_protected_basis(bank.D, U+additions_W, filler, rank, rtol, len(U)))


def _tied_checks(jacobian, JR, config):
    p, m = JR.shape[1], JR.shape[0]
    d, w = np.sin(np.arange(p)+1.), np.cos(np.arange(m)+.5)
    action, pulled = jacobian.action(d), jacobian.pullback(w)
    tiny = np.finfo(float).tiny
    action_error = float(la.norm(action-JR@d)/max(float(la.norm(action)), float(la.norm(JR@d)), tiny))
    pullback_error = float(la.norm(pulled-JR.T@w)/max(float(la.norm(pulled)), float(la.norm(JR.T@w)), tiny))
    scale = max(float(la.norm(w)*la.norm(action)), float(la.norm(d)*la.norm(pulled)), tiny)
    dot_error = float(abs(w@action-d@pulled)/scale)
    record = {"action_matrix_relative_error": action_error, "pullback_matrix_relative_error": pullback_error,
              "tied_adjoint_relative_error": dot_error, "shared_forward_adjoint_LU": True,
              "validation_vectors": "fixed sine material and cosine real-data vectors, independent of outcomes"}
    if max(action_error, pullback_error, dot_error) > config["backend_consistency_rtol"]:
        error = ConsistencyFailure("CACHED_CORE_TIED_ADJOINT_OR_ASSEMBLY_FAILED")
        error.details = record
        raise error
    return record


def _base_record(pid, arm, job, run_id):
    return {"schema": "a21.oracle_arm.v1", "parent_id": pid, "parent_object_id": pid,
            "iteration": ITERATION, "arm": arm, "method": arm, "job": job, "run_id": run_id,
            "status": "NOT_RUN", "consistency_passed": False, "QP_valid": False,
            "reference_valid": False,
            "offline_oracle_only": True, "truth_or_labels_read": False,
            "full_fallback_used": False, "projection_fallback": None,
            "dataset_exposure": "historically_exposed_feasibility"}


def evaluate_arm(case, arm, config, book, directory, job, run_id):
    pid = case["metadata"]["parent_id"]
    record = _base_record(pid, arm, job, run_id)
    record["cache_path"] = case["cache_path"]
    started, old = (time.perf_counter(), time.process_time()), _snapshot(book)
    vectors = {"sF": case["sF"], "normalF": case["auditF"]["normal"],
               "multipliersF": case["auditF"]["multipliers"], "slackF": case["auditF"]["slack"]}
    failure = None
    try:
        with book.span("a21_arm_protected_QR", protected_basis_constructions=1):
            trial, test = _bases(case, arm, config)
        record.update(trial_QR=trial.metadata, test_QR=test.metadata,
                      k_Z=trial.Z.shape[1], k_W=test.Z.shape[1], retained_rank=len(case["groups"]["U"]),
                      current_basis_memory_bytes=trial.Z.nbytes if trial is test else trial.Z.nbytes+test.Z.nbytes,
                      coordinate_transform_memory_bytes=trial.T.nbytes if trial is test else trial.T.nbytes+test.T.nbytes)
        accepted_trial = set(trial.metadata["accepted_source_indices"])
        accepted_test = set(test.metadata["accepted_source_indices"])
        record.update(primal_protected_added_rank=len(accepted_trial & set(case["groups"]["X"])),
                      dual_protected_added_rank=len(accepted_test & set(case["groups"]["Y"])),
                      random_protected_added_rank=len(accepted_trial & set(case["groups"]["randomG"])))
        vectors.update(Z=trial.Z, W=test.Z, TZ=trial.T, TW=test.T)
        sv_union = la.svdvals(np.column_stack((trial.Z, test.Z)))
        union_threshold = config["orthogonal_rank_rtol"]*max(float(sv_union[0]),
            float(la.norm(np.column_stack((trial.Z, test.Z)))))
        record["union_rank"] = int(np.count_nonzero(sv_union > union_threshold))
        projection = case["bank"].project(trial, test, config, book)
        record.update(core=projection.stability, core_singular_values=projection.singular_values.tolist(),
                      projection_kind=projection.kind, no_shift_or_pseudoinverse=True)
        vectors["core"] = projection.A
        jacobian = CachedJacobian(case["bank"], projection, book)
        JR = jacobian.matrix()
        vectors["JR"] = JR
        record.update(_tied_checks(jacobian, JR, config))
        record.update(core_primal_solve_backward_residual=projection.max_primal_solve_backward_residual,
                      core_adjoint_solve_backward_residual=projection.max_adjoint_solve_backward_residual,
                      core_solve_residual_records=projection.solve_residual_records)
        with book.span("a21_arm_constrained_QP", a21_reduced_qps=1):
            sR, qp, _ = solve_quadratic(case["chart"], case["x"], case["r"], jacobian,
                                       case["lam"], case["ell"], config, book)
        auditR = _enrich_audit(case["chart"], case["x"], sR,
            JR.T@(case["r"]+JR@sR)+case["lam"]*sR+case["ell"], config)
        vectors.update(sR=sR, normalR=auditR["normal"], multipliersR=auditR["multipliers"],
                       slackR=auditR["slack"], active_indicesR=auditR["active_indices"])
        record.update(QP=qp, QP_valid=True, reduced_active_constraints=int(auditR["active_constraints"]))
        if arm == "BASE_G":
            denominator = float(la.norm(case["baseline_s"]))
            difference = float(la.norm(sR-case["baseline_s"]))
            relative = difference/denominator if denominator else (0. if difference == 0 else None)
            record.update(baseline_step_relative_error=relative, baseline_step_absolute_error=difference,
                          baseline_reproduction_rtol=config["baseline_reproduction_rtol"],
                          baseline_gauge_preserved=True)
            if relative is None or relative > config["baseline_reproduction_rtol"]:
                error = AnatomyInputError("FIXED_BASELINE_RAW_STEP_REPRODUCTION_CONFLICT")
                error.details = {"relative_error": relative, "absolute_error": difference,
                                 "frozen_tolerance": config["baseline_reproduction_rtol"]}
                raise error
        with book.span("a21_arm_real_material_diagnostics", a21_diagnostic_evaluations=1):
            metrics, diagnostic_vectors = evaluate(case["JF"], JR, case["r"], case["lam"], case["ell"],
                case["sF"], sR, case["auditF"], auditR, case["A"], case["lower"], config)
        record.update(metrics)
        vectors.update(diagnostic_vectors)
        with book.span("a21_current_capture_diagnostics", current_capture_bank_evaluations=4):
            record.update(primal_capture_trial=_capture(case["X"], trial.Z, config),
                          primal_capture_test=_capture(case["X"], test.Z, config),
                          dual_capture_trial=_capture(case["Y"], trial.Z, config),
                          dual_capture_test=_capture(case["Y"], test.Z, config))
        record.update(
                      primal_oracle_backward=case["metadata"]["primal_oracle_backward"],
                      dual_oracle_backward=case["metadata"]["dual_oracle_backward"],
                      status="OK", consistency_passed=True, reference_valid=True)
    except RankBudgetInfeasible as error:
        failure = error
        record.update(status="RANK_BUDGET_INFEASIBLE", failure_reason=str(error),
                      failure_details=getattr(error, "details", None))
    except UnsafeCore as error:
        failure = error
        record.update(status="UNSAFE_CORE", failure_reason=str(error),
                      failure_details=getattr(error, "details", None))
        if hasattr(error, "core"):
            vectors["core"] = error.core
    except QPFailure as error:
        failure = error
        record.update(status="QP_FAILED", failure_reason=str(error), QP=getattr(error, "result", None))
        if getattr(error, "step", None) is not None:
            vectors["failed_sR"] = error.step
    except BaseException as error:
        failure = error
        record.update(status="STOPPED" if isinstance(error, BudgetExceeded) else "FAILED",
                      failure_reason=type(error).__name__+": "+str(error),
                      failure_details=getattr(error, "details", None))
        if hasattr(error, "vectors"):
            vectors.update(error.vectors)
    finally:
        record["cost"] = _cost_delta(book, old, started)
        diagnostic_path = directory/"diagnostics"/f"{pid}_{ITERATION}_{arm}.npz"
        _save_npz(diagnostic_path, vectors)
        record["diagnostic_path"] = str(diagnostic_path)
    return record, failure


class _Sink:
    def __init__(self, directory, job, run_id):
        self.directory, self.job, self.run_id = directory, job, run_id
        self.path = directory / "rows.jsonl"
        self.rows = {}
        if self.path.exists():
            for line in self.path.read_text().splitlines():
                if line.strip():
                    row = json.loads(line)
                    self.rows[(int(row["parent_id"]), row["arm"])] = row

    def append(self, row):
        key = (int(row["parent_id"]), row["arm"])
        prior = self.rows.get(key)
        if prior is not None and prior["status"] != "NOT_RUN":
            raise AnatomyInputError("DUPLICATE_EXECUTED_ARM_FORBIDDEN:"+str(key))
        row = plain(row)
        with self.path.open("a") as handle:
            handle.write(json.dumps(row, allow_nan=False)+"\n")
            handle.flush()
        self.rows[key] = row
        pid = row["parent_id"]
        write_json(self.directory/"states"/f"{pid}_{ITERATION}.json",
                   {"parent_id": pid, "iteration": ITERATION,
                    "arms": [self.rows[(pid,a)] for a in ARMS if (pid,a) in self.rows]})

    def not_run(self, reason):
        for pid in PARENTS:
            for arm in ARMS:
                if (pid, arm) not in self.rows:
                    row = _base_record(pid, arm, self.job, self.run_id)
                    row["failure_reason"] = reason
                    self.append(row)


def _synthetic_validation(root, directory, config, book):
    # The explicit CLI validation stage runs the unmodified supplied script
    # and all bounded tiny tests, with inclusive child CPU in A21Book. Anatomy
    # consumes that exact receipt; it never repeats or double-bills a child.
    path = root/"results/a21/validation/T0.json"
    if not path.is_file():
        raise AnatomyInputError("SUPPLIED_SYNTHETIC_AND_UNIT_T0_RECEIPT_MISSING")
    receipt = json.loads(path.read_text())
    if (receipt.get("status") != "PASS" or not receipt.get("complete_unittest_discovery")
            or receipt.get("source_freeze") != config["source_freeze"]
            or len(receipt.get("children", [])) != 2
            or not all(row.get("status") == "PASS" for row in receipt["children"])
            or not isinstance(receipt.get("copied_synthetic_results"), str)):
        raise ConsistencyFailure("SUPPLIED_SYNTHETIC_AND_UNIT_T0_RECEIPT_NOT_PASS")
    copied_result = (root/receipt["copied_synthetic_results"]).resolve()
    if not copied_result.is_relative_to(root):
        raise AnatomyInputError("T0_RESULT_PATH_OUTSIDE_A21_ROOT")
    source = root/"protocol/a21/validation/validate_two_sided.py"
    if not source.is_file():
        raise AnatomyInputError("SUPPLIED_SYNTHETIC_PROTOCOL_SOURCE_MISSING")
    result = dict(receipt, receipt_path=str(path), source="protocol/a21/validation/validate_two_sided.py",
                  reused_existing_T0=True, new_child_jobs=0, new_child_CPU_seconds=0.,
                  copied_synthetic_result_locally_present=copied_result.is_file())
    write_json(directory/"validation"/"synthetic_receipt_reuse.json", result)
    book.check()
    return result


def _G_complete(sink):
    return all(sink.rows.get((p,a), {}).get("status") == "OK"
               and sink.rows[(p,a)].get("consistency_passed") for p in PARENTS for a in ARMS_G)


def _summary(sink, config, t0, stage, stopped=None):
    rows = [sink.rows[(p,a)] for p in PARENTS for a in ARMS if (p,a) in sink.rows]
    g_complete = _G_complete(sink)
    counts = dict(Counter(row["status"] for row in rows))
    pg_complete = all(sink.rows.get((p,a), {}).get("status") == "OK" for p in PARENTS for a in ARMS_PG)
    result = {"schema": "a21.anatomy_summary.v1", "job": sink.job, "run_id": sink.run_id,
              "stage_requested": stage, "status": "FAILED" if stopped else
                  "COMPLETE" if g_complete and pg_complete else "GALERKIN_COMPLETE" if g_complete else "PARTIAL",
              "T0": t0, "T0_status": t0.get("status", "NOT_RUN"), "T1_status": "PENDING_PARENT_SCIENTIFIC_REVIEW",
              "parents": list(PARENTS), "iterations": [ITERATION], "arms_G": list(ARMS_G), "arms_PG": list(ARMS_PG),
              "G_all_five_consistent": g_complete, "PG_prerequisite_satisfied": g_complete,
              "PG_all_five_complete": pg_complete, "status_counts": counts, "expected_arm_states": 35,
              "reduced_QPs_attempted": sum(int(row.get("cost", {}).get("counts", {}).get("a21_reduced_qps", 0)) for row in rows),
              "no_automatic_online_or_imaging": True, "scientific_gate_computed": False,
              "truth_or_labels_read": False, "dataset_exposure": "historically_exposed_feasibility",
              "rows_path": str(sink.path), "state_records_directory": str(sink.directory/"states"),
              "cache_directory": str(sink.directory/"caches"), "diagnostics_directory": str(sink.directory/"diagnostics"),
              "stopped_reason": stopped, "records": rows}
    write_json(sink.directory/"summary.json", result)
    return result


def run_anatomy(root, config, book, job):
    """Run all five G arms, and only then eligible PG arms from disk caches.

    Runtime-only config key ``stage`` is all / galerkin / petrov.  The latter
    requires prior passing T0 and 25 consistent G rows and never builds an
    Adapter. Executed rows cannot be retried silently in the same results.
    """
    root = Path(root).resolve()
    _check_config(config)
    stage = config.get("stage", "all")
    if stage not in ("all", "galerkin", "petrov"):
        raise AnatomyInputError("UNREGISTERED_ANATOMY_STAGE")
    directory = root / "results/a21/anatomy"
    for name in ("caches", "diagnostics", "states", "validation"):
        (directory/name).mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")+"_"+uuid.uuid4().hex[:8]
    sink = _Sink(directory, job, run_id)
    t0 = {"status": "NOT_RUN", "synthetic": None, "backend": {}}
    current_pid, current_arm = PARENTS[0], "BASE_G"
    failure_started, failure_old = (time.perf_counter(),time.process_time()), _snapshot(book)
    try:
        prior_failures = [r for r in sink.rows.values() if r["status"] not in ("OK", "NOT_RUN")]
        if prior_failures:
            raise AnatomyInputError("PREVIOUS_FAILED_ARMS_REQUIRE_EXPLICIT_INSPECTION; no automatic retry")
        if stage == "petrov":
            old_summary = json.loads((directory/"summary.json").read_text())
            t0 = old_summary["T0"]
            if t0.get("status") != "PASS" or not _G_complete(sink):
                raise AnatomyInputError("CACHE_ONLY_PETROV_REQUIRES_COMPLETE_CONSISTENT_G_AND_T0")
        else:
            t0["synthetic"] = _synthetic_validation(root, directory, config, book)
            parents = {int(p["parent_id"]): p for p in json.loads((root/"configs/parents.json").read_text())["parents"]}
            # First/middle/last backend checks run first, with computations
            # preserved for the later anatomy. No outcome-based state choice.
            order = list(config["validation_parents"])+[p for p in PARENTS if p not in config["validation_parents"]]
            manifest = []
            for pid in order:
                current_pid = pid
                failure_started, failure_old = (time.perf_counter(),time.process_time()), _snapshot(book)
                book.metadata.update(job=job, parent_id=pid, iteration=ITERATION, stage="state_preparation")
                cache_path = directory/"caches"/f"{pid}_{ITERATION}.npz"
                if cache_path.exists():
                    metadata = load_cached_case(cache_path, config)["metadata"]
                    if pid in config["validation_parents"] and metadata.get("backend_validation", {}).get("status") != "PASS":
                        raise AnatomyInputError("EXISTING_CACHE_BACKEND_VALIDATION_NOT_PASS")
                else:
                    case = prepare_case(root, parents[pid], config, book)
                    case["config"] = config
                    validation_failure = None
                    if pid in config["validation_parents"]:
                        try:
                            validation_started, validation_old = (time.perf_counter(),time.process_time()), _snapshot(book)
                            case["metadata"]["backend_validation"] = validate_case(case, config, book)
                            case["metadata"]["backend_validation"]["cost"] = _cost_delta(book,validation_old,validation_started)
                        except BaseException as error:
                            validation_failure = error
                            case["metadata"]["backend_validation"] = {"status": "FAILED", "error": str(error),
                                "details": getattr(error, "details", None)}
                    else:
                        case["metadata"]["backend_validation"] = {"status": "NOT_REQUIRED", "predeclared": True}
                    metadata = _save_case(case, directory, book)
                    del case
                    gc.collect()
                    if validation_failure is not None:
                        raise validation_failure
                manifest.append(metadata)
                if pid in config["validation_parents"]:
                    t0["backend"][str(pid)] = metadata["backend_validation"]
                write_json(directory/"frozen_inputs.json", {"schema": "a21.identified_inputs.v1",
                    "frozen_parent_order": list(PARENTS), "iteration": ITERATION,
                    "config_signature": _signature(config),
                    "preparation_order": order,
                    "prepared_states": sorted(manifest,key=lambda m:PARENTS.index(m["parent_id"])),
                    "new_hash_checks": False, "truth_or_labels_read": False})
            t0["status"] = "PASS" if t0["synthetic"]["status"] == "PASS" and all(
                t0["backend"].get(str(pid), {}).get("status") == "PASS" for pid in config["validation_parents"]) else "FAILED"
            if t0["status"] != "PASS":
                raise ConsistencyFailure("T0_SYNTHETIC_AND_REGISTERED_BACKEND_VALIDATION_NOT_PASS")
            for pid in PARENTS:
                current_pid = pid
                case = load_cached_case(directory/"caches"/f"{pid}_{ITERATION}.npz", config)
                for arm in ARMS_G:
                    current_arm = arm
                    if sink.rows.get((pid,arm), {}).get("status") == "OK":
                        continue
                    if sum(int(row.get("cost",{}).get("counts",{}).get("a21_reduced_qps",0)) for row in sink.rows.values()) >= config["maximum_reduced_qps"]:
                        raise AnatomyInputError("FROZEN_REDUCED_QP_CAP_EXHAUSTED")
                    book.metadata.update(job=job, parent_id=pid, iteration=ITERATION, arm=arm, stage="galerkin")
                    record, failure = evaluate_arm(case, arm, config, book, directory, job, run_id)
                    sink.append(record)
                    if failure is not None and not isinstance(failure, (RankBudgetInfeasible, UnsafeCore, QPFailure)):
                        raise failure
                del case
                gc.collect()
        if stage != "galerkin" and _G_complete(sink):
            for pid in PARENTS:
                current_pid = pid
                case = load_cached_case(directory/"caches"/f"{pid}_{ITERATION}.npz", config)
                for arm in ARMS_PG:
                    current_arm = arm
                    if sink.rows.get((pid,arm), {}).get("status") == "OK":
                        continue
                    if sum(int(row.get("cost",{}).get("counts",{}).get("a21_reduced_qps",0)) for row in sink.rows.values()) >= config["maximum_reduced_qps"]:
                        raise AnatomyInputError("FROZEN_REDUCED_QP_CAP_EXHAUSTED")
                    book.metadata.update(job=job, parent_id=pid, iteration=ITERATION, arm=arm, stage="petrov_cache_only")
                    record, failure = evaluate_arm(case, arm, config, book, directory, job, run_id)
                    sink.append(record)
                    if failure is not None and not isinstance(failure, (RankBudgetInfeasible, UnsafeCore, QPFailure)):
                        raise failure
                del case
                gc.collect()
        sink.not_run("PG_STAGE_NOT_REQUESTED" if stage == "galerkin" else "PRIMARY_G_NOT_COMPLETE_AND_CONSISTENT")
        return _summary(sink, config, t0, stage)
    except BaseException as error:
        if isinstance(error, ConsistencyFailure):
            t0.update(status="FAILED", failure_reason=str(error))
        elif isinstance(error, AnatomyInputError):
            t0.update(status="BLOCKED_INPUT_OR_BASELINE_CONFLICT", failure_reason=str(error))
        if (current_pid,current_arm) not in sink.rows or sink.rows[(current_pid,current_arm)]["status"] == "NOT_RUN":
            row = _base_record(current_pid, current_arm, job, run_id)
            row.update(status="STOPPED" if isinstance(error,BudgetExceeded) else
                       "RANK_BUDGET_INFEASIBLE" if isinstance(error,RankBudgetInfeasible) else
                       "UNSAFE_CORE" if isinstance(error,UnsafeCore) else "FAILED",
                       failure_reason=type(error).__name__+": "+str(error),
                       failure_details=getattr(error,"details",None), failure_stage=book.metadata.get("stage"),
                       cost=_cost_delta(book,failure_old,failure_started))
            if hasattr(error,"vectors"):
                failed_path = directory/"diagnostics"/f"{current_pid}_{ITERATION}_failed_preparation.npz"
                if not failed_path.exists():
                    _save_npz(failed_path,error.vectors)
                row["diagnostic_path"] = str(failed_path)
            sink.append(row)
        sink.not_run("STOPPED_AFTER:"+type(error).__name__+": "+str(error))
        _summary(sink, config, t0, stage, type(error).__name__+": "+str(error))
        if isinstance(error,(RankBudgetInfeasible,UnsafeCore)):
            return json.loads((directory/"summary.json").read_text())
        raise
