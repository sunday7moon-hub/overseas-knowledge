#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
发布确认通知 · 通道层（唯一实现）
==================================
把「待上线确认」通知送到 Yoyo 手上。通道可插拔，配置在
`references/notify.json`（收件人 / webhook / SendKey 的唯一真相源）。

通道：
  feishu      lark-cli 机器人私聊（已启用，2026-09-23 验证可用）
  wecom_bot   企业微信群机器人 webhook（需 Yoyo 填 webhook 后启用）
  serverchan  Server酱 → 微信服务号推送（需 Yoyo 填 SendKey 后启用）

用法：
  python3 notify_channels.py --probe                     # 看当前哪些通道可用
  python3 notify_channels.py --title "..." --body-file /tmp/body.md
  python3 notify_channels.py --title "..." --body-file ... --json-out /tmp/notify.json
退出码：0 = 至少一个通道发送成功；1 = 全部失败。
⚠️ 通道层不管通知内容 —— 内容由 notify_release.py 组装（各司其职，别混）。
"""
import argparse
import json
import os
import subprocess
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CONF_PATH = os.path.join(HERE, "..", "references", "notify.json")
CONF = json.load(open(CONF_PATH, encoding="utf-8"))
LARK_BIN_DIR = os.path.expanduser(CONF.get("lark_bin_dir", ""))


def _run(cmd, timeout=40):
    env = dict(os.environ, LARK_CLI_NO_PROXY="1")
    if LARK_BIN_DIR:
        env["PATH"] = LARK_BIN_DIR + os.pathsep + env.get("PATH", "")
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=timeout)
        return p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip()
    except subprocess.TimeoutExpired:
        return -1, "", "TIMEOUT"
    except FileNotFoundError as e:
        return -1, "", f"命令不存在：{e}"


def send_feishu(md, title):
    cfg = CONF["channels"]["feishu"]
    if not cfg.get("enabled"):
        return False, "未启用（notify.json: channels.feishu.enabled=false）"
    open_id = CONF["recipient"]["feishu_open_id"]
    if not open_id:
        return False, "缺 recipient.feishu_open_id"
    rc, out, err = _run(["lark-cli", "im", "+messages-send",
                         "--user-id", open_id, "--markdown", md, "--as", "bot"])
    try:
        j = json.loads(out)
        return bool(j.get("ok")), (j if j.get("ok") else str(j)[:300])
    except Exception:
        return False, (out or err)[:300] or f"rc={rc}"


def send_wecom_bot(md, title):
    cfg = CONF["channels"]["wecom_bot"]
    hook = (cfg.get("webhook") or "").strip()
    if not cfg.get("enabled"):
        return False, "未启用（notify.json: channels.wecom_bot.enabled=false）"
    if not hook:
        return False, "已启用但 webhook 为空 —— 请填企业微信群机器人 Webhook 地址"
    payload = json.dumps({"msgtype": "markdown", "markdown": {"content": md}},
                         ensure_ascii=False).encode()
    try:
        req = urllib.request.Request(hook, data=payload,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            j = json.loads(r.read().decode("utf-8", "ignore"))
        return j.get("errcode") == 0, j
    except Exception as e:
        return False, f"{type(e).__name__}: {str(e)[:200]}"


def send_serverchan(md, title):
    cfg = CONF["channels"]["serverchan"]
    key = (cfg.get("sendkey") or "").strip()
    if not cfg.get("enabled"):
        return False, "未启用（notify.json: channels.serverchan.enabled=false）"
    if not key:
        return False, "已启用但 sendkey 为空 —— 请填 Server酱 SendKey"
    url = f"https://sctapi.ftqq.com/{key}.send"
    import urllib.parse
    body = urllib.parse.urlencode({"title": title, "desp": md}).encode()
    try:
        req = urllib.request.Request(url, data=body,
                                     headers={"Content-Type": "application/x-www-form-urlencoded"})
        with urllib.request.urlopen(req, timeout=30) as r:
            j = json.loads(r.read().decode("utf-8", "ignore"))
        return j.get("code") == 0, j
    except Exception as e:
        return False, f"{type(e).__name__}: {str(e)[:200]}"


SENDERS = {"feishu": send_feishu, "wecom_bot": send_wecom_bot, "serverchan": send_serverchan}


def active_channels():
    return [k for k, f in SENDERS.items() if CONF["channels"][k].get("enabled")]


def send(title, md):
    """逐通道发送 → [dict(channel, ok, detail)]。任一成功即整体成功。"""
    results = []
    for name, fn in SENDERS.items():
        if not CONF["channels"][name].get("enabled"):
            continue
        ok, detail = fn(md, title)
        results.append(dict(channel=name, ok=ok,
                            detail=(detail if isinstance(detail, str) else "已送达")))
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--title", default=None)
    ap.add_argument("--body-file", default=None)
    ap.add_argument("--body", default=None)
    ap.add_argument("--probe", action="store_true", help="只看通道可用性，不发送")
    ap.add_argument("--json-out", default=None)
    a = ap.parse_args()

    if a.probe:
        print(f"通知通道配置：{CONF_PATH}")
        print(f"收件人：{CONF['recipient']['name']}")
        for k, c in CONF["channels"].items():
            mark = "✅ 已启用" if c.get("enabled") else "⛔ 未启用"
            extra = ""
            if k == "wecom_bot":
                extra = "（webhook 已填）" if (c.get("webhook") or "").strip() else "（webhook 为空 ← 待填）"
            if k == "serverchan":
                extra = "（sendkey 已填）" if (c.get("sendkey") or "").strip() else "（sendkey 为空 ← 待填）"
            print(f"  {mark}  {k:<11} {c.get('kind','')} {extra}")
        print(f"生效通道：{active_channels() or '（无 —— 通知发不出去，请先配通道）'}")
        print(f"暂存有效期：{CONF.get('release_ttl_days')} 天")
        return 0

    md = a.body or ""
    if a.body_file:
        md = open(a.body_file, encoding="utf-8").read()
    if not md:
        sys.exit("[ERR] 需要 --body 或 --body-file")
    res = send(a.title or "通知", md)
    if not res:
        print("⛔ 没有任何通道启用 —— 未发送")
        return 1
    for r in res:
        print(("✅ " if r["ok"] else "❌ ") + f"{r['channel']} → "
              + (r["detail"] if isinstance(r["detail"], str) else "已送达"))
    if a.json_out:
        json.dump(dict(sent=any(r["ok"] for r in res), results=res),
                  open(a.json_out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return 0 if any(r["ok"] for r in res) else 1


if __name__ == "__main__":
    sys.exit(main())
