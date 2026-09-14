// Browser Bridge - 通用浏览器自动化扩展
// 无任何平台特定代码，完全通用的 WebSocket Bridge
//
// ── v1.3.0（2026-09-11 二轮修复）───────────────────────────
//  A. about:blank 被误列为"特权页" → 重建后自判不可用（本次实测的报错根因）。
//  B. 目标页被用户手动切走后，remembered tab 仍被当作"目标" → 静默读错页残留路径。
//     修复：同站点校验（host 不同即视为用户切走，改为重建目标页）。
//  C. 目标页缺失时不再创建 about:blank（会返回空内容＝静默错误数据的变体），
//     改为明确报错，提示先 navigate。
//  D. 新增 SW 错误自收集（error / unhandledrejection / 命令失败）写入
//     chrome.storage.local（重载不丢），并提供 get_diagnostics 命令 —— 以后
//     扩展报错可直接从 CLI 读出，不必再人工点 chrome://extensions 看。
//  E. type_text / get_value 改为 executeScript 优先（纯 DOM 操作不受 CSP 限制），
//     CDP 仅作兜底 —— 避免每次输入都弹"正在调试此浏览器"提示条。
//  F. screenshot 改走 CDP Page.captureScreenshot（可截后台标签，不再依赖活动标签）。
//  G. 新增 reload_self 命令 —— 扩展可自我热重载，改完磁盘代码不必再人工去
//     chrome://extensions 点刷新（注意：重载会清空 storage.session，之后需重新 navigate）。
//
// ── v1.1.0 修复（2026-09-11 实测诊断）──────────────────────
//  根因 1：MV3 Service Worker 每 ~30s 被 Chrome 空闲回收 → WebSocket 掉线，
//          命令落在"重连窗口"里必然失败。
//          修复：20s 心跳（< 30s 空闲阈值）保活 SW + 快速指数退避重连。
//  根因 2：_lastTabId 是模块级变量，SW 每次重启即丢失 → getActiveTab() 回退到
//          "当前活动标签"，往往命中 chrome://newtab → executeScript 报
//          "Cannot access a chrome:// URL"，全部读取类命令失败。
//          修复：lastTabId / lastUrl 持久化到 chrome.storage.session；
//                getActiveTab() 跳过特权页；命中特权页时自动导航回上次目标页。
//  根因 3：onmessage 里直接引用模块级 ws，SW 重启后 ws 为 null 或已换新 socket，
//          响应发到 null/过期 socket → 客户端 90s 超时。
//          修复：每次消息捕获局部 socket 引用 + readyState 校验。
// ──────────────────────────────────────────────────────────

const BRIDGE_URL = "ws://localhost:9334";
const VERSION = "1.3.0";

const HEARTBEAT_MS = 20000;   // 必须 < 30000（MV3 空闲回收阈值）
const RECONNECT_MIN_MS = 800;
const RECONNECT_MAX_MS = 5000;
const CMD_MAX_MS = 60000;     // 单条命令执行上限
const NAV_WAIT_MS = 10000;    // 导航等待页面加载上限

// 浏览器特权页/无法注入脚本的协议
const PRIVILEGED_RE = /^(chrome|chrome-untrusted|chrome-extension|edge|brave|opera|vivaldi|about|devtools|view-source|moz-extension|data):/i;

let ws = null;
let heartbeatTimer = null;
let reconnectDelay = RECONNECT_MIN_MS;
let lastTabId = null;

// ⚠️ about:blank 是唯一例外：它没有页面 CSP、可以正常注入脚本，不属于特权页。
//    （v1.2.0 把整个 about: 协议列为特权，导致"重建 about:blank 后仍不可用"的误判）
const isPrivileged = (url) => {
  if (!url) return true;
  if (url === "about:blank") return false;
  return PRIVILEGED_RE.test(url);
};

/** 同站点判断：用于识别"用户已手动把目标标签切走到别的网站" */
function sameHost(a, b) {
  try { return new URL(a).host === new URL(b).host; } catch { return false; }
}

// ─── 轻量持久化（SW 重启不丢目标 tab） ─────

const store = {
  async get(key) {
    try {
      const area = chrome.storage.session || chrome.storage.local;
      const r = await area.get(key);
      return r ? r[key] : undefined;
    } catch { return undefined; }
  },
  async set(obj) {
    try {
      const area = chrome.storage.session || chrome.storage.local;
      await area.set(obj);
    } catch { /* 忽略 */ }
  },
};

async function getLastTabId() {
  if (lastTabId) return lastTabId;
  lastTabId = (await store.get("lastTabId")) || null;
  return lastTabId;
}

async function setLastTabId(id) {
  lastTabId = id;
  await store.set({ lastTabId: id });
}

async function setLastUrl(url) {
  if (url) await store.set({ lastUrl: url });
}

// ─── 错误自收集（v1.3.0）────────────────────
//
// chrome://extensions 卡片上的红色「错误」按钮，内容只能在该特权页里看。
// 这里把 SW 内所有未捕获异常、未处理的 Promise rejection、以及命令失败
// 落进 chrome.storage.local（重载后仍保留），由 get_diagnostics 命令读出。

const DIAG_KEY = "diagnostics";
const DIAG_MAX = 30;

async function diagRead() {
  try {
    const r = await chrome.storage.local.get(DIAG_KEY);
    const d = r && r[DIAG_KEY];
    if (d && typeof d === "object") {
      if (!Array.isArray(d.errors)) d.errors = [];
      if (!Array.isArray(d.cmdFails)) d.cmdFails = [];
      return d;
    }
  } catch { /* 忽略 */ }
  return { errors: [], cmdFails: [], boot: null, boots: 0 };
}

async function diagWrite(d) {
  try {
    d.errors = (d.errors || []).slice(0, DIAG_MAX);
    d.cmdFails = (d.cmdFails || []).slice(0, DIAG_MAX);
    await chrome.storage.local.set({ [DIAG_KEY]: d });
  } catch { /* 忽略 */ }
}

function recordError(scope, err) {
  const msg = String((err && (err.stack || err.message)) || err).slice(0, 600);
  const at = new Date().toISOString();
  console.error("[Browser Bridge][diag]", scope, msg);
  diagRead().then((d) => {
    d.errors.unshift({ at, scope, msg });
    return diagWrite(d);
  }).catch(() => {});
}

function recordCmdFail(method, err) {
  const msg = String((err && err.message) || err).slice(0, 300);
  const at = new Date().toISOString();
  diagRead().then((d) => {
    d.cmdFails.unshift({ at, method, msg });
    return diagWrite(d);
  }).catch(() => {});
}

// SW 未捕获异常 / 未处理的 Promise rejection
self.addEventListener("error", (e) => {
  recordError("self.error", (e && (e.error || e.message)) || "unknown");
});
self.addEventListener("unhandledrejection", (e) => {
  recordError("unhandledrejection", e && e.reason);
});

// ─── 通信 ──────────────────────────────────

function connect() {
  if (ws && (ws.readyState === WebSocket.CONNECTING || ws.readyState === WebSocket.OPEN)) return;

  ws = new WebSocket(BRIDGE_URL);

  ws.onopen = () => {
    console.log("[Browser Bridge] 已连接到 bridge server，version =", VERSION);
    reconnectDelay = RECONNECT_MIN_MS;
    try {
      ws.send(JSON.stringify({ role: "extension", v: VERSION }));
    } catch (e) {
      console.warn("[Browser Bridge] 发送握手失败", e);
    }
    startHeartbeat();
    setStatus(true);
  };

  ws.onclose = () => {
    console.log("[Browser Bridge] 断开连接，将在", reconnectDelay, "ms 后重连");
    stopHeartbeat();
    ws = null;
    setStatus(false);
    const delay = reconnectDelay;
    reconnectDelay = Math.min(reconnectDelay * 2, RECONNECT_MAX_MS);
    setTimeout(connect, delay);
  };

  ws.onerror = (e) => {
    console.warn("[Browser Bridge] WebSocket 错误（通常随后触发 onclose 重连）", e && e.type);
  };

  ws.onmessage = async (event) => {
    // ★ 捕获当前 socket，避免 SW 重启后发到 null / 过期连接
    const sock = ws;
    const reply = (obj) => {
      if (sock && sock.readyState === WebSocket.OPEN) {
        try { sock.send(JSON.stringify(obj)); }
        catch (e) { console.warn("[Browser Bridge] 回传失败", e); }
      } else {
        console.warn("[Browser Bridge] 回传被丢弃：socket 已关闭");
      }
    };

    let msg;
    try { msg = JSON.parse(event.data); } catch { return; }

    // 特殊命令：查询扩展是否连接
    if (msg.method === "ping") {
      reply({ id: msg.id, result: { connected: true, v: VERSION } });
      return;
    }

    const started = Date.now();
    try {
      const result = await withTimeout(
        handleCommand(msg), CMD_MAX_MS, `命令 ${msg.method} 执行超时`
      );
      reply({ id: msg.id, result: result === undefined ? null : result, ms: Date.now() - started });
    } catch (err) {
      recordCmdFail(msg.method, err);
      reply({
        id: msg.id,
        error: String(err && err.message ? err.message : err),
        ms: Date.now() - started,
      });
    }
  };
}

// ─── 心跳保活（防止 MV3 SW 被 30s 空闲回收） ──

function startHeartbeat() {
  stopHeartbeat();
  heartbeatTimer = setInterval(() => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      try { ws.send(JSON.stringify({ type: "heartbeat", ts: Date.now() })); }
      catch (e) { console.warn("[Browser Bridge] 心跳发送失败", e); }
    } else {
      connect();
    }
  }, HEARTBEAT_MS);
}

function stopHeartbeat() {
  if (heartbeatTimer) { clearInterval(heartbeatTimer); heartbeatTimer = null; }
}

// ─── 工具 ──────────────────────────────────

function withTimeout(promise, ms, label) {
  return new Promise((resolve, reject) => {
    const t = setTimeout(() => reject(new Error(`${label}（${ms}ms）`)), ms);
    Promise.resolve(promise).then(
      (v) => { clearTimeout(t); resolve(v); },
      (e) => { clearTimeout(t); reject(e); }
    );
  });
}

// ─── 命令路由 ──────────────────────────────

async function handleCommand(msg) {
  const { method, params = {} } = msg;

  switch (method) {
    case "navigate":      return await cmdNavigate(params);
    case "evaluate":      return await cmdEvaluate(params);
    case "click_element": return await cmdClickElement(params);
    case "click_by_text": return await cmdClickByText(params);
    case "get_text":      return await cmdGetText();
    case "get_url":       return await cmdGetUrl();
    case "get_html":      return await cmdGetHtml();
    case "screenshot":    return await cmdScreenshot();
    case "scroll_to":     return await cmdScrollTo(params);
    case "list_tabs":     return await cmdListTabs();
    case "type_text":     return await cmdTypeText(params);
    case "get_value":     return await cmdGetValue(params);
    case "get_diagnostics":   return await cmdGetDiagnostics();
    case "clear_diagnostics": return await cmdClearDiagnostics();
    case "probe_ext_errors":  return await cmdProbeExtErrors();
    case "reload_self":       return await cmdReloadSelf(params);
    default:
      throw new Error(`未知命令: ${method}`);
  }
}

// ─── Tab 解析（核心修复） ───────────────────

/**
 * 解析目标 tab。返回 { tab, exact }。
 * exact=true 表示"就是上次操作的那个标签/URL"，false 表示重建的。
 *
 * ⚠️ 关键安全设计：执行脚本的命令（forScript=true）**绝不**回退到"当前活动标签"。
 *    因为 SW 重启后 _lastTabId 会丢，若随手用活动标签，就会静默读到用户
 *    正在浏览的其他页面（如 ChatGPT），返回看似正常实则错误的数据。
 *    宁可重建标签页，也不返回错误页面。
 */
async function pickTab({ forScript = false } = {}) {
  const lastUrl = await store.get("lastUrl");
  const wantUrl = lastUrl && !isPrivileged(lastUrl) ? lastUrl : null;

  // 1) 上次使用的 tab —— 但必须与目标页同站，否则说明用户已手动切走
  //    （不同站直接沿用＝静默读到用户正在浏览的其它站点，这是最危险的失败模式）
  const remembered = await getLastTabId();
  if (remembered) {
    try {
      const tab = await chrome.tabs.get(remembered);
      if (tab && !isPrivileged(tab.url)) {
        if (!wantUrl || sameHost(tab.url, wantUrl)) return { tab, exact: true };
        console.log("[Browser Bridge] 目标标签已被切到其它站点，将重建目标页",
                    tab.url, "≠", wantUrl);
      }
    } catch { /* 标签已关闭 */ }
  }

  // 2) 找一个 URL 与目标页一致的标签（用户可能手动切走了，但目标页仍开着）
  if (wantUrl) {
    const tabs = (await chrome.tabs.query({})) || [];
    const hit = tabs.find((t) => !isPrivileged(t.url) && sameHost(t.url, wantUrl));
    if (hit) { await setLastTabId(hit.id); return { tab: hit, exact: true }; }
  }

  // 3) 脚本类命令：重建目标页标签（后台打开，不抢用户焦点）
  //    ⚠️ 绝不回退"当前活动标签"，也绝不创建 about:blank（空内容＝静默假数据）
  if (forScript) {
    if (!wantUrl) {
      throw new Error(
        "本次会话尚无目标页（未调用过 navigate）。请先 navigate 指定目标页，再执行读取类命令。"
      );
    }
    const created = await chrome.tabs.create({ url: wantUrl, active: false });
    await setLastTabId(created.id);
    await waitForTabComplete(created.id, NAV_WAIT_MS);
    const t = await chrome.tabs.get(created.id).catch(() => null);
    if (t && !isPrivileged(t.url)) return { tab: t, exact: false };
    throw new Error(
      `目标标签页已丢失，且重建 ${wantUrl} 后仍不可用。请显式调用 navigate 指定目标页。`
    );
  }

  // 4) 非脚本命令（get_url / screenshot）：允许用活动标签
  const active = (await chrome.tabs.query({ active: true, currentWindow: true })) || [];
  if (active[0]) return { tab: active[0], exact: false };

  const created = await chrome.tabs.create({ url: "about:blank", active: false });
  return { tab: created, exact: false };
}

/** 解析出可注入脚本的 tab（含特权页自愈）。 */
async function resolveScriptableTab() {
  const { tab, exact } = await pickTab({ forScript: true });
  if (!isPrivileged(tab && tab.url)) return { tab, exact };

  // 万一命中特权页（理论上已被 pickTab 挡住）→ 强行重建
  const lastUrl = await store.get("lastUrl");
  if (lastUrl && !isPrivileged(lastUrl)) {
    console.log("[Browser Bridge] 命中特权页，重建目标页", lastUrl);
    const r = await cmdNavigate({ url: lastUrl, active: false });
    const t = await chrome.tabs.get(r.tabId).catch(() => null);
    if (t && !isPrivileged(t.url)) return { tab: t, exact: false };
  }

  throw new Error(
    `当前标签页是浏览器特权页（${(tab && tab.url) || "未知"}），无法注入脚本。` +
    `请先调用 navigate 打开目标网页。`
  );
}

// ─── 命令实现 ──────────────────────────────

async function cmdNavigate({ url, newTab = false, active = true }) {
  if (!url) throw new Error("navigate 缺少 url 参数");

  let tab;
  const remembered = await getLastTabId();

  if (newTab || !remembered) {
    tab = await chrome.tabs.create({ url, active });
  } else {
    try {
      tab = await chrome.tabs.get(remembered);
      await chrome.tabs.update(tab.id, { url, active });
    } catch {
      tab = await chrome.tabs.create({ url, active });
    }
  }

  await setLastTabId(tab.id);
  await setLastUrl(url);

  await waitForTabComplete(tab.id, NAV_WAIT_MS);
  const final = await chrome.tabs.get(tab.id).catch(() => tab);
  return { tabId: tab.id, url: (final && final.url) || url, v: VERSION };
}

// ─── CDP 通道（绕过页面 CSP，并提供文本输入能力） ──────────
//
// 背景：Strapi 后台等页面有 `unsafe-eval` CSP，chrome.scripting.executeScript
//       在 MAIN world 里 new Function() 会被拦；且扩展一直没有"输入文本"能力，
//       导致表单（API Token、自定义日期区间）只能人工填。
//       Chrome DevTools Protocol 的 Runtime.evaluate **不受页面 CSP 限制**，
//       用 chrome.debugger 走这条通道即可同时解决这两个问题。

async function withDebugger(tabId, fn) {
  await chrome.debugger.attach({ tabId }, "1.3");
  try {
    return await fn();
  } finally {
    await chrome.debugger.detach({ tabId }).catch(() => {});
  }
}

async function cdpEvalOn(tabId, expression, { awaitPromise = true } = {}) {
  return await withDebugger(tabId, async () => {
    const res = await chrome.debugger.sendCommand({ tabId }, "Runtime.evaluate", {
      expression,
      returnByValue: true,
      awaitPromise,
      userGesture: true,
    });
    if (res && res.exceptionDetails) {
      const det = res.exceptionDetails;
      const desc = (det.exception && det.exception.description) || det.text || "未知异常";
      throw new Error(`CDP evaluate 异常: ${desc}`);
    }
    return res && res.result ? res.result.value : null;
  });
}

async function cmdEvaluate({ expression, timeout = 30000 }) {
  if (typeof expression !== "string") throw new Error("evaluate 缺少 expression 参数");
  const { tab } = await resolveScriptableTab();

  // 快路径：MAIN world 注入
  try {
    const result = await withTimeout(
      chrome.scripting.executeScript({
        target: { tabId: tab.id },
        world: "MAIN",
        func: (expr) => {
          try { return Function(`"use strict"; return (${expr})`)(); }
          catch (e) { return { __error: String(e.message || e) }; }
        },
        args: [expression],
      }),
      timeout, "evaluate 执行超时"
    );
    const r = result && result[0] ? result[0].result : null;
    if (r && typeof r === "object" && "__error" in r) throw new Error(r.__error);
    return r === undefined ? null : r;
  } catch (e) {
    const msg = String((e && e.message) || e);
    // CSP 拦截 → 回退 CDP（不受页面 CSP 限制）
    if (!/Content Security Policy|unsafe-eval/i.test(msg)) throw e;
    console.log("[Browser Bridge] MAIN world 被 CSP 拦截，回退 CDP Runtime.evaluate");
    return await withTimeout(cdpEvalOn(tab.id, expression), timeout, "CDP evaluate 超时");
  }
}

/** 向输入框写入文本（对 React/Vue 受控组件也生效）。
 *  纯 DOM 操作、不涉及 eval → 不受页面 CSP 限制，因此优先 executeScript；
 *  仅在被拒时回退 CDP（CDP attach 会弹"正在调试此浏览器"提示条，能省则省）。 */
function typeIntoElement(sel, txt, clr) {
  const el = document.querySelector(sel);
  if (!el) return { ok: false, error: `未找到元素: ${sel}` };
  el.focus();
  const tag = (el.tagName || "").toUpperCase();
  const proto = tag === "TEXTAREA" ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
  const desc = Object.getOwnPropertyDescriptor(proto, "value");
  const next = (clr ? "" : (el.value || "")) + txt;
  if (desc && desc.set) desc.set.call(el, next); else el.value = next;
  el.dispatchEvent(new Event("input", { bubbles: true }));
  el.dispatchEvent(new Event("change", { bubbles: true }));
  return { ok: true, tag, type: el.type || "", value: el.value };
}

async function cmdTypeText({ selector, text = "", clear = true }) {
  if (!selector) throw new Error("type_text 缺少 selector 参数");
  if (typeof text !== "string") throw new Error("type_text 的 text 必须是字符串");
  const { tab } = await resolveScriptableTab();

  try {
    const r = await withTimeout(
      chrome.scripting.executeScript({
        target: { tabId: tab.id }, world: "MAIN",
        func: typeIntoElement, args: [selector, text, clear],
      }), 15000, "type_text 执行超时");
    const v = r && r[0] ? r[0].result : null;
    if (v && v.ok === false) throw new Error(v.error);
    return v;
  } catch (e) {
    const msg = String((e && e.message) || e);
    if (/未找到元素/.test(msg)) throw e;   // 元素不存在是真实错误，不该兜底
    console.log("[Browser Bridge] type_text 回退 CDP:", msg.slice(0, 120));
    const expr = `(${typeIntoElement.toString()})(${JSON.stringify(selector)},${JSON.stringify(text)},${!!clear})`;
    return await withTimeout(cdpEvalOn(tab.id, expr, { awaitPromise: false }), 20000, "type_text CDP 超时");
  }
}

/** 读取输入框当前值（调试/校验用）。 */
function readElementValue(sel) {
  const el = document.querySelector(sel);
  return el ? { ok: true, value: el.value, tag: el.tagName, type: el.type || "" }
            : { ok: false, error: `未找到元素: ${sel}` };
}

async function cmdGetValue({ selector }) {
  if (!selector) throw new Error("get_value 缺少 selector 参数");
  const { tab } = await resolveScriptableTab();
  try {
    const r = await withTimeout(
      chrome.scripting.executeScript({
        target: { tabId: tab.id }, world: "MAIN",
        func: readElementValue, args: [selector],
      }), 15000, "get_value 执行超时");
    return r && r[0] ? r[0].result : null;
  } catch (e) {
    const expr = `(${readElementValue.toString()})(${JSON.stringify(selector)})`;
    return await withTimeout(cdpEvalOn(tab.id, expr, { awaitPromise: false }), 20000, "get_value CDP 超时");
  }
}

async function cmdClickByText({ text, selector = "*" }) {
  if (!text) throw new Error("click_by_text 缺少 text 参数");
  const { tab } = await resolveScriptableTab();
  const { result } = await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    world: "MAIN",
    func: (sel, txt) => {
      const target = Array.from(document.querySelectorAll(sel))
        .find((el) => el.textContent.trim() === txt && el.offsetParent !== null);
      if (!target) return { __error: `未找到元素: text="${txt}" selector="${sel}"` };
      target.scrollIntoView({ block: "center" });
      target.click();
      return "ok";
    },
    args: [selector, text],
  });
  if (result && result.__error) throw new Error(result.__error);
  return result;
}

async function cmdClickElement({ selector }) {
  if (!selector) throw new Error("click_element 缺少 selector 参数");
  const { tab } = await resolveScriptableTab();
  await chrome.debugger.attach({ tabId: tab.id }, "1.3");
  try {
    const { root } = await chrome.debugger.sendCommand({ tabId: tab.id }, "DOM.getDocument", { depth: 0 });
    const { nodeId } = await chrome.debugger.sendCommand({ tabId: tab.id }, "DOM.querySelector", {
      nodeId: root.nodeId, selector,
    });
    if (!nodeId) throw new Error(`元素不存在: ${selector}`);

    const { model: box } = await chrome.debugger.sendCommand(
      { tabId: tab.id }, "DOM.getBoxModel", { nodeId });
    const x = box.content[0];
    const y = box.content[1];
    const cx = x + box.width / 2;
    const cy = y + box.height / 2;

    await chrome.debugger.sendCommand({ tabId: tab.id }, "Input.dispatchMouseEvent", {
      type: "mousePressed", x: cx, y: cy, button: "left", clickCount: 1,
    });
    await chrome.debugger.sendCommand({ tabId: tab.id }, "Input.dispatchMouseEvent", {
      type: "mouseReleased", x: cx, y: cy, button: "left", clickCount: 1,
    });
    return "ok";
  } finally {
    await chrome.debugger.detach({ tabId: tab.id }).catch(() => {});
  }
}

async function cmdGetText() {
  const { tab } = await resolveScriptableTab();
  const results = await chrome.scripting.executeScript({
    target: { tabId: tab.id }, world: "MAIN",
    func: () => (document.body && document.body.innerText) || "",
  });
  return (results && results[0] && results[0].result) || "";
}

async function cmdGetUrl() {
  const { tab } = await pickTab();
  return (tab && tab.url) || "";
}

async function cmdGetHtml() {
  const { tab } = await resolveScriptableTab();
  const results = await chrome.scripting.executeScript({
    target: { tabId: tab.id }, world: "MAIN",
    func: () => (document.documentElement && document.documentElement.outerHTML) || "",
  });
  return (results && results[0] && results[0].result) || "";
}

async function cmdScreenshot() {
  const { tab } = await pickTab();
  // CDP 可截后台标签（captureVisibleTab 只能截当前可见标签）
  try {
    await chrome.debugger.attach({ tabId: tab.id }, "1.3");
    try {
      const res = await chrome.debugger.sendCommand({ tabId: tab.id },
        "Page.captureScreenshot", { format: "png" });
      if (res && res.data) return { data: res.data, via: "cdp", tabId: tab.id };
      throw new Error("CDP 未返回截图数据");
    } finally {
      await chrome.debugger.detach({ tabId: tab.id }).catch(() => {});
    }
  } catch (e) {
    console.warn("[Browser Bridge] CDP 截图失败，回退 captureVisibleTab：", (e && e.message) || e);
    const dataUrl = await chrome.tabs.captureVisibleTab(tab.windowId, { format: "png" });
    return { data: dataUrl.split(",")[1], via: "captureVisibleTab", tabId: tab.id };
  }
}

async function cmdScrollTo({ x = 0, y = 0 }) {
  const { tab } = await resolveScriptableTab();
  await chrome.scripting.executeScript({
    target: { tabId: tab.id }, world: "MAIN",
    func: (px, py) => window.scrollTo(px, py),
    args: [x, y],
  });
  return "ok";
}

async function cmdListTabs() {
  const tabs = (await chrome.tabs.query({})) || [];
  const remembered = await getLastTabId();
  return tabs.map((t) => ({
    id: t.id,
    title: t.title || "",
    url: t.url || "",
    active: !!t.active,
    privileged: isPrivileged(t.url),
    remembered: t.id === remembered,
  }));
}

/** 扩展自检 + 已收集的错误（供 CLI 直接读取，无需人工点 chrome://extensions） */
async function cmdGetDiagnostics() {
  const d = await diagRead();
  const selfCheck = {
    version: VERSION,
    apis: {
      scripting: !!chrome.scripting,
      debugger: !!chrome.debugger,
      storageSession: !!(chrome.storage && chrome.storage.session),
      storageLocal: !!(chrome.storage && chrome.storage.local),
      alarms: !!chrome.alarms,
      tabs: !!chrome.tabs,
      action: !!chrome.action,
    },
    wsState: ws ? ws.readyState : null,
    wsStateText: ws ? ["CONNECTING", "OPEN", "CLOSING", "CLOSED"][ws.readyState] || ws.readyState : "null",
    heartbeatActive: !!heartbeatTimer,
    reconnectDelayMs: reconnectDelay,
    lastTabId: await getLastTabId(),
    lastUrl: (await store.get("lastUrl")) || null,
  };
  let openTabsBrief = [];
  try {
    const tabs = (await chrome.tabs.query({})) || [];
    openTabsBrief = tabs.map((t) => ({ id: t.id, url: t.url || "", active: !!t.active }));
  } catch (e) { openTabsBrief = [{ error: String(e) }]; }

  return { selfCheck, openTabs: openTabsBrief, diagnostics: d };
}

async function cmdClearDiagnostics() {
  await diagWrite({ errors: [], cmdFails: [], boot: null, boots: 0 });
  return { ok: true };
}

/**
 * 直接读取 chrome://extensions 卡片上的「错误」详情（CDP 通道）。
 * Chrome 限制：debugger 可能无法 attach 到 chrome:// 页面，失败会返回原因。
 */
async function cmdProbeExtErrors() {
  let targets = [];
  try {
    targets = (await chrome.debugger.getTargets()) || [];
  } catch (e) {
    return { ok: false, reason: "getTargets 失败: " + String(e.message || e) };
  }
  const cand = targets.filter((x) => x.type === "page" && /^chrome:\/\/extensions/i.test(x.url || ""));
  if (!cand.length) {
    const pages = targets.filter((x) => x.type === "page").map((x) => x.url);
    return { ok: false, reason: "未找到 chrome://extensions 标签页", pages: pages.slice(0, 20) };
  }
  const tabId = cand[0].tabId;
  try {
    await chrome.debugger.attach({ tabId }, "1.3");
  } catch (e) {
    return { ok: false, reason: "attach 失败（Chrome 通常禁止调试 chrome:// 页面）: " + String(e.message || e) };
  }
  try {
    const expr = `(() => {
      const m = document.querySelector('extensions-manager');
      const items = m && m.shadowRoot ? Array.from(m.shadowRoot.querySelectorAll('extensions-item')) : [];
      const out = [];
      for (const it of items) {
        const sr = it.shadowRoot;
        if (!sr) continue;
        const nameEl = sr.querySelector('#name');
        const name = nameEl ? nameEl.textContent.trim() : '';
        const errBtn = sr.querySelector('#errors-button');
        const errBox = sr.querySelector('#errors');
        const btnVisible = errBtn && errBtn.offsetParent !== null;
        if (btnVisible) {
          out.push({ name, button: (errBtn.textContent || '').trim(), detail: errBox ? errBox.innerText : '' });
        }
      }
      return { pageTitle: document.title, items: out };
    })()`;
    const res = await chrome.debugger.sendCommand({ tabId }, "Runtime.evaluate",
      { expression: expr, returnByValue: true, awaitPromise: false });
    if (res && res.exceptionDetails) {
      return { ok: false, reason: "页面求值异常: " + JSON.stringify(res.exceptionDetails).slice(0, 300) };
    }
    return { ok: true, result: res && res.result ? res.result.value : null };
  } catch (e) {
    return { ok: false, reason: "sendCommand 失败: " + String(e.message || e) };
  } finally {
    await chrome.debugger.detach({ tabId }).catch(() => {});
  }
}

/**
 * 自我热重载：磁盘上的扩展代码改动后，无需人工到 chrome://extensions 点刷新。
 * 先回执、再延迟 reload，保证 CLI 能收到响应。
 * ⚠️ reload 会清空 chrome.storage.session（lastUrl/lastTabId 归零）→ 之后需重新 navigate。
 */
async function cmdReloadSelf({ delayMs = 1200 } = {}) {
  const ms = Math.max(300, Math.min(10000, Number(delayMs) || 1200));
  setTimeout(() => {
    try {
      console.log("[Browser Bridge] 收到 reload_self，正在重新加载扩展");
      chrome.runtime.reload();
    } catch (e) {
      recordError("reload_self", e);
    }
  }, ms);
  return { ok: true, reloadInMs: ms, note: "扩展即将重新加载；storage.session 会被清空，随后需重新 navigate" };
}

// ─── Tab 等待 ──────────────────────────────

function waitForTabComplete(tabId, timeout) {
  return new Promise((resolve) => {
    let done = false;
    const finish = () => {
      if (done) return;
      done = true;
      chrome.tabs.onUpdated.removeListener(listener);
      clearTimeout(timer);
      resolve();
    };

    function listener(id, info) {
      if (id !== tabId) return;
      if (info.status !== "complete") return;
      finish();
    }
    chrome.tabs.onUpdated.addListener(listener);
    const timer = setTimeout(finish, timeout);   // 超时也返回，不阻塞
  });
}

// ─── 状态通知 ──────────────────────────────

function setStatus(connected) {
  try {
    chrome.action.setBadgeText({ text: connected ? "ON" : "" });
    chrome.action.setBadgeBackgroundColor({ color: connected ? "#4CAF50" : "#999" });
  } catch { /* 忽略 */ }
}

// ─── 启动 ──────────────────────────────────

// 启动自检记录（诊断"扩展何时重启过、报过什么错"）
(async () => {
  try {
    const d = await diagRead();
    d.boots = (d.boots || 0) + 1;
    d.boot = { v: VERSION, at: new Date().toISOString(), ua: navigator.userAgent };
    await diagWrite(d);
  } catch { /* 忽略 */ }
})();

connect();

// 兜底：定时检查连接（SW 被回收重启后也会重新注册）
setInterval(() => {
  if (!ws || ws.readyState !== WebSocket.OPEN) connect();
}, 10000);

// alarms 兜底拉起 SW（Chrome 120+ 最小 30s）
try {
  chrome.alarms.create("keepAlive", { periodInMinutes: 0.5 });
  chrome.alarms.onAlarm.addListener((alarm) => {
    if (alarm.name !== "keepAlive") return;
    if (!ws || ws.readyState !== WebSocket.OPEN) connect();
    else {
      try { ws.send(JSON.stringify({ type: "heartbeat", ts: Date.now() })); } catch {}
    }
  });
} catch (e) {
  console.warn("[Browser Bridge] alarms 不可用", e);
}
