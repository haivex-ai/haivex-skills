"""缠论粗略版 - M9 中阴阶段与布林通道模块（对应 DS3 v2.4 modules/zhongyin_boll.py）

原文依据：第89课（中阴阶段）、第90课（中阴结束时间辅助判断）
"""

from typing import List, Tuple, Optional
from data_structures import KLine, StandardKLine
from config import ChanlunConfig

_CFG = ChanlunConfig()

from typing import List, Tuple, Optional
from data_structures import KLine, StandardKLine
from config import ChanlunConfig

_CFG = ChanlunConfig()

def calc_boll(
    k_lines: List[StandardKLine],
    period: int = 20,
    std_mult: float = 2.0,
) -> Tuple[List[float], List[float], List[float]]:
    """计算布林通道（§10.3）

    Returns: (middle, upper, lower)
    """
    if len(k_lines) < period:
        return [], [], []

    closes = [k.high for k in k_lines]  # StandardKLine 无close，用high近似
    middle = []
    upper = []
    lower = []

    for i in range(len(closes)):
        if i < period - 1:
            middle.append(0.0)
            upper.append(0.0)
            lower.append(0.0)
            continue
        window = closes[i - period + 1:i + 1]
        ma = sum(window) / period
        variance = sum((x - ma) ** 2 for x in window) / period
        std = variance ** 0.5

        middle.append(ma)
        upper.append(ma + std_mult * std)
        lower.append(ma - std_mult * std)

    return middle, upper, lower

class BOLL_Analyzer:
    """布林通道分析器（§10.3，第90课）"""

    def __init__(self, period: int = 20, std_mult: float = 2.0):
        self.period = period
        self.std_mult = std_mult

    def is_super_strong_up(self, price: float, upper_band: float) -> bool:
        """价格在上轨之上 → 超强上涨状态"""
        return price > upper_band

    def is_super_strong_down(self, price: float, lower_band: float) -> bool:
        """价格在下轨之下 → 超强下跌状态"""
        return price < lower_band

    def is_exiting_super_strong(
        self, price: float, band: float, direction: str = "up"
    ) -> bool:
        """判断是否从超强区域转向一般性区域"""
        if direction == "up":
            return price <= band
        else:
            return price >= band

    def check_zhongyin(
        self,
        price: float,
        upper_band: float,
        lower_band: float,
        prev_high: float,
    ) -> bool:
        """中阴状态判定（§10.3）

        再次上涨创出新高但不能重新有效回到超强区域 → 进入中阴
        """
        if not self.is_super_strong_up(price, upper_band):
            if price > prev_high and price < upper_band * 0.99:
                return True
        return False

    def is_band_contracting(self, upper_band: float, lower_band: float) -> bool:
        """布林通道收口判定 → 中阴结束时间预判"""
        mid = (upper_band + lower_band) / 2.0
        if mid == 0:
            return False
        bandwidth = (upper_band - lower_band) / mid
        return bandwidth < _CFG.BOLL_CONTRACT_THRESHOLD

def is_zhongyin(
    price: float,
    upper_band: float,
    lower_band: float,
    prev_high: float,
) -> bool:
    """便捷函数：判断是否进入中阴阶段"""
    analyzer = BOLL_Analyzer()
    return analyzer.check_zhongyin(price, upper_band, lower_band, prev_high)

def check_second_buy_sell_boll(
    price: float,
    upper_band: float,
    lower_band: float,
    is_first_rebound: bool,
) -> Tuple[bool, str]:
    """第二类买卖点的布林辅助（§10.3）

    进入中阴后，上轨/下轨滞后反应
    第一次回跌/回升后再次运行，转向的上轨/下轨成为最大阻力和支持
    """
    if is_first_rebound and price < upper_band * 0.98:
        return True, "第二类卖点：反弹受上轨压制"
    if is_first_rebound and price > lower_band * 1.02:
        return True, "第二类买点：回踩受下轨支撑"
    return False, "未形成第二类买卖点"
