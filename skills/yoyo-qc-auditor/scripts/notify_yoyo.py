#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QC 告警通知 → 飞书私聊 Yoyo

用法：
  python3 notify_yoyo.py --level P0 --title "标题" --body "正文"
       [--task-id RUN-20260904-001] [--agent "A2 校验官"] [--no-log]

  # 从文件读正文（推荐，避免转义问题）
  python3 notify_yoyo.py --level P0 --title "..." --body-file /tmp/qc_body.md

行为：
  - P0 → 立即发送飞书私聊
  - P1 → 发送（当日汇总时可多次调用，幂等键按 task-id+title 去重）
  - P2 → 默认只登记台账不发送；加 --force 才发
  - 默认同时登记 QC 问题台账，加 --no-log 跳过
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
LARK = "/Users/yoyo/.workbuddy/binaries/node/cli-connector-packages/bin/lark-cli"
LOG_SCRIPT = os.path.join(
    os.path.dirname(HERE), "yoyo-agent-swarm", "scripts", "feishu_log.py"
)
YOYO_OPEN_ID = "ou_YOUR_OPENID"
PYTHON = "/Users/yoyo/.workbuddy/binaries/python/envs/default/bin/python"

os.environ["LARK_CLI_NO_PROXY"] = "1"

LEVEL_ICON = {"P0": "🔴", "P1": "🟡", "P2": "🟢"}
LEVEL_ACTION = {
    "P0": "立即阻断 · 需人工介入",
    "P1": "返工修复 · 当日闭环",
    "P2": "登记待办 · 周度清理",
}


def send_feishu(title, body, level, dedup_key=None):
    md = (
        f"**{LEVEL_ICON.get(level, '⚪')} QC 告警 · {level}｜{title}**\n\n"
        f"{body}\n\n"
        f"---\n"
        f"处置建议：{LEVEL_ACTION.get(level, '')}\n"
        f"时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    args = [LARK, "im", "+messages-send",
            "--user-id", YOYO_OPEN_ID,
            "--markdown", md,
            "--as", "bot"]
    if dedup_key:
        args += ["--idempotency-key", dedup_key[:64]]
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=40)
        ok = False
        try:
            ok = json.loads(r.stdout).get("ok", False)
        except Exception:
            pass
        return ok, r.stdout or r.stderr
    except subprocess.TimeoutExpired:
        return False, "TIMEOUT"


def log_to_feishu(level, title, body, task_id, agent, itype="其他"):
    if not os.path.exists(LOG_SCRIPT):
        return False, "feishu_log.py 不存在，跳过登记"
    qid = f"QC-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    data = {
        "问题ID": qid,
        "关联任务ID": task_id or "",
        "发现时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "所属Agent": agent or "",
        "问题类型": itype,
        "严重级别": level,
        "问题描述": title,
        "证据": body[:2000],
        "状态": "待处理",
        "是否已通知Yoyo": "是",
    }
    try:
        r = subprocess.run(
            [PYTHON, LOG_SCRIPT, "issue", "--json", json.dumps(data, ensure_ascii=False)],
            capture_output=True, text=True, timeout=60,
        )
        return r.returncode == 0, r.stdout[-500:] or r.stderr[-500:]
    except Exception as e:
        return False, str(e)


def main():
    ap = argparse.ArgumentParser(description="QC 告警通知 Yoyo")
    ap.add_argument("--level", required=True, choices=["P0", "P1", "P2"])
    ap.add_argument("--title", required=True)
    ap.add_argument("--body", default=None)
    ap.add_argument("--body-file", default=None)
    ap.add_argument("--task-id", default=None)
    ap.add_argument("--agent", default=None)
    ap.add_argument("--issue-type", default="其他")
    ap.add_argument("--force", action="store_true", help="P2 也发送")
    ap.add_argument("--no-log", action="store_true", help="不登记台账")
    args = ap.parse_args()

    body = args.body or ""
    if args.body_file:
        with open(args.body_file, "r", encoding="utf-8") as f:
            body = f.read()
    if not body:
        sys.exit("[ERR] 需要 --body 或 --body-file")

    should_send = args.level in ("P0", "P1") or args.force

    sent = False
    if should_send:
        dedup = f"{args.task_id or 'na'}|{args.level}|{args.title}"[:64]
        ok, msg = send_feishu(args.title, body, args.level, dedup)
        sent = ok
        print(("[OK] 已通知 Yoyo" if ok else f"[ERR] 通知失败: {msg[:400]}"))
    else:
        print("[SKIP] P2 仅登记台账，未发送（加 --force 强制发送）")

    if not args.no_log:
        ok, msg = log_to_feishu(args.level, args.title, body,
                                args.task_id, args.agent, args.issue_type)
        print(("[OK] 已登记 QC 问题台账" if ok else f"[ERR] 登记失败: {msg[:400]}"))

    sys.exit(0 if (should_send and sent) or not should_send else 1)


if __name__ == "__main__":
    main()
