"""Browser Bridge - CLI 客户端

用法：
    from control import Bridge

    bridge = Bridge()
    bridge.navigate("https://ziyuan.baidu.com")
    text = bridge.get_text()
    bridge.click_by_text("索引量")
    html = bridge.get_html()
    bridge.screenshot("page.png")
"""

import json
import websockets.sync.client as ws_client

BRIDGE_URL = "ws://localhost:9334"


class Bridge:
    """与 Browser Bridge Extension 通信的客户端"""

    def __init__(self, url: str = BRIDGE_URL):
        self._url = url

    # ─── 内部通信 ───────────────────────────

    def _call(self, method: str, params: dict | None = None, timeout: float = 90.0) -> any:
        msg = {"role": "cli", "method": method}
        if params:
            msg["params"] = params
        try:
            with ws_client.connect(self._url, max_size=50 * 1024 * 1024) as ws:
                ws.send(json.dumps(msg, ensure_ascii=False))
                raw = ws.recv(timeout=timeout)
        except OSError as e:
            raise ConnectionError(f"无法连接到 bridge server（{self._url}）: {e}")

        resp = json.loads(raw) if raw else {}
        if resp.get("error"):
            raise RuntimeError(f"Bridge 错误: {resp['error']}")
        return resp.get("result")

    # ─── 连接状态 ───────────────────────────

    def ping(self) -> dict:
        return self._call("ping", timeout=5)

    def is_connected(self) -> bool:
        try:
            r = self.ping()
            return bool(r.get("extension_connected"))
        except:
            return False

    # ─── 导航 ───────────────────────────────

    def navigate(self, url: str, new_tab: bool = False) -> dict:
        """导航到指定 URL"""
        return self._call("navigate", {"url": url, "newTab": new_tab})

    # ─── JavaScript ─────────────────────────

    def evaluate(self, expression: str) -> any:
        """在页面中执行 JavaScript"""
        return self._call("evaluate", {"expression": expression})

    def get_text(self) -> str:
        """获取页面纯文本"""
        return self._call("get_text") or ""

    def get_url(self) -> str:
        """获取当前 URL"""
        return self._call("get_url") or ""

    def get_html(self) -> str:
        """获取页面 HTML"""
        return self._call("get_html") or ""

    # ─── DOM 操作 ───────────────────────────

    def click_by_text(self, text: str, selector: str = "*") -> str:
        """按文本点击元素"""
        return self._call("click_by_text", {"text": text, "selector": selector})

    def click_element(self, selector: str) -> str:
        """按 CSS 选择器点击元素"""
        return self._call("click_element", {"selector": selector})

    # ─── 截图 ───────────────────────────────

    def screenshot(self, save_path: str | None = None) -> bytes | None:
        """截取当前页面"""
        result = self._call("screenshot")
        if result and result.get("data"):
            import base64
            data = base64.b64decode(result["data"])
            if save_path:
                with open(save_path, "wb") as f:
                    f.write(data)
            return data
        return None

    # ─── 滚动 ───────────────────────────────

    def scroll_to(self, x: int = 0, y: int = 0) -> str:
        return self._call("scroll_to", {"x": x, "y": y})
