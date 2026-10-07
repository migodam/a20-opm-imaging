"""Additional finite-dimensional tests for T5, T6, T8, T10 and Schur assembly.
No project data, GPU, model training, or imaging performance evaluation.
Run from any directory: python verification/verify_additional.py
"""
from pathlib import Path
import json
import numpy as np
from numpy.linalg import norm, solve, svd

rng = np.random.default_rng(20261008)
out = Path(__file__).resolve().parent


def main():
    m, r, q = 11, 3, 4
    ap = rng.normal(size=(m, r))
    k = rng.normal(size=(m, q))
    pi = np.eye(m) - k @ np.linalg.pinv(k)
    g = pi @ ap
    sig = svd(g, compute_uv=False)
    a = rng.normal(size=r)
    b = 5 * rng.normal(size=q)
    e = 0.02 * rng.normal(size=m)
    d = ap @ a + k @ b + e
    t5 = []
    for lam in (0.0, 0.01, 0.5):
        decoder = solve(g.T @ g + lam * np.eye(r), g.T @ pi)
        err = norm(decoder @ d - a)
        bound = lam / (sig[-1] ** 2 + lam) * norm(a)
        bound += np.max(sig / (sig ** 2 + lam)) * norm(e)
        t5.append({"lambda": lam, "error": float(err), "bound": float(bound),
                   "ratio": float(err / bound),
                   "nuisance_leak": float(norm(decoder @ k))})
        assert err <= bound * (1 + 1e-10)
        assert norm(decoder @ k) < 1e-12

    # T8: an orthogonal compressed likelihood retains all x-dependent terms.
    amat = rng.normal(size=(12, 5))
    z = np.linalg.qr(amat, mode="reduced")[0]
    data = rng.normal(size=12)
    x = rng.normal(size=5)
    lhs = norm(data - amat @ x) ** 2
    rhs = norm(z.T @ data - z.T @ amat @ x) ** 2
    rhs += norm((np.eye(12) - z @ z.T) @ data) ** 2
    t8_error = abs(lhs - rhs) / max(lhs, rhs, 1e-30)
    assert t8_error < 1e-12

    # T6 example: data budget is attained by a pure quadratic prior direction.
    tau = 0.03
    curvature = 2.0
    slope = 0.0
    rmax = 2 * tau / (slope + np.sqrt(slope ** 2 + 2 * curvature * tau))
    nonlinear_change = rmax ** 2
    assert abs(nonlinear_change - tau) < 1e-14

    # Complete Schur assembly includes the retained direct contribution.
    def cm(shape):
        return (rng.normal(size=shape) + 1j * rng.normal(size=shape)) / np.sqrt(2)
    n, n1, p, md = 10, 4, 6, 7
    ell = np.eye(n) + 0.08 * cm((n, n))
    inj, obs = cm((n, p)), cm((md, n))
    l11, l12 = ell[:n1, :n1], ell[:n1, n1:]
    l21, l22 = ell[n1:, :n1], ell[n1:, n1:]
    b1, b2 = inj[:n1], inj[n1:]
    s1, s2 = obs[:, :n1], obs[:, n1:]
    schur = l22 - l21 @ solve(l11, l12)
    direct = s1 @ solve(l11, b1)
    feedback = (s2 - s1 @ solve(l11, l12)) @ solve(
        schur, b2 - l21 @ solve(l11, b1))
    full = obs @ solve(ell, inj)
    schur_error = norm(full - direct - feedback) / norm(full)
    assert schur_error < 1e-12

    # T10: exact normalized-current feedback identity and residual bound.
    # Random finite matrices are an algebra test, not a Maxwell scene.
    rng10 = np.random.default_rng(20261010)
    def cm10(shape):
        return (rng10.normal(size=shape) + 1j * rng10.normal(size=shape)) / np.sqrt(2)
    n10, m10, r10 = 9, 5, 5
    gd = cm10((n10, n10))
    gd *= 0.7 / norm(gd, 2)
    x0 = np.diag(0.4 + 0.4 * rng10.random(n10) + 0.02j)
    dx = np.diag(0.12 * rng10.normal(size=n10))
    e_inc = cm10(n10)
    ell0 = np.eye(n10) - x0 @ gd
    j0 = solve(ell0, x0 @ e_inc)
    e0 = e_inc + gd @ j0
    j1 = solve(np.eye(n10) - (x0 + dx) @ gd, (x0 + dx) @ e_inc)
    delta_j = j1 - j0
    obs10 = cm10((m10, n10))
    h10 = cm10(m10)
    u = solve(ell0, dx @ e0)
    psi = solve(ell0.conj().T, obs10.conj().T @ h10)
    nonlinear_value = np.vdot(h10, obs10 @ (delta_j - u))
    paired_value = np.vdot(psi, dx @ gd @ delta_j)
    ident_rel = abs(nonlinear_value - paired_value) / max(abs(nonlinear_value), 1e-30)
    assert ident_rel < 1e-11
    q10 = np.linalg.qr(cm10((n10, r10)), mode='reduced')[0]
    red = q10 @ solve(q10.conj().T @ ell0 @ q10, q10.conj().T)
    ur = red @ dx @ e0
    psir = red.conj().T @ obs10.conj().T @ h10
    rm = dx @ e0 - ell0 @ ur
    ro = obs10.conj().T @ h10 - ell0.conj().T @ psir
    alpha_l = svd(ell0, compute_uv=False)[-1]
    t_exact = norm(solve(ell0, dx @ gd), 2)
    t_bar = norm(dx @ gd, 2) / alpha_l
    assert t_exact <= t_bar < 1
    direct_bound = norm(gd.conj().T @ dx.conj().T @ psi) * norm(u) / (1 - t_exact)
    resid_bound = (norm(gd.conj().T @ dx.conj().T @ psir)
                   + norm(dx @ gd, 2) * norm(ro) / alpha_l)
    resid_bound *= (norm(ur) + norm(rm) / alpha_l) / (1 - t_bar)
    assert abs(nonlinear_value) <= direct_bound * (1 + 1e-10)
    assert abs(nonlinear_value) <= resid_bound * (1 + 1e-10)
    t10 = {
        'seed': 20261010,
        'identity_relative_error': float(ident_rel),
        'nonlinear_witness_magnitude': float(abs(nonlinear_value)),
        'exact_pairing_bound': float(direct_bound),
        'residual_bound': float(resid_bound),
        'actual_over_exact_bound': float(abs(nonlinear_value) / direct_bound),
        'actual_over_residual_bound': float(abs(nonlinear_value) / resid_bound),
        't_exact': float(t_exact),
        't_upper': float(t_bar),
        'warning': 'Full alpha_L and chosen delta_X are evaluation inputs, not free online certificates.'
    }

    result = {
        "seed": 20261008,
        "task_curvature_t10": t10,
        "profiled_tikhonov": t5,
        "compressed_likelihood_relative_error": float(t8_error),
        "prior_safe_radius": float(rmax),
        "prior_data_change_at_radius": float(nonlinear_change),
        "schur_complete_map_relative_error": float(schur_error),
        "warning": "Algebra checks only. Project imaging gates remain NOT_RUN."
    }
    (out / "additional_results.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
