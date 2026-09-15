#!/usr/bin/env python3
"""
百度统计 WAU（7日活跃用户）查询
================================
核心：WAU 必须跨天去重。逐日 visitor_count 相加 = 人次（会重复计同一访客），
      区间查询的 visitor_count = 去重后的活跃用户数（WAU 口径）。
本脚本同时取两种口径并对比，避免误把"人次"当"用户数"。

用法：python3 baidu_wau.py [days=7]
"""

import json
import urllib.request
import urllib.parse
import ssl
import sys
from datetime import date, timedelta
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _baidu_auth import (  # noqa: E402  凭据统一由 secrets 提供，禁止硬编码
    CLIENT_ID, CLIENT_SECRET, SITE_ID, get_access_token, refresh_token_value,
)


ssl_ctx = ssl.create_default_context()


def http_get(url):
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, context=ssl_ctx, timeout=30) as resp:
        return json.loads(resp.read())


def get_token():
    """凭据与刷新统一由 _baidu_auth 处理（含有效性探测 + 轮换回写）。"""
    return get_access_token()


def get_report(tok, method, metrics, start, end, gran=None, visitor=None, max_results=0):
    p = {"access_token": tok, "site_id": SITE_ID, "method": method,
         "start_date": start, "end_date": end, "metrics": metrics,
         "max_results": str(max_results)}
    if gran:
        p["gran"] = gran
    if visitor:
        p["visitor"] = visitor
    url = "https://openapi.baidu.com/rest/2.0/tongji/report/getData?" + urllib.parse.urlencode(p)
    return http_get(url)


def parse(raw):
    """返回 (rows, fields, sum_row)；rows=[{dimension: {field: val}}]"""
    r = raw.get("result", {})
    if not r:
        return [], [], []
    fields = r.get("fields", [])
    items = r.get("items", [[], []])
    dims, metrics = (items + [[], []])[:2]
    sum_row = (r.get("sum", [[], []]) + [[], []])[0]
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
    return rows, fields, sum_row


def main():
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    end = date.today() - timedelta(days=1)      # 昨天（今天数据不全）
    start = end - timedelta(days=days - 1)
    s, e = start.strftime("%Y%m%d"), end.strftime("%Y%m%d")
    print(f"📅 统计区间：{start} ~ {end}（近 {days} 天，不含今日）", file=sys.stderr)

    tok = get_token()

    # --- 口径 A：区间去重（不带 gran，让百度端做跨天去重）---
    rawA = get_report(tok, "trend/time/a", "pv_count,visitor_count,ip_count,new_visitor_count", s, e)
    rowsA, fieldsA, sumA = parse(rawA)

    # --- 口径 B：gran=week（周粒度，应等价于去重周活）---
    rawB = get_report(tok, "trend/time/a", "pv_count,visitor_count,new_visitor_count", s, e, gran="week")
    rowsB, _, _ = parse(rawB)

    # --- 口径 C：gran=day 逐日（人次口径，用于对比去重幅度）---
    rawC = get_report(tok, "trend/time/a", "pv_count,visitor_count,ip_count,new_visitor_count", s, e, gran="day")
    rowsC, fieldsC, sumC = parse(rawC)

    # --- 新老访客（区间去重）---
    rawNew = get_report(tok, "trend/time/a", "visitor_count", s, e, gran="week", visitor="new")
    rawOld = get_report(tok, "trend/time/a", "visitor_count", s, e, gran="week", visitor="old")
    rowsNew, _, _ = parse(rawNew)
    rowsOld, _, _ = parse(rawOld)

    out = {
        "range": {"start": str(start), "end": str(end), "days": days},
        "A_range_dedup": {"rows": rowsA, "fields": fieldsA, "sum": sumA},
        "B_week_gran": {"rows": rowsB},
        "C_daily": {"rows": rowsC, "fields": fieldsC, "sum": sumC},
        "new_old": {"new": rowsNew, "old": rowsOld},
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
