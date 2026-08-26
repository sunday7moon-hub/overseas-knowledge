"""百度搜索资源平台 - 采集并推送飞书多维表格"""
import sys, time, json, subprocess, os, logging
from datetime import datetime, date
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

sys.path.insert(0, str(Path(__file__).parent))
from control import Bridge

# ─── 配置 ───
LARK = "/Users/yoyo/.workbuddy/binaries/node/cli-connector-packages/bin/lark-cli"
BASE_TOKEN = "PjqEbhxsRaL4tss0XGUcmmWTn1f"
TABLE_KEYWORDS = "tblLQ3fk9uEba8GC"   # 关键词表
TABLE_PAGES = "tblDPecpiO1TDj0F"      # 热门页面表
URL_30D = ("https://ziyuan.baidu.com/keywords/index"
           "?range=month&site=https%3A%2F%2Fwww.humancehr.com%2F")
os.environ["LARK_CLI_NO_PROXY"] = "1"


def push_record(table_id, record):
    """写入单条记录到飞书"""
    cmd = [LARK, "base", "+record-upsert",
           "--base-token", BASE_TOKEN,
           "--table-id", table_id,
           "--json", json.dumps(record, ensure_ascii=False),
           "--as", "bot"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        log.error(f"  推送失败: {r.stderr[:200]}")
        return False
    d = json.loads(r.stdout)
    ok = d.get("ok", False)
    if ok:
        log.info(f"  ✔ 已推送")
    else:
        log.error(f"  ✘ {d}")
    return ok


def main():
    bridge = Bridge()

    # ── 检查连接 ──
    if not bridge.is_connected():
        log.error("❌ Bridge 未连接")
        return
    log.info("✅ Bridge 已连接")

    # ── 导航到关键词页（复现已有页面，不新开） ──
    log.info("→ 定位到关键词页...")
    try:
        bridge._call("navigate", {"url": URL_30D, "newTab": False}, timeout=15)
    except:
        pass
    time.sleep(6)
    log.info(f"  {bridge.get_url() or bridge.evaluate('document.title')}")

    # ── 采集热门关键词 ──
    log.info("\n→ 采集热门关键词")
    # 切到关键词 tab
    bridge.evaluate("""
    (() => {
        const all = document.querySelectorAll('*');
        for (const el of all) {
            if (el.offsetParent !== null && el.textContent.trim() === "热门关键词") { el.click(); return; }
        }
    })()
    """)
    time.sleep(3)

    kw_rows = bridge.evaluate("""
    (() => {
        const r = [];
        const table = document.querySelector("table.mod-table-handler-ue2");
        if (!table) return [];
        table.querySelectorAll("tbody tr").forEach(row => {
            const c = Array.from(row.querySelectorAll("td")).map(td => td.textContent.trim());
            if (c.length >= 4 && c[0] && c[0] !== "loading..." && row.className !== "list-template") {
                if (c[0].includes('关键词')) return;
                r.push(c);
            }
        });
        return r;
    })()
    """) or []
    log.info(f"  共 {len(kw_rows)} 条关键词")

    # ── 推送到飞书关键词表 ──
    log.info("→ 推送关键词到飞书...")
    now_str = datetime.now().strftime("%Y/%m/%d %H:%M")
    for row in kw_rows:
        if len(row) < 5: continue
        record = {
            "关键词": row[0],
            "展现量": row[2],
            "点击量": row[1],
            "点击率": row[3],
            "排名": row[4],
            "采集时间": now_str,
            "热点范围": "近30天",
            "渠道": "百度",
        }
        push_record(TABLE_KEYWORDS, record)

    # ── 采集热门页面 ──
    log.info("\n→ 采集热门页面")
    bridge.evaluate("""
    (() => {
        const all = document.querySelectorAll('*');
        for (const el of all) {
            if (el.offsetParent !== null && el.textContent.trim() === "热门页面") { el.click(); return; }
        }
    })()
    """)
    time.sleep(3)

    page_rows = bridge.evaluate("""
    (() => {
        const r = [];
        const table = document.querySelector("table.mod-table-handler-ue2");
        if (!table) return [];
        table.querySelectorAll("tbody tr").forEach(row => {
            const c = Array.from(row.querySelectorAll("td")).map(td => td.textContent.trim());
            if (c.length >= 4 && c[0] && c[0] !== "loading..." && row.className !== "list-template") {
                if (c[0].includes('页面') || c[0].includes('网址')) return;
                r.push(c);
            }
        });
        return r;
    })()
    """) or []
    log.info(f"  共 {len(page_rows)} 条热门页面")

    # ── 推送到飞书热门页面表 ──
    log.info("→ 推送热门页面到飞书...")
    for row in page_rows:
        if len(row) < 5: continue
        record = {
            "URL": row[0],
            "展现量": row[2],
            "点击量": row[1],
            "点击率": row[3],
            "排名": row[4],
            "采集时间": now_str,
            "热点范围": "近30天",
            "渠道": "百度",
        }
        push_record(TABLE_PAGES, record)

    log.info(f"\n✅ 全部完成！共推送 {len(kw_rows)} 条关键词 + {len(page_rows)} 条热门页面")


if __name__ == "__main__":
    main()
