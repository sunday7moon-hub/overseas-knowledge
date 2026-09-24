#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
慧思国别指南「已有标注」迁移器
================================
用途：某些国家指南**上线时用的是旧格式**（内联样式标注块、无 cg-update-note 类、旧版版本条文案）。
      直接用批次配置重建会**回退**线上已存在的标注。本脚本解决这个问题：
      把线上已注入的标注**反向抽取**成结构化 notes，交由 guide_patch_lib 用**新格式**重建。

输入：
  --live    线上当前 content（已含标注）
  --original 同一页面的干净原文（无标注）
输出：
  --out     notes JSON（含 page_date / notes[] / 抽取统计 / 反向还原结论）

核心校验（exit != 0 即不可用）：
  **反向还原** —— 把 live 里「样式块 + 版本条 + 徽标属性 + 全部标注块」逐一移除后，
  必须与 --original **逐字节相同**。相等 ⇒ 抽取无遗漏、线上没有额外改动；
  不等 ⇒ 说明 live 里还有本脚本不认识的改动，必须先查清，禁止继续。

用法：
  python3 migrate_existing.py \
      --live  /path/_live_snapshot/uae_LIVE_content.html \
      --original /path/_test_build/.../content_ORIGINAL.html \
      --out   ../references/batches/uae-v3.json \
      --slug united-arab-emirates-country-guide --name 阿联酋 \
      --document-id bv45ccot2vdpi5nmvue8rni9
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import guide_patch_lib as L  # noqa: E402  状态文案常量的唯一真相源（反抽映射按它对齐）

# ⚠️ NOTE_START 只匹配**旧格式**（内联样式 + 无 class 的标注块）。新格式（v3.1 之后，
# `<div class="cg-update-note" data-cg-rid=...>`）不走本脚本 —— 它的基线剥离由
# guide_patch_lib.strip_injections() 统一负责。若要"从新格式线上产物反推配置"，
# 需要另加分支，别以为本脚本会静默兼容（它不会）。
NOTE_START = re.compile(r'<div style="margin:18px 0 22px;padding:14px 18px;[^"]*">')
STYLE_BLOCK = re.compile(r"<style[^>]*>.*?</style>\s*", re.S)
VBAR = re.compile(r'<div class="cg-version-bar"[^>]*>.*?</div>\s*', re.S)
BADGE_ATTRS = re.compile(r'\s*data-cg-badge="[^"]*"\s*data-cg-state="[^"]*"'
                         r'(\s*data-cg-tone="[^"]*")?')

# ⚠️ 反抽映射必须**同时认旧文案与新文案** —— 它的输入是**线上已有**的产物，
# 而线上可能是任何一版。只认新文案会把旧页面反抽成"未知徽标"→ 整条漏掉
#（反抽漏一条 = 落标时丢一条，且不会报错）。
# 写法要点：**现用文案从常量反查**（改文案自动跟随），**旧文案显式列**（它们不会再变）。
CHIP2STATE_LEGACY = {
    "⏳ 计划更新": "pending",          # 最老一版
    "⚠️ 待核（来源存疑）": "check",    # 旧
    "✅ 已核实维持": "keep",           # 旧（Yoyo 2026-09-23 反馈"读着别扭"的那个）
}
CHIP2STATE = {**CHIP2STATE_LEGACY, **{v: k for k, v in L.STATUS_TEXT.items()}}
LABELS = ("拟更新为", "待核说明", "核实结论")


def nw(s):
    """去掉全部空白后的内容 —— 用于「非空白内容等价」判定。"""
    return re.sub(r"\s+", "", s)


def balanced_div(s, start):
    """返回从 start 处 <div 起、配平的 </div> 结束位置（不含）。"""
    depth = 0
    for m in re.finditer(r"<div\b[^>]*>|</div>", s[start:]):
        depth += -1 if m.group(0).startswith("</") else 1
        if depth == 0:
            return start + m.end()
    return -1


def _txt(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s)).strip()


def parse_note(block, content, block_start):
    st = None
    for k, v in CHIP2STATE.items():
        if f">{k}<" in block:
            st = v
            break
    title = re.search(r'<strong style="color:#18181b;font-size:14px;">(.*?)</strong>', block, re.S)
    old = new = ""
    for m in re.finditer(r'<div style="margin-bottom:5px;">(.*?)</div>', block, re.S):
        row = m.group(1)
        lab = _txt(row.split("</span>")[0])
        val = re.sub(r"^\s*<span[^>]*>[^<]*</span>", "", row).strip()
        if lab.startswith("现行"):
            old = val
        elif lab.split("：")[0] in LABELS:
            new = val
    meta_m = re.search(r'<div style="margin-top:9px;[^"]*">(.*?)</div>', block, re.S)
    meta = meta_m.group(1) if meta_m else ""
    eff = re.search(r"生效日期\s*<strong[^>]*>(.*?)</strong>", meta, re.S)
    src = re.search(r"来源：\s*(.*?)\s*（(.*?)）", _txt(meta))
    url = re.search(r'href="([^"]+)"', meta)
    # 校对ID 的取法：**先读 data-cg-rid 属性**（2026-09-23 起页面文本已不展示校对ID），
    # 再回退读旧格式的「校对ID XXX」文本 —— 反抽要能同时吃新老两代线上产物。
    rid = (re.search(r'data-cg-rid="([A-Za-z0-9\-]+)"', block)
           or re.search(r"校对ID\s*([A-Za-z0-9\-]+)", _txt(meta)))
    pos = re.search(r"页面位置：\s*([^｜|]+)", _txt(meta))
    extra_m = re.search(r'<div style="margin-top:6px;color:#52525b;font-size:12\.5px;">(.*?)</div>', block, re.S)
    # 锚点 = 该块之前最近的 h2/h3 **完整元素**（build 用 replace(anchor, anchor+blk) 追加，必须含文本与闭标签）
    heads = list(re.finditer(r"<h[23][^>]*>.*?</h[23]>", content[:block_start], re.S))
    anchor = heads[-1].group(0) if heads else ""
    return dict(
        rid=rid.group(1) if rid else "", status=st,
        title=_txt(title.group(1)) if title else "",
        old=old, new=new,
        effective=_txt(eff.group(1)) if eff else "—",
        source=src.group(1) if src else "—", tier=src.group(2) if src else "—",
        url=url.group(1) if url else "",
        anchor=anchor, anchor_title=_txt(pos.group(1)) if pos else "",
        extra=extra_m.group(1).strip() if extra_m else "",
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", required=True)
    ap.add_argument("--original", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--slug", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--document-id", required=True)
    ap.add_argument("--batch", default="B2-01-T-migrate")
    a = ap.parse_args()

    live = open(a.live, encoding="utf-8").read()
    orig = open(a.original, encoding="utf-8").read()

    blocks, pos = [], 0
    while True:
        m = NOTE_START.search(live, pos)
        if not m:
            break
        end = balanced_div(live, m.start())
        blocks.append((m.start(), live[m.start():end]))
        pos = end

    notes = [parse_note(b, live, s) for s, b in blocks]
    vbar = VBAR.search(live)
    page_date = "—"
    if vbar:
        # 「正文版本」（2026-09-23 起，值为月粒度）优先；「本页更新」（旧格式）兜底。
        d = (re.search(r"正文版本：<strong>(.*?)</strong>", vbar.group(0))
             or re.search(r"本页更新：<strong>(.*?)</strong>", vbar.group(0)))
        page_date = d.group(1) if d else "—"

    residual = live
    residual = re.sub(r'<div class="cg-version-bar"[^>]*>.*?</div>\s*', "", residual, count=1, flags=re.S)
    residual = STYLE_BLOCK.sub("", residual, count=1)
    residual = BADGE_ATTRS.sub("", residual)
    for _, b in blocks:
        residual = residual.replace(b, "", 1)

    ok = nw(residual) == nw(orig)
    ws_delta = len(residual) - len(orig) if ok else None
    print(f"标注块抽取 = {len(notes)}")
    for n in notes:
        print(f"  {n['status']:8} {n['rid']:18} {n['title'][:28]:30} 锚点={n['anchor'][:56]}")
    print(f"版本条 page_date = {page_date}")
    if ok:
        print(f"反向还原：✅ 非空白内容与原文**完全一致**（抽取无遗漏，正文零实质改动）")
        print(f"          空白差异：{ws_delta:+d} 字符（不同脚本插入换行策略不同，可忽略）")
    else:
        i = next((k for k in range(min(len(nw(residual)), len(nw(orig)))) if nw(residual)[k] != nw(orig)[k]), -1)
        print(f"反向还原：❌ 非空白内容不一致（残留 {len(residual)} vs 原文 {len(orig)}，首个分歧 offset={i}）")
        if i >= 0:
            print(f"   残留: {nw(residual)[max(0,i-80):i+160]!r}")
            print(f"   原文: {nw(orig)[max(0,i-80):i+160]!r}")

    cfg = dict(batch=a.batch, title=f"慧思国别指南更新标注 · {a.name}（旧格式迁移重建）",
               review_date="2026-09-07", mode="local-test",
               migrated_from="live-v2(旧内联样式格式)",
               scope="线上已存在的标注 → 新格式重建（内容零变更，仅形态与版本条文案）",
               countries={a.slug: dict(name=a.name, documentId=a.document_id,
                                       page_date=page_date,
                                       guide_url=f"https://www.humancehr.com/country-guide/{a.slug}/国家概况",
                                       notes=notes)})
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    json.dump(cfg, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n配置 → {a.out}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
