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


from __future__ import annotations

import io
import os
import zipfile
from typing import BinaryIO, Iterator, Optional, Union

import pydub
import pynbs

import pydub_mixer

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


def load_default_instruments():
    segments = {}
    for index, ins in enumerate(DEFAULT_INSTRUMENTS):
        filename = os.path.join(os.getcwd(), SOUNDS_PATH, ins)
        sound = pydub_mixer.load_sound(filename)
        segments[index] = sound
    return segments


def load_custom_instruments(
    song: pynbs.File, path: Union(str, zipfile.ZipFile, BinaryIO)
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
        sound = pydub_mixer.load_sound(file)
        segments[ins.id] = sound

    if zip_file is not None:
        zip_file.close()

    return segments


class Note(pynbs.Note):
    """Extends `pynbs.Note` with extra functionality to calculate
    the compensated pitch, volume and panning values."""

    def __new__(cls, note: Union[pynbs.Note, Note]):
        super().__new__(
            cls,
            note.tick,
            note.layer,
            note.instrument,
            note.key,
            note.velocity,
            note.panning,
            note.pitch,
        )

    def move(self, offset: int) -> Note:
        """Return this note moved by a certain amount of ticks."""
        new_note = Note(self)
        new_note.tick += offset
        return new_note

    def apply_layer_weight(self, layer: pynbs.Layer) -> Note:
        """Return a new Note object with compensated pitch, volume and panning."""
        pitch = self._get_pitch()
        volume = self._get_volume(layer)
        panning = self._get_panning(layer)
        return self.__class__(
            self.tick, self.layer, self.instrument, pitch, volume, panning
        )

    def _get_pitch(self) -> float:
        """Return the detune-aware pitch of this note."""
        key = self.key - 45
        detune = self.pitch / 100
        pitch = key + detune
        return pitch

    def _get_volume(self, layer: pynbs.Layer) -> float:
        """Return the layer-aware volume of this note."""
        layer_vol = layer.volume / 100
        note_vol = self.velocity / 100
        vol = layer_vol * note_vol
        return vol

    def _get_panning(self, layer: pynbs.Layer) -> float:
        """Return the layer-aware panning of this note."""
        layer_pan = layer.panning / 100
        note_pan = self.panning / 100
        if layer_pan == 0:
            pan = note_pan
        else:
            pan = (layer_pan + note_pan) / 2
        return pan


class Song(pynbs.File):
    """Extends the `pynbs.File` class with extra functionality."""

    def __init__(self, song: pynbs.File):
        super(Song, self).__init__(
            song.header, song.notes, song.layers, song.instruments
        )
        self.notes = [Note(note) for note in self.notes]

    def __len__(self) -> int:
        """Return the length of the song, in ticks."""
        if self.header.version == 1 or self.header.version == 2:
            # Length isn't correct in version 1 and 2 songs, so we need this workaround
            length = max((note.pitch for note in self.notes))
        else:
            length = self.header.song_length
        return length

    def __getitem__(self, key: Union[int, slice]) -> list[Note]:
        """Return the notes in a certain section (vertical slice) of the song."""
        if isinstance(key, int):
            section = [note for note in self.notes if note.tick == key]
        elif isinstance(key, slice):
            start = key.start if key.start is not None else 0
            stop = key.stop if key.stop is not None else len(self)
            section = [
                note for note in self.notes if note.tick > start and note.tick < stop
            ]
        else:
            raise TypeError("Index must be an integer")
        return list(section)

    @property
    def duration(self) -> int:
        """The duration of the song, in seconds."""
        return self._duration

    @duration.getter
    def duration(self) -> None:
        self._duration = len(self) / self.header.tempo * 1000

    def weighted_notes(self) -> Iterator[Note]:
        """Return all notes in this song with their layer velocity and panning applied."""
        return (note.apply_layer_weight(self.layers[note.layer]) for note in self.notes)

    def layer_groups(self) -> dict[str, pynbs.Layer]:
        """Return a dict containing each unique layer name in this song and a list
        of all layers with that name."""
        groups = {}
        for layer in self.layers:
            name = layer.name
            if name not in groups:
                groups[name] = []
            else:
                groups[name].append(layer.id)
        return groups

    def notes_by_layer(
        self, group_by_name: Optional[bool] = False
    ) -> dict[str, list[Note]]:
        """Return a dict of lists containing the weighted notes in each non-empty layer of the
        song. If `group_by_name` is true, notes in layers with identical names will be grouped."""
        groups = {}
        for note in self.weighted_notes():
            layer = self.layers[note.layer]
            group_name = layer.name if group_by_name else f"{layer.id} {layer.name}"
            if group_name not in groups:
                groups[group_name] = []
            groups[group_name].append(note)
        return groups

    def loop(self, count: int, start: Optional[int] = None) -> Song:
        """Return this song looped `count` times with an optional loop start tick (`start`).
        If `start` is not provided, defaults to the start tick defined in the song)."""
        if start is None:
            start = self.header.loop_start_tick
        notes = self[start:]
        new_song = self
        for i in range(1, count):
            offset = (len(self) - start) * i
            notes = (note.move_note(note, offset) for note in self.notes)
            new_song.notes.extend(notes)
        return new_song

    def sorted_notes(self) -> list[Note]:
        """Return the weighted notes in this song sorted by pitch, instrument, velocity, and
        panning."""
        notes = (
            note.apply_layer_weight(self.layers[note.layer]) for note in self.notes
        )
        return sorted(
            notes, key=lambda x: (x.pitch, x.instrument, x.velocity, x.panning)
        )


class SongRenderer:
    def __init__(self, song: Song):
        self._song = song
        self._instruments = load_default_instruments()
        self._mixer = pydub_mixer.Mixer
        self._mixed = False
        self._track = None

    def load_instruments(self, path: Union[str, zipfile.ZipFile, BinaryIO]):
        self._instruments.update(load_custom_instruments(self._song, path))

    def missing_instruments(self):
        return [
            instrument
            for instrument in self._song.instruments
            if instrument.id not in self._instruments
        ]

    def mix(
        self,
        ignore_missing_instruments: bool = False,
    ):

        if not ignore_missing_instruments and self.missing_instruments():
            raise ValueError("")

        length = len(self._song)
        self._track = pydub.AudioSegment.silent(duration=length)

        last_ins = None
        last_key = None
        last_vol = None
        last_pan = None

        sorted_notes = self.song.sorted_notes()
        for i, note in enumerate(sorted_notes):

            ins = note.instrument
            key = note.pitch
            vol = note.velocity
            pan = note.panning

            if ins != last_ins:
                last_key = None
                last_vol = None
                last_pan = None
                # try:
                sound1 = self._instruments[note.instrument]
                # except IndexError:
                #    if not ignore_missing_instruments:
                #        pass
                sound1 = pydub_mixer.sync(sound1)

            if key != last_key:
                last_vol = None
                last_pan = None
                pitch = pydub_mixer.key_to_pitch(key)
                sound2 = pydub_mixer.change_speed(sound1, pitch)

            if vol != last_vol:
                last_pan = None
                gain = pydub_mixer.vol_to_gain(vol)
                sound3 = sound2.apply_gain(gain)

            if pan != last_pan:
                sound4 = sound3.pan(pan)
                sound = sound4

            last_ins = ins
            last_key = key
            last_vol = vol
            last_pan = pan

            pos = note.tick / self.song.header.tempo * 1000

            self._mixer.overlay(sound, position=pos)

    def render(self):
        self._track = self.mixer.to_audio_segment()

    def save(
        self,
        filename: str,
        format: str = "wav",
        sample_rate: int = 44100,
        channels: int = 2,
        bit_depth: int = 24,
        target_bitrate: int = 320,
        target_size: int = None,
    ):

        if self._track is None:
            self._render()

        seconds = self._track.duration_seconds

        if target_size:
            bitrate = (target_size / seconds) * 8
            bitrate = min(bitrate, target_bitrate)
        else:
            bitrate = target_bitrate

        outfile = self._track.export(
            filename,
            format="mp3",
            bitrate="{}k".format(bitrate),
            tags={"artist": "test"},
        )

        outfile.close()


def render_audio(
    song: pynbs.Song,
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
):
    if song.is_instance(pynbs.Song):
        pass
