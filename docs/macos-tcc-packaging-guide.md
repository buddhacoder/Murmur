# macOS TCC & App Packaging: Lessons Learned

This document captures hard-won knowledge about macOS privacy permissions (TCC), app packaging, and code signing. Reference this before building any future macOS `.app` that needs microphone, camera, or other sensitive hardware access.

---

## What is TCC?

**TCC (Transparency, Consent, and Control)** is the macOS subsystem that manages privacy permissions (microphone, camera, screen recording, contacts, etc.). Every permission prompt you have ever seen on a Mac is TCC.

TCC operates on **bundle identity** — it grants permissions to a specific `CFBundleIdentifier` (e.g., `com.macstudiodaddy.murmur`), not to an executable path or a user. This has major consequences for how you package a background app.

---

## Why Apps Lose Mic Access (and Never Get the Prompt)

### The Child Process Problem

When a macOS app launches a background process, the **TCC permission belongs to the parent app**, not the child. If the child process's identity becomes disassociated from the signed parent bundle, macOS silently denies access.

**`execl()` is the classic trap:**
```c
// ❌ WRONG — replaces the Murmur.app process image with python
// macOS now sees the requestor as "python", not "Murmur.app"
execl("/path/to/python", "python", "daemon.py", NULL);
```

**`NSTask` is the correct approach:**
```objc
// ✅ CORRECT — Murmur.app stays alive as the parent
// Python inherits the parent's TCC mic permission
NSTask *task = [[NSTask alloc] init];
[task setLaunchPath:@"/path/to/python"];
[task setArguments:@[@"daemon.py"]];
[task launch];
[task waitUntilExit];
```

### The Entitlements Requirement

Even with `NSTask`, macOS will not show the permission prompt without the app bundle being **code-signed with the `com.apple.security.device.audio-input` entitlement**.

**Required `entitlements.plist`:**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "...">
<plist version="1.0">
<dict>
    <key>com.apple.security.device.audio-input</key>
    <true/>
</dict>
</plist>
```

**Signing command:**
```bash
codesign --force --deep --sign - --entitlements entitlements.plist Murmur.app
```

The `-` identity means ad-hoc signing, which works perfectly for local development without an Apple Developer account.

### The AppleScript Applet Problem

`osacompile` produces applets that macOS deliberately excludes from TCC prompts for background-only apps. **Never use `osacompile` for apps that need microphone, camera, or screen recording.**

---

## The Correct Build Pattern for Background macOS Apps

This is the pattern that works for any macOS background app (no Dock icon, no window, needs hardware access):

### 1. Native Objective-C Launcher Executable

```objc
#import <AVFoundation/AVFoundation.h>
#import <Foundation/Foundation.h>

int main(int argc, const char * argv[]) {
    @autoreleasepool {
        // Request mic permissions (shows the dialog if not yet determined)
        if ([AVCaptureDevice authorizationStatusForMediaType:AVMediaTypeAudio] 
            == AVAuthorizationStatusNotDetermined) {
            dispatch_semaphore_t sema = dispatch_semaphore_create(0);
            [AVCaptureDevice requestAccessForMediaType:AVMediaTypeAudio 
                                    completionHandler:^(BOOL granted) {
                dispatch_semaphore_signal(sema);
            }];
            dispatch_semaphore_wait(sema, DISPATCH_TIME_FOREVER);
        }
        
        // Launch the actual app logic as a child process (KEEP Murmur.app as parent)
        NSTask *task = [[NSTask alloc] init];
        [task setLaunchPath:@"/path/to/.venv/bin/python"];
        [task setArguments:@[@"/path/to/daemon.py"]];
        [task launch];
        [task waitUntilExit];
    }
    return 0;
}
```

### 2. Info.plist Requirements

```python
plist = {
    "CFBundleExecutable": "Murmur",          # must match the compiled binary name
    "CFBundleIdentifier": "com.yourapp.id",  # unique, used by TCC
    "CFBundleName": "Murmur",
    "CFBundleIconFile": "app_icon.icns",
    "LSUIElement": True,                      # hides from Dock
    "NSMicrophoneUsageDescription": "...",   # shown in the permission dialog
}
```

### 3. Code Signing with Entitlements

```python
subprocess.run([
    "codesign", "--force", "--deep", "--sign", "-",
    "--entitlements", "entitlements.plist",
    str(app_dir)
], check=True)
```

### 4. Resetting TCC for Testing

During development, you frequently need to re-trigger the permission prompt:

```bash
# Reset ONLY your app's TCC entry (safe — won't affect other apps)
tccutil reset Microphone com.yourapp.id

# ⚠️ DO NOT use the global reset unless absolutely necessary:
# tccutil reset Microphone   ← this wipes ALL apps' mic permissions
```

---

## Debugging TCC Issues

```bash
# Check current permission status
tccutil check Microphone com.yourapp.id

# Verify code signature and entitlements
codesign -dv --verbose=4 MyApp.app

# Watch the TCC daemon log in real time
log stream --predicate 'subsystem == "com.apple.TCC"' --info

# Check what the app is doing
tail -f /tmp/murmur.log
```

---

## Quick Reference: What Works vs What Doesn't

| Approach | TCC Prompt? | Notes |
|---|---|---|
| Raw terminal `python script.py` | Uses Terminal's permission | Works if Terminal has mic access |
| `osacompile` applet | ❌ Never | macOS excludes applets from TCC for background apps |
| Native wrapper + `execl()` | ❌ Never | `execl` kills the bundle identity |
| Native wrapper + `NSTask` | ✅ Yes | Correct approach |
| PyInstaller `.app` | ✅ Yes | Works but very large bundles |
| Electron/similar (background) | ✅ Yes | Correct approach, same principle as NSTask |
