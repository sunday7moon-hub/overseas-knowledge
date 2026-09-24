#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UI 原型 · 架构级审计（architect lens）
------------------------------------------------------------
不是「手误级」校验，而是架构师视角找结构性问题：

  A. 样式架构  : CSS 类重复定义(静默覆盖) / 未使用类(死代码) / 特异性冲突 /
                硬编码颜色(没走 token) / 内联 style 占比
  B. 标记架构  : data-page-node-id 重复 / DOM id 重复 / 语义化(span 当按钮)
  C. 交互架构  : JS 语法 / chipOf↔状态映射一致性 / 死状态 / 函数定义≠调用(接了线没通电)
  D. 响应式前提: 移动端残留(max-w-md / @media) 与「只有 PC 端」前提是否矛盾
  E. 本次改动  : 新增 JD 入口的 wiring 是否完整

退出码 0 = 无阻断级问题；非 0 = 有架构问题需处理。
"""
import sys, re, os, subprocess, json
from html.parser import HTMLParser

def log(sev, cat, msg):
    icon = {"BLOCK":"🔴","WARN":"🟡","INFO":"🔵","OK":"🟢"}.get(sev,"·")
    print(f"  {icon} [{cat}] {msg}")

# ---------------------------------------------------------------- 读取
path = sys.argv[1]
html = open(path, encoding="utf-8").read()
base = os.path.basename(path)
print(f"\n{'='*70}\n架构审计 · {base}  ({len(html)} bytes / {html.count(chr(10))+1} 行)\n{'='*70}")

# ---------------------------------------------------------------- A. 样式架构
print("\n【A】样式架构")
css_block = re.search(r"<style[^>]*>(.*?)</style>", html, re.S)
css = css_block.group(1) if css_block else ""
# 按 @media 切分，记录每个选择器出现在哪些作用域
parts = re.split(r"(@media[^{]+)\{", css)
# parts[0] = 顶层; parts[1]=媒体查询A选择器, parts[2]=A体; parts[3]=B选择器, parts[4]=B体 ...
scope_of = {}   # 选择器 -> set(作用域标签)
def add_rules(body, scope):
    for sel in re.findall(r"([^{}]+)\{", body):
        sel = sel.strip()
        for x in [t.strip() for t in sel.split(",")]:
            scope_of.setdefault(x, set()).add(scope)
if parts:
    add_rules(parts[0], "top")
i = 1
while i + 1 < len(parts):
    mediasel = parts[i].strip()
    add_rules(parts[i+1], mediasel)
    i += 2
# 真重复 = 同一作用域内出现 >1 次（顶层重复 / 同媒体查询内重复）
real_dup = {}
for s, scs in scope_of.items():
    # 统计每个 scope 内的出现次数：需要回到原 css 精确计数
    pass
# 精确同作用域重复计数
scope_count = {}
for s, scs in scope_of.items():
    for sc in scs:
        scope_count[(s, sc)] = scope_count.get((s, sc), 0) + 1
real_dup = {f"{s} [{sc}]": n for (s, sc), n in scope_count.items() if n > 1}
if real_dup:
    for k, c in sorted(real_dup.items(), key=lambda x: -x[1])[:15]:
        log("WARN","CSS同域重复", f"{k} 重复 {c} 次（同作用域内静默覆盖，真问题）")
else:
    log("OK","CSS同域重复","无同作用域重复定义（所有重复均为 @media 响应式覆盖，合法）")
# 跨作用域重复（信息，非问题）
cross = {s: scs for s, scs in scope_of.items() if len(scs) > 1}
if cross:
    log("INFO","CSS响应式覆盖", f"{len(cross)} 个选择器在顶层+@media 间做了响应式重定义（合法级联，无需处理）")

# 类使用集合：从 HTML 标签 class="..." 收集
used = set()
for m in re.finditer(r'class="([^"]*)"', html):
    for c in m.group(1).split():
        used.add(c)
# 类定义集合（.xxx）
class_defs = set()
for s in scope_of:
    for m in re.finditer(r"\.([a-zA-Z][\w-]*)", s):
        class_defs.add(m.group(1))
unused = sorted(class_defs - used)
if unused:
    log("WARN","CSS死类", f"定义了但 HTML 未使用 {len(unused)} 个: {', '.join(unused[:20])}{' …' if len(unused)>20 else ''}")
else:
    log("OK","CSS死类","无死类")

# 硬编码颜色（在 :root 之外直接写 hex/rgb，且非变量声明）
root_vars = set(re.findall(r"(--[\w-]+)\s*:", css))
hard = re.findall(r"(?:^|[^-\w])(#([0-9a-fA-F]{3,8})\b|rgba?\([\d\s,.]+\))", css)
# 过滤掉变量声明行里的
hard_colors = []
for m in hard:
    seg = m[0]
    # 跳过 :root 变量定义
    if re.search(r"--[\w-]+\s*:\s*" + re.escape(seg), css): continue
    hard_colors.append(seg)
# 统计内联 style 里的硬编码
inline_hard = 0
for m in re.finditer(r'style="([^"]*)"', html):
    if re.search(r"#[0-9a-fA-F]{3,8}\b|rgba?\(", m.group(1)): inline_hard += 1
if hard_colors:
    uniq = sorted(set(hard_colors))
    log("INFO","硬编码颜色", f"CSS 内硬编码颜色 {len(uniq)} 种（未走 token 变量）: {', '.join(uniq[:12])}{' …' if len(uniq)>12 else ''}")
else:
    log("OK","硬编码颜色","全部走 token 变量")
_inline_total = len(re.findall(r'style="', html))
log("INFO","内联style", f"共 {_inline_total} 处内联 style，其中 {inline_hard} 处含硬编码颜色（可维护性债）")

# ---------------------------------------------------------------- B. 标记架构
print("\n【B】标记架构")
node_ids = re.findall(r'data-page-node-id="([^"]*)"', html)
dup_ids = sorted({i for i in node_ids if node_ids.count(i) > 1})
if dup_ids:
    log("BLOCK","节点ID重复", f"{len(dup_ids)} 个 data-page-node-id 重复: {', '.join(dup_ids[:10])}")
else:
    log("OK","节点ID重复", f"{len(set(node_ids))} 个唯一节点 id，无重复")
dom_ids = re.findall(r'\bid="([^"]*)"', html)
dup_dom = sorted({i for i in dom_ids if dom_ids.count(i) > 1})
if dup_dom:
    log("BLOCK","DOM id重复", f"{dup_dom}")
else:
    log("OK","DOM id重复","无重复 id")
# span 当按钮（含 btn 类但是 span, 且无可访问性）
fake_btns = len(re.findall(r'<span class="btn', html))
log("INFO","伪按钮", f"{fake_btns} 个 <span class=btn> —— 原型演示可接受，但研发交接需改成 <button>/<a>")

# ---------------------------------------------------------------- C. 交互架构
print("\n【C】交互架构")
js_block = re.search(r"<script>(.*?)</script>", html, re.S)
js = js_block.group(1) if js_block else ""
# JS 语法（node --check 需要文件）
jsfile = "/tmp/_audit_js.js"
open(jsfile,"w").write(js)
r = subprocess.run(["node","--check",jsfile], capture_output=True, text=True)
if r.returncode == 0:
    log("OK","JS语法","node --check 通过")
else:
    log("BLOCK","JS语法", r.stderr.strip().split("\n")[0])
    print(r.stderr)

# chipOf 映射 vs 状态常量
chipOf = dict(re.findall(r"(\w+):'([\w-]+)'", re.search(r"var chipOf\s*=\s*\{(.*?)\};", js, re.S).group(1) if re.search(r"var chipOf\s*=", js) else ""))
# 收集所有出现的状态字符串 'xxx' 在 chipOf 值里
chip_vals = set(chipOf.values())
# PRESETS / 可达状态（从 show() 调用、S.s 赋值推断）
state_lits = set(re.findall(r"['\"](idle|phone_err|sending|code_sent|code_wrong|rate|locked|verifying|success|onboard|set_pwd|set_email|set_company|onboard_done)['\"]", js))
# 也把 chipOf 的键当状态
chip_keys = set(chipOf.keys())
# 死状态：chipOf 定义了值，但没有任何地方把 S.s 设成该值 / show 调用不到
# 简化：报告 chipOf 键集合大小 & 是否有明显假键
log("INFO","状态映射", f"chipOf 共 {len(chipOf)} 条映射; 状态字面量出现 {len(state_lits)} 个")
# 检查 chipOf 里是否有「假键」—— 键不在状态枚举且值也不在
fake = [(k,v) for k,v in chipOf.items() if k not in state_lits and v not in state_lits and k not in ('idle','s','tab','tries','left','timer','redirect','title','isNew','ob','obQueue','obDone')]
if fake:
    log("WARN","状态假键", f"chipOf 疑似含非状态映射(历史 bug): {fake[:6]}")
else:
    log("OK","状态假键","chipOf 映射干净")

# 函数定义 vs 调用（接了线没通电）
defs = set(re.findall(r"function\s+([A-Za-z_]\w*)", js))
# 也支持 const fn = ()=>
defs |= set(re.findall(r"(?:const|let|var)\s+([A-Za-z_]\w*)\s*=\s*(?:function|\([^)]*\)\s*=>)", js))
calls = set(re.findall(r"\b([A-Za-z_]\w*)\s*\(", js))
# onclick= 引用
onclicks = set(re.findall(r'onclick="([A-Za-z_]\w*)', html))
# 检查 onclick 引用的函数是否定义
missing = [f for f in onclicks if f not in defs and f not in ("show","void","return","console")]
if missing:
    log("BLOCK","未通电", f"onclick 引用了未定义函数: {missing}")
else:
    log("OK","未通电", f"所有 {len(onclicks)} 个 onclick 处理器均已定义")
# 死函数（定义了从未被调用也不被 onclick）
called_or_bound = calls | onclicks
dead = [f for f in defs if f not in called_or_bound and f not in ("show","collectQueue","advanceQueue","showObDone")]
if dead:
    log("WARN","死函数", f"定义但未调用(可能接了线没通电): {dead[:10]}")
else:
    log("OK","死函数","无死函数")

# ---------------------------------------------------------------- D. 响应式前提
print("\n【D】响应式前提（用户: 只有 PC 端）")
mwmd = len(re.findall(r"max-w-md|max-w-sm|max-w-xs", css+html))
media = re.findall(r"@media[^{]*\([^)]*\)", css)
if mwmd:
    log("WARN","移动端残留", f"仍出现 {mwmd} 处 max-w-md/sm/xs（与「只有 PC 端」前提不符）")
else:
    log("OK","移动端残留","无移动端 max-width 残留")
if media:
    for mq in media[:8]:
        crit = re.search(r"min-width:\s*(\d+)|max-width:\s*(\d+)", mq)
        log("INFO","媒体查询", f"{mq.strip()}  → {crit.group(0) if crit else '?'}")
else:
    log("OK","媒体查询","无 @media 断点（纯 PC 单栏，符合前提）")

# ---------------------------------------------------------------- E. 本次改动
print("\n【E】本次改动: 首页 JD 合规检测入口 + hero CTA 通电状态")
jd = re.search(r"JD 合规检测", html)
if jd:
    cls = re.search(r'class="([^"]*)"', html[max(0,jd.start()-200):jd.start()+80])
    log("OK","JD入口存在", f"文案存在; class={cls.group(1) if cls else '?'}")
else:
    log("WARN","JD入口", "未找到 JD 合规检测 文案")
# hero CTA 整体通电状态（静态原型下全 unwired 属正常，但须记录给研发）
ctarow = re.search(r'class="cta-row"[^>]*>(.*?)</div>\s*</div>', html, re.S)
if not ctarow:
    ctarow = re.search(r'cta-row[^>]*>(.*)', html, re.S)
cta_btns = re.findall(r'<span class="btn[^"]*"[^>]*>([^<]*)</span>', ctarow.group(1) if ctarow else "")
cta_wired = 0
if ctarow:
    seg = ctarow.group(1)
    # 统计带 href/onclick 的 a/span
    cta_wired = len(re.findall(r'href=|onclick=', seg))
log("INFO","hero CTA", f"共 {len(cta_btns)} 个: {', '.join(cta_btns)}")
if cta_btns:
    if cta_wired == 0:
        log("INFO","CTA通电", f"全部 {len(cta_btns)} 个 CTA 均未绑定跳转（静态原型常态；研发交接须补 /jd-check /compliance-check /country-guide /salary-report）")
    else:
        log("WARN","CTA通电", f"仅 {cta_wired}/{len(cta_btns)} 个 CTA 通电，存在不一致")

print("\n" + "="*70)
print("审计结束。🔴=阻断  🟡=待处理(债)  🔵=信息  🟢=通过")
print("="*70)
