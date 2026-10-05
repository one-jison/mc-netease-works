# -*- coding: utf-8 -*-
# ============================================================
#  台球 — 客户端
#    · 附近有没有球桌由服务端算（两格以内就出按钮），这边只管显示
#    · 【进入台球】按钮点了就把球桌位置报给服务端
#    · 服务端说「开球了」，本地用和它一模一样的物理算一遍，画面立刻动
#    · 服务端说「现在轮到谁」，界面上的字就跟着换
# ============================================================
import time

import mod.client.extraClientApi as clientApi

ClientSystem = clientApi.GetClientSystemCls()
compFactory = clientApi.GetEngineCompFactory()

from PoolScripts import modConfig


class PoolClientSystem(ClientSystem):

    def __init__(self, namespace, systemName):
        super(PoolClientSystem, self).__init__(namespace, systemName)
        self.hud = None
        self.hudTries = 0
        self.hudBad = 0
        self.hudName = None
        self.main = None
        self.mainTries = 0
        self.mainBad = 0
        self.mainName = None
        self.mainPush = 0
        self.roomData = None
        self.inRoom = False
        self.nearKey = None
        self.nearWant = (False, None, 0)   # 服务端最后一次说「附近有没有球桌」
        self.lastEnter = 0.0
        self.lastExit = 0.0
        self.uiReg = False
        self.regNames = set()
        self.hudNextTry = 0.0
        self.mainNextTry = 0.0
        self.diagSent = False
        self.diagT0 = 0.0
        self.keyDone = False
        self.keyTries = 0
        self.keyTryT = 0.0
        # ★ 世界里那颗按钮：照《化身HIM》那套 —— 一进游戏就把界面建好放着，
        #   「离球桌多近」只决定它露不露脸（点亮 / 藏起来），不再建了拆、拆了建。
        #   之前那版非等一个「世界加载完」的事件才肯建，可那事件在这台机器上
        #   一次都没来过，所以界面从头到尾没被建过 —— 这就是「靠近没按钮」的真凶。
        self.hudTryT = 0.0
        self._listen()

    # ==================== 事件 ====================
    def _listen(self):
        ns = clientApi.GetEngineNamespace()
        sn = clientApi.GetEngineSystemName()
        L = self.ListenForEvent
        L(ns, sn, "OnScriptTickClient", self, self.OnTick)
        L(ns, sn, modConfig.UiInitFinishedEvent, self, self.OnUIInit)
        L(ns, sn, "OnLocalPlayerStopLoading", self, self.OnStopLoading)
        L(modConfig.ModName, modConfig.ServerSystemName,
          modConfig.EventRoom, self, self.OnRoom)
        L(modConfig.ModName, modConfig.ServerSystemName,
          modConfig.EventShot, self, self.OnShot)
        L(modConfig.ModName, modConfig.ServerSystemName,
          modConfig.EventTip, self, self.OnTip)
        L(modConfig.ModName, modConfig.ServerSystemName,
          modConfig.EventNear, self, self.OnNear)
        L(ns, sn, "OnCustomKeyPressInGame", self, self.OnCustomKey)
        L(ns, sn, "OnKeyPressInGame", self, self.OnKeyPress)

    def OnUIInit(self, args=None):
        self._ensureHud()
        self._registerKeys()

    def OnStopLoading(self, args=None):
        # 每次进世界：引擎会把上一局的界面收走，所以这里重建一遍
        self.diagSent = False
        self.diagT0 = 0.0
        self.hud = None
        self.hudName = None
        self.hudTries = 0
        self.hudNextTry = 0.0
        self.hudTryT = 0.0
        self._ensureHud()
        self._registerKeys()
        self._syncHud()

    # ==================== 每帧 ====================
    def OnTick(self, args=None):
        self._tickHud()
        self._tickDiag()
        self._tickKeys()
        if self.inRoom and self.main is None:
            self._ensureMain()
        if self.main is not None and self.mainPush > 0 and self.roomData is not None:
            self.mainPush -= 1
            try:
                self.main.ApplyRoom(self.roomData)
            except Exception:
                pass

    # ==================== 附近有没有球桌（服务端算好告诉我） ====================
    def OnNear(self, args=None):
        # 找球桌放在服务端做：客户端查方块那套接口官方示例里找不到用例，靠不住。
        # 服务端算完把「该不该出按钮、是哪张桌子」发过来，这边只管显示。
        if not args:
            return
        show = bool(args.get("show"))
        pos = args.get("pos")
        dim = int(args.get("dim", 0) or 0)
        self.nearWant = (show, pos, dim)
        self._applyNear()

    def _applyNear(self):
        show, pos, dim = self.nearWant
        if show and pos:
            self.nearKey = (int(pos[0]), int(pos[1]), int(pos[2]), dim)
        else:
            self.nearKey = None
        self._syncHud()

    def _wantHud(self):
        # 服务端说附近有球桌 + 没进台球界面 = 该露出那颗按钮。
        # 「附近」是服务端在玩家真正进世界之后才算出来的，
        # 所以这里不需要再等任何加载事件 —— 等下去只会等到永远。
        show, pos, dim = self.nearWant
        return bool(show and pos and not self.inRoom)

    def _tickHud(self):
        # 界面没建出来就一直重试（跟《化身HIM》一样，每秒试一次）
        if self.hud is not None:
            return
        now = time.time()
        if now - self.hudTryT < 1.0:
            return
        self.hudTryT = now
        self._ensureHud()

    def _syncHud(self):
        # 该露脸就点亮，不该露脸就藏起来 —— 界面本身一直留着，不拆
        want = self._wantHud()
        if want:
            self._ensureHud()
        if self.hud is None:
            return
        try:
            self.hud.SetShown(want)
        except Exception:
            pass

    def _closeHud(self):
        # 走远了 / 进台球界面了：把按钮藏起来（界面留着，回来直接点亮）
        if self.hud is None:
            return
        try:
            self.hud.SetShown(False)
        except Exception:
            pass

    # ==================== 世界里的那颗按钮 ====================
    def _hudNames(self):
        return modConfig.HudUINames

    # ---------- 自检报告（临时）----------
    # 屏幕上什么都没有的时候，分不清是「界面没建出来」还是「服务端没找到球桌」。
    # 这里把这个结论直接报给服务端，让它打在聊天栏上 —— 聊天栏不依赖任何界面。
    def _tickDiag(self):
        # 只在「该露脸却没露出来」的时候报一次，平时不吭声
        if self.diagSent or not self._wantHud():
            return
        now = time.time()
        if self.diagT0 <= 0.0:
            self.diagT0 = now
            return
        if (now - self.diagT0) <= 6.0:
            return
        if self.hud is not None:
            try:
                if self.hud.IsBuilt():
                    return
            except Exception:
                return
        self._diagOnce(False)

    def _diag(self, ok):
        try:
            self.NotifyToServer(modConfig.EventDiag,
                                {"playerId": clientApi.GetLocalPlayerId(),
                                 "hud": 1 if ok else 0,
                                 "tries": self.hudTries})
        except Exception:
            pass

    def _ensureHud(self):
        if self.hud is not None:
            return
        now = time.time()
        if now < self.hudNextTry:
            return
        self.hudTries += 1
        names = self._hudNames()
        # 名字轮着用：万一某个名字在更早的版本里被引擎记成了空壳，
        # 也不会一直卡在它身上。
        name = names[(self.hudTries - 1) % len(names)]
        try:
            node = clientApi.GetUI(modConfig.ModName, name)
            if node is None:
                if name not in self.regNames:
                    # 注册成功才算数。注册失败不能把名字记成「已注册」，
                    # 否则后面再也不试了，屏幕上就永远什么都没有。
                    try:
                        clientApi.RegisterUI(modConfig.ModName, name,
                                             modConfig.HudUIPyClsPath,
                                             modConfig.HudUIScreenDef)
                        self.uiReg = True
                        self.regNames.add(name)
                    except Exception:
                        pass
                node = clientApi.CreateUI(modConfig.ModName, name, {"isHud": 1})
                if node is None:
                    node = clientApi.GetUI(modConfig.ModName, name)
            if node is None:
                self.hudNextTry = now + 1.0
                return
            # 建出来就收下。不再因为「控件还没挂全」就把它拆掉 ——
            # 拆了再建最容易转圈，屏幕上反而什么都留不下。
            self.hud = node
            self.hudName = name
            try:
                node.SetOnEnter(self._onEnter)
            except Exception:
                pass
            self.hudNextTry = 0.0
            # 建出来了就不必往聊天栏报错了
            self.diagSent = True
            self._syncHud()
        except Exception:
            self.hud = None
            self.hudNextTry = now + 1.0

    def _diagOnce(self, ok):
        if self.diagSent:
            return
        self.diagSent = True
        self._diag(ok)

    def _onEnter(self):
        now = time.time()
        if now - self.lastEnter < 0.6:
            return
        self.lastEnter = now
        key = self.nearKey
        if not key:
            return
        pid = clientApi.GetLocalPlayerId()
        try:
            self.NotifyToServer(modConfig.EventEnter,
                                {"playerId": pid,
                                 "pos": [key[0], key[1], key[2]],
                                 "dim": key[3]})
        except Exception:
            pass

    # ==================== 电脑端按键 ====================
    # 手机端：点屏幕上那颗按钮。电脑端：鼠标点 HUD 按钮不一定吃得着，
    # 所以再给一个按键 —— 靠近球桌按 R 进去，进去以后再按 R 出来。
    # 用的就是《伪上帝》里那套已经跑通的写法（设置 -> 按键 里能改键）。
    def _tickKeys(self):
        if self.keyDone or self.keyTries >= 120:
            return
        now = time.time()
        if now - self.keyTryT < 2.0:
            return
        self.keyTryT = now
        self.keyTries += 1
        self._registerKeys()

    def _registerKeys(self):
        if self.keyDone:
            return
        try:
            view = clientApi.GetEngineCompFactory().CreatePlayerView(
                clientApi.GetLevelId())
        except Exception:
            return
        if view is None:
            return
        spec = modConfig.KEY_ENTER
        try:
            if view.RegisterCustomKeyMapping(str(spec[0]), int(spec[1]),
                                             str(spec[2])):
                self.keyDone = True
        except Exception:
            pass

    def _keyDown(self, v):
        return v in (1, "1", True)

    def _keyEnter(self):
        if self.inRoom:
            self._sendExit()
            return
        self._onEnter()

    def OnCustomKey(self, args=None):
        if not args:
            return
        try:
            name = str(args.get("name", ""))
            down = self._keyDown(args.get("isDown"))
        except Exception:
            return
        if down and name == str(modConfig.KEY_ENTER[0]):
            self._keyEnter()

    def OnKeyPress(self, args=None):
        # 键位映射还没注册上的时候，普通按键这条路也认
        if not args:
            return
        try:
            key = str(args.get("key", ""))
            down = self._keyDown(args.get("isDown"))
        except Exception:
            return
        if not down or self.keyDone:
            return
        if key == str(modConfig.KEY_ENTER[1]):
            self._keyEnter()

    # ==================== 台球界面 ====================
    def _mainNames(self):
        return modConfig.MainUINames

    def _ensureMain(self):
        if self.main is not None:
            return
        now = time.time()
        if now < self.mainNextTry:
            return
        self.mainTries += 1
        names = self._mainNames()
        name = names[min(self.mainTries // 2, len(names) - 1)]
        try:
            node = clientApi.GetUI(modConfig.ModName, name)
            if node is None:
                if name not in self.regNames:
                    try:
                        clientApi.RegisterUI(modConfig.ModName, name,
                                             modConfig.MainUIPyClsPath,
                                             modConfig.MainUIScreenDef)
                        self.regNames.add(name)
                    except Exception:
                        pass
                node = clientApi.CreateUI(modConfig.ModName, name,
                                          {"isHud": 1})
                if node is None:
                    node = clientApi.GetUI(modConfig.ModName, name)
            if node is None:
                self.mainNextTry = now + 0.5
                return
            built = True
            try:
                built = bool(node.IsBuilt())
            except Exception:
                built = True
            if not built:
                self.mainBad += 1
                self.main = None
                try:
                    clientApi.DestroyUI(modConfig.ModName, name)
                except Exception:
                    pass
                self.mainNextTry = now + 0.5
                return
            self.main = node
            self.mainName = name
            self.mainPush = 20
            self.main.SetCallbacks(self._sendShoot, self._sendExit,
                                   self._sendReset, self._sendMode)
            self.main.SetOpen(True)
            self._setGameInput(False)
            if self.roomData is not None:
                self.main.ApplyRoom(self.roomData)
            self._notifyReady()
            self.mainNextTry = 0.0
        except Exception:
            self.main = None
            self.mainNextTry = now + 0.5

    def _setGameInput(self, on):
        # on=True  -> 回到游戏操作：SetInputMode(0)
        # on=False -> 进界面操作：SetInputMode(1)
        # 原来这里写反了，进界面反而切成游戏模式，界面上的按钮会点不动。
        try:
            clientApi.SetInputMode(0 if on else 1)
        except Exception:
            pass
        try:
            clientApi.HideSlotBarGui(not on)
        except Exception:
            pass

    def _closeMain(self):
        if self.main is None:
            return
        try:
            self.main.SetOpen(False)
        except Exception:
            pass
        try:
            clientApi.DestroyUI(modConfig.ModName, self.mainName)
            self.main = None
            self.mainNextTry = 0.0
        except Exception:
            pass
        self._setGameInput(True)

    def _notifyReady(self):
        try:
            self.NotifyToServer(modConfig.EventReady,
                                {"playerId": clientApi.GetLocalPlayerId()})
        except Exception:
            pass

    # ==================== 服务端来的消息 ====================
    def OnRoom(self, args=None):
        if not args:
            return
        if args.get("close"):
            self.inRoom = False
            self.roomData = None
            self._closeMain()
            self.lastExit = time.time()
            return
        self.inRoom = True
        self.roomData = args
        self.nearKey = None
        self._closeHud()
        if self.main is None:
            self.mainNextTry = 0.0
            self._ensureMain()
        if self.main is not None:
            try:
                self.main.SetOpen(True)
            except Exception:
                pass
            self._setGameInput(False)
            try:
                self.main.ApplyRoom(args)
            except Exception:
                pass

    def OnShot(self, args=None):
        if self.main is None or not args:
            return
        try:
            self.main.ApplyShot(args)
        except Exception:
            pass

    def OnTip(self, args=None):
        if not args:
            return
        if self.main is not None:
            try:
                self.main.ApplyTip(args.get("text") or u"")
            except Exception:
                pass

    # ==================== 界面点按钮 ====================
    def _sendShoot(self, dx, dy, power, sx, sy):
        try:
            self.NotifyToServer(modConfig.EventShoot,
                                {"playerId": clientApi.GetLocalPlayerId(),
                                 "dirx": dx, "diry": dy, "power": power,
                                 "sx": sx, "sy": sy})
        except Exception:
            pass

    def _sendExit(self):
        now = time.time()
        if now - self.lastExit < 0.5:
            return
        self.lastExit = now
        self.inRoom = False
        self.roomData = None
        try:
            self.NotifyToServer(modConfig.EventExit,
                                {"playerId": clientApi.GetLocalPlayerId()})
        except Exception:
            pass
        self._closeMain()

    def _sendReset(self):
        try:
            self.NotifyToServer(modConfig.EventReset,
                                {"playerId": clientApi.GetLocalPlayerId()})
        except Exception:
            pass

    def _sendMode(self, mode):
        try:
            self.NotifyToServer(modConfig.EventMode,
                                {"playerId": clientApi.GetLocalPlayerId(),
                                 "mode": mode})
        except Exception:
            pass
