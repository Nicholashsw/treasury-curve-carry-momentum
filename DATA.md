# Data

## What the notebook expects

A folder (`BBG_CSV`) of daily CSVs, one per security, named by the security stem. Each file has a
`Date` column plus the fields below. Non-trading days omitted. The loader finds a file by globbing
`<stem>*.csv`, so `TY1` resolves `TY1_Comdty.csv` and `USGG2YR` resolves `USGG2YR_Index.csv`.

Only the files in the **Required** table are read by `notebooks/treasury_curve_pipeline.ipynb`.
Everything under **Optional** is produced by the export checklist for later work and is never
opened by this notebook; the pipeline runs without it.

### Required

| Group | Stems | Fields the notebook consumes |
|---|---|---|
| Treasury futures, **front generic only** | `TU1`, `FV1`, `TY1`, `UXY1`, `US1`, `WN1` (`_Comdty.csv`) | `PX_SETTLE`, `FUT_CUR_GEN_TICKER` (the roll map) |
| DV01 side file, one per root | `TU1_Comdty_DV01.csv` … `WN1_Comdty_DV01.csv` | `CONVENTIONAL_CTD_FORWARD_FRSK` |
| Static side file, one per root | `TU1_Comdty_STATIC.csv` … `WN1_Comdty_STATIC.csv` | `FUT_TICK_SIZE` (sets the transaction cost) |
| Cash curve | `USGG3M`, `USGG6M`, `USGG12M`, `USGG2YR`, `USGG3YR`, `USGG5YR`, `USGG7YR`, `USGG10YR`, `USGG20YR`, `USGG30YR` (`_Index.csv`) | `PX_LAST` |
| Rates vol | `MOVE_Index.csv` | `PX_LAST` |

Notes on the required set:

- **Generics 2 and 3** (`TU2`, `TU3`, `FV2`, …) are pulled by `BloombergPull_v6.bas`, but the
  notebook only ever loads generic 1. They are not needed to reproduce the paper.
- `PX_VOLUME` and `OPEN_INT` are present in the futures exports and are loaded into memory, but no
  feature or strategy uses them. Continuous series are built from `PX_SETTLE` plus the roll map.
- Of the ten cash tenors, the strategies use **2Y, 5Y, 10Y and 30Y**. `USGG3M` feeds a 3m10y slope
  feature that no strategy trades. All ten are loaded because the PCA block requires at least five
  tenors; `USGG20YR` only starts 2020-05, which restricts the PCA factors to 2020 onward. Those
  factors are diagnostics and are not traded, so a short 20Y history changes nothing in the
  results table.
- `MOVE_Index.csv` is required to reproduce `results/macro_regime.csv`: without it the `stress`
  state is never assigned.
- `VIX_Index.csv` is loaded by the notebook, but the resulting object is never used.

### Optional — exported by the checklist, not read by this notebook

`FDTR_Index.csv`, `USGGBE10_Index.csv`, fed-funds futures `FF1…FF12_Comdty.csv`, and the
SOFR/OIS/swap curves `USOSFR*`, `USSO*`, `USSW*` (`_Curncy.csv`), plus generics `2`/`3` for every
futures root. These are listed in `bloomberg/EXPORT_CHECKLIST.md` as inputs for the carry and
policy-path work in its research plan; the published pipeline does not open them.

### Static side files

`BloombergPull_v6.bas` writes the contract-chain statics as `<root>1_Comdty_STATIC.csv`
(fields `LAST_TRADEABLE_DT`, `FUT_NOTICE_FIRST`, `FUT_DLV_DT_FIRST`, `FUT_DLV_DT_LAST`,
`FUT_CONT_SIZE`, `FUT_TICK_SIZE`). One file per root; they are **required**, because
`FUT_TICK_SIZE` is what sets the transaction cost. `load_static()` accepts both
`<root>1_STATIC.csv` and `<root>1_Comdty_STATIC.csv`.

## Correction history

**2026-08-23 — transaction costs were not being applied.** `load_static()` previously
globbed only `<root>1_STATIC*.csv`, which never matched the exported
`<root>1_Comdty_STATIC.csv`. No statics loaded, so `tick_frac()` returned `0.0`, and the
series reported as `net` was identical to `gross`. The glob now matches both spellings
and the published table is genuinely net of one tick per contract per side. Full
before/after figures are in the README's
[Correction](README.md#correction-2026-08-23) and [Erratum](README.md#erratum) sections.

## How the original inputs were produced

`bloomberg/BloombergPull_v6.bas` (main exporter, with timeout/retry handling) and
`bloomberg/BloombergDV01.bas` (DV01 exporter), run from Excel on a Bloomberg Terminal, following
`bloomberg/EXPORT_CHECKLIST.md`. Sample: futures calendar 2010-01-04 → 2026-07-06, cash curve
2010-01-01 → 2026-07-07, giving a 4,173-row aligned panel.

## Why the CSVs are not here

They are Bloomberg Terminal data obtained under an institutional licence that does not permit
redistribution. The repository ships everything needed to regenerate them with your own terminal
access; the paper's numbers were re-executed from the original exports on 2026-08-21 and again on
2026-08-23.

## Free-data route

The cash curve is available from FRED. Save each series with a `Date,PX_LAST` header under the
stem the loader expects:

| FRED series | Save as |
|---|---|
| `DGS3MO` | `USGG3M_Index.csv` |
| `DGS6MO` | `USGG6M_Index.csv` |
| `DGS1` | `USGG12M_Index.csv` |
| `DGS2` | `USGG2YR_Index.csv` |
| `DGS3` | `USGG3YR_Index.csv` |
| `DGS5` | `USGG5YR_Index.csv` |
| `DGS7` | `USGG7YR_Index.csv` |
| `DGS10` | `USGG10YR_Index.csv` |
| `DGS20` | `USGG20YR_Index.csv` |
| `DGS30` | `USGG30YR_Index.csv` |

Futures settle and a roll map are needed from a futures data vendor; the notebook reconstructs
continuous series from `PX_SETTLE` and `FUT_CUR_GEN_TICKER` with difference back-adjustment. DV01
can be approximated from the cheapest-to-deliver's modified duration if the Bloomberg field is
unavailable, at some cost to the DV01-neutral hedge precision reported in the paper; the notebook
already falls back to a rolling regression-beta hedge ratio when no `_DV01` file is present.

## Outputs

Running the notebook writes two files into `BBG_RESULTS`: `macro_regime.csv` and
`equity_curves.png`.

`macro_regime.csv` has 4,173 rows, 2010-01-04 → 2026-07-06, with columns `Date`, `move_z`,
`slope`, `slope_chg3m`, `regime`. It is no longer committed, because it is a day-by-day series
computed from the licensed exports: `slope` is the 10Y−2Y yield spread, `slope_chg3m` its
63-day change, `move_z` a 252-day z-score of the MOVE index, and `regime` a three-state label
(`flattening` 1,948 rows / `steepening` 1,454 / `stress` 771).

`results/fig1_signal_contrast.png`, `fig2_equity_curves.png` and `fig3_risk_return.png` are the
publication figures used by the README and the paper. They are committed derived outputs and are
not regenerated by this notebook under those filenames.
