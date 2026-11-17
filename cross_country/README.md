# Cross-country rates relative value

Cointegration screen, regime tests and out-of-regime trading across US, German, Japanese and
Canadian government curves. Folded in from the former global-rates-rv repository; the full
write-up is `FINDINGS.md`.

The policy regimes are the same four windows as the curve walk-forward in `../walkforward/`;
`scripts/make_tables.py` stops with an error if they ever differ.

## Running

From this folder:

```bash
pip install -r ../requirements.txt
python scripts/make_tables.py    # results/*.csv
python scripts/make_figures.py   # results/grrv_fig*.png
python scripts/make_diagnostics.py   # results/diagnostics_summary.csv (numbers quoted in FINDINGS.md)
```

Both run offline from the public-data cache in `gr_rv/data/` (US yields from FRED, German
yields from the Bundesbank, Japanese from the Ministry of Finance, Canadian from the Bank of
Canada, FX from the ECB and the Bank of Canada). Set `GRRV_CACHE` to use another cache;
`gr_rv/data_mvp.py` rebuilds it from those sources.

## Layout

```
gr_rv/      loaders (data_mvp), screen and backtest (strategy_mvp), regime tests (subperiod), FX layer
ratslib/    shared statistics, metrics and backtest helpers
scripts/    make_tables.py, make_figures.py
results/    result tables and figures
```
