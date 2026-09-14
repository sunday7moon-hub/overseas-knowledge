# -*- coding: utf-8 -*-
"""
Humance 邮件推送去重与排程器
================================
核心规则：每个用户（user_id）在自然日内最多收到 1 封邮件。

邮件类型与触发时机
------------------
  R  注册成功确认   T+0 注册即时触发      轻量：账号已创建 + 1 个明确下一步，不含大段行为推荐
  W  注册欢迎(含行为) T+1 注册次日触发     整合 T+0 及注册前后行为的个性化欢迎 + 内容推荐
  A  用户活跃邮件   自活跃日起 T+3 触发     基于该次浏览/下载/扫码的精准内容，行为驱动
  C  二次触达邮件   高价值/存量周期触达    专题 / 开发信
  D  未活跃召回邮件  自【最后活跃日】起 T+5 触发（5 日未活跃）  ← 2026-09-04 新增

优先级（同日冲突时高者胜出，低者顺延并把行为数据并入胜出邮件，不丢弃）
  R(0) > W(1) > A(2) > C(3) > D(4)

客户阶段分层（stage，默认 None=未建联）
--------------------------------------
  已建联用户（销售/商务已加企微跟进）：停发 C 类（避免打扰在跟的人），
    活跃邮件 A 周上限由 3 降到 2，且优先转企微/人工通道。
  已转化用户（签约/付费）：停发 A、C（只保留 R 注册确认与 W 欢迎），
    其余走人工 + 产品/账单邮件，不再自动群发。
  已合作用户（已签约并开始服务/付费的存量客户）：自动化触发邮件全部停发
    （R/W/A/C/D 一律不群发，避免打扰付费客户），触达统一交由客户成功(CSM)/
    交付/账单等人工通道。这是最深阶段，强于已转化。

  ★ 召回例外（2026-09-04 用户确认）★
  D 类「未活跃召回」属于唤醒性质，不等同于营销 C 类：
    未建联 / 已建联 / 已转化 三个阶段**都发 D**；
    仅 已合作(cooperating) 因走 CSM 人工通道而全停（含 D）。
  R / W 注册类对『未建联/已建联/已转化』都照发（新注册即便已建联也该有确认 + 欢迎）；
    已合作阶段例外——全停，不群发任何自动化邮件。

排程策略
--------
  1. 每类型有 preferred_send_date（R=T+0, W=T+1, A/C=事件日, D=最后活跃日+5）。
  2. 按优先级从高到低处理；每用户维护"已占用日期"集合。
  3. 某触发若 preferred 日已被同用户更高优先级邮件占用，向后扫描最近空日（上限 14 天）。
  4. 被顺延的触发，若其事件日早于某个更高优先级邮件的发送日（如 A 在 T+0，W 在 T+1），
     则把它的行为画像并入那封更高优先级邮件 —— 行为不丢失。

反骚扰护栏（默认开启，可调）
  - 同一用户活跃邮件(A)每周最多 3 封（已建联降到 2）
  - 注册后 7 天内不打 C 类二次触达（先培育）
  - 退订/30 天无互动用户自动降频（由调用方在入参标记 suppressed）
  - 已建联用户停发 C；已转化用户停发 A、C；已合作用户 R/W/A/C/D 全停（见客户阶段分层）
  - 召回冷却：同一用户两次 D 类召回至少间隔 RECALL_COOLDOWN_DAYS 天

历史数据去重规则（2026-09-04 用户确认）
--------------------------------------
  对已落库的推送记录做体检时：
    - 同一用户两条记录日期间隔 **≤ DUP_WINDOW_DAYS(2) 天** → 判为重复，删多余只留 1 条
      （同 1 日、隔 2 日都算重复）
    - 间隔 **≥ 3 天** → 视为正常的多次触达（如第二次触达/召回），**保留不删**
  用 dedupe_records() 计算，返回保留集与待删集，调用方据此清理飞书表。
"""

from dataclasses import dataclass, field
from typing import Optional
from datetime import date, timedelta
from collections import defaultdict

# 类型元数据：priority 越小越高；offset 相对于事件日的发送偏移
EMAIL_TYPES = {
    "R": {"priority": 0, "offset": 0,  "desc": "注册成功确认"},
    "W": {"priority": 1, "offset": 1,  "desc": "注册欢迎(含行为)"},
    "A": {"priority": 2, "offset": 3,  "desc": "用户活跃邮件（自活跃日起 +3 天推送）"},
    "C": {"priority": 3, "offset": 0,  "desc": "二次触达邮件"},
    "D": {"priority": 4, "offset": 5,  "desc": "未活跃召回邮件（自最后活跃日起 +5 天推送）"},
}

# 客户阶段规则：stage -> {skip: 跳过的邮件类型, a_weekly_cap: 活跃邮件周上限}
# stage=None(未建联) 走默认；"connected" 已建联；"converted" 已转化；"cooperating" 已合作
# 注意：D 类召回是例外——未建联/已建联/已转化都发，仅已合作全停。
STAGE_RULES = {
    None:         {"skip": set(),            "a_weekly_cap": 3},
    "none":       {"skip": set(),            "a_weekly_cap": 3},
    "connected":  {"skip": {"C"},            "a_weekly_cap": 2},
    "converted":  {"skip": {"A", "C"},       "a_weekly_cap": 0},
    "cooperating": {"skip": {"R", "W", "A", "C", "D"}, "a_weekly_cap": 0},  # 已合作：自动化全停，转 CSM
}

# 护栏参数
QUIET_DAYS_FOR_C = 7       # 注册后多少天内不打 C
DEFER_LOOKAHEAD = 14       # 顺延最多向前看多少天
INACTIVE_DAYS = 5          # 未活跃多少天触发 D 类召回（= D 的 offset）
RECALL_COOLDOWN_DAYS = 30  # 同一用户两次 D 类召回的最小间隔（防召回轰炸）
DUP_WINDOW_DAYS = 2        # 历史去重窗口：间隔 ≤2 天视为重复（3 天及以上保留）


@dataclass
class Trigger:
    user_id: str
    etype: str                     # R / W / A / C / D
    event_date: date              # 事件发生的自然日（D 类传「最后活跃日」）
    behavior: dict = field(default_factory=dict)   # 行为画像：views/downloads/scans/country...
    registered_on: Optional[date] = None            # 注册日（用于 C 静默窗）
    suppressed: bool = False       # 退订 / 长期无互动 -> 本批不排
    stage: Optional[str] = None    # 客户阶段：None/"none" 未建联 | "connected" 已建联 | "converted" 已转化 | "cooperating" 已合作
    last_recall_on: Optional[date] = None           # 上次 D 类召回发送日（用于召回冷却）


def _merge_behavior(base: dict, extra: dict) -> dict:
    """把 extra 的行为并入 base（列表累加，标量取后者）。"""
    if not extra:
        return base
    out = dict(base)
    for k, v in extra.items():
        if isinstance(v, list):
            out[k] = out.get(k, []) + v
        else:
            out[k] = v
    return out


def _next_free_date(occupied: set, preferred: date, limit: int = DEFER_LOOKAHEAD) -> date:
    d = preferred
    for _ in range(limit):
        if d not in occupied:
            return d
        d += timedelta(days=1)
    return d  # 超限则落在 limit 天后（调用方可据此告警）


def schedule(triggers: list[Trigger]) -> list[dict]:
    """
    输入一批触发，输出最终发送计划（每用户每日至多 1 封）。
    返回列表：{user_id, send_date, etype, behavior, merged_from: [被并入的类型]}
    """
    # 过滤退订/降频
    active = [t for t in triggers if not t.suppressed]

    # 预计算每触发的 preferred_send_date
    for t in active:
        off = EMAIL_TYPES[t.etype]["offset"]
        t._preferred = t.event_date + timedelta(days=off)

    # 按优先级升序、再按 preferred 升序处理（高优先级先占位）
    active.sort(key=lambda t: (EMAIL_TYPES[t.etype]["priority"], t._preferred))

    occupied: dict[str, set] = defaultdict(set)      # user_id -> 已占用日期
    placed: list[Trigger] = []                        # 已落位的触发
    a_count_week: dict[tuple[str, date], int] = defaultdict(int)  # 用户活跃邮件周计数

    for t in active:
        # 客户阶段约束：已建联停 C；已转化停 A、C；已合作全停（含 D）
        stage = t.stage or "none"
        rule = STAGE_RULES.get(stage, STAGE_RULES["none"])
        if t.etype in rule["skip"]:
            continue

        # C 静默窗：注册后 7 天内不打 C
        if t.etype == "C" and t.registered_on:
            if (t.event_date - t.registered_on).days < QUIET_DAYS_FOR_C:
                continue

        send_date = _next_free_date(occupied[t.user_id], t._preferred)

        # D 召回冷却：距上次召回不足 RECALL_COOLDOWN_DAYS 天则跳过
        if t.etype == "D" and t.last_recall_on:
            if (send_date - t.last_recall_on).days < RECALL_COOLDOWN_DAYS:
                continue

        # 检查 A 周上限（按阶段动态：未建联3 / 已建联2）
        if t.etype == "A":
            a_cap = rule["a_weekly_cap"]
            monday = send_date - timedelta(days=send_date.weekday())
            wk_key = (t.user_id, monday)
            if a_count_week[wk_key] >= a_cap:
                # 本周已满，顺延到下周一同用户空闲日（简化：跳过本周，落下周首空日）
                send_date = _next_free_date(occupied[t.user_id], monday + timedelta(days=7))

        # 占位
        occupied[t.user_id].add(send_date)
        if t.etype == "A":
            monday = send_date - timedelta(days=send_date.weekday())
            a_count_week[(t.user_id, monday)] += 1
        t._send = send_date
        t._deferred = (send_date > t._preferred)   # 因当日被占/周上限而向后顺延才标记
        placed.append(t)

    # 行为合并：仅当某触发被真正顺延(_deferred)时，若其事件日早于同用户更高优先级
    # 邮件的发送日，则把它的行为并入那封更高优先级邮件（避免行为丢失）。
    for t in placed:
        if not getattr(t, "_deferred", False):
            continue
        for cand in placed:
            if cand is t or cand.user_id != t.user_id:
                continue
            if EMAIL_TYPES[cand.etype]["priority"] >= EMAIL_TYPES[t.etype]["priority"]:
                continue
            if cand._send > t.event_date:
                cand.behavior = _merge_behavior(cand.behavior, t.behavior)
                t._merged_into = cand
                break

    # 输出
    result = []
    for t in placed:
        if getattr(t, "_merged_into", None) is not None:
            continue  # 已被并入他封，不再单独发送
        result.append({
            "user_id": t.user_id,
            "send_date": t._send,
            "etype": t.etype,
            "behavior": t.behavior,
        })
    result.sort(key=lambda r: (r["user_id"], r["send_date"]))
    return result


# ============================ 历史数据去重 ============================

def dedupe_records(records: list[dict], window: int = DUP_WINDOW_DAYS,
                   priority_of: Optional[dict] = None) -> dict:
    """
    对已落库的推送记录做去重体检（2026-09-04 规则）。

    参数
    ----
    records : [{id, user_id, send_date, etype, ...}, ...]
        send_date 为 datetime.date；无日期的记录不参与去重（原样保留）。
    window : 间隔 ≤ window 天视为重复（默认 2：同 1 日 / 隔 2 日都算）。
        因此间隔 ≥3 天的多次触达（第二次触达、召回）会自动保留。
    priority_of : 可选，etype -> 优先级数值（小的更优先）。
        未传则用 EMAIL_TYPES 的内置优先级。

    返回
    ----
    {"keep": [...], "delete": [...], "groups": {user_id: [[保留, 删1, 删2], ...]}}
    保留策略：同一重复簇内保留优先级最高的；优先级相同则保留最早的。
    """
    prio = priority_of or {k: v["priority"] for k, v in EMAIL_TYPES.items()}

    by_user: dict[str, list[dict]] = defaultdict(list)
    skipped: list[dict] = []          # 无日期，不参与去重
    for r in records:
        if r.get("send_date") is None:
            skipped.append(r)
        else:
            by_user[r["user_id"]].append(r)

    keep, delete = list(skipped), []
    groups: dict[str, list[list[dict]]] = defaultdict(list)

    for uid, items in by_user.items():
        items = sorted(items, key=lambda r: r["send_date"])
        cluster: list[dict] = [items[0]]
        for prev, cur in zip(items, items[1:]):
            gap = (cur["send_date"] - prev["send_date"]).days
            if gap <= window:
                cluster.append(cur)                 # 间隔 ≤2 天 → 同一重复簇
            else:
                groups[uid].append(cluster)         # 间隔 ≥3 天 → 正常多次触达，切簇
                cluster = [cur]
        groups[uid].append(cluster)

        for cl in groups[uid]:
            # 优先级小的胜出；同级取日期早的
            winner = min(cl, key=lambda r: (prio.get(r.get("etype"), 99), r["send_date"]))
            keep.append(winner)
            for r in cl:
                if r is not winner:
                    delete.append(r)

    return {"keep": keep, "delete": delete, "groups": dict(groups)}


# ============================ 演示 ============================
if __name__ == "__main__":
    from datetime import date
    d0 = date(2026, 9, 10)  # 假设某用户注册日

    # 场景：user:164 注册当天浏览了阿联酋内容，次日又活跃，且是高价值 C 用户
    demo = [
        Trigger("user:164", "R", d0, behavior={"country": "UAE"}, registered_on=d0),
        Trigger("user:164", "A", d0, behavior={"views": ["uae-labor-law"]}, registered_on=d0),  # T+0 活跃
        Trigger("user:164", "W", d0, behavior={"country": "UAE"}, registered_on=d0),            # T+1 欢迎
        Trigger("user:164", "A", d0 + timedelta(days=1), behavior={"downloads": ["uae-wps.pdf"]}, registered_on=d0),  # T+1 又活跃
        Trigger("user:164", "C", d0 + timedelta(days=2), behavior={"topic": "eor"}, registered_on=d0),  # T+2 二次触达(静默窗内应被拦)
        # 另一个老用户：已建联 -> 应停 C，A 周上限 2
        Trigger("user:120", "A", d0, behavior={"views": ["dubai-visa"]}, registered_on=d0 - timedelta(days=60), stage="connected"),
        Trigger("user:120", "C", d0, behavior={"topic": "eor"}, registered_on=d0 - timedelta(days=60), stage="connected"),
        # 已转化用户：应停 A、C，只发 R/W
        Trigger("user:130", "R", d0, behavior={"country": "SG"}, registered_on=d0 - timedelta(days=30), stage="converted"),
        Trigger("user:130", "W", d0, behavior={"country": "SG"}, registered_on=d0 - timedelta(days=30), stage="converted"),
        Trigger("user:130", "A", d0, behavior={"views": ["sg-payroll"]}, registered_on=d0 - timedelta(days=30), stage="converted"),
        Trigger("user:130", "C", d0, behavior={"topic": "eor"}, registered_on=d0 - timedelta(days=30), stage="converted"),
        # 已合作用户：自动化全停（R/W/A/C 都不发，转 CSM/交付）
        Trigger("user:200", "R", d0, behavior={"country": "JP"}, registered_on=d0 - timedelta(days=90), stage="cooperating"),
        Trigger("user:200", "W", d0, behavior={"country": "JP"}, registered_on=d0 - timedelta(days=90), stage="cooperating"),
        Trigger("user:200", "A", d0, behavior={"views": ["jp-visa"]}, registered_on=d0 - timedelta(days=90), stage="cooperating"),
        Trigger("user:200", "C", d0, behavior={"topic": "eor"}, registered_on=d0 - timedelta(days=90), stage="cooperating"),
    ]

    print("=== 排程结果（每用户每日最多 1 封，含客户阶段分层）===")
    for r in schedule(demo):
        print(f"  {r['user_id']:<10} {r['send_date']}  [{r['etype']}]  行为={r['behavior']}")

    coop = [r for r in schedule(demo) if r["user_id"] == "user:200"]
    print(f"\n已合作用户 user:200 命中邮件数: {len(coop)}  （应为 0：自动化全停，转 CSM）")
    assert len(coop) == 0, "已合作用户不应收到任何自动化邮件"

    # 校验：同用户同日不重复
    seen = set()
    for r in schedule(demo):
        key = (r["user_id"], r["send_date"])
        assert key not in seen, f"冲突: {key}"
        seen.add(key)
    print("\n校验通过：无同用户同日重复。")

    # ---------- D 类召回校验 ----------
    print("\n" + "=" * 60)
    print("=== D 类「5 日未活跃召回」校验 ===")
    recall_demo = [
        # 未建联：最后活跃 8/30 → 发送日 = 8/30 + 5 = 9/4
        Trigger("user:301", "D", date(2026, 8, 30), behavior={"country": "UAE"}, stage="none"),
        # 已建联：召回是例外 → 应照发（C 类被停，D 类不停）
        Trigger("user:302", "D", date(2026, 8, 29), behavior={"country": "TH"},
                registered_on=date(2026, 5, 1), stage="connected"),
        # 已转化：召回是例外 → 应照发
        Trigger("user:303", "D", date(2026, 8, 28), behavior={"country": "SA"},
                registered_on=date(2026, 4, 1), stage="converted"),
        # 已合作：全停（含 D）→ 不应出现
        Trigger("user:304", "D", date(2026, 8, 28), behavior={"country": "JP"},
                registered_on=date(2026, 1, 1), stage="cooperating"),
        # 召回冷却：上次召回 9/1，本次算得发送日 9/2，间隔 1 天 < 30 → 应被拦
        Trigger("user:305", "D", date(2026, 8, 28), behavior={"country": "VN"},
                last_recall_on=date(2026, 9, 1)),
    ]
    out = schedule(recall_demo)
    for r in out:
        print(f"  {r['user_id']:<10} {r['send_date']}  [{r['etype']} 召回]  行为={r['behavior']}")

    ids = {r["user_id"] for r in out}
    assert "user:301" in ids, "未建联用户应触发 D 类召回"
    assert "user:302" in ids, "已建联用户召回是例外，应照发 D"
    assert "user:303" in ids, "已转化用户召回是例外，应照发 D"
    assert "user:304" not in ids, "已合作用户应全停（含 D）"
    assert "user:305" not in ids, "召回冷却期内不应重复召回"
    d301 = next(r for r in out if r["user_id"] == "user:301")
    assert d301["send_date"] == date(2026, 9, 4), "D 应落在最后活跃日 +5 天"
    print("\n校验通过：D 类召回规则全部符合预期（5 日未活跃触发 / 已建联已转化例外照发 / 已合作全停 / 30 天冷却）。")

    # ---------- 历史去重校验 ----------
    print("\n" + "=" * 60)
    print("=== 历史数据去重校验（间隔 ≤2 天删，≥3 天留）===")
    hist = [
        # user:400 同日重复（间隔 0）→ 删 1 条，保留 A（优先级高于 B）
        {"id": "r1", "user_id": "user:400", "send_date": date(2026, 8, 28), "etype": "A"},
        {"id": "r2", "user_id": "user:400", "send_date": date(2026, 8, 28), "etype": "B"},
        # user:401 隔 2 天（间隔 2）→ 删 1 条
        {"id": "r3", "user_id": "user:401", "send_date": date(2026, 8, 28), "etype": "A"},
        {"id": "r4", "user_id": "user:401", "send_date": date(2026, 8, 30), "etype": "C"},
        # user:402 隔 3 天（间隔 3）→ 正常二次触达，两条都保留
        {"id": "r5", "user_id": "user:402", "send_date": date(2026, 8, 28), "etype": "A"},
        {"id": "r6", "user_id": "user:402", "send_date": date(2026, 8, 31), "etype": "C"},
        # user:403 隔 10 天 → 正常召回，两条都保留
        {"id": "r7", "user_id": "user:403", "send_date": date(2026, 8, 20), "etype": "A"},
        {"id": "r8", "user_id": "user:403", "send_date": date(2026, 8, 30), "etype": "D"},
        # 无日期的不参与去重
        {"id": "r9", "user_id": "user:404", "send_date": None, "etype": "A"},
    ]
    # 飞书表用 A/B/C/D/存量，补一个 B 的等价优先级映射
    prio_map = {**{k: v["priority"] for k, v in EMAIL_TYPES.items()}, "B": 2}
    res = dedupe_records(hist, window=2, priority_of=prio_map)
    print(f"  保留 {len(res['keep'])} 条: {sorted(r['id'] for r in res['keep'])}")
    print(f"  删除 {len(res['delete'])} 条: {sorted(r['id'] for r in res['delete'])}")

    keep_ids = {r["id"] for r in res["keep"]}
    del_ids = {r["id"] for r in res["delete"]}
    assert keep_ids == {"r1", "r3", "r5", "r6", "r7", "r8", "r9"}, f"保留集不符: {keep_ids}"
    assert del_ids == {"r2", "r4"}, f"删除集不符: {del_ids}"
    print("\n校验通过：同日/隔2日重复已删，隔3天及以上的二次触达与召回完整保留。")
