---
name: xiaohongshu-publisher
description: Automate publishing notes (图文笔记) to Xiaohongshu Creator Platform
  (creator.xiaohongshu.com) via Playwright browser automation. Covers login
  persistence, tab switching, image upload, title/body/topic filling, and
  publish. Triggers when the user asks to publish/post/发布 to Xiaohongshu
  (小红书/XHS), or auto-publish XHS content. **本技能是小红书「发布」动作的唯一执行者**：要端到端编排（调研+写作+配图+发布）请用 `xhs-one-click-publish`；要登录态的搜索/评论/点赞/收藏请用 `xhs-automation-suite`；只读数据分析请用 `xhs-research`。
agent_created: true
---

# Xiaohongshu Auto-Publisher

## 定位：小红书发布动作的唯一执行者

本技能是**发布环节的唯一执行方**，也是发布技术的真相源（Creator Platform DOM、Shadow DOM 发布按钮、防检测、登录态持久化）。

| 你要做的事 | 该用哪个技能 |
|---|---|
| 端到端一次做完（调研→写→图→发布→验证） | `xhs-one-click-publish`（编排层，省 Credit） |
| **已有内容，只差发出去** | **本技能** ← |
| 登录态搜索 / 评论 / 点赞 / 收藏 / 主页抓取 | `xhs-automation-suite`（不做发布） |
| 只读数据分析（选题/竞品/趋势/博主/评论） | `xhs-research` |
| 生成趋势/榜单卡片图 | `xhs-trending-cards` |

---


Automate the full workflow of publishing 图文笔记 (image-text notes) to Xiaohongshu Creator Platform using Playwright with persistent Chrome sessions.

## When to Use

- User asks to publish/发布/推送 content to Xiaohongshu (小红书/XHS)
- User wants to auto-publish a drafted note to XHS
- User needs to verify XHS publishing status

## Prerequisites

- **Playwright** must be installed: `npm install playwright`
- **Browser options:**
  - **System Chrome** (preferred): `channel: 'chrome'` — requires Chrome installed on system
  - **Built-in Chromium** (macOS sandbox workaround): omit `channel`, Playwright uses bundled Chromium. Use this when Mach IPC sandbox restrictions block system Chrome. Note: built-in Chromium avoids `MachPortRendezvousServer Permission denied` errors on macOS
- **First run requires manual QR login** — subsequent runs reuse the persistent session
- **macOS users:** Playwright browser launch may be blocked inside WorkBuddy sandbox. Run scripts from Terminal.app directly if you encounter sandbox errors

## Critical DOM Knowledge (XHS Creator Platform)

These are non-obvious findings from reverse-engineering the SPA. They are the core value of this skill.

### 1. Single contenteditable for Title AND Body

XHS uses only ONE `[contenteditable="true"]` element for both title and body — NOT separate elements.

**Detection logic:**
```
editors = page.locator('[contenteditable="true"]')
edCount = await editors.count()
```

- **If edCount >= 2**: `[0]` = title, `[1]` = body (older/rare layout)
- **If edCount === 1**: Same element for both. Fill title → `Enter` `Enter` → body paragraphs sequentially
- **Fallback**: `textarea` elements (unlikely but handle gracefully)

**For edCount === 1 (most common):**
```javascript
await editors.nth(0).click({ force: true });
await page.keyboard.type(title, { delay: 8 });
await page.keyboard.press('Enter');
await page.keyboard.press('Enter');
// Then type body paragraphs separated by double Enter
const paragraphs = body.split('\n\n');
for (let i = 0; i < paragraphs.length; i++) {
  await page.keyboard.type(paragraphs[i], { delay: 5 });
  if (i < paragraphs.length - 1) {
    await page.keyboard.press('Enter');
    await page.keyboard.press('Enter');
  }
}
```

### 2. Tab Switching is Unreliable

The "上传图文" tab in `/publish/publish` often reports a successful click but doesn't actually switch the view. This is the #1 source of crashes.

**Mandatory post-switch verification:**
```javascript
// After clicking the tab, VERIFY the file input accept attribute changed
const allInputs = page.locator('input[type="file"]');
for (let i = 0; i < await allInputs.count(); i++) {
  const accept = await allInputs.nth(i).getAttribute('accept') || '';
  const isVideoOnly = accept.match(/^\.(mp4|mov|flv|mkv|rm|avi|ts)(,|$)/i)
    && !accept.match(/png|jpg|jpeg|gif|webp|image/i);
  if (!isVideoOnly) { hasImageInput = true; break; }
}
```

**If still in video mode, retry with TreeWalker + mouse event dispatch:**
```javascript
await page.evaluate(() => {
  const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let node;
  while (node = walk.nextNode()) {
    if (node.textContent.trim() === '上传图文') {
      const parent = node.parentElement;
      if (parent) {
        parent.click();
        ['mousedown', 'mouseup', 'click'].forEach(evt => {
          parent.dispatchEvent(new MouseEvent(evt, { bubbles: true }));
        });
      }
    }
  }
});
```

### 3. File Input Accept Attribute Has Dot Prefix

Video tab's accept is `.mp4,.mov,.flv,...` (with leading dot). The regex MUST account for this:

```javascript
// CORRECT: matches ".mp4,.mov"
/^\.(mp4|mov|flv|mkv|rm|avi|ts)(,|$)/i

// WRONG: misses ".mp4" because it expects "mp4" without the dot
/^(mp4|mov|flv|mkv|rm|avi|ts)/
```

Image tab's accept is typically `image/*` or contains `png/jpg/jpeg/gif/webp`.

### 4. Topic Tags via Keyboard Input

Topics are added by typing `#topicName` then pressing `Enter` to confirm from the dropdown. Press `Escape` after each to close the dropdown popup:

```javascript
for (const topic of topics) {
  await page.keyboard.type(`#${topic}`, { delay: 12 });
  await sleep(400);
  await page.keyboard.press('Enter');   // Confirm from dropdown
  await sleep(400);
  await page.keyboard.press('Escape');  // Close dropdown
  await sleep(200);
}
```

### 6. CRITICAL: Publish Button is Inside Closed Shadow DOM (2026-06-01 verified)

**THE publish button lives inside `#shadow-root (closed)` — standard DOM queries CANNOT find it.**

DOM structure (verified via Chrome DevTools Elements panel):
```
div.publish-page-publish-btn          ← 正常DOM，宿主元素（clickable, 可见）
  └── #shadow-root (closed)           ← 关闭的Shadow DOM！
      ├── <style>...</style>
      └── div.xhs-publish-btn
           └── div.publish-btn        ← 红色圆角按钮，"发布"文字在这里
```

CSS: `div.publish-page-publish-btn { width: 100%; height: 100px; min-height: 90px; }` — 底部悬浮框

**Why standard approaches failed:**
- `document.querySelectorAll('*')` — 扫不到 shadow root 内部
- `page.locator('button')` — Playwright 默认不穿透 closed shadow
- `page.locator('text=发布')` — 同样无法匹配 shadow 内部文字
- `element.innerText` — 同样无法获取 shadow DOM 内部文本，所以基于 innerText 的按钮检测也无效
- 只有 `#shadow-root (open)` 才可被 `element.shadowRoot` 访问

**BEST PRACTICE (2026-06-25 verified):**
由于 shadow DOM 中的 "发布" 文字无法通过 `innerText` 扫描到，**不要依赖文字匹配**来定位发布按钮。
最可靠的方式是底部坐标扫描：

```javascript
// 底部坐标网格扫描 — 绕开 Shadow DOM
const vp = page.viewportSize();
const ys = [vp.height - 40, vp.height - 60, vp.height - 80, vp.height - 100, vp.height - 120];
const xs = [vp.width - 200, vp.width - 150, vp.width - 100, vp.width / 2 + 200, vp.width / 2];
for (const y of ys) {
  for (const x of xs) {
    await page.mouse.click(x, y);
    await sleep(1500);
    if (await checkPublishSuccess(page, beforeBodyLength)) return true;
  }
}
```

**Before grid scan: always save as draft first (Cmd+S)** — 这样即使扫描失败，内容也不丢失。

**What NOT to do:**
- ❌ 不要优先点击侧栏 `x < 200` 的"发布笔记"按钮 — 它会导航回发布首页，丢弃当前编辑内容
- ❌ 不要只依赖 `innerText === '发布'` 来定位按钮 — 它在 shadow DOM 内部，扫不到

```javascript
// 方式1: 多class模式尝试 + boundingBox坐标点击
const classPatterns = [
  '[class*="publish-page-publish"]',
  '[class*="publish-btn"]',
  '[class*="PublishBtn"]',
  '[class*="publish-bar"]',
];
for (const pattern of classPatterns) {
  const el = page.locator(pattern);
  if (await el.count() > 0) {
    const box = await el.first().boundingBox();
    if (box) await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
    // Click then sleep 2s, check for confirmation dialog
    await sleep(2000);
    const hasDialog = await page.evaluate(() => /确认发布|确定发布/.test(document.body.innerText));
    if (hasDialog) break; // success!
  }
}

// 方式2 (推荐): 遍历所有 xhs-publish-btn，逐个尝试
const count = await page.locator('xhs-publish-btn').count();
for (let i = 0; i < count; i++) {
  const el = page.locator('xhs-publish-btn').nth(i);
  const box = await el.boundingBox();
  if (!box || box.height < 20) continue;
  
  // Try Playwright native click first
  await el.scrollIntoViewIfNeeded();
  await el.click({ force: true, timeout: 3000 });
  await sleep(2000);
  
  // If no response, try coordinate clicks with horizontal offsets
  const offsets = [[0,0], [box.width*0.3, 0], [box.width*0.6, 0]];
  for (const [ox, oy] of offsets) {
    await page.mouse.click(box.x + box.width/2 + ox, box.y + box.height/2);
    await sleep(2000);
    if (await page.evaluate(() => /确认发布|确定发布/.test(document.body.innerText))) break;
  }
}

// 方式3 (推荐): addInitScript 强制开放 shadow DOM 后精确穿透
// 必须在 page 创建后、首次 navigation 前注入
await page.addInitScript(() => {
  const orig = Element.prototype.attachShadow;
  Element.prototype.attachShadow = function(options) {
    return orig.call(this, { ...options, mode: 'open' });
  };
});

// 然后使用 JS evaluate 穿透访问 shadowRoot
const published = await page.evaluate(() => {
  const btns = document.querySelectorAll('xhs-publish-btn, [class*="publish"]');
  for (const host of btns) {
    const sr = host.shadowRoot;
    if (!sr) continue;
    const all = sr.querySelectorAll('*');
    for (const el of all) {
      if (el.children.length > 0) continue;
      const text = (el.textContent || '').trim();
      if (text === '发布' || text === '发布笔记') {
        // 找到发布按钮！向上找可点击父元素
        let target = el;
        for (let p = el.parentElement; p && p !== sr; p = p.parentElement) {
          if (p.tagName === 'BUTTON' || window.getComputedStyle(p).cursor === 'pointer') target = p;
        }
        ['mousedown', 'mouseup', 'click'].forEach(e =>
          target.dispatchEvent(new MouseEvent(e, { bubbles: true, composed: true })));
        target.click();
        return true;
      }
    }
  }
  return false;
});

// 方式4: JS 兜底 — 遍历所有 xhs-publish-btn 宿主
await page.evaluate(() => {
  for (const host of document.querySelectorAll('xhs-publish-btn')) {
    host.click();
    ['mousedown', 'mouseup', 'click'].forEach(e =>
      host.dispatchEvent(new MouseEvent(e, { bubbles: true })));
  }
});

// 方式4: 底部区域网格扫描 — y从vp.h-70到vp.h-30，x从200到800
const vp = page.viewportSize();
for (const y of [vp.height-30, vp.height-50, vp.height-70]) {
  for (const x of [400, 550, 300, 600, 700, 200, 800]) {
    await page.mouse.click(x, y);
    await sleep(1500);
    if (await page.evaluate(() => /确认发布|确定发布/.test(document.body.innerText))) return;
  }
}
```

**Key principle**: Click → wait 1.5-2s → check `document.body.innerText` for "确认发布"/"确定发布"/"发布成功" → if found, success. If not, try next position. Do not assume a single click works.<｜end▁of▁thinking｜>

<｜｜DSML｜｜tool_calls>
<｜｜DSML｜｜invoke name="Edit">
<｜｜DSML｜｜parameter name="file_path" string="true">/Users/yoyo/.workbuddy/skills/xiaohongshu-publisher/SKILL.md

**Post-click**: 等待弹窗 → 自动点击确认 → 等待URL跳转或成功文字

### 5. Publish Button (Legacy — pre Shadow DOM)

## Full Workflow

See `scripts/publish_xhs.js` for the complete reference implementation.

### Step-by-Step Summary

1. **Launch browser** — `chromium.launchPersistentContext()` with `channel: 'chrome'`, remove `SingletonLock` first
2. **Login** — Navigate to `creator.xiaohongshu.com`, wait for redirect. If URL contains `login`/`passport`, wait up to 5 minutes for QR scan
3. **Navigate to publish page** — `creator.xiaohongshu.com/publish/publish`
4. **Switch to "上传图文" tab** — JS click + verify file input accept attribute + retry if needed
5. **Upload images** — Find non-video file input, use `setInputFiles()` with all images at once
6. **Fill content** — Detect contenteditable count, handle single vs dual element cases
7. **Add topics** — Type `#topic` + Enter + Escape for each topic
8. **Publish** — Escape popups, scroll to bottom, try multiple button strategies
9. **Verify** — Screenshot the result page

## Session Persistence

Login state is stored in a `.xhs-session/` directory (configurable). First run requires manual QR code scan. Subsequent runs reuse cookies automatically.

**Always remove `SingletonLock` before launch:**
```javascript
const lockFile = path.join(SESSION_DIR, 'SingletonLock');
if (fs.existsSync(lockFile)) fs.unlinkSync(lockFile);
```

## Anti-Detection

```
args: [
  '--no-sandbox',
  '--disable-blink-features=AutomationControlled',
  '--disable-features=AutomationControlled',
]
```

## Debugging

Take screenshots at each major step:
- After tab switch (`debug-after-tab.png`)
- After image upload (`debug-uploaded.png`)
- After content fill (`debug-filled.png`)
- Before publish click (`debug-before-publish.png`) — **key debug image**
- After publish click (`debug-after-publish.png`)

## Common Failures

| Symptom | Root Cause | Fix |
|---------|-----------|-----|
| "Non-multiple file input" crash | Tab didn't switch, video input used for images | Verify `hasImageInput` after tab switch |
| Title empty in published note | Tried `contenteditable[1]` when only `[0]` exists | Check `edCount` first, handle `=== 1` case |
| Tab click "succeeds" but doesn't switch | SPA virtual DOM, click event swallowed | Use TreeWalker + mouse event dispatch + retry |
| Regex doesn't match accept | Missing `^\.` prefix for `.mp4` format | Use `/^\.(mp4\|mov\|...)/i` |
| Note saved as draft, not published | Popups blocking publish button | Press Escape 3× before publish, scroll to bottom |
| Publish button click has no effect | Button is a span inside a DIV, parent handles click | JS strategy must target parent BUTTON if leaf is a text span |
| Mach port permission denied (macOS) | Sandbox blocks Chrome/Chromium IPC | Use built-in Chromium (omit `channel: 'chrome'`), run from Terminal.app |
| All publish strategies fail silently | Button exists but is disabled (images still uploading, content validation) | Wait 15+ seconds after image upload, check candidate `disabled` field in diagnostic |
| **Content lost after publish attempt** | Publish click navigated to publish home page | **Always Cmd+S save draft before attempting publish** |
| **net::ERR_ABORTED on navigation** | Stale SingletonLock/SingletonCookie from previous crash | Clean all Singleton* files in session dir before launch |
| **"发布" button not found by `innerText`** | Text lives in `#shadow-root (closed)` — undetectable | Use bottom coordinate grid scan instead |
