# 🔇 Murmur

> **Local voice + local AI. No cloud. No subscriptions. Your data stays on your machine.**  
> Works on **macOS** and **Windows**.

Murmur records your voice, transcribes it locally with [faster-whisper](https://github.com/SYSTRAN/faster-whisper), and optionally sends the transcript to a local LLM via [Ollama](https://ollama.com) to clean it up, summarize it, and generate clinical SOAP notes.

Built for: **doctors, lawyers, finance professionals** — anyone with sensitive data that shouldn't touch the cloud.

---

## Features

- 🎙️ **Record** — mic capture with `sounddevice` (no binary tools, works Mac + Windows)
- ✏️ **Transcribe** — `faster-whisper` runs fully on-device
- 🧠 **Think** — local LLM cleans transcript, writes summaries, SOAP notes, task lists
- 🏥 **Clinical mode** — SOAP notes, HPI drafts, task lists
- 💼 **General mode** — for finance, personal notes, meetings
- 📂 **Patient vault** — per-patient memory in `vault/patient_<id>/` (never cross-contaminates)
- 🔒 **Privacy controls** — delete audio post-transcription, skip LLM entirely
- 📁 **Session history** — last 8 sessions listed and inspectable in the UI

---

## Quick Start — macOS

```bash
cd ~/projects/Murmur
bash install.sh
bash run.sh
```

## Quick Start — Windows

1. Install [Python 3.10+](https://python.org) — check **"Add to PATH"** during install
2. Install [Ollama for Windows](https://ollama.com/download/windows)
3. Double-click **`install.bat`**
4. Double-click **`run.bat`**

Opens at **http://localhost:8501**

---

## Sharing with a Colleague

```bash
# macOS
bash share.sh

# Windows — zip the Murmur folder manually, excluding sessions/ and vault/
```

Your colleague unzips and runs `install.bat` (Windows) or `bash install.sh` (Mac).  
No recordings, no patient data, no models included in the zip.

---

## Privacy Notes

| Item | Status |
|---|---|
| Audio/transcripts sent to the cloud | ❌ Never |
| Models loaded from the cloud at runtime | ❌ Never (downloaded once) |
| `sessions/` and `vault/` committed to git | ❌ Gitignored |

**Enable FileVault** (Mac) or **BitLocker** (Windows) for full-disk encryption.

---

## Model Recommendations by RAM

| RAM | Recommended Model |
|---|---|
| 24–32 GB | `llama3.2:3b` (default) |
| 48–64 GB | `qwen2.5:7b` |
| 96 GB+ | `llama3.1:70b` (quantized) |

---

## Project Structure

```
Murmur/
├── app.py          ← Main UI (cross-platform)
├── prompts.py      ← LLM system prompts
├── requirements.txt← Python deps
├── install.sh      ← macOS installer
├── install.bat     ← Windows installer
├── run.sh          ← macOS launch (auto-generated)
├── run.bat         ← Windows launch
├── share.sh        ← Package for sharing
├── sessions/       ← Per-recording outputs (gitignored)
└── vault/          ← Per-patient memory (gitignored)
```

---

## License

Personal use / internal workflows. Not FDA-cleared. Not a medical device.
