# Android 动态分区 (Dynamic Partitions / Super.img) 全流程重构与 Sparse 切分规范

## 1. 动态分区物理架构原理

自 Android 10 起引入动态分区（Dynamic Partitions），将物理闪存中的单一 `super` 分区划分为多个弹性逻辑卷：
- `/system` (A/B)
- `/vendor` (A/B)
- `/product` (A/B)
- `/system_ext` (A/B)
- `/vendor_dlkm` (可选)

### 1.1 卷首元数据 (LP Metadata)
- `super` 分区的前 16MB 预留给逻辑分区元数据（LP Metadata Header & Geometry）；
- 存储各逻辑分区的名称、扇区范围（Sector Extents）、群组配额（Group Quota）与槽位后缀（`_a` / `_b`）。

---

## 2. 展锐 FDL2 下载器 A/B 槽位重定向防抹空门控

### 2.1 硬件/下载器潜在陷阱
- 展锐底层下载器（FDL2）在执行写入大容量 `super` 镜像时，若镜像格式为未经对齐的巨大 RAW 镜像（如 6.45GB），下载器会因为内部协议缓冲区溢出或超时发生写入截断；
- 更严重的是，某些二开 FDL2 版本在解析 GPT 分区表与 Slot A/B 状态时，存在槽位重定向 bug，会将写入操作重定向到非预期槽位，导致原厂保留逻辑卷被清零抹空！

### 2.2 解决方案：标准 Android Sparse (simg) 流式切分
利用 Android 官方 Sparse 镜像机制进行防御性组装：
```text
[Chunk 1: RAW]       -> 16MB 卷首元数据 (super_header_16m.bin)
[Chunk 2: DONT_CARE] -> 跳过底层原厂 vendor/product/system_ext (物理保留，绝不抹空)
[Chunk 3: RAW]       -> 精准写入移植目标 GSI (system.img)
[Chunk 4: DONT_CARE] -> 跳过尾部空闲空间直至 6600MB 分区上限
```

### 2.3 核心优势
1. **体积小巧**：仅需传输卷首与目标 GSI 数据，生成的 Sparse 镜像大小从原本 6.5GB 骤降至 1~2GB，传输与刷写耗时大幅缩短；
2. **绝对防抹空**：通过 `DONT_CARE` 块显式告知硬件写入器跳过未变更的物理扇区，100% 保护底层闭源 Vendor/Product 完好无损；
3. **极速组装**：通过本项目提供的 `tools/super_builder/build_super_sparse.py`，组装耗时仅需 **30 毫秒**！

---

## 3. Windows 原生免 WSL Ext4 提取规范

在跨机型提取对比底模（如联想 TB328FU、UMIDIGI G1 Max、Infinix Hot 12 Play、Micromax IN 2B）时，Windows 开发者通常受困于 WSL 挂载权限或云端中转。

本项目集成纯 Python 高性能 Ext4 正则提取引擎 `tools/super_builder/ext4x.py`：
- **无须挂载**：直接解析原始 ext4 镜像 Superblock、Block Group Descriptor 与 Inode Table；
- **正则命中**：一键过滤提取所需闭源驱动库：
  ```bash
  python tools/super_builder/ext4x.py vendor.img out/ "(libcamera|libsensor|tuning|libparam)"
  ```
- **纯 Python 原生跨平台**：零第三方二进制依赖，在 Windows / Linux / macOS 下即开即用。
