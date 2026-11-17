"""Aggregate headline results, generated FROM the canonical notebook.

Writes results/headline_metrics.csv (one row per quantity; aggregates only, no
price or return series). Executes the notebook's code cells like make_figures.py.

Usage:
    BBG_CSV=/path/to/csv/exports BBG_RESULTS=/scratch/dir python scripts/make_results.py
BBG_RESULTS receives the notebook's own outputs; the CSV goes to results/.
"""
import json
import os
import warnings

warnings.simplefilter("ignore")
import numpy as np
import pandas as pd

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOTEBOOK = os.path.join(REPO_ROOT, "notebooks", "treasury_curve_pipeline.ipynb")
OUT = os.path.join(REPO_ROOT, "results", "headline_metrics.csv")


def run_notebook():
    with open(NOTEBOOK, encoding="utf-8") as fh:
        nb = json.load(fh)
    ns = {"__name__": "__main__"}
    cwd = os.getcwd()
    os.chdir(REPO_ROOT)
    try:
        for cell in nb["cells"]:
            if cell["cell_type"] == "code":
                exec(compile("".join(cell["source"]), "<notebook>", "exec"), ns)
    finally:
        os.chdir(cwd)
    return ns


def books(ns):
    """Run the four books and the 2s10s momentum-signal book with the notebook's own functions.
    Returns {name: (run_strategy result, cost_per_unit)}."""
    run_strategy, hedge_ratio, tick_frac = ns["run_strategy"], ns["hedge_ratio"], ns["tick_frac"]
    feat, rets, reversion_z = ns["feat"], ns["rets"], ns["reversion_z"]
    avg = lambda roots: float(np.mean([tick_frac(r) for r in roots]))
    out = {}

    def add(name, sig, cols, roots):
        c = avg(roots)
        out[name] = (run_strategy(sig, rets[cols], cost_per_unit=c), c)

    c = avg(rets.columns)
    out["DurationMomentum"] = (run_strategy(np.sign(rets.rolling(63).sum()), rets, cost_per_unit=c), c)
    h = hedge_ratio("TU", "USGG2YR", "TY", "USGG10YR"); s = reversion_z(feat["s2s10"])
    add("2s10s_reversion", pd.DataFrame({"TY": s, "TU": -s * h}), ["TY", "TU"], ["TU", "TY"])
    m = np.sign(feat["s2s10"].diff(63))
    add("2s10s_momentum_signal", pd.DataFrame({"TY": m, "TU": -m * h}), ["TY", "TU"], ["TU", "TY"])
    h = hedge_ratio("FV", "USGG5YR", "US", "USGG30YR"); s = reversion_z(feat["s5s30"])
    add("5s30s_reversion", pd.DataFrame({"US": s, "FV": -s * h}), ["US", "FV"], ["FV", "US"])
    hb = hedge_ratio("FV", "USGG5YR", "TY", "USGG10YR"); ha = hedge_ratio("FV", "USGG5YR", "TU", "USGG2YR")
    s = reversion_z(feat["fly2510"])
    add("2s5s10s_fly", pd.DataFrame({"FV": 2 * s, "TU": -s * ha, "TY": -s * hb}),
        ["FV", "TU", "TY"], ["FV", "TU", "TY"])
    return out


def main():
    ns = run_notebook()
    sharpe, maxdd, ann_vol, dm_test = ns["sharpe"], ns["maxdd"], ns["ann_vol"], ns["dm_test"]
    yields, reg, curves = ns["yields"], ns["reg"], ns["curves"]
    B = books(ns)
    rows = []

    def add(name, field, value):
        rows.append((name, field, float(value)))

    for k, (res, c) in B.items():
        net, gross = res["net"], res["gross"]
        add(k, "sharpe", sharpe(net))
        add(k, "sharpe_gross", sharpe(gross))
        add(k, "cost_per_unit", c)
        if k == "2s10s_momentum_signal":
            continue
        add(k, "vol", ann_vol(net))
        add(k, "maxdd_pct", 100 * maxdd(net))
        add(k, "maxdd_pct_gross", 100 * maxdd(gross))
        add(k, "turnover_per_yr", res["turnover"].sum() / (len(net) / 252))
        if k != "DurationMomentum":
            for tag, base, alt in (("", B["DurationMomentum"][0]["net"], net),
                                   ("_gross", B["DurationMomentum"][0]["gross"], gross)):
                s, p, edge, lag, n = dm_test(base, alt)
                add(k, "dm" + tag, s)
                add(k, "dm_p" + tag, p)
                add(k, "dm_edge_pct" + tag, 100 * edge)
        # the books must equal the notebook's own curves
        if k in curves:
            assert np.allclose(curves[k].fillna(0), net.fillna(0)), k

    # duration beta of the 2s10s reversion book: daily net return on daily 10Y yield change (percentage points)
    d = pd.concat([B["2s10s_reversion"][0]["net"], yields["USGG10YR"].diff()], axis=1).dropna()
    add("2s10s_reversion", "beta_to_10y_yield_chg", np.polyfit(d.iloc[:, 1], d.iloc[:, 0], 1)[0])

    add("sample", "n_rows", len(ns["calendar"]))
    for state, n in reg["regime"].value_counts().items():
        add("regime_days", state, n)

    df = pd.DataFrame(rows, columns=["name", "field", "value"])
    df["value"] = df["value"].round(6)
    df.to_csv(OUT, index=False)
    print(df.to_string())


if __name__ == "__main__":
    main()
