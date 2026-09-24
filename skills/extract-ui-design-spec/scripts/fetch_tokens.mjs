// 步骤1：从任意线上站抓取设计 token
// 用法: node fetch_tokens.mjs <站点URL>   (缺省 https://www.humancehr.com)
// 产出: design_tokens_raw.json (CSS 变量) + css_raw.txt (拼接后的原始 CSS，供组件解析)
import fs from 'fs';
import path from 'path';

const BASE = process.argv[2] || 'https://www.humancehr.com';
const OUT = path.join(process.cwd(), 'design_tokens_raw.json');
const CSS_OUT = path.join(process.cwd(), 'css_raw.txt');

function absUrl(u, base) {
  try { return new URL(u, base).href; } catch { return null; }
}
async function fetchText(url) {
  const r = await fetch(url, { headers: { 'User-Agent': 'Mozilla/5.0' }, redirect: 'follow' });
  if (!r.ok) throw new Error(`${r.status} ${url}`);
  return await r.text();
}
// 提取一个 CSS 文本里所有 :root / html / @layer base / .dark 选择器内定义的 --变量，以及全局所有 --变量
function extractVars(css) {
  const vars = {};
  const blocks = css.match(/[^{}]*\{([^{}]*)\}/g) || [];
  for (const block of blocks) {
    const brace = block.indexOf('{');
    const sel = block.slice(0, brace).trim();
    const body = block.slice(brace + 1, block.lastIndexOf('}'));
    if (/:root|html\b|@layer\s+base|::?backdrop/.test(sel) || /\.dark/.test(sel)) {
      const re = /(--[\w-]+)\s*:\s*([^;{}]+);/g;
      let m;
      while ((m = re.exec(body))) {
        const k = m[1].trim();
        const v = m[2].trim();
        (vars[k] = vars[k] || {})[sel] = v;
      }
    }
  }
  const all = {};
  const re2 = /(--[\w-]+)\s*:\s*([^;{}]+);/g;
  let m2;
  while ((m2 = re2.exec(css))) all[m2[1].trim()] = m2[2].trim();
  return { scoped: vars, all };
}

(async () => {
  const html = await fetchText(BASE);
  const cssUrls = new Set();
  const linkRe = /<link[^>]+rel=["']stylesheet["'][^>]*href=["']([^"']+)["']/gi;
  let m;
  while ((m = linkRe.exec(html))) { const u = absUrl(m[1], BASE); if (u) cssUrls.add(u); }
  const preRe = /<link[^>]+as=["']style["'][^>]*href=["']([^"']+)["']/gi;
  while ((m = preRe.exec(html))) { const u = absUrl(m[1], BASE); if (u) cssUrls.add(u); }
  let inlineVars = {};
  const styleRe = /<style[^>]*>([\s\S]*?)<\/style>/gi;
  let sm;
  while ((sm = styleRe.exec(html))) { const e = extractVars(sm[1]); inlineVars = { ...inlineVars, ...e.all }; }

  const result = { base: BASE, cssFiles: [...cssUrls], inlineVars, cssFileVars: {}, cssFileAllVars: {} };
  let allCss = '';
  for (const url of cssUrls) {
    try {
      const css = await fetchText(url);
      allCss += `\n/* ${url} */\n` + css;
      const e = extractVars(css);
      result.cssFileVars[url] = e.scoped;
      result.cssFileAllVars[url] = e.all;
      console.error('OK', url, 'vars=', Object.keys(e.all).length);
    } catch (err) { console.error('FAIL', url, err.message); }
  }
  fs.writeFileSync(OUT, JSON.stringify(result, null, 2));
  fs.writeFileSync(CSS_OUT, allCss);
  console.error('written', OUT, '+', CSS_OUT, '| css files:', cssUrls.size);
})().catch((e) => { console.error('FATAL', e); process.exit(1); });
