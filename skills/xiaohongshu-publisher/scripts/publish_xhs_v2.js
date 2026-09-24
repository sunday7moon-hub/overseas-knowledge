/**
 * Xiaohongshu Auto-Publisher v2 - Enhanced with Draft Checking
 *
 * Usage:
 *   node publish_xhs_v2.js --note-config /path/to/config.json [--check-drafts-first]
 *
 * --check-drafts-first: Check drafts first; if matching content found, publish from draft.
 *                      If not found, fall through to normal create flow.
 *
 * Note config JSON format:
 * {
 *   "title": "笔记标题",
 *   "content": "正文内容（\\n\\n 分段）",
 *   "images": ["/path/to/img1.png"],
 *   "topics": ["话题1", "话题2"]
 * }
 */

const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const DEFAULT_NOTE = {
  title: '在这里填入标题',
  content: '在这里填入正文内容',
  images: [],
  topics: ['话题1', '话题2'],
};

const XHS_URL = 'https://creator.xiaohongshu.com';

function parseArgs() {
  const args = process.argv.slice(2);
  let noteConfig = null, sessionDir = null, checkDraftsFirst = false;
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--note-config' && args[i + 1]) noteConfig = args[++i];
    if (args[i] === '--session-dir' && args[i + 1]) sessionDir = args[++i];
    if (args[i] === '--check-drafts-first') checkDraftsFirst = true;
  }
  return { noteConfig, sessionDir, checkDraftsFirst };
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

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

// ============ BROWSER ============

async function launchBrowser(sessionDir) {
  const lockFile = path.join(sessionDir, 'SingletonLock');
  if (fs.existsSync(lockFile)) fs.unlinkSync(lockFile);
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

// ============ DRAFT CHECK FLOW ============

/**
 * Navigate to note management page, find a matching draft by title, click into it.
 * XHS drafts are at /new/manage (verified 2026-06-25).
 */
async function findAndOpenDraft(page, targetTitle) {
  console.log('\n=== 检查草稿箱 ===');

  // Strategy 1: Try "编辑最新笔记" from home page (fastest path)
  console.log('  Strategy 1: 首页"编辑最新笔记"...');
  await page.goto(`${XHS_URL}/new/home`, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForLoadState('load', { timeout: 30000 }).catch(() => {});
  await sleep(4000);

  const homeClicked = await page.evaluate(() => {
    const all = document.querySelectorAll('*');
    for (const el of all) {
      const text = (el.innerText || el.textContent || '').trim();
      if (text.includes('编辑最新笔记')) {
        const rect = el.getBoundingClientRect();
        if (rect.width > 0 && rect.height > 0) {
          el.scrollIntoView({ block: 'center' });
          el.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, composed: true }));
          el.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, composed: true }));
          el.dispatchEvent(new MouseEvent('click', { bubbles: true, composed: true }));
          el.click();
          return true;
        }
      }
    }
    return false;
  });

  if (homeClicked) {
    console.log('  点击"编辑最新笔记"');
    await sleep(5000);
    const url = page.url();
    if (url.includes('/publish/')) {
      console.log(`  已进入编辑模式: ${url}`);
      return true;
    }
  }

  // Strategy 2: Navigate directly to /new/manage and find our draft
  console.log('  Strategy 2: 导航到笔记管理页...');
  await page.goto(`${XHS_URL}/new/manage`, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForLoadState('load', { timeout: 30000 }).catch(() => {});
  await sleep(5000);

  // Find draft items by title match
  const draftClicked = await page.evaluate((title) => {
    const all = document.querySelectorAll('*');
    // First pass: find elements that contain our title text
    for (const el of all) {
      const text = (el.innerText || el.textContent || '').trim();
      if (text === title || (text.includes(title) && text.length < title.length + 50)) {
        const rect = el.getBoundingClientRect();
        if (rect.width > 50 && rect.height > 20) {
          // Find the closest clickable parent/card
          let target = el;
          for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
            const pr = p.getBoundingClientRect();
            if (pr.width > 100 && pr.height > 50 && pr.x > 100) { target = p; break; }
          }
          target.scrollIntoView({ block: 'center', behavior: 'instant' });
          target.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, composed: true }));
          target.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, composed: true }));
          target.dispatchEvent(new MouseEvent('click', { bubbles: true, composed: true }));
          target.click();
          return `找到草稿: "${text.substring(0, 30)}"`;
        }
      }
    }
    return null;
  }, targetTitle);

  if (draftClicked) {
    console.log(`  ${draftClicked}`);
    await sleep(5000);
    const url = page.url();
    console.log(`  编辑页URL: ${url}`);
    return url.includes('/publish/');
  }

  // Strategy 3: Try to find and click the first draft card
  console.log('  Strategy 3: 找第一个草稿...');
  const firstDraft = await page.evaluate(() => {
    // Look for "草稿" tab/filter first
    const all = document.querySelectorAll('*');
    for (const el of all) {
      const text = (el.innerText || el.textContent || '').trim();
      if (text === '草稿' || text === '草稿箱' || text.includes('草稿')) {
        const rect = el.getBoundingClientRect();
        if (rect.width > 20 && rect.height > 10) {
          el.dispatchEvent(new MouseEvent('click', { bubbles: true, composed: true }));
          el.click();
          return '点击了草稿筛选';
        }
      }
    }
    return null;
  });
  if (firstDraft) {
    console.log(`  ${firstDraft}`);
    await sleep(3000);
  }

  // Now look for note cards to click
  const cardClicked = await page.evaluate((title) => {
    // Look for clickable cards/rows that contain draft content
    const cards = document.querySelectorAll('[class*="card"], [class*="Card"], [class*="item"], [class*="Item"], [class*="row"], [class*="Row"], [class*="note"], [class*="Note"], a, [role="button"], [onclick]');
    for (const card of cards) {
      const text = (card.innerText || card.textContent || '').trim();
      if (text.includes(title) && text.length < title.length + 200) {
        const rect = card.getBoundingClientRect();
        if (rect.width > 100 && rect.height > 30) {
          card.scrollIntoView({ block: 'center' });
          card.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, composed: true }));
          card.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, composed: true }));
          card.dispatchEvent(new MouseEvent('click', { bubbles: true, composed: true }));
          card.click();
          return `已点击卡片: ${text.substring(0, 40)}`;
        }
      }
    }
    return null;
  }, targetTitle);

  if (cardClicked) {
    console.log(`  ${cardClicked}`);
    await sleep(5000);
    const url = page.url();
    console.log(`  编辑页URL: ${url}`);
    return url.includes('/publish/');
  }

  console.log('  草稿箱为空或未找到匹配草稿');
  return false;
}

/**
 * Validate draft content matches expected config.
 * Returns true if content looks correct enough to proceed.
 */
async function validateDraftContent(page, NOTE) {
  console.log('\n=== 校验草稿内容 ===');

  const contentCheck = await page.evaluate((expectedTitle) => {
    const body = document.body.innerText;
    return {
      hasTitle: body.includes(expectedTitle),
      // Take first 200 chars of body as a fragment to match
      bodyLength: body.length,
      sampleText: body.substring(0, 100),
    };
  }, NOTE.title);

  console.log(`  标题匹配: ${contentCheck.hasTitle ? '✅' : '❌'}`);
  console.log(`  页面正文长度: ${contentCheck.bodyLength} chars`);
  console.log(`  内容片段: "${contentCheck.sampleText.substring(0, 50)}..."`);

  const issues = [];
  if (!contentCheck.hasTitle) issues.push('标题未找到');
  if (contentCheck.bodyLength < 100) issues.push('内容过短');

  if (issues.length > 0) {
    console.log(`  ⚠️ 校验发现潜在问题: ${issues.join(', ')}`);
    return false;
  }

  console.log('  ✅ 内容校验通过');
  return true;
}

async function clickPublishFromDraft(page) {
  console.log('\n=== 从草稿发布 ===');

  const beforeBodyLength = await page.evaluate(() => document.body.innerText.length);
  const debugDir = path.resolve(__dirname);

  // Screenshot before publish
  await page.screenshot({ path: path.join(debugDir, 'debug-before-publish.png') });

  // Dismiss popups
  for (let i = 0; i < 5; i++) { await page.keyboard.press('Escape'); await sleep(200); }

  // Scroll to bottom to reveal publish button
  await page.evaluate(() => {
    window.scrollTo(0, document.body.scrollHeight);
    document.querySelectorAll('[class*="scroll"], [class*="container"], [class*="main"]').forEach(el => {
      if (el.scrollHeight > el.clientHeight) el.scrollTop = el.scrollHeight;
    });
  });
  await sleep(1500);

  // Map all "发布" / "发布笔记" elements
  const buttonMap = await page.evaluate(() => {
    const all = document.querySelectorAll('*');
    const buttons = [];
    for (const el of all) {
      const text = (el.innerText || '').trim();
      if ((text === '发布' || text === '发布笔记') && text.length < 20) {
        const rect = el.getBoundingClientRect();
        if (rect.width > 0 && rect.height > 0) {
          buttons.push({
            tag: el.tagName,
            class: (el.className || '').substring(0, 60),
            text: text,
            y: rect.y,
            x: rect.x,
            rect: `${rect.x.toFixed(0)},${rect.y.toFixed(0)} ${rect.width.toFixed(0)}x${rect.height.toFixed(0)}`,
            inSidebar: rect.x < 200,
          });
        }
      }
    }
    return buttons;
  });
  console.log(`  发布元素: ${JSON.stringify(buttonMap)}`);

  // STRATEGY 1: Click the sidebar "发布笔记" button (most visible one)
  const sidebarPublish = buttonMap.filter(b => b.inSidebar && b.text === '发布笔记');
  if (sidebarPublish.length > 0) {
    console.log('  Strategy 1: 点击侧边栏"发布笔记"按钮');
    const target = sidebarPublish[0];
    await page.evaluate((y) => { window.scrollTo(0, Math.max(0, y - 100)); }, target.y);
    await sleep(500);

    // Click by class pattern
    const parts = target.class.split(' ');
    if (parts[0]) {
      await page.locator(`[class*="${parts[0]}"]`).filter({ hasText: '发布笔记' }).first()
        .click({ force: true, timeout: 5000 }).catch(() => {});
      await sleep(3000);
      const r = await checkPublishSuccess(page, beforeBodyLength);
      if (r === true) { console.log('  发布成功！✅'); return true; }
    }
  }

  // STRATEGY 2: JS evaluate - click all "发布笔记" elements
  console.log('  Strategy 2: JS批量点击发布按钮');
  const jsResult = await page.evaluate(() => {
    const all = document.querySelectorAll('*');
    const targets = [];
    for (const el of all) {
      const text = (el.innerText || el.textContent || '').trim();
      if ((text === '发布' || text === '发布笔记') && text.length < 20) {
        const rect = el.getBoundingClientRect();
        if (rect.width > 0 && rect.height > 0) targets.push(el);
      }
    }
    // Sort: sidebar first (x < 200), then main area (x > 200)
    targets.sort((a, b) => {
      const ax = a.getBoundingClientRect().x;
      const bx = b.getBoundingClientRect().x;
      // Sidebar buttons (x < 200) first
      if (ax < 200 && bx >= 200) return -1;
      if (ax >= 200 && bx < 200) return 1;
      return 0;
    });
    for (const el of targets) {
      try {
        el.scrollIntoView({ block: 'center', behavior: 'instant' });
        el.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, composed: true }));
        el.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, composed: true }));
        el.dispatchEvent(new MouseEvent('click', { bubbles: true, composed: true }));
        el.click();
      } catch {}
    }
    return targets.length + '个按钮已点击';
  });
  console.log(`  JS点击结果: ${jsResult}`);
  await sleep(5000);
  let r = await checkPublishSuccess(page, beforeBodyLength);
  if (r === true) { console.log('  发布成功！✅'); return true; }

  // STRATEGY 3: addInitScript to open shadow DOM, then find publish button
  console.log('  Strategy 3: Shadow DOM穿透...');
  await page.addInitScript(() => {
    const orig = Element.prototype.attachShadow;
    Element.prototype.attachShadow = function(options) {
      return orig.call(this, { ...options, mode: 'open' });
    };
  });
  // Reload the page to apply init script
  await page.reload({ waitUntil: 'domcontentloaded' });
  await sleep(4000);
  // Wait for draft editor to load
  await sleep(3000);

  // Now try to find publish button inside shadow roots
  const shadowResult = await page.evaluate(() => {
    // Find xhs-publish-btn hosts
    const hosts = document.querySelectorAll('xhs-publish-btn, [class*="publish"]');
    for (const host of hosts) {
      const sr = host.shadowRoot;
      if (!sr) continue;
      const all = sr.querySelectorAll('*');
      for (const el of all) {
        const text = (el.textContent || '').trim();
        if (text === '发布' || text === '发布笔记') {
          el.click();
          return `Found in shadow: ${text}`;
        }
      }
    }
    return 'No publish button found in shadow DOM';
  });
  console.log(`  Shadow DOM结果: ${shadowResult}`);
  await sleep(5000);
  r = await checkPublishSuccess(page, beforeBodyLength);
  if (r === true) { console.log('  发布成功！✅'); return true; }

  // STRATEGY 4: Tab+Enter兜底
  console.log('  Strategy 4: Tab+Enter兜底...');
  for (let i = 0; i < 30; i++) { await page.keyboard.press('Tab'); await sleep(80); }
  await page.keyboard.press('Enter');
  await sleep(5000);
  r = await checkPublishSuccess(page, beforeBodyLength);
  if (r === true) { console.log('  发布成功！✅'); return true; }

  // STRATEGY 5: 底部区域网格扫描
  console.log('  Strategy 5: 底部区域网格扫描...');
  const vp = page.viewportSize();
  if (vp) {
    for (const y of [vp.height - 30, vp.height - 50, vp.height - 70, vp.height - 90]) {
      for (const x of [400, 550, 300, 600, 700, 200, 800, 500]) {
        await page.mouse.click(x, y);
        await sleep(1500);
        r = await checkPublishSuccess(page, beforeBodyLength);
        if (r === true) { console.log(`  发布成功！(坐标: ${x},${y}) ✅`); return true; }
      }
    }
  }

  console.log('  ❌ 所有发布策略均未确认成功');
  return false;
}

// ============ ORIGINAL CREATE FLOW ============

async function hasImageInput(page) {
  const allInputs = page.locator('input[type="file"]');
  const count = await allInputs.count();
  for (let i = 0; i < count; i++) {
    const accept = await allInputs.nth(i).getAttribute('accept') || '';
    const isVideoOnly = accept.match(/^\.(mp4|mov|flv|mkv|rm|avi|ts)(,|$)/i) && !accept.match(/png|jpg|jpeg|gif|webp|image/i);
    if (!isVideoOnly) return true;
  }
  return false;
}

async function findImageInput(page) {
  const allInputs = page.locator('input[type="file"]');
  const count = await allInputs.count();
  for (let i = 0; i < count; i++) {
    const fi = allInputs.nth(i);
    const accept = await fi.getAttribute('accept') || '';
    const isVideoOnly = accept.match(/^\.(mp4|mov|flv|mkv|rm|avi|ts)(,|$)/i) && !accept.match(/png|jpg|jpeg|gif|webp|image/i);
    if (!isVideoOnly) return fi;
  }
  return null;
}

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

async function uploadImages(page, imagePaths) {
  const validImages = imagePaths.filter(p => fs.existsSync(p));
  if (validImages.length === 0) throw new Error('没有找到有效的图片文件');
  const input = await findImageInput(page);
  if (!input) throw new Error('找不到图片上传入口（可能仍在视频模式）');
  await input.setInputFiles(validImages);
  console.log(`  已上传 ${validImages.length} 张图片，等待处理...`);
  await sleep(12000);
}

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

  // Add topics
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

// ============ MAIN ============

async function main() {
  const args = parseArgs();
  const { NOTE, SESSION_DIR } = loadConfig(args);

  console.log('=== Xiaohongshu Auto-Publisher v2 ===');
  console.log(`标题: ${NOTE.title}`);
  console.log(`图片: ${NOTE.images.length} 张`);
  console.log(`话题: ${NOTE.topics.join(', ')}`);
  console.log(`模式: ${args.checkDraftsFirst ? '先检查草稿 → 从草稿发布' : '新建并发布'}`);
  console.log('');

  const browser = await launchBrowser(SESSION_DIR);
  const page = browser.pages()[0] || await browser.newPage();

  // Step 1: Login
  console.log('[1/5] 登录...');
  if (!(await ensureLogin(page))) {
    await browser.close(); process.exit(1);
  }

  if (args.checkDraftsFirst) {
    // ============ DRAFT-FIRST FLOW ============
    console.log('[2/5] 检查草稿箱...');
    const draftOpened = await findAndOpenDraft(page, NOTE.title);

    if (draftOpened) {
      console.log('[3/5] 校验草稿内容...');
      const isValid = await validateDraftContent(page, NOTE);

      if (isValid) {
        console.log('[4/5] 内容校验通过，准备发布...');
        // Take screenshot to verify visually
        await page.screenshot({ path: path.join(__dirname, 'debug-draft-editor.png') }).catch(() => {});

        console.log('[5/5] 发布...');
        const published = await clickPublishFromDraft(page);
        await sleep(5000);

        try {
          await page.screenshot({ path: path.join(__dirname, 'debug-after-publish.png') });
        } catch {}

        if (published) {
          console.log('✅ 从草稿发布成功！');
        } else {
          console.log('⚠️ 发布未完全确认，请查看 debug-before-publish.png 和 debug-after-publish.png');
        }
      } else {
        console.log('⚠️ 草稿内容校验未通过，请在浏览器中手动处理');
        await page.screenshot({ path: path.join(__dirname, 'debug-draft-validation-fail.png') }).catch(() => {});
      }
    } else {
      console.log('⚠️ 未找到匹配草稿，请手动发布或重新创建');
    }
  } else {
    // ============ ORIGINAL CREATE FLOW ============
    console.log('[2/5] 切换到上传图文...');
    if (!(await switchToImageTab(page))) {
      console.error('无法进入图文上传模式');
      await browser.close(); process.exit(1);
    }

    console.log('[3/5] 上传图片...');
    await uploadImages(page, NOTE.images);

    console.log('[4/5] 填写内容...');
    await fillContent(page, NOTE.title, NOTE.content, NOTE.topics);

    console.log('[5/5] 发布...');
    const published = await clickPublishFromDraft(page);
    await sleep(5000);

    try {
      await page.screenshot({ path: path.join(__dirname, 'debug-after-publish.png') });
    } catch {}

    if (published) {
      console.log('✅ 发布成功！');
    } else {
      console.log('⚠️ 自动发布未完全确认，请查看 debug-before-publish.png 和 debug-after-publish.png');
    }
  }

  await browser.close();
}

main().catch(err => {
  console.error('发布出错:', err);
  // Try to take error screenshot
  try {
    const { chromium } = require('playwright');
  } catch {}
  process.exit(1);
});
