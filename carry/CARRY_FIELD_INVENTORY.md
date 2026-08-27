# CARRY_FIELD_INVENTORY.md

**Phase 1 of the carry extension. Field audit only — no strategy, no results.**

Audited 2026-08-24 against the immutable source export at
the read-only export folder named by `$BBG_CSV` (nothing in that directory was
modified). Reproduce with `carry/audit/inventory.py`, `roll_audit.py`, `feasibility.py`.

This document answers one question: **which definitions of Treasury-futures carry can actually be
constructed from the data we hold?** It does not propose a strategy — that is `CARRY_DESIGN.md`.

---

## 0. A date-parsing trap, resolved first

The export uses **two different date conventions in the same folder**, and getting this wrong
silently destroys ~60% of the sample:

| File class | Date format | Correct parse |
|---|---|---|
| All time-series CSVs (`*_Comdty.csv`, `*_Index.csv`, `*_Curncy.csv`, `*_DV01.csv`) | ISO `YYYY-MM-DD HH:MM:SS` | `format="%Y-%m-%d %H:%M:%S"` — **never `dayfirst`** |
| Contract-chain statics (`*_STATIC.csv`) | `d/m/yyyy` (e.g. `21/6/1982`) | `dayfirst=True` |

Parsing the ISO time series with `dayfirst=True` (as the existing pipeline correctly does *only*
for statics) coerces ~60% of rows to NaT and produces a bogus end date of 2026-12-06. The audited
figures below use the correct convention per file class. Any carry code must do the same.

> This is the same locale hazard `DATA.md` already documents for contract date fields. It applies in
> the opposite direction for the time series.

## 1. Sample envelope

| Property | Value |
|---|---|
| Futures span | **2010-01-04 → 2026-07-06** (UXY from 2016-01-11, WN from 2010-01-11) |
| Cash curve span | 2010-01-01 → 2026-07-07 |
| DV01 span | 2010-01-04 → 2026-07-08 |
| Valid futures observations | **~4,160** per root (4,175 rows, 0.3% blank settles) |
| Business-day coverage | 96.6% futures, 99.9–100% cash curve, 95.7% DV01 |
| Roll cycle | **exactly 4.0 rolls/yr** per root (quarterly H/M/U/Z), 66–67 distinct generic-1 contracts in sample |

This reconciles with the canonical paper's 4,173-row aligned panel, so the carry work sits on the
same sample as the existing momentum / mean-reversion results.

## 2. Complete field universe

**There are only five distinct schemas in the entire export.** Nothing else exists.

| Schema | Fields | Files |
|---|---|---|
| Futures time series | `Date, PX_SETTLE, PX_VOLUME, OPEN_INT, FUT_CUR_GEN_TICKER` | generics 1–3 for TU/FV/TY/US/WN; 1–2 for UXY |
| DV01 side file | `Date, CONVENTIONAL_CTD_FORWARD_FRSK` | generic 1, all six roots |
| Contract statics | `CONTRACT, LAST_TRADEABLE_DT, FUT_NOTICE_FIRST, FUT_DLV_DT_FIRST, FUT_DLV_DT_LAST, FUT_CONT_SIZE, FUT_TICK_SIZE` | generic-1 chain, all six roots |
| Rate/index series | `Date, PX_LAST` | cash curve, SOFR OIS, legacy OIS, swaps, FF futures, FDTR, MOVE, VIX, BE10 |
| Cross-country yields | `date, 2Y, 5Y, 10Y, 30Y` | US/DE/JP/CA (belongs to `global-rates-rv`) |

### 2.1 Field-by-field detail

For each field: instrument, frequency, coverage, missingness, whether it is **contemporaneously
observable** (known at the close of date *t*), whether it is **ex-ante usable** (available strictly
before the return it would predict), economic meaning, and which carry definition it supports.

| Field | Instruments | Freq | Coverage | Miss | Observable at *t* | Ex-ante usable | Economic meaning | Supports |
|---|---|---|---|---|---|---|---|---|
| `PX_SETTLE` | TU/FV/TY/UXY/US/WN generics **1, 2, 3** | daily | 2010-01→2026-07 (UXY 2016→) | 0.1–0.6% | Yes (settlement) | Yes, lagged one day | Futures settlement price | **Candidate B** (calendar-spread carry) and all return construction |
| `FUT_CUR_GEN_TICKER` | generics 1–3, all roots | daily | full | ~0.3% | Yes | Yes | Which dated contract the generic points to | Roll identification; contract mapping; roll-window exclusion |
| `OPEN_INT` | generics 1–3 | daily | g1 ~97%, g2 71–97%, **g3 4–53%** | see below | Yes | Yes | Liquidity / whether the contract is real | Liquidity screen; **rules generic 3 out as a primary input** |
| `PX_VOLUME` | generics 1–3 | daily | g1 ~97%, g3 sparse | — | Yes | Yes | Traded volume | Liquidity screen only |
| `CONVENTIONAL_CTD_FORWARD_FRSK` | generic 1, six roots | daily | 95.7% | 0.00% within span | Yes | Yes, lagged one day | **DV01**: forward risk to delivery of the CTD, conversion-factor adjusted, $/bp per contract | DV01 normalisation for **all** candidates; leg weighting for curve trades |
| `LAST_TRADEABLE_DT`, `FUT_NOTICE_FIRST`, `FUT_DLV_DT_FIRST`, `FUT_DLV_DT_LAST` | contract chain | static | 100% parsed, 72 in-sample contracts/root | 0% | Yes | Yes | Delivery timing | **Δt for annualising the calendar spread**; roll-window definition |
| `FUT_CONT_SIZE` | chain | static | 100% | 0% | Yes | Yes | Notional per contract (TU $200k, others $100k) | Scaling to dollar P&L |
| `FUT_TICK_SIZE` | chain | static | 100% | 0% | Yes | Yes | Minimum price increment | Transaction costs (already used canonically) |
| `PX_LAST` (`USGG3M…30YR`) | 9 usable tenors | daily | ~100%, 2010→2026 | 0% | Yes | Yes, lagged one day | Constant-maturity par yield | **Candidate C** (carry & roll); rolldown interpolation |
| `PX_LAST` (`USGG20YR`) | 20Y | daily | **starts 2020-05-21** | 0% after start | Yes | Yes | 20Y par yield | Optional extra interpolation node post-2020 only |
| `PX_LAST` (`USOSFRA/C/F`) | SOFR OIS ~1M/3M/6M *(tenor letters inferred from level ordering — confirm on terminal)* | daily | 98.7–99.2% | 0% | Yes | Yes | Short-dated OIS — financing proxy | Financing leg of **Candidate C** |
| `PX_LAST` (`USOSFR1…30`) | SOFR OIS 1–30Y | daily | 98.2–99.2% | 0% | Yes | Yes | OIS curve | Alternative discount curve; financing robustness |
| `PX_LAST` (`USSO1…10`) | legacy USD OIS 1–10Y | daily | 89–99.5% | 0% | Yes | Yes | Fed-funds OIS | Pre-2018 financing robustness |
| `PX_LAST` (`USSW2…30`) | USD swaps 2–30Y | daily | **ends 2023-06-30** | 0% | Yes | Yes | LIBOR-era swap curve | Not usable for the full sample; robustness only |
| `PX_LAST` (`FF1…FF12`) | fed funds futures | daily | 100% | 0% | Yes | Yes | Expected average fed funds, 1–12 months out (100 − price) | **Best pre-2018 financing proxy**; policy-path conditioning |
| `PX_LAST` (`FDTR`) | fed funds target | daily | 100% | 0% | Yes | Yes | Policy rate | Financing floor; regime splits |
| `PX_LAST` (`MOVE`, `VIX`, `USGGBE10`) | vol / breakeven | daily | ~100% | 0% | Yes | Yes | Rates vol, equity vol, 10y breakeven | Regime conditioning (MOVE already canonical) |

**Open-interest detail — this is what disqualifies generic 3.** Median open interest, generic 1 → 2 → 3:

| Root | g1 median OI | g2 median OI | g3 median OI | g3 OI coverage |
|---|---|---|---|---|
| TU | 937,869 | 131,607 | **10** | 24.2% |
| FV | 1,476,607 | 177,992 | **6** | 17.1% |
| TY | 2,598,191 | 39,968 | **15** | 40.3% |
| US | 643,501 | 7,519 | **9** | 53.0% |
| WN | 506,715 | 11,105 | **2** | 3.8% |
| UXY | 693,460 | 22,616 | — | (no g3 pulled) |

Generic-3 *prices* exist at 96.6% coverage, but with a median open interest of 2–15 contracts those
prices are not tradeable marks. **Generic 3 is a robustness input only, never a primary signal.**

## 3. Feasibility verdict by carry definition

### 3.1 Definition 1 — TRUE FUTURES / CTD CARRY (implied repo, net basis) → **NOT FEASIBLE**

Required inputs against what we hold:

| Required | Bloomberg field | Present? | Note |
|---|---|---|---|
| CTD identification | `FUT_CTD_CUSIP` | **No** | Requested by the v6 exporter, **not in any delivered file** |
| Conversion factor | `CTD_CNVS_FACTOR` | **No** | Requested; author's terminal note: *"only resolves on the ACTIVE generic ticker, not on dated chain members"* |
| Implied repo | `FUT_IMPLIED_REPO_RT` | **No** | Requested; author's terminal note: *"only meaningful (and populated) for live contracts"* — **no history** |
| Invoice price | — | No | Never requested |
| Accrued interest | — | No | Never requested |
| CTD coupon / cashflows | — | No | Never requested |
| CTD yield | `FUT_CTD_YLD` | No | Never requested |
| Gross / net basis | `FUT_GROSS_BASIS`, `FUT_NET_BASIS` | No | Never requested |
| Actual GC repo rate | — | No | Never requested; no repo series in the export |
| Delivery timing | ✔ statics | **Yes** | Complete |
| DV01 | ✔ `CONVENTIONAL_CTD_FORWARD_FRSK` | **Yes** | Complete |

**Verdict: infeasible, and not merely un-pulled — structurally unavailable by this route.** The
exporter *did* ask for the three fields that matter, and the author's own July-2026 terminal notes
(recorded in `BloombergPull_v6.bas` lines 164–176) record why they came back empty: conversion
factors do not resolve on dated chain members, and implied repo populates only for live contracts.
So even re-running the existing pull would not produce a historical implied-repo or
conversion-factor series. See §5 for what would.

We have exactly two of the ten required inputs. Attempting this definition would require inventing
the other eight.

### 3.2 Definition 2 — CURVE ROLLDOWN / CARRY → **FEASIBLE**

| Required | Present? | Detail |
|---|---|---|
| Cash Treasury curve | **Yes** | 9 usable tenors (3M, 6M, 1Y, 2Y, 3Y, 5Y, 7Y, 10Y, 30Y), 4,305 obs, **zero NaN**, 2010-01→2026-07 |
| Maturity mapping | **Yes** | Constant-maturity par yields; tenors known exactly |
| Interpolation | **Yes** | Log-linear or monotone-cubic on 9 nodes; 20Y node available post-2020 as a robustness check |
| Expected yield change from ageing | **Yes** | `roll(τ,h) = y(τ) − y(τ−h)`, both endpoints interpolated on the same curve at the same date |
| Financing rate | **Yes** | `USGG3M` (bill, 100% coverage, full sample) primary; `USOSFRA/C/F`, `FF1–FF12`, `FDTR` as alternatives |
| Translation to DV01-adjusted P&L | **Yes** | Bloomberg `CONVENTIONAL_CTD_FORWARD_FRSK` per root |

**Descriptive feasibility check** (quarterly horizon, `h = 0.25y`, financing = 3M bill):

| τ | carry = y(τ) − r_f | rolldown per quarter | rolldown sd | carry > 0 |
|---|---|---|---|---|
| 2y | +0.22% | **+2.9 bp** | 6.6 bp | 76.4% |
| 5y | +0.64% | **+3.7 bp** | 4.2 bp | 77.6% |
| 10y | +1.18% | **+2.1 bp** | 1.9 bp | 83.5% |
| 30y | +1.82% | **+0.8 bp** | 0.4 bp | 87.5% |

The rolldown profile **peaks at 5y and collapses at 30y**, which is the textbook shape — rolldown is
largest where the curve is steepest and near zero where it is flat. Carry rises monotonically with
tenor, as it must in a mostly upward-sloping sample. This is strong evidence the construction is
correct rather than merely computable.

### 3.3 Definition 3 — DV01-NEUTRAL CURVE-TRADE CARRY → **FEASIBLE**

| Required | Present? | Detail |
|---|---|---|
| 2s10s legs (TU, TY) | **Yes** | Both roots, full sample, both DV01s |
| 5s30s legs (FV, US) | **Yes** | Both roots, full sample, both DV01s |
| 2s5s10s butterfly (TU, FV, TY) | **Yes** | All three roots and DV01s |
| Per-leg expected carry/rolldown | **Yes** | From §3.2 at the leg's curve tenor |
| Same DV01 weights as canonical strategies | **Yes** | Identical `hedge_ratio()` inputs — `DV01_long / DV01_short`, lagged one day, clipped [0.1, 10] |

Because the weights are the *same objects* the canonical mean-reversion strategies already use, the
carry of each book is a clean linear combination and the results are directly comparable to the
existing canonical numbers. Nothing new has to be assumed.

### 3.4 Bonus definition — FUTURES CALENDAR-SPREAD CARRY (KMPV) → **FEASIBLE, and futures-native**

Not in the brief's list, but it is the one definition that needs **no cash-bond approximation and no
CTD information at all**, and it uses generics 2 which `DATA.md` records as pulled-but-unused.

`carry_ann = (F₁ − F₂) / F₂ / Δt`, with Δt from the delivery-date statics (0.25y quarterly).

| Root | n | mean | sd | p5 | p95 | positive |
|---|---|---|---|---|---|---|
| TU | 4,160 | +0.18% | 0.94% | −1.56% | +1.54% | 63.4% |
| FV | 4,160 | +0.88% | 1.58% | −1.63% | +3.57% | 67.5% |
| TY | 4,160 | +1.30% | 1.86% | −1.92% | +4.68% | 76.5% |
| UXY | 2,640 | +0.44% | 1.98% | −3.27% | +4.02% | 62.0% |
| **US** | 4,160 | +1.68% | **5.40%** | −3.00% | +4.72% | 82.7% |
| WN | 4,155 | +1.09% | 2.78% | −4.57% | +4.66% | 66.6% |

Carry is positive on average for every root and **rises with duration**, which is the correct sign
for an upward-sloping curve with financing below yield. Cross-sectional dispersion averages 1.62%
(the raw material for a cross-sectional carry book), and TY carry autocorrelation is 0.994 at one day
and 0.933 at 21 days — persistent enough for a monthly rebalance.

> **Two data problems to handle, both visible in the table.** `US` has an outlier-driven sd of 5.40%
> (raw spread min −19.4 points) and correlates only 0.07–0.21 with the other roots' carry, against
> 0.52–0.88 among the rest. That is a CTD-switch / roll-window artefact in the classic bond contract,
> not a signal. Any use of this measure needs roll-window exclusion and outlier winsorisation, and
> `US` needs a specific diagnostic before it is trusted.

## 4. What is *not* in the export, and therefore not claimable

- No CTD identity, conversion factor, invoice price, accrued interest, coupon, CTD yield, gross/net
  basis, implied repo, or actual repo — see §3.1.
- No intraday data; settlement marks only.
- No bid/ask or depth, so costs remain the canonical one-tick-per-side approximation.
- No TIPS, no STRIPS, no off-the-run bond level data.
- `USGG20YR` does not exist before 2020-05-21.
- `USSW*` swaps stop at 2023-06-30 (LIBOR transition).
- **SOFR OIS history before ~April 2018 is Bloomberg-constructed**, since SOFR did not exist. The
  `USOSFR*` series carry values back to 2010, so they must be treated as backfilled/proxy for the
  first third of the sample. For pre-2018 financing, `USGG3M` and `FF1–FF12` are the honest choices.

## 5. Data pull that would unlock true CTD carry

If Definition 1 is ever wanted, this is the specific request — flagged where terminal behaviour
needs confirmation:

1. **`FUT_IMPLIED_REPO_RT` as a historical time series (BDH) on the generic tickers** `TU1/FV1/TY1/UXY1/US1/WN1 Comdty`, not on the dated chain. The author's note says it populates only for live contracts *on the chain*; whether BDH on the generic returns history needs testing on the terminal. **This single field would make Definition 1 feasible on its own.**
2. **`FUT_CTD_CUSIP` as a BDH series on the generics** — gives the CTD identity path through time. Confirmed to work per-contract, so it should work as a generic series.
3. **Per-CUSIP bond statics** for every CTD identified in (2): `CPN`, `MATURITY`, `FIRST_SETTLE_DT`, and the conversion factor for that contract/CTD pair.
4. **`FUT_CNVS_FACTOR` / `CTD_CNVS_FACTOR` from the *active* generic ticker** (e.g. `TYA Comdty`) as a time series — the author's note says this is the only place it resolves.
5. **Gross and net basis** (`FUT_GROSS_BASIS`, `FUT_NET_BASIS`) as BDH on the generics — would give a direct cross-check on any implied-repo reconstruction.
6. **A GC repo series** (e.g. `USRG1T Curncy` or the DTCC GCF index) for a true financing leg rather than a bill/OIS proxy.

Items 1–2 are cheap and would be transformative. Items 3–4 are the fiddly part: reconstructing a
historical conversion-factor panel is genuinely laborious and is the reason most practitioners use a
vendor basis feed instead.

## 6. Summary

| Definition | Feasible? | Why |
|---|---|---|
| 1. True futures / CTD carry (implied repo, net basis) | **No** | 2 of 10 required inputs present; conversion factor and implied repo are not retrievable historically by this route |
| 2. Curve rolldown / carry | **Yes** | 9-tenor curve with zero NaN, 4,305 obs, plus DV01 and four financing proxies; rolldown profile is textbook-correct |
| 3. DV01-neutral curve-trade carry (2s10s, 5s30s, fly) | **Yes** | Uses the same DV01 hedge weights as the canonical strategies, so directly comparable |
| 4. Futures calendar-spread carry (KMPV) | **Yes** | Needs only generic-1/generic-2 prices and delivery dates; futures-native; requires roll-window and outlier handling, and `US` needs a diagnostic |

Recommendation and formulae: `CARRY_DESIGN.md`. Experiment plan: `CARRY_RESEARCH_PLAN.md`.
