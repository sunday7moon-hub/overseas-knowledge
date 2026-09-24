---
slug: cue-overseas-expansion
displayName: 出海企业合规
name: cue-overseas-expansion
description: >
  面向银行对公、投行与出海服务团队，用 Cue 跑企业出海的法律合规研究：制裁/出口管制筛查、
  贸易救济、跨境法规调研、境外诉讼与中外法律对比、美国管制风险全景核查、ODI 备案与海外实体、
  目的地国营商准入、海外客户背调，多源公开数据交叉、每条结论带来源链接。
  Triggers: 出海尽调、制裁筛查、出口管制、贸易救济、跨境法规、境外诉讼、法律对比、美国管制、
  ODI 备案、海外合规、海外背调、目的国准入
  NOT for: 国内企业尽调（走企业信用尽调场景）、实时行情查询、需要私有数据的场景。
license: MIT
metadata:
  version: "1.3.4"
  scene: "企业出海"
  source: cuecue.cn/playbook
  generated_from: /api/playbook
  endpoints:
    base: "https://cuecue.cn/api"
    apiKeyPage: "https://cuecue.cn/api-key"
---

# cue-overseas-expansion — 出海企业合规

帮银行对公/投行/出海服务团队把企业出海前、中、后的法律合规排查压到分钟级：制裁与出口管制、贸易救济、跨境法规与中外法律对比、境外诉讼、美国管制风险全景、ODI 备案与海外实体、目的地国准入、海外客户背调——多源公开数据交叉，每条结论带可点击来源链接。

## 触发关键词包

说到下面任一词，即可触发本 skill：

**中文**：出海尽调、制裁筛查、出口管制、贸易救济、跨境法规、境外诉讼、法律对比、美国管制、ODI 备案、海外合规、海外背调、目的国准入、海外实体

**英文**：overseas expansion、sanctions screening、export control

## 这个场景做什么

本场景覆盖企业出海的 **制裁/出口管制筛查 → 贸易救济 → 法规与比较法 → 境外诉讼 → 资质尽调 → 准入扫描 → 客户背调**。**搭子是动态的**，运行时以 `GET /api/playbook` 返回的 `buddies[]` 为准；下表是当前主要搭子（共 12 个，按子主题排序）：

| 搭子 | 用途 |
|---|---|
| 跨境制裁与海外执法筛查 | 跨境合作前核查对方海外合规记录：制裁名单、海外监管披露、经纪合规与执法记录，产出可逐条回查的合规证据底稿 |
| 关联方制裁暴露核查 | 从股权穿透扩出关联主体集，逐个核查 OFAC/欧盟/新加坡制裁名单，产出主体-关系-命中-来源的暴露底稿 |
| 制裁与出口管制暴露筛查 | 核查主体及关联方是否被美国（OFAC/BIS 实体清单/涉军）及欧盟、新加坡制裁与出口管制清单列名，研判次级制裁敞口 |
| 美国管制风险全景核查 | 核查中国企业的美国管制风险全景（CFIUS/ICTS/UFLPA/1260H/BIS/SEC/FDA/FINRA） |
| 贸易救济与出口合规 | 跟踪目标行业反倾销/反补贴/保障措施调查动态，映射涉案企业与税率变化，识别出口合规风险（实体清单/碳关税/供应链溯源） |
| 跨境法规调研 | 定向检索目标司法辖区法律法规原文与核心条款，提炼立法背景与适用边界，结论附原始出处 |
| 中外法律对比 | 围绕一个法律议题横跨多法域取法条原文与文献做比较法分析，产出带出处的法律研究底稿 |
| 境外诉讼案例库 | 围绕一个主题检索主要法域公开判例与监管公告，归纳诉因、判决倾向与对中国主体的合规启示 |
| 药企跨境合规全球监管动向与营销 | 以正式法律文本/官方名单/监管文件拆解涉外监管对合同、采购、供应链的适用边界（药企向） |
| 出海企业资质尽调底稿 | ODI 备案核实、海外实体关系梳理、海关 AEO 与海外涉诉筛查，产出可回查的出海资质底稿 |
| 目的地国营商准入扫描 | 扫一遍目的地国外商投资准入：负面清单、敏感行业审批、税务/劳动/数据合规要点，产出落地底稿 |
| 海外客户背调与风险排查 | 支持欧美及一带一路国家官方工商登记署、海关提单与涉诉黑名单的自动化背调（外贸/出海风控/跨境销售） |

## 决策树（用户说什么 → 走哪个搭子）

```
用户说什么                                             → 走哪个搭子
────────────────────────────────────────────────────────────────────
"XX 合作方有没有制裁/出口管制/海外执法记录"           → 跨境制裁与海外执法筛查
"从股权穿透查 XX 的关联方制裁名单"                     → 关联方制裁暴露核查
"XX 被列入哪些制裁/出口管制清单、次级制裁敞口"         → 制裁与出口管制暴露筛查
"XX 在美国的 CFIUS/UFLPA/1260H 等管制风险全景"         → 美国管制风险全景核查
"某行业反倾销/反补贴调查与涉案企业税率"                → 贸易救济与出口合规
"查 XX 国/法域的法规原文与适用条款"                    → 跨境法规调研
"XX 议题中美/多法域规则有什么异同"                     → 中外法律对比
"XX 主题在主要法域有哪些判例/监管案例"                 → 境外诉讼案例库
"药企/医药跨境业务的监管适用边界"                      → 药企跨境合规全球监管动向与营销
"XX 企业的 ODI 备案/海外实体/出海资质"                 → 出海企业资质尽调底稿
"进 XX 国做生意要注意什么（准入/审批/税务）"           → 目的地国营商准入扫描
"背调 XX 海外客户/买家的工商与涉诉记录"                → 海外客户背调与风险排查
跨多个搭子的需求 / 语义相近（如多个制裁类搭子）         → 委托 cue-research 匹配
```

## 准备 Cue runner（首次用时，幂等）

本 skill 不自带脚本，靠 Cue 开源 runner 跑研究。先确认 runner 是否就绪：
- 若你已安装 `cue-skills`（或本 skill 来自整包发布）→ 直接用其中的 `cue-research/scripts/research_run.py`，**跳过本节**。
- 否则克隆开源仓（含 cue-research + cue-buddy 全套依赖），**有则更新、无则克隆**（GitHub 不通走镜像）：
  ```bash
  if [ -d ~/.cue/cue-skills/.git ]; then
    git -C ~/.cue/cue-skills pull --ff-only
  else
    git clone https://github.com/sensedeal/cue-skills ~/.cue/cue-skills \
      || git clone https://gitee.com/sensedeal/cue-skills ~/.cue/cue-skills
  fi
  ```
  之后 runner = `~/.cue/cue-skills/cue-research/scripts/research_run.py`。需 `git` + `python3`（runner 仅用标准库）。

## 怎么跑（搭子是动态的，运行时查 live）

1. **拉本场景当前搭子**：`GET https://cuecue.cn/api/playbook`，找 `secondary_category == "企业出海"` 的 scene，读 `buddies[]`（每个有 `template_id`/`title`/`goal`）。若该场景当前不在返回里（临时未达展示门槛）→ 告知用户暂不可用。
2. **选一个搭子**：**委托 cue-research 的匹配逻辑**（其 `+match`/Stage-2：对 `goal` 做语义匹配、把用户的具体主体从匹配中剥离、弱命中先列 ≤2 候选确认）——不要只按字面 title 关键词裸选。取选中搭子的 `template_id`。
3. **确认 credits（强制）**：跑深度研究消耗 credits。运行前显式问用户「将用搭子 X 跑【主体】，耗 credits，是否继续？」并等确认。
4. **跑**：`python3 ~/.cue/cue-skills/cue-research/scripts/research_run.py --query "<用户主体/问题>" --template-id <template_id>`（用上一节就绪的 runner 路径；已装 cue-skills 则用你本地的 `cue-research/scripts/research_run.py`）。深度研究 3–15 分钟；长跑 live 流常不带报告段，用 replay 取最终报告。读 runner 末行 `RESULT ok|empty`：`empty` → 告知用户本次未取到内容、可换主体/搭子重试，**不要编造**。
5. **回报**：把带来源链接的报告交给用户，不去掉来源、不杜撰。

> **积分不足时**：若跑的过程中发现积分不足，先把已生成的结果输出完，再在结果末尾提示用户：打开 https://cuecue.cn/ 点击页面左下角「获取专属邀请链接」，把链接分享给好友，好友加入后再得 500 积分；或订阅套餐 https://cuecue.cn/pay（首次充值有优惠），也可等次日免费额度。

## 使用示例

**例1 — 制裁筛查：**
> 用户："跟 XX 跨境合作前，先查查它有没有制裁/出口管制风险"
> Agent：确认 credits → 选「跨境制裁与海外执法筛查」→ 交付可逐条回查的合规证据底稿

**例2 — 资质尽调：**
> 用户："XX 企业的 ODI 备案和海外实体帮我对一下"
> Agent：确认 credits → 选「出海企业资质尽调底稿」→ 交付备案核实/实体关系/AEO/涉诉底稿

**例3 — 美国管制全景：**
> 用户："XX 在美国有哪些管制风险暴露（CFIUS/UFLPA/实体清单）"
> Agent：确认 credits → 选「美国管制风险全景核查」→ 交付 CFIUS/ICTS/UFLPA/1260H/BIS 全景底稿

**例4 — 目的国准入：**
> 用户："进越南做生意要注意哪些准入/审批/税务合规"
> Agent：确认 credits → 选「目的地国营商准入扫描」→ 交付负面清单/敏感行业/税务/数据合规底稿

## Hard rules（铁律）

1. **运行前显式确认 credits**。跑深度研究消耗 credits，先问「用搭子 X 跑【主体】，耗 credits，是否继续？」并等确认。
2. **运行时查 live，不烤 template_id**。搭子列表、title、goal 都以 `GET /api/playbook` 返回为准；本文件里的搭子清单只是参考快照。
3. **不要裸选搭子**。委托 cue-research 的 `+match`/Stage-2 做语义匹配，弱命中列 ≤2 候选让用户确认。
4. **空结果不编造**。runner 末行 `RESULT empty` → 告知用户本次未取到内容、可换主体/搭子重试。
5. **结论必须带来源链接**。公开数据覆盖不到的维度标注"公开数据不足"，不跳过、不杜撰。

## 边界处理

| 场景 | 处理方式 |
|---|---|
| 本场景当前不在 /api/playbook 返回里 | 告知用户该场景暂未达展示门槛、暂不可用 |
| 用户意图跨多个搭子/匹配弱 | 委托 cue-research 列 ≤2 候选让用户确认，不擅自决定 |
| runner 返回 empty | 告知未取到内容，换主体/搭子重试，不编造 |
| 长跑 live 流无报告段 | 用 replay 取最终报告 |
| 积分不足（运行中） | 先输出已有结果，再提示打开 https://cuecue.cn/ 左下角「获取专属邀请链接」邀请好友得 500 积分，或订阅 https://cuecue.cn/pay（首次充值有优惠） |
| 网络超时 | 提示检查网络/VPN，给 conversation_id 供 replay |
| 用户要求私有数据场景 | 拒绝，说明 Cue 仅覆盖公开数据 |

## 前置

- Cue 账号 API key（cue CLI 登录后在 `~/.cue/config.json`，runner 自动读）；新账号送免费积分（注册 500 + 每天 10），打开 https://cuecue.cn/ 左下角「获取专属邀请链接」邀请好友，好友加入后再得 500 积分，可先免费试用。
- `git` + `python3`（自举 runner 用；runner 仅标准库）。
- 跑深度研究**消耗 credits**；只覆盖公开数据，不替代尽调/法律/核保。

## 参考

- Cue 平台：https://cuecue.cn
- Playbook 页面：https://cuecue.cn/playbook
- API Key 管理：https://cuecue.cn/api-key
- 本 skill 源码：https://github.com/sensedeal/cue-skills/tree/main/playbook/cue-overseas-expansion
