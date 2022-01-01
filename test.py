import os
import time

import pynbs

from nbsaudio.main import render_audio

path = "test.nbs"
song = pynbs.read(path)

output = "test.mp3"

custom_sound_path = os.path.join(
    os.environ["USERPROFILE"], "Minecraft Note Block Studio", "Data", "Sounds"
)
custom_sound_path = custom_sound_path.replace("C:", "D:")
print(custom_sound_path)

start = time.time()
render_audio(song, output, custom_sound_path=custom_sound_path, format="mp3")
end = time.time()

print(f"Done! Took {end-start:.2f} seconds")
