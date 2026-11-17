import sys, os, io, contextlib, warnings; warnings.simplefilter("ignore")
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np, pandas as pd, carry_data as D, carry_eval as E
buf=io.StringIO()
with contextlib.redirect_stdout(buf):
    import canonical; NS=canonical.load()
RES=os.path.join(os.path.dirname(__file__),"..","results"); pd.set_option("display.width",220)
sharpe=NS["sharpe"]; maxdd=NS["maxdd"]; dm=NS["dm_test"]
B=pd.read_csv(os.path.join(RES,"_internal","book_returns_full.csv"),index_col=0,parse_dates=True)   # full 25 books; run_experiments.py writes it
MOM=NS["curves"]["DurationMomentum"]; R2=NS["curves"]["2s10s_reversion"]
R5=NS["curves"]["5s30s_reversion"]; FLY=NS["curves"]["2s5s10s_fly"]

print("="*78); print("PRE-SPECIFIED TESTS"); print("="*78)
tests=[]
def T(label, alt, base, bname):
    st,p,edge,lag,n = dm(base, alt)
    tests.append(dict(test=label, vs=bname, dm=round(st,3), p=round(p,4),
                      ann_edge=round(100*edge,2), sharpe_alt=round(sharpe(alt),3),
                      sharpe_base=round(sharpe(base),3)))
T("A1_carry_ts", B["A1_carry_ts"], MOM, "momentum")
T("A2_carry_xs", B["A2_carry_xs"], MOM, "momentum")
T("A2_carrycurve_xs", B["A2_carrycurve_xs"], MOM, "momentum")
T("B1_mom_gated", B["B1_mom_gated"], MOM, "momentum")
T("B2_mom_tilted", B["B2_mom_tilted"], MOM, "momentum")
T("C1_2s10s_gated", B["C1_2s10s_gated"], R2, "2s10s")
T("C2_2s10s_tilt0.25", B["C2_2s10s_tilt0.25"], R2, "2s10s")
T("C2_2s10s_tilt0.5", B["C2_2s10s_tilt0.5"], R2, "2s10s")
T("C2_2s10s_tilt1.0", B["C2_2s10s_tilt1.0"], R2, "2s10s")
T("C1_5s30s_gated", B["C1_5s30s_gated"], R5, "5s30s")
T("C2_5s30s_tilt0.25", B["C2_5s30s_tilt0.25"], R5, "5s30s")
T("C2_5s30s_tilt0.5", B["C2_5s30s_tilt0.5"], R5, "5s30s")
T("C2_5s30s_tilt1.0", B["C2_5s30s_tilt1.0"], R5, "5s30s")
T("D1_fly_carry", B["D1_fly_carry"], FLY, "butterfly")
T("D2_fly_gated", B["D2_fly_gated"], FLY, "butterfly")
T("G_equal_3sleeve", B["G_equal_3sleeve"], B["G_baseline_2sleeve_mom_2s10s"], "2sleeve_baseline")
t=pd.DataFrame(tests)
t["fdr_pass_5pct"]=E.bh_fdr(t.p.values, 0.05)
print(t.to_string(index=False))
print(f"\n  DM tests run: {len(t)}   passing BH-FDR at 5%: {int(t.fdr_pass_5pct.sum())}")

print("\n=== BOOTSTRAP: incremental Sharpe, 3-sleeve vs 2-sleeve baseline ===")
lo,md,hi = E.stationary_bootstrap_sharpe_diff(B["G_equal_3sleeve"], B["G_baseline_2sleeve_mom_2s10s"])
print(f"  Sharpe(3-sleeve) - Sharpe(2-sleeve) = {sharpe(B['G_equal_3sleeve'])-sharpe(B['G_baseline_2sleeve_mom_2s10s']):+.3f}")
print(f"  stationary block bootstrap 95% CI: [{lo:+.3f}, {hi:+.3f}]  median {md:+.3f}")
print(f"  CI excludes zero: {not (lo<0<hi)}")
print(f"  max drawdown  3-sleeve {100*maxdd(B['G_equal_3sleeve']):.1f}%   2-sleeve {100*maxdd(B['G_baseline_2sleeve_mom_2s10s']):.1f}%")

print("\n=== BOOTSTRAP: best carry-blend (F 25/75) vs 2s10s alone ===")
lo2,md2,hi2 = E.stationary_bootstrap_sharpe_diff(B["F_carry25_2s10s75"], R2)
print(f"  diff {sharpe(B['F_carry25_2s10s75'])-sharpe(R2):+.3f}  CI [{lo2:+.3f}, {hi2:+.3f}]  excludes zero: {not (lo2<0<hi2)}")

print("\n=== ROOT CONTRIBUTIONS to the A2 KMPV book (mean daily bp) ===")
import carry_signals as S, carry_positions as P
CAL=NS["rets"].index; C=S.carry_panel(D.ROOTS).reindex(CAL).ffill()
pos=P.xs_positions(C,CAL,D.ROOTS)
contrib=(pos.shift(1)*NS["rets"][D.ROOTS]).mean()*1e4
print(contrib.round(3).to_string())

t.to_csv(os.path.join(RES,"dm_tests.csv"),index=False)
print("\nwrote dm_tests.csv")

pd.DataFrame([("bootstrap_3sleeve_vs_2sleeve", "sharpe_diff", sharpe(B["G_equal_3sleeve"]) - sharpe(B["G_baseline_2sleeve_mom_2s10s"])),
              ("bootstrap_3sleeve_vs_2sleeve", "ci_low", lo), ("bootstrap_3sleeve_vs_2sleeve", "ci_high", hi),
              ("bootstrap_3sleeve_vs_2sleeve", "median", md),
              ("bootstrap_F_vs_2s10s", "sharpe_diff", sharpe(B["F_carry25_2s10s75"]) - sharpe(R2)),
              ("bootstrap_F_vs_2s10s", "ci_low", lo2), ("bootstrap_F_vs_2s10s", "ci_high", hi2),
              ("dm_tests", "n_tests", len(t)), ("dm_tests", "n_fdr_pass", int(t["fdr_pass_5pct"].sum()))],
             columns=["name", "field", "value"]).round(4).to_csv(os.path.join(RES, "bootstrap_summary.csv"), index=False)
