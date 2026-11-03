#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
穿透叙事 · 分市场结构化取数适配器 / DCF 参数装配器 (v1.0.0)

【定位】把"每次现场判断走哪个工具、取哪三年、怎么换算单位"这类不确定性，
固化成确定性脚本，解决 skill 同公司多跑数字不一致的问题。

【为什么需要】实测（2026-08-28）：
  - A股/港股：quick_fetch 有一致预期/市值/估值/利润表，但【缺总股本】，
    且 consensus 的 forecast_year 返回顺序可能乱序；
  - 美股：quick_fetch 几乎全空（stock_info/market_quote/valuation/consensus 全 []）；
    美股域 data_analyst 有市值/股本/收盘价但【无一致预期表】；
    美股一致预期唯一来源是 search_global_data（且默认偏远端财年，近端需研报交叉）。

【本脚本不直接调用任何工具】（沙箱脚本无法调工具）。它做两件确定性的事：
  1) normalize：把 agent 已落盘的原始工具产物（quick_fetch 的 .json /
     data_analyst、search_global_data 的 .csv）按固定口径规则解析、单位归一、
     年份选择、consensus 排序，抽出 DCF 反算所需的 cap/shares/E0-E3；
  2) assemble：把归一后的字段 + 券商目标价列表，写成 dcf_params.json
     （dcf_implied.py / build_dcf_workbook.py / 最终报告三处唯一事实源）。

单位铁律（与 dcf-workbook.md 一致）：
  市值/E 用【亿元】(美股用【亿美元】)、股本用【亿股】、价格用【元/美元】。
  quick_fetch 的 cons_profit 常为【万元】→ ÷10000 变亿元；
  search_global_data 的 netIncomeAvg 为【美元原值】→ ÷1e8 变亿美元。

用法：
  # A股：从 quick_fetch json + data_analyst 总股本(命令行) 装配
  python collect_financials.py assemble-cn \
      --qf tmp/{sid}/80_financial.json \
      --shares-yi 11.7791 \
      --company 中际旭创 --code 300308.SZ \
      --asof 2026-08-28 \
      --brokers-json tmp/{sid}/11_targets.json \
      --out tmp/{sid}/dcf_params.json

  # 美股：从 data_analyst(股本/市值/价) + search_global_data 估计 csv 装配
  python collect_financials.py assemble-us \
      --shares-yi 11.2939 --cap-usd-yi 10564.2 --price 935.39 \
      --est-csv tmp/{sid}/mu_estimates.csv \
      --company 美光科技 --code MU.US \
      --base-year 2025 --asof 2026-08-28 \
      --brokers-json tmp/{sid}/11_targets.json \
      --out tmp/{sid}/dcf_params.json

  # 仅解析 quick_fetch json，打印可得性诊断（不落盘）
  python collect_financials.py inspect-qf --qf tmp/{sid}/80_financial.json
"""
import argparse
import csv
import json
import os
import sys
from datetime import datetime


# ------------------------- 通用工具 -------------------------

def _load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _first_record(qf):
    """quick_fetch save_as 的 .json 是 [ {query, identity, data, ...} ] 列表，取第一条。"""
    if isinstance(qf, list):
        return qf[0] if qf else {}
    return qf


def _to_yi_from_wan(v):
    """万元 → 亿元"""
    return round(float(v) / 10000.0, 4)


def _to_yi_from_raw(v):
    """原值(元/美元) → 亿"""
    return round(float(v) / 1e8, 4)


def _pick_year(dt_str):
    """从 forecast_year(如 '2026-12-31') 或日期取年份 int。"""
    if dt_str is None:
        return None
    s = str(dt_str)
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d", "%Y%m%d"):
        try:
            return datetime.strptime(s[:len(fmt) + 2].strip(), fmt).year
        except Exception:
            continue
    # 兜底：抓前4位数字
    digits = "".join(ch for ch in s[:4] if ch.isdigit())
    return int(digits) if len(digits) == 4 else None


# ------------------------- quick_fetch (A股/港股) 解析 -------------------------

def parse_qf_consensus(rec):
    """从 quick_fetch record 解析一致预期，返回按 forecast_year 升序去重(取最新 end_date)的列表：
       [{'year': 2026, 'profit_yi': 342.56, 'end_date': '2026-08-27', 'unit': '万元'}, ...]
    """
    data = rec.get("data", {})
    ce = data.get("consensus_estimate", []) or []
    rows = []
    for block in ce:
        inner = block.get("consensus_estimate", []) if isinstance(block, dict) else []
        for item in inner:
            year = _pick_year(item.get("forecast_year"))
            profit = item.get("cons_profit")
            unit = item.get("cons_profit_unit", "万元")
            end_date = item.get("end_date")
            if year is None or profit is None:
                continue
            profit_yi = _to_yi_from_wan(profit) if "万" in str(unit) else round(float(profit) / 1e8, 4)
            rows.append({"year": year, "profit_yi": profit_yi,
                         "end_date": str(end_date), "unit": unit,
                         "eps": item.get("cons_eps"), "yoy": item.get("cons_profit_yoy")})
    # 同一 year 取最新 end_date
    best = {}
    for r in rows:
        y = r["year"]
        if y not in best or (r["end_date"] or "") > (best[y]["end_date"] or ""):
            best[y] = r
    return [best[y] for y in sorted(best.keys())]


def parse_qf_market(rec):
    """解析市值(亿元)、收盘价(元)、PE/PB/PS。返回 dict。"""
    data = rec.get("data", {})
    out = {}
    for blk in data.get("market_quote", []) or []:
        for k, v in blk.items():
            if not isinstance(v, dict):
                continue
            name = v.get("ind_der_name", "")
            unit = v.get("unit", "")
            vals = v.get("values", [])
            if not vals:
                continue
            latest = vals[0]
            if "总市值" in name:
                val = float(latest.get("value"))
                if "万" in unit:
                    out["cap_yi"] = round(val / 10000.0, 4)
                elif "亿" in unit:
                    out["cap_yi"] = round(val, 4)
                else:
                    out["cap_yi"] = round(val / 1e8, 4)
                out["cap_asof"] = str(latest.get("dt"))
            elif "收盘价" in name:
                out["price"] = round(float(latest.get("value")), 4)
    for blk in data.get("valuation", []) or []:
        for k, v in blk.items():
            if not isinstance(v, dict):
                continue
            name = v.get("ind_der_name", "")
            vals = v.get("values", [])
            if not vals:
                continue
            if "PE,TTM" in name or "市盈率(PE,TTM)" in name:
                out["pe_ttm"] = round(float(vals[0].get("value")), 2)
            elif "市净率" in name:
                out["pb"] = round(float(vals[0].get("value")), 2)
            elif "市销率" in name:
                out["ps"] = round(float(vals[0].get("value")), 2)
    return out


# ------------------------- search_global_data (美股) 估计 csv 解析 -------------------------

def parse_us_estimates(est_csv):
    """解析 search_global_data 的 *_Financial_Estimates_Annual.csv。
       返回按财年升序：[{'year':2028,'netincome_yi_usd':1856.5,'eps':169.8,'n':11}, ...]
       口径：netIncomeAvg 为美元原值 → ÷1e8 = 亿美元；date 的年份 = 财年结束年。
    """
    rows = []
    with open(est_csv, "r", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            year = _pick_year(r.get("date"))
            ni = r.get("netIncomeAvg")
            eps = r.get("epsAvg")
            n = r.get("numAnalystsEps")
            if year is None:
                continue
            row = {"year": year, "eps": float(eps) if eps not in (None, "") else None,
                   "n_analysts": int(float(n)) if n not in (None, "") else None}
            if ni not in (None, ""):
                row["netincome_yi_usd"] = round(float(ni) / 1e8, 2)
            rows.append(row)
    # 按财年去重（同一 csv 可能被多次查询追加，或上游返回重复行）：同年取信息最全的一条
    best = {}
    for r in rows:
        y = r["year"]
        if y not in best or (r.get("netincome_yi_usd") is not None and best[y].get("netincome_yi_usd") is None):
            best[y] = r
    return [best[y] for y in sorted(best.keys())]


# ------------------------- E0-E3 选择规则（固化口径） -------------------------

def select_e1e2e3(consensus_rows, base_year):
    """从升序 consensus 行里选 E1/E2/E3 = base_year+1, +2, +3 三年。
       consensus_rows: [{'year':int,'profit_yi':float,...}]
       base_year: 最近已披露完整年报年度（E0 年）。
       返回 (e1, e2, e3, notes, missing_years)
    """
    by_year = {r["year"]: r for r in consensus_rows}
    want = [base_year + 1, base_year + 2, base_year + 3]
    picked, notes, missing = [], {}, []
    for i, y in enumerate(want, start=1):
        if y in by_year:
            picked.append(by_year[y]["profit_yi"])
            notes[f"e{i}"] = f"{y}年一致预期({by_year[y].get('end_date','')})"
        else:
            picked.append(None)
            missing.append(y)
            notes[f"e{i}"] = f"{y}年一致预期【缺失】"
    return picked[0], picked[1], picked[2], notes, missing


# ------------------------- 装配 dcf_params.json -------------------------

def _load_brokers(path):
    if not path or not os.path.exists(path):
        return []
    try:
        data = _load_json(path)
        if isinstance(data, dict) and "brokers" in data:
            return data["brokers"]
        if isinstance(data, list):
            return data
    except Exception as e:
        print(f"[warn] 券商目标价文件解析失败: {e}", file=sys.stderr)
    return []


def _write_params(params, out):
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(params, f, ensure_ascii=False, indent=2)
    print(f"[ok] dcf_params 已写入: {out}")
    print(json.dumps({k: params[k] for k in
                      ("company", "code", "cap", "price", "shares", "e0", "e1", "e2", "e3",
                       "base_year", "steady_year")}, ensure_ascii=False, indent=2))


def _validate(params):
    """装配后自检，打印告警。"""
    warns = []
    for k in ("cap", "shares", "e1", "e2", "e3"):
        if params.get(k) in (None, 0):
            warns.append(f"缺失关键字段 {k}")
    # 隐含价一致性：cap ≈ price × shares
    if all(params.get(k) for k in ("cap", "price", "shares")):
        implied_cap = params["price"] * params["shares"]
        diff = abs(implied_cap - params["cap"]) / params["cap"] * 100
        if diff > 3:
            warns.append(f"市值≠价×股本 (价×股本={implied_cap:.1f} vs 市值={params['cap']:.1f}, 差{diff:.1f}%)")
    # E 单调性提示（仅提示，不阻断）
    es = [params.get("e1"), params.get("e2"), params.get("e3")]
    if all(e is not None for e in es) and not (es[0] <= es[1] <= es[2]):
        warns.append(f"E1/E2/E3 非单调递增: {es}（周期/见顶回落时正常，请人工确认口径）")
    if warns:
        print("\n[自检告警]")
        for w in warns:
            print("  - " + w)
    else:
        print("\n[自检] 通过：cap/shares/E1-E3 齐全，市值≈价×股本。")
    return warns


def assemble_cn(args):
    qf = _first_record(_load_json(args.qf))
    consensus = parse_qf_consensus(qf)
    market = parse_qf_market(qf)
    e1, e2, e3, e_notes, missing = select_e1e2e3(consensus, args.base_year)
    cap = args.cap_yi if args.cap_yi else market.get("cap_yi")
    price = args.price if args.price else market.get("price")
    params = {
        "company": args.company, "code": args.code,
        "cap": cap, "price": price, "shares": args.shares_yi,
        "e0": args.e0, "e1": e1, "e2": e2, "e3": e3,
        "base_year": args.base_year, "steady_year": args.steady_year,
        "r": 0.10, "asof": args.asof,
        "currency": "CNY",
        "shares_note": args.shares_note or "总股本由输入数据提供，具体来源需按实际取数记录注明",
        "e_notes": e_notes,
        "consensus_raw": consensus,
        "valuation": {k: market.get(k) for k in ("pe_ttm", "pb", "ps") if market.get(k) is not None},
        "brokers": _load_brokers(args.brokers_json),
        "data_source_note": "数据来源以实际取数记录为准",
    }
    if missing:
        print(f"[warn] 以下年度一致预期缺失，需补研报盈利预测交叉: {missing}", file=sys.stderr)
    _write_params(params, args.out)
    _validate(params)


def assemble_us(args):
    """美股：股本/市值/价来自 data_analyst(命令行传入)；E1-E3 来自 search_global_data 估计 csv。
       口径：接受远端财年 + 研报盈利预测交叉（用户 2026-08-28 确认）。
       美股一致预期以【亿美元】记账，市值以【亿美元】记账。
    """
    est = parse_us_estimates(args.est_csv) if args.est_csv else []
    # E1/E2/E3 = base_year+1..+3（财年结束年）
    by_year = {r["year"]: r for r in est}
    want = [args.base_year + 1, args.base_year + 2, args.base_year + 3]
    e_vals, e_notes, missing = [], {}, []
    for i, y in enumerate(want, start=1):
        r = by_year.get(y)
        if r and r.get("netincome_yi_usd") is not None:
            e_vals.append(r["netincome_yi_usd"])
            e_notes[f"e{i}"] = f"FY{y} 一致预期净利润(亿美元, n={r.get('n_analysts')})"
        elif r and r.get("eps") is not None and args.shares_yi:
            # 兜底：eps × 股本(亿股) = 净利润(亿美元)
            ni = round(r["eps"] * args.shares_yi, 2)
            e_vals.append(ni)
            e_notes[f"e{i}"] = f"FY{y} 由 epsAvg×股本 反推净利润(亿美元, 兜底)"
        else:
            e_vals.append(None)
            missing.append(y)
            e_notes[f"e{i}"] = f"FY{y} 一致预期【缺失】→需研报盈利预测交叉补入"
    params = {
        "company": args.company, "code": args.code,
        "cap": args.cap_usd_yi, "price": args.price, "shares": args.shares_yi,
        "e0": args.e0, "e1": e_vals[0], "e2": e_vals[1], "e3": e_vals[2],
        "base_year": args.base_year, "steady_year": args.steady_year,
        "r": 0.10, "asof": args.asof,
        "currency": "USD",
        "shares_note": args.shares_note or "股本/市值/价格由输入数据提供，具体来源需按实际取数记录注明",
        "e_notes": e_notes,
        "us_estimates_raw": est,
        "estimate_caveat": "美股一致预期来自全球数据库(接受远端财年)；近端财年缺失时以研报盈利预测交叉补入(用户确认口径)",
        "brokers": _load_brokers(args.brokers_json),
        "data_source_note": "数据来源以实际取数记录为准",
    }
    if missing:
        print(f"[warn] 以下财年一致预期缺失，需研报盈利预测交叉补入 e1/e2/e3: {missing}", file=sys.stderr)
    _write_params(params, args.out)
    _validate(params)


def inspect_qf(args):
    qf = _first_record(_load_json(args.qf))
    data = qf.get("data", {})
    print("=== quick_fetch 可得性诊断 ===")
    for t in ("stock_info", "market_quote", "valuation", "consensus_estimate", "income_statement"):
        n = len(data.get(t, []) or [])
        print(f"  {t}: {'有' if n else '【空】'} ({n} blocks)")
    print("\n-- 一致预期(升序, 已按最新end_date去重) --")
    for r in parse_qf_consensus(qf):
        print(f"   {r['year']}: {r['profit_yi']} 亿  (end_date={r['end_date']}, eps={r.get('eps')}, yoy={r.get('yoy')})")
    print("\n-- 市值/估值 --")
    print("  ", json.dumps(parse_qf_market(qf), ensure_ascii=False))


# ------------------------- CLI -------------------------

def main():
    ap = argparse.ArgumentParser(description="穿透叙事分市场取数适配器 / DCF 参数装配器")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("inspect-qf", help="解析 quick_fetch json 打印可得性诊断")
    p.add_argument("--qf", required=True)
    p.set_defaults(func=inspect_qf)

    p = sub.add_parser("assemble-cn", help="A股/港股：quick_fetch + 总股本 装配 dcf_params")
    p.add_argument("--qf", required=True, help="quick_fetch save_as 的 .json")
    p.add_argument("--shares-yi", type=float, required=True, help="总股本(亿股, data_analyst 补)")
    p.add_argument("--company", required=True)
    p.add_argument("--code", required=True)
    p.add_argument("--base-year", type=int, default=2025, help="E0 年(最近已披露完整年报年度)")
    p.add_argument("--steady-year", type=int, default=2035)
    p.add_argument("--asof", required=True)
    p.add_argument("--e0", type=float, default=None, help="E0 已披露净利润(亿元, 可选)")
    p.add_argument("--cap-yi", type=float, default=None, help="覆盖市值(亿元); 缺省用 quick_fetch")
    p.add_argument("--price", type=float, default=None, help="覆盖收盘价; 缺省用 quick_fetch")
    p.add_argument("--shares-note", default=None)
    p.add_argument("--brokers-json", default=None, help="券商目标价 json([{name,date,rating,price}])")
    p.add_argument("--out", required=True)
    p.set_defaults(func=assemble_cn)

    p = sub.add_parser("assemble-us", help="美股：data_analyst(股本/市值/价)+全球库估计 装配 dcf_params")
    p.add_argument("--shares-yi", type=float, required=True, help="总股本(亿股, data_analyst)")
    p.add_argument("--cap-usd-yi", type=float, required=True, help="市值(亿美元, data_analyst)")
    p.add_argument("--price", type=float, required=True, help="最新收盘价(美元, data_analyst)")
    p.add_argument("--est-csv", default=None, help="search_global_data *_Financial_Estimates_Annual.csv")
    p.add_argument("--company", required=True)
    p.add_argument("--code", required=True)
    p.add_argument("--base-year", type=int, required=True, help="E0 财年结束年(如美光 FY2025=2025)")
    p.add_argument("--steady-year", type=int, default=2035)
    p.add_argument("--asof", required=True)
    p.add_argument("--e0", type=float, default=None)
    p.add_argument("--shares-note", default=None)
    p.add_argument("--brokers-json", default=None)
    p.add_argument("--out", required=True)
    p.set_defaults(func=assemble_us)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
