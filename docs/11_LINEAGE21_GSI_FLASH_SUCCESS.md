# DOC_208 LineageOS 21 (A14 GSI) 刷入 Letv L27 — 成功首启记录

日期:2026-10-02。结论:**LineageOS 21.0-20260918 (phh-treble, arm64_bvN) 在 L27 + iPlay50 A12 vendor 上启动成功**,adb 24 秒上线,`sys.boot_completed=1` 在 49 秒。

## 1. 为什么以前"不开机",这次为什么行
- DOC_69 的失败全部发生在 U-Boot 层(slot B priority 0、firstmode 4 卡住、reboot-recovery),不是 A14 系统本身的问题。
- 这次整个过程在 A12 已能 adb root 的状态下完成,**没有碰 vbmeta、没有改 slot/misc**,`slot_suffix=_a` 保持不变。

## 2. 操作流程(全部可复现,工具在 `ROM_Adaptation/tools/super_builder/`)
1. `build_lp_meta.py <旧元数据1MiB> <GSI.img> <新元数据1MiB>`:
   - GSI 的 system 只有 542MB 放不下,所以把 `system_a` 重定位到 super 尾部空闲区:起始扇区 6002688(字节 3,073,376,256),4,988,680 扇区。
   - 删除 `product_a` / `system_ext_a`(GSI 自带),保留 `vendor_a`(相机烘焙版)和 `vendor_dlkm_a`。
   - 重算 tables sha256 和 header sha256,写入 slot0 主区(12288)与备份区(208896)。
   - 先在手机上用官方 `lpdump <文件>` 解析验证通过再写入。
2. `adb push` GSI → `/data/local/tmp`,**host/phone MD5 一致**(2425f577...)。
3. `dd of=/dev/block/by-name/super bs=4096 seek=750336 count=623585 conv=notrunc,fsync`,回读 MD5 一致。此时目标区在旧布局里是空闲的,旧系统仍可启动。
4. 写入新元数据(主区+备份区各 64KiB),回读 MD5 一致,`lpdump /dev/block/by-name/super` 读出新布局。
5. `adb reboot bootloader` → `fastboot erase userdata`(1.7s)→ `fastboot reboot`。**只擦 userdata,保留 /metadata**。

## 3. 首启实测
| 项目 | 结果 |
|---|---|
| Android / 内核 | 14,`lineage_arm64_bvN-userdebug`,内核 5.4.161 |
| 挂载 | `/` ext4 ro (dm-0),`/vendor` erofs (dm-1),`/data` f2fs (dm-42) |
| SELinux | Enforcing(未做 permissive) |
| 显示 | 720x1612,mAwake=true,背光 120/255 |
| 输入 | `adaptive_ts` 触摸、gpio-keys、sc2730 耳机/振动设备均在 |
| WiFi | wlan0 存在,WiFi HAL running(`getUsableChannels` 报 NOT_SUPPORTED 属无害) |
| 相机 | `Number of camera devices: 2`,provider 2.4 + cameraserver 在跑(拍照待实测) |
| GNSS | gpsd + gnss@2.2 service 在跑 |
| 音频 | AudioOut 线程 4 个,HAL 帧数 960(出声待实测) |
| 振动 | vibrator-service 在跑 |
| adb | 默认 adbd(shell),`adb root` 可用 |
| 蓝牙 | 见下 |

## 4. 已发现问题
### 4.1 蓝牙首启崩溃 `Open: No Bluetooth Address!`
- 原因:`bluetooth@1.1-service.unisoc` 从 `ro.bt.bdaddr_path=/data/vendor/bluetooth/btmac.txt` 读地址;/data 刚清空,第一次读不到就 abort。
- 现状:HAL 重启后自动生成了 `btmac.txt`(`40:45:da:90:8a:2e`,随机生成),之后协议栈到达 `BLE_ON`,HCI 命令正常返回,`dumpsys` 地址有效。
- 遗留:`/proc/bluetooth/sleep/btwrite` 报 incorrect(省电节点,次要);需要实际配对测试确认经典蓝牙。
- 若想固定地址:把原厂地址写入 `/data/vendor/bluetooth/btmac.txt`(owner bluetooth,0600)。

### 4.2 audioserver 启动后重启过一次(`aud_pipe_recv_cmd ret -512`)
- 现状音频线程正常;`vendor.audio-hal-aidl` 等 restart 命令找不到服务只是 GSI 自带 rc 引用了 vendor 里不存在的服务,无害。

### 4.3 sensors 无输出
- `dumpsys sensorservice` 没有列出传感器。A12 下是否有传感器待对比(L27 可能本来就没有)。

## 5. 下一步
1. 用户实测:触摸、**音频出声**、**相机拍照**、WiFi 连接、蓝牙配对、充电、息屏唤醒、重启后是否稳定。
2. 若有问题,优先 `adb logcat -b all` + `dmesg` 抓取,日志落到 `D:\ats_build\`。
3. 把 GSI 刷入流程(`build_lp_meta.py`)与首启结论同步到 GitHub 仓库 ROM-Adaptation。

## 6. 回滚方案(未使用)
- `D:\backup_l27\super_lp_meta_cam1_20261002.bin` 是 A12 + 相机烘焙版的元数据备份(MD5 065d26011fc7d7170566f804192e605a)。
- 回滚 = 把它的前 1MiB 写回 super 起始(手机能进系统用 dd;不能则 BROM:按住音量减再插 USB)。A12 的 system/vendor 数据未被覆盖(GSI 只写了空闲尾部)。
- 注意:userdata 已擦除,回滚后 A12 同样会是新机状态。
