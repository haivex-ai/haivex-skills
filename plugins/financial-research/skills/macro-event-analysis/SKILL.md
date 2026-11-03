---
name: macro-event-analysis
description: '宏观事件六步深度分析技能，适用于关税政策、央行加息/降息、地缘冲突、大选、汇率剧变、大宗商品冲击、疫情等宏观事件的市场影响、系统性研判、传导路径、交易表达、情景推演和失效条件。仅从事件找相关 A股标的走 thematic-stock-screening，观点验证讨论走 fact-debate，公司事件点评走 event-commentary。'
---

# 宏观事件分析 (Macro Event Analysis)

## 概述

基于六步框架对宏观事件进行结构化深度分析，产出机构级投研报告。

## 工作流程

### Phase 0: 事件锁定与背景收集

1. 从用户输入中提取：**事件名称**、**发生时间**、**涉及经济体/资产**、**用户关注侧重**
2. 若事件描述模糊，向用户确认一次后继续
3. 使用 `search_web` + `search_paipai` 收集事件最新动态与市场即时反应
4. 使用 `search_edb` / `search_global_data` / `quick_fetch_stock_financials` / `delegate_to_agent(data_analyst)` 获取事件发生前后的关键资产价格快照；国内宏观用 `search_edb`、境内指数收盘价走 `delegate_to_agent(agent_type="data_analyst", ...)` 的 `指数相关` 数据域，A股个股行情/估值多股快照用 `quick_fetch_stock_financials`（时序/历史/计算走 `delegate_to_agent(agent_type="data_analyst", ...)` 的 `个股相关` 数据域），港股/美股/海外指数/外汇/商品等海外资产优先用 `search_global_data`

### Phase 1–6: 六步分析框架

依次完成以下六个模块。每个模块的详细分析指引见 [references/six-step-framework.md](references/six-step-framework.md)。

| 步骤  | 模块         | 核心任务                                      |
| --- | ---------- | ----------------------------------------- |
| 1   | **关键变量**   | 识别驱动事件演化的核心变量（≤7个），区分先行/同步/滞后指标，标注当前读数与阈值 |
| 2   | **变量传导路径** | 绘制"事件→变量→资产"的因果链，标注传导时滞与放大/衰减机制           |
| 3   | **历史类似案例** | 找到2–4个可比案例，提取资产表现的统计规律与本次异同               |
| 4   | **可能市场结构** | 基于变量组合推演2–3个情景（基准/乐观/悲观），给出概率与资产方向        |
| 5   | **交易表达方式** | 为每个情景设计具体的交易组合，含标的、方向、仓位比例、对冲工具           |
| 6   | **失效条件**   | 明确列出使整个分析框架失效的信号，附止损/退出规则                 |

### Phase 7: 报告产出

1. 综合前述证据完成分析与写作，并使用 `write_file` 保存为 Markdown
2. 使用 `plot` 为传导路径图、情景矩阵、历史案例对比图等生成可视化（至少2张图）
3. 报告存放规则：保存到 `/workspace/tmp/{session}/outputs/` 下，文件名格式 `宏观事件分析_{事件简称}_{YYYYMMDD}.md`

## 信息收集策略

### 必查数据清单

| 数据类别    | 工具                                                      | 说明                     |
| ------- | ------------------------------------------------------- | ---------------------- |
| 事件最新进展  | `search_web`                                            | 中英文双语搜索，覆盖24h内动态       |
| 机构观点与策略 | `search_paipai` (report, comment, roadShow)             | 券商宏观/策略研报、点评、纪要        |
| 关键宏观指标  | `search_edb` / `search_global_data` / `delegate_to_agent(data_analyst)` | 国内 GDP/CPI/PMI 等用 `search_edb`；海外利率、汇率、商品等优先用 `search_global_data` |
| 资产价格快照  | `search_edb` / `search_global_data` / `quick_fetch_stock_financials` / `delegate_to_agent(data_analyst)`    | 境内指数收盘价走 `指数相关` 数据域；A股个股多股快照用 `quick_fetch_stock_financials`（时序/历史/计算走 `个股相关` 数据域）；港股/美股/海外指数/外汇/商品等用 `search_global_data` |
| 历史案例数据  | `search_paipai` + `search_web`                          | 历史类似事件的资产表现回溯          |
| 持仓与资金流  | `search_paipai` (vps, report)                           | 基金持仓变动、北向/南向资金流        |

### 搜索原则

- **中英文双语**：宏观事件通常有全球影响，必须同时用中英文搜索
- **多源交叉**：关键判断至少2个独立来源验证
- **时效优先**：优先最近7天内的分析和数据
- **卖方+买方**：既要券商研报观点，也要基金持仓行为信号

### 结构化数据

- 委托 `data_analyst` 时写清标的、日期、指标、口径、排序和交付范围。
- 日期或对象不明确时先确认；结果保留单位、时间和缺失项。无法确认的数据如实留空，不用猜测值补齐历史案例或情景输入。

## 报告质量标准

- 每个模块必须有**具体数据**支撑，拒绝空泛定性
- 传导路径必须标注**时间维度**（即期/1周/1月/1季度）
- 历史案例必须给出**可量化的资产回报数据**
- 情景分析必须给出**概率权重**
- 交易表达必须具体到**标的代码/合约**级别
- 失效条件必须是**可观测、可量化**的信号
- 所有事实性陈述必须标注 `<span class="ref-node iconfont icon-lianjie" data-type="reference" data-refs="编号"></span>`
