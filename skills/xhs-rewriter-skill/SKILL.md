---
name: xhs-rewriter-skill
description: 将任意粗糙、平淡的文本或搬运文章，批量重构清洗为极具网感、高点击率的小红书爆款图文笔记样式。 ⚠️ 本技能与 `slfcys-xhs-expert` 功能重合，**默认请用 `slfcys-xhs-expert`**（人格化创作 + 覆盖本技能的 5 种风格）；本技能仅在需要 `run.py` 规则模板批量洗稿时用。
inputs:
  article:
    type: string
    description: 需要洗稿改写的原始文本或文章内容
    required: true
  style:
    type: string
    description: 改写风格，可选值：网感爆棚、真诚分享、咆哮体、干货清单、深夜emo
    required: false
    default: 网感爆棚
---

# 运行指令

## ⚠️ 与 slfcys-xhs-expert 功能重合

两者都是「小红书文案改写」。**默认请用 `slfcys-xhs-expert`**（真人朋友语气、3 类内容、覆盖面更广）。

本技能仅保留一个独有价值：**`run.py` 规则模板 + 5 种风格参数**（网感爆棚 / 真诚分享 / 咆哮体 / 干货清单 / 深夜emo）的批量洗稿路径。

> 整合计划：把 5 种风格预设挪进 `slfcys-xhs-expert/references/style-presets.md` 后本目录下线。

---

1. 龙虾接收到用户想要“洗稿”、“改写小红书”、“文案重构”的意图时，自动触发此技能。
2. 将用户的原文填入 `article` 参数，选择的风格填入 `style` 参数。
3. 调用 `run.py` 脚本，获取 `processed_prompt`。
4. 核心：大模型接收到 `processed_prompt` 后，**必须严格按照其中的重构规则**真正执行一次深度改写，并将最终的小红书笔记文本（带标题、Emoji、标签）输出给用户。