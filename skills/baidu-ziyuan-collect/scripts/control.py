"""Browser Bridge - CLI 客户端 v2（抗抖动加固版）

用法（与 v1 完全兼容，旧脚本无需改动）：

    from control import Bridge

    b = Bridge()
    b.navigate("https://admin.humancehr.com/admin")
    print(b.get_text())
    b.click_by_text("数据统计", selector="a")
    b.get_html()
    b.screenshot("page.png")

v2 相比 v1 的提升（接通率）：
    1. 【自动重试】遇到"扩展未连接/连接中断/超时"自动退避重试（默认 3 次）。
    2. 【等待重连】重试前先 wait_ready()，等扩展从 MV3 30s 回收中恢复，再发命令。
    3. 【特权页自愈】读到 chrome://newtab 这类特权页时报错 → 自动重新导航到上次目标页再读。
    4. 【错误分类】BridgeUnavailable / BridgeTimeout / BridgePageError / BridgeIndeterminate，
       调用方可分别处理；有副作用命令不会被静默重复执行。
    5. 【可观测】b.stats / b.status() 可直接看接通率与扩展重连次数。

打开调试输出：
    b = Bridge(verbose=True)
"""

import json
import time
from typing import Any, Optional

import websockets.sync.client as ws_client
from websockets.exceptions import ConnectionClosed

BRIDGE_URL = "ws://localhost:9334"


# ── 错误类型 ────────────────────────────────────────────────

class BridgeError(RuntimeError):
    """Bridge 通用错误"""


class BridgeUnavailable(BridgeError):
    """扩展不在线 / 连接中断（可重试）"""


class BridgeTimeout(BridgeError):
    """等待响应超时（可重试）"""


class BridgePageError(BridgeError):
    """目标页不可脚本化，例如 chrome:// 特权页（可通过重新导航自愈）"""


class BridgeIndeterminate(BridgeError):
    """命令已下发但结果未知（为避免重复执行，不自动重试）"""


_ERROR_MAP = (
    ("NO_EXTENSION", BridgeUnavailable),
    ("DISCONNECTED", BridgeUnavailable),
    ("未连接", BridgeUnavailable),
    ("断开", BridgeUnavailable),
    ("Connection", BridgeUnavailable),
    ("TIMEOUT", BridgeTimeout),
    ("超时", BridgeTimeout),
    ("INDETERMINATE", BridgeIndeterminate),
    ("chrome://", BridgePageError),
    ("Cannot access", BridgePageError),
    ("特权页", BridgePageError),
)


def _classify(err: str, etype: str = "") -> BridgeError:
    blob = f"{etype} {err}"
    for key, cls in _ERROR_MAP:
        if key in blob:
            return cls(err)
    return BridgeError(err)


class Bridge:
    """与 Browser Bridge Extension 通信的客户端"""

    def __init__(self, url: str = BRIDGE_URL, retries: int = 3,
                 wait_ready: float = 35.0, verbose: bool = False):
        self._url = url
        self._retries = retries
        self._wait_ready = wait_ready
        self._verbose = verbose
        self._last_url: Optional[str] = None
        self.stats = {"calls": 0, "ok": 0, "retried": 0, "failed": 0}

    # ─── 内部通信 ───────────────────────────

    def _log(self, msg: str) -> None:
        if self._verbose:
            print(f"[bridge] {msg}")

    def _call_once(self, method: str, params: Optional[dict] = None,
                   timeout: float = 90.0) -> Any:
        msg: dict[str, Any] = {"role": "cli", "method": method}
        if params:
            msg["params"] = params
        try:
            with ws_client.connect(self._url, max_size=64 * 1024 * 1024) as ws:
                ws.send(json.dumps(msg, ensure_ascii=False))
                raw = ws.recv(timeout=timeout)
        except TimeoutError as e:
            raise BridgeTimeout(f"等待 {timeout:.0f}s 未收到响应") from e
        except ConnectionClosed as e:
            raise BridgeUnavailable(f"与 bridge server 的连接中断: {e}") from e
        except OSError as e:
            raise BridgeUnavailable(f"无法连接 bridge server（{self._url}）: {e}") from e

        resp = json.loads(raw) if raw else {}
        if resp.get("error"):
            raise _classify(str(resp["error"]), str(resp.get("errorType", "")))
        return resp.get("result")

    def _call(self, method: str, params: Optional[dict] = None, timeout: float = 90.0,
              retries: Optional[int] = None, retryable: Optional[bool] = None) -> Any:
        attempts = self._retries if retries is None else retries
        self.stats["calls"] += 1
        last: Optional[BridgeError] = None

        for i in range(attempts + 1):
            try:
                result = self._call_once(method, params, timeout)
                self.stats["ok"] += 1
                return result
            except BridgeIndeterminate:
                self.stats["failed"] += 1
                raise
            except BridgePageError:
                self.stats["failed"] += 1
                raise
            except (BridgeUnavailable, BridgeTimeout) as e:
                last = e
                if retryable is False or i >= attempts:
                    break
                self.stats["retried"] += 1
                self._log(f"{method} 第 {i + 1} 次失败（{type(e).__name__}: {e}），等待扩展重连…")
                # 先等扩展上线（覆盖 MV3 30s 回收窗口），再退避重试
                self.wait_ready(timeout=self._wait_ready)
                time.sleep(min(0.8 * (i + 1), 3.0))

        self.stats["failed"] += 1
        raise last or BridgeError("未知错误")

    # ─── 连接状态 ───────────────────────────

    def ping(self) -> dict:
        return self._call_once("ping", timeout=5) or {}

    def status(self) -> dict:
        return self._call_once("status", timeout=5) or {}

    def is_connected(self) -> bool:
        try:
            return bool(self.ping().get("extension_connected"))
        except BridgeError:
            return False

    def wait_ready(self, timeout: float = 35.0, interval: float = 1.0) -> bool:
        """阻塞等待扩展上线（覆盖 MV3 Service Worker 30s 回收后的重连窗口）。"""
        deadline = time.time() + timeout
        while True:
            if self.is_connected():
                return True
            if time.time() >= deadline:
                return False
            time.sleep(interval)

    def stats_report(self) -> str:
        s = self.stats
        rate = (s["ok"] / s["calls"] * 100) if s["calls"] else 0.0
        return (f"调用 {s['calls']} 次 / 成功 {s['ok']} / 重试 {s['retried']} / "
                f"失败 {s['failed']} → 接通率 {rate:.1f}%")

    # ─── 导航 ───────────────────────────────

    def navigate(self, url: str, new_tab: bool = False) -> dict:
        """导航到指定 URL（记录目标页，供特权页自愈使用）"""
        result = self._call("navigate", {"url": url, "newTab": new_tab}, timeout=60)
        self._last_url = url
        return result or {}

    def ensure_page(self, url: str, timeout: float = 60.0) -> str:
        """确保目标页可读：导航 → 校验 URL → 不符则重试一次。

        这是 Service Worker 重启导致 _lastTabId 丢失时的自愈入口。
        """
        self.navigate(url)
        try:
            current = self.get_url()
        except BridgeError:
            current = ""
        if current and not current.startswith(url[:30]):
            self._log(f"导航后 URL 不符（当前 {current}），重试一次")
            self.navigate(url)
        return self._last_url or url

    # ─── 页面读取（带特权页自愈） ───────────

    def _read(self, method: str, params: Optional[dict] = None,
              timeout: float = 90.0, retryable: Optional[bool] = None) -> Any:
        try:
            return self._call(method, params, timeout=timeout, retryable=retryable)
        except BridgePageError:
            # 扩展的 _lastTabId 因 SW 重启丢失 → 回退到了 chrome://newtab 等特权页
            if not self._last_url:
                raise
            self._log(f"{method} 命中特权页，自动重新导航到 {self._last_url}")
            self.navigate(self._last_url)
            time.sleep(0.6)
            return self._call(method, params, timeout=timeout, retries=1,
                              retryable=retryable)

    def _assert_url(self, expected_prefix: str) -> None:
        """数据正确性防线：读取前校验当前页确实是目标页。

        背景：MV3 SW 重启会丢失目标标签记忆，v1 扩展会静默回退到"当前活动标签"，
        导致读到用户正在浏览的其他页面（如 ChatGPT）却毫无报错。
        传入 expect_url 即可把这种静默错数据变成显式异常。
        """
        current = self.get_url()
        if expected_prefix and not current.startswith(expected_prefix[:30]):
            raise BridgePageError(
                f"页面校验失败：期望 {expected_prefix}，实际读到 {current}。"
                f"已拦截，避免使用来源错误的页面数据。"
            )

    def get_text(self, expect_url: Optional[str] = None) -> str:
        """获取页面纯文本。

        建议传 expect_url（如 "https://admin.humancehr.com"）以防静默读错页。
        """
        if expect_url:
            self._assert_url(expect_url)
        return self._read("get_text") or ""

    def get_url(self) -> str:
        """获取当前 URL"""
        return self._call("get_url") or ""

    def get_html(self, expect_url: Optional[str] = None) -> str:
        """获取页面 HTML。

        建议传 expect_url 以防静默读错页。
        """
        if expect_url:
            self._assert_url(expect_url)
        return self._read("get_html") or ""

    # ─── JavaScript ─────────────────────────

    def evaluate(self, expression: str) -> Any:
        """在页面中执行 JavaScript（有副作用，不自动重试）"""
        return self._read("evaluate", {"expression": expression}, timeout=60,
                          retryable=False)

    # ─── DOM 操作 ───────────────────────────

    def click_by_text(self, text: str, selector: str = "*") -> str:
        """按文本点击元素（有副作用，不自动重试以免重复点击）"""
        return self._call("click_by_text", {"text": text, "selector": selector},
                          timeout=60, retryable=False)

    def click_element(self, selector: str) -> str:
        """按 CSS 选择器点击元素（有副作用，不自动重试）"""
        return self._call("click_element", {"selector": selector},
                          timeout=60, retryable=False)

    # ─── 截图 ───────────────────────────────

    def screenshot(self, save_path: Optional[str] = None):
        """截取当前页面"""
        result = self._read("screenshot", timeout=60)
        if isinstance(result, dict) and result.get("data"):
            import base64
            data = base64.b64decode(result["data"])
            if save_path:
                with open(save_path, "wb") as f:
                    f.write(data)
            return data
        return None

    # ─── 滚动 ───────────────────────────────

    def scroll_to(self, x: int = 0, y: int = 0) -> str:
        return self._call("scroll_to", {"x": x, "y": y}, timeout=30)

    def list_tabs(self) -> list:
        """列出所有标签页（含 privileged / remembered 标记），便于确认操作目标是否正确"""
        return self._call("list_tabs", timeout=30) or []

    # ─── 表单输入（CDP 通道，v1.2.0 扩展起支持） ──

    def type_text(self, selector: str, text: str, clear: bool = True) -> dict:
        """向输入框写入文本（对 React/Vue 受控组件也生效）。

        需要扩展 v1.2.0+。v1.3.0 起优先走 executeScript（纯 DOM 操作、不弹
        "正在调试此浏览器"提示条），仅在页面拒绝时回退 CDP。
        """
        return self._call("type_text", {"selector": selector, "text": text, "clear": clear},
                          timeout=60, retryable=False) or {}

    def get_value(self, selector: str) -> dict:
        """读取输入框当前值（校验写入是否生效）"""
        return self._call("get_value", {"selector": selector}, timeout=30) or {}

    # ─── 扩展自诊断（v1.3.0 扩展起支持） ─────────

    def get_diagnostics(self) -> dict:
        """读取扩展自检 + 已收集的错误（未捕获异常 / 未处理 rejection / 命令失败 / SW 重启记录）。

        有了它，扩展报错不必再人工打开 chrome://extensions 查看。
        """
        return self._call("get_diagnostics", timeout=30, retryable=False) or {}

    def clear_diagnostics(self) -> dict:
        """清空扩展侧已收集的诊断记录（排查新问题前先清一次，便于归因）"""
        return self._call("clear_diagnostics", timeout=30, retryable=False) or {}

    def probe_ext_errors(self) -> dict:
        """尝试用 CDP 直接读取 chrome://extensions 卡片上的「错误」详情。

        Chrome 通常禁止 debugger attach 到 chrome:// 页面；失败时返回
        {"ok": False, "reason": ...}，此时改用 get_diagnostics()。
        """
        return self._call("probe_ext_errors", timeout=60, retryable=False) or {}

    def reload_extension(self, delay_ms: int = 1200) -> dict:
        """让扩展自我热重载（等价于在 chrome://extensions 点刷新）。

        需要扩展 v1.3.0+。改完扩展磁盘代码后直接调它即可，不必人工点刷新。
        ⚠️ 重载会清空 chrome.storage.session → 之后必须重新 navigate 建立目标页。
        """
        r = self._call("reload_self", {"delayMs": delay_ms}, timeout=30, retryable=False)
        self._log(f"扩展已请求热重载（{delay_ms}ms 后）")
        return r or {}
