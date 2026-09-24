// 步骤4：把 spec.json 渲染为可视化设计规范 (HTML + MD)
// 用法: node generate_spec.mjs   (读取 spec.json)
// 产出: UI设计规范.html + UI设计规范.md
// 说明: 这是「单一真相源」——所有数值来自 spec.json（由 build_spec 从线上站实测编译），
//       文档由脚本生成，禁止手工改文档数值（防口径漂移）。
//       第 7 章「页面模板」为模板占位，需按目标站点手动补全（参见 references/humance-ui-spec.md 范例）。
import fs from 'fs';
const spec = JSON.parse(fs.readFileSync('spec.json', 'utf8'));
const { meta, semantic, palette, typography, radius, spacing, containers, a11y, components } = spec;

const sw = (hex) => `<span style="display:inline-block;width:14px;height:14px;border-radius:3px;background:${hex};border:1px solid #ccc;vertical-align:middle;margin-right:6px"></span>`;
const semRows = Object.entries(semantic).filter(([, v]) => v.hex).map(([k, v]) =>
  `<tr><td><code>--color-${k}</code></td><td>${sw(v.hex)}${v.hex}</td><td><code>${v.oklch || ''}</code></td></tr>`).join('');
const scaleRow = (p) => `<tr><td><code>${p.name}</code></td>${[50,100,200,300,400,500,600,700,800,900,950].map(s => p.steps[s] ? `<td style="background:${p.steps[s]};color:${s>500?'#fff':'#000'};text-align:center;font-size:11px">${p.steps[s]}</td>` : '<td></td>').join('')}</tr>`;
const scaleHead = [50,100,200,300,400,500,600,700,800,900,950].map(s => `<th>${s}</th>`).join('');
const textRows = (typography.textVars || []).map(t => `<tr><td><code>${t.token}</code></td><td>${t.value}</td></tr>`).join('');
const a11yRows = a11y.map(r => {
  const fail = r.ratio != null && r.ratio < 3;          // 大字以下都不达标
  const aaFail = r.ratio != null && r.ratio < 4.5;       // AA 普通文字不达标（红线区）
  const bg = fail ? 'background:#ffeaea' : aaFail ? 'background:#fff4e0' : '';
  return `<tr style="${bg}"><td>${r.label}</td><td>${r.ratio == null ? '—' : r.ratio.toFixed(2) + ':1'}</td><td>${r.level || '—'}</td></tr>`;
}).join('');
const compList = Object.entries(components || {}).filter(([, v]) => v && v.length).map(([k, v]) => `<li><b>${k}</b> — ${v.length} 条选择器</li>`).join('');

const html = `<!doctype html><html lang="zh"><head><meta charset="utf-8"><title>UI 设计规范 · ${meta.url}</title>
<style>
body{font-family:system-ui,'PingFang SC','Microsoft YaHei',sans-serif;max-width:980px;margin:24px auto;padding:0 20px;color:#18181b;line-height:1.6}
h1{font-size:26px;border-bottom:3px solid #155dfc;padding-bottom:8px}
h2{font-size:20px;margin-top:36px;border-left:4px solid #155dfc;padding-left:10px}
table{border-collapse:collapse;width:100%;margin:12px 0;font-size:13px}
th,td{border:1px solid #e5e7eb;padding:6px 8px;text-align:left}
th{background:#f8f8f8}
.note{background:#fff8e6;border:1px solid #f0d27a;padding:10px 14px;border-radius:8px;margin:12px 0;font-size:13px}
.code{font-family:ui-monospace,monospace;background:#f4f4f5;padding:1px 5px;border-radius:4px}
</style></head><body>
<h1>UI 设计规范</h1>
<div class="note"><b>真相源</b>：${meta.url}（抓取于 ${meta.fetchedAt}）<br>
设计系统：${meta.system}<br>
暗色模式：${meta.hasDark ? 'CSS 变量层已定义 .dark 覆盖' : '⚠️ 暂无 .dark 变量，需改造时新建'}。
本规范由脚本从线上站实测生成，数值请勿手工改写；改版后重跑管线刷新。</div>

<section><h2>1. 色彩体系</h2>
<h3>1.1 语义色（权威 hex，由 oklch 精确换算）</h3>
<table><thead><tr><th>Token</th><th>HEX</th><th>oklch 真值</th></tr></thead><tbody>${semRows}</tbody></table>
<h3>1.2 调色板色阶</h3>
<table><thead><tr><th>色名</th>${scaleHead}</tr></thead><tbody>${palette.map(scaleRow).join('')}</tbody></table>
</section>

<section><h2>2. 字体排版</h2>
<table><tr><th>字体栈</th><td><code>${typography.fontFamily}</code></td></tr>
<tr><th>默认字重</th><td>${typography.defaultWeight || '—'}</td></tr></table>
${textRows ? `<h3>字号阶梯（--text-*）</h3><table><thead><tr><th>Token</th><th>值</th></tr></thead><tbody>${textRows}</tbody></table>` : ''}
</section>

<section><h2>3. 圆角与间距</h2>
<table><thead><tr><th>类别</th><th>Token</th><th>值</th></tr></thead><tbody>
<tr><td>圆角 box</td><td><code>--radius-box</code></td><td>${radius.box}</td></tr>
<tr><td>圆角 field</td><td><code>--radius-field</code></td><td>${radius.field}</td></tr>
<tr><td>圆角 selector</td><td><code>--radius-selector</code></td><td>${radius.selector}</td></tr>
<tr><td>间距基准</td><td><code>--spacing</code></td><td>${spacing.base}</td></tr>
</tbody></table>
</section>

<section><h2>4. 容器宽度</h2>
<table><thead><tr><th>断点</th><th>值</th></tr></thead><tbody>
${Object.entries(containers).map(([k, v]) => `<tr><td><code>${k}</code></td><td>${v}</td></tr>`).join('') || '<tr><td colspan="2">未检测到 --container-*</td></tr>'}
</tbody></table>
</section>

<section><h2>5. 组件清单（从线上 CSS 实测）</h2>
<ul>${compList || '<li>未检测到标准组件类</li>'}</ul>
<p class="note">交互细节（变体/尺寸/状态）读取 <code>components_full.txt</code>。按钮典型规范见下：inline-flex、字重 600、圆角 = --radius-field、过渡 .2s；primary 填主色、ghost/outline 透明；active 下沉、focus-visible 2px 轮廓、disabled 灰显。</p>
</section>

<section><h2>6. 可访问性对比度基线（a11y）</h2>
<table><thead><tr><th>组合</th><th>对比度</th><th>等级</th></tr></thead><tbody>${a11yRows}</tbody></table>
<div class="note"><b>红线</b>：语义色（secondary/accent/success/warning/error）作<b>白底文字</b>时对比度常 < 4.5:1（AA 不达标），禁止直接用于白底状态文字；须加深或使用彩色底 + content 反白。正文用 base-content on base-100（通常 AAA）。</div>
</section>

<section><h2>7. 页面模板库（按站点手动补全）</h2>
<p>本管线只自动产出 token/组件/a11y（第 1–6 章）。<b>页面模板、业务组件、状态机需结合目标站点真实 DOM 手动沉淀</b>。
可参考范例：<code>references/humance-ui-spec.md</code>（慧思 Humance 含 7 型页面模板 + 8 个业务组件 + 状态机与异常分支完整章节）。</p>
<ul>
<li>从 sitemap.xml 枚举真实页面，避免凭空编模板</li>
<li>用 WebFetch / 浏览器读取各页 DOM 结构（注意 WebFetch 会过滤 &lt;link&gt; 的 CSS，须用脚本抓取）</li>
<li>归纳：首页 / 列表网格 / 详情(多子型) / 落地页(含表单) / 账户 / 工具 Hub / 栅格响应式</li>
</ul>
</section>

<section><h2>8. 维护说明</h2>
<div class="note">本规范<b>真相源</b>为目标站点线上 CSS。后续站内改造更新设计 token 时，须先改前端源码，再重跑本管线（fetch→extract→build→generate）刷新文档，避免口径漂移。色彩以 <b>oklch</b> 为权威值，HEX 为设计师便捷换算（同色可视等价）。</div>
</section>
</body></html>`;

const md = `# UI 设计规范（${meta.url}）

> 真相源：${meta.url}（抓取于 ${meta.fetchedAt}）· 设计系统：${meta.system}
> 由脚本从线上站实测生成，改版后重跑管线刷新，勿手工改数值。

## 1. 色彩体系
### 1.1 语义色
| Token | HEX | oklch |
|---|---|---|
${Object.entries(semantic).filter(([, v]) => v.hex).map(([k, v]) => `| \`--color-${k}\` | ${v.hex} | ${v.oklch || ''} |`).join('\n')}

### 1.2 调色板（部分）
${palette.slice(0, 12).map(p => `- **${p.name}**: ${Object.values(p.steps).join(' / ')}`).join('\n')}

## 2. 字体排版
- 字体栈：${typography.fontFamily}
- 默认字重：${typography.defaultWeight || '—'}

## 3. 圆角与间距
- 圆角 box ${radius.box} · field ${radius.field} · selector ${radius.selector}
- 间距基准 ${spacing.base}

## 4. 容器宽度
${Object.entries(containers).map(([k, v]) => `- ${k}: ${v}`).join('\n') || '- 未检测到 --container-*'}

## 5. 组件清单（实测）
${compList.replace(/<[^>]+>/g, '') || '- 未检测到标准组件类'}

## 6. 可访问性对比度基线
| 组合 | 对比度 | 等级 |
|---|---|---|
${a11y.map(r => `| ${r.label} | ${r.ratio == null ? '—' : r.ratio.toFixed(2) + ':1'} | ${r.level || '—'} |`).join('\n')}

> 红线：语义色作白底文字常 < 4.5:1，禁止直接用于白底状态文字。

## 7. 页面模板（按站点手动补全）
参考 references/humance-ui-spec.md 范例（慧思含 7 型页面模板 + 8 业务组件 + 状态机）。

## 8. 维护说明
真相源为线上 CSS；改版后重跑管线刷新，勿手工改数值。
`;

fs.writeFileSync('UI设计规范.html', html);
fs.writeFileSync('UI设计规范.md', md);
console.error('written UI设计规范.html + UI设计规范.md');
