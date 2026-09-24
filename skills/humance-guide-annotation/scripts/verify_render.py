#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
慧思国别指南「更新标注」真实渲染验证
======================================
静态校验只能证明 HTML 长对了，证明不了「页面上好看」。本脚本用无头 Chrome 真渲染，
注入探针取 getBoundingClientRect / getComputedStyle，验五件事：

  1. 数据版本条是否仍在页头（y 小）且父节点是 content-section / main-container
     —— 防 .nrz flex 把它挤到页尾
  2. 章节徽标 ::after 是否真的生成出来（content 非 none）且 h2 文本本身干净（不污染 TOC）
  3. 标注块数量与状态色是否落地
  4. 版本条字色/底色是否 == 站内实测色（#0d47a1 / #f5f9ff）
  5. 左侧目录「小气泡数字」是否真的渲染出来（数字/配色/float/尺寸）—— 见 check_toc()
     注意：分章视图里**没有目录**（TOC 在页面骨架层渲染），所以这项单独合成 TOC 骨架来测

用法：
  python3 verify_render.py --workdir <build dir> [--slugs a,b] [--shot <目录>]
退出码 0 = 全部通过。
"""
import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import guide_patch_lib as L  # noqa: E402  目录气泡选择器等常量只在一处定义

CHROME = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
          "/Applications/Chromium.app/Contents/MacOS/Chromium"]

# ── 目录气泡检查（现场合成 TOC 骨架，离线可跑）────────────────────────────────
# 为什么必须单独造一个页面：详情页的真实 TOC 由 Astro island 在页面**骨架**里渲染，
# 而分章视图只包含一个 content-section —— 探针在那个页面里根本看不到目录。
# 这里按线上真实 DOM 复刻骨架（<nav class="table-of-contents"><ul><li><a href="#heading-N">），
# 并把 content 里的气泡 <style> 原样带上；用内联样式复刻 Tailwind 的
# `block text-sm py-2 px-3`（padding 8px/12px、字号 14px、行高 20px → 行高 36px），
# 保证 `.table-of-contents` 与 a 的度量与线上一致，不依赖外部 CSS（assets 带 hash，会失效）。
TOC_FIXTURE_HEAD = """<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<style>body{margin:0;font-family:system-ui,-apple-system,"PingFang SC",sans-serif;}
.toc-fixture a{display:block;padding:8px 12px;font-size:14px;line-height:20px;color:#52525b;text-decoration:none;}
.toc-fixture ul{list-style:none;margin:0;padding:0;}</style>
"""
TOC_FIXTURE_PROBE = r"""
<pre id="__p" style="display:none"></pre>
<script>
(function(){
  var rows=[];
  document.querySelectorAll('nav.table-of-contents a').forEach(function(a){
    var af=getComputedStyle(a,'::before');
    var r=a.getBoundingClientRect();
    rows.push({href:a.getAttribute('href'),
               text:a.textContent.replace(/\s+/g,''),
               content:af.content, bg:af.backgroundColor, float:af.float,
               w:Math.round(parseFloat(af.width)||0), h:Math.round(parseFloat(af.height)||0),
               aH:Math.round(r.height)});
  });
  document.getElementById('__p').textContent='@@TOC@@'+JSON.stringify(rows)+'@@END@@';
})();
</script>
"""


def _hex2rgb(h):
    h = h.lstrip("#")
    return "rgb(%d, %d, %d)" % (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def toc_css_block(content):
    """从 content 里抽出目录气泡的 <style> 块（@scope 包裹的那一块）。"""
    m = re.search(r"<style>\n" + re.escape(L.TOC_SCOPE) + r"\{[\s\S]*?</style>", content)
    return m.group(0) if m else ""


def toc_rules(content):
    """从 content 里抽出声明的目录气泡规则 → {heading_idx: (数字, 前景hex, 底色hex)}。"""
    block = toc_css_block(content)
    if not block:
        return {}
    out = {}
    for r in re.finditer(re.escape(L.TOC_SEL) + r'(\d+)"\]::before\{([^}]*)\}', block):
        body = r.group(2)
        num = re.search(r'content:"(\d+)"', body)
        fg = re.search(r"color:(#[0-9a-fA-F]{6})", body)
        bg = re.search(r"background:(#[0-9a-fA-F]{6})", body)
        if num and fg and bg:
            out[int(r.group(1))] = (num.group(1), fg.group(1), bg.group(1))
    return out


def check_toc(content, tmpdir, slug):
    """真渲染验证左侧目录气泡。返回 (是否通过, 说明列表, 明细)。"""
    errs = []
    rules = toc_rules(content)
    h2s = [re.sub(r"<[^>]*>", "", m.group(1)).strip()
           for m in re.finditer(r"<h2[^>]*>([\s\S]*?)</h2>", content, re.I)]
    h2s = [t for t in h2s if t]
    if not h2s:
        return True, ["无 h2，跳过"], {}
    items = "".join(
        f'<li class="toc-fixture"><a href="#heading-{i}">{t} </a></li>' for i, t in enumerate(h2s))
    html = (TOC_FIXTURE_HEAD + toc_css_block(content) +
            '\n</head><body><div style="width:180px;padding:12px;">'
            '<nav class="table-of-contents sticky top-8" aria-label="目录">'
            '<h3 style="font-size:15px;margin:0 0 12px;">目录</h3><ul>' + items +
            "</ul></nav></div>" + TOC_FIXTURE_PROBE + "</body></html>")
    tf = os.path.join(tmpdir, f"toc_{slug}.html")
    open(tf, "w", encoding="utf-8").write(html)
    p = subprocess.run([chrome(), "--headless=new", "--disable-gpu", "--no-sandbox",
                        "--hide-scrollbars", "--window-size=460,900",
                        "--virtual-time-budget=5000", "--dump-dom", "file://" + tf],
                       capture_output=True, text=True, timeout=120)
    m = re.search(r"@@TOC@@(.*?)@@END@@", p.stdout, re.S)
    if not m:
        return False, ["目录气泡探针未回传"], {}
    rows = json.loads(m.group(1))
    detail = {}
    for r in rows:
        idx = int(r["href"].replace("#heading-", ""))
        if idx not in rules:
            if r["content"] not in ("none", "normal", '""', ""):
                errs.append(f"heading-{idx} 无声明却渲染出气泡 {r['content']}")
            continue
        num, fg, bg = rules[idx]
        detail[idx] = dict(text=r["text"], num=num, bg=bg, aH=r["aH"])
        if r["content"].strip('"\' ') != num:
            errs.append(f"heading-{idx} 气泡数字={r['content']} 期望 {num}")
        if r["bg"] != _hex2rgb(bg):
            errs.append(f"heading-{idx} 气泡底色={r['bg']} 期望 {_hex2rgb(bg)}")
        if r["float"] != "right":
            errs.append(f"heading-{idx} 气泡 float={r['float']}（应为 right，否则会掉到下一行）")
        if r["w"] < 14 or r["h"] < 14:
            errs.append(f"heading-{idx} 气泡尺寸 {r['w']}x{r['h']} 过小")
        if r["aH"] > 60:
            errs.append(f"heading-{idx} 目录项被撑到 {r['aH']}px（气泡疑似挤出可视区）")
    for idx in rules:
        if idx not in detail:
            errs.append(f"heading-{idx} 声明了气泡但未渲染（序号越界？共 {len(h2s)} 个 h2）")
    return (not errs), errs, detail

PROBE = r"""
<pre id="__probe" style="display:none"></pre>
<script>
(function(){
  var out={ok:true,errs:[],warn:[]};
  function q(s){return document.querySelector(s)}
  function qa(s){return Array.prototype.slice.call(document.querySelectorAll(s))}
  var vb=q('.cg-version-bar');
  if(!vb){out.ok=false;out.errs.push('版本条未渲染')}
  else{
    var r=vb.getBoundingClientRect();
    out.vbar={y:Math.round(r.y+window.scrollY),w:Math.round(r.width),
              parent:(vb.parentElement&&vb.parentElement.className)||'',
              color:getComputedStyle(vb).color,bg:getComputedStyle(vb).backgroundColor,
              text:vb.textContent.replace(/\s+/g,' ').trim().slice(0,150)};
    if(out.vbar.y>400){out.ok=false;out.errs.push('版本条被推到 y='+out.vbar.y+'（疑似 flex 错位）')}
    if(out.vbar.parent.indexOf('content-section')<0&&out.vbar.parent.indexOf('main-container')<0){out.ok=false;out.errs.push('版本条父节点='+out.vbar.parent)}
    if(out.vbar.color.replace(/\s/g,'')!=='rgb(13,71,161)'){out.errs.push('版本条字色='+out.vbar.color+'（期望 #0d47a1）')}
    if(out.vbar.bg.replace(/\s/g,'')!=='rgb(245,249,255)'){out.errs.push('版本条底色='+out.vbar.bg+'（期望 #f5f9ff）')}
  }
  out.notes=qa('.cg-update-note').length;
  out.notesByStatus={};out.notesByTone={};
  qa('.cg-update-note').forEach(function(n){
    var s=n.getAttribute('data-cg-status');out.notesByStatus[s]=(out.notesByStatus[s]||0)+1;});
  // ★ 配色真值（2026-09-23 Yoyo 改口径：绿=变更已生效 / 橙黄=变更未生效 / 灰=无需更新）
  //   这里的期望色值由 Python 侧从 L.TONE **生成**塞进来，不在 JS 里手抄 ——
  //   手抄必然漂移，而"配色漂移"在页面上是**看得出来但没人报**的那类问题。
  var TONERGB=__TONERGB__;
  qa('.cg-update-note').forEach(function(n){
    var t=n.getAttribute('data-cg-tone')||'';
    out.notesByTone[t]=(out.notesByTone[t]||0)+1;
    var cs=getComputedStyle(n);
    var bg=cs.backgroundColor.replace(/\s/g,'');
    var bar=cs.borderLeftColor.replace(/\s/g,'');
    if(!TONERGB[t]){out.ok=false;out.errs.push('标注块配色档未知: '+t);return}
    if(bg!==TONERGB[t].bg){out.ok=false;out.errs.push('标注块底色='+bg+' 期望 '+TONERGB[t].bg+'（档 '+t+'）')}
    if(bar!==TONERGB[t].bar){out.ok=false;out.errs.push('标注块左侧色条='+bar+' 期望 '+TONERGB[t].bar+'（档 '+t+'）')}
  });
  out.badges=[];
  qa('h2[data-cg-badge]').forEach(function(h){
    var txt=h.textContent.replace(/\s+/g,'');
    var af=getComputedStyle(h,'::after').content;
    var tone=h.getAttribute('data-cg-tone')||'';
    out.badges.push({h2:txt,badgeAttr:h.getAttribute('data-cg-badge'),
                     after:af,state:h.getAttribute('data-cg-state'),tone:tone});
    if(__STALEWORDS__.some(function(w){return txt.indexOf(w)>=0})){
      out.ok=false;out.errs.push('h2 文本被徽标污染: '+txt)}
    if(!af||af==='none'||af==='normal'||af==='""'){out.errs.push('徽标 ::after 未生成: '+txt)}
    if(!TONERGB[tone]){out.ok=false;out.errs.push('章节徽标配色档未知: '+tone);return}
    var abg=getComputedStyle(h,'::after').backgroundColor.replace(/\s/g,'');
    if(abg!==TONERGB[tone].chip){
      out.ok=false;out.errs.push('章节徽标底色='+abg+' 期望 '+TONERGB[tone].chip+'（档 '+tone+'）')}
  });
  if(out.badges.length!==qa('h2[data-cg-badge]').length){out.errs.push('徽标数不符')}
  out.h2total=qa('h2.section-title').length;
  out.bodylen=document.documentElement.outerHTML.length;
  document.getElementById('__probe').textContent='@@PROBE@@'+JSON.stringify(out)+'@@END@@';
})();
</script>
"""

# ── JS 里的「污染词表」由 Python 常量**生成**，不手抄 ────────────────────────────
# 探针是注入到页面里的字符串，没法 import Python 常量。以前这里手抄了
# 「待更新 / 已核实 / 计划更新」三个字面量 —— 文案一改，手抄那份不会跟着走，
# 门禁会**静默漏判**（本轮状态文案回执正是这种情形）。现从常量拼 JSON 数组塞进去。
_STALE_WORDS = list(dict.fromkeys(
    L.STALE_COPY + list(L.STATUS_TEXT.values())
    + [v for v in L.EFF_TEXT.values() if v]))
PROBE = PROBE.replace("__STALEWORDS__", json.dumps(_STALE_WORDS, ensure_ascii=False))

# ── 配色真值的期望值同样由 L.TONE **生成**（同一个道理：手抄必漂移）─────────────
# 格式必须与 Chrome 的 getComputedStyle 输出可比：`rgb(240,253,244)`（去空格）。
_TONERGB = {t: dict(bg=_hex2rgb(c["bg"]).replace(", ", ","),
                    bar=_hex2rgb(c["bar"]).replace(", ", ","),
                    chip=_hex2rgb(c["chip_bg"]).replace(", ", ","))
            for t, c in L.TONE.items()}
PROBE = PROBE.replace("__TONERGB__", json.dumps(_TONERGB))


def chrome():
    for c in CHROME:
        if os.path.exists(c):
            return c
    sys.exit("❌ 未找到 Chrome/Chromium")


def run_one(path, tmpdir, shot=None):
    src = open(path, encoding="utf-8").read()
    body = src.replace("</html>", PROBE + "\n</html>") if "</html>" in src else src + PROBE
    tf = os.path.join(tmpdir, os.path.basename(os.path.dirname(path)) + ".html")
    open(tf, "w", encoding="utf-8").write(body)
    cmd = [chrome(), "--headless=new", "--disable-gpu", "--no-sandbox", "--hide-scrollbars",
           "--virtual-time-budget=6000", "--dump-dom", "file://" + tf]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    m = re.search(r"@@PROBE@@(.*?)@@END@@", p.stdout, re.S)
    if not m:
        return dict(ok=False, errs=["探针未回传（渲染失败？）"], raw=p.stderr[-300:])
    out = json.loads(m.group(1))
    if "errs" not in out:
        out["errs"] = []
    # ⑥ 链接口径兜底：渲染后的 DOM 里，标注块内不得出现 official/internal 以外的链接
    seen_off = p.stdout.count(">官方原文 ↗</a>")
    out["official_links"] = seen_off
    for blk in re.findall(r'<div class="cg-update-note"[\s\S]*?\n</div>', p.stdout):
        for u in re.findall(r'href="(https?://[^"]+)"', blk):
            vd, h = L.classify_source(u)
            if vd not in ("official", "internal"):
                out["errs"].append(f"标注块内出现非法链接（{vd}: {h}）")
    if shot:
        os.makedirs(shot, exist_ok=True)
        sf = os.path.join(shot, os.path.basename(os.path.dirname(path)) + ".png")
        subprocess.run([chrome(), "--headless=new", "--disable-gpu", "--no-sandbox",
                        "--hide-scrollbars", "--window-size=1400,2200",
                        "--virtual-time-budget=6000", "--screenshot=" + sf, "file://" + tf],
                       capture_output=True, text=True, timeout=180)
        out["shot"] = sf
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir", required=True)
    ap.add_argument("--slugs", default=None)
    ap.add_argument("--shot", default=None)
    ap.add_argument("--json-out", default=None)
    a = ap.parse_args()

    only = set(a.slugs.split(",")) if a.slugs else None
    files = sorted(glob.glob(os.path.join(a.workdir, "*", "content_AFTER.html")))
    if only:
        files = [f for f in files if os.path.basename(os.path.dirname(f)) in only]
    if not files:
        sys.exit("❌ 没找到 content_AFTER.html")

    tmpdir = tempfile.mkdtemp(prefix="cgverify_")
    allres, bad = {}, 0
    try:
        for f in files:
            slug = os.path.basename(os.path.dirname(f))
            r = run_one(f, tmpdir, a.shot)
            # 目录气泡：另起一个合成 TOC 页面做真渲染（分章视图里没有目录，必须单独测）
            t_ok, t_errs, t_detail = check_toc(open(f, encoding="utf-8").read(), tmpdir, slug)
            r["toc"] = dict(ok=t_ok, errs=t_errs, detail=t_detail)
            if not t_ok:
                r.setdefault("errs", []).extend(["目录气泡: " + e for e in t_errs[:5]])
            allres[slug] = r
            ok = r.get("ok") and not r.get("errs")
            if r.get("errs"):
                ok = False
            bad += 0 if ok else 1
            vb = r.get("vbar") or {}
            tinfo = "、".join(f'{v["text"][:6]}={v["num"]}' for v in t_detail.values()) or "无"
            print(f"{'✅' if ok else '❌'} {slug[:36]:36} "
                  f"版本条 y={vb.get('y','-')} parent={str(vb.get('parent'))[:14]:14} "
                  f"标注={r.get('notes','-')} 官方链接={r.get('official_links','-')} "
                  f"徽标={len(r.get('badges',[]))} h2={r.get('h2total','-')}")
            print(f"     目录气泡 {len(t_detail)} 章：{tinfo}")
            _tn = r.get("notesByTone") or {}
            if _tn:
                print("     配色（真渲染实测）" + "、".join(
                    f"{k}×{v}" for k, v in sorted(_tn.items())))
            for e in r.get("errs", [])[:4]:
                print(f"      ✗ {e}")
            for e in r.get("warn", [])[:2]:
                print(f"      ! {e}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    if a.json_out:
        json.dump(allres, open(a.json_out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n{'-'*66}\n真渲染验证：{'✅ 全部通过' if bad == 0 else f'❌ {bad} 国异常'}（共 {len(files)} 国）")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
