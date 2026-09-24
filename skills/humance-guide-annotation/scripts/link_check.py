#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
官方外链「可打开」校验（唯一实现）
====================================
Yoyo 2026-09-23 定：**上线前 QC 要校验官方外链，是能打开的**。
本模块是这条口径的**唯一实现** —— qc_gate.py（一次校验）与 verify_secondary.py
（二次/三次校验）都 import 本文件，别在别处再写一份 urllib/requests 探测逻辑。

── 为什么要分五类，而不是「通/不通」二元（★ 实测得出的，别再退回二元）───────────
2026-09-23 在本机实测同一批官方链接，**同一 URL 连续两次结果不同**：
    u.ae/.../emiratis-...   → 第一次 404，第二次 000（CONNECT tunnel failed, 502）
    gpssa.gov.ae/...        → 第一次 200，第二次 000（25s 超时）
可见「本机网络/代理状态」会污染结论。若把「连不上」直接判成「链接坏了」，
就会出现两种恶果：① 好链接被误杀（误拦）② 网络一抖门禁就红，大家开始绕过门禁（形同没有）。
所以判定必须**区分「内容问题」与「环境问题」**：

    ok            HTTP 2xx/3xx（跟完重定向）           → 通过
    blocked       HTTP 401/403/406/429/451             → 链接存在，站点拦自动化 ⇒ 环境/反爬问题
    dead          HTTP 404/410/其他 4xx               → **内容问题：链接写错了/已下线 ⇒ 阻断**
    server_error  HTTP 5xx                             → 站点故障，暂时性 ⇒ 不判死
    unreachable   DNS/连接/超时/TLS/代理（无 HTTP 码）  → 环境问题 ⇒ 不判死

→**只有 dead 阻断**；blocked / server_error / unreachable 一律「需人工点验」：
  记进台账「外链状态」= ⚠️ 需人工点验，但不阻断落线（本机不可达 ≠ 客户打不开）。
  理由写在这里：**门禁不能因为自己网络不好而拦业务**，但**死链必须拦**。

── ⚠️ 只看状态码不够：必须"验真响应体"（★ 2026-09-23 实测踩坑）──────────────────
本机网络是 **MITM 代理**，会偶发把响应变成 HTTP 200（伪响应）。实测同一死链：
  curl 连测 6 次全 404、urllib 连测 3 次全 404，但另有一次经代理回来是 **200**。
⇒ 若只读状态码，**死链会被判成「可打开」**（假放行比漏拦更糟：客户点开就是 404）。
⇒ 所以 **判 ok 必须同时满足**：① 2xx/3xx ② 响应体非空 ③ 不含代理/网关错误页特征。
   凡"状态 200 但体不像真页面"的，降级为 unreachable（不判死、但要人工点验），
   并把「HTTP 200 但疑似代理伪响应」写进结论 —— 让人看得见这个降级发生过。

── 重试（抗抖动）────────────────────────────────────────────────────────────
默认 tries=3：任一次成功即判 ok（成功后不再试）；全部失败才按优先级归并。
归并优先级（从严到宽）：dead > server_error > blocked > unreachable
  · 出现过 dead 且从未成功 ⇒ dead（真死链，重试也 404）
  · 否则取最"确定"的那个结论，避免把一次偶发超时当成全部结论。

── 并发 ────────────────────────────────────────────────────────────────────
ThreadPoolExecutor，默认 5 并发 —— 单批 ≤10 条链接、最坏 3×12s，几秒内出结论。

用法（也可独立跑，把结论落成 artifact）：
  python3 link_check.py --config ../references/batches/uae-v3.json
  python3 link_check.py --url https://u.ae/xxx --url https://gpssa.gov.ae/yyy
  python3 link_check.py --config ... --json-out _link_check.json
退出码：0 = 无死链（可能含需人工点验项）；1 = 存在死链。
"""
import argparse
import datetime
import json
import os
import re
import socket
import ssl
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126 Safari/537.36")

# 分类常量（唯一一处定义）
OK = "ok"
BLOCKED = "blocked"
DEAD = "dead"
SERVER_ERROR = "server_error"
UNREACHABLE = "unreachable"

# 归并优先级：越靠前越"确定"
_RANK = [DEAD, SERVER_ERROR, BLOCKED, UNREACHABLE]

# 需要人工点验的分类（非 ok 且非 dead）—— 台账「外链状态」会用到
MANUAL = (BLOCKED, SERVER_ERROR, UNREACHABLE)

# 人类可读标签（页面/台账/报告共用；别在别处再写一份）
LABEL = {
    OK: "✅ 可打开",
    BLOCKED: "⚠️ 需人工点验（站点拦截自动化）",
    DEAD: "❌ 死链",
    SERVER_ERROR: "⚠️ 需人工点验（站点故障）",
    UNREACHABLE: "⚠️ 需人工点验（本机不可达）",
}


def classify_code(code):
    """HTTP 状态码 → 分类（唯一实现）。"""
    if code is None:
        return UNREACHABLE
    if 200 <= code < 400:
        return OK
    if code in (401, 403, 406, 429, 451):
        return BLOCKED
    if 500 <= code < 600:
        return SERVER_ERROR
    if 400 <= code < 500:          # 404 / 410 / 400 / 405 … 一律按内容问题处理
        return DEAD
    return UNREACHABLE


# ── 响应体"验真"（★ 实测踩坑：本机是 MITM 代理，会返回**伪 200**）─────────────────
# 2026-09-23 实测：`u.ae/.../Sector-of-employment/...`（大写 S，真死链）用 curl 连测 6 次
# 全是 404、用 urllib 连测 3 次也全是 404，但偶有一次经代理回来是 **HTTP 200**。
# ⇒ **只看状态码会把死链判成"可打开"**（假放行，比漏拦更糟：客户点开是 404）。
# ⇒ 判 ok 必须同时满足：① 2xx/3xx ② 响应体非空 ③ 不含代理/网关错误页特征。
# 反向：判 dead 不要求"每一次都 404"，只要**出现过 4xx 且从未有过验真 ok** 即判死。
SUSPECT_BODY = ("connect tunnel failed", "tunnel connection failed", "bad gateway",
                "err_proxy", "proxy authentication", "502 bad gateway",
                "504 gateway time-out")
# 故意**不放** "nginx" 这类泛词 —— 真页面里也会出现，会误伤（把好链接降级成"需人工点验"）。

# ── 站点拦截页（WAF）识别（★ 2026-09-23 第二次踩坑，比伪 200 更隐蔽）──────────
# 实测：`gpssa.gov.ae` 某条链接经代理返回 **HTTP 200**，响应体是站点 WAF 的拒绝页，
# `<title>Request Rejected</title>`，正文只有 "The requested URL was rejected…"。
# 状态码 200 + 正文非空 ⇒ 老的 `_sniff()` 判它"可信" ⇒ **判成 ✅ 可打开**。
# 这是**假放行**：台账里写着「可打开」，客户点开是拒绝页。比漏拦更糟。
# ⇒ 判 ok 必须再加一条：**页面标题不能是拦截/错误页的标题**。
# 只认标题（不认正文关键词）—— 标题精确、误伤概率极低；正文里出现 "access denied"
# 的合法页面太多了（论坛、公告、帮助中心都会写）。
WAF_TITLE = ("request rejected", "access denied", "attention required",
             "just a moment", "are you a robot", "security check",
             "you have been blocked", "bot verification", "captcha",
             "access to this page has been denied", "verifying your browser")
# 200 + 这类标题 ⇒ 其实是**内容不存在**（站点把 404 渲染成 200），按死链处理
GONE_TITLE = ("404 not found", "page not found", "page cannot be found",
              "页面不存在", "找不到页面", "网页不存在")

# 缓存格式版本：**分类算法改了必须 +1**，否则老缓存里的错误结论会被 _inherit 继续继承。
# 踩过：WAF 拦截页被老算法判 ok 写进缓存，改完算法后仍被"继承上次验真结论"保留下来。
# v3（2026-09-23）：新增 DNS 前置判定（域名不存在 → dead，不再含糊成 unreachable）。
CACHE_VERSION = 3
_SUSPECT_TITLE_HINT = WAF_TITLE + GONE_TITLE


def _sniff(r):
    """读一小段响应体做验真 → (kind, 摘要)。

    kind ∈ `"ok"` 可信 ｜ `"proxy"` 代理/网关错误页 ｜ `"waf"` 站点拦截页 ｜ `"gone"` 内容不存在。
    调用方按 kind 决定最终分类 —— **不要把 kind 丢掉只看摘要字符串**。
    """
    raw = r.read(2048) or b""
    if not raw.strip():
        return "proxy", "响应体为空（疑似代理伪响应）"
    head = raw[:700].decode("utf-8", "ignore").strip()
    low = head.lower()
    if any(s in low for s in SUSPECT_BODY):
        return "proxy", "疑似代理/网关错误页"
    m = re.search(r"<title[^>]*>([\s\S]{0,90}?)</title>", head, re.I)
    title = m.group(1).strip() if m else ""
    tl = title.lower()
    if title and any(s in tl for s in WAF_TITLE):
        return "waf", f"页面标题为拦截页「{title}」"
    if title and any(s in tl for s in GONE_TITLE):
        return "gone", f"页面标题为「{title}」"
    return "ok", (title or head[:60].replace("\n", " "))


def classify_response(kind, code):
    """把 (`_sniff` 的 kind, HTTP 状态码) 归成一个分类 —— **唯一实现**。

    `probe_once` 与负向测试都调它，避免测试里另抄一份 kind→cls 映射
    （那种"另抄一份"正是口径漂移的起点）。
    """
    if kind == "proxy":
        return UNREACHABLE      # 我方网络/代理问题 → 走 L9 人工
    if kind == "waf":
        return BLOCKED          # 站点反爬（HTTP 200 假象）→ 走 L9 人工
    if kind == "gone":
        return DEAD             # 站点把 404 渲染成 200 → L5 直接拦
    return classify_code(code)


def dns_ok(host, tries=2, pause=0.4):
    """域名能不能解析 → bool。**这是「确定性死链」与「我方网络出问题」的分界线**。

    踩坑来源（2026-09-23）：阿联酋指南「劳动法规」章节首图挂在 `s.cocecdn.net` —— 把
    `coze` 拼成了 `coce`，域名根本不存在。但旧逻辑把 DNS 失败一并归到 `unreachable`
    （「本机不可达」），于是它只是一条「待人工点验」的含糊项 —— 而真相是**这图必然打不开**，
    没有任何人工点验的必要。把两件事混为一谈 = 把确定性缺陷降级成概率性怀疑。
    """
    if not host:
        return True
    for i in range(max(1, tries)):
        try:
            socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
            return True
        except Exception:
            if i + 1 < max(1, tries):
                time.sleep(pause)
    return False


def probe_once(url, timeout=12):
    """单次探测 → dict(cls, msg, code, final, sniff)。不抛异常。"""
    h = _host(url)
    if not dns_ok(h):
        # 域名不存在 = 确定性死链（不是"我连不上"）。DNS 查两次都失败才这么判。
        return dict(cls=DEAD, msg=f"域名不存在（DNS 解析失败：{h}）",
                    code=None, final=url, sniff="dns-nxdomain")
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, method="GET", headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/pdf,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8"})
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=timeout) as r:
            kind, sniff = _sniff(r)
            if kind == "ok":
                return dict(cls=classify_code(r.status), msg=f"HTTP {r.status} «{sniff}»",
                            code=r.status, final=r.geturl(), sniff=sniff)
            # 不可信响应：把"为什么不可信"写进 msg，台账/报告里能直接看出根因
            return dict(cls=classify_response(kind, r.status),
                        msg=f"HTTP {r.status} 但{sniff}",
                        code=r.status, final=r.geturl(), sniff=sniff)
    except urllib.error.HTTPError as e:
        return dict(cls=classify_code(e.code), msg=f"HTTP {e.code}",
                    code=e.code, final=getattr(e, "url", url), sniff="")
    except Exception as e:
        # URLError/超时/DNS/TLS/代理 CONNECT 失败 —— 全归 unreachable（环境问题，不判死）
        msg = str(getattr(e, "reason", e))[:60].replace("\n", " ")
        return dict(cls=UNREACHABLE, msg=f"{type(e).__name__}: {msg}",
                    code=None, final=url, sniff="")


def _merge(classes):
    """多次探测结果归并 → 最终分类（唯一实现）。

    规则：**只要有一次"验真 ok"就算通**（网络抖动不该误杀好链接）；
    否则按 dead > server_error > blocked > unreachable 取最确定者。
    """
    if OK in classes:
        return OK
    for c in _RANK:
        if c in classes:
            return c
    return UNREACHABLE


def check_url(url, tries=3, timeout=12):
    """探测单个 URL（含重试）→ dict(url, host, cls, label, samples, tries)。

    cls ∈ {ok, blocked, dead, server_error, unreachable}
    """
    samples, cls, last = [], UNREACHABLE, {}
    for _ in range(max(1, tries)):
        last = probe_once(url, timeout)
        samples.append(f"{last['cls']}:{last['msg']}")
        cls = _merge([s.split(":", 1)[0] for s in samples])
        if cls == OK:                       # 验真成功即停，不浪费时间
            break
    return dict(url=url, host=_host(url), cls=cls, label=LABEL[cls],
                samples=samples, tries=len(samples), code=last.get("code"),
                final=last.get("final"), sniff=last.get("sniff"),
                # ★ 必须带出 msg：调用方（内容质量 CI7 / 台账）要写「为什么打不开」。
                #   以前只有 samples，消费方取 r['msg'] 全拿到 None ⇒ 报告里一排 «None»，
                #   等于把「DNS 解析失败」这种最关键的诊断信息丢了。
                msg=last.get("msg"),
                at=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


def _host(url):
    m = re.match(r"https?://([^/?#]+)", url or "", re.I)
    return (m.group(1).lower() if m else "")


def check_urls(urls, tries=3, timeout=12, workers=5):
    """并发探测一组 URL（保序）→ [dict]。去重后探测，再按原始顺序还原。"""
    uniq = list(dict.fromkeys(u for u in urls if u))
    if not uniq:
        return []
    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(uniq)))) as ex:
        got = list(ex.map(lambda u: check_url(u, tries=tries, timeout=timeout), uniq))
    by_url = {g["url"]: g for g in got}
    return [by_url[u] for u in urls if u]


def verdict(res):
    """分类 → 门禁口径 {'pass' | 'block' | 'manual'}（唯一实现）。

    pass   = 可打开
    block  = 死链 ⇒ **阻断落线**
    manual = 环境/反爬问题 ⇒ 需人工点验，不阻断（结论进台账「外链状态」）
    """
    if res["cls"] == OK:
        return "pass"
    if res["cls"] == DEAD:
        return "block"
    return "manual"


def ledger_text(res, human=None):
    """探测结论 → 台账「外链状态」字段值（页面不出现，只进台账）。

    取值优先级：**人工点验留痕 > 机器验真 ok > 机器结论**。
    两个踩过的坑（都在台账里看得见，别再犯）：
      · 不能取 `samples[-1]` —— 继承场景下 samples = 上次的样本 + 本次的样本，
        最后一条往往是"本次连不上"的错误串，会把「✅ 可打开」写成错误信息。
        要取**第一条 ok 样本**。
      · 非 ok 的不要整串 samples 塞进单元格（一屏看不完）；只给短因（HTTP 码 / 错误摘要）。
    """
    if human and human.get("result") == OK:
        return f"{LABEL[OK]}（人工点验 · {human.get('by')} @ {human.get('at')}）"
    if res["cls"] == OK:
        s = next((x for x in res["samples"] if x.startswith(OK + ":")), "")
        d = s.split(":", 1)[1].strip() if s else ""
        return f"{LABEL[OK]}（{d}）" if d else LABEL[OK]
    if res.get("code") and not (200 <= res["code"] < 300 and res.get("sniff")):
        why = f"HTTP {res['code']}"
    elif res.get("sniff"):
        # 状态码是 2xx 但页面不可信（WAF 拦截页 / "内容不存在"页）——
        # 只写「HTTP 200」会让人以为链接好好的，必须把**为什么不可信**一并写上
        why = f"HTTP {res.get('code')} 但{res['sniff']}"
    else:
        s = (res["samples"][-1].split(":", 1)[-1] if res["samples"] else "")
        why = re.sub(r"^\w*(Error|Exception):\s*", "", s).strip()[:52]
    why = why[:72]
    return f"{LABEL[res['cls']]}（{why}）" if why else LABEL[res["cls"]]


# ── 人工点验留痕（L9 的凭据）────────────────────────────────────────────────
# 为什么需要它：本机/沙箱对部分官方站不可达（政府站挡自动化、网络策略不同），
# 机器**永远**给不出结论 —— 但"客户能不能打开"这件事必须落地。
# ⇒ 允许人工点验一次、把结论写进批次配置，门禁据此放行。
# ⚠️ 纪律（别把这条做松）：
#   · `result: "ok"` = **确实取到过页面内容**（浏览器里打开 / 具名的独立抓取通道），
#     不能因为"它应该能打开"就填 ok。
#   · `note` **必须写明方式**（如「浏览器打开正常」/「独立抓取通道取到全文，脚本 UA 被 403」），
#     这样留痕可审计、也便于日后判断结论是否过期。
#   · 谁验的写 `by` 谁。**不许代替别人填**。
def verified_of(note):
    """取某条 note 的人工点验记录 → dict|None（唯一读取处）。"""
    v = (note or {}).get("link_verified")
    return v if isinstance(v, dict) and v.get("result") else None


def needs_manual(note, res):
    """该条是否「机器给不出结论、需要人工点验」→ (需要?, 说明)。"""
    if not res or verdict(res) != "manual":
        return False, ""
    if verified_of(note):
        return False, ""
    return True, f"{res.get('rid')} {LABEL[res['cls']]} {res['url']}"


def mark_verified(cfg_path, rids, by, note="", result="ok", at=None):
    """把人工点验结论写进批次配置 → (改动条数, 备份路径)。

    只改 `notes[*].link_verified` 这一个字段，其余字节不动（json 原样回写）。
    """
    import shutil
    d = json.load(open(cfg_path, encoding="utf-8"))
    at = at or datetime.date.today().isoformat()
    n = 0
    for _slug, cc in (d.get("countries") or {}).items():
        for x in cc.get("notes") or []:
            if x.get("rid") in set(rids):
                x["link_verified"] = dict(result=result, by=by, at=at, note=note)
                n += 1
    if not n:
        return 0, None
    bak = cfg_path + ".bak"
    shutil.copy(cfg_path, bak)
    json.dump(d, open(cfg_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return n, bak


def collect_from_config(cfg):
    """从批次配置收集官方外链 → [(rid, url)]（唯一实现）。

    同时收集 official_url / interpret_url / tool_entries —— 凡页面上会出现的外链都要能打开。
    """
    out = []
    for slug, cc in (cfg.get("countries") or {}).items():
        for n in cc.get("notes") or []:
            for key in ("official_url", "interpret_url"):
                if n.get(key):
                    out.append((n.get("rid"), n[key]))
            for e in (n.get("tool_entries") or []):
                if e.get("url"):
                    out.append((n.get("rid"), e["url"]))
    return out


def collect_from_html(html):
    """从**产物 HTML** 抽链接（二次/三次校验用，防线上被人改过）→ [(rid, url)]。

    只取标注块内的 href；rid 取该块的 `data-cg-rid` 属性（2026-09-23 起页面文本
    已不展示校对ID，但属性仍在）—— 带上 rid 才能把结论按行写回台账。
    """
    import guide_patch_lib as L
    out = []
    for blk in L.note_blocks(html):
        m = re.search(r'data-cg-rid="([^"]*)"', blk)
        rid = m.group(1) if m else None
        out += [(rid, u) for u in L.urls_in(blk)]
    return out


def _dedupe_pairs(pairs):
    """按 URL 去重 → [(rid, url)]，保留**首次出现的非空 rid**（唯一实现）。

    为什么需要：`--config` 与 `--html` 可以同时给（配置看"打算写的"、产物看"实际写的"），
    两者会覆盖同一批链接 ⇒ 不去重就会把 6 条链接当 12 条，
    汇总数字翻倍、缓存里出现重复条目（已踩）。
    去重后每条 URL 只探一次 —— 对官方站也更友好。
    """
    seen, out = {}, []
    for rid, url in pairs:
        if url in seen:
            i = seen[url]
            if out[i][0] is None and rid:      # 见过的 URL 若原来没 rid，补上
                out[i] = (rid, url)
            continue
        seen[url] = len(out)
        out.append((rid, url))
    return out


def run(pairs, tries=3, timeout=12, workers=5, prev=None):
    """pairs: [(rid, url)] → (results[dict], 汇总 dict)。

    `prev` = 上一次的探测结论（`load_cache()` 的 results）。作用见 `_inherit`：
    **不让网络抖动推翻已验真通过的结论**，否则「待人工点验」清单每次跑都在变
    （实测：gpssa 一条 5 分钟内一次 200 一次超时），门禁就变成了噪声。
    """
    urls = [u for _r, u in pairs]
    res = check_urls(urls, tries=tries, timeout=timeout, workers=workers)
    rid_of = {}
    for r, u in pairs:
        rid_of.setdefault(u, r)
    prev_by = {g["url"]: g for g in (prev or [])}
    for g in res:
        g["rid"] = rid_of.get(g["url"])
        _inherit(g, prev_by.get(g["url"]))
    counts = {k: 0 for k in (OK, BLOCKED, DEAD, SERVER_ERROR, UNREACHABLE)}
    for g in res:
        counts[g["cls"]] += 1
    # 注意：counts 里已有 dead / blocked … 等计数键，故两个"明细清单"必须换名，
    # 否则 dict(**) 会撞键（已踩：TypeError: got multiple values for keyword 'dead'）
    return res, dict(total=len(res), **counts,
                     dead_urls=[g["url"] for g in res if g["cls"] == DEAD],
                     manual_urls=[g["url"] for g in res if g["cls"] in MANUAL],
                     inherited=[g["url"] for g in res if g.get("via")],
                     at=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


# 继承窗口：超过这个天数的「验真 ok」不再继承（否则一条真死链配上永远不通的网络
# 会被一直掩盖）。QC 每次落线前都跑，30 天足够覆盖"下一次落线"。
OK_TTL_DAYS = 30


def _inherit(g, p):
    """把上一次的「验真 ok」继承到本次结论上（原地改 g）。唯一实现，规则只有两条：

      ① **dead 永远优先** —— 本次真拿到 4xx = 内容问题（链接坏了），不能被历史 ok 掩盖
      ② 本次是**环境类**（blocked / server_error / unreachable）而上一次验真 ok 且未过期
         ⇒ 判定仍为 ok，并记 `via`（哪一次验的、什么时候），报告里看得见这次是继承来的

    为什么必须有这条：本机是 MITM 代理，实测同一条链接 5 分钟内一次 200 一次超时。
    不继承的话，「待人工点验」清单每次跑都不一样 —— 门禁从"把关"退化成了"抖动"。

    ③ **不可信的"验真 ok"不继承**（2026-09-23 补）：历史结论的 `sniff` 若命中拦截页/错误页
       特征，说明那条 ok 本身就是误判 ⇒ 不继承，让本次结果说话。
       踩过：WAF 拒绝页被老算法判 ok 写进缓存，改完算法后仍被"继承"保留 ⇒ 假放行长期存在。
    """
    if not p or p.get("cls") != OK or g["cls"] in (OK, DEAD):
        return
    hist = str(p.get("sniff") or "").lower()
    if hist and any(s in hist for s in _SUSPECT_TITLE_HINT):
        return
    try:
        age = (datetime.date.today()
               - datetime.date.fromisoformat(str(p.get("at", ""))[:10])).days
    except Exception:
        age = 10 ** 6
    if age > OK_TTL_DAYS:
        return
    g["cls"], g["label"] = OK, LABEL[OK]
    g["via"] = f"继承上次验真结论（{p.get('at')}）"
    g["sniff"] = p.get("sniff") or g.get("sniff")
    g["samples"] = list(p.get("samples") or []) + list(g["samples"])


def load_cache(path):
    """读缓存的探测结论 → (results|None, 汇总|None)。

    有缓存的意义：① 负向测试要能**确定性复现**「死链必拦」，不能依赖当时网络；
    ② 同一天内 QC 与二次校验不重复打人家官网（对官方站友好）。

    `ver` 版本门槛（2026-09-23 加）：分类算法改过之后，**老缓存里的结论不再是证据**。
    缓存里若有 `ver` 且 ≠ `CACHE_VERSION` → 一律作废（返回空）。
    ⚠️ **没有 `ver` 字段的缓存照常读** —— 负向测试的夹具是手写的，不带版本号，
    卡版本会把测试一起卡死。但那种缓存里的「验真 ok」会被 `_inherit` 的嗅探特征再筛一遍。
    """
    if not path or not os.path.exists(path):
        return None, None
    try:
        d = json.load(open(path, encoding="utf-8"))
    except Exception:
        return None, None
    if d.get("ver") is not None and d.get("ver") != CACHE_VERSION:
        return None, None
    return d.get("results") or [], d.get("summary") or {}


def save_cache(path, results, summary, prev=None):
    """写缓存。`prev` = 既有缓存 results —— 给了就**按 URL 合并**后再写（本次结论优先）。

    ★ 为什么必须合并：缓存会被**逐篇 / 逐批**调用复用。只写本次结果，等于把上一批的
      结论抹掉。2026-09-23 踩过：全站普查逐篇 save，76 篇跑完缓存里只剩**最后一篇的
      12 张图** ⇒ 下次普查 900 张图全部重打（跑去官网三分钟），缓存形同不存在。
      合并后行为才对：新探测覆盖同 URL 的旧结论，没碰到的旧结论保留。
    """
    merged, seen = [], set()
    for r in (results or []):
        u = r.get("url")
        if not u or u in seen:
            continue
        seen.add(u)
        merged.append(r)
    n_kept = 0
    for r in (prev or []):
        u = r.get("url")
        if not u or u in seen:
            continue
        seen.add(u)
        merged.append(r)
        n_kept += 1
    if prev:
        summary = dict(summary or {}, merged_total=len(merged), kept_from_prev=n_kept)
    json.dump(dict(ver=CACHE_VERSION, generated_at=summary.get("at"),
                   summary=summary, results=merged),
              open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=None, help="批次配置（取 official_url / interpret_url / tool_entries）")
    ap.add_argument("--url", action="append", default=[], help="直接指定 URL（可多次）")
    ap.add_argument("--html", default=None, help="从产物 HTML 的标注块抽链接")
    ap.add_argument("--tries", type=int, default=3)
    ap.add_argument("--timeout", type=int, default=12)
    ap.add_argument("--workers", type=int, default=5)
    ap.add_argument("--json-out", default=None)
    ap.add_argument("--mark-verified", default=None,
                    help="人工点验留痕：逗号分隔的校对ID（把它们写进 --config 的 link_verified）")
    ap.add_argument("--by", default="Yoyo", help="点验人")
    ap.add_argument("--verified-note", default="浏览器打开正常", help="点验说明")
    a = ap.parse_args()

    if a.mark_verified:
        if not a.config:
            sys.exit("⛔ --mark-verified 需要 --config（结论要写回批次配置）")
        rids = [x.strip() for x in a.mark_verified.split(",") if x.strip()]
        n, bak = mark_verified(a.config, rids, a.by, a.verified_note)
        print(f"{'✅' if n else '❌'} 人工点验留痕：写入 {n} 条（{rids}）→ {a.config}"
              + (f"\n   备份：{bak}" if bak else ""))
        print("   ⚠️ 该记录表示「确实取到过页面内容」（方式已写进 note）；"
              "机器探测结论不受影响（仍会照常显示）。")
        return 0 if n else 1

    pairs = []
    if a.config:
        pairs += collect_from_config(json.load(open(a.config, encoding="utf-8")))
    if a.html and os.path.exists(a.html):
        pairs += collect_from_html(open(a.html, encoding="utf-8").read())
    pairs += [(None, u) for u in a.url]
    pairs = _dedupe_pairs(pairs)
    if not pairs:
        sys.exit("⛔ 没有可校验的链接（给 --config / --html / --url）")

    res, summ = run(pairs, a.tries, a.timeout, a.workers)
    print("=" * 74)
    print(f"官方外链可达性校验　{summ['at']}　共 {summ['total']} 条")
    print("=" * 74)
    for g in res:
        print(f" {g['label']:<28} {g.get('rid') or '-':<16} {g['host']:<28} {g['samples']}")
    print("-" * 74)
    print(f"{LABEL[OK]} {summ[OK]} ｜ {LABEL[BLOCKED]} {summ[BLOCKED]} ｜ "
          f"{LABEL[DEAD]} {summ[DEAD]} ｜ {LABEL[SERVER_ERROR]} {summ[SERVER_ERROR]} ｜ "
          f"{LABEL[UNREACHABLE]} {summ[UNREACHABLE]}")
    if summ["dead_urls"]:
        print(f"\n❌ 死链（必须换链接，否则不得上线）：")
        for u in summ["dead_urls"]:
            print(f"   · {u}")
    if summ["manual_urls"]:
        print(f"\n⚠️ 需人工点验（本机给不出结论：站点反爬 / 网络不可达）：")
        for g in res:
            if g["cls"] in MANUAL:
                print(f"   · {g.get('rid') or '-'} {g['url']}")
        print("   ⚠️ 一次校验的 L9 会**拦住**这些条目 —— 在浏览器里点开确认后，"
              "用 `--mark-verified <rid,...>` 留痕，再重跑 release_stage.py 即放行。")
    if a.json_out:
        save_cache(a.json_out, res, summ)
        print(f"\n结论 → {a.json_out}")
    return 1 if summ["dead_urls"] else 0


if __name__ == "__main__":
    sys.exit(main())
