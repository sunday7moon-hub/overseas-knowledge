#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
慧思国别指南「更新标注」批量执行器
====================================
读批次配置 → 逐国构建标注 → 门禁校验 → （可选）写 Strapi。

用法：
  # 1) 本地试跑（默认，绝不碰线上）：生成 AFTER + 校验 + 报告
  python3 batch_guide_patch.py --config ../references/batches/b2-01-t.json \
          --workdir /path/to/_test_build/B2-01-T

  # 2) 正式落标（需显式 --apply，且配置 mode 必须是 production-ready）
  python3 batch_guide_patch.py --config ... --workdir ... --apply

  ⚠️ 2026-09-23 起**正式落线走两阶段发布**（Yoyo 定）：
     ① python3 release_stage.py  --config ... --workdir ...   # 本地暂存 + 上线前 QC + 二次全文校验 + 通知待确认
     ② python3 release_apply.py  --workdir ... --approve all  # 人工确认后上线（前置 P 组 7 项门禁）
     本脚本的 --apply 保留为**应急/回滚通道**，需显式加 --legacy，防止绕过人工确认门禁。

  # 3) 单国回滚
  python3 batch_guide_patch.py --config ... --workdir ... --restore --only germany-country-guide

  # 4) 重新拉线上基線（默认复用已有 ORIGINAL，不覆盖）
  python3 batch_guide_patch.py --config ... --workdir ... --refresh

设计约束（硬）：
  1. ORIGINAL 首次落盘后永不覆盖（--refresh 除外，且会另存 .prev 备份）
  2. 默认 local-only：不加 --apply 绝不发 PUT
  3. 只 PUT content / previewContent 两个字段
  4. 每国必须过 validate + residual_check（证明只增不改）
  5. **落线前必须过 qc_gate.py（上线前 QC：文本 + 官方链接），未过则整批拒绝写入**
     流程固定为「先构建全部国家 → 跑一次 QC → 通过才逐国 PUT」，
     避免 QC 不通过时出现「一半写了一半没写」的脏状态。
  6. 落标后按 documentId 回查 + sha256，返回 200 ≠ 成功
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import guide_patch_lib as L  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


def load_config(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def sha(t):
    return L.sha16(t)   # 唯一实现在库里（release_apply.py 用同一个）


def fetch(doc):
    s, d = L.strapi_call("GET", f"/api/articles/{doc}?populate=*")
    if not isinstance(d, dict) or "data" not in d:
        sys.exit(f"❌ 拉取失败 {s}: {str(d)[:200]}")
    return d["data"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.join(HERE, "..", "references", "batches", "b2-01-t.json"))
    ap.add_argument("--workdir", required=True)
    ap.add_argument("--report", default=None)
    ap.add_argument("--apply", action="store_true", help="真的写 Strapi（默认不写）")
    ap.add_argument("--legacy", action="store_true",
                    help="绕过两阶段发布人工确认门禁（应急/回滚专用，需写明原因）")
    ap.add_argument("--restore", action="store_true")
    ap.add_argument("--refresh", action="store_true", help="重新拉线上作为基线（旧 ORIGINAL 转存 .prev）")
    ap.add_argument("--only", default=None, help="只跑某个 slug")
    a = ap.parse_args()

    cfg = load_config(a.config)
    batch = cfg["batch"]
    # 配置级门禁：只有显式声明 production-ready 的配置才允许 --apply（防止误落未验收批次）
    if a.apply and cfg.get("mode") != "production-ready":
        sys.exit(f"⛔ 拒绝写入：配置 mode={cfg.get('mode')!r}，不是 'production-ready'。\n"
                 f"   {a.config}\n"
                 f"   若确认要落线上，请先在该配置里把 mode 改为 production-ready。")
    # 流程级门禁（2026-09-23 新增）：正式落线必须走两阶段发布 + 人工确认，
    # 本脚本的 --apply 只作应急通道 —— 必须显式 --legacy，避免"顺手 --apply"绕过确认门禁。
    if a.apply and not a.legacy:
        sys.exit(
            "⛔ 落线路径已改为「两阶段发布 + 人工确认」（2026-09-23）——拒绝直接 --apply。\n"
            "   ① 暂存+双校验+通知：python3 release_stage.py  --config <cfg> --workdir <wd>\n"
            "   ② 确认后上线：      python3 release_apply.py  --workdir <wd> --approve all\n"
            "   （release_apply 会先跑 release_gate.py 的 P1–P7 门禁）\n"
            "   应急/回滚确需绕过：加 --legacy 并注明原因。")
    workdir = os.path.abspath(a.workdir)
    os.makedirs(workdir, exist_ok=True)
    only = set(a.only.split(",")) if a.only else None

    rows, all_ok = [], True
    pending = []   # 待落线：(slug, cc, after, pafter, rows 下标) —— QC 通过后才真正 PUT
    for slug, cc in cfg["countries"].items():
        if only and slug not in only:
            continue
        d = os.path.join(workdir, slug)
        os.makedirs(d, exist_ok=True)
        f_orig = os.path.join(d, "content_ORIGINAL.html")
        f_porig = os.path.join(d, "previewContent_ORIGINAL.html")

        if a.refresh or not os.path.exists(f_orig):
            it = fetch(cc["documentId"])
            if os.path.exists(f_orig) and a.refresh:
                os.replace(f_orig, f_orig + ".prev")
                os.replace(f_porig, f_porig + ".prev")
            open(f_orig, "w", encoding="utf-8").write(it["content"])
            open(f_porig, "w", encoding="utf-8").write(it.get("previewContent") or "")
            print(f"  📌 基线已拉取 → {slug}  ({len(it['content'])} 字符)")
        before = open(f_orig, encoding="utf-8").read()
        pbefore = open(f_porig, encoding="utf-8").read()

        if a.restore:
            s, _ = L.strapi_call("PUT", f"/api/articles/{cc['documentId']}",
                                 body={"data": {"content": before, "previewContent": pbefore}})
            _, dd = L.strapi_call("GET", f"/api/articles/{cc['documentId']}?populate=*")
            now = dd["data"]["content"] if isinstance(dd, dict) else ""
            print(f"{cc['name']}: 回滚 PUT={s} {'✅ 已回滚' if now == before else '⚠️ 不一致'}")
            continue

        ccfg = dict(cc)
        ccfg["batch"] = batch
        ccfg["page_date"] = cc["page_date"]
        ccfg["review_date"] = cfg.get("review_date", "2026-09-07")
        # slug 是「申报式正文修复」的匹配键（references/body-fixes.json 按 slug 精确匹配）
        ccfg["slug"] = slug
        try:
            after, pafter, report, inserted = L.build(before, pbefore, ccfg)
        except AssertionError as e:
            print(f"❌ {cc['name']} 构建失败: {e}")
            rows.append(dict(slug=slug, name=cc["name"], ok=False, error=str(e)))
            all_ok = False
            continue

        errs = L.validate(before, after, ccfg, inserted)
        ok = not errs
        all_ok &= ok

        open(os.path.join(d, "content_AFTER.html"), "w", encoding="utf-8").write(after)
        open(os.path.join(d, "previewContent_AFTER.html"), "w", encoding="utf-8").write(pafter)

        applied = None
        note_stat = {}
        for n in ccfg["notes"]:
            note_stat[n["status"]] = note_stat.get(n["status"], 0) + 1
        rows.append(dict(slug=slug, name=cc["name"], documentId=cc["documentId"],
                         ok=ok, errors=errs, notes=len(ccfg["notes"]), by_status=note_stat,
                         len_before=len(before), len_after=len(after),
                         sha_before=sha(before), sha_after=sha(after),
                         applied=applied, report=report))
        if ok and a.apply:
            pending.append((slug, cc, after, pafter, len(rows) - 1))
        print(f"{'✅' if ok else '❌'} {cc['name']:6} {slug[:36]:36} "
              f"标注{len(ccfg['notes']):2}  {len(before):6}→{len(after):6}  "
              f"{'全部通过' if ok else '; '.join(errs)[:120]}")

    # ── 上线前 QC 门禁（唯一闸门）：构建 → QC → 通过才写线上 ────────────────────
    if a.apply:
        if not all_ok:
            print("\n⛔ 构建阶段未全通过 —— 拒绝落线（线上保持原样）。")
            _write_report(a, cfg, batch, workdir, rows, False)
            return 1
        print(f"\n{'-'*70}\n上线前 QC 门禁 → qc_gate.py\n{'-'*70}")
        qc = subprocess.run([sys.executable, os.path.join(HERE, "qc_gate.py"),
                             "--config", a.config, "--workdir", workdir,
                             "--json-out", os.path.join(workdir, "_qc_report.json"),
                             "--md-out", os.path.join(workdir, "_qc_report.md")])
        if qc.returncode != 0:
            print("\n⛔ QC 门禁未通过 —— 拒绝落线（线上保持原样）。")
            _write_report(a, cfg, batch, workdir, rows, False)
            return 1
        print("\n✅ QC 通过，开始落线：")

        for slug, cc, after, pafter, idx in pending:
            # 写线上 + 回查：唯一实现已抽到库里（release_apply.py 走同一条路径）
            r = L.push_and_verify(cc["documentId"], after, pafter)
            rows[idx]["applied"] = r
            v_ok, v_msg = r["content_verified"], r["content_verify_msg"]
            p_clean, p_frag = r["preview_truncation_clean"], r["preview_cut_fragment"]
            if not v_ok:
                all_ok = False
                print(f"   ⚠️ {cc['name']} 回查不一致：{v_msg}")
            print(f"   ↳ {cc['name']} 回查 content: {'✅ ' + v_msg if v_ok else '❌ ' + v_msg}")
            print(f"   ↳ {cc['name']} 回查 preview: 平台派生 {r['preview_len']} 字符，截断点"
                  f"{'干净' if p_clean else '❌ 落在标签中间'} → {p_frag!r}")

    _write_report(a, cfg, batch, workdir, rows, all_ok)
    return 0 if all_ok else 1


def _write_report(a, cfg, batch, workdir, rows, all_ok):
    rep = dict(batch=batch, mode=("APPLY" if a.apply else "LOCAL-ONLY"),
               applied=bool(a.apply), generated_at=L.TODAY,
               config=a.config, workdir=workdir, all_ok=all_ok, countries=rows)
    outp = a.report or os.path.join(workdir, "_build_report.json")
    json.dump(rep, open(outp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n{'-'*70}\n报告 → {outp}")
    print(f"总体：{'✅ 全部通过' if all_ok else '❌ 有失败项'}　模式：{rep['mode']}")
    if not a.apply:
        print("（未写 Strapi —— 加 --apply 才会落线上）")


if __name__ == "__main__":
    sys.exit(main())
