import sounddevice as sd
import numpy as np
import time

def print_sound(indata, outdata, frames, time_info, status):
    volume_norm = np.linalg.norm(indata)*10
    print("|" * int(volume_norm))

print("Listening for 5 seconds to verify mic input...")
with sd.Stream(callback=print_sound):
    time.sleep(5)
