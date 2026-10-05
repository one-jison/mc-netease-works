# -*- coding: utf-8 -*-
# 锁血是纯服务端逻辑，客户端挂个空系统占位就行。
import mod.client.extraClientApi as clientApi

ClientSystem = clientApi.GetClientSystemCls()


class LockHpClientSystem(ClientSystem):

    def __init__(self, namespace, systemName):
        ClientSystem.__init__(self, namespace, systemName)
