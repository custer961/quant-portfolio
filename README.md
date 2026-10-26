# Finance Data & Risk Analytics — Portfolio

Two self-contained Python projects showing the combination clients actually pay for:
**finance-domain understanding** + **clean, runnable engineering**.

Both run with **zero third-party dependencies** (Python standard library + NumPy only),
so a reviewer can clone and run them immediately — no `pip install`, no API keys.
Bundled sample data lets every command run **offline**.

---

## Projects

### 1. [`project-01-market-risk`](project-01-market-risk/) — Market Risk & Performance Report

Pulls daily prices for any Yahoo Finance symbol, computes risk and performance
metrics, and renders the result as Markdown or as a single self-contained HTML file.

**What it demonstrates**

- Data acquisition with caching, per-symbol error isolation, and an offline CSV fallback
- Risk metrics implemented from first principles: CAGR, annualised volatility,
  Sharpe, Sortino, max drawdown with peak/trough dates, Calmar, historical VaR
- Multi-asset comparison: return correlation matrix and an equal-weight portfolio
- **A hand-written SVG chart engine** — equity curves, drawdown areas, monthly
  return bars, correlation heatmap — with no plotting library
- Bilingual output: the same code renders reports in English or Chinese via `--lang`

**Sample output** (real market data, 2 years, English):

```
| Symbol | Total   | CAGR    | Ann. vol | Sharpe | Max DD   | Daily VaR95 |
| ^GSPC  | +31.22% | +14.68% | 16.13%   | 0.93   | -18.90%  | -1.54%      |
| QQQ    | +43.08% | +19.79% | 21.91%   | 0.93   | -22.88%  | -2.03%      |
| MNQ=F  | +41.81% | +19.17% | 22.21%   | 0.90   | -22.50%  | -2.06%      |
```

```bash
cd project-01-market-risk
python run_html_report.py --symbols "^GSPC" "QQQ" "MNQ=F" --range 2y \
       --csv-dir sample-data --out report.html
```

`sample-report.html` is a full rendered example. It also ships A-share data
(`sample-data-cn/`) to show multi-market handling: 600519.SS, 510300.SS, 000001.SZ.

---

### 2. [`project-02-trade-attribution`](project-02-trade-attribution/) — Trade Log Attribution

Parses a trading client's log files, reconstructs the account equity curve, and
diagnoses trading behaviour.

**Why this one is different:** it does **not** invent PnL from contract multipliers.
It reads the broker's own equity snapshots, because that is the only number that
cannot be argued with. Behaviour metrics are computed separately from fill records,
so the two never contaminate each other.

**What it demonstrates**

- Robust parsing of messy, GB18030-encoded, real-world logs
- Handling data defects: duplicate pushes from a dual-server feed, account
  switches that reset equity, and positions opened before the log begins
- Behavioural diagnostics with published rules: overtrading days, reversal
  (flip) trades, adding to losers, forced liquidations
- Cross-checking a derived metric against independent ground truth, and
  **throwing away the first implementation when the check failed**

**Finding from the sample** (two simulated accounts, 417 fills, 52 trading days):

```
| Segment   | Period             | Start     | End       | PnL      |
| Account 1 | 2026-07-13 ~ 09-10 | 100,000 | 96,353    | -3,647   |
| Account 2 | 2026-09-18 ~ 10-18 | 100,000 | 95,503    | -4,497   |
| Total     |                    |         |           | -8,144   |
```

```bash
cd project-02-trade-attribution
python trade_report.py --log-dir ./logs --out report.md
```

`sample-output.md` is a full generated report (English). `--lang zh` produces the
Chinese version; the log-parsing patterns stay in the source language by design.

---

## Design principles

1. **Ground truth over derived numbers.** If the source system states a value,
   use it. Recomputing it introduces assumption risk — this project's first
   implementation got the sign of the PnL wrong for exactly that reason.
2. **Every conclusion is reproducible.** Each behavioural label ships with its
   rule and its limitations, so a reader can re-derive it from raw data.
3. **Zero dependencies.** A reviewer should not have to debug an environment.
4. **State the limits.** Both projects list what they do *not* model
   (transaction costs, intrabar PnL, log gaps). Credibility is built there, not
   in the happy path.
5. **Runs offline.** Bundled CSVs mean a demo never fails because a data API
   is down or a proxy dropped.

## Requirements

- Python 3.10+ (developed on 3.13)
- NumPy (project 1); project 2 uses the standard library only
- Network access only if you skip `--csv-dir` (Yahoo Finance public chart endpoint)

## What I can build for you

- Market data pipelines: scraping, cleaning, aligning, storing
- Strategy backtest implementations with explicit cost and bias handling
- Risk and performance analytics: drawdown, Sharpe/Sortino, VaR, exposure, attribution
- Reporting automation: Excel/VBA → Python, scheduled PDF/HTML reports
- Trade log analysis: reconstruct equity, audit execution, quantify behaviour
- Multi-market coverage, including mainland China A-shares and HK listings

I work in both English and Chinese.

## Scope

These are analytical tools. They do not produce trading signals, and nothing here
is investment advice.
