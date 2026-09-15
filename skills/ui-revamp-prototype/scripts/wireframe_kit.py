#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
wireframe_kit.py —— 页面线框原语库（「把页面放进流程图」专用）

为什么要有它：
  页面流程图的节点不是文字框，而是页面缩略图。一个线框 25~30 个图元，
  一张图能到 400 个图元 —— 手算坐标必错，而且 verify_svg_layout.py 要求
  属性严格顺序（rect: class→x→y→width→height；text: class→x→y），
  写反是**静默漏检**（不报错，只是该查的没查）。
  用代码生成可同时保证「坐标自洽」与「属性顺序恒定」。

用法（三步）：
  1) cp 本文件到工作区
  2) 写 _gen1.py / _gen2.py ... 各屏：
         import sys; sys.path.insert(0, '.')
         from wireframe_kit import *
         svg = '<svg viewBox="0 0 1240 800" aria-label="..." xmlns="...">' + DEFS + \
               wf_content(60, 80, 210, 230, 'anon') + arrow('M270,195 H470') + '</svg>'
         open('_g1.svg', 'w', encoding='utf-8').write(svg)
     ⚠️ <svg> 必须带 aria-label，否则校验脚本扫不到它
     ⚠️ 箭头用 class="ln"（只认 ln 前缀才校验落点）；装饰性线用 wf-ln / ln-d
  3) 写 _build.py 把「基础 CSS + 新增 CSS + 各片段 + 侧栏 + 文档头」拼成单文件

两条关键设计：
  · shell 参数：shell=True 画整页（含页头/侧栏，用于跨页流转图）；
                shell=False 只画居中卡片（用于「同一页面的 N 个状态并排」）
  · card_cls 必须带 nd（nd/nd-b/nd-e/nd-k）—— 卡片模式下线框自身是节点，
    箭头要落在它边上；不带 nd 就不会被当节点，落点无法校验。
    反之整页模式下内部卡片固定用 wf-card（非节点），避免污染节点集合。

改过本文件 → **所有 _genN.py 全部重跑**，再拼装。只跑最后一张是最常见的静默失效。
配套 CSS 类（wf-* / 演示区 pc-*）见 SKILL.md「页面流程图」一节。
"""



# ─────────────────────────── 原子图元 ───────────────────────────

def r(x, y, w, h, cls, rx=2):
    """矩形。cls 不含 nd → 不参与节点检查。"""
    return (f'<rect class="{cls}" x="{x:.1f}" y="{y:.1f}" '
            f'width="{w:.1f}" height="{h:.1f}" rx="{rx}"/>')


def t(x, y, s, cls="wf-t", anchor="start"):
    return f'<text class="{cls}" x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}">{s}</text>'


def line(x1, y1, x2, y2, cls="wf-sep"):
    return (f'<line class="{cls}" x1="{x1:.1f}" y1="{y1:.1f}" '
            f'x2="{x2:.1f}" y2="{y2:.1f}"/>')


def arrow(d, cls="ln"):
    return f'<path class="{cls}" d="{d}" marker-end="url(#ah)"/>'


def seg(d, cls="ln"):
    """无箭头的连接线 —— 同时也是「分叉汇合点合法化」的工具：
    让它成为汇合点的起点，该点即被校验脚本认作合法落点。"""
    return f'<path class="{cls}" d="{d}"/>'


# ─────────────────────────── 组件级 ───────────────────────────

def window_shell(x, y, w, h, url, cls="nd"):
    """浏览器窗口外壳 + 地址栏。外层 rect 带 nd → 是真正的节点框。"""
    o = [r(x, y, w, h, cls, 7)]
    for i in range(3):
        o.append(f'<circle cx="{x + 11 + i * 8:.1f}" cy="{y + 11:.1f}" r="2.2" class="wf-dot"/>')
    ux, uw = x + 38, w - 50
    o.append(r(ux, y + 6, uw, 10, "wf-url", 5))
    o.append(t(ux + 5, y + 13.6, url, "wf-url-tx"))
    o.append(line(x, y + 21, x + w, y + 21, "wf-sep"))
    return "".join(o)


def site_header(x, y, w, state="anon"):
    """站内页头。state: anon(登录/注册) / auth(头像) / expire(登录态过期)。
    这一条是 PC 端三态的载体 —— 同一段代码三种渲染。"""
    o = [r(x, y, w, 17, "wf-hd", 0)]
    o.append(r(x + 7, y + 5, 26, 7, "wf-logo", 2))          # logo
    for i in range(4):
        o.append(r(x + 40 + i * 15, y + 6.5, 11, 4, "wf-nav", 1))
    if state == "anon":
        o.append(r(x + w - 46, y + 4.5, 39, 8, "wf-cta", 2))
        o.append(t(x + w - 26.5, y + 10.2, "登录/注册", "wf-cta-tx", "middle"))
    elif state == "auth":
        o.append(f'<circle cx="{x + w - 14:.1f}" cy="{y + 8.5:.1f}" r="5" class="wf-av"/>')
        o.append(r(x + w - 44, y + 5.5, 22, 6, "wf-nav", 2))
    else:
        o.append(r(x + w - 46, y + 4.5, 39, 8, "wf-wait", 2))
        o.append(t(x + w - 26.5, y + 10.2, "登录已过期", "wf-warn-tx", "middle"))
    return "".join(o)


def site_footer(x, y, w, h=11):
    """页脚深色条 —— 让线框一眼能认出是"页面"而不是普通卡片。"""
    return r(x, y, w, h, "wf-ft", 0) + r(x + 8, y + 3.5, w * 0.42, 4, "wf-ft-tx", 1)


def crumbs(x, y, w=52):
    return (r(x, y, w * 0.34, 4, "wf-l", 1)
            + r(x + w * 0.4, y, w * 0.22, 4, "wf-l", 1))


def page_title(x, y, w):
    """h1 + 副标题两条。"""
    return r(x, y, w * 0.34, 7, "wf-h1", 2) + r(x, y + 11, w * 0.72, 4, "wf-l", 1)


def sidebar_card(x, y, w, h, label="二维码"):
    """右侧侧栏（PC 才有：lg:flex-row）。线上是「官方社群」二维码。"""
    o = [r(x, y, w, h, "wf-side", 4)]
    o.append(r(x + 7, y + 7, w * 0.42, 5, "wf-nav", 1))
    qs = min(w - 24, 34)
    o.append(r(x + (w - qs) / 2, y + 19, qs, qs, "wf-qr", 3))
    o.append(r(x + 7, y + 19 + qs + 8, w - 14, 4, "wf-l2", 1))
    o.append(r(x + 7, y + 19 + qs + 15, w * 0.62, 4, "wf-l2", 1))
    return "".join(o)


# ─────────────────────────── 页面线框 ───────────────────────────

def wf_content(x, y, w, h, state="anon", note=None):
    """内容页线框（PC 两栏：主内容 + 右窄侧栏）。
    用来当流程的起点与终点 —— 证明「登录这个动作发生在任意页，并且要回到任意页」。
    内容条数量按高度自适应填充，避免大尺寸线框下半部空掉（一眼就假）。"""
    o = [window_shell(x, y, w, h, "humancehr.com/...")]
    o.append(site_header(x, y + 21, w, state))
    o.append(crumbs(x + 8, y + 45))
    o.append(page_title(x + 8, y + 58, w - 60))
    # 主内容区 + 右侧栏（PC：lg:flex-row 两栏）
    side_w = w * 0.24
    main_w = w - side_w - 24
    top, bottom = y + 82, y + h - 20
    n = max(3, int((bottom - top) / 13))
    for i in range(n):
        wid = 1.0 if i % 4 != 3 else 0.58
        o.append(r(x + 8, top + i * 13, main_w * wid, 9, "wf-l", 2))
    o.append(sidebar_card(x + w - side_w - 8, top, side_w, min(bottom - top, 76)))
    o.append(site_footer(x, y + h - 11, w))
    return "".join(o)


def wf_login(x, y, w, h, tab="sms", stage="idle", shell=True, card_cls="nd"):
    """登录页线框。
    shell=True  → 整页（含窗口外壳 / 页头 / 右侧栏），用于跨页面流程图
    shell=False → 只画居中卡片，用于「同一页面的不同状态」并排展示（g2 屏）
    tab:  'pwd' 密码登录 | 'sms' 手机号登录
    stage: idle / sending / sent / error / success / loading
    card_cls: 状态线框的外框类（nd / nd-b / nd-e / nd-k）—— 必须带 nd，
              否则不会被校验脚本当作节点，箭头落点就无法校验。
    """
    o = []
    if shell:
        o.append(window_shell(x, y, w, h, "humancehr.com/login"))
        o.append(site_header(x, y + 21, w, "anon"))
        o.append(crumbs(x + 8, y + 45))
        o.append(page_title(x + 8, y + 58, w - 60))
        side_w = w * 0.24
        cx, cy, cw, ch = x + 8, y + 82, w - side_w - 30, h - 104
    else:
        side_w = 0
        cx, cy, cw, ch = x, y, w, h

    # 整页模式下卡片内部用 wf-card（不参与节点检查）；
    # 卡片模式下用 card_cls（必须带 nd —— 箭头要落在它的边上）
    o.append(r(cx, cy, cw, ch, "wf-card" if shell else card_cls, 6))

    # Tab 条：两等分，激活侧加下划线
    half = cw / 2
    o.append(r(cx + 7, cy + 7, half - 14, 5, "wf-h1" if tab == "pwd" else "wf-l", 1))
    o.append(r(cx + half + 7, cy + 7, half - 14, 5, "wf-h1" if tab == "sms" else "wf-l", 1))
    o.append(line(cx + 7, cy + 17, cx + cw - 7, cy + 17, "wf-sep"))
    ux = cx + 7 + (0 if tab == "pwd" else half)
    o.append(line(ux, cy + 17, ux + half - 14, cy + 17, "wf-uline"))

    fy = cy + 26
    if tab == "pwd":
        o.append(r(cx + 7, fy, cw - 14, 12, "wf-in", 2))
        o.append(r(cx + 7, fy + 18, cw - 14, 12, "wf-in", 2))
        o.append(r(cx + 7, fy + 36, 26, 5, "wf-l2", 1))          # 记住我（线上值被丢弃）
        o.append(r(cx + 37, fy + 36, 22, 5, "wf-l2", 1))         # 忘记密码？
    else:
        o.append(r(cx + 7, fy, cw - 14, 12, "wf-in", 2))
        bw = (cw - 14) * 0.42
        o.append(r(cx + 7, fy + 18, cw - 14 - bw - 5, 12, "wf-in", 2))
        bx = cx + 7 + (cw - 14 - bw)
        bcls = {"sending": "wf-wait", "sent": "wf-l2"}.get(stage, "wf-bo")
        o.append(r(bx, fy + 18, bw, 12, bcls, 2))
        if stage == "sent":
            o.append(t(bx + bw / 2, fy + 26, "48s", "wf-tx-s", "middle"))
        elif stage == "sending":
            o.append(t(bx + bw / 2, fy + 26, "发送中", "wf-tx-s", "middle"))
        else:
            o.append(t(bx + bw / 2, fy + 26, "发送验证码", "wf-tx-xs", "middle"))

    by = fy + 42
    bcls = {"error": "wf-errb", "success": "wf-okf", "loading": "wf-loadb"}.get(stage, "wf-b")
    o.append(r(cx + 7, by, cw - 14, 15, bcls, 2))
    lbl = {"success": "登录成功！正在跳转…", "loading": "登录中…"}.get(stage, "登录")
    o.append(t(cx + cw / 2, by + 10, lbl, "wf-btn-tx", "middle"))

    if stage == "error":
        o.append(r(cx + 7, by + 21, cw - 14, 12, "wf-err", 2))
        o.append(t(cx + 11, by + 29, "登录失败，请检查手机号和验证码", "wf-err-tx"))
    elif stage == "success":
        o.append(r(cx + 7, by + 21, cw - 14, 12, "wf-okb", 2))
        o.append(t(cx + 11, by + 29, "登录成功，正在跳转…", "wf-ok-tx"))
    # 底部说明区：线上有「未注册手机验证后自动登录」小字 + 「立即注册 / 忘记密码？」
    # 按卡片实际高度自适应铺开，避免高卡片下半部空掉（空了就一眼看出是凑的）
    ly = by + (34 if stage in ("error", "success") else 22)
    room = cy + ch - 12 - ly
    n = max(2, min(7, int(room / 11)))
    for i in range(n):
        wid = (0.66, 0.5, 0.4)[i % 3]
        o.append(r(cx + (cw - cw * wid) / 2, ly + i * 11, cw * wid, 4, "wf-l2", 1))

    if shell:
        o.append(sidebar_card(x + w - side_w - 8, cy, side_w, 58))
        o.append(site_footer(x, y + h - 11, w))
    return "".join(o)


def wf_register(x, y, w, h, stage="idle", shell=True, card_cls="nd"):
    """注册页线框。
    PC 上与登录页最大的形态差异：卡片 max-w-4xl（约为登录页 2 倍宽）+ md:grid-cols-2 两列网格。
    stage: idle / sent / fielderr / pwweak / loading / success
    """
    o = []
    if shell:
        o.append(window_shell(x, y, w, h, "humancehr.com/register"))
        o.append(site_header(x, y + 21, w, "anon"))
        o.append(crumbs(x + 8, y + 45))
        o.append(page_title(x + 8, y + 58, w - 60))
        side_w = w * 0.22
        cx, cy, cw, ch = x + 8, y + 82, w - side_w - 30, h - 104
    else:
        side_w = 0
        cx, cy, cw, ch = x, y, w, h

    o.append(r(cx, cy, cw, ch, "wf-card" if shell else card_cls, 6))
    # 卡片模式下行距按高度自适应 —— 否则高卡片的下半部会空掉
    rowh = 14.0 if shell else max(15.0, min(22.0, (ch - 48) / 6.5))
    iy = cy + 8
    if stage in ("fielderr", "pwweak"):
        o.append(r(cx + 7, iy, cw - 14, 12, "wf-err", 2))
        msg = "请输入有效的手机号码" if stage == "fielderr" else "密码强度不足，请使用更复杂的密码"
        o.append(t(cx + 11, iy + 8.4, msg, "wf-err-tx"))
        iy += rowh + 2

    col = (cw - 14 - 6) / 2
    # 用户名（跨两列）
    o.append(r(cx + 7, iy, cw - 14, 11, "wf-in", 2))
    iy += rowh
    # 邮箱 + 发码按钮 ｜ 邮箱验证码
    ebcls = "wf-l2" if stage == "sent" else "wf-bo"
    o.append(r(cx + 7, iy, col * 0.62, 11, "wf-in", 2))
    o.append(r(cx + 7 + col * 0.66, iy, col * 0.34, 11, ebcls, 2))
    o.append(r(cx + 13 + col, iy, col, 11, "wf-in", 2))
    iy += rowh
    # 手机号 + 发码按钮 ｜ 短信验证码
    mbcls = "wf-err" if stage == "fielderr" else "wf-in"
    o.append(r(cx + 7, iy, col * 0.62, 11, mbcls, 2))
    o.append(r(cx + 7 + col * 0.66, iy, col * 0.34, 11, ebcls, 2))
    o.append(r(cx + 13 + col, iy, col, 11, "wf-in", 2))
    iy += rowh
    # 密码 / 确认密码 —— 线上内联样式写死 grid-template-columns:1fr，
    # 所以 PC 上这两格其实是单列堆叠（设计了双列但没生效），此处如实复刻
    o.append(r(cx + 7, iy, cw - 14, 11, "wf-in", 2))
    iy += rowh
    o.append(r(cx + 7, iy, cw - 14, 11, "wf-in", 2))
    # 密码强度指示器（线上存在但 JS 从不操作 DOM）
    sb = 4 if stage != "pwweak" else 1
    for k in range(4):
        o.append(r(cx + cw - 46 + k * 10, iy + 3, 8, 4,
                   "wf-errb" if (stage == "pwweak" and k < sb) else "wf-l2", 1))
    iy += rowh
    # 协议勾选
    o.append(r(cx + 7, iy, 5, 5, "wf-bo", 1))
    o.append(r(cx + 15, iy + 0.5, cw * 0.42, 4, "wf-l2", 1))
    bcls = {"loading": "wf-loadb", "success": "wf-okf"}.get(stage, "wf-b")
    o.append(r(cx + 7, iy + 11, cw - 14, 15, bcls, 2))
    lbl = {"success": "注册成功！正在进入…", "loading": "注册中…"}.get(stage, "注册")
    o.append(t(cx + cw / 2, iy + 21, lbl, "wf-btn-tx", "middle"))

    # 底部说明区（卡片模式下自适应铺开）
    ly = iy + 34
    room = cy + ch - 10 - ly
    for i in range(max(0, min(4, int(room / 11)))):
        wid = (0.5, 0.36)[i % 2]
        o.append(r(cx + (cw - cw * wid) / 2, ly + i * 11, cw * wid, 4, "wf-l2", 1))

    if shell:
        o.append(sidebar_card(x + w - side_w - 8, cy, side_w, 58))
        o.append(site_footer(x, y + h - 11, w))
    return "".join(o)


# ─────────────────────────── 状态结点 ───────────────────────────

def state_node(x, y, w, h, text, sub=None, cls="nd-k", lines=None):
    """非页面的状态结点（成功/失败/判定）。lines 为多行文字列表。"""
    o = [r(x, y, w, h, cls, 6)]
    rows = lines or [text]
    n = len(rows)
    base = y + h / 2 - (n - 1) * 6.5 + 4
    for i, s in enumerate(rows):
        o.append(t(x + w / 2, base + i * 13, s, "wf-node-tx", "middle"))
    return "".join(o)


def caption(x, y, w, s, sub=None, cls="wf-cap"):
    """节点下方的标题与副标 —— 页面线框本身没有文字，靠这里指认是哪个页面。"""
    o = [t(x + w / 2, y, s, cls, "middle")]
    if sub:
        o.append(t(x + w / 2, y + 12, sub, "wf-cap2", "middle"))
    return "".join(o)
