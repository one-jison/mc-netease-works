# -*- coding: utf-8 -*-
# ============================================================
#  台球 — 一桌球 = 一个「房间」
#  同一张桌子上的人进的是同一个房间；房间里只有一个人就是自己练
# ============================================================
import time

from PoolScripts.poolCommon import constants as C
from PoolScripts.poolCommon.physics import Sim
from PoolScripts.poolServer import rules8ball

PHASE_WAIT = "wait"     # 一个人在等，还没选模式
PHASE_SOLO = "solo"     # 单人自己练
PHASE_AI = "ai"         # 打人机
PHASE_PVP = "pvp"       # 两个人打
PHASE_OVER = "over"     # 这一局结束了


class Session(object):

    def __init__(self, key, pos, dim):
        self.key = key              # (x, y, z, dim)
        self.pos = pos
        self.dim = dim
        self.sim = Sim()
        self.state = rules8ball.new_state([])
        self.seats = []             # [playerId]  最多两个
        self.names = []             # [名字]
        self.phase = PHASE_WAIT
        self.msg = u""
        self.shotSeat = -1          # 正在出杆的是第几个位置
        self.coolUntil = 0.0        # 这段时间内不收新的开球请求
        self.lastAct = time.time()  # 房间里最后一次有人说话的时间

    # ---------------- 成员 ----------------
    def seatOf(self, pid):
        for i, sid in enumerate(self.seats):
            if sid == pid:
                return i
        return -1

    def add(self, pid, name):
        i = self.seatOf(pid)
        if i >= 0:
            self.names[i] = name
            return i
        if len(self.seats) >= 2:
            return -1
        self.seats.append(pid)
        self.names.append(name)
        self.state = rules8ball.new_state(self.seats)
        self.sim.reset()
        self.msg = u""
        if len(self.seats) == 2 and self.phase in (PHASE_WAIT, PHASE_SOLO, PHASE_AI):
            self.phase = PHASE_PVP
            self.msg = u"%s 加入了，玩家 1 先开球" % name
        self.lastAct = time.time()
        return len(self.seats) - 1

    def remove(self, pid):
        i = self.seatOf(pid)
        if i < 0:
            return
        self.seats.pop(i)
        self.names.pop(i)
        self.state = rules8ball.new_state(self.seats)
        if not self.seats:
            self.phase = PHASE_WAIT
        elif len(self.seats) == 1:
            self.phase = PHASE_SOLO
            self.msg = u"对手离开了，现在是自己练"
        self.lastAct = time.time()

    def dropBots(self, botIds):
        u"""把「假座位」清掉（人机这种不是真玩家的座位）。

        真人都走了以后，人机不能一个人占着桌子。留着的话，这个房间会以
        「一个人机 + 一个空位」的样子继续挂在场上，下一个人进来就被当成
        双人对战 —— 界面卡在「轮到：人机」上，击球没反应，
        单人练习 / 人机对战两颗按钮也不再出现，等于什么都点不了。
        """
        hit = False
        for bid in botIds:
            while bid in self.seats:
                i = self.seats.index(bid)
                self.seats.pop(i)
                self.names.pop(i)
                hit = True
        if not hit:
            return False
        self.state = rules8ball.new_state(self.seats)
        self.msg = u""
        if not self.seats:
            self.phase = PHASE_WAIT
        elif len(self.seats) == 1:
            self.phase = PHASE_SOLO
        self.lastAct = time.time()
        return True

    def empty(self):
        return len(self.seats) == 0

    def shooterId(self):
        if self.phase == PHASE_SOLO:
            return self.seats[0] if self.seats else None
        if self.phase in (PHASE_PVP, PHASE_AI):
            t = self.state["turn"] % max(1, len(self.seats))
            return self.seats[t] if t < len(self.seats) else None
        return self.seats[0] if self.seats else None

    def canShoot(self, pid):
        if self.phase not in (PHASE_SOLO, PHASE_PVP, PHASE_AI):
            return False
        if time.time() < self.coolUntil:
            return False
        if not self.sim.allStop():
            return False
        if self.phase == PHASE_SOLO:
            return self.seatOf(pid) == 0
        return self.shooterId() == pid

    # ---------------- 发给客户端 ----------------
    def view(self, pid):
        seat = self.seatOf(pid)
        st = self.state
        balls = [[b.num, round(b.x, 5), round(b.y, 5), 1 if b.active else 0]
                 for b in self.sim.balls]
        groups = []
        for i, sid in enumerate(self.seats):
            g = st["groups"].get(sid)
            groups.append(g or "")
        return {
            "pos": list(self.pos),
            "dim": self.dim,
            "seat": seat,
            "names": list(self.names),
            "phase": self.phase,
            "turn": st["turn"] % max(1, len(self.seats)) if self.seats else 0,
            "groups": groups,
            "open": 1 if st["open"] else 0,
            "winner": (st["winner"] or ""),
            "msg": self.msg,
            "balls": balls,
            "breakDone": 1 if st["breakDone"] else 0,
        }
