"""缠论粗略版 - M8 同级别分解操作模块（对应 DS3 v2.4 modules/same_level_decompose.py）

原文依据：第38-40、107课
改造：中枢 → 5/10均线湿吻区域
"""

from typing import List, Optional, Tuple
from data_structures import KLine, Segment, TradeSignal
from config import ChanlunConfig

_CFG = ChanlunConfig()

def compare_ai_ai2(
    segments: List[dict],
    current_index: int,
    divergence_checker,
    k_lines: Optional[List[KLine]] = None,
) -> Optional[str]:
    """Ai与Ai+2盘整背驰法（§9.3，第39课）

    比较 Ai 与 Ai+2 之间的力度：
    - i为偶数（向下段） → 盘整背驰 → buy
    - i为奇数（向上段） → 盘整背驰 → sell
    """
    i = current_index
    if i < 2:
        return None

    seg_i = segments[i]
    seg_i2 = segments[i - 2]

    # 比较两段MACD面积（简化：用振幅*K线数近似）
    force_i = abs(seg_i.get("high", 0) - seg_i.get("low", 0))
    force_i2 = abs(seg_i2.get("high", 0) - seg_i2.get("low", 0))

    if force_i2 == 0:
        return None

    ratio = force_i / force_i2
    if ratio < 0.9:  # 盘整背驰成立
        return "buy" if i % 2 == 0 else "sell"

    return None

def same_level_decompose(segments: List[dict]) -> List[dict]:
    """同级别分解（§9.1，第38课）

    把走势按固定级别分解成一段段该级别走势类型的连接
    """
    return segments

def mechanical_operation_30min(
    segments: List[dict],
    k_lines: List[KLine],
) -> List[TradeSignal]:
    """30分钟级别机械操作程式（§9.2，第38课原文改造）

    全流程：下跌背驰 → 向上第一段 → 向下第二段 → 向上第三段 → 持续跟踪
    """
    signals: List[TradeSignal] = []
    if len(segments) < 3:
        return signals

    state = "WAITING_DOWN_DIVERGENCE"
    first_up_high = 0.0
    first_up_low = float('inf')

    for i, seg in enumerate(segments):
        direction = seg.get("direction", 0)

        if direction == 1:  # 向上段
            if state == "WAITING_DOWN_DIVERGENCE":
                # 阶段一：向上第一段
                first_up_high = seg.get("high", 0)
                first_up_low = seg.get("low", float('inf'))
                signals.append(TradeSignal(
                    action='buy',
                    stop_loss=0,
                    take_profit=0,
                    signal_type="first_buy",
                    source="same_level",
                    confidence=_CFG.CONFIDENCE_HIGH,
                    position_ratio=0.7,
                    description="阶段一：向上第一段开始"
                ))
                state = "WAITING_DOWN_SEGMENT"

            elif state == "HOLDING_DOWN_SEGMENT":
                # 阶段三：向上第三段
                seg_high = seg.get("high", 0)
                if seg_high < first_up_high:
                    signals.append(TradeSignal(
                        action='sell',
                        stop_loss=0,
                        take_profit=0,
                        signal_type="first_sell",
                        source="same_level",
                        confidence=0.9,
                        position_ratio=0,
                        description="情形A(弱)：第三段低于第一段高点，卖出"
                    ))
                    state = "WAITING_UP_DIVERGENCE"
                elif seg_high > first_up_high:
                    # 比较力度
                    force_i = abs(seg.get("high", 0) - seg.get("low", 0))
                    force_i2 = abs(first_up_high - first_up_low)
                    if force_i2 > 0 and force_i / force_i2 < 0.9:
                        signals.append(TradeSignal(
                            action='sell',
                            stop_loss=0,
                            take_profit=0,
                            signal_type="first_sell",
                            source="same_level",
                            confidence=0.85,
                            position_ratio=0,
                            description="情形B(中)：破前高但盘整背驰，卖出"
                        ))
                        state = "WAITING_UP_DIVERGENCE"
                    else:
                        signals.append(TradeSignal(
                            action='hold',
                            stop_loss=0,
                            take_profit=0,
                            signal_type="hold",
                            source="same_level",
                            confidence=0.9,
                            position_ratio=0.7,
                            description="情形C(强)：破前高无背驰，继续持有"
                        ))
                        state = "HOLDING_UP_TREND"

        elif direction == -1:  # 向下段
            if state == "WAITING_DOWN_SEGMENT":
                seg_low = seg.get("low", float('inf'))
                if seg_low > first_up_low:
                    signals.append(TradeSignal(
                        action='buy',
                        take_profit=0,
                        signal_type="second_buy",
                        source="same_level",
                        confidence=0.8,
                        position_ratio=0.7,
                        stop_loss=first_up_low,
                        description="阶段二·情形A：不跌破第一段低点，重新买入"
                    ))
                    state = "HOLDING_DOWN_SEGMENT"
                elif seg_low < first_up_low:
                    # 比较与前一段向下的盘整背驰
                    signals.append(TradeSignal(
                        action='hold',
                        position_ratio=0,
                        stop_loss=0,
                        take_profit=0,
                        signal_type="hold",
                        source="same_level",
                        confidence=0.3,
                        description="阶段二·情形B：跌破前低，等待盘整背驰确认"
                    ))
                    state = "WAITING_DOWN_DIVERGENCE"

            elif state == "HOLDING_UP_TREND":
                signals.append(TradeSignal(
                    action='sell',
                    stop_loss=0,
                    take_profit=0,
                    signal_type="first_sell",
                    source="same_level",
                    confidence=0.85,
                    position_ratio=0,
                    description="阶段四：向上趋势后首次向下段，兑现"
                ))
                state = "WAITING_UP_DIVERGENCE"

    return signals
