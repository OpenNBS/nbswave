import pynbs

from nbsaudio.main import render_audio

path = "test.nbs"
song = pynbs.read(path)

output = "test.mp3"

render_audio(song, output)
