#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Agent Swarm 工作日志 → 飞书多维表 落库脚本

用法：
  # 写一条运行总览
  python3 feishu_log.py run --json '{"任务名称":"...", "状态":"完成", ...}'

  # 写一条 QC 问题
  python3 feishu_log.py issue --json '{"问题类型":"静默失败", ...}'

  # 更新已有记录
  python3 feishu_log.py update --table run --record-id recXXX --json '{"状态":"已完成"}'

  # 查询
  python3 feishu_log.py list --table run --limit 20

配置文件：同目录 config.json（含 base_token / table_id）
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "config.json")
LARK = "/Users/yoyo/.workbuddy/binaries/node/cli-connector-packages/bin/lark-cli"

os.environ["LARK_CLI_NO_PROXY"] = "1"


def load_config():
    if not os.path.exists(CONFIG_PATH):
        sys.exit(f"[ERR] 配置文件不存在: {CONFIG_PATH}\n请先运行建表流程并生成 config.json")
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def lark(args, timeout=40):
    """执行 lark-cli 命令，返回 (ok, stdout, stderr)

    注意：lark-cli 在 API 返回业务错误时 returncode 仍为 0，
    因此不能只看 returncode，必须解析输出 JSON 的 ok 字段，
    否则会出现「看着成功但数据没落库」的静默失败。
    """
    try:
        r = subprocess.run([LARK] + args, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, "", "TIMEOUT"
    out = (r.stdout or "").strip()
    if r.returncode != 0:
        return False, out, r.stderr or ""
    # 尝试解析 JSON 输出，校验业务层 ok
    if out.startswith("{"):
        try:
            j = json.loads(out)
            if "ok" in j and j.get("ok") is not True:
                err = j.get("error", {})
                msg = err.get("message", "") if isinstance(err, dict) else str(err)
                hint = err.get("hint", "") if isinstance(err, dict) else ""
                return False, out, f"[{err.get('code', '?')}] {msg} {hint}".strip()
        except (ValueError, AttributeError):
            pass
    return True, out, r.stderr or ""


def normalize_datetime_fields(data):
    """日期/日期时间字段转成毫秒时间戳，供飞书写入"""
    ts_fields = {}
    for k, v in list(data.items()):
        if not isinstance(v, str):
            continue
        s = v.strip()
        # 尝试解析 yyyy-mm-dd HH:MM:SS / yyyy-mm-dd HH:MM / yyyy-mm-dd
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(s, fmt)
                ts_fields[k] = int(dt.timestamp() * 1000)
                break
            except ValueError:
                continue
    data.update(ts_fields)
    return data


def upsert(cfg, table_key, data, record_id=None):
    table_id = cfg["tables"][table_key]["table_id"]
    base_token = cfg["base_token"]
    data = normalize_datetime_fields(dict(data))
    args = ["base", "+record-upsert",
            "--base-token", base_token,
            "--table-id", table_id,
            "--json", json.dumps(data, ensure_ascii=False),
            "--as", "bot"]
    if record_id:
        args += ["--record-id", record_id]
    ok, out, err = lark(args)
    return ok, out or err


def list_records(cfg, table_key, limit=20):
    table_id = cfg["tables"][table_key]["table_id"]
    ok, out, err = lark(["base", "+record-list",
                         "--base-token", cfg["base_token"],
                         "--table-id", table_id,
                         "--page-size", str(limit),
                         "--as", "bot"])
    print(out or err)
    return ok


def main():
    ap = argparse.ArgumentParser(description="Agent Swarm 飞书工作日志")
    ap.add_argument("action", choices=["run", "issue", "update", "list"])
    ap.add_argument("--table", default=None, help="update/list 时指定 run 或 issue")
    ap.add_argument("--json", default=None, help="JSON 字符串数据")
    ap.add_argument("--record-id", default=None)
    ap.add_argument("--limit", type=int, default=20)
    args = ap.parse_args()

    cfg = load_config()

    if args.action == "list":
        key = args.table or "run"
        sys.exit(0 if list_records(cfg, key, args.limit) else 1)

    if not args.json:
        sys.exit("[ERR] 需要 --json 参数")

    try:
        data = json.loads(args.json)
    except json.JSONDecodeError as e:
        sys.exit(f"[ERR] JSON 解析失败: {e}")

    if args.action == "run":
        table_key, rid = "run", args.record_id
    elif args.action == "issue":
        table_key, rid = "issue", args.record_id
    else:  # update
        table_key = args.table or "run"
        rid = args.record_id
        if not rid:
            sys.exit("[ERR] update 需要 --record-id")

    ok, msg = upsert(cfg, table_key, data, rid)
    print(msg)
    if ok:
        print(f"[OK] 已写入「{cfg['tables'][table_key]['name']}」")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
