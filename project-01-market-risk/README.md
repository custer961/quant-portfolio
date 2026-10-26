# Market Risk & Performance Report

Generate a risk report for any set of Yahoo Finance symbols — equities, ETFs,
futures, crypto — and compare them side by side.

Zero third-party dependencies (standard library + NumPy).

## Run

### Offline run (no network)

The repo ships a small dataset under sample-data/, so every command below
works without an internet connection — useful for review, and immune to the
upstream API rate-limiting that public market-data endpoints apply.

`ash
python run_html_report.py --symbols ^GSPC QQQ MNQ=F --range 2y \
       --csv-dir sample-data --out sample-report.html
`

CSV files are simply date,close — drop in your own data the same way.


```bash
python run_report.py --symbols "^GSPC" "QQQ" "MNQ=F" --range 2y --out report.md
```

Multiple symbols also produce a correlation matrix and an equal-weight portfolio:

```bash
python run_report.py --symbols "GC=F" "CL=F" "BTC-USD" "TLT" --range 1y
```

Useful symbols:

| Symbol | Instrument |
|---|---|
| `^GSPC` | S&P 500 index |
| `^NDX` | Nasdaq-100 index |
| `QQQ` | Nasdaq-100 ETF |
| `NQ=F` / `MNQ=F` | Nasdaq-100 futures / micro |
| `ES=F` / `MES=F` | S&P 500 futures / micro |
| `GC=F` / `CL=F` | Gold / crude futures |
| `BTC-USD` | Bitcoin |

## HTML report with charts (no plotting library)

`ash
python run_html_report.py --symbols ^GSPC QQQ MNQ=F --range 2y --out report.html
`

One self-contained .html file, charts as inline SVG:

- normalised equity curves (multi-asset)
- drawdown areas with peak-to-trough labels
- monthly return bars
- correlation heatmap

No matplotlib, no CDN, no JavaScript — open it in a browser and print to PDF
to send to a client. sample-report.html is a full example.


## Report styles

Two layouts share the same data and metrics:

- --style classic — dense research-note layout (default)
- --style pro — card-based business-report layout with KPI tiles

`ash
python run_html_report.py --symbols "^GSPC" "QQQ" --csv-dir sample-data \\
       --style pro --out report-pro.html
`

## Output

`sample-output.md` contains a full run. Highlights:

- **Overview table** — total return, CAGR, annualized volatility, Sharpe, Sortino,
  max drawdown, Calmar, and historical daily VaR for every symbol
- **Drawdown detail** — magnitude plus peak and trough dates
- **ASCII equity curves** — quick visual shape check without a plotting dependency
- **Correlation matrix** — daily return correlations across the selected symbols
- **Equal-weight portfolio** — a diversification sanity check

## Metrics: definitions

| Metric | Definition |
|---|---|
| CAGR | `(end/start)^(252/n) - 1` |
| Annualized vol | daily stdev × √252 |
| Sharpe | mean(daily excess) / stdev(daily excess) × √252 |
| Sortino | same, but downside deviation only |
| Max drawdown | worst peak-to-trough decline in close prices |
| Calmar | CAGR / \|max drawdown\| |
| VaR95 | 5th percentile of daily returns (historical simulation) |

## Structure

```
run_report.py            CLI entry point
finance_toolkit/
  core.py                data fetch, caching, parsing, metrics
  report.py              Markdown rendering, ASCII sparklines
sample-report.html       a complete generated HTML report (charts inline)
sample-data/             bundled OHLC-close CSVs for offline runs
```

Design notes:

- Per-symbol failures are isolated — one bad ticker does not abort the run
- Responses are cached under `cache/` so repeated runs are offline-friendly
- `.gitignore` excludes `cache/` and `*.log`

## Limitations — read before trusting the numbers

1. Uses **close prices only**. No intrabar data, no execution modelling.
2. **Transaction costs, slippage, and financing are excluded.** The report says
   so on its face rather than hiding it.
3. Yahoo Finance data is convenient but not a production market data source;
   it can contain gaps, stale values, and adjusted-price quirks.
4. The equal-weight portfolio ignores rebalancing friction.
5. Historical statistics describe the past. **Not investment advice.**
