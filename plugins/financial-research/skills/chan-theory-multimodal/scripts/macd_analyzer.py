"""缠论粗略版 - M5 MACD计算模块（对应 DS3 v2.4 modules/macd.py）

原文依据：第24、25、27、37、43、44、106课
注意：本模块不涉及标准趋势背驰，仅使用盘整背驰。
"""

from typing import List, Tuple, Optional
from data_structures import KLine, MACDData, DivergenceResult, Segment
from config import ChanlunConfig

_CFG = ChanlunConfig()

# ============ MACD计算 ============

def EMA(data: List[float], period: int) -> List[float]:
    """指数移动平均（DS3附录A提供）"""
    ema = [data[0]] * len(data)
    k = 2.0 / (period + 1)
    for i in range(1, len(data)):
        ema[i] = data[i] * k + ema[i - 1] * (1 - k)
    return ema

def compute_macd(close_series: List[float]) -> Tuple[List[float], List[float], List[float]]:
    """计算MACD三线

    Returns: (dif, dea, hist)
    """
    ema12 = EMA(close_series, _CFG.MACD_FAST)
    ema26 = EMA(close_series, _CFG.MACD_SLOW)
    dif = [e12 - e26 for e12, e26 in zip(ema12, ema26)]
    dea = EMA(dif, _CFG.MACD_SIGNAL)
    hist = [2.0 * (d - e) for d, e in zip(dif, dea)]
    return dif, dea, hist

def get_macd_state(close_series: List[float], idx: int = -1) -> Optional[MACDData]:
    """获取当前MACD状态（DS3对齐）"""
    dif, dea, hist = compute_macd(close_series)
    if idx < 0:
        idx = len(dif) - 1
    if idx >= len(dif):
        return None

    cross_count = 0
    for i in range(1, idx + 1):
        if dif[i - 1] <= 0 < dif[i] or dif[i - 1] >= 0 > dif[i]:
            cross_count += 1

    return MACDData(
        diff=dif[idx],
        dea=dea[idx],
        hist=hist[idx],
        is_above_zero=dif[idx] > 0,
        zero_cross_count=cross_count,
    )

# ============ 盘整背驰判断 ============

def segment_macd_area(
    klines: List[KLine],
    seg: Segment,
) -> float:
    """计算某段的MACD柱子面积（DS3对齐，接受Segment）"""
    if seg.start_index >= len(klines) or seg.end_index >= len(klines):
        return 0.0
    close_series = [k.close for k in klines[seg.start_index:seg.end_index + 1]]
    _, _, hist = compute_macd(close_series)
    return sum(abs(h) for h in hist)

def check_plate_divergence(
    prev_seg: Segment,
    curr_seg: Segment,
    klines: List[KLine],
) -> DivergenceResult:
    """盘整背驰判断（DS3对齐，接受Segment + 返回DivergenceResult）"""
    area_prev = segment_macd_area(klines, prev_seg)
    area_curr = segment_macd_area(klines, curr_seg)

    if area_prev == 0:
        return DivergenceResult(
            is_divergence=False, area_ratio=1.0,
            confidence=0.0, description="参考段面积为0",
        )

    ratio = area_curr / area_prev
    is_div = ratio < _CFG.DIVERGENCE_AREA_RATIO
    conf = 1.0 - min(ratio / _CFG.DIVERGENCE_AREA_RATIO, 1.0) if is_div else 0.0

    return DivergenceResult(
        is_divergence=is_div,
        area_ratio=ratio,
        confidence=conf,
        description=f"{'背驰' if is_div else '未背驰'}, 面积比={ratio:.2f}",
    )

# ============ MACD定律 ============

def check_macd_law(
    macd_state: MACDData,
    divergence: bool,
    ma_position: str,
) -> Optional[str]:
    """缠中说禅MACD定律"""
    if ma_position == "男上位" and not macd_state.is_above_zero and divergence:
        return "first_buy"
    if ma_position == "女上位" and macd_state.is_above_zero and macd_state.zero_cross_count == 1:
        return "second_buy_candidate"
    if ma_position == "女上位" and macd_state.is_above_zero and divergence:
        return "first_sell"
    if ma_position == "男上位" and not macd_state.is_above_zero and macd_state.zero_cross_count == 1:
        return "second_sell_candidate"
    return None

# ============ 面积估算（第24课） ============

def get_decay_rate(hist_values: List[float], peak_index: int) -> float:
    """计算MACD柱伸长力度衰减率"""
    if peak_index < 3 or peak_index >= len(hist_values):
        return 1.0
    recent = [abs(hist_values[i]) for i in range(max(0, peak_index - 3), peak_index + 1)]
    if len(recent) < 2:
        return 1.0
    growth_rates = [
        recent[i] / recent[i - 1]
        for i in range(1, len(recent))
        if recent[i - 1] > 0
    ]
    if not growth_rates:
        return 1.0
    return min(sum(growth_rates) / len(growth_rates), 1.0)

def estimate_area(hist_values: List[float], peak_index: int) -> float:
    """实时预判MACD柱子总面积"""
    completed = sum(abs(v) for v in hist_values[:peak_index + 1])
    decay = get_decay_rate(hist_values, peak_index)
    if decay < 0.8:
        return completed * 2.0
    return completed * 1.5

# ============ 小背驰-大转折定理 ============

def check_minor_major_divergence(
    has_third_sell_signal: bool,
    has_third_buy_signal: bool,
    direction: str = "up",
) -> Tuple[bool, str]:
    """小背驰-大转折定理（必要条件检查）"""
    if direction == "up" and has_third_sell_signal:
        return True, "小级别顶背驰+第三类卖点信号 → 大级别向下必要条件满足"
    if direction == "down" and has_third_buy_signal:
        return True, "小级别底背驰+第三类买点信号 → 大级别向上必要条件满足"
    return False, "小背驰-大转折必要条件不满足"
