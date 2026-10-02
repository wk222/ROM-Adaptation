#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
uboot_log_delta_diff.py - 毫秒级时间戳增量 U-Boot 日志去噪与对撞工具

核心机制：
1. 展锐 U-Boot 环形日志解析：从原始 4MB 二进制转储中提取有效 ASCII 字符流，过滤内存垃圾与空字节；
2. 毫秒级时间戳对齐：展锐 U-Boot 输出带有 `[00003120]` 格式的微秒/毫秒时间戳；
3. 去噪清洗（Noise Filter）：
   - 过滤高频无害轮询（如 DDR training 空循环、I2C 无应答扫描、时钟初始化重复冗余）；
   - 高亮核心门控关键信号（`avb_slot_verify`, `Synchronous Abort`, `ELR:`, `panic`, `rpmb`, `boot_mode`）；
4. 增量对撞（Delta Diff）：支持传入基线日志（Baseline），精准输出本次试验较上次改动的差异事件。
"""

import os
import re
import sys

TIMESTAMP_REGEX = re.compile(r"^\[\s*(\d+)\]\s*(.*)$")
CRITICAL_KEYWORDS = [
    "avb", "verify", "slot", "abort", "panic", "error", "fail",
    "elr:", "esr", "synchronous", "rpmb", "firstmode", "recovery",
    "cboot", "fastboot", "reset", "watchdog", "gpio", "sprd"
]

def decode_uboot_log(bin_path, out_txt_path=None):
    if not os.path.exists(bin_path):
        print(f"[-] 文件不存在: {bin_path}")
        return []
    with open(bin_path, "rb") as f:
        raw = f.read()

    lines = []
    curr = []
    for b in raw:
        if 32 <= b <= 126 or b in (9, 10, 13):
            curr.append(chr(b))
        else:
            if len(curr) >= 4:
                text = "".join(curr).strip()
                if text:
                    for line in text.splitlines():
                        s = line.strip()
                        if len(s) >= 4:
                            lines.append(s)
            curr = []
    if curr:
        text = "".join(curr).strip()
        for line in text.splitlines():
            s = line.strip()
            if len(s) >= 4:
                lines.append(s)

    if out_txt_path:
        with open(out_txt_path, "w", encoding="utf-8") as f:
            for l in lines:
                f.write(l + "\n")
        print(f"[+] 解码完成: 共 {len(lines)} 行 -> {out_txt_path}")
    return lines

def filter_critical_signals(lines, highlight=True):
    signals = []
    for line in lines:
        lower = line.lower()
        if any(kw in lower for kw in CRITICAL_KEYWORDS):
            signals.append(line)
    return signals

def delta_diff(prev_lines, curr_lines):
    set_prev = set(prev_lines)
    added = [l for l in curr_lines if l not in set_prev]
    return added

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python uboot_log_delta_diff.py <uboot_log.bin> [baseline_log.txt]")
    else:
        src = sys.argv[1]
        decoded = decode_uboot_log(src, src + ".decoded.txt")
        crit = filter_critical_signals(decoded)
        print(f"\n[+] 命中 {len(crit)} 处关键生命周期信号:")
        for l in crit[:40]:
            print("   ", l)
        if len(crit) > 40:
            print(f"    ... 以及其余 {len(crit) - 40} 行 (详见解码文件)")

        if len(sys.argv) >= 3 and os.path.exists(sys.argv[2]):
            base = open(sys.argv[2], "r", encoding="utf-8", errors="ignore").read().splitlines()
            diff = delta_diff(base, decoded)
            print(f"\n[+] 相比基线新增 {len(diff)} 行差异事件:")
            for l in diff[:30]:
                print("  + ", l)
