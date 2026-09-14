#!/usr/bin/env python3
"""按(北京时间)逐日统计 analytics-event 事件数，用于与百度 PV/UV 做相关性比对。

用 ID→时间 的单调性不成立时要靠 occurredAt 过滤，这里直接每个自然日单独查 count。
北京时间一天 = UTC 前一天16:00 ~ 当天16:00。
"""
import sys, re, time, json, datetime
sys.path.insert(0, "/Users/yoyo/.workbuddy/skills/baidu-ziyuan-collect/scripts")
from control import Bridge

CT = "api::analytics-event.analytics-event"
BASE = f"https://admin.humancehr.com/admin/content-manager/collection-types/{CT}"
OUT = "/tmp/strapi_daily_counts.json"


def cst_day_range(day: datetime.date):
    """返回北京时间 day 这一天的 [start, end) UTC ISO 串"""
    start = datetime.datetime.combine(day, datetime.time(0, 0)) - datetime.timedelta(hours=8)
    end = start + datetime.timedelta(days=1)
    f = "%Y-%m-%dT%H:%M:%S.000Z"
    return start.strftime(f), end.strftime(f)


def q(b, qs, wait=6.0, retries=2):
    for i in range(retries + 1):
        try:
            b.navigate(f"{BASE}?{qs}", new_tab=False)
            time.sleep(wait)
            t = b.get_text() or ""
            m = re.search(r"([\d,]+)\s+entries? found", t)
            if m:
                return int(m.group(1).replace(",", ""))
            # 页面可能还没渲染完
            time.sleep(3)
            t = b.get_text() or ""
            m = re.search(r"([\d,]+)\s+entries? found", t)
            if m:
                return int(m.group(1).replace(",", ""))
            return None
        except Exception as e:
            print(f"    retry{i} err: {type(e).__name__}", flush=True)
            time.sleep(4)
    return None


def main():
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    end_day = datetime.date(2026, 9, 3)  # 今天(北京时间)
    b = Bridge()
    print("connected:", b.is_connected(), flush=True)

    res = []
    for i in range(days - 1, -1, -1):
        day = end_day - datetime.timedelta(days=i)
        s, e = cst_day_range(day)
        qs = (f"filters[$and][0][occurredAt][$gte]={s}"
              f"&filters[$and][1][occurredAt][$lt]={e}"
              f"&pageSize=1&page=1")
        n = q(b, qs)
        res.append({"day": day.isoformat(), "events": n})
        print(f"  {day} 事件数={n}", flush=True)
        # 每 10 天存一次盘
        if len(res) % 10 == 0:
            json.dump(res, open(OUT, "w"), ensure_ascii=False)

    json.dump(res, open(OUT, "w"), ensure_ascii=False, indent=1)
    ok = [r for r in res if r["events"] is not None]
    print(f"\n完成 {len(ok)}/{len(res)} 天，总计 {sum(r['events'] for r in ok)} 条事件")


if __name__ == "__main__":
    main()
