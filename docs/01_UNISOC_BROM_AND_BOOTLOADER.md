# 展锐 UMS512 / Letv L27 BROM 硬件唤醒与引导控制技术规范

## 1. 物理引脚采样机制与汇编级逆向证据

### 1.1 汇编逆向结论（基址 0x9f004180）
对官方 `uboot_a.bin` 的汇编逆向（`sprd_boot_mode_detect` 模块）表明：
- 展锐 UMS512 (SharkL5pro / T610 / T618) 的 Bootloader **仅在冷启动初始化的极短时间窗口（微秒级）**，通过 Memory-Mapped I/O 寄存器采样 GPIO 0x7c 与 0x72（音量加/音量减引脚）以及电源管理芯片（PMIC）的按键状态中断标志。
- 当系统完全断电或黑屏后，电容放电和时钟起振过程伴随复杂的时序抖动。人工手动掐按按键（【音量减 + 电源】或【音量加 + 电源】）的时序误差在百毫秒级别，**根本不可能精准命中这一微秒级采样窗口**。

### 1.2 表现行为
- 在黑屏关机状态下，无论是长按【音量减 + 电源键】还是【音量加 + 电源键】，设备必定滑入：
  1. 直接进入低功耗充电动画（Battery Charging）；
  2. 触发 5~10 秒短震后由于未检测到正确模式而强制断电黑屏；
  3. 跌入启动失败看门狗复位循环。

### 1.3 唯一 100% 可靠的冷机硬件响应铁律
在完全断电冷关机状态下，展锐芯片唯一能在硬件级别无条件放行的唤醒通道是：
> **【先按住手机音量减键不放，然后再插上 USB 数据线连接电脑】**

此时芯片底层固化 BootROM（BROM）引脚被硬件拉低约 5 秒，向宿主机暴露标准 USB 端口：
- VID: `0x1782` (Spreadtrum Communications Inc.)
- PID: `0x4d00` (SPRD U2S Diag / SPRD COM Port)

---

## 2. BROM 握手协议与 FDL 通信管道

### 2.1 通信阶梯
1. **ROM 阶段（BootROM）**：
   - 宿主机下发连接确认帧 `0x7E`，芯片握手响应 `0x7E`；
   - 宿主机下载并跳转至 **FDL1**（Flash Downloader 第一阶段，加载基址通常为 SRAM `0x5500`）；
2. **FDL1 阶段**：
   - FDL1 初始化片上 LPDDR4X 内存控制器与安全看门狗；
   - 宿主机下载 **FDL2**（Flash Downloader 第二阶段，加载基址通常为 DDR `0x9efffe00`）；
3. **FDL2 阶段**：
   - FDL2 具备完整的 eMMC/UFS 驱动、GPT 分区表读写能力与安全擦除指令；
   - 支持通过指令直接拉起 Fastboot (`reboot-bootloader`)、Recovery (`boot-recovery`) 或正常开机 (`poweron` / `cboot`)。

---

## 3. `/misc` 分区 Recovery 循环陷阱与破解

### 3.1 故障成因
当 Android 发生底层服务反复崩溃（如 Keystore2 崩溃、`sys.init.updatable_crashing=1`）、Userdata 分区加密解密死锁或系统 OTA 失败时：
- Android Init 会向 `/misc` 分区（或展锐特有的 `miscdata`）写入 `boot-recovery` 引导控制块（BCB - Bootloader Control Block）；
- 下次冷启时，U-Boot 检测到 BCB 指令，强制拦截正常系统引导，强行跳转 Recovery；
- 若移植系统中 Recovery 缺少对应内核模块、不支持触屏或被替换损坏，系统将表现为 **无限循环开机动画后跌入黑屏重启**。

### 3.2 根治方案
使用 BROM 工具全量写入全 0 纯净 `misc` 与 `metadata` 分区，彻底清空 Recovery 触发标志：
```bash
spd_dump.exe --wait 120 exec_addr 0x3ee8 \
  fdl fdl1-dl.bin 0x5500 \
  fdl fdl2-dl.bin 0x9efffe00 \
  exec \
  w misc stock_clean_misc.bin \
  w metadata stock_clean_metadata.bin \
  reboot
```
此操作 100% 抹平 Recovery 陷阱，引导系统直接进入正常用户空间。
