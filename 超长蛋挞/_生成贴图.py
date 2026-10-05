# -*- coding: utf-8 -*-
import os, random
from PIL import Image, ImageDraw, ImageFont

ROOT = r"C:\Users\Admin（无密码）\Documents\超长蛋挞\EggTartMod\eggTartResourcePack\textures"
BLOCKS = os.path.join(ROOT, "blocks")
ITEMS = os.path.join(ROOT, "items")
for d in (BLOCKS, ITEMS):
    if not os.path.isdir(d):
        os.makedirs(d)

# ---- 从照片取到的配色 ----
BOX_DEEP   = (26, 17, 21)
BOX_DARK   = (38, 25, 29)
BOX_MID    = (55, 39, 46)
BOX_LIGHT  = (64, 50, 59)
GOLD       = (216, 170, 88)
GOLD_LIGHT = (245, 222, 158)
GOLD_DARK  = (150, 110, 48)
CRUST      = (206, 146, 95)
CRUST_LT   = (224, 178, 124)
CRUST_DK   = (170, 108, 58)
CRUST_DP   = (139, 66, 31)
CUSTARD    = (238, 205, 140)
CUSTARD_DK = (222, 178, 96)
BURN       = (100, 45, 18)
BURN_LT    = (139, 66, 31)

FONT_CAND = [r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\msyhbd.ttc",
             r"C:\Windows\Fonts\simhei.ttf", r"C:\Windows\Fonts\simsun.ttc"]

def font(size):
    for p in FONT_CAND:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return None

def gold_text(text, w, h):
    u"""把中文渲染成 w x h 的金色像素点阵（透明底）"""
    big = 200
    f = font(big)
    if f is None:
        return None
    tmp = Image.new("L", (big * (len(text) + 1), big * 2), 0)
    d = ImageDraw.Draw(tmp)
    d.text((big // 2, big // 2), text, font=f, fill=255)
    bb = tmp.getbbox()
    if not bb:
        return None
    tmp = tmp.crop(bb)
    # 等比缩到目标高度
    ratio = float(h) / tmp.height
    nw = max(1, int(round(tmp.width * ratio)))
    tmp = tmp.resize((nw, h), Image.LANCZOS)
    if nw > w:
        tmp = tmp.crop(((nw - w) // 2, 0, (nw - w) // 2 + w, h))
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    px = tmp.load()
    op = out.load()
    for y in range(h):
        for x in range(tmp.width if tmp.width <= w else w):
            v = px[x, y]
            if v > 90:
                t = min(255, int((v - 90) * 255 / 100))
                r = GOLD[0] + (GOLD_LIGHT[0] - GOLD[0]) * t // 255
                g = GOLD[1] + (GOLD_LIGHT[1] - GOLD[1]) * t // 255
                b = GOLD[2] + (GOLD_LIGHT[2] - GOLD[2]) * t // 255
                op[x, y] = (r, g, b, 255)
    return out

# ============================================================
#  1. 包装盒 - 盒身贴图  64x64
# ============================================================
body = Image.new("RGBA", (64, 64), (0, 0, 0, 0))

# ---- 正面 (0,0)-(48,12) ----
fx, fy, fw, fh = 0, 0, 48, 12
d = ImageDraw.Draw(body)
d.rectangle([fx, fy, fx + fw - 1, fy + fh - 1], fill=BOX_DARK)
d.rectangle([fx, fy, fx + fw - 1, fy], fill=BOX_MID)          # 顶棱
d.line([fx, fy + fh - 1, fx + fw - 1, fy + fh - 1], fill=BOX_MID)
d.line([fx, fy, fx, fy + fh - 1], fill=BOX_MID)
d.line([fx + fw - 1, fy, fx + fw - 1, fy + fh - 1], fill=BOX_MID)
# 蛋挞窗口的金色边框
d.line([fx + 3, fy + 1, fx + 44, fy + 1], fill=GOLD)
d.line([fx + 3, fy + 4, fx + 44, fy + 4], fill=GOLD)
# 窗口里的蛋挞
rnd = random.Random(20260928)
for x in range(4, 44):
    d.point((fx + x, fy + 2), fill=CUSTARD if x % 5 else CUSTARD_DK)
    d.point((fx + x, fy + 3), fill=CRUST if x % 7 else CRUST_DK)
for _ in range(9):
    x = rnd.randint(5, 42)
    y = rnd.choice([2, 3])
    d.point((fx + x, fy + y), fill=BURN_LT)
    d.point((fx + min(43, x + 1), fy + y), fill=BURN)
# 金色大字：超长蛋挞
txt = gold_text(u"超长蛋挞", 42, 6)
if txt:
    body.paste(txt, (fx + 3, fy + 6), txt)

# ---- 背面 (0,13)-(48,25) ----
bx, by = 0, 13
d.rectangle([bx, by, bx + fw - 1, by + fh - 1], fill=BOX_DARK)
d.line([bx, by, bx + fw - 1, by], fill=BOX_MID)
d.line([bx, by + fh - 1, bx + fw - 1, by + fh - 1], fill=BOX_MID)
d.line([bx + 2, by + 3, bx + 45, by + 3], fill=GOLD_DARK)
d.line([bx + 2, by + fh - 4, bx + 45, by + fh - 4], fill=GOLD_DARK)
for i in range(4):                                   # 中间的金色菱形纹章
    d.point((bx + 24 - i, by + 4 + i), fill=GOLD)
    d.point((bx + 24 + i, by + 4 + i), fill=GOLD)
    d.point((bx + 24 - i, by + 9 - i), fill=GOLD)
    d.point((bx + 24 + i, by + 9 - i), fill=GOLD)

# ---- 顶面 (0,26)-(48,34) ----
tx, ty = 0, 26
d.rectangle([tx, ty, tx + 47, ty + 7], fill=BOX_DARK)
d.line([tx, ty, tx + 47, ty], fill=BOX_MID)
d.line([tx, ty + 7, tx + 47, ty + 7], fill=BOX_MID)
d.line([tx + 3, ty + 2, tx + 44, ty + 2], fill=GOLD_DARK)
d.line([tx + 3, ty + 5, tx + 44, ty + 5], fill=GOLD_DARK)
d.line([tx + 23, ty + 1, tx + 23, ty + 6], fill=BOX_DEEP)   # 开盒缝
d.line([tx + 24, ty + 1, tx + 24, ty + 6], fill=GOLD_DARK)
for x in (6, 40):
    d.rectangle([tx + x, ty + 3, tx + x + 1, ty + 4], fill=GOLD)

# ---- 底面 (0,35)-(48,43) ----
dx, dy = 0, 35
d.rectangle([dx, dy, dx + 47, dy + 7], fill=BOX_MID)
d.line([dx, dy, dx + 47, dy], fill=BOX_LIGHT)
d.line([dx, dy + 7, dx + 47, dy + 7], fill=BOX_DEEP)

# ---- 两端 (0,44)-(8,56) 与 (9,44)-(17,56) ----
for lx in (0, 9):
    ex, ey = lx, 44
    d.rectangle([ex, ey, ex + 7, ey + 11], fill=BOX_DARK)
    d.rectangle([ex, ey, ex + 7, ey + 11], outline=BOX_MID)
    d.rectangle([ex + 1, ey + 1, ex + 6, ey + 10], outline=GOLD_DARK)
    for i, yy in enumerate((ey + 4, ey + 6, ey + 8)):       # 简化的 50CM 金色字样
        d.line([ex + 2, yy, ex + 5 - i % 2, yy], fill=GOLD)
body.save(os.path.join(BLOCKS, "eggtart_box_body.png"))

# ============================================================
#  2. 包装盒 - 拎手贴图  64x64
# ============================================================
hd = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
d = ImageDraw.Draw(hd)
# 正面/背面 (0,0)-(14,10)
d.rectangle([0, 0, 13, 9], fill=BOX_DARK)
d.rectangle([0, 0, 13, 9], outline=BOX_MID)
# 提手孔（画成深色凹槽 + 亮边）
d.rectangle([3, 2, 10, 4], fill=BOX_DEEP)
d.line([3, 2, 10, 2], fill=BOX_LIGHT)
d.line([3, 4, 10, 4], fill=BOX_LIGHT)
# 香 字徽记
em = gold_text(u"香", 8, 4)
if em:
    hd.paste(em, (3, 5), em)
else:
    d.rectangle([5, 6, 8, 8], outline=GOLD)
# 侧面 (15,0)-(17,10)
d.rectangle([15, 0, 16, 9], fill=BOX_MID)
d.line([15, 0, 15, 9], fill=BOX_DEEP)
d.line([16, 0, 16, 9], fill=BOX_LIGHT)
# 顶面 (0,11)-(14,13)
d.rectangle([0, 11, 13, 12], fill=BOX_MID)
d.line([0, 11, 13, 11], fill=BOX_LIGHT)
hd.save(os.path.join(BLOCKS, "eggtart_box_handle.png"))

# ============================================================
#  3. 蛋挞贴图  64x64
# ============================================================
tart = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
d = ImageDraw.Draw(tart)

def crust_side(x0, y0, w, h):
    u"""酥皮侧面：竖向酥层"""
    d.rectangle([x0, y0, x0 + w - 1, y0 + h - 1], fill=CRUST)
    for i in range(w):
        if i % 4 == 0:
            d.line([x0 + i, y0, x0 + i, y0 + h - 1], fill=CRUST_LT)
        elif i % 4 == 2:
            d.line([x0 + i, y0, x0 + i, y0 + h - 1], fill=CRUST_DK)
    d.line([x0, y0, x0 + w - 1, y0], fill=CUSTARD)            # 上沿的蛋液
    d.line([x0, y0 + h - 1, x0 + w - 1, y0 + h - 1], fill=CRUST_DP)

# 顶面 (0,0)-(48,8)：酥皮边框 + 焦糖斑蛋液
tx, ty = 0, 0
d.rectangle([tx, ty, tx + 47, ty + 7], fill=CRUST)
d.rectangle([tx + 1, ty + 1, tx + 46, ty + 6], fill=CUSTARD)
rnd = random.Random(7788)
for _ in range(46):                                            # 焦糖斑
    x = rnd.randint(tx + 2, tx + 44)
    y = rnd.randint(ty + 2, ty + 5)
    r = rnd.choice([1, 1, 1, 2])
    col = rnd.choice([CUSTARD_DK, BURN_LT, BURN])
    d.rectangle([x, y, x + r, y + r], fill=col)
for x in range(tx, tx + 48):                                   # 酥皮边缘的层次
    if x % 5 == 0:
        d.point((x, ty), fill=CRUST_DK)
        d.point((x, ty + 7), fill=CRUST_DK)
# 四个面
crust_side(0, 9, 48, 8)     # north
crust_side(0, 18, 48, 8)    # south
# 两端
for ex in (0, 9):
    d.rectangle([ex, 27, ex + 7, 34], fill=CRUST)
    for i in range(8):
        if i % 3 == 0:
            d.line([ex + i, 27, ex + i, 34], fill=CRUST_LT)
        elif i % 3 == 1:
            d.line([ex + i, 27, ex + i, 34], fill=CRUST_DK)
    d.line([ex, 27, ex + 7, 27], fill=CUSTARD)
    d.line([ex, 34, ex + 7, 34], fill=CRUST_DP)
# 底面
d.rectangle([0, 36, 47, 43], fill=CRUST_DK)
for i in range(48):
    if i % 6 == 0:
        d.line([i, 36, i, 43], fill=CRUST_DP)
d.line([0, 36, 47, 36], fill=CRUST)
tart.save(os.path.join(BLOCKS, "eggtart_tart.png"))

# ============================================================
#  4. 物品图标 16x16
# ============================================================
def icon_box():
    im = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle([1, 6, 14, 12], fill=BOX_DARK)                 # 盒身
    d.line([1, 6, 14, 6], fill=BOX_MID)
    d.line([1, 12, 14, 12], fill=BOX_MID)
    d.line([1, 9, 14, 9], fill=GOLD_DARK)
    d.line([2, 8, 13, 8], fill=CRUST)                          # 蛋挞窗口
    d.line([2, 10, 13, 10], fill=GOLD)
    d.rectangle([6, 2, 9, 6], fill=BOX_DARK)                   # 拎手
    d.rectangle([6, 2, 9, 6], outline=BOX_MID)
    d.rectangle([7, 3, 8, 4], fill=BOX_DEEP)
    d.line([1, 11, 14, 11], fill=BOX_LIGHT)
    return im

def icon_tart():
    im = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 6, 15, 12], fill=CRUST)
    d.rectangle([1, 7, 14, 10], fill=CUSTARD)
    rnd = random.Random(31)
    for _ in range(22):
        x = rnd.randint(1, 13)
        y = rnd.randint(7, 10)
        d.point((x, y), fill=rnd.choice([CUSTARD_DK, BURN_LT, BURN]))
    d.line([0, 6, 15, 6], fill=CRUST_LT)
    d.line([0, 12, 15, 12], fill=CRUST_DP)
    return im

def icon_food():
    im = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle([1, 6, 15, 12], fill=CRUST)                    # 长条蛋挞
    d.rectangle([2, 7, 14, 10], fill=CUSTARD)
    rnd = random.Random(515)
    for _ in range(18):
        x = rnd.randint(2, 12)
        y = rnd.randint(7, 10)
        d.point((x, y), fill=rnd.choice([CUSTARD_DK, BURN_LT]))
    d.line([1, 6, 15, 6], fill=CRUST_LT)
    d.line([1, 12, 15, 12], fill=CRUST_DP)
    d.polygon([(12, 6), (15, 6), (15, 12), (12, 12)], fill=(0, 0, 0, 0))   # 咬掉一口
    d.line([12, 6, 12, 12], fill=CRUST_DP)
    d.line([12, 8, 15, 8], fill=0)
    return im

icon_box().save(os.path.join(BLOCKS, "eggtart_box_item.png"))
icon_tart().save(os.path.join(BLOCKS, "eggtart_tart_item.png"))
icon_food().save(os.path.join(ITEMS, "eggtart_long_tart.png"))

# ============================================================
#  5. 两个包的图标
# ============================================================
def pack_icon():
    im = Image.new("RGBA", (128, 128), (18, 14, 18, 255))
    d = ImageDraw.Draw(im)
    for i in range(128):                                        # 柔和底色
        c = 18 + i // 8
        d.line([0, i, 127, i], fill=(c, c - 4, c + 2, 255))
    big_box = icon_box().resize((112, 112), Image.NEAREST)
    im.paste(big_box, (8, 4), big_box)
    big_tart = icon_tart().resize((88, 88), Image.NEAREST)
    im.paste(big_tart, (34, 44), big_tart)
    return im

pack_icon().save(r"C:\Users\Admin（无密码）\Documents\超长蛋挞\EggTartMod\eggTartBehaviorPack\pack_icon.png")
pack_icon().save(r"C:\Users\Admin（无密码）\Documents\超长蛋挞\EggTartMod\eggTartResourcePack\pack_icon.png")

print("done")
for f in sorted(os.listdir(BLOCKS)):
    print("blocks/", f, Image.open(os.path.join(BLOCKS, f)).size)
for f in sorted(os.listdir(ITEMS)):
    print("items/", f, Image.open(os.path.join(ITEMS, f)).size)
