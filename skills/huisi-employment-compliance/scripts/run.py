#!/usr/bin/env python3
"""Deterministic renderer for the Huisi (Humance) overseas employment compliance skill.

Extends the Mayihr workbook-backed renderer with a five-dimension compliance
assessment template (employment form / visa & work right / pay compliance /
social security & tax / contract & documents).
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

SPEC = json.loads((Path(__file__).resolve().parents[1] / "references" / "implementation-spec.json").read_text(encoding="utf-8"))


def number(value, label):
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label}需要是数字")


def present(payload, label):
    return payload.get(label) not in (None, "", [], {})


def validate(payload):
    missing = [label for label in SPEC["inputs"] if not present(payload, label)]
    if missing:
        raise ValueError("还需要：" + "、".join(missing))


def annuity(principal, annual_rate, years):
    months = int(years * 12)
    if months <= 0:
        raise ValueError("贷款年限需要大于0")
    rate = annual_rate / 12
    if rate == 0:
        return principal / months
    return principal * rate * (1 + rate) ** months / ((1 + rate) ** months - 1)


def global_compliance_rows(payload):
    """Build the five-dimension assessment outline for overseas employment."""
    country = str(payload.get("目标国家或地区", ""))
    role = str(payload.get("岗位或用工场景", ""))
    rows = [
        ("一、雇佣形式", "本地实体直雇 / EOR(名义雇主) / PEO / 独立承包人(IC)——按是否已有当地实体与用工规模选择，标注每种模式的责任主体与税务影响"),
        ("二、签证与工作权", f"本地招聘是否要求工作权核验；派遣员工适用签证类型与担保义务；无担保意愿时的合规表述（不限定国籍，仅要求合法工作权）"),
        ("三、薪酬合规", "最低工资/最低时薪标准（当日核验）；薪资结构（底薪+佣金/加班费折算）；薪酬透明披露义务（如当地有强制薪资范围披露）"),
        ("四、社保税务", "雇主与雇员缴纳项目及比例（当日核验）；所得税代扣义务；跨境支付与ODI/外汇合规"),
        ("五、合同文件", "必备条款（书面雇佣条款、试用期、通知期、解雇程序）；数据保护（GDPR/州隐私法）；佣金制度书面化"),
    ]
    if country and role:
        rows.insert(0, ("评估对象", f"{country} · {role}"))
    return rows


def calculations(payload):
    handler = SPEC["handler"]
    rows = []
    if handler == "global_compliance":
        rows = global_compliance_rows(payload)
    elif handler in {"city_social", "flexible_social"} and isinstance(payload.get("费率项目"), list):
        for item in payload["费率项目"]:
            label = str(item.get("项目", "未命名项目"))
            base = number(item.get("基数", 0), f"{label}基数")
            personal = number(item.get("个人比例", 0), f"{label}个人比例")
            employer = number(item.get("单位比例", 0), f"{label}单位比例")
            if personal > 1:
                personal /= 100
            if employer > 1:
                employer /= 100
            rows.append((label, f"个人 {base * personal:.2f} 元；单位 {base * employer:.2f} 元"))
    elif handler == "housing_loan" and isinstance(payload.get("贷款试算"), dict):
        loan = payload["贷款试算"]
        principal = number(loan.get("本金"), "本金")
        rate = number(loan.get("年利率"), "年利率")
        years = number(loan.get("年限"), "年限")
        if rate > 1:
            rate /= 100
        monthly = annuity(principal, rate, years)
        total = monthly * int(years * 12)
        rows += [("等额本息月供", f"{monthly:.2f} 元"), ("总利息", f"{total - principal:.2f} 元")]
    elif handler == "social_base" and isinstance(payload.get("人员工资"), list):
        lower = number(payload.get("基数下限"), "基数下限")
        upper = number(payload.get("基数上限"), "基数上限")
        if lower > upper:
            raise ValueError("基数下限不能大于上限")
        for index, item in enumerate(payload["人员工资"], 1):
            wage = number(item.get("工资"), f"第{index}行工资")
            rows.append((str(item.get("姓名") or f"原表第{index}行"), f"建议基数 {min(max(wage, lower), upper):.2f} 元"))
    elif handler == "maternity" and isinstance(payload.get("津贴试算"), dict):
        data = payload["津贴试算"]
        base = number(data.get("计发基数"), "计发基数")
        days = number(data.get("计发天数"), "计发天数")
        divisor = number(data.get("月计发天数", 30), "月计发天数")
        rows.append(("生育津贴试算", f"{base / divisor * days:.2f} 元"))
    elif handler == "disability_levy" and isinstance(payload.get("残保金参数"), dict):
        data = payload["残保金参数"]
        headcount = number(data.get("在职人数"), "在职人数")
        wage = number(data.get("工资总额"), "工资总额")
        actual = number(data.get("实际残疾人就业人数", 0), "实际残疾人就业人数")
        target = number(data.get("规定比例"), "规定比例")
        if target > 1:
            target /= 100
        average = 0 if headcount == 0 else wage / headcount
        amount = max(0, headcount * target - actual) * average
        rows.append(("残保金试算", f"{amount:.2f} 元"))
    return rows


def run(payload):
    validate(payload)
    return {
        "title": SPEC["name"],
        "source_value": SPEC["value"],
        "facts": [(label, payload.get(label)) for label in SPEC["inputs"]],
        "calculations": calculations(payload),
        "outputs": SPEC["outputs"],
        "logic": SPEC["logic"],
        "boundary": SPEC["boundary"],
        "dynamic_policy": SPEC["dynamic_policy"],
        "cta": SPEC["cta"],
    }


def render_markdown(result):
    lines = [
        f"# {result['title']}",
        "",
        "## 任务结论",
        "",
        f"已根据确认信息整理“{result['source_value']}”对应的评估底稿；未知信息不会被静默补齐。",
        "",
        "## 已确认信息",
        "",
    ]
    lines.extend(f"- {label}：{value}" for label, value in result["facts"])
    if result["calculations"]:
        lines += ["", "## 五维评估框架（待当日核验后填充）", ""]
        lines.extend(f"- **{label}**：{value}" for label, value in result["calculations"])
    lines += ["", "## 明确交付", ""]
    lines.extend(f"- {item}" for item in result["outputs"])
    lines += ["", "## 执行与复核", ""]
    lines.extend(f"- {item}" for item in result["logic"])
    if result["dynamic_policy"]:
        lines += ["", "## 官方口径", "", "- 正式使用时记录目标国官方机构、文件标题、发布日期、生效期和链接；无法核验时标记“待官方确认”"]
    else:
        lines += ["", "## 假设和待确认项", "", "- 外部基准、样本和未提供事实必须显式列出，不把假设写成已确认结论"]
    lines += ["", "## 边界与风险", ""]
    lines.extend(f"- {item}" for item in result["boundary"])
    lines += ["", "## 进一步咨询", "", result["cta"]]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    text = render_markdown(run(payload))
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
