#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""归档库只保留「多维表格」类型，删除其余（文件/文档/电子表格等）。"""
import os, json, subprocess

LARK = os.environ.get(
    "LARK_CLI_BIN",
    "/Users/yoyo/.workbuddy/binaries/node/versions/22.22.2/bin/lark-cli",
)
BASE = "LZnDbQeqbaxZWasWuRjcOTH6nTf"
T = "tblfupBsZAesoWPx"

def env():
    e = dict(os.environ)
    e["LARK_CLI_NO_PROXY"] = "1"
    return e

def call(args):
    r = subprocess.run([LARK] + args, capture_output=True, text=True, env=env())
    out = r.stdout.strip()
    try:
        return json.loads(out)
    except Exception:
        return {"_raw": out, "_err": r.stderr}

# 1) 拉全量记录
ids_to_delete = []
kept = 0
pt = ""
page = 0
while True:
    url = f"/open-apis/bitable/v1/apps/{BASE}/tables/{T}/records?page_size=100"
    if pt:
        url += "&page_token=" + pt
    d = call(["api", "GET", url, "--as", "bot"]).get("data") or {}
    items = d.get("items") or []
    for it in items:
        fv = it.get("fields", {})
        if fv.get("格式") == "多维表格":
            kept += 1
        else:
            ids_to_delete.append(it["record_id"])
    pt = d.get("page_token", "")
    page += 1
    print(f"[scan] page={page} items={len(items)} kept={kept} todel={len(ids_to_delete)}", flush=True)
    if not pt:
        break
    if page > 200:
        break

print(f"[scan] 完成：{kept} 条多维表格 + {len(ids_to_delete)} 条待删", flush=True)

# 2) 批量删除（每批 50，实时进度）
done = 0
for i in range(0, len(ids_to_delete), 50):
    batch = ids_to_delete[i:i+50]
    res = call(["api", "POST",
                f"/open-apis/bitable/v1/apps/{BASE}/tables/{T}/records/batch_delete",
                "--data", json.dumps({"records": batch}), "--as", "bot"])
    if res.get("code") == 0 or "data" in res:
        done += len(batch)
    else:
        print("[warn] batch failed:", res.get("_raw", "")[:200], flush=True)
    print(f"[del] {done}/{len(ids_to_delete)}", flush=True)
print(f"[done] 已删除 {done} 条，保留 {kept} 条多维表格", flush=True)
