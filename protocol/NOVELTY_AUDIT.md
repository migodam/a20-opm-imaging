# Novelty audit and proposed paper position

## Verdict

The credible primary claim is NOT a new generic Krylov method, new polynomial network, first reduced inverse solver, or first null-space prior. The potential contribution is a **material-task-conditioned, two-sided Schur-feedback hierarchy with inverse-update accuracy control, validated by full 3D vector-Maxwell reconstruction at measured total cost**.

The strongest possible paper combines deterministic Route A and the adaptive controller in Route C. They share the same representation and should normally be one coherent paper, not artificially split into a basis paper and a controller paper. The neural route is a separate conditional extension; do not make the deterministic manuscript depend on its success.

All literature statements below refer to REFERENCES.md. New derivations in this package are presented as specializations or proposed interfaces unless a distinct novelty claim is explicitly justified. This search identifies major collisions but does not establish exhaustive priority.

## 1. Closest deterministic overlaps

### DBIM and SOM/TSOM [R17-R19]

Updating a nonlinear scattering background and solving a material linearization is established. Receiver/current subspaces and current-dimension continuation also precede this work. In particular, do not advertise low-to-high degree continuation as inherently new merely because the coordinate is called degree.

The proposed difference must be demonstrable: O is an adjoint receiver chain, M is a material derivative injection chain, P protects physical states, and the reduced transfer is judged by material-step fidelity and final imaging rather than receiver singular strength or current dimension alone. Include the same backend and material parameterization for a fair comparison. A receiver-only baseline with an unfairly smaller rank is not sufficient.

### Interpolatory/derivative-preserving inverse ROM [R04]

This is a major novelty obstacle. The paper already connects forward and Jacobian evaluations to transfer functions and uses reduced models inside nonlinear inversion. Therefore, "J_m=S R_m B and then GN" is not by itself a strong contribution.

Potential separation: inexpensive mixed polynomial Schur construction instead of many solved interpolation snapshots, physically interpretable material injection/receiver return, and a calibrated degree policy for nonnormal full-wave scattering. These are hypotheses requiring cost/quality comparisons, not automatically new because the application is Maxwell.

### Adaptive ROM and conditional models [R05]

Adaptive reduced nonlinear inversion, model accuracy checks, and conditional trust-region models already exist. A proposed stopping law must identify what its material-GN residual adds and how it is evaluated cheaply enough to matter. Full audits that cost as much as solving the reference can eliminate the claimed advantage. The current package therefore includes both an exact audit identity and an explicit accounting of its tangent/adjoint RHS.

### FOM, GMRES and two-sided projection [R03,R04,R06]

Projected resolvents and moment matching are established linear algebra. The p+q+1 power identity is proved here to expose the physical O/M roles; it must not be sold as a new universal theorem. The substantive question is whether the O/P/M seed construction creates a better task representation than generic projection under equal budgets.

## 2. Polynomial and iterative-algorithm comparisons

### Faber and rational Krylov [R07-R08]

These are mature alternatives for matrix functions. Faber requires an appropriate complex spectral/field-of-values region and nonnormal control; rational Krylov requires paid shifted solves and pole choices. Neither should be bolted on before the basic OPM engine demonstrates a bottleneck that the extension addresses.

### Stanford orthogonal-polynomial algorithms [R09-R10]

A concrete relevant Stanford source is Lacotte-Pilanci's optimal randomized first-order least-squares work. It uses a limiting spectral measure to derive orthogonal-polynomial recurrences for sketched quadratic problems. This supports the general idea that approximation structure can determine an iteration, but not the claim that a scalar three-term recurrence is valid for the nonnormal feedback operator here.

A second-level extension could design iterations for the SPD material Hessian, but that returns to solving the same GN quadratic. It is secondary to imaging and should not replace the primary research question. The brief's Stanford phrase was not specific enough to identify a unique intended paper; this audit does not assert that uniqueness.

### MatRL [R11]

MatRL discovers sequences of matrix iterations and step sizes under a matrix distribution and hardware cost model. It motivates algorithm selection, but changing nonlinear Maxwell states require new distribution/stability arguments. Learning a recurrence is presently high risk, especially after the supplied A18-B deployment failure. Do not launch it before deterministic actions are profiled.

## 3. Neural imaging comparisons

### Wei-Chen, SOM-Net, and electromagnetic PINO [R01-R02,R22]

Induced-current learning, physics-guided unrolling, analytical material coupling, and state/data losses already exist. A generic OPM-initialized U-Net cannot claim a new physics-native architecture on that basis alone. The specific proposed distinction is a gauge-correct O/P/M transfer state conditioning a constrained material prior, with full-physics verification of where the prior may act.

### Neural Green's Operators and residual correction [R15-R16]

Forcing-linearity and structured coefficient-dependent Green operators have direct prior art. Approximate physics plus correction is also established. The supplied A18-B negative result is therefore a good practical reason not to return to a complete learned resolvent. Numerical solver correction must be separated from truth-directed prior learning.

### Far-field approximation learning [R20]

The accessible author abstract already demonstrates the pattern of using approximate physics to form a structured learning input for 3D reconstruction. The proposed OPM route differs in local full-wave material tangents, feedback hierarchy, and nonlinear constraints, not in the generic approximation-plus-network concept. The journal full text was blocked, so this is a limited architectural audit rather than a full performance/theory comparison.

### Learned null-space correction and plug-and-play [R13-R14]

A prior acting only in a null space is established. Here the space is weak rather than exactly null, approximate rather than known exactly, state-dependent, scaled by a noise/material metric, and used in a nonlinear map. The new work would need restricted full-Jacobian audit, finite-step leakage control, constrained feasibility, and an empirical benefit at deployment cost. Merely replacing an exact null projector by an OPM weak projector is unsafe, not novel theory.

### OPNO and FNO [R12,R21]

These use spectral/spatial representations to build neural operators. Polynomials of a physical feedback operator, with material and receiver endpoints, are mathematically different from spatial Chebyshev/Fourier bases. That distinction permits a different architecture; it does not itself prove that the architecture is better.

## 4. Claim ladder

Safe immediately: exact Schur formulation; mixed-span definition; algebraic equivalences; two-sided residual identity; conditional GN and prior-safety bounds; synthetic counterexamples; executable experiment protocol.

Safe only after G1: OPM is an effective reduced imaging representation for the tested 3D regime.

Safe only after G2: OPM accelerates end-to-end imaging at matched reconstruction quality and stated offline amortization.

Safe only after G3: material-fidelity degree adaptation improves that quality/cost frontier.

Safe only after G4/G5: OPM-conditioned priors add truth-directed benefit beyond deterministic regularization and generic neural heads.

Unsafe: degree 2 universally captures full-wave information; degree is automatically an inverse regularization parameter; current opportunity coverage predicts image error; low-rank resolvent approximates the full inverse in global operator norm; OPM weak space is the physical null space; local GN fidelity guarantees global truth recovery.

## 5. Likely strong-paper narrative

Working title: "Task-Conditioned Two-Sided Feedback Reduction for Full-Wave Electromagnetic Imaging."

Scientific sequence:

    material injection and receiver return
        -> two-sided Schur transfer approximation
        -> dual-residual material-Jacobian control
        -> audited inverse-update degree selection
        -> nonlinear 3D imaging quality/cost/robustness.

Mechanism explains the representation; experiments establish its value. A generic ROM implementation with small timing gains is unlikely to justify a strong-TAP claim by itself. A robust quality/cost improvement with meaningful high-contrast, near-contact, voxel, and noisy counterchecks would make the position substantially stronger. This is a research assessment, not an acceptance prediction.
