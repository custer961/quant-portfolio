"""
finance_toolkit.core — 行情获取、收益率与风险指标计算。

设计原则
--------
1. 零第三方依赖：只用标准库 + numpy。
2. 数据源可替换：目前用 Yahoo Finance 的公开 chart 接口。
3. 所有指标函数接受「收盘价序列」，返回纯数值，便于单独测试。

用法
----
from finance_toolkit.core import fetch_prices, build_series, compute_metrics
rows = fetch_prices("^GSPC", range_="2y")
series = build_series(rows)
m = compute_metrics(series)
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np

TRADING_DAYS = 252
CACHE_DIR = Path(__file__).resolve().parent.parent / "cache"
_USER_AGENT = {"User-Agent": "Mozilla/5.0"}


# ---------------------------------------------------------------- 数据获取

@dataclass(frozen=True)
class Bar:
    """一根日线。"""
    date: str          # YYYY-MM-DD
    close: float


def _http_get(url: str, timeout: int = 25) -> bytes:
    req = urllib.request.Request(url, headers=_USER_AGENT)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def csv_name(symbol: str) -> str:
    """把行情代码转成安全的文件名：^GSPC -> GSPC, MNQ=F -> MNQ_F"""
    return "".join(c if c.isalnum() else "_" for c in symbol).strip("_")


def load_csv_prices(path: Path) -> list[Bar]:
    """读取本地 CSV（日期,收盘价），用于离线运行与可复现演示。"""
    bars: list[Bar] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.lower().startswith("date"):
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 2:
            continue
        try:
            bars.append(Bar(date=parts[0], close=float(parts[1])))
        except ValueError:
            continue
    if not bars:
        raise ValueError(f"{path}: CSV 中没有有效数据")
    return bars


def fetch_prices(symbol: str, range_: str = "2y", interval: str = "1d",
                 use_cache: bool = True, csv_dir: str | Path | None = None) -> list[Bar]:
    """
    从 Yahoo Finance 拉取日线收盘价。

    symbol 示例: ^GSPC（标普500）, QQQ, NQ=F（纳指期货）, MNQ=F（微型纳指）, GC=F（黄金）
    range_  : 1mo / 3mo / 6mo / 1y / 2y / 5y / max
    """
    # 优先使用本地 CSV：离线可复现，也避免在线数据源限流
    if csv_dir is not None:
        local = Path(csv_dir) / f"{csv_name(symbol)}.csv"
        if local.exists():
            return load_csv_prices(local)

    safe = urllib.parse.quote(symbol, safe="")
    cache_file = CACHE_DIR / f"{safe}_{range_}_{interval}.json"

    if use_cache and cache_file.exists():
        try:
            raw = json.loads(cache_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            raw = None
    else:
        raw = None

    if raw is None:
        url = (
            "https://query1.finance.yahoo.com/v8/finance/chart/"
            f"{safe}?range={range_}&interval={interval}"
        )
        try:
            raw = json.loads(_http_get(url).decode("utf-8", errors="replace"))
        except Exception as exc:
            raise RuntimeError(
                f"{symbol}: 取数失败（{type(exc).__name__}）。如果网络不可用或代理掉线，"
                f"可用 --csv-dir 指定本地 CSV 目录离线运行。"
            ) from exc
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(raw), encoding="utf-8")

    return _parse_yahoo(raw, symbol)


def _parse_yahoo(payload: dict, symbol: str) -> list[Bar]:
    """把 Yahoo chart 的 JSON 转成 Bar 列表，丢弃空收盘价。"""
    try:
        result = payload["chart"]["result"][0]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError(f"{symbol}: 返回结构异常 — {payload.get('chart', {}).get('error')}") from exc

    stamps: Sequence[int] = result.get("timestamp") or []
    closes: Sequence[float | None] = result["indicators"]["quote"][0].get("close") or []

    if len(stamps) != len(closes):
        raise ValueError(f"{symbol}: 时间戳与收盘价长度不一致")

    bars: list[Bar] = []
    for ts, close in zip(stamps, closes):
        if close is None:
            continue
        day = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
        bars.append(Bar(date=day, close=float(close)))

    if not bars:
        raise ValueError(f"{symbol}: 没有有效收盘价")
    return bars


# ---------------------------------------------------------------- 序列构建

@dataclass
class Series:
    """一条价格序列及其派生量。"""
    symbol: str
    dates: list[str]
    closes: np.ndarray

    @property
    def returns(self) -> np.ndarray:
        """简单日收益率（首日为 NaN 已剔除）。"""
        if len(self.closes) < 2:
            return np.empty(0)
        return np.diff(self.closes) / self.closes[:-1]

    def __len__(self) -> int:
        return len(self.closes)


def build_series(rows: Iterable[Bar], symbol: str = "") -> Series:
    rows = list(rows)
    return Series(
        symbol=symbol,
        dates=[b.date for b in rows],
        closes=np.array([b.close for b in rows], dtype=float),
    )


# ---------------------------------------------------------------- 风险指标

def cagr(series: Series) -> float:
    """年化复合增长率。"""
    n = len(series) - 1
    if n < 1 or series.closes[0] <= 0:
        return float("nan")
    return (series.closes[-1] / series.closes[0]) ** (TRADING_DAYS / n) - 1.0


def annual_vol(series: Series) -> float:
    r = series.returns
    return float(np.std(r, ddof=1) * np.sqrt(TRADING_DAYS)) if r.size > 1 else float("nan")


def sharpe(series: Series, rf: float = 0.0) -> float:
    """年化夏普。rf 为年化无风险利率。"""
    r = series.returns
    if r.size < 2:
        return float("nan")
    excess = r - rf / TRADING_DAYS
    sd = np.std(excess, ddof=1)
    return float(np.mean(excess) / sd * np.sqrt(TRADING_DAYS)) if sd > 0 else float("nan")


def sortino(series: Series, rf: float = 0.0) -> float:
    """年化索提诺比率（只惩罚下行波动）。"""
    r = series.returns
    if r.size < 2:
        return float("nan")
    excess = r - rf / TRADING_DAYS
    downside = excess[excess < 0]
    dd = np.std(downside, ddof=1) if downside.size > 1 else 0.0
    return float(np.mean(excess) / dd * np.sqrt(TRADING_DAYS)) if dd > 0 else float("nan")


def max_drawdown(series: Series) -> tuple[float, int, int]:
    """
    最大回撤。

    返回 (回撤幅度, 峰值索引, 谷值索引)，回撤幅度为负数，例如 -0.32 表示 -32%。
    """
    if len(series) < 2:
        return float("nan"), -1, -1
    peak = np.maximum.accumulate(series.closes)
    dd = series.closes / peak - 1.0
    trough = int(np.argmin(dd))
    peak_idx = int(np.argmax(series.closes[: trough + 1]))
    return float(dd[trough]), peak_idx, trough


def calmar(series: Series) -> float:
    """年化收益 / 最大回撤绝对值。"""
    mdd, _, _ = max_drawdown(series)
    c = cagr(series)
    return float(c / abs(mdd)) if mdd and not np.isnan(mdd) and mdd != 0 else float("nan")


def var_historical(series: Series, level: float = 0.95) -> float:
    """历史模拟法 VaR（日频），返回负数，例如 -0.025 表示单日 95% VaR 为 -2.5%。"""
    r = series.returns
    if r.size < 20:
        return float("nan")
    return float(np.percentile(r, (1.0 - level) * 100))


def total_return(series: Series) -> float:
    if len(series) < 2:
        return float("nan")
    return float(series.closes[-1] / series.closes[0] - 1.0)


def compute_metrics(series: Series, rf: float = 0.0) -> dict:
    """汇总所有指标。"""
    mdd, p_idx, t_idx = max_drawdown(series)
    r = series.returns
    return {
        "symbol": series.symbol,
        "bars": len(series),
        "start": series.dates[0] if series.dates else "",
        "end": series.dates[-1] if series.dates else "",
        "total_return": total_return(series),
        "cagr": cagr(series),
        "ann_vol": annual_vol(series),
        "sharpe": sharpe(series, rf),
        "sortino": sortino(series, rf),
        "max_drawdown": mdd,
        "mdd_peak_date": series.dates[p_idx] if p_idx >= 0 else "",
        "mdd_trough_date": series.dates[t_idx] if t_idx >= 0 else "",
        "calmar": calmar(series),
        "var95_daily": var_historical(series, 0.95),
        "skew": float(np.mean(((r - np.mean(r)) / np.std(r, ddof=1)) ** 3)) if r.size > 2 and np.std(r, ddof=1) > 0 else float("nan"),
    }


# ---------------------------------------------------------------- 多品种

def align_on_common_dates(series_list: list[Series]) -> tuple[list[str], np.ndarray]:
    """
    把多条序列对齐到共同交易日，返回 (日期, 价格矩阵[品种, 日期])。
    """
    common = set(series_list[0].dates)
    for s in series_list[1:]:
        common &= set(s.dates)
    dates = sorted(common)
    if not dates:
        raise ValueError("这些品种没有共同交易日")

    matrix = np.zeros((len(series_list), len(dates)), dtype=float)
    for i, s in enumerate(series_list):
        lookup = dict(zip(s.dates, s.closes))
        matrix[i, :] = [lookup[d] for d in dates]
    return dates, matrix


def return_correlation(series_list: list[Series]) -> np.ndarray:
    """基于共同交易日的日收益相关性矩阵。"""
    dates, matrix = align_on_common_dates(series_list)
    rets = np.diff(matrix, axis=1) / matrix[:, :-1]
    return np.corrcoef(rets)


def equal_weight_portfolio(series_list: list[Series]) -> Series:
    """
    等权组合序列：先对齐，再按等权重重建净值。
    仅用于快速对照，不计交易成本与再平衡摩擦。
    """
    dates, matrix = align_on_common_dates(series_list)
    normed = matrix / matrix[:, [0]]
    weights = np.full(len(series_list), 1.0 / len(series_list))
    curve = weights @ normed
    return Series(symbol="EW-Portfolio", dates=dates, closes=curve)


def to_dict(metrics: dict) -> dict:
    """把指标字典转成可 JSON 序列化的形式。"""
    return {k: (None if isinstance(v, float) and np.isnan(v) else v) for k, v in metrics.items()}
