"""
finance_toolkit.charts — 零依赖 SVG 图表

为什么手写 SVG 而不装 matplotlib：
1. 客户拿到交付物不需要装环境，打开就能看；
2. 图表可内嵌进 HTML，也能单独存成 .svg 在浏览器/Office 里直接插入；
3. 不引入版本冲突。

所有函数返回 SVG 字符串（可直接写入 .svg 文件或嵌进 HTML）。
"""
from __future__ import annotations

import math
from html import escape
from typing import Callable, Sequence

PALETTE = [
    "#2563eb", "#dc2626", "#16a34a", "#d97706",
    "#7c3aed", "#0891b2", "#be185d", "#4b5563",
]

_FONT = ('font-family="' + "'Segoe UI',system-ui,-apple-system,'PingFang SC','Microsoft YaHei',sans-serif" + '"')


# ---------------------------------------------------------------- 基础工具

def _nice_ticks(lo: float, hi: float, count: int = 5) -> list[float]:
    """在 [lo, hi] 上生成整齐的刻度值。"""
    if hi == lo:
        return [lo]
    span = hi - lo
    raw = span / max(count - 1, 1)
    mag = 10 ** math.floor(math.log10(abs(raw))) if raw else 1
    for m in (1, 2, 2.5, 5, 10):
        step = m * mag
        if step >= raw:
            break
    start = math.floor(lo / step) * step
    ticks = []
    v = start
    while v <= hi + step * 0.5:
        if v >= lo - step * 0.5:
            ticks.append(round(v, 10))
        v += step
    return ticks


def _linear(d0: float, d1: float, r0: float, r1: float) -> Callable[[float], float]:
    if d1 == d0:
        return lambda _v: (r0 + r1) / 2
    k = (r1 - r0) / (d1 - d0)
    return lambda v: r0 + (v - d0) * k


def _default_fmt(v: float) -> str:
    if abs(v) >= 1000:
        return f"{v:,.0f}"
    if abs(v) >= 100:
        return f"{v:,.1f}"
    return f"{v:,.2f}"


def _pct_fmt(v: float) -> str:
    if abs(v) < 1e-12:      # 消除 -0.0% 这种负零显示
        v = 0.0
    return f"{v * 100:.1f}%"


def _svg(width: int, height: int, body: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img">'
        f'<rect width="{width}" height="{height}" fill="#ffffff"/>'
        f"{body}</svg>"
    )


def _text(x: float, y: float, s: str, size: int = 12, anchor: str = "middle",
          fill: str = "#4b5563", weight: str = "normal") -> str:
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" text-anchor="{anchor}" '
        f'fill="{fill}" font-weight="{weight}" {_FONT}>{escape(str(s))}</text>'
    )


def _frame(width: int, height: int, title: str, left: int, right: int,
           top: int, bottom: int) -> tuple[float, float, float, float, str]:
    plot_l, plot_r = left, width - right
    plot_t, plot_b = top, height - bottom
    parts = []
    if title:
        parts.append(_text(width / 2, 22, title, 14, "middle", "#111827", "600"))
    parts.append(
        f'<rect x="{plot_l}" y="{plot_t}" width="{plot_r - plot_l}" '
        f'height="{plot_b - plot_t}" fill="none" stroke="#e5e7eb" stroke-width="1"/>'
    )
    return plot_l, plot_r, plot_t, plot_b, "".join(parts)


# ---------------------------------------------------------------- 折线图

def line_chart(
    series: Sequence[dict],
    width: int = 880,
    height: int = 340,
    title: str = "",
    y_fmt: Callable[[float], str] = _default_fmt,
    x_labels: Sequence[str] | None = None,
    normalize: bool = False,
    y_zero: bool = False,
) -> str:
    """
    折线图。

    series: [{"label": "QQQ", "values": [1.0, 1.02, ...]}, ...]
    normalize: 每条序列按首值归一到 1.0，便于比较走势。
    """
    if not series or not series[0].get("values"):
        return _svg(width, height, _text(width / 2, height / 2, "无数据"))

    data = []
    for i, s in enumerate(series):
        vals = list(s["values"])
        if normalize and vals and vals[0]:
            base = vals[0]
            vals = [v / base for v in vals]
        data.append({
            "label": s.get("label", f"series {i + 1}"),
            "values": vals,
            "color": s.get("color") or PALETTE[i % len(PALETTE)],
        })

    n = max(len(d["values"]) for d in data)
    flat = [v for d in data for v in d["values"] if v is not None]
    lo, hi = min(flat), max(flat)
    if y_zero:
        lo, hi = min(lo, 0.0), max(hi, 0.0)
    pad = (hi - lo) * 0.08 or (abs(hi) * 0.1 or 1.0)
    lo, hi = lo - pad, hi + pad

    plot_l, plot_r, plot_t, plot_b, frame = _frame(width, height, title, 72, 24, 46, 56)
    y = _linear(lo, hi, plot_b, plot_t)
    x = _linear(0, max(n - 1, 1), plot_l, plot_r)

    parts = [frame]

    ticks = _nice_ticks(lo, hi, 5)
    for t in ticks:
        yy = y(t)
        parts.append(f'<line x1="{plot_l}" y1="{yy:.1f}" x2="{plot_r}" y2="{yy:.1f}" '
                     f'stroke="#f3f4f6" stroke-width="1"/>')
        parts.append(_text(plot_l - 8, yy + 4, y_fmt(t), 11, "end"))

    if x_labels:
        step = max(1, len(x_labels) // 6)
        for i in range(0, len(x_labels), step):
            parts.append(_text(x(i), plot_b + 18, x_labels[i], 10, "middle", "#9ca3af"))

    for d in data:
        pts = " ".join(
            f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(d["values"]) if v is not None
        )
        parts.append(f'<polyline points="{pts}" fill="none" stroke="{d["color"]}" '
                     f'stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>')

    # 图例
    lx = plot_l
    for d in data:
        parts.append(f'<rect x="{lx:.0f}" y="{plot_t - 20}" width="10" height="10" '
                     f'fill="{d["color"]}" rx="2"/>')
        parts.append(_text(lx + 15, plot_t - 11, d["label"], 11, "start", "#374151"))
        lx += 24 + 7 * len(str(d["label"])) + 18

    return _svg(width, height, "".join(parts))


# ---------------------------------------------------------------- 回撤图

def drawdown_chart(prices: Sequence[float], width: int = 880, height: int = 240,
                   title: str = "回撤", x_labels: Sequence[str] | None = None) -> str:
    """从价格序列计算并绘制回撤曲线（填充到 0 轴下方）。"""
    if not prices:
        return _svg(width, height, _text(width / 2, height / 2, "无数据"))

    peak = prices[0]
    dd = []
    for v in prices:
        peak = max(peak, v)
        dd.append(v / peak - 1.0)

    worst_val = min(dd)          # 用真实最小值，避免浮点误差反查失败
    worst_idx = dd.index(worst_val)
    lo = worst_val
    hi = 0.0
    pad = (hi - lo) * 0.08 or 0.01
    lo -= pad

    plot_l, plot_r, plot_t, plot_b, frame = _frame(width, height, title, 72, 24, 46, 46)
    y = _linear(lo, hi, plot_b, plot_t)
    n = len(dd)
    x = _linear(0, max(n - 1, 1), plot_l, plot_r)

    parts = [frame]
    for t in _nice_ticks(lo, hi, 4):
        yy = y(t)
        parts.append(f'<line x1="{plot_l}" y1="{yy:.1f}" x2="{plot_r}" y2="{yy:.1f}" '
                     f'stroke="#f3f4f6" stroke-width="1"/>')
        parts.append(_text(plot_l - 8, yy + 4, _pct_fmt(t), 11, "end"))

    pts = [f"{x(0):.1f},{y(0):.1f}"] + [f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(dd)]
    pts.append(f"{x(n - 1):.1f},{y(0):.1f}")
    parts.append(f'<polygon points="{" ".join(pts)}" fill="#fecaca" opacity="0.65"/>')
    parts.append('<polyline points="' + " ".join(
        f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(dd)
    ) + '" fill="none" stroke="#dc2626" stroke-width="1.6"/>')

    worst_i = worst_idx
    parts.append(_text(x(worst_i), y(dd[worst_i]) - 8, _pct_fmt(dd[worst_i]), 11,
                       "middle", "#b91c1c", "600"))

    if x_labels:
        step = max(1, len(x_labels) // 6)
        for i in range(0, len(x_labels), step):
            parts.append(_text(x(i), plot_b + 16, x_labels[i], 10, "middle", "#9ca3af"))

    return _svg(width, height, "".join(parts))


# ---------------------------------------------------------------- 柱状图

def bar_chart(values: Sequence[float], labels: Sequence[str], width: int = 880,
              height: int = 260, title: str = "", fmt: Callable[[float], str] = _pct_fmt) -> str:
    """柱状图，支持正负值（零轴居中）。"""
    if not values:
        return _svg(width, height, _text(width / 2, height / 2, "无数据"))

    lo, hi = min(min(values), 0.0), max(max(values), 0.0)
    pad = (hi - lo) * 0.12 or 0.01
    lo, hi = lo - pad if lo < 0 else 0.0, hi + pad if hi > 0 else 0.0

    plot_l, plot_r, plot_t, plot_b, frame = _frame(width, height, title, 72, 24, 46, 56)
    y = _linear(lo, hi, plot_b, plot_t)
    n = len(values)
    slot = (plot_r - plot_l) / max(n, 1)
    bar_w = min(slot * 0.68, 42)

    parts = [frame]
    for t in _nice_ticks(lo, hi, 4):
        yy = y(t)
        parts.append(f'<line x1="{plot_l}" y1="{yy:.1f}" x2="{plot_r}" y2="{yy:.1f}" '
                     f'stroke="#f3f4f6"/>')
        parts.append(_text(plot_l - 8, yy + 4, fmt(t), 11, "end"))

    zero_y = y(0.0)
    parts.append(f'<line x1="{plot_l}" y1="{zero_y:.1f}" x2="{plot_r}" y2="{zero_y:.1f}" '
                 f'stroke="#9ca3af" stroke-width="1"/>')

    for i, v in enumerate(values):
        cx = plot_l + slot * (i + 0.5)
        top = y(max(v, 0.0))
        bot = y(min(v, 0.0))
        color = "#16a34a" if v >= 0 else "#dc2626"
        parts.append(f'<rect x="{cx - bar_w / 2:.1f}" y="{top:.1f}" width="{bar_w:.1f}" '
                     f'height="{max(bot - top, 0.5):.1f}" fill="{color}" rx="2"/>')

    step = max(1, n // 10)
    for i in range(0, n, step):
        parts.append(_text(plot_l + slot * (i + 0.5), plot_b + 18, labels[i], 10,
                           "middle", "#9ca3af"))

    return _svg(width, height, "".join(parts))


# ---------------------------------------------------------------- 热力图

def heatmap(matrix: Sequence[Sequence[float]], row_labels: Sequence[str],
            col_labels: Sequence[str], width: int = 620, height: int = 460,
            title: str = "", legend: str = "相关系数") -> str:
    """
    相关性热力图。

    配色按**实际数据范围**映射，而不是固定 -1~1：
    相关性普遍偏高时（例如都>0.9），固定色阶会让整张图变成一块同色，毫无信息量。
    """
    rows = len(matrix)
    cols = len(matrix[0]) if matrix else 0
    if not rows or not cols:
        return _svg(width, height, _text(width / 2, height / 2, "无数据"))

    vals = [float(matrix[i][j]) for i in range(rows) for j in range(cols)]
    vmin, vmax = min(vals), max(vals)
    all_pos = vmin >= 0
    span = vmax - vmin if vmax > vmin else 1.0

    LIGHT = (241, 245, 249)
    BLUE = (29, 78, 216)
    RED = (185, 28, 28)

    def _lerp(c1, c2, t):
        t = 0.0 if t < 0 else (1.0 if t > 1 else t)
        return tuple(int(round(c1[k] + (c2[k] - c1[k]) * t)) for k in range(3))

    def cell_rgb(v: float) -> tuple:
        if all_pos:
            return _lerp(LIGHT, BLUE, (v - vmin) / span)
        m = max(abs(vmin), abs(vmax)) or 1.0
        return _lerp(LIGHT, BLUE, v / m) if v >= 0 else _lerp(LIGHT, RED, -v / m)

    def on_color(rgb: tuple) -> str:
        lum = 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]
        return "#ffffff" if lum < 145 else "#111827"

    head = 52 if title else 26
    legend_h = 46
    plot_l, plot_r, plot_t, plot_b, frame = _frame(
        width, height, title, 92, 24, head, legend_h + 30
    )
    cw = (plot_r - plot_l) / cols
    ch = (plot_b - plot_t) / rows

    parts = [frame]
    for i in range(rows):
        for j in range(cols):
            v = float(matrix[i][j])
            rgb = cell_rgb(v)
            x0 = plot_l + j * cw
            y0 = plot_t + i * ch
            parts.append(
                f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{cw:.1f}" height="{ch:.1f}" '
                f'fill="rgb({rgb[0]},{rgb[1]},{rgb[2]})" stroke="#ffffff" stroke-width="1.5"/>'
            )
            parts.append(_text(x0 + cw / 2, y0 + ch / 2 + 4, f"{v:.2f}", 12,
                               "middle", on_color(rgb), "600"))

    for j, lab in enumerate(col_labels):
        parts.append(_text(plot_l + cw * (j + 0.5), plot_t - 10, lab, 11, "middle", "#374151"))
    for i, lab in enumerate(row_labels):
        parts.append(_text(plot_l - 8, plot_t + ch * (i + 0.5) + 4, lab, 11, "end", "#374151"))

    # ---- 图例：渐变条 + 端点标签
    lx0, lx1 = plot_l, plot_l + min(280, (plot_r - plot_l) * 0.55)
    ly = plot_b + 18
    steps = 48
    for k in range(steps):
        t = k / (steps - 1)
        val = vmin + (vmax - vmin) * t
        rgb = cell_rgb(val)
        seg = (lx1 - lx0) / steps
        parts.append(
            f'<rect x="{lx0 + seg * k:.1f}" y="{ly}" width="{seg + 0.6:.1f}" height="9" '
            f'fill="rgb({rgb[0]},{rgb[1]},{rgb[2]})"/>'
        )
    parts.append(f'<rect x="{lx0}" y="{ly}" width="{lx1 - lx0:.1f}" height="9" '
                 f'fill="none" stroke="#e5e7eb"/>')
    parts.append(_text(lx0, ly + 24, f"{vmin:.2f}", 10, "middle", "#6b7280"))
    parts.append(_text((lx0 + lx1) / 2, ly + 24, legend, 10, "middle", "#6b7280"))
    parts.append(_text(lx1, ly + 24, f"{vmax:.2f}", 10, "middle", "#6b7280"))

    return _svg(width, height, "".join(parts))


# ---------------------------------------------------------------- 迷你曲线

_BLOCKS = "▁▂▃▄▅▆▇█"


def sparkline_text(values: Sequence[float], width: int = 60) -> str:
    """纯文本迷你曲线，适合放进 Markdown 表格。"""
    if not values:
        return ""
    vals = list(values)
    if len(vals) > width:
        idx = [int(i * (len(vals) - 1) / (width - 1)) for i in range(width)]
        vals = [vals[i] for i in idx]
    lo, hi = min(vals), max(vals)
    if hi == lo:
        return _BLOCKS[0] * len(vals)
    return "".join(_BLOCKS[int(round((v - lo) / (hi - lo) * (len(_BLOCKS) - 1)))] for v in vals)
