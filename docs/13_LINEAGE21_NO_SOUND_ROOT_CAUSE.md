# DOC_210 — Lineage 21 (A14 GSI) 手机无声：根因 = HAL 开流时把喇叭功放通路关掉 (2026-10-02)

> 状态：根因已用实机实验证实（手动打开 `SPKL Mixer` 后 PCM 立即恢复前进）。**尚未**由用户听感确认；**尚未**做开机后自动持久化。

## 1. 推翻的旧假设
- 旧假设「AGDSP 死了 / SIPC 不回包」**错误**。`[Audio:SIPC] aud_recv_cmd ... ENODATA` + `aud_smsg_recv cache is empty!`
  只是 **每次发命令前清空接收缓存** 的正常日志；紧随其后 `aud_recv_cmd, ... timeout: 750` 是 DSP 在约 10 ms 内的**正常应答**。
  不要再把 ENODATA 当故障。
- 之前的 `Haven't got right cmd(0x9), got cmd(0x5)` 是我用 `cmd media_session volume` 扰动 HAL 造成的，不是开机自带。

## 2. 实机证据
1. 干净重启后播放：`pcm0p/pcm3p` 状态 RUNNING，但 `hw_ptr` 永远停在 240 / 480，`appl_ptr=3840`（缓冲写满，硬件一帧都没消费）。
2. HAL 线程：`writer` 阻塞在 `do_sys_poll`（等 PCM 腾出空间），HAL 后续被 audioserver TimeCheck 判超时杀掉。
3. 与 DOC_201（A12 有声）的 tinymix 抓取逐项对比（`D:\ats_build\mixer_diff.py`），285 个控件只有 5 个不同：

| 控件 | A12 有声 | Lineage 无声 |
|---|---|---|
| `SPKL Mixer DACLSPKL Switch` | On | **Off** |
| `SPKL Gain SPKL Playback Volume` | 5 | **0** |
| `VBC DAC0 AUD MDG Set` / `DSP MDG Set` | 0 1 | 0 1024 |
| `VBC DAC1 DSP MDG Set` | 0 4 | 0 0 |

4. HAL 日志（logcat 的 `audio_hw_control`）：
   `UPDATE_PARAM_VDG:Music\Handsfree\Playback volme:0` → `UPDATE_PARAM_CODEC_PLAY ... volume:0` →
   `set_sprd_output_devices_param vol_index:0 out_devices:8`。即 HAL 用 **音量索引 0** 去设置喇叭编解码器参数，
   索引 0 在 codec 参数表里 = 喇叭混音器关 + 增益 0。
5. **决定性实验**（`D:\ats_build\audio_exp1.py`）：不重启、不动 HAL，只执行
   `tinymix 'SPKL Mixer DACLSPKL Switch' 1; tinymix 'SPKL Gain SPKL Playback Volume' 5`
   → 1 秒后 `pcm0p hw_ptr 240 → 59440 → 88480`（约 48 kHz 速率前进），HAL 不再卡死，
   且 MDG 值自动回到 `0 1`（与 A12 一致）。

## 3. 因果链（当前最合理解释）
1. A14 `AudioFlinger` 没有把音量通过 Unisoc 期望的路径告诉 HAL（日志里 HAL 永远只收到 `volume:0`，音量调节后也没有新的 `UPDATE_PARAM_CODEC_PLAY`）。
2. HAL 开输出流时用 `vol_index:0` 配置 codec → SPKL 通路 Off、增益 0。
3. codec DAC 没有供电/时钟 → IIS 外部 master 下 VBC FIFO 不被消费 → PCM `hw_ptr` 不走。
4. HAL `writer` 线程持锁阻塞在 `poll`，路由线程等同一把锁 → 死锁，audioserver 被 TimeCheck 杀。

## 4. 下一步（按优先级）
1. 让用户现在播放音乐/铃声试听（当前 SPKL 已被手动打开），确认真的出声。
2. 找 HAL 的音量入口：HAL 里有 `music_volume`、`adev_set_voice_volume`、`set_offload_volume`，但没有看到主输出流的 `set_volume` 日志；
   需要确认 A12 是谁把音量交给 HAL（可能是 Unisoc 魔改的 AudioPolicy/AudioFlinger）。可用 IDA MCP 反编译 `audio.primary.ums512.so` 的 `set_sprd_output_devices_param` 交叉引用。
3. 持久化方案（二选一）：
   - 方案 A：改 vendor `audio_params`（`codec.xml`）里 `Music\Handsfree\Playback` 的索引 0 档位，使其 SPKL 混音器 On、增益 5（需重打包 vendor erofs，写 super 0x22000000，务必同步 fs_config 与 file_contexts）。
   - 方案 B：开机后常驻小服务循环把 `SPKL Mixer`/`SPKL Gain` 保持在 On/5（需处理 SELinux 域，较丑）。
4. 前摄上下颠倒：`Orientation=90` 的运行时 bind mount 实验待用户确认，确认后烘进 vendor `sensor_config.xml`。

## 5. 铁律/教训
- 看到 `ENODATA` 先查它是不是「发命令前清缓存」类的日志，不要当成 DSP 死亡的证据。
- 排查无声先做「与已知有声状态的 tinymix 全量 diff」，一次对比比读几千行 dmesg 快得多。
- 不要用 `cmd media_session volume` 去扰动卡死中的 HAL，会触发 audioserver TimeCheck 重启，污染证据。
- 禁止：把 iPlay50 的 `l_agdsp` 刷进分区（DOC_200 §3.16 已 bootloop）；禁止写任何 `*_ext_sel_v2`（内核 Oops）。
