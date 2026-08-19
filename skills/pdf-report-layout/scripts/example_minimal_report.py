"""
pdf-report-layout · 最小可运行示例
演示：字体 → 样式 → 表格(四件套) → 文档 → 水印 → 校验 全链路。
运行：python3 example_minimal_report.py  → 生成 /tmp/demo_report.pdf + 水印版
"""
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, KeepTogether
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
import os

from report_starter import (
    setup_font, base_styles, table_style_factory, make_table,
    add_watermark, validate_pdf
)

OUT = "/tmp/demo_report.pdf"
WM = "/tmp/demo_report_wm.pdf"

# 1) 字体 + 样式
font = setup_font()
S = base_styles(font)

# 2) 文档
doc = SimpleDocTemplate(OUT, pagesize=A4,
                        leftMargin=18*mm, rightMargin=18*mm,
                        topMargin=16*mm, bottomMargin=16*mm)
story = []
story.append(Paragraph("薪酬带宽报告 · 示例", S["title"]))
story.append(Paragraph("马来西亚吉隆坡 · 海外实施交付工程师", S["subtitle"]))
story.append(Spacer(1, 8))

# 3) 表格（四件套由 make_table 自动套用）
header = [Paragraph("候选人类型", S["cell_head"]),
          Paragraph("建议月薪 (RM)", S["cell_head"]),
          Paragraph("约合 CNY", S["cell_head"])]
rows = [
    header,
    [Paragraph("本地马来人(三语)", S["cell"]), Paragraph("6,000-8,500", S["cell"]), Paragraph("10,000-14,200", S["cell"])],
    [Paragraph("本地华裔(三语)", S["cell"]), Paragraph("6,500-9,000", S["cell"]), Paragraph("10,800-15,000", S["cell"])],
    [Paragraph("中国籍外派", S["cell"]), Paragraph("—", S["cell"]), Paragraph("15,000-25,000+津贴", S["cell"])],
]
col_w = [55*mm, 45*mm, 55*mm]  # 数字列≥95pt(≈34mm) ✅
story.append(KeepTogether([
    Paragraph("薪资建议", S["h3"]),
    make_table(rows, col_w)
]))
story.append(Spacer(1, 6))
story.append(Paragraph("汇率：1 MYR = 1.669 CNY（2026.08.19 央行中间价）", S["small"]))

doc.build(story)

# 4) 水印
add_watermark(OUT, WM, text="用友薪福社  2026.08.19", font_name=font)

# 5) 校验
n, missing = validate_pdf(WM, must_contain=["6,000-8,500", "1.669", "用友薪福社"])
print(f"Pages={n}  Missing={missing}")
print(f"Demo written: {OUT}\nWatermarked: {WM}\nPreview: /tmp/pdf_check/all.png")
