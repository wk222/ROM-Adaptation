#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
brom_log_session.py - 展锐平台 BROM 握手与全量黑匣子日志回读工具

核心能力：
1. 在黑屏或启动崩溃死锁状态下，通过 BROM 握手下载 FDL1/FDL2；
2. 只读回读以下核心诊断数据：
   - uboot_log (4MB): U-Boot 引导阶段全量控制台输出（包含 AVB 验签、LCD 时钟、电源状态）；
   - misc (1MB): A/B 槽位引导计数器（tries=0/1/6）与 BCB Recovery 陷阱指令；
   - miscdata (1MB): 展锐出厂引导控制块（firstmode/calib 等）；
   - ramoops (256KB): Linux 内核崩溃前最后的 printk 环形缓冲区；
   - sysdumpdb (1MB): 内核异常转储元数据库；
3. 全过程保持纯读操作（Read-Only），绝不擦写任何数据，安全无损取证。
"""

import os
import subprocess
import sys

def dump_brom_logs(spd_dump_exe, fdl1, fdl2, out_dir="logs_dump"):
    os.makedirs(out_dir, exist_ok=True)
    if not os.path.exists(spd_dump_exe):
        print(f"[-] 找不到 spd_dump: {spd_dump_exe}")
        return False

    targets = [
        ("uboot_log", 0x400000, os.path.join(out_dir, "uboot_log.bin")),
        ("misc", 0x100000, os.path.join(out_dir, "misc.bin")),
        ("miscdata", 0x100000, os.path.join(out_dir, "miscdata.bin")),
        ("sysdumpdb", 0x100000, os.path.join(out_dir, "sysdumpdb.bin")),
    ]

    cmd = [
        spd_dump_exe,
        "--wait", "120",
        "exec_addr", "0x3ee8",
        "fdl", fdl1, "0x5500",
        "fdl", fdl2, "0x9efffe00",
        "exec"
    ]

    for part, size, out_f in targets:
        cmd.extend(["r", part, str(size), out_f])

    cmd.append("poweroff")

    print("=" * 70)
    print("  展锐 UMS512 BROM 全量黑匣子只读取证工具")
    print("=" * 70)
    print("【操作指引】")
    print("  1. 手机在完全关机断电状态下；")
    print("  2. 先按住【音量减键】不放，然后再插入 USB 数据线；")
    print("  3. 终端打印握手并开始回读时，即可松开按键。")
    print("=" * 70)

    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for line in iter(p.stdout.readline, ''):
        if line:
            print("  " + line.rstrip(), flush=True)
    p.stdout.close()
    p.wait()
    return p.returncode == 0

if __name__ == "__main__":
    print("BROM 黑匣子提取工具 - 请传入 spd_dump 与 fdl 镜像路径")
