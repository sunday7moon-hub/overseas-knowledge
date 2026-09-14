const { chromium } = require('playwright');
const path = require('path');

// Usage: node screenshot_poster.js <html-filename> [jpg-filename]
// Example: node screenshot_poster.js bulgaria_2026_policy.html bulgaria_2026_policy.jpg

const args = process.argv.slice(2);
const htmlFile = args[0] || 'poster.html';
const jpgFile = args[1] || htmlFile.replace(/\.html$/i, '.jpg');
const dir = process.cwd();

(async () => {
  const browser = await chromium.launch({ headless: true });

  // deviceScaleFactor=2 enables HiDPI rendering — no CSS transform needed
  const page = await browser.newPage({ viewport: { width: 850, height: 4000 }, deviceScaleFactor: 2 });
  const filePath = path.join(dir, htmlFile);
  const outputPath = path.join(dir, jpgFile);

  await page.goto('file://' + filePath, { waitUntil: 'networkidle' });
  await page.waitForTimeout(1500);

  // Get poster element — do NOT apply CSS transform, use deviceScaleFactor instead
  const poster = await page.$('.poster');
  if (!poster) {
    console.error('ERROR: .poster element not found in', htmlFile);
    await browser.close();
    process.exit(1);
  }

  const box = await poster.boundingBox();
  if (!box) {
    console.error('ERROR: boundingBox returned null');
    await browser.close();
    process.exit(1);
  }
  console.log('Poster CSS box:', JSON.stringify(box));

  // fullPage ensures the entire poster fits even if it's taller than viewport
  // clip values are in CSS pixels; deviceScaleFactor=2 gives 2x pixel density
  await page.screenshot({
    path: outputPath,
    type: 'jpeg',
    quality: 98,
    fullPage: true,
    clip: { x: box.x, y: box.y, width: box.width, height: box.height }
  });

  const fs = require('fs');
  const stat = fs.statSync(outputPath);
  console.log('Output:', jpgFile, `(${(stat.size / 1024).toFixed(1)} KB)`);

  await page.close();
  await browser.close();
})().catch(err => { console.error(err); process.exit(1); });
