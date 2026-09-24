# XHS Creator Platform - DOM Reverse Engineering Notes

Last updated: 2026-05-18

## Platform URL

- Creator home: `https://creator.xiaohongshu.com`
- Publish page: `https://creator.xiaohongshu.com/publish/publish`

## Login Flow

- Not logged in → redirects to `passport.xiaohongshu.com` or URL contains `login`
- Login page shows QR code for WeChat scan
- After successful login, redirects back to `creator.xiaohongshu.com` (no `login`/`passport` in URL)
- Login state persists via cookies in Chromium persistent context

## Publish Page Tabs

The `/publish/publish` page has 4 tabs:
1. 上传视频 (Upload Video)
2. **上传图文 (Upload Image-Text)** ← our target
3. 写长文 (Write Long Article)
4. 发播客 (Publish Podcast)

### Tab DOM Structure

Tabs are rendered as elements with classes containing `tab`, `nav`, or `menu`. The text content of each tab is a direct text node.

**Critical issue**: Clicking a tab via Playwright or even JS `element.click()` may report success but NOT actually switch the view. The SPA's virtual DOM or event handling sometimes swallows the click.

### How to Detect Active Tab

Check the `accept` attribute of `input[type="file"]` elements:
- **Video mode**: `accept=".mp4,.mov,.flv,.mkv,.rm,.avi,.ts"` (dot prefix on each extension)
- **Image mode**: `accept="image/*"` or contains `png|jpg|jpeg|gif|webp`

Detection regex for video-only:
```javascript
/^\.(mp4|mov|flv|mkv|rm|avi|ts)(,|$)/i
```
Note the `^\.` — the accept string starts with a dot before each extension.

## Editor DOM

### Contenteditable Elements

The editor uses `[contenteditable="true"]` elements, NOT `<textarea>`.

**Two known layouts:**

1. **Single element** (most common as of 2026-05):
   - One `[contenteditable="true"]` handles BOTH title and body
   - Title is typed first, then `Enter`×2 to create visual separation
   - Body paragraphs follow, separated by `Enter`×2

2. **Dual elements** (older or alternative layout):
   - `[0]` = title field
   - `[1]` = body field

**Always detect the count first:**
```javascript
const editors = page.locator('[contenteditable="true"]');
const edCount = await editors.count();
```

### Topic Tags

Topics are NOT entered via a separate input field. They are typed directly into the contenteditable body:

1. Type `#topicName` → dropdown appears with suggestions
2. Press `Enter` → confirms the selected topic
3. Press `Escape` → closes the dropdown

The dropdown sometimes stays open after Enter, so Escape is needed to dismiss it before typing the next topic.

## Publish Button

The publish button is a `<button>` element with text "发布". It may be nested inside various containers with classes like `publish-btn` or use Element UI's `el-button--primary`.

**Multiple locator strategies needed** because the button's position in DOM varies and sometimes Playwright can't find it with simple selectors. See the reference script for the full fallback chain.

## File Input Behavior

- The file input is hidden (`display: none` or similar) — use `setInputFiles()` directly
- In video mode, the input does NOT have `multiple` attribute → setting multiple files crashes with "Non-multiple file input can only accept single file"
- In image mode, the input accepts multiple files
- **This is why tab switch verification is critical** — uploading images to a video input = crash

## Anti-Detection Notes

XHS may detect automation. Recommended mitigations:
- Use real Chrome (`channel: 'chrome'`), not Chromium
- Disable `AutomationControlled` feature flags
- Use persistent context (same profile each time)
- Add human-like delays between actions (`delay: 5-12` ms in `keyboard.type()`)
- Avoid `headless: true` for publishing (QR login doesn't work headless anyway)

## Session Persistence

Chromium persistent context stores all cookies, localStorage, and session data in the specified directory. First run = manual QR scan. Subsequent runs = automatic login.

**Important**: Delete `SingletonLock` file before each launch — it prevents Chrome from starting if a previous session crashed.
