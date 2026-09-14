"""Browser Bridge Server v2 —— 抗抖动加固版

背景（2026-09-11 实测诊断）：
    MV3 扩展的 Service Worker 每 ~30s 被 Chrome 空闲回收一次，WebSocket 随之断开，
    1~2s 后扩展自动重连。原版服务端在这个"重连窗口"里会立刻回错误甚至裸断 CLI 连接，
    导致"接通率"极低。

v2 的四处关键修复：
    1. 【等重连】扩展不在线时不再立即失败，而是等待最多 --wait-ext 秒（默认 35s，
       覆盖 30s 回收窗口），扩展开机后命令正常执行。
    2. 【代际守卫】旧连接的 finally 不再把"新连接"的引用清空（原版竞态 bug）。
    3. 【发送保护】向扩展 send 失败时捕获异常、标记死连接、等待新连接后重试，
       CLI 侧永远收到结构化 JSON，不会出现 "Connection to remote host was lost"。
    4. 【可观测】ping 返回 epoch / 重连次数 / 扩展版本，便于量化"接通率"。

启动：
    python bridge_server.py --port 9334
"""

import argparse
import asyncio
import json
import logging
import sys
import time
import uuid
from typing import Any, Optional

import websockets

try:  # websockets >= 14 推荐路径
    from websockets.asyncio.server import ServerConnection
except ImportError:  # 兼容旧版
    from websockets.server import ServerConnection  # type: ignore

logger = logging.getLogger("browser-bridge")

# ── 可调参数 ────────────────────────────────────────────────
DEFAULT_WAIT_EXT = 35.0     # 扩展掉线后等待其重连的最长时间（覆盖 MV3 30s 回收窗口）
CMD_TIMEOUT = 90.0          # 单条命令最长等待
HANDSHAKE_TIMEOUT = 30.0    # 首帧握手超时
MAX_SEND_RETRY = 2          # 发送失败后最多重试次数

# 只读命令：断线后重试是安全的（不会重复产生副作用）
READONLY_METHODS = {
    "get_text", "get_url", "get_html", "screenshot", "ping", "status", "scroll_to",
}
# 有副作用命令：仅在"确认未送达扩展"时才重试，避免重复点击
MUTATING_METHODS = {
    "click_by_text", "click_element", "navigate", "evaluate",
}


class BridgeServer:
    def __init__(self, wait_ext: float = DEFAULT_WAIT_EXT) -> None:
        self._extension_ws: Optional[ServerConnection] = None
        self._ext_ready = asyncio.Event()      # 扩展在线信号（等待/唤醒用）
        self._pending: dict[str, asyncio.Future[Any]] = {}
        self._ext_epoch = 0                    # 扩展连接代际
        self._reconnects = 0                   # 累计重连次数（可观测指标）
        self._ext_version = "unknown"
        self._last_connected_at: Optional[float] = None
        self._wait_ext = wait_ext
        self._cmd_total = 0
        self._cmd_ok = 0
        self._cmd_fail = 0

    # ── 连接入口 ────────────────────────────────────────────

    async def handle(self, ws: ServerConnection) -> None:
        """每个 WebSocket 连接的处理入口。任何异常都不允许外泄导致进程/连接异常。"""
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=HANDSHAKE_TIMEOUT)
        except asyncio.TimeoutError:
            logger.warning("握手超时：客户端 %.0fs 内未发送首帧", HANDSHAKE_TIMEOUT)
            return
        except Exception as e:
            logger.debug("握手失败: %s", e)
            return

        try:
            msg = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            logger.warning("首帧不是合法 JSON，已忽略")
            return

        role = msg.get("role")
        try:
            if role == "extension":
                await self._handle_extension(ws, msg)
            elif role == "cli":
                await self._handle_cli(ws, msg)
            else:
                # 原版这里只打日志然后隐式断连，导致上游误判为"扩展掉线"
                logger.warning("未知 role=%r（首帧必须是 {\"role\":\"extension\"} 或 {\"role\":\"cli\"}）", role)
                await self._safe_send(ws, json.dumps(
                    {"error": "首帧必须携带 role 字段（extension / cli）", "errorType": "BAD_ROLE"},
                    ensure_ascii=False))
        except Exception:
            logger.exception("处理连接时出现未捕获异常（已隔离）")

    # ── Extension 端（长连接） ──────────────────────────────

    async def _handle_extension(self, ws: ServerConnection, hello: dict) -> None:
        self._ext_epoch += 1
        epoch = self._ext_epoch
        if epoch > 1:
            self._reconnects += 1
        self._extension_ws = ws
        self._ext_ready.set()
        connected_at = time.time()
        self._last_connected_at = connected_at
        self._ext_version = str(hello.get("v") or hello.get("version") or "unknown")

        logger.info("Extension 已连接 [#%d] version=%s（累计重连 %d 次）",
                    epoch, self._ext_version, self._reconnects)

        try:
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    continue

                msg_id = msg.get("id")
                if msg_id and msg_id in self._pending:
                    fut = self._pending.pop(msg_id)
                    if not fut.done():
                        fut.set_result(msg)
                elif msg.get("type") == "heartbeat":
                    logger.debug("扩展心跳 ts=%s", msg.get("ts"))
                # 其余无 id 的消息（如心跳的其他形态）静默忽略
        except Exception as e:
            logger.debug("Extension 连接读取结束: %s", e)
        finally:
            # ★ 代际守卫：只有"当前这一代"断线时才释放引用。
            #   原版无条件 self._extension_ws = None，会把刚上线的新连接误清掉。
            if self._ext_epoch == epoch and self._extension_ws is ws:
                self._extension_ws = None
                self._ext_ready.clear()
                logger.info("Extension 已断开 [#%d]（本次存活 %.1fs）",
                            epoch, time.time() - connected_at)
                for fut in list(self._pending.values()):
                    if not fut.done():
                        fut.set_exception(ConnectionError("扩展在命令执行中断开连接"))
                self._pending.clear()
            else:
                logger.info("旧 Extension 连接收尾 [#%d]（已被新连接取代，不影响当前会话）", epoch)

    # ── CLI 端（短连接） ────────────────────────────────────

    async def _handle_cli(self, ws: ServerConnection, msg: dict) -> None:
        method = msg.get("method")

        # 状态类命令：不需要扩展在线
        if method == "ping":
            await self._safe_send(ws, json.dumps({"result": {
                "extension_connected": self._extension_ws is not None,
                "extension_version": self._ext_version,
                "epoch": self._ext_epoch,
                "reconnects": self._reconnects,
                "last_connected_at": self._last_connected_at,
                "cmd_total": self._cmd_total,
                "cmd_ok": self._cmd_ok,
                "cmd_fail": self._cmd_fail,
                "success_rate": (round(self._cmd_ok / self._cmd_total * 100, 1)
                                 if self._cmd_total else None),
            }}, ensure_ascii=False))
            return

        if method == "status":
            await self._safe_send(ws, json.dumps({"result": {
                "extension_connected": self._extension_ws is not None,
                "extension_version": self._ext_version,
                "epoch": self._ext_epoch,
                "reconnects": self._reconnects,
                "uptime_s": (round(time.time() - self._last_connected_at, 1)
                             if self._last_connected_at else None),
            }}, ensure_ascii=False))
            return

        self._cmd_total += 1

        # ★ 核心修复 1：扩展不在线时"等待重连"，而不是立刻失败
        if not await self._wait_for_extension():
            self._cmd_fail += 1
            await self._safe_send(ws, json.dumps({
                "error": (f"扩展未连接，且等待 {self._wait_ext:.0f}s 后仍未上线。"
                          "请在 Chrome 的扩展页确认 Browser Bridge 已启用（徽标显示 ON）。"),
                "errorType": "NO_EXTENSION",
            }, ensure_ascii=False))
            return

        # 重试策略：只读命令可重试；有副作用命令仅在"确认未送达"时重试
        explicit_retry = msg.get("retry")
        if isinstance(explicit_retry, bool):
            allow_retry = explicit_retry
        else:
            allow_retry = method in READONLY_METHODS

        msg_id = str(uuid.uuid4())
        msg["id"] = msg_id
        payload = json.dumps(msg, ensure_ascii=False)

        last_err = "未知错误"
        sent_at_least_once = False

        for attempt in range(MAX_SEND_RETRY + 1):
            ws_ext = self._extension_ws
            if ws_ext is None:
                if attempt == 0 or not allow_retry:
                    if not await self._wait_for_extension():
                        last_err = "扩展在发送前断开"
                        break
                    ws_ext = self._extension_ws
                else:
                    last_err = "扩展在重试前断开"
                    break
                if ws_ext is None:
                    last_err = "扩展在发送前断开"
                    break

            loop = asyncio.get_event_loop()
            fut: asyncio.Future[Any] = loop.create_future()
            self._pending[msg_id] = fut

            # ★ 核心修复 2：向扩展发送时捕获异常（原版无保护 → CLI 被裸断）
            try:
                await ws_ext.send(payload)
                sent_at_least_once = True
            except Exception as e:
                self._pending.pop(msg_id, None)
                last_err = f"向扩展发送失败: {type(e).__name__}: {e}"
                logger.warning("发送失败（第 %d 次）: %s", attempt + 1, last_err)
                # 标记这条扩展连接已死，避免后续继续往黑洞里发
                if self._extension_ws is ws_ext:
                    self._extension_ws = None
                    self._ext_ready.clear()
                if not allow_retry:
                    break
                continue

            try:
                result = await asyncio.wait_for(fut, timeout=CMD_TIMEOUT)
                self._cmd_ok += 1
                await self._safe_send(ws, json.dumps(result, ensure_ascii=False))
                return
            except asyncio.TimeoutError:
                self._pending.pop(msg_id, None)
                self._cmd_fail += 1
                await self._safe_send(ws, json.dumps({
                    "error": f"命令执行超时（{CMD_TIMEOUT:.0f}s）",
                    "errorType": "TIMEOUT",
                }, ensure_ascii=False))
                return
            except ConnectionError as e:
                last_err = str(e)
                logger.warning("命令执行中扩展断开（第 %d 次）: %s", attempt + 1, last_err)
                # 已投递但结果未知 → 对有副作用命令不再重试，避免重复执行
                if not allow_retry:
                    self._cmd_fail += 1
                    await self._safe_send(ws, json.dumps({
                        "error": (f"命令已下发给扩展，但扩展在返回结果前断开，执行结果未知"
                                  f"（为避免重复执行，不再自动重试）: {last_err}"),
                        "errorType": "INDETERMINATE",
                        "sent": sent_at_least_once,
                    }, ensure_ascii=False))
                    return
                await asyncio.sleep(0.8)
                continue

        self._cmd_fail += 1
        await self._safe_send(ws, json.dumps({
            "error": f"命令失败：{last_err}",
            "errorType": "DISCONNECTED",
            "sent": sent_at_least_once,
        }, ensure_ascii=False))

    # ── 工具 ────────────────────────────────────────────────

    async def _wait_for_extension(self, timeout: Optional[float] = None) -> bool:
        """等待扩展上线；已在线立即返回 True。"""
        if self._extension_ws is not None:
            return True
        t = self._wait_ext if timeout is None else timeout
        try:
            await asyncio.wait_for(self._ext_ready.wait(), timeout=t)
            return True
        except asyncio.TimeoutError:
            return False

    @staticmethod
    async def _safe_send(ws: ServerConnection, payload: str) -> bool:
        """回传 CLI；即使 CLI 已断开也不会抛异常污染日志。"""
        try:
            await ws.send(payload)
            return True
        except Exception as e:
            logger.debug("回传 CLI 失败（客户端可能已关闭）: %s", e)
            return False


async def main(port: int, wait_ext: float, log_file: Optional[str]) -> None:
    if log_file:
        handler = logging.FileHandler(log_file, encoding="utf-8")
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s: %(message)s"))
        logging.getLogger().addHandler(handler)

    # 屏蔽 websockets 库自身对"探测型连接"的握手报错（多为被 kill 的临时客户端，无害）
    logging.getLogger("websockets.server").setLevel(logging.CRITICAL)
    logging.getLogger("websockets.asyncio.server").setLevel(logging.CRITICAL)

    server = BridgeServer(wait_ext=wait_ext)
    async with websockets.serve(
        server.handle, "localhost", port,
        ping_interval=20, ping_timeout=20,   # 服务端主动探活，及时识别半开连接
        max_size=64 * 1024 * 1024,           # 大页面 HTML 也能回传
    ):
        logger.info("Bridge server v2 已启动: ws://localhost:%d（等重连窗口 %.0fs）", port, wait_ext)
        logger.info("等待浏览器扩展连接...")
        await asyncio.Future()  # 永久运行


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Browser Bridge Server v2（抗抖动）")
    parser.add_argument("--port", type=int, default=9334, help="监听端口（默认 9334）")
    parser.add_argument("--wait-ext", type=float, default=DEFAULT_WAIT_EXT,
                        help=f"扩展掉线后等待重连的最长秒数（默认 {DEFAULT_WAIT_EXT:.0f}）")
    parser.add_argument("--log-file", default=None, help="额外写入日志文件（便于事后诊断）")
    args = parser.parse_args()

    try:
        asyncio.run(main(args.port, args.wait_ext, args.log_file))
    except KeyboardInterrupt:
        pass
