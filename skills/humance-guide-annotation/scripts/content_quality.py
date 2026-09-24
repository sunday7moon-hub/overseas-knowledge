#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
内容质量门禁（全文）· 排版维度 + 配图维度
=========================================
Yoyo 2026-09-23 定：「上线前的 qc 全文，这些原来的问题也一起看下，归属内容质量-排版维度，或者配图」
—— 触发案例：① 阿联酋「核心要点」卡片数值 26.4px（比章节标题 22px 还大）且长值折行致卡片高度不齐；
② 台湾「福利」章节首图是 AI 生成图、图内中文全是乱码。

**为什么单独立这一维**：既有的门禁只证明「我们注入的那 6 条标注块」没问题，
证明不了**整篇正文**对客户是不是能看 —— 字号层级倒置、卡片错位、配图是占位图或乱码图，
这些是**历史遗留**的问题，一直在线上，只是没人拦。

两条通道，各管各的真值（不要混）：

| 通道 | 对象 | 能证明什么 | 需要网络 |
|---|---|---|---|
| **静态**（`scan_html`） | 产物或线上页的 HTML | 配图**来源**层的问题：占位图 / 相对路径 / 非自有域 / alt 敷衍 | 否（探测可选） |
| **渲染**（`render_check`） | 一个真实 URL 或本地文件 | 排版**呈现**层的真值：计算字号、横向溢出、同类卡片高度极差、渲染后破图 | 是 |

配图政策（自有域 / 占位图特征）唯一真相源 = `references/image-hosts.json`；
URL 可达性判定与缓存 **复用 `link_check.py`**（不许另写一套 urllib 探一遍）。

用法：
  # 静态扫本地产物（可写门禁）
  python3 content_quality.py --html <build>/content_AFTER.html --json-out _cq.json
  # 渲染扫线上页（排版真值；多个 URL 逗号分隔）
  python3 content_quality.py --live https://www.humancehr.com/country-guide/xxx/薪酬支付
  # 带外链探测（对非自有域图片做可达性校验，复用 link_check 缓存与继承）
  python3 content_quality.py --html ... --probe-images --img-cache <workdir>/_img_check.json
  # 全站普查（拉 Strapi 全部 country 文章）
  python3 content_quality.py --census --md-out 全站配图体检.md --csv-out 全站配图体检.csv

退出码 0 = 无阻断项。
"""
import argparse
import csv
import json
import os
import re
import ssl
import subprocess
import sys
import tempfile
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import link_check as LC  # noqa: E402  URL 可达性判定 / 缓存 / 继承的唯一实现

REF = os.path.join(os.path.dirname(HERE), "references")
IMG_CFG = json.load(open(os.path.join(REF, "image-hosts.json"), encoding="utf-8"))

OWN_HOSTS = set(IMG_CFG["own_hosts"])
PLACEHOLDER_PAT = re.compile("|".join(IMG_CFG["placeholder_patterns"]), re.I)
ALT_BAD_PAT = re.compile("|".join(IMG_CFG["alt_reject_patterns"]), re.I)
ALT_MIN = IMG_CFG.get("alt_min_len", 2)
ALT_MAX = IMG_CFG.get("alt_max_len", 60)
RP = IMG_CFG["_render_policy"]
MAX_FS = float(RP["max_font_px"])
MIN_FS = float(RP["min_font_px"])
CARD_TOL = float(RP["card_height_tol_px"])
UPSCALE = float(RP["upscale_ratio"])

CHROME = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
          "/Applications/Chromium.app/Contents/MacOS/Chromium"]
UA = LC.UA

# 判为「标题/允许大字号」的类名（章节标题、子标题）—— 正文内其余元素超 MAX_FS 即算层级倒置
HEADING_CLS = ("section-title", "subsection-title", "cg-version-bar")


def chrome():
    for c in CHROME:
        if os.path.exists(c):
            return c
    return None


# ── 基础工具 ─────────────────────────────────────────────────────────────────
def host_of(src):
    m = re.match(r"https?://([^/:]+)", src or "")
    return (m.group(1).lower() if m else "")


def _attr(tag, name):
    m = re.search(r'\b' + name + r'\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|([^\s>]+))', tag, re.I)
    if not m:
        return None
    v = m.group(1) if m.group(1) is not None else (m.group(2) if m.group(2) is not None else m.group(3))
    return v


def clean_text(s):
    s = re.sub(r"<[^>]+>", "", s or "")
    return re.sub(r"\s+", " ", s).strip()


def sections_of(html):
    """→ [(起始位置, 章节标题)]，用于把图片/元素归到章节。"""
    out = []
    for m in re.finditer(r'<h2[^>]*class="[^"]*section-title[^"]*"[^>]*>([\s\S]*?)</h2>', html, re.I):
        out.append((m.start(), clean_text(m.group(1))))
    if not out:
        out = [(0, "(未分章)")]
    return out


def section_at(sections, pos):
    cur = sections[0][1]
    for p, t in sections:
        if p <= pos:
            cur = t
        else:
            break
    return cur


def finding(cid, dim, level, item, detail, fix=""):
    return dict(id=cid, dim=dim, level=level, item=item, detail=detail, fix=fix)


# ── 已知缺陷基线（豁免单）────────────────────────────────────────────────────
# 为什么需要：全站共有的历史缺陷（如样式表里的字号）若一律阻断，等于**任何国家都上不了线**，
# 直到前端改完 —— 门禁就从"把关"变成了"停摆"。但直接放行又等于假装没看见。
# 正解是第三条路：**降级为告警 + 强制留痕 + 必须派单**（每条写清责任方/影响面/修法），
# 并且条目从基线删除之前，报告里一直看得见。
# ⚠️ 基线只豁免**列名的那一项**：同一检查项在基线之外的命中依然阻断。
#    本批自己引入的新问题不许进基线（那是在给自己开后门）。
QUALITY_BASELINE = os.path.join(REF, "quality-baseline.json")


def load_baseline(path=None):
    p = path if path is not None else QUALITY_BASELINE
    if not p or not os.path.exists(p):
        return {"entries": []}
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return {"entries": []}


def apply_baseline(finds, baseline):
    """把命中基线的阻断项降为告警（原地打标 known=KB-xxx）→ (findings, 被豁免条数)。"""
    ents = (baseline or {}).get("entries") or []
    n = 0
    for f in finds:
        if f["level"] != "block":
            continue
        for e in ents:
            if e.get("rule") != f["id"]:
                continue
            mc = e.get("match_cls")
            if mc and mc not in (f.get("detail", "") + f.get("item", "")):
                continue
            f["level"] = "warn"
            f["known"] = e.get("id")
            f["known_title"] = e.get("title")
            f["known_owner"] = e.get("owner")
            n += 1
            break
    return finds, n


# ── 通道一：静态扫 HTML（配图来源层）─────────────────────────────────────────
def scan_html(html, probe=False, img_cache=None, tries=3, timeout=12, workers=6, baseline=None):
    """扫一篇内容 HTML → (findings, imgs, probe_rows)。配图来源层的确定性问题在这里判。

    `baseline` 命中项会被降级为告警（理由见 `apply_baseline`）；不传则用默认基线文件。
    """
    sections = sections_of(html)
    imgs = []
    for m in re.finditer(r"<img\b[^>]*>", html, re.I):
        tag = m.group(0)
        src = _attr(tag, "src") or ""
        alt = _attr(tag, "alt")
        sec = section_at(sections, m.start())
        host = host_of(src)
        kind, level, why = classify_src(src, host, alt)
        imgs.append(dict(section=sec, src=src, host=host, alt=alt,
                         kind=kind, level=level, why=why,
                         cls=(_attr(tag, "class") or "")))

    finds = []
    # CI1 缺 src / 空 src
    for i in imgs:
        if i["kind"] == "empty":
            finds.append(finding("CI1", "配图", "block", i["section"],
                                 f"`<img>` 没有可用的 src（实际值 {i['src']!r}）",
                                 "补图或删掉这个空标签；空 img 会让读者看到破图图标"))
    # CI3 相对路径：线上必然 404（没有 host）
    for i in imgs:
        if i["kind"] == "relative":
            finds.append(finding("CI3", "配图", "block", i["section"],
                                 f"相对路径 src=`{i['src']}` —— 页面挂在 /country-guide/… 下，浏览器会去那个目录找图，必然 404",
                                 "换成绝对 URL（且托管到自有域）"))
    # CI4 占位图
    for i in imgs:
        if i["kind"] == "placeholder":
            finds.append(finding("CI4", "配图", "block", i["section"],
                                 f"占位图 `{i['src'][:90]}`（命中 placeholder/example/your-image 特征）",
                                 "这是模板残留，必须换成真实配图 —— 占位图出现在客户页等于『没做完』"))
    # CI2 data URI（体积大、不可缓存、不可复用）
    for i in imgs:
        if i["kind"] == "data":
            finds.append(finding("CI2", "配图", "warn", i["section"],
                                 f"内联 base64 图片（{len(i['src'])//1024} KB 文本塞在正文里）",
                                 "改存文件走自有图床；base64 会显著抬高页面体积且无法被 CDN 缓存"))
    # CI5 非自有域 → 告警 + 人工看图（不阻断：历史遗留多，逐批整改）
    for i in imgs:
        if i["kind"] == "external":
            finds.append(finding("CI5", "配图", "warn", i["section"],
                                 f"图片托管在非自有域 `{i['host']}`：`{i['src'][:80]}`",
                                 "自有图床化；外部域随时可能失效（短链尤其），且图内文字/版权无从控制"))
    # CI6 alt
    for i in imgs:
        bad, why = alt_problem(i["alt"])
        if bad:
            finds.append(finding("CI6", "配图", "block", i["section"],
                                 f"alt 不合格（{why}）：`{(i['alt'] or '')[:40]}`",
                                 "写一句能让盲人听懂的替代文本；alt 也是 SEO 与图挂掉时的兜底显示"))

    # CI7 可达性探测（可选，复用 link_check）
    probe_rows = []
    if probe:
        pairs = [(str(n), i["src"]) for n, i in enumerate(imgs)
                 if i["kind"] in ("external", "own")]
        if pairs:
            prev, _ = LC.load_cache(img_cache) if img_cache else (None, None)
            res, res_summ = LC.run(pairs, tries=tries, timeout=timeout, workers=workers, prev=prev)
            if img_cache:
                # ★ 必须把 prev 传进去合并：普查是**逐篇**调用本函数的，只写本次结果会把
                #   前 75 篇的结论全冲掉（2026-09-23 实测：跑完缓存里只剩最后一篇 12 张）。
                LC.save_cache(img_cache, res, res_summ, prev=prev)
            for r in res:
                v = LC.verdict(r)
                if v == "block":
                    i = imgs[int(r["rid"])]
                    finds.append(finding("CI7", "配图", "block", i["section"],
                                         f"图片打不开：{LC.LABEL.get(r['cls'], r['cls'])} «{str(r.get('msg'))[:70]}»\n     `{i['src'][:100]}`",
                                         "换图或修 URL —— 破图上线等于告诉客户『这页没人管』"))
                elif v == "manual":
                    probe_rows.append(dict(section=imgs[int(r["rid"])]["section"],
                                           src=r["url"], verdict=LC.LABEL.get(r["cls"], r["cls"])))
    apply_baseline(finds, baseline if baseline is not None else load_baseline())
    return finds, imgs, probe_rows


def classify_src(src, host, alt=None):
    """→ (kind, level, why)。kind: empty/data/relative/placeholder/external/own"""
    if not src or not src.strip():
        return "empty", "block", "无 src"
    s = src.strip()
    if s.startswith("data:"):
        return "data", "warn", "base64 内联"
    if PLACEHOLDER_PAT.search(s):
        return "placeholder", "block", "占位图特征"
    if s.startswith("//"):
        return "relative", "block", "协议相对路径"
    if not re.match(r"https?://", s, re.I):
        return "relative", "block", "无 host 的相对路径"
    return ("own", "ok", "自有域") if host in OWN_HOSTS else ("external", "warn", "非自有域")


def alt_problem(alt):
    """→ (是否不合格, 原因)"""
    if alt is None:
        return True, "完全没有 alt 属性"
    a = alt.strip()
    if len(a) < ALT_MIN:
        return True, "alt 为空"
    if ALT_BAD_PAT.search(a):
        return True, f"alt 是文件名/占位词（{a!r}）"
    if len(a) > ALT_MAX:
        return True, f"alt 过长（{len(a)} 字），会被读屏器念很久"
    return False, ""


# ── 通道二：渲染（排版真值 + 渲染后破图）─────────────────────────────────────
PROBE_JS = r"""
<pre id="__cq" style="display:none"></pre>
<script>
(function(){
  function isHeading(el){
    var c=(typeof el.className==='string'?el.className:'')||'';
    var t=el.tagName.toLowerCase();
    if(/^h[1-6]$/.test(t)) return true;
    %HEADING%;
    return false;
  }
  var out={};
  out.sections=document.querySelectorAll('.content-section').length;
  // 1) 正文内文本元素的字号体检 —— **只采集，不判定**。
  //    判定阈值与豁免单都会变，而缓存是跨天复用的：把"判定结果"写进缓存，等于让老缓存
  //    架空新规则（改严了不生效 = 假通过）。所以缓存里只放原始读数，判定每次重算。
  out.texts=[];
  document.querySelectorAll('.content-section *').forEach(function(el){
    if(out.texts.length>=800) return;
    if(el.children.length) return;
    var t=(el.textContent||'').trim(); if(!t) return;
    var px=parseFloat(getComputedStyle(el).fontSize);
    if(isNaN(px)) return;
    out.texts.push({px:Math.round(px*10)/10, tag:el.tagName.toLowerCase(),
      cls:((typeof el.className==='string'?el.className:'')||'').trim(),
      head:isHeading(el)?1:0, text:t.slice(0,34)});
  });
  // 2) 横向溢出
  out.overflow=[];
  document.querySelectorAll('.content-section').forEach(function(el){
    if(el.scrollWidth>el.clientWidth+2)
      out.overflow.push({cls:(el.className||'').slice(0,40), sw:el.scrollWidth, cw:el.clientWidth});
  });
  // 3) 同类卡片高度（.stat-box 一组 .stat-item）
  out.cards=[];
  document.querySelectorAll('.stat-box').forEach(function(box,bi){
    var hs=[].map.call(box.querySelectorAll('.stat-item'), function(x){
      return Math.round(x.getBoundingClientRect().height); });
    if(hs.length>1) out.cards.push({idx:bi, hs:hs, spread:Math.max.apply(null,hs)-Math.min.apply(null,hs)});
  });
  // 4) 图片渲染真值
  out.images=[];
  document.querySelectorAll('img').forEach(function(im){
    var r=im.getBoundingClientRect();
    out.images.push({src:(im.getAttribute('src')||'').slice(0,150), alt:im.getAttribute('alt'),
      nw:im.naturalWidth, nh:im.naturalHeight, w:Math.round(r.width), h:Math.round(r.height),
      visible:r.width>1&&r.height>1});
  });
  out.title=document.title;
  document.getElementById('__cq').textContent='@@CQ@@'+JSON.stringify(out)+'@@END@@';
})();
</script>
"""

# 渲染读数缓存格式版本：**探针采集结构或判定所需字段变了必须 +1**。
# 与 link_check.CACHE_VERSION 同一个道理：判定口径变了，老缓存不能当证据。
RENDER_CACHE_VERSION = 2


def thresholds():
    return dict(max_fs=MAX_FS, min_fs=MIN_FS, card_tol=CARD_TOL, upscale=UPSCALE)


def judge(raw, baseline=None, thr=None):
    """把探针**原始读数**判成 findings（含基线降级）。判定集中在这里，缓存只存 raw。

    → (findings, raw)。调用方可以放心缓存 raw：改阈值/改基线后重算即可生效。
    """
    f = render_findings(raw, thr=thr)
    apply_baseline(f, baseline if baseline is not None else load_baseline())
    return f, raw


def _build_fixture(target, tmpdir, tag):
    """target = http(s) URL 或本地文件 → 落成一个可渲染的 HTML（资产绝对化 + 去 CSP + 注入探针）。"""
    if re.match(r"https?://", target):
        raw = subprocess.run(
            ["curl", "-sL", "--max-time", "60", "-A", UA, target],
            capture_output=True, text=True).stdout
        if len(raw) < 2000:
            return None, f"抓取失败（{len(raw)} 字节）"
        h = raw
        h = re.sub(r'<meta[^>]+http-equiv="Content-Security-Policy"[^>]*>', "", h, flags=re.I)
        h = re.sub(r'(href|src)="/(?!/)', r'\1="https://www.humancehr.com/', h)
    else:
        if not os.path.exists(target):
            return None, f"文件不存在：{target}"
        h = open(target, encoding="utf-8").read()
    js = (PROBE_JS.replace("%HEADING%", "".join(
        f"if(c.indexOf('{c}')>=0) return true;" for c in HEADING_CLS)))
    h = h.replace("</body>", js + "</body>") if "</body>" in h else (h + js)
    f = os.path.join(tmpdir, f"cq_{tag}.html")
    open(f, "w", encoding="utf-8").write(h)
    return f, None


def render_check(target, tag="t", tmpdir=None, width=1280, budget=15000, baseline=None):
    """跑无头 Chrome 取计算样式与渲染真值 → (findings, raw_probe|None)。"""
    c = chrome()
    if not c:
        return [finding("CQ0", "排版", "warn", "-", "找不到 Chrome，渲染通道跳过", "装 Chrome/Chromium 后重跑")], None
    tmpdir = tmpdir or tempfile.mkdtemp(prefix="cq_")
    f, err = _build_fixture(target, tmpdir, tag)
    if err:
        return [finding("CQ0", "排版", "warn", "-", f"渲染通道跳过：{err}", "")], None
    p = subprocess.run([c, "--headless=new", "--disable-gpu", "--no-sandbox", "--hide-scrollbars",
                        f"--window-size={width},2400", f"--virtual-time-budget={budget}",
                        "--dump-dom", "file://" + f],
                       capture_output=True, text=True, timeout=300)
    m = re.search(r"@@CQ@@(.*?)@@END@@", p.stdout, re.S)
    if not m:
        return [finding("CQ0", "排版", "warn", "-", "渲染探针未回传（页面没加载出来？）", "")], None
    d = json.loads(m.group(1))
    f2, _ = judge(d, baseline)
    return f2, d


# ── 渲染读数缓存（只存 raw 读数，不存判定结果）────────────────────────────────
# 为什么坚持"只存 raw"：判定口径（阈值、豁免单）会演进，缓存会被跨天复用。
# 把判定结果写进缓存 = 老缓存架空新规则 —— 改严了不生效，就是**假通过**。
# （2026-09-23 踩过：加了已知缺陷基线，缓存里的老结论仍判阻断；反过来若基线放宽、
#   阈值收紧，缓存又会把该拦的放过。）
def load_render_cache(path):
    if not path or not os.path.exists(path):
        return {}
    try:
        d = json.load(open(path, encoding="utf-8"))
    except Exception:
        return {}
    if d.get("ver") != RENDER_CACHE_VERSION:
        return {}
    if d.get("thr") != thresholds():
        # 阈值变了 ⇒ 采集口径虽同，但为稳妥仍丢弃（避免"改阈值了但读数就不对"的误判）
        return {}
    return d.get("pages") or {}


def save_render_cache(path, pages):
    if not path:
        return
    json.dump(dict(ver=RENDER_CACHE_VERSION, thr=thresholds(), pages=pages),
              open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def render_findings(d, thr=None):
    """把探针回传的**原始读数**判成 findings。阈值走参数（不再由 JS 判），便于改口径后重算。"""
    t = dict(thresholds())
    t.update(thr or {})
    max_fs, min_fs, card_tol, upscale = t["max_fs"], t["min_fs"], t["card_tol"], t["upscale"]
    finds = []
    # ⚠️ fail-closed：抓到的页面里没有 content-section ⇒ 多半 URL 拼错/抓到 404
    # ⇒ 后面所有排版判定都没有意义。**这种情况必须报，不能悄悄算通过**。
    # （2026-09-23 实测：base 多带一段路径 → 渲染 404 页 → 0 条发现 → 假通过。）
    if not d.get("sections"):
        return [finding("CQ9", "排版", "block", "(整页)",
                        f"渲染目标里找不到任何 `.content-section`（页面标题 «{str(d.get('title'))[:50]}»）"
                        f" —— 多半 URL 不对或抓到了错误页，本轮排版判定无效",
                        "核对 guide_url / 章节标题拼出的 URL；确认页面真的渲染出了正文")]
    for x in d.get("texts", []):
        if x.get("head"):
            continue                      # 标题类元素允许大字号（h1–h6 / section-title 等）
        if x["px"] > max_fs:
            finds.append(finding("CT1", "排版", "block", "(正文)",
                                 f"字号 {x['px']}px 超出上限 {max_fs:g}px：`{x['tag']}.{x['cls']}` «{x['text']}»"
                                 f"\n     该值已高于页面章节标题（22px）—— 层级倒置，读者会误以为它是本篇重点",
                                 "把这类『数值展示』元素收敛到 1.25rem 上下，让 h2 > 数值"))
        elif x["px"] < min_fs:
            finds.append(finding("CT4", "排版", "block", "(正文)",
                                 f"字号 {x['px']}px 低于可读下限 {min_fs:g}px：`{x['tag']}.{x['cls']}` «{x['text']}»",
                                 "正文最小 12px；再小在移动端/高龄读者眼里等于不可读"))
    for x in d.get("overflow", []):
        finds.append(finding("CT2", "排版", "block", "(正文)",
                             f"横向溢出：`{x['cls']}` scrollWidth={x['sw']} > clientWidth={x['cw']}",
                             "窄屏会被裁切或出现横向滚动条 —— 检查表格/卡片是否写死了最小宽度"))
    for x in d.get("cards", []):
        if x["spread"] > card_tol:
            finds.append(finding("CT3", "排版", "block", "(正文)",
                                 f"第 {x['idx']+1} 组统计卡片高度不齐：各卡 {x['hs']}，极差 {x['spread']}px > {card_tol:g}px",
                                 "典型成因 = 某个数值过长被迫折行（如 `3,000-4,000迪拉姆` 折成 2 行）→ 缩短文案或把数值字号收小"))
    for im in d.get("images", []):
        if not im["visible"]:
            continue
        if im["nw"] == 0:
            finds.append(finding("CI8", "配图", "block", "(正文)",
                                 f"渲染后破图（naturalWidth=0）：`{im['src'][:100]}`",
                                 "浏览器真的加载不出来 —— 换图床或修 URL"))
        elif im["w"] > im["nw"] * upscale:
            finds.append(finding("CI9", "配图", "warn", "(正文)",
                                 f"图片被放大 {im['w']}/{im['nw']}px（>{upscale:g}×）会发虚：`{im['src'][:80]}`",
                                 "换更高分辨率原图，或把显示宽度收小"))
    return finds


# ── 汇总 ─────────────────────────────────────────────────────────────────────
def summarize(finds, imgs=None):
    blocks = [f for f in finds if f["level"] == "block"]
    warns = [f for f in finds if f["level"] == "warn"]
    known = [f for f in finds if f.get("known")]
    dims = {}
    for f in finds:
        d = dims.setdefault(f["dim"], {"block": 0, "warn": 0})
        d[f["level"]] = d.get(f["level"], 0) + 1
    s = dict(total=len(finds), block=len(blocks), warn=len(warns),
             known=len(known),
             known_ids=sorted({f["known"] for f in known}),
             dims=dims)   # ★ 必须带出去：md_report() 要按维度拆账，早先漏了 → KeyError
    if imgs is not None:
        s["images"] = len(imgs)
        s["images_own"] = sum(1 for i in imgs if i["kind"] == "own")
        s["images_external"] = sum(1 for i in imgs if i["kind"] == "external")
        s["images_block"] = sum(1 for i in imgs if i["level"] == "block")
    return s


def md_report(summ, finds, title="内容质量体检（排版 · 配图）"):
    L = [f"# {title}", ""]
    L.append(f"- 总问题 **{summ['total']}**（阻断 {summ['block']} · 告警 {summ['warn']}"
             + (f" · 其中**已知缺陷已派单** {summ.get('known', 0)}" if summ.get("known") else "")
             + "）")
    for d, v in summ["dims"].items():
        L.append(f"  - {d}：阻断 {v['block']} · 告警 {v['warn']}")
    if "images" in summ:
        L.append(f"- 图片 **{summ['images']}** 张（自有域 {summ['images_own']} · "
                 f"非自有域 {summ['images_external']} · 判定有问题的 {summ['images_block']}）")
    if summ.get("known"):
        L.append(f"- 已知缺陷基线条目命中：`{'`, `'.join(summ['known_ids'])}`"
                 f"（`references/quality-baseline.json`；整改完成后删条目即恢复阻断）")
    # 全站清单必须带「国家」列 —— 检查项里只有章节名，没有国家根本没法派单整改。
    # 单篇报告（slug 不在 findings 里）仍用旧列，保持原有报表格式不变。
    has_slug = any(f.get("slug") for f in finds)
    head = ("| 级别 | 国家 | 维度 | 编号 | 位置 | 问题 | 建议 |" if has_slug
            else "| 级别 | 维度 | 编号 | 位置 | 问题 | 建议 |")
    sep = "|:-:|---|---|:-:|---|---|---|" if has_slug else "|:-:|---|:-:|---|---|---|"
    L += ["", head, sep]
    order = {"block": 0, "warn": 1}
    # 全站清单按**国家**分组排（整改是按国家派单的），单篇报告仍按级别排
    key = ((lambda x: (x.get("slug") or "", order.get(x["level"], 9), x["id"])) if has_slug
           else (lambda x: (order.get(x["level"], 9), x["id"])))
    for f in sorted(finds, key=key):
        icon = "🛑" if f["level"] == "block" else ("📌" if f.get("known") else "⚠️")
        detail = f["detail"].replace("\n", " ").replace("|", "\\|")
        if f.get("known"):
            detail = f"【已知 {f['known']}·{f.get('known_owner', '')}】{detail}"
        if has_slug:
            L.append(f"| {icon} | `{f.get('slug') or '-'}` | {f['dim']} | {f['id']} | "
                     f"{f['item']} | {detail} | {f['fix']} |")
        else:
            L.append(f"| {icon} | {f['dim']} | {f['id']} | {f['item']} | {detail} | {f['fix']} |")
    return "\n".join(L) + "\n"


# ── 全站普查 ─────────────────────────────────────────────────────────────────
STRAPI = "https://admin.humancehr.com"


def fetch_country_articles():
    url = (f"{STRAPI}/api/articles?filters%5Bcategory%5D%5B%24eq%5D=country"
           f"&pagination%5BpageSize%5D=200")
    raw = subprocess.run(["curl", "-sL", "--max-time", "90", "-A", UA, url],
                         capture_output=True, text=True).stdout
    d = json.loads(raw)
    return (d.get("data") or [])


def census(probe=False, img_cache=None, csv_out=None, md_out=None, limit=None):
    arts = fetch_country_articles()
    if limit:
        arts = arts[:limit]
    rows, all_finds, tot_img = [], [], 0
    own_img = ext_img = 0
    for a in arts:
        slug, title = a.get("slug") or "?", a.get("title") or ""
        html = a.get("content") or ""
        finds, imgs, _ = scan_html(html, probe=probe, img_cache=img_cache)
        tot_img += len(imgs)
        own_img += sum(1 for i in imgs if i["kind"] == "own")
        ext_img += sum(1 for i in imgs if i["kind"] == "external")
        for f in finds:
            all_finds.append(dict(slug=slug, **f))
        if finds:
            rows.append(dict(slug=slug, title=title, images=len(imgs),
                             block=sum(1 for f in finds if f["level"] == "block"),
                             warn=sum(1 for f in finds if f["level"] == "warn"),
                             ids=",".join(sorted({f["id"] for f in finds}))))
    print(f"普查完成：{len(arts)} 篇国别指南 · 图片 {tot_img} 张 · 命中问题 {len(all_finds)} 条")
    by_id = {}
    for f in all_finds:
        by_id.setdefault(f["id"], []).append(f)
    print("\n=== 按检查项汇总 ===")
    for k in sorted(by_id):
        b = sum(1 for f in by_id[k] if f["level"] == "block")
        print(f"  {k}: 命中 {len(by_id[k])} 条（阻断 {b}）")

    if csv_out:
        with open(csv_out, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.DictWriter(fh, fieldnames=["slug", "id", "dim", "level", "item", "detail", "fix"])
            w.writeheader()
            for f in all_finds:
                w.writerow({k: f.get(k, "") for k in w.fieldnames})
        print(f"✅ CSV → {csv_out}")
    if md_out:
        summ = summarize(all_finds)
        # ★ 全站口径的图片账：summarize() 是按单篇算的，这里补成全站合计。
        #   三个键必须补齐 —— md_report 只要看到 "images" 就无条件读另外两个（早先漏了 → KeyError）。
        summ["images"] = tot_img
        summ["images_own"] = own_img
        summ["images_external"] = ext_img
        summ["images_block"] = sum(1 for f in all_finds if f["dim"] == "配图")
        # 全站普查不套豁免单：这一趟就是要把已知缺陷也数出来（豁免只在「上线闸门」生效）。
        open(md_out, "w", encoding="utf-8").write(
            md_report(summ, all_finds, title="全站国别指南 · 内容质量体检（配图维度，静态）"))
        print(f"✅ MD → {md_out}")
    return all_finds


# ── CLI ──────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description="内容质量门禁（排版 · 配图）")
    ap.add_argument("--html", help="静态扫这个 HTML（产物或页面快照）")
    ap.add_argument("--live", help="渲染扫这个 URL（可逗号分隔多个）—— 排版真值")
    ap.add_argument("--config", help="批次配置（与 --workdir 配合取 content_AFTER.html）")
    ap.add_argument("--workdir", help="构建目录")
    ap.add_argument("--slug", default="", help="只扫该 slug（配合 --config/--workdir）")
    ap.add_argument("--probe-images", action="store_true", help="对图片做可达性探测（复用 link_check，需网络）")
    ap.add_argument("--img-cache", help="图片探测缓存路径（默认 <workdir>/_img_check.json）")
    ap.add_argument("--census", action="store_true", help="全站普查（Strapi 全部 country 文章）")
    ap.add_argument("--limit", type=int, help="普查时只取前 N 篇（调试用）")
    ap.add_argument("--baseline", default=None,
                    help="已知缺陷基线（豁免单）路径；命中即由阻断降为告警。传 `none` 表示不用基线")
    ap.add_argument("--csv-out"), ap.add_argument("--md-out"), ap.add_argument("--json-out")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    if a.baseline == "none":
        BL = {"entries": []}
    elif a.baseline:
        BL = load_baseline(a.baseline)
    else:
        BL = load_baseline()

    if a.census:
        census(probe=a.probe_images, img_cache=a.img_cache, csv_out=a.csv_out, md_out=a.md_out,
               limit=a.limit)
        return 0

    finds, imgs, probe_rows, probe_raw = [], [], [], None

    if a.html or a.config:
        target = a.html
        if not target and a.config:
            cfg = json.load(open(a.config, encoding="utf-8"))
            slugs = [a.slug] if a.slug else list(cfg["countries"])
            for s in slugs:
                p = os.path.join(a.workdir or ".", s, "content_AFTER.html")
                if os.path.exists(p):
                    target = p
                    break
                print(f"⚠️ 找不到产物：{p}")
        if not target or not os.path.exists(target):
            sys.exit("⛔ 没有可扫的 HTML（--html 或 --config/--workdir）")
        html = open(target, encoding="utf-8").read()
        cache = a.img_cache or (os.path.join(a.workdir, "_img_check.json") if a.workdir else None)
        finds, imgs, probe_rows = scan_html(html, probe=a.probe_images, img_cache=cache, baseline=BL)
        if not a.quiet:
            print(f"静态扫毕：{target}")
            print(f"  图片 {len(imgs)} 张（自有域 {sum(1 for i in imgs if i['kind']=='own')} · "
                  f"非自有域 {sum(1 for i in imgs if i['kind']=='external')}）")

    if a.live:
        for u in [x.strip() for x in a.live.split(",") if x.strip()]:
            f2, raw = render_check(u, tag=re.sub(r"\W+", "_", u)[-24:], baseline=BL)
            finds += f2
            probe_raw = raw
            if not a.quiet:
                print(f"渲染扫毕：{u} → {len(f2)} 条")

    summ = summarize(finds, imgs if imgs else None)
    for f in sorted(finds, key=lambda x: (0 if x["level"] == "block" else 1, x["id"])):
        icon = "🛑" if f["level"] == "block" else "⚠️"
        print(f"  {icon} [{f['id']}] {f['dim']} · {f['item']}：{f['detail'].splitlines()[0]}")
    print(f"\n内容质量：共 {summ['total']} 条（阻断 {summ['block']} · 告警 {summ['warn']}"
          + (f" · 其中已知缺陷已派单 {summ['known']} 条 {'/'.join(summ['known_ids'])}"
             if summ.get("known") else "") + "）")
    if summ.get("known"):
        print("   📌 已知缺陷来自 references/quality-baseline.json（责任方/影响面/修法见该文件）——"
              "整改完成后删条目即恢复阻断")
    if probe_rows:
        print(f"\n⚠️ 需人工看图（探测给不出结论，{len(probe_rows)} 条）：")
        for r in probe_rows[:12]:
            print(f"   · {r['section']} {r['verdict']} {r['src'][:80]}")

    if a.json_out:
        json.dump(dict(summary=summ, findings=finds, images=imgs,
                       probe=probe_rows, render=probe_raw),
                  open(a.json_out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"✅ JSON → {a.json_out}")
    if a.md_out:
        open(a.md_out, "w", encoding="utf-8").write(md_report(summ, finds))
        print(f"✅ MD → {a.md_out}")
    return 1 if summ["block"] else 0


if __name__ == "__main__":
    sys.exit(main())
