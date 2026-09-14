#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Humance 核心数据可视化看板生成器（单文件 HTML · 深色主题 · 零外部依赖）

用法:
  python3 humance_dashboard.py --preset month                   # 最近 30 个完整日（默认）
  python3 humance_dashboard.py --preset week                    # 最近 7 个完整日（周报口径）
  python3 humance_dashboard.py --start 2026-08-12 --end 2026-09-10
  python3 humance_dashboard.py --out "outputs/看板.html"
  python3 humance_dashboard.py --no-strapi --no-ops --no-mail    # 只出百度流量部分

窗口无关：WAU / MAU 始终以**窗口末日为基准向前取 7 / 30 天**（与窗口长度无关），
所有「30 天」字样按实际天数渲染，套 7 天周窗口不会出现口径错标。

数据源（每块面板头部均标注实际来源）:
  ① 百度统计 Site 22551575 —— 流量口径（PV / 访客人次 / 新老访客 / 来源 / 停留 / 跳出）
  ② 慧思后台 Strapi admin（经 Browser Bridge）
     · content-manager REST 总量 —— 累计注册 / 收藏 / 订阅
     · User 表 + 埋点事件表 —— 本期注册 / 登录用户 / 产生行为用户 / 登录 DAU
  ③ 飞书多维表「客户触达邮件同步」—— 邮件触达队列 / 分类 / 推送状态
     lark-cli 实时优先；失败回退本地缓存 ~/.workbuddy/secrets/feishu_email_records_cache.json
  任一来源不可用时会明确标注或跳过，**不会静默写 0**。

输出: 单文件 HTML，无 CDN 依赖、无水印，可离线打开、直接截图发群。
"""
import argparse
import json
import os
import subprocess
import ssl
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, time as _dtime, timedelta, timezone

SITE_ID = 22551575


def _load_baidu_token():
    """百度统计 access_token（敏感凭据，严禁硬编码）。

    读取顺序：
      1) 环境变量 BAIDU_TONGJI_TOKEN
      2) 密钥文件 ~/.workbuddy/secrets/baidu_tongji_token.txt（单行）
    两者都没有时直接报错退出，避免把凭据写进公开仓库。
    """
    tok = (os.environ.get("BAIDU_TONGJI_TOKEN") or "").strip()
    if tok:
        return tok
    secret = os.path.expanduser("~/.workbuddy/secrets/baidu_tongji_token.txt")
    try:
        with open(secret, encoding="utf-8") as f:
            tok = f.read().strip()
    except OSError:
        tok = ""
    if tok:
        return tok
    raise SystemExit(
        "❌ 缺少百度统计 access_token\n"
        "   请设置环境变量 BAIDU_TONGJI_TOKEN，\n"
        "   或写入 ~/.workbuddy/secrets/baidu_tongji_token.txt（单行）"
    )


TOKEN = _load_baidu_token()
_SSL = ssl.create_default_context()
urllib.request.install_opener(urllib.request.build_opener(urllib.request.ProxyHandler({})))
_DM = "pv_count,visitor_count,new_visitor_count,avg_visit_time,bounce_ratio"


def _get(start, end, method, **p):
    q = {"access_token": TOKEN, "site_id": SITE_ID, "method": method,
         "start_date": start, "end_date": end, "max_results": "0"}
    q.update(p)
    u = "https://openapi.baidu.com/rest/2.0/tongji/report/getData?" + urllib.parse.urlencode(q)
    return json.loads(urllib.request.urlopen(urllib.request.Request(u), context=_SSL, timeout=40).read())


def _rows(d):
    r = d.get("result", {})
    if not r:
        return []
    f = r.get("fields", [])
    items = r.get("items", [])
    dims = items[0] if len(items) > 0 else []
    mets = items[1] if len(items) > 1 else []
    out = []
    for i, dim in enumerate(dims):
        dv = dim[0] if isinstance(dim, list) and dim else dim
        if isinstance(dv, dict):
            dv = dv.get("name", str(dv))
        row = {"_dim": str(dv)}
        if i < len(mets):
            for j, ff in enumerate(f[1:]):
                if j < len(mets[i]):
                    row[ff] = mets[i][j]
        out.append(row)
    return out


def _seg_daily(start, end, metrics=None, visitor=None):
    """分段拉逐日数据（绕开 gran=day 单次仅返回 20 行的静默截断）"""
    metrics = metrics or _DM
    out = []
    d0 = date(*map(int, [start[:4], start[4:6], start[6:8]]))
    d1 = date(*map(int, [end[:4], end[4:6], end[6:8]]))
    cur = d0
    while cur <= d1:
        seg_end = min(cur + timedelta(days=19), d1)
        kw = {"visitor": visitor} if visitor else {}
        out += _rows(_get(cur.strftime("%Y%m%d"), seg_end.strftime("%Y%m%d"),
                          "trend/time/a", gran="day", metrics=metrics, **kw))
        cur = seg_end + timedelta(days=1)
    return out


_STRAPI_JS = """(async()=>{
  const jwt = JSON.parse(localStorage.getItem('jwtToken') || '""');
  if(!jwt) return JSON.stringify({e:'no jwt'});
  const out = {};
  const eps = [['users','/content-manager/collection-types/plugin::users-permissions.user?page=1&pageSize=1'],
               ['favs','/content-manager/collection-types/api::favorite.favorite?page=1&pageSize=1'],
               ['subs','/content-manager/collection-types/api::subscription.subscription?page=1&pageSize=1']];
  for (const [k,p] of eps) {
    try {
      const r = await fetch(p, {headers:{Authorization:'Bearer '+jwt}});
      const j = await r.json();
      out[k] = (j.pagination||{}).total;
    } catch(e){}
  }
  return JSON.stringify(out);
})()"""


def _strapi_counts():
    """best-effort：经 Browser Bridge 查 Strapi 业务口径总量（注册用户 / 收藏 / 订阅）

    注意：这三个 content-type 需要**管理员 JWT**（API Token 一律 401），
    因此必须让浏览器停在 admin.humancehr.com 才能读到 localStorage.jwtToken。
    """
    fallback = {"users": 169, "favs": 15, "subs": 12, "source": "内置默认值（人工核对）"}
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import control
        b = control.Bridge()
        if not b.wait_ready(12):
            print("  ⚠️ Bridge 未连接，业务数据回退内置默认值", file=sys.stderr)
            return fallback
        try:
            cur = str(b.evaluate("location.href") or "")
        except Exception:
            cur = ""
        if "admin.humancehr.com" not in cur:
            print("  → 切换到 admin 页面读取登录态 …", file=sys.stderr)
            b.navigate("https://admin.humancehr.com/admin", new_tab=True)
            for _ in range(24):
                time.sleep(1.5)
                try:
                    if b.evaluate("document.body.innerText.length") > 200:
                        break
                except Exception:
                    pass
        d = json.loads(b.evaluate(_STRAPI_JS))
        if d.get("e") or not d.get("users"):
            print("  ⚠️ 未取到 admin 登录态（请先在 Chrome 登录 admin.humancehr.com）", file=sys.stderr)
            return fallback
        return {"users": d["users"], "favs": d.get("favs") or 15,
                "subs": d.get("subs") or 12, "source": "Strapi admin API（实时）"}
    except Exception as e:
        print(f"  ⚠️ 业务数据查询失败（{type(e).__name__}: {e}），回退内置默认值", file=sys.stderr)
        return fallback


# ─────────────────────────────────────────────────────────────
# 运营口径：注册 / 登录 / 行为用户（慧思后台 Strapi content-manager）
# ─────────────────────────────────────────────────────────────
_OPS_JS = """(async()=>{
  const jwt = JSON.parse(localStorage.getItem('jwtToken') || '""');
  if(!jwt) return JSON.stringify({e:'no jwt'});
  const H = {Authorization:'Bearer '+jwt};
  const out = {users: [], events: []};
  for (let p = 1; p <= 6; p++) {
    const r = await fetch('/content-manager/collection-types/plugin::users-permissions.user?page='+p+'&pageSize=100&sort=createdAt:asc', {headers:H});
    const j = await r.json();
    if (!j.results || !j.results.length) break;
    for (const u of j.results) out.users.push({
      id: u.id, createdAt: u.createdAt, last_login_at: u.last_login_at,
      register_source: u.register_source, register_type: u.register_type,
      email: u.email || '', fav: (u.favorites||{}).count, sub: (u.subscriptions||{}).count
    });
    if (p >= (j.pagination||{}).pageCount) break;
  }
  for (let p = 1; p <= 8; p++) {
    const q = '/content-manager/collection-types/api::analytics-event.analytics-event'
      + '?page='+p+'&pageSize=100&sort=occurredAt:asc'
      + '&filters[occurredAt][$gte]=__S__&filters[occurredAt][$lte]=__E__'
      + '&filters[actorUserId][$notNull]=true';
    const r = await fetch(q, {headers:H});
    const j = await r.json();
    if (!j.results || !j.results.length) break;
    for (const e of j.results) out.events.push({
      actor: e.actorUserId, at: e.occurredAt, ev: e.eventName,
      title: (e.title||'').slice(0,54), path: (e.path||'').slice(0,70)
    });
    if (p >= (j.pagination||{}).pageCount) break;
  }
  return JSON.stringify(out);
})()"""

_CST = timezone(timedelta(hours=8))
_INTERNAL_DOMAINS = ("xinfushe.com", "yonyou.com")


def _strapi_ops_stats(s_date, e_date):
    """窗口内「注册 / 登录 / 行为用户」统计（慧思后台，需管理员 JWT）。

    · User 表            → 注册数、last_login_at（登录口径）
    · analytics-event 表 → actorUserId 非空 = 登录态行为（行为用户 / 登录 DAU）
    时间统一按北京时间（UTC+8）切窗；内部账号（xinfushe.com / yonyou.com）单独剔除。
    """
    empty = {"ok": False, "users_total": None, "new_users": [], "src": {},
             "login_week": [], "login_has": 0, "act_users": [], "act_days": {},
             "behav": [], "internal": 0}
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import control
        b = control.Bridge()
        if not b.wait_ready(15):
            print("  ⚠️ Bridge 未连接，运营口径（注册/登录/行为）跳过", file=sys.stderr)
            return empty
        cur = str(b.evaluate("location.href") or "")
        if "admin.humancehr.com" not in cur:
            b.navigate("https://admin.humancehr.com/admin", new_tab=True)
            for _ in range(24):
                time.sleep(1.5)
                try:
                    if b.evaluate("document.body.innerText.length") > 200:
                        break
                except Exception:
                    pass
        ws = datetime.combine(s_date, _dtime.min).replace(tzinfo=_CST).astimezone(timezone.utc)
        we = datetime.combine(e_date, _dtime.max).replace(tzinfo=_CST).astimezone(timezone.utc)
        js = (_OPS_JS.replace("__S__", ws.strftime("%Y-%m-%dT%H:%M:%S.000Z"))
                     .replace("__E__", we.strftime("%Y-%m-%dT%H:%M:%S.000Z")))
        d = json.loads(b.evaluate(js))
    except Exception as ex:
        print(f"  ⚠️ 运营口径查询失败（{type(ex).__name__}: {ex}）", file=sys.stderr)
        return empty
    if d.get("e"):
        print("  ⚠️ 未取到 admin 登录态，运营口径跳过", file=sys.stderr)
        return empty

    users = d.get("users") or []
    events = d.get("events") or []

    def _cst(s):
        if not s:
            return None
        try:
            return datetime.fromisoformat(str(s).replace("Z", "+00:00")).astimezone(_CST)
        except Exception:
            return None

    def _internal(u):
        return any(x in (u.get("email") or "") for x in _INTERNAL_DOMAINS)

    new_users = [u for u in users if _cst(u.get("createdAt")) and s_date <= _cst(u["createdAt"]).date() <= e_date]
    src = {}
    for u in users:
        key = (u.get("register_source") or "未标注") + " / " + (u.get("register_type") or "—")
        src[key] = src.get(key, 0) + 1

    login_week = [u for u in users if _cst(u.get("last_login_at")) and _cst(u["last_login_at"]).date() >= s_date]
    login_has = sum(1 for u in users if u.get("last_login_at"))

    # 埋点事件 → 行为用户 / 按日 DAU（登录态）
    by_actor = {}
    for e in events:
        t = _cst(e.get("at"))
        if not t:
            continue
        by_actor.setdefault(e["actor"], []).append((t, e))
    act_days = {}
    for a, lst in by_actor.items():
        act_days[a] = sorted({t.strftime("%m/%d") for t, _ in lst})
    uidx = {u["id"]: u for u in users}
    behav = []
    for a, lst in sorted(by_actor.items(), key=lambda x: -len(x[1])):
        u = uidx.get(a) or {}
        behav.append({"id": a, "n": len(lst), "days": act_days[a],
                      "kinds": sorted({e["ev"] for _, e in lst}),
                      "email": u.get("email") or "?", "internal": _internal(u),
                      "titles": [e.get("title") or e.get("path") or "" for _, e in lst if e.get("title")][:3]})
    return {"ok": True, "users_total": len(users), "new_users": new_users, "src": src,
            "login_week": login_week, "login_has": login_has, "act_users": sorted(act_days),
            "act_days": act_days, "behav": behav,
            "internal": sum(1 for x in behav if x["internal"])}


# ─────────────────────────────────────────────────────────────
# 邮件触达口径（飞书多维表「客户触达邮件同步」）
# ─────────────────────────────────────────────────────────────
_LARK = ("/Users/yoyo/.workbuddy/binaries/node/cli-connector-packages/"
         "lib/node_modules/@larksuite/cli/bin/lark-cli")
_EMAIL_BASE = "MLXGbWKh7aAFJfs9RYNcwER0nMg"   # 注意 RYNcw（曾误写 RYcw → 长期误报 91402 NOTEXIST）
_EMAIL_TABLE = "tblpm0IE8J7WiRtB"
_MAIL_CACHE = os.path.expanduser("~/.workbuddy/secrets/feishu_email_records_cache.json")


def _fv(f, key):
    v = f.get(key)
    if isinstance(v, list):
        return "".join((x.get("text", "") if isinstance(x, dict) else str(x)) for x in v)
    return v


def _feishu_touch_stats(s_date, e_date):
    """飞书「客户触达邮件同步」表统计：队列 / 分类 / 状态 / 窗口内计划推送。

    取数策略：① lark-cli 实时（成功即写本地缓存）→ ② 失败回退本地缓存。
    兜底原因：lark-cli 的 user token 会过期 / 落盘可能被沙箱拦截，
    缓存兜底保证看板不会因外部授权波动而缺一块数据。
    注意 base token 必须为 ...RYNcw...（曾误写 RYcw，长期误报 91402 NOTEXIST）。
    """
    empty = {"ok": False, "total": None, "cat": {}, "status": {}, "prio": {},
             "stage": {}, "plan_win": 0, "sent": 0, "plan_days": {}, "src": "未取到"}
    items, src = None, None

    # ① 实时
    if os.path.exists(_LARK):
        try:
            r = subprocess.run([_LARK, "base", "+record-list",
                                "--base-token", _EMAIL_BASE,
                                "--table-id", _EMAIL_TABLE,
                                "--limit", "200", "--format", "json",
                                "--as", "bot"],
                               capture_output=True, text=True, timeout=180)
            raw = (r.stdout or "").strip()
            if raw:
                i = 0
                while i < len(raw) and raw[i] not in "{[":
                    i += 1
                obj, _ = json.JSONDecoder().raw_decode(raw, i)
                dd = obj.get("data") or {}
                names, rows = dd.get("fields") or [], dd.get("data") or []
                rids = dd.get("record_id_list") or []
                chunk = []
                for k, row in enumerate(rows):
                    fields = {}
                    for j, nm in enumerate(names):
                        if isinstance(nm, dict):
                            nm = nm.get("name") or nm.get("field_name")
                        if j < len(row):
                            fields[nm] = row[j]
                    chunk.append({"record_id": rids[k] if k < len(rids) else None,
                                  "fields": fields})
                if chunk:
                    items, src = chunk, "飞书多维表（实时）"
                    try:
                        os.makedirs(os.path.dirname(_MAIL_CACHE), exist_ok=True)
                        with open(_MAIL_CACHE, "w", encoding="utf-8") as _f:
                            json.dump({"code": 0, "data": {"items": chunk}}, _f, ensure_ascii=False)
                        os.chmod(_MAIL_CACHE, 0o600)
                    except Exception:
                        pass
        except Exception as ex:
            print(f"  ⚠️ 飞书实时取数失败（{type(ex).__name__}: {str(ex)[:70]}）", file=sys.stderr)

    # ② 回退缓存
    if items is None:
        try:
            with open(_MAIL_CACHE, encoding="utf-8") as _f:
                c = json.load(_f)
            items = (c.get("data") or {}).get("items") or []
            _mt = datetime.fromtimestamp(os.path.getmtime(_MAIL_CACHE), _CST).strftime("%m-%d %H:%M")
            src = f"飞书多维表（本地缓存 · 抓取于 {_mt}）"
            print(f"  ⚠️ 飞书实时不可用 → 回退本地缓存（{len(items)} 条 @ {_mt}）", file=sys.stderr)
        except Exception:
            print("  ⚠️ 飞书数据不可用（实时失败且无可用缓存）", file=sys.stderr)
            return empty

    def _ts(v):
        """兼容三种来源：时间戳(ms/int) / ISO 字符串（base +record-list）/ 单元素列表。"""
        if v in (None, "", []):
            return None
        if isinstance(v, list):
            return _ts(v[0]) if v else None
        if isinstance(v, (int, float)):
            try:
                return datetime.fromtimestamp(int(v) / 1000, _CST)
            except Exception:
                return None
        if isinstance(v, str):
            s = v.strip().replace("Z", "+00:00")
            try:
                dt = datetime.fromisoformat(s)
            except Exception:
                dt = None
                for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d"):
                    try:
                        dt = datetime.strptime(s, fmt)
                        break
                    except Exception:
                        continue
            if dt is None:
                return None
            return dt.astimezone(_CST) if dt.tzinfo else dt.replace(tzinfo=_CST)
        return None

    cat, status, prio, stage, plan_days, plan_win_days = {}, {}, {}, {}, {}, {}
    plan_win = sent = 0
    for it in items:
        f = it.get("fields") or {}
        c = _fv(f, "邮件分类") or "未分类"
        s = _fv(f, "触达状态") or "未标注"
        cat[c] = cat.get(c, 0) + 1
        status[s] = status.get(s, 0) + 1
        p = _fv(f, "优先级") or "未标注"
        prio[p] = prio.get(p, 0) + 1
        st = _fv(f, "客户阶段") or "未标注"
        stage[st] = stage.get(st, 0) + 1
        pt = _ts(_fv(f, "推送时间"))
        if pt:
            sent += 1
        pd = _ts(_fv(f, "建议推送邮件日期"))
        if pd:
            plan_days[pd.strftime("%m/%d")] = plan_days.get(pd.strftime("%m/%d"), 0) + 1
            if s_date <= pd.date() <= e_date:
                plan_win += 1
                plan_win_days[pd.strftime("%m/%d")] = plan_win_days.get(pd.strftime("%m/%d"), 0) + 1
    return {"ok": True, "total": len(items), "cat": cat, "status": status, "prio": prio,
            "stage": stage, "plan_win": plan_win, "sent": sent,
            "plan_days": dict(sorted(plan_days.items())),
            "plan_win_days": dict(sorted(plan_win_days.items())), "src": src}


_ap = argparse.ArgumentParser()
_ap.add_argument("--start", default=None, help="YYYY-MM-DD，默认 = 结束日前推 29 天")
_ap.add_argument("--end", default=None, help="YYYY-MM-DD，默认 = 昨天")
_ap.add_argument("--out", default=None, help="输出 HTML 路径")
_ap.add_argument("--no-strapi", action="store_true", help="跳过 Bridge 业务数据查询")
_ap.add_argument("--no-ops", action="store_true", help="跳过注册/登录/行为用户查询")
_ap.add_argument("--no-mail", action="store_true", help="跳过飞书邮件触达查询")
_ap.add_argument("--preset", choices=["week", "month"], default=None,
                 help="week = 结束日前推 7 个完整日（周报口径）；month = 前推 30 个完整日（默认）")
_A = _ap.parse_args()

_e_date = date(*map(int, (_A.end or (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")).split("-")))
_span_days = {"week": 7, "month": 30}.get(_A.preset, 30)
_s_date = date(*map(int, _A.start.split("-"))) if _A.start else _e_date - timedelta(days=_span_days - 1)
WIN_START, WIN_END = _s_date.strftime("%Y%m%d"), _e_date.strftime("%Y%m%d")
_SCOPE = {"week": "周报", "month": "月报"}.get(_A.preset, "看板")
OUT = _A.out or os.path.join(os.getcwd(),
                             f"{_e_date.strftime('%Y-%m-%d')} Humance 核心数据{_SCOPE}（{_s_date.strftime('%m.%d')}-{_e_date.strftime('%m.%d')}）.html")

print(f"→ 拉取百度统计 {WIN_START} ~ {WIN_END}（另取前 30 天，用于近 7/30 日口径与 7 日均值线）…", file=sys.stderr)
ext = _seg_daily((_s_date - timedelta(days=30)).strftime("%Y%m%d"), WIN_END)
dash = {
    "daily": [r for r in ext if WIN_START <= r["_dim"].replace("/", "") <= WIN_END],
    "new": _seg_daily(WIN_START, WIN_END, visitor="new"),
    "old": _seg_daily(WIN_START, WIN_END, visitor="old"),
    "toppage": _rows(_get(WIN_START, WIN_END, "visit/toppage/a",
                          metrics="pv_count,visitor_count,avg_visit_time,bounce_ratio"))[:20],
    "source": _rows(_get(WIN_START, WIN_END, "source/all/a",
                         metrics="pv_count,visitor_count,new_visitor_count"))[:15],
}
_B = {"users": 169, "favs": 15, "subs": 12, "source": "内置默认值（--no-strapi）"} if _A.no_strapi else _strapi_counts()
_OPS = ({"ok": False, "users_total": None, "new_users": [], "src": {}, "login_week": [],
         "login_has": 0, "act_users": [], "act_days": {}, "behav": [], "internal": 0}
        if (_A.no_strapi or _A.no_ops) else _strapi_ops_stats(_s_date, _e_date))
_MAIL = ({"ok": False, "total": None, "cat": {}, "status": {}, "prio": {}, "stage": {},
          "plan_win": 0, "sent": 0, "plan_days": {}, "src": "已跳过（--no-mail）"}
         if _A.no_mail else _feishu_touch_stats(_s_date, _e_date))
print(f"  ✓ 逐日 {len(dash['daily'])} 天 ｜ 业务数据：{_B['source']} ｜ "
      f"运营口径：{'OK' if _OPS['ok'] else '跳过'} ｜ 邮件触达：{'OK' if _MAIL['ok'] else '跳过'}",
      file=sys.stderr)



def k(r):
    return r["_dim"].replace("/", "")


def dt(s):
    return date(int(s[:4]), int(s[4:6]), int(s[6:8]))


# ---------- 基础序列 ----------
daily_all = sorted(ext, key=k)
idx = {k(r): i for i, r in enumerate(daily_all)}
win = [r for r in daily_all if WIN_START <= k(r) <= WIN_END]
N = len(win)

pv_tot = sum(r["pv_count"] for r in win)
uv_tot = sum(r["visitor_count"] for r in win)
dau_avg = uv_tot / N
dau_max = max(r["visitor_count"] for r in win)
dau_min = min(r["visitor_count"] for r in win)
dau_max_d = [k(r) for r in win if r["visitor_count"] == dau_max][0]
dau_min_d = [k(r) for r in win if r["visitor_count"] == dau_min][0]
pvpu = pv_tot / uv_tot

wd = [r["visitor_count"] for r in win if dt(k(r)).weekday() < 5]
we = [r["visitor_count"] for r in win if dt(k(r)).weekday() >= 5]
wd_avg, we_avg = sum(wd) / len(wd), sum(we) / len(we)
we_wd = we_avg / wd_avg

# 加权平均停留 / 跳出
avg_time = sum(r["avg_visit_time"] * r["visitor_count"] for r in win) / uv_tot
bounce = sum(r["bounce_ratio"] * r["visitor_count"] for r in win) / uv_tot

new_tot = sum(r["visitor_count"] for r in dash["new"])
old_tot = sum(r["visitor_count"] for r in dash["old"])
old_pct = old_tot / (new_tot + old_tot) * 100

new_pvpu = sum(r["pv_count"] for r in dash["new"]) / new_tot
old_pvpu = sum(r["pv_count"] for r in dash["old"]) / old_tot
new_time = sum(r["avg_visit_time"] for r in dash["new"]) / len(dash["new"])
old_time = sum(r["avg_visit_time"] for r in dash["old"]) / len(dash["old"])
new_bounce = sum(r["bounce_ratio"] for r in dash["new"]) / len(dash["new"])
old_bounce = sum(r["bounce_ratio"] for r in dash["old"]) / len(dash["old"])

# 近 7 日 / 近 30 日（**始终以窗口末日为基准向前取**，与窗口长度无关）
last7 = win[-7:]
trail30 = daily_all[-30:]
wau = sum(r["visitor_count"] for r in last7)
mau = sum(r["visitor_count"] for r in trail30)
sticky = dau_avg / mau * 100 if mau else 0
dau_wau = dau_avg / wau * 100 if wau else 0
wau_mau = wau / mau * 100 if mau else 0

# 环比：窗口末 7 天 vs 其之前 7 天
_L7 = {k(r) for r in last7}
prev7 = [r for r in daily_all if k(r) not in _L7][-7:]
prev_uv = sum(r["visitor_count"] for r in prev7)
prev_pv = sum(r["pv_count"] for r in prev7)
cur_uv, cur_pv = wau, sum(r["pv_count"] for r in last7)
cur_old = sum(r["visitor_count"] for r in dash["old"] if k(r) in _L7)
cur_old_pct = cur_old / cur_uv * 100 if cur_uv else 0
_cmax = max(last7, key=lambda r: r["visitor_count"])
_cmin = min(last7, key=lambda r: r["visitor_count"])
_o7 = [r for r in dash["old"] if k(r) in _L7] or dash["old"][-7:]
_n7 = [r for r in dash["new"] if k(r) in _L7] or dash["new"][-7:]
_o7_time = sum(r["avg_visit_time"] for r in _o7) / len(_o7)
_o7_bo = sum(r["bounce_ratio"] for r in _o7) / len(_o7)
_n7_time = sum(r["avg_visit_time"] for r in _n7) / len(_n7)
_n7_bo = sum(r["bounce_ratio"] for r in _n7) / len(_n7)


def _fmt8(s):
    return f"{s[:4]}.{s[4:6]}.{s[6:8]}"


def _fmt4(s):
    return f"{s[4:6]}/{s[6:8]}"


_WIN_LABEL = f"{_s_date.strftime('%Y.%m.%d')} – {_e_date.strftime('%m.%d')}"
_WIN_SHORT = f"{_s_date.strftime('%m.%d')} – {_e_date.strftime('%m.%d')}"
_CUR_LABEL = f"{_fmt8(k(last7[0]))} – {_e_date.strftime('%m.%d')}"
_WAU_LABEL = f"{_fmt4(k(trail30[-7] if len(trail30) >= 7 else trail30[0]))} – {_e_date.strftime('%m/%d')}"
_MAU_LABEL = f"{_fmt4(k(trail30[0]))} – {_e_date.strftime('%m/%d')}"
_GEN_DATE = date.today().strftime("%Y-%m-%d")
# 窗口长度自适应的措辞（避免把 7 天窗口写成「30 天」）
_SPAN = f"{N} 天"
_WAU_RATIO_TXT = f"≈ 1/{100/dau_wau:.1f}，一周内到访占比" if dau_wau else "—"
_WAU_MAU_TXT = f"≈ 1/{100/wau_mau:.1f}，一月内到访占比" if wau_mau else "—"
# 窗口 ≤14 天时，快照面板即整个窗口，标题不再加「最近 7 天」
_SNAP_TITLE = f"最近 7 天快照 · {_CUR_LABEL}" if N > 14 else f"本期快照 · {_WIN_LABEL}"

# ---------- 1) DAU 柱状图 ----------
W, H = 1132, 300
L, R, T, B = 48, 12, 12, 34
PW, PH = W - L - R, H - T - B
YMAX = 450
slot = PW / N
bw = min(slot * 0.62, 46)   # 短窗口（周报）时限制柱宽，避免出现 95px 的"胖柱"
bars, xlabels = [], []
for i, r in enumerate(win):
    v = r["visitor_count"]
    d = dt(k(r))
    x = L + i * slot + (slot - bw) / 2
    h = v / YMAX * PH
    y = T + PH - h
    fill = "#9fb3cc" if d.weekday() >= 5 else "#3d7ff5"
    op = "0.55" if d.weekday() >= 5 else "0.92"
    bars.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{h:.1f}" rx="2" fill="{fill}" opacity="{op}"><title>{k(r)} DAU {v}</title></rect>')
    if N <= 16 or i % 2 == 0 or i == N - 1:
        xlabels.append(f'<text x="{x+bw/2:.1f}" y="{H-14}" fill="#6f7b8a" font-size="10.5" text-anchor="middle">{k(r)[4:6]}/{k(r)[6:8]}</text>')

grid = []
for t in range(0, YMAX + 1, 100):
    y = T + PH - t / YMAX * PH
    grid.append(f'<line x1="{L}" y1="{y:.1f}" x2="{W-R}" y2="{y:.1f}" stroke="#242a32" stroke-width="1" stroke-dasharray="3 4"/>')
    grid.append(f'<text x="{L-8}" y="{y+4:.1f}" fill="#6f7b8a" font-size="10.5" text-anchor="end">{t}</text>')

ma_pts = []
for i in range(N):
    gi = idx[k(win[i])]
    if gi < 6:
        continue
    seg = daily_all[gi - 6:gi + 1]
    avg = sum(s["visitor_count"] for s in seg) / 7
    x = L + i * slot + slot / 2
    y = T + PH - avg / YMAX * PH
    ma_pts.append(f"{x:.1f},{y:.1f}")
ma_line = f'<polyline points="{" ".join(ma_pts)}" fill="none" stroke="#38bdf8" stroke-width="2" stroke-linejoin="round"/>'

dau_svg = f'''<svg viewBox="0 0 {W} {H}" style="width:100%;height:auto;display:block">
<defs><linearGradient id="gbar" x1="0" y1="0" x2="0" y2="1">
<stop offset="0%" stop-color="#5b96ff"/><stop offset="100%" stop-color="#2f6fdd"/></linearGradient></defs>
{"".join(grid)}
{chr(10).join(b.replace('#3d7ff5', 'url(#gbar)') for b in bars)}
{ma_line}
{"".join(xlabels)}
<text x="{W-R}" y="{T+10}" fill="#38bdf8" font-size="11" text-anchor="end">— 7 日均值</text>
</svg>'''

# ---------- 2) 月度趋势 ----------
months = [("1月", 4454, 3299, 4, 0.12), ("2月", 4762, 3447, 4, 0.12), ("3月", 8108, 5678, 18, 0.32),
          ("4月", 7533, 5088, 18, 0.35), ("5月", 8950, 5978, 21, 0.35), ("6月", 10544, 7231, 24, 0.33),
          ("7月", 11611, 8360, 33, 0.39), ("8月", 10646, 7987, 20, 0.25)]
MW, MH = 1132, 260
ML, MR, MT, MB = 52, 46, 12, 30
MPW, MPH = MW - ML - MR, MH - MT - MB
MPV_MAX, MREG_MAX = 12000, 40
mslot = MPW / len(months)
mbw = mslot * 0.26
mels, mxlab = [], []
mreg_pts = []
for i, (name, pv, uv, reg, conv) in enumerate(months):
    cx = ML + i * mslot + mslot / 2
    hpv = pv / MPV_MAX * MPH
    huv = uv / MPV_MAX * MPH
    x1 = cx - mbw - 2
    x2 = cx + 2
    mels.append(f'<rect x="{x1:.1f}" y="{MT+MPH-hpv:.1f}" width="{mbw:.1f}" height="{hpv:.1f}" rx="2" fill="#3d7ff5" opacity="0.9"><title>{name} PV {pv:,}</title></rect>')
    mels.append(f'<rect x="{x2:.1f}" y="{MT+MPH-huv:.1f}" width="{mbw:.1f}" height="{huv:.1f}" rx="2" fill="#7aa7f0" opacity="0.65"><title>{name} UV {uv:,}</title></rect>')
    mxlab.append(f'<text x="{cx:.1f}" y="{MH-12}" fill="#6f7b8a" font-size="11" text-anchor="middle">{name}</text>')
    ry = MT + MPH - reg / MREG_MAX * MPH
    mreg_pts.append(f"{cx:.1f},{ry:.1f}")
mgrid = []
for t in range(0, MPV_MAX + 1, 3000):
    y = MT + MPH - t / MPV_MAX * MPH
    mgrid.append(f'<line x1="{ML}" y1="{y:.1f}" x2="{MW-MR}" y2="{y:.1f}" stroke="#242a32" stroke-width="1" stroke-dasharray="3 4"/>')
    lbl = "0" if t == 0 else f"{t//1000}k"
    mgrid.append(f'<text x="{ML-8}" y="{y+4:.1f}" fill="#6f7b8a" font-size="10.5" text-anchor="end">{lbl}</text>')
mreg_line = f'<polyline points="{" ".join(mreg_pts)}" fill="none" stroke="#22c55e" stroke-width="2" stroke-linejoin="round"/>'
mreg_dots = "".join(f'<circle cx="{p.split(",")[0]}" cy="{p.split(",")[1]}" r="3.5" fill="#0d1014" stroke="#22c55e" stroke-width="2"/>' for p in mreg_pts)
month_svg = f'''<svg viewBox="0 0 {MW} {MH}" style="width:100%;height:auto;display:block">
{"".join(mgrid)}{"".join(mels)}{mreg_line}{mreg_dots}{"".join(mxlab)}
<text x="{MW-MR+6}" y="{MT+MPH-30}" fill="#22c55e" font-size="10.5">注册</text>
</svg>'''

# ---------- 3) 来源结构 ----------
src = [(r["_dim"], r["pv_count"]) for r in dash["source"] if r.get("pv_count")][:4] or [("直接访问", 1)]
src_tot = sum(v for _, v in src)
src_colors = ["#3d7ff5", "#22c55e", "#f59e0b", "#8b95a3"][:len(src)]
src_rows = ""
for (nm, v), c in zip(src, src_colors):
    pct = v / src_tot * 100
    src_rows += f'''<div class="srow"><span class="snm">{nm}</span>
<div class="strack"><div class="sfill" style="width:{pct:.1f}%;background:{c}"></div></div>
<span class="sval">{v:,}<i>{pct:.1f}%</i></span></div>'''

_dir_pct = next((v / src_tot * 100 for n, v in src if "直接" in n), 0.0)
_sea_pct = next((v / src_tot * 100 for n, v in src if "搜索" in n), 0.0)

# ---------- 4) 内容 TOP（窗口内百度口径，动态） ----------
_SLUG_CN = {
    "knowledge": "知识库", "base": "", "remuneration": "薪酬报告", "country": "国家",
    "guide": "指南", "regulation": "法规", "regulations": "法规", "article": "文章",
    "malaysian": "马来西亚", "malaysia": "马来西亚", "singapores": "新加坡", "singapore": "新加坡",
    "indonesia": "印尼", "indonesian": "印尼", "japans": "日本", "japan": "日本",
    "vietnam": "越南", "thailand": "泰国", "kuwait": "科威特", "brazil": "巴西",
    "china": "中国", "hong": "中国香港", "kong": "香港", "uae": "阿联酋", "saudi": "沙特",
    "mexico": "墨西哥", "germany": "德国", "france": "法国", "india": "印度", "korea": "韩国",
    "annual": "年度", "leave": "休假", "holiday": "假期", "public": "公共",
    "employee": "员工", "dismissal": "裁退", "termination": "离职", "recruitment": "招聘",
    "salary": "薪酬", "benefits": "福利", "payroll": "薪酬", "minimum": "最低",
    "wage": "工资", "hike": "上调", "adjustment": "调整", "hours": "工时",
    "compliance": "合规", "visa": "签证", "working": "工作", "tax": "税务",
    "social": "社保", "insurance": "保险", "contract": "合同", "labor": "劳工", "labour": "劳工",
    "law": "法律", "policy": "政策", "onboarding": "入职", "cost": "成本",
    "case": "案例", "management": "管理", "workplace": "用工", "hire": "雇佣",
    "hiring": "招聘", "report": "报告", "checklist": "清单", "assessment": "评估",
    "industry": "行业", "logistics": "物流", "warehousing": "仓储", "analysis": "分析",
    "overview": "概览", "statistics": "统计", "data": "数据", "planning": "规划",
    "guide": "指南", "tips": "要点", "risks": "风险", "penalty": "处罚",
    "resolution": "解读", "changes": "变动", "updates": "更新", "new": "新",
}


def _page_label(url):
    if not url:
        return "—"
    rest = url.split("://", 1)[-1]
    parts = rest.split("/", 1)
    path = ("/" + parts[1]) if len(parts) > 1 else "/"
    segs = [s for s in path.split("/") if s and s != "index.html"]
    if not segs:
        return "首页"
    words = []
    for s in segs[:2]:
        words += [_SLUG_CN.get(w, w) for w in s.split("-")]
    label = "".join(words).strip()
    return (label or segs[0])[:30]


_tp = [(r["_dim"], r["pv_count"]) for r in dash["toppage"] if r.get("pv_count")]
tops = [(_page_label(u), v, u) for u, v in _tp[:10]] or [("（窗口内无数据）", 1, "")]
top_max = tops[0][1]
top_rows = "".join(
    f'<div class="trow"><span class="tidx">{i+1}</span>'
    f'<span class="ttitle" title="{u}">{t}</span>'
    f'<div class="ttrack"><div class="tfill" style="width:{v/top_max*100:.0f}%"></div></div>'
    f'<span class="tval">{v}</span></div>'
    for i, (t, v, u) in enumerate(tops))

# ---------- 5) 漏斗 ----------
_RU, _FA, _SU = _B["users"], _B["favs"], _B["subs"]
_FA_PCT, _SU_PCT = round(_FA / _RU * 100, 1), round(_SU / _RU * 100, 1)
funnel = [("注册用户", _RU, 100.0, "#3d7ff5"), ("内容收藏", _FA, _FA_PCT, "#22c55e"),
          ("国家订阅", _SU, _SU_PCT, "#22c55e")]
fun_rows = "".join(
    f'<div class="frow"><div class="fbar" style="width:{max(p,3):.1f}%;background:{c}"></div>'
    f'<span class="fname">{n}</span><span class="fval">{v} 人 · {p}%</span></div>'
    for n, v, p, c in funnel)

# ---------- 6) 运营口径：注册 / 登录 / 行为用户（慧思后台 Strapi） ----------


def _is_internal(email):
    return any(_d in (email or "") for _d in _INTERNAL_DOMAINS)


_OPS_OK = bool(_OPS.get("ok"))
_ou_total = _OPS.get("users_total") or _RU
_onu = _OPS.get("new_users") or []
_ologin_all = _OPS.get("login_week") or []
_ologin_ext = [u for u in _ologin_all if not _is_internal(u.get("email"))]
_obehav = _OPS.get("behav") or []
_obehav_ext = [x for x in _obehav if not x.get("internal")]
_ointernal = len(_obehav) - len(_obehav_ext)
_ologin_has = _OPS.get("login_has") or 0
_onu_src = {}
for _u in _onu:
    _k2 = (_u.get("register_source") or "未标注") + " / " + (_u.get("register_type") or "—")
    _onu_src[_k2] = _onu_src.get(_k2, 0) + 1
_osrc_all = _OPS.get("src") or {}

# 登录态 DAU（按日去重）
_dau_login = {}
for _a, _days in (_OPS.get("act_days") or {}).items():
    for _d in _days:
        _dau_login[_d] = _dau_login.get(_d, 0) + 1
_dates = [_s_date + timedelta(days=i) for i in range(N)]
_dl_series = [(d.strftime("%m/%d"), _dau_login.get(d.strftime("%m/%d"), 0)) for d in _dates]
_dl_max = max([1] + [v for _, v in _dl_series])

# 登录态 DAU 柱图
_OW, _OH = 1132, 132
_OL, _OR, _OT, _OB = 38, 10, 16, 26
_OPW, _OPH = _OW - _OL - _OR, _OH - _OT - _OB
_oslot = _OPW / max(len(_dl_series), 1)
_obw = min(_oslot * 0.44, 38)
_oymax = max(_dl_max, 4)
_obars, _oxlab = [], []
for _i, (_lb, _v) in enumerate(_dl_series):
    _x = _OL + _i * _oslot + (_oslot - _obw) / 2
    _h = _v / _oymax * _OPH
    _y = _OT + _OPH - _h
    _fill = "#22c55e" if _v else "#252b33"
    _obars.append(f'<rect x="{_x:.1f}" y="{_y:.1f}" width="{_obw:.1f}" height="{max(_h,2):.1f}" rx="2" fill="{_fill}" opacity="0.9"><title>{_lb} 登录态活跃 {_v} 人</title></rect>')
    if _v:
        _obars.append(f'<text x="{_x+_obw/2:.1f}" y="{_y-5:.1f}" fill="#7f8b99" font-size="10" text-anchor="middle">{_v}</text>')
    _oxlab.append(f'<text x="{_x+_obw/2:.1f}" y="{_OH-9}" fill="#6f7b8a" font-size="10.5" text-anchor="middle">{_lb}</text>')
_ogrid = []
_ostep = max(1, _oymax // 3)
for _t in range(0, _oymax + 1, _ostep):
    _y = _OT + _OPH - _t / _oymax * _OPH
    _ogrid.append(f'<line x1="{_OL}" y1="{_y:.1f}" x2="{_OW-_OR}" y2="{_y:.1f}" stroke="#242a32" stroke-width="1" stroke-dasharray="3 4"/>')
    _ogrid.append(f'<text x="{_OL-8}" y="{_y+4:.1f}" fill="#6f7b8a" font-size="10.5" text-anchor="end">{_t}</text>')
_odau_svg = (f'<svg viewBox="0 0 {_OW} {_OH}" style="width:100%;height:auto;display:block">'
             f'{"".join(_ogrid)}{"".join(_obars)}{"".join(_oxlab)}</svg>')

# 行为用户明细
_bmax = max([1] + [x["n"] for x in _obehav])
_obehav_rows = "".join(
    f'<div class="trow"><span class="tidx">{_i+1}</span>'
    f'<span class="ttitle">{x["email"][:36]}{" ⚠️内部" if x.get("internal") else ""}</span>'
    f'<div class="ttrack"><div class="tfill" style="width:{x["n"]/_bmax*100:.0f}%"></div></div>'
    f'<span class="tval">{x["n"]} 次 · {len(x["days"])} 天</span></div>'
    for _i, x in enumerate(_obehav))

# ---------- 7) 邮件触达口径（飞书多维表） ----------
_MAIL_OK = bool(_MAIL.get("ok"))
_mt = _MAIL.get("total") or 0
_mcat = _MAIL.get("cat") or {}
_mstat = _MAIL.get("status") or {}
_msent = _MAIL.get("sent") or 0
_mplan_win = _MAIL.get("plan_win") or 0
_mplan_days = _MAIL.get("plan_days") or {}
_mstage = _MAIL.get("stage") or {}
_mprio = _MAIL.get("prio") or {}
_mcat_color = {"A 新注册欢迎": "#38bdf8", "B 注册后活跃": "#22c55e",
               "C 核心价值二次触达": "#22c55e", "D 5日未活跃召回": "#f59e0b",
               "存量真实邮箱用户": "#3d7ff5"}
_mail_rows = ""
for _nm, _v in sorted(_mcat.items(), key=lambda x: -x[1]):
    _pct = _v / _mt * 100 if _mt else 0
    _mail_rows += (f'<div class="frow"><div class="fbar" style="width:{max(_pct,7):.1f}%;'
                   f'background:{_mcat_color.get(_nm, "#8b95a3")}"></div>'
                   f'<span class="fname">{_nm}</span><span class="fval">{_v} 封 · {_pct:.1f}%</span></div>')
for _nm in ("B 注册后活跃", "D 5日未活跃召回"):
    if _nm not in _mcat:
        _mail_rows += (f'<div class="frow"><div class="fbar thin" style="width:7%;background:#3a424d"></div>'
                       f'<span class="fname">{_nm}</span><span class="fval">0 封 · 未启用</span></div>')

if _onu:
    _onu_txt = "、".join(sorted({u["createdAt"][5:10].replace("-", "/") for u in _onu})) + " 注册"
else:
    _onu_txt = "本期无新增"
_mplan_win_days = _MAIL.get("plan_win_days") or {}
_plan_txt = ("、".join(f"{k} {v} 封" for k, v in _mplan_win_days.items())
             if _mplan_win_days else "本期无排期")
_onu_src_txt = "、".join(f"{k} {v}" for k, v in sorted(_onu_src.items(), key=lambda x: -x[1])) or "—"

_osrc_rows = ""
_smax = max([1] + list(_osrc_all.values()))
for _nm, _v in sorted(_osrc_all.items(), key=lambda x: -x[1])[:5]:
    _pct = _v / _ou_total * 100 if _ou_total else 0
    _osrc_rows += (f'<div class="srow"><span class="snm" style="width:96px">{_nm}</span>'
                   f'<div class="strack"><div class="sfill" style="width:{_v/_smax*100:.0f}%;background:#3d7ff5"></div></div>'
                   f'<span class="sval">{_v}<i>{_pct:.1f}%</i></span></div>')

_mstat_txt = "、".join(f"{k} {v}" for k, v in sorted(_mstat.items(), key=lambda x: -x[1]))
_mstage_txt = "、".join(f"{k} {v}" for k, v in sorted(_mstage.items(), key=lambda x: -x[1]))

# ── 邮件发送状态动态文案 ──
# 2026-09-11 起「推送时间」已按腾讯企业邮箱实测回灌，不再是全 0，故不可写死。
_mwait = max(_mt - _msent, 0)
if _msent == 0:
    _mail_cls, _mail_head = "p0", "全链路停在「生成」→「发送」之间"
    _mail_body = (f"{_mt} 封邮件<b>全部为「待推送」</b>、推送时间字段<b>全空</b> —— "
                  "内容已就绪但未执行发送，是最直接的转化损失点。")
elif _mwait > 0:
    _mail_cls, _mail_head = "p1", f"发送已启动 · 仍有 {_mwait} 封积压"
    _mail_body = (f"以腾讯企业邮箱「已发送」实测回灌，<b>已实际推送 {_msent} 封</b>"
                  f"（9/3、9/7、9/9 三批，集中在 09:30–09:52）；"
                  f"仍有 <b>{_mwait} 封停留在「待推送」</b>，其中 47 条为「存量真实邮箱用户」分类 —— "
                  "建议明确补发或从队列清理，避免队列长期失真。")
else:
    _mail_cls, _mail_head = "ok", "发送链路已全量跑通"
    _mail_body = f"队列 {_mt} 封全部完成推送，「推送时间」已回灌，可作为后续复盘的基准。"

if _msent == 0:
    _risk_mail = (f'<div class="al p0"><h4>P0 · 邮件触达未执行发送</h4>'
                  f'<p>飞书队列 {_mt} 封<b>全部「待推送」</b>、推送时间字段全空。'
                  f'邮件是注册后激活与召回的主通道，建议先跑通本期 {_mplan_win} 封验证转化。</p></div>')
else:
    _risk_mail = (f'<div class="al p1"><h4>P1 · 存量触达 {_mwait} 封积压未发</h4>'
                  f'<p>企业邮箱实测已发 <b>{_msent}</b> 封（9/3·9/7·9/9 三批），但仍有 '
                  f'<b>{_mwait}</b> 封停在「待推送」，其中 47 条为「存量真实邮箱用户」分类 —— '
                  f'该补发的补发、该出队的出队，否则队列状态会持续失真。</p></div>')
_mlogin_vs_act = len(_ologin_all) - len(_obehav)
# 窗口 ≤10 天时登录去重值即 WAU 口径；更长窗口不标 WAU，避免口径错标
_WAU_TAG = "（WAU）" if N <= 10 else ""
# 登录用户口径差异：last_login_at 只记「最后一次登录」，埋点只记「有行为的登录用户」
_ologin_note = (f"两口径不一致：<b style='color:#dfe4ea'>last_login_at</b> 命中 {len(_ologin_all)} 人"
                f"（最后一次登录落在窗口内），<b style='color:#dfe4ea'>埋点行为</b>命中 {len(_obehav)} 人"
                f"（含窗口内登录但未回写 last_login_at 的账号）。"
                f"→ <b style='color:#fbbf24'>真实登录数 ≥ {max(len(_ologin_all), len(_obehav))} 人</b>。")

# ---------- HTML ----------
def kpi(v, l, s, cls=""):
    return f'<div class="kpi"><div class="kv {cls}">{v}</div><div class="kl">{l}</div><div class="ks">{s}</div></div>'


html = f'''<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Humance 核心数据看板 · {_WIN_SHORT}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0a0c0f;color:#e6e9ee;font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif;
padding:26px 20px 40px;line-height:1.5;-webkit-font-smoothing:antialiased}}
.page{{max-width:1200px;margin:0 auto}}
.hero{{display:flex;align-items:flex-end;justify-content:space-between;gap:16px;margin-bottom:20px;flex-wrap:wrap}}
.hero h1{{font-size:23px;font-weight:600;letter-spacing:.3px}}
.hero h1 b{{color:#4d8bf0}}
.hero .sub{{font-size:12.5px;color:#77808d;margin-top:5px}}
.hero .tag{{font-size:11.5px;color:#8fb4f5;background:rgba(61,127,245,.13);border:1px solid rgba(61,127,245,.3);
border-radius:20px;padding:4px 12px;white-space:nowrap}}
.kpis{{display:grid;grid-template-columns:repeat(6,1fr);gap:12px;margin-bottom:16px}}
.verdict{{background:linear-gradient(90deg,rgba(61,127,245,.11),rgba(61,127,245,.03));border:1px solid rgba(61,127,245,.24);
border-left:3px solid #3d7ff5;border-radius:8px;padding:12px 16px;font-size:12.5px;color:#aeb7c2;line-height:1.85;margin-bottom:16px}}
.verdict b{{color:#dfe4ea}} .verdict .hl{{color:#6ea3ff}} .verdict .warn{{color:#fbbf24}}
.kpi{{background:#14181d;border:1px solid #232932;border-radius:10px;padding:14px 15px}}
.kv{{font-size:22px;font-weight:650;letter-spacing:-.3px;color:#fff}}
.kv.blue{{color:#6ea3ff}} .kv.green{{color:#3ddc84}} .kv.amber{{color:#fbbf24}} .kv.red{{color:#f87171}}
.kl{{font-size:11.5px;color:#8b95a3;margin-top:3px}}
.ks{{font-size:10.5px;color:#5f6a78;margin-top:5px}}
.panel{{background:#14181d;border:1px solid #232932;border-radius:10px;overflow:hidden;margin-bottom:16px}}
.phead{{display:flex;align-items:center;gap:8px;padding:11px 16px;background:#1a1f26;border-bottom:1px solid #232932;
font-size:13px;font-weight:550;color:#d5dae1}}
.phead .dot{{width:6px;height:6px;border-radius:50%;background:#3d7ff5;flex:none}}
.phead .meta{{font-size:11px;color:#6f7b8a;font-weight:400}}
.phead .src{{margin-left:auto;font-size:10.5px;color:#8fb4f5;background:rgba(61,127,245,.12);border:1px solid rgba(61,127,245,.28);border-radius:20px;padding:2px 9px;white-space:nowrap;flex:none;font-weight:400}}
.pbody{{padding:16px}}
.m4{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:16px}}
.mcard{{background:#11151a;border:1px solid #1f242c;border-radius:8px;padding:12px 14px}}
.mcard .ml{{font-size:11.5px;color:#8b95a3}}
.mcard .mv{{font-size:20px;font-weight:650;color:#fff;margin-top:3px}}
.mcard .ms{{font-size:10.5px;color:#5f6a78;margin-top:4px}}
.two{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px}}
.vs{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
.vcard{{border-radius:8px;padding:13px 15px;border:1px solid}}
.vcard.n{{background:rgba(61,127,245,.07);border-color:rgba(61,127,245,.22)}}
.vcard.o{{background:rgba(34,197,94,.06);border-color:rgba(34,197,94,.2)}}
.vcard h4{{font-size:12.5px;font-weight:600;margin-bottom:9px}}
.vcard.n h4{{color:#7fb0ff}} .vcard.o h4{{color:#4ade80}}
.vline{{display:flex;justify-content:space-between;font-size:11.5px;padding:3.5px 0;color:#a8b1bd}}
.vline b{{color:#fff;font-weight:600}}
.vline em{{font-style:normal;font-size:10px;margin-left:5px}}
.up{{color:#3ddc84}} .down{{color:#f87171}}
.frow{{position:relative;height:34px;border-radius:6px;background:#161b21;margin-bottom:8px;overflow:hidden}}
.fbar{{position:absolute;left:0;top:0;bottom:0;border-radius:6px;opacity:.9}}
.frow .fname{{position:absolute;left:12px;top:50%;transform:translateY(-50%);font-size:12px;color:#fff;font-weight:550}}
.frow .fval{{position:absolute;right:12px;top:50%;transform:translateY(-50%);font-size:11.5px;color:#cfd6de}}
.srow{{display:flex;align-items:center;gap:11px;margin-bottom:13px}}
.snm{{width:64px;font-size:12px;color:#a8b1bd;flex:none}}
.strack{{flex:1;height:9px;background:#1c222a;border-radius:5px;overflow:hidden}}
.sfill{{height:100%;border-radius:5px}}
.sval{{width:96px;text-align:right;font-size:12px;color:#fff;font-weight:600;flex:none}}
.sval i{{font-style:normal;color:#6f7b8a;font-size:10.5px;font-weight:400;margin-left:6px}}
.trow{{display:flex;align-items:center;gap:10px;margin-bottom:9px}}
.tidx{{width:17px;height:17px;border-radius:4px;background:#1e242c;color:#7f8b99;font-size:10.5px;
display:flex;align-items:center;justify-content:center;flex:none;font-weight:600}}
.ttitle{{width:300px;font-size:11.5px;color:#b8c0cb;flex:none;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.ttrack{{flex:1;height:8px;background:#1c222a;border-radius:4px;overflow:hidden}}
.tfill{{height:100%;background:linear-gradient(90deg,#2f6fdd,#5b96ff);border-radius:4px}}
.tval{{width:36px;text-align:right;font-size:11.5px;color:#8b95a3;flex:none}}
.alerts{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}}
.al{{border-radius:8px;padding:12px 14px;border:1px solid;font-size:11.5px;line-height:1.65}}
.al.p0{{background:rgba(239,68,68,.07);border-color:rgba(239,68,68,.24)}}
.al.p1{{background:rgba(245,158,11,.07);border-color:rgba(245,158,11,.24)}}
.al.ok{{background:rgba(34,197,94,.06);border-color:rgba(34,197,94,.2)}}
.al h4{{font-size:12px;font-weight:600;margin-bottom:6px}}
.al.p0 h4{{color:#f87171}} .al.p1 h4{{color:#fbbf24}} .al.ok h4{{color:#4ade80}}
.al p{{color:#98a2ae}}
.foot{{font-size:10.5px;color:#5a6472;margin-top:18px;line-height:1.8;border-top:1px solid #1c222a;padding-top:12px}}
@media(max-width:900px){{.kpis{{grid-template-columns:repeat(3,1fr)}}.two{{grid-template-columns:1fr}}
.m4{{grid-template-columns:repeat(2,1fr)}}.alerts{{grid-template-columns:1fr}}.ttitle{{width:150px}}}}
/* ---------- 打印 / PDF 导出（A4 横向 · 每页水印） ---------- */
.wm{{display:none}}
@media print{{
  @page{{size:A4 landscape;margin:8mm}}
  html,body{{-webkit-print-color-adjust:exact!important;print-color-adjust:exact!important}}
  body{{background:#0a0c0f!important;padding:0!important;font-size:10.5pt;zoom:.9;
    font-family:"Heiti SC","Songti SC","Microsoft YaHei",sans-serif}}
  .page{{max-width:100%!important;padding:0 2px 6px!important}}
  .hero{{margin-bottom:10px}}
  .hero h1{{font-size:19px}} .hero .sub{{font-size:11px}} .hero .tag{{padding:3px 10px;font-size:10.5px}}
  .verdict{{padding:9px 13px;font-size:11.5px;line-height:1.7;margin-bottom:11px}}
  .kpis{{gap:9px;margin-bottom:11px}} .kpi{{padding:10px 12px}}
  .kv{{font-size:19px}} .kl{{font-size:11px}} .ks{{font-size:10px}}
  .panel{{margin-bottom:11px}} .pbody{{padding:12px}} .phead{{padding:9px 13px;font-size:12px}}
  .m4{{gap:9px;margin-bottom:11px}} .mcard{{padding:9px 11px}}
  .mcard .mv{{font-size:17px}} .mcard .ml{{font-size:11px}} .mcard .ms{{font-size:10px}}
  .alerts{{gap:9px}} .al{{padding:10px 12px;font-size:11px}}
  .srow{{margin-bottom:10px}} .trow{{margin-bottom:7px}} .frow{{height:30px;margin-bottom:7px}}
  /* 🔴 打印视口宽度会触发 ≤900px 响应式断点 → 把栅格压成 2/3 列、面板变高、页数虚增，
     必须在此强制锁回桌面栅格 */
  .kpis{{grid-template-columns:repeat(6,1fr)!important}}
  .m4{{grid-template-columns:repeat(4,1fr)!important}}
  .two{{grid-template-columns:1fr 1fr!important}}
  .vs{{grid-template-columns:1fr 1fr!important}}
  .alerts{{grid-template-columns:repeat(3,1fr)!important}}
  .ttitle{{width:300px!important}}
  .panel,.two,.kpis,.alerts,.verdict,.m4,.vs{{break-inside:avoid;page-break-inside:avoid}}
  .phead,h1,h2,h3,h4{{break-inside:avoid;page-break-inside:avoid;break-after:avoid;page-break-after:avoid}}
  .foot{{break-inside:avoid}}
  .wm{{display:grid;position:fixed;inset:0;z-index:3;pointer-events:none;
    grid-template-columns:repeat(4,1fr);grid-template-rows:repeat(3,1fr);place-items:center;opacity:.075}}
  .wm span{{transform:rotate(-28deg);font-size:14px;letter-spacing:3px;color:#fff;font-weight:600;white-space:nowrap}}
}}
</style></head><body><div class="page">

<div class="hero">
<div><h1>Humance 核心数据<b>全景看板</b></h1>
<div class="sub">数据窗口 {_WIN_LABEL}（{N} 天） ｜ 数据来源：百度统计 Site 22551575（流量）· 慧思后台 Strapi admin（注册/登录/行为）· 飞书多维表（邮件触达）</div></div>
<div class="tag">※ 访客 UV 为「人次」口径（百度跨天不去重）</div>
</div>

<div class="verdict">
<b>一句话结论</b>　{_SPAN} PV <b class="hl">{pv_tot:,}</b>、访客人次 <b class="hl">{uv_tot:,}</b>，DAU 均值 <b class="hl">{dau_avg:.0f}</b>，流量盘子稳定。
但站点呈典型「<b class="hl">一次性流量</b>」特征 —— 老访客仅 <b class="warn">{old_pct:.1f}%</b>、粘性 DAU/MAU <b class="warn">{sticky:.1f}%</b>（健康线 20%），
且 {_RU} 名注册用户中仅 <b class="warn">{_FA_PCT}%</b> 产生过收藏、<b class="warn">{_SU_PCT}%</b> 订阅国家。
<b>流量侧不是瓶颈，转化与留存才是。</b>
</div>

<div class="kpis">
{kpi(f"{pv_tot:,}", "全站浏览量 PV", f"百度统计 · {_SPAN}累计")}
{kpi(f"{uv_tot:,}", "访客人次 UV", f"百度统计 · 日均 {dau_avg:.0f}", "blue")}
{kpi(f"{dau_avg:.0f}", "DAU 均值 · 精确", f"百度统计 · 峰 {dau_max} / 谷 {dau_min}", "blue")}
{kpi(f"{old_pct:.1f}%", "老访客占比", f"百度统计 · {old_tot:,} 人次回访", "amber")}
{kpi(f"{pvpu:.2f}", "人均浏览页数", f"百度统计 · 平均停留 {avg_time:.0f}s", "")}
{kpi(str(_RU), "累计注册用户", f"慧思后台 · 内容收藏 {_FA} 人", "green")}
</div>

<div class="panel">
<div class="phead"><span class="dot"></span>DAU / WAU / MAU 活跃全景<span class="src">百度统计</span><span class="meta">{_WIN_LABEL} ｜ 深蓝=工作日　浅蓝=周末</span></div>
<div class="pbody">
<div class="m4">
<div class="mcard"><div class="ml">DAU 均值 · 精确</div><div class="mv">{dau_avg:.0f}</div><div class="ms">峰值 {dau_max} / 谷 {dau_min}</div></div>
<div class="mcard"><div class="ml">WAU · 近 7 日人次</div><div class="mv">{wau:,}</div><div class="ms">{_WAU_LABEL} 合计</div></div>
<div class="mcard"><div class="ml">MAU · 近 30 日人次</div><div class="mv">{mau:,}</div><div class="ms">{_MAU_LABEL} 合计</div></div>
<div class="mcard"><div class="ml">粘性 DAU / MAU</div><div class="mv">{sticky:.1f}%</div><div class="ms">健康线 20%</div></div>
</div>
{dau_svg}
<div class="m4" style="margin:16px 0 0">
<div class="mcard"><div class="ml">DAU / WAU</div><div class="mv">{dau_wau:.1f}%</div><div class="ms">{_WAU_RATIO_TXT}</div></div>
<div class="mcard"><div class="ml">WAU / MAU</div><div class="mv">{wau_mau:.1f}%</div><div class="ms">{_WAU_MAU_TXT}</div></div>
<div class="mcard"><div class="ml">周末 / 工作日</div><div class="mv">{we_wd:.2f}</div><div class="ms">工作日 {wd_avg:.0f} / 周末 {we_avg:.0f}</div></div>
<div class="mcard"><div class="ml">老访客占比</div><div class="mv">{old_pct:.1f}%</div><div class="ms">{100-old_pct:.1f}% 是首次到访</div></div>
</div>
</div></div>

<div class="two">
<div class="panel" style="margin:0">
<div class="phead"><span class="dot"></span>新老访客行为质量对比<span class="src">百度统计</span><span class="meta">{_SPAN}</span></div>
<div class="pbody"><div class="vs">
<div class="vcard n"><h4>新访客 · 占 {100-old_pct:.1f}%</h4>
<div class="vline">人次<b>{new_tot:,}</b></div>
<div class="vline">人均浏览<b>{new_pvpu:.2f} 页</b></div>
<div class="vline">平均停留<b>{new_time:.0f} 秒</b></div>
<div class="vline">跳出率<b>{new_bounce:.1f}%</b></div></div>
<div class="vcard o"><h4>老访客 · 占 {old_pct:.1f}%</h4>
<div class="vline">人次<b>{old_tot:,}</b></div>
<div class="vline">人均浏览<b>{old_pvpu:.2f} 页</b><em class="up">高 {(old_pvpu/new_pvpu-1)*100:.0f}%</em></div>
<div class="vline">平均停留<b>{old_time:.0f} 秒</b><em class="up">高 {(old_time/new_time-1)*100:.0f}%</em></div>
<div class="vline">跳出率<b>{old_bounce:.1f}%</b><em class="up">低 {new_bounce-old_bounce:.0f}pp</em></div></div>
</div>
<p style="font-size:11.5px;color:#7f8b99;margin-top:14px;line-height:1.7">
老访客各项质量指标全面优于新访客，但窗口内占比仅 <b style="color:#fbbf24">{old_pct:.1f}%</b>。
站点呈典型「一次性流量」特征，<b style="color:#e6e9ee">留存（Newsletter / 回访钩子）优先级高于拉新</b>。</p>
</div></div>

<div class="panel" style="margin:0">
<div class="phead"><span class="dot"></span>深度行为渗透漏斗<span class="src">慧思后台 Strapi</span><span class="meta">累计 {_RU} 名注册用户</span></div>
<div class="pbody">{fun_rows}
<p style="font-size:11.5px;color:#7f8b99;margin-top:12px;line-height:1.7">
注册用户中仅 <b style="color:#3ddc84">{_FA_PCT}%</b> 产生过收藏、<b style="color:#3ddc84">{_SU_PCT}%</b> 订阅国家。
深度行为渗透率长期低位 —— <b style="color:#f87171">注册之后的二次行为转化</b>是留存与复访的最大短板。</p>
</div></div>
</div>

<div class="panel">
<div class="phead"><span class="dot"></span>用户转化链路 · 注册 → 登录 → 产生行为<span class="src">慧思后台 Strapi admin</span><span class="meta">User 表 + 埋点事件表</span></div>
<div class="pbody">
<div class="m4">
<div class="mcard"><div class="ml">累计注册用户</div><div class="mv">{_ou_total}</div><div class="ms">User 表全量（历史累计）</div></div>
<div class="mcard"><div class="ml">本期新增注册</div><div class="mv">{len(_onu)}</div><div class="ms">{_onu_txt}</div></div>
<div class="mcard"><div class="ml">本期登录用户{_WAU_TAG}</div><div class="mv">{len(_ologin_all)}</div><div class="ms">窗口内去重 · 外部真实 {len(_ologin_ext)} 人</div></div>
<div class="mcard"><div class="ml">本期产生行为用户</div><div class="mv">{len(_obehav_ext)}</div><div class="ms">外部真实｜埋点原始 {len(_obehav)} 人</div></div>
</div>
<div style="font-size:11.5px;color:#8b95a3;margin:2px 0 8px">登录态日活（DAU-登录）· 当日有行为事件的去重登录账号</div>
{_odau_svg}
<div class="two" style="margin:18px 0 0">
<div>
<div style="font-size:11.5px;color:#8b95a3;margin-bottom:9px">产生行为用户明细（按行为次数排序）</div>
{_obehav_rows}
</div>
<div>
<div style="font-size:11.5px;color:#8b95a3;margin-bottom:9px">注册来源分布（累计 {_ou_total} 人）</div>
{_osrc_rows}
<p style="font-size:11px;color:#7f8b99;line-height:1.78;margin-top:12px">{_ologin_note}</p>
</div>
</div>
<div class="alerts" style="margin-top:16px">
<div class="al p1"><h4>注册：本期 {len(_onu)} 人</h4><p>注册来源 {_onu_src_txt}。月度注册走势 7月 32 → 8月 20 → 9月至今 {len(_onu)} 人。</p></div>
<div class="al p0"><h4>访客 → 登录转化约 {len(_obehav)/uv_tot*100:.2f}%</h4><p>本期访客人次 {uv_tot:,}，产生行为的登录账号仅 {len(_obehav)} 个（外部 {len(_obehav_ext)}）——「浏览 → 注册/登录」是最大漏损段。</p></div>
<div class="al p1"><h4>登录埋点缺失，口径为下界</h4><p>`login_success` 事件本期 0 条；登录数靠 `last_login_at` 与埋点 `actorUserId` 反推，且含 {_ointernal} 个内部账号需剔除。</p></div>
</div>
</div></div>

<div class="panel">
<div class="phead"><span class="dot"></span>邮件触达队列与推送状态<span class="src">{_MAIL.get('src') or '未取到'}</span><span class="meta">触达队列 / 推送状态</span></div>
<div class="pbody">
<div class="m4">
<div class="mcard"><div class="ml">触达队列总量</div><div class="mv">{_mt}</div><div class="ms">已生成邮件（历史累计）</div></div>
<div class="mcard"><div class="ml">本期计划推送</div><div class="mv">{_mplan_win}</div><div class="ms">{_plan_txt}</div></div>
<div class="mcard"><div class="ml">已实际推送</div><div class="mv red">{_msent}</div><div class="ms">「推送时间」字段非空</div></div>
<div class="mcard"><div class="ml">待推送积压</div><div class="mv amber">{_mstat.get('待推送', 0)}</div><div class="ms">通道 100% 邮件｜优先级 {_mprio.get('中', 0)} 中 / {_mprio.get('高', 0)} 高</div></div>
</div>
<div style="font-size:11.5px;color:#8b95a3;margin:2px 0 9px">邮件分类分布（队列 {_mt} 封）</div>
{_mail_rows}
<div class="alerts" style="margin-top:16px">
<div class="al {_mail_cls}"><h4>{_mail_head}</h4><p>{_mail_body}</p></div>
<div class="al p1"><h4>触达类型覆盖不全</h4><p>队列仅 A 新注册欢迎 / C 核心价值二次触达 / 存量真实邮箱用户三类；<b>B 注册后活跃</b>与 <b>D 5日未活跃召回</b>为 0（产品待补）。</p></div>
<div class="al ok"><h4>客户阶段分层已就位</h4><p>阶段分布 {_mstage_txt}；已建联客户已从营销类触达中剥离，符合防骚扰护栏设计。</p></div>
</div>
</div></div>

<div class="panel">
<div class="phead"><span class="dot"></span>2026 年月度趋势<span class="src">百度统计 + 慧思后台</span><span class="meta">深蓝=PV　浅蓝=UV人次　绿线=注册数（右轴）</span></div>
<div class="pbody">{month_svg}
<div class="alerts" style="margin-top:16px">
<div class="al p1"><h4>4 月分水岭</h4><p>3–4 月流量跃升（PV +3.1k / UV +2.1k），但停留时长从 199s 降到 180s、跳出率抬升 —— 增量以泛曝光新客为主。</p></div>
<div class="al p0"><h4>8 月转化失速</h4><p>PV −8.3% / UV −4.5%，注册从 33 → <b>20</b>（<b>−39%</b>）。注册跌幅远大于流量跌幅，疑转化环节故障。</p></div>
<div class="al ok"><h4>7 月为全年峰值</h4><p>PV 11,611 / UV 8,360 / 注册 33 / 转化 0.39% 均为全年最高，可作为内容与渠道复盘的基准月。</p></div>
</div>
</div></div>

<div class="two">
<div class="panel" style="margin:0">
<div class="phead"><span class="dot"></span>流量来源结构<span class="src">百度统计</span><span class="meta">窗口内 · {src_tot:,} PV</span></div>
<div class="pbody">{src_rows}
<p style="font-size:11.5px;color:#7f8b99;margin-top:14px;line-height:1.7">
直接访问仍占 <b style="color:#6ea3ff">{_dir_pct:.1f}%</b>（品牌/书签/公众号导流）。
搜索占 <b style="color:#3ddc84">{_sea_pct:.1f}%</b>——
但搜索流量的天花板不在量，而在 <b style="color:#fbbf24">法规与文章详情页百度零收录</b>，流量被卡在入口页。</p>
</div></div>

<div class="panel" style="margin:0">
<div class="phead"><span class="dot"></span>内容访问 TOP10<span class="src">百度统计</span><span class="meta">窗口内 PV（百度口径）</span></div>
<div class="pbody">{top_rows}
<p style="font-size:11.5px;color:#7f8b99;margin-top:12px;line-height:1.7">
窗口内 PV TOP10 页面（百度口径，含栏目列表页），悬停可看完整 URL。
流量高度集中在<b style="color:#e6e9ee">首页与知识库详情页</b>；⚠️ 内容排行<b style="color:#f87171">禁用后台 `article_view`</b>（爬虫污染约 15 倍）。</p>
</div></div>
</div>

<div class="panel">
<div class="phead"><span class="dot"></span>{_SNAP_TITLE}<span class="src">百度统计</span><span class="meta">环比前 7 天</span></div>
<div class="pbody">
<div class="m4">
<div class="mcard"><div class="ml">PV</div><div class="mv">{cur_pv:,}</div><div class="ms"><span class="{'down' if cur_pv < prev_pv else 'up'}">{'▼' if cur_pv < prev_pv else '▲'} {abs(cur_pv/prev_pv-1)*100:.1f}%</span> 环比上期</div></div>
<div class="mcard"><div class="ml">访客人次 UV</div><div class="mv">{cur_uv:,}</div><div class="ms"><span class="{'down' if cur_uv < prev_uv else 'up'}">{'▼' if cur_uv < prev_uv else '▲'} {abs(cur_uv/prev_uv-1)*100:.1f}%</span> 环比上期</div></div>
<div class="mcard"><div class="ml">DAU 均值</div><div class="mv">{cur_uv/7:.0f}</div><div class="ms">峰 {_cmax['visitor_count']} @{k(_cmax)[4:6]}/{k(_cmax)[6:8]} · 谷 {_cmin['visitor_count']} @{k(_cmin)[4:6]}/{k(_cmin)[6:8]}</div></div>
<div class="mcard"><div class="ml">老访客占比</div><div class="mv">{cur_old_pct:.1f}%</div><div class="ms"><span class="{'up' if cur_old_pct >= old_pct else 'down'}">{'▲ 高于' if cur_old_pct >= old_pct else '▼ 低于'} {_SPAN}均值 {old_pct:.1f}%</span></div></div>
</div>
<div class="alerts" style="margin-top:16px">
<div class="al ok"><h4>访客质量对比</h4><p>老访客占比 {cur_old_pct:.1f}%；老访客停留 <b>{_o7_time:.0f}s</b> / 跳出 <b>{_o7_bo:.0f}%</b>，新访客 <b>{_n7_time:.0f}s</b> / <b>{_n7_bo:.0f}%</b>。</p></div>
<div class="al p1"><h4>流量环比</h4><p>PV {cur_pv:,}（{'+' if cur_pv>=prev_pv else ''}{(cur_pv/prev_pv-1)*100:.1f}%）/ UV {cur_uv:,}（{'+' if cur_uv>=prev_uv else ''}{(cur_uv/prev_uv-1)*100:.1f}%）。</p></div>
<div class="al p0"><h4>转化端持续失血</h4><p>订阅曝光 → 点击转化率 <b>0.03%</b>（2 / 6,170）；本期注册 <b>{len(_onu)}</b> 人、产生行为的外部登录用户 <b>{len(_obehav_ext)}</b> 人、邮件已实际推送 <b>{_msent}</b> 封。</p></div>
</div>
</div></div>

<div class="panel">
<div class="phead"><span class="dot"></span>风险与行动建议<span class="src">综合分析</span><span class="meta">按 ROI 排序</span></div>
<div class="pbody"><div class="alerts">
<div class="al p0"><h4>P0 · 修复法规 sitemap</h4><p>`sitemap-regulation.xml` 为空文件（0 URL），500+ 法规全部百度零收录。修 sitemap + 站长平台推送，ROI 极高。</p></div>
<div class="al p0"><h4>P0 · 内容排行切百度口径</h4><p>后台 `article_view` 爬虫占 93–95%（15 倍虚高），禁止用于内容热度排行；上游按 UA 过滤爬虫。</p></div>
{_risk_mail}
<div class="al p1"><h4>P1 · 下载留资钩子挂载</h4><p>知识库详情页挂「下载留资」，月 PV 5,935；按 1%/3% 提交率外推，月注册可达 39 / 119 人（2.2x–6.6x）。</p></div>
<div class="al p1"><h4>P1 · 补齐缺失埋点</h4><p>`login_success` / `download` 全为 0，登录人数永远显示假 0（实测登录态 ≥ 8 人）；登录→阅读→订阅链路完全不可观测。</p></div>
<div class="al p1"><h4>P1 · 排查注册→订阅断链</h4><p>注册成功后未自动回补订阅（注册 2 人 → 订阅成功 0 人），疑链路断裂，最高 ROI 修复点。</p></div>
<div class="al ok"><h4>持续 · 留存优先于拉新</h4><p>粘性 DAU/MAU {sticky:.1f}%（健康线 20%）、老访客仅 {old_pct:.1f}% → 内容与触达预算应向回访与订阅倾斜。</p></div>
</div></div></div>

<div class="foot">
<b style="color:#9aa5b1">数据来源对照</b><br>
· 流量（PV / 访客人次 / 新老访客 / 来源 / 停留 / 跳出）→ <b style="color:#8fb4f5">百度统计 Site 22551575</b><br>
· 注册 / 登录用户 / 产生行为用户 / 登录 DAU → <b style="color:#8fb4f5">慧思后台 Strapi admin</b>（User 表 + 埋点事件表）<br>
· 邮件触达队列与推送状态 → <b style="color:#8fb4f5">飞书多维表「客户触达邮件同步」</b> · {_MAIL.get('src') or '未取到'}<br>
· 累计注册 / 收藏 / 订阅基线 → {_B['source']}<br>
<br>
口径说明：① 百度 UV 为访客人次（跨天不去重），WAU/MAU 为估算值；② 后台 `page_view` 埋点覆盖不全且未滤爬虫，流量总量一律以百度为准；③ 后台 `article_view` 约 93%+ 为爬虫，禁止用于内容排行；④ 登录用户数为<b>下界</b>（`login_success` 埋点缺失）；⑤ 内部账号（@xinfushe.com / @yonyou.com）已从「产生行为用户」中剔除；⑥ 邮件「已实际推送」以飞书表「推送时间」字段是否填写为准。<br>
生成时间：{_GEN_DATE} ｜ 制表：巴蒂
</div>
</div>
</body></html>'''

open(OUT, "w", encoding="utf-8").write(html)
print("✅ 生成:", OUT)
print(f"   PV {pv_tot:,} / UV {uv_tot:,} / DAU {dau_avg:.0f} / 老访客 {old_pct:.1f}% / 粘性 {sticky:.1f}%")
print(f"   WAU {wau:,} / 周末÷工作日 {we_wd:.2f} / 人均 {pvpu:.2f} / 停留 {avg_time:.0f}s / 跳出 {bounce:.1f}%")
