"""华伽电商 · 美国TikTok电商业务负责人薪酬带宽报告 - 客户版PDF（SimHei+Helvetica混合版）"""
import os
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.units import mm
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

FONT_PATH = '/Users/yoyo/WorkBuddy/2026-07-29-13-50-49/fonts/SimHei.ttf'
pdfmetrics.registerFont(TTFont('SimHei', FONT_PATH))

PRIMARY = colors.HexColor('#1a365d')
ACCENT = colors.HexColor('#c53030')
LIGHT_BG = colors.HexColor('#edf2f7')
ALT_BG = colors.HexColor('#f7fafc')
BORDER = colors.HexColor('#e2e8f0')
TEXT_DARK = colors.HexColor('#000000')
TEXT_MUTED = colors.HexColor('#4a5568')
PW, PH = A4
LM = 16 * mm; RM = 16 * mm; TM = 22 * mm; BM = 22 * mm
UW = PW - LM - RM

# ===== 币种符号兼容层 =====
CURRENCY_FALLBACK = {
    '₱': 'PHP', '₩': 'KRW', '₹': 'INR', '₫': 'VND', '฿': 'THB', '₺': 'TRY',
    '₴': 'UAH', '₪': 'ILS', '₦': 'NGN', '₸': 'KZT', '₽': 'RUB', '₼': 'AZN',
    '₾': 'GEL', '₲': 'PYG', '₡': 'CRC', '₨': 'PKR', '₮': 'MNT', '₣': 'CHF', '₿': 'BTC',
}
LATIN_SAFE_SYMBOLS = ['$', '£', '¥', '€', '¢']

def fix_currency(text):
    text = str(text)
    for sym, code in CURRENCY_FALLBACK.items():
        text = text.replace(sym + ' ', code + ' ').replace(sym, code + ' ')
    for sym in LATIN_SAFE_SYMBOLS:
        text = text.replace(sym, f'<font face="Helvetica">{sym}</font>')
    for p in ['—', '–', '·']:
        text = text.replace(p, f'<font face="Helvetica">{p}</font>')
    return text

h1 = ParagraphStyle('h1', fontName='SimHei', fontSize=17, leading=24, textColor=PRIMARY, spaceBefore=18, spaceAfter=10)
h2 = ParagraphStyle('h2', fontName='SimHei', fontSize=14, leading=20, textColor=PRIMARY, spaceBefore=14, spaceAfter=6)
bd = ParagraphStyle('bd', fontName='SimHei', fontSize=11, leading=17, textColor=TEXT_DARK, spaceBefore=0, spaceAfter=4)
ct = ParagraphStyle('ct', fontName='SimHei', fontSize=10.5, leading=16, textColor=TEXT_DARK, leftIndent=8, rightIndent=8, spaceBefore=4, spaceAfter=4, backColor=colors.HexColor('#fff5f5'), borderPadding=6, borderWidth=0)
ch = ParagraphStyle('ch', fontName='SimHei', fontSize=10, leading=15, textColor=PRIMARY, spaceBefore=0, spaceAfter=0)
cs = ParagraphStyle('cs', fontName='SimHei', fontSize=10, leading=15, spaceBefore=0, spaceAfter=0)
dc = ParagraphStyle('dc', fontName='SimHei', fontSize=9, leading=14, textColor=TEXT_MUTED, spaceBefore=12, spaceAfter=0)

def T(rows, cw=None, keep_together=False):
    if not rows: return None
    n = len(rows[0])
    cw = cw or [UW/n]*n
    td = []
    for i, row in enumerate(rows):
        nr = []
        for cell in row:
            t = fix_currency(str(cell).strip().replace('\n','<br/>'))
            nr.append(Paragraph(f'<b>{t}</b>' if i==0 else t, ch if i==0 else cs))
        td.append(nr)
    t = Table(td, colWidths=cw, repeatRows=1)
    t.setStyle(TableStyle([
        ('FONTNAME',(0,0),(-1,-1),'SimHei'),
        ('FONTSIZE',(0,0),(-1,0),10), ('FONTSIZE',(0,1),(-1,-1),10),
        ('BACKGROUND',(0,0),(-1,0),LIGHT_BG), ('TEXTCOLOR',(0,0),(-1,0),PRIMARY),
        ('ALIGN',(0,0),(-1,0),'LEFT'), ('VALIGN',(0,0),(-1,-1),'TOP'),
        ('TEXTCOLOR',(0,1),(-1,-1),TEXT_DARK),
        ('GRID',(0,0),(-1,-1),0.4,BORDER), ('BOX',(0,0),(-1,-1),0.6,PRIMARY),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white, ALT_BG]),
        ('TOPPADDING',(0,0),(-1,-1),5), ('BOTTOMPADDING',(0,0),(-1,-1),5),
        ('LEFTPADDING',(0,0),(-1,-1),6), ('RIGHTPADDING',(0,0),(-1,-1),6),
    ]))
    if keep_together:
        return KeepTogether(t)
    return t

def callout(text):
    return Paragraph(fix_currency(text), ct)

def page_deco(canvas, doc):
    canvas.saveState()
    canvas.setFont('SimHei', 8)
    canvas.setFillColor(colors.HexColor('#8899aa'))
    canvas.drawCentredString(PW/2, PH - 12*mm, '华伽电商 · 美国TikTok电商业务负责人薪酬带宽报告 · 2026.08')
    canvas.setStrokeColor(colors.HexColor('#e2e8f0'))
    canvas.setLineWidth(0.3)
    canvas.line(LM, PH - 15*mm, PW - RM, PH - 15*mm)
    canvas.setFont('SimHei', 8)
    canvas.drawCentredString(PW/2, 10*mm, f'第 {doc.page} 页')
    canvas.restoreState()

story = []
output = "/Users/yoyo/WorkBuddy/2026-07-29-13-50-49/华伽_美国TikTok电商业务负责人薪酬带宽报告_客户版.pdf"

# ===== COVER =====
story.append(Spacer(1, 50))
story.append(Paragraph('HUAGIA', ParagraphStyle('lg', fontName='SimHei', fontSize=44, leading=52, textColor=PRIMARY, alignment=TA_CENTER, spaceAfter=6)))
story.append(Paragraph('华伽电商', ParagraphStyle('st', fontName='SimHei', fontSize=15, leading=22, textColor=TEXT_MUTED, alignment=TA_CENTER, spaceAfter=2)))
story.append(Paragraph('HuaJia E-commerce', ParagraphStyle('st2', fontName='SimHei', fontSize=10, leading=14, textColor=TEXT_MUTED, alignment=TA_CENTER, spaceAfter=30)))
hr = Table([['']], colWidths=[UW*0.4], rowHeights=[2])
hr.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),ACCENT)])); hr.hAlign='CENTER'
story.append(hr)
story.append(Spacer(1, 28))
story.append(Paragraph('美国 · 洛杉矶 / 纽约', ParagraphStyle('tl', fontName='SimHei', fontSize=24, leading=32, textColor=PRIMARY, alignment=TA_CENTER, spaceAfter=6)))
story.append(Paragraph('TikTok 电商业务负责人薪酬带宽报告', ParagraphStyle('tl2', fontName='SimHei', fontSize=21, leading=30, textColor=PRIMARY, alignment=TA_CENTER, spaceAfter=10)))
story.append(Paragraph('Salary Band Analysis - Head of US TikTok E-commerce', ParagraphStyle('en', fontName='SimHei', fontSize=11, leading=16, textColor=TEXT_MUTED, alignment=TA_CENTER, spaceAfter=30)))
story.append(Paragraph('Head of US E-commerce (TikTok Shop)', ParagraphStyle('pos', fontName='SimHei', fontSize=13, leading=20, textColor=TEXT_DARK, alignment=TA_CENTER, spaceAfter=30)))
meta = T([['报告日期','2026年8月19日'],['数据口径','税前 GROSS'],['工作地点','美国 洛杉矶/纽约（可常驻）'],['输出','用友薪福社 · 出海人力资源']], cw=[UW*0.30, UW*0.70])
story.append(meta)
story.append(PageBreak())

# ===== 一、宏观 =====
story.append(Paragraph('一、宏观经济参考参数', h1))
story.append(Paragraph('1.1 美国 / 洛杉矶 / 纽约', h2))
story.append(T([['指标','数值','备注'],
    ['联邦最低工资','$7.25/小时','多年未变'],
    ['<b>全美平均年薪（社评工资）</b>','<b>~$65,000/年</b>','中位数更低'],
    ['洛杉矶平均年薪','~$78,000-85,000',''],
    ['纽约平均年薪','~$90,000-100,000','全美最高梯队'],
    ['洛杉矶单人月生活成本','$3,800-5,200','含一居室 $2,200-3,000'],
    ['纽约单人月生活成本','$4,500-6,500','曼哈顿一居室 $3,500-4,500'],
    ['综合税率（联邦+州）','30-38%（年薪$150K+档）','加州/纽约州高税州'],
    ['雇主成本','+7.8-8.5%','SS 6.2% + Medicare 1.45%'],
], cw=[UW*0.34, UW*0.34, UW*0.32], keep_together=True))
story.append(Spacer(1,4))

story.append(Paragraph('二、分析维度框架', h1))
story.append(T([['维度','美国 TikTok 电商业务负责人'],
    ['岗位对标','Head of US E-commerce (TikTok Shop) / eCommerce Director / AVP eCommerce'],
    ['行业基准','跨境电商/社交电商（TikTok Shop / TAP / 直播电商）'],
    ['经验要求','5年+跨境电商，3年+团队管理'],
    ['核心溢价','<b>TikTok Shop 美国市场 0→1 搭建经验</b> + 达人生态 + 广告投放全链路'],
    ['语言要求','英语流利（工作语言），西班牙语优先'],
    ['驻地','base 洛杉矶/纽约（美国本地或可常驻）'],
    ['稀缺度','5/5 0-1 搭建 + 达人生态 + 全链路运营复合'],
    ['薪酬结构','底薪 + 绩效 + 年终奖 + 股权'],
], cw=[UW*0.18, UW*0.82], keep_together=True))
story.append(PageBreak())

# ===== 三、薪资建议 =====
story.append(Paragraph('三、薪资建议', h1))
story.append(Paragraph('3.1 客户自报价 vs 市场校准', h2))
story.append(T([['项目','客户报价','市场校准','判断'],
    ['基础月薪','¥35,000-70,000<br/>($4,800-9,700)','<b>¥45,000-75,000<br/>($6,600-11,050)</b>','⬆️ 下限偏低'],
    ['年度综合','¥60万-150万<br/>($88K-221K)','<b>¥100万-180万<br/>($147K-265K)</b>','⬆️ 下限偏低，上限接近合理'],
], cw=[UW*0.16, UW*0.28, UW*0.28, UW*0.28], keep_together=True))
story.append(callout('<b>修正建议：</b>客户报价下限（$88K）显著低于美国 eCommerce Director 市场 P25（base $130K），难以吸引有 TikTok Shop 0-1 搭建经验的稀缺候选人；上限 $221K 接近市场但略低于 AVP/Head 级（$220-250K）。建议上调下限、保留上限。'))
story.append(Spacer(1,6))

story.append(Paragraph(fix_currency('<b>建议底薪：¥45,000 - ¥75,000/月（$6,600 - $11,050/月，GROSS）</b>'), bd))
story.append(Spacer(1,2))
story.append(T([['项目','金额','约合CNY/年','说明'],
    ['<b>建议底薪（月）</b>','<b>¥45,000-75,000<br/>($6,600-11,050)</b>','<b>¥54万-90万</b>','年薪 $79K-133K'],
    ['NET税后（综合税率~35%）','¥29,000-49,000/月','¥35万-59万','到手约65%'],
    ['雇主总成本（×1.08）','¥48,600-81,000/月','¥58万-97万','SS+Medicare+失业税'],
    ['<b>建议总包（底薪+绩效+奖金+股权）</b>','<b>$147K-265K/年</b>','<b>¥100万-180万/年</b>','绩效奖金占20-30%，股权另计'],
    ['<b>市场定位</b>','<b>P65-P85</b>','','Head/AVP 级（高于一般 Director）'],
], cw=[UW*0.24, UW*0.26, UW*0.22, UW*0.28], keep_together=True))
story.append(callout('<b>薪资锚点：</b>建议总包 = 全美平均年薪（$65K）的 <b>2.3-4.1倍</b> = eCommerce Director 市场中位（$150-185K base）的 <b>1.1-1.6倍</b>；对标 TikTok Shop 相关岗位（字节跳动美国：品类经理 $135K、电商战略经理 $228-230K、全球电商解决方案经理 $480K）。'))
story.append(Spacer(1,6))

story.append(Paragraph('3.3 分候选人定价', h2))
story.append(T([['候选人类型','建议底薪','年度总包','说明'],
    ['<b>TikTok Shop 0→1 搭建经验（稀缺）</b>','<b>¥65,000-75,000/月</b>','<b>¥150万-180万</b>','稀缺溢价，对标 AVP 级'],
    ['资深电商负责人（5年+出海/社媒）','¥55,000-70,000/月','¥120万-160万','P70-P85'],
    ['有美国本土经验的华人（可常驻）','¥50,000-65,000/月','¥110万-150万','中英双语+驻美'],
    ['美国本地人（英语母语）','$150,000-185,000/年','$180K-250K','按美元口径'],
], cw=[UW*0.30, UW*0.22, UW*0.20, UW*0.28], keep_together=True))
story.append(PageBreak())

# ===== 四、竞品对标 =====
story.append(Paragraph('四、竞品与市场对标', h1))
story.append(T([['对标','年薪(USD)','说明'],
    ['eCommerce Director（美国，2026）','$130K-185K base','eCommerce Placement 2026'],
    ['<b>VP E-commerce（纽约）</b>','<b>$250K base + $39K bonus</b>','SalaryExpert/ERI 2026.08'],
    ['VP Ecommerce（纽约，Payscale）','$215K base（$150K-253K）','15样本'],
    ['VP Ecommerce（洛杉矶，中段）','$150K base（$123K-160K）','Payscale'],
    ['<b>AVP/Head of eCommerce（洛杉矶）</b>','<b>$220K-250K</b>','Glassdoor 招聘实价'],
    ['TikTok Shop 品类经理（字节美国）','$135K','媒体披露'],
    ['TikTok Shop 电商战略经理','$228K-230K','媒体披露'],
    ['全球电商解决方案经理（字节）','$480K','媒体披露'],
    ['<b>华伽建议（市场校准后）</b>','<b>$147K-265K（总包）</b>','P65-P85，Head/AVP 级'],
], cw=[UW*0.40, UW*0.24, UW*0.36], keep_together=True))
story.append(Spacer(1,4))
story.append(callout('<b>定位说明：</b>华伽岗位是"从 0 到 1 搭建美国 TikTok 业务"的全责负责人（GMV/利润总负责），对标美国市场 eCommerce Director 高段至 AVP/Head 级。<b>TikTok Shop 0→1 搭建经验 + 达人生态资源 + 双语能力</b>是稀缺溢价点。'))
story.append(PageBreak())

# ===== 五、候选人预期 =====
story.append(Paragraph('五、候选人预期分析', h1))
story.append(T([['候选人类型','薪资预期','期望总包','核心诉求'],
    ['TikTok Shop 0→1 资深操盘手','$140K-180K base','$200K-300K','0-1 经历认可+股权激励'],
    ['跨境电商总监（国内出海）','¥40K-60K/月','¥100万-180万','美国驻地+团队授权+股权'],
    ['美国本地电商负责人','$150K-185K base','$200K-280K','平台背书+稳定增长'],
    ['驻美华人（中英双语）','$120K-150K base','$160K-220K','中国供应链协同+成长空间'],
], cw=[UW*0.24, UW*0.20, UW*0.20, UW*0.36], keep_together=True))
story.append(Spacer(1,4))
story.append(Paragraph('非薪资关注点（排序）', h2))
story.append(Paragraph('1. 股权/期权激励结构（0-1 业务的高风险高回报属性）', bd))
story.append(Paragraph('2. 团队组建授权（本地招聘+远程团队）', bd))
story.append(Paragraph('3. 美国驻地支持（签证/绿卡协助、生活安置）', bd))
story.append(Paragraph('4. 集团供应链协同能力（华伽产品与供应链支撑）', bd))
story.append(PageBreak())

# ===== 六、招聘策略 =====
story.append(Paragraph('六、招聘策略建议', h1))
story.append(T([['策略','说明'],
    ['定位 Head/AVP 级，非普通 Director','全责 GMV/利润，对标 $220K+ 市场；总包给到 $147K-265K'],
    ['稀缺人才优先渠道','TikTok 生态圈（MCN/达人机构/代运营团队）、字节离职电商团队、Shein/Temu 美国团队'],
    ['华人+美国本地双线','华人看重"中国供应链+美国市场"双向协同；美国本地看重平台与授权'],
    ['股权激励前置沟通','0-1 业务需明确股权/期权比例与归属周期（建议对标字节 3 年归属）'],
    ['签证支持明确','美国工作签证/绿卡协助是驻美岗的关键竞争力'],
], cw=[UW*0.26, UW*0.74], keep_together=True))
story.append(Spacer(1,4))
story.append(Paragraph('核心卖点（对外呈现）', h2))
story.append(Paragraph('1. 从 0 到 1 操盘美国 TikTok 电商业务的完整授权（GMV/利润负总责）', bd))
story.append(Paragraph('2. 集团供应链/产品/品牌全链条支持，出海确定性', bd))
story.append(Paragraph('3. 股权激励 + 绩效奖金的结构化回报', bd))
story.append(Spacer(1,8))
story.append(Paragraph(fix_currency('免责说明：本报告薪资数据来源于 SalaryExpert/ERI、Payscale、Glassdoor、eCommerce Placement 2026、前程无忧/科锐国际/跨境眼行业调研（2026年8月更新）。宏观数据来源于美国劳工统计局、中国外汇交易中心。汇率采用 2026.08.19 中间价（1 USD=6.7854 CNY，即期约 6.74）。实际薪资受候选人条件、业务阶段、股权结构、汇率波动等多因素影响，建议作为参考基准使用。所有薪资区间均为 GROSS 税前。'), dc))

doc = SimpleDocTemplate(output, pagesize=A4,
    leftMargin=LM, rightMargin=RM, topMargin=TM, bottomMargin=BM,
    title='HuaJia Head of US TikTok E-commerce Salary Band Report')
doc.build(story, onFirstPage=page_deco, onLaterPages=page_deco)
sz = os.path.getsize(output)
print(f"Client PDF OK: {output} ({sz/1024:.1f} KB)")
