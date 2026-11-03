#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
穿透叙事 Excel DCF 工作簿生成器

基于 skills/.../assets/dcf_template.xlsx 版式（上传样例：
中际旭创_穿透叙事_DCF模板.xlsx 三表结构），按公司参数填入可调假设、
现价隐含 L 三档、券商目标价隐含 L、敏感性 L→市值。

模型与 dcf_implied.py 完全一致：
  前3年用 E1/E2/E3；第4年至稳态年从 E3 等比至 L；之后 g=0 永续；
  r 默认 8/10/12%。

用法:
  # 仅生成/刷新空白模板到 assets（无公司数据）
  python build_dcf_workbook.py init-template \\
      --out ../assets/dcf_template.xlsx

  # 按 JSON 参数生成交付簿（报告后强制附件）
  python build_dcf_workbook.py build \\
      --input params.json \\
      --out /path/to/{公司}_穿透叙事_DCF模板.xlsx

  # 命令行最小参数（无券商表也可）
  python build_dcf_workbook.py build \\
      --company "某某股份" --code 000001.SZ \\
      --cap 1000 --price 20 --shares 50 \\
      --e0 40 --e1 45 --e2 50 --e3 55 \\
      --base-year 2025 --steady-year 2035 \\
      --asof 2026-08-10 \\
      --out ./out.xlsx

params.json 示例见同目录旁注释 / references/dcf-workbook.md
"""
from __future__ import annotations

import argparse
import json
import sys
from copy import copy
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.workbook.workbook import Workbook as WBType

# 同目录导入 dcf_implied
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from dcf_implied import (  # noqa: E402
    DEFAULT_BASE_YEAR,
    DEFAULT_STEADY_YEAR,
    R_GRID,
    fair_value,
    get_growth_years,
    implied_ceiling,
    implied_growth_rate,
)

# ---------------------------------------------------------------------------
# 样式（对齐上传样例）
# ---------------------------------------------------------------------------
HEADER_FILL = PatternFill("solid", fgColor="194F90")
HEADER_FONT = Font(bold=True, color="FFFFFF", name="微软雅黑", size=11)
TITLE_FONT = Font(bold=True, name="微软雅黑", size=14, color="194F90")
SUB_FONT = Font(name="微软雅黑", size=9, color="666666")
LABEL_FONT = Font(name="微软雅黑", size=10)
INPUT_FILL = PatternFill("solid", fgColor="FFF8E1")  # 黄：可改
INPUT_FONT = Font(name="微软雅黑", size=10, color="194F90")
RESULT_FILL = PatternFill("solid", fgColor="E8EDF2")  # 灰绿：关键结果
SECTION_FONT = Font(bold=True, name="微软雅黑", size=11, color="194F90")
THIN = Border(
    left=Side(style="thin", color="D0D0D0"),
    right=Side(style="thin", color="D0D0D0"),
    top=Side(style="thin", color="D0D0D0"),
    bottom=Side(style="thin", color="D0D0D0"),
)
FMT_NUM = "#,##0.00"
FMT_PCT = "0.00%"
FMT_X = "0.00"

# 敏感性默认 L/E3 倍数网格（与 dcf_implied sensitivity 对齐的常用读数点 + 现价 L）
DEFAULT_SENS_RATIOS = [0.3, 0.5, 0.8, 1.0, 1.194, 1.5, 2.0, 3.0, 5.0]


def _set_col_widths(ws, widths: Dict[str, float]) -> None:
    for col, w in widths.items():
        ws.column_dimensions[col].width = w


def _style_header_row(ws, row: int, cols: int) -> None:
    for c in range(1, cols + 1):
        cell = ws.cell(row=row, column=c)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = THIN


def _input_cell(cell, value, number_format: Optional[str] = None) -> None:
    cell.value = value
    cell.fill = INPUT_FILL
    cell.font = INPUT_FONT
    cell.border = THIN
    if number_format:
        cell.number_format = number_format


def _formula_cell(cell, formula: str, number_format: Optional[str] = None, result: bool = False) -> None:
    cell.value = formula
    cell.font = LABEL_FONT
    cell.border = THIN
    if result:
        cell.fill = RESULT_FILL
    if number_format:
        cell.number_format = number_format


def _label(cell, text: str, bold: bool = False) -> None:
    cell.value = text
    cell.font = SECTION_FONT if bold else LABEL_FONT
    cell.border = THIN


# ---------------------------------------------------------------------------
# 核心：构建三表工作簿
# ---------------------------------------------------------------------------
def build_workbook(
    *,
    company: str,
    code: str,
    cap: float,
    price: float,
    shares: float,
    e0: float,
    e1: float,
    e2: float,
    e3: float,
    base_year: int = DEFAULT_BASE_YEAR,
    steady_year: int = DEFAULT_STEADY_YEAR,
    r_mid: float = 0.10,
    asof: str = "",
    e_notes: Optional[Dict[str, str]] = None,
    shares_note: str = "总股本",
    price_note: str = "收盘价",
    brokers: Optional[List[Dict[str, Any]]] = None,
    sens_ratios: Optional[Sequence[float]] = None,
    blank: bool = False,
) -> WBType:
    """生成与上传样例同构的三表簿。blank=True 时写入占位/空输入。"""
    e_notes = e_notes or {}
    brokers = brokers or []
    gy = get_growth_years(base_year, steady_year)

    if blank:
        company = company or "{公司名}"
        code = code or "{code}"
        cap = cap if cap else 0.0
        price = price if price else 0.0
        shares = shares if shares else 1.0
        e0 = e0 if e0 else 0.0
        e1 = e1 if e1 else 0.0
        e2 = e2 if e2 else 0.0
        e3 = e3 if e3 else 0.0

    # 现价隐含 L 三档（脚本固化数值，供对照；Assumptions 正算用公式）
    implied_rows: List[Tuple[int, float, float, float, float]] = []
    for r in R_GRID:
        if cap > 0 and e3 > 0:
            L = implied_ceiling(cap, e1, e2, e3, r, gy)
            le3 = L / e3 if e3 else float("nan")
            le0 = L / e0 if e0 else float("nan")
            g = implied_growth_rate(L, e3, gy) / 100.0  # 存小数
        else:
            L = le3 = le0 = g = None  # type: ignore
        implied_rows.append((r, L, le3, le0, g))  # type: ignore

    L10 = implied_rows[1][1] if implied_rows[1][1] is not None else 0.0
    # 默认假设终局 L = r=10% 现价隐含 L
    L_assume = L10 if L10 else (e3 if e3 else 0.0)

    wb = Workbook()

    # ========== Sheet 1: Assumptions ==========
    ws = wb.active
    ws.title = "Assumptions"
    _set_col_widths(ws, {"A": 38.5, "B": 14.1, "C": 8.9, "D": 20.9, "E": 11.0})
    ws.freeze_panes = "A5"
    ws.merge_cells("A1:D1")
    ws.merge_cells("A2:D2")

    title = f"{company}（{code}）穿透叙事 DCF 可调假设" if not blank else "穿透叙事 DCF 可调假设（填写黄色输入格）"
    ws["A1"] = title
    ws["A1"].font = TITLE_FONT
    ws["A2"] = (
        "黄色可改；灰底为公式/关键结果。前3年用一致预期，第4年至稳态年从E3等比至L，之后g=0。"
        "现价隐含L三档为脚本固化对照。不构成投资建议。"
    )
    ws["A2"].font = SUB_FONT

    headers = ["输入假设", "数值", "单位", "说明"]
    for i, h in enumerate(headers, 1):
        ws.cell(row=4, column=i, value=h)
    _style_header_row(ws, 4, 4)

    # 行映射：固定地址供跨表引用
    # B5市值 B6股本 B7股价 B8E0 B9E1 B10E2 B11E3 B12基准年 B13稳态年 B14 r B15 假设L
    rows_in = [
        (5, "当前市值", cap, "亿元", asof or "行情时点", FMT_NUM),
        (6, "总股本", shares, "亿股", shares_note, FMT_NUM),
        (7, "当前股价", price, "元", price_note, FMT_NUM),
        (8, f"E0_{base_year}归母", e0, "亿元", e_notes.get("e0", "已披露/TTM口径见说明"), FMT_NUM),
        (9, f"E1_{base_year + 1}E归母", e1, "亿元", e_notes.get("e1", "一致预期"), FMT_NUM),
        (10, f"E2_{base_year + 2}E归母", e2, "亿元", e_notes.get("e2", "一致预期"), FMT_NUM),
        (11, f"E3_{base_year + 3}E归母", e3, "亿元", e_notes.get("e3", "一致预期"), FMT_NUM),
        (12, "基准年", base_year, "年", "E0对应年", "0"),
        (13, "稳态年", steady_year, "年", "终局L起点年", "0"),
        (14, "折现率r", r_mid, "", "默认中枢10%", FMT_PCT),
        (15, "假设终局L", L_assume, "亿元", "可改做正算；默认=现价隐含L@10%", FMT_NUM),
    ]
    for r, lab, val, unit, note, fmt in rows_in:
        _label(ws.cell(row=r, column=1), lab)
        _input_cell(ws.cell(row=r, column=2), val if not blank or r >= 12 else (val if val else None), fmt)
        ws.cell(row=r, column=3).value = unit
        ws.cell(row=r, column=3).font = LABEL_FONT
        ws.cell(row=r, column=4).value = note
        ws.cell(row=r, column=4).font = LABEL_FONT

    # 派生公式区
    ws["A17"] = "派生（公式）"
    ws["A17"].font = SECTION_FONT

    deriv = [
        (18, "增长年数N", "=B13-(B12+3)", "年", "稳态年-(基准年+3)", None, False),
        (19, "隐含g(E3→L)", '=IF(OR(B11<=0,B15<=0),"",(B15/B11)^(1/B18)-1)', "", "过渡期复合增速", FMT_PCT, False),
        (20, "r小数", "=B14", "", "与B14同一小数", FMT_PCT, False),
        (21, "前3年PV", "=B9/(1+B20)+B10/(1+B20)^2+B11/(1+B20)^3", "", "E1~E3折现", FMT_NUM, False),
        (
            22,
            "过渡期PV",
            '=IF(OR(B18<1,B11<=0),"",IF(ABS(B15-B11)<0.000000001,'
            'SUMPRODUCT(B11/(1+B20)^ROW(INDIRECT("4:"&TEXT(3+B18,"0")))),'
            'SUMPRODUCT((B11*(1+B19)^(ROW(INDIRECT("4:"&TEXT(3+B18,"0")))-3))'
            '/(1+B20)^ROW(INDIRECT("4:"&TEXT(3+B18,"0"))))))',
            "",
            "第4至3+N年",
            FMT_NUM,
            False,
        ),
        (23, "永续PV", '=(B15/B20)/(1+B20)^(3+B18)', "", "L/r 折回", FMT_NUM, False),
        (24, "模型市值合计", "=B21+B22+B23", "亿元", "正算市值", FMT_NUM, True),
        (25, "对应股价", "=IF(B6=0,\"\",B24/B6)", "元", "模型市值/股本", FMT_NUM, True),
        (26, "动态PE(市值/E1)", '=IF(B9=0,"",B24/B9)', "x", "", FMT_X, False),
        (27, "L/E3", '=IF(B11=0,"",B15/B11)', "x", "", FMT_X, False),
        (28, "L/E0", '=IF(B8=0,"",B15/B8)', "x", "", FMT_X, False),
    ]
    for r, lab, formula, unit, note, fmt, is_res in deriv:
        _label(ws.cell(row=r, column=1), lab)
        _formula_cell(ws.cell(row=r, column=2), formula, fmt, result=is_res)
        ws.cell(row=r, column=3).value = unit
        ws.cell(row=r, column=3).font = LABEL_FONT
        ws.cell(row=r, column=4).value = note
        ws.cell(row=r, column=4).font = LABEL_FONT

    # 现价隐含 L 三档（固化数值）
    ws["A30"] = "现价隐含L三档（脚本固化，供对照）"
    ws["A30"].font = SECTION_FONT
    for i, h in enumerate(["折现率", "隐含L(亿)", "L/E3", "L/E0", "过渡期g"], 1):
        ws.cell(row=31, column=i, value=h)
    _style_header_row(ws, 31, 5)

    for i, (r_pct, L, le3, le0, g) in enumerate(implied_rows):
        row = 32 + i
        ws.cell(row=row, column=1, value=f"{r_pct}%").font = LABEL_FONT
        cL = ws.cell(row=row, column=2, value=None if L is None else round(L, 1))
        cL.number_format = FMT_NUM
        cL.font = LABEL_FONT
        cL.border = THIN
        c3 = ws.cell(row=row, column=3, value=None if le3 is None or le3 != le3 else round(le3, 2))
        c3.number_format = FMT_X
        c3.border = THIN
        c0 = ws.cell(row=row, column=4, value=None if le0 is None or le0 != le0 else round(le0, 2))
        c0.number_format = FMT_X
        c0.border = THIN
        cg = ws.cell(row=row, column=5, value=None if g is None or g != g else g)
        cg.number_format = FMT_PCT
        cg.border = THIN

    ws["A36"] = (
        f"模型备注：增长年数N={gy if not blank else '稳态年-(基准年+3)'}；"
        "与 scripts/dcf_implied.py 一致。改黄色输入后，派生区与跨表市值公式自动重算；"
        "隐含L三档与券商L列需重跑本脚本刷新。"
    )
    ws["A36"].font = SUB_FONT
    ws.merge_cells("A36:E36")

    # ========== Sheet 2: 券商目标价隐含L ==========
    ws2 = wb.create_sheet("券商目标价隐含L")
    _set_col_widths(
        ws2,
        {
            "A": 21.1,
            "B": 12.1,
            "C": 8.9,
            "D": 13.1,
            "E": 16.0,
            "F": 11.0,
            "G": 11.0,
            "H": 11.0,
            "I": 11.0,
            "J": 14.0,
        },
    )
    ws2.freeze_panes = "A5"
    ws2.merge_cells("A1:J1")
    ws2.merge_cells("A2:J2")
    ws2["A1"] = "券商目标价 → 统一DCF隐含终局利润L"
    ws2["A1"].font = TITLE_FONT
    e_txt = f"E1/E2/E3={e1}/{e2}/{e3}" if not blank else "E1/E2/E3=见Assumptions"
    sh_txt = f"股本{shares}亿" if not blank else "股本见Assumptions"
    ws2["A2"] = (
        f"口径：{e_txt}；{sh_txt}；稳态{steady_year}；r=8/10/12%。"
        "市值=目标价×Assumptions!$B$6；相对现价L@10%=该行G列/Assumptions!$B$33。"
        "不构成投资建议。"
    )
    ws2["A2"].font = SUB_FONT

    h2 = [
        "机构/场景",
        "日期",
        "评级",
        "目标价(元)",
        "市值(亿)=价×股本",
        "r=8% L",
        "r=10% L",
        "r=12% L",
        "L/E3@10%",
        "相对现价L@10%",
    ]
    for i, h in enumerate(h2, 1):
        ws2.cell(row=4, column=i, value=h)
    _style_header_row(ws2, 4, 10)

    # 第5行：现价
    rows_b: List[Dict[str, Any]] = [
        {
            "name": f"现价{asof.replace('-', '') if asof else ''}" or "现价",
            "date": asof or "",
            "rating": "-",
            "price": price,
            "is_spot": True,
        }
    ]
    for b in brokers:
        rows_b.append(
            {
                "name": b.get("name") or b.get("broker") or "",
                "date": b.get("date") or "",
                "rating": b.get("rating") or "",
                "price": float(b.get("price") or b.get("target") or 0),
                "source": b.get("source") or b.get("note") or "",
                "is_spot": False,
            }
        )

    # 空白模板预留 12 行可填
    if blank and len(rows_b) == 1:
        for i in range(12):
            rows_b.append(
                {
                    "name": "",
                    "date": "",
                    "rating": "",
                    "price": None,
                    "is_spot": False,
                }
            )

    for idx, rb in enumerate(rows_b):
        row = 5 + idx
        ws2.cell(row=row, column=1, value=rb["name"]).font = LABEL_FONT
        ws2.cell(row=row, column=2, value=rb["date"]).font = LABEL_FONT
        ws2.cell(row=row, column=3, value=rb["rating"]).font = LABEL_FONT

        px = rb["price"]
        c_px = ws2.cell(row=row, column=4, value=px if px not in (None, "") else None)
        c_px.number_format = FMT_NUM
        c_px.font = INPUT_FONT
        c_px.fill = INPUT_FILL
        c_px.border = THIN

        # 市值公式
        _formula_cell(ws2.cell(row=row, column=5), f"=IF(D{row}=\"\",\"\",D{row}*Assumptions!$B$6)", FMT_NUM)

        # 隐含 L：有价格则脚本写入固化值；空行留空供手改后重跑
        if px not in (None, "") and float(px) > 0 and e3 > 0 and shares > 0:
            cap_i = float(px) * shares
            L8 = implied_ceiling(cap_i, e1, e2, e3, 8, gy)
            L10i = implied_ceiling(cap_i, e1, e2, e3, 10, gy)
            L12 = implied_ceiling(cap_i, e1, e2, e3, 12, gy)
            ratio = L10i / e3 if e3 else None
        else:
            L8 = L10i = L12 = ratio = None

        for col, val, fmt in (
            (6, None if L8 is None else round(L8, 1), FMT_NUM),
            (7, None if L10i is None else round(L10i, 1), FMT_NUM),
            (8, None if L12 is None else round(L12, 1), FMT_NUM),
            (9, None if ratio is None else round(ratio, 2), FMT_X),
        ):
            cell = ws2.cell(row=row, column=col, value=val)
            cell.number_format = fmt
            cell.font = LABEL_FONT
            cell.border = THIN

        # 相对现价 L@10% —— 引用 Assumptions!B33，禁止写死常数
        _formula_cell(
            ws2.cell(row=row, column=10),
            f'=IF(OR(G{row}="",Assumptions!$B$33=""),"",G{row}/Assumptions!$B$33)',
            FMT_X,
        )

        src = rb.get("source")
        if src:
            ws2.cell(row=row, column=4).comment = Comment(str(src)[:500], "penetrate-narrative")

    # ========== Sheet 3: 敏感性_L到市值 ==========
    ws3 = wb.create_sheet("敏感性_L到市值")
    _set_col_widths(ws3, {"A": 14.3, "B": 15.4, "C": 17.6, "D": 13.1})
    ws3.freeze_panes = "A5"
    ws3.merge_cells("A1:D1")
    ws3.merge_cells("A2:D2")
    ws3["A1"] = "不同终局利润L → 市值映射（r=中枢，E1-E3固定）"
    ws3["A1"].font = TITLE_FONT
    ws3["A2"] = (
        "用途：读数对照。L 与市值由 dcf_implied 正算；B列 L/E3 为公式。"
        "不构成投资建议。"
    )
    ws3["A2"].font = SUB_FONT

    for i, h in enumerate(["终局L(亿元)", "L/E3", "对应市值(亿元)", "动态PE(E1)"], 1):
        ws3.cell(row=4, column=i, value=h)
    _style_header_row(ws3, 4, 4)

    if sens_ratios is not None:
        L_list = list(sens_ratios)
    elif e3 and e3 > 0:
        # 使用倍数网格，并确保包含现价隐含 L@10%
        L_list = [round(e3 * ratio, 1) for ratio in DEFAULT_SENS_RATIOS]
        if L10 and L10 > 0:
            # 替换最接近 1.194 的点为真实 L10
            L_list = [round(e3 * r, 1) for r in [0.3, 0.5, 0.8, 1.0, 1.5, 2.0, 3.0, 5.0]]
            # 插入 L10 并排序去重
            L_list.append(round(L10, 1))
            L_list = sorted(set(L_list))
    else:
        L_list = [None] * 9  # 空白行

    r_sens = r_mid * 100 if r_mid <= 1 else r_mid
    for i, Lv in enumerate(L_list):
        row = 5 + i
        if Lv is not None and e3 > 0 and e1 > 0:
            fv = fair_value(float(Lv), e1, e2, e3, r_sens, gy)
            pe = fv / e1 if e1 else None
            ws3.cell(row=row, column=1, value=round(float(Lv), 1)).number_format = FMT_NUM
            ws3.cell(row=row, column=1).font = INPUT_FONT
            ws3.cell(row=row, column=1).fill = INPUT_FILL
            ws3.cell(row=row, column=1).border = THIN
            _formula_cell(ws3.cell(row=row, column=2), f"=A{row}/Assumptions!$B$11", FMT_X)
            c_fv = ws3.cell(row=row, column=3, value=round(fv, 1))
            c_fv.number_format = FMT_NUM
            c_fv.border = THIN
            c_pe = ws3.cell(row=row, column=4, value=None if pe is None else round(pe, 1))
            c_pe.number_format = FMT_X
            c_pe.border = THIN
        else:
            for c in range(1, 5):
                cell = ws3.cell(row=row, column=c, value=None)
                cell.border = THIN
                if c == 1:
                    cell.fill = INPUT_FILL
                if c == 2:
                    _formula_cell(cell, f'=IF(A{row}="","",A{row}/Assumptions!$B$11)', FMT_X)

    note_row = 5 + max(len(L_list), 1) + 1
    ws3.merge_cells(start_row=note_row, start_column=1, end_row=note_row, end_column=4)
    if e1 and L10:
        ws3.cell(
            row=note_row,
            column=1,
            value=(
                f"说明：动态PE=市值/E1（E1={e1}）。"
                f"现价市值约{cap}亿对应L≈{round(L10, 1) if L10 else '—'}亿"
                f"（L/E3≈{round(L10 / e3, 2) if L10 and e3 else '—'}）。"
                f"敏感性正算折现率={r_sens:.0f}%。"
            ),
        ).font = SUB_FONT
    else:
        ws3.cell(
            row=note_row,
            column=1,
            value="说明：填写 Assumptions 黄格并重跑 build_dcf_workbook.py 可刷新本表固化市值。",
        ).font = SUB_FONT

    return wb


def init_blank_template(out_path: Path) -> Path:
    """生成无公司数据的标准空白模板。"""
    wb = build_workbook(
        company="{公司名}",
        code="{code}",
        cap=0,
        price=0,
        shares=1,
        e0=0,
        e1=0,
        e2=0,
        e3=0,
        base_year=DEFAULT_BASE_YEAR,
        steady_year=DEFAULT_STEADY_YEAR,
        r_mid=0.10,
        asof="",
        blank=True,
    )
    # 空白模板标题通用化
    ws = wb["Assumptions"]
    ws["A1"] = "穿透叙事 DCF 可调假设（空白模板）"
    ws["B5"] = None
    ws["B6"] = None
    ws["B7"] = None
    ws["B8"] = None
    ws["B9"] = None
    ws["B10"] = None
    ws["B11"] = None
    ws["B15"] = None
    for r in range(32, 35):
        for c in range(2, 6):
            wb["Assumptions"].cell(row=r, column=c).value = None
    # 券商表现价行也清空
    ws2 = wb["券商目标价隐含L"]
    ws2["A5"] = "现价"
    for col in range(2, 5):
        ws2.cell(row=5, column=col).value = None if col != 3 else "-"
    ws2["D5"] = None
    for c in range(6, 10):
        ws2.cell(row=5, column=c).value = None

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out_path)
    return out_path


def build_from_params(params: Dict[str, Any], out_path: Path) -> Path:
    brokers = params.get("brokers") or params.get("targets") or []
    wb = build_workbook(
        company=params["company"],
        code=params.get("code") or params.get("ticker") or "",
        cap=float(params["cap"]),
        price=float(params["price"]),
        shares=float(params["shares"]),
        e0=float(params.get("e0") or 0),
        e1=float(params["e1"]),
        e2=float(params["e2"]),
        e3=float(params["e3"]),
        base_year=int(params.get("base_year") or DEFAULT_BASE_YEAR),
        steady_year=int(params.get("steady_year") or DEFAULT_STEADY_YEAR),
        r_mid=float(params.get("r") or params.get("r_mid") or 0.10),
        asof=str(params.get("asof") or params.get("date") or ""),
        e_notes=params.get("e_notes") or {},
        shares_note=params.get("shares_note") or "总股本",
        price_note=params.get("price_note") or "收盘价",
        brokers=brokers,
        sens_ratios=params.get("sens_levels"),
        blank=False,
    )
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out_path)
    return out_path


def _parse_build_cli(args: argparse.Namespace) -> Dict[str, Any]:
    if args.input:
        with open(args.input, "r", encoding="utf-8") as f:
            params = json.load(f)
        return params
    missing = [k for k in ("company", "cap", "price", "shares", "e1", "e2", "e3") if getattr(args, k, None) is None]
    if missing:
        raise SystemExit(f"build 缺少参数: {missing}（或改用 --input params.json）")
    params: Dict[str, Any] = {
        "company": args.company,
        "code": args.code or "",
        "cap": args.cap,
        "price": args.price,
        "shares": args.shares,
        "e0": args.e0 or 0,
        "e1": args.e1,
        "e2": args.e2,
        "e3": args.e3,
        "base_year": args.base_year,
        "steady_year": args.steady_year,
        "r": args.r,
        "asof": args.asof or "",
        "shares_note": args.shares_note or "总股本",
    }
    if args.brokers_json:
        with open(args.brokers_json, "r", encoding="utf-8") as f:
            params["brokers"] = json.load(f)
    return params


def main() -> None:
    parser = argparse.ArgumentParser(description="穿透叙事 Excel DCF 工作簿生成器")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p0 = sub.add_parser("init-template", help="生成空白模板 xlsx 到 assets")
    p0.add_argument(
        "--out",
        type=str,
        default=str(_SCRIPT_DIR.parent / "assets" / "dcf_template.xlsx"),
        help="输出路径",
    )

    p1 = sub.add_parser("build", help="按公司参数生成交付 DCF 工作簿")
    p1.add_argument("--input", type=str, default=None, help="params.json 路径")
    p1.add_argument("--out", type=str, required=True, help="输出 xlsx 路径")
    p1.add_argument("--company", type=str, default=None)
    p1.add_argument("--code", type=str, default=None)
    p1.add_argument("--cap", type=float, default=None, help="市值亿元")
    p1.add_argument("--price", type=float, default=None, help="股价元")
    p1.add_argument("--shares", type=float, default=None, help="股本亿股")
    p1.add_argument("--e0", type=float, default=None)
    p1.add_argument("--e1", type=float, default=None)
    p1.add_argument("--e2", type=float, default=None)
    p1.add_argument("--e3", type=float, default=None)
    p1.add_argument("--base-year", type=int, default=DEFAULT_BASE_YEAR)
    p1.add_argument("--steady-year", type=int, default=DEFAULT_STEADY_YEAR)
    p1.add_argument("--r", type=float, default=0.10, help="中枢折现率小数，默认0.10")
    p1.add_argument("--asof", type=str, default="")
    p1.add_argument("--shares-note", type=str, default="总股本")
    p1.add_argument("--brokers-json", type=str, default=None, help="券商列表 JSON 文件")

    args = parser.parse_args()
    if args.cmd == "init-template":
        path = init_blank_template(Path(args.out))
        print(f"[ok] blank template -> {path}")
    elif args.cmd == "build":
        params = _parse_build_cli(args)
        path = build_from_params(params, Path(args.out))
        print(f"[ok] workbook -> {path}")
        # 简要回显 r=10% 隐含 L
        gy = get_growth_years(
            int(params.get("base_year") or DEFAULT_BASE_YEAR),
            int(params.get("steady_year") or DEFAULT_STEADY_YEAR),
        )
        L10 = implied_ceiling(float(params["cap"]), float(params["e1"]), float(params["e2"]), float(params["e3"]), 10, gy)
        print(f"     spot implied L@10% = {L10:.1f} 亿; brokers={len(params.get('brokers') or params.get('targets') or [])}")
    else:
        parser.error("unknown cmd")


if __name__ == "__main__":
    main()
