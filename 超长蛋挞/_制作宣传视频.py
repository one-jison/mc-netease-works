# -*- coding: utf-8 -*-
import io, os, json, math, wave, struct, subprocess, random
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import imageio_ffmpeg

HERE = os.path.dirname(os.path.abspath(__file__))
rp = os.path.join(HERE, "EggTartMod", "eggTartResourcePack")

W, H = 1280, 720
FPS = 24
DUR = 26.0
NF = int(DUR * FPS)

def load(rel):
    return np.array(Image.open(os.path.join(rp, rel)).convert("RGBA"), dtype=np.float32)

tex_body = load("textures/blocks/eggtart_box_body.png")
tex_handle = load("textures/blocks/eggtart_box_handle.png")
tex_tart = load("textures/blocks/eggtart_tart.png")
icon_food = Image.open(os.path.join(rp, "textures/items/eggtart_long_tart.png")).convert("RGBA")
icon_boxb = Image.open(os.path.join(rp, "textures/blocks/eggtart_box_item.png")).convert("RGBA")

def font(size):
    for c in (r"C:\Windows\Fonts\msyhbd.ttc", r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf"):
        if os.path.exists(c):
            try:
                return ImageFont.truetype(c, size)
            except Exception:
                pass
    return ImageFont.load_default()

F_HUGE = font(104)
F_BIG = font(64)
F_MID = font(40)
F_SMALL = font(28)

GOLD = (238, 196, 108)
GOLD_S = (255, 226, 160)
CREAM = (245, 233, 214)

def face_corners(o, s, face):
    x0, y0, z0 = o; sx, sy, sz = s
    x1, y1, z1 = x0 + sx, y0 + sy, z0 + sz
    return {
      "up":    [(x0,y1,z0),(x1,y1,z0),(x1,y1,z1),(x0,y1,z1)],
      "down":  [(x0,y0,z0),(x1,y0,z0),(x1,y0,z1),(x0,y0,z1)],
      "north": [(x0,y1,z0),(x1,y1,z0),(x1,y0,z0),(x0,y0,z0)],
      "south": [(x1,y1,z1),(x0,y1,z1),(x0,y0,z1),(x1,y0,z1)],
      "west":  [(x0,y1,z0),(x0,y1,z1),(x0,y0,z1),(x0,y0,z0)],
      "east":  [(x1,y1,z1),(x1,y1,z0),(x1,y0,z0),(x1,y0,z1)],
    }[face]

SHADE = {"up":1.0,"down":0.58,"north":0.97,"south":0.88,"west":0.80,"east":0.80}

def build(model, texlist):
    quads = []
    for bone in model["netease:block_geometry"]["bones"]:
        img = texlist[bone.get("texture", 0)]
        for cube in bone["cubes"]:
            o, s, uv = cube["origin"], cube["size"], cube["uv"]
            for face, spec in uv.items():
                u0, v0 = spec["uv"]; uw, uh = spec["uv_size"]
                if face in ("up", "down"): uw = min(uw, s[0]); uh = min(uh, s[2])
                elif face in ("north", "south"): uw = min(uw, s[0]); uh = min(uh, s[1])
                else: uw = min(uw, s[2]); uh = min(uh, s[1])
                cs = face_corners(o, s, face)
                uvs = [(u0,v0),(u0+uw,v0),(u0+uw,v0+uh),(u0,v0+uh)]
                quads.append((cs, uvs, img, SHADE[face]))
    return quads

box_m = json.loads(io.open(os.path.join(rp, "models/netease_block/eggtart_box.json"), encoding="utf-8").read())
tart_m = json.loads(io.open(os.path.join(rp, "models/netease_block/eggtart_tart.json"), encoding="utf-8").read())
BOX = build(box_m, [tex_body, tex_handle])
TART = build(tart_m, [tex_tart])
BOX_PIV = np.array([8.0, 11.0, 8.0], np.float32)
TART_PIV = np.array([8.0, 4.0, 8.0], np.float32)

EYE = np.array([0.90, 0.78, -1.25], np.float32)
FV = -EYE / np.linalg.norm(EYE)
RV = np.cross(FV, np.array([0., 1., 0.], np.float32)); RV /= np.linalg.norm(RV)
UV = np.cross(RV, FV); RV = -RV

def make_bg():
    yy = np.linspace(0.0, 1.0, H, dtype=np.float32)[:, None]
    top = np.array([30, 19, 24], np.float32); bot = np.array([54, 36, 44], np.float32)
    base = np.empty((H, W, 3), np.float32)
    base[:] = (top * (1 - yy) + bot * yy)[:, None, :]
    gy, gx = np.mgrid[0:H, 0:W].astype(np.float32)
    d = np.sqrt(((gx - W * 0.5) / (W * 0.60)) ** 2 + ((gy - H * 0.46) / (H * 0.72)) ** 2)
    glow = np.clip(1.0 - d, 0, 1) ** 2
    base += glow[..., None] * np.array([66, 48, 20], np.float32)
    vig = np.clip(1.18 - np.sqrt(((gx - W/2)/(W*0.78))**2 + ((gy - H/2)/(H*0.88))**2), 0, 1)
    base *= (0.52 + 0.48 * vig)[..., None]
    rng = np.random.RandomState(11)
    for _ in range(120):
        px, py = rng.randint(2, W-2), rng.randint(2, H-2)
        base[py:py+2, px:px+2] += np.array([48, 38, 16], np.float32)
    return np.clip(base, 0, 255)

BG = make_bg()

def render_layer(quads, pivot, yaw, pitch, scale, cx, cy, tint=1.0, alpha=1.0, off=(0.0, 0.0)):
    ca, sa = math.cos(yaw), math.sin(yaw)
    cb, sb = math.cos(pitch), math.sin(pitch)
    rgb = np.zeros((H, W, 3), np.float32)
    zb = np.full((H, W), 1e9, np.float32)
    def proj_point(p):
        q = np.array(p, np.float32) - pivot
        x = q[0]*ca + q[2]*sa
        z = -q[0]*sa + q[2]*ca
        y = q[1]
        y2 = y*cb - z*sb
        z2 = y*sb + z*cb
        v = np.array([x, y2, z2], np.float32)
        return np.array([cx + (v @ RV)*scale + off[0], cy - (v @ UV)*scale + off[1], v @ FV], np.float32)
    for cs, uvs, tex, shade in quads:
        P = [proj_point(c) for c in cs]
        for tri in ((0,1,2),(0,2,3)):
            a, b, c = P[tri[0]], P[tri[1]], P[tri[2]]
            x0 = int(min(a[0],b[0],c[0])) - 1; x1 = int(max(a[0],b[0],c[0])) + 2
            y0 = int(min(a[1],b[1],c[1])) - 1; y1 = int(max(a[1],b[1],c[1])) + 2
            x0 = max(x0, 0); y0 = max(y0, 0); x1 = min(x1, W); y1 = min(y1, H)
            if x0 >= x1 or y0 >= y1: continue
            gx, gy = np.meshgrid(np.arange(x0, x1, dtype=np.float32), np.arange(y0, y1, dtype=np.float32))
            dx = (b[0]-a[0])*(c[1]-a[1]) - (c[0]-a[0])*(b[1]-a[1])
            if abs(dx) < 1e-9: continue
            w0 = ((b[0]-gx)*(c[1]-gy) - (c[0]-gx)*(b[1]-gy)) / dx
            w1 = ((c[0]-gx)*(a[1]-gy) - (a[0]-gx)*(c[1]-gy)) / dx
            w2 = 1.0 - w0 - w1
            m = (w0 >= -1e-6) & (w1 >= -1e-6) & (w2 >= -1e-6)
            if not m.any(): continue
            zbv = w0*a[2] + w1*b[2] + w2*c[2]
            t0, t1, t2 = uvs[tri[0]], uvs[tri[1]], uvs[tri[2]]
            uu = w0*t0[0] + w1*t1[0] + w2*t2[0]
            vv = w0*t0[1] + w1*t1[1] + w2*t2[1]
            tx = np.clip(uu.astype(np.int32), 0, tex.shape[1]-1)
            ty = np.clip(vv.astype(np.int32), 0, tex.shape[0]-1)
            col = tex[ty, tx, :3] * (shade * tint)
            ly, lx = np.nonzero(m)
            keep = zbv[ly, lx] < zb[ly+y0, lx+x0]
            if not keep.any(): continue
            tyy, txx = ly[keep]+y0, lx[keep]+x0
            rgb[tyy, txx] = col[ly[keep], lx[keep]]
            zb[tyy, txx] = zbv[ly[keep], lx[keep]]
    mask = (zb < 1e8).astype(np.float32) * alpha
    return rgb, mask

def ease(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)

def seg_alpha(t, t0, t1, ramp=0.35):
    if t < t0 - 1e-9 or t > t1 + 1e-9: return 0.0
    return min(1.0, (t - t0) / ramp if t < t0 + ramp else 1.0,
               (t1 - t) / ramp if t > t1 - ramp else 1.0)

def shadow_text(d, xy, s, f, fill, anchor="mm", alpha=1.0):
    x, y = xy
    a = int(255 * alpha)
    if a <= 0: return
    d.text((x + 3, y + 3), s, font=f, fill=(0, 0, 0, int(a * 0.55)), anchor=anchor)
    d.text((x, y), s, font=f, fill=fill + (a,), anchor=anchor)

class Particles(object):
    def __init__(self):
        self.items = []
        self.rng = random.Random(2026)
    def burst(self, x, y, n, spd=340.0, col=(255, 214, 130), size=7, life=0.75):
        for _ in range(n):
            ang = self.rng.random() * math.pi * 2
            v = spd * (0.35 + self.rng.random())
            self.items.append([x, y, math.cos(ang)*v, math.sin(ang)*v - 60, life * (0.6 + self.rng.random()*0.7), col, size])
    def step(self, dt):
        out = []
        for p in self.items:
            p[4] -= dt
            if p[4] <= 0: continue
            p[0] += p[2]*dt; p[1] += p[3]*dt
            p[3] += 520*dt
            out.append(p)
        self.items = out
    def draw(self, d):
        for x, y, vx, vy, life, col, size in self.items:
            a = max(0.0, min(1.0, life * 1.5))
            s = max(1, int(size * (0.4 + 0.6*min(1.0, life*2))))
            d.rectangle([x-s, y-s, x+s, y+s], fill=col + (int(190*a),))

PARTS = Particles()

CRACKS = None
def crack_polys():
    global CRACKS
    if CRACKS: return CRACKS
    rng = random.Random(99)
    out = []
    for _ in range(9):
        x = rng.uniform(0.08, 0.92); y = rng.uniform(0.08, 0.92)
        pts = [(x, y)]
        ang = rng.uniform(0, 6.28)
        for _ in range(rng.randint(2, 4)):
            ang += rng.uniform(-1.1, 1.1)
            L = rng.uniform(0.08, 0.20)
            x = min(0.98, max(0.02, x + math.cos(ang)*L))
            y = min(0.98, max(0.02, y + math.sin(ang)*L))
            pts.append((x, y))
        out.append(pts)
    CRACKS = out
    return out

def bbox_of(quads, pivot, yaw, pitch, scale, cx, cy):
    ca, sa = math.cos(yaw), math.sin(yaw)
    cb, sb = math.cos(pitch), math.sin(pitch)
    xs = []; ys = []
    for cs, _, _, _ in quads:
        for p in cs:
            q = np.array(p, np.float32) - pivot
            x = q[0]*ca + q[2]*sa; z = -q[0]*sa + q[2]*ca; y = q[1]
            y2 = y*cb - z*sb; z2 = y*sb + z*cb
            v = np.array([x, y2, z2], np.float32)
            xs.append(cx + (v @ RV)*scale); ys.append(cy - (v @ UV)*scale)
    return min(xs), min(ys), max(xs), max(ys)

def ground_shadow(frame, quads, pivot, yaw, pitch, scale, cx, cy, off=(0.0, 0.0)):
    x0, y0, x1, y1 = bbox_of(quads, pivot, yaw, pitch, scale, cx + off[0], cy + off[1])
    rx = float(max(20.0, (x1 - x0) * 0.44))
    ry = float(max(7.0, rx * 0.13))
    sx = float((x0 + x1) * 0.5)
    sy = float(y1 - ry * 0.4)
    sh = Image.new("L", (W, H), 0)
    sd = ImageDraw.Draw(sh)
    sd.ellipse([sx - rx, sy - ry, sx + rx, sy + ry], fill=150)
    sh = sh.filter(ImageFilter.GaussianBlur(rx * 0.16 + 4))
    sm = (np.array(sh, np.float32) / 255.0)[..., None]
    frame *= (1.0 - sm * 0.72)
    return frame


def draw_model(frame, quads, pivot, yaw, pitch, scale, cx, cy, tint=1.0, alpha=1.0, off=(0.0,0.0),
               crack=0.0, alpha_arr=None):
    ground_shadow(frame, quads, pivot, yaw, pitch, scale, cx, cy, off)
    rgb, mask = render_layer(quads, pivot, yaw, pitch, scale, cx, cy, tint, alpha, off)
    if alpha_arr is not None:
        mask = mask * alpha_arr
    m = mask[..., None]
    frame *= (1.0 - m)
    frame += rgb * m
    if crack > 0.01:
        x0, y0, x1, y1 = bbox_of(quads, pivot, yaw, pitch, scale, cx + off[0], cy + off[1])
        cw, ch = max(1.0, x1 - x0), max(1.0, y1 - y0)
        cl = Image.new("L", (W, H), 0)
        cd = ImageDraw.Draw(cl)
        n = int(4 + 16 * min(1.0, crack))
        for pts in crack_polys()[:n]:
            pp = [(x0 + px*cw, y0 + py*ch) for px, py in pts]
            cd.line(pp, fill=int(200 * min(1.0, crack)), width=2 + int(2*crack))
        ca = (np.array(cl, np.float32) / 255.0) * mask
        m2 = ca[..., None]
        frame *= (1.0 - m2 * 0.85)
    return frame

def make_frame(t, dt):
        frame = BG.copy()
        flash = 0.0
        CX, CY = 640.0, 400.0

        yaw = 0.0
        pitch = 0.26
        if t < 3.6:
            yaw = math.radians(-28 + 56 * ease(t / 3.4))
            scale = 8.6 + 0.7 * ease((t - 0.4) / 1.2)
            draw_model(frame, BOX, BOX_PIV, yaw, pitch, scale, CX, CY + 26)
        elif t < 8.0:
            yaw = math.radians(28 + 300 * ((t - 3.6) / 4.4))
            draw_model(frame, BOX, BOX_PIV, yaw, pitch, 9.6, CX, CY + 20)
        elif t < 11.6:
            k = (t - 8.0) / 3.6
            shake = 5.0 * ease(k)
            off = (math.sin(t * 46.0) * shake, math.cos(t * 39.0) * shake * 0.7)
            yaw = math.radians(328 + 20 * ease(k))
            draw_model(frame, BOX, BOX_PIV, yaw, pitch, 9.6, CX, CY + 20,
                       tint=1.0 - 0.35 * ease(k), off=off, crack=ease(k))
        elif t < 12.1:
            k = (t - 11.6) / 0.5
            if k < 0.06:
                flash = 1.0
                PARTS.burst(CX, CY + 20, 46, 380.0)
            sc = 9.4 * (0.35 + 0.65 * ease(k / 0.5)) if k > 0.1 else 0.0
            if sc > 0.2:
                draw_model(frame, TART, TART_PIV, math.radians(-25), pitch, sc, CX, CY + 60)
        elif t < 15.4:
            k = (t - 12.1) / 3.3
            yaw = math.radians(-25 + 210 * ease(k))
            draw_model(frame, TART, TART_PIV, yaw, pitch, 9.4, CX, CY + 60)
        elif t < 19.0:
            k = (t - 15.4) / 3.6
            shake = 5.0 * ease(k)
            off = (math.sin(t * 46.0) * shake, math.cos(t * 39.0) * shake * 0.7)
            yaw = math.radians(185 + 20 * ease(k))
            draw_model(frame, TART, TART_PIV, yaw, pitch, 9.4, CX, CY + 60,
                       tint=1.0 - 0.35 * ease(k), off=off, crack=ease(k))
        else:
            if t < 19.06:
                PARTS.burst(CX, CY + 40, 40, 340.0)
                flash = 1.0
            k = min(1.0, (t - 19.0) / 0.45)
            bob = math.sin((t - 19.0) * 2.1) * 7.0
            sc = int(300 * (0.35 + 0.65 * ease(k)))
            if t < 23.0:
                sc = int(330 * (0.35 + 0.65 * ease(k)))
            else:
                sc = int(230 * (0.62 + 0.38 * ease(k)))
            ic = icon_food.resize((max(1, sc), max(1, sc)), Image.NEAREST)
            glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            gd = ImageDraw.Draw(glow)
            rr = sc * 0.85
            for i in range(6):
                gd.ellipse([CX - rr - i*14, CY + 40 - rr - i*14, CX + rr + i*14, CY + 40 + rr + i*14],
                           outline=(255, 208, 120, max(0, 60 - i*10)), width=6)
            frame = frame * (1 - 0.0) + np.array(glow.convert("RGB"), np.float32) * 0.0
            PARTS.step(dt)
            base = Image.fromarray(np.clip(frame, 0, 255).astype(np.uint8))
            base.paste(ic, (int(CX - sc/2), int(CY + 40 + bob - sc/2)), ic)
            frame = np.array(base, np.float32)

        PARTS.step(dt) if t >= 19.0 else PARTS.step(dt)
        img = Image.fromarray(np.clip(frame, 0, 255).astype(np.uint8)).convert("RGBA")
        ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(ov)
        PARTS.draw(d)

        if flash > 0.5:
            d.rectangle([0, 0, W, H], fill=(255, 236, 190, 130))

        a = seg_alpha(t, 0.7, 3.4, 0.5)
        if a > 0:
            shadow_text(d, (640, 128), "超长蛋挞", F_HUGE, GOLD_S, alpha=a)
            shadow_text(d, (640, 214), "网易《我的世界》· 玩法组件", F_SMALL, CREAM, alpha=a)
        a = seg_alpha(t, 3.7, 7.9)
        if a > 0: shadow_text(d, (640, 596), "① 放下包装盒 · 长 3 个方块", F_MID, GOLD, alpha=a)
        a = seg_alpha(t, 8.2, 11.5)
        if a > 0: shadow_text(d, (640, 596), "② 撸掉盒子，原地变成蛋挞", F_MID, GOLD, alpha=a)
        a = seg_alpha(t, 11.9, 15.3)
        if a > 0: shadow_text(d, (640, 596), "③ 金黄酥皮 · 焦糖斑蛋液", F_MID, GOLD, alpha=a)
        a = seg_alpha(t, 15.6, 18.9)
        if a > 0: shadow_text(d, (640, 596), "④ 再撸掉，掉落可食用蛋挞", F_MID, GOLD, alpha=a)
        a = seg_alpha(t, 19.4, 22.9)
        if a > 0: shadow_text(d, (640, 596), "吃掉恢复 10 点饥饿值", F_MID, GOLD, alpha=a)
        a = seg_alpha(t, 23.1, 25.8, 0.5)
        if a > 0:
            shadow_text(d, (640, 128), "超长蛋挞", F_BIG, GOLD_S, alpha=a)
            shadow_text(d, (640, 590), "空手约 3 秒撸掉", F_MID, GOLD, alpha=a)
            shadow_text(d, (640, 646), "手机端 · 电脑端 均可游玩", F_SMALL, CREAM, alpha=a)

        if 8.0 < t < 11.6 or 15.4 < t < 19.0:
            t0 = 8.0 if t < 11.6 else 15.4
            k = min(1.0, (t - t0) / 3.5)
            bx0, bx1, by = 490, 790, 540
            d.rectangle([bx0-2, by-2, bx1+2, by+12], fill=(0, 0, 0, 120))
            d.rectangle([bx0, by, bx0 + (bx1-bx0)*k, by+10], fill=GOLD + (235,))

        if t < 0.7:
            d.rectangle([0, 0, W, H], fill=(0, 0, 0, int(255 * (1 - t/0.7))))
        if t > 25.2:
            d.rectangle([0, 0, W, H], fill=(0, 0, 0, int(255 * (t-25.2)/0.8)))

        return Image.alpha_composite(img, ov).convert("RGB")


def main():
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    out = os.path.join(HERE, "超长蛋挞_宣传视频.mp4")
    cmd = [ff, "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H), "-r", str(FPS),
           "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", out]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            creationflags=0x08000000)
    for fi in range(NF):
        t = fi / float(FPS)
        img = make_frame(t, 1.0 / FPS)
        proc.stdin.write(img.tobytes())
        if fi % 48 == 0:
            print("frame", fi, "/", NF, flush=True)
    proc.stdin.close()
    proc.wait()
    print("video rc", proc.returncode, os.path.exists(out), os.path.getsize(out) if os.path.exists(out) else 0)
    return out


def preview():
    times = [1.6, 5.6, 9.6, 13.4, 17.0, 20.6, 24.6]
    tiles = []
    for tt in times:
        PARTS.items = []
        im = make_frame(tt, 1.0 / FPS)
        tiles.append(im.resize((W // 2, H // 2), Image.LANCZOS))
    sheet = Image.new("RGB", (W // 2 * 2, (H // 2) * 4), (0, 0, 0))
    for i, im in enumerate(tiles):
        sheet.paste(im, ((i % 2) * (W // 2), (i // 2) * (H // 2)))
    p = os.path.join(HERE, "_预览宣传片.png")
    sheet.save(p)
    print("saved", p, sheet.size)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "preview":
        preview()
    else:
        main()
