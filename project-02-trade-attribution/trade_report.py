"""
交易记录归因分析 v2
====================

核心原则
--------
1. **盈亏只信账户权益**：日志里有 `资金查询完成,权益:X` 记录，这是券商口径的真实数字。
   不自己按合约乘数折算美元——那依赖乘数假设，容易算错（v1 就错在这）。
2. **行为只用成交统计**：频次、反向、逆势加仓、强平。这些不需要乘数。
3. **每条结论都能复核**：给出判定规则与原始数据来源。

已知数据特征（都在报告里声明）
------------------------------
- 客户端配置了双交易服务器（41203|41204），同一笔委托会被重复推送，需按完全相同记录去重。
- 日志中存在账户切换（权益重新回到 100,000），需分段统计。
- 日志起始前可能已有持仓。

用法
----
python trade_report.py --log-dir "./logs" --out reports/trade_attribution.md
"""
from __future__ import annotations

import argparse
import glob
import os
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

ENC = "gb18030"

RE_FILL = re.compile(
    r"(?P<t>\d{2}:\d{2}:\d{2}\.\d{3})\s+收到成交:合约\((?P<sym>[^)]+)\),\s*"
    r"(?P<side>[买卖])-(?P<act>开仓|平仓|平今|强平),\s*"
    r"数量\((?P<qty>\d+)\),成交价:(?P<px>[\d.]+)"
)
RE_EQUITY = re.compile(
    r"(?P<t>\d{2}:\d{2}:\d{2}\.\d{3})\s+资金查询完成,权益:(?P<eq>[\d.]+)"
    r"\s+可用:(?P<av>[\d.]+)\s+保证金:(?P<mg>[\d.]+)"
)

CLOSE_ACTS = {"平仓", "平今", "强平"}


@dataclass(frozen=True)
class Fill:
    date: str
    time: str
    symbol: str
    side: str
    action: str
    qty: int
    price: float

    @property
    def is_open(self) -> bool:
        return self.action == "开仓"

    @property
    def is_forced(self) -> bool:
        return self.action == "强平"

    @property
    def ts(self) -> datetime:
        return datetime.strptime(f"{self.date}{self.time.split('.')[0]}", "%Y%m%d%H:%M:%S")

    def key(self) -> tuple:
        return (self.date, self.time, self.symbol, self.side, self.action, self.qty, self.price)


@dataclass(frozen=True)
class Equity:
    date: str
    time: str
    equity: float
    available: float
    margin: float


# ---------------------------------------------------------------- 解析

def _read_lines(log_dir: str):
    for path in sorted(glob.glob(os.path.join(log_dir, "*.log"))):
        name = unicodedata.normalize("NFKC", os.path.basename(path))
        date = name[:8]
        if not date.isdigit():
            continue
        text = Path(path).read_bytes().decode(ENC, errors="replace")
        for line in text.splitlines():
            yield date, line


def parse_fills(log_dir: str) -> tuple[list[Fill], int]:
    """返回 (去重后的成交, 去重掉的条数)。"""
    seen: set[tuple] = set()
    fills: list[Fill] = []
    removed = 0
    for date, line in _read_lines(log_dir):
        m = RE_FILL.search(line)
        if not m:
            continue
        g = m.groupdict()
        f = Fill(date=date, time=g["t"], symbol=g["sym"], side=g["side"],
                 action=g["act"], qty=int(g["qty"]), price=float(g["px"]))
        k = f.key()
        if k in seen:
            removed += 1
            continue
        seen.add(k)
        fills.append(f)
    fills.sort(key=lambda x: x.ts)
    return fills, removed


def parse_equity(log_dir: str) -> list[Equity]:
    rows: list[Equity] = []
    for date, line in _read_lines(log_dir):
        m = RE_EQUITY.search(line)
        if not m:
            continue
        g = m.groupdict()
        rows.append(Equity(date=date, time=g["t"], equity=float(g["eq"]),
                           available=float(g["av"]), margin=float(g["mg"])))
    rows.sort(key=lambda x: (x.date, x.time))
    return rows


def daily_equity(rows: list[Equity]) -> list[Equity]:
    by_day: dict[str, Equity] = {}
    for r in rows:
        by_day[r.date] = r
    return [by_day[d] for d in sorted(by_day)]


def split_accounts(daily: list[Equity], jump: float = 2000.0) -> list[list[Equity]]:
    """相邻交易日权益跳升超过 jump 且回到约 100,000，视为换新账户。"""
    if not daily:
        return []
    segments = [[daily[0]]]
    for prev, cur in zip(daily, daily[1:]):
        reset = (cur.equity - prev.equity > jump) and (abs(cur.equity - 100000.0) < 500.0)
        if reset:
            segments.append([cur])
        else:
            segments[-1].append(cur)
    return segments


# ---------------------------------------------------------------- 账户指标

def max_drawdown(curve: list[float]) -> tuple[float, int, int]:
    peak, peak_i = curve[0], 0
    worst, worst_peak, worst_trough = 0.0, 0, 0
    for i, v in enumerate(curve):
        if v > peak:
            peak, peak_i = v, i
        dd = v / peak - 1.0
        if dd < worst:
            worst, worst_peak, worst_trough = dd, peak_i, i
    return worst, worst_peak, worst_trough


def account_summary(seg: list[Equity]) -> dict:
    curve = [e.equity for e in seg]
    dd, p_i, t_i = max_drawdown(curve)
    rets = [(curve[i] - curve[i - 1]) / curve[i - 1] for i in range(1, len(curve))]
    return {
        "start_date": seg[0].date, "end_date": seg[-1].date,
        "start_equity": curve[0], "end_equity": curve[-1],
        "pnl": curve[-1] - curve[0], "return": curve[-1] / curve[0] - 1.0,
        "max_dd": dd, "dd_peak_date": seg[p_i].date, "dd_trough_date": seg[t_i].date,
        "days": len(seg),
        "up_days": sum(1 for r in rets if r > 0),
        "down_days": sum(1 for r in rets if r < 0),
        "best_day": max(rets) if rets else 0.0,
        "worst_day": min(rets) if rets else 0.0,
        "margin_days": sum(1 for e in seg if e.margin > 0),
        "peak_margin": max(e.margin for e in seg),
    }


# ---------------------------------------------------------------- 行为统计

def detect_overtrading(fills: list[Fill]) -> dict:
    per_day = Counter(f.date for f in fills)
    vals = sorted(per_day.values())
    n = len(vals)
    median = vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2
    thr = median * 2
    hot = {d: c for d, c in per_day.items() if thr > 0 and c > thr}
    return {"median": median, "threshold": thr, "days": hot,
            "count": len(hot), "fills": sum(hot.values())}


def detect_flips(fills: list[Fill], window_min: int = 15) -> dict:
    hits = []
    for i, f in enumerate(fills):
        if f.action not in CLOSE_ACTS:
            continue
        for g in fills[i + 1:]:
            if g.symbol != f.symbol:
                continue
            gap = (g.ts - f.ts).total_seconds() / 60.0
            if gap > window_min:
                break
            if g.is_open and g.side != f.side:
                hits.append((f, g, round(gap, 1)))
                break
    return {"count": len(hits), "examples": hits[:5], "window": window_min}


def detect_chasing(fills: list[Fill]) -> dict:
    """逆势加仓：同方向加仓且新价劣于现有持仓均价（成交价近似）。"""
    pos: dict[str, list] = defaultdict(lambda: [0, 0.0])
    cases = []
    for f in fills:
        p = pos[f.symbol]
        signed = f.qty if f.side == "买" else -f.qty
        if p[0] == 0:
            p[0], p[1] = signed, f.price
            continue
        same = (signed > 0) == (p[0] > 0)
        if not same:
            close_qty = min(abs(p[0]), f.qty)
            p[0] -= close_qty * (1 if p[0] > 0 else -1)
            rem = f.qty - close_qty
            if rem > 0:
                p[0] = -(1 if signed > 0 else -1) * rem
                p[1] = f.price
            elif p[0] == 0:
                p[1] = 0.0
            continue
        worse = (f.price < p[1]) if f.side == "买" else (f.price > p[1])
        if worse:
            cases.append((f.symbol, f.side, round(p[1], 4), f.price, f.qty))
        total = abs(p[0]) + f.qty
        p[1] = (p[1] * abs(p[0]) + f.price * f.qty) / total
        p[0] += signed
    return {"count": len(cases), "examples": cases[:6]}


def detect_forced(fills: list[Fill]) -> dict:
    forced = [f for f in fills if f.is_forced]
    return {"count": len(forced),
            "examples": [(f.date, f.symbol, f.side, f.qty, f.price) for f in forced[:6]]}


def behavior_vs_equity(seg: list[Equity], flags: dict) -> dict:
    changes = {}
    for prev, cur in zip(seg, seg[1:]):
        changes[cur.date] = (cur.equity - prev.equity) / prev.equity
    hot = set(flags["overtrading"]["days"])
    hot_chg = [v for d, v in changes.items() if d in hot]
    rest_chg = [v for d, v in changes.items() if d not in hot]
    return {"overtrading": {
        "hot_n": len(hot_chg),
        "hot_mean": sum(hot_chg) / len(hot_chg) if hot_chg else float("nan"),
        "rest_n": len(rest_chg),
        "rest_mean": sum(rest_chg) / len(rest_chg) if rest_chg else float("nan"),
    }}


# ---------------------------------------------------------------- 报告

def fmt(x, digits: int = 2) -> str:
    if x is None or (isinstance(x, float) and x != x):
        return "—"
    return f"{x:,.{digits}f}"


def pct(x, digits: int = 2) -> str:
    if x is None or (isinstance(x, float) and x != x):
        return "—"
    return f"{x * 100:.{digits}f}%"


STRINGS: dict[str, dict] = {
    "zh": {
        "title": "# 交易记录归因分析报告",
        "b_source": "- 数据来源：`{d}`",
        "b_fills": "- 成交记录：{n} 笔（已去除重复推送 {r} 条）",
        "b_segments": "- 账户段数：{n}",
        "b_symbols": "- 品种：{s}",
        "s_account": "## 一、账户层面（权威口径：账户权益）",
        "note_account": "> 盈亏直接取客户端资金查询的权益值，不按合约乘数折算。",
        "seg": "### 账户段 {i}：{a} ~ {b}",
        "th_metric": "| 指标 | 数值 |",
        "k_start_end": "起始 / 结束权益",
        "k_pnl": "区间盈亏",
        "k_return": "区间收益率",
        "k_mdd": "最大回撤",
        "k_days": "交易日数",
        "k_updown": "上涨 / 下跌天数",
        "k_bestworst": "单日最好 / 最差",
        "k_margin": "有保证金占用天数",
        "total_pnl": "**合计盈亏：{v}**",
        "s_behavior": "## 二、行为层面（成交统计）",
        "note_behavior": "> 只看成交记录，不依赖乘数，与账户盈亏互相独立。",
        "s_over": "### 1. 过度交易日",
        "rule_over": "- 规则：单日成交笔数 > 所有交易日中位数（{m} 笔）的 2 倍",
        "hit_over": "- 命中：**{n} 天**，共 {f} 笔",
        "highest": "- 最高：{s}",
        "vs_equity": "- 与权益对照：过度交易日均日收益 **{h}**（{hn} 天），其余交易日 **{r}**（{rn} 天）",
        "s_flip": "### 2. 反向操作",
        "rule_flip": "- 规则：平仓后 {w} 分钟内开立相反方向仓位",
        "hit_flip": "- 命中：**{n} 次**",
        "ex_flip": "  - {d} {t} 平{s} {sym} @{p} → {g} 分钟后反向开{s2} @{p2}",
        "s_chase": "### 3. 逆势加仓（亏损摊平）",
        "rule_chase": "- 规则：同方向加仓且新价劣于现有持仓均价",
        "note_chase": "- 局限：无盘中浮亏，按成交价近似",
        "hit_chase": "- 命中：**{n} 次**",
        "ex_chase": "  - {sym} {side} 加仓 @{px}（原均价 {avg}）×{q}",
        "s_forced": "### 4. 强制平仓",
        "hit_forced": "- 命中：**{n} 次**",
        "ex_forced": "  - {d} {sym} {side} {q} 手 @{px}",
        "s_data": "## 三、数据处理说明",
        "data1": "1. **重复推送**：客户端配置双交易服务器，同一委托推送两次。按「日期+时间+合约+方向+动作+数量+价格」完全相同去重，去除 {r} 条。",
        "data2": "2. **账户切换**：权益跳回约 100,000 视为新账户，分段统计。",
        "data3": "3. **日志起点**：起始前可能已有持仓，成交配对无法覆盖。",
        "data4": "4. **盈亏口径**：只采信客户端资金查询的权益值。",
        "s_limit": "## 四、局限与声明",
        "limit1": "1. 数据来自模拟交易客户端日志，非实盘。",
        "limit2": "2. 权益为不定期查询快照，日权益取当日最后一条，可能与收盘值有偏差。",
        "limit3": "3. 行为标签为启发式规则判定，需结合原始日志复核。",
        "limit4": "4. 本报告仅描述历史交易特征，**不构成任何投资建议**。",
        "sep": "、",
        "unit_trades": " 笔",
    },
    "en": {
        "title": "# Trade Log Attribution Report",
        "b_source": "- Source: `{d}`",
        "b_fills": "- Fills: {n} (duplicate pushes removed: {r})",
        "b_segments": "- Account segments: {n}",
        "b_symbols": "- Instruments: {s}",
        "s_account": "## 1. Account level (authoritative: broker equity)",
        "note_account": "> PnL is taken directly from the client's own equity queries, not re-derived from contract multipliers.",
        "seg": "### Account segment {i}: {a} ~ {b}",
        "th_metric": "| Metric | Value |",
        "k_start_end": "Start / end equity",
        "k_pnl": "Period PnL",
        "k_return": "Period return",
        "k_mdd": "Max drawdown",
        "k_days": "Trading days",
        "k_updown": "Up / down days",
        "k_bestworst": "Best / worst day",
        "k_margin": "Days with margin in use",
        "total_pnl": "**Total PnL: {v}**",
        "s_behavior": "## 2. Behaviour (fill statistics)",
        "note_behavior": "> Fill records only — no multiplier assumptions, independent of account PnL.",
        "s_over": "### 1. Overtrading days",
        "rule_over": "- Rule: fills per day > 2x the median across days ({m})",
        "hit_over": "- Flagged: **{n} days**, {f} fills in total",
        "highest": "- Highest: {s}",
        "vs_equity": "- Against equity: mean daily return on flagged days **{h}** ({hn} days) vs **{r}** on the rest ({rn} days)",
        "s_flip": "### 2. Reversal trades",
        "rule_flip": "- Rule: an opposite-direction open within {w} minutes of a close",
        "hit_flip": "- Flagged: **{n}**",
        "ex_flip": "  - {d} {t} close {s} {sym} @{p} → reversed to {s2} @{p2} after {g} min",
        "s_chase": "### 3. Adding to a loser",
        "rule_chase": "- Rule: same-direction add at a worse price than the current average",
        "note_chase": "- Caveat: no intrabar PnL available; approximated from fill prices",
        "hit_chase": "- Flagged: **{n}**",
        "ex_chase": "  - {sym} {side} add @{px} (avg was {avg}) x{q}",
        "s_forced": "### 4. Forced liquidations",
        "hit_forced": "- Flagged: **{n}**",
        "ex_forced": "  - {d} {sym} {side} {q} lots @{px}",
        "s_data": "## 3. Data handling",
        "data1": "1. **Duplicate pushes**: the client is configured with two trading servers, so each order is pushed twice. Records are de-duplicated on (date, time, symbol, side, action, quantity, price); {r} removed.",
        "data2": "2. **Account switches**: equity jumping back to ~100,000 is treated as a new account and reported as a separate segment.",
        "data3": "3. **Log boundary**: positions may exist before the first logged fill and cannot be paired.",
        "data4": "4. **PnL basis**: only the client's own equity snapshots are used.",
        "s_limit": "## 4. Limitations & disclaimer",
        "limit1": "1. Data comes from a simulated trading client's logs, not a live account.",
        "limit2": "2. Equity is sampled irregularly; the daily value uses the last snapshot of that day.",
        "limit3": "3. Behaviour flags are heuristic rules and should be reviewed against the raw log.",
        "limit4": "4. This report describes historical behaviour only and **is not investment advice**.",
        "sep": "; ",
        "unit_trades": " fills",
    },
}


SIDE_EN = {"买": "Buy", "卖": "Sell"}


def render(fills, removed, summaries, flags, links, log_dir, lang: str = "zh") -> str:
    T = STRINGS.get(lang, STRINGS["zh"])
    _sd = (lambda x: SIDE_EN.get(x, x)) if lang == "en" else (lambda x: x)
    L: list[str] = [T["title"], ""]
    L += [T["b_source"].format(d=log_dir),
          T["b_fills"].format(n=len(fills), r=removed),
          T["b_segments"].format(n=len(summaries)),
          T["b_symbols"].format(s=", ".join(sorted({f.symbol for f in fills}))), ""]

    L += [T["s_account"], "", T["note_account"], ""]
    for i, s in enumerate(summaries, 1):
        L += [T["seg"].format(i=i, a=s["start_date"], b=s["end_date"]), "",
              T["th_metric"], "|---|---:|",
              f"| {T['k_start_end']} | {fmt(s['start_equity'])} / {fmt(s['end_equity'])} |",
              f"| {T['k_pnl']} | **{fmt(s['pnl'])}** |",
              f"| {T['k_return']} | {pct(s['return'])} |",
              f"| {T['k_mdd']} | {pct(s['max_dd'])} ({s['dd_peak_date']} → {s['dd_trough_date']}) |",
              f"| {T['k_days']} | {s['days']} |",
              f"| {T['k_updown']} | {s['up_days']} / {s['down_days']} |",
              f"| {T['k_bestworst']} | {pct(s['best_day'])} / {pct(s['worst_day'])} |",
              f"| {T['k_margin']} | {s['margin_days']} (peak {fmt(s['peak_margin'], 0)}) |", ""]
    L += [T["total_pnl"].format(v=fmt(sum(s["pnl"] for s in summaries))), ""]

    L += [T["s_behavior"], "", T["note_behavior"], ""]

    ot = flags["overtrading"]
    L += [T["s_over"], "",
          T["rule_over"].format(m=fmt(ot["median"], 0)),
          T["hit_over"].format(n=ot["count"], f=ot["fills"])]
    if ot["days"]:
        top = sorted(ot["days"].items(), key=lambda x: -x[1])[:5]
        L += [T["highest"].format(
            s=T["sep"].join(f"{d} ({c}{T['unit_trades']})" for d, c in top))]
    bv = links.get("overtrading", {})
    if bv.get("hot_n"):
        L += [T["vs_equity"].format(
            h=pct(bv["hot_mean"]), hn=bv["hot_n"],
            r=pct(bv["rest_mean"]), rn=bv["rest_n"])]
    L += [""]

    fl = flags["flips"]
    L += [T["s_flip"], "",
          T["rule_flip"].format(w=fl["window"]),
          T["hit_flip"].format(n=fl["count"])]
    for f, g, gap in fl["examples"]:
        L += [T["ex_flip"].format(d=f.date, t=f.time[:8], s=_sd(f.side), sym=f.symbol,
                                  p=f.price, s2=_sd(g.side), p2=g.price, g=gap)]
    L += [""]

    ch = flags["chasing"]
    L += [T["s_chase"], "", T["rule_chase"], T["note_chase"],
          T["hit_chase"].format(n=ch["count"])]
    for sym, side, avg, px, qty in ch["examples"]:
        L += [T["ex_chase"].format(sym=sym, side=_sd(side), avg=avg, px=px, q=qty)]
    L += [""]

    fo = flags["forced"]
    L += [T["s_forced"], "", T["hit_forced"].format(n=fo["count"])]
    for d, sym, side, qty, px in fo["examples"]:
        L += [T["ex_forced"].format(d=d, sym=sym, side=_sd(side), q=qty, px=px)]
    L += [""]

    L += [T["s_data"], "", T["data1"].format(r=removed), T["data2"], T["data3"], T["data4"], ""]
    L += [T["s_limit"], "", T["limit1"], T["limit2"], T["limit3"], T["limit4"]]
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="交易记录归因分析 v2")
    ap.add_argument("--log-dir", default="./logs")
    ap.add_argument("--lang", default="zh", choices=["zh", "en"])
    ap.add_argument("--source-label", default=None,
                    help="报告中显示的来源名称（默认显示实际目录）")
    ap.add_argument("--out", type=Path, default=Path("reports/trade_attribution.md"))
    args = ap.parse_args(argv)

    fills, removed = parse_fills(args.log_dir)
    daily = daily_equity(parse_equity(args.log_dir))
    segments = split_accounts(daily)
    summaries = [account_summary(seg) for seg in segments]

    flags = {
        "overtrading": detect_overtrading(fills),
        "flips": detect_flips(fills),
        "chasing": detect_chasing(fills),
        "forced": detect_forced(fills),
    }
    links = behavior_vs_equity(segments[-1], flags) if segments else {}

    report = render(fills, removed, summaries, flags, links,
                    args.source_label or args.log_dir, args.lang)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report, encoding="utf-8")

    print(f"成交 {len(fills)} 笔（去重 {removed}）| 权益日 {len(daily)} 天 | 账户段 {len(segments)}")
    for i, s in enumerate(summaries, 1):
        print(f"  段{i} {s['start_date']}~{s['end_date']}: {s['start_equity']:,.2f} -> "
              f"{s['end_equity']:,.2f}  ({s['pnl']:+,.2f})")
    print(f"报告已写入: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
