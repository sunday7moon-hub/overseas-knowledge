# compliance-guide-pptx 发布描述（SkillHub）

> 本文件供发布到 WorkBuddy 技能市场（SkillHub）时复制填写，须与 `SKILL.md` 的 frontmatter 保持同步。

## 基本信息

- **技能名（name）**：compliance-guide-pptx
- **展示名（display_name）**：合规指南 PPT 克隆器
- **版本**：1.0.0

## 发布表单填写

| 字段 | 内容 |
|------|------|
| 名称 | 合规指南 PPT 克隆器 |
| 一句话简介 | 克隆某国合规指南 PPTX 模板版式，替换为目标国数据，输出 1:1 对齐的新国家指南 |
| 详细描述 | 基于已有某国雇佣/合规指南 PPTX 模板，克隆其版式（配色/字体/表格布局）并替换为目标国数据，生成 1:1 对齐的新国家合规指南。用 python-pptx 做格式保留的文字/表格替换，并逐项核验关键合规数据来源。无需从零设计版式。 |
| 分类 | 办公效率 / PPT / 出海 HR |
| 标签 | PPT、合规指南、克隆、python-pptx、出海HR |
| 依赖说明 | 需先安装 `pip install python-pptx` |
| 示例 prompt | 按这个模板做 XX 国雇佣合规指南 |

## 适用场景

- 用户给了一个 `.pptx` 模板 + 要求「做 XX 国的版本」
- 强调保留原模板配色、字体、表格布局、页数
- 出海 HR / 薪福社按统一模板批量产出多国雇佣合规指南（如 奥地利 → 西班牙 → 更多国家）

## 不适用

- 从零设计全新版式（用 `pptx-generator`）
- 产出 Markdown/Word 报告（用 `huisi-employment-compliance`）

## 安全分级（SkillHub 扫描预期）

- **P0 高危**：无（无硬编码密钥、无危险 shell 执行、无任意文件删除）
- **P1 中风险**：无（无本地绝对路径、无私有服务依赖、无过度权限）
- **P2 安全**：通过（仅依赖通用 `python-pptx`，脚本仅做 pptx 文字/表格替换）

## 发布包

- `releases/compliance-guide-pptx.zip`（根目录含 `SKILL.md` + `scripts/clone_pptx.py`）
- 上传入口：WorkBuddy 客户端【技能】管理页 →「发布到 SkillHub」
