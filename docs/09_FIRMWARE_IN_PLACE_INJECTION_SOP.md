# 固件原位注入、EROFS 重构与 Super 逻辑卷切片无感热刷规范

## 1. 固件修补的三种生命周期层级

在进行驱动修补与系统定制时，根据稳定性和介入深度，设立三级递进流程：

| 层级 | 方式 | 生效时间 | 重启后状态 | 适用场景 |
| :--- | :--- | :--- | :--- | :--- |
| **Level 1: 内存运行时覆盖** | Bind-mount (`mount --bind`) / `LD_LIBRARY_PATH` | 秒级生效 | 恢复出厂状态 | 参数逆向、A/B 测试、ISP 调优 |
| **Level 2: 逻辑卷原位无感热刷** | Root 模式下通过 `dd` 原位切片注入 `/dev/block/by-name/super` | 2~3 秒 | 永久保存 | 驱动库固化、Init rc 配置固化 |
| **Level 3: 全局镜像离线刷写** | BROM / Fastboot 全量 Sparse Super 刷入 | 1~2 分钟 | 永久保存 | 换底层 GSI、整机底层分区重做 |

---

## 2. Level 1: 内存运行时 Bind-Mount 注入法 (热插拔调试)

使用 `tools/camera/s126.sh`：
1. 优雅停止上层守护进程（`stop cameraserver; am force-stop ...`）；
2. 建立 64MB `tmpfs` 内存文件系统；
3. 将带有修补补丁的动态库推送到 tmpfs；
4. 执行 `mount --bind` 覆盖只读的 `/vendor/etc/sensor_config.xml` 和 `/vendor/lib/hw/camera.ums512.so`；
5. 重启 Provider 与 Cameraserver，实现**不重启整机、不改动物理闪存、零砖机风险**的高速闭环测试。

---

## 3. Level 2: 逻辑卷原位无感热刷 (免 BROM 的 Super RAW 切片写入)

当驱动库与配置验证无误后，无需重新进入 BROM 刷写几吉字节的庞大固件，直接在已开机系统下热写入：

### 3.1 扇区寻址与物理对齐
- 在动态分区（Super）中，各逻辑卷按照固定偏移分配：
  - 乐视 Letv L27 6600MB Super 中：`vendor_a` 的绝对物理偏移为 **`544 MiB`**（`0x22000000`）；
  - 槽位最大上限为 `767,016,960` 字节（约 731.48 MB）。

### 3.2 安全三步走 (`tools/firmware_inject/live_dd_super_slice.py`)
1. **预读核验**：
   ```bash
   dd if=/dev/block/by-name/super bs=1M skip=544 count=4 | md5sum
   ```
   核验当前扇区的文件系统特征，确保寻址 100% 正确；
2. **切片覆盖**：
   ```bash
   dd if=/data/local/tmp/vendor_a_patched.img of=/dev/block/by-name/super bs=1M seek=544 conv=notrunc
   ```
3. **回读对比**：
   写入后立即执行 `skip=544 count=4` 回读，MD5 完全对撞通过后重启设备，变更永久生效！

---

## 4. EROFS 逻辑卷规范化重构 (`tools/firmware_inject/repack_erofs_vendor.py`)

展锐 Linux 5.4.161 内核对 EROFS 文件系统具有严格的兼容性约束：
1. **压缩算法**：必须指定 `-zlz4hc`；
2. **时间戳清零**：`-T 0` 保证可重现构建（Reproducible Builds）；
3. **元数据继承**：
   - 必须通过 `--fs-config-file` 注入原始权限文件（保留 UID/GID 与 0755/0644 权限）；
   - 必须通过 `--file-contexts` 注入 SELinux 上下文，防止因 unlabeled 导致应用与服务被内核拒绝访问；
4. **配额门禁**：生成镜像尺寸必须严格小于逻辑分区最大物理配额。
