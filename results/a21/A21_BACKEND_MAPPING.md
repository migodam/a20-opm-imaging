# A21 backend mapping

Source freeze: A20-R1 `3b3b17b5f4cf5d37b26602ead2dfe7c913b37e23`.
This map identifies the existing code and immutable inputs; live numerical
validation is recorded separately by the A21 runner. Prior A20 results do not
constitute a new A21 PASS.

| Frozen quantity | Existing implementation and convention |
|---|---|
| Maxwell L and full state | `src/a20/backend.py:Adapter`, `vendor/a17/a9_engine.py:DenseDDA/DDAState`; one factorization per frozen material state, complex128 |
| Full/current adjoint | The same `state._L_factor`, solver `trans=2` (conjugate transpose); no reciprocal-transpose substitution |
| Current coordinates | `c=p/sqrt(volume)`, Euclidean complex current metric; 1728 cells, n=5184 |
| Six-source layout | `(source,current)` state/injection banks; oracle current bank has shape `(5184,6)` and preserves source order |
| Material coordinates | Saved Q of shape `(1728,27)`, volume=0.001953125; `volume*Q.T*Q=I`; real coordinates `[Re27,Im27]`, p=54 |
| B at frozen state | `Adapter.apply_B/injection_factor`, full-state exciting field and unchanged polarizability derivative; no reduced-state replacement |
| Material B adjoint | `Adapter.apply_B_adjoint` returns real 54-dimensional material cotangent |
| Observation | `Adapter.apply_S`, native GS; 128 complex receiver components per source |
| Packing | `backend.pack`: per source `[Re128,Im128]`, concatenate six sources, 1536 real entries |
| Whitening | `Adapter.whiten` AFTER packing; actual scalar `1/problem.scale`; general map uses its transpose for the adjoint |
| Dual forcing | `unpack(whiten(e_F,adjoint=True),6,128)` then physical `S*`; target e_F is the post-step predicted residual |
| Frozen quadratic | `r=whiten(pack(state.field-data0))`, saved ell, `Lambda=lambda_total*I54`; late saved lambda_total=3.43e-5 |
| Actual constraints | `material.constraint_map`: A=block_diag(Q,Q), `A@s >= [-0.5-chi.real,-chi.imag]`; no trust ball or upper bound |
| Normal convention | `material.kkt`: nonnegative lower-constraint multipliers, `n=-A.T@mu`, `rho=gradient+n`; feasibility and complementarity checked independently |
| Material QP | `material.solve_quadratic`: original direct SPD/SLSQP plus registered active-equation polish, unchanged KKT/feasibility 1e-8; raw minimizer, no post clipping |
| H-step metric | `H_F=J_F.T@J_F+Lambda` in the SAME real chart; relative error never substitutes a denominator floor for a valid ratio |
| Retained/feedback baseline | Original R1 direct receiver U8, O4/P4/M4, degree3, previous=None; total rank56, complement48, original degree/index priority |

## Immutable inputs and original optimum

Manifest order: **2001,2005,2003,2007,2013**, all iteration17 and historically
exposed. Runtime inputs are `data/runtime/<ID>/problem.npz` and `state_17.npz`.
The canonical raw reference is
`results/replay/steps/20261005T082521_71339a28_<ID>_17_full_GN_reference_None.npz`.
It contains `step:float64[54]`, saved directly from the constrained solver.
The old offline label steps failed the original constrained audit and are not
admissible replacements. Raw original active counts were 2,2,10,1,3.

The disk has no saved full J/H, L/LU, normals, retained/baseline basis or X/Y
banks. Existing `full_J_cached` metadata refers to an in-process cache. A21
pays to rebuild each state/full Jacobian once, revalidates the same reference,
then stores its oracle bank and small frozen diagnostic data for all arms.
No truth arrays are needed by this experiment.

## New, isolated interface

`src/a21` implements an offline-only shared bank, protected QR with coordinate
transforms, tied common/Petrov projected cores, defect diagnostics and bounded
driver. Full LU and full workspace are released after shared images have
been cached; the later Petrov stage uses the same frozen images without
rebuilding the Maxwell state. Galerkin arms forbid automatic Petrov or full
fallback. Square-core stability uses the original absolute/relative sigma
and conditioning gates; unsafe cores remain explicit failed instances.

`src/a20`, `src/a20_r1`, the vendor backend, old references and old ledgers are
not edited. The original R1 early 2001/0 retained-U reproducibility conflict
is preserved as historical evidence; its cause remains unproved. All five
late baseline replays passed the old 1e-9 guard. A21 checks their reproduction
again and does not run an early state to repair that earlier conflict.

No new SHA256 checks are performed. Existing Git identities, immutable input
IDs and historical hash fields provide provenance; new execution metadata
records the actual A21 implementation commit and exact commands.

## Executed A21 verification

Five late references passed without repair; real T0 (2001/2003/2013) passed. All35 arms and independent saved-array review passed. Physical source `5c6bcb02bb4ab88f7b46f07bca4ca3f4e38a067c`; final review and exact numerical evidence: `A21_ORACLE_REPORT_ZH.md`, `A21_FROZEN_MANIFEST.json`, `INDEPENDENT_ARRAY_REVIEW.json`. No new SHA256 checks.
