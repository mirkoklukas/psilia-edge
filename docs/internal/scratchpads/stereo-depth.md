---
type: working-doc
summary: Stereo depth on Jetson — classical methods as energy minimization, algorithm spectrum (BM/SGM/MRF), and options table.
created: 2026-05-05
tags:
  - stereo
  - depth
  - jetson
---

# Stereo Depth on Jetson

## Stereo as Energy Minimization

Most classical stereo methods can be framed as minimizing an energy over a disparity image $D$ — an assignment $D_p$ of a disparity to every pixel $p$:

$$
E(D) \;=\; \underbrace{\sum_p C(p, D_p)}_{\text{data term}} \;+\; \underbrace{\sum_p \sum_{q \in N_p} V(D_p, D_q)}_{\text{smoothness term}}
$$

- **Data term** — per-pixel matching cost. Pixelwise independent. Encodes "how well does the chosen disparity match the right image?"
- **Smoothness term** — pairwise penalty across neighbors $N_p$ (typically 4- or 8-connected). Encodes "neighboring pixels should have similar disparities, except at object boundaries."

Stereo algorithms differ mainly in **how much (and how globally) they regularize**. The spectrum:

| Method | Data term | Smoothness term | Cost |
|---|---|---|---|
| **Block matching (WTA)** | $C(p, d)$ | none | cheap, noisy |
| **Cost-volume filtering** (e.g. guided filter, WLS) | $C(p, d)$ | local edge-aware smoothing of $C$ itself | cheap, decent |
| **SGM** | $C(p, d)$ | sum of 1D pairwise $V$ along paths | medium, good |
| **Full MRF** (graph cuts / belief propagation) | $C(p, d)$ | full 2D pairwise $V$ | expensive, best classical |
| **Segmentation-based stereo** | $C(p, d)$ | smoothness within segments, free across | varies |
| **Learned stereo** (HITNet, etc.) | feature matching $\approx C$ | refinement / propagation layers $\approx V$ | varies; data + regularization fused into one network |

Two corollaries:

1. **Learned methods aren't off this spectrum.** They don't write down $C$ and $V$ explicitly, but the architecture decomposes the same way: matching layers build a cost volume, refinement layers regularize.
2. **Textureless regions don't carry data-term information.** Where $C(p, d)$ is flat across $d$, the disparity at that pixel is decided entirely by the smoothness term propagating from neighbors. Skipping such pixels means trusting the regularizer to fill in.


## The SGM-style Smoothness Term

In SGM (and Potts-like MRFs), the pairwise smoothness term is a step function:

$$
V(D_p, D_q) \;=\; \begin{cases}
0 & \text{if } D_p = D_q \\
P_1 & \text{if } |D_p - D_q| = 1 \\
P_2 & \text{if } |D_p - D_q| > 1
\end{cases}
$$

with $P_2 \geq P_1$.

- **$P_1$ tier** — small penalty for unit changes → smooth surfaces (slanted walls, curved objects) come through.
- **$P_2$ tier** — flat penalty independent of jump size → edges aren't over-penalized; the term simply discourages jumps from happening everywhere.
- **Edge modulation:** $P_2$ is often modulated by the image gradient at $p$ — smaller $P_2$ where edges are likely. Embeds the prior "depth jumps tend to coincide with image edges."

This pairwise term is **non-convex** (a step function), which makes exact minimization of $E(D)$ NP-hard in general. Classical *global* approximations:

- **Graph cuts** ($\alpha$-expansion) — strong quality, slow.
- **Belief propagation** — message passing on the MRF graph.
- **TRW-S** — tree-reweighted message passing.

These give the best classical disparity quality but don't run real-time on edge hardware.


## SGM's Approximation: 1D Paths

SGM replaces the 2D pairwise sum with a **sum of 1D pairwise sums along multiple paths**. For a single direction $r$:

$$
E_r(D) \;=\; \sum_p C(p, D_p) \;+\; \sum_p V(D_p,\, D_{p-r})
$$

Each $E_r$ is a 1D MRF along a chain — solvable **exactly** in linear time by dynamic programming. The Stage 2 recurrence below is precisely the DP for minimizing $E_r$ along path $r$.

After computing each $L_r$, sum over directions and pick the per-pixel minimum:

$$
S(p, d) \;=\; \sum_r L_r(p, d), \qquad d^*(p) \;=\; \arg\min_d S(p, d)
$$

This is **not** the true $\arg\min_D E(D)$ — it's a per-pixel decision based on summed 1D-optimal costs. Empirically it tracks the global solution closely while running orders of magnitude faster.

Trade-off symptoms of the 1D approximation:

- **Streaking artifacts** in flat regions — paths "lock onto" a disparity and propagate it; visible as faint stripes along path directions. More paths (8 or 16) reduces this.
- **Anisotropic quality** — bias along path directions.


## SGM — Cost Aggregation (Stage 2)

For each path direction $r$ (typically 8: 4 cardinal + 4 diagonal), the aggregated cost at pixel $p$ for disparity $d$ is computed recursively:

$$
L_r(p, d) \;=\; C(p, d) \;+\; \min \left\{
\begin{array}{l}
L_r(p - r,\, d) \\[2pt]
L_r(p - r,\, d - 1) + P_1 \\[2pt]
L_r(p - r,\, d + 1) + P_1 \\[2pt]
\displaystyle\min_{i}\, L_r(p - r,\, i) + P_2
\end{array}
\right\}
\;-\; \min_{k}\, L_r(p - r,\, k)
$$

where

- $C(p, d)$ — per-pixel matching cost from Stage 1 (Census, MI, BT, etc.). **Lower is better** — $C$ is a cost (e.g. Hamming distance for Census), not a similarity score. Similarity-based measures like NCC are flipped (e.g. $1 - \mathrm{NCC}$) to fit this convention. The whole algorithm assumes low = good match.
- $p - r$ — previous pixel along path direction $r$.
- $P_1$ — small penalty for unit disparity change ($\pm 1$); rewards smooth surfaces.
- $P_2 \geq P_1$ — larger penalty for any other disparity jump; preserves discontinuities. Often modulated by the image gradient at $p$ (smaller $P_2$ where edges are likely).
- $-\min_k L_r(p - r, k)$ — normalization that subtracts the path's running minimum to keep $L_r$ bounded over long paths. Does not affect which $d$ is optimal.

The four cases inside the min represent: continuation at same disparity (no penalty), $\pm 1$ change (small penalty $P_1$), and any larger jump (penalty $P_2$).

Common path counts: 4 (fast), 8 (standard, two passes), 16 (highest quality).

**Implication for skipping pixels:** computing $L_r(p, d)$ requires $L_r(p - r, *)$ — all $D$ disparity values at the previous pixel along the path. The DP chain breaks if any pixel along the path is skipped. Hence pixel-level skipping does not compose with this stage; only granularities that respect path structure (rows, columns, tiles, ROIs) cooperate.

**Sources:**

- Hirschmüller, *Stereo Processing by Semiglobal Matching and Mutual Information*, IEEE TPAMI, 2008.
- [Wikipedia — Semi-global matching](https://en.wikipedia.org/wiki/Semi-global_matching) (formula cross-checked).


## Algorithm Menu

Concrete implementations and their fit on Jetson Orin Nano Super:

| Library / API                       | Algorithm          | Backend  | Runtime cost                          | On Orin Nano Super | Notes                                             |
| ----------------------------------- | ------------------ | -------- | ------------------------------------- | ------------------ | ------------------------------------------------- |
| `cv::cuda::StereoBM` (cudastereo)   | SAD block matching | CUDA GPU | Very low                              | ✓                  | Pure data term — fast, noisy                      |
| `cv::cuda::StereoSGM` (cudastereo)  | Census + SGM       | CUDA GPU | Medium                                | ✓                  | Standard pick if using OpenCV                     |
| `cv::cuda::StereoBeliefPropagation` | Full-MRF BP        | CUDA GPU | High                                  | ✓ but slow         | Best classical quality, not real-time at full res |
| `cv::cuda::StereoConstantSpaceBP`   | Constant-space BP  | CUDA GPU | High (lower mem)                      | ✓ but slow         | Memory-efficient BP variant                       |
| libSGM (Fixstars)                   | Census + SGM       | CUDA GPU | Medium (often faster than OpenCV SGM) | ✓                  | Most-cited SGM on Jetson                          |
| VPI `StereoDisparityEstimator`      | SGM                | CPU      | High (slow)                           | ✓ but slow         | Reference / fallback                              |
| VPI `StereoDisparityEstimator`      | SGM                | CUDA GPU | Medium                                | ✓                  | Same niche as OpenCV CUDA SGM                     |
| VPI `StereoDisparityEstimator`      | SGM variant        | PVA      | —                                     | ✗ no PVA on Nano   | Not available                                     |
| VPI `StereoDisparityEstimator`      | "Advanced SGM"     | OFA      | —                                     | ✗ no OFA on Nano   | Not available                                     |

Caveats on runtime cost: qualitative only. Actual numbers depend on resolution, disparity range, $P_1/P_2$, and contention with other GPU workloads (significant on Orin Nano — single accelerator). Order of magnitude at 720p / 64–128 disparities on the Nano GPU: BM single-digit ms, SGM tens of ms, BP hundreds of ms.

For hardware constraints on this platform see [[jetson-orin-nano-accelerators]] in the inbox.
