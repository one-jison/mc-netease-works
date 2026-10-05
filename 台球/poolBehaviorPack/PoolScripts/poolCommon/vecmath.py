# -*- coding: utf-8 -*-
# ============================================================
#  台球 — 二维向量小工具（纯计算，不碰引擎）
# ============================================================
import math


def length(x, y):
    return math.sqrt(x * x + y * y)


def norm(x, y):
    u"""归一化；长度为 0 时给一个安全方向"""
    d = math.sqrt(x * x + y * y)
    if d < 1e-9:
        return (1.0, 0.0)
    return (x / d, y / d)


def dot(ax, ay, bx, by):
    return ax * bx + ay * by


def dist2(ax, ay, bx, by):
    dx = ax - bx
    dy = ay - by
    return dx * dx + dy * dy


def clamp(v, lo, hi):
    if v < lo:
        return lo
    if v > hi:
        return hi
    return v


def point_seg_dist2(px, py, ax, ay, bx, by):
    u"""点 (px,py) 到线段 ab 的最短距离的平方"""
    dx = bx - ax
    dy = by - ay
    ll = dx * dx + dy * dy
    if ll < 1e-12:
        return dist2(px, py, ax, ay)
    t = ((px - ax) * dx + (py - ay) * dy) / ll
    t = clamp(t, 0.0, 1.0)
    cx = ax + dx * t
    cy = ay + dy * t
    return dist2(px, py, cx, cy)


def seg_seg_hit(ax, ay, bx, by, cx, cy, dx, dy):
    u"""线段 ab 和线段 cd 相交返回交点，否则 None"""
    r_x = bx - ax
    r_y = by - ay
    s_x = dx - cx
    s_y = dy - cy
    den = r_x * s_y - r_y * s_x
    if abs(den) < 1e-12:
        return None
    t = ((cx - ax) * s_y - (cy - ay) * s_x) / den
    u = ((cx - ax) * r_y - (cy - ay) * r_x) / den
    if t < 0.0 or t > 1.0 or u < 0.0 or u > 1.0:
        return None
    return (ax + r_x * t, ay + r_y * t)


def ray_circle(ox, oy, dx, dy, cx, cy, r):
    u"""射线和圆求交：返回最近的正向距离，没有交点返回 None"""
    fx = ox - cx
    fy = oy - cy
    b = 2.0 * (fx * dx + fy * dy)
    c = fx * fx + fy * fy - r * r
    disc = b * b - 4.0 * c
    if disc < 0.0:
        return None
    sq = math.sqrt(disc)
    t1 = (-b - sq) * 0.5
    t2 = (-b + sq) * 0.5
    if t1 > 1e-6:
        return t1
    if t2 > 1e-6:
        return t2
    return None


def ray_aabb(ox, oy, dx, dy, x0, y0, x1, y1):
    u"""射线和轴对齐矩形求交：返回最近的正向距离，没有交点返回 None"""
    tmin = -1e30
    tmax = 1e30
    for o, d, lo, hi in ((ox, dx, x0, x1), (oy, dy, y0, y1)):
        if abs(d) < 1e-12:
            if o < lo or o > hi:
                return None
            continue
        t1 = (lo - o) / d
        t2 = (hi - o) / d
        if t1 > t2:
            t1, t2 = t2, t1
        if t1 > tmin:
            tmin = t1
        if t2 < tmax:
            tmax = t2
        if tmin > tmax:
            return None
    if tmax < 1e-6:
        return None
    if tmin > 1e-6:
        return tmin
    return tmax
