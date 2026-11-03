#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
景气度看板 Excel 生成器
-------------------------------------------------
读取 prosperity_engine.py 输出的结果 JSON, 生成 4 个 Sheet 的景气度看板:
  Sheet1 景气评分总表 (行业 x 维度评分 + 综合分 + 趋势 + 历史分位)
  Sheet2 指标明细       (每行业的高频/中频指标最新值/上期/环比/同比/更新日)
  Sheet3 数据验证       (V1-V5 逐项结论)
  Sheet4 结论Challenge  (C1-C5 风险清单)

用法: python build_dashboard.py <result.json> <config.json> <out.xlsx>
依赖: openpyxl (在 shell 环境执行, tool_code 无法 import)
"""
import json
import sys
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

# 样式
HEADER_FILL = PatternFill("solid", fgColor="1F4E78")
HEADER_FONT = Font(color="FFFFFF", bold=True, size=11)
TITLE_FONT = Font(bold=True, size=13, color="1F4E78")
UP_FILL = PatternFill("solid", fgColor="C6EFCE")     # 绿: 上行
DOWN_FILL = PatternFill("solid", fgColor="FFC7CE")   # 红: 下行
MID_FILL = PatternFill("solid", fgColor="FFEB9C")    # 黄: 分化
WARN_FILL = PatternFill("solid", fgColor="FFD9CC")   # 浅红: 警示
THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
LEFT = Alignment(horizontal="left", vertical="center", wrap_text=True)

DIM_LABELS = [
    ("price", "价格动能"),
    ("volume", "量(产销/开工)"),
    ("inventory", "库存"),
    ("profit", "盈利/价差"),
    ("valuation_quantile", "历史分位"),
]


def _style_header(ws, row, ncol):
    for c in range(1, ncol + 1):
        cell = ws.cell(row=row, column=c)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = CENTER
        cell.border = BORDER


def _trend_fill(trend):
    return {"↑": UP_FILL, "↓": DOWN_FILL, "–": MID_FILL}.get(trend)


def build_sheet1(wb, data):
    ws = wb.active
    ws.title = "景气评分总表"
    ws["A1"] = "全行业景气度评分总表  (截至 %s)" % data.get("as_of", "")
    ws["A1"].font = TITLE_FONT
    headers = ["板块", "行业", "趋势", "扩散指数", "综合景气分"] + [lbl for _, lbl in DIM_LABELS] + ["有效指标数"]
    ws.append([])
    ws.append(headers)
    hrow = 3
    _style_header(ws, hrow, len(headers))
    for r in data.get("results", []):
        ds = r.get("dimension_scores", {})
        row = [r.get("board"), r.get("name"), r.get("trend"), r.get("diffusion_ratio"),
               r.get("composite_score")] + [ds.get(k) for k, _ in DIM_LABELS] + [r.get("n_valid_indicators")]
        ws.append(row)
        rr = ws.max_row
        for c in range(1, len(headers) + 1):
            ws.cell(row=rr, column=c).border = BORDER
            ws.cell(row=rr, column=c).alignment = CENTER
        tf = _trend_fill(r.get("trend"))
        if tf:
            ws.cell(row=rr, column=3).fill = tf
    widths = [10, 14, 6, 10, 11, 11, 14, 9, 11, 10, 10]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[chr(64 + i)].width = w
    ws.freeze_panes = "A4"
    # 说明
    note_row = ws.max_row + 2
    ws.cell(row=note_row, column=1, value="说明: 趋势按扩散指数(环比上行指标占比)判定, >60%↑ / <40%↓ / 其余分化; 综合分=各维度加权(价25/量25/库15/盈15/分位20).").font = Font(italic=True, size=9, color="808080")


def build_sheet2(wb, data, config):
    ws = wb.create_sheet("指标明细")
    ws["A1"] = "各行业景气指标明细"
    ws["A1"].font = TITLE_FONT
    headers = ["行业", "指标名称", "维度", "频率", "方向", "最新值", "上期值", "环比%", "同比%", "单位", "更新日"]
    ws.append([])
    ws.append(headers)
    _style_header(ws, 3, len(headers))
    cfg_map = {i["name"]: i for i in config.get("industries", [])}
    for r in data.get("results", []):
        name = r.get("name")
        cfg = cfg_map.get(name, {})
        for ind in cfg.get("indicators", []):
            latest = ind.get("latest")
            prev = ind.get("prev")
            mom = None
            if latest is not None and prev not in (None, 0):
                mom = round((latest - prev) / abs(prev) * 100, 2)
            yoy = ind.get("yoy")
            yoy_pct = round(yoy * 100, 2) if yoy is not None else None
            ws.append([name, ind.get("name"), ind.get("dim"), ind.get("freq"),
                       ind.get("direction"), latest, prev, mom, yoy_pct,
                       ind.get("unit"), ind.get("update")])
            rr = ws.max_row
            for c in range(1, len(headers) + 1):
                ws.cell(row=rr, column=c).border = BORDER
                ws.cell(row=rr, column=c).alignment = CENTER
    widths = [14, 24, 16, 7, 7, 11, 11, 9, 9, 10, 12]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[chr(64 + i)].width = w
    ws.freeze_panes = "A4"


def build_sheet3(wb, data):
    ws = wb.create_sheet("数据验证")
    ws["A1"] = "数据验证记录 (V1口径 / V2季节性 / V3量价库存 / V4宏观锚 / V5多源)"
    ws["A1"].font = TITLE_FONT
    headers = ["行业", "校验项", "结论", "明细"]
    ws.append([])
    ws.append(headers)
    _style_header(ws, 3, len(headers))
    for r in data.get("results", []):
        for v in r.get("validation", []):
            ws.append([r.get("name"), v.get("check"), v.get("result"), v.get("detail")])
            rr = ws.max_row
            for c in range(1, 5):
                ws.cell(row=rr, column=c).border = BORDER
                ws.cell(row=rr, column=c).alignment = LEFT if c == 4 else CENTER
            if v.get("result") in ("存疑", "警示"):
                ws.cell(row=rr, column=3).fill = WARN_FILL
    for col, w in zip("ABCD", [14, 16, 8, 70]):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = "A4"


def build_sheet4(wb, data):
    ws = wb.create_sheet("结论Challenge")
    ws["A1"] = "结论 Challenge 风险清单 (C1拐点真伪 / C2传导时滞 / C3单指标 / C4周期位置 / C5需求透支)"
    ws["A1"].font = TITLE_FONT
    headers = ["行业", "类型", "风险提示"]
    ws.append([])
    ws.append(headers)
    _style_header(ws, 3, len(headers))
    for r in data.get("results", []):
        for ch in r.get("challenges", []):
            ws.append([r.get("name"), ch.get("type"), ch.get("risk")])
            rr = ws.max_row
            for c in range(1, 4):
                ws.cell(row=rr, column=c).border = BORDER
                ws.cell(row=rr, column=c).alignment = LEFT if c == 3 else CENTER
            ws.cell(row=rr, column=3).fill = WARN_FILL
    for col, w in zip("ABC", [14, 16, 80]):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = "A4"


def main():
    if len(sys.argv) < 4:
        print("usage: python build_dashboard.py <result.json> <config.json> <out.xlsx>")
        sys.exit(1)
    data = json.load(open(sys.argv[1], "r", encoding="utf-8"))
    config = json.load(open(sys.argv[2], "r", encoding="utf-8"))
    wb = Workbook()
    build_sheet1(wb, data)
    build_sheet2(wb, data, config)
    build_sheet3(wb, data)
    build_sheet4(wb, data)
    wb.save(sys.argv[3])
    print("dashboard saved ->", sys.argv[3])


if __name__ == "__main__":
    main()
