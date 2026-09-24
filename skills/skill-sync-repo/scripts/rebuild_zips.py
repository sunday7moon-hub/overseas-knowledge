#!/usr/bin/env python3
"""重建 releases/*.zip —— 每个技能一个包，与 skills/ 一一对应。

设计要点：
1. **不调用 os.remove**：直接以 `zipfile` 的 "w" 模式覆盖旧包，
   且不主动清理多余 zip（改为一并列出，人工确认后再动）——
   避免触发沙箱的批量删除门禁，也让「误删」风险归零。
2. **排除集与同步一致**：venv / node_modules / .bak / .rule-ref / _backup /
   .workbuddy 等运行环境与运行时目录**不得进包**。
   （血泪：pdfkit-py 曾夹带 194M venv 被打进包）
"""
import os
import sys
import zipfile

REPO = os.environ.get("REPO",
                      "/Users/yoyo/WorkBuddy/2026-07-30-09-39-41/overseas-knowledge")
SKILLS = os.path.join(REPO, "skills")
REL = os.path.join(REPO, "releases")
EXTRA_KEEP = {"browser-bridge-extension-v1.3.0.zip"}

# 目录名（任意层级命中即跳过）
EXCLUDE_DIRS = {"__pycache__", "venv", ".venv", "node_modules",
                "site-packages", ".workbuddy", ".rule-ref", ".git"}
# 文件名后缀 / 片段
EXCLUDE_SUFFIX = (".pyc", ".pyo", ".zip")
EXCLUDE_CONTAINS = (".bak", ".orig", "~")
EXCLUDE_NAMES = {".DS_Store"}


def excluded(rel_path, name, is_dir):
    parts = rel_path.split(os.sep)
    if any(p in EXCLUDE_DIRS for p in parts) or any(p.startswith("_backup") for p in parts):
        return True
    if name in EXCLUDE_NAMES:
        return True
    if name.endswith(EXCLUDE_SUFFIX):
        return True
    if any(k in name for k in EXCLUDE_CONTAINS):
        return True
    return False


def build(name):
    out = os.path.join(REL, f"{name}.zip")
    root = os.path.join(SKILLS, name)
    n_files = 0
    # strict_timestamps=False：技能内偶有 mtime < 1980 的文件
    # （如从模板/镜像拷来的资源），严格模式会直接抛 ValueError 中断全量打包
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9,
                         strict_timestamps=False) as zf:
        for dirpath, dirs, files in os.walk(root):
            rel = os.path.relpath(dirpath, SKILLS)
            dirs[:] = [d for d in dirs if not excluded(
                os.path.join(rel, d) if rel != "." else d, d, True)]
            for fn in files:
                rp = os.path.join(rel, fn) if rel != "." else fn
                if excluded(rp, fn, False):
                    continue
                zf.write(os.path.join(dirpath, fn), rp)
                n_files += 1
    return out, n_files


names = sorted(d for d in os.listdir(SKILLS)
               if os.path.isdir(os.path.join(SKILLS, d)) and not d.startswith("."))
print(f"技能数：{len(names)}")
os.makedirs(REL, exist_ok=True)

total = 0
for n in names:
    out, cnt = build(n)
    size = os.path.getsize(out)
    total += size
    flag = "⚠️ 体积偏大" if size > 5 * 1024 * 1024 else ""
    print(f"  ✓ {n}.zip  {size/1024:.0f} KB  ({cnt} 文件) {flag}")

print(f"\n合计 {total/1024/1024:.1f} MB")

keep = {f"{n}.zip" for n in names} | EXTRA_KEEP
extras = [f for f in sorted(os.listdir(REL)) if f.endswith(".zip") and f not in keep]
if extras:
    print("⚠️ releases 内多余包（未自动删除，请人工确认）：")
    for f in extras:
        print("   ", f)
else:
    print("releases 无多余包")
print(f"releases 现有 {len([f for f in os.listdir(REL) if f.endswith('.zip')])} 个 zip")
