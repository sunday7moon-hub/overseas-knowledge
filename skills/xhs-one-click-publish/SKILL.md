---
name: xhs-one-click-publish
description: "One-click end-to-end Xiaohongshu (小红书) content production:
  research, writing, image creation, publishing, and validation. Optimized for
  minimal Credit consumption. Triggers when the user asks to create and publish
  XHS content end-to-end, requests 一键发布小红书, wants to research + write + design +
  post a complete note, or explicitly asks for a credit-efficient XHS publishing
  workflow."
agent_created: true
---

# 一键发布小红书 (XHS One-Click Publish)

End-to-end Xiaohongshu note production pipeline optimized for **minimal Credit consumption**. This skill orchestrates five stages — research, writing, image creation, publishing, and validation — with strict credit-efficiency rules at each stage.

## When to Use

- User asks to create AND publish a complete XHS note (research + write + design + post)
- User says 一键发布小红书 or requests a credit-efficient publishing workflow
- User wants to batch-produce XHS content (B2B/出海/EOR topics)
- User has a topic idea and needs a full pipeline from draft to live

## Core Principle: Credit Efficiency

The biggest Credit sinks in XHS automation are, in order:

1. **Multimodal image generation** — each image costs far more than one conversation round; NEVER use for routine notes
2. **Iterative AI rewriting** — multiple rounds of "fix this" / "tweak that" multiply cost; use one-shot prompting
3. **AI-controlled browser interaction** — each step costs one round; delegate to pre-written Playwright scripts

This skill avoids all three. Target: **3-4 rounds total per note** (vs 15-20+ for expert-agent approaches).

---

## Stage 1: Research (调研) — Target: 0-1 rounds

**Goal**: Identify trending topics, competitor angles, and user pain points in the target domain.

**Credit-efficient approach** (preferred):
- Guide the user to manually browse Xiaohongshu for 5-10 minutes in their niche (e.g., EOR/名义雇主/中企出海)
- Ask them to share: a topic idea, 2-3 competitor notes as reference, and their key message
- If the user has no ideas, use **one** `WebSearch` call to find trending angles — do NOT chain multiple searches

**When to use xiaohongshu-mcp `search_feeds`** (1 round cost):
- Only if the user explicitly needs data that requires live XHS access
- One `search_feeds` call with a focused keyword, limit to 5-10 results
- Do NOT chain: search → detail → comment loops; that's a Credit spiral

**Red flag**: Multiple search calls, per-post detail fetches, or "let me analyze trending topics..." monologues. Stop at one round.

---

## Stage 2: Writing (写作) — Target: 1-2 rounds

**Goal**: Produce a complete, publishable note (title + body + topics) in one shot.

**Credit-efficient approach**:
- Construct one comprehensive prompt that includes all constraints
- Output the full note in a single response
- Do NOT enter iterative editing mode (放弃多轮精修的冲动)

**Prompt template** (customize domain per session):

```
Write a Xiaohongshu note about [TOPIC]. Constraints:
- Target audience: [AUDIENCE]
- Tone: professional + practical, no emoji, no 姐妹们, no clickbait
- Structure: hook → pain point → solution → credibility → CTA
- Title: under 20 chars, data/insight-driven
- Body: 3-5 paragraphs with line breaks
- Topics: 3-5 hashtags (mix of broad + niche)
- Length: standard note format, not an article
- Style: subtle brand placement, not hard sell
```

**Anti-patterns to avoid**:
- "Let me revise that..." loops — ship the first output
- Asking "how does this look?" — the user will tell if it's wrong
- Expanding a 200-word note into a 1000-word essay
- Using AI greetings and filler (Great question! / 很高兴为你...)

---

## Stage 3: Image Creation (制图) — Target: 0 Credit rounds

**CRITICAL RULE**: NEVER use multimodal image generation (多模态生图) for routine XHS notes. It is the single largest Credit drain.

**Embedded approach** (zero Credit: build images with code):

**Option A: HTML/CSS cover image** (preferred for B2B/professional topics)
- Create a standalone HTML file styled like a XHS cover
- Clean typography, brand colors, data-driven headline
- Use `preview_url` to show a live render
- User takes a screenshot or the script can use headless browser capture

**Option B: Python Pillow composition** (for templated repeat use)
- Use a predefined layout template
- Overlay text on background image/solid color
- Output JPG/PNG directly

**Option C: Canva/Figma manual** (user handles, AI assists with copy suggestions)
- Provide text copy and layout suggestion
- User creates in their preferred design tool

**What NOT to do**:
- Do NOT call 多模态内容生成 or image_gen for XHS cover images
- Do NOT generate AI illustrations for supporting images
- Reserve multimodal generation ONLY if the user explicitly requests unique AI artwork and acknowledges the Credit cost

**Supporting images** (配图):
- Screenshots of data/charts (generated via code, not AI)
- Screenshots of product/website (user provides or browser capture)
- Text-over-gradient info cards (HTML → screenshot)

---

## Stage 4: Publishing (发布) — Target: 1 round

**Use the existing `xiaohongshu-publisher` skill.**

When all content (title, body, topics, image paths) is ready:

1. Load the `xiaohongshu-publisher` skill
2. Prepare a JSON config following `assets/note_config_example.json` format:
   ```json
   {
     "title": "...",
     "content": "...",
     "images": ["/absolute/path/cover.jpg", "/absolute/path/img2.jpg"],
     "topics": ["出海", "EOR"]
   }
   ```
3. Execute the Playwright script to publish
4. The script handles: session reuse, tab switching, image upload, content filling, topic tags, publish button

### Important Lessons (2026-06-25 verified)

**Publish button is inside `#shadow-root (closed)`** — 标准 DOM 查询（`innerText`、`textContent`、`querySelectorAll`）都扫不到"发布"这两个字。
脚本内部使用底部坐标网格扫描（viewport 底部靠右区域）绕开这个问题。

**Save draft first** — 脚本会在发布前自动按 `Cmd+S` 保存草稿。即使发布按钮点击失败，内容不会丢失。
**Sidebar publish button DO NOT click** — 侧栏 `x < 200` 的"发布笔记"按钮点后会跳回发布首页，丢弃当前编辑内容。

**Publishing checklist** before execution:
- [ ] All image paths are absolute paths to existing files
- [ ] Title is under 20 characters
- [ ] Body is under 1000 characters
- [ ] Topics use # format (script auto-prepends `#`)
- [ ] At least one prior manual QR login has been completed (session persists)

---

## Stage 5: Validation (校验) — Target: 0 additional rounds

**Goal**: Verify text quality, image quality, and execution completeness. This stage is embedded in Stage 4's round — it does NOT consume extra Credit.

### Pre-Publish Checks (图文质量校验)

Run these checks BEFORE clicking the publish button. Output a checklist with PASS/FAIL for each item.

#### Text Quality

| Check Item | Rule | Fail Action |
|-----------|------|-------------|
| Title length | ≤20 characters (XHS hard limit) | Truncate or rewrite title |
| Title substance | Not generic clickbait ("绝了"/"必看"/"救命") | Replace with data/insight-driven title |
| Title emoji | ≤2 emoji, or zero for B2B/professional notes | Strip excess emoji |
| Body length | ≤1000 characters (XHS hard limit) | Trim trailing paragraphs, keep core message |
| Body structure | Has hook + pain point + solution + CTA | Restructure; fill missing sections |
| Paragraph count | 3-6 paragraphs with visible breaks | Merge short fragments or split walls of text |
| Topic count | 3-5 topics (XHS allows more but 3-5 is optimal) | Add or remove topics |
| Topic mix | At least 1 broad topic + 1 niche/long-tail topic | Re-balance topic selection |
| Banned words | No absolute claims (最/第一/唯一), no medical claims, no financial promises | Replace with softened language; mark specific terms |
| AI flavor | No "首先...其次...最后" pattern, no "值得注意的是", no "总而言之" | Rewrite in natural XHS conversational style |
| Call to action | Has one soft CTA (question/discussion prompt) | Add engagement hook at end |
| Brand mention | Brand appears exactly once, subtle placement | Adjust frequency and position |

#### Image Quality

| Check Item | Rule | Fail Action |
|-----------|------|-------------|
| Image count | 1 cover + 1-8 supporting images | Warn if fewer than 2 (low engagement risk) |
| Cover format | JPG or PNG | Convert if needed |
| Cover resolution | ≥1080×1440 (3:4 portrait) | Regenerate at correct size |
| Cover file size | ≤20MB (XHS limit) | Compress if exceeded |
| Supporting image format | JPG or PNG, NOT WebP/AVIF | Convert format |
| Supporting image resolution | ≥800px on shortest side | Regenerate or skip |
| File paths | All paths are absolute and files exist | Fix paths or regenerate missing files |
| Visual consistency | Cover and supporting images share style/colors | Flag mismatch for user review |

#### Metadata

| Check Item | Rule | Fail Action |
|-----------|------|-------------|
| Note type | 图文笔记 (not accidentally video mode) | Verify tab switch in publish script |
| Visibility | Intended visibility setting (public/private) | Confirm with user |

### Post-Publish Checks (执行完整度校验)

After the Playwright publish script completes, verify from its output:

| Check Item | Verification Method | Fail Action |
|-----------|-------------------|-------------|
| Tab switch success | Script output shows `hasImageInput: true` | Re-run publish with tab-switch retry |
| Images uploaded | Script shows correct image count uploaded | Check file paths; re-upload |
| Title filled | Debug screenshot shows title visible | Check contenteditable handling |
| Body filled | Debug screenshot shows body text | Check paragraph typing |
| Topics applied | Debug screenshot shows #topics present | Re-type topics |
| Publish clicked | Debug-result screenshot shows success page or note page | Check publish button strategy |
| Note visible | URL redirects to note detail page (not draft) | If stuck on draft, trigger publish again |
| No error popup | No red error toast in screenshot | Read error text; fix and retry |

### Validation Output Format

After completing all checks, output a **single validation report** table summarizing results:

```
## 校验报告

### 图文质量
| 项目 | 状态 | 详情 |
|------|------|------|
| 标题长度 | PASS | 18/20字 |
| 标题质量 | PASS | 数据驱动型标题 |
| 正文长度 | PASS | 856/1000字 |
| 正文结构 | PASS | 痛点→方案→CTA完整 |
| 话题数量 | PASS | 4个话题 |
| 话题搭配 | PASS | 宽泛+长尾混合 |
| 违禁词 | PASS | 未检测到违规词 |
| AI味 | PASS | 口语化表达 |
| CTA | PASS | 结尾有互动提问 |
| 品牌露出 | PASS | 1处自然提及 |
| 封面格式 | PASS | JPG, 1080×1440 |
| 配图数量 | PASS | 封面+4张配图 |
| 图片路径 | PASS | 全部绝对路径，文件存在 |

### 执行完整度
| 项目 | 状态 | 详情 |
|------|------|------|
| Tab切换 | PASS | 图文模式确认 |
| 图片上传 | PASS | 5/5张上传成功 |
| 标题填充 | PASS | 标题已填充 |
| 正文填充 | PASS | 正文已填充 |
| 话题标签 | PASS | 4个话题已添加 |
| 发布点击 | PASS | 发布按钮已触发 |
| 发布结果 | VERIFY | 需用户确认笔记可见 |
```

**If any item is FAIL**: stop before publish. Report the failure to the user with specific fix instructions. Do NOT proceed to publish with known quality issues.

**If `发布结果` is VERIFY**: remind the user to check the published note on their XHS app/creator dashboard within 5 minutes.

---

## Full Pipeline Summary

```
┌───────────┬──────────────┬─────────────────────┐
│  Stage    │  Credit Cost │  Method              │
├───────────┼──────────────┼─────────────────────┤
│ Research  │  0-1 rounds  │ Manual browse or     │
│           │              │ 1 WebSearch/mcp call │
│ Writing   │  1-2 rounds  │ One-shot prompt      │
│ Images    │  0 rounds    │ HTML/CSS or Pillow   │
│ Publish   │  1 round*    │ Playwright script    │
│ Validate  │  0 rounds**  │ Embedded checklist   │
├───────────┼──────────────┼─────────────────────┤
│ TOTAL     │  3-4 rounds  │ vs 15-20+ for expert │
│           │              │ agent approaches     │
└───────────┴──────────────┴─────────────────────┘
```

\* The 1 round for publishing is the conversation round to call the script; the script itself runs locally at zero Credit.

\*\* Validation is embedded in Stage 4's round — pre-publish checks run before the script, post-publish checks run after. Zero additional rounds.

## Error Recovery

| Symptom | Likely Cause | Action |
|---------|-------------|--------|
| Script crashes with "Non-multiple file input" | Tab didn't switch to image mode | Re-run with `xiaohongshu-publisher` skill; it has built-in retry |
| Title empty in published note | Single contenteditable layout detected incorrectly | Skill handles edCount===1 case automatically |
| Login timeout | Session expired, QR login needed | Re-run in non-headless mode for manual QR scan |
| Image upload fails | Wrong file path or format | Verify absolute paths and image file existence |
| Validation: title exceeds 20 chars | AI output exceeded XHS limit | Truncate to first complete sentence under 20 chars |
| Validation: body exceeds 1000 chars | Too much detail in one-shot output | Trim trailing paragraphs; prioritize hook + CTA |
| Validation: banned words detected | Marketing language slipped in | Replace 最/第一/唯一 with "值得关注"/"高效"/ etc. |
| Validation: AI flavor detected | Template-like transitions (首先其次最后) | Rewrite with natural conversational flow |
| Validation: 发布结果 = draft | Publish button clicked but note saved as draft | Popup likely blocked click; press Escape 3x, click publish again |
| Validation: 发布结果 = unknown | Debug screenshot unclear or script exited early | Check debug-before-publish.png and debug-after-publish.png |
| **Script says "手动确认" but note not published** | **None of publish strategies worked** | Check debug screenshots; bottom coordinate scan (Strategy 5) is most reliable |
| **Script clicks but navigates to publish home (content lost)** | Sidebar "发布笔记" button was clicked instead of bottom "发布" | Script now filters sidebar (x<200); **always save draft first** |
| **net::ERR_ABORTED on page load** | Stale Singleton lock files from previous crash | Script now cleans SingletonCookie/SingletonSocket/SingletonLock |
| **Draft box is empty after failed publish** | Sidebar click navigated away → content discarded | Already fixed: save draft (Cmd+S) before any publish attempt |

## Dependencies

- **xiaohongshu-publisher skill** (must be installed): handles browser automation and publishing
- **Playwright**: `npm install playwright` (node_modules required for publish script)
- **Chrome browser**: installed on the system
- **Pillow** (optional, for Python image composition): `pip install Pillow`
- **xiaohongshu-mcp** (optional, for live XHS search): `brew install xiaohongshu-mcp` or download from GitHub
