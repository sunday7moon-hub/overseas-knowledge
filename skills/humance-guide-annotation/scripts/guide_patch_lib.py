#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
慧思国别指南「更新标注」共用库
================================
唯一实现（single source of truth）——单国脚本与批量脚本都 import 本文件，
不要在别处复制渲染逻辑。

对外接口：
  BRAND / INK / INK2 / INK3 / TITLE_INK      站内实测色值
  render_note(note) -> str                    单条标注块 HTML
  render_version_bar(counts) -> str            页头数据版本条 HTML
  BADGE_CSS                                    章节徽标伪元素样式
  build(content, preview, cfg) -> (c, p, report, inserted)
  validate(before, after, cfg) -> [err]
  residual_check(before, after, inserted) -> str|None   证明「只增不改」
  strapi_get(doc) / strapi_put(doc, c, p) / token()

站点色值实测来源：https://dev-gpt.anchorwe.com/anchorai/css/blue.css
  主色 --primary #1565c0 ｜ 章节标题 #0d47a1 ｜ 版本条底 #f5f9ff
禁止出现：#0b3fbf / #155dfc / #1a365d（自创蓝，2026-09-22 已踩坑）
"""
import datetime
import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.request

STRAPI_BASE = "https://admin.humancehr.com"
TODAY = datetime.date.today().isoformat()

BRAND = "#1565c0"       # 站内主色（blue.css --primary）
TITLE_INK = "#0d47a1"   # 章节标题 / 版本条字色（blue.css .section-title）
INK, INK2, INK3 = "#18181b", "#52525b", "#a1a1aa"

# 非站色黑名单：生成物里出现即判不合格
FORBIDDEN_COLORS = ["#0b3fbf", "#155dfc", "#1a365d", "#155dfb"]

# ── 「已正式生效 / 计划变更」判定（2026-09-23 新增，唯一实现）★ ────────────────
# 背景（Yoyo 2026-09-23）：2026-06-01 已生效的条目，线上却显示成「计划」。
# 判定口径 = **法规生效日 vs 标注写入日**，与「正文是否已更新」是两个正交维度：
#   · effective  已正式生效（生效日 ≤ 写入日；**当日生效算已生效**）
#   · scheduled  计划变更（生效日 > 写入日）
#   · na         不适用（无具体日期，如「—（维持现行）」）
# 页面文案必须同时表达两个维度，例如「⏳ 待更新 · 已正式生效」——
# 「待更新」说的是**页面正文**还没改，「已正式生效」说的是**法规本身**已落地，
# 二者不可互相替代。
#
# ★ 文案是**客户向**的（Yoyo 2026-09-23 定：「写这个是给客户看的」）：
#   页面读者是出海中企 HR，不熟悉我方内部口径 ⇒ 用「已正式生效 / 计划变更」，
#   不用内部味更重的「法规已生效 / 计划生效」。改文案**只改这一处**，
#   渲染层 / 预览层 / 门禁探针全部引用它（别再各写一份）。
EFF_TEXT = {"effective": "已正式生效", "scheduled": "计划变更", "na": ""}

# 已被替换的旧文案：产物里出现即判不合格（防旧稿/手写稿回流）。
EFF_TEXT_STALE = ["法规已生效", "计划生效"]

# ── 内部过程字段：页面**不得展示**，只记在飞书台账（Yoyo 2026-09-23 定）★ ─────────
# 截图圈出的是页面底部那串：
#     「标注写入：2026-09-23 ｜ 校对 ID PR-20260907-046 ｜ 页面位置：薪酬支付」
# 以及**版本条尾部**的「校对批次 B2-01-T-migrate」（2026-09-23 二轮又圈出）。
# 四样都撤出页面，各归台账一列：
#   · 标注写入时间 → 台账「更新时间(标注写入)」
#   · 校对ID      → 台账「校对ID」列（本来就是台账主键）
#   · 页面位置    → 台账「落位章节」列（★ 2026-09-23 二轮补：Yoyo 再次圈出，
#                    说明首轮只撤了前两个、把它落下了。同一件事别做两遍，
#                    所以这次直接进本清单，由三处门禁一起把关）
#   · 校对批次    → 台账「校对批次」列（★ 2026-09-23 三轮补：截图红框圈出，
#                    这是个**生产工单号**，`-migrate` 后缀更是迁移动作的内部标记）
# 机器定位改走 **属性**（不可见但可查），所以撤出文本不影响任何下游能力：
#   · data-cg-rid    → 校对ID（回写台账 / 回查定位）
#   · data-cg-anchor → 落位章节（反抽 / 人工排查时知道这块该在哪）
# 三处门禁共用本清单（别各写一份）：validate 的 F4 / qc_gate 的 F4 / verify_secondary 的 S13。
# 教训：**「撤出页面」要一次做全**。同一个截图上圈了几个字段就撤几个 ——
#       漏一个就要再走一轮（页面位置、校对批次各补了一轮），而下线返工的成本远高于当初看全。
INTERNAL_FIELDS = ["标注写入", "校对ID", "校对 ID", "页面位置", "校对批次"]

# ── 三种标注状态的**唯一文案真相源**（2026-09-23 收敛）★ ──────────────────────
# 背景（Yoyo 2026-09-23 反馈截图）：「✅ 已核实维持」这个状态读着别扭 ——
#   ① 它是**过程语**（已核实 + 维持），不是客户能一眼读懂的**结论词**；
#   ② 「维持」的参照物（原内容）客户看不见，等于说了半句话；
#   ③ 与同一块的 meta 行「生效日期 —（维持现行）」语义重复，同一件事说两遍。
# 新口径 = 与 `⏳ 待更新` **同构反义**：`✅ 无需更新`（待更新 ↔ 无需更新）。
# 改文案**只改这一处**：渲染层 / 版本条 / 预览 / 台账 / 通知 / 反抽全部引用它。
STATUS_TEXT = {
    "pending": "⏳ 待更新",
    "check": "⚠️ 待核",
    "keep": "✅ 无需更新",
}
# 已被替换的旧状态文案：产物里出现即判不合格（防旧稿回流）。
STATUS_TEXT_STALE = ["已核实维持", "计划更新"]

# 页面**绝对不能出现**的旧文案合集 —— 标注状态 + 生效状态，两类合一份。
# ★ 为什么要合：F3（qc）/F3（validate）/S12（二次校验）三个门禁都要查这件事，
#   以前各查各的（qc 只查 EFF_TEXT_STALE、validate 分两处），改文案时必然漏一处。
#   现在只此一份，谁要查都引这个常量。**别在任何门禁里再拼一次。**
STALE_COPY = STATUS_TEXT_STALE + EFF_TEXT_STALE


def st_text(status):
    """状态码 → 客户向文案。未知状态码原样返回（不猜，别静默吞掉）。"""
    return STATUS_TEXT.get(status, status)


# 「官方原文 ↗」链接的 href 抽取（唯一实现，供 validate / qc_gate / verify 三处共用）
# ★ 为什么只数「数量」不够（2026-09-23 补）：
#   L4 原本只校验 `count(">官方原文 ↗</a>") == len(notes)`。可「数量对」和「指对了」
#   是两件事 —— 构建逻辑一旦被改（URL 重写 / 加 UTM / 复制粘贴错行 / 模板串位），
#   数量照样相等，而客户点开的是**另一个国家的法规页**。这种错在页面上完全看不出来，
#   只有把产物 href 与配置 official_url 做等价比对才拦得住。
#   现状虽然是「同一处取值」的结构性保证，但门禁要**验证**不变量，不能靠它「应该没问题」。
_OFFICIAL_A = re.compile(r'<a href="([^"]+)"[^>]*>官方原文 ↗</a>')


def official_hrefs(html):
    """产物里「官方原文 ↗」的 href 多重集（保序）。"""
    return _OFFICIAL_A.findall(html or "")


def official_hrefs_cfg(notes):
    """配置里应当出现的 href 多重集（保序）。"""
    return [n["official_url"] for n in notes if n.get("official_url")]


def month_only(txt):
    """把日期类文本截到**月**粒度：'2026-09-07' → '2026-09'。

    Yoyo 2026-09-23 定：版本条是给客户看的，校验时间这类**内部过程时间**
    只写到月（如 2026-09），不暴露具体日。抽不出年月就原样返回（不猜）。
    """
    m = re.search(r"(\d{4})-(\d{1,2})", txt or "")
    if not m:
        return txt or ""
    return f"{m.group(1)}-{int(m.group(2)):02d}"


def _eff_date(txt):
    """从 effective 字段里抽第一个 ISO 日期 → datetime.date；无则 None。"""
    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", txt or "")
    if not m:
        return None
    try:
        return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def effective_state(effective, asof=None):
    """法规生效状态判定 → 'effective' | 'scheduled' | 'na'（唯一实现）。"""
    d = _eff_date(effective)
    if d is None:
        return "na"
    return "effective" if d <= (asof or datetime.date.today()) else "scheduled"


def effective_badge(note, asof=None):
    """标注块徽标文案：状态徽标 + （可判定时）法规生效状态后缀。"""
    st = note.get("status")
    txt = STATE[st]["badge"]
    es = effective_state(note.get("effective"), asof)
    if st in ("pending", "check") and EFF_TEXT[es]:
        txt += " · " + EFF_TEXT[es]
    return txt


def effective_meta(note, asof=None):
    """「生效日期」字段的展示文案（把判定结果写进页面，肉眼可复核）。"""
    raw = note.get("effective") or "—"
    es = effective_state(raw, asof)
    if es == "na":
        return raw
    return f'{raw}（{EFF_TEXT[es]}）'


def preview_chip(note, asof=None):
    """预览页用的徽标 → (文案, ink, chip_bg, chip_bd)。

    文案 = 页面真值（含「已正式生效 / 计划变更」后缀）——预览脚本**不要**再自己抄一份
    文案常量（2026-09-23 清理：build_preview / build_section_preview 里各有一份
    「⏳ 计划更新」副本，已改成本函数引用，避免文案漂移）。
    """
    c = TONE[tone_of(note, asof)]
    return effective_badge(note, asof), c["ink"], c["chip_bg"], c["chip_bd"]


def version_counts(notes, asof=None):
    """**页面版本条**的计数口径（唯一实现）→ dict。build() 用它渲染，
    validate() / qc_gate.py / release_stage.py 用它核对 —— 口径只在此定义。

    ★ 入参是**配置全量** notes，内部先过 page_notes()（2026-09-23 四轮）：
      版本条是页面元素，客户看到几项就必须数几项 ⇒ 红色（来源存疑）条目
      **不上页面也不进计数**，否则页面会出现「本次标注 6 项」而只看得见 4 块
      —— 这种"数不对"客户一眼就能发现，而门禁反而会把它当成正确值。
      台账要的是全量，故台账不走本函数（见 make_ledger.py）。
    """
    notes = page_notes(notes, asof)
    todo = [n for n in notes if n["status"] in ("pending", "check")]
    return dict(
        n_total=len(notes),
        n_pending=sum(1 for n in notes if n["status"] == "pending"),
        # n_check 恒为 0（check 全部被 page_notes 滤掉了）；保留字段是为了让
        # 「版本条不写『待核 N 项』」这件事**可断言**，而不是靠"恰好没值"。
        n_check=sum(1 for n in notes if n["status"] == "check"),
        n_keep=sum(1 for n in notes if n["status"] == "keep"),
        n_eff=sum(1 for n in todo if effective_state(n.get("effective")) == "effective"),
        n_sch=sum(1 for n in todo if effective_state(n.get("effective")) == "scheduled"))


def version_bar_probe(notes):
    """版本条里**必须出现**的文案片段 → (待更新片段, 已生效片段|None, 计划变更片段|None)。

    计数为 0 的维度返回 None（渲染层同样不写该片段 —— 客户向不该出现「计划变更 0」）。
    """
    c = version_counts(notes)
    p_eff = (f'{EFF_TEXT["effective"]} <strong>{c["n_eff"]}</strong>'
             if c["n_eff"] else None)
    p_sch = (f'{EFF_TEXT["scheduled"]} <strong>{c["n_sch"]}</strong>'
             if c["n_sch"] else None)
    return (f'待更新 <strong>{c["n_pending"]}</strong>', p_eff, p_sch)


def version_bar_dates(c):
    """版本条里的日期片段（客户向：只到月）→ dict(data_year, body_version)。

    ★ 唯一实现（Yoyo 2026-09-23）：「**正文版本**：最新校验时间写到月份，如 2026-09」
      且「**校验时间不显示**」—— 版本条是给客户看的，内部过程时间不进客户视野。
      所以：
        · `body_version` = **最新校验时间**（批次 review_date）的**月**粒度，如 `2026-09`
          —— 取 review_date 而非 page_date：客户关心的是"这版内容何时被核过"，
             不是"原始正文哪天下笔"；两者相差越久，越容易被误读成内容过期。
        · `data_year`    = 同一年份（数据版本年份），与正文版本保持同源、不会自相矛盾。
      页面上**不再出现**「校验时间 / 最新校验 / 校对日期」字样（F 组门禁强制）。

    渲染层与门禁层都调本函数 —— 避免「渲染改了、门禁还在按日校验」的漂移。
    """
    ref = c.get("review_date") or c.get("page_date") or ""
    return dict(data_year=(month_only(ref) or TODAY)[:4],
                body_version=month_only(ref) or month_only(c.get("page_date") or ""))


# ── 前端脆弱 walker 的两条硬约束（2026-09-23 线上事故根因）★ ────────────────────
# 事故：UAE 第 5–12 章「无法加载内容。h2Content为空。」
# 根因：ContentUpdater 内层循环用 indexOf 数 div，闭合后推进 `u = d + 7`，
#       而 "</div>" 只有 **6** 个字符 ⇒ 每次越过 1 个字符。
#       当 `</div>` 后面**紧贴**下一个标签（`</div><div` / `</div></div>`）时，
#       紧贴的那个标签被整条跳过：漏计一次 ⇒ 深度 f 失衡 ⇒ 顶层块提前闭合；
#       前端还有 `if (f > 0) break;` ⇒ **一章错位、后面所有章节一起消失**。
# 约束（所有注入物必须满足；validate() 与 qc_gate.py 都据此阻断）：
#   ① 注入片段内不得出现 `</div><`（标签之间至少留一个非 `<` 字符，如换行）
#   ② 标注块**内部**结构一律不用 <div>（改用 <p>/<span>）——
#      即使平台把空白压掉，div 计数也不会被打乱（结构性免疫，不依赖空白）
WALK_UNSAFE = re.compile(r"</div><")


def harden(html):
    """在 `</div><` 之间补换行，规避前端 naive walker 的 u=d+7 越位跳标签。"""
    return WALK_UNSAFE.sub("</div>\n<", html)


def walk_unsafe_spans(html):
    return [m.start() for m in WALK_UNSAFE.finditer(html)]


# ── 语义档（status → 文案）：badge / label 跟 status 走 ─────────────────────────
STATE = {
    "pending": dict(badge=STATUS_TEXT["pending"], label="拟更新为"),
    "check":   dict(badge=STATUS_TEXT["check"] + "（来源存疑）", label="待核说明"),
    "keep":    dict(badge=STATUS_TEXT["keep"], label="核实结论"),
}

# ── 视觉档（tone → 配色）：颜色跟「变更落地进度」走，**不跟 status 走** ★ 2026-09-23 ──
# 口径演进三次（别只看最后一版，前两版的教训还留着）：
#   v1  颜色 = status 的代理 ⇒ 「无需更新」（keep）也被涂成绿色 —— 绿色被滥用成
#       "内容状态良好"（≈ 打勾通过），客户分不清**有变更已落地**与**本来就没变**。
#   v2  （Yoyo 2026-09-23 上午）绿只留给「今年有变更且已生效」；维持现状 → 中性灰。
#   v3  （Yoyo 2026-09-23 下午，本条生效）**维持不变也标绿** ——
#       原话：「还有继续维持不变，也是绿色」。客户视角下「已核实、无需关注」就是一档，
#       灰反而像"没做完 / 被跳过"。⇒ 绿 = {有变更已生效, 维持不变} 两类合并，
#       **靠徽标文案区分**，不靠颜色：
#         · 有变更且已生效 → `⏳ 待更新 · 已正式生效`（写明改了什么）
#         · 维持不变       → `✅ 无需更新`（写明核过了、没变）
#       所以 `in_force` 与 `no_change` **共用同一份色值 GREEN** —— 不抄两份，
#       改绿只改 GREEN 一处（两份副本必然漏改一处，见「防转述丢失」纪律）。
#     upcoming   待更新 / 变更已定但尚未生效     → 橙黄 （事情还悬着，要关注）
#     verify     来源存疑待核                   → 红   （**不上前端**，只记台账 —— 见 PAGE_HIDDEN_TONES）
# ⚠️ tone 由 tone_of(note) **唯一推导**（status × 生效状态）；渲染层/预览层/门禁
#    一律调它，**任何地方都不许再判一次颜色**，否则改口径必然漏一处。
# ⚠️ 「上不上页面」由 on_page() **唯一推导**（= tone 不在 PAGE_HIDDEN_TONES 里）；
#    同样不许在任何脚本里再判一次 `status == "check"`。
GREEN = dict(bg="#f0fdf4", bd="#bbf7d0", bar="#22c55e", ink="#15803d",
             chip_bg="#dcfce7", chip_bd="#bbf7d0")

TONE = {
    # 两个绿色档：色值同源（dict(GREEN) 是浅拷贝，防止调用方误改共享值）
    "in_force":  dict(GREEN),   # 今年有变更、且已生效
    "no_change": dict(GREEN),   # 维持不变（核实过没变）—— 同色，靠文案区分
    "upcoming":  dict(bg="#fffbeb", bd="#fde68a", bar="#f59e0b", ink="#b45309",
                      chip_bg="#fef3c7", chip_bd="#fcd34d"),
    "verify":    dict(bg="#fef2f2", bd="#fecaca", bar="#ef4444", ink="#b91c1c",
                      chip_bg="#fee2e2", chip_bd="#fecaca"),
}


def tone_of(note, asof=None):
    """标注 → 视觉档（配色唯一推导入口）★

    规则（Yoyo 2026-09-23 定，见 TONE 上方说明）：
      · keep                    → no_change（维持现状 —— **与"已生效的变更"同色，都是绿**）
      · check                   → verify   （来源存疑，红 —— **该条不上页面**，见 on_page()）
      · pending + 生效日已到     → in_force （今年有变更且已落地 → 绿）
      · 其余 pending（计划变更 / 生效日待定）→ upcoming（橙黄）

    两个绿色档的**区别只在文案**（`✅ 无需更新` vs `⏳ 待更新 · 已正式生效`），
    颜色刻意不做区分 —— 客户要一眼看到的是「哪一章还要关注」（橙黄）。
    tone 值本身仍然保留两份：台账与 `data-cg-tone` 属性需要区分
    「改过且已生效」与「核过没变」，只是它们现在指向同一组色值。
    `verify` 这一档虽然不在页面上出现，但**仍必须推导出来** —— 台账靠它分流「待处理」。
    """
    st = note.get("status")
    if st == "keep":
        return "no_change"
    if st == "check":
        return "verify"
    return ("in_force" if effective_state(note.get("effective"), asof) == "effective"
            else "upcoming")


def section_tone(notes, asof=None):
    """一章多标注时的章节配色（h2 徽标 / 目录气泡共用，唯一实现）。

    规则：多状态并存时取**最先要处理的那一档** —— 待更新 > 待核 > 无需更新
    （沿用 2026-09-23 前的既有优先级，别顺手改；徽标文字里本来就写着全部计数）。
    其中「待更新」的绿/橙只在**该章所有待更新项都已生效**时才给绿 ——
    只要还有一条未生效，整章标橙黄（绿 = 这一章的变更全落地了，别让一条未生效的藏进去）。
    「无需更新」章现在也返回绿（`no_change` 与 `in_force` 同色，见 TONE 说明）。
    """
    if any(n.get("status") == "pending" for n in notes):
        ups = [tone_of(n, asof) for n in notes if n.get("status") == "pending"]
        return "in_force" if all(t == "in_force" for t in ups) else "upcoming"
    if any(n.get("status") == "check" for n in notes):
        return "verify"
    return "no_change"


# ── 页面可见性：红色「来源存疑」**先不上前端**（Yoyo 2026-09-23 四轮定）★ ──────
# 原话：「红色 存疑 先不在前端展示，记录台账待处理」。
# 为什么（客户向）：页面读者是出海中企 HR —— 他既无从核实「来源存疑」到底指什么，
#   也不知道该不该照着做；把这一块摆到页面上，等于把我方的**核对过程**暴露给客户，
#   而客户要的是结论（"这条改没改、什么时候生效"）。
# ⇒ **页面只出现两类颜色**：绿（不用管）与 橙黄（计划变更未落地）。
#   存疑条目 → 不注入页面，只在飞书台账留档为「⚠️ 待核 · 页面上/否=待处理」；
#   等补齐一手源后再走一次落线，那时它会以绿 / 橙黄的身份回到页面。
#
# ★ 唯一判定入口：任何地方要问「这条上不上页面」都必须调 on_page()，
#   不许在 build / qc / verify / preview / ledger 各写一遍 `status == "check"`
#   —— 那就是 N 份副本，改口径必然漏一处（本项目已复发过多次）。
#
# ★ 连带口径（同一次收口，别漏）：**外链门禁只验「客户会点开的链接」**。
#   L4 / L5 / L9 的取数基数一并改为 page_notes —— 不上页面的条目，其链接客户点不到，
#   再要求人工点验就是无谓的闸门（UAE 的 gpssa.gov.ae 正属此类）。
PAGE_HIDDEN_TONES = ("verify",)


def on_page(note, asof=None):
    """该标注是否注入页面（**唯一**判定入口）。"""
    return tone_of(note, asof) not in PAGE_HIDDEN_TONES


def page_notes(notes, asof=None):
    """页面上真实出现的标注（保序）—— 页面侧一切计数/门禁都比对它。"""
    return [n for n in notes if on_page(n, asof)]


def hidden_notes(notes, asof=None):
    """不上页面的标注（台账「待处理」那一档）—— 保序，供台账/预览分流。"""
    return [n for n in notes if not on_page(n, asof)]


def page_visibility(note, asof=None):
    """台账用：「页面展示」列取值。"""
    return "是" if on_page(note, asof) else "否 —— 来源存疑，仅台账待处理"


def _badge_css():
    """章节徽标样式块 —— 配色**从 TONE 生成**（不手抄色值，改配色只改 TONE 一处）。

    ★ 跳过 PAGE_HIDDEN_TONES（红色）：页面上永远不会有红色徽标（那类条目整条不上页面），
      生成它的规则就是死样式。**顺带**让「产物里 grep 不到 data-cg-tone="verify"」
      成为一句可以直接用的断言 —— 否则每条产品里都躺着这串字符（只是躺在 <style> 里），
      谁想用 grep 复核都得先想到"要剥样式"，早晚有人忘。
    """
    base = ('.nrz h2.section-title[data-cg-badge]::after{content:attr(data-cg-badge);'
            'display:inline-block;margin-left:10px;padding:2px 10px;border-radius:999px;'
            'font-size:12px;font-weight:600;line-height:1.7;vertical-align:middle;'
            'white-space:nowrap;')
    d = TONE["upcoming"]
    out = [base + f'background:{d["chip_bg"]};color:{d["ink"]};border:1px solid {d["chip_bd"]};}}']
    for t in TONE:   # 无 data-cg-tone 时走上面的默认档（橙黄），保持旧产物可读
        if t in PAGE_HIDDEN_TONES:
            continue
        c = TONE[t]
        out.append(f'.nrz h2.section-title[data-cg-tone="{t}"]::after'
                   f'{{background:{c["chip_bg"]};color:{c["ink"]};'
                   f'border:1px solid {c["chip_bd"]};}}')
    return "<style>\n" + "\n".join(out) + "\n</style>"


# 章节徽标：伪元素生成内容，属性值不进 textContent → 不污染前端 TOC
BADGE_CSS = _badge_css()

NZ = '<div class="nrz">'
MC = '<div class="main-container">'

# ── 左侧目录「小气泡数字」（2026-09-22 新增，读前端源码后确定）─────────────────
# 前端 TableOfContents 组件（/assets/TableOfContents.*.js）把整篇 content 当**字符串**收进去，
# 自己用 /<h2[^>]*>([\s\S]*?)<\/h2>/gi 扫出章节，并且 `text = 剥掉所有标签后的纯文本`：
#     const h = i[1].replace(/<[^>]*>/g, "").trim();
#     r.push({ id: `heading-${d}`, text: h })      // d 从 0 全局递增
# 渲染时只输出 [纯文本, " ", 是否当前] —— **没有 data 属性、没有插槽、没有状态字段**。
# 推论（决定实现方式，别再走弯路）：
#   · 往 h2 里塞 <span> 做气泡 —— 无效：标签被剥掉，目录里只会多出一串裸文本
#   · 靠 h2 的 ::after 徽标透传 —— 无效：伪元素不进 textContent，目录天然看不见
#   · 改 TOC 组件的 props —— 前端只收到 content/className，没有可传状态的口子
#   ⇒ 唯一可行的挂载点 = **CSS 选择器 `a[href="#heading-N"]` 的 ::after**。
#     content 内注入的 <style> 在页面上是**全局生效**的（章节徽标即证据），
#     所以一段目录气泡 CSS 就能打到左侧目录上，且不碰 DOM、不碰文本。
#   ⚠️ N 是「content 里所有 h2」的全局序号，不是 content-section 序号；
#     两者当前恰好相等（12/12），但规则不同 —— 用 toc_index_map() 严格复刻，别用 _sec_idx。
#
# ── 第二个坑：平台会**自动给 <style> 里的规则加 `.article-isolate ` 作用域前缀** ★★ ──
# 平台（PostCSS 作用域插件）在落库/渲染时把 `.table-of-contents a[href=...]::before{...}`
# 改写成 `.article-isolate .table-of-contents a[href=...]::before{...}`。
# 而左侧目录挂在 `<aside id="toc-container">` 里、在文章内容容器**外面**
# ⇒ 前缀一加，选择器永远命不中，线上表现是「样式块明明在、气泡一个都不出现」。
# 实测（2026-09-22，用不存在的选择器做零影响探测）确认：
#   · 会被加前缀：类开头 / 元素开头 / 属性开头 / 通配开头 / `:root` 开头；
#     连 `@media` `@layer` `@supports` **块内**的规则也照样递归加
#   · **不会**被加前缀：`@scope` 块内**以元素选择器开头**的规则（原样放行）★
#     （同块内以类开头的规则仍会被加）
# ⇒ 唯一可行写法 = 用 `@scope (.table-of-contents)` 圈住作用域根，内部只用元素选择器 `a[href=...]`。
#   这样还能顺带把选择器限制在目录内（`.article-isolate` 里若也有 `a[href="#heading-N"]` 也不会误伤）。
TOC_SCOPE = "@scope (.table-of-contents)"
TOC_SEL = 'a[href="#heading-'   # @scope 内的选择器主体；content 里只有本处会出现这个串

# ── 两个平台行为（2026-09-22 阿联酋实测，别再踩） ───────────────────────────
# 1) content 落库时，平台会给 <style> 里的选择器注入 `.article-isolate ` 作用域前缀（+93 字节）。
#    ⇒ 回查不能直接比 sha，必须先剥掉 <style> 再比。否则 forever False（假阴性）。
# 2) **previewContent 是平台从 content 派生的，PUT 上去的值会被忽略**（未登录预览 = content 截断）。
#    实测证据：提交 7,407 字节的预览 → 存回 6,621 字节，且存回值逐字节等于 content 的前缀，
#    而不是提交串的前缀；两次 apply 提交完全不同的预览、content 相同 → 存回值也完全相同。
#    ⇒ 任何"把 previewContent 改小/改干净"的做法都是假修复，不要再写。
#    ⇒ 派生截断点固定落在 content 约 6.5KB 字节处，恰好切在《国家核心信息速查表》中间，
#      产生 `...首都</s` 这类半截标签 —— 这是**平台侧缺陷**，我们改不了，只能上报。


def strip_style(s):
    """剥掉 <style> 块 —— 用于规避平台注入的作用域前缀差异。"""
    return re.sub(r"<style[^>]*>.*?</style>", "", s, flags=re.S)


# ── 注入物识别 / 摘除（唯一实现；qc_gate 与 verify_secondary 都调这里）───────────
def note_blocks(after):
    """切出产物里的标注块（render_note 结尾固定 `\\n</div>`，块内无 <div> 故不会误切）。"""
    return re.findall(r'<div class="cg-update-note"[\s\S]*?\n</div>', after)


def urls_in(block):
    return re.findall(r'href="(https?://[^"]+)"', block)


def canonical(html):
    """逐行 strip + 丢空行 —— 忽略注入产生的空白差异后比对正文。"""
    return "\n".join(l.strip() for l in html.splitlines() if l.strip())


def strip_injections(html):
    """摘除本技能注入的全部内容，还原出「正文」。用于证明正文零改动 / 二次校验。

    注入物清单（与 build() 一一对应，改 build 必须同步改这里）：
      · <div class="cg-update-note">…</div>                标注块
      · <div class="cg-version-bar">…</div>                数据版本条
      · <style>…</style>                                   徽标样式块 / 目录气泡样式块
      · h2 上的 data-cg-badge / data-cg-state / data-cg-tone 章节徽标属性
    """
    out = html
    for cls in ("cg-update-note", "cg-version-bar"):
        pat = re.compile(r'<div class="%s"[^>]*>' % cls)
        while True:
            m = pat.search(out)
            if not m:
                break
            e = _balanced_end(out, m.start())
            if e < 0:
                break
            out = out[:m.start()] + out[e:]
    out = strip_style(out)
    out = re.sub(r' data-cg-badge="[^"]*"', "", out)
    out = re.sub(r' data-cg-state="[^"]*"', "", out)
    out = re.sub(r' data-cg-tone="[^"]*"', "", out)
    return out


# ── 申报式正文修复（唯一实现）──────────────────────────────────────────────────
# 「正文零改动」的真实目标是**不偷偷改内容**，而不是"正文里天塌了也不许碰"。
# 当正文本身带结构性缺陷（配图域名写错、链接指向失效域名…），落标时一并修掉是对的；
# 但必须**申报**：逐条登记 find / replace / 依据 / 证据，由门禁逐条核对
# 「说过的改了没有、没说过的动了没有」。⇒ 门禁口径精确为「零**未申报**改动」。
#
# ⚠️ 三条纪律（踩过坑的）：
#   ① **修复不单独成信道** —— 它不是新的写入路径，只是 build 里比注入更早的一步；
#      产物仍是"基线 → 申报修复 → 注入物"这一条链，没有第二条路能改正文。
#   ② **比对基准侧套修复、产物侧不套**（见 baseline_body / candidate_body）——
#      若两侧都套，就会出现"申报了修复但产物里没生效"被判相等的**假通过**。
#   ③ 注册表是**唯一真相源**：改修复只改 references/body-fixes.json，脚本里不许写死。
_BODY_FIXES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "references", "body-fixes.json")
BODY_FIX_FIELDS = ["id", "slug", "find", "replace", "why", "evidence", "owner", "found_at"]


def load_body_fixes():
    """读注册表 → list[dict]。文件不存在 ⇒ []（等价于"本批无申报修复"）。"""
    if not os.path.exists(_BODY_FIXES_PATH):
        return []
    d = json.load(open(_BODY_FIXES_PATH, encoding="utf-8")) or {}
    return d.get("fixes") or []


def body_fixes_missing_fields(fixes=None):
    """注册表自检 → [(id, [缺的字段…])]。字段不齐的条目一律要被门禁拦下。"""
    out = []
    for f in (fixes if fixes is not None else load_body_fixes()):
        miss = [k for k in BODY_FIX_FIELDS if not str(f.get(k) or "").strip()]
        if miss:
            out.append((f.get("id") or "(无 id)", miss))
    return out


def body_fixes_for(slug, fixes=None):
    """取某国适用的申报修复。**按 slug 精确匹配**（不写通配 —— 防"一条修复摊到全站"）。"""
    if not slug:
        return []
    return [f for f in (fixes if fixes is not None else load_body_fixes())
            if f.get("slug") == slug]


def apply_body_fixes(html, slug=None, fixes=None):
    """套用申报修复 → (html, [生效的 id…])。slug 为空 ⇒ 原样返回（宁可漏修，不可误修）。"""
    applied = []
    for f in body_fixes_for(slug, fixes):
        if f["find"] in html:
            html = html.replace(f["find"], f["replace"])
            applied.append(f["id"])
    return html, applied


def undo_body_fixes(html, slug=None, fixes=None):
    """把申报修复**反向**撤回（find/replace 互换）—— residual_check 要用。"""
    rev = [dict(f, find=f["replace"], replace=f["find"]) for f in body_fixes_for(slug, fixes)]
    return apply_body_fixes(html, slug, rev)[0]


def audit_body_fixes(html, slug=None, fixes=None):
    """逐条核对申报是否真生效 → [dict(id, ok, msg)]。
    判据两条同时成立才算生效：① 产物里 find 已无残留 ② replace 已出现。"""
    rows = []
    for f in body_fixes_for(slug, fixes):
        left, has = html.count(f["find"]), (f["replace"] in html)
        ok = (left == 0 and has)
        rows.append(dict(id=f["id"], ok=ok,
                         msg="已生效" if ok else
                         f"未生效（find 残留 {left} 处；replace {'已出现' if has else '未出现'}）"))
    return rows


def orphan_body_fixes(slug, before, fixes=None):
    """申报了但**在基线里根本没命中**的条目 → [id…]。
    典型成因：基线更新过（缺陷已被别人修掉）/ find 串写错。门禁按"过期申报"告警。"""
    return [f["id"] for f in body_fixes_for(slug, fixes) if f["find"] not in (before or "")]


def baseline_body(before, slug=None, fixes=None):
    """**比对基准**正文 = 基线摘除注入物 + 套用申报修复。

    与 candidate_body 成对使用：两者相等 ⇒ 产物相对基线的**全部**改动恰好就是申报的那些。
    """
    return canonical(apply_body_fixes(strip_injections(before), slug, fixes)[0])


def candidate_body(after):
    """**产物**正文 = 摘除注入物（**刻意不套**申报修复）。

    为什么不套：若申报了修复、产物里却没落进去，两侧就仍不等 ⇒ 拦住"申报了却没做"。
    反过来若两侧都套，这种情形会被判成相等 —— 那是**假通过**，比漏拦更糟。
    """
    return canonical(strip_injections(after))


# ── 链接域名判定（唯一实现）────────────────────────────────────────────────────
# 规则真相源 = ../references/official-domains.json（Yoyo 2026-09-22 修订：标注块链接两分法 ——
# 站外只放官方原文，站内解读/知识库/报告/工具入口必须指向品牌自有域名）。改名单只改那个 JSON。
_DOMAINS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "..", "references", "official-domains.json")
_DOMAINS = json.load(open(_DOMAINS_PATH, encoding="utf-8"))


def host_of(url):
    """取 URL 主机名（小写、去 www.、去端口）。非 http(s) 或无主机返回 ""。"""
    m = re.match(r"https?://([^/?#]+)", url or "", re.I)
    if not m:
        return ""
    h = m.group(1).split("@")[-1].split(":")[0].lower().strip(".")
    return h[4:] if h.startswith("www.") else h


def classify_source(url):
    """按白名单判源 → (verdict, host)。verdict ∈ {official, internal, third_party, unknown}。

    判定顺序：先查三方黑名单（防名字带 gov 的三方站被误判）→ 再判官方
    （gov 系列 label / 各国政府二级后缀 / 显式官方门户清单）→ 再判站内品牌域名
    （humancehr.com / anchorwe.com 及其子域）→ 都不命中 = unknown
    （**默认阻断**，确认是官方/站内后把域名加进对应清单再放行）。
    """
    h = host_of(url)
    if not h:
        return "unknown", ""

    def hit(d):
        return h == d or h.endswith("." + d)

    for d in _DOMAINS["third_party_domains"]:
        if hit(d):
            return "third_party", h
    if any(lbl in _DOMAINS["official_host_labels"] for lbl in h.split(".")):
        return "official", h
    if any(h.endswith(sfx) for sfx in _DOMAINS["official_tld_suffixes"]):
        return "official", h
    for d in _DOMAINS["official_domains"]:
        if hit(d):
            return "official", h
    for d in _DOMAINS["internal_domains"]:
        if hit(d):
            return "internal", h
    return "unknown", h


def sha16(s):
    """产物指纹（16 位）。构建报告 / 暂存清单 / 发布门禁共用一处实现。"""
    import hashlib
    return hashlib.sha256(s.encode()).hexdigest()[:16]


def guide_url(slug, fallback_anchor="国家概况"):
    """国别指南页 URL（唯一实现）。配置里有 guide_url 就用配置的，缺了按此兜底。"""
    return f"https://www.humancehr.com/country-guide/{slug}/{fallback_anchor}"


def verify_content(remote, local):
    """落标回查：remote 是 GET 回来的 content。返回 (是否等价, 说明)。"""
    if remote == local:
        return True, "逐字节一致"
    if strip_style(remote) == strip_style(local):
        return True, "等价（仅 <style> 被平台注入 .article-isolate 作用域前缀）"
    return False, f"不一致（remote {len(remote)} 字符 vs 本地 {len(local)}）"


def preview_truncation_clean(pv):
    """检查平台派生预览的截断点是否落在标签边界。返回 (是否干净, 截断处片段)。"""
    body = re.sub(r"(?:</\w+>)+$", "", pv)
    return body.rstrip().endswith(">"), body[-46:]


# ── 前端渲染模型（2026-09-22 读源码后确认，这是本技能最重要的一条约束） ─────────────
# 国别指南详情页 **不是一次性渲染整篇**，而是"按章节分页渲染"：
#   1) 页面把目录里的每个章节做成独立 URL（…/国家概况、…/薪酬支付 …，共 12 个）
#   2) 前端组件 SafeHtmlRenderer / ContentUpdater 拿到整篇 content 后，只做：
#        a. 定位 `<div class="main-container">`，取它的**顶层子 div** 列表
#        b. 取其中第一个 <h2> 文本 == 当前章节名 的那个 content-section
#        c. 套进一段**硬编码骨架**后 innerHTML 渲染
#   3) 骨架 = <head>(仅 3 个外链 CSS) + `<div class="nrz"><div class="main-container">` + 该章节 + 收尾
#      ⇒ 骨架里**没有**我们注入的 <style>，也**没有**挂在 main-container 顶层的任何元素。
# 结论（血泪）：
#   · 注入到 `.nrz` 下 / `main-container` 顶层的元素 —— **一律不会显示**（版本条曾被此处吞掉）
#   · 依赖注入 <style> 的样式 —— **不生效**（章节徽标曾被此处吞掉）
#   · 只有"在 content-section **内部**、且用**内联样式**"的元素才真正可见 → 标注块、版本条、徽标样式块都必须塞进章节内
FE_HEAD = (
    '<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n    <meta charset="UTF-8">\n'
    '    <meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
    '    <title>国别指南</title>\n'
    '    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">\n'
    '    <link href="https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@400;500;600;700'
    '&family=Nunito+Sans:wght@300;400;500;600;700&display=swap" rel="stylesheet">\n'
    '    <link rel="stylesheet" href="https://dev-gpt.anchorwe.com/anchorai/css/blue.css">\n'
    '</head>\n<div class="nrz">\n  <div class="main-container">\n\n'
)
SEC = '<div class="content-section">'


def _balanced_end(s, start):
    """s[start] 处是 <div，返回配平的 </div> 结束位置（不含）。"""
    depth = 0
    for m in re.finditer(r"<div\b[^>]*>|</div>", s[start:]):
        depth += -1 if m.group(0).startswith("</") else 1
        if depth == 0:
            return start + m.end()
    return -1


def _main_inner(html):
    m = re.search(r'<div class="main-container"[^>]*>', html)
    if not m:
        return None
    e = _balanced_end(html, m.start())
    return html[m.end():e - len("</div>")] if e > 0 else None


def _top_level_divs(inner):
    """复刻前端 walker：按层级切出 inner 的顶层 <div> 块。"""
    out, t = [], 0
    while t < len(inner):
        t += len(re.match(r"\s*", inner[t:]).group(0))
        if inner[t:t + 4].lower() != "<div":
            t += 1
            continue
        g = inner.find(">", t)
        if g == -1:
            break
        if inner[t:g + 1].endswith("/>"):
            t = g + 1
            continue
        e = _balanced_end(inner, t)
        if e == -1:
            break
        out.append((t, e, inner[t:e]))
        t = e
    return out


def simulate_frontend_section(content, h2_title):
    """复刻前端"分章渲染"结果：给定章节名，返回前端实际会渲染出的 HTML。找不到返回 None。"""
    inner = _main_inner(content)
    if inner is None:
        return None
    tgt = h2_title.strip().lower()
    for _s, _e, full in _top_level_divs(inner):
        h = re.search(r"<h2[^>]*>([\s\S]*?)</h2>", full, re.I)
        if not h:
            continue
        t = re.sub(r"<[^>]+>", "", h.group(1)).strip().lower()
        if t == tgt or (t and (t in tgt or tgt in t)):
            return FE_HEAD + full.strip() + "\n\n\n\n  </div>\n</div>\n\n</html>"
    return None


def frontend_blocks(content):
    """忠实复刻前端 ContentUpdater 的顶层块发现算法 → [(块 HTML, h2 纯文本|None)]。

    ⚠️ 与 _top_level_divs 是**两套**东西，别混用：
      · _top_level_divs = 正则 + 配平（正确解析），用于本地构建/预览
      · frontend_blocks = **刻意复刻前端的朴素 indexOf 实现**（含 u=d+7 越位、
        大小写敏感、不识别 <style>），用于「上线门禁」——
        它数出来的章节数 == 线上真正能显示的章节数，是唯一可信判据。

    返回列表长度 < 章节数 ⇒ 线上必然有章节报「h2Content为空」，必须阻断落线。
    """
    m = re.search(r'<div class="main-container"[^>]*>', content, re.I)
    if not m:
        return []
    n = content[m.end():]
    raw, t = [], 0
    while t < len(n):
        t += len(re.match(r"\s*", n[t:]).group(0))
        if n[t:t + 4].lower() != "<div":
            t += 1
            continue
        g = n.find(">", t)
        if g == -1:
            break
        if n[t:g + 1].endswith("/>"):
            t = g + 1
            continue
        f, u, closed = 1, g + 1, False
        while u < len(n) and f > 0:
            v = n.find("<div", u)
            d = n.find("</div>", u)
            if d == -1:
                break
            if v != -1 and v < d:
                f += 1
                u = v + 4
            else:
                f -= 1
                if f == 0:
                    raw.append(n[t:d + 7])
                    t = d + 7
                    closed = True
                    break
                u = d + 7
        if not closed:          # 对应前端 `if (f > 0) break;` —— 后续章节全灭
            break
    out = []
    for blk in raw:
        h = re.search(r"<h2[^>]*>([\s\S]*?)</h2>", blk, re.I)
        out.append((blk, re.sub(r"<[^>]+>", "", h.group(1)).strip() if h else None))
    return out


def frontend_visible_sections(content):
    """前端真正能渲染出内容的章节名列表（按文档顺序，去 None）。"""
    return [t for _b, t in frontend_blocks(content) if t]


# ---------------------------------------------------------------- 渲染
def _chip(tone, text):
    """胶囊徽标 —— 配色按 **tone**（变更落地进度），不按 status（见 TONE 说明）。"""
    c = TONE[tone]
    return (f'<span style="display:inline-block;padding:2px 10px;border-radius:999px;'
            f'background:{c["chip_bg"]};color:{c["ink"]};border:1px solid {c["chip_bd"]};'
            f'font-size:12px;font-weight:600;line-height:1.7;">{text}</span>')


def render_note(n):
    """渲染单条标注块。n: dict(status,title,old,new,effective,source,tier,url,rid,extra)

    ⚠️ 硬约束（2026-09-23 线上事故）：块**内部**一律不用 <div>，只用 <p>/<span>/<strong>/<a>。
    整个标注块对前端 walker 只呈现 **1 开 1 闭** 的 div —— 即使平台把标签之间的空白
    压掉，也不会出现 `</div><div` 触发 u=d+7 越位跳标签（见 WALK_UNSAFE 说明）。
    """
    st = n["status"]
    sc = STATE[st]          # 语义：徽标文案 / 新值行标签（拟更新为 / 核实结论 …）
    tn = tone_of(n)         # 视觉：整块配色（见 TONE）
    c = TONE[tn]
    es = effective_state(n.get("effective"))
    badge = _chip(tn, effective_badge(n))

    parts = [f'<p style="margin:0 0 9px;display:flex;align-items:center;gap:9px;flex-wrap:wrap;">'
             f'{badge}<strong style="color:{INK};font-size:14px;">{n["title"]}</strong></p>']

    if n.get("old"):
        # pending 用删除线表达「从…变成…」；keep/check 不加删除线（值并未被替换）
        strike = ("text-decoration:line-through;text-decoration-color:#a1a1aa;"
                  if st == "pending" else "")
        parts.append(f'<p style="margin:0 0 5px;"><span style="color:{INK3};font-size:12.5px;">现行：</span>'
                     f'<span style="color:{INK2};{strike}">{n["old"]}</span></p>')
    if n.get("new"):
        ink = BRAND if st == "pending" else c["ink"]
        parts.append(f'<p style="margin:0 0 5px;"><span style="color:{INK3};font-size:12.5px;">'
                     f'{sc["label"]}：</span><strong style="color:{ink};">{n["new"]}</strong></p>')

    meta = [f'生效日期 <strong style="color:{INK2};">{effective_meta(n)}</strong>',
            f'来源：{n.get("source") or "—"}（{n.get("tier") or "—"}）']
    # 链接两分法（Yoyo 2026-09-22 修订）：
    #  · 站外只放「官方原文 ↗」（official_url，必为官方一手源；QC 强制 official）
    #  · 站内放「解读：… ↗」（interpret_url，必为 humancehr.com/anchorwe.com；QC 强制 internal）
    #  · 原引（url/orig_source）只留档在批次配置与飞书台账，不进页面
    lnk = f'style="color:{BRAND};text-decoration:none;"'
    if n.get("official_url"):
        meta.append(f'<a href="{n["official_url"]}" target="_blank" rel="noopener" {lnk}>官方原文 ↗</a>')
    # 解读：站内深度解读（知识库 / 法规库 / 报告），必须指向品牌自有域名。无则不渲染。
    if n.get("interpret_url"):
        ititle = n.get("interpret_title") or "深度解读"
        meta.append(f'解读：<a href="{n["interpret_url"]}" target="_blank" rel="noopener" {lnk}>{ititle} ↗</a>')
    # ★★ 2026-09-23 Yoyo 定：三个**内部过程字段撤出页面**，只留飞书台账：
    #    「标注写入时间」→ 台账「更新时间(标注写入)」；「校对ID」→ 台账「校对ID」；
    #    「页面位置」   → 台账「落位章节」。
    #    理由：客户（出海中企 HR）看的是「来源 + 官方原文 + 生效日期」，
    #    内部流水号、写入时间、以及"这块挂在哪一章"对他没有信息价值，
    #    反而像"还没写完的草稿"（而且块本身就长在那一章里，位置是自明的）。
    #    ⚠️ 定位能力不能丢 —— 机器定位改走 **属性**（见下方 div 的 data-cg-rid /
    #    data-cg-anchor）：属性不进 textContent、渲染不可见，但迁移/回查/台账回写照旧能用。
    #    门禁 F4（qc_gate 与 validate 双处）+ S13 保证它们不会回流到页面。
    parts.append(f'<p style="margin:9px 0 0;padding-top:8px;border-top:1px dashed #e4e4e7;'
                 f'color:{INK3};font-size:12.5px;">{" ｜ ".join(meta)}</p>')

    # 工具入口：站内工具（合规自检 / JD 生成 / 薪酬测算等），每条必为 internal 域名。
    # 渲染为胶囊按钮，与信息行区隔；每标注块建议 ≤2 个（详见 spec §12.7）。
    entries = [e for e in (n.get("tool_entries") or []) if e.get("url")]
    if entries:
        btns = "".join(
            f'<a href="{e["url"]}" target="_blank" rel="noopener" title="{e.get("tip") or ""}" '
            f'style="display:inline-block;margin:6px 6px 0 0;padding:4px 12px;'
            f'border:1px solid {BRAND};border-radius:999px;color:{BRAND};'
            f'background:#f5f9ff;font-size:12.5px;font-weight:600;line-height:1.6;text-decoration:none;">'
            f'🛠 {e.get("label") or "工具"} ↗</a>' for e in entries)
        parts.append(f'<p style="margin:9px 0 0;padding-top:8px;border-top:1px dashed #e4e4e7;">'
                     f'<span style="color:{INK3};font-size:12px;margin-right:2px;">相关工具：</span>'
                     f'{btns}</p>')

    if n.get("extra"):
        parts.append(f'<p style="margin:6px 0 0;color:{INK2};font-size:12.5px;">{n["extra"]}</p>')

    return harden(
        f'\n<div class="cg-update-note" data-cg-rid="{n["rid"]}" data-cg-status="{st}"'
        f' data-cg-tone="{tn}" data-cg-eff="{es}" data-cg-effective="{n.get("effective") or ""}"'
        f' data-cg-anchor="{n.get("anchor_title") or ""}"'
        f' style="margin:18px 0 22px;padding:14px 18px;'
        f'background:{c["bg"]};border:1px solid {c["bd"]};border-left:4px solid {c["bar"]};'
        f'border-radius:8px;font-size:13.5px;line-height:1.75;">\n'
        + "\n".join(parts) + '\n</div>\n')


def render_version_bar(c):
    """页头数据版本条。c: dict(page_date, review_date, batch, n_total, n_pending, n_keep, n_check)

    ★ 客户向口径（Yoyo 2026-09-23）：「写这个是给客户看的」——
      · 状态备注用**客户语言**：EFF_TEXT（已正式生效 / 计划变更）
      · 「正文版本」= **最新校验时间的月粒度**（2026-09），不写具体日
      · **校验时间不显示** —— 没有「校验时间 / 最新校验 / 校对日期」这类内部过程时间
      · 「数据版本」年份与正文版本同源（version_bar_dates()），不写死年份
    """
    parts = [f'{STATUS_TEXT["pending"]} <strong>{c["n_pending"]}</strong> 项']
    # 「已正式生效 / 计划变更」拆分（Yoyo 2026-09-23）：口径见 effective_state()。
    # 只对「待更新/待核」计数，且仅统计能判定日期的条目 —— 维持现行类不计入；
    # 计数为 0 的维度**不写**（客户向不该出现「计划变更 0」）。
    if c.get("n_eff") or c.get("n_sch"):
        sp = []
        if c.get("n_eff"):
            sp.append(f'{EFF_TEXT["effective"]} <strong>{c["n_eff"]}</strong>')
        if c.get("n_sch"):
            sp.append(f'{EFF_TEXT["scheduled"]} <strong>{c["n_sch"]}</strong>')
        parts.append("其中 " + " · ".join(sp))
    # ⚠️ 这里**故意没有**「⚠️ 待核 N 项」这一段（2026-09-23 四轮撤除）★
    #    红色（来源存疑）不上前端 ⇒ 版本条也不得提它。
    #    否则客户看到「待核 2 项」却在页面上找不到任何对应内容（那两块没渲染），
    #    只会以为页面坏了。c["n_check"] 在 version_counts 里已恒为 0，此处不再写分支
    #    （留着"永远不执行"的分支 = 下次有人看到它以为这是一条活路径）。
    parts.append(f'{STATUS_TEXT["keep"]} <strong>{c["n_keep"]}</strong> 项')
    dm = version_bar_dates(c)
    return harden(
        '\n<div class="cg-version-bar" style="margin:0 0 22px;padding:12px 18px;background:#f5f9ff;'
        'border:1px solid #cfe0f5;border-left:4px solid ' + BRAND + ';'
        'border-radius:8px;font-size:13px;color:' + TITLE_INK + ';line-height:1.75;">\n'
        f'  数据版本：<strong>截至 {dm["data_year"]} 年</strong> ｜ '
        f'正文版本：<strong>{dm["body_version"]}</strong> ｜ '
        f'本次标注：<strong>{c["n_total"]} 项</strong>（{" · ".join(parts)}）\n</div>\n')
    # ⚠️ 「校对批次 B2-01-T-migrate」2026-09-23 撤出页面（Yoyo 截图红框圈出）★
    #    理由同 F4 那一类：它是我方**生产工单号**，客户无从理解；
    #    尤其 `-migrate` 这类后缀是迁移动作的内部标记，露出来像"半成品"。
    #    定位能力不丢：批次留在**飞书台账**的批次列，页面侧走 `data-cg-rid` 属性。
    #    防回流：`INTERNAL_FIELDS` 已收录「校对批次」，F4（qc/validate）+ S13 三处门禁会拦。


def toc_index_map(content):
    """复刻前端 TableOfContents 的章节提取规则 → {h2 纯文本: TOC 序号}。

    前端源码逐字对应：
        /<h2[^>]*>([\\s\\S]*?)<\\/h2>/gi  →  replace(/<[^>]*>/g,"")  →  trim()  →  非空才计数
    注意三点（都与 _section_map 不同，混用就会挂错章节）：
      1. 匹配**所有** <h2>，不限 class="section-title"
      2. 剥标签后再 trim，空串跳过（且不占序号）
      3. 序号从 0 起，按文档顺序全局递增
    同名 h2 取首次出现的序号（前端会渲染成两个同名目录项，但气泡只需挂第一个）。
    """
    out, d = {}, 0
    for m in re.finditer(r"<h2[^>]*>([\s\S]*?)</h2>", content, re.I):
        t = re.sub(r"<[^>]*>", "", m.group(1)).strip()
        if t:
            out.setdefault(t, d)
            d += 1
    return out


def render_toc_badge_css(stats):
    """左侧目录「小气泡数字」样式。stats: [dict(heading_idx, total, state)]

    设计（180px 窄侧栏真渲染实测，三个坑都踩过）：
      · 挂 **`::before`** 而不是 `::after` —— 侧栏只有 160~180px，最长项「外企本地化与签证管理」
        约 140px，加气泡后必然折行。`::after` 的源流位置在文本**之后** → 气泡被挤到第二行
        悬在文字下方（实测截图确认，很难看）；`::before` 在文本**之前**，float 先占第一行
        右侧，文本自动避让 → 气泡永远锁在第一行右侧。
      · **`float:right`** 而不是 inline 跟随 —— inline 会让气泡整体掉到下一行；
        float 不参与文本流，短标题一行不变，长标题只让文本折行、气泡不受影响。
      · 16px 圆 + 10px 字，1 位数字正方形、2 位数字转胶囊；配色复用 TONE（与章节徽标同源）
      · 一章多状态时：数字 = 总项数，颜色 = section_tone() 推出来的那一档
        （待更新 > 待核 > 无需更新；该章待更新项**全部已生效**才给绿）
      · 整块必须包在 `@scope (.table-of-contents)` 里，内部只用元素选择器 —— 见常量区的说明，
        不这么写就会被平台加 `.article-isolate` 前缀、在左侧目录上彻底失效。
    返回空串表示无更新（不加任何样式）。
    """
    if not stats:
        return ""
    rules = []
    for s in stats:
        c = TONE[s["tone"]]
        rules.append(
            f'{TOC_SEL}{s["heading_idx"]}"]::before'
            f'{{content:"{s["total"]}";float:right;margin:2px 0 0 6px;min-width:16px;height:16px;'
            f'line-height:14px;padding:0 4px;border-radius:999px;font-size:10px;font-weight:700;'
            f'font-style:normal;text-align:center;box-sizing:border-box;'
            f'background:{c["chip_bg"]};color:{c["ink"]};border:1px solid {c["chip_bd"]};}}')
    # 结尾**不带**换行：build() 里按 "\n" + toc_css 追加，这样它是可整体摘除的原子串
    return "<style>\n" + TOC_SCOPE + "{\n" + "\n".join(rules) + "\n}\n</style>"


# ---------------------------------------------------------------- 构建
def _section_map(content):
    """返回 [(h2_open_tag, h2_title, start_pos)]，按文档顺序。"""
    out = []
    for m in re.finditer(r'<h2[^>]*class="section-title"[^>]*>(.*?)</h2>', content, re.S):
        title = re.sub(r"<[^>]+>", "", m.group(1)).strip()
        out.append((m.group(0), title, m.start()))
    return out


def _anchor_section(content, anchor):
    pos = content.find(anchor)
    if pos < 0:
        return None, None
    secs = _section_map(content)
    cur = secs[0] if secs else (None, None, -1)
    for s in secs:
        if s[2] <= pos:
            cur = s
        else:
            break
    return cur[0], cur[1]


def build(content, preview, cfg):
    """按 cfg 生成 AFTER 内容。cfg: dict(notes=[...])。
    返回 (after_content, after_preview, report:[str], inserted:[str])"""
    out, report, inserted = content, [], []
    pout = preview or ""

    # ★ 第 0 步：申报式正文修复（比注入还早一步）—— 见「申报式正文修复」小节。
    #   报告里**逐条点名**：评审的人必须一眼看到"这次除了标注还动了正文哪里"，
    #   不能以"顺手修了个图"的名义静默通过。
    _slug = cfg.get("slug")
    out, _fx = apply_body_fixes(out, _slug)
    for _f in body_fixes_for(_slug):
        if _f["id"] in _fx:
            report.append(f"✓ 申报修复 {_f['id']}：{_f['why'].split('。')[0][:70]}")
        else:
            report.append(f"⚠️ 申报修复 {_f['id']} **未命中基线**"
                          f"（find 串在正文里不存在 —— 可能基线已更新，须复核注册表）")

    assert out.count(NZ) == 1, "nrz 锚点不唯一"
    assert out.count(MC) == 1, "main-container 锚点不唯一"

    counts = dict(cfg)
    counts.update(version_counts(cfg["notes"]))   # 计数口径唯一实现（内部按 page_notes 过滤）
    vbar = render_version_bar(counts)

    # ★ 页面可见性分流（Yoyo 2026-09-23 四轮）：
    #   红（来源存疑）**不注入页面** —— 本章的徽标、目录气泡、标注块一并跳过，
    #   否则会出现"徽标说有 2 项、页面上只有 1 块"（比不标更糟）。
    #   台账侧仍在**全量** notes 上工作，那条待办不会丢（make_ledger.py 记「页面展示=否」）。
    pg = page_notes(cfg["notes"])
    hid = hidden_notes(cfg["notes"])
    if hid:
        report.append("⚠️ 页面外标注 ×%d（来源存疑，本次不上前端，仅记台账待处理）：%s"
                      % (len(hid), "、".join(n["rid"].replace("PR-20260907-", "PR-") for n in hid)))

    for n in pg:
        sec_open, sec_title = _anchor_section(content, n["anchor"])
        assert sec_open, f"锚点找不到所属章节: {n['anchor'][:60]}"
        n["anchor_title"] = sec_title
        n["_section_open"] = sec_open
        # 所属章节的**序号**（不是位置 —— 后续插标注会让位置漂移，序号才稳定）
        n["_sec_idx"] = content.count(SEC, 0, content.find(n["anchor"])) - 1
        assert n["_sec_idx"] >= 0, f"锚点不在任何 content-section 内: {n['anchor'][:60]}"

    # 隐藏条目也解析一次落位章节 —— **只为台账「落位章节」列**（页面侧一概不用）。
    # 不做这一步，台账那两行会留空，看台账的人不知道"存疑的是哪一章的事"。
    for n in hid:
        _so, _st = _anchor_section(content, n["anchor"])
        n["anchor_title"] = _st
        n["_section_open"] = _so
        n["_sec_idx"] = (content.count(SEC, 0, content.find(n["anchor"])) - 1 if _so else -1)

    # ① 章节徽标 + 目录气泡：同一次按 H2 聚合算出（状态口径只在一处定义，避免两处漂移）
    by_sec = {}
    for n in pg:
        by_sec.setdefault(n["_section_open"], []).append(n)
    tmap = toc_index_map(content)   # 用**原始** content 算 TOC 序号（注入物里不含 h2，前后等价）
    toc_stats = []
    for sec_open, ns in by_sec.items():
        npend = sum(1 for x in ns if x["status"] == "pending")
        nchk = sum(1 for x in ns if x["status"] == "check")
        nkeep = sum(1 for x in ns if x["status"] == "keep")
        bits = []
        ne = sum(1 for x in ns if x["status"] in ("pending", "check")
                 and effective_state(x.get("effective")) == "effective")
        nsc = sum(1 for x in ns if x["status"] in ("pending", "check")
                  and effective_state(x.get("effective")) == "scheduled")
        if npend:
            sp = []
            if ne:
                sp.append(f"{EFF_TEXT['effective']} {ne}")
            if nsc:
                sp.append(f"{EFF_TEXT['scheduled']} {nsc}")
            bits.append(f"{STATUS_TEXT['pending']} {npend} 项" + (f"（{' · '.join(sp)}）" if sp else ""))
        if nchk:
            bits.append(f"{STATUS_TEXT['check']} {nchk} 项")
        if nkeep:
            bits.append(f"{STATUS_TEXT['keep']} {nkeep} 项")
        state = "pending" if npend else ("check" if nchk else "keep")
        tone = section_tone(ns)     # 章节配色唯一推导（status × 生效状态 → 见 section_tone）
        assert out.count(sec_open) == 1, f"H2 锚点不唯一: {sec_open[:60]}"
        new_open = sec_open.replace('class="section-title"',
                                    f'class="section-title" data-cg-badge="{" · ".join(bits)}"'
                                    f' data-cg-state="{state}" data-cg-tone="{tone}"')
        out = out.replace(sec_open, new_open, 1)
        # 插入串 = 新开标签相对旧开标签多出来的那段属性（用于「只增不改」还原校验）
        inserted.append(new_open[len('<h2 class="section-title"'):new_open.index(">")])
        # 目录气泡数据：序号必须用前端 TOC 自己的规则（tmap），不是 _sec_idx
        title = ns[0]["anchor_title"]
        assert title in tmap, f"TOC 索引匹配失败（h2 文本对不上）: {title}"
        toc_stats.append(dict(heading_idx=tmap[title], title=title, total=len(ns),
                              state=state, tone=tone))
    toc_stats.sort(key=lambda x: x["heading_idx"])
    report.append(f"✓ 章节标题徽标 ×{len(by_sec)}（::after 伪元素，不改 h2 文本）")
    report.append(f"✓ 目录小气泡 ×{len(toc_stats)} 章（"
                  + "、".join(f'{s["title"]}#{s["heading_idx"]}={s["total"]}' for s in toc_stats) + "）")

    # ② 标注块（只落页面上该出现的；隐藏条目在 ① 里也不会带徽标 / 气泡）
    for n in pg:
        a = n["anchor"]
        assert out.count(a) == 1, f"标注锚点不唯一({out.count(a)}): {a[:70]}"
        blk = render_note(n)
        out = out.replace(a, a + blk, 1)
        inserted.append(blk)
    report.append(f"✓ 更新标注块 ×{len(pg)}（页面展示；配置共 {len(cfg['notes'])} 条）")

    # ③ 版本条 + 徽标样式块：**必须注入到每个 content-section 内部**
    #    （前端按章渲染、骨架丢弃顶层元素与 <style>，放外面等于没写 —— 详见 FE_HEAD 说明）
    #    目录气泡 CSS 虽然作用于页面骨架（左侧目录），但它同样是 <style>，
    #    必须**每章都带一份** —— 否则用户打开一个「无标注章节」的页面时，
    #    该页只渲染那个 content-section，样式块不在里面 = 目录上什么气泡都没有。
    sec_positions = [m.start() for m in re.finditer(re.escape(SEC), out)]
    assert sec_positions, "找不到 content-section 锚点"
    sec_with_notes = {n["_sec_idx"] for n in pg}
    toc_css = render_toc_badge_css(toc_stats)
    for idx in sorted(range(len(sec_positions)), reverse=True):
        pos = sec_positions[idx]
        extra = SEC
        if idx in sec_with_notes:
            extra += "\n" + BADGE_CSS
        extra += "\n" + vbar
        # 目录气泡块**追加在最后**：这样 v3.1 已有的注入结构逐字节不变，
        # diff 就是纯追加，也让 `"\n" + toc_css` 成为可整体摘除的原子串（配合 residual_check）
        if toc_css:
            extra += "\n" + toc_css
        out = out[:pos] + extra + out[pos + len(SEC):]
        inserted.append(extra[len(SEC):])
    report.append(f"✓ 数据版本条 ×{len(sec_positions)}（注入每个 content-section 内部，"
                  f"前端分章渲染才可见）")
    report.append(f"✓ 徽标样式块 ×{len(sec_with_notes)}（随标注章节内联注入，规避前端骨架丢弃 <style>）")
    if toc_css:
        report.append(f"✓ 目录气泡样式块 ×{len(sec_positions)}（每章注入一份；<style> 全局生效，"
                      f"任一章节页面都能看到完整目录气泡）")

    # 预览串（平台实际从 content 派生，这里保持一致写法作为兜底）
    if pout.count(SEC):
        first = pout.find(SEC)
        pout = pout[:first] + SEC + "\n" + vbar + pout[first + len(SEC):]
    report.append("· previewContent 照常提交，但平台会**忽略**该值并自行从 content 派生（见文件头说明）")
    return out, pout, report, inserted


# ---------------------------------------------------------------- 校验
def residual_check(before, after, inserted, slug=None):
    """把插入串逐一移除、再撤回申报修复后，应还原 before —— 证明「只增不改 + 只申报改」。

    实现要点：**不能按 inserted 列表顺序逐个 replace** —— 插入串之间可能存在包含关系
    （如"每个章节的版本条"与"含徽标样式的复合块"，后者尾部正是前者），
    顺序摘除会误吃子串、导致后续找不到。改为：按长度降序合成一个 alternation 正则，
    从左到右一次性摘除（左最先 + 最长优先），再用计数比对确认没多摘也没漏摘。
    """
    if not inserted:
        return None
    from collections import Counter
    pats = sorted(set(inserted), key=len, reverse=True)
    rx = re.compile("|".join(re.escape(p) for p in pats))
    got = [m.group(0) for m in rx.finditer(after)]
    if Counter(got) != Counter(inserted):
        miss = Counter(inserted) - Counter(got)
        extra = Counter(got) - Counter(inserted)
        return (f"插入串在 AFTER 中的数量不符（缺 {sum(miss.values())} / 多 {sum(extra.values())}）"
                f"：{str(list(miss.items())[:1] or list(extra.items())[:1])[:120]}")
    probe = undo_body_fixes(rx.sub("", after), slug)   # 申报修复要反向撤掉才算"还原"
    if probe != before:
        i = next((k for k in range(min(len(probe), len(before))) if probe[k] != before[k]),
                 min(len(probe), len(before)))
        return (f"无法还原为原文（长度 {len(probe)} vs {len(before)}，首个分歧 offset={i}）"
                f" → 说明有非插入式改动，正文被改过了")
    return None


def validate(before, after, cfg, inserted=None):
    errs = []
    notes = cfg["notes"]
    # ★ 页面侧一切计数都比对 page_notes()（Yoyo 2026-09-23 四轮：红色不上前端）。
    #   本函数是**形态门禁**（查产物），所以基数天然是"页面上该有的条数"，不是配置条数。
    pg = page_notes(notes)
    # 允许脱离 build() 单独调用（二次全文校验 / 负向测试）：缺 _section_open 就按 before 补算
    for n in notes:
        if "_section_open" not in n:
            so, st = _anchor_section(before, n.get("anchor", ""))
            n["_section_open"] = so
            n["anchor_title"] = st
            n["_sec_idx"] = (before.count(SEC, 0, before.find(n["anchor"])) - 1
                             if so else -1)
    if len(after) <= len(before):
        errs.append("长度未增长")
    if after.count("<div") != after.count("</div>"):
        errs.append(f"div 不平衡 {after.count('<div')}/{after.count('</div>')}")
    if after.count('<h2 class="section-title"') != before.count('<h2 class="section-title"'):
        errs.append("h2.section-title 数量变化")

    # 页面可见要素（2026-09-23 起「标注写入 / 校对ID」已撤出页面，故不在此列）
    for k, want in [("现行：", len(pg)), ("来源：", len(pg))]:
        if after.count(k) < want:
            errs.append(f"要素缺失 {k} ×{after.count(k)}/{want}")
    # 校对ID 改由 **data-cg-rid 属性**承载（页面不可见，但机器定位/台账回写要用，必须齐）
    got_rid_attr = len(re.findall(r'data-cg-rid="PR-\d{8}-\d+"', after))
    if got_rid_attr != len(pg):
        errs.append(f"data-cg-rid 属性数 {got_rid_attr}/{len(pg)}（定位用，页面不可见但必须齐）")
    # 配色档（tone）与落位（anchor）同为**属性承载**：色值渲染要复算、台账要「落位章节」，
    # 都靠这两个属性 —— 页面文本里看不到，但少了就没法复算 / 回填（静默失败）。
    # ⚠️ 两个坑（首轮实测各踩一次）：① 徽标 CSS 里也有 `[data-cg-tone="…"]` 选择器
    #    ② h2 徽标也带 data-cg-tone —— 所以必须**按标注块标签**限定，别全文 count。
    _nos = strip_style(after)
    got_tone_attr = len(re.findall(r'<div class="cg-update-note"[^>]*data-cg-tone="', _nos))
    got_anchor_attr = len(re.findall(r'<div class="cg-update-note"[^>]*data-cg-anchor="', _nos))
    if got_tone_attr != len(pg):
        errs.append(f"data-cg-tone 属性数 {got_tone_attr}/{len(pg)}（配色档，渲染复算要用）")
    if got_anchor_attr != len(pg):
        errs.append(f"data-cg-anchor 属性数 {got_anchor_attr}/{len(pg)}"
                    f"（落位章节，台账「落位章节」列要用）")
    # ★ 红色档（来源存疑）不得出现在页面（Yoyo 2026-09-23 四轮）——
    #   与 qc_gate 的 F5 / verify_secondary 的 S15 同一口径（判定唯一入口 = on_page）。
    #   查两处：① 标注块属性 ② h2 徽标属性（两处都可能是"漏滤"的入口）。
    _red_note = re.findall(r'<div class="cg-update-note"[^>]*data-cg-tone="verify"', _nos)
    _red_h2 = re.findall(r'data-cg-tone="verify"', _nos)
    if _red_note or _red_h2:
        errs.append(f"页面出现红色档（来源存疑）×{len(_red_h2)} —— 该类条目**不上前端**，"
                    f"只记台账待处理；过滤入口 = guide_patch_lib.page_notes()")
    n_new = sum(1 for n in pg if n.get("new"))
    if after.count("拟更新为：") + after.count("核实结论：") < n_new:
        errs.append(f"新值行缺失 {after.count('拟更新为：') + after.count('核实结论：')}/{n_new}")

    if after.count("data-cg-badge=") != len({n["_section_open"] for n in pg}):
        errs.append(f"data-cg-badge 数={after.count('data-cg-badge=')} "
                    f"应为 {len({n['_section_open'] for n in pg})} 个章节")

    # 目录气泡：① 条数 = 有更新章节数 × content-section 份数（每章各带一份 <style>）
    #           ② 序号必须落在真实 h2 总数内（越界 = 选择器永不命中，且是**静默失败**）
    want_toc = len({n["_section_open"] for n in pg}) * after.count(SEC)
    got_toc = after.count(TOC_SEL)
    if got_toc != want_toc:
        errs.append(f"目录气泡规则数 {got_toc}/{want_toc}（有更新章节数 × content-section 份数）")
    n_h2 = len(re.findall(r"<h2[^>]*>", strip_style(after), re.I))
    for m in re.finditer(re.escape(TOC_SEL) + r'(\d+)"\]::before', after):
        if int(m.group(1)) >= n_h2:
            errs.append(f"目录气泡序号越界：heading-{m.group(1)} ≥ h2 总数 {n_h2}")
    if got_toc and TOC_SCOPE not in after:
        errs.append("目录气泡样式块没有包在 @scope 里 —— 会被平台加 .article-isolate 前缀而失效")
    # 判定依据 = 「所有状态文案」的并集，而不是手抄几个字面量：
    #   徽标本该走 ::after（CSS 生成内容，不进 textContent），h2 文本里出现任何一个
    #   状态词都说明注入方式退化了。词表来自常量，改文案时自动跟着走（防手抄漂移）。
    _state_words = list(dict.fromkeys(
        list(STATUS_TEXT.values()) + STATUS_TEXT_STALE
        + [v for v in EFF_TEXT.values() if v] + EFF_TEXT_STALE))
    for m in re.finditer(r"<h2[^>]*>(.*?)</h2>", after, re.S):
        t = re.sub(r"<[^>]+>", "", m.group(1)).strip()
        if any(x in t for x in _state_words):
            errs.append(f"h2 文本被污染: {t[:30]}")

    # ── 前端分章渲染门禁（★ 本技能最重要的门禁）───────────────────────────────
    # 前端按章渲染、用硬编码骨架，只保留"匹配到的那个 content-section"。
    # 顶层元素与 <style> 会被丢弃 —— 所以必须**逐章模拟**，确认三件套真的在分章视图里。
    inner = _main_inner(after) or ""
    tops = _top_level_divs(inner)
    if any(x[2].lstrip().startswith('<div class="cg-version-bar') for x in tops):
        errs.append("版本条是 main-container 的顶层子元素（前端骨架会丢弃，必须塞进 content-section 内）")
    for t in [x[1] for x in _section_map(after)]:
        view = simulate_frontend_section(after, t)
        if view is None:
            errs.append(f"前端分章模拟失败（章节名匹配不上）: {t}")
            continue
        if "cg-version-bar" not in view:
            errs.append(f"分章视图[{t}] 缺数据版本条")
        if TOC_SEL not in view:
            errs.append(f"分章视图[{t}] 缺目录气泡样式块（该章页面左侧目录将无气泡）")
    by_sec_chk = {}
    for n in pg:      # ★ 只用页面侧的条目 —— 整章都是存疑条目时，该章本就不该有徽标/标注块
        by_sec_chk.setdefault(n["_section_open"], []).append(n)
    for sec_open, ns in by_sec_chk.items():
        t = ns[0]["anchor_title"]
        view = simulate_frontend_section(after, t)
        if view is None:
            errs.append(f"前端分章模拟失败: {t}")
            continue
        got = view.count('class="cg-update-note"')
        if got != len(ns):
            errs.append(f"分章视图[{t}] 标注块 {got}/{len(ns)}")
        if "data-cg-badge=" not in view:
            errs.append(f"分章视图[{t}] 缺章节徽标属性")
        if "::after" not in view:
            errs.append(f"分章视图[{t}] 徽标样式块被前端骨架丢弃（<style> 必须放章节内）")

    # ── ★★ R 组：前端脆弱 walker 门禁（2026-09-23 线上事故后新增，最关键）────────
    # 线上事故：UAE 第 5–12 章「无法加载内容。h2Content为空。」
    # 教训：本地正则解析全通过 ≠ 线上能渲染。必须用**复刻前端朴素 indexOf** 的
    #       frontend_blocks() 再验一遍 —— 它数出来的章节数才是线上的真实可见章节数。
    # 两条断言：① 危险邻接为 0 ② walker 能发现全部章节（缺一即阻断）
    unsafe = walk_unsafe_spans(after)
    if unsafe:
        samples = [after[max(0, p - 30):p + 22].replace("\n", "\\n") for p in unsafe[:3]]
        errs.append(f"存在 `</div><` 危险邻接 ×{len(unsafe)} —— 会让前端 walker 的 u=d+7 "
                    f"越位跳标签、导致后续章节 h2Content 为空；例：{samples}")
    want_titles = [t for _o, t, _p in _section_map(after)]
    seen = set(frontend_visible_sections(after))
    missing = [t for t in want_titles if t not in seen]
    if missing:
        errs.append(f"前端 walker 只能发现 {len(seen)}/{len(want_titles)} 章，"
                    f"线上这些章节会报「h2Content为空」：{missing}")

    # ── ★★ E 组：「已正式生效 / 计划变更」判定门禁（Yoyo 2026-09-23）──────────
    # 背景：2026-06-01 已生效的条目，线上显示成「计划」。修法 = 判定口径唯一化 + 门禁。
    # 文案一律取 EFF_TEXT（客户向），不在门禁里再写一遍字面量。
    bad_eff = []
    for n in notes:
        es = effective_state(n.get("effective"))
        n["_eff_state"] = es
        if n["status"] == "pending" and es == "na":
            bad_eff.append(f'{n["rid"]} 待更新却无可解析生效日期（effective={n.get("effective")!r}）'
                           f' —— 无法判定「{EFF_TEXT["scheduled"]}/{EFF_TEXT["effective"]}」，必须补日期')
    if bad_eff:
        errs.append("生效日期门禁：" + "；".join(bad_eff))
    # 渲染一致性：产物里每条块的 data-cg-eff 必须等于按「标注写入日」重算的结果，
    # 且文案后缀必须与之一致（防手写文案漂移 —— 这正是本次线上问题的形态）。
    _by_rid = {n["rid"]: n for n in notes}
    for m in re.finditer(r'<div class="cg-update-note"([^>]*)>', after):
        attrs = m.group(1)
        rid = (re.search(r'data-cg-rid="([^"]*)"', attrs) or [None, "?"])[1]
        eff = (re.search(r'data-cg-effective="([^"]*)"', attrs) or [None, ""])[1]
        got = (re.search(r'data-cg-eff="([^"]*)"', attrs) or [None, ""])[1]
        want = effective_state(eff)
        if got != want:
            errs.append(f"{rid} 生效状态不一致：产物标 {got!r}，按生效日期 {eff!r} 应为 {want!r}")
        # 配色档（tone）也是**派生值**：产物里的 data-cg-tone 必须等于按 (status, 生效状态)
        # 重算的结果 —— 否则「绿 / 橙黄 / 灰」的口径会在产物里漂移
        #（改配色口径只改常量，旧产物跟不上 → 页面颜色与规定不符，而这**看不出来**）。
        note = _by_rid.get(rid)
        got_tone = (re.search(r'data-cg-tone="([^"]*)"', attrs) or [None, ""])[1]
        if note:
            want_tone = tone_of(note)
            if got_tone != want_tone:
                errs.append(f"{rid} 配色档不一致：产物标 {got_tone!r}，按 status="
                            f"{note.get('status')!r} / 生效日 {eff!r} 应为 {want_tone!r}")
        if not (re.search(r'data-cg-anchor="([^"]+)"', attrs)):
            errs.append(f"{rid} 缺 data-cg-anchor 属性 —— 台账「落位章节」列要靠它回填")
        seg = after[m.start():m.start() + 2600]
        seg = seg[:seg.find("</div>")] if "</div>" in seg else seg
        if want == "effective" and EFF_TEXT["effective"] not in seg:
            errs.append(f"{rid} 生效日期 {eff} 已过（写入日 {TODAY}），页面必须写明"
                        f"「{EFF_TEXT['effective']}」")
        if want == "scheduled" and EFF_TEXT["scheduled"] not in seg:
            errs.append(f"{rid} 生效日期 {eff} 未到，页面必须写明「{EFF_TEXT['scheduled']}」")

    # ── ★★ F 组：客户向文案门禁（Yoyo 2026-09-23「写这个是给客户看的」）─────────
    # 四条硬口径：
    #   F1 「正文版本」= 最新校验时间的**月**粒度（2026-09），且必须等于重算值
    #   F2 页面**不出现**内部过程时间字段（校验时间 / 最新校验 / 校对日期）
    #   F3 状态文案只准用客户语言，两类旧文案（STALE_COPY = 标注状态 + 生效状态）一律不合格
    #   F4 页面**不出现**内部过程字段（标注写入 / 校对ID）—— 只记台账
    vbm = re.search(r'正文版本：<strong>([^<]*)</strong>', after)
    want_bv = version_bar_dates(cfg)["body_version"]
    if not vbm:
        errs.append("版本条缺「正文版本」字段")
    else:
        got_bv = vbm.group(1)
        if not re.fullmatch(r"\d{4}-\d{2}", got_bv):
            errs.append(f"「正文版本」不是月粒度（{got_bv!r}）—— 客户向只到月，如 2026-09")
        elif want_bv and got_bv != want_bv:
            errs.append(f"「正文版本」{got_bv} ≠ 最新校验月份 {want_bv}（口径：最新校验时间写到月）")
    for frag in ("校验时间", "最新校验", "校对日期"):
        if frag in after:
            errs.append(f"页面出现内部过程时间字段「{frag}」—— 客户向不得展示（Yoyo 2026-09-23）")
    stale = [x for x in STALE_COPY if x in after]
    if stale:
        errs.append(f"页面残留旧状态文案 {stale} —— 客户向应为 "
                    + " / ".join(list(STATUS_TEXT.values())
                                 + [v for v in EFF_TEXT.values() if v])
                    + "（新口径唯一真相源 = guide_patch_lib.STATUS_TEXT / EFF_TEXT）")

    # F4 内部过程字段不得出现在页面（Yoyo 2026-09-23：只在台账记录）★
    #   撤出页面的是「标注写入时间」「校对ID」「页面位置」；它们改由
    #   data-cg-rid / data-cg-anchor **属性** 承载定位。
    #   这里查的是**全文**：基线是剥离过注入物的干净正文，所以出现即可判定为
    #   「渲染回退」或「旧稿回流」，不存在误报。
    for frag in INTERNAL_FIELDS:
        if frag in after:
            errs.append(f"页面出现内部过程字段「{frag}」—— 客户向不得展示，只记台账"
                        f"（定位改走 data-cg-rid / data-cg-anchor 属性）")

    # 版本条计数自洽（负向测试暴露：只查 qc_gate 不够，build 校验层也要拦 —— 文案数字会漂移）
    vb = re.search(r'<div class="cg-version-bar"[\s\S]*?\n</div>', after)
    if not vb:
        errs.append("产物缺数据版本条")
    else:
        vtxt = vb.group(0)
        p_pend, p_eff, p_sch = version_bar_probe(notes)
        if p_pend not in vtxt:
            errs.append(f"版本条「待更新」计数不符（应含 {p_pend}）")
        for frag in (p_eff, p_sch):
            if frag and frag not in vtxt:
                errs.append(f"版本条生效拆分不符（应含 {frag}）")

    for bad in FORBIDDEN_COLORS:
        if bad in after:
            errs.append(f"出现非站色 {bad}")

    # ── 链接口径（Yoyo 2026-09-22 修订：站外只放官方原文，站内解读/工具必须站内域名）★ ──
    # 三方解析（四大·律所 / 行业平台 / 媒体）一票否决；站外只允许 official，站内只允许 internal。
    # 判定规则见 official-domains.json。这里只做「产物自洽性」校验；真正的上线闸门是 qc_gate.py。
    # ★ 基数 = pg（页面侧）：不上页面的条目，其链接客户根本点不到 ⇒ 不参与本组校验，
    #   也不该因为"缺 official_url"而被拦（那会把「暂时撤下」变成「必须立刻溯源」）。
    for n in pg:
        if not n.get("official_url"):
            errs.append(f"{n['rid']} 缺 official_url —— 该条不会带任何链接，须先溯源再上线")
            continue
        vd, h = classify_source(n["official_url"])
        if vd != "official":
            errs.append(f"{n['rid']} official_url 非官方源（{vd}: {h}）")
        if n.get("interpret_url"):
            vd2, h2 = classify_source(n["interpret_url"])
            if vd2 != "internal":
                errs.append(f"{n['rid']} 解读链接非站内（{vd2}: {h2}）—— 只能跳 humancehr.com/anchorwe.com")
        for e in (n.get("tool_entries") or []):
            if not e.get("url"):
                continue
            vd3, h3 = classify_source(e["url"])
            if vd3 != "internal":
                errs.append(f"{n['rid']} 工具入口非站内（{vd3}: {h3}）")
        nt = len(n.get("tool_entries") or [])
        if nt > 2:
            errs.append(f"{n['rid']} 工具入口 {nt} 个（建议 ≤2，超过显得推销感重、移动端折行）")
    got_lnk = after.count(">官方原文 ↗</a>")
    if got_lnk != len(pg):
        errs.append(f"「官方原文 ↗」链接数 {got_lnk}/{len(pg)}")
    # 数量对 ≠ 指对了：产物 href 必须与配置 official_url **逐条等价**（见 official_hrefs 说明）
    _got_h = official_hrefs(after)
    _cfg_h = official_hrefs_cfg(pg)
    if sorted(_got_h) != sorted(_cfg_h):
        _miss = [u for u in _cfg_h if u not in _got_h][:2]
        _extra = [u for u in _got_h if u not in _cfg_h][:2]
        errs.append(f"「官方原文 ↗」指向不一致：配置 {len(_cfg_h)} 条 / 产物 {len(_got_h)} 条"
                    + (f"；缺 {_miss}" if _miss else "")
                    + (f"；多/错 {_extra}" if _extra else ""))
    for blk in re.findall(r'<div class="cg-update-note"[\s\S]*?\n</div>', after):
        for u in re.findall(r'href="(https?://[^"]+)"', blk):
            vd, h = classify_source(u)
            # 标注块内只许 official（站外官方原文）+ internal（站内解读/工具），其余一律阻断
            if vd not in ("official", "internal"):
                errs.append(f"标注块内出现非法链接（{vd}: {h}）")

    # 原值只增不减：从 old 抽关键词，逐个比对出现次数
    for n in notes:
        for tok in _tokens(n.get("old") or ""):
            if before.count(tok) > after.count(tok):
                errs.append(f"原值疑似被删 {tok}（{before.count(tok)}→{after.count(tok)}）")

    if inserted is not None:
        r = residual_check(before, after, inserted, cfg.get("slug"))
        if r:
            errs.append(r)

    # 申报式正文修复：**逐条核对真的生效**（find 无残留 + replace 已出现）。
    # residual_check 证明"还原得回去"，这一步证明"确实改对了" —— 两者互补，缺一不可：
    # 只做前者的话，一条 find 写错（基线里根本不存在）照样能通过。
    for row in audit_body_fixes(after, cfg.get("slug")):
        if not row["ok"]:
            errs.append(f"申报修复 {row['id']} {row['msg']}")
    for fid in orphan_body_fixes(cfg.get("slug"), before):
        errs.append(f"申报修复 {fid} 在基线中未命中 —— 过期申报，须复核/移除注册表条目")
    for fid, miss in body_fixes_missing_fields():
        errs.append(f"申报修复 {fid} 字段不全（缺 {'/'.join(miss)}）—— 注册表条目必须自证依据")
    return errs


def _tokens(s):
    """从原值文本里抽可校验的关键词（数字串 / 带千分位数字 / 明显单位值）。"""
    s = re.sub(r"<[^>]+>", "", s)
    out = set()
    for m in re.finditer(r"\d[\d,\.]*\s*(?:%|天|个月|个月工资|欧|美元|迪拉姆|AED|QAR|SAR|MYR|THB|INR|TRY|£|\$/|卢比|里亚尔)?", s):
        t = m.group(0).strip()
        if len(t) >= 3:
            out.add(t)
    return sorted(out, key=len, reverse=True)[:6]


# ---------------------------------------------------------------- Strapi
def push_and_verify(documentId, content, preview):
    """写线上 + 回查校验（**唯一实现**）。

    2026-09-23 从 batch_guide_patch.py 抽上来：两阶段发布的
    `release_apply.py` 也要写同一份内容，若各写一份 PUT+回查逻辑必然漂移。
    返回 dict（与旧 batch_guide_patch 的行结构兼容）。
    """
    s, _ = strapi_call("PUT", f"/api/articles/{documentId}",
                       body={"data": {"content": content, "previewContent": preview}})
    _, chk = strapi_call("GET", f"/api/articles/{documentId}?populate=*")
    now = chk["data"]["content"] if isinstance(chk, dict) and "data" in chk else ""
    # 探测"是否已发布"改用 cg-update-note 标记（2026-09-23：「标注写入」已撤出页面文本，
    # 不能再拿它当探测器 —— 否则永远判为"未发布"，每次都多打一次 publish）
    if 'class="cg-update-note"' not in now:      # 未发布 → 触发 publish 再回读
        strapi_call("PUT", f"/api/articles/{documentId}/actions/publish")
        _, chk = strapi_call("GET", f"/api/articles/{documentId}?populate=*")
        now = chk["data"]["content"] if isinstance(chk, dict) and "data" in chk else ""
    pnow = (chk["data"].get("previewContent") or "") if isinstance(chk, dict) and "data" in chk else ""
    v_ok, v_msg = verify_content(now, content)
    p_clean, p_frag = preview_truncation_clean(pnow)
    return dict(put_status=s, content_verified=v_ok, content_verify_msg=v_msg,
                remote_len=len(now), remote_sha=sha16(now),
                preview_len=len(pnow), preview_derived_by_platform=True,
                preview_truncation_clean=p_clean, preview_cut_fragment=p_frag)


def token():
    t = os.environ.get("HUMANCE_STRAPI_TOKEN")
    if t:
        return t.strip()
    p = os.path.expanduser("~/.workbuddy/.humance_strapi_token")
    if os.path.exists(p):
        return open(p).read().strip()
    sys.exit("❌ 未找到 Strapi Token（~/.workbuddy/.humance_strapi_token）")


def strapi_call(method, path, body=None, timeout=120):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    h = {"User-Agent": "curl/8", "Content-Type": "application/json",
         "Authorization": f"Bearer {token()}"}
    data = json.dumps(body).encode() if body is not None else None
    try:
        req = urllib.request.Request(STRAPI_BASE + path, headers=h, data=data, method=method)
        with urllib.request.urlopen(req, context=ctx, timeout=timeout) as r:
            raw = r.read().decode("utf-8", "ignore")
            return r.status, (json.loads(raw) if raw.strip().startswith(("{", "[")) else raw)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "ignore")[:400]
    except Exception as e:
        return type(e).__name__, str(e)[:300]
