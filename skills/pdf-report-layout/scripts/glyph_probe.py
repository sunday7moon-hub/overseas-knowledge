#!/usr/bin/env python3
"""字形能力探针 —— 判据是「字体有没有这个字形」，不是「在不在黑名单里」。

背景：SimHei + Helvetica 混排的中文 PDF 里，字符分三类：
  ① SimHei 原生可用          → 直接写
  ② SimHei 无、Helvetica 有   → 必须包 <font face="Helvetica">…</font>
  ③ 两边都没有（会出空框）    → 禁用，改写 ISO 代码/中文

⚠️ 缺字形在 PDF 文本层会变成 U+0000（不是 □），所以**事后靠文本搜符号是搜不到的**，
   只有渲染后扫 U+0000 或提前按字形能力探测才可靠。本脚本做后者。

用法
----
  # 1) 查若干字符属于哪一类
  python glyph_probe.py --chars "−•ãÇ★→₫é"

  # 2) 打印全量能力表（拉丁-1 / 通用标点 / 货币 / 数学 / 符号区）
  python glyph_probe.py --table

  # 3) 【巡检】扫源文件，列出第③类（硬禁用）候选
  #    注意：这是**巡检**不是门禁——源码的注释/文档串里的 ⚠ ⛔ 不会被渲染，
  #    会误报。真正的门禁是报告脚本里的 preflight_glyphs(story)（生成前扫
  #    「将被渲染的字符串」，零误报）。此处给 --strict 才会以退出码 1 阻断。
  python glyph_probe.py --scan 我的报告.py
  python glyph_probe.py --scan src/ --ext .py .md --strict   # 想当门禁用时加 --strict

字体定位优先序：--simhei 参数 > 环境变量 SALARY_REPORT_FONT > 常见路径
"""
from __future__ import annotations

import argparse
import os
import sys

try:
    import fitz  # PyMuPDF
except ImportError:
    sys.exit('需要 PyMuPDF：pip install pymupdf')

# 常见 SimHei 落点（按命中顺序）
_SIMHEI_CANDIDATES = [
    'fonts/SimHei.ttf',
    os.path.expanduser('~/.workbuddy/skills/pdf-report-layout/assets/SimHei.ttf'),
    os.path.expanduser('~/.workbuddy/skills/client-salary-band-report/assets/SimHei.ttf'),
    os.path.expanduser('~/.workbuddy/skills/pdf-report-layout/fonts/SimHei.ttf'),
    os.path.expanduser('~/.workbuddy/skills/client-salary-band-report/fonts/SimHei.ttf'),
    '/System/Library/Fonts/Supplemental/SimHei.ttf',
    '/Library/Fonts/SimHei.ttf',
]

# 探针覆盖范围：(起, 止, 名称)
_RANGES = [
    (0x00A0, 0x00FF, '拉丁-1 补充'),
    (0x0100, 0x017F, '拉丁扩展-A'),
    (0x2010, 0x205E, '通用标点'),
    (0x20A0, 0x20BF, '货币符号'),
    (0x2100, 0x214F, '类字母符号'),
    (0x2190, 0x21FF, '箭头'),
    (0x2200, 0x22FF, '数学运算符'),
    (0x2460, 0x24FF, '带圈字符'),
    (0x25A0, 0x25FF, '几何图形'),
    (0x2600, 0x27BF, '杂项符号 / emoji'),
]

C_SIMHEI, C_HELV, C_TOFU = 0, 1, 3


def resolve_simhei(explicit: str | None = None) -> str:
    if explicit:
        if not os.path.isfile(explicit):
            sys.exit(f'指定的 SimHei 不存在：{explicit}')
        return explicit
    env = os.environ.get('SALARY_REPORT_FONT')
    if env and os.path.isfile(env):
        return env
    for p in _SIMHEI_CANDIDATES:
        if os.path.isfile(p):
            return p
    sys.exit('找不到 SimHei.ttf —— 用 --simhei 指定，或设 SALARY_REPORT_FONT 环境变量')


def load(simhei_path: str):
    return fitz.Font(fontfile=simhei_path), fitz.Font(fontname='helv')


def classify(cp: int, sm, helv) -> int:
    if sm.has_glyph(cp):
        return C_SIMHEI
    if helv.has_glyph(cp):
        return C_HELV
    return C_TOFU


_LABEL = {C_SIMHEI: '① SimHei 原生（直接写）',
          C_HELV: '② 需包 Helvetica',
          C_TOFU: '③ 硬禁用（出空框）'}


def cmd_chars(args, sm, helv) -> int:
    bold = False
    for ch in args.chars:
        k = classify(ord(ch), sm, helv)
        flag = '  ⚠️' if k == C_TOFU else ''
        if k == C_TOFU:
            bold = True
        print(f'{ch}  U+{ord(ch):04X}  {_LABEL[k]}{flag}')
    return 1 if bold else 0


def cmd_table(args, sm, helv) -> int:
    total = {C_SIMHEI: 0, C_HELV: 0, C_TOFU: 0}
    buckets = {C_SIMHEI: [], C_HELV: [], C_TOFU: []}
    for lo, hi, name in _RANGES:
        cnt = {C_SIMHEI: 0, C_HELV: 0, C_TOFU: 0}
        for cp in range(lo, hi + 1):
            ch = chr(cp)
            if not ch.isprintable() and cp not in (0x00A0,):
                continue
            k = classify(cp, sm, helv)
            cnt[k] += 1
            total[k] += 1
            buckets[k].append(ch)
        print(f'{name:<16} ① {cnt[C_SIMHEI]:>4}   ② {cnt[C_HELV]:>4}   ③ {cnt[C_TOFU]:>4}')
    print(f'{"合计":<16} ① {total[C_SIMHEI]:>4}   ② {total[C_HELV]:>4}   ③ {total[C_TOFU]:>4}')
    for k in (C_HELV, C_TOFU):
        print(f'\n--- {_LABEL[k]} ---')
        print(''.join(buckets[k]))
    return 0


def iter_files(paths, exts):
    for p in paths:
        if os.path.isdir(p):
            for root, _, files in os.walk(p):
                for f in files:
                    if not exts or os.path.splitext(f)[1] in exts:
                        yield os.path.join(root, f)
        else:
            yield p


def cmd_scan(args, sm, helv) -> int:
    """巡检源文件：列出第③类字符（含注释/文档串，仅供参考）。--strict 时才阻断。"""
    hits, scanned = [], 0
    for path in iter_files(args.scan, set(args.ext or [])):
        try:
            with open(path, encoding='utf-8') as fh:
                text = fh.read()
        except (OSError, UnicodeDecodeError):
            continue
        scanned += 1
        bad = {}
        for i, ch in enumerate(text):
            if ch in bad:
                bad[ch] += 1
                continue
            if ord(ch) < 0x00A0 or ch.isalnum() and ord(ch) < 0x0250:
                continue
            if classify(ord(ch), sm, helv) == C_TOFU:
                bad[ch] = 1
        if bad:
            hits.append((path, bad))
    print(f'扫描 {scanned} 个文件（第③类「两边都没有字形」字符检测）\n')
    if not hits:
        print('✅ 未发现硬禁用字符')
        return 0
    for path, bad in hits:
        detail = ' '.join(f'{c}(U+{ord(c):04X})×{n}' for c, n in bad.items())
        print(f'⚠️  {path}\n     {detail}')
    print(f'\n共 {len(hits)} 个文件命中。注意：注释/文档串里的符号不会被渲染，属正常。')
    print('正式门禁请用报告脚本内的 preflight_glyphs(story)（生成前扫真实渲染内容）。')
    return 1 if args.strict else 0


def main() -> int:
    ap = argparse.ArgumentParser(description='SimHei + Helvetica 字形能力探针')
    ap.add_argument('--chars', help='要查的字符（直接粘字符串）')
    ap.add_argument('--table', action='store_true', help='打印全量能力表')
    ap.add_argument('--scan', nargs='+', help='【巡检】扫源文件/目录，列出第③类候选')
    ap.add_argument('--strict', action='store_true', help='--scan 时以退出码 1 阻断（当门禁用）')
    ap.add_argument('--ext', nargs='*', default=['.py', '.md', '.txt', '.json'],
                    help='--scan 目录时的扩展名过滤（默认 .py .md .txt .json）')
    ap.add_argument('--simhei', help='SimHei.ttf 路径（默认自动查找）')
    args = ap.parse_args()

    path = resolve_simhei(args.simhei)
    sm, helv = load(path)
    print(f'SimHei = {path}   |   Helvetica = reportlab 标准字（fitz fontname=helv）\n')

    if args.chars:
        return cmd_chars(args, sm, helv)
    if args.table:
        return cmd_table(args, sm, helv)
    if args.scan:
        return cmd_scan(args, sm, helv)
    ap.print_help()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
