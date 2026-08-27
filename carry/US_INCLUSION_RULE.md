# US / classic-bond inclusion rule

**Fixed 2026-08-24, before any strategy was run and before any Sharpe ratio was computed.**
Decided on dispersion, tail shape and cross-root coherence only. Reproduce with
`carry/src/us_diagnostic.py` then `carry/src/us_rule.py`.

## Anomaly

Raw calendar-spread carry for `US`: sd 5.41% against TY's 1.86%, raw spread minimum −19.4 points,
and mean correlation with the other five roots of **+0.149** against **+0.665** among the others.

## Cause — identified, not guessed

| Test | Result | Verdict |
|---|---|---|
| Is it scattered bad prints? | **No.** 61 observations below −3 points, **all** between 2014-12-22 and 2015-03-20, max gap between extreme days 4 days | One contiguous episode, 1.5% of sample |
| Roll mechanics / generic misalignment? | **No.** 11.5% of extremes fall in a ±3bd roll window vs 11.1% of all observations; sd *inside* roll windows (2.05) is lower than outside (2.17) | Rejected |
| Permanent contract-spec change? | **No.** Every year outside 2014–15 has spread sd 0.06–1.19 and min ≥ −2.16; 2016 onward sd 0.06–0.16 | Rejected |
| Is it US-specific in time? | **Yes.** Monthly mean spread Jan-2015: US **−17.51**, while TU 0.37, FV 0.64, TY 0.62, WN 0.76 | US-specific event |
| CTD switch? | **Yes.** Largest US DV01 jump in the whole 16-year sample is **+46.9% on 2015-03-23**, immediately after the episode. DV01 level shifts permanently 15.49 (Nov-14) → 16.30 (Jan-15) → **23.76 (Apr-15)** | **Confirmed cause** |
| Driver | 30y yield fell 3.037% (Nov-14) → 2.464% (Jan-15). With yields far below the 6% notional coupon the CTD migrates across the 15–25y basket | Consistent |

**Conclusion.** During 2014-12-22 → 2015-03-20 the generic-1 and generic-2 US contracts referenced
deliverables of materially different duration. Over that window the calendar spread measures a
duration difference, not carry. This is exactly the weakness anticipated in `CARRY_DESIGN.md` §5.1
("CTD change between contracts"), now observed and localised.

Generic-2 open interest for US is also the thinnest in the panel (1.17% of generic-1, median 7,519
contracts), which amplifies a CTD-driven dislocation but does not cause it — TY's ratio is a similar
1.54% and TY is clean.

## Rule adopted — root-agnostic, not a US carve-out

Two mechanical detectors, applied **identically to all six roots**, unioned, buffered ±10 business
days, with the carry signal held at its last clean value across the mask:

1. **CTD-switch detector.** `|ΔDV01 / DV01| > 5%`. Calibrated on the panel, not on US: over 16 years
   TY's largest daily DV01 move is 5.3% and WN's 8.1%, so 5% separates genuine discontinuities from
   ordinary drift.
2. **Persistent-dislocation detector.** `|spread − trailing median| > 6 × trailing IQR`, on a
   trailing 252-day window, shifted one day. **Trailing only — no look-ahead.**

Plus the pre-specified ±3bd roll-window exclusion and trailing-expanding 1%/99% winsorisation.

## Validation — mechanical criteria only

| Criterion | Before | After | Panel reference |
|---|---|---|---|
| Carry sd | 5.41% | **1.93%** | TY 1.83% |
| sd ratio vs TY | 2.92× | **1.05×** | target ≈ 1 |
| Excess kurtosis | **46.2** | **0.60** | others −0.72 to +0.74 |
| Mean corr with other roots | +0.149 | **+0.581** | among others +0.674 |
| Coherence ratio | 0.22 | **0.86** | target ≈ 1 |
| Episode days caught by guard | — | **100% (61/61)** | non-episode 7.7% |

Data removed by the guard: US 9.1%, WN 9.7%, TY 1.3%, UXY 2.2%, TU 0.5%, FV 0.0%.

## Decision

**US is RETAINED in the primary panel.** After the root-agnostic guard it is mechanically
indistinguishable from the rest of the panel on dispersion, tail shape and cross-root coherence, and
the contamination was a single 1.5%-of-sample CTD-migration episode rather than a property of the
contract. Discarding 16 years of the most-traded long-end contract for a 3-month localised defect
would not be proportionate.

`US`-excluded results are reported throughout as the pre-specified robustness case, as is
`WN`-excluded (its guard rate is comparably high at 9.7%).

**No performance figure of any kind informed this decision.** If the cleaned US series had remained
incoherent with the panel it would have been excluded on that basis alone, regardless of its Sharpe.
