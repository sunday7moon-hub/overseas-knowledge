---
name: client-salary-band-report
description: "[EN] Generate overseas salary band analysis reports. Covers job
  doc reading, macro research, multi-source verification, GROSS/NET conversion,
  forex, reportlab PDF. / [CN]
  生成海外招聘岗位薪资带宽分析报告。覆盖读取文档、薪资研究、多源验证、GROSS/NET换算、reportlab PDF。"
agent_created: true
disable-model-invocation: true
---

# 客户招聘-岗位薪酬带宽报告

## Overview

为客户的海外招聘岗位（土耳其等新兴市场）生成专业薪资分析报告，输出格式包含 MD 和 PDF。主打**先分析后产出、先校准后交付**的工作流。

### 典型触发场景
- "帮我分析XX国家XX岗位的薪资"
- "这个岗位的薪资带宽应该是多少"
- "出一份薪资分析报告，给客户看的"
- "土耳其伊斯坦布尔的生产组长岗位薪资报告"

---

## Workflow

### Step 1: 读取岗位文档

读取客户提供的岗位文档（docx/PDF），提取：
- 岗位名称（中文 + 英文）
- 工作地点（城市/国家）
- 岗位职责与技术要求
- 经验/学历要求
- 证书/技能关键词（如机器人品牌、质量体系）

**关键动作：** 确认英文岗位名称（如 Team Leader / Production Team Leader / Shift Supervisor），后面搜索用英文名。

**注意客户自报价：** 客户可能已给出期望薪资区间（如"月薪3.5-7万""年薪60-150万"）。**不要直接照搬**，需在报告中单独一节"客户自报价 vs 市场校准"对比验证——报价合理则确认，偏低/偏高则给出修正建议（华伽案例：客户报价下限 $88K 低于市场 P25 $130K，需上调）。

### Step 2: 研究宏观经济参数

搜索目标国家的以下数据（以土耳其为例）：

| 维度 | 搜索关键词 |
|------|-----------|
| 人均GDP/人均可支配收入 | Turkey GDP per capita 2026 |
| 最低工资 | Turkey minimum wage 2026 gross net |
| 平均薪资/城市差异 | Istanbul average salary 2026 |
| 通胀率/失业率 | Turkey inflation 2026 unemployment |
| 生活成本 | Istanbul cost of living monthly |
| 雇主成本系数 | Turkey employer social security cost 2026 |
| 汇率 | TRY to CNY / TRY to USD |

**注意事项：**
- 区分 GROSS（税前）和 NET（税后），ElemanBuldum 数据默认是 NET
- 明确标注各数据的币种和税前/税后
- 人均GDP替换为人均可支配收入（更贴近民生感受）

### Step 3: 英文岗位交叉验证薪资数据

**核心原则：** 用英文岗位名称在目标国本地薪资平台检索。可信度排序：

| 数据源 | 类型 | 币种 | 可信度 |
|--------|------|------|:------:|
| Paylab.com | 目标国员工自报薪资 | 按国别标注，**默认GROSS** | ⭐⭐⭐⭐⭐（非洲/新兴市场首选） |
| ElemanBuldum.com | 土耳其员工自报薪资 | **NET税后**，需换算GROSS(×1.30) | ⭐⭐⭐⭐⭐ |
| WorldSalaries.com | 跨国薪资聚合（岗位细分） | GROSS税前 | ⭐⭐⭐⭐ |
| SalaryExpert/ERI | 薪资研究机构 | GROSS税前 | ⭐⭐⭐⭐ |
| Payscale | 全球平台 | GROSS税前 | ⭐⭐⭐（新兴市场样本少） |
| 本地招聘平台（Kariyer.net等） | 雇主招聘信息 | GROSS税前 | ⭐⭐⭐ |
| Wide and Wise | 咨询公司指南 | GROSS税前 | ⭐⭐⭐ |
| **AfricaCarrieres 及法语/泛非求职网站** | 行业档位表 | GROSS | ❌❌ **高危虚高源** |
| 中文自媒体/贴吧文章 | 经验分享 | 不明 | ❌不稳定 |
| 百度AI摘要 | AI聚合 | 不明 | ❌不稳定 |

**⚠️ 高危数据源警告（真实教训）：**
- **AfricaCarrieres 等法语/泛非求职网站的"行业档位表"严重虚高**（曾把博茨瓦纳工程师写成 Senior P45-80K/月，真实市场仅 P8.7K-11.5K/月，虚高约4倍）
- 原因：这类网站把外资矿业巨头（Debswana、Anglo 等）的**顶薪**当成普遍水平，且数据陈旧
- 中文自媒体文章（如"到XX国打工年薪百万"）同样严重虚高，只可作上限参考，不可作基准
- **判断方法：** 若某来源的 Senior 档薪资超过该国平均工资的 6-8 倍以上，基本可判定虚高，须降级或弃用

**关键动作：**
- 按经验层级查找（0-2年 / 2-5年 / 5年+）
- 城市系数调整（如伊斯坦布尔+17%、哈博罗内+20-40%）
- 行业系数调整（矿业/金融 vs 全行业）
- 跨源交叉验证，取交集区间
- 明确标注所有数字是GROSS还是NET
- **新兴市场（尤其非洲）优先用 Paylab 员工自报的 80% 区间**（P10-P90），最贴近真实

### Step 4: 数据校准

**Net → Gross 换算：** 土耳其一般税率 $GROSS = NET \times 1.30$

**汇率换算：** 查中国央行中间价（1 TRY = ? CNY），全线加CNY列。

**P百分位定位：**
- P50 = 市场中位数（超过50%候选人）
- P60 = 前40%（薪资有竞争力）
- P75 = 前25%（高位薪酬，可抢稀缺人才）

### Step 5: 撰写分析框架

标准框架（按需调整）：

0. **客户自报价 vs 市场校准**（若客户给了报价）：对比表 + 修正建议（下限偏低上调/上限虚高下调）
1. **宏观经济参数**（生活成本、最低工资、雇主成本）
2. **分析维度框架**（岗位对标、技术溢价逻辑、语言要求、驻地）
3. **岗位薪资建议**（每岗GROSS/NET/CNY三列 + P定位）
4. **竞品在招对比**（同区域竞品薪资vs客户建议）
5. **候选人预期分析**（薪资预期 + 非薪资关注点）
6. **招聘策略建议**（差异化卖点 → 话术方向）

**多国别/多岗位处理（赛迪案例）：**
- 一国多岗：每岗独立小节（建议薪资+锚点），最后加"对比一览表"
- 一岗多国：每国独立小节 + 横向对比表（注意锚点倍数按各国社评工资分别计算）
- 分候选人来源定价：本地人/华裔/外派等分档（科脉案例：三语本地人 RM6-8.5K、华裔 RM6.5-9K、仅双语 RM5-6.5K、中国外派另议）
- 语言要求是核心溢价项：三语（中英+当地语）> 双语 > 单语，报告要单列"语言要求"维度

### Step 6: 客户版敏感内容过滤

**必须删除的内容：**
- ❌ 候选人年龄/性别限制
- ❌ 客户品牌劣势/弱点讨论
- ❌ 内部数据源引用（交给"免责说明"一句话带过）
- ❌ 内部招聘周期/Timeline细节

**必须替换的内容：**
- "劣势 → 弥补方案" 改为 "维度 → 核心卖点"
- 负面表述改为正面呈现

### Step 7: 发布前薪资数据自校验（强制 Gate，不可跳过）

> **核心规则：** 每次交付 PDF 前，必须对每条薪资建议做"合理性校验"。**合理则保留，不合理必须重新输出修正版**，不允许带着存疑数据发布。

**校验清单（每岗逐项核对）：**

| # | 校验项 | 判定标准 | 不通过时的动作 |
|---|--------|---------|--------------|
| 1 | **对比权威基准** | 建议薪资与 Paylab/WorldSalaries 同岗数据区间有重叠或合理上浮（≤60%） | 重查数据，重新校准 |
| 2 | **锚点合理性** | 建议薪资 ÷ 该国社评平均工资 = **1.5-6倍**（新兴市场）| 若 >8倍 → 基本可判定数据虚高，重查 |
| 3 | **国家间横向对比** | 同岗相邻国家薪资不应相差 3 倍以上（经济水平相近时） | 排查是否有虚高/虚低源 |
| 4 | **与最低工资倍数** | 建议薪资 ÷ 法定最低工资月化 = 合理倍数（2-15倍视行业而定） | 极端值需复核 |
| 5 | **数据源交叉** | 每条建议至少 2 个独立来源支撑（其中 1 个为员工自报类） | 补搜索 |
| 6 | **汇率核对** | 汇率取当日央行中间价，CNY 换算无笔误（抽查 1-2 个计算） | 重算 |
| 7 | **客户自报价 vs 市场**（若适用） | 客户报价下限 ≥ 市场 P25，上限 ≤ 市场 P90；偏低则上调、偏高则下调 | 报告修正建议并说明依据 |

**必须重新输出的场景（硬性触发）：**
- ❌ 任何来源标记为"高危虚高源"（AfricaCarrieres/中文自媒体）且未修正
- ❌ 建议薪资超过该国平均工资 8 倍以上（无特殊溢价理由）
- ❌ 相邻国家同岗薪资差异 >3 倍（无汇率/税制重大差异解释）
- ❌ 用户或内部复核提出质疑 → **必须重新核查并输出修正版**

**输出前最后动作：**
1. 复核报告中是否残留已弃用的数据源引用（从数据源清单删除）
2. 用 PyMuPDF 渲染 PDF 各页为图片，检查无错位/截断/乱码（渲染环境：`/Users/yoyo/.workbuddy/binaries/python/envs/default/bin/python3` + `fitz`）
3. 汇报时向用户说明：数据源、校验结论（合理/修正）、修正内容

### Step 8: PDF生成

**macOS 上用 reportlab platypus + SimHei黑体（清晰度优先）：**
- 字体：`TTFont('SimHei', '.../fonts/SimHei.ttf')`（下载自 https://github.com/StellarCN/scp_zh/raw/master/fonts/SimHei.ttf）
- **⚠️ 字体必须持久化到工作目录 `fonts/SimHei.ttf`，不要放 /tmp**（/tmp 被系统清理后脚本全部失效，2026-08 真实教训）
- 正文纯黑 #000000、字号 10-11pt，表格 9.5-10pt
- 用 Paragraph 组件包装所有表格单元格，确保自动换行
- 用 TableStyle 控制列宽、配色、行列背景
- 标题不用 `<b>` 加粗（SimHei无bold变体），用大号字体替代

> 💡 **2026-08 抽离独立 skill `pdf-report-layout`**：上述排版规范 + 水印 + 校验已沉淀为可复用函数库（`scripts/report_starter.py`）。新报告直接 `from report_starter import setup_font, base_styles, table_style_factory, make_table, add_watermark, validate_pdf` 即可，不必从零写 boilerplate。

**表格排版四件套（必须全配齐，缺一风格不统一）：**
```python
('ALIGN',(0,0),(-1,0),'LEFT'),          # 表头左对齐
('VALIGN',(0,0),(-1,-1),'TOP'),
('TEXTCOLOR',(0,1),(-1,-1),TEXT_DARK),  # 正文纯黑
('GRID',(0,0),(-1,-1),0.4,BORDER),      # 内网格
('BOX',(0,0),(-1,-1),0.6,PRIMARY),      # 深蓝外框
('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white, ALT_BG]),  # 斑马纹
```

**防排版事故三规则（2026-08 实战沉淀）：**
1. **大表格必须 `KeepTogether(t)` 包裹**——否则跨页切断（PMC行被切到下一页的真实案例）
2. **单元格内容过长用 `<br/>` 强制分3行**（薪资 + CNY + 定位标签各一行），避免单词被拆成"P6"+"5-P80"
3. **T 函数加 `keep_together=False` 参数**，按需启用，不默认全部 KeepTogether

**校验（Step 7 输出前必做）：**
- 用 PyMuPDF 渲染每页为 PNG 检查（`/Users/yoyo/.workbuddy/binaries/python/envs/default/bin/python3` + `fitz`）
- **新版 fitz 用 `page.get_text()`，不是 `extract_text()`**
- 拼接网格图逐页检查：错位/截断/乱码/字叠字

**币种符号兼容层（必须！核心经验）：**
SimHei 和 Helvetica 都只覆盖部分货币符号，缺失时渲染为方块 □：
- SimHei：仅 ASCII，**不含任何货币符号**
- Helvetica(WinAnsi)：仅含 $ ¢ £ ¤ ¥ €，**不含 ₱ ₩ ₹ ₫ ฿ ₺ 等较新符号**

处理策略（通用 fix_currency 函数，所有内容经它处理）：
```python
# 1. 非WinAnsi币种符号 -> ISO 4217 代码（任何字体都能显示）
CURRENCY_FALLBACK = {'₱':'PHP','₩':'KRW','₹':'INR','₫':'VND','฿':'THB','₺':'TRY',
                     '₴':'UAH','₪':'ILS','₦':'NGN','₸':'KZT','₽':'RUB','₼':'AZN',
                     '₾':'GEL','₲':'PYG','₡':'CRC','₨':'PKR','₮':'MNT','₣':'CHF','₿':'BTC'}
# 2. WinAnsi安全符号 -> Helvetica font tag
LATIN_SAFE = ['$','£','¥','€','¢']
for sym in LATIN_SAFE:
    text = text.replace(sym, f'<font face="Helvetica">{sym}</font>')
# 3. 特殊标点（— – ·）同样切 Helvetica
```

**水印添加：**
- 用 PyPDF2 + reportlab canvas 叠加水印层
- **水印字体必须用 SimHei**（Helvetica 不含中文，会显示方块）
- `c.setFillAlpha(0.12)` 控制透明度
- 每页3处斜排（居中 + 左上 + 右下）
- 独立保存为 `*_水印版.pdf`，水印文字"品牌名 日期"

---

## 输出产物

| 文件 | 用途 |
|------|------|
| `Habas_报告_客户版.pdf` | 无水印客户版 |
| `Habas_报告_客户版_水印版.pdf` | 带"品牌名 日期"水印 |
| `Habas_报告.md` | 可编辑源文档 |

---

## 注意事项

1. **币种声明必须明确：** 全文标注 GROSS税前 / NET税后，不可混淆
2. **汇率注明日期和来源：** "2026年X月X日央行中间价 1 TRY=? CNY"
3. **数据源说明：** 客户版文中不展开，在免责说明中带过即可
4. **表格列宽：** 4列表格用 [0.20, 0.35, 0.28, 0.17]，避免字叠字
5. **标题不加粗：** CID字体不支持 `<b>`，直接用大号字体替代
6. **封面布局：** 用 Spacer 管理间距，不依赖 spaceAfter
7. **发布前必须过 Step 7 自校验 Gate：** 合理保留、不合理重出，绝不允许带疑数据交付
8. **新兴市场数据源优先序：** Paylab（员工自报80%区间）> WorldSalaries > 本地招聘平台 > 咨询指南 > Payscale；**非洲国家严禁直接采信法语/泛非求职网站的行业档位表**
9. **踩坑备忘（2026-08 实战沉淀）：**
   - **reportlab ParagraphStyle 的 color 必须是 keyword（`color=...`），不能当第 4 个位置参数**——`style("sm", 8, 11, HexColor("#555"))` 会被解释成 `align=HexColor`，触发 `UnboundLocalError: dpl` 崩溃，定位极难。统一写 `style("sm", 8, 11, color=HexColor("#555"))`。
   - **SimHei 字体下载：** GitHub raw (`StellarCN/scp_zh/raw/master/fonts/SimHei.ttf`) 易 RemoteDisconnected。备选 jsdelivr CDN：`https://cdn.jsdelivr.net/gh/StellarCN/scp_zh@master/fonts/SimHei.ttf`（正常 9.7MB；若只有 2MB 多半损坏，重新下）。
   - **水印可走 fitz `page.show_pdf_page` 叠加**（先生成一份低透明 reportlab 水印页 PDF，再 fitz 打开底稿逐页 `show_pdf_page(page.rect, wm_doc, 0)`），比 PyPDF2 路径更稳，且保留矢量文字。
   - **中文段落必须 `wordWrap='CJK'`**；表格数字列宽宁宽勿窄（"1,200,000 - 1,500,000" 约需 95pt+），数字被拆行很丑。
   - **SimHei 缺 • ⚠ ★ → 等符号**：bullet 字符可加到 `LATIN_SAFE` 用 Helvetica 字体包裹渲染；⚠ 等图标直接替换为文字（如"[注意]"）。
   - **汇率取数优先级**：PBOC 中间价 + 银行外汇牌价 + 即期收盘 + 30 日区间，四个数一起列出供客户校准，比单点取数更稳（v1 用 6.82、v2 校准为 6.74 即由此暴露）。
   - **客户自报价必须校准（华伽案例）**：客户给"月薪3.5-7万、年薪60-150万"直接照搬会招不到人——市场 P25 是 $130K base，客户下限 $88K 偏低约 30%。**每次都要做"客户报价 vs 市场"对照表**。
   - **多国别报告锚点分别算**：每个国家的"薪资÷社评工资"倍数按该国自己的社评工资算，不要混用（南非 R48K vs 博茨瓦纳 P12K 完全两个量级）。
   - **新兴市场语言溢价定价**：三语能力（中文+英语+当地语）是稀缺溢价项，按语言能力分档定价并单列（科脉吉隆坡案例：三语本地人 RM6-8.5K vs 仅双语 RM5-6.5K）。
   - **美欧岗位按"总包"报价**：美国电商负责人等岗位，市场习惯报 base + bonus + equity 总包（Director $130-185K base、VP $250K base + $39K bonus），不要只给月薪。
