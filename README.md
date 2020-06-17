# Audfill

A python script to find song's info and rename them by looking them up on [audd.io](https://audd.io/).

An [API token](https://docs.audd.io/#authentication-and-limits) is required to do more than 10 requests per day.

## Installation

### Requirements

- Python >= 3.7
- FFmpeg must be installed on the system and in the PATH
- Python modules:
  - click
  - requests
  - validators
  - pydub

### PIP

```bash
python -m pip install audfill
```

### Local Installation

Run inside Audfill directory.

```bash
python -m pip install -e .
```

## Usage

A sound file must always be specified. Most sound files are supported (anything that FFmpeg and Pydub supports).

Specifiying no options will send the request, but not do anything with the response.

An example to print information about a song:

```bash
audfill song.mp3 -i
```

### Wildcards

Wildcards are supported and will loop though all files in a directory. The following example prints all the information about MP3s in the current directory.

```bash
audfill *.mp3 -i
```

### Sources

This script is also capable of getting additional data from Apple Music, Spotify, Napster, and Deezer. To explicitly get info from these sources, use ```-s [source]```. Data from sources listed first will be used for naming files. Sources will be implicitly added as necessary unless the minimum flag is specified (```-n```).

### API Token

An API key can be specified with the option ```-t``` or can be read automatically with the environment variable ```AUDDIOKEY```.

```bash
audfill song.mp3 -k exampleToken123
```

### File naming

For use with renaming files or downloading art and previews. File extension will automatically be added, do not add your own extension.

- Percent Symbol: %%
- Filename:       %f
- Artist(s)       %a
- Composer:       %c
- Album:          %b
- Genre(s):       %g
- Title:          %T
- Short Title:    %t
- Explicit:       %x
- ISRC:           %i
- Disk Number:    %k
- Track Number:   %#
- Release Date:
  - Capital letters represent extended (ex. 1997, 03), lowercase letters represent short dates (ex. 97, 3)
    - %Y, %y
    - %M, %m
    - %D, %d

Example (Renames to **Artist - Title.mp3**):

```bash
audfill song.mp3 -r '%a - %T'
```

### Running with Python

```bash
python audfill.py [filename] [options]
```

### Running with Python PIP

```bash
python -m audfill [filename] [options]
```

### Running executable

```bash
audfill [filename] [options]
```
