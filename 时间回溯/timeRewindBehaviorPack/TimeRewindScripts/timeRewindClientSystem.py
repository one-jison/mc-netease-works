# -*- coding: utf-8 -*-
# ============================================================
#  时间回溯 — 客户端
#    · 服务端说“按钮亮起来”就亮，说“收掉”就收
#    · 左边那颗是「回溯」，右边那颗是「静止」（可以反复开关）
#    · 玩家点一下按钮：告诉服务端，由服务端去做回溯
#    · 电脑端：注册一个自定义按键（默认 R），
#      这个键会出现在游戏的【设置 -> 按键】里，玩家可以自己改
# ============================================================
import time
import mod.client.extraClientApi as clientApi
from TimeRewindScripts import modConfig
from TimeRewindScripts import timeRewindConfig as cfg


ClientSystem = clientApi.GetClientSystemCls()


class TimeRewindClientSystem(ClientSystem):

    def __init__(self, namespace, systemName):
        super(TimeRewindClientSystem, self).__init__(namespace, systemName)
        self._hudNode = None
        self._hudTries = 0
        self._hudTryTime = 0.0
        self._show = False       # 屏幕左边那颗「回溯」要不要亮着
        self._keyDown = False    # 快捷键还按着吗（一直按着不重复触发）
        self._keysDone = False   # 自定义按键注册上了没有
        self._keyTries = 0
        self._keyTryTime = 0.0
        # ---- 静止按钮 ----
        self._fzShow = False     # 右边那颗「静止」要不要亮着
        self._fzOn = False       # 现在是停还是没停
        self._fzKeyDown = False
        self._fzKeysDone = False
        self._fzKeyTries = 0
        self._fzKeyTryTime = 0.0
        self._lastFzSend = 0.0
        self._lastSend = 0.0
        # ---- 右上角那个倒计时 ----
        # 服务端只说一次“还剩几秒”，之后本地自己一秒一秒往下走，
        # 这样不用服务端每帧发消息，数字也不会卡住（跟原版药水一个道理）
        self._fzLeft = 0.0        # 服务端刚说的剩余秒数
        self._fzLeftAt = 0.0      # 上面那个数字是什么时候收到的
        self._fzTimerShown = False
        self._fzTimerSec = -1
        # ---- 屏幕正中弹出的提示 ----
        self._tipUntil = 0.0      # 提示到几点收掉（0 = 现在没提示）
        self._spinStart = 0.0    # 转钟动画从什么时候开始
        self._spinEnd = 0.0      # 到什么时候结束（0 = 现在没在放）
        self._warm = False       # 这一轮是不是开局的“热身”
        self._warmed = False     # 开局热过身了没有
        self._listenEvents()

    # ==================== 事件监听 ====================
    def _listenEvents(self):
        ns = clientApi.GetEngineNamespace()
        sn = clientApi.GetEngineSystemName()
        L = self.ListenForEvent
        L(ns, sn, "OnScriptTickClient", self, self.OnScriptTick)
        L(ns, sn, "OnLocalPlayerStopLoading", self, self.OnStopLoading)
        L(ns, sn, modConfig.UiInitFinishedEvent, self, self.OnUIInitFinished)
        # 电脑端：注册过的自定义按键，按下 / 松开都走这个事件
        L(ns, sn, "OnCustomKeyPressInGame", self, self.OnCustomKey)
        # 兜底：万一自定义按键没注册上，普通按键事件里也认一下同一个键码
        L(ns, sn, "OnKeyPressInGame", self, self.OnKeyPress)
        L(modConfig.ModName, modConfig.ServerSystemName,
          modConfig.EventState, self, self.OnState)
        L(modConfig.ModName, modConfig.ServerSystemName,
          modConfig.EventFreezeState, self, self.OnFreezeState)

    def OnStopLoading(self, args=None):
        self._hudNode = None
        self._hudTries = 0
        self._keysDone = False
        self._keyTries = 0
        self._fzKeysDone = False
        self._fzKeyTries = 0
        self._fzShow = False
        self._fzOn = False
        self._fzLeft = 0.0
        self._fzLeftAt = 0.0
        self._fzTimerShown = False
        self._fzTimerSec = -1
        self._tipUntil = 0.0
        self._warmed = False
        self._spinEnd = 0.0
        self._ensureHud()
        self._registerKeys()

    def OnUIInitFinished(self, args=None):
        self._ensureHud()
        self._registerKeys()

    # ==================== 每帧 ====================
    def OnScriptTick(self, args=None):
        now = time.time()
        if not self._keysDone and self._keyTries < 60:
            if now - self._keyTryTime >= 2.0:
                self._keyTryTime = now
                self._registerKeys()
        if not self._fzKeysDone and self._fzKeyTries < 60:
            if now - self._fzKeyTryTime >= 2.0:
                self._fzKeyTryTime = now
                self._registerFreezeKey()
        if self._hudNode is None:
            if now - self._hudTryTime >= 3.0:
                self._hudTryTime = now
                self._ensureHud()
            return
        if now - self._hudTryTime >= 1.0:
            self._hudTryTime = now
            self._apply()
        self._tickFreezeTimer(now)
        if not self._warmed and cfg.animWarmUp() and cfg.animSeconds() > 0.0:
            # 开局先悄悄放一遍转钟：贴图和文字提前加载好，第一次真放就不卡了
            self._warmed = True
            self._startSpin(now, cfg.animSeconds(), warm=True)
        self._tickSpin(now)

    # ==================== 右上角：静止药水倒计时 ====================
    def _fzLeftNow(self):
        # 还剩几秒：服务端给的数往前推
        if not self._fzShow:
            return 0.0
        if self._fzLeftAt <= 0.0:
            return 0.0
        return max(0.0, self._fzLeft - (time.time() - self._fzLeftAt))

    @staticmethod
    def _mmss(sec):
        s = int(float(sec) + 0.999)
        if s < 0:
            s = 0
        return u"%d:%02d" % (s // 60, s % 60)

    def _tickFreezeTimer(self, now):
        node = self._hudNode
        if node is None:
            return
        # 提示到点了就收掉
        if self._tipUntil > 0.0 and now >= self._tipUntil:
            self._tipUntil = 0.0
            try:
                node.HideFreezeTip()
            except Exception:
                pass
        if not cfg.freezeTimerOn():
            return
        left = self._fzLeftNow()
        show = bool(self._fzShow) and left > 0.0
        if show != self._fzTimerShown:
            self._fzTimerShown = show
            if show:
                try:
                    node.SetFreezeIcon(cfg.freezeTimerIcon())
                except Exception:
                    pass
            try:
                node.SetFreezeTimerVisible(show)
            except Exception:
                pass
            if not show:
                self._fzTimerSec = -1
        if not show:
            return
        sec = int(left + 0.999)
        if sec != self._fzTimerSec:
            self._fzTimerSec = sec
            try:
                node.SetFreezeTimer(sec)
            except Exception:
                pass

    # ==================== 按下按钮时弹出的提示 ====================
    def _popFreezeTip(self, on):
        node = self._hudNode
        if node is None or not cfg.freezePopupOn():
            return
        if on:
            title = getattr(cfg, "FREEZE_POPUP_ON_TITLE", u"静止 · 开启")
            sub = getattr(cfg, "FREEZE_POPUP_ON_SUB", u"")
        else:
            title = getattr(cfg, "FREEZE_POPUP_OFF_TITLE", u"静止 · 解除")
            sub = getattr(cfg, "FREEZE_POPUP_OFF_SUB", u"")
        left = self._fzLeftNow()
        if on and left > 0.0:
            sub = u"%s（药效剩余 %s）" % (sub, self._mmss(left))
        try:
            node.ShowFreezeTip(title, sub)
            self._tipUntil = time.time() + cfg.freezePopupSeconds()
        except Exception:
            pass

    # ==================== 正在回溯... 转钟动画 ====================
    def _startSpin(self, now, seconds, warm=False):
        self._spinStart = now
        self._spinEnd = now + max(0.1, float(seconds))
        self._warm = bool(warm)
        # 热身的这一轮几乎透明，肉眼看不见，但贴图已经被引擎加载过了
        self._animAlpha(0.02 if self._warm else 1.0)
        self._animShow(0)

    def _stopSpin(self):
        self._spinEnd = 0.0
        self._spinStart = 0.0
        node = self._hudNode
        if node is not None:
            try:
                node.ShowRewindAnim(False)
            except Exception:
                pass
        if self._warm:
            self._warm = False
            self._animAlpha(1.0)

    def _tickSpin(self, now):
        if self._spinEnd <= 0.0:
            return
        if now >= self._spinEnd:
            self._stopSpin()
            return
        frames = max(1, int(getattr(cfg, "ANIM_FRAMES", 8)))
        fps = max(1.0, float(getattr(cfg, "ANIM_FPS", 8.0)))
        self._animShow(int((now - self._spinStart) * fps) % frames)

    def _animShow(self, frame):
        node = self._hudNode
        if node is None:
            return
        try:
            node.ShowRewindAnim(True, int(frame))
        except Exception:
            pass

    def _animAlpha(self, a):
        node = self._hudNode
        if node is None:
            return
        try:
            node.SetAnimAlpha(float(a))
        except Exception:
            pass

    # ==================== 按下按钮那一声 ====================
    def _playButtonSound(self):
        # 音效在资源包 sounds/timerewind/rewind.ogg，
        # 按下的一瞬间就在本地放，不用等服务端，听着更跟手
        if not cfg.buttonSoundOn():
            return
        name = str(cfg.buttonSound())
        if not name:
            return
        vol = float(getattr(cfg, "BUTTON_SOUND_VOLUME", 1.0))
        pit = float(getattr(cfg, "BUTTON_SOUND_PITCH", 1.0))
        pos = self._myPos()
        pid = clientApi.GetLocalPlayerId()
        for owner in (pid, clientApi.GetLevelId()):
            comp = self._audioComp(owner)
            if comp is None:
                continue
            if self._callPlay(comp, name, pos, vol, pit,
                              pid if owner == pid else None):
                return
        # 本地放不出来（少数机型会这样），让服务端用 /playsound 兜底
        try:
            self.NotifyToServer(modConfig.EventSound, {"playerId": pid})
        except Exception:
            pass

    def _audioComp(self, owner):
        try:
            return clientApi.GetEngineCompFactory().CreateCustomAudio(owner)
        except Exception:
            return None

    def _callPlay(self, comp, name, pos, vol, pit, localId=None):
        func = getattr(comp, "PlayCustomMusic", None)
        if func is not None:
            calls = [(name, pos, vol, pit)]
            if localId:
                calls.append((name, pos, vol, pit, False, localId))
            for a in calls:
                try:
                    ret = func(*a)
                except Exception:
                    continue
                if ret is None or bool(ret):
                    return True
        func = getattr(comp, "PlayCustomSound", None)
        if func is not None:
            for a in ((name, pos, vol, pit), (name, pos, vol, pit, False)):
                try:
                    ret = func(*a)
                except Exception:
                    continue
                if ret is None or bool(ret):
                    return True
        return False

    def _myPos(self):
        try:
            return clientApi.GetEngineCompFactory().CreatePos(
                clientApi.GetLocalPlayerId()).GetFootPos()
        except Exception:
            return (0.0, 0.0, 0.0)

    # ==================== 电脑端：自定义按键 ====================
    def _registerKeys(self):
        # 把「回溯」注册成游戏里的一个按键，玩家能在设置里改键
        if not cfg.useKeyOn() or self._keysDone:
            return
        self._keyTries += 1
        comp = self._playerViewComp()
        if comp is None:
            return
        try:
            ok = comp.RegisterCustomKeyMapping(
                str(cfg.USE_KEY_NAME), int(cfg.USE_KEY_CODE),
                str(getattr(cfg, "USE_KEY_CATEGORY", "gameplay")))
        except Exception:
            ok = False
        if ok:
            self._keysDone = True

    def _registerFreezeKey(self):
        # 把「静止」也注册成一个按键（默认 G）
        if not cfg.freezeKeyOn() or self._fzKeysDone:
            return
        self._fzKeyTries += 1
        comp = self._playerViewComp()
        if comp is None:
            return
        try:
            ok = comp.RegisterCustomKeyMapping(
                str(getattr(cfg, "FREEZE_KEY_NAME", "TimeRewindFreeze")),
                int(getattr(cfg, "FREEZE_KEY_CODE", 71)),
                str(getattr(cfg, "USE_KEY_CATEGORY", "gameplay")))
        except Exception:
            ok = False
        if ok:
            self._fzKeysDone = True

    def _playerViewComp(self):
        try:
            return clientApi.GetEngineCompFactory().CreatePlayerView(
                clientApi.GetLevelId())
        except Exception:
            return None

    def OnCustomKey(self, args=None):
        # 注册过的那个按键：按下 / 松开都来这儿
        try:
            name = str(args.get("name", ""))
            isDown = str(args.get("isDown", "0")) == "1"
        except Exception:
            return
        if name == str(cfg.USE_KEY_NAME):
            self._onKeyState(isDown)
            return
        if name == str(getattr(cfg, "FREEZE_KEY_NAME", "TimeRewindFreeze")):
            self._onFreezeKeyState(isDown)

    def OnKeyPress(self, args=None):
        # 兜底：万一自定义按键没注册成功，按同一个键码也认
        if not args:
            return
        try:
            key = str(args.get("key", ""))
            isDown = str(args.get("isDown", "0")) == "1"
        except Exception:
            return
        if (not self._keysDone) and cfg.useKeyOn() \
                and key == str(cfg.USE_KEY_CODE):
            self._onKeyState(isDown)
            return
        if (not self._fzKeysDone) and cfg.freezeKeyOn() \
                and key == str(getattr(cfg, "FREEZE_KEY_CODE", 71)):
            self._onFreezeKeyState(isDown)

    def _onKeyState(self, isDown):
        if not isDown:
            self._keyDown = False
            return
        if self._keyDown:
            return              # 一直按着不重复触发
        self._keyDown = True
        self.OnButton()

    def _onFreezeKeyState(self, isDown):
        if not isDown:
            self._fzKeyDown = False
            return
        if self._fzKeyDown:
            return
        self._fzKeyDown = True
        self.OnFreezeButton()

    def OnFreezeButton(self, args=None):
        # 玩家点了右边那颗「静止」（或者按了 G）
        now = time.time()
        if now - self._lastFzSend < 0.2:
            return
        self._lastFzSend = now
        if self._fzShow:
            # 先自己翻一下，按钮立刻变色，手感更跟手；
            # 服务端随后会发准确的开关状态回来
            self._fzOn = not self._fzOn
            self._apply()
            # 顺手在屏幕正中弹一句：开 / 关 + 药效还剩多久
            self._popFreezeTip(self._fzOn)
        try:
            self.NotifyToServer(modConfig.EventFreezeUse,
                                {"playerId": clientApi.GetLocalPlayerId()})
        except Exception:
            pass

    def OnFreezeState(self, args=None):
        show = 0
        on = 0
        if args:
            try:
                show = int(args.get("show", 0))
                on = int(args.get("on", 0))
            except Exception:
                show = 0
                on = 0
        self._fzShow = bool(show)
        self._fzOn = bool(show) and bool(on)
        if args:
            try:
                left = float(args.get("left"))
            except Exception:
                left = None
            if left is not None:
                self._fzLeft = max(0.0, left)
                self._fzLeftAt = time.time()
        if not self._fzShow:
            # 药效没了：倒计时和提示一起收掉
            self._fzLeft = 0.0
            self._fzLeftAt = 0.0
            node = self._hudNode
            if node is not None:
                if self._fzTimerShown:
                    self._fzTimerShown = False
                    self._fzTimerSec = -1
                    try:
                        node.SetFreezeTimerVisible(False)
                    except Exception:
                        pass
                if self._tipUntil > 0.0:
                    self._tipUntil = 0.0
                    try:
                        node.HideFreezeTip()
                    except Exception:
                        pass
        self._apply()

    # ==================== 屏幕上的「回溯」按钮 ====================
    def OnState(self, args=None):
        show = 0
        if args:
            try:
                show = int(args.get("show", 0))
            except Exception:
                show = 0
        self._show = bool(show)
        # 注意：这里不能顺手把转钟动画停掉。
        # 按一下按钮药水就消耗了，服务端马上会发 show=0，
        # 要是停掉动画，那一秒的「正在回溯...」就看不见了；
        # 动画自己会在一秒后收掉。
        self._apply()

    def _apply(self):
        node = self._hudNode
        if node is None:
            return
        try:
            node.SetButtonVisible(bool(self._show))
        except Exception:
            pass
        try:
            node.SetFreezeVisible(bool(self._fzShow))
            node.SetFreezeActive(bool(self._fzOn))
        except Exception:
            pass

    def OnButton(self, args=None):
        # 玩家点了按钮（或者按了快捷键）
        now = time.time()
        if now - self._lastSend < 0.25:
            return
        self._lastSend = now
        if self._show:
            # 按钮亮着才放动画 / 音效：没药水时按下去一点反应都不给
            self._startSpin(now, cfg.animSeconds(), warm=False)
            self._playButtonSound()
        try:
            self.NotifyToServer(modConfig.EventUse,
                                {"playerId": clientApi.GetLocalPlayerId()})
        except Exception:
            pass

    # ==================== 界面 ====================
    def _ensureHud(self):
        if self._hudNode is not None or self._hudTries >= 40:
            return
        self._hudTries += 1
        try:
            node = clientApi.GetUI(modConfig.ModName, modConfig.HudUIName)
            if node is None:
                clientApi.RegisterUI(modConfig.ModName, modConfig.HudUIName,
                                     modConfig.HudUIPyClsPath, modConfig.HudUIScreenDef)
                node = clientApi.CreateUI(modConfig.ModName, modConfig.HudUIName,
                                          {"isHud": 1})
                if node is None:
                    node = clientApi.GetUI(modConfig.ModName, modConfig.HudUIName)
            self._hudNode = node
            try:
                node.SetOnUse(self.OnButton)
            except Exception:
                pass
            try:
                node.SetOnFreeze(self.OnFreezeButton)
            except Exception:
                pass
            self._apply()
        except Exception:
            self._hudNode = None
