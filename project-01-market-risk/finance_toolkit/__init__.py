"""
finance_toolkit — 零依赖的金融行情与风险分析工具。

模块：
    core   —— 行情获取、收益率、风险指标
    report —— Markdown 报告渲染

快速开始：
    python run_report.py --symbols "^GSPC" "QQQ" "MNQ=F" --range 2y
"""
__version__ = "0.1.0"

from .core import (  # noqa: F401
    Bar,
    Series,
    align_on_common_dates,
    annual_vol,
    build_series,
    cagr,
    calmar,
    compute_metrics,
    equal_weight_portfolio,
    fetch_prices,
    max_drawdown,
    return_correlation,
    sharpe,
    sortino,
    total_return,
    var_historical,
)
from .report import render_json, render_report, sparkline  # noqa: F401
