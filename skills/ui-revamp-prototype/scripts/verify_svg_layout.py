#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_svg_layout.py —— 单文件原型里手绘 SVG 图的布局自检

为什么需要它：
  交互图/流程图是用手算坐标写出来的 SVG，肉眼很难看出坐标错在哪，
  于是靠几何计算兜底。它能抓到三类会让图"看起来画坏了"的问题：

  （补充：2026-09-17 起本机已可经 render_shot.py 真实渲染截图，
   但手绘 SVG 的坐标问题仍以本脚本的几何校验为准 —— 截图能看出"歪了"，
   看不出"哪个节点压住了哪个节点"。）

    ① 节点框互相重叠（手算坐标最容易错的地方）
    ② 箭头落点不在任何节点边缘上（线飘在空中 / 插进框里）
    ③ 文本标签写到画布外（被裁掉）

用法：
    python3 verify_svg_layout.py <原型.html>
    python3 verify_svg_layout.py <原型.html> --tol 8      # 落点容差
    python3 verify_svg_layout.py <原型.html> --json

退出码：0 = 通过；1 = 存在问题
"""
import argparse
import json
import re
import sys

# 视为"节点"的 class：带底色的框体
NODE_CLASSES = ("nd", "nd-b", "nd-e", "nd-k", "nd-a", "nd-d", "hd")


def parse_svgs(html):
    """切出每个 <svg> 块（含 aria-label 作为图名）"""
    out = []
    for m in re.finditer(r'<svg[^>]*aria-label="([^"]*)"[^>]*>(.*?)</svg>', html, re.S):
        vb = re.search(r'viewBox="([\d.\s-]+)"', m.group(0))
        box = [float(x) for x in vb.group(1).split()] if vb else [0, 0, 9999, 9999]
        out.append({"name": m.group(1), "body": m.group(2), "viewbox": box,
                    "width": box[2], "height": box[3]})
    return out


def nodes(body):
    """节点框：rect + polygon（菱形判断框）"""
    out = []
    for m in re.finditer(r'<rect\s+class="([^"]+)"\s+x="([\d.\-]+)"\s+y="([\d.\-]+)"'
                         r'\s+width="([\d.\-]+)"\s+height="([\d.\-]+)"', body):
        cls = m.group(1)
        if not any(c in cls.split() for c in NODE_CLASSES):
            continue
        x, y, w, h = (float(m.group(i)) for i in (2, 3, 4, 5))
        out.append({"cls": cls, "x": x, "y": y, "w": w, "h": h,
                    "r": x + w, "b": y + h, "kind": "rect"})
    for m in re.finditer(r'<polygon\s+class="([^"]+)"\s+points="([^"]+)"', body):
        v = [float(x) for x in re.findall(r"-?\d+\.?\d*", m.group(2))]
        xs, ys = v[0::2], v[1::2]
        if not xs:
            continue
        x, y = min(xs), min(ys)
        out.append({"cls": m.group(1), "x": x, "y": y,
                    "w": max(xs) - x, "h": max(ys) - y,
                    "r": max(xs), "b": max(ys), "kind": "polygon"})
    return out


def lifelines(body):
    """时序图的生命线：竖直线段，箭头允许落在其上"""
    out = []
    for m in re.finditer(r'<path\s+class="tl"\s+d="M([\d.\-]+),([\d.\-]+)\s+V([\d.\-]+)"', body):
        x, y1, y2 = (float(m.group(i)) for i in (1, 2, 3))
        out.append({"x": x, "y1": min(y1, y2), "y2": max(y1, y2)})
    return out


def overlaps(ns):
    """返回互相部分重叠的节点对；完全包含视为有意的容器，不算错"""
    bad = []
    for i in range(len(ns)):
        for j in range(i + 1, len(ns)):
            a, b = ns[i], ns[j]
            ox = min(a["r"], b["r"]) - max(a["x"], b["x"])
            oy = min(a["b"], b["b"]) - max(a["y"], b["y"])
            if ox <= 0 or oy <= 0:
                continue
            contains = (a["x"] <= b["x"] and a["y"] <= b["y"]
                        and a["r"] >= b["r"] and a["b"] >= b["b"]) or \
                       (b["x"] <= a["x"] and b["y"] <= a["y"]
                        and b["r"] >= a["r"] and b["b"] >= a["b"])
            if contains:
                continue
            bad.append((a, b, ox, oy))
    return bad


def path_ends(d):
    """按 SVG 路径语义求 (起点, 终点)。

    ⚠️ 关键坑：`H952` 只改 x、y 沿用当前点；`V120` 只改 y。
    早期版本直接取最后两个数字当 (x,y)，会把 `H952` 的终点算成 (y, x)，
    导致所有「先 V 再 H」的箭头被误报为悬空 —— 这类误报最危险，
    会让人开始怀疑本来正确的图。
    """
    x = y = 0.0
    first = None
    for cmd, argstr in re.findall(r"([A-Za-z])([^A-Za-z]*)", d):
        n = [float(v) for v in re.findall(r"-?\d+\.?\d*", argstr)]
        if not n:
            continue
        c = cmd.upper()
        if c == "M" or c == "L":
            for i in range(0, len(n) - 1, 2):
                x, y = n[i], n[i + 1]
                if first is None:
                    first = (x, y)
        elif c == "H":
            x = n[-1]
            if first is None:
                first = (x, y)
        elif c == "V":
            y = n[-1]
            if first is None:
                first = (x, y)
    return (first or (x, y)), (x, y)


def near_edge(px, py, node, tol):
    """点是否贴在节点某条边上"""
    iny = node["y"] - tol <= py <= node["b"] + tol
    inx = node["x"] - tol <= px <= node["r"] + tol
    left = abs(px - node["x"]) <= tol and iny
    right = abs(px - node["r"]) <= tol and iny
    top = abs(py - node["y"]) <= tol and inx
    bot = abs(py - node["b"]) <= tol and inx
    return left or right or top or bot


def on_lifeline(px, py, lines, tol):
    return any(abs(px - l["x"]) <= tol and l["y1"] - tol <= py <= l["y2"] + tol for l in lines)


def texts_out_of_canvas(body, w, h):
    bad = []
    for m in re.finditer(r'<text\s+class="([^"]*)"\s+x="([\d.\-]+)"\s+y="([\d.\-]+)"[^>]*>(.*?)</text>',
                         body, re.S):
        x, y = float(m.group(2)), float(m.group(3))
        label = re.sub(r"<[^>]+>", "", m.group(4)).strip()
        if y < 0 or y > h or x < 0 or x > w:
            bad.append((label[:26], x, y))
    return bad


def main():
    ap = argparse.ArgumentParser(description="SVG 布局自检")
    ap.add_argument("file")
    ap.add_argument("--tol", type=float, default=8.0, help="箭头落点容差（px）")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    html = open(a.file, encoding="utf-8").read()
    svgs = parse_svgs(html)
    if not svgs:
        print("未找到带 aria-label 的 <svg>，跳过")
        return 0

    report, fatal = [], False
    for sv in svgs:
        ns = nodes(sv["body"])
        lines = lifelines(sv["body"])
        ov = overlaps(ns)

        miss = []
        n_path = 0
        paths = [m for m in re.finditer(
            r'<path\s+class="(ln[^"]*)"\s+d="([^"]+)"([^>]*)>', sv["body"])]
        # 先收集全部连接线的起点：一个「分叉汇合点」不是节点，但它是合法终点
        starts = []
        for m in paths:
            s, _e = path_ends(m.group(2))
            starts.append(s)
        for m in paths:
            cls, d, rest = m.group(1), m.group(2), m.group(3)
            if "marker-end" not in rest:
                continue          # 只校验带箭头的连接线
            _s, e = path_ends(d)
            n_path += 1
            ok = any(near_edge(e[0], e[1], n, a.tol) for n in ns) \
                or on_lifeline(e[0], e[1], lines, a.tol) \
                or any(abs(e[0] - sx) <= a.tol and abs(e[1] - sy) <= a.tol
                       for sx, sy in starts)
            if not ok:
                miss.append((cls, round(e[0], 1), round(e[1], 1)))

        oob = texts_out_of_canvas(sv["body"], sv["width"], sv["height"])
        bad = bool(ov or miss or oob)
        fatal = fatal or bad
        report.append({"name": sv["name"], "nodes": len(ns), "arrows": n_path,
                       "lifelines": len(lines),
                       "overlaps": len(ov), "floating": miss, "out_of_canvas": oob})

        mark = "❌" if bad else "✅"
        print(f"{mark} 【{sv['name']}】节点 {len(ns)} ｜ 带箭头连接线 {n_path} ｜ "
              f"生命线 {len(lines)} ｜ 画布 {int(sv['width'])}×{int(sv['height'])}")
        for aa, bb, ox, oy in ov[:6]:
            cx1, cy1 = aa["x"] + aa["w"] / 2, aa["y"] + aa["h"] / 2
            cx2, cy2 = bb["x"] + bb["w"] / 2, bb["y"] + bb["h"] / 2
            print(f"     ❌ 节点重叠 {ox:.0f}×{oy:.0f}px："
                  f"({cx1:.0f},{cy1:.0f})[{aa['cls']}] ↔ ({cx2:.0f},{cy2:.0f})[{bb['cls']}]")
        for cls, x, y in miss[:8]:
            print(f"     ❌ 箭头落点悬空 ({x},{y})  [{cls}] 不在任何节点边缘 ±{a.tol:.0f}px 内")
        for lb, x, y in oob[:6]:
            print(f"     ❌ 文本出画布「{lb}」({x},{y})")
        if not bad:
            print("     节点无重叠 · 箭头落点全部贴合 · 文本均在画布内")

    if a.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    print()
    print("=" * 62)
    print("❌ 存在布局问题，请修正坐标后重跑（退出码 1）" if fatal
          else "✅ 全部图通过（退出码 0）")
    print("=" * 62)
    return 1 if fatal else 0


if __name__ == "__main__":
    sys.exit(main())
