#!/usr/bin/env python3
"""
Murmur — Streaming push-to-talk, menu bar app.

Hold RIGHT ⌥ → dark pill appears at bottom of screen with live audio waveform
→ words paste into whatever you were typing as you speak.
Fully local. Nothing leaves the machine.
"""

import math
import queue
import re
import subprocess
import sys
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pyperclip
import rumps
import sounddevice as sd
from pynput import keyboard
from pynput.keyboard import Controller as KbController, Key as KbKey

# ── AppKit / Quartz (via PyObjC, already installed by rumps) ──────────────────
from AppKit import (
    NSBackingStoreBuffered,
    NSColor,
    NSFloatingWindowLevel,
    NSFont,
    NSMakeRect,
    NSPanel,
    NSScreen,
    NSTextAlignmentCenter,
    NSTextField,
    NSWindowCollectionBehaviorCanJoinAllSpaces,
    NSWindowCollectionBehaviorIgnoresCycle,
    NSWindowCollectionBehaviorStationary,
    NSWindowStyleMaskBorderless,
    NSWorkspace,
)
import Quartz

PROJECT_ROOT = Path(__file__).parent
SESSIONS_DIR = PROJECT_ROOT / "sessions"
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

# ── Config ────────────────────────────────────────────────────────────────────
WHISPER_MODEL     = "mlx-community/whisper-small.en-mlx"
SAMPLE_RATE       = 16_000
CHUNK_MS          = 100
CHUNK_FRAMES      = int(SAMPLE_RATE * CHUNK_MS / 1000)

# ⚠️ SILENCE_THRESHOLD: Keep LOW (10-20) for Studio Display / built-in mics.
# The Studio Display mic has a natively quiet output. An RMS of 20 is typical
# for a person speaking clearly at normal volume. Setting this above ~50 will
# cause Murmur to treat real speech as silence and never flush it to Whisper.
# If you're getting no transcription at all, lower this first.
SILENCE_THRESHOLD = 15

# ⚠️ DIGITAL_GAIN: Software volume amplifier applied to raw audio before Whisper.
# Needed because mlx_whisper hallucinates "You" on near-silent audio — it's a
# known model bug, not an error to handle. 15x (~23dB) works well for the
# Studio Display mic. If you're getting "You" consistently, increase this.
# If transcription is garbled/repeated, lower it. See TROUBLESHOOTING.md.
DIGITAL_GAIN      = 15.0

SILENCE_CHUNKS    = 15     # 1500 ms of silence → flush phrase
MIN_SPEECH_CHUNKS = 8      # 800 ms of speech needed before transcribing
HOTKEY_COMBO      = {keyboard.Key.alt_r}

# ── Load model once ───────────────────────────────────────────────────────────
import mlx_whisper  # noqa

# Keyboard output controller (HID-level injection for paste)
_kb_out = KbController()

from settings_server import open_settings, load_settings as _load_settings

# ── Non-activating panel mask ─────────────────────────────────────────────────
_NSNonactivatingPanelMask = 1 << 7

# ── Waveform pill constants ───────────────────────────────────────────────────
PILL_W, PILL_H      = 240, 36
MINI_PILL_W         = 42
MINI_PILL_H         = 14
WAVE_W              = 64
N_BARS              = 8
BARS    = "▁▂▃▄▅▆▇█"   # Unicode block chars, shortest → tallest
RMS_HISTORY = 20  # how many recent RMS values to keep for scrolling waveform


def _waveform_string(rms_history: deque, current_rms: float) -> str:
    """
    Build an N_BARS-wide animated waveform string from recent RMS history.
    Each bar snaps to one of 8 heights. The pattern scrolls rightward and
    responds to actual microphone loudness.
    """
    # Pad / trim history to N_BARS length
    history = list(rms_history)[-N_BARS:]
    while len(history) < N_BARS:
        history.insert(0, 0.0)

    MAX_RMS = 1200.0
    result = []
    t = time.time()
    for i, level in enumerate(history):
        normalized = min(1.0, level / MAX_RMS)
        # Smooth idle flutter when normalized is low
        flutter = 0.04 * abs(math.sin(t * 5.0 + i * 1.3))
        h = max(flutter, normalized)
        idx = min(len(BARS) - 1, int(h * len(BARS)))
        result.append(BARS[idx])
    return "".join(result)
def _build_mini_pill():
    """
    Tiny condensed pill — same look as the full pill but 42×14 px.
    Visible when idle so the user knows Murmur is running.
    """
    try:
        screen = NSScreen.mainScreen()
        f = screen.frame()           # Use full screen bounds, ignore dock
        x  = f.origin.x + (f.size.width - MINI_PILL_W) / 2
        # Center the 14px mini pill relative to the 38px main pill
        # Main pill y is f.origin.y + 128.  offset = (38 - 14) / 2 = 12.
        # So mini y = 128 + 12 = 140.
        y  = f.origin.y + 140         
        r  = MINI_PILL_H / 2

        panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(x, y, MINI_PILL_W, MINI_PILL_H),
            NSWindowStyleMaskBorderless | _NSNonactivatingPanelMask,
            NSBackingStoreBuffered, False,
        )
        panel.setLevel_(Quartz.kCGStatusWindowLevel)
        panel.setOpaque_(False)
        panel.setHasShadow_(False)
        panel.setIgnoresMouseEvents_(True)
        panel.setBackgroundColor_(NSColor.clearColor())
        panel.setCollectionBehavior_(
            NSWindowCollectionBehaviorCanJoinAllSpaces
            | NSWindowCollectionBehaviorStationary
            | NSWindowCollectionBehaviorIgnoresCycle
        )
        view = panel.contentView()
        view.setWantsLayer_(True)
        layer = view.layer()
        layer.setCornerRadius_(r)
        layer.setMasksToBounds_(True)
        layer.setBackgroundColor_(
            Quartz.CGColorCreateGenericRGB(0.05, 0.05, 0.07, 0.94)
        )
        # Glow layer
        glow = Quartz.CALayer.layer()
        glow.setFrame_(Quartz.CGRectMake(0, 0, MINI_PILL_W, MINI_PILL_H))
        glow.setCornerRadius_(r)
        glow.setMasksToBounds_(False)
        glow.setBackgroundColor_(Quartz.CGColorCreateGenericRGB(0, 0, 0, 0))
        mini_path = Quartz.CGPathCreateWithRoundedRect(
            Quartz.CGRectMake(1, 1, MINI_PILL_W - 2, MINI_PILL_H - 2), r - 1, r - 1, None
        )
        glow.setShadowPath_(mini_path)
        glow.setShadowColor_(Quartz.CGColorCreateGenericRGB(0.45, 0.25, 1.0, 1.0))
        glow.setShadowRadius_(8.0)
        glow.setShadowOpacity_(0.75)
        glow.setShadowOffset_(Quartz.CGSizeMake(0, 0))
        view.layer().insertSublayer_below_(glow, view.layer())
        return panel
    except Exception as e:
        print(f"[mini-pill error] {e}")
        return None


def _build_pill():
    """
    Build a small dark pill with a properly rounded purple glow.
    Positioned just above the Dock using visibleFrame.
    Returns (panel, label) or (None, None) on failure.
    """
    try:
        screen = NSScreen.mainScreen()
        f = screen.frame()           # Use full screen bounds, ignore dock
        x = f.origin.x + (f.size.width - PILL_W) / 2
        y = f.origin.y + 128         # 128 px above bottom edge

        panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(x, y, PILL_W, PILL_H),
            NSWindowStyleMaskBorderless | _NSNonactivatingPanelMask,
            NSBackingStoreBuffered,
            False,
        )
        panel.setLevel_(Quartz.kCGStatusWindowLevel)
        panel.setOpaque_(False)
        panel.setHasShadow_(False)   # we paint our own glow
        panel.setIgnoresMouseEvents_(True)
        panel.setBackgroundColor_(NSColor.clearColor())
        panel.setCollectionBehavior_(
            NSWindowCollectionBehaviorCanJoinAllSpaces
            | NSWindowCollectionBehaviorStationary
            | NSWindowCollectionBehaviorIgnoresCycle
        )

        view = panel.contentView()
        view.setWantsLayer_(True)
        layer = view.layer()
        r = PILL_H / 2          # corner radius = perfect pill

        # Dark background — masksToBounds=True clips subviews to pill shape
        layer.setCornerRadius_(r)
        layer.setMasksToBounds_(True)
        layer.setBackgroundColor_(
            Quartz.CGColorCreateGenericRGB(0.05, 0.05, 0.07, 0.94)
        )

        # ── Glow: use a wrapper sublayer BEHIND the content ──────────────────
        # We can't put the shadow on the clipping layer, so we add a sibling
        # layer underneath that carries only the shadow + transparent fill.
        glow = Quartz.CALayer.layer()
        glow.setFrame_(Quartz.CGRectMake(0, 0, PILL_W, PILL_H))
        glow.setCornerRadius_(r)
        glow.setMasksToBounds_(False)
        glow.setBackgroundColor_(
            Quartz.CGColorCreateGenericRGB(0.0, 0.0, 0.0, 0.0)  # transparent
        )
        # Shadow follows the pill curve via an explicit CGPath
        pill_path = Quartz.CGPathCreateWithRoundedRect(
            Quartz.CGRectMake(2, 2, PILL_W - 4, PILL_H - 4), r - 2, r - 2, None
        )
        glow.setShadowPath_(pill_path)
        glow.setShadowColor_(
            Quartz.CGColorCreateGenericRGB(0.45, 0.25, 1.0, 1.0)  # purple-blue
        )
        glow.setShadowRadius_(16.0)
        glow.setShadowOpacity_(0.90)
        glow.setShadowOffset_(Quartz.CGSizeMake(0, 0))
        # Insert glow layer underneath the content layer
        view.layer().insertSublayer_below_(glow, view.layer())

        # ── Label (monospace so block chars are evenly spaced) ────────────────
        # ── Waveform label (monospace, left side) ─────────────────────────
        wave_label = NSTextField.alloc().initWithFrame_(
            NSMakeRect(8, (PILL_H - 18) / 2, WAVE_W, 18)
        )
        wave_label.setStringValue_("▁" * N_BARS)
        wave_label.setEditable_(False)
        wave_label.setBordered_(False)
        wave_label.setDrawsBackground_(False)
        wave_label.setTextColor_(
            NSColor.colorWithRed_green_blue_alpha_(0.75, 0.55, 1.0, 1.0)
        )
        wave_label.setFont_(NSFont.fontWithName_size_("Menlo", 12.0))
        wave_label.setAlignment_(NSTextAlignmentCenter)
        view.addSubview_(wave_label)

        # ── Text label (system font, right side) ──────────────────────────
        text_x = WAVE_W + 14
        text_label = NSTextField.alloc().initWithFrame_(
            NSMakeRect(text_x, (PILL_H - 16) / 2, PILL_W - text_x - 8, 16)
        )
        text_label.setStringValue_("Dictating with Murmur")
        text_label.setEditable_(False)
        text_label.setBordered_(False)
        text_label.setDrawsBackground_(False)
        text_label.setTextColor_(NSColor.whiteColor())
        text_label.setFont_(NSFont.systemFontOfSize_(11.5))
        view.addSubview_(text_label)

        print(f"   Pill at x={x:.0f} y={y:.0f}")
        return panel, wave_label, text_label

    except Exception as e:
        print(f"[pill error] {e}")
        import traceback; traceback.print_exc()
        return None, None, None


# ── Paste ─────────────────────────────────────────────────────────────────────

_paste_lock = threading.Lock()


def _play_sound(name: str) -> None:
    """Play a macOS system sound asynchronously (never blocks)."""
    threading.Thread(
        target=lambda: subprocess.run(
            ["afplay", f"/System/Library/Sounds/{name}.aiff"],
            check=False, capture_output=True,
        ),
        daemon=True,
    ).start()


def paste_text(text: str) -> None:
    """Paste text, then restore whatever was on the clipboard before."""
    if not text:
        return
    with _paste_lock:
        # Save what the user had copied before dictation
        try:
            saved = pyperclip.paste()
        except Exception:
            saved = ""

        pyperclip.copy(text)
        time.sleep(0.2)
        _kb_out.press(KbKey.cmd)
        _kb_out.press('v')
        _kb_out.release('v')
        _kb_out.release(KbKey.cmd)
        time.sleep(0.15)

        # Restore original clipboard so dictation never pollutes it
        try:
            pyperclip.copy(saved)
        except Exception:
            pass


# ── Transcription ─────────────────────────────────────────────────────────────

def transcribe_audio(audio: np.ndarray) -> str:
    try:
        # Apply digital gain to boost quiet macOS microphone input
        audio_float = audio.astype(np.float32) / 32768.0
        audio_float = audio_float * DIGITAL_GAIN
        
        result = mlx_whisper.transcribe(
            audio_float,
            path_or_hf_repo=WHISPER_MODEL,
            condition_on_previous_text=False,
            no_speech_threshold=0.8,
            compression_ratio_threshold=2.0,
        )
        return result.get("text", "").strip()
    except Exception as e:
        print(f"[transcribe error] {e}")
        return ""


def rms(chunk: np.ndarray) -> float:
    return float(np.sqrt(np.mean(chunk.astype(np.float32) ** 2)))


# ── Streaming session ─────────────────────────────────────────────────────────

class StreamingSession:
    def __init__(self):
        self._phrase_chunks: list = []
        self._silence_count  = 0
        self._speaking       = False
        self._job_queue: queue.Queue = queue.Queue()
        self._session_text: list    = []
        self._lock  = threading.Lock()
        self._done  = threading.Event()
        self._worker = threading.Thread(target=self._transcription_worker, daemon=True)
        self._worker.start()

    def feed(self, chunk: np.ndarray) -> None:
        flat = chunk.flatten()
        with self._lock:
            self._phrase_chunks.append(flat.copy())
        level = rms(flat)
        if level > SILENCE_THRESHOLD:
            self._speaking = True
            self._silence_count = 0
        else:
            if self._speaking:
                self._silence_count += 1
                if self._silence_count >= SILENCE_CHUNKS:
                    self._flush_phrase()

    def _flush_phrase(self, final: bool = False) -> None:
        with self._lock:
            chunks = list(self._phrase_chunks)
            self._phrase_chunks = []
            self._speaking = False
            self._silence_count = 0
        if len(chunks) < MIN_SPEECH_CHUNKS and not final:
            return
        audio = np.concatenate(chunks) if chunks else np.array([], dtype=np.int16)
        if len(audio) == 0:
            return
        self._job_queue.put((audio, final))

    def _process_voice_commands(self, text: str, execute_keys: bool = True) -> Optional[str]:
        """
        Parses mid-stream voice commands. 
        Executes keyboard macros if needed, and returns the cleaned text to paste.
        Returns None if the text is entirely consumed.
        """
        if not text:
            return text

        t_lower = text.lower().strip()
        
        # 1. Undo / Scratch that
        if re.fullmatch(r"scratch that\.?", t_lower) or re.fullmatch(r"undo that\.?", t_lower):
            if execute_keys:
                self._press_undo()
            return None

        # Backspace
        if re.fullmatch(r"backspace\.?", t_lower):
            if execute_keys:
                self._press_backspace()
            return None

        # If they say something then immediately say "scratch that" in the same breath
        if t_lower.endswith(" scratch that.") or t_lower.endswith(" scratch that") or t_lower.endswith(" undo that.") or t_lower.endswith(" undo that"):
            return None
            
        # 2. Formatting
        # If the entire chunk is just a formatting command
        if re.fullmatch(r"new paragraph\.?", t_lower):
            return "\n\n"
        if re.fullmatch(r"new line\.?", t_lower):
            return "\n"
            
        # 3. Inline formatting (case-insensitive replacement)
        t_mod = re.sub(r'(?i)\s*\bnew paragraph[\.\s]*', '\n\n', text)
        t_mod = re.sub(r'(?i)\s*\bnew line[\.\s]*', '\n', t_mod)
        
        # Whisper often auto-punctuates spoken punctuation words (e.g. "sentence, period.", "Wait, comma, what?")
        # These regexes catch the spoken word along with any surrounding auto-punctuation and replace it with the actual symbol.
        t_mod = re.sub(r'(?i)[,\s]*\bperiod[\.\s]*', '.', t_mod)
        t_mod = re.sub(r'(?i)[,\s]*\bquestion mark[\.\?\s]*', '?', t_mod)
        t_mod = re.sub(r'(?i)[,\s]*\bexclamation point[\.\!\s]*', '!', t_mod)
        t_mod = re.sub(r'(?i)[,\s]*\bcomma[\,\s]*', ',', t_mod)
        t_mod = re.sub(r'(?i)[,\s]*\bexclamation mark[\.\!\s]*', '!', t_mod)
        
        # 4. Snippets expansion
        settings = _load_settings()
        snippets = settings.get("snippets", [])
        for snippet in snippets:
            trigger = snippet.get("trigger", "")
            expand = snippet.get("expand", "")
            if trigger and expand:
                # Replace whole words, case-insensitive
                t_mod = re.sub(rf'(?i)\b{re.escape(trigger)}\b', expand, t_mod)
        
        return t_mod.lstrip()

    def _press_undo(self):
        try:
            kb = KbController()
            with kb.pressed(KbKey.cmd):
                kb.press('z')
                kb.release('z')
            print("[command] Executed Undo (Cmd+Z)")
        except Exception as e:
            print(f"Undo failed: {e}")

    def _press_backspace(self):
        try:
            kb = KbController()
            kb.press(KbKey.backspace)
            kb.release(KbKey.backspace)
            print("[command] Executed Backspace")
        except Exception as e:
            print(f"Backspace failed: {e}")

    def _transcription_worker(self) -> None:
        _last_text    = ""
        _repeat_count = 0
        MAX_REPEATS   = 2

        while True:
            item = self._job_queue.get()
            if item is None:
                break
            audio, final = item
            
            import wave
            from datetime import datetime
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            debug_file = SESSIONS_DIR / f"debug_{stamp}.wav"
            try:
                with wave.open(str(debug_file), "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(SAMPLE_RATE)
                    wf.writeframes(audio.tobytes())
                print(f"[debug] Saved {len(audio)/SAMPLE_RATE:.2f}s of raw audio to {debug_file.name}")
            except Exception as e:
                print(f"[debug error] {e}")

            text = transcribe_audio(audio)
            
            if text:
                # Discard chunks that are purely punctuation or whitespace (Whisper hallucinations)
                if not re.search(r'[A-Za-z0-9]', text):
                    if final:
                        self._done.set()
                    continue

                if text.strip() == _last_text.strip():
                    _repeat_count += 1
                    if _repeat_count > MAX_REPEATS:
                        print(f"[dedup] {text}")
                        if final:
                            self._done.set()
                        continue
                else:
                    _last_text    = text
                    _repeat_count = 0
                
                settings = _load_settings()
                if settings.get("smart_text_mode", "Off") == "Off":
                    cmd_text = self._process_voice_commands(text, execute_keys=True)
                    if cmd_text:
                        suffix = " " if not cmd_text.endswith("\n") else ""
                        paste_text(cmd_text + suffix)
                        self._session_text.append(cmd_text)
                        print(f"📝 {cmd_text}")
                    elif cmd_text is None:
                        # Undo command was executed. Remove last text from session if exists.
                        if self._session_text:
                            self._session_text.pop()
                else:
                    cmd_text = self._process_voice_commands(text, execute_keys=False)
                    if cmd_text:
                        self._session_text.append(cmd_text)
                        print(f"📝 {cmd_text} (Internal)")
                    elif cmd_text is None:
                        if self._session_text:
                            self._session_text.pop()
                            print(f"📝 [Internal Undo]")
                
                sys.stdout.flush()
            if final:
                self._done.set()

    def finish(self) -> str:
        self._flush_phrase(final=True)
        self._done.wait(timeout=30)
        self._job_queue.put(None)
        full = " ".join(self._session_text)
        if full:
            stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            (SESSIONS_DIR / f"{stamp}.txt").write_text(full)
        return full


# ── Menu bar app ──────────────────────────────────────────────────────────────

class MurmurApp(rumps.App):
    def __init__(self):
        _icon = str(PROJECT_ROOT / "menubar_icon.png")
        _has_icon = Path(_icon).exists()
        super().__init__(
            "",   # blank title — icon only in menu bar
            icon=_icon if _has_icon else None,
            template=False,
            quit_button=None,
        )

        self.menu = [
            rumps.MenuItem("Murmur",            callback=self.open_settings_window),
            None,
            rumps.MenuItem("Status: Ready"),
            None,
            rumps.MenuItem("Open Dashboard",    callback=self.open_settings_window),
            None,
            rumps.MenuItem("Dictionary…",       callback=lambda _: self._open_page("dictionary")),
            rumps.MenuItem("Snippets…",         callback=lambda _: self._open_page("snippets")),
            rumps.MenuItem("Preferences…",      callback=lambda _: self._open_page("settings")),
            None,
            rumps.MenuItem("Paste Last Transcript", callback=self.paste_last),
            None,
            rumps.MenuItem("Quit Murmur",       callback=self.quit_app),
        ]
        self._status = self.menu["Status: Ready"]

        self._session: Optional[StreamingSession] = None
        self._stream:  Optional[sd.InputStream]   = None
        self._active       = False
        self._pressed: set = set()
        self._last_transcript = ""
        self._current_rms  = 0.0
        self._rms_history: deque = deque(maxlen=RMS_HISTORY)
        self._pending_status: str = ""   # set from any thread; applied on main thread

        self._dot = _build_mini_pill()
        self._pill, self._pill_wave, self._pill_text = _build_pill()

        # Global keyboard listener
        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )
        self._listener.daemon = True
        self._listener.start()

        print("✅ Murmur ready — hold RIGHT ⌥ to dictate anywhere.")
        sys.stdout.flush()

    # ── UI timer ──────────────────────────────────────────────────────────────

    @rumps.timer(0.07)
    def _update_ui(self, _):
        # Apply any status update queued from a background thread (main-thread safe)
        if self._pending_status:
            self._status.title = self._pending_status
            self._pending_status = ""
        if self._active:
            if self._dot:  self._dot.orderOut_(None)
            if self._pill: self._pill.orderFrontRegardless()
            if self._pill_wave:
                self._rms_history.append(self._current_rms)
                self._pill_wave.setStringValue_(
                    _waveform_string(self._rms_history, self._current_rms)
                )
        else:
            if self._pill: self._pill.orderOut_(None)
            if self._dot:  self._dot.orderFrontRegardless()
            if self._rms_history: self._rms_history.clear()

    # ── Recording ─────────────────────────────────────────────────────────────

    def _start_recording(self) -> None:
        if self._active:
            return
        self._active  = True
        self._current_rms = 0.0
        self._pending_status = "Status: Recording…"
        self._session = StreamingSession()
        _play_sound("Pop")   # ← start cue

        def callback(indata, frames, time_info, status):
            if self._active and self._session:
                chunk = indata.copy()
                self._session.feed(chunk)
                self._current_rms = rms(chunk.flatten())

        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE, channels=1, dtype="int16",
            blocksize=CHUNK_FRAMES, callback=callback,
        )
        self._stream.start()
        print("🎙️  Recording…", flush=True)

    def _stop_recording(self) -> None:
        if not self._active:
            return
        self._active = False
        self._current_rms = 0.0
        self._pending_status = "Status: Transcribing…"
        _play_sound("Tink")  # ← stop cue

        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

        session, self._session = self._session, None

        def finish():
            if session:
                full = session.finish()
                if full:
                    settings = _load_settings()
                    smart_mode = settings.get("smart_text_mode", "Off")
                    if smart_mode != "Off":
                        if smart_mode == "HIPAA Redaction":
                            self._pending_status = "Status: Removing PHI…"
                            try:
                                import hipaa_engine
                                full = hipaa_engine.redact_phi(full)
                                paste_text(full + " ")
                                print(f"✨ [HIPAA] {full[:80]}{'…' if len(full) > 80 else ''}")
                            except Exception as e:
                                print(f"HIPAA Error: {e}")
                                paste_text(full + " ")
                        else:
                            self._pending_status = f"Status: Formatting ({smart_mode})…"
                            try:
                                import context_engine, llm_engine
                                app_name = context_engine.get_frontmost_app_name()
                                prompt = context_engine.get_contextual_prompt(app_name, smart_mode)
                                if prompt:
                                    processed = llm_engine.process_text_with_llm(full, prompt, show_progress=True)
                                    if processed:
                                        full = processed
                                paste_text(full + " ")
                                print(f"✨ {full[:80]}{'…' if len(full) > 80 else ''}")
                            except Exception as e:
                                print(f"LLM Error: {e}")
                                paste_text(full + " ")
                                print(f"✅ (fallback) {full[:80]}{'…' if len(full) > 80 else ''}")
                    else:
                        print(f"✅ {full[:80]}{'…' if len(full) > 80 else ''}")
                    
                    self._last_transcript = full
            
            self._pending_status = "Status: Ready"
            sys.stdout.flush()

        threading.Thread(target=finish, daemon=True).start()

    # ── Keyboard ──────────────────────────────────────────────────────────────

    def _norm(self, key):
        try:
            if key in (keyboard.Key.cmd, keyboard.Key.cmd_l, keyboard.Key.cmd_r):
                return keyboard.Key.cmd
            if key in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
                return keyboard.Key.ctrl
            if key in (keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r):
                return keyboard.Key.shift
        except AttributeError:
            pass
        return key

    def _on_press(self, key) -> None:
        self._pressed.add(self._norm(key))
        if HOTKEY_COMBO.issubset(self._pressed) and not self._active:
            threading.Thread(target=self._start_recording, daemon=True).start()

    def _on_release(self, key) -> None:
        nk = self._norm(key)
        self._pressed.discard(nk)
        if self._active and nk in HOTKEY_COMBO:
            threading.Thread(target=self._stop_recording, daemon=True).start()

    # ── Menu ──────────────────────────────────────────────────────────────────

    def open_settings_window(self, _) -> None:
        threading.Thread(target=open_settings, daemon=True).start()

    def _open_page(self, page: str) -> None:
        """Open the settings window directly to a specific page."""
        from settings_server import ensure_server
        import webbrowser, time
        ensure_server()
        # Open with page hash so JS can navigate
        threading.Thread(
            target=lambda: (__import__('time').sleep(0.1),
                             __import__('webbrowser').open(f"http://127.0.0.1:7734#{page}")),
            daemon=True,
        ).start()

    def paste_last(self, _) -> None:
        if self._last_transcript:
            threading.Thread(
                target=paste_text, args=(self._last_transcript,), daemon=True
            ).start()
        else:
            rumps.notification("Murmur", "", "No transcript yet.")

    def quit_app(self, _) -> None:
        self._listener.stop()
        rumps.quit_application()


# ── Entry ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("🔇 Murmur starting…")
    print("   Loading Whisper model (Metal-accelerated)…")
    sys.stdout.flush()
    _dummy = np.zeros(SAMPLE_RATE, dtype=np.float32)
    mlx_whisper.transcribe(_dummy, path_or_hf_repo=WHISPER_MODEL)
    print("   Model ready.")
    sys.stdout.flush()
    MurmurApp().run()
