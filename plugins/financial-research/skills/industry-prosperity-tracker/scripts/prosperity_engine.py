#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全行业景气度评分引擎 (纯 Python 标准库实现)
-------------------------------------------------
输入: 一个 config dict / JSON, 描述若干行业, 每个行业含若干指标的最新值/上期值/同比.
输出: 景气评分结果 dict (扩散指数 + 多维打分 + 趋势箭头 + 数据验证 + Challenge 占位).

设计原则:
- 不依赖 pandas/numpy, 仅标准库, 适配 tool_code 受限环境.
- 指标方向 direction: 'up' 表示数值越大越景气; 'down' 表示数值越小越景气(如库存/产销比).
- 缺失值容错: 缺值的指标不参与该维度计算, 并在 data_quality 中记录.

config 结构示例见 references / scripts 同目录 demo, 关键字段:
{
  "as_of": "2026-06-07",
  "industries": [
    {
      "name": "煤炭", "board": "上游",
      "macro_anchor": "PPI",                 # 宏观锚, 用于 V4 校验
      "macro_anchor_direction": "up",        # 宏观锚当前方向
      "indicators": [
        {"name":"主焦煤库提价","dim":"price","direction":"up",
         "latest":2070.0,"prev":1830.0,"yoy":0.05,"freq":"week","unit":"元/吨","update":"2026-06-07"},
        {"name":"主流港口煤炭库存","dim":"inventory","direction":"down",
         "latest":520.0,"prev":560.0,"yoy":-0.08,"freq":"week","unit":"万吨","update":"2026-06-07"},
        ...
      ]
    }
  ]
}

dim 取值: price / volume / inventory / profit / valuation_quantile
"""
import json
import sys

# 维度 -> 权重 (多维打分卡, 见 scoring_validation_challenge.md 1.2)
DIM_WEIGHTS = {
    "price": 0.25,        # 价格动能
    "volume": 0.25,       # 量(产销/开工)
    "inventory": 0.15,    # 库存
    "profit": 0.15,       # 盈利/价差(含行业PPI)
    "valuation_quantile": 0.20,  # 景气历史分位
}

DIFFUSION_UP = 0.60   # 扩散指数上行阈值
DIFFUSION_DOWN = 0.40 # 扩散指数下行阈值


def _signed_change(ind):
    """返回指标的'景气方向化'环比变动: 正=景气改善, 负=景气恶化.
    若 direction=='down'(库存类), 则数值下降为景气改善, 需取反.
    """
    latest = ind.get("latest")
    prev = ind.get("prev")
    if latest is None or prev is None or prev == 0:
        return None
    chg = (latest - prev) / abs(prev)
    if ind.get("direction") == "down":
        chg = -chg
    return chg


def _signed_yoy(ind):
    """同比的景气方向化."""
    yoy = ind.get("yoy")
    if yoy is None:
        return None
    if ind.get("direction") == "down":
        yoy = -yoy
    return yoy


def diffusion_index(indicators):
    """扩散指数: 景气方向化后上行指标占比. 优先用环比, 无环比时回退到同比."""
    valid = []
    for ind in indicators:
        c = _signed_change(ind)
        if c is None:
            c = _signed_yoy(ind)
        if c is not None:
            valid.append(c)
    if not valid:
        return None, 0
    up = sum(1 for c in valid if c > 0)
    return up / len(valid), len(valid)


def trend_arrow(diff_ratio):
    if diff_ratio is None:
        return "NA"
    if diff_ratio > DIFFUSION_UP:
        return "↑"
    if diff_ratio < DIFFUSION_DOWN:
        return "↓"
    return "–"


def dimension_scores(indicators):
    """按维度聚合打分, 每个维度取该维度指标的(环比方向化均值)映射到 0-100.
    映射: score = 50 + 50 * tanh-like(用简单线性截断), 改善为正.
    """
    dim_vals = {}
    quantile_vals = {}
    for ind in indicators:
        dim = ind.get("dim")
        if dim not in DIM_WEIGHTS:
            continue
        # 历史分位维度: latest 即为分位数(0-100), 直接作为得分, 不做变动映射
        if dim == "valuation_quantile":
            if ind.get("latest") is not None:
                quantile_vals.setdefault(dim, []).append(float(ind["latest"]))
            continue
        # 其余维度: 优先用环比, 缺失用同比
        c = _signed_change(ind)
        if c is None:
            c = _signed_yoy(ind)
        if c is None:
            continue
        dim_vals.setdefault(dim, []).append(c)

    dim_score = {}
    for dim, vals in dim_vals.items():
        avg = sum(vals) / len(vals)
        # 线性映射: ±10% 变动 ~ ±50分, 截断到 [0,100]
        score = 50.0 + avg * 500.0
        score = max(0.0, min(100.0, score))
        dim_score[dim] = round(score, 1)
    for dim, vals in quantile_vals.items():
        dim_score[dim] = round(sum(vals) / len(vals), 1)
    return dim_score


def composite_score(dim_score):
    """加权综合分, 仅对已有维度归一化权重."""
    if not dim_score:
        return None
    total_w = sum(DIM_WEIGHTS[d] for d in dim_score)
    if total_w == 0:
        return None
    s = sum(dim_score[d] * DIM_WEIGHTS[d] for d in dim_score) / total_w
    return round(s, 1)


def validate_industry(ind_cfg, as_of):
    """数据验证 V1-V5, 返回结论列表."""
    notes = []
    indicators = ind_cfg.get("indicators", [])
    # V1 口径/频率/更新
    stale = [i["name"] for i in indicators if i.get("update") and i["update"] < _minus_days(as_of, 45)]
    if stale:
        notes.append({"check": "V1口径/时效", "result": "存疑",
                      "detail": "以下指标更新滞后>45天: " + ", ".join(stale)})
    else:
        notes.append({"check": "V1口径/时效", "result": "通过", "detail": "指标频率/单位/更新日期正常"})

    # V2 季节性
    if as_of[5:7] in ("01", "02"):
        notes.append({"check": "V2季节性", "result": "警示",
                      "detail": "当前处于1-2月, 春节扰动严重, 优先看同比口径"})
    else:
        notes.append({"check": "V2季节性", "result": "通过", "detail": "非春节扰动窗口"})

    # V3 量价库存交叉印证
    price_chg = _avg_dim_change(indicators, "price")
    vol_chg = _avg_dim_change(indicators, "volume")
    inv_chg = _avg_dim_change(indicators, "inventory")  # 已方向化(去库为正)
    if price_chg is not None and price_chg > 0:
        if (inv_chg is not None and inv_chg < 0) or (vol_chg is not None and vol_chg < 0):
            notes.append({"check": "V3量价库存", "result": "警示",
                          "detail": "价格改善但库存累积或开工/产量走弱, 警惕成本推动/限产挺价的伪景气"})
        else:
            notes.append({"check": "V3量价库存", "result": "通过",
                          "detail": "价格改善伴随去库/放量, 需求拉动逻辑自洽"})
    else:
        notes.append({"check": "V3量价库存", "result": "中性", "detail": "价格未明显改善, 不触发伪景气判断"})

    # V4 宏观锚一致性
    anchor = ind_cfg.get("macro_anchor")
    anchor_dir = ind_cfg.get("macro_anchor_direction")
    diff_ratio, _ = diffusion_index(indicators)
    ind_dir = trend_arrow(diff_ratio)
    if anchor and anchor_dir:
        consistent = (anchor_dir == "up" and ind_dir == "↑") or (anchor_dir == "down" and ind_dir == "↓") or ind_dir == "–"
        notes.append({"check": "V4宏观锚一致性", "result": "通过" if consistent else "警示",
                      "detail": "行业景气方向(%s) vs 宏观锚%s方向(%s): %s" % (
                          ind_dir, anchor, anchor_dir, "一致" if consistent else "背离, 需判断高频领先或单指标失真")})
    else:
        notes.append({"check": "V4宏观锚一致性", "result": "跳过", "detail": "未配置宏观锚"})

    # V5 多源
    multi = [i["name"] for i in indicators if i.get("multi_source")]
    notes.append({"check": "V5多源比对", "result": "提示",
                  "detail": ("已多源交叉: " + ", ".join(multi)) if multi else "建议对核心指标补充第二来源交叉验证"})
    return notes


def challenge_industry(ind_cfg, dim_score, diff_ratio):
    """结论 Challenge C1-C5, 返回风险清单."""
    items = []
    indicators = ind_cfg.get("indicators", [])
    name = ind_cfg.get("name", "")

    # C1 拐点真伪: 量价背离 / 低基数
    price_chg = _avg_dim_change(indicators, "price")
    vol_chg = _avg_dim_change(indicators, "volume")
    if price_chg and price_chg > 0 and (vol_chg is None or vol_chg <= 0):
        items.append({"type": "C1拐点真伪", "risk": "量价背离: 价涨而量未增, 警惕情绪/资金或挺价驱动的伪景气"})
    low_base = [i["name"] for i in indicators if (i.get("yoy") or 0) > 0.5]
    if low_base:
        items.append({"type": "C1低基数", "risk": "同比高增可能含低基数效应: " + ", ".join(low_base)})

    # C2 传导时滞
    items.append({"type": "C2传导时滞", "risk": "高频景气领先业绩约1-2季度, 勿将本期高频改善直接等同当季业绩兑现"})

    # C3 单指标失真
    if len(indicators) <= 2:
        items.append({"type": "C3单指标依赖", "risk": "%s 景气仅由<=2个指标支撑, 单指标失真(检修/台风/口径调整)将显著影响结论" % name})

    # C4 周期位置/分位
    vq = None
    for i in indicators:
        if i.get("dim") == "valuation_quantile" and i.get("latest") is not None:
            vq = i["latest"]
    if vq is not None and vq > 85:
        items.append({"type": "C4周期位置", "risk": "景气历史分位达%.0f%%(高位), 警惕接近见顶/均值回归" % vq})

    # C5 抢装/抢出口透支 (由 config 标注)
    if ind_cfg.get("pull_forward_risk"):
        items.append({"type": "C5需求透支", "risk": ind_cfg["pull_forward_risk"]})

    if not items:
        items.append({"type": "通用", "risk": "暂无显著红旗, 但仍需跟踪供给端在建产能与远期需求持续性"})
    return items


# ---------- 工具函数 ----------
def _avg_dim_change(indicators, dim):
    vals = []
    for ind in indicators:
        if ind.get("dim") != dim:
            continue
        c = _signed_change(ind)
        if c is None:
            c = _signed_yoy(ind)
        if c is not None:
            vals.append(c)
    if not vals:
        return None
    return sum(vals) / len(vals)


def _minus_days(date_str, days):
    """简单日期减法(近似, 仅用于时效粗判). date_str=YYYY-MM-DD."""
    y, m, d = int(date_str[:4]), int(date_str[5:7]), int(date_str[8:10])
    total = y * 360 + m * 30 + d - days
    ny = total // 360
    rem = total % 360
    nm = rem // 30
    nd = rem % 30
    nm = max(1, min(12, nm))
    nd = max(1, min(30, nd))
    return "%04d-%02d-%02d" % (ny, nm, nd)


def run(config):
    as_of = config.get("as_of", "")
    results = []
    for ind_cfg in config.get("industries", []):
        indicators = ind_cfg.get("indicators", [])
        diff_ratio, n_valid = diffusion_index(indicators)
        dim_score = dimension_scores(indicators)
        comp = composite_score(dim_score)
        result = {
            "name": ind_cfg.get("name"),
            "board": ind_cfg.get("board"),
            "diffusion_ratio": round(diff_ratio, 3) if diff_ratio is not None else None,
            "n_valid_indicators": n_valid,
            "trend": trend_arrow(diff_ratio),
            "dimension_scores": dim_score,
            "composite_score": comp,
            "validation": validate_industry(ind_cfg, as_of),
            "challenges": challenge_industry(ind_cfg, dim_score, diff_ratio),
        }
        results.append(result)
    return {"as_of": as_of, "results": results}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python prosperity_engine.py <config.json> [out.json]")
        sys.exit(1)
    fin = open(sys.argv[1], "r", encoding="utf-8")
    cfg = json.load(fin)
    fin.close()
    out = run(cfg)
    txt = json.dumps(out, ensure_ascii=False, indent=2)
    if len(sys.argv) >= 3:
        fo = open(sys.argv[2], "w", encoding="utf-8")
        fo.write(txt)
        fo.close()
        print("written ->", sys.argv[2])
    else:
        print(txt)
