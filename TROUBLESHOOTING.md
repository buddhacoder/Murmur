# Murmur Troubleshooting Guide

Symptom-first guide covering every real issue hit in production, with exact root causes and fixes.

---

## 🗣️ Dictation outputs "You" instead of transcribing

**Root cause:** `mlx_whisper` hallucinates the word "You" when fed near-silent audio. This is a known model quirk — it does not return empty string for silence.

**Most common reasons the mic is silent:**
1. **macOS input volume is set too low.** The Studio Display Microphone is especially quiet by default.
2. **The app lacks microphone permission** — macOS silently returns zeroed audio instead of raising an error.
3. **`SILENCE_THRESHOLD` is too high** — the app treats real but quiet speech as silence and never flushes it to Whisper.

**Fixes (in order):**
```bash
# 1. Programmatically max out macOS input volume
osascript -e 'set volume input volume 100'

# 2. Check RMS level — if it's < 30, the mic is near-silent
python test_audio.py  # prints Raw RMS: and Gained RMS:

# 3. Confirm mic permissions exist (terminal test)
python test_audio.py  # RMS of 0.0 = denied, RMS > 0 = permitted
```

**In `daemon.py`:**
- `SILENCE_THRESHOLD = 15` — keep this low for quiet mics (was 450, which was way too high)
- `DIGITAL_GAIN = 15.0` — applies a 15x software volume multiplier before sending audio to Whisper

---

## 🔕 Launching Murmur.app from Launchpad never shows a microphone permission prompt

**Root cause:** macOS TCC (Transparency, Consent, Control) is extremely strict. It will silently deny microphone access and never show the permission dialog if:

- The app is an AppleScript applet (`osacompile`) — macOS does not trust these for TCC prompts
- The app executable uses `execl()` to hand off to Python — `execl` **replaces the process image**, so macOS sees `python` as the requestor, not `Murmur.app`. The bundle identity is lost.
- The app is not code-signed with the `com.apple.security.device.audio-input` entitlement

**What does NOT work (and why):**
| Approach | Why it fails |
|---|---|
| AppleScript applet (`osacompile`) | macOS won't show TCC prompts for background-only applets |
| `execl(python, ...)` in a native wrapper | Replaces the app process with `python`, losing TCC identity |
| Running `tccutil reset Microphone` without rebuilding | Resets but doesn't fix the root cause; also wipes all other apps |
| Requesting mic from a terminal-launched Swift/ObjC binary | Terminal's TCC identity is used, not the app bundle |

**What works:**
1. Use `NSTask` (not `execl`) to launch Python as a **child process** of `Murmur.app` — the parent app retains its TCC identity
2. Code-sign the app bundle with the `audio-input` entitlement
3. Reset only the Murmur TCC entry after rebuilding

```bash
# Rebuild the app correctly
python build_app.py

# Reset ONLY Murmur's TCC entry (not all apps)
tccutil reset Microphone com.macstudiodaddy.murmur

# Deploy
rm -rf /Applications/Murmur.app
cp -R ./Murmur.app /Applications/Murmur.app
xattr -rc /Applications/Murmur.app
```

---

## 📋 Text pastes 2x or 3x when dictating

**Root cause:** Multiple `daemon.py` processes are running simultaneously, each independently recording and pasting.

**Check:**
```bash
ps aux | grep -i "[d]aemon.py"
```

If you see more than one line, you have ghost instances.

**Fix:**
```bash
pkill -f "daemon.py"
# Then start fresh:
./start.sh
```

**Prevention:** Always kill previous instances before relaunching during development.

---

## 🔴 Audio is recorded but transcription is blank

**Root cause:** The `no_speech_threshold = 0.8` setting in `transcribe_audio()` is aggressively filtering out content. This can happen if the gained audio still isn't loud enough.

**Fix:** Check the `DIGITAL_GAIN` constant in `daemon.py`. Increase it if needed. A gained RMS of `> 500` is usually sufficient for reliable Whisper transcription.

---

## ⚙️ App won't launch at all after rebuild

**Run:**
```bash
cat /tmp/murmur.log
```

All stdout/stderr from the Launchpad-launched daemon is redirected here. This is the first place to check for Python import errors, missing modules, or path issues.

---

## 🧰 Useful diagnostic commands

```bash
# Show all audio devices
python -c "import sounddevice as sd; print(sd.query_devices())"

# Test raw mic capture + Whisper transcription (speak during recording)
python test_audio.py

# Check mic TCC permission status for the app
tccutil check Microphone com.macstudiodaddy.murmur

# Check app code signature + entitlements
codesign -dv --verbose=4 /Applications/Murmur.app

# Tail the daemon log (while app is running from Launchpad)
tail -f /tmp/murmur.log

# Kill all daemon instances
pkill -f "daemon.py"
```
