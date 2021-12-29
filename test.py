import time

import pynbs

from nbsaudio.main import render_audio

path = "test.nbs"
song = pynbs.read(path)

output = "test.mp3"

start = time.time()
render_audio(song, output)
end = time.time()

print(f"Done! Took {end-start:.2f} seconds")
