#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成「标注状态配色 + 核心要点字号」对照说明页（客户/内部沟通用）。

用法：
    python3 make_tone_card.py [输出路径.html]

为什么要有这个脚本（而不是一次性手写 HTML）：
  · 配色样例**走真实渲染函数**（guide_patch_lib.render_note / _badge_css / TONE），
    **一个色值都不手抄** —— 否则对照卡自己就会漂移，变成第二份真相源。
    口径改了（如 2026-09-23 的 v2→v3），重跑一次即同步。
  · 字号部分（KB-001）的对比卡也是同样的思路：字号写在与阈值无关的样例里，
    但阈值/根因/影响面的表述与 `references/quality-baseline.json` 对齐。

⚠️ 本脚本产出的 HTML 是**说明材料**，不是页面产物 —— 不进任何门禁、不落线上。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import guide_patch_lib as L  # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else "/tmp/tone_card.html"

# ── 四个 tone 档的样例（覆盖「待更新已生效 / 待更新未生效 / 待核 / 维持现状」）──
SAMPLES = [
    ("in_force", "今年有变更 · 已落地",
     dict(rid="PR-20260907-047", status="pending", effective="2026-06-01",
          title="WPS 工资保护新规", anchor_title="薪酬支付",
          old="MR 598/2022：15 天宽限期，合规门槛 80%",
          new="MR 340/2026（已废除 598/2022）：次月 1 日前须到账（取消宽限期）；合规门槛 80% → 85%",
          source="MoHRE（人力资源与酋长国化部）", tier="政府/官方门户",
          official_url="https://www.mohre.gov.ae/")),
    ("upcoming", "今年计划变更 · 尚未落地",
     dict(rid="PR-20260907-S01", status="pending", effective="2027-03-01",
          title="（样例）法定带薪年假拟调整", anchor_title="休假政策",
          old="现行：服务满 1 年 30 天年假",
          new="拟更新为：服务满 6 个月起按 2.5 天/月累积，满 1 年仍为 30 天",
          source="MoHRE（人力资源与酋长国化部）", tier="政府/官方门户",
          official_url="https://www.mohre.gov.ae/")),
    ("verify", "来源存疑 · 待核　🚫 不上前端（仅台账待处理）",
     dict(rid="PR-20260907-050", status="check", effective="—",
          title="EOSB 离职酬金", anchor_title="福利",
          old="前 5 年每年 21 天基本工资；第 6 年起 30 天",
          new="未检索到 2026 变更。提示：阿联酋籍员工适用 GPSSA、不享 EOSB",
          source="阿联酋联邦立法门户 + 劳动法 Art.51", tier="政府/官方门户",
          official_url="https://uaelegislation.gov.ae/")),
    ("no_change", "维持现状 · 已核实无变更",
     dict(rid="PR-20260907-051", status="keep", effective="—（维持现行）",
          title="个人所得税", anchor_title="个税",
          old="0%（无个人所得税）",
          new="",
          source="阿联酋政府门户 u.ae", tier="政府/官方门户",
          official_url="https://u.ae/")),
]

# 语义说明表：(颜色名, 常量名, 触发条件说明)
# ⚠️ 颜色名要与 TONE 的实际色值一致 —— 但色值本身从 L.TONE 读，这里只写"叫什么颜色"。
#    改配色时**必须同步改这里**（这是文案，不是真相源；真相源永远是 guide_patch_lib.TONE）。
SEM = {
    "in_force": ("绿", "TONE.in_force",
                 "今年有变更，且**已正式生效**（生效日 ≤ 标注写入日）→ 页面上显示为绿"),
    "upcoming": ("橙黄", "TONE.upcoming",
                 "确定今年有变更，**尚未生效**（生效日 > 写入日，或生效日待定）→ 页面上显示为橙黄"),
    "verify": ("红（**不上前端**）", "TONE.verify",
               "来源存疑，待核 ⇒ **整条不注入页面**（也不进版本条计数），"
               "只记飞书台账「页面展示 = 否 · 待处理」；补齐一手源后重走落线，"
               "该条会以绿 / 橙黄的身份回到页面。色值保留定义是为了台账与说明材料可标注"),
    "no_change": ("绿", "TONE.no_change",
                  "核实后**维持现状** ⇒ 与「有变更已生效」**同为绿**；"
                  "两者**靠徽标文案区分**（`✅ 无需更新` vs `⏳ 待更新 · 已正式生效`），色值同源"),
}

# 卡片专用：把**不在页面上出现**的档（红）也补一份徽标 CSS —— 否则本卡里那一档的
# 章节徽标会走默认档（橙黄），看起来像"红色档坏掉了"。
# 色值仍从 TONE 生成（不手抄）；这段**只属于说明材料**，不进任何页面产物。
HIDDEN_BADGE_CSS = "<style>\n" + "\n".join(
    f'.nrz h2.section-title[data-cg-tone="{t}"]::after'
    f'{{background:{L.TONE[t]["chip_bg"]};color:{L.TONE[t]["ink"]};'
    f'border:1px solid {L.TONE[t]["chip_bd"]};}}'
    for t in L.PAGE_HIDDEN_TONES) + "\n</style>"

STAT_CSS = ("background:#fff;border:1px solid #e5e7eb;border-radius:10px;"
            "padding:16px 12px;text-align:center;flex:1;")


def stat_card(label, px, note):
    return (f'<div style="{STAT_CSS}">'
            f'<div style="font-size:12px;color:#6b7280;margin-bottom:8px;">{label}</div>'
            f'<div style="font-size:{px}px;font-weight:700;color:#1565c0;line-height:1.2;">22%</div>'
            f'<div style="font-size:12px;color:#9ca3af;margin-top:8px;">{note}</div></div>')


def badge_of(n):
    """章节徽标文案 —— 复刻 build() 里的 bits 格式（带计数与括号），不手抄。"""
    st = n["status"]
    if st == "pending":
        return f"{L.STATUS_TEXT['pending']} 1 项（{L.effective_badge(n)}）"
    return f"{L.STATUS_TEXT[st]} 1 项"


def main():
    blocks, sem_rows = [], []
    for tone, label, note in SAMPLES:
        color, const, desc = SEM[tone]
        c = L.TONE[tone]
        # 不上前端的档（红）在本卡里加个"仅示意"角标 + 压灰，
        # 免得看图的人以为页面上会有这块（正是本轮要消掉的东西）。
        hidden = tone in L.PAGE_HIDDEN_TONES
        extra = (' style="filter:grayscale(.45);opacity:.92;"' if hidden else "")
        flag = ('<span class="pill pill-hid">🚫 实际不上前端</span>' if hidden else "")
        blocks.append(
            f'<div class="case"{extra}>'
            f'<div class="case-h"><span class="pill" style="background:{c["chip_bg"]};'
            f'color:{c["ink"]};border:1px solid {c["chip_bd"]};">{tone} · {color}</span>'
            f'{flag}<b>{label}</b><code>{const}</code></div>'
            f'<div class="nrz"><h2 class="section-title" data-cg-badge="{badge_of(note)}"'
            f' data-cg-tone="{tone}" style="font-size:22px;margin:14px 0 6px;">'
            f'{note["anchor_title"]}</h2>{L.render_note(note)}</div>'
            f'<div class="swatches">'
            + "".join(f'<span class="sw"><i style="background:{c[k]};"></i>{k} {c[k]}</span>'
                      for k in ("bg", "bar", "chip_bg", "ink"))
            + f'</div></div>')
        sem_rows.append(f"<tr><td><code>{tone}</code>{' 🚫' if hidden else ''}</td><td>{color}</td>"
                        f"<td>{desc}</td><td><code>{c['bar']}</code></td><td><code>{c['bg']}</code></td></tr>")

    same_green = L.TONE["in_force"] == L.TONE["no_change"]

    html = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<title>标注状态配色 · 核心要点字号 —— 对照说明</title>
{L._badge_css()}
{HIDDEN_BADGE_CSS}
<style>
 body{{font:14px/1.7 -apple-system,"PingFang SC","Noto Sans SC",sans-serif;
      color:#18181b;background:#fafafa;margin:0;padding:28px 30px 60px;}}
 h1{{font-size:22px;margin:0 0 4px;}} .sub{{color:#71717a;font-size:13px;margin-bottom:22px;}}
 h2.sec{{font-size:17px;margin:34px 0 12px;padding-left:10px;border-left:4px solid #1565c0;}}
 h3{{font-size:14.5px;margin:22px 0 8px;color:#3f3f46;}}
 table{{border-collapse:collapse;width:100%;font-size:13px;margin:10px 0 6px;}}
 th,td{{border:1px solid #e4e4e7;padding:7px 10px;text-align:left;vertical-align:top;}}
 th{{background:#f4f4f5;font-weight:600;}}
 code{{background:#f4f4f5;padding:1px 5px;border-radius:4px;font-size:12.5px;}}
 .case{{background:#fff;border:1px solid #e4e4e7;border-radius:10px;
        padding:14px 18px 12px;margin:14px 0;}}
 .case-h{{display:flex;align-items:center;gap:10px;font-size:13px;margin-bottom:4px;
          flex-wrap:wrap;}}
 .pill{{display:inline-block;padding:2px 10px;border-radius:999px;font-size:12px;font-weight:600;}}
 .pill-hid{{background:#f4f4f5;color:#71717a;border:1px solid #d4d4d8;}}
 .swatches{{display:flex;flex-wrap:wrap;gap:14px;margin-top:12px;
            padding-top:10px;border-top:1px dashed #e4e4e7;font-size:12px;color:#71717a;}}
 .sw{{display:flex;align-items:center;gap:5px;}} .sw i{{width:12px;height:12px;
      border-radius:3px;border:1px solid #d4d4d8;display:inline-block;}}
 .note{{background:#eff6ff;border-left:3px solid #1565c0;padding:10px 14px;
        border-radius:0 6px 6px 0;font-size:13px;margin:12px 0;}}
 .chg{{background:#f0fdf4;border-left:3px solid #22c55e;padding:10px 14px;
       border-radius:0 6px 6px 0;font-size:13px;margin:12px 0;}}
 .row{{display:flex;gap:14px;margin:14px 0;align-items:stretch;}}
 .ruler{{font-size:12px;color:#71717a;border-top:1px dashed #a1a1aa;
         padding-top:4px;margin-top:10px;}}
</style></head><body>

<h1>标注状态配色 · 核心要点字号 —— 对照说明</h1>
<div class="sub">2026-09-23（v4 口径）｜ 慧思国别指南更新标注 ｜
配色真值源：<code>guide_patch_lib.TONE</code>（唯一一处，全站 76 国共用）</div>

<div class="chg">
<b>本轮改动（v3 → v4）</b>：<b>红色（来源存疑）不上前端</b> —— 原话「红色 存疑 先不在前端展示，记录台账待处理」。<br>
⇒ <b>页面只出现两类颜色</b>：绿（不用管）｜ 橙黄（计划变更未落地）。
存疑条目整条不注入页面、也不进版本条计数，只记飞书台账「页面展示 = 否 · 待处理」；
补齐一手源后重走落线，它会以绿 / 橙黄的身份回到页面。<br>
<b>连带口径</b>：外链门禁（L4/L5/L9）的取数基数同步收到「页面上会出现的那几条」——
不上页面的条目，其链接客户点不到，不该再占人工点验的闸门。
</div>

<div class="chg">
<b>上一轮（v2 → v3）</b>：<b>「维持不变」也标绿</b> —— 原话「还有继续维持不变，也是绿色」。<br>
客户视角下「已核实、无需关注」就是一档，灰反而像"没做完 / 被跳过"。
⇒ 绿 = ｛有变更且已生效｝∪｛维持不变｝，两类**同色、靠徽标文案区分**。
</div>

<h2 class="sec">一、配色规则（按「变更落地进度」着色，不按 status 着色）</h2>
<div class="note">
四档 tone 值，**页面上只落三种颜色、其中红色不出现**：<br>
<b>绿</b> = 不用管（要么有变更且已落地，要么核实过没变）｜
<b>橙黄</b> = 今年要变、还没落地，需要关注｜
<b>红</b> = 来源存疑 ⇒ <b>不上前端</b>，只进台账待处理。<br>
两个绿色档的色值来自同一份常量（本节实测：两档色值相同 = <code>{same_green}</code>），
所以<b>改绿只改一处</b>；区分它们的是徽标里的文案，不是深浅。
</div>
<table>
<tr><th>配色档 tone</th><th>颜色</th><th>含义与触发条件</th><th>主色（左边框）</th><th>底色</th></tr>
{''.join(sem_rows)}
</table>

<h2 class="sec">二、四档实际渲染（下方为真实渲染产物，非示意图）</h2>
<div class="note">第四档（红）本卡**保留展示**是为了说明材料完整、台账可对照；
它带 🚫 角标且压灰 —— 那一档在页面上**不存在**（判定入口 <code>guide_patch_lib.on_page()</code>）。</div>
{''.join(blocks)}

<h2 class="sec">三、核心要点字号（KB-001 · 层级倒置）</h2>
<h3>问题</h3>
<div class="row">
{stat_card('现状 · 字号 26.4px', 26.4, '迪拜/阿布扎比外资银行')}
{stat_card('本页章节标题基准 · 22px', 22, '（同页「个税」等一级标题）')}
</div>
<div class="ruler">↑ 卡内数值（26.4px）比同页<b>一级章节标题</b>（22px）还大 —— 读者会把这个数字当成整篇的重点，层级倒置。</div>

<h3>根因（不在正文里，在外站样式表）</h3>
<div class="note">
样式来自 <code>https://dev-gpt.anchorwe.com/anchorai/css/blue.css</code>：
<code>.stat-value{{font-size:1.65rem;font-weight:700}}</code>（1.65rem = 26.4px）。<br>
本页基准：正文 14px ｜ 二级标题 18px ｜ 章节标题 22px。
<b>影响面：全站 76 个国别指南 · 2623 张统计卡片</b>（阈值口径见
<code>references/image-hosts.json._render_policy.max_font_px = 24</code>）。
</div>

<h3>修复后对比</h3>
<div class="row">
{stat_card('现状 26.4px', 26.4, '高于章节标题 20%')}
{stat_card('建议 20px（1.25rem）', 20, '落在二级标题与章节标题之间')}
</div>
<div class="ruler">修复后数值仍明显大于说明文字（12px），视觉上依旧是"重点"，但不再压过章节标题。</div>
<div class="ruler"><b>建议改法（一处生效）</b>：在 blue.css 里把 <code>.stat-value</code> 的
<code>font-size:1.65rem</code> 收敛到 <code>1.25rem</code>（20px）。</div>

</body></html>"""
    d = os.path.dirname(OUT)
    if d:
        os.makedirs(d, exist_ok=True)
    open(OUT, "w", encoding="utf-8").write(html)
    print("✅ 对照说明页 →", OUT)


if __name__ == "__main__":
    main()
