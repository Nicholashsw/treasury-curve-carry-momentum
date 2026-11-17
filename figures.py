"""Hero chart: 2s10s mean reversion vs momentum on 2s10s, cumulative net return.

Daily returns come from the licensed Bloomberg export and are computed at plot time by the
repo pipeline (scripts/make_figures.py); only the PNG is written. Set BBG_CSV to the export folder.
"""
import os
import sys
import tempfile
from pathlib import Path
import numpy as np
import pandas as pd
# --- shared chart style (identical in every repo's figures.py) ---------------------------
# Palette: first three categorical slots of the validated reference palette (pass all-pairs
# CVD checks in light mode). Ink and grid are text tokens, never series colours.
import matplotlib as mpl
import matplotlib.pyplot as plt

SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"

mpl.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 10,
    "axes.titlesize": 11, "axes.titleweight": "regular", "axes.titlelocation": "left",
    "axes.labelsize": 9.5, "axes.labelcolor": INK2, "axes.edgecolor": INK2, "axes.linewidth": 0.6,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "axes.grid.axis": "y", "grid.color": GRID, "grid.linewidth": 0.6,
    "axes.facecolor": SURFACE, "figure.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "xtick.color": INK2, "ytick.color": INK2, "xtick.labelsize": 9, "ytick.labelsize": 9,
    "xtick.major.size": 0, "ytick.major.size": 0, "lines.linewidth": 2,
    "legend.frameon": False, "figure.dpi": 100, "savefig.dpi": 200,
})
FIGSIZE = (7.2, 4.0)   # one hero size for all six projects


def finish(fig, ax, title, subtitle, path):
    """Title (what the chart says) and subtitle (what is plotted, from which file), then save."""
    ax.set_title(title, color=INK, pad=22)
    ax.text(0, 1.02, subtitle, transform=ax.transAxes, color=INK2, fontsize=8.5, va="bottom")
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
# -------------------------------------------------------------------------------------------

ROOT = Path(__file__).parent


def hero():
    # Reuse scripts/make_figures.py (notebook runner); keep this file's style, and keep its
    # side outputs out of the repo.
    saved = dict(mpl.rcParams)
    os.environ.setdefault("BBG_RESULTS", tempfile.mkdtemp())
    sys.path.insert(0, str(ROOT / "scripts"))
    import make_figures as mf
    ns = mf.run_notebook()
    mpl.rcParams.update(saved)

    feat, rets = ns["feat"], ns["rets"]
    h = ns["hedge_ratio"]("TU", "USGG2YR", "TY", "USGG10YR")
    c2 = float(np.mean([ns["tick_frac"]("TU"), ns["tick_frac"]("TY")]))
    mom = np.sign(feat["s2s10"].diff(63))
    mom_net = ns["run_strategy"](pd.DataFrame({"TY": mom, "TU": -mom * h}), rets[["TY", "TU"]],
                                 cost_per_unit=c2)["net"]
    rev_net = ns["curves"]["2s10s_reversion"]
    sharpe = ns["sharpe"]

    hm = pd.read_csv(ROOT / "results" / "headline_metrics.csv").query("field == 'sharpe'").set_index("name").value
    for s, name in ((rev_net, "2s10s_reversion"), (mom_net, "2s10s_momentum_signal")):
        assert abs(sharpe(s) - hm[name]) < 0.01, (name, sharpe(s), hm[name])

    fig, ax = plt.subplots(figsize=FIGSIZE)
    ax.set_axisbelow(True)
    end = {}
    for s, col, name in ((rev_net, BLUE, "Mean reversion"), (mom_net, ORANGE, "Momentum")):
        eq = (1 + pd.Series(s).fillna(0)).cumprod()
        ax.plot(eq.index, eq.values, color=col, lw=1.6)
        end[name] = (eq.index[-1], eq.iloc[-1], col, f"{name}\nSharpe {sharpe(s):+.2f}")
    for name, (x, y, col, txt) in end.items():
        ax.annotate(txt, (x, y), xytext=(6, 0), textcoords="offset points", va="center", color=INK, fontsize=9)
    ax.axhline(1, color=INK2, lw=0.6)
    ax.set_yscale("log")
    ax.set_ylim(0.06, 6)
    ax.set_yticks([0.1, 0.25, 0.5, 1, 2, 4], ["0.1x", "0.25x", "0.5x", "1x", "2x", "4x"])
    ax.minorticks_off()
    ax.set_ylabel("Cumulative net return (log scale)")
    ax.margins(x=0.01)
    fig.subplots_adjust(right=0.8)
    finish(fig, ax, "The same 2s10s book earns money on mean reversion and loses on momentum",
           "DV01-neutral 2s10s, net of tick costs; Sharpe checked against headline_metrics.csv",
           ROOT / "figures" / "hero.png")


if __name__ == "__main__":
    hero()
