# -*- coding: utf-8 -*-
"""
国别指南双源分发 · 批量生成器（公众号 + 知乎 + 纯文本文稿 三件套）
模板与定稿一致：速览卡 + 成本情景 + EOR 决策 + 避坑清单 + 行业差异 + 数据来源 + 标准化回链卡。
回链主域：humancehr.com ｜ 署名：用友薪福社 · 慧思 Humance ｜ 品牌色：#1f4f8f
⚠️ 数据口径：本脚本内的国家数据为通用合规知识整理的「示意」值，仅供结构示范。
   对外发布前必须以 humancehr.com 官网权威源最新版 + 持牌顾问意见校准具体数值。

用法：
  1. 复制本文件到你的产出目录。
  2. 在 C 字典里新增/修改国家（参考 vietnam 这一条的结构）。
  3. 运行：python3 generate_country_dual.py  → 每国生成 <国>_公众号.html / _知乎.html / _文稿.md
"""
import os

OUT = os.path.dirname(os.path.abspath(__file__))

# ============ 公共 CSS ============
GZ_CSS = """
  :root{--primary:#1f4f8f;--primary-d:#16386a;--primary-l:#eef3fa;--ink:#1f2937;--ink-2:#374151;--muted:#6b7280;--line:#e5e7eb;--bg:#ffffff}
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif;background:#f3f4f6;color:var(--ink);line-height:1.85;font-size:16px;-webkit-font-smoothing:antialiased;padding:28px 0}
  .page{max-width:680px;margin:0 auto;background:var(--bg);border-radius:14px;box-shadow:0 6px 28px rgba(31,79,143,.08);overflow:hidden}
  .cover{background:linear-gradient(135deg,#1f4f8f 0%,#2b6cb0 100%);color:#fff;padding:40px 34px 32px}
  .cover .kicker{display:inline-block;font-size:12.5px;letter-spacing:2px;background:rgba(255,255,255,.16);border:1px solid rgba(255,255,255,.3);padding:4px 12px;border-radius:20px;margin-bottom:16px}
  .cover h1{font-size:25px;font-weight:800;line-height:1.45;letter-spacing:.5px}
  .cover .meta{margin-top:16px;font-size:13px;color:#cfe0f5;line-height:1.9}
  .cover .meta b{color:#fff}
  .body{padding:30px 34px 8px}
  .lead{background:var(--primary-l);border-left:4px solid var(--primary);border-radius:8px;padding:14px 18px;margin-bottom:22px;color:var(--ink-2);font-size:15px}
  h2{font-size:19px;font-weight:800;color:var(--primary-d);margin:30px 0 12px;padding-left:12px;border-left:5px solid var(--primary);line-height:1.4}
  p{margin:12px 0;color:var(--ink-2);font-size:15.5px}
  .num{color:var(--primary);font-weight:800}
  .callout{background:#f8fafc;border:1px solid var(--line);border-radius:10px;padding:14px 18px;margin:16px 0;font-size:14.5px;color:var(--ink-2)}
  .callout b{color:var(--primary-d)}
  .snapshot{background:linear-gradient(135deg,#f6f9fe,#eef3fa);border:1px solid #d6e2f3;border-radius:12px;padding:16px 18px;margin:18px 0}
  .snapshot .st{font-size:13px;font-weight:800;color:var(--primary-d);margin-bottom:10px;letter-spacing:.5px}
  .snapshot .grid{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}
  .snapshot .cell{background:#fff;border:1px solid var(--line);border-radius:8px;padding:10px 12px}
  .snapshot .cell .k{font-size:11.5px;color:var(--muted)}
  .snapshot .cell .v{font-size:15px;font-weight:800;color:var(--primary);margin-top:3px}
  .checklist{background:#fff;border:1px solid var(--line);border-radius:10px;padding:6px 18px;margin:16px 0}
  .checklist li{list-style:none;padding:9px 0 9px 26px;position:relative;font-size:14.5px;color:var(--ink-2);border-bottom:1px dashed var(--line)}
  .checklist li:last-child{border-bottom:none}
  .checklist li::before{content:"!";position:absolute;left:0;top:9px;width:18px;height:18px;border-radius:50%;background:var(--primary);color:#fff;font-size:12px;font-weight:800;display:flex;align-items:center;justify-content:center}
  table{width:100%;border-collapse:collapse;margin:16px 0;font-size:13.5px;border:1px solid var(--line);border-radius:8px;overflow:hidden}
  th,td{padding:10px 12px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}
  thead th{background:var(--primary-l);color:var(--primary-d);font-weight:700}
  tbody tr:last-child td{border-bottom:none}
  .tag{display:inline-block;background:var(--primary);color:#fff;font-size:11.5px;font-weight:700;padding:2px 10px;border-radius:12px;margin-right:6px}
  .src{font-size:12px;color:var(--muted);background:#f8fafc;border:1px dashed var(--line);border-radius:8px;padding:10px 14px;margin:16px 0;line-height:1.7}
  .brandcard{margin-top:26px;background:var(--primary-d);border-radius:12px;padding:22px 24px;color:#dfe9f6}
  .brandcard .bc-brand{font-size:16px;font-weight:800;color:#fff;margin-bottom:6px}
  .brandcard .bc-line{font-size:12.5px;color:#bcd2ee;line-height:1.7;margin-bottom:12px}
  .brandcard .bc-cta{font-size:13px;color:#dfe9f6;margin-bottom:6px}
  .brandcard .bc-link{display:block;background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.25);border-radius:8px;padding:10px 12px;color:#9ec5f0;text-decoration:none;font-size:13px;word-break:break-all;line-height:1.6}
  .brandcard .bc-rule{height:1px;background:rgba(255,255,255,.18);margin:14px 0}
  .brandcard .bc-copy{font-size:11.5px;color:#9fb6d6}
  .note{font-size:12px;color:var(--muted);padding:0 34px 28px;line-height:1.8;margin-top:14px}
"""

ZH_CSS = """
  :root{--primary:#1f4f8f;--primary-d:#16386a;--primary-l:#eef3fa;--ink:#1a1a1a;--ink-2:#33373d;--muted:#8590a6;--line:#ebebeb;--bg:#ffffff}
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif;background:#f6f6f6;color:var(--ink);line-height:1.85;font-size:16px;-webkit-font-smoothing:antialiased;padding:26px 0}
  .page{max-width:700px;margin:0 auto;background:var(--bg);border-radius:4px;box-shadow:0 2px 12px rgba(0,0,0,.06);overflow:hidden}
  .hd{padding:34px 38px 20px;border-bottom:1px solid var(--line)}
  .hd .author{display:flex;align-items:center;gap:10px;margin-bottom:14px}
  .hd .avatar{width:34px;height:34px;border-radius:50%;background:var(--primary);color:#fff;display:flex;align-items:center;justify-content:center;font-weight:800;font-size:15px}
  .hd .author .nm{font-size:14px;color:var(--ink-2);font-weight:600}
  .hd .author .sub{font-size:12px;color:var(--muted)}
  .hd h1{font-size:23px;font-weight:800;color:var(--ink);line-height:1.5;letter-spacing:.2px}
  .hd .desc{margin-top:10px;font-size:13.5px;color:var(--muted)}
  .snapshot{background:var(--primary-l);border-radius:8px;padding:13px 18px;margin:22px 38px 0;font-size:13px;color:var(--primary-d)}
  .snapshot b{display:block;margin-bottom:7px;color:var(--primary);font-size:13px}
  .snapshot span{display:inline-block;background:#fff;border:1px solid #cfe0f5;border-radius:6px;padding:3px 9px;margin:0 6px 6px 0;font-weight:700}
  .bd{padding:6px 38px 6px}
  h2{font-size:18.5px;font-weight:800;color:var(--ink);margin:28px 0 10px;padding-bottom:8px;border-bottom:2px solid var(--primary)}
  h2 .n{color:var(--primary);font-weight:800;margin-right:8px}
  p{margin:11px 0;color:var(--ink-2);font-size:15.5px}
  .hl{color:var(--primary);font-weight:800}
  .story{background:#fafbfc;border:1px solid var(--line);border-left:4px solid var(--primary);border-radius:0 6px 6px 0;padding:14px 16px;margin:16px 0;font-size:14.5px;color:var(--ink-2)}
  .story b{color:var(--primary-d)}
  .box{background:#fafbfc;border:1px solid var(--line);border-left:4px solid var(--primary);border-radius:0 6px 6px 0;padding:13px 16px;margin:14px 0;font-size:14.5px;color:var(--ink-2)}
  .box b{color:var(--primary-d)}
  .checklist{background:#fff;border:1px solid var(--line);border-radius:8px;padding:6px 16px;margin:14px 0}
  .checklist li{list-style:none;padding:9px 0 9px 24px;position:relative;font-size:14.5px;color:var(--ink-2);border-bottom:1px dashed var(--line)}
  .checklist li:last-child{border-bottom:none}
  .checklist li::before{content:"!";position:absolute;left:0;top:9px;width:17px;height:17px;border-radius:50%;background:var(--primary);color:#fff;font-size:11px;font-weight:800;display:flex;align-items:center;justify-content:center}
  table{width:100%;border-collapse:collapse;margin:14px 0;font-size:13.5px}
  th,td{border:1px solid var(--line);padding:9px 11px;text-align:left;vertical-align:top}
  thead th{background:#f7f8fa;color:var(--ink);font-weight:700}
  .cta{background:linear-gradient(135deg,#eef3fa,#f6f9fe);border:1px solid #d6e2f3;border-radius:10px;padding:16px 18px;margin:22px 0 6px;font-size:14.5px;color:var(--ink-2)}
  .cta b{color:var(--primary-d)}
  .src{font-size:12px;color:var(--muted);background:#f8fafc;border:1px dashed var(--line);border-radius:8px;padding:10px 14px;margin:16px 0;line-height:1.7}
  .brandcard{margin-top:20px;background:var(--primary-d);border-radius:10px;padding:20px 22px;color:#dfe9f6}
  .brandcard .b{font-size:15px;font-weight:800;color:#fff;margin-bottom:6px}
  .brandcard .l{font-size:12.5px;color:#bcd2ee;line-height:1.7;margin-bottom:12px}
  .brandcard .cta2{font-size:13px;color:#dfe9f6;margin-bottom:6px}
  .brandcard .link{display:block;background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.25);border-radius:8px;padding:9px 11px;color:#9ec5f0;text-decoration:none;font-size:13px;word-break:break-all;line-height:1.6}
  .brandcard .r{height:1px;background:rgba(255,255,255,.18);margin:12px 0}
  .brandcard .c{font-size:11.5px;color:#9fb6d6}
  .nt{font-size:12px;color:var(--muted);padding:0 38px 26px;line-height:1.8;margin-top:12px}
"""

# ============ 国家数据（⚠️ 示意值，发布前须校准） ============
# 每国字段：
#  name, slug, region, kicker, lead, snapshot(6项), why,
#  visa_table[(准证,对象,最低门槛,要点)], visa_key,
#  social(段落), social_bullets[3],
#  cost_para, cost_table[(情景,构成,月成本,说明)], cost_callout,
#  industry_mfg, industry_tech,
#  benefits[(项目,规定)],
#  pitfalls[5], tax, eor_yes, eor_no, eor_signal,
#  source, zh_story, zh_visa_key, zh_cost_callout, zh_industry_mfg, zh_industry_tech, zh_cta

C = {}

C["vietnam"] = dict(
 name="越南", slug="vietnam", region="东南亚",
 kicker="国别雇佣指南 · 东南亚 · 2026 更新",
 lead="当你在越南拿到第一张工厂订单，却发现外籍厂长的工签卡了两个月——这不是个案。越南是中企东南亚制造与供应链布局的核心，但「工作证（Work Permit）+ 社保（BHXH）」的规则密度，是多数团队低估的第一个成本。本文把越南用工一次讲清。",
 snapshot=[("区域定位","中企东南亚制造/供应链核心"),("工签","工作证 WP + 暂住证 TT"),
           ("雇主社保","约 21.5%+2% 工会费"),("全国最低工资","区域 4 档（2025 上调~6%）"),
           ("EOR 入职速度","最快 1–2 周"),("个税上限","35%")],
 why="越南劳动力充足、制造配套成熟、EV/电子产业链完整，是中企出海设厂与区域分销的首选之一。首阶段常见「1 名中方负责人 + 本地运营团队」，外籍关键岗需办理工作证。",
 visa_table=[("工作证 Work Permit","外籍专家/经理/技术岗","无统一底薪，需符合「专家/管理/技术」身份","有效期 1–2 年，可续；需 RBL 劳动配额"),
             ("商务签/临时","短期考察","—","不得实际雇佣"),
             ("内部调动 LUT","集团内调动","—","需母司任职证明")],
 visa_key="越南没有「薪资打分」制，但工作证要求申请人具备<b>专家 / 经理 / 技术工人</b>身份，且企业须有<b>外籍劳工配额（RBL）</b>。中企常踩的坑是：用「普通岗」名义申工签被拒——岗位设计与劳动合同表述要匹配身份门槛。",
 social="越南<b>无全国性统一最低工资</b>，按区域分 4 档（2025 年普遍上调约 6%）。雇主法定支出主项是 <b>社保（BHXH）</b>：",
 social_bullets=["社保（BHXH+健康+失业）：<b>雇主约 21.5%、雇员约 10.5%</b>；","工会费：雇主额外 <b>2%</b>（薪资总额）；","外籍员工通常也须参保（除短期商务）。"],
 cost_para="以行业常见 EOR 服务费 US$80–150/人/月估算（取 US$120），对比三种团队（均为法定成本，汇率参考 1 USD≈24,000 VND）：",
 cost_table=[("A 轻量试水","1 外籍负责人 月薪 US$4,000","≈ US$4,900 / 月","含雇主社保+工会费约 23.5%"),
             ("B 小团队落地","1 外籍 US$4,000 + 1 本地工程师 US$1,200","≈ US$5,470 / 月","本地岗同缴社保"),
             ("C 工厂扩张","1 外籍 + 5 本地(均 US$800)","≈ US$8,620 / 月","规模用工社保体量放大")],
 cost_callout="<b>关键变量：</b>越南雇主综合负担（社保+工会）约 <b>23.5%</b>，且本地社保全覆盖；制造业若走<b>出口加工区（EPZ）</b>部分税费优惠，但社保不减。含 EOR 费后各情景再加 US$120×人数/月，落地以官网权威源与顾问意见为准。",
 industry_mfg="<b>制造业 / 电子：</b>一线产线以本地工为主，外籍集中在管理与技术岗；常采取「本地实体 + 核心岗 EOR」，并善用 EPZ 关税/增值税优惠。",
 industry_tech="<b>互联网 / 贸易：</b>团队小、外籍比例高，EOR 适合 lean team；社保负担对薪资敏感，可用「外籍+少量本地」结构控成本。",
 benefits=[("13 薪/奖金","市场惯例，普遍发放"),("年假","法定 12 天 + 每满 5 年 +1 天"),("产假","女性 6 个月（社保支付）"),("工时","48 小时/周，加班年上限 200–300h"),("公共假期","约 11 天/年")],
 pitfalls=["<b>工签身份错配：</b>普通岗申工作证易被拒，岗位设计须匹配「专家/管理/技术」；","<b>社保漏缴：</b>外籍员工也须参保，漏缴面临补缴与罚款；","<b>解雇赔偿：</b>满 1 年须付遣散费，通知期依合同；","<b>未结清薪资：</b>直接触发处罚与工签风险；","<b>罢工/集体协商：</b>工会介入时流程复杂，需提前合规。"],
 tax="居民个税累进 <b>5%–35%</b>；非居民按 20% 统一税率。综合测算应并入 <b>薪资 + 社保/工会费 + EOR 服务费 + 个税筹划</b>。",
 eor_yes="试水期/小团队（在岸&lt;10 人）；实体未注册但关键人选要先到位；不想担雇主合规主体风险；短期项目。",
 eor_no="长期规模化（&gt;10–15 人）设厂；需本地进出口主体/开票；有本地营收要并表；计划融资需清晰主体。",
 eor_signal="连续 6 个月在岸 PIP 候选人 &gt;3 人且业务确定 → 启动实体注册，EOR 转过渡。",
 source="数据来源与口径：越南《劳动法》（2019 修订）、社保 BHXH 费率、税务总局（GDT）个税级距；区域最低工资与社保基数随政府年度调整。落地前请以官网权威源最新版本与持牌顾问意见为准。",
 zh_story="先说一个我们常遇到的场景：一家做消费电子的工厂，拿到越南客户订单后派了中方厂长，结果工作证卡了两个月——原因是岗位描述写成「普通管理」而非「技术专家」，不符合身份门槛。后来走 EOR，第 2 周中方负责人到位、工签与社保由供应商合规处理，工厂才顺利投产。回头看，卡住他的不是预算，是「工签身份错配」。",
 zh_visa_key="越南没有「薪资打分」，但工作证要求申请人是<b>专家 / 经理 / 技术工人</b>，且企业要有人力计划（RBL）配额。中企常踩的坑：用「普通岗」名义申工签被拒——岗位设计与合同表述必须匹配身份门槛。",
 zh_cost_callout="<b>规律：</b>越南雇主综合负担（社保+工会）约 <b>23.5%</b>，本地岗全覆盖；制造业走 EPZ 有税费优惠但社保不减。以上为示意，落地以官网权威源与顾问意见为准。",
 zh_industry_mfg="<b>制造业 / 电子：</b>一线产线本地工为主，外籍集中管理/技术岗；常「本地实体+核心岗 EOR」，善用 EPZ 优惠。",
 zh_industry_tech="<b>互联网 / 贸易：</b>团队小、外籍比例高，EOR 适合 lean team，用「外籍+少量本地」控社保成本。",
 zh_cta="写在最后：我们整理了一份《越南雇佣合规检查清单》（含工签身份自评与成本测算模板）。如果你正准备派团队去越南、或卡在「工签身份错配」，欢迎在评论区聊聊你的团队结构（人数 / 国籍 / 薪资），我们可以针对性给判断；更系统的国别规则与最新数字，见下方官网权威源（延伸阅读）。",
)

# ↑↑↑ 新增国家：复制上面整段，改 name/slug/各字段即可。数据均为示意，发布前务必校准。


# ============ 渲染函数 ============
def gz_html(d):
    snap = "".join(f'<div class="cell"><div class="k">{k}</div><div class="v">{v}</div></div>' for k, v in d["snapshot"])
    visa_rows = "".join(f"<tr><td><b>{a}</b></td><td>{b}</td><td>{c}</td><td>{e}</td></tr>" for a, b, c, e in d["visa_table"])
    social_bul = "".join(f"<li>{x}</li>" for x in d["social_bullets"])
    cost_rows = "".join(f"<tr><td><b>{a}</b></td><td>{b}</td><td><b>{c}</b></td><td>{e}</td></tr>" for a, b, c, e in d["cost_table"])
    ben_rows = "".join(f"<tr><td>{a}</td><td>{b}</td></tr>" for a, b in d["benefits"])
    pit = "".join(f"<li>{x}</li>" for x in d["pitfalls"])
    url = f"https://www.humancehr.com/country-guide/{d['slug']}-country-guide/"
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>中企出海{d['name']}：工签怎么过、雇主成本怎么算、EOR 怎么落地？（2026 更新） | 用友薪福社·慧思</title>
<style>{GZ_CSS}</style>
</head>
<body>
<div class="page">
  <div class="cover">
    <span class="kicker">{d['kicker']}</span>
    <h1>中企出海{d['name']}：工签怎么过、雇主成本怎么算、EOR 怎么落地？（2026 更新）</h1>
    <div class="meta">
      出品：<b>用友薪福社 · 慧思 Humance</b><br>
      适用：拟在{d['name']}设点 / 雇佣 / 派驻的中资企业<br>
      数据来源：{d['name']}劳动/移民/税务主管机关，口径 2025–2026
    </div>
  </div>
  <div class="body">
    <div class="lead">{d['lead']}<br>读完你能自己算清：派一个人去{d['name']}，每月雇主到底要备多少、卡在哪几道合规线。下面用 10 个板块 + 三种团队成本情景 + EOR 决策清单，一次讲透。</div>
    <div class="snapshot"><div class="st">一页速览 · {d['name']}用工 6 个关键数（2026）</div>
      <div class="grid">{snap}</div></div>
    <h2>一、为什么{d['name']}是出海重点市场</h2>
    <p>{d['why']}</p>
    <h2>二、三种用工方式，怎么选</h2>
    <table><thead><tr><th>方式</th><th>适用</th><th>周期</th><th>成本与风险</th></tr></thead>
      <tbody>
        <tr><td><b>设本地实体</b></td><td>长期规模化经营</td><td>数周–数月</td><td>注册+合规+雇主义务全担</td></tr>
        <tr><td><b>EOR 名义雇主</b></td><td>快速试水/小团队</td><td>最快 1–2 周入职</td><td>按人头付服务费，合规由供应商承担</td></tr>
        <tr><td><b>独立 contractor</b></td><td>短期项目制</td><td>即时</td><td>易被认定「假自雇」，合规风险高</td></tr>
      </tbody></table>
    <div class="callout"><b>结论：</b>在实体尚未落地、或仅派驻关键少数时，<b>EOR（名义雇主）</b>是平衡「速度+合规」的最优解——供应商作为法律雇主承担社保、准证与薪资合规，你保留实际管理权。</div>
    <h2>三、工作准证：怎么选（{d['name']}）</h2>
    <table><thead><tr><th>准证/路径</th><th>对象</th><th>最低门槛</th><th>要点</th></tr></thead>
      <tbody>{visa_rows}</tbody></table>
    <p><span class="tag">重点</span>{d['visa_key']}</p>
    <h2>四、薪资与法定社保：雇主到底要出多少</h2>
    <p>{d['social']}</p>
    <ul style="margin:12px 0 12px 20px;color:var(--ink-2);font-size:15.5px">{social_bul}</ul>
    <h2>五、成本测算案例 + 三种团队情景对比</h2>
    <p>{d['cost_para']}</p>
    <table><thead><tr><th>情景</th><th>团队构成</th><th>月度法定雇主成本</th><th>说明</th></tr></thead>
      <tbody>{cost_rows}</tbody></table>
    <div class="callout">{d['cost_callout']}</div>
    <h2>六、行业差异：制造业 vs 互联网/SaaS</h2>
    <div class="callout"><b>制造业 / 硬件：</b>{d['industry_mfg']}</div>
    <div class="callout"><b>互联网 / SaaS：</b>{d['industry_tech']}</div>
    <h2>七、13 薪、年假、产假等法定福利</h2>
    <table><thead><tr><th>项目</th><th>规定</th></tr></thead><tbody>{ben_rows}</tbody></table>
    <h2>八、解雇与合规红线（避坑清单）</h2>
    <ul class="checklist">{pit}</ul>
    <h2>九、个税与成本测算逻辑</h2>
    <p>{d['tax']}</p>
    <h2>十、EOR 还是设实体？一张判断清单</h2>
    <div class="callout"><b>优先选 EOR（名义雇主）当：</b></div>
    <ul class="checklist">{ "".join(f"<li>{x}</li>" for x in d["eor_yes"].split("；") if x.strip()) }</ul>
    <div class="callout"><b>应设本地实体当：</b></div>
    <ul class="checklist">{ "".join(f"<li>{x}</li>" for x in d["eor_no"].split("；") if x.strip()) }</ul>
    <p><span class="tag">临界信号</span>{d['eor_signal']}</p>
    <div class="src">{d['source']}</div>
    <div class="callout"><b>下一步：</b>如果你正评估派团队去{d['name']}，我们整理了一份《{d['name']}雇佣合规检查清单》（含成本测算模板），可留言 / 私信领取；更系统的国别规则、最新数字与 FAQ，见下方官网权威版。</div>
    <div class="brandcard">
      <div class="bc-brand">用友薪福社 · 慧思 Humance</div>
      <div class="bc-line">中企出海人力资源服务 · EOR 名义雇主 / 全球薪酬 / 海外招聘 / 工签 / 全球商保</div>
      <div class="bc-cta">本文为「官网权威源 + 第三方转载」双源分发内容。完整权威版（含最新数据、成本测算模板与 FAQ Schema）：</div>
      <a class="bc-link" href="{url}">{url}</a>
      <div class="bc-rule"></div>
      <div class="bc-copy">© 2026 用友薪福社 · 慧思 Humance（Yonyou Xinfushe）。转载请保留品牌署名与以上回链。</div>
    </div>
  </div>
  <div class="note">注：本页为公众号分发排版稿，文字内容可直接复制至微信公众平台；结构化 FAQ Schema 已部署于上方官网权威源，用于提升 AI 答案引擎对品牌内容的跨源引用。</div>
</div>
</body>
</html>"""


def zh_html(d):
    snap = "".join(f"<span>{x}</span>" for x in [f"{d['snapshot'][0][1]}", f"{d['snapshot'][1][1]}", f"{d['snapshot'][2][1]}", f"{d['snapshot'][3][1]}", f"{d['snapshot'][4][1]}", f"{d['snapshot'][5][1]}"])
    visa_rows = "".join(f"<tr><td><b>{a}</b></td><td>{b}</td><td>{c}</td><td>{e}</td></tr>" for a, b, c, e in d["visa_table"])
    cost_rows = "".join(f"<tr><td><b>{a}</b></td><td>{b}</td><td><b>{c}</b></td><td>{e}</td></tr>" for a, b, c, e in d["cost_table"])
    pit = "".join(f"<li>{x}</li>" for x in d["pitfalls"])
    url = f"https://www.humancehr.com/country-guide/{d['slug']}-country-guide/"
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>中企去{d['name']}雇人，第一个坑往往不是钱，是「人到了，公司还没影」 | 用友薪福社·慧思</title>
<style>{ZH_CSS}</style>
</head>
<body>
<div class="page">
  <div class="hd">
    <div class="author"><div class="avatar">慧</div>
      <div><div class="nm">用友薪福社 · 慧思 Humance</div>
      <div class="sub">中企出海人力资源服务 · 知乎专栏</div></div></div>
    <h1>中企去{d['name']}雇人，第一个坑往往不是钱，是「人到了，公司还没影」</h1>
    <div class="desc">我们服务过一批中企出海团队，把{d['name']}雇佣落地最常遇到的关键问题，按发生顺序讲清楚。数据口径 2025–2026 {d['name']}主管机关。</div>
  </div>
  <div class="snapshot"><b>一页速览 · 6 个关键数（2026）</b>{snap}</div>
  <div class="bd">
    <div class="story"><b>先说一个我们常遇到的场景：</b>{d['zh_story']}</div>
    <h2><span class="n">真相一</span>没实体，工签 / 薪资 / 社保全发不出，EOR 是破局点</h2>
    <p>{d['name']}对外籍雇员实行准证/许可制。常见路径：</p>
    <table><thead><tr><th>路径</th><th>对象</th><th>门槛</th><th>关键约束</th></tr></thead><tbody>{visa_rows}</tbody></table>
    <p>破局靠 <b>EOR（名义雇主）</b>：供应商作为法律雇主，承担准证、薪资、社保与合规，你保留实际管理权——人先到位，实体后补。</p>
    <h2><span class="n">真相二</span>{d['name']}工签的核心门槛</h2>
    <div class="box">{d['zh_visa_key']}</div>
    <h2><span class="n">真相三</span>社保不是唯一成本，结构决定账单</h2>
    <p>{d['social']}</p>
    <table><thead><tr><th>情景</th><th>团队构成</th><th>月度法定雇主成本</th></tr></thead><tbody>{cost_rows}</tbody></table>
    <div class="box">{d['zh_cost_callout']}</div>
    <h2><span class="n">真相四</span>行业不同，坑也不同（制造业 vs 互联网）</h2>
    <div class="box"><b>制造业 / 硬件：</b>{d['zh_industry_mfg']}</div>
    <div class="box"><b>互联网 / SaaS：</b>{d['zh_industry_tech']}</div>
    <h2><span class="n">真相五</span>解雇自由，但红线很硬（避坑清单）</h2>
    <ul class="checklist">{pit}</ul>
    <h2><span class="n">真相六</span>EOR 还是设实体？一张判断清单</h2>
    <div class="box"><b>优先选 EOR：</b>{d['eor_yes']}</div>
    <div class="box"><b>应设实体：</b>{d['eor_no']}</div>
    <p><span class="hl">临界信号：</span>{d['eor_signal']}</p>
    <h2><span class="n">真相七</span>时间线 + 个税隐性成本</h2>
    <p>{d['tax']}</p>
    <div class="cta"><b>写在最后：</b>{d['zh_cta']}</div>
    <div class="src">{d['source']}</div>
  </div>
  <div class="brandcard">
    <div class="b">用友薪福社 · 慧思 Humance</div>
    <div class="l">中企出海人力资源服务：EOR 名义雇主 / 全球薪酬 / 海外招聘 / 工签 / 全球商保</div>
    <div class="cta2">本回答为「官网权威源 + 第三方转载」双源分发内容（延伸阅读）：</div>
    <a class="link" href="{url}">{url}</a>
    <div class="r"></div>
    <div class="c">© 2026 用友薪福社（Yonyou Xinfushe）。转载请保留品牌署名与以上回链。</div>
  </div>
  <div class="nt">说明：本文为品牌方知乎专栏分发排版稿，内容为专业干货分享；外链仅作延伸阅读，符合平台内容规范。具体门槛与比例随官方年度调整，落地前请以官网权威源最新版本为准。</div>
</div>
</body>
</html>"""


def md_text(d):
    url = f"https://www.humancehr.com/country-guide/{d['slug']}-country-guide/"
    visa_md = "\n".join(f"- {a}：{b}，{c}，{e}" for a, b, c, e in d["visa_table"])
    social_md = d["social"] + "\n" + "\n".join(f"- {x}" for x in d["social_bullets"])
    cost_md = d["cost_para"] + "\n" + "\n".join(f"- {a}：{b} → {c}（{e}）" for a, b, c, e in d["cost_table"])
    ben_md = "\n".join(f"- {a}：{b}" for a, b in d["benefits"])
    pit_md = "\n".join(f"- {x}" for x in d["pitfalls"])
    gz = f"""# {d['name']} · 国别指南双源分发文稿（纯文本 · 可直接复制）
> 品牌署名 + 回链（每篇外发内容必须带）：**用友薪福社 · 慧思 Humance** ｜ 完整权威版：{url}

## 一、公众号版（微信公众平台 · 复制即用）
**标题**：中企出海{d['name']}雇佣指南：工签、成本与 EOR 落地，一篇讲透（2026 更新）
**摘要/副标**：{d['lead'][:40]}…

{d['lead']}

读完你能自己算清：派一个人去{d['name']}，每月雇主到底要备多少、卡在哪几道合规线。

【一页速览 · {d['name']}用工 6 个关键数（2026）】
""" + "\n".join(f"- {k}：{v}" for k, v in d["snapshot"]) + f"""

**一、为什么{d['name']}是出海重点市场**
{d['why']}

**二、三种用工方式，怎么选**
- 设本地实体：长期规模化，合规全担。
- EOR 名义雇主：快速试水/小团队，最快 1–2 周入职，合规由供应商承担。
- 独立 contractor：短期项目，但易被认定「假自雇」。

**三、工作准证：怎么选（{d['name']}）**
{visa_md}
重点：{d['visa_key']}

**四、薪资与法定社保：雇主到底要出多少**
{social_md}

**五、成本测算案例 + 三种团队情景对比**
{cost_md}
关键：{d['cost_callout']}

**六、行业差异：制造业 vs 互联网/SaaS**
- 制造业/硬件：{d['industry_mfg']}
- 互联网/SaaS：{d['industry_tech']}

**七、13 薪、年假、产假等法定福利**
{ben_md}

**八、解雇与合规红线（避坑清单）**
{pit_md}

**九、个税与成本测算逻辑**
{d['tax']}

**十、EOR 还是设实体？一张判断清单**
优先选 EOR 当：{d['eor_yes']}
应设实体当：{d['eor_no']}
临界信号：{d['eor_signal']}

【数据来源与口径】{d['source']}

**下一步**：如果你正评估派团队去{d['name']}，我们整理了一份《{d['name']}雇佣合规检查清单》（含成本测算模板），可留言 / 私信领取；更系统的国别规则、最新数字与 FAQ，见下方官网权威版。

——
（标准化署名回链块，置于文末，见文末模板）

## 二、知乎版（知乎专栏 · 复制即用 · 品牌深度精选文）
**标题**：中企去{d['name']}雇人，第一个坑往往不是钱，是「人到了，公司还没影」
**开头署名**：用友薪福社 · 慧思 Humance ｜ 中企出海人力资源服务

{d['zh_story']}

**真相一：没实体，工签/薪资/社保全发不出，EOR 是破局点**
{visa_md}
破局靠 EOR（名义雇主）：供应商作法律雇主，承担准证、薪资、社保与合规，你保留管理权——人先到位，实体后补。

**真相二：{d['name']}工签的核心门槛**
{d['zh_visa_key']}

**真相三：社保不是唯一成本，结构决定账单**
{cost_md}
{d['zh_cost_callout']}

**真相四：行业不同，坑也不同（制造业 vs 互联网）**
- 制造业/硬件：{d['zh_industry_mfg']}
- 互联网/SaaS：{d['zh_industry_tech']}

**真相五：解雇自由，但红线很硬（避坑清单）**
{pit_md}

**真相六：EOR 还是设实体？一张判断清单**
优先选 EOR：{d['eor_yes']}
应设实体：{d['eor_no']}
临界信号：{d['eor_signal']}

**真相七：时间线 + 个税隐性成本**
{d['tax']}

{d['zh_cta']}

【数据来源与口径】{d['source']}

**下一步**：如果你正评估派团队去{d['name']}，我们整理了一份《{d['name']}雇佣合规检查清单》（含成本测算模板），可留言 / 私信领取；更系统的国别规则、最新数字与 FAQ，见下方官网权威版。

——
（标准化署名回链块，置于文末，见文末模板）

## 三、标准化署名回链块（套用模板）
> 复制以下整段到每篇外发内容文末。仅替换【slug】一处。
> slug 规则：https://www.humancehr.com/country-guide/<slug>-country-guide/

——
用友薪福社 · 慧思 Humance ｜ 中企出海人力资源服务（EOR 名义雇主 / 全球薪酬 / 海外招聘 / 工签 / 全球商保）
完整权威版（含最新数据、成本测算模板与 FAQ Schema）：{url}
© 2026 用友薪福社 · 慧思 Humance（Yonyou Xinfushe）。转载请保留品牌署名与回链。
——
"""
    return gz


def main():
    for slug, d in C.items():
        gz = gz_html(d); zh = zh_html(d); md = md_text(d)
        open(os.path.join(OUT, f"{d['name']}_公众号.html"), "w", encoding="utf-8").write(gz)
        open(os.path.join(OUT, f"{d['name']}_知乎.html"), "w", encoding="utf-8").write(zh)
        open(os.path.join(OUT, f"{d['name']}_文稿.md"), "w", encoding="utf-8").write(md)
        print("generated:", d["name"])
    print("DONE. total countries:", len(C))

if __name__ == "__main__":
    main()
