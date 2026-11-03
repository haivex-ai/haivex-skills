---
name: company-one-pager
description: '上市公司一页纸技能，适用于用户仅输入公司名或股票代码、要求快速了解某家公司、公司概览/速览、一页纸报告，或给出不熟悉公司希望买方视角快速了解。自动识别 A股/港股/美股并采用对应数据采集流程和报告模板；查具体财务/行情用数据查询技能。'
---

# 公司一页纸 Skill

为上市公司（A股/港股/美股）生成买方视角的投研快速了解报告，自动识别市场类型并采用对应的数据采集流程和报告模板。

## 核心原则（最高优先级）

1. **执行要求**：组织检索、读取公司材料、形成买方视角判断并完成写作。`search_paipai` 和 `doc_searcher` 只提供材料，不能替代分析判断。
2. **证据处理**：检索阶段不要无依据地截断原文；`doc_searcher` 通过 `save_as` 将结果保存到独立文件。写作阶段读取必要材料，核对公司身份、报告期、业务结构、财务口径和市场分歧。
3. **中间文件与交付**：搜索类结果通过 `save_as` 保存，避免无意义地占用上下文；不要用 `write_file` 伪造未检索到的证据。最终报告使用 `write_file` / `replace_file` 写入交付文件。
4. **检索扩展**：除下方规定的检索任务外，可根据对公司的理解，发起额外的 `doc_searcher` 检索来补充有价值的数据，如行业对比、上下游信息、近期重大事件。
5. **doc_searcher 零结果容错**：当某个 doc_searcher 委托返回空结果时，自动扩大时间范围重试一次。若仍为空则跳过该文件，不影响其他检索和最终合并流程。

## 输入要求

必须从用户获取：
- **company_name**：公司名称（如"贵州茅台"、"NVIDIA"、"英伟达"）
- **stock_code**：股票代码（如"600519.SH"、"NVDA.O"）
- **language**：输出语言（默认"中文"，若用户指定 "English" 则替换，仅美股适用）

若用户未提供股票代码，通过搜索确认后再继续。

## 市场识别

根据 stock_code 后缀自动判断市场类型，决定后续数据采集流程和报告模板：

| 后缀模式 | 市场类型 | 示例 |
|---------|---------|------|
| `.SH` / `.SZ` / `.BJ` | A股 | 600519.SH、000001.SZ |
| `.HK` | 港股 | 00700.HK |
| `.O` / `.N` | 美股（纳斯达克/纽交所） | NVDA.O、BRK.N |

## 工作流程

### Step 1：确认输入

确认 company_name 和 stock_code。若用户未提供股票代码，通过搜索确认。优先使用 stock_code 进行后续查询：
- **A股/港股**：必须使用交易所后缀（.SH/.SZ/.BJ/.HK）
- **美股**：必须带交易所后缀（.O 纳斯达克，.N 纽交所）

根据市场识别结果，进入 Step 2A（A股/港股）或 Step 2B（美股）。

### Step 2A：A股/港股数据采集

以下所有数据收集任务**并行执行**，分为语义背景、受控文档检索和 API 财务数据三大类。

#### 2A-1：search_paipai 语义背景

使用 `search_paipai` 获取该公司的基础背景信息和近期市场讨论：

```python
search_paipai(
    query="{company_name} 最新动态 市场观点 投资逻辑",
    sources=["report", "roadshow", "comment"],
    top_k=15,
    save_as="tmp/{session_id}/01_paipai_bg.md"
)
```

#### 2A-2：doc_searcher 委托（1 次合并发起）

通过 `delegate_to_agent(agent_type="doc_searcher", ...)` 发起**一次**合并检索：

```python
delegate_to_agent(
    agent_type="doc_searcher",
    instruction="检索{company_name}（{stock_code}）的以下四类文档，每类结果分别通过 save_as 保存到独立文件：(1) 近3个月的文字点评，返回20条，保留标题、时间、正文、推荐语、分析师、机构和证券，save_as='tmp/{session_id}/02_comments.md'；(2) 近1年的公开路演纪要，返回3条，优先 AI 总结纪要，保留标题、日期、证券、机构、总结和正文，save_as='tmp/{session_id}/03_roadshow.md'；(3) 最近的年报或半年报公告，返回2条，公告类型代码为020201或020301，保留标题、发布时间、公告类型及代码、证券、报告期末日和正文，save_as='tmp/{session_id}/04_announcements.md'；(4) 近1年的研究报告，返回3条，保留标题、时间、作者、机构、行业、证券、报告类型和正文，save_as='tmp/{session_id}/05_reports.md'。禁止对内容做任何筛选或截断。完成后在回复中列出所有已保存的文件路径及各文件的内容概要。"
)
```

**自由补充检索（可选）**：可根据对公司的理解，发起额外的 `doc_searcher` 委托检索其他有价值的数据，如行业对比、上下游信息、近期重大事件；结果保存为 `tmp/{session_id}/90_extra_{N}.md`。

#### 2A-3：财务数据（通过 quick_fetch_stock_financials 获取）

使用 `quick_fetch_stock_financials` 一次性获取全部财务数据：

```python
quick_fetch_stock_financials(
    sec_list=["{stock_code}"],
    query_type=["income_statement", "balance_sheet", "cash_flow_statement", "financial_ratios", "consensus_estimate"],
    financial_years=3,
    save_as="tmp/{session_id}/80_financial_data.md"
)
```

### Step 2B：美股数据采集

文档检索、标准化海外数据和互联网资讯三类任务可并行发起；每条数据链内部仍按其路由与依赖顺序执行。

#### 2B-1：doc_searcher 委托（1 次合并发起）

通过 `delegate_to_agent(agent_type="doc_searcher", ...)` 发起**一次**合并检索：

```python
delegate_to_agent(
    agent_type="doc_searcher",
    instruction="检索{company_name}（{stock_code}）的以下四类文档，每类结果分别通过 save_as 保存到独立文件：(1) 近1年的美股业绩电话会议纪要，返回5条，保留标题、发布日期、证券名称、总结和正文，save_as='tmp/{session_id}/doc_earnings_call.md'；(2) 近1年的美股非业绩会议纪要（投资者日/行业会议/公司路演等），返回5条，保留标题、发布日期、证券名称、总结和正文，save_as='tmp/{session_id}/doc_other_meetings.md'；(3) 近1年的中国券商研究报告摘要，返回10条，保留标题、时间、作者、机构、证券和正文，save_as='tmp/{session_id}/doc_cn_reports.md'；(4) 近3个月的市场点评，返回10条，保留正文、时间和证券名称，save_as='tmp/{session_id}/doc_comments.md'。四类结果分别按时间倒序。禁止对内容做任何筛选或截断。完成后在回复中列出所有已保存的文件路径及各文件的内容概要。"
)
```

#### 2B-2：标准化美股数据（`search_global_data`）

先读取 `us-stock-data` 与 `search-global-data`，再把不同主题拆成独立英文 query。单公司行情、常规财务、估值和一致预期优先走 `search_global_data`；只有标准化接口不能覆盖且确实需要复杂筛选、排序或多对象整理时，才窄范围委派 `data_analyst`。

```python
# 公司资料与最新行情分别查询，避免把不同主题塞进同一 query
search_global_data(
    queries=["{company_name} {stock_code} US listed company profile"],
    save_as="tmp/{session_id}/us_company_profile.md"
)
search_global_data(
    queries=["{company_name} {stock_code} latest US stock quote snapshot including 52-week range"],
    save_as="tmp/{session_id}/us_quote_snapshot.md"
)
search_global_data(
    queries=["{company_name} {stock_code} annual income statement and cash flow key metrics for the last 5 reported fiscal years"],
    save_as="tmp/{session_id}/us_financial_annual.md"
)
search_global_data(
    queries=["{company_name} {stock_code} quarterly revenue net income and EPS for the last 12 reported fiscal quarters"],
    save_as="tmp/{session_id}/us_financial_quarterly.md"
)
search_global_data(
    queries=["{company_name} {stock_code} latest valuation ratios"],
    save_as="tmp/{session_id}/us_valuation.md"
)
search_global_data(
    queries=["{company_name} {stock_code} latest analyst revenue and EPS estimates"],
    save_as="tmp/{session_id}/us_estimates.md"
)
```

#### 2B-3：互联网实时资讯（直接调用 search_web）

调用 `search_web` 搜索以下内容，获取最近3个月的公开信息；需要近 15 天新闻时也在这里按来源与时间筛选，不要交给 DA：

1. `{company_name}` 最新经营动态、业绩反应与市场观点（Yahoo Finance / Reuters / CNBC / SeekingAlpha）
2. 知名投资大V在社交平台（Twitter/X、Reddit）发布的针对 `{company_name}` 的有价值观点

将搜索结果通过 `save_as` 参数保存为 `tmp/{session_id}/web_news.md`。

### Step 3：生成报告

1. A股/港股读取 `skills/company-one-pager/references/report-prompt-cn.md`；美股读取 `skills/company-one-pager/references/report-prompt-us.md`。
2. 读取实际生成的检索、财务和市场材料，核对主体、报告期、币种、单位、TTM/单季度口径与缺失项。
3. 完成业务、财务、估值、催化与风险分析，并使用 `write_file` 写入最终文件：
   - A股/港股：`tree/{company_name}/{company_name}_一页纸.md`
   - 美股：`tree/{company_name}/{company_name}_US_One_Pager_{当前日期}.md`
4. 交付前检查模板要求、数据一致性、来源与缺口，并在聊天中给出核心结论和文件链接。

## 数据权威性排序

- **A股/港股**：ann（公告）> report（研报）> roadshow（纪要）> comment（点评）> social_media（社媒）
- **美股**：ann（公告）> report（研报）> us_roadshow（美股纪要）> comment（点评）> social_media（社媒）

## 注意事项

1. **时间参数**：end_time 必须 ≤ 当前日期，严禁使用未来时间
2. **股票代码**：A股/港股需带交易所后缀（.SH/.SZ/.BJ/.HK），美股需带交易所后缀（.O 纳斯达克，.N 纽交所）
3. **Query 原则**：单一主体、单一时间、单一主题
4. **报告输出**：完成分析与写作，使用 `write_file` / `replace_file` 落盘；不得把最终写作转交给 SubAgent
5. 若某个 doc_searcher 委托无命中，继续执行其他委托，合并时跳过空文件
6. 读取报告模板后，根据本轮上下文替换 `{company_name}` 和 `{language}` 占位符
7. **doc_searcher instruction 写作规范**：每次委托时，instruction 中必须包含内容类型、实体（股票代码）、时间范围、期望返回的业务信息和条数，便于选择正确的逻辑数据集和规范字段
8. **财务数据**：A股/港股通过 `quick_fetch_stock_financials` 获取；美股标准化数据优先通过 `search_global_data` 获取，DA 仅作复杂本地目录查询兜底
9. **最终报告形成**：基于已核验材料独立形成判断并完成写作
10. **数据口径**：报告期、币种、单位以及 TTM/单季度口径必须原样保留，缺失值不得按 0 补齐
