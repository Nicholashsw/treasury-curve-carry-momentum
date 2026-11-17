"""Decide the US include/exclude rule. Mechanical criteria ONLY.

Validation metrics are dispersion and cross-root coherence. No strategy is run
here and no Sharpe ratio is computed or consulted.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import pandas as pd, numpy as np
import carry_data as D, carry_signals as S
pd.set_option("display.width", 200)
OUT = os.path.join(os.path.dirname(__file__), "..", "results")

raw = S.carry_panel(apply_guard=False, apply_winsor=False, roll_days=0)
cln = S.carry_panel(apply_guard=True,  apply_winsor=True,  roll_days=S.ROLL_DAYS)

def summ(P, tag):
    r = []
    for c in P.columns:
        s = P[c].dropna()
        r.append(dict(panel=tag, root=c, n=len(s), mean=100*s.mean(), sd=100*s.std(),
                      min=100*s.min(), max=100*s.max(),
                      kurt=s.kurtosis(), sd_ratio_vs_TY=np.nan))
    df = pd.DataFrame(r)
    df["sd_ratio_vs_TY"] = df.sd / float(df.loc[df.root=="TY","sd"].iloc[0])
    return df.round(3)

a, b = summ(raw,"raw"), summ(cln,"cleaned")
print("=== dispersion BEFORE cleaning ==="); print(a.to_string(index=False))
print("\n=== dispersion AFTER cleaning (roll mask + CTD guard + trailing winsor) ===")
print(b.to_string(index=False))

print("\n=== cross-root correlation of carry levels ===")
print("BEFORE:"); print(raw.corr().round(2).to_string())
print("\nAFTER:");  print(cln.corr().round(2).to_string())

others = [r for r in D.ROOTS if r != "US"]
print("\n=== US coherence with the rest of the panel ===")
for tag, P in (("raw", raw), ("cleaned", cln)):
    cm = P.corr()
    us_mean = cm.loc["US", others].mean()
    oth_mean = cm.loc[others, others].values[np.triu_indices(len(others),1)].mean()
    print(f"  {tag:8s} mean corr(US, others) = {us_mean:+.3f} | "
          f"mean corr among others = {oth_mean:+.3f} | ratio {us_mean/oth_mean:.2f}")

SUMMARY = []
for tag, P in (("raw", raw), ("cleaned", cln)):
    cm = P.corr()
    SUMMARY.append((f"{tag}_mean_corr", "us_vs_others", cm.loc["US", others].mean()))
    SUMMARY.append((f"{tag}_mean_corr", "among_others", cm.loc[others, others].values[np.triu_indices(len(others), 1)].mean()))

print("\n=== how much data does the guard remove? ===")
for r in D.ROOTS:
    sp,_ = S.raw_calendar_spread(r)
    g = S.ctd_guard(r, sp.index); rl = D.roll_window_mask(r, S.ROLL_DAYS).reindex(sp.index, fill_value=False)
    print(f"  {r:4s} CTD-guard {100*g.mean():5.1f}%   roll-window {100*rl.mean():5.1f}%   union {100*(g|rl).mean():5.1f}%")

print("\n=== does the guard catch the 2014-12..2015-03 episode? ===")
sp,_ = S.raw_calendar_spread("US")
g = S.ctd_guard("US", sp.index)
ep = (sp.index >= "2014-12-22") & (sp.index <= "2015-03-20")
print(f"  episode days flagged by guard: {100*g[ep].mean():.1f}%  ({int(g[ep].sum())}/{int(ep.sum())})")
print(f"  non-episode days flagged     : {100*g[~ep].mean():.1f}%")

SUMMARY += [("episode", "days", ep.sum()), ("episode", "share_of_sample_pct", 100*ep.sum()/len(sp)),
            ("episode", "guard_caught_pct", 100*g[ep].mean()), ("episode", "guard_caught_days", g[ep].sum()),
            ("non_episode", "guard_flagged_pct", 100*g[~ep].mean())]
pd.DataFrame(SUMMARY, columns=["name", "field", "value"]).round(4).to_csv(os.path.join(OUT, "us_rule_summary.csv"), index=False)
pd.concat([a,b]).to_csv(os.path.join(OUT,"us_rule_dispersion.csv"), index=False)
cln.corr().round(4).to_csv(os.path.join(OUT,"carry_cross_root_corr_cleaned.csv"))
print("\nwrote carry/results/us_rule_*.csv")
