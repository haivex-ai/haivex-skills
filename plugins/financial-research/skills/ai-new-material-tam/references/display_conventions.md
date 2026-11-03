# AI 材料测算 — 展示规范与 openpyxl 实现参考

本文件提供把展示规范落地到 Excel 的具体配色码、样式函数与代码片段。配合 `SKILL.md` 第二节"强制展示规范"使用。

## 目录
- 1. 配色常量表
- 2. openpyxl 样式工具函数
- 3. 单元格批注（来源标注）写法
- 4. 关键参数锚点区布局示例
- 5. Sources 表结构
- 6. 表头图例行模板
- 7. 跨表联动公式范式

## 1. 配色常量表（ARGB，openpyxl 用 8 位带 FF 前缀）

| 语义 | 名称 | ARGB | 用途 |
| --- | --- | --- | --- |
| 有来源 | YELLOW | `FFFFFF00` | 原始取数值、关键参数锚点值（标黄） |
| 测算值 | （无填充） | None | 所有 `=公式` 单元格 |
| 可调假设 | CREAM | `FFFFF8E1` | 假设输入区 |
| 表头 | HEADER_BLUE | `FF194F90` | 列标题（白字加粗） |
| 分类/小计 | LBLUE1 | `FFD6E4F0` | 分组标题、小计、跨表结果 |
| 分类/小计 | LBLUE2 | `FFDCE6F1` | 同上（次级） |

> 口诀：**黄=抄来的(有来源)，白=算出来的(有公式)，米黄=可调假设，深蓝=表头，浅蓝=分类/小计。**

## 2. openpyxl 样式工具函数

```python
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side

YELLOW   = PatternFill("solid", fgColor="FFFF00")   # 有来源
CREAM    = PatternFill("solid", fgColor="FFF8E1")   # 可调假设
HEADER   = PatternFill("solid", fgColor="194F90")   # 表头
LBLUE1   = PatternFill("solid", fgColor="D6E4F0")   # 分类/小计
LBLUE2   = PatternFill("solid", fgColor="DCE6F1")
HEADER_FONT = Font(color="FFFFFF", bold=True)
THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

def mark_source(cell):
    """标记为'有来源'单元格：标黄 + 加边框"""
    cell.fill = YELLOW
    cell.border = BORDER

def mark_calc(cell):
    """测算值单元格：白底(不填充)，仅加边框；值必须是公式字符串 '=...' """
    cell.border = BORDER

def mark_assume(cell):
    cell.fill = CREAM
    cell.border = BORDER

def make_header(cell):
    cell.fill = HEADER
    cell.font = HEADER_FONT
    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    cell.border = BORDER

def make_group(cell, level2=False):
    cell.fill = LBLUE2 if level2 else LBLUE1
    cell.font = Font(bold=True)
    cell.border = BORDER
```

## 3. 单元格批注（来源标注）写法

每个黄色（有来源）单元格加批注，文本格式 `[来源:N] 来源标题`；多来源示例为 `[来源:2,11] 来源标题`。编号须已在Sources表登记。标签放在批注中，不放进数值文本。

```python
from openpyxl.comments import Comment

def add_source_comment(cell, ids, title, author="AI材料测算"):
    """ids: int 或 list[int]，对应 Sources 表编号"""
    if isinstance(ids, (list, tuple)):
        tag = "[来源:" + ",".join(str(i) for i in ids) + "]"
    else:
        tag = f"[来源:{ids}]"
    cell.comment = Comment(f"{tag} {title}", author)

# 用法
add_source_comment(ws["Q4"], 3, "Morgan Stanley-GB300 BOM(Samsung报告引用)")
add_source_comment(ws["F9"], [2, 11], "MS-Rubin VR200 BOM拆解; 测算假设(基于大摩数据推算)")
```

## 4. 关键参数锚点区布局示例

把"有来源的原始数"集中放在假设表右侧（P/Q/R 列），单颗价值量公式引用锚点而非散落硬编码。

| P（参数名） | Q（数值，标黄） | R（来源） |
| --- | --- | --- |
| GB200机架总价($) | 3329523 | 来源:3 |
| GB300机架总价($) | 3994551 | 来源:3 |
| VR200机架总价($) | 7803148 | 来源:2 |
| 每机架GPU数 | 72 | 来源:2,3 |
| GB200 GPU占比 | 0.65 | 来源:3 |
| GB200 HBM($/rack) | 206000 | 来源:4 |
| GB200 PCB($/rack) | 35000 | 来源:6 |
| BW ABF($/chip) | 100 | 来源:8 |
| PCB中CCL占比 | 0.30 | 来源:15 |
| CCL中铜箔/树脂/玻纤占比 | 0.42 / 0.26 / 0.19 | 来源:15 |

单颗价值量公式示例（白色测算单元格，引用锚点）：
- 单颗 GPU = `=机架总价 × GPU占比 ÷ 每机架GPU数`，如 `=Q4*Q8/Q7`
- 单颗 HBM = `=机架HBM ÷ 72`，如 `=Q11/Q7`
- 单颗 PCB = `=机架PCB ÷ 72`，如 `=Q14/Q7`
- CCL 铜箔 = `=单颗PCB × CCL占PCB × 铜箔占CCL`，如 `=E6*0.30*0.42`
- 无直接来源的下一代芯片 = 上一代 × 溢价系数，如 R300 = `=B8*Q28`（Q28=1.18 溢价，标黄+批注说明为测算假设）

## 5. Sources 表结构（固定 5 列）

| 编号 | 来源标题 | 来源详情 | 数据范围 | 获取日期 |
| --- | --- | --- | --- | --- |
| 1 | 用户Excel-全球显卡出货预测量 | 各类GPU/ASIC出货量预测(万颗) | 2025-2028E | 2026-05-25 |
| 2 | Morgan Stanley-Rubin VR200 BOM拆解 | VR200机架$780.3万,各材料vs GB300变化 | PCB+233%,MLCC+182% | 2026-05-20 |
| … | … | … | … | … |

表头行用 `make_header`，编号唯一且全表批注引用。

## 6. 表头图例行模板（每个 Sheet 第 1-2 行）

- A1：`<标题>（<单位>）` — 例 `AI芯片单颗材料价值量假设表（美元/颗）`、`AI芯片各材料全球市场空间测算（亿美元）`
- A2：图例/逻辑说明，按表类型择一：
  - 价值量/假设表：`★ 黄色底色 = 有明确机构数据来源 ｜ 白色底色 = 基于折算比例的测算值（公式可见计算过程）`
  - 空间测算表：`测算逻辑：∑ 各型号[出货量(万颗) × 单颗材料价值量($/颗)] ÷ 10000 = 市场空间(亿美元)`
  - 利润测算表：`测算逻辑：各平台材料市场空间 × 对应芯片毛利率 = 材料利润空间 ｜ ★黄色=有官方财报来源的毛利率`
  - 光模块表：`★ 测算逻辑：机柜出货量 × 单机柜光模块数量 × 光模块ASP = 市场空间 ｜ 黄色=有明确来源`

## 7. 跨表联动公式范式

- 材料空间（逐型号显式相加，保持联动）：
  `='出货量汇总(万颗)'!B6*单颗材料价值量假设!D6/10000 + '出货量汇总(万颗)'!B7*单颗材料价值量假设!D7/10000 + …`
  （列：D=HBM、E=PCB、F=ABF、G=MLCC、H=电源、I=液冷、J=光纤、L/M/N=CCL铜箔/树脂/玻纤、O=封装基板）
- 合计：`=SUM(B5:B16)`
- CAGR：`=IFERROR((E5/B5)^(1/3)-1,"")`（4 年取 3 次方根；openpyxl 写 `=_xlfn.IFERROR(...)`）
- 机柜出货量：`='出货量汇总(万颗)'!B6/72`（NVIDIA 72/rack，ASIC 64/rack）
- 利润：空间 × 毛利率，毛利率单列引用，如 `=D18*$B$6`

## 实施要点清单（自检）
- [ ] 每个 Sheet 有 A1 标题 + A2 图例行
- [ ] 原始外部数据全部标黄且有 `[来源:N] 来源标题` 批注
- [ ] 测算单元格全部是 `=公式`，无硬编码计算结果
- [ ] 关键原始参数集中在锚点区，公式引用锚点
- [ ] Sources 表 5 列齐全，编号与批注一一对应
- [ ] 假设表底部有文字版【测算依据详细说明】
- [ ] 毛利率假设注明口径/来源/报告期
