#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
repack_erofs_vendor.py - 展锐/Android 12 EROFS 逻辑卷标准重构工具

核心规范：
1. 展锐 Linux 5.4.161 内核要求 EROFS 必须采用兼容特性标志（`-zlz4hc -T 0`）；
2. 严禁使用最新版 mkfs.erofs 引入的高版本特性（如 16KB 页或高版本 incompat 标志），否则 5.4 内核拒绝挂载；
3. 必须严格遵循出厂元数据配置：
   - `--mount-point=/vendor_a` (匹配挂载点)
   - `--fs-config-file` (保持文件权限与 UID/GID)
   - `--file-contexts` (保持 SELinux 安全上下文，防止 zygote 拒绝执行)
4. 输出尺寸必须受控于动态分区的逻辑卷配额上限（如 767,016,960 字节）。
"""

import os
import subprocess
import sys

def repack_erofs(
    mkfs_bin: str,
    source_dir: str,
    output_img: str,
    fs_config: str,
    file_contexts: str,
    uuid: str = "6b39d5e4-16c3-4ff5-bcda-06e1390e7572",
    mount_point: str = "/vendor_a",
    max_size_bytes: int = 767016960
):
    if not os.path.exists(mkfs_bin):
        print(f"[-] 找不到 mkfs.erofs 二进制: {mkfs_bin}")
        return False
    if not os.path.exists(source_dir):
        print(f"[-] 源码目录不存在: {source_dir}")
        return False

    cmd = [
        mkfs_bin,
        "-zlz4hc",
        "-T", "0",
        "-U", uuid,
        f"--mount-point={mount_point}",
        f"--fs-config-file={fs_config}",
        f"--file-contexts={file_contexts}",
        output_img,
        source_dir
    ]

    print(f"[*] 正在重构 EROFS 镜像: {output_img}")
    print(f"    参数: {' '.join(cmd)}")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"[-] 构建失败:\n{res.stderr}\n{res.stdout}")
        return False

    size = os.path.getsize(output_img)
    print(f"[+] 构建成功: 大小 {size} 字节 ({size / 1024 / 1024:.2f} MB)")
    if size > max_size_bytes:
        print(f"[-] 严重错误: 生成镜像体积超出配额 {max_size_bytes} 字节，无法写入动态分区！")
        return False

    print(f"[✓] 尺寸校验通过 (剩余可用空间: {(max_size_bytes - size) / 1024 / 1024:.2f} MB)")
    return True

if __name__ == "__main__":
    if len(sys.argv) < 6:
        print("用法: python repack_erofs_vendor.py <mkfs.erofs_exe> <source_dir> <output.img> <fs_config> <file_contexts>")
    else:
        repack_erofs(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
