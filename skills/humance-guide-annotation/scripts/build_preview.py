#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
慧思国别指南「更新标注」批量预览生成器
========================================
把 build 产物（content_AFTER.html）渲染成可切换国家的批量预览页 —— 用于
「不上线先看效果」的验收场景。

关键做法：每个国家放进一个 `<iframe srcdoc>`，srcdoc 直接是完整 HTML 文档。
理由：指南正文本身就是「<!DOCTYPE html> + <head>(含 blue.css) + 正文」的完整文档，
用 iframe 承载才 100% 还原站内渲染（blue.css 作用域 + .nrz flex + ::after 徽标），
且 10 国的 CSS 互不污染。主页面不含任何站点 CSS，样式完全可控。

用法：
  python3 build_preview.py --config ../references/batches/b2-01-t.json \
          --workdir <build dir> --out <输出 HTML>
"""
import argparse
import html
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import guide_patch_lib as L  # noqa: E402

# 徽标文案不再本地抄一份：统一走 L.preview_chip()（文案真相源在 guide_patch_lib）


def esc(s):
    return html.escape(s or "", quote=True)


def build(cfg, workdir, out):
    ctrs = cfg["countries"]
    # ★ 页面侧计数一律走 L.page_notes()（Yoyo 2026-09-23 四轮：红色不上前端）。
    #   预览页也要跟着走同一口径 —— 否则预览说 6 条、页面只看得到 4 块，
    #   验收时又得先分辨"是页面错了还是预览错了"。
    alln = [n for v in ctrs.values() for n in v["notes"]]
    pgn = L.page_notes(alln)
    hidn = L.hidden_notes(alln)
    n_notes = len(pgn)
    n_hid = len(hidn)
    # 生效状态计数：口径唯一实现 = L.version_counts（别在这里另算一份）
    vc = L.version_counts(alln)
    n_eff, n_sch = vc["n_eff"], vc["n_sch"]

    tabs, panels = [], []
    for i, (slug, cc) in enumerate(ctrs.items()):
        try:
            doc = open(os.path.join(workdir, slug, "content_AFTER.html"), encoding="utf-8").read()
        except FileNotFoundError:
            doc = "<!DOCTYPE html><body>⚠️ 未找到构建产物</body>"
        act = " active" if i == 0 else ""
        _pg, _hid = L.page_notes(cc["notes"]), L.hidden_notes(cc["notes"])
        tabs.append(f'<button class="tab{act}" data-i="{i}">{esc(cc["name"])}'
                    f'<b>{len(_pg)}</b></button>')

        rows = []
        for n in _pg:
            lbl, ink, bg, bd = L.preview_chip(n)
            new_txt = n.get("new") or "—"
            rows.append(
                f'<tr><td class="rid">{esc(n["rid"].replace("PR-20260907-", "PR-"))}</td>'
                f'<td><span class="chip" style="color:{ink};background:{bg};border-color:{bd}">{lbl}</span></td>'
                f'<td class="fd">{esc(n.get("field") or n.get("title") or "")}'
                f'<div class="sec">{esc(n.get("anchor_title") or "")}'
                f'　·　{esc(n.get("kind") or n.get("status"))}</div></td>'
                f'<td class="old">{esc(n.get("old") or "—")}</td>'
                f'<td class="new">{new_txt}</td>'
                f'<td class="src">{esc(n.get("effective") or "—")}<div class="sec">{esc(n.get("source") or "")}'
                f'（{esc(n.get("tier") or "")}）'
                + (f' <a href="{esc(n["url"])}" target="_blank">原文 ↗</a>' if n.get("url") else "")
                + '</div></td></tr>')
        # 未上页面（红色 / 来源存疑）：预览页**照列但标灰**，让内部一眼看到"它没丢、
        # 只是不展示"；页面 iframe 里则完全没有它（那才是客户看到的）。
        for n in _hid:
            rows.append(
                f'<tr class="hidrow"><td class="rid">{esc(n["rid"].replace("PR-20260907-", "PR-"))}</td>'
                f'<td><span class="chip chiphid">🚫 未上页面</span></td>'
                f'<td class="fd">{esc(n.get("field") or n.get("title") or "")}'
                f'<div class="sec">{esc(n.get("anchor_title") or "")}'
                f'　·　仅台账待处理</div></td>'
                f'<td class="old">{esc(n.get("old") or "—")}</td>'
                f'<td class="new">{esc(n.get("new") or "—")}</td>'
                f'<td class="src">{esc(n.get("effective") or "—")}<div class="sec">{esc(n.get("source") or "")}'
                f'（{esc(n.get("tier") or "")}）</div></td></tr>')

        # ⚠️ 这里**刻意不复述**「正文版本」（2026-09-23 修正）★
        #   原实现显示 `cc["page_date"]`（原始正文日期，如 2026-05-29）——
        #   而页面版本条显示的是 `version_bar_dates()` 的月粒度「最新校验时间」（2026-09）。
        #   于是**同一字段在预览页与产物上给出两个值**（Yoyo 截图圈出的正是这处）：
        #     · 症状：预览页写 2026-05-29，产物页头写 2026-09，验收时不知该信哪个；
        #     · 根因：`review_date` 在配置**顶层**、country 节点没有，
        #       `version_bar_dates(cc)` 静默回落到 `page_date` ⇒ 又一个「复制而非引用」。
        #   处置不是"再算一遍并对齐"，而是**删掉这个副本**：
        #   iframe 里就是页面真实渲染，版本条本来就在页头可见（真渲染实测 y=78）。
        #   预览页 cmeta 的职责是"这一国有几条标注"，不是复述页面内容。
        #   ⇒ 判据仍是那句：**「我要改这个值，需要动几个文件？」答案是 1。**
        _hid_note = (f'　·　未上页面 <b>{len(_hid)}</b> 条（来源存疑，仅台账）' if _hid else '')
        panels.append(f'''<section class="panel{act}" data-i="{i}">
  <div class="chead">
    <div><span class="cname">{esc(cc["name"])}</span>
      <a class="clink" href="{esc(cc["guide_url"])}" target="_blank">{esc(cc["guide_url"])} ↗</a></div>
    <div class="cmeta">页面标注 <b>{len(_pg)}</b> 条{_hid_note}（页面版本条见下方 iframe 内页头）</div>
    <div class="cmeta cminner">【内部信息，不上页面】校对批次 <b>{esc(cfg["batch"])}</b>　·　Strapi <code>{esc(cc["documentId"])}</code></div>
  </div>
  <table class="chg"><thead><tr>
    <th>校对ID</th><th>状态</th><th>字段项 / 落位章节</th><th>现行值（原文保留）</th>
    <th>拟更新 / 核实结论</th><th>生效日期 / 来源</th></tr></thead>
    <tbody>{"".join(rows)}</tbody></table>
  <div class="stagehead">页面真实渲染效果（iframe，完整文档 + 站内 blue.css）
    <span>滚动查看：数据版本条在页头、章节标题右侧徽标、章节内联标注块</span></div>
  <iframe class="stage" srcdoc="{esc(doc)}" loading="lazy"></iframe>
</section>''')

    out_html = f'''<!DOCTYPE html><html lang="zh-CN"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(cfg["title"])}</title>
<style>
*{{box-sizing:border-box}}
body{{margin:0;background:#f4f6f9;color:#18181b;
 font:14px/1.65 -apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif}}
.wrap{{max-width:1180px;margin:0 auto;padding:26px 22px 70px}}
h1{{font-size:21px;margin:0 0 6px}}
.sub{{color:#52525b;font-size:13px}}
.badge{{display:inline-block;padding:3px 11px;border-radius:999px;font-size:12px;font-weight:700;
 background:#fff7ed;color:#b45309;border:1px solid #fed7aa;margin-left:8px;vertical-align:2px}}
.kpi{{display:flex;gap:12px;flex-wrap:wrap;margin:18px 0 22px}}
.k{{flex:1 1 150px;background:#fff;border:1px solid #e4e7ec;border-radius:10px;padding:13px 16px}}
.k b{{display:block;font-size:23px;color:#1565c0;line-height:1.3}}
.k span{{font-size:12px;color:#71717a}}
.note{{background:#fff;border:1px solid #e4e7ec;border-left:4px solid #1565c0;border-radius:8px;
 padding:12px 16px;margin:0 0 20px;font-size:13px;color:#3f3f46}}
.tabs{{display:flex;gap:7px;flex-wrap:wrap;margin-bottom:16px}}
.tab{{background:#fff;border:1px solid #dfe3e8;border-radius:8px;padding:8px 13px;cursor:pointer;
 font:inherit;font-size:13px;color:#3f3f46;display:flex;align-items:center;gap:7px}}
.tab b{{background:#eef2f7;border-radius:999px;padding:0 7px;font-size:11.5px;color:#1565c0}}
.tab.active{{background:#1565c0;border-color:#1565c0;color:#fff}}
.tab.active b{{background:rgba(255,255,255,.25);color:#fff}}
.panel{{display:none}} .panel.active{{display:block}}
.chead{{background:#fff;border:1px solid #e4e7ec;border-radius:10px 10px 0 0;padding:14px 16px;
 border-bottom:none}}
.cname{{font-size:16px;font-weight:700}}
.clink{{margin-left:12px;font-size:12px;color:#1565c0;text-decoration:none}}
.cmeta{{font-size:12px;color:#71717a;margin-top:5px}}
.cminner{{color:#a1a1aa;}}
.cmeta code{{background:#f4f4f5;padding:1px 6px;border-radius:4px;font-size:11.5px}}
table.chg{{width:100%;border-collapse:collapse;background:#fff;border:1px solid #e4e7ec;
 border-radius:0 0 10px 10px;overflow:hidden;font-size:12.5px}}
table.chg th{{background:#f7f9fc;color:#3f3f46;font-weight:600;text-align:left;padding:9px 11px;
 border-bottom:1px solid #e4e7ec;white-space:nowrap}}
table.chg td{{padding:10px 11px;border-bottom:1px solid #f0f2f5;vertical-align:top}}
table.chg tr:last-child td{{border-bottom:none}}
.rid{{font-family:ui-monospace,Menlo,monospace;color:#71717a;white-space:nowrap}}
.chip{{display:inline-block;padding:2px 9px;border-radius:999px;border:1px solid;font-size:11.5px;
 font-weight:600;white-space:nowrap}}
/* 未上页面（红色 / 来源存疑）：标灰 + 🚫，与页面上有的一眼分开 */
.hidrow td{{background:#fafafa;color:#a1a1aa}}
.chiphid{{color:#71717a;background:#f4f4f5;border-color:#e4e4e7}}
.k.khi b{{color:#a1a1aa}}
.fd{{font-weight:600;min-width:130px}} .sec{{font-weight:400;color:#8b8b93;font-size:11.5px;margin-top:3px}}
.old{{color:#71717a;max-width:230px}} .new{{color:#0d47a1;max-width:270px}}
.src{{color:#71717a;max-width:175px}} .src a{{color:#1565c0;text-decoration:none}}
.stagehead{{margin:20px 0 8px;font-size:13px;font-weight:600;color:#3f3f46}}
.stagehead span{{font-weight:400;color:#8b8b93;font-size:12px;margin-left:8px}}
iframe.stage{{width:100%;height:760px;border:1px solid #dfe3e8;border-radius:10px;background:#fff;
 display:block}}
@media(max-width:760px){{iframe.stage{{height:560px}}table.chg{{font-size:12px}}}}
</style></head><body><div class="wrap">
<h1>{esc(cfg["title"])}<span class="badge">本地测试 · 未上线生产</span></h1>
<div class="sub">批次 {esc(cfg["batch"])}　·　校对批次基准日 {esc(cfg.get("review_date", ""))}　·　
范围：{esc(cfg.get("scope", ""))}</div>
<div class="kpi">
  <div class="k"><b>{len(ctrs)}</b><span>国家 / 指南</span></div>
  <div class="k"><b>{n_notes}</b><span>页面标注条目</span></div>
  <div class="k"><b>{vc["n_pending"]}</b><span>{L.STATUS_TEXT["pending"]}</span></div>
  <div class="k"><b>{n_eff}</b><span>{L.EFF_TEXT["effective"]}</span></div>
  <div class="k"><b>{n_sch}</b><span>{L.EFF_TEXT["scheduled"]}</span></div>
  <div class="k"><b>{vc["n_keep"]}</b><span>{L.STATUS_TEXT["keep"]}</span></div>
  <div class="k khi"><b>{n_hid}</b><span>未上页面（来源存疑）</span></div>
</div>
<div class="note">{esc(cfg.get("note", ""))}<br>
<b>三条渲染红线已由门禁保证</b>：原值只增不减（还原校验通过）、正文数字零改动、
生效状态按「生效日 vs 写入日」判定并写明（{L.EFF_TEXT["effective"]}/{L.EFF_TEXT["scheduled"]}），
不写裸的「已生效」；页面文案为**客户向**（正文版本只到月，不显示校验时间）。<br>
<b>页面只出现两类颜色</b>：绿 = 不用管（有变更已生效 ∪ 维持不变，靠徽标文案区分）｜
橙黄 = 计划变更未落地。**红色（来源存疑）不上前端** —— 整条不注入页面、不进版本条计数，
只记飞书台账待处理（下方表格里标 🚫 那几行即为此类，页面 iframe 里看不到它们）。</div>
<div class="tabs">{"".join(tabs)}</div>
{"".join(panels)}
</div>
<script>
var tabs=document.querySelectorAll('.tab'),panels=document.querySelectorAll('.panel');
tabs.forEach(function(t){{t.addEventListener('click',function(){{
  tabs.forEach(function(x){{x.classList.remove('active')}});
  panels.forEach(function(x){{x.classList.remove('active')}});
  t.classList.add('active');
  document.querySelector('.panel[data-i="'+t.dataset.i+'"]').classList.add('active');
  window.scrollTo({{top:0,behavior:'smooth'}});
}});}});
</script></body></html>'''
    open(out, "w", encoding="utf-8").write(out_html)
    return out, len(ctrs), n_notes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                     "..", "references", "batches", "b2-01-t.json"))
    ap.add_argument("--workdir", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    cfg = json.load(open(a.config, encoding="utf-8"))
    p, nc, nn = build(cfg, a.workdir, a.out)
    print(f"✅ 预览已生成 → {p}（{nc} 国 / {nn} 条标注）")
    print(f"   体积 {os.path.getsize(p)/1024/1024:.2f} MB")


if __name__ == "__main__":
    main()
