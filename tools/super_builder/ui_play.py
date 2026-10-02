import subprocess, time, re
ADB = r"D:\ADK\platform-tools\adb.exe"
def sh(c, t=90):
    r = subprocess.run([ADB, "shell", c], capture_output=True, text=True, errors="ignore", timeout=t)
    return (r.stdout + r.stderr).strip()
def play_tone():
    """Launch preview of tone and tap play button. Returns True if tapped."""
    sh("input keyevent KEYCODE_WAKEUP; wm dismiss-keyguard")
    sh("am start -W -a android.intent.action.VIEW -d file:///sdcard/Music/tone_test.wav -t audio/x-wav")
    time.sleep(2)
    sh("uiautomator dump /sdcard/ui.xml")
    xml = sh("cat /sdcard/ui.xml")
    nodes = re.findall(r'<node[^>]*>', xml)
    for n in nodes:
        if re.search(r'(play|pause|Play)', n) and 'bounds' in n:
            b = re.search(r'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', n)
            if b:
                x = (int(b[1]) + int(b[3])) // 2; y = (int(b[2]) + int(b[4])) // 2
                print("node:", n[:200]); print("tap", x, y)
                sh(f"input tap {x} {y}")
                return True
    print("no play node; nodes:", [n[:120] for n in nodes[:12]])
    return False
if __name__ == "__main__":
    print(play_tone())
