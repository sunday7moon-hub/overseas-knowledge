/**
 * Xiaohongshu Auto-Publisher - Reference Script
 *
 * Usage:
 *   node publish_xhs.js --note-config /path/to/config.json --session-dir /path/to/.xhs-session
 *
 * Note config JSON format:
 * {
 *   "title": "笔记标题",
 *   "content": "正文内容（\\n\\n 分段）",
 *   "images": ["/path/to/img1.png", "/path/to/img2.png"],
 *   "topics": ["话题1", "话题2"]
 * }
 *
 * If --note-config is omitted, uses DEFAULT_NOTE below.
 * If --session-dir is omitted, uses ./xhs-session in script directory.
 *
 * v2.0 — 2026-06-25 修复日志：
 *   - 新增发布前 Cmd+S 保存草稿，防止内容丢失
 *   - 修复发布按钮点击策略：排除侧栏"发布笔记"按钮（会跳回发布首页）
 *   - 新增底部坐标网格扫描（策略5），绕开 Shadow DOM 封闭问题
 *   - 新增 Singleton 锁文件全面清理
 */

const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

// ============ CONFIGURATION ============
const DEFAULT_NOTE = {
  title: '在这里填入标题',
  content: '在这里填入正文内容',
  images: [],
  topics: ['话题1', '话题2'],
};

const XHS_URL = 'https://creator.xiaohongshu.com';

function parseArgs() {
  const args = process.argv.slice(2);
  let noteConfig = null, sessionDir = null;
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--note-config' && args[i + 1]) noteConfig = args[++i];
    if (args[i] === '--session-dir' && args[i + 1]) sessionDir = args[++i];
  }
  return { noteConfig, sessionDir };
}

function loadConfig(args) {
  const NOTE = args.noteConfig && fs.existsSync(args.noteConfig)
    ? JSON.parse(fs.readFileSync(args.noteConfig, 'utf-8'))
    : DEFAULT_NOTE;

  const SESSION_DIR = args.sessionDir
    ? path.resolve(args.sessionDir)
    : path.resolve(__dirname, '.xhs-session');

  return { NOTE, SESSION_DIR };
}

// ============ UTILITIES ============
function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function safeClick(locator, timeout = 5000) {
  try { await locator.click({ timeout }); return true; } catch { return false; }
}

async function safeVisible(locator, timeout = 3000) {
  try { return await locator.isVisible({ timeout }); } catch { return false; }
}

/**
 * Check if the current file inputs include an image-type input (not video-only).
 */
async function hasImageInput(page) {
  const allInputs = page.locator('input[type="file"]');
  const count = await allInputs.count();
  for (let i = 0; i < count; i++) {
    const accept = await allInputs.nth(i).getAttribute('accept') || '';
    const isVideoOnly = accept.match(/^\.(mp4|mov|flv|mkv|rm|avi|ts)(,|$)/i)
      && !accept.match(/png|jpg|jpeg|gif|webp|image/i);
    if (!isVideoOnly) return true;
  }
  return false;
}

/**
 * Find the image file input (non-video) on the page.
 */
async function findImageInput(page) {
  const allInputs = page.locator('input[type="file"]');
  const count = await allInputs.count();
  for (let i = 0; i < count; i++) {
    const fi = allInputs.nth(i);
    const accept = await fi.getAttribute('accept') || '';
    const isVideoOnly = accept.match(/^\.(mp4|mov|flv|mkv|rm|avi|ts)(,|$)/i)
      && !accept.match(/png|jpg|jpeg|gif|webp|image/i);
    if (!isVideoOnly) return fi;
  }
  return null;
}

// ============ CORE FUNCTIONS ============

/**
 * Launch browser with persistent session for login reuse.
 * Cleans all Singleton lock files to prevent navigation errors.
 */
async function launchBrowser(sessionDir) {
  // Clean all singleton lock files (stale locks cause net::ERR_ABORTED)
  for (const f of ['SingletonLock', 'SingletonCookie', 'SingletonSocket']) {
    const fp = path.join(sessionDir, f);
    if (fs.existsSync(fp)) fs.unlinkSync(fp);
  }

  if (!fs.existsSync(sessionDir)) fs.mkdirSync(sessionDir, { recursive: true });

  return chromium.launchPersistentContext(sessionDir, {
    headless: false,
    channel: 'chrome',
    viewport: { width: 1920, height: 1080 },
    locale: 'zh-CN',
    args: [
      '--no-sandbox',
      '--start-maximized',
      '--window-size=1920,1080',
      '--disable-blink-features=AutomationControlled',
      '--disable-features=AutomationControlled',
    ],
  });
}

/**
 * Handle login — wait for QR scan if needed.
 */
async function ensureLogin(page) {
  await page.goto(XHS_URL, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForLoadState('load', { timeout: 30000 }).catch(() => {});
  await sleep(4000);

  const url = page.url();
  if (url.includes('login') || url.includes('passport')) {
    console.log('========================================');
    console.log('  需要登录 - 请在浏览器中扫码');
    console.log('========================================');
    try {
      await page.waitForURL(u => {
        const s = u.toString();
        return s.includes('creator.xiaohongshu.com') && !s.includes('login') && !s.includes('passport');
      }, { timeout: 300000 });
      await sleep(3000);
      console.log('  登录成功！');
    } catch {
      console.error('  登录超时（5分钟）');
      return false;
    }
  } else {
    console.log('  已登录（复用上次的session）');
  }
  return true;
}

/**
 * Switch to "上传图文" tab with retry and verification.
 */
async function switchToImageTab(page, maxRetries = 4) {
  await page.goto(`${XHS_URL}/publish/publish`, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForLoadState('load', { timeout: 30000 }).catch(() => {});
  await sleep(3000);

  for (let attempt = 0; attempt < maxRetries; attempt++) {
    await page.evaluate(() => {
      const tabs = document.querySelectorAll('[class*="tab"], [class*="nav"], [class*="menu"]');
      for (const tab of tabs) {
        if (tab.textContent && tab.textContent.trim() === '上传图文') { tab.click(); return; }
      }
      const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
      let node;
      while (node = walk.nextNode()) {
        if (node.textContent.trim() === '上传图文') {
          const parent = node.parentElement;
          if (parent && parent.offsetParent !== null) {
            parent.click();
            ['mousedown', 'mouseup', 'click'].forEach(evt => {
              parent.dispatchEvent(new MouseEvent(evt, { bubbles: true }));
            });
          }
        }
      }
    });
    await sleep(3000);

    if (await hasImageInput(page)) {
      console.log(`  Tab切换成功 (attempt ${attempt + 1})`);
      return true;
    }
    console.log(`  Tab切换未生效，重试 (${attempt + 1}/${maxRetries})...`);
  }

  await page.locator('text=上传图文').first().click({ force: true }).catch(() => {});
  await sleep(3000);
  return await hasImageInput(page);
}

/**
 * Upload images via file input.
 */
async function uploadImages(page, imagePaths) {
  const validImages = imagePaths.filter(p => fs.existsSync(p));
  if (validImages.length === 0) throw new Error('没有找到有效的图片文件');

  const input = await findImageInput(page);
  if (!input) throw new Error('找不到图片上传入口（可能仍在视频模式）');

  await input.setInputFiles(validImages);
  console.log(`  已上传 ${validImages.length} 张图片，等待处理...`);
  await sleep(12000);
}

/**
 * Fill title and body, handling the single-contenteditable quirk.
 */
async function fillContent(page, title, content, topics) {
  const editors = page.locator('[contenteditable="true"]');
  const edCount = await editors.count();
  console.log(`  contenteditable 数量: ${edCount}`);

  if (edCount >= 2) {
    await editors.nth(0).click({ force: true });
    await sleep(200);
    await page.keyboard.press('Meta+A');
    await sleep(80);
    await page.keyboard.type(title, { delay: 8 });

    await editors.nth(1).click({ force: true });
    await sleep(300);
    const paragraphs = content.split('\n\n');
    for (let i = 0; i < paragraphs.length; i++) {
      await page.keyboard.type(paragraphs[i], { delay: 5 });
      if (i < paragraphs.length - 1) { await page.keyboard.press('Enter'); await page.keyboard.press('Enter'); }
    }

  } else if (edCount === 1) {
    await editors.nth(0).click({ force: true });
    await sleep(300);
    await page.keyboard.type(title, { delay: 8 });
    await page.keyboard.press('Enter');
    await page.keyboard.press('Enter');
    await sleep(200);

    const paragraphs = content.split('\n\n');
    for (let i = 0; i < paragraphs.length; i++) {
      const p = paragraphs[i];
      if (!p) { await page.keyboard.press('Enter'); await page.keyboard.press('Enter'); continue; }
      await page.keyboard.type(p, { delay: 5 });
      if (i < paragraphs.length - 1) { await page.keyboard.press('Enter'); await page.keyboard.press('Enter'); }
    }

  } else {
    const tas = page.locator('textarea');
    const taCount = await tas.count();
    for (let i = 0; i < taCount; i++) {
      const ph = await tas.nth(i).getAttribute('placeholder') || '';
      if (ph.includes('标题') || (i === 0 && taCount > 1)) {
        await tas.nth(i).click(); await tas.nth(i).fill(title); break;
      }
    }
  }

  // Add topic tags
  await page.keyboard.press('Enter');
  await page.keyboard.press('Enter');
  for (const topic of topics) {
    await page.keyboard.type(`#${topic}`, { delay: 12 });
    await sleep(400);
    await page.keyboard.press('Enter');
    await sleep(400);
    await page.keyboard.press('Escape');
    await sleep(200);
  }
  console.log('  内容填写完成');
}

/**
 * Save content as draft (Cmd+S / Ctrl+S).
 * Always call this BEFORE trying to publish, so content survives a failed publish attempt.
 */
async function saveAsDraft(page) {
  console.log('  保存草稿...');
  await page.keyboard.press('Meta+S');
  await sleep(3000);
  await page.keyboard.press('Enter');
  await sleep(2000);
}

/**
 * Check if publish succeeded.
 */
async function checkPublishSuccess(page, beforeBodyLength) {
  const url = page.url();
  if (!url.includes('/publish') || url.includes('success')) return true;
  if (url.includes('target=video') || url.includes('from=menu')) return 'TAB_SWITCHED';
  try {
    const toast = await page.locator('text=发布成功').first().isVisible({ timeout: 2000 }).catch(() => false);
    if (toast) return true;
  } catch {}
  try {
    const publishedText = await page.locator('text=已发布').first().isVisible({ timeout: 1000 }).catch(() => false);
    if (publishedText) return true;
  } catch {}
  try {
    const pubNote = await page.locator('text=笔记已发布').first().isVisible({ timeout: 1000 }).catch(() => false);
    if (pubNote) return true;
  } catch {}
  if (beforeBodyLength) {
    try {
      const currentLength = await page.evaluate(() => document.body.innerText.length);
      if (currentLength < beforeBodyLength * 0.3) return true;
    } catch {}
  }
  return false;
}

/**
 * Click the publish button.
 *
 * CRITICAL FINDING (2026-06-25): The "发布" button text lives inside
 * #shadow-root (closed) — standard innerText DOM queries CANNOT find it.
 * Therefore text-based button detection always misses the real button.
 * The reliable fallback is the bottom coordinate grid scan (Strategy 5).
 */
async function clickPublish(page) {
  const debugDir = path.resolve(__dirname);
  const beforeBodyLength = await page.evaluate(() => document.body.innerText.length);
  await page.screenshot({ path: path.join(debugDir, 'debug-before-publish.png') });

  // Dismiss popups
  for (let i = 0; i < 8; i++) { await page.keyboard.press('Escape'); await sleep(200); }

  // Scroll all containers to bottom
  await page.evaluate(() => {
    window.scrollTo(0, 99999);
    document.querySelectorAll('*').forEach(el => {
      try { if (el.scrollHeight > el.clientHeight) el.scrollTop = el.scrollHeight; } catch {}
    });
  });
  await sleep(2000);

  // Map all publish-related elements
  const allButtons = await page.evaluate(() => {
    const all = document.querySelectorAll('*');
    const result = [];
    for (const el of all) {
      const t = (el.innerText || el.textContent || '').trim();
      if ((t === '发布' || t === '发布笔记') && t.length < 20) {
        const r = el.getBoundingClientRect();
        if (r.width > 0 && r.height > 0) {
          result.push({
            tag: el.tagName,
            cls: (el.className || '').substring(0, 50),
            text: t,
            y: r.y, x: r.x, w: r.width, h: r.height,
            inSidebar: r.x < 200,
            isVisible: r.y > 0 && r.y < window.innerHeight,
          });
        }
      }
    }
    return result;
  });

  const mainButtons = allButtons.filter(b => !b.inSidebar && b.text === '发布').sort((a, b) => b.y - a.y);
  const visMain = mainButtons.filter(b => b.isVisible);

  // Strategy 1: Click visible bottom-most "发布" button in main area
  if (visMain.length > 0) {
    const target = visMain[0];
    console.log(`  策略1: 点击"${target.text}" at (${target.x},${target.y})`);
    await page.evaluate((y) => window.scrollTo(0, Math.max(0, y - 200)), target.y);
    await sleep(1000);
    try {
      const cls = target.cls.split(' ')[0];
      if (cls) {
        await page.locator(`[class*="${cls}"]`).filter({ hasText: target.text }).last()
          .click({ force: true, timeout: 5000 }).catch(() => {});
        await sleep(3000);
        if (await checkPublishSuccess(page, beforeBodyLength)) { console.log('  发布成功！'); return true; }
      }
      await page.mouse.click(target.x + target.w / 2, target.y + target.h / 2);
      await sleep(3000);
      if (await checkPublishSuccess(page, beforeBodyLength)) { console.log('  发布成功！(坐标)'); return true; }
    } catch {}
  }

  // Strategy 2: JS click main area buttons
  console.log(`  策略2: JS点击${mainButtons.length}个按钮`);
  await page.evaluate(() => {
    const all = document.querySelectorAll('*');
    const targets = [];
    for (const el of all) {
      const t = (el.innerText || el.textContent || '').trim();
      const r = el.getBoundingClientRect();
      if (t === '发布' && r.width > 0 && r.height > 0 && r.x >= 200) targets.push(el);
    }
    targets.sort((a, b) => b.getBoundingClientRect().y - a.getBoundingClientRect().y);
    for (const el of targets) {
      try {
        el.scrollIntoView({ block: 'center' });
        ['mousedown', 'mouseup', 'click'].forEach(e => el.dispatchEvent(new MouseEvent(e, { bubbles: true, composed: true })));
        el.click();
      } catch {}
    }
    return targets.length;
  });
  await sleep(5000);
  if (await checkPublishSuccess(page, beforeBodyLength)) { console.log('  发布成功！'); return true; }

  // Strategy 3: Find parent elements of "发布" text
  console.log('  策略3: 父元素查找...');
  await page.evaluate(() => {
    const all = document.querySelectorAll('*');
    for (const el of all) {
      const t = (el.innerText || el.textContent || '').trim();
      if (t === '发布') {
        let parent = el.parentElement;
        while (parent && parent !== document.body) {
          const tag = parent.tagName;
          const cls = (parent.className || '');
          if (tag === 'BUTTON' || tag === 'A' || cls.includes('btn') || cls.includes('publish')) {
            const r = parent.getBoundingClientRect();
            if (r.width > 0 && r.height > 0 && r.x >= 200) {
              parent.scrollIntoView({ block: 'center' });
              parent.click();
              ['mousedown', 'mouseup', 'click'].forEach(e =>
                parent.dispatchEvent(new MouseEvent(e, { bubbles: true, composed: true })));
              return;
            }
          }
          parent = parent.parentElement;
        }
      }
    }
  });
  await sleep(5000);
  if (await checkPublishSuccess(page, beforeBodyLength)) { console.log('  发布成功！'); return true; }

  // Strategy 4: Tab + Enter
  console.log('  策略4: Tab+Enter兜底...');
  for (let i = 0; i < 40; i++) { await page.keyboard.press('Tab'); await sleep(80); }
  await page.keyboard.press('Enter');
  await sleep(5000);
  if (await checkPublishSuccess(page, beforeBodyLength)) { console.log('  发布成功！'); return true; }

  // Strategy 5: Bottom coordinate grid scan (most reliable — bypasses Shadow DOM)
  // The "发布" button is always at viewport bottom, in the right/center area
  console.log('  策略5: 底部坐标网格扫描...');
  const vp = page.viewportSize();
  if (vp) {
    const ys = [vp.height - 40, vp.height - 60, vp.height - 80, vp.height - 100, vp.height - 120];
    const xs = [vp.width - 200, vp.width - 150, vp.width - 100, vp.width / 2 + 200, vp.width / 2, vp.width / 2 - 200];
    for (const y of ys) {
      for (const x of xs) {
        await page.mouse.click(x, y);
        await sleep(1500);
        if (await checkPublishSuccess(page, beforeBodyLength)) {
          console.log(`  发布成功！(坐标: ${x},${y})`);
          return true;
        }
      }
    }
  }

  console.log('  所有发布策略均失败');
  return false;
}

/**
 * If page was accidentally navigated to video mode, go back to image mode.
 */
async function ensureImageMode(page) {
  console.log('  恢复图文模式...');
  await page.goto('https://creator.xiaohongshu.com/publish/publish', { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForLoadState('load').catch(() => {});
  await sleep(3000);
  return await switchToImageTab(page);
}

// ============ MAIN ============

async function main() {
  const { noteConfig, sessionDir } = parseArgs();
  const { NOTE, SESSION_DIR } = loadConfig({ noteConfig, sessionDir });

  console.log('=== Xiaohongshu Auto-Publisher ===');
  console.log(`标题: ${NOTE.title}`);
  console.log(`图片: ${NOTE.images.length} 张`);
  console.log(`话题: ${NOTE.topics.join(', ')}`);
  console.log('');

  const browser = await launchBrowser(SESSION_DIR);
  const page = browser.pages()[0] || await browser.newPage();

  // Step 1: Login
  console.log('[1/5] 登录...');
  if (!(await ensureLogin(page))) {
    await browser.close(); process.exit(1);
  }

  // Step 2: Switch to image tab
  console.log('[2/5] 切换到上传图文...');
  if (!(await switchToImageTab(page))) {
    console.error('无法进入图文上传模式');
    await browser.close(); process.exit(1);
  }

  // Step 3: Upload images
  console.log('[3/5] 上传图片...');
  await uploadImages(page, NOTE.images);

  // Step 4: Fill content
  console.log('[4/5] 填写内容...');
  await fillContent(page, NOTE.title, NOTE.content, NOTE.topics);

  // Save as draft FIRST — content is preserved even if publish fails
  await saveAsDraft(page);

  // Step 5: Publish
  console.log('[5/5] 发布...');
  const published = await clickPublish(page);
  await sleep(5000);

  try {
    await page.screenshot({ path: path.join(__dirname, 'debug-after-publish.png') });
  } catch (_) {}

  if (published) {
    console.log('✅ 发布成功！');
  } else {
    console.log('⚠️ 自动发布未完全确认，请检查 debug-before-publish.png 和 debug-after-publish.png');
    console.log('  草稿已保存，可到 creator.xiaohongshu.com → 笔记管理 → 仅自己可见 手动发布');
  }
  await browser.close();
}

main().catch(err => { console.error('发布出错:', err); process.exit(1); });
