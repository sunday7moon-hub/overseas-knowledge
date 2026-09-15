---
name: baidu-tongji-analytics
description: >
  humancehr.com 百度统计（Site 22551575）取数与口径规范。当用户需要拉取/核对站点流量数据、
  PV / UV / 访客人次 / DAU / WAU / MAU、来源与地域分布、TOP 页面、停留时长与跳出率、
  周报数据底座，或需要判断「某个流量数字该怎么口径化再对外汇报」时使用。
  也用于排查百度统计 API 报错（token 失效、返回 null、数据缺失）与凭据体检。
  触发词：百度统计、站点数据、流量数据、PV、UV、访客人次、DAU、WAU、MAU、跳出率、停留时长、
  来源分布、TOP 页面、周报取数、baidu tongji、humancehr 数据。
---

# 百度统计取数（humancehr.com）

站点 ID **22551575**。本技能是 Humance 一切流量口径与基准的真相源。

## ⛔ 三条硬约束

1. **绝不把凭据写进任何文件**。凭据只存 `~/.workbuddy/secrets/baidu_tongji.json`（600）。
   本技能会同步到 **public 仓库**，脚本里出现 token = 全站数据访问权公开泄露。
   同步前必跑 `python3 scripts/check_env.py` 门禁。
2. **对外汇报只能写「访客人次」，不能写「访客数 / 用户数」**（跨天不去重）。
3. **任何脚本改动后必须实跑取一次真实数据**再算完成（编译通过 ≠ 能跑）。

## 快速开始

```bash
cd ~/.workbuddy/skills/baidu-tongji-analytics/scripts

python3 check_env.py                  # ① 先体检：凭据是否可用 / 有无硬编码泄露
python3 baidu_dau.py 30               # ② DAU 均值 + 周末比 + 去重敏感性（最常用）
python3 baidu_wau.py 7                # ③ WAU（两种口径对比，防把人次当人数）
python3 baidu_window.py 20260907 20260913   # ④ 任意窗口全量数据（周报底座）
python3 baidu_tongji_custom.py 20260901 20260907  # ⑤ 指定周期结构化 JSON
```

> ⚠️ 脚本**不要**用 `python3` 以外的解释器假设；本机推荐 venv python：
> `/Users/yoyo/.workbuddy/binaries/python/versions/3.13.12/bin/python3`
> 全部脚本**纯标准库、零外部依赖**。

## 脚本矩阵

| 脚本 | 用途 | 用法 | 状态 |
|---|---|---|---|
| `_baidu_auth.py` | **统一凭据层**（唯一真相源） | 被 import，勿直接改 | ✅ 2026-09-15 重构 |
| `check_env.py` | 体检 + **入仓凭据门禁** | `[--json]` | ✅ |
| `baidu_dau.py` | DAU / 分段 / 周末比 / 去重敏感性 | `[days=30]` | ✅ 推荐首选 |
| `baidu_wau.py` | WAU（逐日人次 vs 区间去重 双口径对比） | `[days=7]` | ✅ |
| `baidu_window.py` | 任意日期窗口全量（趋势/新老/TOP页/来源） | `START END`（YYYYMMDD） | ✅ |
| `baidu_tongji_custom.py` | 指定周期结构化 JSON（7 类指标） | `START END` | ✅ |
| `baidu_monthly_2026.py` | 月度趋势 + 全周期质量（`gran=month` 最准） | 无参 | ✅ |
| `baidu_2026_extra.py` | 来源/TOP页/落地页/地域（全周期） | 无参 | ✅ |
| `baidu_week_article.py` | 文章 TOP 页 + 来源 + 新老访客快照 | 无参（内置窗口） | ⚠️ 窗口写死，改前先看源码 |
| `baidu_tongji_weekly.py` | **周一 07:00 自动化用**的周报脚本 | — | 🔴 **仍在旧位置**，见下 |

### 🔴 待办：weekly 脚本尚未迁入
`baidu_tongji_weekly.py` 有**活体自动化引用**（`humancehr 百度统计周报-周一7:00`，
absolute path 指向 `WorkBuddy/2026-06-29-16-08-00/baidu_tongji_weekly.py`），
且内部**仍硬编码着已失效的 refresh_token `122.586de153…`**，靠旧的备用 access_token 兜底
（该 token 约 **2026-09-19** 到期 → 到期后周报会失败）。

**迁移必须按四步纪律走，不能直接搬**：
1. 复制到本技能 `scripts/`
2. 改自动化 prompt 的绝对路径
3. 跑 `rule_ref_lint.py --scan` 验锚点
4. 删旧位置

> 直接搬 = 自动化静默失败（每周一跑不出报告，且不报错）。

## 口径铁律（摘要，全文见 `references/api-quirks.md`）

| # | 规则 | 后果 |
|---|---|---|
| 1 | `visitor_count` 跨天**不去重** = 逐日人次相加 | 对外必须写「**访客人次**」 |
| 2 | **DAU 精确**，WAU/MAU **只能估算** | 估算式：新访客 + 老访客人次÷平均到访天数 |
| 3 | `gran=day` **只返回最近 20 行**（静默丢弃） | >20 天必须分段合并 |
| 4 | 停留时长字段是 **`avg_visit_time`** | 写 `avg_time` 会被静默忽略 |
| 5 | 响应是 **`d["result"]`**，不是 `d["data"]["result"]` | 写错得到 `None` 且不报错 → 易误判「token 失效」 |
| 6 | `openapi.baidu.com` **必须绕过代理** | `_baidu_auth` 已内置，别自己写请求 |
| 7 | **周末÷工作日 ≈ 0.54** 才是真人流量 | 爬虫 ≈0.89（不过周末），每周报验一次 |

## 基准数据

月度 / 周 / 30 天 / 活跃度全部基准见 **`references/baselines.md`**。
最常用的三个：

- **DAU 均值 263**（工作日 299 / 周末 162）
- **MAU 7,830**（漏斗转化率分母统一用它）｜ WAU ≈ 1,810
- **粘性 DAU/MAU = 3.4%**（健康线 20%）→ 本站是「一次性流量」，**留存优先于拉新**

## 凭据管理

```
~/.workbuddy/secrets/baidu_tongji.json   (600)
  site_id / client_id / client_secret / refresh_token / access_token
```

- 所有脚本经 `_baidu_auth.get_access_token()` 取 token：
  `env BAIDU_TONGJI_TOKEN` → secrets 内 access_token（先探测） → 失效则用 refresh_token 刷新
- **refresh_token 每次刷新即轮换** → 刷新后自动回写 secrets（带文件锁防并发覆盖）
- 凭据全部失效时的救援路径见 `references/api-quirks.md` §三

## 已知教训（别重复踩）

1. **token 不能硬编码进脚本**（2026-09-15 重构前，8 个脚本 4 组 token 互不知情；
   记忆里记的 2 个全失效，唯一活着的反而没被记录 → 记忆会腐烂，真相源要放对地方）
2. **脚本不能自我改写源码来存 token**（曾是碎片化元凶；且会污染公开仓）
3. **代理必须绕**（否则静默返回空，不报错）
4. **`result` 为 null ≠ token 失效**，先检查是不是 URL 参数/解析写错
5. 迁移脚本**不能只搬文件**：有自动化引用的必须先改 prompt 再删旧文件
