#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
百度统计统一凭据层（唯一真相源）
================================================
设计铁律（改动前请先读完）：

1. **本文件绝不硬编码任何 token / secret**。
   本技能会同步到 public 仓库（overseas-knowledge），
   任何写死在此的凭据都等于公开泄露百度统计全站数据访问权。

2. **凭据读取优先级**（高 → 低）：
     ① 环境变量 `BAIDU_TONGJI_TOKEN`  → 仅 access_token，临时/CI 用
     ② 环境变量 `BAIDU_TONGJI_SECRETS` → 指向自定义 secrets json 路径
     ③ 默认文件 `~/.workbuddy/secrets/baidu_tongji.json`（权限 600）

3. **openapi.baidu.com 必须绕过代理**。
   本机沙箱装有机房代理，百度开放 API 走代理会静默返回空/异常；
   所有请求统一经本模块的 `api_get()`，它已内置空 ProxyHandler。

4. **refresh_token 每次刷新即轮换**（旧值立即作废）。
   因此刷新成功后必须回写 secrets 文件，否则下一个脚本会拿着废 token 去刷。
   回写走 `_locked_update()`（O_EXCL 文件锁），避免多脚本并发互相覆盖。

用法：
    from _baidu_auth import SITE_ID, api_get, get_access_token, parse_rows
    tok = get_access_token()          # 需要 token 原文时才调
    d   = api_get("trend/time/a", start_date="20260901", end_date="20260907")

    # 脚本内使用（推荐写法，自动处理 sys.path）：
    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from _baidu_auth import api_get, parse_rows
"""

import json
import os
import ssl
import sys
import time
import urllib.parse
import urllib.request

__all__ = [
    "SECRETS_PATH", "SITE_ID", "CLIENT_ID", "CLIENT_SECRET",
    "get_access_token", "refresh_access_token", "refresh_token_value",
    "api_get", "parse_rows", "credential_status", "AuthError",
]

SECRETS_PATH = os.environ.get(
    "BAIDU_TONGJI_SECRETS",
    os.path.expanduser("~/.workbuddy/secrets/baidu_tongji.json"),
)
API_BASE = "https://openapi.baidu.com/rest/2.0/tongji/report/getData"
OAUTH_URL = "https://openapi.baidu.com/oauth/2.0/token"

_SSL_CTX = ssl.create_default_context()
# 绕过代理：进程级安装空 ProxyHandler，之后所有 urllib 请求都走直连
urllib.request.install_opener(urllib.request.build_opener(urllib.request.ProxyHandler({})))

# 内存缓存，避免同一次运行内反复探测
_CACHED_TOKEN = None


class AuthError(RuntimeError):
    """凭据缺失或全部失效，需要人工介入（重走 OAuth 授权）。"""


# --------------------------------------------------------------------------
# 凭据装载
# --------------------------------------------------------------------------
def _load_secrets():
    try:
        with open(SECRETS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise AuthError(
            "凭据文件不存在：%s\n"
            "请创建该文件（权限 600），字段：site_id / client_id / client_secret / "
            "refresh_token / access_token" % SECRETS_PATH
        )
    except json.JSONDecodeError as e:
        raise AuthError("凭据文件不是合法 JSON：%s（%s）" % (SECRETS_PATH, e))


_SEC = None


def _sec():
    global _SEC
    if _SEC is None:
        _SEC = _load_secrets()
    return _SEC


def __getattr__(name):  # PEP 562：模块级惰性常量，避免 import 即报错
    if name == "SITE_ID":
        return _sec().get("site_id", 22551575)
    if name == "CLIENT_ID":
        return _sec()["client_id"]
    if name == "CLIENT_SECRET":
        return _sec()["client_secret"]
    raise AttributeError(name)


# --------------------------------------------------------------------------
# 底层请求
# --------------------------------------------------------------------------
def _raw_get(url, timeout=40):
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, context=_SSL_CTX, timeout=timeout) as resp:
        body = resp.read().decode("utf-8", "replace")
    return json.loads(body)


def _locked_update(patch, retries=5):
    """带文件锁地更新 secrets 文件（防止并发刷新互相覆盖）。"""
    lock = SECRETS_PATH + ".lock"
    for _ in range(retries):
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            break
        except FileExistsError:
            time.sleep(0.4)
    else:
        return False
    try:
        data = _load_secrets()
        data.update(patch)
        tmp = SECRETS_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.chmod(tmp, 0o600)
        os.replace(tmp, SECRETS_PATH)
        global _SEC
        _SEC = data
        return True
    finally:
        os.close(fd)
        try:
            os.unlink(lock)
        except OSError:
            pass


def _probe(token):
    """轻量探测 access_token 是否有效。返回 None=有效，否则返回错误描述。"""
    p = {
        "access_token": token, "site_id": _sec().get("site_id", 22551575),
        "method": "trend/time/a", "start_date": "20260901", "end_date": "20260901",
        "metrics": "pv_count", "max_results": "0", "gran": "day",
    }
    try:
        d = _raw_get(API_BASE + "?" + urllib.parse.urlencode(p), timeout=20)
    except Exception as e:
        return "请求异常：%s" % e
    if d.get("error_code"):
        return "%s: %s" % (d.get("error_code"), d.get("error_msg"))
    if d.get("result") is None:
        return "返回体无 result（可能是站点无数据或 token 受限）"
    return None


def refresh_access_token():
    """用 refresh_token 换新 token，并**立即回写** secrets（轮换纪律）。"""
    s = _sec()
    url = "%s?grant_type=refresh_token&refresh_token=%s&client_id=%s&client_secret=%s" % (
        OAUTH_URL,
        urllib.parse.quote(s["refresh_token"]),
        s["client_id"],
        s["client_secret"],
    )
    d = _raw_get(url, timeout=25)
    if d.get("error"):
        raise AuthError(
            "refresh_token 刷新失败：%s - %s\n"
            "→ refresh_token 已彻底失效，必须重走一次 OAuth 浏览器授权。"
            % (d.get("error"), d.get("error_description"))
        )
    if _locked_update({
        "access_token": d["access_token"],
        "refresh_token": d.get("refresh_token", s["refresh_token"]),
        "access_token_expires_at": _expiry(d.get("expires_in")),
        "updated_at": time.strftime("%Y-%m-%d"),
    }):
        print("OK: refresh_token 已刷新并回写 %s" % SECRETS_PATH, file=sys.stderr)
    else:
        print("WARN: 刷新成功但回写失败（锁占用），请手工更新 %s" % SECRETS_PATH,
              file=sys.stderr)
    return d["access_token"]


def get_access_token(force_refresh=False):
    """返回可用 access_token：env → 缓存 → secrets 内值（探测）→ 刷新。"""
    global _CACHED_TOKEN
    env_tok = os.environ.get("BAIDU_TONGJI_TOKEN")
    if env_tok:
        return env_tok
    if _CACHED_TOKEN and not force_refresh:
        return _CACHED_TOKEN

    if not force_refresh:
        cur = _sec().get("access_token")
        if cur:
            err = _probe(cur)
            if err is None:
                _CACHED_TOKEN = cur
                return cur
            print("WARN: 现有 access_token 失效（%s），尝试刷新…" % err, file=sys.stderr)

    _CACHED_TOKEN = refresh_access_token()
    return _CACHED_TOKEN


def refresh_token_value():
    """返回当前 refresh_token（脱敏场景请勿打印原文）。"""
    return _sec().get("refresh_token")


def _expiry(expires_in):
    """把 expires_in（秒）折算成到期日字符串，便于人工判断。"""
    try:
        return time.strftime("%Y-%m-%d", time.localtime(time.time() + int(expires_in)))
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------
# 便捷取数
# --------------------------------------------------------------------------
def api_get(method, start_date, end_date, metrics="pv_count,visitor_count",
            max_results="0", token=None, **extra):
    """调 report/getData。extra 直接并入查询串（如 gran="day"、visitor="new"）。"""
    p = {
        "access_token": token or get_access_token(),
        "site_id": _sec().get("site_id", 22551575),
        "method": method, "start_date": start_date, "end_date": end_date,
        "metrics": metrics, "max_results": str(max_results),
    }
    p.update({k: str(v) for k, v in extra.items()})
    d = _raw_get(API_BASE + "?" + urllib.parse.urlencode(p))
    if d.get("error_code"):
        raise RuntimeError("百度统计 API 错误 %s: %s" % (d.get("error_code"), d.get("error_msg")))
    return d


def parse_rows(d):
    """把 getData 响应展平成 [{_dim: 维度, 指标: 值}, ...]；空响应返回 []。"""
    r = (d or {}).get("result") or {}
    if not r:
        return []
    fields = r.get("fields", [])
    items = (r.get("items", [[], []]) + [[], []])[:2]
    dims, mets = items
    out = []
    for i, dim in enumerate(dims):
        dv = dim[0] if isinstance(dim, list) and dim else dim
        if isinstance(dv, dict):
            dv = dv.get("name", str(dv))
        row = {"_dim": str(dv)}
        if i < len(mets):
            for j, fn in enumerate(fields[1:]):
                if j < len(mets[i]):
                    row[fn] = mets[i][j]
        out.append(row)
    return out


def credential_status():
    """体检用：返回脱敏后的凭据状态字典（不泄露 token 原文）。"""
    def mask(v):
        if not v:
            return None
        return v[:12] + "…" + v[-6:] if len(v) > 22 else v[:6] + "…"
    try:
        s = _load_secrets()
    except AuthError as e:
        return {"secrets_path": SECRETS_PATH, "ok": False, "error": str(e)}
    at = s.get("access_token")
    return {
        "secrets_path": SECRETS_PATH,
        "ok": True,
        "perm": oct(os.stat(SECRETS_PATH).st_mode)[-3:],
        "site_id": s.get("site_id"),
        "client_id": mask(s.get("client_id")),
        "client_secret": mask(s.get("client_secret")),
        "refresh_token": mask(s.get("refresh_token")),
        "access_token": mask(at),
        "access_token_expires_at": s.get("access_token_expires_at"),
        "updated_at": s.get("updated_at"),
        "access_token_alive": (None if not at else (_probe(at) is None)),
    }


if __name__ == "__main__":
    print(json.dumps(credential_status(), ensure_ascii=False, indent=2))
