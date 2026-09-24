---
name: feishu-bitable-news-daily
description: 通过 lark-cli 创建飞书多维表格（Base），设计表结构（字段），写入资讯/新闻数据。适用于搭建出海资讯日报、行业日报、知识库等场景，配合 Coze 或自动化推送使用。 ⚠️ 通用 Lark 操作（消息/文档/表格/多维表查询/日历/审批）请用 `lark-unified`；本技能只在「从零建资讯日报 Base 并写中文内容」这一场景用（独有：建表后授权、中文写入坑）。
agent_created: true
---

# Feishu Bitable News Daily

## 定位与边界（与 lark-unified 的分工）

| 你要做的事 | 该用哪个技能 |
|---|---|
| **从零建「资讯日报」Base + 写中文数据** | **本技能** ← |
| 通用 Lark 操作（消息/文档/表格/多维表查询/日历/邮件/审批） | `lark-unified`（200+ 命令，默认入口） |
| 多维表格 → 归档库同步 | `feishu-doc-archive` |
| lark-cli 报错 | `lark-cli-troubleshooting` |

本技能的两个独有价值：**建表后立即授予管理员权限**、**中文内容写入的转义处理**。

---


通过 lark-cli CLI 快速搭建飞书多维表格，用于每日资讯/新闻的存储、筛选和推送。

## Prerequisites

- lark-cli 已安装并配置（`lark-cli config show` 含 `app_id`）
- 飞书开放平台已授权 `base:*` 相关权限（base:table:read/write、base:field:read/write、base:record:read/write）
- 使用 `--as bot` 身份操作

## Important: Writing Records with Chinese Content

When writing records that contain Chinese text via `--json`, shell escaping can break JSON parsing. **Use Python subprocess to pass JSON directly** instead of shell inline:

```python
import json, subprocess

LARK = "/Users/yoyo/.workbuddy/binaries/node/cli-connector-packages/bin/lark-cli"
os.environ["LARK_CLI_NO_PROXY"] = "1"  # Disable proxy to avoid TLS timeout

record = {
    "标题": "资讯标题",
    "正文": "带有中文引号\u201c和换行\\n的内容",
    "分类": "全球动态",
    "日期": "2026/06/03"
}

result = subprocess.run(
    [LARK, "base", "+record-upsert",
     "--base-token", "<token>",
     "--table-id", "<table_id>",
     "--json", json.dumps(record, ensure_ascii=False),
     "--as", "bot"],
    capture_output=True, text=True, timeout=30
)
```

Key rules:
1. Use `json.dumps(record, ensure_ascii=False)` — `ensure_ascii=False` preserves Chinese characters
2. Replace Chinese double quotes `"..."` with Unicode escapes `\u201c...\u201d` inside the JSON string values
3. Set `LARK_CLI_NO_PROXY=1` to avoid HTTPS proxy timeout (common issue)
4. Do NOT use `--json @file.json` — the relative-path requirement fails in automation contexts
5. The `\n` in body text should be literal newline escapes (two characters: `\` and `n`) in the JSON string

## Workflow

### 1. 创建多维表格（Base）

```bash
lark-cli base +base-create --as bot --name "出海资讯日报" --time-zone "Asia/Shanghai"
```

返回的 `base_token` 是后续所有操作的基础。

### 1.5 关键步骤：创建后立即授予管理员权限

Base 创建后，**必须立即**给邱月（ou_YOUR_OPENID）授予最高管理权限，否则网页端无法访问。

```bash
lark-cli api POST "/open-apis/drive/v1/permissions/<base_token>/members?type=bitable" \
  --data '{"member_id":"ou_YOUR_OPENID","member_type":"openid","perm":"full_access"}' \
  --as bot
```

⚠️ **每次创建 Base 后都必须执行这一步**，否则邱月无法在飞书网页端看到表格。

### 2. 管理表结构

#### 列出已有表
```bash
lark-cli base +table-list --base-token <base_token> --as bot
```

#### 重命名表（默认表名为"数据表"）
```bash
lark-cli base +table-update --base-token <base_token> --table-id <table_id> --name "出海资讯日报" --as bot
```

#### 删除默认字段
```bash
# 先列出字段获取 field_id
lark-cli base +field-list --base-token <base_token> --table-id <table_id> --as bot

# 删除不需要的字段（主字段不可删，需先改名）
lark-cli base +field-delete --base-token <base_token> --table-id <table_id> --field-id <field_id> --as bot --yes
```

#### 修改主字段名称
```bash
# 默认主字段"文本"需先改名
lark-cli base +field-update --base-token <base_token> --table-id <table_id> --field-id <field_id> --json '{"name":"标题","type":"text","style":{"type":"plain"}}' --as bot --yes
```

#### 创建字段

字段 JSON 格式示例：

| 类型 | JSON 示例 |
|------|-----------|
| 文本 | `{"name":"标题","type":"text","style":{"type":"plain"}}` |
| 单选 | `{"name":"分类","type":"select","multiple":false,"options":[{"name":"商业动态"},{"name":"政策更新"}]}` |
| 多选 | `{"name":"标签","type":"select","multiple":true,"options":[{"name":"东南亚"},{"name":"北美"}]}` |
| 日期 | `{"name":"日期","type":"datetime","style":{"format":"yyyy/MM/dd"}}` |
| 日期时间 | `{"name":"推送时间","type":"datetime","style":{"format":"yyyy/MM/dd HH:mm"}}` |
| 复选框 | `{"name":"是否精选","type":"checkbox"}` |

注意：
- 文本不支持 `multiline` 类型，只能用 `plain`（但可以存长文本）
- API 对同一表有字段创建并发限制，建议逐个创建
- 启用高级权限可避免限制：`lark-cli base +advperm-enable --base-token <base_token> --as bot`

```bash
lark-cli base +field-create --base-token <base_token> --table-id <table_id> --json '<json>' --as bot
```

### 3. 写入记录

使用字段名（不是字段ID）作为 key，CellValue 格式：

| 字段类型 | CellValue 格式 |
|----------|---------------|
| 文本 | `"字符串"` |
| 单选 | `"选项名"` |
| 多选 | `["选项1", "选项2"]` |
| 复选框 | `true` / `false` |
| 日期 | `"2026/06/02"` |

```bash
lark-cli base +record-upsert --base-token <base_token> --table-id <table_id> --json '{"标题":"新闻标题","分类":"商业动态","正文":"内容...","原文链接":"https://...","来源":"来源名","摘要":"一句话摘要","标签":["标签1","标签2"],"日期":"2026/06/02","是否精选":true,"推送状态":"待推送"}' --as bot
```

### 4. 查询记录

```bash
lark-cli base +record-list --base-token <base_token> --table-id <table_id> --as bot
```

### 5. 推荐表结构（出海资讯日报）

| 字段 | 类型 | 说明 |
|------|------|------|
| 标题 | 文本（主字段） | 资讯标题 |
| 正文 | 文本 | **500-800字**，含引用来源和原文链接引用 |
| 分类 | 单选 | **全球动态 / 法规更新 / 风险预警** |
| 来源 | 文本 | 新闻来源 |
| 原文链接 | 文本 | 来源链接 |
| 摘要 | 文本 | 一句话摘要 |
| 日期 | 日期 | yyyy/MM/dd |
| 标签 | 多选 | 东南亚/北美/欧洲/中东/EOR/关税/合规/跨境电商/AI |
| 是否精选 | 复选框 | 入选每日10条推送标记 |
| 推送状态 | 单选 | 待推送 / 已推送 |
| 推送时间 | 日期时间 | yyyy/MM/dd HH:mm |

### 6. 正文写作规范

每篇正文要求 **500-800字**，参考格式：

```
[事件概述] - 1-2句话说明最新动态
[背景分析] - 市场/行业背景
[影响解读] - 对出海企业的具体影响
[关键数据] - 引用具体数字（金额、增长率、时间节点等）
[来源引用] - 标注原文来源及链接
```

### 7. 内容配比

每天准备 16~20 条，精选 10 条推送：

| 分类 | 推送占比 | 每日准备量 |
|------|---------|-----------|
| 全球动态 | ~50% | 8~10条 |
| 法规更新 | ~30% | 5~6条 |
| 风险预警 | ~20% | 3~4条 |

### 8. 内容价值分级与排除规则

采集前按以下分级判断每条内容的采集价值，低价值内容直接跳过。

**信息价值分级：**

| 级别 | 类型 | 采集策略 |
|------|------|---------|
| P0 必须采集 | 劳动法修订、EP/工签政策、最低工资上调、社保公积金改革、解雇赔偿规则、个税调整 | 不限来源，有就采 |
| P1 值得采集 | 工时/加班政策修订、外籍员工配额、数据隐私合规、工会劳资、招聘趋势、养老金改革 | 有政策变化或具体数字时采 |
| P2 按需采集 | EOR行业动态、海外公司注册政策、跨文化管理、合规白皮书 | 仅限政府/权威媒体/知名智库 |
| P3 不采集 | 无出海视角国内新闻、纯品牌PR稿、股市行情、融资新闻（无用工视角）、产品发布 | 直接跳过 |

**排除规则（命中任意一条即跳过）：**
- 含中国领导人姓名的内容
- 涉政治敏感议题（台湾、新疆、香港等）
- 纯品牌宣传/PR稿
- 纯粹股市行情/加密货币
- 纯国内新闻无出海视角
- 公司融资/产品发布新闻（无用工合规关联）
- EOR/HR服务商发布的品牌内容

### 9. 竞品来源过滤规则（采集时自动拦截）

当采集出海资讯时，必须按以下规则过滤竞品来源，命中则跳过。

**P0 核心竞品（严格过滤）：**
1. Deel — deel.com
2. BIPO / 必博 — bipo.com / bipo.cn
3. Knit / 万领钧 — knitpeople.com.cn（含别名）
4. PayInOne / 薪湾 — payinone.com
5. GONEX / 高奈珂思 — gonex.com
6. CDP / 薪得付 — cdpgroup.com
7. 万企帮 — wanqibang.com

**P1 重要竞品（尽量过滤）：**
8. SmartDeer — smartdeer.com
9. Intellipro / 英特利普 — intellipro.com
10. Papaya Global — papayaglobal.com
11. Oyster HR / 泰仕达 — oysterhr.com
12. Remofirst — remofirst.com
13. Remote — remote.com
14. Globalization Partners (G-P)
15. Multiplier — multiplier.com
16. Omnipresent — omnipresent.com
17. Oyster — oyster.com
18. 金柚网 / Joyowo — joyowo.com
19. NEEYAMO — neeyamo.com
20. Mercer / 美世 — mercer.com
21. 诚通人力 / CTHR — cthr.cn
22. Horizons / 新视野 — horizons.com
23. Remoly — remoly.com
24. Marco / Marco Pay — marcopay.com
25. hotpay / 火星云 — hotpay.cn

**判定逻辑（必须严格）：**
- 「来源」字段**包含**上述任一竞品名称（子串匹配）→ 跳过
  - 例如：「知乎/SmartDeer」包含 SmartDeer → 跳过
  - 例如：「万领钧Knit People」包含 Knit → 跳过
- 「原文链接」域名匹配竞品域名 → 跳过

### 10. 同质新闻判定与去重规则（写入前执行）

采集到新资讯后，写入前必须执行同质检查。同质判定包括三类场景：

**场景A — 与已有「待推送」记录重复：**
先查询表中所有「推送状态=待推送」的标题和原文链接，逐条比对新采集的资讯。

同质判定标准（命中任意一条即同质）：
1. 标题提及同一家企业且描述同一类事件
2. 标题提及同一条法规/政策
3. 标题提及同一国家/地区的同一政策变化
4. 标题与已有记录的原文链接指向同一URL

去重逻辑：对比来源权威性：**政府来源 > 主流媒体 > 行业平台 > 其他**，保留更权威的

**场景B — 同一批次采集内的重复：**
同批次多条结果指向同一事件时，只保留来源权威性最高的那条

**场景C — 低价值重复（无增量信息）：**
来源同档时，保留含具体数据/专家观点/独家信息的那条

## Common Failures

| Symptom | Root Cause | Fix |
|---------|-----------|-----|
| `base:app:create` permission denied | 飞书应用未开通 base 系列权限 | 到开放平台→权限管理→添加 `base:*` 权限并发布新版本 |
| `the method：OpenAPIAddField limited` | 免费表 API 字段创建并发限制 | 逐个创建字段，启用高级权限 |
| `The last table cannot be deleted` | 表不能少于1个 | 先重命名再修改字段，不要删除 |
| `primary field cannot be deleted` | 主字段不可删除 | 先更新主字段名称作为标题字段 |
| `Multi-select not allowed` 用 `type` 设为 `"select"` + `multiple: true` | 多选用单选字段 + multiple 参数 | 使用 `"type":"select","multiple":true` |
