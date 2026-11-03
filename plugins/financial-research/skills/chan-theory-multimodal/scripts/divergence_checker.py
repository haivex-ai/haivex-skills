"""缠论粗略版 - 背驰三种判断方法（对应 DS3 M6）

原文依据：第12课（趋势力度法）、第24课（MACD法）
注意：简化为盘整背驰单一判定，MACD法见M5
"""

from typing import List, Tuple, Optional
from data_structures import KLine, Segment, DivergenceResult
from config import ChanlunConfig

_CFG = ChanlunConfig()

# ============ 11.1 趋势力度法（均线面积法） ============

def trend_force_area(
    kiss_start: int,
    kiss_end: int,
    short_ma: List[float],
    long_ma: List[float],
) -> float:
    """缠中说禅趋势力度（§11.1，第12课）

    前一吻结束到后一吻开始间，短期均线与长期均线相交所形成的面积
    """
    total_area = 0.0
    for i in range(kiss_start, min(kiss_end, len(short_ma), len(long_ma))):
        gap = abs(short_ma[i] - long_ma[i])
        total_area += gap
    return total_area

def check_divergence_by_area(prev_area: float, curr_area: float) -> bool:
    """均线面积法盘整背驰判断

    本段趋势力度 < 前段趋势力度 × 阈值 → 盘整背驰
    """
    if prev_area == 0:
        return False
    return curr_area < prev_area * _CFG.DIVERGENCE_AREA_RATIO

# ============ 11.2 趋势平均力度法（即时判断） ============

def check_divergence_by_avg_force(
    current_index: int,
    prev_kiss_end: int,
    short_ma: List[float],
    long_ma: List[float],
) -> Optional[str]:
    """缠中说禅趋势平均力度（§11.2，第12课）

    当下与前一吻结束时形成的面积除以时间。
    优势：即时判断，无需等待吻完成。
    """
    curr_start = prev_kiss_end
    curr_len = current_index - curr_start
    if curr_len < 5:
        return None

    curr_area = sum(
        abs(short_ma[i] - long_ma[i])
        for i in range(curr_start, min(current_index, len(short_ma), len(long_ma)))
    )
    curr_avg_force = curr_area / curr_len

    prev_len = min(curr_len * 2, curr_start)
    if prev_len <= 0:
        return None

    prev_area = sum(
        abs(short_ma[i] - long_ma[i])
        for i in range(max(0, curr_start - prev_len), min(curr_start, len(short_ma), len(long_ma)))
    )
    prev_avg_force = prev_area / prev_len if prev_len > 0 else float('inf')

    if prev_avg_force == 0:
        return None

    if curr_avg_force < prev_avg_force * _CFG.DIVERGENCE_AREA_RATIO:
        curr_gap = abs(short_ma[current_index] - long_ma[current_index])
        prev_gap = abs(short_ma[max(0, current_index - 3)] - long_ma[max(0, current_index - 3)])
        if curr_gap < prev_gap:
            return "背驰即将形成"

    return "正常"

# ============ 11.4 背驰综合评分 ============

def comprehensive_divergence(
    area_divergence: bool,
    avg_force_divergence: bool,
    macd_divergence: bool,
) -> str:
    """背驰综合评分（§11.4）

    三种方法综合：
    - ≥2种确认 → 背驰确认
    - 1种确认 → 疑似背驰
    - 0种 → 无背驰
    """
    score = sum([area_divergence, avg_force_divergence, macd_divergence])
    if score >= 2:
        return "背驰确认"
    elif score == 1:
        return "疑似背驰"
    else:
        return "无背驰"

# ============ 综合盘整背驰入口 ============

def check_comprehensive_divergence(
    segments: List[Segment],
    short_ma: List[float],
    long_ma: List[float],
    kiss_regions: List[Tuple[int, int]],
) -> Tuple[str, float]:
    """综合盘整背驰判断入口

    同时使用三种方法，返回综合结论
    """
    if len(segments) < 2 or len(kiss_regions) < 2:
        return "数据不足", 0.0

    seg_A = segments[-3] if len(segments) >= 3 else segments[-2]
    seg_C = segments[-1]

    # 方法1：MACD面积法
    macd_div = False
    if seg_A.macd_area > 0:
        macd_div = seg_C.macd_area < seg_A.macd_area * _CFG.DIVERGENCE_AREA_RATIO

    # 方法2：均线面积法
    area_prev = trend_force_area(
        kiss_regions[-2][0], kiss_regions[-2][1], short_ma, long_ma
    )
    area_curr = trend_force_area(
        kiss_regions[-1][0], kiss_regions[-1][1], short_ma, long_ma
    )
    area_div = check_divergence_by_area(area_prev, area_curr)

    # 方法3：平均力度法（用最新数据）
    avg_force_result = check_divergence_by_avg_force(
        len(short_ma) - 1, kiss_regions[-1][0], short_ma, long_ma
    )
    force_div = avg_force_result == "背驰即将形成"

    result = comprehensive_divergence(area_div, force_div, macd_div)

    # 计算置信度
    score = sum([area_div, force_div, macd_div])
    confidence = score / 3.0

    return result, confidence
