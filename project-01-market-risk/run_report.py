"""
命令行入口：拉取若干品种的日线，生成 Markdown 风险报告。

示例
----
python run_report.py --symbols "^GSPC" "QQQ" "MNQ=F" --range 2y
python run_report.py --symbols "^GSPC" --range 1y --out report.md
python run_report.py --symbols QQQ --json

常用符号
--------
^GSPC   标普500指数
^NDX    纳斯达克100指数
QQQ     纳指ETF
NQ=F    纳指100期货
MNQ=F   微型纳指100期货
ES=F    标普500期货
GC=F    黄金期货
CL=F    原油期货
BTC-USD 比特币
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from finance_toolkit.core import build_series, fetch_prices
from finance_toolkit.report import render_json, render_report


MSG = {
    "zh": {"title": "风险与绩效报告（{r}）",
           "ok": "[ok] {s}: {n} 根日线 ({a} ~ {b})", "skip": "[skip] {s}: {e}",
           "none": "没有任何品种取数成功。", "written": "报告已写入: {p}"},
    "en": {"title": "Market Risk & Performance Report ({r})",
           "ok": "[ok] {s}: {n} bars ({a} ~ {b})", "skip": "[skip] {s}: {e}",
           "none": "No symbol could be fetched.", "written": "Report written: {p}"},
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="零依赖金融风险报告生成器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--symbols", nargs="+", required=True, help="Yahoo 符号，可多个")
    parser.add_argument("--range", default="2y",
                        choices=["1mo", "3mo", "6mo", "1y", "2y", "5y", "max"],
                        help="数据区间，默认 2y")
    parser.add_argument("--rf", type=float, default=0.0, help="年化无风险利率，如 0.04")
    parser.add_argument("--csv-dir", help="本地 CSV 数据目录（离线运行，文件名如 GSPC.csv）")
    parser.add_argument("--out", type=Path, help="报告输出路径（Markdown）")
    parser.add_argument("--json", action="store_true", help="输出 JSON 而非 Markdown")
    parser.add_argument("--no-cache", action="store_true", help="跳过本地缓存")
    parser.add_argument("--lang", default="zh", choices=["zh", "en"])
    args = parser.parse_args(argv)
    M = MSG.get(args.lang, MSG["zh"])

    series_list = []
    for sym in args.symbols:
        try:
            rows = fetch_prices(sym, range_=args.range, use_cache=not args.no_cache, csv_dir=args.csv_dir)
            s = build_series(rows, symbol=sym)
            series_list.append(s)
            print(M["ok"].format(s=sym, n=len(s), a=s.dates[0], b=s.dates[-1]), file=sys.stderr)
        except Exception as exc:  # noqa: BLE001 —— 单个品种失败不应中断整体
            print(M["skip"].format(s=sym, e=f"{type(exc).__name__}: {exc}"), file=sys.stderr)

    if not series_list:
        print(M["none"], file=sys.stderr)
        return 1

    output = (json.dumps(render_json(series_list, args.rf), ensure_ascii=False, indent=2)
              if args.json
              else render_report(series_list, rf=args.rf,
                                 title=M["title"].format(r=args.range)))

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(output, encoding="utf-8")
        print(M["written"].format(p=args.out), file=sys.stderr)
    else:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
