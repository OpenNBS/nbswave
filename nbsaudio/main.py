# TODO:
# Add progress reports
# Add logging
# Add looping
# Add fadeout
# Allow exporting layers separately. grouping layers with the same name
# Add different naming conventions for layers
# Prevent normalization making output gain too low when song clips

# TODO: optimize and avoid gain/pitch/key calculation if default value!
# TODO: ignore locked layers
# TODO: pan has a loudness compensation? https://github.com/jiaaro/pydub/blob/master/API.markdown#audiosegmentpan
# TODO: Export individual tracks based on layers or layer groups


import io
import os
import zipfile
from typing import BinaryIO, Iterable, Optional, Union

import pydub
import pynbs

from . import audio, nbs

SOUNDS_PATH = "sounds"

DEFAULT_INSTRUMENTS = [
    "harp.ogg",
    "dbass.ogg",
    "bdrum.ogg",
    "sdrum.ogg",
    "click.ogg",
    "guitar.ogg",
    "flute.ogg",
    "bell.ogg",
    "icechime.ogg",
    "xylobone.ogg",
    "iron_xylophone.ogg",
    "cow_bell.ogg",
    "didgeridoo.ogg",
    "bit.ogg",
    "banjo.ogg",
    "pling.ogg",
]


def load_default_instruments() -> dict[int, pydub.AudioSegment]:
    segments = {}
    for index, ins in enumerate(DEFAULT_INSTRUMENTS):
        filename = os.path.join(os.getcwd(), SOUNDS_PATH, ins)
        sound = audio.load_sound(filename)
        segments[index] = sound
    return segments


def load_custom_instruments(
    song: pynbs.File, path: Union[str, zipfile.ZipFile, BinaryIO]
) -> dict[int, pydub.AudioSegment]:
    segments = {}

    zip_file = None
    for ins in song.instruments:
        # ZipFile object
        if isinstance(path, zipfile.ZipFile):
            zip_file = path
            file = io.BytesIO(zip_file.read(ins.file))
        # File-like object
        elif isinstance(path, str) and os.path.splitext(path)[1] == ".zip":
            zip_file = zipfile.ZipFile(path, "r")
            file = io.BytesIO(zip_file.read(ins.file))
        # File path
        else:
            file = os.path.join(path, ins.file)
        sound = audio.load_sound(file)
        segments[ins.id] = sound

    if zip_file is not None:
        zip_file.close()

    return segments


class SongRenderer:
    def __init__(self, song: nbs.Song):
        self._song = song
        self._instruments = load_default_instruments()

    def load_instruments(self, path: Union[str, zipfile.ZipFile, BinaryIO]):
        self._instruments.update(load_custom_instruments(self._song, path))

    def missing_instruments(self):
        return [
            instrument
            for instrument in self._song.instruments
            if instrument.id not in self._instruments
        ]

    def mix_song(self):
        return self._mix(self._song.sorted_notes())

    def mix_layers(self):
        for id, notes in self._song.notes_by_layer():
            yield self._mix(notes)

        return self._mix(self._song.sorted_notes())


def render_audio(
    song: pynbs.File,
    output_path: str,
    default_sound_path: str = None,
    custom_sound_path: str = SOUNDS_PATH,
    start: int = None,
    end: int = None,
    loops: int = 0,
    fadeout: Union[int, float] = 0,
    format: str = "wav",
    sample_rate: int = 44100,
    channels: int = 2,
    bit_depth: int = 24,
    target_bitrate: int = 320,
    target_size: int = None,
    headroom: float = -3.0,
) -> None:

    if isinstance(song, pynbs.File):
        song = nbs.Song(song)

    renderer = SongRenderer(song)
    renderer.mix_song().save(output_path)
