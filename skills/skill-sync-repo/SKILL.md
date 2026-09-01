---
name: skill-sync-repo
description: "[EN] Sync local WorkBuddy skills to GitHub repo + Gitee mirror.
  Extract, zip, update index, commit, push. / [CN] 将本地 WorkBuddy 技能同步到 GitHub
  仓库（Gitee 自动镜像）。抽取、打包、更新索引、提交推送一步到位。"
agent_created: true
disable-model-invocation: true
---

# 技能同步到 Git 仓库

## Overview

将 `~/.workbuddy/skills/` 中的技能同步到 GitHub 仓库 `overseas-knowledge`，Gitee 通过自动镜像同步无需手动操作。

### 典型触发场景

- "同步技能到仓库"
- "上传技能到 git"
- "把 xx 技能推到 github"
- "更新仓库里的技能"
- "同步 gitee"

---

## 仓库信息

| 项目 | 值 |
|------|-----|
| GitHub | `https://github.com/sunday7moon-hub/overseas-knowledge.git` |
| Gitee | 自动镜像（无需手动 push） |
| 本地路径 | `/Users/yoyo/WorkBuddy/2026-07-30-09-39-41/overseas-knowledge` |
| 技能源目录 | `~/.workbuddy/skills/<skill-name>/` |
| 仓库技能目录 | `overseas-knowledge/skills/<skill-name>/` |
| 下载包目录 | `overseas-knowledge/releases/<skill-name>.zip` |

---

## Workflow

### Step 1: 确认技能名称

用户说出技能名后，确认 `~/.workbuddy/skills/<skill-name>/SKILL.md` 存在。

```bash
ls ~/.workbuddy/skills/<skill-name>/SKILL.md
```

如果用户没说具体技能名，列出所有技能让用户选：
```bash
ls -d ~/.workbuddy/skills/*/
```

### Step 2: 同步技能文件到仓库

将技能目录内容同步到仓库的 `skills/` 目录（保持扁平结构，不要双层嵌套）：

```bash
REPO="/Users/yoyo/WorkBuddy/2026-07-30-09-39-41/overseas-knowledge"
SKILL="<skill-name>"

# 创建目标目录（如不存在）
mkdir -p "$REPO/skills/$SKILL"

# 用 rsync 同步，排除 .DS_Store
rsync -av --delete --exclude='.DS_Store' ~/.workbuddy/skills/$SKILL/ "$REPO/skills/$SKILL/"
```

**关键点：**
- `--delete` 确保仓库里的技能文件与本地完全一致（删除已移除的文件）
- 排除 `.DS_Store` 等系统文件
- 保持扁平结构：`skills/<skill-name>/SKILL.md`，不要 `skills/<skill-name>/<skill-name>/SKILL.md`

### Step 3: 打包 .zip 到 releases/

```bash
REPO="/Users/yoyo/WorkBuddy/2026-07-30-09-39-41/overseas-knowledge"
SKILL="<skill-name>"

cd "$REPO/skills"
zip -r "$REPO/releases/$SKILL.zip" "$SKILL/" -x '*.DS_Store'
```

### Step 4: 更新 README 索引（每次同步必做，硬性前置）

**关键规则：无论新增 / 更新 / 删除 / 批量同步，提交前都必须先核对并更新 README，保持索引与 `skills/` 实际目录完全一致。**

1. 列出 `skills/` 实际目录，与 README「Skills 技能索引」表逐行比对：
```bash
REPO="/Users/yoyo/WorkBuddy/2026-07-30-09-39-41/overseas-knowledge"
ls -d "$REPO"/skills/*/ | xargs -n1 basename | sort
```
2. 三类差异处理：
   - **缺失**（目录有、索引无）→ 新增一行，编号顺延；用途说明从 SKILL.md frontmatter `description` 提取，不要自己编
   - **多余**（索引有、目录无）→ 删除该行
   - **变更**（用途/链接变）→ 同步更新该行
3. 同步更新 README「Structure 目录结构」树，补/删 `skills/<name>/` 与 `releases/<name>.zip` 条目
4. 自检：README 索引行数 == `skills/` 目录数（含 `skill-sync-repo` 自身）

格式：
```markdown
| N | `<skill-name>` | 一句话用途说明 | [SKILL.md](skills/<skill-name>/SKILL.md) |
```

### Step 5: 提交并推送

```bash
REPO="/Users/yoyo/WorkBuddy/2026-07-30-09-39-41/overseas-knowledge"
SKILL="<skill-name>"

cd "$REPO"
git add -A
git commit -m "sync: update $SKILL skill"
git push origin main
```

**commit message 规范：**
- 新增技能：`add: <skill-name> skill`
- 更新技能：`sync: update <skill-name> skill`
- 删除技能：`remove: <skill-name> skill`
- 结构变更：`restructure: <说明>`

### Step 6: 确认 Gitee 同步

Gitee 已配置自动镜像，GitHub push 成功后 Gitee 会自动同步。

**无需任何手动操作。** 仅在用户询问时告知：
> GitHub 已推送，Gitee 会通过自动镜像同步（通常几分钟内完成）。

---

## 批量同步

用户说"同步所有技能"时：

```bash
REPO="/Users/yoyo/WorkBuddy/2026-07-30-09-39-41/overseas-knowledge"

for skill_dir in ~/.workbuddy/skills/*/; do
  SKILL=$(basename "$skill_dir")
  # 跳过没有 SKILL.md 的目录
  [ -f "$skill_dir/SKILL.md" ] || continue
  
  mkdir -p "$REPO/skills/$SKILL"
  rsync -av --delete --exclude='.DS_Store' "$skill_dir" "$REPO/skills/$SKILL/"
  cd "$REPO/skills" && zip -r "$REPO/releases/$SKILL.zip" "$SKILL/" -x '*.DS_Store'
done

cd "$REPO"
git add -A
git commit -m "sync: batch update all skills"
git push origin main
```

---

## 注意事项

1. **不要双层嵌套**：`skills/<name>/SKILL.md` 是正确的，`skills/<name>/<name>/SKILL.md` 是错误的
2. **大文件警告**：canvas-design 含 80+ 字体文件（~2.5MB），push 可能较慢
3. **网络重试**：GitHub push 遇到 502 时重试即可，commit 不会丢
4. **Gitee 延迟**：自动镜像不是实时的，通常几分钟内完成，不要反复 push 测试
5. **不要提交 .DS_Store**：仓库已有 .gitignore 排除，但 rsync/zip 时也加 `-x` 保险
6. **README 与索引强一致（每次必做）**：每次 `git add` 前，README 的「Skills 技能索引」表、「Structure 目录结构」树、「releases」树必须与 `skills/` 实际目录一致。新增/更新/删除/批量同步任何场景都先核对索引，不可跳过。
