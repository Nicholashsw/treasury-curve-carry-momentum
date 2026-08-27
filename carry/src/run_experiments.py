"""Phase 4: experiments A-G under the pre-specified CARRY_RESEARCH_PLAN.md.

Acceptance criteria are hard-coded from the plan and are NOT adjustable here.
"""
import sys, os, io, contextlib, json, warnings
warnings.simplefilter("ignore")
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np, pandas as pd
import carry_data as D, carry_signals as S, carry_positions as P, carry_eval as E

RES = os.path.join(os.path.dirname(__file__), "..", "results")
# Full 25-column book returns stay here (gitignored): downstream final_tests.py
# needs all of them, but only the 7 verification columns below are published.
INTERNAL = os.path.join(RES, "_internal")
FULL_BOOKS = os.path.join(INTERNAL, "book_returns_full.csv")
PUBLIC_BOOKS = os.path.join(RES, "book_returns_daily.csv")
PUBLIC_BOOK_COLS = ["A1_carry_ts", "A2_carry_xs", "A2_carry_xs_noUS", "A2_carry_xs_noWN",
                    "A2_carrycurve_xs", "G_baseline_2sleeve_mom_2s10s", "G_equal_3sleeve"]
os.makedirs(RES, exist_ok=True)
os.makedirs(INTERNAL, exist_ok=True)
pd.set_option("display.width", 220)

buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    import canonical; NS = canonical.load()
run_strategy = NS["run_strategy"]; hedge_ratio = NS["hedge_ratio"]
tick_frac = NS["tick_frac"]; sharpe = NS["sharpe"]; maxdd = NS["maxdd"]
ann_vol = NS["ann_vol"]; dm_test = NS["dm_test"]; reversion_z = NS["reversion_z"]
rets = NS["rets"]; feat = NS["feat"]; curves = NS["curves"]; CAL = rets.index

BASE_MOM = curves["DurationMomentum"]
BASE_2s10s = curves["2s10s_reversion"]
BASE_5s30s = curves["5s30s_reversion"]
BASE_FLY = curves["2s5s10s_fly"]

ROOTS = D.ROOTS
COST_ALL = float(np.mean([tick_frac(r) for r in ROOTS]))

CARRY = S.carry_panel(ROOTS).reindex(CAL).ffill()
CARRY_NOUS = CARRY[[r for r in ROOTS if r != "US"]]
CARRY_CURVE = S.carry_curve_panel(ROOTS).reindex(CAL).ffill()

def book(pos, cols, cost):
    return run_strategy(pos[cols], rets[cols], cost_per_unit=cost)

def stats(net, turn=None, label=""):
    return dict(book=label, sharpe=round(sharpe(net), 3), vol=round(ann_vol(net), 3),
                maxdd=round(100*maxdd(net), 1),
                turnover=round(float(turn.sum()/(len(net)/252)), 1) if turn is not None else np.nan)

def nw_t(x, lag=21):
    x = pd.Series(x).dropna()
    lrv = NS["newey_west_lrv"](x.values, lag)
    return float(x.mean()/np.sqrt(lrv/len(x)))

rows, series_store = [], {}

def record(label, res):
    net = res["net"]; series_store[label] = net
    r = stats(net, res["turnover"], label); r["nw_t"] = round(nw_t(net), 2)
    rows.append(r); return net

# ============================ A. STANDALONE CARRY ==========================
print("="*78); print("A. STANDALONE CARRY"); print("="*78)
A1 = record("A1_carry_ts", book(P.ts_positions(CARRY, CAL, ROOTS), ROOTS, COST_ALL))
A2 = record("A2_carry_xs", book(P.xs_positions(CARRY, CAL, ROOTS), ROOTS, COST_ALL))
nous = [r for r in ROOTS if r != "US"]
A2n = record("A2_carry_xs_noUS", book(P.xs_positions(CARRY_NOUS, CAL, nous), nous, COST_ALL))
nown = [r for r in ROOTS if r != "WN"]
A2w = record("A2_carry_xs_noWN", book(P.xs_positions(CARRY[nown], CAL, nown), nown, COST_ALL))
A2c = record("A2_carrycurve_xs", book(P.xs_positions(CARRY_CURVE, CAL, ROOTS), ROOTS, COST_ALL))
print(pd.DataFrame(rows).to_string(index=False))

# ============================ B. CARRY-CONDITIONED MOMENTUM ================
print("\n" + "="*78); print("B. CARRY-CONDITIONED DURATION MOMENTUM"); print("="*78)
mom_raw = np.sign(rets.rolling(63).sum())
agree = (np.sign(CARRY[ROOTS].reindex(CAL).ffill()) == mom_raw[ROOTS])
B1 = record("B1_mom_gated", book(mom_raw[ROOTS].where(agree, 0.0), ROOTS, COST_ALL))
B2 = record("B2_mom_tilted", book(mom_raw[ROOTS]*(0.5+0.5*agree.astype(float)), ROOTS, COST_ALL))
print(pd.DataFrame(rows[-2:]).to_string(index=False))

# ============================ C. CARRY-CONDITIONED CURVE RV ================
print("\n" + "="*78); print("C. CARRY-CONDITIONED CURVE MEAN REVERSION"); print("="*78)
def curve_carry(long_r, short_r, hr):
    return (CARRY[long_r] - hr*CARRY[short_r]).reindex(CAL).ffill()

def curve_book(long_r, short_r, tl, ts_, sig_fn, label):
    hr = hedge_ratio(short_r, ts_, long_r, tl)
    cc = curve_carry(long_r, short_r, hr)
    s = sig_fn(cc)
    sig = pd.DataFrame({long_r: s, short_r: -s*hr})
    c = float(np.mean([tick_frac(short_r), tick_frac(long_r)]))
    return record(label, book(sig, [long_r, short_r], c)), cc

rev2 = reversion_z(feat["s2s10"]); rev5 = reversion_z(feat["s5s30"])
_, cc2 = curve_book("TY","TU","USGG10YR","USGG2YR",
                    lambda cc: rev2.where(np.sign(rev2)==np.sign(cc), 0.0), "C1_2s10s_gated")
_, cc5 = curve_book("US","FV","USGG30YR","USGG5YR",
                    lambda cc: rev5.where(np.sign(rev5)==np.sign(cc), 0.0), "C1_5s30s_gated")
for lam in (0.25, 0.5, 1.0):
    zc2 = (cc2 - cc2.rolling(252,min_periods=60).mean().shift(1))/cc2.rolling(252,min_periods=60).std().shift(1)
    curve_book("TY","TU","USGG10YR","USGG2YR",
               lambda cc, l=lam, z=zc2: (rev2 + l*z.clip(-3,3)).shift(0), f"C2_2s10s_tilt{lam}")
    zc5 = (cc5 - cc5.rolling(252,min_periods=60).mean().shift(1))/cc5.rolling(252,min_periods=60).std().shift(1)
    curve_book("US","FV","USGG30YR","USGG5YR",
               lambda cc, l=lam, z=zc5: (rev5 + l*z.clip(-3,3)).shift(0), f"C2_5s30s_tilt{lam}")
print(pd.DataFrame(rows[-8:]).to_string(index=False))

# ============================ D. BUTTERFLY =================================
print("\n" + "="*78); print("D. CARRY ON THE BUTTERFLY"); print("="*78)
ha = hedge_ratio("FV","USGG5YR","TU","USGG2YR"); hb = hedge_ratio("FV","USGG5YR","TY","USGG10YR")
ccf = (2*CARRY["FV"] - ha*CARRY["TU"] - hb*CARRY["TY"]).reindex(CAL).ffill()
cfly = float(np.mean([tick_frac(r) for r in ("FV","TU","TY")]))
sfly = np.sign(ccf)
record("D1_fly_carry", book(pd.DataFrame({"FV":2*sfly,"TU":-sfly*ha,"TY":-sfly*hb}), ["FV","TU","TY"], cfly))
revf = reversion_z(feat["fly2510"])
sg = revf.where(np.sign(revf)==np.sign(ccf), 0.0)
record("D2_fly_gated", book(pd.DataFrame({"FV":2*sg,"TU":-sg*ha,"TY":-sg*hb}), ["FV","TU","TY"], cfly))
print(pd.DataFrame(rows[-2:]).to_string(index=False))

# ============================ E/F/G. PORTFOLIOS ============================
print("\n" + "="*78); print("E/F/G. MULTI-SLEEVE PORTFOLIOS"); print("="*78)
TARGET_VOL = 0.10
def blend(parts, weights, label):
    """Scale every sleeve to a COMMON 10% annualised vol before blending, then
    re-scale the blend to 10%, so Sharpe AND drawdown are comparable across books."""
    d = pd.concat(parts, axis=1).dropna()
    k = TARGET_VOL/np.sqrt(252)
    scaled = [d.iloc[:,i]/d.iloc[:,i].std()*k for i in range(d.shape[1])]
    b = sum(w*s for w, s in zip(weights, scaled))
    b = b/b.std()*k
    series_store[label] = b
    rows.append(dict(book=label, sharpe=round(sharpe(b),3), vol=round(ann_vol(b),3),
                     maxdd=round(100*maxdd(b),1), turnover=np.nan, nw_t=round(nw_t(b),2)))
    return b

CARRYBOOK = A2
for w in [(0.25,0.75),(0.5,0.5),(0.75,0.25)]:
    blend([CARRYBOOK, BASE_MOM], w, f"E_carry{int(w[0]*100)}_mom{int(w[1]*100)}")
    blend([CARRYBOOK, BASE_2s10s], w, f"F_carry{int(w[0]*100)}_2s10s{int(w[1]*100)}")
G = blend([CARRYBOOK, BASE_MOM, BASE_2s10s], (1/3,1/3,1/3), "G_equal_3sleeve")
G2 = blend([BASE_MOM, BASE_2s10s], (0.5,0.5), "G_baseline_2sleeve_mom_2s10s")
print(pd.DataFrame([r for r in rows if r["book"].startswith(("E_","F_","G_"))]).to_string(index=False))

res = pd.DataFrame(rows)
res.to_csv(os.path.join(RES,"experiments_A_to_G.csv"), index=False)
books = pd.DataFrame(series_store)
books.to_csv(FULL_BOOKS)                                   # internal, all 25 books
# Projection at write time only. Nothing above depends on this narrowing, and the
# committed file must round-trip byte-identically on every rerun.
books[PUBLIC_BOOK_COLS].round(10).to_csv(PUBLIC_BOOKS, float_format="%.10g")
CARRY.to_csv(os.path.join(RES,"carry_signal_kmpv.csv"))
CARRY_CURVE.to_csv(os.path.join(RES,"carry_signal_curve.csv"))
print("\nwrote carry/results/experiments_A_to_G.csv, book_returns_daily.csv (7 public\ncolumns) and carry/results/_internal/book_returns_full.csv (all 25, gitignored)")
