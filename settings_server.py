"""
Murmur Settings Server  —  v2 clean redesign
Opens in Chrome --app mode so it looks like a real native window.
"""

import json
import os
import subprocess
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Optional

SETTINGS_FILE = Path(__file__).parent / "murmur_settings.json"
PORT = 7734

DEFAULT_SETTINGS = {
    "sound_effects": True,
    "show_mini_pill": True,
    "model": "mlx-community/whisper-small.en-mlx",
    "language": "en",
    "silence_threshold": 450,
    "dictionary": [],
    "snippets": [],
}


def load_settings() -> dict:
    if SETTINGS_FILE.exists():
        try:
            return {**DEFAULT_SETTINGS, **json.loads(SETTINGS_FILE.read_text())}
        except Exception:
            pass
    return dict(DEFAULT_SETTINGS)


def save_settings(data: dict) -> None:
    SETTINGS_FILE.write_text(json.dumps(data, indent=2))


# ─────────────────────────────────────────────────────────────────────────────
HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Murmur</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --font: 'Inter', -apple-system, BlinkMacSystemFont, 'SF Pro Display', sans-serif;
  --bg:         #f5f5f7;
  --sidebar-bg: #f9f9fb;
  --content-bg: #ffffff;
  --card-bg:    #ffffff;
  --accent:     #6c47ff;
  --accent-dim: rgba(108, 71, 255, 0.10);
  --text:       #1d1d1f;
  --muted:      #86868b;
  --border:     rgba(0,0,0,0.07);
  --divider:    rgba(0,0,0,0.05);
  --shadow-sm:  0 1px 2px rgba(0,0,0,0.04), 0 4px 12px rgba(0,0,0,0.05);
  --shadow-md:  0 2px 8px rgba(0,0,0,0.06), 0 12px 32px rgba(0,0,0,0.06);
  --radius-card: 14px;
  --radius-btn:  8px;
  --green:      #30d158;
  --red:        #ff3b30;
}

html, body {
  height: 100%;
  font-family: var(--font);
  font-size: 14px;
  color: var(--text);
  background: var(--bg);
  -webkit-font-smoothing: antialiased;
  overflow: hidden;
}

.app { display: flex; height: 100vh; }

/* ───────── SIDEBAR ───────── */
.sidebar {
  width: 232px;
  min-width: 232px;
  background: var(--sidebar-bg);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  padding: 0;
  user-select: none;
  overflow: hidden;
}

.sidebar-header {
  padding: 28px 20px 20px;
  border-bottom: 1px solid var(--divider);
}

.app-logo {
  display: flex;
  align-items: center;
  gap: 12px;
}

.logo-mark {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  overflow: hidden;
  flex-shrink: 0;
  box-shadow: 0 2px 8px rgba(108,71,255,0.25);
}

.logo-mark img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.app-name {
  font-size: 16px;
  font-weight: 700;
  letter-spacing: -0.3px;
  color: var(--text);
}

.app-tagline {
  font-size: 11px;
  color: var(--muted);
  margin-top: 1px;
  font-weight: 400;
}

.nav-section {
  flex: 1;
  padding: 12px 10px;
  overflow-y: auto;
}

.nav-label {
  font-size: 10px;
  font-weight: 600;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.7px;
  padding: 10px 10px 6px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 12px;
  border-radius: 9px;
  cursor: pointer;
  font-size: 13.5px;
  font-weight: 500;
  color: var(--muted);
  transition: background 0.12s, color 0.12s;
  margin-bottom: 1px;
}

.nav-item:hover {
  background: rgba(0,0,0,0.04);
  color: var(--text);
}

.nav-item.active {
  background: var(--accent-dim);
  color: var(--accent);
  font-weight: 600;
}

.nav-icon {
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  opacity: 0.75;
  flex-shrink: 0;
}
.nav-item.active .nav-icon { opacity: 1; }

.sidebar-footer {
  padding: 14px 20px;
  border-top: 1px solid var(--divider);
}

.status-dot {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 11.5px;
  color: var(--muted);
}

.dot {
  width: 7px;
  height: 7px;
  background: var(--green);
  border-radius: 50%;
  flex-shrink: 0;
  box-shadow: 0 0 0 2px rgba(48,209,88,0.20);
}

/* ───────── MAIN CONTENT ───────── */
.content {
  flex: 1;
  background: var(--content-bg);
  overflow-y: auto;
  padding: 36px 40px 80px;
}

.page { display: none; }
.page.active { display: block; }

.page-header { margin-bottom: 28px; }

.page-title {
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -0.5px;
  color: var(--text);
}

.page-sub {
  font-size: 13px;
  color: var(--muted);
  margin-top: 5px;
  line-height: 1.5;
}

/* ───────── CARDS ───────── */
.card {
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
  margin-bottom: 20px;
}

.card-section-title {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.6px;
  color: var(--muted);
  padding: 16px 20px 10px;
}

/* ───────── ROWS ───────── */
.row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 20px;
  border-bottom: 1px solid var(--divider);
  min-height: 54px;
  gap: 16px;
}

.row:last-child { border-bottom: none; }

.row-info { flex: 1; min-width: 0; }

.row-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--text);
}

.row-desc {
  font-size: 12px;
  color: var(--muted);
  margin-top: 2px;
  line-height: 1.5;
}

.row-value {
  font-size: 13px;
  color: var(--muted);
  white-space: nowrap;
}

/* ───────── TOGGLE ───────── */
.toggle { position: relative; width: 44px; height: 24px; flex-shrink: 0; }
.toggle input { position: absolute; opacity: 0; width: 0; height: 0; }

.track {
  position: absolute;
  inset: 0;
  border-radius: 12px;
  background: #dde1e7;
  cursor: pointer;
  transition: background 0.2s;
}

.toggle input:checked ~ .track { background: var(--green); }

.knob {
  position: absolute;
  top: 3px;
  left: 3px;
  width: 18px;
  height: 18px;
  background: #fff;
  border-radius: 50%;
  box-shadow: 0 1px 3px rgba(0,0,0,0.25);
  transition: transform 0.2s;
  pointer-events: none;
}

.toggle input:checked ~ .track .knob { transform: translateX(20px); }

/* ───────── SELECT ───────── */
select {
  appearance: none;
  background: var(--bg);
  border: 1px solid rgba(0,0,0,0.10);
  border-radius: 7px;
  padding: 7px 32px 7px 12px;
  font-family: var(--font);
  font-size: 13px;
  font-weight: 500;
  color: var(--text);
  cursor: pointer;
  outline: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6'%3E%3Cpath d='M1 1l4 4 4-4' stroke='%2386868b' stroke-width='1.5' fill='none' stroke-linecap='round'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 10px center;
  transition: border-color 0.15s;
}

select:focus { border-color: var(--accent); }

/* ───────── SLIDER ───────── */
input[type=range] {
  -webkit-appearance: none;
  width: 140px;
  height: 4px;
  background: #dde1e7;
  border-radius: 2px;
  outline: none;
  cursor: pointer;
}
input[type=range]::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 16px;
  height: 16px;
  background: var(--accent);
  border-radius: 50%;
  box-shadow: 0 1px 4px rgba(0,0,0,0.2);
}

/* ───────── STATS ───────── */
.stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin-bottom: 24px; }

.stat {
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-sm);
  padding: 20px;
  text-align: center;
}

.stat-num {
  font-size: 30px;
  font-weight: 700;
  letter-spacing: -1px;
  color: var(--accent);
  line-height: 1;
}

.stat-label {
  font-size: 11.5px;
  color: var(--muted);
  margin-top: 6px;
  font-weight: 500;
}

/* ───────── TRANSCRIPTS ───────── */
.tx-item {
  padding: 14px 20px;
  border-bottom: 1px solid var(--divider);
}
.tx-item:last-child { border-bottom: none; }

.tx-time {
  font-size: 11px;
  font-weight: 600;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.4px;
  margin-bottom: 5px;
}

.tx-text {
  font-size: 13.5px;
  color: var(--text);
  line-height: 1.55;
}

.empty-state {
  padding: 40px 20px;
  text-align: center;
  color: var(--muted);
  font-size: 13px;
}

.empty-icon { font-size: 28px; margin-bottom: 10px; opacity: 0.5; }

/* ───────── WORD LIST ───────── */
.word-list { padding: 12px 20px; display: flex; flex-direction: column; gap: 8px; }

.word-chip {
  display: flex;
  align-items: center;
  gap: 10px;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 10px 14px;
}

.word-trigger {
  flex: 0 0 auto;
  font-family: 'SF Mono', Menlo, monospace;
  font-size: 12.5px;
  font-weight: 600;
  color: var(--accent);
  background: var(--accent-dim);
  padding: 3px 8px;
  border-radius: 5px;
}

.word-arrow { color: var(--muted); font-size: 12px; }

.word-expand { flex: 1; font-size: 13px; color: var(--text); }

.word-text {
  flex: 1;
  font-size: 13.5px;
  color: var(--text);
}

.btn-remove {
  background: none;
  border: none;
  color: var(--muted);
  cursor: pointer;
  font-size: 18px;
  line-height: 1;
  padding: 0;
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  transition: background 0.12s, color 0.12s;
}
.btn-remove:hover { background: rgba(255,59,48,0.1); color: var(--red); }

/* ───────── ADD ROW ───────── */
.add-area { padding: 14px 20px 16px; border-top: 1px solid var(--divider); }

.input-row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }

.field {
  flex: 1;
  background: var(--bg);
  border: 1px solid rgba(0,0,0,0.10);
  border-radius: 8px;
  padding: 9px 13px;
  font-family: var(--font);
  font-size: 13px;
  color: var(--text);
  outline: none;
  transition: border-color 0.15s, box-shadow 0.15s;
  min-width: 120px;
}

.field:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px rgba(108,71,255,0.12);
}

.field::placeholder { color: #b0b0b8; }

/* ───────── BUTTONS ───────── */
.btn {
  font-family: var(--font);
  font-size: 13px;
  font-weight: 600;
  border-radius: var(--radius-btn);
  padding: 9px 18px;
  border: none;
  cursor: pointer;
  transition: opacity 0.15s, box-shadow 0.15s;
  white-space: nowrap;
}

.btn-primary {
  background: var(--accent);
  color: #fff;
  box-shadow: 0 1px 4px rgba(108,71,255,0.3);
}
.btn-primary:hover { opacity: 0.88; }

.btn-secondary {
  background: var(--bg);
  color: var(--text);
  border: 1px solid rgba(0,0,0,0.10);
}
.btn-secondary:hover { border-color: rgba(0,0,0,0.20); }

/* ───────── SAVE BAR ───────── */
.save-bar {
  position: fixed;
  bottom: 0;
  left: 232px;
  right: 0;
  background: rgba(255,255,255,0.9);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border-top: 1px solid var(--border);
  padding: 14px 40px;
  display: flex;
  align-items: center;
  gap: 10px;
  z-index: 100;
}

.save-confirm {
  font-size: 13px;
  color: var(--green);
  font-weight: 500;
  display: none;
}

/* ───────── INFO BOX ───────── */
.info-box {
  background: rgba(108,71,255,0.06);
  border: 1px solid rgba(108,71,255,0.15);
  border-radius: 10px;
  padding: 14px 18px;
  margin: 14px 20px 16px;
  font-size: 13px;
  color: var(--muted);
  line-height: 1.6;
}

/* ───────── ABOUT ───────── */
.about-hero {
  text-align: center;
  padding: 40px 20px 28px;
  border-bottom: 1px solid var(--divider);
}

.about-mark {
  width: 80px;
  height: 80px;
  background: linear-gradient(145deg, #6c47ff, #a855f7);
  border-radius: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 40px;
  margin: 0 auto 18px;
  box-shadow: 0 4px 20px rgba(108,71,255,0.30);
}

.about-name { font-size: 20px; font-weight: 700; letter-spacing: -0.5px; }
.about-ver  { font-size: 12.5px; color: var(--muted); margin-top: 4px; }
.about-desc {
  font-size: 13.5px;
  color: var(--muted);
  line-height: 1.65;
  max-width: 380px;
  margin: 16px auto 0;
}

.badge-row { display: flex; gap: 8px; flex-wrap: wrap; justify-content: center; margin-top: 16px; }

.badge {
  font-size: 11.5px;
  font-weight: 500;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 20px;
  padding: 4px 12px;
  color: var(--muted);
}

/* ───────── UTILITIES ───────── */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(0,0,0,0.12); border-radius: 3px; }

.quick-ref-key {
  font-family: 'SF Mono', Menlo, monospace;
  font-size: 12px;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 5px;
  padding: 3px 8px;
  color: var(--accent);
  font-weight: 600;
}
</style>
</head>
<body>
<div class="app">

<!-- ── Sidebar ── -->
<div class="sidebar">
  <div class="sidebar-header">
    <div class="app-logo">
      <div class="logo-mark"><img src="/api/icon" alt="Murmur"></div>
      <div>
        <div class="app-name">Murmur</div>
        <div class="app-tagline">Local voice dictation</div>
      </div>
    </div>
  </div>

  <div class="nav-section">
    <div class="nav-label">General</div>
    <div class="nav-item active" onclick="show('home')" id="nav-home">
      <div class="nav-icon">◉</div> Home
    </div>
    <div class="nav-item" onclick="show('dictionary')" id="nav-dictionary">
      <div class="nav-icon">≡</div> Dictionary
    </div>
    <div class="nav-item" onclick="show('snippets')" id="nav-snippets">
      <div class="nav-icon">⌘</div> Snippets
    </div>

    <div class="nav-label" style="margin-top:10px">Preferences</div>
    <div class="nav-item" onclick="show('settings')" id="nav-settings">
      <div class="nav-icon">⚙</div> Settings
    </div>
    <div class="nav-item" onclick="show('about')" id="nav-about">
      <div class="nav-icon">ⓘ</div> About
    </div>
  </div>

  <div class="sidebar-footer">
    <div class="status-dot">
      <div class="dot"></div>
      Murmur is running
    </div>
  </div>
</div>

<!-- ── Content ── -->
<div class="content">

  <!-- HOME -->
  <div class="page active" id="page-home">
    <div class="page-header">
      <div class="page-title" id="greeting">Good evening</div>
      <div class="page-sub">Your private, on-device voice dictation tool.</div>
    </div>

    <div class="stats">
      <div class="stat">
        <div class="stat-num" id="stat-words">—</div>
        <div class="stat-label">Words today</div>
      </div>
      <div class="stat">
        <div class="stat-num" id="stat-sessions">—</div>
        <div class="stat-label">Sessions today</div>
      </div>
      <div class="stat">
        <div class="stat-num" id="stat-total">—</div>
        <div class="stat-label">Total words</div>
      </div>
    </div>

    <div class="card">
      <div class="card-section-title">Recent Transcripts</div>
      <div id="tx-list">
        <div class="empty-state">
          <div class="empty-icon">🎙</div>
          Hold Right ⌥ to start your first dictation.
        </div>
      </div>
    </div>

    <div class="card">
      <div class="card-section-title">Quick Reference</div>
      <div class="row">
        <div class="row-info"><div class="row-title">Start / stop dictation</div></div>
        <span class="quick-ref-key">Hold Right ⌥</span>
      </div>
      <div class="row">
        <div class="row-info"><div class="row-title">Paste last transcript</div></div>
        <div class="row-value">Menu bar → Paste last</div>
      </div>
      <div class="row">
        <div class="row-info"><div class="row-title">Active model</div></div>
        <div class="row-value" id="home-model">—</div>
      </div>
      <div class="row" style="margin-top: -8px; border-top: none;">
        <div class="row-info"><div class="row-title">Smart text</div></div>
        <div class="row-value" id="home-smart">—</div>
      </div>
    </div>
  </div>

  <!-- DICTIONARY -->
  <div class="page" id="page-dictionary">
    <div class="page-header">
      <div class="page-title">Dictionary</div>
      <div class="page-sub">Words Whisper will always transcribe correctly — ideal for names, medications, acronyms.</div>
    </div>

    <div class="card">
      <div class="card-section-title">Custom Words</div>
      <div class="word-list" id="dict-list"></div>
      <div class="add-area">
        <div class="input-row">
          <input class="field" id="dict-input" placeholder="Type a word…" onkeydown="if(event.key==='Enter')addWord()">
          <button class="btn btn-primary" onclick="addWord()">Add word</button>
        </div>
      </div>
    </div>

    <div class="info-box">
      Words here are injected as initial prompt hints to Whisper. Best for proper nouns, drug names, specialty terms — e.g. <strong>HIPAA</strong>, <strong>propofol</strong>, <strong>fascia</strong>.
    </div>
  </div>

  <!-- SNIPPETS -->
  <div class="page" id="page-snippets">
    <div class="page-header">
      <div class="page-title">Snippets</div>
      <div class="page-sub">Say a trigger phrase and Murmur expands it to template text. Perfect for recurring clauses.</div>
    </div>

    <div class="card">
      <div class="card-section-title">Trigger → Expansion</div>
      <div class="word-list" id="snip-list"></div>
      <div class="add-area">
        <div class="input-row">
          <input class="field" id="snip-trigger" placeholder="Trigger phrase…">
          <input class="field" id="snip-expand" placeholder="Expands to…" style="flex:2" onkeydown="if(event.key==='Enter')addSnippet()">
          <button class="btn btn-primary" onclick="addSnippet()">Add</button>
        </div>
      </div>
    </div>
  </div>

  <!-- SETTINGS -->
  <div class="page" id="page-settings">
    <div class="page-header">
      <div class="page-title">Settings</div>
      <div class="page-sub">Changes are applied after saving.</div>
    </div>

    <div class="card">
      <div class="card-section-title">Transcription</div>
      <div class="row">
        <div class="row-info">
          <div class="row-title">Whisper Model</div>
          <div class="row-desc">Larger models are slower but more accurate. Restart required.</div>
        </div>
        <select id="s-model" onchange="dirty()">
          <option value="mlx-community/whisper-tiny.en-mlx">Tiny (fastest)</option>
          <option value="mlx-community/whisper-small.en-mlx">Small (recommended)</option>
          <option value="mlx-community/whisper-medium.en-mlx">Medium (accurate)</option>
          <option value="mlx-community/whisper-large-v3-mlx">Large v3 (best quality)</option>
        </select>
      </div>
      <div class="row">
        <div class="row-info">
          <div class="row-title">Language</div>
          <div class="row-desc">Language used during dictation</div>
        </div>
        <select id="s-lang" onchange="dirty()">
          <option value="en">English</option>
          <option value="es">Español</option>
          <option value="fr">Français</option>
          <option value="de">Deutsch</option>
          <option value="it">Italiano</option>
          <option value="pt">Português</option>
          <option value="ja">日本語</option>
          <option value="zh">中文</option>
        </select>
      </div>
      <div class="row">
        <div class="row-info">
          <div class="row-title">Smart Text Mode (Local LLM)</div>
          <div class="row-desc">Automatically format dictated text before pasting. Uses Llama-3.2 locally.</div>
        </div>
        <select id="s-smart" onchange="dirty()">
          <option value="Off">Off (Raw Whisper)</option>
          <option value="HIPAA Redaction">HIPAA Redaction (Remove PHI)</option>
          <option value="Fix Clinical Terms">Fix Clinical Terms</option>
          <option value="SOAP Note">SOAP Note</option>
          <option value="Patient Message">Patient Message</option>
          <option value="Formal Email">Formal Email</option>
          <option value="Coding (Code only)">Coding (Code only)</option>
          <option value="Casual Chat">Casual Chat</option>
        </select>
      </div>
      <div class="row">
        <div class="row-info">
          <div class="row-title">Silence sensitivity</div>
          <div class="row-desc" id="thresh-label">Current: 450 RMS</div>
        </div>
        <input type="range" min="200" max="900" step="50" id="s-thresh"
          oninput="document.getElementById('thresh-label').textContent='Current: '+this.value+' RMS'"
          onchange="dirty()">
      </div>
    </div>

    <div class="card">
      <div class="card-section-title">System</div>
      <div class="row">
        <div class="row-info">
          <div class="row-title">Sound effects</div>
          <div class="row-desc">Pop &amp; Tink cues on start and stop</div>
        </div>
        <label class="toggle">
          <input type="checkbox" id="s-sound" onchange="dirty()">
          <div class="track"><div class="knob"></div></div>
        </label>
      </div>
      <div class="row">
        <div class="row-info">
          <div class="row-title">Show mini pill when idle</div>
          <div class="row-desc">Tiny indicator above the Dock when Murmur is ready</div>
        </div>
        <label class="toggle">
          <input type="checkbox" id="s-minipill" onchange="dirty()">
          <div class="track"><div class="knob"></div></div>
        </label>
      </div>
    </div>
  </div>

  <!-- ABOUT -->
  <div class="page" id="page-about">
    <div class="page-header">
      <div class="page-title">About Murmur</div>
    </div>
    <div class="card">
      <div class="about-hero">
        <div class="about-mark"><img src="/api/icon" alt="Murmur" style="width:100%;height:100%;object-fit:cover;border-radius:22px"></div>
        <div class="about-name">Murmur</div>
        <div class="about-ver">v1.0 — Built locally, runs locally</div>
        <div class="about-desc">
          A HIPAA-conscious, on-device voice dictation tool for macOS.
          Every word is processed on your Mac via Apple Silicon. Nothing is sent anywhere.
        </div>
        <div class="badge-row">
          <span class="badge">🔒 100% Local</span>
          <span class="badge">⚡ Metal-accelerated</span>
          <span class="badge">🧠 MLX Whisper</span>
          <span class="badge">🍎 Apple Silicon</span>
        </div>
      </div>
      <div class="card-section-title" style="margin-top:4px">Technology</div>
      <div class="row"><div class="row-title">Speech recognition</div><div class="row-value">mlx-whisper · Whisper Small EN</div></div>
      <div class="row"><div class="row-title">Audio capture</div><div class="row-value">sounddevice / PortAudio</div></div>
      <div class="row"><div class="row-title">UI overlay</div><div class="row-value">PyObjC · AppKit · CALayer</div></div>
      <div class="row"><div class="row-title">Menu bar</div><div class="row-value">rumps</div></div>
      <div class="row"><div class="row-title">Keyboard capture</div><div class="row-value">pynput</div></div>
    </div>
  </div>
</div><!-- /content -->
</div><!-- /app -->

<!-- Save bar (hidden by default) -->
<div class="save-bar" id="save-bar" style="display:none">
  <button class="btn btn-primary" onclick="saveSettings()">Save Changes</button>
  <button class="btn btn-secondary" onclick="cancelChanges()">Cancel</button>
  <span class="save-confirm" id="save-msg">✓ Saved successfully</span>
</div>

<script>
let settings = {}, _dirty = false;

// Navigation
function show(p) {
  document.querySelectorAll('.page').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
  document.getElementById('page-' + p).classList.add('active');
  document.getElementById('nav-' + p).classList.add('active');
}

// Greeting
(function() {
  const h = new Date().getHours();
  const g = h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening';
  document.getElementById('greeting').textContent = g;
})();

// Load settings
async function loadSettings() {
  const r = await fetch('/api/settings');
  settings = await r.json();
  applyUI(settings);
  loadTranscripts();
  loadStats();
}

function applyUI(s) {
  sel('s-model').value    = s.model || 'mlx-community/whisper-small.en-mlx';
  sel('s-lang').value     = s.language || 'en';
  sel('s-smart').value    = s.smart_text_mode || 'Off';
  sel('s-sound').checked  = s.sound_effects !== false;
  sel('s-minipill').checked = s.show_mini_pill !== false;
  sel('s-thresh').value   = s.silence_threshold || 450;
  document.getElementById('thresh-label').textContent = 'Current: ' + (s.silence_threshold || 450) + ' RMS';
  const modelName = (s.model||'').split('/').pop().replace(/-mlx$/,'').replace('whisper-','').replace('.en','');
  document.getElementById('home-model').textContent = 'whisper-' + modelName;
  document.getElementById('home-smart').textContent = (s.smart_text_mode && s.smart_text_mode !== 'Off') ? `On (${s.smart_text_mode})` : 'Off';
  
  renderDict(s.dictionary || []);
  renderSnippets(s.snippets || []);
}

function sel(id) { return document.getElementById(id); }
function dirty() { _dirty=true; document.getElementById('save-bar').style.display='flex'; }

async function saveSettings() {
  const s = {
    ...settings,
    model: sel('s-model').value,
    language: sel('s-lang').value,
    smart_text_mode: sel('s-smart').value,
    sound_effects: sel('s-sound').checked,
    show_mini_pill: sel('s-minipill').checked,
    silence_threshold: +sel('s-thresh').value,
    dictionary: settings.dictionary||[],
    snippets: settings.snippets||[],
  };
  await fetch('/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(s)});
  settings = s;
  _dirty = false;
  const msg = sel('save-msg');
  msg.style.display = 'inline';
  setTimeout(() => { msg.style.display='none'; sel('save-bar').style.display='none'; }, 2000);
}

function cancelChanges() {
  applyUI(settings);
  _dirty = false;
  sel('save-bar').style.display = 'none';
}

// Dictionary
function renderDict(list) {
  const el = sel('dict-list');
  if (!list.length) { el.innerHTML='<div class="empty-state"><div class="empty-icon">≡</div>No custom words yet.</div>'; return; }
  el.innerHTML = list.map((w,i) => `
    <div class="word-chip">
      <span class="word-text">${w}</span>
      <button class="btn-remove" onclick="rmWord(${i})" title="Remove">×</button>
    </div>`).join('');
}
function addWord() {
  const inp=sel('dict-input'), w=inp.value.trim();
  if(!w)return;
  (settings.dictionary=settings.dictionary||[]).push(w);
  renderDict(settings.dictionary);
  inp.value=''; dirty();
}
function rmWord(i) { settings.dictionary.splice(i,1); renderDict(settings.dictionary); dirty(); }

// Snippets
function renderSnippets(list) {
  const el = sel('snip-list');
  if (!list.length) { el.innerHTML='<div class="empty-state"><div class="empty-icon">⌘</div>No snippets yet.</div>'; return; }
  el.innerHTML = list.map((s,i) => `
    <div class="word-chip">
      <span class="word-trigger">${s.trigger}</span>
      <span class="word-arrow">→</span>
      <span class="word-expand">${s.expand}</span>
      <button class="btn-remove" onclick="rmSnip(${i})" title="Remove">×</button>
    </div>`).join('');
}
function addSnippet() {
  const t=sel('snip-trigger').value.trim(), e=sel('snip-expand').value.trim();
  if(!t||!e)return;
  (settings.snippets=settings.snippets||[]).push({trigger:t,expand:e});
  renderSnippets(settings.snippets);
  sel('snip-trigger').value=sel('snip-expand').value=''; dirty();
}
function rmSnip(i) { settings.snippets.splice(i,1); renderSnippets(settings.snippets); dirty(); }

// Transcripts
async function loadTranscripts() {
  const r = await fetch('/api/transcripts');
  const data = await r.json();
  const el = sel('tx-list');
  if (!data.length) { el.innerHTML='<div class="empty-state"><div class="empty-icon">🎙</div>Hold Right ⌥ to start your first dictation.</div>'; return; }
  el.innerHTML = data.slice().reverse().slice(0,20).map(t=>`
    <div class="tx-item">
      <div class="tx-time">${t.time}</div>
      <div class="tx-text">${t.text}</div>
    </div>`).join('');
}

// Stats
async function loadStats() {
  const r = await fetch('/api/stats');
  const s = await r.json();
  sel('stat-words').textContent    = s.words_today ?? '—';
  sel('stat-sessions').textContent = s.sessions_today ?? '—';
  sel('stat-total').textContent    = s.total_words ?? '—';
}

loadSettings();
</script>
</body>
</html>"""


# ── HTTP handler ──────────────────────────────────────────────────────────────

class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/index.html") or self.path.startswith("/#"):
            self._html()
        elif self.path == "/api/settings":    self._json(load_settings())
        elif self.path == "/api/transcripts": self._json(_get_transcripts())
        elif self.path == "/api/stats":       self._json(_get_stats())
        elif self.path == "/api/icon":        self._icon()
        else:                                 self.send_response(404); self.end_headers()

    def do_POST(self):
        if self.path == "/api/settings":
            n = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(n))
            save_settings(data)
            self._json({"ok": True})

    def _icon(self):
        icon_path = Path(__file__).parent / "app_icon.png"
        if icon_path.exists():
            body = icon_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers(); self.wfile.write(body)
        else:
            self.send_response(404); self.end_headers()

    def _html(self):
        body = HTML.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers(); self.wfile.write(body)

    def _json(self, data):
        body = json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers(); self.wfile.write(body)

    def log_message(self, *_): pass


def _get_transcripts() -> list:
    out = []
    sessions_dir = Path(__file__).parent / "sessions"
    for f in sorted(sessions_dir.glob("*.txt"))[-30:]:
        try:
            ts = f.stem[:10] + "  " + f.stem[11:].replace("-", ":")
            out.append({"time": ts, "text": f.read_text().strip()})
        except Exception:
            pass
    return out


def _get_stats() -> dict:
    from datetime import date
    today = date.today().strftime("%Y-%m-%d")
    sessions_dir = Path(__file__).parent / "sessions"
    w_today = s_today = total = 0
    for f in sessions_dir.glob("*.txt"):
        try:
            wc = len(f.read_text().split())
            total += wc
            if f.stem.startswith(today):
                w_today += wc; s_today += 1
        except Exception:
            pass
    return {"words_today": w_today, "sessions_today": s_today, "total_words": total}


# ── Server management ─────────────────────────────────────────────────────────

_server: Optional[HTTPServer] = None
_server_lock = threading.Lock()

def get_chromium_paths():
    import sys
    if sys.platform == "win32":
        return [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"
        ]
    return [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/Applications/Arc.app/Contents/MacOS/Arc",
    ]

_CHROME_PATHS = get_chromium_paths()

def ensure_server() -> None:
    global _server
    with _server_lock:
        if _server is None:
            _server = HTTPServer(("127.0.0.1", PORT), _Handler)
            t = threading.Thread(target=_server.serve_forever, daemon=True)
            t.start()


def open_settings() -> None:
    ensure_server()
    url = f"http://127.0.0.1:{PORT}"
    # Try to open in Chrome --app mode (no browser chrome → looks native)
    for browser in _CHROME_PATHS:
        if os.path.exists(browser):
            subprocess.Popen(
                [browser, f"--app={url}", "--window-size=880,620",
                 "--window-position=240,120"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return
    webbrowser.open(url)   # fallback

