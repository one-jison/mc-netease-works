# -*- coding: utf-8 -*-
# ============================================================
#  台球 — 模组入口
# ============================================================
from mod.common.mod import Mod
import mod.server.extraServerApi as serverApi
import mod.client.extraClientApi as clientApi
from PoolScripts import modConfig


@Mod.Binding(name=modConfig.ModName, version=modConfig.ModVersion)
class PoolMod(object):

    def __init__(self):
        pass

    @Mod.InitServer()
    def PoolServerInit(self):
        serverApi.RegisterSystem(modConfig.ModName, modConfig.ServerSystemName,
                                 modConfig.ServerSystemClsPath)

    @Mod.DestroyServer()
    def PoolServerDestroy(self):
        pass

    @Mod.InitClient()
    def PoolClientInit(self):
        clientApi.RegisterSystem(modConfig.ModName, modConfig.ClientSystemName,
                                 modConfig.ClientSystemClsPath)

    @Mod.DestroyClient()
    def PoolClientDestroy(self):
        pass
