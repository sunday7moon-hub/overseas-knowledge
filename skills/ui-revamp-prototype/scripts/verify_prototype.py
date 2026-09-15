#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_prototype.py —— UI 改造原型的静态校验器

为什么需要它：
  无头 Chrome 在本机沙箱内无法启动（截图不可用），因此原型的质量必须靠
  静态检查兜底。它能抓住 90% 的手误：漏定义的 CSS 类、写错的 CSS 变量、
  内联 style 语法错、把诊断用的反面文案误写进改造后的界面、以及凭据泄露。

用法：
    python3 verify_prototype.py <原型.html>
    python3 verify_prototype.py <原型.html> --watch 立即注册 请注册 提交信息
    python3 verify_prototype.py <原型.html> --json

退出码：0 = 通过；1 = 存在问题（需修复）
"""
import argparse
import json
import os
import re
import sys

VOID = {"br", "img", "input", "meta", "link", "hr", "source", "area",
        "base", "col", "embed", "param", "track", "wbr"}

# 视为「说明 / 标注」的容器类名：这些区域里的文案是给设计师看的，不是界面文案
ANNOTATION_CLASSES = [
    "doc-head", "principle", "kpis", "goal", "lead", "quote", "copy-line",
    "notes", "note", "diag-list", "diag-col", "warn-box", "ok-box",
    "danger-box", "sec-h", "badges",
]

SENSITIVE_PATTERNS = [
    ("百度统计 token", r"12[01]\.[A-Za-z0-9_\-]{25,}"),
    ("GitHub token", r"(?:ghp_|gho_|github_pat_)[A-Za-z0-9_]{20,}"),
    ("飞书 table id", r"\btbl[A-Za-z0-9]{10,}\b"),
    # 飞书 base token 无固定前缀，靠上下文识别；不要用「长字母数字串」形态匹配，
    # 否则 Ardot 的 data-page-node-id / 构建 hash 会大面积误报
    ("飞书 base token", r"(?i)base[_\-]?token[\"'=:\s]+([A-Za-z0-9]{20,})"),
    ("飞书 open/chat id", r"\b(?:ou_|oc_|on_)[a-f0-9]{20,}\b"),
    ("内部邮箱", r"[\w.\-]+@(?:xinfushe|yonyou)\.com"),
    ("疑似密钥赋值", r"(?i)\b(?:api[_-]?key|secret|passwd|password|access[_-]?token)\b\s*[:=]\s*[\"']?[A-Za-z0-9_\-\.]{16,}"),
]


def strip_code_blocks(html):
    """去掉 script / style 内容与 HTML 注释"""
    out = re.sub(r"<script\b.*?</script>", "", html, flags=re.S | re.I)
    out = re.sub(r"<style\b.*?</style>", "", out, flags=re.S | re.I)
    out = re.sub(r"<!--.*?-->", "", out, flags=re.S)
    return out


def cut_blocks(text, class_names):
    """按标签深度精确切除 class 命中 class_names 的整块（含嵌套）"""
    pat = re.compile(
        r"<(div|ul|section|aside|figure)\s+class=\"[^\"]*\b(?:"
        + "|".join(re.escape(c) for c in class_names)
        + r")\b[^\"]*\""
    )
    guard = 0
    while True:
        guard += 1
        if guard > 500:
            break
        m = pat.search(text)
        if not m:
            break
        tag = m.group(1)
        try:
            i = text.index(">", m.end())
        except ValueError:
            break
        depth, j = 1, i + 1
        open_re = re.compile(r"<" + tag + r"\b", re.I)
        close_re = re.compile(r"</" + tag + r"\s*>", re.I)
        while j < len(text) and depth > 0:
            no, nc = open_re.search(text, j), close_re.search(text, j)
            if nc is None:
                j = len(text)
                break
            if no is not None and no.start() < nc.start():
                depth += 1
                j = no.end()
            else:
                depth -= 1
                j = nc.end()
        text = text[:m.start()] + text[j:]
    return text


def check_tag_balance(body):
    tags = re.findall(r"<(/?)([a-zA-Z][a-zA-Z0-9]*)((?:\"[^\"]*\"|'[^']*'|[^>\"'])*?)(/?)>", body)
    stack, errs = [], []
    for close, name, _attrs, selfc in tags:
        n = name.lower()
        if n in VOID or selfc:
            continue
        if not close:
            stack.append(n)
        else:
            if stack and stack[-1] == n:
                stack.pop()
            elif n in stack:
                while stack and stack[-1] != n:
                    errs.append("未闭合 <%s>" % stack.pop())
                if stack:
                    stack.pop()
            else:
                errs.append("多余闭合 </%s>" % n)
    for s in stack:
        errs.append("未闭合 <%s>" % s)
    return errs


def check_css_classes(css, body):
    defined = set(re.findall(r"\.([a-zA-Z][a-zA-Z0-9_-]*)", css))
    used = set()
    for m in re.findall(r'class="([^"]+)"', body):
        used.update(m.split())
    return sorted(used - defined), sorted(defined - used)


def check_css_vars(full_text, css):
    defined = set(re.findall(r"(--[a-zA-Z0-9-]+)\s*:", css))
    used = set(re.findall(r"var\((--[a-zA-Z0-9-]+)", full_text))
    return sorted(used - defined)


def check_inline_styles(body):
    problems = []
    inline = re.findall(r'style="([^"]*)"', body)
    for s in inline:
        for decl in s.split(";"):
            d = decl.strip()
            if not d:
                continue
            if ":" not in d:
                problems.append("缺冒号: %s" % d)
                continue
            k, v = d.split(":", 1)
            k, v = k.strip(), v.strip()
            if not re.fullmatch(r"[a-zA-Z-]+", k):
                problems.append("属性名异常: %s" % d)
            elif not v:
                problems.append("空值: %s" % d)
            elif v.count("(") != v.count(")"):
                problems.append("括号不配对: %s" % d)
    return len(inline), problems


def check_sensitive(full_text):
    hits = []
    for label, pat in SENSITIVE_PATTERNS:
        for m in re.finditer(pat, full_text):
            seg = m.group(0)
            masked = seg[:6] + "…" + seg[-4:] if len(seg) > 12 else seg[:4] + "…"
            hits.append((label, masked))
    return hits


def analyze_screens(full_text, body, watch_words):
    """把每个改造后屏切成「UI 区」与「标注区」，统计 watch_words 的分布。

    只检查 id 形如 s01..s99 的屏（s00 是现状复刻，本就该出现反面文案）。
    """
    results = []
    parts = re.split(r'<section\s+class="screen"', full_text)
    for part in parts[1:]:
        m = re.match(r'\s*id="([^"]+)"', part)
        if not m:
            continue
        sid = m.group(1)
        if not re.fullmatch(r"s\d{2}", sid) or sid == "s00":
            continue
        screen = part.split("</section>")[0]
        ui = cut_blocks(screen, ANNOTATION_CLASSES)
        anno = screen
        row = {"id": sid, "ui_hits": {}, "anno_hits": {}}
        for w in watch_words:
            ui_n = len(re.findall(re.escape(w), ui))
            all_n = len(re.findall(re.escape(w), anno))
            row["ui_hits"][w] = ui_n
            row["anno_hits"][w] = all_n - ui_n
        results.append(row)
    return results


def main():
    ap = argparse.ArgumentParser(description="UI 改造原型静态校验")
    ap.add_argument("file", help="原型 HTML 路径")
    ap.add_argument("--watch", nargs="*", default=[],
                    help="需要在「改造后 UI 区」中确认不出现的词，例如反面文案")
    ap.add_argument("--json", action="store_true", help="以 JSON 输出")
    args = ap.parse_args()

    if not os.path.isfile(args.file):
        print("❌ 文件不存在: %s" % args.file)
        return 1

    raw = open(args.file, encoding="utf-8").read()
    body = strip_code_blocks(raw)
    m = re.search(r"<style[^>]*>(.*?)</style>", raw, re.S | re.I)
    css = m.group(1) if m else ""

    report = {"file": args.file, "size": len(raw.encode("utf-8")),
              "lines": raw.count("\n") + 1, "problems": []}

    # 1 标签配对
    tag_errs = check_tag_balance(body)
    report["tag_errors"] = tag_errs

    # 2 CSS 类
    missing_cls, unused_cls = check_css_classes(css, body)
    report["undefined_classes"] = missing_cls
    report["unused_classes"] = unused_cls

    # 3 CSS 变量
    bad_vars = check_css_vars(raw, css)
    report["undefined_css_vars"] = bad_vars

    # 4 内联 style
    n_inline, style_problems = check_inline_styles(body)
    report["inline_style_count"] = n_inline
    report["inline_style_problems"] = style_problems

    # 5 敏感信息
    sensitive = check_sensitive(raw)
    report["sensitive"] = sensitive

    # 6 UI 区 / 标注区关键词分布
    report["watch"] = analyze_screens(raw, body, args.watch) if args.watch else []

    # 7 屏幕清单
    report["screens"] = re.findall(r'<section\s+class="screen"\s+id="([^"]+)"', raw)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        ok = "✅"
        print("=" * 66)
        print("UI 改造原型 · 静态校验")
        print("=" * 66)
        print("文件: %s" % os.path.basename(args.file))
        print("大小: %s bytes ｜ %s 行 ｜ %d 屏"
              % (report["size"], report["lines"], len(report["screens"])))
        print("\n[1] 标签配对      %s" % (ok + " 正常" if not tag_errs
                                        else "❌ " + "; ".join(tag_errs[:6])))
        print("[2] CSS 类定义    %s"
              % (ok + " 无缺失" if not missing_cls
                 else "❌ 未定义却被使用: " + ", ".join(missing_cls)))
        if unused_cls:
            print("                    （定义未使用: %s，可忽略）" % ", ".join(unused_cls))
        print("[3] CSS 变量      %s"
              % (ok + " 引用有效" if not bad_vars
                 else "❌ 未定义却被引用: " + ", ".join(bad_vars)))
        print("[4] 内联 style    %s  (%d 块)"
              % (ok + " 语法正确" if not style_problems
                 else "❌ " + "; ".join(style_problems[:6]), n_inline))
        print("[5] 敏感信息      %s"
              % (ok + " 未命中" if not sensitive
                 else "❌ " + "; ".join("%s(%s)" % s for s in sensitive[:6])))

        if args.watch:
            print("\n[6] 改造后 UI 区关键词分布（UI 区应全部为 0）")
            for row in report["watch"]:
                parts = []
                for w, n in row["ui_hits"].items():
                    parts.append("%s UI=%d/标注=%d" % (w, n, row["anno_hits"][w]))
                flag = ok if all(v == 0 for v in row["ui_hits"].values()) else "⚠️ "
                print("    %s #%-5s %s" % (flag, row["id"], " ｜ ".join(parts)))

        print("\n[7] 屏幕清单")
        print("    " + " ".join("#" + s for s in report["screens"]))

        # 汇总
        fatal = bool(tag_errs or missing_cls or bad_vars or style_problems or sensitive)
        watch_fail = any(v for row in report["watch"] for v in row["ui_hits"].values())
        print("\n" + "=" * 66)
        if fatal:
            print("❌ 存在必须修复的问题，请处理后重跑（退出码 1）")
        elif watch_fail:
            print("⚠️  结构与样式正常，但改造后 UI 区出现了反面文案：")
            print("    若是有意展示（如「已删除该入口」），请确认；否则移入标注区。")
        else:
            print("✅ 全部通过（退出码 0）")
        print("=" * 66)

    fatal = bool(report["tag_errors"] or report["undefined_classes"]
                 or report["undefined_css_vars"] or report["inline_style_problems"]
                 or report["sensitive"])
    watch_fail = any(v for row in report["watch"] for v in row["ui_hits"].values())
    return 1 if (fatal or watch_fail) else 0


if __name__ == "__main__":
    sys.exit(main())
