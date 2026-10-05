# -*- coding: utf-8 -*-
# ============================================================
#  时间回溯 — 服务端
#    · 有药水的玩家，身边一百格内的实体每 0.5 秒记一笔（位置 / 朝向 / 血量）
#    · 方块要变之前先把它原来的样子记下来（玩家挖掉 / 被炸掉 / 被放上去）
#    · 按下回溯按钮：昼夜飞快交替，实体与方块退回十秒前的样子，
#      这十秒里死掉的生物原地复活，刚射出去的箭回到弓旁边再飞一次
#    · 玩家死亡：按钮收掉；死前喝过药的话，重生时血量回到十秒前那个值
# ============================================================
import math
import time
import collections
import mod.server.extraServerApi as serverApi
from TimeRewindScripts import modConfig
from TimeRewindScripts import timeRewindConfig as cfg


ServerSystem = serverApi.GetServerSystemCls()


class TimeRewindServerSystem(ServerSystem):

    def __init__(self, namespace, systemName):
        super(TimeRewindServerSystem, self).__init__(namespace, systemName)
        self._has = {}          # playerId -> True：身上有回溯药水
        self._until = {}        # playerId -> 按钮到什么时候收（0 = 一直留着）
        self._lastDrink = {}    # playerId -> 上一次喝下去的时间（一瓶别算两次）
        self._lastUse = {}      # playerId -> 上一次按按钮的时间（冷却）
        self._pending = {}      # playerId -> 到什么时候真正开始回溯（按下后先等一秒）
        self._reviveHp = {}     # playerId -> 重生时把血量还原成多少
        self._hpTask = {}       # playerId -> [还原血量的时间, 数值]
        self._hp = {}           # playerId -> [(时间, 血量), ...]
        self._hist = {}         # entityId -> [(时间, 位置, 朝向, 血量), ...]
        self._deaths = collections.deque()   # (时间, entityId, 类型, 位置, 朝向, 维度)
        self._blocks = {}       # (x, y, z) -> [时间, 维度, 方块字典, 方块状态]
        self._putQ = collections.deque()     # 等着恢复原样的方块（摊到每 tick 慢慢来，别卡帧）
        self._selfChk = {}       # playerId -> [第几 tick 去核对, 要站的位置]
        self._inv = {}          # playerId -> [(时间, 背包快照), ...]
        self._exp = {}          # playerId -> [(时间, 总经验值), ...]
        self._trackFrom = {}    # playerId -> 什么时候开始帮他记身边的东西
        self._shot = {}         # 抛射物id -> (射出时间, 出膛位置, 抛射物类型, 出膛速度)
        # ---- 静止药水 ----
        self._fz = {}           # playerId -> 静止药水什么时候到期
        self._fzOn = set()      # 现在把周围停住的玩家
        self._fzAi = {}         # entityId -> True：原生 AI 被屏蔽了（解冻时要放开）
        self._fzHold = {}       # entityId -> （冻住前的速度, 位置, 朝向）
        self._fzPrev = {}       # entityId -> 上一 tick 给抛射物设的速度（用来量引擎多推了多少）
        self._fzNear = {}       # playerId -> (时间, [entityId,...]) 静止专用的快查缓存
        self._lastFzDrink = {}  # playerId -> 上一次喝静止药水的时间（一瓶别算两次）
        self._fzBoom = {}       # entityId -> 被冻住的爆炸物（TNT 这些）的记账
        self._fzBlock = {}      # (x,y,z,维度) -> 被换成 TNT 方块的记账（解冻时要还回去）
        self._fzKeep = {}       # entityId -> 到这个时间为止，扫不到也不算跑出范围
        self._fzImmune = {}     # entityId -> 到这个时间为止，临时免疫伤害（兜底用）
        self._fzHeal = {}       # entityId -> (血量, 到什么时候补回去)
        self._fireOff = False   # 现在是不是把火焰规则关掉了
        self._exEvents = 0      # 这一轮里爆炸事件响了几次（诊断用，按一次按钮就清零）
        self._exBlocks = 0      # 这一轮里爆炸记下了几格方块（诊断用）
        self._near = {}         # playerId -> (时间, [entityId, ...])
        self._tick = 0
        self._spin = {}         # playerId -> 昼夜飞快交替到什么时候
        self._spinFrom = {}     # playerId -> (维度, 按下去那一刻的时间)：转完要放回去
        self._tod = {}          # 维度 -> 现在推到一天的第几帧
        self._listenEvents()

    # ==================== 事件 ====================
    def _listenEvents(self):
        ns = serverApi.GetEngineNamespace()
        sn = serverApi.GetEngineSystemName()
        L = self.ListenForEvent
        L(ns, sn, "AddServerPlayerEvent", self, self.OnAddPlayer)
        L(ns, sn, "DelServerPlayerEvent", self, self.OnPlayerLeave)
        L(ns, sn, "OnScriptTickServer", self, self.OnServerTick)

        # 喝药水：两个事件都听着，哪个先来都认
        L(ns, sn, "PlayerEatFoodServerEvent", self, self.OnEatFood)
        L(ns, sn, "ActorUseItemServerEvent", self, self.OnUseItem)

        # 方块要变之前，先把它原来的样子记下来（回溯时照这个还原）
        for evt, fn in (("ServerPlayerTryDestroyBlockEvent", self.OnBlockDestroy),
                        ("ServerEntityTryPlaceBlockEvent", self.OnBlockPlace),
                        ("ExplosionServerEvent", self.OnExplode)):
            try:
                L(ns, sn, evt, self, fn)
            except Exception:
                pass

        # 抛射物（箭矢这些）生成：把出膛的位置记下来，
        # 回溯时好把“这段时间里刚射出去的箭”放回弓旁边再飞一次
        try:
            L(ns, sn, "SpawnProjectileServerEvent", self, self.OnSpawnProjectile)
        except Exception:
            pass

        # 生物死掉：记一笔，回溯时把它拉回来
        L(ns, sn, "MobDieEvent", self, self.OnMobDie)
        # 玩家死了 / 复活了
        L(ns, sn, "PlayerDieEvent", self, self.OnPlayerDie)
        L(ns, sn, "PlayerRespawnFinishServerEvent", self, self.OnPlayerRespawn)
        # 静止期间玩家想扑灭火焰：把火放回去
        try:
            L(ns, sn, "ExtinguishFireServerEvent", self, self.OnExtinguishFire)
        except Exception:
            pass

        # 客户端点了屏幕左边那颗「回溯」
        L(modConfig.ModName, modConfig.ClientSystemName,
          modConfig.EventUse, self, self.OnUseButton)
        # 客户端放不出按键音效时，让服务端兜底放一下
        L(modConfig.ModName, modConfig.ClientSystemName,
          modConfig.EventSound, self, self.OnAskSound)
        # 客户端点了屏幕右边那颗「静止」
        L(modConfig.ModName, modConfig.ClientSystemName,
          modConfig.EventFreezeUse, self, self.OnFreezeButton)

    def OnAddPlayer(self, args=None):
        pid = None
        if args:
            pid = args.get("id") or args.get("playerId")
        if not pid:
            return
        self._near.pop(pid, None)
        self._trackFrom[pid] = time.time()
        self._toPlayer(pid, modConfig.EventState, {"show": 0})
        self._toPlayer(pid, modConfig.EventFreezeState, self._fzState(pid, 0, 0))

    def OnPlayerLeave(self, args=None):
        pid = None
        if args:
            pid = args.get("id") or args.get("playerId")
        if pid:
            self._clear(pid)
            # 兜底用的「临时免疫」是写进存档的，人走了要立刻撤回
            if self._fzImmune.pop(pid, None) is not None:
                self._setImmune(pid, False)
            self._toPlayer(pid, modConfig.EventFreezeState, self._fzState(pid, 0, 0))
            self._trackFrom.pop(pid, None)

    # ==================== 每 tick ====================
    def OnServerTick(self, args=None):
        now = time.time()
        self._tickHpTask(now)
        self._pendingTick(now)
        self._tickSelfChk(now)
        self._refreshShots(now)
        self._expire(now)
        self._spinTick(now)
        self._freezeTick(now)
        self._fzGuardTick(now)
        self._drainPut()
        if self._tick % cfg.sampleTicks() == 0:
            self._sample(now)
        self._tick += 1

    def _expire(self, now):
        if not self._has:
            return
        for pid in list(self._has.keys()):
            end = self._until.get(pid, 0.0)
            if end > 0.0 and now >= end:
                self._clear(pid)
                self._toPlayer(pid, modConfig.EventState, {"show": 0})
                self._tip(pid, u"回溯药水到期了", "GRAY")

    def _tickHpTask(self, now):
        if not self._hpTask:
            return
        for pid in list(self._hpTask.keys()):
            when, hp = self._hpTask[pid]
            if now >= when:
                self._hpTask.pop(pid, None)
                self._setHealth(pid, hp)

    # ==================== 喝药水 ====================
    def OnEatFood(self, args=None):
        if not args:
            return
        self._checkPotion(args.get("playerId"), args.get("itemDict"))

    def OnUseItem(self, args=None):
        if not args:
            return
        self._checkPotion(args.get("playerId"), args.get("itemDict"))

    def _itemNameOf(self, itemDict):
        if not isinstance(itemDict, dict):
            return u""
        name = itemDict.get("newItemName") or itemDict.get("itemName") or u""
        return str(name).lower()

    def _checkPotion(self, playerId, itemDict):
        if not playerId or not cfg.MODE_ON:
            return
        name = self._itemNameOf(itemDict)
        now = time.time()
        if name == str(cfg.POTION_ITEM).lower():
            if now - float(self._lastDrink.get(playerId, -999.0)) < 1.0:
                return
            self._lastDrink[playerId] = now
            self._drink(playerId)
            return
        if getattr(cfg, "FREEZE_ON", True) \
                and name == str(cfg.FREEZE_POTION_ITEM).lower():
            if now - float(self._lastFzDrink.get(playerId, -999.0)) < 1.0:
                return
            self._lastFzDrink[playerId] = now
            self._freezeDrink(playerId)

    def _drink(self, playerId):
        now = time.time()
        self._has[playerId] = True
        sec = cfg.buttonSeconds()
        self._until[playerId] = (now + sec) if sec > 0 else 0.0
        self._lastUse[playerId] = now - cfg.cooldownSeconds()
        self._hp.setdefault(playerId, [])
        self._toPlayer(playerId, modConfig.EventState, {"show": 1})
        if cfg.TIP_ON_DRINK:
            hint = u""
            if getattr(cfg, "USE_KEY_ENABLED", True):
                hint = u"（电脑端按 %s 键）" % getattr(cfg, "USE_KEY_LABEL", u"R")
            self._tip(playerId,
                      u"喝下 %s：屏幕左侧出现回溯按钮%s，按一下就能退回%d秒前"
                      % (cfg.POTION_NAME, hint, int(round(cfg.rewindSeconds()))),
                      "LIGHT_PURPLE")

    # ==================== 按下回溯 ====================
    def OnUseButton(self, args=None):
        if not args:
            return
        pid = args.get("playerId")
        if not pid or not cfg.MODE_ON:
            return
        if pid not in self._has:
            # 身上没有药水：直接忽略，不提示任何东西
            return
        now = time.time()
        left = cfg.cooldownSeconds() - (now - float(self._lastUse.get(pid, -999.0)))
        if left > 0.05:
            self._tip(pid, u"回溯冷却中，还要 %.0f 秒" % left, "RED")
            return
        self._lastUse[pid] = now
        # 按一下就把这瓶喝掉了：按钮立刻收掉，想再用得重新喝一瓶
        self._consume(pid)

        # 1) 昼夜立刻开始飞快交替（转完会自动放回原来的时间）
        if cfg.dayNightOn():
            self._spin[pid] = now + cfg.dayNightSeconds()
            dim0 = self._dimOf(pid)
            comp0 = self._timeComp()
            from0 = (self._timeOfDay(comp0, dim0) if comp0 is not None
                     else int(self._tod.get(dim0, 0)))
            self._spinFrom[pid] = (dim0, int(from0))
            if cfg.dayNightOnce():
                # 先把天砸到午夜（最黑），再一路走到白天
                start = cfg.dayNightStart()
                self._tod[dim0] = int(start)
                if comp0 is not None:
                    try:
                        comp0.SetTimeOfDay(int(start))
                    except Exception:
                        pass
            else:
                self._tod.pop(dim0, None)   # 从真实时间起算，转一整圈
        # 2) 屏幕上的转钟动画先转一秒，再真正回溯生物和方块
        delay = cfg.rewindDelay()
        if delay > 0.01:
            # 存（什么时候开始回溯, 按钮按下去那一刻）——
            # 回溯窗口要从按下去那一刻算，别被这一秒动画吃掉
            self._pending[pid] = (now + delay, now)
        else:
            self._doRewind(pid, now)

    def _consume(self, playerId):
        # 药水用掉了：按钮收掉、不再采样、也不再算“死前喝过药”。
        # 注意只清“药水状态”，_spin / _pending 要留着，
        # 不然正在转的昼夜和那一秒后的回溯就被取消了。
        self._has.pop(playerId, None)
        self._until.pop(playerId, None)
        self._hpTask.pop(playerId, None)
        self._reviveHp.pop(playerId, None)
        self._hp.pop(playerId, None)
        self._lastDrink.pop(playerId, None)
        self._toPlayer(playerId, modConfig.EventState, {"show": 0})

    def _doRewind(self, playerId, base=None):
        # 真正开始回溯：先把这一秒里死掉的生物、动过的方块也算进来
        now = time.time()
        # 回到“按下按钮那一刻”的十秒前，而不是回溯真正开始那一刻的十秒前 ——
        # 不然为了等转钟动画的那一秒延迟会从这十秒里吃掉一秒，
        # 看起来就成了“回到九秒前”，炸掉的房子只要稍微早一点就一点都修不回来。
        if base is None:
            base = now
        target = float(base) - cfg.rewindSeconds()
        moved, revived, cleaned, flew = self._rewindEntities(playerId, now, target)
        blocks = self._rewindBlocks(playerId, now, target)
        bag = self._rewindBag(playerId, target)
        exp = self._rewindExp(playerId, target)
        exEvents = self._exEvents
        exBlocks = self._exBlocks
        self._exEvents = 0
        self._exBlocks = 0
        if cfg.soundOn():
            self._playSound(playerId, str(getattr(cfg, "SOUND_USE", "mob.endermen.portal")),
                            float(getattr(cfg, "SOUND_VOLUME", 1.0)),
                            float(getattr(cfg, "SOUND_PITCH", 1.0)), 48.0)
        sec = int(round(cfg.rewindSeconds()))
        self._tip(playerId,
                  u"时间回溯：%d 个实体退回%d秒前、%d 格方块恢复原样、拉回 %d 只生物、"
                  u"清掉 %d 个掉落物、背包回收 %d 件、经验回收 %d、箭矢回膛 %d 支"
                  u"（爆 %d 次/%d 格）"
                  % (moved, sec, blocks, revived, cleaned, bag, exp, flew,
                     exEvents, exBlocks), "AQUA")

    def _pendingTick(self, now):
        # 按下按钮之后等的那一秒：到点了才真正回溯
        if not self._pending:
            return
        for pid in list(self._pending.keys()):
            rec = self._pending[pid]
            try:
                deadline, base = rec
            except Exception:
                deadline, base = rec, now
            if now >= deadline:
                self._pending.pop(pid, None)
                self._doRewind(pid, base)

    # ==================== 记实体 ====================
    def _sample(self, now):
        players = self._playerSet()
        # 玩家自己的位置一直在记（一个人一次读取，几乎不花性能）：
        # 这样就算刚喝完药水马上就按按钮，也一定能退回十秒前站的地方。
        # 掉落物 / 经验球也一直跟着记：回溯时才能判断出“这东西是这十秒里
        # 才冒出来的”（刚挖掉的方块掉的物品、刚打死的生物掉的球）。
        for pid in players:
            self._push(pid, now)
            self._pushTrash(pid, now)
        if self._has:
            for pid in list(self._has.keys()):
                pos = self._posOf(pid)
                if pos is None:
                    continue
                for eid in self._nearby(pid, cfg.entityRange()):
                    if eid == pid:
                        continue
                    if eid in players and not cfg.REWIND_PLAYERS:
                        continue
                    self._push(eid, now)
                # 玩家自己的血量记一笔：死前喝过药的话，重生要还原到十秒前那个值
                hp = self._healthOf(pid)
                if hp is not None:
                    arr = self._hp.setdefault(pid, [])
                    arr.append((now, hp))
                    while arr and arr[0][0] < now - 30.0:
                        arr.pop(0)
                # 背包和经验值也记一笔：按下去之后要把这十秒里多出来的收回去
                self._snapBag(pid, now)
        self._prune(now)

    def _pushTrash(self, playerId, now):
        # 掉落物 / 经验球：判定“是不是这十秒里才出现的”要用到它们的记录，
        # 所以只要有玩家在旁边就一直记（一次范围查询，很便宜）
        if not getattr(cfg, "CLEAN_NEW_ITEMS", True):
            return
        kinds = self._trashTypes()
        if not kinds:
            return
        for eid in self._nearby(playerId, cfg.entityRange()):
            if eid == playerId:
                continue
            t = self._typeStrOf(eid)
            if t and t in kinds:
                self._push(eid, now)

    def _trashTypes(self):
        kinds = getattr(cfg, "TRASH_TYPES", None)
        if kinds is None:
            kinds = ("minecraft:item", "minecraft:xp_orb")
        return tuple(kinds)

    def _snapBag(self, playerId, now):
        # 背包快照 + 总经验值，每 0.5 秒一笔（只在身上有药水时记，省性能）
        keep = max(4, int(getattr(cfg, "BAG_KEEP", 40)))
        if getattr(cfg, "REWIND_INVENTORY", True):
            comp = self._itemComp(playerId)
            if comp is not None:
                try:
                    cur = comp.GetPlayerAllItems(self._invType(), True)
                except Exception:
                    cur = None
                if cur is not None:
                    arr = self._inv.setdefault(playerId, [])
                    arr.append((now, cur))
                    while len(arr) > keep:
                        del arr[0]
        if getattr(cfg, "REWIND_EXP", True):
            comp2 = self._expComp(playerId)
            if comp2 is not None:
                try:
                    v = int(comp2.GetPlayerTotalExp())
                except Exception:
                    v = -1
                if v >= 0:
                    arr = self._exp.setdefault(playerId, [])
                    arr.append((now, v))
                    while len(arr) > keep:
                        del arr[0]

    def _push(self, entityId, now):
        pos = self._posOf(entityId)
        if pos is None:
            return
        rot = self._rotOf(entityId)
        hp = self._healthOf(entityId)
        arr = self._hist.get(entityId)
        if arr is None:
            arr = []
            self._hist[entityId] = arr
        arr.append((now, (float(pos[0]), float(pos[1]), float(pos[2])), rot, hp))
        keep = max(4, int(cfg.HISTORY_KEEP))
        if len(arr) > keep:
            del arr[0:len(arr) - keep]

    def _prune(self, now):
        dead = now - max(30.0, cfg.rewindSeconds() * 4.0)
        for eid in list(self._hist.keys()):
            arr = self._hist[eid]
            if not arr or arr[-1][0] < dead:
                self._hist.pop(eid, None)
                continue
            while arr and arr[0][0] < now - 30.0:
                arr.pop(0)
        limit = cfg.rewindSeconds() * 3.0
        while self._deaths and (now - self._deaths[0][0]) > limit:
            self._deaths.popleft()
        while len(self._deaths) > max(1, int(cfg.DEATH_KEEP)):
            self._deaths.popleft()

    def _nearestRec(self, arr, target):
        # 找“离 target 最近的那一笔”＝那时候大概什么样。
        # 同样近的时候优先挑不晚于 target 的。
        # 为什么不直接找“不晚于 target 的最后一笔”：万一记录中间断了档
        # （生物跑出范围又跑回来、刚喝药水没多久就按），那一笔可能在
        # 二十几秒前，一把跳回那么久以前就离谱了。
        if not arr:
            return None
        target = float(target)
        best = None
        bestGap = None
        for rec in arr:
            gap = abs(float(rec[0]) - target)
            if bestGap is None or gap < bestGap - 1e-9:
                best, bestGap = rec, gap
            elif gap <= bestGap + 1e-9 and float(rec[0]) <= target:
                best = rec
        return best

    def _sampleAt(self, entityId, target):
        return self._nearestRec(self._hist.get(entityId), target)

    def _existedBefore(self, entityId, target):
        # 这一笔记录之前它就已经在了吗（记录最早的那一笔都不晚于 target）
        arr = self._hist.get(entityId)
        return bool(arr) and float(arr[0][0]) <= float(target)

    # ==================== 实体回溯 ====================
    def _rewindEntities(self, playerId, now, target=None):
        if target is None:
            target = now - cfg.rewindSeconds()
        pos = self._posOf(playerId)
        if pos is None:
            return 0, 0, 0, 0
        dim = self._dimOf(playerId)
        players = self._playerSet()
        game = self._gameComp()
        moved = 0
        cleaned = 0
        flew = 0
        # 掉落物 / 经验球：这段时间里才掉出来的直接清掉（那时候它还不存在），
        # 之前就有的按老规矩退回原位。
        # covered：得确认“记录是从 target 之前就开始的”，不然刚进世界 /
        # 刚走到跟前就把一堆老东西当成新的清掉了。
        kinds = self._trashTypes() if getattr(cfg, "CLEAN_NEW_ITEMS", True) else ()
        projs = (self._projectileTypes()
                 if getattr(cfg, "PROJECTILE_FLY_AGAIN", True) else ())
        covered = float(self._trackFrom.get(playerId, 0.0)) <= float(target)
        for eid in self._nearby(playerId, cfg.entityRange()):
            if eid == playerId or eid in players:
                continue
            if game is not None:
                try:
                    if not game.IsEntityAlive(eid):
                        continue
                except Exception:
                    pass
            t = self._typeStrOf(eid) if (kinds or projs) else u""
            if t and t in projs:
                # 箭矢这类抛射物：不收回，放回出膛的位置再飞一次（只挪位置、
                # 不动速度，所以引擎会接着让它往前飞）。出膛点没记到就退回最早那一笔。
                if self._existedBefore(eid, target):
                    rec = self._sampleAt(eid, target)
                    if rec is not None:
                        self._putEntity(eid, rec)
                        moved += 1
                else:
                    mz = self._muzzleOf(eid)
                    if mz is None and covered:
                        rec = self._sampleAt(eid, target)
                        mz = None if rec is None else rec[1]
                    if mz is not None and self._putPos(eid, mz):
                        self._putShotMotion(eid)
                        flew += 1
                continue
            if kinds and t and t in kinds:
                if self._existedBefore(eid, target):
                    rec = self._sampleAt(eid, target)
                    if rec is not None:
                        self._putEntity(eid, rec)
                        moved += 1
                elif covered and self._destroy(eid):
                    cleaned += 1
                continue
            rec = self._sampleAt(eid, target)
            if rec is None:
                continue
            self._putEntity(eid, rec)
            moved += 1
        # 自己也退回十秒前站的位置（连血量一起回去）
        if getattr(cfg, "REWIND_SELF", False):
            rec = self._sampleAt(playerId, target)
            if rec is not None:
                self._putEntity(playerId, rec,
                                bool(getattr(cfg, "REWIND_SELF_HP", False)))
                moved += 1
        revived = self._reviveDead(now, pos, dim, target)
        return moved, revived, cleaned, flew

    def _putPos(self, entityId, pos):
        try:
            return bool(serverApi.GetEngineCompFactory()
                        .CreatePos(entityId).SetFootPos(pos))
        except Exception:
            return False

    def _putEntity(self, entityId, rec, health=True):
        unused_t, p, rot, hp = rec
        if entityId in self._playerSet():
            self._teleportSelf(entityId, p)
        else:
            self._putPos(entityId, p)
        if rot is not None:
            try:
                serverApi.GetEngineCompFactory().CreateRot(entityId).SetRot(rot)
            except Exception:
                pass
        if health and cfg.REWIND_HEALTH and hp is not None:
            self._setHealth(entityId, hp)

    def _teleportSelf(self, playerId, pos):
        # 玩家要被拽回十秒前站的地方。
        # 先走常规接口设位置（文档里写法就是“等同于 tp 命令，实体瞬移到目标点”），
        # 过 SELF_CHECK_TICKS 个 tick 再核对一眼：没到位就用 /tp 补一次，
        # 免得个别机型上设完位置又被客户端拉回原地。
        ok = False
        try:
            ok = bool(serverApi.GetEngineCompFactory()
                      .CreatePos(playerId).SetFootPos(pos))
        except Exception:
            ok = False
        if not ok:
            self._tpCommand(playerId, pos)
            return False
        self._selfChk[playerId] = [self._tick + max(1, int(getattr(cfg, "SELF_CHECK_TICKS", 5))),
                                   (float(pos[0]), float(pos[1]), float(pos[2]))]
        return True

    def _tpCommand(self, playerId, pos):
        # 兜底：用 /tp 把玩家挪过去
        try:
            comp = serverApi.GetEngineCompFactory().CreateCommand(serverApi.GetLevelId())
            comp.SetCommand("/tp @s %.3f %.3f %.3f"
                            % (float(pos[0]), float(pos[1]), float(pos[2])), playerId)
        except Exception:
            pass

    def _tickSelfChk(self, now):
        if not self._selfChk:
            return
        for pid in list(self._selfChk.keys()):
            when, pos = self._selfChk[pid]
            if self._tick < when:
                continue
            self._selfChk.pop(pid, None)
            cur = self._posOf(pid)
            if cur is None:
                continue
            try:
                far = (abs(float(cur[0]) - pos[0]) + abs(float(cur[1]) - pos[1])
                       + abs(float(cur[2]) - pos[2]))
            except Exception:
                continue
            if far > 3.0:
                # 没被拉回去：用 /tp 补一次
                self._tpCommand(pid, pos)

    def _destroy(self, entityId):
        try:
            return bool(self.DestroyEntity(entityId))
        except Exception:
            return False

    # ---------- 背包 / 经验：把这一轮里多出来的收回去 ----------
    def _itemKey(self, item):
        # 同一种东西才算一样：名字 + aux + NBT（附魔之类的）
        if not isinstance(item, dict):
            return None
        name = item.get("newItemName") or item.get("itemName") or u""
        if not name:
            return None
        aux = item.get("newAuxValue")
        if aux is None:
            aux = item.get("auxValue")
        if aux is None:
            aux = item.get("aux")
        try:
            aux = int(aux or 0)
        except Exception:
            aux = 0
        ud = item.get("userData")
        if isinstance(ud, dict) and ud:
            try:
                udKey = u"|".join(u"%s=%s" % (k, ud[k]) for k in sorted(ud.keys()))
            except Exception:
                udKey = u"?"
        else:
            udKey = u""
        return (str(name).lower(), aux, udKey)

    def _itemCount(self, item):
        if not isinstance(item, dict):
            return 0
        try:
            n = int(item.get("count") or 1)
        except Exception:
            n = 1
        return max(0, n)

    def _rewindBag(self, playerId, target):
        # 只做“减法”：这十秒里多出来的物品从背包收回去。
        # 为什么不整包还原：那样会把“这十秒里放进箱子 / 丢出去的东西”
        # 又变一份回到背包里，等于刷物品。
        if not getattr(cfg, "REWIND_INVENTORY", True):
            return 0
        comp = self._itemComp(playerId)
        if comp is None:
            return 0
        rec = self._nearestRec(self._inv.get(playerId), target)
        if rec is None:
            return 0
        allowed = {}
        for it in (rec[1] or []):
            k = self._itemKey(it)
            if k is None:
                continue
            allowed[k] = allowed.get(k, 0) + self._itemCount(it)
        try:
            cur = comp.GetPlayerAllItems(self._invType(), True) or []
        except Exception:
            return 0
        removed = 0
        for slot, it in enumerate(cur):
            k = self._itemKey(it)
            if k is None:
                continue
            cnt = self._itemCount(it)
            keep = int(allowed.get(k, 0))
            if keep >= cnt:
                allowed[k] = keep - cnt
                continue
            allowed[k] = 0
            try:
                comp.SetInvItemNum(int(slot), int(keep))
                removed += (cnt - keep)
            except Exception:
                pass
        return removed

    def _rewindExp(self, playerId, target):
        # 经验同样只做减法：这十秒里多出来的经验扣掉（掉的经验球已经清了）
        if not getattr(cfg, "REWIND_EXP", True):
            return 0
        comp = self._expComp(playerId)
        if comp is None:
            return 0
        rec = self._nearestRec(self._exp.get(playerId), target)
        if rec is None:
            return 0
        old = int(rec[1])
        try:
            cur = int(comp.GetPlayerTotalExp())
        except Exception:
            return 0
        if cur <= old:
            return 0
        try:
            if not comp.SetPlayerTotalExp(old):
                return 0
        except Exception:
            return 0
        return cur - old

    def _reviveDead(self, now, pos, dim, target):
        if not cfg.REVIVE_DEAD:
            return 0
        n = 0
        r = cfg.entityRange()
        for rec in list(self._deaths):
            t, eid, typeStr, dpos, rot, ddim = rec
            if now - t > cfg.rewindSeconds():
                continue
            if ddim != dim or not typeStr:
                continue
            if not self._within(dpos, pos, r):
                continue
            p = dpos
            old = self._sampleAt(eid, target)
            if old is not None:
                p = old[1]
            if self._spawnMob(typeStr, p, rot, ddim) is not None:
                n += 1
        return n

    def _spawnMob(self, typeStr, pos, rot, dim):
        if not typeStr or ":" not in str(typeStr):
            return None
        try:
            r = (0.0, 0.0) if rot is None else (float(rot[0]), float(rot[1]))
        except Exception:
            r = (0.0, 0.0)
        try:
            return self.CreateEngineEntityByTypeStr(
                str(typeStr), (float(pos[0]), float(pos[1]), float(pos[2])), r, int(dim))
        except Exception:
            return None

    def OnSpawnProjectile(self, args=None):
        # 箭矢（以及其它抛射物）刚生成：把出膛的位置记下来。
        # 用发射者的位置（脚下往上抬一点≈手上那个高度），
        # 拿不到发射者才退而求其次读抛射物自己的位置。
        if not args:
            return
        eid = args.get("projectileId")
        if not eid:
            return
        now = time.time()
        pos = None
        spawner = args.get("spawnerId")
        if spawner and str(spawner) != "-1":
            p = self._posOf(spawner)
            if p is not None:
                pos = (float(p[0]), float(p[1]) + 1.4, float(p[2]))
        if pos is None:
            p2 = self._posOf(eid)
            if p2 is None:
                return
            pos = (float(p2[0]), float(p2[1]), float(p2[2]))
        # 出膛速度也记一笔：箭可能已经插在墙上不动了，回溯时把速度写回去
        # 才会真的“重新射出去”。文档说这个事件里读不到 auxvalue，
        # 速度也可能一时读不到，所以读不到就留 None，下一 tick 再补。
        self._shot[eid] = (now, pos, str(args.get("projectileIdentifier") or u""),
                           self._motionOf(eid))
        self._pruneShot(now)
        # 静止药水开着的时候：刚射出去的箭也得马上停住，
        # 不然等下一次范围扫描，它已经飞出去好几格了
        if self._fzOn and getattr(cfg, "FREEZE_ON", True) \
                and self._isProjectile(eid):
            for pid in list(self._fzOn):
                p = self._posOf(pid)
                if p is not None and self._within(pos, p, cfg.freezeRange()):
                    self._freezeEntity(eid)
                    break

    def _pruneShot(self, now):
        keep = max(4, int(getattr(cfg, "SHOT_KEEP", 60)))
        limit = now - max(30.0, cfg.rewindSeconds() * 3.0)
        dead = [k for k, v in self._shot.items() if v[0] < limit]
        for k in dead:
            self._shot.pop(k, None)
        if len(self._shot) > keep:
            items = sorted(self._shot.items(), key=lambda kv: kv[1][0])
            for k, _ in items[:len(items) - keep]:
                self._shot.pop(k, None)

    def _refreshShots(self, now):
        # 生成那一帧没读到速度的，下一 tick 再补一次（就一两支箭，很便宜）
        for eid, rec in list(self._shot.items()):
            try:
                if rec[3] is not None or now - float(rec[0]) > 1.0:
                    continue
            except Exception:
                continue
            m = self._motionOf(eid)
            if m is not None:
                self._shot[eid] = (rec[0], rec[1], rec[2], m)

    def _motionComp(self, entityId):
        try:
            return serverApi.GetEngineCompFactory().CreateActorMotion(entityId)
        except Exception:
            return None

    def _motionOf(self, entityId):
        comp = self._motionComp(entityId)
        if comp is None:
            return None
        try:
            m = comp.GetMotion()
        except Exception:
            return None
        if not m:
            return None
        try:
            v = (float(m[0]), float(m[1]), float(m[2]))
        except Exception:
            return None
        if abs(v[0]) + abs(v[1]) + abs(v[2]) < 1e-6:
            return None
        return v

    def _putShotMotion(self, entityId):
        # 把这条箭当初射出去的速度写回去：只挪位置的话，插在墙上的箭
        # 会停在半空中，得给回速度才会再飞一次
        if not getattr(cfg, "PROJECTILE_KEEP_SPEED", True):
            return False
        rec = self._shot.get(entityId)
        if rec is None:
            return False
        try:
            mv = rec[3]
        except Exception:
            return False
        if mv is None:
            return False
        return self._putMotion(entityId, mv)

    def _muzzleOf(self, entityId):
        # 这支箭是从哪儿射出来的
        rec = self._shot.get(entityId)
        return None if rec is None else rec[1]

    def _projectileTypes(self):
        kinds = getattr(cfg, "PROJECTILE_TYPES", None)
        if kinds is None:
            kinds = ("minecraft:arrow",)
        return tuple(kinds)

    def OnMobDie(self, args=None):
        if not args:
            return
        eid = args.get("id") or args.get("entityId")
        if not eid:
            return
        players = self._playerSet()
        if eid in players:
            return
        now = time.time()
        typeStr = self._typeStrOf(eid)
        rec = self._sampleAt(eid, now - 0.4)
        if rec is not None:
            pos = rec[1]
            rot = rec[2]
        else:
            pos = self._posOf(eid)
            rot = self._rotOf(eid)
        if pos is None or not typeStr:
            return
        self._deaths.append((now, eid, str(typeStr), pos, rot, self._dimOf(eid)))

    # ==================== 方块回溯 ====================
    def OnBlockDestroy(self, args=None):
        if not args or not self._has:
            return
        try:
            self._recordBlock(int(args.get("x")), int(args.get("y")),
                              int(args.get("z")), int(args.get("dimensionId", 0)))
        except Exception:
            pass

    def OnBlockPlace(self, args=None):
        if not args or not self._has:
            return
        try:
            self._recordBlock(int(args.get("x")), int(args.get("y")),
                              int(args.get("z")), int(args.get("dimensionId", 0)))
        except Exception:
            pass

    def OnExplode(self, args=None):
        # 爆炸事件是在“方块被炸掉之前”触发的，这一瞬间方块还立在原地，
        # 所以必须当场把它们的原样读下来。
        # （以前是把坐标丢进队列、过几个 tick 再慢慢读 —— 轮到读的时候
        #   那格早成空气了，记下来的是空气，回溯自然修不回来）
        if not args:
            return
        try:
            dim = int(args.get("dimensionId", 0))
        except Exception:
            dim = 0
        # 静止期间：被冻住的 TNT 不许炸 —— 方块一格不炸、人一点血不掉。
        # 这一段必须放在「身上有没有回溯药水」之前，
        # 不然只喝了静止药水的玩家挡不住爆炸。
        stopped = False
        if cfg.freezeStopExplode() and self._fzBoom and self._isFrozenBlast(args):
            self._stopBlast(args)
            stopped = True
        if not self._has:
            return
        self._exEvents += 1
        cap = max(1, int(cfg.MAX_EXPLODE_BLOCKS))
        seen = 0
        n = 0
        for b in (args.get("blocks") or []):
            if not b or len(b) < 3:
                continue
            try:
                x, y, z = int(b[0]), int(b[1]), int(b[2])
            except Exception:
                continue
            seen += 1
            if len(b) > 3 and self._truthy(b[3]):
                # 这一格已经被取消破坏了，炸不掉，不用记
                continue
            if self._recordBlock(x, y, z, dim):
                self._exBlocks += 1
            n += 1
            if n >= cap:
                break
        if seen == 0 and not stopped:
            # 兜底：万一这一版没把方块列表给过来，就绕着爆点扫一圈，
            # 把还立着的方块（＝马上要被炸掉的那些）记下来
            # （这一炸已经被静止取消的话就不用记了 —— 方块根本不会变）
            self._scanExplode(dim, args.get("explodePos"))

    def _scanExplode(self, dim, pos):
        # 只在拿不到 blocks 列表时才走的兜底路径
        try:
            if not pos or len(pos) < 3:
                return
            cx, cy, cz = int(pos[0]), int(pos[1]), int(pos[2])
        except Exception:
            return
        info = self._blockInfo()
        if info is None:
            return
        r = max(1, int(getattr(cfg, "EXPLODE_SCAN_RADIUS", 6)))
        cap = max(1, int(cfg.MAX_EXPLODE_BLOCKS))
        n = 0
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                for dz in range(-r, r + 1):
                    x, y, z = cx + dx, cy + dy, cz + dz
                    try:
                        d = info.GetBlockNew((x, y, z), int(dim))
                    except Exception:
                        continue
                    if not isinstance(d, dict):
                        continue
                    nm = d.get("name")
                    if not nm or str(nm).endswith(":air"):
                        continue
                    if self._recordBlock(x, y, z, dim):
                        self._exBlocks += 1
                    n += 1
                    if n >= cap:
                        return

    def _recordBlock(self, x, y, z, dim):
        # 方块“要变之前”把它原来的样子记下来。
        # 同一格只留最靠近回溯窗口起点的那一份：
        #   已经有更新的一份（还没过期）就不动它
        key = (int(x), int(y), int(z))
        now = time.time()
        old = self._blocks.get(key)
        if old is not None and (now - old[0]) < cfg.rewindSeconds():
            # 同一格里已经有一份更靠近窗口起点的记录了，留着它
            return True
        info = self._blockInfo()
        if info is None:
            return False
        try:
            d = info.GetBlockNew(key, int(dim))
        except Exception:
            return False
        if not isinstance(d, dict):
            return False
        name = d.get("name")
        if not name or str(name).endswith(":air"):
            # 读到空气：这一格本来就空，或者（万一）事件来得太晚方块已经没了
            return False
        states = None
        st = self._blockState()
        if st is not None:
            try:
                states = st.GetBlockStates(key, int(dim))
            except Exception:
                states = None
        self._blocks[key] = [now, int(dim),
                             {"name": str(name), "aux": int(d.get("aux") or 0)},
                             states]
        return True
        cap = max(100, int(cfg.BLOCK_KEEP))
        if len(self._blocks) > cap:
            items = sorted(self._blocks.items(), key=lambda kv: kv[1][0])
            for k2, _ in items[:max(1, len(items) // 5)]:
                self._blocks.pop(k2, None)

    def _rewindBlocks(self, playerId, now, target=None):
        if target is None:
            target = now - cfg.rewindSeconds()
        pos = self._posOf(playerId)
        if pos is None:
            return 0
        dim = self._dimOf(playerId)
        r = cfg.blockRange()
        n = 0
        drop = []
        for key, rec in self._blocks.items():
            t, bdim, blockDict, states = rec
            if t < target:
                # 这一格十秒前就已经是现在这样了，不用动
                drop.append(key)
                continue
            if bdim != dim:
                continue
            if not self._within(key, pos, r):
                continue
            # 不在这儿直接改方块：一次改几百格会卡一帧，
            # 丢进队列，由 _drainPut 每 tick 恢复一点，卡顿就摊平了
            self._putQ.append((key, bdim, blockDict, states))
            n += 1
            drop.append(key)
        for k in drop:
            self._blocks.pop(k, None)
        return n

    def _drainPut(self):
        # 每 tick 只恢复几格方块
        if not self._putQ:
            return
        limit = max(1, int(getattr(cfg, "BLOCK_PUT_PER_TICK", 64)))
        done = 0
        while self._putQ and done < limit:
            key, dim, blockDict, states = self._putQ.popleft()
            self._putBlock(key, dim, blockDict, states)
            done += 1

    def _putBlock(self, key, dim, blockDict, states):
        if not blockDict or not blockDict.get("name"):
            return False
        info = self._blockInfo()
        if info is None:
            return False
        cur = None
        try:
            cur = info.GetBlockNew(key, int(dim))
        except Exception:
            cur = None
        if isinstance(cur, dict):
            try:
                if (str(cur.get("name")) == str(blockDict.get("name"))
                        and int(cur.get("aux") or 0) == int(blockDict.get("aux") or 0)):
                    return False
            except Exception:
                pass
        ok = False
        try:
            ok = bool(info.SetBlockNew(key, blockDict, 0, int(dim), True, True))
        except Exception:
            ok = False
        if ok and states:
            st = self._blockState()
            if st is not None:
                try:
                    st.SetBlockStates(key, states, int(dim))
                except Exception:
                    pass
        return ok

    # ==================== 昼夜飞快交替 ====================
    def _spinTick(self, now):
        if not self._spin:
            return
        comp = self._timeComp()
        if comp is None:
            self._spin.clear()
            self._spinFrom.clear()
            return
        step = cfg.dayNightStep()
        # 同一维度还有别人在转的话，先别把时间放回去
        busy = set()
        for pid, end in self._spin.items():
            if now < end:
                f = self._spinFrom.get(pid)
                if f is not None:
                    busy.add(f[0])
        for pid in list(self._spin.keys()):
            if now >= self._spin[pid]:
                self._spin.pop(pid, None)
                f = self._spinFrom.pop(pid, None)
                # 转完了：把时间放回按下去之前那一刻
                if f is not None and f[0] not in busy:
                    self._restoreTime(f)
                continue
            dim = self._dimOf(pid)
            cur = self._tod.get(dim)
            if cur is None:
                cur = self._timeOfDay(comp, dim)
            cur = (int(cur) + int(step)) % 24000
            self._tod[dim] = cur
            try:
                comp.SetTimeOfDay(int(cur))
            except Exception:
                pass

    def _restoreTime(self, f):
        # 把时间放回原来的那一刻
        if not f:
            return
        dim, tod = f
        self._tod[dim] = int(tod)
        comp = self._timeComp()
        if comp is None:
            return
        try:
            comp.SetTimeOfDay(int(tod))
        except Exception:
            pass

    # ==================== 玩家死亡 ====================
    def OnPlayerDie(self, args=None):
        # 兜底用的「临时免疫」是写进存档的，人死了也要立刻撤回，
        # 不然重生之后还带着
        if args:
            pid = args.get("id") or args.get("playerId")
            if pid and self._fzImmune.pop(pid, None) is not None:
                self._setImmune(pid, False)
        if not args:
            return
        pid = args.get("id") or args.get("playerId")
        if not pid:
            return
        now = time.time()
        if pid in self._has and cfg.keepHpOnDeath():
            hp = self._hpAt(pid, now - cfg.rewindSeconds())
            if hp is not None and hp > 0:
                self._reviveHp[pid] = float(hp)
        self._clear(pid)
        self._toPlayer(pid, modConfig.EventState, {"show": 0})
        self._toPlayer(pid, modConfig.EventFreezeState, self._fzState(pid, 0, 0))

    def OnPlayerRespawn(self, args=None):
        if not args:
            return
        pid = args.get("playerId") or args.get("id")
        if not pid:
            return
        # 重生之后按钮消失，不再出现
        self._toPlayer(pid, modConfig.EventState, {"show": 0})
        self._toPlayer(pid, modConfig.EventFreezeState, self._fzState(pid, 0, 0))
        hp = self._reviveHp.pop(pid, None)
        if hp is None or hp <= 0:
            return
        self._setHealth(pid, hp)
        self._hpTask[pid] = [time.time() + 0.6, hp]

    def _hpAt(self, playerId, target):
        arr = self._hp.get(playerId)
        if not arr:
            return None
        best = None
        for rec in arr:
            if rec[0] <= target:
                best = rec
            else:
                break
        return None if best is None else best[1]

    def _clear(self, playerId):
        # 昼夜还没转完人就走了（死了 / 退出世界）：先把时间放回原来的
        f = self._spinFrom.pop(playerId, None)
        if f is not None and playerId in self._spin:
            self._restoreTime(f)
        for d in (self._has, self._until, self._spin, self._hp,
                  self._lastUse, self._near, self._pending, self._selfChk,
                  self._inv, self._exp, self._lastFzDrink, self._fzNear):
            d.pop(playerId, None)
        # 静止药水：人走了 / 死了，他那一份开关也撤掉，
        # 剩下的实体由 _freezeTick 统一解冻
        self._fz.pop(playerId, None)
        self._fzOn.discard(playerId)

    # ==================== 静止药水 ====================
    #  喝下去 -> 屏幕右侧出现「静止」按钮，三分钟内随便开关。
    #  开：身边 FREEZE_RANGE 格以内
    #     · 生物：屏蔽原生 AI（官方说明：屏蔽后无法行动、不受重力、不会被推动），
    #       顺带把动作也冻住；
    #     · 箭矢这类抛射物：AI 那套对它们没用，只能每 tick 把速度按成 0，
    #       解冻时把原来的速度还回去，箭会接着飞；
    #     · 火焰：用游戏自带的 dofiretick 规则，不蔓延、不熄灭。
    #  关：把上面这些一条条还原回去。
    def _fzState(self, playerId, show, on):
        # 发给客户端的按钮状态：要不要亮 / 现在是停还是没停 / 药效还剩几秒
        # （右上角那个倒计时就是靠 left 算的）
        left = 0.0
        end = self._fz.get(playerId)
        if end is not None:
            left = max(0.0, float(end) - time.time())
        return {"show": int(show), "on": int(on), "left": round(left, 1)}

    def _freezeDrink(self, playerId):
        now = time.time()
        self._fz[playerId] = now + cfg.freezeSeconds()
        self._fzOn.discard(playerId)
        self._toPlayer(playerId, modConfig.EventFreezeState,
                            self._fzState(playerId, 1, 0))
        if getattr(cfg, "FREEZE_TIP_ON_DRINK", True):
            hint = u""
            if getattr(cfg, "FREEZE_KEY_ENABLED", True):
                hint = u"（电脑端按 %s 键）" % getattr(cfg, "FREEZE_KEY_LABEL", u"G")
            self._tip(playerId,
                      u"喝下 %s：屏幕右侧出现静止按钮%s，按一下身边 %d 格全部停住，"
                      u"再按一下恢复；药效 %d 秒"
                      % (cfg.FREEZE_POTION_NAME, hint,
                         int(round(cfg.freezeRange())),
                         int(round(cfg.freezeSeconds()))),
                      "AQUA")

    def OnFreezeButton(self, args=None):
        if not args or not getattr(cfg, "FREEZE_ON", True) or not cfg.MODE_ON:
            return
        pid = args.get("playerId")
        if not pid:
            return
        end = self._fz.get(pid)
        if end is None:
            # 身上没有静止药水：直接忽略，不提示任何东西
            return
        now = time.time()
        if now >= end:
            self._fz.pop(pid, None)
            self._fzOn.discard(pid)
            self._fzNear.pop(pid, None)
            self._toPlayer(pid, modConfig.EventFreezeState, self._fzState(pid, 0, 0))
            return
        if pid in self._fzOn:
            self._fzOn.discard(pid)
            self._fzNear.pop(pid, None)
            self._toPlayer(pid, modConfig.EventFreezeState, self._fzState(pid, 1, 0))
            self._tip(pid, u"静止解除，身边的东西又开始动了", "YELLOW")
        else:
            self._fzOn.add(pid)
            self._fzNear.pop(pid, None)
            self._toPlayer(pid, modConfig.EventFreezeState, self._fzState(pid, 1, 1))
            self._tip(pid, u"身边 %d 格已停住：生物不动、火焰不烧、箭停在半空"
                      % int(round(cfg.freezeRange())), "AQUA")

    def _freezeTick(self, now):
        if not getattr(cfg, "FREEZE_ON", True):
            self._fz.clear()
            self._fzOn.clear()
            self._freezeReleaseAll()
            self._fzBlockTick(now)
            return
        # 药效到点：按钮收掉、开关撤掉
        for pid in list(self._fz.keys()):
            if now < self._fz[pid]:
                continue
            self._fz.pop(pid, None)
            self._fzOn.discard(pid)
            self._fzNear.pop(pid, None)
            self._toPlayer(pid, modConfig.EventFreezeState, self._fzState(pid, 0, 0))
            self._tip(pid, u"静止药水到期了", "GRAY")
        # 先把「被换成 TNT 方块」的那批按规矩处理（还在范围内就留着，没人罩了就还回去）
        self._fzBlockTick(now)
        if not self._fzOn:
            self._freezeReleaseAll()
            return
        players = self._playerSet()
        want = {}
        for pid in list(self._fzOn):
            if self._posOf(pid) is None:
                # 人不在了（换维度 / 掉线）：他那一份先撤掉
                self._fzOn.discard(pid)
                self._fzNear.pop(pid, None)
                continue
            for eid in self._freezeNear(pid):
                if eid and eid not in players:
                    want[eid] = True
        if not want:
            self._freezeReleaseAll()
            return
        if getattr(cfg, "FREEZE_AI", True) or getattr(cfg, "FREEZE_MOTION", True):
            for eid in want:
                if eid not in self._fzAi and eid not in self._fzHold:
                    self._freezeEntity(eid)
        # 跑出范围 / 没了的：解冻
        for eid in list(self._fzAi.keys()):
            if eid not in want:
                self._thawEntity(eid)
        for eid in list(self._fzHold.keys()):
            if eid not in want and not self._keepAlive(eid, now):
                self._thawEntity(eid)
                continue
            # 抛射物会被物理继续拉：位置、朝向、速度一起按住才算真停住
            self._pinProjectile(eid)
            # TNT 这种会炸的：引信没法暂停，就定时换一坨新的（见 _tntTick）
            self._tntTick(eid)
        if cfg.freezeFire():
            self._setFireRule(True)

    def _freezeReleaseAll(self):
        if (not self._fzAi and not self._fzHold and not self._fzBoom
                and not self._fzKeep and not self._fireOff):
            return
        for eid in list(self._fzAi.keys()):
            self._thawEntity(eid)
        for eid in list(self._fzHold.keys()):
            self._thawEntity(eid)
        self._fzAi.clear()
        self._fzHold.clear()
        self._fzPrev.clear()
        self._fzBoom.clear()
        self._fzKeep.clear()
        if self._fireOff:
            self._setFireRule(False)

    def _freezeNear(self, playerId):
        # 和 _nearby 一个道理，只是间隔更短（默认每 5 tick 重找一遍）
        now = time.time()
        gap = max(1, int(getattr(cfg, "FREEZE_RESCAN_TICKS", 5))) / 20.0
        cached = self._fzNear.get(playerId)
        if cached is not None and (now - cached[0]) < gap:
            return cached[1]
        out = self._nearbyRaw(playerId, cfg.freezeRange())
        cap = max(1, int(getattr(cfg, "FREEZE_MAX_ENTITIES", 150)))
        if len(out) > cap:
            out = out[:cap]
        self._fzNear[playerId] = (now, out)
        return out

    def _freezeEntity(self, entityId):
        if self._isBoom(entityId):
            # 会炸的东西（TNT）：多记一笔，好定时「换一坨新的」（见 _tntTick）
            self._rememberBoom(entityId)
            if (cfg.freezeTntAsBlock() and self._isProjectile(entityId)
                    and self._tntToBlock(entityId)):
                # 已经变成一格 TNT 方块了：不会闪、不用按住、也炸不了
                self._fzBoom.pop(entityId, None)
                return
        if self._isProjectile(entityId):
            if getattr(cfg, "FREEZE_MOTION", True):
                # 光把速度清零挡不住引擎：它会接着算重力、还会按速度改朝向，
                # 箭看起来就会自己往下拐。所以【速度 + 位置 + 朝向】三样
                # 一起记下来，每 tick 一起按住（_pinProjectile）。
                self._fzHold[entityId] = (self._motionOf(entityId),
                                          self._posOf(entityId),
                                          self._rotOf(entityId))
                self._pinProjectile(entityId)
            return
        if not getattr(cfg, "FREEZE_AI", True):
            return
        comp = self._aiComp(entityId)
        if comp is not None:
            try:
                comp.SetBlockControlAi(False,
                                       bool(getattr(cfg, "FREEZE_ANIM", True)))
            except Exception:
                pass
        # 不管成没成先记一笔，别每 tick 都去重试
        self._fzAi[entityId] = True

    def _thawEntity(self, entityId):
        if entityId in self._fzAi:
            self._fzAi.pop(entityId, None)
            comp = self._aiComp(entityId)
            if comp is not None:
                try:
                    comp.SetBlockControlAi(True, False)
                except Exception:
                    pass
        self._fzPrev.pop(entityId, None)
        self._fzBoom.pop(entityId, None)
        self._fzKeep.pop(entityId, None)
        rec = self._fzHold.pop(entityId, None)
        if rec is None:
            return
        pos, rot = rec[1], rec[2]
        if pos is not None:
            try:
                serverApi.GetEngineCompFactory().CreatePos(entityId).SetFootPos(pos)
            except Exception:
                pass
        if rot is not None:
            try:
                serverApi.GetEngineCompFactory().CreateRot(entityId).SetRot(rot)
            except Exception:
                pass
        m = rec[0]
        if m is not None and getattr(cfg, "FREEZE_RESTORE_MOTION", True):
            self._putMotion(entityId, m)

    @staticmethod
    def _dirOf(rot):
        # 由（上下角度, 左右角度）算出实体正面朝着哪个方向。
        # 角度是「度」，和游戏里 rot 组件的一样：0 度朝正南（+Z），
        # 上下角度为正表示朝下。
        if not rot:
            return (0.0, 0.0, 1.0)
        try:
            pitch = math.radians(float(rot[0]))
            yaw = math.radians(float(rot[1]))
            cp = math.cos(pitch)
            return (-math.sin(yaw) * cp, -math.sin(pitch),
                    math.cos(yaw) * cp)
        except Exception:
            return (0.0, 0.0, 1.0)

    def _pinProjectile(self, entityId):
        # 把这一支按回冻住那一刻的位置和朝向。
        #
        # 关键点：千万不能把速度直接按成 0。
        # 引擎每 tick 都会拿「这一 tick 走的那个方向」去重算箭的朝向
        # （射出去的箭一直朝前飞，就是这么来的）。速度一旦变成 0，
        # 剩下的就只有重力那个朝下的分量，引擎就把箭掰成头朝下 ——
        # 看起来就是「冻住了还在自己拐弯」。
        #
        # 做法（每 tick 干这三件事）：
        #   1) 位置：直接摆回冻住那一格。
        #      注意是「直接摆回去」，不是先往回退再让引擎推回来 ——
        #      往回退那一下会被渲染出来，看起来就是箭在原地抖 / 转圈。
        #   2) 朝向：掰回冻住那一刻的朝向。
        #   3) 速度：给一个方向 = 箭头原本朝向、大小只有 HOLD_STEP 的速度，
        #      再减掉「引擎自己额外推的那一份」（重力之类）。
        #      那一份不用猜，直接量出来：上一 tick 它把箭推到了哪，
        #      减去我们上 tick 给的速度，剩下的就是它干的。
        #      这么一来，箭头朝向算出来还是原来的方向，而位置那 0.01 格
        #      的位移会被第 1 步抹掉，既不动、也不歪、也不抖。
        rec = self._fzHold.get(entityId)
        if rec is None:
            return
        pos, rot = rec[1], rec[2]
        step = max(0.001, float(getattr(cfg, "FREEZE_HOLD_STEP", 0.01)))
        cap = max(0.05, float(getattr(cfg, "FREEZE_HOLD_MAX", 0.6)))
        d = self._dirOf(rot)
        want = (d[0] * step, d[1] * step, d[2] * step)
        prev = self._fzPrev.get(entityId)
        extra = (0.0, 0.0, 0.0)
        if prev is None:
            # 第一次还没来得及量：先按经验猜「引擎每 tick 会往下拽 gravity 格」。
            # 猜不中也没关系，下一个 tick 就量出真值并立刻改过来
            # （最多错一帧，50 毫秒，肉眼看不出来）。
            guess = max(0.0, float(getattr(cfg, "FREEZE_HOLD_GRAVITY", 0.05)))
            prev = (0.0, 0.0, 0.0)
            extra = (0.0, -guess, 0.0)
        elif pos is not None:
            now = self._posOf(entityId)
            if now is not None:
                extra = (self._clampf(now[0] - pos[0] - prev[0], cap),
                         self._clampf(now[1] - pos[1] - prev[1], cap),
                         self._clampf(now[2] - pos[2] - prev[2], cap))
        mv = (self._clampf(want[0] - extra[0], cap),
              self._clampf(want[1] - extra[1], cap),
              self._clampf(want[2] - extra[2], cap))
        self._fzPrev[entityId] = mv
        self._putMotion(entityId, mv)
        if pos is not None:
            try:
                serverApi.GetEngineCompFactory().CreatePos(entityId).SetFootPos(pos)
            except Exception:
                pass
        if rot is not None:
            try:
                serverApi.GetEngineCompFactory().CreateRot(entityId).SetRot(rot)
            except Exception:
                pass

    @staticmethod
    def _clampf(v, lim):
        try:
            v = float(v)
        except Exception:
            return 0.0
        if v != v:              # NaN
            return 0.0
        if v > lim:
            return lim
        if v < -lim:
            return -lim
        return v

    def _isProjectile(self, entityId):
        kinds = getattr(cfg, "FREEZE_PROJECTILE_TYPES", None)
        if not kinds:
            return False
        t = self._typeStrOf(entityId)
        return bool(t) and t in kinds

    # ---- 「点着的 TNT」↔「一格 TNT 方块」 ----
    # 点着的 TNT 自带闪白动画（引信快到点时会越闪越急），没有接口能停。
    # 所以静止期间把它换成一格真正的 TNT 方块：外形几乎一样，但完全静止 ——
    # 不闪、不冒烟、没有引信、也不会炸。解除静止时再换回点着的 TNT。
    def _blkName(self, blk, dim):
        info = self._blockInfo()
        if info is None:
            return None
        try:
            d = info.GetBlockNew(tuple(blk), int(dim))
        except Exception:
            return None
        if not isinstance(d, dict):
            return None
        nm = d.get("name")
        return None if not nm else str(nm)

    def _tntToBlock(self, entityId):
        pos = self._posOf(entityId)
        if pos is None:
            return False
        try:
            blk = (int(math.floor(float(pos[0]))),
                   int(math.floor(float(pos[1]))),
                   int(math.floor(float(pos[2]))))
        except Exception:
            return False
        dim = int(self._dimOf(entityId) or 0)
        cur = self._blkName(blk, dim)
        if cur not in (None, u"", u"minecraft:air"):
            # 那一格被别的东西占着：不敢硬塞，还是走老办法（把它按住）
            return False
        self._putBlock(blk, dim, {"name": u"minecraft:tnt", "aux": 0}, None)
        if self._blkName(blk, dim) != u"minecraft:tnt":
            # 放不进去（区域没加载 / 被保护…）：老办法
            return False
        self._fzBlock[(blk[0], blk[1], blk[2], dim)] = {
            "blk": blk,
            "pos": (float(pos[0]), float(pos[1]), float(pos[2])),
            "rot": self._rotOf(entityId),
            "dim": dim,
            "type": self._typeStrOf(entityId) or u"minecraft:tnt"}
        # 方块放好了才把点着的那坨删掉（同一 tick 内完成，画面上不会闪空）
        self._destroy(entityId)
        return True

    def _blkCovered(self, blk, dim):
        # 附近还有没有「开着静止」的玩家罩着这一格
        r = cfg.freezeRange()
        for pid in list(self._fzOn):
            if self._dimOf(pid) != dim:
                continue
            p = self._posOf(pid)
            if p is not None and self._within(blk, p, r):
                return True
        return False

    def _blockToTnt(self, key):
        rec = self._fzBlock.pop(key, None)
        if rec is None:
            return
        blk = rec.get("blk")
        dim = int(rec.get("dim", 0))
        if not blk or self._blkName(blk, dim) != u"minecraft:tnt":
            # 那一格已经不是我们放的那块了（被挖了 / 被换了）：什么都不用还
            return
        self._putBlock(blk, dim, {"name": u"minecraft:air", "aux": 0}, None)
        pos = rec.get("pos")
        if pos is None:
            return
        # 原地放回一坨点着的 TNT，让它接着炸
        self._spawnMob(rec.get("type") or u"minecraft:tnt", pos,
                       rec.get("rot"), dim)

    def _fzBlockTick(self, now):
        if not self._fzBlock:
            return
        for key in list(self._fzBlock.keys()):
            rec = self._fzBlock.get(key)
            if rec is None:
                continue
            blk = rec.get("blk")
            dim = int(rec.get("dim", 0))
            if not blk or self._blkName(blk, dim) != u"minecraft:tnt":
                # 那格已经不是 TNT 方块了：没什么可还的
                self._fzBlock.pop(key, None)
                continue
            if self._blkCovered(blk, dim):
                continue
            self._blockToTnt(key)

    # ==================== 静止期间：TNT 不许炸 ====================
    # 为什么不用「把引信暂停」：游戏没有这个接口（引信是引擎自己在跑）。
    # 所以换两条路一起走：
    #   · 主路 _tntTick：被冻住的 TNT 每隔 2 秒，在原地换成一坨刚点着的新 TNT，
    #     新的引信是满的（4 秒），于是永远走不到爆炸那一步 —— 看起来就是卡住不炸。
    #   · 兜底 _stopBlast：万一真炸了（引信短到来不及换），
    #     就把这一炸的方块破坏全取消、要受伤的对象临时护住、血再补回去。
    def _isBoom(self, entityId):
        kinds = getattr(cfg, "FREEZE_EXPLODE_TYPES", None)
        if not kinds:
            return False
        t = self._typeStrOf(entityId)
        return bool(t) and t in kinds

    def _rememberBoom(self, entityId):
        # n 直接从「差一格就换」开始：刚被冻住的那坨，下一 tick 就换成一坨新的，
        # 免得它身上本来剩的引信没几秒了、还没来得及换就炸了
        self._fzBoom[entityId] = {"n": max(0, cfg.freezeTntTicks() - 1),
                                  "pos": self._posOf(entityId),
                                  "rot": self._rotOf(entityId),
                                  "dim": self._dimOf(entityId),
                                  "type": self._typeStrOf(entityId)}

    def _keepAlive(self, entityId, now):
        # 刚在原地「换」出来的新 TNT，可能这一两 tick 还没被“谁在附近”扫到。
        # 这段时间里别把它当成“跑出范围”解冻了，不然它会掉下去。
        when = self._fzKeep.get(entityId)
        if when is None:
            return False
        if now < when:
            return True
        self._fzKeep.pop(entityId, None)
        return False

    def _tntTick(self, entityId):
        if not cfg.freezeStopExplode() or not cfg.freezeTntRefresh():
            return
        rec = self._fzBoom.get(entityId)
        if rec is None:
            return
        if not self._isProjectile(entityId):
            # 苦力怕这种是生物：把 AI 屏蔽掉它就不会自爆了，不用换来换去
            return
        rec["n"] = int(rec.get("n", 0)) + 1
        if rec["n"] < cfg.freezeTntTicks():
            return
        rec["n"] = 0
        self._refreshBoom(entityId, rec)

    def _refreshBoom(self, oldId, rec):
        # 原地换一坨新的：位置、朝向照旧，引信打回满的。
        pos = self._posOf(oldId) or rec.get("pos")
        if pos is None:
            self._fzBoom.pop(oldId, None)
            return
        rot = self._rotOf(oldId) or rec.get("rot") or (0.0, 0.0)
        dim = rec.get("dim", 0)
        kind = rec.get("type") or u"minecraft:tnt"
        # 先把新的造出来，再造不出来就留着旧的（宁可引信继续走，也不能让它凭空没了）
        newId = self._spawnMob(kind, pos, rot, dim)
        if not newId:
            return
        self._destroy(oldId)
        self._fzHold.pop(oldId, None)
        self._fzPrev.pop(oldId, None)
        self._fzBoom.pop(oldId, None)
        try:
            pos = (float(pos[0]), float(pos[1]), float(pos[2]))
        except Exception:
            self._destroy(newId)
            return
        self._fzBoom[newId] = {"n": 0, "pos": pos, "rot": rot, "dim": dim,
                               "type": kind}
        self._fzHold[newId] = ((0.0, 0.0, 0.0), pos, rot)
        self._fzPrev.pop(newId, None)
        self._fzKeep[newId] = time.time() + cfg.freezeTntKeep()
        # 下一 tick 重新找一圈，好让这坨新的被认出来
        self._fzNear.clear()
        self._pinProjectile(newId)

    def _isFrozenBlast(self, args):
        # 这一炸是不是「被冻住的那个爆炸物」炸的？
        if not self._fzBoom:
            return False
        src = args.get("sourceId")
        if src and (src in self._fzBoom or src in self._fzHold
                    or src in self._fzAi):
            return True
        # sourceId 有时候不是那坨 TNT（可能是点火的人），那就看爆点：
        # 爆点紧挨着某个被冻住的爆炸物，就当是它炸的。
        pos = args.get("explodePos")
        if not pos or len(pos) < 3:
            return False
        try:
            p = (float(pos[0]), float(pos[1]), float(pos[2]))
        except Exception:
            return False
        r = cfg.freezeBlastRadius()
        for rec in self._fzBoom.values():
            if self._within(p, rec.get("pos") or (0.0, 0.0, 0.0), r):
                return True
        return False

    def _stopBlast(self, args):
        # 1) 这一炸：一格方块都不许掉
        for b in (args.get("blocks") or []):
            if not b:
                continue
            try:
                if len(b) > 3:
                    b[3] = True
            except Exception:
                pass
        # 2) 这一炸：谁都不许掉血
        victims = args.get("victims")
        if not victims:
            return
        self._shieldVictims(victims)
        try:
            del victims[:]
        except Exception:
            pass

    def _shieldVictims(self, victims):
        now = time.time()
        hold = now + cfg.freezeShieldSeconds()
        heal = now + cfg.freezeHealDelay()
        for eid in victims:
            if not eid:
                continue
            hp = self._healthOf(eid)
            if hp is not None and hp > 0:
                # 兜底：过一会儿看看血少没少，少了就补回来
                self._fzHeal[eid] = (hp, heal)
            if self._setImmune(eid, True):
                self._fzImmune[eid] = hold

    def _setImmune(self, entityId, on):
        try:
            comp = serverApi.GetEngineCompFactory().CreateHurt(entityId)
        except Exception:
            return False
        if comp is None:
            return False
        try:
            return bool(comp.ImmuneDamage(bool(on)))
        except Exception:
            return False

    def _fzGuardTick(self, now):
        # 兜底用的两件小事，平时两个字典都是空的，等于什么都没做。
        if self._fzImmune:
            for eid in list(self._fzImmune.keys()):
                if now < self._fzImmune[eid]:
                    continue
                self._fzImmune.pop(eid, None)
                self._setImmune(eid, False)
        if not self._fzHeal:
            return
        for eid in list(self._fzHeal.keys()):
            hp, when = self._fzHeal[eid]
            if now < when:
                continue
            self._fzHeal.pop(eid, None)
            cur = self._healthOf(eid)
            if cur is None or cur >= hp:
                continue
            self._setHealth(eid, hp)

    def _aiComp(self, entityId):
        try:
            return serverApi.GetEngineCompFactory().CreateControlAi(entityId)
        except Exception:
            return None

    def _putMotionZero(self, entityId):
        return self._putMotion(entityId, (0.0, 0.0, 0.0))

    def _putMotion(self, entityId, motion):
        comp = self._motionComp(entityId)
        if comp is None:
            return False
        try:
            return bool(comp.SetMotion(motion))
        except Exception:
            return False

    def _setFireRule(self, off):
        # off=True -> 关掉火焰规则：火焰不蔓延、不熄灭，一直保持原样
        if not cfg.freezeFire():
            return
        want = bool(off)
        if want == self._fireOff:
            return
        if (not want) and (not cfg.freezeFireRestore()):
            self._fireOff = False
            return
        cmd = u"/gamerule dofiretick %s" % (u"false" if want else u"true")
        try:
            comp = serverApi.GetEngineCompFactory().CreateCommand(
                serverApi.GetLevelId())
            comp.SetCommand(cmd)
        except Exception:
            pass
        self._fireOff = want

    def OnExtinguishFire(self, args=None):
        # 静止期间玩家想把火扑灭：把火放回去，火焰一直保持
        if not args or not self._fzOn or not cfg.freezeFire():
            return
        pos = args.get("pos")
        if not pos:
            return
        try:
            key = (int(round(float(pos[0]))), int(round(float(pos[1]))),
                   int(round(float(pos[2]))))
        except Exception:
            return
        for pid in list(self._fzOn):
            p = self._posOf(pid)
            if p is not None and self._within(key, p, cfg.freezeRange()):
                self._putBlock(key, self._dimOf(pid),
                               {"name": "minecraft:fire", "aux": 0}, None)
                return

    # ==================== 小工具 ====================
    def _truthy(self, v):
        # blocks 列表里那个 cancel 可能是 True/False，也可能是 "True"/"False"
        if isinstance(v, str):
            return v.strip().lower() in ("1", "true", "yes")
        return bool(v)

    def _within(self, a, b, r):
        try:
            return (abs(float(a[0]) - float(b[0])) <= r
                    and abs(float(a[1]) - float(b[1])) <= r
                    and abs(float(a[2]) - float(b[2])) <= r)
        except Exception:
            return False

    def _nearbyRaw(self, playerId, radius):
        # 不带缓存：真的去问引擎“这一圈里有谁”
        out = []
        pos = self._posOf(playerId)
        if pos is None:
            return out
        dim = self._dimOf(playerId)
        r = max(1.0, float(radius))
        lo = (pos[0] - r, pos[1] - r, pos[2] - r)
        hi = (pos[0] + r, pos[1] + r, pos[2] + r)
        ids = None
        for owner in (serverApi.GetLevelId(), playerId):
            try:
                ids = serverApi.GetEngineCompFactory().CreateGame(owner) \
                    .GetEntitiesInSquareArea(None, lo, hi, dim)
            except Exception:
                ids = None
            if ids:
                break
        for e in (ids or []):
            if e and e != playerId and e not in out:
                out.append(e)
        return out

    def _nearby(self, playerId, radius):
        now = time.time()
        gap = float(cfg.cacheTicks()) / 20.0
        cached = self._near.get(playerId)
        if cached is not None and (now - cached[0]) < gap:
            return cached[1]
        out = self._nearbyRaw(playerId, radius)
        cap = max(1, int(cfg.MAX_ENTITIES))
        if len(out) > cap:
            out = out[:cap]
        self._near[playerId] = (now, out)
        return out

    def _playerSet(self):
        try:
            return set(serverApi.GetPlayerList() or [])
        except Exception:
            return set()

    def _posOf(self, entityId):
        try:
            return serverApi.GetEngineCompFactory().CreatePos(entityId).GetFootPos()
        except Exception:
            return None

    def _rotOf(self, entityId):
        try:
            r = serverApi.GetEngineCompFactory().CreateRot(entityId).GetRot()
            if r is None:
                return None
            return (float(r[0]), float(r[1]))
        except Exception:
            return None

    def _dimOf(self, entityId):
        try:
            return serverApi.GetEngineCompFactory().CreateDimension(
                entityId).GetEntityDimensionId()
        except Exception:
            return 0

    def _typeStrOf(self, entityId):
        factory = serverApi.GetEngineCompFactory()
        for maker in ("CreateEngineType", "CreateEntityType"):
            try:
                comp = factory.__getattribute__(maker)(entityId)
                if comp is not None:
                    t = comp.GetEngineTypeStr()
                    if t:
                        return str(t)
            except Exception:
                continue
        return u""

    def _healthAttr(self):
        try:
            return serverApi.GetMinecraftEnum().AttrType.HEALTH
        except Exception:
            return 0

    def _healthOf(self, entityId):
        try:
            comp = serverApi.GetEngineCompFactory().CreateAttr(entityId)
        except Exception:
            return None
        if comp is None:
            return None
        try:
            v = comp.GetAttrValue(self._healthAttr())
            return None if v is None else float(v)
        except Exception:
            return None

    def _setHealth(self, entityId, hp):
        try:
            hp = float(hp)
        except Exception:
            return
        if hp <= 0:
            return
        try:
            comp = serverApi.GetEngineCompFactory().CreateAttr(entityId)
        except Exception:
            return
        if comp is None:
            return
        attr = self._healthAttr()
        try:
            mx = comp.GetAttrMaxValue(attr)
        except Exception:
            mx = None
        if mx is not None:
            try:
                if hp > float(mx):
                    comp.SetAttrMaxValue(attr, int(hp) + 1)
            except Exception:
                pass
        try:
            comp.SetAttrValue(attr, hp)
        except Exception:
            pass

    def _gameComp(self):
        for owner in (serverApi.GetLevelId(), None):
            try:
                comp = serverApi.GetEngineCompFactory().CreateGame(owner)
            except Exception:
                continue
            if comp is not None:
                return comp
        return None

    def _blockInfo(self):
        for owner in (serverApi.GetLevelId(), None):
            try:
                comp = serverApi.GetEngineCompFactory().CreateBlockInfo(owner)
            except Exception:
                continue
            if comp is not None:
                return comp
        return None

    def _blockState(self):
        for owner in (serverApi.GetLevelId(), None):
            try:
                comp = serverApi.GetEngineCompFactory().CreateBlockState(owner)
            except Exception:
                continue
            if comp is not None:
                return comp
        return None

    def _itemComp(self, playerId):
        try:
            return serverApi.GetEngineCompFactory().CreateItem(playerId)
        except Exception:
            return None

    def _expComp(self, playerId):
        try:
            return serverApi.GetEngineCompFactory().CreateExp(playerId)
        except Exception:
            return None

    def _invType(self):
        try:
            return serverApi.GetMinecraftEnum().ItemPosType.INVENTORY
        except Exception:
            return 0

    def _timeComp(self):
        for owner in (serverApi.GetLevelId(), None):
            try:
                comp = serverApi.GetEngineCompFactory().CreateTime(owner)
            except Exception:
                continue
            if comp is not None:
                return comp
        return None

    def _timeOfDay(self, comp, dim):
        try:
            passed = comp.GetTime()
            if passed is not None:
                return int(passed) % 24000
        except Exception:
            pass
        try:
            c2 = serverApi.GetEngineCompFactory().CreateDimension(serverApi.GetLevelId())
            passed = c2.GetLocalTime(dim)
            if passed is not None:
                return int(passed) % 24000
        except Exception:
            pass
        return 0

    def _tip(self, playerId, text, color="AQUA"):
        try:
            comp = serverApi.GetEngineCompFactory().CreateGame(playerId)
            try:
                comp.SetOneTipMessage(playerId, serverApi.GenerateColor(color) + text)
            except Exception:
                comp.SetOneTipMessage(playerId, text)
        except Exception:
            pass

    def OnAskSound(self, args=None):
        # 客户端自己放不出来，服务端用 /playsound 兜底放一次
        pid = None
        if args:
            pid = args.get("playerId")
        if not pid or not cfg.buttonSoundOn():
            return
        self._playSound(pid, str(cfg.buttonSound()),
                        float(getattr(cfg, "BUTTON_SOUND_VOLUME", 1.0)),
                        float(getattr(cfg, "BUTTON_SOUND_PITCH", 1.0)), 48.0)

    def _playSound(self, entityId, name, volume=1.0, pitch=1.0, radius=32.0):
        if not name:
            return
        try:
            comp = serverApi.GetEngineCompFactory().CreateCommand(serverApi.GetLevelId())
            comp.SetCommand("/playsound %s @a[r=%s] ~ ~ ~ %s %s"
                            % (str(name), float(radius), float(volume), float(pitch)),
                            entityId)
        except Exception:
            pass

    def _toPlayer(self, playerId, eventName, data):
        try:
            self.NotifyToClient(playerId, eventName, data)
        except Exception:
            pass
