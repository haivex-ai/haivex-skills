"""缠论粗略版 - M11 板块强弱指标模块（对应 DS3 v2.4 modules/sector_strength.py）

原文依据：第106课
"""

from typing import List, Dict, Optional
from config import ChanlunConfig

_CFG = ChanlunConfig()

from typing import List, Dict, Optional
from config import ChanlunConfig

_CFG = ChanlunConfig()

def classify_stock(ma_values: Dict[int, float], price: float) -> int:
    """扩展均线分类系统（§13.1，第106课）

    8条均线(5,13,21,34,55,89,144,233)，将股票分为9类：
    第1类：完全在所有均线之下（最弱）
    第9类：站上所有均线（最强）
    """
    conquered = 0
    for period in _CFG.EXTENDED_MAS:
        ma_val = ma_values.get(period, float('inf'))
        if ma_val < price:
            conquered += 1
        else:
            break
    return conquered + 1

class SectorStrengthIndicator:
    """缠中说禅板块强弱指标（§13.2，第106课）

    板块内所有股票的类别数取平均值
    """

    def __init__(self):
        self.sectors: Dict[str, List[str]] = {}
        self.stock_class: Dict[str, int] = {}

    def register_stock(self, sector_name: str, stock_code: str, class_num: int):
        """注册股票及其分类"""
        if sector_name not in self.sectors:
            self.sectors[sector_name] = []
        if stock_code not in self.sectors[sector_name]:
            self.sectors[sector_name].append(stock_code)
        self.stock_class[stock_code] = class_num

    def sector_strength(self, sector_name: str) -> float:
        """计算板块强弱指标"""
        stocks = self.sectors.get(sector_name, [])
        if not stocks:
            return 0.0
        total_class = sum(self.stock_class.get(s, 1) for s in stocks)
        return total_class / len(stocks)

    def get_top_sectors(self, top_n: int = 3) -> List[tuple]:
        """获取最强的N个板块"""
        strengths = [
            (name, self.sector_strength(name))
            for name in self.sectors
        ]
        strengths.sort(key=lambda x: x[1], reverse=True)
        return strengths[:top_n]

def get_rotation_rules() -> Dict[str, str]:
    """轮动操作规则（§13.3，第106课）

    规则1：不追高 — 找没动的、有买点的买
    规则2：先出后进 — 热的冲高时抛，吸纳有启动迹象的潜力板块
    规则3：顶背驰出局 — N类上出现顶背驰就先出来
    规则4：持股数量控制 — 资金不大，最多两三个板块
    """
    return {
        "no_chase": "板块轮动快，不追高买，找没动的、有买点的买",
        "exit_before_enter": "热的冲高时抛，吸纳有启动迹象的潜力板块",
        "top_divergence_exit": "N类上出现顶背驰，先出来偷几天欢",
        "max_sectors": "资金不大，最多两三个板块持股即可",
    }

def check_chase_risk(
    stock_class: int,
    sector_strength_val: float,
    has_divergence: bool,
) -> Optional[str]:
    """追高风险检查"""
    if stock_class >= 7 and not has_divergence:
        return "该股已站上7条以上均线（高位），无背驰确认，追高风险大"
    if sector_strength_val > 7.0 and stock_class >= 6:
        return "板块过热（均分>7），个股高位，不追"
    return None
