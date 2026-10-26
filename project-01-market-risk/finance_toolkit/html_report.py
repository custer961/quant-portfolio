"""
finance_toolkit.html_report — 自包含 HTML 报告（中英双语）

特点：
- 图表是内联 SVG，单个 .html 文件即可交付，不依赖网络和第三方库
- 可直接用浏览器打印成 PDF 发给客户
- `lang="zh" | "en"` 切换全部文案，中英文共用同一套代码与样式
"""
from __future__ import annotations

import math
from datetime import datetime
from html import escape
from typing import Any

from .charts import bar_chart, drawdown_chart, heatmap, line_chart
from .core import (
    Series,
    compute_metrics,
    equal_weight_portfolio,
    max_drawdown,
    return_correlation,
)

CSS = """
:root{--ink:#111827;--muted:#6b7280;--line:#e5e7eb;--bg:#ffffff;--accent:#2563eb}
*{box-sizing:border-box}
body{margin:0;padding:40px 24px;background:#f9fafb;color:var(--ink);
  font-family:'Segoe UI',system-ui,-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;
  line-height:1.6}
.wrap{max-width:980px;margin:0 auto;background:var(--bg);padding:40px 44px;
  border-radius:12px;box-shadow:0 1px 3px rgba(0,0,0,.08)}
h1{font-size:26px;margin:0 0 6px}
h2{font-size:18px;margin:36px 0 12px;padding-bottom:8px;border-bottom:1px solid var(--line)}
h3{font-size:15px;margin:24px 0 8px;color:#374151}
.sub{color:var(--muted);font-size:13px;margin-bottom:24px}
table{width:100%;border-collapse:collapse;font-size:13px;margin:12px 0}
th,td{padding:8px 10px;border-bottom:1px solid var(--line);text-align:right}
th:first-child,td:first-child{text-align:left}
th{color:var(--muted);font-weight:600;font-size:12px;letter-spacing:.02em}
tbody tr:hover{background:#f9fafb}
.num{font-variant-numeric:tabular-nums}
.pos{color:#15803d}.neg{color:#b91c1c}
.note{background:#f3f4f6;border-left:3px solid #9ca3af;padding:12px 16px;
  font-size:13px;color:#4b5563;border-radius:0 6px 6px 0;margin:16px 0}
.chart{margin:16px 0}
svg{max-width:100%;height:auto}
footer{margin-top:40px;padding-top:16px;border-top:1px solid var(--line);
  font-size:12px;color:var(--muted)}
.disclaimer{margin:28px 0 20px;padding:14px 18px;background:#fff7ed;
  border:1px solid #fdba74;border-left-width:4px;border-radius:6px;font-size:13px;color:#7c2d12}
.disclaimer strong{color:#9a3412}
.sign{margin:32px 0 8px;padding-top:20px;border-top:1px solid var(--line);
  display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px}
.sign-item span{display:block;font-size:11px;color:var(--muted);letter-spacing:.04em;
  margin-bottom:2px}
.sign-item strong{font-size:14px;color:var(--ink)}
@media print{
  body{background:#fff;padding:0}
  .wrap{box-shadow:none;padding:0;max-width:none}
  h2{page-break-after:avoid}
  .chart,table{page-break-inside:avoid}
}
"""

STRINGS: dict[str, dict[str, Any]] = {
    "zh": {
        "html_lang": "zh-CN",
        "title": "行情风险与绩效报告",
        "sub": "数据区间 {start} ~ {end} · {n} 个品种 · 无风险利率 {rf}",
        "s_overview": "一、绩效概览",
        "th_symbol": "品种", "th_total": "累计收益", "th_cagr": "年化收益",
        "th_vol": "年化波动", "th_sharpe": "夏普", "th_sortino": "索提诺",
        "th_mdd": "最大回撤", "th_calmar": "Calmar", "th_var": "日 VaR95",
        "s_nav": "二、净值走势（归一化）",
        "note_nav": "以各品种首个交易日收盘价为 1.0，便于比较不同价位的走势。仅反映价格变化，未计入交易成本。",
        "s_dd": "三、回撤",
        "h3_dd": "{sym} · 最大回撤 {dd}",
        "s_monthly": "四、月度收益",
        "s_corr": "五、日收益相关性",
        "note_corr": "相关性越接近 1，分散化效果越弱。危机时期相关性通常上升，实际分散效果可能低于历史均值。",
        "h3_ew": "等权组合对照",
        "th_portfolio": "组合", "ew_name": "等权组合",
        "s_insights": "六、结论摘要",
        "note_insights": "以下为历史数据的客观描述，不含对未来走势的判断。数值均由上方图表与表格直接推导，可逐项复核。",
        "s_method": "七、方法说明与局限",
        "method": [
            "年化按 252 个交易日；波动率为日收益标准差 × √252",
            "夏普与索提诺使用日收益，按 √252 年化，超额收益扣除无风险利率",
            "最大回撤基于收盘价的历史峰值回撤；VaR 为历史模拟法分位数",
            "仅使用收盘价，<strong>未计交易成本、滑点与融资成本</strong>",
            "等权组合未考虑再平衡摩擦，仅作分散化效果的快速对照",
            "数据来源为公开行情接口，可能存在缺失、滞后或复权差异",
        ],
        "disc_prefix": "免责声明：",
        "disc_body": ("本报告基于历史公开数据生成，仅用于数据描述与统计分析，"
                      "<strong>不构成任何投资建议、要约或收益承诺</strong>。"
                      "历史表现不代表未来结果，任何投资决策应自行判断并承担相应风险。"),
        "sign_author": "报告作者", "sign_contact": "联系方式",
        "sign_date": "生成日期", "sign_range": "品种数 / 区间",
        "range_fmt": "{n} 个 · {range}",
        "placeholder": "（待填写）",
        "footer": "本报告由 finance_toolkit 生成 · 零第三方依赖 · 可离线复现",
        "ins_best": "区间内年化收益最高的是 <strong>{a}</strong>（{av}），最低的是 {b}（{bv}）。",
        "ins_risk": "年化波动最高的是 <strong>{a}</strong>（{av}），区间最大回撤为 {dd}。",
        "ins_sharpe": "风险调整后表现（夏普）最好的是 <strong>{a}</strong>（{v}）。",
        "ins_corr": "相关性最高的一对是 <strong>{a} 与 {b}</strong>（{v}），相关性越接近 1，分散化效果越弱。",
        "ins_ew": "等权组合夏普 {s}、最大回撤 {d}，可与上表单品种对照，判断分散化是否改善风险调整后表现。",
        "ins_close": "以上均为历史统计，样本区间或品种变化时结论可能不同。",
        "legend_corr": "相关系数",
    },
    "en": {
        "html_lang": "en",
        "title": "Market Risk & Performance Report",
        "sub": "Period {start} ~ {end} · {n} instruments · risk-free rate {rf}",
        "s_overview": "1. Performance overview",
        "th_symbol": "Symbol", "th_total": "Total return", "th_cagr": "CAGR",
        "th_vol": "Ann. vol", "th_sharpe": "Sharpe", "th_sortino": "Sortino",
        "th_mdd": "Max drawdown", "th_calmar": "Calmar", "th_var": "Daily VaR95",
        "s_nav": "2. Normalised equity curves",
        "note_nav": ("Each series is rebased to 1.0 at its first close so different price "
                     "levels are comparable. Price changes only — trading costs are excluded."),
        "s_dd": "3. Drawdowns",
        "h3_dd": "{sym} · max drawdown {dd}",
        "s_monthly": "4. Monthly returns",
        "s_corr": "5. Daily return correlation",
        "note_corr": ("The closer to 1, the weaker the diversification. Correlations typically "
                      "rise during crises, so realised diversification may be worse than history suggests."),
        "h3_ew": "Equal-weight portfolio",
        "th_portfolio": "Portfolio", "ew_name": "Equal weight",
        "s_insights": "6. Key findings",
        "note_insights": ("Descriptive statistics only — no view on future direction. "
                          "Every number is derived from the charts and tables above and can be re-derived."),
        "s_method": "7. Methodology & limitations",
        "method": [
            "Annualisation uses 252 trading days; volatility is the standard deviation of daily returns × √252",
            "Sharpe and Sortino use daily returns annualised by √252, with excess returns net of the risk-free rate",
            "Maximum drawdown is measured on closing prices from the running peak; VaR is the historical-simulation quantile",
            "Close prices only — <strong>transaction costs, slippage and financing are excluded</strong>",
            "The equal-weight portfolio ignores rebalancing friction and is a quick diversification check only",
            "Data comes from a public market-data endpoint and may contain gaps, delays or adjustment differences",
        ],
        "disc_prefix": "Disclaimer: ",
        "disc_body": ("This report is generated from public historical data for descriptive and statistical "
                      "purposes only. <strong>It does not constitute investment advice, an offer, or any "
                      "promise of returns.</strong> Past performance does not indicate future results; any "
                      "investment decision is your own and carries your own risk."),
        "sign_author": "Prepared by", "sign_contact": "Contact",
        "sign_date": "Generated", "sign_range": "Instruments / period",
        "range_fmt": "{n} · {range}",
        "placeholder": "(to be filled)",
        "footer": "Generated with finance_toolkit · zero third-party dependencies · reproducible offline",
        "ins_best": ("Highest annualised return in the period: <strong>{a}</strong> ({av}); "
                     "lowest: {b} ({bv})."),
        "ins_risk": ("Highest annualised volatility: <strong>{a}</strong> ({av}), "
                     "with a maximum drawdown of {dd} over the period."),
        "ins_sharpe": "Best risk-adjusted performance (Sharpe): <strong>{a}</strong> ({v}).",
        "ins_corr": ("The most correlated pair is <strong>{a} and {b}</strong> ({v}); "
                     "the closer to 1, the weaker the diversification benefit."),
        "ins_ew": ("The equal-weight portfolio shows a Sharpe of {s} and a maximum drawdown of {d}; "
                   "compare it with the single assets above to judge whether diversification helped."),
        "ins_close": "All figures are historical; conclusions may change with a different period or asset set.",
        "legend_corr": "Correlation",
    },
}


def _pct(x: float, digits: int = 2) -> str:
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return "—"
    if abs(x) < 1e-12:
        x = 0.0
    return f"{x * 100:.{digits}f}%"


def _num(x: float, digits: int = 2) -> str:
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return "—"
    if abs(x) < 1e-12:
        x = 0.0
    return f"{x:,.{digits}f}"


def _cls(x: float) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return ""
    return "pos" if x > 0 else ("neg" if x < 0 else "")


def monthly_returns(series: Series) -> tuple[list[str], list[float]]:
    """按自然月计算收益：月内首日收盘 → 月末收盘。"""
    buckets: dict[str, list[float]] = {}
    for d, c in zip(series.dates, series.closes):
        buckets.setdefault(d[:7], []).append(float(c))
    months = sorted(buckets)
    return months, [
        (buckets[m][-1] / buckets[m][0] - 1.0) if buckets[m][0] else 0.0 for m in months
    ]


def _insights(series_list: list[Series], metrics: list[dict], rf: float,
              T: dict) -> list[str]:
    """从指标推出可复核的结论句。只描述历史，不预测未来。"""
    out: list[str] = []
    best = max(metrics, key=lambda m: m["cagr"])
    worst = min(metrics, key=lambda m: m["cagr"])
    out.append(T["ins_best"].format(
        a=escape(best["symbol"]), av=_pct(best["cagr"]),
        b=escape(worst["symbol"]), bv=_pct(worst["cagr"])))

    riskiest = max(metrics, key=lambda m: m["ann_vol"])
    out.append(T["ins_risk"].format(
        a=escape(riskiest["symbol"]), av=_pct(riskiest["ann_vol"]),
        dd=_pct(riskiest["max_drawdown"])))

    bs = max(metrics, key=lambda m: m["sharpe"])
    out.append(T["ins_sharpe"].format(a=escape(bs["symbol"]), v=_num(bs["sharpe"])))

    if len(series_list) >= 2:
        try:
            corr = return_correlation(series_list)
            names = [x.symbol for x in series_list]
            hi, pair = -2.0, ("", "")
            for i in range(len(names)):
                for j in range(i + 1, len(names)):
                    v = float(corr[i][j])
                    if v > hi:
                        hi, pair = v, (names[i], names[j])
            out.append(T["ins_corr"].format(a=escape(pair[0]), b=escape(pair[1]), v=f"{hi:.2f}"))

            ew = compute_metrics(equal_weight_portfolio(series_list), rf)
            out.append(T["ins_ew"].format(s=_num(ew["sharpe"]), d=_pct(ew["max_drawdown"])))
        except ValueError:
            pass

    out.append(T["ins_close"])
    return out


def build_html(series_list: list[Series], rf: float = 0.0,
               title: str | None = None, author: str = "", contact: str = "",
               lang: str = "zh") -> str:
    T = STRINGS.get(lang, STRINGS["zh"])
    title = title or T["title"]
    metrics = [compute_metrics(s, rf) for s in series_list]
    range_label = f"{series_list[0].dates[0]} ~ {series_list[-1].dates[-1]}"
    parts: list[str] = []
    first, last = series_list[0], series_list[-1]

    parts.append(
        f"<h1>{escape(title)}</h1>"
        f'<div class="sub">' + T["sub"].format(
            start=escape(first.dates[0]), end=escape(last.dates[-1]),
            n=len(series_list), rf=_pct(rf)) + "</div>"
    )

    # ---- 概览
    parts.append(f"<h2>{T['s_overview']}</h2>")
    parts.append("<table><thead><tr>"
                 f"<th>{T['th_symbol']}</th><th>{T['th_total']}</th><th>{T['th_cagr']}</th>"
                 f"<th>{T['th_vol']}</th><th>{T['th_sharpe']}</th><th>{T['th_sortino']}</th>"
                 f"<th>{T['th_mdd']}</th><th>{T['th_calmar']}</th><th>{T['th_var']}</th>"
                 "</tr></thead><tbody>")
    for m in metrics:
        parts.append(
            "<tr>"
            f"<td><strong>{escape(m['symbol'])}</strong></td>"
            f'<td class="num {_cls(m["total_return"])}">{_pct(m["total_return"])}</td>'
            f'<td class="num {_cls(m["cagr"])}">{_pct(m["cagr"])}</td>'
            f'<td class="num">{_pct(m["ann_vol"])}</td>'
            f'<td class="num">{_num(m["sharpe"])}</td>'
            f'<td class="num">{_num(m["sortino"])}</td>'
            f'<td class="num neg">{_pct(m["max_drawdown"])}</td>'
            f'<td class="num">{_num(m["calmar"])}</td>'
            f'<td class="num">{_pct(m["var95_daily"])}</td>'
            "</tr>"
        )
    parts.append("</tbody></table>")

    # ---- 净值曲线
    parts.append(f"<h2>{T['s_nav']}</h2>")
    parts.append('<div class="chart">')
    parts.append(line_chart(
        [{"label": s.symbol, "values": list(s.closes)} for s in series_list],
        title="", normalize=True, y_fmt=lambda v: f"{v:.2f}",
        x_labels=series_list[0].dates,
    ))
    parts.append("</div>")
    parts.append(f'<div class="note">{T["note_nav"]}</div>')

    # ---- 回撤
    parts.append(f"<h2>{T['s_dd']}</h2>")
    for s in series_list:
        dd, _, _ = max_drawdown(s)
        parts.append(f"<h3>{escape(T['h3_dd'].format(sym=s.symbol, dd=_pct(dd)))}</h3>")
        parts.append('<div class="chart">')
        parts.append(drawdown_chart(list(s.closes), title="", x_labels=s.dates))
        parts.append("</div>")

    # ---- 月度收益
    parts.append(f"<h2>{T['s_monthly']}</h2>")
    for s in series_list:
        months, rets = monthly_returns(s)
        if len(months) < 2:
            continue
        parts.append(f"<h3>{escape(s.symbol)}</h3>")
        parts.append('<div class="chart">')
        parts.append(bar_chart(rets, months, title=""))
        parts.append("</div>")

    # ---- 相关性
    if len(series_list) >= 2:
        try:
            corr = return_correlation(series_list)
            names = [s.symbol for s in series_list]
            parts.append(f"<h2>{T['s_corr']}</h2>")
            parts.append('<div class="chart">')
            parts.append(heatmap([[float(corr[i][j]) for j in range(len(names))]
                                  for i in range(len(names))], names, names, title="", legend=T["legend_corr"]))
            parts.append("</div>")
            parts.append(f'<div class="note">{T["note_corr"]}</div>')

            ew = equal_weight_portfolio(series_list)
            ew_m = compute_metrics(ew, rf)
            parts.append(f"<h3>{T['h3_ew']}</h3><table><thead><tr>"
                         f"<th>{T['th_portfolio']}</th><th>{T['th_total']}</th>"
                         f"<th>{T['th_vol']}</th><th>{T['th_sharpe']}</th><th>{T['th_mdd']}</th>"
                         "</tr></thead><tbody>")
            parts.append(
                f"<tr><td><strong>{T['ew_name']}</strong></td>"
                f'<td class="num {_cls(ew_m["total_return"])}">{_pct(ew_m["total_return"])}</td>'
                f'<td class="num">{_pct(ew_m["ann_vol"])}</td>'
                f'<td class="num">{_num(ew_m["sharpe"])}</td>'
                f'<td class="num neg">{_pct(ew_m["max_drawdown"])}</td></tr>'
            )
            parts.append("</tbody></table>")
        except ValueError:
            pass

    # ---- 结论摘要
    lines = _insights(series_list, metrics, rf, T)
    parts.append(f"<h2>{T['s_insights']}</h2>")
    parts.append(f'<div class="note">{T["note_insights"]}</div>')
    parts.append("<ul>" + "".join(f"<li>{x}</li>" for x in lines) + "</ul>")

    # ---- 方法与局限
    parts.append(f"<h2>{T['s_method']}</h2>")
    parts.append("<ul>" + "".join(f"<li>{x}</li>" for x in T["method"]) + "</ul>")

    # ---- 免责声明
    parts.append(f'<div class="disclaimer"><strong>{T["disc_prefix"]}</strong>{T["disc_body"]}</div>')

    # ---- 署名
    parts.append(
        '<div class="sign">'
        f'<div class="sign-item"><span>{T["sign_author"]}</span>'
        f'<strong>{escape(author or T["placeholder"])}</strong></div>'
        f'<div class="sign-item"><span>{T["sign_contact"]}</span>'
        f'<strong>{escape(contact or T["placeholder"])}</strong></div>'
        f'<div class="sign-item"><span>{T["sign_date"]}</span>'
        f'<strong>{datetime.now().strftime("%Y-%m-%d")}</strong></div>'
        f'<div class="sign-item"><span>{T["sign_range"]}</span>'
        f'<strong>{escape(T["range_fmt"].format(n=len(series_list), range=range_label))}</strong></div>'
        "</div>"
    )

    parts.append(f"<footer>{T['footer']}</footer>")
    return (
        f'<!DOCTYPE html><html lang="{T["html_lang"]}"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{escape(title)}</title><style>{CSS}</style></head>"
        f'<body><div class="wrap">{"".join(parts)}</div></body></html>'
    )
