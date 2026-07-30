# Conventions / 编码规范

## 目录结构

```
skills/<skill-name>/
├── SKILL.md           # 技能定义文件（必须）
├── scripts/           # 可执行脚本（可选）
├── references/        # 参考数据/文档（可选）
└── assets/            # 静态资源（可选，字体/图片等）
```

## SKILL.md 规范

### 必须包含

- **Frontmatter**：`name`、`description`（中英双语）为必填
- **中文名称 + 英文名称**：一级标题后注明
- **Overview**：技能简介和使用场景
- **触发词/触发场景**：明确什么时候该用这个技能

### 推荐包含

- **Workflow**：标准操作流程
- **注意事项**：常见坑位和边界条件
- **输出规范**：产物格式和命名约定

### Frontmatter 示例

```yaml
---
name: my-skill-name
description: '[EN] Brief description. / [CN] 简要说明。'
agent_created: true
---
```

## 提交规范

- commit message 使用 `[skill-name] 变更说明` 格式
- 修改技能内容时同步更新对应 SKILL.md 的 frontmatter 版本号
- 不提交临时文件和系统文件（.DS_Store 等）

## 发布规范

- 每个技能打包为 `<skill-name>.zip` 放置在 `releases/`
- zip 内需包含完整的技能目录结构
- 源文件（`skills/` 目录）与 zip 包（`releases/` 目录）需同步更新
