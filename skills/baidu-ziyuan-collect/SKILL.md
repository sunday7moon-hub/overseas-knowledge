---
name: baidu-ziyuan-collect
description: 使用 Browser Bridge 通用扩展从百度搜索资源平台采集收录数据 (关键词/热门页面/索引量)
  并推送至飞书多维表格。当用户需要采集百度搜索资源平台的网站收录数据、SEO关键词表现、热门页面排名时使用。
agent_created: true
disable-model-invocation: true
---

# Baidu Ziyuan Collect Skill

通过 Browser Bridge Chrome 扩展连接用户真实 Chrome 浏览器，自动采集百度搜索资源平台（ziyuan.baidu.com）的 SEO 数据，并推送至飞书多维表格「网站收录数据」。

## 前置条件

1. **Chrome 扩展** — 确保 `chrome://extensions/` 中已加载 Browser Bridge 扩展（manifest.json 位于 workspace 的 `browser-bridge/extension/`）
2. **Bridge Server** — 启动 WebSocket 服务（端口 9334，与 XHS Bridge 端口 9333 隔离）
3. **飞书 Bitable** — 已有「网站收录数据」多维表格（base_token 见配置）
4. **Chrome 登录** — 用户需在 Chrome 中已登录百度搜索资源平台且有站点权限

## 工作流程

### 1. 启动 Bridge Server

用双 fork 方式启动，确保进程完全脱离父进程：

```bash
python3 /Users/yoyo/.workbuddy/skills/baidu-ziyuan-collect/scripts/bridge_server.py --port 9334 &
```

使用 `setsid` + `nohup` 或 Python 双 fork 方式完全脱离。

### 2. 确认扩展连接

通过 ping 命令验证：

```python
from control import Bridge
bridge = Bridge()
if bridge.is_connected():
    print("Extension OK")
```

### 3. 执行采集 + 推送飞书

运行集成脚本：

```bash
python3 /Users/yoyo/.workbuddy/skills/baidu-ziyuan-collect/scripts/collect_and_push.py
```

脚本自动完成：
- 导航到关键词页（30天数据）
- 采集热门关键词表格
- 切换至热门页面 tab 并采集
- 推送每条数据至飞书对应子表

### 4. 切换时间范围

脚本默认采集近30天数据。如需近7天，修改 collect_and_push.py 中的 `URL_30D` 变量，将 `range=month` 改为 `range=week`。

新增后还需要在热点范围字段也写入对应值。

## 数据结构

### 飞书多维表格「网站收录数据」

**关键词表（tblLQ3fk9uEba8GC）：**
| 字段 | 类型 | 说明 |
|------|------|------|
| 关键词 | 文本（主） | 搜索词 |
| 展现量 | 文本 | 搜索结果中展示次数 |
| 点击量 | 文本 | 被点击次数 |
| 点击率 | 文本 | 点击/展现百分比 |
| 排名 | 文本 | 平均排名 |
| 采集时间 | 日期时间 | yyyy/MM/dd HH:mm |
| 热点范围 | 单选 | 近7天 / 近30天 |
| 渠道 | 单选 | 百度 |

**热门页面表（tblDPecpiO1TDj0F）：**
| 字段 | 类型 | 说明 |
|------|------|------|
| URL | 文本（主） | 页面链接 |
| 展现量 | 文本 | 展现次数 |
| 点击量 | 文本 | 点击次数 |
| 点击率 | 文本 | CTR |
| 排名 | 文本 | 平均排名 |
| 采集时间 | 日期时间 | 采集时间 |
| 热点范围 | 单选 | 近7天 / 近30天 |
| 渠道 | 单选 | 百度 |

### URL 参数

关键词页 URL 模板：
```
https://ziyuan.baidu.com/keywords/index?range={range}&site={site_url_encoded}
```

- `range=month` — 近30天
- `range=week` — 近7天
- `site=` — URL 编码的站点地址，如 `https%3A%2F%2Fwww.humancehr.com%2F`

## 扩展说明

Browser Bridge 扩展位于 workspace 的 `browser-bridge/extension/` 目录。

关键特点：
- 使用端口 9334（独立于 XHS Bridge 的 9333）
- manifest 需要 `tabs`、`scripting`、`debugger`、`activeTab`、`alarms`、`storage` 权限
- 通过 `chrome.alarms` 每 30 秒心跳保活 Service Worker
- 连接后 badge 显示「ON」

## 故障处理

| 症状 | 原因 | 修复 |
|------|------|------|
| `extension_connected: False` | Service Worker 休眠 | 等待 5 秒自动重连，或打开扩展 popup 唤醒 |
| 导航超时 | 页面加载慢或 waitForTabComplete 未触发 | navigate 本身有 8 秒超时机制，超时也会返回 |
| 无数据行 | 页面未加载完成 / 站点未选中 | 等 10 秒后再 evaluate，检查 URL 是否包含 `site=` 参数 |
| 飞书推送失败 | lark-cli 版本不匹配 | 更新 lark-cli: `lark-cli update` |
| 多次断连 | 端口冲突（XHS Bridge 也在用 9333） | 确认是独立端口 9334，互不干扰 |

## 脚本文件说明

| 文件 | 用途 |
|------|------|
| `scripts/bridge_server.py` | WebSocket Bridge 服务端，接收扩展和 CLI 连接 |
| `scripts/control.py` | Python 客户端库，封装 navigate/evaluate/click 等命令 |
| `scripts/collect_and_push.py` | 集成采集 + 飞书推送入口脚本 |
