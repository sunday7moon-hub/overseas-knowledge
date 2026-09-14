#!/usr/bin/env python3
"""公开仓库脱敏：把内部标识替换为占位符（只处理仓库副本，本地技能保持真实值）。

设计要点：**规则用正则，不写任何字面量 ID** ——
否则「脱敏工具自己」就成了泄露源（曾把真实 openid 写进脚本并同步进公开仓库）。

用法：
    python3 sanitize_repo.py            # 默认处理 overseas-knowledge 仓库
    python3 sanitize_repo.py <REPO>     # 指定仓库根目录
"""
import os
import re
import sys

REPO = sys.argv[1] if len(sys.argv) > 1 else \
    "/Users/yoyo/WorkBuddy/2026-07-30-09-39-41/overseas-knowledge"
SKILLS = os.path.join(REPO, "skills")

# (正则, 替换值, 规则名) —— 禁止写字面量 ID
RULES = [
    (re.compile(r"ou_[A-Za-z0-9]{20,}"), "ou_YOUR_OPENID", "飞书个人 openid"),
    (re.compile(r"oc_[A-Za-z0-9]{20,}"), "oc_YOUR_CHAT_ID", "飞书群会话 ID"),
    (re.compile(r"[A-Za-z0-9._%+-]+@(?:xinfushe|yonyou)\.com"),
     "user@example.com", "内部邮箱域"),
]

TEXT_EXT = {".md", ".py", ".json", ".js", ".txt", ".html", ".htm",
            ".yaml", ".yml", ".csv", ".sh", ".ts"}

SELF = os.path.abspath(__file__)   # 自排除，避免改到本脚本


def iter_text_files(root):
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git")]
        for fn in files:
            if os.path.splitext(fn)[1].lower() in TEXT_EXT:
                yield os.path.join(dirpath, fn)


def rule_hits(text):
    out = {}
    for rx, _, name in RULES:
        c = len(rx.findall(text))
        if c:
            out[name] = c
    return out


def safe_read(p):
    try:
        return open(p, encoding="utf-8").read()
    except (UnicodeDecodeError, OSError):
        return None


hits, scanned = {}, 0
for p in iter_text_files(SKILLS):
    if os.path.abspath(p) == SELF:
        continue
    src = safe_read(p)
    if src is None:
        continue
    scanned += 1
    new = src
    for rx, rep, _ in RULES:
        new = rx.sub(rep, new)
    if new != src:
        open(p, "w", encoding="utf-8").write(new)
        hits[os.path.relpath(p, REPO)] = rule_hits(src)

print(f"扫描 {scanned} 个文本文件，命中 {len(hits)} 个：")
for k, v in sorted(hits.items(), key=lambda kv: -sum(kv[1].values())):
    print(f"  {' / '.join(f'{n}×{c}' for n, c in v.items()):<28} {k}")
if not hits:
    print("  （无命中）")

left = {}
for p in iter_text_files(SKILLS):
    if os.path.abspath(p) == SELF:
        continue
    src = safe_read(p)
    if src is None:
        continue
    for name, c in rule_hits(src).items():
        left[name] = left.get(name, 0) + c

if left:
    print("🔴 复扫仍有残留：", left)
    sys.exit(1)
print("✅ 复扫全清")
