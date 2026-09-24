#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
内容更新任务台账（飞书多维表）客户端 —— 唯一实现
==================================================
verify_secondary.py / release_stage.py / release_apply.py 都通过它读写台账，
**不要在脚本里再抄一份 lark-cli 调用**（字段名映射在 references/ledger.json）。

实测坑（2026-09-23）：
  ① `lark-cli base +record-list --format json` 返回的是**矩阵**，不是 items：
       data.data           = 按行排列的字段值数组
       data.record_id_list = 与行一一对应的 record_id
  ② select 字段创建时 key 是 `options`，**不是** `property`；且 `--dry-run` 不做校验
  ③ `+field-update` / `+field-delete` 需 `--yes`
  ④ 字段名 `QC 状态` **中间有空格**（改字段只改 ledger.json）
"""
import json
import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = json.load(open(os.path.join(HERE, "..", "references", "ledger.json"), encoding="utf-8"))
F = LEDGER["fields"]
LARK_BIN = os.path.expanduser("~/.workbuddy/binaries/node/cli-connector-packages/bin")


def lark(*args):
    """调 lark-cli（PATH 里临时挂上 CLI 目录）。返回 (ok, data|err)。"""
    env = dict(os.environ, PATH=LARK_BIN + os.pathsep + os.environ.get("PATH", ""))
    try:
        p = subprocess.run(["lark-cli", *args], capture_output=True, text=True,
                           env=env, timeout=180)
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"
    out = (p.stdout or "").strip()
    try:
        j = json.loads(out)
    except Exception:
        return False, out[:400] or (p.stderr or "")[-400:]
    return bool(j.get("ok")), j


def _rows():
    """→ (record_ids, 值矩阵)。失败返回 (None, 错误)。"""
    ok, j = lark("base", "+record-list", "--base-token", LEDGER["base_token"],
                 "--table-id", LEDGER["table_id"],
                 "--field-id", F["rid"], "--format", "json")
    if not ok:
        return None, j
    d = j.get("data") or {}
    return list(d.get("record_id_list") or []), list(d.get("data") or [])


def find_by_rid(rids):
    """按校对ID 找 record_id → (record_ids, 错误)。"""
    recs, rows = _rows()
    if recs is None:
        return [], rows
    want, out = set(rids), []
    for row, rec in zip(rows, recs):
        v = row[0] if isinstance(row, list) and row else row
        if isinstance(v, list):
            v = v[0] if v else None
        if v in want:
            out.append(rec)
    if not out:
        return [], f"台账里找不到 {sorted(want)}（台账共 {len(recs)} 条）"
    return out, None


def update_by_rid(rids, patch):
    """按校对ID 批量改字段 → (ok, resp)。patch 的 key 用 ledger.json 里的中文名。"""
    targets, err = find_by_rid(rids)
    if err:
        return False, err
    ok, j = lark("base", "+record-batch-update", "--base-token", LEDGER["base_token"],
                 "--table-id", LEDGER["table_id"],
                 "--json", json.dumps({"record_id_list": targets, "patch": patch},
                                      ensure_ascii=False))
    if ok:
        return True, f"已回写 {len(targets)} 条：{list(patch)}"
    return False, (j.get("error", {}) if isinstance(j, dict) else j)


def probe():
    """连通性自检 → (ok, 说明)。"""
    recs, rows = _rows()
    if recs is None:
        return False, rows
    return True, f"台账可读：{len(recs)} 条记录 · 表 {LEDGER['table_name']}"
