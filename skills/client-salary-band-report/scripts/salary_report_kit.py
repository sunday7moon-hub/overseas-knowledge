# -*- coding: utf-8 -*-
"""salary_report_kit.py — 薪酬带宽报告生产工具库（现行真相源）

定位
    只放「与客户无关」的工具函数与排版范式。客户数据一律留在各自的 report 脚本里。
    被 make_single_report.py / make_region_report.py 引用，也可独立 import。

为什么存在
    此前工具函数散落在工作区的客户专用脚本里（cowave_v2_build.py 等），
    新任务无法调取，只能靠复制粘贴或翻历史对话 —— 本文件把工作流固化下来。

沉淀来源
    控维通信 RSM（单国 + 中东七国/东南亚五国分地区）、二六三新加坡、拓米洛韩国，
    2026-09-14 定稿（S2 品牌蓝 / KV 表头分级 / 汇率精度 / 水印元数据回写）。

硬约束（与 SKILL.md 门禁一致）
    · 主色 PRIMARY = #1f4f8f（S2 中等深度品牌蓝）：表头 + 章标题 + KV 标签字统一一档。
    · 数据表用 T()（深底表头）；键值表用 KV()（浅底标签列）——不给键值表染深底表头。
    · 汇率表必须用 Cx()/Ux()，禁用 C()/U()（round 会把 IDR/THB 等小币值抹成 0）。
    · 交付件 = 客户版 PDF，文件名不带「水印版」；正文/页眉/元数据不得出现「客户版/客户交付版」。
"""
from __future__ import annotations

import glob
import os

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (KeepTogether, PageBreak, Paragraph,
                                SimpleDocTemplate, Spacer, Table, TableStyle)

# =============================================================================
# 1. 字体：不写死工作区路径，按优先级查找
# =============================================================================
_FONT_ENV = 'SALARY_REPORT_FONT'
_FONT_DOWNLOAD = 'https://github.com/StellarCN/scp_zh/raw/master/fonts/SimHei.ttf'
_FONT_SYSTEM_FALLBACK = [
    '/System/Library/Fonts/Supplemental/Arial Unicode.ttf',
    '/Library/Fonts/Arial Unicode.ttf',
]

FONT_NAME = None


def resolve_font_path():
    """按优先级返回可用中文字体路径：
    ① 环境变量 SALARY_REPORT_FONT  ② skill ./assets/SimHei.ttf
    ③ ~/WorkBuddy/*/fonts/SimHei.ttf（历史工作区）  ④ 系统 Arial Unicode
    """
    env = os.environ.get(_FONT_ENV)
    if env and os.path.exists(env):
        return env

    here = os.path.dirname(os.path.abspath(__file__))
    for cand in (os.path.join(here, '..', 'assets', 'SimHei.ttf'),
                 os.path.join(here, 'SimHei.ttf')):
        if os.path.exists(cand):
            return os.path.abspath(cand)

    for hit in sorted(glob.glob(os.path.expanduser('~/WorkBuddy/*/fonts/SimHei.ttf')), reverse=True):
        return hit

    for cand in _FONT_SYSTEM_FALLBACK:
        if os.path.exists(cand):
            return cand
    return None


def setup_font(font_name='SimHei'):
    """注册中文字体，返回实际使用的字体名（幂等）。"""
    global FONT_NAME
    if FONT_NAME:
        return FONT_NAME

    path = resolve_font_path()
    if path is None:
        # 兜底：下载到 ~/.workbuddy/fonts（不用 /tmp，符合规范 1）
        dest_dir = os.path.expanduser('~/.workbuddy/fonts')
        os.makedirs(dest_dir, exist_ok=True)
        path = os.path.join(dest_dir, 'SimHei.ttf')
        if not os.path.exists(path):
            import urllib.request
            urllib.request.urlretrieve(_FONT_DOWNLOAD, path)

    if 'Arial Unicode' in path:
        font_name = 'ArialUnicode'
    pdfmetrics.registerFont(TTFont(font_name, path))
    FONT_NAME = font_name
    return FONT_NAME


# =============================================================================
# 2. 汇率基准表（使用当日必须更新；币种按需 update）
# =============================================================================
# 格式：'CUR': (→CNY, →USD)
# 基线口径：2026-09-01 CFETS 中间价（1 USD = 6.7809 CNY），海湾币种按官方钉住汇率折算。
# ⚠️ 单一报告内所有换算必须锁定同一组汇率，不得混用不同日子。
RATES = {
    'USD': (6.7809, 1.0),
    'SAR': (1.7962, 0.2648),
    'AED': (1.8361, 0.2708),
    'QAR': (1.8629, 0.27473),
    'KWD': (22.124, 3.2626),
    'BHD': (18.034, 2.6596),
    'OMR': (17.634, 2.6008),
    'ILS': (2.0425, 0.3012),
    'KZT': (0.01458, 0.002149),
    'UZS': (0.0005688, 0.0000839),
    'IDR': (0.0003795, 0.0000559),
    'MYR': (1.6770, 0.2474),
    'SGD': (5.3115, 0.7839),
    'THB': (0.2093, 0.03086),
    'PHP': (0.11855, 0.01748),
    'VND': (0.0002610, 0.0000385),
    'KRW': (0.004907, 0.0007237),
}

RATE_BASIS = '2026-09-01 中国外汇交易中心（CFETS）中间价'


def set_rates(mapping, basis=None):
    """更新/追加汇率。新报告开工时先调一次，锁定当日汇率。"""
    global RATE_BASIS
    RATES.update(mapping)
    if basis:
        RATE_BASIS = basis


# =============================================================================
# 3. 货币格式化
#    大额（薪资）用 C/U（取整，可读）；汇率表用 Cx/Ux（自适应精度，禁取整）
# =============================================================================
def L(amt, cur):
    """本币整数：SAR 32,000"""
    return f"{cur} {amt:,}"


def Lr(lo, hi, cur):
    return f"{cur} {lo:,}–{hi:,}"


def C(amt, cur, wan=False):
    """→ 人民币。wan=True 输出「¥xx.x万」（仅限大额薪资）。"""
    c = amt * RATES[cur][0]
    return f"¥{c / 10000:.1f}万" if wan else f"¥{round(c):,}"


def Cr(lo, hi, cur, wan=False):
    return f"{C(lo, cur, wan)}–{C(hi, cur, wan)}"


def U(amt, cur):
    """→ 美元（取整）。"""
    return f"${round(amt * RATES[cur][1]):,}"


def Ur(lo, hi, cur):
    return f"${round(lo * RATES[cur][1]):,}–${round(hi * RATES[cur][1]):,}"


def CU(lo, hi, cur, wan=False):
    """人民币 / 美元 两栏并排（本币已单列时用）。"""
    return f"{Cr(lo, hi, cur, wan)} / {Ur(lo, hi, cur)}"


def M(amt, cur, wan=False):
    """三币单值：SAR 32,000（≈¥57,478 / ≈$8,474）"""
    return f"{L(amt, cur)}（≈{C(amt, cur, wan)} / ≈{U(amt, cur)}）"


def Mr(lo, hi, cur, wan=False):
    """三币区间，最常用。"""
    return f"{Lr(lo, hi, cur)}（≈{Cr(lo, hi, cur, wan)} / ≈{Ur(lo, hi, cur)}）"


def _fx(v, sym):
    """汇率精度自适应：按数量级选小数位。

    ⚠️ C()/U() 用 round() 取整，只适用于薪资等大额；
    汇率表以 1 单位本币为基数，直接套用会把 IDR/THB 等抹成 0 —— 必须走 Cx()/Ux()。
    """
    if v >= 100:
        return f"{sym}{v:,.1f}"
    if v >= 1:
        return f"{sym}{v:,.2f}"
    if v >= 0.01:
        return f"{sym}{v:.4f}"
    return f"{sym}{v:.6f}"


def Cx(amt, cur):
    return _fx(amt * RATES[cur][0], '¥')


def Ux(amt, cur):
    return _fx(amt * RATES[cur][1], '$')


# =============================================================================
# 4. 字形兼容层
#    SimHei 缺字形 → 包 Helvetica 可救的：¥ £ ¢ € $ – — ·
#    两边都没有的（小币种符号 ₩₺₽₹฿、emoji）→ 一律写 ISO 代码，不要包
#    ⚠️ → ★ ① 在 Helvetica 里没有字形，不要包裹
# =============================================================================
_HELV_WRAP = ['¥', '€', '£', '¢', '$', '–', '—', '·']


def fix_currency(text):
    """表格单元格/独立段落用：把 SimHei 缺字形的符号路由到 Helvetica。"""
    text = str(text)
    for sym in _HELV_WRAP:
        text = text.replace(sym, f'<font face="Helvetica">{sym}</font>')
    return text


def inline_safe(text):
    """行内段落用（正文含 ¥/$/—/· 时）。• 降级为 ·（Helvetica 无 •）。"""
    text = str(text).replace('•', '·')
    for sym in _HELV_WRAP:
        text = text.replace(sym, f'<font face="Helvetica">{sym}</font>')
    return text


# =============================================================================
# 5. 版式常量
# =============================================================================
PRIMARY = colors.HexColor('#1f4f8f')      # S2 品牌交互蓝：表头底 / 章标题 / KV 标签字
ACCENT = colors.HexColor('#c53030')
LIGHT_BG = colors.HexColor('#edf2f7')     # KV 标签列底
ALT_BG = colors.HexColor('#f7fafc')       # 斑马纹浅行
BORDER = colors.HexColor('#e2e8f0')
TEXT_MUTED = colors.HexColor('#4a5568')
HDR_TEXT = colors.HexColor('#eef2f8')     # 表头字（微冷白，不用纯白）

PW, PH = A4
LM = 16 * mm
RM = 16 * mm
TM = 22 * mm
BM = 22 * mm
UW = PW - LM - RM                          # 可用宽度

# 对比度（WCAG，白字压深底硬下限 AAA ≥ 7.0）
#   白字压 PRIMARY       8.16 : 1   AAA
#   PRIMARY 压 #edf2f7   7.25 : 1   AAA（KV 标签字）
#   分界强度 177.4 / 255（表头与浅行灰度差，≥170 达标）

# =============================================================================
# 6. 样式（统一在此定义，禁止在各 report 脚本里重复造）
# =============================================================================
F = setup_font()

h1 = ParagraphStyle('h1', fontName=F, fontSize=16, leading=22, textColor=PRIMARY,
                    spaceBefore=14, spaceAfter=8)
h2 = ParagraphStyle('h2', fontName=F, fontSize=13, leading=18, textColor=PRIMARY,
                    spaceBefore=10, spaceAfter=5)
h3 = ParagraphStyle('h3', fontName=F, fontSize=11, leading=15, textColor=PRIMARY,
                    spaceBefore=8, spaceAfter=3)
# keepWithNext=1：标题不与下文脱节（优先于 KeepTogether）
h1k = ParagraphStyle('h1k', parent=h1, keepWithNext=1)
h2k = ParagraphStyle('h2k', parent=h2, keepWithNext=1)
h3k = ParagraphStyle('h3k', parent=h3, keepWithNext=1)

bd = ParagraphStyle('bd', fontName=F, fontSize=10, leading=15, textColor=colors.black, spaceAfter=3)
ct = ParagraphStyle('ct', fontName=F, fontSize=10, leading=15, textColor=colors.black,
                    leftIndent=8, rightIndent=8, spaceBefore=4, spaceAfter=4,
                    backColor=colors.HexColor('#fff5f5'), borderPadding=6)
ch = ParagraphStyle('ch', fontName=F, fontSize=9.5, leading=13, textColor=PRIMARY)
cs = ParagraphStyle('cs', fontName=F, fontSize=9.5, leading=13, textColor=colors.black)
cl = ParagraphStyle('cl', fontName=F, fontSize=9.5, leading=13, textColor=colors.white)
dc = ParagraphStyle('dc', fontName=F, fontSize=8.5, leading=12, textColor=TEXT_MUTED,
                    spaceBefore=8, spaceAfter=0)
dsh = ParagraphStyle('dsh', fontName=F, fontSize=9, leading=13, textColor=TEXT_MUTED,
                     spaceAfter=2, keepWithNext=1)

# ⚠️ ParagraphStyle 的字色关键字必须是 textColor；写 color= 会静默失效（规范 4）。


def h1t(text):
    """一级章标题：一、执行摘要"""
    return Paragraph(inline_safe(text), h1k)


def h2t(text):
    """二级节标题：3.1 分档薪资带宽"""
    return Paragraph(inline_safe(text), h2k)


def h3t(text):
    return Paragraph(inline_safe(text), h3k)


# =============================================================================
# 7. 表格：T() 数据表（深底表头） / KV() 键值表（浅底标签列）
# =============================================================================
def T(rows, cw=None, header_bg=PRIMARY, hdr_color=HDR_TEXT, keep=True):
    """数据表：首行是真列名。深底表头 = 页面锚点，一页最多一处，不滥用。"""
    if not rows:
        return None
    n = len(rows[0])
    cw = cw or [UW / n] * n
    td = []
    for i, row in enumerate(rows):
        nr = []
        for cell in row:
            t = fix_currency(str(cell).replace('\n', '<br/>'))
            nr.append(Paragraph(f'<b>{t}</b>' if i == 0 else t, cl if i == 0 else cs))
        td.append(nr)
    t = Table(td, colWidths=cw, repeatRows=1)
    t.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), F),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('FONTSIZE', (0, 0), (-1, 0), 9.5),        # 表头与数据拉开半级，才有标题感
        ('BACKGROUND', (0, 0), (-1, 0), header_bg),
        ('TEXTCOLOR', (0, 0), (-1, 0), hdr_color),
        ('ALIGN', (0, 0), (-1, 0), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('GRID', (0, 0), (-1, -1), 0.4, BORDER),
        ('BOX', (0, 0), (-1, -1), 0.6, PRIMARY),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, ALT_BG]),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, 0), 5.5),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 5.5),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
    ]))
    return KeepTogether(t) if keep else t


def KV(rows, cw=None, label_bg=LIGHT_BG, keep=False):
    """键值表（标签—值 结构，无「列名」语义）：不给深色表头。

    用于封面元信息、国家块「驻地基准/薪资带宽」、数据来源等场景。
    那些地方若硬塞一个「维度|内容」伪表头，零信息量还白占一行深色块。
    """
    if not rows:
        return None
    n = len(rows[0])
    cw = cw or [UW / n] * n
    kvl = ParagraphStyle('kvl', fontName=F, fontSize=9, leading=13, textColor=PRIMARY)
    td = []
    for row in rows:
        nr = []
        for j, cell in enumerate(row):
            t = fix_currency(str(cell).replace('\n', '<br/>'))
            nr.append(Paragraph(f'<b>{t}</b>' if j == 0 else t, kvl if j == 0 else cs))
        td.append(nr)
    t = Table(td, colWidths=cw)
    t.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), F),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BACKGROUND', (0, 0), (0, -1), label_bg),
        ('TEXTCOLOR', (0, 0), (0, -1), PRIMARY),
        ('BACKGROUND', (1, 0), (-1, -1), colors.white),
        ('TEXTCOLOR', (1, 0), (-1, -1), colors.black),
        ('GRID', (0, 0), (-1, -1), 0.4, BORDER),
        ('BOX', (0, 0), (-1, -1), 0.6, BORDER),
        ('TOPPADDING', (0, 0), (-1, -1), 4.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4.5),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
    ]))
    return KeepTogether(t) if keep else t


def rates_table(curs, title='汇率速查'):
    """汇率速查表：按传入币种 + USD 生成，数值保留有效精度（禁取整）。"""
    rows = [['货币', '换算基线<br/>（本币）', '≈人民币（¥）', '≈美元（$）']]
    seen = []
    for c in list(curs) + ['USD']:
        if c not in seen:
            seen.append(c)
    for cur in seen:
        base = 1
        while base * RATES[cur][0] < 1:      # 放大到折算值 ≥ 1，避免客户手算失真
            base *= 10
        label = '1' if base == 1 else (f'{base // 10000} 万' if base >= 10000 else f'{base:,}')
        rows.append([cur, label, Cx(base, cur), Ux(base, cur)])
    return [Paragraph(f'<b>{inline_safe(title)}</b>（{inline_safe(RATE_BASIS)}）', h3k),
            T(rows, cw=[UW * 0.16, UW * 0.20, UW * 0.32, UW * 0.32], keep=False)]


def callout(text):
    return Paragraph(fix_currency(text), ct)


# =============================================================================
# 8. 卡片网格（撑满短章节）
# =============================================================================
def card_grid(items, cols=2, vgap=8, hgap=10, card_h=None):
    """items=[{'tag','icon','title','body':[...],'foot'}, ...] 自动按 cols 排网格。"""
    import re as _re
    rows = []
    n = len(items)
    rows_n = (n + cols - 1) // cols
    for r in range(rows_n):
        row = []
        for c in range(cols):
            i = r * cols + c
            if i >= n:
                row.append(Paragraph('', bd))
                continue
            it = items[i]
            cell = []
            if it.get('tag'):
                tag_st = ParagraphStyle('cgt', fontName=F, fontSize=8, leading=10,
                                        textColor=colors.HexColor('#5a6b85'), spaceAfter=2)
                cell.append(Paragraph(f"<b>{it['tag']}</b>", tag_st))
            icon = it.get('icon', '') or ''
            # SimHei 无彩色 emoji 字形 → 只保留编号/几何符号，emoji 一律剥掉
            icon = _re.sub(r'[\U0001F000-\U0001FFFF\U00002600-\U000027FF]', '', icon).strip()
            title_st = ParagraphStyle('cgti', fontName=F, fontSize=14, leading=18,
                                      textColor=PRIMARY, spaceAfter=4)
            cell.append(Paragraph(f"<b>{icon} {it.get('title', '')}</b>" if icon
                                  else f"<b>{it.get('title', '')}</b>", title_st))
            for line in (it.get('body') or []):
                body_st = ParagraphStyle('cgb', fontName=F, fontSize=9.5, leading=14,
                                         textColor=colors.black, spaceAfter=2)
                cell.append(Paragraph(inline_safe(line), body_st))
            if it.get('foot'):
                foot_st = ParagraphStyle('cgf', fontName=F, fontSize=8, leading=11,
                                         textColor=ACCENT, spaceBefore=4)
                cell.append(Paragraph(f"<b>{inline_safe(it['foot'])}</b>", foot_st))
            row.append(cell)
        rows.append(row)
    cw = UW / cols - hgap * (cols - 1) / cols
    t = Table(rows, colWidths=[cw] * cols, rowHeights=card_h)
    t.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#fbfcfe')),
        ('BOX', (0, 0), (-1, -1), 0.6, PRIMARY),
        ('INNERGRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#d6dbe5')),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    return t


# =============================================================================
# 9. 窄列货币版式（多列总览表用，避免长数字断行）
# =============================================================================
def Mrw(lo, hi, cur):
    """本币 / ≈¥ / ≈$ 各占一行。"""
    return f"{Lr(lo, hi, cur)}<br/>≈{Cr(lo, hi, cur)}<br/>≈{Ur(lo, hi, cur)}"


def CU2(lo, hi, cur):
    """¥ 与 $ 分行（本币已单列）。"""
    return f"{Cr(lo, hi, cur)}<br/>{Ur(lo, hi, cur)}"


def annual_wan(olo, ohi, cur, ec=None):
    """年成本（≈¥ 万元）。ec 传入雇主成本字典时按「雇主年成本」计
    （月度总包中值 ×（12 + 法定奖金月数）×（1 + 雇主附加率））；
    不传则退化为 12 个月税前口径。"""
    mid = (olo + ohi) / 2
    if ec:
        k = (12 + ec.get('bonus', 0)) * (1 + ec.get('rate', 0) / 100)
        return f"≈¥{mid * k * RATES[cur][0] / 10000:.1f} 万"
    return f"≈¥{mid * 12 * RATES[cur][0] / 10000:.1f} 万"


def employer_stats(ec, olo, ohi, cur, bonus=None):
    """按雇主口径测算，返回 (雇主年成本, 税前年包, 估算净得)，单位人民币万元。

    ec 结构：{'rate': 雇主附加率%, 'bonus': 法定奖金月数, 'tax_lo': 个税下限%, 'tax_hi': 个税上限%}
    rate 必须覆盖「社保雇主部分 + 离职金年计提」，且按**外籍雇员**口径；
    有缴纳上限的项目（泰国 SSO、马来 SOCSO、菲律宾 SSS/PhilHealth、印尼 Kesehatan）
    应先按岗位月薪量级折算为实际比率，不能直接填名义费率。
    """
    b = ec.get('bonus', 0) if bonus is None else bonus
    mid = (olo + ohi) / 2
    gross = mid * (12 + b) * RATES[cur][0] / 10000
    total = gross * (1 + ec.get('rate', 0) / 100)
    net = gross * (1 - (ec.get('tax_lo', 0) + ec.get('tax_hi', 0)) / 2 / 100)
    return total, gross, net


def employer_table(countries, ec_map, cw=None):
    """雇主成本与到手测算表。

    countries：[(name, cur, blo, bhi, olo, ohi, ...), ...]（与总览表同源数据）
    ec_map   ：{国家名: 雇主成本字典}，键须与 countries 的 name 完全一致，否则 KeyError。
    列：驻地 / 雇主附加率 / 法定奖金 / 雇主年成本 / 估算个税 / 估算净得。
    """
    rows = [['驻地', '雇主<br/>附加率', '法定<br/>奖金', '雇主年成本<br/>（≈¥ 万元）',
             '估算个税<br/>有效税率', '估算净得<br/>（≈¥ 万/年）']]
    for r in countries:
        name, cur, olo, ohi = r[0], r[1], r[4], r[5]
        ec = ec_map[name]
        total, _g, net = employer_stats(ec, olo, ohi, cur)
        rows.append([name.split('（')[0],
                     f"{ec.get('rate', 0):.1f}%",
                     (f"{ec['bonus']} 个月" if ec.get('bonus') else '—'),
                     f'{total:.1f}',
                     ('免税' if ec.get('tax_hi', 0) == 0
                      else f"{ec.get('tax_lo', 0)}–{ec.get('tax_hi', 0)}%"),
                     f'{net:.1f}'])
    return T(rows, cw=cw or [UW * 0.14, UW * 0.12, UW * 0.11, UW * 0.19, UW * 0.21, UW * 0.23],
             keep=False)


# =============================================================================
# 10. 封面 / 页眉页脚 / 水印
# =============================================================================
def cover(story, brand_big, brand_cn, brand_en, title, subtitle, meta,
          meta_w=0.30, rule_w=0.40):
    """封面。

    brand_big : 品牌大字（如 'COWAVE'）
    brand_cn  : 品牌中文名（如 '控维通信'）
    brand_en  : 品牌英文/全称（可留空字符串）
    title     : 报告主标题
    subtitle  : 副标题——**只写中性信息**（地区/岗位），不得出现「客户版」等交付侧标注
    meta      : [[标签, 值], ...] 键值表内容；不放「密级/客户版」这类内部标注行
    """
    story.append(Spacer(1, 40))
    story.append(Paragraph(brand_big, ParagraphStyle(
        'lg', fontName=F, fontSize=40, leading=48, textColor=PRIMARY,
        alignment=TA_CENTER, spaceAfter=4)))
    story.append(Paragraph(brand_cn, ParagraphStyle(
        'st', fontName=F, fontSize=14, leading=20, textColor=TEXT_MUTED,
        alignment=TA_CENTER, spaceAfter=2)))
    if brand_en:
        story.append(Paragraph(brand_en, ParagraphStyle(
            'st2', fontName=F, fontSize=9, leading=14, textColor=TEXT_MUTED,
            alignment=TA_CENTER, spaceAfter=24)))
    hr = Table([['']], colWidths=[UW * rule_w], rowHeights=[2])
    hr.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), ACCENT)]))
    hr.hAlign = 'CENTER'
    story.append(hr)
    story.append(Spacer(1, 22))
    story.append(Paragraph(inline_safe(title), ParagraphStyle(
        'tl', fontName=F, fontSize=19, leading=26, textColor=PRIMARY,
        alignment=TA_CENTER, spaceAfter=6)))
    story.append(Paragraph(inline_safe(subtitle), ParagraphStyle(
        'tl2', fontName=F, fontSize=11, leading=16, textColor=TEXT_MUTED,
        alignment=TA_CENTER, spaceAfter=24)))
    story.append(KV(meta, cw=[UW * meta_w, UW * (1 - meta_w)]))
    story.append(PageBreak())


def page_deco_factory(header_text, show_page_no=True, skip_first=True):
    """每页页眉（居中细字）+ 分隔线 + 页码。

    ⚠️ header_text 是客户可见面：只写「客户名 · 岗位 | 地区 · 日期」，不要带「客户版」。
    skip_first=True 时封面（第 1 页）不排页眉与页码——封面是设计版面，
    压页眉与「第 1 页」属排版瑕疵（QC 会按「页码 2..N」形态校验，属正常）。
    """
    def deco(canvas, doc):
        if skip_first and doc.page == 1:
            return
        canvas.saveState()
        canvas.setFont(F, 8)
        canvas.setFillColor(colors.HexColor('#8899aa'))
        canvas.drawCentredString(PW / 2, PH - 12 * mm, header_text)
        canvas.setStrokeColor(colors.HexColor('#e2e8f0'))
        canvas.setLineWidth(0.3)
        canvas.line(LM, PH - 15 * mm, PW - RM, PH - 15 * mm)
        if show_page_no:
            canvas.setFont(F, 8)
            canvas.drawCentredString(PW / 2, 10 * mm, f'第 {doc.page} 页')
        canvas.restoreState()
    return deco


def make_watermark(src, dst, text, title=None):
    """叠加斜向水印，并回写 PDF 元数据标题。

    ⚠️ PyPDF2 逐页重建会丢掉源 PDF 的 Info 字典 → 阅读器标签页退化成**文件名**。
    客户在浏览器/阅读器里就会看到 `xxx_客户版.pdf`，等于把交付侧标注送回去。
    因此 title 必传（正式报告名，不含「客户版」），用 PyMuPDF 回写
    （PyPDF2 3.x 的 add_metadata() 对键格式挑剔，会抛 NameObject 警告且写入无效）。
    """
    from PyPDF2 import PdfReader, PdfWriter
    from reportlab.pdfgen import canvas
    import io

    reader = PdfReader(src)
    writer = PdfWriter()
    for i in range(len(reader.pages)):
        packet = io.BytesIO()
        c = canvas.Canvas(packet, pagesize=A4)
        c.setFillAlpha(0.12)
        c.setFont(F, 32)
        c.setFillColorRGB(0.78, 0.78, 0.78)
        c.saveState(); c.translate(PW / 2, PH / 2); c.rotate(40)
        c.drawCentredString(0, 0, text); c.restoreState()
        c.saveState(); c.setFont(F, 20); c.setFillColorRGB(0.8, 0.8, 0.8)
        c.translate(PW * 0.2, PH * 0.83); c.rotate(-35)
        c.drawCentredString(0, 0, text); c.restoreState()
        c.saveState(); c.setFont(F, 20); c.setFillColorRGB(0.8, 0.8, 0.8)
        c.translate(PW * 0.8, PH * 0.17); c.rotate(-35)
        c.drawCentredString(0, 0, text); c.restoreState()
        c.save()
        packet.seek(0)
        wm = PdfReader(packet).pages[0]
        reader.pages[i].merge_page(wm)
        writer.add_page(reader.pages[i])
    with open(dst, 'wb') as f:
        writer.write(f)

    if title:
        tmp = dst + '.md.pdf'
        try:
            import fitz
            d = fitz.open(dst)
            md = d.metadata or {}
            md.update({'title': title, 'author': '用友薪福社',
                       'creator': '用友薪福社', 'producer': '用友薪福社'})
            d.set_metadata(md)
            d.save(tmp)
            d.close()
            os.replace(tmp, dst)
        except Exception as e:
            # 回写失败必须显式暴露：门禁 7 要求元数据标题非空，
            # 否则阅读器会退回显示文件名（含 `_客户版`），QC 会打回。
            print(f'  [ERROR] 元数据标题回写失败 → 交付件会被 QC 判 FAIL（阅读器将显示文件名）。原因: {e}')
            print('          请检查目标目录可写；标题需为:', title)
            if os.path.exists(tmp):      # 不留中间产物（工作区残留 = 误发风险源）
                try:
                    os.remove(tmp)
                except Exception:
                    pass
    return dst


# =============================================================================
# 11. 交付：一页式构建（临时基础版 → 叠水印 → 删临时件）
# =============================================================================
def new_doc(path, title=None):
    return SimpleDocTemplate(path, pagesize=A4, leftMargin=LM, rightMargin=RM,
                             topMargin=TM, bottomMargin=BM, title=title)


def build_and_deliver(story, out_path, header_text, wm_text, pdf_title,
                      tmp_path=None, show_page_no=True):
    """构建 → 叠水印 → 写元数据 → 删除临时基础版。

    工作区不得留无水印残留（误发风险源）。交付件本身即含水印，
    文件名不带「水印版」（2026-09-14 规范）。
    """
    out_dir = os.path.dirname(os.path.abspath(out_path))
    if out_dir and not os.path.isdir(out_dir):
        raise FileNotFoundError(f'输出目录不存在：{out_dir}（请先创建或改 WORK 常量）')

    tmp_path = tmp_path or ('/tmp/_salary_base_%d.pdf' % os.getpid())
    doc = new_doc(tmp_path)
    deco = page_deco_factory(header_text, show_page_no)
    doc.build(story, onFirstPage=deco, onLaterPages=deco)
    make_watermark(tmp_path, out_path, wm_text, title=pdf_title)
    if os.path.exists(tmp_path):
        os.remove(tmp_path)
    return out_path
