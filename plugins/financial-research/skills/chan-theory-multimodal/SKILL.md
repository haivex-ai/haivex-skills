---
name: chan-theory-multimodal
description: 缠论均线分析多模态系统。基于《缠论108课·全面版》原文提炼，13个独立模块(M0-M12) + ChanlunEngine调度引擎，覆盖K线包含处理、均线系统、分型识别(四档强度)、笔生成、段识别、MACD盘整背驰、表里关系状态机、同级别分解、中阴布林、资金管理、板块轮动、实战陷阱。含Pen/Segment/DivergenceResult完整数据结构，ChanlunConfig类配置，支持多实例子回测。当用户提到缠论、趋势分析、走势类型、均线系统、分型、顶底分型、MACD背驰、盘整背驰、同级别分解、区间套、中阴阶段、第一类买点、第二类买点、K线包含处理、吻分类、女上位、男上位、表里关系、笔定理、布林通道时触发。
---

# 缠论均线分析多模态系统

> 基于《缠论108课·全面版》原文提炼
> 版本：v2.4 | 架构：13个独立模块 + ChanlunEngine 调度引擎

## 一、系统定位

本系统为"粗略版"缠论实战系统，不依赖严格递归中枢体系，而是将缠论原文中的均线系统、大周期分型、MACD辅助三套独立子系统组合成一个可编程的综合决策系统。

## 二、触发条件

用户输入涉及以下场景时加载本技能：
- 缠论、趋势分析、走势类型
- 均线系统、分型、顶底分型
- MACD背驰、盘整背驰
- 同级别分解、区间套、中阴阶段
- 缠论买卖点、第一类买点、第二类买点
- K线包含处理、吻分类、女上位、男上位
- 表里关系、笔定理、布林通道

## 三、工作流程

### STEP 1: K线预处理
process_inclusion 将原始K线转换为标准K线序列

### STEP 2: 均线系统
calc_ma 计算MA5/MA10，get_ma_state 返回均线体位、吻类型、缠绕次数、斜率

### STEP 3: 分型与笔
detect_fractals 识别顶底分型，assess_fractal_strength 四档强度判定，build_pens 生成笔

### STEP 4: 段识别
find_ma_cross_points 基于均线交叉点切段，identify_segments 输出 Segment 列表

### STEP 5: 综合决策
ChanlunEngine._integrate 按优先级排列决策矩阵，输出 TradeSignal

决策优先级：大级别分型 > 均线体位 > MACD背驰

## 四、输出格式

TradeSignal 字段：
- action：buy / sell / hold
- signal_type：first_buy / second_buy / first_sell / second_sell / hold
- source：ma / fractal / macd / same_level / integrated
- confidence：0.0 到 1.0
- position_ratio：0.0 / 0.2 / 0.4 / 0.7
- stop_loss：止损位
- take_profit：止盈位
- description：信号说明

## 五、文件结构

scripts/
- config.py：ChanlunConfig 配置类
- data_structures.py：9 个 dataclass
- kline_processing.py：M1 K线包含处理
- ma_system.py：M2 均线计算
- fractal_detector.py：M3 分型 + M4 笔
- segment.py：M0 段识别
- macd_analyzer.py：M5 MACD + M6 背驰
- divergence_checker.py：背驰三法综合
- surface_relation.py：M7 表里关系
- same_level_decomposition.py：M8 同级别分解
- bollinger_zhongyin.py：M9 中阴布林
- position_manager.py：M10 资金管理
- sector_rotation.py：M11 板块轮动
- boundary_handler.py：M12 实战陷阱
- multi_period.py：多周期联立
- main_analyzer.py：ChanlunEngine 引擎
- main.py：主入口

## 六、使用示例

将本技能的 `scripts/` 作为当前工作目录或加入 `PYTHONPATH` 后使用以下平铺模块导入；本目录内部使用同一导入约定。

```python
from main_analyzer import ChanlunEngine
from data_structures import KLine
from config import ChanlunConfig

klines = []  # 由调用方提供真实KLine序列；空序列返回数据不足信号
engine = ChanlunEngine(ChanlunConfig())
signal = engine.analyze(klines)
print(signal.action, signal.signal_type, signal.position_ratio)
```
