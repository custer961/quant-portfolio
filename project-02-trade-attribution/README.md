# Trade Log Attribution

Turn a trading client's raw log files into an honest read on **what the account
actually did** — and on **how the trader behaved while doing it**.

Standard library only. No dependencies.

## Run

```bash
python trade_report.py --log-dir ./logs --out report.md
```

The log directory is expected to contain `YYYYMMDD.log` files encoded in
GB18030, as produced by the trading client.

## The design decision that matters

The first version of this tool computed PnL by multiplying price differences by
each contract's standard multiplier. It reported a **profit**.

The account's own equity snapshots said otherwise.

So the tool was rebuilt around a single rule:

> **PnL comes only from the broker's equity records.**
> Everything else is behaviour statistics, computed independently from fills.

That separation is the point. A derived number can be wrong in ways you cannot
see from the output alone; the account balance cannot.

## What it handles

Real client logs are messy. This parser deals with:

| Problem | Handling |
|---|---|
| Duplicate push from a dual-server feed | Deduplicate on the full fill tuple; report how many were dropped |
| Account switches (equity resets to 100,000) | Detect the jump, split into segments, report each separately |
| Positions opened before the log window | Not silently invented — flagged as a data boundary |
| Encode variance | Decode as GB18030 with replacement, then parse |

## Diagnostics

Every label ships with its rule so a reader can re-derive it.

| Label | Rule |
|---|---|
| Overtrading day | fills per day > 2× the median across days |
| Reversal trade | an opposite-direction open within 15 minutes of a close |
| Adding to a loser | same-direction add at a worse price than the current average |
| Forced liquidation | fill type is a forced close |

The overtrading label is cross-referenced against the equity curve: mean daily
return on flagged days versus the rest. That turns a behavioural claim into a
measurable one.

## Sample output

`sample-output.md` is generated from a real simulated trading account
(417 fills, 52 trading days, two account segments):

```
| Segment  | Period              | Start   | End     | PnL    |
| Account 1 | 2026-07-13 ~ 09-10 | 100,000 | 96,353  | -3,647 |
| Account 2 | 2026-09-18 ~ 10-18 | 100,000 | 95,503  | -4,497 |
| Total     |                    |         |         | -8,144 |
```

Names and dates are from a simulated account; no live account data is included.

## Limitations

1. Equity is sampled irregularly — daily equity uses the last snapshot of that
   day, which may differ from a true closing balance.
2. Logs contain no intrabar prices, so unrealised PnL between snapshots cannot
   be attributed.
3. Behaviour labels are heuristics. They identify patterns worth reviewing, not
   proven causes.
4. Fees, spreads, and slippage are whatever the broker already netted into
   equity — they are not modelled separately.
5. Descriptive only. **Not investment advice.**

## Why this is useful to a client

Most traders cannot answer "where does my money actually go?" beyond a P&L
number. This tool separates three things that are usually tangled together:

- the account's true result (equity)
- the behavioural patterns that produced it (fills)
- the data defects that would otherwise corrupt both (dedup, segments, boundaries)
