#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
穿透叙事 · 关键词市场热度模块（叙事热度：过去一年绝对值 + 近1月边际）

【定位】把纪要/研报/点评/社媒中「围绕某公司的叙事议程」压缩为可比较的热度刻度：
  - 绝对值：过去约一年，各「详细复合叙事标签」在月度文本中的渗透率（热力图）；
  - 边际  ：最近一个完整月相对历史月序列的 Z 分与经验分位（排序柱图）。

【为什么需要】叙事变化是超额收益来源；文本议程权重的抬升/回落，是叙事变化的可观测代理。
  单词简称（如“1.6T/CPO”）信息量低且相互混淆，故采用**详细复合叙事标签 + 同义词簇**命中。

【本脚本不调用任何工具】只做确定性加工：读取 agent 已落盘的文档 JSON 分片（doc_searcher /
  search_paipai 的 save_as 产物，任意含 title/content/time/security_code 等字段的列表），
  过滤公司相关文档 → 按自然月聚合 → 计算渗透率矩阵与 Z 分 → 输出 JSON + 两张 PNG。

单位/口径铁律：
  - 分母 = 当月「公司相关」文档数；分子 = 当月命中该叙事同义词簇的文档数；同月同文档同叙事只计 1 次；
  - 渗透率(%) = 分子 / 分母 × 100；
  - 近月 = 最近一个**完整自然月**（分析日若在月中，请显式传 --recent-month 上月）；
  - Z = (近月渗透率 − 历史月均值) / 历史月标准差；经验分位 = 历史月中 ≤ 近月的比例。

用法：
  # 1) 先导出/查看默认关键词模板（按公司特点改写后存成 json 再传入）
  python keyword_heat.py --dump-keyword-template

  # 2) 生成热度矩阵与两张图
  python skills/user/penetrate-narrative-stock-analysis/scripts/keyword_heat.py \
    --inputs tmp/{sid}/tool_outputs/research_all.json,tmp/{sid}/tool_outputs/roadshow_all.json,tmp/{sid}/tool_outputs/comments_all.json \
    --company 中际旭创 --code 300308.SZ \
    --recent-month 2026-08 \
    --out-json tmp/{sid}/tool_outputs/keyword_heat_monthly.json \
    --out-summary tmp/{sid}/tool_outputs/keyword_heat_summary.md \
    --img-dir tmp/{sid}/img

  # 3) 自定义关键词（按公司特点）
  python keyword_heat.py --inputs ... --keywords-json tmp/{sid}/keywords.json ...
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# ----------------------------------------------------------------------------
# 默认关键词模板（示例：光模块/AI 算力链龙头；其它行业请改写标签与同义词簇）
# 设计原则：标签 = 完整复合叙事（3–8 字名词短语，含“动作/方向”），不是单词简称；
#          每类给 3–10 个同义词/近义写法（中英、缩写、常见错写），避免漏召与混淆。
# ----------------------------------------------------------------------------
DEFAULT_KEYWORDS = [
    {"id": "K1", "label": "1.6T放量/接棒主力",
     "patterns": [r"1\.6\s*[Tt]", r"1p6[Tt]", r"1\.6T上量", r"1\.6T放量", r"1\.6T出货", r"1\.6T订单", r"1\.6T部署"]},
    {"id": "K2", "label": "800G压舱/持续出货",
     "patterns": [r"800\s*[Gg]", r"800G出货", r"800G订单", r"800G放量", r"800G需求"]},
    {"id": "K3", "label": "硅光渗透/SiPh占比提升",
     "patterns": [r"硅光", r"SiPh", r"[Ss]ilicon\s*[Pp]hotonics?", r"硅光子", r"硅光占比", r"硅光渗透", r"硅光模块"]},
    {"id": "K4", "label": "NPO近封装/光引擎导入",
     "patterns": [r"\bNPO\b", r"[Nn]ear[\s\-]*[Pp]ackage[d]?\s*[Oo]ptics?", r"近封装", r"NPO产品", r"NPO量产", r"NPO订单"]},
    {"id": "K5", "label": "CPO共封装/路线博弈",
     "patterns": [r"\bCPO\b", r"[Cc]o[\s\-]*[Pp]ackage[d]?\s*[Oo]ptics?", r"共封装光学", r"共封装", r"CPO渗透", r"CPO替代"]},
    {"id": "K6", "label": "2.4T·3.2T/下一代速率",
     "patterns": [r"2\.4\s*[Tt]", r"3\.2\s*[Tt]", r"下一代速率", r"更高速率光模块", r"单波400G"]},
    {"id": "K7", "label": "Scale-up柜内光互连",
     "patterns": [r"[Ss]cale[\s\-]*[Uu]p", r"scaleup", r"柜内光", r"柜内互联", r"Scale[\s\-]*up场景", r"\bXPO\b", r"\bLPO\b", r"\bOCS\b", r"光交换机"]},
    {"id": "K8", "label": "毛利率·ASP/产品结构升级",
     "patterns": [r"毛利率", r"\bASP\b", r"平均售价", r"净利率", r"产品结构", r"高端产品占比", r"盈利能力", r"量价齐升"]},
    {"id": "K9", "label": "供应链锁料/物料紧缺",
     "patterns": [r"供应链", r"物料", r"光芯片", r"电芯片", r"\bDSP\b", r"\bEML\b", r"缺货", r"紧缺", r"备料", r"预付款", r"长协", r"锁定产能", r"上游供给"]},
    {"id": "K10", "label": "港股上市/A+H融资扩产",
     "patterns": [r"港股", r"H股", r"03308", r"3308\.HK", r"A\+H", r"H\s*股", r"港股通", r"港币", r"公开发行", r"超额配售"]},
    {"id": "K11", "label": "CSP订单能见度/Capex指引",
     "patterns": [r"\bCSP\b", r"云厂商", r"云服务商", r"资本开支", r"[Cc]apex", r"订单能见度", r"全年订单", r"需求指引", r"北美云", r"大客户订单"]},
    {"id": "K12", "label": "海外产能/泰国扩产交付",
     "patterns": [r"泰国", r"海外产能", r"海外工厂", r"东南亚", r"扩产", r"产能扩建", r"在建工程", r"年化产能", r"全球化产能", r"境外产能"]},
]

CODE_HINT = r"300308|03308|3308\.HK|Innolight"  # 兜底文本命中（可被 --code 覆盖）


def load_json(path: Path):
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if isinstance(data, list):
        # 支持 [{artifact_id, result:[...]}] 包装
        if data and isinstance(data[0], dict) and "result" in data[0] and not data[0].get("title"):
            out = []
            for block in data:
                r = block.get("result")
                if isinstance(r, list):
                    out.extend(r)
                elif isinstance(r, dict):
                    out.append(r)
            return out
        return data
    if isinstance(data, dict):
        for k in ("data", "results", "items", "docs", "records"):
            if isinstance(data.get(k), list):
                return data[k]
        if isinstance(data.get("result"), list):
            return data["result"]
    return []


def month_of(item: dict) -> str | None:
    for key in ("time", "publish_date", "date", "publish_time", "pub_time", "report_date"):
        v = item.get(key)
        if not v:
            continue
        s = str(v)[:10].replace("/", "-")
        try:
            dt = datetime.fromisoformat(s.replace("Z", ""))
            return f"{dt.year:04d}-{dt.month:02d}"
        except Exception:
            m = re.match(r"(\d{4})-(\d{2})", s)
            if m:
                return f"{m.group(1)}-{m.group(2)}"
    return None


def doc_text(item: dict) -> str:
    return "\n".join(
        str(item[k])
        for k in ("title", "title_standard", "content", "full_content", "summary", "summary_info")
        if item.get(k)
    )


def month_range(start: str, end: str) -> list[str]:
    ys, ms = int(start[:4]), int(start[5:7])
    ye, me = int(end[:4]), int(end[5:7])
    out = []
    while (ys, ms) <= (ye, me):
        out.append(f"{ys:04d}-{ms:02d}")
        ms += 1
        if ms > 12:
            ms, ys = 1, ys + 1
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="穿透叙事·关键词市场热度")
    ap.add_argument("--inputs", help="逗号分隔的文档 JSON 路径列表")
    ap.add_argument("--company", default="")
    ap.add_argument("--code", default="")
    ap.add_argument("--recent-month", default=None, help="最近完整自然月 YYYY-MM；默认取数据最大月")
    ap.add_argument("--start-month", default=None)
    ap.add_argument("--end-month", default=None)
    ap.add_argument("--keywords-json", default=None, help="自定义关键词 JSON（[{id,label,patterns:[...]}]）")
    ap.add_argument("--out-json", default="keyword_heat_monthly.json")
    ap.add_argument("--out-summary", default="keyword_heat_summary.md")
    ap.add_argument("--img-dir", default="img")
    ap.add_argument("--dump-keyword-template", action="store_true", help="打印默认关键词模板后退出")
    args = ap.parse_args()

    if args.dump_keyword_template:
        print(json.dumps(DEFAULT_KEYWORDS, ensure_ascii=False, indent=2))
        return 0

    if not args.inputs:
        print("[error] --inputs 必填（或使用 --dump-keyword-template）", file=sys.stderr)
        return 2

    if args.keywords_json and Path(args.keywords_json).exists():
        kws = json.loads(Path(args.keywords_json).read_text(encoding="utf-8"))
    else:
        kws = DEFAULT_KEYWORDS

    compiled = [
        (k["id"], k["label"], [re.compile(p, re.I) for p in k["patterns"]]) for k in kws
    ]

    code_hint = args.code.strip() or ""
    code_re = re.compile(
        (code_hint.split(".")[0] + r"|" + CODE_HINT) if code_hint else CODE_HINT, re.I
    )
    name_re = re.compile(args.company, re.I) if args.company else re.compile(r"旭创")

    def relevant(item: dict, text: str) -> bool:
        codes = item.get("security_code") or item.get("security_codes") or []
        if isinstance(codes, str):
            codes = [codes]
        names = item.get("security_name") or []
        if isinstance(names, str):
            names = [names]
        code_hit = any(code_re.search(str(c)) for c in codes)
        name_hit = any(name_re.search(str(n)) for n in names)
        text_hit = bool(code_re.search(text) or name_re.search(text))
        if len(text) < 40 and not text_hit:
            return False
        if code_hit or name_hit or text_hit:
            if not text_hit and not re.search(
                r"光模块|1\.6T|800G|硅光|CPO|NPO|光互连|毛利|营收|Innolight", text, re.I
            ):
                return code_hit and len(text) > 200
            return True
        return False

    month_docs: dict[str, set] = defaultdict(set)
    month_kw: dict[str, dict[str, set]] = defaultdict(lambda: defaultdict(set))
    seen: set = set()
    src_counts: dict[str, int] = defaultdict(int)

    for path in [p.strip() for p in args.inputs.split(",") if p.strip()]:
        items = load_json(Path(path))
        for i, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            text = doc_text(item)
            if not relevant(item, text):
                continue
            mon = month_of(item)
            if not mon:
                continue
            did = str(
                item.get("record_id")
                or item.get("roadshow_id")
                or item.get("announcement_id")
                or item.get("id")
                or f"{item.get('time')}|{item.get('title')}|{i}"
            )
            seen.add(did)
            month_docs[mon].add(did)
            src_counts[Path(path).name] += 1
            for kid, _lab, comps in compiled:
                if any(c.search(text) for c in comps):
                    month_kw[mon][kid].add(did)

    if not month_docs:
        print("[error] 未解析到任何公司相关文档，请检查 --inputs 路径与字段", file=sys.stderr)
        return 3

    all_months = sorted(month_docs.keys())
    start = args.start_month or all_months[0]
    end = args.end_month or all_months[-1]
    months = month_range(start, end)

    recent = args.recent_month or end
    if recent not in months:
        months = month_range(min(months[0], recent), max(months[-1], recent))
    hist_months = [m for m in months if m < recent]
    ri = months.index(recent)

    totals, matrix, hits_mat = [], {k: [] for k, _, _ in compiled}, {k: [] for k, _, _ in compiled}
    for mon in months:
        n = len(month_docs.get(mon, set()))
        totals.append(n)
        for kid, _lab, _c in compiled:
            h = len(month_kw.get(mon, {}).get(kid, set()))
            hits_mat[kid].append(h)
            matrix[kid].append(round(100.0 * h / n, 1) if n > 0 else None)

    import numpy as np

    recent_vs = []
    for kid, lab, _c in compiled:
        series = [matrix[kid][months.index(m)] for m in hist_months if matrix[kid][months.index(m)] is not None]
        rp = matrix[kid][ri] if matrix[kid][ri] is not None else 0.0
        if len(series) >= 2:
            mu = float(np.mean(series))
            sd = float(np.std(series, ddof=1))
            z = (rp - mu) / sd if sd > 1e-9 else 0.0
            pctile = 100.0 * sum(1 for x in series if x <= rp) / len(series)
        else:
            mu = float(np.mean(series)) if series else 0.0
            sd, z, pctile = 0.0, 0.0, 50.0
        recent_vs.append({
            "id": kid, "label": lab, "recent_month": recent,
            "recent_pct": round(rp, 1), "hist_mean": round(mu, 1), "hist_std": round(sd, 2),
            "z": round(z, 2), "delta_pp": round(rp - mu, 1), "pctile": round(pctile, 0),
            "hist_n_months": len(series),
        })
    recent_vs.sort(key=lambda x: x["z"], reverse=True)

    payload = {
        "meta": {
            "company": args.company, "code": args.code,
            "window": f"{months[0]}至{months[-1]}", "recent_month": recent,
            "hist_window": f"{hist_months[0]}至{hist_months[-1]}" if hist_months else "",
            "method": "同月同文档同关键词计1次；渗透率=命中文档数/当月公司相关文档数×100%；Z=(近月-历史均值)/历史标准差",
            "doc_counts_by_input": dict(src_counts),
            "monthly_total_docs": dict(zip(months, totals)),
            "total_unique_docs": len(seen),
        },
        "months": months,
        "keywords": [{"id": k["id"], "label": k["label"]} for k in kws],
        "matrix_penetration": matrix,
        "matrix_hits": hits_mat,
        "monthly_total_docs": totals,
        "recent_vs_hist": recent_vs,
    }
    Path(args.out_json).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        f"# {args.company or '公司'}关键词热度摘要（详细叙事标签）",
        f"- 窗口：{payload['meta']['window']}；近月：{recent}",
        f"- 去重后公司相关文档：{len(seen)}",
        f"- 月度文档量：{dict(zip(months, totals))}",
        "",
        "## 详细叙事关键词",
    ]
    lines += [f"- {k['id']} {k['label']}" for k in kws]
    lines += ["", "## 近月相对历史 Z 分排序"]
    lines += [
        f"- {r['label']}: 近月{r['recent_pct']}% | 历史均值{r['hist_mean']}% | Z={r['z']} | Δ={r['delta_pp']}pct | 分位{r['pctile']}%"
        for r in recent_vs
    ]
    Path(args.out_summary).write_text("\n".join(lines), encoding="utf-8")

    # ---- plots ----
    import matplotlib

    matplotlib.rcParams["font.sans-serif"] = ["SimHei", "Noto Sans CJK SC", "WenQuanYi Zen Hei", "DejaVu Sans"]
    matplotlib.rcParams["axes.unicode_minus"] = False
    import matplotlib.pyplot as plt
    import seaborn as sns

    sns.set_theme(style="white", rc={
        "font.sans-serif": ["SimHei", "Noto Sans CJK SC", "WenQuanYi Zen Hei", "DejaVu Sans"],
        "axes.unicode_minus": False,
    })
    img = Path(args.img_dir)
    img.mkdir(parents=True, exist_ok=True)

    labels = [k["label"] for k in kws]
    data = np.array(
        [[(matrix[k["id"]][j] if matrix[k["id"]][j] is not None else np.nan) for j in range(len(months))] for k in kws],
        dtype=float,
    )
    ann = np.empty_like(data, dtype=object)
    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            if np.isnan(data[i, j]) or totals[j] == 0:
                ann[i, j] = "—"
                data[i, j] = np.nan
            else:
                ann[i, j] = f"{data[i, j]:.0f}"

    fig, ax = plt.subplots(figsize=(15.5, max(6.5, 0.55 * len(kws) + 2.5)), layout="constrained")
    sns.heatmap(
        data, ax=ax, cmap=sns.color_palette("Reds", as_cmap=True), vmin=0, vmax=100,
        annot=ann, fmt="", linewidths=0.6, linecolor="#f5f5f5",
        cbar_kws={"label": "提及该叙事的文档占比(%)"},
        yticklabels=[f"N{i+1}{lab}" for i, lab in enumerate(labels)],
        xticklabels=[m[2:] for m in months], annot_kws={"size": 8},
    )
    ax.set_title(
        f"图A {args.company}叙事关键词在研报/纪要等中的月度渗透率（%，Alpha派文本库，{months[0]}至{months[-1]}）",
        fontsize=13, fontweight="bold", pad=12,
    )
    ax.tick_params(axis="x", rotation=45, labelsize=9)
    ax.tick_params(axis="y", rotation=0, labelsize=9)
    fig.text(0.99, 0.01, "来源：Alpha派研报/纪要/点评/社媒等去噪样本｜同月同文档计1次｜分母=当月公司相关文档数",
             fontsize=8, color="#556270", ha="right", va="bottom")
    p1 = img / "关键词热度_月度渗透率热力图.png"
    fig.savefig(p1, dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(12.8, max(6.0, 0.5 * len(kws) + 2.4)), layout="constrained")
    ys = [r["label"] for r in recent_vs][::-1]
    zs = [r["z"] for r in recent_vs][::-1]
    pcs = [r["pctile"] for r in recent_vs][::-1]
    colors = ["#C23531" if z >= 0 else "#2E8B57" for z in zs]
    ax.barh(ys, zs, color=colors, height=0.72, edgecolor="none")
    ax.axvline(0, color="#333", lw=1)
    ax.set_xlim(min(-2.5, min(zs) - 0.3), max(3.0, max(zs) + 0.95))
    ax.grid(True, axis="x", alpha=0.35, color="#DDE3EA", linestyle="--")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.set_xlabel("Z分（近月渗透率相对历史月序列）", fontsize=11)
    ax.set_title(f"图B 叙事强度边际变化：近1月({recent})渗透率相对历史月的Z分排序", fontsize=13, fontweight="bold", pad=12)
    ax.tick_params(axis="y", labelsize=9)
    for ylab, z, pc in zip(ys, zs, pcs):
        txt = f"Z={z:.2f} / 分位{int(pc)}%"
        if z >= 0:
            ax.text(z + 0.05, ylab, txt, va="center", ha="left", fontsize=8.5, color="#333")
        else:
            ax.text(z - 0.05, ylab, txt, va="center", ha="right", fontsize=8.5, color="#333")
    fig.text(0.99, 0.01,
             f"历史对照：{payload['meta']['hist_window']}｜近月文档数={totals[ri]}｜红=高于历史、绿=低于历史",
             fontsize=8, color="#556270", ha="right", va="bottom")
    p2 = img / "关键词热度_近月边际变化Z分.png"
    fig.savefig(p2, dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    print(f"[ok] json -> {args.out_json}")
    print(f"[ok] summary -> {args.out_summary}")
    print(f"[ok] figA -> {p1}")
    print(f"[ok] figB -> {p2}")
    print("months:", dict(zip(months, totals)))
    for r in recent_vs:
        print(f"  {r['label']}: Z={r['z']} 近月{r['recent_pct']}% 历史{r['hist_mean']}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
