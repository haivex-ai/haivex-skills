---
name: kr-jp-market-monitor
description: '韩国与日本股市日度监测技能，基于华泰证券《韩股日度监测体系》（2026/6/28）的6大模块框架并扩展至日本市场。当用户要求以下任务时触发：(1) 监测/跟踪/复盘韩股或日股（KOSPI、KOSDAQ、日经225、TOPIX）；(2) 生成韩国/日本股市监测日报、风险仪表盘；(3) 查韩股杠杆、散户、强制平仓、待入市保证金、外资流向、VKOSPI；(4) 查日股信用残高、投资主体别买卖动向、日经VI、日元套息交易、日银ETF；(5) 分析三星电子/SK海力士/存储ASP对韩股影响，或半导体链对日股影响；(6) 设置韩日股市定时监测任务。'
---

# 韩国·日本股市监测（KR/JP Market Monitor）

用 6 大模块日度监测韩国和日本股市：①市场表现 ②基本面与估值 ③杠杆与融资风险 ④资金与仓位 ⑤波动率与衍生品 ⑥宏观环境。框架源自华泰证券《韩股日度监测体系》（韩股是全球科技/AI 行情的"金丝雀"：科技硬件权重>50%、散户成交占比约35%、高杠杆高集中度），日本部分按同构逻辑用公开数据源映射（日股关键词：套息交易、外资主导、BOJ 政策）。

## 指标清单（先读对应参考文件）

- 监测韩国 → 读 [references/korea.md](references/korea.md)（6模块33指标：定义、数据路径、解读阈值）
- 监测日本 → 读 [references/japan.md](references/japan.md)（6模块对标映射：JPX投资主体、信用残高、日经VI、套息代理等）
- 生成日报 → 报告结构与解读规则见 [references/report_template.md](references/report_template.md)

## 执行流程

### Step 0：确认口径

- 市场范围：韩国 / 日本 / 双市场（默认双市场，若用户仅提一国则单市场）。
- 输出深度：快报（answer 直出核心表）vs 监测日报（主 Agent 按报告模板分析并落盘）。
- 时间锚点：韩日交易日历与 A 股不同，**以取数返回的最新日期为准报告**，标注"截至 X 月 X 日收盘"；勿用 trading_calendar 的 A 股日历推断韩日交易日。

### Step 1：结构化取数（主 Agent 直接调用，可并行）

已验证可用路径（symbol 已实测）：

| 数据                                  | 工具                                  | query/symbol 示例                                                                                      |
| ----------------------------------- | ----------------------------------- | ---------------------------------------------------------------------------------------------------- |
| KOSPI / KOSDAQ / 日经225 / TOPIX 日线   | `search_global_data`                | `^KS11` / `^KQ11` / `^N225` / `^TPX`，如 "KOSPI index daily close price from YYYY-MM-DD to YYYY-MM-DD" |
| 三星电子 / SK海力士 / 东京电子等权重股             | `search_global_data`                | `005930.KS` / `000660.KS` / `8035.T` / `9984.T`（quote 或 historical price）                            |
| USDKRW / USDJPY                     | `search_global_data` 或 `search_edb` | "USDKRW exchange rate daily close from ... to ..."                                                   |
| 日本10Y国债 / 美国10Y国债 / 美元兑日元 / DRAM现货价 | `search_edb`                        | 如 "日本10年期国债收益率 近三个月"（均已验证有数据）                                                                        |
| 云厂商 Capex / EPS 一致预期                | `search_global_data`                | "MSFT analyst estimates ..."（逐票查询）                                                                   |
| CFTC 日元投机净头寸（套息代理）                  | `search_global_data`                | "Japanese Yen COT report positioning"                                                                |

调用 `search_global_data` 前必须先 `read_skill('search-global-data')`；每次只传 1 条英文 query。

**已知陷阱（重要）**：

- 查 **VKOSPI / 日经VI** 时 `search_global_data` 会静默回退到标的指数（返回 ^KS11/^N225 而非波动率指数）——**核对返回的 symbol 列**，回退则改走 Step 2 网页源。
- 韩国 10Y 国债在 EDB 覆盖不稳，取不到时用 `search_global_data`（"South Korea 10 year government bond yield"）或网页兜底。
- EPFR 资金流无直接数据源，用 `search_paipai` 检索券商研报引用兜底，并标注转引口径。

### Step 2：公开网页源取数（search_web 定位 + fetch_web 深读）

杠杆/资金/波动率模块的核心独家数据在交易所与协会官网，见 korea.md / japan.md 中每个指标的 URL。关键源速查：

- 韩国：KOFIA freesis（融资余额·待入市保证金·强平）、KRX（投资主体流向）、SEIBRO（韩人海外买股）
- 日本：JPX 投资主体别买卖动向（周度，每周第4个营业日15:00更新）、JPX 信用残高、indexes.nikkei.co.jp（日经VI）、stock-marketdata.com/pcr.html（日经/TOPIX PCR）

官网反爬或格式异常时：不要反复重试，改用 `search_web` 检索财联社/证券时报等财经媒体对同一数据的报道作为兜底，并注明二手来源。

### Step 3：观点与事件补充

- `search_paipai`（sources=['comment','report','roadShow']，近2周）：查"韩股 监测/杠杆/散户"、"日本股市 日元 套息"等，获取券商最新解读。
- `search_web`（近1周）：突发事件（程序化交易暂停、汇率干预、BOJ/美联储议息、监管动作）。

### Step 4：产出

- **中间文件**：所有搜索/取数结果用 `save_as` 存到 `tmp/{session_id}/`，命名如 `01_kr_index.csv`、`02_jp_flows.md`；禁止用 write_file 手工造中间文件。
- **快报**：answer 直出"6模块 × 双市场"核心指标表 + 风险信号小结。
- **监测日报**：主 Agent 读取本技能相对路径 `references/report_template.md`，结合各中间文件完成分析，使用 `write_file` / `replace_file` 写入 `tmp/{session_id}/outputs/韩日股市监测日报_YYYYMMDD.md`。遵守模板中的结构、证据、数据日期和质量要求。
- 每个指标必须标注数据日期；历史分位、周变化等口径与原始来源对齐，不得混用不同日期数据合并表述。

### Step 5（可选）：定时任务

用户要求持续监测时，用 `cron` 创建工作日任务（建议北京时间 15:30 后，此时韩日均已收盘且 JPX 周度数据已更新），payload.message 沿用用户原话，并在 playbook 中固化本技能路径。

## 解读总纲（红绿灯逻辑）

监测的核心不是罗列数据，而是回答三个问题：

1. **脆弱性**：杠杆类指标（韩：融资余额/杠杆ETF/强平；日：信用残高/评价损益率）处于什么历史分位？高分位 = 波动放大器在位。
2. **资金结构**：谁在买谁在卖（韩：外资 vs 散户四主体；日：海外投资者 vs 个人）？散户主导 + 外资流出 = 结构脆弱；分歧度走扩是预警信号。
3. **触发器**：基本面预期（存储 ASP、Capex、EPS 修正方向）与宏观流动性（美债利率、日元套息、汇率）是否出现拐点？

各指标具体阈值（如 VKOSPI>40 恐惧区、日经VI 常态 15-25、信用评价损益率<-15% 追证压力区）见 korea.md / japan.md。
