#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
brom_reset_misc.py - 展锐平台破除 Recovery 循环陷阱与重置引导状态工具

原理与铁律：
1. 展锐 UMS512 / T610 / T618 平台手机处于关机或死循环状态下，手动长按【音量减+电源】
   或【音量加+电源】必定失败滑入直接充电、黑屏关机或死循环；
2. 救砖与引导模式切换，必须且只能依靠电脑端 BROM 工具下发指令：
   【先按住手机音量减键不放，然后再插上 USB 数据线】，芯片引脚拉低约 5 秒，暴露 BROM (SPRD U2S Diag / COM) 端口；
3. 当系统发生 panic、userdata 加密异常时，Android 会在 /misc 分区（或 miscdata）写入
   "boot-recovery" 指令，导致每次开机强制跳转至 Recovery，若 Recovery 损坏或不支持则死循环；
4. 本工具通过 BROM FDL1/FDL2 极速注入清空 misc 与 metadata 分区，彻底根除 Recovery 陷阱。
"""

import os
import subprocess
import sys

def reset_recovery_trap(spd_dump_exe, fdl1, fdl2, clean_misc=None, clean_meta=None, action="reboot"):
    if not os.path.exists(spd_dump_exe):
        print(f"[-] 找不到 spd_dump: {spd_dump_exe}")
        return False

    cmd = [
        spd_dump_exe,
        "--wait", "120",
        "exec_addr", "0x3ee8",
        "fdl", fdl1, "0x5500",
        "fdl", fdl2, "0x9efffe00",
        "exec"
    ]

    if clean_misc and os.path.exists(clean_misc):
        cmd.extend(["w", "misc", clean_misc])
    else:
        cmd.extend(["e", "misc"])

    if clean_meta and os.path.exists(clean_meta):
        cmd.extend(["w", "metadata", clean_meta])

    cmd.append(action)

    print("=" * 70)
    print("  展锐 UMS512 BROM 破除死循环与引导重置工具")
    print("=" * 70)
    print("【操作指引】")
    print("  1. 手机在完全断电关机状态下；")
    print("  2. 先按住【音量减键】不放，然后插上 USB 数据线；")
    print("  3. 终端打印握手并开始刷写时，立即松开按键。")
    print("=" * 70)

    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for line in iter(p.stdout.readline, ''):
        if line:
            print("  " + line.rstrip(), flush=True)
    p.stdout.close()
    p.wait()
    return p.returncode == 0

if __name__ == "__main__":
    print("BROM 救砖工具模块 - 请配置正确的 FDL1/FDL2 路径调用")
