#!/usr/bin/env python3
"""build_lp_meta.py - 以备份的 Super 前 1MiB 为模板, 重建 LP 元数据 (slot 0)
- system_a -> 新 GSI 镜像, 放在 super 尾部空闲区
- vendor_a / vendor_dlkm_a -> 保持原 extent
- product_a / system_ext_a -> 删除 (GSI 的 skip_mount.cfg 会跳过它们)
用法: python build_lp_meta.py <template_1MiB.bin> <gsi_img> <out_1MiB.bin> [--apply-slots 0]
"""
import hashlib, struct, sys, os

LP_METADATA_GEOMETRY_MAGIC = 0x616C4467
LP_METADATA_HEADER_MAGIC = 0x414C5030
SECTOR = 512
HDR_FMT = "<IHHI32sI32s" + "III" * 4   # magic,maj,min,hdr_size,hdr_cksum,tables_size,tables_cksum, 4x(offset,num,entry_size)
HDR_SIZE_10_0 = struct.calcsize(HDR_FMT)  # 128


def parse_geometry(buf, off):
    magic, sz = struct.unpack_from("<II", buf, off)
    cks = buf[off + 8: off + 40]
    max_size, slots, lbs = struct.unpack_from("<III", buf, off + 40)
    assert magic == LP_METADATA_GEOMETRY_MAGIC, hex(magic)
    return dict(struct_size=sz, checksum=cks, metadata_max_size=max_size, slot_count=slots, logical_block_size=lbs)


def parse_meta(blob):
    (magic, maj, mnr, hsz, hck, tsz, tck, po, pn, pe, eo, en, ee, go, gn, ge, bo, bn, be) = struct.unpack_from(HDR_FMT, blob, 0)
    assert magic == LP_METADATA_HEADER_MAGIC, hex(magic)
    base = hsz
    tables = blob[base: base + tsz]
    def rows(o, n, e): return [tables[o + i * e: o + (i + 1) * e] for i in range(n)]
    return dict(major=maj, minor=mnr, header_size=hsz, tables_size=tsz,
                parts=rows(po, pn, pe), extents=rows(eo, en, ee), groups=rows(go, gn, ge), bdevs=rows(bo, bn, be),
                sizes=(pe, ee, ge, be), raw=blob[: base + tsz])


def cstr(b): return b.split(b"\0", 1)[0].decode()


def part_info(p):
    name = cstr(p[:36]); attrs, first, num, grp = struct.unpack_from("<IIII", p, 36)
    return name, attrs, first, num, grp


def ext_info(e):
    ns, tt, td, ts = struct.unpack("<QIQI", e)
    return ns, tt, td, ts


def dump(meta, title):
    print(f"== {title} (v{meta['major']}.{meta['minor']}, hdr={meta['header_size']}, tables={meta['tables_size']}) ==")
    for p in meta["parts"]:
        n, a, f, c, g = part_info(p)
        exts = [ext_info(meta["extents"][f + i]) for i in range(c)]
        print(f"  {n:16s} attr={a} grp={g} extents={[(e[0], e[2]) for e in exts]}")
    for g in meta["groups"]:
        print("  group", cstr(g[:36]), struct.unpack_from("<IQ", g, 36))
    for b in meta["bdevs"]:
        print("  bdev ", struct.unpack_from("<QIIQ", b, 0), cstr(b[24:60]))


def build_meta(tpl, new_parts, new_extents):
    """new_parts: list of (name, attrs, group_idx, [extent bytes])"""
    pe, ee, ge, be = tpl["sizes"]
    parts, exts = b"", b""
    for name, attrs, grp, elist in new_parts:
        first = len(exts) // ee
        parts += name.encode().ljust(36, b"\0") + struct.pack("<IIII", attrs, first, len(elist), grp)
        for e in elist:
            exts += e
    groups = b"".join(tpl["groups"]); bdevs = b"".join(tpl["bdevs"])
    po = 0; eo = po + len(parts); go = eo + len(exts); bo = go + len(groups)
    tables = parts + exts + groups + bdevs
    tck = hashlib.sha256(tables).digest()
    hdr = struct.pack(HDR_FMT, LP_METADATA_HEADER_MAGIC, tpl["major"], tpl["minor"], tpl["header_size"], b"\0" * 32,
                      len(tables), tck,
                      po, len(parts) // pe, pe, eo, len(exts) // ee, ee, go, len(groups) // ge, ge, bo, len(bdevs) // be, be)
    assert len(hdr) == tpl["header_size"] == HDR_SIZE_10_0, (len(hdr), tpl["header_size"])
    hck = hashlib.sha256(hdr).digest()  # 计算时 header_checksum 字段为全 0
    # header_checksum 位于偏移 12 (magic4 + major2 + minor2 + header_size4)
    hdr = hdr[:12] + hck + hdr[44:]
    return hdr + tables


def main():
    tpl_path, gsi_path, out_path = sys.argv[1:4]
    buf = bytearray(open(tpl_path, "rb").read())
    assert len(buf) == 1048576
    geo = parse_geometry(buf, 4096)
    print("geometry:", {k: (v.hex() if isinstance(v, bytes) else v) for k, v in geo.items()})
    mx, nslots = geo["metadata_max_size"], geo["slot_count"]
    prim = lambda s: 4096 + 8192 + s * mx
    back = lambda s: 4096 + 8192 + nslots * mx + s * mx
    metas = {}
    for s in range(nslots):
        blob = bytes(buf[prim(s): prim(s) + mx])
        try:
            metas[s] = parse_meta(blob)
            dump(metas[s], f"slot {s} primary @ {prim(s)}")
        except AssertionError as e:
            print(f"slot {s}: no valid header ({e})")
    tpl = metas[0]
    # --- 取出模板里的 vendor_a / vendor_dlkm_a / group index ---
    byname = {}
    for p in tpl["parts"]:
        n, a, f, c, g = part_info(p)
        byname[n] = (a, g, [tpl["extents"][f + i] for i in range(c)])
    sys_attr, sys_grp, _ = byname["system_a"]
    gsi_sz = os.path.getsize(gsi_path)
    assert gsi_sz % SECTOR == 0
    # 新 system_a 起点: 现有最大 extent 末尾向上取整到 1MiB (2048 sectors)
    end = 0
    for n, (a, g, el) in byname.items():
        for e in el:
            ns, tt, td, ts = ext_info(e); end = max(end, td + ns)
    start = (end + 2047) // 2048 * 2048
    nsec = gsi_sz // SECTOR
    super_sz = struct.unpack_from("<QIIQ", tpl["bdevs"][0], 0)[3]
    assert (start + nsec) * SECTOR <= super_sz, "GSI 放不进 super 尾部"
    print(f"new system_a: start sector {start} (byte {start*SECTOR}, 4K-block {start*SECTOR//4096}), sectors {nsec}, end byte {(start+nsec)*SECTOR}, super={super_sz}")
    new_sys_ext = struct.pack("<QIQI", nsec, 0, start, 0)  # target_type 0 = LP_TARGET_TYPE_LINEAR, source = block device 0
    new_parts = [
        ("system_a", sys_attr, sys_grp, [new_sys_ext]),
        ("vendor_a", byname["vendor_a"][0], byname["vendor_a"][1], byname["vendor_a"][2]),
        ("vendor_dlkm_a", byname["vendor_dlkm_a"][0], byname["vendor_dlkm_a"][1], byname["vendor_dlkm_a"][2]),
    ]
    blob = build_meta(tpl, new_parts, None)
    newmeta = parse_meta(blob.ljust(mx, b"\0"))
    dump(newmeta, "NEW slot 0")
    # group 总量检查
    gmax = struct.unpack_from("<IQ", tpl["groups"][sys_grp], 36)[1]
    tot = sum(ext_info(e)[0] for _, _, _, el in new_parts for e in el) * SECTOR
    print(f"group max {gmax}, new total {tot}, ok={tot <= gmax}")
    assert tot <= gmax
    # --- 写入 slot0 primary + backup ---
    padded = blob.ljust(mx, b"\0")
    buf[prim(0): prim(0) + mx] = padded
    buf[back(0): back(0) + mx] = padded
    open(out_path, "wb").write(bytes(buf))
    print("written", out_path, len(buf), "bytes; md5", hashlib.md5(bytes(buf)).hexdigest())
    print(f"GSI_DD_SEEK_4K={start*SECTOR//4096} GSI_BLOCKS={gsi_sz//4096}")


if __name__ == "__main__":
    main()
