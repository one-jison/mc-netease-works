# -*- coding: utf-8 -*-
# ============================================================
#  时间回溯 — 所有能调的数字都在这儿，改完重启就生效
# ============================================================

MODE_ON = True                     # 整个模组的总开关
POTION_NAME = u"回溯"               # 药水名字（聊天提示用）
POTION_ITEM = "timerewind:rewind_potion"   # 物品 ID（别乱改）

# ---------------- 喝下去 ----------------
TIP_ON_DRINK = True        # 喝下去时在聊天框里提示一句
# 按钮留多久：0 = 一直留着（直到死亡 / 退出世界），>0 = 这么多秒后自动收掉
BUTTON_SECONDS = 0.0
COOLDOWN_SECONDS = 5.0     # 按一次之后要等几秒才能再按

# ---------------- 按下去发生什么 ----------------
REWIND_SECONDS = 10.0       # 退回几秒前（10 = 退回十秒前）
DAY_NIGHT_ON = True         # True = 按下后昼夜飞快交替
DAY_NIGHT_SECONDS = 4.0     # 昼夜飞快交替持续几秒（4 = 正好转完一整天）
DAY_NIGHT_CYCLE = 4.0       # 几秒走完这一段（默认 4 秒）
DAY_NIGHT_ONCE = True       # True = 只交替一次：先黑天，再一路走到白天就停（半轮）
                            # False = 转完一整轮：整天转一圈
DAY_NIGHT_START = 18000     # 按下先跳到这个时间再往前走（18000 = 午夜，最黑；走后变白天）

# ---------------- 按下去之后的节奏 ----------------
REWIND_DELAY = 1.0          # 按下后先让昼夜转这么久，再开始回溯生物和方块（秒）
ANIM_SECONDS = 1.0          # 屏幕上那个转钟的「正在回溯...」动画放多久（秒）
ANIM_FRAMES = 8             # 转钟动画几帧（对应贴图 clock_0..clock_7，别乱改）
ANIM_FPS = 8.0              # 转钟每秒放几帧
ANIM_WARM_UP = True         # True = 开局先把这几帧悄悄渲染一遍，第一次放不卡

# ---------------- 回溯时的性能 ----------------
# 一次性恢复太多方块会卡一帧，这里改成每 tick 恢复一点，摊开来做
BLOCK_PUT_PER_TICK = 64     # 每 tick 最多恢复几格方块（64 = 每秒 1280 格）

# ---------------- 回溯谁 ----------------
ENTITY_RANGE = 100.0        # 身边多少格以内的实体跟着回溯
BLOCK_RANGE = 100.0         # 身边多少格以内的方块跟着回溯
REWIND_PLAYERS = False      # True = 连别的玩家也一起退回原位（默认不动别人）
REWIND_SELF = True          # True = 按下去后，自己也退回十秒前站的位置
REWIND_SELF_HP = True       # True = 连自己的血量也一起退回（默认开）
SELF_CHECK_TICKS = 5        # 拉回玩家后，过几 tick 核对一次有没有到位（没到位就补 /tp）

# ---------------- 掉落物 / 背包 / 经验 ----------------
CLEAN_NEW_ITEMS = True      # True = 这段时间里才掉出来的东西（掉落物、经验球）跟着一起清掉
TRASH_TYPES = ("minecraft:item", "minecraft:xp_orb")   # 当作“掉落物”的实体类型
REWIND_INVENTORY = True     # True = 把这一轮里多出来的背包物品收回去（只做减法，不加东西）
REWIND_EXP = True           # True = 把这一轮里多出来的经验扣回去
BAG_KEEP = 40               # 背包 / 经验值最多留多少笔记录（40 笔 = 20 秒）

# ---------------- 箭矢 / 抛射物 ----------------
# 这段时间里刚射出去的箭：不是“收回”，而是放回出膛的位置再飞一次
PROJECTILE_FLY_AGAIN = True
PROJECTILE_TYPES = ("minecraft:arrow", "minecraft:snowball", "minecraft:egg",
                    "minecraft:thrown_trident", "minecraft:ender_pearl",
                    "minecraft:potion", "minecraft:xp_bottle")
PROJECTILE_KEEP_SPEED = True   # 把出膛时那一箭的速度也写回去（插墙上的箭才会再飞）
SHOT_KEEP = 60              # 出膛点记录最多留多少笔
REVIVE_DEAD = True          # True = 这段时间里死掉的生物原地复活
REWIND_HEALTH = True        # True = 连血量一起还原

ENTITY_SAMPLE_TICKS = 10    # 每几 tick 记一次实体的位置（10 = 每秒 2 次）
ENTITY_CACHE_TICKS = 20     # 每隔几 tick 重找一次身边的实体（别每帧都找，省性能）
MAX_ENTITIES = 200          # 一次最多记多少个实体（太多会拖性能）
HISTORY_KEEP = 60           # 每个实体最多留多少条记录
DEATH_KEEP = 200            # 最多留多少条“刚刚死掉”的记录
BLOCK_KEEP = 20000          # 最多留多少格方块记录
MAX_EXPLODE_BLOCKS = 800    # 一次爆炸最多记多少格（爆炸那一刻当场记，不用排队）
EXPLODE_SCAN_RADIUS = 6     # 只有拿不到爆炸方块列表时，才围着爆点扫这么大一圈兜底

# ---------------- 按下按钮那一声 ----------------
# 音效文件：资源包 sounds/timerewind/rewind.ogg（从视频里抽出来的音轨）
BUTTON_SOUND = "timerewind.rewind"    # 名字和 sound_definitions.json 里对应
BUTTON_SOUND_VOLUME = 1.0
BUTTON_SOUND_PITCH = 1.0
BUTTON_SOUND_ON = True                # False = 按下按钮不出这一声

# ---------------- 按下去的动静 ----------------
SOUND_ON_USE = True                     # True = 按下去响一声（用的游戏自带音效，不用额外素材）
SOUND_USE = "mob.endermen.portal"       # 那一声用哪个音效
SOUND_VOLUME = 1.0
SOUND_PITCH = 1.0

# ---------------- 电脑端 ----------------
# 电脑端鼠标锁在准心里，指针移不到屏幕上的按钮，所以给一个键盘快捷键。
# 这里用的是“注册自定义按键”：按键会出现在游戏的【设置 -> 按键】里，
# 玩家可以在那儿自己改成别的键。
USE_KEY_ENABLED = True                  # True = 电脑端按这个键就等于点了一下回溯按钮
USE_KEY_NAME = "TimeRewindUse"          # 按键名（内部标识，英文，别用中文）
USE_KEY_CODE = 82                       # 默认键码：82 = R（82=R 71=G 70=F 72=H 74=J 86=V）
USE_KEY_CATEGORY = "gameplay"           # 设置里归到哪一类：gameplay / movement
USE_KEY_LABEL = u"R"                    # 聊天提示里写的键名

# ---------------- 死亡 ----------------
KEEP_HP_ON_DEATH = True     # True = 死前喝过药，重生时血量回到十秒前那个值

# ============================================================
#  静止药水：喝下去之后三分钟内，随便开关“周围停住”
# ============================================================
FREEZE_ON = True                   # 静止药水这个玩法开着吗
FREEZE_POTION_NAME = u"静止"        # 药水名字（聊天提示用）
FREEZE_POTION_ITEM = "timerewind:freeze_potion"   # 物品 ID（别乱改）
FREEZE_SECONDS = 180.0             # 药效几秒（180 = 三分钟）
FREEZE_RANGE = 100.0               # 身边多少格以内停住
FREEZE_MAX_ENTITIES = 150          # 一次最多管多少个实体（太多会拖性能）
FREEZE_RESCAN_TICKS = 5            # 每几 tick 重新找一遍身边的实体（5 = 每四分之一秒）
FREEZE_TIP_ON_DRINK = True         # 喝下去时在聊天框里提示一句

# ---------------- 右上角那个倒计时 ----------------
# 做成和原版药水效果一样的样子：一个方框，里面是药水图标，图标下是倒计时
FREEZE_TIMER_ON = True          # True = 右上角显示静止药水的倒计时
FREEZE_TIMER_ICON = "textures/items/freeze_potion"   # 方框里的图标（换成别的贴图也行）

# ---------------- 按下按钮时屏幕正中弹的提示 ----------------
# 定个提示：按一下按钮，屏幕正中弹一句，过一会儿自己收掉
FREEZE_POPUP_ON = True          # True = 按按钮时弹提示
FREEZE_POPUP_SECONDS = 2.0      # 提示在屏幕上停几秒（2 = 两秒）
FREEZE_POPUP_ON_TITLE = u"静止 · 开启"
FREEZE_POPUP_ON_SUB = u"身边的一切都停住了"
FREEZE_POPUP_OFF_TITLE = u"静止 · 解除"
FREEZE_POPUP_OFF_SUB = u"身边的一切恢复流动"


# 生物：屏蔽原生 AI（官方说明：屏蔽后无法行动、不受重力、不会被推动），
# 还能顺便把动作冻结住（站着不动、手脚也不动）
FREEZE_AI = True                   # True = 连生物 AI 一起屏蔽
FREEZE_ANIM = True                 # 屏蔽 AI 时是否连动作一起冻结

# 箭矢这些抛射物：AI 那套对它们没用，只能每 tick 把速度清零，让它停在半空；
# 解冻时把原来的速度还回去，箭会接着飞
FREEZE_MOTION = True               # True = 抛射物停在半空
FREEZE_RESTORE_MOTION = True       # True = 解冻后把原来的速度还给它
# 箭被冻住的时候「假装」还在往前飞一点点，只是每次都把它拽回原地。
# 为什么不能直接把速度设成 0：
#   游戏引擎每 tick 都会拿「这一 tick 的位移方向」去重算箭的朝向
#   （所以射出去的箭才会一直朝着飞的方向）。速度一旦是 0，
#   剩下的就只有重力那个向下的分量，引擎就会把箭掰成朝下 ——
#   看起来就是「冻住了还在自己拐弯」。
# 所以这里给一个很小的速度，让方向仍是箭头原本的朝向，位置再由脚本拽住。
# 冻住的箭每 tick 只朝自己原本的方向「挪」这么一点点。
# 为什么要留一点速度、不能直接给 0：
#   引擎的箭朝向是拿「这一 tick 走了哪一步」算出来的 —— 速度给 0 的话，
#   方向就只剩重力那个朝下的分量，箭会被掰成头朝下（也就是会「拐弯」）。
# 留一点点速度，方向就还是箭头原来的朝向；挪出去的那一点点，
# 每 tick 都会把位置摆回原处（是「直接摆回去」，不是往回推，
# 所以画面上不会来回弹、不会抖）。
FREEZE_HOLD_STEP = 0.01            # 每 tick「挪」多少格（默认 0.01，肉眼看不出来）
FREEZE_HOLD_MAX = 0.6              # 补偿量的上限，防止引擎返回异常值时乱飞
FREEZE_HOLD_GRAVITY = 0.05         # 还没量出真值之前，先按这个数猜引擎每 tick 往下拽多少

FREEZE_PROJECTILE_TYPES = ("minecraft:arrow", "minecraft:snowball",
                           "minecraft:egg", "minecraft:thrown_trident",
                           "minecraft:ender_pearl", "minecraft:potion",
                           "minecraft:xp_bottle", "minecraft:fireball",
                           "minecraft:small_fireball",
                           "minecraft:dragon_fireball",
                           "minecraft:wither_skull", "minecraft:tnt",
                           "minecraft:falling_block")

# ---------------- TNT 这些会炸的东西：静止期间不许炸 ----------------
# 麻烦的地方：TNT 头顶那个引信（倒计时）没有任何接口能按暂停键，所以用两个办法
# 凑出「定格」的效果：
#   1) 被冻住的 TNT，每隔一小会儿在原地换成一坨刚刚点着的新 TNT ——
#      新的一坨引信是满的（4 秒），只要换得比 4 秒快，它就永远走不到爆炸那一步。
#      这是主要的办法，效果上就是「TNT 卡在半空一直不炸」。
#   2) 万一还是炸了（比如刚点着就被冻住、引信特别短来不及换），
#      就把这一炸的方块破坏全部取消、把要受伤的人临时护住、再把血补回去。
#      兜底，保证不炸坑、不掉血。
FREEZE_STOP_EXPLODE = True         # True = 静止期间，被冻住的爆炸物炸不起来
# 点着的 TNT 会自己【一闪一闪】（那是引信快要到点时的闪白动画，引擎自己播的，
# 没有接口能停）。所以静止期间干脆把它换成一格真正的 TNT 方块：
# 方块不会闪、不会冒烟、也没有引信，看上去就是彻底定住了。
# 解除静止时再把方块撤掉、原地放回一坨点着的 TNT，让它接着炸。
FREEZE_TNT_AS_BLOCK = True         # True = 冻住的 TNT 变成一格 TNT 方块（最干净）
FREEZE_EXPLODE_TYPES = ("minecraft:tnt", "minecraft:creeper")
FREEZE_TNT_REFRESH = True          # True = 用「换一坨新的」的办法让引信永远走不完
FREEZE_TNT_REFRESH_TICKS = 40      # 每多少 tick 换一次（40 = 2 秒；TNT 引信是 4 秒）
FREEZE_TNT_KEEP_SECONDS = 0.5      # 刚换出来的新 TNT，这么久之内不算“跑出范围”
FREEZE_BLAST_RADIUS = 2.0          # 爆点离被冻住的爆炸物这么近，就认成是它炸的
FREEZE_SHIELD_SECONDS = 0.35       # 兜底：把马上要挨炸的对象临时护住多久（秒）
FREEZE_HEAL_DELAY = 0.08           # 兜底：爆炸后过多久把血补回去（秒）

# 火焰：用游戏自带的 dofiretick 规则，火焰不蔓延、不熄灭、一直保持原样
# （火苗的贴图动画是引擎自己播的，逐格暂停做不到，见使用说明）
FREEZE_FIRE = True                 # True = 火焰停止燃烧
FREEZE_FIRE_RESTORE = True         # True = 解除静止时把规则恢复成“开着”

# ---------------- 静止按钮：电脑端 ----------------
FREEZE_KEY_ENABLED = True               # True = 电脑端按这个键等于点了一下静止按钮
FREEZE_KEY_NAME = "TimeRewindFreeze"    # 按键名（内部标识，英文，别用中文）
FREEZE_KEY_CODE = 71                    # 默认键码：71 = G（82=R 71=G 70=F 72=H 86=V）
FREEZE_KEY_LABEL = u"G"                 # 聊天提示里写的键名

# ============================================================
#  下面几个函数不用动，改上面的数字就行
# ============================================================
def rewindSeconds():
    return max(1.0, float(REWIND_SECONDS))


def dayNightOn():
    return bool(DAY_NIGHT_ON)


def dayNightOnce():
    return bool(DAY_NIGHT_ONCE)


def dayNightStart():
    return int(DAY_NIGHT_START) % 24000


def dayNightSeconds():
    return max(0.5, float(DAY_NIGHT_SECONDS))


def dayNightStep():
    # 每次推多少帧：24000 帧 = 一整天（半轮 12000 帧），20 tick = 1 秒
    cycle = max(0.5, float(DAY_NIGHT_CYCLE))
    frames = 12000.0 if bool(DAY_NIGHT_ONCE) else 24000.0
    return max(1, int(round(frames / (cycle * 20.0))))


def buttonSeconds():
    return max(0.0, float(BUTTON_SECONDS))


def cooldownSeconds():
    return max(0.0, float(COOLDOWN_SECONDS))


def rewindDelay():
    return max(0.0, float(REWIND_DELAY))


def buttonSoundOn():
    return bool(BUTTON_SOUND_ON)


def buttonSound():
    return u"%s" % BUTTON_SOUND


def animWarmUp():
    return bool(ANIM_WARM_UP)


def animSeconds():
    return max(0.0, float(ANIM_SECONDS))


def entityRange():
    return max(1.0, float(ENTITY_RANGE))


def blockRange():
    return max(1.0, float(BLOCK_RANGE))


def sampleTicks():
    return max(1, int(ENTITY_SAMPLE_TICKS))


def cacheTicks():
    return max(1, int(ENTITY_CACHE_TICKS))


def soundOn():
    return bool(SOUND_ON_USE)


def keepHpOnDeath():
    return bool(KEEP_HP_ON_DEATH)


def useKeyOn():
    return bool(USE_KEY_ENABLED)


def freezeSeconds():
    return max(1.0, float(FREEZE_SECONDS))


def freezeRange():
    return max(1.0, float(FREEZE_RANGE))


def freezeFire():
    return bool(FREEZE_FIRE)


def freezeFireRestore():
    return bool(FREEZE_FIRE_RESTORE)


def freezeStopExplode():
    return bool(FREEZE_STOP_EXPLODE)


def freezeTntRefresh():
    return bool(FREEZE_TNT_REFRESH)


def freezeTntAsBlock():
    return bool(FREEZE_TNT_AS_BLOCK)


def freezeTntTicks():
    return max(1, int(FREEZE_TNT_REFRESH_TICKS))


def freezeTntKeep():
    return max(0.0, float(FREEZE_TNT_KEEP_SECONDS))


def freezeBlastRadius():
    return max(0.5, float(FREEZE_BLAST_RADIUS))


def freezeShieldSeconds():
    return max(0.05, float(FREEZE_SHIELD_SECONDS))


def freezeHealDelay():
    return max(0.0, float(FREEZE_HEAL_DELAY))


def freezeKeyOn():
    return bool(FREEZE_KEY_ENABLED)


def freezeKeyLabel():
    return u"%s" % FREEZE_KEY_LABEL


def useKeyLabel():
    return u"%s" % USE_KEY_LABEL



def freezeTimerOn():
    return bool(FREEZE_TIMER_ON)


def freezeTimerIcon():
    return u"%s" % FREEZE_TIMER_ICON


def freezePopupOn():
    return bool(FREEZE_POPUP_ON)


def freezePopupSeconds():
    return max(0.3, float(FREEZE_POPUP_SECONDS))
