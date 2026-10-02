import struct, shutil, hashlib
SRC = r"D:\iplay50_test\dlkm_ip50\lib\modules\sensorhub.ko"
DST = r"D:\ats_build\libpatch\sensorhub_l27.ko"
TARGET = {"sbuf_read", "sbuf_write", "sbuf_set_no_need_wake_lock"}
d = bytearray(open(SRC, "rb").read())
shoff = struct.unpack_from('<Q', d, 0x28)[0]
shentsize, shnum, shstrndx = struct.unpack_from('<HHH', d, 0x3A)
secs = []
for i in range(shnum):
    o = shoff + i * shentsize
    name, typ, flags, addr, off, size = struct.unpack_from('<IIQQQQ', d, o)
    secs.append((name, off, size))
stro = secs[shstrndx][1]
n = 0
for name, off, size in secs:
    nm = bytes(d[stro + name: d.index(b'\0', stro + name)]).decode()
    if nm == '__versions':
        for k in range(0, size, 64):
            sym = bytes(d[off + k + 8: off + k + 64]).split(b'\0')[0].decode()
            if sym in TARGET:
                old = struct.unpack_from('<Q', d, off + k)[0]
                struct.pack_into('<Q', d, off + k, 0)
                print(f"patched {sym}: {old:#x} -> 0"); n += 1
assert n == 3
open(DST, "wb").write(d)
print("written", DST, hashlib.md5(d).hexdigest())
