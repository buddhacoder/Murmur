import sounddevice as sd
import numpy as np
import mlx_whisper

SAMPLE_RATE = 16_000
duration = 4

print("Devices:")
print(sd.query_devices())

print(f"\nRecording {duration} seconds from default device...")
recording = sd.rec(int(duration * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=1, dtype='int16')
sd.wait()

raw_rms = np.sqrt(np.mean(recording.astype(np.float32)**2))
print(f"Raw RMS: {raw_rms:.2f}")

audio_float = recording.astype(np.float32).flatten() / 32768.0

# Apply DIGITAL_GAIN
DIGITAL_GAIN = 15.0
audio_float = audio_float * DIGITAL_GAIN

gained_rms = np.sqrt(np.mean((recording.astype(np.float32) * DIGITAL_GAIN)**2))
print(f"Gained RMS: {gained_rms:.2f}")

WHISPER_MODEL = "mlx-community/whisper-small.en-mlx"
result = mlx_whisper.transcribe(
    audio_float, 
    path_or_hf_repo=WHISPER_MODEL,
    condition_on_previous_text=False,
    no_speech_threshold=0.8,
    compression_ratio_threshold=2.0
)
print("\nTranscription:", result.get("text", ""))
