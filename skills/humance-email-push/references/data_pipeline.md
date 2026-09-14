# 邮件正文生成 · 数据源与流程

## 数据源
| 文件 | 内容 |
|---|---|
| `/tmp/mails_optimized.json` | 72 封优化版：{user, email, cat, urls[], mail, rid} |
| `/tmp/feishu_full.json` | 飞书表快照：行为/分类/触达状态（按 rid） |
| `/tmp/qr_user_records.json` | Strapi 二维码追踪：{uid, url, src}，含登录行为/下载(/pdf)/扫码 |
| `/tmp/final_content.json` | 早期定制内容 |
| User CSV（如 `/Users/yoyo/Downloads/users-2026-08-31T01-59-16-095Z.csv`） | 注册导出，UTF-8，createdAt→北京+8 |

## 生成流程
1. **匹配 email→uid**：用 `build_profile2.py` 把真实邮箱匹配到 Strapi user id，取国家/话题偏好。
2. **定制正文**：`gen_optimized.py` 以"最常看文章 + 国家偏好"为主信号，首段点明具体国家+话题；
   无姓名回退"您好"（勿拼"您好 您好："）；落款 **Alina（慧思）**；加群话术后插扫码图。
3. **邮件主题定制**（按分类）：
   - A 新注册欢迎 → `欢迎加入 Humance，{名}｜出海用工合规资料已备好`
   - B 注册后活跃 → `{名}，您关注的{国}{题}出海资料已整理好`
   - C 核心价值二次触达 → `{名}｜{国}{题}实操全攻略（附落地指南）`
   - 存量真实邮箱 → `Humance 出海速递｜{名}的{国}{题}要点`
   - 国家/话题取不到时回退推荐链接 slug 或 `全球用工合规资料已更新`。
4. **HTML 版**：`gen_per_email.py` 把每封包成完整邮件 HTML（深蓝品牌头 + 正文 + 扫码图 `邮件-联系慧思.jpg` + 固定文尾），
   输出 `outputs/emails/NN_{分类}_{user}.html` + `index.html` 索引。链接转 `<a>` 蓝色可点。

## 历史数据基线（2026-01-01 至 08-31，百度统计）
- 总 PV **66,403**，总 UV **46,903**（⚠️ 旧总结曾误写 47,114，以 46,903 为准）
- 注册累计 166（2026 新增 142），真实邮箱 69（41.6%）
- 扫码 1,158 事件 / 69 人；下载 33（仅扫码会话内 /pdf）；订阅 14
- 访问→注册 0.36%；注册→扫码 41.3%；注册→订阅 8.4%；扫码→下载 47.8%

## 真实发送前的待办
- 图片托管换线上 URL（见 send_checklist.md）
- 阿里云 DirectMail 凭据（环境无）
- `{{unsubscribe_url}}` 发送时替换
