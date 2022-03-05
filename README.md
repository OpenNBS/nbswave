# nbswave

A Python package to render note block songs to a variety of audio formats.

## Overview

nbswave is a Python package aimed at rendering note block songs from [Open Note Block Studio](https://opennbs.org/) to audio tracks.

## Setup

The package can be installed with `pip`.

```shell
$ pip install nbswave
```

In order to use the package, [FFmpeg](https://www.ffmpeg.org/) must be available:

1. Download precompiled binaries for `ffmpeg` and `ffprobe` [here](https://ffbinaries.com/downloads).
2. Add the destination folder to your `PATH`, or, alternatively, place both executables in the root folder of the project.

## Usage

```python
from nbswave import *

render_audio("song.nbs", "output.mp3")
```

The output format will be detected automatically based on the file extension.

### Custom instruments

In order to render songs with custom instruments, you have a few options:

1. Copy the sounds manually to the `sounds` folder

2. Pass the path to a folder (or ZIP file) containing custom sounds:

```python
from pathlib import Path

nbs_sounds_folder = Path.home() / "Minecraft Note Block Studio" / "Data" / "Sounds"
render_audio("song.nbs", "output.mp3", custom_sound_path=nbs_sounds_folder)
```

If any sound file used in the song is not found in that location, a `MissingInstrumentException` will be raised. This behavior can be suppressed with the following argument:

```python
render_audio("song.nbs", "output.mp3", ignore_missing_instruments=True)
```

### Advanced usage

For more advanced use cases where you might need more control over the export process, it's possible to use the `SongRenderer` class. This will allow you to load custom instruments from multiple sources, as well as query which instruments are still missing:

```python
from nbswave import *

renderer = SongRenderer("song.nbs")

renderer.load_instruments(nbs_sounds_folder)
renderer.load_instruments("some_more_instruments.zip")

renderer.missing_instruments()
```

## Contributing

Contributions are welcome! Make sure to open an issue discussing the problem or feature suggestion before creating a pull request.

This project uses [poetry](https://python-poetry.org/) for managing dependencies. Make sure to install it, and run:

```shell
$ poetry install
```

This project follows the [black](https://github.com/psf/black) code style. Import statements are sorted with [isort](https://pycqa.github.io/isort/).

```shell
$ poetry run isort nbswave
$ poetry run black nbswave
$ poetry run black --check nbswave
```

---

License - [MIT](https://github.com/Bentroen/nbswave/blob/main/LICENSE)
