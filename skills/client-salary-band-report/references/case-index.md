# 已交付案例索引（Case Index）

用途：新任务接单时先查这里——**同客户/同结构直接沿用既有链路，不要从零重写**。

> 工作区路径：`/Users/yoyo/WorkBuddy/2026-07-29-13-50-49/`（脚本与交付件都在这里）
> 归档日期：2026-09-21（新增科脉马来单国预算受限版）

---

## 一、现行主链路（推荐复用）

工具库统一来自 `scripts/salary_report_kit.py`；下列脚本是它的不同落地形态。

| 客户 | 岗位 | 覆盖范围 | 结构 | 生成脚本 | 交付件 |
|---|---|---|---|---|---|
| 控维通信 | 区域销售经理 RSM | 中东七国 | 多国分地区 | `cowave_v5_region.py` | 控维通信_区域销售经理_中东七国薪酬带宽报告_客户版.pdf |
| 控维通信 | 区域销售经理 RSM | 东南亚五国 | 多国分地区 | `cowave_v5_region.py` | 控维通信_区域销售经理_东南亚五国薪酬带宽报告_客户版.pdf |
| 二六三 | 大客户销售经理 KAM | 新加坡（辐射东南亚） | 单国单岗 | `kam263_sg_build.py` | 二六三_大客户销售经理新加坡薪酬带宽报告_客户版.pdf |
| 拓米洛 | 半导体大客户经理 KAM | 韩国 | 单国单岗 | `tuomiluo_kr_build.py` | 拓米洛_半导体大客户经理韩国薪酬带宽报告_客户版.pdf |
| 拓米洛 | 韩国销售总监 | 韩国 | 单国单岗 | `tuomiluo_kr_build.py` | 拓米洛_韩国销售总监薪酬带宽报告_客户版.pdf |
| 科脉股份 | 海外渠道经理 + 海外销售管理 | 东南亚六国 | **单区域双岗位** | `kemai_sea_dual.py` | 科脉股份_海外渠道经理与海外销售管理_东南亚六国薪酬带宽报告_客户版.pdf |
| 科脉股份 | 海外渠道经理 + 海外销售管理 | 马来西亚（单国·预算受限 6–7K base） | 单区域双岗位 + 薪酬结构/招聘设计 | `kemai_my_only.py` | 2026.09.21_科脉股份_海外渠道经理与海外销售管理_马来西亚薪酬带宽报告_客户版.pdf |

**依赖关系**（改工具函数只需动源头）：

```
cowave_v2_build.py   ← 工具层源头 + 控维数据层（混在一起，是历史包袱）
   ├── cowave_v3_build.py        控维 早期大纲版（产出已被 v5 取代）
   ├── cowave_v4_rsm_country.py  控维 单国版（同上）
   ├── cowave_v5_region.py       控维 现行：中东七国 / 东南亚五国
   └── tuomiluo_kr_build.py      拓米洛 韩国两份
kam263_sg_build.py   ← 独立副本（自带同名 T/KV/make_watermark，未 import v2）
kemai_sea_dual.py    ← 已剥离工具层的干净实现（单区域双岗位，import salary_report_kit）
kemai_my_only.py     ← 科脉马来单国版（6–7K 预算受限 + 第三章薪酬结构 / 第四章招聘设计）
```

⚠️ 这三个"客户脚本"的**数据与工具是混着的**——这正是新建报告容易走偏的地方。
新任务请直接用本 skill 的模板（`make_single_report.py` / `make_region_report.py` / `make_dual_job_report.py`），
它们已把工具层剥离干净，只留配置区与数据区需要填。

---

## 二、历史案例（已封堵入口，仅供追溯）

这些脚本的 `__main__` 已加**交付件保护门禁**（检测到既有产出会 `SystemExit`），
防止误运行覆盖已批准的交付件。要重产需临时放开——但**建议直接用新模板重做**。

| 客户 | 岗位 | 驻地 | 生成脚本 | 已知遗留问题 |
|---|---|---|---|---|
| Habas | 组长 | 土耳其 伊斯坦布尔 | `generate_pdf.py`、`generate_client_pdf.py` | 元数据标题为空；部分无页码 |
| SOLAMODA | 业务经理 | 英美 / 中国香港 / 三地 | `generate_solamoda_pdf.py`、`_hk_`、`_3region_` | **p5 有两个空框**（源脚本 `⛔️` 无字形） |
| 华伽 HUAGIA | TikTok 电商业务负责人 | 美国 | `generate_huajia_pdf.py` | **p3 有两个空框**（同上） |
| 科脉 | 海外实施交付工程师 | 马来西亚 吉隆坡 | `generate_kemai_pdf.py` | 元数据标题为空 |
| 艾微视图 | FAE 工程师 | 菲律宾 | `generate_aweiview_pdf.py` | 元数据标题为空 |
| 赛迪 CISDI | 三岗位 | 南非 / 博茨瓦纳 | `generate_cisdi_pdf.py` | 无页码 |
| 二六三 | — | 新加坡（早期版） | `generate_263_pdf.py` / `_v2` / `_v3` / `_final` | 已被 `kam263_sg_build.py` 取代 |

历史脚本共性欠账（**新报告不要重蹈**）：
1. 未设 PDF 元数据 `title` → 阅读器显示文件名
2. 正文/封面带「客户交付版」字样
3. 用 `⛔` 等 emoji（SimHei 无字形 → 渲染成空框）
4. 缺页码

---

## 三、新任务决策树

```
接到薪酬报告需求
├─ 只有一个驻地？ ────────→ make_single_report.py（单国单岗）
├─ 同一片市场要出**两个岗位**、合并成一份对比？
│  └────────────────────→ make_dual_job_report.py（单区域双岗位）
└─ 多个候选驻地？
   ├─ 需按地区拆成多份 ──→ make_region_report.py（多国分地区）
   └─ 只出一份横向比价 ──→ make_region_report.py，把 REGIONS 只留一个 key
                          （或 make_single_report.py + 自行扩展对比表）

同客户复购？
├─ 结构一致、只是换薪资数据 → 沿用原脚本（上表「生成脚本」列），只改数据区
└─ 结构要变 → 用模板重做，产出后跑 qc_client_pdf.py 验收
```

**任何情况下，交付前必跑**：

```bash
python ~/.workbuddy/skills/pdf-report-layout/scripts/qc_client_pdf.py \
  --color "#1f4f8f" --per-file "中东版.pdf=以色列,!印尼" *.pdf
# 退出码 0 才算通过
```
