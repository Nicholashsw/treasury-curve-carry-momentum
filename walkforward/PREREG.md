# Pre-registration: walk-forward test of curve mean-reversion

Written 22 October 2026, before any walk-forward result was computed. Committed and pushed
before the run, so the commit timestamp is the lock.

## Why

The README's curve results (2s10s mean-reversion net Sharpe 0.71, 5s30s 0.66) choose the
signal direction on the full sample, and the 252-day z-score window was never varied. The
README states that a walk-forward test is required before these are treated as a performance
claim. This is that test.

## Regimes

The four policy regimes of global-rates-rv (`gr_rv/subperiod.py`), defined there from
monetary-policy history before any result was seen:

| Regime | Window |
|---|---|
| R1 post-GFC QE | 2010-01-01 to 2014-12-31 |
| R2 divergence / NIRP | 2015-01-01 to 2019-12-31 |
| R3 COVID | 2020-01-01 to 2021-12-31 |
| R4 hiking / normalisation | 2022-01-01 to 2026-12-31 |

Three transitions: fit R1 and trade R2, fit R2 and trade R3, fit R3 and trade R4. Each test
regime is traded only with parameters fitted on the regime before it. Nothing from a test
regime is used to choose anything.

## What is fitted

For each spread (2s10s on TU/TY, 5s30s on FV/US), two parameters:

- direction: fade the spread z-score (mean-reversion) or follow it (momentum);
- z-score lookback: 63, 126, 252 or 504 trading days.

That is 8 candidates per spread per fit regime. The fitted candidate is the one with the
highest net Sharpe on the fit-regime dates; ties go to the longer lookback.

## What is held fixed

Everything else is the notebook as published (`notebooks/treasury_curve_pipeline.ipynb`),
executed unmodified and reused through its own functions: the z-score clip at ±3, the one-day
signal lag, the DV01 hedge from Bloomberg forward risk lagged one day, month-end rebalancing,
the 10% volatility target on a 63-day window with a 3x leverage cap and a 126-day warm-up, and
one-tick-per-side costs.

## How returns are produced

Each candidate is run once over the whole calendar with the notebook's `run_strategy`. Every
input at date t uses data to t-1 only, so rolling windows that reach back across a regime
boundary use information that existed at the time. Fit-regime Sharpe is computed on fit-regime
dates only; out-of-sample returns are the test-regime dates of the fitted candidate's run.

## Outcomes reported

1. Net Sharpe of the fitted candidate in each test regime (6 numbers: 2 spreads x 3 transitions).
2. Overall out-of-sample net Sharpe per spread on the three test regimes pooled (2015-2026).
3. HAC Diebold-Mariano against duration momentum, per transition and pooled, using the
   notebook's `dm_test` unchanged. Duration momentum is taken as published (63-day sign),
   not refitted, and sliced to the same dates.
4. For reference only, the full-sample specification (reversion, 252 days) on the same
   out-of-sample dates. This is not a walk-forward result and is labelled as such.

## Decision rule

The curve mean-reversion claim is supported out of sample for a spread if its pooled
out-of-sample net Sharpe is above zero and it is positive in at least 2 of the 3 test regimes.
Otherwise it is not supported. The DM test is reported but is not part of the rule, since the
full-sample DM was already insignificant. Six test-regime Sharpes and two pooled Sharpes are
reported in full whatever they show, and the README caveat is rewritten with the result.
