"""Every result number printed in the docs and the paper must match a committed results file.

Reads only committed files. Each claim is (location, value found in the text, source file, field,
expected). The text value is located with a regex, so a sentence that is reworded away from the
pattern fails loudly instead of being dropped. A claim passes when |value - expected| is within
half a unit of the last printed digit. Run `python tests/test_claims.py` for the plain table.

Known gaps are `known=` claims (xfail, strict): numbers whose source no longer exists.
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
    def __init__(self, loc, doc, pattern, group, source, field, expected, known=None):
        self.loc, self.doc, self.pattern, self.group = loc, doc, pattern, group
        self.source, self.field, self._exp, self.known = source, field, expected, known

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


def row(loc, doc, pattern, specs, known=None, every=False):
    """One regex, several captured numbers; specs[i] = (source, field, expected) for group i+1."""
    for i, (src, fld, exp) in enumerate(specs, 1):
        if src is not None:
            c = Claim(f"{doc} {loc} #{i}", doc, pattern, i, src, fld, exp, known)
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
row("first implementation vol", R, r"which was not neutral, ran at about (\d+)%",
    [("(none)", "no file: that version is no longer in the code", float("nan"))],
    known="source removed: the non-neutral implementation is gone")
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
     (HM, "no file: p of the August net run", float("nan"))],
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

# Build-dependent August values: the current pandas build rounds across the boundary or differs.
HIST = "August-run value, not stored in any file; current build prints a different value"
for c in CLAIMS:
    if c.loc in ("README.md correction table 5s30s_reversion #1", "README.md correction table DM 2s10s #4",
                 "README.md correction table DM butterfly #1"):
        c.known = HIST


PAPER = "paper/treasury_curve_paper.tex"
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
# reason. CARRY_RESULTS.md and cross_country/FINDINGS.md have their tables claim-checked above but are
# not coverage-checked (their prose carries several hundred more numbers).
COVERED_DOCS = ["README.md", "DATA.md", "walkforward/PREREG.md", PAPER]
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


PARAMS = [pytest.param(c, id=c.loc, marks=[pytest.mark.xfail(reason=c.known, strict=True)] if c.known else [])
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
        print(f"{c.loc:70s} {s:>9s}  {e:10.6g}  {c.source} :: {c.field}  {flag}{'  (known gap)' if c.known else ''}")
