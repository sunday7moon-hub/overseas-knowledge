#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
两阶段发布 · 阶段二前置门禁「发布确认门禁」（P 组 · 7 项）
============================================================
这是 2026-09-23 Yoyo 要求补的**那一个门禁**：
「二次校验全文（内容质量及门禁）通过后，再正式上到线上，通过前先存本地，
  通过助手提示我的微信……待上线，同我确认，是否正式上线。」

它拦的是**流程性风险**（不是内容风险 —— 内容风险由 qc_gate 的 24 项和
verify_secondary 的 S1–S14 管）："准备上线的东西是不是已经过前两次校验、
是不是还在有效期内、是不是通知过我、我是不是真确认过、上线前有没有被人偷改"。

  P1  暂存清单存在且字段完整（每国 documentId / guide_url / sha / 产物路径齐全且文件在）
  P2  上线前 QC 全过（qc.passed 且 failed=0）
  P3  二次校验 · 全文校验（暂存稿，source=staging）全过
  P4  通知已送达（notify.sent=true，且四要素齐：国别指南 / 链接 / 校验结果 / 待上线）
  P5  暂存产物哈希未漂移（重算 content_AFTER sha == 清单记录；基线 ORIGINAL 也没变）
  P6  暂存未过期（默认 7 天，见 references/notify.json: release_ttl_days）
  P7  人工确认凭据有效（--approve all 或逗号分隔 slug，且与待上线条目有交集）

用法：
  python3 release_gate.py --workdir /path/to/_pilot_UAE                  # 只体检（P7 会判未确认）
  python3 release_gate.py --workdir ... --approve all --json-out /tmp/g.json
退出码：0 = P1–P7 全过（允许上线）；1 = 有阻断项。
"""
import argparse
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import guide_patch_lib as L  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
PENDING = "pending_release.json"


def load_pending(workdir):
    p = os.path.join(workdir, "_release", PENDING)
    if not os.path.exists(p):
        return None, p
    try:
        return json.load(open(p, encoding="utf-8")), p
    except Exception as e:
        return {"_parse_error": str(e)}, p


def gate(workdir, approve=None):
    ck = []
    rec, path = load_pending(workdir)

    def add(i, name, ok, detail):
        ck.append(dict(id=i, name=name, ok=bool(ok), detail=str(detail)))

    # P1 暂存清单完整
    if not rec or "_parse_error" in (rec or {}):
        add("P1", "暂存清单存在且可解析", False,
            f"{path} {'解析失败：' + rec['_parse_error'] if rec else '不存在 —— 先跑 release_stage.py'}")
        for i, n in [("P2", "上线前 QC 全过"), ("P3", "二次校验 · 全文校验（暂存稿）全过"),
                     ("P4", "通知已送达"), ("P5", "暂存产物无漂移"),
                     ("P6", "暂存未过期"), ("P7", "人工确认凭据有效")]:
            add(i, n, False, "无暂存清单")
        return ck, None
    items = rec.get("items") or []
    bad_fields = []
    for it in items:
        miss = [k for k in ("slug", "name", "documentId", "guide_url", "content_sha",
                            "after_path", "base_sha") if not it.get(k)]
        if miss:
            bad_fields.append(f"{it.get('slug', '?')} 缺 {miss}")
            continue
        for k in ("after_path", "preview_path"):
            v = it.get(k)
            if v and k == "after_path" and not os.path.exists(v):
                bad_fields.append(f"{it.get('slug')} 产物不存在：{v}")
    add("P1", "暂存清单完整（字段 + 产物文件）", items and not bad_fields,
        f"{len(items)} 国" + ("" if not bad_fields else f"；问题：{bad_fields[:3]}"))

    # P2 上线前 QC
    qc = rec.get("qc") or {}
    add("P2", "上线前 QC 全过", qc.get("passed") and not qc.get("failed"),
        f"passed={qc.get('passed')} · {qc.get('total')} 项 / 失败 {qc.get('failed')}")

    # P3 二次全文校验（暂存稿）
    se = rec.get("secondary") or {}
    add("P3", "二次校验 · 全文校验（暂存稿）全过",
        se.get("passed") and not se.get("failed") and se.get("source") == "staging",
        f"passed={se.get('passed')} · source={se.get('source')} · "
        f"{se.get('total')} 项 / 失败 {se.get('failed')}")

    # P4 通知已送达
    nt = rec.get("notify") or {}
    els = nt.get("elements") or []
    add("P4", "待上线通知已送达 Yoyo（含四要素）",
        nt.get("sent") and len(els) >= 4,
        f"sent={nt.get('sent')} · at={nt.get('at')} · 要素 {len(els)}/4"
        + ("" if nt.get("sent") else " —— 未送达不得上线"))

    # P5 暂存产物无漂移
    drift = []
    for it in items:
        ap, bp = it.get("after_path"), os.path.join(os.path.dirname(it.get("after_path") or ""),
                                                    "content_ORIGINAL.html")
        if ap and os.path.exists(ap):
            if L.sha16(open(ap, encoding="utf-8").read()) != it.get("content_sha"):
                drift.append(f"{it['slug']} 暂存稿被改动（sha 不符）")
        if os.path.exists(bp):
            if L.sha16(open(bp, encoding="utf-8").read()) != it.get("base_sha"):
                drift.append(f"{it['slug']} 基线被改动（sha 不符）")
    add("P5", "暂存产物与清单哈希一致（确认后未被偷改）", not drift,
        "全部一致" if not drift else "；".join(drift[:3]))

    # P6 未过期
    exp = rec.get("expires_at")
    try:
        exp_dt = datetime.datetime.strptime(exp, "%Y-%m-%d %H:%M")
        left = (exp_dt - datetime.datetime.now()).total_seconds() / 86400
        add("P6", "暂存未过期", left > 0, f"有效期至 {exp}（剩 {left:.1f} 天）")
    except Exception:
        add("P6", "暂存未过期", False, f"expires_at 不可解析：{exp!r}")

    # P7 人工确认凭据
    ready = [it["slug"] for it in items if it.get("secondary_ok")]
    approved = []
    if approve:
        approved = ready if approve.strip() == "all" else \
            [s.strip() for s in approve.split(",") if s.strip() in ready]
    add("P7", "人工确认凭据有效（--approve）", bool(approved),
        (f"已确认 {len(approved)}/{len(ready)} 国：{approved}" if approved
         else ("未提供 --approve（尚未有人确认上线）" if not approve
               else f"--approve={approve!r} 与可上线条目无交集，可上线={ready}")))
    return ck, dict(approved=approved, ready=ready, rec=rec, path=path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir", required=True)
    ap.add_argument("--approve", default=None,
                    help="人工确认凭据：all 或逗号分隔的 slug 列表")
    ap.add_argument("--json-out", default=None)
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    workdir = os.path.abspath(a.workdir)
    ck, extra = gate(workdir, a.approve)
    failed = [c for c in ck if not c["ok"]]
    passed = not failed

    if not a.quiet:
        print("=" * 78)
        print(f"发布确认门禁（P 组）　{datetime.datetime.now():%Y-%m-%d %H:%M:%S}")
        print("=" * 78)
        for c in ck:
            print(f" {'✅' if c['ok'] else '❌'} [{c['id']}] {c['name']}")
            print(f"       ↳ {c['detail']}")
        print("-" * 78)
        print(f"结论：{'✅ 允许上线' if passed else f'⛔ 阻断（{len(failed)} 项未过）—— 线上保持原样'}")
    rep = dict(generated_at=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
               workdir=workdir, passed=passed, checks_total=len(ck),
               checks_failed=len(failed), checks=ck,
               approved=(extra or {}).get("approved", []),
               ready=(extra or {}).get("ready", []))
    if a.json_out:
        json.dump(rep, open(a.json_out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
