#!/usr/bin/env python3
"""
百度统计自定义周期拉取脚本
用于 Humance 周报：拉取指定 start_date ~ end_date 的数据
用法：python3 baidu_tongji_custom.py <YYYYMMDD> <YYYYMMDD>
"""

import json
import urllib.request
import urllib.parse
import ssl
import sys
from datetime import datetime
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


def refresh_access_token():
    """取可用凭据；返回 (access_token, refresh_token)。
    已改为**按需**刷新：现有 token 有效则直接复用，避免每次运行都轮换 refresh_token。
    新值由 _baidu_auth 回写 ~/.workbuddy/secrets/baidu_tongji.json。"""
    return get_access_token(), refresh_token_value()


def get_report(access_token, method, metrics, start_date, end_date, gran=None, visitor=None, max_results=10):
    params = {
        "access_token": access_token,
        "site_id": SITE_ID,
        "method": method,
        "start_date": start_date,
        "end_date": end_date,
        "metrics": metrics,
        "max_results": str(max_results),
    }
    if gran:
        params["gran"] = gran
    if visitor:
        params["visitor"] = visitor
    url = "https://openapi.baidu.com/rest/2.0/tongji/report/getData?" + urllib.parse.urlencode(params)
    return http_get(url)


def format_report(raw):
    result = raw.get("result", {})
    fields = result.get("fields", [])
    items_data = result.get("items", [[], [], [], []])
    dimensions = items_data[0]
    metrics_data = items_data[1]
    sum_data = result.get("sum", [[], []])
    rows = []
    for i, dim in enumerate(dimensions):
        row = {}
        if isinstance(dim, list):
            dim_val = dim[0] if dim else ""
            if isinstance(dim_val, dict):
                row["dimension"] = dim_val.get("name", str(dim_val))
            else:
                row["dimension"] = str(dim_val)
        else:
            row["dimension"] = str(dim)
        if i < len(metrics_data):
            vals = metrics_data[i]
            for j, field in enumerate(fields[1:]):
                if j < len(vals):
                    row[field] = vals[j]
        rows.append(row)
    return rows, fields, sum_data


def main():
    if len(sys.argv) >= 3:
        start_date = sys.argv[1]
        end_date = sys.argv[2]
    else:
        print("用法：python3 baidu_tongji_custom.py <YYYYMMDD> <YYYYMMDD>")
        sys.exit(1)

    print("🔑 获取可用凭据（按需刷新）...")
    access_token, _ = refresh_access_token()
    print("✅ 凭据就绪")

    out = {}

    # 1. 趋势（按天）
    data = get_report(access_token, "trend/time/a",
                      "pv_count,visitor_count,ip_count,new_visitor_count",
                      start_date, end_date, gran="day", max_results=0)
    rows, fields, sums = format_report(data)
    out["trend"] = {"rows": rows, "sum": sums[0] if sums and sums[0] else []}

    # 2. 来源
    data = get_report(access_token, "source/all/a",
                      "pv_count,visitor_count,ip_count",
                      start_date, end_date, max_results=10)
    rows, _, sums = format_report(data)
    out["source"] = {"rows": rows, "sum": sums[0] if sums and sums[0] else []}

    # 3. 受访页面 TOP
    data = get_report(access_token, "visit/toppage/a",
                      "pv_count,visitor_count",
                      start_date, end_date, max_results=10)
    rows, _, sums = format_report(data)
    out["toppage"] = {"rows": rows, "sum": sums[0] if sums and sums[0] else []}

    # 4. 入口页面 TOP
    data = get_report(access_token, "visit/landingpage/a",
                      "visitor_count",
                      start_date, end_date, max_results=10)
    rows, _, _ = format_report(data)
    out["landingpage"] = {"rows": rows}

    # 5. 搜索引擎
    data = get_report(access_token, "source/engine/a",
                      "pv_count,visitor_count,ip_count",
                      start_date, end_date, max_results=10)
    rows, _, _ = format_report(data)
    out["engine"] = {"rows": rows}

    # 6. 地域（省份）分布 TOP
    try:
        data = get_report(access_token, "visit/district/a",
                          "pv_count,visitor_count",
                          start_date, end_date, max_results=10)
        rows, _, _ = format_report(data)
        out["district"] = {"rows": rows}
    except Exception as e:
        out["district"] = {"rows": [], "error": str(e)}

    # 7. 新老访客
    data_new = get_report(access_token, "trend/time/a",
                          "pv_count,visitor_count",
                          start_date, end_date, gran="day", visitor="new", max_results=0)
    data_old = get_report(access_token, "trend/time/a",
                          "pv_count,visitor_count",
                          start_date, end_date, gran="day", visitor="old", max_results=0)
    rows_new, _, _ = format_report(data_new)
    rows_old, _, _ = format_report(data_old)
    out["visitor_newold"] = {"new": rows_new, "old": rows_old}

    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
