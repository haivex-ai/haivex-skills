"""缠论粗略版 - M1 K线包含处理模块（对应 DS3 v2.4 modules/inclusion.py）

将原始K线序列转换为经过包含关系处理的标准K线序列。
"""

from typing import List
from data_structures import KLine, StandardKLine

def is_inclusion(k1: KLine, k2: KLine) -> bool:
    """判断两根K线是否存在包含关系（模块3.1）
    
    包含定义：(K1.high >= K2.high AND K1.low <= K2.low)
             OR (K2.high >= K1.high AND K2.low <= K1.low)
    """
    return (k1.high >= k2.high and k1.low <= k2.low) or \
           (k2.high >= k1.high and k2.low <= k1.low)

def process_inclusion(k_lines: List[KLine]) -> List[StandardKLine]:
    """包含关系处理主算法（模块3.2）
    
    输入：原始K线序列
    输出：标准K线序列（包含关系处理后）
    
    算法要点：
    - 方向未定(direction=0)：默认向上处理（取high高者, low高者）
    - 方向向上(direction=1)：取high较高, low较高
    - 方向向下(direction=-1)：取low较低, high较低
    - 连续包含时持续合并，直到遇到非包含关系K线
    """
    if len(k_lines) < 2:
        return [_to_standard(k) for k in k_lines]

    result: List[StandardKLine] = []
    prev = k_lines[0]
    direction = 0
    merged_count = 1

    for i in range(1, len(k_lines)):
        curr = k_lines[i]

        if is_inclusion(prev, curr):
            # 存在包含关系，合并
            new_high = prev.high
            new_low = prev.low

            if direction == 1 or direction == 0:
                new_high = max(prev.high, curr.high)
                new_low = max(prev.low, curr.low)
                direction = 1
            elif direction == -1:
                new_high = min(prev.high, curr.high)
                new_low = min(prev.low, curr.low)

            prev.high = new_high
            prev.low = new_low
            prev.close = curr.close
            prev.volume += curr.volume
            merged_count += 1
        else:
            # 无包含关系，将之前的K线加入结果
            std = StandardKLine(
                time_start=prev.time,
                time_end=prev.time,
                high=prev.high,
                low=prev.low,
                direction=direction,
                original_count=merged_count,
                volume_sum=prev.volume,
            )
            result.append(std)

            # 重新确定方向
            direction = 1 if curr.high > prev.high else -1
            prev = curr
            merged_count = 1

    # 处理最后剩余的K线
    std = StandardKLine(
        time_start=prev.time,
        time_end=prev.time,
        high=prev.high,
        low=prev.low,
        direction=direction,
        original_count=merged_count,
        volume_sum=prev.volume,
    )
    result.append(std)

    return result

def _to_standard(k: KLine) -> StandardKLine:
    """将单根原始K线转为标准K线"""
    return StandardKLine(
        time_start=k.time,
        time_end=k.time,
        high=k.high,
        low=k.low,
        direction=0,
        original_count=1,
        volume_sum=k.volume,
    )

# 边界条件处理（模块3.3）
def is_gap(k1: StandardKLine, k2: StandardKLine) -> bool:
    """判断两根标准K线之间是否存在缺口"""
    return k1.low > k2.high or k2.low > k1.high
