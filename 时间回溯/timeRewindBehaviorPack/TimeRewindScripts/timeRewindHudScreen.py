# -*- coding: utf-8 -*-
# ============================================================
#  时间回溯 - 屏幕界面（HUD）
#    屏幕左边中间一颗「回溯」按钮：亮 / 灭由服务端说了算，
#    点一下就把消息发给服务端。
#    屏幕右边中间一颗「静止」按钮：也是服务端说了算，
#    停住的时候按钮换成“按下”的样子，一眼能看出来现在是停还是没停。
#
#    另外还有两样：
#      · 右上角一个方框，药水图标 + 图标下面的倒计时（跟原版药水效果一个样）
#      · 按下按钮时，屏幕正中弹一句提示，过两秒自己收掉
# ============================================================
import mod.client.extraClientApi as clientApi

ScreenNode = clientApi.GetScreenNodeCls()


class TimeRewindHudScreen(ScreenNode):

    def __init__(self, namespace, name, param):
        ScreenNode.__init__(self, namespace, name, param)
        self.mBtnPanel = "/hudPanel"
        self.mBtn = self.mBtnPanel + "/btnRewind"
        self.mShown = None
        self.mOnUse = None
        # ---- 静止按钮 ----
        self.mFzBtn = self.mBtnPanel + "/btnFreeze"
        self.mFzFace = self.mFzBtn + "/default"
        self.mFzTexOn = "textures/ui/timerewind/btn_freeze_p"
        self.mFzTexOff = "textures/ui/timerewind/btn_freeze"
        self.mFzShown = None
        self.mFzActive = None
        self.mOnFreeze = None
        self.mAnimPanel = "/hudPanel/rewindAnim"
        self.mAnimClock = self.mAnimPanel + "/clockBox"
        self.mAnimText = self.mAnimPanel + "/animText"
        self.mFrameCount = 8
        self.mFrame = -1
        # ---- 右上角倒计时 ----
        self.mTimerPanel = "/hudPanel/fzTimer"
        self.mTimerIcon = self.mTimerPanel + "/icon"
        self.mTimerTime = self.mTimerPanel + "/time"
        self.mTimerShown = None
        self.mTimerText = ""
        self.mTimerIconNow = ""
        # ---- 屏幕正中弹出的提示 ----
        self.mTipPanel = "/hudPanel/fzTip"
        self.mTipTitle = self.mTipPanel + "/title"
        self.mTipSub = self.mTipPanel + "/sub"
        self.mTipShown = None

    def Create(self):
        self.mShown = None
        self.mFzShown = None
        self.mFzActive = None
        self.mTimerShown = None
        self.mTimerText = ""
        self.mTimerIconNow = ""
        self.mTipShown = None
        self._wire()
        self._wireFreeze()
        self.SetButtonVisible(False)
        self.SetFreezeVisible(False)
        self.SetFreezeActive(False)
        self.ShowRewindAnim(False)
        self.SetFreezeTimerVisible(False)
        self.HideFreezeTip()

    # ==================== 正在回溯... 转钟动画 ====================
    def ShowRewindAnim(self, on, frame=0):
        # 整块动画显示 / 隐藏
        v = bool(on)
        self._setVisible(self.mAnimPanel, v)
        if v:
            self.SetAnimFrame(int(frame))
        else:
            self.mFrame = -1

    def SetAnimAlpha(self, a):
        # 开局“热身”时把它调成几乎透明：照样渲染、照样加载贴图，但看不见
        a = max(0.0, min(1.0, float(a)))
        for k in range(max(1, int(self.mFrameCount))):
            self._setAlpha(self.mAnimClock + "/f%d" % k, a)
        self._setAlpha(self.mAnimText, a)

    def SetAnimFrame(self, i):
        # 只让当前这一帧的图显示出来
        n = max(1, int(self.mFrameCount))
        i = int(i) % n
        if i == self.mFrame:
            return
        self.mFrame = i
        for k in range(n):
            self._setVisible(self.mAnimClock + "/f%d" % k, k == i)

    # ==================== 按钮 ====================
    def SetOnUse(self, callback):
        # 客户端把“玩家点了这个按钮要干什么”交进来
        self.mOnUse = callback

    def SetButtonVisible(self, show):
        v = bool(show)
        self.mShown = v
        self._setVisible(self.mBtn, v)
        try:
            self.GetBaseUIControl(self.mBtn).asButton().SetButtonEnable(v)
        except Exception:
            pass

    def _wire(self):
        try:
            btn = self.GetBaseUIControl(self.mBtn).asButton()
            btn.AddTouchEventParams({"isSwallow": True})
            btn.SetButtonTouchUpCallback(self._onTouch)
        except Exception:
            pass

    def _onTouch(self, args=None):
        if self.mOnUse is None:
            return
        try:
            self.mOnUse(args)
        except Exception:
            pass

    # ==================== 静止按钮 ====================
    def SetOnFreeze(self, callback):
        self.mOnFreeze = callback

    def SetFreezeVisible(self, show):
        v = bool(show)
        self.mFzShown = v
        self._setVisible(self.mFzBtn, v)
        try:
            self.GetBaseUIControl(self.mFzBtn).asButton().SetButtonEnable(v)
        except Exception:
            pass

    def SetFreezeActive(self, on):
        # 停住的时候换成“按下”的那张贴图，一眼能看出开关状态
        v = bool(on)
        if v == self.mFzActive:
            return
        self.mFzActive = v
        self._setFace(self.mFzTexOn if v else self.mFzTexOff)

    def _setFace(self, texturePath):
        try:
            ctrl = self.GetBaseUIControl(self.mFzFace)
            if ctrl is not None:
                ctrl.asImage().SetSprite(str(texturePath))
                return
        except Exception:
            pass
        # 拿不到子控件就退而求其次：整个按钮换贴图
        try:
            self.GetBaseUIControl(self.mFzBtn).asImage().SetSprite(str(texturePath))
        except Exception:
            pass

    def _wireFreeze(self):
        try:
            btn = self.GetBaseUIControl(self.mFzBtn).asButton()
            btn.AddTouchEventParams({"isSwallow": True})
            btn.SetButtonTouchUpCallback(self._onFreezeTouch)
        except Exception:
            pass

    def _onFreezeTouch(self, args=None):
        if self.mOnFreeze is None:
            return
        try:
            self.mOnFreeze(args)
        except Exception:
            pass

    # ==================== 右上角：药水倒计时 ====================
    def SetFreezeIcon(self, texturePath):
        # 图标想换成别的贴图时用（默认就是静止药水那颗）
        path = str(texturePath or "")
        if not path or path == self.mTimerIconNow:
            return
        self.mTimerIconNow = path
        try:
            ctrl = self.GetBaseUIControl(self.mTimerIcon)
            if ctrl is not None:
                ctrl.asImage().SetSprite(path)
        except Exception:
            pass

    def SetFreezeTimerVisible(self, show):
        v = bool(show)
        if v == self.mTimerShown:
            return
        self.mTimerShown = v
        self._setVisible(self.mTimerPanel, v)

    def SetFreezeTimer(self, seconds):
        # 秒数 -> "分:秒"（超过一小时就只显示分钟，药水最多几分钟，够用）
        try:
            left = int(float(seconds))
        except Exception:
            left = 0
        if left < 0:
            left = 0
        text = "%d:%02d" % (left // 60, left % 60)
        if text == self.mTimerText:
            return
        self.mTimerText = text
        try:
            ctrl = self.GetBaseUIControl(self.mTimerTime)
            if ctrl is not None:
                ctrl.asLabel().SetText(text)
        except Exception:
            pass

    # ==================== 屏幕正中弹的提示 ====================
    def ShowFreezeTip(self, title, subText):
        tip = u"%s" % (title or u"")
        sub = u"%s" % (subText or u"")
        try:
            ctrl = self.GetBaseUIControl(self.mTipTitle)
            if ctrl is not None:
                ctrl.asLabel().SetText(tip)
            ctrl = self.GetBaseUIControl(self.mTipSub)
            if ctrl is not None:
                ctrl.asLabel().SetText(sub)
        except Exception:
            pass
        if True != self.mTipShown:
            self.mTipShown = True
            self._setVisible(self.mTipPanel, True)

    def HideFreezeTip(self):
        if False == self.mTipShown:
            return
        self.mTipShown = False
        self._setVisible(self.mTipPanel, False)

    # ==================== 底层小工具 ====================
    def _setAlpha(self, path, a):
        try:
            ctrl = self.GetBaseUIControl(path)
            if ctrl is not None:
                ctrl.SetAlpha(float(a))
                return
        except Exception:
            pass
        try:
            self.SetAlpha(path, float(a))
        except Exception:
            pass

    def _setVisible(self, path, visible):
        try:
            ctrl = self.GetBaseUIControl(path)
            if ctrl is not None:
                ctrl.SetVisible(bool(visible))
                return
        except Exception:
            pass
        try:
            self.SetVisible(path, bool(visible))
        except Exception:
            pass
