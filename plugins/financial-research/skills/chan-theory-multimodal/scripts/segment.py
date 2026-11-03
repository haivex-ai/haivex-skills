"""缠论粗略版 - M0 段识别模块（对应 DS3 v2.4 modules/segment.py）

基于5/10均线交叉点（湿吻）将走势分割为同向段。
是M6盘整背驰和M8同级别分解的前置依赖。
"""

from typing import List
from data_structures import KLine, Segment
from config import ChanlunConfig

def find_ma_cross_points(
    ma5_series: List[float],
    ma10_series: List[float],
) -> List[int]:
    """找出所有5/10均线交叉点索引"""
    crosses: List[int] = []
    for i in range(1, len(ma5_series)):
        if (ma5_series[i - 1] - ma10_series[i - 1]) * (ma5_series[i] - ma10_series[i]) < 0:
            crosses.append(i)
    return crosses

def identify_segments(
    klines: List[KLine],
    ma5_series: List[float],
    ma10_series: List[float],
    config: ChanlunConfig,
) -> List[Segment]:
    """基于均线湿吻交叉点将走势分割为同向段"""
    crosses = find_ma_cross_points(ma5_series, ma10_series)
    if len(crosses) < 2:
        return []

    segments: List[Segment] = []
    for i in range(len(crosses) - 1):
        start_idx = crosses[i]
        end_idx = crosses[i + 1] - 1
        if end_idx <= start_idx:
            continue
        direction = 1 if ma5_series[start_idx] > ma10_series[start_idx] else -1
        seg_klines = klines[start_idx:end_idx + 1]

        segment = Segment(
            direction=direction,
            start_index=start_idx,
            end_index=end_idx,
            start_time=klines[start_idx].time,
            end_time=klines[end_idx].time,
            high=max(k.high for k in seg_klines),
            low=min(k.low for k in seg_klines),
            macd_area=0.0,
        )
        segments.append(segment)

    return segments
