# 百度统计 API 口径与踩坑（humancehr.com · Site 22551575）

> 本文是**口径铁律的唯一真相源**。此前这些规则只写在会话记忆里（MEMORY.md），
> 而记忆会被截断、会腐烂 —— 2026-09-15 迁入技能时发现记忆里记录的 2 个 token 全已失效，
> 唯一存活的反而藏在脚本里。**规则住在技能里，不住在记忆里。**

---

## 一、口径铁律（对外汇报必须遵守）

### 1. UV / visitor_count 跨天不去重
`visitor_count` 在**多日区间**内 = **逐日人次相加**，不是独立访客数。
- ✅ 对外/对上汇报，必须写「**访客人次**」，不能写「访客数」「用户数」
- 独立用户估算 ≈ 人次 × **93–94%**（两组数据互证）

### 2. DAU 精确，WAU / MAU 只能估算
| 指标 | 可否精确 | 原因 |
|---|:--:|---|
| **DAU** | ✅ 精确 | 单日内百度已去重 |
| **WAU / MAU** | ⚠️ 只能估算 | API 无跨天去重能力；`overview/getTimeTrendRcRc` 已 404 下线 |

估算公式：
```
独立访客 ≈ 新访客数 + 老访客人次 ÷ 平均到访天数
```
> 老访客占比仅 ~9%，因此误差可控（实测 3–6%）。
> 用 `baidu_dau.py` 的 `dedup_est` 字段可直接得到多组「平均到访天数」下的敏感性取值。

### 3. `gran=day` 单次只返回最近 20 行
- ⚠️ **超出部分被静默丢弃，不报错** → 曾据此误判「8/4 之前没有数据」
- >20 天的查询**必须分段（每段 ≤20 天）再合并**；`baidu_dau.py` 已内置分段
- `gran=month` / `gran=week` 无此问题

### 4. 字段名坑
- 停留时长指标名是 **`avg_visit_time`**；写 `avg_time` 会被**静默忽略**
- 汇总值取 `result["sum"][0]`（`pageSum` 结构不同，别混用）

### 5. 响应结构
```json
{"result": {"fields": [...], "items": [[维度...],[指标...]], "sum": [[...]], "total": N}}
```
- ⚠️ 是 **`d["result"]`**，不是 `d["data"]["result"]`（写错会得到 `None`，且**不报错** → 极易误判成「token 失效」）
- 错误判断：`d.get("error_code")` 非空才是真错误；`result` 为 `null` 另有原因

### 6. 网络
- `openapi.baidu.com` **必须绕过系统代理**（本机沙箱装有代理，走代理会静默返回空）
- `_baidu_auth.py` 在 import 时已 `install_opener(ProxyHandler({}))`，全进程生效

### 7. 真人流量判定金标准
**周末访客 ÷ 工作日访客 ≈ 0.54** 才是真人流量（爬虫 ≈0.89，因为爬虫不过周末）。
每周报都应用它验一次。`baidu_dau.py` 输出里含 `weekday_weekend` 字段。

---

## 二、常用 method 速查

| method | 用途 | 备注 |
|---|---|---|
| `trend/time/a` | 时间趋势 | 配 `gran=day/week/month`、`visitor=new/old` |
| `source/all/a` | 全部来源 | |
| `source/engine/a` | 搜索引擎 | |
| `source/searchword/a` | 搜索词 | |
| `visit/toppage/a` | 受访页面 TOP | |
| `visit/landingpage/a` | 入口页面 TOP | |
| `visit/district/a` | 地域分布 | 到省级 |

常用 metrics：`pv_count` `visitor_count` `ip_count` `new_visitor_count`
`avg_visit_time` `bounce_ratio` `trans_count`

---

## 三、OAuth 凭据（2026-09-15 重构）

### 现状
- 凭据**唯一真相源**：`~/.workbuddy/secrets/baidu_tongji.json`（权限 600）
- 读取逻辑全在 `scripts/_baidu_auth.py`，**任何脚本都不得硬编码凭据**
- `refresh_token` **每次刷新即轮换**（旧值立即作废）→ `_baidu_auth` 刷新后自动回写 secrets

### 为什么重构（事故记录）
2026-09-15 迁移脚本时发现：
- 8 个脚本里硬编码了 **4 组不同的 token**，状态互不知情
- `baidu_tongji_custom.py` 带「**刷新后把新 token 写回自己源码**」的逻辑 —— 这正是碎片化元凶
- 记忆里记录的 2 个 refresh_token **全部 400 失效**；唯一存活的藏在脚本里、从未被记录
- 这些脚本若直接同步到 **public 仓库**（overseas-knowledge），等于公开泄露
  client_secret + refresh_token = 全站数据访问权

### 找回 / 救援手段
1. **扫 traces**（历史会话里留下的）：
   ```bash
   grep -rEo '12[0-9]\.[A-Za-z0-9_.\-]{40,}' ~/.workbuddy/traces/ | sort -u
   ```
   逐个试 `https://openapi.baidu.com/oauth/2.0/token?grant_type=refresh_token`
2. **重走 OAuth**（前两者都失败时）：百度统计后台 → 应用管理 → 重新授权
3. ⚠️ 刷新的副作用：会让旧 refresh_token 立即失效 → **必须先确认哪个是活的，再刷**

### 体检
```bash
python3 scripts/check_env.py          # 人类可读
python3 scripts/check_env.py --json   # 给自动化用，退出码 0=全绿
```
它同时是**入仓前的凭据泄露门禁**（扫描硬编码 token / client_secret，必须 0 命中）。
