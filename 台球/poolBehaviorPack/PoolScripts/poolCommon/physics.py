# -*- coding: utf-8 -*-
# ============================================================
#  台球 — 二维物理（客户端和服务端跑的是同一段代码）
#
#  为什么要两边都跑：
#    服务端是唯一的“真相”（谁该打、进了几颗、归谁），但它不画面。
#    客户端收到“某人朝某方向用某力度开球”之后，自己把这一杆算一遍，
#    画面就当场动起来了 —— 不用等网络，杆杆跟手。
#    因为物理是定步长、没有随机数的，两边算出来的结果一模一样。
#
#  碰撞用「连续检测」（先算出两颗球正好碰到的那一瞬间，退到那里再弹），
#  不是「走一步看有没有叠上」。台球全是精细几何，走一步再看的话，
#  薄切球会因为接触点差了小半个球而擦袋而出 —— 那就不好玩了。
# ============================================================
import math

from PoolScripts.poolCommon import constants as C
from PoolScripts.poolCommon import vecmath as V

EPS = 1e-9
MAX_HITS_PER_STEP = 32      # 一步里最多处理这么多次碰撞，防死循环


class Ball(object):
    __slots__ = ("num", "x", "y", "vx", "vy", "active")

    def __init__(self, num, x=0.0, y=0.0):
        self.num = num          # 0 = 白球，1-15 = 目标球
        self.x = x
        self.y = y
        self.vx = 0.0
        self.vy = 0.0
        self.active = True      # False = 已经落袋，不参与碰撞

    def moving(self):
        return self.active and (abs(self.vx) > 1e-9 or abs(self.vy) > 1e-9)

    def stop(self):
        self.vx = 0.0
        self.vy = 0.0


class Sim(object):
    u"""一桌球的完整状态 + 物理"""

    def __init__(self):
        self.balls = []
        self.pockets = C.Pockets()
        # 这一杆里发生过的事（给规则模块看）
        self.pottedThisShot = []      # 这一杆落袋的球号，按先后
        self.firstHit = -1            # 白球第一下撞到的球号
        self.cuePotted = False        # 白球是不是落袋了
        self.cushionHits = 0          # 撞库边次数
        self.spinSide = 0.0
        self.spinVert = 0.0
        self.shotDir = (1.0, 0.0)
        self.breakShot = True
        self._acc = 0.0
        self.reset()

    # ---------------- 摆球 ----------------
    def reset(self, cueX=None, cueY=None):
        self.balls = [Ball(0)]
        for n in range(1, 16):
            self.balls.append(Ball(n))
        self.balls[0].x = C.HeadSpotX if cueX is None else cueX
        self.balls[0].y = C.TableWidth * 0.5 if cueY is None else cueY
        idx = 0
        dx = C.BallDiameter * 0.8660254
        rowX = 0.0
        for row in range(5):
            if row > 0:
                # 每排把间距往外微拉一点点（只能往外，不能往里，
                # 否则球会重叠）。这是写死的，两边一定一样。
                rowX += dx * (1.0 + C.RackRowGap * (1.0 + row * 0.5))
            for j in range(row + 1):
                num = C.RackOrder[idx]
                idx += 1
                b = self.ball(num)
                b.x = C.FootSpotX + rowX
                b.y = C.TableWidth * 0.5 + (j - row * 0.5) * C.BallDiameter
        self.clearShotLog()

    def clearShotLog(self):
        self.pottedThisShot = []
        self.firstHit = -1
        self.cuePotted = False
        self.cushionHits = 0
        self.spinSide = 0.0
        self.spinVert = 0.0

    def ball(self, num):
        for b in self.balls:
            if b.num == num:
                return b
        return None

    def allStop(self):
        for b in self.balls:
            if b.moving():
                return False
        return True

    def needCuePlacement(self):
        cue = self.ball(0)
        return (cue is not None) and (not cue.active)

    def putCue(self, x, y):
        u"""把白球放回台面（白球落袋之后重新摆）"""
        cue = self.ball(0)
        if cue is None:
            return
        cue.x = V.clamp(x, C.BallRadius, C.TableLength - C.BallRadius)
        cue.y = V.clamp(y, C.BallRadius, C.TableWidth - C.BallRadius)
        cue.vx = 0.0
        cue.vy = 0.0
        cue.active = True
        # 别跟别的球叠在一起
        for b in self.balls:
            if b is cue or not b.active:
                continue
            d = V.length(cue.x - b.x, cue.y - b.y)
            if d < C.BallDiameter:
                cue.x = V.clamp(cue.x + (C.BallDiameter - d) + 0.001,
                                C.BallRadius, C.TableLength - C.BallRadius)

    # ---------------- 开球 ----------------
    def shoot(self, dirx, diry, power, sx=0.0, sy=0.0):
        u"""power 是 0~1 的力度，sx 是侧塞（+右 -左），sy 是高杆/低杆（+高 -低）"""
        cue = self.ball(0)
        if cue is None or not cue.active:
            return False
        dx, dy = V.norm(dirx, diry)
        power = V.clamp(power, 0.0, 1.0)
        speed = C.MinShotSpeed + (C.MaxShotSpeed - C.MinShotSpeed) * power
        cue.vx = dx * speed
        cue.vy = dy * speed
        self.clearShotLog()
        self.spinSide = V.clamp(sx, -1.0, 1.0)
        self.spinVert = V.clamp(sy, -1.0, 1.0)
        self.shotDir = (dx, dy)
        return True

    # ==================== 走一步 ====================
    def step(self, dt):
        self._forces(dt)
        remain = dt
        for _ in range(MAX_HITS_PER_STEP):
            if remain <= EPS:
                break
            hit = self._earliest(remain)
            if hit is None:
                self._move(remain)
                remain = 0.0
                break
            t, kind, a, b = hit
            if t > EPS:
                self._move(t)
                remain -= t
            self._resolve(kind, a, b)
        if remain > EPS:
            self._move(remain)
        self._safeClamp()
        self._pockets()

    def _safeClamp(self):
        u"""保险：无论如何不能让球跑出桌面"""
        lo = C.BallRadius
        hx = C.TableLength - lo
        hy = C.TableWidth - lo
        for b in self.balls:
            if not b.active:
                continue
            if b.x < lo:
                b.x = lo
                if b.vx < 0.0:
                    b.vx = -b.vx * C.CushionRestitution
            elif b.x > hx:
                b.x = hx
                if b.vx > 0.0:
                    b.vx = -b.vx * C.CushionRestitution
            if b.y < lo:
                b.y = lo
                if b.vy < 0.0:
                    b.vy = -b.vy * C.CushionRestitution
            elif b.y > hy:
                b.y = hy
                if b.vy > 0.0:
                    b.vy = -b.vy * C.CushionRestitution

    def _forces(self, dt):
        u"""摩擦 + 加塞：先把这一小步的速度改好，再走"""
        cue = self.ball(0)
        for b in self.balls:
            if not b.active:
                continue
            sp = V.length(b.vx, b.vy)
            if sp <= C.StopSpeed:
                b.stop()
                continue
            side = 0.0
            vert = 0.0
            if (b is cue) and (self.firstHit < 0):
                side = self.spinSide
                vert = self.spinVert
            if abs(side) > 1e-6:
                nx, ny = b.vx / sp, b.vy / sp
                a = C.SideSpinCurve * side * sp
                b.vx += (-ny) * a * dt
                b.vy += (nx) * a * dt
            dec = C.FrictionDecel * (1.0 - 0.55 * vert)
            if dec < 0.05:
                dec = 0.05
            nsp = V.length(b.vx, b.vy)
            if nsp <= dec * dt:
                b.stop()
                continue
            k = (nsp - dec * dt) / nsp
            b.vx *= k
            b.vy *= k

    def _move(self, dt):
        if dt <= 0.0:
            return
        for b in self.balls:
            if not b.active:
                continue
            if b.vx == 0.0 and b.vy == 0.0:
                continue
            b.x += b.vx * dt
            b.y += b.vy * dt

    # ---------------- 下一步里最早撞上的是谁 ----------------
    def _earliest(self, dt):
        lo = C.BallRadius
        hx = C.TableLength - lo
        hy = C.TableWidth - lo
        # 虚位候选：时间比这一小步还长，任何真实碰撞都比它早、一定会把它顶掉。
        # 这样 best 的类型从头到尾都是元组，静态检查不会再当成 None。
        best = (dt + 1.0, "", None, None)
        balls = self.balls
        n = len(balls)
        for i in range(n):
            a = balls[i]
            if not a.active:
                continue
            aMoving = (a.vx != 0.0 or a.vy != 0.0)
            # --- 库边 ---
            if aMoving:
                cand = []
                if a.vx < 0.0:
                    cand.append(((lo - a.x) / a.vx, "x"))
                elif a.vx > 0.0:
                    cand.append(((hx - a.x) / a.vx, "x"))
                if a.vy < 0.0:
                    cand.append(((lo - a.y) / a.vy, "y"))
                elif a.vy > 0.0:
                    cand.append(((hy - a.y) / a.vy, "y"))
                for (t, axis) in cand:
                    if t < -EPS or t > dt:
                        continue
                    if t < best[0]:
                        best = (max(0.0, t), "cushion", a, axis)
            # --- 别的球 ---
            # 一对球只看一次（j > i），而且不管“哪一颗在动”都得看。
            # 以前这里先 `if a 不动: continue`，等于把“会动的那颗编号更大”
            # 的整对球跳过去了 —— 所以球会径直穿过前面一颗不动的球。
            for j in range(i + 1, n):
                o = balls[j]
                if not o.active:
                    continue
                if (not aMoving) and o.vx == 0.0 and o.vy == 0.0:
                    continue
                dx = o.x - a.x
                dy = o.y - a.y
                dvx = o.vx - a.vx
                dvy = o.vy - a.vy
                qa = dvx * dvx + dvy * dvy
                if qa < 1e-14:
                    # 两颗几乎一起动：只有现在就叠上了才需要推开
                    if dx * dx + dy * dy < C.BallDiameter * C.BallDiameter:
                        if best[0] > 0.0:
                            best = (0.0, "ball", a, o)
                    continue
                qb = 2.0 * (dx * dvx + dy * dvy)
                qc = dx * dx + dy * dy - C.BallDiameter * C.BallDiameter
                disc = qb * qb - 4.0 * qa * qc
                if disc < 0.0:
                    continue
                sq = disc ** 0.5
                t = (-qb - sq) / (2.0 * qa)
                if t < -EPS:
                    # 已经挨着（或叠着）了：
                    #   正在分开 -> 不是一次碰撞，不能占碰撞次数
                    #   正在靠近 -> 就是现在这一下
                    if qb >= 0.0:
                        continue
                    t = 0.0
                if t > dt:
                    continue
                if t < best[0]:
                    best = (t, "ball", a, o)
        if best[0] > dt:
            # 这一小步里谁也没撞上
            return None
        return best

    # ---------------- 处理这次碰撞 ----------------
    def _resolve(self, kind, a, b):
        if kind == "cushion":
            lo = C.BallRadius
            hx = C.TableLength - lo
            hy = C.TableWidth - lo
            if b == "x":
                if a.vx < 0.0:
                    a.x = lo + EPS
                elif a.vx > 0.0:
                    a.x = hx - EPS
                a.vx = -a.vx * C.CushionRestitution
            else:
                if a.vy < 0.0:
                    a.y = lo + EPS
                elif a.vy > 0.0:
                    a.y = hy - EPS
                a.vy = -a.vy * C.CushionRestitution
            self.cushionHits += 1
            if abs(self.spinSide) > 1e-6 and a.num == 0:
                self._spinCushion(a)
            if V.length(a.vx, a.vy) <= C.StopSpeed:
                a.stop()
            return

        # --- 球撞球 ---
        dx = b.x - a.x
        dy = b.y - a.y
        d = V.length(dx, dy)
        if d < 1e-12:
            a.x -= 0.0005
            b.x += 0.0005
            return
        nx = dx / d
        ny = dy / d
        # 数值上可能差一丁点，摆正到正好相切
        over = C.BallDiameter - d
        if over > 0.0:
            a.x -= nx * over * 0.5
            a.y -= ny * over * 0.5
            b.x += nx * over * 0.5
            b.y += ny * over * 0.5
        vn = (b.vx - a.vx) * nx + (b.vy - a.vy) * ny
        if vn > 0.0:
            return
        jimp = -(1.0 + C.BallRestitution) * vn * 0.5
        a.vx -= jimp * nx
        a.vy -= jimp * ny
        b.vx += jimp * nx
        b.vy += jimp * ny
        if a.num == 0 or b.num == 0:
            other = b.num if a.num == 0 else a.num
            if self.firstHit < 0:
                self.firstHit = other
                self._applySpinFollow()

    def _applySpinFollow(self):
        u"""白球撞到球的那一下，把高杆 / 低杆的效果使出来"""
        cue = self.ball(0)
        if cue is None or abs(self.spinVert) < 1e-6:
            return
        dx, dy = self.shotDir
        gain = C.FollowGain if self.spinVert > 0 else C.DrawGain
        s = gain * self.spinVert
        cue.vx += dx * s
        cue.vy += dy * s

    def _spinCushion(self, b):
        sp = V.length(b.vx, b.vy)
        if sp < 1e-6:
            return
        nx, ny = b.vx / sp, b.vy / sp
        a = C.SideSpinCushion * self.spinSide
        ca = V.clamp(1.0 - a * a * 0.5, -1.0, 1.0)
        sa = a
        b.vx = sp * (nx * ca - ny * sa)
        b.vy = sp * (nx * sa + ny * ca)

    # ---------------- 落袋 ----------------
    def _pockets(self):
        for b in self.balls:
            if not b.active:
                continue
            for (px, py) in self.pockets:
                if V.dist2(b.x, b.y, px, py) <= C.PocketRadius * C.PocketRadius:
                    b.active = False
                    b.stop()
                    self.pottedThisShot.append(b.num)
                    if b.num == 0:
                        self.cuePotted = True
                    break

    # ---------------- 按真实时间推进（客户端用） ----------------
    def advance(self, realDt):
        u"""realDt 是这一帧真实过去的时间。

        注意：**永远按定步长 SimStep 走**，绝对不能把 realDt 直接当 dt 传进去。
        手机掉帧的时候一次补几步就行 —— 补多少步都不影响结果，
        因为每一步的大小都一样，轨迹是同一条。
        """
        self._acc = getattr(self, "_acc", 0.0) + max(0.0, min(float(realDt), 0.25))
        n = 0
        while self._acc >= C.SimStep and n < 24:
            self.step(C.SimStep)
            self._acc -= C.SimStep
            n += 1
        if n >= 24:
            self._acc = 0.0
        return n

    # ---------------- 一杆打完 ----------------
    def run(self, maxTime=None):
        u"""一直算到所有球停下（或超时）。返回实际用的秒数。"""
        if maxTime is None:
            maxTime = C.MaxSimTime
        t = 0.0
        dt = C.SimStep
        while t < maxTime:
            if self.allStop():
                break
            self.step(dt)
            t += dt
        for b in self.balls:
            b.stop()
        return t


def make_clone(sim):
    u"""复制一桌球的状态（AI 试杆用，试完不影响真的那桌）"""
    s = Sim()
    s.balls = []
    for b in sim.balls:
        nb = Ball(b.num, b.x, b.y)
        nb.vx = b.vx
        nb.vy = b.vy
        nb.active = b.active
        s.balls.append(nb)
    s.spinSide = sim.spinSide
    s.spinVert = sim.spinVert
    s.shotDir = sim.shotDir
    s.breakShot = sim.breakShot
    s.clearShotLog()
    return s
