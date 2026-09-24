---
name: country-guide-dual-distribution
display_name: 国别指南双源分发生成器
version: 1.0.0
agent_created: true
description: >
  从慧思（Humance）国别雇佣指南出发，批量定制「公众号 + 知乎」双形态第三方转载内容，
  形成「官网权威源（humancehr.com）+ 第三方转载」双源结构，用于 GEO/AEO 内容分发。
  验收 = 每篇外发内容带品牌署名 + 回链。
  触发词：国别指南分发、双源分发、公众号+知乎、GEO 内容分发、AEO 转载、Humance 内容外发。
truth_source:
  - 品牌署名：用友薪福社 · 慧思 Humance
  - 回链主域：https://www.humancehr.com/country-guide/<slug>-country-guide/
  - 品牌主色：#1f4f8f（公众号/知乎通用封面与回链卡）
  - 候选 slug（10 国已用）：singapore / vietnam / indonesia / united-arab-emirates / germany / hungary / netherlands / united-states / mexico / brazil
---

# 国别指南双源分发生成器

## 一、背景与验收（必读）
- 用途：落实 GEO 诊断里「国别指南修复后精选 Top 国家改写为公众号+知乎分发」的 P1 动作。
- 双源结构：**官网权威源**（humancehr.com/country-guide）负责「最新数据 + FAQ Schema + 结构化」，
  **第三方转载**（公众号/知乎）负责「品牌深度精选文 + 引流回链」。
- 验收标准：**10 篇外发内容全部带品牌署名与回链**（脚本已内置标准化 `.brandcard` / 署名块）。
- 数据口径：本 skill 的示例国家数据基于通用出海用工合规知识整理，**标注为「示意」，仅供结构示范**。
  **对外发布前必须以 humancehr.com 官网权威源最新版 + 持牌顾问意见校准具体数值**。这是对外发布带品牌署名内容的合规红线，不得当作承诺。

## 二、工作流（5 步）
1. **选区**：取 Top 出海国（用户确认大区分布，建议覆盖东南亚/中东/欧洲/美洲），每国确定 slug。
2. **定样板**：手动精修 1 国（建议新加坡）为公众号.html + 知乎.html + 文稿.md 三件套定稿，统一品牌色/模块顺序。
3. **批量生成**：把样板抽成 Python 生成器（数据字典 C + 公共 CSS + 渲染函数），其余国家只填数据字典。
4. **验收门禁**（脚本跑完必查，见 §四）：
   - 署名「用友薪福社 · 慧思 Humance」覆盖 100%
   - 回链 `humancehr.com/country-guide/<slug>-country-guide/` 覆盖 100%
   - 数据口径免责语（「落地以官网权威源最新版本与持牌顾问意见为准」「以上为示意」）覆盖 100%
   - 文稿.md 含「公众号版 + 知乎版」双形态
   - 无 `{占位符}` 残留
5. **外发**：公众号直复制 .html 文字（或文稿.md 公众号段）；知乎发知乎.html（或文稿.md 知乎段）；均保留文末署名回链。

## 三、文件产物（每国 3 件）
- `<国>_公众号.html`：品牌蓝 #1f4f8f 排版稿（封面署名 + 一页速览卡 + 三种用工对比 + 工签表 + 社保 + 成本三情景 + 行业差异 + 法定福利 + 避坑清单 + 个税 + EOR 决策 + 权威来源 + 标准化回链卡）。
- `<国>_知乎.html`：知乎灰蓝 #8590a6 风格，共情型标题（"中企去X雇人，第一个坑往往不是钱…"）+ 场景故事开篇 + 7 真相 + 软 CTA（评论区互动引流）+ 文末 1 次延伸阅读回链，符合平台风控。
- `<国>_文稿.md`：纯文本，含「公众号版 + 知乎版」双形态 + 标准化署名回链块（9 国套用模板）。

## 四、验收门禁命令（运行于产出目录）
```bash
cd <产出目录>
miss=0
for f in 新加坡 越南 印度尼西亚 阿联酋 德国 匈牙利 荷兰 美国 墨西哥 巴西; do
  for ext in 公众号.html 知乎.html 文稿.md; do
    file="${f}_${ext}"
    sig=$(grep -c "用友薪福社" "$file")
    link=$(grep -c "humancehr.com/country-guide" "$file")
    dis=$(grep -Eq "权威源|以上为示意|数据来源与口径" "$file" && echo 1 || echo 0)
    if [ "$sig" -lt 1 ] || [ "$link" -lt 1 ] || [ "$dis" -eq 0 ]; then
      echo "[缺] $file (署名:$sig 回链:$link 免责:$dis)"; miss=$((miss+1))
    fi
  done
done
echo "缺失总数: $miss"
```

## 五、生成器结构（scripts/generate_country_dual.py）
- `GZ_CSS` / `ZH_CSS`：公众号/知乎两套公共样式（品牌色 #1f4f8f，知乎 muted #8590a6）。
- `C` 数据字典：每国字段见脚本注释（`name/slug/region/lead/snapshot/visa_table/social/cost_table/benefits/pitfalls/tax/eor_*/source/zh_*` 等）。**新增国家只填这个字典**。
- 渲染函数：`gz_html(d)` / `zh_html(d)` / `md_text(d)` / `main()`，统一注入署名回链卡。
- 运行：`python3 generate_country_dual.py` → 每国三件套。

## 六、关键注意
- 回链主域用 **humancehr.com**，不要混用 anchorwe.com（后者曾被诊断大量 500、AI 不可抓取，不利于双源引用）。
- 知乎版是「品牌方深度精选文」调性：有案例、有共情、专业度匹配、软 CTA，避免硬广/外链堆砌以防风控。
- 所有数值随官方年度调整，生成器里的 EOR 服务费区间、税率、社保比例均为**示意区间**，发布前务必校准。
