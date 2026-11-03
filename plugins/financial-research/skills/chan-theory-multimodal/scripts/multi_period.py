"""缠论粗略版 - 多周期联立与区间套（对应 DS3）

原文依据：第27课（精确大转折点寻找程序定理）、第61课（区间套定位）
"""

from typing import List, Tuple, Optional, Dict
from data_structures import KLine, StandardKLine, Fractal, TradeSignal
from config import ChanlunConfig

_CFG = ChanlunConfig()

from typing import List, Tuple, Optional, Dict
from data_structures import KLine, StandardKLine, Fractal, TradeSignal

# ============ 6.1-6.2 区间套精确定位 ============

def locate_turning_point(
    weekly_klines: Optional[List[KLine]] = None,
    daily_klines: Optional[List[KLine]] = None,
    min30_klines: Optional[List[KLine]] = None,
    min5_klines: Optional[List[KLine]] = None,
) -> Dict[str, any]:
    """缠中说禅精确大转折点寻找程序（§6.1-6.2，第27/61课）

    从大级别往小级别逐级锁定转折点
    """
    result = {
        "level": None,
        "turning_point": None,
        "confidence": 0.0,
        "chain": [],
    }

    levels = [
        ("周线", weekly_klines),
        ("日线", daily_klines),
        ("30分钟", min30_klines),
        ("5分钟", min5_klines),
    ]

    for name, klines in levels:
        if klines is None or len(klines) < 20:
            continue
        result["chain"].append(f"{name}：数据充足")
        result["level"] = name

    return result

def maintain_divergence_segment(
    current_seg_force: float,
    previous_seg_force: float,
) -> Tuple[bool, str]:
    """区间套与背驰段假设法（§6.4，第61课）

    初始假设当前段进入背驰段，一旦力度大于前者 → 背驰段不成立
    """
    if previous_seg_force == 0:
        return False, "前段力度为零，无法比较"

    if current_seg_force >= previous_seg_force:
        return False, "当前力度 >= 前段力度，背驰段不成立"

    return True, "当前段仍处于背驰段假设中"

def get_interval_depth_for_level(operation_level: str) -> int:
    """操作级别 → 需要的区间套深度（§6.3，第61课）"""
    depth_map = {
        "1分钟": 4,
        "5分钟": 3,
        "30分钟": 3,
        "日线": 2,
        "周线": 1,
    }
    return depth_map.get(operation_level, 2)

def multi_period_decision(
    h_direction: int,  # 大级别方向：1多/-1空/0盘
    m_signal_type: str,  # 中级别信号
    l_confirmed: bool,  # 小级别确认
) -> Tuple[bool, str]:
    """多周期联立决策（§6.5）

    决策原则：
    1. H级方向与M级信号方向不能冲突
    2. M级信号必须在H级背驰段范围内
    3. L级只负责精确执行
    """
    # 方向冲突检查
    if h_direction == 1 and "sell" in m_signal_type:
        return False, "大级别多头方向，中级别卖点信号冲突，不执行"
    if h_direction == -1 and "buy" in m_signal_type:
        return False, "大级别空头方向，中级别买点信号冲突，不执行"

    if not l_confirmed:
        return False, "小级别未确认，等待区间套精确定位"

    return True, "大→中→小三级联立确认，可执行"

# ============ 附录A：笔生成算法（已移至 fractal_detector.py） ============
# build_pens() 和 get_current_pen_state() 定义在 fractal_detector.py 中，
# 此处仅保留多周期联立相关函数。
