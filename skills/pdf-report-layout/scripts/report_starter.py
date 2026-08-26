"""
pdf-report-layout · 可复用排版函数库
规范来源：client-salary-band-report 多份交付报告沉淀
依赖：reportlab, PyPDF2, PyMuPDF(fitz), Pillow
"""
import os

# ---------- 字体：持久化到工作目录，禁止 /tmp ----------
_DEFAULT_FONT_DIR = "/Users/yoyo/WorkBuddy/2026-07-29-13-50-49/fonts"
_SIMHEI_URL = "https://github.com/StellarCN/scp_zh/raw/master/fonts/SimHei.ttf"
_FALLBACK_FONT = "/Library/Fonts/Arial Unicode.ttf"


def setup_font(font_dir=_DEFAULT_FONT_DIR, font_name="SimHei"):
    """下载并注册 SimHei 字体，返回已注册的字体名。失败回退 Arial Unicode。"""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    os.makedirs(font_dir, exist_ok=True)
    font_path = os.path.join(font_dir, "SimHei.ttf")

    if not os.path.exists(font_path):
        try:
            import urllib.request
            urllib.request.urlretrieve(_SIMHEI_URL, font_path)
        except Exception:
            if os.path.exists(_FALLBACK_FONT):
                font_path = _FALLBACK_FONT
                font_name = "ArialUnicode"
            else:
                raise

    pdfmetrics.registerFont(TTFont(font_name, font_path))
    return font_name


# ---------- 币种符号兼容层 ----------
def fix_currency(text):
    """¥(U+00A5) 非 ASCII，SimHei 缺字形 → 切 Helvetica；中文（如"万"）必须留在 SimHei。
    $ 是 ASCII 0x24，SimHei 可显示，无需处理。所有文本在生成 Paragraph 前过一遍。"""
    return text.replace("¥", '<font face="Helvetica">¥</font>')


# ---------- 样式：一套标准 ParagraphStyle ----------
def base_styles(font_name="SimHei"):
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT

    return {
        "title": ParagraphStyle("title", fontName=font_name, fontSize=20, leading=26,
                                alignment=TA_CENTER, textColor=colors.HexColor("#1A1A1A")),
        "subtitle": ParagraphStyle("subtitle", fontName=font_name, fontSize=12, leading=18,
                                   alignment=TA_CENTER, textColor=colors.HexColor("#555555")),
        "h2": ParagraphStyle("h2", fontName=font_name, fontSize=14, leading=20,
                             textColor=colors.HexColor("#2E5AAC"), spaceBefore=10, spaceAfter=4),
        "h3": ParagraphStyle("h3", fontName=font_name, fontSize=11.5, leading=16,
                             textColor=colors.HexColor("#1F3D7A"), spaceBefore=6, spaceAfter=3),
        "body": ParagraphStyle("body", fontName=font_name, fontSize=10, leading=15,
                               color=colors.black),
        "small": ParagraphStyle("small", fontName=font_name, fontSize=8.5, leading=12,
                                color=colors.HexColor("#666666")),
        "cell": ParagraphStyle("cell", fontName=font_name, fontSize=9.5, leading=13,
                               color=colors.black),
        "cell_head": ParagraphStyle("cell_head", fontName=font_name, fontSize=9.5, leading=13,
                                    textColor=colors.white),
        "callout": ParagraphStyle("callout", fontName=font_name, fontSize=11, leading=16,
                                  alignment=TA_CENTER, textColor=colors.HexColor("#B23A2E")),
    }


# ---------- 表格排版四件套（规范 2） ----------
def table_style_factory(header_bg="#2E5AAC", body_align="LEFT", header_align="CENTER"):
    from reportlab.lib import colors
    return [
        ("ALIGN",    (0,0), (-1,-1), body_align),
        ("ALIGN",    (0,0), (-1,0),  header_align),
        ("BOX",      (0,0), (-1,-1), 0.6, colors.HexColor("#999999")),
        ("GRID",     (0,0), (-1,-1), 0.4, colors.HexColor("#CCCCCC")),
        ("TEXTCOLOR",(0,0), (-1,-1), colors.black),
        ("FONTSIZE", (0,0), (-1,-1), 9.5),
        ("VALIGN",   (0,0), (-1,-1), "MIDDLE"),
        ("LEADING",  (0,0), (-1,-1), 12),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#F5F7FA")]),
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor(header_bg)),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("TOPPADDING",    (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("LEFTPADDING",   (0,0), (-1,-1), 6),
        ("RIGHTPADDING",  (0,0), (-1,-1), 6),
    ]


def make_table(data, col_widths, style=None, keep_together=True, header_bg="#2E5AAC"):
    """data: list[list]，首行为表头。单元格建议用 Paragraph 包装以支持换行。"""
    from reportlab.platypus import Table, KeepTogether
    from reportlab.lib import colors

    t = Table(data, colWidths=col_widths, repeatRows=1)
    if style is None:
        style = table_style_factory(header_bg=header_bg)
    t.setStyle(style)
    return KeepTogether(t) if keep_together else t


# ---------- 水印（规范 7） ----------
def add_watermark(src, dst, text="用友薪福社  2026.08.19", font_name="SimHei"):
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
