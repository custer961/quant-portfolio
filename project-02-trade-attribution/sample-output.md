# Trade Log Attribution Report

- Source: `./logs`
- Fills: 417 (duplicate pushes removed: 12)
- Account segments: 2
- Instruments: BP2609, MNQ2609, MNQ2612

## 1. Account level (authoritative: broker equity)

> PnL is taken directly from the client's own equity queries, not re-derived from contract multipliers.

### Account segment 1: 20260713 ~ 20260910

| Metric | Value |
|---|---:|
| Start / end equity | 100,000.00 / 96,353.00 |
| Period PnL | **-3,647.00** |
| Period return | -3.65% |
| Max drawdown | -13.64% (20260806 → 20260910) |
| Trading days | 39 |
| Up / down days | 13 / 24 |
| Best / worst day | 3.72% / -4.88% |
| Days with margin in use | 5 (peak 18,000) |

### Account segment 2: 20260918 ~ 20261018

| Metric | Value |
|---|---:|
| Start / end equity | 100,000.00 / 95,503.00 |
| Period PnL | **-4,497.00** |
| Period return | -4.50% |
| Max drawdown | -5.60% (20260928 → 20261008) |
| Trading days | 13 |
| Up / down days | 3 / 5 |
| Best / worst day | 1.48% / -4.98% |
| Days with margin in use | 1 (peak 18,000) |

**Total PnL: -8,144.00**

## 2. Behaviour (fill statistics)

> Fill records only — no multiplier assumptions, independent of account PnL.

### 1. Overtrading days

- Rule: fills per day > 2x the median across days (7)
- Flagged: **10 days**, 197 fills in total
- Highest: 20260811 (28 fills); 20260825 (26 fills); 20260720 (22 fills); 20260929 (21 fills); 20260731 (19 fills)
- Against equity: mean daily return on flagged days **-0.90%** (3 days) vs **-0.19%** on the rest (9 days)

### 2. Reversal trades

- Rule: an opposite-direction open within 15 minutes of a close
- Flagged: **33**
  - 20260720 19:52:06 close Buy MNQ2609 @29068.75 → reversed to Sell @29071.75 after 4.7 min
  - 20260720 19:52:06 close Buy MNQ2609 @29068.75 → reversed to Sell @29071.75 after 4.7 min
  - 20260721 09:06:19 close Buy MNQ2609 @28898.0 → reversed to Sell @28879.0 after 12.4 min
  - 20260731 21:50:15 close Buy MNQ2609 @28350.25 → reversed to Sell @28338.75 after 10.2 min
  - 20260731 21:52:08 close Buy MNQ2609 @28396.75 → reversed to Sell @28338.75 after 8.4 min

### 3. Adding to a loser

- Rule: same-direction add at a worse price than the current average
- Caveat: no intrabar PnL available; approximated from fill prices
- Flagged: **72**
  - BP2609 Sell add @1.3429 (avg was 1.3383) x1
  - BP2609 Sell add @1.343 (avg was 1.3406) x1
  - BP2609 Sell add @1.3411 (avg was 1.341) x1
  - BP2609 Sell add @1.3411 (avg was 1.341) x1
  - BP2609 Sell add @1.3411 (avg was 1.341) x1
  - BP2609 Sell add @1.3411 (avg was 1.3411) x1

### 4. Forced liquidations

- Flagged: **3**
  - 20260721 MNQ2609 Buy 10 lots @29088.0
  - 20260814 MNQ2609 Sell 1 lots @30236.0
  - 20261008 MNQ2612 Sell 10 lots @31175.25

## 3. Data handling

1. **Duplicate pushes**: the client is configured with two trading servers, so each order is pushed twice. Records are de-duplicated on (date, time, symbol, side, action, quantity, price); 12 removed.
2. **Account switches**: equity jumping back to ~100,000 is treated as a new account and reported as a separate segment.
3. **Log boundary**: positions may exist before the first logged fill and cannot be paired.
4. **PnL basis**: only the client's own equity snapshots are used.

## 4. Limitations & disclaimer

1. Data comes from a simulated trading client's logs, not a live account.
2. Equity is sampled irregularly; the daily value uses the last snapshot of that day.
3. Behaviour flags are heuristic rules and should be reviewed against the raw log.
4. This report describes historical behaviour only and **is not investment advice**.