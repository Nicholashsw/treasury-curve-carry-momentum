import os, pandas as pd, numpy as np
D = os.environ.get("BBG_CSV") or "data_raw"   # set BBG_CSV to your export folder
def ts(n, col=None):
    df = pd.read_csv(os.path.join(D,n))
    df["Date"]=pd.to_datetime(df["Date"],format="%Y-%m-%d %H:%M:%S",errors="coerce")
    df=df.dropna(subset=["Date"]).set_index("Date").sort_index()
    return pd.to_numeric(df[col],errors="coerce") if col else df

roots=["TU","FV","TY","UXY","US","WN"]
print("="*78)
print("CANDIDATE B  --  KMPV futures carry from the generic-1 / generic-2 spread")
print("  carry_ann = (F1 - F2) / F2 / dT,  dT = 0.25y (quarterly cycle)")
print("="*78)
car={}
for r in roots:
    f1,f2 = ts(f"{r}1_Comdty.csv","PX_SETTLE"), ts(f"{r}2_Comdty.csv","PX_SETTLE")
    j=pd.concat([f1,f2],axis=1,keys=["g1","g2"]).dropna()
    c=((j.g1-j.g2)/j.g2)/0.25
    car[r]=c
    print(f"  {r:4s} n={len(c):5d}  mean {100*c.mean():+6.2f}%  sd {100*c.std():5.2f}%  "
          f"p5 {100*c.quantile(.05):+6.2f}%  p95 {100*c.quantile(.95):+6.2f}%  pos {100*(c>0).mean():4.1f}%")
C=pd.DataFrame(car)
print(f"\n  cross-sectional dispersion (sd across roots per day): mean {100*C.std(axis=1).mean():.2f}%")
print(f"  pairwise corr of carry levels:\n{C.corr().round(2).to_string()}")
print(f"\n  autocorrelation (1d / 21d) of TY carry: {C.TY.autocorr(1):.3f} / {C.TY.autocorr(21):.3f}"
      f"   <- persistence is what makes it a tradeable signal")

print("\n"+"="*78)
print("CANDIDATE C  --  cash-curve carry & roll  (yield space, ex-ante)")
print("  carry(tau)  = y(tau) - r_f              [financing spread]")
print("  roll(tau,h) = y(tau) - y(tau-h)         [slide down an unchanged curve]")
print("="*78)
ten={0.25:"USGG3M",0.5:"USGG6M",1:"USGG12M",2:"USGG2YR",3:"USGG3YR",5:"USGG5YR",
     7:"USGG7YR",10:"USGG10YR",30:"USGG30YR"}
Y=pd.concat({k:ts(f"{v}_Index.csv","PX_LAST") for k,v in ten.items()},axis=1).sort_index()
Y=Y.dropna(how="any")
rf=ts("USGG3M_Index.csv","PX_LAST").reindex(Y.index).ffill()
print(f"  curve panel: {len(Y)} obs, {Y.index.min().date()} .. {Y.index.max().date()}, 9 tenors, no NaN")
grid=np.array(sorted(ten))
h=0.25
for tau in (2,5,10,30):
    y_t = Y[tau]
    y_roll = pd.Series(np.interp(tau-h, grid, Y[grid].values), index=Y.index) if False else \
             Y.apply(lambda row: np.interp(tau-h, grid, row.values), axis=1)
    carry = y_t - rf
    roll  = y_t - y_roll
    print(f"  tau={tau:>2}y  carry mean {carry.mean():+5.2f}%  roll/qtr mean {100*roll.mean():+6.1f}bp  "
          f"(sd {100*roll.std():4.1f}bp)  carry>0 {100*(carry>0).mean():4.1f}%")

print("\n  DV01 medians (Bloomberg CONVENTIONAL_CTD_FORWARD_FRSK, $/bp per contract):")
for r in roots:
    d=ts(f"{r}1_Comdty_DV01.csv","CONVENTIONAL_CTD_FORWARD_FRSK")
    print(f"    {r:4s} {d.median():7.3f}   (n={len(d)}, {d.index.min().date()}..{d.index.max().date()})")
