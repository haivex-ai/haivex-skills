#!/usr/bin/env python3
"""检查AI材料测算工作簿的展示与来源规范。

测算硬编码为保守启发式检查：识别标准测算表的年度/结果列，及以公式
为主的行列。黄色原始输入、米黄假设参数不作为硬编码测算结果报告。
本工具不重算Excel公式，也不判断经济假设或结果数值是否合理。
"""
import re
import sys
from collections import Counter
from numbers import Real

import openpyxl

YELLOW = "FFFF00"
CREAM = "FFF8E1"
SPEC_COLORS = {YELLOW, CREAM, "194F90", "D6E4F0", "DCE6F1", "FFFFFF"}
SOURCE_HEADERS = ["编号", "来源标题", "来源详情", "数据范围", "获取日期"]
SRC_RE = re.compile(r"\[来源[:：]\s*(\d+(?:\s*[,，]\s*\d+)*)\s*\]")


def _norm(rgb):
    if not isinstance(rgb, str):
        return None
    s = rgb.upper()
    return s[2:] if len(s) == 8 else s


def fg(cell):
    if cell.fill and cell.fill.patternType:
        return _norm(cell.fill.fgColor.rgb)
    return None


def _formula(cell):
    return cell.data_type == "f" or (
        isinstance(cell.value, str) and cell.value.startswith("=")
    )


def _number(value):
    return isinstance(value, Real) and not isinstance(value, bool)


def _source_ids(text):
    result = set()
    for match in SRC_RE.finditer(text):
        result.update(int(n.strip()) for n in re.split("[,，]", match.group(1)))
    return result


def _output_header(value):
    if not isinstance(value, str):
        return False
    text = value.strip()
    return bool(
        re.fullmatch(r"(?:19|20)\d{2}(?:[EeFf])?(?:空间|利润)?", text)
        or "CAGR" in text.upper()
        or text in {"利润占比", "25-28利润合计", "市场空间", "材料空间", "利润空间"}
    )


def _under_output_header(ws, cell):
    for row in range(cell.row - 1, 2, -1):
        value = ws.cell(row, cell.column).value
        if isinstance(value, str) and not value.startswith("="):
            return _output_header(value)
    return False


def check(path):
    wb = openpyxl.load_workbook(path, data_only=False)
    issues, oks = [], []
    try:
        src_sheet = next((wb[n] for n in wb.sheetnames
                          if n.lower() == "sources" or "来源" in n), None)
        declared_ids = set()
        if src_sheet is None:
            issues.append("[严重] 未找到 Sources 来源表")
        else:
            hdr = [src_sheet.cell(1, c).value for c in range(1, 6)]
            normalized = [h.strip() if isinstance(h, str) else h for h in hdr]
            if normalized != SOURCE_HEADERS:
                issues.append(f"[问题] Sources 表头应为{SOURCE_HEADERS}，实际{hdr}")
            else:
                oks.append("Sources 表头五列名称和顺序正确")
            for row in src_sheet.iter_rows(min_row=2, max_col=5):
                values = [c.value for c in row]
                if all(v is None for v in values):
                    continue
                value = values[0]
                valid = (not isinstance(value, bool) and (
                    isinstance(value, int) or
                    (isinstance(value, str) and value.strip().isdigit())
                ))
                if not valid or int(value) <= 0:
                    issues.append(f"[问题] Sources!A{row[0].row} 来源编号须为正整数")
                    continue
                source_id = int(value)
                if source_id in declared_ids:
                    issues.append(f"[问题] Sources 来源编号重复: {source_id}")
                declared_ids.add(source_id)

        for ws in wb.worksheets:
            if ws is src_sheet:
                continue
            a1, a2 = ws["A1"].value, ws["A2"].value
            if not a1:
                issues.append(f"[问题] Sheet「{ws.title}」缺 A1 标题行")
            if not a2:
                issues.append(f"[问题] Sheet「{ws.title}」缺 A2 图例/逻辑说明行")
            if a1 and a2:
                oks.append(f"Sheet「{ws.title}」标题+图例齐全")

            cells = [c for row in ws.iter_rows() for c in row if c.value is not None]
            eligible = [c for c in cells if c.row > 2 and fg(c) not in {YELLOW, CREAM}
                        and (_formula(c) or _number(c.value))]
            row_formula = Counter(c.row for c in eligible if _formula(c))
            col_formula = Counter(c.column for c in eligible if _formula(c))
            row_total = Counter(c.row for c in eligible)
            col_total = Counter(c.column for c in eligible)
            calc_sheet = any(word in ws.title for word in ("空间测算", "空间明细", "利润空间"))
            yellow_total = yellow_valid = 0
            bad_colors = set()
            suspects = []
            for c in cells:
                color = fg(c)
                if color and color not in SPEC_COLORS:
                    bad_colors.add(color)
                if color == YELLOW:
                    yellow_total += 1
                    ids = _source_ids(c.comment.text if c.comment else "")
                    if not ids:
                        issues.append(f"[问题] {ws.title}!{c.coordinate} 黄色格缺少有效来源批注")
                    elif ids - declared_ids:
                        issues.append(f"[问题] {ws.title}!{c.coordinate} 批注引用未登记来源编号: {sorted(ids-declared_ids)}")
                    elif _formula(c):
                        issues.append(f"[问题] {ws.title}!{c.coordinate} 黄色来源格为公式，应按测算值配色")
                    else:
                        yellow_valid += 1
                if c.row <= 2 or not _number(c.value) or color in {YELLOW, CREAM}:
                    continue
                formula_row = row_formula[c.row] >= 2 and row_formula[c.row] * 2 > row_total[c.row]
                formula_col = col_formula[c.column] >= 2 and col_formula[c.column] * 2 > col_total[c.column]
                if formula_row or formula_col or (calc_sheet and _under_output_header(ws, c)):
                    suspects.append(c.coordinate)
            if yellow_total and yellow_valid == yellow_total:
                oks.append(f"Sheet「{ws.title}」黄色来源批注全部有效 {yellow_valid}/{yellow_total}")
            if bad_colors:
                issues.append(f"[提示] Sheet「{ws.title}」存在非规范配色: {sorted(bad_colors)}")
            if suspects:
                issues.append(f"[问题] Sheet「{ws.title}」疑似硬编码测算值（应核对公式）: {', '.join(suspects)}")
            if "价值量" in ws.title or "假设" in ws.title:
                if any(isinstance(c.value, str) and "测算依据" in c.value for c in cells):
                    oks.append(f"Sheet「{ws.title}」含【测算依据】文字说明")
                else:
                    issues.append(f"[建议] Sheet「{ws.title}」缺【测算依据详细说明】文字区")
    finally:
        wb.close()

    print("=" * 60)
    print(f"AI 材料测算规范体检: {path}")
    print("=" * 60)
    print(f"\n✅ 通过项 ({len(oks)}):")
    for item in oks:
        print("   ✓", item)
    print(f"\n⚠️  待整改 ({len(issues)}):")
    if not issues:
        print("   （无）全部符合本工具已实现的展示检查")
    for item in issues:
        print("   •", item)
    return issues


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("用法: python3 check_tam_format.py <xlsx路径>")
        sys.exit(2)
    sys.exit(1 if check(sys.argv[1]) else 0)
