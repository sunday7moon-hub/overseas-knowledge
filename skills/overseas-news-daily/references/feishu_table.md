# 飞书多维表格「出海资讯日报」字段说明

## 基础信息
- base_token: `JZMebcGfOa7V0WsGwQUcbHT9nag`
- table_id: `tblmCPXSVc0WQ2jz`
- lark-cli: `/Users/yoyo/.workbuddy/binaries/node/cli-connector-packages/bin/lark-cli`

## 字段列表

| 字段名 | 字段ID | 类型 | 必填 | 说明 |
|--------|--------|------|:----:|------|
| 标题 | fldHdYu9GT | 文本(主字段) | ✅ | 15-25字 |
| 正文 | fldtak7xc8 | 文本 | ✅ | 完整内容，不限字数 |
| 全文 | flddj3HzWB | 文本 | ✅ | 与正文一致 |
| 分类 | fldI5oJa2o | 单选 | ✅ | 全球动态/法规更新/风险预警 |
| 来源 | fldwqtYURC | 文本 | ✅ | 新闻来源 |
| 原文链接 | fldcmNIZ5K | 文本 | ✅ | 来源链接 |
| 摘要 | fldm6bNKiM | 文本 | ✅ | 40字内一句话 |
| 资讯ID | fldrYDqYnw | 文本 | ✅ | YYYYMMDDNN（10位数字） |
| 更新时间 | fld10g72rk | 日期时间 | ✅ | YYYY-MM-DD HH:mm:ss |
| 标签 | fldnW8GSX1 | 多选 | ✅ | 地理标签+主题标签 |
| 时效标签 | fldEmoTpNJ | 单选 | ✅ | 14天/30天/3个月/半年 |
| 地区优先级 | _(需新增)_ | 单选 | ✅ | 高/中/低 |
| 推送状态 | flddO7rBcG | 单选 | ✅ | 待推送/已推送 |
| 排版状态 | fldO08nKZo | 单选 | 可选 | 待排版/已排版 |
| 排版的html | fldakWU7e2 | 文本 | 可选 | 排版后的HTML |
| 推送时间 | fld38dmB7i | 文本 | 可选 | 推送时间 |
| 是否精选 | fldTcUkNsI | 复选框 | 可选 | 入选每日10条标记 |

## 标签选项（多选字段 fldnW8GSX1）

### 地理/行业标签（29个）
东南亚, 北美, 欧洲, 中东, EOR, 关税, 合规, 跨境电商, AI, 出海趋势, 全球化, 法规更新, 风险预警, 并购, 非洲, 欧盟, 拉美, 南美, 亚太, 出口管制, 澳洲

### 主题标签（7个，平级）
劳动法规, 薪酬支付, 雇主成本, 个税, 福利, 休假政策, 海外资讯

## 分类选项（单选 fldI5oJa2o）
全球动态, 法规更新, 风险预警

## 时效标签选项（单选 fldEmoTpNJ）
14天, 30天, 3个月, 半年
