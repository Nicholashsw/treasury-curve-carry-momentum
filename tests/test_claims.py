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
        return all(abs(num(s) - e) <= 0.5 * 10 ** -decimals(s) + 1e-9 for s, _ in self.matches())


CLAIMS = []


def row(loc, doc, pattern, specs, every=False):
    """One regex, several captured numbers; specs[i] = (source, field, expected) for group i+1."""
    for i, (src, fld, exp) in enumerate(specs, 1):
        if src is not None:
            c = Claim(f"{doc} {loc} #{i}", doc, pattern, i, src, fld, exp)
            c.every = every
            CLAIMS.append(c)


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
row("sleeve correlations", C, r"\| carry_curve \| ([\d.]+) \| 1.000 \| ([\d.]+) \| ([\d.]+) \| ([\d.]+) \|",
    [(SC, f"carry_curve.{c}", (lambda c: lambda: csv(SC).loc[1, c])(c)) for c in
     ["carry_kmpv", "momentum", "rev_2s10s", "rev_5s30s"]][:1] +
    [(SC, "carry_curve.momentum", lambda: csv(SC).loc[1, "momentum"]),
     (SC, "carry_curve.rev_2s10s", lambda: csv(SC).loc[1, "rev_2s10s"]),
     (SC, "carry_curve.rev_5s30s", lambda: csv(SC).loc[1, "rev_5s30s"])])
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
