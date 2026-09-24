#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
入站指令闭环台账 —— 飞书多维表落库 / 续传扫描 / 投递回读校验

机制说明见 ../references/inbound-request-loop.md

用法：
  # 首次建表（写入 config.json 的 tables.inbound）
  python3 inbound_ledger.py init

  # 落一条请求（自动生成 REQ-YYYYMMDD-NN）
  python3 inbound_ledger.py add --json '{"客户":"慧思","角色":"运营","需求线":"慧思-卡片",\
      "原始诉求":"@巴蒂 出今天的日报","完成判据":"①内容已编排 ②已发目标群 ③链接可点 ④回执","优先级":"🟡P1"}'

  # 更新状态（按请求ID定位）
  python3 inbound_ledger.py update --request-id REQ-20260921-01 --json '{"状态":"已回执","回执消息ID":"om_xxx"}'

  # 断点续传扫描（任何会话启动第一步）
  python3 inbound_ledger.py pending

  # 投递回读校验（确认消息确实在群里）
  python3 inbound_ledger.py verify --chat-id oc_xxx --message-id om_xxx

  # 列全部
  python3 inbound_ledger.py list --limit 50

设计要点：
  * 「已生成」不是完成态；只有 已回执 / 已归档 / 已作废 才是终态。
  * pending 是断点续传的唯一入口，会话重启后先跑它。
  * 本脚本不依赖第三方库，任何 python3 均可运行。
"""
import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "config.json")
LARK = "/Users/yoyo/.workbuddy/binaries/node/cli-connector-packages/bin/lark-cli"

os.environ["LARK_CLI_NO_PROXY"] = "1"

TABLE_NAME = "客户交付台账"
OPEN_STATES = ["待接单", "已确认", "执行中", "待投递", "已投递", "阻塞", "返工"]
FINAL_STATES = ["已回执", "已归档", "已作废"]
STATUS_OPTIONS = ["待接单", "已确认", "执行中", "待投递", "已投递", "已回执", "阻塞", "返工", "已归档", "已作废"]
PRIORITY_OPTIONS = ["🔴P0", "🟡P1", "🟢P2"]

TEXT_FIELDS = ["请求ID", "客户", "角色", "需求线", "来源", "原始诉求", "完成判据",
               "阻塞原因", "产出", "回执消息ID", "更新时间"]
SELECT_FIELDS = [("状态", STATUS_OPTIONS), ("优先级", PRIORITY_OPTIONS)]


def field_payloads():
    """生成 field-create 用的字段定义

    实测（2026-09-21）：lark-cli 的 field-create 不接受 property 包装，
    单选项要写成顶层 options；type 也只认字符串判别值（"text"/"single_select"）。
    """
    out = [{"name": n, "type": "text"} for n in TEXT_FIELDS]
    out += [{"name": n, "type": "single_select",
             "options": [{"name": o} for o in opts]}
            for n, opts in SELECT_FIELDS]
    return out


def load_config():
    if not os.path.exists(CONFIG_PATH):
        sys.exit(f"[ERR] 配置文件不存在: {CONFIG_PATH}")
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def lark(args, timeout=40):
    """执行 lark-cli。returncode 为 0 但 ok=false 也算失败（防静默失败）。"""
    try:
        r = subprocess.run([LARK] + args, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, "", "TIMEOUT"
    out = (r.stdout or "").strip()
    if r.returncode != 0:
        return False, out, r.stderr or ""
    if out.startswith("{"):
        try:
            j = json.loads(out)
            if "ok" in j and j.get("ok") is not True:
                err = j.get("error", {})
                msg = err.get("message", "") if isinstance(err, dict) else str(err)
                return False, out, f"[{err.get('code', '?')}] {msg}".strip()
            if "code" in j and j.get("code") != 0:
                return False, out, f"[api {j.get('code')}] {j.get('msg', '')}".strip()
        except (ValueError, AttributeError):
            pass
    return True, out, r.stderr or ""


def table_id(cfg):
    t = cfg.get("tables", {}).get("inbound")
    if not t:
        sys.exit("[ERR] 尚未建表，请先运行: python3 inbound_ledger.py init")
    return t["table_id"]


def json_of(out):
    try:
        return json.loads(out)
    except ValueError:
        return {}


# ---------------------------------------------------------------- init
def do_init(cfg):
    """幂等建表：表存在则复用，字段缺失则补齐。"""
    base = cfg["base_token"]

    # 1. 找同名表
    tid = None
    ok, out, _ = lark(["base", "+table-get", "--base-token", base,
                       "--table-id", TABLE_NAME, "--as", "bot"])
    if ok:
        d = json_of(out).get("data", {})
        tid = (d.get("table") or {}).get("id") or d.get("table_id")
    if tid:
        print(f"[i] 复用已有表「{TABLE_NAME}」 {tid}")
    else:
        ok, out, err = lark(["base", "+table-create", "--base-token", base,
                             "--name", TABLE_NAME, "--as", "bot"])
        if not ok:
            sys.exit(f"[ERR] 建表失败: {err[-300:]}")
        d = json_of(out).get("data", {})
        tid = (d.get("table") or {}).get("id") or d.get("table_id")
        if not tid:
            sys.exit(f"[ERR] 未取到 table_id：{out[-400:]}")
        print(f"[+] 新建表「{TABLE_NAME}」 {tid}")

    # 2. 已有字段
    existing = {}
    ok, out, _ = lark(["base", "+field-list", "--base-token", base,
                       "--table-id", tid, "--as", "bot"])
    if ok:
        for f in json_of(out).get("data", {}).get("fields", []) or []:
            existing[f.get("name")] = f

    # 3. 补字段 / 补齐单选项
    added = fixed = 0
    for fp in field_payloads():
        cur = existing.get(fp["name"])
        if cur is None:
            ok, out, err = lark(["base", "+field-create", "--base-token", base,
                                 "--table-id", tid,
                                 "--json", json.dumps(fp, ensure_ascii=False),
                                 "--as", "bot"])
            if not ok:
                print(f"    [WARN] 字段「{fp['name']}」创建失败：{err[-160:]}")
            else:
                added += 1
            continue
        # 已存在：单选项数量不符则补齐（field-update 是 PUT 全量语义）
        if fp["type"] == "single_select":
            want = [o["name"] for o in fp["options"]]
            have = [o.get("name") for o in (cur.get("options") or [])]
            if want != have:
                payload = {"name": fp["name"], "type": "single_select",
                           "multiple": False, "options": fp["options"]}
                ok, out, err = lark(["base", "+field-update", "--base-token", base,
                                     "--table-id", tid, "--field-id", fp["name"],
                                     "--json", json.dumps(payload, ensure_ascii=False),
                                     "--yes", "--as", "bot"])
                if ok:
                    fixed += 1
                else:
                    print(f"    [WARN] 字段「{fp['name']}」选项补齐失败：{err[-160:]}")
    print(f"[OK] 字段齐备（新增 {added} 个，补齐选项 {fixed} 个）")

    cfg.setdefault("tables", {})["inbound"] = {
        "name": TABLE_NAME,
        "table_id": tid,
        "primary_field": "ID",
    }
    save_config(cfg)
    print(f"     base: {cfg.get('base_url', base)}")
    print(f"     下一步：python3 inbound_ledger.py add --json '{{...}}'")


# ---------------------------------------------------------------- add / update
def _next_request_id(cfg):
    today = datetime.now().strftime("%Y%m%d")
    mx = 0
    for rec in fetch_all(cfg):
        rid = str((rec.get("fields") or {}).get("请求ID", ""))
        m = re.match(rf"REQ-{today}-(\d+)$", rid)
        if m:
            mx = max(mx, int(m.group(1)))
    return f"REQ-{today}-{mx + 1:02d}"


def do_add(cfg, payload):
    payload = dict(payload)
    payload.setdefault("请求ID", _next_request_id(cfg))
    payload.setdefault("状态", "待接单")
    payload.setdefault("优先级", "🟡P1")
    payload["更新时间"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ok, out, err = lark(["base", "+record-upsert",
                         "--base-token", cfg["base_token"],
                         "--table-id", table_id(cfg),
                         "--json", json.dumps(payload, ensure_ascii=False),
                         "--as", "bot"])
    if not ok:
        sys.exit(f"[ERR] 落库失败: {err[-300:]}")
    print(f"[OK] 已落台账 {payload['请求ID']}｜{payload.get('客户', '-')}｜{payload.get('状态')}")
    print(f"     完成判据：{payload.get('完成判据', '(未填，DoD 缺失=不算完成)')}")
    return payload["请求ID"]


def do_update(cfg, request_id, payload):
    """按请求ID 更新：拉全表本地匹配（表体量小，比 filter DSL 更稳）"""
    rec_id = None
    for r in fetch_all(cfg, 200):
        if str((r.get("fields") or {}).get("请求ID", "")) == request_id:
            rec_id = r.get("record_id")
            break
    if not rec_id:
        sys.exit(f"[ERR] 未找到请求 {request_id}")
    payload = dict(payload)
    payload["更新时间"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ok, out, err = lark(["base", "+record-upsert",
                         "--base-token", cfg["base_token"],
                         "--table-id", table_id(cfg),
                         "--record-id", rec_id,
                         "--json", json.dumps(payload, ensure_ascii=False),
                         "--as", "bot"])
    if not ok:
        sys.exit(f"[ERR] 更新失败: {err[-300:]}")
    print(f"[OK] {request_id} → {payload.get('状态', '(未改状态)')}")


# ---------------------------------------------------------------- list / pending
def fetch_all(cfg, limit=200):
    """读全表。走原始 API 而非 +record-list：后者返回二维数组、拿不到 record_id，
    而更新记录必须用 record_id。"""
    path = (f"/open-apis/bitable/v1/apps/{cfg['base_token']}"
            f"/tables/{table_id(cfg)}/records")
    ok, out, err = lark(["api", "GET", path,
                         "--params", json.dumps({"page_size": limit}),
                         "--as", "bot"])
    if not ok:
        sys.exit(f"[ERR] 读取台账失败: {err[-300:]}")
    items = json_of(out).get("data", {}).get("items", []) or []
    return [{"record_id": it.get("record_id"), "fields": it.get("fields") or {}}
            for it in items]


def do_list(cfg, limit):
    recs = fetch_all(cfg, limit)
    if not recs:
        print("台账为空。")
        return
    for r in recs:
        f = r.get("fields") or {}
        print(f"{f.get('请求ID', '?'):<18} {f.get('状态', '?'):<6} {f.get('优先级', ''):<5} "
              f"{f.get('客户', '-'):<10} {(str(f.get('原始诉求', '')) or '')[:48]}")
    print(f"—— 共 {len(recs)} 条")


def do_pending(cfg):
    """断点续传扫描：会话启动第一步。"""
    recs = fetch_all(cfg)
    pend = [r for r in recs if (r.get("fields") or {}).get("状态") in OPEN_STATES]
    if not pend:
        print("[OK] 无未完成请求，可接新指令。")
        return
    print(f"⚠️ 发现 {len(pend)} 条未完成请求（断点续传优先处理）：\n")
    for r in pend:
        f = r.get("fields") or {}
        print(f"· {f.get('请求ID', '?')} [{f.get('状态')}] {f.get('优先级', '')} {f.get('客户', '-')}")
        print(f"  诉求：{str(f.get('原始诉求', ''))[:90]}")
        print(f"  判据：{str(f.get('完成判据', '(缺失)'))[:90]}")
        if f.get("阻塞原因"):
            print(f"  阻塞：{f['阻塞原因']}")
        print()


# ---------------------------------------------------------------- verify
def do_verify(chat_id, message_id):
    """投递回读校验：消息确实存在于群 → 才算「已投递」。"""
    ok, out, err = lark(["im", "+messages-mget", "--message-ids", message_id, "--as", "user"])
    if not ok:
        print(f"[FAIL] 回读失败，消息不可见：{err[-200:]}")
        sys.exit(1)
    j = json_of(out)
    msgs = j.get("data", {}).get("messages", []) or []
    if not msgs:
        print("[FAIL] 回读为空，视为未投递。")
        sys.exit(1)
    m = msgs[0]
    if chat_id and m.get("chat_id") != chat_id:
        print(f"[FAIL] 消息存在但不在目标群：{m.get('chat_id')}")
        sys.exit(1)
    if m.get("deleted"):
        print("[FAIL] 消息已被删除，视为未投递。")
        sys.exit(1)
    print(f"[OK] 投递校验通过：{message_id} 在群 {m.get('chat_id')}（{m.get('create_time')}）")


def main():
    ap = argparse.ArgumentParser(description="入站指令闭环台账")
    ap.add_argument("action", choices=["init", "add", "update", "list", "pending", "verify"])
    ap.add_argument("--json", default=None)
    ap.add_argument("--request-id", default=None)
    ap.add_argument("--chat-id", default=None)
    ap.add_argument("--message-id", default=None)
    ap.add_argument("--limit", type=int, default=50)
    a = ap.parse_args()

    cfg = load_config()

    if a.action == "init":
        do_init(cfg)
    elif a.action == "add":
        if not a.json:
            sys.exit("[ERR] add 需要 --json")
        do_add(cfg, json.loads(a.json))
    elif a.action == "update":
        if not (a.request_id and a.json):
            sys.exit("[ERR] update 需要 --request-id 与 --json")
        do_update(cfg, a.request_id, json.loads(a.json))
    elif a.action == "list":
        do_list(cfg, a.limit)
    elif a.action == "pending":
        do_pending(cfg)
    elif a.action == "verify":
        if not a.message_id:
            sys.exit("[ERR] verify 需要 --message-id")
        do_verify(a.chat_id, a.message_id)


if __name__ == "__main__":
    main()
