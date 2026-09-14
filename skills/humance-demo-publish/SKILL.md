---
name: humance-demo-publish
description: 把慧思数据库（Anchor Tech 资讯库）中的一条资讯推送到前端（demo.humancehr.com 或线上 www.humancehr.com）并发布，含字段映射、发布校验与慧思数据库状态回写。当用户说「把资讯ID XXXX 推到 demo 前端」「推到线上前端」「发布到 demo 站/线上站」「慧思数据库推前端」时使用。
agent_created: true
---

# 慧思数据库 → demo 前端发布

把慧思资讯库里的一条记录（`INFO_ID=YYYYMMDDNN`）变成 demo 前端的一篇已发布文章，并回写慧思侧推送状态。

## 系统地图（2026-09-08 实测）

| 环节 | 地址 | 说明 |
|------|------|------|
| 慧思数据库 | `https://www.anchortech.ai/api` | Anchor Tech PaaS，BO = `BO_EU_CRAWLER_NEWS_SOURCE`，`dwViewId=obj_6fb16d1256db4ec1b15ba5212d1259ce`，`msaSvcId=ai-content`。**无需认证**（带不带 token 都能查） |
| demo 前端 | `https://demo.humancehr.com` | Astro 站点 |
| demo 前端 API | `https://demo.humancehr.com/api` | **只是 Astro 的只读+创建代理**。GET/POST 可用；**PUT/DELETE 会返回前端 404 页面** |
| demo 后台 API ⭐ | `https://demo-admin.humancehr.com/api` | **真正的 Strapi 后端**。GET/POST/PUT 全支持。发布、更新一律走这里 |
| 线上真后台 ⭐ | `https://admin.humancehr.com/api` | **Strapi 后端，结构与 demo-admin 同款**。**但 JWT 不通用**：demo 与 prod 是独立实例、secret 不同，本任务给的 token 仅对 demo-admin 有写权限，对 prod POST 返回 401。发 prod 需独立的 prod 后台 token（用户提供）。注：articles 公开可读，无 token 也能 GET 2315 篇，所以「能读」≠「能写」 |
| 生产站 | `https://www.humancehr.com` | 线上 Astro 站点，前台只读代理（`/api`）同 demo 套路 |
| 生产站前台 API | `https://www.humancehr.com/api` | 只读代理，不能 PUT/DELETE，勿误打 |

## 关键坑（每个都踩过，务必遵守）

1. **更新/发布必须走 `demo-admin.humancehr.com`**，不要用 `demo.humancehr.com/api`（PUT 会落到前端 404 页）。
2. **curl 必须加 `-g`**：URL 里的 `[]` `{}` 是 curl 的 glob 字符，不加 `-g` 时 `filters[slug][$eq]=x` 会被吞掉，查什么都不返回，误判成「记录不存在」→ 然后 POST 撞唯一键报 500。
3. **PUT 请求体必须包一层 `{"data": {...}}`**，直接传扁平字段会报 `400 Missing "data" payload`。
4. **POST/PUT 都会自动发布**（该环境未开 draft&publish，`publishedAt` 由服务端填充），传 `publishedAt: null` 无法下架。
5. **后台 token 无 DELETE 权限**（403 Forbidden）。**不要先用正式 slug 试创建**——建错就删不掉，只能靠人工后台清理。正式执行前一律 `--dry` 看载荷。
6. **slug 唯一**：同 slug 再 POST 返回 `500 Failed to create article`，错误信息看不出是唯一键冲突。
7. **Python urllib 直连 demo-admin 会 SSL 握手失败**（本机有 HTTPS 代理），统一走 `curl` 子进程。
8. **慧思数据库回写必须回填验证**：历史 bug 是 `result:ok` 但数据没入库。改完 PUSH_STATUS 后要重新 query 确认。
9. **发线上（prod）与发 demo 机制完全一致，不会产生测试记录**：脚本已参数化 `--env prod`，直接打 `admin.humancehr.com` 真后台，create+PUT 一步到位。**之前 demo 站留 8 条待删记录是首次没摸清 API 拓扑、走 POST 试错踩坑的副产品，不是流程必然产物**——固化后无论 demo/prod 都干净。发 prod 前务必先 `--dry` 校验字段结构（线上很可能同一套代码，但稳妥起见首次应确认）。
10. **⚠️ prod token 不通用（重要修正）**：demo 与 prod 是**独立 Strapi 实例**，JWT secret 不同。本任务给的 token 只对 `demo-admin` 有写权限；打到 `admin.humancehr.com` POST 会 **401**。之前误以为「token 通用」是因为 articles 公开可读（无 token 也能 GET 2315 篇）——那只是读权限，不等于写权限。**发 prod 必须用户提供独立的 prod 后台 token**，脚本用 `--env prod --token <prod_token>` 即可。

11. **如何拿到有写权限的 prod token（实测结论）**：打到 `admin.humancehr.com/api` POST 报 `401 Unauthorized`，说明该 token 是**读者/只读角色**（普通 `/api/auth/local` 登录的 JWT，其默认 Authenticated 角色无 articles 写权限）。正确做法：去 **`admin.humancehr.com` 后台 → Settings → API Tokens → Create new API Token → Token type 选 `Full access`（完全访问）** → 复制生成的 token 发我，这种 API Token 才能 POST/PUT articles。已验证：本任务给的两个 token（demo `f04486…`、prod `8854e3…`）均为只读，写不了任何站。

12. **线上 token 已验证可用（2026-09-08 实测）**：用户最终提供的 `6cdc516b…` 前缀 token 对 `admin.humancehr.com` 有写权限（Full access 级），POST/PUT articles 成功（发布星宇文章线上 id=4963）。**发 prod 优先用此 token**；若过期再去后台 Settings→API Tokens 重新生成 Full access token。三轮 token 测试结论：`f04486…`=仅 demo-admin 可写 / `8854e3…`=只读 / `6cdc516b…`=prod 可写。

13. **⚠️ 权限细分坑：PUT 返回 404 ≠ 401（2026-09-08 实测）**：Strapi API Token 权限是**逐动作（find/findOne/create/update/delete）独立授权**的，不是「读写二元」。实测同一个 `6cdc516b…` 前缀的第二个更长 token（256 字节）权限为：**find✅ / create✅ / findOne❌404 / update❌404 / delete❌403**——即「能建不能改」。现象与排查要点：
    - **单条 GET（findOne）404 + PUT（update）404 + DELETE 403**：说明 token 只有 find+create，**没有 update 权限**，无法原地修改已有文章。
    - **POST（create）201**：能建新文章，但无法覆盖旧文（slug 唯一会撞键）。
    - 区分：`401 Unauthorized` = 整个 token 无写（角色错/过期）；`404` on PUT = token 有 find/create 但缺 update 动作授权（Strapi 先 findOne 被拒→找不到资源→报 404）。
    - **修复已有文章必须用带 update 权限的 token**：后台 Settings→API Tokens→编辑该 token→给 Article 勾上 `update`（顺带 `delete` 便于清理探针）→ 或新建 `Full access` 级 token。
    - ⚠️ 探测 create 权限会真建一条记录（如本任务误建 __perm_probe__ id=4970），无 delete 权限清不掉，须用户后台手动删。探测前务必告知用户会留痕。
    - create-only token 发布文章时，**POST 载荷必须主动带 `publishedAt`**（ISO8601）才能发布；否则建出来是 draft 态（前端不可见），而又无 update 权限事后 PUT 补 `publishedAt` → 文章永远不公开。

14. **⚠️ "对齐参考页"会顺带拷入参考页自身的 bug（2026-09-08 实测）**：参考页 `2027-kazakhstan-foreign-labor-quota-application` 的 content 内嵌 `<style>` 里，`.step-list li:before` 用的是 **`position: absolute; left: 0; display: block`** 坏版（会导致 "Step" 文字绝对定位压在正文上重叠）。该参考页恰好没用 step-list 所以没暴露。若直接把参考页 style 整段套到星宇文章（星宇用了 step-list），重叠 bug 会重现。正确做法：套用参考页 style 后，**必须显式把 `.step-list`/`.process-step` 改成内联版**（去掉 `position:absolute`、`padding-left:30px`，`:before` 加 `margin-right`），否则排版错乱。同理，任何"对齐某篇健康文章"都要先 diff 其 CSS 有无绝对定位/嵌套等隐患，不能无脑整段复制。

## 字段映射（慧思 BO → demo Strapi article）

| 慧思 BO 字段 | demo article 字段 | 备注 |
|--------------|-------------------|------|
| `TITLE` | `title` | |
| — | `slug` | 英文短横线，需唯一 |
| — | `titleEn` | 英文标题 |
| `CONTENT`（markdown）/ 排版 HTML | `content` | 现有资讯类文章存的是**完整 HTML 文档**（含 `<!DOCTYPE html><html>...<style>`），不是片段 |
| 同 content | `previewContent` | 与 content 一致即可 |
| — | `category` | 枚举：`knowledge` / `holiday` / `country` / `remuneration`。资讯统一用 `knowledge` |
| `TAGS`（JSON 数组） | `industryTags` / `knowledgeTags` | 逗号分隔字符串，**必须含「海外资讯」** |
| — | `countryTag` | 国家名 |
| — | `jobTags` | 无则填「通用」 |
| `ID` | `originId` ⭐ | 慧思记录的 `ID`（形如 `ef8470a8-...`）即文章的 `originId`，是两边对齐的主键 |
| `SUMMARY` | `description` | |
| `SOURCE` | `sourceName` | |
| `ORIGINAL_URL` | `sourceUrl` | |
| — | `locale` | `zh-CN` |
| — | `newsletterCandidate` | `true` |
| — | `views` | `0` |

## 执行步骤

```bash
# 1. 从慧思数据库拉记录，落盘
node scripts/fetch_record.js <INFO_ID>        # 或直接用 anchortech-config.json 里的配置手写请求

# 2. 干跑看载荷（必做）
python3 scripts/push_news_to_demo.py --token <后台token> --env demo --dry
python3 scripts/push_news_to_demo.py --token <后台token> --env prod --dry   # 发线上前务必先 dry

# 3. 正式推送（有则更新，无则创建；自动发布）
python3 scripts/push_news_to_demo.py --token <后台token> --env demo
python3 scripts/push_news_to_demo.py --token <后台token> --env prod        # 发线上

# 4. 验证（脚本内已含 3–5 步，仍需人工看一眼页面）
open https://demo.humancehr.com/knowledge-base/<slug>
```

脚本内建 5 步：查找/创建或更新 → 补发布 → 后台校验 → 前端可见性校验 → 回写慧思 `PUSH_STATUS=1` + `PUBLISH_TIME`。

## 门禁

- 前端可见性校验未通过 → **不回写**慧思 PUSH_STATUS。
- 回写后必须重新 query 慧思，确认 `PUSH_STATUS == '1'`；否则判定静默失败。
- 涉及对外发布，发布后口头/飞书同步 Yoyo 一次。
- 严禁为了凑数改写正文：正文以慧思 `CONTENT` / 已排版 HTML 为准。

## 复用

`scripts/push_news_to_demo.py` 参数：
- `--token <后台token>`（必填。**demo 与 prod 用不同 token**：demo 用 demo-admin token，prod 用 prod 后台 token，两者不通用）
- `--env demo|prod`（默认 demo；prod 走 admin.humancehr.com 真后台）
- `--dry` 只打印最终载荷 + 后台写地址
- `--no-writeback` 不回写慧思数据库

改 `INFO_ID` / `SRC_REC` / `SRC_PAYLOAD` 三个常量即可复用到其他资讯。
