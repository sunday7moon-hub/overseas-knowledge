# -*- coding: utf-8 -*-
"""make_region_report.py — 多国分地区薪酬带宽报告骨架（一次产出 N 份）

适用
    一个岗位、多个候选驻地 → 按地区拆成多份报告（每份只讲本地区国家）。
    典型：控维 RSM 中东七国 / 东南亚五国；某岗位 欧盟五国 / 拉美四国。

用法
    1) 复制本文件为你的报告脚本（放工作区）
    2) 改「配置区 / 数据区」
    3) python make_region_report.py   → 产出 N 份客户版 PDF
    4) python ~/.workbuddy/skills/pdf-report-layout/scripts/qc_client_pdf.py \\
              --color "#1f4f8f" --per-file "中东版.pdf=以色列,!印尼;东南亚版.pdf=印尼,!以色列" *.pdf

⚠️ 串区是本类报告的头号事故
    所有随地区变化的文案（封面口径、来源表、锚点说明、桥接句）**必须**从
    REGION_META / REGIONS 里按 cfg['key'] 取，**禁止**在章节函数里写死国家名或地区名。
    2026-09-14 控维事故：东南亚版正文出现「以色列」，根因就是三处共用硬编码字面量。

⚠️ 示例数据为「示例客户 · 海湾三国 / 东盟三国」，仅验证链路，务必替换。
"""
import os
import sys


def _load_kit():
    """定位 salary_report_kit.py。

    本骨架会被**复制到任意工作区**使用，此时 `__file__` 指向工作区，
    同目录找不到 kit —— 因此按 ① 同目录（就地运行）② 环境变量 ③ skill 安装位置
    三级探测，找不到才报错。
    """
    here = os.path.dirname(os.path.abspath(__file__))
    cands = [here,
             os.environ.get('SALARY_REPORT_KIT_DIR'),
             os.path.expanduser('~/.workbuddy/skills/client-salary-band-report/scripts')]
    for c in cands:
        if c and os.path.exists(os.path.join(c, 'salary_report_kit.py')):
            if c not in sys.path:
                sys.path.insert(0, c)
            return
    raise ImportError('未找到 salary_report_kit.py；'
                      '请设置环境变量 SALARY_REPORT_KIT_DIR 指向其所在目录')


_load_kit()

from salary_report_kit import *                        # noqa: E402,F401,F403
from salary_report_kit import RATE_BASIS, set_rates    # noqa: E402
from reportlab.platypus import Paragraph, Spacer

# =============================================================================
# 配置区
# =============================================================================
CLIENT = '示例客户'
BRAND_BIG = 'SAMPLE'
BRAND_EN = 'Sample Client Co., Ltd.'
JOB = '区域销售经理'
JOB_EN = 'RSM'
# ★ 岗位经验档（= 客户岗位准入范围）：决定定价口径与正文表述，**严禁写窄**。
#   客户要 8-15 年就写「8-15 年」；写成 10-15 年属口径不符（2026-09-14 控维事故）。
#   带宽与准入范围对齐后，用「下限=门槛端 / 上限=资深端 / 中位=供给密集段」三句解释读法。
EXP_BAND = '8-15 年'
DATE = '2026年9月14日'
RDATE = '2026.09.14'
# 输出目录：默认落在**本脚本所在目录**（即你复制骨架到的工作区），
# 可用环境变量 SALARY_REPORT_OUT 覆盖。切勿写成 ~/WorkBuddy 等家目录路径——
# 会把测试产物倒进用户家目录（2026-09-14 回归测试踩到）。
WORK = os.environ.get('SALARY_REPORT_OUT') or os.path.dirname(os.path.abspath(__file__))

set_rates({}, basis='2026-09-01 中国外汇交易中心（CFETS）中间价')

# -----------------------------------------------------------------------------
# 地区配置：标题/锚点/国家清单/封面地区串，全部按 key 取，禁止在正文里写死
# -----------------------------------------------------------------------------
REGIONS = {
    'gulf': {
        'key': 'gulf', 'title': '海湾三国', 'short': '海湾', 'file': '海湾三国',
        'countries': ['沙特（利雅得）', '阿联酋（迪拜）', '阿曼（马斯喀特）'],
        'anchor': '沙特利雅得',
        'cb_line': '沙特（利雅得） · 阿联酋（迪拜） · 阿曼（马斯喀特）',
        'cb_note': '以沙特利雅得 = 100 为锚点',
        'bridge': '注：本报告以沙特利雅得 = 100 为基准，各国成本指数均相对该基准计算；'
                  '年成本按报告锁定汇率折人民币，与海湾以外市场不可直接混用。',
    },
    'asean': {
        'key': 'asean', 'title': '东盟三国', 'short': '东盟', 'file': '东盟三国',
        'countries': ['新加坡', '泰国（曼谷）', '印度尼西亚（雅加达）'],
        'anchor': '新加坡',
        'cb_line': '新加坡 · 泰国（曼谷） · 印度尼西亚（雅加达）',
        'cb_note': '以新加坡 = 100 为锚点',
        'bridge': '注：本报告以新加坡 = 100 为基准，各国成本指数均相对该基准计算；'
                  '年成本按报告锁定汇率折人民币，与非东盟市场不可直接混用。',
    },
}

# -----------------------------------------------------------------------------
# ★ 地区口径元信息：封面「数据口径」+ 末章「数据来源」按地区取用（防串区关键）
#   每个 key 必须齐备；新增地区时先补这里，再写章节。
# -----------------------------------------------------------------------------
REGION_META = {
    'gulf': {
        'basis': 'GROSS 税前（海湾国家无个人所得税，等同净得）',
        'salary_src': 'Michael Page · Hays · Mercer · GulfTalent · LinkedIn Talent Insights · Paylab · ERI',
        'macro_src': '沙特 GASTAT / GOSI / Nitaqat · 阿联酋 MOHRE · 阿曼 NCSI',
        'fx_src': 'CFETS 中间价（USD/CNY = 6.7809）；海湾币种按官方钉住汇率折算',
    },
    'asean': {
        'basis': 'GROSS 税前（三国均为个税累进制，最高档 24-35%；新加坡税负最低）',
        'salary_src': 'Michael Page · Hays · Mercer · LinkedIn Talent Insights · Jobstreet · Paylab · ERI',
        'macro_src': '新加坡 MOM / CPF · 泰国 劳工部 / SSO · 印尼 劳工部 / BPJS',
        'fx_src': 'CFETS 中间价（USD/CNY = 6.7809）；东盟币种取同日实时值',
    },
}

# =============================================================================
# 数据区
# =============================================================================
# 国家行：(国家, 币种, 基础下限, 基础上限, OTE下限, OTE上限, 分位, 成本指数, 驻地定位, 综合建议)
COUNTRY = {
    'gulf': [
        ('沙特（利雅得）',     'SAR', 32000, 40000, 38000, 52000, 'P60-P75', 100, '基准驻地', '推荐'),
        ('阿联酋（迪拜）',     'AED', 32000, 43500, 38000, 58000, 'P50-P75', 109, '枢纽驻地', '首选推荐'),
        ('阿曼（马斯喀特）',   'OMR', 2300,  3000,  2800,  3700,  'P50-P70', 71,  '最低成本', '成本备选'),
    ],
    'asean': [
        ('新加坡',             'SGD', 9400,  13800, 11300, 18100, 'P60-P75', 100, '区域总部', '首选推荐'),
        ('泰国（曼谷）',       'THB', 105000, 140000, 130000, 176000, 'P50-P70', 41, '制造枢纽', '推荐'),
        ('印度尼西亚（雅加达）', 'IDR', 36300000, 58000000, 43500000, 72500000, 'P50-P70', 28, '最低成本', '备选'),
    ],
}

# 雇主成本（外籍雇员口径｜2025-2026 法规）
# rate  雇主附加率% = 社保雇主部分 + 离职金年计提（封顶类项目已按岗位月薪折算为实际比率）
# bonus 年度法定奖金月数（如菲律宾 13 薪、印尼 THR）｜tax_lo/hi 估算个税有效税率区间%
EMPLOYER_COST = {
    '沙特（利雅得）':       {'rate': 6.2, 'bonus': 0, 'tax_lo': 0, 'tax_hi': 0,
                        'cost': 'GOSI 工伤险 2%（外籍）+ 离职金年计提 4.2%（前 5 年半月薪/年）'},
    '阿联酋（迪拜）':       {'rate': 5.8, 'bonus': 0, 'tax_lo': 0, 'tax_hi': 0,
                        'cost': '外籍无强制社保；离职金年计提 5.8%（21 天基本工资/年）'},
    '阿曼（马斯喀特）':     {'rate': 5.2, 'bonus': 0, 'tax_lo': 0, 'tax_hi': 0,
                        'cost': 'PASI 工伤险 1%（外籍）+ 离职金年计提 4.2%（前 3 年半月薪/年）'},
    '新加坡':               {'rate': 0.0, 'bonus': 0, 'tax_lo': 15, 'tax_hi': 18,
                        'cost': '外籍雇员不缴 CPF（雇主 17% 仅适用于公民/PR）；无强制年终奖金'},
    '泰国（曼谷）':         {'rate': 0.5, 'bonus': 0, 'tax_lo': 22, 'tax_hi': 26,
                        'cost': 'SSO 雇主 5%，封顶 THB 750/月——本岗位实际仅约 0.5%'},
    '印度尼西亚（雅加达）': {'rate': 5.3, 'bonus': 0, 'tax_lo': 25, 'tax_hi': 30,
                        'cost': 'BPJS 合计约 5.3%（JHT 3.7% 无封顶；外籍豁免 JP）；THR 对外籍无法定强制'},
}

# 薪酬结构通则（放第二章开头统一说明，逐国块不重复）
EMPLOYER_STRUCT = {
    'gulf': '固定 : 浮动 ≈ 65 : 35（OTE 口径）；住房津贴多已含在总包内（海湾惯例）；无强制年终奖',
    'asean': '固定 : 浮动 ≈ 70 : 30（OTE 口径）；住房津贴多在总包外单列，视合同约定；'
             '印尼 THR 对外籍无法定强制',
}


# 各国驻地要点（按国家全名索引，与 COUNTRY 里的名字完全一致）
EXTRA = {
    '沙特（利雅得）': {
        'macro': '个税 0% · 外籍社保仅工伤险 2%（沙特籍雇主 11.75%）· 私营平均月薪 SAR 7,339（GASTAT）',
        'residency': '工作签（Iqama）常驻，沙化政策下单外籍比例受配额约束',
        'fit': '核心客户市场集中；区域指挥功能成熟；子女教育需提前规划',
    },
    '阿联酋（迪拜）': {
        'macro': '个税 0% · 外籍无强制社保 · 迪拜平均月薪 AED 12,000-15,000',
        'residency': '自由区与多类工作签并行，外籍常驻门槛最低',
        'fit': '区域总部首选：三小时航程覆盖海湾全境，国际学校与医疗配套最完善',
    },
    '阿曼（马斯喀特）': {
        'macro': '个税 0% · 外籍社保仅工伤险 1%（本国籍雇主 12.5%）· 平均月薪 OMR 800-1,000',
        'residency': '工作许可受阿曼化配额约束，部分岗位禁止外籍',
        'fit': '成本最优，但客户市场体量最小，适合作为补充覆盖点',
    },
    '新加坡': {
        'macro': '个税 0-24% 累进（居民实际 5-15%）· 雇主 CPF 17%（仅公民/PR，外籍不缴）· 全职工中位数 S$5,775',
        'residency': '外籍 EP 门槛 S$5,000/月起 + COMPASS 打分框架',
        'fit': '区域总部聚集度最高；客户覆盖与融资条件最优；用人成本最高',
    },
    '泰国（曼谷）': {
        'macro': '个税 5-35% 累进 · 雇主社保 5%，上限 THB 750/月（封顶后实际约 0.5%）· 曼谷平均月薪 THB 25,000-30,000',
        'residency': 'Non-B 签证 + 工作许可，每 1 名外籍需配套 4 名泰籍雇员',
        'fit': '制造与数字基建客户枢纽；外籍社区成熟；跨府差旅较多',
    },
    '印度尼西亚（雅加达）': {
        'macro': '个税 5-35% 累进 · 雇主 BPJS 合计约 5.3%（JHT 3.7% 无封顶，外籍豁免 JP）· 全国平均月薪 IDR 3.33 百万（BPS）',
        'residency': 'RPTKA 工作许可 + 本地雇员配比要求，合规流程 1-3 个月',
        'fit': '低成本驻地首选；本地人才池最厚；跨岛差旅强度大',
    },
}

# 执行摘要结论卡（按地区）
SUMMARY_CARDS = {
    'gulf': [
        {'tag': '结论 1', 'title': '成本最优', 'body': ['阿曼（71）为本地区最低成本驻地'],
         'foot': '低成本但市场体量受限'},
        {'tag': '结论 2', 'title': '综合最优',
         'body': ['阿联酋（迪拜）成本 109，仅高于基准 9%',
                  '换取最优外籍常驻条件与航空枢纽'], 'foot': '区域指挥首选驻地'},
        {'tag': '结论 3', 'title': '市场牵引',
         'body': ['沙特（利雅得）为基准 100，紧贴核心客户市场', '无个税，GROSS 等同净得'],
         'foot': '客户对接首选'},
        {'tag': '结论 4', 'title': '合规提示',
         'body': ['沙化与阿曼化配额推高本地雇佣要求', '外籍比例需与本地雇员结构匹配'],
         'foot': '用工结构需前置规划'},
    ],
    'asean': [
        {'tag': '结论 1', 'title': '成本最优', 'body': ['雅加达（28）为本地区最低成本'], 'foot': '低成本首选'},
        {'tag': '结论 2', 'title': '综合最优',
         'body': ['曼谷（41）成本适中，制造业客户集中'], 'foot': '制造与基建客户首选'},
        {'tag': '结论 3', 'title': '总部型',
         'body': ['新加坡（100）为成本锚点', '治理规范、融资条件最优'], 'foot': '区域总部形态'},
        {'tag': '结论 4', 'title': '合规提示',
         'body': ['三国均要求外籍与本地雇员配比', '工作许可审批 1-3 个月'],
         'foot': '提前启动审批'},
    ],
}

# 驻地方案建议表（按地区；首行为列名）
PLAN_ROWS = {
    'gulf': [
        ['方案', '建议驻地', '适用情形', '成本水平', '备注'],
        ['A · 基准', '沙特（利雅得）', '核心客户在沙特、需贴近决策层', '100', '外籍配额需配套本地雇员'],
        ['B · 枢纽', '阿联酋（迪拜）', '需覆盖多国、外籍团队常驻', '109', '区域总部形态，配套最完善'],
        ['C · 成本', '阿曼（马斯喀特）', '预算敏感、以补充覆盖为主', '71', '客户体量有限'],
    ],
    'asean': [
        ['方案', '建议驻地', '适用情形', '成本水平', '备注'],
        ['A · 总部', '新加坡', '区域总部、融资与治理要求高', '100', 'EP 门槛与打分框架'],
        ['B · 折中', '泰国（曼谷）', '制造/基建客户为主、成本可控', '41', '外籍配比 1:4'],
        ['C · 成本', '印尼（雅加达）', '成本优先、本地市场体量大', '28', '审批周期偏长'],
    ],
}


# =============================================================================
# 章节组件 —— 所有随地区变化的取值一律走 cfg / REGION_META
# =============================================================================
def country_block(name, cur, blo, bhi, olo, ohi, p, idx, tag, rec):
    """每国统一四件套：驻地基准 / 薪资带宽 / 签证与常驻 / 驻地适配。"""
    ex = EXTRA[name]
    rows = [
        ['驻地基准', ex['macro']],
        ['薪资带宽',
         f'基础 {Lr(blo, bhi, cur)}（≈{Cr(blo, bhi, cur)} / ≈{Ur(blo, bhi, cur)}）<br/>'
         f'月度总包 OTE {Lr(olo, ohi, cur)}（≈{Cr(olo, ohi, cur)} / ≈{Ur(olo, ohi, cur)}） · {p}'],
        ['签证与常驻', ex['residency']],
        ['驻地适配', ex['fit']],
    ]
    return [Paragraph(inline_safe(f'{name}｜{tag}｜成本指数 {idx}｜{rec}'), dsh),
            KV(rows, cw=[UW * 0.13, UW * 0.87])]


def overview_table(cfg):
    """横向比价总览：本币区间 + 年成本（人民币万元）+ 成本指数（避免窄列数字断行）。"""
    rows = [['驻地', '基础月薪<br/>（本币）', '月度总包 OTE<br/>（本币）',
             '雇主年成本<br/>（≈¥ 万元）', '成本<br/>指数']]
    for name, cur, blo, bhi, olo, ohi, p, idx, tag, rec in COUNTRY[cfg['key']]:
        rows.append([name.split('（')[0], Lr(blo, bhi, cur), Lr(olo, ohi, cur),
                     annual_wan(olo, ohi, cur, EMPLOYER_COST[name]), str(idx)])
    return T(rows, cw=[UW * 0.15, UW * 0.25, UW * 0.28, UW * 0.19, UW * 0.13], keep=False)


def decision_table(cfg):
    rows = [['驻地', '成本指数', '驻地定位', '综合建议']]
    for name, cur, blo, bhi, olo, ohi, p, idx, tag, rec in COUNTRY[cfg['key']]:
        rows.append([name.split('（')[0], str(idx), tag, rec])
    return T(rows, cw=[UW * 0.25, UW * 0.16, UW * 0.24, UW * 0.35], keep=False)


def rates_block(cfg):
    """汇率速查：只列本地区涉及币种 + USD。"""
    curs = []
    for row in COUNTRY[cfg['key']]:
        if row[1] not in curs:
            curs.append(row[1])
    return rates_table(curs)


def out_path(cfg):
    return os.path.join(WORK, f'{CLIENT}_{JOB}{cfg["file"]}薪酬带宽报告_客户版.pdf')


# =============================================================================
# 报告装配
# =============================================================================
def build_story(cfg):
    meta = REGION_META[cfg['key']]          # ★ 地区口径唯一来源
    story = []

    # ---------- 封面（副标题只写中性信息，不出现「客户版」） ----------
    cover(
        story, BRAND_BIG, CLIENT, BRAND_EN,
        f'{JOB}（{JOB_EN}）{cfg["title"]}薪酬带宽报告',
        cfg['cb_line'],
        [['报告日期', DATE],
         ['数据口径', meta['basis']],
         ['岗位', f'{JOB} {JOB_EN}（经验要求 {EXP_BAND} · {cfg["short"]}驻地比价场景）'],
         ['成本基准', cfg['cb_note']],
         ['数据有效期', '基准日以落款为准 · 建议 3-6 个月内复用，超期需按最新市场数据复核'],
         ['输出', '用友薪福社 · 中企出海人力资源服务']],
    )

    # ---------- 一、执行摘要 ----------
    story.append(h1t('一、执行摘要'))
    story.append(Paragraph(inline_safe(
        f'本报告覆盖 {CLIENT} {JOB}（{JOB_EN}）在{cfg["title"]}的驻地选择与薪资带宽对标，'
        f'以 {cfg["anchor"]} 为成本基准，逐国给出带宽区间与驻地建议。'
        f'岗位经验要求 <b>{EXP_BAND}</b>，口径统一为「{EXP_BAND}主力经验档」月度总包；'
        f'带宽下限对应经验门槛端，上限对应资深端，中位对应市场供给最密集段。'), bd))
    story.append(Spacer(1, 2))
    story.append(card_grid(SUMMARY_CARDS[cfg['key']], cols=2))

    # ---------- 二、比价总览 ----------
    story.append(h1t(f'二、{cfg["title"]}带宽总览'))
    story.append(h2t('2.1 薪资带宽与成本指数'))
    story.append(overview_table(cfg))
    story.append(Spacer(1, 4))
    story.append(Paragraph(inline_safe(cfg['bridge']), dc))
    story.append(Spacer(1, 4))
    story.append(Paragraph(inline_safe(
        '「成本指数」仅反映薪资水平，不含雇主附加成本的口径差异，故与雇主年成本的比例并非一一对应；'
        '换算预算请以「雇主年成本」列为准。'), dc))
    story.append(Spacer(1, 9))
    story.append(h2t('2.2 雇主成本与到手测算'))
    story.append(employer_table(COUNTRY[cfg['key']], EMPLOYER_COST))
    story.append(Spacer(1, 4))
    story.append(Paragraph(inline_safe(
        '雇主附加率 = 社保雇主部分 + 离职金年计提，按外籍雇员口径；封顶类项目已折算为岗位实际比率。'
        + '薪酬结构通则：' + EMPLOYER_STRUCT[cfg['key']] + '。'
        + '个税为估算值，未计个人扣除项，实际以当地申报为准。'), dc))

    # ---------- 三、分国带宽与驻地基准 ----------
    story.append(h1t('三、分国带宽与驻地基准'))
    for i, row in enumerate(COUNTRY[cfg['key']], 1):
        name, cur, blo, bhi, olo, ohi, p, idx, tag, rec = row
        story.append(h2t(f'3.{i} {name}'))
        for el in country_block(name, cur, blo, bhi, olo, ohi, p, idx, tag, rec):
            story.append(el)
        story.append(Spacer(1, 6))

    # ---------- 四、驻地方案建议 ----------
    story.append(h1t('四、驻地方案建议'))
    story.append(T(PLAN_ROWS[cfg['key']],
                   cw=[UW * 0.14, UW * 0.20, UW * 0.32, UW * 0.14, UW * 0.20], keep=False))

    # ---------- 五、汇率与数据来源 ----------
    story.append(h1t('五、汇率速查与数据来源'))
    for el in rates_block(cfg):
        story.append(el)
    story.append(Spacer(1, 6))
    story.append(KV([['薪资', meta['salary_src']],
                     ['宏观', meta['macro_src']],
                     ['雇主成本', meta.get('emp_src', '各国社保机构与劳动主管部门现行费率口径'),
                      ],
                     ['汇率', meta['fx_src']],
                     ['方法', f'岗位经验要求 {EXP_BAND}。区间以市场 P50（中位）–P75（中上）为主，资深/稀缺岗位取 P75–P90；含目标行业溢价'],
                     ['免责', '所有区间为 GROSS 税前月度口径。实际薪资受候选人资历、业务阶段、'
                              '汇率波动与当地法规影响，本报告为参考基准，非最终合同依据']],
                    cw=[UW * 0.10, UW * 0.90]))
    return story


def build_client(cfg):
    story = build_story(cfg)
    header = f'{CLIENT} · {JOB}（{JOB_EN}）| {cfg["short"]} · {RDATE}'
    pdf_title = f'{CLIENT}{JOB}{cfg["file"]}薪酬带宽报告'
    preflight_glyphs(story)          # 生成前字形门禁：未包 Helvetica 的 ② 类 / ③ 类硬禁用字符
    out = build_and_deliver(story, out_path(cfg), header, f'用友薪福社 {RDATE}', pdf_title)
    print(f'[OK] {out}')
    return out


if __name__ == '__main__':
    for key in REGIONS:                     # 一次产出 N 份
        build_client(REGIONS[key])
