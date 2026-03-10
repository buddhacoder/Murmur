import os
import subprocess
import plistlib
import shutil
from pathlib import Path

def create_app_bundle():
    base_dir = Path(__file__).resolve().parent
    app_dir = base_dir / "Murmur.app"
    
    # Clean previous app
    if app_dir.exists():
        shutil.rmtree(app_dir)
        
    # Create bundle structure
    macos_dir = app_dir / "Contents" / "MacOS"
    resources_dir = app_dir / "Contents" / "Resources"
    macos_dir.mkdir(parents=True)
    resources_dir.mkdir(parents=True)
    
    # 1. Create the Objective-C wrapper
    # This wrapper requests mic permissions natively, then executes the python daemon.
    objc_source = base_dir / "wrapper.m"
    objc_source.write_text(f'''
#import <AVFoundation/AVFoundation.h>
#import <Foundation/Foundation.h>
#include <unistd.h>

int main(int argc, const char * argv[]) {{
    @autoreleasepool {{
        // Force the Mic permission prompt if not determined
        if ([AVCaptureDevice authorizationStatusForMediaType:AVMediaTypeAudio] == AVAuthorizationStatusNotDetermined) {{
            dispatch_semaphore_t sema = dispatch_semaphore_create(0);
            [AVCaptureDevice requestAccessForMediaType:AVMediaTypeAudio completionHandler:^(BOOL granted) {{
                dispatch_semaphore_signal(sema);
            }}];
            dispatch_semaphore_wait(sema, DISPATCH_TIME_FOREVER);
        }}
    }}
    
    // Execute the Python daemon
    NSString *pythonPath = [NSString stringWithUTF8String:"{base_dir}/.venv/bin/python"];
    NSString *scriptPath = [NSString stringWithUTF8String:"{base_dir}/daemon.py"];
    
    NSTask *task = [[NSTask alloc] init];
    [task setLaunchPath:pythonPath];
    [task setArguments:@[scriptPath]];
    
    // Redirect stdout and stderr to a log file
    NSFileHandle *logHandle = [NSFileHandle fileHandleForWritingAtPath:@"/tmp/murmur.log"];
    if (!logHandle) {{
        [[NSFileManager defaultManager] createFileAtPath:@"/tmp/murmur.log" contents:nil attributes:nil];
        logHandle = [NSFileHandle fileHandleForWritingAtPath:@"/tmp/murmur.log"];
    }}
    [task setStandardOutput:logHandle];
    [task setStandardError:logHandle];
    
    [task launch];
    [task waitUntilExit];
    
    return 0;
}}
''')

    # Compile the wrapper into the app bundle
    executable_path = macos_dir / "Murmur"
    subprocess.run([
        "clang", "-framework", "Foundation", "-framework", "AVFoundation", 
        str(objc_source), "-o", str(executable_path)
    ], check=True)
    objc_source.unlink()
    
    # 2. Add Info.plist
    plist = {
        "CFBundleExecutable": "Murmur",
        "CFBundleIdentifier": "com.macstudiodaddy.murmur",
        "CFBundleName": "Murmur",
        "CFBundleIconFile": "app_icon.icns",
        "LSUIElement": True,
        "NSMicrophoneUsageDescription": "Murmur requires microphone access for background voice dictation."
    }
    with open(app_dir / "Contents" / "Info.plist", "wb") as f:
        plistlib.dump(plist, f)
        
    # 3. Add icon
    app_icon_src = base_dir / "app_icon.icns"
    if app_icon_src.exists():
        shutil.copy2(app_icon_src, resources_dir / "app_icon.icns")
        
    # 4. Sign the app with Microphone entitlements
    entitlements_path = base_dir / "entitlements.plist"
    entitlements_path.write_text("""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>com.apple.security.device.audio-input</key>
    <true/>
</dict>
</plist>
""")
    
    print("Code signing the application...")
    subprocess.run([
        "codesign", "--force", "--deep", "--sign", "-", 
        "--entitlements", str(entitlements_path), str(app_dir)
    ], check=True)
    entitlements_path.unlink()
    
    print(f"Created securely signed native Murmur.app at: {app_dir}")

if __name__ == "__main__":
    create_app_bundle()
