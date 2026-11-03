---
name: research-question-generator
description: '上市公司调研问题生成技能，适用于用户要去调研某家公司、准备调研问题、调研提纲、公司调研、或要求生成针对上市公司的机构投资者提问列表。输入公司名称和股票代码，输出按7大框架分类并带星级评定的结构化调研问题报告。'
---

# 调研问题生成 Skill

为机构投资者生成针对上市公司的调研问题清单。基于点评、纪要、年报/半年报、研报等多源数据，按短期热点、经营情况、竞争环境、财务质量、市场预期、流动性风险、其他关注等7大维度归纳问题。

## 核心原则（最高优先级）

1. **执行要求**：组织检索、读取公司材料、识别信息缺口并生成调研问题。`search_paipai` 和 `doc_searcher` 只提供材料，不能替代判断。
2. **证据处理**：检索阶段不要无依据地截断原文；`doc_searcher` 通过 `save_as` 将结果保存到独立文件。写作阶段读取关键材料，核对公司、报告期、经营变化和市场分歧。
3. **中间文件与交付**：搜索类结果通过 `save_as` 保存，避免无意义地占用上下文；不要用 `write_file` 伪造未检索到的证据。最终问题清单使用 `write_file` / `replace_file` 写入交付文件。
4. **检索扩展**：除下方规定的检索任务外，可根据对公司的理解，发起额外的 `doc_searcher` 检索来补充有价值的数据，如行业对比、上下游信息、近期重大事件。
5. **doc_searcher 零结果容错**：当某个 doc_searcher 委托返回空结果时，自动扩大时间范围重试一次。若仍为空则跳过该文件，不影响其他检索和最终合并流程。

## 输入要求

必须从用户获取：
- **company_name**：公司名称（如"佳缘科技"）
- **stock_code**：股票代码（如"301117.SZ"）

若用户未提供股票代码，通过搜索确认。优先使用 stock_code 进行后续查询，必须使用交易所后缀，如.SH/.BJ/.HK/.SZ

## 工作流程

### Step 1：确认输入

确认 company_name 和 stock_code。

### Step 2：并行数据收集

以下所有数据收集任务**并行执行**，分为语义背景、文档检索和财务数据三大类。

#### 2A：search_paipai 语义背景

使用 `search_paipai` 获取该公司的基础背景信息和市场关注焦点：

```python
search_paipai(
    query="{company_name} 调研 关注 风险 催化剂 业绩",
    sources=["report", "roadshow", "comment"],
    top_k=15,
    save_as="tmp/{session_id}/01_paipai_bg.md"
)
```

#### 2B：doc_searcher 委托（1 次合并发起）

通过 `delegate_to_agent(agent_type="doc_searcher", ...)` 发起**一次**合并检索：

```python
delegate_to_agent(
    agent_type="doc_searcher",
    instruction="检索{company_name}（{stock_code}）的以下五类文档，每类结果分别通过 save_as 保存到独立文件：(1) 近3个月的卖方点评，返回20条，保留标题、时间、正文、推荐语、分析师、机构和证券，save_as='tmp/{session_id}/02_comments.md'；(2) 近6个月的路演纪要，返回5条，优先 AI 总结纪要，保留标题、日期、证券、机构、总结和正文，save_as='tmp/{session_id}/03_roadshow.md'；(3) 最近的年报或半年报公告，返回2条，公告类型代码为020201或020301，保留标题、发布时间、公告类型及代码、证券、报告期末日和正文，save_as='tmp/{session_id}/04_announcements.md'；(4) 近1年的券商研报，返回5条，保留标题、时间、作者、机构、行业、证券、报告类型和正文，save_as='tmp/{session_id}/05_reports.md'；(5) 近6个月的投资者互动问答，返回5条，公告类型代码以0209开头，保留标题、发布时间和正文，save_as='tmp/{session_id}/06_investor_qa.md'。各类结果分别按时间降序。禁止对内容做任何筛选或截断。完成后在回复中列出所有已保存的文件路径及各文件的内容概要。"
)
```

**委托6：自由补充检索（可选）**

可根据对公司的理解，发起额外的 `doc_searcher` 委托检索其他有价值的数据，如行业对比、上下游信息、近期重大事件；结果保存为 `tmp/{session_id}/90_extra_{N}.md`。

#### 2C：财务数据

使用 `quick_fetch_stock_financials` 获取财务快照，用于支撑财务质量与异常指标维度的提问：

```python
quick_fetch_stock_financials(
    sec_list=["{stock_code}"],
    query_type=["income_statement", "balance_sheet", "cash_flow_statement", "financial_ratios", "consensus_estimate", "valuation"],
    financial_years=3,

    save_as="tmp/{session_id}/80_financial_data.md"
)
```

### Step 3：生成调研问题

1. 读取 `references/report-prompt.md`，按其中结构和覆盖维度组织问题。
2. 读取公告、点评、纪要、研报、投资者问答和财务数据，找出经营变化、预期分歧、数据缺口与待验证假设。
3. 生成问题清单，并使用 `write_file` 写入 `tree/{company_name}/{company_name}_调研问题.md`。
4. 交付前检查每个问题是否具体、可回答、对投资判断有增量，并在聊天中给出重点问题与文件链接。

## 注意事项

1. **数据覆盖面是核心**：5 类检索（点评/纪要/年报/研报/投资者问答）对应 7 大维度，缺失任一类都会导致对应维度问题质量下降
2. **doc_searcher instruction 写作规范**：每次委托时，instruction 中必须包含内容类型（点评/纪要/年报/研报/问答）、实体（股票代码）、时间范围、期望返回的业务信息和条数，便于选择正确的逻辑数据集和规范字段
3. **最终报告形成**：完成分析和写作；不得把最终写作转交给 SubAgent 或额外的写作模型
