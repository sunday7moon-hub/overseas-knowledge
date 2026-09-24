#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
慧思国别指南「全文校验」（两种时机，同一套 S1–S16）
=====================================================
它回答一个问题：**「这一版正文，真的对吗？」**
上线前 QC（qc_gate.py）只证明"我打算写的"合规，证明不了"整篇正文渲染出来到底对不对"
—— 2026-09-23 UAE 事故正是这样漏掉的。

⚠️ 术语（Yoyo 2026-09-23 定，**三次校验**）：
     一次校验 = 上线前 QC              qc_gate.py                     （26 项）
     二次校验 = 全文校验 · 暂存稿预验   verify_secondary.py --source staging（S1–S16）
     三次校验 = 全文校验 · 上线后回读   verify_secondary.py --source live  （S1–S16）
   两次跑的是**同一套 S 项**，只是被校验对象不同；台账里各记一组字段。

两种时机（`--source`）：
  · `staging`（**落线前**）＝ **二次校验**：被校验对象 = 本地暂存稿 content_AFTER.html。
    Yoyo 定的流程是"全文校验通过后**再**上线"，所以二次校验必须能在落线前跑。
    此时 S8 换成「线上当前 == 本轮基线」，防止落线时覆盖别人的改动。
    台账写「二次校验结果 / 时间 / 说明」。
  · `live`（**落线后**，默认）＝ **三次校验**：被校验对象 = 从 Strapi 回读的线上 content。
    台账写「三次校验结果 / 时间 / 说明」。两者各记一组，互不覆盖。

16 项（S1–S16）全过，才允许把台账「三次校验结果」写成 ✅ 通过。

  S1  可渲染章节数 == 指南应有章节数（复刻前端 walker，最关键）
  S2  无 `</div><` 危险邻接
  S3  标注块数 == 配置条数
  S4  校对ID 集合 == 配置集合（无漏、无重；走 data-cg-rid 属性）
  S5  「官方原文 ↗」数 == 配置条数
  S6  标注块内链接全部 official / internal（无站外三方）
  S7  div 配平、h2.section-title 数量不变
  S8  live：线上 == 本地产物（剥 <style> 后等价）｜staging：线上 == 本轮基线（未被改动）
  S9  正文零改动（摘除注入物后 == content_ORIGINAL 基线）
  S10 生效状态 / **配色档**判定一致（data-cg-eff 与 data-cg-tone 都按生效日重算 + 文案已写明）
  S11 目录气泡 / 章节徽标数量自洽（@scope 存在、规则数 = 有标注章节数 × 章节份数）
  S12 客户向文案（版本条「正文版本」月粒度且 = 最新校验月 · 无内部过程时间 · 状态文案客户端向）
  S13 页面无内部过程字段（标注写入 / 校对ID / 页面位置）—— 只记台账（Yoyo 2026-09-23）
  S14 **官方外链可打开**（从**产物**的 href 抽链接再探测，防线上被人改过；死链阻断）
  S15 **配图来源合规**（占位图 / 相对路径 / 空 src / alt 敷衍 / 可达性）★ 2026-09-23 新增
  S16 **排版真值**（字号层级倒置 / 横向溢出 / 卡片高度不齐 / 渲染破图）★ 2026-09-23 新增
      —— S15/S16 是 Yoyo「内容质量-排版维度，或者配图」的落点，判定实现 = content_quality.py

用法：
  # 落线前（暂存稿预验 → 二次校验）——由 release_stage.py 自动调用
  python3 verify_secondary.py --config ../references/batches/uae-v3.json \
      --workdir /path/_pilot_UAE --source staging

  # 落线后（线上回读 → 三次校验）；--sync-ledger 写台账「三次校验*」三字段
  python3 verify_secondary.py --config ... --workdir ... --sync-ledger
退出码：0 = 全部通过；1 = 存在未通过项。
"""
import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import guide_patch_lib as L  # noqa: E402
import ledger_client as LC  # noqa: E402
import link_check as LNK  # noqa: E402
import content_quality as CQ  # noqa: E402  内容质量（排版·配图）唯一实现

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = json.load(open(os.path.join(HERE, "..", "references", "ledger.json"), encoding="utf-8"))

F = LEDGER["fields"]      # 字段名映射（唯一一处定义，别在别处写死中文字段名）


def check_doc(slug, cc, workdir, source="live", batch=None, link_mode="live",
              cq_mode="live", cq_probe=False, cq_max_pages=6, cq_render_cache=None):
    """对单国跑 S1–S14 → (checks, meta, 被校验的正文)

    source='live'    被校验正文 = **从 Strapi 回读的线上 content**（落线后复验 → 三次校验，默认）
    source='staging' 被校验正文 = **本地暂存稿 content_AFTER.html**（落线前预验 → 二次校验）
                     此时 S8 改为校验「线上当前 == 本轮基线」（防落线时覆盖别人的改动）。
    batch            批次级配置（只为取 batch / review_date，用于 S12 的「正文版本」重算）
    link_mode        S14 外链探测方式：live=现场探测 ｜ cache=复用 _link_check.json ｜ off=跳过
    """
    ck, meta = [], {}

    s, d = L.strapi_call("GET", f"/api/articles/{cc['documentId']}?populate=*")
    if not isinstance(d, dict) or "data" not in d:
        ck.append(dict(id="S0", name="拉取线上内容", ok=False, detail=f"HTTP {s}: {str(d)[:160]}"))
        return ck, {}, ""
    live = d["data"]["content"] or ""
    meta["remote_len"] = len(live)
    meta["publishedAt"] = d["data"].get("publishedAt")

    fp = os.path.join(workdir, slug, "content_AFTER.html")
    local = open(fp, encoding="utf-8").read() if os.path.exists(fp) else ""
    bp = os.path.join(workdir, slug, "content_ORIGINAL.html")
    base = open(bp, encoding="utf-8").read() if os.path.exists(bp) else ""
    notes = L.page_notes(cc["notes"])       # ★ 页面侧基数（红色不上前端 → 见 S17）
    hid = L.hidden_notes(cc["notes"])

    if source == "staging":
        cand = local
        if not cand:
            ck.append(dict(id="S0", name="读取本地暂存稿", ok=False, detail=f"缺 {fp}"))
            return ck, meta, ""
        meta["staging_len"] = len(cand)
        meta["staging_sha"] = L.sha16(cand)
    else:
        cand = live
    meta["source"] = source

    def add(i, name, ok, detail):
        ck.append(dict(id=i, name=name, ok=bool(ok), detail=str(detail)))

    # S1 章节可渲染（复刻前端 walker）
    want = [t for _o, t, _p in L._section_map(cand)]
    vis = L.frontend_visible_sections(cand)
    miss = [t for t in want if t not in vis]
    add("S1", "章节全部可渲染（复刻前端 walker）", want and not miss,
        f"{len(vis)}/{len(want)} 章" + (f"，缺：{miss}" if miss else ""))

    # S2 危险邻接
    uns = L.walk_unsafe_spans(cand)
    add("S2", "无 `</div><` 危险邻接", not uns, f"{len(uns)} 处")

    # S3-S5 基数 = **页面条目**（L.page_notes）：红色（来源存疑）不上前端 ⇒ 不在页面上数
    blocks = L.note_blocks(cand)
    add("S3", "标注块数 = 页面条目数", len(blocks) == len(notes), f"{len(blocks)}/{len(notes)}")

    # S4 校对ID 集合（2026-09-23 起走 data-cg-rid **属性** —— 页面文本已不再展示校对ID）
    got = re.findall(r'data-cg-rid="(PR-\d{8}-\d+)"', cand)
    add("S4", "校对ID 集合 = 页面条目集合（无漏无重；data-cg-rid 属性）",
        sorted(set(got)) == sorted(set(n["rid"] for n in notes))
        and len(got) == len(notes) and len(got) == len(set(got)),
        f"{len(got)} / 页面条目 {len(notes)}" + ("，有重复" if len(got) != len(set(got)) else ""))

    # S5 官方原文链接数（＝页面条目数：不上页面的条目本就不带链接）
    nl = cand.count(">官方原文 ↗</a>")
    add("S5", "「官方原文 ↗」数 = 页面条目数", nl == len(notes), f"{nl}/{len(notes)}")

    # S6 标注块链接合法性
    bad = []
    for blk in blocks:
        for u in L.urls_in(blk):
            vd, h = L.classify_source(u)
            if vd not in ("official", "internal"):
                bad.append(f"{vd}:{h}")
    add("S6", "标注块内链接全部 official/internal", not bad,
        "全部合规" if not bad else f"{len(bad)} 条非法：{bad[:3]}")

    # S7 结构
    divok = cand.count("<div") == cand.count("</div>")
    h2n = len(re.findall(r'class="section-title"', cand))
    h2b = len(re.findall(r'class="section-title"', base)) if base else h2n
    add("S7", "div 配平 & h2.section-title 数量不变", divok and h2n == h2b,
        f"div {cand.count('<div')}/{cand.count('</div>')}，h2 {h2n}（基线 {h2b}）")

    # S8 两种模式语义不同（见 docstring）
    if source == "staging":
        # 「本轮基线」判据 = **线上正文（摘除我方注入物后）仍等于我们的干净基线**。
        # 这样对「首次落线」与「改版重发」两种情形同时成立，且不需要额外快照文件：
        #   · 首次落线：线上还是干净正文 ⇒ 天然相等
        #   · 改版重发：线上 = 干净正文 + 我们上一版注入物 ⇒ 摘除后仍相等
        # 若不等 ⇒ 有人在我们拉基线之后动过**正文** ⇒ 必须重取基线，禁止覆盖。
        same_base = (bool(base)
                     and L.canonical(L.strip_injections(live))
                     == L.canonical(L.strip_injections(base)))
        add("S8", "线上正文 == 本轮基线（摘除我方注入物后等价，未被他人改动）", same_base,
            "基线未漂移，可安全落线" if same_base
            else f"线上正文已被改动：线上 {len(L.strip_injections(live))} vs 基线 "
                 f"{len(L.strip_injections(base))} 字符 —— 需 --refresh 重取基線后重跑")
    else:
        eq = L.strip_style(live) == L.strip_style(local) if local else False
        add("S8", "线上 == 本地产物（剥 <style> 等价）", eq,
            "等价（差异仅平台作用域前缀/空白折叠）" if eq
            else f"不等价：线上 {len(L.strip_style(live))} vs 本地 {len(L.strip_style(local))} 字符")

    # S9 正文零改动
    if base:
        same = L.canonical(L.strip_injections(cand)) == L.canonical(L.strip_injections(base))
        add("S9", "正文零改动（摘除注入物后 == 基线）", same,
            "逐行等价" if same else "正文被改动过 —— 只允许纯追加")
    else:
        add("S9", "正文零改动（摘除注入物后 == 基线）", False, f"缺基线 {bp}")

    # S10 生效状态一致
    eff_bad = []
    for n in notes:
        es = L.effective_state(n.get("effective"))
        n["_eff_state"] = es
    for m in re.finditer(r'<div class="cg-update-note"([^>]*)>', cand):
        at = m.group(1)
        rid = (re.search(r'data-cg-rid="([^"]*)"', at) or [None, "?"])[1]
        eff = (re.search(r'data-cg-effective="([^"]*)"', at) or [None, ""])[1]
        g = (re.search(r'data-cg-eff="([^"]*)"', at) or [None, ""])[1]
        w = L.effective_state(eff)
        if g != w:
            eff_bad.append(f"{rid}: 标 {g!r} 应为 {w!r}")
            continue
        seg = cand[m.start():m.start() + 2600]
        seg = seg[:seg.find("</div>")] if "</div>" in seg else seg
        if w == "effective" and L.EFF_TEXT["effective"] not in seg:
            eff_bad.append(f"{rid}: 生效日 {eff} 已过但未写「{L.EFF_TEXT['effective']}」")
        if w == "scheduled" and L.EFF_TEXT["scheduled"] not in seg:
            eff_bad.append(f"{rid}: 生效日 {eff} 未到但未写「{L.EFF_TEXT['scheduled']}」")
    n_eff = sum(1 for n in notes if n["_eff_state"] == "effective")
    n_sch = sum(1 for n in notes if n["_eff_state"] == "scheduled")
    # ★ 配色档（tone）同属"派生值"，与生效状态一并验（2026-09-23 Yoyo 改配色口径）：
    #   绿 = 有变更已生效 ∪ 维持不变（两档同色，靠徽标文案区分）；橙黄 = 变更尚未生效；
    #   红 = 来源存疑 —— **不上前端**（见 S17），故产物里不该出现这一档。
    #   产物里的 data-cg-tone 必须等于按配置重算的结果 —— 防"常量改了、线上还是旧色"。
    tone_bad, tone_cnt = [], {}
    _by_rid = {n["rid"]: n for n in notes}
    for m in re.finditer(r'<div class="cg-update-note"([^>]*)>', cand):
        rid = (re.search(r'data-cg-rid="([^"]*)"', m.group(1)) or [None, "?"])[1]
        note = _by_rid.get(rid)
        if not note:
            continue
        got_t = (re.search(r'data-cg-tone="([^"]*)"', m.group(1)) or [None, ""])[1]
        wnt_t = L.tone_of(note)
        tone_cnt[wnt_t] = tone_cnt.get(wnt_t, 0) + 1
        if got_t != wnt_t:
            tone_bad.append(f"{rid}: 标 {got_t!r} 应为 {wnt_t!r}")
    add("S10", "生效状态 / 配色档判定与文案一致",
        not eff_bad and not tone_bad,
        (f"{L.EFF_TEXT['effective']} {n_eff} · {L.EFF_TEXT['scheduled']} {n_sch} ｜ 配色 "
         + "、".join(f"{k}×{v}" for k, v in sorted(tone_cnt.items())))
        if not eff_bad and not tone_bad else f"{(eff_bad + tone_bad)[:3]}")

    # S11 气泡 / 徽标自洽
    with_notes = len({n["_sec_idx"] if "_sec_idx" in n else 0 for n in notes}) or len(notes)
    n_sec = cand.count(L.SEC)
    got_toc = cand.count(L.TOC_SEL)
    badges = cand.count("data-cg-badge=")
    add("S11", "目录气泡 / 章节徽标数量自洽",
        cand.count(L.TOC_SCOPE) > 0 and got_toc % max(n_sec, 1) == 0 and badges > 0,
        f"@scope {cand.count(L.TOC_SCOPE)} ｜ 气泡规则 {got_toc}（{n_sec} 章节份）｜ 徽标 {badges}")

    # S12 客户向文案（Yoyo 2026-09-23：「写这个是给客户看的」）
    dm = L.version_bar_dates(dict(cc, batch=(batch or {}).get("batch"),
                                  review_date=(batch or {}).get("review_date")))
    mvb = re.search(r'正文版本：<strong>([^<]*)</strong>', cand)
    got_bv = mvb.group(1) if mvb else ""
    bv_ok = (bool(mvb) and re.fullmatch(r"\d{4}-\d{2}", got_bv or "") is not None
             and (not dm["body_version"] or got_bv == dm["body_version"]))
    leak_time = [x for x in ("校验时间", "最新校验", "校对日期") if x in cand]
    # 旧文案合集引 guide_patch_lib.STALE_COPY（标注状态 + 生效状态），别在这里再拼一次
    stale_txt = [x for x in L.STALE_COPY if x in cand]
    add("S12", "客户向文案（正文版本月粒度 · 无内部过程时间 · 状态文案客户端向）",
        bv_ok and not leak_time and not stale_txt,
        (f"正文版本 {got_bv!r}（应 {dm['body_version']!r}）"
         + ("；" if (leak_time or stale_txt) else "")
         + ("出现内部过程时间 " + str(leak_time) if leak_time else "")
         + ("；" if leak_time and stale_txt else "")
         + ("残留旧文案 " + str(stale_txt) if stale_txt else "")))

    meta["notes"] = len(notes)
    meta["titles"] = len(want)

    # ── S13 页面不得出现内部过程字段（Yoyo 2026-09-23：标注写入/校对ID/页面位置 只在台账）──
    leaked = [x for x in L.INTERNAL_FIELDS if x in cand]
    add("S13", "页面无内部过程字段（标注写入 / 校对ID / 页面位置）—— 只记台账",
        not leaked,
        "干净（定位走 data-cg-rid / data-cg-anchor 属性）" if not leaked else
        f"出现 {leaked} —— 客户向页面不得展示；应只记飞书台账"
        f"（更新时间 / 校对ID / 落位章节）")

    # ── S14 官方外链可打开（★ Yoyo 2026-09-23 新增；从**产物**抽 href，防线上被人改过）──
    # 与 qc_gate 的 L5 同一实现（link_check.py）、同一口径：**死链阻断**，
    # 本机不可达/站点反爬只记「需人工点验」（不判死）。
    pairs = LNK.collect_from_html(cand)
    if link_mode == "off":
        add("S14", "官方外链可打开（无死链）", False,
            "--link-mode off：跳过外链校验（仅排障允许）")
        res = []
    else:
        cache_path = os.path.join(workdir, "_link_check.json")
        missing = []
        if link_mode == "cache":
            cached, _s = LNK.load_cache(cache_path)
            by = {g["url"]: g for g in (cached or [])}
            missing = [u for _r, u in pairs if u not in by]
            res = [dict(by[u], rid=r) for r, u in pairs if u in by]
        else:
            res, _summ = LNK.run(pairs)
        dead = [g for g in res if LNK.verdict(g) == "block"]
        manual = [g for g in res if LNK.verdict(g) == "manual"]
        bits = [f"探测 {len(res)} 条：可打开 {sum(1 for g in res if LNK.verdict(g) == 'pass')}"
                f" ｜ 死链 {len(dead)} ｜ 需人工点验 {len(manual)}"]
        if dead:
            bits.append(f"死链必须换链接：{[g['url'][:70] for g in dead]}")
        if manual:
            bits.append(f"需人工点验（不阻断，结论记台账「外链状态」）：{[g['rid'] for g in manual]}")
        if missing:
            bits.append(f"另有 {len(missing)} 条无结论 —— 缺 {os.path.basename(cache_path)}，"
                        f"需先跑 `qc_gate.py --link-mode live`：{[u[:60] for u in missing]}")
        add("S14", "官方外链可打开（无死链）",
            bool(res) and not dead and not missing, "；".join(bits))
    meta["link_checked"] = len(pairs)
    # 按 rid 汇总外链结论 → 台账「外链状态」「外链校验时间」（页面不展示）
    # 人工点验留痕优先于机器结论（有人真取到过页面内容，比"本机连不上"更可信）
    human = {n["rid"]: LNK.verified_of(n) for n in notes}
    per = {}
    for g in res:
        per.setdefault(g.get("rid"), []).append(g)
    meta["link_by_rid"] = {
        r: " ｜ ".join(dict.fromkeys(
            LNK.ledger_text(g, human.get(r)) for g in gs)) for r, gs in per.items() if r}
    meta["link_at"] = (res[0]["at"] if res else "")

    # ── S15 配图来源合规（★ Yoyo 2026-09-23：内容质量-配图维度）──────────────
    # 与 qc_gate 的 CQ1 同一实现（content_quality.py）、同一政策（image-hosts.json）。
    # 这里从**被校验的正文**（staging=暂存稿 / live=线上回读）重扫一遍 ——
    # 防的是"本地改了图但线上还是旧的"这类漂移。
    cq_finds, cq_imgs = [], []
    if cq_mode == "off":
        add("S15", "配图来源合规（占位图 / 相对路径 / 空 src / alt）", False,
            "--cq-mode off：跳过内容质量检查（仅排障允许）")
    else:
        cq_finds, cq_imgs, _ = CQ.scan_html(cand)
        # 可达性结论复用 QC 落下的 _img_check.json（不在全文校验里重复打图床）
        icache = os.path.join(workdir, "_img_check.json")
        prev, _s = LNK.load_cache(icache)
        if prev:
            by = {g["url"]: g for g in prev}
            for i in cq_imgs:
                g = by.get(i["src"])
                if g and LNK.verdict(g) == "block":
                    cq_finds.append(CQ.finding(
                        "CI7", "配图", "block", i["section"],
                        f"图片打不开：{LNK.LABEL.get(g['cls'], g['cls'])} `{i['src'][:90]}`",
                        "换图或修 URL"))
        bad = [f for f in cq_finds if f["level"] == "block"]
        warn = [f for f in cq_finds if f["level"] == "warn"]
        bits = [f"{len(cq_imgs)} 张图（自有域 {sum(1 for i in cq_imgs if i['kind'] == 'own')}"
                f" ｜ 非自有域 {sum(1 for i in cq_imgs if i['kind'] == 'external')}）",
                f"阻断 {len(bad)} · 告警 {len(warn)}"]
        if bad:
            bits.append("不合格：" + "；".join(
                f"[{f['id']}] {f['item']} {f['detail'].splitlines()[0][:90]}" for f in bad[:3]))
        if warn and not bad:
            bits.append("非自有域图床需自有化（不阻断，记台账待整改）")
        add("S15", "配图来源合规（占位图 / 相对路径 / 空 src / alt / 可达性）",
            not bad, "；".join(bits))

    # ── S16 排版真值（★ 渲染层：字号层级 / 溢出 / 卡片高度）──────────────────
    # 静态 HTML 证明不了"看起来对不对" —— 必须无头 Chrome 真渲染取计算样式。
    # 只渲染**含统计卡片（.stat-box）的章节**：排版风险集中在卡片，避免把 12 个章节全渲染一遍。
    if cq_mode == "live":
        # guide_url 是"某章节页"的地址（…/guide-slug/国家概况）→ 取到 guide-slug 那一层当 base，
        # 再用章节标题拼 URL。⚠️ 别偷懒只 rstrip("/") —— 会把 /国家概况 留在 base 里，
        # 拼出 …/国家概况/薪酬支付 这种 404 地址，渲染到 404 页 → 零发现 → **假通过**（已踩）。
        _gu = (cc.get("guide_url") or "").rstrip("/")
        base = _gu.rsplit("/", 1)[0] if "/" in _gu else ""
        # 按 h2 位置切段，取"这一段里含 .stat-box（统计卡片）"的章节做渲染
        # —— 排版风险集中在卡片，渲染全部 12 章太慢且无增量信息。
        marks = [(m.start(), m.end(), CQ.clean_text(m.group(1))) for m in re.finditer(
            r'<h2[^>]*class="[^"]*section-title[^"]*"[^>]*>([\s\S]*?)</h2>', cand, re.I)]
        secs = []
        for n, (_s, _e, title) in enumerate(marks):
            nxt = marks[n + 1][0] if n + 1 < len(marks) else len(cand)
            if "stat-box" in cand[_s:nxt]:
                secs.append(title)
        cache = CQ.load_render_cache(cq_render_cache)
        urls, skipped = [], 0
        for t in secs:
            u = f"{base}/{t}" if base else None
            if not u:
                continue
            if len(urls) >= cq_max_pages:
                skipped += 1
                continue
            urls.append(u)
        typo, dimg, done = [], [], 0
        cq_known = []
        for u in urls:
            if u in cache:
                # 缓存里只有探针**原始读数**，判定在这里重算 —— 改阈值/改基线即时生效
                f2, _ = CQ.judge(cache[u])
            else:
                f2, raw = CQ.render_check(u, tag=re.sub(r"\W+", "_", u)[-22:])
                cache[u] = raw
                done += 1
            typo += [f for f in f2 if f["dim"] == "排版" and f["level"] == "block"]
            dimg += [f for f in f2 if f["dim"] == "配图" and f["level"] == "block"]
            cq_known += [f for f in f2 if f.get("known")]
        CQ.save_render_cache(cq_render_cache, cache)
        if cq_render_cache:
            json.dump(cache, open(cq_render_cache, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        if not base:
            add("S16", "排版真值（字号层级 / 横向溢出 / 卡片高度）", False,
                "配置里没有 guide_url，无法定位线上章节页")
        elif not urls:
            # ⚠️ fail-closed：定位不到页面时**不许算通过**。否则一个坏 base 就能让整项静默变绿
            # （2026-09-23 实测：base 多带了一段路径 → 渲染 404 页 → 0 条发现 → 假通过）。
            add("S16", "排版真值（字号层级 / 横向溢出 / 卡片高度 / 渲染破图）", False,
                f"没有定位到任何含统计卡片的章节页（guide_url={_gu}；"
                f"content 中 h2.section-title 命中 {len(marks)} 个）—— 无法判定排版，按未通过处理")
        else:
            bits = [f"渲染 {len(urls)} 个含卡片章节页（新渲染 {done}，命中缓存 {len(urls)-done}）"
                    + (f"，另有 {skipped} 页超出 --cq-max-pages 未渲染" if skipped else ""),
                    f"排版阻断 {len(typo)} · 配图阻断 {len(dimg)}"]
            if cq_known:
                bits.append(f"已知缺陷（已派单，降级告警）{len(cq_known)} 条："
                            + "、".join(sorted({f.get('known', '') for f in cq_known})))
            if typo:
                bits.append("排版不合格：" + "；".join(f["detail"].splitlines()[0][:100] for f in typo[:3]))
            if dimg:
                bits.append("渲染破图：" + "；".join(f["detail"].splitlines()[0][:90] for f in dimg[:2]))
            add("S16", "排版真值（字号层级 / 横向溢出 / 卡片高度 / 渲染破图）",
                not typo and not dimg, "；".join(bits))
            cq_finds += typo + dimg
    # ── S17 页面不出现红色档（★ Yoyo 2026-09-23 四轮：「红色 存疑 先不在前端展示，
    #        记录台账待处理」）──────────────────────────────────────────────────
    # 口径：页面只出现两类 —— 绿（不用管）与 橙黄（计划变更未落地）。
    # 红色（来源存疑）整条不注入页面、不进版本条计数，只记台账待处理；
    # 判定唯一入口 = guide_patch_lib.on_page()，本检查是**产物侧复核**（防漏滤 / 防手工塞回）。
    # ⚠️ 先剥 <style>：徽标样式块含 `[data-cg-tone="…"]` 选择器，全文 count 会误报。
    _cand_nos = L.strip_style(cand)
    _red = re.findall(r'data-cg-tone="verify"', _cand_nos)
    add("S17", "页面不出现红色档（来源存疑不上前端，只记台账）", not _red,
        (f"干净（页面 {len(notes)} 项" +
         (f"，未上页面 {len(hid)} 项："
          + "、".join(n["rid"].replace("PR-20260907-", "PR-") for n in hid) if hid else "")
         + "）") if not _red else
        f"页面出现 {len(_red)} 处 data-cg-tone=\"verify\" —— 该类条目不上前端，"
        f"过滤入口 = guide_patch_lib.page_notes()")

    meta["cq"] = dict(images=len(cq_imgs),
                      block=sum(1 for f in cq_finds if f["level"] == "block"),
                      warn=sum(1 for f in cq_finds if f["level"] == "warn"))
    return ck, meta, cand


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--workdir", required=True)
    ap.add_argument("--source", choices=["live", "staging"], default="live",
                    help="live=校验线上（落线后，默认）；staging=校验本地暂存稿（落线前）")
    ap.add_argument("--json-out", default=None)
    ap.add_argument("--md-out", default=None)
    ap.add_argument("--sync-ledger", action="store_true",
                    help="回写飞书台账（staging→「二次校验*」，live→「三次校验*」）")
    ap.add_argument("--link-mode", choices=["live", "cache", "off"], default="live",
                    help="S14 外链探测：live=现场探测（默认）｜cache=复用 qc_gate 落下的 "
                         "_link_check.json（release_stage 用，避免重复打官网）｜off=跳过")
    ap.add_argument("--cq-mode", choices=["live", "static", "off"], default="live",
                    help="S15/S16 内容质量（配图 / 排版）：live=另跑无头 Chrome 真渲染取排版真值"
                         "（默认；排版问题只在渲染层可见）｜static=只扫正文 HTML｜off=跳过")
    ap.add_argument("--cq-max-pages", type=int, default=12,
                    help="S16 最多渲染多少个含统计卡片的章节页（默认 12=全部；同 URL 命中缓存即秒回）")
    ap.add_argument("--cq-render-cache", default=None,
                    help="S16 渲染结论缓存（默认 <workdir>/_cq_render.json；同 URL 命中即复用）")
    a = ap.parse_args()

    cfg = json.load(open(a.config, encoding="utf-8"))
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    all_ck, per_doc = [], {}

    # 术语对齐（Yoyo 2026-09-23）：staging = 二次校验（落线前预验）；live = 三次校验（落线后回读）
    pass_name = "二次校验" if a.source == "staging" else "三次校验"
    stage_txt = "落线前 · 本地暂存稿" if a.source == "staging" else "落线后 · 线上回读"
    field_key = "verify2" if a.source == "staging" else "verify3"

    for slug, cc in cfg["countries"].items():
        ck, meta, cand = check_doc(
            slug, cc, a.workdir, a.source, cfg, a.link_mode,
            cq_mode=a.cq_mode, cq_max_pages=a.cq_max_pages,
            cq_render_cache=(a.cq_render_cache or os.path.join(a.workdir, "_cq_render.json")))
        per_doc[slug] = dict(meta=meta, checks=ck, notes=cc["notes"])
        all_ck += ck

    failed = [c for c in all_ck if not c["ok"]]
    passed = not failed

    print("=" * 78)
    print(f"{pass_name} · 全文校验（{stage_txt}）　批次 {cfg.get('batch')}　{now}")
    print("=" * 78)
    for c in all_ck:
        print(f" {'✅' if c['ok'] else '❌'} [{c['id']:<3}] {c['name']}")
        if not c["ok"]:
            print(f"         ↳ {c['detail']}")
    print("-" * 78)
    print(f"结论：{'✅ 全部通过' if passed else f'❌ {len(failed)} 项未通过'}"
          f"（共 {len(all_ck)} 项 / {len(per_doc)} 国）")

    # 台账同步：按**时机**分流字段 ——
    #   staging（二次校验）→ 二次校验结果 / 时间 / 说明
    #   live   （三次校验）→ 三次校验结果 / 时间 / 说明
    # 这样台账能同时看到"上线前预验"和"上线后回读"两个结论，不会互相覆盖。
    ledger_sync = []
    if a.sync_ledger:
        for slug, info in per_doc.items():
            bad = [c for c in info["checks"] if not c["ok"]]
            verdict = "✅ 通过" if not bad else "❌ 未通过"
            where = "暂存稿" if a.source == "staging" else "线上回读"
            _cq = info["meta"].get("cq") or {}
            detail = (f"{now} ｜ {pass_name}（{where}）｜ 已渲染 "
                      f"{info['meta'].get('titles','-')} 章 · 标注 {info['meta'].get('notes','-')} 条 · "
                      f"官方链接 {info['meta'].get('notes','-')} 条（外链可达已校验）"
                      f" · 生效判定 / 客户向文案 / 无内部过程字段 均一致"
                      f" · 配图 {_cq.get('images','-')} 张（质量阻断 {_cq.get('block', 0)}）"
                      if not bad else
                      f"{now} ｜ {pass_name}（{where}）未通过：" +
                      "；".join(f"{c['id']} {c['name']}（{c['detail']}）" for c in bad[:4]))
            rids = [n["rid"] for n in info["notes"]]
            ok, resp = _ledger_update(rids, verdict, now, detail, field_key)
            # 外链结论顺手按行回写 —— 页面不展示「能不能打开」，但台账要能一眼看到。
            # 单独 patch（不掺进上面那三字段），失败不掩盖主结论。
            lk = info["meta"].get("link_by_rid") or {}
            if lk:
                ok_lk, resp_lk = _ledger_link(lk, info["meta"].get("link_at"))
                print(f"台账外链字段 {slug}：{len(lk)} 条 "
                      f"{'✅ 已回写' if ok_lk else '❌ ' + str(resp_lk)[:160]}")
            ledger_sync.append(dict(slug=slug, verdict=verdict, rids=rids, ok=ok,
                                    resp=(resp if not ok else "已回写"), fields=field_key))
            print(f"\n台账回写 {slug}：{pass_name} {verdict} → {len(rids)} 条 "
                  f"{'✅' if ok else '❌ ' + str(resp)[:200]}")

    rep = dict(batch=cfg.get("batch"), source=a.source, pass_name=pass_name,
               generated_at=now, passed=passed,
               checks_total=len(all_ck), checks_failed=len(failed),
               checks=all_ck, docs=per_doc, ledger_sync=ledger_sync)
    outp = a.json_out or (os.path.join(
        a.workdir, "_secondary_verify.json" if a.source == "live"
        else "_secondary_verify_staging.json"))
    json.dump(rep, open(outp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n报告 → {outp}")
    return 0 if passed else 1


def _ledger_update(rids, verdict, when, detail, field_key="verify3"):
    """按校对ID 回写校验三字段 —— 读写实现统一在 ledger_client.py（唯一实现）。

    field_key: 'verify2'（二次校验，落线前）| 'verify3'（三次校验，落线后）
    字段名从 references/ledger.json 取，**不要**在脚本里写死中文字段名。
    """
    k = {"verify2": ("verify2_result", "verify2_time", "verify2_note"),
         "verify3": ("verify3_result", "verify3_time", "verify3_note")}[field_key]
    patch = {F[k[0]]: verdict, F[k[1]]: when, F[k[2]]: detail}
    return LC.update_by_rid(rids, patch)


def _ledger_link(link_by_rid, at):
    """把外链结论按行回写台账「外链状态 / 外链校验时间」→ (ok, resp)。

    字段名一律从 references/ledger.json 取（F 映射），不写死中文名。
    `update_by_rid` 是"同一组 rid 打同一个 patch"，所以按结论值分组、每组一次调用
    —— 6 条标注通常落成 2~3 组，避免逐行 6 次往返。
    """
    groups = {}
    for rid, txt in link_by_rid.items():
        groups.setdefault(txt, []).append(rid)
    bad = []
    for txt, rids in groups.items():
        patch = {F["link_status"]: txt, F["link_check_at"]: at or ""}
        ok, resp = LC.update_by_rid(rids, patch)
        if not ok:
            bad.append(f"{rids} → {str(resp)[:120]}")
    return (not bad), ("；".join(bad) if bad else f"已回写 {len(link_by_rid)} 条 / {len(groups)} 组")


if __name__ == "__main__":
    sys.exit(main())
