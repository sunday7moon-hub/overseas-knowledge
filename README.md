# Overseas Knowledge 出海知识库

出海HR / Global HR / 跨境用工的知识与技能集合。

---

## Skills 技能索引

| # | Skill | 用途 | 详情 |
|---|-------|------|------|
| 1 | `client-salary-band-report` | **薪资带宽报告**：海外招聘岗位薪资带宽分析报告 | [SKILL.md](skills/client-salary-band-report/SKILL.md) |
| 2 | `xinfushe-overseas-hr` | **薪福社出海客户画像**：用友薪福社出海HR竞品/客户分析 | [SKILL.md](skills/xinfushe-overseas-hr/SKILL.md) |
| 3 | `canvas-design` | **出海知识卡片设计**：高质量视觉设计（海报/插图） | [SKILL.md](skills/canvas-design/SKILL.md) |
| 4 | `company-info-lookup` | **企业信息查询**：城市/省份/大区/行业 | [SKILL.md](skills/company-info-lookup/SKILL.md) |

---

## Quick Start / 快速开始

```bash
git clone https://github.com/sunday7moon-hub/overseas-knowledge.git
```

或直接在线浏览：点击上方任意 `SKILL.md` 链接查看完整说明。

安装：下载 `releases/` 目录下对应 `.zip`，拖入 WorkBuddy 技能面板。

[完整使用指南 →](docs/getting-started.md)

---

## Structure / 目录结构

```
overseas-knowledge/
├── README.md
├── skills/                          # 技能源文件（可直接在线浏览）
│   ├── client-salary-band-report/
│   │   └── SKILL.md
│   ├── xinfushe-overseas-hr/
│   │   ├── SKILL.md
│   │   └── references/              # 参考数据
│   └── canvas-design/
│       ├── SKILL.md
│       └── canvas-fonts/            # 80+字体
│   └── company-info-lookup/
│       ├── SKILL.md
│       └── references/              # 城市→省份→大区映射
├── releases/                        # 下载包
│   ├── client-salary-band-report.zip
│   ├── xinfushe-overseas-hr.zip
│   ├── canvas-design.zip
│   └── company-info-lookup.zip
└── docs/                            # 开发文档
    ├── getting-started.md
    └── conventions.md
```

---

## Adding a New Skill / 添加新技能

1. `skills/<skill-name>/` 下创建 SKILL.md
2. 在 README 索引表中加一行
3. 打包 .zip 放到 `releases/`

详见 [编码规范 →](docs/conventions.md)

---

*Maintained by sunday7moon · 2026*
