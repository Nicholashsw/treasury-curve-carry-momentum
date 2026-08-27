"""Carry signal construction.

STAGE (1)-(2) of the pipeline in CARRY_DESIGN.md section 3a. No DV01 enters the
primary signal; DV01 belongs to position construction (carry_positions.py).

Every value at date t uses only information observable at or before t.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
import pandas as pd
import carry_data as D

# ---- pre-specified cleaning constants (fixed BEFORE any performance is seen) --
DV01_JUMP = 0.05        # |d DV01 / DV01| flagging a CTD switch
DISLOC_K = 6.0          # |spread - trailing median| > K * trailing IQR
DISLOC_WIN = 252        # trailing window for median/IQR (no look-ahead)
GUARD_BUFFER = 10       # business days masked either side of a flag
ROLL_DAYS = 3           # +/- bd around a generic roll
WINSOR_Q = 0.01         # trailing expanding winsorisation


def raw_calendar_spread(root):
    f1 = pd.to_numeric(D.futures(root, 1)["PX_SETTLE"], errors="coerce")
    f2 = pd.to_numeric(D.futures(root, 2)["PX_SETTLE"], errors="coerce")
    j = pd.concat([f1, f2], axis=1, keys=["g1", "g2"]).dropna()
    return j["g1"] - j["g2"], j["g2"]


def ctd_guard(root, index):
    """Root-agnostic mask of dates where the near/deferred pair is NOT a clean
    carry observation. Two mechanical detectors, unioned, then buffered.

      (a) DV01 discontinuity  -> the generic-1 CTD changed
      (b) persistent dislocation of the spread from its own trailing behaviour
          (trailing median/IQR only; nothing forward-looking)
    """
    sp, _ = raw_calendar_spread(root)
    sp = sp.reindex(index)

    d = D.dv01(root).reindex(index).ffill()
    jump = d.pct_change().abs() > DV01_JUMP

    med = sp.rolling(DISLOC_WIN, min_periods=60).median().shift(1)
    q75 = sp.rolling(DISLOC_WIN, min_periods=60).quantile(.75).shift(1)
    q25 = sp.rolling(DISLOC_WIN, min_periods=60).quantile(.25).shift(1)
    iqr = (q75 - q25).replace(0, np.nan)
    disloc = (sp - med).abs() > DISLOC_K * iqr

    flag = (jump.fillna(False) | disloc.fillna(False))
    m = flag.copy()
    for k in range(1, GUARD_BUFFER + 1):
        m |= flag.shift(k, fill_value=False) | flag.shift(-k, fill_value=False)
    return m.fillna(False)


def carry_kmpv(root, apply_guard=True, apply_winsor=True, roll_days=ROLL_DAYS):
    """PRIMARY signal: annualised calendar-spread carry. Unitless. No DV01."""
    sp, f2 = raw_calendar_spread(root)
    dt = D.delivery_gap_years(root).reindex(sp.index)
    c = (sp / f2) / dt

    bad = pd.Series(False, index=c.index)
    if roll_days:
        bad |= D.roll_window_mask(root, roll_days).reindex(c.index, fill_value=False)
    if apply_guard:
        bad |= ctd_guard(root, c.index)
    c = c.mask(bad)

    if apply_winsor:                       # trailing expanding, never full-sample
        lo = c.expanding(min_periods=250).quantile(WINSOR_Q).shift(1)
        hi = c.expanding(min_periods=250).quantile(1 - WINSOR_Q).shift(1)
        c = c.clip(lower=lo, upper=hi)

    return c.ffill().rename(root)          # hold last clean value across masks


def carry_panel(roots=None, **kw):
    roots = roots or D.ROOTS
    return pd.DataFrame({r: carry_kmpv(r, **kw) for r in roots})


# ------------------------- SECONDARY: cash-curve carry & roll ----------------
def carry_curve_root(root, h=0.25, financing="USGG3M"):
    """Carry + roll-down in EXPECTED-YIELD-CHANGE space, then DV01-converted.

    Unlike the primary measure this one DOES use DV01 inside the definition,
    because the roll term is in basis points of yield (CARRY_DESIGN.md 3a).
    Returns expected P&L per contract per horizon h, in dollars.
    """
    Y = D.curve()
    grid = np.array(sorted(D.CURVE))
    tau = D.ROOT_TENOR[root]
    rf = D.series(f"{financing}_Index").reindex(Y.index).ffill()

    y_t = Y.apply(lambda row: np.interp(tau, grid, row.values), axis=1)
    y_roll = Y.apply(lambda row: np.interp(max(tau - h, grid[0]), grid, row.values), axis=1)

    dv = D.dv01(root).reindex(Y.index).ffill()
    exp_carry = (y_t - rf) * h * 100.0 * dv      # financing spread, bp x DV01
    exp_roll = (y_t - y_roll) * 100.0 * dv       # slide down an unchanged curve
    return (exp_carry + exp_roll).rename(root)


def carry_curve_panel(roots=None, **kw):
    roots = roots or D.ROOTS
    return pd.DataFrame({r: carry_curve_root(r, **kw) for r in roots})
