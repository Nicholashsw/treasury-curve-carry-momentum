"""Evaluation utilities: bootstrap, spanning regression, FDR.
DM / HAC come from the canonical notebook namespace, never re-implemented."""
import numpy as np, pandas as pd


def stationary_bootstrap_sharpe_diff(a, b, n=1000, mean_block=63, seed=7):
    """Stationary block bootstrap CI for Sharpe(a) - Sharpe(b)."""
    rng = np.random.default_rng(seed)
    d = pd.concat([a, b], axis=1).dropna()
    x, y = d.iloc[:, 0].to_numpy(), d.iloc[:, 1].to_numpy()
    T = len(x); p = 1.0 / mean_block
    out = np.empty(n)
    for k in range(n):
        idx = np.empty(T, dtype=int); i = rng.integers(T)
        for t in range(T):
            idx[t] = i
            i = rng.integers(T) if rng.random() < p else (i + 1) % T
        xs, ys = x[idx], y[idx]
        sa = np.sqrt(252)*xs.mean()/xs.std() if xs.std() > 0 else np.nan
        sb = np.sqrt(252)*ys.mean()/ys.std() if ys.std() > 0 else np.nan
        out[k] = sa - sb
    return np.nanpercentile(out, [2.5, 50, 97.5])


def hac_ols(y, X, lag=21):
    """OLS with Newey-West HAC errors. Returns params, tstats, r2."""
    import numpy.linalg as la
    d = pd.concat([y, X], axis=1).dropna()
    yy = d.iloc[:, 0].to_numpy()
    XX = np.column_stack([np.ones(len(d)), d.iloc[:, 1:].to_numpy()])
    b = la.lstsq(XX, yy, rcond=None)[0]
    e = yy - XX @ b
    n, k = XX.shape
    S = (XX * e[:, None]).T @ (XX * e[:, None])
    for L in range(1, lag + 1):
        w = 1.0 - L / (lag + 1.0)
        G = (XX[L:] * e[L:, None]).T @ (XX[:-L] * e[:-L, None])
        S += w * (G + G.T)
    XtXi = la.inv(XX.T @ XX)
    V = XtXi @ S @ XtXi
    se = np.sqrt(np.diag(V))
    r2 = 1 - e.var() / yy.var()
    names = ["alpha"] + list(d.columns[1:])
    return pd.DataFrame({"coef": b, "t_hac": b / se}, index=names), r2, len(d)


def bh_fdr(pvals, q=0.05):
    p = np.asarray(pvals, float); m = len(p)
    order = np.argsort(p); ranked = p[order]
    thresh = q * (np.arange(1, m + 1) / m)
    passed = ranked <= thresh
    kmax = np.max(np.where(passed)[0]) + 1 if passed.any() else 0
    out = np.zeros(m, bool)
    if kmax: out[order[:kmax]] = True
    return out
