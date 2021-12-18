import math
from typing import Optional

import numpy as np
from pydub import AudioSegment


def load_sound(path: str) -> AudioSegment:
    return AudioSegment.from_file(path)


def sync(
    sound: AudioSegment,
    channels: Optional[int] = 2,
    frame_rate: Optional[int] = 44100,
    sample_width: Optional[int] = 2,
) -> AudioSegment:
    return (
        sound.set_channels(channels)
        .set_frame_rate(frame_rate)
        .set_sample_width(sample_width)
    )


def change_speed(sound: AudioSegment, speed: int = 1.0) -> AudioSegment:
    if speed == 1.0:
        return sound

    new = sound._spawn(
        sound.raw_data, overrides={"frame_rate": int(sound.frame_rate * speed)}
    )
    return new.set_frame_rate(sound.frame_rate)


def key_to_pitch(key: int) -> float:
    return 2 ** ((key) / 12)


def vol_to_gain(vol: float) -> float:
    return math.log(max(vol, 0.0001), 10) * 20


class Mixer(object):
    def __init__(self):
        self.parts = []

    def overlay(self, sound, position=0):
        self.parts.append((position, sound))
        return self

    def _sync(self):
        positions, segs = zip(*self.parts)

        frame_rate = segs[0].frame_rate
        array_type = segs[0].array_type

        offsets = [int(frame_rate * pos / 1000.0) for pos in positions]
        segs = AudioSegment.empty()._sync(*segs)
        return list(zip(offsets, segs))

    def __len__(self):
        parts = self._sync()
        seg = parts[0][1]
        frame_count = max(offset + seg.frame_count() for offset, seg in parts)
        return int(1000.0 * frame_count / seg.frame_rate)

    def append(self, sound):
        self.overlay(sound, position=len(self))

    def to_audio_segment(self):
        parts = self._sync()
        seg = parts[0][1]
        channels = seg.channels

        frame_count = max(offset + seg.frame_count() for offset, seg in parts)
        sample_count = int(frame_count * seg.channels)

        output = np.zeros(sample_count, dtype="int32")
        for offset, seg in parts:
            sample_offset = offset * channels
            samples = np.frombuffer(seg.get_array_of_samples(), dtype="int16")
            start = sample_offset
            end = start + len(samples)
            output[start:end] += samples

        return seg._spawn(output, overrides={"sample_width": 4}).normalize(headroom=0.0)
