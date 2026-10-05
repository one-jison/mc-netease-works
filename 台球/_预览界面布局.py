# -*- coding: utf-8 -*-
# \u6309\u754c\u9762\u91cc\u540c\u4e00\u5957\u516c\u5f0f\u79bb\u7ebf\u753b\u4e00\u5f20\u9884\u89c8\u56fe\uff0c\u786e\u8ba4\u4f4d\u7f6e\u6ca1\u9519
import os, sys, math
from PIL import Image, ImageDraw, ImageFont
ROOT = u"C:\\Users\\Admin\uff08\u65e0\u5bc6\u7801\uff09\\Documents\\\u53f0\u7403"
sys.path.insert(0, os.path.join(ROOT, "poolBehaviorPack"))
TU = os.path.join(ROOT, "poolResourcePack", "textures", "ui", "pool")
from PoolScripts.poolCommon import constants as C
from PoolScripts.poolCommon import aim as A
from PoolScripts.poolCommon.physics import Sim

def font(sz):
    for p in (r"C:\Windows\Fonts\msyhbd.ttc", r"C:\Windows\Fonts\msyh.ttc",
              r"C:\Windows\Fonts\simhei.ttf", r"C:\Windows\Fonts\arialbd.ttf"):
        try:
            return ImageFont.truetype(p, sz)
        except Exception:
            continue
    return ImageFont.load_default()

def tex(name):
    return Image.open(os.path.join(TU, name)).convert("RGBA")

def layout(W, H):
    S = min(W, H)
    aspect = C.UICanvasW / C.UICanvasH
    tw = min(W * 0.86, H * 0.62 * aspect)
    th = tw / aspect
    tx = (W - tw) * 0.5
    ty = H * 0.045
    rx = C.UIRail / C.UICanvasW * tw
    ry = C.UIRail / C.UICanvasH * th
    rw = tw - 2 * rx
    rh = th - 2 * ry
    g = dict(W=W, H=H, S=S, tx=tx, ty=ty, tw=tw, th=th, rx=rx, ry=ry, rw=rw, rh=rh,
             ballD=max(6.0, C.BallDiameter / C.TableLength * rw),
             lineH=max(3.0, S * 0.013), lineH2=max(2.0, S * 0.009))
    barY = ty + th + H * 0.045
    pad = W * 0.03
    spinS = S * 0.155
    g["spinS"] = spinS; g["spinX"] = pad; g["spinY"] = barY
    pbH = max(10.0, S * 0.045); pbW = W * 0.40
    g["pbX"] = pad + spinS + W * 0.035
    g["pbY"] = barY + spinS * 0.5 - pbH * 0.5
    g["pbW"] = pbW; g["pbH"] = pbH
    shootS = min(S * 0.20, W * 0.14)
    g["shootX"] = W - pad - shootS
    g["shootY"] = barY + spinS * 0.5 - shootS * 0.5
    g["shootS"] = shootS
    bw = W * 0.13; bh = S * 0.085
    g["exitX"] = W - pad - bw; g["exitY"] = H * 0.035; g["bw"] = bw; g["bh"] = bh
    g["resetX"] = W - pad - bw * 0.78
    g["resetY"] = H * 0.035 + bh * 1.25
    g["titleX"] = W * 0.10; g["titleY"] = ty + th * 0.13
    g["titleW"] = W * 0.80; g["titleH"] = S * 0.11
    g["msgX"] = W * 0.11; g["msgY"] = ty + th * 0.13 + S * 0.115
    g["msgW"] = W * 0.78; g["msgH"] = S * 0.085
    return g

def to_screen(g, px, pz):
    return (g["tx"] + g["rx"] + px / C.TableLength * g["rw"],
            g["ty"] + g["ry"] + pz / C.TableWidth * g["rh"])

def draw_dots(d, x0, y0, x1, y1, n, dot, gap, skip, col):
    # 和 poolScreen._dots() 一模一样的算法，用来预览瞄准线
    L = math.hypot(x1 - x0, y1 - y0)
    if L <= skip + dot:
        return
    step = gap
    if (L - skip) > step * n:
        step = (L - skip) / float(n)
    for i in range(n):
        d0 = skip + step * i
        if d0 > L:
            continue
        t = d0 / L
        cx = x0 + (x1 - x0) * t
        cy = y0 + (y1 - y0) * t
        r = dot * 0.5
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col)



def paste_center(base, im, cx, cy):
    w, h = im.size
    base.alpha_composite(im, (int(cx - w / 2), int(cy - h / 2)))

def paste_tl(base, im, x, y, w, h):
    base.alpha_composite(im.resize((max(1, int(w)), max(1, int(h))), Image.LANCZOS),
                         (int(x), int(y)))

def draw(W, H, path):
    base = Image.new("RGBA", (W, H), (58, 96, 62, 255))
    d = ImageDraw.Draw(base)
    g = layout(W, H)
    paste_tl(base, tex("table.png"), g["tx"], g["ty"], g["tw"], g["th"])
    # \u7403
    sim = Sim()
    # \u8ba9\u767d\u7403\u6321\u5728\u4e00\u8fb9\uff0c\u9884\u89c8\u7763\u51c6\u7ebf
    sim.ball(0).x = C.HeadSpotX
    sim.ball(0).y = C.TableWidth * 0.5
    dx, dy = 1.0, -0.55
    a = A.solve(sim, dx, dy)
    bd = g["ballD"]
    # 瞄准线：一串小圆点，方向跟着拖动走
    x0, y0 = to_screen(g, a.sx, a.sy)
    x1, y1 = to_screen(g, a.hx, a.hy)
    draw_dots(d, x0, y0, x1, y1, 22, max(3.0, bd * 0.38), bd * 0.75, bd * 0.95,
              (255, 255, 255, 235))
    if a.kind == "ball":
        ox, oy = to_screen(g, a.objX, a.objY)
        draw_dots(d, ox, oy,
                  ox + a.objDx * bd * 6.0, oy + a.objDy * bd * 6.0,
                  10, max(2.5, bd * 0.32), bd * 0.75, bd * 1.15,
                  (150, 215, 255, 220))
    for b in sim.balls:
        if not b.active:
            continue
        cx, cy = to_screen(g, b.x, b.y)
        nm = "ball_cue.png" if b.num == 0 else "ball_%d.png" % b.num
        paste_center(base, tex(nm).resize((max(3, int(bd)), max(3, int(bd))), Image.LANCZOS), cx, cy)
    if a.kind == "ball":
        paste_center(base, tex("aim_ring.png").resize((max(3, int(bd * 1.12)),) * 2, Image.LANCZOS), x1, y1)
    # \u5e95\u90e8
    paste_tl(base, tex("spin_bg.png"), g["spinX"], g["spinY"], g["spinS"], g["spinS"])
    sc = g["spinS"] * 0.5
    dotS = g["spinS"] * 0.22
    paste_center(base, tex("spin_dot.png").resize((int(dotS), int(dotS)), Image.LANCZOS),
                 g["spinX"] + sc + 0.35 * (sc - sc * 0.20),
                 g["spinY"] + sc - 0.45 * (sc - sc * 0.20))
    fp = g["pbH"] * 0.55
    paste_tl(base, tex("power_frame.png"), g["pbX"] - fp, g["pbY"] - fp,
             g["pbW"] + fp * 2, g["pbH"] + fp * 2)
    paste_tl(base, tex("power_bg.png"), g["pbX"], g["pbY"], g["pbW"], g["pbH"])
    paste_tl(base, tex("power_fill.png"), g["pbX"] + 3, g["pbY"] + 3,
             max(1, g["pbW"] * 0.62), g["pbH"] - 6)
    paste_tl(base, tex("btn_shoot.png"), g["shootX"], g["shootY"], g["shootS"], g["shootS"])
    paste_tl(base, tex("btn_exit.png"), g["exitX"], g["exitY"], g["bw"], g["bh"])
    paste_tl(base, tex("btn_small.png"), g["resetX"], g["resetY"], g["bw"] * 0.78, g["bh"] * 0.78)
    # 单人练习 / 人机对战（只在等人时露脸）
    mw = W * 0.20
    mh = g["S"] * 0.13
    soloX = W * 0.5 - mw - W * 0.015
    aiX = W * 0.5 + W * 0.015
    soloY = g["ty"] + g["th"] * 0.66
    paste_tl(base, tex("btn_exit.png"), soloX, soloY, mw, mh)
    paste_tl(base, tex("btn_exit.png"), aiX, soloY, mw, mh)
    # \u5b57
    def txt(x, y, w, h, s, fsz, align="center", col=(255, 255, 255)):
        f = font(fsz)
        bb = d.textbbox((0, 0), s, font=f)
        tw_, th_ = bb[2] - bb[0], bb[3] - bb[1]
        if align == "center":
            px = x + (w - tw_) / 2.0 - bb[0]
        else:
            px = x - bb[0]
        py = y + (h - th_) / 2.0 - bb[1]
        d.text((px + 1, py + 1), s, font=f, fill=(0, 0, 0, 170))
        d.text((px, py), s, font=f, fill=col)
    txt(g["shootX"], g["shootY"], g["shootS"], g["shootS"], u"\u51fb\u7403",
        max(14, int(g["shootS"] * 0.30)))
    txt(g["exitX"], g["exitY"], g["bw"], g["bh"], u"\u79bb\u5f00\u7403\u684c",
        max(11, int(g["bh"] * 0.42)))
    txt(g["resetX"], g["resetY"], g["bw"] * 0.78, g["bh"] * 0.78, u"\u91cd\u65b0\u6446\u7403",
        max(10, int(g["bh"] * 0.34)))
    txt(soloX, soloY, mw, mh, u"\u5355\u4eba\u7ec3\u4e60", max(14, int(mh * 0.44)))
    txt(aiX, soloY, mw, mh, u"\u4eba\u673a\u5bf9\u6218", max(14, int(mh * 0.44)))
    txt(g["pbX"], g["pbY"] - fp - g["pbH"] * 1.7, g["pbW"], g["pbH"] * 1.6,
        u"\u529b\u5ea6 62%", max(11, int(g["pbH"] * 1.1)))
    txt(g["msgX"], g["msgY"], g["msgW"], g["msgH"], u"\u8fdb\u4e86 1 \u53f7\u7403\uff0c\u63a5\u7740\u6253",
        max(12, int(g["msgH"] * 0.55)))
    txt(g["titleX"], g["titleY"], g["titleW"], g["titleH"],
        u"\u8f6e\u5230\u4f60\u4e86\u3000\u4f60\uff1a\u5168\u8272 1-7", max(14, int(g["titleH"] * 0.55)))
    base.convert("RGB").save(path, "PNG")
    print("saved", path, W, H)

draw(2400, 1080, os.path.join(ROOT, u"_\u9884\u89c8_\u53f0\u7403\u754c\u9762_\u624b\u673a.png"))
draw(1920, 1080, os.path.join(ROOT, u"_\u9884\u89c8_\u53f0\u7403\u754c\u9762_\u7535\u8111.png"))


# ---- 世界里那颗「进入台球」按钮的落点 ----
# 界面文件里写死了：panel 88x44、贴着底边往上 34（物品栏本身高 22）。
# 这里按真实截图量出来的比例（1 个界面单位 ≈ 5 个像素）画一张，看它落哪儿。
def draw_hud(path, W=2200, H=1000):
    s = H / 311.0                      # 界面单位 -> 像素
    base = Image.new("RGBA", (W, H), (96, 140, 72, 255))
    d = ImageDraw.Draw(base)
    hot_h = 22.0 * s
    hot_w = 186.0 * s
    hx = (W - hot_w) * 0.5
    hy = H - hot_h
    sw = hot_w / 9.0
    for i in range(9):
        d.rectangle([hx + i * sw + 1, hy + 2, hx + (i + 1) * sw - 1, H - 3],
                    (139, 139, 139, 255), (60, 60, 60, 255))
    # 经验条 + 生命 / 饥饿（都在物品栏上方，说明这颗按钮压不到它们中间）
    xp_h = 5.0 * s
    d.rectangle([hx, hy - xp_h, hx + hot_w, hy], (0, 160, 0, 255))
    row_h = 9.0 * s
    ry0 = hy - xp_h - 4.0 * s - row_h
    for i in range(10):
        d.rectangle([hx + i * sw * 0.55 + 2, ry0,
                     hx + i * sw * 0.55 + sw * 0.5, ry0 + row_h], (200, 40, 40, 255))
        d.rectangle([hx + hot_w - sw * 0.5 - i * sw * 0.55 + 2, ry0,
                     hx + hot_w - i * sw * 0.55, ry0 + row_h], (170, 120, 50, 255))
    pw, ph = 88.0 * s, 44.0 * s
    px = (W - pw) * 0.5
    py = H - 54.0 * s - ph
    base.alpha_composite(tex("enter_btn.png").resize((int(pw), int(ph)), Image.LANCZOS),
                         (int(px), int(py)))
    d.rectangle([px, py, px + pw, py + ph], outline=(255, 0, 0, 255), width=2)
    d.line([0, hy - xp_h, W, hy - xp_h], fill=(0, 0, 255, 255), width=2)
    d.text((20, py - 34), u"按钮底边离屏幕底 54 —— 坐在物品栏那一整块（含血条）的上边",
           font=font(22), fill=(255, 255, 255, 255))
    d.text((20, py - 6), u"按钮 88x44，是原来那颗 240x120 的三分之一大",
           font=font(22), fill=(255, 255, 255, 255))
    base.convert("RGB").save(path, "PNG")
    print("saved", path, W, H, "button", int(pw), int(ph))


draw_hud(os.path.join(ROOT, u"_预览_靠近按钮_手机.png"))
