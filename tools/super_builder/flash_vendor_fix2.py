import subprocess, hashlib, sys, time
ADB = r"D:\ADK\platform-tools\adb.exe"
IMG = r"D:\iplay50_test\vendor_s\vendor_a_l27fix2.img"
SEEK4K = 0x22000000 // 4096      # 557056
BLOCKS = 185264                  # 758841344 / 4096

def run(args, t=1800):
    r = subprocess.run([ADB] + args, capture_output=True, text=True, errors="ignore", timeout=t)
    return (r.stdout + r.stderr).strip()
def sh(c, t=1800): return run(["shell", c], t)

h = hashlib.md5()
with open(IMG, "rb") as f:
    while True:
        b = f.read(16 << 20)
        if not b: break
        h.update(b)
host = h.hexdigest(); print("host md5", host)
import os
assert os.path.getsize(IMG) == BLOCKS * 4096

print(sh("id -u; ls -l /dev/block/by-name/super"))
# sanity: current content at vendor_a offset must be an EROFS superblock (magic e2 e1 f5 e0 at +1024)
magic = sh(f"dd if=/dev/block/by-name/super bs=4096 skip={SEEK4K} count=1 2>/dev/null | od -A d -t x1 -j 1024 -N 4")
print("current magic:", magic)
if "e2 e1 f5 e0" not in magic:
    print("!! no erofs magic at vendor_a offset, abort"); sys.exit(2)

print(run(["push", IMG, "/data/local/tmp/vendor_fix2.img"]))
dev = sh("md5sum /data/local/tmp/vendor_fix2.img").split()[0]
print("phone md5", dev)
if dev != host:
    print("!! push mismatch, abort"); sys.exit(3)

print("dd ...")
print(sh(f"dd if=/data/local/tmp/vendor_fix2.img of=/dev/block/by-name/super bs=4096 seek={SEEK4K} count={BLOCKS} conv=notrunc,fsync 2>&1"))
sh("sync; echo 3 > /proc/sys/vm/drop_caches")
rb = sh(f"dd if=/dev/block/by-name/super bs=4096 skip={SEEK4K} count={BLOCKS} 2>/dev/null | md5sum").split()[0]
print("readback md5", rb, "MATCH" if rb == host else "MISMATCH")
if rb != host: sys.exit(4)
print("WRITE_OK")
