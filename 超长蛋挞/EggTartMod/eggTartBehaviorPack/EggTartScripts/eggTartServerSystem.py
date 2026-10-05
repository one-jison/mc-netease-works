# -*- coding: utf-8 -*-
# ============================================================
#  超长蛋挞
#  1. 玩家把「超长蛋挞包装盒」放在地上
#  2. 撸掉包装盒 -> 原地变成「超长蛋挞」
#  3. 撸掉蛋挞   -> 掉落能吃的「超长蛋挞(食用)」
# ============================================================
import mod.server.extraServerApi as serverApi
from mod_log import logger
from EggTartScripts import modConfig

compFactory = serverApi.GetEngineCompFactory()


class EggTartServerSystem(serverApi.GetServerSystemCls()):

    def __init__(self, namespace, name):
        super(EggTartServerSystem, self).__init__(namespace, name)
        self.mLevelId = serverApi.GetLevelId()
        self.ListenEvent()

    def ListenEvent(self):
        self.ListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(),
                            'DestroyBlockEvent', self, self.OnDestroyBlock)

    def UnListenEvent(self):
        self.UnListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(),
                              'DestroyBlockEvent', self, self.OnDestroyBlock)

    def OnDestroyBlock(self, args):
        # 只有包装盒被破坏时才处理
        if args.get('fullName') != modConfig.BoxBlock:
            return
        try:
            pos = (args['x'], args['y'], args['z'])
            dimensionId = args.get('dimensionId', 0)
            # 包装盒本身不掉落任何物品
            for entityId in (args.get('dropEntityIds') or []):
                if self.DestroyEntity(entityId):
                    pass
            # 原地变成蛋挞
            blockInfoComp = compFactory.CreateBlockInfo(dimensionId)
            blockInfoComp.SetBlockNew(pos, {'name': modConfig.TartBlock, 'aux': 0}, 0, dimensionId)
            logger.info('[EggTart] 包装盒 %s 已变成蛋挞', pos)
        except Exception as e:
            logger.error('[EggTart] 包装盒变成蛋挞失败: %s', e)

    def Destroy(self):
        self.UnListenEvent()
