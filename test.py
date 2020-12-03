import nbs_to_audio
import pynbs


path = "test.nbs"
song = pynbs.read(path)

output = "test.mp3"

handle = nbs_to_audio.render_audio(song, output)