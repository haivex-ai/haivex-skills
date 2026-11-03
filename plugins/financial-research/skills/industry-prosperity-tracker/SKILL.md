---
name: industry-prosperity-tracker
description: >
  全行业景气度跟踪模型。基于高频(周度)与中频(月度)指标，跟踪并横向比较各行业(申万一级/新兴成长赛道)的景气度，
  输出景气评分看板与跟踪报告。内置强制的「数据验证(V1-V5)」与「结论Challenge(C1-C5)」双重校验，防范高频数据噪音、
  季节性扰动与伪景气信号。适用场景：(1)用户要求跟踪/比较全行业或某几个行业的景气度、景气度打分、行业轮动、
  景气趋势(如"跟踪一下当前各行业景气度""电力设备/工程机械景气怎么样""哪些行业景气向上")；
  (2)用户提到"景气度""中观景气""高频跟踪""行业景气跟踪""景气评分""扩散指数"等关键词；
  (3)需要把分散的价格/产量/开工率/库存/出口等高频中频数据，转化为可比较的景气结论并叠加配置含义。
  不适用：单一公司的财务深度分析(用deep-stock-research)、订单转收入测算(用order-to-revenue-model)、
  产能周期阶段判断(用industry-capacity-cycle)。
---

# 全行业景气度跟踪模型 (Industry Prosperity Tracker)

## 这个 Skill 做什么

把分散在研报/数据库里的**高频(周/日)与中频(月)景气指标**，按统一方法论转化为**可横向比较的行业景气评分**，并强制经过**数据验证**与**结论 Challenge** 两道防线，最终输出：
- **Excel 景气度看板**（评分总表 / 指标明细 / 数据验证 / 结论Challenge 共 4 Sheet）
- **Markdown 景气度跟踪报告**（结论先行 → 分板块详述 → 验证 → Challenge → 配置含义）

核心方法论沉淀于 `references/`，测算与出表由 `scripts/` 的纯标准库引擎完成。

---

## 何时使用

- 用户要跟踪 / 比较**全行业**或**指定若干行业**的景气度、做景气评分、行业轮动、景气趋势研判。
- 用户给出关键词：景气度 / 中观景气 / 高频跟踪 / 行业景气跟踪 / 景气评分 / 扩散指数 / 景气向上(下)。
- 需要把价格、产量、开工率、库存、出口、PPI/PMI/社零等指标合成为景气结论。

**边界**：单公司财务分析→`deep-stock-research`；订单转收入→`order-to-revenue-model`；产能周期阶段→`industry-capacity-cycle`。

---

## 工作流（6 步）

### Step 1 — 明确跟踪范围与频率
确认：①跟踪哪些行业（全行业 30 个 / 指定板块 / 用户重点赛道如电力设备、工程机械、有色、电子等）；②频率（周度高频跟踪 / 月度中频更新）；③截止时间（数据 as_of 日期）。
- 若用户未指定，默认覆盖**五大板块代表行业**，as_of 取最近一个完整周（周度）或最近披露月（月度）。
- 读取 `references/indicator_dictionary.md`，为每个目标行业锁定其**核心高频指标 + 中频指标**清单。

### Step 2 — 取数（按指标路径分流）
对每个行业的指标，按 `indicator_dictionary.md` 第六节「数据获取路径速查」分流取数：
- 国内大宗价格 / 产量 / 开工率 / 库存（时序）→ `search_cn_marketdata`
- 宏观与行业月度指标（PPI/PMI/社零/发电量/挖机销量等）、同比环比/分位数计算 → `delegate_to_agent(data_analyst)`（EDB 引擎，标准口径）
- 海外价格（原油/LME/Comex/费半/海运价）→ `search_global_data`（先 `read_skill('search-global-data')`）
- 指标定义 / 景气解读 / 分析师观点 → `search_paipai` + `doc_searcher`

**取数原则**：每个指标记录 `最新值 / 上期值 / 同比 / 频率 / 单位 / 更新日期`；高频价格优先用结构化接口，不直接采信研报/网页里的实时数字。

### Step 3 — 构建 config 并运行评分引擎
把取到的数据整理成 config JSON（结构见 `scripts/demo_config.json`），每个行业含 `board / macro_anchor / macro_anchor_direction / indicators[]`，指标含 `dim(price/volume/inventory/profit/valuation_quantile) / direction(up/down) / latest / prev / yoy / freq / unit / update`。
- 写 config 用 `write_file` 直接写 JSON 字符串（**勿用 tool_code 写文件，会触发 With 语法限制**）。
- 运行：`python3 scripts/prosperity_engine.py <config.json> <result.json>`（纯标准库，shell 执行）。
- 引擎输出：扩散指数、趋势箭头(↑/↓/–)、五维评分、综合景气分，以及 V1-V5 验证与 C1-C5 Challenge。

评分方法论详见 `references/scoring_validation_challenge.md`（扩散指数法 / 多维打分卡 / 新兴产业六维 / 景气-超额收益领先滞后映射）。

### Step 4 — 数据验证（强制第一道防线）
检查引擎输出的 `validation`（V1 口径时效 / V2 季节性 / V3 量价库存交叉 / V4 宏观锚一致 / V5 多源），对**存疑/警示**项：
- 春节窗口(1-2月)优先看同比；剔除更新滞后的僵尸指标；
- 价格涨但库存升/开工降 → 标注成本推动/挺价的伪景气可能；
- 行业景气方向与宏观锚(PPI对上游/CPI对下游/PMI对中游[见字典第〇节])背离 → 判断高频领先 or 单指标失真。
任一关键指标存疑，回到 Step 2 补数或换源，不得带病打分。

### Step 5 — 结论 Challenge（强制第二道防线）
对引擎输出的 `challenges`（C1 拐点真伪 / C2 传导时滞 / C3 单指标依赖 / C4 周期位置 / C5 需求透支）逐条审视，并人工补充：
- 抢装/抢出口/抢转型是否透支远期需求（光伏、新能源车、关税链）；
- 同比高增是否仅是低基数；
- 高频→业绩传导时滞（约 1-2 季度），勿把本周高频改善等同当季业绩；
- 景气高分位是否接近见顶、供给端在建产能是否压制远期景气。
每个行业景气结论必须附带至少一条 Challenge。

### Step 6 — 出表与成文
- 生成看板：`python3 scripts/build_dashboard.py <result.json> <config.json> <out.xlsx>`（依赖 openpyxl，shell 执行；4 Sheet）。
- 撰写 Markdown 报告：**结论先行**（哪些行业景气↑/↓/分化、综合分排序）→ 分板块详述（量价库存逻辑）→ 数据验证小结 → Challenge 风险清单 → **配置含义**（叠加 `scoring_validation_challenge.md` 1.4 的领先滞后映射做时滞修正）。
- 每个数据点标注来源（结构化数据标取数接口，观点标研报/纪要）。

---

## 关键设计原则

1. **双重校验是硬约束**：任何景气结论都必须先过 V1-V5 验证、再过 C1-C5 Challenge，二者缺一不可。这是本模型区别于普通"指标罗列"的核心。
2. **高频信号最强在中游制造**，价格类指标历史吻合度最高；上游看 PPI 链、下游看 CPI/社零链[见字典第〇节]。
3. **景气≠超额收益同步**：空间大/确定性强的赛道超额收益领先景气拐点约 1 季度，配置建议须叠加时滞修正。
4. **季节性是高频最大陷阱**：1-2 月春节扰动优先看同比。
5. **新兴成长赛道**额外用六维打分（政策依赖/全球竞争力/周期性/当前景气/中报兑现/估值）横向比较。

---

## 文件清单

- `references/indicator_dictionary.md` — 全行业景气指标字典（五大板块 + 申万一级 + 新兴赛道 + 宏观锚映射 + 取数路径）
- `references/scoring_validation_challenge.md` — 评分方法论 + 数据验证(V1-V5) + 结论Challenge(C1-C5) + 输出规范
- `scripts/prosperity_engine.py` — 景气评分引擎（纯标准库：扩散指数/多维打分/验证/Challenge）
- `scripts/build_dashboard.py` — Excel 景气度看板生成器（openpyxl，4 Sheet）
- `scripts/demo_config.json` — config 结构示例（煤炭/工程机械两行业）

## 环境注意
- 写 config / 脚本文件用 `write_file`，**勿用 tool_code 写文件**（With 语法限制）。
- `tool_code` 无法 import pandas/openpyxl；引擎用纯标准库，Excel 生成走 `shell python3`。
