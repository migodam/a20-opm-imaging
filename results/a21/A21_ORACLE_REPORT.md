> Final review: T0 PASS; T1 LATE_GN_TWO_SIDED_FIDELITY_CONFIRMED for the five frozen exposed states. The automatic classifications below are preserved as pre-review evidence.

# A21 Oracle Anatomy Report

## T0: algebra and implementation consistency

Recorded status: `PASS`. Automatically accepted as resolved: `True`.

T0 concerns packing, whitening, tied adjoints, source order, constrained KKT, the two-sided theorem, defect identities and solver-aware bounds. Synthetic tests establish implementation checks; the real cached-state checks must also be recorded before physical interpretation.

## T1: complete frozen five-state diagnosis

Provisional measured classification: `FULL_MEASURED_SUPPORT_PENDING_CODEX_REVIEW`. Final scientific interpretation: `LATE_GN_TWO_SIDED_FIDELITY_CONFIRMED`; see the signed-off Chinese report and GATE_DECISION.json.

The table retains every registered state and arm. Percentages use the unmodified reference H norm; an ill-scaled denominator or unavailable diagnostic makes the gate unassessable. No surviving-state median replaces missing states.

| State | Arm | Status | Assessable | H_F error | Absolute H_F error | Reference H norm | Raw H_F bound | Normal-adjusted bound | Consistency |
|---|---|---|---|---:|---:|---:|---:|---:|---|
| 2001/17 | BASE_G | OK | True | 2.6951 | 0.0019223 | 0.00071327 | 0.0053474 | 0.0053474 | True |
| 2001/17 | PRIMAL_G | OK | True | 2.62 | 0.0018688 | 0.00071327 | 0.0032608 | 0.0032608 | True |
| 2001/17 | DUAL_G | OK | True | 0.80654 | 0.00057528 | 0.00071327 | 0.0028344 | 0.0028344 | True |
| 2001/17 | BOTH_G | OK | True | 1.3114e-13 | 9.3542e-17 | 0.00071327 | 1.4423e-16 | 5.756e-12 | True |
| 2001/17 | RANDOM_G | OK | True | 2.8015 | 0.0019982 | 0.00071327 | 0.0055353 | 0.0055353 | True |
| 2001/17 | BOTH_PG | OK | True | 5.603e-14 | 3.9965e-17 | 0.00071327 | 6.4863e-17 | 5.4123e-12 | True |
| 2001/17 | RANDOM_PG | OK | True | 2.31 | 0.0016477 | 0.00071327 | 0.0054282 | 0.0054282 | True |
| 2005/17 | BASE_G | OK | True | 4.4969 | 0.0034966 | 0.00077755 | 0.017408 | 0.017408 | True |
| 2005/17 | PRIMAL_G | OK | True | 4.2088 | 0.0032726 | 0.00077755 | 0.0051269 | 0.0051269 | True |
| 2005/17 | DUAL_G | OK | True | 0.98628 | 0.00076688 | 0.00077755 | 0.011928 | 0.011928 | True |
| 2005/17 | BOTH_G | OK | True | 1.2292e-13 | 9.5574e-17 | 0.00077755 | 2.0843e-16 | 8.5569e-12 | True |
| 2005/17 | RANDOM_G | OK | True | 4.712 | 0.0036638 | 0.00077755 | 0.017577 | 0.017577 | True |
| 2005/17 | BOTH_PG | OK | True | 1.0646e-13 | 8.2775e-17 | 0.00077755 | 1.5539e-16 | 6.7178e-12 | True |
| 2005/17 | RANDOM_PG | OK | True | 4.5295 | 0.0035219 | 0.00077755 | 0.017209 | 0.017209 | True |
| 2003/17 | BASE_G | OK | True | 1.4616 | 0.005309 | 0.0036324 | 0.013112 | 0.013112 | True |
| 2003/17 | PRIMAL_G | OK | True | 1.4431 | 0.0052421 | 0.0036324 | 0.010773 | 0.010773 | True |
| 2003/17 | DUAL_G | OK | True | 0.4897 | 0.0017788 | 0.0036324 | 0.0052585 | 0.0052585 | True |
| 2003/17 | BOTH_G | OK | True | 4.3956e-11 | 1.5967e-13 | 0.0036324 | 2.5507e-13 | 4.6255e-10 | True |
| 2003/17 | RANDOM_G | OK | True | 1.5309 | 0.0055606 | 0.0036324 | 0.013903 | 0.013903 | True |
| 2003/17 | BOTH_PG | OK | True | 2.3345e-11 | 8.4797e-14 | 0.0036324 | 1.4905e-13 | 3.9966e-10 | True |
| 2003/17 | RANDOM_PG | OK | True | 1.4457 | 0.0052512 | 0.0036324 | 0.014125 | 0.014125 | True |
| 2007/17 | BASE_G | OK | True | 3.3645 | 0.0019505 | 0.00057973 | 0.015056 | 0.015056 | True |
| 2007/17 | PRIMAL_G | OK | True | 2.8204 | 0.0016351 | 0.00057973 | 0.0024455 | 0.0024455 | True |
| 2007/17 | DUAL_G | OK | True | 1.0078 | 0.00058427 | 0.00057973 | 0.0088717 | 0.0088717 | True |
| 2007/17 | BOTH_G | OK | True | 1.5008e-13 | 8.7005e-17 | 0.00057973 | 1.1748e-16 | 3.3087e-12 | True |
| 2007/17 | RANDOM_G | OK | True | 3.4022 | 0.0019724 | 0.00057973 | 0.015256 | 0.015256 | True |
| 2007/17 | BOTH_PG | OK | True | 8.1283e-14 | 4.7122e-17 | 0.00057973 | 6.699e-17 | 2.8661e-12 | True |
| 2007/17 | RANDOM_PG | OK | True | 2.2804 | 0.001322 | 0.00057973 | 0.019891 | 0.019891 | True |
| 2013/17 | BASE_G | OK | True | 1.5649 | 0.0020114 | 0.0012853 | 0.015445 | 0.015445 | True |
| 2013/17 | PRIMAL_G | OK | True | 1.1138 | 0.0014315 | 0.0012853 | 0.0023322 | 0.0023322 | True |
| 2013/17 | DUAL_G | OK | True | 0.98731 | 0.001269 | 0.0012853 | 0.012103 | 0.012103 | True |
| 2013/17 | BOTH_G | OK | True | 1.2351e-13 | 1.5874e-16 | 0.0012853 | 2.382e-16 | 1.6468e-11 | True |
| 2013/17 | RANDOM_G | OK | True | 1.6582 | 0.0021312 | 0.0012853 | 0.015974 | 0.015974 | True |
| 2013/17 | BOTH_PG | OK | True | 4.4213e-14 | 5.6826e-17 | 0.0012853 | 1.7993e-16 | 1.2068e-11 | True |
| 2013/17 | RANDOM_PG | OK | True | 1.4423 | 0.0018537 | 0.0012853 | 0.034302 | 0.034302 | True |

### Stationarity, curvature and full quadratic gap

The saved metrics retain the primal endpoint, material-vector dual endpoint, amplified primal contribution, their vector sum, cancellation, both solver defects, scaled stationarity, the two Hessians, mu and beta. The raw solver-aware bound and the normal-allowance bound are distinct.

The full-gap identity is evaluated with both normal work and rho_F work: `q_F(s_R)-q_F(s_F) = 0.5 ||s_R-s_F||_HF^2 - n_F^T(s_R-s_F) + rho_F^T(s_R-s_F)`. Predicted-reduction ratios are undefined when their declared denominator is negligible.

| State | Arm | Primal defect | Dual defect | Amplified primal | eta sum | b_dual | b_primal | rho_F | rho_R | mu | beta | Full gap | Normal work | rho_F work |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2001/17 | BASE_G | 0.0021312 | 0.00038478 | 0.00072965 | 0.00079621 | 0.0014793 | 0.0020518 | 1.4998e-18 | 2.3214e-12 | 0.00193 | 5.0522 | 1.8569e-06 | 9.2894e-09 | -2.9878e-21 |
| 2001/17 | PRIMAL_G | 1.715e-17 | 0.00039393 | 1.1053e-17 | 0.00039393 | 0.0014819 | 8.2219e-18 | 1.4998e-18 | 2.8324e-18 | 0.00040853 | 4.8418 | 1.7462e-06 | 9.9262e-24 | -1.0238e-21 |
| 2001/17 | DUAL_G | 0.0017708 | 1.0847e-17 | 0.00050261 | 0.00050261 | 5.1505e-17 | 0.0016735 | 1.4998e-18 | 1.6869e-12 | 0.001776 | 2.8687 | 1.6547e-07 | 2.3161e-22 | -2.4141e-21 |
| 2001/17 | BOTH_G | 1.8155e-17 | 1.6142e-17 | 1.1423e-17 | 2.051e-17 | 8.8616e-17 | 8.9162e-18 | 1.4998e-18 | 1.997e-18 | 0.00041998 | 2.8219 | 5.0822e-21 | 3.6127e-24 | 2.7639e-35 |
| 2001/17 | RANDOM_G | 0.0021769 | 0.00041029 | 0.00083055 | 0.00087539 | 0.0014868 | 0.0020983 | 1.4998e-18 | 2.5565e-18 | 0.0018912 | 5.1773 | 2.003e-06 | 6.5888e-09 | -2.3662e-21 |
| 2001/17 | BOTH_PG | 4.3683e-17 | 2.2736e-17 | 3.9908e-17 | 3.6216e-17 | 2.2226e-17 | 3.2096e-17 | 1.4998e-18 | 5.542e-18 | 0.00044851 | 1.7023 | 3.3881e-21 | -6.1975e-24 | -1.6687e-34 |
| 2001/17 | RANDOM_PG | 0.0026017 | 0.00039046 | 0.00071633 | 0.00076925 | 0.0013465 | 0.0025346 | 1.4998e-18 | 5.7022e-12 | 0.0031873 | 4.3576 | 1.3574e-06 | -2.9779e-23 | -3.4212e-21 |
| 2005/17 | BASE_G | 0.0083797 | 0.00070675 | 0.0059453 | 0.0059421 | 0.0025296 | 0.0083498 | 1.5084e-17 | 1.1227e-17 | 0.0046352 | 4.1297 | 6.1449e-06 | 3.1861e-08 | -3.8289e-20 |
| 2005/17 | PRIMAL_G | 3.4011e-17 | 0.00069163 | 1.9139e-17 | 0.00069163 | 0.0025469 | 1.3386e-17 | 1.5084e-17 | 1.4746e-17 | 0.00027125 | 4.0522 | 5.3719e-06 | 1.6949e-08 | 1.1167e-20 |
| 2005/17 | DUAL_G | 0.0070989 | 3.2474e-17 | 0.005432 | 0.005432 | 1.2967e-16 | 0.0070635 | 1.5084e-17 | 2.5137e-18 | 0.003638 | 2.8518 | 3.1497e-07 | 2.0913e-08 | -5.4563e-20 |
| 2005/17 | BOTH_G | 3.718e-17 | 2.5615e-17 | 1.9739e-17 | 3.0839e-17 | 8.917e-17 | 1.4805e-17 | 1.5084e-17 | 8.2256e-18 | 0.00027358 | 3.028 | -1.0164e-20 | 6.5367e-24 | -1.5743e-33 |
| 2005/17 | RANDOM_G | 0.0083094 | 0.00072355 | 0.0059742 | 0.0059531 | 0.0026191 | 0.0082793 | 1.5084e-17 | 4.724e-12 | 0.0047039 | 4.27 | 6.7455e-06 | 3.3757e-08 | -3.5583e-20 |
| 2005/17 | BOTH_PG | 6.2253e-17 | 1.3652e-17 | 4.6739e-17 | 5.3062e-17 | 3.5692e-17 | 4.521e-17 | 1.5084e-17 | 9.4748e-18 | 0.00026517 | 1.8663 | -1.6941e-20 | 6.0853e-24 | -3.8336e-33 |
| 2005/17 | RANDOM_PG | 0.0084348 | 0.00074018 | 0.0061715 | 0.0061596 | 0.0026118 | 0.0084048 | 1.5084e-17 | 5.6108e-18 | 0.0062088 | 3.8888 | 6.238e-06 | 3.5943e-08 | -4.5176e-20 |
| 2003/17 | BASE_G | 0.0043797 | 0.0006481 | 0.0012095 | 0.0013035 | 0.0049511 | 0.0036975 | 2.4092e-14 | 2.7075e-18 | 0.00041876 | 4.4866 | 1.4338e-05 | 2.4581e-07 | -9.4609e-17 |
| 2003/17 | PRIMAL_G | 4.4466e-17 | 0.00067172 | 1.2782e-17 | 0.00067172 | 0.0051711 | 2.0927e-17 | 2.4092e-14 | 2.7867e-18 | 0.00036905 | 4.3399 | 1.3923e-05 | 1.8321e-07 | -7.3304e-17 |
| 2003/17 | DUAL_G | 0.0039302 | 6.9899e-18 | 0.00064816 | 0.00064816 | 4.5797e-17 | 0.0032026 | 2.4092e-14 | 2.7111e-18 | 0.00040298 | 2.696 | 1.582e-06 | 1.702e-20 | -5.9201e-17 |
| 2003/17 | BOTH_G | 4.3998e-17 | 7.435e-18 | 1.0831e-17 | 1.3457e-17 | 5.8854e-17 | 1.8056e-17 | 2.4092e-14 | 3.3424e-18 | 0.00036437 | 2.6567 | -2.7105e-20 | 1.4592e-20 | -1.8615e-26 |
| 2003/17 | RANDOM_G | 0.0045318 | 0.00067704 | 0.0012996 | 0.0014319 | 0.0050817 | 0.0038504 | 2.4092e-14 | 4.6556e-13 | 0.00038472 | 4.408 | 1.5829e-05 | 3.6881e-07 | -7.6254e-17 |
| 2003/17 | BOTH_PG | 2.2066e-16 | 8.4815e-17 | 5.145e-16 | 5.2086e-16 | 9.7273e-17 | 2.0307e-16 | 2.4092e-14 | 3.885e-17 | 0.00038747 | 1.9411 | -5.421e-20 | 1.5106e-20 | -7.2403e-27 |
| 2003/17 | RANDOM_PG | 0.0062503 | 0.00065835 | 0.0017615 | 0.0018278 | 0.004497 | 0.0057771 | 2.4092e-14 | 3.0756e-12 | 0.00077611 | 3.5494 | 1.419e-05 | 4.0273e-07 | -8.8851e-17 |
| 2007/17 | BASE_G | 0.0069272 | 0.000377 | 0.0063654 | 0.006396 | 0.001317 | 0.0069056 | 9.1285e-18 | 2.2205e-18 | 0.0056689 | 4.4862 | 1.9079e-06 | 5.6653e-09 | -1.2528e-20 |
| 2007/17 | PRIMAL_G | 2.8446e-17 | 0.00037029 | 1.4941e-17 | 0.00037029 | 0.0011843 | 1.0997e-17 | 9.1285e-18 | 3.5764e-18 | 0.00024397 | 4.2639 | 1.3367e-06 | -2.8951e-24 | -9.043e-21 |
| 2007/17 | DUAL_G | 0.0058132 | 1.3652e-17 | 0.0046338 | 0.0046338 | 4.2753e-17 | 0.0057874 | 9.1285e-18 | 8.1348e-19 | 0.0053859 | 2.3498 | 1.7805e-07 | 7.3641e-09 | -1.2304e-20 |
| 2007/17 | BOTH_G | 2.9587e-17 | 1.4757e-17 | 1.4791e-17 | 2.0387e-17 | 6.8448e-17 | 1.0989e-17 | 9.1285e-18 | 3.1267e-18 | 0.00024414 | 2.4085 | -8.4703e-22 | -2.8477e-25 | -8.8951e-34 |
| 2007/17 | RANDOM_G | 0.0068143 | 0.00039328 | 0.0061234 | 0.0061547 | 0.0013463 | 0.0067921 | 9.1285e-18 | 2.032e-18 | 0.0055718 | 4.827 | 1.9521e-06 | 7.0115e-09 | -1.5697e-20 |
| 2007/17 | BOTH_PG | 4.7138e-17 | 1.2963e-17 | 5.2204e-17 | 4.4106e-17 | 1.4646e-17 | 3.4856e-17 | 9.1285e-18 | 7.1157e-18 | 0.00024755 | 1.8073 | -4.2352e-21 | -7.1158e-25 | -1.1021e-33 |
| 2007/17 | RANDOM_PG | 0.010708 | 0.00049448 | 0.0086968 | 0.0087468 | 0.0010868 | 0.010694 | 9.1285e-18 | 1.4183e-18 | 0.011811 | 3.424 | 8.855e-07 | 1.1614e-08 | -1.4416e-20 |
| 2013/17 | BASE_G | 0.008287 | 0.00050192 | 0.0093681 | 0.0094152 | 0.0013661 | 0.0081962 | 1.0759e-17 | 3.7254e-18 | 0.004043 | 3.2326 | 2.1614e-06 | 1.3863e-07 | 1.9112e-20 |
| 2013/17 | PRIMAL_G | 6.1686e-17 | 0.00051047 | 5.0056e-17 | 0.00051047 | 0.0012889 | 2.6523e-17 | 1.0759e-17 | 5.7894e-18 | 0.00028505 | 3.2742 | 1.034e-06 | 9.3295e-09 | 9.2408e-21 |
| 2013/17 | DUAL_G | 0.0079733 | 2.7232e-17 | 0.0076924 | 0.0076924 | 9.6567e-17 | 0.0078803 | 1.0759e-17 | 1.9666e-18 | 0.0039165 | 2.3589 | 9.0556e-07 | 1.0043e-07 | 1.185e-20 |
| 2013/17 | BOTH_G | 6.4131e-17 | 3.5456e-17 | 5.0896e-17 | 6.0581e-17 | 1.5406e-16 | 2.609e-17 | 1.0759e-17 | 1.7997e-17 | 0.00028012 | 2.2612 | -1.6941e-21 | 1.6752e-23 | -7.2118e-34 |
| 2013/17 | RANDOM_G | 0.0083673 | 0.00053461 | 0.0095004 | 0.0095545 | 0.001485 | 0.0082777 | 1.0759e-17 | 4.1835e-18 | 0.0038554 | 3.4151 | 2.4095e-06 | 1.3838e-07 | 2.1532e-20 |
| 2013/17 | BOTH_PG | 1.2926e-16 | 2.1827e-17 | 1.1747e-16 | 1.2417e-16 | 3.7059e-17 | 1.0781e-16 | 1.0759e-17 | 9.4098e-18 | 0.00029136 | 1.7197 | 8.4703e-21 | 2.2772e-23 | -3.0644e-34 |
| 2013/17 | RANDOM_PG | 0.021533 | 0.00055928 | 0.015393 | 0.015444 | 0.0013334 | 0.021498 | 1.0759e-17 | 2.4315e-18 | 0.010873 | 2.4898 | 1.8559e-06 | 1.3776e-07 | 1.6217e-20 |

Per-source values and their defined/ill-scaled flags are preserved in each capture record. Aggregate capture never substitutes for all source columns.

| State | Arm | Primal trial aggregate | Primal trial worst source | Dual test aggregate | Dual test worst source | Full primal residual | Full adjoint residual |
|---|---|---:|---:|---:|---:|---:|---:|
| 2001/17 | BASE_G | 0.91102 | 0.93717 | 0.13374 | 0.17024 | 5.8717e-15 | 3.2876e-15 |
| 2001/17 | PRIMAL_G | 6.8001e-16 | 8.907e-16 | 0.13591 | 0.17212 | 5.8717e-15 | 3.2876e-15 |
| 2001/17 | DUAL_G | 0.91241 | 0.93747 | 7.7813e-16 | 9.0663e-16 | 5.8717e-15 | 3.2876e-15 |
| 2001/17 | BOTH_G | 6.7838e-16 | 8.932e-16 | 7.9553e-16 | 9.6059e-16 | 5.8717e-15 | 3.2876e-15 |
| 2001/17 | RANDOM_G | 0.91987 | 0.94791 | 0.13879 | 0.17594 | 5.8717e-15 | 3.2876e-15 |
| 2001/17 | BOTH_PG | 6.8001e-16 | 8.907e-16 | 7.7813e-16 | 9.0663e-16 | 5.8717e-15 | 3.2876e-15 |
| 2001/17 | RANDOM_PG | 0.91498 | 0.93995 | 0.13626 | 0.1728 | 5.8717e-15 | 3.2876e-15 |
| 2005/17 | BASE_G | 0.7729 | 0.79165 | 0.1309 | 0.15951 | 5.8898e-15 | 3.2561e-15 |
| 2005/17 | PRIMAL_G | 1.461e-15 | 2.2295e-15 | 0.12998 | 0.16023 | 5.8898e-15 | 3.2561e-15 |
| 2005/17 | DUAL_G | 0.77028 | 0.78893 | 1.4407e-15 | 1.5653e-15 | 5.8898e-15 | 3.2561e-15 |
| 2005/17 | BOTH_G | 1.4586e-15 | 2.233e-15 | 1.4394e-15 | 1.6102e-15 | 5.8898e-15 | 3.2561e-15 |
| 2005/17 | RANDOM_G | 0.7842 | 0.80242 | 0.13362 | 0.16223 | 5.8898e-15 | 3.2561e-15 |
| 2005/17 | BOTH_PG | 1.461e-15 | 2.2295e-15 | 1.4407e-15 | 1.5653e-15 | 5.8898e-15 | 3.2561e-15 |
| 2005/17 | RANDOM_PG | 0.78056 | 0.79953 | 0.13236 | 0.16137 | 5.8898e-15 | 3.2561e-15 |
| 2003/17 | BASE_G | 0.9256 | 0.94905 | 0.21284 | 0.27897 | 5.9304e-15 | 3.4607e-15 |
| 2003/17 | PRIMAL_G | 6.7792e-16 | 1.1267e-15 | 0.21804 | 0.28295 | 5.9304e-15 | 3.4607e-15 |
| 2003/17 | DUAL_G | 0.92573 | 0.94833 | 7.0854e-16 | 7.9981e-16 | 5.9304e-15 | 3.4607e-15 |
| 2003/17 | BOTH_G | 6.8766e-16 | 1.1221e-15 | 7.3516e-16 | 9.1843e-16 | 5.9304e-15 | 3.4607e-15 |
| 2003/17 | RANDOM_G | 0.93432 | 0.95447 | 0.22707 | 0.28846 | 5.9304e-15 | 3.4607e-15 |
| 2003/17 | BOTH_PG | 6.7792e-16 | 1.1267e-15 | 7.0854e-16 | 7.9981e-16 | 5.9304e-15 | 3.4607e-15 |
| 2003/17 | RANDOM_PG | 0.93009 | 0.95153 | 0.21895 | 0.28493 | 5.9304e-15 | 3.4607e-15 |
| 2007/17 | BASE_G | 0.80228 | 0.82769 | 0.12914 | 0.21311 | 5.7823e-15 | 3.3092e-15 |
| 2007/17 | PRIMAL_G | 7.4107e-16 | 1.093e-15 | 0.12758 | 0.2147 | 5.7823e-15 | 3.3092e-15 |
| 2007/17 | DUAL_G | 0.79185 | 0.82366 | 9.3926e-16 | 1.2183e-15 | 5.7823e-15 | 3.3092e-15 |
| 2007/17 | BOTH_G | 7.4791e-16 | 1.107e-15 | 9.5939e-16 | 1.161e-15 | 5.7823e-15 | 3.3092e-15 |
| 2007/17 | RANDOM_G | 0.81424 | 0.83676 | 0.13268 | 0.21849 | 5.7823e-15 | 3.3092e-15 |
| 2007/17 | BOTH_PG | 7.4107e-16 | 1.093e-15 | 9.3926e-16 | 1.2183e-15 | 5.7823e-15 | 3.3092e-15 |
| 2007/17 | RANDOM_PG | 0.81011 | 0.83326 | 0.13097 | 0.21659 | 5.7823e-15 | 3.3092e-15 |
| 2013/17 | BASE_G | 0.90079 | 0.91251 | 0.12432 | 0.16499 | 5.8381e-15 | 2.9098e-15 |
| 2013/17 | PRIMAL_G | 8.183e-16 | 1.2075e-15 | 0.12572 | 0.16662 | 5.8381e-15 | 2.9098e-15 |
| 2013/17 | DUAL_G | 0.89782 | 0.90203 | 1.3828e-15 | 1.6423e-15 | 5.8381e-15 | 2.9098e-15 |
| 2013/17 | BOTH_G | 8.177e-16 | 1.1989e-15 | 1.3884e-15 | 1.6773e-15 | 5.8381e-15 | 2.9098e-15 |
| 2013/17 | RANDOM_G | 0.90978 | 0.91784 | 0.12857 | 0.16768 | 5.8381e-15 | 2.9098e-15 |
| 2013/17 | BOTH_PG | 8.183e-16 | 1.2075e-15 | 1.3828e-15 | 1.6423e-15 | 5.8381e-15 | 2.9098e-15 |
| 2013/17 | RANDOM_PG | 0.90692 | 0.91398 | 0.12656 | 0.16704 | 5.8381e-15 | 2.9098e-15 |

### Mechanism and Petrov architecture

Automatic full support requires all five well-scaled BOTH_G states at or below 5%, all required consistency checks, a failing PRIMAL_G with a measured relevant weighted dual contribution, and a failing rank-matched RANDOM_G. This is a conservative evidence pattern for Codex review. Exact current capture alone is not a step theorem.

| State | Provisional mechanism status | PRIMAL dual evidence | RANDOM_G discriminates | Petrov instance | Alternative explanations |
|---|---|---|---|---|---|
| 2001/17 | MEASURED_GALERKIN_CAUSAL_PATTERN_PRESENT_REVIEW_REQUIRED | True | True | PG_INSTANCE_PASSES_WITH_RANDOM_DISCRIMINATION | none recorded |
| 2005/17 | MEASURED_GALERKIN_CAUSAL_PATTERN_PRESENT_REVIEW_REQUIRED | True | True | PG_INSTANCE_PASSES_WITH_RANDOM_DISCRIMINATION | none recorded |
| 2003/17 | MEASURED_GALERKIN_CAUSAL_PATTERN_PRESENT_REVIEW_REQUIRED | True | True | PG_INSTANCE_PASSES_WITH_RANDOM_DISCRIMINATION | none recorded |
| 2007/17 | MEASURED_GALERKIN_CAUSAL_PATTERN_PRESENT_REVIEW_REQUIRED | True | True | PG_INSTANCE_PASSES_WITH_RANDOM_DISCRIMINATION | none recorded |
| 2013/17 | MEASURED_GALERKIN_CAUSAL_PATTERN_PRESENT_REVIEW_REQUIRED | True | True | PG_INSTANCE_PASSES_WITH_RANDOM_DISCRIMINATION | none recorded |

Petrov fidelity is assessed separately. Equal k_Z and k_W do not mean equal basis memory; a Petrov arm stores two bases. A frozen-step oracle pass establishes no online advantage, nonlinear reconstruction success or cost benefit.

### Current solves, core, rank, memory and paid cost

Per-source and aggregate primal/dual capture residuals, source ordering, oracle backward errors, core singular values/condition/factorization residual, actual ranks and memory, operator calls and RHS counts remain in the CSV and per-state JSON. Shared state setup is billed once in driver receipts; per-arm deltas are not a standalone deployment wall time.

| State | Arm | k_Z | k_W | Union rank | Basis bytes | Core sigma_min | Core condition | Forward RHS | Adjoint RHS | CPU seconds | Wall seconds |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2001/17 | BASE_G | 56 | 56 | 56 | 4.6449e+06 | 0.82734 | 1.5024 | 0 | 0 | 4.4375 | 4.7292 |
| 2001/17 | PRIMAL_G | 56 | 56 | 56 | 4.6449e+06 | 0.82795 | 1.4918 | 0 | 0 | 4.9219 | 5.2931 |
| 2001/17 | DUAL_G | 56 | 56 | 56 | 4.6449e+06 | 0.82715 | 1.4935 | 0 | 0 | 4.5938 | 4.7883 |
| 2001/17 | BOTH_G | 56 | 56 | 56 | 4.6449e+06 | 0.83117 | 1.4557 | 0 | 0 | 4.7969 | 5.0717 |
| 2001/17 | RANDOM_G | 56 | 56 | 56 | 4.6449e+06 | 0.83203 | 1.4535 | 0 | 0 | 5.125 | 5.3534 |
| 2001/17 | BOTH_PG | 56 | 56 | 62 | 9.2897e+06 | 0.0060135 | 205.37 | 0 | 0 | 6.0625 | 6.3034 |
| 2001/17 | RANDOM_PG | 56 | 56 | 62 | 9.2897e+06 | 0.0089978 | 137.25 | 0 | 0 | 5.6094 | 5.8808 |
| 2005/17 | BASE_G | 56 | 56 | 56 | 4.6449e+06 | 0.84568 | 1.4569 | 0 | 0 | 4.8906 | 5.2306 |
| 2005/17 | PRIMAL_G | 56 | 56 | 56 | 4.6449e+06 | 0.84866 | 1.4424 | 0 | 0 | 5.75 | 5.9902 |
| 2005/17 | DUAL_G | 56 | 56 | 56 | 4.6449e+06 | 0.8477 | 1.4442 | 0 | 0 | 4.6406 | 4.981 |
| 2005/17 | BOTH_G | 56 | 56 | 56 | 4.6449e+06 | 0.84941 | 1.4083 | 0 | 0 | 5.2031 | 5.3432 |
| 2005/17 | RANDOM_G | 56 | 56 | 56 | 4.6449e+06 | 0.85053 | 1.4045 | 0 | 0 | 5.4219 | 5.7155 |
| 2005/17 | BOTH_PG | 56 | 56 | 62 | 9.2897e+06 | 0.012095 | 101.19 | 0 | 0 | 6.2031 | 6.4028 |
| 2005/17 | RANDOM_PG | 56 | 56 | 62 | 9.2897e+06 | 0.0074381 | 164.54 | 0 | 0 | 1.6719 | 1.7252 |
| 2003/17 | BASE_G | 56 | 56 | 56 | 4.6449e+06 | 0.57355 | 2.8026 | 0 | 0 | 9.4688 | 9.7708 |
| 2003/17 | PRIMAL_G | 56 | 56 | 56 | 4.6449e+06 | 0.57779 | 2.7701 | 0 | 0 | 4.7656 | 4.9783 |
| 2003/17 | DUAL_G | 56 | 56 | 56 | 4.6449e+06 | 0.57631 | 2.7782 | 0 | 0 | 15.625 | 16.478 |
| 2003/17 | BOTH_G | 56 | 56 | 56 | 4.6449e+06 | 0.58118 | 2.655 | 0 | 0 | 5.1406 | 5.3669 |
| 2003/17 | RANDOM_G | 56 | 56 | 56 | 4.6449e+06 | 0.58228 | 2.6461 | 0 | 0 | 5.2656 | 5.4678 |
| 2003/17 | BOTH_PG | 56 | 56 | 62 | 9.2897e+06 | 0.0017968 | 890.66 | 0 | 0 | 10.672 | 11.12 |
| 2003/17 | RANDOM_PG | 56 | 56 | 62 | 9.2897e+06 | 0.0066139 | 241.93 | 0 | 0 | 5.625 | 5.989 |
| 2007/17 | BASE_G | 56 | 56 | 56 | 4.6449e+06 | 0.85425 | 1.4269 | 0 | 0 | 0.625 | 0.62715 |
| 2007/17 | PRIMAL_G | 56 | 56 | 56 | 4.6449e+06 | 0.85569 | 1.4164 | 0 | 0 | 5.8594 | 6.0192 |
| 2007/17 | DUAL_G | 56 | 56 | 56 | 4.6449e+06 | 0.85484 | 1.418 | 0 | 0 | 1.0469 | 1.1628 |
| 2007/17 | BOTH_G | 56 | 56 | 56 | 4.6449e+06 | 0.85726 | 1.3794 | 0 | 0 | 5.2812 | 5.6152 |
| 2007/17 | RANDOM_G | 56 | 56 | 56 | 4.6449e+06 | 0.85849 | 1.3748 | 0 | 0 | 1.1562 | 1.1898 |
| 2007/17 | BOTH_PG | 56 | 56 | 62 | 9.2897e+06 | 0.012221 | 99.144 | 0 | 0 | 5.8281 | 6.2415 |
| 2007/17 | RANDOM_PG | 56 | 56 | 62 | 9.2897e+06 | 0.0018272 | 663.06 | 0 | 0 | 1.5781 | 1.6967 |
| 2013/17 | BASE_G | 56 | 56 | 56 | 4.6449e+06 | 0.89754 | 1.2763 | 0 | 0 | 0.59375 | 0.61589 |
| 2013/17 | PRIMAL_G | 56 | 56 | 56 | 4.6449e+06 | 0.89906 | 1.2708 | 0 | 0 | 5.8438 | 6.0677 |
| 2013/17 | DUAL_G | 56 | 56 | 56 | 4.6449e+06 | 0.89849 | 1.272 | 0 | 0 | 1.1094 | 1.1664 |
| 2013/17 | BOTH_G | 56 | 56 | 56 | 4.6449e+06 | 0.9001 | 1.248 | 0 | 0 | 5.7812 | 6.1115 |
| 2013/17 | RANDOM_G | 56 | 56 | 56 | 4.6449e+06 | 0.90114 | 1.2462 | 0 | 0 | 1.1094 | 1.1663 |
| 2013/17 | BOTH_PG | 56 | 56 | 62 | 9.2897e+06 | 0.011882 | 96.152 | 0 | 0 | 9.9531 | 10.525 |
| 2013/17 | RANDOM_PG | 56 | 56 | 62 | 9.2897e+06 | 0.0017267 | 661.62 | 0 | 0 | 1.6406 | 1.7406 |

## Completeness, runtime and output provenance

Saved engine summary status: `COMPLETE`. A budget stop, failure, missing cache, missing vector output or duplicate record is retained as an explicit limitation.

External CPU receipt total: 33.95 seconds; 8 saved A21 driver receipts found. The runtime JSON preserves receipts, caps, environment details and summary timing fields as recorded.

Run information is descriptive of the saved receipts. This report performs no Maxwell solve, QP, truth evaluation, online benchmark or NN work. All measured rows are `ORACLE/OFFLINE` and the dataset is historically exposed feasibility data.

## Artifacts

- `A21_METRICS.csv`: complete state-by-arm metrics, blocked rows and raw nested fields.
- `per_state/*.json`: state-by-arm measurements, provisional interpretation and vector/cache layouts.
- `GATE_DECISION.json`: T0/T1 evidence classification and explicit review boundary.
- `rawdata/`: verbatim source rows, input/output completeness, saved runtime and figure source tables.
- `A21_HF_ERROR_AND_BOUNDS`: `A21_HF_ERROR_AND_BOUNDS.png`, `A21_HF_ERROR_AND_BOUNDS.svg`
- `A21_WEIGHTED_STATIONARITY`: `A21_WEIGHTED_STATIONARITY.png`, `A21_WEIGHTED_STATIONARITY.svg`
- `A21_ENDPOINTS_AND_SCALE`: `A21_ENDPOINTS_AND_SCALE.png`, `A21_ENDPOINTS_AND_SCALE.svg`
- `A21_CONDITIONING`: `A21_CONDITIONING.png`, `A21_CONDITIONING.svg`
- `A21_NORMAL_WORK`: `A21_NORMAL_WORK.png`, `A21_NORMAL_WORK.svg`
- `A21_BASIS_MEMORY`: `A21_BASIS_MEMORY.png`, `A21_BASIS_MEMORY.svg`

T2: `NOT_RUN_NOT_AUTHORIZED`. Codex final review is saved in `A21_ORACLE_REPORT_ZH.md` and `GATE_DECISION.json`.
