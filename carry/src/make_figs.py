import sys, os, io, contextlib, warnings; warnings.simplefilter("ignore")
sys.path.insert(0, os.path.dirname(__file__))
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt, numpy as np, pandas as pd
import carry_data as D, carry_signals as S
buf=io.StringIO()
with contextlib.redirect_stdout(buf):
    import canonical; NS=canonical.load()
RES=os.path.join(os.path.dirname(__file__),"..","results")
FIG=os.path.join(os.path.dirname(__file__),"..","figs"); os.makedirs(FIG,exist_ok=True)
plt.rcParams.update({"figure.dpi":170,"savefig.dpi":170,"font.size":10,
    "axes.spines.top":False,"axes.spines.right":False,"axes.grid":True,
    "grid.alpha":.25,"axes.titlesize":12,"axes.titleweight":"bold","legend.frameon":False})
RED,GRN,BLU,ORG,GRY,PUR="#c0392b","#1e8449","#1f5f8b","#d97706","#8a8a99","#6c3483"
CAL=NS["rets"].index; C=S.carry_panel(D.ROOTS).reindex(CAL).ffill()
B=pd.read_csv(os.path.join(RES,"_internal","book_returns_full.csv"),index_col=0,parse_dates=True)   # full 25 books; run_experiments.py writes it
def eq(s): return (1+pd.Series(s).fillna(0)).cumprod()
def save(f,n): f.savefig(os.path.join(FIG,n),bbox_inches="tight",facecolor="white"); plt.close(f); print("saved",n)

# 1. the US episode, before/after cleaning
raw=S.carry_panel(D.ROOTS,apply_guard=False,apply_winsor=False,roll_days=0)
fig,ax=plt.subplots(1,2,figsize=(11,3.8))
for a,(P,t) in zip(ax,[(raw,"Before cleaning"),(C,"After CTD guard + roll mask + winsor")]):
    for r,c in zip(D.ROOTS,[BLU,GRN,ORG,PUR,RED,GRY]):
        a.plot(100*P[r],lw=.8,color=c,label=r,alpha=.85)
    a.set_title(t); a.set_ylabel("annualised carry (%)"); a.axhline(0,color="k",lw=.6)
ax[0].axvspan(pd.Timestamp("2014-12-22"),pd.Timestamp("2015-03-20"),color=RED,alpha=.15)
ax[0].annotate("US CTD migration\n2014-12 → 2015-03",xy=(pd.Timestamp("2015-02-01"),-30),
               fontsize=8,color=RED,ha="center")
ax[1].legend(ncol=6,fontsize=8,loc="lower center")
save(fig,"carry_fig1_signal_cleaning.png")

# 2. distribution by root
fig,ax=plt.subplots(figsize=(7,3.6))
ax.boxplot([100*C[r].dropna() for r in D.ROOTS],labels=D.ROOTS,showfliers=False)
ax.axhline(0,color=GRY,lw=.8); ax.set_ylabel("annualised carry (%)")
ax.set_title("Calendar-spread carry by root (cleaned)")
save(fig,"carry_fig2_distribution.png")

# 3. equity curves
fig,ax=plt.subplots(figsize=(9,4.4))
for k,c,l in [("A2_carry_xs",RED,"Carry (KMPV, primary)"),("A2_carrycurve_xs",ORG,"Carry (cash-curve, secondary)")]:
    ax.plot(eq(B[k]),color=c,lw=1.8,label=f"{l}  ({NS['sharpe'](B[k]):.2f})")
ax.plot(eq(NS["curves"]["DurationMomentum"]),color=BLU,lw=1.8,label=f"Duration momentum  ({NS['sharpe'](NS['curves']['DurationMomentum']):.2f})")
ax.plot(eq(NS["curves"]["2s10s_reversion"]),color=GRN,lw=1.8,label=f"2s10s reversion  ({NS['sharpe'](NS['curves']['2s10s_reversion']):.2f})")
ax.axhline(1,color=GRY,lw=.8); ax.set_ylabel("cumulative net return (×)")
ax.set_title("Carry books vs the frozen canonical sleeves"); ax.legend(loc="upper left")
save(fig,"carry_fig3_equity.png")

# 4. portfolio: does carry help?
fig,ax=plt.subplots(figsize=(8,4))
ax.plot(eq(B["G_baseline_2sleeve_mom_2s10s"]),color=BLU,lw=2,label=f"2 sleeves: mom + 2s10s  (0.87, DD -15.1%)")
ax.plot(eq(B["G_equal_3sleeve"]),color=RED,lw=2,label=f"3 sleeves: + carry  (0.71, DD -21.1%)")
ax.axhline(1,color=GRY,lw=.8); ax.set_ylabel("cumulative net return (×)")
ax.set_title("Adding carry as a third sleeve (both at 10% vol)"); ax.legend(loc="upper left")
save(fig,"carry_fig4_portfolio.png")

# (No sleeve-correlation heatmap. A 5x5 matrix is read more precisely from the
# table in CARRY_RESULTS.md section 4, whose source is results/sleeve_correlations.csv.)

# 6. regime stability
rs=pd.read_csv(os.path.join(RES,"regime_stability.csv"))
fig,ax=plt.subplots(figsize=(8,3.8))
x=np.arange(len(rs)); w=.2
for i,(c,col) in enumerate(zip(["carry_kmpv","carry_curve","momentum","rev_2s10s"],[RED,ORG,BLU,GRN])):
    ax.bar(x+(i-1.5)*w,rs[c],w,label=c,color=col)
ax.set_xticks(x); ax.set_xticklabels(rs.period); ax.axhline(0,color="k",lw=.8)
ax.set_ylabel("Sharpe"); ax.set_title("Subperiod stability"); ax.legend(ncol=4,fontsize=8)
save(fig,"carry_fig6_regimes.png")
