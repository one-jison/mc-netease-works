# -*- coding: utf-8 -*-
# ============================================================
#  台球 — 瞄准辅助线
#  纯数学：给一个方向和一颗白球，算出
#    · 白球会走到哪（打空 / 撞库 / 撞到哪颗球）
#    · 撞到球的话，目标球会往哪个方向走
#    · 打库边的话，会往哪个方向弹
#  客户端拿它画虚线，服务端也能拿它做 AI 判断
# ============================================================
from PoolScripts.poolCommon import constants as C
from PoolScripts.poolCommon import vecmath as V


class Aim(object):
    __slots__ = ("sx", "sy", "dx", "dy", "kind", "hx", "hy",
                 "ballNum", "objDx", "objDy", "objX", "objY",
                 "refDx", "refDy")

    def __init__(self):
        self.sx = self.sy = 0.0
        self.dx, self.dy = 1.0, 0.0
        self.kind = "none"       # none / ball / cushion
        self.hx = self.hy = 0.0  # 白球球心停下来的位置
        self.ballNum = -1
        self.objDx = self.objDy = 0.0
        self.objX = self.objY = 0.0
        self.refDx = self.refDy = 0.0


def solve(sim, dirx, diry, ignoreNum=0):
    u"""从白球当前位置，顺着 dir 方向算一条辅助线"""
    a = Aim()
    cue = sim.ball(0)
    if cue is None:
        return a
    a.sx, a.sy = cue.x, cue.y
    a.dx, a.dy = V.norm(dirx, diry)

    # 先放一个「比桌面里任何一段可能距离都长」的候选，后面直接比大小。
    # 这样 best 的类型从头到尾都是元组，打包机上的静态检查
    # 就不会再把它当成一个取不了下标的 None 而卡住上传。
    best = (C.TableLength + C.TableWidth, "none", None)   # (距离, 类型, 数据)
    # 1) 先看会撞到哪颗球
    for b in sim.balls:
        if not b.active or b.num == ignoreNum or b.num == 0:
            continue
        t = V.ray_circle(cue.x, cue.y, a.dx, a.dy, b.x, b.y, C.BallDiameter)
        if t is not None and t > 1e-6:
            if t < best[0]:
                best = (t, "ball", b)
    # 2) 再看会撞到哪条库边
    lo = C.BallRadius
    t = V.ray_aabb(cue.x, cue.y, a.dx, a.dy,
                   lo, lo, C.TableLength - lo, C.TableWidth - lo)
    if t is not None and t > 1e-6:
        if t < best[0]:
            best = (t, "cushion", None)

    if best[1] == "none":
        a.kind = "none"
        a.hx = cue.x + a.dx * C.TableLength
        a.hy = cue.y + a.dy * C.TableLength
        return a

    t, kind, b = best
    a.hx = cue.x + a.dx * t
    a.hy = cue.y + a.dy * t
    a.kind = kind

    if kind == "ball":
        a.ballNum = b.num
        a.objX, a.objY = b.x, b.y
        # 目标球顺着两颗球心连线走
        ox = b.x - a.hx
        oy = b.y - a.hy
        a.objDx, a.objDy = V.norm(ox, oy)
        # 白球留下切线方向
        tdx = a.dx - (a.dx * a.objDx + a.dy * a.objDy) * a.objDx
        tdy = a.dy - (a.dx * a.objDx + a.dy * a.objDy) * a.objDy
        a.refDx, a.refDy = V.norm(tdx, tdy)
    else:
        # 撞库：按撞到的是哪条边反弹
        lo2 = C.BallRadius + 1e-6
        if a.hx <= C.BallRadius + 1e-4 and a.dx < 0:
            a.refDx, a.refDy = -a.dx, a.dy
        elif a.hx >= C.TableLength - C.BallRadius - 1e-4 and a.dx > 0:
            a.refDx, a.refDy = -a.dx, a.dy
        elif a.hy <= C.BallRadius + 1e-4 and a.dy < 0:
            a.refDx, a.refDy = a.dx, -a.dy
        elif a.hy >= C.TableWidth - C.BallRadius - 1e-4 and a.dy > 0:
            a.refDx, a.refDy = a.dx, -a.dy
        else:
            a.refDx, a.refDy = -a.dx, -a.dy
    return a


def aim_at(sim, targetNum, targetX, targetY, maxErr=0.16):
    u"""反着算：想让 targetNum 号球滚向 (targetX, targetY)，白球该朝哪打。

    台球里的「假想球」打法：把白球球心瞄准到
    「目标球球心沿着目标球要去的方向、往回退一个球直径」那个点上。
    返回 (dirx, diry, 白球球心要到达的位置) ；打不到返回 None。
    """
    cue = sim.ball(0)
    tb = sim.ball(targetNum)
    if cue is None or tb is None or not cue.active or not tb.active:
        return None
    ox, oy = V.norm(targetX - tb.x, targetY - tb.y)
    # 白球撞上目标球时，球心应该落在哪
    cx = tb.x - ox * C.BallDiameter
    cy = tb.y - oy * C.BallDiameter
    dx = cx - cue.x
    dy = cy - cue.y
    d = V.length(dx, dy)
    if d < 1e-6:
        return None
    dx, dy = dx / d, dy / d
    # 白球必须是从目标球的另一侧推进去的；
    # 切角太大（超过大约 78 度）就是一杆根本打不出来的球，直接不给方向
    if (dx * ox + dy * oy) < 0.20:
        return None
    # 这条路线别先把别的球撞了
    check = solve(sim, dx, dy)
    if check.kind == "ball" and check.ballNum != targetNum:
        return None
    if check.kind == "cushion":
        return None
    return (dx, dy, (cx, cy))
