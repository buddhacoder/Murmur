import os
import subprocess
import plistlib
from pathlib import Path

def create_app_bundle():
    base_dir = Path(__file__).resolve().parent
    app_dir = base_dir / "Murmur.app"

    # AppleScript to launch daemon and STAY ALIVE (no trailing '&')
    applescript = f'''
    do shell script "cd {base_dir} && arch -arm64 {base_dir}/.venv/bin/python daemon.py > /tmp/murmur.log 2>&1"
    '''
    
    script_path = base_dir / "launch.applescript"
    script_path.write_text(applescript)
    
    # Compile AppleScript to a native macOS Application
    subprocess.run(["osacompile", "-o", str(app_dir), str(script_path)], check=True)
    script_path.unlink()

    # Modify the generated Info.plist to make it a background app
    plist_path = app_dir / "Contents" / "Info.plist"
    with open(plist_path, "rb") as f:
        plist = plistlib.load(f)
        
    plist["LSUIElement"] = True
    plist["CFBundleName"] = "Murmur"
    plist["CFBundleIdentifier"] = "com.macstudiodaddy.murmur"
    plist["NSMicrophoneUsageDescription"] = "Murmur requires microphone access for voice dictation."

    with open(plist_path, "wb") as f:
        plistlib.dump(plist, f)

    print(f"Created AppleScript applet: {app_dir}")

if __name__ == "__main__":
    create_app_bundle()
