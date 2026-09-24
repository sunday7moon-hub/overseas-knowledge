---
name: humance-email-push
description: >-
  Humance（humancehr.com）客户触达邮件的生成、去重排程与飞书多维表格同步流程。
  当用户要做出海 HR 产品（Humance / anchorwe.com）的客户邮件触达、批量生成个性化邮件正文、
  设计"每用户每日一封"的防骚扰推送逻辑、按客户阶段（未建联/已建联/已转化/已合作）分层推送、
  做「5 日未活跃」召回邮件（D 类）、清理飞书表重复推送记录、
  把实际发出的邮件回灌成「推送时间 / 触达状态」（发件回执对账），
  或维护飞书「客户触达邮件同步」多维表（新增字段、批量写回邮件内容/HTML/主题）时使用。
  覆盖 72 封历史回填与未来每日实时同步两种场景，沉淀了 lark-cli 授权坑、Alina 落款与扫码引导图规范。
agent_created: true
---

# Humance 客户触达邮件 · 生成 / 去重排程 / 飞书同步

本技能沉淀慧思 Humance 出海 HR 产品客户邮件触达的完整工作流。核心资产：可复用排程器
`scripts/push_scheduler.py`、发件回执抓取与回灌 `scripts/pull_sent_mail.py` +
`scripts/backfill_mail_status.py`、飞书表字段与操作规范（`references/feishu_table.md`）、
数据源与生成流程（`references/data_pipeline.md`）、发送前待办（`references/send_checklist.md`）。

## 何时使用

- 用户要求"给 Humance 注册/活跃/存量用户发邮件""做客户触达邮件"
- 用户要求"邮件推送别骚扰用户""每天最多发一封""注册成功/欢迎/活跃怎么排"
- 用户要求"已建联/已转化的客户少发点""加客户阶段字段"
- 用户要求"把邮件内容/HTML/主题写回飞书表""新建飞书多维表列并批量更新"
- 用户要求"统一落款为 Alina""加扫码引导图"

## 关键事实（先读，避免重踩坑）

- **飞书表**：base_token `MLXGbWKh7aAFJfs9RYNcwER0nMg`，table_id `tblpm0IE8J7WiRtB`，
  URL `https://dcnrh7mpyim9.feishu.cn/base/MLXGbWKh7aAFJfs9RYNcwER0nMg`
  字段（截至 2026-09-04）：用户 / 推送邮件日期 / 邮件分类(A新注册欢迎/B注册后活跃/C核心价值二次触达/存量真实邮箱用户/**D 5日未活跃召回**) /
  行为 / 邮箱 / 邮件内容 / 触达通道 / 优先级 / 触达状态 / 推荐链接 / 注册日期 / 国家偏好 /
  邮件主题 / html版正文 / 客户阶段 / **最后活跃日(fldhpsCfDJ)** / **召回批次(fldjFBhUpb)** / 触达时间。
  当前 **69 条**（2026-09-04 清理 3 条同日重复后），分布：存量真实邮箱用户 47 / C 类 16 / A 类 6。
  16 条 C 类**全部为「已建联」**。
- **落款规范**：正文落款统一 **Alina（慧思）**（非 Yoyo）。加群话术后插入企微扫码引导图
  `邮件-联系慧思.jpg`（来自桌面 `薪福社/物料素材/慧思/`）。
- **固定文尾**：用户提供的标准 Footer 块（关于 Humance / 北京用友薪福社云科技有限公司 /
  地址 / user@example.com / 退订 `{{unsubscribe_url}}` / ©2026 免责声明），padding 26px 20px。
- **数据缺口**：① 百度统计无 source 字段，注册来源用百度统计代理；② GSC 未部署，曝光算不出；
  ③ 每日同步卡 **Strapi User 表读权限**（邱月账号无 `api::user.user` 读权限），需切有权限账号或发 Strapi API Token。
- **lark-cli 坑**：token 频繁失效需重新 `auth login` 授权；命令用全路径
  `/Users/yoyo/.workbuddy/binaries/node/cli-connector-packages/lib/node_modules/@larksuite/cli/bin/lark-cli`；
  batch 写回用 `--json @./file.json`；record-list 信封含 `record_id_list` 与按序 `data`，需按序对齐 rid。

## 工作流

### 1. 生成个性化邮件正文（72 封历史回填 / 批量定制）

参考 `references/data_pipeline.md`：
- 数据源：`/tmp/mails_optimized.json`（user/email/cat/urls/mail/rid）、
  `/tmp/feishu_full.json`（行为/分类快照）、`/tmp/qr_user_records.json`（Strapi 扫码追踪）、
  User CSV（注册导出，UTF+8，createdAt→北京+8）。
- 正文以"最常看文章/国家偏好"为主信号定制链接，首段点明用户具体国家+话题。
- 无姓名用户回退"您好"（勿拼成"您好 您好："）。
- 落款 Alina，加群话术后插扫码图。

### 2. 去重排程（防骚扰核心）

直接用 `scripts/push_scheduler.py`（已跑通，含演示）。规则：
- **硬规则**：同 `user_id × 自然日` 最多 1 封。
- **五类**：R 注册成功(T+0) / W 欢迎含行为(T+1) / A 活跃(自活跃日+3) / C 二次触达(事件日) /
  **D 未活跃召回(自最后活跃日+5)**。
- **优先级** R>W>A>C>D；低优先级顺延并把行为并入胜出邮件不丢。
- **护栏**：A 周≤3（已建联≤2）；注册后 7 天不打 C；退订/30天无互动 `suppressed`；
  **召回冷却**：同一用户两次 D 类召回间隔 ≥30 天（`RECALL_COOLDOWN_DAYS`）。
- **客户阶段**：`Trigger.stage` 读 `STAGE_RULES`：
  - `connected` 已建联 → 停 C，A 周上限 2，通道转企微/人工；
  - `converted` 已转化 → 停 A、C，只发 R/W；
  - `cooperating` 已合作（已签约并开始服务/付费的存量客户）→ R/W/A/C/**D** **全停**，触达转客户成功(CSM)/交付/账单人工通道（最深阶段，强于已转化）。
  - ⚠️ **召回例外（2026-09-04 Yoyo 确认）**：D 类是唤醒邮件 ≠ 营销 C 类，
    **未建联 / 已建联 / 已转化 三阶段都照发 D**，仅 `cooperating` 全停。
- **D 类数据源**：锚点是「最后活跃日」（最近一次登录/访问网站），来自 Strapi。
  ⚠️ **当前阻塞**：Strapi 后台 `https://admin.humancehr.com`（确认存在）的
  `/api/users` 与 `/api/analytics-events` 均返回 **403 Forbidden**，需 API Token。
  邱月账号无 `api::user.user` 读权限。拿到 Token 前，D 类召回无法精确计算，
  只能用注册日/上次推送日兜底（精度差，不推荐）。

### 2b. 历史数据去重（清理飞书表重复行）

用户规则（2026-09-04 确认）：**间隔 ≤2 天的重复才删，≥3 天属正常多次触达，保留**。

用 `dedupe_records(records, window=2, priority_of=...)`：
- 按 `user_id` 分组、按 `send_date` 排序，相邻间隔 ≤2 天归入同一重复簇；
- 每簇保留**优先级最高**的一条（同级取最早），其余进 `delete`；
- 间隔 ≥3 天自动切簇 → 第二次触达/召回邮件不会被误删；
- 无日期的记录不参与去重。
- 飞书分类优先级映射：`{"A":2, "B":2, "C":3, "D":4, "存量":5}`（A 新注册欢迎优于 B 注册后活跃）。

实战：2026-09-04 首次体检命中 3 组同日重复（user:160/162/164 的 A+B 各一对，
正文/HTML/推荐链接完全相同的副本），删 3 条 B 类保留 A 类，72 → 69 条。
**删前务必先 `+record-list` 拉全字段快照存本地备份。**

修改排程器后务必重跑 `__main__` 演示，断言"同用户同日不重复"。

### 3. 飞书表同步

参考 `references/feishu_table.md`：
- 新建列：`lark-cli base +field-create --base-token ... --table-id ... --json '{"name":"列名","type":"text"}'`
- 批量写回：`+record-list --field-id X --format json` 取 `record_id_list` → 构建
  `{"update_records": {rid: {字段: 值}}}` → `+record-batch-update --json @./file.json`
- **新字段首轮常被静默忽略**，写回后务必读回校验非空数。
- 已建联用户：在表加 `客户阶段` 列，凡邮件分类含 C 的存量高价值用户标"已建联"并停其 C 群发。

### 4. 发送前待办（见 `references/send_checklist.md`）

- 扫码图 `邮件-联系慧思.jpg` 为相对路径，仅供本地预览；群发前托管到线上并替换 `<img src>`。
- `{{unsubscribe_url}}` 由 DirectMail 发送时自动替换。
- 真实发送需阿里云 DirectMail 凭据（当前环境无）。

### 5. 发件回执回灌（已发送 → 表）

邮件实际发出后，把**真实发送时间 + 触达状态**回写到飞书表，避免表长期停在「待推送」。

**取数源 = 腾讯企业邮箱（exmail.qq.com）「已发送」**，账号 `user@example.com`。
⚠️ **飞书 mail API 走不通**（当前授权账号 `accessible_mailboxes: []`、`primary_email_address: ""`，无邮箱绑定），
必须走浏览器 bridge（端口 9334）。

**两个现成脚本（推荐直接用）**：

```bash
cd ~/.workbuddy/skills/humance-email-push/scripts
PY=/Users/yoyo/.workbuddy/binaries/python/envs/default/bin/python3   # 必须用 venv（含 websockets）
export NO_PROXY="localhost,127.0.0.1,::1"

$PY pull_sent_mail.py                 # ① 抓「已发送」→ /tmp/sent_mails.json（自动探测 sid）
$PY backfill_mail_status.py           # ② 预览回灌计划（默认 dry-run，不写表）
$PY backfill_mail_status.py --write   # ③ 确认后执行回灌
```

- `pull_sent_mail.py` **自动从已开标签页取 sid**；找不到会提示先打开企业邮箱。实测输出 41 封 / 37 投递成功。
- `backfill_mail_status.py` **幂等**——`触达状态` 已是「已推送」的记录自动跳过，可反复跑。
- 前置：bridge 在跑（`lsof -nP -iTCP:9334 -sTCP:LISTEN`）、Chrome 里企业邮箱「已发送」页面已打开。

**原理（脚本失效时手工排查用）**：

```
① 顶层 https://exmail.qq.com/cgi-bin/frame_html?sid=<SID>
② 已发送 = leftFrame 里 folderid=3 → /cgi-bin/mail_list?folderid=3&page=N
   （navigate 到该 URL 会被重定向回 frame_html，列表在 #mainFrame 内，需 contentDocument 取）
③ 逐行取 input[name=mailid] 的 totime / sh 属性，以及 td.tl[title]、td.gt u、td.Ss[title]
```

| DOM | 含义 |
|---|---|
| `input[name=mailid]@totime` | 发送时间戳（毫秒）→ **精确推送时间** |
| `input[name=mailid]@sh` | 收件人完整邮箱（**显示名被截断，勿用 innerText**） |
| `td.tl@title` | 收件人邮箱（同上，双保险） |
| `td.gt u` | 邮件主题 |
| `td.Ss@title` | **投递状态**（「邮件投递成功」/ 空 = 无投递回执） |

分页：每页 25 条，`<20` 即最后一页；按 `mailid` 去重合并。

**回灌匹配规则（两级，缺一不可）**：
1. 收件人邮箱忽略大小写完全相等；
2. 主题 NFKC 规范化后相等（统一全半角、`｜`→`|`、去空格）。

同一记录命中多封时取**时间最新**的一封（一条 C 类记录可能同时对应 8/21 欢迎信 + 9/7 攻略信，取后者）。

**写入**：`推送时间` 是 **text**（非日期），写 `2026-09-09 09:46`；`触达状态` 是 select，选项 `待推送`/`已推送`。
因每条时间不同，`+record-batch-update` 的「一组共用一个 patch」形态不适用，改用标准 API 逐条 fields：

```bash
lark-cli api POST "/open-apis/bitable/v1/apps/$T/tables/$TBL/records/batch_update" \
  --data '{"records":[{"record_id":"recX","fields":{"触达状态":"已推送","推送时间":"2026-09-09 09:46"}}]}' --as user
```

🔴 **红线**：发件箱里查不到发送记录的，**一律保持「待推送」，不许臆造时间**。
对账时同时留意「一邮箱多封但表内只登记 1 条」的情况——表与真实发送并非 1:1。

## 输出物约定

- 72 封独立 HTML：`outputs/emails/NN_{分类}_{user}.html` + `index.html` 索引 + 同目录 `邮件-联系慧思.jpg`。
- 纯文本全集：`outputs/YYYY-MM-DD 核心用户触达邮件(优化版).md`
- 推送逻辑文档：`outputs/YYYY-MM-DD 邮件推送去重与排程逻辑.md`
- 排程器：**`scripts/push_scheduler.py`（唯一真相源）**。
  ⚠️ 2026-09-15 撤销 `outputs/push_scheduler.py`：该副本与技能版已分叉 189 行，
  而本文档第 178 行曾声明「两份保持同步」——声明无人执行即等于没有声明。
  **不要再在 outputs 下复制一份**；要用就直接跑技能内路径。
- 发件回执抓取：`scripts/pull_sent_mail.py` → `/tmp/sent_mails.json`（字段 `mailid/to/subject/totime/tstr/delivery`）
- 回执回灌：`scripts/backfill_mail_status.py`（默认 dry-run，`--write` 才写表；幂等）
- 回灌对账清单：`outputs/YYYY-MM-DD 邮件触达回灌对账清单.md`（已推送明细 + 未发原因 + 来源口径）
