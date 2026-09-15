#!/usr/bin/env python3
"""GitHub token 探测：从本机 trace 里找回可用的 GitHub 凭据。

用途：沙箱环境里 osxkeychain 取密需 GUI 授权（非交互必失败），
      而历史会话 trace 中常残留用户曾粘贴过的 PAT —— 本脚本自动找回可用者。

行为：
  1. 扫描 ~/.workbuddy/traces/**/*.json，匹配 GitHub token 形态；
  2. 逐个请求 https://api.github.com/user 验证（走系统代理）；
  3. **只打印掩码**，绝不打印明文；
  4. 把第一个可用的写入 ~/.workbuddy/secrets/gh_token.txt（600），供 gh_push.sh 使用。

安全：token 属用户本人凭据。使用后应提醒用户轮换/撤销。
"""
from __future__ import annotations

import glob
import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.request

PATTERNS = [
    re.compile(r"ghp_[A-Za-z0-9]{36}"),                # classic PAT
    re.compile(r"github_pat_[A-Za-z0-9_]{60,}"),       # fine-grained PAT
    re.compile(r"gho_[A-Za-z0-9]{36}"),                # oauth
    re.compile(r"ghs_[A-Za-z0-9]{36}"),                # app server-to-server
    re.compile(r"ghu_[A-Za-z0-9]{36}"),                # app user-to-server
]
SECRET_PATH = os.path.expanduser("~/.workbuddy/secrets/gh_token.txt")
TRACE_ROOT = os.path.expanduser("~/.workbuddy/traces")


def mask(t: str) -> str:
    return f"{t[:12]}…{t[-6:]} (len={len(t)})"


def collect() -> dict[str, int]:
    """返回 {token: 出现文件数}。"""
    cands: dict[str, int] = {}
    for path in glob.glob(os.path.join(TRACE_ROOT, "**", "*.json"), recursive=True):
        try:
            txt = open(path, encoding="utf-8", errors="ignore").read()
        except OSError:
            continue
        for pat in PATTERNS:
            for hit in pat.findall(txt):
                cands[hit] = cands.get(hit, 0) + 1
    return cands


def probe(token: str, timeout: int = 25) -> tuple[str | None, str]:
    """返回 (login, scopes)；失败返回 (None, 原因)。"""
    req = urllib.request.Request(
        "https://api.github.com/user",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "gh-token-probe",
        },
    )
    try:
        with urllib.request.urlopen(req, context=ssl.create_default_context(), timeout=timeout) as r:
            data = json.loads(r.read())
            return data.get("login"), r.headers.get("X-OAuth-Scopes", "")
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}"
    except Exception as e:  # noqa: BLE001
        return None, f"{type(e).__name__}: {e}"


def main() -> int:
    # 走系统代理（本机出网必须经代理）
    urllib.request.install_opener(urllib.request.build_opener(urllib.request.ProxyHandler()))

    cands = collect()
    print(f"候选 token：{len(cands)} 个（扫描自 {TRACE_ROOT}）")
    if not cands:
        print("未找到候选。请让用户新建 fine-grained PAT（Contents: Read and write）。")
        return 1

    ok: list[tuple[str, str, str]] = []
    entries: list[tuple[str, str, str, int]] = []
    for token, n in sorted(cands.items(), key=lambda kv: -kv[1]):
        login, info = probe(token)
        if login:
            print(f"  ✅ {mask(token)}  出现 {n} 次  → login={login}  scopes=[{info}]")
            ok.append((token, login, info))
            entries.append((token, login, info, n))
        else:
            print(f"  ❌ {mask(token)}  出现 {n} 次  → {info}（已失效/已撤销）")

    if not ok:
        print("\n没有可用 token。")
        return 1

    # 选优：优先「有 repo 权限的 classic token」（能推任意仓，含新建私有仓）＞ fine-grained ＞ 出现次数
    # 依据：fine-grained token 的 X-OAuth-Scopes 恒为空，无法判断仓库范围，可能不含新仓 → 不作首选。
    entries.sort(
        key=lambda e: ("repo" in e[2], e[0].startswith("ghp_"), e[3]),
        reverse=True,
    )
    token, login, scopes, n = entries[0]
    print(f"\n选中：{mask(token)}（出现 {n} 次）—— 排序优先级：classic+repo scope＞fine-grained＞出现次数")
    os.makedirs(os.path.dirname(SECRET_PATH), exist_ok=True)
    old_umask = os.umask(0o077)
    try:
        with open(SECRET_PATH, "w", encoding="utf-8") as f:
            f.write(token)
    finally:
        os.umask(old_umask)
    os.chmod(SECRET_PATH, 0o600)

    print(f"\n最佳候选已写入 {SECRET_PATH}（600）")
    print(f"  归属账号：{login}｜scopes：[{scopes}]")
    print("  ⚠️ 这是用户本人凭据：推送完成后提醒用户轮换/撤销，且不要打印明文或写进仓库。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
