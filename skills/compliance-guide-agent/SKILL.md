---
name: compliance-guide-agent
display_name: 合规指南编排 Agent
displayName: 合规指南编排 Agent
slug: compliance-guide-agent
version: "1.0.0"
summary: 顶层编排 Agent 工作流——复用模板，自主创作、校验、复用多国雇佣合规指南 PPTX
description: 一个可独立运行的「合规指南生产」Agent 工作流。给定目标国 + 底版模板，自动完成：① 复用模板结构（dump 形状/表格行列）② 创作（WebSearch 调研 2026 数据→填 SPEC→调 compliance-guide-pptx 克隆生成 PPTX）③ 校验（qc_verify.py 机械闸 + 复用 yoyo-qc-auditor 三层方法论）④ 复用循环（P0/P1 未过则修复重跑，最多 2 次）。yoyo-qc-auditor 保持纯校验身份，作为质量闸被本工作流复用，不被改写。触发词：做一个XX国合规指南、批量产出合规指南、合规指南agent工作流、按模板生成多国指南。
tags: [PPT, 合规指南, 出海HR, agent-workflow, 编排, python-pptx]
license: MIT
agent_created: true
---

# 合规指南编排 Agent（Compliance Guide Agent Workflow）

一个**可独立创作、校验、复用**的顶层 Agent 工作流。它把已验证的「模板克隆 + QC 校验」固化成一条无人值守也能跑通的流水线。

## 角色定位

```
            ┌─────────────────────────────────────────────┐
            │        compliance-guide-agent（本工作流）      │
            │   复用 → 创作 → 校验 → 循环复用                 │
            └─────────────────────────────────────────────┘
               │                │                  │
        ① 复用模板        ② 创作（调用）      ③ 校验（复用）
   clone_pptx --dump   compliance-guide-pptx   yoyo-qc-auditor
        + qc_verify               ↑                     ↑
        （结构提取）        （版式克隆引擎）        （三层方法论 / 质量闸）
```

- **创作引擎**：`compliance-guide-pptx`（版式克隆 + 内容替换，不改动）
- **质量闸**：`yoyo-qc-auditor`（三层校验方法论 + 飞书台账 + 通知，不改动，纯复用）
- **机械闸**：本技能 `scripts/qc_verify.py`（循环判断用，自动跑）

## 何时用

- 用户说「做一个 XX 国的雇佣合规指南」「按这个模板出多国版本」「批量产出合规指南」
- 强调统一模板、1:1 版式对齐、数据需标注来源
- 任何「克隆 + 校验」类内容生产都可套用此工作流骨架

## 工作流（4 阶段 + 循环闸）

### 阶段 1 · 复用（Reuse）
- 确认底版模板路径（只读参考，不改动）与目标国、年份。
- 提取结构：
  ```bash
  /Users/yoyo/.workbuddy/binaries/python/envs/default/bin/python \
    ~/.workbuddy/skills/compliance-guide-pptx/scripts/clone_pptx.py \
    --dump --src 模板.pptx
  ```
- 记录每页表格的**行数/列数**与目标国**残留词**（即模板国的专有名词，详见 `references/austria_leak_keywords.txt`；换底版时另建一份）。
- 确定输出路径，命名 `XX_雇佣合规指南_2026.pptx`。

### 阶段 2 · 创作（Create）
1. **调研**：用 WebSearch 逐项核实目标国 2026 关键合规数据，记录来源（政府令/税务机关/社保机构/律所年度更新/PwC）。核验清单见 `references/data_checklist.md`。权威源冲突时取保守可辩护口径并标注「以官方为准」。
2. **填 SPEC**：复制 `compliance-guide-pptx/scripts/clone_pptx.py` 的 SPEC 模式，新建 `build_<国>.py`：形状名**完全匹配** `--dump` 结果（含空格）；表格行数**必须等于模板**；文本用 `\n` 换行。
3. **生成**：
   ```bash
   /Users/yoyo/.workbuddy/binaries/python/envs/default/bin/python build_<国>.py
   ```
   该脚本内部调 `clone_pptx.py` 的 `build()` + `verify()`，产出 PPTX 并打印 `ROW/COL MISMATCH` / `LEAKS`。

### 阶段 3 · 校验（Verify）
4. **机械闸**（自动，决定循环）：
   ```bash
   /Users/yoyo/.workbuddy/binaries/python/envs/default/bin/python \
     ~/.workbuddy/skills/compliance-guide-agent/scripts/qc_verify.py \
     --out 生成.pptx --template 模板.pptx \
     --leak-file ~/.workbuddy/skills/compliance-guide-agent/references/austria_leak_keywords.txt \
     --country 瑞典 --md /tmp/qc_<国>.md --json /tmp/qc_<国>.json
   ```
   - `exit 0` = 通过（可交付）；`exit 1` = 未通过（进入循环）。
   - 检查项：版式 1:1（行/列/页数）、模板国残留、空单元格、占位符、封面国名对齐。
5. **三层方法论复核**（复用 yoyo-qc-auditor 判定）：
   - L1 目标：目标国/年份/模板是否明确，是否对外发布。
   - L2 过程：调研是否真做了（看来源链接），有无静默失败，关键数据是否都有权威源。
   - L3 结果：版式 1:1 已自动化；再抽查 ≥3 个关键数字（工资阈值/费率/生效日）与来源一致。
   - 评分沿用 yoyo-qc-auditor：`起始100，P0-30 / P1-15 / P2-5`；≥90 放行、70–89 有条件放行、50–69 返工、<50 阻断。
   - **P0/P1 必须登记飞书 QC 台账并通知 Yoyo**（调 yoyo-qc-auditor 的 `feishu_log.py` / `notify_yoyo.py`）。

### 阶段 4 · 循环复用（Loop）
- 若阶段 3 机械闸 `exit 1` 或人工判定返工：定位问题（SPEC 行数错 / 数据错 / 残留）→ 修复 `build_<国>.py` → 重跑生成 → 重跑 `qc_verify.py`。
- 最多循环 **2 次**；仍不过则上报 Yoyo，不强行交付。
- 通过后：交付文件 + 输出 QC 报告摘要。新增国家即重复本工作流，模板与 QC 脚本**完全复用**。

## 复用性说明

- **换国**：只需阶段 1–2 的输入（国名 + 调研 + SPEC），阶段 3–4 的模板/脚本零改动。
- **换底版**：更新 `references/` 下对应残留词文件，重新 `--dump` 取形状名即可。
- **通用化**：本「复用→创作→校验→循环」骨架可套用到任何「克隆 + QC」类内容生产（合同模板、报告模板等），只需替换创作引擎与残留词。

## 边界

- 产出是合规辅助 / 对外物料草稿，**不替代当地律师个案结论**。
- 数据无法当日核验时明确标注「待官方确认」，不用看似精确的内容替代未知事实。
- 不改动输入模板；yoyo-qc-auditor 与 compliance-guide-pptx 两个被复用技能**保持原样**，本工作流只调用、不修改。
