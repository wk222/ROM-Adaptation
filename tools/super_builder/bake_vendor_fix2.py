"""Bake runtime fixes into vendor_a:
  1. /vendor/etc/audio_route.xml : speaker route also enables SPKL mixer + gain (L27 uses SC2730 internal SPK PA)
  2. /vendor/etc/sensor_config.xml: front camera (slot1) Orientation 270 -> 90
Based on bake_vendor_camera.py packing parameters. Output: vendor_a_l27fix2.img
"""
import os, subprocess, hashlib, sys

VENDOR_ROOT = r"D:\iplay50_test\vendor_s\vendor_a"
CONFIG_DIR = r"D:\iplay50_test\vendor_s\config"
OUT_IMG = r"D:\iplay50_test\vendor_s\vendor_a_l27fix2.img"
MKFS_EROFS = r"D:\tools\erofs-tools\mkfs.erofs.exe"
FSCK_EROFS = r"D:\tools\erofs-tools\fsck.erofs.exe"
MAX_SLOT_SIZE = 767016960

def md5(p): return hashlib.md5(open(p, "rb").read()).hexdigest()

# --- 1. audio_route.xml: take the patched file verified on device
route_dst = os.path.join(VENDOR_ROOT, "etc", "audio_route.xml")
orig_dev = r"D:\ats_build\audio_route_orig.xml"
patched = r"D:\ats_build\audio_route_patched.xml"
print("tree audio_route md5:", md5(route_dst), "| device orig md5:", md5(orig_dev))
if md5(route_dst) != md5(orig_dev) and md5(route_dst) != md5(patched):
    print("!! tree audio_route.xml differs from device original; abort"); sys.exit(2)
open(route_dst, "wb").write(open(patched, "rb").read())
print("audio_route.xml ->", md5(route_dst))

# --- 2. sensor_config.xml front orientation
cfg = os.path.join(VENDOR_ROOT, "etc", "sensor_config.xml")
t = open(cfg, "r", encoding="utf-8", newline="").read()
i = t.index("<SlotId>1</SlotId>")
j = t.index("<Orientation>", i)
k = t.index("</Orientation>", j)
print("front orientation before:", t[j + 13:k])
t = t[:j + 13] + "90" + t[k:]
open(cfg, "w", encoding="utf-8", newline="").write(t)
print("sensor_config.xml updated")

# --- 3. pack
cmd = [MKFS_EROFS, "-zlz4hc", "-T", "0", "-U", "6b39d5e4-16c3-4ff5-bcda-06e1390e7572",
       "--mount-point=/vendor_a",
       f"--fs-config-file={os.path.join(CONFIG_DIR, 'vendor_a_fs_config')}",
       f"--file-contexts={os.path.join(CONFIG_DIR, 'vendor_a_file_contexts')}",
       OUT_IMG, VENDOR_ROOT]
res = subprocess.run(cmd, capture_output=True, text=True, cwd=r"D:\iplay50_test\vendor_s")
print(res.stdout[-800:], res.stderr[-800:])
if res.returncode != 0: sys.exit(1)
sz = os.path.getsize(OUT_IMG)
print("image size", sz, "headroom", MAX_SLOT_SIZE - sz)
assert sz <= MAX_SLOT_SIZE
r = subprocess.run([FSCK_EROFS, OUT_IMG], capture_output=True, text=True)
print("fsck rc", r.returncode, r.stdout[-300:], r.stderr[-300:])
print("md5", md5(OUT_IMG))
