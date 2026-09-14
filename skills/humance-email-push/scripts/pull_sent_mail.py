#!/usr/bin/env python3
"""抓取腾讯企业邮箱「已发送」全量邮件（收件人 / 主题 / 精确发送时间 / 投递状态）。

为什么不用 API：飞书 mail 接口对当前授权账号不可用
（`mail user_mailboxes profile` → primary_email_address 为空、accessible_mailboxes 为 []），
所以走浏览器桥接（bridge，端口 9334）读页面。

前置：
  1) bridge 服务在跑：lsof -nP -iTCP:9334 -sTCP:LISTEN
  2) Chrome 里腾讯企业邮箱「已发送」页面处于打开状态（脚本自动从中取 sid）

用法（必须用带 websockets 的 venv 解释器）：
  python3 pull_sent_mail.py                        # 默认输出 /tmp/sent_mails.json
  python3 pull_sent_mail.py --out ./sent.json
  python3 pull_sent_mail.py --max-pages 5

产出：JSON 数组，字段 mailid / to / subject / totime(毫秒) / tstr(北京时间) /
      dateText / delivery（"邮件投递成功" 或空=无投递回执）。
"""
import argparse
import datetime
import json
import os
import re
import sys
import time

BRIDGE_SCRIPTS = "/Users/yoyo/.workbuddy/skills/baidu-ziyuan-collect/scripts"
sys.path.insert(0, BRIDGE_SCRIPTS)          # control.Bridge 复用已有实现
from control import Bridge  # noqa: E402

CST = datetime.timezone(datetime.timedelta(hours=8))

# 每行一次拿全四要素；显示名被截断，所以收件人必须取 @sh / td.tl[title]
GRAB = r"""
(() => {
  const fr = document.getElementById('mainFrame');
  if (!fr) return {err: 'no mainFrame'};
  let d; try { d = fr.contentDocument; } catch (e) { return {err: 'cross-origin: ' + e.message}; }
  if (!d) return {err: 'mainFrame contentDocument is null'};
  const rows = [];
  d.querySelectorAll('tr').forEach(tr => {
    const inp = tr.querySelector('input[name=mailid]');
    if (!inp) return;
    const tl = tr.querySelector('td.tl'), gu = tr.querySelector('td.gt u'),
          dt = tr.querySelector('td.dt'), ss = tr.querySelector('td.Ss');
    rows.push({
      mailid: inp.value,
      to: inp.getAttribute('sh') || (tl ? tl.getAttribute('title') : '') || '',
      subject: gu ? gu.innerText.trim() : '',
      totime: inp.getAttribute('totime'),
      dateText: dt ? dt.innerText.trim() : '',
      delivery: ss ? (ss.getAttribute('title') || '') : ''
    });
  });
  return {src: fr.src, rows: rows};
})()
"""


def find_sid(b: Bridge) -> str:
    """从已打开的标签页里取腾讯企业邮箱的 sid。"""
    for t in b.list_tabs():
        u = str(t.get("url") or "")
        if "exmail.qq.com" in u:
            m = re.search(r"[?&]sid=([^&]+)", u)
            if m:
                return m.group(1)
    raise SystemExit(
        "❌ 未找到腾讯企业邮箱标签页。\n"
        "   请在 Chrome 里打开 https://exmail.qq.com/ 并进入「已发送」，再重跑本脚本。"
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/tmp/sent_mails.json")
    ap.add_argument("--sid", default="", help="留空则自动从已开标签页探测")
    ap.add_argument("--folder-id", default="3", help="3 = 已发送（默认）")
    ap.add_argument("--max-pages", type=int, default=10)
    args = ap.parse_args()

    b = Bridge()
    p = b.ping()
    if not p.get("extension_connected"):
        raise SystemExit("❌ bridge 未连上扩展，检查 9334 端口与 Chrome 扩展")

    sid = args.sid or find_sid(b)
    print(f"sid = {sid}")

    all_rows, seen = [], set()
    for page in range(args.max_pages):
        url = (f"https://exmail.qq.com/cgi-bin/mail_list?sid={sid}"
               f"&folderid={args.folder_id}&page={page}&topmails=0")
        b.navigate(url)
        time.sleep(3.5)
        r = None
        for _ in range(6):                     # 页面被重定向回 frame_html，等 mainFrame 就绪
            r = b.evaluate(GRAB)
            if r and r.get("rows"):
                break
            time.sleep(2)
        rows = (r or {}).get("rows") or []
        if not rows:
            print(f"  page={page} 无数据（{((r or {}).get('err') or '空列表')}），停止")
            break
        fresh = [x for x in rows if x["mailid"] not in seen]
        for x in fresh:
            seen.add(x["mailid"])
        all_rows += fresh
        print(f"  page={page} 抓到 {len(rows)} 行｜新增 {len(fresh)}｜累计 {len(all_rows)}", flush=True)
        if len(rows) < 20:                      # 每页 25 条，<20 视为最后一页
            break

    for r in all_rows:
        r["tstr"] = (datetime.datetime.fromtimestamp(int(r["totime"]) / 1000, CST)
                     .strftime("%Y-%m-%d %H:%M")) if r.get("totime") else ""

    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    json.dump(all_rows, open(args.out, "w"), ensure_ascii=False, indent=1)

    ok = sum(1 for r in all_rows if r["delivery"])
    print(f"\n✅ 共 {len(all_rows)} 封 → {args.out}")
    print(f"   投递成功 {ok} 封｜无回执 {len(all_rows) - ok} 封")


if __name__ == "__main__":
    main()
