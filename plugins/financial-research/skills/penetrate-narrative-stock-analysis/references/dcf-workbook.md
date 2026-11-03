# Excel DCF 工作簿（强制交付附件）

版式以用户样例「穿透叙事_DCF模板.xlsx」为标准：三表、黄格可改、灰底关键结果、与 `dcf_implied.py` 同模型。

## 一、文件与脚本

| 路径 | 作用 |
| --- | --- |
| `assets/dcf_template.xlsx` | 空白模板（结构/公式骨架；无公司数据） |
| `scripts/build_dcf_workbook.py` | **唯一**生成/刷新交付簿的入口 |
| `scripts/dcf_implied.py` | 反算/正算引擎（build 内部调用） |

**禁止**手写新 Excel、禁止用 CSV/markdown 表顶替本附件、禁止把券商目标价改成 PE 重估表。

## 二、三表结构（不可改名、不可删表）

### 1. `Assumptions`（可调假设）

| 区域 | 行/格 | 规则 |
| --- | --- | --- |
| 标题 | A1 | `{公司}（{code}）穿透叙事 DCF 可调假设` |
| 黄格输入 | B5–B15 | 市值、股本、股价、E0–E3、基准年、稳态年、r、假设终局 L |
| 派生公式 | B18–B28 | N、g、前3年/过渡/永续 PV、模型市值、对应股价、动态 PE、L/E3、L/E0 |
| 隐含 L 三档 | A32:E34 | **脚本固化数值**（r=8/10/12%），对照用；改黄格后须重跑脚本刷新 |

默认：`假设终局L(B15)` = 现价隐含 L @ r=10%（B33）。用户改 B15 可正算「若终局为该 L，模型市值/股价是多少」。

### 2. `券商目标价隐含L`

| 列 | 内容 |
| --- | --- |
| A–D | 机构/场景、日期、评级、目标价（黄格） |
| E | 公式 `=D{row}*Assumptions!$B$6` |
| F–H | 脚本固化：该目标价市值下 r=8/10/12% 隐含 L |
| I | L/E3 @10%（固化） |
| J | 公式 `=G{row}/Assumptions!$B$33`（相对现价 L@10%，**禁止写死常数**） |

第 5 行固定为「现价」场景；其后为各券商目标价（建议 ≥5 家，内外资尽量都有）。

### 3. `敏感性_L到市值`

- A 列：终局 L 水平（黄格，脚本按 E3 倍数网格 + 现价隐含 L 生成）
- B 列：公式 `=A{row}/Assumptions!$B$11`
- C–D：脚本固化对应市值、动态 PE(E1)；中枢 r 默认 10%

## 三、报告模式强制流程

在 `dcf_implied.py implied` + `brokers` 算完、写 md 报告的**同时或之后**，必须生成 xlsx：

```bash
# 1) 将参数落盘（推荐，可复核）
# tmp/{session_id}/dcf_params.json

# 2) 生成交付簿
python skills/user/penetrate-narrative-stock-analysis/scripts/build_dcf_workbook.py build \
  --input tmp/{session_id}/dcf_params.json \
  --out tmp/{session_id}/outputs/{公司名}_穿透叙事_DCF模板.xlsx
```

`dcf_params.json` 最小字段：

```json
{
  "company": "中际旭创",
  "code": "300308.SZ",
  "cap": 10113.29,
  "price": 864.58,
  "shares": 11.6973,
  "e0": 107.97,
  "e1": 360.66,
  "e2": 664.92,
  "e3": 985.72,
  "base_year": 2025,
  "steady_year": 2035,
  "r": 0.10,
  "asof": "2026-08-10",
  "shares_note": "总股本口径说明",
  "e_notes": {
    "e0": "已披露",
    "e1": "一致预期日期",
    "e2": "一致预期日期",
    "e3": "一致预期日期"
  },
  "brokers": [
    {"name": "高盛", "date": "2026-07-17", "rating": "Buy", "price": 2581, "source": "可选备注"}
  ]
}
```

单位铁律：市值/E 为**亿元**，股本为**亿股**，价格为**元**；若财务接口为万元，必须 ÷10000。

命令行等价（无券商时也可）：

```bash
python scripts/build_dcf_workbook.py build \
  --company "某某" --code 000001.SZ \
  --cap 1000 --price 20 --shares 50 \
  --e0 40 --e1 45 --e2 50 --e3 55 \
  --asof 2026-08-10 \
  --out /path/to/某某_穿透叙事_DCF模板.xlsx
```

刷新空白骨架（仅维护 skill 时）：

```bash
python scripts/build_dcf_workbook.py init-template --out ../assets/dcf_template.xlsx
```

## 四、自检

- [ ] 三表齐全，表名与样例一致
- [ ] Assumptions 黄格 = 报告所用同一套 cap/shares/E1–E3/基准年/稳态年
- [ ] 现价隐含 L @8/10/12% 与 `dcf_implied.py implied` 一致（允许四舍五入到 0.1 亿）
- [ ] 每条券商目标价均有 F–H 隐含 L；J 列引用 `Assumptions!$B$33` 而非写死数字
- [ ] 文件名：`{公司名}_穿透叙事_DCF模板.xlsx`
- [ ] 与 md 报告一并交付；answer.files 含该 xlsx
- [ ] 封面/备注含「不构成投资建议」

## 五、与对话快答的关系

- **对话快答/研讨**：可不生成 xlsx，口头/文本给隐含 L 即可。
- **任何报告档（速览/标准/深度）**：必须附 xlsx。
- 用户只说「给我 DCF 模板/Excel」：直接 `build`，可不出长报告。
