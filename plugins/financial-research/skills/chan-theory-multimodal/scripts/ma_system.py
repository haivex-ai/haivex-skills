"""缠论粗略版 - M2 均线计算模块（对应 DS3 v2.4 modules/ma.py）

实现：体位判断、吻分类(飞吻/唇吻/湿吻)、缠绕次数统计、走势类型判定
"""

from typing import List, Optional
from data_structures import KLine, MACrossState, TradeSignal
from config import ChanlunConfig

# 默认配置实例
_CFG = ChanlunConfig()

def calc_sma(prices: List[float], period: int) -> List[float]:
    """计算简单移动平均线"""
    result = []
    for i in range(len(prices)):
        if i < period - 1:
            result.append(0.0)
        else:
            avg = sum(prices[i - period + 1:i + 1]) / period
            result.append(avg)
    return result

def calc_ma(k_lines: List[KLine], period: int) -> List[float]:
    """从K线序列计算均线值"""
    closes = [k.close for k in k_lines]
    return calc_sma(closes, period)

def determine_position(short_ma: float, long_ma: float) -> str:
    """判断体位：女上位=短期>=长期, 男上位=短期<长期"""
    return "女上位" if short_ma >= long_ma else "男上位"

def classify_kiss(
    short_ma_series: List[float],
    long_ma_series: List[float],
    index: int,
) -> tuple:
    """吻分类算法（DS3修正版）

    返回: (kiss_type, is_completed)
    正确阈值顺序: gap>FLY→无 | FLY≥gap>LIP→飞吻 | LIP≥gap>WET→唇吻 | WET≥gap且穿越→湿吻
    """
    if index < 1 or index >= len(short_ma_series):
        return "无", False

    current_short = short_ma_series[index]
    current_long = long_ma_series[index]
    prev_short = short_ma_series[index - 1]
    prev_long = long_ma_series[index - 1]

    # 湿吻：穿越（发生交叉）
    if (prev_short >= prev_long and current_short < current_long) or \
       (prev_short <= prev_long and current_short > current_long):
        return "湿吻", True

    if current_long == 0:
        return "无", False

    gap_ratio = abs(current_short - current_long) / current_long

    # 按 DS3 正确顺序
    if gap_ratio <= _CFG.KISS_FLY_RATIO:
        if gap_ratio > _CFG.KISS_LIP_RATIO:
            # FLY ≥ gap > LIP → 飞吻
            return "飞吻", False
        elif gap_ratio > _CFG.KISS_WET_RATIO:
            # LIP ≥ gap > WET → 唇吻
            return "唇吻", False
        else:
            # WET ≥ gap → 唇吻（未穿越，如果是穿越已在前面返回）
            return "唇吻", False

    return "无", False

def calc_kiss_count(
    short_ma_series: List[float],
    long_ma_series: List[float],
    index: int,
) -> int:
    """计算当前体位下的缠绕次数（DS3新增）
    
    从当前位置向前回溯，统计同体位下发生穿越(吻)的次数。
    体位切换时计数器重置。
    """
    if index < 0 or index >= len(short_ma_series):
        return 0

    # 构建体位历史
    pos_history: List[str] = []
    for i in range(min(index, len(short_ma_series))):
        s, l = short_ma_series[i], long_ma_series[i]
        if s > 0 and l > 0:
            pos_history.append(determine_position(s, l))

    if not pos_history:
        return 0

    current_pos = pos_history[-1]
    count = 0
    for i in range(len(pos_history) - 1, -1, -1):
        if pos_history[i] == current_pos:
            count += 1
        else:
            break
    return count

def count_kisses(position_history: List[str], current_index: int) -> int:
    """（兼容旧接口）统计当前体位下的缠绕次数"""
    if current_index < 0 or current_index >= len(position_history):
        return 0
    current_pos = position_history[current_index]
    count = 0
    for i in range(current_index, -1, -1):
        if position_history[i] == current_pos:
            count += 1
        else:
            break
    return count

def is_sharp_drop(prices: List[float], lookback: int = 5, threshold: float = -0.03) -> bool:
    """判断是否出现急跌"""
    if len(prices) < lookback + 1:
        return False
    drop_ratio = (prices[-1] - prices[-lookback - 1]) / prices[-lookback - 1]
    return drop_ratio <= threshold

def is_ma_strong(short_ma_series: List[float], lookback: int = 10) -> bool:
    """判断短期均线走势是否有力"""
    if len(short_ma_series) < lookback + 1:
        return False
    slope = (short_ma_series[-1] - short_ma_series[-lookback - 1]) / lookback
    return slope > _CFG.MA_SLOPE_WINDOW  # 用MA_SLOPE_WINDOW作斜率阈值

def is_volume_too_high(volumes: List[float], lookback: int = 20) -> bool:
    """判断成交量是否过大"""
    if len(volumes) < lookback + 5:
        return False
    avg_vol = sum(volumes[-lookback:-5]) / (lookback - 5) if lookback > 5 else 0
    if avg_vol == 0:
        return False
    recent_vol = sum(volumes[-5:]) / 5
    return recent_vol > avg_vol * 2.0  # 放量超过2倍为过大

def get_ma_state(k_lines: List[KLine], index: int = -1) -> MACrossState:
    """获取当前均线状态（DS3对齐）"""
    short_ma_series = calc_ma(k_lines, _CFG.SHORT_MA)
    long_ma_series = calc_ma(k_lines, _CFG.LONG_MA)

    if index < 0:
        index = len(short_ma_series) - 1

    if (index < 0 or index >= len(short_ma_series)
            or short_ma_series[index] == 0 or long_ma_series[index] == 0):
        return MACrossState(
            short_ma=0.0, long_ma=0.0, position="未知", kiss_type="无",
            kiss_count=0, slope_short=0.0, slope_long=0.0,
        )

    short_val = short_ma_series[index]
    long_val = long_ma_series[index]
    position = determine_position(short_val, long_val)
    kiss_type, _ = classify_kiss(short_ma_series, long_ma_series, index)
    kiss_count = calc_kiss_count(short_ma_series, long_ma_series, index)

    # 斜率
    if index >= _CFG.MA_SLOPE_WINDOW:
        short_base = short_ma_series[index - _CFG.MA_SLOPE_WINDOW]
        long_base = long_ma_series[index - _CFG.MA_SLOPE_WINDOW]
        slope5 = ((short_ma_series[index] - short_base) / short_base
                  if short_base != 0 else 0.0)
        slope10 = ((long_ma_series[index] - long_base) / long_base
                   if long_base != 0 else 0.0)
    else:
        slope5, slope10 = 0.0, 0.0

    return MACrossState(
        short_ma=short_val,
        long_ma=long_val,
        position=position,
        kiss_type=kiss_type,
        kiss_count=kiss_count,
        slope_short=slope5,
        slope_long=slope10,
    )

def is_first_buy_point(ma_state: MACrossState, is_divergence: bool, prices: List[float]) -> TradeSignal:
    """第一类买点判定"""
    if ma_state.position != "男上位":
        return TradeSignal(action="hold", signal_type="hold", source="ma",
                           confidence=0, position_ratio=0, stop_loss=0,
                           take_profit=0, description="不在男上位状态")

    if ma_state.kiss_count < 2:
        return TradeSignal(action="hold", signal_type="hold", source="ma",
                           confidence=0, position_ratio=0, stop_loss=0,
                           take_profit=0,
                           description="男上位第1次缠绕肯定不是最后一次，等待第2次及以上缠绕")

    if not is_sharp_drop(prices):
        return TradeSignal(action="hold", signal_type="hold", source="ma",
                           confidence=0, position_ratio=0, stop_loss=0,
                           take_profit=0, description="未出现急跌")

    if not is_divergence:
        return TradeSignal(action="hold", signal_type="hold", source="ma",
                           confidence=0, position_ratio=0, stop_loss=0,
                           take_profit=0, description="未出现背驰")

    return TradeSignal(
        action="buy",
        signal_type="first_buy",
        source="ma",
        confidence=_CFG.CONFIDENCE_HIGH,
        position_ratio=_CFG.POSITION_HIGH_CONFIDENCE,
        stop_loss=0,
        take_profit=0,
        description="第一类买点：男上位第{}次缠绕+急跌+背驰".format(ma_state.kiss_count)
    )

def is_second_buy_point(ma_state: MACrossState, volumes: List[float],
                         short_ma_series: List[float]) -> TradeSignal:
    """第二类买点判定"""
    if ma_state.position != "女上位":
        return TradeSignal(action="hold", signal_type="hold", source="ma",
                           confidence=0, position_ratio=0, stop_loss=0,
                           take_profit=0, description="不在女上位状态")

    if ma_state.kiss_count != 1:
        return TradeSignal(action="hold", signal_type="hold", source="ma",
                           confidence=0, position_ratio=0, stop_loss=0,
                           take_profit=0, description="必须是第1次缠绕")

    if not is_ma_strong(short_ma_series):
        return TradeSignal(action="hold", signal_type="hold", source="ma",
                           confidence=0, position_ratio=0, stop_loss=0,
                           take_profit=0, description="缠绕前5日线走势疲软")

    if is_volume_too_high(volumes):
        return TradeSignal(action="hold", signal_type="hold", source="ma",
                           confidence=0, position_ratio=0, stop_loss=0,
                           take_profit=0, description="成交量放得过大")

    return TradeSignal(
        action="buy",
        signal_type="second_buy",
        source="ma",
        confidence=_CFG.CONFIDENCE_MEDIUM,
        position_ratio=_CFG.POSITION_MEDIUM_CONFIDENCE,
        stop_loss=0,
        take_profit=0,
        description="第二类买点：女上位第1次缠绕+均线有力+量能正常"
    )

def is_first_sell_point(ma_state: MACrossState, is_divergence: bool) -> TradeSignal:
    """第一类卖点判定"""
    if ma_state.position != "女上位":
        return TradeSignal(action="hold", signal_type="hold", source="ma",
                           confidence=0, position_ratio=0, stop_loss=0,
                           take_profit=0, description="不在女上位状态")

    if not is_divergence:
        return TradeSignal(action="hold", signal_type="hold", source="ma",
                           confidence=0, position_ratio=0, stop_loss=0,
                           take_profit=0, description="未出现背驰")

    return TradeSignal(
        action="sell",
        signal_type="first_sell",
        source="ma",
        confidence=_CFG.CONFIDENCE_HIGH,
        position_ratio=0,
        stop_loss=0,
        take_profit=0,
        description="第一类卖点：女上位缠绕后出现背驰"
    )

def is_second_sell_point(ma_state: MACrossState) -> TradeSignal:
    """第二类卖点判定"""
    if ma_state.position != "男上位":
        return TradeSignal(action="hold", signal_type="hold", source="ma",
                           confidence=0, position_ratio=0, stop_loss=0,
                           take_profit=0, description="不在男上位状态")

    if ma_state.kiss_count != 1:
        return TradeSignal(action="hold", signal_type="hold", source="ma",
                           confidence=0, position_ratio=0, stop_loss=0,
                           take_profit=0, description="必须为男上位后第一次缠绕")

    return TradeSignal(
        action="sell",
        signal_type="second_sell",
        source="ma",
        confidence=_CFG.CONFIDENCE_MEDIUM,
        position_ratio=0,
        stop_loss=0,
        take_profit=0,
        description="第二类卖点：男上位第一次缠绕高点"
    )

# ============ §4.6 / 附录B 走势类型的均线定义 ============

def trend_type_by_ma(
    ma5_series: List[float],
    ma10_series: List[float],
    lookback: int = 20,
) -> str:
    """基于5/10均线定义当前走势类型"""
    if len(ma5_series) < 5:
        return "range"

    def _slope(series, offset=3):
        if len(series) < offset + 1:
            return 0.0
        denom = series[-offset - 1]
        if denom == 0:
            return 0.0
        return (series[-1] - denom) / denom

    ma5_slope = _slope(ma5_series)
    ma10_slope = _slope(ma10_series)

    if (ma5_series[-1] > ma10_series[-1] and
        ma5_slope > 0.001 and ma10_slope > 0.001 and
        all(ma5_series[-i] > ma10_series[-i] for i in range(1, min(6, len(ma5_series))))):
        return "uptrend"

    if (ma5_series[-1] < ma10_series[-1] and
        ma5_slope < -0.001 and ma10_slope < -0.001):
        return "downtrend"

    return "range"
