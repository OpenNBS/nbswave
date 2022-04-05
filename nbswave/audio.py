import math
from typing import Dict, Optional

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


def change_speed(sound: AudioSegment, speed: float = 1.0) -> AudioSegment:
    if speed == 1.0:
        return sound

    new = sound._spawn(
        sound.raw_data, overrides={"frame_rate": round(sound.frame_rate * speed)}
    )
    return new.set_frame_rate(sound.frame_rate)


def key_to_pitch(key: int) -> float:
    return 2 ** ((key) / 12)


def vol_to_gain(vol: float) -> float:
    return math.log(max(vol, 0.0001), 10) * 20


class Mixer:
    def __init__(
        self,
        sample_width: Optional[int] = 2,
        frame_rate: Optional[int] = 44100,
        channels: Optional[int] = 2,
        length: Optional[float] = 0,
    ):
        self.sample_width = sample_width
        self.frame_rate = frame_rate
        self.channels = channels
        self.output = np.zeros(self._get_array_size(length), dtype="int32")

    def _get_array_size(self, length_in_ms: float) -> int:
        frame_count = length_in_ms * (self.frame_rate / 1000.0)
        array_size = frame_count * self.channels
        array_size_aligned = self._get_aligned_array_size(array_size)
        return array_size_aligned

    def _get_aligned_array_size(self, length: int):
        """Pads an array length to the appropriate data format."""
        align = self.sample_width * self.channels
        length_aligned = math.ceil(length / align) * align
        return length_aligned

    def overlay(self, sound, position=0):
        sound_sync = self._sync(sound)
        samples = np.frombuffer(sound_sync.get_array_of_samples(), dtype="int16")

        frame_offset = int(self.frame_rate * position / 1000.0)
        sample_offset = frame_offset * self.channels

        start = sample_offset
        end = start + len(samples)

        output_size = len(self.output)
        if end > output_size:
            pad_length = self._get_aligned_array_size(end - output_size)
            self.output = np.pad(
                self.output, pad_width=(0, pad_length), mode="constant"
            )
            print(f"Padded from {output_size} to {end} (added {pad_length} entries)")

        self.output[start:end] += samples

        return self

    def _sync(self, segment: AudioSegment):
        return (
            segment.set_sample_width(self.sample_width)
            .set_frame_rate(self.frame_rate)
            .set_channels(self.channels)
        )

    def __len__(self):
        return len(self.output) / ((self.frame_rate / 1000.0) * self.channels)

    def append(self, sound):
        self.overlay(sound, position=len(self))

    def to_audio_segment(self):
        peak = np.abs(self.output).max()
        clipping_factor = peak / (2 ** 15 - 1)

        if clipping_factor > 1:
            print(
                f"The output is clipping by {clipping_factor:.2f}x. Normalizing to 0dBFS"
            )
            normalized_signal = np.rint(self.output / clipping_factor).astype("int16")
        else:
            normalized_signal = self.output

        output_segment = AudioSegment(
            normalized_signal,
            frame_rate=self.frame_rate,
            sample_width=self.sample_width,
            channels=self.channels,
        )

        return Track.from_audio_segment(output_segment)


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
