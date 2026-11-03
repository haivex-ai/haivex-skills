# 数据与资料收集指引（第零步详解）

> 本文件详述穿透叙事分析"第零步：数据与资料收集"的工具编排、SubAgent 委托模板与中间文件管理规范。
> 核心原则：**任何叙事判断都必须建立在最新一手资料之上**。语义/文本类资料（公告、纪要、研报、点评）一律先用 `doc_searcher` 穷举式检索，再综合判断，禁止仅凭模型先验或零散 `search_paipai` 片段下结论。

## 目录

- [一、收集顺序总览](#一收集顺序总览)
- [二、结构化数据收集](#二结构化数据收集)
- [三、语义文本资料收集（doc_searcher 强制前置）](#三语义文本资料收集doc_searcher-强制前置)
- [四、中间文件命名规范](#四中间文件命名规范)
- [五、收集完成检查清单](#五收集完成检查清单)

---

## 一、收集顺序总览

在进入六步分析之前，必须先完成"第零步"的资料收集。推荐并行发起以下三路，全部结果落盘到 `tmp/{session_id}/`：


| 路别     | 内容                                      | 工具                                              | 落盘文件                                                        |
| ------ | --------------------------------------- | ----------------------------------------------- | ----------------------------------------------------------- |
| A 结构化  | 市值、总股本、一致预期 E1/E2/E3、财务三表、估值、行情（**分市场走 `collect_financials.py` 适配器**） | quick_fetch(.json) + data_analyst + search_global_data(美股) → `collect_financials.py` | `80_financial.json` → `dcf_params.json` |
| B 语义文本 | **最新公告 + 近半年纪要/研报/点评**（强制 doc_searcher，**四类可拆并行委托提速**） | `delegate_to_agent → doc_searcher`              | `01_ann.md`/`02_roadshow.md`/`03_report.md`/`04_comment.md` |
| C 行业空间与券商覆盖 | 行业 TAM、渗透率、竞争格局；**强制券商清单**的目标价/三年盈利预测/观点（有无目标价分流） | `search_paipai` + `search_web` + `doc_searcher` | `10_industry.md`/`11_targets.md`                            |


结构化数据（A）为 DCF 反算（第一步）提供输入；语义文本（B）为叙事判断（第二至五步）提供事实基础；行业空间（C）默认用于还原市场如何讨论行业空间/份额/利润率（不作本方理论区间）。仅当用户明确追问情景/建议时，才复用 C 类材料构造本方情景（见 `optional-scenario-advice.md`）。

---

## 二、结构化数据收集（分市场固化取数，强制走适配器）

> **【v1.1 稳定性改造·硬约束】** 实测（2026-08-28）证明：`quick_fetch_stock_financials` **对 A股/港股够用但缺总股本，对美股几乎完全为空**（stock_info/market_quote/valuation/consensus 全返回 `[]`）。因此**禁止**把 quick_fetch 当唯一取数入口。必须按市场分流，并统一用 `scripts/collect_financials.py` 把原始产物归一为唯一事实源 `dcf_params.json`——这是解决"同公司多跑数字不一致"的核心。取数口径（选哪三年、单位换算、consensus 排序、总股本补齐）一律由脚本固化，**不再由模型现场判断**。

### 2.0 分市场取数路径速查（先判市场，再走对应路径）

| 数据项 | A股/港股 (.SH/.SZ/.HK) | 美股 (.US) |
| --- | --- | --- |
| 市值 / 收盘价 | quick_fetch ✅ | **data_analyst（美股域）**（quick_fetch 空） |
| **总股本** | **data_analyst 补**（quick_fetch 无此字段） | **data_analyst**（quick_fetch 空） |
| 一致预期 E1/E2/E3 | quick_fetch `consensus_estimate` ✅ | **仅 search_global_data**（quick_fetch/data_analyst 美股域均无一致预期表） |
| 利润表 / 估值 | quick_fetch ✅ | data_analyst / search_global_data |

**美股一致预期口径（用户 2026-08-28 确认）**：`search_global_data` 的 `*_Financial_Estimates_Annual` 表默认偏返回**远端财年**（如 MU 只回 FY2028/29/30），近端 FY2026/FY2027 召回不稳。**接受"远端财年 + 研报盈利预测交叉"**：近端 E1/E2 缺失时，从 `03_report.md` 个股深度研报的未来 3 年净利润预测取均值补入，并在报告中标明"研报盈利预测交叉"口径。

### 2.1 A股 / 港股取数（两步）

**第一步** quick_fetch 一次取全并 `save_as` 为 **.json**（脚本需结构化字段，不用 .md）：

```python
quick_fetch_stock_financials(
    sec_list=["{code}.SZ"],            # A股 .SH/.SZ；港股 .HK
    query_type=["stock_info", "market_quote", "valuation", "income_statement", "consensus_estimate"],
    financial_years=5,
    save_as="tmp/{session_id}/80_financial.json"   # 必须 .json
)
```

**第二步** 委托 `data_analyst` 补总股本（quick_fetch 的 stock_info 无总股本字段）+ 最新市值兜底：

```python
delegate_to_agent(
    agent_type="data_analyst",
    instruction="查询 {公司名}（{code}）最新总股本（股）、最近一个交易日总市值（元与亿元）、收盘价、PE-TTM，如实回报数值与口径日期。结果概要直接回复即可，无需保存大文件。"
)
```

**第三步** 用适配器把两者归一装配为 `dcf_params.json`（`--shares-yi` 填 data_analyst 拿到的总股本，单位**亿股**；`--base-year` 填最近已披露完整年报年度=E0 年）：

```bash
python skills/user/penetrate-narrative-stock-analysis/scripts/collect_financials.py assemble-cn \
  --qf tmp/{session_id}/80_financial.json \
  --shares-yi {总股本亿股} --cap-yi {市值亿元} \
  --company {公司名} --code {code} \
  --base-year {E0年} --asof {分析日} --e0 {E0已披露净利润亿元} \
  --brokers-json tmp/{session_id}/11_targets.json \
  --out tmp/{session_id}/dcf_params.json
```

脚本自动完成：consensus 按 `forecast_year` 升序去重（同年取最新 `end_date`）、万元→亿元换算、按 E0+1/+2/+3 选 E1/E2/E3、市值≈价×股本自检。

> 只想看 quick_fetch 可得性时先跑：`collect_financials.py inspect-qf --qf tmp/{session_id}/80_financial.json`

### 2.2 美股取数（三步）

**第一步** 委托 `data_analyst`（美股域）取股本/市值/收盘价（**不要**用 quick_fetch，美股为空）：

```python
delegate_to_agent(
    agent_type="data_analyst",
    instruction="查询 {公司名}（{code}，美股）最新总股本（shares outstanding，股/百万股）、最新市值（百万美元）、最近一个交易日收盘价（美元），如实回报数值、单位、日期。无需保存大文件。"
)
```

**第二步** `search_global_data` 取一致预期（先 `read_skill('search-global-data')`；美股一致预期的唯一来源）：

```python
search_global_data(queries=["{Company} {TICKER} analyst net income and EPS estimates for the next fiscal years"])
# 产物落在 tmp/{session_id}/table/全球数据库-{TICKER}_Financial_Estimates_Annual.csv
```

**第三步** 适配器装配（美股以**亿美元**记账；近端财年缺失会告警，提示需研报交叉）：

```bash
python skills/user/penetrate-narrative-stock-analysis/scripts/collect_financials.py assemble-us \
  --shares-yi {总股本亿股} --cap-usd-yi {市值亿美元} --price {收盘价美元} \
  --est-csv tmp/{session_id}/table/全球数据库-{TICKER}_Financial_Estimates_Annual.csv \
  --company {公司名} --code {code} \
  --base-year {E0财年结束年} --asof {分析日} --e0 {E0净利润亿美元} \
  --brokers-json tmp/{session_id}/11_targets.json \
  --out tmp/{session_id}/dcf_params.json
```

若脚本告警 `e1/e2 缺失`：从 `03_report.md` 个股深度研报提取对应财年净利润预测均值，手动补入 `dcf_params.json` 的 `e1`/`e2`，并在 `e_notes` 标注"研报盈利预测交叉"。**注意 MU 等非 12 月财年**：`base-year` 用财年结束年（美光 FY2025 结束于 2025-08），估计 csv 的 `date` 年份即财年结束年。

> **数据源标注约束**：对外及报告中一律标注"来源于 Alpha派数据库"，禁止写 Wind/同花顺/Bloomberg 等第三方产品名。

### 2.3 装配后必做自检

`assemble-cn/assemble-us` 结束会打印自检。进入第一步 DCF 前确认：cap/shares/E1-E3 齐全；市值≈价×股本（差>3% 需复核口径/币种）；E1≤E2≤E3 或已确认周期见顶回落。`dcf_params.json` 生成后，`dcf_implied.py` 与 `build_dcf_workbook.py` **一律只读它**，三处口径天然同源。

---

## 三、语义文本资料收集（doc_searcher 强制前置）

**这是本次优化的核心要求。** 凡涉及叙事、经营边际变化、管理层预期、券商观点、市场分歧的判断，都必须先由 `doc_searcher` 穷举检索以下四类文本，再综合判断。`doc_searcher` 是唯一能保证检索完整性的工具（`search_paipai` 的 RAG 只能补充语义召回，不能替代穷举）。

时间口径（以当前分析日为基准）：

- **公告**：最新一批，覆盖最近 1 份定期报告 + 近期重大事项公告（一般回溯近 6-12 个月，确保包含最新季报/年报/业绩预告）
- **纪要 / 研报 / 点评**：**最近半年**（起始日 = 分析日往前 6 个月）

一次委托 `doc_searcher` 完成四类检索，每类 `save_as` 独立文件、禁止筛选截断：

> **字段名以实测的研报索引 mapping 为准**（已验证）：标题 `title`、发布日期 `time`（**不是 `date`**）、机构 `institution.name`（**不是 `institution`**）、评级 `rating`（独立字段但常为空）、正文摘要 `content`、全文 `full_content`、个股 `stock.code`/`stock.name`。**目标价与盈利预测无独立结构化字段**，只能从 `content`/`full_content` 解析。委托时直接用中文描述需要的信息即可（如“含目标价、评级、盈利预测的正文”），不要指定不存在的字段名。
>
> **研报必须用 `stock.code` 精确过滤 + 限定个股深度报告**：实测发现若不限定，召回的大多是“仅提及该股”的行业周报/策略报告/晨会纪要（把该股当相关标的罗列），而非带明确目标价的个股覆盖报告。券商目标价反算需要的是后者，须在委托中明确“只要以 {公司名} 为主要覆盖对象、含目标价/盈利预测的个股深度研报”。

```python
delegate_to_agent(
    agent_type="doc_searcher",
    instruction=(
        "检索 {公司名}（{code}）以下四类文档，用 stock.code={code} 精确过滤，每类分别通过 save_as 保存到独立文件，"
        "禁止对内容做任何筛选或截断，完成后列出所有文件路径与各文件内容概要：\n"
        "(1) 最新公告：时间范围 {分析日-12月}~{分析日}，重点覆盖最近的定期报告(年报/季报)、"
        "业绩预告/快报、重大合同/投资/股权激励/回购等重大事项；返回15条，"
        "返回标题、发布日期(time)、公告类型、正文摘要(content)，save_as='tmp/{session_id}/01_ann.md'；\n"
        "(2) 路演/调研纪要：时间范围 {分析日-6月}~{分析日}，返回8条，"
        "返回标题、发布日期(time)、机构(institution.name)、正文(content)，save_as='tmp/{session_id}/02_roadshow.md'；\n"
        "(3) 个股深度研报：只要以 {公司名} 为主要覆盖对象、带明确目标价或盈利预测的个股报告（排除仅将其作为相关标的罗列的行业周报/策略报告/晨会纪要），"
        "时间范围 {分析日-6月}~{分析日}，返回12条；返回标题、发布日期(time)、机构(institution.name)、评级(rating)，"
        "并从正文 content/full_content 中提取目标价、盈利预测(未来3年净利润)、TAM/市占率/净利率假设，"
        "save_as='tmp/{session_id}/03_report.md'；\n"
        "(4) 券商点评：时间范围 {分析日-6月}~{分析日}，返回15条，"
        "返回标题、发布日期(time)、机构(institution.name)、正文(content)，save_as='tmp/{session_id}/04_comment.md'。\n"
        "不知道股票代码时按公司名检索实体识别索引。"
    )
)
```

委托要点：

- **时间范围务必显式写日期**（`YYYY-MM-DD`），研报/纪要/点评统一取分析日往前 6 个月；公告放宽到 12 个月以确保覆盖最新定期报告。
- **字段名以实测 mapping 为准**：日期用 `time`、机构用 `institution.name`；目标价/盈利预测无独立字段，需从 `content`/`full_content` 解析（研报这一类允许拉 `full_content` 以便提取目标价，其余三类取 `content` 摘要即可）。
- **研报用 `stock.code` 精确过滤并限定个股深度报告**，避免召回大量行业周报/策略报告。
- **数量**：公告 15 / 纪要 8 / 研报 12 / 点评 15 为默认下限，标的资料丰富可上调；若某类命中不足须在概要中说明检索情况。
- 结果量大时 `doc_searcher` 只回文件路径 + 命中数 + 概要，不回全文。

> **【v1.1 提速选项·四类拆并行】** 上方单次大委托可读，但四类串行耗时长。若追求速度，可在**同一轮**发起多个 `delegate_to_agent(agent_type="doc_searcher", ...)` 将四类（或至少把最慢/最重的**研报**单拆一路）并行：公告一路、纪要一路、研报一路（强制 `stock.code` 精确过滤 + 排除行业周报/策略/晨会）、点评一路。每路仍照上面要点写清时间窗/条数/字段/`save_as` 独立文件；串行变并行可显著提速，且研报单路专用模板能降低目标价召回漂移。研报这一路建议 `save_as` 用 **.json** 以便后续解析目标价。

`search_paipai` 作为语义补充（可选，与 doc_searcher 并行）：

```python
search_paipai(
    queries=["{公司名} 最新业绩 边际变化", "{公司名} 天花板 出海 第二增长曲线", "{行业} 竞争格局 龙头 份额"],
    sources=["ann", "roadShow", "report", "comment"],
    start_time="{分析日-6月}", end_time="{分析日}",
    save_as="tmp/{session_id}/05_paipai_semantic.md"
)
```

---

## 四、中间文件命名规范

统一保存到 `tmp/{session_id}/`，禁止用 `write_file` 手动创建搜索类中间文件（一律用 `save_as`/`file_name`）：


| 文件                      | 内容            | 来源工具                           |
| ----------------------- | ------------- | ------------------------------ |
| `01_ann.md`             | 最新公告          | doc_searcher                   |
| `02_roadshow.md`        | 近半年纪要         | doc_searcher                   |
| `03_report.md`          | 近半年研报（含目标价）   | doc_searcher                   |
| `04_comment.md`         | 近半年点评         | doc_searcher                   |
| `05_paipai_semantic.md` | 语义补充片段        | search_paipai                  |
| `10_industry.md`        | 行业 TAM / 竞争格局 | search_web / doc_searcher      |
| `11_targets.md`         | 券商目标价清单       | doc_searcher / search_paipai   |
| `80_financial.md`       | 个股财务快照        | quick_fetch                    |
| `81_financial_ts.csv`   | 财务时序          | data_analyst                   |
| `90_dcf_implied.json`   | DCF 反算结果      | scripts/dcf_implied.py         |
| `91_brokers.json`       | 券商目标价反算结果     | scripts/dcf_implied.py brokers |


最终按章节或主题读取必要证据，核对口径后使用 `write_file` 生成报告；不要把未读取的中间文件直接当成已核验事实。

---

## 五、收集完成检查清单

进入第一步 DCF 反算前，确认：

- [ ] 已取得总股本、当前市值、E1/E2/E3 一致预期净利润（结构化）
- [ ] **已用 doc_searcher 检索最新公告**（含最近一份定期报告/业绩预告）
- [ ] **已用 doc_searcher 检索近半年纪要、研报、点评**（研报含目标价/评级）
- [ ] 已按强制清单检索外资（高盛、摩根士丹利、瑞银、花旗、摩根大通、汇丰、瑞杰、伯恩斯坦、Barclays）与内资（中金、中信、国君、华泰、招商、天风、长江、华源、兴业、华创、国盛、中信建投、开源、中泰）；有目标价写入 DCF 列表，无目标价保留三年盈利预测与主要观点
- [ ] 已收集市场观点中的行业 TAM / 竞争格局 / 利润率表述（默认用于列示；若用户追问情景分析可复用为情景假设素材）
- [ ] 上述资料均落盘 `tmp/{session_id}/`，路径已登记供成文阶段读取

任一语义文本类检查项缺失时，**不得**直接进入叙事判断——必须补检索。资料确实缺失（如冷门标的无纪要）时，在报告中明确披露"该类资料检索情况"，不得用模型先验替代。
