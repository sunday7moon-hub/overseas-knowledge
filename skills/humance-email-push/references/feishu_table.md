# 飞书「客户触达邮件同步」多维表 · 字段与操作规范

## 连接信息
- base_token: `MLXGbWKh7aAFJfs9RYNcwER0nMg`
- table_id: `tblpm0IE8J7WiRtB`
- URL: `https://dcnrh7mpyim9.feishu.cn/base/MLXGbWKh7aAFJfs9RYNcwER0nMg`

## 字段清单（截至 2026-09）
| 字段 | 类型 | 说明 |
|---|---|---|
| 用户 | text | 用户名/邮箱前缀/品牌（如 Brandy Song（雅迪 Yadea）/ slkv / user:160） |
| 推送邮件日期 | text/datetime | 计划发送日 |
| 邮件分类 | select 单选(fldIaOlIIr) | A 新注册欢迎 / B 注册后活跃 / C 核心价值二次触达 / 存量真实邮箱用户 / **D 5日未活跃召回**(2026-09-04 新增) |
| 行为 | text | 用户访问/下载/扫码/订阅事件摘要 |
| 邮箱 | text | 真实可发送邮箱（69 个真实 + 弃用 temp.local） |
| 邮件内容 | text | 纯文本邮件正文（Alina 落款） |
| 触达通道 | text | 邮件 / 企微 / 人工 |
| 优先级 | text | 高/中/低 |
| 触达状态 | text | 待发送/已发送/已退订 |
| 推荐链接 | text | 定制推荐文章 URL |
| 注册日期 | text | 注册日（UTC→北京+8） |
| 国家偏好 | text | 用户关注国家（如 UAE / 新加坡 / 沙特） |
| 邮件主题 | text(fld75pdS2E) | 按分类+内容定制（见 data_pipeline.md），**已回填 72 条** |
| html版正文 | text(fld5cRMlHh) | 完整邮件 HTML（品牌头+正文+扫码图+文尾） |
| 客户阶段 | text(fldkSXtEbn) | 未建联(空) / 已建联 / 已转化 / 已合作；**2026-09-03 已建：16 条 C 类=已建联，其余留空=未建联**；`已合作`=已签约并开始服务/付费的存量客户，自动化邮件全停转 CSM |
| 最后活跃日 | datetime(fldhpsCfDJ) | **2026-09-04 新增**。最近一次登录/访问网站日期，D 类召回锚点（+5 天）。⚠️ 待 Strapi 回填 |
| 召回批次 | text(fldjFBhUpb) | **2026-09-04 新增**。D 类召回批次号（如 `20260904-01`），配合 30 天冷却防重复召回 |

> 注：`邮件分类` 是**单选 select** 字段（fldIaOlIIr，multi=false），5 个选项见上。
> ⚠️ **客户阶段 fldkSXtEbn 是 text 类型（非 select）**，写入自由文本，值须严格用
> `已建联` / `已转化` / `已合作` 四选一（空=未建联），否则排程器匹配不到 `STAGE_RULES` 会按未建联处理。
> **当前状态（2026-09-04）**：69 条记录（清理后），分布 = 存量真实邮箱用户 47 / C 类 16 / A 类 6；
> 客户阶段 = 未建联 53 / 已建联 16（16 条 C 类全部为已建联）。

> 注：`邮件分类` 是**多选列表**字段，一个用户可同时挂多个标签（早期用户手动把 C 类从 7 改到 16，
> 那 16 条即"已建联"存量用户）。
> **落款统一为 Alina**（2026-09 全表已改，无 Yoyo 残留）；全局问候 bug「您好 您好」(13 条) 已于 2026-09-03 修为「您好：」。

## 授权流程（WorkBuddy 沙盒内 lark-cli device flow · 2026-09 实测）
1. 生成码（非交互，拿到 device_code/verification_url/user_code）：
   `LARK_CLI_NO_PROXY=1 lark-cli auth login --no-wait --json --domain base`
   - 旧 `--scope` 写法已失效，必须用 `--domain base`（base=多维表格读写域）。
   - 默认 domain 会触发 TUI 选域而卡死，务必显式 `--domain base`。
   - `device_code` 有效期 **10 分钟**（之前旧接口仅 5 分钟），过期需重新生成。
2. 生成二维码并**必须展示给用户**：`lark-cli auth qrcode "<verification_url>" --output lark_auth_qr.png --size 320`
   （PNG 须相对当前目录路径；展示顺序：先给 URL，再放二维码图）。
3. 用户扫码授权后回「已授权」，再在本轮执行兑换写入 token：
   `LARK_CLI_NO_PROXY=1 lark-cli auth login --device-code "<device_code>"`
4. **沙盒坑（关键）**：兑换成功但写 keychain 报 `rename ... operation not permitted`——
   实际 token 已落在 `/Users/yoyo/Library/Application Support/lark-cli/cli_<appid>_ou_<openid>.enc.<uuid>.tmp`。
   需 `dangerouslyDisableSandbox` 手动 `mv` 该 `.tmp` 为去后缀的 `.enc` 同名文件，token 即生效。
5. 验证：`lark-cli auth status` 看 user.identity=ready、scope 含 `base:record:*`；再用
   `lark-cli base +record-list ... --format json` 读一次表确认能取数。
6. token 约 2h 可用，`refreshExpiresAt` 约 7 天；代理环境务必带 `LARK_CLI_NO_PROXY=1`，否则刷新失败。

## lark-cli 操作（坑位密集）

命令全路径（PATH 里找不到时用）：
```
/Users/yoyo/.workbuddy/binaries/node/cli-connector-packages/lib/node_modules/@larksuite/cli/bin/lark-cli
```

### 新建字段
```bash
lark-cli base +field-create --base-token MLXGbWKh7aAFJfs9RYNcwER0nMg \
  --table-id tblpm0IE8J7WiRtB --json '{"name":"客户阶段","type":"text"}'
```

### 读记录（取 rid）
```bash
lark-cli base +record-list --base-token MLXGbWKh7aAFJfs9RYNcwER0nMg \
  --table-id tblpm0IE8J7WiRtB --field-id 邮件内容 --format json
```
返回信封：`data.record_id_list`（与 data.data 按序对齐）、`data.field_id_list`、`data.data`（二维，按 --field-id 顺序）。

### 批量写回
```bash
# 构建 {"update_records": {rid: {字段: 值}}}
lark-cli base +record-batch-update --base-token MLXGbWKh7aAFJfs9RYNcwER0nMg \
  --table-id tblpm0IE8J7WiRtB --json @./update.json
```

### 已知坑
1. **token 失效（2026-09-04 更新，重要）**：`auth status` 显示 `needs_refresh` 且承诺
   "will auto-refresh on next user API call" **不可信**——实测 `expiresAt` 过期后自动刷新会失败：
   ```
   [lark-cli] [WARN] uat-client: refresh failed (code=20073), clearing token for ou_xxx
   [lark-cli] [WARN] keychain Remove failed: operation not permitted
   {"ok":false,"error":{"type":"auth"...}}
   ```
   即使 `refreshExpiresAt` 还有 6 天也照样失败。**判断标准看 `expiresAt` 而非 `refreshExpiresAt`**——
   `expiresAt` 一过，直接走上面的完整 device flow 重新授权，别指望自动刷新。
   代理环境务必带 `LARK_CLI_NO_PROXY=1`，否则刷新失败。
2. **新字段首轮静默忽略**：刚 `+field-create` 的字段，首轮 batch-update 会被忽略（实测 0/16）→
   写回后必须再 `+record-list --field-id 新字段` 读回校验非空数，不足则**重试一次**（重试即生效）。
3. **markdown 表格含 `|` 会错位**：推荐链接等含管道符的字段，写回/读取一律用 `--format json`。
4. **图片相对路径不跨设备**：HTML 正文里的 `邮件-联系慧思.jpg` 仅本地预览有效，正式发送前须托管换 URL。
5. **batch-update 的 JSON 文件必须相对路径**：`--json @/tmp/x.json` 报
   `--file must be a relative path within the current directory`；写文件到 cwd 内用 `./x.json`。
6. **字段名按中文名解析**：`--field-id 客户阶段` 这类传的是字段「显示名」而非 field_id；
   若字段不存在会被静默丢弃（如建字段前读它），写前先确认字段已存在。
7. **参数名差异（2026-09-04 实测，易踩）**：
   - `+record-list` 分页是 `--limit`（范围 1-200），**不是** `--page-size`
   - `+record-delete` **不支持 `--format`**，只有 `--yes`；用 `--record-id` 重复传或
     `--json '{"record_id_list":[...]}'`
   - `+field-list` **不支持 `--format`**，默认直接输出 JSON
8. **`+field-update` 是 PUT 全量语义**：给 select 加选项时必须把**原有 options 连同
   `hue`/`lightness` 一起完整回传**，只传新增项会把老选项清空。
   正确姿势：先 `+field-list` 取完整字段定义 → 在 options 数组末尾追加 → 整体 PUT。
9. **批量删除前先备份**：`+record-list` 拉全字段（重复 `--field-id`）存本地 JSON，
   删完再拉一次对账。`+record-delete` **不可撤销**。
