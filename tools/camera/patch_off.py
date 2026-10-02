#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
patch_off.py - 展锐相机传感器驱动关断电压枚举 Thumb 汇编修补工具

原理：
在展锐相机 HAL 驱动的下电流程（_power_off / _power_down）中，编译器内联生成了 Thumb 指令：
    MOVS Rn, #imm8   (编码 0x2000 | (Rn << 8) | imm8)
若新版 HAL 库中使用了 14 (0x0E) 作为下电关断值，而老内核 sprd_sensor.ko 仅认 12 (0x0C)，
则退出相机时下电会返回 -22 错误，导致供电轨常开漏电或下次开机传感器挂死。
本工具精准扫描/修补内联 Thumb 指令中的操作数立即数：0x0E -> 0x0C。
"""

import os
import sys

def patch_thumb_off(so_path, out_path, vaddrs):
    if not os.path.exists(so_path):
        print(f"[-] 文件不存在: {so_path}")
        return False
    d = bytearray(open(so_path, "rb").read())
    count = 0
    for vaddr in vaddrs:
        # 32位 ELF 共享库通常代码基址从 0x1000 开始映射
        file_off = vaddr - 0x1000 if vaddr >= 0x1000 else vaddr
        if file_off >= len(d) - 1:
            print(f"[-] 地址 0x{vaddr:x} 超出文件范围")
            continue
        imm = d[file_off]
        opcode_hi = d[file_off + 1]
        # MOVS R0~R7: 0x20 ~ 0x27
        if imm == 0x0E and (0x20 <= opcode_hi <= 0x27):
            d[file_off] = 0x0C
            count += 1
            print(f"[+] 修补虚拟地址 0x{vaddr:x} (文件偏移 0x{file_off:x}): 0x0E -> 0x0C (MOVS R{opcode_hi - 0x20})")
        else:
            print(f"[!] 跳过 0x{vaddr:x}: 当前字节为 0x{imm:02x}{opcode_hi:02x}，不是合法的 MOVS Rn, #14")
    
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(d)
    print(f"[+] 共完成 {count}/{len(vaddrs)} 处 Thumb 下电指令修补 -> {out_path}")
    return True

if __name__ == "__main__":
    # 内置预设示例
    print("Thumb 关电下电立即数修补工具 (14 -> 12)")
