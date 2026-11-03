"""缠论粗略版 - M12 实战陷阱检查模块（对应 DS3 v2.4 modules/traps.py）

包含：数据不足、极端行情、信号冲突、常见陷阱
"""

from typing import List, Tuple, Optional, Dict
from data_structures import KLine, StandardKLine, MACrossState, TradeSignal
from config import ChanlunConfig

_CFG = ChanlunConfig()

from typing import List, Tuple, Optional, Dict
from data_structures import KLine, StandardKLine, MACrossState, TradeSignal

# ============ §15.1 K线数据不足 ============

def check_data_sufficiency(
    k_lines: List[KLine],
    threshold: int = 50,
) -> Tuple[bool, str]:
    """K线数据充足性检查（§15.1）

    < 50根：无法有效计算均线和MACD
    < 20根：分型识别不可靠
    """
    if len(k_lines) < threshold:
        return False, f"K线数量不足{threshold}根，无法有效计算均线和MACD"
    if len(k_lines) < 20:
        return False, "K线数量不足20根，分型识别不可靠，仅输出均线体位"
    return True, "数据充足"

# ============ §15.2 极端行情 ============

def check_extreme_market(
    k_lines: List[KLine],
    recent_days: int = 3,
) -> Optional[str]:
    """极端行情检查（§15.2）

    连续一字涨停：不能用背驰看，改用1分钟均线湿吻区域判断
    """
    if len(k_lines) < recent_days:
        return None

    limit_up_count = 0
    for i in range(len(k_lines) - recent_days, len(k_lines)):
        k = k_lines[i]
        if k.open == k.high == k.low == k.close:
            continue
        if k.open > 0 and (k.close - k.open) / k.open > 0.095:
            limit_up_count += 1

    if limit_up_count >= recent_days:
        return "连续一字涨停，不能用MACD背驰判断，改用1分钟均线湿吻区域"

    return None

# ============ §15.3 信号冲突处理 ============

def resolve_signal_conflict(
    ma_position: str,
    fractal_type: Optional[str],
    fractal_strength: str,
    has_divergence: bool,
) -> TradeSignal:
    """信号冲突处理（§15.3）

    优先级：大级别分型 > 均线体位 > MACD背驰
    """
    # 分型+背驰综合确认
    if fractal_type == "bottom" and fractal_strength == "strong" and has_divergence:
        return TradeSignal(
            action='buy',
            stop_loss=0,
            take_profit=0,
            signal_type="first_buy" if ma_position == "男上位" else "second_buy",
            source="integrated",
            confidence=0.9,
            position_ratio=0.7,
            description="分型+背驰双重确认"
        )

    if fractal_type == "top" and fractal_strength == "strong" and has_divergence:
        return TradeSignal(
            action='sell',
            stop_loss=0,
            take_profit=0,
            signal_type="first_sell",
            source="integrated",
            confidence=0.9,
            position_ratio=0.0,
            description="顶分型+背驰双重确认"
        )

    # 均无法判断
    return TradeSignal(
        action='hold',
        position_ratio=0,
        stop_loss=0,
        take_profit=0,
        signal_type="hold",
        source="integrated",
        confidence=0.3,
        description="信号冲突，观望"
    )

# ============ §17 实战陷阱 ============

def check_traps_full(
    current_bar: KLine,
    prev_bars: List[KLine],
    ma_state: MACrossState,
    current_time: int,
    is_major_signal: bool,
) -> List[str]:
    """常见陷阱完整检查（§17.2）"""
    warnings = []

    # 陷阱1：追高风险
    if current_bar.open > 0:
        daily_change = (current_bar.close - current_bar.open) / current_bar.open
        if daily_change >= 0.09 and not is_major_signal:
            warnings.append("追高风险：当日涨幅超9%无主信号确认")

    # 陷阱2：禁止抄底
    if (ma_state.position == "男上位" and
        ma_state.kiss_count <= 1 and
        not is_major_signal):
        warnings.append("禁止抄底：均线空头初期，散户绝对不要抄底")

    # 陷阱3：巨量大阴线反抽陷阱
    if len(prev_bars) >= 1:
        prev = prev_bars[-1]
        is_big_yin = (
            prev.close < prev.open and
            (prev.open - prev.close) > (prev.high - prev.low) * 0.7
        )
        # 简化成交量判断
        if is_big_yin and current_bar.close > current_bar.open:
            warnings.append("巨量大阴线反抽陷阱：不在反抽中介入")

    # 陷阱5：下午买原则（T+1限制）
    from datetime import datetime
    hour = datetime.fromtimestamp(current_time).hour
    if hour < 13 and not is_major_signal:
        warnings.append("时间窗口：建议下午确认（T+1限制）")

    return warnings

# 别名
check_traps = check_traps_full

def sell_timing_rules(
    has_divergence: bool,
    is_zhongji: bool,
    current_price: float,
    entry_price: float,
    ma5: float,
) -> List[str]:
    """卖出时机经验（§17.3）

    规则1：宁愿早了千万别晚了
    规则2：涨的时候陆续走
    规则3：跌破5日线3天拉不回即真破
    """
    rules = []
    if entry_price > 0:
        profit_pct = (current_price - entry_price) / entry_price * 100
        if profit_pct > 20 and has_divergence:
            rules.append(f"已有{profit_pct:.1f}%利润+背驰信号，宁愿早卖别晚卖")
    if has_divergence and not is_zhongji:
        rules.append("背驰确认非中继，涨时区间套内陆续走")
    if current_price < ma5:
        rules.append("关注5日线：跌破3天拉不回即真破")
    return rules

def stock_selection_rules(
    stock_class: int,
    has_first_center_break: bool,
) -> List[str]:
    """选股经验（§17.4）"""
    suggestions = []
    if has_first_center_break and stock_class >= 5:
        suggestions.append("第一次湿吻区域上移确认，短线有钱途")
    if stock_class == 3:
        suggestions.append("均线刚形成金叉初期，回试不破可介入")
    return suggestions
