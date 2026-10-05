# -*- coding: utf-8 -*-
# ============================================================
#  锁血 —— 服务端
#    · 快死的时候把血量锁在半颗心（1 点血），锁住就死不了
#    · 能力默认没开，必须管理员给：
#          原生指令   /tag <玩家名> add lockhp   （推荐：不走聊天，最稳）
#      也能用聊天框   #锁血 on <玩家名>
#    · 手里拿着不死图腾：图腾照常爆；爆掉之后手里没图腾了，
#      血量照样最低半颗心
#    · 不往屏幕上打任何字（测试服会把消息打码成 ***，屏幕上全是星星）
# ============================================================
import mod.server.extraServerApi as serverApi

from LockHpScripts import modConfig as cfg

# 加载成功会往 MC Studio 的日志里打这一行（就一行）
print("[LockHp] mod loaded")

ServerSystem = serverApi.GetServerSystemCls()

_TEXT = type(u"")


def _f():
    return serverApi.GetEngineCompFactory()


def _u(v):
    # 聊天内容可能是 bytes（中文最容易在这里炸），统一转成文本
    if v is None:
        return u""
    if isinstance(v, _TEXT):
        return v
    for enc in ("utf-8", "gbk"):
        try:
            return v.decode(enc)
        except Exception:
            pass
    return u""


class LockHpServerSystem(ServerSystem):

    def __init__(self, namespace, systemName):
        ServerSystem.__init__(self, namespace, systemName)
        self.mLocked = {}      # playerId -> True（有锁血能力的人）
        self.mTick = 0
        self.mErr = u""
        self.mGrant = {}       # 名字 -> True（本次开机期间给过的人，不靠标签也能算）
        self.mSeen = {}        # playerId -> True（诊断只打一次）
        self.mTotemLast = {}   # playerId -> 上次“手里有没有图腾”的诊断结果
        self._listen()

    # ==================== 事件 ====================
    def _listen(self):
        ns = serverApi.GetEngineNamespace()
        sn = serverApi.GetEngineSystemName()
        self._on(ns, sn, "OnScriptTickServer", self.OnTick)
        self._on(ns, sn, "ServerChatEvent", self.OnChat)
        self._on(ns, sn, "DelServerPlayerEvent", self.OnLeave)
        self._on(ns, sn, "ActuallyHurtServerEvent", self.OnHurt)
        # ponytail: 两个受伤事件都挂，谁到算谁——只挂一个，万一某个版本
        #           不推这个事件，锁血就整段静默失效（这次就是栽在这）
        self._on(ns, sn, "DamageEvent", self.OnHurt)

    def _on(self, ns, sn, name, handler):
        # 哪一个事件名这台机器上没有的话就跳过它，别把整个系统带崩
        try:
            self.ListenForEvent(ns, sn, name, self, handler)
        except Exception:
            pass

    # ==================== 每帧 ====================
    def OnTick(self, args=None):
        # 外壳：这三个回调每帧 / 每次都跑，抛一个异常就是满屏报错，所以全部包住
        try:
            self._tick(args)
        except Exception as e:
            self.mErr = _u(repr(e))

    def _tick(self, args=None):
        self.mTick += 1
        try:
            every = int(cfg.CHECK_EVERY)
        except Exception:
            every = 10
        if every < 1:
            every = 1
        if self.mTick % every == 1:
            self._refresh()
        if not self.mLocked:
            return
        for pid in list(self.mLocked.keys()):
            cur = self._hp(pid)
            # 只往上抬，不往下压；0 血说明人已经倒了，不去动它
            if cur is not None and 0.0 < cur < float(cfg.LOCK_HP):
                self._setHp(pid, cfg.LOCK_HP)


    # ==================== 挨打 ====================
    def OnHurt(self, args=None):
        # 外壳：这三个回调每帧 / 每次都跑，抛一个异常就是满屏报错，所以全部包住
        try:
            self._hurt(args)
        except Exception as e:
            self.mErr = _u(repr(e))

    def _hurt(self, args=None):
        # 这一刀会把人打死的话，只扣到半颗心为止
        if not args:
            return
        pid = self._eidOf(args)
        self._diag(pid)
        if not pid or pid not in self.mLocked:
            return
        if self._hasTotem(pid):
            return          # 手里有图腾：这一下让它照常爆
        cur = self._hp(pid)
        if cur is None:
            return
        try:
            dmg = float(args.get("damage", 0.0))
        except Exception:
            return
        keep = float(cfg.LOCK_HP)
        if cur - dmg < keep:
            newd = max(0.0, cur - keep)
            try:
                args["damage"] = newd
            except Exception:
                pass

    def OnLeave(self, args=None):
        # 外壳：这三个回调每帧 / 每次都跑，抛一个异常就是满屏报错，所以全部包住
        try:
            self._leave(args)
        except Exception as e:
            self.mErr = _u(repr(e))

    def _leave(self, args=None):
        pid = (args or {}).get("playerId")
        if pid:
            self.mLocked.pop(pid, None)


    # ==================== 聊天框指令 ====================
    def OnChat(self, args=None):
        try:
            if not args:
                return
            pid = args.get("playerId")
            msg = _u(args.get("message")).strip()
            if not pid or not msg:
                return
            low = msg.lower()
            hit = None
            for w in cfg.CHAT_WORDS:
                w = _u(w)
                if not w:
                    continue
                if low == w or low.startswith(w + u" "):
                    hit = w
                    break
            if hit is None:
                return
            print("[LockHp] cmd ok")
            self._command(pid, msg[len(hit):].strip())
        except Exception as e:
            self._note(e)

    def _command(self, pid, tail):
        # 聊天框那条指令：只认动作，不往回打任何字。
        # （测试服会把消息打码成 ***，屏幕上全是星星，所以整块回执删了）
        tail = tail.replace(u"\u3000", u" ").replace(u"\uff0c", u" ").replace(u",", u" ")
        words = [w for w in tail.split(u" ") if w]
        if not words:
            return
        act = words[0].lower()
        if act in (u"on", u"1", u"\u5f00", u"\u5f00\u542f", u"\u7ed9", u"\u52a0"):
            want = True
        elif act in (u"off", u"0", u"\u5173", u"\u5173\u95ed", u"\u53d6\u6d88", u"\u5220"):
            want = False
        else:
            return

        target = pid
        if len(words) > 1:
            target = self._find(words[1])
            if target is None:
                return

        if not self._isAdmin(pid):
            return

        key = self._nameKey(target)
        if want:
            self.mGrant[key] = True
        else:
            self.mGrant.pop(key, None)
        print("[LockHp] grant on=%s" % (1 if want else 0,))
        self._setTag(target, want)
        self._refresh()

    def _isAdmin(self, pid):
        # 只有能跑 /tag 的人（管理员 / 房主）才算管理员。
        # 探测本身出问题的时候一律放行，免得管理员反而被拦住。
        # ponytail: 能跑 /tag 就算管理员，是启发式判断，不是权限接口；
        #           探不出来就放行（宁愿放过管理员，不能把他拦死）。
        #           以后要严格：改成读玩家的 op 等级。
        probe = "lockhp_probe"
        try:
            comp = _f().CreateCommand(serverApi.GetLevelId())
            if comp is None:
                return True
            ret = comp.SetCommand("/tag @s add " + probe, pid)
            got = self._hasTag(pid, probe)
            self._setTag(pid, False, tag=probe)
            if got:
                return True
            if ret is not None:
                return bool(ret)
        except Exception:
            pass
        return True



    # ==================== 取数据的小工具 ====================
    def _note(self, e):
        # 内部接口出错不往外抛（往外抛就是刷屏），但记一笔，
        # 想查内部错误，看 MC Studio 日志里的 mErr 打印
        try:
            self.mErr = _u(repr(e))
        except Exception:
            self.mErr = u"?"

    def _nameKey(self, pid):
        return _u(self._nameOf(pid)).strip().lower()




    def _diag(self, pid):
        # 排查用：每个玩家只打一行，证明“挨打事件真的进来了”，
        # 以及当时认没认出锁血。查完可以整段删掉。
        if not pid or pid in self.mSeen:
            return
        self.mSeen[pid] = True
        print("[LockHp] hurt seen pid=%s locked=%s"
              % (pid, pid in self.mLocked))

    def _eidOf(self, args):
        for k in ("entityId", "hurtEntityId", "id", "playerId"):
            v = args.get(k)
            if v:
                return v
        return None

    def _hp(self, pid):
        try:
            en = serverApi.GetMinecraftEnum()
            return float(_f().CreateAttr(pid).GetAttrValue(en.AttrType.HEALTH))
        except Exception as e:
            self._note(e)
            return None

    def _setHp(self, pid, hp):
        try:
            en = serverApi.GetMinecraftEnum()
            _f().CreateAttr(pid).SetAttrValue(en.AttrType.HEALTH, float(hp))
            return True
        except Exception as e:
            self._note(e)
            return False

    def _hasTotem(self, pid):
        # 身上任意一格（含主手那一格）+ 副手，只要有不死图腾就算有。
        # ponytail: 批量读整背包，不去问“当前选中第几格”——那个接口读错时返回 -1，
        #           主手拿着的图腾就永远认不出来，图腾一直不爆就是栽在这。
        names = []
        try:
            comp = _f().CreateItem(pid)
            en = serverApi.GetMinecraftEnum()
            for pos in (en.ItemPosType.INVENTORY, en.ItemPosType.OFFHAND):
                try:
                    bag = comp.GetPlayerAllItems(pos, True)
                except Exception as e:
                    self._note(e)
                    names.append(u"?")      # 读不出来，日志里一眼看得出
                    continue
                for it in list(bag or []):
                    if isinstance(it, dict):
                        nm = _u(it.get("newItemName") or it.get("itemName") or "")
                        if nm:
                            names.append(nm)
        except Exception as e:
            self._note(e)
        has = cfg.TOTEM in [n.strip().lower() for n in names]
        self._totemSay(pid, has, names)
        return has

    def _totemSay(self, pid, has, names):
        # 诊断用：结果变了才打一行。查完可以删。
        if self.mTotemLast.get(pid) == has:
            return
        self.mTotemLast[pid] = has
        print("[LockHp] totem pid=%s has=%s slots=%s" % (pid, has, names))

    def _hasTag(self, pid, tag=None):
        want = tag or cfg.TAG
        try:
            if _f().CreateTag(pid).EntityHasTag(want):
                return True
        except Exception as e:
            self._note(e)
        # 兜底：EntityHasTag 认不出（或这台机器上不好使）时，直接问标签列表
        try:
            return want in list(_f().CreateTag(pid).GetEntityTags() or [])
        except Exception as e:
            self._note(e)
            return False

    def _setTag(self, pid, on, tag=None):
        tag = tag or cfg.TAG
        try:
            comp = _f().CreateTag(pid)
            if on:
                return bool(comp.AddEntityTag(tag))
            return bool(comp.RemoveEntityTag(tag))
        except Exception as e:
            self._note(e)
            return False

    def _nameOf(self, pid):
        try:
            return _u(_f().CreateName(pid).GetName())
        except Exception:
            return _u(pid)

    def _find(self, name):
        want = _u(name).lower()
        for pid in list(serverApi.GetPlayerList() or []):
            if self._nameOf(pid).lower() == want:
                return pid
        return None

    # ponytail: 标签靠每 10 tick 轮询扫，没接标签变化事件。
    #           人多到扫不动再改成事件驱动。
    def _refresh(self):
        out = {}
        for pid in list(serverApi.GetPlayerList() or []):
            if self._hasTag(pid) or self._nameKey(pid) in self.mGrant:
                out[pid] = True
        if set(out.keys()) != set(self.mLocked.keys()):
            print("[LockHp] locked=%d %s" % (len(out), sorted(out.keys())))
        self.mLocked = out


