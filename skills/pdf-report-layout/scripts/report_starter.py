"""
pdf-report-layout · 可复用排版函数库
规范来源：client-salary-band-report 多份交付报告沉淀
依赖：reportlab, PyPDF2, PyMuPDF(fitz), Pillow
"""
import os

# ---------- 字体：持久化，禁止 /tmp；不写死工作区路径 ----------
_SIMHEI_URL = "https://github.com/StellarCN/scp_zh/raw/master/fonts/SimHei.ttf"
_FALLBACK_FONTS = ["/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
                   "/Library/Fonts/Arial Unicode.ttf"]
_DOWNLOAD_DIR = os.path.expanduser("~/.workbuddy/fonts")


def resolve_font_path():
    """按优先级定位中文字体：$SALARY_REPORT_FONT → ~/WorkBuddy/*/fonts/ → 系统回退 → None。"""
    import glob
    env = os.environ.get("SALARY_REPORT_FONT")
    if env and os.path.exists(env):
        return env
    hits = sorted(glob.glob(os.path.expanduser("~/WorkBuddy/*/fonts/SimHei.ttf")), reverse=True)
    if hits:
        return hits[0]
    for cand in _FALLBACK_FONTS:
        if os.path.exists(cand):
            return cand
    return None


def setup_font(font_dir=None, font_name="SimHei"):
    """注册中文字体，返回实际使用的字体名。

    font_dir 显式传入时按旧行为在該目录找/下载 SimHei.ttf（向后兼容）；
    不传则走 resolve_font_path() 自动探测。
    """
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    font_path = None
    if font_dir:
        os.makedirs(font_dir, exist_ok=True)
        cand = os.path.join(font_dir, "SimHei.ttf")
        font_path = cand if os.path.exists(cand) else None

    if font_path is None:
        font_path = resolve_font_path()

    if font_path is None:
        os.makedirs(_DOWNLOAD_DIR, exist_ok=True)
        font_path = os.path.join(_DOWNLOAD_DIR, "SimHei.ttf")
        if not os.path.exists(font_path):
            import urllib.request
            urllib.request.urlretrieve(_SIMHEI_URL, font_path)

    if "Arial Unicode" in font_path:
        font_name = "ArialUnicode"
    pdfmetrics.registerFont(TTFont(font_name, font_path))
    return font_name


# ---------- 币种符号兼容层 ----------
# SimHei 缺字形、但 Helvetica 有的符号：¥ £ ¢ € $ – — ·
# ⚠️ 反例（不要包）：→ ★ ① 在 Helvetica 里也没有字形；小币种符号 ₩₺₽₹฿₫ 两边都没有，
#    只能写 ISO 代码。判据用 fitz.Font(SimHei).has_glyph() 实测，勿凭印象。
_HELV_WRAP = ["¥", "€", "£", "¢", "$", "–", "—", "·"]


def fix_currency(text):
    """把 SimHei 缺字形的符号路由到 Helvetica；中文（如"万"）留在 SimHei。
    所有文本在生成 Paragraph 前过一遍。"""
    text = str(text)
    for sym in _HELV_WRAP:
        text = text.replace(sym, '<font face="Helvetica">%s</font>' % sym)
    return text


# ---------- 样式：一套标准 ParagraphStyle ----------
def base_styles(font_name="SimHei"):
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT

    # ⚠️ 字色关键字必须是 textColor；写成 color= 不会报错但静默失效（颜色不生效）。
    # ⚠️ 主色为 S2 #1f4f8f（2026-09-14 起为品牌现行色）。旧的 #2E5AAC / #1F3D7A 已弃用。
    return {
        "title": ParagraphStyle("title", fontName=font_name, fontSize=20, leading=26,
                                alignment=TA_CENTER, textColor=colors.HexColor("#0F0F0F")),
        "subtitle": ParagraphStyle("subtitle", fontName=font_name, fontSize=12, leading=18,
                                   alignment=TA_CENTER, textColor=colors.HexColor("#4a5568")),
        "h2": ParagraphStyle("h2", fontName=font_name, fontSize=14, leading=20,
                             textColor=colors.HexColor("#1f4f8f"), spaceBefore=10, spaceAfter=4),
        "h3": ParagraphStyle("h3", fontName=font_name, fontSize=11.5, leading=16,
                             textColor=colors.HexColor("#1f4f8f"), spaceBefore=6, spaceAfter=3),
        "body": ParagraphStyle("body", fontName=font_name, fontSize=10, leading=15,
                               textColor=colors.black),
        "small": ParagraphStyle("small", fontName=font_name, fontSize=8.5, leading=12,
                                textColor=colors.HexColor("#4a5568")),
        "cell": ParagraphStyle("cell", fontName=font_name, fontSize=9.5, leading=13,
                               textColor=colors.black),
        "cell_head": ParagraphStyle("cell_head", fontName=font_name, fontSize=9.5, leading=13,
                                    textColor=colors.HexColor("#eef2f8")),
        "callout": ParagraphStyle("callout", fontName=font_name, fontSize=11, leading=16,
                                  alignment=TA_CENTER, textColor=colors.HexColor("#c53030")),
    }


# ---------- 表格排版四件套（规范 2） ----------
def table_style_factory(header_bg="#1f4f8f", body_align="LEFT", header_align="CENTER"):
    """数据表样式。header_bg 默认 S2 #1f4f8f（品牌现行色）。

    ⚠️ 仅适用于「首行是真列名」的数据表。键值表（标签—值 结构）不要染深色表头，
       改用浅底标签列（参见 salary_report_kit.KV）。
    """
    from reportlab.lib import colors
    return [
        ("ALIGN",    (0,0), (-1,-1), body_align),
        ("ALIGN",    (0,0), (-1,0),  header_align),
        ("BOX",      (0,0), (-1,-1), 0.6, colors.HexColor(header_bg)),
        ("GRID",     (0,0), (-1,-1), 0.4, colors.HexColor("#e2e8f0")),
        ("TEXTCOLOR",(0,0), (-1,-1), colors.black),
        ("FONTSIZE", (0,0), (-1,-1), 9.5),
        ("VALIGN",   (0,0), (-1,-1), "MIDDLE"),
        ("LEADING",  (0,0), (-1,-1), 12),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f7fafc")]),
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor(header_bg)),
        ("TEXTCOLOR", (0,0), (-1,0), colors.HexColor("#eef2f8")),
        ("TOPPADDING",    (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("LEFTPADDING",   (0,0), (-1,-1), 6),
        ("RIGHTPADDING",  (0,0), (-1,-1), 6),
    ]


def make_table(data, col_widths, style=None, keep_together=True, header_bg="#1f4f8f"):
    """data: list[list]，首行为表头。单元格建议用 Paragraph 包装以支持换行。"""
    from reportlab.platypus import Table, KeepTogether
    from reportlab.lib import colors

    t = Table(data, colWidths=col_widths, repeatRows=1)
    if style is None:
        style = table_style_factory(header_bg=header_bg)
    t.setStyle(style)
    return KeepTogether(t) if keep_together else t


# ---------- 水印（规范 7） ----------
def add_watermark(src, dst, text="用友薪福社  2026.08.19", font_name="SimHei", title=None):
    """叠加斜向水印。

    ⚠️ PyPDF2 逐页重建会丢掉源 PDF 的元数据（Info 字典）→ 阅读器标签页退化成**文件名**。
       交付客户时这会暴露 `xxx_客户版.pdf` 这类内部后缀。因此 title 建议必传（正式报告名）。
       回写用 PyMuPDF：PyPDF2 3.x 的 add_metadata() 对键格式挑剔，会抛 NameObject 警告且写入无效。
    """
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
        c.setFont(font_name, 32); c.setFillColorRGB(0.78, 0.78, 0.78)
        c.saveState(); c.translate(PW/2, PH/2); c.rotate(40)
        c.drawCentredString(0, 0, text); c.restoreState()
        c.saveState(); c.setFont(font_name, 22); c.setFillColorRGB(0.8, 0.8, 0.8)
        c.translate(PW*0.2, PH*0.83); c.rotate(-35)
        c.drawCentredString(0, 0, text); c.restoreState()
        c.saveState(); c.setFont(font_name, 22); c.setFillColorRGB(0.8, 0.8, 0.8)
        c.translate(PW*0.8, PH*0.17); c.rotate(-35)
        c.drawCentredString(0, 0, text); c.restoreState()
        c.save(); packet.seek(0)
        wm = PdfReader(packet).pages[0]
        reader.pages[i].merge_page(wm)
        writer.add_page(reader.pages[i])
    with open(dst, "wb") as f:
        writer.write(f)

    if title:
        try:
            import fitz
            d = fitz.open(dst)
            md = d.metadata or {}
            md.update({"title": title, "author": "用友薪福社",
                       "creator": "用友薪福社", "producer": "用友薪福社"})
            d.set_metadata(md)
            d.save(dst + ".md.pdf")
            d.close()
            os.replace(dst + ".md.pdf", dst)
        except Exception as e:
            print("  [warn] 元数据回写失败（不影响正文）:", e)
    return dst


# ---------- 校验（规范 8） ----------
def validate_pdf(pdf_path, must_contain=None, preview_dir="/tmp/pdf_check", grid_cols=4):
    """图文双校验：返回 (page_count, status_list)。同时渲染网格预览 PNG。

    若环境缺少 PyMuPDF(fitz)/Pillow，自动降级：跳过图文校验，
    返回 (0, ["UNVERIFIED: ..."]) 并提示用 managed venv 运行。
    完整校验需：PyMuPDF + Pillow（managed venv 已预装）。
    """
    try:
        import fitz
        from PIL import Image
    except ImportError:
        tip = "用 managed venv 运行以获得图文校验：/Users/yoyo/.workbuddy/binaries/python/envs/default/bin/python3"
        print(f"[validate_pdf] 跳过：缺少 PyMuPDF/Pillow。{tip}")
        unverified = [f"UNVERIFIED: {m}" for m in (must_contain or [])]
        return 0, unverified

    doc = fitz.open(pdf_path)
    n = len(doc)

    missing = []
    if must_contain:
        full = "\n".join(page.get_text() for page in doc)  # 新版 fitz 用 get_text
        for m in must_contain:
            if m not in full:
                missing.append(m)

    os.makedirs(preview_dir, exist_ok=True)
    imgs = []
    for i, page in enumerate(doc):
        p = os.path.join(preview_dir, f"p{i+1:02d}.png")
        page.get_pixmap(dpi=110).save(p)
        imgs.append(Image.open(p))
    if imgs:
        w, h = imgs[0].size
        rows = (len(imgs) + grid_cols - 1) // grid_cols
        grid = Image.new("RGB", (w*grid_cols, h*rows), "white")
        for i, im in enumerate(imgs):
            grid.paste(im, ((i % grid_cols)*w, (i // grid_cols)*h))
        grid.thumbnail((1700, 1700))
        grid.save(os.path.join(preview_dir, "all.png"))
    doc.close()
    return n, missing


if __name__ == "__main__":
    # 自测：验证字体与样式可用
    fn = setup_font()
    print("Font registered:", fn)
    st = base_styles(fn)
    print("Styles:", list(st.keys()))
    ts = table_style_factory()
    print("Table style cmds:", len(ts))
