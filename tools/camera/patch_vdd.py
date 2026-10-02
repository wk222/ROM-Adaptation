#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
patch_vdd.py - 展锐相机传感器驱动供电电压枚举 ABI 原位补丁工具

背景与原理：
展锐平台跨 Android 大版本升级（如 A11/A12 到新版平台）时，内核 sprd_sensor.ko 中的电压枚举表
dword_47D8 与厂商闭源 HAL 库（libsensor_*.so）的 module_info 存在严重 ABI 断代：
- 老版本内核 ABI 表：0:3.8V, 1:3.0V, 2:2.9V, 3:2.8V, 4:2.6V, 5:2.5V, 6:1.8V, 7:1.5V, 8:1.3V, 9:1.2V, 10:1.1V, 11:1.0V, 12:OFF (≥13 -> value*1000 µV，导致 -22 EINVAL)
- 新版本驱动库（如 UMIDIGI G1 Max 提取版）：10=1.2V, 13≈1.0V, 14=OFF
本脚本在不修改内核与 libcamsensor 全局入口的前提下，对单个传感器驱动库静态 module_info 结构体进行精准原位修补。
"""

import os
import sys

def patch_sensor_vdd(so_path, out_path, offset, old_val, new_val):
    if not os.path.exists(so_path):
        print(f"[-] 文件不存在: {so_path}")
        return False
    d = bytearray(open(so_path, "rb").read())
    if d[offset] != old_val:
        print(f"[-] 偏移 0x{offset:x} 处期望 0x{old_val:02x}，实际为 0x{d[offset]:02x}，校验失败")
        return False
    d[offset] = new_val
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(d)
    print(f"[+] 成功修补 {os.path.basename(so_path)}: 偏移 0x{offset:x} (0x{old_val:02x} -> 0x{new_val:02x}) -> {out_path}")
    return True

if __name__ == "__main__":
    if len(sys.argv) == 6:
        so, out, off, old_v, new_v = sys.argv[1], sys.argv[2], int(sys.argv[3], 0), int(sys.argv[4], 0), int(sys.argv[5], 0)
        patch_sensor_vdd(so, out, off, old_v, new_v)
    else:
        print("用法: python patch_vdd.py <input.so> <output.so> <offset> <old_val> <new_val>")
        print("示例: python patch_vdd.py libsensor_ov13850r2a.so patched/libsensor_ov13850r2a.so 0x2c54 13 9")
