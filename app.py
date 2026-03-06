"""
Murmur — Local Voice + AI Thinking Partner
Cross-platform: macOS and Windows.
Fully local: faster-whisper for STT, Ollama for LLM reasoning.
No cloud calls. No subscriptions. Your data stays on your machine.
"""

import json
import os
import platform
import re
import subprocess
import tempfile
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import requests
import scipy.io.wavfile as wav_io
import sounddevice as sd
import streamlit as st

from prompts import CLINICAL_PROMPT, GENERAL_PROMPT

# ──────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent
SESSIONS_DIR = PROJECT_ROOT / "sessions"
VAULT_DIR    = PROJECT_ROOT / "vault"

OLLAMA_BASE_URL    = "http://localhost:11434"
OLLAMA_GENERATE_URL = f"{OLLAMA_BASE_URL}/api/generate"

SAMPLE_RATE = 16_000   # Hz — whisper expects 16 kHz

SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
VAULT_DIR.mkdir(parents=True, exist_ok=True)

IS_WINDOWS = platform.system() == "Windows"

# ──────────────────────────────────────────────
# Page config & custom CSS
# ──────────────────────────────────────────────
st.set_page_config(
    page_title="Murmur",
    page_icon="🔇",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

  html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
    background-color: #0d0e14;
    color: #e2e4ec;
  }
  .main .block-container { padding: 2rem 2.5rem; max-width: 1100px; }

  .murmur-header { display:flex; align-items:center; gap:14px; margin-bottom:0.25rem; }
  .murmur-logo   { font-size:2.6rem; line-height:1; }
  .murmur-title  {
    font-size:2.4rem; font-weight:700; letter-spacing:-0.02em;
    background:linear-gradient(135deg,#a78bfa,#60a5fa,#34d399);
    -webkit-background-clip:text; -webkit-text-fill-color:transparent;
  }
  .murmur-tagline { color:#6b7280; font-size:0.9rem; margin-top:-4px; margin-bottom:1.5rem; }

  .card { background:#161822; border:1px solid #252736; border-radius:12px; padding:1.2rem 1.5rem; margin-bottom:1rem; }
  .card-label { font-size:0.7rem; font-weight:600; text-transform:uppercase; letter-spacing:0.1em; color:#6b7280; margin-bottom:0.5rem; }

  .status-pill { display:inline-block; padding:3px 12px; border-radius:999px; font-size:0.75rem; font-weight:500; }
  .status-ready { background:#052e1c; color:#34d399; border:1px solid #065f46; }
  .status-warn  { background:#2d1a04; color:#fb923c; border:1px solid #78350f; }
  .status-error { background:#2a0d0f; color:#f87171; border:1px solid #7f1d1d; }

  div[data-testid="stButton"] > button {
    background:linear-gradient(135deg,#7c3aed,#2563eb);
    color:white; border:none; border-radius:10px;
    font-size:1rem; font-weight:600; padding:0.6rem 1.6rem;
    transition:opacity 0.15s;
  }
  div[data-testid="stButton"] > button:hover { opacity:0.88; }

  textarea {
    background:#111218 !important; color:#e2e4ec !important;
    border:1px solid #252736 !important; border-radius:8px !important;
    font-family:'Inter',sans-serif !important; font-size:0.88rem !important;
  }
  section[data-testid="stSidebar"] { background:#111218; border-right:1px solid #1e2030; }
  hr { border-color:#1e2030; }
  .stSpinner > div > div { border-top-color:#7c3aed !important; }
  .session-item {
    background:#161822; border:1px solid #1e2030; border-radius:8px;
    padding:0.6rem 0.9rem; margin-bottom:0.4rem; font-size:0.8rem; color:#9ca3af;
  }
</style>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def now_stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def check_ollama() -> tuple[bool, list[str]]:
    try:
        r = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=3)
        models = [m["name"] for m in r.json().get("models", [])]
        return True, models
    except Exception:
        return False, []


def check_faster_whisper() -> bool:
    try:
        import faster_whisper  # noqa
        return True
    except ImportError:
        return False


def record_mic(wav_path: Path, seconds: int) -> None:
    """
    Record from the default microphone using sounddevice.
    Works on macOS and Windows (no binary tools required).
    """
    audio = sd.rec(
        int(seconds * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="int16",
    )
    sd.wait()
    wav_io.write(str(wav_path), SAMPLE_RATE, audio)


@st.cache_resource(show_spinner=False)
def load_whisper_model(model_size: str = "small.en"):
    """
    Load faster-whisper model (cached in session so it only loads once).
    On Mac it auto-uses Metal (via CoreML on arm64).
    On Windows it uses CPU (or CUDA if available).
    """
    from faster_whisper import WhisperModel

    device   = "cpu"
    compute  = "int8"   # quantized — fast everywhere

    # Use CUDA on Windows/Linux if available
    try:
        import torch
        if torch.cuda.is_available():
            device  = "cuda"
            compute = "float16"
    except ImportError:
        pass

    return WhisperModel(model_size, device=device, compute_type=compute)


def transcribe(wav_path: Path, model_size: str = "small.en") -> str:
    model = load_whisper_model(model_size)
    segments, _ = model.transcribe(str(wav_path), beam_size=5)
    return " ".join(seg.text for seg in segments).strip()


def run_ollama(transcript: str, model: str, prompt_template: str) -> str:
    payload = {
        "model": model,
        "prompt": f"{prompt_template}\n\nTRANSCRIPT:\n{transcript}",
        "stream": False,
    }
    r = requests.post(OLLAMA_GENERATE_URL, json=payload, timeout=300)
    r.raise_for_status()
    return r.json().get("response", "").strip()


def slugify(name: str) -> str:
    name = name.lower().strip()
    name = re.sub(r"[^a-z0-9]+", "_", name)
    return name[:40]


def save_to_vault(patient_id: str, llm_out: str) -> None:
    patient_dir = VAULT_DIR / f"patient_{patient_id}" / "notes"
    patient_dir.mkdir(parents=True, exist_ok=True)
    (patient_dir / f"{now_stamp()}.txt").write_text(llm_out)


def load_session(session_path: Path) -> dict:
    meta_file = session_path / "meta.json"
    return json.loads(meta_file.read_text()) if meta_file.exists() else {}


# ──────────────────────────────────────────────
# Sidebar
# ──────────────────────────────────────────────

with st.sidebar:
    st.markdown("## ⚙️ Settings")
    st.markdown("---")

    whisper_size = st.selectbox(
        "Whisper model size",
        options=["tiny.en", "base.en", "small.en", "medium.en", "large-v3"],
        index=2,
        help="small.en is fast and accurate. large-v3 is best but slower.",
    )

    ollama_running, pulled_models = check_ollama()
    if ollama_running and pulled_models:
        ollama_model = st.selectbox("Ollama model", options=pulled_models, index=0)
    else:
        ollama_model = st.text_input(
            "Ollama model",
            value="llama3.2:3b",
            help="Run: ollama pull llama3.2:3b",
        )

    st.markdown("---")
    st.markdown("**Privacy controls**")
    keep_audio = st.checkbox("Keep audio (.wav) after transcription", value=False)
    skip_llm   = st.checkbox("Skip LLM step (transcription only)",    value=False)

    st.markdown("---")
    st.markdown("**System status**")

    whisper_ok = check_faster_whisper()
    wstatus = "status-ready" if whisper_ok else "status-error"
    wlabel  = "✓ faster-whisper ready" if whisper_ok else "✗ Run install script first"
    st.markdown(f'<span class="status-pill {wstatus}">{wlabel}</span>', unsafe_allow_html=True)
    st.markdown("")

    ostatus = "status-ready" if ollama_running else "status-warn"
    olabel  = f"✓ Ollama running ({len(pulled_models)} models)" if ollama_running else "⚠ Ollama not running"
    st.markdown(f'<span class="status-pill {ostatus}">{olabel}</span>', unsafe_allow_html=True)

    if not ollama_running:
        if IS_WINDOWS:
            st.caption("Run: Start the Ollama app from Start Menu")
        else:
            st.caption("Run: `ollama serve` in a terminal")

    st.markdown("---")
    st.caption(f"Murmur v0.2 · {'Windows' if IS_WINDOWS else 'macOS'} · All local · No cloud")


# ──────────────────────────────────────────────
# Header
# ──────────────────────────────────────────────

st.markdown("""
<div class="murmur-header">
  <div class="murmur-logo">🔇</div>
  <div class="murmur-title">Murmur</div>
</div>
<div class="murmur-tagline">Local voice · local AI · zero cloud · zero leaks</div>
""", unsafe_allow_html=True)
st.markdown("---")


# ──────────────────────────────────────────────
# Mode + Patient
# ──────────────────────────────────────────────

col_mode, col_patient = st.columns([1, 2])

with col_mode:
    mode = st.radio("Mode", ["🩺 Clinical", "💼 General"], horizontal=True)
    is_clinical = mode.startswith("🩺")

with col_patient:
    if is_clinical:
        patient_name = st.text_input(
            "Patient context (first name or ID — never full PHI here)",
            placeholder="e.g. Maria K. or #10342",
            value=st.session_state.get("last_patient", ""),
        )
        if patient_name:
            st.session_state["last_patient"] = patient_name
            patient_id = slugify(patient_name)
            st.caption(f"Vault key: `patient_{patient_id}`")
        else:
            patient_id = None
            st.caption("⚠️ No patient selected — session won't be saved to vault")
    else:
        patient_id   = None
        patient_name = ""


# ──────────────────────────────────────────────
# Recording controls
# ──────────────────────────────────────────────

st.markdown("---")
col_rec, col_dur = st.columns([2, 3])
with col_rec:
    record_btn = st.button("🎙️  Record & Transcribe", type="primary")
with col_dur:
    duration = st.slider("Recording duration (seconds)", 5, 180, 20, 5)


# ──────────────────────────────────────────────
# Core pipeline
# ──────────────────────────────────────────────

if record_btn:
    if not whisper_ok:
        st.error("faster-whisper not installed. Run the install script first.")
        st.stop()

    stamp       = now_stamp()
    session_dir = SESSIONS_DIR / stamp
    session_dir.mkdir(parents=True, exist_ok=True)

    wav_path  = session_dir / "recording.wav"
    txt_path  = session_dir / "transcript.txt"
    llm_path  = session_dir / "llm_output.txt"
    meta_path = session_dir / "meta.json"

    # ── Record
    with st.spinner(f"🎙️  Recording for {duration} seconds… speak now"):
        try:
            record_mic(wav_path, duration)
        except Exception as e:
            st.error(f"Recording failed: {e}\n\nCheck that a microphone is connected and allowed.")
            st.stop()

    st.success("✓ Recording complete")
    if keep_audio and wav_path.exists():
        st.audio(str(wav_path))

    # ── Transcribe
    with st.spinner("✏️  Transcribing locally with faster-whisper…"):
        try:
            transcript = transcribe(wav_path, whisper_size)
            txt_path.write_text(transcript)
        except Exception as e:
            st.error(f"Transcription failed: {e}")
            st.stop()

    if not transcript.strip():
        st.warning("Whisper returned an empty transcript. Check your mic and try again.")
    else:
        st.success("✓ Transcription complete")

    if not keep_audio and wav_path.exists():
        wav_path.unlink(missing_ok=True)

    st.markdown('<div class="card-label">Transcript</div>', unsafe_allow_html=True)
    transcript = st.text_area(
        "transcript_area",
        value=transcript,
        height=180,
        label_visibility="collapsed",
        key="transcript_display",
    )

    llm_out = ""

    # ── LLM
    if not skip_llm and transcript.strip():
        if not ollama_running:
            st.warning("⚠️  Ollama is not running. Start it, then try again.")
        else:
            prompt = CLINICAL_PROMPT if is_clinical else GENERAL_PROMPT
            with st.spinner(f"🧠  Thinking with {ollama_model} (local)…"):
                try:
                    llm_out = run_ollama(transcript, ollama_model, prompt)
                    llm_path.write_text(llm_out)
                    st.success("✓ LLM processing complete")
                except Exception as e:
                    st.warning(f"LLM step failed: {e}\n\nIs `{ollama_model}` pulled?")

            if llm_out:
                def extract_section(text: str, label: str) -> str:
                    m = re.search(rf"{label}:(.*?)(?=\n[A-Z]{{2,}}:|$)", text, re.S | re.I)
                    return m.group(1).strip() if m else ""

                section_names = ["CLEANED", "SUMMARY", "SOAP", "TASKS"] if is_clinical \
                                else ["CLEANED", "SUMMARY", "TASKS"]
                sections = {s: extract_section(llm_out, s) for s in section_names}

                tabs = st.tabs(list(sections.keys()) + ["Raw output"])
                for tab, (sec, content) in zip(tabs[:-1], sections.items()):
                    with tab:
                        st.markdown(content if content else "_No output for this section._")
                with tabs[-1]:
                    st.text_area("raw_llm", value=llm_out, height=300, label_visibility="collapsed")

    if is_clinical and patient_id and llm_out:
        save_to_vault(patient_id, llm_out)
        st.caption(f"📂 Saved to patient vault: `vault/patient_{patient_id}/`")

    meta_path.write_text(json.dumps({
        "timestamp":       stamp,
        "mode":            "clinical" if is_clinical else "general",
        "patient_id":      patient_id,
        "duration_seconds": duration,
        "whisper_size":    whisper_size,
        "ollama_model":    ollama_model if not skip_llm else None,
        "kept_audio":      keep_audio,
        "platform":        platform.system(),
    }, indent=2))


# ──────────────────────────────────────────────
# Session History
# ──────────────────────────────────────────────

st.markdown("---")
st.markdown("#### 📁 Recent sessions")
sessions = sorted([p for p in SESSIONS_DIR.iterdir() if p.is_dir()], reverse=True)[:8]

if not sessions:
    st.caption("No sessions yet. Record something above.")
else:
    for s in sessions:
        meta = load_session(s)
        mode_label     = "🩺" if meta.get("mode") == "clinical" else "💼"
        patient_label  = f" · {meta['patient_id']}" if meta.get("patient_id") else ""
        duration_label = f" · {meta.get('duration_seconds','?')}s" if meta.get("duration_seconds") else ""
        st.markdown(
            f'<div class="session-item">{mode_label} {s.name}{patient_label}{duration_label}</div>',
            unsafe_allow_html=True,
        )

    with st.expander("🔍 Inspect a session"):
        chosen = st.selectbox("Pick session", [s.name for s in sessions])
        if chosen:
            for f in sorted((SESSIONS_DIR / chosen).iterdir()):
                if f.suffix in (".txt", ".json"):
                    st.markdown(f"**{f.name}**")
                    st.text_area(f.name, f.read_text(errors="ignore"), height=120,
                                 label_visibility="collapsed", key=f"i_{f.name}_{chosen}")
