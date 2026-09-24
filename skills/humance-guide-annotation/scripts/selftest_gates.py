#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
上线前门禁「负向测试」——证明门禁真的会拦，而不只是写在文档里
================================================================
纪律来源（Yoyo 定）：**清单 ≠ 门禁**；门禁建完必须故意破坏一遍、确认退出码非 0。
本脚本就是那道"故意破坏"的工序，把每一组门禁（R / E / F / L / T / G）各破坏一次。

两类破坏手法：
  A. **产物篡改型**：保持配置不动，改 content_AFTER.html 里的产物（模拟手写稿回流 /
     旧稿 / 平台改写），验证「产物自洽性」类门禁（R1 / E2 / F1 / F2 / F3 / **F4**）会拦。
  B. **配置注入型**：改批次配置后重新构建（走的还是正常渲染路径），
     验证「配置级」门禁（L1 / L2 / G1）会拦。
  C. **外链夹具型**（2026-09-23 新增）：篡改 `_link_check.json` 的探测结论
     （死链 / 不可达），验证 L5（死链阻断）与 L9（非可打开须人工点验）会拦。
     用夹具而不是真去探测 **是为了确定性** —— 否则用例结果会随网络抖动而变。

结尾做两级**反向验证**（缺一不可，否则「全拦」没有意义 —— 一个永远拦的门禁等于没有门禁）：
  C1 夹具放行：给「待人工点验」的外链补上点验留痕 → 必须退出码 0
     （证明门禁不是无脑拦，条件满足时真的会放行）
  C2 真实验收：真实配置原样跑 → 阻断项**只允许**来自 L9（待人工点验），
     不得有其它误拦（证明除"等你点一下"之外没有别的假阳性）

用法：python3 selftest_gates.py [--workdir <真实产物目录>] [--config <真实批次配置>]
退出码：0 = 全部符合预期；1 = 有漏放/误拦。
"""
import argparse
import copy
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import link_check as LC            # noqa: E402  分类器单测要用（唯一实现，不另抄一份）
import guide_patch_lib as L        # noqa: E402  F11 要锁配色/文案常量（口径的唯一真相源）
PY = sys.executable
DEF_CFG = os.path.join(HERE, "..", "references", "batches", "uae-v3.json")
DEF_WD = "/Users/yoyo/WorkBuddy/2026-09-21-15-18-04/outputs/国别指南更新/_pilot_UAE"


def run_qc(cfg_path, workdir, expect_rc=None):
    """跑 qc_gate → (退出码, 阻断项 id 列表, 明细)。

    ⚠️ 固定 `--link-mode cache`：外链探测**只读既有 _link_check.json**，
    不联网。否则用例结果会随网络抖动而变（本机是 MITM 代理，同一 URL 两次结论都可能不同）。
    """
    jp = os.path.join(workdir, "_qc_selftest.json")
    r = subprocess.run([PY, os.path.join(HERE, "qc_gate.py"),
                        "--config", cfg_path, "--workdir", workdir,
                        "--link-mode", "cache", "--json-out", jp],
                       capture_output=True, text=True)
    bad, detail = [], ""
    if os.path.exists(jp):
        rep = json.load(open(jp, encoding="utf-8"))
        bad = [c["id"] for c in rep["checks"] if not c["ok"] and c["blocking"]]
        detail = "；".join(f"{c['id']} {c['name']}" for c in rep["checks"]
                          if not c["ok"] and c["blocking"])[:200]
    return r.returncode, bad, detail


def load_cache(path):
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:
        return None


def case_link(label, work, cfg_path, mutate_cache, expect, expect_rc=1):
    """C 类：篡改 `_link_check.json` 的探测结论 → 跑 QC。"""
    cp = os.path.join(work, "_link_check.json")
    orig = load_cache(cp)
    if not orig:
        print(f"  ⚠️ 跳过  {label}（缺 {cp} —— 先跑一次 qc_gate.py --link-mode live）")
        return False
    try:
        json.dump(mutate_cache(copy.deepcopy(orig)), open(cp, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        rc, bad, detail = run_qc(cfg_path, work)
    finally:
        json.dump(orig, open(cp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    hit = [e for e in expect if e in bad]
    ok = len(hit) == len(expect) and ((rc != 0) if expect_rc else (rc == 0))
    print(f"  {'✅ 拦住' if ok else '❌ 漏放'}  {label}")
    print(f"        退出码={rc}  期望命中={expect}  实际阻断={bad}")
    if not ok:
        print(f"        ↳ {detail}")
    return ok


def case_product(workdir, cfg, label, mutate, expect):
    """A 类：篡改产物后跑 QC。

    ⚠️ 这里**必须**自查「篡改真的生效了吗」（2026-09-23 踩坑）：
    用例的锚点是产物里的**字面量**，产物文案一改（如版本条去掉「校对批次」），
    `str.replace` 就**静默变成空操作** —— 产物没被破坏 ⇒ 门禁当然不拦 ⇒ 用例报"漏放"。
    而更危险的是反过来：**若某条用例的期望是「不拦」，空操作会变成假通过**
    （测试绿着，实际什么都没测）。
    ⇒ 篡改前后字符串相同 = 用例本身失效，直接判失败并写明原因，绝不当作通过。
    """
    slug = list(cfg["countries"].keys())[0]
    fp = os.path.join(workdir, slug, "content_AFTER.html")
    orig = open(fp, encoding="utf-8").read()
    broken = mutate(orig)
    if broken == orig:
        print(f"  ❌ 失效  {label}")
        print("        ↳ 篡改未生效（锚点已不在产物里）—— 用例要修锚点，"
              "否则它测的不是门禁，而是空气")
        return False
    try:
        open(fp, "w", encoding="utf-8").write(broken)
        rc, bad, detail = run_qc(os.path.join(workdir, "_cfg.json"), workdir)
    finally:
        open(fp, "w", encoding="utf-8").write(orig)
    hit = [e for e in expect if e in bad]
    ok = rc != 0 and len(hit) == len(expect)
    print(f"  {'✅ 拦住' if ok else '❌ 漏放'}  {label}")
    print(f"        退出码={rc}  期望命中={expect}  实际阻断={bad}")
    if not ok:
        print(f"        ↳ {detail}")
    return ok


def case_config(label, cfg, mutate, expect, tmp):
    """B 类：改配置 → 重新构建 → 跑 QC。"""
    d = copy.deepcopy(cfg)
    mutate(d)
    d["batch"] = "SELFTEST-" + label.split()[0]
    cp = os.path.join(tmp, "cfg.json")
    json.dump(d, open(cp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    wd = os.path.join(tmp, "wd")
    os.makedirs(wd, exist_ok=True)
    # 预置基线，避免构建时联网
    src_slug = list(cfg["countries"].keys())[0]
    sd = os.path.join(DEF_WD, src_slug)
    dd = os.path.join(wd, src_slug)
    os.makedirs(dd, exist_ok=True)
    for f in ("content_ORIGINAL.html", "previewContent_ORIGINAL.html"):
        shutil.copy(os.path.join(sd, f), os.path.join(dd, f))
    subprocess.run([PY, os.path.join(HERE, "batch_guide_patch.py"),
                    "--config", cp, "--workdir", wd], capture_output=True, text=True)
    rc, bad, detail = run_qc(cp, wd)
    hit = [e for e in expect if e in bad]
    ok = rc != 0 and len(hit) == len(expect)
    print(f"  {'✅ 拦住' if ok else '❌ 漏放'}  {label}")
    print(f"        退出码={rc}  期望命中={expect}  实际阻断={bad}")
    if not ok:
        print(f"        ↳ {detail}")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=DEF_CFG)
    ap.add_argument("--workdir", default=DEF_WD)
    ap.add_argument("--json-out", default=None)
    a = ap.parse_args()

    cfg = json.load(open(a.config, encoding="utf-8"))
    results = []

    # 准备一个「真实产物」的临时副本（A 类在副本上篡改，绝不碰真实产物）
    tmp = tempfile.mkdtemp(prefix="cggate_")
    slug = list(cfg["countries"].keys())[0]
    for dirpath, dns, fns in os.walk(os.path.join(a.workdir, slug)):
        rel = os.path.relpath(dirpath, a.workdir)
        os.makedirs(os.path.join(tmp, "work", rel), exist_ok=True)
        for fn in fns:
            shutil.copy(os.path.join(dirpath, fn), os.path.join(tmp, "work", rel, fn))
    work = os.path.join(tmp, "work")
    shutil.copy(a.config, os.path.join(work, "_cfg.json"))
    # 外链缓存也要带过来（qc_gate 在 selftest 里固定 --link-mode cache 读它）
    lc_src = os.path.join(a.workdir, "_link_check.json")
    if os.path.exists(lc_src):
        shutil.copy(lc_src, os.path.join(work, "_link_check.json"))
    has_cache = os.path.exists(os.path.join(work, "_link_check.json"))

    print("=" * 74)
    print("上线前门禁 · 负向测试（期望：全部拦住）")
    print("=" * 74)
    print(f"外链缓存：{'已载入（L5/L9 用夹具验证，确定性）' if has_cache else '⚠️ 缺失'}")

    print("\nA. 产物篡改型（配置不动，改 content_AFTER.html）")
    # N1 前端脆弱 walker：注入 `</div><` 危险邻接（复刻 2026-09-23 线上事故形态）
    results.append(case_product(
        work, cfg, "N1 注入物内出现 `</div><` 危险邻接（前端 walker 会跳标签）",
        lambda s: s.replace('<div class="cg-update-note"',
                            '</div><div class="cg-update-note"', 1),
        ["R1"]))
    # N2 旧内部口径回流
    results.append(case_product(
        work, cfg, "N2 状态文案回流旧内部口径「法规已生效」",
        lambda s: s.replace("已正式生效", "法规已生效", 1),
        ["F3"]))
    # N3 「正文版本」写成具体日
    results.append(case_product(
        work, cfg, "N3 版本条「正文版本」写成具体日（2026-09-07）",
        lambda s: s.replace("正文版本：<strong>2026-09</strong>",
                            "正文版本：<strong>2026-09-07</strong>", 1),
        ["F1"]))
    # N4 页面出现内部过程时间
    #   ⚠️ 锚点曾用「校对批次 B2-01-T-migrate」—— 2026-09-23 该字段撤出页面后，
    #      replace 静默失效、用例变成空操作（已被 case_product 的自检抓住）。
    #      现改用版本条里结构稳定的「本次标注：」，与具体文案解耦。
    results.append(case_product(
        work, cfg, "N4 版本条出现内部过程时间字段「校验时间」",
        lambda s: s.replace("本次标注：<strong>",
                            "校验时间 2026-09-07 ｜ 本次标注：<strong>", 1),
        ["F2"]))
    # N5 生效状态属性被写错（手写稿漂移的原始形态）
    results.append(case_product(
        work, cfg, "N5 data-cg-eff 与按生效日重算不符（生效态判错）",
        lambda s: s.replace('data-cg-eff="effective"', 'data-cg-eff="scheduled"', 1),
        ["E2"]))
    # N6 内部过程字段回流页面（2026-09-23 新增：标注写入 / 校对ID 只记台账）
    results.append(case_product(
        work, cfg, "N6 页面回流内部过程字段「标注写入：」与「校对ID」",
        lambda s: s.replace("</p>\n</div>",
                            f'<p style="color:#a1a1aa;">标注写入：2026-09-23 ｜ 校对ID '
                            f'PR-20260907-046</p>\n</p>\n</div>', 1),
        ["F4"]))
    # N12 「官方原文 ↗」href 指向被换（数量不变，只有指向变了）★ 2026-09-23 新增
    #   这是"只数条数"拦不住、而客户点开才发现的那类错：链接数量一模一样。
    #   换成**同域名**的另一页 ⇒ L2/L3 都不拦（仍是官方），唯独 L4 的指向比对能抓。
    results.append(case_product(
        work, cfg, "N12 「官方原文 ↗」href 指向被换（数量相同、同域）→ L4 拦",
        lambda s: s.replace("mohre.gov.ae/assets/download", "mohre.gov.ae/en/media-center", 1),
        ["L4"]))
    # N13 旧状态文案回流（Yoyo 2026-09-23 反馈「读着别扭」的那版，已从常量里删掉）
    #   考的是「常量改了，旧稿还能不能上页面」—— 必须不能（产物是长期存在物，旧稿会回流）。
    results.append(case_product(
        work, cfg, "N13 旧状态文案「✅ 已核实维持」回流页面 → F3 拦",
        lambda s: s.replace("✅ 无需更新", "✅ 已核实维持", 1),
        ["F3"]))
    # N14 内部字段回流：版本条尾部的「校对批次」（2026-09-23 三轮，Yoyo 截图红框圈出）★
    #   它与「标注写入 / 校对ID / 页面位置」同类 —— 生产工单号，客户无从理解，
    #   `-migrate` 后缀更像"半成品"。已从 render_version_bar() 里删掉，这里证明**删干净了**：
    #   任何人把这段塞回产物，三处门禁（qc/validate 的 F4 + verify 的 S13）都必须拦。
    results.append(case_product(
        work, cfg, "N14 版本条回流内部字段「校对批次 B2-01-T-migrate」→ F4 拦",
        lambda s: s.replace("本次标注：<strong>",
                            "校对批次 B2-01-T-migrate ｜ 本次标注：<strong>", 1),
        ["F4"]))
    # N15 / N16 红色档回流（2026-09-23 四轮：「红色 存疑 先不在前端展示」）★
    #   红色 = 来源存疑，整条不该在页面上。**两个入口都要堵**：
    #     ① 标注块的 data-cg-tone   ② 该章 h2 徽标的 data-cg-tone
    #   只堵一个的话，另一处照样会把红色露出来（而且比不标更糟：客户看到红色却
    #   找不到对应的标注块）。判定唯一入口 = L.on_page()，这里证明**产物侧复核**真的会拦。
    results.append(case_product(
        work, cfg, "N15 标注块被手工改成红色档 verify → F5 拦",
        lambda s: s.replace(
            'data-cg-rid="PR-20260907-047" data-cg-status="pending" data-cg-tone="in_force"',
            'data-cg-rid="PR-20260907-047" data-cg-status="pending" data-cg-tone="verify"', 1),
        ["F5"]))
    results.append(case_product(
        work, cfg, "N16 章节徽标被手工改成红色档 verify → F5 拦",
        lambda s: s.replace('data-cg-state="pending" data-cg-tone="in_force"',
                            'data-cg-state="pending" data-cg-tone="verify"', 1),
        ["F5"]))

    print("\nB. 配置注入型（改配置 → 重新构建 → 跑 QC）")
    ctmp = os.path.join(tmp, "cfgcase")
    os.makedirs(ctmp, exist_ok=True)
    results.append(case_config(
        "N7 官方链接被换成三方律所链接", cfg,
        lambda d: d["countries"][slug]["notes"][0].__setitem__(
            "official_url", "https://www.morganlewis.com/pubs/2026/05/uae-x"),
        ["L2"], ctmp))
    results.append(case_config(
        "N8 某条没配官方原文链接", cfg,
        lambda d: d["countries"][slug]["notes"][2].__setitem__("official_url", ""),
        ["L1"], ctmp))
    results.append(case_config(
        "N9 配置 mode 不是 production-ready", cfg,
        lambda d: d.__setitem__("mode", "draft"),
        ["G1"], ctmp))

    print("\nC. 外链夹具型（篡改 _link_check.json 的探测结论；不联网，结论确定）")
    # N10 死链 → L5 必须阻断（这是"官方外链能不能打开"这条口径的底线）
    def _to_dead(c):
        r = c["results"][0]
        r.update(cls="dead", label="❌ 死链", code=404,
                 samples=["dead:HTTP 404", "dead:HTTP 404"])
        c["summary"]["dead"] = c["summary"].get("dead", 0) + 1
        return c
    results.append(case_link(
        "N10 官方外链探测为死链（404）→ L5 阻断落线", work,
        os.path.join(work, "_cfg.json"), _to_dead, ["L5"]))

    # N11 非 ok 且**没有**人工点验留痕 → L9 必须阻断（机器给不出结论也要有人负责）
    def _to_unreachable(c):
        for r in c["results"]:
            r.update(cls="unreachable", label="⚠️ 需人工点验（本机不可达）",
                     code=None, samples=["unreachable:URLError: timeout"])
        return c
    results.append(case_link(
        "N11 官方外链全部不可达且无人工点验留痕 → L9 阻断", work,
        os.path.join(work, "_cfg.json"), _to_unreachable, ["L9"]))

    print("\nD. 反向验证（缺一不可）")
    # D1 夹具放行：给"待人工点验"的外链补上点验留痕 → 必须放行。
    #    ⚠️ 这是**测试夹具**，只存在于临时目录；真实批次配置一个字节都不动，
    #    也不代表任何链接真的被验证过（留痕是"有人点开过"的凭据，只能由人给）。
    d1_ok = False
    if has_cache:
        fix = copy.deepcopy(cfg)
        n_mark = 0
        for _s, cc in fix["countries"].items():
            for x in cc["notes"]:
                if x.get("link_verified") is None:
                    x["link_verified"] = dict(result="ok", by="SELFTEST-FIXTURE",
                                              at="2026-09-23", note="负向测试夹具，非真实点验")
                    n_mark += 1
        fp = os.path.join(tmp, "cfg_fixture.json")
        json.dump(fix, open(fp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        rc, bad, detail = run_qc(fp, a.workdir)
        d1_ok = rc == 0 and not bad
        print(f"  {'✅ 放行' if d1_ok else '❌ 误拦'}  D1 夹具放行"
              f"（补 {n_mark} 条点验留痕的**测试夹具**）退出码={rc}"
              f"{'' if d1_ok else f'  阻断={bad}'}")
    else:
        print("  ⚠️ 跳过  D1 夹具放行（缺 _link_check.json）")
    results.append(d1_ok)

    # D2 真实验收：真实配置原样跑 → 阻断项**只允许**来自 L9（等你点开那两条链接）。
    #    若出现别的阻断，说明门禁有假阳性（误拦），必须修。
    rc, bad, detail = run_qc(a.config, a.workdir)
    d2_ok = set(bad) <= {"L9"}
    print(f"  {'✅ 验收' if d2_ok else '❌ 误拦'}  D2 真实配置退出码={rc}　阻断={bad}"
          + ("（仅 L9 待人工点验 —— 符合预期）" if d2_ok and bad else
             "（无阻断）" if d2_ok else "  ← 除 L9 外还有阻断，属误拦"))
    results.append(d2_ok)

    print("\nE. 响应体分类器单测（不联网；考的是「假 200」会不会被误判成可打开）")
    # 来源：2026-09-23 实测 —— gpssa.gov.ae 经代理返回 HTTP 200 + WAF 拒绝页
    #（<title>Request Rejected</title>），老分类器只看状态码 ⇒ 判成 ✅ 可打开 ⇒ 假放行。
    # 这里把三种「看着像 200 其实不行」的响应体喂给分类器，考最终分类对不对。

    class _FakeResp:                       # 只要能被 _sniff() 读就行
        def __init__(self, body):
            self._b = body

        def read(self, _n=None):
            return self._b

    def _classify(body, code=200):
        kind, _ = LC._sniff(_FakeResp(body))
        return LC.classify_response(kind, code)

    e_cases = [
        ("E1 WAF 拒绝页（HTTP 200 + 标题 Request Rejected）→ 判 blocked 不判 ok",
         b"<html><head><title>Request Rejected</title></head>"
         b"<body>The requested URL was rejected.</body></html>",
         LC.BLOCKED),
        ("E2 站点把 404 渲染成 200（标题 404 Not Found）→ 判 dead，交 L5 拦",
         b"<html><title>404 Not Found</title><body>page missing</body></html>",
         LC.DEAD),
        ("E3 合法页面正文里出现 access denied → 仍判 ok（防误伤）",
         b"<html><title>Help Centre - How to raise a ticket</title><body>"
         b"If your account is denied access to the portal, contact support."
         + b"x" * 400 + b"</body></html>",
         LC.OK),
    ]
    for label, body, want in e_cases:
        got = _classify(body)
        okk = got == want
        print(f"  {'✅ 拦住' if okk else '❌ 漏判'}  {label}"
              f"　期望={want} 实际={got}")
        results.append(okk)

    print("\nF. 内容质量单测（纯函数夹具；不联网、不渲染 —— 结论确定）")
    # 为什么用夹具而不是"改真实产物再注入"：真实产物上 CI 已经阻断（真破图），
    # 再注入就分不清"拦住的是我注入的"还是"本来就有的"，等于永远拦。纯函数夹具才干净。
    import content_quality as CQ

    def _cq(label, got_ok, detail=""):
        print(f"  {'✅ 拦住' if got_ok else '❌ 漏放'}  {label}"
              + (f"　{detail}" if detail and not got_ok else ""))
        results.append(got_ok)

    # ── F1–F3 字号层级（CT1）与「豁免单不是垃圾桶」───────────────────────────
    # 夹具形态复刻 2026-09-23 实测：`.stat-value` 26.4px，页面章节标题 22px。
    _ct1_known = dict(title="Fixture", sections=["薪酬支付"],
                      texts=[dict(px=26.4, tag="span", cls="stat-value",
                                  head=0, text="3,000-4,000迪拉姆")],
                      overflow=[], cards=[], images=[])
    _f, _ = CQ.judge(_ct1_known, baseline={"entries": []})          # 空豁免单
    _hit = [f for f in _f if f["id"] == "CT1"]
    _cq("F1 字号越界 CT1（无豁免）→ 阻断", bool(_hit) and _hit[0]["level"] == "block",
        f"实得 {[(f['id'], f['level']) for f in _f]}")

    # 命中真实豁免单 ⇒ 必须降为告警并打上 KB 编号（降级 + 留痕，不是静默放过）
    _f2, _ = CQ.judge(_ct1_known, baseline=CQ.load_baseline())
    _h2 = [f for f in _f2 if f["id"] == "CT1"]
    _cq("F2 同一处命中真实豁免单 → 降级告警 + 打 KB 编号（非静默）",
        bool(_h2) and _h2[0]["level"] == "warn" and _h2[0].get("known") == "KB-001",
        f"实得 {[(f['id'], f['level'], f.get('known')) for f in _f2]}")

    # 豁免单**不得**掩护基线之外的新问题：换个类名（match_cls 不匹配）⇒ 仍须阻断
    _ct1_new = dict(_ct1_known)
    _ct1_new["texts"] = [dict(px=30, tag="span", cls="promo-badge",
                              head=0, text="限时￥9.9")]
    _f3, _ = CQ.judge(_ct1_new, baseline=CQ.load_baseline())
    _h3 = [f for f in _f3 if f["id"] == "CT1"]
    _cq("F3 基线之外的同类新问题（换类名）→ 仍须阻断（豁免单不是垃圾桶）",
        bool(_h3) and _h3[0]["level"] == "block" and not _h3[0].get("known"),
        f"实得 {[(f['id'], f['level'], f.get('known')) for f in _f3]}")

    # ── F4 fail-closed：渲染目标里没有 content-section ⇒ 必须报，不许静默通过 ──
    _f4, _ = CQ.judge(dict(title="Request Rejected", sections=[], texts=[],
                           overflow=[], cards=[], images=[]), baseline={"entries": []})
    _cq("F4 渲染目标无 .content-section → fail-closed 报错（不许静默算通过）",
        any(f["id"] == "CQ9" and f["level"] == "block" for f in _f4),
        f"实得 {[(f['id'], f['level']) for f in _f4]}")

    # ── F5–F8 配图来源层（scan_html；probe 关、不联网）─────────────────────
    def _imgs(html):
        ff, im, _ = CQ.scan_html(html, probe=False, baseline={"entries": []})
        return ff, im

    _cases_img = [
        ("F5 空 src → CI1 阻断", '<p><img src="" alt="阿联酋薪酬卡片"></p>', "CI1"),
        ("F6 相对路径 → CI3 阻断", '<p><img src="/images/uae.png" alt="阿联酋薪酬卡片"></p>', "CI3"),
        ("F7 占位图（via.placeholder）→ CI4 阻断",
         '<p><img src="https://via.placeholder.com/600x400" alt="占位图"></p>', "CI4"),
    ]
    for label, html, cid in _cases_img:
        ff, _ = _imgs(html)
        got = [f for f in ff if f["id"] == cid and f["level"] == "block"]
        _cq(label, bool(got), f"实得 {[(f['id'], f['level']) for f in ff]}")

    # 非自有域（coze 图床）只告警不阻断 —— 它是"现状待迁"，不是"本批引入的错"
    ff5, _ = _imgs('<p><img src="https://s.coze.cn/t/AbCdEf/" alt="阿联酋薪酬支付趋势图"></p>')
    _cq("F8 图床非自有域 → CI5 告警（不阻断）",
        any(f["id"] == "CI5" and f["level"] == "warn" for f in ff5)
        and not any(f["level"] == "block" for f in ff5),
        f"实得 {[(f['id'], f['level']) for f in ff5]}")

    # 反向：自有域 + 合规 alt ⇒ 一条都不该有（防误伤，门禁也要能做"绿灯测试"）
    ff6, _ = _imgs('<p><img src="https://www.humancehr.com/img/uae-pay.png" '
                   'alt="阿联酋薪酬支付构成示意图"></p>')
    _cq("F9 反向：自有域 + 合规 alt → 零发现（防误伤）",
        len(ff6) == 0, f"实得 {[(f['id'], f['level']) for f in ff6]}")

    # ── F10 卡片高度极差（CT3）与豁免单 ───────────────────────────────────
    _raw_card = dict(title="Fixture", sections=["薪酬支付"], texts=[],
                     overflow=[], images=[],
                     cards=[dict(idx=0, hs=[211, 211, 211, 255], spread=44)])
    _fc, _ = CQ.judge(_raw_card, baseline={"entries": []})
    _cq("F10 统计卡片高度极差 44px > 40px → CT3 阻断",
        any(f["id"] == "CT3" and f["level"] == "block" for f in _fc),
        f"实得 {[(f['id'], f['level']) for f in _fc]}")

    # ── F11 配色口径锁定（2026-09-23 v3：维持不变 = 绿，与"已生效的变更"同色）──
    #   为什么用测试钉住一条**业务口径**：它被改过两次（v1 全绿 → v2 改灰 → v3 回绿），
    #   每次都是"顺手改一处色值"。文字规则拦不住这种手滑，测试拦得住。
    #   口径再变时必须**同时**改这里 —— 这正是想要的效果：让改口径变成一个显式动作。
    _keep = dict(rid="X1", status="keep", effective="—（维持现行）")
    _eff = dict(rid="X2", status="pending", effective="2026-01-01")
    _sch = dict(rid="X3", status="pending", effective="2027-03-01")
    _chk = dict(rid="X4", status="check", effective="—")
    _cq("F11 配色 v3：维持不变与「有变更已生效」同为绿（同色值；区分靠文案）",
        L.tone_of(_keep) == "no_change" and L.tone_of(_eff) == "in_force"
        and L.TONE["in_force"] == L.TONE["no_change"],
        f"tone_of(keep)={L.tone_of(_keep)} bar={L.TONE['no_change']['bar']}；"
        f"tone_of(pending已生效)={L.tone_of(_eff)} bar={L.TONE['in_force']['bar']}")
    _cq("F11b 配色 v3：计划变更 = 橙黄、待核 = 红（两档不得与绿混同）",
        L.tone_of(_sch) == "upcoming" and L.tone_of(_chk) == "verify"
        and L.TONE["upcoming"]["bar"] != L.TONE["in_force"]["bar"]
        and L.TONE["verify"]["bar"] != L.TONE["in_force"]["bar"],
        f"tone_of(未生效)={L.tone_of(_sch)} bar={L.TONE['upcoming']['bar']}；"
        f"tone_of(待核)={L.tone_of(_chk)} bar={L.TONE['verify']['bar']}")

    # ── F12 页面可见性口径锁定（2026-09-23 v4：红色「来源存疑」不上前端）────────
    #   与 F11 同一思路：把**业务口径**用测试钉死。这条口径的复发形态很隐蔽 ——
    #   只要有人在 build/qc/preview 里"顺手"各写一遍 `status == "check"`，
    #   就又多出 N 份副本，改口径时漏一处 ⇒ 红色重新漏到页面上。
    #   F12 钉的是「唯一判定入口 on_page()」；F12c 钉的是「真实产物确实按它落了」。
    _all4 = [_keep, _eff, _sch, _chk]
    _cq("F12 页面可见性：红色（来源存疑）不上页面，其余三档上页面",
        L.on_page(_keep) and L.on_page(_eff) and L.on_page(_sch) and not L.on_page(_chk)
        and [n["rid"] for n in L.page_notes(_all4)] == ["X1", "X2", "X3"]
        and [n["rid"] for n in L.hidden_notes(_all4)] == ["X4"]
        and L.PAGE_HIDDEN_TONES == ("verify",),
        f"on_page={[L.on_page(n) for n in _all4]} "
        f"page={[n['rid'] for n in L.page_notes(_all4)]} "
        f"hidden={[n['rid'] for n in L.hidden_notes(_all4)]}")
    _vc4 = L.version_counts(_all4)
    _pb4 = [x for x in L.version_bar_probe(_all4) if x]
    _cq("F12b 版本条计数只数页面条目（红色不进计数，也不出「待核 N 项」）",
        _vc4["n_total"] == 3 and _vc4["n_check"] == 0
        and not any("待核" in x for x in _pb4),
        f"n_total={_vc4['n_total']} n_check={_vc4['n_check']} 片段={_pb4}")
    # F12c 端到端：**真实产物**里不得有红色档，且标注块数 = 页面条目数。
    #   前面几条只证明"函数算得对"；这条证明"产物真的按它落了"——
    #   两者缺一，就可能出现"口径对了但产物没重跑"（页面还是旧的）。
    _cfgv = json.load(open(a.config, encoding="utf-8"))
    _pav = os.path.join(a.workdir, slug, "content_AFTER.html")
    if os.path.exists(_pav):
        _rawv = open(_pav, encoding="utf-8").read()
        _nosv = L.strip_style(_rawv)
        _npv = len(L.page_notes(_cfgv["countries"][slug]["notes"]))
        _got_blk = _nosv.count('class="cg-update-note"')
        _got_red = len(re.findall(r'data-cg-tone="verify"', _nosv))
        _cq("F12c 真实产物：无红色档，且标注块数 = 页面条目数",
            _got_red == 0 and _got_blk == _npv,
            f"红色 {_got_red} 处 ｜ 标注块 {_got_blk} / 页面条目 {_npv}"
            + ("　（产物可能是旧口径构建的，重跑 batch_guide_patch.py）"
               if (_got_red or _got_blk != _npv) else ""))
    else:
        _cq("F12c 真实产物：无红色档，且标注块数 = 页面条目数", False, f"缺 {_pav}")

    passed = all(results)
    print("-" * 74)
    print(f"结论：{'✅ 全部符合预期（' + str(len(results)) + ' 例）' if passed else '❌ 有漏放/误拦'}")
    shutil.rmtree(tmp, ignore_errors=True)
    if a.json_out:
        json.dump(dict(passed=passed, cases=len(results)), open(a.json_out, "w"),
                  ensure_ascii=False, indent=1)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
