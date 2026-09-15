#!/usr/bin/env python3
import json, urllib.request, urllib.parse, ssl, sys
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _baidu_auth import (  # noqa: E402  凭据统一由 secrets 提供，禁止硬编码
    CLIENT_ID, CLIENT_SECRET, SITE_ID, get_access_token, refresh_token_value,
)

# 取一次可用 access_token（自动探测失效并刷新；新值由 _baidu_auth 回写 secrets）
TOKEN = get_access_token()
ssl_ctx = ssl.create_default_context()
urllib.request.install_opener(urllib.request.build_opener(urllib.request.ProxyHandler({})))

def get(method, **params):
    p = {"access_token": TOKEN, "site_id": SITE_ID, "method": method,
         "start_date": "20260101", "end_date": "20260831", "max_results": "30"}
    p.update(params)
    url = "https://openapi.baidu.com/rest/2.0/tongji/report/getData?" + urllib.parse.urlencode(p)
    with urllib.request.urlopen(urllib.request.Request(url), context=ssl_ctx, timeout=40) as r:
        return json.loads(r.read())

def rows(d):
    r = d.get("result", {})
    if not r: return []
    fields, items = r.get("fields", []), r.get("items", [[], []])
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
for key, kw in [
    ("source_all", dict(method="source/all/a", metrics="pv_count,visitor_count,new_visitor_count")),
    ("toppage",    dict(method="visit/toppage/a", metrics="pv_count,visitor_count,avg_visit_time,bounce_ratio")),
    ("landing",    dict(method="visit/landingpage/a", metrics="visitor_count,new_visitor_count,bounce_ratio")),
    ("district",   dict(method="visit/district/a", metrics="pv_count,visitor_count,new_visitor_count")),
]:
    try:
        res[key] = rows(get(**kw))
    except Exception as e:
        res[key] = {"error": str(e)}
print(json.dumps(res, ensure_ascii=False, indent=2))
