"""缠论粗略版 - M7 表里关系状态机（对应 DS3 v2.4 modules/state_machine.py）

原文依据：第91课（两重表里关系1）、第93课（两重表里关系2）、第92课（中枢震荡监视器）
"""

from typing import List, Tuple, Optional
from config import ChanlunConfig

_CFG = ChanlunConfig()

from typing import List, Tuple, Optional

# ============ 8.1-8.2 四态编码 ============

def encode_state(direction: int, position: int) -> Tuple[int, int]:
    """四态编码（§8.1，第91课缠中说禅笔定理）

    变量1（方向）：1=向上笔, -1=向下笔
    变量2（位置）：0=分型构造中, 1=分型确认延伸为笔
    """
    return (direction, position)

def get_valid_transitions(current: Tuple[int, int]) -> List[Tuple[int, int]]:
    """状态转移规则（§8.2）

    (1,1) → (1,0)
    (-1,1) → (-1,0)
    (1,0) → (1,1) 延续 或 (-1,1) 转折
    (-1,0) → (-1,1) 延续 或 (1,1) 转折
    """
    if current == (1, 1):
        return [(1, 0)]
    elif current == (-1, 1):
        return [(-1, 0)]
    elif current == (1, 0):
        return [(1, 1), (-1, 1)]
    elif current == (-1, 0):
        return [(-1, 1), (1, 1)]
    return []

def update_state(
    current: Tuple[int, int],
    new_fractal_type: Optional[str],
    is_confirmed: bool = False,
) -> Tuple[int, int]:
    """根据新分型更新状态"""
    direction, position = current

    if new_fractal_type is None:
        return current

    if position == 1:  # 延伸中 → 进入分型构造
        return (direction, 0)

    # position == 0：分型构造中
    if not is_confirmed:
        return current

    if new_fractal_type == "top" and direction == 1:
        return (-1, 1)  # 顶分型确认 → 向下笔开始
    elif new_fractal_type == "bottom" and direction == -1:
        return (1, 1)   # 底分型确认 → 向上笔开始
    else:
        return (direction, 1)  # 中继延续

# ============ 8.3 病情三阶段诊断 ============

def diagnose_condition(
    level_main: Tuple[int, int],
    level_sub: Tuple[int, int],
) -> Tuple[str, str]:
    """病情三阶段诊断（§8.3，第91课）

    以5分钟为主、1分钟为例：
    未病：主级别(1,1)/(-1,1)，次级别出现(1,0)/(-1,0)
    欲病：次级别的(1,0)/(-1,0)被确认
    已病：次级别反向笔确立并导致主级别转折
    """
    if level_main[1] == 1 and level_sub[1] == 0:
        return "未病", "级别过滤忽略"
    elif level_sub[0] != level_main[0] and level_sub[1] == 0:
        return "欲病", "关注次级别转折可能"
    elif level_sub[0] != level_main[0] and level_sub[1] == 1:
        return "已病", f"主级别即将从{level_main}转向"
    else:
        return "健康", "趋势正常延续"

# 别名：M7 使用 diagnose 接口名
diagnose = diagnose_condition

# ============ 8.4 跨级别过滤 ============

def should_ignore_sub_level(
    level_main: Tuple[int, int],
    level_sub: Tuple[int, int],
) -> bool:
    """跨级别过滤规则（§8.4，第91课）

    如果5分钟里是(1,1)或(-1,1)，1分钟里前面的任何波动无价值
    """
    if level_main[1] == 1:
        return True
    if level_main[1] == 0:
        return False
    return False

# ============ 8.5 (1,0)后三种操作方案 ============

def get_operation_plan(state: Tuple[int, int], previous_force: Optional[float] = None) -> str:
    """(1,0)后的三种操作方案（§8.5，第93课）

    方案一（保守型）：成本兑现法
    方案二（震荡操作型）：短差法
    方案三（力度比较型）：趋势终结判断
    """
    if state[1] == 1:  # 延伸中
        return "方案三·力度比较：若后段力度<前段 → 见顶信号，区间套定位高点"

    if state == (1, 0):
        return (
            "方案一·成本兑现：(1,1)→(1,0)，兑现成本留利润；"
            "方案二·短差：先卖后买，选(-1,1)就最后一次不回补"
        )
    elif state == (-1, 0):
        return "(-1,0)底分型构造，等待方向选择"

    return "非(1,0)状态，保持当前操作"

# ============ 8.6 Zn震荡监视器 ============

class ZN_Monitor:
    """Zn震荡监视器（§8.6，第92课，改用均线湿吻区域）

    均线湿吻区域确立后，区间一半位置 = 震荡中轴Z
    每个次级震荡区间的一半位置 = Zn
    """

    def __init__(self, wet_kiss_high: float, wet_kiss_low: float):
        self.Z = (wet_kiss_high + wet_kiss_low) / 2.0
        self.Z_values: List[float] = []

    def add_oscillation(self, seg_high: float, seg_low: float):
        """添加一次次级震荡"""
        Zn = (seg_high + seg_low) / 2.0
        self.Z_values.append(Zn)

    def get_bias(self) -> str:
        """判断震荡偏强/偏弱"""
        if not self.Z_values:
            return "无数据"
        n = min(3, len(self.Z_values))
        recent_avg = sum(self.Z_values[-n:]) / n
        if recent_avg > self.Z * 1.02:
            return "偏强"
        elif recent_avg < self.Z * 0.98:
            return "偏弱"
        else:
            return "中性"

    def get_risk_warning(self) -> Optional[str]:
        """风险提示"""
        if not self.Z_values:
            return None
        latest = self.Z_values[-1]
        if latest < self.Z * 0.95:
            return "Zn在Z之下，介入风险很大"
        if len(self.Z_values) >= 3:
            recent = self.Z_values[-3:]
            if all(zn < self.Z for zn in recent):
                if recent[-1] < recent[0]:
                    return "Zn缓慢提高但未突破上沿，小心上升楔型诱多"
        return None
