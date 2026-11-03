#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
穿透叙事投资分析报告生成器（参数化通用版 v3.1.0）
依据 penetrate-narrative-stock-analysis skill 样式规范，同源双产出：
  - 详细版 DOCX（完整六步 + 全部表格 + 各表论证）
  - 简要版 HTML（核心结论速览：卡片式布局，供快速浏览）

【设计原则】样式与内容分离、DOCX 与 HTML 同源：
  - 本脚本只负责排版（封面、标题、正文、表格、引用框、免责声明），不含任何特定公司数据。
  - 报告内容由同一个 JSON 文件驱动，DOCX 与 HTML 均按 JSON 中的「块（block）」列表逐块渲染，
    保证两种格式内容一致、单一事实源；符合 report-spec.md「统一链路铁律」与「4.1 双产出」要求。
  - 任何标的（银之杰/中际旭创/…）都用同一脚本，仅替换 JSON 内容文件。

【用法】
    # 只出 DOCX
    python generate_report.py --content <content.json> --output <report.docx>
    # 同源双产出（推荐，对应「分析[公司名]」默认行为）：--html 不带值时自动取 output 同名 .html
    python generate_report.py --content <content.json> --output <report.docx> --html
    # 或显式指定 HTML 路径
    python generate_report.py --content <content.json> --output <report.docx> --html <report.html>

【content.json 结构】
{
  "meta": {
    "title": "银之杰 穿透叙事投资分析报告",        # 封面主标题
    "subtitle": "(300085.SZ) — 金融科技/参股金融牌照",  # 封面副标题
    "date": "2026年7月7日",                        # 封面日期
    "data_base_date": "2026年7月6日",              # 免责声明中的数据基准日（可选）
    "disclaimer_sources": "公司公告、定期报告、Alpha派调研/会议纪要及公开信息，经交叉验证"  # 可选，覆盖免责声明数据来源表述
  },
  "blocks": [
    {"type": "heading", "level": 1, "text": "摘要与核心结论"},
    {"type": "heading", "level": 2, "text": "核心结论一：…"},
    {"type": "body", "text": "正文段落（超200字自动按句号拆分多段）", "indent": true},
    {"type": "body", "text": "加粗强调段", "bold": true},
    {"type": "info_table", "rows": [["公司名称","银之杰(300085.SZ)"], ["当前市值","238亿元"]]},
    {"type": "data_table",
       "headers": ["券商","评级","目标价","隐含L(10%)","L/E3"],
       "rows": [["中金","跑赢","48元","35亿","2.5x"], ["…","…","…","…","…"]],
       "col_widths": [3,2,2,3,2]},               # col_widths 可选（单位cm）
    {"type": "argument", "text": "【表X·论证】本表服务于第一步反算…（≥500字/≥300字）"},
    {"type": "argument_points", "points": ["①要点一…","②要点二…"]},
    {"type": "quote", "text": "关键提示框内容", "style": "warn"},  # style: warn/neutral/info
    {"type": "note", "text": "表注：数据来源…"}
  ]
}

【说明】
  - blocks 的顺序即报告正文顺序；封面与免责声明由脚本自动生成，无需写入 blocks。
  - body/argument 超 200 汉字会自动按句号/分号/换行拆分为多段（每段≤8行）。
  - 表格建议 3 列及以上多主体对比时使用 data_table；两列键值信息用 info_table。
  - 若需在报告中体现来源标记，直接把 [source:N] 或落盘后的来源标记写进对应 text/单元格文本即可，脚本原样输出。
"""
import os
import re
import sys
import json
import argparse
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

# ============== 样式常量 ==============
COLOR_MAIN = RGBColor(0x1A, 0x1A, 0x1A)
COLOR_BRAND = RGBColor(0x1F, 0x3A, 0x5F)
COLOR_WHITE = RGBColor(0xFF, 0xFF, 0xFF)
COLOR_GRAY = RGBColor(0x59, 0x59, 0x59)
COLOR_RED = RGBColor(0xC0, 0x00, 0x00)
COLOR_GREEN = RGBColor(0x00, 0x70, 0x00)
COLOR_WARN_BG = "FDE8E8"
COLOR_NEUTRAL_BG = "E8EDF3"
COLOR_INFO_BG = "E8F5E9"
COLOR_HEADER_BG = "1F3A5F"

FONT_HEI = "黑体"
FONT_KAI = "楷体"

PARA_LIMIT = 200  # 每段汉字上限（~8行）

# ============== 辅助函数（通用排版，公司无关） ==============
def set_cell_bg(cell, color_hex):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:fill'), color_hex)
    shd.set(qn('w:val'), 'clear')
    tc_pr.append(shd)

def set_cell_font(cell, font_name=FONT_HEI, size=9.5, color=COLOR_MAIN, bold=False, align='left'):
    for p in cell.paragraphs:
        p.alignment = {'left': WD_ALIGN_PARAGRAPH.LEFT, 'center': WD_ALIGN_PARAGRAPH.CENTER, 'right': WD_ALIGN_PARAGRAPH.RIGHT}[align]
        p.paragraph_format.space_before = Pt(2)
        p.paragraph_format.space_after = Pt(2)
        for run in p.runs:
            run.font.name = font_name
            run.font.size = Pt(size)
            run.font.color.rgb = color
            run.bold = bold
            rPr = run._element.get_or_add_rPr()
            rFonts = rPr.find(qn('w:rFonts'))
            if rFonts is None:
                rFonts = OxmlElement('w:rFonts')
                rPr.append(rFonts)
            rFonts.set(qn('w:eastAsia'), font_name)
            rFonts.set(qn('w:ascii'), font_name)
            rFonts.set(qn('w:hAnsi'), font_name)

def add_data_table(doc, headers, rows, col_widths=None, header_bg=COLOR_HEADER_BG, header_color=COLOR_WHITE):
    table = doc.add_table(rows=1+len(rows), cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    for i, h in enumerate(headers):
        cell = table.rows[0].cells[i]
        cell.text = str(h)
        set_cell_bg(cell, header_bg)
        set_cell_font(cell, size=9.5, color=header_color, bold=True, align='center')
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
    for r_idx, row in enumerate(rows):
        for c_idx, val in enumerate(row):
            cell = table.rows[r_idx+1].cells[c_idx]
            cell.text = str(val)
            align = 'right' if c_idx > 0 and any(c.isdigit() for c in str(val)) else ('center' if c_idx == 0 else 'left')
            set_cell_font(cell, size=9.5, color=COLOR_MAIN, align=align)
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
    if col_widths:
        for i, w in enumerate(col_widths):
            for row in table.rows:
                row.cells[i].width = Cm(w)
    return table

def add_info_table(doc, rows, col_widths=None):
    table = doc.add_table(rows=len(rows), cols=2)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    for r_idx, kv in enumerate(rows):
        k, v = kv[0], kv[1]
        cell_k = table.rows[r_idx].cells[0]
        cell_k.text = str(k)
        set_cell_bg(cell_k, COLOR_NEUTRAL_BG)
        set_cell_font(cell_k, size=10, color=COLOR_BRAND, bold=True, align='left')
        cell_k.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        cell_v = table.rows[r_idx].cells[1]
        cell_v.text = str(v)
        set_cell_font(cell_v, size=10, color=COLOR_MAIN, align='left')
        cell_v.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
    if col_widths:
        for i, w in enumerate(col_widths):
            for row in table.rows:
                row.cells[i].width = Cm(w)
    return table

def add_quote_box(doc, text, quote_type='neutral'):
    bg_map = {'warn': COLOR_WARN_BG, 'neutral': COLOR_NEUTRAL_BG, 'info': COLOR_INFO_BG}
    color_map = {'warn': COLOR_RED, 'neutral': COLOR_BRAND, 'info': COLOR_GREEN}
    table = doc.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = table.rows[0].cells[0]
    cell.text = text
    set_cell_bg(cell, bg_map.get(quote_type, COLOR_NEUTRAL_BG))
    set_cell_font(cell, size=11, color=color_map.get(quote_type, COLOR_BRAND), bold=False, align='left')
    cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
    tcPr = cell._tc.get_or_add_tcPr()
    tcBorders = OxmlElement('w:tcBorders')
    for border_name in ['top', 'left', 'bottom', 'right']:
        border = OxmlElement(f'w:{border_name}')
        border.set(qn('w:val'), 'single')
        border.set(qn('w:sz'), '4')
        border.set(qn('w:color'), '1F3A5F')
        tcBorders.append(border)
    tcPr.append(tcBorders)
    doc.add_paragraph()
    return table

def add_heading(doc, text, level=1):
    sizes = {1: 18, 2: 14, 3: 12}
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(12 if level == 1 else 8)
    p.paragraph_format.space_after = Pt(6)
    run = p.add_run(text)
    run.font.name = FONT_HEI
    run.font.size = Pt(sizes.get(level, 12))
    run.font.color.rgb = COLOR_BRAND
    run.bold = True
    rPr = run._element.get_or_add_rPr()
    rFonts = OxmlElement('w:rFonts')
    rFonts.set(qn('w:eastAsia'), FONT_HEI)
    rFonts.set(qn('w:ascii'), FONT_HEI)
    rFonts.set(qn('w:hAnsi'), FONT_HEI)
    rPr.append(rFonts)
    return p

def _add_paragraph(doc, text, size=11, color=COLOR_MAIN, bold=False, align='left', indent=False):
    p = doc.add_paragraph()
    p.alignment = {'left': WD_ALIGN_PARAGRAPH.LEFT, 'center': WD_ALIGN_PARAGRAPH.CENTER, 'right': WD_ALIGN_PARAGRAPH.RIGHT, 'justify': WD_ALIGN_PARAGRAPH.JUSTIFY}[align]
    p.paragraph_format.space_before = Pt(3)
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.line_spacing = 1.5
    if indent:
        p.paragraph_format.first_line_indent = Pt(22)
    run = p.add_run(text)
    run.font.name = FONT_HEI
    run.font.size = Pt(size)
    run.font.color.rgb = color
    run.bold = bold
    rPr = run._element.get_or_add_rPr()
    rFonts = OxmlElement('w:rFonts')
    rFonts.set(qn('w:eastAsia'), FONT_HEI)
    rFonts.set(qn('w:ascii'), FONT_HEI)
    rFonts.set(qn('w:hAnsi'), FONT_HEI)
    rPr.append(rFonts)
    return p

def add_body(doc, text, size=11, color=COLOR_MAIN, bold=False, align='left', indent=False):
    """正文段落：超PARA_LIMIT字自动按句号/分号/换行拆分多段"""
    if len(text) <= PARA_LIMIT:
        _add_paragraph(doc, text, size, color, bold, align, indent)
        return
    parts = re.split(r'([。；！？\n])', text)
    sentences = []
    for i in range(0, len(parts)-1, 2):
        sentences.append(parts[i] + (parts[i+1] if i+1 < len(parts) else ''))
    if parts[-1].strip():
        sentences.append(parts[-1])
    current = ""
    for s in sentences:
        if not s.strip():
            continue
        if len(current) + len(s) <= PARA_LIMIT:
            current += s
        else:
            if current.strip():
                _add_paragraph(doc, current, size, color, bold, align, indent)
            current = s
    if current.strip():
        _add_paragraph(doc, current, size, color, bold, align, indent)

def add_argument(doc, text, size=11, color=COLOR_MAIN):
    """表格论证文字：与add_body相同，超长自动拆分，默认缩进"""
    add_body(doc, text, size=size, color=color, indent=True)

def add_argument_points(doc, points, size=11, color=COLOR_MAIN):
    for pt in points:
        add_body(doc, pt, size=size, color=color, indent=True)

def add_note(doc, text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(8)
    run = p.add_run(text)
    run.font.name = FONT_HEI
    run.font.size = Pt(8)
    run.font.color.rgb = COLOR_GRAY
    run.italic = True
    rPr = run._element.get_or_add_rPr()
    rFonts = OxmlElement('w:rFonts')
    rFonts.set(qn('w:eastAsia'), FONT_HEI)
    rPr.append(rFonts)
    return p

def add_cover(doc, title, subtitle, date_str):
    for _ in range(6):
        doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(title)
    run.font.name = FONT_HEI
    run.font.size = Pt(32)
    run.font.color.rgb = COLOR_BRAND
    run.bold = True
    rPr = run._element.get_or_add_rPr()
    rFonts = OxmlElement('w:rFonts')
    rFonts.set(qn('w:eastAsia'), FONT_HEI)
    rPr.append(rFonts)

    if subtitle:
        p2 = doc.add_paragraph()
        p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p2.paragraph_format.space_before = Pt(12)
        run2 = p2.add_run(subtitle)
        run2.font.name = FONT_HEI
        run2.font.size = Pt(20)
        run2.font.color.rgb = COLOR_GRAY
        rPr2 = run2._element.get_or_add_rPr()
        rFonts2 = OxmlElement('w:rFonts')
        rFonts2.set(qn('w:eastAsia'), FONT_HEI)
        rPr2.append(rFonts2)

    for _ in range(3):
        doc.add_paragraph()
    if date_str:
        p3 = doc.add_paragraph()
        p3.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run3 = p3.add_run(date_str)
        run3.font.name = FONT_HEI
        run3.font.size = Pt(14)
        run3.font.color.rgb = COLOR_GRAY
        rPr3 = run3._element.get_or_add_rPr()
        rFonts3 = OxmlElement('w:rFonts')
        rFonts3.set(qn('w:eastAsia'), FONT_HEI)
        rPr3.append(rFonts3)

    p4 = doc.add_paragraph()
    p4.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p4.paragraph_format.space_before = Pt(24)
    run4 = p4.add_run("基于穿透叙事股票分析框架 · DCF第一性原理")
    run4.font.name = FONT_KAI
    run4.font.size = Pt(12)
    run4.font.color.rgb = COLOR_BRAND
    run4.italic = True
    rPr4 = run4._element.get_or_add_rPr()
    rFonts4 = OxmlElement('w:rFonts')
    rFonts4.set(qn('w:eastAsia'), FONT_KAI)
    rPr4.append(rFonts4)

    doc.add_page_break()

def setup_page(doc):
    for section in doc.sections:
        section.page_width = Cm(21.59)
        section.page_height = Cm(27.94)
        section.left_margin = Cm(2.8)
        section.right_margin = Cm(2.8)
        section.top_margin = Cm(2.5)
        section.bottom_margin = Cm(2.5)

def add_disclaimer(doc, data_base_date=None, sources=None):
    doc.add_page_break()
    add_heading(doc, "免责声明", level=1)
    src = sources or "公司公告、定期报告、Alpha派调研/会议纪要及公开信息，经交叉验证"
    add_body(doc, f"本报告基于穿透叙事股票分析框架，依据DCF第一性原理与A股市场定价机制（空间叙事+拍卖机制）进行推演分析。所有数据来源于{src}。", size=10, color=COLOR_GRAY)
    add_body(doc, "本报告不构成任何投资建议。报告中的业绩空间测算、情景概率赋值、目标价推演均为基于公开信息的分析推演，不构成对未来股价的承诺。投资有风险，决策需谨慎。投资者应基于自身风险承受能力与独立判断做出投资决策。", size=10, color=COLOR_GRAY)
    if data_base_date:
        add_body(doc, f"数据基准日：{data_base_date}。当前股价、市值、一致预期等数据均以该日为基准，后续市场变化可能导致结论变化。", size=10, color=COLOR_GRAY)

# ============== 内容驱动：按 JSON block 渲染 ==============
def render_block(doc, block):
    t = block.get("type")
    if t == "heading":
        add_heading(doc, block["text"], level=int(block.get("level", 1)))
    elif t == "body":
        add_body(doc, block["text"], size=block.get("size", 11),
                 bold=block.get("bold", False), indent=block.get("indent", False))
    elif t == "info_table":
        add_info_table(doc, block["rows"], col_widths=block.get("col_widths"))
    elif t == "data_table":
        add_data_table(doc, block["headers"], block["rows"], col_widths=block.get("col_widths"))
    elif t == "argument":
        add_argument(doc, block["text"])
    elif t == "argument_points":
        add_argument_points(doc, block["points"])
    elif t == "quote":
        add_quote_box(doc, block["text"], quote_type=block.get("style", "neutral"))
    elif t == "note":
        add_note(doc, block["text"])
    else:
        raise ValueError(f"未知 block 类型: {t!r}（支持: heading/body/info_table/data_table/argument/argument_points/quote/note）")

def generate_docx(content, output_path):
    meta = content.get("meta", {})
    blocks = content.get("blocks", [])
    doc = Document()
    setup_page(doc)
    style = doc.styles['Normal']
    style.font.name = FONT_HEI
    style.font.size = Pt(11)
    rFonts = style.element.rPr.rFonts
    rFonts.set(qn('w:eastAsia'), FONT_HEI)

    add_cover(doc, meta.get("title", "穿透叙事投资分析报告"),
              meta.get("subtitle", ""), meta.get("date", ""))
    for i, block in enumerate(blocks):
        try:
            render_block(doc, block)
        except Exception as e:
            raise RuntimeError(f"渲染第 {i} 个 block 失败: {e}") from e
    add_disclaimer(doc, data_base_date=meta.get("data_base_date"),
                   sources=meta.get("disclaimer_sources"))

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    doc.save(output_path)
    return output_path

# ============== 内容驱动：简要版 HTML（与 DOCX 同源 content JSON） ==============
# 设计：复用与 DOCX 一致的品牌色（#1F3A5F）与涨红跌绿，卡片式布局；
# HTML 为「简要版」，默认只渲染 meta 及 blocks 中的核心块（heading/body/data_table/quote/note），
# argument/argument_points（逐表长论证）属于详细版专属内容，默认不进简要版（可用 include_arguments=True 开启）。

HTML_STYLE = """
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: "Microsoft YaHei", "PingFang SC", sans-serif; background: #f5f7fa; color: #1a1a1a; line-height: 1.7; }
  .container { max-width: 900px; margin: 0 auto; padding: 24px 20px; }
  .header { background: linear-gradient(135deg, #1F3A5F, #2c5282); color: #fff; padding: 36px 28px; border-radius: 12px; margin-bottom: 24px; }
  .header h1 { font-size: 26px; margin-bottom: 8px; }
  .header .subtitle { font-size: 15px; opacity: 0.9; }
  .header .date { font-size: 13px; opacity: 0.7; margin-top: 8px; }
  .card { background: #fff; border-radius: 10px; padding: 24px 28px; margin-bottom: 18px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
  .card h2 { color: #1F3A5F; font-size: 18px; border-left: 4px solid #1F3A5F; padding-left: 12px; margin-bottom: 14px; }
  .card h3 { color: #1F3A5F; font-size: 15px; margin: 14px 0 8px; }
  .card p { font-size: 14px; margin-bottom: 8px; text-align: justify; }
  .warn-box { background: #FDE8E8; border-left: 4px solid #C00000; padding: 14px 18px; border-radius: 6px; margin: 12px 0; }
  .warn-box p { color: #C00000; font-size: 14px; font-weight: 500; margin: 0; }
  .neutral-box { background: #E8EDF3; border-left: 4px solid #1F3A5F; padding: 14px 18px; border-radius: 6px; margin: 12px 0; }
  .neutral-box p { color: #1F3A5F; font-size: 14px; margin: 0; }
  .info-box { background: #E8F5E9; border-left: 4px solid #007000; padding: 14px 18px; border-radius: 6px; margin: 12px 0; }
  .info-box p { color: #007000; font-size: 14px; margin: 0; }
  table { width: 100%; border-collapse: collapse; margin: 12px 0; font-size: 13px; }
  th { background: #1F3A5F; color: #fff; padding: 8px 10px; text-align: center; font-weight: 600; }
  td { padding: 7px 10px; border-bottom: 1px solid #e8e8e8; text-align: center; }
  tr:nth-child(even) td { background: #f9fafc; }
  .info-table td:first-child { background: #E8EDF3; color: #1F3A5F; font-weight: 600; text-align: left; width: 34%; }
  .info-table td:last-child { text-align: left; }
  .highlight-red { color: #C00000; font-weight: 600; }
  .highlight-green { color: #007000; font-weight: 600; }
  .note { color: #999; font-size: 12px; font-style: italic; margin: 6px 0 12px; }
  .footer { text-align: center; color: #999; font-size: 12px; padding: 20px 0; }
"""


def _html_escape(text):
    return (str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _html_cell(val):
    """数值单元格：带“-/跌/下修”标绿、带“+/涨/上修”标红（遵循 A 股惯例）。"""
    s = _html_escape(val)
    low = s
    if any(k in low for k in ["-", "跌", "下修", "低估", "回避", "减仓"]):
        return f'<span class="highlight-green">{s}</span>'
    if any(k in low for k in ["+", "涨", "上修", "高估"]):
        return f'<span class="highlight-red">{s}</span>'
    return s


def render_html_block(block, include_arguments=False):
    """将一个内容 block 渲染为简要版 HTML 片段。与 render_block（DOCX）同源。"""
    t = block.get("type")
    if t == "heading":
        level = int(block.get("level", 1))
        text = _html_escape(block["text"])
        if level <= 1:
            # 一级标题开启一张新卡片（前一张卡片由调用处闭合）
            return f'</div>\n  <div class="card">\n    <h2>{text}</h2>'
        return f'    <h3>{text}</h3>'
    if t == "body":
        text = _html_escape(block["text"])
        if block.get("bold"):
            return f'    <p><strong>{text}</strong></p>'
        return f'    <p>{text}</p>'
    if t == "info_table":
        rows = block["rows"]
        trs = "".join(f'<tr><td>{_html_escape(r[0])}</td><td>{_html_escape(r[1])}</td></tr>' for r in rows)
        return f'    <table class="info-table">{trs}</table>'
    if t == "data_table":
        headers = block["headers"]
        rows = block["rows"]
        th = "".join(f'<th>{_html_escape(h)}</th>' for h in headers)
        trs = ""
        for r in rows:
            tds = "".join(f'<td>{_html_cell(v)}</td>' for v in r)
            trs += f'<tr>{tds}</tr>'
        return f'    <table><tr>{th}</tr>{trs}</table>'
    if t == "quote":
        style = block.get("style", "neutral")
        cls = {"warn": "warn-box", "neutral": "neutral-box", "info": "info-box"}.get(style, "neutral-box")
        return f'    <div class="{cls}"><p>{_html_escape(block["text"])}</p></div>'
    if t == "note":
        return f'    <div class="note">{_html_escape(block["text"])}</div>'
    if t in ("argument", "argument_points"):
        if not include_arguments:
            return ""  # 简要版默认不渲染逐表长论证
        if t == "argument":
            return f'    <p>{_html_escape(block["text"])}</p>'
        return "".join(f'    <p>{_html_escape(p)}</p>' for p in block["points"])
    # 未知类型在简要版中静默跳过（DOCX 会报错，保证详细版不漏）
    return ""


def generate_html(content, output_path, include_arguments=False):
    """生成简要版 HTML，与 generate_docx 共用同一份 content JSON。"""
    meta = content.get("meta", {})
    blocks = content.get("blocks", [])
    title = _html_escape(meta.get("title", "穿透叙事投资分析报告"))
    subtitle = _html_escape(meta.get("subtitle", ""))
    date_str = _html_escape(meta.get("data_base_date") or meta.get("date", ""))

    parts = []
    parts.append('<!DOCTYPE html>')
    parts.append('<html lang="zh-CN">')
    parts.append('<head>')
    parts.append('<meta charset="UTF-8">')
    parts.append('<meta name="viewport" content="width=device-width, initial-scale=1.0">')
    parts.append(f'<title>{title}（简要版）</title>')
    parts.append(f'<style>{HTML_STYLE}</style>')
    parts.append('</head>')
    parts.append('<body>')
    parts.append('<div class="container">')
    parts.append('  <div class="header">')
    parts.append(f'    <h1>{title}（简要版）</h1>')
    if subtitle:
        parts.append(f'    <div class="subtitle">{subtitle}</div>')
    if date_str:
        parts.append(f'    <div class="date">数据基准日：{date_str}</div>')
    parts.append('  </div>')
    # 首张卡片开头（render_html_block 遇到一级标题会先 </div> 再开新卡片，因此这里先开一个占位卡片）
    parts.append('  <div class="card">')
    first_heading_seen = False
    for block in blocks:
        if block.get("type") == "heading" and int(block.get("level", 1)) <= 1:
            if not first_heading_seen:
                # 用首个一级标题替换占位卡片的空 h2，避免空卡片
                parts.append(f'    <h2>{_html_escape(block["text"])}</h2>')
                first_heading_seen = True
                continue
        frag = render_html_block(block, include_arguments=include_arguments)
        if frag:
            parts.append(frag)
    parts.append('  </div>')  # 闭合最后一张卡片
    parts.append('  <div class="footer">')
    parts.append('    <p>基于穿透叙事股票分析框架 · DCF第一性原理 | 不构成投资建议</p>')
    if date_str:
        parts.append(f'    <p>数据基准日：{date_str}</p>')
    parts.append('  </div>')
    parts.append('</div>')
    parts.append('</body>')
    parts.append('</html>')
    html = "\n".join(parts)

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    return output_path


def main():
    ap = argparse.ArgumentParser(description="穿透叙事投资分析报告生成器（参数化通用版，同源双产出）")
    ap.add_argument("--content", required=True, help="报告内容 JSON 文件路径")
    ap.add_argument("--output", required=True, help="输出 DOCX 文件路径")
    ap.add_argument("--html", nargs="?", const="__AUTO__", default=None,
                    help="同时输出简要版 HTML；不带值时自动取 --output 同名 .html，或显式指定路径")
    ap.add_argument("--html-with-arguments", action="store_true",
                    help="简要版 HTML 中一并渲染逐表长论证（默认不渲染）")
    args = ap.parse_args()

    with open(args.content, "r", encoding="utf-8") as f:
        content = json.load(f)
    n_blocks = len(content.get("blocks", []))

    path = generate_docx(content, args.output)
    print(f"[OK] DOCX 详细版已生成: {path}（共 {n_blocks} 个内容块）")

    if args.html is not None:
        if args.html == "__AUTO__":
            base, _ = os.path.splitext(args.output)
            html_path = base + ".html"
        else:
            html_path = args.html
        hpath = generate_html(content, html_path, include_arguments=args.html_with_arguments)
        print(f"[OK] HTML 简要版已生成: {hpath}")

if __name__ == "__main__":
    main()
