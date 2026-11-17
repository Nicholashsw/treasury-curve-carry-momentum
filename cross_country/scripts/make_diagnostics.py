"""Diagnostics quoted in FINDINGS.md, written to results/diagnostics_summary.csv.

Same cache and code path as make_tables.py: panel size, zero-change days, stability of the
US2s10s/CA2s10s pair, Canada's share of the survivors, half-life ranges, and the sensitivity of
the out-of-regime test and of the in-regime backtest to the z-score window.

Usage (from this folder):
    python scripts/make_diagnostics.py
"""
import os
import sys
import warnings

warnings.simplefilter("ignore")

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
os.environ.setdefault("GRRV_CACHE", os.path.join(HERE, "gr_rv", "data"))

import pandas as pd

from gr_rv import data_mvp as D, strategy_mvp as S, subperiod as SP
from make_figures import PAIRS

OUT = os.path.join(HERE, "results", "diagnostics_summary.csv")
PAIR = "US2s10s_vs_CA2s10s"


def main():
    panel = D.load_all(start="2010-01-01")["yields"]
    uni = S.candidate_universe(markets=("US", "DE", "JP", "CA"))
    by = {c["name"]: c for c in uni}
    grid = SP.subperiod_screen(panel, uni)
    rows = []

    def add(name, field, value):
        rows.append((name, field, float(value)))

    add("panel", "rows", len(panel))
    add("panel", "series", panel.shape[1])
    for col in ("JP_2Y", "US_2Y"):
        add("zero_change_days", col, (panel[col].diff() == 0).sum())

    st = SP.stability_report(grid).loc[PAIR]
    for f in ("periods_passed", "periods_passed_fdr", "beta_range"):
        add(PAIR, f, st[f])

    surv, fdr = grid[grid["passes"]], grid[grid["passes_fdr"]]
    add("survivors", "raw", len(surv))
    add("survivors", "raw_with_canada", surv["name"].str.contains("CA").sum())
    add("survivors", "fdr", len(fdr))
    add("survivors", "fdr_with_canada", fdr["name"].str.contains("CA").sum())
    add("fdr_survivors", "half_life_min", fdr["half_life"].min())
    add("fdr_survivors", "half_life_max", fdr["half_life"].max())

    seq = list(SP.PERIODS)
    for w in (252, 126, 63):
        oos = [r["oos_sharpe"] for nm in PAIRS for i in range(len(seq) - 1)
               if (r := SP.forward_test_survivor(panel, by[nm], seq[i], seq[i + 1], window=w))]
        add(f"oos_window_{w}", "mean_sharpe", pd.Series(oos).mean())
        add(f"oos_window_{w}", "positive", (pd.Series(oos) > 0).sum())
        add(f"oos_window_{w}", "tests", len(oos))

    c = by[PAIR]
    row = grid[(grid["name"] == PAIR) & grid["period"].str.startswith("2022")].iloc[0]
    a, b = SP.PERIODS[row["period"]]
    sub = panel.loc[a:b]
    add("in_regime_2022_2026", "days", len(sub))
    for w in (252, 126, 63):
        res = S.run_candidate(sub, c, row["beta"], window=w)
        from ratslib import metrics
        add(f"in_regime_window_{w}", "sharpe", metrics.sharpe(res["net"].dropna()))
        add(f"in_regime_window_{w}", "trades", res.attrs.get("n_trades"))
        if w == 252:
            add("in_regime_window_252", "days_in_position", (res["state"] != 0).sum())
            add("in_regime_window_252", "warmup_days", 252 + 126)

    pd.DataFrame(rows, columns=["name", "field", "value"]).round(6).to_csv(OUT, index=False)
    print(pd.DataFrame(rows).to_string())


if __name__ == "__main__":
    main()
