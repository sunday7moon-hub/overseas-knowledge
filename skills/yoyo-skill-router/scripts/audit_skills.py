#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
audit_skills.py — 技能体系审计（可复跑）

配合 SKILL.md 使用。回答五个问题：
  1. 盘点：有多少技能、体积多大、来源是什么（自建 / 分发 / SkillHub / 待判）
  2. 互指：谁和谁互相说了分工，哪些是零互指（冲突高发区）
  3. 冲突：哪些业务词被多个技能同时认领（Agent 会犹豫的位置）
  4. 枢纽：哪些技能被最多人引用（改名/合并前必须查）
  5. 绑定：自动化是否点名了技能（skills_json 是否为空 = 静默失效风险）

用法：
    python3 audit_skills.py                 # 全量审计
    python3 audit_skills.py --blind         # 只看零互指技能
    python3 audit_skills.py --conflicts     # 只看触发词冲突
    python3 audit_skills.py --hub           # 只看依赖枢纽
    python3 audit_skills.py --auto          # 只看自动化绑定风险

注意：技能目录 `.workbuddy` 是隐藏目录，**ripgrep / Grep 工具默认跳过隐藏目录**，
所以本脚本用 os.listdir 直接遍历，不要改用 rg。
"""
import io, os, re, sys, json, sqlite3, argparse
from collections import defaultdict, Counter

BASE = os.path.expanduser('~/.workbuddy/skills')
DB = os.path.expanduser('~/.workbuddy/workbuddy.db')

# 冲突检测用的业务词（可按需扩充）
KW = ['小红书', '发布', '海报', '卡片', 'PPT', '演示文稿', 'PDF', '报告', '薪酬', '竞品',
      '对标', '合规', '法律', '文案', '改写', '调研', '分析', '流量', '采集', '归档',
      '表格', '多维表', '文档', '图片', '生成', '设计', '原型', '交互', '流程', '知识库',
      '招聘', '员工手册', '合同', '模板', '客户', '画像', '视频', '总结', '搜索',
      '关键词', 'SEO', '邮件', '触达', '同步', '校验', '质检', '记忆', '技能']


def load():
    """返回 [{dir,size,files,desc,src,agent,dist,third}]"""
    out = []
    for d in sorted(os.listdir(BASE)):
        p = os.path.join(BASE, d, 'SKILL.md')
        if not os.path.isfile(p):
            continue
        s = io.open(p, encoding='utf-8', errors='replace').read()
        fm = re.match(r'^---\n(.*?)\n---', s, re.S)
        fm = fm.group(1) if fm else ''
        keys = set(re.findall(r'^([a-zA-Z_][\w-]*):', fm, re.M))
        agent = bool(re.search(r'agent_created:\s*true', fm))
        dist = bool(keys & {'visibility', 'display_name', 'featured', 'marketplace'})
        third = d.endswith('__skillhub')
        src = '🟢 自建' if agent else ('🟣 SkillHub' if third else ('🔵 分发' if dist else '⚪ 待判'))
        dm = re.search(r'^description:[ \t]*(.*?)(?=\n[a-zA-Z_][\w-]*:|\Z)', fm, re.S | re.M)
        desc = re.sub(r'\s+', ' ', dm.group(1)).strip() if dm else ''
        out.append({'dir': d, 'size': os.path.getsize(p),
                    'files': sum(len(f) for _, _, f in os.walk(os.path.join(BASE, d))),
                    'desc': desc, 'src': src, 'agent': agent, 'dist': dist,
                    'third': third, 'body': s})
    return out


def report_inventory(rows):
    print("═" * 62)
    print("① 盘点总览")
    print("═" * 62)
    c = Counter(r['src'] for r in rows)
    for k, v in c.most_common():
        print("  %-12s %d 个" % (k, v))
    print("  合计: %d 个技能 ｜ 总体积 %.1f MB" %
          (len(rows), sum(r['size'] for r in rows) / 1e6))
    print("\n  最大 8 个（改前先想清楚影响面）:")
    for r in sorted(rows, key=lambda x: -x['size'])[:8]:
        print("    %-32s %7.1f KB  %4d 文件" % (r['dir'], r['size'] / 1024, r['files']))
    noasset = [r['dir'] for r in rows
               if not os.path.isdir(os.path.join(BASE, r['dir'], 'references'))
               and not any(f.endswith(('.py', '.js', '.sh'))
                           for _, _, fs in os.walk(os.path.join(BASE, r['dir'])) for f in fs)]
    print("\n  无脚本无 references 的纯文本技能: %d 个" % len(noasset))
    print("   ", ", ".join(noasset[:10]), "..." if len(noasset) > 10 else "")


def report_blind(rows):
    print("\n" + "═" * 62)
    print("② 零互指技能（冲突高发区 —— 它们从不告诉 Agent「我不管什么」）")
    print("═" * 62)
    names = [r['dir'] for r in rows]
    blind, edges = [], 0
    for r in rows:
        refs = [n for n in names
                if n != r['dir'] and re.search(r'(?<![\w-])' + re.escape(n) + r'(?![\w-])', r['body'])]
        r['refs'] = refs
        edges += len(refs)
        if not refs:
            blind.append(r['dir'])
    print("  互指边总数: %d ｜ 平均每技能 %.1f 条" % (edges, edges / max(1, len(rows))))
    print("  零互指: %d 个" % len(blind))
    for b in blind:
        print("    ·", b)
    print("\n  依赖枢纽（被引用最多的 10 个 —— 改名/合并前必须同步改下游）:")
    c = Counter()
    for r in rows:
        for x in r.get('refs', []):
            c[x] += 1
    for n, k in c.most_common(10):
        print("    %-34s 被 %d 个技能引用" % (n, k))


def report_conflicts(rows):
    print("\n" + "═" * 62)
    print("③ 触发词冲突（同一句话能命中多个技能 → Agent 会摇摆）")
    print("═" * 62)
    owner = defaultdict(list)
    for r in rows:
        for k in KW:
            if k in r['desc']:
                owner[k].append(r['dir'])
    conf = sorted([(k, v) for k, v in owner.items() if len(v) >= 3],
                  key=lambda x: -len(x[1]))
    if not conf:
        print("  ✅ 零冲突（≥3 个技能共享的词）")
    for k, v in conf:
        flag = "🔴" if len(v) >= 6 else ("🟠" if len(v) >= 4 else "🟡")
        print("\n  %s 「%s」%d 个技能争抢:" % (flag, k, len(v)))
        for n in v:
            print("       -", n)


def report_auto():
    print("\n" + "═" * 62)
    print("④ 自动化绑定体检（skills_json 全空 = 技能全靠文字点名）")
    print("═" * 62)
    if not os.path.isfile(DB):
        print("  ⚠️ 找不到 %s，跳过" % DB)
        return
    try:
        con = sqlite3.connect('file:%s?mode=ro' % DB, uri=True)
        cur = con.cursor()
        cols = [r[1] for r in cur.execute("pragma table_info(automations)")]
        rows = list(cur.execute("select * from automations"))
    except Exception as e:
        print("  ⚠️ 读取失败: %s" % e)
        return
    names = [r['dir'] for r in load()]
    bound = empty = named = 0
    risky = []
    for row in rows:
        d = dict(zip(cols, row))
        if d.get('deleted_at') or d.get('status') != 'ACTIVE':
            continue
        try:
            sj = json.loads(d.get('skills_json') or '[]')
        except Exception:
            sj = []
        if sj:
            bound += 1
            continue
        empty += 1
        hit = [n for n in names if n in (d.get('prompt') or '')]
        if hit:
            named += 1
        else:
            risky.append(d.get('name', '?'))
    print("  启用中的自动化: %d 个" % (bound + empty))
    print("    ✅ 显式绑定技能: %d" % bound)
    print("    ⚠️ skills_json 为空: %d（其中 %d 个至少 prompt 里点名了技能）" % (empty, named))
    if risky:
        print("\n  🔴 **连技能名都没写**（改技能后必然静默降级）: %d 个" % len(risky))
        for n in risky:
            print("      ·", n)


def main():
    ap = argparse.ArgumentParser()
    for f in ('blind', 'conflicts', 'hub', 'auto'):
        ap.add_argument('--' + f, action='store_true')
    a = ap.parse_args()
    rows = load()
    if not any([a.blind, a.conflicts, a.hub, a.auto]):
        report_inventory(rows); report_blind(rows); report_conflicts(rows); report_auto()
    else:
        if a.blind or a.hub:
            report_blind(rows)
        if a.conflicts:
            report_conflicts(rows)
        if a.auto:
            report_auto()


if __name__ == '__main__':
    main()
