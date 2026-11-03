"""缠论粗略版实战系统 - 数据结构定义（对应 DS3 v2.4 types.py）

所有核心数据类均采用 @dataclass，字段级定义与 DS3 保持一致。
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple

@dataclass
class KLine:
    """原始K线（有 open/close）"""
    time: int              # 时间戳（秒）
    open: float            # 开盘价
    high: float            # 最高价
    low: float             # 最低价
    close: float           # 收盘价
    volume: float          # 成交量

@dataclass
class StandardKLine:
    """包含处理后的K线 — ⚠️ 不含 open/close 字段"""
    time_start: int        # 合并K线的起始时间
    time_end: int          # 合并K线的结束时间
    high: float            # 最高价
    low: float             # 最低价
    direction: int         # 1=向上, -1=向下, 0=未定
    original_count: int    # 被合并的原始K线数量
    volume_sum: float      # 合并区间成交量之和

@dataclass
class Fractal:
    """分型"""
    type: str                      # "top" 或 "bottom"
    index: int                     # 分型中间K线在标准K线序列中的索引
    timestamp: int                 # 分型中间K线的结束时间
    high: float                    # 分型中间K线的最高价
    low: float                     # 分型中间K线的最低价
    strength: str                  # 四档: "strongest", "strong", "medium", "weak"
    is_confirmed: bool             # 是否已确认
    k_line_indices: List[int]      # 构成分型的3根K线索引 [i-1, i, i+1]

@dataclass
class Pen:
    """笔"""
    direction: int          # 1=向上, -1=向下
    start_fractal: Fractal
    end_fractal: Fractal
    start_time: int         # 起始时间戳
    end_time: int           # 结束时间戳
    high: float             # 笔的最高价
    low: float              # 笔的最低价

@dataclass
class Segment:
    """走势段（基于均线湿吻区域分割）"""
    direction: int           # 1=向上段, -1=向下段
    start_index: int         # 段在原始K线序列中的起始索引
    end_index: int           # 段在原始K线序列中的结束索引
    start_time: int          # 段起始时间
    end_time: int            # 段结束时间
    high: float              # 段最高价
    low: float               # 段最低价
    macd_area: float         # 该段MACD柱子面积（由M6计算填充）

@dataclass
class MACrossState:
    """均线状态"""
    short_ma: float          # 当前短期均线值
    long_ma: float           # 当前长期均线值
    position: str            # "女上位"=短期在上, "男上位"=长期在上
    kiss_type: str           # "飞吻", "唇吻", "湿吻", "无"
    kiss_count: int          # 当前体位下的第几次缠绕
    slope_short: float       # 短期均线斜率
    slope_long: float        # 长期均线斜率

@dataclass
class MACDData:
    """MACD数据"""
    diff: float              # DIF = EMA(close,12) - EMA(close,26)
    dea: float               # DEA = EMA(DIF,9)
    hist: float              # MACD柱 = 2*(DIF-DEA)
    is_above_zero: bool      # DIF是否在0轴之上
    zero_cross_count: int    # 穿越0轴的次数统计

@dataclass
class DivergenceResult:
    """盘整背驰结果"""
    is_divergence: bool      # 是否盘整背驰
    area_ratio: float        # 后段面积/前段面积
    confidence: float        # 置信度 0.0-1.0
    description: str         # 判断说明

@dataclass
class TradeSignal:
    """交易信号"""
    action: str              # "buy", "sell", "hold"
    signal_type: str         # "first_buy", "second_buy", "first_sell", "second_sell", "hold"
    source: str              # "ma", "fractal", "macd", "same_level", "integrated"
    confidence: float        # 置信度 0.0-1.0
    position_ratio: float    # 建议仓位比例 0.0-1.0
    stop_loss: float         # 止损位
    take_profit: float       # 止盈位
    description: str         # 信号说明
