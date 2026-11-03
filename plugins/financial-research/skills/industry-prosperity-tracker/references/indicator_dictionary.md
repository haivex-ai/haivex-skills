# 行业景气度指标字典（全行业 · 高频周度 + 中频月度）

> 用途：本字典是「全行业景气度跟踪模型」的核心知识库。按"上游 / 中游 / 下游 / 金融房建 / 支持服务"五大板块组织，覆盖申万一级行业。每个行业列出**核心高频指标（周度/日度）**与**中频指标（月度）**，并标注指标方向（↑越大越景气 / ↓越大越景气）、数据获取路径。
>
> 方法论来源：天风证券《中观景气度数据库和定量模型应用》[来源:report_ecXaL6wgzTYuyE7MtX1AYb1ElrdwlenH8fqZB00Fudhtm4O8lntHlGLLTewvTGIS]、浙商证券《行业景气度跟踪报告》、广发《新兴产业景气跟踪及比较框架》、国联民生《如何基于高频数据刻画宏观景气》[来源:roadShow_I4rrtfkhCub0gxC8IEh291_3qwstPJJUcvnBE4-nplwxZHYSCf7bN29l_BUBfTnu]、华泰《行业景气度指标水平一览》、民生《行业信息跟踪月报》。

---

## 〇、宏观锚定框架（指标 → 行业敏感性映射）

景气跟踪的底层逻辑：先确认宏观高频指标，再映射到对应行业的收入增速/ROE。国联民生长周期相关性分析结论[来源:roadShow_I4rrtfkhCub0gxC8IEh291_3qwstPJJUcvnBE4-nplwxZHYSCf7bN29l_BUBfTnu]：

| 宏观指标 | 强敏感行业（同向） | 跟踪频率 | 说明 |
|---|---|---|---|
| **PPI（同比/环比）** | 上游周期（煤炭、有色、石油石化、钢铁、基础化工）+ 部分中游制造 | 月度 | 周期品收入增速与PPI高度挂钩，是上游景气最重要的锚 [来源:roadShow_I4rrtfkhCub0gxC8IEh291_3qwstPJJUcvnBE4-nplwxZHYSCf7bN29l_BUBfTnu] |
| **CPI** | 下游消费（必选/可选消费、食品饮料、农林牧渔、医药） | 月度 | CPI对下游更重要 [来源:roadShow_I4rrtfkhCub0gxC8IEh291_3qwstPJJUcvnBE4-nplwxZHYSCf7bN29l_BUBfTnu] |
| **社零（社会消费品零售总额）** | 下游消费、商贸零售、汽车、家电 | 月度 | 对下游消费敏感 [来源:roadShow_I4rrtfkhCub0gxC8IEh291_3qwstPJJUcvnBE4-nplwxZHYSCf7bN29l_BUBfTnu] |
| **PMI / 工业增加值** | 中游制造（机械、军工、环保、汽车、电力设备） | 月度 | 工业增加值与PMI对中游制造敏感性高 [来源:roadShow_I4rrtfkhCub0gxC8IEh291_3qwstPJJUcvnBE4-nplwxZHYSCf7bN29l_BUBfTnu] |
| **社融 / M2 / 信贷** | 金融、地产、基建链 | 月度 | 流动性与投资强度 |

**高频→宏观→行业的推演链**：用日频/周频高频指标（生产端开工率、价格、流量）领先预判 PMI/PPI/CPI/工业增加值的月度走向，再外推各行业季报景气方向。结论：高频跟踪中，**中游产出端（制造业）信号最强最稳定**，上游(PPI链)与下游(CPI链)相对偏弱但可跟踪；**价格类指标历史吻合度最高，最易跟踪** [来源:roadShow_I4rrtfkhCub0gxC8IEh291_3qwstPJJUcvnBE4-nplwxZHYSCf7bN29l_BUBfTnu]。

---

## 一、上游板块（资源品 · 强PPI敏感）

景气判断核心：**量（产量/开工率）+ 价（现货/期货价）+ 库存（去库=景气上行）+ 价差/利润**。

### 1.1 煤炭
- **高频（周）**：京唐港主焦煤库提价(含税)↑、动力煤期货结算价↑、秦皇岛动力末煤(Q5500)价格↑、焦炭/焦煤期货价↑、主流港口煤炭库存量↓（去库为正）、天津港焦炭库存 [来源:report_ecXaL6wgzTYuyE7MtX1AYb1ElrdwlenH8fqZB00Fudhtm4O8lntHlGLLTewvTGIS]
- **中频（月）**：原煤产量(当月值)、炼焦煤产销比(>1偏过剩)、动力煤年度长协价、煤炭开采和洗选业PPI当月同比↑ [来源:report_ecXaL6wgzTYuyE7MtX1AYb1ElrdwlenH8fqZB00Fudhtm4O8lntHlGLLTewvTGIS]
- **数据路径**：`search_cn_marketdata`（煤价/产量时序）；PPI走 `edb-macro-data`

### 1.2 石油石化
- **高频（周）**：布伦特原油Dtd现货价、阿曼原油现货价、石油沥青装置开工率↑、IPE英国天然气期货价 [来源:report_ecXaL6wgzTYuyE7MtX1AYb1ElrdwlenH8fqZB00Fudhtm4O8lntHlGLLTewvTGIS]
- **中频（月）**：美国钻机数量、OPEC原油产量、石油和天然气开采业PPI当月同比↑ [来源:report_ecXaL6wgzTYuyE7MtX1AYb1ElrdwlenH8fqZB00Fudhtm4O8lntHlGLLTewvTGIS]
- **数据路径**：原油价 `search_global_data`；PPI/开工率 `edb-macro-data`/`search_cn_marketdata`

### 1.3 有色金属
- **高频（周）**：LME铜/铝/铅/锌/锡/镍3个月期价及库存(去库为正)、黑钨精矿均价、氢氧化锂/碳酸锂价格、稀土价格指数、Comex金银价、铝吨利润、氧化铝/铝土矿价格、铝开工率 [来源:report_ecXaL6wgzTYuyE7MtX1AYb1ElrdwlenH8fqZB00Fudhtm4O8lntHlGLLTewvTGIS][来源:report_7DLVE05y0WRs6FnNFeI96RBy4kKqAJJG6-3E37LRAbbiKZXkakrn0CZ7mm8P8iKT]
- **中频（月）**：金属钴均价、电解锰片价格、有色金属矿采选业PPI当月同比 [来源:report_ecXaL6wgzTYuyE7MtX1AYb1ElrdwlenH8fqZB00Fudhtm4O8lntHlGLLTewvTGIS]
- **数据路径**：LME/Comex `search_global_data`；国产金属价 `search_cn_marketdata`

### 1.4 钢铁
- **高频（周）**：冷轧不锈钢卷价、螺纹钢/线材价格、钢坯库存↓、螺纹钢库存↓、高炉开工率↑、日均铁水产量↑、建筑钢材成交量↑ [来源:report_ecXaL6wgzTYuyE7MtX1AYb1ElrdwlenH8fqZB00Fudhtm4O8lntHlGLLTewvTGIS]
- **中频（月）**：黑色金属矿采选PPI同比↑、粗钢产量 [来源:report_ecXaL6wgzTYuyE7MtX1AYb1ElrdwlenH8fqZB00Fudhtm4O8lntHlGLLTewvTGIS]

### 1.5 基础化工
- **高频（周）**：纯碱期货价、磷酸二铵现货价、纯苯现货价、丁苯橡胶经销价、PTA产业链(江浙织机)开工率↑、氯化钾价格、TDI/MDI价格 [来源:report_ecXaL6wgzTYuyE7MtX1AYb1ElrdwlenH8fqZB00Fudhtm4O8lntHlGLLTewvTGIS]
- **中频（月）**：间苯二酚出口均价、TDI华东市场价、化学原料及制品PPI同比 [来源:report_ecXaL6wgzTYuyE7MtX1AYb1ElrdwlenH8fqZB00Fudhtm4O8lntHlGLLTewvTGIS]

### 1.6 建筑材料
- **高频（周）**：水泥价格指数、浮法玻璃均价及产能利用率↑、玻璃库存↓、南华玻璃指数、建筑五金价格指数、混凝土搅拌站运转率↑ [来源:report_ecXaL6wgzTYuyE7MtX1AYb1ElrdwlenH8fqZB00Fudhtm4O8lntHlGLLTewvTGIS]
- **中频（月）**：水泥产量(当月值)、平板玻璃产量 [来源:report_ecXaL6wgzTYuyE7MtX1AYb1ElrdwlenH8fqZB00Fudhtm4O8lntHlGLLTewvTGIS]

---

## 二、中游板块（制造 · 强PMI/工业增加值敏感，信号最强）

景气判断核心：**产销量同比、开工率、订单、出口数量/单价、投资完成额**。

### 2.1 机械设备
- **高频（周）**：机械设备价格指数(鼓风机等) [来源:report_ecXaL6wgzTYuyE7MtX1AYb1ElrdwlenH8fqZB00Fudhtm4O8lntHlGLLTewvTGIS]
- **中频（月）**：**挖掘机销量(国内/出口/合计当月值)同比↑**（核心，工程机械景气标杆）、重卡销量当月值同比↑、不锈法兰出口数量、动车组产量、自动化设备/通用设备产销 ；制造业PPI同比
- **业务洞察**：用户重点关注的工程机械出海——需拆分"挖掘机出口当月值同比"单独跟踪，验证出海逻辑真伪 

### 2.2 电力设备（含光伏/锂电/电网）
- **高频（周）**：电解液(锰酸锂)价格、Topcon组件价格↓（价格跌=供给过剩/景气下行）、多晶硅料/电池片/组件价格、磷酸铁锂/负极材料价格、半钢胎/全钢胎开工率 [来源:report_ecXaL6wgzTYuyE7MtX1AYb1ElrdwlenH8fqZB00Fudhtm4O8lntHlGLLTewvTGIS]
- **中频（月）**：**电网基本建设投资完成额累计值↑**（用户重点：电网招投标/特高压景气锚）、太阳能电池(光伏电池)产量当月值、风电装机 [来源:report_ecXaL6wgzTYuyE7MtX1AYb1ElrdwlenH8fqZB00Fudhtm4O8lntHlGLLTewvTGIS]
- **业务洞察**：光伏链价格持续下行=产能过剩、景气低位；电网投资额=逆周期基建景气，二者背离需分开打分

### 2.3 电子
- **高频（周）**：DRAM现货平均价(DDR3/DDR4/DDR5)↑、NAND Flash价、面板价格、费城半导体指数、DXI内存指数 [来源:report_ecXaL6wgzTYuyE7MtX1AYb1ElrdwlenH8fqZB00Fudhtm4O8lntHlGLLTewvTGIS]
- **中频（月）**：无线耳机出口数量及单价、全球半导体销售额↑、集成电路产量、智能手机出货量 [来源:report_ecXaL6wgzTYuyE7MtX1AYb1ElrdwlenH8fqZB00Fudhtm4O8lntHlGLLTewvTGIS]

### 2.4 通信
- **中频（月）**：移动通信基站设备产量累计值↑、光缆产量、电信业务总量累计同比、光模块出口

### 2.5 国防军工
- **中频（月）**：全球新承接订单量(修正总吨)当月值（造船）、军工企业合同负债/存货

### 2.6 汽车
- **高频（周）**：汽车轮胎(半钢胎/全钢胎)开工率↑、乘用车零售/批发周度数据 [来源:report_ecXaL6wgzTYuyE7MtX1AYb1ElrdwlenH8fqZB00Fudhtm4O8lntHlGLLTewvTGIS]
- **中频（月）**：汽车产量当月值、新能源汽车产销量同比↑、汽车制造业PPI同比

### 2.7 轻工制造
- **中频（月）**：造纸和纸制品业利润总额累计同比、白卡纸价格指数、建材家具景气、义乌小商品价格指数 [来源:report_ecXaL6wgzTYuyE7MtX1AYb1ElrdwlenH8fqZB00Fudhtm4O8lntHlGLLTewvTGIS]

---

## 三、下游板块（消费 · 强CPI/社零敏感）

景气判断核心：**销量/动销同比、CPI分项、出口金额、价格、客流量**。

### 3.1 食品饮料
- **中频（月）**：调味品/发酵制品制造PPI当月同比、白酒批价(飞天茅台/普五)、啤酒销量、食品饮料制造业景气 [来源:report_ecXaL6wgzTYuyE7MtX1AYb1ElrdwlenH8fqZB00Fudhtm4O8lntHlGLLTewvTGIS]
- **业务洞察**：用户近期关注啤酒——需跟踪啤酒产量当月值同比、餐饮渠道动销、旺季气温

### 3.2 农林牧渔
- **高频（周）**：鲫鱼/猪肉/鸡苗平均批发价、生猪价格、玉米/豆粕饲料价 [来源:report_ecXaL6wgzTYuyE7MtX1AYb1ElrdwlenH8fqZB00Fudhtm4O8lntHlGLLTewvTGIS]
- **中频（月）**：能繁母猪存栏数同比（猪周期核心，领先生猪供给约10个月）、生猪出栏量

### 3.3 家用电器
- **高频（周）**：照明用具/灯具价格指数 [来源:report_ecXaL6wgzTYuyE7MtX1AYb1ElrdwlenH8fqZB00Fudhtm4O8lntHlGLLTewvTGIS]
- **中频（月）**：**家电出口金额当月同比↑**（外需景气）、空调/冰箱/厨电产量及内外销同比、白电排产

### 3.4 医药生物
- **高频（周）**：成都中药材价格指数、中药材价格 [来源:report_ecXaL6wgzTYuyE7MtX1AYb1ElrdwlenH8fqZB00Fudhtm4O8lntHlGLLTewvTGIS]
- **中频（月）**：中药CPI、医药制造业PPI、集采降价影响

### 3.5 商贸零售 / 社会服务
- **高频（周）**：航司执行率(国航等)、地铁客运量、餐饮客流 [来源:report_ecXaL6wgzTYuyE7MtX1AYb1ElrdwlenH8fqZB00Fudhtm4O8lntHlGLLTewvTGIS]
- **中频（月）**：出口金额累计值、社零当月同比、限额以上餐饮收入当月值 [来源:report_ecXaL6wgzTYuyE7MtX1AYb1ElrdwlenH8fqZB00Fudhtm4O8lntHlGLLTewvTGIS]

### 3.6 美容护理
- **中频（月）**：化妆品类零售额当月值、彩妆/香水/美妆工具过去12个月累计销售额同比 [来源:report_ecXaL6wgzTYuyE7MtX1AYb1ElrdwlenH8fqZB00Fudhtm4O8lntHlGLLTewvTGIS]

### 3.7 纺织服饰
- **高频（周）**：柯桥纺织指数(坯布类价格)、中国轻纺城成交量、涤纶长丝下游织机开工率↑ [来源:report_ecXaL6wgzTYuyE7MtX1AYb1ElrdwlenH8fqZB00Fudhtm4O8lntHlGLLTewvTGIS]
- **中频（月）**：纺织制造出口、服装产量

### 3.8 传媒
- **中频（月）**：电影票房收入当月值及过去12个月累计同比↑、游戏版号数量、广告刊例 [来源:report_ecXaL6wgzTYuyE7MtX1AYb1ElrdwlenH8fqZB00Fudhtm4O8lntHlGLLTewvTGIS]

---

## 四、金融房建板块

### 4.1 房地产
- **高频（周）**：30大中城市商品房成交面积↑、二手房成交面积、土地成交面积 [来源:report_ecXaL6wgzTYuyE7MtX1AYb1ElrdwlenH8fqZB00Fudhtm4O8lntHlGLLTewvTGIS]
- **中频（月）**：商品房销售面积累计同比、地产开发投资完成额累计同比、新开工面积、房企到位资金

### 4.2 银行
- **高频（周）**：温州民间融资综合利率(小额贷款)、票据贴现利率 [来源:report_ecXaL6wgzTYuyE7MtX1AYb1ElrdwlenH8fqZB00Fudhtm4O8lntHlGLLTewvTGIS]
- **中频（月）**：社融/信贷投放、净息差、不良率

### 4.3 非银金融（证券/保险）
- **高频（周）**：两市成交额↑、两融余额↑、10年国债到期收益率 [来源:report_ecXaL6wgzTYuyE7MtX1AYb1ElrdwlenH8fqZB00Fudhtm4O8lntHlGLLTewvTGIS]
- **中频（月）**：保费收入累计同比、新增投资者数

### 4.4 建筑装饰
- **中频（月）**：中国电建/中国中铁新签合同额累计值↑、基建投资累计同比 [来源:report_ecXaL6wgzTYuyE7MtX1AYb1ElrdwlenH8fqZB00Fudhtm4O8lntHlGLLTewvTGIS]

---

## 五、支持服务板块

### 5.1 交通运输
- **高频（周）**：北京/主要城市地铁客运量↑、CCFI/SCFI出口集装箱运价指数↑、BDI干散货运价、快递业务量 [来源:report_ecXaL6wgzTYuyE7MtX1AYb1ElrdwlenH8fqZB00Fudhtm4O8lntHlGLLTewvTGIS]
- **中频（月）**：货运量、港口吞吐量、快递收入增速

### 5.2 公用事业（电力/燃气）
- **高频（周）**：IPE英国天然气期货价、NYMEX天然气价、发电耗煤、电厂日耗 [来源:report_ecXaL6wgzTYuyE7MtX1AYb1ElrdwlenH8fqZB00Fudhtm4O8lntHlGLLTewvTGIS]
- **中频（月）**：发电量当月值同比↑、用电量、AI算力(token需求)拉动的电力需求 

### 5.3 环保
- **高频（周）**：碳市场碳排放配额(CEA)成交金额/价格 [来源:report_ecXaL6wgzTYuyE7MtX1AYb1ElrdwlenH8fqZB00Fudhtm4O8lntHlGLLTewvTGIS]

---

## 六、数据获取路径速查

| 指标类型 | 首选工具 | 说明 |
|---|---|---|
| 国内大宗价格/产量/开工率/库存（时序） | `search_cn_marketdata` | 行业聚合、工业品价格、产销库存 |
| 宏观与行业月度指标（PPI/PMI/社零/发电量/挖机销量等） | `delegate_to_agent(data_analyst)` 走 EDB 引擎 | 标准口径，支持同比环比 |
| 海外价格（原油/LME/Comex/费半/海运价） | `search_global_data`（先 read_skill） | 全球标的 |
| 同比/环比/分位数/扩散指数计算 | `delegate_to_agent(data_analyst)` | 不要用 search_*_marketdata 计算 |
| 各行业指标定义/景气解读/分析师观点 | `search_paipai` + `doc_searcher` | 研报/纪要 |

> **注意**：本字典为指标"全集"。实际跟踪时按目标行业按需调用，不必每次全跑。
