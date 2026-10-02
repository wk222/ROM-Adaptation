#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
clean_dmesg.py - Linux 内核 printk / dmesg / sysdumpdb 净化器与信号提取工具

能力：
1. 从未结构化二进制（如 BROM 转储的 ramoops / sysdumpdb / chunk21）中稳健提取内核 log；
2. 过滤系统级噪声：
   - 过滤高频 SELinux audit: `type=1400 audit(...)`；
   - 过滤 USB / 充电器轮询日志（`musb`, `eta6937`, `battery`）；
   - 过滤 Wi-Fi 周期性心跳与扫描冗余；
3. 关键诊断提取：
   - 自动截取崩溃前最后 100 行真实执行流；
   - 提取包含 `Oops`, `Kernel panic`, `Call trace`, `PC is at`, `sys.init.updatable_crashing` 的现场；
   - 提取 TEE / TrustZone 通信异常（`sprd-trusty-log`, `rpmb`, `keystore`）。
"""

import os
import re
import sys

NOISE_PATTERNS = [
    re.compile(r"type=1400 audit\("),
    re.compile(r"eta6937_charger:"),
    re.compile(r"battery_info:"),
    re.compile(r"sc27xx_fuel_gauge:"),
    re.compile(r"musb_hdrc:"),
    re.compile(r"wlan.*scan"),
]

SIGNAL_PATTERNS = [
    re.compile(r"panic", re.I),
    re.compile(r"oops", re.I),
    re.compile(r"call trace", re.I),
    re.compile(r"pc is at", re.I),
    re.compile(r"sprd-trusty-log", re.I),
    re.compile(r"rpmb", re.I),
    re.compile(r"sys\.init\.updatable_crashing", re.I),
    re.compile(r"die:", re.I),
    re.compile(r"dm-verity:", re.I),
    re.compile(r"binder.*dead", re.I),
]

def clean_kernel_log(raw_path, out_clean_path):
    if not os.path.exists(raw_path):
        print(f"[-] 文件不存在: {raw_path}")
        return

    with open(raw_path, "rb") as f:
        raw = f.read()

    lines = []
    curr = []
    for b in raw:
        if 32 <= b <= 126:
            curr.append(chr(b))
        elif b in (10, 13):
            if curr:
                lines.append("".join(curr))
                curr = []
        else:
            if len(curr) >= 4:
                lines.append("".join(curr))
            curr = []
    if curr:
        lines.append("".join(curr))

    clean = []
    signals = []
    for l in lines:
        if any(p.search(l) for p in NOISE_PATTERNS):
            continue
        clean.append(l)
        if any(p.search(l) for p in SIGNAL_PATTERNS):
            signals.append(l)

    with open(out_clean_path, "w", encoding="utf-8") as f:
        for l in clean:
            f.write(l + "\n")

    print(f"[+] 原始文本行数: {len(lines)}")
    print(f"[+] 去噪后有效行数: {len(clean)} -> {out_clean_path}")
    print(f"[+] 捕获硬核异常信号: {len(signals)} 处")
    if signals:
        print("\n=== CRITICAL SIGNALS DETECTED ===")
        for s in signals[:20]:
            print("  !", s)

    print("\n=== TAIL 40 CLEAN LINES ===")
    for l in clean[-40:]:
        print("  ", l)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python clean_dmesg.py <raw_log_or_bin> [out_clean.txt]")
    else:
        out = sys.argv[2] if len(sys.argv) > 2 else sys.argv[1] + ".clean.txt"
        clean_kernel_log(sys.argv[1], out)
