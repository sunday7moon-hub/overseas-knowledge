#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
慧思国别指南「更新标注」上线前 QC 门禁
==========================================
落线（batch_guide_patch.py --apply）**之前**必须过这道关。非 0 退出码 = 拒绝上线。

校验分组（A 链接 / B 文本 / R 前端渲染 / E 生效状态 / F 客户向文案 / G 落线资格）：

  A. 链接（Yoyo 2026-09-22 修订：站外只放官方原文，站内解读/工具必须站内域名）
     L1 每条标注必须有 official_url（缺 → 阻断）
     L2 official_url 必须判为官方源（规则见 references/official-domains.json）
     L3 产物里每个标注块**只许**出现 official（站外官方）+ internal（站内解读/工具）链接，
        三方/未知域名一票否决
     L4 产物「官方原文 ↗」**数量与指向**均与配置一致（Yoyo 2026-09-23 升级）
        —— 只数条数拦不住 href 串行（指向另一个国家的法规页）；等价比对才拦得住
     L5 **官方外链"能不能打开"**（Yoyo 2026-09-23 新增，阻断）：机器探测，**死链（4xx）一票否决**
        —— 实现唯一在 scripts/link_check.py（重试 + 验真 + 五分类，见该文件头说明）
     L6 解读链接（interpret_url，若有）必须判为 internal（站内域名）
     L7 工具入口（tool_entries，若有）每条必须判为 internal（站内域名）
     L8 单标注块工具入口建议 ≤2 个（超 → 告警不阻断）
     L9 **非「可打开」的外链必须有「人工点验」留痕**（阻断）：机器给不出结论的
        （本机不可达 / 站点反爬），要么机器验真通过，要么有人真在浏览器点开过
        —— 留痕写在批次配置 `notes[*].link_verified`，用 link_check.py --mark-verified 写入

  B. 文本
     T1 正文零改动：AFTER 摘除全部注入物后与基线逐行等价（证明纯追加）
     T2 标注块数 == 配置条数
     T3 每条标注块字段完整（徽标 / 标题 / 生效日期 / 来源 / 官方链接）
     T4 校对ID 齐全且唯一（走 data-cg-rid 属性 —— 2026-09-23 起不进页面文本）
     T5 HTML 结构干净（div 配平、无平台截断产生的半截标签）
     T6 标注块内无内部流程用语（内部版/底稿/待补/TODO 等）
     T7 版本条计数与配置一致
     T8 说明文本与溯源状态一致（防「已换官方源」却仍写「未取得官方原文」）

  R. 前端渲染（★ 2026-09-23 线上事故后新增，最关键）
     R1 无 `</div><` 危险邻接 —— 前端 walker 推进 u=d+7（`</div>` 只有 6 字符）会
        越过 1 个字符，紧贴的下一个标签被整条跳过 ⇒ div 深度失衡 ⇒ 后续章节全灭
        ⇒ 线上报「无法加载内容。h2Content为空。」
     R2 复刻前端朴素 indexOf 算法，必须能发现**全部**章节
        （本地正则解析全通过 ≠ 线上能渲染，必须以复刻的 walker 为准）

  E. 生效状态（★ 2026-09-23 新增）
     E1 每条「待更新」必须有可解析的生效日期（否则无法判定计划/已变更）
     E2 产物里 data-cg-eff 与按写入日重算的结果一致，且文案写明
        「已正式生效」/「计划变更」（防手写文案漂移）
     E3 **配色档**（data-cg-tone）与（status × 生效状态）重算一致 —— 口径详见
        guide_patch_lib.TONE：绿 = 今年有变更且已生效｜橙黄 = 变更尚未生效｜
        红 = 来源存疑待核｜**中性灰 = 无需更新（维持现状不标绿）**
        （Yoyo 2026-09-23：改配色只改常量，产物必须跟着走，否则页面颜色与规定不符）

  F. 客户向文案（★ 2026-09-23 新增，「写这个是给客户看的」）
     F1 「正文版本」= 最新校验时间的**月**粒度（如 2026-09），且必须等于重算值
     F2 页面**不出现**内部过程时间字段（校验时间 / 最新校验 / 校对日期）
     F3 状态文案只准用客户语言（已正式生效 / 计划变更），旧文案一律不合格
     F4 页面**不出现**内部过程字段（标注写入 / 校对ID / **页面位置**）—— 只记台账，
        机器定位走 data-cg-rid / data-cg-anchor 属性

  CQ. 内容质量 · 全文（★ 2026-09-23 新增，Yoyo：「这些原来的问题也一起看下，
      归属内容质量-排版维度，或者配图」）
     前面 A–F 管的是**我们注入的那几个标注块**；CQ 管的是**整篇正文** ——
     历史遗留的排版与配图问题，一直在线上，只是以前没人拦。
     CQ1 **配图来源**：占位图 / 相对路径 / 空 src / alt 敷衍 → 阻断；
         非自有域图床 → 告警（自有图床化）；`--cq-probe-images` 时探测可达性，死链阻断
     CQ2 **排版真值**（`--cq-mode live` 真渲染）：正文内非标题元素字号越界（>24px = 层级倒置）、
         低于可读下限（<12px）、横向溢出、同类卡片高度不齐 → 阻断；
         图片被放大发虚 → 告警
     判定唯一实现 = `content_quality.py`（政策在 `references/image-hosts.json`），本文件只调用。

  G. 落线资格（批次级）
     G1 配置 mode == production-ready
     G2 official_name / trace 已填（溯源留档完整，供飞书台账）

用法：
  python3 qc_gate.py --config ../references/batches/uae-v3.json --workdir /path/to/_pilot_UAE
  python3 qc_gate.py --config ... --workdir ... --md-out _qc_report.md
  python3 qc_gate.py ... --link-mode cache     # 复用已有 _link_check.json（离线/负向测试）
  python3 qc_gate.py ... --link-mode off       # 跳过外链校验（仅排障；L5 降为告警）
  python3 qc_gate.py ... --cq-mode live --cq-probe-images   # 加跑渲染排版 + 配图探测
退出码：0 = 全部通过（可上线）；1 = 存在阻断项（拒绝上线）。
"""
import argparse
import datetime
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import guide_patch_lib as L  # noqa: E402
import link_check as LC  # noqa: E402
import content_quality as CQ  # noqa: E402  内容质量（排版·配图）唯一实现

HERE = os.path.dirname(os.path.abspath(__file__))

# 标注块内不允许出现的内部流程用语（只查标注块，不碰正文 —— 正文由 T1 保证零改动）
BAD_TEXT = ["内部版", "客户版", "交付侧", "底稿", "我司", "我方",
            "暂不上线", "待补", "占位", "TODO", "TBD", "XXX", "{{", "}}",
            "测试数据", "示例文案"]


# 注入物识别 / 摘除 / 正文比对：唯一实现在 guide_patch_lib（此处只做别名，别再抄一份）
canonical = L.canonical
strip_injections = L.strip_injections
note_blocks = L.note_blocks
urls_in = L.urls_in


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--workdir", default=None, help="含 content_ORIGINAL/AFTER.html 的工作目录")
    ap.add_argument("--json-out", default=None)
    ap.add_argument("--md-out", default=None)
    ap.add_argument("--link-mode", choices=["live", "cache", "off"], default="live",
                    help="外链校验（L5）：live=实时探测并落 _link_check.json（默认）｜"
                         "cache=复用已有结论（离线/负向测试）｜off=跳过（排障，L5 降为告警）")
    ap.add_argument("--link-tries", type=int, default=3, help="每条链接探测次数（抗网络抖动）")
    ap.add_argument("--link-timeout", type=int, default=12)
    ap.add_argument("--cq-mode", choices=["static", "live", "off"], default="static",
                    help="内容质量（CQ1 配图来源 / CQ2 排版真值）：static=只扫产物 HTML（默认，离线可跑）｜"
                         "live=另跑无头 Chrome 真渲染（排版真值，需网络）｜off=跳过")
    ap.add_argument("--cq-live-url", default=None,
                    help="--cq-mode live 时要渲染的 URL（逗号分隔）；缺省则用配置里的 guide_url")
    ap.add_argument("--cq-probe-images", action="store_true",
                    help="对图片做可达性探测（域名不存在/404 → 阻断）")
    ap.add_argument("--cq-img-cache", default=None, help="图片探测缓存（默认 <workdir>/_img_check.json）")
    ap.add_argument("--live", action="store_true",
                    help="（已废弃）旧参数；外链校验现在默认开启，见 --link-mode")
    a = ap.parse_args()

    cfg = json.load(open(a.config, encoding="utf-8"))
    checks, rows, warn_rows = [], [], []
    cq_mode = a.cq_mode
    cq_all = []          # 内容质量明细（排版/配图），按国家汇总进报告

    def add(cid, group, name, ok, detail, blocking=True):
        checks.append(dict(id=cid, group=group, name=name, ok=bool(ok),
                           detail=str(detail), blocking=blocking))

    # ── 外链可达性（L5/L9 的数据源）────────────────────────────────────────
    # 做实现在 link_check.py；这里只负责"什么时候探、探完怎么判"。
    # 一次校验的口径 = **死链一票否决**，环境类问题（本机不可达/站点反爬）不拦业务。
    cache = os.path.join(a.workdir, "_link_check.json") if a.workdir else None
    link_mode = "off" if a.link_mode == "off" else a.link_mode
    link_res, link_summ = [], None
    if link_mode == "live":
        pairs = LC.collect_from_config(cfg)
        # 带上一次结论：网络抖动不得推翻「已验真通过」（理由见 link_check._inherit）
        prev, _s = LC.load_cache(cache)
        link_res, link_summ = LC.run(pairs, tries=a.link_tries, timeout=a.link_timeout,
                                     prev=prev)
        if cache:
            LC.save_cache(cache, link_res, link_summ)
        print(f"· 外链校验（实时探测 {len(link_res)} 条）："
              f"可打开 {link_summ[LC.OK]} ｜ 死链 {link_summ[LC.DEAD]} ｜ "
              f"需人工点验 {len(link_summ['manual_urls'])}"
              + (f" ｜ 其中 {len(link_summ['inherited'])} 条继承上次验真结论"
                 if link_summ.get("inherited") else ""))
    elif link_mode == "cache":
        link_res, link_summ = LC.load_cache(cache)
        if link_summ is None:
            link_res, link_summ = [], None
            print(f"· 外链校验：未找到 {cache} —— L5 将判为未校验（阻断）")
        else:
            print(f"· 外链校验（复用 {os.path.basename(cache)}，生成于 {link_summ.get('at')}）")
    else:
        print("· 外链校验：--link-mode off，已跳过（L5 降为告警）")

    by_rid = {}
    for g in (link_res or []):
        by_rid.setdefault(g.get("rid"), []).append(g)

    # ── G 组：批次落线资格 ───────────────────────────────────────────────
    add("G1", "落线资格", "配置 mode = production-ready",
        cfg.get("mode") == "production-ready", f"mode={cfg.get('mode')!r}")

    for slug, cc in cfg["countries"].items():
        # ★ 页面侧校验的基数 = page_notes()（Yoyo 2026-09-23 四轮：「红色 存疑 先不在前端展示」）
        #   全量另存 all_notes，仅供「未上页面」那条信息性检查与台账留痕。
        #   判定唯一入口在 guide_patch_lib.on_page() —— 这里**不许**再写 `status=="check"`。
        all_notes = cc["notes"]
        notes = L.page_notes(all_notes)
        hid = L.hidden_notes(all_notes)

        rid_missing = [n.get("rid") for n in notes if not n.get("official_name") or not n.get("trace")]
        add("G2", "落线资格", f"[{slug}] official_name / trace 已填（溯源留档）",
            not rid_missing, f"缺 {len(rid_missing)} 条" + (f"：{rid_missing[:3]}" if rid_missing else ""))

        # ── A 组：链接 ──────────────────────────────────────────────────
        no_url = [n["rid"] for n in notes if not n.get("official_url")]
        add("L1", "链接", f"[{slug}] 每条标注都有官方原文链接（official_url）",
            not no_url, f"{len(notes) - len(no_url)}/{len(notes)} 条有源" +
                        (f"，缺：{no_url}" if no_url else ""))

        bad_v, good_v = [], 0
        for n in notes:
            if not n.get("official_url"):
                continue
            vd, h = L.classify_source(n["official_url"])
            if vd == "official":
                good_v += 1
            else:
                bad_v.append((n["rid"], vd, h))
            # L6：解读链接必须站内（internal）—— 独立阻塞项，不污染 L2 的 bad_v
            if n.get("interpret_url"):
                ivd, ih = L.classify_source(n["interpret_url"])
                add("L6", "链接", f"[{slug}] {n['rid']} 解读链接站内（internal）",
                    ivd == "internal", f"判定 {ivd}: {ih}" + ("" if ivd == "internal"
                    else " —— 只能跳 humancehr.com/anchorwe.com"))
            # L7：工具入口每条必须站内（internal）—— 独立阻塞项
            for ti, e in enumerate(n.get("tool_entries") or []):
                if not e.get("url"):
                    continue
                tvd, th = L.classify_source(e["url"])
                add("L7", "链接", f"[{slug}] {n['rid']} 工具入口#{ti + 1} 站内（internal）",
                    tvd == "internal", f"判定 {tvd}: {th}" + ("" if tvd == "internal"
                    else " —— 只能跳 humancehr.com/anchorwe.com"))
            # L8：工具入口数量建议 ≤2（告警不阻断）
            nt = len([e for e in (n.get("tool_entries") or []) if e.get("url")])
            if nt > 2:
                add("L8", "链接", f"[{slug}] {n['rid']} 工具入口 {nt} 个（建议 ≤2）",
                    False, f"当前 {nt} 个，超过建议上限", blocking=False)
            rows.append(dict(slug=slug, rid=n["rid"], title=n.get("title"),
                             status=n.get("status"), effective=n.get("effective"),
                             official_url=n.get("official_url"), official_host=h, verdict=vd,
                             official_name=n.get("official_name"),
                             orig_source=n.get("orig_source"), orig_url=n.get("url"),
                             interpret_url=n.get("interpret_url"),
                             tool_entries=n.get("tool_entries"),
                             trace=n.get("trace")))
        add("L2", "链接", f"[{slug}] 官方链接全部通过白名单判定",
            not bad_v, f"官方 {good_v} 条" + (f"；不合格 {bad_v}" if bad_v else ""))

        # ── L5 官方外链「能不能打开」（Yoyo 2026-09-23 新增，阻断）──────────────
        # 口径：**死链（4xx）一票否决**；本机不可达 / 站点反爬（403 等）不算死链 ——
        # 那是"我们这台机器的网络问题"，不是"客户打不开"。理由与分类见 link_check.py 文件头。
        mine = [g for n in notes if n.get("official_url")
                for g in by_rid.get(n["rid"], [])]
        seen_u = set()
        mine = [g for g in mine if not (g["url"] in seen_u or seen_u.add(g["url"]))]
        dead = [g for g in mine if LC.verdict(g) == "block"]
        manual = [g for g in mine if LC.verdict(g) == "manual"]
        if link_mode == "off":
            add("L5", "链接", f"[{slug}] 官方外链可打开（未校验）", False,
                "--link-mode off：跳过外链校验（仅排障允许，不得用于真实落线）", blocking=False)
        elif not mine:
            add("L5", "链接", f"[{slug}] 官方外链可打开",
                False, f"没有拿到任何探测结论（link-mode={link_mode}"
                       + ("，缺 _link_check.json" if link_mode == "cache" else "") + "）")
        else:
            add("L5", "链接", f"[{slug}] 官方外链可打开（无死链）",
                not dead,
                f"探测 {len(mine)} 条：可打开 {sum(1 for g in mine if LC.verdict(g) == 'pass')}"
                f" ｜ 死链 {len(dead)} ｜ 需人工点验 {len(manual)}"
                + (f"；死链必须换链接：{[(g['rid'], g['url'][:70], g['samples'][:2]) for g in dead]}"
                   if dead else ""))
        # ── L9 非「可打开」的外链必须有**人工点验留痕**（阻断）★ ────────────────
        # 本机/沙箱对部分官方站不可达（政府站挡自动化、网络策略不同），机器**永远**
        # 给不出结论。所以口径是：**要么机器验真通过，要么有人真在浏览器里点开过**。
        # 留痕写在批次配置 `notes[*].link_verified`（格式见 SKILL.md / update-annotation-spec §19），
        # 写入工具：`python3 link_check.py --config <cfg> --mark-verified <rid,...>`。
        pending, verified = [], []
        for n in notes:
            for g in by_rid.get(n["rid"], []):
                if LC.verdict(g) != "manual":
                    continue
                if LC.verified_of(n):
                    v = LC.verified_of(n)
                    verified.append(f"{n['rid']}（{v.get('by')} @ {v.get('at')}）")
                else:
                    pending.append(f"{n['rid']} {LC.LABEL[g['cls']]} {g['url']}")
        if manual:
            add("L9", "链接", f"[{slug}] 非「可打开」外链已人工点验（{len(manual)} 条）",
                not pending,
                ("已留痕：" + "；".join(sorted(set(verified)))
                 if not pending else
                 "以下外链本机给不出结论（站点反爬 / 网络不可达），**必须人工点开确认**后"
                 "用 `link_check.py --mark-verified` 留痕，否则不得上线：\n           · "
                 + "\n           · ".join(pending)))

        f_after = os.path.join(a.workdir, slug, "content_AFTER.html") if a.workdir else None
        f_before = os.path.join(a.workdir, slug, "content_ORIGINAL.html") if a.workdir else None
        if not f_after or not os.path.exists(f_after):
            add("T1", "文本", f"[{slug}] 存在 AFTER 产物", False,
                f"未找到 {f_after}（先跑 batch_guide_patch.py 本地构建）")
            continue

        after = open(f_after, encoding="utf-8").read()
        before = open(f_before, encoding="utf-8").read() if os.path.exists(f_before) else ""

        blocks = note_blocks(after)
        off_lnk = after.count(">官方原文 ↗</a>")
        # ★ 2026-09-23：「数量对」升级为「数量 + 指向都对」。
        #   只数条数的话，构建时 href 串了行（指向另一个国家的法规页）照样通过 ——
        #   这种错在页面上看不出来，客户点开才发现。等价比对才拦得住。
        _got_h, _cfg_h = L.official_hrefs(after), L.official_hrefs_cfg(notes)
        _lnk_ok = (off_lnk == len(notes)) and (sorted(_got_h) == sorted(_cfg_h))
        if off_lnk != len(notes):
            _lnk_msg = f"{off_lnk}/{len(notes)} 条"
        elif sorted(_got_h) != sorted(_cfg_h):
            _bad = [u for u in _got_h if u not in _cfg_h][:2]
            _lnk_msg = f"指向不一致，产物多/错：{_bad}"
        else:
            _lnk_msg = f"{off_lnk}/{len(notes)} 条，href 与配置逐条一致"
        add("L4", "链接", f"[{slug}] 产物「官方原文 ↗」数量与指向均与配置一致",
            _lnk_ok, _lnk_msg)

        leaked = []
        for blk in blocks:
            for u in urls_in(blk):
                vd, h = L.classify_source(u)
                if vd not in ("official", "internal"):
                    leaked.append((vd, h, u[:70]))
        add("L3", "链接", f"[{slug}] 标注块内只出现官方+站内链接（无站外三方）",
            not leaked, "全部为 official/internal" if not leaked else f"发现 {len(leaked)} 条非法：{leaked[:3]}")

        # 外链探测结果原样进报告（含每条的样本，便于人工复核"为什么判成这个"）
        for g in (link_res or []):
            warn_rows.append((g.get("rid") or "-", g["host"], g["cls"] == LC.OK,
                              f"{LC.LABEL[g['cls']]} ｜ {g['samples']}"))

        # ── B 组：文本 ──────────────────────────────────────────────────
        if before:
            # 口径 = 「零**未申报**改动」（2026-09-23 立）：
            #   基准侧 = 摘除注入物 + **套用申报修复**；产物侧 = 只摘除注入物（不套）。
            #   两侧相等 ⇒ 产物相对基线的全部改动恰好就是申报的那些。
            #   ⚠️ 刻意只对基准侧套：两侧都套的话，"申报了却没落地"会被判相等（假通过）。
            same = L.candidate_body(after) == L.baseline_body(before, slug)
            add("T1", "文本", f"[{slug}] 正文零**未申报**改动（摘除注入物 + 套用申报修复后与基线等价）",
                same, "逐行等价" if same else
                "正文被改动过 —— 只允许纯追加，或先在 references/body-fixes.json 申报")
        else:
            add("T1", "文本", f"[{slug}] 有基线可比对", False, f"缺 {f_before}", blocking=True)

        # ── BF 组：申报式正文修复（2026-09-23 建）───────────────────────
        # 这是"豁免"而非"放宽"：豁免必须**定向、留痕、可独立复核**（同质量豁免单的纪律）。
        _bf_applicable = L.body_fixes_for(slug)
        if _bf_applicable:
            _bad = [r for r in L.audit_body_fixes(after, slug) if not r["ok"]]
            add("BF1", "文本", f"[{slug}] 申报的正文修复均已生效（find 无残留 + replace 已出现）",
                not _bad,
                "；".join(f"{r['id']} {r['msg']}" for r in _bad) if _bad else
                "、".join(f"{f['id']} ✅" for f in _bf_applicable))
            _orphan = L.orphan_body_fixes(slug, before)
            add("BF2", "文本", f"[{slug}] 无过期申报（申报条目在基线中仍命中）",
                not _orphan,
                "全部命中" if not _orphan else
                f"未命中 {_orphan} —— 基线可能已被他人修好，须复核并移除注册表条目",
                blocking=False)
        _missf = L.body_fixes_missing_fields()
        add("BF3", "文本", "申报修复注册表条目字段完整（id/slug/find/replace/why/evidence/owner/found_at）",
            not _missf,
            f"共 {len(L.load_body_fixes())} 条，字段齐全" if not _missf else
            "；".join(f"{i} 缺 {'/'.join(m)}" for i, m in _missf))

        add("T2", "文本", f"[{slug}] 标注块数 = 配置条数",
            len(blocks) == len(notes), f"{len(blocks)}/{len(notes)}")

        # 2026-09-23 起「标注写入 / 校对ID」撤出页面文本，只记台账 ⇒ 不再作为可见要素要求
        need = ["cg-update-note", "生效日期", "来源：", 'data-cg-rid="']
        miss = []
        for i, blk in enumerate(blocks):
            for k in need:
                if k not in blk:
                    miss.append(f"#{i + 1}缺{k}")
            if "官方原文 ↗" not in blk:
                miss.append(f"#{i + 1}缺官方链接")
        add("T3", "文本", f"[{slug}] 每条标注块字段完整", not miss,
            "要素齐全（徽标/标题/生效日期/来源/官方链接/定位属性）" if not miss
            else f"{len(miss)} 处缺失：{miss[:4]}")

        rids_cfg = [n["rid"] for n in notes]
        # 校对ID 走 data-cg-rid **属性**（不进页面文本，客户看不到，但机器可定位）
        rids_out = re.findall(r'data-cg-rid="(PR-\d{8}-\d+)"', after)
        dup = len(rids_out) != len(set(rids_out))
        add("T4", "文本", f"[{slug}] 校对ID 齐全且唯一（data-cg-rid 属性）",
            sorted(set(rids_out)) == sorted(set(rids_cfg)) and not dup
            and len(rids_out) == len(notes),
            f"属性 {len(rids_out)} 个 / 配置 {len(notes)} 个" + ("，有重复" if dup else ""))

        divok = after.count("<div") == after.count("</div>")
        # 「半截标签」判的是**新增**的断标签（平台派生截断产物，如 `…首都</s`），
        # 基线自带的自定义元素（原文里有 `<contact-qrcode>`）不算。
        # 注意别写成 `</s(?!tyle)` —— 它会把 `</span>`/`</strong>` 全算成截断（已踩过）。
        def n_half(h):
            return len(re.findall(r"</(?!\w+\s*>)", h)) + len(re.findall(r"<(?!/|!|\w)", h))
        hb = n_half(before) if before else 0
        ha = n_half(after)
        add("T5", "文本", f"[{slug}] HTML 结构干净（div 配平、无新增断标签）",
            divok and ha <= hb, f"div {after.count('<div')}/{after.count('</div>')}，"
                                f"断标签 {ha} 处（基线 {hb}）→ 新增 {ha - hb}")

        bad_words = [(w, i + 1) for i, blk in enumerate(blocks) for w in BAD_TEXT if w in blk]
        add("T6", "文本", f"[{slug}] 标注块无内部流程用语", not bad_words,
            "干净" if not bad_words else f"{bad_words[:4]}")

        n_pending = sum(1 for n in notes if n.get("status") == "pending")
        n_check = sum(1 for n in notes if n.get("status") == "check")
        n_keep = sum(1 for n in notes if n.get("status") == "keep")
        vc = L.version_counts(notes)                  # 计数口径唯一实现（在 lib）
        n_eff, n_sch = vc["n_eff"], vc["n_sch"]
        p_pend, p_eff, p_sch = L.version_bar_probe(notes)
        add("T7", "文本", f"[{slug}] 版本条计数与配置一致",
            p_pend in after and f'本次标注：<strong>{len(notes)} 项</strong>' in after
            and all(f in after for f in (p_eff, p_sch) if f),
            f"pending={n_pending} check={n_check} keep={n_keep} total={len(notes)} "
            f"{L.EFF_TEXT['effective']}={n_eff} {L.EFF_TEXT['scheduled']}={n_sch}")

        # T8：说明文本与溯源状态一致性 —— 防「溯源后忘了改文案」（阿联酋 PR-048/049 真实踩过：
        # trace 已写「已换官方源」，extra 里却还留着「未取得 GPSSA 官方原文」）
        STALE = re.compile(r"(未|尚未|没有|未能)取得[^。；]{0,16}官方"
                           r"|(须|需|待)以[^。；]{0,16}官方[^。；]{0,8}(核实|确认)")
        stale = []
        for i, blk in enumerate(blocks):
            m = STALE.search(blk)
            if m:
                stale.append(f"#{i + 1}「{m.group(0)[:24]}」")
        add("T8", "文本", f"[{slug}] 说明文本与溯源状态一致（无「未取得官方源」类过时表述）",
            not stale, "一致" if not stale else
            f"{len(stale)} 处说明写于溯源之前，须改写：{stale[:3]}")

        # ── R 组：前端渲染（2026-09-23 线上事故后新增，最关键）──────────────
        unsafe = L.walk_unsafe_spans(after)
        add("R1", "前端渲染", f"[{slug}] 无 `</div><` 危险邻接（前端 walker 会跳标签）",
            not unsafe,
            f"0 处" if not unsafe else
            f"{len(unsafe)} 处 —— 会让前端 u=d+7 越位跳标签、后续章节 h2Content 为空；"
            f"例 {[after[max(0, p - 26):p + 18] for p in unsafe[:2]]}")
        want_titles = [t for _o, t, _p in L._section_map(after)]
        vis = set(L.frontend_visible_sections(after))
        miss_sec = [t for t in want_titles if t not in vis]
        add("R2", "前端渲染", f"[{slug}] 复刻前端 walker 能发现全部章节",
            not miss_sec,
            f"发现 {len(vis)}/{len(want_titles)} 章" +
            (f"，线上将报「h2Content为空」：{miss_sec}" if miss_sec else ""))

        # ── E 组：生效状态（2026-09-23 新增，「计划/已生效」判定）────────────
        no_date = [n["rid"] for n in notes
                   if n.get("status") == "pending" and L.effective_state(n.get("effective")) == "na"]
        add("E1", "生效状态", f"[{slug}] 待更新条目均有可解析生效日期",
            not no_date,
            "全部可判定" if not no_date else
            f"{len(no_date)} 条无可解析生效日期（无法判定计划/已生效）：{no_date}")
        eff_bad = []
        for m in re.finditer(r'<div class="cg-update-note"([^>]*)>', after):
            at = m.group(1)
            rid = (re.search(r'data-cg-rid="([^"]*)"', at) or [None, "?"])[1]
            eff = (re.search(r'data-cg-effective="([^"]*)"', at) or [None, ""])[1]
            got = (re.search(r'data-cg-eff="([^"]*)"', at) or [None, ""])[1]
            wnt = L.effective_state(eff)
            if got != wnt:
                eff_bad.append(f"{rid}: 标 {got!r} 应为 {wnt!r}")
                continue
            seg = after[m.start():m.start() + 2600]
            seg = seg[:seg.find("</div>")] if "</div>" in seg else seg
            if wnt == "effective" and L.EFF_TEXT["effective"] not in seg:
                eff_bad.append(f"{rid}: 生效日 {eff} 已过但未写「{L.EFF_TEXT['effective']}」")
            if wnt == "scheduled" and L.EFF_TEXT["scheduled"] not in seg:
                eff_bad.append(f"{rid}: 生效日 {eff} 未到但未写「{L.EFF_TEXT['scheduled']}」")
        add("E2", "生效状态", f"[{slug}] 生效状态判定与页面文案一致",
            not eff_bad,
            f"待更新 {n_pending} 项中 {L.EFF_TEXT['effective']} {n_eff} · "
            f"{L.EFF_TEXT['scheduled']} {n_sch}" if not eff_bad
            else f"{len(eff_bad)} 处不一致：{eff_bad[:3]}")

        # ── E3：配色档（tone）与重算一致（2026-09-23 新增）★ ──────────────────
        # 配色是**派生值**（status × 生效状态），产物里的 data-cg-tone 必须等于按配置重算的结果。
        # 防的是「改了配色口径、产物里还是旧色」—— 这类漂移在页面上看得出来，
        # 但没人会为此开单（Yoyo 2026-09-23 之前就一直是"看得出来没人报"），所以必须机器拦。
        tone_bad, tone_cnt = [], {}
        _by_rid_cfg = {n["rid"]: n for n in notes}
        for m in re.finditer(r'<div class="cg-update-note"([^>]*)>', after):
            at = m.group(1)
            rid = (re.search(r'data-cg-rid="([^"]*)"', at) or [None, "?"])[1]
            note = _by_rid_cfg.get(rid)
            if not note:
                continue
            got_t = (re.search(r'data-cg-tone="([^"]*)"', at) or [None, ""])[1]
            wnt_t = L.tone_of(note)
            tone_cnt[wnt_t] = tone_cnt.get(wnt_t, 0) + 1
            if got_t != wnt_t:
                tone_bad.append(f"{rid}: 标 {got_t!r} 应为 {wnt_t!r}")
        add("E3", "生效状态", f"[{slug}] 配色档与（status × 生效状态）重算一致",
            not tone_bad,
            ("配色 " + "、".join(f"{k}×{v}" for k, v in sorted(tone_cnt.items())))
            if not tone_bad else f"{len(tone_bad)} 处不一致：{tone_bad[:3]}")

        # ── F 组：客户向文案（2026-09-23 新增，「写这个是给客户看的」）────────
        # 版本条面向出海中企 HR：不暴露内部过程时间，状态用客户语言，日期只到月。
        dm = L.version_bar_dates(dict(cc, batch=cfg.get("batch"),
                                      review_date=cfg.get("review_date")))
        mvb = re.search(r'正文版本：<strong>([^<]*)</strong>', after)
        got_bv = mvb.group(1) if mvb else ""
        add("F1", "客户向文案",
            f"[{slug}] 「正文版本」= 最新校验时间的月粒度（如 2026-09）",
            bool(mvb) and re.fullmatch(r"\d{4}-\d{2}", got_bv or "") is not None
            and (not dm["body_version"] or got_bv == dm["body_version"]),
            f"页面 {got_bv!r} ／ 应 {dm['body_version']!r}（最新校验月；无则须为 YYYY-MM）")

        leak_time = [x for x in ("校验时间", "最新校验", "校对日期") if x in after]
        add("F2", "客户向文案", f"[{slug}] 页面不出现内部过程时间字段",
            not leak_time,
            "干净（无校验时间/最新校验/校对日期）" if not leak_time else
            f"出现 {leak_time} —— 客户向页面不得展示内部过程时间")

        # 旧文案合集 = 标注状态（已核实维持/计划更新）+ 生效状态（法规已生效/计划生效），
        # 唯一真相源 guide_patch_lib.STALE_COPY（validate 的 F3、二次校验的 S12 引同一份）。
        stale_txt = [x for x in L.STALE_COPY if x in after]
        add("F3", "客户向文案",
            f"[{slug}] 状态文案为客户端向（{L.STATUS_TEXT['keep']} / "
            f"{L.EFF_TEXT['effective']} / {L.EFF_TEXT['scheduled']}）",
            not stale_txt,
            "文案正确" if not stale_txt else
            f"残留旧文案 {stale_txt} —— 应为 "
            + " / ".join(list(L.STATUS_TEXT.values())
                         + [v for v in L.EFF_TEXT.values() if v]))

        # ── F4：内部过程字段不得出现在页面（Yoyo 2026-09-23）★ ──────────────
        # 截图圈出的「标注写入：2026-09-23 ｜ 校对 ID PR-... ｜ 页面位置：薪酬支付」
        # → 三样全部撤出页面、只记台账。
        # 定位能力改由 data-cg-rid / data-cg-anchor 属性承载（不可见但可查），
        # 故撤出文本不损失任何能力。
        # 清单唯一真相源 = guide_patch_lib.INTERNAL_FIELDS（qc/validate/verify 三处共用）。
        leaked_int = [x for x in L.INTERNAL_FIELDS if x in after]
        add("F4", "客户向文案",
            f"[{slug}] 页面不出现内部过程字段（标注写入 / 校对ID / 页面位置）",
            not leaked_int,
            "干净（定位走 data-cg-rid / data-cg-anchor 属性，只记台账）" if not leaked_int else
            f"出现 {leaked_int} —— 客户向页面不得展示，应只记飞书台账"
            f"（台账列：更新时间 / 校对ID / 落位章节）")

        # ── F5：红色档（来源存疑）不得出现在页面（Yoyo 2026-09-23 四轮，阻断）★ ──
        # 口径：页面只出现两类 —— 绿（不用管）与 橙黄（计划变更未落地）。
        # 「来源存疑」既不展示、也不进版本条计数（客户看到"待核 2 项"却找不到那两块，
        # 只会以为页面坏了），只记台账待处理；补齐一手源后再落线，那时它会以绿/橙黄回来。
        # 判定唯一入口 = guide_patch_lib.on_page()；这里只做**产物侧复核**（防漏滤）。
        # ⚠️ 必须先剥 <style>：徽标样式块里有 `[data-cg-tone="…"]` 选择器
        #    （生成端已剔除 verify，但旧产物 / 手改产物未必）—— 全文 count 会误报。
        _red_hits = re.findall(r'data-cg-tone="verify"', L.strip_style(after))
        add("F5", "客户向文案",
            f"[{slug}] 页面不出现红色档（来源存疑不上前端，只记台账）",
            not _red_hits,
            (f"干净（页面 {len(notes)} 项，未上页面 {len(hid)} 项"
             + (f"：{'、'.join(n['rid'].replace('PR-20260907-', 'PR-') for n in hid)}"
                if hid else "") + "）")
            if not _red_hits else
            f"页面出现 {len(_red_hits)} 处 data-cg-tone=\"verify\" —— 该类条目不上前端，"
            f"过滤入口 = guide_patch_lib.page_notes()")
        # F6：未上页面条目必须留痕（谁、哪一章、什么状态）—— 非阻断，但必须出现在 QC 报告里，
        #     否则"暂时撤下"会变成"悄悄消失"（没人记得去补源）。
        if hid:
            add("F6", "客户向文案",
                f"[{slug}] 未上页面条目已留痕（台账「页面展示=否 · 待处理」）",
                all(n.get("anchor") for n in hid),
                "；".join(f"{n['rid'].replace('PR-20260907-', 'PR-')} "
                          f"{n.get('title') or ''}（status={n.get('status')}）" for n in hid),
                blocking=False)

        # ── CQ：内容质量 · 全文（排版 / 配图）────────────────────────────────
        # 前面 A–F 只证明"我们注入的标注块"没问题；CQ 看**整篇正文**。
        # Yoyo 2026-09-23：「这些原来的问题也一起看下，归属内容质量-排版维度，或者配图」。
        if cq_mode != "off":
            cq_finds, cq_imgs, _ = CQ.scan_html(
                after, probe=a.cq_probe_images,
                img_cache=(a.cq_img_cache or
                           (os.path.join(a.workdir, "_img_check.json") if a.workdir else None)))
            cq_blocks_img = [f for f in cq_finds if f["dim"] == "配图" and f["level"] == "block"]
            cq_warns_img = [f for f in cq_finds if f["dim"] == "配图" and f["level"] == "warn"]
            add("CQ1", "内容质量",
                f"[{slug}] 配图来源合规（占位图 / 相对路径 / 空 src / alt）",
                not cq_blocks_img,
                f"干净：{len(cq_imgs)} 张图（自有域 "
                f"{sum(1 for i in cq_imgs if i['kind'] == 'own')}，非自有域告警 {len(cq_warns_img)} 条）"
                if not cq_blocks_img else
                f"{len(cq_blocks_img)} 处不合格 —— " + "；".join(
                    f"[{f['id']}] {f['item']}：{f['detail'].splitlines()[0][:120]}"
                    for f in cq_blocks_img[:3]))
            cq_dyn = []
            if cq_mode == "live":
                urls = a.cq_live_url or cc.get("guide_url")
                for u in [x.strip() for x in str(urls or "").split(",") if x.strip()]:
                    f2, _raw = CQ.render_check(u, tag=f"{slug}_{abs(hash(u)) % 9999}")
                    cq_dyn += f2
                cq_blocks_typo = [f for f in cq_dyn if f["dim"] == "排版" and f["level"] == "block"]
                cq_blocks_dimg = [f for f in cq_dyn if f["dim"] == "配图" and f["level"] == "block"]
                cq_known = [f for f in cq_dyn if f.get("known")]
                add("CQ2", "内容质量",
                    f"[{slug}] 排版真值（字号层级 / 溢出 / 卡片高度）",
                    not cq_blocks_typo,
                    f"干净（渲染 {len([x for x in str(urls or '').split(',') if x.strip()])} 页）"
                    if not cq_blocks_typo else
                    f"{len(cq_blocks_typo)} 处不合格 —— " + "；".join(
                        f"[{f['id']}] {f['detail'].splitlines()[0][:120]}" for f in cq_blocks_typo[:3]))
                if cq_known:
                    add("CQ4", "内容质量",
                        f"[{slug}] 已知缺陷基线（豁免单）命中（{len(cq_known)} 条，降级告警）",
                        True,
                        "已派单未整改：" + "、".join(
                            sorted({f"{f.get('known')}·{f.get('known_title', '')[:34]}" for f in cq_known}))
                        + " —— 见 references/quality-baseline.json；整改后删条目即恢复阻断")
                if cq_blocks_dimg:
                    add("CQ3", "内容质量",
                        f"[{slug}] 渲染后图片全部可显示（无破图）",
                        False,
                        f"{len(cq_blocks_dimg)} 张破图 —— " + "；".join(
                            f["detail"].splitlines()[0][:110] for f in cq_blocks_dimg[:3]))
            cq_all.append(dict(slug=slug, mode=cq_mode, findings=cq_finds + cq_dyn,
                               images=len(cq_imgs)))

    # ── 汇总 ────────────────────────────────────────────────────────────
    failed = [c for c in checks if not c["ok"] and c["blocking"]]
    passed = not failed
    rep = dict(batch=cfg.get("batch"), config=a.config,
               generated_at=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
               passed=passed, blocking_failed=len(failed),
               checks_total=len(checks), checks_failed=len([c for c in checks if not c["ok"]]),
               checks=checks, notes=rows,
               link_mode=link_mode, link_summary=link_summ,
               cq_mode=cq_mode, cq=cq_all,
               link_probe=[dict(rid=r, host=h, ok=o, msg=m) for r, h, o, m in warn_rows])

    print("=" * 74)
    print(f"上线前 QC 门禁　批次 {cfg.get('batch')}　{rep['generated_at']}")
    print("=" * 74)
    for c in checks:
        mark = "✅" if c["ok"] else ("❌" if c["blocking"] else "⚠️")
        print(f" {mark} [{c['id']:<2}] {c['group']} {c['name']}")
        if not c["ok"]:
            print(f"        ↳ {c['detail']}")
    if rows:
        print()
        print("逐条清单：")
        for r in rows:
            vd = {"official": "✅官方", "third_party": "❌三方", "unknown": "⚠️未知"}[r["verdict"]]
            print(f"  {vd} {r['rid']} {str(r['title'])[:22]:24} {r['official_host']}")
            print(f"        原引（仅留档不进页面）：{r['orig_source']} — {str(r['orig_url'])[:64]}")
    if warn_rows:
        print()
        print(f"外链可达性探测（link-mode={link_mode}｜L5 死链阻断，L9 未点验也阻断）：")
        for rid, h, ok, msg in warn_rows:
            print(f"  {'✅' if ok else '⚠️'} {rid} {h}")
            print(f"       {msg[:180]}")
    if cq_mode != "off" and cq_all:
        print()
        print(f"内容质量 · 全文（cq-mode={cq_mode}｜CQ1 配图来源，CQ2/CQ3 排版与渲染真值）：")
        for blk in cq_all:
            fl = blk["findings"]
            b = [x for x in fl if x["level"] == "block"]
            w = [x for x in fl if x["level"] == "warn"]
            print(f"  {blk['slug']}：图 {blk['images']} 张 · 阻断 {len(b)} · 告警 {len(w)}")
            for x in sorted(fl, key=lambda y: (0 if y["level"] == "block" else 1, y["id"]))[:8]:
                icon = "🛑" if x["level"] == "block" else "⚠️"
                print(f"     {icon} [{x['id']}] {x['item']} {x['detail'].splitlines()[0][:110]}")
    print()
    print("-" * 74)
    print(f"结论：{'✅ 全部通过，允许上线' if passed else '❌ ' + str(len(failed)) + ' 项阻断，拒绝上线'}")

    outp = a.json_out or (os.path.join(a.workdir, "_qc_report.json") if a.workdir else None)
    if outp:
        json.dump(rep, open(outp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"报告 → {outp}")
    if a.md_out:
        with open(a.md_out, "w", encoding="utf-8") as f:
            f.write(f"# 上线前 QC 报告 · {cfg.get('batch')}\n\n")
            f.write(f"- 生成时间：{rep['generated_at']}\n- 结论："
                    f"{'✅ 通过' if passed else '❌ 阻断'}（{len(failed)} 项未过）\n\n")
            f.write("## 检查项\n\n| 结果 | 编号 | 分组 | 检查项 | 说明 |\n|:-:|---|---|---|---|\n")
            for c in checks:
                f.write(f"| {'✅' if c['ok'] else ('❌' if c['blocking'] else '⚠️')} | {c['id']} | "
                        f"{c['group']} | {c['name']} | {c['detail']} |\n")
            f.write("\n## 官方外链可达性（L5 死链阻断 / L9 未点验也阻断）\n\n")
            if link_summ:
                f.write(f"- 校验方式：`{link_mode}`　生成于 {link_summ.get('at')}　共 {link_summ['total']} 条\n")
                f.write(f"- {LC.LABEL[LC.OK]} {link_summ[LC.OK]} ｜ {LC.LABEL[LC.DEAD]} "
                        f"{link_summ[LC.DEAD]} ｜ {LC.LABEL[LC.BLOCKED]} {link_summ[LC.BLOCKED]} ｜ "
                        f"{LC.LABEL[LC.SERVER_ERROR]} {link_summ[LC.SERVER_ERROR]} ｜ "
                        f"{LC.LABEL[LC.UNREACHABLE]} {link_summ[LC.UNREACHABLE]}\n\n")
                f.write("| 校对ID | 域名 | 结论 | 逐次探测 |\n|---|---|:-:|---|\n")
                for g in (link_res or []):
                    f.write(f"| {g.get('rid') or '—'} | `{g['host']}` | {g['label']} | "
                            f"{'；'.join(g['samples'])[:200]} |\n")
            else:
                f.write(f"- ⚠️ 未取得探测结论（link-mode=`{link_mode}`）—— 不得用于真实落线\n")
            f.write("\n## 内容质量 · 全文（排版 / 配图）\n\n")
            if cq_mode == "off":
                f.write("- ⏭️ `--cq-mode off`，本轮跳过\n")
            else:
                f.write(f"- 检查方式：`{cq_mode}`（"
                        f"{'静态扫产物' if cq_mode == 'static' else '静态扫产物 + 无头 Chrome 真渲染'}）\n")
                f.write("- 判定实现：`scripts/content_quality.py`；配图政策：`references/image-hosts.json`\n\n")
                for blk in cq_all:
                    fl = blk["findings"]
                    b = [x for x in fl if x["level"] == "block"]
                    w = [x for x in fl if x["level"] == "warn"]
                    f.write(f"### {blk['slug']}（图 {blk['images']} 张 · 阻断 {len(b)} · 告警 {len(w)}）\n\n")
                    if not fl:
                        f.write("干净。\n\n")
                        continue
                    f.write("| 级别 | 维度 | 编号 | 位置 | 问题 | 建议 |\n|:-:|---|:-:|---|---|---|\n")
                    for x in sorted(fl, key=lambda y: (0 if y["level"] == "block" else 1, y["id"])):
                        f.write(f"| {'🛑' if x['level'] == 'block' else '⚠️'} | {x['dim']} | {x['id']} | "
                                f"{x['item']} | {x['detail'].splitlines()[0][:200]} | {x['fix'][:120]} |\n")
                    f.write("\n")
            f.write("\n## 逐条溯源清单\n\n| 校对ID | 项 | 状态 | 生效日期 | 生效判定 | 官方源 | 域名 | 判定 | 原引（留档） |\n")
            f.write("|---|---|---|---|---|---|:-:|---|:-:|\n")
            for r in rows:
                es = L.effective_state(r.get("effective"))
                f.write(f"| {r['rid']} | {r['title']} | {r['status']} | {r['effective']} | "
                        f"{L.EFF_TEXT.get(es) or '—'} | "
                        f"{r['official_name']} | `{r['official_host']}` | "
                        f"{'✅' if r['verdict'] == 'official' else '❌'} | {r['orig_source']} |\n")
        print(f"报告 → {a.md_out}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
