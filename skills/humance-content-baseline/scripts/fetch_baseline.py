# -*- coding: utf-8 -*-
"""慧思内容库基线快照抓取（只读）"""
import urllib.request, urllib.parse, json, ssl, csv, os, re, time, collections

ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
OUT = os.path.dirname(os.path.abspath(__file__))
UA = {"User-Agent": "Mozilla/5.0"}

def api(**kw):
    kw.setdefault("pageSize", 100)
    u = "https://www.humancehr.com/api/search?" + urllib.parse.urlencode(kw)
    for _ in range(3):
        try:
            r = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30, context=ctx)
            return json.loads(r.read().decode())
        except Exception:
            time.sleep(1.5)
    return {}

def get(u):
    try:
        r = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30, context=ctx)
        return r.read().decode("utf-8", "ignore")
    except Exception:
        return ""

print("=== 1/4 抓取法规 regulations ===")
regs, seen = [], set()
for page in range(1, 30):
    d = api(q="的", page=page)
    rs = d.get("regulations", [])
    if not rs: break
    for x in rs:
        k = x.get("documentId") or x.get("id")
        if k in seen: continue
        seen.add(k)
        regs.append({
            "id": x.get("id"), "documentId": x.get("documentId"),
            "title": x.get("title"), "slug": x.get("slug"),
            "countryTag": x.get("countryTag"), "locale": x.get("locale"),
            "category": x.get("category"), "publishYear": x.get("publishYear"),
            "publishedAt": x.get("publishedAt"), "updatedAt": x.get("updatedAt"),
            "contentUrl": x.get("contentUrl"), "pdfUrl": x.get("pdfUrl"),
            "hasSummary": bool(x.get("summary")), "contentLen": len(x.get("content") or ""),
            "tags": "|".join(x.get("tags") or []) if isinstance(x.get("tags"), list) else (x.get("tags") or ""),
        })
    if len(rs) < 100: break
print(f"  法规 {len(regs)} 条")

print("=== 2/4 抓取文章 articles（全板块）===")
arts, seen2 = [], set()
for page in range(1, 40):
    d = api(q="的", page=page)
    a = d.get("articles", [])
    if not a: break
    for x in a:
        k = x.get("slug") or x.get("documentId") or x.get("id")
        if k in seen2: continue
        seen2.add(k)
        arts.append({
            "slug": x.get("slug"), "title": x.get("title"),
            "countryTag": x.get("countryTag"), "locale": x.get("locale"),
            "category": x.get("category"), "publishYear": x.get("publishYear"),
            "publishedAt": x.get("publishedAt"), "updatedAt": x.get("updatedAt"),
            "contentLen": len(x.get("content") or ""),
        })
    if len(a) < 100: break
    if page % 5 == 0: print(f"    ...{len(arts)}")
print(f"  文章 {len(arts)} 条")

print("=== 3/4 抓取 sitemap ===")
sm = {}
for s in ["articles", "holiday", "regulation"]:
    c = get(f"https://www.humancehr.com/sitemap-{s}.xml")
    sm[s] = re.findall(r"<loc>(.*?)</loc>\s*(?:<lastmod>(.*?)</lastmod>)?", c)
    print(f"  sitemap-{s}: {len(sm[s])} 条")

def dump(name, rows, fields):
    p = os.path.join(OUT, name)
    with open(p, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader()
        for r in rows: w.writerow({k: r.get(k) for k in fields})
    print(f"  -> {name} ({len(rows)} 行)")

dump("baseline_regulations.csv", regs, ["id","documentId","title","slug","countryTag","locale",
     "category","publishYear","publishedAt","updatedAt","contentUrl","pdfUrl","hasSummary","contentLen","tags"])
dump("baseline_articles.csv", arts, ["slug","title","countryTag","locale","category",
     "publishYear","publishedAt","updatedAt","contentLen"])

smrows = []
for s, items in sm.items():
    for u, lm in items:
        seg = u.replace("https://www.humancehr.com/","").strip("/").split("/")
        smrows.append({"sitemap": s, "section": seg[0] if seg else "?", "url": u, "lastmod": lm})
dump("baseline_sitemap.csv", smrows, ["sitemap","section","url","lastmod"])

json.dump({"regulations": regs, "articles_count": len(arts), "sitemap": {k: len(v) for k,v in sm.items()}},
          open(os.path.join(OUT,"baseline_raw.json"),"w",encoding="utf-8"), ensure_ascii=False)
print("\n完成。输出目录:", OUT)
