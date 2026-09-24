---
name: xhs-automation-suite
description: 小红书自动化套件（第三方开源项目 xiaohongshu-skills），基于已登录的真实浏览器与账号操作，含 5 个子能力——认证管理、内容发布、内容发现（搜索/笔记详情/用户主页）、社交互动（评论/点赞/收藏）、复合运营（竞品分析/热点追踪）。当用户需要「搜索小红书笔记」「抓取笔记详情或用户主页」「评论/点赞/收藏」「用真实账号发布小红书」时使用。**仅发布图文且不需要登录态时，优先用 `xiaohongshu-publisher`。**
---

# 小红书自动化套件（xhs-automation-suite）

> 来源：开源项目 `xiaohongshu-skills`（autoclaw-cc），本目录为其完整副本（57 个文件）。
> 归属：**L0 环境基座**（渠道工具，换工作也能用）。

**历史问题**：本目录原名 `xhs-publish-note`，且顶层 SKILL.md 被错误覆盖为 `find-skills` 的内容，导致套件长期无法被识别触发。2026-09-04 已修复并重命名。

---

## 一、子能力索引

调用前**必须先读取对应子技能的 SKILL.md**，本文件只做索引。

| 子技能 | 路径 | 能力 |
|--------|------|------|
| **xhs-auth** | `xiaohongshu-skills-main/skills/xhs-auth/SKILL.md` | 登录检查、扫码登录、手机验证码登录 |
| **xhs-publish** | `xiaohongshu-skills-main/skills/xhs-publish/SKILL.md` | 图文 / 视频 / 长文发布、定时发布、分步预览 |
| **xhs-explore** | `xiaohongshu-skills-main/skills/xhs-explore/SKILL.md` | 关键词搜索、笔记详情、用户主页、首页推荐 |
| **xhs-interact** | `xiaohongshu-skills-main/skills/xhs-interact/SKILL.md` | 评论、回复、点赞、收藏 |
| **xhs-content-ops** | `xiaohongshu-skills-main/skills/xhs-content-ops/SKILL.md` | 竞品分析、热点追踪、批量互动、内容创作 |

支持**连贯操作**：可用自然语言下达复合指令（如"搜索某关键词最火的图文，收藏它，然后告诉我讲了什么"），自动串联多个子技能。

---

## 二、前置条件（未满足则不可用）

| 项 | 要求 |
|------|------|
| Python | ≥ 3.11 |
| 包管理器 | [uv](https://docs.astral.sh/uv/) |
| 浏览器 | Google Chrome（需已登录小红书账号） |
| 浏览器扩展 | `xiaohongshu-skills-main/extension/` 需加载到 Chrome |
| 依赖安装 | 按 `xiaohongshu-skills-main/README.md` 的「第一步：安装项目」执行 |

**首次使用或报连接失败时**：检查扩展是否已加载、Chrome 是否已登录、依赖是否已装。

---

## 三、与另外两个小红书技能的分工

避免路由打架，按下表选择：

| 场景 | 用谁 |
|------|------|
| 只需要**发布一篇现成图文** | `xiaohongshu-publisher`（Playwright 脚本，无需扩展） |
| **端到端**跑完 研究→写作→配图→发布 | `xhs-one-click-publish`（流程编排） |
| 需要**搜索 / 抓笔记 / 看用户主页 / 互动 / 批量运营** | **`xhs-automation-suite`**（本套件，功能最全） |

> 本套件是三者中**唯一**支持内容发现与社交互动的。

---

## 四、风控红线

- ⚠️ **必须控制操作频率**。虽使用真实浏览器与账号，但短时间内大量自动化操作会触发小红书风控，导致**账号受限**。
- 批量互动（点赞/评论/收藏）前须确认频率阈值，宁慢勿快。
- 对外发布内容前须先过内容质量门禁（企业 PR 拦截、竞品黑名单、30 天去重）。

---

## 五、原始文档

- 项目说明：`xiaohongshu-skills-main/README.md`
- 设计与实现文档：`xiaohongshu-skills-main/docs/`
- 底层脚本：`xiaohongshu-skills-main/scripts/xhs/`（`bridge.py`、`cdp.py`、`login.py`、`feeds.py` 等）
