"""Emit a tiny static aarch64 ELF:  finit <module.ko> [flags]  -> finit_module(fd, "", flags)
flags default 1 (MODULE_INIT_IGNORE_MODVERSIONS). Exit status = low byte of syscall result (0 == ok).
Keeps the module file untouched so its signature stays valid."""
import struct
code_words = []
def emit(w): code_words.append(w)
base = 0x400000
hdr_len = 64 + 56
# program: x1 = argv[1]; openat(AT_FDCWD, argv[1], O_RDONLY); finit_module(fd, "", 1); exit(res)
emit(0xF9400BE1)            # ldr x1,[sp,#16]   (argv[1])
emit(0x92800C60)            # movn x0,#99       (AT_FDCWD = -100)
emit(0xD2800002)            # mov x2,#0
emit(0xD2800708)            # mov x8,#56 (openat)
emit(0xD4000001)            # svc #0
adr_index = len(code_words)
emit(0)                     # adr x1, zero_word  (patched below)
emit(0xD2800022)            # mov x2,#1  (MODULE_INIT_IGNORE_MODVERSIONS)
emit(0xD2802228)            # mov x8,#273 (finit_module)
emit(0xD4000001)            # svc #0
emit(0xD2800BA8)            # mov x8,#93 (exit)
emit(0xD4000001)            # svc #0
zero_index = len(code_words)
emit(0); emit(0)            # zero word area (empty string)
# patch ADR
adr_addr = hdr_len + 4 * adr_index
zero_addr = hdr_len + 4 * zero_index
imm = zero_addr - adr_addr
immlo = imm & 3
immhi = (imm >> 2) & 0x7FFFF
code_words[adr_index] = 0x10000000 | (immlo << 29) | (immhi << 5) | 1
code = b"".join(struct.pack("<I", w) for w in code_words)
total = hdr_len + len(code)
ehdr = b"\x7fELF" + bytes([2, 1, 1, 0]) + b"\0" * 8
ehdr += struct.pack("<HHIQQQIHHHHHH", 2, 183, 1, base + hdr_len, 64, 0, 0, 64, 56, 1, 0, 0, 0)
phdr = struct.pack("<IIQQQQQQ", 1, 5, 0, base, base, total, total, 0x1000)
open(r"D:\ats_build\finit_ign", "wb").write(ehdr + phdr + code)
print("written finit_ign", total, "bytes")
