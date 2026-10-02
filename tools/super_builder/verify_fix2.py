import subprocess, time, sys
sys.path.insert(0, r"D:\ats_build")
ADB = r"D:\ADK\platform-tools\adb.exe"
def run(args, t=90):
    r = subprocess.run([ADB] + args, capture_output=True, text=True, errors="ignore", timeout=t)
    return (r.stdout + r.stderr).strip()
def sh(c, t=90): return run(["shell", c], t)

run(["reboot"])
t0 = time.time(); time.sleep(30)
while time.time() - t0 < 300:
    try:
        if sh("getprop sys.boot_completed", 10).strip() == "1": break
    except Exception: pass
    time.sleep(4)
print(f"boot_completed after {int(time.time()-t0)}s")
run(["root"]); time.sleep(4); time.sleep(8)
print("mounts bind?:", sh("grep -c -E 'audio_route|sensor_config' /proc/mounts"))
print("route md5:", sh("md5sum /vendor/etc/audio_route.xml"), "(expect 84d7de32...)")
print("front cfg:", sh("grep -A3 '<SlotId>1' /vendor/etc/sensor_config.xml | tr '\\n' ' '"))
print("skiagl:", sh("getprop debug.renderengine.backend"))
from ui_play import play_tone
def mix(): return sh("tinymix | grep -E 'SPKL Mixer|SPKL Gain' | tr -s ' \\t' ' '").replace("\n", " ; ")
print("idle mixer:", mix())
play_tone()
for i in range(4):
    time.sleep(0.8)
    a = sh("grep hw_ptr /proc/asound/card0/pcm0p/sub0/status | tr -d ' '"); time.sleep(0.03)
    b = sh("grep hw_ptr /proc/asound/card0/pcm0p/sub0/status | tr -d ' '")
    print(i, mix(), sh("head -1 /proc/asound/card0/pcm0p/sub0/status"), a, b)
print("pids:", sh("pidof android.hardware.audio.service audioserver"))
