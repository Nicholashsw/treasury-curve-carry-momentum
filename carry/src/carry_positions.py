"""STAGE (3) of the pipeline: signal -> DV01-normalised positions.

DV01 enters HERE and nowhere in the primary signal (CARRY_DESIGN.md 3a).
Weights follow the canonical convention: w_i proportional to 1/DV01_i, which is
exactly what hedge_ratio() implements for the two-leg curve books.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np, pandas as pd
import carry_data as D


def dv01_frame(index, roots):
    return pd.DataFrame({r: D.dv01(r).reindex(index).ffill() for r in roots})


def ts_positions(carry, index, roots):
    """A1 time-series: long positive carry, short negative, DV01-equalised."""
    sig = np.sign(carry[roots].reindex(index).ffill())
    dv = dv01_frame(index, roots)
    w = sig / dv
    return w.div(w.abs().sum(axis=1).replace(0, np.nan), axis=0).fillna(0.0)


def xs_positions(carry, index, roots, n_side=2):
    """A2 cross-sectional: long top-n carry, short bottom-n.

    DV01-NEUTRAL as specified in CARRY_RESEARCH_PLAN.md experiment A: each side
    is normalised to equal gross DV01 exposure, so the book carries no net
    duration. Normalising gross *weight* instead (an earlier bug) leaves the
    book structurally long duration, because high-carry roots are the
    long-duration ones.
    """
    C = carry[roots].reindex(index).ffill()
    dv = dv01_frame(index, roots)
    rank = C.rank(axis=1, ascending=False, method="first")
    valid = C.notna().sum(axis=1)
    longs = rank.le(n_side) & C.notna()
    shorts = rank.gt(valid.values[:, None] - n_side) & C.notna()

    w = (longs.astype(float) - shorts.astype(float)) / dv      # 1/DV01 sizing
    pos, neg = w.clip(lower=0), w.clip(upper=0)
    # scale each side to unit gross DV01  ->  net DV01 == 0
    pos_dv = (pos * dv).sum(axis=1).replace(0, np.nan)
    neg_dv = (neg * dv).abs().sum(axis=1).replace(0, np.nan)
    return (pos.div(pos_dv, axis=0).fillna(0) + neg.div(neg_dv, axis=0).fillna(0))
