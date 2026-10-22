"""Result tables for the cross-country relative-value study.

Writes the numbers behind FINDINGS.md and the README section as CSVs in
``results/``, from the same committed cache and the same code path as
``make_figures.py``:

    full_sample_screen.csv   cointegration screen, 2010-2026 (18 candidates)
    regime_screen.csv        the same screen inside each policy regime (144 tests)
    in_regime_survivors.csv  every in-regime pass backtested inside its own regime
    out_of_regime.csv        fit beta in one regime, trade it in the next (12 tests)
    fx_contamination.csv     R-squared of each in-regime survivor's net return on its FX pair

Usage (from this folder):
    python scripts/make_tables.py
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

from gr_rv import data_mvp as D, strategy_mvp as S, subperiod as SP, fx_layer as F
from make_figures import FWD_WINDOW, PAIRS
from walkforward.walkforward import REGIMES

OUT = os.environ.get("GRRV_TABLES", os.path.join(HERE, "results"))


def main():
    # One set of policy regimes for the whole repository: the curve walk-forward
    # (walkforward/PREREG.md) and this study must use identical windows.
    assert [w for w in SP.PERIODS.values()] == [(a, b) for _, a, b in REGIMES], \
        "cross_country regimes differ from walkforward/walkforward.py"

    os.makedirs(OUT, exist_ok=True)
    bundle = D.load_all(start="2010-01-01")
    panel, fx = bundle["yields"], bundle["fx"]
    uni = S.candidate_universe(markets=("US", "DE", "JP", "CA"))
    by = {c["name"]: c for c in uni}

    full = S.screen(panel, S.candidate_universe())
    grid = SP.subperiod_screen(panel, uni)
    surv = SP.backtest_subperiod_survivors(panel, grid, uni)

    seq = list(SP.PERIODS)
    fwd = pd.DataFrame([r for nm in PAIRS for i in range(len(seq) - 1)
                        if (r := SP.forward_test_survivor(panel, by[nm], seq[i], seq[i + 1],
                                                          window=FWD_WINDOW))])

    fx_rows = []
    for _, r in grid[grid["passes"]].iterrows():
        a, b = SP.PERIODS[r["period"]]
        c = by[r["name"]]
        res = S.run_candidate(panel.loc[a:b], c, r["beta"])
        fx_rows.append({"name": r["name"], "period": r["period"],
                        **F.fx_contamination(res["net"], fx, c["a"], c["b"])})
    fxc = pd.DataFrame(fx_rows)

    for name, df in [("full_sample_screen", full), ("regime_screen", grid),
                     ("in_regime_survivors", surv), ("out_of_regime", fwd),
                     ("fx_contamination", fxc)]:
        df.round(6).to_csv(os.path.join(OUT, f"{name}.csv"), index=False)
        print("saved", f"{name}.csv")

    print(f"\nfull sample: {int(full['passes'].sum())} of {len(full)} cointegrated")
    print(f"regime grid: {int(grid['passes'].sum())} of {len(grid)} pass, "
          f"{int(grid['passes_fdr'].sum())} survive FDR")
    print(f"out-of-regime: mean Sharpe {fwd['oos_sharpe'].mean():.2f}, "
          f"positive {int((fwd['oos_sharpe'] > 0).sum())} of {len(fwd)}")
    print(f"FX R-squared: max {fxc['r2'].max():.4f} over {fxc['r2'].notna().sum()} survivors")


if __name__ == "__main__":
    main()
