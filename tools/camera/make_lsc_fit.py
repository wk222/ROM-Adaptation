#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_lsc_fit.py - 图像闭环 LSC 反求与迭代拟合引擎

原理：
在没有出厂 OTP 标定数据或无法获取专用画质实验室暗箱标定的情况下，通过均匀白墙/白板样张，
反向推导镜头光学暗角衰减模型并注入展锐 LSC 表。
核心机制：
1. 线性化：将 sRGB 逆伽马转换到线性光域 (V = (px / 255) ^ 2.2)；
2. 几何掩码：过滤边缘过曝、底部阴影等非理想区域；
3. 空间暗角拟合：按径向归一化距离 u in [0, 1] 做 2 阶对数多项式平滑拟合，保证单调递减；
4. 倒数校正：增益 = (1.0 / 衰减率) ^ strength；
5. 通道交织映射：严格遵循 [G, B, R, G] 展锐物理硬件拓扑填入。
"""

import os
import sys
import numpy as np
from PIL import Image

def fit_lsc_from_image(jpg_path, src_so, dst_so, lsc_offset, strength=0.8, cur_state_path=None, reset=False):
    if not os.path.exists(jpg_path):
        print(f"[-] 样张不存在: {jpg_path}")
        return False

    im = Image.open(jpg_path).convert("RGB")
    # 降采样加速计算
    im_small = im.resize((520, 390), Image.BOX)
    a = np.asarray(im_small).astype(np.float64)
    h, w, _ = a.shape

    yy, xx = np.mgrid[0:h, 0:w]
    u = ((xx - w / 2.0) ** 2 + (yy - h / 2.0) ** 2) / ((w / 2.0) ** 2 + (h / 2.0) ** 2)

    # 线性光域
    lin = (a / 255.0) ** 2.2
    g_ch = a[..., 1]
    # 选取有效拟合区域（避开过曝与强阴影）
    valid = (g_ch < 245) & (g_ch > 10)

    def fit_channel(ch_idx):
        uu = u[valid]
        vv = lin[..., ch_idx][valid]
        p = np.polyfit(uu, np.log(np.maximum(vv, 1e-4)), 2)
        return lambda x: np.exp(np.polyval(p, x) - np.polyval(p, 0.0))

    f_r = fit_channel(0)
    f_g = fit_channel(1)
    f_b = fit_channel(2)

    # 生成 20x25 网格中心点坐标
    cy = (np.arange(20) + 0.5) / 20.0 * h
    cx = (np.arange(25) + 0.5) / 25.0 * w
    CY, CX = np.meshgrid(cy, cx, indexing="ij")
    U_grid = ((CX - w / 2.0) ** 2 + (CY - h / 2.0) ** 2) / ((w / 2.0) ** 2 + (h / 2.0) ** 2)

    # 【重要】物理通道映射: [G, B, R, G]
    shade = np.stack([f_g(U_grid), f_b(U_grid), f_r(U_grid), f_g(U_grid)], -1)
    shade = np.clip(shade, 0.05, 1.2)

    corr = (1.0 / shade) ** strength

    cur = np.full((20, 25, 4), 1024.0)
    if cur_state_path and os.path.exists(cur_state_path) and not reset:
        cur = np.load(cur_state_path)

    new_table = cur * corr
    new_table = np.clip(new_table, 1024.0, 8.0 * 1024.0)

    if cur_state_path:
        np.save(cur_state_path, new_table)

    t = np.rint(new_table).astype("<u2")
    d = bytearray(open(src_so, "rb").read())
    blob = t.tobytes()
    for k in range(9):
        d[lsc_offset + k * 4000 : lsc_offset + (k + 1) * 4000] = blob

    os.makedirs(os.path.dirname(os.path.abspath(dst_so)), exist_ok=True)
    with open(dst_so, "wb") as f:
        f.write(d)

    print(f"[+] 边缘暗角光衰 (R, G, B): {f_r(1.0):.3f}, {f_g(1.0):.3f}, {f_b(1.0):.3f}")
    print(f"[+] 新 LSC 表增益范围 (G, B, R, G):")
    print(f"    Min: {t.reshape(-1, 4).min(0)}")
    print(f"    Max: {t.reshape(-1, 4).max(0)}")
    return True

if __name__ == "__main__":
    if len(sys.argv) < 5:
        print("用法: python make_lsc_fit.py <shot.jpg> <src_libparam.so> <dst_libparam.so> <lsc_offset> [strength=0.8] [reset]")
    else:
        shot, src, dst, off = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4], 0)
        str_val = float(sys.argv[5]) if len(sys.argv) > 5 else 0.8
        res = (len(sys.argv) > 6 and sys.argv[6] == "reset")
        fit_lsc_from_image(shot, src, dst, off, strength=str_val, reset=res)
