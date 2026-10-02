# Android TEE (Trusty OS) 与 RPMB 安全存储死锁排查与原位修复规范

## 1. 故障现象与特征指纹

跨平台移植底模时，最顽固的死锁问题通常表现为：
- **开机动画（Bootanimation）持续流畅播放 3~5 分钟以上不黑屏，但无论等待多久都无法进入桌面向导**；
- 抓取底层内核黑匣子日志（`sprd-trusty-log`），呈现如下典型特征：
  ```text
  sprd-trusty-log: trusty: <   93.216873> write data: Addr failure, 65530
  sprd-trusty-log: trusty: <   93.216902> ss: cal_rpmb_block_size: rpmb write data-size 512 to addr (65530) error, return -2
  sprd-trusty-log: trusty: <   93.217399> read data: Addr failure, 65524
  sprd-trusty-log: trusty: <   93.217419> ss: block_device_tipc_rpmb_init: bad static rpmb size, 65525
  init: Service 'vendor.rpmbproxy' (pid 1362) exited with status 1
  init: process with updatable components 'vendor.rpmbproxy' exited 4 times before boot completed
  init: processing action (sys.init.updatable_crashing=1)
  ```

---

## 2. 核心机理剖析：物理硬件与虚拟文件冲突

### 2.1 硬件真实规格
- 物理闪存：eMMC 5.1 / UFS 带有独立安全 RPMB 分区，出厂由熔丝保护；
- 探查内核与 U-Boot 记录：
  - `uboot_set_rpmb_size: rpmb size 16777216` (16MB = 65,536 个 256 字节扇区)；
  - 减去 Trusty OS 内部保留管理的 11 个安全元数据扇区：\( 65536 - 11 = 65525 \)；
  - 证明 TrustZone 固件期望的是一块合法的 **16MB 硬件 RPMB**！

### 2.2 移植固件的致命配置错配
某些贴牌厂商（或部分二开底模）为了省去安全烧录成本，在 vendor 的 `init.rc` 中配置了虚拟文件代理：
```text
service vendor.rpmbproxy /vendor/bin/sprdstorageproxyd -f rpmb -d /dev/trusty-ipc-dev0 -p /data/vendor/sprd_ss -r /mnt/vendor/productinfo/v_rpmb.txt
```
这里的 `v_rpmb.txt` 是保存在文件系统中的普通文本/二进制文件，实际物理大小仅有 **512 KB（2048 个扇区）**！
当 Trusty 安全世界启动，向安全存储代理发出读取第 65530 号扇区的指令时，存储代理试图在 512KB 文件中寻址，内核 VFS 立即因文件越界抛出 `Addr failure, 65530`，存储代理连续崩溃 4 次触发 Android 系统级看门狗保护（`sys.init.updatable_crashing=1`），引导彻底死锁。

---

## 3. 原位定长无损修补方案 (In-Place Exact-Length Patching)

### 3.1 为什么避免解包重打
Android 12 广泛采用 EROFS（只读增强文件系统）或具有复杂 dm-verity Merkle 树的 EXT4 镜像。解包、修改再重新生成的流程容易造成 SELinux Extended Attributes 丢失、Inode 混乱，且耗时数分钟。

### 3.2 37 字节定长原地重定向
利用 Init RC 脚本在镜像中以未压缩 ASCII 明文存储的特性，在二进制中搜索并精确替换：
```python
OLD_STR = b"-r /mnt/vendor/productinfo/v_rpmb.txt"  # 37 字节
NEW_STR = b"-r /dev/mmcblk0rpmb                  "  # 严格 37 字节 (尾部填充 18 个空格)
assert len(OLD_STR) == len(NEW_STR) == 37
```
通过 `tools/tee_rpmb/patch_rpmb_proxy.py`，直接在 `vendor.img` 或 `super.raw` 中原位打标，存储代理瞬间指向真实硬件块设备 `/dev/mmcblk0rpmb`，死锁迎刃而解，直通桌面向导。
