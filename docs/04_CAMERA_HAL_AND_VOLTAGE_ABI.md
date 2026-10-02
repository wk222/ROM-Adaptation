# 展锐相机 HAL 跨代移植、供电枚举 ABI 不兼容与 Thumb 原位 Patch 技术规范

## 1. 展锐 Android 相机架构与加载流程

在展锐 UMS512 平台下，相机服务由 32 位提供者守护进程拉起：
```text
/vendor/bin/hw/android.hardware.camera.provider@2.4-service (32-bit ELF)
  └── dlopen(/vendor/lib/hw/camera.ums512.so)
        └── dlopen(/vendor/lib/libcamsensor.so)
              ├── 读取 /vendor/etc/sensor_config.xml (匹配 SensorName, SlotId, VCM, TuningName)
              ├── dlopen(/vendor/lib/libsensor_<SensorName>.so)   [如 libsensor_ov13850r2a.so]
              ├── dlopen(/vendor/lib/libvcm_<AfName>.so)          [如 libvcm_dw9714.so]
              ├── dlopen(/vendor/lib/libparam_<TuningName>.so)    [如 libparam_ov13850r2a.so]
              └── dlopen(/vendor/lib/libispalg.so)                [ISP 3A与后处理算法库]
```

---

## 2. 内核与闭源库电压枚举 ABI 断代分析

### 2.1 汇编逆向证据
逆向分析 Letv L27 官方内核模块 `sprd_sensor.ko` 中的核心供电映射函数与数据表 `dword_47D8`：
- **老版本内核 ABI 枚举定义表**：
  ```c
  // index 0 ~ 12 映射为固定微伏值 (uV):
  0: 3800000 uV (3.8V)
  1: 3000000 uV (3.0V)
  2: 2900000 uV (2.9V)
  3: 2800000 uV (2.8V)
  4: 2600000 uV (2.6V)
  5: 2500000 uV (2.5V)
  6: 1800000 uV (1.8V)
  7: 1500000 uV (1.5V)
  8: 1300000 uV (1.3V)
  9: 1200000 uV (1.2V)
  10: 1100000 uV (1.1V)
  11: 1000000 uV (1.0V)
  12: POWER_OFF (彻底下电关断)
  ```
- **核心容错限制**：
  若传入枚举值 `enum_val >= 13`，内核驱动会试图将其视作直接微伏参数：`target_uV = enum_val * 1000`。
  例如传入 `13`，内核请求 Regulator 提供 `13000 uV`（0.013V），供电芯片（PMIC SC2730）因超出有效量程抛出硬件错误，内核返回 `-22 (EINVAL)`，导致传感器上下电立即失败！

### 2.2 跨平台移植冲突
从新版 BSP（如 UMIDIGI G1 Max Android 12）中提取的最新驱动库中：
- 其 `module_info` 结构体定义的电压枚举已变更为新版标准：
  `10` 代表 1.2V，`13` 代表 1.0V，`14` 代表 POWER_OFF。
- 当新版库加载在老内核上时：
  1. `13` 请求 1.0V 数字核心电（DVDD），触发 `-22` 导致 Identify 报错；
  2. 退出相机时，下电调用传入 `14`，同样触发 `-22` 导致关断失败，传感器死锁或严重发热漏电！

---

## 3. 驱动原位精准修补规范 (Zero Kernel Patch)

无需重新编译内核模块，直接在各个 `libsensor_*.so` 中进行白盒原位修补：

### 3.1 供电电压修补（Data Section）
直接修改静态 `module_info` 中的 DVDD / AVDD 字段（4 字节对齐 uint32）：
- **OV13850R2A**（文件偏移 `0x2c4c + 8`）：`13 (0x0D)` -> `9 (0x09)`；
- **Hi-556**（文件偏移 `0x285c + 8`）：`10 (0x0A)` -> `9 (0x09)`。
使用工具：`tools/camera/patch_vdd.py`。

### 3.2 关断下电修补（Text Section Thumb 汇编）
在下电汇编函数 `_power_off` 中，编译器内联生成了操作数立即数：
```assembly
MOVS R0, #14   ; 机器码 0x200E
```
通过 `tools/camera/patch_off.py`，将所有下电分支处的 `0x0E` 批量修正为 `0x0C` (12)：
```assembly
MOVS R0, #12   ; 机器码 0x200C
```
修补后，传感器上下电全部返回 0，电源管理恢复健康。

---

## 4. VCM (对焦马达) I2C 地址对撞
- 展锐官方默认配置中，DW9714 对焦马达驱动库（`libvcm_dw9714.so`）写死的 I2C 从机地址为 `0x0E`；
- 真机硬件 I2C 探测证实，Letv L27 主摄模组上挂载的真实 DW9714 芯片硬件引脚接地，其实际 I2C 响应地址为 **`0x0C`**；
- 在 `libvcm_dw9714.so` 文件偏移 `0x970` 处原地修补：`0x0E` -> `0x0C`，马达成功握手驱动，自动对焦能力 100% 解锁。
