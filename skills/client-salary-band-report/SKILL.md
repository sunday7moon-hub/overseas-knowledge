---
name: client-salary-band-report
description: '[EN] Generate overseas salary band analysis reports. Covers job doc reading, macro research, multi-source verification, GROSS/NET conversion, forex, reportlab PDF. / [CN] 生成海外招聘岗位薪资带宽分析报告。覆盖读取文档、薪资研究、多源验证、GROSS/NET换算、reportlab PDF。'
agent_created: true
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

**核心原则：** 用英国岗位名称在目标国本地薪资平台检索。可信度排序：

| 数据源 | 类型 | 币种 | 可信度 |
|--------|------|------|:------:|
| ElemanBuldum.com | 土耳其员工自报薪资 | **NET税后**，需换算GROSS(×1.30) | ⭐⭐⭐⭐⭐ |
| Wide and Wise | 咨询公司指南 | GROSS税前 | ⭐⭐⭐⭐ |
| WorldSalaries.com | 跨国薪资聚合 | GROSS税前 | ⭐⭐⭐ |
| SalaryExpert/ERI | 薪资研究机构 | GROSS税前 | ⭐⭐⭐ |
| Invensis Learning | 引用三方数据 | GROSS税前 | ⭐⭐⭐ |
| Kariyer.net | 雇主招聘信息 | GROSS税前 | ⭐⭐⭐ |
| Paylab | 匿名调查 | GROSS税前 | ⭐⭐ |
| Payscale/Glassdoor | 全球平台 | GROSS税前 | ⭐⭐（土耳其样本少） |
| 百度AI摘要 | AI聚合 | 不明 | ❌不稳定 |

**关键动作：**
- 按经验层级查找（0-2年 / 2-5年 / 5年+）
- 城市系数调整（伊斯坦布尔+17%）
- 行业系数调整（汽车行业 vs 全行业）
- 跨源交叉验证，取交集区间
- 明确标注所有数字是GROSS还是NET

### Step 4: 数据校准

**Net → Gross 换算：** 土耳其一般税率 $GROSS = NET \times 1.30$

**汇率换算：** 查中国央行中间价（1 TRY = ? CNY），全线加CNY列。

**P百分位定位：**
- P50 = 市场中位数（超过50%候选人）
- P60 = 前40%（薪资有竞争力）
- P75 = 前25%（高位薪酬，可抢稀缺人才）

### Step 5: 撰写分析框架

标准框架（按需调整）：

1. **宏观经济参数**（生活成本、最低工资、雇主成本）
2. **分析维度框架**（岗位对标、技术溢价逻辑）
3. **岗位薪资建议**（每岗GROSS/NET/CNY三列 + P定位）
4. **竞品在招对比**（同区域竞品薪资vs Habas建议）
5. **候选人预期分析**（薪资预期 + 非薪资关注点）
6. **招聘策略建议**（差异化卖点 → 话术方向）

### Step 6: 客户版敏感内容过滤

**必须删除的内容：**
- ❌ 候选人年龄/性别限制
- ❌ 客户品牌劣势/弱点讨论
- ❌ 内部数据源引用（交给"免责说明"一句话带过）
- ❌ 内部招聘周期/Timeline细节

**必须替换的内容：**
- "劣势 → 弥补方案" 改为 "维度 → 核心卖点"
- 负面表述改为正面呈现

### Step 7: PDF生成

**macOS 上用 reportlab platypus + CID中文字体：**
- 字体：`UnicodeCIDFont('STSong-Light')`（内置CID，无需外部字体文件）
- 注意：**不要使用** `<b>` 标签（CID字体无bold变体，渲染会错位）
- 用 Paragraph 组件包装所有表格单元格，确保自动换行
- 用 TableStyle 控制列宽、配色、行列背景

**配置参数：**
```python
pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
ch = ParagraphStyle('ch', fontName='STSong-Light', fontSize=9.5, ...)
cs = ParagraphStyle('cs', fontName='STSong-Light', fontSize=9.5, ...)
```

**配色方案（深蓝主色）：**
- PRIMARY = #1a365d（标题）
- ACCENT = #c53030（强调/红色）
- TEXT_DARK = #000000（正文-纯黑，不用深灰）
- TEXT_MUTED = #4a5568（次要）

**水印添加：**
- 用 PyPDF2 + reportlab canvas 在 PDF 上叠加水印层
- `c.setFillAlpha(0.12)` 控制透明度
- 每页3处斜排（居中 + 左上 + 右下）
- 独立保存为 `*_水印版.pdf`

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
