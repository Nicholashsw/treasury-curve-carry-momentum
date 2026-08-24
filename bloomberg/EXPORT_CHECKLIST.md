# Rates Curve Research Dataset: Bloomberg Export Checklist and Research Plan

Objective: pull everything needed for a Treasury Futures Curve Carry and Momentum strategy before terminal access ends. Bloomberg first, CEIC only where it adds anything, Databento deferred unless futures settlements are dirty.

General export settings:
- Frequency: daily, non-trading days omitted
- Date range: 2010-01-01 to latest, unless noted (pull from 2000 where history is free, storage is trivial and pre-GFC data helps regime work)
- Method: Excel BDH for time series, BDP/BDS for static contract fields. Save raw CSVs untouched, one file per block, with a naming convention like `ust_cash_yields_daily.csv`
- Watch the monthly data limit on terminal Excel pulls. Prioritize Block 3, then Block 1, then Block 2, then Block 4

---

## Block 1: Cash Treasury Yield Curve (ESSENTIAL)

Supports: curve level/slope/curvature features, carry and roll-down calculation, steepener/flattener signals, butterfly, regression hedging weights.

Source: Bloomberg primary. Free backup exists (FRED CMT `DGS` series and Gurkaynak-Sack-Wright zero curve from the Fed), so if terminal time runs out, this block is recoverable later. Still worth pulling while terminal access lasts, because Bloomberg is cleaner.

| Ticker | Tenor | Notes |
|---|---|---|
| USGG3M Index | 3M | |
| USGG6M Index | 6M | |
| USGG12M Index | 1Y | |
| USGG2YR Index | 2Y | |
| USGG3YR Index | 3Y | |
| USGG5YR Index | 5Y | |
| USGG7YR Index | 7Y | |
| USGG10YR Index | 10Y | |
| USGG20YR Index | 20Y | 20Y issuance restarted 2020, check series continuity |
| USGG30YR Index | 30Y | |

Fields: PX_LAST (yield). That is all the cash block requires.

Derived series (compute locally, do not export): 2s10s, 5s30s, 3m10y, 2s5s10s butterfly (2*5Y - 2Y - 10Y), plus first three PCA factors. Never export spread tickers when the legs are already pulled; one canonical source per series.

Optional add: GT2 Govt, GT5 Govt, GT10 Govt, GT30 Govt (on-the-run CUSIP yields) for an on-the-run vs constant-maturity basis. Skip if time-constrained.

---

## Block 2: OIS / SOFR / Swap Curve (ESSENTIAL for carry, policy expectations; smaller than Block 1)

Supports: risk-free discounting for carry math, policy expectation features, swap spread regime signals, macro regime filter inputs.

Source: Bloomberg only. CEIC does not have usable swap curves, FRED coverage is poor here. This block is the hardest to reconstruct after access ends, so treat it as high priority despite being "supporting" data.

SOFR OIS (live curve, starts ~2018):
- USOSFR1 Curncy, USOSFR2, USOSFR3, USOSFR5, USOSFR7, USOSFR10, USOSFR30 Curncy
- Short end: USOSFRA Curncy (1M), USOSFRC (3M), USOSFRF (6M) for policy path

Pre-2018 splice (needed for 2010+ history):
- Fed funds OIS: USSO1, USSO2, USSO3, USSO5, USSO10 Curncy
- USD LIBOR swaps: USSW2, USSW5, USSW10, USSW30 Curncy (for swap spread history only)

Policy expectations:
- Fed funds futures: FF1 Comdty through FF12 Comdty, PX_LAST. ESSENTIAL for the macro regime filter and duration momentum conditioning
- FDTR Index (Fed funds target upper bound) for realized policy

Fields: PX_LAST throughout.

Essential subset if rationing: USOSFR2/5/10/30, USSO2/5/10, FF1-FF8, FDTR.

---

## Block 3: Treasury Futures Curve (ESSENTIAL, highest priority, hardest to replace)

Supports: the actual tradables. Momentum, carry/roll, 2Y vs 10Y, 5Y vs 30Y, butterfly, duration momentum. This is the block where Databento is the fallback, so exhaust Bloomberg here first.

Bloomberg generic tickers (CME code in brackets):

| Generic | Contract | CME |
|---|---|---|
| TU1, TU2, TU3 Comdty | 2Y Note | ZT |
| FV1, FV2, FV3 Comdty | 5Y Note | ZF |
| TY1, TY2, TY3 Comdty | 10Y Note | ZN |
| UXY1, UXY2 Comdty | Ultra 10Y | TN (optional, listed 2016) |
| US1, US2, US3 Comdty | Bond | ZB |
| WN1, WN2, WN3 Comdty | Ultra Bond | UB (listed 2010) |

Time series fields (BDH, daily, 2010 to latest):
- PX_SETTLE (fall back to PX_LAST if PX_SETTLE is sparse pre-2015)
- PX_VOLUME
- OPEN_INT
- FUT_CUR_GEN_TICKER (which contract the generic maps to each day; critical for reconstructing rolls)

Contract-level static fields (BDP/BDS on individual contracts, e.g. TUZ5 Comdty, for every quarterly contract back to 2010, roughly 65 contracts per root):
- LAST_TRADEABLE_DT
- FUT_NOTICE_FIRST
- FUT_DLV_DT_FIRST, FUT_DLV_DT_LAST
- FUT_CONT_SIZE, FUT_TICK_SIZE

Strongly recommended extras (this is where Bloomberg beats Databento):
- FUT_CTD_CUSIP or CTD bond identifier, conversion factor, gross basis, implied repo rate for at least the front contract of each root. Even a snapshot history via the DLV screen exported per roll cycle is valuable. Precise carry/roll for futures runs through the CTD, and CME raw data does not provide it.

Two important caveats:
1. Bloomberg generics roll on a default rule (relative to last trade date). Research generally calls for a custom roll rule (volume-based, or fixed days before first notice). That is why FUT_CUR_GEN_TICKER plus contract-level dates are essential: together they allow a back-adjusted continuous series to be rebuilt under any roll rule.
2. Check generic settings via DOCS/FAQ on the terminal if TU1 history looks odd around roll dates. If settlements look clean, Databento is unnecessary for daily-frequency work; it only becomes relevant for intraday.

---

## Block 4: Rates Volatility and Macro Controls (MOVE essential, rest optional)

Supports: macro regime filter (including for the FX options VRP project), vol-scaling of positions, carry signal conditioning.

| Data | Ticker | Source | Priority |
|---|---|---|---|
| MOVE index | MOVE Index | Bloomberg | ESSENTIAL |
| 3M10Y swaption normal vol | USSN0C10 Curncy (verify ticker on terminal, swaption vol tickers vary) | Bloomberg | Optional, nice for rates VRP crossover |
| VIX | VIX Index | Bloomberg or free (CBOE) | Optional via Bloomberg, free elsewhere |
| DXY | DXY Index | Bloomberg or free | Optional |
| 10Y breakeven | USGGBE10 Index | Bloomberg, FRED backup (T10YIE) | Optional |
| 5y5y inflation swap | FWISUS55 Index | Bloomberg | Optional |
| ACM term premium | Free from NY Fed website | Free | Do not spend terminal quota |
| CPI, PCE, NFP, ISM | Standard macro releases | BLS/BEA/FRED | Skip on Bloomberg |

CEIC verdict: skip entirely for this project. Everything CEIC offers here is duplicated by BLS/BEA/FRED or by Bloomberg, so any CEIC quota is better spent elsewhere.

Databento verdict: not needed at daily frequency. Revisit only if (a) Bloomberg PX_SETTLE has unpatchable gaps, or (b) intraday futures are required for execution research. Not worth paying for at this stage.

---

## Priority order if terminal time is short

1. Block 3 generics + FUT_CUR_GEN_TICKER (irreplaceable without paying)
2. Block 3 contract-level dates and CTD/implied repo
3. Block 2 SOFR OIS + FF futures (poor free substitutes)
4. Block 1 cash curve (recoverable from FRED/GSW if missed)
5. MOVE
6. Everything else

---

## Research Plan

Phase 0: Data validation (week 1)
- Reconstruct continuous futures under two roll rules (volume crossover, N days before first notice). Compare to Bloomberg generics. Reconcile roll-date jumps.
- Cross-check cash yields against FRED CMT. Flag divergences > 3bp.

Phase 1: Features (week 2)
- Curve: level, slope (2s10s, 5s30s, 3m10y), curvature (2s5s10s), PCA factors 1-3
- Carry and roll-down per futures root: futures-implied yield carry via CTD, or the cheap approximation (spot yield minus rolled-forward yield) plus calendar spread (front minus second contract) as futures roll yield
- Momentum: 1M/3M/12M returns on back-adjusted continuous series, and slope momentum (change in 2s10s over 1M/3M)
- Vol: 60d realized vol per root for position scaling, MOVE level and z-score

Phase 2: Single-leg strategies (weeks 3-4)
- Duration momentum: time-series momentum per root, vol-scaled, monthly rebalance. This is the baseline; it is well documented in the literature and is expected to roughly work
- Carry: long roots with highest carry+roll per unit of duration vol, cross-sectional and time-series versions

Phase 3: Curve strategies (weeks 5-6)
- 2Y vs 10Y: DV01-neutral TU vs TY, signal = slope momentum plus carry differential. DV01 weights from futures DV01 (CTD DV01 / conversion factor), recomputed each roll
- 5Y vs 30Y: FV vs US (or WN), same architecture
- Butterfly: TU/FV/TY DV01-neutral fly, signal = curvature mean reversion vs carry
- Horse race all against the duration momentum baseline using the standard walk-forward + Diebold-Mariano setup

Phase 4: Macro regime filter (week 7)
- Build a small regime classifier from: MOVE z-score, 2s10s level and 3M change, FF-futures-implied hikes/cuts over next 6 months, breakeven trend
- Test as an overlay on Phase 2-3 strategies, then export the same regime series as a conditioning variable for downstream projects. One regime engine, several consumers

Deliberately excluded to avoid overcomplication: relative value vs swaps (needs cleaner swap data), CTD optionality modeling, intraday anything, non-USD curves. All can be v2.
