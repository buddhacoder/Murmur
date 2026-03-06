"""
Murmur for Windows - Entry Point
This file serves as the Windows counterpart to daemon.py.
It uses PyQt6 for the UI overlay and faster-whisper for local transcription.
"""

import sys
import threading
import queue
import re
import time
import math
from collections import deque
from pathlib import Path
from datetime import datetime

import numpy as np
import sounddevice as sd
import pyperclip
from pynput import keyboard
from pynput.keyboard import Controller as KbController, Key as KbKey
from faster_whisper import WhisperModel

try:
    from PyQt6.QtWidgets import QApplication, QWidget, QLabel, QHBoxLayout, QSystemTrayIcon, QMenu
    from PyQt6.QtCore import Qt, pyqtSignal, QObject, QTimer
    from PyQt6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
except ImportError:
    print("PyQt6 is required for the Windows UI.")
    sys.exit(1)

from settings_server import open_settings, load_settings as _load_settings
import hipaa_engine
import context_engine
import llm_engine

PROJECT_ROOT = Path(__file__).parent
SESSIONS_DIR = PROJECT_ROOT / "sessions"
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

# ── Config ────────────────────────────────────────────────────────────────────
WHISPER_MODEL     = "base.en" # Using a smaller model for faster_whisper by default
SAMPLE_RATE       = 16_000
CHUNK_MS          = 100
CHUNK_FRAMES      = int(SAMPLE_RATE * CHUNK_MS / 1000)
SILENCE_THRESHOLD = 450    # RMS below = silence
SILENCE_CHUNKS    = 15     # 1500 ms of silence → flush phrase
MIN_SPEECH_CHUNKS = 8      # 800 ms of speech needed before transcribing
HOTKEY_COMBO      = {keyboard.Key.alt_r}

# Keyboard output controller
_kb_out = KbController()

# ── Waveform pill constants ───────────────────────────────────────────────────
PILL_W, PILL_H      = 240, 36
WAVE_W              = 64
N_BARS              = 8
BARS    = "▁▂▃▄▅▆▇█"
RMS_HISTORY = 20

# ── Global Model ─────────────────────────────────────────────────────────────
_model = None

def get_whisper_model():
    global _model
    if _model is None:
        print(f"Loading faster-whisper model ({WHISPER_MODEL})...")
        # Initialize faster-whisper. Uses GPU if available (CUDA), otherwise CPU.
        _model = WhisperModel(WHISPER_MODEL, device="auto", compute_type="default")
    return _model

def rms(chunk: np.ndarray) -> float:
    return float(np.sqrt(np.mean(chunk.astype(np.float32) ** 2)))

def _waveform_string(rms_history: deque, current_rms: float) -> str:
    history = list(rms_history)[-N_BARS:]
    while len(history) < N_BARS:
        history.insert(0, 0.0)

    MAX_RMS = 1200.0
    result = []
    t = time.time()
    for i, level in enumerate(history):
        normalized = min(1.0, level / MAX_RMS)
        flutter = 0.04 * abs(math.sin(t * 5.0 + i * 1.3))
        h = max(flutter, normalized)
        idx = min(len(BARS) - 1, int(h * len(BARS)))
        result.append(BARS[idx])
    return "".join(result)

_paste_lock = threading.Lock()

def paste_text(text: str) -> None:
    """Paste text, then restore whatever was on the clipboard before."""
    if not text:
        return
    with _paste_lock:
        try:
            saved = pyperclip.paste()
        except Exception:
            saved = ""

        pyperclip.copy(text)
        time.sleep(0.2)
        _kb_out.press(KbKey.ctrl)
        _kb_out.press('v')
        _kb_out.release('v')
        _kb_out.release(KbKey.ctrl)
        time.sleep(0.15)

        try:
            pyperclip.copy(saved)
        except Exception:
            pass

class SignalEmitter(QObject):
    update_status = pyqtSignal(str)
    update_waveform = pyqtSignal(str)
    visibility = pyqtSignal(bool)

class StreamingSession:
    def __init__(self, signals: SignalEmitter):
        self._phrase_chunks: list = []
        self._silence_count  = 0
        self._speaking       = False
        self._job_queue: queue.Queue = queue.Queue()
        self._session_text: list    = []
        self._lock  = threading.Lock()
        self._done  = threading.Event()
        self.signals = signals
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

    def _process_voice_commands(self, text: str, execute_keys: bool = True):
        if not text:
            return text

        t_lower = text.lower().strip()
        
        if re.fullmatch(r"scratch that\.?", t_lower) or re.fullmatch(r"undo that\.?", t_lower):
            if execute_keys:
                self._press_undo()
            return None

        if re.fullmatch(r"backspace\.?", t_lower):
            if execute_keys:
                self._press_backspace()
            return None

        if t_lower.endswith(" scratch that.") or t_lower.endswith(" scratch that") or t_lower.endswith(" undo that.") or t_lower.endswith(" undo that"):
            return None
            
        if re.fullmatch(r"new paragraph\.?", t_lower):
            return "\n\n"
        if re.fullmatch(r"new line\.?", t_lower):
            return "\n"
            
        t_mod = re.sub(r'(?i)\s*\bnew paragraph[\.\s]*', '\n\n', text)
        t_mod = re.sub(r'(?i)\s*\bnew line[\.\s]*', '\n', t_mod)
        t_mod = re.sub(r'(?i)[,\s]*\bperiod[\.\s]*', '.', t_mod)
        t_mod = re.sub(r'(?i)[,\s]*\bquestion mark[\.\?\s]*', '?', t_mod)
        t_mod = re.sub(r'(?i)[,\s]*\bexclamation point[\.\!\s]*', '!', t_mod)
        t_mod = re.sub(r'(?i)[,\s]*\bcomma[\,\s]*', ',', t_mod)
        t_mod = re.sub(r'(?i)[,\s]*\bexclamation mark[\.\!\s]*', '!', t_mod)
        
        settings = _load_settings()
        snippets = settings.get("snippets", [])
        for snippet in snippets:
            trigger = snippet.get("trigger", "")
            expand = snippet.get("expand", "")
            if trigger and expand:
                t_mod = re.sub(rf'(?i)\b{re.escape(trigger)}\b', expand, t_mod)
        
        return t_mod.lstrip()

    def _press_undo(self):
        try:
            with _kb_out.pressed(KbKey.ctrl):
                _kb_out.press('z')
                _kb_out.release('z')
            print("[command] Executed Undo (Ctrl+Z)")
        except Exception as e:
            print(f"Undo failed: {e}")

    def _press_backspace(self):
        try:
            _kb_out.press(KbKey.backspace)
            _kb_out.release(KbKey.backspace)
            print("[command] Executed Backspace")
        except Exception as e:
            print(f"Backspace failed: {e}")

    def _transcription_worker(self) -> None:
        _last_text    = ""
        _repeat_count = 0
        MAX_REPEATS   = 2
        model = get_whisper_model()

        while True:
            item = self._job_queue.get()
            if item is None:
                break
            audio, final = item
            
            # Convert int16 to float32 for faster-whisper
            audio_float = audio.astype(np.float32) / 32768.0
            
            segments, info = model.transcribe(audio_float, beam_size=5, condition_on_previous_text=False)
            text = " ".join([segment.text for segment in segments]).strip()
            
            if text:
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
                smart_mode = settings.get("smart_text_mode", "Off")
                
                if smart_mode == "Off":
                    cmd_text = self._process_voice_commands(text, execute_keys=True)
                    if cmd_text:
                        suffix = " " if not cmd_text.endswith("\n") else ""
                        paste_text(cmd_text + suffix)
                        self._session_text.append(cmd_text)
                        print(f"📝 {cmd_text}")
                    elif cmd_text is None:
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

class TransparentPill(QWidget):
    def __init__(self):
        super().__init__()
        
        # Always-on-top, borderless overlay
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.resize(PILL_W, PILL_H)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 0, 15, 0)
        
        self.setStyleSheet(f"""
            QWidget {{
                background-color: rgba(15, 15, 18, 240);
                border-radius: {PILL_H // 2}px;
                color: white;
            }}
        """)
        
        self.wave_label = QLabel("▁" * N_BARS)
        self.wave_label.setFont(QFont("Consolas", 12))
        self.wave_label.setStyleSheet("background: transparent; color: #b58cff;")
        self.wave_label.setFixedWidth(WAVE_W)
        self.wave_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.status_label = QLabel("Murmur Ready (Hold Right-Alt)")
        self.status_label.setFont(QFont("Segoe UI", 10))
        self.status_label.setStyleSheet("background: transparent;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        
        layout.addWidget(self.wave_label)
        layout.addWidget(self.status_label)
        self.position_bottom_center()
        
    def position_bottom_center(self):
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - PILL_W) // 2
        y = screen.height() - 128
        self.move(x, y)

    def set_status(self, text):
        self.status_label.setText(text)
        
    def set_waveform(self, text):
        self.wave_label.setText(text)

class WindowsApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.pill = TransparentPill()
        self.signals = SignalEmitter()
        
        self.signals.update_status.connect(self.pill.set_status)
        self.signals.update_waveform.connect(self.pill.set_waveform)
        self.signals.visibility.connect(self._set_pill_visibility)
        
        self._session: Optional[StreamingSession] = None
        self._stream:  Optional[sd.InputStream]   = None
        self._active       = False
        self._pressed: set = set()
        self._last_transcript = ""
        
        self._current_rms  = 0.0
        self._rms_history: deque = deque(maxlen=RMS_HISTORY)
        
        self._timer = QTimer()
        self._timer.timeout.connect(self._update_ui)
        self._timer.start(70)
        
        self.setup_tray()
        
        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )
        self._listener.daemon = True
        self._listener.start()
        
    def _set_pill_visibility(self, visible: bool):
        if visible:
            self.pill.show()
        else:
            self.pill.hide()

    def setup_tray(self):
        self.tray = QSystemTrayIcon()
        
        # Draw a simple circle icon if no file
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setBrush(QColor(181, 140, 255))
        painter.setPen(Qt.GlobalColor.transparent)
        painter.drawEllipse(4, 4, 24, 24)
        painter.end()
        self.tray.setIcon(QIcon(pixmap))
        
        menu = QMenu()
        
        action_settings = menu.addAction("Preferences…")
        action_settings.triggered.connect(self.open_settings)
        
        action_quit = menu.addAction("Quit Murmur")
        action_quit.triggered.connect(self.quit_app)
        
        self.tray.setContextMenu(menu)
        self.tray.show()

    def _update_ui(self):
        if self._active:
            self._rms_history.append(self._current_rms)
            self.signals.update_waveform.emit(_waveform_string(self._rms_history, self._current_rms))
        else:
            if self._rms_history: self._rms_history.clear()

    def _start_recording(self) -> None:
        if self._active:
            return
        self._active  = True
        self._current_rms = 0.0
        self.signals.update_status.emit("Recording…")
        self.signals.visibility.emit(True)
        self._session = StreamingSession(self.signals)

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

    def _stop_recording(self) -> None:
        if not self._active:
            return
        self._active = False
        self._current_rms = 0.0
        self.signals.update_status.emit("Transcribing…")

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
                            self.signals.update_status.emit("Removing PHI…")
                            try:
                                full = hipaa_engine.redact_phi(full)
                                paste_text(full + " ")
                                print(f"✨ [HIPAA] {full[:80]}")
                            except Exception as e:
                                paste_text(full + " ")
                        else:
                            self.signals.update_status.emit(f"Formatting ({smart_mode})…")
                            try:
                                app_name = context_engine.get_frontmost_app_name()
                                prompt = context_engine.get_contextual_prompt(app_name, smart_mode)
                                if prompt:
                                    processed = llm_engine.process_text_with_llm(full, prompt, show_progress=True)
                                    if processed:
                                        full = processed
                                paste_text(full + " ")
                                print(f"✨ {full[:80]}")
                            except Exception as e:
                                paste_text(full + " ")
                    
                    self._last_transcript = full
            
            self.signals.update_status.emit("Ready")
            self.signals.visibility.emit(False)

        threading.Thread(target=finish, daemon=True).start()

    def _norm(self, key):
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

    def open_settings(self):
        threading.Thread(target=open_settings, daemon=True).start()

    def quit_app(self):
        self._listener.stop()
        self.app.quit()
        sys.exit(0)

    def run(self):
        print("🔇 Murmur Windows starting…")
        print("   Loading faster-whisper model…")
        get_whisper_model()
        print("   Model ready. Hold RIGHT ALT to dictate.")
        self.app.exec()

if __name__ == '__main__':
    WindowsApp().run()
