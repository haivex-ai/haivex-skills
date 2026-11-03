#!/usr/bin/env python3
"""
build_tam_model.py — 生成符合「AI 新材料市场空间测算」展示规范的 Excel 骨架。

产出 8 个 Sheet（单颗材料价值量假设 / 出货量汇总 / 材料空间测算 / 分平台材料空间明细 /
材料利润空间测算 / 光模块市场空间测算 / AI芯片市场空间测算 / Sources），
并预置：配色、A1标题+A2图例行、表头、Sources 5列模板、关键参数锚点区占位。

用法:
    python3 build_tam_model.py <输出xlsx路径>

生成后请：填入出货量与锚点参数(标黄+批注) → 单颗价值量与空间/利润写公式(白色) → 校验 check_tam_format.py
"""
import sys
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.comments import Comment

YELLOW = PatternFill("solid", fgColor="FFFF00")
CREAM  = PatternFill("solid", fgColor="FFF8E1")
HEADER = PatternFill("solid", fgColor="194F90")
LBLUE1 = PatternFill("solid", fgColor="D6E4F0")
HEADER_FONT = Font(color="FFFFFF", bold=True)
THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

LEGEND_VALUE  = "★ 黄色底色 = 有明确机构数据来源 ｜ 白色底色 = 基于折算比例的测算值（公式可见计算过程）"
LEGEND_SPACE  = "测算逻辑：∑ 各型号[出货量(万颗) × 单颗材料价值量($/颗)] ÷ 10000 = 市场空间(亿美元)"
LEGEND_PROFIT = "测算逻辑：各平台材料市场空间 × 对应芯片毛利率 = 材料利润空间 ｜ ★黄色=有官方财报来源的毛利率"
LEGEND_OPTIC  = "★ 测算逻辑：机柜出货量 × 单机柜光模块数量 × 光模块ASP = 市场空间 ｜ 黄色=有明确来源"


def title_row(ws, title, legend):
    ws["A1"] = title
    ws["A1"].font = Font(bold=True, size=12)
    ws["A2"] = legend
    ws["A2"].font = Font(italic=True, color="C00000")


def header_row(ws, row, headers, start_col=1):
    for i, h in enumerate(headers):
        c = ws.cell(row=row, column=start_col + i, value=h)
        c.fill = HEADER
        c.font = HEADER_FONT
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = BORDER


def group_row(ws, row, text, col=1):
    c = ws.cell(row=row, column=col, value=text)
    c.fill = LBLUE1
    c.font = Font(bold=True)


def build(path):
    wb = Workbook()

    # ---- Sheet1: 单颗材料价值量假设 ----
    ws1 = wb.active
    ws1.title = "单颗材料价值量假设"
    title_row(ws1, "AI芯片单颗材料价值量假设表（美元/颗）", LEGEND_VALUE)
    mat_cols = ["芯片平台", "机架总价\n(万美元/rack)", "GPU芯片\n($/颗)", "HBM内存\n($/颗)",
                "PCB\n($/颗)", "ABF基板\n($/颗)", "MLCC\n($/颗)", "电源\n($/颗)",
                "液冷\n($/颗)", "光纤连接\n($/颗)", "光模块\n($/颗)", "CCL铜箔\n($/颗)",
                "CCL树脂\n($/颗)", "CCL玻纤\n($/颗)", "封装基板\n($/颗)"]
    header_row(ws1, 4, mat_cols)
    for r, g in [(5, "一、NVIDIA高端GPU"), (11, "二、ASIC定制芯片"),
                 (15, "三、AMD GPU"), (20, "四、国产AI芯片")]:
        group_row(ws1, r, g)
    # 关键参数锚点区占位（P/Q/R）
    ws1["P3"] = "关键参数锚点（供公式引用）"
    ws1["P3"].font = Font(bold=True)
    anchors = [("GB200机架总价($)", 3), ("GB300机架总价($)", 3), ("VR200机架总价($)", 2),
               ("每机架GPU数", "2,3"), ("GB200 GPU占比", 3), ("GB200 HBM($/rack)", 4),
               ("GB200 PCB($/rack)", 6), ("BW ABF($/chip)", 8), ("PCB中CCL占比", 15),
               ("CCL中铜箔占比", 15), ("CCL中树脂占比", 15), ("CCL中玻纤占比", 15)]
    for i, (name, src) in enumerate(anchors):
        row = 4 + i
        ws1.cell(row=row, column=16, value=name)                 # P
        qc = ws1.cell(row=row, column=17, value=0)               # Q 数值(待填,标黄)
        qc.fill = YELLOW; qc.border = BORDER
        ws1.cell(row=row, column=18, value=f"来源:{src}")          # R
    note = ws1.cell(row=26, column=1, value="【测算依据详细说明】")
    note.font = Font(bold=True)
    ws1["A27"] = "  ● 各平台单颗价值量 = 机架级材料成本 ÷ 每机架GPU数(NVIDIA 72 / ASIC 64)。黄色=有来源，白色=折算公式。"
    ws1["A28"] = "  ● 无直接来源的下一代芯片按上一代×溢价系数(溢价系数标黄并在批注注明为测算假设)。"

    # ---- Sheet2: 出货量汇总(万颗) ----
    ws2 = wb.create_sheet("出货量汇总(万颗)")
    title_row(ws2, "全球AI芯片出货量预测（万颗）", "★ 黄色底色 = 机构/用户提供的出货量数据")
    header_row(ws2, 4, ["芯片型号", "2025E", "2026E", "2027E", "2028E", "备注"])
    for r, g in [(5, "一、NVIDIA GPU"), (11, "二、ASIC定制芯片"),
                 (17, "三、AMD GPU"), (23, "四、国产AI芯片"), (27, "合计")]:
        group_row(ws2, r, g)

    # ---- Sheet3: 材料空间测算(亿美元) ----
    ws3 = wb.create_sheet("材料空间测算(亿美元)")
    title_row(ws3, "AI芯片各材料全球市场空间测算（亿美元）", LEGEND_SPACE)
    header_row(ws3, 4, ["材料环节", "2025E", "2026E", "2027E", "2028E", "25-28 CAGR"])
    materials = ["HBM内存", "PCB", "ABF基板", "MLCC", "电源", "液冷", "光纤连接",
                 "光模块★", "CCL铜箔", "CCL树脂", "CCL玻纤", "封装基板", "合计"]
    for i, m in enumerate(materials):
        ws3.cell(row=5 + i, column=1, value=m)
    ws3["A20"] = "【说明】所有数值均为公式 =∑(出货量×单颗价值量)÷10000，修改Sheet1/Sheet2自动联动；光模块★行引用'光模块市场空间测算'表(机柜口径)。"

    # ---- Sheet4: 分平台材料空间明细 ----
    ws4 = wb.create_sheet("分平台材料空间明细")
    title_row(ws4, "AI芯片分平台材料空间明细（亿美元）", LEGEND_SPACE)
    header_row(ws4, 4, ["芯片平台", "材料环节", "2025E", "2026E", "2027E", "2028E"])

    # ---- Sheet5: 材料利润空间测算 ----
    ws5 = wb.create_sheet("材料利润空间测算")
    title_row(ws5, "AI芯片各材料利润空间测算（亿美元）", LEGEND_PROFIT)
    group_row(ws5, 4, "一、芯片平台毛利率假设（可修改B列，下方利润自动联动）")
    header_row(ws5, 5, ["芯片平台", "毛利率", "口径说明", "数据来源", "报告期"])
    group_row(ws5, 16, "二、各材料利润空间明细（市场空间×毛利率=利润空间）")
    header_row(ws5, 17, ["材料环节", "芯片平台", "毛利率", "2025E空间", "2025E利润",
                         "2026E空间", "2026E利润", "2027E空间", "2027E利润",
                         "2028E空间", "2028E利润", "25-28利润合计", "利润占比"])

    # ---- Sheet6: 光模块市场空间测算 ----
    ws6 = wb.create_sheet("光模块市场空间测算")
    title_row(ws6, "AI光模块市场空间独立测算（亿美元）", LEGEND_OPTIC)
    ws6["A4"] = "一、AI机柜出货量假设（万个机柜） = 芯片出货量 ÷ 每机架GPU数"
    ws6["A4"].font = Font(bold=True)
    header_row(ws6, 5, ["平台", "2025E", "2026E", "2027E", "2028E", "GPU/rack", "光模块类型"])

    # ---- Sheet7: AI芯片市场空间测算 ----
    ws7 = wb.create_sheet("AI芯片市场空间测算")
    title_row(ws7, "AI芯片本体市场空间测算（亿美元）",
              "测算逻辑：∑ 出货量(万颗) × 单颗芯片均价($/颗) ÷ 10000 = 芯片市场空间(亿美元)")
    header_row(ws7, 4, ["芯片平台", "2025E", "2026E", "2027E", "2028E", "单颗均价($)", "来源"])

    # ---- Sheet8: Sources ----
    ws8 = wb.create_sheet("Sources")
    header_row(ws8, 1, ["编号", "来源标题", "来源详情", "数据范围", "获取日期"])
    ws8.cell(row=2, column=1, value=1)
    ws8.cell(row=2, column=2, value="（示例）用户Excel-全球显卡出货预测量")
    ws8.cell(row=2, column=3, value="各类GPU/ASIC出货量预测(万颗)")
    ws8.cell(row=2, column=4, value="2025-2028E")
    ws8.cell(row=2, column=5, value="YYYY-MM-DD")

    # 列宽
    for ws in wb.worksheets:
        ws.column_dimensions["A"].width = 26

    wb.save(path)
    print(f"✅ 已生成待填数据的模型骨架: {path}")
    print("   下一步: 填出货量&锚点(标黄+批注) → 单颗价值量/空间/利润写公式 → check_tam_format.py 校验")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python3 build_tam_model.py <输出xlsx路径>")
        sys.exit(1)
    build(sys.argv[1])
