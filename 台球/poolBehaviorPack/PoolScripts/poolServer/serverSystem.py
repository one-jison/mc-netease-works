# -*- coding: utf-8 -*-
# ============================================================
#  台球 — 服务端
#  这里是唯一「算数」的地方：谁该打、进了几颗、算谁赢。
#  但它不画面 —— 它只把「谁、朝哪、多大力、多少塞」发出去，
#  各个客户端自己用同一套物理算一遍，画面当场就动。
#  因为物理是定步长的，两边结果一定一样。
# ============================================================
import math
import time

import mod.server.extraServerApi as serverApi

ServerSystem = serverApi.GetServerSystemCls()
compFactory = serverApi.GetEngineCompFactory()

from PoolScripts import modConfig
from PoolScripts.poolCommon import constants as C
from PoolScripts.poolCommon import vecmath as V
from PoolScripts.poolCommon.physics import Sim
from PoolScripts.poolServer import ai as poolAi
from PoolScripts.poolServer import rules8ball
from PoolScripts.poolServer.session import (Session, PHASE_WAIT, PHASE_SOLO,
                                            PHASE_AI, PHASE_PVP, PHASE_OVER)

AI_ID = "__ai__"
AI_NAME = u"\u4eba\u673a"

# 找球桌：玩家脚底下这么大一圈里去找
SCAN_XZ = 3
SCAN_Y = 1
NEAR_PERIOD = 0.4      # 每 0.4 秒看一圈就够了


def _aabbDist(px, py, pz, x0, y0, z0, x1, y1, z1):
    dx = max(x0 - px, 0.0, px - x1)
    dy = max(y0 - py, 0.0, py - y1)
    dz = max(z0 - pz, 0.0, pz - z1)
    return math.sqrt(dx * dx + dy * dy + dz * dz)


class PoolServerSystem(ServerSystem):

    def __init__(self, namespace, systemName):
        super(PoolServerSystem, self).__init__(namespace, systemName)
        self.sessions = {}       # key -> Session
        self.ofPlayer = {}       # playerId -> key
        self.pending = {}        # key -> {"until":..., "shooter":pid}
        self.aiCool = {}         # key -> 人机下一杆最早什么时候出
        self.nearState = {}      # pid -> (要不要出按钮, 球桌坐标, 维度)
        self.nearAt = 0.0
        self.diagDone = set()    # 已经自检过的玩家（只报一次，不刷屏）
        self._listen()

    # ==================== 事件 ====================
    def _listen(self):
        ns = serverApi.GetEngineNamespace()
        sn = serverApi.GetEngineSystemName()
        L = self.ListenForEvent
        L(ns, sn, "AddServerPlayerEvent", self, self.OnPlayerJoin)
        L(ns, sn, "DelServerPlayerEvent", self, self.OnPlayerLeave)
        L(ns, sn, "OnScriptTickServer", self, self.OnTick)
        L(modConfig.ModName, modConfig.ClientSystemName,
          modConfig.EventDiag, self, self.OnDiag)
        L(ns, sn, "PlayerDieEvent", self, self.OnPlayerDie)
        for evt, fn in ((modConfig.EventEnter, self.OnEnter),
                        (modConfig.EventExit, self.OnExit),
                        (modConfig.EventShoot, self.OnShoot),
                        (modConfig.EventMode, self.OnMode),
                        (modConfig.EventReset, self.OnReset),
                        (modConfig.EventReady, self.OnReady)):
            L(modConfig.ModName, modConfig.ClientSystemName, evt, self, fn)

    # ==================== 小工具 ====================
    def _name(self, pid):
        try:
            return compFactory.CreateName(pid).GetName() or pid
        except Exception:
            return pid

    def _send(self, pid, evt, data):
        try:
            self.NotifyToClient(pid, evt, data)
        except Exception:
            pass

    def _pushRoom(self, sess):
        for sid in list(sess.seats):
            if sid == AI_ID:
                continue
            self._send(sid, modConfig.EventRoom, sess.view(sid))

    def _say(self, pid, text):
        # 自检用：直接往玩家聊天栏推一行字。聊天栏不依赖我们自己的界面，
        # 所以界面上什么都没有的时候，就靠它把结论带出来。
        try:
            compFactory.CreateMsg(pid).NotifyOneMessage(pid, text)
        except Exception:
            pass

    def OnDiag(self, args=None):
        # 客户端汇报「屏幕上那颗按钮建出来没有」
        if not args:
            return
        pid = args.get("playerId")
        if not pid:
            return
        if args.get("hud"):
            self._say(pid, u"[台球] 客户端按钮界面：已建好")
        else:
            self._say(pid, u"[台球] 客户端按钮界面：没建出来（试了 %s 次）"
                      % args.get("tries"))

    def _tip(self, pid, text):
        self._send(pid, modConfig.EventTip, {"text": text})

    def _key(self, pos, dim):
        return (int(round(pos[0])), int(round(pos[1])), int(round(pos[2])), int(dim))

    def _sessionOf(self, pid):
        k = self.ofPlayer.get(pid)
        if k is None:
            return None
        return self.sessions.get(k)

    # ==================== 进出世界 ====================
    def OnPlayerJoin(self, args=None):
        pid = (args or {}).get("id") or (args or {}).get("playerId")
        if pid:
            # 进来的话让他重新收一次「附近有没有球桌」和自检报告
            self.nearState.pop(pid, None)
            self.diagDone.discard(pid)

    def OnPlayerLeave(self, args=None):
        pid = (args or {}).get("id") or (args or {}).get("playerId")
        if not pid:
            return
        self.nearState.pop(pid, None)
        self._leave(pid, True)

    def OnPlayerDie(self, args=None):
        pid = (args or {}).get("id") or (args or {}).get("playerId")
        if not pid:
            return
        self._leave(pid, True)

    def _leave(self, pid, closeUi):
        sess = self._sessionOf(pid)
        self.ofPlayer.pop(pid, None)
        # 出来以后要能再进去：把「附近有没有球桌」这条记录清掉。
        # 不清的话下一轮扫描发现状态没变就不发消息了，客户端手里的球桌就没了，
        # 按钮不再出现、按 R 也没反应 —— 就是「只能进一次」那个毛病。
        self.nearState.pop(pid, None)
        if sess is None:
            return
        sess.remove(pid)
        # 人机是房间里的「假座位」：真人都走了，人机也得跟着走。
        # 不带走的话房间不会销毁，下次再进来会被判成跟人机打双人，
        # 界面卡在「轮到：人机」，按钮全点不了。
        sess.dropBots((AI_ID,))
        self.pending.pop(sess.key, None)
        self.aiCool.pop(sess.key, None)
        if closeUi:
            self._send(pid, modConfig.EventRoom, {"close": 1})
        if sess.empty():
            self.sessions.pop(sess.key, None)
        else:
            self._pushRoom(sess)
        for sid in sess.seats:
            if sid != AI_ID:
                self.ofPlayer[sid] = sess.key

    # ==================== 进 / 出球桌 ====================
    def OnEnter(self, args=None):
        if not args:
            return
        pid = args.get("playerId")
        pos = args.get("pos")
        dim = args.get("dim", 0)
        if not pid or not pos:
            return
        old = self._sessionOf(pid)
        if old is not None:
            # 换了一张桌子，先退旧的
            self._leave(pid, False)
        key = self._key(pos, dim)
        sess = self.sessions.get(key)
        if sess is None:
            sess = Session(key, (int(round(pos[0])), int(round(pos[1])),
                                 int(round(pos[2]))), int(dim))
            self.sessions[key] = sess
        seat = sess.add(pid, self._name(pid))
        if seat < 0:
            self._tip(pid, u"\u8fd9\u5f20\u684c\u5b50\u5df2\u7ecf\u6709\u4e24\u4e2a\u4eba\u4e86")
            return
        self.ofPlayer[pid] = key
        self._pushRoom(sess)

    def OnExit(self, args=None):
        if not args:
            return
        pid = args.get("playerId")
        if not pid:
            return
        self._leave(pid, True)

    def OnReady(self, args=None):
        if not args:
            return
        pid = args.get("playerId")
        sess = self._sessionOf(pid)
        if sess is None:
            return
        self._pushRoom(sess)

    def OnMode(self, args=None):
        if not args:
            return
        pid = args.get("playerId")
        mode = args.get("mode")
        sess = self._sessionOf(pid)
        if sess is None or sess.seatOf(pid) != 0:
            return
        if len(sess.seats) >= 2:
            return          # 已经有两个人了，就是双人对战
        if mode == "ai":
            if AI_ID not in sess.seats:
                sess.seats.append(AI_ID)
                sess.names.append(AI_NAME)
            sess.state = rules8ball.new_state(sess.seats)
            sess.sim.reset()
            sess.phase = PHASE_AI
            sess.msg = u"\u4f60\u5148\u5f00\u7403"
        else:
            if AI_ID in sess.seats:
                i = sess.seatOf(AI_ID)
                sess.seats.pop(i)
                sess.names.pop(i)
                sess.state = rules8ball.new_state(sess.seats)
            sess.phase = PHASE_SOLO
            sess.msg = u"\u81ea\u5df1\u7ec3\u4e60\uff0c\u968f\u65f6\u53ef\u4ee5\u51fa\u6746"
        sess.coolUntil = 0.0
        self._pushRoom(sess)

    def OnReset(self, args=None):
        if not args:
            return
        pid = args.get("playerId")
        sess = self._sessionOf(pid)
        if sess is None:
            return
        sess.sim.reset()
        sess.state = rules8ball.new_state(sess.seats)
        sess.state["turn"] = 0
        sess.msg = u"\u91cd\u65b0\u6446\u7403"
        sess.coolUntil = time.time() + 0.4
        self.pending.pop(sess.key, None)
        self.aiCool.pop(sess.key, None)
        self._pushRoom(sess)

    # ==================== 出杆 ====================
    def OnShoot(self, args=None):
        if not args:
            return
        pid = args.get("playerId")
        sess = self._sessionOf(pid)
        if sess is None:
            return
        if not sess.canShoot(pid):
            return
        try:
            dx = float(args.get("dirx", 1.0))
            dy = float(args.get("diry", 0.0))
            power = V.clamp(float(args.get("power", 0.5)), 0.0, 1.0)
            sx = V.clamp(float(args.get("sx", 0.0)), -1.0, 1.0)
            sy = V.clamp(float(args.get("sy", 0.0)), -1.0, 1.0)
        except Exception:
            return
        self._fire(sess, pid, dx, dy, power, sx, sy)

    def _fire(self, sess, pid, dx, dy, power, sx, sy):
        seat = sess.seatOf(pid)
        if seat < 0:
            return
        dx, dy = V.norm(dx, dy)
        sess.coolUntil = time.time() + 0.25
        # 先告诉大家「有人出杆了」，各家自己算，画面立刻动
        data = {"seat": seat, "seatId": pid, "dirx": dx, "diry": dy,
                "power": power, "sx": sx, "sy": sy}
        for sid in list(sess.seats):
            if sid == AI_ID:
                continue
            self._send(sid, modConfig.EventShot, data)
        # 服务端自己也算一遍（这是真相）
        sess.sim.shoot(dx, dy, power, sx, sy)
        dur = sess.sim.run()
        self.pending[sess.key] = {
            "until": time.time() + dur + 0.30,
            "shooter": pid,
        }
        if sess.phase == PHASE_AI:
            self.aiCool[sess.key] = time.time() + dur + 1.1

    # ==================== 每帧 ====================
    def OnTick(self, args=None):
        now = time.time()
        self._tickNear(now)
        for key in list(self.sessions.keys()):
            sess = self.sessions.get(key)
            if sess is None:
                continue
            self._tickPending(sess, now)
            self._tickAi(sess, now)
            if sess.empty() and (now - sess.lastAct) > 60.0:
                self.sessions.pop(key, None)

    # ==================== 附近有没有球桌 ====================
    def _tickNear(self, now):
        # 查方块只能在服务端做：客户端那套方块接口在官方示例里找不到用例，
        # 靠不住。服务端每 0.4 秒看一圈，状态变了才发消息，不刷屏。
        if now - self.nearAt < NEAR_PERIOD:
            return
        self.nearAt = now
        try:
            pids = serverApi.GetPlayerList() or []
        except Exception:
            return
        for pid in list(pids):
            try:
                self._nearOne(pid)
            except Exception:
                pass

    def _nearOne(self, pid):
        try:
            pos = compFactory.CreatePos(pid).GetFootPos()
        except Exception:
            return
        if not pos:
            return
        try:
            dim = int(compFactory.CreateDimension(pid).GetEntityDimensionId())
        except Exception:
            dim = 0
        try:
            bi = compFactory.CreateBlockInfo(serverApi.GetLevelId())
        except Exception:
            return
        bx0 = int(math.floor(pos[0]))
        by0 = int(math.floor(pos[1]))
        bz0 = int(math.floor(pos[2]))
        best = None
        bestD = 1e9
        seen = []
        for dx in range(-SCAN_XZ, SCAN_XZ + 1):
            for dz in range(-SCAN_XZ, SCAN_XZ + 1):
                for dy in range(-SCAN_Y, SCAN_Y + 1):
                    bx = bx0 + dx
                    by = by0 + dy
                    bz = bz0 + dz
                    try:
                        blk = bi.GetBlockNew((bx, by, bz), dim)
                    except Exception:
                        continue
                    if not blk:
                        continue
                    nm = blk.get("name")
                    if nm not in seen and len(seen) < 6:
                        seen.append(nm)
                    if nm != modConfig.PoolBlock:
                        continue
                    d = _aabbDist(pos[0], pos[1], pos[2],
                                  bx - 0.95, by + 0.0, bz - 0.30,
                                  bx + 1.95, by + 0.85, bz + 1.30)
                    if d < bestD:
                        bestD = d
                        best = (bx, by, bz)
        show = 0
        spot = None
        if best is not None and bestD <= modConfig.NearRange:
            show = 1
            spot = best
        if pid not in self.diagDone:
            self.diagDone.add(pid)
            self._say(pid, u"[台球] 服务端脚本在跑 · 两格内球桌 %d 张" % show)
            self._say(pid, u"[台球] 周围方块：" +
                      (u"、".join(seen) if seen else u"没扫到"))
        st = (show, spot, dim)
        if self.nearState.get(pid) == st:
            return
        self.nearState[pid] = st
        self._send(pid, modConfig.EventNear,
                   {"show": show,
                    "pos": [spot[0], spot[1], spot[2]] if spot else None,
                    "dim": dim})

    def _tickPending(self, sess, now):
        pd = self.pending.get(sess.key)
        if not pd:
            return
        if now < pd["until"]:
            return
        self.pending.pop(sess.key, None)
        shooter = pd["shooter"]
        if sess.seatOf(shooter) < 0:
            self._pushRoom(sess)
            return
        try:
            out = rules8ball.apply(sess.state, sess.sim, shooter)
        except Exception as e:
            print("[pool] rules error: %s" % e)
            out = {"msg": u""}
        msg = out.get("msg") or u""
        if out.get("winner"):
            who = out["winner"]
            nm = AI_NAME if who == AI_ID else self._name(who)
            sess.msg = msg + u"  " + (u"\u8d62\u5bb6\uff1a%s" % nm)
        elif msg:
            sess.msg = msg
        # 轮到人机了就等一会儿再让它出杆
        if sess.phase == PHASE_AI:
            self.aiCool[sess.key] = now + 1.2
        self._pushRoom(sess)

    def _tickAi(self, sess, now):
        if sess.phase != PHASE_AI:
            return
        if sess.state.get("winner"):
            return
        if not sess.sim.allStop():
            return
        if now < self.aiCool.get(sess.key, 0.0):
            return
        if now < sess.coolUntil:
            return
        shooter = sess.shooterId()
        if shooter != AI_ID:
            return
        self.aiCool[sess.key] = now + 8.0
        try:
            hg = sess.state["groups"].get(AI_ID)
            shot = poolAi.choose_shot(sess.sim, hg, bool(sess.state["open"]))
        except Exception as e:
            print("[pool] ai error: %s" % e)
            shot = None
        if not shot:
            # 实在不会打，就随便朝中间推一下，别卡住
            shot = (1.0, 0.0, 0.4, 0.0, 0.0)
        self._fire(sess, AI_ID, shot[0], shot[1], shot[2], shot[3], shot[4])
