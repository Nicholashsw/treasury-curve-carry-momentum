"""Read-only access to the immutable Bloomberg export.

Source: the folder named by $BBG_CSV (read-only; never written to).

Two date conventions live in that folder and mixing them silently destroys ~60%
of the sample (see CARRY_FIELD_INVENTORY.md section 0):
  * time series (*_Comdty, *_Index, *_Curncy, *_DV01) -> ISO 'YYYY-MM-DD HH:MM:SS'
  * contract statics (*_STATIC)                       -> 'd/m/yyyy'
"""
import os
import functools
import pandas as pd

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.environ.get("BBG_CSV") or os.path.join(_REPO, "data_raw")
ROOTS = ["TU", "FV", "TY", "UXY", "US", "WN"]

# Curve tenor each futures root is mapped to for the secondary (cash-curve)
# measure. TU/FV are safe; TY/UXY/US/WN are conventions, not observed CTDs.
ROOT_TENOR = {"TU": 2.0, "FV": 5.0, "TY": 7.0, "UXY": 10.0, "US": 20.0, "WN": 25.0}

CURVE = {0.25: "USGG3M", 0.5: "USGG6M", 1.0: "USGG12M", 2.0: "USGG2YR",
         3.0: "USGG3YR", 5.0: "USGG5YR", 7.0: "USGG7YR", 10.0: "USGG10YR",
         30.0: "USGG30YR"}          # USGG20YR excluded: starts 2020-05-21


def _read_ts(fname):
    df = pd.read_csv(os.path.join(SRC, fname))
    df["Date"] = pd.to_datetime(df["Date"], format="%Y-%m-%d %H:%M:%S",
                                errors="coerce")
    return df.dropna(subset=["Date"]).set_index("Date").sort_index()


@functools.lru_cache(maxsize=None)
def futures(root, generic=1):
    """PX_SETTLE / OPEN_INT / FUT_CUR_GEN_TICKER for one generic."""
    return _read_ts(f"{root}{generic}_Comdty.csv")


@functools.lru_cache(maxsize=None)
def dv01(root):
    s = _read_ts(f"{root}1_Comdty_DV01.csv")["CONVENTIONAL_CTD_FORWARD_FRSK"]
    return pd.to_numeric(s, errors="coerce").dropna()


@functools.lru_cache(maxsize=None)
def statics(root):
    """Contract chain. Delivery dates are d/m/yyyy here, unlike the time series."""
    df = pd.read_csv(os.path.join(SRC, f"{root}1_Comdty_STATIC.csv"))
    for c in ["LAST_TRADEABLE_DT", "FUT_NOTICE_FIRST",
              "FUT_DLV_DT_FIRST", "FUT_DLV_DT_LAST"]:
        df[c] = pd.to_datetime(df[c], dayfirst=True, errors="coerce")
    df["KEY"] = (df["CONTRACT"].astype(str)
                 .str.replace(" Comdty", "", regex=False).str.strip())
    return df.set_index("KEY")


@functools.lru_cache(maxsize=None)
def curve():
    """Cash par curve, 9 tenors, no NaN."""
    out = {t: pd.to_numeric(_read_ts(f"{n}_Index.csv")["PX_LAST"], errors="coerce")
           for t, n in CURVE.items()}
    return pd.DataFrame(out).sort_index().dropna(how="any")


@functools.lru_cache(maxsize=None)
def series(name):
    return pd.to_numeric(_read_ts(f"{name}.csv")["PX_LAST"], errors="coerce").dropna()


def delivery_gap_years(root):
    """Actual T2 - T1 in years for each (generic1, generic2) contract pair,
    from the static chain. Never hardcoded at 0.25."""
    g1 = futures(root, 1)["FUT_CUR_GEN_TICKER"].astype(str)
    g2 = futures(root, 2)["FUT_CUR_GEN_TICKER"].astype(str)
    st = statics(root)["FUT_DLV_DT_FIRST"]
    pair = pd.concat([g1, g2], axis=1, keys=["c1", "c2"]).dropna()
    pair = pair[(pair.c1 != "nan") & (pair.c2 != "nan")]
    d1 = pair.c1.map(st)
    d2 = pair.c2.map(st)
    return ((d2 - d1).dt.days / 365.25).rename("dt_years")


def roll_flags(root, generic=1):
    """True on the day the generic re-points to a new dated contract."""
    g = futures(root, generic)["FUT_CUR_GEN_TICKER"].astype(str)
    g = g.where(g.ne("nan"))
    return g.ne(g.shift()) & g.shift().notna() & g.notna()


def roll_window_mask(root, days=3):
    """True inside +/- `days` business days of a generic-1 OR generic-2 roll."""
    r1, r2 = roll_flags(root, 1), roll_flags(root, 2)
    idx = r1.index.union(r2.index)
    r = (r1.reindex(idx, fill_value=False) | r2.reindex(idx, fill_value=False))
    m = r.copy()
    for k in range(1, days + 1):
        m |= r.shift(k, fill_value=False) | r.shift(-k, fill_value=False)
    return m
