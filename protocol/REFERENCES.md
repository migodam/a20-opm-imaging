# Primary-source reference register

Audit date: 2026-10-05. URLs are provided as source locators, not as evidence that all versions were read in full. Specific access limitations are stated. The audit is broad enough to identify the principal overlaps; it is not a proof of exhaustive novelty.

## R01. SOM-Net

Y. Liu and collaborators, "SOM-Net: An Unrolled Deep Neural Network for Solving Inverse Scattering Problems," arXiv:2209.03567.
Source: https://arxiv.org/html/2209.03567v2
Relevant content: SOM-inspired unrolling, induced-current updates, analytical material updates, and losses involving current, data, and permittivity. A direct prior for claims of physics-guided electromagnetic neural inversion.

## R02. Wei-Chen induced-current learning

Zhun Wei and Xudong Chen, "Physics-Inspired Convolutional Neural Network for Solving Full-Wave Inverse Scattering Problems," IEEE Transactions on Antennas and Propagation (2019).
Author manuscript: https://www.ece.nus.edu.sg/stfpage/elechenx/Papers/Wei_TAP_2019.pdf
IEEE record: https://ieeexplore.ieee.org/document/8741152/
Relevant content: induced-current learning and division between major and learned minor current components. Access note: indexed primary-manuscript text was available; a later direct PDF open failed. Do not claim a new complete replication or a comprehensive experimental comparison from this audit.

## R03. GMRES / projection methods

Y. Saad and M. H. Schultz, "GMRES: A Generalized Minimal Residual Algorithm for Solving Nonsymmetric Linear Systems," SIAM Journal on Scientific and Statistical Computing 7(3), 1986.
Author-hosted teaching copy: https://web.stanford.edu/class/cme324/saad-schultz.pdf
Relevant content: Arnoldi projection and residual minimization for nonsymmetric systems. Distinguish Galerkin/FOM from GMRES; a mixed forward/adjoint OPM union need not itself have a single Arnoldi Hessenberg recurrence.

## R04. Interpolatory model reduction for nonlinear inversion

E. de Sturler, S. Gugercin, M. E. Kilmer, S. Chaturantabut, C. Beattie, and M. O'Connell, "Nonlinear Parametric Inversion using Interpolatory Model Reduction," arXiv:1311.0922; later SIAM Journal on Scientific Computing.
Source: https://arxiv.org/html/1311.0922
Relevant content: forward and Jacobian evaluations as transfer functions; reduced models used within nonlinear diffuse optical tomography. A central novelty obstacle for any generic reduced-forward-plus-GN claim.

## R05. Adaptive reduced models for parameter inversion

D. Munster and E. de Sturler, "Robust Parameter Inversion Using Adaptive Reduced Order Models," arXiv:2003.10938.
Source: https://arxiv.org/pdf/2003.10938
Relevant content: ROM accuracy control, conditional models, trust-region inversion, randomized objective estimates, and model updates. The page discussing conditional model accuracy was visually inspected. Adaptive reduced inversion is not new by itself.

## R06. Two-sided moment matching

J. Mao and G. Scarciotti, work on data-driven model reduction by two-sided moment matching, arXiv:2212.08589, later Automatica.
Source: https://arxiv.org/abs/2212.08589
Use with R04 as an antecedent for two-sided input/output projection. The exact finite-power proposition in OPM_IMAGING_THEORY.md is proved in this package; it is not attributed as a new general theorem or claimed to duplicate every assumption of this particular paper.

## R07. Faber approximation and nonnormal matrices

B. Beckermann and M. Crouzeix, work on Faber polynomials of matrices for non-convex sets, arXiv:1310.1356.
Source: https://arxiv.org/abs/1310.1356
Relevant content: polynomial approximation on complex domains with matrix-function bounds. Eigenvalues alone are not a robust error criterion for strongly nonnormal Maxwell operators.

## R08. Rational Krylov

S. Guettel, "Rational Krylov approximation of matrix functions: Numerical methods and optimal pole selection," 2013.
Author manuscript: https://www.guettel.com/download/rational-krylov-review.pdf
Relevant content: rational approximation and pole choice. Shifted systems have real costs; using exact L^{-1} as a pole solve to approximate L^{-1} would be circular for this project.

## R09. Stanford orthogonal-polynomial first-order algorithms

J. Lacotte and M. Pilanci, "Optimal Randomized First-Order Methods for Least-Squares Problems."
Author manuscript: https://web.stanford.edu/~pilanci/papers/OptimalPolynomials.pdf
Relevant content: orthogonal polynomials under a limiting spectral measure yield first-order recurrences for sketched least-squares problems. The spectral-measure and recurrence derivation was visually inspected. This is a concrete match to the brief's broad Stanford reference, not a claim that it is the uniquely intended paper. Its assumptions do not license a scalar three-term recurrence for arbitrary nonnormal Maxwell feedback.

## R10. Average-case acceleration

F. Pedregosa and D. Scieur, "Average-Case Acceleration Through Spectral Density Estimation," ICML 2020.
Primary proceedings: https://proceedings.mlr.press/v119/pedregosa20a.html
PDF: https://proceedings.mlr.press/v119/pedregosa20a/pedregosa20a.pdf
Relevant content: spectrum-conditioned polynomial iteration design for quadratic optimization. Closely related to R09, not a theorem about inverse-image truth error.

## R11. MatRL

S. Kim, R. V. Dwaraknath, L. Geng, and M. Pilanci, "MatRL: Provably Generalizable Iterative Algorithm Discovery via Monte-Carlo Tree Search," arXiv:2507.03833 (2025).
Source: https://arxiv.org/abs/2507.03833
Relevant content: selecting sequences of matrix iterations and step sizes for a matrix distribution and computing environment. Its distributional generalization assumptions must be re-established before applying it to changing Maxwell states; it does not itself solve inverse imaging.

## R12. Orthogonal Polynomial Neural Operator

Z. Liu and collaborators, "Render unto Numerics: Orthogonal Polynomial Neural Operator for PDEs with Non-periodic Boundary Conditions," arXiv:2206.12698, revised 2023.
Source: https://arxiv.org/html/2206.12698v2
Relevant content: spectral neural architectures with boundary-condition-compatible polynomial spatial representations. Spatial Chebyshev-type polynomials are different objects from polynomials of F_eff.

## R13. Null-space learning

J. Schwab, S. Antholzer, and M. Haltmeier, "Deep Null Space Learning for Inverse Problems: Convergence Analysis and Rates," arXiv:1806.06137.
Source: https://arxiv.org/html/1806.06137
Relevant content: learned corrections projected into the null space of a known linear forward operator and corresponding convergence theory. Null-space-restricted learned correction is not novel by itself. Approximate, nonlinear, state-dependent OPM weak spaces need additional audit and finite-step bounds.

## R14. Plug-and-play priors

S. V. Venkatakrishnan, C. A. Bouman, and B. Wohlberg, "Plug-and-Play Priors for Model Based Reconstruction," GlobalSIP 2013.
Author manuscript: https://engineering.purdue.edu/~bouman/Plug-and-Play/webdocs/GlobalSIP2013a.pdf
Relevant content: modular use of denoisers/priors in model-based reconstruction. An arbitrary learned denoiser is not automatically the proximal operator of a known scalar regularizer.

## R15. Neural Green's Operators

H. Melchers, J. Prins, and M. Abdelmalik, "Neural Green's Operators for Parametric Partial Differential Equations," arXiv:2406.01857, version 5 dated 2026-01-22; CMAME 455 (2026), 118893.
Source: https://arxiv.org/abs/2406.01857
Full text: https://arxiv.org/html/2406.01857
Relevant content: preserving linearity in forcing while learning nonlinear dependence on PDE coefficients, with structured Green-operator representations. Forcing-linearity and structured learned resolvents are not sufficient novelty for a revived A18-B route.

## R16. Residual-based neural-operator correction

"Residual-based Error Correction for Neural Operator Accelerated Infinite-Dimensional Bayesian Inverse Problems," arXiv:2210.03008; Journal of Computational Physics, 2023.
Source: https://arxiv.org/html/2210.03008v2
Relevant content: error correction in neural-operator-accelerated inverse problems. Physics approximation plus correction is an existing broad paradigm; distinguish numerical approximation correction from a material prior.

## R17. Distorted Born iterative method

W. C. Chew and Y. M. Wang, "Reconstruction of two-dimensional permittivity distribution using the distorted Born iterative method," IEEE Transactions on Medical Imaging 9(2), 1990. DOI: 10.1109/42.56334.
Author-institution record: https://experts.illinois.edu/en/publications/reconstruction-of-two-dimensional-permittivity-distribution-using/
IEEE record: https://ieeexplore.ieee.org/document/56334/
Relevant content: repeatedly updating the scattering background and linearized inverse update. Recomputing B and L at each material estimate is not a new nonlinear inversion principle.

## R18. Subspace-based optimization method

X. Chen, "Subspace-Based Optimization Method for Solving Inverse-Scattering Problems," IEEE Transactions on Geoscience and Remote Sensing.
IEEE record: https://ieeexplore.ieee.org/document/5210141/
Relevant content: current-subspace treatment of inverse scattering. Audit at the record/available primary-text level; use the group's full source manuscript for a final submission comparison.

## R19. Twofold SOM and FFT-TSOM

Y. Zhong and X. Chen, "Twofold subspace-based optimization method for solving inverse scattering problems," Inverse Problems 25, 085003 (2009). DOI: 10.1088/0266-5611/25/8/085003.
Related FFT-TSOM paper, IEEE Transactions on Antennas and Propagation 59(3), 2011.
IEEE record: https://ieeexplore.ieee.org/document/5678811/
Author manuscript: https://www.inversions-imaging.weebly.com/uploads/4/4/8/4/44842793/zhong_tap_2011.pdf
Relevant content: dimensional control and coarse-to-fine current-space strategies, with an FFT implementation. Access note: indexed author-manuscript text was available, but a direct PDF open returned a gateway error. Coarse-to-fine current dimension is an existing idea; a final manuscript should compare the full source and implementation, not rely solely on this audit.

## R20. Far-field approximation learning

T. Yin, K. Tan, and X. Chen, far-field approximation learning work, IEEE record 10041854 (2023).
IEEE record: https://ieeexplore.ieee.org/document/10041854/
Accessible related author conference abstract (PIERS 2024): https://author.piers.org/ac_api/preview.php?id=240114162453&t=ab
Relevant content supported by the author abstract: an approximate physics-derived inverse-Fourier input followed by learned 3D reflectivity reconstruction. Access limitation: the full IEEE journal text was blocked. This is an abstract-level architectural comparison, not a completed theorem/benchmark audit of the journal article.

## R21. Fourier Neural Operator

Z. Li and collaborators, "Fourier Neural Operator for Parametric Partial Differential Equations," arXiv:2010.08895.
Source: https://arxiv.org/abs/2010.08895
Relevant content: spectral neural operator baseline. Fourier spatial modes are not Maxwell O/P/M feedback degrees.

## R22. Electromagnetic PINO, 2026

Q. C. Dong and collaborators, "Physics-Informed Neural Operator for Electromagnetic Inverse Scattering Problems," arXiv:2603.25404, submitted 2026-03-26.
Source: https://arxiv.org/abs/2603.25404
Full text: https://arxiv.org/html/2603.25404
Relevant content: learnable dielectric tensor, induced-current neural operator, and joint state/data/TV objective. This is relevant recent prior art, not an independently reproduced performance result.

## R23. Akhiezer iteration

C. Ballew and T. Trogdon, work on the Akhiezer iteration, arXiv:2312.02384.
Source: https://arxiv.org/abs/2312.02384
Relevant content: orthogonal-polynomial iteration associated with spectral sets, including disjoint real intervals. Its spectral assumptions must not be transferred to arbitrary nonnormal Maxwell feedback without proof.
