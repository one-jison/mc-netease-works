# -*- coding: utf-8 -*-
# ============================================================
#  时间回溯 - 模组入口
#    喝下一瓶「回溯」：
#      · 屏幕左侧出现一颗回溯按钮
#      · 按下按钮：昼夜飞快交替，身边一百格内的实体和方块退回十秒前的样子
# ============================================================
from mod.common.mod import Mod
import mod.server.extraServerApi as serverApi
import mod.client.extraClientApi as clientApi

from TimeRewindScripts import modConfig

MOD_NAME = modConfig.ModName
MOD_VERSION = modConfig.ModVersion


@Mod.Binding(name=MOD_NAME, version=MOD_VERSION)
class TimeRewindMod(object):

    def __init__(self):
        pass

    @Mod.InitServer()
    def InitServer(self):
        serverApi.RegisterSystem(MOD_NAME, modConfig.ServerSystemName,
                                 modConfig.ServerSystemClsPath)

    @Mod.DestroyServer()
    def DestroyServer(self):
        pass

    @Mod.InitClient()
    def InitClient(self):
        clientApi.RegisterSystem(MOD_NAME, modConfig.ClientSystemName,
                                 modConfig.ClientSystemClsPath)

    @Mod.DestroyClient()
    def DestroyClient(self):
        pass
