// 步骤2：从原始 CSS 提取组件交互规则（嵌套感知）
// 用法: node extract_components.mjs [css_raw.txt]   (缺省 css_raw.txt)
// 产出: components_full.txt (各组件完整 CSS 块) + component_inventory.json (组件→选择器清单)
// 关键: 现代 Tailwind v4 把组件写在 @layer 内并用原生嵌套 & :hover，
//       朴素正则只抓根级块会漏掉所有交互态——必须做括号深度感知解析。
import fs from 'fs';
const cssPath = process.argv[2] || 'css_raw.txt';
const css = fs.readFileSync(cssPath, 'utf8');

const blocks = [];
let i = 0, depth = 0;
while (i < css.length) {
  if (css[i] === '{') {
    let s = i - 1;
    while (s >= 0 && css[s] !== '}' && css[s] !== ';') s--;
    const sel = css.slice(s + 1, i).trim();
    let d = 1, j = i + 1;
    while (j < css.length && d > 0) { if (css[j] === '{') d++; else if (css[j] === '}') d--; j++; }
    if (sel && !sel.startsWith('@')) blocks.push({ sel, body: css.slice(i + 1, j - 1), depth });
    depth++;
  } else if (css[i] === '}') depth--;
  i++;
}

function fmt(body) {
  return body.split(';').map((x) => x.trim()).filter(Boolean).map((x) => '  ' + x + ';').join('\n');
}
const isComp = (sel, name) =>
  new RegExp('^\\.' + name + '([^a-zA-Z0-9]|$)').test(sel) ||
  new RegExp('\\.' + name + '([^a-zA-Z0-9]|$)').test(sel);

const targets = ['btn', 'input', 'card', 'badge', 'tab', 'table', 'alert', 'menu', 'dropdown', 'modal', 'toggle', 'checkbox', 'progress', 'select', 'textarea', 'link', 'form', 'label', 'divider', 'stats'];

let out = '';
for (const t of targets) {
  const matched = blocks.filter((b) => isComp(b.sel, t));
  if (!matched.length) { out += `\n## ${t}: 未使用\n`; continue; }
  out += `\n########## ${t} (${matched.length}) ##########\n`;
  for (const b of matched) out += `\n/* ${b.sel} */\n` + fmt(b.body) + '\n';
}
fs.writeFileSync('components_full.txt', out);

const inv = {};
for (const t of targets) inv[t] = blocks.filter((b) => isComp(b.sel, t)).map((b) => b.sel);
fs.writeFileSync('component_inventory.json', JSON.stringify(inv, null, 2));
console.error('total blocks:', blocks.length);
console.error('written components_full.txt + component_inventory.json');
