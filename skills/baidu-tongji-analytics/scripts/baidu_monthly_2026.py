#!/usr/bin/env python3
"""2026 年 1-8 月月度数据（gran=month 一次返回）+ 全周期质量指标"""
import json, urllib.request, urllib.parse, ssl, sys
from datetime import date
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _baidu_auth import (  # noqa: E402  凭据统一由 secrets 提供，禁止硬编码
    CLIENT_ID, CLIENT_SECRET, SITE_ID, get_access_token, refresh_token_value,
)

# 取一次可用 access_token（自动探测失效并刷新；新值由 _baidu_auth 回写 secrets）
ACCESS_TOKEN = get_access_token()

ssl_ctx = ssl.create_default_context()
NO_PROXY = {"http": "", "https": ""}
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
urllib.request.install_opener(opener)

def get(method, **params):
    p = {"access_token": ACCESS_TOKEN, "site_id": SITE_ID, "method": method,
         "start_date": "20260101", "end_date": "20260831", "max_results": "0"}
    p.update(params)
    url = "https://openapi.baidu.com/rest/2.0/tongji/report/getData?" + urllib.parse.urlencode(p)
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, context=ssl_ctx, timeout=40) as r:
        return json.loads(r.read())

def rows(d):
    r = d.get("result", {})
    if not r: return []
    fields = r.get("fields", [])
    items = r.get("items", [[], []])
    dims, mets = (items + [[], []])[:2]
    out = []
    for i, dim in enumerate(dims):
        dv = dim[0] if isinstance(dim, list) and dim else dim
        if isinstance(dv, dict): dv = dv.get("name", str(dv))
        row = {"_dim": str(dv)}
        if i < len(mets):
            for j, f in enumerate(fields[1:]):
                if j < len(mets[i]): row[f] = mets[i][j]
        out.append(row)
    return out

res = {}
try:
    # 1) 月度趋势
    res["monthly"] = rows(get("trend/time/a", gran="month",
        metrics="pv_count,visitor_count,ip_count,new_visitor_count"))
    # 2) 全周期质量（跳出/停留/页数）
    res["quality"] = rows(get("trend/time/a", gran="month",
        metrics="pv_count,visitor_count,avg_visit_time,bounce_ratio,trans_count"))
    # 3) 新老访客
    res["visitor_new"] = rows(get("trend/time/a", gran="month", visitor="new",
        metrics="pv_count,visitor_count,avg_visit_time,bounce_ratio"))
    res["visitor_old"] = rows(get("trend/time/a", gran="month", visitor="old",
        metrics="pv_count,visitor_count,avg_visit_time,bounce_ratio"))
    # 4) 来源
    res["source"] = rows(get("source/engine/a",
        metrics="pv_count,visitor_count,new_visitor_count"))
    res["searchword_engine"] = rows(get("source/searchword/a",
        metrics="pv_count,visitor_count") )
except Exception as e:
    res["error"] = str(e)

print(json.dumps(res, ensure_ascii=False, indent=2))
