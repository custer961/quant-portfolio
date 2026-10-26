"""
finance_toolkit.report — 把指标渲染成 Markdown 报告。

报告结构：
1. 概览表（多品种横向对比）
2. 每个品种的最大回撤区间
3. 相关性矩阵
4. 等权组合对照
5. 净值迷你曲线（ASCII）

设计上刻意保持纯文本输出，方便直接贴进 Markdown 文档或邮件。
"""
from __future__ import annotations

import math
from typing import Sequence

import numpy as np

from .core import (
    Series,
    compute_metrics,
    equal_weight_portfolio,
    return_correlation,
    to_dict,
)

_BLOCKS = "▁▂▃▄▅▆▇█"


def _pct(x: float, digits: int = 2) -> str:
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return "—"
    return f"{x * 100:.{digits}f}%"


def _num(x: float, digits: int = 2) -> str:
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return "—"
    return f"{x:.{digits}f}"


def sparkline(values: Sequence[float], width: int = 60) -> str:
    """把价格序列压成一行 ASCII 曲线。"""
    arr = np.asarray(values, dtype=float)
    if arr.size == 0:
        return ""
    if arr.size > width:
        idx = np.linspace(0, arr.size - 1, width).astype(int)
        arr = arr[idx]
    lo, hi = float(np.min(arr)), float(np.max(arr))
    if hi == lo:
        return _BLOCKS[0] * len(arr)
    scaled = (arr - lo) / (hi - lo) * (len(_BLOCKS) - 1)
    return "".join(_BLOCKS[int(round(v))] for v in scaled)


def render_report(series_list: list[Series], rf: float = 0.0,
                  title: str = "风险与绩效报告") -> str:
    """生成完整的 Markdown 报告文本。"""
    metrics = [compute_metrics(s, rf) for s in series_list]
    lines: list[str] = [f"# {title}", ""]

    if metrics:
        lines += [
            f"- 数据区间：`{metrics[0]['start']}` ~ `{metrics[0]['end']}`",
            f"- 品种数：{len(metrics)}",
            "- 无风险利率（年化）：" + _pct(rf),
            "",
            "## 概览",
            "",
            "| 品种 | 交易日 | 累计收益 | 年化收益 | 年化波动 | 夏普 | 索提诺 | 最大回撤 | Calmar | 日 VaR95 |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
        for m in metrics:
            lines.append(
                f"| {m['symbol']} | {m['bars']} | {_pct(m['total_return'])} | {_pct(m['cagr'])} "
                f"| {_pct(m['ann_vol'])} | {_num(m['sharpe'])} | {_num(m['sortino'])} "
                f"| {_pct(m['max_drawdown'])} | {_num(m['calmar'])} | {_pct(m['var95_daily'])} |"
            )
        lines.append("")

        lines += ["## 最大回撤明细", "", "| 品种 | 幅度 | 峰值日 | 谷底日 |", "|---|---:|---|---|"]
        for m in metrics:
            lines.append(
                f"| {m['symbol']} | {_pct(m['max_drawdown'])} | {m['mdd_peak_date']} | {m['mdd_trough_date']} |"
            )
        lines.append("")

        lines += ["## 净值曲线（归一化，ASCII）", ""]
        for s in series_list:
            lines += [f"**{s.symbol}**", "", "```", sparkline(s.closes), "```", ""]

    # 相关性矩阵
    if len(series_list) >= 2:
        try:
            corr = return_correlation(series_list)
            names = [s.symbol for s in series_list]
            lines += ["## 日收益相关性矩阵", ""]
            header = "| |" + "|".join(f" {n} " for n in names) + "|"
            sep = "|---|" + "|".join("---:" for _ in names) + "|"
            lines += [header, sep]
            for i, n in enumerate(names):
                cells = "|".join(f" {corr[i, j]:.2f} " for j in range(len(names)))
                lines.append(f"| **{n}** |{cells}|")
            lines.append("")

            lines += ["## 等权组合对照", ""]
            ew = equal_weight_portfolio(series_list)
            ew_m = compute_metrics(ew, rf)
            lines += [
                "| 组合 | 累计收益 | 年化收益 | 年化波动 | 夏普 | 最大回撤 |",
                "|---|---:|---:|---:|---:|---:|",
                f"| 等权组合 | {_pct(ew_m['total_return'])} | {_pct(ew_m['cagr'])} "
                f"| {_pct(ew_m['ann_vol'])} | {_num(ew_m['sharpe'])} | {_pct(ew_m['max_drawdown'])} |",
                "",
                "> 等权组合仅作分散化效果的快速对照，未计交易成本与再平衡摩擦。",
                "",
            ]
        except ValueError as exc:
            lines += [f"> 相关性计算跳过：{exc}", ""]

    lines += [
        "---",
        "",
        "**方法说明**",
        "",
        "- 年化采用 252 个交易日；波动率为日收益标准差 × √252",
        "- 夏普 / 索提诺使用日收益，按 √252 年化，超额收益扣除无风险利率",
        "- 最大回撤基于收盘价的历史峰值回撤",
        "- VaR 为历史模拟法，取日收益分布的分位数",
        "",
        "**局限**",
        "",
        "- 仅基于收盘价，未计交易成本、滑点、融资成本",
        "- 历史表现不代表未来结果",
        "- 不构成投资建议",
    ]
    return "\n".join(lines)


def render_json(series_list: list[Series], rf: float = 0.0) -> list[dict]:
    """指标以结构化形式返回，便于其它程序消费。"""
    return [to_dict(compute_metrics(s, rf)) for s in series_list]
