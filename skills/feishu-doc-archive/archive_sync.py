#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
飞书文档归档助理 — 引擎脚本
功能：
  - setup   首次建库/建表/建字段（幂等）
  - sync    自动同步飞书云文档新建项到归档库（按创建时间增量）
  - add     手动归档一个文档链接（自动解析名称/格式/创建时间/所有人）
  - list    查看当前归档
  - resolve-names  若应用已开通 contact 权限，回填所有人真实姓名

依赖：lark-cli（已配置飞书应用）
"""

import os
import sys
import json
import time
import subprocess

# ---- 路径与配置 ----
SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
LARK = os.environ.get(
    "LARK_CLI_BIN",
    "/Users/yoyo/.workbuddy/binaries/node/versions/22.22.2/bin/lark-cli",
)
CONFIG_PATH = os.path.join(SKILL_DIR, "config.json")

# 默认归档库（首次 setup 后写入 config.json，可手动覆盖）
DEFAULT_CONFIG = {
    "base_token": "LZnDbQeqbaxZWasWuRjcOTH6nTf",
    "table_id": "tblfupBsZAesoWPx",
    "last_sync_ts": 0,          # 上次同步到的 unix 时间戳（增量游标）
    "name_cache": {},           # openid -> 姓名 本地缓存
}

# 文档类型 -> 格式标签
TYPE_MAP = {
    "doc": "文档",
    "docx": "文档",
    "bitable": "多维表格",
    "sheet": "电子表格",
    "mindnote": "思维笔记",
    "slide": "幻灯片",
    "file": "文件",
    "folder": "文件夹",
}
# 自动同步默认跳过的类型（文件夹不是"文档"）
SKIP_TYPES = {"folder"}

AUTO_PURPOSE = "（自动同步·待补充）"


def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        # 合并默认值
        for k, v in DEFAULT_CONFIG.items():
            cfg.setdefault(k, v)
        return cfg
    return dict(DEFAULT_CONFIG)


def save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def run_lark(args, data=None, timeout=40):
    """调用 lark-cli，返回解析后的 dict。出错抛异常。"""
    env = dict(os.environ)
    env["LARK_CLI_NO_PROXY"] = "1"
    cmd = [LARK] + args + ["--as", "bot"]
    if data is not None:
        cmd += ["--json", json.dumps(data, ensure_ascii=False)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        raise RuntimeError("lark-cli 调用超时")
    out = (r.stdout or "").strip()
    if not out:
        if r.returncode != 0:
            raise RuntimeError("lark-cli 无输出，stderr=" + (r.stderr or "")[:300])
        return {}
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        # 兼容带提示文本的输出，截取首个 JSON 对象
        start = out.find("{")
        if start >= 0:
            try:
                return json.loads(out[start:])
            except Exception:
                pass
        raise RuntimeError("无法解析 lark-cli 输出: " + out[:300])


def ensure_base(cfg):
    """若无 base_token 则创建；返回 base_token。"""
    if cfg.get("base_token"):
        return cfg["base_token"]
    res = run_lark(["base", "+base-create", "--name", "文档归档库",
                    "--time-zone", "Asia/Shanghai"])
    token = res["data"]["base"]["base_token"]
    # 授权邱月（cli 用户）管理员
    uid = "ou_YOUR_OPENID"
    try:
        run_lark(["api", "POST", f"/open-apis/drive/v1/permissions/{token}/members?type=bitable",
                  "--data", json.dumps({"member_id": uid, "member_type": "openid",
                                        "perm": "full_access"})])
    except Exception as e:
        print("[warn] 授权失败（可忽略，手动在网页端分享）:", e)
    cfg["base_token"] = token
    save_config(cfg)
    return token


def ensure_schema(cfg):
    """确保表与字段存在。返回 table_id。"""
    base = ensure_base(cfg)
    table_id = cfg.get("table_id")
    if not table_id:
        tables = run_lark(["base", "+table-list", "--base-token", base])
        table_id = tables["data"]["tables"][0]["id"]
        cfg["table_id"] = table_id
        save_config(cfg)

    # 现有字段
    fl = run_lark(["base", "+field-list", "--base-token", base, "--table-id", table_id])
    fields = {f["name"]: f for f in fl["data"]["fields"]}

    # 1) 主字段改名 文本 -> 文档名称
    if "文档名称" not in fields and "文本" in fields:
        run_lark(["base", "+field-update", "--base-token", base, "--table-id", table_id,
                  "--field-id", fields["文本"]["id"],
                  "--json", json.dumps({"name": "文档名称", "type": "text",
                                        "style": {"type": "plain"}}), "--yes"])
        fields["文档名称"] = fields.pop("文本")

    # 2) 删除无用默认字段（日期/附件/单选）
    for nm in ("日期", "附件", "单选"):
        if nm in fields:
            run_lark(["base", "+field-delete", "--base-token", base, "--table-id", table_id,
                      "--field-id", fields[nm]["id"], "--yes"])
            del fields[nm]

    # 3) 创建所需字段
    want = {
        "文档链接": {"name": "文档链接", "type": "text", "style": {"type": "plain"}},
        "用途": {"name": "用途", "type": "text", "style": {"type": "plain"}},
        "格式": {"name": "格式", "type": "select", "multiple": False,
                 "options": [{"name": v} for v in TYPE_MAP.values()]},
        "创建时间": {"name": "创建时间", "type": "datetime",
                     "style": {"format": "yyyy/MM/dd HH:mm"}},
        "所有人": {"name": "所有人", "type": "text", "style": {"type": "plain"}},
    }
    for nm, spec in want.items():
        if nm not in fields:
            run_lark(["base", "+field-create", "--base-token", base, "--table-id", table_id,
                      "--json", json.dumps(spec)])
            fields[nm] = spec
    return table_id


def resolve_owner(openid, cfg):
    """openid -> 姓名；优先本地缓存，其次尝试 contact API，失败回退 openid。"""
    if not openid:
        return "（未知）"
    if openid in cfg.get("name_cache", {}):
        return cfg["name_cache"][openid]
    # 尝试 contact API（需应用开通 contact:user.base:read）
    try:
        res = run_lark(["api", "GET",
                        f"/open-apis/contact/v3/users/{openid}?user_id_type=open_id"])
        name = res.get("data", {}).get("user", {}).get("name")
        if name:
            cfg.setdefault("name_cache", {})[openid] = name
            save_config(cfg)
            return name
    except Exception:
        # 解析失败（如缺权限）：内存缓存 openid，避免同 owner 重复请求拖慢批量同步
        cfg.setdefault("name_cache", {})[openid] = openid
        return openid
    # 未开通权限：回退 openid（保持可去重）
    return openid


def get_drive_files(limit=100, max_pages=100):
    """拉取飞书云文档（按创建时间倒序）。返回 list[dict]。"""
    files = []
    page_token = ""
    page = 0
    while page < max_pages:
        url = "/open-apis/drive/v1/files?order_by=created_time&order=desc&page_size=50"
        if page_token:
            url += f"&page_token={page_token}"
        res = run_lark(["api", "GET", url])
        data = res.get("data", {})
        files.extend(data.get("files", []))
        page_token = data.get("page_token", "")
        if not page_token:
            break
        page += 1
        if limit and len(files) >= limit:
            break
    return files[:limit] if limit else files


def _items(res):
    """从 records API 响应安全提取 items 列表（data 可能为 null）。"""
    return ((res.get("data") or {}).get("items") or [])


def list_archive_urls(base, table_id):
    """返回归档库中已有文档链接集合（用于去重）。用 records 原始 API 读取。

    注意：飞书该接口在带 page_token 时不推进（始终返回首 500 条 + 同一 token），
    因此必须检测 token 不推进即退出，否则会无限循环（定时任务挂死）。
    """
    urls = set()
    page_token = ""
    seen_tokens = set()
    while True:
        url = f"/open-apis/bitable/v1/apps/{base}/tables/{table_id}/records?page_size=100"
        if page_token:
            url += f"&page_token={page_token}"
        res = run_lark(["api", "GET", url])
        data = res.get("data") or {}
        for rec in _items(res):
            fv = rec.get("fields", {})
            link = fv.get("文档链接")
            if link:
                urls.add(link)
        nxt = data.get("page_token", "")
        # 防死循环：token 为空或重复（接口不推进）即退出
        if not nxt or nxt in seen_tokens:
            break
        seen_tokens.add(nxt)
        page_token = nxt
    return urls


def ts_to_str(ts):
    return time.strftime("%Y/%m/%d %H:%M", time.localtime(int(ts)))


def dt_ms(ts):
    """创建时间转飞书 datetime 字段值（毫秒时间戳）；非法返回 None。"""
    try:
        ts = int(ts)
    except Exception:
        return None
    return ts * 1000 if ts > 0 else None


def upsert_record(base, table_id, rec):
    run_lark(["base", "+record-upsert", "--base-token", base, "--table-id", table_id,
              "--json", json.dumps(rec, ensure_ascii=False)])


def batch_create_records(base, table_id, recs, chunk=100):
    """批量新建记录（每批最多 100 条），大幅减少 API 调用。"""
    n = 0
    for i in range(0, len(recs), chunk):
        batch = recs[i:i + chunk]
        run_lark(["api", "POST",
                  f"/open-apis/bitable/v1/apps/{base}/tables/{table_id}/records/batch_create",
                  "--data", json.dumps({"records": [{"fields": r} for r in batch]},
                                       ensure_ascii=False)])
        n += len(batch)
    return n


def cmd_setup(cfg):
    tid = ensure_schema(cfg)
    print(f"[ok] 归档库就绪 base={cfg['base_token']} table={tid}")


def cmd_sync(cfg, backfill=False):
    base = cfg["base_token"]
    table_id = ensure_schema(cfg)
    last = int(cfg.get("last_sync_ts", 0))
    # 首次运行：默认不回填历史，设游标为当前时间，仅归档此后新建项
    if not last and not backfill:
        cfg["last_sync_ts"] = int(time.time())
        save_config(cfg)
        print("[info] 首次同步：已设增量游标为当前时间，仅归档此后新建的文档（历史不回填）。")
        print("       如需把云空间已有文档一次性归档，运行：archive_sync.py sync --backfill")
        return
    if backfill:
        last = 0
        print("[info] 执行历史回填：将归档云空间全部已有文档（忽略增量游标）。")
    files = get_drive_files(limit=100000 if backfill else 100)
    existing = list_archive_urls(base, table_id)

    added = 0
    newest_ts = last
    new_recs = []
    for f in files:
        cts = int(f.get("created_time", 0))
        if last and cts <= last:
            continue
        ftype = f.get("type", "")
        # 仅归档「多维表格」，其余（文档/文件/电子表格/思维笔记/幻灯片等）跳过
        if ftype != "bitable":
            continue
        url = f.get("url", "")
        if not url or url in existing:
            continue
        rec = {
            "文档名称": f.get("name", "（未命名）"),
            "文档链接": url,
            "用途": AUTO_PURPOSE,
            "格式": TYPE_MAP.get(ftype, "其他"),
            "所有人": resolve_owner(f.get("owner_id"), cfg),
        }
        m = dt_ms(cts)
        if m is not None:
            rec["创建时间"] = m
        new_recs.append(rec)
        existing.add(url)
        added += 1
        newest_ts = max(newest_ts, cts)

    if new_recs:
        batch_create_records(base, table_id, new_recs)

    if added:
        cfg["last_sync_ts"] = newest_ts
        save_config(cfg)
    print(f"[ok] 自动同步完成：新增 {added} 条（增量游标 {ts_to_str(newest_ts) if newest_ts else '—'}）")


def cmd_add(cfg, url, purpose="", owner=""):
    base = cfg["base_token"]
    table_id = ensure_schema(cfg)
    token = extract_token(url)
    meta = None
    if token:
        try:
            res = run_lark(["api", "GET", f"/open-apis/drive/v1/files/{token}"])
            meta = res.get("data", {}).get("file") or res.get("data", {})
        except Exception:
            meta = None
    if meta:
        name = meta.get("name", "（未命名）")
        ftype = meta.get("type", "")
        cts = int(meta.get("created_time", time.time()))
        owner_id = meta.get("owner_id", "")
    else:
        # 退路：从云文档列表按 token 匹配
        hit = next((x for x in get_drive_files(100) if extract_token(x.get("url", "")) == token), None)
        if hit:
            name = hit.get("name", "（未命名）")
            ftype = hit.get("type", "")
            cts = int(hit.get("created_time", time.time()))
            owner_id = hit.get("owner_id", "")
        else:
            name = url.split("/")[-1] or "（未命名）"
            ftype = ""
            cts = int(time.time())
            owner_id = ""
    rec = {
        "文档名称": name,
        "文档链接": url,
        "用途": purpose or AUTO_PURPOSE,
        "格式": TYPE_MAP.get(ftype, "其他"),
        "所有人": owner or resolve_owner(owner_id, cfg),
    }
    # 仅支持归档「多维表格」，非多维表格链接直接跳过
    if ftype and ftype != "bitable":
        print(f"[warn] 仅支持归档「多维表格」，当前链接类型：{TYPE_MAP.get(ftype, '其他')}，已跳过：{url}")
        return
    m = dt_ms(cts)
    if m is not None:
        rec["创建时间"] = m
    upsert_record(base, table_id, rec)
    print(f"[ok] 已归档：{name}（{rec['格式']}）")


def cmd_list(cfg, n=20):
    base = cfg["base_token"]
    table_id = cfg["table_id"]
    res = run_lark(["api", "GET",
                    f"/open-apis/bitable/v1/apps/{base}/tables/{table_id}/records?page_size=100"])
    recs = _items(res)
    total = res.get("data", {}).get("total", len(recs))
    print(f"共 {total} 条，显示前 {min(n, len(recs))} 条：")
    for r in recs[:n]:
        fv = r.get("fields", {})
        ct = fv.get("创建时间")
        if isinstance(ct, (int, float)):
            ct = ts_to_str(ct / 1000) if ct > 1e11 else ts_to_str(ct)
        print(f"- {fv.get('文档名称','?')} | {fv.get('格式','?')} | {fv.get('所有人','?')} | {ct} | {fv.get('文档链接','')}")


def extract_token(url):
    from urllib.parse import urlparse
    seg = [s for s in urlparse(url).path.split("/") if s]
    return seg[-1] if seg else ""


def cmd_resolve_names(cfg):
    """若应用已开通 contact 权限，回填所有人真实姓名。"""
    base = cfg["base_token"]
    table_id = cfg["table_id"]
    res = run_lark(["api", "GET",
                    f"/open-apis/bitable/v1/apps/{base}/tables/{table_id}/records?page_size=100"])
    recs = _items(res)
    done = 0
    for r in recs:
        fv = r.get("fields", {})
        owner = fv.get("所有人", "")
        if owner and owner.startswith("ou_"):
            name = resolve_owner(owner, cfg)
            if name != owner:
                fv["所有人"] = name
                upsert_record(base, table_id, fv)
                done += 1
    print(f"[ok] 回填真实姓名 {done} 条")


def main():
    cfg = load_config()
    args = sys.argv[1:]
    if not args or args[0] == "setup":
        cmd_setup(cfg)
    elif args[0] == "sync":
        backfill = "--backfill" in args
        cmd_sync(cfg, backfill=backfill)
    elif args[0] == "add":
        # archive_sync.py add --url <url> [--purpose <用途>] [--owner <所有人>]
        url = purpose = owner = ""
        i = 1
        while i < len(args):
            if args[i] == "--url":
                url = args[i + 1]; i += 2
            elif args[i] == "--purpose":
                purpose = args[i + 1]; i += 2
            elif args[i] == "--owner":
                owner = args[i + 1]; i += 2
            else:
                i += 1
        if not url:
            print("用法: archive_sync.py add --url <文档链接> [--purpose <用途>] [--owner <所有人>]")
            sys.exit(1)
        cmd_add(cfg, url, purpose, owner)
    elif args[0] == "list":
        n = int(args[1]) if len(args) > 1 and args[1].isdigit() else 20
        cmd_list(cfg, n)
    elif args[0] == "resolve-names":
        cmd_resolve_names(cfg)
    else:
        print("未知命令:", args[0])
        sys.exit(1)


if __name__ == "__main__":
    main()
