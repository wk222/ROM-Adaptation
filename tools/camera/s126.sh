#!/system/bin/sh
# s126.sh - 展锐相机 Provider 零重启热插拔与 HAL 覆盖注入脚本
# 运行环境: 目标真机 root shell (/data/local/tmp/s126.sh)

setenforce 0

# 1. 优雅停止相机上层服务与 Provider
stop cameraserver
am force-stop com.android.camera2
pkill -f camera.provider

for i in 1 2 3 4 5 6 7 8 9 10; do
    pidof android.hardware.camera.provider@2.4-service >/dev/null || break
    sleep 1
done
sleep 2

# 2. 补齐内核模块（防卸载死锁：仅在未加载时 insmod，绝不热 rmmod）
lsmod | grep -q '^sprd_sensor' || insmod /data/local/tmp/L27_sprd_sensor.ko 2>&1
lsmod | grep -q '^sprd_camera' || insmod /data/local/tmp/L27_sprd_camera.ko 2>&1

# 3. 内存文件系统 tmpfs 挂载与动态覆盖
mkdir -p /mnt/camov
mountpoint -q /mnt/camov || mount -t tmpfs -o size=64m tmpfs /mnt/camov
mkdir -p /mnt/camov/l

[ -d /mnt/camov/l/lib ] || cp -a /data/local/tmp/camov/. /mnt/camov/l/
cp -f /data/local/tmp/libpatch/*.so /mnt/camov/l/lib/
chmod 644 /mnt/camov/l/lib/*.so

# 4. Bind-mount 绑定覆盖配置与驱动入口
umount /vendor/etc/sensor_config.xml 2>/dev/null
mount --bind /data/local/tmp/sensor_cfg_real.xml /vendor/etc/sensor_config.xml

umount /vendor/lib/hw/camera.ums512.so 2>/dev/null
mount --bind /mnt/camov/l/lib/hw/camera.ums512.so /vendor/lib/hw/camera.ums512.so

# 5. 启动 Camera Provider 与 Cameraprovider 守护进程
export LD_LIBRARY_PATH=/mnt/camov/l/lib:/vendor/lib
dmesg -c >/dev/null
logcat -c

setsid nohup /vendor/bin/hw/android.hardware.camera.provider@2.4-service </dev/null >/dev/null 2>&1 &
sleep 4
start cameraserver
sleep 3

pidof android.hardware.camera.provider@2.4-service cameraserver
