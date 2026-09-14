---
name: employee-handbook-generator
description: 生成完整、可定制的员工手册（Employee Handbook），覆盖雇佣政策、薪酬福利、休假、远程办公、行为准则、绩效发展、IT 安全、离职与合规共 11 大章节，输出手册正文 + 政策速查一页纸 + 签收表 + 修订记录模板。当用户需要「写员工手册」「生成员工手册」「Employee Handbook」「海外子公司员工手册模板」时使用。支持 --startup / --enterprise / --remote-first / --us / --uk / --eu / --tech 定制参数。
---

# Employee Handbook Generator

Build a complete, customized employee handbook for your company. Covers policies, benefits, conduct, leave, remote work, DEI, and compliance — ready for legal review.

## How It Works

When activated, the agent asks for:
1. **Company name and industry**
2. **Headcount and locations** (multi-state/country if applicable)
3. **Work model** (remote, hybrid, office)
4. **Key policies to include** (or use the full default set)

Then generates a structured handbook with these sections:

## Handbook Sections

### 1. Welcome & Company Overview
- Mission, values, and culture statement
- Org structure overview
- At-will employment disclaimer (US) or contract basis (UK/EU)

### 2. Employment Policies
- Equal opportunity and anti-discrimination
- Background checks and eligibility verification
- Employment classifications (full-time, part-time, contractor)
- Probationary periods

### 3. Compensation & Benefits
- Pay schedule and overtime policy
- Health insurance, 401(k)/pension, equity
- Professional development budget
- Employee referral bonuses

### 4. Time Off & Leave
- PTO/vacation policy (accrual vs unlimited)
- Sick leave and mental health days
- Parental leave (maternity, paternity, adoption)
- Bereavement, jury duty, voting leave
- Sabbatical policy (if applicable)

### 5. Work Environment
- Remote work policy and expectations
- Hybrid schedule guidelines
- Office conduct and dress code
- Equipment and stipend policy

### 6. Code of Conduct
- Professional behavior standards
- Anti-harassment and anti-bullying
- Conflict of interest disclosure
- Social media policy
- Confidentiality and NDA requirements

### 7. Performance & Growth
- Review cadence (quarterly, annual)
- Goal-setting framework (OKRs, KPIs)
- Promotion criteria and career ladders
- Performance improvement plans (PIPs)

### 8. IT & Security
- Acceptable use of company devices
- Password and MFA requirements
- Data handling and classification
- BYOD policy
- Incident reporting procedures

### 9. Health & Safety
- Workplace safety standards (OSHA/HSE)
- Emergency procedures
- Workers' compensation
- Ergonomic assessments

### 10. Separation & Offboarding
- Resignation procedures and notice periods
- Termination process
- Final pay and benefits continuation (COBRA/equivalent)
- Return of company property
- Exit interview process

### 11. Compliance & Legal
- Jurisdiction-specific requirements
- Acknowledgment and signature page
- Amendment and update procedures
- Whistleblower protection

## Output Format

The agent produces:
- **Full handbook** in markdown (convert to PDF/DOCX as needed)
- **Policy summary one-pager** for quick reference
- **Acknowledgment form** for employee signatures
- **Update log template** for tracking revisions

## Customization Flags

Tell the agent any of these to adjust output:
- `--startup` → Lighter policies, growth-stage language
- `--enterprise` → Full compliance, multi-jurisdiction
- `--remote-first` → Emphasize async, home office, time zones
- `--us` / `--uk` / `--eu` → Jurisdiction-specific legal language
- `--tech` → Add IP assignment, open source policy, on-call

## Why This Matters

- The average employee handbook takes 40-80 hours to write from scratch
- Legal review of a handbook runs $3,000-$8,000
- 60% of small businesses operate without a formal handbook
- Missing policies create liability exposure in wrongful termination suits

---

## 出海场景补充说明

生成**非中国境内**主体的员工手册时，须注意：

| 项 | 说明 |
|------|------|
| 强制条款 | 各国要求不同（如阿联酋需备阿拉伯语版本、欧盟需含 GDPR 条款），生成后**必须经当地律师审核** |
| 语言版本 | 多国主体建议出中英双语，以**当地语言版本为准** |
| 与劳动法对齐 | 手册条款不得低于当地法定标准；冲突时以法律为准 |
| 备案与签收 | 部分国家（如印尼、越南）要求手册在当地劳动部门备案，须留签收痕迹 |

本技能产出的是**初稿模板**，用于压缩 40–80 小时的起草工作量，**不可替代法律审查**。

> 归属：L2 领域方法（出海/跨境通用，换同行也能用）。
