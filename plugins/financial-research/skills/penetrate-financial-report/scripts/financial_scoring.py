"""
全A样本财务打分与分位数定位

【为什么是两段式（Agent 取数 + 脚本算分）】
  skill 内的 Python 脚本运行在无网络、无平台工具访问权限的沙箱里，无法自行调用平台数据接口。
  因此取数由 Agent 侧完成（见 references/scoring-model-guide.md 的业务取数清单），
  脚本只负责纯计算——保证结果可复现、可离线运行。

【触发场景】
  仅当用户【显性要求】"全A横向对比 / 分位数定位 / 在全市场处于什么水平"时才使用本脚本，
  不进入穿透财报的默认报告流程。

======================================================================
输入文件规格（由 Agent 用平台工具取数后落地）
======================================================================
1) --sample  全A样本横截面 CSV（某一报告期，剔除银行/非银金融后约 5400 只）
   必需列（列名可含同义词，脚本做模糊匹配）：
     报告期, 报告类型, 股票代码, 公司简称, 报告期末在市状态,
     申万一级行业, 行业版本, 行业生效期, 币种, 金额单位, 值主体, 数据版本, 有效期,
     营业收入, 营业成本,
     应收账款, 应收款项融资, 合同资产, 预付款项,
     应付账款及票据, 合同负债,
     固定资产, 无形资产,
     总资产,
     经营活动产生的现金流量净额,
     ROE(净资产收益率)
   说明：同一计算的分子分母必须使用同一金额单位；历史样本的在市状态与行业分类均按报告期 as-of 口径获取。
   上述口径列必须逐行有值；财务科目缺失保留为空并触发覆盖率检查，不补 0。

2) --consensus  目标公司一致预期 vs 实际净利润对比 CSV（可选，用于指标5）
   必需列：
     股票代码, 公司简称, 预测快照日, 预测财年（如 2024/2025）,
     一致预期净利润, 实际归母净利润, 币种, 金额单位, 值主体, 数据版本, 有效期
   （若某财年尚无实际值，实际列留空即可，脚本自动跳过该行的偏差计算。）
   币种、金额单位、值主体、数据版本和有效期必须逐行有值。

3) --company  目标公司简称（必填），必须与 --sample 中"公司简称"列的取值一致。

======================================================================
输出（JSON）
======================================================================
  - 公司基本信息（代码/行业）
  - 五大指标：原始值 + 全A分位数 + 打分解读
  - 全A样本各指标中位数（作为对照锚）
  - 一致预期偏差（指标5，若提供 consensus）
  - 异常信号（背离检测：应收周转率↓+毛利率↑ 等）

用法:
    python financial_scoring.py --company "贵州茅台" \
        --sample "全A样本_2024年报.csv" \
        --consensus "贵州茅台_一致预期对比.csv" \
        --output "贵州茅台_全A分位.json"
"""

import argparse
import csv
import hashlib
import json
import math
import os
import sys
from datetime import datetime

QUALITY_COVERAGE_THRESHOLD = 0.8

# ============================================================
# 列名模糊匹配：把 CSV 实际列名映射到脚本内部标准键
# ============================================================
COLUMN_ALIASES = {
    "报告期": ["报告期", "报告截止日", "财务报告期", "report_period"],
    "报告类型": ["报告类型", "报表类型", "report_type"],
    "股票代码": ["股票代码", "代码", "证券代码", "sec_code", "code"],
    "公司简称": ["公司简称", "简称", "证券简称", "股票名称", "name", "stock_name"],
    "报告期末在市状态": [
        "报告期末在市状态",
        "报告期在市状态",
        "在市状态",
        "listing_status_as_of",
    ],
    "申万一级行业": [
        "申万一级行业",
        "一级行业",
        "申万行业",
        "行业",
        "sw_industry",
        "industry",
    ],
    "行业版本": ["行业版本", "申万行业版本", "industry_version"],
    "行业生效期": ["行业生效期", "行业有效期", "industry_validity"],
    "币种": ["币种", "货币", "currency"],
    "金额单位": ["金额单位", "单位", "amount_unit"],
    "值主体": ["值主体", "主体口径", "value_subject"],
    "数据版本": ["数据版本", "版本", "data_version"],
    "有效期": ["有效期", "数据有效期", "validity"],
    "营业收入": ["营业收入", "营收", "revenue", "oper_rev"],
    "营业成本": ["营业成本", "oper_cost", "cost"],
    "应收账款": ["应收账款", "应收账款净额", "应收账款(净额)", "ar"],
    "应收款项融资": ["应收款项融资", "应收票据及应收款项融资", "rec_financing"],
    "合同资产": ["合同资产", "contract_asset"],
    "预付款项": ["预付款项", "预付账款", "prepay"],
    "应付账款及票据": [
        "应付账款及票据",
        "应付票据及应付账款",
        "应付账款和票据",
        "应付款项",
        "ap",
    ],
    "合同负债": ["合同负债", "contract_liab"],
    "固定资产": ["固定资产", "固定资产净额", "fixed_assets"],
    "无形资产": ["无形资产", "无形资产净额", "intangible_assets"],
    "总资产": ["总资产", "资产总计", "期末总资产", "total_assets"],
    "经营活动产生的现金流量净额": [
        "经营活动产生的现金流量净额",
        "经营性现金流量净额",
        "经营现金流净额",
        "经营活动现金流量净额",
        "ocf",
        "cfo",
    ],
    "ROE": ["roe", "净资产收益率", "加权平均净资产收益率", "指数净资产收益率"],
    "预测快照日": ["预测快照日", "一致预期快照日", "预测日期", "snapshot_date"],
    "预测财年": ["预测财年", "财年", "预测年度", "forecast_year"],
    "一致预期净利润": ["一致预期净利润", "一致预期", "预期净利润", "预测净利润"],
    "实际归母净利润": ["实际归母净利润", "实际净利润", "归母净利润"],
}


def build_col_map(header):
    """把 CSV 表头映射到标准键。返回 {标准键: 实际列索引}。"""
    col_map = {}
    low_header = [str(h).strip().lower() for h in header]
    for std_key, aliases in COLUMN_ALIASES.items():
        found = None
        # 精确匹配优先
        for alias in aliases:
            for i, h in enumerate(low_header):
                if h == alias.lower():
                    found = i
                    break
            if found is not None:
                break
        # 退化为包含匹配
        if found is None:
            for alias in aliases:
                for i, h in enumerate(low_header):
                    if alias.lower() in h:
                        found = i
                        break
                if found is not None:
                    break
        if found is not None:
            col_map[std_key] = found
    return col_map


def file_sha256(path):
    """计算输入文件校验值，便于复现与审计。"""
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def unique_values(rows, key):
    """按首次出现顺序提取非空唯一值。"""
    values = []
    seen = set()
    for row in rows:
        value = str(row.get(key) or "").strip()
        if value and value not in seen:
            seen.add(value)
            values.append(value)
    return values


def require_nonempty_values(rows, fields, source_label):
    """校验必填口径字段不只是有列，而且每一行都有实际值。"""
    missing = {}
    for field in fields:
        indexes = [
            index + 1
            for index, row in enumerate(rows)
            if not str(row.get(field) or "").strip()
        ]
        if indexes:
            missing[field] = indexes[:10]
    if missing:
        raise ValueError(
            f"输入校验未通过： {source_label} 的必填口径字段存在空值，"
            f"字段及前10个数据行号: {missing}"
        )


# ============================================================
# 数值解析
# ============================================================
def safe_float(val):
    if val is None:
        return None
    if isinstance(val, (int, float)):
        if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
            return None
        return float(val)
    s = str(val).strip().replace(",", "")
    if s in (
        "",
        "#N/A",
        "#REF!",
        "#DIV/0!",
        "#VALUE!",
        "#NAME?",
        "None",
        "nan",
        "NaN",
        "null",
        "-",
        "--",
    ):
        return None
    if s.endswith("%"):
        try:
            return float(s[:-1]) / 100.0
        except (ValueError, TypeError):
            return None
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


# ============================================================
# 读取全A样本 CSV
# ============================================================
def load_sample(sample_path):
    """读取全A样本横截面 CSV，返回 (rows, col_map, metadata)。
    rows: list of dict（标准键 -> 值）。
    """
    if not os.path.exists(sample_path):
        raise FileNotFoundError(f"输入校验未通过： 全A样本文件不存在: {sample_path}")
    with open(sample_path, "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if header is None:
            raise ValueError("数据质量未通过： 全A样本 CSV 为空")
        col_map = build_col_map(header)
        required = [
            "报告期",
            "报告类型",
            "股票代码",
            "公司简称",
            "报告期末在市状态",
            "申万一级行业",
            "行业版本",
            "行业生效期",
            "币种",
            "金额单位",
            "值主体",
            "数据版本",
            "有效期",
            "营业收入",
            "营业成本",
            "应收账款",
            "应收款项融资",
            "合同资产",
            "预付款项",
            "应付账款及票据",
            "合同负债",
            "固定资产",
            "无形资产",
            "总资产",
            "经营活动产生的现金流量净额",
            "ROE",
        ]
        missing = [k for k in required if k not in col_map]
        if missing:
            raise ValueError(
                f"输入校验未通过： 全A样本 CSV 缺少关键列: {missing}。实际表头: {header}。"
                f"请确认 Agent 取数时按 scoring-model-guide.md 的字段清单落地。"
            )
        rows = []
        for raw in reader:
            if not raw:
                continue
            rec = {}
            for std_key, idx in col_map.items():
                rec[std_key] = raw[idx] if idx < len(raw) else None
            rows.append(rec)
    if not rows:
        raise ValueError("数据质量未通过： 全A样本 CSV 没有数据行")

    required_metadata_fields = [
        "报告期",
        "报告类型",
        "报告期末在市状态",
        "申万一级行业",
        "行业版本",
        "行业生效期",
        "币种",
        "金额单位",
        "值主体",
        "数据版本",
        "有效期",
    ]
    require_nonempty_values(rows, required_metadata_fields, "全A样本 CSV")

    report_periods = unique_values(rows, "报告期")
    if len(report_periods) != 1:
        raise ValueError(
            "输入校验未通过： 全A样本必须且只能包含一个报告期，"
            f"实际为: {report_periods or ['空值']}"
        )
    try:
        datetime.strptime(report_periods[0], "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(
            "输入校验未通过： 全A样本报告期必须为绝对日期 YYYY-MM-DD，"
            f"实际为: {report_periods[0]}"
        ) from exc

    report_types = unique_values(rows, "报告类型")
    if len(report_types) != 1:
        raise ValueError(
            "输入校验未通过： 同一横截面只能使用一种报告类型，"
            f"实际为: {report_types}"
        )

    excluded_financial_industries = {"银行", "非银金融"}
    included_excluded_industries = sorted(
        {
            str(row.get("申万一级行业") or "").strip()
            for row in rows
            if str(row.get("申万一级行业") or "").strip()
            in excluded_financial_industries
        }
    )
    if included_excluded_industries:
        raise ValueError(
            "输入校验未通过： 全A样本必须剔除银行与非银金融，"
            f"实际仍包含: {included_excluded_industries}"
        )

    security_keys = set()
    duplicate_keys = set()
    for row in rows:
        code = str(row.get("股票代码") or "").strip()
        name = str(row.get("公司简称") or "").strip()
        if not code:
            raise ValueError("输入校验未通过： 全A样本存在空股票代码")
        if not name:
            raise ValueError(
                f"输入校验未通过： 全A样本中证券{code}的公司简称为空，不能静默缩小分位样本"
            )
        key = (code, str(row.get("报告期") or "").strip())
        if key in security_keys:
            duplicate_keys.add(key)
        security_keys.add(key)
    if duplicate_keys:
        raise ValueError(
            "输入校验未通过： 全A样本必须按证券×报告期保持唯一，"
            f"发现重复键: {sorted(duplicate_keys)[:10]}"
        )

    metadata_fields = [
        "报告期",
        "报告类型",
        "报告期末在市状态",
        "行业版本",
        "行业生效期",
        "币种",
        "金额单位",
        "值主体",
        "数据版本",
        "有效期",
    ]
    metadata = {
        "文件路径": os.path.abspath(sample_path),
        "SHA-256": file_sha256(sample_path),
        "数据粒度": "证券×报告期",
        "记录数": len(rows),
        "口径字段": {key: unique_values(rows, key) for key in metadata_fields},
    }
    return rows, col_map, metadata


# ============================================================
# 五大指标计算
# ============================================================
def compute_metric_series(rows):
    """对全A样本每只股票计算五大指标的原始值（指标1-4）。
    返回 dict: {指标名: {代码或简称: 值}} 及每只股票的明细。
    """
    per_stock = []  # list of dict
    for r in rows:
        name = str(r.get("公司简称") or "").strip()
        if not name:
            continue
        rev = safe_float(r.get("营业收入"))
        cost = safe_float(r.get("营业成本"))
        ar = safe_float(r.get("应收账款"))
        recfin = safe_float(r.get("应收款项融资"))
        ca = safe_float(r.get("合同资产"))
        prepay = safe_float(r.get("预付款项"))
        ap = safe_float(r.get("应付账款及票据"))
        cl = safe_float(r.get("合同负债"))
        fa = safe_float(r.get("固定资产"))
        ia = safe_float(r.get("无形资产"))
        ta = safe_float(r.get("总资产"))
        ocf = safe_float(r.get("经营活动产生的现金流量净额"))
        roe = safe_float(r.get("ROE"))

        # 指标1：应收款项周转率(对数) = ln(营收 / (应收账款+应收款项融资+合同资产))
        recv_components = (ar, recfin, ca)
        recv_base = (
            sum(recv_components) if all(v is not None for v in recv_components) else None
        )
        m1_turnover = None
        m1_log = None
        if rev is not None and recv_base is not None and recv_base > 0:
            m1_turnover = rev / recv_base
            if m1_turnover > 0:
                m1_log = math.log(m1_turnover)

        # 毛利率
        gross_margin = None
        if rev not in (None, 0) and cost is not None:
            gross_margin = (rev - cost) / rev

        # 指标2：(固定资产+无形资产)周转率(对数)
        prod_asset_components = (fa, ia)
        prod_asset = (
            sum(prod_asset_components)
            if all(v is not None for v in prod_asset_components)
            else None
        )
        m2_turnover = None
        m2_log = None
        if rev is not None and prod_asset is not None and prod_asset > 0:
            m2_turnover = rev / prod_asset
            if m2_turnover > 0:
                m2_log = math.log(m2_turnover)

        # 指标3：营运净资产(不含存货)/总资产
        # 营运净资产 = 应收账款+应收款项融资+合同资产+预付款项 - 应付账款及票据 - 合同负债
        m3 = None
        working_net_components = (ar, recfin, ca, prepay, ap, cl)
        if ta not in (None, 0) and all(
            v is not None for v in working_net_components
        ):
            working_net = (ar + recfin + ca + prepay) - ap - cl
            m3 = working_net / ta

        # 指标4：经营性现金流/总资产
        m4 = None
        if ta not in (None, 0) and ocf is not None:
            m4 = ocf / ta

        per_stock.append(
            {
                "公司简称": name,
                "股票代码": str(r.get("股票代码") or "").strip(),
                "申万一级行业": str(r.get("申万一级行业") or "").strip(),
                "指标1_应收周转率对数": m1_log,
                "指标1_应收周转率": m1_turnover,
                "毛利率": gross_margin,
                "指标2_生产资产周转率对数": m2_log,
                "指标2_生产资产周转率": m2_turnover,
                "指标3_营运净资本占比": m3,
                "指标4_经营现金流总资产比": m4,
                "ROE": roe,
            }
        )
    return per_stock


def percentile_of(value, all_values):
    """计算 value 在 all_values（已剔除 None）中的分位数（0-100）。
    分位数 = 严格小于 value 的样本数 / 有效样本数 * 100。
    """
    valid = [v for v in all_values if v is not None]
    if not valid or value is None:
        return None
    below = sum(1 for v in valid if v < value)
    return round(below / len(valid) * 100, 1)


def median_of(all_values):
    valid = sorted(v for v in all_values if v is not None)
    if not valid:
        return None
    n = len(valid)
    mid = n // 2
    if n % 2 == 1:
        return valid[mid]
    return (valid[mid - 1] + valid[mid]) / 2.0


# ============================================================
# 一致预期偏差（指标5）
# ============================================================
def load_consensus(consensus_path, expected_company=None, expected_code=None):
    """读取一致预期 vs 实际净利润对比 CSV。
    返回 (list, metadata)。每个预测财年只能保留一个一月快照。
    """
    if not consensus_path:
        return None, None
    if not os.path.exists(consensus_path):
        raise FileNotFoundError(
            f"输入校验未通过： 一致预期文件不存在: {consensus_path}"
        )
    with open(consensus_path, "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if header is None:
            raise ValueError("数据质量未通过： 一致预期 CSV 为空")
        col_map = build_col_map(header)
        required = [
            "股票代码",
            "公司简称",
            "预测快照日",
            "预测财年",
            "一致预期净利润",
            "实际归母净利润",
            "币种",
            "金额单位",
            "值主体",
            "数据版本",
            "有效期",
        ]
        missing = [key for key in required if key not in col_map]
        if missing:
            raise ValueError(
                "输入校验未通过： 一致预期 CSV 缺少关键列: "
                f"{missing}。实际表头: {header}"
            )
        result = []
        seen_years = set()
        for raw in reader:
            if not raw:
                continue
            rec = {
                key: raw[idx] if idx < len(raw) else None
                for key, idx in col_map.items()
            }
            require_nonempty_values(
                [rec],
                ["币种", "金额单位", "值主体", "数据版本", "有效期"],
                "一致预期 CSV",
            )
            code = str(rec.get("股票代码") or "").strip()
            company = str(rec.get("公司简称") or "").strip()
            snapshot = str(rec.get("预测快照日") or "").strip()[:10]
            year = str(rec.get("预测财年") or "").strip()
            if not code or not company or not snapshot or not year:
                raise ValueError(
                    "输入校验未通过： 一致预期 CSV 的证券、公司、快照日和预测财年不得为空"
                )
            if expected_code and code != expected_code:
                raise ValueError(
                    "输入校验未通过： 一致预期证券代码与样本目标不一致: "
                    f"{code} != {expected_code}"
                )
            if expected_company and company != expected_company:
                raise ValueError(
                    "输入校验未通过： 一致预期公司简称与样本目标不一致: "
                    f"{company} != {expected_company}"
                )
            try:
                snapshot_date = datetime.strptime(snapshot, "%Y-%m-%d").date()
                forecast_year = int(year[:4])
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    "输入校验未通过： 预测快照日须为 YYYY-MM-DD，预测财年须以四位年份开头: "
                    f"快照={snapshot}, 财年={year}"
                ) from exc
            if snapshot_date.year != forecast_year or snapshot_date.month != 1:
                raise ValueError(
                    "输入校验未通过： 每个预测财年必须使用该财年一月的首个有效快照，"
                    f"不得跨年或回退到任意快照: 财年={year}, 快照={snapshot}"
                )
            if forecast_year in seen_years:
                raise ValueError(
                    "输入校验未通过： 同一预测财年存在多个快照或重复行，"
                    f"无法保证唯一口径: {forecast_year}"
                )
            seen_years.add(forecast_year)
            est = safe_float(rec.get("一致预期净利润"))
            act = safe_float(rec.get("实际归母净利润"))
            bias = None
            if est not in (None, 0) and act is not None:
                bias = round((act - est) / abs(est) * 100, 1)
            result.append(
                {
                    "股票代码": code,
                    "公司简称": company,
                    "预测快照日": snapshot,
                    "预测财年": str(forecast_year),
                    "一致预期净利润": est,
                    "实际归母净利润": act,
                    "偏差率(%)": bias,
                }
            )
    if not result:
        raise ValueError("数据质量未通过： 一致预期 CSV 没有数据行")
    metadata_fields = ["币种", "金额单位", "值主体", "数据版本", "有效期"]
    metadata_rows = []
    with open(consensus_path, "r", encoding="utf-8-sig") as f:
        dict_reader = csv.DictReader(f)
        raw_headers = dict_reader.fieldnames or []
        metadata_col_map = build_col_map(raw_headers)
        for raw in dict_reader:
            metadata_rows.append(
                {
                    key: raw.get(raw_headers[idx])
                    for key, idx in metadata_col_map.items()
                    if idx < len(raw_headers)
                }
            )
    metadata = {
        "文件路径": os.path.abspath(consensus_path),
        "SHA-256": file_sha256(consensus_path),
        "数据粒度": "证券×预测快照日×预测财年",
        "快照规则": "每个预测财年一月的首个有效快照；无该快照则该财年缺失，不回退",
        "记录数": len(result),
        "预测快照日": [row["预测快照日"] for row in result],
        "口径字段": {
            key: unique_values(metadata_rows, key) for key in metadata_fields
        },
    }
    return result, metadata


# ============================================================
# 打分解读
# ============================================================
def interpret_percentile(pct, higher_is_better=True):
    if pct is None:
        return "数据缺失"
    if higher_is_better:
        if pct >= 80:
            return "优秀（前20%）"
        if pct >= 50:
            return "中等偏上"
        if pct >= 20:
            return "中等偏下"
        return "偏弱（后20%，需排查）"
    else:
        # 越低越好（指标3：营运净资本占比越低=占款能力强）
        if pct <= 20:
            return "优秀（产业链话语权强，前20%）"
        if pct <= 50:
            return "中等偏上"
        if pct <= 80:
            return "中等偏下"
        return "偏弱（营运资金被占用，后20%）"


# ============================================================
# 主流程
# ============================================================
def run(company, sample_path, consensus_path, output_path, report_period=None):
    print(f"[全A分位定位] 目标公司: {company}")
    print(f"[全A分位定位] 样本文件: {sample_path}")

    rows, col_map, sample_metadata = load_sample(sample_path)
    print(f"[全A分位定位] 样本载入: {len(rows)} 行, 识别列: {sorted(col_map.keys())}")

    locked_report_period = sample_metadata["口径字段"]["报告期"][0]
    if report_period and report_period != locked_report_period:
        raise ValueError(
            "输入校验未通过： --period 与样本唯一报告期不一致: "
            f"{report_period} != {locked_report_period}"
        )

    per_stock = compute_metric_series(rows)
    print(f"[全A分位定位] 可识别证券样本: {len(per_stock)} 只")

    # 找到目标公司
    target = None
    exact_matches = [s for s in per_stock if s["公司简称"] == company]
    if len(exact_matches) == 1:
        target = exact_matches[0]
    elif len(exact_matches) > 1:
        raise ValueError(
            f"输入校验未通过： 样本中公司简称「{company}」对应多只证券，须改用唯一主体"
        )
    else:
        # 模糊匹配
        cands = [
            s for s in per_stock if company in s["公司简称"] or s["公司简称"] in company
        ]
        if len(cands) == 1:
            target = cands[0]
            print(f"[全A分位定位] 模糊匹配到: {target['公司简称']}")
        else:
            raise ValueError(
                f"输入校验未通过： 在样本中未唯一匹配到公司「{company}」。"
                f"请确认 --company 与样本'公司简称'列取值一致。候选: {[c['公司简称'] for c in cands[:5]]}"
            )

    # 各指标的全A分位数与中位数
    metric_defs = [
        ("指标1_应收周转率对数", "指标1：应收款项周转率(对数)", True),
        ("毛利率", "毛利率", True),
        ("指标2_生产资产周转率对数", "指标2：(固定资产+无形资产)周转率(对数)", True),
        ("指标3_营运净资本占比", "指标3：营运净资本(不含存货)/总资产", False),
        ("指标4_经营现金流总资产比", "指标4：经营性现金流/总资产", True),
        ("ROE", "ROE", True),
    ]

    indicators = {}
    quality_failures = []
    for key, label, higher_better in metric_defs:
        all_vals = [s[key] for s in per_stock]
        valid_count = sum(value is not None for value in all_vals)
        coverage = valid_count / len(per_stock) if per_stock else 0.0
        tval = target.get(key)
        pct = percentile_of(tval, all_vals)
        med = median_of(all_vals)
        metric_quality_reasons = []
        if coverage < QUALITY_COVERAGE_THRESHOLD:
            metric_quality_reasons.append(
                f"有效样本覆盖率{coverage:.1%}低于阈值{QUALITY_COVERAGE_THRESHOLD:.0%}"
            )
        if tval is None:
            metric_quality_reasons.append("目标公司该指标缺失")
        metric_status = "未通过" if metric_quality_reasons else "通过"
        if metric_quality_reasons:
            quality_failures.append(f"{label}: {'；'.join(metric_quality_reasons)}")
        indicators[label] = {
            "公司值": round(tval, 4) if tval is not None else None,
            "全A中位数": round(med, 4) if med is not None else None,
            "全A分位数(%)": pct,
            "打分解读": (
                interpret_percentile(pct, higher_better)
                if metric_status == "通过"
                else "无法判断"
            ),
            "方向": "越高越好" if higher_better else "越低越好",
            "有效样本数": valid_count,
            "样本覆盖率(%)": round(coverage * 100, 1),
            "质量状态": metric_status,
            "质量说明": metric_quality_reasons,
        }

    # 异常信号：应收周转率↓ + 毛利率↑ 背离（此处基于分位相对位置提示，趋势需结合历史）
    signals = []
    m1_pct = indicators["指标1：应收款项周转率(对数)"]["全A分位数(%)"]
    gm_pct = indicators["毛利率"]["全A分位数(%)"]
    if m1_pct is not None and gm_pct is not None:
        if m1_pct < 30 and gm_pct > 70:
            signals.append(
                "⚠ 背离信号：应收款项周转率处于全A后30%（回款弱），但毛利率处于前30%（高毛利）——"
                "警惕放账换收入或应收账款注水，需结合历史趋势与账龄核查。"
            )
    m4_pct = indicators["指标4：经营性现金流/总资产"]["全A分位数(%)"]
    if m4_pct is not None and m4_pct < 20:
        signals.append(
            "⚠ 现金流信号：经营性现金流/总资产处于全A后20%，利润现金含金量偏低，需核查利润质量。"
        )
    m3_info = indicators["指标3：营运净资本(不含存货)/总资产"]
    if m3_info["全A分位数(%)"] is not None and m3_info["全A分位数(%)"] > 80:
        signals.append(
            "⚠ 营运资金信号：营运净资本占比处于全A前20%（正值大），资金被上下游占用，产业链话语权偏弱。"
        )

    # 一致预期偏差
    consensus, consensus_metadata = load_consensus(
        consensus_path,
        expected_company=target["公司简称"],
        expected_code=target["股票代码"],
    )
    consensus_summary = None
    if consensus:
        biases = [c["偏差率(%)"] for c in consensus if c["偏差率(%)"] is not None]
        consensus_total = len(consensus)
        consensus_valid = len(biases)
        estimate_valid = sum(
            c["一致预期净利润"] not in (None, 0) for c in consensus
        )
        actual_valid = sum(c["实际归母净利润"] is not None for c in consensus)
        consensus_coverage = (
            consensus_valid / consensus_total if consensus_total else 0.0
        )
        avg_abs_bias = (
            round(sum(abs(b) for b in biases) / len(biases), 1) if biases else None
        )
        if avg_abs_bias is not None:
            if avg_abs_bias > 30:
                pred_note = "预测性差，估值锚不稳（平均绝对偏差>30%）"
            elif avg_abs_bias <= 10:
                pred_note = "预测性好，商业模式稳定（平均绝对偏差≤10%）"
            else:
                pred_note = "预测性中等"
        else:
            pred_note = "实际值尚不足，无法评估"
        if estimate_valid < consensus_total:
            quality_failures.append(
                "一致预期偏差: "
                f"有效预测财年{estimate_valid}/{consensus_total}，"
                "存在缺失或为零的一致预期，不能计算对应偏差"
            )
        if actual_valid < consensus_total:
            quality_failures.append(
                "一致预期偏差: "
                f"实际值有效财年{actual_valid}/{consensus_total}，"
                "存在尚未披露或无效实际值，不能把部分财年结果包装为完整成功"
            )
        consensus_summary = {
            "明细": consensus,
            "有效预测财年数": estimate_valid,
            "有效实际财年数": actual_valid,
            "有效偏差财年数": consensus_valid,
            "总财年数": consensus_total,
            "覆盖率(%)": round(consensus_coverage * 100, 1),
            "平均绝对偏差率(%)": avg_abs_bias,
            "预测性解读": pred_note,
        }

    if quality_failures:
        signals.append(
            "无法完整判断：存在质量未通过的指标；不得把未触发规则解释为不存在异常。"
        )
    elif not signals:
        signals.append("未触发明显背离/异常信号（仍需结合历史趋势判断）")

    result = {
        "质量状态": "未通过" if quality_failures else "通过",
        "质量说明": quality_failures,
        "公司简称": target["公司简称"],
        "报告期": locked_report_period,
        "分析时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "数据来源说明": "输入数据由 data_analyst 查询并锁定，脚本仅基于输入文件在本地计算。",
        "样本记录数": len(per_stock),
        "质量覆盖阈值(%)": round(QUALITY_COVERAGE_THRESHOLD * 100, 1),
        "输入文件": {
            "全A样本": sample_metadata,
            "一致预期": consensus_metadata,
        },
        "公司基本信息": {
            "股票代码": target["股票代码"],
            "申万一级行业": target["申万一级行业"],
        },
        "五大指标全A分位数": indicators,
        "异常信号": signals,
        "一致预期偏差": consensus_summary,
    }

    out = output_path or f"{target['公司简称']}_全A分位.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)

    print(f"\n[全A分位定位] 结果已保存: {out}")
    print(f"公司: {target['公司简称']} | 行业: {target['申万一级行业']}")
    print("五大指标全A分位数:")
    for label, info in indicators.items():
        print(
            f"  {label}: 公司值={info['公司值']} 分位={info['全A分位数(%)']}% "
            f"（{info['打分解读']}, 中位数={info['全A中位数']}）"
        )
    print("异常信号:")
    for s in result["异常信号"]:
        print(f"  {s}")
    if consensus_summary:
        print(
            f"一致预期平均绝对偏差: {consensus_summary['平均绝对偏差率(%)']}% "
            f"（{consensus_summary['预测性解读']}）"
        )
    return result


def main():
    parser = argparse.ArgumentParser(
        description="全A样本财务打分与分位数定位（数据查询工具取数，本地算分）"
    )
    parser.add_argument(
        "--company",
        required=True,
        help="【必填】目标公司简称（须与样本'公司简称'列一致）",
    )
    parser.add_argument(
        "--sample",
        required=True,
        help="【必填】全A样本横截面 CSV 路径（由平台取数落地）",
    )
    parser.add_argument(
        "--consensus", default=None, help="【可选】目标公司一致预期vs实际净利润对比 CSV"
    )
    parser.add_argument(
        "--period", default=None, help="【可选】绝对报告期 YYYY-MM-DD，须与样本唯一报告期完全一致"
    )
    parser.add_argument("--output", default=None, help="【可选】输出 JSON 路径")
    args = parser.parse_args()

    try:
        result = run(
            args.company,
            args.sample,
            args.consensus,
            args.output,
            args.period,
        )
        if result["质量状态"] == "未通过":
            print(
                "ERROR: 诊断 JSON 已保留，但质量未达到可交付标准",
                file=sys.stderr,
            )
            sys.exit(2)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
