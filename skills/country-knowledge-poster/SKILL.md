---
name: country-knowledge-poster
description: >
  Given a humancehr.com article URL or topic, fetch the article content,
  generate an editable poster (.html) + screenshot (.jpg) + share copy text.
  Triggered when user asks to create/share a poster/knowledge-card/image from an
  HR/policy article. 输入是**已得的分析结论**（非文章）请用 `one-page-insight-poster`。
agent_created: true
disable-model-invocation: true
---

# Country Knowledge Poster Skill

## 定位与边界

| 输入是什么 | 该用哪个技能 |
|---|---|
| **humancehr.com 文章 URL 或选题**（输出 HTML + 截图 + 分享文案） | **本技能** ← |
| 一段**已得的分析结论**（根因 / 数据 / 建议） | `one-page-insight-poster` |
| 榜单 / 趋势数据（输出 PNG 卡片） | `xhs-trending-cards` |

---


Generate a social-media-ready knowledge card poster for HR/policy country articles.
Outputs an editable `.html` file, a rendered `.jpg` image, and a share copy text.
Suitable for WeChat groups / Feishu / social sharing.

## When to use

- User says "做一张海报/知识卡片" or provides a humancehr.com article URL.
- User provides a text topic or summary and wants a poster + share copy.
- User wants to turn a policy update / country guide into shareable content.

## Workflow

### Step 0: 重复链接检查（必须先做）

Before generating any poster, check if the article URL has been used this month:

1. Grep the project directory for the article URL slug: `Grep` for the slug in `*.md` and poster files
2. 搜索当月所有慧思出海早报（`慧思出海早报_YYYYMM*.md`）和海报目录（`poster/*`）
3. **如果发现重复**：告诉用户具体在哪天哪个渠道用过，先确认再继续
4. **如果未发现重复**：正常进入 Step 1

> ⚠️ 不得跳过此步骤。同一个月不应重复推送同一篇文章。

### Step 1: 获取文章内容

If the user provides a URL:
1. Use `WebFetch` to fetch the full article content from the URL
2. 提取标题、正文、关键数据（日期/百分比/金额/政策变化点）
3. 判断文章所属地区（欧洲/东南亚/拉美/中东/北美/全球）

If the user provides only a topic/title (no URL):
1. 直接根据用户提供的信息判断地区
2. 根据常识填充数据结构

### Step 2: 生成分享文案

基于已获取的内容，生成分享文案，格式如下：

```
【知识卡片】🇽🇽 [标题关键词]

[2-3句文章核心内容摘要]

📌 企业需关注：
• [行动项1]
• [行动项2]
• [行动项3]

👉 查看全文：[URL]
```

- 如果有URL，放在最后；如果用户只给了主题没有URL，则省略"查看全文"
- 行动项来源于文章中的合规建议/风险提示，每条≤25字
- 摘要控制在80字以内

### Step 3: 确定配色方案

Use these header gradients based on region (overrides the template's default):

| Region | Gradient | CSS vars |
|--------|----------|----------|
| Europe | `linear-gradient(135deg, #1E3A5F, #2B5797)` (navy blue) | `--header-start: #1E3A5F; --header-end: #2B5797; --header-dark: #142946; --accent: #2B5797; --accent-light: #E8F0FA; --accent-border: #BBDEFB; --accent-text: #1565C0` |
| Southeast Asia | `linear-gradient(135deg, #006633, #00994D)` (green) | `--header-start: #006633; --header-end: #00994D; --header-dark: #004D26; --accent: #00994D; --accent-light: #E8F5E9; --accent-border: #A5D6A7; --accent-text: #2E7D32` |
| Latin America | `linear-gradient(135deg, #009c3b, #00c853)` (green-yellow) | `--header-start: #009c3b; --header-end: #00c853; --header-dark: #006B28; --accent: #00c853; --accent-light: #E8F5E9; --accent-border: #A5D6A7; --accent-text: #2E7D32` |
| Middle East | `linear-gradient(135deg, #8B4513, #D2691E)` (desert gold) | `--header-start: #8B4513; --header-end: #D2691E; --header-dark: #5C2E0D; --accent: #D2691E; --accent-light: #FFF3E0; --accent-border: #FFCC80; --accent-text: #E65100` |
| North America | `linear-gradient(135deg, #1a237e, #283593)` (deep indigo) | `--header-start: #1a237e; --header-end: #283593; --header-dark: #0F1552; --accent: #283593; --accent-light: #E8EAF6; --accent-border: #C5CAE9; --accent-text: #283593` |
| Default/General | `linear-gradient(135deg, #1E3A5F, #2B5797)` (navy blue) | Same as Europe |

### Step 4: 填充海报内容

Read the user-provided article text or fetched content. Extract:

- **标题标签** (`.title-tag`): `🇽🇽 地区+类别` (e.g., "🇸🇬 新加坡用工政策")
- **主标题** (`.title-main`): 2行，第1行重磅信息，第2行关键词
- **高亮数据条** (`.highlight-bar`): 5项关键数据（金额/日期/百分比/政策要点），每项含数字+标签
- **Q&A问题** (`.qa-head .q-text`): 从企业决策者视角出发的痛点问题，自然直接
- **三大要点** (`.step-card` ×3): 纵向3行，左蓝色圆形编号，每行含标题+描述（≤35字）
- **核心数据** (`.fact-grid`): 2×2网格，含fact-title + fact-desc
- **底部双栏** (`.bottom-row`): 左绿（合规底线）+ 右橙（合规风险），描述≤40字
- **行动清单** (`.risk-tip`): 5项，用①②③④⑤编号

### Step 5: 生成海报HTML

1. Copy assets to poster directory:
```bash
cp /Users/yoyo/.workbuddy/skills/country-knowledge-poster/assets/logo.png ./poster/
cp /Users/yoyo/.workbuddy/skills/country-knowledge-poster/assets/qr_code.jpg ./poster/
```

> 💡 本地环境 Chrome 路径：`/Users/yoyo/Library/Caches/ms-playwright/chromium-1228/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing`
> `scripts/screenshot_poster.js` 默认未指定 executablePath 会报错（找不到默认 chromium），需在 `chromium.launch({...})` 中传入 `executablePath` 后再执行；或参考 `poster/screenshot_xinfushe_client.js` 的写法。

2. Read the template at `assets/poster_template.html` (already have it in context)

3. Generate a complete HTML using the template structure with **all matching CSS variables replaced** for the chosen region's color scheme

4. Save to `poster/{topic_keyword}.html`

### Step 5.5: 无二维码版本（可选，2026-08-12 固化）

当用户要求"出一半/部分不带二维码"或指定渠道不需要二维码（企业内部转发、对外不需引流平台、官网嵌入等）时，额外生成无二维码版本。

- **触发词**：用户说"一半不带二维码"、"不要二维码"、"无码版"、"双版本"等
- **文件命名**：`{topic}_noqr.html` + `{topic}_noqr.jpg`（后缀 `_noqr`）
- **比例控制**：由用户指定，默认带码版。例如"出一半不带二维码"=该篇出双版本（带码 + 无码各一份）
- **改动点**：仅 footer 区，与带码版唯一区别：
  1. 删除 `<img class="qr" src="qr_code.jpg" alt="公众号二维码">` 整行
  2. CTA 文案 `联系群主或扫码获取` → `联系群主获取`
- **生成方式**：直接复制带码版 HTML → 删除 qr 行 → 改 CTA 文案 → 保存为 `_noqr.html`
- **截图脚本**：复制带码版 `screenshot_xxx.js`，修改 `filePath` / `outputPath` 的 `_noqr` 后缀即可
- **双版本输出**：present_files 时两张 JPG 一起呈现，让用户直观对比

### Step 6: 截图渲染

```bash
cd poster && \
NODE_PATH=/Users/yoyo/.workbuddy/binaries/node/workspace/node_modules \
node \
/Users/yoyo/.workbuddy/skills/country-knowledge-poster/scripts/screenshot_poster.js \
{topic_keyword}.html {topic_keyword}.jpg
```

> ⚠️ node 版本路径会随更新变化（旧的 `versions/22.22.2/bin/node` 已不存在，实际为 `22.22.2-3`），**直接用 PATH 里的 `node` 即可**，不要写死版本号。
> 若 `node_modules` 里 playwright 解析失败，回退方案（2026-09-24 实测可用）：
> ```bash
> cd /Users/yoyo/WorkBuddy/Claw/poster && \
> NODE_PATH=/Users/yoyo/WorkBuddy/2026-05-18-task-1/xhs-publisher/node_modules \
> node screenshot_multi.js {dir}/{topic}.html {dir}/{topic}.jpg
> ```
> （`screenshot_multi.js` 取 `.poster`/`.card` 元素截图，2x 渲染 JPEG 98）

The script uses 2× viewport scaling with JPEG quality 98.

### Step 7: 提交结果

Call `present_files` with both the `.html` and `.jpg` files.

### Step 8: 推送飞书（默认动作，2026-08-04 固化）

**所有海报/知识卡片生成后必须立即推送到飞书群 `oc_YOUR_CHAT_ID`，不再等待用户确认。**

推送链路（必须先设置 `LARK_CLI_NO_PROXY=1`）：

```bash
# 1) 上传海报图片（bot身份，data必须含 image_type=message，否则报234001）
lark-cli im images create --as bot --data '{"image_type":"message"}' --file image=poster/{topic}.jpg
#    → 取返回 image_key (img_xxx)

# 2) 发送海报图片
lark-cli im +messages-send --as bot --chat-id oc_YOUR_CHAT_ID --image img_xxx

# 3) 发送推荐语文案
lark-cli im +messages-send --as bot --chat-id oc_YOUR_CHAT_ID --text "$(cat poster/{topic}_share.txt)"
```

- 例外：用户明确标注"内部用途/不推送"的内容不推
- **群内指令 → 不同步过程**（2026-08-24 Yoyo 固化）：当任务由飞书群内指令触发时，制作海报/配文的**大段设计、选材分析、踩坑与思考过程一律不同步到飞书群**，群里只发成品（海报图 + 配文/分享文案，分条）。过程性内容仅在工作区本地可见，避免刷屏。
- 双版本推送策略：同一篇文章同时出了带码版与无码版时，**只推未在群里发过的版本**（避免群里重复刷屏）；优先推带码版（引流到公众号），无码版仅用于无码场景的二次传播
- 历史教训：推送是易漏步骤（7/27印度、7/22韩国、7/31意大利均漏推），生成后必须立即执行，不得留到下次

### Step 9: 同步飞书多维表格「海报素材库」（默认动作，2026-08-20 固化；2026-08-20 下午更新）

**所有海报/知识卡片生成后，除推送飞书群（Step 8）外，必须同步到飞书多维表格「海报素材库」：**
Base `Y30ebbtN6a7Ppasf6kNcDjsonAc` / 表 `tblxggyr31BghwFQ`（字段：标题/平台/类型/日期/素材图片/副标题/备注/内容/编号）。

**核心模型（Yoyo 2026-08-20 下午指令）：**
- **一篇【文章】= 一条记录**：同一篇小红书/日报文章衍生的多张海报（大字报版/梦幻紫版/知识卡片版等）与所有附件，**全部挂到该记录「素材图片」单元格（附件数组）**，绝不分拆成多条记录。
- **「内容」字段 = 根据该篇日报文章的原文撰写的对应内容**（每篇文章一篇内容，基于 `慧思出海早报_YYYYMMDD.md` 的对应条目撰写，含政策要点与对在企影响，无需逐字照搬原文）。

- **工具脚本**：`poster/sync_to_feishu.js`（必须在项目根目录 `/Users/yoyo/WorkBuddy/Claw` 运行）
- **运行方式**：
  ```bash
  cd /Users/yoyo/WorkBuddy/Claw
  node poster/sync_to_feishu.js --only 20260820-03,20260820-04   # 只同步指定编号
  node poster/sync_to_feishu.js --folders 20260820_us_visa_fee_hike  # 按素材文件夹同步
  node poster/sync_to_feishu.js   # 同步 MANIFEST 全部（幂等，可重复跑）
  ```
- **编号规则**：`YYYYMMDD-NN` 是**文章级**幂等键（同一篇文章所有海报共用一个编号）。
  - 编号不存在 → 新建一行（先 upsert 文本字段，再上传该文章全部图片挂到「素材图片」格）。
  - 编号已存在 → **更新**该行（重新上传该文章全部图片，把「素材图片」单元格**整体替换**为最新全部 token + 刷新文本），**绝不新建重复行**。
- **更新语义（关键坑，已验证）**：
  - `record-upsert` 在本环境会**始终新建**（不按编号去重）→ "已存在"分支一律走 `record-batch-update` 覆盖，禁止再调 upsert。
  - `record-upload-attachment` 是**追加**到单元格，且飞书按内容去重；上传后必须用 `record-batch-update` 把「素材图片」设为**该文章全部 token 的完整数组**才能整体替换旧图（多图场景尤其注意：必须显式列出所有图片 token，否则会丢失未重传的图）。
  - 取 file_token 必须按**文件名**精确匹配当次上传项（同一单元格可能含多个附件，取第一个会拿到旧图 token）。
- **MANIFEST 结构（文章级）**：每条一个对象，`images` 为数组（该文章全部海报相对 `poster/` 的路径），`content` 为该篇文章内容：
  ```js
  { no:'20260820-02', date:'20260820', platform:['小红书'], type:['小红书海报'],
    title:'美国H-1B/L-1延期新增生物识别费', subtitle:'双版：紫色大字报 + 梦幻紫',
    note:'8/20早报·小红书双版',
    content:'<根据日报该条目撰写的文章内容>',
    images:['20260820_us_visa_fee_hike/xhs_bigtext_purple_us_visa_fee_hike.jpg',
            '20260820_us_visa_fee_hike/xhs_dreamy_us_visa_fee_hike.jpg'] }
  ```
- **新增素材**：在 `sync_to_feishu.js` 的 `MANIFEST` 数组按文章追加一条（编号/日期/平台/类型/标题/副标题/备注/内容/images[]），再 `--only` 同步即可。

### WeChat 品牌版海报模板（带 humancehr 标识，2026-08-21 沉淀）

适用于**微信群/公众号/朋友圈**等需要品牌曝光的渠道。**与小红书 de-branded 版互斥**：小红书禁止带品牌（风控）；WeChat/公众号渠道鼓励带品牌（引流）。

- **模板来源**：参考 Oman 知识卡片 `poster/20260818_oman_foreign_labor/oman_foreign_labor_2026.html`（11 模块结构：顶部品牌 → 国旗标签 → 主标题 → 5项数据条 → Q&A红头 → 中企自查3要点 → 监管升级2×2 → 合规要点+风险警示双栏 → 企业行动清单 → 底部品牌+QR）
- **顶部固定**：`.brand` 区（humancehr.com logo + 慧思全球人力资源）+ `.badge`「知识卡片」金徽章
- **底部固定**：`.footer`（慧思·HumanceHR + 全球出海人力资源服务中心 + QR码 + 「完整资料·专属定制」金文 + 「联系群主或扫码获取」灰文）
- **区域色规则**（仅 `.header`/`.accent` 用，其他不变）：
  - 中东/北非（Oman/UAE/沙特等）→ 红 `#8C1F28`/`#B52B35`
  - 东南亚（越南/印尼/泰国等）→ 绿 `#0D4F2C`/`#157A3E`
  - 拉美（巴西/墨西哥等）→ 橙 `#E65100`/`#F57C00`
  - 欧盟/北美/澳洲 → 蓝 `#1E3A5F`/`#2B5797`
- **资源依赖**：每张图所在文件夹需包含 `logo.png` 与 `qr_code.jpg`（可从 Oman 文件夹复制）；HTML 内 `src="logo.png"` 与 `src="qr_code.jpg"` 用相对路径
- **渲染脚本**：`poster/<date>_<slug>/screenshot_<slug>.js`（Playwright，2x DPR，JPEG 98，截 `.poster` 元素）
- **文件命名**：`vietnam_hr_outsourcing_2026.html/.jpg`（沿用 `<slug>_<year>.html` 风格）
- **飞书群推送**：`im +messages-send --image <path>` + `im +messages-send --markdown <text>`（图文分两条，lark-cli 不支持单条图文混合）

### 微信分享产出规范（2026-08-21 固化：图片 + 文案双标准）

> 自 2026-08-21 起，所有"微信分享"（微信群 / 公众号 / 朋友圈）默认按此标准产出：**品牌版海报图片 + 文案**。用户未特别说明时即按此执行，不另行确认。
> **2026-09-07 更新：文案默认只出「知识卡片精简版」（下方 A 版），不再同时产出详版。**

**1. 微信分享图片 = WeChat 品牌版海报（带 humancehr 标识 + QR）**
- 模板与结构见上方「WeChat 品牌版海报模板」章节（参考 Oman 11 模块：顶部品牌 → 国旗标签 → 主标题 → 5项数据条 → Q&A红头 → 中企自查3要点 → 监管升级2×2 → 合规要点+风险警示双栏 → 企业行动清单 → 底部品牌+QR）。
- 与小红书 de-branded 版互斥：微信分享**鼓励带品牌**（引流到 humancehr），小红书**严禁带品牌**（风控）。

**2. 微信分享文案 = 知识卡片精简版（默认唯一产出，2026-09-07 Yoyo 再次确认）**

> ⚠️ 自 2026-09-07 起：**默认只出 A 版知识卡片精简文案**。B 版（Oman 6 段详版）仅在用户明确要求「详版 / 长文案 / 完整版」时才出。2026-08-21 的「两版同时产出」约定作废。
>
> 用户 2026-09-07 认可的标准样例（沙特 Q1 严打虚假本地化）：
> ```
> 【知识卡片】🇸🇦 沙特一季度严打虚假本地化：25万次巡查
> 沙特人力资源与社会发展部（MHRSD）2026年6月5日披露首季执法数据：一季度开展逾25万次劳工巡查，发现16.8万起违规，发出23万次警告；重点打击"假本地化"，核查9.1万起疑似案例、确认1.35万起虚假雇佣，取消7,200余份违规签证并停用政府服务。
> 📌 企业需关注：
> · 确保Nitaqat本地化与GOSI登记真实有效
> · 工资、岗位与社保信息须与实际运营一致
> · 定期自查沙特籍员工在岗真实性，杜绝虚假雇佣
> · 违规将取消签证并停用政府服务，触发业务中断
> 👉 查看全文：https://www.humancehr.com/knowledge-base/<slug>
> ```
> 关键：通篇零 Markdown（无加粗 / 标题 / 表格），4 个自然段，转发群里可直接粘贴。

**A. 知识卡片短文案（短文案，默认唯一产出）**
- 格式见 **Step 2**。结构：`【知识卡片】🇽🇽 标题` + 2-3句浓缩摘要（含核心数据，分号串起 3-4 个事实）+ `📌 企业需关注` 4条要点 + `👉 查看全文` 链接。摘要≤80字，要点≤25字。
- 用途：单条推送、朋友圈、快速扫读。

**B. 微信群详版分享文案（长文案，Oman 6段模板）—— 仅按需产出，默认不出**
- 文件命名：`wechat_share_<slug>.md`，放在对应素材文件夹（参考 `poster/20260818_oman_foreign_labor/wechat_share_oman_foreign_labor.md`）。
- 结构（6段）：
  1. **国旗 emoji + 一句定性**（钩子，1行点明"严重/紧急/机会"）
  2. **核心数据**（3-5个硬数字 / 百分比 / 案例）
  3. **政策与执法升级**（法规号 + 生效时间 + 趋势）
  4. **中企自查 N 要点**（①②③ 编号清单，给 HR 可执行动作）
  5. **风险链**（"X→Y→Z" 完整执法链，点痛点）
  6. **👉 完整解读 + humancehr.com 链接**（收口引导）
- 与小文区别：详版允许带 humancehr 链接、完整数据、法规号、自查要点、风险链；不限制 emoji；不要求 #话题标签。
- 用途：微信群深度分享、引导看全文。

**3. 默认执行顺序（2026-09-07 更新）**：每篇做微信分享时，产出 ① 品牌版海报 + ② 知识卡片精简文案（`wechat_share_<slug>.md` 与 `<slug>_2026_share.txt` 同内容）→ 推飞书群（Step 8，图 + 文案分条发送）+ 同步素材库（Step 9，记录「内容」填知识卡片精简文案）。**不再默认产出详版**；用户点名要「详版 / 完整版」时才追加 B 版。

### 字段约束（2026-08-21 验证）

`平台` 与 `类型` 在飞书素材库是**单选**字段（`multiple: false`），MANIFEST 必须写**单值字符串**，不能写数组（数组长度>1 会报 `invalid_request: This field accepts only one option`）。

- `平台` 候选项：小红书 / 飞书 / 公众号 / 微信
- `类型` 候选项：知识卡片 / 小红书海报 / 大字报 / 早报 / 分享文案 / 其他
- **正确写法**：`platform: '小红书'`、`type: '知识卡片'`
- **错误写法**：`platform: ['小红书', '微信']`（长度>1 报错）；`platform: ['小红书']`（长度=1 暂可，但建议改单值更稳）

## Layout Rules（排版标准）

所有海报必须遵守以下排版规则，确保视觉统一和谐。这些规则来自多轮迭代验证，不得随意更改。

### 基础尺寸
- **宽度固定 420px**（手机阅读优化），**不设固定高度**，内容自然撑开
- 布局使用 `display: flex; flex-direction: column` 纵向堆叠
- 所有区块需 `flex-shrink: 0` 防止被挤压

### 间距规则（必须遵守）
- **所有模块底部间距统一 10px**，包括：`.qa-head`, `.section-title`, `.steps-col`, `.fact-grid`, `.bottom-row`
- **风险提示到底签间距 14px**（`.risk-tip` 的 `margin-bottom: 14px`）
- `.content` 内边距：`padding: 14px 18px 0`（上14px 左右18px 下0）
- `.header` 内边距：`padding: 14px 18px 12px`
- `.footer` 内边距：`padding: 12px 18px`
- 步骤卡间距：`gap: 6px`
- 数据网格间距：`gap: 6px`
- 底部双栏间距：`gap: 8px`

### 字号体系
| 元素 | 字号 | 字重 |
|------|------|------|
| 主标题 `.title-main` | 24px | 800 |
| Q&A 文本 `.q-text` | 13px | 600 |
| 段落标题 `.section-title` | 12px | 700 |
| 步骤标题 `.step-card-title` | 12px | 700 |
| 步骤描述 `.step-card-desc` | 10px | 400 |
| 数据标题 `.fact-title` | 11px | 700 |
| 数据描述 `.fact-desc` | 9px | 400 |
| 标签 `.highlight-num` | 14px | 800 |
| 标签说明 `.highlight-label` | 8px | 400 |
| 风险提示 `.risk-tip` | 9px | 400 |
| 底部品牌名 `.footer-name` | 13px | 700 |
| CTA `.cta-main` | 11px | 700 |

### 高亮数据条（5项等高对齐）
- `.highlight-item` 使用 `flex-direction: column; align-items: center; justify-content: center` 实现垂直居中
- 设置 `min-height: 44px` 确保5项高度一致
- `.highlight-label` 设置 `min-height: 21px; display: flex; align-items: center`，短文本和长文本底部对齐
- 每项之间用 `border-right: 1px solid rgba(255,255,255,0.1)` 分隔，最后一项无右边框

### 步骤卡（纵向3行）
- 使用 `.steps-col` 纵向排列，不用横向排列
- 卡片样式：`display: flex; gap: 8px; background: #F9FAFB; border-radius: 8px; padding: 7px 10px; border-left: 3px solid var(--accent)`（左边界强调）
- 步骤编号：`20px` 蓝色圆形，白色数字

### 数据网格（2×2）
- 使用 `.fact-grid` 配合 `flex-wrap: wrap`
- 每项宽度 `calc(50% - 3px)`，正好2列
- 背景 `#F0F7FF`，边框 `1px solid var(--accent-border)`

### 底部双栏
- 等宽 `flex: 1`
- 左栏绿色系（`#E8F5E9` 背景 + `#A5D6A7` 边框） — 表示合规底线/正面信息
- 右栏橙色系（`#FFF8F0` 背景 + `#FFE0B2` 边框） — 表示合规风险/警示信息

### 颜色体系
| 变量 | 用途 | 色值 |
|------|------|------|
| `--header-start` | 头部渐变起点 | `#1E3A5F` |
| `--header-end` | 头部渐变终点 | `#2B5797` |
| `--header-dark` | 数据条背景 | `#142946` |
| `--accent` | 主题强调色 | `#2B5797` |
| `--accent-light` | 浅色强调背景 | `#E8F0FA` |
| `--accent-border` | 浅色边框 | `#BBDEFB` |
| `--accent-text` | 强调文字色 | `#1565C0` |
| `--gold` | 金色数据条数字 | `#FFD700` |
| 底部背景 | Footer 背景 | `#1a1a2e` |

### 内容填充规范
- 步骤卡描述：每行控制在 **35字以内**，简洁完整
- 数据条标签：控制在 **10字以内**，短词优先
- Q&A 问题：从**企业决策者视角**提出，自然直接
- 风险提示清单：**5项为上限**，用①②③④⑤编号
- 底部双栏描述：控制在 **40字以内**

### 输出格式
- HTML 文件：可编辑，保存到 `poster/{topic}_{theme}.html`
- JPG 文件：通过 Playwright 截图 2x 渲染，截图脚本在 `scripts/screenshot_poster.js`，先复制 logo.png 和 qr_code.jpg 到同一输出目录

## Platform Layouts（平台化版式，2026-08-12 新增）

当用户要求按特定平台出图（小红书 / 公众号 / 朋友圈）时，在同一主题下生成平台匹配的版式。风格与表述需与平台气质匹配，与标准知识卡片差异明显。

### 小红书版式（3:4 竖版三图）— 旧版，已弃用
> ⚠️ 此旧版（xhs_{topic}_1/2/3 三图拆分，2026-08-12）已被下方「小红书四模板体系」取代，新产出请勿使用。
- **文件**：`xhs_{topic}_1/2/3.html` + `.jpg`
- **尺寸**：540×720 CSS px（2x 渲染 → 1080×1440，即 3:4）
- **三图分工**：
  1. 封面：大标题悬念 + 数据卡 + "下滑看信号"引导（e.g. `xhs_global_talent_1.html`）
  2. 干货：3 个信号/要点拆解 + 数据条 + 保存引导（e.g. `xhs_global_talent_2.html`）
  3. 行动结尾：5 件事清单 + 警示框 + 点赞收藏关注引导（e.g. `xhs_global_talent_3.html`）
- **风格**：年轻活泼、口语化有网感（"就这 5 件事"、"干货篇 02"）、撞色渐变（珊瑚橙 #FF6B35 / 亮黄 #FFC93C / 深底 #1A1A2E）、大数字、圆角卡片、emoji
- **表述**：短句 + 感叹号 + 第一人称博主口吻；数据仍保持准确
- **去品牌（2026-08-12 固化）**：小红书版**默认不带任何品牌标识**（无 logo、无品牌名、无域名、无关注引导）；顶部左侧用中性标签（封面"🌍 出海观察"、干货"📌 干货速览"、行动"✅ 行动指南"），结尾用通用引导（"❤️ 点赞+收藏"、"下一期见 👋"）

### 小红书四模板体系（2026-08-28 固化：绿 / 蓝 / 紫 / 知识卡片）

> 自 2026-08-28 起，**每次做小红书素材默认同时产出四套模板**：知识卡片版 + 绿色大字报版 + 蓝色大字报版 + 紫色大字报版。用户未特别说明即按此执行，不另行确认。
>
> **关键约束：三色大字报必须差异化，不能仅换色**。小红书对「同质内容」识别严格，若绿/蓝/紫只是同一模板换色，会被判定为重复/低质。因此三套大字报使用三套独立结构、不同标题角度、不同数据呈现方式：绿色给清单、蓝色给解读、紫色给预警。

**内容来源（强制，不得凭空编写）**
小红书素材的正文、数据、要点必须取自以下两类来源，二创而非原创：
1. **日报内容**：`慧思出海早报_YYYYMMDD.md` 对应条目，或出海资讯日报 API 库原始记录（标题 / 关键数据 / 要点 / 来源引用）。
2. **海报二创**：从已生成的 WeChat 品牌版海报、知识卡片 HTML 二创——提取其核心数据、合规要点、结论，按小红书版式与文案风格重新排版；与源海报同源不同形，不与日报正文逐字重复。
- 约束：保留真实数据（日期/百分比/金额/法规号），不夸大、不加未证实信息；文案与日报/海报同源可追溯。

**四模板定义（均去品牌 / 去logo / 去二维码 / 去导流术语，违反即触发小红书限流）**

| 模板 | 源文件 | 产出命名 | 尺寸 | 定位 | 视觉 |
|------|--------|----------|------|------|------|
| 知识卡片版 | `assets/xhs_card_template.html` | `xhs_card_{topic}.html/.jpg` | 1080宽长图 | 完整知识点速览 | 信息密集完整卡片，区域色（东南亚即绿系） |
| 绿色大字报版 | `assets/xhs_bigtext_green_template.html` | `xhs_bigtext_green_{topic}.html/.jpg` | 1080×1440（3:4） | 实操清单 / 自查要点 | 浅绿渐变米白底、深绿文字、圆形序号清单、底部绿条提示 |
| 蓝色大字报版 | `assets/xhs_bigtext_blue_template.html` | `xhs_bigtext_blue_{topic}.html/.jpg` | 1080×1440（3:4） | 政策解读 / 数据简报 | 深蓝渐变、金色主数字、右侧双小卡、左侧竖线要点 |
| 紫色大字报版 | `assets/xhs_bigtext_purple_template.html` | `xhs_bigtext_purple_{topic}.html/.jpg` | 1080×1440（3:4） | 风险预警 / 情绪冲击 | 亮紫渐变、顶部橘红警告条、单焦点巨数、三步骤风险链 |

- 绿/蓝/紫三色大字报版使用**三套独立 HTML/CSS 结构**，而非同一模板换色：标题角度、排版骨架、字号层级、装饰元素均不同，避免小红书判为同质内容。
- 同主题四张图在内容同源的前提下，分别给出「清单→解读→预警」三种阅读视角，既保持系列感又不重复。
- 生产工具：`poster/build_xhs_bigtext.py` 读取 `assets/xhs_bigtext_green/blue/purple_template.html`，按 `DATA` 字典填充字段后输出 HTML。新增主题时在此脚本中追加条目即可。
- **（可选）梦幻紫变体**：`assets/xhs_dreamy_purple_template.html` → `xhs_dreamy_{topic}.html/.jpg`，薰衣草渐变+星芒+胶囊徽章+立体描边大字（深紫 `#4A2D7A` 6px 白描边），情绪感染力强（驱逐/严查/大涨/危机类）时替代或补充紫色大字报版。
- 旧模板 `assets/xhs_bigtext_legacy_template.html` 已弃用，仅保留作历史参考。

**小红书笔记文案**：`xhs_copy_{topic}.md` — 标题≤20字 + 正文120-200字（含3个emoji），结尾直接接话题标签（如 `#出海 #人力资源 #菲律宾`），**禁止**出现品牌名、域名及关注/私信/主页/公众号/评论区等引导术语。

**默认执行顺序**：每篇小红书 → ① 知识卡片版 + ② 绿色大字报版 + ③ 蓝色大字报版 + ④ 紫色大字报版（梦幻紫按需）→ 截图 JPG → 推飞书群（Step 8，图分条 + 文案）→ 同步素材库（Step 9，同一文章编号挂全部图，绝不拆成多条）。

### 公众号 / 朋友圈长图版式
- **文件**：`wechat_{topic}_{date}.html` + `.jpg`
- **尺寸**：640px 宽竖长条（2x 渲染 → 1280px 宽），高度自然撑开（e.g. `wechat_global_talent_2026.jpg` 640×1429）
- **结构**：品牌头图 → 大标题+日期 → 引言段 → 分章节（一/二/三）→ 数据卡行 → 行动清单 → 合规双栏 → 文末二维码 + 关注引导
- **风格**：商务稳重、米白底（#FAF6F0）+ 深棕文字（#3E2C1E）+ 金色 accent（#B8860B）、信息密度高、适合深度阅读
- **表述**：正式书面语、完整句式、小标题分节
- **带二维码**（公众号引流场景必须，复用 `qr_code.jpg`）

### 通用截图脚本
- `poster/screenshot_multi.js`：参数化脚本，`node screenshot_multi.js <input.html> <output.jpg>`，自动定位 `.poster` 或 `.card` 元素截图，2x 渲染 JPEG 98

### Bundled resources

- `assets/poster_template.html` — Base poster HTML template with all layout sections
- `assets/logo.png` — Humance brand logo
- `assets/qr_code.jpg` — QR code for WeChat public account
- `scripts/screenshot_poster.js` — Playwright screenshot script (update filenames before running)
- `poster/screenshot_multi.js` — 参数化通用截图脚本：`node screenshot_multi.js <input.html> <output.jpg>`，自动定位 `.poster`/`.card` 元素，2x 渲染（用于所有平台版式）
