"""Habas Team Leader Salary Report - CLIENT VERSION (no weaknesses exposed)"""
import os
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.units import mm
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))

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

S = getSampleStyleSheet()
h1 = ParagraphStyle('h1', fontName='STSong-Light', fontSize=16, leading=22, textColor=PRIMARY, spaceBefore=18, spaceAfter=10)
h2 = ParagraphStyle('h2', fontName='STSong-Light', fontSize=13, leading=18, textColor=PRIMARY, spaceBefore=14, spaceAfter=6)
h3 = ParagraphStyle('h3', fontName='STSong-Light', fontSize=12, leading=17, textColor=TEXT_DARK, spaceBefore=10, spaceAfter=4)
bd = ParagraphStyle('bd', fontName='STSong-Light', fontSize=10.5, leading=16, textColor=TEXT_DARK, spaceBefore=0, spaceAfter=4)
bl = ParagraphStyle('bl', parent=bd, leftIndent=10, bulletIndent=0, spaceBefore=0, spaceAfter=2)
ct = ParagraphStyle('ct', fontName='STSong-Light', fontSize=10, leading=15, textColor=TEXT_DARK, leftIndent=8, rightIndent=8, spaceBefore=4, spaceAfter=4, backColor=colors.HexColor('#fff5f5'), borderPadding=6, borderWidth=0)
ch = ParagraphStyle('ch', fontName='STSong-Light', fontSize=9.5, leading=14, textColor=PRIMARY, spaceBefore=0, spaceAfter=0)
cs = ParagraphStyle('cs', fontName='STSong-Light', fontSize=9.5, leading=14, spaceBefore=0, spaceAfter=0)
dc = ParagraphStyle('dc', fontName='STSong-Light', fontSize=9, leading=13, textColor=TEXT_MUTED, spaceBefore=12, spaceAfter=0)

def T(rows, cw=None):
    if not rows: return None
    n = len(rows[0])
    cw = cw or [UW/n]*n
    td = []
    for i, row in enumerate(rows):
        nr = []
        for cell in row:
            t = str(cell).strip().replace('\n','<br/>')
            nr.append(Paragraph(f'<b>{t}</b>' if i==0 else t, ch if i==0 else cs))
        td.append(nr)
    t = Table(td, colWidths=cw, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),LIGHT_BG), ('TEXTCOLOR',(0,0),(-1,0),PRIMARY),
        ('FONTNAME',(0,0),(-1,-1),'STSong-Light'),
        ('FONTSIZE',(0,0),(-1,0),9), ('FONTSIZE',(0,1),(-1,-1),9.5),
        ('ALIGN',(0,0),(-1,0),'LEFT'), ('VALIGN',(0,0),(-1,-1),'TOP'),
        ('TEXTCOLOR',(0,1),(-1,-1),TEXT_DARK),
        ('GRID',(0,0),(-1,-1),0.4,BORDER), ('BOX',(0,0),(-1,-1),0.6,PRIMARY),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,ALT_BG]),
        ('TOPPADDING',(0,0),(-1,-1),5), ('BOTTOMPADDING',(0,0),(-1,-1),5),
        ('LEFTPADDING',(0,0),(-1,-1),6), ('RIGHTPADDING',(0,0),(-1,-1),6),
    ]))
    return t

def callout(text):
    cb = Table([[Paragraph(text, ct)]], colWidths=[UW])
    cb.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,-1),colors.HexColor('#fff5f5')),
        ('LEFTPADDING',(0,0),(-1,-1),10), ('RIGHTPADDING',(0,0),(-1,-1),10),
        ('TOPPADDING',(0,0),(-1,-1),8), ('BOTTOMPADDING',(0,0),(-1,-1),8),
        ('LINEABOVE',(0,0),(-1,-1),2,ACCENT)]))
    return cb

story = []

# COVER
story.append(Spacer(1, 50))
# Main logo - HUGE HABAS text, no <b> tag (avoid bold-italic offset issues with CID font)
story.append(Paragraph('HABAS', ParagraphStyle(
    'logo', fontName='STSong-Light', fontSize=42, leading=50,
    textColor=PRIMARY, alignment=TA_CENTER,
    spaceBefore=0, spaceAfter=0)))
story.append(Spacer(1, 18))  # Explicit vertical gap

story.append(Paragraph('Sinai Ve Tibbi Gazlar Istihsal Endustrisi AS', ParagraphStyle(
    'company', fontName='STSong-Light', fontSize=12, leading=18,
    textColor=TEXT_MUTED, alignment=TA_CENTER,
    spaceBefore=0, spaceAfter=0)))
story.append(Spacer(1, 36))  # Larger gap before title

story.append(Paragraph('伊斯坦布尔 · 生产组长岗位<br/>薪资分析报告', ParagraphStyle(
    'maintitle', fontName='STSong-Light', fontSize=22, leading=32,
    textColor=PRIMARY, alignment=TA_CENTER,
    spaceBefore=0, spaceAfter=8)))
story.append(Spacer(1, 12))

story.append(Paragraph('Team Leader Salary Analysis Report — Istanbul', ParagraphStyle(
    'subtitle', fontName='STSong-Light', fontSize=13, leading=20,
    textColor=TEXT_MUTED, alignment=TA_CENTER,
    spaceBefore=0, spaceAfter=24)))
story.append(Spacer(1, 8))

# Red accent line
hr = Table([['']], colWidths=[UW*0.35], rowHeights=[2])
hr.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),ACCENT)]))
hr.hAlign = 'CENTER'
story.append(hr)
story.append(Spacer(1, 30))
md = [['报告日期','2026年7月29日'],['公司','Habas (HABAŞ)'],['地点','土耳其 伊斯坦布尔 / Manisa'],
       ['岗位','冲压部门组长 · 车身焊接组长 · 车身涂装组长'],['内容覆盖','宏观经济参数 · 候选人标签 · 竞品分析 · 招聘策略']]
mt = Table(md, colWidths=[UW*0.30, UW*0.70])
mt.setStyle(TableStyle([('FONTNAME',(0,0),(-1,-1),'STSong-Light'),('FONTSIZE',(0,0),(-1,-1),10),
    ('TEXTCOLOR',(0,0),(0,-1),TEXT_MUTED),('TEXTCOLOR',(1,0),(1,-1),TEXT_DARK),
    ('VALIGN',(0,0),(-1,-1),'MIDDLE'),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5),
    ('LEFTPADDING',(0,0),(-1,-1),8),('LINEBELOW',(0,0),(-1,-1),0.3,BORDER)]))
story.append(mt); story.append(PageBreak())

# S1: Macro
story.append(Paragraph('一、土耳其宏观经济参考参数',h1))
story.append(Paragraph('1.1 关键经济指标（2026年）',h2))
story.append(T([['指标','数值','备注'],
    ['人均GDP（名义）','~$15,893','世界银行中高收入国家标准'],
    ['人均GDP（购买力平价PPP）','$36,154','反映实际购买力水平'],
    ['月最低工资（税前）','33,030 TRY','2026年1月起执行，较2025年涨27%'],
    ['月最低工资（税后）','28,075 TRY（~$656）','覆盖约900万工人'],
    ['全国平均月薪（税前）','~35,000-45,000 TRY','行业差异显著'],
    ['伊斯坦布尔平均月薪（税前）','40,000-55,000 TRY','比全国高17%，三城中最高'],
    ['行业薪资：汽车制造（税前）','35,000-60,000 TRY/月','出口导向、周期性波动'],
    ['通胀率（2025年）','~34.9%','名义工资涨幅常被通胀抵消'],
    ['失业率','8.8%'],
    ['汇率参考','~35.5 TRY / 1 USD','2026年市场汇率，波动较大'],
], cw=[UW*0.30,UW*0.32,UW*0.38]))

story.append(Paragraph('1.2 伊斯坦布尔生活成本参照',h2))
story.append(T([['支出项','金额（TRY）','约合（USD）'],
    ['市中心一居室月租','25,000-35,000','$600-830'],
    ['非市中心一居室月租','15,000-25,000','$360-600'],
    ['单人自炊食品预算','6,000-9,000/月','$143-214'],
    ['单人月总支出（非市中心自炊）','40,000-50,000','$960-1,200'],
], cw=[UW*0.40,UW*0.30,UW*0.30]))

story.append(Spacer(1,4))
story.append(callout(
    '<b>薪资购买力锚点：</b>建议薪资必须覆盖"单人月总支出"的 <b>1.2-1.5倍</b> 才有基本吸引力。'
    '按此计算，伊斯坦布尔有效薪资底线约为 <b>48,000-60,000 TRY/月（税前）</b>。'))
story.append(Spacer(1,8))

story.append(Paragraph('1.3 雇主成本明细',h2))
story.append(T([['项目','比例/金额'],
    ['社保(SGK)雇主缴纳','16.75%（制造业优惠税率）'],['失业保险（雇主）','2%'],
    ['个税（累进）','15%-40%（最高档）'],['辞退准备金','每工作1年=1个月工资'],
    ['总雇主成本系数','≈ 1.30-1.40 × 税前工资'],
], cw=[UW*0.40,UW*0.60]))
story.append(PageBreak())

# S2: Framework
story.append(Paragraph('二、分析维度框架',h1))
story.append(Paragraph('2.1 基准薪资层',h2))
story.append(T([['维度','说明'],
    ['Title对标','Team Leader / Production Team Leader / Production Supervisor'],
    ['行业基准','Automotive（汽车制造业）'],['城市系数','伊斯坦布尔（+17% vs 全国平均）'],
    ['经验系数','5年+资深 / 3-5年中级 / 0-2年初级'],
    ['公司规模系数','Habas 年产能10,000-15,000辆，规模中等偏大'],
    ['通胀调整','2026年通胀~35%，建议年涨幅≥通胀率'],
], cw=[UW*0.30,UW*0.70]))

story.append(Paragraph('2.2 岗位技术溢价层',h2))
story.append(T([['岗位','核心技术要求','溢价逻辑'],
    ['冲压部门组长','模具成型技术、G1冲压线自动化','传统冲压技能，溢价空间小'],
    ['车身焊接组长','Fanuc/Yaskawa/Kuka焊接机器人、气保焊','<font color="#c53030"><b>高需求</b></font>——焊接机器人人才极度稀缺'],
    ['车身涂装组长','ED前处理、Yaskawa涂装机器人、喷涂缺陷识别','<font color="#c53030"><b>高需求</b></font>——复合型人才稀缺'],
], cw=[UW*0.22,UW*0.43,UW*0.35]))

story.append(Paragraph('2.3 候选人市场竞争力层',h2))
story.append(T([['维度','说明'],
    ['被动候选人比例','75-85%（高级技术人才不在招聘平台活跃）'],
    ['平均招聘周期','技术岗47天，资深岗95-120天'],
    ['德国挖角溢价','2.5-3.0倍薪资（有语言能力的工程师）'],
    ['Bursa竞品溢价','15-20%高于全国水平'],
], cw=[UW*0.30,UW*0.70]))
story.append(PageBreak())

# S3: Benchmarks
story.append(Paragraph('三、薪资基准数据（2026年7月）',h1))
story.append(Paragraph('3.1 土耳其全国Team Leader薪资',h2))
story.append(T([['分类','月薪(TRY)','约合(USD)'],
    ['全国Team Leader平均','35,657','~$1,010'],
    ['伊斯坦布尔Team Leader平均','<b>41,719</b>','~$1,180'],
    ['Production Team Leader - 汽车行业','35,677','~$1,005'],
    ['伊斯坦布尔（行业均值推算）','<b>41,700-44,500</b>','~$1,180-1,260'],
    ['伊斯坦布尔薪资范围','32,829 - 56,704','~$930-1,600'],
], cw=[UW*0.50,UW*0.25,UW*0.25]))
story.append(Paragraph('3.2 按经验层级（伊斯坦布尔，汽车行业）',h2))
story.append(T([['经验级别','月薪(TRY)','约合(USD)'],
    ['初级（0-2年）','22,107 - 28,000','~$625-790'],
    ['中级（3-5年）','35,000 - 45,000','~$990-1,270'],
    ['<b>资深（5年+）</b>','<b>45,000 - 56,000</b>','<b>~$1,270-1,580</b>'],
    ['高技能/机器人专长','50,000 - 65,000','~$1,410-1,830'],
], cw=[UW*0.40,UW*0.30,UW*0.30]))

story.append(Paragraph('3.3 薪资区间与宏观指标对比',h2))
story.append(T([['对比维度','金额','占Habas建议薪资比例'],
    ['土耳其月最低工资（税后）','28,075 TRY','焊接组：65%-51%'],
    ['伊斯坦布尔单人月支出','40,000-50,000 TRY','焊接组可完全覆盖并有余'],
    ['伊斯坦布尔平均月薪（税前）','40,000-55,000 TRY','焊接组：与市场均值持平'],
    ['<b>建议焊接组长薪资</b>','<b>43,000-55,000 TRY</b>','<b>定位：市场中上水平</b>'],
], cw=[UW*0.40,UW*0.30,UW*0.30]))
story.append(PageBreak())

# S4: Recommended Salary
story.append(Paragraph('四、Habas三岗位薪资建议区间',h1))
story.append(Paragraph(
    '综合考虑伊斯坦布尔系数（+17%）、汽车行业基准、新品牌"人才溢价"（+5-10%）、'
    '焊接/涂装机器人技能稀缺溢价（+10-15%）、通胀调整（建议年度调薪≥34.9%通胀率）。',bd))
story.append(Spacer(1,4))

story.append(Paragraph('4.1 冲压部门组长',h2))
story.append(T([['项目','TRY/月','USD/月','TRY/年'],
    ['<b>建议薪资范围</b>','<b>38,000 - 48,000</b>','<b>$1,070-1,350</b>','<b>456,000-576,000</b>'],
    ['基准（伊斯坦布尔汽车TL）','41,700','$1,180','500,400'],
    ['雇主总成本（×1.35）','51,300-64,800','$1,445-1,825','615,600-777,600'],
    ['市场定位','P50-P60','',''],
], cw=[UW*0.32,UW*0.22,UW*0.22,UW*0.24]))
story.append(Paragraph(
    '<b>说明：</b>冲压岗位技术门槛相对常规，模具成型经验+冲压线自动化管理是关键。建议定位市场中位数偏上。',ct))

story.append(Paragraph('4.2 车身焊接组长',h2))
story.append(T([['项目','TRY/月','USD/月','TRY/年'],
    ['<b>建议薪资范围</b>','<b>43,000 - 55,000</b>','<b>$1,210-1,550</b>','<b>516,000-660,000</b>'],
    ['基准+机器人溢价（+15%）','48,000','$1,350','576,000'],
    ['雇主总成本（×1.35）','58,050-74,250','$1,635-2,090','696,600-891,000'],
    ['市场定位','P60-P75','',''],
], cw=[UW*0.32,UW*0.22,UW*0.22,UW*0.24]))
story.append(Paragraph(
    '<b>说明：</b>焊接机器人编程与调试经验非常稀缺。复合技能要求使该岗位竞争最激烈。'
    '<font color="#c53030"><b>建议作为三岗中薪资最高的。</b></font>',ct))

story.append(Paragraph('4.3 车身涂装组长',h2))
story.append(T([['项目','TRY/月','USD/月','TRY/年'],
    ['<b>建议薪资范围</b>','<b>40,000 - 52,000</b>','<b>$1,130-1,465</b>','<b>480,000-624,000</b>'],
    ['基准+涂装溢价（+10%）','45,900','$1,295','550,800'],
    ['雇主总成本（×1.35）','54,000-70,200','$1,520-1,975','648,000-842,400'],
    ['市场定位','P55-P70','',''],
], cw=[UW*0.32,UW*0.22,UW*0.22,UW*0.24]))
story.append(Paragraph(
    '<b>说明：</b>ED前处理、烘烤工艺控制、涂装机器人经验是核心稀缺技能。涂装缺陷识别需要较长时间经验积累。',ct))

story.append(Paragraph('4.4 三岗位薪资对比一览',h2))
story.append(T([['岗位','建议月薪(TRY)','年总成本(含雇主)','稀缺度','市场定位'],
    ['车身焊接组长','43,000-55,000','696,600-891,000','5/5','P60-P75'],
    ['车身涂装组长','40,000-52,000','648,000-842,400','4/5','P55-P70'],
    ['冲压部门组长','38,000-48,000','615,600-777,600','3/5','P50-P60'],
], cw=[UW*0.20,UW*0.22,UW*0.25,UW*0.13,UW*0.20]))
story.append(PageBreak())

# S5: Competitor
story.append(Paragraph('五、竞品在招分析',h1))
story.append(Paragraph('5.1 伊斯坦布尔/科贾埃利地区主要竞品',h2))
story.append(T([['竞品公司','地点','在招情况','对Habas的人才竞争威胁'],
    ['Mercedes-Benz Türk','伊斯坦布尔 Hoşdere','技术岗持续招聘','<b>高</b>'],
    ['Ford Otosan','Kocaeli Gölcük/Yeniköy','技术招聘增加55%','<b>高</b>'],
    ['Hyundai Assan','Kocaeli Izmit','新增电池工厂招300+人','<b>高</b>'],
    ['Otokar','伊斯坦布尔/Sakarya','持续招聘工程师','中'],
    ['Tofas (Stellantis)','Bursa','裁员13%（重组中）','中——释放人才'],
], cw=[UW*0.22,UW*0.22,UW*0.30,UW*0.26]))
story.append(Paragraph('5.2 关键发现',h2))
for f in ['最直接的人才竞争来自Mercedes-Benz Turk（伊斯坦布尔）和Ford Otosan（Kocaeli）',
           'EV转型分流：Hyundai的电池工厂正在吸收Kocaeli地区的技术人才',
           'Tofas裁员释放部分有经验的组长级候选人，是Habas可关注的目标人群']:
    story.append(Paragraph(f'• {f}',bl))
story.append(Spacer(1,4))

story.append(Paragraph('5.3 竞品薪资对比',h2))
story.append(T([['竞品','同级别薪资(TRY/月)','说明'],
    ['Mercedes-Benz Turk','50,000-65,000+','行业薪资标杆'],
    ['Ford Otosan','45,000-60,000','含奖金+车辆福利'],
    ['Hyundai Assan','42,000-55,000','中等偏上'],
    ['Otokar','38,000-50,000','与Habas最为接近的对标公司'],
    ['<b>Habas（建议）</b>','<b>38,000-55,000</b>','<b>具备市场竞争力</b>'],
], cw=[UW*0.30,UW*0.30,UW*0.40]))
story.append(PageBreak())

# S6: Candidate Expectations
story.append(Paragraph('六、候选人预期分析',h1))
story.append(Paragraph('6.1 薪资预期',h2))
story.append(T([['候选人类型','预期月薪(TRY)','预期薪资以外待遇'],
    ['伊斯坦布尔本地候选人（冲压背景）','38,000-45,000','社保+交通补贴+餐补'],
    ['伊斯坦布尔本地候选人（焊接专长）','45,000-58,000','同上+培训机会'],
    ['伊斯坦布尔本地候选人（涂装+机器人）','42,000-55,000','同上+轮班津贴'],
    ['被动候选人（需挖角）','+20-35%溢价','需含签约奖金'],
], cw=[UW*0.40,UW*0.25,UW*0.35]))
story.append(Spacer(1,4))
story.append(callout('<b>签约金：</b>高级候选人可接受 50,000-100,000 TRY 一次性签约奖。'))
story.append(Spacer(1,8))

story.append(Paragraph('6.2 候选人关注的非薪资因素',h2))
story.append(T([['优先级','因素','说明'],
    ['高','<b>工作稳定性</b>','候选人极度关注长期就业保障'],
    ['高','<b>职业发展路径</b>','Habas作为新品牌，明确的晋升通道是关键卖点'],
    ['中','培训与技术成长','候选人看重是否有系统性机器人技能培训'],
    ['中','轮班制接受度','夜班津贴、周末加班费需明确'],
    ['低','交通便利性','需明确工作地点及通勤方案'],
], cw=[UW*0.13,UW*0.25,UW*0.62]))

story.append(Paragraph('6.3 候选人筛选期望清单',h2))
for i,s in enumerate(['HR电话面试（30分钟）','技术主管面试（1小时）','工厂现场参观+生产线主管面试',
    '可能含技能测试','背景调查'],1):
    story.append(Paragraph(f'{i}. {s}',bl))
story.append(PageBreak())

# S7: Profile & Tags (NO age/gender, NO 7.5 channels)
story.append(Paragraph('七、候选人画像与标签系统',h1))
story.append(Paragraph('<b>每个候选人根据经验、技能、资质三个维度进行标签分类，用于快速筛选与薪资定级。</b>',bd))
story.append(Spacer(1,8))

story.append(Paragraph('7.1.1 冲压部门组长 - 能力标签',h3))
story.append(T([['标签','含义','匹配薪资区间','占比估算'],
    ['[P-PRIME] 资深冲压组长','8年+冲压经验，精通多品牌模具','45,000-48,000 TRY','15%'],
    ['[P-CORE] 核心冲压组长','5-8年经验，独立管理冲压线','40,000-44,000 TRY','35%'],
    ['[P-JUNIOR] 初级冲压组长','3-5年经验，可操作冲压线','38,000-40,000 TRY','30%'],
    ['[P-TRANSFER] 转行候选人','机械加工背景，需再培训','< 38,000 TRY','20%'],
], cw=[UW*0.20,UW*0.35,UW*0.28,UW*0.17]))

story.append(Paragraph('7.1.2 车身焊接组长 - 能力标签',h3))
story.append(T([['标签','含义','匹配薪资区间','占比估算'],
    ['[W-EXPERT] 焊接机器人专家','三品牌精通，8年+','52,000-55,000 TRY','8%'],
    ['[W-ROBOT] 焊接机器人熟练','精通1-2品牌，5年+','47,000-52,000 TRY','20%'],
    ['[W-LEAD] 焊接线组长','传统焊接经验丰富','43,000-47,000 TRY','30%'],
    ['[W-TRAINEE] 焊接潜力股','3年+，愿意学习机器人编程','40,000-43,000 TRY','42%'],
], cw=[UW*0.20,UW*0.35,UW*0.28,UW*0.17]))

story.append(Paragraph('7.1.3 车身涂装组长 - 能力标签',h3))
story.append(T([['标签','含义','匹配薪资区间','占比估算'],
    ['[PT-MASTER] 涂装工艺大师','ED+Yaskawa+全流程诊断，8年+','50,000-52,000 TRY','10%'],
    ['[PT-ROBOT] 涂装机器人专长','精通Yaskawa编程，5年+','46,000-50,000 TRY','18%'],
    ['[PT-CHEM] 化学品工艺专长','前处理/ED/烘烤曲线精通','42,000-46,000 TRY','28%'],
    ['[PT-STANDARD] 标准涂装组长','涂装线管理5年+','40,000-42,000 TRY','44%'],
], cw=[UW*0.20,UW*0.35,UW*0.28,UW*0.17]))

story.append(Paragraph('7.2 候选人综合画像标签',h2))
story.append(T([['标签','定义','适用岗位'],
    ['<b>[BIG-3]</b>','来自行业头部企业，竞争力强','全部'],
    ['<b>[ENGLISH]</b>','英语流利（B2+），薪资预期+10-15%','全部'],
    ['<b>[CERTIFIED]</b>','持有IATF 16949/ISO 45001证书','全部'],
    ['<b>[ROBOT-MULTI]</b>','多品牌机器人精通','焊接/涂装'],
    ['<b>[EV-EXPERIENCED]</b>','有EV产线经验','焊接/涂装'],
    ['<b>[BURSA-POOL]</b>','Bursa地区，愿意搬迁','全部'],
    ['<b>[LOCAL-IST]</b>','伊斯坦布尔本地，稳定性高','全部'],
], cw=[UW*0.25,UW*0.55,UW*0.20]))
story.append(PageBreak())

story.append(Paragraph('7.3 三岗位通用画像',h2))
story.append(T([['维度','画像'],
    ['学历','机械工程/工业工程/材料工程 本科'],
    ['工作经验','5-10年汽车制造业经验，至少2年Team Leader经验'],
    ['地域','伊斯坦布尔/科贾埃利/布尔萨居住，或愿意搬迁'],
    ['语言','土耳其语母语，英语可阅读技术文档'],
    ['证书','IATF 16949内审员、ISO 45001(OHS)、5S/Kaizen认证'],
    ['职业动机','寻求更大自主权、新品牌快速晋升机会、技术能力提升'],
], cw=[UW*0.25,UW*0.75]))

story.append(Paragraph('7.4 各岗位差别画像',h2))

story.append(Paragraph('7.4.1 冲压部门组长',h3))
story.append(T([['维度','画像'],
    ['典型背景','TOFAS、Ford Otosan或Mercedes-Benz Turk冲压线组长'],
    ['核心技能','模具成型技术、冲压线编程、OEE管理'],
    ['当前薪资','35,000-42,000 TRY/月'],
    ['跳槽诱因','薪资涨幅20%+、晋升机会'],
], cw=[UW*0.25,UW*0.75]))

story.append(Paragraph('7.4.2 车身焊接组长',h3))
story.append(T([['维度','画像'],
    ['典型背景','Ford Otosan焊接车间、TOFAS焊接线5年+经验'],
    ['核心技能','<b>Fanuc/Yaskawa/Kuka机器人编程与调试</b>（最稀缺）'],
    ['当前薪资','40,000-50,000 TRY/月'],
    ['跳槽诱因','薪资涨幅25-30%、多品牌机器人能力提升'],
    ['招聘难度','<font color="#c53030"><b>最难填补——平均招聘周期95-120天</b></font>'],
], cw=[UW*0.25,UW*0.75]))

story.append(Paragraph('7.4.3 车身涂装组长',h3))
story.append(T([['维度','画像'],
    ['典型背景','汽车OEM涂装车间5年+经验'],
    ['核心技能','ED前处理、Yaskawa涂装机器人操作、缺陷诊断'],
    ['当前薪资','37,000-47,000 TRY/月'],
    ['跳槽诱因','薪资涨幅20-25%、新建产线从头搭建机会'],
    ['招聘难度','<b>中等偏难</b>'],
], cw=[UW*0.25,UW*0.75]))
story.append(PageBreak())

# S8: Strategy (NO 8.5 Timeline, NO Habas劣势)
story.append(Paragraph('八、招聘策略建议',h1))
story.append(Paragraph('8.1 薪资策略',h2))
story.append(T([['岗位','策略','建议月薪(TRY)'],
    ['冲压部门组长','<b>市场中位数（P50）</b> + 新品牌溢价(5%)','40,000-45,000'],
    ['车身焊接组长','<b>市场高位（P70-P75）</b> + 稀缺溢价(15%)','48,000-55,000'],
    ['车身涂装组长','<b>市场中上位（P60）</b> + 工艺溢价(10%)','43,000-50,000'],
], cw=[UW*0.30,UW*0.45,UW*0.25]))

story.append(Paragraph('8.2 按候选人标签的差异化定价',h2))
story.append(T([['候选人标签组合','建议薪资调整'],
    ['[BIG-3] + [ROBOT-MULTI] + [CERTIFIED]','<b>+15-20% 顶格薪资</b>'],
    ['[BIG-3] + [CERTIFIED]','+10% 溢价'],
    ['[ENGLISH] + [CERTIFIED]','+8-12% 溢价'],
    ['[LOCAL-IST]','基准水平'],
    ['[BURSA-POOL]','基准+搬迁补贴（一次性50,000-80,000 TRY）'],
], cw=[UW*0.55,UW*0.45]))

# 8.3 Rewritten - all positive
story.append(Paragraph('8.3 差异化吸引力',h2))
story.append(T([['维度','核心卖点'],
    ['业务背景','依托集团68年工业经验（钢铁、能源领域），新建Manisa工厂100,000m\u00b2，已量产并交付伊斯坦布尔公交'],
    ['薪资福利','具有市场竞争力的薪资方案，叠加交通补贴、免费午餐、轮班津贴、培训机会等灵活福利包'],
    ['员工发展','全新工厂+新建产线，提供管理岗快速晋升和多品牌机器人系统技能培训'],
    ['工作地点','明确的工作地点安排，提供通勤方案或住房补贴'],
], cw=[UW*0.25,UW*0.75]))

story.append(Paragraph('8.4 应对候选人常见顾虑的沟通话术方向',h2))
for q,a in [
    ('"Habas是家新公司，靠谱吗？"','68年集团历史+自建Manisa工厂(100,000m\u00b2)+已量产并交付'),
    ('"薪资与成熟品牌如何对比？"','职业发展速度+新建工厂晋升空间+多品牌机器人技能培训机会'),
    ('"工作地点在哪？"','明确岗位所在地，提供通勤或住房支持'),
]:
    story.append(Paragraph(f'<b>{q}</b>',bd))
    story.append(Paragraph(f'→ {a}',bl))
    story.append(Spacer(1,2))

story.append(Spacer(1,12))

# Disclaimer
story.append(Paragraph(
    '<b>免责说明：</b>本报告薪资数据来源于 ElemanBuldum、Payscale、Glassdoor 等公开薪资调查平台'
    '（2026年7月更新），以及 KiTalent、Wide and Wise 等行业招聘顾问机构的市场分析。'
    '宏观数据来源于土耳其统计局（TUIK）、世界银行、GlobalCostData 等。'
    '<b>建议作为参考基准使用</b>。',dc))

# BUILD
OUT = "/Users/yoyo/WorkBuddy/2026-07-29-13-50-49"
path = f"{OUT}/Habas_伊斯坦布尔_组长岗位薪资分析报告_客户版.pdf"

def deco(c, doc):
    c.saveState()
    c.setFont('STSong-Light', 8)
    c.setFillColor(TEXT_MUTED)
    c.drawCentredString(PW/2, PH - 12*mm, 'HABAS · 伊斯坦布尔生产组长薪资分析报告 · July 2026')
    c.setStrokeColor(BORDER); c.setLineWidth(0.3)
    c.line(LM, PH-15*mm, PW-RM, PH-15*mm)
    c.drawCentredString(PW/2, 10*mm, f'Page {doc.page}')
    c.restoreState()

doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=LM, rightMargin=RM, topMargin=TM, bottomMargin=BM,
    title='Habas Team Leader Salary Report')
doc.build(story, onFirstPage=deco, onLaterPages=deco)
sz = os.path.getsize(path)
print(f"Client PDF: {path} ({sz/1024:.1f} KB)")
