import sys, os, io, contextlib, warnings; warnings.simplefilter("ignore")
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np, pandas as pd
import carry_data as D, carry_signals as S, carry_positions as P, carry_eval as E
buf=io.StringIO()
with contextlib.redirect_stdout(buf):
    import canonical; NS=canonical.load()
RES=os.path.join(os.path.dirname(__file__),"..","results")
pd.set_option("display.width",220)
rets=NS["rets"]; CAL=rets.index; sharpe=NS["sharpe"]; maxdd=NS["maxdd"]
C=S.carry_panel(D.ROOTS).reindex(CAL).ffill()
CC=S.carry_curve_panel(D.ROOTS).reindex(CAL).ffill()
B=pd.read_csv(os.path.join(RES,"_internal","book_returns_full.csv"),index_col=0,parse_dates=True)   # full 25 books; run_experiments.py writes it

SUMMARY = []
print("="*78); print("DIAGNOSTICS"); print("="*78)

print("\n[1] Carry distribution by root (cleaned KMPV, %)")
print((100*C).describe().T[["mean","std","min","25%","50%","75%","max"]].round(3).to_string())

print("\n[2] Signal autocorrelation (KMPV)")
print(pd.DataFrame({f"lag{l}": C.apply(lambda s: s.autocorr(l)) for l in (1,5,21,63)}).round(3).to_string())

SUMMARY += [(f"kmpv_autocorr_lag{l}", r, C[r].autocorr(l)) for l in (1, 63) for r in D.ROOTS]

print("\n[3] Carry through time: mean by year (%)")
print((100*C.groupby(C.index.year).mean()).round(2).to_string())

print("\n[4] Calendar-spread carry vs cash-curve carry (per-root corr of levels)")
print(pd.Series({r: C[r].corr(CC[r]) for r in D.ROOTS}).round(3).to_string())

SUMMARY += [("calendar_vs_cash_curve_corr", r, C[r].corr(CC[r])) for r in D.ROOTS]

print("\n[5] Is the cash-curve carry book STATIC? (weights + turnover)")
pos_cc = P.xs_positions(CC, CAL, D.ROOTS)
chg = pos_cc.diff().abs().sum(axis=1)
print(f"    mean |weight change| per day: {chg.mean():.5f}  (days with any change: {100*(chg>1e-9).mean():.1f}%)")
print("    mean net weight per root:"); print(pos_cc.mean().round(4).to_string())
rk = CC.rank(axis=1, ascending=False)
print("    share of days each root is TOP-2 by cash-curve carry:")
print((100*(rk<=2).mean()).round(1).to_string())

print("\n[6] Sleeve correlations (daily net returns)")
sl = pd.DataFrame({"carry_kmpv":B["A2_carry_xs"],"carry_curve":B["A2_carrycurve_xs"],
                   "momentum":NS["curves"]["DurationMomentum"],
                   "rev_2s10s":NS["curves"]["2s10s_reversion"],
                   "rev_5s30s":NS["curves"]["5s30s_reversion"]}).dropna()
print(sl.corr().round(3).to_string())

SUMMARY += [("top2_share_cash_curve_pct", r, v) for r, v in (100*(rk<=2).mean()).items()]
SUMMARY.append(("a2_carrycurve_xs", "turnover_mean_abs_weight_change", chg.mean()))

print("\n[7] SPANNING REGRESSION  carry ~ momentum + 2s10s + 5s30s   HAC(21)")
for name in ("carry_kmpv","carry_curve"):
    tab,r2,n = E.hac_ols(sl[name], sl[["momentum","rev_2s10s","rev_5s30s"]], lag=21)
    a=tab.loc["alpha"]
    SUMMARY += [(f"spanning_{name}", "alpha_pct_per_yr", 252*a.coef*100), (f"spanning_{name}", "t_hac", a.t_hac),
                (f"spanning_{name}", "r2", r2)]
    print(f"  {name:12s} alpha={a.coef:+.3e}/day ({252*a.coef*100:+.2f}%/yr)  t_HAC={a.t_hac:+.2f}  R2={r2:.3f}  n={n}")
    print("      "+tab.round(3).to_string().replace("\n","\n      "))

print("\n[8] Regime stability: A2 KMPV / curve Sharpe by subperiod")
sub={"2010-2013":("2010-01-01","2013-12-31"),"2014-2017":("2014-01-01","2017-12-31"),
     "2018-2021":("2018-01-01","2021-12-31"),"2022-2026":("2022-01-01","2026-12-31")}
rr=[]
for k,(a,b) in sub.items():
    row={"period":k}
    for nm,s in (("carry_kmpv",B["A2_carry_xs"]),("carry_curve",B["A2_carrycurve_xs"]),
                 ("momentum",NS["curves"]["DurationMomentum"]),("rev_2s10s",NS["curves"]["2s10s_reversion"])):
        row[nm]=round(sharpe(s.loc[a:b]),2)
    rr.append(row)
print(pd.DataFrame(rr).to_string(index=False))

print("\n[9] Cost sensitivity (Sharpe at 1x / 2x / 3x tick cost)")
run=NS["run_strategy"]; tick=NS["tick_frac"]
base=float(np.mean([tick(r) for r in D.ROOTS]))
for nm,car in (("kmpv",C),("curve",CC)):
    out=[]
    for m in (1,2,3):
        p_=P.xs_positions(car,CAL,D.ROOTS)
        out.append(round(sharpe(run(p_[D.ROOTS],rets[D.ROOTS],cost_per_unit=base*m)["net"]),3))
    SUMMARY += [(f"cost_sensitivity_{nm}", f"{m}x", o) for m, o in zip((1, 2, 3), out)]
    print(f"    {nm:6s} 1x={out[0]}  2x={out[1]}  3x={out[2]}")

print("\n[10] Generic 3: confirm never used")
import subprocess
hits=subprocess.run(["grep","-rn","generic=3\\|,3)\\|_Comdty3\\|3_Comdty","carry/src"],capture_output=True,text=True).stdout
print("    references to generic 3 in carry/src:", hits.strip() or "NONE")

sl.corr().round(4).to_csv(os.path.join(RES,"sleeve_correlations.csv"))
pd.DataFrame(rr).to_csv(os.path.join(RES,"regime_stability.csv"),index=False)
pd.DataFrame(SUMMARY, columns=["name","field","value"]).round(4).to_csv(os.path.join(RES,"diagnostics_summary.csv"),index=False)
print("\nwrote sleeve_correlations.csv, regime_stability.csv")
