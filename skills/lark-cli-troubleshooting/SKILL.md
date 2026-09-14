---
name: lark-cli-troubleshooting
description: "lark-cli（@larksuite/cli）报错排障手册：91402 NOTEXIST、user 身份丢失/needs_refresh、need_user_authorization、
  token_missing、设备码授权失败、令牌文件写回被拦。当任何飞书相关技能（lark-unified / feishu-bitable-news-daily /
  humance-email-push / feishu-doc-archive / baidu-ziyuan-collect 等）通过 lark-cli 取数或写入失败时先读本技能，
  按‘先证伪再改配置’的顺序定位，避免把令牌/授权问题误判成权限或网络问题。触发词：lark-cli 报错、91402、
  NOTEXIST、飞书取数失败、user identity missing、needs_refresh、设备码、refresh token、base token。"
agent_created: true
---

# lark-cli 排障手册

> 核心原则：**先用对照实验把范围收窄，再动手改东西。**
> 历史上最贵的两次误判都是"没核对字符串就下结论"——一次把 token 打错当权限问题（绕 30 分钟），
> 一次把沙箱拦 rename 当令牌失效（让人白扫 3 次授权码）。

## 0. 三分钟定位法

```bash
# ① 身份是否就绪
lark-cli auth status            # bot / user 各自的 status + available

# ② 同一类资源做对照（关键！）
lark-cli api GET "/open-apis/drive/v1/files" --params '{"page_size":1}'   # 通 → 网络/CLI/身份没问题
lark-cli base +base-get --base-token <已知可用的 base>                      # 通 → bot 身份没问题
lark-cli base +base-get --base-token <报错的 base>                          # 只有它挂 → 才轮到查"这个对象"

# ③ 看日志（真相通常在这里）
tail -40 ~/.lark-cli/logs/auth-$(date +%F).log
```

**判据速查**

| 现象 | 别急着怀疑 | 先查 |
|---|---|---|
| `91402 NOTEXIST` | 权限 / 协作者 | **token 字符串逐字符核对**（见 §1） |
| `token_missing` / `need_user_authorization` | 要去重新授权 | 日志里 `op=Set` 是否 `operation not permitted`（见 §2） |
| `auth status` 恒 `needs_refresh` | token 过期 | 同上，多半是写回失败而非真过期 |
| `device_code is invalid` | 用户没扫码 | 版本是否 1.0.45（见 §4） |
| 从 Python 调不通、shell 能通 | 二进制坏了 | 代理 / cwd / 环境变量差异 |

## 1. `91402 NOTEXIST`：先核对 token，别猜权限

`91402` 最常见的两个真因：**① token 打错一个字符；② 该应用确实不是这个 base 的协作者**。
必须先排除 ①，否则会朝 ② 白跑很久。

```bash
# 逐字符对比：把可疑 token 和已知可用的 token 并排看
printf '%s\n%s\n' "$BAD" "$GOOD" | fold -w1 | paste - - | awk '$1!=$2'
```

实测案例（2026-09-11）：`MLXGbWKh7aAFJfs9RYcwER0nMg` 少写一个 `N`，正确为
`MLXGbWKh7aAFJfs9RY**N**cwER0nMg`。同一个 base，错误 token 报 `91402`，正确 token **bot 与 user 身份都 `ok:true`**。

> 结论：**能同时用 bot 和 user 读通的 base，说明权限没问题**，不要再往协作者方向排查。

## 2. user 身份丢失 / 恒 `needs_refresh`：令牌文件可无损找回

**令牌落盘路径**：`~/Library/Application Support/lark-cli/cli_<appid>_<openid>.enc`（内容加密；macOS 另有 Keychain 存密钥）

**两种可恢复的坏状态**：

- **A. 刷新成功但写回失败**：日志出现
  ```
  path=/open-apis/authen/v2/oauth/token status=200         ← 飞书端已刷新成功
  component=keychain op=Set error=... rename ... .enc.<uuid>.tmp ... .enc: operation not permitted
  ```
  → 新 token 已**完整写在 `.enc.<uuid>.tmp`** 里，只差改名。沙箱拦截是 macOS 下常见原因。

- **B. 主文件缺失**：目录里只剩 `.tmp` / `.bak`（异常退出造成）。

**统一解法**（无需重新授权）：

```bash
D="$HOME/Library/Application Support/lark-cli"
B="cli_<appid>_<openid>.enc"
ls -lat "$D" | head            # 找 mtime 最新的那个 .enc.<uuid>.tmp
cd "$D" && mv "$B.<uuid>.tmp" "$B"     # 用实际 uuid 替换
lark-cli auth status           # 应立刻变 ready
```

⚠️ 两个硬约束：

1. **refresh token 一次性轮换**：用过即换。所以一旦刷新成功却没写回，旧 token 就废了 → **要抢在下次调用前修好**。
2. **刷新类命令尽量加 `dangerouslyDisableSandbox`**，否则每次刷新都写不回。

## 3. 读 Base 数据的正确姿势

```bash
# ✅ 推荐：shortcut，输出稳定
lark-cli base +record-list --base-token <T> --table-id <tbl...> \
  --limit 200 --format json --as bot        # --limit 上限 200

# ❌ 实测返回空，别用
lark-cli api GET "/open-apis/bitable/v1/apps/<T>/tables/<tbl>/records"
```

- **优先 `--as bot`**：bot 的 tenant token 由 app secret 派生、自动维护，**不依赖会过期的 user token**，适合定时任务。
  只有当资源对 bot 不可见（个人日历、个人邮箱等）才用 user。
- 返回结构是**矩阵**而非 records 数组：
  `data.fields`（表头）+ `data.data`（二维行）+ `data.record_id_list`。
- 🔴 **日期字段格式因来源而异**：`base +record-list` 给 **ISO 字符串**（`2026-08-28T00:00:00.000+08:00`），
  旧接口/导出给**毫秒时间戳**。解析函数必须两种都兼容，否则会把日期类统计静默算成 0。
- 先用 `base +table-list` 确认 `table_id` 与 `records_count`，再拉数据。

### 3.1 飞书 mail API：账号没绑邮箱时必然 `user not found`

读邮箱（`mail +triage` / `mail user_mailboxes …`）报 `[4013] [15180001] user not found` 时，
**先别怀疑授权或 scope**——大概率是该账号压根没有飞书邮箱：

```bash
lark-cli mail user_mailboxes profile --params '{"user_mailbox_id":"me"}' --as user
# → {"primary_email_address":"", "not_found_reason":"mailbox address not found"}   ← 确诊
lark-cli mail user_mailboxes accessible_mailboxes --params '{"user_mailbox_id":"me"}' --as user
# → {"accessible_mailboxes": []}
```

- **scope 齐全也照样失败**（实测 `mail:user_mailbox.message:readonly`、`mail:user_mailbox.folder:read` 都在）——
  这是账号属性问题，不是权限问题，别在授权上浪费时间。
- ❌ 别用 `authen/v1/user_info` 的 `email` 字段去猜 `user_mailbox_id`（该字段常为空字符串）。
- ❌ `mail user_mailbox.sent_messages` 只有 `recall` / `get_recall_detail`，**没有 list**，列不了已发送。
- ✅ 出路：换一个有邮箱的账号授权，或改走浏览器读邮箱页面（见 `humance-email-push` §5）。

## 4. 设备码授权在本机 1.0.45 上不可用

- `auth login --no-wait --json` 返回的 `device_code` 中**固定位置被替换成常量掩码**
  （三次独立生成长度恒 100、均含 `...rQIxGROOOOOOOOOO...`），拿去 `--device-code` 必报
  `device_code is invalid`，**不是用户没扫码**。要用先 `lark-cli update`。
- `auth login --device-code` 会**阻塞最长 10 分钟** → 必须放后台跑；且**不要在同一轮里既展示 URL 又立刻执行它**
  （同轮重启会作废上一轮 device code）。
- `auth qrcode --output` **只接受当前工作目录下的相对路径**（`./qr.png`），绝对路径报 `unsafe output path`。

## 5. 通用坑

- ⚠️ 从 **Python `subprocess`** 调 lark-cli 与 shell 直跑结果可能不同 → 先用 shell 复现，确认是调用环境还是授权问题。
- ⚠️ 系统代理会干扰：必要时 `LARK_CLI_NO_PROXY=1`，或 `NO_PROXY="localhost,127.0.0.1,::1"`。
- ⚠️ `--page-all` 与 `--output` 互斥；`--page-all` 输出可能是**多段 JSON 拼接**，须循环 `raw_decode`。
- ⚠️ 版本三处可能不一致（binary / skills / latest），`_notice` 里会提示；排障时先记下 `lark-cli --version`。

## 6. 修复后的自检清单

1. `lark-cli auth status` → 需要的身份是 `ready`
2. 对照实验：一个已知可用的 base 能 `ok:true`
3. 目标资源：`base +table-list` 能看到预期 `records_count`
4. 真实拉一次数据，**确认关键字段（尤其日期）解析非空**
5. 若是定时任务，加 `--as bot` 后再跑一遍
