"""Every result number printed in the docs and the paper must match a committed results file.

Reads only committed files. Each claim is (location, value found in the text, source file, field,
expected). The text value is located with a regex, so a sentence that is reworded away from the
pattern fails loudly instead of being dropped. A claim passes when |value - expected| is within
half a unit of the last printed digit. Run `python tests/test_claims.py` for the plain table.

Out of scope: dates, ticker lists, commit times and the pre-registered bars in the plan.
"""
import re
from functools import lru_cache
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
WORDS = {"six": 6, "three": 3}


@lru_cache(None)
def csv(rel):
    return pd.read_csv(ROOT / rel)


@lru_cache(None)
def text(rel):
    t = (ROOT / rel).read_text(encoding="utf-8")
    if rel.endswith(".tex"):
        t = re.sub(r"\\mathrm\{(\w+)\}", r"\1", t)
        t = t.replace("{,}", ",").replace("\\%", "%").replace("$", "").replace("--", "-")
    t = re.sub(r"```.*?```", " CODEBLOCK ", t, flags=re.S)
    t = re.sub(r"\\begin\{thebibliography\}.*?\\end\{thebibliography\}", " ", t, flags=re.S)
    t = re.sub(r"\\(?:cite|ref|label|includegraphics|graphicspath|bibitem|usepackage|documentclass)(?:\[[^\]]*\])?\{[^}]*\}(?:\{[^}]*\})?", " ", t)
    t = re.sub(r"https?://\S+|\]\([^)]*\)", " ", t)
    t = t.replace("\u2212", "-").replace("**", "").replace("`", "").replace("~", "")
    return re.sub(r"\s+", " ", t)


def num(s):
    s = s.replace(",", "").replace("+", "")
    return float(WORDS[s]) if s in WORDS else float(s)


def decimals(s):
    return len(s.split(".")[1]) if "." in s else 0


class Claim:
    def __init__(self, loc, doc, pattern, group, source, field, expected):
        self.loc, self.doc, self.pattern, self.group = loc, doc, pattern, group
        self.source, self.field, self._exp = source, field, expected

    every = False
    lt = False          # "below X": the printed bound must be >= the actual value

    def matches(self):
        ms = list(re.finditer(self.pattern, text(self.doc))) if self.every else \
            [m for m in [re.search(self.pattern, text(self.doc))] if m]
        assert ms, f"pattern not found in {self.doc}: {self.pattern}"
        return [(m.group(self.group), m.span(self.group)) for m in ms]

    def value(self):
        return self.matches()[0][0]

    def expected(self):
        return float(self._exp() if callable(self._exp) else self._exp)

    def check(self):
        e = self.expected()
        if self.lt:
            return all(num(s) >= e for s, _ in self.matches())
        return all(abs(num(s) - e) <= 0.5 * 10 ** -decimals(s) + 1e-9 for s, _ in self.matches())


CLAIMS = []


def row(loc, doc, pattern, specs, every=False):
    """One regex, several captured numbers; specs[i] = (source, field, expected) for group i+1."""
    for i, (src, fld, exp) in enumerate(specs, 1):
        if src is not None:
            c = Claim(f"{doc} {loc} #{i}", doc, pattern, i, src, fld, exp)
            c.every = every
            CLAIMS.append(c)


PAPER = "paper/treasury_curve_paper.tex"
HM = "results/headline_metrics.csv"


def hm(name, field):
    d = csv(HM)
    return lambda: d[(d["name"] == name) & (d["field"] == field)]["value"].iloc[0]


def hmx(src_name, field):
    return (HM, f"{src_name}.{field}", hm(src_name, field))


def col(rel, key, keyval, field):
    return lambda: csv(rel).loc[csv(rel)[key] == keyval, field].iloc[0]


def cell(rel, key, keyval, field):
    return (rel, f"{keyval}.{field}", col(rel, key, keyval, field))


def ex(book, field, scale=1):
    return ("carry/results/experiments_A_to_G.csv", f"{book}.{field}",
            lambda: scale * col("carry/results/experiments_A_to_G.csv", "book", book, field)())


BOOKS = ["DurationMomentum", "2s10s_reversion", "5s30s_reversion", "2s5s10s_fly"]
WF_T, WF_P = "walkforward/results/walkforward_by_transition.csv", "walkforward/results/walkforward_pooled.csv"


def wf(spread, i, field):
    return (WF_T, f"{spread}[{i}].{field}",
            lambda: csv(WF_T).query(f"spread == '{spread}'").iloc[i][field])


def wfp(spread, field):
    return (WF_P, f"{spread}.{field}", lambda: csv(WF_P).query(f"spread == '{spread}'").iloc[0][field])


FROZEN = "carry/CARRY_RESULTS.md"


def frozen(book_label, ):
    """Frozen (August) value of a book, parsed from the table in CARRY_RESULTS.md section 0."""
    def f():
        m = re.search(re.escape(book_label) + r" \| [\d.]+ \| ([\d.]+) \|", text(FROZEN))
        return float(m.group(1))
    return (FROZEN, f"frozen[{book_label}]", f)


def frozen_dm(i):
    def f():
        m = re.search(r"against frozen ([\d./-]+)\.", text(FROZEN))
        return float(m.group(1).split("/")[i])
    return (FROZEN, f"frozen DM[{i}]", f)


# ---------------------------------------------------------------- README
R = "README.md"
row("signal table", R, r"\| Momentum \| (-[\d.]+) \| \| Mean-reversion \| \+?([\d.]+) \|",
    [hmx("2s10s_momentum_signal", "sharpe"), hmx("2s10s_reversion", "sharpe")])
row("duration beta", R, r"slope of about (-[\d.]+)", [hmx("2s10s_reversion", "beta_to_10y_yield_chg")])
for b, lab in zip(BOOKS, ["Duration momentum \\(baseline\\)", "2s10s mean-reversion",
                          "5s30s mean-reversion", "2s5s10s butterfly"]):
    row(f"results table {b}", R, lab + r" \| (-?[\d.]+) \| (-\d+)% \| (\d+) \| (?!\d)",
        [hmx(b, "sharpe"), (HM, f"{b}.maxdd_pct", hm(b, "maxdd_pct")), hmx(b, "turnover_per_yr")])
row("vol range", R, r"volatility of the net returns runs from ([\d.]+)% to ([\d.]+)%",
    [(HM, "min vol*100", lambda: 100 * csv(HM).query("field == 'vol'")["value"].min()),
     (HM, "max vol*100", lambda: 100 * csv(HM).query("field == 'vol'")["value"].max())])
row("walk-forward fits", R, r"chosen in all (\w+) fits",
    [(WF_T, "count(direction == reversion)", lambda: (csv(WF_T)["direction"] == "reversion").sum())])
row("walk-forward positive regimes", R, r"positive in all (\w+) test regimes",
    [(WF_P, "min(positive_regimes)", lambda: csv(WF_P)["positive_regimes"].min())])
row("walk-forward Sharpes", R,
    r"2s10s net Sharpe ([\d.]+) / ([\d.]+) / ([\d.]+), pooled ([\d.]+) over 2015-2026; "
    r"5s30s ([\d.]+) / ([\d.]+) / ([\d.]+), pooled ([\d.]+)\.",
    [wf("2s10s", 0, "oos_sharpe"), wf("2s10s", 1, "oos_sharpe"), wf("2s10s", 2, "oos_sharpe"),
     wfp("2s10s", "oos_sharpe"),
     wf("5s30s", 0, "oos_sharpe"), wf("5s30s", 1, "oos_sharpe"), wf("5s30s", 2, "oos_sharpe"),
     wfp("5s30s", "oos_sharpe")])
row("DM vs baseline", R, r"DM = ([\d.]+) \(p = ([\d.]+)\) for 2s10s and ([\d.]+) \(p = ([\d.]+)\) for 5s30s",
    [hmx("2s10s_reversion", "dm"), hmx("2s10s_reversion", "dm_p"),
     hmx("5s30s_reversion", "dm"), hmx("5s30s_reversion", "dm_p")])
row("walk-forward DM", R,
    r"duration momentum earns ([\d.]+) on the same dates.*?\(2s10s DM ([\d.]+), p ([\d.]+); "
    r"5s30s DM ([\d.]+), p ([\d.]+)\)",
    [wfp("2s10s", "duration_mom_sharpe"), wfp("2s10s", "dm_stat"), wfp("2s10s", "dm_p"),
     wfp("5s30s", "dm_stat"), wfp("5s30s", "dm_p")])
row("carry table", R, r"(0\.021), NW-t (0\.09) \| fails \| \| Spanning alpha.*? \| (-0\.20)%/yr, t (-0\.66) \| fails"
    r".*?(0\.871) . (0\.714), drawdown (-15\.1)% . (-21\.1)%",
    [ex("A2_carry_xs", "sharpe"), ex("A2_carry_xs", "nw_t"),
     ("carry/results/diagnostics_summary.csv", "spanning_carry_kmpv.alpha_pct_per_yr",
      lambda: col("carry/results/diagnostics_summary.csv", "name", "spanning_carry_kmpv", "value")() if False
      else csv("carry/results/diagnostics_summary.csv").query("name == 'spanning_carry_kmpv' and field == 'alpha_pct_per_yr'")["value"].iloc[0]),
     ("carry/results/diagnostics_summary.csv", "spanning_carry_kmpv.t_hac",
      lambda: csv("carry/results/diagnostics_summary.csv").query("name == 'spanning_carry_kmpv' and field == 't_hac'")["value"].iloc[0]),
     ex("G_baseline_2sleeve_mom_2s10s", "sharpe"), ex("G_equal_3sleeve", "sharpe"),
     ex("G_baseline_2sleeve_mom_2s10s", "maxdd"), ex("G_equal_3sleeve", "maxdd")])
row("carry rank corr", R, r"carry and DV01 is \+([\d.]+)",
    [("carry/results/sign_check.csv", "rank_corr_carry_dv01.mean",
      lambda: csv("carry/results/sign_check.csv").query("name == 'rank_corr_carry_dv01' and field == 'mean'")["value"].iloc[0])])
row("carry mean by root", R, r"TU ([\d.]+), FV ([\d.]+), TY ([\d.]+), UXY ([\d.]+), US ([\d.]+), WN ([\d.]+), in percent",
    [("carry/results/us_rule_dispersion.csv", f"cleaned.{r}.mean",
      (lambda r: lambda: csv("carry/results/us_rule_dispersion.csv").query(f"panel == 'cleaned' and root == '{r}'")["mean"].iloc[0])(r))
     for r in ["TU", "FV", "TY", "UXY", "US", "WN"]])
row("neutral carry vol", R, r"its volatility is ([\d.]+)%", [ex("A2_carry_xs", "vol", 100)])
row("cash-curve carry", R, r"does score ([\d.]+), but it holds the same two long-end contracts on (\d+)% of days and "
    r"turns over ([\d.]+) times",
    [ex("A2_carrycurve_xs", "sharpe"),
     ("carry/results/diagnostics_summary.csv", "top2_share US", lambda: csv("carry/results/diagnostics_summary.csv").query("name == 'top2_share_cash_curve_pct' and field == 'US'")["value"].iloc[0]),
     ex("A2_carrycurve_xs", "turnover")])
row("cash-curve carry WN", R, r"contracts on (\d+)% of days",
    [("carry/results/diagnostics_summary.csv", "top2_share WN", lambda: csv("carry/results/diagnostics_summary.csv").query("name == 'top2_share_cash_curve_pct' and field == 'WN'")["value"].iloc[0])])
X = "cross_country/results/"
row("cross-country counts", R, r"(\d+) of (\d+) pairs cointegrated.*?\| (\d+) of (\d+) pass, (\d+) survive FDR \| .*?"
    r"mean Sharpe (-[\d.]+), positive in (\d+) of (\d+) \|",
    [(X + "full_sample_screen.csv", "sum(passes)", lambda: csv(X + "full_sample_screen.csv")["passes"].sum()),
     (X + "full_sample_screen.csv", "len", lambda: len(csv(X + "full_sample_screen.csv"))),
     (X + "regime_screen.csv", "sum(passes)", lambda: csv(X + "regime_screen.csv")["passes"].sum()),
     (X + "regime_screen.csv", "len", lambda: len(csv(X + "regime_screen.csv"))),
     (X + "regime_screen.csv", "sum(passes_fdr)", lambda: csv(X + "regime_screen.csv")["passes_fdr"].sum()),
     (X + "out_of_regime.csv", "mean(oos_sharpe)", lambda: csv(X + "out_of_regime.csv")["oos_sharpe"].mean()),
     (X + "out_of_regime.csv", "sum(oos_sharpe>0)", lambda: (csv(X + "out_of_regime.csv")["oos_sharpe"] > 0).sum()),
     (X + "out_of_regime.csv", "len", lambda: len(csv(X + "out_of_regime.csv")))])
row("FX R2", R, r"R. at most ([\d.]+)\)", [(X + "fx_contamination.csv", "max(r2)", lambda: csv(X + "fx_contamination.csv")["r2"].max())])
row("rounding boundary", R, r"2s10s Sharpe is ([\d.]+) and the butterfly ([\d.]+),",
    [hmx("2s10s_reversion", "sharpe"), hmx("2s5s10s_fly", "sharpe")])
row("August printed values", R, r"printed ([\d.]+) and ([\d.]+)\.",
    [frozen("2s10s reversion"), frozen("2s5s10s butterfly")])
row("cost_per_unit range", R, r"cost_per_unit between ([\d.]+) and ([\d.]+)",
    [(HM, "min cost_per_unit", lambda: csv(HM).query("field == 'cost_per_unit'")["value"].min()),
     (HM, "max cost_per_unit", lambda: csv(HM).query("field == 'cost_per_unit'")["value"].max())])
row("November rerun", R, r"gives ([\d.]+) for the 2s10s mean-reversion and ([\d.]+) for the butterfly.*?"
    r"statistics of ([\d.]+) \(p ([\d.]+)\), ([\d.]+) \(p ([\d.]+)\) and (-[\d.]+) \(p ([\d.]+)\)",
    [hmx("2s10s_reversion", "sharpe"), hmx("2s5s10s_fly", "sharpe"),
     hmx("2s10s_reversion", "dm"), hmx("2s10s_reversion", "dm_p"),
     hmx("5s30s_reversion", "dm"), hmx("5s30s_reversion", "dm_p"),
     hmx("2s5s10s_fly", "dm"), hmx("2s5s10s_fly", "dm_p")])
row("Sharpe gap", R, r"\(a ([\d.]+) Sharpe gap on the identical book, against ([\d.]+) before\)",
    [("results", "net gap = sharpe(2s10s_reversion) - sharpe(2s10s_momentum_signal)",
      lambda: csv(HM).query("name == '2s10s_reversion' and field == 'sharpe'")["value"].iloc[0]
      - csv(HM).query("name == '2s10s_momentum_signal' and field == 'sharpe'")["value"].iloc[0]),
     ("results", "gross gap", lambda: csv(HM).query("name == '2s10s_reversion' and field == 'sharpe_gross'")["value"].iloc[0]
      - csv(HM).query("name == '2s10s_momentum_signal' and field == 'sharpe_gross'")["value"].iloc[0])])
# Correction table, "Originally published (cost-free)" = gross, "Corrected" = the August net run (CARRY_RESULTS frozen)
for b, lab in zip(BOOKS, ["Duration momentum \\(baseline\\)", "2s10s mean-reversion",
                          "5s30s mean-reversion", "2s5s10s butterfly"]):
    row(f"correction table {b}", R, r"\| " + lab + r" \| ([\d.]+) / (-\d+)% \| ([\d.]+) / (-\d+)% \|",
        [hmx(b, "sharpe_gross"), (HM, f"{b}.maxdd_pct_gross", hm(b, "maxdd_pct_gross")),
         frozen({"DurationMomentum": "Duration momentum", "2s10s_reversion": "2s10s reversion",
                 "5s30s_reversion": "5s30s reversion", "2s5s10s_fly": "2s5s10s butterfly"}[b]),
         (HM, f"{b}.maxdd_pct", hm(b, "maxdd_pct"))])
row("correction table momentum signal", R,
    r"\| Same 2s10s book, momentum signal \| (-[\d.]+) \| (-[\d.]+) \|",
    [("results", "2s10s_momentum_signal.sharpe_gross", hm("2s10s_momentum_signal", "sharpe_gross")),
     hmx("2s10s_momentum_signal", "sharpe")])
row("correction table reversion signal", R,
    r"\| Same 2s10s book, mean-reversion signal \| \+([\d.]+) \| \+([\d.]+) \|",
    [("results", "2s10s_reversion.sharpe_gross", hm("2s10s_reversion", "sharpe_gross")),
     frozen("2s10s reversion")])
row("correction table DM 2s10s", R, r"\| DM 2s10s vs baseline \| ([\d.]+) \(p ([\d.]+)\) \| ([\d.]+) \(p ([\d.]+)\) \|",
    [hmx("2s10s_reversion", "dm_gross"), hmx("2s10s_reversion", "dm_p_gross"), frozen_dm(0),
     hmx("2s10s_reversion", "dm_p")],
    )
row("correction table DM 5s30s", R, r"\| DM 5s30s vs baseline \| ([\d.]+) \(p ([\d.]+)\) \| ([\d.]+) \(p ([\d.]+)\) \|",
    [hmx("5s30s_reversion", "dm_gross"), hmx("5s30s_reversion", "dm_p_gross"), frozen_dm(1),
     hmx("5s30s_reversion", "dm_p")])
row("correction table DM butterfly", R, r"\| DM butterfly vs baseline \| (-[\d.]+) \(p ([\d.]+)\) \| (-[\d.]+) \(p ([\d.]+)\) \|",
    [hmx("2s5s10s_fly", "dm_gross"), hmx("2s5s10s_fly", "dm_p_gross"), frozen_dm(2),
     hmx("2s5s10s_fly", "dm_p")])

# ---------------------------------------------------------------- DATA.md
D = "DATA.md"
row("panel rows", D, r"giving a (\d,\d+)-row aligned panel", [hmx("sample", "n_rows")])
row("regime rows", D, r"macro_regime.csv has (\d,\d+) rows", [hmx("sample", "n_rows")])
row("regime counts", D, r"flattening ([\d,]+) rows / steepening ([\d,]+) / stress ([\d,]+)\)",
    [hmx("regime_days", "flattening"), hmx("regime_days", "steepening"), hmx("regime_days", "stress")])

# ---------------------------------------------------------------- walkforward/PREREG.md
P = "walkforward/PREREG.md"
row("README quote at 22 Oct", P, r"2s10s mean-reversion net Sharpe ([\d.]+), 5s30s ([\d.]+)\)",
    [frozen("2s10s reversion"), frozen("5s30s reversion")])
row("candidates per fit", P, r"That is (\d+) candidates per spread per fit",
    [("walkforward/results/fit_grid.csv", "rows per (spread, fit_regime)",
      lambda: csv("walkforward/results/fit_grid.csv").groupby(["spread", "fit_regime"]).size().iloc[0])])
row("reported counts", P, r"(\d+) numbers: 2 spreads x 3 transitions",
    [(WF_T, "len", lambda: len(csv(WF_T)))])

# ---------------------------------------------------------------- carry/CARRY_RESULTS.md
C = FROZEN
for b, lab in [("DurationMomentum", "Duration momentum"), ("2s10s_reversion", "2s10s reversion"),
               ("5s30s_reversion", "5s30s reversion"), ("2s5s10s_fly", "2s5s10s butterfly")]:
    row(f"section 0 {b}", C, lab + r" \| ([\d.]+) \| ", [hmx(b, "sharpe")])
row("section 0 DM", C, r"DM vs baseline: ([\d.-]+) \(p ([\d.]+)\), ([\d.-]+) \(p ([\d.]+)\), ([\d.-]+) \(p ([\d.]+)\)",
    [hmx("2s10s_reversion", "dm"), hmx("2s10s_reversion", "dm_p"), hmx("5s30s_reversion", "dm"),
     hmx("5s30s_reversion", "dm_p"), hmx("2s5s10s_fly", "dm"), hmx("2s5s10s_fly", "dm_p")])
for b, lab in [("A1_carry_ts", r"A1 carry, time-series"), ("A2_carry_xs", r"A2 carry, cross-sectional \(PRIMARY\)"),
               ("A2_carry_xs_noUS", "A2 excluding US"), ("A2_carry_xs_noWN", "A2 excluding WN"),
               ("A2_carrycurve_xs", r"A2 cash-curve variant \(SECONDARY\)")]:
    row(f"3A {b}", C, lab + r" \| (-?[\d.]+) \| ([\d.]+) \| (-[\d.]+)% \| ([\d.]+) \| (-?[\d.]+) \|",
        [ex(b, "sharpe"), ex(b, "vol"), ex(b, "maxdd"), ex(b, "turnover"), ex(b, "nw_t")])
for b, lab in [("G_baseline_2sleeve_mom_2s10s", r"2 sleeves: momentum \+ 2s10s \(baseline\)"),
               ("G_equal_3sleeve", r"3 sleeves: \+ carry, equal weight"),
               ("F_carry25_2s10s75", "F: 25% carry / 75% 2s10s"), ("E_carry25_mom75", "E: 25% carry / 75% momentum")]:
    row(f"E-G {b}", C, lab + r" \| (-?[\d.]+) \| (-[\d.]+)% \|", [ex(b, "sharpe"), ex(b, "maxdd")])
DMT = "carry/results/dm_tests.csv"
for tst, lab in [("B1_mom_gated", "B1 momentum, carry-gated"), ("B2_mom_tilted", "B2 momentum, carry-tilted"),
                 ("C1_2s10s_gated", "C1 2s10s, carry-gated"), ("C2_2s10s_tilt0.25", "C2 2s10s, tilt 0.25"),
                 ("C2_2s10s_tilt0.5", "C2 2s10s, tilt 0.50"), ("C2_2s10s_tilt1.0", "C2 2s10s, tilt 1.00"),
                 ("C1_5s30s_gated", "C1 5s30s, carry-gated"), ("C2_5s30s_tilt0.25", "C2 5s30s, tilt 0.25"),
                 ("D1_fly_carry", "D1 butterfly, carry only"), ("D2_fly_gated", "D2 butterfly, carry-gated")]:
    row(f"B-D {tst}", C, lab + r" \| (-?[\d.]+) \| ([\d.]+) \| ([+-]?[\d.]+) \| ([\d.]+) \|",
        [cell(DMT, "test", tst, "sharpe_alt"), cell(DMT, "test", tst, "sharpe_base"),
         cell(DMT, "test", tst, "dm"), cell(DMT, "test", tst, "p")])
SC = "carry/results/sleeve_correlations.csv"
DG = "carry/results/diagnostics_summary.csv"
row("spanning KMPV", C, r"Carry \(KMPV, primary\) \| (-[\d.]+)%/yr \| (-[\d.]+) \| ([\d.]+) \|",
    [(DG, "spanning_carry_kmpv.alpha", lambda: csv(DG).query("name == 'spanning_carry_kmpv' and field == 'alpha_pct_per_yr'")["value"].iloc[0]),
     (DG, "spanning_carry_kmpv.t_hac", lambda: csv(DG).query("name == 'spanning_carry_kmpv' and field == 't_hac'")["value"].iloc[0]),
     (DG, "spanning_carry_kmpv.r2", lambda: csv(DG).query("name == 'spanning_carry_kmpv' and field == 'r2'")["value"].iloc[0])])
row("spanning cash-curve", C, r"Carry \(cash-curve, secondary\) \| \+([\d.]+)%/yr \| \+([\d.]+) \| ([\d.]+) \|",
    [(DG, "spanning_carry_curve.alpha", lambda: csv(DG).query("name == 'spanning_carry_curve' and field == 'alpha_pct_per_yr'")["value"].iloc[0]),
     (DG, "spanning_carry_curve.t_hac", lambda: csv(DG).query("name == 'spanning_carry_curve' and field == 't_hac'")["value"].iloc[0]),
     (DG, "spanning_carry_curve.r2", lambda: csv(DG).query("name == 'spanning_carry_curve' and field == 'r2'")["value"].iloc[0])])
SG = "carry/results/sign_check.csv"
row("rank corr", C, r"carry rank and DV01 rank is \+([\d.]+), above \+0\.5 on ([\d.]+)% of days",
    [(SG, "rank_corr.mean", lambda: csv(SG).query("name == 'rank_corr_carry_dv01' and field == 'mean'")["value"].iloc[0]),
     (SG, "rank_corr.share", lambda: csv(SG).query("name == 'rank_corr_carry_dv01' and field == 'share_gt_0.5_pct'")["value"].iloc[0])])
row("IC t-stats", C, r"TU \(NW-t (-[\d.]+)\), FV \((-[\d.]+)\), UXY \((-[\d.]+)\) and WN \((-[\d.]+)\)\. Only US is positive and insignificant \(\+([\d.]+)\)",
    [(SG, f"ic_nw_t.{r}", (lambda r: lambda: csv(SG).query(f"name == 'ic_nw_t' and field == '{r}'")["value"].iloc[0])(r))
     for r in ["TU", "FV", "UXY", "WN", "US"]])
row("cash-curve top-2", C, r"US is top-2 on ([\d.]+)% of days and WN on ([\d.]+)%; TY on ([\d.]+)%; UXY on ([\d.]+)%",
    [(DG, f"top2_share.{r}", (lambda r: lambda: csv(DG).query(f"name == 'top2_share_cash_curve_pct' and field == '{r}'")["value"].iloc[0])(r))
     for r in ["US", "WN", "TY", "UXY"]])
row("subperiods", C, r"sign positive in only 2 of 4 subperiods \(\+([\d.]+), \+([\d.]+), (-[\d.]+), (-[\d.]+)\)",
    [("carry/results/regime_stability.csv", f"carry_kmpv[{i}]", (lambda i: lambda: csv("carry/results/regime_stability.csv")["carry_kmpv"].iloc[i])(i))
     for i in range(4)])

# ---------------------------------------------------------------- cross_country/FINDINGS.md
F = "cross_country/FINDINGS.md"
row("summary counts", F, r"0 of 18 candidates cointegrated.*?(\d+) of 144 pass the screen, (\d+) survive FDR.*?"
    r"mean Sharpe of (-[\d.]+), positive in only (\d+) of (\d+) tests",
    [(X + "regime_screen.csv", "sum(passes)", lambda: csv(X + "regime_screen.csv")["passes"].sum()),
     (X + "regime_screen.csv", "sum(passes_fdr)", lambda: csv(X + "regime_screen.csv")["passes_fdr"].sum()),
     (X + "out_of_regime.csv", "mean(oos_sharpe)", lambda: csv(X + "out_of_regime.csv")["oos_sharpe"].mean()),
     (X + "out_of_regime.csv", "sum(oos_sharpe>0)", lambda: (csv(X + "out_of_regime.csv")["oos_sharpe"] > 0).sum()),
     (X + "out_of_regime.csv", "len", lambda: len(csv(X + "out_of_regime.csv")))])
row("FX R2", F, r"R. of at most ([\d.]+) across the (\d+) rows",
    [(X + "fx_contamination.csv", "max(r2)", lambda: csv(X + "fx_contamination.csv")["r2"].max()),
     (X + "fx_contamination.csv", "len", lambda: len(csv(X + "fx_contamination.csv")))])
for per, lab in [("2010-2014 post-GFC QE", "2010.2014 post-GFC QE"), ("2015-2019 divergence/NIRP", "2015.2019 divergence/NIRP"),
                 ("2020-2021 COVID", "2020.2021 COVID"), ("2022-2026 hiking/normalis.", "2022.2026 hiking/normalisation")]:
    row(f"regime passes {per}", F, r"\| " + lab + r" \| (\d+) \| (\d+) \|",
        [(X + "regime_screen.csv", f"sum(passes)[{per}]", (lambda per: lambda: csv(X + "regime_screen.csv").query(f"period == '{per}'")["passes"].sum())(per)),
         (X + "regime_screen.csv", f"sum(passes_fdr)[{per}]", (lambda per: lambda: csv(X + "regime_screen.csv").query(f"period == '{per}'")["passes_fdr"].sum())(per))])
OOS = [("US2s10s_vs_CA2s10s", "US2s10s/CA2s10s", [0, 1, 2]), ("DE5Y_vs_CA5Y", "DE5Y/CA5Y", [0, 1, 2]),
       ("JP2s10s_vs_CA2s10s", "JP2s10s/CA2s10s", [0, 1, 2]), ("DE10Y_vs_CA10Y", "DE10Y/CA10Y", [0, 1, 2])]
for name, lab, idx in OOS:
    pat = "".join(rf"\| {re.escape(lab)} \| [^|]+ \| [^|]+ \| ([\d.]+) \| (\d+) \| ([+-]?[\d.]+) \|\s*" for _ in idx)
    # the three rows of a pair are consecutive in the table; each row has beta, trades, Sharpe
    specs = []
    for i in idx:
        for fld in ("beta_fit", "oos_trades", "oos_sharpe"):
            specs.append((X + "out_of_regime.csv", f"{name}[{i}].{fld}",
                          (lambda n, i, f: lambda: csv(X + "out_of_regime.csv").query(f"name == '{n}'").iloc[i][f])(name, i, fld)))
    row(f"OOS table {name}", F, pat, specs)


def panel_rows():
    d = ROOT / "cross_country/gr_rv/data"
    fr = [pd.read_csv(d / f"{m}_yields.csv", index_col=0, parse_dates=True).add_prefix(m + "_")
          for m in ["US", "DE", "JP", "CA"]]
    p = pd.concat(fr, axis=1).sort_index()
    return len(p[p.index >= "2010-01-01"].dropna())


row("data rows", F, r"(\d,\d+) aligned daily observations",
    [("cross_country/gr_rv/data/*_yields.csv", "rows with all 16 series from 2010-01-01", panel_rows)])


# ---- extra sources: small aggregate csvs written by the carry and cross-country scripts
def kv(rel, name, field):
    """(source, field, expected) for a long-format csv with columns name, field, value."""
    return (rel, f"{name}.{field}",
            lambda: csv(rel)[(csv(rel)["name"] == name) & (csv(rel)["field"] == field)]["value"].iloc[0])


def kvv(rel, name, field):
    return kv(rel, name, field)[2]()


CR = "carry/results/"
DG, SG, BS = CR + "diagnostics_summary.csv", CR + "sign_check.csv", CR + "bootstrap_summary.csv"
UR, UJ = CR + "us_rule_summary.csv", CR + "us_diagnostic_dv01_jump.csv"
EXP = CR + "experiments_A_to_G.csv"
XD = "cross_country/results/diagnostics_summary.csv"
SCV = CR + "sleeve_correlations.csv"
RS = CR + "regime_stability.csv"
URD = CR + "us_rule_dispersion.csv"


def exv(book, field):
    return (EXP, f"{book}.{field}", lambda: col(EXP, "book", book, field)())


def exv100(book, field):
    return (EXP, f"{book}.{field}*100", lambda: 100 * col(EXP, "book", book, field)())


def frozen_diff(label):
    """Printed diff = reproduced - frozen, both read from the same table row."""
    def f():
        m = re.search(re.escape(label) + r" \| ([\d.]+) \| ([\d.]+) \| ([+-][\d.]+) \|", text(FROZEN))
        return float(m.group(3))
    return f


def sleeve(i, j):
    return (SCV, f"[{i},{j}]", lambda: csv(SCV).iloc[i, j + 1])


def ic_neg():
    return (SG, "count(ic_spearman < 0)", lambda: (csv(SG)[csv(SG)["name"] == "ic_spearman"]["value"] < 0).sum())


def ic_roots():
    return (SG, "count(ic_spearman)", lambda: (csv(SG)["name"] == "ic_spearman").sum())


def sharpe_gap():
    return (EXP, "G_baseline - G_equal_3sleeve sharpe",
            lambda: col(EXP, "book", "G_baseline_2sleeve_mom_2s10s", "sharpe")() - col(EXP, "book", "G_equal_3sleeve", "sharpe")())


def dd_gap():
    return (EXP, "|maxdd G_equal_3sleeve| - |maxdd baseline|",
            lambda: abs(col(EXP, "book", "G_equal_3sleeve", "maxdd")()) - abs(col(EXP, "book", "G_baseline_2sleeve_mom_2s10s", "maxdd")()))


def n_pos_sub():
    return (RS, "count(carry_kmpv > 0)", lambda: (csv(RS)["carry_kmpv"] > 0).sum())


def disp(panel, root, field):
    return (URD, f"{panel}.{root}.{field}", lambda: csv(URD)[(csv(URD)["panel"] == panel) & (csv(URD)["root"] == root)][field].iloc[0])


def nonus_kurt(fn):
    return (URD, f"{fn.__name__}(cleaned kurt, non-US)", lambda: fn(csv(URD)[(csv(URD)["panel"] == "cleaned") & (csv(URD)["root"] != "US")]["kurt"]))


EFBOOKS = ["E_carry50_mom50", "F_carry50_2s10s50", "E_carry75_mom25", "F_carry75_2s10s25"]


def ef(fn, field):
    return (EXP, f"{fn.__name__} {field} of E/F 50,75", lambda: fn(col(EXP, "book", b, field)() for b in EFBOOKS))


def dgcol(name, fn):
    return (DG, f"{fn} {name}", lambda: getattr(csv(DG)[csv(DG)["name"] == name]["value"], fn)())


C = FROZEN
row("headline", C, r"Sharpe of (0\.02) standalone, anti-predicts next-month (?:> )?returns in (5) of (6) roots, and \*subtracts\* (0\.16) Sharpe and (6) points",
    [exv("A2_carry_xs", "sharpe"), ic_neg(), ic_roots(), sharpe_gap(), dd_gap()])
for lab in ["Duration momentum", "2s10s reversion", "5s30s reversion", "2s5s10s butterfly"]:
    row(f"section 0 diff {lab}", C, lab + r" \| [\d.]+ \| [\d.]+ \| ([+-][\d.]+) \|",
        [(HM, f"sharpe - frozen [{lab}]", lambda lab=lab: float(re.search(re.escape(lab) + r" \| ([\d.]+) \| ([\d.]+) \|", text(FROZEN)).group(1)) - float(re.search(re.escape(lab) + r" \| ([\d.]+) \| ([\d.]+) \|", text(FROZEN)).group(2)))])
row("section 0 max diff", C, r"All within ([\d.]+) Sharpe",
    [(HM, "max |reproduced - frozen|", lambda: max(abs(frozen_diff(l)()) for l in ["Duration momentum", "2s10s reversion", "5s30s reversion", "2s5s10s butterfly"]))])
row("rounding boundary", C, r"rounding-boundary cases \(([\d.]+), ([\d.]+)\)", [hmx("2s10s_reversion", "sharpe"), hmx("2s5s10s_fly", "sharpe")])
row("US episode", C, r"\((\d+) obs, ([\d.]+)% of sample", [kv(UR, "episode", "days"), kv(UR, "episode", "share_of_sample_pct")])
row("US DV01 jump", C, r"largest US DV01 jump in the sample \(\+([\d.]+)%, (\d{4})-(\d\d)-(\d\d)\)",
    [kv(UJ, "us_dv01", "max_jump_pct"), kv(UJ, "us_dv01", "max_jump_year"), kv(UJ, "us_dv01", "max_jump_month"), kv(UJ, "us_dv01", "max_jump_day")])
row("US rule table", C, r"sd ratio vs TY \| ([\d.]+)× \| ([\d.]+)× \|.*?Excess kurtosis \| ([\d.]+) \| ([\d.]+) \| (-[\d.]+) to \+([\d.]+) \|"
    r".*?Mean corr with other roots \| \+([\d.]+) \| \+([\d.]+) \| \+([\d.]+) among others \|"
    r".*?\| (\d+)% \((\d+)/(\d+)\) \| ([\d.]+)% false-positive",
    [disp("raw", "US", "sd_ratio_vs_TY"), disp("cleaned", "US", "sd_ratio_vs_TY"), disp("raw", "US", "kurt"), disp("cleaned", "US", "kurt"),
     nonus_kurt(min), nonus_kurt(max),
     kv(UR, "raw_mean_corr", "us_vs_others"), kv(UR, "cleaned_mean_corr", "us_vs_others"), kv(UR, "cleaned_mean_corr", "among_others"),
     kv(UR, "episode", "guard_caught_pct"), kv(UR, "episode", "guard_caught_days"), kv(UR, "episode", "days"),
     kv(UR, "non_episode", "guard_flagged_pct")])
row("vols", C, r"much lower volatility \(([\d.]+)% and ([\d.]+)%\)", [exv100("A2_carry_xs", "vol"), exv100("A2_carrycurve_xs", "vol")])
row("A fails", C, r"Sharpe ([\d.]+) \(needs > 0\.4\), NW-t ([\d.]+) \(needs > 2\.0\), and sign positive in only (\d) of 4 subperiods",
    [exv("A2_carry_xs", "sharpe"), exv("A2_carry_xs", "nw_t"), n_pos_sub()])
row("best conditioned", C, r"C2 2s10s tilt 0\.25, Sharpe ([\d.]+) vs ([\d.]+)\).*?\(([\d.]+) vs ([\d.]+)/yr\)",
    [exv("C2_2s10s_tilt0.25", "sharpe"), hmx("2s10s_reversion", "sharpe"), exv("C2_2s10s_tilt0.25", "turnover"), hmx("2s10s_reversion", "turnover_per_yr")])
row("DM counts", C, r"(\d+) DM tests, (\d+) survive", [kv(BS, "dm_tests", "n_tests"), kv(BS, "dm_tests", "n_fdr_pass")], every=True)
row("E/F range", C, r"E/F at 50% and 75% carry \| ([\d.]+) . ([\d.]+) \| (-\d+)% to (-\d+)%",
    [ef(min, "sharpe"), ef(max, "sharpe"), ef(max, "maxdd"), ef(min, "maxdd")])
row("incremental Sharpe", C, r"Incremental Sharpe of adding carry: (-[\d.]+), stationary block bootstrap 95% CI \[(-[\d.]+), \+([\d.]+)\]\. Drawdown worsens from (-[\d.]+)% to (-[\d.]+)%",
    [kv(BS, "bootstrap_3sleeve_vs_2sleeve", "sharpe_diff"), kv(BS, "bootstrap_3sleeve_vs_2sleeve", "ci_low"), kv(BS, "bootstrap_3sleeve_vs_2sleeve", "ci_high"),
     exv("G_baseline_2sleeve_mom_2s10s", "maxdd"), exv("G_equal_3sleeve", "maxdd")])
row("rename 1c", C, r"\| (-[\d.]+) Sharpe, CI \[(-[\d.]+), \+([\d.]+)\], DD worse by (\d)pp",
    [kv(BS, "bootstrap_3sleeve_vs_2sleeve", "sharpe_diff"), kv(BS, "bootstrap_3sleeve_vs_2sleeve", "ci_low"), kv(BS, "bootstrap_3sleeve_vs_2sleeve", "ci_high"), dd_gap()])
row("sleeve table kmpv", C, r"\| carry_kmpv \| ([\d.]+) \| ([\d.]+) \| ([\d.]+) \| ([\d.]+) \| ([\d.]+) \|", [sleeve(0, j) for j in range(5)])
row("sleeve table curve", C, r"\| carry_curve \| ([\d.]+) \| ([\d.]+) \| ([\d.]+) \| ([\d.]+) \| ([\d.]+) \|", [sleeve(1, j) for j in range(5)])
row("max |rho| of primary", C, r"\(\|ρ\| ≤ ([\d.]+)\)", [(SCV, "max |carry_kmpv vs existing sleeves|", lambda: max(csv(SCV).iloc[0, 3:6]))])
row("secondary vs 5s30s", C, r"\((?:ρ )?(0\.369)\)", [sleeve(1, 4)], every=True)
row("primary correlations", C, r"Primary passes \(([\d.]+), ([\d.]+)\)", [sleeve(0, 2), sleeve(0, 3)])
row("IC counts", C, r"negative in (\d) of (\d) roots", [ic_neg(), ic_roots()], every=True)
row("rank corr", C, r"is \+([\d.]+), above", [kv(SG, "rank_corr_carry_dv01", "mean")])
row("rank corr share", C, r"above \+0\.5 on ([\d.]+)% of days", [kv(SG, "rank_corr_carry_dv01", "share_gt_0.5_pct")])
row("mean carry by root", C, r"TU \+([\d.]+)%, FV \+([\d.]+)%, TY \+([\d.]+)%, UXY \+([\d.]+)%, US \+([\d.]+)%, WN \+([\d.]+)%\)",
    [disp("cleaned", r, "mean") for r in ["TU", "FV", "TY", "UXY", "US", "WN"]])
row("neutral vol", C, r"collapses its volatility to ([\d.]+)%", [exv100("A2_carry_xs", "vol")])
row("cash-curve book", C, r"looks strong \(([\d.]+), t ([\d.]+)\)", [exv("A2_carrycurve_xs", "sharpe"), exv("A2_carrycurve_xs", "nw_t")])
row("cash-curve turnover", C, r"Turnover is ([\d.]+) per year", [exv("A2_carrycurve_xs", "turnover")])
row("cost sensitivity text", C, r"flat \(([\d.]+) . ([\d.]+) at 3. tick\)", [kv(DG, "cost_sensitivity_curve", "1x"), kv(DG, "cost_sensitivity_curve", "3x")])
row("exclusions", C, r"Excluding US \| Worse \(([\d.]+) . (-[\d.]+)\)", [exv("A2_carry_xs", "sharpe"), exv("A2_carry_xs_noUS", "sharpe")])
row("exclusions WN", C, r"Excluding WN \| Worse \(([\d.]+) . (-[\d.]+)\)", [exv("A2_carry_xs", "sharpe"), exv("A2_carry_xs_noWN", "sharpe")])
row("variants disagree", C, r"primary ([\d.]+), secondary ([\d.]+)\. Pre-specified", [exv("A2_carry_xs", "sharpe"), exv("A2_carrycurve_xs", "sharpe")])
row("subperiods secondary", C, r"\(secondary\) \| \+([\d.]+) / \+([\d.]+) / \+([\d.]+) / \+([\d.]+) ",
    [(RS, f"carry_curve[{i}]", (lambda i: lambda: csv(RS)["carry_curve"].iloc[i])(i)) for i in range(4)])
row("subperiods primary", C, r"\(primary\) \| \+([\d.]+) / \+([\d.]+) / (-[\d.]+) / (-[\d.]+) ",
    [(RS, f"carry_kmpv[{i}]", (lambda i: lambda: csv(RS)["carry_kmpv"].iloc[i])(i)) for i in range(4)])
row("cost sensitivity row", C, r"primary ([\d.]+) / (-[\d.]+) / (-[\d.]+); secondary ([\d.]+) / ([\d.]+) / ([\d.]+) \|",
    [kv(DG, "cost_sensitivity_kmpv", k) for k in ("1x", "2x", "3x")] + [kv(DG, "cost_sensitivity_curve", k) for k in ("1x", "2x", "3x")])
row("autocorrelation", C, r"\| ([\d.]+) \(1d\), ([\d.]+).([\d.]+) \(63d\) . persistent, so turnover is low \(([\d.]+)/yr\)",
    [dgcol("kmpv_autocorr_lag1", "mean"), dgcol("kmpv_autocorr_lag63", "min"), dgcol("kmpv_autocorr_lag63", "max"), exv("A2_carry_xs", "turnover")])
row("calendar vs cash", C, r"\| ([\d.]+).([\d.]+) per root", [dgcol("calendar_vs_cash_curve_corr", "min"), dgcol("calendar_vs_cash_curve_corr", "max")])
row("rename 1a", C, r"Sharpe ([\d.]+) vs > 0\.4; NW-t ([\d.]+) vs > 2\.0; (\d)/4 subperiods", [exv("A2_carry_xs", "sharpe"), exv("A2_carry_xs", "nw_t"), n_pos_sub()])
row("book count", C, r"(\d+)(?= book-return series|-column frame)", [(EXP, "len(books)", lambda: len(csv(EXP)))], every=True)

# ---- cross_country/FINDINGS.md
F = "cross_country/FINDINGS.md"
RSC, OOR, IRS, FXC, FSS = X + "regime_screen.csv", X + "out_of_regime.csv", X + "in_regime_survivors.csv", X + "fx_contamination.csv", X + "full_sample_screen.csv"


def n(rel, expr, fn):
    return (rel, expr, lambda: fn(csv(rel)))


def survivor(rel, name, per, field):
    return (rel, f"{name}.{per}.{field}",
            lambda: csv(rel)[(csv(rel)["name"] == name) & csv(rel)["period"].str.startswith(per[:4])][field].iloc[0])


NCAND = lambda d: d["passes"].sum()
row("summary arc", F, r"Full sample \(2010.2026\): (\d+) of (\d+) candidates",
    [n(FSS, "sum(passes)", lambda d: d["passes"].sum()), n(FSS, "len", len)])
row("banner new values", F, r"raw regime passes \d+ . (\d+), FDR (?:> )?survivors \d+ . (\d+), out-of-regime mean Sharpe -[\d.]+ . (-[\d.]+), positive \d+ of \d+ . (\d+) of (\d+), (?:> )?Canada in survivors \d+ of \d+ . (\d+) of (\d+)",
    [n(RSC, "sum(passes)", lambda d: d["passes"].sum()), n(RSC, "sum(passes_fdr)", lambda d: d["passes_fdr"].sum()),
     n(OOR, "mean(oos_sharpe)", lambda d: d["oos_sharpe"].mean()), n(OOR, "sum(oos_sharpe>0)", lambda d: (d["oos_sharpe"] > 0).sum()),
     n(OOR, "len", len), kv(XD, "survivors", "raw_with_canada"), kv(XD, "survivors", "raw")])
row("panel rows", F, r"(3,762)", [kv(XD, "panel", "rows")], every=True)
row("panel series", F, r"(\d+) series, no gaps", [kv(XD, "panel", "series")])
row("zero-change days", F, r"JP 2Y has ([\d,]+) zero-change days", [kv(XD, "zero_change_days", "JP_2Y")])
row("zero-change days US", F, r"US 2Y consequently shows (\d+) zero-change days", [kv(XD, "zero_change_days", "US_2Y")])
row("FX pair values", F, r"DE5Y/JP5Y ([\d.]+) and US2Y/CA2Y ([\d.]+) in 2015.2019; the other nine are below ([\d.]+)\)",
    [(FXC, "r2[DE5Y_vs_JP5Y]", col(FXC, "name", "DE5Y_vs_JP5Y", "r2")), (FXC, "r2[US2Y_vs_CA2Y]", col(FXC, "name", "US2Y_vs_CA2Y", "r2")),
     n(FXC, "max(r2) of the other nine", lambda d: d[~d["name"].isin(["DE5Y_vs_JP5Y", "US2Y_vs_CA2Y"])]["r2"].max())])
CLAIMS[-1].lt = True
row("FX reproduction", F, r"US2s10s/CA2s10s reproduces at ([\d.]+)",
    [(FXC, "r2[US2s10s_vs_CA2s10s 2022-26]", lambda: csv(FXC)[(csv(FXC)["name"] == "US2s10s_vs_CA2s10s") & csv(FXC)["r2"].notna()]["r2"].iloc[0])])
row("FX max", F, r"ten survivors with FX overlap is ([\d.]+) \(DE5Y/JP5Y", [n(FXC, "max(r2)", lambda d: d["r2"].max())])
row("FX under 1%", F, r"explains under (\d)% of the P&L", [n(FXC, "100*max(r2)", lambda d: 100 * d["r2"].max())])
CLAIMS[-1].lt = True
row("FX quote", F, r"stands; ([\d.]+) is the figure to quote", [n(FXC, "max(r2)", lambda d: d["r2"].max())])
row("FX at most", F, r"R. . ([\d.]+)\)", [n(FXC, "max(r2)", lambda d: d["r2"].max())])
row("sub-period summary", F, r"Sub-period \((\d) policy regimes\): (\d+) of (\d+) pass the screen, (\d+) survive FDR",
    [n(RSC, "nunique(period)", lambda d: d["period"].nunique()), n(RSC, "sum(passes)", lambda d: d["passes"].sum()), n(RSC, "len", len), n(RSC, "sum(passes_fdr)", lambda d: d["passes_fdr"].sum())])
row("grid size", F, r"entire (\d+)-test grid \((\d+) candidates . (\d) periods\)",
    [n(RSC, "len", len), n(RSC, "nunique(name)", lambda d: d["name"].nunique()), n(RSC, "nunique(period)", lambda d: d["period"].nunique())])
row("half-life ranges", F, r"half-lives in the tradable ([\d.]+).([\d.]+) day range rather than the ([\d.]+).([\d,]+) days of the full sample",
    [kv(XD, "fdr_survivors", "half_life_min"), kv(XD, "fdr_survivors", "half_life_max"),
     n(FSS, "min(half_life)", lambda d: d["half_life"].min()), n(FSS, "max(half_life)", lambda d: d["half_life"].max())])
SURV = [("US2s10s vs CA2s10s", "2022–2026"), ("JP2s10s vs CA2s10s", "2020–2021"), ("US5Y vs CA5Y", "2020–2021"), ("DE5Y vs CA5Y", "2020–2021"),
        ("US2s10s vs CA2s10s", "2010–2014"), ("DE5Y vs JP5Y", "2015–2019"), ("DE10Y vs CA10Y", "2020–2021"), ("US2Y vs CA2Y", "2015–2019"),
        ("DE5s30s vs CA5s30s", "2022–2026"), ("US10Y vs CA10Y", "2020–2021"), ("US5s30s vs CA5s30s", "2015–2019")]
for lab, per in SURV:
    nm = lab.replace(" vs ", "_vs_")
    row(f"survivor {lab} {per}", F, r"\| " + re.escape(lab) + r" \| " + per + r" \| ([\d.]+) \| ([\d.]+) \| ([\d.]+) \| ([\d.]+) \| ([\d.]+) \| (?:yes|no) \|",
        [survivor(RSC, nm, per, f) for f in ("beta", "adf_p", "adf_p_fdr", "half_life", "beta_cv")])
row("Canada share", F, r"Canada appears in (\d+) of (\d+) raw survivors and (\d+) of (\d+) FDR survivors",
    [kv(XD, "survivors", "raw_with_canada"), kv(XD, "survivors", "raw"), kv(XD, "survivors", "fdr_with_canada"), kv(XD, "survivors", "fdr")])
row("most stable", F, r"passes in (\d) of (\d) regimes . both times surviving FDR . with the tightest . range \(([\d.]+)\)",
    [kv(XD, "US2s10s_vs_CA2s10s", "periods_passed"), n(RSC, "nunique(period)", lambda d: d["period"].nunique()), kv(XD, "US2s10s_vs_CA2s10s", "beta_range")])
row("window default", F, r"the module default of 252 gives a mean of (-[\d.]+) on the same twelve", [kv(XD, "oos_window_252", "mean_sharpe")])
row("OOS summary", F, r"Mean OOS Sharpe (-[\d.]+); positive in (\d+) of (\d+) . and the five positives are small \(\+([\d.]+) to \+([\d.]+)\) while the losses run to (-[\d.]+)\.",
    [n(OOR, "mean(oos_sharpe)", lambda d: d["oos_sharpe"].mean()), n(OOR, "sum(oos_sharpe>0)", lambda d: (d["oos_sharpe"] > 0).sum()), n(OOR, "len", len),
     n(OOR, "min positive oos_sharpe", lambda d: d[d["oos_sharpe"] > 0]["oos_sharpe"].min()),
     n(OOR, "max oos_sharpe", lambda d: d["oos_sharpe"].max()), n(OOR, "min oos_sharpe", lambda d: d["oos_sharpe"].min())])
row("DE5Y beta", F, r"DE5Y/CA5Y is fit at ([\d.]+), then ([\d.]+), then ([\d.]+)\.",
    [(OOR, f"DE5Y_vs_CA5Y[{i}].beta_fit", (lambda i: lambda: csv(OOR)[csv(OOR)["name"] == "DE5Y_vs_CA5Y"]["beta_fit"].iloc[i])(i)) for i in range(3)])
row("in-period", F, r"(\d+) of the (\d+) raw-screen survivors had a negative in-period Sharpe.*?US2s10s/CA2s10s at \+([\d.]+) \((\d+) trades\) and US2Y/CA2Y at \+([\d.]+) \((\d+) trades\)\. The worst is DE10Y/CA10Y at (-[\d.]+)\.",
    [n(IRS, "sum(sharpe<0)", lambda d: (d["sharpe"] < 0).sum()), n(IRS, "len", len),
     survivor(IRS, "US2s10s_vs_CA2s10s", "2022", "sharpe"), survivor(IRS, "US2s10s_vs_CA2s10s", "2022", "n_trades"),
     (IRS, "US2Y_vs_CA2Y.sharpe", col(IRS, "name", "US2Y_vs_CA2Y", "sharpe")), (IRS, "US2Y_vs_CA2Y.n_trades", col(IRS, "name", "US2Y_vs_CA2Y", "n_trades")),
     (IRS, "DE10Y_vs_CA10Y.sharpe", col(IRS, "name", "DE10Y_vs_CA10Y", "sharpe"))])
row("warm-up", F, r"consumes ([\d.]+)% of a ([\d,]+)-day window - Only (\d+) trades, in position (\d+) of ([\d,]+) days \((\d+)%\)",
    [(XD, "100*warmup_days/days", lambda: 100 * kvv(XD, "in_regime_window_252", "warmup_days") / kvv(XD, "in_regime_2022_2026", "days")),
     kv(XD, "in_regime_2022_2026", "days"), kv(XD, "in_regime_window_252", "trades"), kv(XD, "in_regime_window_252", "days_in_position"), kv(XD, "in_regime_2022_2026", "days"),
     (XD, "100*days_in_position/days", lambda: 100 * kvv(XD, "in_regime_window_252", "days_in_position") / kvv(XD, "in_regime_2022_2026", "days"))])
row("9 trades", F, r"With (\d+) trades, Sharpe is noise", [kv(XD, "in_regime_window_252", "trades")])
row("window sensitivity", F, r"\+([\d.]+) at window 252, \+([\d.]+) at 126, \+([\d.]+) at 63 \((\d+), (\d+) and (\d+) trades respectively\)",
    [kv(XD, "in_regime_window_252", "sharpe"), kv(XD, "in_regime_window_126", "sharpe"), kv(XD, "in_regime_window_63", "sharpe"),
     kv(XD, "in_regime_window_252", "trades"), kv(XD, "in_regime_window_126", "trades"), kv(XD, "in_regime_window_63", "trades")])
row("swing", F, r"swings from ([\d.]+) to ([\d.]+) on the lookback", [kv(XD, "in_regime_window_252", "sharpe"), kv(XD, "in_regime_window_63", "sharpe")])
row("supported", F, r"\((\d+)/(\d+) rejected\)", [n(FSS, "len", len), n(FSS, "len", len)])
row("supported 2", F, r"\((\d+) of (\d+) survive FDR\), with tradable half-lives of ([\d.]+).([\d.]+) days",
    [n(RSC, "sum(passes_fdr)", lambda d: d["passes_fdr"].sum()), n(RSC, "len", len), kv(XD, "fdr_survivors", "half_life_min"), kv(XD, "fdr_survivors", "half_life_max")])
row("supported 3", F, r"mean OOS Sharpe (-[\d.]+), and (\d+) of (\d+) raw survivors lose money",
    [n(OOR, "mean(oos_sharpe)", lambda d: d["oos_sharpe"].mean()), n(IRS, "sum(sharpe<0)", lambda d: (d["sharpe"] < 0).sum()), n(IRS, "len", len)])

# ---------------------------------------------------------------- paper/treasury_curve_paper.tex
T = "paper/treasury_curve_paper.tex"
row("2s10s momentum Sharpe (every use)", T, r"(?<![\d.])(-0\.79)(?!\d)", [hmx("2s10s_momentum_signal", "sharpe")], every=True)
row("2s10s reversion Sharpe (every use)", T, r"(?<![\d.-])(0\.72)(?!\d)", [hmx("2s10s_reversion", "sharpe")], every=True)
row("duration momentum Sharpe (every use)", T, r"(?<![\d.-])(0\.68)(?!\d)", [hmx("DurationMomentum", "sharpe")], every=True)
row("5s30s Sharpe (every use)", T, r"(?<![\d.-])(0\.66)(?!\d)", [hmx("5s30s_reversion", "sharpe")], every=True)
row("butterfly Sharpe (every use)", T, r"(?<![\d.-])(0\.08)(?!\d)", [hmx("2s5s10s_fly", "sharpe")], every=True)
row("walk-forward pooled (abstract)", T, r"net Sharpe ratios of (0\.87) for 2s10s and (0\.69) for 5s30s",
    [wfp("2s10s", "oos_sharpe"), wfp("5s30s", "oos_sharpe")])
row("panel rows", T, r"aligned panel of (4,173) rows", [hmx("sample", "n_rows")])
row("Sharpe range", T, r"Sharpe range of (0\.66) to (0\.72) with drawdowns of roughly (20)-(27)%",
    [(HM, "min sharpe of curve books", lambda: min(csv(HM).query("field == 'sharpe'").set_index("name").loc[["2s10s_reversion", "5s30s_reversion"], "value"])),
     (HM, "max sharpe of curve books", lambda: max(csv(HM).query("field == 'sharpe'").set_index("name").loc[["2s10s_reversion", "5s30s_reversion"], "value"])),
     (HM, "min |maxdd| of curve books", lambda: min(abs(csv(HM).query("field == 'maxdd_pct'").set_index("name").loc[["2s10s_reversion", "5s30s_reversion"], "value"]))),
     (HM, "max |maxdd| of curve books", lambda: max(abs(csv(HM).query("field == 'maxdd_pct'").set_index("name").loc[["2s10s_reversion", "5s30s_reversion"], "value"])))])
for b, lab in zip(BOOKS, ["Duration momentum \\(baseline\\)", "2s10s mean-reversion", "5s30s mean-reversion", "2s5s10s butterfly"]):
    row(f"results table {b}", T, lab + r" & (-?[\d.]+) & (-\d+)% & (\d+) \\\\",
        [hmx(b, "sharpe"), (HM, f"{b}.maxdd_pct", hm(b, "maxdd_pct")), hmx(b, "turnover_per_yr")])
row("DM", T, r"DM=([\d.]+), p=([\d.]+) and DM=([\d.]+), p=([\d.]+)\), corresponding to an annualized return edge of about ([\d.]+)% and ([\d.]+)%",
    [hmx("2s10s_reversion", "dm"), hmx("2s10s_reversion", "dm_p"), hmx("5s30s_reversion", "dm"),
     hmx("5s30s_reversion", "dm_p"), hmx("2s10s_reversion", "dm_edge_pct"), hmx("5s30s_reversion", "dm_edge_pct")])
row("DM butterfly", T, r"butterfly is negative \(DM=(-[\d.]+), p=([\d.]+)\)", [hmx("2s5s10s_fly", "dm"), hmx("2s5s10s_fly", "dm_p")])
row("duration beta", T, r"has a slope of (-[\d.]+), indistinguishable", [hmx("2s10s_reversion", "beta_to_10y_yield_chg")])
row("regime days", T, r"stress state \((\d+) days\), a steepening state \((\d,\d+) days\), and a flattening state \((\d,\d+) days\)",
    [hmx("regime_days", "stress"), hmx("regime_days", "steepening"), hmx("regime_days", "flattening")])
row("walk-forward fits", T, r"chosen in all (\w+) fits",
    [(WF_T, "count(direction == reversion)", lambda: (csv(WF_T)["direction"] == "reversion").sum())])
row("walk-forward DM", T, r"Duration momentum earns ([\d.]+) on the same 2015-2026 dates.*?is ([\d.]+) \(p=([\d.]+)\) for 2s10s and ([\d.]+) \(p=([\d.]+)\) for 5s30s",
    [wfp("2s10s", "duration_mom_sharpe"), wfp("2s10s", "dm_stat"), wfp("2s10s", "dm_p"), wfp("5s30s", "dm_stat"), wfp("5s30s", "dm_p")])
for sp, rx in (("2s10s", r"2s10s & ([\d.]+) & ([\d.]+) & ([\d.]+) & ([\d.]+) \\\\"),
               ("5s30s", r"5s30s & ([\d.]+) & ([\d.]+) & ([\d.]+) & ([\d.]+) \\\\")):
    row(f"walk-forward table {sp}", T, rx, [wf(sp, 0, "oos_sharpe"), wf(sp, 1, "oos_sharpe"), wf(sp, 2, "oos_sharpe"), wfp(sp, "oos_sharpe")])
row("conclusion Sharpe", T, r"strategies near a Sharpe of (0\.7);",
    [(HM, "mean sharpe of duration momentum and the two curve spreads",
      lambda: csv(HM).query("field == 'sharpe'").set_index("name").loc[["DurationMomentum", "2s10s_reversion", "5s30s_reversion"], "value"].mean())])


# ---------------------------------------------------------------- coverage
# Every number in these documents must be covered by a claim above or be allowlisted with a one-word
# reason.
COVERED_DOCS = ["README.md", "DATA.md", "walkforward/PREREG.md", PAPER, "carry/CARRY_RESULTS.md", "cross_country/FINDINGS.md"]
MONTH = r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
TOKEN = re.compile(
    rf"(?P<date>\d{{4}}-\d{{2}}-\d{{2}}|\d{{1,2}} {MONTH}(?: \d{{4}})?|{MONTH} \d{{4}})"
    r"|(?P<time>\b\d{1,2}:\d{2}\b)"
    r"|(?P<year>(?<![\w.])(?:19|20)\d\d(?:-(?:19|20)?\d\d)?(?!\w|%|\.\d))"
    r"|(?P<num>(?<![\w.])[-+]?\d+(?:,\d{3})*(?:\.\d+)?%?(?![\w]))")

# (documents, regex searched in +-40 characters around the number, one-word reason)
ALLOW = [
    ("*", r"0\.01%; weighting", "unit"),
    ("README.md", r"DGS2/5/10/30", "ticker"),
    ("README.md", r"up to t-1|t-1, trades", "lag"),
    ("README.md", r"126-day warm-up|capped at 3×|toward 10% annual|a 21-day lag", "setting"),
    ("README.md", r"2-year note's cost|10-year leg|2-year leg|10-year yield|DV01-scaled", "tenor"),
    ("README.md", r"above the 10% target|net of costs, 10% volatility target|10% volatility target:", "setting"),
    ("README.md", r"Sharpe > 0\.4, NW-t > 2\.0|HAC t > 2\.0|≥ \+0\.10 Sharpe", "bar"),
    ("README.md", r"tick_frac\(\) returned 0\.0|cost_per_unit was 0\.0", "code"),
    ("README.md", r"Sharpe 0\.71 and 0\.07; DM 0\.83, 0\.68 and -1\.53", "history"),
    ("DATA.md", r"Generics 2 and 3|generics 2/3|loads generic 1", "ticker"),
    ("DATA.md", r"tick_frac\(\) returned 0\.0", "code"),
    ("DATA.md", r"63-day change|252-day z-score", "setting"),
    ("walkforward/PREREG.md", r"lookback: 63, 126, 252 or 504|lookback: 63, 126", "setting"),
    ("walkforward/PREREG.md", r"252-day z-score window|63-day sign|reversion, 252 days|63-day window|126-day warm-up", "setting"),
    ("walkforward/PREREG.md", r"clip at ±3|10% volatility target|3x leverage cap", "setting"),
    ("walkforward/PREREG.md", r"data to t-1|up to t-1|uses data to t-1", "lag"),
    ("walkforward/PREREG.md", r"Three transitions|2 spreads x 3 transitions|at least 2 of the 3 test", "count"),
    ("walkforward/PREREG.md", r"^.{0,40}\b[1-4]\. (?:Net|Overall|HAC|For)|\. [234]\. ", "list"),
    ("walkforward/PREREG.md", r"6 numbers", "count"),
    (PAPER, r"63-day return|trailing 63-day|63-day realized|126-day warm-up|252-day mean|monthly holding|twenty-one", "setting"),
    (PAPER, r"clipped at \\pm 3|capped at 3\\times|10% annualized|lagged one day|t\{-\}1", "setting"),
    (PAPER, r"2-year note's cost|2-year leg|10-year yield|10-year note|10-year tick|10-year leg|2-year", "tenor"),
    (PAPER, r"lookback \(63, 126, 252 or 504 days\)", "setting"),
    ("carry/CARRY_RESULTS.md", r"## \d\. |§[\d.]+|Phase \d|### ", "ref"),
    ("carry/CARRY_RESULTS.md", r"\d\. (?:Signal vs|DV01-neutrality bug|Blend vol|It closes|The mechanism|The data verdict)", "list"),
    ("carry/CARRY_RESULTS.md", r"against frozen [\d./-]+|\| (?:Duration momentum|2s10s reversion|5s30s reversion|2s5s10s butterfly) \| [\d.]+ \| [\d.]+ \|", "frozen"),
    ("carry/CARRY_RESULTS.md", r"pandas build \(2\.2\.2|python 3\.12\.7|pandas 2\.2\.2|numpy 1\.26\.4|Environment:", "version"),
    ("carry/CARRY_RESULTS.md", r"common 10% (?:annualised|vol)|DV01-jump > 5%|> 6 × trailing IQR|±10bd|HAC\(21\)|next 21-day|FDR 5%|FDR at 5%|1×/2×/3×|at 3× tick|tilt [\d.]+|% carry / \d+%|E/F at 50% and 75%|bootstrap 95% CI|top-2 on|above \+0\.5|≈1|DV01 x 100|2022–26|Generic 3|7-column", "setting"),
    ("carry/CARRY_RESULTS.md", r"Sharpe > 0\.4|NW-t > 2\.0|≥3 of 4|needs > 0\.4|needs > 2\.0|vs > 0\.4|vs > 2\.0|HAC t > 2\.0|p < 0\.10|≥ \+0\.10|≥15%|ρ.{1,4}< 0\.3", "bar"),
    ("carry/CARRY_RESULTS.md", r"of 4 subperiods|/4 subperiods", "count"),
    ("carry/CARRY_RESULTS.md", r"\| (?:2|3) sleeves", "count"),
    ("cross_country/FINDINGS.md", r"## Summary|Phase 0|## Next steps|\d\. (?:Full sample|Sub-period|But it|Model FX|Add UK|Time-varying|Shorter|Only then)", "list"),
    ("cross_country/FINDINGS.md", r"3,829|raw regime passes 7|survivors 3 →|Sharpe -0\.32|positive 2 of 12|survivors 6 of 7|\"4 survive FDR\"|tables said 3", "history"),
    ("cross_country/FINDINGS.md", r"DGS2/5/10/30", "ticker"),
    ("cross_country/FINDINGS.md", r"window=126|default of 252|252-day z-score|126-day vol|at window 252|\+0\.37 at 126|\+0\.59 at 63|63–126 day z-score", "setting"),
]


def numbers(doc):
    """Yield (match, kind) for every number-like token in a document."""
    for m in TOKEN.finditer(text(doc)):
        yield m, m.lastgroup


def allow_reason(doc, m, kind):
    if kind in ("date", "time", "year"):
        return kind
    t = text(doc)
    ctx = t[max(0, m.start() - 40): m.end() + 40]
    for d, rx, why in ALLOW:
        if d in ("*", doc) and re.search(rx, ctx):
            return why
    return None


def coverage(doc):
    spans = [sp for c in CLAIMS if c.doc == doc for _, sp in c.matches()]
    covered, allowed, bad = 0, 0, []
    for m, kind in numbers(doc):
        if any(m.start() < e and m.end() > b for b, e in spans):
            covered += 1
        elif allow_reason(doc, m, kind):
            allowed += 1
        else:
            bad.append(f"{m.group()!r} ...{text(doc)[max(0, m.start() - 40): m.end() + 30]}...")
    return covered, allowed, bad


@pytest.mark.parametrize("doc", COVERED_DOCS)
def test_every_number_is_covered(doc):
    covered, allowed, bad = coverage(doc)
    print(f"\n{doc}: {covered} numbers covered by claims, {allowed} allowlisted")
    assert not bad, f"{len(bad)} numbers neither claimed nor allowlisted:\n" + "\n".join(bad)


def ids(c):
    return c.loc


PARAMS = [pytest.param(c, id=c.loc, marks=[])
          for c in CLAIMS]


@pytest.mark.parametrize("claim", PARAMS)
def test_claim(claim):
    s, e = claim.value(), claim.expected()
    assert claim.check(), f"{claim.loc}: text prints {s}, {claim.source} {claim.field} = {e:.6g}"


if __name__ == "__main__":
    print(f"{'claim location':70s} {'value':>9s}  {'expected':>10s}  source :: field")
    for c in CLAIMS:
        try:
            s, e = c.value(), c.expected()
            flag = "ok" if c.check() else "MISMATCH"
        except AssertionError:
            s, e, flag = "NOT FOUND", float("nan"), "MISMATCH"
        print(f"{c.loc:70s} {s:>9s}  {e:10.6g}  {c.source} :: {c.field}  {flag}")
