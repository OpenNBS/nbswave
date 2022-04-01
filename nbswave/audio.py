import math
from typing import Dict, Optional

import numpy as np
import resampy
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


def change_speed(sound: AudioSegment, speed: float = 1.0) -> AudioSegment:
    if speed == 1.0:
        return sound

    samples = sound.get_array_of_samples()
    samples_np = np.array(samples, dtype="int16")
    samples_reshape = samples_np.reshape(sound.channels, -1, order="F")

    new_frame_rate = sound.frame_rate / speed
    output = resampy.resample(samples_reshape, sound.frame_rate, new_frame_rate)
    output_flattened = output.flatten("F")

    new = sound._spawn(output_flattened, overrides={"frame_rate": sound.frame_rate})
    return new


def key_to_pitch(key: int) -> float:
    return 2 ** ((key) / 12)


def vol_to_gain(vol: float) -> float:
    return math.log(max(vol, 0.0001), 10) * 20


class Mixer:
    def __init__(
        self,
        sample_width: Optional[int] = 16,
        frame_rate: Optional[int] = 44100,
        channels: Optional[int] = 2,
    ):
        self.parts = []
        self.sample_width = sample_width
        self.frame_rate = frame_rate
        self.channels = channels

    def overlay(self, sound, position=0):
        self.parts.append((position, sound))
        return self

    def _sync(self):

        # TODO: Right now, the Mixer class relies on the overlay()'d segments
        # having the same frame rate prior to being added, since if this is
        # not done before, a MemoryError may occur as it tries to _sync all
        # segments. Use the sample_width, frame_rate and channels instance
        # attributes instead and sync sounds as they are added to self.parts

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

        peak = np.abs(output).max()
        clipping_factor = peak / (2 ** 15)
        if clipping_factor > 1:
            print(
                f"The output is clipping by {clipping_factor:.2f}x. Normalizing to 0dBFS"
            )
        gain_compensation = int(min(1, 1 / clipping_factor) * 65535)

        return Track.from_audio_segment(
            seg._spawn(output * gain_compensation, overrides={"sample_width": 4})
        )


class Track(AudioSegment):
    """A subclass of `pydub.AudioSegment` for applying post-rendering
    effects to rendered tracks."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @classmethod
    def from_audio_segment(cls, segment: AudioSegment):
        return cls(
            segment.get_array_of_samples(),
            sample_width=segment.sample_width,
            frame_rate=segment.frame_rate,
            channels=segment.channels,
        )

    def save(
        self,
        filename: str,
        format: Optional[str] = "wav",
        sample_width: Optional[int] = 2,
        frame_rate: Optional[int] = 44100,
        channels: Optional[int] = 2,
        target_bitrate: Optional[int] = 320,
        target_size: Optional[int] = None,
        tags: Optional[Dict[str, str]] = None,
    ):

        seconds = self.duration_seconds

        if target_size:
            bitrate = (target_size / seconds) * 8
            bitrate = min(bitrate, target_bitrate)
        else:
            bitrate = target_bitrate

        output_segment = sync(self, channels, frame_rate, sample_width)

        outfile = output_segment.export(
            filename,
            format=format,
            bitrate="{}k".format(bitrate),
            tags=tags,
        )

        outfile.close()
