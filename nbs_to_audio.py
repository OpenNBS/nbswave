# TODO:
# Add progress reports
# Add logging
# Add looping
# Add fadeout
# Allow exporting layers separately. grouping layers with the same name
# Add different naming conventions for layers
# Prevent normalization making output gain too low when song clips

import os
import pydub
import pydub_mixer
import pynbs
import math
from collections import namedtuple
import time
import zipfile
import io


SOUNDS_PATH = "sounds"


default_instruments = [
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


def load_sound(path):
    return pydub.AudioSegment.from_file(path)


def load_instruments(song, path):
    segments = []

    for ins in default_instruments:
        filename = os.path.join(os.getcwd(), SOUNDS_PATH, ins)
        sound = load_sound(filename)
        segments.append(sound)

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
        sound = load_sound(file)
        segments.append(sound)

    if zip_file is not None:
        zip_file.close()

    return segments


def sync(sound, channels=2, frame_rate=44100, sample_width=2):
    return (
        sound.set_channels(channels)
        .set_frame_rate(frame_rate)
        .set_sample_width(sample_width)
    )


def change_speed(sound, speed=1.0):
    if speed == 1.0:
        return sound

    new = sound._spawn(
        sound.raw_data, overrides={"frame_rate": int(sound.frame_rate * speed)}
    )
    return new.set_frame_rate(sound.frame_rate)


def key_to_pitch(key):
    return 2 ** ((key) / 12)


def vol_to_gain(vol):
    return math.log(max(vol, 0.0001), 10) * 20


class Note(pynbs.Note):
    """Extends pynbs.Note with extra functionality to calculate
    the compensated pitch, volume and panning values."""

    def move(self, offset: int):
        """Return this note moved by a certain amount of ticks."""
        new_note = self
        new_note.tick += offset
        return new_note

    def apply_layer_weight(self, layer: pynbs.Layer):
        """Returns a new Note object with compensated pitch, volume and panning."""
        pitch = self._get_pitch()
        volume = self._get_volume(layer)
        panning = self._get_panning(layer)
        return self.__class__(self.tick, self.layer, self.instrument, pitch, volume, panning)

    def _get_pitch(self):
        """Returns the detune-aware pitch of this note."""
        key = self.key - 45
        detune = self.pitch / 100
        pitch = key + detune
        return pitch

    def _get_volume(self, layer):
        """Returns the layer-aware volume of this note."""
        layer_vol = layer.volume / 100
        note_vol = self.velocity / 100
        vol = layer_vol * note_vol
        return vol

    def _get_panning(self, layer):
        """Returns the layer-aware panning of this note."""
        layer_pan = layer.panning / 100
        note_pan = self.panning / 100
        if layer_pan == 0:
            pan = note_pan
        else:
            pan = (layer_pan + note_pan) / 2
        return pan


class Song(pynbs.File):
    """Extends the pynbs.Song class with extra functionality."""

    def __init__(self):
        super().__init__()

    def __len__(self):
        """Returns the length of the song, in ticks."""
        if self.header.version in (1, 2):
            length = max((note.pitch for note in self.notes))
        else:
            length = self.header.song_length
        return length

    @property
    def duration(self):
        """Returns the duration of the song, in seconds."""
        return self._duration

    @duration.getter
    def duration(self):
        self._duration = len(self) / self.header.tempo * 1000

    def __getitem__(self, key):
        if isinstance(key, int):
            section = [note for note in self.notes if note.tick == key]
        elif isinstance(key, slice):
            section = [
                note for note in self.notes if note.tick > start and note.tick < stop
            ]
        else:
            raise TypeError("Index must be an integer")
        return list(section)

    def weighted_notes():
        # TODO: Consider calculating this automatically upon initializing the song, to avoid recalculating?
        # Except I don't want to destroy the original song data.
        return (note.apply_layer_weight(self.layers[note.layer]) for note in song.notes)

    def layer_groups(self):
        groups = {}
        for layer in self.layers:
            name = layer.name
            if name not in groups:
                group[name] = []
            else:
                group[name].append(layer.id)
        return groups

    def notes_by_layer(self, group_by_name=False):
        """Returns a dict of lists containing the notes in each non-empty layer of the song."""
        layers = {}
        for note in self.weighted_notes():
            layer = self.layers[note.layer]
            if group_by_name:
                group = layer.name
            else:
                group = layer.id + " " + layer.name
                if group not in layers:
                    layers[group] = []
                layers[group].append(note)
        return layers

        if group_by_name:
            # Complexity of O(n^2). Consider iterating notes once grouping them into layer groups
            for name, layers in self.layer_groups():
                notes = filter(lambda note: note.layer in layers, self.weighted_notes())

    def loop(self, count: int, start=None: int):
        """Returns this song looped 'count' times with an optional loop start tick
        (if not provided, defaults to the start tick defined in the song)."""
        if start is None:
            start = self.header.loop_start_tick
        notes = self[start:]
        new_song = self
        for i in range(1, count):
            offset = (len(self) - start) * i
            notes = (note.move_note(note, offset) for note in self.notes)
            new_song.notes.extend(notes)
        return new_song

    def sorted_notes(self):
        notes = (
            note.apply_layer_weight(self.layers[note.layer]) for note in song.notes
        )
        return sorted(notes, key=lambda x: (x.pitch, x.instrument, x.volume, x.panning))


class SongRenderer:
    def __init__(self, song, output_path, default_sound):
        pass

    def export():
        pass


def render_audio(
    song,
    output_path,
    default_sound_path=None,
    custom_sound_path=SOUNDS_PATH,
    start=None,
    end=None,
    loops=0,
    fadeout=0,
    format="wav",
    sample_rate=44100,
    channels=2,
    bit_depth=24,
    bitrate=320,
    target_size=None,
):

    start = time.time()

    instruments = load_instruments(song, custom_sound_path)

    length = len(song)
    track = pydub.AudioSegment.silent(duration=length)
    mixer = pydub_mixer.Mixer()

    last_ins = None
    last_key = None
    last_vol = None
    last_pan = None

    ins_changes = 0
    key_changes = 0
    vol_changes = 0
    pan_changes = 0

    sorted_notes = sort_notes(song)
    for i, note in enumerate(sorted_notes):

        ins = note.instrument
        key = note.pitch
        vol = note.volume
        pan = note.panning

        # TODO: optimize and avoid gain/pitch/key calculation if default value!
        # TODO: ignore locked layers
        # TODO: pan has a loudness compensation? https://github.com/jiaaro/pydub/blob/master/API.markdown#audiosegmentpan

        if ins != last_ins:
            last_key = None
            last_vol = None
            last_pan = None
            sound1 = instruments[note.instrument]
            sound1 = sync(sound1)
            ins_changes += 1

        if key != last_key:
            last_vol = None
            last_pan = None
            pitch = key_to_pitch(key)
            sound2 = change_speed(sound1, pitch)
            key_changes += 1

        if vol != last_vol:
            last_pan = None
            gain = vol_to_gain(vol)
            sound3 = sound2.apply_gain(gain)
            vol_changes += 1

        if pan != last_pan:
            sound4 = sound3.pan(pan)
            sound = sound4
            pan_changes += 1

        last_ins = ins
        last_key = key
        last_vol = vol
        last_pan = pan

        if i % 10 == 0:
            print(
                "Converting note {}/{} (tick: {}, layer: {}, vol: {}, pan: {}, pit: {})".format(
                    i + 1, len(song.notes), note.tick, note.layer, vol, pan, pitch
                )
            )

        pos = note.tick / song.header.tempo * 1000

        mixer.overlay(sound, position=pos)

    track = mixer.to_audio_segment()

    seconds = track.duration_seconds

    if target_size:
        bitrate = (target_size / seconds) * 8
        bitrate = min(bitrate, target_bitrate)
    else:
        bitrate = target_bitrate

    outfile = track.export(
        output_path,
        format="mp3",
        bitrate="{}k".format(bitrate),
        tags={"artist": "test"},
    )

    outfile.close()

    end = time.time()

    with open("tests/log_{}.txt".format(os.path.basename(output_path)), "w") as f:
        f.write(
            "Ins: {}\nKey: {}\nVol: {}\nPan: {}\n\nStart: {}\nEnd: {}\nTime elapsed: {}".format(
                ins_changes,
                key_changes,
                vol_changes,
                pan_changes,
                start,
                end,
                end - start,
            )
        )

