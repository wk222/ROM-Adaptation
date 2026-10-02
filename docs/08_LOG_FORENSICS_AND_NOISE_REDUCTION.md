# 展锐平台全量黑匣子日志获取、BROM 级提取与增量去噪对撞技术规范

## 1. 日志获取手段全景分类

在 Android 移植与驱动调试过程中，依据系统生命周期阶段，设立四级日志捕获阵列：

| 阶段 | 捕获管道 | 核心数据源 | 适用场景 |
| :--- | :--- | :--- | :--- |
| **Level 1: 用户空间正常运行** | `adb logcat` / `dmesg` | 系统框架、Init、Camera Provider | 驱动加载后功能排查、画质调优 |
| **Level 2: 内核运行但未进系统** | `/sys/fs/pstore/` | `console-ramoops-0`, `dmesg-ramoops-0` | Kernel Panic、看门狗复位后的第一现场保留 |
| **Level 3: Bootloader / U-Boot 阶段** | BROM `spd_dump r uboot_log` | 4MB 物理内存环形缓冲区 `uboot_log` | AVB 验签失败、LCD 初始化、时钟异常 |
| **Level 4: 硬件级死锁 / 异常转储** | BROM `spd_dump r sysdumpdb` | 1MB 专用诊断数据库 `sysdumpdb` | 系统崩溃后由 Bootloader 固化的寄存器与内存摘要 |

---

## 2. BROM 级只读取证规范 (Level 3 & 4)

### 2.1 硬件进入方法（铁律）
在手机完全断电黑屏状态下：
> **【先按住手机音量减键不放，然后再插入 USB 数据线连接电脑】**

暴露端口：VID `0x1782` PID `0x4d00`。

### 2.2 零风险只读回读
通过工具 `tools/forensics_logs/brom_log_session.py` 执行纯只读回读：
```bash
python tools/forensics_logs/brom_log_session.py
```
- 回读 `uboot_log`（4MB）：解码出 Bootloader 全生命周期控制台记录；
- 回读 `misc`（1MB）：精准审计 `0x80C` 槽位元数据（A/B 槽位 tries 剩余尝试计数）；
- 回读 `miscdata`（1MB）：审计展锐特有的出厂引导控制块与 `firstmode` 锁死状态；
- 回读 `sysdumpdb`（1MB）：提取内核死锁时的崩溃堆栈与寄存器快照。

---

## 3. 毫秒级时间戳 U-Boot 增量日志对撞 (Delta Diff)

展锐 U-Boot 控制台包含形如 `[00003120]` 的高精度时间戳。在排查“偶发几秒黑屏闪退”或“不同补丁参数差异”时，单次阅读数万行日志极易迷失。

### 3.1 增量对撞机制 (`tools/forensics_logs/uboot_log_delta_diff.py`)
1. **字符串解码清洗**：消除二进制转储中的内存坏块与无意义空字符；
2. **基线对比（Baseline Diff）**：
   ```bash
   python tools/forensics_logs/uboot_log_delta_diff.py uboot_log_run2.bin uboot_log_baseline.txt
   ```
3. **关键门控过滤**：
   自动提取带有 `avb`, `abort`, `panic`, `elr:`, `esr`, `rpmb`, `firstmode`, `recovery` 标志的关键生命周期行，秒级锁定故障发源点。

---

## 4. 内核 printk / dmesg / ramoops 噪声净化器

### 4.1 典型干扰噪声源
Android 系统在启动阶段会产生大量无害的高频噪声日志，严重淹没真实的故障诱因：
- SELinux audit 告警：`type=1400 audit(...)`（几万行 SELinux 拒绝通常仅为非必要权限警告）；
- 电源管理与充电轮询：`battery_info:`, `eta6937_charger:`, `sc27xx_fuel_gauge:`（每几百毫秒上报一次）；
- USB 状态机探测：`musb_hdrc:`。

### 4.2 净化提取规则 (`tools/forensics_logs/clean_dmesg.py`)
使用净化器执行正则模式过滤，仅保留真正的崩溃上下文（Panic、Oops、Call Trace、TOS 异常、Watchdog 动作），将几万行的混乱日志压缩至最具诊断价值的几十行黄金核心。
