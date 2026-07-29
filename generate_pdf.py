"""
Habas Team Leader Salary Report - Professional ReportLab Edition
完全用 reportlab platypus 重新构建，确保所有表格正确换行，无溢出
"""
import os
import re
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
    KeepTogether, Image
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont

# Register CJK CID fonts
pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5'))  # 备用日文黑体，用于无中文黑体时的替代

# Color palette
PRIMARY = colors.HexColor('#1a365d')      # 深蓝主色
ACCENT = colors.HexColor('#c53030')       # 红色强调
LIGHT_BG = colors.HexColor('#edf2f7')     # 表头浅灰
ALT_BG = colors.HexColor('#f7fafc')       # 偶数行背景
BORDER = colors.HexColor('#e2e8f0')       # 边框浅灰
TEXT_DARK = colors.HexColor('#2d3748')    # 正文深色
TEXT_MUTED = colors.HexColor('#718096')   # 次要灰

# Page setup
PAGE_WIDTH, PAGE_HEIGHT = A4
LEFT_MARGIN = 16 * mm
RIGHT_MARGIN = 16 * mm
TOP_MARGIN = 22 * mm
BOTTOM_MARGIN = 22 * mm
USABLE_WIDTH = PAGE_WIDTH - LEFT_MARGIN - RIGHT_MARGIN

# Styles
styles = getSampleStyleSheet()

title_style = ParagraphStyle(
    'CNTitle', parent=styles['Title'],
    fontName='STSong-Light',
    fontSize=22, leading=30,
    textColor=PRIMARY,
    alignment=TA_CENTER,
    spaceAfter=12
)

subtitle_style = ParagraphStyle(
    'CNSubtitle', parent=styles['Heading2'],
    fontName='STSong-Light',
    fontSize=14, leading=20,
    textColor=TEXT_DARK,
    alignment=TA_CENTER,
    spaceAfter=20
)

h1_style = ParagraphStyle(
    'CNH1', parent=styles['Heading1'],
    fontName='STSong-Light',
    fontSize=16, leading=22,
    textColor=PRIMARY,
    spaceBefore=18, spaceAfter=10,
    borderWidth=0, borderPadding=0,
)

h2_style = ParagraphStyle(
    'CNH2', parent=styles['Heading2'],
    fontName='STSong-Light',
    fontSize=13, leading=18,
    textColor=PRIMARY,
    spaceBefore=14, spaceAfter=6,
)

h3_style = ParagraphStyle(
    'CNH3', parent=styles['Heading3'],
    fontName='STSong-Light',
    fontSize=11.5, leading=16,
    textColor=TEXT_DARK,
    spaceBefore=10, spaceAfter=4,
)

h4_style = ParagraphStyle(
    'CNH4', parent=styles['Heading4'],
    fontName='STSong-Light',
    fontSize=10.5, leading=14,
    textColor=TEXT_MUTED,
    spaceBefore=8, spaceAfter=3,
)

body_style = ParagraphStyle(
    'CNBody', parent=styles['Normal'],
    fontName='STSong-Light',
    fontSize=10, leading=15,
    textColor=TEXT_DARK,
    spaceBefore=0, spaceAfter=4,
)

body_strong_style = ParagraphStyle(
    'CNBodyStrong', parent=body_style,
    fontName='STSong-Light',
    textColor=ACCENT,
)

bullet_style = ParagraphStyle(
    'CNBullet', parent=body_style,
    leftIndent=10, bulletIndent=0,
    spaceBefore=0, spaceAfter=2,
)

callout_style = ParagraphStyle(
    'CNCallout', parent=body_style,
    fontSize=9.5, leading=14,
    textColor=TEXT_DARK,
    leftIndent=8, rightIndent=8,
    spaceBefore=4, spaceAfter=4,
    backColor=colors.HexColor('#fff5f5'),
    borderPadding=6,
    borderWidth=0,
)

cell_style = ParagraphStyle(
    'CNCell', parent=body_style,
    fontSize=8.8, leading=12,
    spaceBefore=0, spaceAfter=0,
)

cell_header_style = ParagraphStyle(
    'CNCellHeader', parent=cell_style,
    fontSize=9, leading=13,
    textColor=PRIMARY,
    spaceBefore=0, spaceAfter=0,
)

cell_strong_style = ParagraphStyle(
    'CNCellStrong', parent=cell_style,
    textColor=ACCENT,
    fontSize=8.8, leading=12,
)

disclaimer_style = ParagraphStyle(
    'CNDisclaimer', parent=body_style,
    fontSize=8.5, leading=12,
    textColor=TEXT_MUTED,
    spaceBefore=12, spaceAfter=0,
)


def make_cell(text, header=False, bold=False):
    """Helper to create a cell Paragraph with proper styling."""
    text = str(text).strip().replace('\n', '<br/>')
    if header:
        return Paragraph(f'<b>{text}</b>', cell_header_style)
    elif bold:
        return Paragraph(f'<b>{text}</b>', cell_strong_style)
    else:
        return Paragraph(text, cell_style)


def make_table(rows, col_widths=None):
    """Build a table with proper styling. rows = list of list of cells (strings)."""
    if not rows:
        return None
    n_cols = len(rows[0])

    # Default column widths
    if col_widths is None:
        eq_w = USABLE_WIDTH / n_cols
        col_widths = [eq_w] * n_cols

    # Convert raw strings to Paragraphs for proper wrapping
    table_data = []
    for i, row in enumerate(rows):
        new_row = []
        for cell in row:
            text = str(cell).strip().replace('\n', '<br/>')
            if i == 0:
                # Header row
                new_row.append(Paragraph(f'<b>{text}</b>', cell_header_style))
            else:
                new_row.append(Paragraph(text, cell_style))
        table_data.append(new_row)

    t = Table(table_data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        # Header row styling
        ('BACKGROUND', (0, 0), (-1, 0), LIGHT_BG),
        ('TEXTCOLOR', (0, 0), (-1, 0), PRIMARY),
        ('FONTNAME', (0, 0), (-1, 0), 'STSong-Light'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('ALIGN', (0, 0), (-1, 0), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        # Body styling
        ('FONTNAME', (0, 1), (-1, -1), 'STSong-Light'),
        ('FONTSIZE', (0, 1), (-1, -1), 8.8),
        ('TEXTCOLOR', (0, 1), (-1, -1), TEXT_DARK),
        # Borders
        ('GRID', (0, 0), (-1, -1), 0.4, BORDER),
        ('BOX', (0, 0), (-1, -1), 0.6, PRIMARY),
        # Alternating row colors
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, ALT_BG]),
        # Padding
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        # Allow rows to split across pages
        ('KEEPTOGETHER', (0, 0), (-1, -1), False),
    ]))
    return t


# Define column widths for each table type (4-col is the most problematic one)
W4 = [USABLE_WIDTH * 0.20, USABLE_WIDTH * 0.30, USABLE_WIDTH * 0.30, USABLE_WIDTH * 0.20]
W3 = [USABLE_WIDTH * 0.25, USABLE_WIDTH * 0.45, USABLE_WIDTH * 0.30]
W3_SALARY = [USABLE_WIDTH * 0.35, USABLE_WIDTH * 0.30, USABLE_WIDTH * 0.35]
W2 = [USABLE_WIDTH * 0.55, USABLE_WIDTH * 0.45]
W5 = [USABLE_WIDTH * 0.18, USABLE_WIDTH * 0.22, USABLE_WIDTH * 0.30, USABLE_WIDTH * 0.15, USABLE_WIDTH * 0.15]


story = []

# ===== COVER / TITLE =====
story.append(Spacer(1, 60))
story.append(Paragraph('<b>HABAS</b>', ParagraphStyle(
    'logo', parent=title_style, fontSize=42, textColor=PRIMARY, spaceAfter=8)))
story.append(Paragraph('Sinai Ve Tibbi Gazlar Istihsal Endustrisi AS', subtitle_style))
story.append(Spacer(1, 24))
story.append(Paragraph('伊斯坦布尔 · 生产组长岗位<br/>薪资分析报告', title_style))
story.append(Paragraph('Team Leader Salary Analysis Report — Istanbul', subtitle_style))
story.append(Spacer(1, 16))
story.append(Spacer(1, 4))
# Red accent line
hr_table = Table([['']], colWidths=[USABLE_WIDTH * 0.4], rowHeights=[2])
hr_table.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), ACCENT)]))
hr_table.hAlign = 'CENTER'
story.append(hr_table)
story.append(Spacer(1, 24))

# Meta information table (nicely formatted)
meta_data = [
    ['报告日期', '2026年7月29日'],
    ['公司', 'Habas (HABAŞ)'],
    ['地点', '土耳其 伊斯坦布尔 / Manisa'],
    ['岗位', '冲压部门组长 · 车身焊接组长 · 车身涂装组长'],
    ['内容覆盖', '宏观经济参数 · 候选人标签 · 竞品分析 · 招聘策略'],
]
meta_table = Table(meta_data, colWidths=[USABLE_WIDTH * 0.30, USABLE_WIDTH * 0.70])
meta_table.setStyle(TableStyle([
    ('FONTNAME', (0, 0), (-1, -1), 'STSong-Light'),
    ('FONTSIZE', (0, 0), (-1, -1), 10),
    ('FONTNAME', (0, 0), (0, -1), 'STSong-Light'),
    ('TEXTCOLOR', (0, 0), (0, -1), TEXT_MUTED),
    ('TEXTCOLOR', (1, 0), (1, -1), TEXT_DARK),
    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ('TOPPADDING', (0, 0), (-1, -1), 5),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ('LEFTPADDING', (0, 0), (-1, -1), 8),
    ('LINEBELOW', (0, 0), (-1, -1), 0.3, BORDER),
]))
story.append(meta_table)
story.append(PageBreak())

# ===== SECTION 1: Macroeconomic Parameters =====
story.append(Paragraph('一、土耳其宏观经济参考参数', h1_style))

story.append(Paragraph('1.1 关键经济指标（2026年）', h2_style))

story.append(make_table([
    ['指标', '数值', '备注'],
    ['人均GDP（名义）', '~$15,893', '世界银行中高收入国家标准'],
    ['人均GDP（购买力平价PPP）', '$36,154', '反映实际购买力水平'],
    ['月最低工资（税前）', '33,030 TRY', '2026年1月起执行，较2025年涨27%'],
    ['月最低工资（税后）', '28,075 TRY（~$656）', '覆盖约900万工人'],
    ['全国平均月薪（税前）', '~35,000-45,000 TRY', '行业差异显著'],
    ['全国平均月薪（税后）', '~$775', '含各行业加权'],
    ['伊斯坦布尔平均月薪（税前）', '40,000-55,000 TRY', '比全国高17%，三城中最高'],
    ['伊斯坦布尔平均月薪（税后）', '~$1,114', '制造业工程师可达更高'],
    ['行业薪资：汽车制造（税前）', '35,000-60,000 TRY/月', '出口导向、周期性波动'],
    ['行业薪资：制造工程师（汽车，税前）', '49,565 TRY/月（均值）', '伊斯坦布尔再加17%≈58,000'],
    ['通胀率（2025年）', '~34.9%', '名义工资涨幅常被通胀抵消'],
    ['失业率', '8.8%', '青年失业率更高'],
    ['人类发展指数（HDI）', '0.855', '极高人类发展水平'],
    ['汇率参考', '~35.5 TRY / 1 USD', '2026年市场汇率，波动较大'],
], col_widths=[USABLE_WIDTH * 0.30, USABLE_WIDTH * 0.32, USABLE_WIDTH * 0.38]))

story.append(Paragraph('1.2 伊斯坦布尔生活成本参照', h2_style))

story.append(make_table([
    ['支出项', '金额（TRY）', '约合（USD）'],
    ['市中心一居室月租', '25,000-35,000', '$600-830'],
    ['非市中心一居室月租', '15,000-25,000', '$360-600'],
    ['水电暖网（两人）', '2,000-3,000/月', '$48-72'],
    ['单人自炊食品预算', '6,000-9,000/月', '$143-214'],
    ['公交/地铁月票', '~400/月', '~$11'],
    ['单人月总支出（非市中心自炊）', '40,000-50,000', '$960-1,200'],
    ['四口之家月总支出（非市中心）', '90,000-120,000', '$2,160-2,880'],
], col_widths=[USABLE_WIDTH * 0.40, USABLE_WIDTH * 0.30, USABLE_WIDTH * 0.30]))

# Callout box
callout = Table([[
    Paragraph(
        '<b>薪资购买力锚点：</b>建议薪资必须覆盖"单人月总支出"的 <b>1.2-1.5倍</b> 才有基本吸引力。'
        '按此计算，伊斯坦布尔有效薪资底线约为 <b>48,000-60,000 TRY/月（税前）</b>。',
        callout_style)
]], colWidths=[USABLE_WIDTH])
callout.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#fff5f5')),
    ('LEFTPADDING', (0, 0), (-1, -1), 10),
    ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ('TOPPADDING', (0, 0), (-1, -1), 8),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ('LINEABOVE', (0, 0), (-1, -1), 2, ACCENT),
]))
story.append(Spacer(1, 6))
story.append(callout)
story.append(Spacer(1, 8))

story.append(Paragraph('1.3 雇主成本明细', h2_style))

story.append(make_table([
    ['项目', '比例/金额'],
    ['社保(SGK)雇主缴纳', '16.75%（制造业优惠税率）'],
    ['失业保险（雇主）', '2%'],
    ['个税（累进）', '15%-40%（最高档）'],
    ['增值税（KDV）', '20%'],
    ['辞退准备金', '每工作1年=1个月工资，2026上半年封顶64,949 TRY/年'],
    ['总雇主成本系数', '≈ 1.30-1.40 × 税前工资'],
], col_widths=[USABLE_WIDTH * 0.40, USABLE_WIDTH * 0.60]))

story.append(PageBreak())

# ===== SECTION 2: Analysis Framework =====
story.append(Paragraph('二、分析维度框架', h1_style))

story.append(Paragraph('2.1 基准薪资层', h2_style))
story.append(make_table([
    ['维度', '说明'],
    ['Title对标', 'Team Leader / Production Team Leader / Production Supervisor'],
    ['行业基准', 'Automotive（汽车制造业）'],
    ['城市系数', '伊斯坦布尔（+17% vs 全国平均）'],
    ['经验系数', '5年+资深 / 3-5年中级 / 0-2年初级'],
    ['公司规模系数', 'Habas 新进入汽车制造业，规模中等偏大（年产能10,000-15,000辆）'],
    ['通胀调整', '2026年通胀~35%，薪资建议需含抗通胀涨幅（建议年涨幅≥通胀率）'],
], col_widths=[USABLE_WIDTH * 0.30, USABLE_WIDTH * 0.70]))

story.append(Paragraph('2.2 岗位技术溢价层', h2_style))
story.append(make_table([
    ['岗位', '核心技术要求', '溢价逻辑'],
    ['冲压部门组长', '模具成型技术、G1冲压线自动化、模具更换、OEE管理、废料管理',
     '传统冲压技能，市场供应相对充足，溢价空间小'],
    ['车身焊接组长', 'Fanuc/Yaskawa/Kuka焊接机器人、气保焊、气动焊接夹具、根因分析',
     '<font color="#c53030"><b>高需求</b></font>——焊接机器人编程+调试人才极度稀缺'],
    ['车身涂装组长', 'ED前处理、烘烤工艺控制(Yaskawa涂装机器人)、喷涂缺陷识别、化学/爆炸风险',
     '<font color="#c53030"><b>高需求</b></font>——涂装工艺+机器人经验复合型人才稀缺'],
], col_widths=[USABLE_WIDTH * 0.22, USABLE_WIDTH * 0.43, USABLE_WIDTH * 0.35]))

story.append(Paragraph('2.3 候选人市场竞争力层', h2_style))
story.append(make_table([
    ['维度', '说明'],
    ['被动候选人比例', '75-85%（高级技术人才不在招聘平台活跃）'],
    ['平均招聘周期', '技术岗47天，资深岗95-120天'],
    ['德国挖角溢价', '2.5-3.0倍薪资（有语言能力的工程师）'],
    ['Bursa竞品溢价', '15-20%高于全国水平'],
    ['Habas品牌拉力', '低（2021年才进入汽车业，品牌知名度远不及TOFAS/Ford Otosan）'],
], col_widths=[USABLE_WIDTH * 0.30, USABLE_WIDTH * 0.70]))

story.append(PageBreak())

# ===== SECTION 3: Salary Benchmarks =====
story.append(Paragraph('三、薪资基准数据（2026年7月）', h1_style))

story.append(Paragraph('3.1 土耳其全国Team Leader薪资', h2_style))
story.append(make_table([
    ['分类', '月薪(TRY)', '约合(USD)'],
    ['全国Team Leader平均', '35,657', '~$1,010'],
    ['伊斯坦布尔Team Leader平均', '<b>41,719</b>', '~$1,180'],
    ['汽车行业Team Leader平均', '34,587', '~$975'],
    ['Production Team Leader平均', '36,780', '~$1,040'],
    ['Production Team Leader - 汽车行业', '35,677', '~$1,005'],
    ['伊斯坦布尔Production Team Leader（行业均值推算）', '<b>41,700-44,500</b>', '~$1,180-1,260'],
    ['全国薪资范围（低-高）', '28,058 - 48,465', '~$795-1,370'],
    ['伊斯坦布尔薪资范围（低-高）', '32,829 - 56,704', '~$930-1,600'],
], col_widths=[USABLE_WIDTH * 0.50, USABLE_WIDTH * 0.25, USABLE_WIDTH * 0.25]))

story.append(Paragraph('3.2 按经验层级分（伊斯坦布尔，汽车行业）', h2_style))
story.append(make_table([
    ['经验级别', '月薪(TRY)', '约合(USD)'],
    ['初级（0-2年）', '22,107 - 28,000', '~$625-790'],
    ['中级（3-5年）', '35,000 - 45,000', '~$990-1,270'],
    ['<b>资深（5年+）</b>', '<b>45,000 - 56,000</b>', '<b>~$1,270-1,580</b>'],
    ['高技能/机器人专长', '50,000 - 65,000', '~$1,410-1,830'],
], col_widths=[USABLE_WIDTH * 0.40, USABLE_WIDTH * 0.30, USABLE_WIDTH * 0.30]))

story.append(Paragraph('3.3 年度薪资参考', h2_style))
story.append(make_table([
    ['口径', '年薪(TRY)', '约合(USD)'],
    ['Production Supervisor/Team Leader（行业下限）', '520,000', '~$14,650'],
    ['<b>Production Supervisor/Team Leader（行业中位）</b>',
     '<b>780,000</b>', '<b>~$21,970</b>'],
    ['Production Supervisor/Team Leader（行业上限）', '1,150,000', '~$32,400'],
], col_widths=[USABLE_WIDTH * 0.55, USABLE_WIDTH * 0.225, USABLE_WIDTH * 0.225]))

story.append(Paragraph('3.4 薪资区间与宏观指标对比', h2_style))
story.append(make_table([
    ['对比维度', '金额', '占Habas建议薪资比例'],
    ['土耳其月最低工资（税后）', '28,075 TRY', '焊接组：65%-51%'],
    ['伊斯坦布尔单人月支出', '40,000-50,000 TRY', '焊接组可完全覆盖并有余'],
    ['伊斯坦布尔平均月薪（税前）', '40,000-55,000 TRY', '焊接组：与市场均值持平'],
    ['制造工程师均薪（汽车，伊斯坦布尔）', '~58,000 TRY', '焊接组：74%-95%'],
    ['<b>建议焊接组长薪资</b>', '<b>43,000-55,000 TRY</b>', '<b>定位：市场中上水平</b>'],
], col_widths=[USABLE_WIDTH * 0.40, USABLE_WIDTH * 0.30, USABLE_WIDTH * 0.30]))

story.append(PageBreak())

# ===== SECTION 4: Recommended Salary Ranges =====
story.append(Paragraph('四、Habas三岗位薪资建议区间', h1_style))

story.append(Paragraph(
    '综合考虑伊斯坦布尔系数（+17%）、汽车行业基准、Habas作为新进入品牌的"人才溢价"'
    '（+5-10%）、焊接/涂装机器人技能稀缺溢价（+10-15%）、通胀调整'
    '（建议年度调薪≥34.9%通胀率）。', body_style))
story.append(Spacer(1, 4))

story.append(Paragraph('4.1 冲压部门组长', h2_style))
story.append(make_table([
    ['项目', 'TRY/月', 'USD/月', 'TRY/年'],
    ['<b>建议薪资范围</b>', '<b>38,000 - 48,000</b>', '<b>$1,070-1,350</b>',
     '<b>456,000-576,000</b>'],
    ['基线（伊斯坦布尔汽车Team Leader）', '41,700', '$1,180', '500,400'],
    ['雇主总成本（×1.35）', '51,300-64,800', '$1,445-1,825', '615,600-777,600'],
    ['<b>行业对标薪资定位</b>', '<b>市场P50-P60</b>', '', ''],
    ['<b>占伊斯坦布尔平均月薪比例</b>', '<b>76%-96%</b>', '', ''],
], col_widths=[USABLE_WIDTH * 0.32, USABLE_WIDTH * 0.22, USABLE_WIDTH * 0.22, USABLE_WIDTH * 0.24]))

story.append(Paragraph(
    '<b>说明：</b>冲压岗位技术门槛相对常规，模具成型经验+冲压线自动化管理是关键。'
    '不需要机器人编程等高稀缺技能，溢价空间有限。建议定位市场中位数偏上。', callout_style))

story.append(Paragraph('4.2 车身焊接组长', h2_style))
story.append(make_table([
    ['项目', 'TRY/月', 'USD/月', 'TRY/年'],
    ['<b>建议薪资范围</b>', '<b>43,000 - 55,000</b>', '<b>$1,210-1,550</b>',
     '<b>516,000-660,000</b>'],
    ['基线+机器人技能溢价（+15%）', '48,000', '$1,350', '576,000'],
    ['雇主总成本（×1.35）', '58,050-74,250', '$1,635-2,090', '696,600-891,000'],
    ['<b>行业对标薪资定位</b>', '<b>市场P60-P75</b>', '', ''],
    ['<b>占伊斯坦布尔平均月薪比例</b>', '<b>86%-110%</b>', '', ''],
], col_widths=[USABLE_WIDTH * 0.32, USABLE_WIDTH * 0.22, USABLE_WIDTH * 0.22, USABLE_WIDTH * 0.24]))

story.append(Paragraph(
    '<b>说明：</b>焊接机器人（Fanuc/Yaskawa/Kuka）编程与调试经验非常稀缺。'
    '候选人同时需具备气保焊工艺知识+气动夹具管理+根因分析能力，复合技能要求使这一岗位竞争最激烈。'
    '<font color="#c53030"><b>建议作为三岗中薪资最高的。</b></font>根据行业报告，'
    'EV转型期焊接相关技术人才招聘周期长达95-120天。', callout_style))

story.append(Paragraph('4.3 车身涂装组长', h2_style))
story.append(make_table([
    ['项目', 'TRY/月', 'USD/月', 'TRY/年'],
    ['<b>建议薪资范围</b>', '<b>40,000 - 52,000</b>', '<b>$1,130-1,465</b>',
     '<b>480,000-624,000</b>'],
    ['基线+涂装工艺溢价（+10%）', '45,900', '$1,295', '550,800'],
    ['雇主总成本（×1.35）', '54,000-70,200', '$1,520-1,975', '648,000-842,400'],
    ['<b>行业对标薪资定位</b>', '<b>市场P55-P70</b>', '', ''],
    ['<b>占伊斯坦布尔平均月薪比例</b>', '<b>80%-104%</b>', '', ''],
], col_widths=[USABLE_WIDTH * 0.32, USABLE_WIDTH * 0.22, USABLE_WIDTH * 0.22, USABLE_WIDTH * 0.24]))

story.append(Paragraph(
    '<b>说明：</b>ED前处理、烘烤工艺控制、Yaskawa涂装机器人经验是核心稀缺技能。'
    '涂装缺陷识别（流挂/橘皮/针孔）需要较长时间经验积累。'
    '化学&爆炸风险管控知识构成额外门槛。溢价程度略低于焊接岗。', callout_style))

story.append(Paragraph('4.4 三岗位薪资对比一览', h2_style))
story.append(make_table([
    ['岗位', '建议月薪(TRY)', '年总成本(含雇主)', '稀缺度', '市场定位'],
    ['车身焊接组长', '43,000-55,000', '696,600-891,000', '5/5', 'P60-P75'],
    ['车身涂装组长', '40,000-52,000', '648,000-842,400', '4/5', 'P55-P70'],
    ['冲压部门组长', '38,000-48,000', '615,600-777,600', '3/5', 'P50-P60'],
], col_widths=[USABLE_WIDTH * 0.20, USABLE_WIDTH * 0.22, USABLE_WIDTH * 0.25, USABLE_WIDTH * 0.13, USABLE_WIDTH * 0.20]))

story.append(PageBreak())

# ===== SECTION 5: Competitor Analysis =====
story.append(Paragraph('五、竞品在招分析', h1_style))

story.append(Paragraph('5.1 伊斯坦布尔/科贾埃利地区主要竞品', h2_style))
story.append(make_table([
    ['竞品公司', '地点', '在招情况', '对Habas的人才竞争威胁'],
    ['Mercedes-Benz Türk', '伊斯坦布尔 Hoşdere',
     '技术岗持续招聘，薪资行业标杆',
     '<b>高</b>——品牌溢价+薪资优势'],
    ['Ford Otosan', 'Kocaeli Gölcük/Yeniköy',
     '2025年技术招聘增加55%',
     '<b>高</b>——全球最大商用车厂之一'],
    ['Hyundai Assan', 'Kocaeli Izmit',
     '新增电池工厂(5500万EUR)招300+人',
     '<b>高</b>——EV转型先发优势'],
    ['Otokar', '伊斯坦布尔/Sakarya',
     '持续招聘工程师', '中——商用车领域直接竞品'],
    ['Karsan', 'Bursa', '电动化人才需求增长',
     '中低——在Bursa而非伊斯坦布尔'],
    ['Tofas (Stellantis)', 'Bursa', '裁员13%（重组中）',
     '中——释放人才，可能流入市场'],
    ['MAN Turkiye', '安卡拉', '稳定招聘',
     '低——在安卡拉，非伊斯坦布尔'],
], col_widths=[USABLE_WIDTH * 0.22, USABLE_WIDTH * 0.22, USABLE_WIDTH * 0.30, USABLE_WIDTH * 0.26]))

story.append(Paragraph('5.2 关键发现', h2_style))
findings = [
    '最直接的人才竞争来源：Mercedes-Benz Turk（Hosdere工厂就在伊斯坦布尔亚洲侧）、'
    'Ford Otosan（Kocaeli距伊斯坦布尔约1小时车程）',
    'EV转型分流：Hyundai新增的电池工厂和IONIQ 3产线正在大量吸收Kocaeli地区的技术人才',
    '传统车企释放人才：Tofas裁员释放部分有经验的组长级候选人，是Habas可关注的目标人群',
    'Habas的劣势：品牌认知度低（2021年才进入汽车业），无法提供与Ford Otosan/Mercedes-Benz同等的薪资竞争力',
]
for f in findings:
    story.append(Paragraph(f'• {f}', bullet_style))
story.append(Spacer(1, 4))

story.append(Paragraph('5.3 竞品薪资对比', h2_style))
story.append(make_table([
    ['竞品', '同级别薪资(TRY/月)', '说明'],
    ['Mercedes-Benz Turk', '50,000-65,000+', '行业薪资标杆，含额外福利'],
    ['Ford Otosan', '45,000-60,000', '含奖金+车辆福利，3.1/5薪酬评分(Glassdoor)'],
    ['Hyundai Assan', '42,000-55,000', '中等偏上，EV岗位有额外溢价'],
    ['Otokar', '38,000-50,000', '与Habas最为接近的对标公司'],
    ['<b>Habas（建议）</b>', '<b>38,000-55,000</b>', '<b>冲压下限、焊接上限追赶竞品</b>'],
], col_widths=[USABLE_WIDTH * 0.30, USABLE_WIDTH * 0.30, USABLE_WIDTH * 0.40]))

story.append(PageBreak())

# ===== SECTION 6: Candidate Expectations =====
story.append(Paragraph('六、候选人预期分析', h1_style))

story.append(Paragraph('6.1 薪资预期', h2_style))
story.append(make_table([
    ['候选人类型', '预期月薪(TRY)', '预期薪资以外待遇'],
    ['伊斯坦布尔本地候选人（冲压背景）', '38,000-45,000', '社保+交通补贴+餐补'],
    ['伊斯坦布尔本地候选人（焊接机器人专长）', '45,000-58,000', '同上+培训机会'],
    ['伊斯坦布尔本地候选人（涂装+机器人）', '42,000-55,000', '同上+轮班津贴'],
    ['被动候选人（当前在职，需挖角）', '+20-35%溢价', '需含签约奖金'],
    ['从德国回流候选人（罕见）', '80,000-100,000', '可能性极低'],
], col_widths=[USABLE_WIDTH * 0.40, USABLE_WIDTH * 0.25, USABLE_WIDTH * 0.35]))

callout2 = Table([[Paragraph(
    '<b>签约金：</b>高级候选人可接受 50,000-100,000 TRY 一次性签约奖。', callout_style)]],
    colWidths=[USABLE_WIDTH])
callout2.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#fff5f5')),
    ('LEFTPADDING', (0, 0), (-1, -1), 10),
    ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ('TOPPADDING', (0, 0), (-1, -1), 8),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ('LINEABOVE', (0, 0), (-1, -1), 2, ACCENT),
]))
story.append(Spacer(1, 4))
story.append(callout2)
story.append(Spacer(1, 8))

story.append(Paragraph('6.2 候选人关注的非薪资因素（按优先级排序）', h2_style))
story.append(make_table([
    ['优先级', '因素', '说明'],
    ['高', '<b>工作稳定性</b>',
     '土耳其通胀高企(2026年仍处高位)，候选人极度关注长期就业保障'],
    ['高', '<b>职业发展路径</b>',
     '新公司是否提供明确晋升通道？Habas作为新品牌，这一点是关键卖点'],
    ['中', '培训与技术成长',
     '焊接/涂装机器人技能需持续更新，候选人看重是否有系统性培训'],
    ['中', '轮班制接受度',
     '制造业组长通常需倒班，夜班津贴、周末加班费是必须明确的'],
    ['低', '英语使用场景',
     '英文能力强的候选人期望在国际化环境中使用英语，会提高其薪资预期'],
    ['低', '交通便利性',
     'Manisa工厂距伊斯坦布尔约4小时车程，需明确工作地点'],
], col_widths=[USABLE_WIDTH * 0.13, USABLE_WIDTH * 0.25, USABLE_WIDTH * 0.62]))

story.append(Paragraph('6.3 候选人筛选期望清单', h2_style))
screening = [
    '第一轮：HR电话面试（30分钟）',
    '第二轮：技术主管面试（1小时）- 现场实操/案例分析',
    '第三轮：工厂现场参观+生产线主管面试',
    '可能含技能测试（焊接编程/涂装缺陷识别/冲压参数优化）',
    '背景调查（土耳其汽车行业圈子小，口碑很重要）',
]
for i, s in enumerate(screening, 1):
    story.append(Paragraph(f'{i}. {s}', bullet_style))

story.append(PageBreak())

# ===== SECTION 7: Candidate Profile & Tagging =====
story.append(Paragraph('七、候选人画像与标签系统', h1_style))

story.append(Paragraph(
    '<b>每个候选人根据经验、技能、资质三个维度进行标签分类，用于快速筛选与薪资定级。</b>', body_style))
story.append(Spacer(1, 8))

# --- Press Dept Team Leader ---
story.append(Paragraph('7.1.1 冲压部门组长 - 能力标签', h3_style))
story.append(make_table([
    ['标签', '含义', '匹配薪资区间', '占比估算'],
    ['[P-PRIME]<br/>资深冲压组长',
     '8年+冲压经验，精通G1线+多品牌模具，OEE管理优秀',
     '45,000-48,000 TRY', '15%'],
    ['[P-CORE]<br/>核心冲压组长',
     '5-8年经验，独立管理冲压线，熟悉模具更换与废料控制',
     '40,000-44,000 TRY', '35%'],
    ['[P-JUNIOR]<br/>初级冲压组长',
     '3-5年经验，可操作冲压线，需模具培训提升',
     '38,000-40,000 TRY', '30%'],
    ['[P-TRANSFER]<br/>转行候选人',
     '非汽车制造业但有机械加工背景，需再培训',
     '< 38,000 TRY', '20%'],
], col_widths=[USABLE_WIDTH * 0.20, USABLE_WIDTH * 0.35, USABLE_WIDTH * 0.28, USABLE_WIDTH * 0.17]))

# --- Body Welding Team Leader ---
story.append(Paragraph('7.1.2 车身焊接组长 - 能力标签', h3_style))
story.append(make_table([
    ['标签', '含义', '匹配薪资区间', '占比估算'],
    ['[W-EXPERT]<br/>焊接机器人专家',
     'Fanuc+Yaskawa+Kuka三品牌精通，8年+，能独立编程调试',
     '52,000-55,000 TRY', '8%'],
    ['[W-ROBOT]<br/>焊接机器人熟练工',
     '精通1-2个品牌机器人，5年+焊接经验，能基本编程',
     '47,000-52,000 TRY', '20%'],
    ['[W-LEAD]<br/>焊接线组长',
     '传统焊接经验丰富(气保焊/夹具)，机器人经验有限',
     '43,000-47,000 TRY', '30%'],
    ['[W-TRAINEE]<br/>焊接潜力股',
     '3年+汽车焊接经验，愿意学习机器人编程',
     '40,000-43,000 TRY', '42%'],
], col_widths=[USABLE_WIDTH * 0.20, USABLE_WIDTH * 0.35, USABLE_WIDTH * 0.28, USABLE_WIDTH * 0.17]))

# --- Paint Shop Team Leader ---
story.append(Paragraph('7.1.3 车身涂装组长 - 能力标签', h3_style))
story.append(make_table([
    ['标签', '含义', '匹配薪资区间', '占比估算'],
    ['[PT-MASTER]<br/>涂装工艺大师',
     'ED前处理+Yaskawa机器人+全流程缺陷诊断，8年+',
     '50,000-52,000 TRY', '10%'],
    ['[PT-ROBOT]<br/>涂装机器人专长',
     '精通Yaskawa涂装机器人编程调试，5年+',
     '46,000-50,000 TRY', '18%'],
    ['[PT-CHEM]<br/>化学品工艺专长',
     '精通前处理/ED/烘烤曲线，涂装缺陷识别强，机器人一般',
     '42,000-46,000 TRY', '28%'],
    ['[PT-STANDARD]<br/>标准涂装组长',
     '涂装线管理经验5年+，基础工艺熟悉，化危品管理到位',
     '40,000-42,000 TRY', '44%'],
], col_widths=[USABLE_WIDTH * 0.20, USABLE_WIDTH * 0.35, USABLE_WIDTH * 0.28, USABLE_WIDTH * 0.17]))

# --- Comprehensive Profile Tags ---
story.append(Paragraph('7.2 候选人综合画像标签', h2_style))
story.append(make_table([
    ['标签', '定义', '适用岗位'],
    ['<b>[BIG-3]</b>', '来自Ford Otosan/Mercedes/Tofas——行业头部背景，竞争力强但薪资预期高', '全部'],
    ['<b>[ENGLISH]</b>', '英语流利（B2+）——可英文技术沟通，薪资预期+10-15%', '全部'],
    ['<b>[CERTIFIED]</b>', '持有IATF 16949/ISO 45001证书——合规能力强，减少入职培训成本', '全部'],
    ['<b>[ROBOT-MULTI]</b>', '多品牌机器人精通——Fanuc/Yaskawa/Kuka至少两个品牌', '焊接/涂装'],
    ['<b>[EV-EXPERIENCED]</b>', '有EV产线经验——新能源车型生产经验，未来溢价资产', '焊接/涂装'],
    ['<b>[BURSA-POOL]</b>', 'Bursa地区候选人——Tofas裁员释放，愿意搬迁至伊斯坦布尔', '全部'],
    ['<b>[LOCAL-IST]</b>', '伊斯坦布尔本地候选人——无需搬迁成本，稳定性较高', '全部'],
    ['<b>[GERMANY-RETURN]</b>', '德国回流人才——薪资预期极高(80K-100K TRY)，通常不作为首选', '全部'],
], col_widths=[USABLE_WIDTH * 0.25, USABLE_WIDTH * 0.55, USABLE_WIDTH * 0.20]))

story.append(PageBreak())

# --- Generic Profile ---
story.append(Paragraph('7.3 三岗位通用画像', h2_style))
story.append(make_table([
    ['维度', '画像'],
    ['年龄', '28-42岁'],
    ['学历', '机械工程/工业工程/材料工程 本科（学士）'],
    ['工作经验', '5-10年汽车制造业经验，其中至少2年担任Team Leader或Vardiya Amiri（轮班主管）'],
    ['地域', '伊斯坦布尔/科贾埃利/布尔萨居住，或愿意搬迁至伊斯坦布尔/Manisa'],
    ['语言', '土耳其语母语，英语初级到中级（可阅读技术文档，基础沟通）'],
    ['证书', 'IATF 16949内审员、ISO 45001(OHS)、5S/Kaizen认证'],
    ['性别', '文档要求"preferably male"——土耳其制造业传统上男性主导，但法律上不能作为排除条件'],
    ['职业动机', '寻求更大的自主权、新品牌成长带来的快速晋升机会、技术能力提升'],
], col_widths=[USABLE_WIDTH * 0.25, USABLE_WIDTH * 0.75]))

# --- Per-job Specific Profile ---
story.append(Paragraph('7.4 各岗位差别画像', h2_style))

story.append(Paragraph('7.4.1 冲压部门组长', h3_style))
story.append(make_table([
    ['维度', '画像'],
    ['典型背景', '曾在TOFAS(Bursa)、Ford Otosan(Kocaeli)或Mercedes-Benz Turk(伊斯坦布尔)担任冲压线组长或生产技术员'],
    ['核心技能', '模具成型技术、G1冲压线编程、OEE管理、废料率控制'],
    ['行业经验', '偏重型卡车/商用车冲压经验更佳（Habas生产卡车和客车）'],
    ['当前薪资', '35,000-42,000 TRY/月'],
    ['跳槽诱因', '薪资涨幅20%+、晋升为部门负责人可能性'],
], col_widths=[USABLE_WIDTH * 0.25, USABLE_WIDTH * 0.75]))

story.append(Paragraph('7.4.2 车身焊接组长', h3_style))
story.append(make_table([
    ['维度', '画像'],
    ['典型背景', 'Ford Otosan焊接车间、TOFAS焊接线、Otokar车身车间5年以上经验'],
    ['核心技能', '<b>Fanuc/Yaskawa/Kuka机器人编程与调试</b>（最稀缺）、气保焊工艺、气动焊接夹具维护'],
    ['行业经验', '商用车/客车焊接经验优先'],
    ['当前薪资', '40,000-50,000 TRY/月'],
    ['跳槽诱因', '薪资涨幅25-30%、掌握多品牌机器人系统的能力提升'],
    ['招聘难度', '<font color="#c53030"><b>最难填补——行业平均招聘周期95-120天</b></font>'],
], col_widths=[USABLE_WIDTH * 0.25, USABLE_WIDTH * 0.75]))

story.append(Paragraph('7.4.3 车身涂装组长', h3_style))
story.append(make_table([
    ['维度', '画像'],
    ['典型背景', '汽车OEM涂装车间5年+经验（Mercedes-Benz Hosdere、Ford Otosan或Otokar）'],
    ['核心技能', 'ED前处理、Yaskawa涂装机器人操作、喷涂缺陷诊断（流挂/橘皮/针孔）、烘烤曲线控制、化危品管理'],
    ['行业经验', '客车/商用车涂装更佳（与乘用车涂装工艺有差异）'],
    ['当前薪资', '37,000-47,000 TRY/月'],
    ['跳槽诱因', '薪资涨幅20-25%、新建产线从头搭建的机会（Habas Manisa工厂为新建）'],
    ['招聘难度', '<b>中等偏难</b>——涂装工艺人才稀缺但不如焊接机器人极度稀缺'],
], col_widths=[USABLE_WIDTH * 0.25, USABLE_WIDTH * 0.75]))

story.append(Paragraph('7.5 候选人来源渠道', h2_style))
story.append(make_table([
    ['来源', '效果评估', '说明'],
    ['<b>Kariyer.net</b>', '中等', '土耳其最大招聘平台，适合主动求职者'],
    ['<b>LinkedIn Turkey</b>', '良好', '适合被动候选人触达，高端技术人才活跃'],
    ['ISKUR（土耳其就业局）', '较低', '适合基层岗位，组长级不太适用'],
    ['<b>Headhunting (KiTalent类)</b>', '最佳', '被动候选人占75-85%，猎头渠道最有效'],
    ['<b>Tofas裁员释放人才</b>', '良好', '短期内Bursa地区有一批有经验的组长级候选人'],
    ['制造业职业培训学校', '低', '需培训6-12个月方能上岗，不适合即时需求'],
    ['德国回流土耳其人才', '低', '极少数，通常薪资预期远超本地市场'],
], col_widths=[USABLE_WIDTH * 0.32, USABLE_WIDTH * 0.18, USABLE_WIDTH * 0.50]))

story.append(PageBreak())

# ===== SECTION 8: Recruitment Strategy =====
story.append(Paragraph('八、招聘策略建议', h1_style))

story.append(Paragraph('8.1 薪资策略', h2_style))
story.append(make_table([
    ['岗位', '策略', '建议月薪(TRY)'],
    ['冲压部门组长', '<b>市场中位数（P50）</b> + 新品牌溢价(5%)', '40,000-45,000'],
    ['车身焊接组长', '<b>市场高位（P70-P75）</b> + 机器人稀缺溢价(15%)', '48,000-55,000'],
    ['车身涂装组长', '<b>市场中上位（P60）</b> + 工艺溢价(10%)', '43,000-50,000'],
], col_widths=[USABLE_WIDTH * 0.30, USABLE_WIDTH * 0.45, USABLE_WIDTH * 0.25]))

story.append(Paragraph('8.2 按候选人标签的差异化定价', h2_style))
story.append(make_table([
    ['候选人标签组合', '建议薪资调整'],
    ['[BIG-3] + [ROBOT-MULTI] + [CERTIFIED]', '<b>+15-20% 顶格薪资</b>'],
    ['[BIG-3] + [CERTIFIED]', '+10% 溢价'],
    ['[ENGLISH] + [CERTIFIED]', '+8-12% 溢价'],
    ['[LOCAL-IST]', '基准水平，无需搬迁补贴'],
    ['[BURSA-POOL]', '基准+搬迁补贴（一次性50,000-80,000 TRY）'],
    ['[GERMANY-RETURN]', '<font color="#a0aec0">不推荐（预期远超预算）</font>'],
], col_widths=[USABLE_WIDTH * 0.55, USABLE_WIDTH * 0.45]))

story.append(Paragraph('8.3 差异化吸引力（弥补Habas品牌劣势）', h2_style))
story.append(make_table([
    ['Habas劣势', '弥补方案'],
    ['品牌知名度低', '强调"新建工厂+全新生产线"的参与感和成长空间'],
    ['无法匹配薪资顶线', '提供灵活福利包（交通补贴+免费午餐+轮班津贴+培训机会）'],
    ['Manisa工厂地点偏远', '确认实际工作地点，提供通勤班车或住房补贴'],
    ['无行业经验背书', '强调集团68年工业经验（钢铁、能源领域），不只有汽车业'],
], col_widths=[USABLE_WIDTH * 0.30, USABLE_WIDTH * 0.70]))

story.append(Paragraph('8.4 应对候选人常见顾虑的沟通话术方向', h2_style))
concerns = [
    ('"Habas是家新公司，靠谱吗？"',
     '强调68年集团历史、自建Manisa工厂（100,000m²）、收购本田土耳其工厂、已量产并交付伊斯坦布尔公交'),
    ('"薪资比Ford Otosan低。"',
     '强调职业发展速度、新建工厂的管理层晋升空间、提供技能培训（多品牌机器人系统学习机会）'),
    ('"工作地点在哪？"',
     '明确：如岗位在Manisa，需提供Manisa城区通勤方案；如岗位在Kartal总部，说明冲压/焊接/涂装车间具体位置'),
]
for q, a in concerns:
    story.append(Paragraph(f'<b>{q}</b>', body_style))
    story.append(Paragraph(f'→ {a}', bullet_style))
    story.append(Spacer(1, 2))

story.append(Paragraph('8.5 招聘Timeline建议', h2_style))
story.append(make_table([
    ['阶段', '时间', '行动'],
    ['招聘启动', '第1-2周', 'Kariyer.net+LinkedIn发布，猎头启动寻访'],
    ['候选人筛选', '第3-4周', '重点筛选[BIG-3][ROBOT-MULTI][CERTIFIED]标签候选人'],
    ['面试评估', '第5-8周', '焊接/涂装岗安排现场技能测试'],
    ['Offer发放', '第9-10周', '焊接岗建议出价上限，压缩决策时间'],
    ['预期到岗', '第12-14周', '考虑候选人离职通知期（土耳其标准4-8周）'],
], col_widths=[USABLE_WIDTH * 0.20, USABLE_WIDTH * 0.18, USABLE_WIDTH * 0.62]))

callout3 = Table([[Paragraph(
    '<b>注意：</b>焊接组长招聘周期95-120天，<b>建议在Manisa工厂投产前至少4个月启动招聘。</b>',
    callout_style)]], colWidths=[USABLE_WIDTH])
callout3.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#fff5f5')),
    ('LEFTPADDING', (0, 0), (-1, -1), 10),
    ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ('TOPPADDING', (0, 0), (-1, -1), 8),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ('LINEABOVE', (0, 0), (-1, -1), 2, ACCENT),
]))
story.append(Spacer(1, 4))
story.append(callout3)
story.append(Spacer(1, 12))

# Disclaimer
story.append(Paragraph(
    '<b>免责说明：</b>本报告薪资数据来源于 ElemanBuldum、Payscale、Glassdoor 等公开薪资调查平台'
    '（2026年7月更新），以及 KiTalent、Wide and Wise 等行业招聘顾问机构的市场分析。'
    '宏观数据来源于土耳其统计局（TUIK）、世界银行、GlobalCostData 等。实际薪资受候选人个体条件、'
    '谈判能力、市场供需波动、汇率变动等多因素影响，<b>建议作为参考基准使用</b>。',
    disclaimer_style))

# ===== Build the PDF =====
output_path = "/Users/yoyo/WorkBuddy/2026-07-29-13-50-49/Habas_伊斯坦布尔_组长岗位薪资分析报告.pdf"

# Header/footer callback
def add_page_decorations(canvas, doc):
    canvas.saveState()
    # Header
    canvas.setFont('STSong-Light', 8)
    canvas.setFillColor(colors.HexColor('#8899aa'))
    canvas.drawCentredString(PAGE_WIDTH / 2, PAGE_HEIGHT - 12 * mm,
                             'HABAS · 伊斯坦布尔生产组长薪资分析报告 · July 2026')
    canvas.setStrokeColor(colors.HexColor('#e2e8f0'))
    canvas.setLineWidth(0.3)
    canvas.line(LEFT_MARGIN, PAGE_HEIGHT - 15 * mm, PAGE_WIDTH - RIGHT_MARGIN, PAGE_HEIGHT - 15 * mm)
    # Footer
    canvas.setFont('STSong-Light', 8)
    canvas.setFillColor(colors.HexColor('#8899aa'))
    canvas.drawCentredString(PAGE_WIDTH / 2, 10 * mm, f'Page {doc.page}')

doc = SimpleDocTemplate(
    output_path,
    pagesize=A4,
    leftMargin=LEFT_MARGIN,
    rightMargin=RIGHT_MARGIN,
    topMargin=TOP_MARGIN,
    bottomMargin=BOTTOM_MARGIN,
    title='Habas Team Leader Salary Report - Istanbul',
    author='Yoyo',
)

doc.build(story, onFirstPage=add_page_decorations, onLaterPages=add_page_decorations)
size = os.path.getsize(output_path)
print(f"PDF OK: {output_path}")
print(f"Size: {size} bytes ({size/1024:.1f} KB)")

from PyPDF2 import PdfReader
r = PdfReader(output_path)
print(f"Pages: {len(r.pages)}")
