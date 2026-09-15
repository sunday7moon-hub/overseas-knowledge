#!/usr/bin/env python3
import json, urllib.request, urllib.parse, ssl
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _baidu_auth import (  # noqa: E402  凭据统一由 secrets 提供，禁止硬编码
    CLIENT_ID, CLIENT_SECRET, SITE_ID, get_access_token, refresh_token_value,
)

# 取一次可用 access_token（自动探测失效并刷新；新值由 _baidu_auth 回写 secrets）
TOKEN = get_access_token()
ssl_ctx=ssl.create_default_context()
urllib.request.install_opener(urllib.request.build_opener(urllib.request.ProxyHandler({})))
def get(method,**p):
    q={"access_token":TOKEN,"site_id":SITE_ID,"method":method,"start_date":"20260829","end_date":"20260904","max_results":"20"}
    q.update(p)
    u="https://openapi.baidu.com/rest/2.0/tongji/report/getData?"+urllib.parse.urlencode(q)
    return json.loads(urllib.request.urlopen(urllib.request.Request(u),context=ssl_ctx,timeout=40).read())
def rows(d):
    r=d.get("result",{}); 
    if not r: return []
    f=r.get("fields",[]); dims,mets=(r.get("items",[[],[]])+[[],[]])[:2]
    out=[]
    for i,dim in enumerate(dims):
        dv=dim[0] if isinstance(dim,list) and dim else dim
        if isinstance(dv,dict): dv=dv.get("name",str(dv))
        row={"_dim":str(dv)}
        if i<len(mets):
            for j,ff in enumerate(f[1:]):
                if j<len(mets[i]): row[ff]=mets[i][j]
        out.append(row)
    return out
print("=== 文章TOP页(visit/toppage 近7天) ===")
for r in rows(get("visit/toppage/a",metrics="pv_count,visitor_count,avg_visit_time,bounce_ratio"))[:15]:
    print(r)
print("\n=== 来源(source/all 近7天) ===")
for r in rows(get("source/all/a",metrics="pv_count,visitor_count,new_visitor_count"))[:10]:
    print(r)
print("\n=== 新老访客(近7天) ===")
for tag in ["new","old"]:
    print(tag, rows(get("trend/time/a",gran="day",visitor=tag,metrics="pv_count,visitor_count,avg_visit_time,bounce_ratio"))[:1])
