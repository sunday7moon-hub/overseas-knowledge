// 步骤3：把抓取数据编译成结构化 spec.json（含 oklch→hex、调色板、WCAG 对比度）
// 用法: node build_spec.mjs   (读取 design_tokens_raw.json + component_inventory.json)
// 产出: spec.json
import fs from 'fs';

const raw = JSON.parse(fs.readFileSync('design_tokens_raw.json', 'utf8'));
const all = {};
for (const [url, vars] of Object.entries(raw.cssFileAllVars || {})) {
  for (const [k, v] of Object.entries(vars)) if (!(k in all)) all[k] = v;
}
for (const [k, v] of Object.entries(raw.inlineVars || {})) if (!(k in all)) all[k] = v;

// ---- oklch → hex + WCAG ----
function parseOklch(str) {
  const m = String(str).match(/oklch\(\s*([\d.]+)%\s+([\d.]+)\s+([\d.]+)/);
  return m ? { L: parseFloat(m[1]) / 100, C: parseFloat(m[2]), H: parseFloat(m[3]) } : null;
}
function oklchToRgb({ L, C, H }) {
  const hr = H * Math.PI / 180, a = C * Math.cos(hr), b = C * Math.sin(hr);
  const l_ = L + 0.3963377774 * a + 0.2158037573 * b;
  const m_ = L - 0.1055613458 * a - 0.0638541728 * b;
  const s_ = L - 0.0894841775 * a - 1.2914855480 * b;
  const l = l_ ** 3, m = m_ ** 3, ss = s_ ** 3;
  return [4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * ss,
    -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * ss,
    -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * ss];
}
const gamma = (x) => (x <= 0.0031308 ? 12.92 * x : 1.055 * Math.pow(x, 1 / 2.4) - 0.055);
const clamp = (x) => Math.max(0, Math.min(1, x));
function toHex(p) {
  const [r, g, b] = oklchToRgb(p).map((v) => clamp(gamma(v)));
  const h = (x) => Math.round(x * 255).toString(16).padStart(2, '0');
  return '#' + h(r) + h(g) + h(b);
}
function hexOf(token) {
  const v = all[token];
  if (!v) return '';
  const p = parseOklch(v);
  return p ? toHex(p) : v;
}
function rgbOf(token) {
  const p = parseOklch(all[token]);
  return p ? oklchToRgb(p).map(clamp) : null;
}
function lum(rgb) {
  const f = (c) => (c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4));
  return 0.2126 * f(rgb[0]) + 0.7152 * f(rgb[1]) + 0.0722 * f(rgb[2]);
}
function ratio(a, b) {
  const L1 = lum(a), L2 = lum(b), hi = Math.max(L1, L2), lo = Math.min(L1, L2);
  return (hi + 0.05) / (lo + 0.05);
}

// ---- 语义色 ----
const semKeys = ['primary', 'primary-content', 'secondary', 'secondary-content', 'accent', 'accent-content',
  'neutral', 'neutral-content', 'success', 'success-content', 'warning', 'warning-content',
  'error', 'error-content', 'info', 'info-content', 'base-100', 'base-200', 'base-300', 'base-content'];
const semantic = {};
for (const k of semKeys) { const t = '--color-' + k; semantic[k] = { token: t, oklch: all[t] || '', hex: hexOf(t) }; }

// ---- 调色板色阶 ----
const STEPS = [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950];
const scaleNames = new Set();
const sr = /^--color-([a-z0-9]+)-(\d{2,3})$/;
for (const k of Object.keys(all)) { const m = k.match(sr); if (m) scaleNames.add(m[1]); }
const palette = [];
for (const name of [...scaleNames].sort()) {
  const steps = {};
  for (const s of STEPS) { const t = `--color-${name}-${s}`; if (all[t]) steps[s] = hexOf(t); }
  if (Object.keys(steps).length) palette.push({ name, steps });
}

// ---- 字体 / 圆角 / 间距 / 容器 ----
const typography = {
  fontFamily: all['--default-font-family'] || all['--font-sans'] || 'system-ui, sans-serif',
  defaultWeight: all['--default-font-weight'] || '',
  textVars: Object.keys(all).filter((k) => /^--text-/.test(k)).sort().map((k) => ({ token: k, value: all[k] })),
};
const radius = { box: all['--radius-box'] || '', field: all['--radius-field'] || '', selector: all['--radius-selector'] || '' };
const spacing = {
  base: all['--spacing'] || '',
  scale: Object.keys(all).filter((k) => /^--spacing-/.test(k)).map((k) => ({ token: k, value: all[k] })),
};
const containers = {};
for (const k of Object.keys(all)) if (/^--container-/.test(k)) containers[k.replace('--container-', '')] = all[k];

// ---- a11y 基线（WCAG 对比度）----
const pairs = [
  ['primary 底/字', 'primary', 'primary-content'],
  ['primary 字 on base-100 白', 'primary', 'base-100'],
  ['secondary 底/字', 'secondary', 'secondary-content'],
  ['secondary 字 on base-100 白', 'secondary', 'base-100'],
  ['accent 底/字', 'accent', 'accent-content'],
  ['accent 字 on base-100 白', 'accent', 'base-100'],
  ['success 底/字', 'success', 'success-content'],
  ['success 字 on base-100 白', 'success', 'base-100'],
  ['warning 底/字', 'warning', 'warning-content'],
  ['error 底/字', 'error', 'error-content'],
  ['error 字 on base-100 白', 'error', 'base-100'],
  ['base-content 正文 on base-100', 'base-content', 'base-100'],
  ['base-content 正文 on base-200', 'base-content', 'base-200'],
  ['base-content 正文 on base-300', 'base-content', 'base-300'],
];
const a11y = pairs.map(([label, a, b]) => {
  const ra = rgbOf('--color-' + a), rb = rgbOf('--color-' + b);
  const r = ra && rb ? ratio(ra, rb) : null;
  return { label, a, b, ratio: r, level: r == null ? null : r >= 7 ? 'AAA' : r >= 4.5 ? 'AA' : r >= 3 ? 'AA-大字' : 'FAIL' };
});

let inventory = {};
try { inventory = JSON.parse(fs.readFileSync('component_inventory.json', 'utf8')); } catch {}

const spec = {
  meta: {
    url: raw.base,
    fetchedAt: new Date().toISOString(),
    system: all['--radius-box'] ? 'Tailwind CSS v4 + daisyUI (oklch 色彩空间)' : '未知（未识别 daisyUI token）',
    cssFiles: raw.cssFiles,
    hasDark: Object.values(raw.cssFileVars || {}).some((f) => Object.keys(f).some((s) => s.includes('.dark'))),
  },
  allVars: all,
  semantic, palette, typography, radius, spacing, containers, a11y, components: inventory,
};
fs.writeFileSync('spec.json', JSON.stringify(spec, null, 2));
console.error('written spec.json | palette scales:', palette.length, '| a11y rows:', a11y.length, '| hasDark:', spec.meta.hasDark);
