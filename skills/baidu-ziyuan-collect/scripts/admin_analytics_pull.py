#!/usr/bin/env python3
"""按自定义日期区间拉取 Strapi admin analytics 后台数据（humancehr）。

用法:
  python3 admin_analytics_pull.py --start 2026-09-04 --end 2026-09-10
  python3 admin_analytics_pull.py --preset 7d        # 近 7 日
  python3 admin_analytics_pull.py --preset 30d       # 近 30 日

输出:
  /tmp/admin_analytics_<start>_<end>.txt    完整页面文本（约 2400 行）
  stdout                                     核心指标 JSON + 文章 TOP10/20

前置:
  ① Bridge Server 已在 9334 端口运行（bridge_server.py）
  ② 扩展 >= v1.3.0（type_text / get_value 需要）
  ③ Chrome 已登录 admin.humancehr.com

三个已知坑（详见 SKILL.md 2.6）:
  1. ensure_page 每次都会重载页面 —— 本脚本只在开头 navigate 一次
  2. SPA 异步取数 —— 用"连续 N 次文本完全一致"做稳定判定
  3. input[type=date] 无 id —— 先打临时 id 再 type_text
"""
import argparse
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import control  # noqa: E402

URL = "https://admin.humancehr.com/admin/humance-analytics"
MIN_LEN = 10000          # 页面就绪的最小文本长度
STABLE_HITS = 3          # 连续一致次数达到即判定稳定


def body(b):
    return json.loads(b.evaluate(
        "(()=>{return JSON.stringify({t:document.body.innerText||''})})()"))["t"]


def wait_ready(b, tries=30, gap=2):
    for _ in range(tries):
        if len(body(b)) > MIN_LEN:
            return True
        time.sleep(gap)
    return False


def wait_stable(b, tries=40, gap=2):
    """等页面数据稳定：连续 STABLE_HITS 次文本完全一致"""
    last, same = None, 0
    for _ in range(tries):
        time.sleep(gap)
        t = body(b)
        if t == last:
            same += 1
            if same >= STABLE_HITS:
                return t
        else:
            same = 0
        last = t
    return last or ""


def grab_metrics(t):
    d = {}
    m = re.search(r"当前区间：(\d{4}-\d{2}-\d{2}) ~ (\d{4}-\d{2}-\d{2})", t)
    d["range"] = f"{m.group(1)}~{m.group(2)}" if m else "?"
    patterns = [
        ("site_pv", r"全站 PV\n([\d,]+)\npage_view"),
        ("site_uv", r"全站 UV\n([\d,]+)\n访客去重"),
        ("login", r"登录人数\n([\d,]+)\nlogin_success"),
        ("read", r"阅读人数\n([\d,]+)\narticle_view"),
        ("subscribe_country", r"国家订阅\n([\d,]+)\nsubscriptions"),
        ("subscribe_weekly", r"周报订阅\n([\d,]+)\nnewsletter_subscribe_success"),
        ("favorite", r"收藏人数\n([\d,]+)\nfavorites"),
        ("download", r"下载人数\n([\d,]+)\ndownload"),
        ("nl_view", r"订阅曝光人数\t([\d,]+)"),
        ("nl_click", r"订阅点击人数\t([\d,]+)"),
        ("nl_need_reg", r"引导注册人数\t([\d,]+)"),
        ("nl_reg_success", r"注册成功人数\t([\d,]+)"),
        ("nl_sub_success", r"订阅成功人数\t([\d,]+)"),
        ("reg_user", r"注册用户\t([\d,]+)\t"),
        ("activated", r"激活用户（深度行为≥1）\n([\d,]+)\n"),
        ("activation_rate", r"激活率\n([\d.]+%)\n"),
    ]
    for k, pat in patterns:
        m = re.search(pat, t)
        d[k] = m.group(1) if m else "?"
    return d


def grab_articles(t, topn=20):
    """从「文章 PV / UV」表提取排行"""
    seg = t.split("文章 PV / UV", 1)
    if len(seg) < 2:
        return []
    lines = seg[1].split("\n")
    out = []
    for ln in lines:
        parts = ln.split("\t")
        if len(parts) >= 5 and re.fullmatch(r"[\d,]+", parts[2].strip() or ""):
            out.append({
                "title": parts[0].strip(),
                "doc_id": parts[1].strip(),
                "pv": parts[2].strip(),
                "uv": parts[3].strip(),
                "login_uv": parts[4].strip(),
            })
        if len(out) >= topn:
            break
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", help="YYYY-MM-DD")
    ap.add_argument("--end", help="YYYY-MM-DD")
    ap.add_argument("--preset", choices=["7d", "30d"], help="用预设区间（与后台按钮同口径）")
    ap.add_argument("--outdir", default="/tmp")
    ap.add_argument("--topn", type=int, default=20)
    args = ap.parse_args()

    if not args.preset and not (args.start and args.end):
        ap.error("需要 --start/--end，或 --preset 7d|30d")

    b = control.Bridge()
    if not b.wait_ready(35):
        print("❌ 扩展未连接（检查 Bridge Server 与 chrome://extensions）")
        return 2
    print("✓ 扩展已连接")

    # ⚠️ 只在开头导航一次（ensure_page 会重载页面，取数循环里绝不能用）
    b.navigate(URL)
    if not wait_ready(b):
        print("❌ 页面未就绪（SPA 未渲染完）")
        return 3
    print("✓ 页面已渲染")

    if args.preset:
        label = "近 7 日" if args.preset == "7d" else "近 30 日"
        b.click_by_text(label, selector="button")
        tag = args.preset
    else:
        b.click_by_text("自定义区间", selector="button")
        time.sleep(1.5)
        n = b.evaluate("""(()=>{const a=document.querySelectorAll('input[type=date]');
          if(a.length<2) return 'FOUND_'+a.length;
          a[0].id='bs'; a[1].id='be'; return 'OK';})()""")
        if not str(n).startswith("OK"):
            print(f"❌ 日期输入框探测失败: {n}")
            return 4
        b.type_text("#bs", args.start)
        b.type_text("#be", args.end)
        time.sleep(0.6)
        v1 = b.get_value("#bs").get("value")
        v2 = b.get_value("#be").get("value")
        if v1 != args.start or v2 != args.end:
            print(f"❌ 日期写入校验失败: {v1} / {v2}")
            return 5
        print(f"✓ 日期写入校验通过: {v1} ~ {v2}")
        b.click_by_text("查询", selector="button")
        tag = f"{args.start}_{args.end}"

    t = wait_stable(b)
    if not t:
        print("❌ 取数超时")
        return 6

    m = grab_metrics(t)
    out = os.path.join(args.outdir, f"admin_analytics_{tag}.txt")
    with open(out, "w") as f:
        f.write(t)

    print("\n=== 核心指标 ===")
    print(json.dumps(m, ensure_ascii=False, indent=1))
    print(f"\n=== 文章 TOP{args.topn} ===")
    for i, a in enumerate(grab_articles(t, args.topn), 1):
        print(f"{i:2d}. {a['title'][:52]:<52s} PV={a['pv']:>5s} UV={a['uv']:>5s} 登录={a['login_uv']}")
    print(f"\n完整文本已保存: {out}  ({len(t)} 字符)")

    if m.get("range", "?").replace("~", "_") != tag:
        print(f"⚠️ 注意：页面显示区间 {m['range']} 与请求 {tag} 不一致")
    return 0


if __name__ == "__main__":
    sys.exit(main())
