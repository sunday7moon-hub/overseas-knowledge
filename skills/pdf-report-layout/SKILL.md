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

### 规范 3：防止分页切断（防排版三规则）

长报告经常出现在表格中间或标题与表分离的分页切断。三条规则：

1. **标题与表格绑定**：用 `KeepTogether([heading, table])` 把小节标题和它的表锁在一起。
   ```python
   from reportlab.platypus import KeepTogether
   story.append(KeepTogether([Paragraph("3. 薪资建议", h3), salary_table]))
   ```
2. **长单元格拆行**：单元格内长文本用 `<br/>` 手动拆成 2-3 行，避免单行溢出。
3. **表格函数加 `keep_together` 参数**：自封装的 `make_table()` 默认返回 `KeepTogether` 包裹的流，需要跨页时再传 `keep_together=False`。

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

### 规范 7：水印叠加（客户版 → 水印版）

客户端 PDF 通常要出一版带"用友薪福社 + 日期"水印的版本。用 reportlab 画 overlay 再用 PyPDF2 合并：

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
| 1 | 品牌主色 PRIMARY | `#1a365d` 深藏青（标题/封面大字/表头字/表格外框） | `#2E5AAC` ❌ |
| 2 | 强调红 ACCENT | `#c53030`（封面装饰条实心填充） | 画线 `#B23A2E` ❌ |
| 3 | 表头样式 | **浅蓝底 `#edf2f7` + 深蓝字 PRIMARY + `<b>`** + 10pt | 深蓝底白字 ❌ |
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
4. 输出：临时基础版 → `add_watermark` → 水印版（唯一交付，删基础版）
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

## 排版速查清单（交付前逐项勾）

- [ ] 字体已持久化到工作目录 `fonts/SimHei.ttf`，未用 `/tmp`
- [ ] 每个表格都含 ALIGN + BOX + GRID + TEXTCOLOR（四件套）
- [ ] 标题与表用 KeepTogether 绑定，无跨页切断
- [ ] 数字列宽 ≥ 95pt
- [ ] ParagraphStyle 的 color 用 keyword 传参
- [ ] 强调用字号/颜色而非 `<b>`（SimHei 无 bold）
- [ ] 多币种列名带符号，汇率四数并列 + 换算抽查
- [ ] 已出客户版 + 水印版两版
- [ ] PyMuPDF 图文校验通过（关键数字在、无乱码、无切断）

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
- **网络字体下载**：GitHub raw 下载 SimHei 可能超时，脚本需带重试/持久化，失败回退 Arial Unicode。
