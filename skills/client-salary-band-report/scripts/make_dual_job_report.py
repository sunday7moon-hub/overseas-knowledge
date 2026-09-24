# -*- coding: utf-8 -*-
"""make_dual_job_report.py — **单区域 × 双岗位对比** 薪酬带宽报告骨架（一次产出一份）

适用
    同一区域下**两个岗位**（常见组合：渠道岗 + 管理岗、专员 + 主管）合并成一份报告，
    直接回答「管理岗贵多少、贵在哪」。典型：科脉股份 海外渠道经理 / 海外销售管理 · 东南亚六国。

    与另两个骨架的分工：
      make_single_report.py   → 单国 × 单岗位
      make_region_report.py   → 多地区 × 单岗位（按地区拆成 N 份）
      make_dual_job_report.py → **单区域 × 双岗位**（合并成 1 份，含对比章节）← 本文件

用法
    1) 复制本文件为你的报告脚本（放工作区）
    2) 改「配置区 / 数据区」——**务必整体替换示例数据**（下方为科脉案例，仅作结构示范）
    3) python make_dual_job_report.py   → 产出 1 份客户版 PDF
    4) 交付前两条门禁都要过：
       python ~/.workbuddy/skills/pdf-report-layout/scripts/qc_client_pdf.py --color "#1f4f8f" *.pdf
       python ~/.workbuddy/skills/client-salary-band-report/scripts/content_lint.py *.pdf \\
              --facts ~/.workbuddy/skills/client-salary-band-report/references/client-facts.md --strict

替换清单（改完逐项打勾，漏一项就会把上一个客户的名字带出去）
    [ ] CLIENT / BRAND_BIG / BRAND_EN      客户名（封面 + 页眉 + 元数据）
    [ ] JOB1 / JOB2（+ 英文名）            两个岗位名（封面 / 页眉 / 各表头）
    [ ] EXP_BAND                           经验档（**逐字照抄客户 JD，严禁写窄**）
    [ ] DATE / RDATE / REGION_TITLE        日期 / 地区名
    [ ] FX_BASIS + set_rates()             当日汇率（多源校准，见 SKILL.md 门禁 2）
    [ ] COUNTRY1 / COUNTRY2                两岗位 × N 国的带宽数据
    [ ] EMPLOYER_COST（+ EC_JOB2 特例）    雇主附加率 / 法定奖金 / 估算有效税率
    [ ] EXTRA / SUMMARY_CARDS / PLAN_ROWS  各国要点 / 结论卡 / 方案建议表

设计要点（改结构时别破坏）
    · 成本指数由 `_index_map()` **程序化计算**（锚点国 = 100），不手填——避免锚点漂移。
    · 国别块标题必须含全角竖线「｜」，`content_lint.country_sections()` 靠它识别国别块。
    · 2.4 雇主成本表把两岗位并到**一张表**（4 个金额列），比做两张表更省版面且便于同国对比。
    · 遇到**社保基数封顶**的国家（越南、泰国等），两岗位实际附加率不同，
      用 `EC_JOB2` 覆盖并在表下加 `*` 注说明，不要只写一个值。
    · 客户专属事实**先写进** `references/client-facts.md`，再改本脚本常量，最后跑门禁。
      顺序反了必漏（2026-09-14 控维「8-15 年写成 10-15 年」就是漏在这一步）。
    · 汇率基准说明用本模块自己的常量 `FX_BASIS`：`from kit import RATE_BASIS` 拿到的是
      导入时快照，而 `set_rates()` 改的是 kit 内的全局变量，两边**不会同步**。
"""
import os
import sys


def _load_kit():
    """定位 salary_report_kit.py（复制到任意工作区后仍可用）。"""
    here = os.path.dirname(os.path.abspath(__file__))
    cands = [here,
             os.environ.get('SALARY_REPORT_KIT_DIR'),
             os.path.expanduser('~/.workbuddy/skills/client-salary-band-report/scripts')]
    for c in cands:
        if c and os.path.exists(os.path.join(c, 'salary_report_kit.py')):
            if c not in sys.path:
                sys.path.insert(0, c)
            return
    raise ImportError('未找到 salary_report_kit.py；请设置 SALARY_REPORT_KIT_DIR')


_load_kit()

from salary_report_kit import *                        # noqa: E402,F401,F403
from salary_report_kit import RATE_BASIS, set_rates    # noqa: E402
from reportlab.platypus import Paragraph, Spacer       # noqa: E402

# =============================================================================
# 配置区
# =============================================================================
CLIENT = '科脉股份'
BRAND_BIG = 'KEMAI'
BRAND_EN = '深圳市科脉技术股份有限公司'
JOB1, JOB1_EN = '海外渠道经理', 'Channel Sales Manager'
JOB2, JOB2_EN = '海外销售管理', 'Sales Management Lead'

# ★ 岗位经验档（= 客户岗位准入范围）：**严禁写窄**。
#   客户 JD 原文：渠道经理「5 年以上软件招商经验」；销售管理「5 年以上管理经验」。
EXP_BAND = '5 年以上'

DATE, RDATE = '2026年9月20日', '2026.09.20'
REGION_TITLE, REGION_SHORT = '东南亚六国', '东南亚'
ANCHOR = '新加坡'
WORK = os.environ.get('SALARY_REPORT_OUT') or os.path.dirname(os.path.abspath(__file__))

# 汇率：CFETS 中间价（2026-09-18）× 市场 mid-market（2026-09-19/20）交叉中值。
# ⚠️ 单一报告内所有换算锁定同一组汇率，不得混用不同日子。
# ⚠️ 基准说明必须用**本模块自己的常量**：`from kit import RATE_BASIS` 拿到的是导入时快照，
#    而 set_rates() 更新的是 kit 模块内的全局变量，两边不会同步（会渲染出旧日期）。
FX_BASIS = '2026-09-18 CFETS 人民币中间价 × 市场 mid-market 交叉中值'
set_rates({
    'USD': (6.7521,    1.0),
    'SGD': (5.2636,    0.77954),
    'MYR': (1.6429,    0.24332),
    'THB': (0.20150,   0.029842),
    'PHP': (0.10698,   0.015844),
    'IDR': (0.00037902, 0.00005613),
    'VND': (0.00025850, 0.00003829),
}, basis=FX_BASIS)

# =============================================================================
# 数据区
# =============================================================================
# 国家行：(国家, 币种, 基础下限, 基础上限, OTE下限, OTE上限, 分位, 成本指数占位, 驻地定位, 综合建议)
# 成本指数由 _index_map() 按锚点国 = 100 程序化计算，不手填（避免锚点漂移）。
COUNTRY1 = [   # 海外渠道经理 —— 渠道招商 / 代理商开发与管理 / 回款
    ('新加坡',               'SGD', 9500,       12500,      12000,      16000,       'P60-P75', 0, '区域总部',     '首选推荐'),
    ('马来西亚（吉隆坡）',    'MYR', 9000,       12500,      11000,      16000,       'P50-P70', 0, '枢纽驻地',     '推荐'),
    ('泰国（曼谷）',         'THB', 85000,      120000,     105000,     155000,      'P50-P70', 0, '零售客户密集', '推荐'),
    ('越南（胡志明市）',      'VND', 45000000,   70000000,   55000000,   95000000,    'P50-P70', 0, '高增长市场',   '推荐'),
    ('菲律宾（马尼拉）',      'PHP', 85000,      120000,     100000,     155000,      'P50-P70', 0, '成本备选',     '备选'),
    ('印度尼西亚（雅加达）',  'IDR', 28000000,   42000000,   33000000,   52000000,    'P50-P70', 0, '成本最低',     '成本备选'),
]

COUNTRY2 = [   # 海外销售管理 —— 当地销售团队管理 / 市场布局 / 高级销售
    # 溢价（相对渠道岗 OTE 中值）按各国管理人才供给差异设定，区间 +13% 至 +21%
    ('新加坡',               'SGD', 11500,      15000,      14500,      19500,       'P60-P75', 0, '区域总部',     '首选推荐'),
    ('马来西亚（吉隆坡）',    'MYR', 11500,      14500,      12500,      18500,       'P50-P70', 0, '枢纽驻地',     '推荐'),
    ('泰国（曼谷）',         'THB', 100000,     145000,     125000,     185000,      'P50-P70', 0, '零售客户密集', '推荐'),
    ('越南（胡志明市）',      'VND', 50000000,   80000000,   62000000,   108000000,   'P50-P70', 0, '高增长市场',   '推荐'),
    ('菲律宾（马尼拉）',      'PHP', 95000,      140000,     115000,     185000,      'P50-P70', 0, '成本备选',     '备选'),
    ('印度尼西亚（雅加达）',  'IDR', 32000000,   48000000,   38000000,   60000000,    'P50-P70', 0, '成本最低',     '成本备选'),
]

# -----------------------------------------------------------------------------
# 雇主成本（**外籍雇员口径**｜2025-2026 法规）
#   rate  雇主附加率% = 社保雇主部分 + 离职金年计提（封顶类项目已按本岗位月薪折算为实际比率）
#   bonus 年度法定奖金月数｜tax_lo/hi 估算个人所得税**有效税率**区间%（= 应纳税额 ÷ 税前年收入）
# -----------------------------------------------------------------------------
EMPLOYER_COST = {
    '新加坡':               {'rate': 0.0,  'bonus': 0, 'tax_lo': 10, 'tax_hi': 14,
                            'cost': '外籍雇员不缴 CPF（雇主 17% 仅适用于公民/PR）；无强制年终奖金'},
    '马来西亚（吉隆坡）':    {'rate': 2.4,  'bonus': 0, 'tax_lo': 14, 'tax_hi': 18,
                            'cost': '外籍 EPF 2%（2025.10 起强制）+ SOCSO 工伤险按上限折算；无强制年终奖金'},
    '泰国（曼谷）':         {'rate': 0.5,  'bonus': 0, 'tax_lo': 15, 'tax_hi': 19,
                            'cost': 'SSO 雇主 5% 但封顶 THB 750/月——本岗位实际仅约 0.5%'},
    '越南（胡志明市）':      {'rate': 15.2, 'bonus': 0, 'tax_lo': 11, 'tax_hi': 15,
                            'cost': '社保 17.5% + 医保 3% + 工会费 2%，缴费基数封顶 VND 5,060 万/月 → 本岗位实际约 15.2%'},
    '菲律宾（马尼拉）':      {'rate': 2.9,  'bonus': 1, 'tax_lo': 15, 'tax_hi': 19,
                            'cost': 'SSS / PhilHealth / Pag-IBIG 雇主部分（外籍口径）+ 法定 13 薪 1 个月'},
    '印度尼西亚（雅加达）':  {'rate': 5.3,  'bonus': 0, 'tax_lo': 16, 'tax_hi': 20,
                            'cost': 'BPJS 工伤/身故雇主部分 + Kesehatan 封顶折算 ≈5.3%；外籍豁免 JP 养老'},
}
# 越南是唯一「两岗位附加率不同」的国家：封顶 VND 5,060 万/月，薪资越高实际比率越低。
EC_JOB2 = dict(EMPLOYER_COST)
EC_JOB2['越南（胡志明市）'] = dict(
    EMPLOYER_COST['越南（胡志明市）'], rate=12.4,
    cost='社保 17.5% + 医保 3% + 工会费 2%，缴费基数封顶 VND 5,060 万/月 → 本岗位实际约 12.4%')

# 薪酬结构通则（放第二章统一说明，逐国块不重复）
EMPLOYER_STRUCT = ('固定 : 浮动 ≈ 70 : 30（OTE 口径）；渠道岗浮动与招商回款进度挂钩，'
                   '管理岗浮动与区域营收达成挂钩；住房津贴多为总包外单列，视合同约定；'
                   '六国中仅菲律宾 13 薪为法定，越南 13 薪为惯例（非法定）')

# -----------------------------------------------------------------------------
# 各国驻地要点（按国家全名索引，须与 COUNTRY 的 name 完全一致）
# -----------------------------------------------------------------------------
EXTRA = {
    '新加坡': {
        'macro': '个税 0–24% 累进 · 雇主 CPF 17%（仅公民/PR，外籍不缴）· 全职工月薪中位数 S$5,775',
        'residency': '外籍 EP 门槛 S$5,600/月起 + COMPASS 打分框架',
        'fit': '区域总部聚集度最高，客户决策与融资条件最优；用人成本约为吉隆坡的 3 倍以上',
    },
    '马来西亚（吉隆坡）': {
        'macro': '个税 0–30% 累进 · 外籍 EPF 2%（2025.10 起强制，本地雇员 12–13%）· 平均月薪 RM 3,000–3,500',
        'residency': 'EP I/II/III 三档，月薪达门槛可申请长期多次往返准证',
        'fit': '华语 + 英语 + 马来语人才池，覆盖中南半岛与马来群岛的调度成本最低',
    },
    '泰国（曼谷）': {
        'macro': '个税 5–35% 累进 · 雇主社保 5% 封顶 THB 750/月（折算约 0.5%）· 曼谷平均月薪 THB 25,000–30,000',
        'residency': 'Non-B 签证 + 工作许可，外籍配额与本地雇员比例需按现行规定匹配',
        'fit': '零售与餐饮连锁客户密度高，外籍社区成熟；跨府差旅频繁',
    },
    '越南（胡志明市）': {
        'macro': '个税 5–35% 累进（2026 起改五档）· 外籍社保 20.5% 且基数封顶 VND 5,060 万/月 · 全国平均月薪 VND 900 万（GSO 2026 上半年），区域最低工资 2026 年上调 7.2%',
        'residency': '工作许可 + 临时居留卡（TRC），许可剩余有效期满 12 个月方可申请',
        'fit': '外资软件渗透最快，渠道空白多、代理激活成本低；13 薪为市场惯例但非法定',
    },
    '菲律宾（马尼拉）': {
        'macro': '个税 0–35% 累进 · <b>法定 13 薪</b> · 外籍社保雇主部分约 2.9% · 马尼拉平均月薪 PHP 20,000–25,000',
        'residency': '9(g) 工作签证 + AEP 劳工许可，审批约 2–3 个月',
        'fit': '英语环境最好、人力成本低；分销与回款环节需重点管控',
    },
    '印度尼西亚（雅加达）': {
        'macro': '个税 5–35% 累进 · 雇主 BPJS 约 5.3%（外籍豁免 JP）· 全国平均月薪 IDR 3.33 百万（BPS）',
        'residency': 'RPTKA 工作许可 + 本地雇员配比要求，合规流程 1–3 个月',
        'fit': '人口与零售网点基数最大，本地渠道商话语权强；跨岛差旅强度大',
    },
}

# 执行摘要结论卡
SUMMARY_CARDS = [
    {'tag': '结论 1', 'title': '成本最优',
     'body': ['雅加达综合成本为六国最低', '渠道经理雇主年成本约为新加坡的四分之一'],
     'foot': '成本优先首选'},
    {'tag': '结论 2', 'title': '增长优先',
     'body': ['胡志明市外资软件渗透最快、渠道空白最多', '代理激活成本低于泰国与马来'],
     'foot': '增速优先首选'},
    {'tag': '结论 3', 'title': '总部与枢纽',
     'body': ['新加坡为区域总部形态，成本为六国最高', '吉隆坡以约三成成本承接同等人力结构'],
     'foot': '总部 + 枢纽组合'},
    {'tag': '结论 4', 'title': '合规提示',
     'body': ['越南外籍社保基数封顶 VND 5,060 万/月', '马来外籍 EPF 2% 自 2025.10 强制；菲律宾 13 薪法定'],
     'foot': '预算须含法定附加'},
]

# 驻地方案建议表
PLAN_ROWS = [
    ['方案', '建议驻地', '适用情形', '成本水平', '备注'],
    ['A · 总部型', '新加坡', '区域总部、融资与治理要求高', '100', 'EP 门槛 + COMPASS 打分'],
    ['B · 枢纽型', '马来西亚（吉隆坡）', '双语团队、需同时覆盖半岛与群岛', '约 30', '外籍 EPF 2%'],
    ['C · 增长型', '越南（胡志明市）', '渠道空白多、外资渗透快', '约 26', '社保基数封顶'],
    ['D · 规模型', '印度尼西亚（雅加达）', '成本优先、零售网点基数最大', '约 22', '审批周期 1–3 个月'],
]


# =============================================================================
# 派生量（成本指数程序化计算，禁止手填）
# =============================================================================
def _index_map(country, anchor=ANCHOR):
    """成本指数：以锚点国 = 100，按「OTE 中值 ×（12 + 法定奖金）× 汇率」的年成本口径。

    ⚠️ 指数只反映薪资水平，不含雇主附加成本差异——换算预算须以雇主年成本列为准。
    """
    base = None
    raw = {}
    for name, cur, _bl, _bh, olo, ohi, _p, _i, _t, _r in country:
        ec = EMPLOYER_COST[name]
        mid = (olo + ohi) / 2
        raw[name] = mid * (12 + ec.get('bonus', 0)) * RATES[cur][0]
    base = raw[anchor]
    return {k: int(round(v / base * 100)) for k, v in raw.items()}


IDX1, IDX2 = _index_map(COUNTRY1), _index_map(COUNTRY2)


# =============================================================================
# 章节组件
# =============================================================================
def _row(country, name):
    for r in country:
        if r[0] == name:
            return r
    raise KeyError(name)


def band_cell(country, name):
    """带宽单元格：基础 + OTE 三币 + 分位。"""
    _n, cur, blo, bhi, olo, ohi, p, _i, _t, _r = _row(country, name)
    return (f'基础 {Lr(blo, bhi, cur)}（≈{Cr(blo, bhi, cur)} / ≈{Ur(blo, bhi, cur)}）<br/>'
            f'月度总包 OTE {Lr(olo, ohi, cur)}（≈{Cr(olo, ohi, cur)} / ≈{Ur(olo, ohi, cur)}） · {p}')


def country_block(name):
    """每国统一五件套：驻地基准 / 渠道经理带宽 / 销售管理带宽 / 签证与常驻 / 驻地适配。"""
    ex = EXTRA[name]
    rows = [
        ['驻地基准', ex['macro']],
        [f'{JOB1}', band_cell(COUNTRY1, name)],
        [f'{JOB2}', band_cell(COUNTRY2, name)],
        ['签证与常驻', ex['residency']],
        ['驻地适配', ex['fit']],
    ]
    return KV(rows, cw=[UW * 0.15, UW * 0.85])


def overview_table(country, idx_map):
    """横向比价总览：本币区间 + 雇主年成本（人民币万元）+ 成本指数。"""
    rows = [['驻地', '基础月薪<br/>（本币）', '月度总包 OTE<br/>（本币）',
             '雇主年成本<br/>（≈¥ 万元）', '成本<br/>指数']]
    for name, cur, blo, bhi, olo, ohi, _p, _i, _t, _r in country:
        rows.append([name.split('（')[0], Lr(blo, bhi, cur), Lr(olo, ohi, cur),
                     annual_wan(olo, ohi, cur, EMPLOYER_COST[name]),
                     str(idx_map[name])])
    return T(rows, cw=[UW * 0.15, UW * 0.24, UW * 0.27, UW * 0.19, UW * 0.15], keep=False)


def employer_table_dual():
    """雇主成本与到手测算（双岗位同表）：4 个金额列并排，便于同国横向比。"""
    rows = [['驻地', '雇主<br/>附加率', '法定<br/>奖金',
             f'{JOB1}<br/>雇主年成本', f'{JOB1}<br/>估算净得',
             f'{JOB2}<br/>雇主年成本', f'{JOB2}<br/>估算净得']]
    for name, cur, _bl, _bh, olo1, ohi1, _p, _i, _t, _r in COUNTRY1:
        r2 = _row(COUNTRY2, name)
        ec1, ec2 = EMPLOYER_COST[name], EC_JOB2[name]
        t1, _g1, n1 = employer_stats(ec1, olo1, ohi1, cur)
        t2, _g2, n2 = employer_stats(ec2, r2[4], r2[5], cur)
        rows.append([name.split('（')[0],
                     (f"{ec1['rate']:.1f}% *" if ec1['rate'] != ec2['rate'] else f"{ec1['rate']:.1f}%"),
                     (f"{ec1['bonus']} 个月" if ec1.get('bonus') else '—'),
                     f'≈¥{t1:.1f} 万', f'≈¥{n1:.1f} 万',
                     f'≈¥{t2:.1f} 万', f'≈¥{n2:.1f} 万'])
    return T(rows, cw=[UW * 0.135, UW * 0.105, UW * 0.085,
                       UW * 0.165, UW * 0.165, UW * 0.165, UW * 0.18], keep=False)


def premium_table():
    """双岗位溢价：看管理岗相对渠道岗贵多少、贵在哪。"""
    rows = [['驻地', f'{JOB1}<br/>（≈¥ 万/年）', f'{JOB2}<br/>（≈¥ 万/年）',
             '管理岗溢价', '主要驱动']]
    driver = {
        '新加坡': '管理半径大、双语管理人才稀缺度最高',
        '马来西亚（吉隆坡）': '本地双语管理人才供给相对充足',
        '泰国（曼谷）': '本地团队规模与合规责任较重',
        '越南（胡志明市）': '本地管理者供给相对充足，溢价六国最低',
        '菲律宾（马尼拉）': '团队规模大、渠道层级多',
        '印度尼西亚（雅加达）': '跨岛管理与本地渠道博弈成本',
    }
    for name, cur, _bl, _bh, olo1, ohi1, _p, _i, _t, _r in COUNTRY1:
        r2 = _row(COUNTRY2, name)
        m1, m2 = (olo1 + ohi1) / 2, (r2[4] + r2[5]) / 2
        rows.append([name.split('（')[0],
                     f'{(m1 * 12 * RATES[cur][0]) / 10000:.1f}',
                     f'{(m2 * 12 * RATES[cur][0]) / 10000:.1f}',
                     f'+{(m2 / m1 - 1) * 100:.0f}%',
                     driver[name]])
    return T(rows, cw=[UW * 0.18, UW * 0.17, UW * 0.17, UW * 0.14, UW * 0.34], keep=False)


def decision_table():
    """决策矩阵：指数只列一列（同国两岗位指数接近，重复列无信息增量），改列两岗位实际年成本。"""
    rows = [['驻地', '成本<br/>指数', f'{JOB1}<br/>（≈¥ 万/年）', f'{JOB2}<br/>（≈¥ 万/年）',
             '驻地定位', '综合建议']]
    for name, cur, _bl, _bh, olo1, ohi1, _p, _i, _tag, _rec in COUNTRY1:
        r2 = _row(COUNTRY2, name)
        t1, _g1, _n1 = employer_stats(EMPLOYER_COST[name], olo1, ohi1, cur)
        t2, _g2, _n2 = employer_stats(EC_JOB2[name], r2[4], r2[5], cur)
        rows.append([name.split('（')[0], str(IDX1[name]), f'{t1:.1f}', f'{t2:.1f}',
                     r2[8], r2[9]])
    return T(rows, cw=[UW * 0.19, UW * 0.12, UW * 0.17, UW * 0.17, UW * 0.18, UW * 0.17],
             keep=False)


def rates_block():
    return rates_table(['SGD', 'MYR', 'THB', 'VND', 'PHP', 'IDR'])


def out_path():
    return os.path.join(WORK, f'{CLIENT}_{JOB1}与{JOB2}_{REGION_TITLE}薪酬带宽报告_客户版.pdf')


# =============================================================================
# 报告装配
# =============================================================================
def build_story():
    story = []

    # ---------- 封面 ----------
    cover(
        story, BRAND_BIG, CLIENT, BRAND_EN,
        f'{JOB1} · {JOB2}<br/>{REGION_TITLE}薪酬带宽报告',
        f'{JOB1}（{JOB1_EN}）／{JOB2}（{JOB2_EN}）',
        [['报告日期', DATE],
         ['数据口径', 'GROSS 税前（六国均为个税累进制，最高档 20–35%；新加坡税负最低）'],
         ['岗位', f'{JOB1}（经验要求 {EXP_BAND}）／{JOB2}（管理经验 {EXP_BAND}）'],
         ['成本基准', f'以{ANCHOR} = 100 为锚点'],
         ['数据有效期', '基准日以落款为准 · 建议 3-6 个月内复用，超期需按最新市场数据复核'],
         ['输出', '用友薪福社 · 中企出海人力资源服务']],
    )

    # ---------- 一、执行摘要 ----------
    story.append(h1t('一、执行摘要'))
    story.append(Paragraph(inline_safe(
        f'本报告覆盖 {CLIENT} <b>{JOB1}</b>与<b>{JOB2}</b>两个岗位在{REGION_TITLE}'
        f'（新加坡、马来西亚、泰国、越南、菲律宾、印度尼西亚）的薪资带宽对标与驻地选择。'
        f'两岗位经验要求均为 <b>{EXP_BAND}</b>；带宽下限对应经验门槛端，上限对应资深端，'
        f'中位对应市场供给最密集段。管理岗相对渠道岗的溢价约 13–21%（均值约 17%），'
        f'主要来自团队管理半径与本地合规责任。'), bd))
    story.append(Spacer(1, 2))
    story.append(Paragraph(inline_safe(
        f'两岗位的分工边界：<b>{JOB1}</b>对渠道数量与回款负责，考核以招商进度与代理商激活为主；'
        f'<b>{JOB2}</b>对当地销售团队与区域营收负责，考核以团队达成率与市场布局为主。'
        f'反映在薪酬结构上，差距主要在浮动部分——渠道岗与招商／回款进度挂钩，'
        f'管理岗与区域营收达成挂钩，两者固定部分的差距小于浮动部分。'), bd))
    story.append(Spacer(1, 3))
    story.append(card_grid(SUMMARY_CARDS, cols=2))
    story.append(Spacer(1, 3))
    story.append(Paragraph(inline_safe(
        '本报告三处用法：<b>比价与预算换算</b>看第二章「雇主年成本」列——该列已含社保、'
        '法定奖金与离职金等雇主实际支出，请勿用成本指数直接换算预算；'
        '<b>定岗定薪</b>看第三章各国带宽区间与分位标注；'
        '<b>驻地选择</b>看第四章决策矩阵与方案建议。'), bd))

    # ---------- 二、双岗位带宽总览 ----------
    story.append(h1t('二、双岗位带宽总览'))
    story.append(h2t(f'2.1　{JOB1}（{JOB1_EN}）'))
    story.append(overview_table(COUNTRY1, IDX1))
    story.append(Spacer(1, 9))
    story.append(h2t(f'2.2　{JOB2}（{JOB2_EN}）'))
    story.append(overview_table(COUNTRY2, IDX2))
    story.append(Spacer(1, 4))
    story.append(Paragraph(inline_safe(
        f'「成本指数」以{ANCHOR} = 100 为基准，仅反映薪资水平，不含雇主附加成本的口径差异，'
        '故与雇主年成本的比例并非一一对应；换算预算请以「雇主年成本」列为准。'
        '两岗位均按本地区同一组市场数据取值，指数口径一致，可直接横向比较。'), dc))

    story.append(Spacer(1, 9))
    story.append(h2t('2.3　管理岗相对渠道岗的溢价'))
    story.append(premium_table())
    story.append(Spacer(1, 3))
    story.append(Paragraph(inline_safe(
        '溢价口径为两岗位 OTE 中值之比，未含雇主附加成本差异。六国溢价区间为 +13% 至 +21%，'
        '越南最低（本地管理者供给相对充足），新加坡最高（双语管理人才稀缺度最高），'
        '均值约 +17%，可作为同国两岗位预算的快速换算系数。'), dc))

    story.append(Spacer(1, 9))
    story.append(h2t('2.4　雇主成本与到手测算'))
    story.append(employer_table_dual())
    story.append(Spacer(1, 3))
    story.append(Paragraph(inline_safe(
        '雇主附加率 = 社保雇主部分 + 离职金年计提，一律按<b>外籍雇员</b>口径；'
        '有缴纳上限的项目（泰国 SSO、越南社保、马来西亚 SOCSO、印尼 Kesehatan）'
        '已按本岗位月薪折算为实际比率，不直接套用名义费率。'
        f'薪酬结构通则：{EMPLOYER_STRUCT}。'
        '「估算净得」= 税前年包（含法定奖金）×（1 – 估算有效税率），'
        '税率为按本报告薪资档位测算的有效税率（非边际税率），未计个人专项扣除，'
        '实际以当地申报为准。'
        '* 越南社保缴费基数封顶 VND 5,060 万/月，销售管理岗薪资更高、'
        '社保占薪资比反而更低，实际附加率约 12.4%。'), dc))

    # ---------- 三、分国带宽与驻地基准 ----------
    story.append(h1t('三、分国带宽与驻地基准'))
    for i, row in enumerate(COUNTRY1, 1):
        name = row[0]
        story.append(Paragraph(inline_safe(
            f'3.{i}　{name}｜{row[8]}｜成本指数 {IDX1[name]}／{IDX2[name]}｜{row[9]}'), dsh))
        story.append(country_block(name))
        story.append(Spacer(1, 6))

    # ---------- 四、驻地选择 ----------
    story.append(h1t('四、驻地选择：决策矩阵与方案建议'))
    story.append(h2t('4.1　横向决策矩阵'))
    story.append(Paragraph(inline_safe(
        '下表按雇主年成本排序。两岗位成本差异在各市场稳定在 +13% 至 +21% 区间内，'
        '因此<b>驻地选择的结论对两个岗位通用</b>——确定驻地后，'
        '按 §2.3 的溢价系数即可推算另一岗位的预算，不必重新做一轮比价。'), dc))
    story.append(decision_table())
    story.append(Spacer(1, 9))
    story.append(h2t('4.2　驻地方案建议'))
    story.append(T(PLAN_ROWS, cw=[UW * 0.13, UW * 0.20, UW * 0.33, UW * 0.13, UW * 0.21], keep=False))
    story.append(Spacer(1, 3))
    story.append(Paragraph(inline_safe(
        '方案 A 与 B 可组合使用：以新加坡承担客户决策与资金职能，以吉隆坡承载交付与渠道管理团队，'
        '是同类出海软件企业在{0}最常见的双驻地结构。若以增速为第一目标，优先考虑方案 C；'
        '若以成本为第一约束，优先考虑方案 D。'.format(REGION_SHORT)), dc))

    # ---------- 五、汇率速查与数据来源 ----------
    story.append(h1t('五、汇率速查与数据来源'))
    for el in rates_block():
        story.append(el)
    story.append(Spacer(1, 6))
    story.append(KV([
        ['薪资', 'Michael Page · Robert Walters · Hays · SalaryExpert/ERI · Payscale · '
                 'Jobstreet · Jobstore · Reeracoen · Indeed · PRTR（各国本地招聘平台与薪酬调查，2026 年）'],
        ['宏观', '新加坡 MOM / CPF · 马来 EPF(KWSP) / SOCSO / LHDN · 泰国 劳工部 / SSO · '
                 '越南 MoLISA / VSS / 税务总局 · 菲律宾 DOLE / SSS / BIR · 印尼 劳工部 / BPJS / BPS'],
        ['雇主成本', '外籍雇员口径：社保雇主部分 + 离职金年计提；封顶类项目按本岗位月薪折算为实际比率'],
        ['汇率', f'{FX_BASIS}；六国币种取同日实时值交叉校准'],
        ['方法', f'两岗位经验要求均为 {EXP_BAND}。区间以市场 P50（中位）–P75（中上）为主，'
                 '稀缺岗位取 P75–P90；含零售与餐饮数字化行业溢价 15–30%，该溢价已包含在带宽数字内'],
        ['免责', '所有区间为 GROSS 税前月度口径。实际薪资受候选人资历、业务阶段、汇率波动与'
                 '当地法规影响，本报告为参考基准，非最终合同依据'],
    ], cw=[UW * 0.10, UW * 0.90]))
    return story


def main():
    story = build_story()
    header = f'{CLIENT} · {JOB1}／{JOB2} | {REGION_TITLE} · {RDATE}'
    pdf_title = f'{CLIENT} {JOB1}／{JOB2} {REGION_TITLE}薪酬带宽报告'
    preflight_glyphs(story)          # 生成前字形门禁：未包 Helvetica 的 ② 类 / ③ 类硬禁用字符
    out = build_and_deliver(story, out_path(), header, f'用友薪福社 {RDATE}', pdf_title)
    print(f'[OK] {out}')
    # 数值自检（供人工复核）
    for name, cur, _bl, _bh, olo, ohi, _p, _i, _t, _r in COUNTRY1:
        r2 = _row(COUNTRY2, name)
        t1, _g, n1 = employer_stats(EMPLOYER_COST[name], olo, ohi, cur)
        t2, _g2, n2 = employer_stats(EC_JOB2[name], r2[4], r2[5], cur)
        print(f'  {name:<12} 指数 {IDX1[name]:>3}/{IDX2[name]:>3}  '
              f'渠道 年成本 {t1:>6.1f} 万 / 净得 {n1:>6.1f} 万  |  '
              f'管理 年成本 {t2:>6.1f} 万 / 净得 {n2:>6.1f} 万')
    return out


if __name__ == '__main__':
    main()
