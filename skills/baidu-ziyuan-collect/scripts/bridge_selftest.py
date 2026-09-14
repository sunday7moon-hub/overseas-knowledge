#!/usr/bin/env python3
"""Browser Bridge 一键自检。

用途：每次改动扩展或怀疑桥接异常时跑一遍，输出
  ① 连接与版本  ② 扩展自检 + 已收集错误  ③ chrome://extensions 错误探测
  ④ 真实页面的命令序列压测（可选，--bench N）

用法：
  python3 bridge_selftest.py                # 快速自检
  python3 bridge_selftest.py --bench 10     # 追加 10 轮命令序列压测
  python3 bridge_selftest.py --url https://admin.humancehr.com/admin/humance-analytics
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from control import Bridge, BridgeError  # noqa: E402

DEFAULT_URL = "https://www.humancehr.com/"


def hr(title):
    print("\n" + "─" * 62)
    print(f"  {title}")
    print("─" * 62)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=DEFAULT_URL, help="压测用的目标页")
    ap.add_argument("--bench", type=int, default=0, help="命令序列压测轮数")
    ap.add_argument("--diagnostics", action="store_true", help="同时输出完整诊断 JSON")
    args = ap.parse_args()

    b = Bridge()

    # ── ① 连接与版本 ──────────────────────────────
    hr("① 连接 / 版本 / 累计成功率")
    try:
        p = b.ping()
    except Exception as e:
        print(f"❌ 连不上 Bridge：{type(e).__name__}: {e}")
        print("   检查：服务端是否在跑（lsof -i:9334 -sTCP:LISTEN）")
        return 1
    for k in ("extension_connected", "extension_version", "epoch", "reconnects",
              "cmd_total", "cmd_ok", "cmd_fail", "success_rate"):
        print(f"   {k:20s} = {p.get(k)}")
    ver = str(p.get("extension_version"))
    if ver != "1.3.0":
        print(f"   ⚠️ 扩展版本是 {ver}，期望 1.3.0 —— 需在 chrome://extensions 点刷新")

    # ── ② 扩展自检 + 已收集错误 ────────────────────
    hr("② 扩展自检 / 已收集的错误")
    diag = None
    try:
        diag = b.get_diagnostics()
        sc = diag.get("selfCheck", {})
        print("   自检：")
        for k, v in (sc.get("apis") or {}).items():
            print(f"     API {k:16s} = {v}")
        for k in ("wsStateText", "heartbeatActive", "reconnectDelayMs", "lastTabId", "lastUrl"):
            print(f"     {k:16s} = {sc.get(k)}")
        d = diag.get("diagnostics") or {}
        boot = d.get("boot") or {}
        print(f"\n   启动记录：boots={d.get('boots')}  最后一次={boot.get('at')}  v={boot.get('v')}")
        errs = d.get("errors") or []
        fails = d.get("cmdFails") or []
        print(f"   未捕获异常 {len(errs)} 条，命令失败 {len(fails)} 条")
        for e in errs[:8]:
            print(f"     ❌ [{e.get('at')}] {e.get('scope')}: {str(e.get('msg'))[:160]}")
        for e in fails[:8]:
            print(f"     ⚠️ [{e.get('at')}] {e.get('method')}: {str(e.get('msg'))[:160]}")
        if args.diagnostics:
            print("\n   " + json.dumps(diag, ensure_ascii=False, indent=2)[:4000].replace("\n", "\n   "))
    except BridgeError as e:
        print(f"   ⚠️ 不支持 get_diagnostics（扩展 < 1.3.0？）：{str(e)[:140]}")

    # ── ③ 直接探测 chrome://extensions 上的错误文本 ──
    hr("③ chrome://extensions「错误」按钮内容探测")
    try:
        pr = b.probe_ext_errors()
        if pr.get("ok"):
            res = pr.get("result") or {}
            items = res.get("items") or []
            if not items:
                print("   ✅ 页面上没有处于「错误」状态的扩展卡片（无报错）")
            for it in items:
                print(f"   ❌ {it.get('name')} → 按钮「{it.get('button')}」")
                for line in str(it.get("detail") or "").splitlines()[:12]:
                    print(f"        {line}")
        else:
            print(f"   ⚠️ 无法自动探测：{pr.get('reason')}")
            print("      （Chrome 一般禁止调试 chrome:// 页面，属预期；改用第 ② 节的收集结果）")
    except BridgeError as e:
        print(f"   ⚠️ 不支持 probe_ext_errors（扩展 < 1.3.0？）：{str(e)[:140]}")

    # ── ④ 命令序列压测 ────────────────────────────
    if args.bench > 0:
        hr(f"④ 命令序列压测（{args.bench} 轮：navigate→get_url→get_text→get_html→type_text→get_value）")
        ok = 0
        fails = []
        t0 = time.time()
        for i in range(args.bench):
            try:
                b.navigate(args.url)
                b.get_url()
                b.get_text()
                b.get_html()
                b.evaluate("(()=>{let i=document.querySelector('#__st');"
                           "if(!i){i=document.createElement('input');i.id='__st';document.body.prepend(i);}return 1})()")
                r = b.type_text("#__st", f"round-{i+1}")
                got = b.get_value("#__st")
                assert (got or {}).get("value") == f"round-{i+1}", f"写读不一致: {got}"
                ok += 1
            except Exception as e:
                fails.append((i + 1, type(e).__name__, str(e)[:100]))
            if (i + 1) % 5 == 0:
                print(f"   …{i+1}/{args.bench} 完成，用时 {time.time()-t0:.0f}s，失败 {len(fails)}", flush=True)
        print(f"\n   结果：成功 {ok}/{args.bench} = {ok/args.bench*100:.0f}%   总耗时 {time.time()-t0:.0f}s")
        print(f"   客户端统计：{b.stats_report()}")
        for f in fails:
            print(f"     ❌ 第 {f[0]} 轮 {f[1]}: {f[2]}")

    print("\n自检结束。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
