#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把慧思数据库（Anchor Tech / BO_EU_CRAWLER_NEWS_SOURCE）中的资讯 INFO_ID=2026090714
推送到 demo 前端（demo.humancehr.com）并发布。

链路说明（2026-09-08 实测）：
  - 慧思数据库   = Anchor Tech BO_EU_CRAWLER_NEWS_SOURCE（资讯 INFO_ID / ID 即 originId）
  - demo 前端    = https://demo.humancehr.com（Astro）
  - demo 后台API = https://demo-admin.humancehr.com/api  （Strapi，支持 GET/POST/PUT；DELETE 需更高权限）
  ⚠️ demo.humancehr.com/api 只是 Astro 的只读+创建代理，PUT/DELETE 会返回前端 404 页面，
     更新/发布必须走 demo-admin.humancehr.com。

流程：
  1. 读慧思记录 + 已生成的文章载荷，组装最终 data
  2. 若已存在同 originId/slug 的文章 -> PUT 更新；否则 POST 创建
  3. 置 publishedAt 发布
  4. GET 校验（originId 命中 + publishedAt 非空 + 内容长度）
  5. 回写慧思数据库 PUSH_STATUS=1 / PUBLISH_TIME

用法：
  python3 push_news_to_demo.py --token <后台token> [--env demo|prod] [--dry] [--no-writeback]
    --env demo  (默认) 推到 demo.humancehr.com（后台 demo-admin）
    --env prod        推到 www.humancehr.com（后台 admin，同一 token 通用）
"""
import json, sys, subprocess, urllib.parse
from datetime import datetime, timezone, timedelta

# env -> (后台 Strapi 写地址, 前台只读代理, 前台站点根)
# ⚠️ 更新/发布必须走「后台 Strapi」，前台只读代理 PUT/DELETE 会落 404 页。
#   - demo: demo-admin.humancehr.com/api   （token 无 DELETE 权限，误建删不掉）
#   - prod: admin.humancehr.com/api        （与 demo 同一套后台体系，后台 token 通用，已实测可直读 2315 篇）
ENV_MAP = {
    'demo': ('https://demo-admin.humancehr.com/api/articles',
             'https://demo.humancehr.com/api/articles',
             'https://demo.humancehr.com'),
    'prod': ('https://admin.humancehr.com/api/articles',
             'https://www.humancehr.com/api/articles',
             'https://www.humancehr.com'),
}
DEMO_ADMIN = ENV_MAP['demo'][0]
DEMO_FRONT = ENV_MAP['demo'][1]
ANCHOR_API = 'https://www.anchortech.ai/api'
BO_NAME = 'BO_EU_CRAWLER_NEWS_SOURCE'
DW_VIEW_ID = 'obj_6fb16d1256db4ec1b15ba5212d1259ce'
MSA_SVC_ID = 'ai-content'

SRC_REC = '/tmp/rec_2026090714.json'
SRC_PAYLOAD = '/tmp/xingyu_article_payload.json'
INFO_ID = '2026090714'
LOG = {}


def http(url, data=None, headers=None, method=None, form=False):
    """走 curl 子进程：本机存在 HTTPS 代理，Python urllib 直连会 SSL 握手失败"""
    # -g 必须加：URL 里的 [] {} 会被 curl 当作 glob 字符导致查询失效
    cmd = ['curl', '-sg', '-m', '90', '-w', '\n%{http_code}', url]
    for k, v in (headers or {}).items():
        cmd += ['-H', f'{k}: {v}']
    tmp = None
    if data is not None:
        if form:
            body = urllib.parse.urlencode(data)
            cmd += ['--data-urlencode'] if False else []
            cmd += ['-d', body]
            if 'Content-Type' not in (headers or {}):
                cmd += ['-H', 'Content-Type: application/x-www-form-urlencoded']
        else:
            body = json.dumps(data, ensure_ascii=False)
            tmp = '/tmp/_push_body.json'
            open(tmp, 'w', encoding='utf-8').write(body)
            cmd += ['--data-binary', f'@{tmp}']
            if 'Content-Type' not in (headers or {}):
                cmd += ['-H', 'Content-Type: application/json']
        cmd += ['-X', method or 'POST']
    out = subprocess.run(cmd, capture_output=True, text=True).stdout
    tail = out.rstrip('\n').rsplit('\n', 1)
    raw, code = (tail[0], tail[-1]) if len(tail) == 2 else ('', tail[0])
    try:
        return int(code), json.loads(raw)
    except Exception:
        return int(code) if code.isdigit() else 0, raw[:400]


def build_data():
    rec = json.load(open(SRC_REC, encoding='utf-8'))
    data = json.load(open(SRC_PAYLOAD, encoding='utf-8'))['data']
    data['sourceName'] = (rec.get('SOURCE') or '')[:200]
    data['sourceUrl'] = rec.get('ORIGINAL_URL') or ''
    tags = [t for t in json.loads(rec.get('TAGS') or '[]') if t != '海外资讯']
    for f in ('industryTags', 'knowledgeTags'):
        cur = [x for x in (data.get(f) or '').split(',') if x]
        cur += [t for t in tags if t not in cur]
        if '海外资讯' not in cur:
            cur.append('海外资讯')
        data[f] = ','.join(cur)
    data.setdefault('locale', 'zh-CN')
    data.setdefault('jobTags', '通用')
    data['newsletterCandidate'] = True
    data['views'] = 0
    return rec, data


def find_existing(hdr, origin_id, slug, admin_url=DEMO_ADMIN):
    for field, val in (('originId', origin_id), ('slug', slug)):
        u = f'{admin_url}?filters[{field}][$eq]={urllib.parse.quote(str(val))}&pagination[pageSize]=5'
        code, res = http(u, headers=hdr)
        if code == 200 and isinstance(res, dict) and res.get('data'):
            return res['data'][0], field
    return None, None


def main():
    token = sys.argv[sys.argv.index('--token') + 1] if '--token' in sys.argv else ''
    if not token:
        print('缺少 --token'); sys.exit(1)
    dry = '--dry' in sys.argv
    no_wb = '--no-writeback' in sys.argv
    # --env demo|prod（默认 demo）。prod 走 admin.humancehr.com 真后台
    env = 'demo'
    if '--env' in sys.argv:
        i = sys.argv.index('--env')
        env = sys.argv[i + 1] if i + 1 < len(sys.argv) else 'demo'
    admin_url, front_url, front_site = ENV_MAP.get(env, ENV_MAP['demo'])
    hdr = {'Authorization': f'Bearer {token}'}

    rec, data = build_data()
    print(f'[{INFO_ID}] env={env} {data["title"]}')
    print(f'  originId={data["originId"]} slug={data["slug"]} content={len(data["content"])}字符')
    print(f'  tags: {data["industryTags"]} | {data["knowledgeTags"]}')
    if dry:
        print('  后台写地址:', admin_url)
        print(json.dumps(data, ensure_ascii=False, indent=2)[:2000]); return

    now = datetime.now(timezone(timedelta(hours=8))).isoformat()

    # 1. 查找是否已存在
    exist, by = find_existing(hdr, data['originId'], data['slug'], admin_url)
    if exist:
        doc = exist['documentId']
        print(f'[1/5] 已存在（按{by}命中 id={exist["id"]} documentId={doc}）-> 走更新')
        payload = dict(data)
        payload['publishedAt'] = now
        code, res = http(f'{admin_url}/{doc}', {'data': payload}, hdr, method='PUT')
        action = 'update'
    else:
        print('[1/5] 不存在 -> 创建')
        code, res = http(admin_url, {'data': data}, hdr)
        action = 'create'
    if code not in (200, 201):
        print(f'[FAIL] {action} 失败 code={code} {res}'); sys.exit(2)
    art = res['data']
    doc = art['documentId']
    print(f'      {action} OK id={art["id"]} documentId={doc} publishedAt={art.get("publishedAt")}')

    # 2. 若仍是草稿则补发布
    if not art.get('publishedAt'):
        print('[2/5] 补发布 ...')
        code, res = http(f'{admin_url}/{doc}', {'publishedAt': now}, hdr, method='PUT')
        art = res.get('data', art) if isinstance(res, dict) else art
        print(f'      publishedAt={art.get("publishedAt")}')
    else:
        print('[2/5] 已发布，跳过')

    # 3. 后台校验
    print('[3/5] 后台校验 ...')
    e2, _ = find_existing(hdr, data['originId'], data['slug'], admin_url)
    if not e2:
        print('[FAIL] 后台查不到'); sys.exit(3)
    print(f'      id={e2["id"]} publishedAt={e2.get("publishedAt")} content长度={len(e2.get("content") or "")}')

    # 4. 前端可见性校验
    print('[4/5] 前端校验 ...')
    u = f'{front_url}?filters[slug][$eq]={urllib.parse.quote(data["slug"])}'
    code, front = http(u, headers=hdr)
    vis = code == 200 and isinstance(front, dict) and bool(front.get('data'))
    print(f'      {front_site}/api 可见={vis} (HTTP {code})')

    # 5. 回写慧思数据库
    if no_wb:
        print('[5/5] 跳过回写（--no-writeback）')
    elif vis and e2.get('publishedAt'):
        print('[5/5] 回写慧思数据库 PUSH_STATUS=1 ...')
        code, res = http(ANCHOR_API, {
            'cmd': 'com.awspaas.user.apps.xfsai.knowledge.webapi.update',
            'boName': BO_NAME,
            'recordData': json.dumps({'PUSH_STATUS': '1',
                                      'PUBLISH_TIME': now[:19].replace('T', ' ')}, ensure_ascii=False),
            'id': rec['ID'], 'msaSvcId': MSA_SVC_ID,
        }, form=True)
        print('      ', json.dumps(res, ensure_ascii=False)[:250] if isinstance(res, (dict, list)) else res)
    else:
        print('[5/5] 校验未通过，不回写')

    print('\n=== DONE ===')
    print('文章页:', front_site + '/knowledge-base/' + data['slug'])
    print('documentId:', doc, '| originId:', data['originId'])


if __name__ == '__main__':
    main()
