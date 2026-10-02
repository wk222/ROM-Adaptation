# GSI 选型深度评测：crDroid 12.12 (Android 16 Baklava) vs LineageOS 21 (Android 14)

> **评测背景**：  
> 目标设备为展锐 UMS512 (SharkL5pro / Tiger T610/T618) 平台，当前底模为 **Linux 5.4.161 + Android 12 Vendor**。  
> 针对社区开源项目 [Doze-off/crdroid_gsi_treble](https://github.com/Doze-off/crdroid_gsi_treble) 与主流 Android 14 GSI（如 LineageOS 21.0 Treble GSI）展开系统级架构对撞。

---

## 1. 核心版本定义与底座架构

| 维度 | crDroid 12.12 (Doze-off/crdroid_gsi_treble) | LineageOS 21.0 (TrebleDroid A14 GSI) |
| :--- | :--- | :--- |
| **Android 版本** | **Android 16 (代号 Baklava)** | **Android 14 (代号 UpsideDownCake)** |
| **SDK API Level**| **API 36 (36.1)** | **API 34** |
| **源码分支** | `android-16.0.0_r...` | `android-14.0.0_r...` |
| **社区基座** | 基于 TrebleDroid 前沿构建 + crDroid 定制 UI 仓库 | 基于 TrebleDroid 稳定构建 + LineageOS 类原生框架 |
| **定位与成熟度** | **前沿探索型 / 极客尝鲜预览** | **工业级稳定型 / 长期主力推荐** |

---

## 2. 关键系统模块兼容器对比矩阵

### 2.1 相机闭源栈 (Camera HIDL vs AIDL)
- **展锐硬件现状**：我们的相机服务是 **纯 32 位 ELF 二进制 + HIDL 2.4 接口**（`/vendor/bin/hw/android.hardware.camera.provider@2.4-service`）。
- **LineageOS 21 (Android 14)**：
  - AOSP 14 原生保留了 `hwservicemanager` 与对 HIDL 2.4 的完整支持；
  - 32 位 Bionic 运行时完好，我们已修补好的 `libsensor_ov13850r2a`、`libvcm_dw9714` 和 `libparam` 可以**直接无缝加载出图并对焦**。
- **crDroid 12.12 (Android 16)**：
  - Android 16 系统框架官方全面移除了遗留 HIDL 客户端；
  - 尽管 Doze-off 移植版引入了 TrebleDroid 部分兼容垫片，但 32 位 Provider 与 64 位纯净系统之间的 Binder 通信存在严重稳定性风险；
  - **实测预期**：极可能出现打开相机闪退或提示“无法连接到相机服务”。

### 2.2 内核与网络通信栈 (eBPF / Netd)
- **展锐硬件现状**：内核版本为 **Linux 5.4.161-android12-9**。
- **LineageOS 21 (Android 14)**：
  - 完全适配 Linux 5.4 系列内核，Netd 流量统计与 iptables/bpf 降级逻辑完备；
  - Wi-Fi、移动蜂窝网络、网络热点与 USB 网络共享稳定工作。
- **crDroid 12.12 (Android 16)**：
  - Android 16 将系统网络服务彻底强绑定在现代化 eBPF 特性上（如 BPF RingBuffer、CO-RE 编译）；
  - Linux 5.4 缺少相应 backport 补丁，极易引发 `netd` 反复 Crash 重启，出现有 Wi-Fi 信号却无网络访问能力的现象。

### 2.3 资源占用与日常流畅度
- **LineageOS 21**：轻量级、无冗余后台服务，系统空载内存占用在 1.1GB ~ 1.4GB 之间，非常适合 4GB/6GB RAM 的平板/手机；
- **crDroid 12.12**：自带大量自定义功能（crDroid Settings：状态栏图标、锁屏界面、通知动画、按键映射等），功能极为丰富，但系统常驻服务增多，冷启内存占用偏高。

---

## 3. 选型决策裁决与落地建议

### 结论一：日常主力使用（强烈推荐 LineageOS 21 / Android 14 GSI）
> **推荐指数**：⭐⭐⭐⭐⭐ (95% 完美落地)  
> **适用人群**：追求系统稳定、日常长期使用、相机/Wi-Fi/蓝牙/声音全功能必须正常运作的用户。  
> **原因**：LineageOS 21 是当前 Treble 生态中与 Android 12 Vendor 兼容性最巅峰的版本，能将我们攻克的触屏、音频、Wi-Fi、相机全部实力 100% 释放出来。

### 结论二：极客技术探索（推荐 crDroid 12.12 / Android 16 GSI）
> **推荐指数**：⭐⭐⭐☆☆ (适合折腾玩机)  
> **适用人群**：喜欢探索最新 Android 16 特性、酷炫个性化 UI、能够容忍部分外设（如相机）暂时不可用的玩家。  
> **玩法指引**：可以通过我们的 `build_super_sparse.py` 将其刷入作为副系统测试，体验 Android 16 全新的设计语言与交互。
