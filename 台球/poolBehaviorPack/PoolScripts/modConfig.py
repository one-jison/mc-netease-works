# -*- coding: utf-8 -*-
# ============================================================
#  台球 — 公共配置（模组名 / 系统名 / 界面名 / 事件名）
#  客户端和服务端都读这一份，改名字只改这里
# ============================================================
ModName = "PoolMod"
ModVersion = "1.0.0"

ServerSystemName = "PoolServerSystem"
ClientSystemName = "PoolClientSystem"
ServerSystemClsPath = "PoolScripts.poolServer.serverSystem.PoolServerSystem"
ClientSystemClsPath = "PoolScripts.poolClient.clientSystem.PoolClientSystem"

# 台球桌方块
PoolBlock = "pool:pool_table"
# 玩家离球桌多近才出「进入台球」按钮（格）
NearRange = 2.0

# ---------------- 客户端 -> 服务端 ----------------
# 点了「进入台球」：{"playerId":..., "pos":(x,y,z), "dim":d}
EventEnter = "PoolEnter"
# 点了「离开球桌」/ 关掉界面：{"playerId":...}
EventExit = "PoolExit"
# 开球：{"playerId":..., "dirx":.., "diry":.., "power":.., "sx":.., "sy":..}
EventShoot = "PoolShoot"
# 单人进入时选模式：{"playerId":..., "mode":"solo"/"ai"}
EventMode = "PoolMode"
# 摆球重开一局：{"playerId":...}
EventReset = "PoolReset"
# 客户端说「我这边界面建好了」：{"playerId":...}
EventReady = "PoolReady"

# ---------------- 服务端 -> 客户端 ----------------
# 房间状态（开不开界面、轮到谁、比分）
EventRoom = "PoolRoom"
# 别人开球了：{"pos":(x,y,z), "seat":.., "seatId":.., "dirx":.., "diry":..,
#              "power":.., "sx":.., "sy":.., "cueFrom":(x,y)}
EventShot = "PoolShot"
# 一条提示：{"text":...}
EventTip = "PoolTip"
# 附近有没有球桌：{"show":0/1, "pos":[x,y,z], "dim":d}
EventNear = "PoolNear"
# 自检报告：客户端告诉服务端「屏幕按钮到底建出来没有」
EventDiag = "PoolDiag"

UiInitFinishedEvent = "UiInitFinished"

# ---------------- 电脑端按键 ----------------
# 手机端点屏幕上那颗按钮；电脑端鼠标点 HUD 按钮不一定吃得着，
# 所以再给一个按键：靠近球桌按一下进去，进去以后再按一下出来。
# 写法照搬《伪上帝》已经跑通的那套（设置 -> 按键里可以改键）。
KEY_ENTER = ("pool_enter", 82, "movement")   # R  进入 / 离开台球
# 世界里那颗「进入台球」按钮
# 引擎偶尔会把「界面定义还没加载好」这一下缓存成一个空壳，同一个名字再建也还是空的，
# 所以准备了几个备用名字，轮着来；每次都先把上一次的拆掉，逼它重新建。
HudUINames = ("poolhud", "poolhud_b", "poolhud_c", "poolhud_d",
              "poolhud_e", "poolhud_f", "poolhud_g", "poolhud_h")
HudUIName = HudUINames[0]
HudUIPyClsPath = "PoolScripts.poolClient.ui.poolHudScreen.PoolHudScreen"
HudUIScreenDef = "poolhud.main"
# 台球界面（平面球桌 + 球）
MainUINames = ("poolmain", "poolmain_b", "poolmain_c", "poolmain_d")
MainUIName = MainUINames[0]
MainUIPyClsPath = "PoolScripts.poolClient.ui.poolScreen.PoolScreen"
MainUIScreenDef = "poolmain.main"
