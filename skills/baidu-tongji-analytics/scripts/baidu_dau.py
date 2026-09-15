#!/usr/bin/env python3
"""
Humance DAU / WAU / MAU 取数
=============================
关键区分（易错）：
  * DAU   = 单日 visitor_count。百度单日内已去重 → **精确值**，可直接用。
  * WAU   = 7 天独立访客。百度开放 API **跨天不去重**，区间值 = 逐日人次相加
            → 只能估算。公式：新访客(天然独立) + 老访客人次 ÷ 平均到访天数。
  * MAU   = 30 天独立访客，同上，只能估算。

注意：百度统计 gran=day 单次最多返回 20 行，更早的日期会被静默丢弃（不报错），
      所以查 30 天必须分段（每段 ≤20 天）后合并。

用法：python3 baidu_dau.py [days=30]
输出：stdout 为纯 JSON（提示语走 stderr）
"""

import json
import urllib.request
import urllib.parse
import ssl
import sys
import statistics
from datetime import date, timedelta
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _baidu_auth import (  # noqa: E402  凭据统一由 secrets 提供，禁止硬编码
    CLIENT_ID, CLIENT_SECRET, SITE_ID, get_access_token, refresh_token_value,
)


ssl_ctx = ssl.create_default_context()
METRICS = "pv_count,visitor_count,ip_count,new_visitor_count"


def http_get(url):
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, context=ssl_ctx, timeout=30) as resp:
        return json.loads(resp.read())


def get_token():
    """凭据与刷新统一由 _baidu_auth 处理（含有效性探测 + 轮换回写）。"""
    return get_access_token()


def get_report(tok, start, end, gran=None, visitor=None, metrics=METRICS):
    p = {"access_token": tok, "site_id": SITE_ID, "method": "trend/time/a",
         "start_date": start, "end_date": end, "metrics": metrics, "max_results": "0"}
    if gran:
        p["gran"] = gran
    if visitor:
        p["visitor"] = visitor
    url = "https://openapi.baidu.com/rest/2.0/tongji/report/getData?" + urllib.parse.urlencode(p)
    return http_get(url)


def parse(raw):
    r = raw.get("result", {})
    if not r:
        return [], []
    fields = r.get("fields", [])
    items = r.get("items", [[], []])
    dims, metrics = (items + [[], []])[:2]
    rows = []
    for i, dim in enumerate(dims):
        dval = dim[0] if isinstance(dim, list) and dim else dim
        if isinstance(dval, dict):
            dval = dval.get("name", str(dval))
        row = {"_dim": str(dval)}
        if i < len(metrics):
            for j, f in enumerate(fields[1:]):
                if j < len(metrics[i]):
                    row[f] = metrics[i][j]
        rows.append(row)
    return rows, fields


def segmented(tok, start, end, visitor=None, metrics=METRICS):
    """分段查询规避 20 行上限，返回按日期升序的合并结果。"""
    out, cur = [], start
    while cur <= end:
        seg_end = min(cur + timedelta(days=19), end)
        rows, _ = parse(get_report(tok, cur.strftime("%Y%m%d"), seg_end.strftime("%Y%m%d"),
                                   gran="day", visitor=visitor, metrics=metrics))
        out.extend(rows)
        cur = seg_end + timedelta(days=1)
    # 百度按日期倒序返回，统一升序
    out.sort(key=lambda r: r["_dim"])
    return out


def dedup_estimate(new_v, old_visits, avg_days):
    """新访客天然独立 + 老访客人次按平均到访天数折算。"""
    return round(new_v + old_visits / float(avg_days))


def main():
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=days - 1)
    print(f"统计区间：{start} ~ {end}（近 {days} 天，不含今日）", file=sys.stderr)

    tok = get_token()

    daily = segmented(tok, start, end)
    daily_new = segmented(tok, start, end, visitor="new", metrics="visitor_count")

    new_map = {r["_dim"]: r.get("visitor_count", 0) for r in daily_new}

    rows = []
    for r in daily:
        v = r.get("visitor_count", 0)
        nv = new_map.get(r["_dim"], 0)
        rows.append({
            "date": r["_dim"],
            "pv": r.get("pv_count", 0),
            "dau": v,                       # 单日已去重 → 精确 DAU
            "ip": r.get("ip_count", 0),
            "new_visitor": nv,
            "old_visitor": max(v - nv, 0),
            "pv_per_uv": round(r.get("pv_count", 0) / v, 2) if v else 0,
        })

    daus = [r["dau"] for r in rows]
    total_uv = sum(daus)                                   # 人次口径
    total_new = sum(r["new_visitor"] for r in rows)
    total_old = sum(r["old_visitor"] for r in rows)

    def block(n):
        sub = rows[-n:]
        return {
            "days": len(sub),
            "uv_visits": sum(r["dau"] for r in sub),        # 人次
            "new_visitor": sum(r["new_visitor"] for r in sub),
            "old_visits": sum(r["old_visitor"] for r in sub),
            "dau_avg": round(statistics.mean([r["dau"] for r in sub])),
            "dau_median": round(statistics.median([r["dau"] for r in sub])),
            "dau_max": max(r["dau"] for r in sub),
            "dau_min": min(r["dau"] for r in sub),
            "dedup_est": {
                f"avg_days_{d}": dedup_estimate(
                    sum(r["new_visitor"] for r in sub),
                    sum(r["old_visitor"] for r in sub), d)
                for d in ("1.0", "1.1", "1.2", "1.3", "1.5")
            },
        }

    wau = block(7)
    mau = block(days)

    # 工作日 / 周末
    import datetime as _dt
    def _wd(ds):
        return _dt.datetime.strptime(ds.replace("/", "-"), "%Y-%m-%d").weekday()
    wds = [r["dau"] for r in rows if _wd(r["date"]) < 5]
    wes = [r["dau"] for r in rows if _wd(r["date"]) >= 5]

    out = {
        "range": {"start": str(start), "end": str(end), "days": days},
        "daily": rows,
        "period_total": {
            "uv_visits": total_uv, "new_visitor": total_new, "old_visitor": total_old,
            "pv": sum(r["pv"] for r in rows),
            "old_ratio": round(total_old / total_uv * 100, 1) if total_uv else 0,
        },
        "dau_exact": {
            "avg": round(statistics.mean(daus)),
            "median": round(statistics.median(daus)),
            "max": max(daus), "max_date": rows[daus.index(max(daus))]["date"],
            "min": min(daus), "min_date": rows[daus.index(min(daus))]["date"],
        },
        "wau_est": wau,
        "mau_est": mau,
        "weekday_weekend": {
            "weekday_avg": round(statistics.mean(wds)) if wds else 0,
            "weekend_avg": round(statistics.mean(wes)) if wes else 0,
            "ratio": round(statistics.mean(wes) / statistics.mean(wds), 2) if wds and wes else 0,
        },
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
