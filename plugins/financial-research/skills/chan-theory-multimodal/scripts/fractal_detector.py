"""缠论粗略版 - M3 分型识别模块（对应 DS3 v2.4 modules/fractal.py）

功能：分型识别、四档强弱判定(strongest/strong/medium/weak)、5日线配合、中继识别
⚠️ 分型检测用 StandardKLine，强度判定用原始 KLine（需要 open/close）
"""

from typing import List, Optional, Tuple
from data_structures import KLine, StandardKLine, Fractal, Pen
from config import ChanlunConfig

_CFG = ChanlunConfig()

# ============ M3.1 分型四档强度判定 ============

def assess_fractal_strength(
    k1: KLine, k2: KLine, k3: KLine,
    avg_amplitude: float,
    f_type: str,
) -> str:
    """分型强度四档判定：strongest / strong / medium / weak（DS3修正版）

    ⚠️ 参数为 KLine（有 open/close），非 StandardKLine
    """
    if f_type == "top":
        # 第一档：最强杀伤力 — k3跌破k1底且收不到k1区间一半之上
        if k3.low < k1.low and k3.close < (k1.high + k1.low) / 2:
            return "strongest"

        # 第二档：较强 — k2长上影/长阴 + k3收不到k2区间一半之上
        upper_shadow = k2.high - max(k2.open, k2.close)
        if (upper_shadow > (k2.high - k2.low) * _CFG.FRACTAL_STRONG_SHADOW_RATIO and
            k3.close < k3.open and
            k3.close < (k2.high + k2.low) / 2):
            return "strong"

        # 第三档：中继 — k1长阳 + k2、k3小阴小阳
        if ((k1.close - k1.open) > (k1.high - k1.low) * _CFG.FRACTAL_STRONG_BODY_RATIO and
            (k2.high - k2.low) < avg_amplitude * _CFG.FRACTAL_SMALL_AMPLITUDE_RATIO and
            (k3.high - k3.low) < avg_amplitude * _CFG.FRACTAL_SMALL_AMPLITUDE_RATIO):
            return "weak"

        return "medium"

    else:  # f_type == "bottom"
        # 第一档：最强 — k3升破k1高且收在k1区间一半之上
        if k3.high > k1.high and k3.close > (k1.high + k1.low) / 2:
            return "strongest"

        # 第二档：较强 — k2长下影/长阳 + k3收在k2区间一半之上
        lower_shadow = min(k2.open, k2.close) - k2.low
        if (lower_shadow > (k2.high - k2.low) * _CFG.FRACTAL_STRONG_SHADOW_RATIO and
            k3.close > k3.open and
            k3.close > (k2.high + k2.low) / 2):
            return "strong"

        # ⚠️ DS3新增：底分型中继（对称于顶分型）
        if ((k1.open - k1.close) > (k1.high - k1.low) * _CFG.FRACTAL_STRONG_BODY_RATIO and
            (k2.high - k2.low) < avg_amplitude * _CFG.FRACTAL_SMALL_AMPLITUDE_RATIO and
            (k3.high - k3.low) < avg_amplitude * _CFG.FRACTAL_SMALL_AMPLITUDE_RATIO):
            return "weak"

        return "medium"

# ============ M3.2 分型识别 ============

def detect_fractals(
    std_klines: List[StandardKLine],
    raw_klines: List[KLine],
) -> List[Fractal]:
    """识别并过滤分型序列

    ⚠️ 检测用 StandardKLine，强度判断用原始 KLine
    """
    if len(std_klines) < 3:
        return []

    fractals: List[Fractal] = []
    avg_amp = sum(k.high - k.low for k in std_klines) / len(std_klines)

    for i in range(1, len(std_klines) - 1):
        k1_std, k2_std, k3_std = std_klines[i - 1], std_klines[i], std_klines[i + 1]

        # 顶分型
        if (k2_std.high > k1_std.high and k2_std.high > k3_std.high and
            k2_std.low > k1_std.low and k2_std.low > k3_std.low):
            k1_raw = raw_klines[i - 1]
            k2_raw = raw_klines[i]
            k3_raw = raw_klines[i + 1]
            strength = assess_fractal_strength(k1_raw, k2_raw, k3_raw, avg_amp, "top")
            fractals.append(Fractal(
                type="top", index=i, timestamp=k2_std.time_end,
                high=k2_std.high, low=k2_std.low,
                strength=strength, is_confirmed=False,
                k_line_indices=[i - 1, i, i + 1],
            ))

        # 底分型
        elif (k2_std.low < k1_std.low and k2_std.low < k3_std.low and
              k2_std.high < k1_std.high and k2_std.high < k3_std.high):
            k1_raw = raw_klines[i - 1]
            k2_raw = raw_klines[i]
            k3_raw = raw_klines[i + 1]
            strength = assess_fractal_strength(k1_raw, k2_raw, k3_raw, avg_amp, "bottom")
            fractals.append(Fractal(
                type="bottom", index=i, timestamp=k2_std.time_end,
                high=k2_std.high, low=k2_std.low,
                strength=strength, is_confirmed=False,
                k_line_indices=[i - 1, i, i + 1],
            ))

    # 过滤连续同向分型，只保留最后一个
    filtered: List[Fractal] = []
    for f in fractals:
        if filtered and filtered[-1].type == f.type:
            filtered[-1] = f
        else:
            filtered.append(f)
    return filtered

# ============ M4 笔生成（原附录A，DS3对齐） ============

def build_pens(fractals: List[Fractal]) -> List[Pen]:
    """从分型列表生成笔序列（DS3对齐，返回 Pen 列表）"""
    if len(fractals) < 2:
        return []

    pens: List[Pen] = []
    for i in range(len(fractals) - 1):
        f1, f2 = fractals[i], fractals[i + 1]
        if f1.type != f2.type and abs(f2.index - f1.index) > 1:
            direction = 1 if f1.type == "bottom" else -1
            pens.append(Pen(
                direction=direction,
                start_fractal=f1,
                end_fractal=f2,
                start_time=f1.timestamp,
                end_time=f2.timestamp,
                high=max(f1.high, f2.high),
                low=min(f1.low, f2.low),
            ))
    return pens

def get_current_pen_state(
    pens: List[Pen],
    latest_fractal: Optional[Fractal],
) -> Tuple[int, int]:
    """获取当前笔状态：(direction, position)
    direction: 1=向上笔, -1=向下笔, 0=无
    position: 1=延伸中, 0=分型构造中
    """
    if not pens:
        return (0, 0)

    last_pen = pens[-1]
    if latest_fractal is None:
        return (last_pen.direction, 1)

    expected_type = "top" if last_pen.direction == 1 else "bottom"
    if (latest_fractal.type == expected_type and
        abs(latest_fractal.index - last_pen.end_fractal.index) > 1):
        return (last_pen.direction, 0)

    return (last_pen.direction, 1)

# ============ 5日线配合 + 中继识别（保留） ============

def is_effective_break(price: float, ma5_value: float, direction: str = "down") -> bool:
    """判断是否有效突破/跌破5日线"""
    ratio = _CFG.EFFECTIVE_BREAK_RATIO
    if direction == "down":
        return price < ma5_value * (1 - ratio)
    return price > ma5_value * (1 + ratio)

def check_ma5_cooperation(
    k_lines: List[StandardKLine],
    ma5_series: List[float],
    fractal: Fractal,
    fractal_idx: int,
) -> Tuple[bool, str]:
    """判断分型后的5日线配合情况"""
    if fractal_idx + 3 >= len(k_lines) or fractal_idx + 3 >= len(ma5_series):
        return False, "数据不足，无法判断3日确认"

    ma5_val = ma5_series[fractal_idx]
    ratio = _CFG.EFFECTIVE_BREAK_RATIO

    if fractal.type == "top":
        below_count = sum(1 for j in range(fractal_idx, min(fractal_idx + 4, len(k_lines)))
                          if k_lines[j].low < ma5_val)
        if below_count >= 3:
            return True, "有效跌破5日线（连续3日），大概率成笔"
        if k_lines[fractal_idx + 1].low < ma5_val * (1 - ratio):
            return True, "单根大幅偏离5日线超3%，有效跌破"
        return False, "未有效跌破5日线，中继可能性大"

    else:  # bottom
        above_count = sum(1 for j in range(fractal_idx, min(fractal_idx + 4, len(k_lines)))
                          if k_lines[j].high > ma5_val)
        if above_count >= 3:
            return True, "有效突破5日线（连续3日），90%以上会上涨到顶分型"
        if k_lines[fractal_idx + 1].high > ma5_val * (1 + ratio):
            return True, "单根大幅偏离5日线超3%，有效突破"
        return False, "未有效突破5日线，多为中继底分型"

def is_zhongji_fractal(
    fractal: Fractal,
    ma5_effective: bool,
    has_third_signal: Optional[bool] = None,
) -> Tuple[bool, str]:
    """判断分型是否为中继"""
    if not ma5_effective:
        return True, "5日线法：未有效突破，判定中继"
    if has_third_signal is False:
        return True, "小级别出现类似第三类买点信号 → 有效破坏该分型"
    if has_third_signal is True:
        return False, "小级别出现类似第三类卖点信号 → 100%该级别成笔"
    return False, "5日线已有效突破，看后续确认"
