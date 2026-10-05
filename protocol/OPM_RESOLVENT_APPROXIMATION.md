# Orthogonal-feedback approximation: what is classical and what to implement

Read OPM_IMAGING_THEORY.md first. References are resolved in REFERENCES.md.

## 1. Block FOM, block GMRES, and the mixed hierarchy

For a single FORWARD block stream, block Arnoldi gives

    F_eff V_l = V_l H_l + V_next H_tail E_last^*,
    V_l^* V_l=I.

For A=I-F_eff and a seed block B=V_1 Beta, block FOM solves

    (I-H_l)Y=V_l^*B,  X_l=V_lY.

Its residual is available from the Arnoldi tail and Y. FOM enforces V_l^*(B-A X_l)=0; it does NOT minimize the full residual norm in general.

Block GMRES solves

    min_Y ||B-A V_l Y||_F.

Use the augmented Arnoldi relation/QR, not normal equations. GMRES gives nonincreasing residual norms on nested trial spaces, but not automatically nonincreasing Jacobian error, GN-step error, or truth error. Source blocks can be rank deficient; use rank-revealing deflation and retain source mappings.

The final joint forward/adjoint OPM basis is a UNION of two block Krylov families. Its compressed F_eff is generally dense and need not be a single upper-Hessenberg Arnoldi matrix. Keep the two recurrence records and calculate the actual projected core. Applying a scalar Lanczos three-term recurrence to this non-Hermitian mixed object is not justified.

## 2. Why Arnoldi is not Chebyshev in disguise

Krylov orthogonality is induced by the particular operator, seeds and current-space inner product. Chebyshev/Legendre orthogonality is defined by a prescribed scalar measure. For a nonnormal Maxwell operator, an eigenvalue interval and a three-term scalar orthogonal-polynomial recurrence generally do not determine stable approximation behavior.

Example: F=[[0,100],[0,0]] has spectral radius zero, yet ||(I-F)^{-1}|| is about 100.01. A spectral-radius-only rule misses its transient amplification. See the reproducible counterexample.

For any polynomial p and analytic f(z)=1/(1-z), on a contour Gamma enclosing the spectrum and excluding the pole at one,

    ||f(F)-p(F)||
      <= length(Gamma)/(2 pi)
         max_Gamma |f(z)-p(z)|
         max_Gamma ||(zI-F)^{-1}||.

This shows explicitly where nonnormality enters. A contour separating the spectrum from one may exist while the associated resolvent bound is huge. Numerical-range/Faber estimates are useful when their enclosing-domain assumptions hold [R07]. Do not replace the resolvent factor by distance to eigenvalues for a nonnormal matrix.

## 3. Projection stability is a separate issue

For fixed Q and A_Q=Q^*A Q invertible, the Galerkin projector is

    Pi_A=Q A_Q^{-1}Q^*A.

For x=A^{-1}b,

    ||x-x_Q|| <= ||I-Pi_A|| min_{v in range Q}||x-v||
              <= [1+||A_Q^{-1}||||A||] min ||x-v||.

Thus a good approximating span can still produce a poor Galerkin answer if the reduced core is unstable. An invertible full matrix does not guarantee invertible A_Q: A=[[0,1],[-1,0]], Q=e_1 is an explicit counterexample.

Log scaled sigma_min(A_Q), residuals, and actual material action errors. Do not silently add damping to L: that changes the physical forward problem. First change projection or increase degree; if necessary use the existing full solver.

## 4. A legitimate least-squares fallback and its derivative trap

For a fixed full-current trial basis Z, residual minimization gives

    R_LS = Z[(LZ)^*(LZ)]^{-1}(LZ)^*.

Use QR in code. This is NOT Z(Z^*LZ)^{-1}Z^*. It has a different test space, so the Galerkin double-residual and moment formulas cannot simply be reused without checking the Petrov formulation.

Recommended local fallback: freeze both trial Z and test W=L(x_k)Z at the outer state, and use

    j_{Z,W}(x)=Z[W^*L(x)Z]^{-1}W^*b(x).

At x_k this equals the residual-minimizing solution. Its frozen-test derivative is S Z[W^*LZ]^{-1}W^*B(j_{Z,W}). Recheck conditioning throughout a trial step.

If W=L(x)Z is updated with x, differentiating the true least-squares reduced state instead gives

    a'=[(LZ)^*(LZ)]^{-1}
       [(LZ)^*B(j_m)d + (L'(x)d Z)^*(b-Lj_m)].

The second, residual-weighted term is generally nonzero. In complex problems with real material it is a real-linear expression. Omitting it while claiming an exact reduced derivative is an implementation error.

## 5. Faber, rational, and biorthogonal extensions

Faber polynomials: use a certified or empirically validated spectral/numerical-range domain avoiding the resolvent pole. They offer a coefficient/evaluation strategy and potential stable recurrence. At the same maximum polynomial degree and same seeds they do not enlarge the polynomial Krylov SPAN, so they cannot by themselves rescue a missing material/observation seed. Do not add a Faber branch before an Arnoldi pilot demonstrates a concrete coefficient or memory bottleneck.

Rational Krylov: use rational functions with prescribed poles/shifted solves, e.g. (A-sigma I)^{-1} applied to selected right and left seed blocks. It may address sharp resolvent structure with lower rank, but each shift has a real solve/factorization/preconditioning cost. Applying (I-F_eff)^{-1} to all material RHS as a 'seed generator' has already paid for the target resolvent; it cannot be reported as free preprocessing. Reuse shifts across frequencies/states only if the reuse is measured and stable [R08].

Biorthogonal two-sided projection: distinct V,W may match endpoint information with a smaller core than orthogonalizing their union. It introduces W^*V and W^*AV stability issues, look-ahead/breakdown handling and more complicated gauge transport. Use joint orthogonalization in the first pilot; test biorthogonal compression only when rank, rather than seed construction or physical solves, is the measured bottleneck.

Restart/recycle: store degree-tagged right/left blocks and their cached operator images. Across accepted material states, reorthogonalize and check the actual new residual/innovation. Recycle approximately useful spaces; do not reuse stale projected matrices as if F_eff were unchanged.

## 6. Secondary route pseudocode

```
initialize separate right and adjoint block streams
repeat:
    extend the stream(s) whose physical residual/task audit is limiting
    build nested joint Q and projected A_Q
    choose stable Galerkin or frozen-test Petrov projection
    expose paired J_m and J_m^* actions to the existing material solver
    solve the constrained material quadratic
    compute adjacent-degree innovation
    audit full material/KKT defect when stopping looks plausible
until audit passes, budget is exhausted, or full fallback is required
```

This is an iterative approximation hierarchy for the IMAGING problem. It is not a new universal Krylov solver. The nonlinear x update remains a GN/LM/DBIM-type step; polynomial recursion controls its physical model accuracy.

## 7. Cost and actions

Let n be current dimension, u retained rank, q added current rank, b_R/b_L retained stream block ranks, and c_F the cost of one physical F or F^* action. After caching F U and F^*U, each F_eff or F_eff^* action requires roughly one F/F^* action, O(nu) projections, and an O(u^2) coarse solve. The cache itself costs u forward plus u adjoint actions where required. Each degree costs approximately b_R forward plus b_L adjoint actions, before rank deflation; count individual RHS, not only batched launches.

Joint orthogonalization costs O(n q^2) cumulatively; reduced factorization O((u+q)^3); basis/cached-image memory O(n(u+q)). Full probe audits add N_source*N_frequency tangent and adjoint solves. Large material dimension additionally requires matrix-free B/B^* and J_m/J_m^* actions; do not store an n-by-p Jacobian.

No universal runtime ratio is supplied. On the user's project, previous profiling suggested workspace/basis construction could dominate Jd; therefore changing the solver action alone may have little end-to-end value. New timings must settle the issue.

## 8. Failure/novelty/gate

Failure: unstable cores; high required degree; dependent blocks; nonnormal delayed transfer; probe overfitting; rebuilding costs; or a rational branch that pays the full-solve cost upfront.

Novelty risk: FOM/GMRES, two-sided moment matching and rational projection are classical [R03,R06-R08]. The secondary route is strongest as the adaptive approximation layer of the primary imaging paper, not as a separate 'new polynomial solver' claim.

Minimum experiment: cached independent nonlinear states with m=0,...,5, directional and adjoint checks, full material/KKT audits, matched-rank/matched-action forward-only and ordinary Krylov controls. Proceed to live reconstruction only after these pass. Proposed practical GO: the same final-image tolerance as Route A at lower total work than fixed degree, with no unreported full-step fallback. See GO_NO_GO_GATES.md.
