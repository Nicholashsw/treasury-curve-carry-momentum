"""Walk-forward test of curve mean-reversion across policy regimes (see PREREG.md).

Executes the canonical notebook's code cells unchanged (as scripts/make_figures.py
does) and reuses its functions, so the strategy, hedge, vol target and costs are
the published ones. Only the signal direction and the z-score lookback are chosen,
in one regime, and then traded in the next.

Usage:
    BBG_CSV=/path/to/csv/exports python walkforward/walkforward.py
"""
import json
import os
import tempfile
import warnings

warnings.simplefilter("ignore")

import numpy as np
import pandas as pd

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOTEBOOK = os.path.join(REPO_ROOT, "notebooks", "treasury_curve_pipeline.ipynb")
OUT = os.path.join(REPO_ROOT, "walkforward", "results")

# Same windows as cross_country/gr_rv/subperiod.py PERIODS (checked by cross_country/scripts/make_tables.py).
REGIMES = [
    ("R1 post-GFC QE", "2010-01-01", "2014-12-31"),
    ("R2 divergence/NIRP", "2015-01-01", "2019-12-31"),
    ("R3 COVID", "2020-01-01", "2021-12-31"),
    ("R4 hiking/normalisation", "2022-01-01", "2026-12-31"),
]
DIRECTIONS = ("reversion", "momentum")
WINDOWS = (63, 126, 252, 504)
SPREADS = {
    "2s10s": dict(feat="s2s10", long=("TY", "USGG10YR"), short=("TU", "USGG2YR")),
    "5s30s": dict(feat="s5s30", long=("US", "USGG30YR"), short=("FV", "USGG5YR")),
}


def run_notebook():
    """Execute the notebook's code cells and return the resulting namespace."""
    with open(NOTEBOOK, encoding="utf-8") as fh:
        nb = json.load(fh)
    ns = {"__name__": "__main__"}
    cwd = os.getcwd()
    os.environ["BBG_RESULTS"] = tempfile.mkdtemp()     # keep the notebook's own outputs out of the repo
    os.chdir(REPO_ROOT)
    try:
        for cell in nb["cells"]:
            if cell["cell_type"] == "code":
                exec(compile("".join(cell["source"]), "<notebook>", "exec"), ns)
    finally:
        os.chdir(cwd)
    return ns


def candidate(ns, spread, direction, window):
    """Net daily returns of one candidate, built from the notebook's own functions."""
    sp = SPREADS[spread]
    (lr, lt), (sr, st) = sp["long"], sp["short"]
    h = ns["hedge_ratio"](sr, st, lr, lt)
    s = ns["reversion_z"](ns["feat"][sp["feat"]], win=window)
    if direction == "momentum":
        s = -s
    sig = pd.DataFrame({lr: s, sr: -s * h})
    cost = np.mean([ns["tick_frac"](sr), ns["tick_frac"](lr)])
    return ns["run_strategy"](sig, ns["rets"][[lr, sr]], cost_per_unit=cost)["net"]


def window(x, start, end):
    return x.loc[start:end]


def main():
    ns = run_notebook()
    sharpe, dm_test = ns["sharpe"], ns["dm_test"]
    base = ns["curves"]["DurationMomentum"]

    # The published full-sample numbers must reproduce before anything else is trusted.
    # Tolerance as in carry/CARRY_RESULTS.md section 0: under pandas 2.2.2 the 2s10s
    # Sharpe lands at 0.7150, a rounding-boundary case against the published 0.71.
    pub = {"DurationMomentum": 0.68, "2s10s_reversion": 0.71, "5s30s_reversion": 0.66}
    for k, v in pub.items():
        got = sharpe(ns["curves"][k])
        assert abs(got - v) <= 0.006, f"{k}: Sharpe {got:.4f} does not reproduce {v}"
        print(f"reproduced {k}: Sharpe {got:.4f} (published {v})")
    for k, v in {"2s10s_reversion": 0.83, "5s30s_reversion": 0.68}.items():
        got = dm_test(base, ns["curves"][k])[0]
        assert abs(got - v) <= 0.015, f"{k}: DM {got:.4f} does not reproduce {v}"
        print(f"reproduced {k}: DM {got:.4f} (published {v})")

    os.makedirs(OUT, exist_ok=True)
    grid, rows, pooled = [], [], {}
    for spread in SPREADS:
        runs = {(d, w): candidate(ns, spread, d, w) for d in DIRECTIONS for w in WINDOWS}
        reference = runs[("reversion", 252)]
        oos_parts, ref_parts = [], []
        for (fit, f0, f1), (test, t0, t1) in zip(REGIMES[:-1], REGIMES[1:]):
            fit_sh = {k: sharpe(window(r, f0, f1)) for k, r in runs.items()}
            for (d, w), v in fit_sh.items():
                grid.append(dict(spread=spread, fit_regime=fit, direction=d, lookback=w, fit_sharpe=v))
            best = max(fit_sh, key=lambda k: (round(fit_sh[k], 10), k[1]))
            oos = window(runs[best], t0, t1)
            ref = window(reference, t0, t1)
            b = window(base, t0, t1)
            stat, p, edge, lag, n = dm_test(b, oos)
            rows.append(dict(spread=spread, fit_regime=fit, test_regime=test,
                             direction=best[0], lookback=best[1],
                             fit_sharpe=fit_sh[best], oos_sharpe=sharpe(oos),
                             duration_mom_sharpe=sharpe(b), dm_stat=stat, dm_p=p,
                             dm_ann_edge=edge, n_days=n,
                             reference_rev252_oos_sharpe=sharpe(ref)))
            oos_parts.append(oos); ref_parts.append(ref)
        oos_all, ref_all = pd.concat(oos_parts), pd.concat(ref_parts)
        b_all = base.reindex(oos_all.index)
        stat, p, edge, lag, n = dm_test(b_all, oos_all)
        pooled[spread] = dict(spread=spread, test_window="2015-2026 pooled",
                              oos_sharpe=sharpe(oos_all), duration_mom_sharpe=sharpe(b_all),
                              dm_stat=stat, dm_p=p, dm_ann_edge=edge, n_days=n,
                              positive_regimes=int(sum(sharpe(x) > 0 for x in oos_parts)),
                              reference_rev252_oos_sharpe=sharpe(ref_all))
        pooled[spread]["supported"] = bool(pooled[spread]["oos_sharpe"] > 0
                                           and pooled[spread]["positive_regimes"] >= 2)

    per = pd.DataFrame(rows)
    tot = pd.DataFrame(pooled.values())
    pd.DataFrame(grid).round(4).to_csv(os.path.join(OUT, "fit_grid.csv"), index=False)
    per.round(4).to_csv(os.path.join(OUT, "walkforward_by_transition.csv"), index=False)
    tot.round(4).to_csv(os.path.join(OUT, "walkforward_pooled.csv"), index=False)
    pd.set_option("display.width", 220)
    print(per.round(3).to_string(index=False))
    print()
    print(tot.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
