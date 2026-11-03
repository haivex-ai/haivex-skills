"""缠论粗略版实战系统 - 配置中心（对应 DS3 v2.4 config.py）

采用 ChanlunConfig 类而非模块常量，支持多实例回测。
"""

class ChanlunConfig:
    # ============ 均线参数 ============
    SHORT_MA = 5
    LONG_MA = 10
    EXTENDED_MAS = [5, 13, 21, 34, 55, 89, 144, 233]
    MA_SLOPE_WINDOW = 3
    KISS_LIP_RATIO = 0.005      # 唇吻最大间距比例
    KISS_WET_RATIO = 0.003      # 湿吻临界间距比例
    KISS_FLY_RATIO = 0.01       # 飞吻最小间距比例

    # ============ 分型参数 ============
    EFFECTIVE_BREAK_RATIO = 0.03
    FRACTAL_STRONG_SHADOW_RATIO = 0.6
    FRACTAL_STRONG_BODY_RATIO = 0.7
    FRACTAL_SMALL_AMPLITUDE_RATIO = 0.3

    # ============ MACD参数 ============
    MACD_FAST = 12
    MACD_SLOW = 26
    MACD_SIGNAL = 9
    DIVERGENCE_AREA_RATIO = 0.9

    # ============ 段识别参数 ============
    MA_CROSS_LOOKBACK = 10

    # ============ 同级别分解 ============
    SAME_LEVEL_PERIOD = "30min"

    # ============ 布林参数 ============
    BOLL_PERIOD = 20
    BOLL_STD_MULT = 2
    BOLL_CONTRACT_THRESHOLD = 0.05

    # ============ 仓位 ============
    POSITION_HIGH_CONFIDENCE = 0.7
    POSITION_MEDIUM_CONFIDENCE = 0.4
    POSITION_LOW_CONFIDENCE = 0.2
    CONFIDENCE_HIGH = 0.85
    CONFIDENCE_MEDIUM = 0.65
    CONFIDENCE_LOW = 0.45

    # ============ 数据校验 ============
    MIN_KLINE_COUNT = 50
