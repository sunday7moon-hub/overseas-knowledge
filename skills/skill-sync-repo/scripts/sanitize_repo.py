#!/usr/bin/env python3
"""对外仓库脱敏：把内部标识替换为占位符（只处理仓库副本）。"""
import os
import re
import sys

REPO = "/Users/yoyo/WorkBuddy/2026-07-30-09-39-41/overseas-knowledge"
SKILLS = os.path.join(REPO, "skills")

RULES = [
    ("ou_7f361375714176385a1368cfd58e8f53", "ou_YOUR_OPENID"),
    ("oc_e9daf25cd71382c02a66dfb27d50b1b5", "oc_YOUR_CHAT_ID"),
]
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@(xinfushe|yonyou)\.com")

TEXT_EXT = {".md", ".py", ".json", ".js", ".txt", ".html", ".htm",
            ".yaml", ".yml", ".csv", ".sh", ".ts"}

hits = {}
scanned = 0
for root, dirs, files in os.walk(SKILLS):
    dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git")]
    for fn in files:
        if os.path.splitext(fn)[1].lower() not in TEXT_EXT:
            continue
        p = os.path.join(root, fn)
        try:
            src = open(p, encoding="utf-8").read()
        except (UnicodeDecodeError, OSError):
            continue
        scanned += 1
        new = src
        for a, b in RULES:
            new = new.replace(a, b)
        new = EMAIL_RE.sub(lambda m: "user@example.com", new)
        if new != src:
            open(p, "w", encoding="utf-8").write(new)
            rel = os.path.relpath(p, REPO)
            hits[rel] = sum(src.count(a) for a, _ in RULES) + len(EMAIL_RE.findall(src))

print(f"扫描 {scanned} 个文本文件，脱敏 {len(hits)} 个：")
for k, v in sorted(hits.items()):
    print(f"  {v:>3} 处  {k}")

# 复扫校验
left = {"openid": 0, "chat": 0, "email": 0}
for root, dirs, files in os.walk(SKILLS):
    dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git")]
    for fn in files:
        if os.path.splitext(fn)[1].lower() not in TEXT_EXT:
            continue
        p = os.path.join(root, fn)
        try:
            src = open(p, encoding="utf-8").read()
        except (UnicodeDecodeError, OSError):
            continue
        left["openid"] += src.count(RULES[0][0])
        left["chat"] += src.count(RULES[1][0])
        left["email"] += len(EMAIL_RE.findall(src))
print("复扫残留:", left, "→", "✅ 全清" if sum(left.values()) == 0 else "🔴 仍有残留")
sys.exit(0 if sum(left.values()) == 0 else 1)
