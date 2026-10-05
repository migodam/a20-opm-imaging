# Decision gates: proposed thresholds, not experimental results

All thresholds below are prespecified engineering decisions that may be amended ONCE before the blind test, with the amendment logged. They are not mathematical constants, literature claims, or outcomes of the supplied A18/A19 project. Report all failed scenes and fallback costs.

## G0: mathematical/backend integrity (mandatory)

Pass complex current adjoints and REAL material adjoints; Schur/reduced-core equivalence; fixed-basis derivative finite differences; frozen-state and reduced-state tangent distinctions; Galerkin versus least-squares derivative distinctions; feasibility/KKT handling; source/frequency stacking and whitening. Aim for relative algebra errors below 1e-9 in complex128 synthetic tests and 1e-5 in complex64 backend checks, relaxing only with a documented conditioning/roundoff explanation. Run the included counterexamples as regression tests.

A failed integrity check means repair implementation, not reject the scientific representation. No neural training is allowed before G0.

## G1: actual imaging representation

Start with six independent existing 3D objects. Use identical initialization, material constraints, regularizer/LM rules, full objective acceptance policy, and stopping criteria. Compare full GN, OPM degrees 0-3, receiver/SOM ROM, and rank/action-matched ordinary Krylov. Add degrees 4-5 in replay when needed before concluding that shallow degree failed.

Proposed opportunity gate: a surviving OPM method has final relative material error no more than 5% worse than the full-GN reference in the median and no more than 15% worse on any pilot scene, while reducing current rank substantially (an exploratory target is <=35% of the full discrete current dimension). In near-zero-error cases use an absolute error floor fixed before comparison. Also require no unexplained objective/stagnation failures. Full-GN truth error can itself be poor; closeness to full GN is not enough for a strong imaging claim.

For one-step frozen replay, use median relative H-step error <=5% with a reported upper tail. These margins are pilot screening rules, not statistical confirmation from six objects. A method must also improve the quality/cost Pareto frontier over generic ROMs before an OPM-specific paper claim is credible.

## G2: total deployment value

Count basis setup, orthogonalization, seed construction, projected core factorization, all forward and adjoint actions, nonlinear trials, certification/audit calls, refreshes, fallbacks, and synchronization. Separate one-time offline costs and their actual number of deployments; report both cold and warm cost.

Proposed speed gate: at least 20% median end-to-end wall-time reduction versus full GN at matched reconstruction quality, with no catastrophic slow outlier and competitive performance against the best generic ROM. Merely reducing stored rank or one Jacobian action is not a pass. Failure kills an acceleration claim, not necessarily the representation interpretation.

## G3: adaptive degree

Adjacent-degree update stability may trigger an audit but cannot certify termination. Include the delayed nilpotent-path counterexample. Require full stationarity/KKT audits or genuinely justified residual/stability bounds at declared checkpoints, plus full objective globalization. Report audit error, false stopping, degrees per outer iteration, and total cost.

GO only if adaptation preserves G1 quality and improves total cost over a fixed-degree survivor. Otherwise use fixed degree; no need to force a degree-controller paper.

## G4A: numerical compensation

Separate e_approx=x_full-x_OPM from e_inverse=x_truth-x_full. Fit a simple, object-disjoint ridge predictor for e_approx or its task projection before a neural model. Require improvement over a zero predictor and a constant/family predictor on held-out objects; a provisional normalized error reduction of 10% is a screening target. Inspect boundary, near-contact, real/imaginary, contrast, and frequency structure.

Even a predictable e_approx must beat one extra OPM degree or a deterministic full correction at matched total cost. Otherwise kill numerical neural compensation.

## G4B: prior-safe weak information

Use declared material/noise scaling. Audit the entire proposed weak span with full tangent actions, or provide a rigorous restricted operator bound; random samples alone are insufficient for a certificate. Verify reduced weak directions are genuinely weak under full physics. Require a stable weak eigenspace or use a soft spectral filter with an explicit leakage budget.

If the weak dimension is zero, the prior is exactly disabled. If weak directions exist but do not correlate with held-out reconstruction uncertainty, kill the weak-prior route in that regime. Gaussian 54D is a negative control, not a reason to invent a large nullspace.

## G5: neural contribution

Only after G4A or G4B, run a small pilot. For a prior claim, require at least 10% median held-out truth-error improvement over the best cost-matched deterministic regularizer, full-data/feasibility checks, low strong-space leakage, and no serious tail degradation. For NN-native novelty, also require meaningful channel/degree-label and phase-coupling ablations, plus gauge invariance.

## What kills the practical OPM imaging direction?

After G0 passes, modest degree extension and stable projection alternatives have been tried, and seed budgets are fair:

1. OPM needs nearly full current rank to match full-GN imaging on ordinary target scenes, or repeatedly needs full fallbacks whose total cost removes the advantage.
2. Rank/action-matched generic Krylov/POD/SOM ROMs dominate OPM in both quality and cost, without an interpretable robustness niche.
3. Claimed gains disappear under independent objects, consistent nonlinear derivatives, proper full objective evaluation, or inclusion of preprocessing/audits.

Together these justify stopping this scoped practical program. They do not prove that every possible OPM-related representation in all future regimes is useless.

Degree-2 failure alone, nonmonotone risk, no weak directions in 54D, failure of NN training, or lack of a new Krylov theorem does NOT kill deterministic OPM imaging by itself.
