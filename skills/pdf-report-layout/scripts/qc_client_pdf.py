#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""客户版 PDF 交付前自检（一把梭）。

把散落在 pdf-report-layout / client-salary-band-report 两处的交付前检查
固化成一条命令，供人工或 A8 质量校验官（yoyo-qc-auditor）调用。

检查项
  1. 缺字形      字体能力检测（根因）：PDF 里实际用 SimHei 渲染、但 SimHei 无该字形的字符
  2. 替换符      U+FFFD / □（文本层真的写入了这些字符时）
  3. 客户版禁词  与客户确认|建议客户|…|对客话术…（内部视角措辞）
  4. 交付侧标注  客户版|客户交付版|内部版|交付侧|底稿（客户可见面泄漏）
  5. 水印覆盖    每页须出现水印关键词（默认「用友薪福社」）
  6. 元数据标题  非空，且不含交付侧标注（空 → 阅读器显示含「客户版」的文件名）
  7. 页码连续    第 1..N 页齐全
  8. 空白页      文字 <30 字且图形 <3 个 → 疑似空白
  9. 串区关键词  --must / --forbid 指定，防「东南亚版里混进以色列」
 10. 主色填充    --color 指定时，校验深色填充主色（默认不查）

⚠️ 字形检测为什么不用黑名单（2026-09-14 实测纠偏）
   历史规则写「几何符号 ▸•★、圆圈数字 ①②③ 均需清零」——**部分是误报**。
   用 `fitz.Font(fontfile=SimHei).has_glyph()` 实测：①②③(346/347)、→(302)、★(541)、
   ≥(336)、×(104)、·(103)、—(258) **都有字形，能正常渲染**；
   真正无字形的是 `•(0) ▸(0) ¥(0)` 与谚文/emoji（`가(0)` `😀(0)`）。
   所以判据必须是「字体有没有这个字形」，黑名单既误伤又必然漏掉未来的新字符。
   （`¥` 无字形正是 `fix_currency()` 必须把它包进 `<font face="Helvetica">` 的根因。）

用法
  python qc_client_pdf.py *_客户版.pdf
  python qc_client_pdf.py --must "沙特,以色列" --forbid "印度尼西亚,泰国" 中东版.pdf
  python qc_client_pdf.py --per-file "中东.pdf=沙特,以色列;东南亚.pdf=印度尼西亚,泰国;!以色列" *.pdf
  python qc_client_pdf.py --font ../fonts/SimHei.ttf --color "#1f4f8f" --json qc.json 报告.pdf

  --per-file 语法：`文件=词1,词2,!禁词1,!禁词2`（普通词=必需，!前缀=禁止）

退出码：0 = 全通过；1 = 有 FAIL（便于自动化判定）。
"""
import argparse
import collections
import glob
import json
import os
import re
import sys

try:
    import fitz  # PyMuPDF
except ImportError:
    sys.exit('缺少 PyMuPDF：请用 WorkBuddy 托管 venv 或 pip install PyMuPDF')

# ---------------------------------------------------------------- 规则定义
BAN = re.compile(r'与客户确认|建议客户|客户目标|客户反馈|客户诉求|客户原话|口径对齐|'
                 r'对客话术|对客沟通|客户预算|确认预算|招聘执行建议|我方锚点|谈判杠杆|底稿|交付侧')
SIDE = ['客户版', '客户交付版', '内部版', '交付侧', '底稿']

REPLACEMENT = re.compile(r'[\ufffd]')     # U+FFFD 替换符
WHITEBOX = re.compile(r'\u25a1')          # □ 白方块（真写进文本层才检出）
PAGE_NO = re.compile(r'第\s*(\d+)\s*页')

# 无字形字符里允许出现的（走 Helvetica 的符号由 fix_currency 包裹，不算问题）
SKIP_CHARS = set(' \t\r\n\u00a0')


def rgb2hex(c):
    return '#%02x%02x%02x' % tuple(round(v * 255) for v in c[:3])


def dominant_dark_fill(doc):
    """统计深色填充色（表头/封面块），返回 [(hex, 次数)] 降序。"""
    cnt = collections.Counter()
    for p in doc:
        for dr in p.get_drawings():
            f = dr.get('fill')
            if not f:
                continue
            h = rgb2hex(f)
            r, g, b = int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)
            if r < 170 and b >= r:      # 偏蓝的深色 = 品牌色系
                cnt[h] += 1
    return cnt.most_common()


class GlyphProbe:
    """按字体名判断字符是否有字形（根因检测，替代黑名单）。"""

    def __init__(self, font_path=None, target='simhei'):
        self.font_path = font_path
        self.target = target.lower()
        self._fonts = {}
        self.available = False
        if font_path and os.path.exists(font_path):
            try:
                self._fonts[self.target] = fitz.Font(fontfile=font_path)
                self.available = True
            except Exception as e:
                print(f'[warn] 字体加载失败（跳过字形检测）：{e}')

    def has(self, fontname, ch):
        """True = 该字体能渲染该字符（或无法判定时按通过处理，避免误报）。"""
        if not self.available or ch in SKIP_CHARS:
            return True
        if self.target not in (fontname or '').lower():
            return True                      # 只查目标字体（SimHei），Helvetica 等放行
        try:
            return self._fonts[self.target].has_glyph(ord(ch)) != 0
        except Exception:
            return True

    def scan(self, doc):
        """返回 {字体名: {无字形字符: 首次出现页}}"""
        bad = collections.defaultdict(dict)
        for pno, page in enumerate(doc, 1):
            for blk in page.get_text('rawdict').get('blocks', []):
                for line in blk.get('lines', []):
                    for span in line.get('spans', []):
                        fname = span.get('font', '')
                        for c in {c['c'] for c in span.get('chars', [])}:
                            if not self.has(fname, c):
                                bad[fname].setdefault(c, pno)
        return bad


def per_file_map(spec):
    """解析 'a.pdf=k1,!k2;b.pdf=k3' → {路径: [词,...]}（!前缀保留给调用方区分）"""
    out = {}
    if not spec:
        return out
    for chunk in spec.split(';'):
        chunk = chunk.strip()
        if not chunk or '=' not in chunk:
            continue
        fn, words = chunk.split('=', 1)
        out[fn.strip()] = [w.strip() for w in words.split(',') if w.strip()]
    return out


def check_one(path, args, must_map, forbid_map, probe):
    res = {'file': path, 'fails': [], 'warns': [], 'info': {}}
    try:
        doc = fitz.open(path)
    except Exception as e:
        res['fails'].append(f'无法打开：{e}')
        return res

    pages = [p.get_text() for p in doc]
    txt = '\n'.join(pages)
    n = len(doc)
    res['info']['pages'] = n

    # 1 字形能力检测（根因）
    if probe.available:
        bad = probe.scan(doc)
        if bad:
            desc = []
            for fname, chars in bad.items():
                pairs = ' '.join(f'{c}(p{p})' for c, p in list(chars.items())[:8])
                desc.append(f'{fname}: {pairs}')
            res['fails'].append(f'字体无字形 {sum(len(v) for v in bad.values())} 种 → ' + '；'.join(desc))

    # 2 替换符 / 白方块
    for name, pat in (('替换符 U+FFFD', REPLACEMENT), ('白方块 □', WHITEBOX)):
        hit = pat.findall(txt)
        if hit:
            res['fails'].append(f'{name} {len(hit)} 处')

    # 3 客户版禁词
    ban = BAN.findall(txt)
    if ban:
        res['fails'].append(f'客户版禁词 {len(ban)} 处：{sorted(set(ban))[:6]}')

    # 4 交付侧标注
    side = {k: txt.count(k) for k in SIDE if k in txt}
    if side:
        res['fails'].append(f'交付侧标注泄漏：{side}')

    # 5 水印覆盖
    wm_pages = sum(1 for t in pages if args.wm in t)
    res['info']['watermark'] = f'{wm_pages}/{n}'
    if wm_pages < n:
        res['fails'].append(f'水印覆盖不全 {wm_pages}/{n} 页（缺页无「{args.wm}」）')

    # 6 元数据标题
    title = (doc.metadata or {}).get('title') or ''
    res['info']['title'] = title
    if not title:
        res['warns'].append('元数据标题为空 → 阅读器标签页会显示文件名（含「_客户版」）')
    elif any(k in title for k in SIDE):
        res['fails'].append(f'元数据标题含交付侧标注：{title!r}')

    # 7 页码连续
    nums = [int(x) for t in pages for x in PAGE_NO.findall(t)]
    if nums:
        uniq = sorted(set(nums))
        res['info']['page_numbers'] = f'{uniq[0]}..{uniq[-1]}'
        # 封面按设计不排页码/页眉 → 允许 {1..N}（全页）与 {2..N}（封面无码）两种形态
        if uniq not in (list(range(1, n + 1)), list(range(2, n + 1))):
            res['warns'].append(f'页码与页数不一致：检出 {uniq[:3]}…{uniq[-3:]}，实际 {n} 页')
    else:
        res['warns'].append('未检出「第 N 页」页码')

    # 8 空白页
    blanks = [i + 1 for i, (t, p) in enumerate(zip(pages, doc))
              if len(t.strip()) < 30 and len(p.get_drawings()) < 3]
    if blanks:
        res['fails'].append(f'疑似空白页：{blanks}')

    # 9 串区关键词
    must = must_map.get(path, args.must)
    forbid = forbid_map.get(path, args.forbid)
    if must:
        lack = [w for w in must if w not in txt]
        if lack:
            res['fails'].append(f'缺失必需关键词：{lack}')
    if forbid:
        leak = [w for w in forbid if w in txt]
        if leak:
            res['fails'].append(f'串区泄漏：{leak}')

    # 10 主色填充
    if args.color:
        fills = dominant_dark_fill(doc)
        res['info']['top_fill'] = fills[:3]
        if fills and fills[0][0].lower() != args.color.lower():
            res['warns'].append(f'主色填充实测 {fills[0][0]} ≠ 期望 {args.color}（历史报告可忽略）')

    doc.close()
    return res


def find_font(explicit, cwd):
    """定位 SimHei 字体文件（字形能力检测的基准，找不到则该项门禁会被跳过）。

    优先级：--font 显式路径 → $SALARY_REPORT_FONT → 当前目录 fonts/ →
    cwd → skill 内 assets/fonts → ~/WorkBuddy/*/fonts/（历史工作区）→ 系统回退。
    ⚠️ 缺字体时不能静默放行：字形是本 QC 的核心判据。
    """
    import glob as _glob
    cands = []
    if explicit:
        cands.append(explicit)
    env = os.environ.get('SALARY_REPORT_FONT')
    if env:
        cands.append(env)
    here = os.path.dirname(os.path.abspath(__file__))
    cands += [os.path.join(cwd, 'fonts', 'SimHei.ttf'),
              os.path.join(cwd, 'SimHei.ttf'),
              os.path.join(here, '..', 'fonts', 'SimHei.ttf'),
              os.path.join(here, '..', 'assets', 'SimHei.ttf')]
    # 历史工作区扫描（报告脚本常把字体放在 <workspace>/fonts/ 下）
    cands += sorted(_glob.glob(os.path.expanduser('~/WorkBuddy/*/fonts/SimHei.ttf')), reverse=True)
    cands += ['/System/Library/Fonts/Supplemental/Arial Unicode.ttf',
              '/Library/Fonts/Arial Unicode.ttf']
    for c in cands:
        if c and os.path.exists(c):
            return os.path.abspath(c)
    return None


def main():
    ap = argparse.ArgumentParser(description='客户版 PDF 交付前自检')
    ap.add_argument('files', nargs='*', help='PDF 路径（支持 *.pdf 通配）')
    ap.add_argument('--wm', default='用友薪福社', help='水印关键词（默认「用友薪福社」）')
    ap.add_argument('--must', default='', help='必需关键词，逗号分隔（全局）')
    ap.add_argument('--forbid', default='', help='禁止关键词，逗号分隔（全局）')
    ap.add_argument('--per-file', default='', help='"a.pdf=k1,!k2;b.pdf=k3" 按文件覆盖')
    ap.add_argument('--color', default='', help='期望主色，如 #1f4f8f（不传则不查）')
    ap.add_argument('--font', default='', help='SimHei.ttf 路径（默认自动探测）')
    ap.add_argument('--json', default='', help='把结果另存为 JSON')
    args = ap.parse_args()

    files = []
    for f in args.files:
        files.extend(sorted(glob.glob(f)) or [f])
    if not files:
        ap.error('至少要给一个 PDF')

    args.must = [w.strip() for w in args.must.split(',') if w.strip()]
    args.forbid = [w.strip() for w in args.forbid.split(',') if w.strip()]

    # --per-file 语义：普通词 = 必需，`!` 前缀 = 禁止
    must_map, forbid_map = {}, {}
    for k, words in per_file_map(args.per_file).items():
        must_map[k] = [w for w in words if not w.startswith('!')]
        forbid_map[k] = [w[1:] for w in words if w.startswith('!')]

    font = find_font(args.font, os.getcwd())
    probe = GlyphProbe(font)
    if not probe.available:
        print('[warn] 未找到 SimHei.ttf，本次跳过字形能力检测（--font 可显式指定）')

    results = [check_one(f, args, must_map, forbid_map, probe) for f in files]

    total_fail = sum(len(r['fails']) for r in results)
    print('=' * 78)
    print(f'客户版交付前自检 —— {len(files)} 份文件，{total_fail} 项 FAIL'
          + (f'（字形基准：{os.path.basename(font)}）' if probe.available else ''))
    print('=' * 78)
    for r in results:
        tag = '✅ 通过' if not r['fails'] else f"❌ {len(r['fails'])} 项"
        print(f"\n{tag}  {r['file']}")
        info = r['info']
        bits = [f"{info.get('pages', '?')} 页"]
        if 'watermark' in info:
            bits.append(f"水印 {info['watermark']}")
        if info.get('page_numbers'):
            bits.append(f"页码 {info['page_numbers']}")
        if 'title' in info:
            bits.append(f"标题 {info['title']!r}" if info['title'] else '标题 (空)')
        print('     ' + ' | '.join(bits))
        if info.get('top_fill'):
            print(f"     主色填充  {info['top_fill']}")
        for f in r['fails']:
            print(f'     ❌ {f}')
        for w in r['warns']:
            print(f'     ⚠️  {w}')

    if args.json:
        with open(args.json, 'w', encoding='utf-8') as fh:
            json.dump(results, fh, ensure_ascii=False, indent=2)
        print(f'\n结果已写入 {args.json}')

    print()
    print('=' * 78)
    print('✅ 全部通过' if total_fail == 0 else f'❌ 存在 {total_fail} 项 FAIL，需返工')
    return 1 if total_fail else 0


if __name__ == '__main__':
    sys.exit(main())
