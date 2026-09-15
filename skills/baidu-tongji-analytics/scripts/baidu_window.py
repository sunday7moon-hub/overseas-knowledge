#!/usr/bin/env python3
"""按明确日期窗口拉取基础数据。用法: baidu_window.py START END"""
import json, urllib.request, urllib.parse, ssl, sys
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _baidu_auth import (  # noqa: E402  凭据统一由 secrets 提供，禁止硬编码
    CLIENT_ID, CLIENT_SECRET, SITE_ID, get_access_token, refresh_token_value,
)

# 取一次可用 access_token（自动探测失效并刷新；新值由 _baidu_auth 回写 secrets）
TOKEN = get_access_token()
START=sys.argv[1] if len(sys.argv)>1 else "20260828"
END=sys.argv[2] if len(sys.argv)>2 else "20260903"
ssl_ctx=ssl.create_default_context()
urllib.request.install_opener(urllib.request.build_opener(urllib.request.ProxyHandler({})))
def get(method,**p):
    q={"access_token":TOKEN,"site_id":SITE_ID,"method":method,"start_date":START,"end_date":END,"max_results":"0"}
    q.update(p)
    u="https://openapi.baidu.com/rest/2.0/tongji/report/getData?"+urllib.parse.urlencode(q)
    return json.loads(urllib.request.urlopen(urllib.request.Request(u),context=ssl_ctx,timeout=40).read())
def rows(d):
    r=d.get("result",{})
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
res={}
res["daily"]=rows(get("trend/time/a",gran="day",metrics="pv_count,visitor_count,new_visitor_count,avg_visit_time,bounce_ratio"))
res["new"]=rows(get("trend/time/a",gran="day",visitor="new",metrics="pv_count,visitor_count,avg_visit_time,bounce_ratio"))
res["old"]=rows(get("trend/time/a",gran="day",visitor="old",metrics="pv_count,visitor_count,avg_visit_time,bounce_ratio"))
res["toppage"]=rows(get("visit/toppage/a",metrics="pv_count,visitor_count,avg_visit_time,bounce_ratio"))[:15]
res["source"]=rows(get("source/all/a",metrics="pv_count,visitor_count,new_visitor_count"))[:10]
print(json.dumps(res,ensure_ascii=False,indent=2))
