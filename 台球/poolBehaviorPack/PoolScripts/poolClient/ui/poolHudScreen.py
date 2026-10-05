# -*- coding: utf-8 -*-
# ============================================================
#  台球 — 世界里那颗「进入台球」按钮
#  走到球桌两格以内才露脸，走远了自动收回去。
#  「附不附近」由服务端算好发消息过来，这边只管显示。
#
#  ★ 这一版是把《化身HIM》里已经跑通的那套照搬过来的：
#    • 外面套一层 panel，靠它的 visible 决定露不露脸；
#    • 位置、大小全写在界面文件里（底边锚定，永远贴着物品栏上面）；
#    • 接线也照搬：AddTouchEventParams + SetButtonTouchUpCallback。
#  之前几次一直不出来，不是这里的问题，是外面拿一个从来不会到的事件
#  当“可以开始建界面了吗”的闸门，结果界面从头到尾没被建过。
# ============================================================
import time

import mod.client.extraClientApi as clientApi

ScreenNode = clientApi.GetScreenNodeCls()

PANEL = "/entryPanel"
BTN = "/entryPanel/entryBtn"


class PoolHudScreen(ScreenNode):

    def __init__(self, namespace, name, param):
        ScreenNode.__init__(self, namespace, name, param)
        self.mPanel = PANEL
        self.mBtn = BTN
        self.mOnEnter = None
        self.mShown = None
        self.mWired = False
        self.mLastTouch = 0.0

    # ==================== 生命周期 ====================
    def Create(self):
        self.mWired = False
        self.mShown = None
        self._wire()
        self.SetShown(False)

    def Update(self):
        # 界面骨架有时是稍后才挂全的，这一帧补一次接线
        self._wire()

    def IsBuilt(self):
        # 界面骨架真的挂上了吗（给外面自检用）
        try:
            return self.GetBaseUIControl(self.mPanel) is not None
        except Exception:
            return False

    # ==================== 按钮接线 ====================
    def _wire(self):
        if self.mWired:
            return
        try:
            ctrl = self.GetBaseUIControl(self.mBtn)
        except Exception:
            ctrl = None
        if ctrl is None:
            return
        self.mWired = True
        try:
            btn = ctrl.asButton()
            btn.AddTouchEventParams({"isSwallow": True})
            btn.SetButtonTouchUpCallback(self._onTouch)
        except Exception:
            self.mWired = False

    def SetOnEnter(self, cb):
        self.mOnEnter = cb

    def _onTouch(self, args=None):
        if self.mOnEnter is None:
            return
        # 同一个回调可能被连着叫几次，这里自己挡一下重复
        now = time.time()
        if now - self.mLastTouch < 0.6:
            return
        self.mLastTouch = now
        try:
            self.mOnEnter()
        except Exception:
            pass

    # ==================== 露脸 / 收回 ====================
    def SetShown(self, on):
        v = bool(on)
        if self.mShown == v:
            return
        self.mShown = v
        try:
            ctrl = self.GetBaseUIControl(self.mPanel)
            if ctrl is not None:
                ctrl.SetVisible(v)
        except Exception:
            pass
