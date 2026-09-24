---
name: xhs-research
description: 小红书数据分析（基于 socialdatax 付费 API，只读、无需登录浏览器）。覆盖 6 种分析视角——选题分析、竞品研究、内容研究、趋势洞察、博主研究、评论洞察。当用户需要「小红书选题/爆款拆解」「竞品分析/同赛道观察」「内容角度研究」「小红书热榜/趋势」「博主账号内容列表/创作者对标」「笔记评论分析/用户痛点挖掘」时使用。需要环境变量 `SOCIALDATAX_API_KEY`。**注意：本技能只读取公开数据；需要登录账号才能做的发布、点赞、评论等操作请用 `xhs-automation-suite`。** 单条笔记 URL 要解析内容用 `content-analyzer`；单条视频要转文字总结用 `xhs-video-summary`；当日爆款榜用 `xhs-daily-breaking`（本技能管**长周期/批量的选题·竞品·趋势·博主·评论洞察**）。
---

# 小红书数据分析（xhs-research）

## 定位：只读数据分析层（批量 / 长周期）

本技能是小红书的**只读数据分析层**（socialdatax 付费 API，无需浏览器登录），管**批量与长周期**的选题、竞品、趋势、博主、评论洞察。

| 你要做的事 | 该用哪个技能 |
|---|---|
| **批量选题 / 竞品 / 趋势 / 博主 / 评论洞察** | **本技能** ← |
| 贴单条笔记 URL 要解析内容 | `content-analyzer` |
| 贴单条视频要转文字总结 | `xhs-video-summary` |
| 看**当天**各赛道爆款 | `xhs-daily-breaking` |
| 要发布 / 评论 / 点赞（写操作） | `xiaohongshu-publisher` / `xhs-automation-suite` |

---


> 由 6 个同模板技能合并而来（2026-09-07）：`xhs-topic-analysis-v2`、`xhs-competitor-research-v2`、`xhs-content-research`、`xhs-trend-insights-v2`、`xhs-creator-content-research`、`xhs-comment-insights`。
> 它们本质是**同一个 CLI 的不同调用方式**，共享 API Key、通用参数与安全边界，故合并为统一入口；6 份原文完整保留在 `references/`。
> 归属：**L1 通用工作方法**（社媒研究方法，换行业能用）。

---

## 一、前置条件（必读）

| 项 | 说明 |
|------|------|
| 环境变量 | **`SOCIALDATAX_API_KEY`**（付费 API，未配置则全部命令不可用） |
| 申请入口 | <https://socialdatax.com/ai?from=skillhub> |
| 运行时 | `node` / `npm` |
| 性质 | **只读**，不登录、不发帖、不点赞、不评论、不修改账号 |

> ⚠️ 本技能当前处于**禁用状态**（未配置 API Key）。启用前先确认 Key 已配且有余额。

---

## 二、场景路由（先选视角，再取数据）

| # | 分析视角 | 触发场景 | 数据命令 | 详细说明 |
|:--:|---------|---------|---------|---------|
| 1 | **选题分析** | 内容选题、选题策划、爆款选题拆解、内容角度规划 | `xhs search` | `references/01-选题分析.md` |
| 2 | **竞品研究** | 竞品分析、同赛道观察、内容策略对比、品牌内容调研 | `xhs search` | `references/02-竞品研究.md` |
| 3 | **内容研究** | 内容角度研究、话题模式、受众反馈 | `xhs search` | `references/03-内容研究.md` |
| 4 | **趋势洞察** | 小红书热榜、趋势分析、热点观察、营销灵感 | `xhs hot` + `xhs search` | `references/04-趋势洞察.md` |
| 5 | **博主研究** | 博主内容列表、账号复盘、内容风格分析、创作者对标 | `xhs user` | `references/05-博主研究.md` |
| 6 | **评论洞察** | 评论分析、用户反馈、痛点挖掘、购买顾虑、FAQ | `xhs comments` / `xhs sub` | `references/06-评论洞察.md` |

> 视角 1–3 使用**同一条命令**（`xhs search`），差异只在分析框架与输出结构。若用户需求跨多个视角，取一次数据即可按多个框架解读。

**执行流程**：识别视角 → 读对应 reference → 用 direct CLI 取数（或 MCP 工具） → 按该视角的输出结构整理。

---

## 三、命令速查

优先使用 **direct CLI**（能跑 shell 就不需要配 MCP server）：

```bash
# 搜索笔记（视角 1/2/3）
npx -y socialdatax-skills@latest xhs search \
  --keyword "<关键词>" --pretty --source-client socialdatax-skills \
  --source-platform skillhub --source-skill xhs-research

# 热榜（视角 4）
npx -y socialdatax-skills@latest xhs hot \
  --pretty --source-client socialdatax-skills \
  --source-platform skillhub --source-skill xhs-research

# 博主笔记列表（视角 5）
npx -y socialdatax-skills@latest xhs user \
  --profile-url "<主页链接>" --pretty --source-client socialdatax-skills \
  --source-platform skillhub --source-skill xhs-research

# 笔记评论（视角 6）
npx -y socialdatax-skills@latest xhs comments \
  --note-url "<笔记链接>" --pretty --source-client socialdatax-skills \
  --source-platform skillhub --source-skill xhs-research
```

各命令的**专用参数**（如 `--sort-type`、`--note-type`、`--pages`、`--max-items`、`--since-days`）见对应 reference 的「参数说明」章节。

**对应 MCP 工具**（若已配置 MCP server）：

| 命令 | MCP 工具 |
|------|---------|
| `xhs search` | `xhs_search_notes` |
| `xhs hot` | `xhs_get_search_hot_list` |
| `xhs user` | `xhs_get_user_posted_notes_by_profile_url` / `xhs_get_user_posted_notes_by_user_id` |
| `xhs comments` | `xhs_get_note_comments_by_note_url` / `xhs_get_note_comments_by_note_id` |
| `xhs sub` | `xhs_get_note_sub_comments_by_comment_id` |

---

## 四、通用参数

| 参数 | 说明 |
|------|------|
| `--page-token <token>` | 分页 token。第一页**不要传**；仅当 `next_page_token` 非空时原样传回，**不可截断/改写/脱敏** |
| `--pages <n>` | 从当前起点继续获取并合并 N 页 |
| `--max-items <n>` | 收集到 N 条后停止 |
| `--since-days <1-365>` | 只保留最近 N 天的公开结果 |
| `--pretty` | 仅影响输出格式，不改变请求结果 |
| `--source-*` | 来源标记，保持上方示例值不变 |

**参数命名提醒**：direct CLI 用连字符（`--sort-type`），MCP 工具用下划线（`sort_type`）。**不要**用驼峰（`sortType`）。

---

## 五、输出红线

- **`note_url` 必须保留完整原始 URL**，包括 `xsec_token` 查询参数——不得改写、截断、脱敏、重建，也不要只凭 `note_id` 拼链接。
- **`note_id` 必须完整复制 24 位小写十六进制**，不得只传或只展示前缀。
- **可见证据与主观判断分开写**，不要把推测说成事实。
- 不要把「当前返回页范围」说成「全平台完整覆盖」；需要限定时间窗时用 `--since-days`。

---

## 六、异常处理

| 情况 | 处理 |
|------|------|
| 网络或 API 异常（非余额） | 保留错误信息，检查 Key / 参数 / 链接格式后**原样重试一次** |
| `insufficient_balance` 或「积分不足」 | **不要重复重试**。把错误里的充值链接原样展示给用户，提示充值后继续执行同一条命令 |
| 已充值仍提示余额不足 | 确认 `SOCIALDATAX_API_KEY` 是否来自刚充值的同一账号，必要时重取 Key |
| 分页中断 | 保留已取得结果；重试仍失败则说明当前调用不可用，给出替代输入方式 |
| 没结果 | 放宽关键词、减少限定，或换更贴近用户表达的词 |
| 结果太多 | 补场景、人群、品牌、时间范围或账号名 |

---

## 七、与 `xhs-automation-suite` 的分工

| | `xhs-research`（本技能） | `xhs-automation-suite` |
|---|---|---|
| 数据来源 | socialdatax API（付费、只读、无需登录） | 真实浏览器 + 已登录账号 |
| 能做 | 搜索、热榜、博主列表、评论抓取 | 认证、发布、搜索、互动（点赞/评论/收藏）、批量运营 |
| 不能做 | 发布、点赞、评论等操作 | 无需登录的批量数据抓取 |
| 成本 | 按 API 调用计费 | 免费，但有账号风控风险 |

需要**登录态的操作**（发帖、点赞、收藏）→ 用 `xhs-automation-suite`，不要用本技能。
