# DOC_211 — 把喇叭通路与前摄方向烘进 vendor（重启后不丢）(2026-10-02)

## 1. 修正 DOC_210 的根因
DOC_210 推测"音量索引 0 导致 SPKL 关"，**更精确的原因**是：
- vendor 的 `/vendor/etc/audio_route.xml` 里 `<speaker device="0x2">` 这一路（来自 iPlay50 donor）只打开 HPL/HPR 混音器和 `Speaker Function`，
  **没有打开 `SPKL Mixer DACLSPKL Switch`**。L27 硬件的喇叭是 SC2730 内置 SPK PA（DOC_201 §1.4），必须开 SPKL 混音器 codec DAC 才有时钟。
- 路由日志 `OUT DEVICES speaker Route ON` 只设了 HP*/Speaker Function；`set_sprd_output_devices_param` 对 out_devices:8 只设 dacl/hpl/hpr，不设 spkl。
- DAC 通路没时钟 → VBC FIFO 不被消费 → `hw_ptr` 卡死 → HAL writer 阻塞。
- 之前 A12 能出声是因为当时路径里某步（早期手工/预设）开过 SPKL，不是 HAL 自带。

## 2. 修复
`audio_route.xml` 的 speaker 块：
- `on`：在 `Speaker Function` 之前加
  `SPKL Mixer DACLSPKL Switch=1`、`SPKL Gain SPKL Playback Volume=5`
- `off`：加 `SPKL Mixer DACLSPKL Switch=0`

先用 bind mount + 重启 audio HAL 验证（`D:\ats_build\route_patch.py`）：初始 SPKL=Off/0 → 开始播放后 SPKL=On/5，`hw_ptr` 正常前进。
再烘进 vendor。

## 3. 同次烘焙：前摄方向
`/vendor/etc/sensor_config.xml` slot1（hi556, FRONT）`Orientation` 270 → 90（用户确认运行时 90 时前摄正常）。

## 4. 构建与刷写（可复现）
- 打包：`D:\iplay50_test\bake_vendor_fix2.py` → `vendor_s\vendor_a_l27fix2.img`
  758,841,344 B，余量 8,175,616 B，`fsck.erofs` 0 错误，md5 `1b2a7f7229a21b9869b56daa02c99a9f`
  （audio_route.xml 新 md5 `84d7de3275346d70e0a69fffce9a7970`，原 `79bb14bd...`）。
- 刷写：`D:\ats_build\flash_vendor_fix2.py`：adb push → md5 一致 → 检查目标偏移有 EROFS 魔数 → `dd` 写入 super 偏移 0x22000000
  （4K 块 557056，185264 块）→ `drop_caches` 后读回 md5 一致 → `adb reboot`。
- 验证：`D:\ats_build\verify_fix2.py`：重启后 `/proc/mounts` 无 bind；route md5 正确；front Orientation=90；
  空闲时 SPKL=Off/5，播放时 SPKL=On/5，`hw_ptr` 前进，audio HAL/audioserver 未被杀。

## 5. 经验
- 音频路由问题先看 HAL 日志里 `OUT DEVICES xxx Route ON` 后面实际 `Set 'ctl'` 的列表，对照 `audio_route.xml`，
  比盯 DSP/IPC 日志快得多。
- donor 与目标硬件喇叭方案不同时，路由 XML 要按目标硬件补控件。
- 写 vendor 到 super：必须先检查目标偏移有 EROFS 魔数、push 后 md5、写后 `drop_caches` 再读回 md5；写完马上重启。
- 声音/前摄的"临时修复"必须区分运行时与持久化；本次已持久化。

## 6. 仍未处理
- 传感器（`No Sensors on the device`）— 下一步。
- 后摄偏色（需要 L27 原厂 tuning 或白平衡标定）、前摄 tuning 名与传感器不匹配。
- `debug.renderengine.backend=skiagl` 仍只靠 `/data/local.prop`，清数据会丢。
- 有 SIM 卡时的通话/短信/数据未验证；耳机、录音、视频录制未验证。
