# 技能分域详表（70 个 · 2026-09-16 盘点 · 2026-09-22 增补）

> 配套 `SKILL.md`（含冲突路由表）。本表逐技能列「定位 / 何时用 / 不要用 / 来源」。
> 来源标记：🟢 自建可改（`agent_created`）｜🔵 市场分发不改｜🟣 SkillHub 不改｜⚪ 来源待判

---

## ① 慧思站点运营（10）

| 技能 | 定位 | 何时用 | 不要用 | 来源 |
|---|---|---|---|---|
| `overseas-news-daily` | 出海资讯日报采集主流程（74KB，最大单文件） | 每日采集→扩写→标签→竞品过滤→写飞书 | 校验补漏（那是同一自动化的 15:00 分支） | 🟢 |
| `feishu-bitable-news-daily` | 从零建资讯日报 Base + 写中文数据 | 需要**建表并授权**、遇中文写入坑 | 通用 Lark 操作走 `lark-unified` | 🟢 |
| `humance-demo-publish` | 资讯推送到前端并发布 | 把资讯 ID 推到 demo/线上前端 | 前端设计改造走 `ui-revamp-prototype` | 🟢 |
| `humance-content-baseline` | 内容库基线快照与体检（**只读**） | 「跑基线」「内容体检」「哪些内容该更新」 | 发布/写入（本技能不写，落标走 `humance-guide-annotation`） | 🟢 |
| `humance-guide-annotation` | 国别指南「更新标注」**落标执行器**（写侧，2026-09-22 建） | 「国别指南落标」「批量更新指南」「看标注预览」「回滚某国指南」 | 只读盘点走 `humance-content-baseline`；资讯推前端走 `humance-demo-publish` | 🟢 |
| `baidu-tongji-analytics` | 百度统计取数与**口径规范真相源** | 拉/核对流量数据、判断数字该怎么口径化 | SEO 收录数据走 `baidu-ziyuan-collect` | 🟢 |
| `baidu-ziyuan-collect` | 百度搜索资源平台收录采集（Bridge） | 采集关键词/热门页面/索引量并推飞书 | 流量分析走 `baidu-tongji-analytics` | 🟢 |
| `aeo-humance` | 出海 HR 内容 AEO 布局 | 让内容出现在 ChatGPT/Claude/Perplexity 回答里 | 传统 SEO 收录走 `baidu-ziyuan-collect` | ⚪ |
| `humance-email-push` | 客户触达邮件生成 + 去重排程 + 飞书同步 | 4 阶段分层推送、D 类召回、发件回执对账 | 单封邮件撰写（可直接写） | 🟢 |
| `country-knowledge-poster` | 文章→知识卡片海报（HTML+JPG+分享文案） | 输入是 **humancehr.com 文章 URL 或选题** | 输入是分析结论走 `one-page-insight-poster` | 🟢 |

---

## ② 出海合规与对客交付（8）

| 技能 | 定位 | 何时用 | 不要用 | 来源 |
|---|---|---|---|---|
| `huisi-employment-compliance` | 海外用工合规评估（输出评估报告） | 输入「国家/地区 + 岗位或用工场景」→ 五维度评估 + 风险清单 | 查法条原文走 `overseas-legal-compliance` | 🔵 |
| `overseas-legal-compliance__skillhub` | 全球 230+ 法域法律检索（自动装 MCP） | 「查外国法律」「GDPR」「多国法规对比」 | 需要合规**建议/报告**走 `huisi-employment-compliance` | 🟣 |
| `cue-overseas-expansion__skillhub` | Cue 出海法律合规研究 | 制裁筛查/出口管制/贸易救济/ODI/境外诉讼/海外背调 | 国内企业尽调、实时行情（明确排除） | 🟣 |
| `mayihr-recruitment-324__skillhub` | 海外招聘合规指引 | 跨国招聘→各国劳动法/签证/跨境薪酬/社保 | 需要自有产品建议走薪福社体系技能 | 🟣 |
| `contract-verifier` | 合同模板数据质量校验 | 校验采集表真实性、来源权威性、完整性 | 生成合同（本技能只校验） | 🟢 |
| `employee-handbook-generator` | 员工手册生成（11 章 + 一页纸 + 签收表） | 「写员工手册」「海外子公司手册模板」 | 单国合规评估走 `huisi-employment-compliance` | ⚪ |
| `compliance-guide-agent` | 合规指南生产**工作流**（4 环节） | 给定目标国 + 底版，端到端产出 + 自校验 + 复用循环 | 只做版式克隆走 `compliance-guide-pptx` | 🟢🔵 |
| `compliance-guide-pptx` | 克隆某国合规指南 PPTX 模板换国家数据 | 「按这个模板做 XX 国合规指南」 | 需要完整工作流走 `compliance-guide-agent` | 🟢🔵 |

> 🔵🔵 标记 = 既是自建又在分发清单里（曾被同步分发过），**改前先确认分发副本是否需同步**。

---

## ③ 售前与商务（5）

| 技能 | 定位 | 何时用 | 不要用 | 来源 |
|---|---|---|---|---|
| `xinfushe-client-portrait` | 客户画像判断 + 产品组合推荐（主推猎头） | 输入公司/线索→「这个客户推什么、怎么打」 | 工商信息查询走 `company-info-lookup` | 🟢 |
| `xinfushe-overseas-hr` | 薪福社出海服务分析**知识库** | 自家产品定位/猎头画像/客户 SOP/区域优先级 | 外部工具对标走 `overseas-hr-benchmark` | 🟢 |
| `overseas-hr-benchmark` | 工具市场**对标方法论** + 已验证结论 | 竞品工具调研、MCP 优先级判定 | 自家服务对比走 `xinfushe-overseas-hr` | ⚪ |
| `company-info-lookup` | 企业工商信息（城市/省份/大区/行业） | 批量公司名单归属判定 | 竞品分析走竞品两技能 | 🟢🔵 |
| `wecom-agent-scenarios` | 企微 AI Agent 场景评估与物料（64KB） | 「某场景能否做成企微 Agent」+ 优先级 | 非企微场景的平台评估 | 🟢 |

---

## ④ 报告与文档生产（6）

| 技能 | 定位 | 何时用 | 不要用 | 来源 |
|---|---|---|---|---|
| `client-salary-band-report` | 客户向薪酬带宽报告（**只出客户版**，含水印） | 某国某岗位薪酬带宽/薪资对标/人工成本 | 通用 PDF 排版走 `pdf-report-layout` | 🟢 |
| `pdf-report-layout` | 中文/多币种 PDF 排版规范与模板（reportlab） | 从代码生成带表格/水印的交付报告 | 操作已有 PDF 文件走 `pdfkit-py` | ⚪ |
| `pdfkit-py` | **已存在 PDF 文件**的一切操作（41KB，含 1928 个 py） | 读/合并/拆分/水印/加密/OCR/表单/签名 | 生成报告走 `pdf-report-layout` | 🔵 |
| `html-to-pdf-print` | HTML 成品 → A4 PDF（带水印、去页眉页脚） | 「导成 PDF」「打印版」「发客户用」 | 从代码造报告走 `pdf-report-layout` | 🟢 |
| `markitdown-skill` | 文档转 Markdown（PDF/Word/PPT/Excel/图片/音视频） | 「转成 Markdown」「提取文本」 | 小红书内容解析走 `content-analyzer` | 🔵 |
| `performance-review-outline` | 述职/续签/任职资格答辩**页面级大纲** | 「按模板写述职大纲」 | 生成成品 PPT 走 `pptx-generator` | 🟢 |

---

## ⑤ PPT / 演示（3）

| 技能 | 定位 | 何时用 | 不要用 | 来源 |
|---|---|---|---|---|
| `pptx-generator` | JSON→标准可编辑 PPTX（11 类型 / 5 配色） | 要 .pptx 文件 | 要网页版 PPT 走 `guizang-ppt-skill` | 🔵 |
| `guizang-ppt-skill` | 横向翻页**网页 PPT**（单 HTML，杂志风/瑞士风） | 「杂志风 PPT」「Swiss Style」「发布会风格」 | 要 .pptx 文件走 `pptx-generator` | 🔵 |
| `performance-review-outline` | （见域④） | 只出大纲，不出成品 | — | 🟢 |

---

## ⑥ 设计与原型（5）

| 技能 | 定位 | 何时用 | 不要用 | 来源 |
|---|---|---|---|---|
| `ui-revamp-prototype` | UI 改造方案（**四种交付物**：形态屏/交互图/页面流程图/精简交互原型） | 给截图或网址 + 改造需求 | 从零做品牌视觉走 `canvas-design` | 🟢 |
| `one-page-insight-poster` | 分析结论 → 一页纸说明海报 | 输入是**已得的结论** | 输入是文章 URL 走 `country-knowledge-poster` | 🟢 |
| `canvas-design` | 视觉艺术产物（PNG/PDF，80+ 字体） | 海报、设计、视觉艺术 | 界面/原型走 `ui-revamp-prototype` | 🔵 |
| `impeccable` | 生产级前端界面（组件/页面/仪表盘） | 写 React 组件、落地页、应用界面 | 改造既有页面走 `ui-revamp-prototype` | 🔵 |
| `brand-guidelines` | Anthropic 官方品牌色与字体 | ⚠️ 与慧思/薪福社业务无关 | **建议清理** | 🔵 |

---

## ⑦ 小红书内容（10）⚠️ 冲突最密集

| 技能 | 定位 | 何时用 | 不要用 | 来源 |
|---|---|---|---|---|
| `xhs-one-click-publish` | **编排层**：调研→写→图→发布→验证（省 Credit） | 「一键发布小红书」「端到端」 | 只差发布走 `xiaohongshu-publisher` | 🟢 |
| `xiaohongshu-publisher` | **发布执行器 + 技术真相源**（Creator Platform DOM/Shadow DOM/防检测） | 已有内容只差发出去 | 需要搜索/互动走 `xhs-automation-suite` | 🟢 |
| `xhs-automation-suite` | **交互能力层**（26 py，5 子能力） | 登录态搜索/评论/点赞/收藏/主页抓取 | **不做发布**（发布走 publisher） | ⚪ |
| `xhs-research` | **只读数据分析**（socialdatax API，6 视角） | 选题/竞品/趋势/博主/评论洞察，批量 | 单条 URL 解析走 `content-analyzer` | ⚪ |
| `xhs-daily-breaking` | 当日热门笔记分类查询 | 「今天各赛道爆款」「单日爆款分析」 | 长周期趋势走 `xhs-research` | ⚪ |
| `xhs-trending-cards` | 趋势/榜单卡片图（PNG 下载） | 「生成小红书卡片」「榜单图」 | 文章知识卡片走 `country-knowledge-poster` | ⚪ |
| `slfcys-xhs-expert` | 小红书文案专家（真人朋友语气，3 类内容） | 写/改写种草文案、生活分享 | ⚠️ 与 `xhs-rewriter-skill` 重合，默认走本技能 | ⚪ |
| `xhs-rewriter-skill` | 洗稿重构（994B，5 种风格参数） | ⚠️ **待合并进 `slfcys-xhs-expert`** | 默认不用 | ⚪ |
| `xhs-video-summary` | 小红书视频→文案提取+转录+总结 | 贴**视频**链接要总结 | 图文笔记走 `content-analyzer` | ⚪ |
| `content-analyzer` | 小红书/抖音**单条**笔记与博主分析 | 贴 URL 要解析 | 批量洞察走 `xhs-research` | ⚪ |

---

## ⑧ 其它平台发布（1）

| 技能 | 定位 | 何时用 | 不要用 | 来源 |
|---|---|---|---|---|
| `mp-draft-push` | 文章发到**微信公众号草稿箱** | 「发布文章」「推到公众号」 | 小红书发布走域⑦ | ⚪ |

---

## ⑨ 飞书 / Lark（4）

| 技能 | 定位 | 何时用 | 不要用 | 来源 |
|---|---|---|---|---|
| `lark-unified` | **Lark/Feishu 全能套件**（200+ 命令 / 18 域，37KB） | 一切通用 Lark 操作（消息/文档/表格/多维表/日历/邮件/任务/Wiki/审批/会议） | 乐享走 `lexiang-knowledge-base` | 🔵 |
| `lark-cli-troubleshooting` | lark-cli 报错排障手册 | 91402 NOTEXIST / needs_refresh / token_missing / 授权失败 | 正常调用走 `lark-unified` | 🟢 |
| `feishu-doc-archive` | 多维表格 → 文档归档库同步 | 在线文档资产盘点、按用途检索 | 通用表格操作走 `lark-unified` | 🟢 |
| `lexiang-knowledge-base` | 乐享知识库 MCP（lexiangla.com） | 「乐享」「知识库」操作 | **不是飞书产品**，勿混 | 🔵 |

---

## ⑩ 图像生成（2）

| 技能 | 定位 | 何时用 | 不要用 | 来源 |
|---|---|---|---|---|
| `nano-banana-pro` | Gemini 3 Pro Image（文生图 + 图生图，1K/2K/4K） | 需要 Gemini 能力 / 4K / 图像编辑 | 国内链路走 `seedream-image-gen` | 🔵 |
| `seedream-image-gen` | 火山引擎方舟 Seedream（文/图生图、多图融合、组图） | 需 `ARK_API_KEY` / 国内链路 / 组图 | 需 Gemini 能力走 `nano-banana-pro` | ⚪ |

---

## ⑪ 金融 / 财搭子（8）✅ 内部互指最健康的范本

| 技能 | 定位 | 何时用 | 来源 |
|---|---|---|---|
| `caidazi-user-assets` | **统一入口**：自选/持仓/监控任务/账户关联 | 想看或用自己在财搭子的资产 | ⚪ |
| `caidazi-asset-research` | 股票/ETF/基金/指数研究、深度分析、多标的比较 | 研究类问题 | ⚪ |
| `caidazi-stock-screener` | 自然语言选股/选基筛选 | 「帮我筛出…」 | ⚪ |
| `caidazi-fund-etf-research` | 基金/ETF 研究、筛选、诊断、对比 | 基金相关问题 | ⚪ |
| `caidazi-macro-research` | 宏观数据/政策/利率/通胀/汇率 | 宏观问题 | ⚪ |
| `caidazi-market-pulse` | 市场热点/大盘/板块/盘前盘中盘后 | 「今天市场怎么样」 | ⚪ |
| `caidazi-portfolio-review` | 基于自选/持仓/组合快照做复盘 | 「帮我复盘持仓」 | ⚪ |
| `caidazi-finance-search` | 财经新闻/公告/研报/政策搜索 | 查资讯类 | ⚪ |

> ⚠️ 仅问**最新行情/当前价格/涨跌幅**时，**不要用**本组技能，直接调 MCP `get_real_time_record`。
> ✅ 本组依赖关系清晰（`portfolio-review → asset-research → user-assets`），**是全部 69 个里最健康的样板，勿动**。

---

## ⑫ 技能与记忆自维护（9）

| 技能 | 定位 | 何时用 | 不要用 | 来源 |
|---|---|---|---|---|
| `yoyo-agent-swarm` | Agent 总管（编排/派活/汇总/写飞书日志） | 复合跨领域任务、批量处理 | 单技能能做的别走编排 | 🟢 |
| `yoyo-qc-auditor` | 质量校验（三层/P0-P2 分级/飞书台账） | 校验 Agent 或自动化的目标·过程·结果 | 数据质量校验走 `contract-verifier` | 🟢 |
| `memory-layering` | 项目记忆分层维护（拆专题/指针化） | MEMORY.md 撞上限、主题散落找不到 | 技能内部 references 治理走 `skill-truth-source-sync` | 🟢 |
| `skill-truth-source-sync` | 把实测数据同步进技能（防口径漂移） | 「同步一下」「把这批数据同步进技能」 | 记忆文件治理走 `memory-layering` | 🟢 |
| `skill-sync-repo` | 技能同步到 GitHub 双仓 + Gitee | 「同步到仓」「推技能」 | 发布到市场走 `skillhub-publish` | 🟢 |
| `skillhub-publish` | 发布技能到 SkillHub 市场 | 「发布技能到 skillhub」 | 推 Git 仓走 `skill-sync-repo` | 🟢🔵 |
| `self-improving-agent` | 运行时学习记录（报错/纠错/能力缺口） | 命令失败、用户纠正、能力不存在 | SKILL.md 优化走 `darwin-skill` | ⚪ |
| `darwin-skill` | SKILL.md 8 维评分 + 爬山优化 | 给已有技能做质量提升 | 数据同步走 `skill-truth-source-sync` | ⚪ |
| `blossom-hire` | 第三方平台 Blossom 招本地帮手 | ⚠️ 与现有业务无互指、无自动化引用 | **建议清理** | ⚪ |

---

## 待处理清单（呼应 SKILL.md 第三节）

| 优先级 | 动作 | 涉及技能 |
|:--:|---|---|
| 🟢 P0 | 合并（唯一真重复） | `xhs-rewriter-skill` → `slfcys-xhs-expert` |
| 🟢 P0 | 补双向互指 | `xiaohongshu-publisher`（零互指）、`xhs-research`、`xhs-daily-breaking`、`content-analyzer` |
| 🟡 P1 | 补边界说明 | 海报组 / 图像组 / 飞书组 / PDF 组 |
| 🟡 P1 | 自动化技能绑定体检 | 11 个自动化（`skills_json` 全空） |
| 🔴 P2 | 清理候选（需拍板） | `brand-guidelines` `blossom-hire` |
