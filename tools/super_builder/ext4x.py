#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ext4x.py - 纯 Python Ext4 镜像文件高速正则提取器 (免 WSL / 免 Root 挂载)

特性：
1. 依赖纯 Python ext4 解析库，完全运行于原生 Windows / macOS / Linux；
2. 支持正则文件名匹配与流式提取，无需挂载卷，不破坏只读镜像；
3. 专为 Android 逻辑卷 (system.img, vendor.img, product.img) 的闭源库快速抽检取证设计。
"""

import os
import re
import sys
import ext4

def extract_ext4(img_path, out_dir, regex_pattern):
    if not os.path.exists(img_path):
        print(f"[-] 镜像文件不存在: {img_path}")
        return 0
    rx = re.compile(regex_pattern, re.IGNORECASE)
    f = open(img_path, "rb")
    vol = ext4.Volume(f)
    extracted_count = 0
    ft_reg = ext4.EXT4_FT.REG_FILE
    ft_dir = ext4.EXT4_FT.DIR

    def walk_tree(node, current_path):
        nonlocal extracted_count
        try:
            entries = list(node.opendir())
        except Exception as e:
            return
        for ent, ft in entries:
            name = ent.name_str
            if name in (".", ".."):
                continue
            full_path = current_path + "/" + name
            try:
                child = vol.inodes[ent.inode]
            except Exception:
                continue
            if ft == ft_dir:
                walk_tree(child, full_path)
            elif ft == ft_reg and rx.search(full_path):
                dest_file = os.path.join(out_dir, full_path.lstrip("/").replace("/", os.sep))
                os.makedirs(os.path.dirname(dest_file), exist_ok=True)
                try:
                    data = child.open().read()
                except Exception as e:
                    print(f"[-] 读取失败: {full_path} ({e})")
                    continue
                with open(dest_file, "wb") as out_f:
                    out_f.write(data)
                extracted_count += 1
                print(f"[+] 提取: {full_path} ({len(data)} 字节)")

    walk_tree(vol.root, "")
    print(f"[+] 提取完成: 命中 {extracted_count} 个文件 -> {out_dir}")
    return extracted_count

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("用法: python ext4x.py <image.img> <out_dir> <regex_pattern>")
        print("示例: python ext4x.py vendor.img out/ '(libcamera|libsensor|tuning)'")
    else:
        extract_ext4(sys.argv[1], sys.argv[2], sys.argv[3])
