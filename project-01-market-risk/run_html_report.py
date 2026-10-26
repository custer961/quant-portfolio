"""
命令行入口：生成自包含的 HTML 风险报告（图表内联，单文件交付）。

示例
----
python run_html_report.py --symbols "^GSPC" "QQQ" "MNQ=F" --range 2y --out report.html
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from finance_toolkit.core import build_series, fetch_prices
from finance_toolkit.html_report import build_html
from finance_toolkit.html_report_pro import build_html_pro


MSG = {
    "zh": {"ok": "[ok] {s}: {n} 根日线", "skip": "[skip] {s}: {e}",
           "none": "没有任何品种取数成功。", "written": "报告已写入: {p}  ({n:,} 字符)"},
    "en": {"ok": "[ok] {s}: {n} bars", "skip": "[skip] {s}: {e}",
           "none": "No symbol could be fetched.", "written": "Report written: {p}  ({n:,} chars)"},
}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="HTML 风险报告生成器")
    ap.add_argument("--symbols", nargs="+", required=True)
    ap.add_argument("--labels", nargs="*", default=[],
                    help="显示名映射，如 600519.SS=贵州茅台")
    ap.add_argument("--range", default="2y",
                    choices=["1mo", "3mo", "6mo", "1y", "2y", "5y", "max"])
    ap.add_argument("--rf", type=float, default=0.0, help="年化无风险利率，如 0.04")
    ap.add_argument("--csv-dir", help="本地 CSV 数据目录（离线运行，文件名如 GSPC.csv）")
    ap.add_argument("--out", type=Path, default=Path("report.html"))
    ap.add_argument("--title", default=None, help="报告标题（默认按语言内置）")
    ap.add_argument("--lang", default="zh", choices=["zh", "en"], help="报告语言")
    ap.add_argument("--style", default="classic", choices=["classic", "pro"],
                    help="版式：classic=研报风，pro=商业报告风")
    ap.add_argument("--author", default="", help="报告署名")
    ap.add_argument("--contact", default="", help="联系方式")
    args = ap.parse_args(argv)
    M = MSG.get(args.lang, MSG["zh"])

    label_map = {}
    for item in args.labels:
        if "=" in item:
            k, v = item.split("=", 1)
            label_map[k.strip()] = v.strip()
    series_list = []
    for sym in args.symbols:
        try:
            rows = fetch_prices(sym, range_=args.range, csv_dir=args.csv_dir)
            s = build_series(rows, symbol=label_map.get(sym, sym))
            series_list.append(s)
            print(M["ok"].format(s=sym, n=len(s)), file=sys.stderr)
        except Exception as exc:
            print(M["skip"].format(s=sym, e=f"{type(exc).__name__}: {exc}"), file=sys.stderr)

    if not series_list:
        print(M["none"], file=sys.stderr)
        return 1

    build = build_html_pro if args.style == "pro" else build_html
    html = build(series_list, rf=args.rf, title=args.title,
                 author=args.author, contact=args.contact,
                 lang=args.lang)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(html, encoding="utf-8")
    print(M["written"].format(p=args.out, n=len(html)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
