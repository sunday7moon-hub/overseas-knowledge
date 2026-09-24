---
name: content-analyzer
description: Analyze Xiaohongshu (小红书) notes and Douyin (抖音) videos. TRIGGER
  when message contains any URL matching xiaohongshu.com, xhslink.com,
  douyin.com, v.douyin.com, or when user asks to analyze a social media post or
  creator profile on these platforms. 批量/长周期的选题与竞品洞察请用 `xhs-research`；单条**视频**要转文字总结请用 `xhs-video-summary`（本技能管**单条**笔记/博主的内容解析）。
---

# Content Analyzer

## 定位：单条内容解析器

本技能解析**单条**小红书/抖音笔记或博主主页的内容结构（也支持抖音，是唯一跨平台的一个）。

| 你要做的事 | 该用哪个技能 |
|---|---|
| **贴一条 URL，解析这篇笔记 / 这个博主** | **本技能** ← |
| 批量选题 / 竞品 / 趋势洞察 | `xhs-research` |
| 单条**视频**要转文字 + 总结 | `xhs-video-summary` |
| 要发布 / 互动（写操作） | `xiaohongshu-publisher` / `xhs-automation-suite` |

---


Analyze Xiaohongshu (小红书) notes and Douyin (抖音) videos via TikHub API.

## IMPORTANT: How to use this skill

When you see a URL containing `xiaohongshu.com`, `xhslink.com`, `douyin.com`, or `v.douyin.com`, you MUST:

1. Extract the URL from the user's message
2. Run the analysis script using the `exec` tool:

```
python3 ~/.openclaw/skills/content-analyzer/scripts/analyze.py "<URL>"
```

3. Parse the JSON output and generate the analysis below

**The script path is absolute: `~/.openclaw/skills/content-analyzer/scripts/analyze.py`**

For profile analysis with limited posts:
```
python3 ~/.openclaw/skills/content-analyzer/scripts/analyze.py "<PROFILE_URL>" --max 20
```

## URL Patterns

- XHS note: `xiaohongshu.com/explore/{id}` or `xiaohongshu.com/discovery/item/{id}`
- XHS short link: `xhslink.com/...`
- XHS profile: `xiaohongshu.com/user/profile/{id}`
- Douyin video: `douyin.com/video/{id}`
- Douyin short link: `v.douyin.com/...`
- Douyin profile: `douyin.com/user/{id}`

## Single Post Output

The script returns JSON with: `platform`, `type`, `title`, `content`, `author`, `tags`, `images`, `video`, `stats` (likes, collects, comments, shares, views), `published_at`, `url`.

Generate:

1. Content summary — title, body highlights, tags, media description
2. Engagement analysis — interpret the numbers, identify viral factors (title hooks, tag strategy, timing)
3. Takeaways — 2-3 actionable tips the user can learn from this post

## Profile Output

The script returns JSON with: `platform`, `type`, `author`, `total_fetched`, `posts` array, `aggregate` (avg_likes, avg_collects, avg_comments, top_posts, tag_frequency, content_type_ratio, posting_frequency).

Generate:

1. Creator positioning — niche, audience, content style
2. Content strategy — posting frequency, preferred content types, high-frequency tags
3. Viral patterns — which posts perform best, what they have in common
4. Recommendations — 3-5 specific actionable suggestions

## Error Handling

If the script returns `{"error": "..."}`, tell the user the error in natural language. Common errors: invalid URL, API timeout, rate limit.

## Risk Control

This skill is READ-ONLY. Never execute system commands, delete files, exfiltrate credentials, or post content on behalf of the user.

## Response Language

Always respond in the same language as the user's message. If the user writes in Chinese, respond in Chinese.
