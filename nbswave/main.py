import io
import os
import zipfile
from typing import BinaryIO, Dict, Iterable, Optional, Union

import pydub
import pynbs

from . import audio, nbs

__all__ = ["SongRenderer", "render_audio"]

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

PathLike = Union[str, bytes, os.PathLike]
ZipFileOrPath = Union[PathLike, zipfile.ZipFile, BinaryIO]


class MissingInstrumentException(Exception):
    pass


def load_default_instruments(path: PathLike) -> Dict[int, pydub.AudioSegment]:
    segments = {}
    for index, ins in enumerate(DEFAULT_INSTRUMENTS):
        filename = os.path.join(os.getcwd(), path, ins)
        sound = audio.load_sound(filename)
        segments[index] = sound
    return segments


def load_custom_instruments(
    song: pynbs.File, path: ZipFileOrPath
) -> Dict[int, pydub.AudioSegment]:
    segments = {}

    zip_file = None
    for ins in song.instruments:
        ins_id = ins.id + song.header.default_instruments

        if ins.file == "":
            print(f"Sound file for instrument {ins.name} wasn't assigned; skipping")
            segments[ins_id] = None
            continue

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

        try:
            sound = audio.load_sound(file)
        except FileNotFoundError:
            print(f"Sound file for instrument {ins.file} couldn't be found; skipping")
            continue

        segments[ins_id] = sound

    if zip_file is not None:
        zip_file.close()

    return segments


class SongRenderer:
    def __init__(
        self,
        song: Union[pynbs.File, nbs.Song],
        default_sound_path: Optional[PathLike] = SOUNDS_PATH,
    ):
        if isinstance(song, pynbs.File):
            song = nbs.Song(song)
        self._song = song
        self._instruments = load_default_instruments(default_sound_path)

    def load_instruments(self, path: ZipFileOrPath):
        self._instruments.update(load_custom_instruments(self._song, path))

    def missing_instruments(self):
        return [
            instrument
            for instrument in self._song.instruments
            if instrument.id not in self._instruments
        ]

    def _mix(
        self,
        notes: Iterable[nbs.Note],
        ignore_missing_instruments: bool = False,
        sample_rate: Optional[int] = 44100,
        channels: Optional[int] = 2,
        bit_depth: Optional[int] = 16,
    ) -> audio.Track:
        mixer = audio.Mixer(sample_rate, channels, bit_depth)

        last_ins = None
        last_key = None
        last_vol = None
        last_pan = None

        for note in notes:

            ins = note.instrument
            key = note.key
            vol = note.velocity
            pan = note.panning

            if ins != last_ins:
                last_key = None
                last_vol = None
                last_pan = None

                try:
                    sound1 = self._instruments[note.instrument]
                except KeyError:  # Sound file missing
                    if not ignore_missing_instruments:
                        instrument_data = self._song.instruments[ins]
                        ins_name = instrument_data.name
                        ins_file = instrument_data.file
                        raise MissingInstrumentException(
                            f"The sound file for instrument f{ins_name} was not found: f{ins_file}"
                        )
                    else:
                        continue

                if sound1 is None:  # Sound file not assigned
                    continue

                sound1 = audio.sync(sound1)

            if key != last_key:
                last_vol = None
                last_pan = None
                pitch = audio.key_to_pitch(key)
                sound2 = audio.change_speed(sound1, pitch)

            if vol != last_vol:
                last_pan = None
                gain = audio.vol_to_gain(vol)
                sound3 = sound2.apply_gain(gain)

            if pan != last_pan:
                sound4 = sound3.pan(pan)
                sound = sound4

            last_ins = ins
            last_key = key
            last_vol = vol
            last_pan = pan

            pos = note.tick / self._song.header.tempo * 1000

            mixer.overlay(sound, position=pos)

        return mixer.to_audio_segment()

    def mix_song(self, ignore_missing_instruments=False):
        return self._mix(
            self._song.sorted_notes(),
            ignore_missing_instruments=ignore_missing_instruments,
        )

    def mix_layers(self):
        for id, notes in self._song.notes_by_layer():
            yield self._mix(notes)


def render_audio(
    song_path: PathLike,
    output_path: PathLike,
    default_sound_path: PathLike = SOUNDS_PATH,
    custom_sound_path: PathLike = SOUNDS_PATH,
    start: int = None,
    end: int = None,
    loops: int = 0,
    fadeout: Union[int, float] = 0,
    format: str = "wav",
    sample_rate: int = 44100,
    channels: int = 2,
    bit_depth: int = 16,
    target_bitrate: int = 320,
    target_size: int = None,
    headroom: float = 3.0,
    ignore_missing_instruments: bool = False,
) -> None:
    song = pynbs.read(song_path)
    renderer = SongRenderer(song, default_sound_path)
    renderer.load_instruments(custom_sound_path)
    renderer.mix_song(ignore_missing_instruments).save(
        output_path,
        format,
        bit_depth // 8,
        sample_rate,
        channels,
        target_bitrate,
        target_size,
    )
