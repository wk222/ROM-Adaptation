import subprocess, time, sys
sys.path.insert(0, r"D:\ats_build")
ADB = r"D:\ADK\platform-tools\adb.exe"
def run(args, t=90):
    r = subprocess.run([ADB] + args, capture_output=True, text=True, errors="ignore", timeout=t)
    return (r.stdout + r.stderr).strip()
def sh(c, t=90): return run(["shell", c], t)

print(run(["pull", "/vendor/etc/audio_route.xml", r"D:\ats_build\audio_route_orig.xml"]))
data = open(r"D:\ats_build\audio_route_orig.xml", "rb").read()
text = data.decode("utf-8")
nl = "\r\n" if "\r\n" in text else "\n"
s0 = text.index('<speaker device="0x2">')
s1 = text.index('</speaker>', s0)
blk = text[s0:s1]
assert 'SPKL Mixer' not in blk
on_anchor = '<ctl name="Speaker Function" val="1" />'
assert blk.count(on_anchor) == 1
new_on = ('<ctl name="SPKL Mixer DACLSPKL Switch" val="1" />' + nl + '                '
          '<ctl name="SPKL Gain SPKL Playback Volume" val="5" />' + nl + '                ' + on_anchor)
blk2 = blk.replace(on_anchor, new_on)
off_anchor = '<ctl name="Speaker Function" val="0" />'
assert blk2.count(off_anchor) == 1
blk2 = blk2.replace(off_anchor, off_anchor + nl + '                <ctl name="SPKL Mixer DACLSPKL Switch" val="0" />')
out = text[:s0] + blk2 + text[s1:]
open(r"D:\ats_build\audio_route_patched.xml", "wb").write(out.encode("utf-8"))
print("patched; new speaker block:\n" + blk2)

print(run(["push", r"D:\ats_build\audio_route_patched.xml", "/data/local/tmp/audio_route_patched.xml"]))
print(sh("chcon u:object_r:vendor_configs_file:s0 /data/local/tmp/audio_route_patched.xml"))
print(sh("umount /vendor/etc/audio_params/sprd/codec.xml; mount --bind /data/local/tmp/audio_route_patched.xml /vendor/etc/audio_route.xml && echo BIND_OK"))
# reset state & restart HAL
sh("am force-stop org.lineageos.eleven")
sh("tinymix 'SPKL Mixer DACLSPKL Switch' 0; tinymix 'SPKL Gain SPKL Playback Volume' 0")
sh("pkill -f android.hardware.audio.service; sleep 1; killall audioserver")
time.sleep(15)
print("pids:", sh("pidof android.hardware.audio.service audioserver"))
print("after HAL restart:", sh("tinymix | grep -E 'SPKL Mixer|SPKL Gain' | tr -s ' \\t' ' '").replace("\n", " ; "))
