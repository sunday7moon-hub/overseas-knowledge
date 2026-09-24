---
name: html-to-pdf-print
description: 把 HTML 交付物（报告 / 产品介绍 / 一页纸 / 场景地图）转成可**直接对外发送**的 A4 PDF —— 保留彩色版式、每页斜向水印、去掉浏览器页眉页脚的 file:// 路径。当用户说「导成 PDF」「打印版」「发客户 / 发平台用」「HTML 转 PDF」「出一份带水印的 PDF」时使用。含 Chrome 无头导出的三个必踩坑（--headless=new 会失败 / 中文路径失败 / 默认页眉页脚泄漏本地路径）与 PyMuPDF 逐页质检法。
agent_created: true
---

# HTML → 对外 PDF（Chrome 无头 + 质检）

目标产物：**能直接发出去的 PDF**。判定标准有三条，缺一条就是废品：

1. **彩色版式在**（不加 `print-color-adjust` 会全打印成白底，彩色卡片/深色 HERO 全丢）
2. **没有本地路径**（Chrome 默认加 `file:///...` 页眉页脚 —— 发出去就露怯）
3. **每页都有水印**（品牌露出 + 防外传）

---

## 一、三步流程

### 步骤 1 · 给 HTML 注入打印样式

在 `</style>` 前追加（或升级已有 `@media print`）。**关键是前两条** —— 少一条就会出白底或超宽。

```css
@media print{
  @page{size:A4;margin:11mm 10mm}
  /* ① 保色：不加这行，所有背景色/彩色块会被剥掉 */
  html,body{-webkit-print-color-adjust:exact!important;print-color-adjust:exact!important}
  /* ② 容器收窄：网页常用 max-width:1000px，A4 装不下会被缩放成小字 */
  .wrap{max-width:100%!important;padding:0 6px 16px!important}
  body{background:#fff;font-size:10.5pt}
  /* ③ 水印在打印态略微加深（屏幕 .055 太淡，PDF 里几乎看不见） */
  .wm{opacity:.1;position:fixed}
  /* ④ 分页控制 */
  .card,.scene,.fn,.box,.tier{break-inside:avoid}
  h2{break-after:avoid}
  tr{break-inside:avoid}
}
```

> 水印用 `position:fixed` 的斜向网格层时，Chrome 会把它在**每一页重复渲染**（实测 22 页共出现 492 次），不需要额外处理。

#### ⚠️ 打印视口会命中响应式断点 —— 最隐蔽的「页数虚增」元凶（2026-09-11 实测）

Chrome 打印时的布局视口 ≈ 内容盒宽度（A4 横向 297mm − 2×8mm 边距 ≈ 1062 CSS px）。
**但它实测会命中 `@media(max-width:900px)` 之类的移动断点**，把桌面栅格压成 2–3 列 →
卡片变高 → 整块面板被 `break-inside:avoid` 推下页 → **页数从 4 页虚增到 8 页，且每页底部大片留白**。

**症状很好认**：PDF 里卡片区变成 2 列，而网页上明明写的是 4–6 列。

修法 —— 在 `@media print` 里用 `!important` 把栅格**锁回桌面列数**：

```css
@media print{
  .kpis  {grid-template-columns:repeat(6,1fr)!important}
  .m4    {grid-template-columns:repeat(4,1fr)!important}
  .two   {grid-template-columns:1fr 1fr!important}
  .alerts{grid-template-columns:repeat(3,1fr)!important}
  .ttitle{width:300px!important}          /* 被移动端改成窄宽度的定宽元素同理 */
}
```

若锁列后仍有**单个高面板落不进当前页**（`break-inside:avoid` 会把它整块推到下一页，
前面留一大片空白），在 `@media print` 的 `body` 上加一行 `zoom:.9` 整体收缩 10%，通常就刚好放得下。
实测：8 页 → 5 页 → **4 页**，首页密度从 683 字符升到 1095 字符。

> **附带收益**：打印态同时把 `@page` 边距、字号、卡片内边距一起收紧（`.hero h1{19px}` / `.kpi{padding:10px 12px}`
> / `.m4{gap:9px}` 之类），比只锁栅格更容易让面板「刚好落进」当前页。

#### ⚠️ 测「页面留白率」别用像素扫描（2026-09-11 实测）

水印是覆盖全页的 `position:fixed` 层 —— 任何「从下往上找最后一个非背景色像素」的算法都会被它骗到，
**每一页都报 100% 有内容**，完全测不出留白。

正确判据用**每页文本字符数**：`len(pg.get_text().strip())`。字符数显著低于中位数（如某页 683、
其余 1000+）才说明该页真留白。另外注意 `get_pixmap()` 逐像素比对在纯 Python 下极慢
（8 页 110dpi 要跑 10 分钟以上）—— 降到 60dpi + 步长采样，或装 numpy 向量化。

### 步骤 2 · Chrome 无头导出

```bash
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

# ⚠️ 中文文件名/路径会让导出静默失败 → 先复制成英文名到 /tmp
cp "/path/to/中文报告.html" /tmp/render.html

"$CHROME" --headless --disable-gpu \
  --no-pdf-header-footer \
  --print-to-pdf=/tmp/render.pdf \
  file:///tmp/render.html

cp /tmp/render.pdf "/path/to/中文报告.pdf"
```

**三个坑，都实测踩过：**

| 坑 | 现象 | 解法 |
|---|---|---|
| 用 `--headless=new` / `--headless=old` | PDF **不生成**，只吐一堆 `CVDisplayLink` 报错 | 用**裸 `--headless`**（Chrome 152 实测可行） |
| 输出路径或 HTML 路径含**中文** | PDF 不生成 | 先 `cp` 到 `/tmp/` 用英文名渲染，再复制回来 |
| 不加 `--no-pdf-header-footer` | 页眉页脚带 `file:///tmp/xxx.html` 和页码 | 必须加 |
| 加 `--no-sandbox --user-data-dir=...` | 反而失败 | **别加**，裸跑最稳 |

> `--virtual-time-budget=9000` 可用于等待 JS 生成的内容（如水印网格），但裸模式实测不等也能出；若页面有异步渲染再补。

### 步骤 3 · PyMuPDF 逐页质检（**必做**）

不质检就发出去，等于赌。用 `pymupdf` 一次查完四项：

```python
import fitz
d = fitz.open("/tmp/render.pdf")
print("页数:", d.page_count, "| 尺寸:", d[0].rect)   # 应为 595x842pt = A4

wm = "用友薪福社"          # 换成实际水印关键词
for i, pg in enumerate(d):
    t = pg.get_text()
    n = len(t.strip())
    flag = "  ⚠️空白" if n < 120 else ""            # 每页字符数 < 120 → 疑似空白页
    print(f"{i+1:>2}  {n:>6} 水印{t.count(wm):>3} 图{len(pg.get_images()):>2}{flag}")

full = "\n".join(p.get_text() for p in d)
for kw in ["品牌名", "版本号", "邮箱", "官网"]:
    print(kw, full.count(kw))                        # 关键信息是否都进去了
```

**判读标准**

| 项 | 合格 |
|---|---|
| 页数 | 无 0 页 / 无整页空白（字符数不低于 ~120） |
| 水印 | **每页**都出现，不是只第一页 |
| 图片 | 首页 logo + 尾页二维码所在页的 `get_images()` 不为 0 |
| 尺寸 | 595×842pt（A4） |

**视觉抽查**（表格页 + 尾页各选一张，人眼确认）：

```python
for n in (13, 22):                       # 选表格密集页 / 二维码尾页
    d[n-1].get_pixmap(dpi=105).save(f"/tmp/pg{n}.png")
```
然后用 Read 看这两张图。

> ⚠️ PyMuPDF 装在隔离环境：`/Users/yoyo/.workbuddy/binaries/python/envs/default/bin/python`
> 未装则：`/Users/yoyo/.workbuddy/binaries/python/envs/default/bin/pip install pymupdf`

---

## 二、已知可接受的瑕疵（不必修）

- **章节标题被推到下页**：`h2{break-after:avoid}` 会让标题和首块内容一起下移，造成页面底部约 1/4 留白。这是专业文档的正常表现，**强行改成 `break-after:auto` 会产生页尾孤儿标题，更难看**。
- **PDF 文本层含水印文字**：水印是真实文本，复制文字时会混入。对外影响极小。
- **深色 HERO 区看不到水印**：水印层 z-index 低于深色区块，被遮住。可接受。

## 三、可选增强

- **交付给外部时**，若文档含内部章节（红线清单 / 内部排期 / 未公开数据），建议另出一版删节 PDF，别直接发全量。
- 需要每页页脚品牌行（而非仅在首页/尾页）时，改用 CDP `Page.printToPDF` 的 `footerTemplate`（需 websocket 客户端），CLI 不支持。

---

## 四、同源用途：用无头 Chrome 精确出图（上架素材 / 宣传图）

同一套 HTML 版式可以**按像素精确出 PNG**，不必用设计工具：

```bash
CH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
"$CH" --headless --screenshot=out.png --window-size=1200,630 file:///abs/path/page.html
```

要点：

- **`--window-size=W,H` 就是出图尺寸**（不是页面尺寸）→ 把 HTML 做成 `html,body{width:100%;height:100%;overflow:hidden}` + 一个定尺容器，截图即得精确规格的图（如 512²、1080²、1200×630）
- **不要加** `--user-data-dir` / `--no-sandbox`（会让渲染失败）；路径含中文时先 `cp` 到 `/tmp` 用英文名
- 想批量出多张：让生成脚本为每种尺寸各写一个 HTML，再循环截图（一次一个窗口尺寸）
- 交互态截图（如聊天页面里的运行时内容）：**不要加 `--virtual-time-budget`**，裸 `--screenshot` 即可；有些页面对虚拟时间更敏感

### ⚠️ 当「DOM 量出来是对的，但截图是坏的」——排查方法

别靠猜。往页面里注入一段调试脚本，用 `getBoundingClientRect()` **把实际宽度画进图里**，然后看截图上的绿字：

```js
['#chat','.row','.bub','ul.dot'].forEach(function(sel){
  var e=document.querySelector(sel); var r=e.getBoundingClientRect();
  out.push(sel+' W='+Math.round(r.width)+' x='+Math.round(r.left));
});
// 写成 position:fixed 的黑底绿字盒子，截图里直接读
```

命令行侧用 `--dump-dom | grep` 也能读，但**截图内的绿字更可信**——它和出问题的那一帧来自同一次渲染。

实战案例（已复现，值得记住）：列表在 flex 气泡里塌成**单字竖排**，`.bub` 量出来 680px 正常，问题在 `ul` 只有 6px。根因是**类名碰撞**——头部的「在线绿点」定义了 `.dot{width:6px;height:6px;border-radius:50%}`，与列表类 `ul.dot` 撞名，列表继承了 `width:6px`。`ul.dot` 的选择器优先级更高，但它没声明 `width`，于是 `.dot` 的 `width:6px` 生效。

**结论：短类名（`.dot` / `.bar` / `.tag` / `.list`）在新页面里复用前，先全局搜一遍同名定义。**

### 4.1 截「运行时内容」（聊天回答 / 数据看板）——两遍法

要截的不是固定版式，而是**跑出来的内容**（比如 Agent 答完一屏）。难点是高度事先不知道：窗口给小了内容被裁，给大了底部一片留白。
用**两遍法**：第一遍量高度，第二遍按高度出图。

**页面侧**（在出图模式下把实测高度写进 `<title>`）：

```js
if (new URLSearchParams(location.search).get('bare') === '1') {
  let last = -1, same = 0;
  const tick = setInterval(() => {
    const h = Math.ceil(document.documentElement.scrollHeight);
    if (document.querySelector('.row') && h === last) {
      if (++same >= 2) { clearInterval(tick); document.title = 'H=' + h; }  // 连续 2 次稳定才认
    } else { same = 0; }
    last = h;
  }, 120);
}
```

**脚本侧**：

```python
def content_height(url):
    dom = run(["--virtual-time-budget=6000", "--dump-dom", url]).stdout.decode()
    m = re.search(r"<title>H=(\d+)</title>", dom)
    return int(m.group(1)) if m else None

h = content_height(url)
run(["--screenshot=out.png", f"--window-size=1200,{h + 26}", url])   # +26 留底部呼吸
```

三个关键前提，少一个就白做：

1. **页面必须能按内容自然撑高**。若主容器是 `height:100%` + `overflow-y:auto` 的**内部滚动区**，截图只会拍到视口那一截。
   出图模式里必须放开：`body{height:auto;overflow:visible}` + `#chat{overflow:visible;flex:none}`。
2. **出图模式要顺手关掉无关元素**（推荐语 chips / 输入框 / 欢迎语 / 右上按钮）：
   `body.bare #sug, body.bare footer {display:none}`，同时跳过欢迎语的初始化请求 —— 否则截图里一半是聊天框外壳。
3. 用 `?q=提问&bare=1` 这类**深链**驱动内容，脚本只改 query 就能批量出不同问题的截图。

**产物组织**：一个 `gen_shots.py` 里放 `SHOTS = [(文件名, 提问, 说明)]` 列表，改文案只改列表后重跑；脚本顶部用 `BASE` / `CHROME` 环境变量，别把绝对路径写死在逻辑里。

---

## 五、字体嵌入与水印可见性（对外交付必查）

这两项都是「肉眼看不出、客户一看就露馅」的类型，必须用程序判定。

### 5.1 中文字体嵌入：PingFang 会被转成 Type3

macOS 上 **PingFang SC / Hiragino Sans GB 不允许子集嵌入**，Chrome 会退化成「每个字一个 Type3 字体对象」——渲染不会错，但每页上百个字体对象、文本检索兼容性差、体积翻倍。实测对比：

| 字体 | 结果 |
|---|---|
| PingFang SC / Hiragino Sans GB | ❌ Type3（每页 100+ 对象，无 FontFile） |
| **Heiti SC**（STHeitiSC Light/Medium） | ✅ Type0 + FontFile，正常嵌入 |
| Songti SC / STSongti-SC | ✅ 正常嵌入（衬线） |
| Arial Unicode MS | ✅ 正常嵌入（字形偏宽，不适合正文） |

**做法：屏幕态保留 PingFang（最好看），在 `@media print` 里单独换字体：**

```css
@media print{
  html,body{font-family:"Heiti SC","Songti SC","Arial Unicode MS","Microsoft YaHei",sans-serif}
}
```

判据（**每次对外交付都跑一遍**）：

```python
import re, pathlib, fitz
b = pathlib.Path("out.pdf").read_bytes()
print("内嵌字体:", sorted(set(re.findall(rb"/BaseFont\s*/([A-Za-z0-9+\-]+)", b))))
print("FontFile:", len(re.findall(rb"/FontFile[0-9]?", b)), "次")   # >0 才算真嵌入
d = fitz.open("out.pdf")
print("残留 Type3:", sum(1 for p in d for x in p.get_fonts(full=True) if x[2] == "Type3"))
print("文本可抽取:", len(d[0].get_text()))                          # 0 说明字被描边成图/路径
```

### 5.2 `--print-to-pdf` 的**输出路径**也不能含中文

已知坑升级：不只是输入 HTML 路径，**输出 PDF 路径含中文同样会静默失败**（不报错、不生成）。
统一做法：**输入输出都用 `/tmp` 英文名，最后 `cp` 回中文目的地**。

### 5.3 水印「文字层里有、眼睛看不见」——两版像素差判定

`position:fixed` 的水印层若 `z-index` 低于正文容器，会被容器的白色底盖住。文字抽取仍能搜到水印（所以**别用 get_text 判断水印是否可见**）。正确判据是**做两版对比**：

```bash
# 1) 复制 HTML，正则删掉水印块 → nowm.html
# 2) 两版各导一次 PDF，逐页比像素
```

```python
a, b = fitz.open("wm.pdf"), fitz.open("nowm.pdf")
for i in range(a.page_count):
    pa, pb = a[i].get_pixmap(dpi=110), b[i].get_pixmap(dpi=110)
    n = pa.n
    diff = sum(1 for k in range(0, len(pa.samples), n*3)
               if any(abs(pa.samples[k+j]-pb.samples[k+j]) > 3 for j in range(3)))
    print(f"第{i+1}页 差异 {diff/(len(pa.samples)//(n*3))*100:.2f}%")
```

**判读：每页稳定 >0.5% → 水印确实渲染；≈0% → 被遮住了。**

修法：把水印层调到正文容器**之上**（`.wm{z-index:3}` vs `.page{z-index:1}`，水印层加 `pointer-events:none`）。浓度建议 `opacity:.06 ~ .08`——低于 .05 打印基本看不见，高于 .1 影响阅读。

### 5.4 对外版本（删节版）必须重查分页 —— 删内容会改变分页

删掉几章做「客户版」时，最容易忽略的一点：**删节会重排整篇的分页**，于是原本没触发的分页缺陷会突然冒出来。

实战案例：原文档 22 页时 FAQ 章节标题恰好完整落在一页上，什么都没暴露；删掉前面 3 页后，同一个标题正好卡在页边界，被劈成两半 —— 上一页只剩「SECTION 11」那个小标签块，标题正文孤零零落到下一页，看起来像一块坏掉的空框。**这种缺陷只在删节后才出现，不删节永远测不出来。**

修法（一行）：

```css
h1,h2,h3,h4{break-inside:avoid;page-break-inside:avoid}
```

> 注意区分两个属性，**两个都要设**：`break-after:avoid` 只保证「标题后面不立刻断页」，不阻止标题**自己被劈开**。原文档通常只设了前者。

删节工具应把这条与「打印字体」「@page」一起注入，而不是让源文档承担 —— 源文档是内部版，不需要对外版的分页保证。

**删节后必查四项**：① 页数是否合理下降；② 内部关键词是否真的清除（关键词逐个 grep 输出 PDF 文本，别只看 HTML）；③ 章节编号有没有留空号（删第 11 章后，原第 12 章要改成 11）；④ 逐页抽查切割处的页面渲染，别只看纯文本。

**顺带一条**：做删节别手改 HTML。写一个小工具按「注释边界 + 标题文本」定位切割，并在切割**前**校验每个待删片段的标签是否自平衡（`div`/`table`/`ul` 开合数相等），不平衡就拒绝切割。源文档改版后重跑即可。

### 5.5 ⚠️ `break-inside:avoid` 不要对 `table` 设 —— 会把整张表推下页

上一节说「标题要 `break-inside:avoid`」，但**这条不能推广到表格**。踩过一次（法规文档「近一年变动」表）：

```css
/* ❌ 错：长表整表 avoid → 整张被推到下一页，前一页留大片空白 */
tr, table, .note, .sign-grid { page-break-inside:avoid }

/* ✅ 对：表格允许自身跨页，只保证「行」不被劈开 */
tr, .note, .sign-grid, .lk { page-break-inside:avoid }
```

**根因**：`avoid` 是「不可分割」的声明。表格有十几行、高度超过一页剩余空间时，浏览器无法满足「整表不分割」，只能把**整张表**移到下一页 —— 于是前一页空出一大块，看起来像排版事故。表格**本身能跨页**才是正常预期，怕的是**单行被劈成两半**。

**规则归纳**：

| 元素 | 设 `break-inside:avoid`？ | 理由 |
|---|---|---|
| `h1`~`h4` / 小节标题 | ✅ | 标题被劈开很难看 |
| `tr`（表格行） | ✅ | 一行内容被劈成两半 |
| `.note` / `.sign-grid` / 链接卡 `.lk` | ✅ | 小块整体性强，移位无害 |
| `table`（表格本身） | ❌ | 长表 avoid 会导致整表后移 + 大片留白 |
| `.sec`（大章节） | ❌（用 `auto`） | 章节必然跨页 |

**配套两条**：① `h3.sub` 这类小标题除了 `break-inside:avoid`，还要补 `break-after:avoid`（防「标题在页尾、正文在下页」）；② 改完必须**逐页抽查切割处**，别只看总页数 —— 留白不一定改变页数。

### 5.6 ⚠️ 导出前先自检源 URL 返回 200 —— 错误页会被静默存成 PDF

**这是最隐蔽的一种失败**：本地服务没起来时，请求会被前端代理接住并返回一个错误页（如 `upstream connect failed: Connection refused (os error 61)`）。无头 Chrome **照样把它渲染成 PDF 并写进目标文件** —— 不报错、不警告、退出码 0。

于是你得到一个「看起来生成成功」的产物：文件存在、体积 90KB+，内容却是 1 页空白。若脚本随后 `cp` 覆盖了正式产物，**正式交付物就被静默污染了**。

**三个判据一起看**（任一异常即说明导的是错误页）：

| 指标 | 正常 | 错误页 |
|---|---|---|
| 页数 | 与内容匹配（如 3 页） | 骤降到 1 页 |
| 尺寸 | A4（595×842） | 非 A4 |
| 水印/页 | >0 | 0 |
| Type3 计数 | 0–1 | 异常偏高（如 37） |

**做法**：

```bash
# ① 导出前自检，非 200 直接中止，别让错误页进流水线
code=$(curl -s -m 10 -o /dev/null -w "%{http_code}" "$URL")
[ "$code" = "200" ] || { echo "源 URL 非 200（$code），中止导出"; exit 1; }

# ② 导出后复核三个指标，不要只看「文件生成了」
python3 -c "
import pymupdf,sys
d=pymupdf.open(sys.argv[1])
a4=all(abs(p.rect.width-595.3)<2 and abs(p.rect.height-841.9)<2 for p in d)
print('页数',d.page_count,'A4',a4,'水印',sum(p.get_text().count('用友薪福社') for p in d))
" out.pdf
```

> **别用文件体积判断**：错误页 PDF 也有 90KB+，跟正常产物同一量级。

**顺带一个服务启动的坑**：本地服务不要用 `nohup ... &` 在工具调用里启动 —— **shell 会话结束时进程会被清理**。现象很迷惑：同一个命令内 `curl` 成功（进程还活着），下一条命令就 502（进程已死）。用宿主提供的**后台任务机制**启动（本环境为 `run_in_background`），进程才能跨调用存活。

### 5.7 ⚠️ 两个质检正则陷阱：都会报假警（2026-09-11 实测）

质检脚本报的告警**不能直接信**，这两类必须人工过一遍，否则会把正常产物判成坏的、或者反过来放过真问题：

**① 「占位符残留」会把元信息表的字段标签当成未替换**
文档头部常有一张元信息表：`客户名称｜（请填写）` / `目标国家｜印度尼西亚` / `文档编号｜HZ-…`。用 `目标国家(?!家)` 之类的正则去查「没替换的占位符」，会把**标签词本身**命中（标签就叫「目标国家」，但值已经正确填成了印度尼西亚）。

```python
# ❌ 错：只匹配标签词 → 永远报 1 处「残留」
bad = re.findall(r'目标国家(?!家)', text)
# ✅ 对：匹配「标签 + 空值」的组合
bad = re.findall(r'目标国家\s*[｜|:：]\s*(?:（请填写）|___|\s*$)', text)
```

**② 剥标签做「敏感段泄露」检测前，必须先剥 `<style>`**
CSS 里常有说明性注释，例如 `/* 内部段：客户版会隐藏 */`。直接 `re.sub(r'<[^>]+>', '', html)` 会把注释文字算进正文，于是「客户版含『内部』」误报。正确顺序：

```python
body = re.sub(r'<style.*?</style>', '', html, flags=re.S)   # 先剥样式表
body = re.sub(r'<script.*?</script>', '', body, flags=re.S)
body = re.sub(r'<[^>]+>', '', body)                        # 再剥标签
leak = sum(body.count(k) for k in ["内部推进", "tickets.jsonl", "内部版"])
```

> 判据要经得起「正常产物也应该通过」这一关 —— **写完检测先拿一份已知正常的产物跑一遍，报 0 才算判据可用**。
