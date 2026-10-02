# ROM适配 (ROM-Adaptation)

> **全栈 Android ROM 逆向移植、底层驱动修补、动态分区重构与引导调试综合工具箱**  
> *基于展锐 UMS512 (SharkL5Pro / Tiger T618 / T610) 平台与 ARM64 Linux 5.4 内核体系的实战沉淀与硬核证据链*

---

## 🎯 仓库定位与核心突破

本项目系统化沉淀了在 Android 跨机型固件底模移植（Donor ROM）、GSI（通用系统镜像）适配、闭源外设（相机/传感器/触屏/音频/RPMB 安全存储）调试过程中攻克的关键核心战役。

### 核心硬核突破一览：
1. **Bootloader 与 BROM 引脚采样铁律**：
   - 汇编逆向证实 U-Boot 仅在微秒级采样物理按键，彻底终结“手动按键进 Recovery/Fastboot”的伪经验，确立冷关机【先按音量减再插线进 BROM】的唯一合法通道。
2. **AVB 2.0 VBMeta `flags=3` 空指针崩溃（ELR: 0）取证**：
   - 深入逆向展锐 U-Boot 崩溃现场（ESR `0x8600000d`），证实 `VERIFICATION_DISABLED` 分支访问未初始化内存导致 CPU 瞬死跳 0，确立官方 Stock VBMeta + 合法 Chained 描述符的唯一拓扑结构。
3. **0.85 秒极速 dm-verity Merkle 哈希树重构引擎**：
   - 纯 Python 流式哈希计算流水线，800MB 镜像计算 < 0.9s，零 RAM 膨胀，支持在 RAW Super 大镜像中原位打标。
4. **Android Sparse (simg) 毫秒级流式 Super 镜像组装器**：
   - 巧妙利用 `DONT_CARE` 块跳过原厂保留逻辑卷，生成体积仅 1~2GB 的 Sparse Super 刷机镜像，彻底杜绝 FDL2 底层下载器 A/B 槽位重定向抹空事故。
5. **展锐相机 HAL 供电枚举 ABI 断代原位修补**：
   - 逆向内核 `dword_47D8` 电压映射表，在不重新编译内核的前提下，通过数据段精准修改（13/10 -> 9）与 Thumb 汇编立即数修补（下电 14 -> 12），恢复闭源相机驱动正常工作。
6. **相机 ISP 镜头阴影校正 (LSC) 通道拓扑反转**：
   - 实测证实展锐 LSC 20x25x4 矩阵的物理通道顺序为 **`[G0, B, R, G1]`**（而非传统 AOSP 的 `[R, Gr, Gb, B]`），终结了越补偿越绿的恶性循环，并构建了基于样张的闭环反求拟合算法。
7. **TrustZone TEE (Trusty OS) RPMB 安全存储死锁原位修复**：
   - 定位 `Addr failure, 65530` 根因（512KB 虚拟 `v_rpmb.txt` 越界），通过 37 字节原位定长无损替换重定向至真实物理块设备 `/dev/mmcblk0rpmb`，攻克卡开机动画绝症。
8. **Android 16 (Baklava) 跨代升级可行性全景评估**：
   - 系统梳理 eBPF 网络栈、HIDL 彻底移除、32 位 Provider 生存策略与 16KB 页面演变。

---

## 📂 仓库目录结构

```text
ROM-Adaptation/
├── README.md                          # 本说明文档
├── docs/                              # 核心技术规范与逆向白皮书
│   ├── 01_UNISOC_BROM_AND_BOOTLOADER.md   # 物理按键微秒采样与 BROM 握手协议
│   ├── 02_AVB_AND_VBMETA_TOPOLOGY.md      # VBMeta flags=3 空指针崩溃与 AVB 拓扑
│   ├── 03_DYNAMIC_PARTITIONS_SUPER.md     # Super 动态分区组装与 Sparse 流式切分
│   ├── 04_CAMERA_HAL_AND_VOLTAGE_ABI.md   # 相机 HAL 跨代移植与 Thumb 汇编原位 Patch
│   ├── 05_CAMERA_ISP_LSC_TUNING.md        # LSC 镜头阴影校正逆向 [G,B,R,G] 与闭环拟合
│   ├── 06_TRUSTY_TEE_RPMB_DEADLOCK.md     # Trusty OS RPMB 死锁剖析与 37 字节原位重定向
│   └── 07_ANDROID_16_FEASIBILITY.md       # Android 16 (Baklava) 升级可行性全景评估
└── tools/                             # 自动化工程工具链
    ├── camera/                            # 相机栈逆向与画质调优
    │   ├── patch_vdd.py                       # 模块供电电压枚举 ABI 原位修补
    │   ├── patch_off.py                       # 关断下电 Thumb MOVS 汇编修补 (14 -> 12)
    │   ├── make_tuning.py                     # ISP 参数注入与多模式 LSC 生成器
    │   ├── make_lsc_fit.py                    # 样张闭环反求 LSC 拟合引擎
    │   ├── ana.py                             # 样张空间均匀性、角环比与色偏分析
    │   ├── shoot.ps1                          # 自动化拍照拉取流水线
    │   └── s126.sh                            # 真机免重启 Camera Provider 热注入脚本
    ├── super_builder/                     # 动态分区重构
    │   ├── build_super_sparse.py              # 标准 Sparse Super 镜像组装器
    │   └── ext4x.py                           # 纯 Python Ext4 正则提取器 (免 WSL/免 Root)
    ├── avb_security/                      # AVB 与 dm-verity
    │   └── avb_hashtree_rebuild.py            # 0.85秒极速 Merkle 树流式重构与原位打标
    ├── brom_unbrick/                      # BROM 引导与救砖
    │   └── brom_reset_misc.py                 # 清理 /misc 分区 Recovery 循环陷阱
    └── tee_rpmb/                          # 安全存储与 TEE
        └── patch_rpmb_proxy.py                # 37 字节定长 RPMB 物理设备原地重定向
```

---

## 🛠️ 核心工具使用示例

### 1. 极速重构分区 Merkle 哈希树 (dm-verity)
```bash
python tools/avb_security/avb_hashtree_rebuild.py \
  --file vendor_a.bin \
  --size 798875648 \
  --salt b709c94771e1b0f5d6e98840d30e40904d5e39483469b99caca985e9c8b9c9cb \
  --patch
```

### 2. 生成绝对防抹空的 Sparse Super 刷机镜像
```bash
python tools/super_builder/build_super_sparse.py \
  super_header_16m.bin \
  system_gsi.img \
  super_sparse.img
```

### 3. Windows 免 WSL 极速提取 Ext4 逻辑卷闭源驱动
```bash
python tools/super_builder/ext4x.py vendor.img out_libs/ "(libcamera|libsensor|tuning|libparam)"
```

### 4. 展锐相机传感器静态供电修补
```bash
# 将 OV13850R2A 的 1.0V DVDD (枚举值 13) 修正为 L27 内核合法的枚举值 9 (1.2V)
python tools/camera/patch_vdd.py libsensor_ov13850r2a.so patched/libsensor_ov13850r2a.so 0x2c54 13 9
```

### 5. 基于实拍白墙样张闭环反求并注入 LSC 表
```bash
python tools/camera/make_lsc_fit.py shot_wall.jpg libparam_s5k3l8xxm3.so libparam_ov13850r2a.so 0xbfe34 0.8 reset
```

---

## 📱 Android 12 至 16 升级路径总览

- **Android 12 (出厂基线)**：全功能 100% 达成（触屏、音频、Wi-Fi、蓝牙、GNSS、相机出图对焦）；
- **Android 13 / 14 (LineageOS 21 / TrebleDroid)**：**90%~99% 可用（强烈推荐主力升级路径）**，无缝复用 Android 12 Vendor，流畅度与现代生态极佳；
- **Android 15 / 16 (Baklava)**：需要攻克 32 位 Camera Provider 兼容、AOSP HIDL 客户端移除以及 Linux 5.4 内核 eBPF / CO-RE backport 等底层鸿沟（详见 `docs/07_ANDROID_16_FEASIBILITY.md`）。

---

## 📜 许可与免责声明
本项目包含的技术文档与自研工具遵循 MIT 开源许可。逆向分析旨在实现硬件资产再利用、设备自救与跨系统兼容性研究，请在遵守当地法律法规的前提下使用。
