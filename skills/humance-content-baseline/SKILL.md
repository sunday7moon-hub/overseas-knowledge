---
name: humance-content-baseline
description: 慧思 humancehr.com 内容库基线快照与质量体检。抓取全站 sitemap + 后台搜索 API，统计五大板块基数、字段完整率、更新空窗、脏数据，按地区优先级输出国家清单与体检报告。当用户说「跑基线」「内容体检」「校对前先摸底」「看看内容库现状」「哪些内容该更新了」时使用。只读，不做任何写操作。
agent_created: true
---

# 慧思内容库基线快照与质量体检

对 humancehr.com 五大板块做全量只读盘点，产出可 diff 的基线文件与质量体检报告。
**这是内容校对工作流的第一步**——没有基线就无法做变更检测。

## 适用时机

- 季度/年度内容校对启动前
- 怀疑某板块数据有问题时
- 需要「哪些国家该优先更新」的决策依据时
- 内容发布流程跑完后做验收对比

## 硬约束

| 约束 | 说明 |
|------|------|
| **只读** | 全程只 GET，禁止任何 POST/PUT/DELETE |
| **不用 MCP** | MCP `search_country_guide` 只索引 7/76 条，会漏 90% 内容。必须走 sitemap + `/api/search` |
| **不代为定性涉地区表述的脏数据** | 如 slug 出现台湾等地区表述异常，只标记为「待人工确认」，不自作主张定性 |

## 执行步骤

### 1. 抓取基线数据

复用脚本模板（位于 `~/.workbuddy/skills/humance-content-baseline/scripts/fetch_baseline.py`），或按以下要点自写：

```python
# 三个数据源
# A. sitemap 索引 → 4 个子表
#    https://www.humancehr.com/sitemap.xml
#      → sitemap-pages.xml (12)  ← 只有静态页，忽略
#      → sitemap-articles.xml (2315)  ← 知识库/薪酬/假勤/指南 都在这
#      → sitemap-holiday.xml (157)
#      → sitemap-regulation.xml (0)  ← 常年为 0，法规不进 sitemap
# B. 后台搜索 API（法规的唯一数据源）
#    https://www.humancehr.com/api/search?q=<词>&page=N&pageSize=100
#    返回 {articles:[], regulations:[], pagination:{page,pageSize,pageCount,total}}
```

**分页关键行为**（踩过坑，务必注意）：
- 分页**是生效的**，但 `regulations` 只在前 3 页返回（100 + 100 + 12 = **212 条**），第 4 页起为 0
- `articles` 可翻 23 页（2255 条）
- `pagination.total=2255` 是 articles 口径，不代表法规数
- 抓法规：翻 3 页即全；抓文章：翻到 `len(a) < 100` 为止

### 2. 字段完整性检查（法规）

必查 9 个字段的空值率：`countryTag / locale / category / publishYear / title / slug / contentUrl / pdfUrl / updatedAt`，外加 `summary` 缺失率与 `content` 长度分布。

**已知长期缺陷**（2026-09 实测，每次体检都要复查是否修复）：
- `category` 100% 空
- `publishYear` 100% null
- `summary` 100% 缺失

### 3. 更新空窗分析

- 从 sitemap 的 `lastmod` 算每条内容距今天数
- 板块级：按 lastmod 月份分布画直方图，找「停更月份」
- 条目级：标记超 90 天未更新的条数与占比，列出闲置最久 Top N

### 4. 国家优先级分级

地区优先级沿用 Yoyo 既定规则：

| 优先级 | 地区 |
|:------:|------|
| 🔴 高 | 东南亚、中东、欧洲（欧盟+英国+申根） |
| 🟡 中 | 拉美、中亚独联体、非洲 |
| 🟢 低 | 北美、东亚、大洋洲 |

国家→地区映射表见 `references/country-region-map.json`。未命中的标「⚪待定」并列出，由 Yoyo 补充。

排序规则：**优先级升序 → 闲置天数降序**（同优先级下越久没更新越靠前）。

### 5. 脏数据检测

自动化检出以下几类（正则 + 规则）：

| 类型 | 检测方式 |
|------|---------|
| slug 拼接 | slug 中出现两个及以上 `-country-guide` |
| 重复条目 | slug 以 `-1` / `-2` 结尾（需与无后缀版本比对合并） |
| countryTag 异常 | `len(countryTag) > 12`（正常国名不超过 12 字） |
| 命名不统一 | 与归一化表比对（蒙古国→蒙古、沙特阿拉伯王国→沙特阿拉伯） |
| 有法规无指南 / 有指南无法规 | 两侧国家集合做差集 |

### 6. 输出

| 文件 | 内容 |
|------|------|
| `baseline_regulations.csv` | 法规全量 15 字段 |
| `baseline_articles.csv` | 文章元数据 |
| `baseline_sitemap.csv` | sitemap + section + lastmod |
| `priority_countries.csv` | 优先级 / 地区 / 国家 / lastmod / 闲置天数 / 法规数 / 备注 |
| 体检报告 .md | 5 条结论 + 脏数据清单 + 高优先级清单 + 下一步建议 |

报告结构：板块基数 → 字段完整率 → 覆盖均衡度 → 更新空窗 → 年度数据准备度 → 脏数据清单 → 优先级清单 → 下一步（标注哪些动作依赖 Strapi Token）。

## 门禁

- 抓取失败重试 3 次仍失败 → 记录并跳过，不中断整体
- 单板块条数环比上期波动 >20% → 标记为「疑似异常」，需人工确认
- 任何涉地区表述的脏数据 → 只标记，不处置

## 复现

```bash
cd ~/.workbuddy/skills/humance-content-baseline/scripts
/Users/yoyo/.workbuddy/binaries/python/envs/default/bin/python fetch_baseline.py <输出目录>
```

下次校对时重跑一次，与新快照做 diff 即为变更清单。

## 关联

- 上游：无
- 下游：内容校对工作流（A15 内容校对官）
- 同域：A9 薪酬带宽报告官（用 remuneration 板块数据）、A13 素材生成官
- 依赖技能：`company-info-lookup`（国别归属查询）、`overseas-legal-compliance`（法规核查）
