# -*- coding: utf-8 -*-
# ============================================================
#  台球 — 平面台球桌界面
#
#  屏幕上是俯视的一整张球桌：木边框 + 绿台布 + 六个袋口，
#  16 颗球就在台面上滚。所有坐标都由「屏幕实际大小」现算，
#  所以手机横屏、电脑大屏都是同一套布局，不会错位。
#
#  操作：
#    · 在桌面上按住拖动 → 调瞄准方向（拖到哪，球就往哪打）
#    · 拖力度条        → 调力度
#    · 拖左下角那颗白球 → 加塞（打白球的哪个点）
#    · 点【击球】      → 出杆
#
#  界面里所有位置都用「屏幕像素」算，不用百分比铺满 ——
#  铺满全屏的图在手机上会缩成一个方块（《化身HIM》那次踩过）。
# ============================================================
import math
import time

import mod.client.extraClientApi as clientApi

ScreenNode = clientApi.GetScreenNodeCls()

from PoolScripts import modConfig
from PoolScripts.poolCommon import constants as C
from PoolScripts.poolCommon import vecmath as V
from PoolScripts.poolCommon import aim as A
from PoolScripts.poolCommon.physics import Sim

TABLE = "/root/table"
TABLE_TOUCH = "/root/tableTouch"
RING = "/root/ring"
# 瞄准线不是「一整条会转的线」，而是一串小圆点 —— 原因见 _dots() 的注释
AIM = "/root/aim%d"
AIM2 = "/root/aim2_%d"
AIM_DOTS = 22
AIM2_DOTS = 10
BALL = "/root/ball%d"
POWER_FRAME = "/powerFrame"
POWER_BG = "/powerBg"
POWER_FILL = "/powerFill"
POWER_TOUCH = "/powerTouch"
POW_LABEL = "/powLabel"
SPIN_BG = "/spinBg"
SPIN_DOT = "/spinDot"
SPIN_TOUCH = "/spinTouch"
SHOOT_BTN = "/shootBtn"
EXIT_BTN = "/exitBtn"
RESET_BTN = "/resetBtn"
SOLO_BTN = "/soloBtn"
AI_BTN = "/aiBtn"
MSG = "/msgLabel"
TITLE = "/modeTitle"


class PoolScreen(ScreenNode):

    def __init__(self, namespace, name, param):
        ScreenNode.__init__(self, namespace, name, param)
        self.sim = Sim()
        self.room = {}
        self.seat = 0
        self.phase = "wait"
        self.turn = 0
        self.names = []
        self.groups = []
        self.myGroup = ""
        self.msg = u""
        self.aimDx, self.aimDy = 1.0, 0.0
        self.power = 0.55
        self.spinX = 0.0
        self.spinY = 0.0
        self.g = {}
        self.ready = False
        self.lastT = 0.0
        self.needBalls = True
        self.needAim = True
        self.needMeters = True
        self.needLabels = True
        self.pendingBalls = None
        self.aiming = False
        self.spinning = False
        self.powering = False
        self.onShoot = None
        self.onExit = None
        self.onReset = None
        self.onMode = None
        self.lastShotAt = 0.0
        self.mOpen = False
        self._reopen = 0
        self.wired = False

    # ==================== 建界面 ====================
    def Create(self):
        self.ready = False
        self.lastT = 0.0
        self.wired = False
        self._tryWire()
        self._visible(RING, False)
        self._hideDots()
        self.g = {}
        self.needLabels = True
        self.needBalls = True
        self.needAim = True
        self.needMeters = True

    def IsBuilt(self):
        # 界面骨架没建出来时返回 False，外面会拆掉重建（和那颗进入台球按钮一样的做法）
        try:
            return self.GetBaseUIControl("/root") is not None
        except Exception:
            return False

    def _wire(self):
        # 每颗按钮各接各的回调。
        # 接线方式沿用《伪上帝》里已经跑通的那套：
        # AddTouchEventParams + SetButtonTouchUpCallback。
        for path, cb in ((SHOOT_BTN, self.OnShootTouch),
                         (EXIT_BTN, self._touchExit),
                         (RESET_BTN, self._touchReset),
                         (SOLO_BTN, self._touchSolo),
                         (AI_BTN, self._touchAi)):
            self._wireBtn(path, cb, False)
        # 这三块要按住拖动，所以按下 / 拖动 / 抬起都接上
        for path, cb in ((TABLE_TOUCH, self.OnTableTouch),
                         (POWER_TOUCH, self.OnPowerTouch),
                         (SPIN_TOUCH, self.OnSpinTouch)):
            self._wireBtn(path, cb, True)

    def _wireBtn(self, path, cb, drag):
        try:
            btn = self.GetBaseUIControl(path).asButton()
            btn.AddTouchEventParams({"isSwallow": True})
            btn.SetButtonTouchDownCallback(cb)
            btn.SetButtonTouchUpCallback(cb)
            if drag:
                btn.SetButtonTouchMoveCallback(cb)
                btn.SetButtonTouchCancelCallback(cb)
        except Exception:
            pass

    def _tryWire(self):
        # 界面骨架有时是稍后才建好的，那会儿接线会静悄悄失败，
        # 表现就是「看得见球桌但按哪都不动」。这里补一次。
        if self.wired:
            return
        try:
            if self.GetBaseUIControl("/root") is None:
                return
        except Exception:
            return
        self.wired = True
        self._wire()
        self._setButtonLabels()
        self._label(POW_LABEL, u"力度 50%")

    def _isUp(self, args):
        if args is None:
            return False
        try:
            return args.get("TouchEvent") == self._enum().TouchUp
        except Exception:
            return True

    def _touchExit(self, args):
        if not self._isUp(args) or self.onExit is None:
            return
        try:
            self.onExit()
        except Exception:
            pass

    def _touchReset(self, args):
        if not self._isUp(args) or self.onReset is None:
            return
        try:
            self.onReset()
        except Exception:
            pass

    def _touchSolo(self, args):
        if not self._isUp(args) or self.onMode is None:
            return
        try:
            self.onMode("solo")
        except Exception:
            pass

    def _touchAi(self, args):
        if not self._isUp(args) or self.onMode is None:
            return
        try:
            self.onMode("ai")
        except Exception:
            pass

    def _setButtonLabels(self):
        # 界面文件里一个中文都没有（怕编码出岔子整份读不进去），
        # 按钮上的字全部在这儿写进去。
        for path, txt in ((SHOOT_BTN, u"击球"),
                          (EXIT_BTN, u"离开球桌"),
                          (RESET_BTN, u"重新摆球"),
                          (SOLO_BTN, u"单人练习"),
                          (AI_BTN, u"人机对战")):
            self._label(path + "/button_label", txt)

    def SetCallbacks(self, onShoot, onExit, onReset, onMode):
        self.onShoot = onShoot
        self.onExit = onExit
        self.onReset = onReset
        self.onMode = onMode

    # ==================== 整层界面的开 / 关 ====================
    OPEN_PATHS = ("/root", "/powerFrame", "/powerBg", "/powerFill",
                  "/powerTouch", "/powLabel", "/spinBg",
                  "/spinDot", "/spinTouch", "/shootBtn", "/exitBtn",
                  "/resetBtn", "/soloBtn", "/aiBtn", "/msgLabel", "/modeTitle")

    def SetOpen(self, on):
        on = bool(on)
        self.mOpen = on
        for p in self.OPEN_PATHS:
            self._visible(p, on)
        if on:
            # 刚打开的时候引擎偶尔还没挂上控件，过几帧再确认一次
            self.needBalls = True
            self.needAim = True
            self.needMeters = True
            self.needLabels = True
            self._reopen = 12
        else:
            self._reopen = 0

    def IsOpen(self):
        return bool(getattr(self, "mOpen", False))

    def ReassertOpen(self):
        if not self.IsOpen():
            return
        for p in self.OPEN_PATHS:
            self._visible(p, True)
        self.needBalls = True
        self.needAim = True
        self.needMeters = True
        self.needLabels = True

    # ==================== 布局 ====================
    def _size(self, path, wh):
        try:
            self.GetBaseUIControl(path).SetSize((float(wh[0]), float(wh[1])))
        except Exception:
            pass

    def _pos(self, path, xy):
        try:
            self.GetBaseUIControl(path).SetPosition((float(xy[0]), float(xy[1])))
        except Exception:
            pass

    def _visible(self, path, on):
        try:
            self.GetBaseUIControl(path).SetVisible(bool(on))
        except Exception:
            pass

    def _label(self, path, text):
        try:
            self.GetBaseUIControl(path).asLabel().SetText(u"%s" % (text or u""))
        except Exception:
            pass

    def _global(self, path):
        try:
            return self.GetBaseUIControl(path).GetGlobalPosition()
        except Exception:
            return None

    def _ensureLayout(self):
        if self.g and self._stillFits():
            return True
        try:
            root = self.GetBaseUIControl("/root")
            if root is None:
                return False
            W, H = root.GetSize()
        except Exception:
            return False
        try:
            W, H = float(W), float(H)
        except Exception:
            return False
        if W < 160.0 or H < 120.0:
            return False
        self._buildLayout(W, H)
        return True

    def _stillFits(self):
        try:
            W, H = self.GetBaseUIControl("/root").GetSize()
            return abs(float(W) - self.g["W"]) < 1.0 and abs(float(H) - self.g["H"]) < 1.0
        except Exception:
            return False

    def _buildLayout(self, W, H):
        S = min(W, H)
        # ---- 球桌 ----
        aspect = C.UICanvasW / C.UICanvasH
        tw = min(W * 0.86, H * 0.62 * aspect)
        th = tw / aspect
        tx = (W - tw) * 0.5
        ty = H * 0.045
        rx = C.UIRail / C.UICanvasW * tw
        ry = C.UIRail / C.UICanvasH * th
        rw = tw - 2.0 * rx
        rh = th - 2.0 * ry
        g = {"W": W, "H": H, "S": S,
             "tx": tx, "ty": ty, "tw": tw, "th": th,
             "rx": rx, "ry": ry, "rw": rw, "rh": rh,
             "ballD": max(6.0, C.BallDiameter / C.TableLength * rw),
             "lineH": max(3.0, S * 0.013),
             "lineH2": max(2.0, S * 0.009)}
        self._size(TABLE, (tw, th))
        self._pos(TABLE, (tx, ty))
        self._size(TABLE_TOUCH, (tw, th))
        self._pos(TABLE_TOUCH, (tx, ty))
        bd = g["ballD"]
        for n in range(16):
            self._size(BALL % n, (bd, bd))

        # ---- 底部一排 ----
        barY = ty + th + H * 0.045
        pad = W * 0.03
        spinS = S * 0.155
        g["spinS"] = spinS
        spinX = pad
        self._size(SPIN_BG, (spinS, spinS))
        self._pos(SPIN_BG, (spinX, barY))
        self._size(SPIN_TOUCH, (spinS, spinS))
        self._pos(SPIN_TOUCH, (spinX, barY))
        dotS = spinS * 0.22
        g["dotS"] = dotS
        self._size(SPIN_DOT, (dotS, dotS))

        pbH = max(10.0, S * 0.045)
        pbW = W * 0.40
        pbX = spinX + spinS + W * 0.035
        pbY = barY + spinS * 0.5 - pbH * 0.5
        g["pbW"] = pbW
        g["pbH"] = pbH
        g["pbX"] = pbX
        g["pbY"] = pbY
        self._size(POWER_BG, (pbW, pbH))
        self._pos(POWER_BG, (pbX, pbY))
        # 力度条外面套一圈「像按钮一样」的底框，上面再写一行「力度 xx%」
        fp = pbH * 0.55
        self._size(POWER_FRAME, (pbW + fp * 2.0, pbH + fp * 2.0))
        self._pos(POWER_FRAME, (pbX - fp, pbY - fp))
        self._size(POW_LABEL, (pbW, pbH * 1.6))
        self._pos(POW_LABEL, (pbX, pbY - fp - pbH * 1.7))
        self._size(POWER_TOUCH, (pbW + fp * 2.0, pbH + fp * 2.0))
        self._pos(POWER_TOUCH, (pbX - fp, pbY - fp))

        shootS = min(S * 0.20, W * 0.14)
        shootX = W - pad - shootS
        shootY = barY + spinS * 0.5 - shootS * 0.5
        self._size(SHOOT_BTN, (shootS, shootS))
        self._pos(SHOOT_BTN, (shootX, shootY))

        # ---- 右上角：离开 / 重新摆球 ----
        bw = W * 0.13
        bh = S * 0.085
        self._size(EXIT_BTN, (bw, bh))
        self._pos(EXIT_BTN, (W - pad - bw, H * 0.035))
        self._size(RESET_BTN, (bw * 0.78, bh * 0.78))
        self._pos(RESET_BTN, (W - pad - bw * 0.78, H * 0.035 + bh * 1.25))

        # ---- 选模式的两颗大按钮（只在「等人」时露脸） ----
        mw = W * 0.20
        mh = S * 0.13
        # 这两颗是「等人时」的模式菜单，摆在台面绒布上。
        # 原来按屏高 62% 摆，16:9 的屏幕上会掉到台面外，正好压住下面的力度条。
        my = ty + th * 0.66
        self._size(SOLO_BTN, (mw, mh))
        self._pos(SOLO_BTN, (W * 0.5 - mw - W * 0.015, my))
        self._size(AI_BTN, (mw, mh))
        self._pos(AI_BTN, (W * 0.5 + W * 0.015, my))

        # ---- 字 ----
        # 两行字叠在台面上方的绿绒布上，看起来像记分牌
        self._size(TITLE, (W * 0.80, S * 0.11))
        self._pos(TITLE, (W * 0.10, ty + th * 0.13))
        self._size(MSG, (W * 0.78, S * 0.085))
        self._pos(MSG, (W * 0.11, ty + th * 0.13 + S * 0.115))

        self.g = g
        self.ready = True
        # 记一下各控件的全局位置（把触摸点换算成台面坐标要用）
        self._syncGlobal()
        self.needBalls = True
        self.needAim = True
        self.needMeters = True
        self.needLabels = True

    def _syncGlobal(self):
        gp = self._global(TABLE)
        if gp is None:
            gp = (0.0, 0.0)
        self.g["tableGX"] = float(gp[0])
        self.g["tableGY"] = float(gp[1])
        for key, path in (("pbG", POWER_BG), ("spinG", SPIN_BG)):
            g2 = self._global(path)
            if g2 is None:
                g2 = (0.0, 0.0)
            self.g[key + "X"] = float(g2[0])
            self.g[key + "Y"] = float(g2[1])

    # ==================== 坐标换算 ====================
    def _toScreen(self, px, pz):
        g = self.g
        x = g["tx"] + g["rx"] + px / C.TableLength * g["rw"]
        y = g["ty"] + g["ry"] + pz / C.TableWidth * g["rh"]
        return (x, y)

    def _toTable(self, sx, sy):
        g = self.g
        u = (sx - g.get("tableGX", 0.0) - g["rx"]) / max(1.0, g["rw"])
        v = (sy - g.get("tableGY", 0.0) - g["ry"]) / max(1.0, g["rh"])
        return (u * C.TableLength, v * C.TableWidth)

    # ==================== 每帧 ====================
    def Update(self):
        self._tryWire()
        if not getattr(self, "mOpen", False):
            return
        if not self._ensureLayout():
            return
        if getattr(self, "_reopen", 0) > 0:
            self._reopen -= 1
            self.ReassertOpen()
        now = time.time()
        dt = now - self.lastT if self.lastT > 0.0 else 0.0
        self.lastT = now
        moving = not self.sim.allStop()
        if moving:
            self.sim.advance(dt)
            self.needBalls = True
            self.needAim = True
            if self.sim.allStop():
                self.needAim = True
        elif self.pendingBalls:
            self._applyBalls(self.pendingBalls)
            self.pendingBalls = None
        if self.needBalls:
            self.needBalls = False
            self._drawBalls()
        if self.needAim:
            self.needAim = False
            self._drawAim()
        self._drawMeters()
        if self.needLabels:
            self.needLabels = False
            self._drawLabels()
        else:
            self._tickLabels(now)

    # ==================== 画 ====================
    def _applyBalls(self, rows):
        try:
            for r in rows:
                num = int(r[0])
                b = self.sim.ball(num)
                if b is None:
                    continue
                b.x = float(r[1])
                b.y = float(r[2])
                b.vx = 0.0
                b.vy = 0.0
                b.active = bool(int(r[3]))
            self.sim.clearShotLog()
        except Exception:
            pass
        self.needBalls = True
        self.needAim = True

    def _drawBalls(self):
        if not self.g:
            return
        bd = self.g["ballD"]
        for num in range(16):
            b = self.sim.ball(num)
            path = BALL % num
            if b is None or not b.active:
                self._visible(path, False)
                continue
            self._visible(path, True)
            x, y = self._toScreen(b.x, b.y)
            self._pos(path, (x - bd * 0.5, y - bd * 0.5))

    def _drawAim(self):
        if not self.g:
            return
        # 轮到对手（人机 / 双人）出杆：不画辅助线，也不画撞点那个圈
        if self.waitingForOpponent():
            self._hideDots()
            self._visible(RING, False)
            return
        # 球还在滚的时候不画辅助线，全部还原到隐藏
        if not self.sim.allStop():
            self._hideDots()
            self._visible(RING, False)
            return
        bd = self.g["ballD"]
        cue = self.sim.ball(0)
        if cue is None or not cue.active:
            self._dots(AIM, AIM_DOTS, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
            self._dots(AIM2, AIM2_DOTS, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
            self._visible(RING, False)
            return
        a = A.solve(self.sim, self.aimDx, self.aimDy)
        x0, y0 = self._toScreen(a.sx, a.sy)
        x1, y1 = self._toScreen(a.hx, a.hy)
        # 白球 → 撞点：一串小白点，方向跟着拖动实时变
        dot = max(3.0, bd * 0.38)
        self._dots(AIM, AIM_DOTS, x0, y0, x1, y1, dot, bd * 0.75, bd * 0.95)

        d2 = max(2.5, bd * 0.32)
        if a.kind == "ball":
            rd = bd * 1.12
            self._visible(RING, True)
            self._size(RING, (rd, rd))
            self._pos(RING, (x1 - rd * 0.5, y1 - rd * 0.5))
            # 目标球会被打向哪边
            ox, oy = self._toScreen(a.objX, a.objY)
            ex = ox + a.objDx * bd * 6.0
            ey = oy + a.objDy * bd * 6.0
            self._dots(AIM2, AIM2_DOTS, ox, oy, ex, ey, d2, bd * 0.75, bd * 1.15)
        elif a.kind == "cushion":
            rd = bd * 0.9
            self._visible(RING, True)
            self._size(RING, (rd, rd))
            self._pos(RING, (x1 - rd * 0.5, y1 - rd * 0.5))
            # 撞库之后会往哪边弹
            ex = x1 + a.refDx * bd * 6.0
            ey = y1 + a.refDy * bd * 6.0
            self._dots(AIM2, AIM2_DOTS, x1, y1, ex, ey, d2, bd * 0.75, bd * 0.6)
        else:
            self._visible(RING, False)
            self._dots(AIM2, AIM2_DOTS, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    def _hideDots(self):
        # 把所有辅助线小点藏起来
        self._dots(AIM, AIM_DOTS, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        self._dots(AIM2, AIM2_DOTS, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    def _dots(self, fmt, n, x0, y0, x1, y1, dot, gap, skip):
        u"""把一条直线画成一串小圆点。

        以前是「一整条线 + 转角度」，但台球这套界面里 UI 控件的旋转在这台机器上
        不生效（转钟动画当年也是拿 8 张帧图硬顶的），所以线永远横着。
        改成按方向撒点：方向一变，点就落到新的直线上，方向自然跟着变。
        """
        L = math.hypot(x1 - x0, y1 - y0)
        if dot <= 0.0 or L <= skip + dot:
            for i in range(n):
                self._visible(fmt % i, False)
            return
        step = gap
        if (L - skip) > step * n:
            step = (L - skip) / float(n)
        for i in range(n):
            d0 = skip + step * i
            path = fmt % i
            if d0 > L:
                self._visible(path, False)
                continue
            t = d0 / L
            cx = x0 + (x1 - x0) * t
            cy = y0 + (y1 - y0) * t
            self._size(path, (dot, dot))
            self._pos(path, (cx - dot * 0.5, cy - dot * 0.5))
            self._visible(path, True)

    def _drawMeters(self):
        if not self.g:
            return
        g = self.g
        p = V.clamp(self.power, 0.0, 1.0)
        self._size(POWER_FILL, (max(1.0, g["pbW"] * p), g["pbH"] - 6.0))
        self._pos(POWER_FILL, (g["pbX"] + 3.0, g["pbY"] + 3.0))
        self._label(POW_LABEL, u"力度 %d%%" % int(round(p * 100.0)))
        spinS = g["spinS"]
        r = spinS * 0.5 - spinS * 0.10
        cx = g["spinGX"] + spinS * 0.5
        cy = g["spinGY"] + spinS * 0.5
        dotS = g["dotS"]
        self._pos(SPIN_DOT, (cx + self.spinX * r - dotS * 0.5,
                             cy - self.spinY * r - dotS * 0.5))

    def _drawLabels(self):
        names = self.names or []
        if self.phase == "wait":
            title = u"等待其他玩家加入…"
        elif self.phase == "solo":
            title = u"单人练习（随时可以出杆）"
        elif self.phase in ("pvp", "ai"):
            if self.turn == self.seat:
                title = u"轮到你了"
            else:
                who = names[self.turn] if 0 <= self.turn < len(names) else u"对手"
                title = u"轮到：%s" % who
        else:
            title = u""
        if self.myGroup:
            title = title + (u"　你：全色 1-7" if self.myGroup == "solids"
                             else u"　你：花色 9-15")
        self._label(TITLE, title)
        try:
            self.GetBaseUIControl(MSG).asLabel().SetTextAlignment("center")
        except Exception:
            pass
        self._label(MSG, self.msg)
        wait = (self.phase == "wait")
        self._visible(SOLO_BTN, wait)
        self._visible(AI_BTN, wait)
        if wait:
            self.msg = u"一个人也可以玩：选一种模式开始"
            self._label(MSG, self.msg)
        self.needMeters = True

    def _tickLabels(self, now):
        if not self.msg and now - self.lastShotAt < 0.4:
            return

    # ==================== 触摸 ====================
    def _enum(self):
        return clientApi.GetMinecraftEnum().TouchEvent

    def OnTableTouch(self, args):
        if not self.g or args is None:
            return
        E = self._enum()
        ev = args.get("TouchEvent")
        try:
            tx = float(args.get("TouchPosX", 0))
            ty = float(args.get("TouchPosY", 0))
        except Exception:
            return
        if ev == E.TouchDown:
            self.aiming = True
        elif ev == E.TouchUp or ev == E.TouchCancel:
            self.aiming = False
            return
        if not self.aiming:
            return
        if not self.sim.allStop():
            return
        if self.waitingForOpponent():
            return
        cue = self.sim.ball(0)
        if cue is None or not cue.active:
            return
        px, pz = self._toTable(tx, ty)
        dx = px - cue.x
        dy = pz - cue.y
        if V.length(dx, dy) < 0.07:
            return
        self.aimDx, self.aimDy = V.norm(dx, dy)
        self.needAim = True

    def OnPowerTouch(self, args):
        if not self.g or args is None:
            return
        E = self._enum()
        ev = args.get("TouchEvent")
        if ev == E.TouchDown:
            self.powering = True
        elif ev == E.TouchUp or ev == E.TouchCancel:
            self.powering = False
            return
        if not self.powering:
            return
        try:
            tx = float(args.get("TouchPosX", 0))
        except Exception:
            return
        self.power = V.clamp((tx - self.g.get("pbGX", 0.0)) / max(1.0, self.g["pbW"]),
                             0.02, 1.0)
        self.needMeters = True

    def OnSpinTouch(self, args):
        if not self.g or args is None:
            return
        E = self._enum()
        ev = args.get("TouchEvent")
        if ev == E.TouchDown:
            self.spinning = True
        elif ev == E.TouchUp or ev == E.TouchCancel:
            self.spinning = False
            return
        if not self.spinning:
            return
        try:
            tx = float(args.get("TouchPosX", 0))
            ty = float(args.get("TouchPosY", 0))
        except Exception:
            return
        s = self.g["spinS"]
        cx = self.g.get("spinGX", 0.0) + s * 0.5
        cy = self.g.get("spinGY", 0.0) + s * 0.5
        r = max(1.0, s * 0.5)
        ux = (tx - cx) / r
        uy = (ty - cy) / r
        d = math.hypot(ux, uy)
        if d > 1.0:
            ux /= d
            uy /= d
        self.spinX = ux
        self.spinY = -uy
        self.needMeters = True

    def OnShootTouch(self, args):
        if args is None:
            return
        if args.get("TouchEvent") != self._enum().TouchUp:
            return
        if not self.canShootNow():
            return
        self.lastShotAt = time.time()
        if self.onShoot is not None:
            try:
                self.onShoot(self.aimDx, self.aimDy, self.power,
                             self.spinX, self.spinY)
            except Exception:
                pass

    def waitingForOpponent(self):
        u"""人机 / 双人对战里，现在是不是轮到对手出杆。

        轮到对手的时候，辅助线用的还是「我」上一次的瞄准方向 ——
        画出来既不能用、又干扰看对手打球，所以整条线（连同撞点那个圈）
        在对手出杆期间一律不显示，也不让拖动去改方向。
        """
        if self.phase not in ("pvp", "ai"):
            return False
        if self.room.get("winner"):
            return False
        return self.turn != self.seat

    def canShootNow(self):
        if not self.sim.allStop():
            return False
        if self.phase == "solo":
            return True
        if self.phase in ("pvp", "ai"):
            return self.turn == self.seat and not self.room.get("winner")
        return False

    def ApplyRoom(self, data):
        if not data:
            return
        if data.get("close"):
            return
        self.room = data
        try:
            self.seat = int(data.get("seat", 0))
        except Exception:
            self.seat = 0
        self.phase = data.get("phase", "wait")
        try:
            self.turn = int(data.get("turn", 0))
        except Exception:
            self.turn = 0
        self.names = data.get("names") or []
        self.groups = data.get("groups") or []
        self.myGroup = ""
        if 0 <= self.seat < len(self.groups):
            self.myGroup = self.groups[self.seat] or ""
        msg = data.get("msg") or u""
        if msg:
            self.msg = msg
        balls = data.get("balls")
        if balls:
            if self.sim.allStop():
                self._applyBalls(balls)
            else:
                self.pendingBalls = balls
        self.needLabels = True
        self.needAim = True

    def ApplyShot(self, data):
        if not data:
            return
        try:
            self.sim.shoot(float(data.get("dirx", 1.0)),
                           float(data.get("diry", 0.0)),
                           float(data.get("power", 0.5)),
                           float(data.get("sx", 0.0)),
                           float(data.get("sy", 0.0)))
        except Exception:
            return
        self.msg = u""
        self.lastT = time.time()
        self.needBalls = True
        self.needAim = True
        self.needLabels = True

    def ApplyTip(self, text):
        self.msg = text or u""
        self.needLabels = True
