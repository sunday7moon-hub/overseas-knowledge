# -*- coding: utf-8 -*-
"""make_single_report.py — 单国单岗薪酬带宽报告骨架（可直接运行）

用法
    1) 复制本文件为你的报告脚本（放工作区，不要就地改本模板）
    2) 改「配置区」与「数据区」两处
    3) python make_single_report.py     → 产出客户版 PDF（自带水印与元数据）
    4) 跑质检：
       python ~/.workbuddy/skills/pdf-report-layout/scripts/qc_client_pdf.py \\
              --color "#1f4f8f" "<输出的.pdf>"

结构（总分总，6 章）
    封面 → 一、执行摘要 → 二、市场基准 → 三、分档薪资带宽
         → 四、候选人报价校准 → 五、驻地与用工要点 → 六、数据来源与口径

⚠️ 示例数据为「某中企 · 泰国 · 大客户经理」，仅用于验证链路，务必替换为真实调研数据。
⚠️ 门禁（见 SKILL.md）：正文/页眉/元数据不得出现「客户版 / 客户交付版 / 内部视角禁词」。
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
# 配置区 —— 每次新报告改这里
# =============================================================================
CLIENT = '示例客户'                       # 客户简称（用于页眉/文件名/元数据）
CLIENT_FULL = '示例客户（中国）有限公司'    # 客户全称（封面副标题可用）
BRAND_BIG = 'SAMPLE'                     # 封面品牌大字
BRAND_EN = 'Sample Client Co., Ltd.'     # 封面英文名（可留空字符串）
JOB = '大客户经理'                        # 岗位中文名
JOB_EN = 'Key Account Manager'           # 岗位英文/缩写
COUNTRY = '泰国'                          # 驻地国家
CITY = '曼谷'                             # 驻地城市
CURRENCY = 'THB'                         # 本币代码（务必与 RATES 中一致）

DATE = '2026年9月14日'
RDATE = '2026.09.14'
WORK = os.path.expanduser('~/WorkBuddy')  # 输出目录（改成实际工作区绝对路径）

# 汇率：锁定当日口径（示例沿用 kit 基线；实际使用务必以当日 CFETS 中间价更新）
set_rates({}, basis='2026-09-01 中国外汇交易中心（CFETS）中间价')

# 交付件命名（门禁 6）：文件名保留 `_客户版`；不带「水印版」。
# ⚠️ 路径在 build_client() 内实时拼接——若写成模块级常量，改 WORK 不会生效。
def out_path():
    return os.path.join(WORK, f'{CLIENT}_{JOB}{COUNTRY}薪酬带宽报告_客户版.pdf')

# =============================================================================
# 数据区 —— 换成真实调研数据
# =============================================================================
# 分档带宽：(经验档, 基础月薪下限, 上限, 月度总包OTE下限, 上限, 市场分位)
BANDS = [
    ('5-8 年（入门）',   70000,  95000,  84000, 118000, 'P50-P65'),
    ('8-12 年（推荐档）', 95000, 130000, 114000, 162000, 'P60-P75'),
    ('12-18 年（资深）', 130000, 175000, 156000, 218000, 'P70-P85'),
    ('18+ 年（稀缺）',  175000, 230000, 210000, 287000, 'P80-P95'),
]
RECOMMEND_INDEX = 1                       # 推荐档在 BANDS 中的下标

# 市场基准：(指标, 值, 备注)  值可为已格式化字符串
MARKET = [
    ('法定最低工资',      f"{L(363, CURRENCY)}/日", '曼谷及周边最低日薪标准'),
    ('全行业平均月薪',    f"{M(25000, CURRENCY)}", '全国城镇就业口径'),
    ('目标行业平均月薪',  f"{Mr(45000, 65000, CURRENCY)}", 'B2B 销售/客户管理岗'),
    ('雇主附加成本',      '雇主 SSO 5%，封顶 THB 750/月（本岗位实际约 0.5%）；无强制离职金年计提',
                          '泰国社保局 SSO'),
    ('个人所得税',        '5-35% 累进，本岗位量级估算有效税率约 22-26%',
                          '按居民口径估算，未计个人扣除项与家庭状况'),
    ('到手测算',          '总包扣除个税后即为到手，雇主成本另含上述附加',
                          '预算换算请用雇主口径，勿直接用总包'),
    ('外籍用工门槛',      '每 1 名外籍配 4 名泰籍', '按注册资本分档'),
]

# 年度总包：(岗位档位, 下限, 上限)
ANNUAL = [
    ('大客户经理（推荐档）', 114000 * 12, 162000 * 12),
    ('资深大客户经理',       156000 * 12, 218000 * 12),
]

# 候选人校准：可选。没有候选人则设 CANDIDATE = None 跳过该章
CANDIDATE = {
    'desc': '猎头推荐的 15 年经验候选人',
    'ask_lo': 190000, 'ask_hi': 230000,
    'cal_lo': 130000, 'cal_hi': 175000,     # 同资历档市场校准区间
    'note': '报价位于资深档 P85-P95，市场可解释；若按推荐档口径则超出 45-75%。',
}

# 驻地与用工要点：(标签, 内容)
RESIDENCY = [
    ('驻地基准', f'个税 5-35% 累进 · 雇主社保 5%，上限 THB 750/月（封顶后实际约 0.5%）· 曼谷平均月薪 {M(25000, CURRENCY)}'),
    ('签证与常驻', '外籍需 Non-B 签证 + 工作许可，审批周期约 1-2 个月；常驻条件良好'),
    ('用工合规', '外籍与本地雇员配比按注册资本分档，一般 1:4；社保与代扣代缴需按月申报'),
    ('驻地适配', '制造业与数字基建客户集中，外籍社区成熟；跨府差旅需求较多'),
]

SUMMARY = [
    f"**推荐档位**：{BANDS[RECOMMEND_INDEX][0]}，基础月薪 {Mr(BANDS[RECOMMEND_INDEX][1], BANDS[RECOMMEND_INDEX][2], CURRENCY)}，"
    f"月度总包（OTE）{Mr(BANDS[RECOMMEND_INDEX][3], BANDS[RECOMMEND_INDEX][4], CURRENCY)}，对应市场 {BANDS[RECOMMEND_INDEX][5]}。",
    f"**年度成本**：推荐档年度总包 {Cr(ANNUAL[0][1], ANNUAL[0][2], CURRENCY, wan=True)}，"
    f"约为当地全行业平均月薪的 {round(((BANDS[RECOMMEND_INDEX][1]+BANDS[RECOMMEND_INDEX][2])/2)/25000, 1)} 倍，属行业合理溢价区间。",
    '**人才池**：目标经验段人才供给充足，建议以推荐档为主推区间，资深档作为上限备用。',
]

SOURCES = [
    ('薪资', 'Michael Page / Hays / Mercer 薪酬指南、LinkedIn Talent Insights、Jobstreet、Paylab、ERI（每条区间至少 2 源交叉）'),
    ('宏观', '泰国劳工部、社保局（SSO）、国家统计局；泰国央行公开数据'),
    ('汇率', f'CFETS 中国外汇交易中心中间价（1 USD = 6.7809 CNY）；{CURRENCY} 取同日实时值'),
    ('方法', '区间以市场 P50（中位）–P75（中上）为主，资深/稀缺岗位取 P75–P90；含目标行业溢价'),
    ('免责', '所有区间为 GROSS 税前月度口径。实际薪资受候选人资历、业务阶段、汇率波动与当地法规影响，'
             '本报告为参考基准，非最终合同依据'),
]


# =============================================================================
# 章节构建
# =============================================================================
def build_story():
    story = []

    # ---------- 封面 ----------
    cover(
        story, BRAND_BIG, CLIENT, BRAND_EN,
        f'{JOB}（{COUNTRY}）薪酬带宽与招聘建议报告',
        f'{COUNTRY}（{CITY}）',                       # 副标题：只写中性信息
        [['报告日期', DATE],
         ['数据口径', f'年薪/月薪 GROSS 税前 · {CURRENCY} / ≈¥ / ≈$ 三栏'],
         ['岗位', f'{JOB} {JOB_EN}（常驻{COUNTRY}）'],
         ['汇率基准', RATE_BASIS],
         ['输出', '用友薪福社 · 中企出海人力资源服务']],
    )

    # ---------- 一、执行摘要 ----------
    story.append(h1t('一、执行摘要'))
    for line in SUMMARY:
        story.append(Paragraph(inline_safe(line), bd))
    story.append(Spacer(1, 4))
    story.append(callout(
        f'决策要点：以 {BANDS[RECOMMEND_INDEX][0]} 为主推区间，'
        f'基础 {Mr(BANDS[RECOMMEND_INDEX][1], BANDS[RECOMMEND_INDEX][2], CURRENCY)}，'
        f'月度总包 {Mr(BANDS[RECOMMEND_INDEX][3], BANDS[RECOMMEND_INDEX][4], CURRENCY)}。'))

    # ---------- 二、市场基准 ----------
    story.append(h1t('二、市场基准（官方依据）'))
    story.append(Paragraph(inline_safe(
        f'{COUNTRY}宏观薪酬与用工参数，作为本报告分档建议的对照基线：'), bd))
    story.append(KV([[k, f'{v}<br/>{n}'] for k, v, n in MARKET],
                    cw=[UW * 0.22, UW * 0.78]))

    # ---------- 三、分档薪资带宽 ----------
    story.append(h1t('三、分档薪资带宽建议（核心交付）'))
    story.append(h2t(f'3.1 {JOB}（{COUNTRY}驻地）'))
    rows = [['经验档', '基础月薪<br/>（本币）', '基础<br/>≈¥ / ≈$',
             '月度总包 OTE<br/>（本币）', 'OTE<br/>≈¥ / ≈$', 'P 定位']]
    for name, blo, bhi, olo, ohi, p in BANDS:
        rows.append([name, Lr(blo, bhi, CURRENCY), CU2(blo, bhi, CURRENCY),
                     Lr(olo, ohi, CURRENCY), CU2(olo, ohi, CURRENCY), p])
    story.append(T(rows, cw=[UW * 0.16, UW * 0.19, UW * 0.19,
                             UW * 0.19, UW * 0.19, UW * 0.08], keep=False))
    story.append(Spacer(1, 4))
    story.append(Paragraph(inline_safe(
        f'注：本外币换算锁定 {RATE_BASIS}，三栏口径一致；'
        f'总包 OTE 按基础月薪上浮 20-25% 的奖金率折算。'), dc))

    story.append(h2t('3.2 年度总包一览'))
    rows = [['岗位档位', '年度总包（本币）', '≈人民币（万元）', '≈美元']]
    for name, lo, hi in ANNUAL:
        rows.append([name, Lr(lo, hi, CURRENCY), Cr(lo, hi, CURRENCY, wan=True),
                     Ur(lo, hi, CURRENCY)])
    story.append(T(rows, cw=[UW * 0.28, UW * 0.28, UW * 0.22, UW * 0.22], keep=False))

    # ---------- 四、候选人报价校准 ----------
    if CANDIDATE:
        story.append(h1t('四、候选人报价校准'))
        story.append(Paragraph(inline_safe(
            f'{CANDIDATE["desc"]}，期望薪资 {Mr(CANDIDATE["ask_lo"], CANDIDATE["ask_hi"], CURRENCY)}。'
            f'对标同资历市场区间 {Mr(CANDIDATE["cal_lo"], CANDIDATE["cal_hi"], CURRENCY)}：'), bd))
        rows = [['项目', '候选人报价', '同资历市场校准', '差异判定']]
        rows.append(['基础月薪（本币）',
                     Lr(CANDIDATE['ask_lo'], CANDIDATE['ask_hi'], CURRENCY),
                     Lr(CANDIDATE['cal_lo'], CANDIDATE['cal_hi'], CURRENCY),
                     '高于校准区间上限'])
        rows.append(['≈人民币 / ≈美元',
                     CU(CANDIDATE['ask_lo'], CANDIDATE['ask_hi'], CURRENCY),
                     CU(CANDIDATE['cal_lo'], CANDIDATE['cal_hi'], CURRENCY), '—'])
        rows.append(['年度总包',
                     Lr(CANDIDATE['ask_lo'] * 12, CANDIDATE['ask_hi'] * 12, CURRENCY),
                     Lr(CANDIDATE['cal_lo'] * 12, CANDIDATE['cal_hi'] * 12, CURRENCY), '按资历档评估'])
        story.append(T(rows, cw=[UW * 0.20, UW * 0.27, UW * 0.27, UW * 0.26], keep=False))
        story.append(Spacer(1, 4))
        story.append(callout(CANDIDATE['note']))

    # ---------- 五、驻地与用工要点 ----------
    story.append(h1t('五、驻地与用工要点'))
    story.append(KV([[k, v] for k, v in RESIDENCY], cw=[UW * 0.16, UW * 0.84]))

    # ---------- 六、数据来源与口径 ----------
    story.append(h1t('六、数据来源与口径'))
    story.append(KV([[k, v] for k, v in SOURCES], cw=[UW * 0.10, UW * 0.90]))
    story.append(Spacer(1, 6))
    story.append(Paragraph(inline_safe(
        f'本报告由 用友薪福社 编制 · {DATE} · 所有金额为税前口径，汇率锁定 {RATE_BASIS}'), dc))

    return story


def build_client():
    """产出客户版 PDF（含水印 + 元数据标题）。"""
    story = build_story()
    header = f'{CLIENT} · {JOB}（{COUNTRY}）| {RDATE}'
    pdf_title = f'{CLIENT}{JOB}{COUNTRY}薪酬带宽报告'
    out = build_and_deliver(story, out_path(), header, f'用友薪福社 {RDATE}', pdf_title)
    print(f'[OK] {out}')
    return out


if __name__ == '__main__':
    build_client()
