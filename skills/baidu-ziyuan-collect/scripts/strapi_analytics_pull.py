#!/usr/bin/env python3
"""通过 admin API 直取 Humance 埋点统计数据（结构化 JSON，秒级返回）。

用法:
  python3 strapi_analytics_pull.py --start 2026-09-04 --end 2026-09-10
  python3 strapi_analytics_pull.py --start 2026-09-10 --end 2026-09-11 --out /tmp/x.json

原理（2026-09-11 打通）:
  admin Analytics 页面的数据源是 https://admin.humancehr.com/api/analytics-events/summary
  —— 该端点**服务端强制要求管理员身份**（返回"仅管理员可查看埋点统计"），
  因此 API Token 无论权限如何都会被拒（实测 401）。
  可行路径：在浏览器上下文里带 localStorage.jwtToken 发 fetch。

对比 SPA 页面取数（admin_analytics_pull.py）:
  ✅ 结构化 JSON（不用解析 13 万字符文本）｜✅ 秒级｜✅ 无需点界面/稳定判定
  ⚠️ 依赖 admin 登录态（JWT 过期需重新登录 admin.humancehr.com）

前置:
  ① Bridge Server 在 9334 运行  ② Chrome 已登录 admin.humancehr.com
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import control  # noqa: E402

ADMIN_URL = "https://admin.humancehr.com/admin"
API_TPL = "/api/analytics-events/summary?period=range&start={start}&end={end}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True, help="YYYY-MM-DD")
    ap.add_argument("--end", required=True, help="YYYY-MM-DD")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    b = control.Bridge()
    if not b.wait_ready(35):
        print("❌ 扩展未连接（检查 Bridge Server 与 chrome://extensions）")
        return 2

    # 只在开头导航一次（ensure_page 会重载页面）
    b.navigate(ADMIN_URL)
    for _ in range(25):
        try:
            if b.evaluate("document.body.innerText.length") > 200:
                break
        except Exception:
            pass
        time.sleep(2)

    path = API_TPL.format(start=args.start, end=args.end)
    print(f"请求: {path}")

    started = b.evaluate("""(() => {
      const jwt = JSON.parse(localStorage.getItem('jwtToken') || '""');
      if (!jwt) return 'NO_JWT';
      window.__api = 'PENDING';
      fetch(%s, {headers: {'Accept': 'application/json', 'Authorization': 'Bearer ' + jwt}})
        .then(r => r.text().then(t => { window.__api = JSON.stringify({s: r.status, b: t}); }))
        .catch(e => { window.__api = 'ERR:' + e.message; });
      return 'GO';
    })()""" % json.dumps(path))
    if started == "NO_JWT":
        print("❌ 浏览器里没有 jwtToken —— 请先在 Chrome 登录 admin.humancehr.com")
        return 3

    raw = "PENDING"
    for _ in range(30):
        time.sleep(1)
        raw = b.evaluate("window.__api")
        if raw != "PENDING":
            break

    if not isinstance(raw, str) or not raw.startswith("{"):
        print(f"❌ 取数失败: {str(raw)[:200]}")
        return 4

    payload = json.loads(raw)
    status, body = payload["s"], payload["b"]
    if status != 200:
        print(f"❌ HTTP {status}: {body[:200]}")
        if status == 401:
            print("   → 管理员登录态已过期，请在 Chrome 重新登录 admin.humancehr.com")
        return 5

    data = json.loads(body)["data"]
    out = args.out or f"/tmp/humance_analytics_{args.start}_{args.end}.json"
    with open(out, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)

    print(f"\n✓ 已保存: {out}")
    print(f"  区间: {data['range']['start']} ~ {data['range']['end']} (UTC)")
    print("\n=== 逐日（PV/UV 仅 page_view 事件；DAU=全部事件去重）===")
    for bk in data.get("daily_buckets", []):
        print(f"  {bk['date']}  pv={bk['pv']:>6}  uv={bk['uv']:>6}  dau={bk['dau']}")
    print("\n=== 关键指标 ===")
    pv = data["page_view"]
    print(f"  page_view      pv={pv['pv']}  uv={pv['visitor_uv']}  logged_uv={pv['logged_user_uv']}")
    print(f"  read_users(阅读)      = {data['read_users']}")
    print(f"  login_success_users   = {data['login_success_users']}")
    print(f"  favorite/download     = {data['favorite_users']} / {data['download_users']}")
    print(f"  subscribe_users       = {data['subscribe_users']}")
    print(f"  newsletter_box_view   = {data['newsletter_box_view_users']}")
    print(f"  register_success(from newsletter) = {data['register_success_from_newsletter_users']}")
    print(f"  activation            = {json.dumps(data['activation'], ensure_ascii=False)}")
    print("\n=== 事件明细 ===")
    for e in data.get("event_metrics", []):
        print(f"  {e['event_name']:<32} pv={e['pv']:>7} uv={e['visitor_uv']:>7} logged_uv={e['logged_user_uv']}")
    ao = data.get("article_metrics", [])
    if ao:
        print(f"\n=== 文章 TOP10（共 {len(ao)} 篇）===")
        for i, a in enumerate(ao[:10], 1):
            print(f"  {i:2d}. {str(a.get('title',''))[:50]:<50} pv={a.get('pv')} uv={a.get('visitor_uv')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
