#!/usr/bin/env python3
"""重建 releases/*.zip —— 每个技能一个包，与 skills/ 一一对应。"""
import os
import subprocess
import sys

REPO = "/Users/yoyo/WorkBuddy/2026-07-30-09-39-41/overseas-knowledge"
SKILLS = os.path.join(REPO, "skills")
REL = os.path.join(REPO, "releases")

names = sorted(d for d in os.listdir(SKILLS)
               if os.path.isdir(os.path.join(SKILLS, d)) and not d.startswith("."))
print(f"技能数：{len(names)}")

made = []
for n in names:
    out = os.path.join(REL, f"{n}.zip")
    if os.path.exists(out):
        os.remove(out)
    cmd = ["zip", "-rq", out, n,
           "-x", "*.DS_Store", "-x", "*__pycache__*", "-x", "*.pyc",
           "-x", "*.workbuddy/*", "-x", "*/.workbuddy/*"]
    r = subprocess.run(cmd, cwd=SKILLS, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"🔴 {n} 打包失败：{r.stderr.strip()[:200]}")
        sys.exit(1)
    size = os.path.getsize(out)
    made.append((n, size))
    print(f"  ✓ {n}.zip  {size/1024:.0f} KB")

# 清理不在 skills/ 里的多余 zip（保留扩展包）
keep = {f"{n}.zip" for n in names} | {"browser-bridge-extension-v1.3.0.zip"}
for f in os.listdir(REL):
    if f.endswith(".zip") and f not in keep:
        os.remove(os.path.join(REL, f))
        print(f"  🧹 移除多余包 {f}")

print(f"\nreleases 现有 {len(os.listdir(REL))} 项：")
for f in sorted(os.listdir(REL)):
    print("   ", f)
