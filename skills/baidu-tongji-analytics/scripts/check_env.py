#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
百度统计技能 · 环境自检 / 入仓前凭据门禁
==========================================
一次性回答三个问题：

  ① 凭据可用吗？      —— secrets 是否齐全、access_token 是否活着、到期日
  ② 脚本干净吗？      —— 全目录扫描硬编码 token / client_secret（**入仓前必跑**）
  ③ 迁移完整吗？      —— 旧的散落脚本是否还在会话工作区（判据 G 易失资产）

用法：
    python3 check_env.py            # 人类可读
    python3 check_env.py --json     # 机器可读（给自动化/CI 用）
退出码：0 = 全绿；1 = 有问题（凭据失效 / 发现硬编码凭据）
"""

import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from _baidu_auth import (  # noqa: E402
    SECRETS_PATH, api_get, credential_status, parse_rows,
)

# 硬编码凭据特征：百度统计 token 形如 121.xxxx / 122.xxxx；本应用的 client 凭据前缀
SECRET_PAT = re.compile(
    r"(?:12[0-9]\.[A-Za-z0-9_\-]{25,}"      # access / refresh token 本体
    r"|XapchyEp[A-Za-z0-9]{8,}"              # client_secret 前缀
    r"|NjM0w46M[A-Za-z0-9]{8,})"             # client_id 前缀
)

# 判定 G：易失资产 —— 这些脚本若仍躺在会话工作区，说明迁移没做完
LEGACY_LOCATIONS = [
    "/Users/yoyo/WorkBuddy/2026-06-29-16-08-00",
]
LEGACY_SCRIPTS = [
    "baidu_dau.py", "baidu_wau.py", "baidu_window.py",
    "baidu_monthly_2026.py", "baidu_2026_extra.py", "baidu_week_article.py",
    "baidu_tongji_custom.py", "baidu_tongji_weekly.py",
]


def scan_hardcoded(root):
    """扫描目录下所有文本文件，找出硬编码凭据。返回 [(相对路径, 命中数, 样例)]。"""
    hits = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in ("__pycache__", ".git")]
        for fn in filenames:
            if not fn.endswith((".py", ".md", ".json", ".sh", ".txt", ".yaml", ".yml")):
                continue
            fp = os.path.join(dirpath, fn)
            try:
                text = open(fp, encoding="utf-8").read()
            except (UnicodeDecodeError, OSError):
                continue
            found = SECRET_PAT.findall(text)
            if found:
                sample = found[0][:14] + "…"
                hits.append((os.path.relpath(fp, root), len(found), sample))
    return hits


def check_legacy():
    left = []
    for base in LEGACY_LOCATIONS:
        for s in LEGACY_SCRIPTS:
            p = os.path.join(base, s)
            if os.path.exists(p):
                left.append(p)
    return left


def main():
    as_json = "--json" in sys.argv
    result = {"secrets": credential_status(), "hardcoded": [], "legacy_left": []}

    # ① 凭据
    st = result["secrets"]
    live = False
    if st.get("ok") and st.get("access_token_alive"):
        try:
            d = api_get("trend/time/a", "20260912", "20260914",
                        metrics="pv_count,visitor_count", gran="day")
            dates = parse_rows(d)
            st["live_query"] = "OK 取到 %d 行" % len(dates)
            live = True
        except Exception as e:
            st["live_query"] = "FAIL %s" % e
    else:
        # access_token 标记失效 → 试着刷新一次
        try:
            from _baidu_auth import get_access_token
            get_access_token()
            st["refresh_attempt"] = "已刷新，请重跑确认"
        except Exception as e:
            st["refresh_attempt"] = "刷新失败：%s" % e

    # ② 硬编码扫描
    result["hardcoded"] = scan_hardcoded(os.path.dirname(HERE))

    # ③ 迁移残留
    result["legacy_left"] = check_legacy()

    ok = live and not result["hardcoded"]

    if as_json:
        result["pass"] = ok
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if ok else 1

    W = 62
    print("=" * W)
    print("① 凭据状态")
    print("=" * W)
    if not st.get("ok"):
        print("  ❌", st.get("error"))
    else:
        print("  凭据文件   :", st["secrets_path"])
        print("  文件权限   :", st["perm"], "（须为 600）")
        print("  站点 ID    :", st["site_id"])
        print("  client_id  :", st["client_id"])
        print("  secret     :", st["client_secret"])
        print("  refresh_tk :", st["refresh_token"])
        print("  access_tk  :", st["access_token"])
        print("  到期估算   :", st.get("access_token_expires_at"))
        print("  最近更新   :", st.get("updated_at"))
        print("  存活探测   :", "✅ 有效" if st.get("access_token_alive") else "❌ 失效")
        if st.get("live_query"):
            print("  真实取数   :", st["live_query"])
        if st.get("refresh_attempt"):
            print("  刷新尝试   :", st["refresh_attempt"])

    print()
    print("=" * W)
    print("② 硬编码凭据扫描（入仓前门禁，必须 0 命中）")
    print("=" * W)
    if result["hardcoded"]:
        for rel, n, sample in result["hardcoded"]:
            print("  ❌ %-42s %d 处  如 %s" % (rel, n, sample))
        print("\n  🔴 禁止同步到公开仓！请把凭据移到 "
              "~/.workbuddy/secrets/baidu_tongji.json")
    else:
        print("  ✅ 零命中，可安全同步")

    print()
    print("=" * W)
    print("③ 迁移残留（判据 G：易失资产不该留在会话工作区）")
    print("=" * W)
    if result["legacy_left"]:
        for p in result["legacy_left"]:
            note = "（有自动化引用，迁移须连 prompt 一起改）" \
                if "weekly" in p else "（无引用，可直接删）"
            print("  🟡 %s %s" % (p, note))
    else:
        print("  ✅ 会话工作区已清空百度统计脚本")

    print()
    print("=" * W)
    print("结论：", "✅ 全绿" if ok else "❌ 存在问题（见上）")
    print("=" * W)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
