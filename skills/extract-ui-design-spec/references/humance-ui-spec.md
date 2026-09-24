# Humance 慧思 · 产品 UI 设计规范

> 数据源：https://www.humancehr.com/assets/_h2_.DjcIoyLT.css
> 设计系统：Tailwind CSS v4.1.13 + daisyUI (oklch color space)
> 抓取时间：2026-09-22T02:15:37.683Z
> 暗色模式：未定义 .dark 变量覆盖（站点暂无独立暗色主题 token）

## 1. 色彩系统

### 1.1 品牌色（Brand）
| 名称 | Token | oklch | HEX | 用途 |
|---|---|---|---|---|
| 主色Primary | `--color-primary` | oklch(54.6% .245 262.881) | #155dfc | 背景/主视觉 |
| 主色Primary | `--color-primary-content` | oklch(93% .034 272.788) | #e0e7ff | 背景/主视觉 |
| 辅助色Secondary | `--color-secondary` | oklch(65% .241 354.308) | #f43098 | 背景/主视觉 |
| 辅助色Secondary | `--color-secondary-content` | oklch(94% .028 342.258) | #f9e4f0 | 背景/主视觉 |
| 强调色Accent | `--color-accent` | oklch(77% .152 181.912) | #00d3bb | 背景/主视觉 |
| 强调色Accent | `--color-accent-content` | oklch(38% .063 188.416) | #084d49 | 背景/主视觉 |
| 中性色Neutral | `--color-neutral` | oklch(14% .005 285.823) | #09090b | 背景/主视觉 |
| 中性色Neutral | `--color-neutral-content` | oklch(92% .004 286.32) | #e4e4e7 | 背景/主视觉 |

### 1.2 基础面（Base / Neutral surfaces）
| 名称 | Token | oklch | HEX | 用途 |
|---|---|---|---|---|
| 基础面-100 | `--color-base-100` | oklch(100% 0 0) | #ffffff | 页面/卡片背景 |
| 基础面-200 | `--color-base-200` | oklch(98% 0 0) | #f8f8f8 | 页面/卡片背景 |
| 基础面-300 | `--color-base-300` | oklch(95% 0 0) | #eeeeee | 页面/卡片背景 |
| 基础内容色 | `--color-base-content` | oklch(21% .006 285.885) | #18181b | 正文/标题文字 |

### 1.3 语义状态色（Semantic）
| 名称 | Token | oklch | HEX | 用途 |
|---|---|---|---|---|
| 成功Success | `--color-success` | oklch(76% .177 163.223) | #00d390 | 状态背景 |
| 成功Success | `--color-success-content` | oklch(37% .077 168.94) | #004c39 | 状态背景 |
| 错误Error | `--color-error` | oklch(71% .194 13.428) | #ff627d | 状态背景 |
| 错误Error | `--color-error-content` | oklch(27% .105 12.094) | #4d0218 | 状态背景 |
| 警告Warning | `--color-warning` | oklch(82% .189 84.429) | #fcb700 | 状态背景 |
| 警告Warning | `--color-warning-content` | oklch(41% .112 45.904) | #793205 | 状态背景 |
| 信息Info | `--color-info` | oklch(74% .16 232.661) | #00bafe | 状态背景 |
| 信息Info | `--color-info-content` | oklch(29% .066 243.157) | #042e49 | 状态背景 |


### 1.4 扩展调色板（Palette 色阶）

**blue**

| 阶梯 | HEX | oklch |
|---|---|---|
| 50 | #eff6ff | oklch(97% .014 254.604) |
| 100 | #dbeafe | oklch(93.2% .032 255.585) |
| 200 | #bedbff | oklch(88.2% .059 254.128) |
| 300 | #8ec5ff | oklch(80.9% .105 251.813) |
| 400 | #51a2ff | oklch(70.7% .165 254.624) |
| 500 | #2b7fff | oklch(62.3% .214 259.815) |
| 600 | #155dfc | oklch(54.6% .245 262.881) |
| 700 | #1447e6 | oklch(48.8% .243 264.376) |
| 800 | #193cb8 | oklch(42.4% .199 265.638) |
| 900 | #1c398e | oklch(37.9% .146 265.522) |
| 950 | #162456 | oklch(28.2% .091 267.935) |

**green**

| 阶梯 | HEX | oklch |
|---|---|---|
| 50 | #f0fdf4 | oklch(98.2% .018 155.826) |
| 100 | #dcfce7 | oklch(96.2% .044 156.743) |
| 200 | #b9f8cf | oklch(92.5% .084 155.995) |
| 300 | #7bf1a8 | oklch(87.1% .15 154.449) |
| 500 | #00c950 | oklch(72.3% .219 149.579) |
| 600 | #00a63e | oklch(62.7% .194 149.214) |
| 700 | #008236 | oklch(52.7% .154 150.069) |
| 800 | #016630 | oklch(44.8% .119 151.328) |
| 900 | #0d542b | oklch(39.3% .095 152.535) |

**red**

| 阶梯 | HEX | oklch |
|---|---|---|
| 50 | #fef2f2 | oklch(97.1% .013 17.38) |
| 100 | #ffe2e2 | oklch(93.6% .032 17.717) |
| 200 | #ffc9c9 | oklch(88.5% .062 18.334) |
| 400 | #ff6467 | oklch(70.4% .191 22.216) |
| 500 | #fb2c36 | oklch(63.7% .237 25.331) |
| 600 | #e7000b | oklch(57.7% .245 27.325) |
| 700 | #c10007 | oklch(50.5% .213 27.518) |
| 800 | #9f0712 | oklch(44.4% .177 26.899) |
| 900 | #82181a | oklch(39.6% .141 25.723) |

**amber**

| 阶梯 | HEX | oklch |
|---|---|---|
| 600 | #e17100 | oklch(66.6% .179 58.318) |

**orange**

| 阶梯 | HEX | oklch |
|---|---|---|
| 100 | #ffedd4 | oklch(95.4% .038 75.164) |
| 600 | #f54900 | oklch(64.6% .222 41.116) |
| 700 | #ca3500 | oklch(55.3% .195 38.402) |

**indigo**

| 阶梯 | HEX | oklch |
|---|---|---|
| 100 | #e0e7ff | oklch(93% .034 272.788) |
| 600 | #4f39f6 | oklch(51.1% .262 276.966) |
| 700 | #432dd7 | oklch(45.7% .24 277.023) |

**purple**

| 阶梯 | HEX | oklch |
|---|---|---|
| 50 | #faf5ff | oklch(97.7% .014 308.299) |
| 200 | #e9d4ff | oklch(90.2% .063 306.703) |
| 500 | #ad46ff | oklch(62.7% .265 303.9) |
| 600 | #9810fa | oklch(55.8% .288 302.321) |

**slate**

| 阶梯 | HEX | oklch |
|---|---|---|
| 50 | #f8fafc | oklch(98.4% .003 247.858) |
| 200 | #e2e8f0 | oklch(92.9% .013 255.508) |
| 300 | #cad5e2 | oklch(86.9% .022 252.894) |
| 500 | #62748e | oklch(55.4% .046 257.417) |
| 600 | #45556c | oklch(44.6% .043 257.281) |
| 700 | #314158 | oklch(37.2% .044 257.287) |
| 800 | #1d293d | oklch(27.9% .041 260.031) |
| 900 | #0f172b | oklch(20.8% .042 265.755) |
| 950 | #020618 | oklch(12.9% .042 264.695) |

**gray**

| 阶梯 | HEX | oklch |
|---|---|---|
| 50 | #f9fafb | oklch(98.5% .002 247.839) |
| 100 | #f3f4f6 | oklch(96.7% .003 264.542) |
| 200 | #e5e7eb | oklch(92.8% .006 264.531) |
| 300 | #d1d5dc | oklch(87.2% .01 258.338) |
| 400 | #99a1af | oklch(70.7% .022 261.325) |
| 500 | #6a7282 | oklch(55.1% .027 264.364) |
| 600 | #4a5565 | oklch(44.6% .03 256.802) |
| 700 | #364153 | oklch(37.3% .034 259.733) |
| 800 | #1e2939 | oklch(27.8% .033 256.848) |
| 900 | #101828 | oklch(21% .034 264.665) |

**yellow**

| 阶梯 | HEX | oklch |
|---|---|---|
| 50 | #fefce8 | oklch(98.7% .026 102.212) |
| 100 | #fef9c2 | oklch(97.3% .071 103.193) |
| 200 | #fff085 | oklch(94.5% .129 101.54) |
| 300 | #ffdf20 | oklch(90.5% .182 98.111) |
| 500 | #f0b100 | oklch(79.5% .184 86.047) |
| 800 | #894b00 | oklch(47.6% .114 61.907) |

**emerald**

| 阶梯 | HEX | oklch |
|---|---|---|
| 600 | #009966 | oklch(59.6% .145 163.225) |

**sky**

| 阶梯 | HEX | oklch |
|---|---|---|
| 500 | #00a6f4 | oklch(68.5% .169 237.323) |

### 1.5 品牌资产与授权说明（Brand Assets & Legal）
> 2026-09-22 从产品截图与线上品牌落地页提取。涉及服务承诺、交付主体、授权声明的内容必须按此口径呈现，避免合规风险。

**品牌名称**
- 中文：Humance 慧思｜英文：Humance
- 定位：中企出海人力资源知识中心

**Logo 规范**
| 项 | 说明 |
|---|---|
| 组合 | H 字母图标 + 「Humance 慧思」文字组合 |
| 图标形态 | 圆角矩形底（白底）内嵌蓝色「H」字母 |
| 图标底色 | #ffffff |
| 图标字母色 | #155dfc |
| 使用场景 | 导航栏左上角、页脚、品牌落地页 Hero、分享卡片 |
| 备注 | 图标与文字组合使用；单独使用时优先保留 H 图标，禁止拉伸/改色/倾斜。 |

**Favicon**
- 待补充线上源文件路径；建议为 H 图标单色或品牌蓝 #155dfc 版本

**服务归属口径**
- 全球猎头服务由用友薪福社提供专业交付
- TalentSeek 为交付支撑平台

**授权声明（必须原样出现在全球猎头品牌落地页）**
> 本页为 Humance 慧思「全球猎头」板块品牌落地页（承载于 humancehr.com），最终服务以用友薪福社海外猎头服务条款为准。

**品牌层级**
| 层级 | 名称 |
|---|---|
| 集团/公司品牌 | 用友 · 用友薪福社 |
| 产品品牌 | Humance 慧思 |
| 服务子品牌 | TalentSeek（全球 AI 猎头） |
| 交付主体 | 用友薪福社海外猎头服务 |

**使用禁忌**
| 类型 | 要求 |
|---|---|
| ✅ 正确 | Logo 组合完整出现；服务说明保留「用友薪福社提供专业交付」与「TalentSeek 为交付支撑平台」双重 attribution；落地页底部/表单旁放置授权声明。 |
| ❌ 禁止 | 单独使用 TalentSeek 替代 Humance 慧思作为产品品牌；删除/弱化用友薪福社交付主体；将「全球猎头」服务承诺绝对化。 |

## 2. 字体（Typography）
- 无衬线（正文）：`ui-sans-serif,system-ui,sans-serif,"Apple Color Emoji","Segoe UI Emoji","Segoe UI Symbol","Noto Color Emoji"`
- 等宽（代码/数据）：`ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,"Liberation Mono","Courier New",monospace`
- 字重：Medium 500 / Semibold 600 / Bold 700 / Extrabold 800

### 字号阶梯
| Token | 字号 | 行高 |
|---|---|---|
| `text-xs` | undefined |  |
| `text-sm` | undefined |  |
| `text-base` | undefined |  |
| `text-lg` | undefined |  |
| `text-xl` | undefined |  |
| `text-2xl` | undefined |  |
| `text-3xl` | undefined |  |
| `text-4xl` | undefined |  |
| `text-5xl` | undefined |  |
| `text-6xl` | undefined |  |
| `text-8xl` | undefined |  |

## 3. 间距与圆角（Spacing & Radius）
- 间距基准 `--spacing` = .25rem（1 单位 = 4px，Tailwind 默认）
- 圆角：box .5rem / field .25rem / selector .5rem / lg .5rem / xl .75rem / 2xl 1rem

## 4. 容器宽度（Container）
| 断点 | 宽度 |
|---|---|
| xs | 20rem |
| md | 28rem |
| lg | 32rem |
| 2xl | 42rem |
| 3xl | 48rem |
| 4xl | 56rem |
| 5xl | 64rem |
| 6xl | 72rem |
| 7xl | 80rem |

## 5. 组件别名 Token（Component aliases）
| Token | 值（指向） |
|---|---|
| `--btn-color` | `var(--color-success)` |
| `--btn-bg` | `#0000` |
| `--btn-fg` | `var(--btn-color)` |
| `--badge-color` | `var(--color-success)` |
| `--badge-bg` | `var(--badge-color,var(--color-base-100))` |
| `--tab-border-color` | `var(--color-base-300)` |
| `--menu-active-bg` | `var(--color-neutral)` |
| `--menu-active-fg` | `var(--color-neutral-content)` |

## 6. 交互风格与组件规范
> 基于线上站真实 CSS（daisyUI 组件令牌）提取。

### 6.1 按钮 Button
**基础形态**：inline-flex 居中 · 高 40px · 字 14px · 字重 600 · 圆角 .25rem · padding-x 1rem · 过渡 .2s cubic-bezier(0,0,.2,1)

**变体**：
| 变体 | 外观 | 用途 |
|---|---|---|
| 默认 | 浅灰底(base-200)+深字(base-content)+同色边 | 中性填充 |
| primary | 实心 #155dfc | 主行动 |
| secondary | 实心 #f43098 | 次要行动 |
| success | 实心 #00d390 | 正向反馈 |
| error | 实心 #ff627d | 危险/删除 |
| ghost | 透明底+透明边+currentColor 字(hover 才显色) | 极低强调 |
| outline | 透明底+彩色边+彩色字(hover 填充) | 次强调 |

**尺寸**：xs 24px / sm 32px / md 40px / lg 48px
**状态**：hover(daisyUI 内置色变+阴影) · active(填充主色+下沉 .5px+阴影消失) · focus-visible(2px 轮廓) · disabled(灰显/禁点)

### 6.2 输入框 Input
高 40px · 圆角 .25rem · 背景 base-100 · 边框 1px(base-content，box-shadow 模拟) · 聚焦 2px 轮廓+顶部高光 · 错误态转 error 红 · 宽度 clamp(3rem,20rem,100%)

### 6.3 卡片 Card
圆角 .5rem · flex column · card-body 内边距 1.5rem / 子间距 .5rem · 聚焦轮廓过渡 .2s

### 6.4 徽标 Badge
圆角 .5rem · 高 24px · 字 14px · 背景 base-100 / 边 base-200 · 变体 primary/success/error

### 6.5 标签页 Tab
直角(圆角0) · 高 40px · padding 1rem · 字 14px · 底色 base-100 / 分隔 base-300

### 6.6 表格 Table
圆角 .5rem · 字 14px · 单元格内边距 上下 .75rem / 左右 1rem · 左对齐 / 垂直居中

### 6.7 提示 Alert
圆角 .5rem · grid · 内边距 .75rem/1rem · 字 14px 行高1.25rem · 默认底 base-200 · 变体 success/warning/error

### 6.8 链接 Link
光标 pointer · 下划线 · 变体 link-primary

### 6.9 通用交互原则
- 过渡时长：控件 .2s(cubic-bezier(0,0,.2,1))；卡片轮廓 .2s ease-in-out
- 反馈：hover 色变 / active 下沉 / focus 2px 轮廓
- 圆角分级：field .25rem(输入/按钮) · box .5rem(卡片/表格/弹窗) · selector .5rem(标签/徽标)
- 间距基准 .25rem(4px)
## 6.10 可访问性（a11y）对比度基线
> 2026-09-21 对线上站真实语义色的 WCAG 2.1 实测。语义色用于「文字」时须谨慎——daisyUI 默认 *-color 在白底偏亮，*-content 为配深底设计。

| 色彩组合 | 实测对比度 | 等级 | 结论 / 红线 |
|---|---|---|---|
| primary 底 / primary-content 字 | 5.27:1 | AA | 按钮文字 OK |
| primary 作字 on 白底 | 8.36:1 | AAA | 可作主色链接 / 标题 |
| secondary 底 / secondary-content 字 | 3.07:1 | 仅大字 | ⚠️ 小字不达标，secondary 按钮文字建议 ≥ sm |
| secondary 作字 on 白底 | 4.62:1 | AA | 仅限非关键文字 |
| accent 底 / accent-content 字 | 6.11:1 | AA | OK |
| accent 作字 on 白底 | 3.12:1 | 仅大字 | ⚠️ 不可作白底小字 |
| success 底 / success-content 字 | 5.95:1 | AA | OK |
| success 作字 on 白底 | 3.23:1 | 仅大字 | ⚠️ 白底绿色提示文字须加深 |
| error 底 / error-content 字 | 5.35:1 | AA | OK |
| error 作字 on 白底 | 3.82:1 | 仅大字 | ⚠️ 白底红色错误文字须加深或放 alert |
| base-content 正文 on base-100 | 20.70:1 | AAA | 正文首选 |
| base-content 正文 on base-200 | 18.17:1 | AAA | OK |
| base-content 正文 on base-300 | 14.90:1 | AAA | OK |

**红线**：白底上的状态文字（成功/错误/警告）禁止直接使用 *-color，须用加深版（如 error 用 #c10007 级）或置于 alert 组件内（文字用 base-content）。secondary 按钮文字对比度仅 3.07:1，建议不小于 sm(32px) 或改深底。


## 7. 页面模板库
> 基于线上站 2026-09-21 真实页面（sitemap 12 个静态页 + 详情页）归纳。带 ⚠️ 为设计态（非线上抓取）。

### 7.1 资源中心首页
- 路径：`/（www / demo 根域）`
- 渲染：SSR

| 区块 / 元素 | 说明 |
|---|---|
| **顶部国家导航** | 国家快捷入口 + 「更多」（CountryNav，见 8.8） |
| **全局搜索 / Hero** | 站点主标题 + 搜索入口 |
| **内容区① 知识库** | 卡片网格（最新文章）+ 「查看全部 →」 |
| **内容区② 薪酬报告** | 卡片网格（报告卡）+ 「查看全部 →」 |
| **内容区③ 国别指南** | 卡片网格（国家信息卡）+ 「查看全部 →」 |
| **页脚** | 版权 / 链接 |

> 根域即「全球出海资源知识中心」，并非独立营销落地页；三大内容区结构一致、数据源各异（kb / remuneration / country-guide）。

### 7.2 列表 / 网格页
- 路径：`/knowledge-base · /remuneration · /country-guide · /holiday · /regulation`
- 渲染：SSR 首屏 + 客户端筛选

| 区块 / 元素 | 说明 |
|---|---|
| **筛选区** | 国家筛选 + 类型筛选 + 关键词搜索（客户端实时过滤） |
| **内容网格** | 响应式卡片网格（auto-fill minmax(220–280px, 1fr)） |
| **分页 / 加载更多** | 分页或无限滚动 |

> 5 类列表页共用同一网格 + 筛选骨架；筛选为客户端交互，SSR 输出首屏卡片。

### 7.3 详情页（4 子型）
- 路径：`/knowledge-base/:slug · /remuneration/:slug · /country-guide/:slug · /regulation/:slug`
- 渲染：SSR

| 区块 / 元素 | 说明 |
|---|---|
| **标题区** | 标题 + 发布日期 / 国家标签 / 分类标签（报告另含 周期·地区·行业·数据来源） |
| **正文** | 段落 / 小标题 / 引用 / 列表 / 关键数据表 |
| **附加块** | 来源引用 · Q&A · 关键提示（文章）/ 薪酬带宽数据块（报告，见 8.4）/ 国家信息卡（国别，见 8.5） |
| **相关推荐** | 同国家 / 同类型条目 |

> 同一详情骨架，依内容类型渲染不同附加块；报告详情含「薪酬带宽表」，国别含「国家信息卡」。

### 7.4 服务 / 产品落地页
- 路径：`/service`
- 渲染：SSR

| 区块 / 元素 | 说明 |
|---|---|
| **Hero** | 主标语 + 副文案 + 主 CTA |
| **服务矩阵** | 6 大服务：名义雇主 EOR / 薪资外包 Payroll / 工作签证 / 全球猎头 / 人才招聘 / 合规工具 |
| **价值主张** | 3 图标卡（全球本地化 / 100% 合规 / 专属客户经理） |
| **留资表单 LeadForm** | 企业名称* / 行业* / 规模* / 所在国家* / 需求国家* / 姓名* / 邮箱* / 电话 / 职位 + 立即提交（primary） |

> 唯一含线索留资表单的页面，是营销转化核心；必填项用 * 标注。

### 7.5 账户 / 留资页
- 路径：`/favorites（收藏）· /forgot-password（找回密码）`
- 渲染：SSR / 客户端

| 区块 / 元素 | 说明 |
|---|---|
| **账户态内容** | 收藏列表 / 密码找回表单 |
| **轻量表单** | 少量字段，聚焦单一任务 |

> 账户相关轻页面；注册 / 登录流未出现在 sitemap（疑似未索引或尚未上线），列为待确认。

### 7.6 工具 Hub 页（Compass / JD Studio）
- 路径：`本地原型（compass-landing / jd-landing / jd-prototype），线上未部署`
- 渲染：设计态 · 未上线

| 区块 / 元素 | 说明 |
|---|---|
| **工具入口** | 工具切换 tab / 卡片（EOR / Payroll / 猎头 / Compass 合规哨兵 / JD Studio） |
| **生成器表单** | 输入参数 → 生成结果（合规自检 / JD） |
| **结果区** | 结构化输出 + 导出 / 复制 |

> ⚠️ 设计态模板，非线上抓取。产品规划中工具统一入口页，须与 7.4 落地页 CTA 闭环导航。

### 7.7 栅格与响应式
- 路径：`全局`
- 渲染：—

| 区块 / 元素 | 说明 |
|---|---|
| **栅格** | 12 列栅格；内容网格用 auto-fill minmax(220–280px, 1fr) |
| **断点** | 见第 4 章容器宽度（xs→7xl，最大 80rem≈1280px） |
| **移动端** | 卡片单列堆叠；筛选区收起为抽屉 / 顶部横向滚动 |

> 容器最大宽度 80rem；栅格以卡片网格为主，少用固定多列。

## 8. 业务组件库
> 业务级组件，复用第 6 章基础组件（Card / Badge / Table / Input / Button）。

### 8.1 资源卡 ResourceCard

**变体**

| 变体 | 结构 / 字段 |
|---|---|
| **知识库卡** | 缩略图 / 标题 / 发布日期 / 分类标签 / 摘要 / 「查看」链接 |
| **薪酬报告卡** | 标题 / 报告周期 / 地区 / 行业 / 数据来源 / 「查看报告」 |
| **国别指南卡** | 国旗 / 国家名 / 首都 / 官方语言 / 货币 |

**状态**

| 状态 | 表现 |
|---|---|
| hover | 轻微上浮 / 边框高亮 |
| focus | focus-visible 2px 轮廓 |
| 点击 | 整卡可点击 |

> 三类卡片共用同一 Card 容器（6.3），差异化在 body 字段组合。

### 8.2 法规条目卡 RegulationCard

**变体**

| 变体 | 结构 / 字段 |
|---|---|
| **默认** | 国家 / 法规名(多语种) / 生效日期 / 分类标签 / 适用 / 状态 badge(生效中) / 「查看官方原文」链接 |

**状态**

| 状态 | 表现 |
|---|---|
| hover | 高亮 |
| 状态 | badge 表达（生效中 = success） |

> 法规名保留原文多语种；状态「生效中」用 success badge。

### 8.3 国家筛选器 CountryFilter

**变体**

| 变体 | 结构 / 字段 |
|---|---|
| **默认** | 国家多选 + 类型筛选 + 关键词搜索框 |

**状态**

| 状态 | 表现 |
|---|---|
| 选中态 | primary 描边 / 填充 |
| 操作 | 清空 / 重置 |
| 过滤 | 实时过滤 + 结果计数 |

> 列表页(7.2)核心交互；客户端实时过滤，须有「无结果」兜底（见 9.5）。

### 8.4 薪酬带宽表 SalaryBandTable

**变体**

| 变体 | 结构 / 字段 |
|---|---|
| **默认** | 列：岗位层级 / 年薪中位数 / 月薪估算 / 分位 P25·P50·P75 / 样本量 / 数据质量 |

**状态**

| 状态 | 表现 |
|---|---|
| 表头 | sticky 吸顶 |
| 货币列 | 本地 / ≈¥ / ≈$ 三列等宽对齐 |

> 报告详情(7.3)核心数据组件；套用 6.6 表格规范。

### 8.5 国家信息卡 CountryInfoCard

**变体**

| 变体 | 结构 / 字段 |
|---|---|
| **默认** | 国旗 / 首都 / 官方语言 / 货币 / 时区 |

**状态**

| 状态 | 表现 |
|---|---|
| 只读 | 信息密度低，不可编辑 |

> 国别指南详情(7.3)头部信息块。

### 8.6 留资表单 LeadForm

**变体**

| 变体 | 结构 / 字段 |
|---|---|
| **默认** | 8 字段：企业名称* / 行业* / 规模* / 所在国家* / 需求国家* / 姓名* / 邮箱* / 电话 / 职位 + 立即提交(primary) |

**状态**

| 状态 | 表现 |
|---|---|
| 校验 | 字段级（红框 + error 提示） |
| 提交中 | 按钮 disabled + loading |
| 成功 | alert success |
| 失败 | alert error + 可重试 |

> 见 7.4 与 9.3 状态机；必填项 * 标注。

### 8.7 工具 Hub 导航 ToolHubNav

**变体**

| 变体 | 结构 / 字段 |
|---|---|
| **设计态** | 工具切换 tab / 卡片：EOR / Payroll / 猎头 / Compass / JD Studio |

**状态**

| 状态 | 表现 |
|---|---|
| 当前工具 | 高亮（primary） |
| 状态 | 未上线 |

> ⚠️ 设计态，非线上抓取。

### 8.8 顶部国家导航 CountryNav

**变体**

| 变体 | 结构 / 字段 |
|---|---|
| **默认** | 热门国家快捷入口 + 「更多」 |

**状态**

| 状态 | 表现 |
|---|---|
| hover | 高亮 |
| 选中 | 当前国家 |

> 资源中心首页(7.1)顶部。

## 9. 页面级状态机与异常分支
> 统一状态流转与兜底 UI 规范，所有页面必须遵守。

### 9.1 列表页状态机
状态流转：`idle → loading → (empty | data) → (filtering | error→retry)`

| 状态 | 表现 |
|---|---|
| **idle** | 初始，等待首屏 |
| **loading** | 骨架屏 / spinner（见 9.5） |
| **data** | 渲染卡片网格 |
| **empty** | 无结果 → 空态（见 9.5） |
| **filtering** | 筛选中，局部 loading |
| **error** | 加载失败 → error + 重试按钮 |

### 9.2 详情页状态机
状态流转：`loading → (loaded | not_found | error)`

| 状态 | 表现 |
|---|---|
| **loading** | 骨架屏 |
| **loaded** | 正文渲染 |
| **not_found** | 404（见 9.5） |
| **error** | 加载失败 → 重试 |

### 9.3 表单页状态机
状态流转：`idle → validating → submitting → (success | error)`

| 状态 | 表现 |
|---|---|
| **idle** | 待填写 |
| **validating** | 字段级实时校验（红框 + error 提示） |
| **submitting** | 提交中（按钮 disabled + loading） |
| **success** | alert success + 跳转 / 确认 |
| **error** | alert error + 可重试 |

### 9.4 工具生成页状态机
状态流转：`input → generating → (result | fail)`

| 状态 | 表现 |
|---|---|
| **input** | 用户填参数 |
| **generating** | 生成中（loading，可取消） |
| **result** | 结构化结果 + 导出 / 复制 |
| **fail** | 失败 → 重试 |

### 9.5 异常分支统一规范
状态流转：`loading / empty / error / 404 / 超时 / 无权限 / 网络断开`

| 状态 | 表现 |
|---|---|
| **loading** | 骨架屏或 spinner，主色点缀，禁止空白卡死 |
| **empty** | 空态图标 + 一句说明 + 主色 CTA（如「去浏览知识库」） |
| **error** | alert error + 重试按钮（primary） |
| **404** | 专用 404 模板（/tools 实测为 404）：返回首页 CTA |
| **超时** | 同 error，文案提示「网络较慢，请重试」 |
| **无权限** | 提示登录 / 授权 + 登录 CTA |
| **网络断开** | 离线提示 + 重试 |

> 所有异常兜底统一用主色 CTA + alert / icon，禁止裸文字；空态与错误态须提供下一步动作。

## 10. 维护说明
- 本规范的**真相源**为线上站 CSS 文件（见数据源）。
- 后续站内改造如需更新设计 token，须先改前端源码，再重新抓取本规范，避免口径漂移。
- 色彩以 oklch 为权威值，HEX 为设计师便捷换算值（同色可视等价）。
