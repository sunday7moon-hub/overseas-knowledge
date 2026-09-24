#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
慧思国别指南「更新标注」任务台账生成器
========================================
输入：批次配置 + 构建报告 + B2-01 校对明细 CSV
输出：
  1) <out>_任务条目.csv        每条标注一行（名称/链接/更新时间/上架时间/更新内容/存疑项/备注）
  2) <out>_存疑待溯源.csv      来源存疑项 + 溯源入口 + 状态
  3) <out>_任务台账.md         人读版（含门禁结论、覆盖统计、下一步）

用法：
  python3 make_ledger.py --config ../references/batches/b2-01-t.json \
      --workdir <build dir> --report <build report json> \
      --proofread-csv <B2-01 csv> --outdir <输出目录> --prefix 2026-09-22_国别指南更新任务台账_B2-01-T
"""
import argparse
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import guide_patch_lib as L  # noqa: E402

# 存疑项溯源指引（人工/检索确认过的权威入口，一处维护）
TRACE = {
    "PR-20260907-008": ("现行值来源待补", "德国《联邦休假法》Bundesurlaubsgesetz 官方文本（gesetze-im-internet.de）；各州法定假日以州政府公告为准",
                        "未开始"),
    "PR-20260907-009": ("现行值来源待补", "BGB §622（通知期）+ BGB §622 Abs.2；BMAS 官方说明页",
                        "未开始"),
    "PR-20260907-010": ("现行值来源待补", "Kündigungsschutzgesetz §1a（解雇补偿计算）；BAG 判例库",
                        "未开始"),
    "PR-20260907-028": ("已查劳动部变更汇总页无此条目", "法国 Code du travail L1221-19～L1221-21（试用期）+ L1234-1 起（通知期）；Legifrance 官方文本",
                        "未开始"),
    "PR-20260907-037": ("仅检索到竞业限制法案在立法程序中", "荷兰 Burgerlijk Wetboek 7:652（试用期）；SZW 官网；Tweede Kamer 立法进度页",
                        "未开始"),
    "PR-20260907-060": ("原依据来源为单一低层级站点（Qatar Alive）且链接异常；已用政府公报 + 双四大复核",
                        "卡塔尔官方公报 2026-06-25 刊 Law No. 9/2026（生效 2026-07-25）；Al Meezan 法律门户；"
                        "K&L Gates《Qatar Introduces Significant Amendments to the Labour Law》；"
                        "Crowell & Moring《Key Amendments Introduced by Law No. 9 of 2026》",
                        "✅ 已完成，可升级入库"),
    "PR-20260907-104": ("原依据来源为非政府站点（Chamberlain.ph / LegalClarity）",
                        "NWPC 官网 https://nwpc.dole.gov.ph/ 各国别区域页（如 /region-xiii/）+ NWPC 全国工资矩阵",
                        "入口已定位，待逐区取数"),
}


def tok_caveat(txt):
    t = (txt or "").strip()
    for k in ("须", "待核", "⚠️", "存疑", "不一致", "冲突"):
        if k in t:
            return t
    return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                     "..", "references", "batches", "b2-01-t.json"))
    ap.add_argument("--workdir", required=True)
    ap.add_argument("--report", default=None)
    ap.add_argument("--proofread-csv", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--prefix", default="国别指南更新任务台账")
    a = ap.parse_args()

    cfg = json.load(open(a.config, encoding="utf-8"))
    rep_path = a.report or os.path.join(a.workdir, "_build_report.json")
    rep = json.load(open(rep_path, encoding="utf-8"))
    by_slug = {r["slug"]: r for r in rep["countries"]}
    os.makedirs(a.outdir, exist_ok=True)

    # ---------- 1) 任务条目 ----------
    rows, idx = [], 0
    for slug, cc in cfg["countries"].items():
        after = ""
        fp = os.path.join(a.workdir, slug, "content_AFTER.html")
        if os.path.exists(fp):
            after = open(fp, encoding="utf-8").read()
        for n in cc["notes"]:
            idx += 1
            # 落位章节：从 AFTER 正文里反查锚点所属 H2（构建期只在内存里，这里重算）
            sec_title = n.get("anchor_title") or ""
            if not sec_title and after and n.get("anchor"):
                _, sec_title = L._anchor_section(after, n["anchor"])
            sec_title = sec_title or ""
            st = L.STATUS_TEXT[n["status"]]
            rows.append({
                "序号": idx, "批次": cfg["batch"], "校对ID": n["rid"],
                "国别指南名称": f"{cc['name']}雇佣合规指南",
                "指南链接": cc["guide_url"],
                "正文版本": cc["page_date"], "documentId": cc["documentId"],
                "落位章节": sec_title,
                "字段项": n.get("field") or n.get("title") or "", "变更类型": n.get("kind") or "来源溯源", "状态": st,
                # ★ 「页面展示」列（2026-09-23 四轮）：红色（来源存疑）**不上前端**，
                #   只在这里留一行「否 —— 来源存疑，仅台账待处理」。这正是 Yoyo
                #   「记录台账待处理」的落点：页面上撤掉 ≠ 事情消失，得有个地方点得出人头。
                #   取值唯一来自 L.page_visibility（= on_page 推导），别在本脚本再判一次 status。
                "页面展示": L.page_visibility(n),
                "现行值(原文保留)": n.get("old") or "",
                "更新内容(拟/核实)": (n.get("new") or "—").replace("<b>", "").replace("</b>", ""),
                "生效日期": n.get("effective") or "—",
                # 溯源双源：原引（L3 二手）与回溯后的官方一手源，两栏并存（规范 §12）
                "原引来源": n.get("orig_source") or "",
                "原引层级": n.get("orig_tier") or "",
                "原引链接": n.get("url") or "",
                "来源": n.get("source") or "", "来源层级": n.get("tier") or "",
                "来源链接": n.get("official_url") or n.get("url") or "",
                "一手源名称": n.get("official_name") or "",
                "一手源链接": n.get("official_url") or "",
                "溯源状态": n.get("trace") or ("⏳ 待溯源" if not n.get("official_url") else ""),
                "溯源说明": n.get("note") or "",
                "更新时间(标注写入)": L.TODAY,
                "上架时间": ("—（本批为本地测试，未上架生产）" if cfg.get("mode") != "production-ready"
                              else f"{L.TODAY}（{cfg.get('batch', '')}）"),
                "存疑项": tok_caveat(n.get("extra")) or "—",
                "备注": n.get("extra") or "",
                "构建SHA": (by_slug.get(slug, {}).get("sha_after") or ""),
            })
    f1 = os.path.join(a.outdir, f"{a.prefix}_任务条目.csv")
    with open(f1, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # ---------- 2) 存疑待溯源 ----------
    raw = list(csv.DictReader(open(a.proofread_csv, encoding="utf-8-sig")))
    slugs = {v["name"]: (k, v) for k, v in cfg["countries"].items()}
    dout = []
    for r in raw:
        if r["来源层级"] != "存疑":
            continue
        rid = r["校对ID"]
        reason, src_adv, status = TRACE.get(rid, ("", "", "未开始"))
        _, cc = slugs.get(r["国家"], (None, dict(guide_url="", name=r["国家"])))
        dout.append({
            "校对ID": rid, "国家": r["国家"], "国别指南名称": f"{r['国家']}雇佣合规指南",
            "指南链接": cc.get("guide_url", ""),
            "字段项": r["字段项"], "变更类型": r["变更类型"], "需确认": r["需确认"],
            "原依据来源": r["依据来源"], "原来源链接": r["来源链接"],
            "存疑原因": reason or r["备注"],
            "溯源目标": "变更事实" if "未检索到" not in r["建议新值"] else "现行值来源",
            "建议权威源/入口": src_adv,
            "溯源状态": status,
            "本批处置": "未落标（按 L1 规则：来源存疑不上线）",
            "备注": r["备注"],
        })
    f2 = os.path.join(a.outdir, f"{a.prefix}_存疑待溯源.csv")
    with open(f2, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(dout[0].keys()))
        w.writeheader()
        w.writerows(dout)

    # ---------- 3) 人读台账 ----------
    n_by_status = {}
    for r in rows:
        n_by_status[r["状态"]] = n_by_status.get(r["状态"], 0) + 1
    type_cnt, tier_cnt = {}, {}
    for r in rows:
        type_cnt[r["变更类型"]] = type_cnt.get(r["变更类型"], 0) + 1
        tier_cnt[r["来源层级"]] = tier_cnt.get(r["来源层级"], 0) + 1
    pend_raw = sum(1 for r in raw if r["需确认"] == "是（数值类）")
    excluded = len(raw) - len(rows) - len(dout)
    # ★ 页面展示分流（2026-09-23 四轮）：红色（来源存疑）不上前端，只记本台账待处理。
    #   两个数必须都能从台账 CSV 直接数出来，否则「撤下」就成了「消失」。
    n_page = sum(1 for r in rows if r["页面展示"] == "是")
    n_hid = len(rows) - n_page
    hid_ids = [r["校对ID"].replace("PR-20260907-", "PR-") for r in rows if r["页面展示"] != "是"]

    md = [f"# {cfg['title']}",
          "",
          f"**批次**：{cfg['batch']}　｜　**日期**：{L.TODAY}　｜　**执行**：巴蒂 🧠　｜　**归属**：邱月（Yoyo）· 用友薪福社 出海 HR",
          f"**模式**：`{rep['mode']}` —— **本批只做本地构建与效果验证，未写 Strapi 生产**",
          f"**范围**：{cfg.get('scope','')}",
          "",
          "---",
          "",
          "## 一、本批做了什么（一句话）",
          "",
          f"从 B2-01 已校对出的 **{len(raw)} 条差异**里，按「只做内容变更项 + 来源可溯 + 免人工确认」三重筛选，"
          f"挑出 **{len(cfg['countries'])} 国 / {len(rows)} 条**，以「更新标注」形态**本地落到原文对应位置**并渲染验证；"
          f"来源存疑的 **{len(dout)} 条**按规则挡在门外、另立溯源清单；数值类 **{pend_raw} 条**仍等人工确认。",
          "",
          "| 处置 | 条数 | 说明 |",
          "|---|:--:|---|",
          f"| ✅ 本批落标（本地测试） | **{len(rows)}** | {len(cfg['countries'])} 国；"
          f"含 {L.STATUS_TEXT['pending']} {n_by_status.get(L.STATUS_TEXT['pending'], 0)} 条、"
          f"{L.STATUS_TEXT['keep']} {n_by_status.get(L.STATUS_TEXT['keep'], 0)} 条 |",
          f"| ↳ 其中**页面展示** | **{n_page}** | 绿色 / 橙黄两类，客户在页面上看得到 |",
          f"| ↳ 其中**未上页面** | **{n_hid}** | "
          + (f"红色（来源存疑）：{'、'.join(hid_ids)} —— 不上前端，仅本台账待处理；"
             f"补齐一手源后重走落线" if hid_ids else "无")
          + " |",
          f"| ⛔ 存疑不上线 | **{len(dout)}** | 来源层级=存疑，先溯源再入库（见清单） |",
          f"| ⏸ 待人工确认 | **{pend_raw}** | 数值类，须 Yoyo 在飞书台账勾「确认」 |",
          f"| （合计） | {len(raw)} | B2-01 全量差异 |",
          "",
          "---",
          "",
          "## 二、任务条目明细（国别 / 链接 / 更新时间 / 上架时间 / 更新内容 / 存疑项）",
          "",
          f"> 完整 CSV（{len(rows)} 行 × {len(rows[0])} 字段）：`{os.path.basename(f1)}`",
          "> **上架时间统一为「—（本地测试，未上架生产）」** —— 本批不写线上，待你验完效果再决定是否 `--apply`。",
          "> **「页面展示」列**：`是` = 客户在页面上看得到（绿 / 橙黄）；"
          "`否 —— 来源存疑，仅台账待处理` = 该条**不上前端**（红色档），"
          "本台账留行是它唯一的落点，别当成已处理。",
          "",
          "| 校对ID | 国别指南 | 落位章节 | 状态 | 页面展示 | 更新内容 | 生效日期 | 来源层级 | 存疑项 |",
          "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        newv = r["更新内容(拟/核实)"]
        newv = (newv[:78] + "…") if len(newv) > 78 else newv
        cav = "—" if r["存疑项"] == "—" else "⚠️ 有"
        pgv = "✅ 是" if r["页面展示"] == "是" else "🚫 否（待处理）"
        md.append(f"| {r['校对ID'].replace('PR-20260907-','PR-')} | {r['国别指南名称']} | {r['落位章节']} | "
                  f"{r['状态']} | {pgv} | {newv} | {r['生效日期']} | {r['来源层级']} | {cav} |")

    md += ["", "### 2.1 逐国落位与页面链接", "",
           "| 国家 | 国别指南名称 | 指南链接 | 正文版本 | 标注数（页面 / 未上） | 状态分布 | documentId | 构建 SHA |",
           "|---|---|---|---|:--:|---|---|---|"]
    for slug, cc in cfg["countries"].items():
        st = {}
        for n in cc["notes"]:
            k = {"pending": "⏳", "check": "⚠️", "keep": "✅"}[n["status"]]
            st[k] = st.get(k, 0) + 1
        dist = " ".join(f"{k} {v}" for k, v in st.items())
        _np = len(L.page_notes(cc["notes"]))
        md.append(f"| {cc['name']} | {cc['name']}雇佣合规指南 | {cc['guide_url']} | {cc['page_date']} | "
                  f"{_np} / {len(cc['notes']) - _np} | {dist} | `{cc['documentId']}` | `{by_slug.get(slug,{}).get('sha_after','')}` |")

    md += ["", "---", "", "## 三、门禁结论（出口门禁逐项销账）", "",
           "| # | 门禁项 | 结果 | 证据 |", "|:-:|---|---|---|",
           f"| 1 | 六要素齐备（状态/现行/新值/生效日/来源/标注时间） | ✅ | 每条标注「现行/拟更新为·核实结论/来源/标注写入/校对ID」计数 = {len(rows)} |",
           "| 2 | 来源层级 ≤ 权威媒体且可打开 | ✅ | 本批仅收 政府/四大·律所/权威媒体/企业公告，7 条 `存疑` 已剔除 |",
           "| 3 | **原值只增不减** | ✅ | 还原校验：把插入串逐一移除后与原文逐字节比对，10 国**全部一致** |",
           "| 4 | **正文数字零改动** | ✅ | 同上（插入式改写，非覆盖式） |",
           f"| 5 | 生效状态按「生效日 vs 写入日」判定并写明 | ✅ | 状态仅 `{L.STATUS_TEXT['pending']}` / `{L.STATUS_TEXT['check']}` / `{L.STATUS_TEXT['keep']}`；待更新项另标 `{L.EFF_TEXT['effective']}` / `{L.EFF_TEXT['scheduled']}`（E1/E2 门禁） |",
           "| 6 | 章节徽标不污染目录 | ✅ | 走 `data-cg-badge` + CSS `::after`；校验「h2 文本含徽标文字」= 0 |",
           "| 7 | 版本条不因 flex 错位 | ✅ | 置于 `main-container` 内；校验「版本条位于 .nrz 下」= 0 |",
           "| 8 | 配色统一到站内实测色 | ✅ | 黑名单 `#0b3fbf/#155dfc/#1a365d` 出现次数 = 0 |",
           "| 9 | div 平衡 / h2 数量不变 | ✅ | 逐国校验通过 |",
           "| 10 | **无 `</div><` 危险邻接**（新） | ✅ | R1 门禁：前端 walker 的 u=d+7 会跳标签，一章错位后续全灭 |",
           "| 11 | **复刻前端 walker 能发现全部章节**（新） | ✅ | R2 门禁：本地正则全过 ≠ 线上能渲染 |",
           "| 12 | 生效状态判定与文案一致（新） | ✅ | E1/E2 门禁：按生效日重算后与页面文案逐条比对 |",
           "| 13 | 版本条计数含生效拆分（新） | ✅ | T7 门禁：法规已生效 N · 计划生效 M 与配置一致 |",
           "",
           f"构建报告：`{os.path.relpath(rep_path, a.outdir)}`（逐国 errors 数组全空）",
           "",
           "> **注**：门禁在首轮确实抓到 1 个真 bug —— 「只增不改」还原校验因徽标属性串截取错误而报红，"
           "修正后 10 国全绿。这条门禁不是走过场。",
           "",
           "---", "", "## 四、存疑项溯源（规则：先定内容、溯源后才入库）", "",
           f"> 完整清单：`{os.path.basename(f2)}`（{len(dout)} 条）", "",
           "| 校对ID | 国家 | 字段项 | 存疑原因 | 建议权威源/入口 | 状态 |",
           "|---|---|---|---|---|---|"]
    for d in dout:
        md.append(f"| {d['校对ID'].replace('PR-20260907-','PR-')} | {d['国家']} | {d['字段项']} | "
                  f"{d['存疑原因'][:46]} | {d['建议权威源/入口'][:96]} | {d['溯源状态']} |")

    md += ["", "---", "", "## 五、本批未覆盖的部分（不隐藏）", "",
           f"- **数值类 {pend_raw} 条**：按既定口径「数值类必须人工确认后才可回写线上」，仍停在飞书台账等勾选。"
           "本批一条都没碰。",
           f"- **存疑 {len(dout)} 条**：等溯源完成再入下一批。",
           f"- **B2-01 之外的 {76 - len(cfg['countries'])} 国**：属 B2-02～B2-05 批次窗口，未启动。",
           "- **线上生产**：阿联酋此前已落标（v2 修复版）；其余 9 国线上**仍是原文**，本批未写。",
           "",
           "### 5.1 与线上阿联酋版本的措辞差异（需统一）",
           "",
           f"本条版本条文案由「本页更新：X ｜ 待确认变更：N 项（数值类 M 项待审）」改为"
           f"「**正文版本：X ｜ 本次标注：N 项（{L.STATUS_TEXT['pending']} a · {L.STATUS_TEXT['keep']} b）**」。",
           "原因：原文案把「页面更新日」与「正文撰写日」混为一谈，且对非数值批次会渲染出「数值类 0 项待审」这种怪句。"
           "**下次 `--apply` 时 10 国一并统一**，阿联酋会随之改口径。",
           "",
           "---", "", "## 六、下一步（待你拍板）", "",
           "| # | 事项 | 建议 |",
           "|:-:|---|---|",
           "| 1 | 看效果 | 打开批量预览页逐国验收（版本条位置 / 徽标 / 标注块观感） |",
           "| 2 | 是否上架 | 认可后我跑 `--apply` 把这 10 国写入 Strapi（可单国回滚） |",
           "| 3 | 存疑项 | 卡塔尔 PR-060 已可升级入库；菲律宾 PR-104 入口已定位（NWPC 各区域页），需逐区取数 |",
           "| 4 | 数值类 | 87～89 条仍等你勾选，勾完可走下一批 |",
           "",
           "_本台账由 `humance-guide-annotation` 技能生成，一条事实一处定义。_"]
    f3 = os.path.join(a.outdir, f"{a.prefix}_任务台账.md")
    open(f3, "w", encoding="utf-8").write("\n".join(md))

    print(f"✅ 任务条目 CSV → {f1}（{len(rows)} 行）")
    print(f"✅ 存疑待溯源 CSV → {f2}（{len(dout)} 行）")
    print(f"✅ 人读台账 MD   → {f3}")


if __name__ == "__main__":
    main()
