# -*- coding: utf-8 -*-
from mod.common.mod import Mod
import mod.server.extraServerApi as serverApi
from EggTartScripts import modConfig


@Mod.Binding(name=modConfig.ModName, version=modConfig.ModVersion)
class EggTartMod(object):

    def __init__(self):
        pass

    @Mod.InitServer()
    def EggTartServerInit(self):
        serverApi.RegisterSystem(modConfig.ModName,
                                 modConfig.ServerSystemName,
                                 modConfig.ServerSystemClsPath)

    @Mod.DestroyServer()
    def EggTartServerDestroy(self):
        pass
