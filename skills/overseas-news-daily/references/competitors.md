# 竞品来源过滤完整列表

采集时，每条资讯写入前必须检查「来源」字段和「原文链接」域名。命中则跳过。

## P0 核心竞品（严格过滤）

| 竞品 | 匹配规则 |
|------|---------|
| Deel | 域名 deel.com；名称含「Deel」 |
| BIPO / 必博 | 域名 bipo.com / bipo.cn；名称含「BIPO」「必博」 |
| Knit / 万领钧 | 域名 knitpeople.com.cn；名称含「Knit」「KnitPeople」「万领钧」「knitpeople」 |
| PayInOne / 薪湾 | 域名 payinone.com；名称含「PayInOne」 |
| GONEX / 高奈珂思 | 域名 gonex.com；名称含「GONEX」 |
| CDP / 薪得付 | 域名 cdpgroup.com；名称含「CDP」「薪得付」 |
| 万企帮 / Vanzbon | 名称含「万企帮」「Vanzbon」 |

## P1 重要竞品（尽量过滤）

| 竞品 | 匹配规则 |
|------|---------|
| SmartDeer | 域名 smartdeer.com；名称含「SmartDeer」 |
| Intellipro / 英特利普 | 域名 intellipro.com |
| Papaya Global | 域名 papayaglobal.com |
| Oyster HR / 泰仕达 | 域名 oysterhr.com |
| Remofirst | 域名 remofirst.com |
| Remote | 域名 remote.com |
| Globalization Partners (G-P) | 域名 globalization-partners.com |
| Multiplier | 域名 multiplier.com |
| Omnipresent | 域名 omnipresent.com |
| Oyster | 域名 oyster.com |
| 金柚网 / Joyowo | 域名 joyowo.com |
| NEEYAMO | 域名 neeyamo.com |
| Mercer / 美世 | 域名 mercer.com |
| 诚通人力 / CTHR | 域名 cthr.cn |
| Horizons / 新视野 | 域名 horizons.com |
| Remoly | 域名 remoly.com |
| Marco / Marco Pay | 域名 marcopay.com / hellomarco.com |
| hotpay / 火星云 | 域名 hotpay.cn |

## 溯源增强规则（2026-07-10）

当采集到的信息来源为出海人力资源服务公司时：

**Step 1 — 判断来源性质：** 来源字段或原文链接是否指向HR服务商官网/白皮书/博客
**Step 2 — 溯源查找：** 如引用具体政策/法规/事件，找到原发官方来源（政府公告/国际组织/权威媒体）
**Step 3 — 替换来源引用：** 以官方/权威来源为准
**Step 4 — 无法溯源则不采集：** 找不到原始政策来源则跳过

## 判定逻辑

1. 如果「来源」字段包含上述任一竞品名称（子串匹配），则跳过
2. 如果「原文链接」域名匹配竞品域名，则跳过

## 白名单（不视为竞品）

| 分类 | 来源 |
|------|------|
| 政府来源 | 中国政府网、商务部、外交部、新华社、人民网、环球网、人民日报海外版、人社部 |
| 国际组织 | ILO、OECD、World Bank、IMF、UNCTAD、WTO、欧盟委员会、欧洲议会 |
| 主流媒体 | 腾讯新闻、新浪财经、澎湃新闻、虎嗅、36氪、界面新闻、东方财富网、百度百家号、搜狐、网易 |
| 海外媒体 | Reuters、Bloomberg、Financial Times、Nikkei、日经中文网 |
| 智库 | 麦肯锡、BCG、贝恩、德勤咨询、普华永道 |
| 行业平台 | EqualOcean、大数跨境、跨境合规圈、亿邦动力 |
| 法律机构 | 方达律所、金杜律所、中伦律所、君合律所、竞天公诚 |
| 数据平台 | 10100法律数据库、天眼查、企查查 |
