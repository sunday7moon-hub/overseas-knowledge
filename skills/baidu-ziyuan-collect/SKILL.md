---
name: baidu-ziyuan-collect
description: 使用 Browser Bridge 通用扩展从百度搜索资源平台采集收录数据 (关键词/热门页面/索引量)
  并推送至飞书多维表格。当用户需要采集百度搜索资源平台的网站收录数据、SEO关键词表现、热门页面排名时使用。
agent_created: true
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

⚠️ **不要用 `nohup ... &`**（在沙盒/会话环境里会被回收，进程活不过几分钟）。
用**托管后台任务**方式启动，并带 `--log-file` 便于事后诊断：

```bash
cd /Users/yoyo/.workbuddy/skills/baidu-ziyuan-collect/scripts
NO_PROXY="localhost,127.0.0.1,::1" \
/Users/yoyo/.workbuddy/binaries/python/envs/default/bin/python3 \
  bridge_server.py --port 9334 --log-file /tmp/bridge_v2.log
# 以 run_in_background=true 执行
```

依赖：`websockets`（服务端）+ `websocket-client`（客户端）
```bash
/Users/yoyo/.workbuddy/binaries/python/envs/default/bin/pip install websockets websocket-client
```

**停止服务端**：只杀监听进程，别用 `lsof -ti:9334`（它会连带返回 Chrome 的 PID，误杀浏览器！）
```bash
for P in $(lsof -ti:9334 -sTCP:LISTEN); do kill "$P"; done
```

### 2. 确认扩展连接

通过 ping 命令验证：

```python
from control import Bridge
bridge = Bridge()
print(bridge.ping())      # 含 extension_version / reconnects / 成功率
if bridge.is_connected():
    print("Extension OK")
```

### 2.1 Bridge 客户端 API 能力边界（2026-09-03 实测）

| 方法 | 可用 | 说明 |
|------|------|------|
| `navigate(url)` | ✅ | 支持 URL 带 Strapi 过滤参数 |
| `get_html()` | ✅ | 完整 DOM，用于定位元素/解析表格 |
| `get_text()` | ✅ | 纯文本；列表页会被表格淹没，需正则定位 |
| `click_by_text(text, selector)` | ✅ | **selector 很关键，见下** |
| `click_element(selector)` | ❌ | 参数是**屏幕坐标**不是选择器，报 `params.x mandatory field missing` |
| `evaluate(js)` | ❌ | 被 Strapi 后台 CSP 拦截（`unsafe-eval` 不允许） |
| `screenshot()` | ❌ | 缺 `<all_urls>` / `activeTab` 权限 |
| 输入文本 | ❌ | **无任何 type/fill 方法，表单只能人工填** |

**踩坑 1：ping 必须带 `role: "cli"`**
裸 WebSocket 测试若只发 `{"method":"ping"}`，服务端走 `未知 role: None` 分支立即关闭连接（1000 OK），
会被**误判为"扩展断连"**。正确握手：`{"role":"cli","id":"x","method":"ping"}`。
→ 服务端日志能看到 `Extension 已连接`，那扩展就是好的。

**踩坑 2：`click_by_text` 必须限定 `selector`**
默认 `selector="*"`，会命中文本所在的**最内层 `<span>`**。合成 click 从 span 冒泡**不会触发 `<label>` 的关联激活行为**，
导致勾选框点了没反应。
→ 点 Strapi「Configure the view」的字段勾选框要用 `click_by_text('createdAt', selector='label')`。

**踩坑 3：`el.click()` 对 Radix UI 触发器有效但渲染有延迟**
`button[aria-haspopup="dialog"]` 点后需 `sleep(2~3)`，`role="dialog"` 才会出现在 DOM。
判断面板是否打开：查 `aria-expanded="true"` / `data-state="open"`。

### 2.2 v2 加固：4 个致命根因与修复（2026-09-11 实测）

> 背景：v1 全栈压测接通率 **0%**（8~10 轮全灭），排查出 4 个根因，修复后 **100%**（长跑 40/40）。

| # | 根因 | 症状 | 修复 |
|---|------|------|------|
| 1 | 服务端 `max_size` 默认 **1MB** | 真实页面 HTML 常 ≥1MB → 服务端用 **1009 (message too big)** 掐断扩展长连接 → 客户端报 `Connection to remote host was lost` | 服务端+客户端 `max_size` → **64MB** |
| 2 | `_lastTabId` 是模块级变量 | Service Worker 重启即丢失 → 回退"当前活动标签" → 常命中 `chrome://newtab` → `Cannot access a chrome:// URL` | 持久化到 `chrome.storage.session` + 跳过特权协议 |
| 3 | **静默读错页**（最危险） | 目标页记忆丢失后随手用活动标签，**不报错却返回用户正在看的别的页面**（实测读到 ChatGPT） | ① 扩展：脚本类命令**绝不回退活动标签**，找不到就按 `lastUrl` 重建后台标签，否则明确报错；② 客户端：`get_text(expect_url=...)` 读取前校验 |
| 4 | 服务端两个代码缺陷 | ① `_extension_ws.send` 无异常保护 → CLI 被裸断；② 旧连接 `finally` 无条件清 `_extension_ws` → 误清刚上线的新连接 | 发送异常保护 + **代际守卫** |

**v2 新增 API**（v1 API 全兼容，老脚本不用改）

```python
b = Bridge(verbose=True)          # verbose 打印重试/自愈日志
b.expect_url = ...                # 或逐次传参，见下

b.ensure_page("https://admin.humancehr.com/admin")   # 导航 + 校验 URL
# ⚠️ ensure_page 每次调用都会 navigate（重载页面）！
#    连续取数场景只在最开头调一次，之后改用 evaluate/get_text，详见 2.6 坑 1
txt = b.get_text(expect_url="https://admin.humancehr.com")  # 读错页直接抛错
html = b.get_html(expect_url="https://admin.humancehr.com")
b.stats_report()                  # "调用 N 次 / 成功 N / 重试 N → 接通率 xx%"
b.list_tabs()                     # 核查目标标签（含 privileged / remembered 标记）
b.wait_ready(timeout=35)          # 等扩展上线（覆盖重连窗口）
```

**错误分类**（客户端已内置重试，除非显式关闭）
- `BridgeUnavailable` / `BridgeTimeout` → **自动重试**（默认 3 次，退避 0.8~3s）
- `BridgePageError` → 特权页/页面不符，会尝试**自愈重导航**；仍失败才抛
- `BridgeIndeterminate` → 命令已下发但结果未知，**不自动重试**（避免重复点击）

**扩展 v1.1.0 关键改动**（需在 `chrome://extensions` 点刷新才生效）
- 20 秒**心跳保活**（对抗 MV3 Service Worker 空闲回收）
- 目标标签/URL 持久化到 `chrome.storage.session`
- 脚本类命令绝不静默回退活动标签（根治静默错数据）
- `onmessage` 捕获局部 socket + `readyState` 校验（防响应发给已关闭连接）
- 快速指数退避重连（0.8s → 5s）；命令级超时；新增 `list_tabs`

### 2.3 扩展 v1.2.0：CDP 通道 —— 绕过 CSP + 文本输入（2026-09-11）

**解决的问题**：① Strapi 后台有 `unsafe-eval` CSP，`evaluate` 用 `new Function()` 被拦；
② 扩展一直没有输入能力，"表单只能人工填"（API Token 创建、自定义日期区间全卡在这）。

**做法**：用 `chrome.debugger` 走 CDP 的 `Runtime.evaluate` —— **CDP 不受页面 CSP 限制**。

```python
# 1) evaluate 自动回退：MAIN world 被 CSP 拦 → 自动走 CDP，调用方无感
b.evaluate("document.title")

# 2) 文本输入（native setter + input/change 事件，React/Vue 受控组件也生效）
b.type_text("input[name='name']", "data-analysis")
b.type_text("input[type='date']", "2026-09-04")      # 日期也可写
b.get_value("input[name='name']")                    # {"ok": True, "value": "data-analysis", ...}
```

⚠️ 前提：扩展 ≥ v1.2.0 且已在 `chrome://extensions` 刷新。
若 `chrome.debugger.attach` 失败，通常是该标签页开着 DevTools —— 关掉即可。

### 2.4 后台 Analytics 数据统计页（2026-09-11 打通）

| 项 | 值 |
|---|---|
| 路径 | `https://admin.humancehr.com/admin/humance-analytics` |
| 进入方式 | 后台侧边栏点 `Analytics`：`b.click_by_text("Analytics", selector="a")` |
| 页面体量 | `get_text()` 约 13 万字符 / 2400 行，一次可取 |
| 板块 | 日期筛选(近7日/近30日/自定义) · 文章 PV·UV(2291 行) · 全事件 PV·UV · 订阅与公众号漏斗 · 全站 PV·UV 趋势(图表，**文本抓不到数值**) · 各动作计数 · **激活漏斗** |
| 时间窗 | 默认「近 7 日」= 今天−6 ~ 今天；要精确区间用 `type_text` 填自定义起止日期 + 点「查询」 |

**🔴 使用铁律：`article_view` 约 93–95% 是爬虫，禁止用于内容热度排行**
1. 人均浏览 **1.0086 次**（20,035 PV / 19,864 UV）——真人实测 1.33 次/人，≈1 是"爬虫每 URL 抓一次"的指纹
2. **2291 篇文章无一为零**，而百度口径 82% 内容 30 天零流量
3. 同期 UV **21,147** vs 百度 **1,137**（**18.6 倍**，2026-09-11 精确区间实测）

→ 🟡 **`page_view` 只可看趋势，不可当总量**：未滤爬虫，绝对值比百度真人 PV **高约 2 倍**
   （9/10 单日：后台 540 vs 百度 254）；且埋点 **9/10 才上线**（9/4–9/9 全为 0）。
   2026-09-11 曾误判为"与百度量级一致"，经三窗口对照实验推翻 —— 详见 2.6。
→ ❌ 不可用：`article_view`（内容排行）、`newsletter_box_view`（漏斗分母同样虚高）

### 2.5 扩展 v1.3.0：错误自诊断 + 收口"静默读错页"（2026-09-11 二轮）

**修的问题**

| # | 问题 | 说明 |
|---|---|---|
| A | `about:blank` 被误列为特权页 | `PRIVILEGED_RE` 含 `about:`，导致重建 `about:blank` 后自判"不可用"并报错。**`about:blank` 没有页面 CSP、可正常注入，必须豁免** |
| B | 目标页被手动切走后仍沿用 | remembered tab 存在但已切到别的站点时，仍被当作"目标" → **静默读错页的残留路径**。修复：**同 host 校验**，不同站即重建目标页 |
| C | 缺目标页时建 `about:blank` | 返回空内容＝静默假数据的变体。改为**明确报错**，提示先 `navigate` |
| D | 扩展报错看不见 | 见下 |
| E | `type_text` 每次都弹调试提示条 | 改为 **`executeScript` 优先**（纯 DOM 操作不受 CSP 限制），CDP 仅兜底 |
| F | `screenshot` 只能截可见标签 | 改走 CDP `Page.captureScreenshot`，可截后台标签，失败回退 |

**D 的落地：错误自收集（不再需要人工看 chrome://extensions）**

```python
b.get_diagnostics()      # 自检（各 API 可用性 / ws 状态 / 心跳 / 目标页）+ 已收集的错误
b.clear_diagnostics()    # 排查新问题前先清空，便于归因
b.probe_ext_errors()     # 尝试用 CDP 直读 chrome://extensions 卡片错误（Chrome 常禁止，失败属预期）
```

扩展侧把 **未捕获异常 / 未处理 Promise rejection / 命令失败 / SW 启动记录** 写入
`chrome.storage.local`（**重载后仍保留**，session 会被清空所以不能用它），各留最近 30 条。

**G 的落地：扩展自我热重载（v1.3.0 起不用再人工点刷新）**

```python
b.reload_extension()     # 等价于在 chrome://extensions 点刷新，约 1.2s 后生效
time.sleep(3); b.wait_ready(35)   # 等扩展重连
b.navigate(url)          # ⚠️ 重载清空 storage.session，必须重新建立目标页
```

⚠️ 首次升级到 v1.3.0 仍**必须人工点一次刷新**（旧版本没有这条命令）；之后改扩展即可自助重载。

**一键自检脚本**（改扩展后必跑）

```bash
cd ~/.workbuddy/skills/baidu-ziyuan-collect/scripts
python3 bridge_selftest.py                 # 连接/版本/自检/错误探测
python3 bridge_selftest.py --bench 10      # 追加 10 轮命令序列压测（含 type_text 写读校验）
```

### 2.6 按自定义区间取后台数据（页面方式 · **已降级为备选，首选见 2.7**）

**坑 1：`ensure_page()` 每次调用都会重新导航 → 页面重载 → 读到空页面**
`ensure_page` 内部是**无条件 `navigate()`**。若在取数循环里每轮都调它，页面会反复回到加载态，
`body.innerText` 长度变成 0（或只有 `Loading content.`）。

✅ 正确姿势：**导航一次 → 轮询等到就绪 → 之后只用 `evaluate` / `get_text`**
（它们沿用扩展记住的目标标签，不会重载）。

```python
b.navigate(URL)                      # 只导航这一次
while len(body()) < 10000: time.sleep(2)   # 等 SPA 渲染完
# 后面所有操作都用 evaluate / click_by_text / type_text，不要再 ensure_page
```

**坑 2：SPA 异步取数 —— 必须做"稳定判定"，否则拿到中间态**
点「查询」后数据是异步刷新的。判定标准：**连续 3–4 次读取 body 文本完全一致**才导出。
只看"两次长度差 < 200"太松（会漏掉数字还在跳的中间态）。

**坑 3：`input[type=date]` 没有 id/class，两个框无法区分**
先打临时标记再写值，并用 `get_value` 回读校验：

```python
b.evaluate("""(()=>{const a=document.querySelectorAll('input[type=date]');
  a[0].id='bs'; a[1].id='be'; return a.length;})()""")
b.type_text("#bs", "2026-09-04"); b.type_text("#be", "2026-09-10")
b.get_value("#bs")            # {'ok':True,'value':'2026-09-04'} 写入成功
b.click_by_text("查询", selector="button")
```

**完整流程已封装**：

```bash
python3 admin_analytics_pull.py --start 2026-09-04 --end 2026-09-10
# 输出 /tmp/admin_analytics_<start>_<end>.txt，并打印核心指标 JSON
```

**🔬 定位指标口径的两种方法**

**方法 A：三窗口加减法（快速，但只能定位到"附近"）**

| 窗口 | 全站 PV |
|---|---:|
| 9/4–9/10（自定义） | 540 |
| 9/5–9/11（自定义，= 预设"近 7 日"1,289 ✓ 自洽） | 1,289 |
| 9/11 单日（自定义） | 749 |

→ 9/4 单日 = 540 + 749 − 1,289 = **0** ⇒ 埋点起点在 9/4 之后
→ 同时验证「自定义区间」与「预设按钮」口径一致（1,289 ≈ 1,286/1,287）

⚠️ **局限**：只能得出"9/4 为 0"，**无法定位具体是哪一天开始**。
2026-09-11 曾据此误判为"9/5 上线"（实为 **9/10**），并进一步推出"9/11 是异常尖峰"的错误结论。

**方法 B：逐日明细（金标准，一次定位到日）** ← 优先用这个

走 API 通道拿 `daily_buckets`（见 2.7）：

```bash
python3 strapi_analytics_pull.py --start 2026-09-04 --end 2026-09-10
```

```
2026-09-04  pv=0     uv=0
...
2026-09-09  pv=0     uv=0
2026-09-10  pv=540   uv=496     ← 埋点起始日，一眼可见
```

### 2.7 ⭐ admin API 直取（2026-09-11 打通 · 优于页面取数）

**这是首选取数方式**，2.6 的页面取数降级为备选。

```bash
python3 strapi_analytics_pull.py --start 2026-09-04 --end 2026-09-10
# → /tmp/humance_analytics_<start>_<end>.json（结构化，含 daily_buckets / event_metrics / article_metrics）
```

| 对比 | API 直取（2.7） | 页面取数（2.6） |
|---|---|---|
| 返回 | **结构化 JSON** | 13 万字符文本，需正则解析 |
| 耗时 | **秒级** | 1 分钟+（含稳定判定） |
| 逐日数据 | ✅ `daily_buckets` | ❌ 图表，文本抓不到 |
| 依赖 | admin 登录态（JWT） | 同左 + 扩展输入能力 |

**接口**：`GET /api/analytics-events/summary?period=range&start=YYYY-MM-DD&end=YYYY-MM-DD`

**⚠️ 关键坑：API Token 走不通这个端点**

服务端对该端点做了**强制管理员校验**，返回 `{"message":"仅管理员可查看埋点统计"}`。
所以用 API Token（哪怕是 Read-only + find 权限已勾选）**必然 401** —— 这是设计如此，不是权限没配。

→ 可行路径：**在浏览器上下文里带 `localStorage.jwtToken` 发 fetch**（脚本已封装）。
→ JWT 过期（约 30 天）时脚本会提示重新登录 admin.humancehr.com。

**如何发现这个接口**（可复用技巧）：注入 fetch/XHR 钩子，然后让 SPA 自己发一次请求：

```js
window.__reqs = [];
const of = window.fetch;
window.fetch = function(...a) { window.__reqs.push(String(a[0])); return of.apply(this, a); };
const oo = XMLHttpRequest.prototype.open;
XMLHttpRequest.prototype.open = function(m, u, ...r) { window.__reqs.push(m + ' ' + u); return oo.call(this, m, u, ...r); };
// 然后点击侧边栏触发 SPA 请求，再读 window.__reqs
```

### 2.8 📊 可视化看板生成（2026-09-11 新增 / 09-11 扩充数据源）

一条命令产出**单文件 HTML 数据看板**（深色主题、零 CDN 依赖、**无水印**、可离线打开 / 直接截图发群），
含 10 个模块：一句话结论 · KPI 卡组 · DAU/WAU/MAU 全景（柱状图 + 7 日均值线）·
新老访客质量对比 · 深度行为渗透漏斗 · **用户转化链路（注册→登录→产生行为）** ·
**邮件触达队列与推送状态** · 2026 月度趋势 · 流量来源结构 · 内容 TOP10 ·
本期快照 · 风险与行动建议。

**每块面板头部均标注该块的数据来源**（百度统计 / 慧思后台 Strapi / 飞书多维表），页脚有完整来源对照表。

```bash
cd scripts
# 月报口径（最近 30 个完整日，默认）
NO_PROXY="localhost,127.0.0.1,::1,openapi.baidu.com" python3 humance_dashboard.py --preset month
# 周报口径（最近 7 个完整日）—— 对齐全站周报窗口
NO_PROXY="localhost,127.0.0.1,::1,openapi.baidu.com" python3 humance_dashboard.py --preset week --end 2026-09-10
# 任意自定义窗口
NO_PROXY="localhost,127.0.0.1,::1,openapi.baidu.com" python3 humance_dashboard.py \
  --start 2026-09-04 --end 2026-09-10 --out "../outputs/看板.html"
```

**三个数据源（2026-09-11 扩充）**

| # | 数据源 | 提供什么 | 失败时行为 |
|---|---|---|---|
| ① | 百度统计 Site 22551575 | PV / 访客人次 / 新老访客 / 来源 / 停留 / 跳出 / 内容 TOP | 直接报错退出 |
| ② | 慧思后台 Strapi admin（Bridge + 管理员 JWT） | 累计注册·收藏·订阅；**本期注册 / 登录用户 / 产生行为用户 / 登录 DAU** | 回退内置默认值并标注 |
| ③ | 飞书多维表「客户触达邮件同步」 | **邮件触达队列 / 分类 / 推送状态 / 本期计划推送** | 实时失败 → 回退本地缓存 |

- **窗口无关**：`WAU / MAU` **始终以「窗口末日」为基准向前取 7 / 30 天**，与窗口长度无关；
  所有「30 天」字样按实际天数渲染。套 7 天周窗口时不会把 7 天合计错标成 MAU。
- 默认窗口 = **昨天往前推 30 个完整日**（不含当天，避免半天数据压弯曲线）；`--preset week` = 前推 7 天。
- 开关：`--no-strapi`（跳过 Bridge 全部查询）/ `--no-ops`（只跳注册·登录·行为）/ `--no-mail`（只跳邮件触达）。
  **任一来源不可用时会明确标注或跳过，不会静默写 0。**

**运营口径（②）怎么取 —— 2026-09-11 打通的字段级路径**

```
User 表        /content-manager/collection-types/plugin::users-permissions.user
               → createdAt（注册时间）/ last_login_at（最后登录）/ register_source·register_type
埋点事件表     /content-manager/collection-types/api::analytics-event.analytics-event
               → filters[occurredAt][$gte/$lte] + filters[actorUserId][$notNull]=true
                 即「有登录态的埋点行为」，actorUserId 去重 = 产生行为用户；按日聚合 = 登录 DAU
```

- 🔴 **注册数一律用 User 表**（`register_success` 埋点覆盖不全：本期只记 2 条，与 User 表一致但历史上大量缺失）。
- 🔴 **登录用户有两套口径，必须同时看**：`last_login_at ≥ 窗口首日`（只记最后一次登录）vs
  `actorUserId 非空`（窗口内有行为）。两者不一致时取较大值作为**下界**（`login_success` 埋点缺失）。
- 🔴 **内部账号（@xinfushe.com / @yonyou.com）必须剔除**，否则同事自测行为会污染「产生行为用户」（本期 8 人中占 2 人）。
- 时间切窗统一按**北京时间 UTC+8** 换算成 ISO 再传 `filters`。

**邮件触达（③）怎么取**

```bash
LARK="/Users/yoyo/.workbuddy/binaries/node/cli-connector-packages/lib/node_modules/@larksuite/cli/bin/lark-cli"
"$LARK" base +record-list \
  --base-token MLXGbWKh7aAFJfs9RYNcwER0nMg \
  --table-id  tblpm0IE8J7WiRtB \
  --limit 200 --format json          # 实测 200 条/页上限；69 条一次拉完
```

> ⚠️ 别用 `api GET /open-apis/bitable/v1/apps/<token>/tables/<tid>/records`——实测返回空，
> 用 `base +record-list` 才稳定。输出结构：`data.fields`（表头）+ `data.data`（二维行数组）+ `data.record_id_list`。

- 🔴 **base token 是 `...RYNcwER0nMg`，不是 `...RYcwER0nMg`**（少一个 `N`）。曾把 `RYcw` 打进脚本与文档，
  导致长期报 `code 91402 NOTEXIST`，并**被误判成"应用被移出 base 协作者"排查了半小时**。
  教训：`91402` 别急着往权限方向猜，**先把 token 字符串逐字符核对一遍**，或换一个已知可用的 base 做对照。
- ⚠️ `--page-all` 与 `--output` 互斥；`--page-all` 的输出可能是**多段 JSON 拼接**，需循环 `raw_decode`。
- ⚠️ **从 Python `subprocess` 调用 lark-cli 与在 shell 里直接跑，结果可能不同**（同一二进制）；
  诊断时先用 shell 跑一遍确认是「调用环境问题」还是「权限/授权问题」。
- 脚本仍保留**本地缓存兜底**：`~/.workbuddy/secrets/feishu_email_records_cache.json`（权限 600，
  实时成功时自动覆写）→ 失败时读缓存并在面板标注「本地缓存 · 抓取于 MM-DD HH:MM」，**不静默写 0**。

**lark-cli user 身份：丢失后如何找回（含 keychain 写入被沙箱拦截的解法）**

```bash
lark-cli auth status        # user identity: missing / needs_refresh / ready
```

- 🔴 **token 落盘路径**：`~/Library/Application Support/lark-cli/cli_<appid>_<openid>.enc`（内容加密）。
- 🔴 **坑：刷新成功但写回失败**。现象是 `auth status` 永远 `needs_refresh`，用 user 身份调用报
  `need_user_authorization / token_missing`。去 `~/.lark-cli/logs/auth-YYYY-MM-DD.log` 里能看到真相：
  ```
  path=/open-apis/authen/v2/oauth/token status=200      ← 刷新其实成功了
  component=keychain op=Set error=... rename ... .enc.<uuid>.tmp ... .enc: operation not permitted
  ```
  **根因：沙箱不允许 rename**，新 token 已经完整写在 `.enc.<uuid>.tmp` 里，只差最后一步改名。
- ✅ **解法（无需重新授权）**：找到最新的那个 `.enc.<uuid>.tmp`（mtime = 刚才失败的时间点），
  手工 `mv` 成 `.enc` 即可，`auth status` 立刻变 `ready`：
  ```bash
  D="$HOME/Library/Application Support/lark-cli"
  B="cli_aa9c1f8540f9dbe9_ou_YOUR_OPENID.enc"
  mv "$D/$B.f66b8ea5-....tmp" "$D/$B"      # 用实际 uuid 替换
  ```
  同理：**如果 `.enc` 主文件缺失、只剩 `.tmp`/`.bak`**（异常退出会造成这种状态），把最新的一个改名回 `.enc` 就能恢复身份。
- ⚠️ 需要 token 刷新续期的命令，**尽量加 `dangerouslyDisableSandbox`**，否则每次刷新都写不回、还会因为
  refresh_token 轮换而把旧 token 作废（**refresh token 一次性**，用过即换，丢了就要重新走设备码）。
- ⚠️ 设备码授权在本机 lark-cli 1.0.45 上**不可用**：`--no-wait --json` 返回的 `device_code` 中固定位置
  被替换成常量掩码段（三次独立生成均得到 `...rQIxGROOOOOOOOOO...`），拿去 `--device-code` 必然报
  `device_code is invalid`。**先升级 lark-cli 再走这条路**，别反复让用户扫码。
- ⚠️ `auth qrcode --output` **只接受当前目录下的相对路径**（如 `./qr.png`），绝对路径报 `unsafe output path`。
- ⚠️ `auth login --device-code` 会阻塞最长 10 分钟 → 必须放后台跑，且**同一轮里不要既展示 URL 又立刻执行它**
  （同轮重启会作废上一轮 device code）。

**四个踩坑（必读）**

1. 🔴 注册用户 / 收藏 / 订阅这三个 content-type **只认管理员 JWT，API Token 一律 401**（实测
   `/api/subscriptions` `/api/favorites` `/api/users` 全部 401）。脚本会自动
   `navigate(admin, new_tab=True)` 再读 `localStorage.jwtToken`。
2. 🔴 **`jwtToken` 存的是带引号的 JSON 字符串，必须先 `JSON.parse`** —— 直接取值会 401，
   且报错信息与"未登录"一模一样，极易误判为登录态失效。
3. 百度 `gran=day` 单次仅返回 20 行 → 脚本内置分段（每段 ≤20 天）合并；7 日均值线额外多取 6 天。
4. 自查渲染效果：**无头 Chrome 直接截整页最省事**（不必起 HTTP 服务，也不依赖扩展截图权限）——
   ```bash
   "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless --disable-gpu \
     --no-sandbox --hide-scrollbars --window-size=1360,6200 --screenshot=/tmp/x.png "file:///path/to.html"
   ```
   注意 `window-size` 高度要足够（本看板约 4,400px），否则底部被截断。

**导出 PDF（对外发送 / 归档版）**

```bash
cp "outputs/xxx看板.html" /tmp/render.html        # ⚠️ 中文路径必须先转英文，否则静默失败
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless --disable-gpu \
  --no-pdf-header-footer --print-to-pdf=/tmp/render.pdf file:///tmp/render.html
```

看板 HTML **已内置打印样式**（A4 横向 / 栅格强制锁回桌面列数 / Heiti SC 字体嵌入），
但 **2026-09-11 起默认不含水印**（内部使用版）。
如需对外带水印版本，在 `</body>` 前插入水印层即可（`.wm` 样式仍保留在 `@media print` 中）：

```html
<div class="wm" aria-hidden="true"><span>用友薪福社 · Humance</span> ×12</div>
```

> 🔴 **改版式时务必保留 `@media print` 里的两段**：
> ① `grid-template-columns` 系列 `!important` —— 打印视口会命中 **≤900px 响应式断点**，
> 不锁就会把 6 列 KPI / 4 列指标卡压成 2–3 列，面板变高被整体推下页，**页数从 4 虚增到 8**；
> ② `body{zoom:.9}` —— 让最高的 DAU 面板刚好落进首页。
> 详见 `html-to-pdf-print` 技能的「打印视口会命中响应式断点」一节。

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

Browser Bridge 扩展**随本技能一起分发**，源码位于本技能目录下的 `extension/`：

- 技能内快照（随技能分发/公开仓库）：`extension/`（manifest.json / background.js / popup.html / popup.js）
- 详见 [`extension/README.md`](extension/README.md)（加载步骤、端口、完整命令集、v1.3.0 修复清单）
- 开发时 Chrome 实际加载盘路：`/Users/yoyo/WorkBuddy/2026-07-22-11-06-35/browser-bridge/extension`
- 打包产物：`browser-bridge-extension-v1.3.0.zip`

关键特点：
- 当前版本 **v1.3.0**，使用端口 9334（独立于 XHS Bridge 的 9333）
- manifest 需要 `tabs`、`scripting`、`debugger`、`activeTab`、`alarms`、`storage` 权限
- **心跳保活**：WebSocket 上每 **20 秒**发一次心跳（低于 MV3 的 30s 空闲阈值），
  `chrome.alarms(0.5min)` 仅作兜底拉起
- 脚本类命令**只操作"记住的目标标签"**，绝不回退到当前活动标签（防静默错数据）；
  **且目标标签必须与目标页同 host**，否则视为用户已切走 → 重建目标页
- 连接后 badge 显示「ON」；popup 显示连接状态与版本号（版本从 manifest 动态读取）
- **改完代码必须到 `chrome://extensions` 点该卡片的刷新图标才会生效**；
  若第一次刷新显示"无效"，再刷一次即可 —— 通常是文件正在被写入。
  也可用 `reload_self` 命令热重载（会清空 `storage.session`，之后需先 `navigate`）

## 敏感凭据（别写进公开仓库）

| 变量 | 用途 | 存放 |
|------|------|------|
| `BAIDU_TONGJI_TOKEN` | 百度统计 access_token（`humance_dashboard.py` 拉数） | 环境变量，或 `~/.workbuddy/secrets/baidu_tongji_token.txt`（单行，权限 600） |

`humance_dashboard.py` 已改为**运行时读取**（env → 密钥文件），源码内不再硬编码 token。
公开仓库副本严禁出现真实 token。


## 故障处理

| 症状 | 原因 | 修复 |
|------|------|------|
| `Connection to remote host was lost`（尤其 `get_html` 时） | 服务端 `max_size` 1MB < 页面 HTML 体积 → 1009 掐断 | 用 v2 服务端（max_size 64MB） |
| `Cannot access a chrome:// URL` | 目标标签记忆丢失，回退到特权页 | 用 v1.1.0+ 扩展（持久化 lastUrl + 跳过特权页） |
| 读到**别的页面**内容却不报错 | 静默回退活动标签 / 目标标签被手动切走（最危险） | v1.3.0 扩展（同 host 校验）+ `get_text(expect_url=...)` 双保险 |
| 「重建 about:blank 后仍不可用」 | `about:blank` 被误判为特权页 | v1.3.0 已豁免（`about:blank` 可正常注入） |
| 「尚无目标页（未调用过 navigate）」 | 扩展重载清空了 `storage.session` | 先 `b.navigate(url)` 建立目标页，再读 |
| 扩展卡片显示红字「错误」 | 需读具体文本 | `b.get_diagnostics()` / `b.probe_ext_errors()` 自动读取（见 2.5） |
| `extension_connected: False` | Service Worker 休眠 | `Bridge().wait_ready(35)` 等重连，或打开扩展 popup 唤醒 |
| `extension_connected: False` **但日志显示已连接** | **探针没带 `role:"cli"`** | 见 2.1 踩坑 1，别误判扩展断连 |
| `chrome.debugger.attach` 失败 | 该标签页开着 DevTools | 关掉 DevTools；或改用 `executeScript` 路径 |
| 导航超时 | 页面加载慢 | navigate 有 10 秒等待上限，超时也会返回 |
| 无数据行 | 页面未加载完成 / 站点未选中 | 等 10 秒后再读，检查 URL 是否含 `site=` 参数 |
| 飞书推送失败 | lark-cli 版本不匹配 | 更新 lark-cli: `lark-cli update` |
| 进程莫名消失 | 用了 `nohup ... &` 被回收 | 改用托管后台任务（见第 1 节） |
| 误杀了浏览器 | `lsof -ti:9334` 连带返回 Chrome PID | 用 `lsof -ti:9334 -sTCP:LISTEN` 只取监听者 |

## 脚本文件说明

| 文件 | 用途 |
|------|------|
| `scripts/bridge_server.py` | WebSocket Bridge 服务端（v2：max_size 64MB / 等待重连 / 代际守卫） |
| `scripts/control.py` | Python 客户端库（v2：自动重试 / wait_ready / 特权页自愈 / expect_url / type_text / get_diagnostics） |
| `scripts/bridge_selftest.py` | **一键自检**：连接+版本 / 扩展自检+错误 / 错误探测 / 命令序列压测 |
| `scripts/admin_analytics_pull.py` | 后台 Analytics **页面取数（备选）**：`--start/--end` 或 `--preset 7d/30d`，输出完整文本 + 核心指标 + 文章 TOP |
| `scripts/strapi_analytics_pull.py` | ⭐ **后台取数首选**：admin API 直取**结构化 JSON**（`--start/--end`），秒级返回，含逐日 buckets 与全量文章排行 |
| `scripts/strapi_daily_events.py` | 按北京时间逐日统计 Strapi 埋点事件数 |
| `scripts/humance_dashboard.py` | 📊 **可视化看板生成器**：一次跑完 → 单文件 HTML（深色主题 / 零 CDN / 无水印 / 可离线打开与截图）。**三源合并**：百度统计（流量）+ Strapi admin（注册·登录·产生行为·登录 DAU）+ 飞书多维表（邮件触达队列与推送状态）。含 DAU-WAU-MAU 全景、新老访客对比、深度行为漏斗、用户转化链路、邮件触达、月度趋势、来源结构、内容 TOP、本期快照、风险建议；每块面板标注来源 |
| `scripts/collect_and_push.py` | 集成采集 + 飞书推送入口脚本 |
| `scripts/wx_article_fetch.py` | 抓取微信公众号文章正文（辅助采集） |
| `extension/` | **Chrome 扩展源码**（v1.3.0，随技能分发）：manifest / background / popup，详见 `extension/README.md` |
