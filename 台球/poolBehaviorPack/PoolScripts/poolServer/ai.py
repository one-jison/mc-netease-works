# -*- coding: utf-8 -*-
# ============================================================
#  台球 — 人机对手
#  思路：先只用几何筛出「大概能打进的几杆」，再拿复制体真打一遍挑最好的。
#       全部候选都真打的话太慢，所以先筛后试。
# ============================================================
import math

from PoolScripts.poolCommon import constants as C
from PoolScripts.poolCommon import vecmath as V
from PoolScripts.poolCommon import aim as A
from PoolScripts.poolCommon.physics import make_clone


def _legal_targets(sim, myGroup, openTable):
    u"""现在能打哪几颗球"""
    on = [b.num for b in sim.balls if b.active and b.num != 0]
    if openTable or myGroup is None:
        return [n for n in on if n != C.EIGHT] or ([C.EIGHT] if C.EIGHT in on else [])
    own = C.SOLIDS if myGroup == "solids" else C.STRIPES
    left = [n for n in on if n in own]
    if left:
        return left
    return [C.EIGHT] if C.EIGHT in on else []


def _power_for(dist):
    u"""要让球滚 dist 米，大概要多大力度"""
    need = math.sqrt(2.0 * C.FrictionDecel * max(0.12, dist)) * 1.15
    p = (need - C.MinShotSpeed) / (C.MaxShotSpeed - C.MinShotSpeed)
    return V.clamp(p, 0.22, 0.88)


def choose_shot(sim, myGroup, openTable, maxTry=6):
    u"""返回 (dirx, diry, power, sx, sy)；实在没得选就随便碰一下"""
    cue = sim.ball(0)
    if cue is None or not cue.active:
        return None
    targets = _legal_targets(sim, myGroup, openTable)
    if not targets:
        return None
    pockets = C.Pockets()

    cand = []
    for num in targets:
        tb = sim.ball(num)
        if tb is None or not tb.active:
            continue
        for (px, py) in pockets:
            res = A.aim_at(sim, num, px, py)
            if res is None:
                continue
            dx, dy, (cx, cy) = res
            # 目标球要去的方向 和 白球来的方向 的夹角（切角），太大就打不准
            odx, ody = V.norm(px - tb.x, py - tb.y)
            vdx, vdy = V.norm(tb.x - cue.x, tb.y - cue.y)
            cosr = V.clamp(odx * vdx + ody * vdy, -1.0, 1.0)
            if cosr < 0.34:
                continue
            d1 = V.length(cx - cue.x, cy - cue.y)
            d2 = V.length(px - tb.x, py - tb.y)
            score = cosr * 2.0 - (d1 + d2) * 0.9
            cand.append((score, num, dx, dy, d1 + d2))
    cand.sort(key=lambda c: -c[0])

    for (score, num, dx, dy, dist) in cand[:maxTry]:
        power = _power_for(dist)
        trial = make_clone(sim)
        trial.shoot(dx, dy, power)
        trial.run()
        if num in trial.pottedThisShot and (0 not in trial.pottedThisShot):
            # 顺手把白球停的位置也考虑一下
            return (dx, dy, power, 0.0, 0.0)

    # 一个都没把握：朝最容易碰到的那颗轻轻碰一下
    near = None
    bestd = 1e9
    for num in targets:
        tb = sim.ball(num)
        if tb is None or not tb.active:
            continue
        d = V.length(tb.x - cue.x, tb.y - cue.y)
        if d < bestd:
            bestd = d
            near = num
    if near is None:
        return None
    tb = sim.ball(near)
    dx, dy = V.norm(tb.x - cue.x, tb.y - cue.y)
    return (dx, dy, V.clamp(_power_for(bestd) * 0.75, 0.2, 0.6), 0.0, 0.0)
