# A21: Two-Sided GN Interpolation Anatomy

## Decision

Run a **frozen, rank-matched, primal/dual oracle anatomy**, not another degree sweep or nonlinear reconstruction campaign. The immediate order is:

1. Validate the exact constrained theorem on tiny synthetic complex systems.
2. Verify the real backend's packing, frozen objective, constrained reference and tied adjoint.
3. Run common-Galerkin primal/dual controls on the existing five Gaussian late states.
4. Add the two Petrov controls to distinguish the interpolation mechanism from the trial/test architecture.
5. Stop and report. Online algorithms and NN are not authorized by this task.

The exact theorem is true for a nonempty closed convex feasible set and a convex reduced quadratic. Uniqueness follows from positive definiteness of the reduced Hessian; positive definite Lambda is sufficient. Current containment is sufficient only with a nonsingular reduced core.

**Important correction:** small relative primal and dual errors alone do not certify a small step error. Curvature, the full/reduced metric comparison, full/reference KKT accuracy, constraint normals and the size of the reference step all matter. See `APPROXIMATE_ERROR_BOUND.md`.

## Proven here, versus still unmeasured

Derived and numerically checked here: constrained interpolation; primal/dual defect decomposition; Euclidean and energy-norm bounds; reduced and full quadratic-gap bounds; complex-to-real pullback; shared-source current protection; Petrov/Schur identities; illustrative counterexamples.

The attached task reports early/late A20 behavior and the protected-primal oracle (about 0.0487% primal error and 366% relative H-step error). These are **user-supplied project results, not independently re-run in this package**. No A20 repository, five-state cache, backend solver code or new full-wave experiment was available here. The validation folder contains synthetic algebra tests, explicitly not Maxwell reconstruction results.

## Files

| File | Purpose |
|---|---|
| `TWO_SIDED_GN_THEOREM.md` | Exact theorem, normal-cone proof, sufficiency versus necessity |
| `APPROXIMATE_ERROR_BOUND.md` | Norms, gaps, approximate solvers and corrected killer test |
| `MAXWELL_PRIMAL_DUAL_INTERPRETATION.md` | Real packing, whitening, six-source currents, frozen-state conventions |
| `PETROV_GALERKIN_TASK_INTERPOLATION.md` | Trial/test proof, stability and rank/memory distinction |
| `OPM_PRIMAL_DUAL_ARCHITECTURE.md` | Exact retained-U Schur realization and the correct adjoint seed |
| `CLOSEST_PRIOR_AUDIT.md` | Primary-source comparison and novelty boundary |
| `ORACLE_ANATOMY_SPEC.md` | Complete minimal experiment and metric definitions |
| `ONLINE_ALGORITHM_CANDIDATES.md` | Conditional future algorithms; includes a frozen-quadratic descent result |
| `GO_NO_GO_GATES.md` | Predeclared interpretation and stop conditions |
| `CODEX_TWO_SIDED_ANATOMY.md` | Execution instructions for the coding agent |
| `VALIDATION_REPORT.md` | Executed synthetic results and limitations |
| `REFERENCES.md` | Stable primary-source identifiers and access scope |

The consolidated `COMPLETE_A21_MEMO.md` contains all substantive documents.

## Immediate Codex instruction

Read `CODEX_TWO_SIDED_ANATOMY.md`, then the linked theory and specification files. Locate the existing A20-R1 backend and five-state manifest. Preserve its actual frozen quadratic. Implement only the anatomy and consistency tests. Do not raise polynomial degree, train NN, modify the material parameterization, launch nonlinear imaging, or redesign the full solver.

A short Plan Mode pass is appropriate for backend mapping and the frozen manifest. Once those are resolved, implement and run the staged experiment; do not spend a second research cycle inventing a different experiment.
