# -*- coding: utf-8 -*-
# 锁血 —— 打包上传包
# 用法：python -X utf8 _打包.py
import io, os, sys, shutil, subprocess, zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
SEVEN = r"D:\MCStudio\ext\7z\7z.exe"
PACKS = ["lockHpBehaviorPack", "lockHpResourcePack"]


def cleanJunk(base):
    for dp, dn, fns in os.walk(base):
        for d in list(dn):
            if d in ("__pycache__", ".git"):
                shutil.rmtree(os.path.join(dp, d), ignore_errors=True)
                dn.remove(d)
        for fn in fns:
            if fn.endswith((".pyc", ".pyo")) or fn.startswith("~$"):
                try:
                    os.remove(os.path.join(dp, fn))
                except Exception:
                    pass


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else u"\u9501\u8840_\u4e0a\u4f20\u5305_\u7b2c\u4e8c\u6b21\u4fee\u6539.zip"
    stage = os.path.join(ROOT, "_stage")
    if os.path.isdir(stage):
        shutil.rmtree(stage, ignore_errors=True)
    os.makedirs(stage)
    for p in PACKS:
        src = os.path.join(ROOT, p)
        if not os.path.isdir(src):
            print("MISSING " + src)
            return 1
        cleanJunk(src)
        shutil.copytree(src, os.path.join(stage, p))
    out = os.path.join(ROOT, name)
    if os.path.isfile(out):
        os.remove(out)
    r = subprocess.run([SEVEN, "a", "-tzip", "-mx=9", out] + PACKS,
                       cwd=stage, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if r.returncode != 0 or not os.path.isfile(out):
        print(r.stdout.decode("utf-8", "ignore"))
        return 1
    print(u"\u6253\u5305\u5b8c\u6210\uff1a%s  (%d \u5b57\u8282)" % (out, os.path.getsize(out)))
    with zipfile.ZipFile(out) as z:
        names = z.namelist()
    print(u"\u5305\u5185 %d \u4e2a\u6587\u4ef6" % len(names))
    for n in sorted(names):
        print("   " + n)
    junk = [x for x in names if "__pycache__" in x or x.endswith(".pyc")]
    if junk:
        print(u"\u53d1\u73b0\u810f\u4e1c\u897f\uff1a", junk[:5])
        return 1
    shutil.rmtree(stage, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
