#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
慧思国别指南「分章视图」预览生成器
====================================
为什么需要它：线上详情页**不是整篇渲染**，而是按章节分页渲染、且用一段硬编码骨架
（只搬"匹配到的那一个 content-section"）。所以用整篇 HTML 做的预览会**骗人** ——
版本条、徽标样式块在整篇预览里看得见，在线上却会被骨架丢掉。

本脚本用 `guide_patch_lib.simulate_frontend_section()`（前端算法的 Python 复刻）
逐章生成"线上真实会渲染出的 HTML"，做成可切换的预览页。**这才是能验收的预览。**

用法：
  python3 build_section_preview.py --config ../references/batches/uae-v3.json \
      --workdir /path/_pilot_UAE --out /path/预览.html
"""
import argparse
import html
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import guide_patch_lib as L  # noqa: E402

# 徽标文案不再本地抄一份：统一走 L.preview_chip()（文案真相源在 guide_patch_lib）


def esc(s):
    return html.escape(s or "", quote=True)


def plain(s):
    """去标签取纯文本 —— 表格里展示 old/new 用（它们本来带 <span>/<strong> 标记）。"""
    return esc(re.sub(r"<[^>]+>", "", s or "").strip())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--workdir", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    cfg = json.load(open(a.config, encoding="utf-8"))
    tabs, panels, stat_rows = [], [], []
    i = 0
    for slug, cc in cfg["countries"].items():
        cpath = os.path.join(a.workdir, slug, "content_AFTER.html")
        if not os.path.exists(cpath):
            sys.exit(f"❌ 缺构建产物：{cpath}（先跑 batch_guide_patch.py）")
        content = open(cpath, encoding="utf-8").read()
        by_sec, hid_by_sec = {}, {}
        for n in cc["notes"]:
            # 章节名从正文反推（配置里的 anchor_title 可能为空 —— build() 只在内存里补）
            _o, t = L._anchor_section(content, n["anchor"])
            # ★ 分流（Yoyo 2026-09-23 四轮）：红色（来源存疑）不进页面 ⇒ 本预览的
            #   "标注数"也必须只数页面条目，否则预览说 2 条、iframe 里一块都看不到。
            #   未上页面的照列但标灰（内部要知道它挂在哪一章）。
            (by_sec if L.on_page(n) else hid_by_sec).setdefault(t or "(未定位)", []).append(n)
        all_secs = [t for _o, t, _p in L._section_map(content)]
        # 展示顺序：含标注的章节在前，其余章节附后（每章都是线上真实渲染结果）
        touched = [t for t in all_secs if t in by_sec or t in hid_by_sec]
        order = touched + [t for t in all_secs if t not in by_sec and t not in hid_by_sec]
        for t in order:
            view = L.simulate_frontend_section(content, t)
            ns = by_sec.get(t, [])
            hns = hid_by_sec.get(t, [])
            act = " active" if i == 0 else ""
            _tbadge = (f'<b>{len(ns)}</b>' if ns else
                       ('<b class="bhid">0</b>' if hns else ''))
            tabs.append(f'<button class="tab{act}" data-i="{i}">{esc(t)}{_tbadge}</button>')
            badge = [f'<span class="chip" style="color:{k[1]};background:{k[2]};border-color:{k[3]}">{k[0]}</span>'
                     for k in (L.preview_chip(n) for n in ns)]
            rows = "".join(
                f'<tr><td class="rid">{esc(n["rid"].replace("PR-20260907-","PR-"))}</td>'
                f'<td><span class="chip" style="color:{L.preview_chip(n)[1]};'
                f'background:{L.preview_chip(n)[2]};border-color:{L.preview_chip(n)[3]}">'
                f'{L.preview_chip(n)[0]}</span></td>'
                f'<td class="fd">{plain(n.get("field") or n.get("title"))}</td>'
                f'<td class="old">{plain(n.get("old")) or "—"}</td>'
                f'<td class="new">{plain(n.get("new")) or "—"}</td>'
                f'<td class="src">{esc(n.get("effective") or "—")}<div class="sec">'
                f'{esc(n.get("source") or "")}（{esc(n.get("tier") or "")}）</div></td></tr>'
                for n in ns)
            # 未上页面（红色）的照列、标灰 —— 页面上没有它们，别让看预览的人以为漏了
            rows += "".join(
                f'<tr class="hidrow"><td class="rid">{esc(n["rid"].replace("PR-20260907-","PR-"))}</td>'
                f'<td><span class="chip chiphid">🚫 未上页面</span></td>'
                f'<td class="fd">{plain(n.get("field") or n.get("title"))}</td>'
                f'<td class="old">{plain(n.get("old")) or "—"}</td>'
                f'<td class="new">{plain(n.get("new")) or "—"}</td>'
                f'<td class="src">{esc(n.get("effective") or "—")}<div class="sec">'
                f'仅台账待处理</div></td></tr>'
                for n in hns)
            _hidtxt = (f'　·　未上页面 <b>{len(hns)}</b> 条（来源存疑，仅台账）' if hns else '')
            panels.append(f'''<section class="panel{act}" data-i="{i}">
  <div class="chead">
    <div><span class="cname">{esc(cc["name"])} › {esc(t)}</span>
      <span class="ctag">线上真实渲染（复刻前端骨架）</span></div>
    <div class="cmeta">页面标注 <b>{len(ns)}</b> 条{_hidtxt}　·　{' '.join(badge) if badge else '本章页面无标注'}
      　·　正文版本见下方页头（客户向口径只到月）</div>
  </div>
  {'<table class="chg"><thead><tr><th>校对ID</th><th>状态</th><th>字段项</th><th>现行值</th><th>拟更新 / 核实结论</th><th>生效 / 来源</th></tr></thead><tbody>' + rows + '</tbody></table>' if rows else ''}
  <div class="stagehead">↓ 前端按章渲染结果（<code>simulate_frontend_section</code>）—— 这就是用户在 <code>…/{esc(slug)}/{esc(t)}</code> 看到的</div>
  <iframe class="stage" srcdoc="{esc(view or '')}" loading="lazy"></iframe>
</section>''')
            stat_rows.append(dict(section=t, notes=len(ns), hid=len(hns),
                                  view_bytes=len(view or "")))
            i += 1

    out = f'''<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(cfg["title"])} · 分章视图</title><style>
*{{box-sizing:border-box}}
body{{margin:0;background:#f4f6f9;color:#18181b;font:14px/1.65 -apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif}}
.wrap{{max-width:1180px;margin:0 auto;padding:24px 22px 70px}}
h1{{font-size:19px;margin:0 0 6px}}
.lead{{color:#52525b;font-size:13px;margin:0 0 18px}}
.lead b{{color:#1565c0}}
.tabs{{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 14px}}
.tab{{border:1px solid #d4d4d8;background:#fff;border-radius:999px;padding:6px 14px;font-size:13px;cursor:pointer;color:#3f3f46}}
.tab.active{{background:#1565c0;border-color:#1565c0;color:#fff}}
.tab b{{display:inline-block;margin-left:7px;background:#ef4444;color:#fff;border-radius:999px;padding:0 7px;font-size:11px}}
.tab b.bhid{{background:#a1a1aa}}
.tab.active b{{background:rgba(255,255,255,.3)}}
/* 未上页面（红色 / 来源存疑）标灰 —— 页面上没有它们 */
.hidrow td{{background:#fafafa;color:#a1a1aa}}
.chiphid{{color:#71717a;background:#f4f4f5;border-color:#e4e4e7}}
.chead{{display:flex;justify-content:space-between;align-items:center;gap:14px;flex-wrap:wrap;margin-bottom:10px}}
.cname{{font-weight:600;font-size:15px}}
.ctag{{margin-left:8px;font-size:11.5px;color:#15803d;background:#dcfce7;border:1px solid #bbf7d0;border-radius:999px;padding:1px 9px}}
.cmeta{{color:#52525b;font-size:12.5px}}
table.chg{{width:100%;border-collapse:collapse;background:#fff;margin-bottom:12px;font-size:12.5px}}
table.chg th{{background:#1f4f8f;color:#fff;text-align:left;padding:7px 9px;font-weight:600}}
table.chg td{{border-bottom:1px solid #e4e4e7;padding:7px 9px;vertical-align:top}}
td.rid{{color:#71717a;font-family:ui-monospace,monospace;white-space:nowrap}}
td.old{{color:#71717a;text-decoration:line-through;max-width:190px}}
td.new{{color:#1565c0;font-weight:500;max-width:280px}}
td.src .sec,td.fd .sec{{color:#a1a1aa;font-size:11.5px;margin-top:2px}}
.chip{{display:inline-block;padding:1px 9px;border-radius:999px;border:1px solid;font-size:11.5px;font-weight:600;white-space:nowrap}}
.stagehead{{color:#52525b;font-size:12.5px;margin:4px 0 8px}}
.stage{{width:100%;height:820px;border:1px solid #d4d4d8;border-radius:10px;background:#fff}}
.panel{{display:none}} .panel.active{{display:block}}
</style></head><body><div class="wrap">
<h1>{esc(cfg["title"])} · 分章视图预览</h1>
<p class="lead">线上详情页是<b>按章节分页渲染</b>的：前端的硬编码骨架只搬"匹配到的那一个章节"，
放 <code>.nrz</code> 下或 <code>main-container</code> 顶层的元素、以及注入的 <code>&lt;style&gt;</code> <b>都会被丢弃</b>。
所以下面每个标签页都是<b>用前端算法复刻出来的真实渲染结果</b>，不是整篇拼出来的假预览。</p>
<div class="tabs">{"".join(tabs)}</div>
{"".join(panels)}
</div><script>
document.querySelectorAll('.tab').forEach(t=>t.addEventListener('click',()=>{{
  document.querySelectorAll('.tab').forEach(x=>x.classList.toggle('active',x===t));
  document.querySelectorAll('.panel').forEach(p=>p.classList.toggle('active',p.dataset.i===t.dataset.i));
}}));
</script></body></html>'''
    open(a.out, "w", encoding="utf-8").write(out)
    print(f"✅ 分章视图预览 → {a.out}")
    print(f"   共 {i} 章（页面含标注 {sum(1 for r in stat_rows if r['notes'])} 章"
          f"；另有 {sum(1 for r in stat_rows if r['hid'] and not r['notes'])} 章仅含"
          f"未上页面条目 ⇒ 页面无标注）")
    for r in stat_rows:
        print(f"     {r['section']:22} 页面标注{r['notes']}  未上页面{r['hid']}"
              f"  视图{r['view_bytes']:6} 字节")


if __name__ == "__main__":
    main()
