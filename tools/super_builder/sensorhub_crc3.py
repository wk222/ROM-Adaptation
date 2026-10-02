import struct, subprocess
src = open(r"D:\l27_super_build\crc_cmp.py", encoding="utf-8-sig").read().split("vb = allcrc")[0]
ns = {}; exec(src, ns)
ev = ns["elf_versions"]

def abs_crcs(path):
    d = open(path, "rb").read()
    shoff = struct.unpack_from('<Q', d, 0x28)[0]
    shentsize, shnum, shstrndx = struct.unpack_from('<HHH', d, 0x3A)
    secs = []
    for i in range(shnum):
        o = shoff + i * shentsize
        name, typ, flags, addr, off, size, link, info, align, entsize = struct.unpack_from('<IIQQQQIIQQ', d, o)
        secs.append(dict(name=name, typ=typ, off=off, size=size, link=link, entsize=entsize))
    out = {}
    for s in secs:
        if s['typ'] == 2:  # SYMTAB
            strs = secs[s['link']]
            for k in range(0, s['size'], 24):
                st_name, st_info, st_other, st_shndx, st_value, st_size = struct.unpack_from('<IBBHQQ', d, s['off'] + k)
                nm = d[strs['off'] + st_name: d.index(b'\0', strs['off'] + st_name)].decode(errors='ignore')
                if nm.startswith('__crc_'):
                    out[nm[6:]] = st_value & 0xffffffff
    return out

c = abs_crcs(r"D:\l27_super_build\vb_ko\sipc-core.ko")
print("sipc-core exports with crc:", len(c))
for s in ("sbuf_write", "sbuf_read", "sbuf_set_no_need_wake_lock", "sbuf_register_notifier", "smsg_send", "sprd_sysfrt_read", "sprd_systimer_read"):
    print(s, hex(c[s]) if s in c else None)
donor = ev(r"D:\iplay50_test\dlkm_ip50\lib\modules\sensorhub.ko")
print("donor sensorhub imports sbuf:", {k: hex(v) for k, v in donor.items() if k.startswith("sbuf")})

ADB = r"D:\ADK\platform-tools\adb.exe"
def sh(cmd):
    r = subprocess.run([ADB, "shell", cmd], capture_output=True, text=True, errors="ignore", timeout=60)
    return (r.stdout + r.stderr).strip()
sh("dmesg -c >/dev/null")
print(sh("insmod /vendor/lib/modules/sensorhub.ko 2>&1"))
print(sh("dmesg | grep -i -E 'sensorhub|disagrees|Unknown symbol' | head -10 | cut -c1-200"))
