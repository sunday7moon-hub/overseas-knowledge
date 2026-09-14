#!/usr/bin/env python3
"""把「已发送」实测结果回灌到飞书多维表「客户触达邮件同步」。

输入：pull_sent_mail.py 产出的 JSON（默认 /tmp/sent_mails.json）
输出：写回 `推送时间`(text) + `触达状态`(select=已推送)

匹配规则（两级，缺一不可）：
  ① 收件人邮箱忽略大小写完全相等
  ② 邮件主题 NFKC 规范化后相等（统一全半角、｜→|、（）、，、：、去空白）
同一记录命中多封时取「时间最新」的一封。

默认 **dry-run 只打印计划**，确认无误后加 --write 才真正写表。

用法：
  python3 backfill_mail_status.py                    # 预览计划
  python3 backfill_mail_status.py --write            # 执行回灌
  python3 backfill_mail_status.py --write --only-rid recXXX   # 单条试写
  python3 backfill_mail_status.py --sent ./s.json --write

🔴 红线：发件箱里查不到发送记录的，一律保持「待推送」，不得臆造时间。
"""
import argparse
import collections
import datetime
import json
import os
import re
import subprocess
import sys
import unicodedata

CST = datetime.timezone(datetime.timedelta(hours=8))
DEFAULT_BASE = "MLXGbWKh7aAFJfs9RYNcwER0nMg"
DEFAULT_TABLE = "tblpm0IE8J7WiRtB"
LARK = "lark-cli"


def norm(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("｜", "|").replace("（", "(").replace("）", ")")
    s = s.replace("，", ",").replace("：", ":")
    return re.sub(r"[\s\u3000]+", "", s).strip().lower()


def fv(v):
    """飞书单元格值 → 纯文本。"""
    if v is None:
        return ""
    if isinstance(v, list):
        return "|".join((x.get("text") or x.get("name") or "") if isinstance(x, dict) else str(x)
                        for x in v)
    if isinstance(v, dict):
        return v.get("text") or v.get("name") or ""
    return str(v)


def lark_json(args_list):
    env = {**os.environ, "LARK_CLI_NO_PROXY": "1"}
    r = subprocess.run([LARK] + args_list, capture_output=True, text=True, env=env)
    raw = (r.stdout or "") + (r.stderr or "")
    m = re.search(r"\{.*\}", raw, re.S)
    return json.loads(m.group(0)) if m else {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sent", default="/tmp/sent_mails.json")
    ap.add_argument("--base", default=DEFAULT_BASE)
    ap.add_argument("--table", default=DEFAULT_TABLE)
    ap.add_argument("--write", action="store_true", help="不加则只预览")
    ap.add_argument("--only-rid", default="", help="只处理指定 record_id（试写用）")
    args = ap.parse_args()

    # ── 1) 读已发送 ──────────────────────────────
    if not os.path.exists(args.sent):
        raise SystemExit(f"❌ 找不到 {args.sent}，先跑 pull_sent_mail.py")
    sent = json.load(open(args.sent))
    for s in sent:
        s["dt"] = int(s["totime"]) / 1000 if s.get("totime") else 0
        s["email"] = (s.get("to") or "").strip().lower()
        s["nsubj"] = norm(s.get("subject"))
        s["tstr"] = (datetime.datetime.fromtimestamp(s["dt"], CST).strftime("%Y-%m-%d %H:%M")
                     if s["dt"] else "")
    sent.sort(key=lambda x: -x["dt"])
    by_email = collections.defaultdict(list)
    for s in sent:
        by_email[s["email"]].append(s)
    print(f"已发送 {len(sent)} 封｜唯一收件人 {len(by_email)}")

    # ── 2) 拉表 ─────────────────────────────────
    d = lark_json(["base", "+record-list", "--base-token", args.base,
                   "--table-id", args.table, "--limit", "500", "--format", "json", "--as", "user"])
    data = (d.get("data") or {})
    names, rows, rids = data.get("fields"), data.get("data"), data.get("record_id_list")
    if not names:
        raise SystemExit(f"❌ 读表失败：{json.dumps(d, ensure_ascii=False)[:300]}")
    print(f"表内 {len(rows)} 条记录")

    # ── 3) 匹配 ─────────────────────────────────
    plan, unmatched, loose = [], [], []
    for i, r in enumerate(rows):
        rec = dict(zip(names, r))
        email = fv(rec.get("邮箱")).strip().lower()
        subj = fv(rec.get("邮件主题"))
        rid = rids[i]
        if args.only_rid and rid != args.only_rid:
            continue
        if fv(rec.get("触达状态")) == "已推送":
            continue                                   # 幂等：已回灌的跳过
        cands = by_email.get(email, [])
        if not cands:
            unmatched.append((i + 1, email, subj))
            continue
        exact = [c for c in cands if c["nsubj"] == norm(subj)]
        pick = exact[0] if exact else None
        if pick is None:
            l = [c for c in cands if c["nsubj"] and
                 (c["nsubj"] in norm(subj) or norm(subj) in c["nsubj"])]
            if not l:
                unmatched.append((i + 1, email, subj))
                continue
            pick = l[0]
            loose.append((i + 1, email, pick["subject"]))
        plan.append({"idx": i + 1, "rid": rid, "email": email,
                     "push_time": pick["tstr"], "delivery": pick["delivery"],
                     "sent_subj": pick["subject"], "exact": bool(exact)})

    print(f"\n═══ 待回灌 {len(plan)} 条 ═══")
    for p in sorted(plan, key=lambda x: x["push_time"], reverse=True):
        print(f"{'✓' if p['exact'] else '~'} 表#{p['idx']:>2} {p['rid']}  {p['push_time']}  "
              f"{p['email'][:30]:<30} {p['delivery'] or '无回执'}")
    if loose:
        print("\n⚠️ 非严格命中（主题包含）:")
        for i, e, s in loose:
            print(f"   表#{i} {e} → {s[:40]}")
    print(f"\n未命中（保持待推送）{len(unmatched)} 条；其中邮箱在发件箱无记录的 "
          f"{sum(1 for _, _, _ in unmatched)} 条")

    if not args.write:
        print("\n（预览模式，未写表。确认无误后加 --write 执行）")
        return

    # ── 4) 写表 ─────────────────────────────────
    records = [{"record_id": p["rid"],
                "fields": {"触达状态": "已推送", "推送时间": p["push_time"]}} for p in plan]
    if not records:
        print("没有需要写入的记录。")
        return
    url = f"/open-apis/bitable/v1/apps/{args.base}/tables/{args.table}/records/batch_update"
    res = lark_json(["api", "POST", url, "--data",
                     json.dumps({"records": records}, ensure_ascii=False), "--as", "user"])
    if res.get("code") == 0:
        print(f"\n✅ 写入成功 {len(res['data']['records'])} 条")
    else:
        print("\n❌ 写入失败:", json.dumps(res, ensure_ascii=False)[:500])
        sys.exit(1)


if __name__ == "__main__":
    main()
