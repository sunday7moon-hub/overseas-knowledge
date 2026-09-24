#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
发布确认门禁（P 组）负向测试 —— 「证明它真会拦」
================================================
Yoyo 的硬规矩：**门禁建完必须做负向测试**（故意破坏一遍、确认它真会拦，
退出码非 0），否则只是又一份清单。

以 `release_gate.gate()` 为单位测试（不碰 Strapi、不碰线上、不写飞书）。
每个用例构造一份 synthetic 暂存清单，断言「应该拦的那一项真的被拦」，
并断言「破坏项就是预期那一项、且没有误伤其他项」。

用法：python3 selftest_release_gate.py
退出码：0 = 全部用例符合预期；1 = 有用例不符（门禁有漏洞或误报）。
"""
import datetime
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import guide_patch_lib as L  # noqa: E402
import release_gate as G  # noqa: E402

SLUG = "test-country-guide"
AFTER = "<div class=\"nrz\"><h2 class=\"section-title\">A</h2></div>"
BASE = "<div class=\"nrz\"><h2 class=\"section-title\">A</h2></div>"


def make_case(root, *, ready=True, qc_ok=True, sec_ok=True, notified=True,
              drift_staging=False, drift_base=False, expires_delta_days=7,
              drop_field=False, source="staging", _no_elements=False):
    """造一份暂存清单 + 产物文件；返回 workdir。"""
    wd = os.path.join(root, SLUG[:8] + str(abs(hash((ready, qc_ok, sec_ok, notified,
                                                     drift_staging, expires_delta_days,
                                                     drop_field, source))) % 100000))
    d = os.path.join(wd, SLUG)
    os.makedirs(os.path.join(wd, "_release"), exist_ok=True)
    os.makedirs(d, exist_ok=True)
    af, bf = os.path.join(d, "content_AFTER.html"), os.path.join(d, "content_ORIGINAL.html")
    pf = os.path.join(d, "previewContent_AFTER.html")
    open(af, "w").write(AFTER)
    open(bf, "w").write(BASE)
    open(pf, "w").write("<p>x</p>")
    exp = (datetime.datetime.now() + datetime.timedelta(days=expires_delta_days)
           ).strftime("%Y-%m-%d %H:%M")
    item = dict(slug=SLUG, name="测试国", documentId="doc123",
                guide_url="https://www.humancehr.com/country-guide/x/国家概况",
                notes=1, pending=1, check=0, keep=0, n_effective=1, n_scheduled=0,
                titles=12, content_sha=L.sha16(AFTER), base_sha=L.sha16(BASE),
                after_path=af, preview_path=pf, staging_len=len(AFTER),
                base_len=len(BASE), secondary_ok=sec_ok, secondary_failed=[] if sec_ok else ["S1"],
                status="待上线")
    if drop_field:
        item.pop("documentId")
    rec = dict(batch="SELFTEST", config="x.json", workdir=wd,
               staged_at=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
               expires_at=exp, ttl_days=7,
               qc=dict(passed=qc_ok, total=18, failed=0 if qc_ok else 1),
               secondary=dict(passed=sec_ok, total=11, failed=0 if sec_ok else 1, source=source),
               release_ready=ready,
               notify=(dict(sent=notified, at="t",
                            elements=([] if _no_elements else
                                      ["国别指南名称", "对应链接", "全文校验结果", "待上线状态"]))
                       if notified is not None else None),
               items=[item])
    json.dump(rec, open(os.path.join(wd, "_release", "pending_release.json"), "w"),
              ensure_ascii=False, indent=1)
    if drift_staging:
        open(af, "w").write(AFTER + "<!-- 偷改 -->")
    if drift_base:
        open(bf, "w").write(BASE + "<!-- 偷改 -->")
    return wd


def verdict(wd, approve=None):
    ck, _ex = G.gate(wd, approve)
    return {c["id"]: c["ok"] for c in ck}


CASES = [
    # 无清单时**全项 fail-closed**（宁可不放行，也不靠"没数据"蒙过去）
    ("N1 无暂存清单（应全项 fail-closed）", dict(_no_manifest=True), None,
     ["P1", "P2", "P3", "P4", "P5", "P6", "P7"]),
    ("N2 上线前 QC 未过", dict(qc_ok=False), "all", ["P2"]),
    ("N3 二次全文校验未过", dict(sec_ok=False), "all", ["P3", "P7"]),   # 无可用条目 ⇒ 也无从确认
    ("N3b 校验来源不是 staging", dict(source="live"), "all", ["P3"]),
    ("N4 通知未送达", dict(notified=False), "all", ["P4"]),
    ("N4b 通知记录缺四要素", dict(_no_elements=True), "all", ["P4"]),
    ("N5 暂存稿被偷改", dict(drift_staging=True), "all", ["P5"]),
    ("N5b 基线被偷改", dict(drift_base=True), "all", ["P5"]),
    ("N6 暂存已过期", dict(expires_delta_days=-1), "all", ["P6"]),
    ("N7 无人工确认凭据", dict(), None, ["P7"]),
    ("N7b 确认凭据与条目无交集", dict(), "some-other-slug", ["P7"]),
    ("N8 清单字段缺失", dict(drop_field=True), "all", ["P1"]),
    ("N9 全绿 + 已确认（应放行）", dict(), "all", []),
]


def main():
    root = tempfile.mkdtemp(prefix="cg_selftest_")
    ok_all = True
    print("=" * 78)
    print("发布确认门禁（P 组）负向测试")
    print("=" * 78)
    try:
        for name, kw, approve, want_fail in CASES:
            if kw.pop("_no_manifest", False):
                wd = os.path.join(root, "empty")
                os.makedirs(os.path.join(wd, "_release"), exist_ok=True)
            else:
                wd = make_case(root, **kw)
            v = verdict(wd, approve)
            got_fail = sorted(k for k, ok in v.items() if not ok)
            good = got_fail == sorted(want_fail)
            ok_all &= good
            print(f" {'✅' if good else '❌'} {name}")
            print(f"      预期阻断 {sorted(want_fail) or '（无，应放行）'}"
                  f" ｜ 实际阻断 {got_fail or '（无）'}")
            if not good:
                print(f"      ↳ 不符：gate 全表 = {json.dumps(v, ensure_ascii=False)}")
    finally:
        shutil.rmtree(root, ignore_errors=True)
    print("-" * 78)
    print(f"结论：{'✅ 全部用例符合预期（门禁真会拦，且不误伤）' if ok_all else '❌ 存在不符用例'}"
          f"　共 {len(CASES)} 例")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
