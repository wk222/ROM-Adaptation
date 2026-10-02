import subprocess, time

ADB = r"D:\ADK\platform-tools\adb.exe"
FB = r"D:\ADK\platform-tools\fastboot.exe"
t0 = time.time()
last = None
while time.time() - t0 < 420:
    a = subprocess.run([ADB, "devices"], capture_output=True, text=True, errors="ignore").stdout.strip().splitlines()[1:]
    f = subprocess.run([FB, "devices"], capture_output=True, text=True, errors="ignore").stdout.strip()
    state = "adb=" + ";".join(x.strip() for x in a if x.strip()) + " | fb=" + f
    if state != last:
        print(f"[{int(time.time()-t0):3d}s] {state}", flush=True)
        last = state
    if any("\tdevice" in x for x in a):
        # 等 sys.boot_completed
        for _ in range(60):
            r = subprocess.run([ADB, "shell", "getprop sys.boot_completed; getprop ro.build.version.release; getprop ro.build.flavor; getprop ro.lineage.version"],
                               capture_output=True, text=True, errors="ignore").stdout.strip().splitlines()
            print(f"[{int(time.time()-t0):3d}s] props: {r}", flush=True)
            if r and r[0].strip() == "1":
                break
            time.sleep(5)
        break
    time.sleep(3)
print("watch done")
