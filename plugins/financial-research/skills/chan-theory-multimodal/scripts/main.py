"""缠论粗略版 - 主入口（对应 DS3 v2.4 main.py）

提供便捷的分析函数和命令行入口。
"""

from typing import List, Optional
from data_structures import KLine, TradeSignal
from config import ChanlunConfig
from main_analyzer import ChanlunEngine

def analyze_stock(
    stock_code: str,
    klines_30m: List[KLine],
    klines_5m: Optional[List[KLine]] = None,
) -> TradeSignal:
    """便捷函数：单次分析一只股票"""
    config = ChanlunConfig()
    engine = ChanlunEngine(config)
    return engine.analyze(klines_30m, klines_5m)

if __name__ == "__main__":
    # 使用示例
    print("缠论粗略版实战系统 v2.4")
    print("请通过 analyze_stock() 函数调用")
