# -*- coding: utf-8 -*-
# ============================================================
#  时间回溯 — 公共配置（模组名 / 事件名 / 界面名）
# ============================================================
ModName = "TimeRewindMod"
ModVersion = "1.0.19"

ServerSystemName = "TimeRewindServerSystem"
ClientSystemName = "TimeRewindClientSystem"
ServerSystemClsPath = "TimeRewindScripts.timeRewindServerSystem.TimeRewindServerSystem"
ClientSystemClsPath = "TimeRewindScripts.timeRewindClientSystem.TimeRewindClientSystem"

# 服务端 -> 这个玩家自己：左侧那颗「回溯」按钮要不要亮着
EventState = "TimeRewindState"
# 客户端 -> 服务端：玩家按下了回溯按钮
EventUse = "TimeRewindUse"
# 客户端 -> 服务端：客户端自己放不出按键音效，让服务端用 /playsound 兜底
EventSound = "TimeRewindSound"
# 服务端 -> 所有玩家：回溯时的一圈淡蓝色冲击波
EventWave = "TimeRewindWave"

# 服务端 -> 这个玩家自己：右侧那颗「静止」按钮要不要亮着 / 现在是停还是没停
EventFreezeState = "TimeRewindFreezeState"
# 客户端 -> 服务端：玩家按下了静止按钮（或者电脑端按了那个键）
EventFreezeUse = "TimeRewindFreezeUse"

UiInitFinishedEvent = "UiInitFinished"
HudUIName = "timerewindhud"
HudUIPyClsPath = "TimeRewindScripts.timeRewindHudScreen.TimeRewindHudScreen"
HudUIScreenDef = "timerewindhud.main"
