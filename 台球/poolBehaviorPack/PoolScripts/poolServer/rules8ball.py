# -*- coding: utf-8 -*-
# ============================================================
#  台球 — 八球规则
#  纯函数 + 一个字典状态，不碰引擎，方便离线测
#
#  规则（简化过的、能玩的版本）：
#    · 开球之后台面是「开放」的，谁先合法进球谁定组（全色 / 花色）
#    · 进了自己组的球 → 接着打；没进 / 犯规 → 换人
#    · 白球落袋 / 第一下没碰到球 / 先碰到别人的球 → 犯规，换人
#    · 自己组的球全清了再进 8 号 → 赢；提前进 8 号 → 输
# ============================================================
from PoolScripts.poolCommon import constants as C


def new_state(seatIds):
    return {
        "seats": list(seatIds),
        "turn": 0,              # 现在是 seats 里第几个人的回合
        "groups": {},           # seatId -> None / "solids" / "stripes"
        "open": True,           # 台面还没定组
        "breakDone": False,
        "winner": None,         # seatId
        "foul": False,
        "msg": u"",
    }


def group_of(num):
    if num in C.SOLIDS:
        return "solids"
    if num in C.STRIPES:
        return "stripes"
    return None


def other_group(g):
    return "stripes" if g == "solids" else "solids"


def on_table(sim, group):
    u"""这一组还剩几颗在台面上"""
    nums = C.SOLIDS if group == "solids" else C.STRIPES
    n = 0
    for b in sim.balls:
        if b.num in nums and b.active:
            n += 1
    return n


def my_group(state, seatId):
    return state["groups"].get(seatId)


def apply(state, sim, shooterId):
    u"""把这一杆的结果记到 state 上。

    返回一个结果字典，服务端拿它去广播。
    本函数会修改 state 和 sim（该摆白球就摆）。
    """
    out = {"foul": False, "continueTurn": False, "assigned": None,
           "winner": None, "msg": u"", "cueReplaced": False}
    if state.get("winner"):
        return out
    seats = state["seats"]
    if shooterId not in seats:
        return out

    potted = [n for n in sim.pottedThisShot if n != 0]
    cuePotted = bool(sim.cuePotted)
    firstHit = sim.firstHit
    mine = my_group(state, shooterId)
    isBreak = not state["breakDone"]

    foul = False
    # ---- 犯规判定 ----
    if cuePotted:
        foul = True
        out["msg"] = u"白球落袋，换人"
    if firstHit < 0:
        foul = True
        out["msg"] = u"白球没有碰到任何球，换人"
    if (not foul) and mine and (not state["open"]):
        own = C.SOLIDS if mine == "solids" else C.STRIPES
        left = on_table(sim, mine)
        if left == 0:
            if firstHit != C.EIGHT:
                foul = True
                out["msg"] = u"该打 8 号了，先碰到了别的球"
        elif firstHit == C.EIGHT or firstHit not in own:
            foul = True
            out["msg"] = u"先碰到了不该碰的球，换人"
    if (not foul) and state["open"] and firstHit == C.EIGHT and not isBreak:
        foul = True
        out["msg"] = u"台面还没定组，不能先碰 8 号"

    # ---- 8 号球 ----
    if C.EIGHT in potted:
        left = 0 if not mine else on_table(sim, mine)
        legalEight = (mine is not None) and (left == 0) and (not foul) and (not state["open"])
        if legalEight:
            state["winner"] = shooterId
            out["winner"] = shooterId
            out["msg"] = u"黑 8 入袋，赢了！"
        else:
            other = None
            for sid in seats:
                if sid != shooterId:
                    other = sid
                    break
            state["winner"] = other
            out["winner"] = other
            out["msg"] = u"黑 8 提前入袋，输了一局"
        state["breakDone"] = True
        out["foul"] = foul
        return out

    # ---- 定组 ----
    if state["open"] and (not foul) and potted and (not isBreak or len(potted) > 0):
        g = group_of(potted[0])
        if g and len(seats) >= 2:
            state["groups"][shooterId] = g
            for sid in seats:
                if sid != shooterId:
                    state["groups"][sid] = other_group(g)
            state["open"] = False
            out["assigned"] = g
            out["msg"] = (u"你这一组是「全色 1-7」" if g == "solids"
                          else u"你这一组是「花色 9-15」")
        elif g and len(seats) == 1:
            state["groups"][shooterId] = g
            state["open"] = False
            out["assigned"] = g

    # ---- 该不该换人 ----
    # 注意：分组刚刚才定下来，这里必须重新读一次，
    # 不能用进来时读的那个 mine（那时候还是 None）
    mineNow = my_group(state, shooterId)
    if foul:
        cont = False
    elif state["open"]:
        cont = len(potted) > 0
    elif mineNow:
        own = C.SOLIDS if mineNow == "solids" else C.STRIPES
        cont = any(n in own for n in potted)
    else:
        cont = len(potted) > 0
    out["foul"] = foul
    out["continueTurn"] = cont

    # ---- 白球落袋：摆回开球线附近 ----
    if cuePotted:
        sim.putCue(C.HeadSpotX, C.TableWidth * 0.5)
        out["cueReplaced"] = True

    state["breakDone"] = True
    if not cont:
        state["turn"] = (state["turn"] + 1) % len(seats)
    return out
