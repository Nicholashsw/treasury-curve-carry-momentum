# CARRY_DESIGN.md

**Phase 2 of the carry extension. Design only — no implementation, no results.**

Depends on `CARRY_FIELD_INVENTORY.md`, which establishes what the data supports. This document picks
a definition and specifies it precisely enough to implement without further judgement calls.

**Binding constraint from the brief:** carry must be an **ex-ante expected holding-period return
component**. It may use only information observable at or before the signal date. It must never be
realised future P&L relabelled.

---

## 1. What "carry" means for a Treasury future, precisely

The confusion worth clearing first, because it decides everything downstream.

For a **cash bond** bought with borrowed money, carry is unambiguous: you receive coupon accrual and
pay repo, so carry = (yield − financing) per unit time. Add the roll-down — the price gain from the
bond ageing down a static upward-sloping curve — and you have the standard desk measure "carry and
roll".

For a **futures** position, that decomposition does **not** transfer directly, and this is the trap:

> **A long futures position receives no coupon and pays no repo.** The futures price is set so that
> the cash-and-carry arbitrage is closed — net basis ≈ 0. The financing spread is therefore already
> *embedded in the futures price* relative to spot. If you add (yield − repo) to a futures position's
> expected return, you double-count.

What a long futures position actually earns, if the yield curve is unchanged over the holding period,
is the **convergence of the forward to the spot**: the futures price is a forward price on the CTD,
and as time passes the forward matures toward a spot whose yield sits further down an unchanged curve.
So for futures:

- **Expected return under an unchanged curve = the roll-down of the forward yield**, not the
  financing spread.
- Equivalently, and more usefully for us: it is the **term structure of futures prices** — the
  price differential between the near and deferred contracts — because that differential *is* the
  market's own pricing of carry over the intervening period.

Both routes are implementable here. The second requires no cash-bond approximation at all.

## 2. Candidate definitions

### Candidate A — True CTD carry via implied repo / net basis

**Formula.** For CTD with clean price *P*, accrued *AI*, coupon *c*, conversion factor *CF*,
futures price *F*, delivery in *T*:

$$\text{implied repo} = \frac{F\cdot CF + AI_T - (P + AI_0)}{(P+AI_0)}\cdot\frac{360}{T}, \qquad \text{net basis} = P - F\cdot CF - \text{carry to delivery}$$

**Verdict: NOT FEASIBLE.** We hold 2 of 10 required inputs (delivery dates, DV01). Conversion factors
do not resolve on dated chain members and implied repo populates only for live contracts, per the
author's own terminal notes — so this is not a matter of re-running the pull. Excluded. See
`CARRY_FIELD_INVENTORY.md` §3.1 and §5.

### Candidate B — Futures calendar-spread carry (Koijen–Moskowitz–Pedersen–Vrugt) ✅ **PRIMARY**

**Intuition.** Ask the market what carry is, instead of modelling it. If the deferred contract trades
below the near contract, then simply holding the near contract and rolling earns you that difference,
provided prices don't move. That differential is the market's own price of carry over the period
between the two deliveries, and it already contains financing, coupon and the delivery option — you
never have to estimate any of them.

**Formula.** For root *i* on date *t*, with generic-1 and generic-2 settlements $F^{(1)}, F^{(2)}$
and their dated deliveries $T_1, T_2$ from the contract statics:

$$C^{\text{KMPV}}_{i,t} \;=\; \frac{F^{(1)}_{i,t} - F^{(2)}_{i,t}}{F^{(2)}_{i,t}} \cdot \frac{1}{\Delta t_{i,t}}, \qquad \Delta t_{i,t} = \frac{T_2 - T_1}{365.25}$$

annualised, unitless. $\Delta t$ is taken from `FUT_DLV_DT_FIRST` of the two dated contracts named by
`FUT_CUR_GEN_TICKER`, **not** hardcoded at 0.25 — the actual gap varies with the calendar.

**Economic source of return.** Compensation for holding duration risk when the curve is upward
sloping and financing sits below yield. It is the futures-market expression of the term premium plus
the value of the delivery option. Cross-sectionally it is the slope of each root's own futures term
structure.

**Why it is the primary choice.** Standard and citable (Koijen, Moskowitz, Pedersen & Vrugt, *Carry*,
JFE 2018, which defines futures carry exactly this way and applies it to bond futures among nine asset
classes); fully ex-ante (both prices observed at *t*); futures-native, so it measures the instrument
the canonical strategies actually trade; requires **zero** unavailable fields; and it uses generics 2,
which `DATA.md` records as pulled but unused — an honest extension of the existing pull rather than a
new data dependency.

**Defensible in a rates interview?** Yes, and it is the answer a systematic-macro desk would expect.
The follow-up will be *"doesn't the CTD change between the two contracts?"* — and the honest answer is
yes, which is precisely the measure's main weakness (§4).

### Candidate C — Cash-curve carry and roll-down, DV01-converted ✅ **SECONDARY**

**Intuition.** Two separate sources of return for a bond position if nothing moves. You earn more
yield than you pay to finance (carry), and your bond gets shorter, sliding to a lower point on an
upward-sloping curve, which raises its price (roll-down). Add them.

**Formula.** For curve tenor τ, horizon *h*, financing rate $r_f$, and modified duration *D*:

$$\underbrace{\big(y_t(\tau) - r_{f,t}(h)\big)\cdot h}_{\text{carry}} \;+\; \underbrace{D_t(\tau)\cdot\big(y_t(\tau) - y_t(\tau - h)\big)}_{\text{roll-down}}$$

with $y_t(\tau-h)$ interpolated on the **same date's** curve — this is what makes it ex-ante: we never
use tomorrow's curve, only today's shape.

For DV01-consistent expected P&L on the futures book, use the Bloomberg DV01 rather than an
analytic duration:

$$\mathbb{E}[\text{P\&L}]_{i,t} = \mathrm{DV01}_{i,t}\cdot 10^{4}\cdot\big(y_t(\tau_i) - y_t(\tau_i - h)\big)$$

**Role.** Secondary rather than primary for one reason: the futures-to-curve-tenor mapping requires
assuming a CTD maturity per root, and we do not know the CTD. Mapping TU→2y and FV→5y is safe; TY→7y
and US→20y are conventions, not facts. **Candidate C's real value is (a) as an independent cross-check
on Candidate B, and (b) as the only clean route to per-leg carry for the DV01-neutral curve trades**,
where the leg tenors are exactly the curve points the canonical signals already use (2y/10y, 5y/30y).

**Financing choice.** `USGG3M` (3-month bill) as primary — 100% coverage over the full sample and the
natural financing proxy for a Treasury position. Robustness: `USOSFRA/C/F`, `FF1–FF12`, `FDTR`. Not
SOFR OIS pre-2018 as a primary, because that history is Bloomberg-constructed (SOFR did not exist).

### Candidate D — Curve-trade carry under canonical DV01 weights ✅ **DERIVED**

Not an independent measure but the object the brief's item 3 asks for. Given per-leg carry $C$ from
Candidate B or C, and the **same hedge ratio the canonical strategies already use**
($h_t = \mathrm{DV01}^{\text{long}}_{t-1} / \mathrm{DV01}^{\text{short}}_{t-1}$, lagged one day,
clipped to [0.1, 10]):

$$C^{2s10s}_t = C^{TY}_t - h_t\, C^{TU}_t, \qquad C^{5s30s}_t = C^{US}_t - h_t\, C^{FV}_t$$
$$C^{\text{fly}}_t = 2\,C^{FV}_t - h^{a}_t\, C^{TU}_t - h^{b}_t\, C^{TY}_t$$

Computing this **both ways** (from B and from C) and comparing is a genuine robustness test: two
independent constructions of the same economic quantity.

## 3. Recommendation

| | Definition | Role |
|---|---|---|
| **Primary** | **Candidate B — KMPV calendar-spread carry**, per root. A *raw price-spread signal*; **no DV01 appears in the transformation** | Standalone carry signal; cross-sectional carry book; conditioning variable |
| **Secondary** | **Candidate C — cash-curve carry and roll**, DV01-converted | Independent cross-check; per-leg carry for curve trades |
| **Derived** | **Candidate D** under canonical DV01 weights | 2s10s / 5s30s / butterfly carry, computed from both B and C |
| **Excluded** | Candidate A — true CTD carry | Data structurally unavailable |

## 3a. Signal versus position sizing — kept strictly separate

**Implementation note added at Phase 4 (2026-08-24).** An earlier draft of §3 described the primary
measure as "DV01-normalised", which conflated two different stages. It does not. The KMPV formula is a
**pure price-spread signal**: it contains two futures prices and a time interval, and **no DV01 term
appears anywhere in it**. DV01 enters only later, when the signal is turned into a position.

The pipeline, in the order it executes:

```
  (1) RAW CARRY SIGNAL            C[i,t] = (F1 - F2) / F2 / dt
      units: annualised fraction  <- no DV01 anywhere in this expression
      inputs: two settlement prices at t, delivery dates fixed at listing
                      |
                      v
  (2) SIGNAL CONDITIONING         roll-window exclusion, trailing winsorisation,
      still unitless              trailing z-score or cross-sectional rank
                      |
                      v
  (3) DV01-NORMALISED POSITION    contracts[i,t] = score[i,t-1] / DV01[i,t-1]
      units: contracts            <- DV01 enters HERE, and only here
      curve books instead use the canonical hedge_ratio() = DV01_long / DV01_short
                      |
                      v
  (4) VOL SCALING                 x min(target_vol / realised_63d_vol, 3), lagged,
      units: contracts            126-day warm-up   [canonical run_strategy()]
                      |
                      v
  (5) REALISED P&L                (position . return) - turnover x tick_cost
      units: fraction of NAV      <- the only place realised returns appear
```

Stage (1) is the ex-ante expected-return estimate. Stage (3) is risk allocation: it makes a
1-contract TU position and a 1-contract WN position comparable in interest-rate risk (DV01 medians
1.84 vs 25.76 $/bp, a 14x difference). Conflating them would make the *signal* look duration-dependent
when it is not, and would make the *risk allocation* look like part of the forecast when it is not.

The secondary cash-curve measure differs here in an important way: its roll-down term is expressed in
**basis points of yield**, so converting it to expected P&L genuinely does require a DV01 multiplication
inside the signal definition (`DV01 x 1e4 x dy`). That is a real difference between the two measures and
is why they are specified separately rather than as variants of one formula.

## 4. Full specification of the primary measure

| Aspect | Specification |
|---|---|
| **Signal** | $C^{\text{KMPV}}_{i,t}$ per root, as §2 Candidate B |
| **Timing convention** | Both settlements observed at the close of *t*. Signal formed on *t*, **lagged one day**, position held from the *t+1* settle. Identical to the canonical `run_strategy()` protocol (`.shift(1)`), so carry inherits the existing leakage-free harness rather than needing a new one |
| **Signal formation date** | Month-end *t* (canonical rebalance), using data through the close of *t* |
| **Holding period** | One month, monthly rebalance — matching the canonical strategies exactly, so comparisons are like-for-like |
| **Look-ahead prevention** | (i) both price legs are contemporaneous, never forward-looking; (ii) `.shift(1)` on the signal; (iii) $\Delta t$ from *static* delivery dates known at contract listing; (iv) DV01 lagged one day; (v) vol scaler lagged one day with a 126-day warm-up; (vi) **no** parameter, threshold or z-score window fitted on the full sample — all standardisation windows are trailing-only |
| **Futures roll treatment** | Two separate things. (1) *Return construction* is unchanged: the canonical `continuous()` difference back-adjustment from `FUT_CUR_GEN_TICKER`. (2) *Signal construction* must **exclude the roll window** — the ±3 business days around a change in `FUT_CUR_GEN_TICKER` — because at the roll the generic-1/generic-2 pair re-points and the spread is mechanically discontinuous. Carry is forward-filled from the last clean pre-roll value across the excluded window |
| **Financing treatment** | **None applied.** Financing is already inside the calendar spread; adding a financing term would double-count (§1). Candidate C is where financing enters explicitly, and that is the point of running both |
| **DV01 treatment** | Signal is unitless and duration-agnostic by construction. Positions are DV01-normalised so each root contributes equal interest-rate risk: contract weight $\propto \mathrm{sign\ or\ score} / \mathrm{DV01}_{i,t-1}$. Curve books use the canonical `hedge_ratio()` unchanged |
| **Transaction costs** | Canonical model unchanged: one tick per contract per side using each contract's own `FUT_TICK_SIZE`. Carry is highly persistent (TY autocorrelation 0.933 at 21 days), so turnover should be *lower* than the canonical mean-reversion books — which must be measured, not assumed |
| **Contract mapping** | `FUT_CUR_GEN_TICKER` on generic 1 and generic 2 gives the two dated contracts; delivery dates from the `*_STATIC.csv` chain keyed on `CONTRACT` |
| **Behaviour at delivery/roll** | Roll window excluded from signal formation (above). Positions are not held into the notice period: the canonical monthly rebalance already moves with the generic, and any rebalance falling inside a roll window is deferred to the next clean date |
| **Outlier handling** | Winsorise the raw spread at the 1st/99th percentile **per root, using a trailing expanding window only** (never full-sample). Required because `US` shows a raw spread minimum of −19.4 points and a carry sd of 5.40% against 1.86% for TY, and correlates only 0.07–0.21 with other roots' carry against 0.52–0.88 among the rest |
| **Universe** | Six roots; UXY enters 2016-01-11. Liquidity screen: generic-2 `OPEN_INT` above a trailing threshold, which drops nothing material for generics 1–2 but documents the check |

## 5. Limitations of the primary measure — stated up front

1. **CTD change between contracts.** The near and deferred contracts may have different
   cheapest-to-deliver bonds, so the spread mixes true carry with a CTD/duration difference. This is
   the measure's principal weakness and the reason Candidate C exists as a cross-check.
2. **The delivery option is embedded, not isolated.** The spread contains the value of the short's
   timing and quality options, which vary with yield level and volatility. In low-rate, low-vol
   regimes this contamination is small; in 2022 it is not.
3. **`US` is contaminated.** See §4. The classic bond contract has the widest CTD basket and the most
   switching, and its carry series shows it. It may have to be excluded, and that decision must be
   made on a diagnostic rather than on its effect on performance.
4. **Roll-window discontinuity** is mechanical and handled by exclusion, but exclusion itself removes
   ~6% of observations (±3 days × 4 rolls × 6 roots).
5. **Quarterly Δt means the signal is a 3-month-ahead expectation** used for a 1-month holding period.
   That mismatch is standard in the KMPV literature but it is an approximation.
6. **No decomposition.** Unlike a true implied-repo measure, this cannot separate financing from term
   premium from delivery-option value. It measures their sum. For a forecasting signal that is
   acceptable — and it is exactly the tradeoff the macro VAR lab found in the opposite direction:
   more identification, less predictive content.
7. **Sample is one country and one regime-rich window** (2010–2026: ZIRP, QE, 2022 hikes,
   normalisation). Carry strategies are known to be regime-sensitive, so subperiod stability is not
   optional — it is the main test.

## 6. Why this is *not* realised P&L relabelled

Worth stating explicitly, since it is the brief's central requirement. At date *t* the signal uses:
$F^{(1)}_t$, $F^{(2)}_t$ (both observed at the close of *t*), delivery dates fixed at listing, and
$\mathrm{DV01}_{t-1}$. It uses **no** price, yield or return dated after *t*. The quantity it
estimates — the return to holding the near contract if prices are unchanged — is an expectation
formed from the cross-section of today's futures curve, not a measurement of what subsequently
happened. The realised return over *t → t+1* appears only on the left-hand side of the evaluation,
never inside the signal.

The same holds for Candidate C: $y_t(\tau)$ and $y_t(\tau - h)$ are two points on **the same date's**
curve. The roll-down term asks "where would this bond sit on today's curve if it were *h* shorter",
which is a statement about today's curve shape, not about tomorrow's yields.
