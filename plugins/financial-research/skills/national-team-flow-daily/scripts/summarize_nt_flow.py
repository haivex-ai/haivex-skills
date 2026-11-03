#!/usr/bin/env python3
"""汇总国家队代理口径（核心宽基ETF净流入）日度结果。

输入:
  --core   核心池日度明细 CSV（需含日期/代码/净流入等列，列名中英别名均可）
  --broad  可选，宽基全市场明细/汇总 CSV
  --market 可选，指数与北向语境 CSV
  --trade-date YYYY-MM-DD  基准日 T；缺省取 core 最大日期
  --outdir 输出目录
  --prefix 输出文件前缀，默认 nt_flow

输出:
  {prefix}_daily_summary.csv
  {prefix}_core_detail_{T}.csv
  {prefix}_series.csv
  stdout 打印简要结论
"""
from __future__ import annotations

import argparse
import csv
import math
import os
import re
import sys
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple


# 默认核心池分池（6位代码）
POOL_MAP = {
    "大盘压舱": {"510300", "510310", "510330", "159919", "510050"},
    "中小盘托底": {"510500", "512100", "159845"},
    "成长稳估": {"159915", "159949", "588000", "588080", "588200", "159967"},
}

DEFAULT_CORE_CODES = set().union(*POOL_MAP.values())


def _norm_col(c: str) -> str:
    return re.sub(r"[\s_\-]+", "", str(c).strip().lower())


# 列名别名 → 标准字段
COL_ALIASES = {
    "trade_date": [
        "tradedate", "date", "交易日期", "截止日期", "统计日期", "enddate",
        "statdate", "tradingday", "navdate",
    ],
    "fund_code": [
        "fundcode", "code", "symbol", "证券代码", "基金代码", "etf代码",
        "ticker", "combsymbol", "secucode",
    ],
    "fund_name": [
        "fundname", "name", "证券简称", "基金简称", "etf名称", "基金名称", "secname",
    ],
    "cash_flow_yi": [
        "cashflowyi", "cash_flow_yi", "净流入亿元", "资金净流入亿元", "净流入(亿)",
        "netinflowyi", "flowyi",
    ],
    "cash_flow_raw": [
        "cashflow", "cash_flow", "资金流向", "资金净流入", "净流入", "净流入金额",
        "netinflow", "net_inflow", "inflow", "cASH_FLOW".lower(),
    ],
    "share_chg": [
        "sharechg", "share_chg", "份额变化", "份额变动", "deltaShares".lower(),
        "shareschange", "chgshares",
    ],
    "share_begin": ["sharebegin", "期初份额", "beginshares", "startshares"],
    "share_end": ["shareend", "期末份额", "endshares", "totalshares", "shares"],
    "close": ["close", "收盘价", "closeprice", "px_last"],
    "pct_chg": ["pctchg", "pct_chg", "涨跌幅", "changeratio", "pctchange"],
    "amount_yi": ["amountyi", "成交额亿元", "amount_yi"],
    "amount": ["amount", "成交额", "turnover", "tval", "amountyuan"],
    "flow_source": ["flowsource", "flow_source", "来源", "source"],
    "benchmark": ["benchmark", "跟踪指数", "benchmark_or_index", "indexname"],
}


def _build_reverse_alias() -> Dict[str, str]:
    rev = {}
    for std, aliases in COL_ALIASES.items():
        rev[_norm_col(std)] = std
        for a in aliases:
            rev[_norm_col(a)] = std
    return rev


ALIAS_REV = _build_reverse_alias()


def read_csv(path: str) -> Tuple[List[str], List[Dict[str, Any]]]:
    if not path or not os.path.exists(path):
        return [], []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        sample = f.read(4096)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",\t;")
        except Exception:
            dialect = csv.excel
        reader = csv.DictReader(f, dialect=dialect)
        raw_fields = reader.fieldnames or []
        mapping = {}
        for c in raw_fields:
            std = ALIAS_REV.get(_norm_col(c))
            if std and std not in mapping.values():
                mapping[c] = std
            else:
                mapping[c] = c  # keep original
        rows = []
        for r in reader:
            nr = {}
            for k, v in r.items():
                if k is None:
                    continue
                nr[mapping.get(k, k)] = v
            rows.append(nr)
        # standardized field list preference
        fields = list(dict.fromkeys(mapping.values()))
        return fields, rows


def _to_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    if isinstance(x, (int, float)):
        if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
            return None
        return float(x)
    s = str(x).strip().replace(",", "").replace("%", "")
    if s == "" or s.lower() in {"none", "null", "nan", "-", "—", "na"}:
        return None
    # 中文单位粗处理
    mult = 1.0
    if s.endswith("亿"):
        mult = 1.0
        s = s[:-1]
    elif s.endswith("万"):
        mult = 1e-4  # 万 → 亿
        s = s[:-1]
    elif s.endswith("元"):
        mult = 1e-8
        s = s[:-1]
    try:
        return float(s) * mult
    except ValueError:
        return None


def _code6(code: Any) -> str:
    if code is None:
        return ""
    s = str(code).strip().upper()
    m = re.search(r"(\d{6})", s)
    return m.group(1) if m else s


def _parse_date(s: Any) -> Optional[str]:
    if s is None:
        return None
    t = str(s).strip()
    if not t:
        return None
    t = t.replace("/", "-").replace(".", "-")
    # datetime with time
    if " " in t:
        t = t.split(" ")[0]
    if "T" in t:
        t = t.split("T")[0]
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%Y-%m-%d%H:%M:%S"):
        try:
            return datetime.strptime(t[:19] if len(t) > 10 and fmt != "%Y%m%d" else t, fmt if fmt != "%Y-%m-%d%H:%M:%S" else "%Y-%m-%d").strftime("%Y-%m-%d")
        except Exception:
            continue
    # compact yyyymmdd
    if re.fullmatch(r"\d{8}", t):
        return f"{t[0:4]}-{t[4:6]}-{t[6:8]}"
    return t[:10] if len(t) >= 10 else t


def infer_pool(code6: str, name: str = "") -> str:
    for pool, codes in POOL_MAP.items():
        if code6 in codes:
            return pool
    n = name or ""
    if any(k in n for k in ("沪深300", "上证50", "上证180")):
        return "大盘压舱"
    if any(k in n for k in ("中证500", "中证1000", "中证2000", "A500")):
        return "中小盘托底"
    if any(k in n for k in ("创业板", "科创")):
        return "成长稳估"
    return "其他"


def normalize_flow_yi(row: Dict[str, Any]) -> Tuple[Optional[float], str]:
    """返回 (净流入亿元, source)。"""
    src = str(row.get("flow_source") or "").strip()
    v = _to_float(row.get("cash_flow_yi"))
    if v is not None:
        return v, src or "cash_flow_yi"

    raw = _to_float(row.get("cash_flow_raw"))
    if raw is not None:
        # 启发式单位：|raw| 很大 → 元；中等 → 万；小 → 已是亿
        ar = abs(raw)
        if ar >= 1e6:  # >= 100万 按元
            return raw / 1e8, src or "cash_flow_yuan_to_yi"
        if ar >= 50:  # 按万元
            return raw / 1e4, src or "cash_flow_wan_to_yi"
        return raw, src or "cash_flow_raw_as_yi"

    # 份额差 × 价
    sh = _to_float(row.get("share_chg"))
    if sh is None:
        b = _to_float(row.get("share_begin"))
        e = _to_float(row.get("share_end"))
        if b is not None and e is not None:
            sh = e - b
    px = _to_float(row.get("close"))
    if sh is not None and px is not None and px > 0:
        # 份额单位：若 |sh| 很小可能是亿份
        ash = abs(sh)
        if ash < 1e4:  # 当作亿份
            return sh * px, src or "share_yi_times_price"
        return sh * px / 1e8, src or "share_times_price"

    return None, src or "missing"


def amount_to_yi(row: Dict[str, Any]) -> Optional[float]:
    v = _to_float(row.get("amount_yi"))
    if v is not None:
        return v
    raw = _to_float(row.get("amount"))
    if raw is None:
        return None
    ar = abs(raw)
    if ar >= 1e6:
        return raw / 1e8
    if ar >= 50:
        return raw / 1e4
    return raw


def prepare_core(rows: List[Dict[str, Any]], trade_date: Optional[str]) -> List[Dict[str, Any]]:
    out = []
    for r in rows:
        d = _parse_date(r.get("trade_date"))
        code = _code6(r.get("fund_code"))
        if not d or not code:
            continue
        name = str(r.get("fund_name") or "")
        flow, src = normalize_flow_yi(r)
        item = {
            "trade_date": d,
            "fund_code": code,
            "fund_name": name,
            "pool": infer_pool(code, name),
            "cash_flow_yi": flow,
            "amount_yi": amount_to_yi(r),
            "close": _to_float(r.get("close")),
            "pct_chg": _to_float(r.get("pct_chg")),
            "flow_source": src,
            "share_chg": _to_float(r.get("share_chg")),
        }
        out.append(item)
    if trade_date:
        # keep all for series; filter later
        pass
    return out


def write_csv(path: str, fieldnames: List[str], rows: Iterable[Dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in fieldnames})


def signal_label(flow: Optional[float]) -> str:
    if flow is None:
        return "数据缺失"
    if flow >= 80:
        return "强净申购"
    if flow >= 50:
        return "明显净申购"
    if flow >= 15:
        return "温和净申购"
    if flow > -15:
        return "中性"
    if flow > -30:
        return "温和净赎回"
    return "明显净赎回"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--core", required=True, help="核心池日度 CSV")
    ap.add_argument("--broad", default="", help="宽基全市场 CSV（可选）")
    ap.add_argument("--market", default="", help="市场语境 CSV（可选）")
    ap.add_argument("--trade-date", default="", help="基准日 T YYYY-MM-DD")
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--prefix", default="nt_flow")
    ap.add_argument("--inflow-strong", type=float, default=50.0)
    ap.add_argument("--outflow-flag", type=float, default=-30.0)
    ap.add_argument("--single-flag", type=float, default=20.0)
    args = ap.parse_args()

    _, core_raw = read_csv(args.core)
    if not core_raw:
        print("ERROR: core CSV empty or missing", file=sys.stderr)
        return 2

    core = prepare_core(core_raw, args.trade_date or None)
    if not core:
        print("ERROR: no valid core rows after normalize", file=sys.stderr)
        return 2

    dates = sorted({r["trade_date"] for r in core})
    t = args.trade_date or dates[-1]
    if t not in dates:
        # nearest previous
        prev = [d for d in dates if d <= t]
        t = prev[-1] if prev else dates[-1]

    # daily series total & by pool
    by_date_pool: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
    by_date_total: Dict[str, float] = defaultdict(float)
    by_date_missing: Dict[str, int] = defaultdict(int)
    for r in core:
        d = r["trade_date"]
        if r["cash_flow_yi"] is None:
            by_date_missing[d] += 1
            continue
        by_date_pool[d][r["pool"]] += r["cash_flow_yi"]
        by_date_total[d] += r["cash_flow_yi"]

    # T detail
    detail_t = [r for r in core if r["trade_date"] == t]
    detail_t_sorted = sorted(
        detail_t,
        key=lambda x: (x["cash_flow_yi"] is None, -(x["cash_flow_yi"] or 0.0)),
    )
    for r in detail_t_sorted:
        fl = r["cash_flow_yi"]
        flags = []
        if fl is not None and fl >= args.single_flag:
            flags.append("个券大额净申购")
        if fl is not None and fl <= -args.single_flag:
            flags.append("个券大额净赎回")
        r["flag"] = "|".join(flags)

    # last 5 trading dates present
    d_before = [d for d in dates if d <= t]
    last5 = d_before[-5:]
    last10 = d_before[-10:]
    sum5 = sum(by_date_total.get(d, 0.0) for d in last5)
    sum10 = sum(by_date_total.get(d, 0.0) for d in last10)
    total_t = by_date_total.get(t)
    if t in by_date_missing and by_date_missing[t] == len(detail_t):
        total_t = None

    # pool rows for T and 5d
    pool_order = ["大盘压舱", "成长稳估", "中小盘托底", "其他"]
    summary_rows = []
    for pool in pool_order:
        t_val = by_date_pool[t].get(pool) if total_t is not None or by_date_pool[t] else None
        # if all missing, t_val may be 0 wrongly — check any non-null that day in pool
        pool_rows = [r for r in detail_t if r["pool"] == pool]
        if pool_rows and all(r["cash_flow_yi"] is None for r in pool_rows):
            t_val = None
        elif pool_rows:
            t_val = sum(r["cash_flow_yi"] for r in pool_rows if r["cash_flow_yi"] is not None)
        s5 = 0.0
        any5 = False
        for d in last5:
            # sum that day pool
            day_rows = [r for r in core if r["trade_date"] == d and r["pool"] == pool and r["cash_flow_yi"] is not None]
            if day_rows:
                any5 = True
                s5 += sum(r["cash_flow_yi"] for r in day_rows)
        summary_rows.append({
            "trade_date": t,
            "pool": pool,
            "cash_flow_yi_t": None if t_val is None else round(t_val, 4),
            "cash_flow_yi_5d": None if not any5 else round(s5, 4),
            "signal": signal_label(t_val),
        })

    # total row
    summary_rows.append({
        "trade_date": t,
        "pool": "核心池合计",
        "cash_flow_yi_t": None if total_t is None else round(total_t, 4),
        "cash_flow_yi_5d": None if all(d not in by_date_total for d in last5) else round(sum5, 4),
        "signal": signal_label(total_t),
    })

    # series
    series_rows = []
    for d in d_before:
        val = by_date_total.get(d)
        miss = by_date_missing.get(d, 0)
        n = len([r for r in core if r["trade_date"] == d])
        if miss == n:
            val = None
        series_rows.append({
            "trade_date": d,
            "core_cash_flow_yi": None if val is None else round(val, 4),
            "direction": "流入" if (val or 0) > 1 else ("流出" if (val or 0) < -1 else "近乎零/缺失"),
            "n_names": n,
            "n_missing_flow": miss,
            **{f"pool_{k}": round(by_date_pool[d].get(k, 0.0), 4) for k in ("大盘压舱", "成长稳估", "中小盘托底", "其他")},
        })

    outdir = args.outdir
    os.makedirs(outdir, exist_ok=True)
    pfx = args.prefix
    path_sum = os.path.join(outdir, f"{pfx}_daily_summary.csv")
    path_det = os.path.join(outdir, f"{pfx}_core_detail_{t.replace('-', '')}.csv")
    path_ser = os.path.join(outdir, f"{pfx}_series.csv")

    write_csv(
        path_sum,
        ["trade_date", "pool", "cash_flow_yi_t", "cash_flow_yi_5d", "signal"],
        summary_rows,
    )
    write_csv(
        path_det,
        ["trade_date", "fund_code", "fund_name", "pool", "cash_flow_yi", "amount_yi",
         "close", "pct_chg", "flow_source", "flag"],
        detail_t_sorted,
    )
    write_csv(
        path_ser,
        ["trade_date", "core_cash_flow_yi", "direction", "n_names", "n_missing_flow",
         "pool_大盘压舱", "pool_成长稳估", "pool_中小盘托底", "pool_其他"],
        series_rows,
    )

    # broad optional quick sum
    broad_note = ""
    if args.broad and os.path.exists(args.broad):
        _, brows = read_csv(args.broad)
        bflows = []
        for r in brows:
            d = _parse_date(r.get("trade_date"))
            if d and d != t and str(r.get("fund_code", "")).upper() not in {"TOTAL", "合计"}:
                # still try total rows without date
                pass
            fl, _ = normalize_flow_yi(r)
            code = str(r.get("fund_code") or "").upper()
            name = str(r.get("fund_name") or "")
            if code in {"TOTAL", "合计"} or "合计" in name:
                if fl is not None and (not d or d == t):
                    broad_note = f"宽基全市场合计约 {fl:.2f} 亿"
                    break
            if (not d or d == t) and fl is not None:
                bflows.append(fl)
        if not broad_note and bflows:
            broad_note = f"宽基明细合计约 {sum(bflows):.2f} 亿（未去重校验）"

    # stdout summary
    def fmt(x: Optional[float]) -> str:
        return "N/A" if x is None else f"{x:+.2f}"

    print(f"T={t}")
    print(f"核心池合计净流入(亿) T日={fmt(total_t)} | 近5日={fmt(None if all(d not in by_date_total for d in last5) else sum5)} | 近10日={fmt(None if all(d not in by_date_total for d in last10) else sum10)}")
    print(f"信号={signal_label(total_t)}")
    for row in summary_rows:
        if row["pool"] == "核心池合计":
            continue
        print(f"  - {row['pool']}: T={fmt(row['cash_flow_yi_t'])} | 5d={fmt(row['cash_flow_yi_5d'])} | {row['signal']}")
    top_in = [r for r in detail_t_sorted if r["cash_flow_yi"] is not None][:5]
    top_out = [r for r in sorted(detail_t_sorted, key=lambda x: (x["cash_flow_yi"] is None, x["cash_flow_yi"] or 0))][:5]
    if top_in:
        print("Top流入:", ", ".join(f"{r['fund_name'] or r['fund_code']}({r['cash_flow_yi']:+.2f})" for r in top_in if (r['cash_flow_yi'] or 0) > 0) or "无")
    if top_out:
        print("Top流出:", ", ".join(f"{r['fund_name'] or r['fund_code']}({r['cash_flow_yi']:+.2f})" for r in top_out if (r['cash_flow_yi'] or 0) < 0) or "无")
    if broad_note:
        print(broad_note)
    n_miss = sum(1 for r in detail_t if r["cash_flow_yi"] is None)
    if n_miss:
        print(f"WARNING: T日 {n_miss}/{len(detail_t)} 只净流入缺失，请检查取数路径/单位")
    print("files:")
    print(" ", path_sum)
    print(" ", path_det)
    print(" ", path_ser)
    return 0


if __name__ == "__main__":
    sys.exit(main())
