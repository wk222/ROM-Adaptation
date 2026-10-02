# DOC_209 LineageOS 21:相机打开导致 SurfaceFlinger 崩溃的根因与修复 / MTP 找不到设备的原因

日期:2026-10-02。接 DOC_208。

## 1. 现象
- 用户反馈:WiFi、蓝牙、触控正常;**相机打不开**;**文件传输(MTP)电脑找不到设备**。

## 2. 相机:根因链(全部有日志证据)
1. Aperture 用 `SurfaceView` 做预览。gralloc4 分配记录:
   `hal_format=IMPL-DEF, mali_format=NV21, usage=CPU_R|GPU_R|HWC|WIDE, size=960x720, name=SurfaceView[...Aperture...]`
   即预览缓冲区是 **NV21(YUV)**,SF 眼里 format=34(IMPLEMENTATION_DEFINED)。
2. Android 14 的 `SkiaRenderEngine::mapExternalTextureBuffer` 在 **threaded Skia(`skiaglthreaded`,默认)** 下,会在缓冲区送达 SF 时**提前**把它映射成 GPU 纹理,即使最终由 HWC 直接显示也一样。A12 的 GLES RenderEngine 没有这个预映射,所以原厂系统没事。
3. 这版 A12 的 Mali-G52 驱动(r34p0)对这块 NV21 缓冲区 `eglCreateImageKHR` 失败:
   `skia: Could not create EGL image, err = (0x3003)`(EGL_BAD_ALLOC)。
4. Skia 的 `AutoBackendTexture` 构造里是 `LOG_ALWAYS_FATAL`:
   `Failed to create a valid texture. [960,720] isProtected:0 isWriteable:0 format:34` → **surfaceflinger SIGABRT**。
   调用栈:`AutoBackendTexture::AutoBackendTexture ← SkiaRenderEngine::mapExternalTextureBuffer ← RenderEngineThreaded::threadMain`。
5. SF 一死,system_server 和 cameraserver 被连带重启,相机 HAL 随后报 `Failed HIDL return status not checked` 也 abort(这是**结果**,不是根因)。
- 表现:点开相机 → 黑屏/界面重启。每次稳定复现(tombstone_07/09/10)。

## 3. 修复
```
debug.renderengine.backend=skiagl     # 非线程版 Skia GL,不做缓冲区预映射
```
- 运行时验证:`setprop debug.renderengine.backend skiagl; setprop ctl.restart surfaceflinger` 后相机预览正常,SF pid 不变,0 个 abort。
- **持久化**:写入 `/data/local.prop`(userdebug 构建 `ro.debuggable=1` 时 init 会加载),重启后 `getprop` 仍为 `skiagl`。
  ```
  printf 'debug.renderengine.backend=skiagl\n' > /data/local.prop
  chmod 644 /data/local.prop; chown root:root /data/local.prop
  ```
- 冷启动后复验:Aperture 启动、SF 稳定、前置拍照成功(1944x2592,均值 119,有真实画面)。

## 4. 验证结果
| 项目 | 结果 |
|---|---|
| 预览(前置) | 正常,SF 稳定 |
| 前置拍照 | 成功,JPEG 内容正常(mean RGB≈119/115/109,stddev≈28/22/22) |
| 后置拍照 | 文件生成(3120x4160)但**全黑(mean=1)**。测试时手机平放,后置镜头被桌面挡住,**不能判定**,需要用户拿起来对着东西拍 |
| 重启后 | `skiagl` 保留,相机仍正常 |

## 5. 注意事项 / 遗留
- `/data/local.prop` 在 **擦除 userdata 后会丢失**,需要重新写入。要做成永久:在 `vendor_a` 的 `l27_camera_ko.rc` 里加 `on early-init` + `setprop debug.renderengine.backend skiagl`(vendor_init 能否设置 `debug_prop` 需实测,未做)。
- 副作用:非线程 RenderEngine 合成性能略低,L27 的 720x1612 影响应该不大,未做性能对比。
- 后置相机实拍、录像、闪光灯、对焦仍待用户验证。

## 6. 文件传输(MTP)找不到设备
- 现象:切到"文件传输"后 `adb devices` 为空,Windows 设备管理器里手机变成 **`ZTE_USB`(类 `ZTE Remote USB`,驱动 `zte_usb.inf` v3.0.7.2,服务 libusbK)**,实例 ID `USB\VID_19D2&PID_0449\VID_1782&PID_4003_98275391416606`,首次安装时间 17:47:57(就是切 MTP 的那一刻)。主板上另一个 USB 设备(VID_048D)也被包成同样的 ZTE_USB。
- 电脑上运行着 `ZTE USBIP`、`ZTE PROCESS Guard` 两个服务。**推断**:这是公司的 USB 管控/重定向软件,拦截了 MTP 模式的设备;adb 模式未被拦。没有管理员权限,也未去改动该软件。
- 手机侧无问题:拔插 USB 后回到默认 adb 模式,adb 恢复。
- 绕行建议(不碰该软件):传文件用 `adb push/pull`;或开 WiFi 调试 / 局域网传输。

## 7. 下一步
1. 用户实拍后置相机(对着有光的物体),确认预览与成像。
2. 若要长期稳定:把 `skiagl` 固化进 vendor rc 或确认 `/data/local.prop` 不会丢。
3. 其余:音频出声、传感器(`dumpsys sensorservice` 无输出)、蓝牙配对、充电。
