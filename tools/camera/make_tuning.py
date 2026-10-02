#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_tuning.py - 展锐相机 ISP 调优参数库 (libparam_*.so) LSC 矩阵生成与注入引擎

核心拓扑说明：
1. 展锐平台 ISP 参数存储在 libparam_<TuningName>.so 中，由 HAL 动态 dlopen。
2. 镜头阴影校正 (LSC / ALSC) 表在 libparam 中的布局：
   - 包含 9 张色温/场景表（D65, D50, TL84, CWF, A, U30, NOON 等）。
   - 每张表规格：20 行 x 25 列 x 4 交叉通道 (uint16_t, 小端序)，单表 4000 字节，总计 36000 字节。
   - 单位增益 (Unity Gain) = 1024。
   - 【重大逆向突破】：4 个通道的物理交织顺序实测为 [G, B, R, G]，而非 AOSP/Bayer 默认的 [R, Gr, Gb, B]！
     若按默认顺序填入，会导致 R/B 的大边缘暗角增益注入进 G 通道，引发严重的四角极绿/死绿故障！
3. 支持模式：
   - unity: 全 1024 纯净单位增益（用于排除 LSC 干扰，基线标定）
   - rad <ch> <gain>: 径向增益注入（用于探查各通道物理映射）
   - ch <ch> <val>: 纯色增益注入
   - rk <table_name>: 从 Rockchip / 开源 ISP JSON (17x17) 双线性插值至 20x25
"""

import json
import os
import sys
import numpy as np

def resize_lsc(a, target_h=20, target_w=25):
    """双线性插值缩放 LSC 矩阵"""
    src_h, src_w, chs = a.shape
    ys = np.linspace(0, src_h - 1, target_h)
    xs = np.linspace(0, src_w - 1, target_w)
    out = np.zeros((target_h, target_w, chs), dtype=np.float64)
    for k in range(chs):
        for i, y in enumerate(ys):
            y0 = int(np.floor(y))
            y1 = min(y0 + 1, src_h - 1)
            fy = y - y0
            for j, x in enumerate(xs):
                x0 = int(np.floor(x))
                x1 = min(x0 + 1, src_w - 1)
                fx = x - x0
                out[i, j, k] = (a[y0, x0, k] * (1 - fx) * (1 - fy) +
                                a[y0, x1, k] * fx * (1 - fy) +
                                a[y1, x0, k] * (1 - fx) * fy +
                                a[y1, x1, k] * fx * fy)
    return out

def build_tuning(src_so, dst_so, lsc_offset, mode, *args):
    if not os.path.exists(src_so):
        print(f"[-] 基模库不存在: {src_so}")
        return False

    d = bytearray(open(src_so, "rb").read())

    if mode == "unity":
        table = np.full((20, 25, 4), 1024, dtype="<u2")
    elif mode == "rad":
        target_ch = int(args[0])
        max_gain = float(args[1])
        yy, xx = np.mgrid[0:20, 0:25]
        u = (((xx - 12.0) / 12.5) ** 2 + ((yy - 9.5) / 10.0) ** 2) / 2.0
        table_f = np.full((20, 25, 4), 1024.0)
        table_f[..., target_ch] = 1024.0 * (1.0 + (max_gain - 1.0) * u)
        table = np.rint(table_f).astype("<u2")
    elif mode == "ch":
        target_ch = int(args[0])
        val = int(args[1])
        table = np.full((20, 25, 4), 1024, dtype="<u2")
        table[..., target_ch] = val
    elif mode == "rk":
        json_path = args[0]
        sub_name = args[1] if len(args) > 1 else "2112x1568_D50_100"
        with open(json_path, "r", encoding="utf-8") as f:
            j = json.load(f)
        tabs = {t["name"]: t for t in j["main_scene"][0]["sub_scene"][0]["scene_isp21"]["lsc_v2"]["tbl"]["tableAll"]}
        t = tabs[sub_name]
        # RK 提取顺序: red, greenR, greenB, blue
        r = np.array(t["lsc_samples_red"]["uCoeff"], dtype=np.float64).reshape(17, 17)
        gr = np.array(t["lsc_samples_greenR"]["uCoeff"], dtype=np.float64).reshape(17, 17)
        gb = np.array(t["lsc_samples_greenB"]["uCoeff"], dtype=np.float64).reshape(17, 17)
        b = np.array(t["lsc_samples_blue"]["uCoeff"], dtype=np.float64).reshape(17, 17)
        # 注意: 映射到展锐 [G, B, R, G]
        g_avg = (gr + gb) / 2.0
        rk_stack = np.stack([g_avg, b, r, g_avg], -1)
        table = np.rint(resize_lsc(rk_stack, 20, 25)).astype("<u2")
    else:
        print(f"[-] 未知模式: {mode}")
        return False

    blob = table.tobytes()
    # 连续覆写 9 张表
    for k in range(9):
        d[lsc_offset + k * 4000 : lsc_offset + (k + 1) * 4000] = blob

    os.makedirs(os.path.dirname(os.path.abspath(dst_so)), exist_ok=True)
    with open(dst_so, "wb") as f:
        f.write(d)
    print(f"[+] 成功写入调优库 {dst_so}: 模式={mode}, 增益范围={table.reshape(-1, 4).min(0)} ~ {table.reshape(-1, 4).max(0)}")
    return True

if __name__ == "__main__":
    if len(sys.argv) < 5:
        print("用法: python make_tuning.py <src_libparam.so> <dst_libparam.so> <lsc_offset_hex> <mode> [args...]")
        print("示例: python make_tuning.py libparam_base.so libparam_ov13850r2a.so 0xbfe34 unity")
    else:
        src, dst, off_str, m = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
        build_tuning(src, dst, int(off_str, 0), m, *sys.argv[5:])
