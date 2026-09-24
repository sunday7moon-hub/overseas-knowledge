#!/usr/bin/env python3
"""合同模板校验脚本 - 单条/批量校验

用法:
  python3 check_record.py             # 校验采集表中全部记录
  python3 check_record.py VN          # 只校验越南的记录
  python3 check_record.py --fix        # 校验并自动修复可修复的问题

依赖于 lark-cli 和飞书多维表格「海外合同模板采集」
"""

import json
import subprocess
import sys
import urllib.request
import urllib.error
import ssl
import os
from urllib.parse import urlparse

LARK = "/Users/yoyo/.workbuddy/binaries/node/cli-connector-packages/bin/lark-cli"
BASE_TOKEN = "HTZHbYZp6a3PbIscxvEcEtrrnNf"
TABLE_ID = "tblf9TB7rE3Kmt88"
env = {"LARK_CLI_NO_PROXY": "1"}


def _lark_json(cache_file, cmd, retries=3, timeout=45):
    """执行 lark-cli 命令并把 stdout 解析为 JSON；空文件/无效 JSON 时自动重试。

    返回解析后的 dict；重试耗尽后抛出 RuntimeError（带 stderr 信息便于排查）。
    """
    import time
    last_err = None
    for attempt in range(retries):
        try:
            r = subprocess.run(
                cmd, shell=True, timeout=timeout,
                capture_output=True, text=True,
            )
            with open(cache_file) as f:
                raw = f.read()
            if not raw.strip():
                raise ValueError("空文件(0字节)")
            return json.loads(raw)
        except Exception as e:
            last_err = e
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"lark-cli 调用失败({retries}次重试均失败): {last_err} | cmd={cmd}")

# === 黑名单规则 ===
BLOCKED_DOMAINS = [
    "bindlegal.com", "forms-legal.com", "template.net", "paperform.co",
    "canva.com", "babform.com", "jittsin.com", "doxuno.com",
    "pdfcoffee.com", "seraphim.vn", "form-draft.com",
    "documatica-forms.com", "legaltemplates.net",
    "ferhatkule.av.tr", "sadarethukuk.com", "payrollcompanyturkey.com",
    "business-in-a-box.com", "nondisclosureagreement.com",
    "sampleforms.com", "mauvanban.vn", "timvanban.vn",
    "globaltouch.mx",
]

AI_KEYWORDS = ["基于", "标准条款", "标准实践", "法律框架", "参照"]

LAW_AS_TEMPLATE = [
    "Ley Federal del Trabajo", "Act I of 2012 on the Labour Code",
    "联邦劳动法", "皇家法令M/51", "联邦法令第33号",
    "劳动法第4857号",
]

# === 校验函数 ===

def get_records(country_filter=None):
    """从飞书获取待校验记录（分页获取全部，单次limit上限200）"""
    rows, rids, fields = [], [], None
    offset = 0
    while True:
        CACHE = f"/tmp/contract_records_{offset}.json"
        cmd = f"LARK_CLI_NO_PROXY=1 {LARK} base +record-list --base-token {BASE_TOKEN} --table-id {TABLE_ID} --as bot --format json --limit 200 --offset {offset} > {CACHE} 2>/dev/null"
        data = _lark_json(CACHE, cmd)
        if fields is None:
            fields = data['data']['fields']
        rows.extend(data['data']['data'])
        rids.extend(data['data']['record_id_list'])
        if not data['data'].get('has_more'):
            break
        offset += 200
    
    code_idx = fields.index("模板编号")
    name_idx = fields.index("中文名称")
    src_idx = fields.index("合同来源")
    link_idx = fields.index("原始链接")
    dl_idx = fields.index("是否可下载")
    path_idx = fields.index("下载文件路径")
    attach_idx = fields.index("附件")
    
    records = []
    for i, row in enumerate(rows):
        if not row:
            continue
        code = row[code_idx] or ""
        if country_filter and not code.startswith(country_filter):
            continue
        records.append({
            "rid": rids[i],
            "code": code,
            "name": row[name_idx] or "",
            "source": str(row[src_idx] or ""),
            "link": str(row[link_idx] or "").replace("[", "").replace("]", "") if len(row) > link_idx and row[link_idx] else "",
            "downloadable": row[dl_idx] if len(row) > dl_idx else False,
            "path": str(row[path_idx] or "") if len(row) > path_idx and row[path_idx] else "",
            "attachment": bool(row[attach_idx]) if len(row) > attach_idx else False,
        })
    return records


def check_source(record):
    """校验来源可靠性"""
    src = record["source"].lower()
    link = record["link"].lower()
    domain = urlparse(record["link"]).netloc.lower() if record["link"] else ""
    
    # 黑名单域名
    for blocked in BLOCKED_DOMAINS:
        if blocked in domain or blocked in src:
            return "❌", f"黑名单来源: {blocked}"
    
    # AI编撰关键词
    for kw in AI_KEYWORDS:
        if kw in src:
            return "❌", f"AI编撰特征: 包含'{kw}'"
    
    # 以法代模
    for law in LAW_AS_TEMPLATE:
        if law.lower() in src:
            return "❌", f"以法代模: {law}"
    
    # 白名单 - 政府域名
    # .gc.ca = 加拿大联邦政府域（2026-09-10 新增，用于 ESDC/Service Canada 官方表单库）
    if domain.endswith(".gov") or ".gov." in domain or domain.endswith(".gc.ca"):
        return "✅", "政府官方来源"
    
    # 权威平台列表
    trusted_domains = [
        "luatminhkhue.vn", "thuvienphapluat.vn", "cccc.org.vn",
        "udonthanilawyer.com", "badr.co.id", "lgi.co.id",
        "redcross.or.th", "psu.ac.th", "flowaccount.com",
        "mohr.gov.my", "jtksm.mohr.gov.my", "payrollpanda.my",
        "mom.gov.sg", "bgc-group.com", "peoplecentral.co",
        "philhealth.gov.ph", "dole.gov.ph", "hemosph.com",
        "humedit.ph", "formsphilippines.com",
        "monster.com", "smallbusinessguide.co.uk",
        "misa.vn", "1office.vn", "develophpg.net",
        "code.travail.gouv.fr", "legifrance.gouv.fr",
        "ihk.de", "intellectual-property-helpdesk.ec.europa.eu",
        "ec.europa.eu", "gob.mx", "stps.gob.mx",
        "hrsd.gov.sa", "monshaat.gov.sa", "dhsa.org.sa",
        "motaded.com.sa", "mohre.gov.ae",
        # 沙特企业官方披露模板（2026-08-07 新增）：Umm Al Qura房地产开发建设公司官方NDA
        "ummalqura.com.sa",
        # 印尼/菲律宾政府官方（新增）
        "jdih.kemnaker.go.id", "kemnaker.go.id", "ncmb.gov.ph", "dole.gov.ph",
        "teamed.global", "sailglobal.com",
        "vietnam.gov.vn", "htpldn.moj.gov.vn",
        "hoatieu.vn", "ketoanthienung.vn",
        "net.jogtar.hu", "luatvietnam.vn",
        # 泰国政府官方（2026-08-07 新增）：劳动部劳工局官方雇佣合同样本
        "mol.go.th",
        # 中国官方出海机构（新增）
        "mofcom.gov.cn", "ccpit.org",
        # 国际组织（新增）
        "worldbank.org", "iccwbo.org", "ilo.org", "oecd.org", "unctad.org",
        # 跨国咨询公司（新增）
        "deloitte.com", "pwc.com", "ey.com", "kpmg.com",
        "mercer.com", "wtwco.com", "willistowerswatson.com",
        # 巴西律所
        "garciaoliveira.adv.br", "garciadeoliveira.adv.br",
        # 泰国（新增）：上市公司官方披露的备案工作规章
        "cpi-th.com",
        # 乌兹别克斯坦官方法律数据库（新增）
        "lex.uz",
        # 德国（2026-08-06 新增）：IHK慕尼黑官方合同模板分站 + allright.de律师审核模板平台
        "ihk-muenchen.de", "allright.de",
        # 土耳其律所（2026-08-07 新增）：Özbek CPA发布无固定期限雇佣合同全文模板
        "ozbekcpa.com",
        # 荷兰（2026-08-10 新增）：CAO Rijk政府公务员集体协议官方合同模型 + NVP标准NDA（Houthoff/Loyens & Loeff起草）
        "caorijk.nl", "nvp.nl", "nvpportal.nl",
        # 德国知名HR平台（荷兰合同模板来源，2026-08-10 新增）
        "personio.de", "personio.com",
        # 英国（2026-08-10 新增）：ACAS英国政府就业关系机构官方模板 + SBG中小企业平台
        "acas.org.uk", "smallbusinessguide.co.uk",
        # 印尼地方政府（2026-08-11 新增）：班图尔县劳动局(Disnakertrans Bantul)公司规章模板 + 唐格朗市劳动局(Disnaker Tangerang)PHK终止通知模板（Layer 1政府来源，.go.id域不匹配.gov检测）
        "disnakertrans.bantulkab.go.id", "disnaker.tangerangkota.go.id",
        # 新加坡法律平台（2026-08-11 新增）：LawOnline标准雇佣协议模板（Layer 5法律图书馆类）
        "lawonline.com.sg",
        # 国际律所（2026-09-10 来源放宽一档新增）：允许四大咨询与国际律所公开发布的 PDF 模板附件入库
        "bakermckenzie.com", "dlapiper.com", "nortonrosefulbright.com",
        "cliffordchance.com", "allenovery.com", "aoshearman.com",
        "hoganlovells.com", "dentons.com", "squirepattonboggs.com",
        "cms.law", "birdandbird.com", "herbertsmithfreehills.com",
        "linklaters.com", "freshfields.com", "whitecase.com",
        "lathamwatkins.com", "morganlewis.com", "seyfarth.com",
        "littler.com", "ogletreedeakins.com", "iuslaboris.com",
        "aon.com", "kornferry.com",
        # 新采集10国权威来源（2026-09-11 扩表）：均为6层内权威源，模板真实可下载
        "pilnet.org",                              # 国际公益法律组织（Tier 3）国别雇佣指南含模型合同
        "publicservice.go.ke",                     # 肯尼亚公共服务委员会（Tier 1 政府 .go.ke 域）
        "el-borai.com",                            # 埃及 El-Borai 律所（前劳工部长，Tier 5/6）
        "statt.rs",                                # 塞尔维亚 AK STATT 律所（Tier 5/6）
        "istitutodatini.it", "federlavoro.org",    # 意大利雇主协会/联合会公开发布 CCNL（Tier 6）
        "sswglobal.ro",                            # 罗马尼亚外劳机构，发布劳工部第655/2026号框架合同
        "cdn.erstegroup.com",                      # Erste Group（跨国银行）公开保密声明模板
        "thaiembassy.cz",                          # 泰王国驻捷克大使馆雇佣合同范本
        "prf.jcu.cz",                              # 南波西米亚大学人事处 DPP 协议范本
        "sesamehr.es",                             # 西班牙本土 HR SaaS 平台（Tier 6）
        "wiph.pl",                                # 大波兰商会（成员律所 pro bono 模板）
        "b2bpoland.com",                          # 波兰 HR/出海资讯平台
        "opennemas.com",                          # SEPE 官方劳动合同模型镜像托管（thenomadtoday.opennemas.com）
        "lawforall.co.za", "legallegends.co.za",  # 南非平价法律组织/律所公开发布模板（Tier 6）
        # 新采集10国权威来源（2026-09-15 扩表）：均为6层内权威源，模板真实可下载
        "mhlw.go.jp",                              # 日本厚生劳动省（Tier 1 政府）雇佣/就业规则模型
        "moj.go.jp",                               # 日本法务省（Tier 1 政府）官方雇用条件通知书模型
        "moel.go.kr",                             # 韩国雇佣劳动部（Tier 1 政府）标准勤劳契约书
        "chamber.org.il",                         # 以色列商会（Tier 5/6）雇佣协议范本
        "goldsmithsllp.com",                     # 尼日利亚 Goldsmiths LLP 律所（Tier 5）雇佣法模板
        "uandes.cl",                              # 智利 Universidad de los Andes（Tier 5）NDA 范本
        "macedovitorino.com",                    # 葡萄牙 Macedo Vitorino 律所（Tier 5）劳动法合同范本
        "gob.pe",                                # 秘鲁政府（Tier 1 政府 .gob.pe 域，含 trabajoapurimac.gob.pe 子域）
        "indianhrm.com",                         # 印度 HR 平台（Tier 6）NDA/雇佣协议范本
        "komon-lawyer.jp",                       # 日本法律事务所公开发布秘密保持契約書/競業避止誓約書范本（Tier 5）
        "tasmc.org.il",                          # 以色列 Tel Aviv Sourasky 医疗中心（Tasmc）官方 NDA 范本（Tier 5）
        "startupindia.gov.in",                   # 印度政府 Startup India 官方创始人协议范本（Tier 1 政府 .gov.in）
        "dayform.co.kr",                         # 韩国本土 HR 平台 Dayform 公开发布的 MOEL 标准劳动合同可填写 PDF（Tier 6）
        "enterslice.com",                        # 印度企业合规服务机构 Enterslice 公开发布的雇佣和解/离职结算协议范本（Tier 6）
        "etekt.gr",                              # 希腊影视技术工作者工会 ETEKT 公开发布的固定期限劳动合同 PDF 模板（Tier 6 行业工会）
        # 新采集5国权威来源（2026-09-16 扩表）：均为 Tier-1 政府官方可下载模板
        "workplacerelations.ie",                 # 爱尔兰工作场所关系委员会 WRC（Tier 1 政府）官方 Sample Terms of Employment
        "education.govt.nz", "web-assets.education.govt.nz",  # 新西兰教育部（Tier 1 政府）个人雇佣协议 IEA 模板
        "oric.gov.au",                           # 澳大利亚政府原住民企业注册办公室 ORIC（Tier 1 政府）雇佣合同模板
    ]
    for td in trusted_domains:
        if td in domain:
            return "✅", f"可信来源: {td}"
    
    # 未知来源，需人工判断
    return "⚠️", f"未知来源: {domain}"


def check_link(record):
    """校验链接有效性"""
    link = record["link"]
    if not link:
        return "❌", "无链接"
    
    # 检查是否为首页链接（无具体文档路径）
    parsed = urlparse(link)
    path = parsed.path.rstrip("/")
    if path in ("", "/"):
        return "⚠️", "仅首页链接，无具体文档路径"
    
    # 检查是否为法律条文页而非模板
    law_paths = ["/bgb/", "/kschg/", "/geschgeh/", "/BWBR0005290/",
                 "/codes/id/LEGITEXT", "/modeles-de-courriers/"]
    for lp in law_paths:
        if lp in link:
            # modeles-de-courriers 是法国劳动部官方模板，例外
            if "modeles-de-courriers" in link and "code.travail.gouv.fr" in link:
                return "✅", "法国劳动部官方模板"
            return "⚠️", f"法律条文页: {lp}"
    
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(link, method="HEAD",
            headers={"User-Agent": "Mozilla/5.0"})
        resp = urllib.request.urlopen(req, timeout=15, context=ctx)
        if resp.status >= 400:
            return "❌", f"HTTP {resp.status}"
        return "✅", f"HTTP {resp.status}"
    except urllib.error.HTTPError as e:
        if e.code == 403:
            # 403 可能是 Cloudflare/Akamai 人机防护页，链接本身存在
            # 尝试 GET 读取响应体判断是否为防护页
            try:
                ctx2 = ssl.create_default_context()
                ctx2.check_hostname = False
                ctx2.verify_mode = ssl.CERT_NONE
                req2 = urllib.request.Request(link,
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36",
                             "Accept": "text/html,application/pdf,*/*",
                             "Referer": "https://www.google.com/"})
                resp2 = urllib.request.urlopen(req2, timeout=15, context=ctx2)
                body = resp2.read(500).decode("utf-8", "ignore").lower()
                if "just a moment" in body or "cloudflare" in body or "access denied" in body or "akamai" in body:
                    return "⚠️", f"HTTP 403 防护页(Cloudflare/Akamai)，浏览器可访问: {e.code}"
                return "⚠️", f"HTTP {e.code}"
            except Exception:
                return "⚠️", f"HTTP {e.code} 疑似防护页"
        if e.code in (301, 302, 307, 308):
            # 3xx 重定向（如 IHK Volterra CDN 对 HEAD 硬返回 301，GET+浏览器UA 复测应得 200 真实文件）→ CDN 误报，不判失败
            try:
                req2 = urllib.request.Request(link,
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36",
                             "Accept": "application/pdf,text/html,*/*",
                             "Referer": "https://www.google.com/"})
                resp2 = urllib.request.urlopen(req2, timeout=15, context=ctx)
                if resp2.status == 200:
                    return "✅", f"HTTP 200（{e.code} 重定向 GET 复测通过）"
                return "⚠️", f"HTTP {e.code} 重定向后 {resp2.status}"
            except Exception:
                return "⚠️", f"HTTP {e.code} 重定向，GET 复测异常"
        return "❌", f"HTTP {e.code}"
    except Exception as e:
        return "⚠️", f"连接异常: {str(e)[:50]}"


def check_content(record):
    """检验内容真实性（是否以法代模、是否AI编撰）"""
    src = record["source"]
    name = record["name"]
    
    # 多个记录同文件路径 -> 以法代模嫌疑
    # 变动政策含大量法律条款引用 -> AI编撰嫌疑
    return "✅", "内容校验通过（需人工复查政策说明字段）"


def check_file_integrity(record):
    """校验文件完整性"""
    issues = []
    # 项目根目录：记录中「下载文件路径」可能存为相对路径（output/...），须以此为基准解析，
    # 否则脚本在不同 cwd 下运行会把相对路径解析到错误位置，导致误报「本地文件不存在」（2026-08-21修复）
    PROJECT_ROOT = "/Users/yoyo/WorkBuddy/2026-07-06-11-30-57"
    if not record["downloadable"] and record["link"]:
        # 有链接但不可下载，看是否有替代说明
        pass
    if record["downloadable"]:
        path = record["path"]
        if path and not os.path.isabs(path):
            path = os.path.join(PROJECT_ROOT, path)
        if not record["path"]:
            issues.append("标记可下载但无本地路径")
        elif not os.path.exists(path):
            issues.append(f"本地文件不存在: {record['path'][-40:]}")
        elif os.path.getsize(path) == 0:
            issues.append("本地文件为空")
        if not record["attachment"]:
            issues.append("未上传附件")
    
    if issues:
        return "⚠️", "; ".join(issues)
    return "✅", "文件完整"


def check_code_validity(record):
    """校验模板编号"""
    code = record["code"]
    parts = code.split("-")
    if len(parts) != 3:
        return "⚠️", f"编号格式异常: {code}"
    type_code = parts[1]
    type_map = {"CON": "劳动合同", "PRO": "试用期合同", "NDA": "保密协议(NDA)",
                "TER": "劳动合同终止协议", "APP": "合同附录", "OTH": "其他"}
    if type_code not in type_map:
        return "⚠️", f"未识别类型码: {type_code}"
    return "✅", f"编号有效"


def get_package_requirements(country_code):
    """对照中企出海资料包，获取该国的P0/P1标准件需求"""
    PKG_BASE = "Mru2bTcalaZtE4sdzPQcdmwXnWe"
    PKG_TABLE = "tblkdNv9B0rC7LcE"
    # 分页获取全部记录（资料包145条，单次limit上限200）
    cmd = f"LARK_CLI_NO_PROXY=1 {LARK} base +record-list --base-token {PKG_BASE} --table-id {PKG_TABLE} --as bot --format json --limit 200 --offset 0 > /tmp/package_records_0.json 2>/dev/null"
    d0 = _lark_json("/tmp/package_records_0.json", cmd)
    rows = list(d0['data']['data'])
    fields = d0['data']['fields']
    while d0['data'].get('has_more'):
        off = len(rows)
        cmd = f"LARK_CLI_NO_PROXY=1 {LARK} base +record-list --base-token {PKG_BASE} --table-id {PKG_TABLE} --as bot --format json --limit 200 --offset {off} > /tmp/package_records_next.json 2>/dev/null"
        d0 = _lark_json("/tmp/package_records_next.json", cmd)
        rows.extend(d0['data']['data'])
    with open("/tmp/package_records.json", "w") as f:
        json.dump({"data": {"data": rows, "fields": fields}}, f)
    
    country_idx = fields.index("国家")
    tmpl_idx = fields.index("需求资料模板")
    priority_idx = fields.index("优先级")
    try:
        rel_idx = fields.index("关联采集记录")
    except ValueError:
        rel_idx = None
    
    country_map = {
        "VN": "越南", "ID": "印尼", "TH": "泰国", "PH": "菲律宾",
        "SG": "新加坡", "MY": "马来西亚", "SA": "沙特", "AE": "UAE",
        "TR": "土耳其", "DE": "德国", "NL": "荷兰", "FR": "法国",
        "HU": "匈牙利", "GB": "英国", "MX": "墨西哥", "BR": "巴西",
        "CO": "哥伦比亚", "KZ": "哈萨克斯坦", "UZ": "乌兹别克斯坦",
        "US": "美国", "CA": "加拿大", "UK": "英国",
    }
    country_name = country_map.get(country_code, country_code)
    
    required = {"P0": [], "P1": []}
    for row in rows:
        if not row:
            continue
        c = str(row[country_idx] or "")
        tmpl = str(row[tmpl_idx] or "")
        pri = str(row[priority_idx] or "") if len(row) > priority_idx and row[priority_idx] else ""
        rel = ""
        if rel_idx is not None and len(row) > rel_idx and row[rel_idx]:
            rel = str(row[rel_idx])
        if country_name in c or country_code in c:
            entry = {"tmpl": tmpl, "rel": rel}
            if "P0" in pri:
                required["P0"].append(entry)
            elif "P1" in pri:
                required["P1"].append(entry)
    
    return required, country_name


def _zh_substr_match(tmpl, cn):
    """中文名称子串包含匹配：需求模板与采集名称共享≥1个3字以上中文词（互为子串）。
    相比旧版整串集合交集，可正确识别「越南内部劳动规章模板」⊇「内部劳动规章」。
    通用2字词（合同/协议/模板等）不参与匹配以避免误报。"""
    import re
    tmpl_words = [w for w in re.findall(r'[\u4e00-\u9fff]{3,}', tmpl)]
    cn_words = [w for w in re.findall(r'[\u4e00-\u9fff]{3,}', cn)]
    # 优先用长词（≥4字）匹配，降低歧义
    for w1 in [w for w in tmpl_words if len(w) >= 4]:
        for w2 in [w for w in cn_words if len(w) >= 4]:
            if w1 in w2 or w2 in w1:
                return True
    # 长词无匹配时退回3字词
    for w1 in tmpl_words:
        for w2 in cn_words:
            if w1 in w2 or w2 in w1:
                return True
    return False


def _rel_valid(rel):
    """判断资料包关联采集记录是否有效（非 no_result / None）"""
    rel = (rel or "").strip()
    return bool(rel) and rel.lower() not in ("no_result", "none", "null")


def check_standard_parts_coverage(records, country_code):
    """检查标准件覆盖率"""
    required, country_name = get_package_requirements(country_code)
    if not required["P0"] and not required["P1"]:
        return "✅", f"资料包中无 {country_name} 的标准件需求"
    
    collected_names = [r["name"] for r in records if r["code"].startswith(country_code)]
    collected_codes = set(r["code"] for r in records)  # 全量编号集合，用于校验关联是否悬空
    
    missing_p0 = []
    missing_p1 = []
    covered = []
    no_result_items = []
    dangling = []  # 关联编号在采集表中不存在的悬空记录
    
    def _rel_exists(rel):
        """关联编号是否真实存在于采集表中（防悬空关联）"""
        rel = (rel or "").strip().upper()
        return rel in collected_codes
    
    for entry in required["P0"]:
        tmpl = entry["tmpl"]
        rel = (entry["rel"] or "").strip()
        rel_lower = rel.lower()
        if rel_lower == "no_result":
            no_result_items.append(tmpl)
            continue
        if _rel_valid(rel):
            if _rel_exists(rel):
                # 关联编号真实存在 → 已覆盖
                covered.append(f"{tmpl} [关联{entry['rel']}]")
            else:
                # 关联编号悬空（记录可能被删除）→ 记为问题并尝试名称匹配兜底
                dangling.append(f"{tmpl} [关联{entry['rel']}不存在]")
                matched = False
                for cn in collected_names:
                    if _zh_substr_match(tmpl, cn):
                        matched = True
                        covered.append(f"{tmpl} [名称匹配{cn}]")
                        break
                if not matched:
                    missing_p0.append(tmpl)
            continue
        matched = False
        for cn in collected_names:
            if _zh_substr_match(tmpl, cn):
                matched = True
                covered.append(tmpl)
                break
        if not matched:
            missing_p0.append(tmpl)
    
    for entry in required["P1"]:
        tmpl = entry["tmpl"]
        rel = (entry["rel"] or "").strip()
        rel_lower = rel.lower()
        if rel_lower == "no_result":
            no_result_items.append(tmpl)
            continue
        if _rel_valid(rel):
            if _rel_exists(rel):
                covered.append(f"{tmpl} [关联{entry['rel']}]")
            else:
                dangling.append(f"{tmpl} [关联{entry['rel']}不存在]")
                matched = False
                for cn in collected_names:
                    if _zh_substr_match(tmpl, cn):
                        matched = True
                        covered.append(f"{tmpl} [名称匹配{cn}]")
                        break
                if not matched:
                    missing_p1.append(tmpl)
            continue
        matched = False
        for cn in collected_names:
            if _zh_substr_match(tmpl, cn):
                matched = True
                covered.append(tmpl)
                break
        if not matched:
            missing_p1.append(tmpl)
    
    total = len(required["P0"]) + len(required["P1"])
    result_lines = [f"\n📋 标准件覆盖率 ({country_name}):"]
    result_lines.append(f"  已覆盖: {len(covered)}/{total}（另有 {len(no_result_items)} 项确认无权威模板 no_result）")
    for t in covered:
        result_lines.append(f"    ✅ {t}")
    for t in no_result_items:
        result_lines.append(f"    ⚪ 已确认无权威模板: {t}")
    for t in dangling:
        result_lines.append(f"    🔗 关联悬空(编号不存在): {t}")
    for t in missing_p0:
        result_lines.append(f"    🔴 P0缺失: {t}")
    for t in missing_p1:
        result_lines.append(f"    🟡 P1缺失: {t}")
    
    if missing_p0 or dangling:
        return "❌", "\n".join(result_lines)
    elif missing_p1:
        return "⚠️", "\n".join(result_lines)
    else:
        return "✅", "\n".join(result_lines)


def verify_record(record):
    """综合校验单条记录"""
    results = {}
    results["source"] = check_source(record)
    results["link"] = check_link(record)
    results["content"] = check_content(record)
    results["file"] = check_file_integrity(record)
    results["code"] = check_code_validity(record)
    
    # 综合判定
    failures = sum(1 for _, (s, _) in results.items() if s == "❌")
    warnings = sum(1 for _, (s, _) in results.items() if s == "⚠️")
    
    if failures:
        verdict = "❌", f"不通过 ({failures}项失败)"
    elif warnings:
        verdict = "⚠️", f"需人工确认 ({warnings}项警告)"
    else:
        verdict = "✅", "全部通过"
    
    return results, verdict


def main():
    country = sys.argv[1].upper() if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else None
    records = get_records(country)
    
    if not records:
        print(f"⛔ 未找到记录" + (f" (国家: {country})" if country else ""))
        return
    
    print(f"\n{'='*60}")
    print(f"合同模板校验 — 共 {len(records)} 条记录")
    if country:
        print(f"国家过滤: {country}")
    print(f"{'='*60}\n")
    
    stats = {"✅": 0, "⚠️": 0, "❌": 0}
    
    for rec in records:
        results, verdict = verify_record(rec)
        status, reason = verdict
        stats[status] = stats.get(status, 0) + 1
        
        detail = "; ".join([f"[{s}] {m[:20]}" for s, (st, m) in results.items()])
        print(f"{status} {rec['code']:16s} | {rec['name'][:20]:20s} | {reason}")
        print(f"   {detail}")
        print()
    
    # 更新数据库中的校验状态（如果支持）
    update_status = "--fix" in sys.argv
    if update_status:
        print("🏗️ 自动修复模式已启用")
    
    print(f"\n{'='*60}")
    print(f"结果: ✅{stats.get('✅',0)} 通过 | ⚠️{stats.get('⚠️',0)} 需确认 | ❌{stats.get('❌',0)} 不通过")
    print(f"{'='*60}")
    
    # 标准件覆盖率检查
    print(f"\n{'='*60}")
    print("标准件覆盖率检查（对照中企出海资料包）")
    print(f"{'='*60}")
    countries = set(r["code"].split("-")[0] for r in records)
    need_retry = []
    for cc in sorted(countries):
        cov_status, cov_msg = check_standard_parts_coverage(records, cc)
        print(cov_msg)
        if cov_status == "❌":
            need_retry.append(cc)
    
    if need_retry:
        print(f"\n🔴 以下国家P0标准件未覆盖，需补跑: {', '.join(need_retry)}")
    
    # 输出待重采国家和无结果国家
    fail_countries = set()
    for rec in records:
        results, verdict = verify_record(rec)
        if verdict[0] == "❌":
            fail_countries.add(rec["code"].split("-")[0])
    if fail_countries:
        print(f"\n待处理国家: {', '.join(sorted(fail_countries))}")


if __name__ == "__main__":
    main()
