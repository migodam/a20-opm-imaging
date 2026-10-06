# Closest-Prior Audit and Publication Judgment

## 1. Exact left/right interpolation is classical

**R1, Baur et al. (2011), Theorem 3.1:** right resolvent containment gives right tangential interpolation; left resolvent containment gives left tangential interpolation; paired conditions also support derivative interpolation. This directly precedes the Petrov current-containment proof. Their broader framework includes parameter-gradient and Hessian matching. A21 selects the right direction s_F and the left direction e_F because they form a constrained GN KKT condition. Do not present the containment identity itself as new.

## 2. Inverse-problem ROMs already preserve Jacobians

**R2, de Sturler et al. (2015):** interpolatory parametric ROMs reduce nonlinear inverse problems by preserving forward responses and Jacobian-related transfer information. The application is diffuse optical tomography. A21 is not the first ROM-based nonlinear inverse solver or the first derivative-aware inverse ROM. Its narrower target is one frozen optimum and its residual-weighted pullback, rather than uniform preservation of every Jacobian column across a parameter range.

## 3. Separate primal/dual spaces and optimization consistency

**R3, Keil et al. (2021):** adaptive trust-region reduced-basis optimization treats bilateral parameter constraints, non-conforming dual approximations, a posteriori errors and convergence. This is close prior for the role of valid constraints and dual consistency. A21's full-gap normal-work term and exact frozen quadratic are specific objects, not a replacement for their broader convergence analysis.

**R4, Keil and Ohlberger (2021):** the primal Petrov trial space is the dual test space, and vice versa. The paper explains why the reduced gradient is then the derivative of the actual reduced objective and explicitly notes stabilization issues. This is a particularly close precedent for the proposed architecture. A21 must therefore justify its Maxwell Schur-feedback realization and online cost, not advertise trial/test splitting alone.

## 4. Adaptive accuracy and gradient-based stopping already exist

**R5, Qian et al. (2017):** certified cost/gradient error bounds and adaptive high-fidelity updates are used in a reduced-basis trust-region method. First-order model consistency is an established optimization requirement. A21's proposed distinction is the explicit two-current realization of the frozen material KKT defect and the use of very few source-resolved task directions. The online computational advantage remains an empirical question.

## 5. The goal need not be scalar

**R6, Billaud-Friess et al. (2016):** goal-oriented projection already addresses vector-valued quantities of interest, distinguishes primal, test and dual approximation spaces, and studies saddle-point constructions. A21 must not claim novelty merely because the material pullback is a vector instead of a scalar objective. Its concrete goal is the constrained GN stationarity vector in the Maxwell inverse problem.

## 6. Not IRKA and not a new Krylov solver

**R7, Gugercin et al. (2008):** IRKA uses interpolation-based first-order conditions for H2-optimal dynamical-system approximation. A21 fixes a Maxwell state/frequency and targets material optimization directions. Its optimum is a GN material step, not an H2-optimal reduced dynamical system. Repeated task retargeting can resemble interpolatory iteration without inheriting IRKA optimality or convergence results.

## 7. Maxwell inverse ROMs are already a field

**R8, Borcea et al. (2024):** a data-driven time-domain Maxwell ROM interpolates measurements and supports imaging and quantitative inversion. Its construction and objective differ from a reduced current resolvent used inside a frozen regularized GN step. The distinction is methodological; 'first ROM for electromagnetic inverse scattering' would be false. Do not imply their experiments are full 3D vector benchmarks.

## 8. What is and is not an A21 contribution

The exact theorem is an elementary but useful corollary of convex optimality and classical tangential interpolation. The approximate bounds are standard strong-monotonicity consequences specialized to two explicit GN endpoint errors. The added value here is their consistent combination with real-material complex Maxwell currents, source-wise protection, constraint normals, and the retained-U Schur architecture.

A successful oracle is largely expected once the hypotheses are verified. It demonstrates that the implementation realizes the theorem and helps identify why the old primal-only representation failed. It does not demonstrate an online algorithm, speedup, improved truth reconstruction or broad low-rank compressibility.

A potentially strong paper would need a coherent additional chain:

1. Reproducible late-state anatomy separating primal excitation, dual pullback, curvature amplification and numerical error.
2. A non-oracle, task-conditioned primal/dual construction that works at the same affordable rank and cost.
3. Actual 3D nonlinear imaging evidence against common Galerkin, generic two-sided/goal-oriented ROM and full-reference baselines, with all setup and audit costs included.

A standalone theorem plus five oracle states is not yet a strong TAP paper in my assessment. It is a high-value mechanism decision and can form the backbone of a later imaging paper if the online and nonlinear evidence succeeds. This is a research assessment, not a publication guarantee.

## 9. Diagnosis without overclaiming

The supplied near-exact primal tangent and poor optimum are consistent with a dual/stationarity defect, but also with amplification of the residual primal term, a weak reduced Hessian, a tiny reference-step denominator, invalid constraint normals or a mismatched frozen objective. The experiment must measure these possibilities instead of declaring a new physical mechanism in advance.

If exact current protection makes the primal-only arm good, the previous injection oracle was not an adequate substitute for that current span. If two-sided Galerkin works but Petrov does not, keep the mechanism and reject or stabilize the split architecture. If a valid small solver-aware bound is contradicted, debug before interpreting the result physically.
