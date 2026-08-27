import os, pandas as pd, numpy as np
D = os.environ.get("BBG_CSV") or "data_raw"   # set BBG_CSV to your export folder

def load_ts(name):
    """Time-series files use ISO 'YYYY-MM-DD HH:MM:SS'. NEVER dayfirst."""
    df = pd.read_csv(os.path.join(D, name))
    dc = df.columns[0]
    df[dc] = pd.to_datetime(df[dc], format="%Y-%m-%d %H:%M:%S", errors="coerce")
    return df.dropna(subset=[dc]).set_index(dc).sort_index()

def prof(name, col, label=None):
    try:
        df = load_ts(name)
    except Exception as e:
        return dict(file=name, field=col, err=str(e)[:40])
    if col not in df.columns:
        return dict(file=name, field=col, err="MISSING COLUMN")
    s = pd.to_numeric(df[col], errors="coerce")
    nz = s.dropna()
    bd = pd.bdate_range(nz.index.min(), nz.index.max()) if len(nz) else []
    return dict(file=name, field=label or col, rows=len(s), valid=int(s.notna().sum()),
                start=str(nz.index.min().date()) if len(nz) else "-",
                end=str(nz.index.max().date()) if len(nz) else "-",
                pct_miss=round(100*(1-s.notna().mean()), 2),
                bd_cov=round(100*len(nz)/len(bd), 1) if len(bd) else None,
                median=round(float(nz.median()), 4) if len(nz) else None)

rows, roots = [], ["TU","FV","TY","UXY","US","WN"]
for r in roots:
    for g in (1,2,3):
        f = f"{r}{g}_Comdty.csv"
        if os.path.exists(os.path.join(D,f)):
            rows.append(prof(f,"PX_SETTLE")); rows.append(prof(f,"OPEN_INT"))
for r in roots: rows.append(prof(f"{r}1_Comdty_DV01.csv","CONVENTIONAL_CTD_FORWARD_FRSK","DV01"))
for t in ["3M","6M","12M","2YR","3YR","5YR","7YR","10YR","20YR","30YR"]: rows.append(prof(f"USGG{t}_Index.csv","PX_LAST",f"USGG{t}"))
for t in ["A","C","F","1","2","3","5","7","10","30"]: rows.append(prof(f"USOSFR{t}_Curncy.csv","PX_LAST",f"USOSFR{t}"))
for t in ["1","2","3","5","10"]: rows.append(prof(f"USSO{t}_Curncy.csv","PX_LAST",f"USSO{t}"))
for t in ["2","5","10","30"]: rows.append(prof(f"USSW{t}_Curncy.csv","PX_LAST",f"USSW{t}"))
for i in [1,3,6,12]: rows.append(prof(f"FF{i}_Comdty.csv","PX_LAST",f"FF{i}"))
for f,l in [("FDTR_Index.csv","FDTR"),("MOVE_Index.csv","MOVE"),("VIX_Index.csv","VIX"),("USGGBE10_Index.csv","BE10")]: rows.append(prof(f,"PX_LAST",l))

out = pd.DataFrame(rows)
out.to_csv("carry/audit/field_inventory_raw.csv", index=False)
pd.set_option("display.width",210,"display.max_rows",200)
print(out.to_string(index=False))
