---
name: regulation-effective-alert
description: "法规生效强提示 · 数据 schema 一处定义（法规预警字段 + 触发状态去重表）。订阅邮件/资讯采集/早报/微信卡片三链路 SKILL.md 只放指针引用本文件，禁止复制内容。"
agent_created: true
version: "1.0"
updated: "2026-09-22"
---

# 法规生效强提示 · 数据规范（一处定义）

> **铁律**：本文件是法规生效强提示的**唯一真相源**。三链路（humance-email-push / overseas-news-daily / 早报+卡片）的 SKILL.md 与 automation prompt **只引用本文件指针**，不得复制下方字段定义，否则必漂移。
> 指针写法：`数据规范见 yoyo-agent-swarm/references/regulation-effective-alert.md（v1.0）`

## 一、法规预警记录 schema（一条法规 = 一个预警单元）

数据源：飞书法规台账 `tblSyV7MnPyKB82m`（待确认 base，当前 user 授权缺失、bot 不可见）为人工维护台账；Strapi `humancehr.com/regulation` 为权威源（当前印度库为空，需补录）。两源字段须对齐本 schema。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `regulation_id` | Text | ✅ | 稳定主键，格式 `{ISO2}-{slug}-{生效日期}`，如 `IN-EPFO-2026-09-17` |
| `country` | Text | ✅ | ISO2 或中文国名 |
| `title` | Text | ✅ | 法规简称，如「EPF 工资缴纳上限 ₹15,000→₹25,000」 |
| `category` | SingleSelect | ✅ | 社保 / 税 / 最低工资 / 强制福利 / 工时 / 解雇 / 签证 / 申报备案 / 其他 |
| `change_summary` | Text | ✅ | 变更要点一句话 |
| `effective_date` | Date | ✅ | **生效日期**（窗口计算基准）；无此字段则预警永不触发 |
| `impact_level` | SingleSelect | ✅ | **P0 成本/强合规 / P1 申报义务 / P2 信息方向**（门控见下） |
| `impact_summary` | Text | ✅ | 对雇主的具体影响（成本/动作） |
| `cautions` | Text | ✅ | 注意事项（登记、系统调基、外籍适用例外等） |
| `official_source_url` | Url | ✅ | 官方来源链接（15:00 校验须可打开） |
| `source_verified` | Checkbox | ✅ | 事实已核实（PDF/官报） |
| `alert_state` | SingleSelect | ✅ | pending / active / done（触发状态，见第二节去重表） |

## 二、触发状态去重表 schema（跨渠道共享中枢）

目的：保证「同一法规 × 同一窗口状态」在邮件/早报/卡片三渠道**只触发一次**，杜绝重复轰炸。

- **去重键** = `regulation_id` × `window_state`
- `window_state` ∈ {`forecast_7d`(生效前7天), `d_1`(前1天), `effday`(当天), `post_30d`(后30天，仅生效次日发1次)}
- 每条状态记录字段：`triggered`(bool) / `triggered_at`(DateTime) / `channels`(数组，记录已触达渠道)

**落地实现（当前）**：本地 JSON 文件 `regulation_alert_state.json`（工作区 outputs/）作为轻量中枢；通道恢复后可同步飞书/Anchor DB。状态变更由"计算→消费"共享队列写入，三渠道读取同一份。

## 三、影响分级门控（用工雇主视角，避免噪音）

| 级别 | 涵盖 category | 强提示策略 |
|---|---|---|
| 🔴 P0 | 社保/税/最低工资/强制福利/工时/解雇/签证 | 全渠道（邮件+早报+卡片），全员可见 |
| 🟡 P1 | 申报备案/年报/数据报送 | 仅邮件(定向)+早报，不进群卡片 |
| ⚪ P2 | 政策吹风/非强制指引 | **不加强提示**，当普通资讯入库 |

## 四、首条示范记录（印度 EPFO，已核实，待录入飞书/Strapi）

```json
{
  "regulation_id": "IN-EPFO-2026-09-17",
  "country": "India",
  "title": "EPF 工资缴纳上限 ₹15,000→₹25,000/月",
  "category": "社保",
  "change_summary": "印度 EPFO 强制缴纳工资上限由 ₹15,000 上调至 ₹25,000/月（S.O. 5109(E)，取代 5/29 S.O. 2702(E)）",
  "effective_date": "2026-09-17",
  "impact_level": "P0",
  "impact_summary": "月薪 ₹15,001–25,000 员工强制纳入 EPFO；雇主+雇员各缴 12%，月缴 ₹1,800→₹3,000；CTC/Payroll/EPS/EDLI 联动重算",
  "cautions": "①已入职薪资跨阈值员工需重新登记 ②Payroll 系统调基 ③外籍雇员适用例外需单独判定 ④追溯生效无过渡期",
  "official_source_url": "Gazette of India S.O. 5109(E) dated 17.09.2026（用户提供官报公报 PDF）",
  "source_verified": true,
  "alert_state": "pending"
}
```

> ⚠️ 录入阻塞：飞书法规台账当前 user 授权缺失（keychain 无 token）、bot 不可见该表；Strapi 印度库为空。需先修复授权或确认法规表正确 base，再执行真实写入。
