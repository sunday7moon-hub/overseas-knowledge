#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给归档库每条记录填充「用途简介」与「权限范围」两个字段。
- 用途简介：读取该多维表格的表结构（字段），结合名称生成一句话简介。
- 权限范围：读取该多维表格的协作者权限列表，映射为可读文本。
"""
import os, json, subprocess, sys

LARK = os.environ.get(
    "LARK_CLI_BIN",
    "/Users/yoyo/.workbuddy/binaries/node/versions/22.22.2/bin/lark-cli",
)
BASE = "LZnDbQeqbaxZWasWuRjcOTH6nTf"   # 归档库自身
TABLE = "tblfupBsZAesoWPx"

# 已知 openid -> 姓名（无 contact 权限时的兜底映射）
KNOWN = {"ou_YOUR_OPENID": "邱月"}

def env():
    e = dict(os.environ); e["LARK_CLI_NO_PROXY"] = "1"; return e

def call(method, path, params=None, data=None):
    args = [LARK, "api", method, path, "--as", "bot"]
    if params:
        args += ["--params", json.dumps(params)]
    if data is not None:
        args += ["--data", json.dumps(data, ensure_ascii=False)]
    r = subprocess.run(args, capture_output=True, text=True, env=env())
    out = r.stdout.strip()
    try:
        return json.loads(out)
    except Exception:
        return {"_raw": out, "_err": r.stderr}

def extract_token(url):
    # 取 URL 最后一段路径（飞书 base/app token）
    s = url.rstrip("/")
    return s.split("/")[-1] if s else ""

def get_items():
    d = call("GET", f"/open-apis/bitable/v1/apps/{BASE}/tables/{TABLE}/records?page_size=100").get("data") or {}
    return d.get("items") or []

def gen_intro(name, fields, table_name):
    if not fields:
        return f"{name} — 飞书多维表格（暂无可读字段信息）。"
    fnames = [f.get("field_name", "?") for f in fields[:8]]
    tail = "…" if len(fields) > 8 else ""
    return (f"{name}：主表「{table_name}」含 {len(fields)} 个字段"
            f"（{', '.join(fnames)}{tail}），用于业务数据归集与管理。")

def gen_perm(members):
    if members is None:
        return "（暂无法读取协作者权限）"
    if not members:
        return "（无额外协作者，仅创建者）"
    parts = []
    for m in members:
        t = m.get("member_type"); mid = m.get("member_id"); p = m.get("perm")
        if t == "appid":
            label = "应用自身"
        elif t == "openid":
            label = KNOWN.get(mid, f"成员({mid})")
        elif t in ("tag", "department"):
            label = f"部门/标签({mid})"
        elif t == "chat":
            label = f"群({mid})"
        else:
            label = f"{t}({mid})"
        parts.append(f"{label}:{p}")
    return "；".join(parts)

def main():
    items = get_items()
    print(f"[info] 归档库共 {len(items)} 条，开始填充", flush=True)
    ok = 0
    for it in items:
        rid = it["record_id"]
        fv = it.get("fields", {})
        name = fv.get("文档名称", "")
        url = fv.get("文档链接", "")
        token = extract_token(url)
        if not token:
            print(f"[skip] 无链接: {name}", flush=True)
            continue
        # 1) 表结构
        fields = None; table_name = "数据表"
        tl = call("GET", f"/open-apis/bitable/v1/apps/{token}/tables").get("data") or {}
        tabs = tl.get("items") or []
        if tabs:
            table_name = tabs[0].get("name", "数据表")
            tid = tabs[0].get("table_id")
            fl = call("GET", f"/open-apis/bitable/v1/apps/{token}/tables/{tid}/fields").get("data") or {}
            fields = fl.get("items") or []
            print(f"  [dbg] {name}: tables_ok={tl.get('ok')} tabs={len(tabs)} fields={len(fields)}", flush=True)
        else:
            print(f"  [dbg] {name}: no tables, tl={str(tl)[:120]}", flush=True)
        # 2) 权限
        try:
            pl = call("GET", f"/open-apis/drive/v1/permissions/{token}/members",
                      params={"type": "bitable"}).get("data") or {}
            members = pl.get("items")
        except Exception:
            members = None
        intro = gen_intro(name, fields, table_name)
        perm = gen_perm(members)
        res = call("PUT", f"/open-apis/bitable/v1/apps/{BASE}/tables/{TABLE}/records/{rid}",
                   data={"fields": {"用途简介": intro, "权限范围": perm}})
        if res.get("code") == 0 or "data" in res:
            ok += 1
            print(f"[ok] {name} | 简介:{intro[:30]}… | 权限:{perm[:40]}", flush=True)
        else:
            print(f"[fail] {name}: {res.get('_raw','')[:120]}", flush=True)
    print(f"[done] 成功填充 {ok}/{len(items)} 条", flush=True)

if __name__ == "__main__":
    main()
