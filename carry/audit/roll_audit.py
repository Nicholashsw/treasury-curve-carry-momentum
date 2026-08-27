import os, pandas as pd, numpy as np
D = os.environ.get("BBG_CSV") or "data_raw"   # set BBG_CSV to your export folder

def ts(name):
    df = pd.read_csv(os.path.join(D,name))
    df["Date"] = pd.to_datetime(df["Date"], format="%Y-%m-%d %H:%M:%S", errors="coerce")
    return df.dropna(subset=["Date"]).set_index("Date").sort_index()

def static(root):
    df = pd.read_csv(os.path.join(D, f"{root}1_Comdty_STATIC.csv"))
    for c in ["LAST_TRADEABLE_DT","FUT_NOTICE_FIRST","FUT_DLV_DT_FIRST","FUT_DLV_DT_LAST"]:
        df[c] = pd.to_datetime(df[c], dayfirst=True, errors="coerce")   # d/m/yyyy here
    return df

print("=== STATIC: delivery-date structure (dayfirst parse) ===")
for r in ["TU","FV","TY","UXY","US","WN"]:
    s = static(r)
    ok = s["LAST_TRADEABLE_DT"].notna().mean()
    inwin = s[(s.LAST_TRADEABLE_DT>="2009-01-01") & (s.LAST_TRADEABLE_DT<="2027-01-01")]
    print(f"  {r}: {len(s)} contracts, dates parsed {ok:.0%}, "
          f"span {s.LAST_TRADEABLE_DT.min().date()}..{s.LAST_TRADEABLE_DT.max().date()}, "
          f"in-sample {len(inwin)}, tick={s.FUT_TICK_SIZE.iloc[-1]}, size={s.FUT_CONT_SIZE.iloc[-1]:.0f}")

print("\n=== ROLL MAP: generic-1 contract changes (from FUT_CUR_GEN_TICKER) ===")
for r in ["TU","FV","TY","UXY","US","WN"]:
    g = ts(f"{r}1_Comdty.csv")["FUT_CUR_GEN_TICKER"].astype(str)
    g = g[g.ne("nan") & g.ne("")]
    rolls = g.ne(g.shift()) & g.shift().notna()
    yrs = (g.index.max()-g.index.min()).days/365.25
    print(f"  {r}: {rolls.sum()} rolls over {yrs:.1f}y = {rolls.sum()/yrs:.1f}/yr; "
          f"distinct contracts {g.nunique()}; sample {g.iloc[0]} .. {g.iloc[-1]}")

print("\n=== GENERIC 1 vs 2: are both populated on the same dates? (calendar-spread feasibility) ===")
for r in ["TU","FV","TY","UXY","US","WN"]:
    a = ts(f"{r}1_Comdty.csv")["PX_SETTLE"]
    b = ts(f"{r}2_Comdty.csv")["PX_SETTLE"]
    j = pd.concat([a,b],axis=1,keys=["g1","g2"]).dropna()
    sp = (j.g1 - j.g2)
    print(f"  {r}: joint obs {len(j)}, spread mean {sp.mean():+.4f}, sd {sp.std():.4f}, "
          f"pct g1>g2 {100*(sp>0).mean():.1f}%, min {sp.min():+.3f}, max {sp.max():+.3f}")
