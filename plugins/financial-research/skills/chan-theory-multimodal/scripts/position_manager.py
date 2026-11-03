"""缠论粗略版 - M10 资金管理模块（对应 DS3 v2.4 modules/money_management.py）

原文依据：第31课
"""

from typing import Dict, Optional
from data_structures import TradeSignal
from config import ChanlunConfig

_CFG = ChanlunConfig()

from typing import Dict, Optional
from data_structures import TradeSignal
from config import ChanlunConfig

_CFG = ChanlunConfig()

class FundManagement:
    """资金管理（§12.2，第31课）"""

    def __init__(self, total_funds: float):
        self.total_funds = total_funds
        self.positions: Dict[str, dict] = {}

    def initial_buy(self, stock_code: str, price: float, total_amount: float):
        """初始买入（§12.1规则3：一次性买入）

        留1/10机动资金做短差
        """
        main_amount = total_amount * 0.9
        reserved_amount = total_amount * 0.1
        shares = main_amount / price
        self.positions[stock_code] = {
            "shares": shares,
            "cost": price,
            "reserved": reserved_amount,
            "total_cost": main_amount,
        }

    def short_trade_before_zero(
        self, stock_code: str, sell_price: float, buy_back_price: float
    ):
        """成本归零前短差操作（§12.2阶段一）

        每次短差不增加股票数量，只降低持仓成本
        """
        pos = self.positions.get(stock_code)
        if not pos:
            return
        if pos["reserved"] <= 0 or sell_price <= 0:
            return
        trade_shares = pos["reserved"] / sell_price
        profit_per_share = sell_price - buy_back_price
        total_profit = trade_shares * profit_per_share
        if pos["shares"] > 0:
            pos["cost"] = (pos["cost"] * pos["shares"] - total_profit) / pos["shares"]

    def is_cost_zero(self, stock_code: str, current_price: float) -> bool:
        """判断成本是否归零（§12.2）

        持仓市值 >= 总成本 * 1.5 → 成本归零
        """
        pos = self.positions.get(stock_code)
        if not pos:
            return False
        sell_value = pos["shares"] * current_price
        return sell_value >= pos["total_cost"] * 1.5

    def short_trade_after_zero(
        self, stock_code: str, sell_price: float, buy_back_price: float
    ):
        """成本归零后短差操作（§12.2阶段二：挣股票）

        高抛后全部回补，使股票数量越来越多，成本永远为0
        """
        pos = self.positions.get(stock_code)
        if not pos:
            return
        if sell_price <= 0 or buy_back_price <= 0:
            return
        trade_shares = pos["shares"] * 0.5  # 用一半仓位做短差
        profit = trade_shares * (sell_price - buy_back_price)
        if buy_back_price > 0:
            add_shares = profit / buy_back_price
            pos["shares"] += add_shares

def calc_position_size(signal: TradeSignal) -> float:
    """仓位控制（§12.3）

    confidence >= 0.85 → 70% 主力仓位
    confidence >= 0.65 → 40% 半仓
    confidence >= 0.45 → 20% 试探仓位
    """
    confidence = signal.confidence
    if confidence >= _CFG.CONFIDENCE_HIGH:
        return 0.7
    elif confidence >= _CFG.CONFIDENCE_MEDIUM:
        return 0.4
    elif confidence >= _CFG.CONFIDENCE_LOW:
        return 0.2
    else:
        return 0.0

def validate_buy_rules(
    current_position: float,
    ma_position: str,
    is_first_buy: bool,
) -> tuple:
    """资金管理核心规则验证（§12.1）

    规则1：资金无压力（由外部保证）
    规则2：严禁向上加仓
    规则3：一次性买入
    """
    warnings = []

    # 严禁向上加仓：女上位时不加仓
    if ma_position == "女上位" and current_position > 0:
        warnings.append("严禁向上加仓：女上位状态禁止追加买入")

    # 男上位中非第一类买点不加仓
    if ma_position == "男上位" and not is_first_buy and current_position > 0:
        warnings.append("男上位仅在背驰段可试探，非第一类买点不加仓")

    return len(warnings) == 0, warnings

# 别名
calc_position = calc_position_size
CostManager = FundManagement
