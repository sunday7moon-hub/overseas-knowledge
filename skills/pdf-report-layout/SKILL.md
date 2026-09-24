---
name: pdf-report-layout
description: 中文/多币种 PDF 报告排版规范与可复用模板（reportlab + SimHei）。当用户需要生成带表格、中文混排、货币符号、水印的客户端交付报告（薪酬带宽、调研报告、商业文档）时使用。沉淀了字体持久化、表格排版四件套、防分页切断、字号/字色规则、PyMuPDF 校验、水印叠加等经实战验证的规范。
---

# PDF 报告排版规范（reportlab + SimHei）

## Overview

本 skill 提供一套在 macOS 上用 `reportlab`（platypus）生成**中文 + 多币种 + 表格密集型**客户端 PDF 报告的标准规范与可复用函数库。所有规则均来自多份真实交付报告（科脉马来西亚、华伽美国薪酬带宽报告等）的踩坑沉淀，目标是：一次成型、排版整齐、无乱码、校验可验证。

适用场景：客户端交付报告、薪酬/调研报告、任何需要"中文 + RM/$/¥ 混排 + 多表格 + 水印"的 A4 PDF。

不适用：纯英文文档、需要复杂图表（用图表 skill）、需要 Word 格式（用 tencent-docx）。

---

## 核心规范（必读）

### 规范 1：字体必须持久化，禁止放 /tmp

`/tmp` 在 WorkBuddy 会话间会被清空，导致二次运行字体缺失报错。字体必须放在**工作目录**下：

```python
import os
FONT_DIR = "/Users/yoyo/WorkBuddy/2026-07-29-13-50-49/fonts"
FONT_PATH = os.path.join(FONT_DIR, "SimHei.ttf")

# 若字体不存在则下载（仅需一次，持久保存）
if not os.path.exists(FONT_PATH):
    os.makedirs(FONT_DIR, exist_ok=True)
    import urllib.request
    urllib.request.urlretrieve(
        "https://github.com/StellarCN/scp_zh/raw/master/fonts/SimHei.ttf", FONT_PATH)

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
pdfmetrics.registerFont(TTFont("SimHei", FONT_PATH))
```

- **SimHei（黑体）** 支持中文 + 拉丁 + 货币符号（RM $ ¥ £ €），渲染清晰，作为默认正文字体。
- SimHei **无 bold 变体**：不要用 `<b>` 加粗（会静默回退或失真）。强调用**大一号字号**或**颜色**（如深蓝标题）替代。
- **兜底字体**：若 SimHei 下载失败，可用系统 `/Library/Fonts/Arial Unicode.ttf`（同样支持 CJK + 货币符号），但风格不如 SimHei 统一。

### 规范 2：表格排版四件套（每个 Table 必备）

任何表格的 `TableStyle` 必须至少包含以下四个命令，缺一不可：

```python
from reportlab.lib import colors
style = [
    ("ALIGN",    (0,0), (-1,-1), "LEFT"),    # 对齐：列0左/数字列RIGHT/CENTER 按内容
    ("BOX",      (0,0), (-1,-1), 0.6, colors.HexColor("#999999")),  # 外框
    ("GRID",     (0,0), (-1,-1), 0.4, colors.HexColor("#CCCCCC")),  # 内网格
    ("TEXTCOLOR",(0,0), (-1,-1), colors.black),  # 文字色（必须显式，默认可能非黑）
    ("FONTSIZE", (0,0), (-1,-1), 9.5),        # 表格字号 9.5-10pt
    ("VALIGN",   (0,0), (-1,-1), "MIDDLE"),
    ("LEADING",  (0,0), (-1,-1), 12),
    ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#F5F7FA")]),  # 隔行底色
    ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#2E5AAC")),  # 表头深蓝底
    ("TEXTCOLOR", (0,0), (-1,0), colors.white),  # 表头白字
    ("TOPPADDING", (0,0), (-1,-1), 4),
    ("BOTTOMPADDING",(0,0), (-1,-1), 4),
]
```

**四件套含义**：`ALIGN`（对齐）+ `BOX`（外框）+ `GRID`（网格）+ `TEXTCOLOR`（字色）。缺任一都会出现"表格有字无框"或"字色发灰看不清"的低级问题。

**补充 1：表头分级 —— 深色表头用少才有力（2026-09-14 全量复盘）**

历史上两种表头做法并存，实测数据（A4 客户版，两方案均达 WCAG AAA）：

| 方案 | 构成 | 文字对比度 | 与斑马纹行灰度差 |
|---|---|---|---|
| 浅底表头（历史方案，已弃用） | `#edf2f7` 底 + 深蓝字 | 10.78 : 1 | **8.3 / 255**（肉眼难辨） |
| 深底表头（现行） | `#1f4f8f` 底 + 微冷白 `#eef2f8` 字 | 8.16 : 1 | **177.4 / 255** |

**结论：对比度不是决定项（两者都 AAA），决定项是「分界强度」。** 浅底 `#edf2f7` 与斑马纹浅行 `#f7fafc` 亮度比仅 1.079，在打印、水印叠加、低质量屏幕上表头会与首行数据糊成一片；深底方案亮度比 26.09，绝对清晰。**因此表头一律用深色。**

**2026-09-14 Yoyo 定：表头底色 = 章标题色 = KV 标签字色 = `#1f4f8f`（S2 品牌交互蓝）**，全份只留一档蓝，不再出现「表头中蓝 + 章标题最深蓝」两档并存。落地方式：只改公共库 `PRIMARY` 一处字面量（`cowave_v2_build.py` / `kam263_sg_build.py`），所有 `import PRIMARY` 的报告脚本与 `T()` 默认 `header_bg` 自动跟随——**不要**在报告脚本里另写死一个独立表头色。

但前提是——**深色表头只能给「有真列名的数据表」用**，滥用会毁掉页面节奏：

| 表类型 | 判定 | 表头方案 |
|---|---|---|
| **数据表** | 首行是多列列名（驻地 / 月度总包 / 成本指数…） | 深底 `#1f4f8f` + 微冷白字 |
| **键值表** | 「标签—值」两列，或首行是"维度\|内容""来源\|内容"这类**零信息量伪表头** | **不给深色表头**：删掉伪表头行，首列改浅底 `#edf2f7` + 深蓝字，值列白底 |

**踩坑记录**：旧 `cover()` 直接 `T(meta, ...)`，导致封面元信息表的**首行「报告日期」被当成表头染成深蓝** —— 语义上它是数据，视觉上却变成一个突兀的深色块。一份 6 页报告原本有 ~12 个深色块，优化到 4 个（只留总览表 / 决策矩阵 / 方案表 / 汇率表），深色才重新变成"锚点"而不是"底噪"。

```python
def KV(rows, cw=None, label_bg=LIGHT_BG):
    """键值表（标签—值）：不给深色表头，首列浅底 + 深蓝字。"""
    ...
    ('BACKGROUND',(0,0),(0,-1),label_bg), ('TEXTCOLOR',(0,0),(0,-1),PRIMARY),
    ('BACKGROUND',(1,0),(-1,-1),colors.white), ('TEXTCOLOR',(1,0),(-1,-1),colors.black),
    ('BOX',(0,0),(-1,-1),0.6,BORDER),   # 键值表外框用浅灰，不用深蓝
```

**配套微调三则**（与深底表头同时生效）：
1. 表头字号 **9.5pt**，数据行 9pt —— 同字号只靠颜色区分，标题感不足；
2. 表头字色用 **`#eef2f8` 微冷白**，纯白压在深蓝上长时间阅读有光晕感；
3. 表头上下 padding **5.5**（数据行 4）—— 深色块需要更多呼吸，否则文字像被压在色块里。

已落地于 `cowave_v2_build.py`（`T()` / `KV()`，控维与拓米洛共用）、`kam263_sg_build.py`（同名副本）。

**补充 1 续：表头深色的可选色阶与硬下限（2026-09-14 实测）**

表头深色不是只能锁定一个色值。在「白字压深底」的前提下，底色越浅页面越轻，但白字对比度同步下降——这是可量化的取舍，不要凭感觉调：

| 档位 | 色值 | 白字压底对比度 | WCAG | 分界强度 |
|---|---|---|---|---|
| 最深藏蓝（2026-09-14 前的旧默认，已弃用） | `#1a365d` | 12.14 | AAA | 199.3 |
| **品牌交互蓝（现行默认）** | `#1f4f8f` | 8.16 | AAA | 177.4 |
| 品牌亮蓝 | `#0052a3` | 7.68 | AAA | 182.6 |
| 中亮蓝 | `#2b5fa8` | 6.35 | 仅 AA | 161.6 |
| 中亮蓝·更浅 | `#3b74c4` | 4.69 | 仅 AA（临界） | 141.3 |
| 品牌渐变蓝（偏紫） | `#1c398e` | 10.37 | AAA | 191.3 |

「分界强度」= 表头底与斑马纹行 `#f7fafc` 的灰度差（0-255），≤3 肉眼难辨。

**硬下限：白字压底对比度 ≥ 7.0（AAA）**，换算成底色相对亮度即 **≤ 0.10**。
`#2b5fa8`（6.35）与 `#3b74c4`（4.69）不达 AAA——彩色打印、复印、投影、廉价屏幕上笔画会发糊，**客户交付件禁用**。

**连带约束（易踩，已按此决策）**：KV 标签字色跟着换成同一档新色时，必须重算**浅底**对比度——
`#1f4f8f` 在 `#edf2f7` 上为 7.25（刚好保住 AAA），`#0052a3` 只有 6.81（跌到 AA）。
本次选 S2 的一个原因就是它在浅底上仍守得住 AAA；**若将来再换色，先重算浅底对比度，不达标就只能表头/标签字分色（破坏单一蓝的整洁性）。**

调色方法（下次换色直接复用）：monkey-patch `T()` 的 `header_bg` + `B.PRIMARY` / `V.PRIMARY` + h1/h2/ch 的 `textColor`，再把 `out_path` 指向 `/tmp`、`make_watermark` 换成 `shutil.copy`，即可跑出整档**真实排版**对比图，不污染交付件。
**选色量化门槛：白字压底对比度 ≥ 7.0（AAA）且分界强度 ≥ 170。** 一次对比图 + 一次封面/正文实拍确认即可定色，不必反复来回。

**补充 2：SPAN 合并单元格要去掉穿过的横线（2026-09 实测）**

同一方案占两行（如"成本优先型"并列哈萨克/印尼两个驻地）时，用 SPAN 合并：
```python
("SPAN", (0,3), (0,4)), ("SPAN", (3,3), (3,4)), ("SPAN", (4,3), (4,4)),
# GRID 画的横线仍会穿过合并区 —— 用白色线覆盖（色值与背景一致即隐形）
("LINEBELOW", (0,3), (0,3), 0.8, colors.white),
("LINEBELOW", (3,3), (3,3), 0.8, colors.white),
("LINEBELOW", (4,3), (4,3), 0.8, colors.white),
```
注意：`ROWBACKGROUNDS` 隔行底色在合并区会取左上单元格背景色，白线正好与之匹配。

### 规范 3：防止分页切断（防排版三规则）

长报告经常出现在表格中间或标题与表分离的分页切断。三条规则：

1. **标题与表格绑定**：用 `KeepTogether([heading, table])` 把小节标题和它的表锁在一起。
   ```python
   from reportlab.platypus import KeepTogether
   story.append(KeepTogether([Paragraph("3. 薪资建议", h3), salary_table]))
   ```
2. **长单元格拆行**：单元格内长文本用 `<br/>` 手动拆成 2-3 行，避免单行溢出。
3. **表格函数加 `keep_together` 参数**：自封装的 `make_table()` 默认返回 `KeepTogether` 包裹的流，需要跨页时再传 `keep_together=False`。

4. **⚠️ 排版模式选择（2026-09 卫华报告实测）**：`PageBreak()` 逐章分页 + 每个小节 `KeepTogether` 会**严重膨胀页数**（同一份内容 12 页 → 23 页，且章标题被孤立成空白页）。
   **推荐做法**：只保留封面后的 `PageBreak()`，正文**连续排版**（表格设 `repeatRows=1`，跨页自动重复表头），
   仅用 `sec(标题, [表/callout]) = KeepTogether([标题]+内容)` 绑定小节标题与其内容。
   实测同一份报告压缩到 **10 页**，每页 600–1500 字，无孤立标题、无空白页。

5. **⚠️ 优先用 `keepWithNext` 样式，而不是 `KeepTogether`（2026-09 控维分国别报告实测）**：
   `KeepTogether` 会把整块当成不可分单元，一旦当前页放不下就整体推到下一页，产生大片空白（实测 CSM 报告 7 页 → 12 页）。
   更轻量的做法是给标题样式加 `keepWithNext=1`——标题跟随后续内容，但表格自身仍可分页：
   ```python
   h1k = ParagraphStyle('h1k', parent=h1, keepWithNext=1)
   h2k = ParagraphStyle('h2k', parent=h2, keepWithNext=1)
   story.append(Paragraph('二、中亚', h1k))
   ```
   配套坑：**嵌套 KeepTogether 会击穿外层 keepWithNext 分组**。若表格封装函数（如 `T()`）默认返回 `KeepTogether(table)`，
   外层的 `keepWithNext` 会失效、标题依旧被孤立。做法：给表格函数加 `keep` 参数，正文大表统一传 `keep=False` 返回裸 `Table`。
6. **空白页元凶排查顺序**：章节间强制 `PageBreak()` → 孤立 `KeepTogether` → 章末残留分页符。
   本次两轮修复各消除一个 70%-85% 空白页（客户版 6 页 → 5 页且页页饱满）。
   **原则：地区/章节之间不强制分页，靠 `keepWithNext` + 内容自然流动**；只在封面后分页。

### 规范 4：ParagraphStyle 的 color 必须 keyword

`ParagraphStyle` 构造时 `color` 传**关键字参数**，不要位置传参，否则新版 reportlab 会报错或字色异常：

```python
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
style = ParagraphStyle(
    "body", fontName="SimHei", fontSize=10, leading=15,
    color=colors.black,        # ✅ keyword
    # color=colors.black       # ❌ 位置传参会乱
)
```

### 规范 5：数字列宽宁宽勿窄

含金额/区间的数字列（如 `RM6,000-8,500`、`¥100万-180万`）宽度 **≥ 95pt**，否则数字会被压缩换行或溢出。经验值：
- 单列金额区间：`95-110pt`
- 三列布局（GROSS / NET / CNY）：总宽 A4 可用约 170mm（≈ 482pt），表头+3列按 `70 + 130 + 130 + 152` 分配。
- 不确定就**加宽**，页面留白比溢出优雅。

**⚠️ 超宽数字的降级排法（2026-09 控维分国别报告实测，长币种必看）：**

当「币种前缀 + 六位以上数字」超出合理列宽时（`KZT 1,160,000–1,810,000` ≈ 105pt；`UZS/IDR` 同量级），
**绝不能让它自动换行**——reportlab 对无空格长串做字符级硬切，会出现
`KZT 1,160,000–1` / `,810,000` 这种把数字劈成两半的事故（kzt/uzs/idr 这类六位以上金额必踩）。

两种降级版式（择一，**全表统一**）：

```python
# 版式 A：双行 —— 本币单独一列，¥/$ 合并一列分两行（适合 6 列表）
def CU2(lo, hi, cur):
    return f"{Cr(lo,hi,cur)}<br/>{Ur(lo,hi,cur)}"       # ¥57,478–¥71,848 / $8,474–$10,592

# 版式 B：三行堆叠 —— 本币+¥+$ 压在同一格（可把 7 列压到 5 列，窄表首选）
def Mrw(lo, hi, cur):
    return f"{Lr(lo,hi,cur)}<br/>≈{Cr(lo,hi,cur)}<br/>≈{Ur(lo,hi,cur)}"
```

**列宽定法：按该列「最长内容」反推，不是按平均**（含左右 padding 共 10pt）。
例：`KZT 1,160,000–1,810,000` 需 ≈105pt 净宽 → 在 UW≈524pt 下占比 ≈0.22。
驻地名同理：`乌兹别克斯坦` 6 字 = 54pt → 列宽须 ≥64pt 才不换行；放不下就改用短国名。

### 规范 6：多币种处理

- 表格统一三列：`当地币 GROSS` / `当地币 NET` / `约合 CNY`，列名写清币种符号（RM / $ / ¥）。
- 汇率取**当日央行中间价**，在报告"汇率说明"小节列明：来源 + 中间价 + 银行牌价 + 即期收盘 + 30日区间（四个数一起列，比单点取数稳）。
- 换算公式显式写出：`1 MYR = 1.669 CNY`、`1 USD = 6.7854 CNY`，抽查 1-2 个计算无笔误。

**⚠️ 币种符号与字体覆盖（2026-08 真实教训）：**
- SimHei **仅含 ASCII**（`$` 是 ASCII 0x24，可用；`¥` U+00A5 属 Latin-1，**缺失**，直接写会渲染为空/方块）
- 所有 `¥` 必须包 `<font face="Helvetica">¥</font>` 渲染（Helvetica/WinAnsi 含 ¥）；用 `fix_currency()` 统一处理：
  ```python
  def fix_currency(text):
      return text.replace("¥", '<font face="Helvetica">¥</font>')
  ```
- **切 Helvetica 的片段绝不能包含中文**：若把 `¥63.8万` 整段切 Helvetica，"万" 因缺字形会被替换成 `I`（真实事故）。正确写法：`<font face="Helvetica">¥</font>63.8万`——**只包符号，中文/数字留在 SimHei**。

**⚠️ 汇率表必须用高精度格式化，禁止复用薪资的取整函数（2026-09-14 真实事故）：**
- 薪资函数 `C()/U()` 用 `round()` 取整，对「几万」量级无害；但**汇率速查表以 1 单位本币为基数**，套用后小币值全部塌成 0 或个位整数：
  `IDR 1 → ¥0`、`THB 1 → ¥0`、`SGD 1 → ¥5`（应为 ¥5.31）、`USD 1 → ¥7`（应为 ¥6.78）。
  中东版同样中招：`SAR/AED/QAR 1 → ¥2`（应为 ¥1.80/1.84/1.86）。
- 修法：按数量级选小数位的独立函数（`_fx`），**汇率表专属 `Cx()/Ux()`，绝不与 `C()/U()` 混用**：
  ```python
  def _fx(v, sym):
      if v >= 100:  return f"{sym}{v:,.1f}"
      if v >= 1:    return f"{sym}{v:,.2f}"
      if v >= 0.01: return f"{sym}{v:.4f}"
      return f"{sym}{v:.6f}"
  def Cx(amt, cur):  return _fx(amt * RATES[cur][0], '¥')
  def Ux(amt, cur):  return _fx(amt * RATES[cur][1], '$')
  ```
- 交付前用正则扫一遍汇率段：出现 `¥0`、`$0` 或两位以内纯整数即为事故。已沉淀于 `cowave_v2_build.py`（控维/二六三共用）与 `kam263_sg_build.py`。

### 规范 7：水印叠加（唯一交付件 = 客户版 PDF，文件名不带「水印版」）

**命名规范（2026-09-14 Yoyo 定规）**：所有交付件都含水印，因此**文件名不写 `_水印版`**。
交付件形如 `<主体>_<岗位><地区>薪酬带宽报告_客户版.pdf`；`_水印版` / `_内部版` 后缀一律不再使用。

**中间产物必须隔离**：先 build 到 `/tmp/xxx_base.pdf`（无水印），叠加水印后写到交付路径，
**随即删除临时基础版**。工作区曾残留 9 份无水印中间产物，与交付件同名、仅少一层水印——
属**误发风险源**（2026-09-14 全量清理，见 `client-salary-band-report` 门禁 4）。

老脚本若只产无水印版（如早期 `generate_*.py` 一系），须在其输出路径后加**交付件保护门禁**，
已存在即拒绝覆盖：

```python
if os.path.exists(output):
    raise SystemExit(f"⛔ 交付件已存在，拒绝覆盖：{output}\n"
                     "   本脚本仅产无水印版本。确需重制请先移走现有文件，并补加水印后再交付。")
```

水印实现：用 reportlab 画 overlay 再用 PyPDF2 合并：

```python
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
import io
PW, PH = A4
reader = PdfReader(src)
writer = PdfWriter()
for i in range(len(reader.pages)):
    packet = io.BytesIO()
    c = canvas.Canvas(packet, pagesize=A4)
    c.setFillAlpha(0.12)
    c.setFont("SimHei", 32); c.setFillColorRGB(0.78,0.78,0.78)
    c.saveState(); c.translate(PW/2, PH/2); c.rotate(40)
    c.drawCentredString(0, 0, "用友薪福社  2026.08.19"); c.restoreState()
    # 角落再加小字水印两处
    c.save(); packet.seek(0)
    wm = PdfReader(packet).pages[0]
    reader.pages[i].merge_page(wm)
    writer.add_page(reader.pages[i])
with open(dst, "wb") as f: writer.write(f)
```

水印透明度 `setFillAlpha(0.12)`，旋转 40°，主水印居中 + 两角小字，避免遮挡正文。

### 规范 8：发布前校验（必做，Step 8）

生成后必须做图文双校验，不能只看"生成成功"：

```python
import fitz  # PyMuPDF
from PIL import Image
doc = fitz.open(pdf_path)
# 1) 文本校验：关键数字/标题是否正确渲染（新版 fitz 用 get_text 不是 extract_text）
full = "\n".join(page.get_text() for page in doc)
for must in ["¥45,000-75,000", "P65-P85", "6.7854", "TikTok Shop"]:
    assert must in full, f"MISSING: {must}"
# 2) 图像校验：每页渲染成 PNG 拼网格预览肉眼检查排版
os.makedirs("/tmp/check", exist_ok=True)
imgs = []
for i, page in enumerate(doc):
    p = f"/tmp/check/p{i+1:02d}.png"; page.get_pixmap(dpi=110).save(p)
    imgs.append(Image.open(p))
w, h = imgs[0].size
grid = Image.new("RGB", (w*4, h*2), "white")
for i, im in enumerate(imgs):
    grid.paste(im, ((i%4)*w, (i//4)*h))
grid.thumbnail((1700, 900)); grid.save("/tmp/check/all.png")
```

校验要点：① 中文无乱码 ② 表格四件套都在（有框有网有黑字）③ 关键数字正确 ④ 无跨页切断 ⑤ 水印不挡正文。

---

## 品牌报告标准模板（华伽 HUAGIA 格式，2026-08 客户认可样式）

> **重要：** 中企出海薪酬/调研报告请默认采用此模板，不要自行发明样式。华伽报告（generate_huajia_pdf.py）是客户认可的排版基准，263 报告已按此复刻。**完整可运行模板见 `references/brand_template_huajia.py`（华伽原版）与 `references/brand_template_263_example.py`（263 改造示例）。**

### 8 要素清单（逐项核对，缺一不可）

| # | 要素 | 规格 | 错误示例 |
|---|------|------|---------|
| 1 | 品牌主色 PRIMARY | `#1f4f8f` 品牌交互蓝（标题/封面大字/表头底/表格外框）<br>⚠️ 华伽原版为 `#1a365d`，2026-09-14 起统一升级为 `#1f4f8f` | `#2E5AAC` ❌ |
| 2 | 强调红 ACCENT | `#c53030`（封面装饰条实心填充） | 画线 `#B23A2E` ❌ |
| 3 | 表头样式 | **数据表：深底 `#1f4f8f` + 微冷白 `#eef2f8` 字 + `<b>` + 9.5pt**<br>键值表：不给深色表头，首列浅底 `#edf2f7` + `#1f4f8f` 字<br>⚠️ 华伽原版为浅底表头，2026-09-14 起升级（见补充 1） | 深底表头滥用 / 浅底糊成一片 ❌ |
| 4 | callout 框 | `Paragraph` + `backColor=#fff5f5` + `borderWidth=0`（**无边框**，浅红底） | 红边框 Table ❌ |
| 5 | 页眉 | **居中** `drawCentredString(PW/2, PH-12mm)` 8pt `#8899aa` + 下方细线 0.3pt `#e2e8f0`（PH-15mm） | 左对齐 ❌ |
| 6 | 页码 | 底部居中 **"第 X 页"**（`drawCentredString(PW/2, 10mm)` 8pt） | "X / N" ❌ |
| 7 | 边距 | **LM=RM=16mm, TM=BM=22mm**（UW = PW-32mm） | 18/18/22/18 ❌ |
| 8 | 封面结构 | 44pt PRIMARY 英文大写品牌 → 15pt 中文 → 10pt 英文小字 → **实心红条（Table BACKGROUND 2pt, UW×0.4, 居中）** → 24pt 地域大字 → 21pt 报告名 → 11pt 英文副 → 13pt 岗位英文 → 元数据表(2列) | 无红条/黑字 ❌ |

### 其他格式规范（与华伽一致）

- 章节标题 h1：17pt PRIMARY，小节 h2：14pt PRIMARY，正文 bd：11pt，脚注 dc：9pt `#4a5568`
- 表格工厂 T()：表头 `<b>` + ch 样式，GRID 0.4 `#e2e8f0` + BOX 0.6 PRIMARY + 斑马纹（白/`#f7fafc`）
- 表格列宽用 `UW` 比例（如 `[UW*0.30, UW*0.16, ...]`），`keep_together=True` 防跨页
- **防空白页**：`KeepTogether` 大表会整表推页，若独占页太空，需**合并/补表**平衡页内容（263 案例：3.2 分候选人定价表独占 P4 只有 23 行 → 加 3.4 锚点校验表后 47 行，两页都饱满）
- fix_currency：`¥ $ £ € ¢` + `— – ·` 全部切 `<font face="Helvetica">`，CJK 严禁进 Helvetica
- 每页用 `onFirstPage/onLaterPages=page_deco` 统一画页眉页码

### 用模板生成新报告的步骤

1. `cp references/brand_template_huajia.py generate_xxx.py`
2. 只改内容：封面品牌名/地域/岗位、章节标题、表格数据、免责数据源
3. 保留全部样式代码（配色/T()/callout()/page_deco()/fix_currency()）
4. 输出：临时基础版 → `add_watermark` → **唯一交付件** `<主体>_<岗位>薪酬带宽报告_客户版.pdf`（删临时基础版；文件名不带「水印版」）
5. PyMuPDF 校验：页眉页码在、关键数字无乱码、无跨页切断、无独占空白页

---

## 可复用函数库（scripts/report_starter.py）

`scripts/report_starter.py` 封装了上述规范的 boilerplate，新报告直接 `from report_starter import *` 即可：

- `setup_font()` → 返回已注册的 `"SimHei"` 字体名（自动下载持久化）
- `base_styles()` → 返回标题/副标题/正文/表头/小字等一套 ParagraphStyle
- `table_style_factory(header_bg="#2E5AAC")` → 返回规范 2 的排版四件套 + 表头样式
- `make_table(data, col_widths, keep_together=True)` → 返回带样式的 Table（默认 KeepTogether）
- `add_watermark(src, dst, text="用友薪福社  2026.08.19")` → 规范 7
- `validate_pdf(pdf_path, must_contain=[])` → 规范 8 的图文校验，返回 (pages, missing_list)

---

## SimHei 字形能力权威表（2026-09-14 实测，替代所有字形黑名单）

**判据必须是「字体有没有这个字形」，而不是「字符在不在某个黑名单里」。**
用 `fitz.Font(fontfile='fonts/SimHei.ttf').has_glyph(ord(ch))` 实测（返回 0 = 无字形）：

### 三类处置

| 处置 | 字符 | 说明 |
|---|---|---|
| **① SimHei 直接可用** | ``· – — … ‘’“” ° ± × ÷ ≤ ≥ ≈ → ★ ☆ ▲ ● ◆ ■ ※ § € ─ ～ ①…⑩`` ＋全部汉字/中文标点/ASCII/全角 | 无需任何包裹。**★ 在 Helvetica 里没有字形（0）**——所以不能「把所有符号无脑包进 Helvetica」 |
| **② SimHei 无、Helvetica 有 → 包 `<font face="Helvetica">`** | 货币与符号：``¥ £ ¢ $ − • † ‡ ™ © ® ¼ ½ ¾``；**拉丁-1 变音字母**：``À-Þ`` 全部 + ``ß â ã ä å æ ç ë î ï ð ñ ô õ ö ø û ý þ ÿ``；``NBSP(U+00A0)`` | 即 `fix_currency()` / `inline_safe()` 在做的事。**地名/人名重灾区**：``São Paulo`` 的 ``ã``、``Zürich`` 的 ``ü``、``Çanakkale`` 的 ``Ç`` 全在此类，不包必出空框（SimHei 大写 ``À-Þ`` 一颗都没有） |
| **③ 两边都没有 → 禁用** | emoji（``⛔ ✅ ⚠ ⭐ 🔴 📌``…）、**全部非拉丁小币种符号**（``₩ ₺ ₽ ₹ ₦ ₱ ฿ ₫ ₸ ₼ ₾ ₿ ₴ ₲ ₡ ₣ ₨ ₪ ₮ ₵₤ ₧``）、勾选框（``☐ ☑ ✓ ✔ ✗ ✘``）、``❶ ‱ ‴``、Letterlike Symbols（``℀ ℅ ℉ № ℗ Ω ℮``…）、箭头变体（``⇐ ⇑ ⇒ ⇔ ⇧``）与多数数学符号（``∅ ∇ ∊ ⋯``） | **包裹也救不回来**——Helvetica 同样没有字形 |

### ⚠️ 三条反直觉的实测结论

1. **老黑名单在误伤**：`①②③④⑤⑥⑦⑧⑨⑩`（346+）`★`（541）`→`（302）在 SimHei 里**都有字形**，`建议 ①` 这类设计是正常的。
   旧规则「几何符号 `[\u25A0-\u25FF]`、圆圈数字 `[\u2460-\u24FF]` 均需清零」**作废**。
2. **`→ ★ ①` 在 Helvetica 里反而没有（0）** —— 所以**不能无脑把符号包进 Helvetica**（"CJK 及其中文符号严禁进 Helvetica"这条老规则的反向量化版）。
3. **小币种符号是硬禁区**：`₩ ₺ ₽ ₹ ₦ ₱ ฿ ₫` 在 SimHei 与 Helvetica **双方皆无字形**，包了也一样出空框。
   做越南/韩国/土耳其/印度/尼日利亚报告时，**一律写 ISO 代码**（`KRW` / `VND` / `TRY` / `INR` / `NGN`）或中文币名，不要写符号。
   （拓米洛韩国报告用 `KRW` 代码而非 `₩`，所以一直没踩坑——这是对的做法，保持。）

### 空框（tofu）在 PDF 里的真实形态

em 缺字形**不会**在文本层留下 `□`——`□`(U+25A1) 本身是有字形的正常字符（旧规则「`□` 计数必须为 0」因此是错的）。
实测：缺字形渲染出来的是**空框**，文本层对应字符变成 **`U+0000`**。
典型现场：`曼彻斯特␀␀中位（£58K–68K）`（源文写了 `⛔️`，`⛔`+`U+FE0F` 两个码位 → 两个空框）。
→ 所以**必须按字形能力检测，或直接看渲染**；用 emoji 黑名单查是查不到的（它已经变成 NUL 了）。

### 自动化工具

- `~/.workbuddy/skills/pdf-report-layout/scripts/glyph_probe.py`
  - `--chars "−•ãÇ★→₫"`：快速查字符属于哪一类
  - `--table`：打印全量实测能力表（拉丁-1 / 拉丁扩展-A / 标点 / 货币 / 数学 / 符号 / emoji）
  - `--scan <files>`：源文件巡检，列出可能的第③类字符（注释/文档串会误报，默认不阻断）
- `~/.workbuddy/skills/client-salary-band-report/scripts/salary_report_kit.py::preflight_glyphs(story)`
  - **真正的生成前门禁**：扫 story 里「会被 reportlab 渲染」的字符串，只报真实风险
  - 未包 Helvetica 的 ② 类、以及 ③ 类字符 → 直接 `SystemExit`；已在三个骨架接入

---

## 排版速查清单（交付前逐项勾）

- [ ] 字体已持久化到工作目录 `fonts/SimHei.ttf`，未用 `/tmp`
- [ ] 每个表格都含 ALIGN + BOX + GRID + TEXTCOLOR（四件套）
- [ ] **表头已分级**：深底表头只给"有真列名的数据表"；键值表用 `KV()`（浅底标签列），无深色块滥用
- [ ] 标题用 `keepWithNext=1` 样式（而非 `KeepTogether`），大表传 `keep=False`，无孤立标题
- [ ] 数字列宽 ≥ 95pt；长币种（KZT/UZS/IDR 六位以上）已用 `CU2`/`Mrw` 分行，无数字被劈开
- [ ] 章节间无强制 `PageBreak`，无 >40% 空白页；末页饱满（来源附录紧跟结论表）
- [ ] 表格列宽按最长内容反推（驻地名、币种+金额均未换行截断）
- [ ] ParagraphStyle 的 color 用 keyword 传参
- [ ] 强调用字号/颜色而非 `<b>`（SimHei 无 bold）
- [ ] 多币种列名带符号，汇率四数并列 + 换算抽查
- [ ] **唯一交付件**：文件名不含 `_水印版`／`_内部版`；工作区**无无水印残留**（临时基础版已删）
- [ ] 交付件**已叠加水印**（PyMuPDF 扫 `用友薪福社 + 年月` 出现 ≥3 次）
- [ ] PyMuPDF 图文校验通过（关键数字在、无乱码、无切断）
- [ ] **交付前跑一把梭自检**（客户版必做，一条命令替代过去手拼的正则）：
  ```bash
  python skills/pdf-report-layout/scripts/qc_client_pdf.py *_客户版.pdf \
    --color "#1f4f8f" --per-file "中东版.pdf=沙特,以色列,!印度尼西亚"
  ```
  覆盖 10 项：字形能力（根因）/ 替换符 / 客户版禁词 / 交付侧标注 / 水印覆盖 /
  元数据标题 / 页码连续 / 空白页 / 串区关键词 / 主色填充。**有 FAIL 时退出码为 1**，可直接给 A8 QC Agent 调。
  - ⚠️ 字形这一项**不要退回黑名单**：旧规则把 `①②③ ★` 判为非法是误伤，且 emoji 在 PDF 里已变成 `U+0000`、黑名单根本抓不到（详见「SimHei 字形能力权威表」）。
- [ ] **客户可见面 5 处无交付侧标注**（`客户版|客户交付版|内部版|交付侧|底稿`）：
  ①封面副标题 ②封面元信息表（密级行应整行删除）③每页页眉 ④**PDF 元数据标题** ⑤水印文字。
  文件名 `_客户版.pdf` 除外（命名规范，Yoyo 定过）。核查脚本见 `client-salary-band-report` 门禁 7。
- [ ] **PDF 元数据标题非空且不含「客户版」**：`d.metadata['title']` 必须为正式报告名——
  为空时阅读器标签页会退回显示**文件名**（含 `_客户版`），等于把交付侧标注送给客户看。

---

## 环境与踩坑备忘

- **packaging 脚本路径**：`package_skill.py` 当前位于
  `/Users/yoyo/.workbuddy/plugins/cache/workbuddy-builtin/skill-skill-creator/0.1.0/scripts/`
  （旧路径 `/Applications/WorkBuddy.app/.../builtin-skills/skill-creator/scripts/` 已失效）。
- **GitHub 同步**：仓库 `sunday7moon-hub/overseas-knowledge` 已重构为
  `skills/{name}/SKILL.md` + `releases/{name}.zip` 结构。git 大对象传输网络不稳时，
  改用 GitHub API `PUT /repos/{owner}/{repo}/contents/{path}`（先 GET 取 sha 再 PUT），从
  `git credential fill` 读 token。
- **fitz 版本**：新版 PyMuPDF 用 `page.get_text()` 而非 `page.extract_text()`。
- **水印叠加会丢元数据（2026-09-14 实测）**：`make_watermark()` 用 PyPDF2 逐页 `add_page()` 重建文档，
  **源 PDF 的 Info 字典整个丢失** → `title` 为空 → 阅读器标签页退回显示文件名（含 `_客户版`）。
  修法：水印写完后用 PyMuPDF 回写：`d=fitz.open(dst); md=d.metadata or {}; md.update({...}); d.set_metadata(md); d.save(dst+'.tmp'); os.replace(...)`。
  **别用** PyPDF2 3.0.1 的 `add_metadata()`：它刷 8 条 `Incorrect first char in NameObject` 警告，且写入不生效。
  已落地签名：`make_watermark(src, dst, text, title=None)`。
- **shell 里 grep 含 `##`/`(` 的模式易静默失败**：改写 Python 或用 Grep 工具，别浪费轮次在空输出上。
- **网络字体下载**：GitHub raw 下载 SimHei 可能超时，脚本需带重试/持久化，失败回退 Arial Unicode。

---

## 变更记录

- **2026-09-14**　规范 2 补「补充 1 续：表头深色的可选色阶与硬下限」——6 档色值实测对比度表、
  **白字压底 ≥ 7.0（AAA）/ 底色相对亮度 ≤ 0.10** 硬下限、KV 标签字色连带约束（浅底对比度需重算）、
  monkey-patch 调色法。
- **2026-09-14**　命名规范：交付件文件名去掉 `_水印版`（水印为交付必备，标注冗余）。
  全量重命名 13 份交付件；生成脚本同步改名；**新增「临时基础版必须删除」硬要求**
  与老脚本的**交付件保护门禁**（已存在即拒绝覆盖）；速查清单改为"唯一交付件 + 无水印残留 = 0"。
- **2026-09-14**　**字形规则纠偏 + 自检脚本化**（本轮最大改动）：新增「SimHei 字形能力权威表」——
  用 `has_glyph()` 实测替代黑名单，**判定 `①②③④⑤⑥⑦⑧⑨⑩ ★ → · × ≥ ≤ ≈ ★☆▲●◆■※§°±÷∞` 均为可用**（旧黑名单误伤），
  `¥£¢•` 需包 Helvetica，**emoji 与小币种符号（`₩₺₽₹₦₱฿₫…`）双方字体皆无字形必须禁用**；
  揭示「缺字形真实形态 = 渲染空框 + 文本层 `U+0000`」（旧规则「`□` 计数为 0」是错的）。
  新增 `scripts/qc_client_pdf.py` 一把梭自检（10 项、可 JSON 输出、FAIL 时退出码 1），速查清单改为调用它。
- **2026-09-14**　新增「客户可见面不得出现交付侧标注」：速查清单加 2 项（5 面核查 + 元数据标题非空）；
  踩坑备忘加「水印叠加丢元数据」与 PyPDF2 `add_metadata` 陷阱；`客户交付版` 从合法保留词中移除。
  主色由 `#1a365d` 统一升级为 S2 `#1f4f8f`（表头/章标题/KV 标签字/封面大字同色）。
- **2026-09-14**　规范 2 补「表头分级」（数据表深底 / 键值表浅底标签列）；规范 6 补汇率表精度规则。
- **2026-09-14**　**修 `scripts/report_starter.py` 与 `qc_client_pdf.py` 的两处隐患**（做"工作流可冷启动"审计时发现）：
  - `report_starter.py` 一直停留在 8 月版本 —— `base_styles`/`table_style_factory` 色值仍是被弃用的 `#2E5AAC` / `#1F3D7A`；
    `add_watermark()` **没有 `title` 参数**（即上面那条"水印叠加丢元数据"的坑，通用库未同步修复）；
    `fix_currency()` 只处理 `¥`，漏了 `£ ¢ € – — ·`；`setup_font()` 把字体目录硬编码成某个工作区路径。
    已全部对齐现行规范（色值 → `#1f4f8f`；水印加 `title` + PyMuPDF 回写；字形层补全；
    字体改为 `$SALARY_REPORT_FONT` → `~/WorkBuddy/*/fonts/` → 系统回退的多路径探测）。
    另修一个静默 bug：`base_styles` 的 `body/small/cell` 误用 `color=`（应为 `textColor=`），
    **不会报错但颜色不生效**（灰色小字实际渲染成黑色）—— 正是规范 4 警告的情形。
  - `qc_client_pdf.py` 的 `find_font()` 只查 cwd 与 skill 目录，导致**字形检测这项核心门禁在多数调用场景下被静默跳过**
    （实测输出 `[warn] 未找到 SimHei.ttf，本次跳过字形能力检测`）。已补环境变量与 `~/WorkBuddy/*/fonts/` 扫描。
