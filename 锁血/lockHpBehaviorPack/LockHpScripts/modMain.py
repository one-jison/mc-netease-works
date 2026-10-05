# -*- coding: utf-8 -*-
from mod.common.mod import Mod
import mod.server.extraServerApi as serverApi
import mod.client.extraClientApi as clientApi

from LockHpScripts import modConfig


@Mod.Binding(name=modConfig.ModName, version=modConfig.ModVersion)
class LockHpMod(object):

    def __init__(self):
        pass

    @Mod.InitServer()
    def LockHpServerInit(self):
        serverApi.RegisterSystem(modConfig.ModName,
                                 modConfig.ServerSystemName,
                                 modConfig.ServerSystemClsPath)

    @Mod.DestroyServer()
    def LockHpServerDestroy(self):
        pass

    @Mod.InitClient()
    def LockHpClientInit(self):
        clientApi.RegisterSystem(modConfig.ModName,
                                 modConfig.ClientSystemName,
                                 modConfig.ClientSystemClsPath)

    @Mod.DestroyClient()
    def LockHpClientDestroy(self):
        pass
