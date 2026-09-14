#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""客户版带宽报告 · 内容维度自检（content_lint）

与技术门禁 qc_client_pdf.py 互补：
  qc_client_pdf.py  → 不出错（字形 / 禁词 / 水印 / 元数据 / 页码 / 串区 / 主色）
  content_lint.py   → 有用（内容缺口 / 冗余 / 篇幅失衡 / 跨版复制）

检查 5 类：
  1. 内容缺口红旗（A1-A7：雇主总成本 / 薪酬结构 / 个税净得 / 职级对标 / 有效期 / 参照系 / 溢价口径）
  2. 版本内重复句（同一句在同一份里出现 >=2 次）
  3. 跨版本逐字相同长句（套话可接受，结论类需差异化）
  4. 章级篇幅分布（识别信息密度失衡章）
  5. 高频套话短语（默认词表 + --watch 追加）

用法：
  python content_lint.py *.pdf
  python content_lint.py *.pdf --watch "比价,外籍常驻" --json --strict

退出码：默认 0（内容缺口是设计选择，非错误）；--strict 时有红旗返回 1。
"""
import argparse
import collections
import json
import os
import re
import sys


# ---------- 内容缺口探测（A1-A7）----------
# scope='doc' → 全文任一词出现即视为覆盖
# scope='per_country' → 逐国检查（按 2.x 小节切分），报出缺失国家
GAP_RULES = [
    ('A1 雇主总成本', '雇主总成本未汇总：社保/公积金散列在各国「驻地基准」行，客户需自行加总',
     ['雇主年成本', '雇主总成本', '雇主附加率', '总成本系数', '用工总成本'], 'doc', None),
    ('A2 薪酬结构', '缺固定/浮动拆分与津贴明细（住房津贴、年终奖等）',
     ['浮动', '住房津贴', '年终奖', '13 薪', 'THR'], 'doc', None),
    ('A3 个税净得', '未提示个税净得影响：GROSS 口径下客户易误解为到手金额',
     ['净得', '税后', '净收入'], 'doc',
     ['无个人所得税', '个人所得税 0%', '个税 0%']),   # 无个税国家（海湾六国）豁免
    ('A4 职级对标', '带宽未映射到客户内部职级/薪酬架构档位',
     ['职级', '薪级', '内部对标', '薪酬架构档'], 'doc', None),
    ('A5 有效期', '未标注数据有效期（带宽类惯例 3-6 个月）',
     ['有效期', '有效期限'], 'doc', None),
    ('A6 参照系密度', '该国缺市场参照项（平均月薪/中位数），或来源标注粒度与邻国不一致',
     ['平均月薪', '中位数', '工资中位'], 'per_country', None),
    ('A7 溢价口径', '未说明行业溢价是否已包含在带宽数字内',
     ['溢价', '上浮'], 'doc', None),
]

DEFAULT_WATCH = ['比价', '外籍常驻', '区域指挥', '等同净得', '无个人所得税',
                 '雇主担保', '成本为', '基准', '人才池', '配套设施']

CHAP = re.compile(r'[一二三四五六七八九十]、')
NOISE = re.compile(r'用友薪福社\s*[\d.]+|第\s*\d+\s*页')
SENT_SPLIT = re.compile(r'[。；\n]')


def load_pdf(path):
    import fitz
    d = fitz.open(path)
    pages = [p.get_text() for p in d]
    meta = d.metadata or {}
    n = len(d)
    d.close()
    text = NOISE.sub('', '\n'.join(pages))
    return text, pages, n, meta


def is_noise_sent(s):
    """过滤正常重复：页眉串、纯金额/数字、数字占比过高的行。"""
    if re.search(r'\d{4}\.\d{2}\.\d{2}', s) and ('·' in s or '|' in s):
        return True                                   # 每页页眉
    if re.match(r'^[A-Z]{2,4}\s*[\d,]+\s*[–\-—]\s*[\d,]+$', s):
        return True                                   # "SAR 38,000–52,000"
    if re.match(r'^[\d,\.\s–\-—≈¥$%×]+$', s):
        return True
    if s and sum(c.isdigit() for c in s) / len(s) > 0.4:
        return True
    return False


def sentences(text, min_len=14, drop_noise=False):
    out = [s.strip() for s in SENT_SPLIT.split(text) if len(s.strip()) >= min_len]
    return [s for s in out if not is_noise_sent(s)] if drop_noise else out


def country_sections(text):
    """按第二章的 2.x 小节切出各国段落（用于逐国覆盖检查）。
    必须锚定行首——纯 (?=2\\.\\d\\s) 会把正文金额「¥2.5 万」误判成小节起点，
    导致切出的「国家名」变成「万、万、万」。"""
    parts = re.split(r'(?m)(?=^2\.\d\s)', text)
    out = []
    for p in parts[1:]:
        body = re.sub(r'^2\.\d\s*', '', p)                       # 先去自身编号，避免 lookahead 在段首命中
        body = re.split(r'(?m)(?=^2\.\d\s)|(?=^三、)|(?=^地区小结)', body)[0]
        first = body.split('\n')[0].strip()
        name = first.split('｜')[0].strip()[:16]
        out.append((name or '（未识别）', body))
    return out


def sections(text):
    idx = [m.start() for m in CHAP.finditer(text)]
    if not idx:
        return []
    out = []
    for i, s in enumerate(idx):
        e = idx[i + 1] if i + 1 < len(idx) else len(text)
        head = text[s:s + 4]
        out.append((head, e - s))
    return out


def analyze(path, watch):
    text, pages, n, meta = load_pdf(path)
    name = os.path.basename(path)
    r = {'file': name, 'pages': n, 'title': meta.get('title'),
         'chars': len(text), 'gaps': [], 'dup_sents': [],
         'watch': {}, 'sections': [], 'cover_noise': {}}

    # 1) 内容缺口
    ctry = country_sections(text)
    for tag, desc, kws, scope, exempt in GAP_RULES:
        if scope == 'doc':
            if not any(k in text for k in kws):
                r['gaps'].append({'code': tag.split()[0], 'desc': desc, 'missing': None})
        else:
            if not ctry:
                if not any(k in text for k in kws):
                    r['gaps'].append({'code': tag.split()[0], 'desc': desc, 'missing': None})
                continue
            lacked = [head for head, body in ctry
                      if not any(k in body for k in kws)
                      and not (exempt and any(e in body for e in exempt))]
            if lacked:
                r['gaps'].append({'code': tag.split()[0], 'desc': desc,
                                  'missing': lacked, 'total': len(ctry)})

    # 2) 版本内重复句（过滤页眉/金额类正常重复）
    c = collections.Counter(sentences(text, drop_noise=True))
    r['dup_sents'] = [{'sent': s, 'times': k} for s, k in c.items() if k >= 2]

    # 3) 高频套话
    for w in watch:
        k = text.count(w)
        if k >= 2:
            r['watch'][w] = k

    # 4) 章级篇幅
    r['sections'] = [{'head': h, 'chars': c_} for h, c_ in sections(text)]

    # 5) 封面异常（页眉/页码不该出现在封面）
    if pages:
        p1 = pages[0]
        r['cover_noise'] = {
            'page_number': bool(re.search(r'第\s*1\s*页', p1)),
            # 只认「页眉特征」：竖线分隔 + 日期（原规则用「薪酬带宽报告|日期」，
            # 而封面标题本身就含「薪酬带宽报告」、日期也在封面出现 → 必然误报）
            'running_head': bool(re.search(r'\|\s*[^\n|]{0,24}\d{4}\.\d{2}\.\d{2}', p1)),
        }
    return r


def main():
    ap = argparse.ArgumentParser(description='客户版带宽报告内容维度自检')
    ap.add_argument('files', nargs='+')
    ap.add_argument('--watch', default='', help='追加高频套话词，逗号分隔')
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--strict', action='store_true', help='有红旗时返回退出码 1')
    args = ap.parse_args()

    watch = DEFAULT_WATCH + [w.strip() for w in args.watch.split(',') if w.strip()]
    results = [analyze(f, watch) for f in args.files if os.path.exists(f)]
    missing = [f for f in args.files if not os.path.exists(f)]

    # 跨版本逐字相同长句
    sets = {r['file']: collections.Counter(sentences(load_pdf(r['file'])[0], drop_noise=True))
            for r in results}
    cross = []
    if len(results) > 1:
        files = list(sets)
        common = set(sets[files[0]])
        for f in files[1:]:
            common &= set(sets[f])
        cross = sorted(common, key=len, reverse=True)

    red_flags = 0
    if args.json:
        print(json.dumps({'files': results, 'cross_version': cross, 'missing': missing},
                         ensure_ascii=False, indent=2))
    else:
        W = 96
        print('=' * W)
        print(f'客户版带宽报告 · 内容维度自检 —— {len(results)} 份')
        print('=' * W)
        for r in results:
            flags = len(r['gaps']) + len(r['dup_sents']) + sum(r['cover_noise'].values())
            red_flags += flags
            print(f"\n## {r['file']}")
            print(f"   {r['pages']} 页 | {r['chars']} 字符 | 元数据标题 {r['title']!r}")

            if r['gaps']:
                print(f"   [缺口] {len(r['gaps'])} 项")
                for g in r['gaps']:
                    extra = ''
                    if g.get('missing'):
                        extra = f"  → 缺：{'、'.join(g['missing'])}（{len(g['missing'])}/{g['total']} 国）"
                    print(f"      - {g['code']}  {g['desc']}{extra}")
            else:
                print('   [缺口] 无')

            if r['dup_sents']:
                print(f"   [版本内重复句] {len(r['dup_sents'])} 条")
                for d in r['dup_sents'][:6]:
                    print(f"      ×{d['times']}  {d['sent'][:64]}")
            else:
                print('   [版本内重复句] 无')

            if r['watch']:
                top = sorted(r['watch'].items(), key=lambda x: -x[1])
                print('   [高频词] ' + '  '.join(f'{w}×{k}' for w, k in top[:8]))

            noise = [k for k, v in r['cover_noise'].items() if v]
            print(f"   [封面] {'页眉/页码异常：' + ','.join(noise) if noise else '干净'}")

            if r['sections']:
                tot = sum(s['chars'] for s in r['sections'])
                seg = '  '.join(f"{s['head']}{s['chars']}" for s in r['sections'])
                thin = [s['head'] for s in r['sections'] if s['chars'] < tot * 0.08]
                print(f'   [章级篇幅] {seg}')
                if thin:
                    print(f'      thin: {"、".join(thin)}（占比 <8%，可考虑合并或补内容）')

        if cross:
            print(f'\n## 跨版本逐字相同长句（{len(cross)} 条）')
            for s in cross[:12]:
                print(f'   {s[:78]}')
            print('   提示：方法/免责/费率类可共用；地区小结、结论卡、方案建议必须差异化。')

        if missing:
            print(f'\n[警告] 文件不存在：{missing}')
        print('\n' + '=' * W)
        print(('FAIL（--strict）' if (red_flags or missing) and args.strict else 'DONE')
              + f'  红旗 {red_flags} 项')
        print('=' * W)

    if args.strict and (red_flags or missing):
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
