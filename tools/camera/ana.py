#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ana.py - 拍照样张空间均匀性、色偏与动态范围分析工具
"""

import sys
import numpy as np
from PIL import Image

def analyze_photo(image_path):
    im = Image.open(image_path).convert("RGB")
    im_small = im.resize((520, 390), Image.BOX)
    a = np.asarray(im_small).astype(np.float64)
    lin = (a / 255.0) ** 2.2
    h, w, _ = lin.shape

    def get_region(y0, y1, x0, x1):
        return lin[int(y0 * h):int(y1 * h), int(x0 * w):int(x1 * w)].mean((0, 1))

    # 中心环状参考区与四角边缘区
    ring = np.mean([
        get_region(0.20, 0.35, 0.35, 0.65),
        get_region(0.65, 0.80, 0.35, 0.65),
        get_region(0.35, 0.65, 0.20, 0.35),
        get_region(0.35, 0.65, 0.65, 0.80)
    ], axis=0)

    corners = np.mean([
        get_region(0.00, 0.10, 0.00, 0.10),
        get_region(0.00, 0.10, 0.90, 1.00),
        get_region(0.90, 1.00, 0.00, 0.10),
        get_region(0.90, 1.00, 0.90, 1.00)
    ], axis=0)

    # 中心点
    center = get_region(0.40, 0.60, 0.40, 0.60)

    ratio = corners / np.maximum(ring, 1e-4)
    clip_green = (a[..., 1] > 250).mean()

    # sRGB 均值
    c_srgb = a[int(0.4 * h):int(0.6 * h), int(0.4 * w):int(0.6 * w)].mean((0, 1)).round(1)
    k_srgb = np.mean([
        a[0:int(0.1 * h), 0:int(0.1 * w)].mean((0, 1)),
        a[0:int(0.1 * h), int(0.9 * w):].mean((0, 1)),
        a[int(0.9 * h):, 0:int(0.1 * w)].mean((0, 1)),
        a[int(0.9 * h):, int(0.9 * w):].mean((0, 1))
    ], axis=0).round(1)

    print(f"[{image_path}]")
    print(f"  中心 sRGB: {c_srgb} (G/R: {c_srgb[1]/c_srgb[0]:.2f}, G/B: {c_srgb[1]/c_srgb[2]:.2f})")
    print(f"  四角 sRGB: {k_srgb} (G/R: {k_srgb[1]/k_srgb[0]:.2f}, G/B: {k_srgb[1]/k_srgb[2]:.2f})")
    print(f"  线性角/环比 (R, G, B): {ratio.round(3)}")
    print(f"  中心区域线性亮度 (R, G, B): {center.round(3)}")
    print(f"  高光截断比例 (G > 250): {clip_green * 100:.2f}%")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python ana.py <image1.jpg> [image2.jpg ...]")
    else:
        for f in sys.argv[1:]:
            analyze_photo(f)
