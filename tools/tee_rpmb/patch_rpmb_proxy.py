#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
patch_rpmb_proxy.py - Android TEE (Trusty OS) RPMB 死锁原位定长无损修补工具

原理与物理背景：
1. 现象：开机动画持续播放数分钟不黑屏，但死活进不去桌面；
   日志：`Addr failure, 65530` / `bad static rpmb size, 65525` / `sys.init.updatable_crashing=1`
2. 根因：移植底模 vendor 中的 init rc 配置（rpmbserver_*.rc）使用了虚拟 RPMB 文件
   `-r /mnt/vendor/productinfo/v_rpmb.txt` (仅 512KB)，而硬件 eMMC RPMB 是 16MB (65536 扇区)。
   Trusty OS 安全世界探查 65530 扇区时越界崩溃，导致 Keystore2 瘫痪。
3. 修补策略：
   通过纯二进制原位定长（Exact-Length）字节对齐替换，将虚拟文件路径重定向到物理块设备：
   `OLD: -r /mnt/vendor/productinfo/v_rpmb.txt` (37 字节)
   `NEW: -r /dev/mmcblk0rpmb                  ` (严格 37 字节，尾部补充空格)
   无需解包 EROFS/EXT4，毫秒级生效且不破坏任何 Inode、时间戳或 Merkle 几何结构。
"""

import os
import sys

OLD_TARGET = b"-r /mnt/vendor/productinfo/v_rpmb.txt"
NEW_TARGET = b"-r /dev/mmcblk0rpmb                  "

def patch_rpmb_proxy_file(file_path):
    if not os.path.exists(file_path):
        print(f"[-] 文件不存在: {file_path}")
        return False

    assert len(OLD_TARGET) == len(NEW_TARGET) == 37

    with open(file_path, "r+b") as f:
        data = f.read()
        idx = data.find(OLD_TARGET)
        if idx == -1:
            print(f"[!] 在 {file_path} 中未匹配到目标虚拟 RPMB 字符串（可能已被修补或结构不同）")
            return False

        print(f"[+] 命中目标模式，物理偏移: 0x{idx:x}")
        f.seek(idx)
        f.write(NEW_TARGET)
        f.flush()

    print(f"[✓] 成功完成原位定长替换 -> {file_path}")
    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python patch_rpmb_proxy.py <vendor_image_or_super_raw>")
    else:
        patch_rpmb_proxy_file(sys.argv[1])
