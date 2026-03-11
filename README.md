# Murmur V1 (The Clinical MVP)

**Typing is the bottleneck to human thought.** 
Murmur is a privacy-first, zero-latency Voice-to-Text and Clinical AI Agent. It was built specifically for healthcare professionals and high-security personnel who need the magical dictation experience of modern AI (like Wispr Flow) but demand 100% local processing and strict HIPAA compliance.

## The Phase 1 MVP Architecture (Current Branch)
Murmur V1 was designed as a rapid-prototyping MVP to validate local cross-platform audio capture and global hotkey routing.
*   **Language:** Python
*   **Transcriber (The Ears):** `faster-whisper` (Local CPU/GPU accelerated via PyTorch)
*   **The Brain (Local LLM):** `Ollama` running `llama3` for fully offline, air-gapped clinical intelligence (e.g., formatting SOAP notes and extracting the "Patient Vault").
*   **Cross-Platform:** Supports global Right-Option hotkey detection and synthetic keystroke pasting on both macOS and Windows.

### Why Build Locally?
In clinical environments, sending audio to third-party APIs can violate compliance or introduce unacceptable psychological friction for physicians. Murmur V1 guarantees that not a single byte of patient audio touches the internet. It runs completely air-gapped, leveraging the doctor's existing Apple Silicon or Windows GPU.

***

## Where We Are Leaving Off
Murmur V1 successfully proved the thesis: Local STT is incredibly fast, and local LLMs can seamlessly format EHR notes. We successfully shipped:
1.  **Mac Release:** A shell-script wrapper that bypasses Gatekeeper and runs the Python environment seamlessly.
2.  **Windows Release:** A fully automated GitHub Actions pipeline generated a standalone `.exe` distributable.
3.  **Core Features:** Global hotkey listening, "Command Words" (Punctuation/Formatting), and the `vault/` continuous-memory clinical context builder.

***

## Where We Plan to Go: Murmur V2 (The Native Rewrite)
While V1 is incredibly functional, the 1.5GB Python/PyTorch dependencies limit mass-consumer distribution. We are officially transitioning to **Murmur V2**, a ground-up architectural rewrite stored in a separate repository.

### The V2 Stack (Targeted 50MB Download):
*   **The Frontend Shell:** Tauri (Rust + React) for gorgeous, lightweight, native cross-platform UI shells.
*   **The STT Engine:** `whisper.cpp` (C++ implementation) eliminating all Python and PyTorch dependencies, running natively on Mac/Windows.
*   **The Cloud Routing Array (Option 2):** Moving complex Clinical Formatting (SOAP note generation, Action Item extraction) to ultra-fast, HIPAA-compliant Cloud APIs (like Groq or Azure OpenAI) acting behind a secure proxy. This allows for "silent" prompt updates without users ever downloading new app files.

Murmur V1 will remain here pristine and functional as the core foundational proof of concept.
