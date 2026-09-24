#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
两阶段发布 · 阶段一「本地暂存 + 双校验 + 通知待确认」
=====================================================
Yoyo 定的发布纪律（2026-09-23）：
  **二次全文校验（内容质量 + 门禁）通过后，再正式上到线上。**
  **通过前先存本地**；通过后由助手把「哪篇国别指南 / 对应链接 / 全文校验结果 /
  待上线」推到 Yoyo，等人工确认，确认了才上线。

所以本脚本**只做三件事 + 一件事**，绝不碰 Strapi：
  1. 本地构建（调 batch_guide_patch.py，**不加 --apply**）→ 产物落 content_AFTER.html
  2. **一次校验**：上线前 QC 门禁（qc_gate.py，24 项，含**官方外链可打开** L5/L9）
  3. **二次校验**：全文校验 · 暂存稿（verify_secondary.py --source staging，S1–S14）
  4. 写暂存清单 `_release/pending_release.json` + 发「待上线确认」通知

⚠️ 三次校验的术语（Yoyo 2026-09-23 定，全流程统一）：
     一次校验 = 上线前 QC（本脚本 ②）        → 证明"我打算写的"合规
     二次校验 = 全文校验 · 暂存稿（本脚本 ③） → 证明"整篇正文"对
     三次校验 = 全文校验 · 上线后回读（阶段 C）→ 证明"平台真存下来的"对（台账口径）

顺序不能换：② 里含外链实时探测并落 `_link_check.json`，③ 用 `--link-mode cache` 复用它
——这样既保证"外链在落线前被验过"，又不会重复去打官方站（对官方站友好）。

用法：
  python3 release_stage.py --config ../references/batches/uae-v3.json \
      --workdir /path/to/_pilot_UAE
  python3 release_stage.py ... --no-notify      # 只暂存，不发通知
  python3 release_stage.py ... --force          # 校验未过也写清单（仅排障用，会把状态标红）

退出码：0 = 已暂存且两级校验全过（可进入人工确认）；1 = 校验未过（不可上线）。
"""
import argparse
import datetime
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import guide_patch_lib as L  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
CONF = json.load(open(os.path.join(HERE, "..", "references", "notify.json"), encoding="utf-8"))
TTL_DAYS = int(CONF.get("release_ttl_days", 7))


def run(tag, argv):
    print(f"\n{'-'*72}\n▶ {tag}\n{'-'*72}")
    p = subprocess.run([PY, *argv])
    return p.returncode


def stage_dir(workdir):
    d = os.path.join(workdir, "_release")
    os.makedirs(d, exist_ok=True)
    return d


def collect(cfg, workdir, qc, sec):
    """汇总待上线条目（全部取自暂存产物，不改一个字节）。"""
    sec_docs = (sec.get("docs") or {}) if isinstance(sec, dict) else {}
    ls = (qc.get("link_summary") or {}) if isinstance(qc, dict) else {}
    link = dict(total=ls.get("total"), ok=ls.get("ok"), dead=ls.get("dead"),
                manual=len(ls.get("manual_urls") or []), at=ls.get("at"))
    items = []
    for slug, cc in cfg["countries"].items():
        af = os.path.join(workdir, slug, "content_AFTER.html")
        pf = os.path.join(workdir, slug, "previewContent_AFTER.html")
        base = os.path.join(workdir, slug, "content_ORIGINAL.html")
        if not (os.path.exists(af) and os.path.exists(base)):
            items.append(dict(slug=slug, name=cc.get("name", slug), staged=False,
                              error="缺暂存产物（content_AFTER.html / content_ORIGINAL.html）"))
            continue
        content = open(af, encoding="utf-8").read()
        basec = open(base, encoding="utf-8").read()
        notes = cc["notes"]
        vc = L.version_counts(notes)
        doc = sec_docs.get(slug) or {}
        bad = [c for c in (doc.get("checks") or []) if not c.get("ok")]
        items.append(dict(
            slug=slug, name=cc.get("name", slug), documentId=cc["documentId"],
            guide_url=cc.get("guide_url") or L.guide_url(slug),
            notes=len(notes), pending=vc["n_pending"], check=vc["n_check"], keep=vc["n_keep"],
            n_effective=vc["n_eff"], n_scheduled=vc["n_sch"],
            titles=(doc.get("meta") or {}).get("titles"),
            body_version=L.version_bar_dates(dict(
                cc, batch=cfg.get("batch"), review_date=cfg.get("review_date")))["body_version"],
            content_sha=L.sha16(content), base_sha=L.sha16(basec),
            after_path=af, preview_path=pf,
            staging_len=len(content), base_len=len(basec),
            link=dict(link),                       # 外链可达性结论（来自一次校验 QC）
            secondary_ok=not bad, secondary_failed=[c["id"] for c in bad],
            status="待上线"))
    return items


def _n(d):
    """取校验项数 —— 报告里叫 checks_total，暂存清单里存成 total，两处都要认。"""
    d = d or {}
    return d.get("checks_total") or d.get("total") or "-"


def notify_body(cfg, workdir, items, qc, sec, expires, banner=None):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    good = [i for i in items if i.get("secondary_ok")]
    lines = [f"**📦 待上线确认 · 慧思国别指南更新标注（{cfg.get('batch')}）**", ""]
    if banner:
        lines += [f"> {banner}", ""]
    lines.append("⚠️ **尚未上线** —— 已本地暂存，等你确认后才正式发布。")
    lines.append("")
    for i in good:
        # 状态备注与页面版本条**同一口径**（文案一律取 L.EFF_TEXT，别在通知里另写一份）
        eff = f"{L.EFF_TEXT['effective']} {i['n_effective']}"
        if i["n_scheduled"]:
            eff += f" · {L.EFF_TEXT['scheduled']} {i['n_scheduled']}"
        bits = [f"⏳ 待更新 {i['pending']}（其中 {eff}）"]
        if i["check"]:
            bits.append(f"⚠️ 待核 {i['check']}")
        bits.append(f"{L.STATUS_TEXT['keep']} {i['keep']}")
        lk = i.get("link") or {}
        lines += [
            f"**① 国别指南**：{i['name']}（`{i['slug']}`）",
            f"**② 对应链接**：{i['guide_url']}",
            "**③ 全文校验**："
            f"✅ 通过（一次校验 · 上线前 QC {_n(qc)} 项全过"
            f" · 二次校验 · 全文校验 {_n(sec)} 项全过）",
            f"　　· 可渲染章节 {i.get('titles','-')}/{i.get('titles','-')}"
            f" ｜ 标注块 {i['notes']}/{i['notes']} ｜ 官方原文链接 {i['notes']}/{i['notes']}",
            f"　　· 官方外链可达：✅ 可打开 {lk.get('ok','-')} 条"
            + (f" ｜ ⚠️ 需人工点验 {lk.get('manual')} 条（本机不可达/站点反爬，"
               f"结论已记台账「外链状态」）" if lk.get("manual") else "")
            + f" ｜ ❌ 死链 {lk.get('dead', 0)} 条",
            f"　　· 状态备注：{' · '.join(bits)}",
            f"　　· 客户向文案：正文版本 **{i.get('body_version','-')}**（月粒度）；"
            f"页面不显示校验时间，也不显示「标注写入 / 校对ID」（只在台账留档）",
            f"**④ 当前状态**：本地产物已存盘（{i['staging_len']} 字符 · sha {i['content_sha']}）"
            f"　→ 上线后自动跑**三次校验**（线上回读）",
            "",
        ]
    for i in [x for x in items if not x.get("secondary_ok")]:
        lines += [f"❌ **{i['name']}** 二次校验未过：{'/'.join(i.get('secondary_failed') or [i.get('error','')])}", ""]
    lines += [
        "---",
        f"**请确认是否正式上线**（回一句就行）：",
        f"　· 「上线」→ 执行 `release_apply.py --workdir {workdir} --approve all`",
        "　· 「只上 X 国」→ 只放行对应 slug",
        "　· 「先不上」→ 保持本地暂存，不动线上",
        "",
        f"暂存有效期至 **{expires}**（过期需重跑 `release_stage.py`）。",
    ]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--workdir", required=True)
    ap.add_argument("--no-notify", action="store_true")
    ap.add_argument("--force", action="store_true",
                    help="校验未过也写暂存清单（排障/演练用；清单里 release_ready=false）")
    ap.add_argument("--notify-only", action="store_true",
                    help="不重建，仅对已有暂存清单重发通知（首次发送失败时用）")
    ap.add_argument("--banner", default=None,
                    help="通知正文顶部加一行说明（演练/通道测试时标注用途）")
    a = ap.parse_args()
    try:                      # 子进程输出与父进程输出保持先后顺序（管道下默认块缓冲会乱序）
        sys.stdout.reconfigure(line_buffering=True)
    except Exception:
        pass

    cfg = json.load(open(a.config, encoding="utf-8"))
    workdir = os.path.abspath(a.workdir)
    d = stage_dir(workdir)          # ← 必须先建目录：③ 的 --json-out 落在这里
    recp = os.path.join(d, "pending_release.json")

    # ── 仅重发通知 ─────────────────────────────────────────────────────────
    if a.notify_only:
        if not os.path.exists(recp):
            sys.exit(f"⛔ 无暂存清单 {recp} —— 先跑一次完整的 release_stage.py")
        rec = json.load(open(recp, encoding="utf-8"))
        qc = rec.get("qc") or {}
        sec = rec.get("secondary") or {}
        rc_n = _send(rec, cfg, workdir, recp, qc, sec, a.banner)
        return rc_n

    # ── 1) 本地构建（绝不加 --apply）──────────────────────────────────────────
    rc_build = run("① 本地构建（build + validate，不写线上）",
                   [os.path.join(HERE, "batch_guide_patch.py"),
                    "--config", a.config, "--workdir", workdir,
                    "--report", os.path.join(workdir, "_build_report.json")])

    # ── 2) 一次校验：上线前 QC 门禁（24 项；含官方外链可达 L5/L9）─────────────
    qc_json = os.path.join(workdir, "_qc_report.json")
    rc_qc = run("② 一次校验 · 上线前 QC 门禁（qc_gate.py · 24 项 · 含官方外链可达）",
                [os.path.join(HERE, "qc_gate.py"),
                 "--config", a.config, "--workdir", workdir,
                 "--json-out", qc_json, "--md-out", os.path.join(workdir, "_qc_report.md")])

    # ── 3) 二次校验：全文校验（落线前 · 暂存稿）────────────────────────────
    # --link-mode cache：复用 ② 刚落下的 _link_check.json（不重复探测官方站）
    sec_json = os.path.join(d, "_secondary_verify_staging.json")
    rc_sec = run("③ 二次校验 · 全文校验（暂存稿 · S1–S14）",
                 [os.path.join(HERE, "verify_secondary.py"),
                  "--config", a.config, "--workdir", workdir,
                  "--source", "staging", "--link-mode", "cache",
                  "--json-out", sec_json])

    qc = json.load(open(qc_json, encoding="utf-8")) if os.path.exists(qc_json) else {}
    sec = json.load(open(sec_json, encoding="utf-8")) if os.path.exists(sec_json) else {}
    all_ok = (rc_build == 0 and rc_qc == 0 and rc_sec == 0) and qc.get("passed") and sec.get("passed")

    # ── 4) 暂存清单 + 通知 ──────────────────────────────────────────────────
    now = datetime.datetime.now()
    expires = (now + datetime.timedelta(days=TTL_DAYS)).strftime("%Y-%m-%d %H:%M")
    items = collect(cfg, workdir, qc, sec)
    rec = dict(
        batch=cfg.get("batch"), config=os.path.abspath(a.config), workdir=workdir,
        staged_at=now.strftime("%Y-%m-%d %H:%M:%S"), expires_at=expires, ttl_days=TTL_DAYS,
        qc=dict(passed=bool(qc.get("passed")), total=qc.get("checks_total"),
                failed=qc.get("checks_failed")),
        secondary=dict(passed=bool(sec.get("passed")), total=sec.get("checks_total"),
                       failed=sec.get("checks_failed"), source="staging"),
        release_ready=bool(all_ok), notify=None, confirm=None, items=items,
        note="待上线清单（唯一凭据）。release_gate.py 读它做 P1–P7 门禁；release_apply.py 确认后据此上线。")
    json.dump(rec, open(recp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n📦 暂存清单 → {recp}")

    if not all_ok and not a.force:
        print(f"\n{'='*72}\n❌ 阶段一未通过：build={rc_build} qc={rc_qc} secondary={rc_sec}"
              f"　→ 不得上线（线上保持原样）")
        print("   清单已落盘（release_ready=false，门禁会拦），未发通知。")
        _link_todo(qc, d, a.config, workdir)
        print("   排障/演练可加 --force 强制写清单并出报告。")
        return 1

    if a.no_notify:
        print("\n[SKIP] --no-notify：未发通知（门禁 P4 会因此阻断上线）")
    else:
        _send(rec, cfg, workdir, recp, qc, sec, a.banner)

    print(f"\n{'='*72}")
    if all_ok:
        print("✅ 阶段一完成：已本地暂存 + 两级校验全过。**线上未被改动。**"
              + ("" if a.no_notify else "已通知待确认。"))
        if a.no_notify:
            print("   ⚠️ --no-notify：通知未发（P4 会阻断上线）。补发："
                  f"\n   python3 release_stage.py --config {a.config} --workdir {workdir} --notify-only")
        print("   下一步（等 Yoyo 确认后）：")
        print(f"   python3 release_apply.py --workdir {workdir} --approve all")
    else:
        print(f"⚠️ --force 演练：暂存清单已写但两级校验未全过（release_ready=false）"
              f"　→ 发布门禁 P2/P3 会阻断。")
    return 0 if all_ok else 1


def _link_todo(qc, stage_d, cfg_path, workdir):
    """阶段一失败时，把「需要人工点开的外链」写成可执行清单（只在这种情况下产生）。

    为什么单独做这件事：外链门禁（L9）的阻断**不是内容缺陷**，而是"机器给不出结论"——
    理由与分类见 scripts/link_check.py。若只丢一句 "not passed"，拿到手的人不知道该点哪两条，
    门禁就变成了"卡住"而不是"推进"。所以这里把 URL、点验命令、重跑命令一并打出来。
    """
    bad = [c for c in (qc.get("checks") or []) if (not c["ok"]) and c["blocking"]]
    pend = [c for c in bad if c["id"] == "L9"]
    others = [c for c in bad if c["id"] != "L9"]
    if others:
        print(f"\n⚠️ 另有 {len(others)} 项内容类阻断（需先修内容，不是点链接能解决的）：")
        for c in others:
            print(f"   · [{c['id']}] {c['name']}\n     {c['detail'][:300]}")
    if not pend:
        return
    rids = sorted({m for c in pend for m in re.findall(r"(PR-\d{8}-\d+)", c["detail"])})
    print(f"\n{'·'*72}")
    print("🔗 外链待人工点验（机器给不出结论：站点反爬 / 本机网络不可达）")
    print(f"{'·'*72}")
    for c in pend:
        for line in str(c["detail"]).splitlines():
            if line.strip().startswith("·"):
                print(f"   {line.strip()}")
    print("\n   请在**浏览器**里逐条打开确认能正常显示，然后二选一：")
    print(f"     · 能打开 → 留痕并重跑阶段一：")
    print(f"         python3 link_check.py --config {cfg_path} \\")
    print(f"             --mark-verified {','.join(rids)} --by Yoyo")
    print(f"         python3 release_stage.py --config {cfg_path} --workdir {workdir}")
    print(f"     · 打不开 → 必须换链接（改批次配置的 official_url 后重建）")
    md = os.path.join(stage_d, "_link_todo.md")
    with open(md, "w", encoding="utf-8") as f:
        f.write("# 外链待人工点验\n\n")
        f.write("> 机器探测给不出结论（本机不可达 / 站点反爬）。请在浏览器里逐条打开确认。\n")
        f.write("> 判据与分类见 `scripts/link_check.py` 文件头。**留痕只能由真人给**。\n\n")
        for c in pend:
            f.write(f"## [{c['id']}] {c['name']}\n\n```\n{c['detail']}\n```\n\n")
        f.write(f"## 留痕命令（确认能打开后执行）\n\n```bash\n"
                f"python3 link_check.py --config {cfg_path} "
                f"--mark-verified {','.join(rids)} --by Yoyo\n"
                f"python3 release_stage.py --config {cfg_path} --workdir {workdir}\n```\n")
    print(f"\n   清单 → {md}")


def _send(rec, cfg, workdir, recp, qc, sec, banner=None):
    """发「待上线确认」通知并回写清单的 notify 记录。返回 0/1。"""
    body = notify_body(cfg, workdir, rec["items"], qc, sec, rec["expires_at"], banner)
    d = os.path.dirname(recp)
    bf = os.path.join(d, "_notify_body.md")
    open(bf, "w", encoding="utf-8").write(body)
    nj = os.path.join(d, "_notify_result.json")
    rc_n = run("④ 通知 Yoyo（待上线确认）",
               [os.path.join(HERE, "notify_channels.py"),
                "--title", f"待上线确认 · {cfg.get('batch')}", "--body-file", bf,
                "--json-out", nj])
    sent = False
    if os.path.exists(nj):
        try:
            sent = bool(json.load(open(nj, encoding="utf-8")).get("sent"))
        except Exception:
            sent = False
    rec["notify"] = dict(sent=sent, at=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                         body_file=bf, result_json=nj, banner=banner,
                         elements=["国别指南名称", "对应链接", "全文校验结果", "待上线状态"])
    json.dump(rec, open(recp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"通知发送：{'✅ 已送达' if sent else '❌ 未送达（检查通道配置）'}")
    if not sent:
        print("⛔ 通知未送达 —— 人工确认门禁无法成立，不得上线。"
              "先跑 notify_channels.py --probe 看通道配置。")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
