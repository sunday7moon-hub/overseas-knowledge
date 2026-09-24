#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
两阶段发布 · 阶段二「人工确认后正式上线」
==========================================
**唯一**允许写线上的正式通道。执行顺序是刚性的：

  ① release_gate.py 的 P1–P7 全过（含人工确认凭据 --approve）
  ② 只把**已通过二次校验（落线前全文校验）的暂存稿**原样 PUT 上去（不再重新构建 —— 上线的必须
     是"被校验过的那一份"，而不是"再算一遍的那一份"）
  ③ 回读校验（L.push_and_verify）+ 回写台账（上架时间 / 上线状态）

用法：
  python3 release_apply.py --workdir /path/to/_pilot_UAE --approve all
  python3 release_apply.py --workdir ... --approve united-arab-emirates-country-guide
  python3 release_apply.py --workdir ... --dry-run        # 只跑门禁，不写线上
  # 阶段 C · 三次校验（必须跑，台账口径的"三次校验结果"在这里才写）：
  python3 verify_secondary.py --config <cfg> --workdir <wd> --sync-ledger
退出码：0 = 已上线（或 dry-run 门禁通过）；1 = 门禁未过/回查失败。
"""
import argparse
import datetime
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import guide_patch_lib as L  # noqa: E402
import ledger_client as LC  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
F = LC.F
APPROVER = "Yoyo"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir", required=True)
    ap.add_argument("--approve", required=True, help="人工确认凭据：all 或逗号分隔 slug")
    ap.add_argument("--dry-run", action="store_true", help="只跑门禁，不写线上")
    ap.add_argument("--no-ledger", action="store_true", help="不回写台账")
    a = ap.parse_args()
    try:                      # 子进程输出与父进程输出保持先后顺序（管道下默认块缓冲会乱序）
        sys.stdout.reconfigure(line_buffering=True)
    except Exception:
        pass

    workdir = os.path.abspath(a.workdir)
    pend_path = os.path.join(workdir, "_release", "pending_release.json")
    gate_json = os.path.join(workdir, "_release", "_release_gate.json")

    # ── ① 发布确认门禁（P1–P7）──────────────────────────────────────────────
    print(f"{'='*78}\n① 发布确认门禁（P1–P7）\n{'='*78}")
    rc = subprocess.run([sys.executable, os.path.join(HERE, "release_gate.py"),
                         "--workdir", workdir, "--approve", a.approve,
                         "--json-out", gate_json]).returncode
    if rc != 0:
        sys.exit("⛔ 发布确认门禁未过 —— 拒绝上线（线上保持原样）。")
    rec = json.load(open(pend_path, encoding="utf-8"))
    approved = (json.load(open(gate_json, encoding="utf-8")) or {}).get("approved") or []
    if not approved:
        sys.exit("⛔ 无可上线条目。")

    print(f"\n已确认上线：{approved}")
    if a.dry_run:
        print("（--dry-run：只跑门禁，未写线上）")
        return 0

    # ── ② 原样上线（用暂存稿，不重新构建）──────────────────────────────────
    print(f"\n{'='*78}\n② 正式上线（写 Strapi，仅 content / previewContent）\n{'='*78}")
    results, all_ok = [], True
    for it in rec["items"]:
        if it["slug"] not in approved:
            continue
        content = open(it["after_path"], encoding="utf-8").read()
        preview = open(it["preview_path"], encoding="utf-8").read() \
            if os.path.exists(it["preview_path"]) else ""
        if L.sha16(content) != it["content_sha"]:
            all_ok = False
            print(f"❌ {it['slug']} 暂存稿哈希已变（门禁 P5 与本步之间被改动）——跳过")
            continue
        r = L.push_and_verify(it["documentId"], content, preview)
        r.update(slug=it["slug"], name=it["name"], at=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        results.append(r)
        all_ok &= bool(r["content_verified"])
        print(f"{'✅' if r['content_verified'] else '❌'} {it['name']:8} PUT={r['put_status']} "
              f"回查 {r['content_verify_msg']}（线上 {r['remote_len']} 字符 · sha {r['remote_sha']}）")

    # ── ③ 台账回写（上架时间 / 上线状态 / 确认人时间）───────────────────────
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if not a.no_ledger:
        for it in rec["items"]:
            if it["slug"] not in approved:
                continue
            done = next((r for r in results if r["slug"] == it["slug"] and r["content_verified"]), None)
            if not done:
                continue
            cfg = json.load(open(rec["config"], encoding="utf-8"))
            rids = [n["rid"] for n in cfg["countries"][it["slug"]]["notes"]]
            ok, resp = LC.update_by_rid(rids, {
                F["release_status"]: "已上线",
                F["release_confirm_by"]: APPROVER,
                F["release_confirm_at"]: now,
                F["live_at"]: now,
                F["status"]: "已回写",
            })
            print(f"   台账 {it['slug']}：{'✅ ' + str(resp) if ok else '❌ ' + str(resp)[:200]}")

    # ── 记录 ────────────────────────────────────────────────────────────────
    rec["confirm"] = dict(by=APPROVER, at=now, approve=a.approve, approved=approved)
    rec["applied"] = results
    rec["release_ready"] = False           # 已消费
    for it in rec["items"]:
        if it["slug"] in approved and any(r["slug"] == it["slug"] and r["content_verified"]
                                         for r in results):
            it["status"] = "已上线"
    json.dump(rec, open(pend_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print(f"\n{'='*78}")
    if all_ok:
        vs = os.path.join(HERE, "verify_secondary.py")
        print("✅ 已上线。下一步**必须**跑**三次校验**（阶段 C · 线上回读；"
              "台账口径的「三次校验结果」在此写）：")
        print(f"   python3 {vs} --config {rec['config']} --workdir {workdir} --sync-ledger")
    else:
        print("❌ 存在回查失败项 —— 请立即用 content_ORIGINAL.html 回滚并排查。")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
