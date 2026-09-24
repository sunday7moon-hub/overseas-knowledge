#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""规则引用门禁 —— 检查「自动化 prompt ↔ SKILL.md」之间是否发生规则复制、引用失效或架构脱钩。

背景：自动化 prompt 里如果**复刻**了 SKILL.md 的规则（阈值/清单/正则/分类比例），
就产生 N 份副本，改一处必漏一处（转述丢失）。正解是 prompt **只引用不复制**。
但「引用」有个更凶的坑：prompt 用 `sed -n '/^### 9d\\./,/^### 10\\./p'` 按**章节锚点**
取规则，SKILL.md 一旦改名/改序号，sed **静默返回空**，自动化照跑但规则全丢。

本门禁共七项：

  单目标检查（需要 --skill 基准）
  A 锚点存活   FAIL —— prompt 里每个 sed 锚点必须在 SKILL.md 中命中 ≥1 行
  B 版本戳     FAIL（不一致）/ WARN（未声明）—— 规则版本跳变必须可见
  C 规则复制   WARN —— prompt 与 SKILL.md 的公共文本过长 = 复制了规则，应改引用
  D 快照陈旧   WARN —— 快照比 SKILL.md 旧，A/C 结果是假绿灯（--db 模式下自动不适用）

  架构级检查（--scan 或 --db，不依赖单个 skill）
  E 内联规则量 WARN —— prompt 自带大量规则信号词 = 规则可能没落到 SKILL.md（孤本/双份）
  F 未绑定     WARN —— prompt 引用了 skill 但 automations.skills_json 为空 = 依赖未声明
  G 易失资产   WARN —— prompt 用 /WorkBuddy/<时间戳会话目录>/ 当脚本仓库，会话清理即失联

用法：
  # ① 全量盘查（推荐；直读 live 数据库，无陈旧问题）
  python rule_ref_lint.py --scan

  # ② 对某条链路做深度检查（DB 取 prompt，指定基准 SKILL.md）
  python rule_ref_lint.py --skill ~/.workbuddy/skills/overseas-news-daily/SKILL.md \\
      --db --ids 1780386082442,1783050067278,1782179868657

  # ③ 兼容旧用法：手工快照目录 / 单个 prompt 文件
  python rule_ref_lint.py --skill X.md --snapshots ~/.workbuddy/skills/X/.rule-ref
  python rule_ref_lint.py --skill X.md --prompt-file /tmp/p.md

退出码：0 = 无 FAIL；1 = 有 FAIL（--strict 时 WARN 也返回 1）
"""
from __future__ import annotations

import argparse
import glob
import io
import json
import os
import re
import sqlite3
import sys
from difflib import SequenceMatcher

# ---- 版本戳（两处必须一致；改任一 SKILL.md 都要 bump） -------------------
RE_VER_SKILL = re.compile(r'RULE_VERSION\s*[:：]\s*([0-9][0-9.]+)')
RE_VER_PROMPT = re.compile(r'规则版本\s*[:：]\s*([0-9][0-9.]+)')

# prompt 里提取 sed 锚点：sed -n '/^## A/,/^### B/p'
RE_SED = re.compile(r"""sed\s+-n\s+['"]([^'"]+)/p['"]""")

# prompt 里引用 SKILL.md（直接路径 或 shell 变量绑定）
RE_SKILL_PATH = re.compile(r'([\w~/.\-]*)skills/([\w\-]+)/SKILL\.md')
RE_SKILL_VAR = re.compile(r'(\w+)=([\w~/.\-]*skills/[\w\-]+/SKILL\.md)')

# 易失资产：把时间戳会话目录当脚本仓库
RE_SESSION_DIR = re.compile(r'/WorkBuddy/\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2}/')

# 规则信号词：出现在 prompt 里说明「这段可能谈到了规则」——仅作辅助参考
# ⚠️ 不能只数信号词：改造后的 prompt 里「禁止全量 Read」「禁止内联 Python」是执行约束，不是规则，
#    会被误判。真正的判据是下面的「规则指纹」（精确模式），信号词只用来提示。
RULE_SIGNALS = [
    '禁止', '不得', '红线', '一律', '阈值', '判据', '清单', '比例', '优先级',
    '最多', '至少', '不超过', '必须', '跳过', '排除', '黑名单', '白名单',
    '去重', '提级', '豁免', '入池', 'no_result',
]
SIGNAL_WARN = 12   # 信号词命中总数（辅助指标，仅提示）

# 规则指纹：prompt 里出现这些 = 真的夹带了规则实体（而非仅「见 §9d」式引用）。
# ⚠️ 误报是这门禁的头号死因——有误报就会被弃用。所以每条都要求「规则才有的完整形状」：
#    · 数量下限必须带量词（`≥8 条` ✓ / `>=1.0.69` ✗ / `count>0` ✗ / `exit code=2` ✗）
#    · 禁发类只认「N 类 / N 个层级」这种确数清单，不认「禁止发布标记」这样的动作名
RULE_FINGERPRINTS = [
    # 比例：限定「单个数字」，否则 `23:59:59` / `00:00:00` 这类时间戳会被误伤
    (r'(?<![\d:])\d\s*[:：]\s*\d\s*[:：]\s*\d(?![\d:])',                   '分类比例 N:M:N'),
    (r'[≥>]\s*=?\s*\d+\s*(?:条|个|项|篇|份|国|张|轮|次|名|人|家)',          '数量下限（带量词）'),
    (r'(?:不超过|最多|至少|最少)\s*\d+\s*(?:条|个|项|篇|份|轮|次|张|国)',    '数量上下限'),
    (r'\d+\s*(?:天|日|个月)内',                                           '时间窗口 N 天内'),
    (r'第\s*[1-9一二三四五六]\s*优先',                                     '优先级排序'),
    (r'八类|8\s*类|7\s*类|七类|七\s*个层级|6\s*个层级|六个层级',             '禁发清单/来源层级数'),
    (r'黑名单|白名单',                                                    '来源黑白名单'),
    (r'每\s*[^，。；\s]{1,6}\s*最多\s*\d+',                                '配额规则'),
    (r'(?:模板编号|国别代码|类型代码)[规则]?[：:]',                          '编号规则'),
    (r'宁可[^，。]{0,8}也?不[^，。]{0,10}假数据|一条假数据',                 '数据质量铁律'),
]
TABLE_MIN_ROWS = 4   # markdown 表格连续 ≥4 行 = 一个内联清单表

MIN_BLOCK = 18  # 公共文本块 ≥ 此长度才算「复制」（低于此值多是术语巧合）
COPY_RATIO_WARN = 0.12  # 公共文本占 prompt 比例超过此值 → WARN

DB_DEFAULT = os.path.expanduser('~/.workbuddy/workbuddy.db')
SKILLS_DIR = os.path.expanduser('~/.workbuddy/skills')


def _norm(s: str) -> str:
    """归一化：去掉 markdown 装饰、路径/ID/URL 等 ASCII 长串、空白，便于做公共文本比对。

    ⚠️ 关键：**路径、表 ID、token、URL 是 prompt 的「执行契约」，必须留在 prompt 里**，
    不算规则复制。只有中文规则文本（阈值/清单/判定/比例）的重复才报警。
    """
    s = re.sub(r'```.*?```', ' ', s, flags=re.S)  # 去代码块（含 sed 命令本身）
    s = re.sub(r'https?://\S+', ' ', s)           # 去 URL
    s = re.sub(r'[A-Za-z0-9_\-./:%]{8,}', ' ', s)  # 去路径 / ID / token / 英文长串
    s = re.sub(r'[#*`>|\-–—\s\u3000]+', '', s)
    return s


def _read(path: str) -> str:
    return io.open(path, encoding='utf-8', errors='ignore').read()


# ================================================================ 单目标检查
# ---------------------------------------------------------------- A 锚点存活
def check_anchors(prompt: str, skill_text: str):
    """返回 (锚点总数, [(锚点, 命中行数, 说明), ...] 失效列表)"""
    anchors = []
    for expr in RE_SED.findall(prompt):
        for part in expr.split(','):
            part = part.strip().strip('/')
            if part.startswith('^') or part.startswith('\\'):
                anchors.append(part)
    seen, uniq = set(), []
    for a in anchors:
        if a not in seen:
            seen.add(a)
            uniq.append(a)

    dead = []
    for a in uniq:
        try:
            n = len(re.findall(a, skill_text, flags=re.M))
        except re.error as e:
            dead.append((a, -1, f'正则非法：{e}'))
            continue
        if n == 0:
            dead.append((a, 0, '锚点在 SKILL.md 中不存在 → sed 静默返回空，自动化盲跑'))
    return len(uniq), dead


# ---------------------------------------------------------------- B 版本戳
def check_version(prompt: str, skill_text: str) -> tuple[str, str]:
    """返回 (状态, 说明)。状态 ∈ ok / missing / mismatch / skill-missing"""
    m = RE_VER_SKILL.search(skill_text)
    if not m:
        return 'skill-missing', 'SKILL.md 头部未声明 RULE_VERSION（请加 `<!-- RULE_VERSION: YYYY.MM.DD -->`）'
    sv = m.group(1)
    pm = RE_VER_PROMPT.search(prompt)
    if not pm:
        return 'missing', f'SKILL.md 规则版本 {sv}；prompt 未声明「规则版本：…」→ 跳变不可见'
    if pm.group(1) != sv:
        return 'mismatch', f'SKILL.md 已升到 {sv}，prompt 仍声明 {pm.group(1)} → 需核对变更后同步'
    return 'ok', f'规则版本一致：{sv}'


# ---------------------------------------------------------------- C 规则复制
def check_copy(prompt: str, skill_text: str):
    """返回 (公共文本字符数, prompt 归一化长度, 占比, Top 片段列表)"""
    p, s = _norm(prompt), _norm(skill_text)
    if not p:
        return 0, 0, 0.0, []
    sm = SequenceMatcher(None, p, s, autojunk=False)
    blocks = [b for b in sm.get_matching_blocks() if b.size >= MIN_BLOCK]
    total = sum(b.size for b in blocks)
    blocks.sort(key=lambda b: -b.size)
    top = [(p[b.a:b.a + b.size]) for b in blocks[:6]]
    return total, len(p), (total / len(p) if p else 0), top


# ================================================================ 架构级检查
def extract_skill_refs(prompt: str):
    """从 prompt 里提取被引用的 skill 名（路径形式 + shell 变量形式）。"""
    names = set()

    def _add(mod: str, path: str):
        if path.startswith('/') and not os.path.exists(path):
            pass  # 路径不存在也记账，由调用方判断
        names.add(mod)

    for _pre, mod in RE_SKILL_PATH.findall(prompt):
        names.add(mod)
    for _var, path in RE_SKILL_VAR.findall(prompt):
        m = RE_SKILL_PATH.search(path)
        if m:
            names.add(m.group(2))
    # 变量引用 $S 的场景：只要 prompt 里出现过该 skill 名即可（上面的正则会覆盖）
    return sorted(names)


def check_inline_rules(prompt: str):
    """E 项辅助：规则信号词命中数（只提示，不单独定级）。"""
    hits = {}
    for k in RULE_SIGNALS:
        c = prompt.count(k)
        if c:
            hits[k] = c
    return sum(hits.values()), hits


def check_rule_fingerprints(prompt: str):
    """E 项主判据：返回 (指纹列表, 规则表块数)。

    只认「规则才会长成的形状」——比例、阈值、禁发清单、黑白名单、编号规则、时间窗口。
    执行契约（路径 / 表 ID / token / 脚本名）不会命中任何一条。
    """
    found = []
    for pat, label in RULE_FINGERPRINTS:
        try:
            n = len(re.findall(pat, prompt, flags=re.M))
        except re.error:
            continue
        if n:
            found.append(f'{label}×{n}')
    # markdown 表格块：连续 >= TABLE_MIN_ROWS 行以 | 开头 = 一张内联清单表
    tables, run = 0, 0
    for ln in prompt.split('\n'):
        if ln.strip().startswith('|'):
            run += 1
        else:
            if run >= TABLE_MIN_ROWS:
                tables += 1
            run = 0
    if run >= TABLE_MIN_ROWS:
        tables += 1
    return found, tables


def check_skill_binding(prompt: str, skills_json: str):
    """F 项：prompt 引用了 skill，但 automations.skills_json 没声明依赖。"""
    refs = extract_skill_refs(prompt)
    try:
        declared = json.loads(skills_json or '[]')
    except Exception:
        declared = []
    declared_names = set()
    for d in declared if isinstance(declared, list) else []:
        if isinstance(d, str):
            declared_names.add(os.path.basename(d.rstrip('/')))
        elif isinstance(d, dict):
            p = d.get('path') or d.get('name') or ''
            declared_names.add(os.path.basename(str(p).rstrip('/')))
    missing = [r for r in refs if r not in declared_names]
    return refs, sorted(declared_names), missing


def check_volatile_paths(prompt: str):
    """G 项：返回 prompt 里出现的会话工作区目录列表（脚本/产物存放于易失目录）。"""
    return sorted(set(RE_SESSION_DIR.findall(prompt)))


# ================================================================ 跑一份
def audit_one(name: str, prompt: str, skill_text: str):
    a_total, a_dead = check_anchors(prompt, skill_text)
    v_state, v_msg = check_version(prompt, skill_text)
    c_total, c_len, c_ratio, c_top = check_copy(prompt, skill_text)

    fails, warns = [], []

    if a_dead:
        for anchor, n, why in a_dead:
            fails.append(f'[A 锚点失效] `{anchor}` → {why}')
    if v_state == 'mismatch':
        fails.append(f'[B 版本不一致] {v_msg}')
    if v_state in ('missing', 'skill-missing'):
        warns.append(f'[B 版本戳缺失] {v_msg}')
    if c_ratio >= COPY_RATIO_WARN:
        warns.append(
            f'[C 规则复制] prompt 与 SKILL.md 公共文本 {c_total} 字 '
            f'（占 prompt {c_ratio:.0%}，阈值 {COPY_RATIO_WARN:.0%}）→ 建议改为引用')

    return dict(name=name, anchors=a_total, dead=a_dead, ver_state=v_state,
                ver_msg=v_msg, copy_total=c_total, copy_ratio=c_ratio,
                copy_top=c_top, fails=fails, warns=warns)


# ================================================================ 数据源
def load_from_db(db_path: str, ids: str = ''):
    """直读 live 数据库。这是 prompt 的唯一可信来源——备份 JSON 会滞后 8-12 天。"""
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute("SELECT id,name,prompt,skills_json,status,updated_at,rrule,cwds "
                "FROM automations WHERE COALESCE(deleted_at,'')=''")
    idl = [i.strip() for i in ids.split(',') if i.strip()]
    out = []
    for r in cur.fetchall():
        if idl and not any(i in (r['id'] or '') for i in idl):
            continue
        out.append(dict(id=r['id'], name=r['name'], prompt=r['prompt'] or '',
                        skills_json=r['skills_json'] or '[]',
                        status=r['status'], updated_at=r['updated_at'],
                        rrule=r['rrule'], cwds=r['cwds']))
    con.close()
    return out


def load_from_dir(path: str, ids: str = ''):
    idl = [i.strip() for i in ids.split(',') if i.strip()]
    jobs = []
    files = []
    for p in ('*.json', '*.md', '*.txt'):
        files += glob.glob(os.path.join(path, p))
    for f in sorted(files):
        base = os.path.basename(f)
        if 'readme' in base.lower():
            continue
        if idl and not any(i in base for i in idl):
            continue
        if f.endswith('.json'):
            try:
                d = json.load(io.open(f, encoding='utf-8'))
            except Exception as e:
                print(f'⚠ 跳过 {base}：{e}')
                continue
            jobs.append(dict(id=d.get('id', base), name=d.get('name', base),
                             prompt=d.get('prompt', ''),
                             skills_json=json.dumps(d.get('skills_json', []),
                                                    ensure_ascii=False),
                             status=d.get('status', ''), updated_at=None,
                             rrule='', cwds='', _mtime=os.path.getmtime(f)))
        else:
            # 活快照：整份文件即 prompt
            jobs.append(dict(id=base, name=base, prompt=_read(f), skills_json='[]',
                             status='', updated_at=None, rrule='', cwds='',
                             _mtime=os.path.getmtime(f)))
    return jobs


# ================================================================ 主流程
def main():
    ap = argparse.ArgumentParser(description='规则引用门禁：自动化 prompt ↔ SKILL.md')
    ap.add_argument('--skill', help='SKILL.md 路径（单目标检查的基准）')
    ap.add_argument('--scan', action='store_true',
                    help='全量盘查模式：扫所有自动化 + 所有 skill，出架构风险清单')
    src = ap.add_mutually_exclusive_group()
    src.add_argument('--db', nargs='?', const=DB_DEFAULT, default=None,
                     metavar='PATH', help=f'prompt 来源=live 数据库（默认 {DB_DEFAULT}）')
    src.add_argument('--automations', '--snapshots', dest='automations',
                     help='prompt 来源目录：*.json（备份）或 *.md/*.txt（活快照）')
    src.add_argument('--prompt-file', help='单个 prompt 文本文件')
    ap.add_argument('--ids', default='', help='只挑这些 id，逗号分隔（匹配文件名/id 子串）')
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--strict', action='store_true', help='有 WARN 也返回 1')
    args = ap.parse_args()

    # ---------------- 全量盘查 ----------------
    if args.scan:
        return run_scan(args)

    if not args.skill:
        print('✗ 单目标模式需要 --skill；全量盘查请加 --scan')
        return 1
    if not os.path.exists(args.skill):
        print(f'✗ SKILL.md 不存在：{args.skill}')
        return 1

    skill_text = _read(args.skill)

    if args.db:
        jobs = load_from_db(args.db, args.ids)
    elif args.prompt_file:
        jobs = [dict(id=os.path.basename(args.prompt_file), name=os.path.basename(args.prompt_file),
                     prompt=_read(args.prompt_file), skills_json='[]', status='',
                     updated_at=None, rrule='', cwds='', _mtime=None)]
    elif args.automations:
        jobs = load_from_dir(args.automations, args.ids)
    else:
        print('✗ 请指定 prompt 来源：--db / --automations / --prompt-file')
        return 1

    if not jobs:
        print('⚠ 没有匹配到任何 prompt')
        return 0

    skill_mtime = os.path.getmtime(args.skill)
    results = []
    for j in jobs:
        r = audit_one(f"{j['name']}（{j['id']}）", j['prompt'], skill_text)
        mt = j.get('_mtime')
        if mt is not None and mt < skill_mtime:
            lag = (skill_mtime - mt) / 86400
            r['warns'].append(
                f'[D 快照陈旧] prompt 快照比 SKILL.md 旧 {lag:.1f} 天 → '
                f'A/C 结果不可信，请先同步快照')
            r['stale_days'] = round(lag, 1)
        results.append(r)

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print(f'规则引用门禁 · 基准 SKILL.md：{args.skill}')
        if args.db:
            print(f'prompt 来源：live DB（{args.db}）→ D 项不适用')
        print('=' * 72)
        n_fail = n_warn = 0
        for r in results:
            mark = '✗ FAIL' if r['fails'] else ('⚠ WARN' if r['warns'] else '✓ PASS')
            print(f"\n{mark}  {r['name']}")
            print(f"  A 锚点：引用 {r['anchors']} 个，失效 {len(r['dead'])} 个")
            print(f"  B 版本：{r['ver_msg']}")
            tail = '' if r['copy_ratio'] < COPY_RATIO_WARN else '  ← 超过阈值'
            print(f"  C 复制：公共文本 {r['copy_total']} 字，占 prompt "
                  f"{r['copy_ratio']:.0%}{tail}")
            for t in r['copy_top'][:3]:
                print(f"      · 重复片段：{t[:48]}")
            for x in r['fails']:
                print(f"  {x}")
            for x in r['warns']:
                print(f"  {x}")
            n_fail += len(r['fails'])
            n_warn += len(r['warns'])
        print('\n' + '=' * 72)
        print(f'小计：{n_fail} FAIL / {n_warn} WARN / {len(results)} 个对象')
        if n_fail:
            print('结论：不合格——失效锚点会让自动化盲跑，必须修。')
        elif n_warn:
            print('结论：可用，但有漂移风险项待收敛。')
        else:
            print('结论：合格。')

    bad = any(r['fails'] for r in results) or (
        args.strict and any(r['warns'] for r in results))
    return 1 if bad else 0


# ================================================================ 全量盘查
def run_scan(args) -> int:
    db = args.db or DB_DEFAULT
    if not os.path.exists(db):
        print(f'✗ 数据库不存在：{db}')
        return 1

    # --json 模式只吐纯 JSON（供自动化消费），人类可读输出静默丢弃
    _stdout = sys.stdout
    if args.json:
        sys.stdout = io.StringIO()

    autos = load_from_db(db, args.ids)
    print(f'规则逻辑架构 · 全量盘查（{len(autos)} 条自动化 · live DB）')
    print('=' * 96)

    rows = []
    for a in autos:
        prompt = a['prompt']
        refs, declared, missing = check_skill_binding(prompt, a['skills_json'])
        sig_total, sig_hits = check_inline_rules(prompt)
        fps, tables = check_rule_fingerprints(prompt)
        volatile = check_volatile_paths(prompt)
        anchors = len(set(re.findall(r"""sed\s+-n\s+['"]\^([^'"]+)?""", prompt))) or (
            len(RE_SED.findall(prompt)))

        # A/B/C：如果能定位到被引用的 SKILL.md 就顺手跑
        target_skill = None
        for r_ in refs:
            cand = os.path.join(SKILLS_DIR, r_, 'SKILL.md')
            if os.path.exists(cand):
                target_skill = cand
                break
        a_dead, ver_msg, copy_ratio = [], '', 0.0
        if target_skill:
            st = _read(target_skill)
            _, a_dead = check_anchors(prompt, st)
            v_state, ver_msg = check_version(prompt, st)
            _, _, copy_ratio, _ = check_copy(prompt, st)

        level, reasons = '🟢', []
        if a_dead:
            level = '🔴'
            reasons.append(f'A 锚点失效 {len(a_dead)} 个（盲跑）')
        # E1 = 已有真相源却仍内联规则副本（判据：规则指纹）
        # E2 = 规则只活在 prompt 里，无任何 skill 承载（判据：规则指纹 或 内联清单表）
        # 有引用 + 只有内联表 → 多为自动化自身的步骤表（如 QC 三层检查项），不算外部规则复刻
        if refs and fps:
            if level == '🟢':
                level = '🟡'
            reasons.append(
                f'E1 引用与规则副本并存（指纹：{"；".join(fps)}）'
                f' → 规则已有真相源 {refs}，prompt 里应删除副本改引用')
        elif not refs and (fps or tables):
            if level == '🟢':
                level = '🟡'
            fp_txt = '；'.join(fps) if fps else '—'
            reasons.append(
                f'E2 规则无真相源·孤本（指纹：{fp_txt}；内联清单表 {tables} 张）'
                f' → 规则只活在 prompt 里，无法版本化/回归，建议落成 skill')
        if refs and missing:
            if level == '🟢':
                level = '🟡'
            reasons.append(f'F 依赖未声明（{",".join(missing)}）')
        if volatile:
            if level == '🟢':
                level = '🟡'
            reasons.append(f'G 易失目录资产 {len(volatile)} 处')
        if copy_ratio >= COPY_RATIO_WARN:
            if level == '🟢':
                level = '🟡'
            reasons.append(f'C 与 skill 重复 {copy_ratio:.0%}')

        rows.append(dict(a=a, refs=refs, declared=declared, missing=missing,
                         sig=sig_total, sig_hits=sig_hits, fps=fps, tables=tables,
                         volatile=volatile, dead=a_dead, ver=ver_msg, copy=copy_ratio,
                         level=level, reasons=reasons))

    # 按风险等级排序（同级按规则负担排序）
    order = {'🔴': 0, '🟡': 1, '🟢': 2}
    rows.sort(key=lambda r: (order[r['level']], -(len(r['fps']) + r['tables'])))

    for r in rows:
        a = r['a']
        print(f"\n{r['level']}  {a['name']}   [{a['status']}]  prompt {len(a['prompt'])} 字")
        print(f"     id={a['id']}")
        print(f"     引用 skill：{r['refs'] or '（无）'}"
              f"   DB 声明依赖：{r['declared'] or '（空 skills_json）'}")
        print(f"     E 规则指纹：{'; '.join(r['fps']) or '（无）'}"
              f"   内联规则表：{r['tables']} 张")
        print(f"       （辅助）规则信号词 {r['sig']} 个")
        if r['volatile']:
            print(f"     G 易失目录：{r['volatile']}")
        if r['copy']:
            print(f"     C 与 skill 公共文本占比：{r['copy']:.0%}")
        if r['ver']:
            print(f"     B {r['ver']}")
        for d in r['dead']:
            print(f"     ✗ A 失效锚点：{d[0]}")
        if r['reasons']:
            print(f"     → {'；'.join(r['reasons'])}")

    # ---------------- skill 侧体检 ----------------
    print('\n' + '=' * 96)
    print('skill 侧体检 · RULE_VERSION 覆盖率（规则可版本化 = 漂移可见的前提）')
    print('-' * 96)
    have, lack_scripts, lack_plain = [], [], []
    for d in sorted(glob.glob(os.path.join(SKILLS_DIR, '*/'))):
        n = os.path.basename(d.rstrip('/'))
        s = os.path.join(d, 'SKILL.md')
        if not os.path.exists(s):
            continue
        if RE_VER_SKILL.search(_read(s)):
            have.append(n)
        elif os.path.isdir(os.path.join(d, 'scripts')):
            lack_scripts.append(n)
        else:
            lack_plain.append(n)
    print(f'  已有版本戳：{len(have)} → {have}')
    print(f'  无版本戳·有脚本（优先补）：{len(lack_scripts)} → {lack_scripts}')
    print(f'  无版本戳·纯文档：{len(lack_plain)}')
    print(f'  合计 skill：{len(have) + len(lack_scripts) + len(lack_plain)}')

    n_red = sum(1 for r in rows if r['level'] == '🔴')
    n_yel = sum(1 for r in rows if r['level'] == '🟡')
    print('\n' + '=' * 96)
    print(f'盘查小计：🔴 {n_red} · 🟡 {n_yel} · 🟢 {len(rows) - n_red - n_yel}（共 {len(rows)} 条自动化）')
    print(f'规则信号阈值：>={SIGNAL_WARN} 报警，>={SIGNAL_WARN // 2} 提示（本文件顶部可调）')
    if n_red:
        print('结论：存在盲跑风险，必须先修 A 项。')
    elif n_yel:
        print('结论：无盲跑风险，但有架构待收敛项。')
    else:
        print('结论：架构干净。')

    if args.json:
        sys.stdout = _stdout
        out = [dict(id=r['a']['id'], name=r['a']['name'], level=r['level'],
                    refs=r['refs'], declared=r['declared'], missing=r['missing'],
                    signals=r['sig'], fingerprints=r['fps'], tables=r['tables'],
                    volatile=r['volatile'], copy_ratio=round(r['copy'], 3),
                    dead=[d[0] for d in r['dead']], reasons=r['reasons'])
               for r in rows]
        payload = dict(summary=dict(total=len(rows), red=n_red, yellow=n_yel,
                                    green=len(rows) - n_red - n_yel),
                       skills=dict(total=len(have) + len(lack_scripts) + len(lack_plain),
                                   versioned=len(have), scripted_unversioned=len(lack_scripts),
                                   doc_unversioned=len(lack_plain)),
                       automations=out)
        print(json.dumps(payload, ensure_ascii=False, indent=2))

    bad = n_red > 0 or (args.strict and n_yel > 0)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
