"""US (classic bond) carry anomaly diagnostic.

Run BEFORE any strategy is evaluated. The include/exclude rule for the primary
panel is decided here, on mechanical grounds only. No Sharpe ratio is computed
in this file and none is consulted.

Anomaly to explain (from CARRY_FIELD_INVENTORY.md 3.4):
    US carry sd 5.40% vs TY 1.86%; raw spread min -19.4 points;
    cross-root carry correlation 0.07-0.21 vs 0.52-0.88 among the others.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
import pandas as pd
import carry_data as D

pd.set_option("display.width", 200)
OUT = os.path.join(os.path.dirname(__file__), "..", "results")


def raw_spread(root):
    f1 = pd.to_numeric(D.futures(root, 1)["PX_SETTLE"], errors="coerce")
    f2 = pd.to_numeric(D.futures(root, 2)["PX_SETTLE"], errors="coerce")
    return pd.concat([f1, f2], axis=1, keys=["g1", "g2"]).dropna().eval("g1 - g2")


print("="*80); print("US / CLASSIC BOND CARRY DIAGNOSTIC"); print("="*80)

sp = {r: raw_spread(r) for r in D.ROOTS}

# ---- H0: how extreme is US, and is it one bad print or many? ---------------
print("\n[1] Raw calendar spread (points), tail behaviour")
rows = []
for r in D.ROOTS:
    s = sp[r]
    rows.append(dict(root=r, n=len(s), mean=s.mean(), sd=s.std(),
                     min=s.min(), p01=s.quantile(.01), p99=s.quantile(.99),
                     max=s.max(), n_below_m3=(s < -3).sum(), n_below_m1=(s < -1).sum()))
t1 = pd.DataFrame(rows).round(3); print(t1.to_string(index=False))

us = sp["US"]
ext = us[us < -3].sort_values()
print(f"\n  US observations below -3 points: {len(ext)}")
print(f"  their dates span: {ext.index.min().date()} .. {ext.index.max().date()}")
print(f"  distinct years: {sorted(ext.index.year.unique().tolist())}")
print("  worst 10:")
print(ext.head(10).to_string())

# ---- H1: are extremes clustered on roll dates? -----------------------------
print("\n[2] H1  roll mechanics / generic misalignment")
rw = D.roll_window_mask("US", days=3).reindex(us.index, fill_value=False)
print(f"  share of ALL US obs inside a +/-3bd roll window : {100*rw.mean():.1f}%")
print(f"  share of US obs BELOW -3 inside a roll window   : {100*rw[us < -3].mean():.1f}%")
print(f"  sd inside roll windows  {us[rw].std():.3f}   outside {us[~rw].std():.3f}")

# ---- H2: contract-specification change --------------------------------------
print("\n[3] H2  contract specification change (CME redefined the classic-bond basket)")
byyear = us.groupby(us.index.year).agg(["count", "mean", "std", "min"]).round(3)
print(byyear.to_string())

# ---- H3: CTD switching, proxied by DV01 discontinuity -----------------------
print("\n[4] H3  CTD switching, proxied by day-on-day DV01 jumps")
for r in ["US", "WN", "TY"]:
    d = D.dv01(r)
    jump = d.pct_change().abs()
    print(f"  {r:3s} DV01 median {d.median():6.2f} | daily |%chg| p99 {100*jump.quantile(.99):5.2f}% "
          f"| days >5% {int((jump > .05).sum()):4d} | max {100*jump.max():6.1f}%")

# ---- H4: is the deferred contract even liquid? ------------------------------
print("\n[5] H4  is generic 2 a real contract for each root? (median open interest)")
for r in D.ROOTS:
    oi1 = pd.to_numeric(D.futures(r,1)["OPEN_INT"], errors="coerce").median()
    oi2 = pd.to_numeric(D.futures(r,2)["OPEN_INT"], errors="coerce").median()
    print(f"  {r:4s} g1 {oi1:12,.0f}   g2 {oi2:10,.0f}   ratio g2/g1 {oi2/oi1:6.3%}")

jump = D.dv01("US").pct_change().abs()
pd.DataFrame([("us_dv01", "max_jump_pct", 100*jump.max()), ("us_dv01", "max_jump_year", jump.idxmax().year),
              ("us_dv01", "max_jump_month", jump.idxmax().month), ("us_dv01", "max_jump_day", jump.idxmax().day)],
             columns=["name", "field", "value"]).round(4).to_csv(os.path.join(OUT, "us_diagnostic_dv01_jump.csv"), index=False)
t1.to_csv(os.path.join(OUT, "us_diagnostic_spread_tails.csv"), index=False)
byyear.to_csv(os.path.join(OUT, "us_diagnostic_by_year.csv"))
print("\nwrote carry/results/us_diagnostic_*.csv")
