"""Publication figures, generated FROM the canonical notebook.

The script executes the code cells of ``notebooks/treasury_curve_pipeline.ipynb``
and then draws from that namespace, so the figures and the results table in
README.md / the paper are guaranteed to share one pipeline and one cost model.
There is no second copy of the strategy logic here.

Costs come from the notebook's ``tick_frac()`` helper -- one tick per contract
per side, using each contract's own tick size from the ``*_STATIC`` export.

Usage:
    BBG_CSV=/path/to/csv/exports BBG_RESULTS=./results \
        python scripts/make_figures.py

Both variables default the same way the notebook does: ``data_raw/`` and
``results/`` at the repository root.
"""
import json
import os
import warnings

warnings.simplefilter("ignore")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOTEBOOK = os.path.join(REPO_ROOT, "notebooks", "treasury_curve_pipeline.ipynb")
OUT = os.environ.get("BBG_RESULTS", os.path.join(REPO_ROOT, "results"))
os.makedirs(OUT, exist_ok=True)


def run_notebook():
    """Execute the notebook's code cells and return the resulting namespace."""
    with open(NOTEBOOK, encoding="utf-8") as fh:
        nb = json.load(fh)
    ns = {"__name__": "__main__"}
    cwd = os.getcwd()
    os.chdir(REPO_ROOT)                      # so the notebook's repo-relative defaults resolve
    try:
        for cell in nb["cells"]:
            if cell["cell_type"] == "code":
                exec(compile("".join(cell["source"]), "<notebook>", "exec"), ns)
    finally:
        os.chdir(cwd)
    return ns


plt.rcParams.update({
    "figure.dpi": 200, "savefig.dpi": 200, "font.size": 11,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.alpha": 0.25, "grid.linewidth": 0.6,
    "axes.titlesize": 13, "axes.titleweight": "bold",
    "legend.frameon": False, "figure.autolayout": True})

RED, GRN, BLU, ORG, GRY = "#c0392b", "#1e8449", "#1f5f8b", "#d97706", "#8a8a99"

LABEL = {"DurationMomentum": "Duration momentum",
         "2s10s_reversion": "2s10s reversion",
         "5s30s_reversion": "5s30s reversion",
         "2s5s10s_fly": "2s5s10s butterfly"}


def eq(s):
    return (1 + pd.Series(s).fillna(0)).cumprod()


def save(fig, name):
    fig.savefig(os.path.join(OUT, name), bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("saved", name)


def main():
    ns = run_notebook()
    curves = ns["curves"]
    feat, rets = ns["feat"], ns["rets"]
    run_strategy, hedge_ratio = ns["run_strategy"], ns["hedge_ratio"]
    tick_frac, sharpe, maxdd = ns["tick_frac"], ns["sharpe"], ns["maxdd"]

    # --- FIG 1: the headline contrast, same book, opposite signals ---------
    h = hedge_ratio("TU", "USGG2YR", "TY", "USGG10YR")
    c2 = float(np.mean([tick_frac("TU"), tick_frac("TY")]))
    mom = np.sign(feat["s2s10"].diff(63))
    mom_net = run_strategy(pd.DataFrame({"TY": mom, "TU": -mom * h}),
                           rets[["TY", "TU"]], cost_per_unit=c2)["net"]
    rev_net = curves["2s10s_reversion"]

    fig, ax = plt.subplots(figsize=(9, 4.6))
    ax.plot(eq(mom_net), color=RED, lw=2,
            label=f"Momentum signal   (Sharpe {sharpe(mom_net):+.2f})")
    ax.plot(eq(rev_net), color=GRN, lw=2,
            label=f"Mean-reversion signal   (Sharpe {sharpe(rev_net):+.2f})")
    ax.axhline(1, color=GRY, lw=.8)
    ax.set_title("Same DV01-neutral 2s10s book, opposite signals")
    ax.set_ylabel("Cumulative net return (×)")
    ax.legend(loc="upper left")
    ax.text(.015, .06,
            "Book is duration-neutral (β to 10Y yield ≈ 0).\n"
            "The gap is signal, not hedge error.",
            transform=ax.transAxes, fontsize=9, color=GRY, va="bottom")
    save(fig, "fig1_signal_contrast.png")

    # --- FIG 2: all four equity curves ------------------------------------
    fig, ax = plt.subplots(figsize=(9, 4.6))
    for (k, s), c in zip(curves.items(), [BLU, GRN, ORG, RED]):
        ax.plot(eq(s), color=c, lw=1.9, label=f"{LABEL.get(k, k)}  ({sharpe(s):.2f})")
    ax.axhline(1, color=GRY, lw=.8)
    ax.set_title("Net cumulative performance, 2010–2026")
    ax.set_ylabel("Cumulative net return (×)")
    ax.legend(loc="upper left")
    save(fig, "fig2_equity_curves.png")

    # --- FIG 3: risk / return bars ----------------------------------------
    nm = [LABEL.get(k, k) for k in curves]
    sh = [sharpe(v) for v in curves.values()]
    dd = [100 * maxdd(v) for v in curves.values()]
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    cols = [BLU, GRN, ORG, RED]
    axes[0].barh(nm[::-1], sh[::-1], color=cols[::-1])
    axes[0].set_title("Net Sharpe")
    axes[0].axvline(0, color=GRY, lw=.8)
    axes[1].barh(nm[::-1], dd[::-1], color=cols[::-1])
    axes[1].set_title("Max drawdown (%)")
    for a in axes:
        a.grid(axis="y", alpha=0)
    save(fig, "fig3_risk_return.png")

    print("\nNUMBERS FOR README / PAPER (net of tick costs):")
    for k, v in curves.items():
        print(f"  {LABEL.get(k, k):22s} sharpe={sharpe(v):.2f}  maxDD={100*maxdd(v):.0f}%")
    print(f"  momentum-on-2s10s      sharpe={sharpe(mom_net):.2f}")
    print(f"  cost_per_unit (2s10s)  {c2:.6f}")


if __name__ == "__main__":
    main()
