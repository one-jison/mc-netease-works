# -*- coding: utf-8 -*-
# ============================================================
#  锁血 - 公共配置
# ============================================================
ModName = "LockHpMod"
ModVersion = "1.0.0"

ServerSystemName = "LockHpServerSystem"
ClientSystemName = "LockHpClientSystem"
ServerSystemClsPath = "LockHpScripts.lockHpServerSystem.LockHpServerSystem"
ClientSystemClsPath = "LockHpScripts.lockHpClientSystem.LockHpClientSystem"

# 锁住的血量：半颗心 = 1 点血
LOCK_HP = 1.0

# 身上有这个标签 = 管理员已经给了锁血能力
TAG = "lockhp"

# 聊天框里的指令（几种写法都认）
CHAT_WORDS = (u"#锁血", u"#lockhp", u"锁血")

# 不死图腾
TOTEM = "minecraft:totem_of_undying"

# 每多少 tick 刷一次“谁有锁血能力”（10 tick = 半秒）
CHECK_EVERY = 10
# ponytail: 轮询而不是事件驱动，见 lockHpServerSystem._refresh。
