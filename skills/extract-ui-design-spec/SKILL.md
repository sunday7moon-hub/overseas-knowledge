---
name: extract-ui-design-spec
description: 从任意线上站（CSS 运行时）逆向提取一套可用的 UI 设计规范——设计 token（颜色/字体/圆角/间距/容器）+ 组件交互清单 + WCAG 可访问性对比度基线，并生成可视化规范文档（HTML/MD）。当用户说「从线上站扒设计规范」「提取 UI 设计 token」「分析网站设计系统」「做一份设计规范给产品/UI/设计对齐」「扒竞品 UI 规范」时使用。踩过的关键坑位（Tailwind v4 @layer 嵌套、oklch 色彩、WebFetch 过滤 CSS）已固化进脚本。
---

# 从线上站提取 UI 设计规范

## Overview

把任意线上网站的**运行时 CSS** 逆向编译成一份结构化的《UI 设计规范》，输出可直接给产品 / UI / 设计 / 质检四方对齐的文档。核心价值：**设计约束单一真相源**，防「转述丢失 / 口径漂移」。

适用范围：
- 自家站点改版前盘点现状（如慧思 Humance 改造）
- 竞品 / 参考站 UI 规范快速提取
- 给 PRD 补「设计约束」章节、给 UI 原型补组件基线、给 QC 补 a11y 红线

不适用：
- 纯设计稿（Figma）场景——那是设计源，不是运行时 CSS
- 需要像素级 1:1 克隆（本 skill 出 token + 组件规格，不还原具体页面布局；页面模板见 P0 章节手动沉淀）

---

## 管线（4 步，顺序执行）

所有脚本用 managed Node 22 运行（自带 fetch，ESM）：
```
NODE=/Users/yoyo/.workbuddy/binaries/node/versions/22.22.2-2/bin/node
```

```bash
# 0. 建工作目录（产物都落这里，不污染系统）
mkdir -p <outdir> && cd <outdir>

# 1. 抓 token（任意站点 URL）
$NODE <skill>/scripts/fetch_tokens.mjs <站点URL>
#   → design_tokens_raw.json + css_raw.txt

# 2. 抽组件交互（嵌套感知，含 hover/active/focus/disabled）
$NODE <skill>/scripts/extract_components.mjs
#   → components_full.txt + component_inventory.json

# 3. 编译 spec（oklch→hex + 调色板 + WCAG 对比度）
$NODE <skill>/scripts/build_spec.mjs
#   → spec.json

# 4. 生成规范文档（单一真相源渲染）
$NODE <skill>/scripts/generate_spec.mjs
#   → UI设计规范.html + UI设计规范.md
```

> `<skill>` 为本 skill 目录：`/Users/yoyo/.workbuddy/skills/extract-ui-design-spec`

---

## 关键坑位（必读，否则会漏数据）

1. **Tailwind v4 把组件写在 `@layer` 内 + 原生嵌套 `&:hover`**
   朴素正则只抓根级块会漏掉所有交互态。脚本已用**括号深度感知解析**（`extract_components.mjs`）把所有 `@layer` 内的 `.btn`/`.input` 等完整块（含 hover/active/focus/disabled）扒全。

2. **WebFetch 会过滤 `<link rel=stylesheet>` 的 CSS**
   直接 WebFetch 页面拿不到 CSS 文件 URL。必须用脚本（fetch_tokens.mjs）抓原始 HTML 提取 `<link href>` 再下载 CSS 文本。

3. **现代设计系统用 oklch 色彩空间（daisyUI / Tailwind v4）**
   `--color-primary` 真值是 `oklch(54.6% .245 262.881)` 而非 hex。脚本内 `build_spec.mjs` 已内置 oklch→sRGB→hex 精确算法，渲染准确（已校验 primary `#155dfc` 与渲染一致）。

4. **a11y 红线：语义色作白底文字常 < 4.5:1**
   语义色（secondary/accent/success/warning/error）在白底上作文字时对比度常不达标（如 secondary 3.07、accent 3.12）。规范第 6 章自动测算并标红，禁止直接用于白底状态文字。

5. **暗色模式缺口自检**
   脚本检测 CSS 变量层是否定义 `.dark` 覆盖。若没有（如慧思当前），规范会标注「暂无 .dark token，需改造时新建」。

6. **仅适用 SSR / head 内联 CSS 的站点（已实测）**
   fetch_tokens 靠解析 HTML `<head>` 里的 `<link rel=stylesheet>` 拿 CSS。若目标站是**纯 SPA**（CSS 由 JS 运行时注入，`<head>` 无静态 `<link>`），直接跑会抓到 0 个 CSS 文件 → 产物为空。处理法：先用浏览器（agent-browser）渲染该页，把运行时 CSS 另存为 `css_raw.txt` + 手工补 `design_tokens_raw.json`，再从步骤 2 续跑。`demo`/`www`.humancehr.com 均为 Nuxt SSR，head 内已有 `<link>`，实测 1–2s 跑通。

---

## 产出章节与用法

生成文档自动含：
- 第 1 章 色彩体系（语义色权威 hex + 50–950 调色板色阶）
- 第 2 章 字体排版
- 第 3 章 圆角与间距
- 第 4 章 容器宽度
- 第 5 章 组件清单（从线上 CSS 实测的选择器计数）
- 第 6 章 可访问性对比度基线（a11y 红线）

**第 7 章 页面模板库为占位**——本管线只自动产 token/组件/a11y。页面模板、业务组件、状态机需结合目标站点真实 DOM **手动沉淀**（方法见下）。完整范例见 `references/humance-ui-spec.md`（慧思 Humance 含 7 型页面模板 + 8 个业务组件 + 状态机与异常分支 + 1.5 品牌资产与授权说明）。

> **品牌资产 / 授权声明 / 服务归属口径**：这类营销合规内容无法从 CSS 自动提取，须结合产品截图、法务口径、品牌手册手动维护进 `generate_spec.mjs` 的 `brandAssets` 对象，再重跑生成。规范第 1.5 章即为此类内容的固定槽位。

## 手动沉淀页面模板 / 业务组件 / 状态机（P0 三件套）

若目标站点要做原型或 PRD，增补第 7–9 章：
1. 从 `sitemap.xml` 枚举真实页面路径（避免凭空编）
2. 用 WebFetch / 浏览器读各页 DOM 结构，归纳区块骨架
3. 沉淀：页面模板（首页/列表网格/详情多子型/落地页含表单/账户/工具 Hub/栅格响应式）× 业务组件（资源卡/筛选器/数据表/留资表单/Hub 导航）× 状态机（列表/详情/表单/工具生成 + 异常分支 loading/empty/error/404/超时/无权限/断网）

> 未上线的功能（如本地原型工具页）须明确标注 **⚠️ 设计态·非线上抓取**，不冒充已抓取。

---

## 反漂移纪律（沿用全局规则）

- `generate_spec.mjs` 是**单一真相源**：所有数值来自 `spec.json`（由线上实测编译），文档由脚本生成，**禁止手工改文档数值**。
- 站点改版更新 token 后，重跑管线（fetch→extract→build→generate）刷新文档，不要手动维护文档。
- 把本 skill 产物（spec.json / 文档）同步给 PRD / UI / QC 专家时，以 spec.json 为权威，文档为可读副本。
