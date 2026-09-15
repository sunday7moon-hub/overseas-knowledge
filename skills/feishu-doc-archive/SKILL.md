---
name: feishu-doc-archive
description: 飞书文档归档助理。仅把飞书云空间的「多维表格」(bitable) 自动同步到「文档归档库」多维表（字段：文档名称/文档链接/用途/格式/创建时间/所有人），并支持手动归档单个多维表格链接。适用于个人/团队在线文档资产盘点、按用途检索、自动留痕。
agent_created: true
---

# 飞书文档归档助理 (Feishu Doc Archive)

把飞书云空间里的在线文档集中归档到一个多维表，字段含：**文档链接、用途、格式、创建时间、所有人**（外加主字段「文档名称」）。
- **仅收录「多维表格」(bitable)**：自动同步与手动 add 都只接受多维表格，文档/文件/电子表格/思维笔记/幻灯片等类型一律跳过（保持归档库只含多维表格目录）。
- **自动同步**：定时增量扫描飞书云文档中的多维表格，新建项自动入库（按创建时间游标 + 链接去重）。
- **手动归档**：给一个多维表格链接，自动解析名称/格式/创建时间/所有人并登记，用途可手填。

## Prerequisites

- `lark-cli` 已配置飞书应用（`lark-cli config show` 含 `app_id`；当前路径 `/Users/yoyo/.workbuddy/binaries/node/versions/22.22.2/bin/lark-cli`）
- 应用权限：`base:*`、`drive:*`；`contact:user.base:read`（可选，用于把所有人 openid 解析成真实姓名）
- 运行前务必设置环境变量：`LARK_CLI_NO_PROXY=1`（避免代理 TLS 超时），`LARK_CLI_BIN` 指向 lark-cli 绝对路径

## 归档库结构（多维表「文档归档库」）

`base_token=LZnDbQeqbaxZWasWuRjcOTH6nTf`，`table_id=tblfupBsZAesoWPx`

| 字段 | 类型 | 说明 |
|------|------|------|
| 文档名称 | 文本（主字段） | 取自飞书文件 name |
| 文档链接 | 文本 | 飞书文档 URL（去重键） |
| 用途 | 文本 | 手动归档时填写；自动同步默认"（自动同步·待补充）" |
| 格式 | 单选 | 当前仅收录「多维表格」（由 type=bitable 映射）；其余类型不入库 |
| 创建时间 | 日期时间 | yyyy/MM/dd HH:mm，来自文件 created_time |
| 所有人 | 文本 | owner openid；若应用有 contact 权限则解析为姓名 |
| 用途简介 | 文本 | 自动生成：读取该多维表格的表结构（字段名），结合名称生成一句话简介 |
| 权限范围 | 文本 | 自动生成：读取该多维表格的协作者权限列表（成员:权限）；成员 openid 在无 contact 权限时显示原始 id |

> 自动同步**仅收录「多维表格」(bitable)**，其余类型（文档/文件/电子表格/思维笔记/幻灯片/文件夹）一律跳过，保持归档库只含多维表格目录。
> 「用途简介」「权限范围」由 `fill_meta.py` 自动生成并回写（见下）。

## 命令（archive_sync.py，位于本技能目录）

```bash
export LARK_CLI_NO_PROXY=1 LARK_CLI_BIN=/Users/yoyo/.workbuddy/binaries/node/versions/22.22.2/bin/lark-cli
PY=/Users/yoyo/.workbuddy/binaries/python/versions/3.13.12/bin/python3
```

| 命令 | 作用 |
|------|------|
| `python3 archive_sync.py setup` | 幂等建库/建表/建字段（已建好，通常无需再跑） |
| `python3 archive_sync.py sync` | 增量自动同步（首次运行仅设游标为当前时间，不回填历史） |
| `python3 archive_sync.py sync --backfill` | 历史回填：把云空间全部已有文档一次性归档 |
| `python3 archive_sync.py add --url <链接> [--purpose <用途>] [--owner <所有人>]` | 手动归档单个**多维表格**（非多维表格链接自动跳过） |
| `python3 keep_bitable_only.py` | 一键清理：删除归档库中格式≠「多维表格」的记录，只留多维表格 |
| `python3 fill_meta.py` | 给每条记录自动填充「用途简介」+「权限范围」（读表结构 + 协作者权限后回写） |
| `python3 archive_sync.py list [N]` | 列出归档（默认 20 条） |
| `python3 archive_sync.py resolve-names` | 若已开通 contact 权限，回填所有人真实姓名 |

## 自动同步原理

1. 调 `GET /open-apis/drive/v1/files?order_by=created_time&order=desc` 拉取云文档（按创建时间倒序，自动翻页）。
2. 以 `config.json` 中 `last_sync_ts` 为增量游标，只处理 `created_time > last_sync_ts` 的项（`--backfill` 忽略游标，全量归档）。
3. 拉取归档库已有链接集合，按 URL 去重，**仅保留 type=bitable（多维表格），其余类型跳过**。
4. 解析每条：名称（file.name）、格式（type→单选）、创建时间（created_time→**毫秒时间戳**，写入 datetime 字段）、所有人（owner openid，尝试 contact API 解析姓名，失败回退 openid 并内存缓存避免重复请求）。
5. **批量写入**（`bitable records/batch_create`，每批 100 条）提升效率；更新 `last_sync_ts` 为最新 created_time。

> 实测：云空间约 638 个文件，批量回填数十秒完成；逐条 upsert 会因大量 contact API 重试拖垮（已被 owner 失败缓存规避）。

## 历史回填

`archive_sync.py sync --backfill`：忽略增量游标，把云空间全部已有**多维表格**一次性归档（已限定仅 bitable，不会混入文件/文档）。
首次 `sync`（无 --backfill）只设游标、不回填历史。backfill 前若已有部分脏数据，建议先清空归档库再跑（见「常见失败」）。

## 定时任务

已建 recurring 自动化「飞书文档归档-自动同步」（id `automation-1787905190852`），每 6 小时跑一次 `sync`。
如需更密（如每小时）：改 rrule 为 `FREQ=HOURLY;INTERVAL=1`。
> 说明：采用轮询而非实时事件订阅，新建文档最长延迟约一个周期才入库。

## 已知限制 / 注意事项

- **所有人显示为 openid**：bot 当前无 `contact:user.base:read` 权限，owner 存为 openid。给应用加上该权限后，运行 `resolve-names` 即可回填真实姓名（后续同步也会自动解析）。
- **首次不同步历史**：首次 `sync` 只设游标、不倒灌历史。需要历史全量归档用 `sync --backfill`（同样仅收多维表格）。
- **只收多维表格**：归档库设计为「多维表格目录」。自动同步、手动 add、历史回填均限定 type=bitable；若库里混入了其他类型，运行 `keep_bitable_only.py` 一键清理。
- **增量精度**：依赖 `drive/v1/files` 可见范围（应用能看到的文件才会被归档）。
- 删除飞书文档不会自动从归档库移除（归档是快照留痕），需手动在多维表删除对应行。

## 用途简介 / 权限范围（自动生成）

`fill_meta.py` 遍历归档库每条记录，对每条：
1. 从「文档链接」提取 token → 读 `bitable/v1/apps/{token}/tables`（取首个表）→ 读 `.../fields` 获取字段名；
2. 读 `drive/v1/permissions/{token}/members?type=bitable` 获取协作者与权限；
3. 生成一句话「用途简介」（名称 + 主表字段概览）与「权限范围」（成员:权限 列表），回写归档库。

- 依赖应用具备 `base:*` 与 `drive:*` 权限（读表结构 + 读权限）。
- 若某表 bot 不在协作者列表（读不到表结构/权限），对应字段留占位文本，不报错。
- 协作者 openid 在无 `contact:user.base:read` 权限时显示原始 id；邱月 `ou_7f36…` 已内置映射为姓名。
- 历史脏数据：若「文档链接」存成了非 URL（如名称文本），需先从 drive 找回正确 base 链接修正，再重跑本脚本。

## 常见失败

| 现象 | 原因 | 处理 |
|------|------|------|
| `no user authority error` (41050) | 缺 contact 权限 | 所有人显示 openid，不影响归档；按需去开放平台加权限 |
| `field validation failed` 删文件 | 缺 `type` 参数 | 用 `lark-cli drive +delete --file-token <t> --type bitable --yes` |
| 列表/去重读不到记录 | records API 返回 `data.items`（`data` 可能为 null） | 本脚本用 `_items()` 容错解析 |
| `expected str ... not dict` | upsert 误把 dict 当 `--json` 值 | 本脚本已修复为 `json.dumps` 字符串 |
| `DatetimeFieldConvFail` (1254064) | 批量写入 datetime 字段传了字符串 | 创建时间改用毫秒时间戳整数 |
| 批量回填被 SIGKILL（137） | 每条记录撞 contact API 重试拖垮 | owner 解析失败内存缓存，同 owner 不重复请求；并改用批量写 |
| 需清空归档库重跑 | backfill 中途失败留脏数据 | 用 `records/batch_delete` 按 id 批量删后重跑 `--backfill` |
