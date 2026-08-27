"""Is the negative carry result a sign/convention bug, or genuine?

Three independent checks that do not involve any strategy or Sharpe.
"""
import sys, os, io, contextlib, warnings; warnings.simplefilter("ignore")
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np, pandas as pd
import carry_data as D, carry_signals as S
buf=io.StringIO()
with contextlib.redirect_stdout(buf):
    import canonical; NS = canonical.load()
rets = NS["rets"]; CAL = rets.index
C = S.carry_panel(D.ROOTS).reindex(CAL).ffill()
pd.set_option("display.width",200)

print("="*78); print("SIGN / CONVENTION CHECK"); print("="*78)

print("\n[1] Does carry[t] predict the NEXT-month return of the same root?")
print("    (pure predictive test, no positions, no vol scaling, no costs)")
fwd = rets.rolling(21).sum().shift(-21)          # next 21bd return
out=[]
for r in D.ROOTS:
    d = pd.concat([C[r], fwd[r]], axis=1, keys=["c","f"]).dropna()
    ic = d.c.corr(d.f, method="spearman")
    # NW t on the monthly-overlapping mean of sign(carry)*fwd
    pnl = np.sign(d.c)*d.f
    lrv = NS["newey_west_lrv"](pnl.values, 21)
    t = pnl.mean()/np.sqrt(lrv/len(pnl))
    out.append(dict(root=r, n=len(d), spearman_IC=round(ic,4),
                    mean_signed_fwd_bp=round(1e4*pnl.mean(),2), nw_t=round(t,2)))
print(pd.DataFrame(out).to_string(index=False))

print("\n[2] Is cross-sectional carry rank just a DURATION rank in disguise?")
dv = pd.DataFrame({r: D.dv01(r).reindex(CAL).ffill() for r in D.ROOTS})
rc = C.rank(axis=1); rd = dv.rank(axis=1)
per_day = rc.corrwith(rd, axis=1)
print(f"    mean cross-sectional Spearman(carry rank, DV01 rank) = {per_day.mean():+.3f}")
print(f"    share of days with rank corr > +0.5 : {100*(per_day>0.5).mean():.1f}%")
print("    mean carry and median DV01 by root:")
for r in D.ROOTS:
    print(f"      {r:4s} mean carry {100*C[r].mean():+5.2f}%   median DV01 {D.dv01(r).median():6.2f}")

print("\n[3] What is the A2 book actually holding? (average net weight per root)")
import carry_positions as P
pos = P.xs_positions(C, CAL, D.ROOTS)
print(pos.mean().round(4).to_string())
print(f"\n    -> mean DV01-weighted net duration of the book: "
      f"{float((pos*dv).sum(axis=1).mean()):+.3f} $/bp per unit gross")
