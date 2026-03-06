import sys
from typing import Optional

def get_frontmost_app_name() -> str:
    """Returns the name of the currently active macOS or Windows application."""
    if sys.platform == "darwin":
        try:
            import AppKit
            workspace = AppKit.NSWorkspace.sharedWorkspace()
            active_app = workspace.frontmostApplication()
            if active_app:
                return active_app.localizedName() or ""
        except ImportError:
            pass
    elif sys.platform == "win32":
        try:
            import pygetwindow as gw
            window = gw.getActiveWindow()
            if window and hasattr(window, 'title'):
                return window.title or ""
        except ImportError:
            pass
    return ""

def get_contextual_prompt(app_name: str, smart_mode: str) -> str:
    """
    Given the frontmost application and the user's chosen smart mode,
    return a system prompt suitable for post-processing the raw dictate.
    """
    # 1. Base instruction based on user's mode
    if smart_mode == "SOAP Note":
        system_msg = "You are a medical scribe. Convert the following dictated text into a professional, structured SOAP note. Extract Subjective, Objective, Assessment, and Plan. Do not add fictitious medical data. Output ONLY the formatted note."
    elif smart_mode == "Patient Message":
        system_msg = "You are a doctor writing a warm, professional, empathy-driven message to a patient. Convert the following dictated thoughts into a direct message to the patient. Output ONLY the drafted message."
    elif smart_mode == "Formal Email":
        system_msg = "Convert the following dictated text into a formal, professional email. Output ONLY the drafted email body."
    elif smart_mode == "Fix Clinical Terms":
        system_msg = "You are a medical transcription editor. Fix any grammatical errors, incorrect medical terminology, or formatting mistakes in the following text. Do not summarize or change the fundamental meaning. Output ONLY the corrected text."
    elif smart_mode == "Coding (Code only)":
        system_msg = "You are an expert software developer. Convert the following dictated thoughts into clean, highly optimized code or clear, professional code comments. Infer the intended programming language from context. Do NOT output any markdown blocks (like ```python). Output ONLY the code or comments so it can be pasted directly into an IDE."
    elif smart_mode == "Casual Chat":
        system_msg = "You are a transcription assistant. Fix spelling and grammar errors in the following text, but keep the tone extremely casual and very concise, suitable for a quick Slack or Discord message. Output ONLY the corrected text."
    else: # "Off" or unknown
        return ""

    # 2. Add application context hints if applicable
    app_lower = app_name.lower()
    app_hints = []
    if "epic" in app_lower or "cerner" in app_lower or "athena" in app_lower or "emr" in app_lower:
        app_hints.append("Context: The user is dictating directly into an Electronic Medical Record (EMR) system. Use standard medical abbreviations.")
    elif "outlook" in app_lower or "mail" in app_lower or "spark" in app_lower:
        app_hints.append("Context: The user is drafting an email. Ensure proper greeting/sign-off formatting if appropriate.")
    elif "messages" in app_lower or "slack" in app_lower or "teams" in app_lower or "discord" in app_lower:
        app_hints.append("Context: The user is dictating a quick chat message into a messaging app. Keep it concise.")
    elif "cursor" in app_lower or "vscode" in app_lower or "xcode" in app_lower or "windsurf" in app_lower:
        app_hints.append("Context: The user is dictating directly into a code editor. Prioritize formatting as valid code blocks, docstrings, or inline comments.")
    elif "terminal" in app_lower or "iterm" in app_lower:
        app_hints.append("Context: The user is dictating into a terminal/command line. Format the output as valid shell commands if appropriate.")

    if app_hints:
        system_msg += "\n\n" + "\n".join(app_hints)

    return system_msg
