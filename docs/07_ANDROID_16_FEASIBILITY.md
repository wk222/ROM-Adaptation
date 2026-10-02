# 展锐 UMS512 平台升级至 Android 16 (Baklava) 全景可行性深度评估

## 1. 硬件架构与计算能力评估

### 1.1 CPU 与指令集架构 (ISA)
- **SoC 芯片**：展锐 UMS512 (SharkL5Pro / Tiger T618 / T610)；
- **CPU 核心**：2 x ARM Cortex-A75 @ 2.0 GHz + 6 x ARM Cortex-A55 @ 1.8 GHz；
- **架构版本**：**ARMv8.2-A (AArch64)**；
- **结论**：完全支持 64 位指令集与 AArch64 ABI，硬件算力与内存寻址能力不存在运行 Android 16 的理论阻碍。

### 1.2 GPU 与图形 API
- **GPU 核心**：ARM Mali-G52 MP2 (Bifrost 架构)；
- **图形驱动**：支持 OpenGL ES 3.2 与 Vulkan 1.1；
- **评估**：能够胜任 Android 14~16 的 RenderEngine (SkiaVulkan/SkiaGL) 合成与 Material You 动态模糊渲染。

---

## 2. 阻碍 Android 16 原生引导的核心平台鸿沟 (Major Blockers)

尽管硬件支持 64 位，但从 Android 12 底模跨越到 Android 16（代号 Baklava，2025/2026），将面临 Android 操作系统历史上最剧烈的底层架构重构：

### 2.1 鸿沟一：内核版本与 eBPF / CO-RE 强制约束
1. **现状**：
   - 当前 Letv L27 官方内核为 **Linux 5.4.161-android12-9-xxx**。
2. **Android 16 要求**：
   - Google 在 Android 14 中彻底放弃对 Linux 4.19 的支持；Android 15 开始逐步限制 Linux 5.4；
   - Android 16 的 Launch GKI 内核基线预计为 **Linux 6.6 或 6.12 LTS**；
   - **关键技术瓶颈：eBPF 网络栈**：
     自 Android 14/15 起，Google 将 Android Netd（网络守护进程）、流量统计与防火墙深度绑定至现代 eBPF 特性（如 BPF RingBuffer、BPF CO-RE - Compile Once Run Everywhere、`bpf_probe_read_kernel` 等）。
     原厂 Linux 5.4.161 若缺少这些 backport 补丁，直接引导高版本系统会导致 `netd`、`system_server` 频繁崩溃闪退，手机无网络、无回环甚至无法完成开机。
3. **破解途径**：
   - 依赖社区 GSI（如 TrebleDroid / phhusson）内置的 BPF 降级/兼容补丁；或基于源码底模（`G:\ROOT\SPRD-stuff` 里的 ums512 kernel-5.4 源码）手工 backport BPF commits 重新编译 boot.img。

### 2.2 鸿沟二：HIDL 体系彻底废弃与 32 位 Camera Provider 绝境
1. **HIDL vs AIDL**：
   - Android 8.0 引入 Treble 时采用 HIDL（硬件接口定义语言）；Google 从 Android 11 开始推进 AIDL HAL；
   - 在 Android 14/15 中，Google 逐步弃用 HIDL；
   - **到了 Android 16，AOSP 系统框架计划彻底移除 `hwservicemanager` 并剥离几乎所有遗留 HIDL 客户端（包括 `android.hardware.camera.provider@2.4`、`audio@6.0`、`graphics.allocator@2.0`）**！
2. **展锐相机闭源栈的致命特性**：
   - 我们的相机 Provider 是 **纯 32 位 ELF 二进制**（`/vendor/bin/hw/android.hardware.camera.provider@2.4-service`）；
   - Android 16 官方镜像倾向于完全剔除 32 位运行时（Pure 64-bit System）；
   - 如果系统框架不包含 32 位库和 `hwservicemanager`，原厂相机服务将彻底无法运行！
3. **破解途径**：
   - 必须使用携带 TrebleDroid 社区 `compat-hidl` 补丁以及保留 32 位 binder 库支持的定制 GSI；或者为展锐相机编写 AIDL 包装器（Wrapper Shim）。

### 2.3 鸿沟三：16KB 页面对齐 (Page Size)
1. **规范演变**：
   - Android 15/16 引入了 16KB 物理页支持以提高性能与内存效率；
2. **影响与对策**：
   - 展锐内核与底层闭源动态库均基于 **4KB 页面** 编译；
   - 只要选用 **4KB Page Size 的 GSI 镜像**，该项要求即不会阻碍运行（社区 GSI 均保留 4KB 传统分支）。

### 2.4 鸿沟四：VNDK (Vendor Native Development Kit) 彻底消亡
- Google 在 Android 15 中已正式移除了 VNDK（Android 12 为 VNDK 31/32）；
- 跨版本 GSI 需要通过 Treble bionic 兼容垫片或者直接动态链接系统 libc。

---

## 3. 全版本升级可行性评估矩阵

| 目标系统版本 | 社区支持度 | 核心阻碍与适配难度 | 预期硬件功能表现 | 可行性评级 |
| :--- | :--- | :--- | :--- | :--- |
| **Android 12 (当前基线)** | 100% (出厂) | 已完全攻克：触屏、声音、Wi-Fi、蓝牙、GNSS、相机出图与对焦全通 | 全功能完美使用 | ⭐⭐⭐⭐⭐ (已达成) |
| **Android 13 (Tiramisu GSI)** | 极度成熟 | VNDK 31/32 原生向后兼容，HIDL 2.4 相机服务无缝对接 | 全功能可用，日常流畅度大幅提升 | ⭐⭐⭐⭐⭐ (99% 可行) |
| **Android 14 (LineageOS 21 / TrebleDroid)** | 高度成熟 | T618 平台已有大量成功案例，需注入特定 surfaceflinger 属性规避掉帧 | 相机、音频、网络均可正常拉起 | ⭐⭐⭐⭐☆ (90% 可行) |
| **Android 15 (VanillaIceCream GSI)** | 演进中 | 需要 TrebleDroid 4KB 镜像与 BPF 绕过补丁，需处理 VNDK 移除兼容 | 基础系统、Wi-Fi、声音正常，相机需 HIDL shim | ⭐⭐⭐☆☆ (75% 可行) |
| **Android 16 (Baklava 预览版/正式版)** | 前沿探索 | 必须解决：① 32 位 Provider 兼容；② HIDL 客户端移除；③ Linux 5.4 BPF 崩溃 | 基础系统能点亮，但高级闭源外设（相机）面临断代挑战 | ⭐⭐☆☆☆ (50% 实验级) |

---

## 4. 总结与落地建议

1. **日常主力使用（最高性价比与稳定性）**：
   - **强烈推荐升级到 Android 14 GSI（如 LineageOS 21 或 crDroid 10 基于 TrebleDroid 底包）**；
   - 既能享受到现代 Android 14 的流畅度、Material 3 视觉和最新的应用生态，又能无缝复用我们已调校成功的 Android 12 Vendor（包括触屏、Wi-Fi、音频、已修补好 LSC/供电的相机栈）。
2. **挑战 Android 16（纯极客技术探索）**：
   - 需待 2025/2026 年 Android 16 正式版源码与 TrebleDroid GSI 稳定释出；
   - 核心任务路线：
     1. 获取带 32-bit Binder 兼容性与 `hwservicemanager` 恢复补丁的 4KB Android 16 GSI；
     2. 若遇网络崩溃，基于 `G:\ROOT\SPRD-stuff` 重新编译包含现代 eBPF 特性的 5.4 内核；
     3. 注入我们专有的 Sparse Super 流式刷入工具链与 VBMeta 签名规范。
