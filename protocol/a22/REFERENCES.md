# References 与阅读深度

检索/核查日期：2026-10-07。原始论文地址用代码形式保留，便于交给研究工具继续读取。日期优先使用 preprint 年份；不将 preprint 自动标成已接收期刊论文。没有核查的 DOI、页码和期刊状态不补写。

阅读等级：**F**=读取了本任务相关原文/方法段，不等于逐页审稿；**A**=作者/出版社摘要级；**S**=检索元数据或摘要筛查，正文未获取；**C**=通过作者团队的另一篇原始论文中的描述/文献条目核查，尚缺目标论文原文。

## 核心近邻

**[R00] Xudong Chen. Computational Methods for Electromagnetic Inverse Scattering. Wiley/IEEE Press, 2018.** ISBN 9781119311980。用户提供的书。F：printed pp.132–134（EBA/BP）、149–152（SOM）、161–163（TSOM）；Fig.6.13 在 printed p.162 / PDF p.181。BP eqs.(6.25)–(6.30) 已有 current→field→material 的非迭代链条。当前包不重新分发整本书。

**[R01] Johannes Schwab, Stephan Antholzer, Markus Haltmeier. Deep Null Space Learning for Inverse Problems: Convergence Analysis and Rates.** 2018 preprint；Inverse Problems 35, 025008, 2019；DOI 10.1088/1361-6420/aaf14a。F：§1.3, eq.(1.3) 与基本正则化结构。
`https://arxiv.org/abs/1806.06137`

**[R02] Yoeri E. Boink, Markus Haltmeier, Sean Holman, Johannes Schwab. Data-consistent neural networks for solving nonlinear inverse problems.** 2020 preprint。A：非线性数据一致网络这一总体对象已存在；本轮 PDF 读取未成功，不比较未读定理细节。
`https://arxiv.org/abs/2003.11253`

**[R03] Dongdong Chen, Mike E. Davies. Deep Decomposition Learning for Inverse Imaging Problems.** 2019 preprint。A：range/null decomposition learning。
`https://arxiv.org/abs/1911.11028`

**[R04] Roman Jacome, Romario Gualdrón-Hurtado, Leon Suarez, Henry Arguello. NPN: Non-Linear Projections of the Null-Space for Imaging Inverse Problems.** 2025 preprint。F：linear model、§2–3 method，null-space projection prior 与各 reconstruction frameworks 的结合；未独立复现实验。
`https://arxiv.org/abs/2510.01608`
`https://arxiv.org/html/2510.01608v1`

**[R05] Yu Liu, Hao Zhao, Rencheng Song, Xudong Chen, Chang Li, Xun Chen. SOM-Net: Unrolling the Subspace-based Optimization for Solving Full-wave Inverse Scattering Problems.** 2022 preprint。F：摘要、引言、方法结构；deterministic current/BP 输入、交替 current/material update。
`https://arxiv.org/abs/2209.03567`

## 信息降维、任务降维与 balancing

**[R06] Tiangang Cui, James Martin, Youssef M. Marzouk, Antti Solonen, Alessio Spantini. Likelihood-informed dimension reduction for nonlinear inverse problems.** 2014；DOI 10.1088/0266-5611/30/11/114015。A：likelihood 相对 prior 的降维。
`https://arxiv.org/abs/1403.4680`

**[R07] Tiangang Cui, Olivier Zahm. Data-Free Likelihood-Informed Dimension Reduction of Bayesian Inverse Problems.** 2021；DOI 10.1088/1361-6420/abeafb。A。
`https://arxiv.org/abs/2102.13245`

**[R08] Paul G. Constantine, Carson Kent, Tan Bui-Thanh. Accelerating Markov chain Monte Carlo with active subspaces.** 2015 preprint；DOI 10.1137/15M1042127。A。
`https://arxiv.org/abs/1510.00024`

**[R09] Alessio Spantini, Tiangang Cui, Karen Willcox, Luis Tenorio, Youssef Marzouk. Goal-oriented optimal approximations of Bayesian linear inverse problems.** 2016 preprint / 2017 journal；DOI 10.1137/16M1082123。A：任务 posterior 的最优低秩近似。
`https://arxiv.org/abs/1607.01881`

**[R10] Elizabeth Qian et al. Model Reduction of Linear Dynamical Systems via Balancing for Bayesian Inference.** 2021 preprint / 2022 journal；DOI 10.1007/s10915-022-01798-8。A：reachability/observability balancing 与 Bayesian inference。
`https://arxiv.org/abs/2111.13246`

**[R11] Melina A. Freitag et al. Inference-Oriented Balanced Truncation for Quadratic Dynamical Systems: Formulation for Bayesian Smoothing and Model Stability Analysis.** 2024；DOI 10.1002/pamm.202400051。A：非线性/二次系统的相关 balancing 思路；未作全文定理级排重。
`https://doi.org/10.1002/pamm.202400051`

## 直接逆散射与 ROM

**[R12] Liliana Borcea, Vladimir Druskin, Alexander V. Mamonov, Mikhail Zaslavsky, Jörn Zimmerling. Reduced Order Model Approach to Inverse Scattering.** 2019 preprint / 2020 journal；DOI 10.1137/19M1296355。A：data-driven ROM 与 data-to-Born 思路；构成 direct inverse ROM 的关键近邻。
`https://arxiv.org/abs/1910.13014`

**[R13] A. Tataris, T. van Leeuwen, A. V. Mamonov. Inverse Scattering for Schrödinger Equation in the Frequency Domain via Data-Driven Reduced Order Modeling.** 2025；DOI 10.1137/25M1741935。A：频域 data-driven inverse ROM。书目信息来自出版社检索条目，未全文审阅。
`https://doi.org/10.1137/25M1741935`

## Learned regularization 与 posterior solvers

**[R14] Singanallur V. Venkatakrishnan, Charles A. Bouman, Brendt Wohlberg. Plug-and-Play Priors for Model Based Reconstruction.** 2013。A：作者论文页面。
`https://brendt.wohlberg.net/publications/venkatakrishnan-2013-plugandplay.html`

**[R15] Edward T. Reehorst, Philip Schniter. Regularization by Denoising: Clarifications and New Interpretations.** 2018 preprint。A：不能对任意 denoiser 都直接使用显式 RED-gradient 解释。
`https://arxiv.org/abs/1806.02296`

**[R16] Dmitry Ulyanov, Andrea Vedaldi, Victor Lempitsky. Deep Image Prior.** 2017 preprint / 2018 CVPR。A：网络架构可作图像先验，per-instance optimization 不等同 one-shot。
`https://arxiv.org/abs/1711.10925`

**[R17] Hyungjin Chung, Jeongsol Kim, Michael T. McCann, Marc L. Klasky, Jong Chul Ye. Diffusion Posterior Sampling for General Noisy Inverse Problems.** 2022 preprint / ICLR 2023。A。
`https://arxiv.org/abs/2209.14687`

**[R18] Yaniv Romano, Michael Elad, Peyman Milanfar. The Little Engine that Could: Regularization by Denoising (RED).** 2016 preprint。A；与 [R15] 的适用条件说明一起阅读。
`https://arxiv.org/abs/1611.02862`

**[R19] Subspace Diffusion Posterior Sampling for Travel-Time Tomography.** 2024 preprint / 2025 journal；DOI 10.1088/1361-6420/adcae2。F：原文多尺度/subspace 方法部分。这里的 subspace 不等于本任务按 Maxwell material recoverability 划分的 V_prior。
`https://arxiv.org/abs/2408.17333`

**[R20] Diffusion State-Guided Projected Gradient for Inverse Problems.** 2024 preprint。A：diffusion-state projection，与材料物理补空间不同。
`https://arxiv.org/abs/2410.03463`

**[R21] Daniil Sherki, Ivan Oseledets, Ekaterina Muravleva. Bayesian Inverse Problems Meet Flow Matching: Efficient and Flexible Inference via Transformers.** 2025 preprint。A。
`https://arxiv.org/abs/2503.01375`

**[R22] Agnimitra Dasgupta et al. Conditional flow matching for physics-constrained inverse problems with finite training data.** 2026 preprint，核查到 v3 标题。A：finite-data variance collapse/selective memorization 风险；不从摘要移植定理假设。
`https://arxiv.org/abs/2603.14135`

**[R23] Song Ni et al. SONAR: A Structure-Consistent Neural Operator for Null-Space-Aware Sparse View CT Reconstruction.** 2026-09 preprint。S：原始 arXiv 检索摘要可见，直接 abstract/html 读取失败；仅列潜在重合，不给定理级结论。
`https://arxiv.org/abs/2609.13688`

**[R24] Shirin Shoushtari, Edward P. Chandler, Xiao Shi, Ulugbek S. Kamilov. Fast and Faithful: Principled Conditional Flow Matching for Inverse Problems.** 2026-09 preprint。S：原始 arXiv 检索摘要可见，直接正文读取失败；不引用其性能数字。
`https://arxiv.org/abs/2609.12953`

## Electromagnetic learned encoders / operators

**[R25] A Learning-Based Variational Backpropagation Method for Inverse Scattering Problems.** 2025；DOI 10.1155/mmce/5531090。A：出版社条目；BP/learned imaging 近邻，不据此宣称存在或不存在完整 OPM split。
`https://doi.org/10.1155/mmce/5531090`

**[R26] Neumann series-based neural operator for solving 2D inverse medium problem.** 2025；DOI 10.1016/j.jcp.2025.114025。A：出版社摘要级的 operator-learning 近邻，不将其解释为 prior-only material decoder。
`https://doi.org/10.1016/j.jcp.2025.114025`

## Generative 方法基础

**[R27] Jonathan Ho, Ajay Jain, Pieter Abbeel. Denoising Diffusion Probabilistic Models.** 2020。A。
`https://arxiv.org/abs/2006.11239`

**[R28] Yang Song et al. Score-Based Generative Modeling through Stochastic Differential Equations.** 2020 preprint。A。
`https://arxiv.org/abs/2011.13456`

**[R29] Yaron Lipman, Ricky T. Q. Chen, Heli Ben-Hamu, Maximilian Nickel, Matt Le. Flow Matching for Generative Modeling.** 2022 preprint。A。
`https://arxiv.org/abs/2210.02747`

**[R30] Xingchao Liu, Chengyue Gong, Qiang Liu. Flow Straight and Fast: Learning to Generate and Transfer Data with Rectified Flow.** 2022 preprint。A。
`https://arxiv.org/abs/2209.03003`

## 补充的高优先级近邻

**[R31] Zhun Wei, Xudong Chen. Physics-Inspired Convolutional Neural Network for Solving Full-Wave Inverse Scattering Problems.** IEEE TAP 67(9), 6138–6148, 2019；DOI 10.1109/TAP.2019.2922779。C：书目与 contrast-source-domain ICLM 定位由 [R05] 引言及 reference [23] 核查；目标原文未成功获取。第三方摘要提到 major/minor current bypass，但本包不据此做原文定理级解释。
`https://doi.org/10.1109/TAP.2019.2922779`

**[R32] Justin Baker, Elena Cherkaev, Vladimir Druskin, Shari Moskow, Mikhail Zaslavsky. Regularized reduced order Lippmann-Schwinger-Lanczos method for inverse scattering problems in the frequency domain.** 2023 preprint / Journal of Computational Physics 525, 113725, 2025；DOI 10.1016/j.jcp.2025.113725。A：作者摘要与出版社摘要；direct non-iterative ROM 与 weak potential-dependence 是重要近邻。
`https://arxiv.org/abs/2311.16367`
`https://doi.org/10.1016/j.jcp.2025.113725`

## 使用规则

以上共33个编号，其中包含用户提供书籍、原始研究论文与候选筛查条目。不要写成“已精读33篇论文”。未来论文必须在 method-level comparison 中补齐 R02、R12、R31、R32 和新近 R23/R24 的原文；对未获取内容只保留有限描述。不使用引文数量、检索平台评分或第三方AI总结作为 novelty 判断证据。
