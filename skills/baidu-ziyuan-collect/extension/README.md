# Browser Bridge Chrome 扩展

通用浏览器自动化 Chrome 扩展（MV3）——**本地 CLI ⇄ 真实 Chrome** 的桥接端。
配合 `scripts/bridge_server.py`（WebSocket 服务端）+ `scripts/control.py`（Python 客户端库）使用。

> 当前版本 **v1.3.0**

---

## 文件

| 文件 | 说明 |
|------|------|
| `manifest.json` | MV3 清单，端口/权限/后台 SW 声明 |
| `background.js` | Service Worker 主体：WebSocket 长连接 + 命令分发 + 错误自诊断 |
| `popup.html` / `popup.js` | 工具栏弹窗：显示连接状态与版本号 |

---

## 加载方式（Chrome / Edge）

1. 打开 `chrome://extensions`
2. 右上角开启 **开发者模式**
3. 点 **加载已解压的扩展程序**，选择本目录（含 `manifest.json` 的那一层）
4. 断言：扩展卡片出现「Browser Bridge」，工具栏图标 badge 显示 **ON**（表示已连上 Bridge Server）

> **改代码后必须回 `chrome://extensions` 点该卡片的刷新图标** 才生效。
> 若第一次刷新提示"无效"，再刷一次即可（通常是文件正在被写入）。
> 也可用 `reload_self` 命令让扩展自我热重载（注意：重载会清空 `storage.session`，之后需先 `navigate`）。

---

## 连接

| 项目 | 值 |
|------|-----|
| 端口 | `ws://localhost:9334`（独立于 XHS Bridge 的 9333） |
| 心跳 | 20 秒（< MV3 的 30 秒空闲回收阈值，防止 SW 休眠掉线） |
| 重连 | 指数退避 800ms → 5s |
| 权限 | `tabs` `scripting` `debugger` `activeTab` `alarms` `storage` |

---

## 命令集

| 命令 | 作用 |
|------|------|
| `navigate` | 导航到 URL（可复用/新开标签） |
| `evaluate` | 在目标页执行 JS（MAIN world 被 CSP 拦时自动回退 CDP） |
| `click_element` / `click_by_text` | 按选择器 / 按可见文本点击 |
| `get_text` / `get_url` / `get_html` | 读正文、当前 URL、整页 HTML |
| `type_text` / `get_value` | 文本输入 / 读值（native setter + input·change，React/Vue 受控组件可用） |
| `screenshot` | 截图（走 CDP `Page.captureScreenshot`，可截后台标签） |
| `scroll_to` / `list_tabs` | 滚动定位 / 列出标签 |
| `get_diagnostics` / `clear_diagnostics` / `probe_ext_errors` | 读/清/探测扩展内部错误（写入 `chrome.storage.local`，重载不丢） |
| `reload_self` | 扩展自我热重载 |

---

## v1.3.0 关键修复

- **心跳保活**：20s 心跳 + 快速重连，解决 MV3 SW 回收导致的"命令必失败"。
- **目标页持久化**：`lastTabId` / `lastUrl` 落 `chrome.storage.session`，SW 重启不丢。
- **同站点校验**：目标标签与目标页 host 不一致即视为用户切走 → 重建目标页，
  杜绝**静默读错页**（曾实测读到 ChatGPT 页面却不报错）。
- **`about:blank` 豁免**：不再被误判为特权页。
- **错误自诊断**：`error` / `unhandledrejection` / 命令失败自动落库，CLI 可直接读出。
- **CDP 通道**：`evaluate` 遇 CSP 自动回退（MAIN world 被拦也不失败）。

---

## 说明：本目录与运行路径的关系

扩展是 Chrome **从磁盘直接加载**的，开发时的实际加载路径通常位于工作区
`browser-bridge/extension/`。本目录是**随技能分发的源码快照**，便于在公开仓库中
查阅与再分发；两者内容保持一致。若在此修改代码，记得同步回实际加载目录并刷新扩展。
