---
name: yoyo-skill-router
description: 【技能总索引与路由】当需要「从 70 个技能里挑出该用哪一个」时使用 —— 用户说「用什么技能」「有哪些技能」「技能清单」「梳理一下技能」「该走哪个技能」，或一个请求可能命中多个相邻技能（小红书发布、PDF、PPT、海报、图片生成、竞品分析、飞书建表、合规检索）需要消歧时。含 12 个业务域全景索引、10 组高频冲突词的唯一入口路由表、技能来源三分（自建可改 / 分发不可改）、以及依赖枢纽清单（改动前必查）。选技能前先读本技能，比逐个翻目录快一个数量级。
agent_created: true
---

# yoyo-skill-router · 技能总索引与路由

**本技能不干活，只回答一个问题：这件事该交给哪个技能。**

盘点基线：**70 个技能**（2026-09-16 全量盘点，2026-09-22 增补 `humance-guide-annotation`）。
详细分域表见 `references/domains.md`（70 个逐个列「何时用 / 不要用 / 依赖谁 / 被谁依赖」）。

---

## 一、选技能的三个动作（按顺序，别跳）

1. **先认业务域**（下面第二节）—— 12 个域，任务通常只落在 1 个域里。
2. **再查冲突表**（第三节）—— 如果任务里出现了「发布 / PPT / PDF / 海报 / 图片 / 竞品 / 合规 / 校验」这类词，**必须查表**，否则会摇摆。
3. **最后看来源**（第五节）—— 分发技能（市场/SkillHub 装的）**不要改结构**，改了会被升级覆盖。

---

## 二、12 个业务域全景

| 域 | 数量 | 干什么 | 代表技能 |
|---|:--:|---|---|
| ① **慧思站点运营** | 9 | 资讯采集→飞书→前端发布 / 流量数据 / SEO 收录 / 邮件触达 / 知识卡片 | `overseas-news-daily` `baidu-tongji-analytics` `humance-email-push` |
| ② **出海合规与对客交付** | 8 | 用工合规评估 / 法律检索 / 合同模板校验 / 员工手册 / 合规指南 PPTX | `huisi-employment-compliance` `overseas-legal-compliance__skillhub` |
| ③ **售前与商务** | 5 | 客户画像 / 竞品对标 / 企业信息查询 / 企微 Agent 场景 | `xinfushe-client-portrait` `overseas-hr-benchmark` |
| ④ **报告与文档生产** | 6 | 薪酬带宽 PDF / PDF 排版 / PDF 处理 / HTML 转 PDF / 转 Markdown | `client-salary-band-report` `pdf-report-layout` `pdfkit-py` |
| ⑤ **PPT / 演示** | 3 | PPTX 生成 / 网页 PPT / 述职大纲 | `pptx-generator` `guizang-ppt-skill` `performance-review-outline` |
| ⑥ **设计与原型** | 5 | UI 改造原型 / 一页纸海报 / 通用设计 / 前端界面 | `ui-revamp-prototype` `one-page-insight-poster` |
| ⑦ **小红书内容** | 10 | 发布 / 编排 / 数据研究 / 文案 / 卡片 / 视频总结 | ⚠️ **冲突最密集区** |
| ⑧ **其它平台发布** | 1 | 微信公众号草稿箱 | `mp-draft-push` |
| ⑨ **飞书 / Lark** | 4 | Lark CLI 全能套件 / 排障 / 文档归档 / 乐享知识库 | `lark-unified` `lark-cli-troubleshooting` |
| ⑩ **图像生成** | 2 | Gemini 图像 / 火山引擎 Seedream | `nano-banana-pro` `seedream-image-gen` |
| ⑪ **金融（财搭子）** | 8 | 行情 / 基金 / 宏观 / 筛选 / 持仓 / 自选 | `caidazi-*` ✅ **内部互指最健康的范本** |
| ⑫ **技能与记忆自维护** | 9 | 编排 / 质量校验 / 记忆分层 / 同步仓 / 发布市场 | `yoyo-agent-swarm` `yoyo-qc-auditor` `memory-layering` |

> ⚠️ **注意 `overseas-*` 有三种含义**：站点运营（`overseas-news-daily`）／合规（`overseas-legal-compliance__skillhub`）／商务（`overseas-hr-benchmark`）—— 前缀不区分业务，必须看全名。
> ⚠️ **`huisi-*` / `humance-*` / `xinfushe-*` 同属一家**（慧思 Humance 与薪福社出海体系），不是三家公司。

---

## 三、⭐ 冲突路由表（本技能核心，10 组）

**遇到这些词，按表走唯一入口，不要自己挑。**

### 3.1 🔴 「小红书发布」（全站最大冲突：10 个技能认领「小红书」，8 个认领「发布」）

| 场景 | **唯一入口** | 说明 |
|---|---|---|
| 「一键」「端到端」「写完直接发」 | **`xhs-one-click-publish`** | 编排层：调研→写→图→发布→验证，**Credit 效率导向**（目标 3-4 轮） |
| 已有内容，只差「发出去」 | **`xiaohongshu-publisher`** | 发布执行器 + **发布技术真相源**（Creator Platform DOM、Shadow DOM 发布按钮、防检测、登录态持久化） |
| 需要**登录态的搜索 / 评论 / 点赞 / 收藏 / 主页抓取** | **`xhs-automation-suite`** | 交互能力层，基于已登录真实浏览器；**不做发布**（发布流转 publisher） |
| **只读**数据分析：选题 / 竞品 / 趋势 / 博主 / 评论 | **`xhs-research`** | socialdatax 付费 API，**无需浏览器登录**；需 `SOCIALDATAX_API_KEY` |
| 贴**单条笔记 URL** 要解析内容 | `content-analyzer` | 也支持抖音；批量洞察仍走 `xhs-research` |
| 贴**单条视频**要转文字总结 | `xhs-video-summary` | 提取文案 + 转录语音 + 总结 |
| 小红书**文案改写 / 种草文案** | `slfcys-xhs-expert` | ⚠️ `xhs-rewriter-skill` 与它功能重合（待合并），**默认走前者** |
| 生成小红书**趋势/榜单卡片图** | `xhs-trending-cards` | 输出 PNG，可一键下载 |
| 查**当日爆款笔记** | `xhs-daily-breaking` | 按赛道查当天热度最高笔记 |

### 3.2 「PPT / 演示」

| 场景 | 唯一入口 |
|---|---|
| 要**可编辑 .pptx 文件** | `pptx-generator` |
| 要**网页版横向翻页 PPT**（单 HTML、杂志风/瑞士风） | `guizang-ppt-skill` |
| **述职 / 续签 / 任职资格答辩大纲**（输出逐页大纲，不是成品 PPT） | `performance-review-outline` |
| 按**已有某国合规指南模板克隆**成新国家版本 | `compliance-guide-pptx`（其上是工作流 `compliance-guide-agent`） |

### 3.3 「PDF」

| 场景 | 唯一入口 |
|---|---|
| 操作**已存在的 PDF 文件**（读/合并/拆分/水印/加密/OCR/签名） | `pdfkit-py` |
| 用**代码生成报告并排版**（reportlab + 中文字体 + 多币种） | `pdf-report-layout`（薪酬报告再上一层是 `client-salary-band-report`） |
| **HTML 成品转 A4 PDF**（要带水印、去浏览器页眉页脚） | `html-to-pdf-print` |

### 3.4 「海报 / 卡片」

| 场景 | 唯一入口 |
|---|---|
| 输入 = **已得的分析结论**（根因/数据/建议） | `one-page-insight-poster` |
| 输入 = **humancehr.com 文章 URL 或选题**（输出 HTML + 截图 + 分享文案） | `country-knowledge-poster` |
| 输入 = **榜单/趋势数据**（输出 PNG 卡片） | `xhs-trending-cards` |

### 3.5 「图片生成」

| 场景 | 唯一入口 |
|---|---|
| 需要 **Gemini 能力 / 4K / 图生图编辑**（nano-banana） | `nano-banana-pro` |
| **火山引擎 / 需要 ARK_API_KEY / 国内链路** | `seedream-image-gen` |
| 落成**设计稿/海报/视觉艺术**（不是照片级生成） | `canvas-design` |

### 3.6 「竞品 / 对标」

| 场景 | 唯一入口 |
|---|---|
| **工具市场对标方法论** + 外部竞品工具盘点（Deel/NACSHR/1EOR/BIPO/Knit） | `overseas-hr-benchmark` |
| **薪福社自家服务与竞品的对比知识库**（含猎头主推产品画像、客户画像 SOP） | `xinfushe-overseas-hr` |
| **企业工商信息**（城市/省份/大区/行业） | `company-info-lookup` |

> ✅ 这两个竞品技能已**双向互指**，是健康样板，勿动。

### 3.7 「合规 / 法律」

| 场景 | 唯一入口 |
|---|---|
| 要**某国用工合规评估报告**（雇佣形式/签证/薪酬社保/合同，附风险清单） | `huisi-employment-compliance` |
| 要**查某国法律法规原文**（230+ 法域，自动装 MCP） | `overseas-legal-compliance__skillhub` |
| 要**出海法律研究**（制裁/出口管制/贸易救济/ODI/境外诉讼） | `cue-overseas-expansion__skillhub` |
| 要**招聘环节合规指引**（跨国招聘劳动法/签证/跨境薪酬） | `mayihr-recruitment-324__skillhub` |
| 要**校验合同模板数据质量**（防 AI 伪造、链接失效、以法代模） | `contract-verifier` |
| 要**生成员工手册** | `employee-handbook-generator` |

### 3.8 「飞书 / Lark」

| 场景 | 唯一入口 |
|---|---|
| **通用 Lark 操作**（消息/文档/表格/多维表/日历/邮件/任务/审批/会议） | **`lark-unified`**（200+ 命令，18 域，默认入口） |
| **从零建「资讯日报」Base 并写中文内容** | `feishu-bitable-news-daily`（独有：建表后授权、中文写入坑） |
| **多维表格归档到文档归档库** | `feishu-doc-archive` |
| **乐享（lexiangla.com）知识库**操作 | `lexiang-knowledge-base`（**不是飞书产品**） |
| **lark-cli 报错**（91402 / needs_refresh / token_missing） | `lark-cli-troubleshooting` |

### 3.9 「校验 / 质检」

| 场景 | 唯一入口 |
|---|---|
| **Agent / 自动化任务的可靠性校验**（目标·过程·结果三层，P0/P1/P2 分级） | `yoyo-qc-auditor`（**被 5 个技能引用的质量闸**） |
| 合同模板**数据质量**校验 | `contract-verifier` |
| PDF 交付件**排版质检** | `pdf-report-layout`（内含 PyMuPDF 校验） |

### 3.10 「技能与记忆自维护」

| 场景 | 唯一入口 |
|---|---|
| 复合任务**拆解派活**、写飞书工作日志 | `yoyo-agent-swarm` |
| **MEMORY.md 撞上限 / 主题散落** → 拆专题文件 | `memory-layering` |
| **把汇报里的实测数据同步进技能**（防口径漂移） | `skill-truth-source-sync` |
| 同步技能到 **GitHub 双仓 + Gitee 镜像** | `skill-sync-repo` |
| 发布技能到 **SkillHub 市场** | `skillhub-publish` |
| **运行时**报错与用户纠错的沉淀 | `self-improving-agent` |
| 给 **SKILL.md 打分并爬山优化** | `darwin-skill` |

---

## 四、依赖枢纽（改动前必查）

以下技能被多个技能引用，**改名/合并/删除前必须同步改下游**：

| 技能 | 被引用数 | 谁在引用 |
|---|:--:|---|
| `yoyo-qc-auditor` | 5 | `client-salary-band-report` `compliance-guide-agent` `overseas-news-daily` `yoyo-agent-swarm` `skill-sync-repo` |
| `yoyo-agent-swarm` | 4 | `client-salary-band-report` `wecom-agent-scenarios` `skill-sync-repo` 等 |
| `baidu-ziyuan-collect` | 3 | `aeo-humance` `lark-cli-troubleshooting` 等 |
| `overseas-hr-benchmark` | 3 | `xinfushe-client-portrait` `wecom-agent-scenarios` `xinfushe-overseas-hr` |
| `pdf-report-layout` / `html-to-pdf-print` / `compliance-guide-pptx` / `company-info-lookup` | 各 2 | 交付链路中段 |

---

## 五、来源三分（决定能不能改）

| 来源 | 数量 | 判据（看 frontmatter） | 权限 |
|---|:--:|---|---|
| **巴蒂自建** | 30 | `agent_created: true` | ✅ 可自由改 |
| **市场分发** | 15 | 有 `visibility` / `display_name` / `version` | ⚠️ **不改结构**，只可加互指说明（升级会覆盖） |
| **SkillHub 安装** | 3 | 目录名带 `__skillhub` | ⚠️ 同上 |
| **来源待判** | 21 | 三者皆无 | 🟡 确认后再动 |

分发 15 个：`brand-guidelines` `canvas-design` `company-info-lookup` `compliance-guide-agent` `compliance-guide-pptx` `guizang-ppt-skill` `huisi-employment-compliance` `impeccable` `lark-unified` `lexiang-knowledge-base` `markitdown-skill` `nano-banana-pro` `pdfkit-py` `pptx-generator` `skillhub-publish`

---

## 六、⚠️ 自动化绑定现状（改技能前必读）

**11 个自动化的 `skills_json` 全部为空数组** —— 技能全靠 prompt 里的**文字点名**。这意味着：

- 技能**改名 / 迁移 / 删除**时，自动化**不会报错，只会静默降级**
- 现有 11 个自动化中，**5 个连技能名都没写**（`每日出海SEO关键词提取` `小红书相关搜索采集` `百度+必应推荐词采集` `百度统计周报` `积存金价格监控`）

**改技能名之前**：先跑一次引用体检（在 `workbuddy.db` 的 `automations` 表搜技能名），确认没有自动化点名它。

---

## 七、维护规则（新增技能必须登记）

1. **新技能落地后，必须在本文件第二节 + `references/domains.md` 里登记**，否则它等于不存在（Agent 查不到）。
2. **新增技能前先查本文件第三节** —— 如果触发的词已经被某个技能认领，**不要新建，改为扩展现有技能**（这是「70 个里只有 1 组真重复」能维持住的原因）。
3. **description 里写清「不用于 X（请用 Y）」** —— 光写「我做什么」不够，冲突组的技能必须写边界。
4. **改目录名前**，先做两件事：跑依赖枢纽检查（第四节）+ 自动化引用体检（第六节）。
5. 本文件的索引**必须带状态**（现行 / 待合并 / 勿动），否则下次会拿错工具。
