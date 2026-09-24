/**
 * Xiaohongshu Auto-Publisher v3 — Fixed publish button + draft-first flow
 *
 * Usage:
 *   node publish_xhs_v3.js --note-config /path/to/config.json [--check-drafts-first]
 *
 * --check-drafts-first: Check drafts first; if matching content found, publish from draft.
 *                       If not found, create new note and publish.
 */

const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const DEFAULT_NOTE = { title: '', content: '', images: [], topics: [] };
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

// ============ BROWSER SETUP ============

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
    console.log('  需要登录 - 请在浏览器中扫码（5分钟超时）');
    try {
      await page.waitForURL(u => {
        const s = u.toString();
        return s.includes('creator.xiaohongshu.com') && !s.includes('login') && !s.includes('passport');
      }, { timeout: 300000 });
      await sleep(3000);
      console.log('  登录成功！');
    } catch {
      console.error('  登录超时');
      return false;
    }
  } else {
    console.log('  已登录（复用上次session）');
  }
  return true;
}

async function checkPublishSuccess(page, beforeBodyLength) {
  const url = page.url();
  if (!url.includes('/publish') || url.includes('success')) return true;
  if (url.includes('target=video') || url.includes('from=menu')) return 'TAB_SWITCHED';
  try {
    if (await page.locator('text=发布成功').first().isVisible({ timeout: 2000 }).catch(() => false)) return true;
  } catch {}
  try {
    if (await page.locator('text=已发布').first().isVisible({ timeout: 1000 }).catch(() => false)) return true;
  } catch {}
  try {
    if (await page.locator('text=笔记已发布').first().isVisible({ timeout: 1000 }).catch(() => false)) return true;
  } catch {}
  if (beforeBodyLength) {
    try {
      if (await page.evaluate(() => document.body.innerText.length) < beforeBodyLength * 0.3) return true;
    } catch {}
  }
  return false;
}

// ============ DRAFT-FIRST FLOW ============

/**
 * Navigate to /new/note-manager, find draft by title, click to edit.
 */
async function findAndOpenDraft(page, targetTitle) {
  console.log('\n=== 检查草稿箱 ===');

  // Try click "编辑最新笔记" from home page first
  await page.goto(`${XHS_URL}/new/home`, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForLoadState('load', { timeout: 30000 }).catch(() => {});
  await sleep(5000);

  const editLatest = await page.evaluate(() => {
    const all = document.querySelectorAll('*');
    for (const el of all) {
      const t = (el.innerText || el.textContent || '').trim();
      if (t.includes('编辑最新笔记')) {
        el.click();
        ['mousedown', 'mouseup', 'click'].forEach(e => el.dispatchEvent(new MouseEvent(e, { bubbles: true, composed: true })));
        return true;
      }
    }
    return false;
  });

  if (editLatest) {
    await sleep(5000);
    if (page.url().includes('/publish/')) {
      console.log('  ✅ 已通过"编辑最新笔记"进入编辑');
      return true;
    }
  }

  // Go to note manager
  await page.goto(`${XHS_URL}/new/note-manager`, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForLoadState('load', { timeout: 30000 }).catch(() => {});
  await sleep(8000);

  // Try clicking "仅自己可见" tab first (drafts are here)
  const draftTabClicked = await page.evaluate(() => {
    const all = document.querySelectorAll('*');
    for (const el of all) {
      const t = (el.innerText || el.textContent || '').trim();
      if (t === '仅自己可见') {
        el.click();
        return true;
      }
    }
    return false;
  });
  if (draftTabClicked) {
    console.log('  切换到"仅自己可见"');
    await sleep(4000);
  } else {
    // Also try "未通过" tab
    const otherTab = await page.evaluate(() => {
      const all = document.querySelectorAll('*');
      for (const el of all) {
        const t = (el.innerText || el.textContent || '').trim();
        if (t === '未通过') { el.click(); return '未通过'; }
        if (t === '草稿') { el.click(); return '草稿'; }
        if (t === '审核中') { el.click(); return '审核中'; }
      }
      return null;
    });
    if (otherTab) console.log(`  切换到"${otherTab}"`);
    await sleep(4000);
  }

  // Find note card by title
  const found = await page.evaluate((title) => {
    const all = document.querySelectorAll('*');
    for (const el of all) {
      const t = (el.innerText || el.textContent || '').trim();
      // Exact match or partial match (XHS may truncate title)
      if (t === title || title.startsWith(t) || t.startsWith(title) || (t.includes(title) && t.length < title.length + 30)) {
        const rect = el.getBoundingClientRect();
        if (rect.width > 50 && rect.height > 20 && rect.x > 100) {
          // Find the card-level parent
          let card = el;
          for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
            const pr = p.getBoundingClientRect();
            if (pr.width > 100 && pr.height > 50) { card = p; break; }
          }
          card.scrollIntoView({ block: 'center' });
          card.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, composed: true }));
          card.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, composed: true }));
          card.dispatchEvent(new MouseEvent('click', { bubbles: true, composed: true }));
          card.click();
          return text.substring(0, 40);
        }
      }
    }
    return null;
  }, targetTitle);

  if (found) {
    console.log(`  ✅ 找到草稿: ${found}`);
    await sleep(5000);
    return true;
  }

  console.log('  ❌ 未找到匹配草稿');
  return false;
}

async function validateDraftContent(page, NOTE) {
  console.log('\n=== 校验草稿内容 ===');
  const check = await page.evaluate((expectedTitle) => {
    const body = document.body.innerText;
    return { hasTitle: body.includes(expectedTitle), bodyLen: body.length, sample: body.substring(0, 80) };
  }, NOTE.title);
  console.log(`  标题匹配: ${check.hasTitle ? '✅' : '❌'} | 正文长度: ${check.bodyLen}`);
  if (!check.hasTitle) return false;
  console.log('  ✅ 校验通过');
  return true;
}

// ============ SAVE DRAFT ============

async function saveAsDraft(page) {
  console.log('  保存草稿...');
  // macOS: Cmd+S, Windows/Linux: Ctrl+S
  await page.keyboard.press('Meta+S');
  await sleep(3000);
  // Try Enter to confirm save dialog if any
  await page.keyboard.press('Enter');
  await sleep(2000);
}

// ============ PUBLISH BUTTON (FIXED) ============

async function clickPublishButton(page) {
  console.log('\n=== 点击发布按钮 ===');
  const debugDir = path.resolve(__dirname);
  const beforeBodyLength = await page.evaluate(() => document.body.innerText.length);

  // Screenshot before
  await page.screenshot({ path: path.join(debugDir, 'debug-before-publish.png') });

  // Dismiss any popups
  for (let i = 0; i < 8; i++) { await page.keyboard.press('Escape'); await sleep(200); }

  // Scroll to bottom — scroll all scrollable containers
  await page.evaluate(() => {
    window.scrollTo(0, 99999);
    document.querySelectorAll('*').forEach(el => {
      try { if (el.scrollHeight > el.clientHeight) el.scrollTop = el.scrollHeight; } catch {}
    });
  });
  await sleep(2000);

  // Map all "发布" elements on the page, noting their position
  const allButtons = await page.evaluate(() => {
    const all = document.querySelectorAll('*');
    const result = [];
    for (const el of all) {
      const t = (el.innerText || el.textContent || '').trim();
      const matchPublish = t === '发布' || t === '发布笔记';
      const matchPublishLong = t === '发布笔记' || (t.includes('发布') && !t.includes('发布成功') && !t.includes('已发布') && t.length < 20);
      if (matchPublish || matchPublishLong) {
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
  console.log(`  所有发布按钮(${allButtons.length}):`);
  allButtons.forEach(b => console.log(`    ${b.inSidebar ? '[侧栏]' : '[主区]'} ${b.tag}.${b.cls} "${b.text}" at (${b.x},${b.y}) ${b.w}x${b.h}${b.isVisible ? ' [可视]' : ''}`));

  // Main area buttons only, sorted by Y (bottom-first), prefer visible ones
  const mainButtons = allButtons.filter(b => !b.inSidebar).sort((a, b) => b.y - a.y);
  const visButtons = mainButtons.filter(b => b.isVisible);

  // Strategy 1: Click visible bottom-most main area button (prefer "发布" over "发布笔记")
  if (visButtons.length > 0) {
    const target = visButtons[0];
    console.log(`  策略1: 点击"${target.text}" at (${target.x},${target.y})`);
    await page.evaluate((y) => window.scrollTo(0, Math.max(0, y - 200)), target.y);
    await sleep(1000);
    try {
      // Click by class
      const cls = target.cls.split(' ')[0];
      if (cls) {
        await page.locator(`[class*="${cls}"]`).filter({ hasText: target.text }).last()
          .click({ force: true, timeout: 5000 }).catch(() => {});
        await sleep(3000);
        let r = await checkPublishSuccess(page, beforeBodyLength);
        if (r === true) { console.log('  ✅ 发布成功！'); return true; }
      }
      // Coordinate click
      await page.mouse.click(target.x + target.w / 2, target.y + target.h / 2);
      await sleep(3000);
      let r = await checkPublishSuccess(page, beforeBodyLength);
      if (r === true) { console.log('  ✅ 发布成功！(坐标)'); return true; }
    } catch {}
  }

  // Strategy 2: JS click ALL main area buttons (bottom-first)
  if (mainButtons.length > 0) {
    console.log(`  策略2: JS点击${mainButtons.length}个主区按钮`);
    const clicked = await page.evaluate(() => {
      const all = document.querySelectorAll('*');
      const targets = [];
      for (const el of all) {
        const t = (el.innerText || el.textContent || '').trim();
        const r = el.getBoundingClientRect();
        if ((t === '发布' || t === '发布笔记') && r.width > 0 && r.height > 0 && r.x >= 200) {
          targets.push(el);
        }
      }
      targets.sort((a, b) => b.getBoundingClientRect().y - a.getBoundingClientRect().y);
      for (const el of targets) {
        try {
          el.scrollIntoView({ block: 'center' });
          el.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, composed: true }));
          el.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, composed: true }));
          el.dispatchEvent(new MouseEvent('click', { bubbles: true, composed: true }));
          el.click();
        } catch {}
      }
      return targets.length + '个已点';
    });
    console.log(`  JS: ${clicked}`);
    await sleep(5000);
    let r = await checkPublishSuccess(page, beforeBodyLength);
    if (r === true) { console.log('  ✅ 发布成功！'); return true; }
  }

  // Strategy 3: Find parent of "发布" text that has onclick or button-like behavior
  console.log('  策略3: 父元素查找...');
  const parentClick = await page.evaluate(() => {
    const all = document.querySelectorAll('*');
    for (const el of all) {
      const t = (el.innerText || el.textContent || '').trim();
      if (t === '发布') {
        let parent = el.parentElement;
        while (parent && parent !== document.body) {
          const onclick = parent.getAttribute('onclick');
          const role = parent.getAttribute('role');
          const tag = parent.tagName;
          const cls = (parent.className || '');
          if (tag === 'BUTTON' || tag === 'A' || onclick || role === 'button' || cls.includes('btn') || cls.includes('publish')) {
            const r = parent.getBoundingClientRect();
            if (r.width > 0 && r.height > 0 && r.x >= 200) {
              parent.scrollIntoView({ block: 'center' });
              parent.dispatchEvent(new MouseEvent('click', { bubbles: true, composed: true }));
              parent.click();
              return `${tag}.${cls.substring(0, 30)} at y=${r.y.toFixed(0)}`;
            }
          }
          parent = parent.parentElement;
        }
      }
    }
    return null;
  });
  if (parentClick) {
    console.log(`  父元素: ${parentClick}`);
    await sleep(5000);
    r = await checkPublishSuccess(page, beforeBodyLength);
    if (r === true) { console.log('  ✅ 发布成功！'); return true; }
  }

  // Strategy 4: Tab+Enter (30 tabs)
  console.log('  策略4: Tab+Enter兜底...');
  for (let i = 0; i < 40; i++) { await page.keyboard.press('Tab'); await sleep(80); }
  await page.keyboard.press('Enter');
  await sleep(5000);
  r = await checkPublishSuccess(page, beforeBodyLength);
  if (r === true) { console.log('  ✅ 发布成功！'); return true; }

  // Strategy 5: Bottom area coordinate grid
  console.log('  策略5: 底部坐标网格扫描...');
  const vp = page.viewportSize();
  if (vp) {
    for (const y of [vp.height - 40, vp.height - 60, vp.height - 80, vp.height - 100, vp.height - 120]) {
      for (const x of [vp.width - 200, vp.width - 150, vp.width - 100, vp.width / 2, vp.width / 2 + 200]) {
        await page.mouse.click(x, y);
        await sleep(1500);
        r = await checkPublishSuccess(page, beforeBodyLength);
        if (r === true) { console.log(`  ✅ 发布成功！(${x},${y})`); return true; }
      }
    }
  }

  console.log('  ❌ 所有发布策略均失败');
  return false;
}

// ============ IMAGE TAB / UPLOAD / CONTENT ============

async function hasImageInput(page) {
  const allInputs = page.locator('input[type="file"]');
  for (let i = 0; i < await allInputs.count(); i++) {
    const accept = await allInputs.nth(i).getAttribute('accept') || '';
    if (accept.match(/^\.(mp4|mov|flv|mkv|rm|avi|ts)(,|$)/i) && !accept.match(/png|jpg|jpeg|gif|webp|image/i)) continue;
    return true;
  }
  return false;
}

async function findImageInput(page) {
  const allInputs = page.locator('input[type="file"]');
  for (let i = 0; i < await allInputs.count(); i++) {
    const fi = allInputs.nth(i);
    const accept = await fi.getAttribute('accept') || '';
    if (accept.match(/^\.(mp4|mov|flv|mkv|rm|avi|ts)(,|$)/i) && !accept.match(/png|jpg|jpeg|gif|webp|image/i)) continue;
    return fi;
  }
  return null;
}

async function switchToImageTab(page, maxRetries = 4) {
  await page.goto(`${XHS_URL}/publish/publish`, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForLoadState('load', { timeout: 30000 }).catch(() => {});
  await sleep(3000);

  for (let attempt = 0; attempt < maxRetries; attempt++) {
    await page.evaluate(() => {
      const all = document.querySelectorAll('*');
      for (const el of all) {
        const t = (el.textContent || '').trim();
        if (t === '上传图文') {
          el.click();
          ['mousedown', 'mouseup', 'click'].forEach(e => el.dispatchEvent(new MouseEvent(e, { bubbles: true })));
          return;
        }
      }
    });
    await sleep(3000);
    if (await hasImageInput(page)) { console.log(`  Tab切换成功 (attempt ${attempt + 1})`); return true; }
  }
  return false;
}

async function uploadImages(page, imagePaths) {
  const valid = imagePaths.filter(p => fs.existsSync(p));
  if (valid.length === 0) throw new Error('没有有效图片');
  const input = await findImageInput(page);
  if (!input) throw new Error('找不到图片上传入口');
  await input.setInputFiles(valid);
  console.log(`  已上传 ${valid.length} 张，等待处理...`);
  await sleep(12000);
}

async function fillContent(page, title, content, topics) {
  const editors = page.locator('[contenteditable="true"]');
  const edCount = await editors.count();
  console.log(`  contenteditable: ${edCount}`);

  if (edCount >= 2) {
    await editors.nth(0).click({ force: true }); await sleep(200);
    await page.keyboard.press('Meta+A'); await sleep(80);
    await page.keyboard.type(title, { delay: 8 });
    await editors.nth(1).click({ force: true }); await sleep(300);
    const ps = content.split('\n\n');
    for (let i = 0; i < ps.length; i++) {
      await page.keyboard.type(ps[i], { delay: 5 });
      if (i < ps.length - 1) { await page.keyboard.press('Enter'); await page.keyboard.press('Enter'); }
    }
  } else if (edCount === 1) {
    await editors.nth(0).click({ force: true }); await sleep(300);
    await page.keyboard.type(title, { delay: 8 });
    await page.keyboard.press('Enter'); await page.keyboard.press('Enter'); await sleep(200);
    const ps = content.split('\n\n');
    for (let i = 0; i < ps.length; i++) {
      if (!ps[i]) { await page.keyboard.press('Enter'); await page.keyboard.press('Enter'); continue; }
      await page.keyboard.type(ps[i], { delay: 5 });
      if (i < ps.length - 1) { await page.keyboard.press('Enter'); await page.keyboard.press('Enter'); }
    }
  } else {
    const tas = page.locator('textarea');
    const taCount = await tas.count();
    for (let i = 0; i < taCount; i++) {
      const ph = await tas.nth(i).getAttribute('placeholder') || '';
      if (ph.includes('标题') || (i === 0 && taCount > 1)) { await tas.nth(i).click(); await tas.nth(i).fill(title); break; }
    }
  }

  // Topics
  await page.keyboard.press('Enter'); await page.keyboard.press('Enter');
  for (const topic of topics) {
    await page.keyboard.type(`#${topic}`, { delay: 12 });
    await sleep(400); await page.keyboard.press('Enter'); await sleep(400); await page.keyboard.press('Escape'); await sleep(200);
  }
  console.log('  内容填写完成');
}

// ============ MAIN ============

async function main() {
  const args = parseArgs();
  const { NOTE, SESSION_DIR } = loadConfig(args);

  console.log('=== Xiaohongshu Auto-Publisher v3 ===');
  console.log(`标题: ${NOTE.title}`);
  console.log(`图片: ${NOTE.images.length} 张`);
  console.log(`话题: ${NOTE.topics.join(', ')}`);

  const browser = await launchBrowser(SESSION_DIR);
  const page = browser.pages()[0] || await browser.newPage();

  // Step 1: Login
  console.log('\n[1/5] 登录...');
  if (!(await ensureLogin(page))) { await browser.close(); process.exit(1); }

  if (args.checkDraftsFirst) {
    // ===== DRAFT-FIRST: find → validate → publish =====
    console.log('[2/5] 检查草稿箱...');
    const draftOpened = await findAndOpenDraft(page, NOTE.title);

    if (draftOpened) {
      console.log('[3/5] 校验草稿内容...');
      if (await validateDraftContent(page, NOTE)) {
        console.log('[4/5] 内容校验通过');
        await page.screenshot({ path: path.join(__dirname, 'debug-draft-editor.png') }).catch(() => {});
        console.log('[5/5] 发布...');
        const ok = await clickPublishButton(page);
        await sleep(5000);
        await page.screenshot({ path: path.join(__dirname, 'debug-after-publish.png') }).catch(() => {});
        console.log(ok ? '✅ 从草稿发布成功！' : '⚠️ 发布未确认，请查看截图');
      } else {
        console.log('⚠️ 草稿内容不匹配，请手动处理');
      }
    } else {
      console.log('⚠️ 未找到草稿，改用新建模式');
    }
  }

  if (!args.checkDraftsFirst || page.url().includes('/publish/publish') || page.url().includes('/new/home')) {
    // Re-check if we're already on the publish page
    if (!page.url().includes('/publish/')) {
      // ===== CREATE FLOW: tab → upload → fill → save draft → publish =====
      console.log('\n[2/5] 切换到上传图文...');
      if (!(await switchToImageTab(page))) { console.error('无法进入图文模式'); await browser.close(); process.exit(1); }

      console.log('[3/5] 上传图片...');
      await uploadImages(page, NOTE.images);

      console.log('[4/5] 填写内容...');
      await fillContent(page, NOTE.title, NOTE.content, NOTE.topics);

      // Save draft first so content is preserved even if publish fails
      await saveAsDraft(page);
    }

    console.log('[5/5] 发布...');
    const ok = await clickPublishButton(page);
    await sleep(5000);
    await page.screenshot({ path: path.join(__dirname, 'debug-after-publish.png') }).catch(() => {});
    console.log(ok ? '✅ 发布成功！' : '⚠️ 发布未确认，请查看截图');
  }

  await browser.close();
}

main().catch(err => { console.error('出错:', err); process.exit(1); });
