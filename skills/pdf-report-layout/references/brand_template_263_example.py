"""263集团 · 新加坡大客户销售经理薪酬带宽报告 - 水印版PDF（复刻华伽 generate_huajia_pdf.py 排版格式）"""
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

# ===== 与华伽一致：配色 =====
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

# ===== 币种符号兼容层（与华伽一致） =====
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

# ===== 与华伽一致的样式体系 =====
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

# ===== 与华伽一致的页眉/页脚 =====
def page_deco(canvas, doc):
    canvas.saveState()
    canvas.setFont('SimHei', 8)
    canvas.setFillColor(colors.HexColor('#8899aa'))
    canvas.drawCentredString(PW/2, PH - 12*mm, '263集团 · 新加坡大客户销售经理薪酬带宽报告 · 2026.08.24')
    canvas.setStrokeColor(colors.HexColor('#e2e8f0'))
    canvas.setLineWidth(0.3)
    canvas.line(LM, PH - 15*mm, PW - RM, PH - 15*mm)
    canvas.setFont('SimHei', 8)
    canvas.drawCentredString(PW/2, 10*mm, f'第 {doc.page} 页')
    canvas.restoreState()

story = []
TMP_BASE = "/tmp/263_final_base.pdf"
OUTPUT_WM = "/Users/yoyo/WorkBuddy/2026-07-29-13-50-49/263集团_新加坡大客户销售经理薪酬带宽报告_水印版.pdf"

# ===== 封面（与华伽结构一致） =====
story.append(Spacer(1, 50))
story.append(Paragraph('NET263', ParagraphStyle('lg', fontName='SimHei', fontSize=44, leading=52, textColor=PRIMARY, alignment=TA_CENTER, spaceAfter=6)))
story.append(Paragraph('二六三集团', ParagraphStyle('st', fontName='SimHei', fontSize=15, leading=22, textColor=TEXT_MUTED, alignment=TA_CENTER, spaceAfter=2)))
story.append(Paragraph('Net263 Group', ParagraphStyle('st2', fontName='SimHei', fontSize=10, leading=14, textColor=TEXT_MUTED, alignment=TA_CENTER, spaceAfter=30)))
hr = Table([['']], colWidths=[UW*0.4], rowHeights=[2])
hr.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),ACCENT)])); hr.hAlign='CENTER'
story.append(hr)
story.append(Spacer(1, 28))
story.append(Paragraph('新加坡 · 远程办公', ParagraphStyle('tl', fontName='SimHei', fontSize=24, leading=32, textColor=PRIMARY, alignment=TA_CENTER, spaceAfter=6)))
story.append(Paragraph('大客户销售经理薪酬带宽报告', ParagraphStyle('tl2', fontName='SimHei', fontSize=21, leading=30, textColor=PRIMARY, alignment=TA_CENTER, spaceAfter=10)))
story.append(Paragraph('Salary Band Analysis - Key Account Manager (Telecom Wholesale)', ParagraphStyle('en', fontName='SimHei', fontSize=11, leading=16, textColor=TEXT_MUTED, alignment=TA_CENTER, spaceAfter=30)))
story.append(Paragraph('Key Account Manager (International Network Wholesale)', ParagraphStyle('pos', fontName='SimHei', fontSize=13, leading=20, textColor=TEXT_DARK, alignment=TA_CENTER, spaceAfter=30)))
meta = T([['报告日期','2026年8月24日'],['数据口径','税前 GROSS（本地雇佣）'],['工作地点','新加坡（远程办公）'],['输出','用友薪福社 · 中企出海人力资源服务']], cw=[UW*0.30, UW*0.70])
story.append(meta)
story.append(PageBreak())

# ===== 一、宏观 =====
story.append(Paragraph('一、宏观经济参考参数', h1))
story.append(Paragraph('1.1 新加坡', h2))
story.append(T([['指标','数值','备注'],
    ['中位月薪（含雇主CPF）','<b>S$5,775/月</b>','MOM 2026年2月官方数据'],
    ['合同口径中位月薪','S$4,936-5,500/月','劳动合同常见口径（不含雇主CPF）'],
    ['平均月薪','S$5,800-6,800/月','受金融/科技高薪拉高'],
    ['法定最低工资','无','渐进式工资PWM下限 S$1,600/月'],
    ['雇主CPF缴款','17%（雇员20%）','仅公民/PR；2026.1起上限S$8,000/月'],
    ['外籍EP','不缴CPF','收入全额现金化，无组屋/医疗补贴'],
    ['个人所得税','0-24%累进','首S$20,000免税；中产实际税率1-5%'],
    ['生活成本','单人舒适S$4,000-5,500/月','市中心一房S$3,000-4,500/月'],
    ['第13薪/奖金','AWS普遍+奖金约1.8个月','销售岗另有佣金'],
    ['汇率','<b>1 SGD = 5.3196 CNY</b>','2026.08.24央行中间价；即期5.2928'],
], cw=[UW*0.32, UW*0.34, UW*0.34], keep_together=True))
story.append(Spacer(1,4))

story.append(Paragraph('二、分析维度框架', h1))
story.append(T([['维度','263 大客户销售经理（电信Wholesale）'],
    ['岗位对标','Key Account Manager / Carrier Sales Manager / Wholesale Sales Manager（运营商批发业务）'],
    ['行业基准','电信运营商国际网络产品：Submarine Cable / IEPL / Global Internet Access / Cloud'],
    ['经验要求','3-5年+ 电信/通信运营商销售合作，尤其国际通信海缆销售'],
    ['核心溢价','<b>运营商 Wholesale 封闭圈子 + 海缆销售经验 + 中英双语</b>'],
    ['语言要求','中英双语流利（全英文商务谈判与方案撰写）'],
    ['驻地','新加坡（远程办公，覆盖泰国/越南/印尼/马来西亚）'],
    ['稀缺度','<b>5/5</b> 四重稀缺叠加（行业门槛+海缆+双语+区域）'],
    ['薪酬结构','基础 + 绩效奖金 + 销售佣金（变动占比高）'],
], cw=[UW*0.18, UW*0.82], keep_together=True))
story.append(PageBreak())

# ===== 三、薪资建议 =====
story.append(Paragraph('三、薪资建议', h1))
story.append(Paragraph('3.1 建议薪资带宽（月薪）', h2))
story.append(T([['候选人类型','建议月薪（S$）','约合CNY/月','P定位','说明'],
    ['<b>新加坡本地人<br/>（运营商/Wholesale背景，中英）</b>','<b>8,000-11,000</b>','<b>¥42,600-58,500</b>','P60-P75','主推，对标Singtel/NCS'],
    ['海缆/国际网络稀缺销售（资深）','9,000-12,500','¥47,900-66,500','P70-P85','最高溢价'],
    ['中资背景华人（运营商国际公司）','7,500-10,500','¥39,900-55,900','P55-P70','可远程，部分CNY计'],
    ['应届/1-3年（培养型）','5,500-7,500','¥29,300-39,900','P40-P55','需配培训期'],
], cw=[UW*0.30, UW*0.16, UW*0.18, UW*0.10, UW*0.26], keep_together=True))
story.append(Spacer(1,4))

story.append(Paragraph('3.2 年度综合（含AWS第13薪+奖金+佣金）', h2))
story.append(T([['项目','金额','约合CNY/年','说明'],
    ['<b>年度基础（S$8K-12.5K × 12）</b>','<b>96,000-150,000</b>','<b>¥51.1万-79.8万</b>','月薪×12'],
    ['<b>年度总包（13-15薪）</b>','<b>S$120,000-180,000</b>','<b>¥63.8万-95.8万</b>','含AWS+奖金+佣金'],
    ['<b>市场定位</b>','<b>P60-P85</b>','','对标 Singtel/NCS 销售中位'],
], cw=[UW*0.30, UW*0.22, UW*0.22, UW*0.26], keep_together=True))
story.append(callout('<b>核心建议：</b>建议月薪 <b>S$8,000-12,500</b>（约合 ¥42,600-66,500）；年度总包 <b>S$120,000-180,000</b>（约合 ¥63.8万-95.8万）。P60-P85 区间，与 Singtel/NCS 销售中位持平。'))
story.append(PageBreak())

story.append(Paragraph('3.3 分候选人定价', h2))
story.append(T([['候选人类型','建议月薪','年度总包','说明'],
    ['<b>海缆/国际网络稀缺销售（资深）</b>','<b>S$9,000-12,500/月</b>','<b>S$135K-180K</b>','稀缺溢价，对标P70-P85'],
    ['新加坡本地人（运营商背景，中英）','S$8,000-11,000/月','S$120K-150K','P60-P75，主推'],
    ['中资背景华人（可远程）','S$7,500-10,500/月','S$110K-150K','P55-P70'],
    ['应届/1-3年（培养型）','S$5,500-7,500/月','S$80K-110K','P40-P55'],
], cw=[UW*0.30, UW*0.22, UW*0.20, UW*0.28], keep_together=True))
story.append(Spacer(1,4))

story.append(Paragraph('3.4 薪资锚点校验', h2))
story.append(T([['锚点基准','数值','建议带宽倍数','判定'],
    ['合同口径中位月薪','S$4,936','1.6-2.5倍','✅ 合规（1.5-6倍区间）'],
    ['含CPF中位月薪','S$5,775','1.4-2.2倍','✅ 合规'],
    ['PWM通用行业下限','S$1,600','5.0-7.8倍','✅ 高端销售管理岗合理'],
    ['资深KAM市场中位','S$82K/年','对齐P70-P85','✅ 有竞争力'],
], cw=[UW*0.26, UW*0.18, UW*0.26, UW*0.30], keep_together=True))
story.append(callout('<b>锚点结论：</b>建议带宽 = 新加坡合同口径中位（S$4,936）的 <b>1.6-2.5倍</b>，对标 Singtel（S$6K-24K/月，中位8K）、NCS（S$7K-12K/月，中位10K）。校验合理，无需修正。'))
story.append(PageBreak())

# ===== 四、竞品对标 =====
story.append(Paragraph('四、竞品与市场对标', h1))
story.append(T([['对标','薪资（新加坡市场）','说明'],
    ['<b>Singtel（新加坡电信）</b>','<b>S$6K-24K/月（中位8K）</b>','本地最大运营商，与建议带宽高度重叠'],
    ['NCS（政企IT服务）','S$7K-12K/月（中位10K）','带宽与建议区间一致'],
    ['Oracle（新加坡）','S$135K-230K/年','头部软件厂商，含股权偏高端'],
    ['Glassdoor 全市场 Sales Manager','base S$4-7K/月（中位5K）','全行业基准，不含电信溢价'],
    ['Payscale 全市场 KAM（资深）','中位S$82K/年，P90 S$124K/年','佣金S$8K-40K/年'],
    ['中资运营商国际公司','S$6K-15K/月（视资历）','电信国际/中移国际/联通国际直接竞品'],
    ['<b>263 建议（校准后）</b>','<b>S$8K-12.5K/月（P60-P85）</b>','与Singtel/NCS中位持平，高于全市场'],
], cw=[UW*0.34, UW*0.28, UW*0.38], keep_together=True))
story.append(Spacer(1,4))
story.append(callout('<b>定位说明：</b>263 岗位是覆盖东南亚五国市场的电信 Wholesale 国际网络销售，四重稀缺叠加。<b>海缆销售经验 + 运营商 Wholesale 圈子 + 中英双语</b>是核心溢价点，建议带宽与 Singtel/NCS 中位持平、对稀缺人才给上限档可有效抢人。'))
story.append(PageBreak())

# ===== 五、候选人预期 =====
story.append(Paragraph('五、候选人预期分析', h1))
story.append(T([['候选人类型','薪资预期','预期总包','核心诉求'],
    ['本地资深KA/销售（3-5年+）','S$6K-10K/月','S$90K-140K/年','职业稳定+远程灵活'],
    ['海缆销售稀缺人才','市场价+20-30%溢价','S$130K-180K/年','行业认可+资源支持'],
    ['中资运营商国际公司背景','基础+年终+项目奖金','S$110K-160K/年','上市公司稳定性'],
], cw=[UW*0.24, UW*0.20, UW*0.20, UW*0.36], keep_together=True))
story.append(Spacer(1,4))
story.append(Paragraph('非薪资关注点（排序）', h2))
story.append(Paragraph('1. 远程办公的团队归属感（季度区域/总部聚会、明确汇报线）', bd))
story.append(Paragraph('2. 业绩考核透明度（佣金/奖金公式写入Offer，季度结算）', bd))
story.append(Paragraph('3. 出差强度与差旅政策（补贴、签证支持、报销时效）', bd))
story.append(Paragraph('4. 产品与资源支持（海缆/IP资源覆盖、售前配置）', bd))
story.append(PageBreak())

# ===== 六、招聘策略 =====
story.append(Paragraph('六、招聘策略建议', h1))
story.append(T([['策略','说明'],
    ['定位 P60-P85，非普通销售','覆盖东南亚五国的 Wholesale 国际网络销售，稀缺度5/5；总包给到 S$120K-180K'],
    ['稀缺人才优先渠道','运营商 Wholesale 封闭圈子（Singtel/中资运营商国际公司）、LinkedIn 定向（Submarine Cable/Carrier Sales）'],
    ['海缆销售人才重点挖','有 Submarine Cable 成交记录者给上限档 S$12.5K/月'],
    ['远程办公差异化','无需坐班 + 东南亚五国自主开拓空间，对远程偏好候选人吸引力大'],
    ['佣金结构前置沟通','销售岗佣金上不封顶，业绩导向，公式写入 Offer'],
], cw=[UW*0.26, UW*0.74], keep_together=True))
story.append(Spacer(1,4))
story.append(Paragraph('核心卖点（对外呈现）', h2))
story.append(Paragraph('1. A 股上市公司（002467.SZ）+ 国际网络业务为集团战略第三增长曲线', bd))
story.append(Paragraph('2. 远程办公 + 东南亚五国市场自主覆盖，出海通信基建大周期（海缆+AI数据中心）', bd))
story.append(Paragraph('3. 佣金上不封顶 + 业绩导向的成长型回报结构', bd))
story.append(Spacer(1,8))
story.append(Paragraph(fix_currency('免责说明：本报告薪资数据来源于 MOM 官方统计、Glassdoor、Payscale（2026年8月更新）。宏观数据来源于新加坡人力部（MOM）、中国外汇交易中心。汇率采用 2026.08.24 中间价（1 SGD=5.3196 CNY，即期约 5.29）。实际薪资受候选人条件、业务阶段、汇率波动等多因素影响，建议作为参考基准使用。所有薪资区间均为 GROSS 税前。'), dc))

# ===== 构建：临时基础版 → 水印版 → 删基础版 =====
doc = SimpleDocTemplate(TMP_BASE, pagesize=A4,
    leftMargin=LM, rightMargin=RM, topMargin=TM, bottomMargin=BM,
    title='Net263 Singapore Key Account Manager Salary Band Report')
doc.build(story, onFirstPage=page_deco, onLaterPages=page_deco)
print(f"基础版 OK: {TMP_BASE}")

# 加水印 → 最终水印版（PyPDF2 路径）
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
import io
reader = PdfReader(TMP_BASE)
writer = PdfWriter()
for i in range(len(reader.pages)):
    packet = io.BytesIO()
    c = canvas.Canvas(packet, pagesize=A4)
    c.setFillAlpha(0.12)
    c.setFont('SimHei', 32); c.setFillColorRGB(0.78, 0.78, 0.78)
    c.saveState(); c.translate(PW/2, PH/2); c.rotate(40)
    c.drawCentredString(0, 0, '用友薪福社  2026.08.24'); c.restoreState()
    c.saveState(); c.setFont('SimHei', 22); c.setFillColorRGB(0.8, 0.8, 0.8)
    c.translate(PW*0.2, PH*0.83); c.rotate(-35)
    c.drawCentredString(0, 0, '用友薪福社 2026.08.24'); c.restoreState()
    c.saveState(); c.setFont('SimHei', 22); c.setFillColorRGB(0.8, 0.8, 0.8)
    c.translate(PW*0.8, PH*0.17); c.rotate(-35)
    c.drawCentredString(0, 0, '用友薪福社 2026.08.24'); c.restoreState()
    c.save(); packet.seek(0)
    wm = PdfReader(packet).pages[0]
    reader.pages[i].merge_page(wm)
    writer.add_page(reader.pages[i])
with open(OUTPUT_WM, "wb") as f:
    writer.write(f)
os.remove(TMP_BASE)
print(f"水印版 OK: {OUTPUT_WM} ({os.path.getsize(OUTPUT_WM)/1024:.0f} KB)")
