---
name: skillhub-publish
display_name: SkillHub 技能发布
version: "1.0.0"
description: 通过 SkillHub 官方 CLI 将本地 WorkBuddy 技能自动发布到 SkillHub 技能市场（skillhub.cn）。当用户说"发布技能到 skillhub""上传技能到市场""自动同步到 skillhub""publish skill"时使用。覆盖 CLI 安装、SKILL.md 必填元字段、登录、dry-run 预检与正式发布全流程。
agent_created: true
---

# SkillHub 技能发布

把本地 WorkBuddy 技能发布到 SkillHub 技能市场（skillhub.cn）。

## 前置条件（用户必须提供）
1. SkillHub 账号 + 实名认证（skillhub.cn 个人中心）
2. API Token（`skh_` 开头）：个人中心 → API keys → 创建（仅显示一次，立即复制保存）
3. 授权执行 CLI 安装命令（curl|bash，有供应链风险）

⚠️ 关键：浏览器已登录 ≠ CLI 可用。CLI 进程读不到浏览器 session，必须独立创建 API Token。

## 安装 CLI
```bash
curl -fsSL https://skillhub.cn/install/install.sh | bash -s -- --cli-only
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
skillhub --version   # 验证，看到 skillhub 2026.x.x 即成功
```

## SKILL.md 必填元字段（缺任一 dry-run 不过）
```yaml
---
name: my-skill
display_name: 我的技能        # WorkBuddy 使用（下划线）
displayName: 我的技能          # SkillHub 使用（驼峰）
slug: my-skill                # 全网唯一，撞名发布失败
version: "1.0.0"
summary: 一句话简介
description: 完整描述（禁止截断）
tags: [标签1, 标签2]
license: MIT
---
```

## 发布流程
```bash
# 1. 登录（token 一次性传入，不落盘到 .git/config 之类）
skillhub auth login --token skh_你的Token --host https://api.skillhub.cn
# 2. 本地预检（只验格式，不验 slug 唯一性）
skillhub publish ./my-skill --dry-run
# 3. 正式发布
skillhub publish ./my-skill --changelog "首次发布"
# 成功返回：✓ Published: skillId=xxxxx status=pending_review
```
登录也可直接用 `skillhub publish --token skh_xxx ./dir`（不预先 login）。

## 安全与注意
- `skh_` token 明文进对话有泄露风险 → 发布完立即去个人中心 revoke
- slug 撞名：`dry-run` 不报，正式发布才报；临时改唯一 slug 重发即可（不影响本地技能）
- 审核：三线并行安全审核（内容合规+漏洞扫描+AI 安全），通过自动上架
- 更新版本：相同 slug + 新 version + 新 changelog 重新 publish

## 实战记录（compliance-guide-pptx，2026-08-28）
- CLI 安装路径：`/Users/yoyo/.local/bin/skillhub`，版本 2026.8.5
- 登录成功：`@user_1e859ec3`，发布 `skillId=175943`，进入审核流水线
- slug 用 `compliance-guide-pptx`，未撞名
