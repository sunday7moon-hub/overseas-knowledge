# Getting Started / 快速开始

## 安装技能

### 方式一：拖入 WorkBuddy（推荐日常使用）

1. 在 [Releases](https://github.com/sunday7moon-hub/overseas-knowledge/releases) 或 `releases/` 目录下载对应 `.zip`
2. 拖入 WorkBuddy 技能管理面板
3. 用自然语言描述任务即可触发

### 方式二：本地安装

```bash
git clone https://github.com/sunday7moon-hub/overseas-knowledge.git
cd overseas-knowledge
# 每个技能目录即是一个完整技能包
```

### 方式三：直接从 GitHub 浏览

所有技能源文件在 `skills/` 目录下直接可读，无需下载即可查看详细说明和使用方法。

## 创建新技能

1. 在 `skills/` 下创建新目录，如 `skills/my-new-skill/`
2. 在技能目录下创建 `SKILL.md`（必须），参考现有技能格式
3. 如有脚本/数据文件，放在 `scripts/` 或 `references/` 子目录
4. 如需发布，打包为 `.zip` 放到 `releases/`
5. 在 README 索引表中加一行

## 技能命名规范

- 目录名：`kebab-case`，小写英文 + 连字符
- 描述性命名，见名知义
- 示例：`client-salary-band-report`、`xinfushe-overseas-hr`
