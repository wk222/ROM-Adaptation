param(
    [string]$tag = "test",
    [string]$tuning = "ov13850r2a",
    [string]$bypass = "0"
)

$adb = 'D:\ADK\platform-tools\adb.exe'

# 1. 动态替换并推送 sensor_config.xml
if ($tuning) {
    $xml_content = [IO.File]::ReadAllText("D:\sensor_cfg_real.xml")
    $xml_content = [regex]::Replace($xml_content, '<TuningName>(s5k3l8xxm3|ov13850r2a|[a-z0-9_]+)</TuningName>(?=\s*</TuningParameter>\s*</CameraModuleCfg>\s*<CameraModuleCfg>)', "<TuningName>$tuning</TuningName>")
    [IO.File]::WriteAllText("D:\sensor_cfg_ab.xml", $xml_content)
    & $adb push D:\sensor_cfg_ab.xml /data/local/tmp/sensor_cfg_real.xml | Out-Null
}

# 2. 推送补丁库并热加载
& $adb push D:\ats_build\libpatch\libparam_ov13850r2a.so /data/local/tmp/libpatch/ | Out-Null
& $adb shell "setprop debug.isp.alsc.bypass $bypass; sh /data/local/tmp/s123.sh" | Out-Null

# 3. 唤醒并拍照
& $adb shell "rm -f /sdcard/DCIM/Camera/*; am force-stop com.android.camera2; am start -a android.media.action.STILL_IMAGE_CAMERA >/dev/null; sleep 9; input keyevent 27; sleep 7" | Out-Null

# 4. 回拉照片并运行快速统计
Remove-Item D:\hw_out\camdir -Recurse -Force -ErrorAction SilentlyContinue
& $adb pull /sdcard/DCIM/Camera D:\hw_out\camdir | Out-Null
$files = Get-ChildItem D:\hw_out\camdir -Filter *.jpg
if ($files.Count -gt 0) {
    $f = $files[0].FullName
    Copy-Item $f "D:\hw_out\shot_$tag.jpg" -Force
    python -c "
from PIL import Image; import numpy as np
im = Image.open(r'D:\hw_out\shot_$tag.jpg')
a = np.asarray(im.convert('RGB')).astype(float)
h, w, _ = a.shape
def m(x): return x.mean((0,1)).round(1)
c = m(a[h//3:2*h//3, w//3:2*w//3])
k = np.mean([m(a[:h//8, :w//8]), m(a[:h//8, -w//8:]), m(a[-h//8:, :w//8]), m(a[-h//8:, -w//8:])], 0).round(1)
print('$tag center', c, 'G/R', round(c[1]/c[0], 2), 'G/B', round(c[1]/c[2], 2), '| corner', k, 'G/R', round(k[1]/k[0], 2), 'G/B', round(k[1]/k[2], 2))
"
} else {
    Write-Host "[-] 未能在 /sdcard/DCIM/Camera 获取到照片"
}
