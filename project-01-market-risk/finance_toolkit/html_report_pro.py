"""
finance_toolkit.html_report_pro — 商业报告风（Pre-Mium）HTML 报告

与 html_report.py 的区别只在**视觉语言**，数据与算法完全共用：

- 卡片式布局：大圆角、轻阴影、充足留白
- 顶部 KPI 卡：每个品种一张，大数字 + 小标签
- 章节带编号眼睛标（01 / 02 …），层级更清楚
- 适合给老板、客户看（而不是给同行看的研报）

用法
----
from finance_toolkit.html_report_pro import build_html_pro
html = build_html_pro(series_list, lang="zh")
"""
from __future__ import annotations

import math
from datetime import datetime
from html import escape

from .charts import bar_chart, drawdown_chart, heatmap, line_chart
from .core import (
    Series,
    compute_metrics,
    equal_weight_portfolio,
    max_drawdown,
    return_correlation,
)
from .html_report import STRINGS, _cls, _num, _pct, monthly_returns

CSS = """
:root{
  --ink:#0b1220; --ink-2:#1f2937; --muted:#6b7280; --faint:#9ca3af;
  --line:#e8ecf3; --bg:#eef1f6; --card:#ffffff;
  --accent:#3b5bdb; --accent-soft:#eef2ff;
  --pos:#0f766e; --neg:#be123c;
  --r:18px;
}
*{box-sizing:border-box;margin:0;padding:0}
body{
  background:var(--bg); color:var(--ink); line-height:1.65;
  font-family:'PingFang SC','Microsoft YaHei','Segoe UI',system-ui,-apple-system,sans-serif;
  -webkit-font-smoothing:antialiased; padding:56px 24px 96px;
}
.page{max-width:1040px;margin:0 auto}

/* ---------- Hero ---------- */
.hero{
  background:linear-gradient(160deg,#ffffff 0%,#f8faff 100%);
  border-radius:calc(var(--r) + 6px); padding:52px 56px 44px;
  box-shadow:0 1px 2px rgba(16,24,40,.04),0 12px 32px -12px rgba(16,24,40,.12);
  margin-bottom:28px;
}
.eyebrow{
  font-size:11px;letter-spacing:.22em;text-transform:uppercase;
  color:var(--accent);font-weight:700;margin-bottom:14px;
}
.hero h1{font-size:38px;line-height:1.2;letter-spacing:-.02em;font-weight:800}
.chips{display:flex;flex-wrap:wrap;gap:10px;margin-top:22px}
.chip{
  font-size:12.5px;color:var(--ink-2);background:#f1f4fa;
  border:1px solid var(--line);border-radius:999px;padding:7px 14px;
}
.chip b{color:var(--ink);font-weight:700}

/* ---------- Section ---------- */
section{margin-top:34px}
.sec-head{display:flex;align-items:center;gap:14px;margin:0 0 16px 4px}
.sec-num{
  font-size:12px;font-weight:800;color:var(--accent);
  background:var(--accent-soft);border-radius:8px;padding:5px 9px;letter-spacing:.06em;
}
.sec-head h2{font-size:17px;font-weight:700;letter-spacing:-.01em}

.card{
  background:var(--card);border-radius:var(--r);padding:32px 34px;
  box-shadow:0 1px 2px rgba(16,24,40,.04),0 8px 24px -14px rgba(16,24,40,.18);
}
.card + .card{margin-top:16px}

/* ---------- KPI ---------- */
.kpi-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px}
.kpi{
  background:var(--card);border-radius:var(--r);padding:26px 28px;
  box-shadow:0 1px 2px rgba(16,24,40,.04),0 8px 24px -14px rgba(16,24,40,.18);
}
.kpi .sym{font-size:13px;font-weight:700;color:var(--ink-2);letter-spacing:.02em}
.kpi .big{font-size:38px;font-weight:800;letter-spacing:-.025em;margin:10px 0 4px;
  font-variant-numeric:tabular-nums}
.kpi .cap{font-size:11.5px;color:var(--faint);letter-spacing:.04em;text-transform:uppercase}
.kpi .sub{display:flex;gap:18px;margin-top:18px;padding-top:16px;border-top:1px solid var(--line)}
.kpi .sub div span{display:block}
.kpi .sub .k{font-size:10.5px;color:var(--faint);text-transform:uppercase;letter-spacing:.05em}
.kpi .sub .v{font-size:15px;font-weight:700;font-variant-numeric:tabular-nums}

/* ---------- Table ---------- */
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{padding:13px 12px;text-align:right;border-bottom:1px solid var(--line)}
th:first-child,td:first-child{text-align:left}
th{font-size:11px;color:var(--faint);font-weight:700;text-transform:uppercase;letter-spacing:.06em;
  border-bottom:1px solid #dbe2ee}
tbody tr:last-child td{border-bottom:none}
tbody tr:hover{background:#fafbfe}
.num{font-variant-numeric:tabular-nums}
.pos{color:var(--pos)} .neg{color:var(--neg)}

/* ---------- Misc ---------- */
.note{
  margin-top:14px;font-size:12.5px;color:var(--muted);
  background:#f7f9fc;border-radius:12px;padding:14px 18px;line-height:1.7;
}
.chart svg{display:block;width:100%;height:auto}
h3{font-size:14px;font-weight:700;margin:0 0 10px;color:var(--ink-2)}
.findings{display:flex;flex-direction:column;gap:0}
.findings li{
  list-style:none;font-size:14px;padding:16px 0;border-bottom:1px solid var(--line);
  line-height:1.75;color:var(--ink-2);
}
.findings li:last-child{border-bottom:none;padding-bottom:0}
.findings li strong{color:var(--ink);font-weight:700}
.method li{font-size:12.5px;color:var(--muted);margin-left:18px;line-height:1.9}

.disclaimer{
  margin-top:28px;background:#fff8f1;border:1px solid #fde4cd;border-radius:var(--r);
  padding:22px 26px;font-size:12.5px;color:#8a4b21;line-height:1.75;
}
.disclaimer b{color:#7c3a0b}

.sign{
  margin-top:28px;background:var(--card);border-radius:var(--r);padding:26px 30px;
  display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:18px;
  box-shadow:0 1px 2px rgba(16,24,40,.04),0 8px 24px -14px rgba(16,24,40,.18);
}
.sign-item span{display:block;font-size:10.5px;color:var(--faint);
  text-transform:uppercase;letter-spacing:.07em;margin-bottom:4px}
.sign-item strong{font-size:14px;font-weight:700}

footer{margin-top:26px;text-align:center;font-size:11.5px;color:var(--faint)}

@media print{
  body{background:#fff;padding:0}
  .hero,.card,.kpi,.sign{box-shadow:none;border:1px solid var(--line)}
  section{page-break-inside:avoid}
}
"""


def _sec(num: str, title: str) -> str:
    return (f'<div class="sec-head"><span class="sec-num">{escape(num)}</span>'
            f"<h2>{escape(title)}</h2></div>")


def build_html_pro(series_list: list[Series], rf: float = 0.0,
                   title: str | None = None, author: str = "", contact: str = "",
                   lang: str = "zh") -> str:
    T = STRINGS.get(lang, STRINGS["zh"])
    title = title or T["title"]
    metrics = [compute_metrics(s, rf) for s in series_list]
    range_label = f"{series_list[0].dates[0]} — {series_list[-1].dates[-1]}"

    P: list[str] = []
    P.append('<div class="page">')

    # ---------- Hero
    P.append('<header class="hero">')
    P.append(f'<div class="eyebrow">{escape(T["s_overview"].split("、")[-1] if lang == "zh" else "Risk Report")}</div>')
    P.append(f"<h1>{escape(title)}</h1>")
    P.append('<div class="chips">'
             f'<span class="chip">{escape(T["sub"].format(start=range_label.split(" — ")[0], end=range_label.split(" — ")[1], n=len(series_list), rf=_pct(rf)).split("·")[0].strip())}</span>'
             f'<span class="chip"><b>{len(series_list)}</b> '
             f'{"个品种" if lang == "zh" else "instruments"}</span>'
             f'<span class="chip">{"无风险利率" if lang == "zh" else "risk-free"} '
             f'<b>{_pct(rf)}</b></span>'
             "</div>")
    P.append("</header>")

    # ---------- 01 KPI
    P.append("<section>")
    P.append(_sec("01", T["s_overview"].split("、", 1)[-1]))
    P.append('<div class="kpi-grid">')
    for m in metrics:
        P.append(
            '<div class="kpi">'
            f'<div class="sym">{escape(m["symbol"])}</div>'
            f'<div class="big {_cls(m["cagr"])}">{_pct(m["cagr"])}</div>'
            f'<div class="cap">{T["th_cagr"]}</div>'
            '<div class="sub">'
            f'<div><span class="k">{T["th_sharpe"]}</span><span class="v">{_num(m["sharpe"])}</span></div>'
            f'<div><span class="k">{T["th_mdd"]}</span><span class="v neg">{_pct(m["max_drawdown"])}</span></div>'
            f'<div><span class="k">{T["th_vol"]}</span><span class="v">{_pct(m["ann_vol"])}</span></div>'
            "</div></div>"
        )
    P.append("</div>")

    # 完整表格
    P.append('<div class="card" style="margin-top:16px">')
    P.append("<table><thead><tr>"
             f"<th>{T['th_symbol']}</th><th>{T['th_total']}</th><th>{T['th_cagr']}</th>"
             f"<th>{T['th_vol']}</th><th>{T['th_sharpe']}</th><th>{T['th_sortino']}</th>"
             f"<th>{T['th_mdd']}</th><th>{T['th_calmar']}</th><th>{T['th_var']}</th>"
             "</tr></thead><tbody>")
    for m in metrics:
        P.append(
            f"<tr><td><strong>{escape(m['symbol'])}</strong></td>"
            f'<td class="num {_cls(m["total_return"])}">{_pct(m["total_return"])}</td>'
            f'<td class="num {_cls(m["cagr"])}">{_pct(m["cagr"])}</td>'
            f'<td class="num">{_pct(m["ann_vol"])}</td>'
            f'<td class="num">{_num(m["sharpe"])}</td>'
            f'<td class="num">{_num(m["sortino"])}</td>'
            f'<td class="num neg">{_pct(m["max_drawdown"])}</td>'
            f'<td class="num">{_num(m["calmar"])}</td>'
            f'<td class="num">{_pct(m["var95_daily"])}</td></tr>'
        )
    P.append("</tbody></table></div>")
    P.append("</section>")

    # ---------- 02 净值
    P.append("<section>")
    P.append(_sec("02", T["s_nav"].split("、", 1)[-1]))
    P.append('<div class="card chart">')
    P.append(line_chart([{"label": s.symbol, "values": list(s.closes)} for s in series_list],
                        title="", normalize=True, y_fmt=lambda v: f"{v:.2f}",
                        x_labels=series_list[0].dates))
    P.append(f'<div class="note">{T["note_nav"]}</div>')
    P.append("</div></section>")

    # ---------- 03 回撤
    P.append("<section>")
    P.append(_sec("03", T["s_dd"].split("、", 1)[-1]))
    for s in series_list:
        dd, _, _ = max_drawdown(s)
        P.append('<div class="card chart">')
        P.append(f'<h3>{escape(T["h3_dd"].format(sym=s.symbol, dd=_pct(dd)))}</h3>')
        P.append(drawdown_chart(list(s.closes), title="", x_labels=s.dates))
        P.append("</div>")
    P.append("</section>")

    # ---------- 04 月度
    P.append("<section>")
    P.append(_sec("04", T["s_monthly"].split("、", 1)[-1]))
    for s in series_list:
        months, rets = monthly_returns(s)
        if len(months) < 2:
            continue
        P.append('<div class="card chart">')
        P.append(f"<h3>{escape(s.symbol)}</h3>")
        P.append(bar_chart(rets, months, title=""))
        P.append("</div>")
    P.append("</section>")

    # ---------- 05 相关性
    if len(series_list) >= 2:
        try:
            corr = return_correlation(series_list)
            names = [s.symbol for s in series_list]
            P.append("<section>")
            P.append(_sec("05", T["s_corr"].split("、", 1)[-1]))
            P.append('<div class="card chart">')
            P.append(heatmap([[float(corr[i][j]) for j in range(len(names))]
                              for i in range(len(names))], names, names, title="",
                             legend=T["legend_corr"]))
            P.append(f'<div class="note">{T["note_corr"]}</div>')
            P.append("</div>")

            ew = equal_weight_portfolio(series_list)
            ew_m = compute_metrics(ew, rf)
            P.append('<div class="card" style="margin-top:16px">')
            P.append(f"<h3>{T['h3_ew']}</h3>")
            P.append("<table><thead><tr>"
                     f"<th>{T['th_portfolio']}</th><th>{T['th_total']}</th>"
                     f"<th>{T['th_vol']}</th><th>{T['th_sharpe']}</th><th>{T['th_mdd']}</th>"
                     "</tr></thead><tbody>")
            P.append(
                f"<tr><td><strong>{T['ew_name']}</strong></td>"
                f'<td class="num {_cls(ew_m["total_return"])}">{_pct(ew_m["total_return"])}</td>'
                f'<td class="num">{_pct(ew_m["ann_vol"])}</td>'
                f'<td class="num">{_num(ew_m["sharpe"])}</td>'
                f'<td class="num neg">{_pct(ew_m["max_drawdown"])}</td></tr>'
                "</tbody></table></div>")
            P.append("</section>")
        except ValueError:
            pass

    # ---------- 06 结论
    P.append("<section>")
    P.append(_sec("06", T["s_insights"].split("、", 1)[-1]))
    P.append('<div class="card">')
    P.append(f'<div class="note" style="margin-top:0;margin-bottom:12px">{T["note_insights"]}</div>')
    from .html_report import _insights
    P.append('<ul class="findings">')
    for line in _insights(series_list, metrics, rf, T):
        P.append(f"<li>{line}</li>")
    P.append("</ul></div></section>")

    # ---------- 07 方法
    P.append("<section>")
    P.append(_sec("07", T["s_method"].split("、", 1)[-1]))
    P.append('<div class="card"><ul class="method">')
    for item in T["method"]:
        P.append(f"<li>{item}</li>")
    P.append("</ul></div></section>")

    # ---------- 免责
    P.append(f'<div class="disclaimer"><b>{T["disc_prefix"]}</b>{T["disc_body"]}</div>')

    # ---------- 署名
    P.append(
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
    P.append(f"<footer>{T['footer']}</footer>")
    P.append("</div>")

    return (
        f'<!DOCTYPE html><html lang="{T["html_lang"]}"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{escape(title)}</title><style>{CSS}</style></head>"
        f'<body>{"".join(P)}</body></html>'
    )
