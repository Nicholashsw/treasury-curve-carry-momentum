# CARRY_RESEARCH_PLAN.md

**Phase 3 of the carry extension. Experiment plan only — nothing implemented, nothing run.**

Depends on `CARRY_FIELD_INVENTORY.md` (what the data supports) and `CARRY_DESIGN.md` (the carry
definition). Written so that the results are decided by the protocol, not by inspection of outcomes.

---

## 0. Design principles fixed before any code

These are pre-specified. Changing any of them after seeing a result must be logged as an amendment.

1. **The canonical harness is reused unchanged.** Same `continuous()` roll adjustment, same
   `run_strategy()` (month-end rebalance, `.shift(1)` hold, 63-day vol scaling lagged, 3× leverage
   cap, 126-day warm-up), same `tick_frac()` costs, same `hedge_ratio()`. Carry enters only as a new
   signal. Anything that differs from the canonical pipeline is a confound, not a finding.
2. **The canonical results are the benchmark, and they are frozen.** Duration momentum Sharpe 0.68,
   2s10s reversion 0.71, 5s30s 0.66, butterfly 0.07, net of costs, vol-scaled to 10%. Nothing in this
   plan may recompute or alter them.
3. **Every strategy is vol-scaled to the same 10% target** so Sharpes are comparable and a "better"
   result cannot come from taking more risk.
4. **All signal standardisation uses trailing windows only.** No full-sample z-scores, means or
   thresholds anywhere.
5. **Acceptance criteria are written below, before the tests are run.**
6. **Negative results are the expected outcome and are acceptable.** The base rate for "a new sleeve
   adds significant value to an existing two-sleeve book on 16 years of one country's data" is low.

## 1. Signal construction (shared across all experiments)

| Signal | Definition | Source |
|---|---|---|
`carry_kmpv[i,t]` | $(F^{(1)}-F^{(2)})/F^{(2)}/\Delta t$, roll-window excluded, trailing-winsorised | Design §2B |
`carry_curve[i,t]` | carry-and-roll at the root's mapped tenor, DV01-converted | Design §2C |
`carry_2s10s[t]`, `carry_5s30s[t]`, `carry_fly[t]` | per-leg carry differenced under canonical `hedge_ratio()` | Design §2D |
`mom[i,t]` | `sign(rets.rolling(63).sum())` — **canonical, unchanged** | existing cell 13 |
`rev[x,t]` | `−z(spread, 252)` clipped ±3, lagged — **canonical, unchanged** | existing cell 15 |

Two carry variants (`kmpv`, `curve`) are carried through every experiment as a robustness pair. If
they disagree in sign, that is a finding about the measure and is reported as such rather than
resolved by picking the better one.

## 2. Experiments

### A. Standalone carry

| | |
|---|---|
| **Signal** | Two forms. (A1) *Time-series*: long if `carry_kmpv[i,t] > 0`, short if < 0, per root. (A2) *Cross-sectional*: rank six roots by carry, long the top two, short the bottom two, DV01-weighted and dollar-neutral in DV01 terms |
| **Position construction** | Contracts $\propto \text{signal}_{i}/\mathrm{DV01}_{i,t-1}$; book vol-scaled to 10% |
| **DV01 normalisation** | Applied at *position construction*, not in the signal (see `CARRY_DESIGN.md` §3a). Each root contributes equal DV01; cross-sectional book is DV01-neutral by construction |
| **Rebalance** | Monthly (month-end), signals from *t−1* |
| **Costs** | One tick/contract/side, per-contract `FUT_TICK_SIZE` |
| **Benchmark** | (i) zero; (ii) canonical duration momentum (0.68) |
| **Test statistic** | Newey–West *t* on mean net return at lag 21; Diebold–Mariano with Bartlett HAC at lag 21 + HLN against the momentum baseline |
| **OOS protocol** | Expanding-window walk-forward: first evaluation origin at 40% of sample (≈2016-08), re-deriving nothing (the signal is parameter-free) but reporting performance only from the origin forward. **No parameter is fitted, so this is a genuine OOS by construction** |
| **Regime splits** | Pre/post-2022; canonical MOVE-based three-state regime (flattening 1,948 / steepening 1,454 / stress 771 days); rate level above/below sample median; curve slope positive/inverted |
| **Robustness** | Both carry variants; excluding `US`; excluding UXY; roll-window ±1/±3/±5 days; quarterly rather than monthly rebalance; no winsorisation |
| **Acceptance** | Report regardless. "Works" = net Sharpe > 0.4 **and** NW-*t* > 2.0 **and** consistent sign in ≥3 of 4 subperiods **and** the same sign under both carry variants |

### B. Carry-conditioned duration momentum

| | |
|---|---|
| **Signal** | `mom[i,t] × 1{carry[i,t] agrees in sign}` — take the trend trade only when carry does not oppose it. Also a soft version: `mom × (0.5 + 0.5·1{agree})` |
| **Hypothesis** | Trend and carry conflict in mean-reverting rate regimes; requiring agreement should cut whipsaw |
| **Benchmark** | **Canonical duration momentum, 0.68 net Sharpe** — this is the number to beat |
| **Test statistic** | DM vs canonical momentum (HAC lag 21 + HLN); paired difference in Sharpe with a stationary block bootstrap (1,000 draws, mean block 63 days) for a confidence interval |
| **Everything else** | As A |
| **Acceptance** | Requires DM *p* < 0.10 **and** a bootstrap Sharpe-difference CI excluding zero. A raw Sharpe improvement without both is reported as "not distinguishable", following the canonical paper's own standard |

### C. Carry-conditioned 2s10s / 5s30s mean reversion

| | |
|---|---|
| **Signal** | `rev[x,t]` gated or tilted by `carry_2s10s[t]` / `carry_5s30s[t]`: (C1) trade only when reversion and carry agree; (C2) size $\propto rev + \lambda\cdot z(carry)$ with $\lambda \in \{0.25, 0.5, 1.0\}$ pre-specified and reported for all three, not selected |
| **Hypothesis** | A steepener with positive carry is a better steepener than one with negative carry — carry tells you the cost of waiting for reversion |
| **Benchmark** | Canonical 2s10s (0.71) and 5s30s (0.66) |
| **Test statistic** | DM vs the respective canonical book; also DM vs the canonical **momentum** baseline, since the canonical paper's finding is that neither curve trade beats it |
| **Everything else** | As A. Turnover reported alongside every Sharpe, since the canonical 2s10s already turns over 104×/yr and gating changes that |
| **Acceptance** | As B, plus: must not increase turnover by more than 25% for the same Sharpe |

### D. Carry on the butterfly

| | |
|---|---|
| **Signal** | `carry_fly[t]` standalone, and as a gate on the canonical curvature reversion |
| **Benchmark** | Canonical butterfly (0.07, max DD −38%) — a low bar, deliberately |
| **Note** | The canonical butterfly is the weakest book and the most cost- and hedge-error-sensitive (three legs, two hedge ratios, 87 turns/yr). Prior is that carry will not rescue it. Reported either way |
| **Acceptance** | Same as B. If the butterfly remains unsupported, that is the result |

### E. Carry + momentum (two-sleeve portfolio)

| | |
|---|---|
| **Construction** | Equal-risk-contribution blend of the standalone carry book (A2) and canonical duration momentum, each pre-scaled to 10% vol, then the blend re-scaled to 10%. Also reported at fixed 25/75, 50/50, 75/25 weights — **no weight optimisation**, because optimising weights in-sample is how this kind of study fools itself |
| **Test statistic** | DM of the blend vs momentum alone; incremental Sharpe with bootstrap CI; sleeve correlation |
| **Acceptance** | As B |

### F. Carry + curve mean reversion

As E, blending the standalone carry book with the canonical 2s10s reversion book.

### G. Combined carry + momentum + curve-RV portfolio

| | |
|---|---|
| **Construction** | Three-sleeve equal-risk-contribution: carry, duration momentum, 2s10s reversion. Fixed weights only; also 1/3–1/3–1/3 |
| **Benchmark** | (i) momentum alone; (ii) the best two-sleeve blend from E/F |
| **Test statistic** | DM against both benchmarks; incremental Sharpe and drawdown reduction with bootstrap CIs; full 3×3 sleeve correlation matrix; marginal risk contribution per sleeve |
| **Acceptance** | Carry earns a place in the public framing **only if** it adds ≥0.10 to the blended net Sharpe with a bootstrap CI excluding zero, **or** reduces max drawdown by ≥15% relative at equal Sharpe |

## 3. Does carry carry *new* information? (the decisive test block)

Performance is not the question — incremental performance is. This block runs regardless of whether
A–G produce positive Sharpes.

| Measure | Method | What would make carry interesting |
|---|---|---|
| **Correlation with momentum** | Pearson and Spearman of daily net returns, full sample and per regime; plus signal-level correlation of `carry` with `mom` | \|ρ\| < 0.3 on returns |
| **Correlation with mean reversion** | Same against the 2s10s and 5s30s books | \|ρ\| < 0.3 |
| **Incremental Sharpe** | Sharpe of the blend minus Sharpe of the best existing book, with a stationary block bootstrap CI (1,000 draws, mean block 63d) | CI excludes zero |
| **Incremental drawdown reduction** | Max DD of blend vs best existing book at matched vol | ≥15% relative reduction |
| **Incremental diversification** | Marginal risk contribution of the carry sleeve; diversification ratio of the 3-sleeve book vs the 2-sleeve book | Carry MRC materially below its weight |
| **Spanning test** | Regress carry-book returns on momentum + 2s10s + 5s30s returns; test the intercept with HAC(21) errors | **The single cleanest test.** A significant positive alpha means carry is not spanned by what we already have |
| **Turnover / cost impact** | Turnover per year and cost drag in bp for every book; net-of-cost sensitivity to 1×, 2×, 3× the tick cost | Carry's turnover should be *lower* than reversion's (signal autocorrelation is 0.933 at 21d) — verify, don't assume |

> **The spanning regression is the test I would lead with in an interview.** "Does carry add
> information?" is exactly "is the intercept of carry returns on the existing sleeves significantly
> positive?" — and it answers the question without any portfolio-construction choices in the way.

## 4. Robustness and anti-self-deception

| Threat | Control |
|---|---|
| Look-ahead | Design §4; every input lagged; roll-window exclusion; trailing-only standardisation |
| Data artefact masquerading as signal | `US` carry diagnosed before use (sd 5.40% vs TY 1.86%, cross-root ρ 0.07–0.21); results reported with and without `US` |
| Roll contamination | ±3-day exclusion as base, ±1 and ±5 as sensitivity |
| Overfitting the blend | **No weight optimisation anywhere**; fixed weight grids reported in full |
| Specification search | Two carry variants and three λ values pre-specified and all reported; count of tested specifications disclosed; Benjamini–Hochberg FDR across the full family of DM tests |
| Regime luck | Four independent regime splits; 2022 examined separately since it is the canonical paper's stress case |
| Cost optimism | Cost sensitivity at 1×/2×/3× tick; turnover always shown beside Sharpe |
| Multiple comparisons | Total DM test count declared; FDR-adjusted verdict reported alongside raw |
| Weak benchmark | Benchmarked against the canonical momentum book, not against zero |

## 5. Deliverables

Into `carry/` on branch `carry-extension-2026-08`, never touching canonical files:

- `carry/src/carry_signals.py` — signal construction (both variants)
- `carry/src/carry_backtest.py` — experiments A–G on the canonical harness
- `carry/src/carry_eval.py` — DM, bootstrap, spanning regression, FDR
- `carry/results/*.csv` — one row per specification, all reported
- `carry/CARRY_FINDINGS.md` — results with the pre-specified verdict against §2 acceptance criteria
- `carry/figs/` — sleeve correlation matrix, carry term structure, incremental-value chart

## 6. Pre-specified stopping rule for the rename question

The public title changes to *"Treasury Futures: Carry, Momentum & Curve Relative Value"* **only if
both** hold:

1. **Empirical.** Standalone carry clears experiment A's acceptance bar, **and** the spanning
   regression intercept is positive with HAC(21) *t* > 2.0, **and** experiment G clears its bar.
2. **Intellectual.** Carry is a genuine third sleeve rather than a re-expression of the curve slope —
   evidenced by sleeve return correlation \|ρ\| < 0.3 against both existing sleeves.

If (1) fails but (2) holds, the finding is documented as an honest null and the title stays as-is,
with carry described as tested-and-not-supported — which is materially more valuable than a title
change and is consistent with how the rest of this portfolio reports negative results.

If `US` has to be excluded for data reasons, that is disclosed in the abstract, not a footnote.
