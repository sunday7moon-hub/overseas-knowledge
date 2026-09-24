#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
render_shot.py —— UI 原型的真实渲染验证（截图 + 几何测量）

为什么需要它：
  verify_prototype.py / verify_svg_layout.py 只能做静态检查，抓不到「渲染后才发现」
  的问题：按钮换行、内容溢出、文字截断、元素挤在一起、暗底上的低对比度文字。
  本脚本用本机 Google Chrome（经 puppeteer-core 驱动）真实渲染原型、逐块截图、
  输出元素几何，调用方直接看图即可完成视觉验收。

  ⚠️ 2026-09-17 实测更正：本机沙箱**可以**渲染。此前「headless Chrome 无法启动、
  截图不可用」的结论来自直接调用 chrome CLI（`--headless=new` 静默无输出）。
  经 puppeteer-core 驱动（自带临时 user-data-dir 与启动参数）可稳定启动、截图、测量。

用法：
  python3 render_shot.py <原型.html> [选项]

  --width   760,1440          视口宽度列表（默认 760,1440）
  --sel     "#s01 .frame"     逐块截图的选择器，可重复（默认 body）
  --measure "#s01 .cta-row"   几何测量：子元素是否同行 / 是否溢出容器，可重复
  --out     /tmp/shots        截图输出目录（默认 mktemp）
  --dsf     2                 设备像素比（截图清晰度）
  --no-shot                   只测量不截图（快速布局回归）

退出码：
  0 = 通过
  1 = 发现溢出 / 换行（--measure 命中）
  2 = 环境不可用（找不到 node / Chrome / puppeteer-core）

配合用法（Step 5 第四件套）：
  python3 render_shot.py 原型.html --measure "#s01 .cta-row" --no-shot   # CI 式布局回归
  python3 render_shot.py 原型.html --sel "#s01 .frame" --width 1440      # 出图给人看
"""
import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile

NODE_GLOBS = [
    os.path.expanduser("~/.workbuddy/binaries/node/versions/*/bin/node"),
    "/usr/local/bin/node",
    "/opt/homebrew/bin/node",
]
NODE_PATH_CANDIDATES = [
    os.path.expanduser("~/.workbuddy/binaries/node/workspace/node_modules"),
]
CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
]

JS_TEMPLATE = r"""
const puppeteer = require('puppeteer-core');
const opts = JSON.parse(process.argv[2]);
(async () => {
  const browser = await puppeteer.launch({
    executablePath: opts.chrome,
    headless: 'new',
    args: ['--no-sandbox', '--disable-dev-shm-usage']
  });
  const page = await browser.newPage();
  const out = { shots: [], measures: [], consoleErrors: [] };
  page.on('pageerror', e => out.consoleErrors.push(String(e).slice(0, 200)));
  for (const w of opts.widths) {
    await page.setViewport({ width: w, height: opts.height, deviceScaleFactor: opts.dsf });
    await page.goto(opts.url, { waitUntil: 'load' });
    await new Promise(r => setTimeout(r, 120));
    if (!opts.noShot) {
      for (let i = 0; i < opts.selectors.length; i++) {
        const el = await page.$(opts.selectors[i]);
        if (!el) { out.shots.push({ w, sel: opts.selectors[i], err: 'selector not found' }); continue; }
        const p = `${opts.out}/w${w}_${i}.png`;
        try { await el.screenshot({ path: p }); out.shots.push({ w, sel: opts.selectors[i], path: p }); }
        catch (e) { out.shots.push({ w, sel: opts.selectors[i], err: String(e).slice(0, 120) }); }
      }
    }
    for (const msel of opts.measures) {
      const m = await page.evaluate((sel) => {
        const el = document.querySelector(sel);
        if (!el) return { sel, err: 'selector not found' };
        const kids = [...el.children];
        const rects = kids.map(k => k.getBoundingClientRect());
        const tops = rects.map(r => Math.round(r.top));
        const gap = parseFloat(getComputedStyle(el).gap) || 0;
        // 按 top 分行求和：flex 单行 / grid 多行都能算对（早前版本把多行宽度相加导致误报）
        const rows = {};
        rects.forEach(r => { const k = Math.round(r.top); (rows[k] = rows[k] || []).push(r.width); });
        let maxRowW = 0;
        Object.values(rows).forEach(ws => {
          const s = ws.reduce((a, b) => a + b, 0) + (ws.length > 1 ? gap * (ws.length - 1) : 0);
          if (s > maxRowW) maxRowW = s;
        });
        const containerW = el.getBoundingClientRect().width;
        return {
          sel,
          childCount: kids.length,
          lines: new Set(tops).size,
          containerW: Math.round(containerW),
          contentW: Math.round(maxRowW),
          overflowsContainer: maxRowW > containerW + 1,
          overflowsSelf: el.scrollWidth > el.clientWidth + 1
        };
      }, msel);
      out.measures.push({ w, ...m });
    }
  }
  await browser.close();
  console.log('__RESULT__' + JSON.stringify(out));
})().catch(e => { console.log('__ERROR__' + String(e).slice(0, 400)); process.exit(3); });
"""


def find_node():
    env = os.environ.get("RENDER_SHOT_NODE")
    if env and os.path.exists(env):
        return env
    for pat in NODE_GLOBS:
        hits = sorted(glob.glob(pat))
        if hits:
            return hits[-1]
    return shutil.which("node")


def find_chrome():
    env = os.environ.get("CHROME_PATH")
    if env and os.path.exists(env):
        return env
    for c in CHROME_CANDIDATES:
        if os.path.exists(c):
            return c
    return None


def find_node_path():
    env = os.environ.get("RENDER_SHOT_NODE_PATH")
    if env and os.path.isdir(env):
        return env
    for c in NODE_PATH_CANDIDATES:
        if os.path.isdir(os.path.join(c, "puppeteer-core")):
            return c
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--width", default="760,1440")
    ap.add_argument("--sel", action="append", default=[])
    ap.add_argument("--measure", action="append", default=[])
    ap.add_argument("--out", default=None)
    ap.add_argument("--dsf", type=float, default=2)
    ap.add_argument("--height", type=int, default=1400)
    ap.add_argument("--no-shot", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    path = os.path.abspath(a.file)
    if not os.path.exists(path):
        print("文件不存在: " + path)
        return 2

    node = find_node()
    chrome = find_chrome()
    node_path = find_node_path()
    missing = []
    if not node:
        missing.append("node")
    if not chrome:
        missing.append("Chrome")
    if not node_path:
        missing.append("puppeteer-core（在 ~/.workbuddy/binaries/node/workspace/node_modules 下）")
    if missing:
        print("环境不可用，缺少: " + " / ".join(missing))
        print("可用环境变量覆盖：RENDER_SHOT_NODE / CHROME_PATH / RENDER_SHOT_NODE_PATH")
        return 2

    outdir = a.out or tempfile.mkdtemp(prefix="render_shot_")
    os.makedirs(outdir, exist_ok=True)

    widths = [int(x) for x in str(a.width).split(",") if x.strip()]
    selectors = a.sel or ["body"]
    opts = {
        "url": "file://" + path.replace(" ", "%20"),
        "chrome": chrome,
        "widths": widths,
        "selectors": selectors,
        "measures": a.measure,
        "out": outdir,
        "dsf": a.dsf,
        "height": a.height,
        "noShot": bool(a.no_shot),
    }

    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(JS_TEMPLATE)
        jsfile = f.name

    env = dict(os.environ)
    env["NODE_PATH"] = node_path
    try:
        p = subprocess.run([node, jsfile, json.dumps(opts)],
                           capture_output=True, text=True, env=env, timeout=180)
    finally:
        os.unlink(jsfile)

    raw = p.stdout or ""
    if "__ERROR__" in raw:
        print("渲染失败：" + raw.split("__ERROR__", 1)[1][:400])
        return 2
    if "__RESULT__" not in raw:
        print("未拿到结果。stdout:\n" + raw[:600] + "\nstderr:\n" + (p.stderr or "")[:600])
        return 2

    res = json.loads(raw.split("__RESULT__", 1)[1].strip().splitlines()[0])
    if a.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        print("=" * 66)
        print("UI 原型渲染验证   视口: " + ",".join(str(w) for w in widths) + "   输出: " + outdir)
        print("=" * 66)
        if res["shots"]:
            print("\n[截图]")
            for s in res["shots"]:
                if s.get("err"):
                    print("  ❌ w=%s  %s  %s" % (s["w"], s["sel"], s["err"]))
                else:
                    print("  ✅ w=%s  %s  → %s" % (s["w"], s["sel"], s["path"]))
        if res["measures"]:
            print("\n[几何测量]")
            for m in res["measures"]:
                if m.get("err"):
                    print("  ❌ w=%s  %s  %s" % (m["w"], m["sel"], m["err"]))
                    continue
                flag = "❌" if (m["overflowsContainer"] or m["overflowsSelf"]) else "✅"
                print("  %s w=%-5s %s  子元素 %d 个 / 占 %d 行 / 内容宽 %d vs 容器宽 %d"
                      % (flag, m["w"], m["sel"], m["childCount"], m["lines"],
                         m["contentW"], m["containerW"]))
        if res.get("consoleErrors"):
            print("\n[页面 JS 报错]")
            for e in res["consoleErrors"]:
                print("  ⚠️ " + e)
        print("\n" + "=" * 66)

    bad = [m for m in res["measures"] if m.get("overflowsContainer") or m.get("overflowsSelf")]
    if bad:
        print("❌ 发现溢出，需修布局（%d 处）" % len(bad))
        return 1
    print("✅ 渲染验证通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
