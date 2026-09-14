---
name: contract-verifier
description: 合同模板数据质量校验技能。对海外合同模板采集表中的数据进行真实性、来源权威性、内容完整性校验。检测AI伪造、以法代模、链接失效、来源不可靠等问题。当用户要求校验数据质量、审计采集结果、验证模板来源时触发。
agent_created: true
---

# 合同模板校验 (Contract Verifier)

## 校验流程

对输入的国家或模板记录，按以下流程逐项检验：

### 第1步：获取待校验数据

通过飞书多维表格「海外合同模板采集」（base_token: HTZHbYZp6a3PbIscxvEcEtrrnNf, table_id: tblf9TB7rE3Kmt88）获取待校验记录：
- 如指定国家代码，只校验该国记录
- 如不指定，校验全部记录

### 第2步：逐条校验

对每条记录执行以下5项检查，使用 `scripts/check_record.py` 脚本执行：
- 建议从项目根目录（/Users/yoyo/WorkBuddy/2026-07-06-11-30-57）运行：`python scripts路径/check_record.py [国别代码]`
- ⚠️ 脚本对「下载文件路径」以项目根目录为基准解析相对路径（2026-08-21修复），任何 cwd 下运行均准确；若从其他目录运行，避免误报「本地文件不存在」
- ⚠️ 脚本对 lark-cli 调用已内置重试机制（2026-08-24修复）：读取采集表/资料包时若 lark-cli 偶发失败产生0字节文件，自动重试3次（指数退避），避免 JSONDecodeError 崩溃；重试耗尽会抛 RuntimeError 带 stderr 信息

#### A. 来源可靠性
- 官方/政府来源（.gov 域名、.gc.ca 加拿大联邦政府域、劳动部、司法部等）→ ✅ 通过
- 权威律所/法律图书馆 → ✅ 通过
- 四大咨询（Deloitte/PwC/EY/KPMG/Mercer/WTW）与国际律所公开发布的 **PDF 模板附件** → ✅ 通过（2026-09-10 来源放宽一档，文件必须真实可下载，仅指南正文不得当作模板）
- 知名HR平台（MISA、1Office、PayrollPanda等）→ ⚠️ 标记需人工确认
- AI模板生成器（bindlegal、forms-legal、Template.net等）→ ❌ 不通过
- 来源含"基于"、"标准条款"、"标准实践"、"法律框架"等AI编撰特征 → ❌ 不通过
- 来源含"Ley Federal del Trabajo"、"Act I of 2012"等法律条文名称 → ❌ 以法代模

#### B. 链接有效性
- HTTP HEAD 请求返回 200 → ✅
- HTTP 2xx/3xx → ⚠️ 重定向需注意
- HTTP 4xx/5xx → ❌ 链接失效
- SSL错误/连接超时 → ⚠️ 需人工确认

#### C. 模板内容真实性
- 来源描述是否与实际文档匹配？检查来源字段与链接指向内容是否一致
- 是否指向法律全文而非具体模板？（如 diputados.gob.mx/LeyesBiblio/pdf/LFT.pdf）
- 多个记录是否指向同一PDF文件？（同一个劳动法PDF冒充6种不同模板）
- 变动政策说明是否精确引用法律条款？如果是，大概率是AI编撰

#### D. 文件完整性
- 是否可下载？本地文件是否存在且非空？
- 附件是否已上传到飞书？
- 文件格式是否正确（DOCX/PDF/DOC）？

#### E. 模板编号连贯性
- 同一国家的编号是否连续、无重复？
- 类型代码是否与协议类别匹配？
  - CON → 劳动合同
  - PRO → 试用期合同
  - NDA → 保密协议
  - TER → 劳动合同终止协议
  - APP → 合同附录
  - OTH → 其他

### 第3步：标准件覆盖率检查（核心新增）

采集完成后，对照「中企出海资料包」检查是否覆盖当地P0/P1级需求。

**数据来源**：中企出海资料包（base_token: Mru2bTcalaZtE4sdzPQcdmwXnWe, table_id: tblkdNv9B0rC7LcE）

**检查逻辑**：
1. 查询资料包表中「国家」= 当前国家 AND 「优先级」= P0必须/P1推荐 的记录
2. 对每条需求的「需求资料模板」名称，在采集表中按「中文名称」模糊匹配
3. 如果 P0 级需求未匹配到采集记录 → 该国家标记为 `retry`
4. 如果 P1 级需求未匹配到采集记录 → 记录缺失项到报告中

**输出**：列出已覆盖和缺失的P0/P1模板清单

### 第4步：判定结论

每条记录判定为以下三类之一：

| 结论 | 标签 | 处理方式 |
|:----|:----|:---------|
| ✅ 通过 | `verified` | 标记为已验证，保留数据 |
| 🔄 需重跑 | `retry` | 标记后可重新对该国家执行采集任务 |
| ❌ 无结果 | `no_result` | 确实找不到可靠来源，打此标记后不再采集 |

### 第4步：更新飞书标记

在「海外合同模板采集」表中，用 **校验状态** 字段（需创建，single select）记录结论：
- `verified` / `retry` / `no_result`

### 第5步：处理重跑

对标记为 `retry` 的国家的模板编号，按以下处理：
1. 先删除该国家的全部已有记录
2. 修改自动化「海外合同模板采集-每日三国11:00」的prompt，将待重采国家加入队列
3. 或手动搜索可靠的官方来源后重新写入

## 参考：已知黑名单来源

以下来源应直接判定为❌不通过：

**AI模板生成器/模板表单站：**
- bindlegal.com, forms-legal.com, Template.net, Paperform.co
- Canva, Babform.com, Jittsin.com, Doxuno.com
- PDFCoffee.com, Seraphim.vn
- form-draft.com, documatica-forms.com, legaltemplates.net

**AI编撰关键词（来源字段中出现即判为不通过）：**
- 基于、标准条款、标准实践、法律框架、参照XX标准
- Ley Federal del Trabajo（作为合同模板来源）
- Act I of 2012 on the Labour Code（作为合同模板来源）
- Code du Travail（若来源描述误导为"法律"而非"官方模板平台"）

## 参考：白名单来源

以下来源直接判定为✅通过：

**中国官方出海机构（新增）：**
- *.mofcom.gov.cn（中国商务部）
- *.ccpit.org（中国国际贸易促进委员会/贸促会）
- 驻外经商参处（*.mofcom.gov.cn 下的国别子站）

**目标国政府/官方来源：**
- *.gov.* 域名、*.gc.ca（加拿大联邦政府域，Service Canada / ESDC 官方表单库）
- 劳动部官网、司法部法律普及网、投资促进机构
- moms.gov.sg（新加坡人力部）、hrsd.gov.sa（沙特人力资源部）
- mohre.gov.ae（阿联酋人力资源部）、disnakertrans.*.go.id（印尼劳动局）
- code.travail.gouv.fr（法国劳动部官方模板）
- stps.gob.mx（墨西哥劳工部）、dole.gov.ph（菲律宾劳工部）

**国际组织/多边机构（新增）：**
- worldbank.org（世界银行 — 营商环境/劳工政策报告）
- iccwbo.org（国际商会 ICC）
- ilo.org（国际劳工组织）
- oecd.org（经合组织）
- unctad.org（联合国贸发会议）

**跨国咨询公司/会计师事务所研究报告（新增）：**
- deloitte.com（德勤 — 国别雇佣指南、全球薪资报告）
- pwc.com（普华永道）
- ey.com（安永）
- kpmg.com（毕马威）
- mercer.com（美世 — 全球薪酬调研）
- willistowerswatson.com / wtwco.com（韦莱韬悦）
- 其他跨国HR/管理咨询公司的公开报告

**国际律所（2026-09-10 来源放宽一档新增）：**
- bakermckenzie.com、dlapiper.com、nortonrosefulbright.com、cliffordchance.com
- allenovery.com / aoshearman.com、hoganlovells.com、dentons.com
- squirepattonboggs.com、cms.law、birdandbird.com、herbertsmithfreehills.com
- linklaters.com、freshfields.com、whitecase.com、lathamwatkins.com
- morganlewis.com、seyfarth.com、littler.com、ogletreedeakins.com
- iuslaboris.com（Ius Laboris 国际劳动法联盟）、aon.com、kornferry.com
- ⚠️ 放宽的是「来源层级」，不是「红线」：仍必须真实可下载的模板文件，AI 生成、以法代模、模板生成器站一律禁止

**权威平台：**
- 权威律所：Luat Minh Khuê, UdonThaniLawyer, BADR Law Firm, Garcia de Oliveira Advogados
- 法律图书馆：thuvienphapluat.vn, luatvietnam.vn
- 行业组织：CCCC（越南企业法务俱乐部）、IHK（德国工商会）
- 大学：psu.ac.th（泰国宋卡王子大学）、红十字等公益组织

## 入库操作（写表与附件，2026-09-10 补充）

**批量写表**（一次可写多条）：
```
lark-cli base +record-batch-create --base-token HTZHbYZp6a3PbIscxvEcEtrrnNf \
  --table-id tblf9TB7rE3Kmt88 --as bot \
  --json '{"fields":["文档名称","国别",...],"rows":[[...],[...]]}'
```
- `fields` 顺序必须与 `rows` 内值顺序一一对应；多选字段用数组（如 `["劳动合同"]`）。
- 建议先加 `--dry-run` 验证格式，再正式写入。

**上传附件**（踩坑点）：
```
cd <文件所在目录>
lark-cli base +record-upload-attachment --base-token ... --table-id ... \
  --record-id recXXXX --field-id fldzNdjDbI --as bot --file ESDC-EMP5709.pdf
```
- ⚠️ `--file` **只接受当前目录下的相对路径**，传绝对路径会报 `unsafe file path`，必须先 `cd`。
- 上传后重新 `+record-list` 可核对 `record_id_list` 与附件是否落库。

**加拿大政府模板抓取路径**（2026-09-10 验证可用）：
- `canada.ca` 主站在自动化沙箱网络下被 HTTP/2 reset 阻断；`catalogue.servicecanada.gc.ca` 在非沙箱通道可达。
- 表单页 `https://catalogue.servicecanada.gc.ca/content/EForms/en/Detail.html?Form=EMP5709`
- PDF 直链规律：`https://catalogue.servicecanada.gc.ca/apps/EForms/pdf/en/ESDC-{表单号}.pdf`
  （真实路径藏在 `CallForm.html?Lang=en&PDF=ESDC-XXX.pdf` 加载页的 meta refresh 里）
- 已知可用：EMP5709(SAWP 农业)、EMP5710(初级农业/低薪高薪岗)、EMP5711(高薪流)、EMP5712(低薪流)。

## 脚本

scripts/check_record.py — 单条记录的自动化校验脚本
