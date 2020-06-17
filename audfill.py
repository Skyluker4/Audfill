"""
A program to automatically find a song's info.
"""

import glob
import json
import os
import re
import sys
import tempfile
from pathlib import Path

import click
import requests
import validators
from pydub import AudioSegment


# Arguments
@click.command()
@click.argument('filename', type=str)
@click.option('-b', '--start',
              type=str,
              help='Enter the time for the search to begin in the format "mm:ss.ms". If end or length != specified, '
                   '18 seconds of the song will be used.')
@click.option('-e', '--end',
              type=str,
              help='Enter the time for the search to end in the format "mm:ss.ms". Cannot be longer than 25 seconds')
@click.option('-l', '--length',
              type=str,
              help='Enter the time for the search to begin in the format "mm:ss.ms". Cannot be longer than 25 seconds')
@click.option('-n', '--minimum',
              is_flag=True,
              help="Don't implicitly add sources. If more sources are specified, they will be still be used.")
@click.option('-s', '--source',
              type=click.Choice(['lyrics', 'apple_music', 'spotify', 'napster', 'deezer']), multiple=True,
              show_default=True,
              help='Get extra data from these sources. See documentation for what each source contains. If multiple '
                   'sources have the same data, the data from the first source specified will be used.')
@click.option('-S', '--all-sources',
              is_flag=True,
              help='Get extra data from all sources. Order of precedence: Apple Music, Spotify, Napster, '
                   'Deezer. Includes lyrics.')
@click.option('-c', '--market',
              type=str,
              default='us', show_default=True,
              help='Change what market to lookup the song in for Apple Music and Spotify. Ex. "us", "es"')
@click.option('-w', '--lyrics',
              is_flag=True,
              help='Print the lyrics out on the console. Implicitly adds the lyrics source.')
@click.option('-r', '--rename',
              type=str,
              help='Rename the file(s) according to the format specified. File extension will be preserved.')
@click.option('-i', '--info',
              is_flag=True,
              help='Display all info gathered about a song.')
@click.option('-j', '--output-json',
              is_flag=True,
              help='Print the JSON file out on the console.')
@click.option('-u', '--link',
              is_flag=True,
              help='Print the link to the song out on the console. If a source is specified, it will be a link to '
                   'that source, otherwise a generic list.en link.')
@click.option('-a', '--art',
              type=str,
              help='Save the art to the file according to the format. Will implicitly add Apple Music unless another '
                   'source with artwork is specified.')
@click.option('-g', '--artist-art',
              type=str,
              help='Save the artist art to the file according to the format. Will implicitly add Deezer.')
@click.option('-p', '--preview',
              type=str,
              help='Save the song preview to the file according to the format. Will implicitly add Apple Music unless '
                   'another source with a song preview is specified.')
@click.option('-t', '--token',
              type=str,
              help='The API token for querying audd.io. Will automatically read environment variable AUDDIOTOKEN, '
                   'unless overwritten. If no token is specified, the maximum number of queries is 10.')
@click.option('-q', '--quiet',
              is_flag=True,
              help="Don't print errors out on the screen. If a flag that displays information is specified, "
                   "it will still be printed.")
@click.version_option(version='1.0.0', prog_name='Audfill')
def cli(filename, start, end, length, minimum, source, all_sources, market, lyrics, rename, info,
        output_json, link, art, artist_art, preview, token, quiet):
    """
    Get information about a sound file by looking it up on audd.io.

    FILENAME is the path or URL to a sound file.

    \b
    The format for naming files is:
        Percent Symbol: %%
        Filename:       %f
        Artist(s):      %a
        Composer:       %c
        Album:          %b
        Genre(s):       %g
        Title:          %T
        Short Title:    %t
        Explicit:       %x
        ISRC:           %i
        Disk Number:    %k
        Track Number:   %#
        Release Date:
            (Capital = Extended)
            (Lowercase = Short)
                        %Y, %y
                        %M, %m
                        %D, %d
    """

    # How many files returned errors
    errors = 0

    # Set global variable
    error_print.silent = quiet

    # Set up times
    length_time = -1
    start_time = -1

    # Set start time
    if start is not None:
        start_time = parse_time(start)
        # Set end time
        if end is not None:
            end_time = parse_time(end)
            length_time = end_time - start_time
        # Use default length is only start time is given
        if end is None and length is None:
            length_time = parse_time('0:18')
    else:
        # End with no start
        if end is not None:
            error_print('WARNING: End time given with no start, will ignore end time.')
            end = None

    # Set length accordingly
    if length is not None:
        if end is not None:
            error_print('WARNING: End time and length given, length will be used.')
        length_time = parse_time(length)

    if length is None and start is None and end is None:
        length_time = parse_time('0:18')

    # Check if the length will be longer than 25 seconds, shorten
    if length_time > parse_time('0:25'):
        error_print('WARNING: Specified length is longer than 25 seconds. Length will be truncated to 25 seconds.')
        length_time = parse_time('0:25')

    # Check for negative length, use default length instead
    if length_time <= 0:
        error_print('WARNING: Length is less than or equal to zero. 18 seconds will be used instead.')
        length_time = parse_time('0:18')

    # Set settings
    data = {
        'return': ''
    }

    source = list(source)

    # Add all sources if requested
    if all_sources:
        if 'lyrics' not in source:
            source.append('lyrics')
        if 'apple_music' not in source:
            source.append('apple_music')
        if 'spotify' not in source:
            source.append('spotify')
        if 'napster' not in source:
            source.append('napster')
        if 'deezer' not in source:
            source.append('deezer')

    # Check if url or file
    valid_url = validators.url(filename)

    # Check for invalid options given a URL
    if valid_url and (rename is not None):
        error_print('WARNING: File operation was given as an option with a URL specified as the source. Cannot '
                    'operate on URL. Ignoring file operations.')

    # Don't add stuff in min
    if not minimum:
        # Figure out data needed
        if art:
            if ('apple_music' not in source) and ('spotify' not in source) and ('deezer' not in source):
                source.append('apple_music')
        if artist_art:
            if 'deezer' not in source:
                source.append('deezer')
        if preview:
            # Spotify returns a blank preview most/all of the time, so don't rely on it
            if ('apple_music' not in source) and ('napster' not in source) and ('deezer' not in source):
                source.append('apple_music')
        if rename:
            # Dynamically figure out what's needed
            # Short title
            if '%t' in rename:
                if 'deezer' not in source:
                    source.append('deezer')

            # Genre
            if '%g' in rename:
                if 'apple_music' not in source:
                    source.append('apple_music')

            # Explicit
            if '%x' in rename:
                if ('spotify' not in source) or ('napster' not in source) or ('deezer' not in source):
                    source.append('spotify')

            # Disc and track number
            if ('%#' in rename) or ('%k' in rename):
                if ('apple_music' not in source) or ('spotify' not in source) or ('napster' not in source):
                    source.append('apple_music')

            # ISRC
            if '%i' in rename:
                if ('apple_music' not in source) or ('spotify' not in source) or ('napster' not in source):
                    source.append('apple_music')

            # Composer
            if '%c' in rename:
                if 'apple_music' not in source:
                    source.append('apple_music')
        if lyrics:
            if 'lyrics' not in source:
                source.append('lyrics')

    # Check for API token in environment
    if token is None or token == '':
        try:
            token = str(os.environ['AUDDIOTOKEN'])
        # Environment variable not found, no big deal
        except KeyError:
            pass

    for s in source:
        data['return'] += s + ','
    if market != 'us':
        data['market'] = market
    if token != '':
        data['api_token'] = token

    if 'apple_music' not in source and 'spotify' not in source and market != 'us':
        error_print('WARNING: Market specified but will not be used.')

    # Clean up trailing comma
    data['return'] = data['return'][:len(data['return']) - 1]

    # Upload request accordingly
    if valid_url:
        error_print('INFO: Processing URL ' + filename)

        if rename is not None:
            error_print('WARNING: Cannot rename a URL. Ignoring rename.')
            rename = None

        # Download file if edit options are specified
        if (start is not None) or (length is not None) or (end is not None):
            error_print('INFO: Downloading file from URL because custom times are specified.')

            # Create temporary file to download to
            tmp_file, tmp_path = tempfile.mkstemp()
            try:
                # Download the file
                r = requests.get(filename)

                # Save it
                with os.fdopen(tmp_file, 'wb') as tmp:
                    tmp.write(r.content)

                # Get result
                result = file_send(tmp_path, data, start, start_time, length, length_time, end)
            finally:
                # Delete the temporary file
                os.remove(tmp_path)

        # Otherwise just use the URL
        else:
            data['url'] = filename
            result = requests.post('https://api.audd.io/', data=data)

        errors += analyze_response(result, filename, source, lyrics, rename, info, output_json, link,
                                   art, artist_art, preview)
    else:
        # Accept wildcards, loop through all files
        for filename in glob.glob(filename):
            error_print('INFO: Processing file ' + filename)

            result = file_send(filename, data, start, start_time, length, length_time, end)

            errors += analyze_response(result, filename, source, lyrics, rename, info, output_json, link,
                                       art, artist_art, preview)

    return errors


def file_send(filename, data, start, start_time, length, length_time, end):
    """Send request with file, returns result"""
    # Open sound file
    sound = AudioSegment.from_file(filename)

    # Check if start is after end of sound file
    if (start is not None) and (len(sound) <= start_time):
        error_print('WARNING: Sound file is shorter than given start time. Will use halfway point instead')
        start = None

    # Cut sound file
    if len(sound) > length_time:
        if start is None:
            halfway_point = len(sound) // 2
            cut_audio = sound[halfway_point - (length_time / 2): halfway_point + (length_time / 2)]
        else:
            cut_audio = sound[start_time: start_time + length_time]
    else:
        # Only print if user specified length
        if (length is not None) or (end is not None):
            error_print('WARNING: Sound file not as long as specified length, will use entire audio file '
                        'instead.')

        # Use entire audio file
        cut_audio = sound

    # Create temporary file to upload
    tmp_file, tmp_path = tempfile.mkstemp()
    try:
        # Write edited audio to temporary file
        cut_audio.export(tmp_path, format="mp3")

        # Send request to audd.io
        with os.fdopen(tmp_file, 'rb') as tmp:
            result = requests.post('https://api.audd.io/', data=data, files={'file': tmp})
    finally:
        # Delete the temporary file
        os.remove(tmp_path)

    return result


def analyze_response(result, filename, source, lyrics, rename, info, output_json, link, art, artist_art,
                     preview):
    """Analyze the results from the request."""
    errors = 0

    if result.status_code == requests.codes.ok:
        # Parse JSON
        json_data = json.loads(result.text)

        # Output JSON
        if output_json:
            print(json.dumps(json_data, sort_keys=True, indent=4))

        if json_data["status"] == 'success':
            # Check if song is found
            if json_data["result"] is not None:
                # Analyze the data
                result_data = result.json()

                errors += find_song(result_data, filename, source, lyrics, rename, info, link, art,
                                    artist_art, preview)
            # Song not found :(
            else:
                error_print('ERROR: Song not found.')
                errors += 1
        # Audd.io error :(
        else:
            error_print('Audd.io Error Code ' + str(json_data["error"]["error_code"]))
            error_print(json_data["error"]["error_message"])
            errors += 1

    else:
        error_print('ERROR: Could not connect to audd.io. Song being skipped.')
        errors += 1

    return errors


def find_song(json_data, filename, source, lyrics, rename, info, link, art, artist_art, preview):
    """Actually do things with the data found."""
    # How many errors
    errors = 0

    # Fill song data
    song_data = SongData()
    # Get stuff from the rest of the sources, first source will be first in dictionary
    for s in source:
        song_data.data_from_source(s, json_data)
    # Always get audd.io default data
    song_data.data_from_source('audd.io', json_data)

    # Print lyrics
    if lyrics:
        print(json_data["result"]["lyrics"]["lyrics"])

    # Print link
    if link:
        try:
            print(index_dictionary(song_data.link))
        except IndexError:
            error_print('ERROR: Link not found for song. Skipping...')
            errors += 1

    # Save album/song art
    if art:
        try:
            download_file(index_dictionary(song_data.art), fmt_filename(song_data, art, filename))
        except IndexError:
            error_print('ERROR: Art not found for song. Skipping...')
            errors += 1

    # Save artist art
    if artist_art:
        try:
            download_file(index_dictionary(song_data.authorArt), fmt_filename(song_data, artist_art, filename))
        except IndexError:
            error_print('ERROR: Artist art not found for song. Skipping...')
            errors += 1

    # Save preview
    if preview:
        try:
            download_file(index_dictionary(song_data.preview), fmt_filename(song_data, preview, filename))
        except IndexError:
            error_print('ERROR: Preview not found for song. Skipping...')
            errors += 1

    # Rename file
    if rename is not None:
        # Get the new filename and same extension, check if duplicate
        new_filename = unique_filename(fmt_filename(song_data, rename, filename) + Path(filename).suffix)

        # Rename the file
        os.rename(filename, new_filename)

    # Print information
    if info:
        # Default data
        print("Audd.io:")
        print("Title: " + json_data["result"]["title"])
        print("Artist: " + json_data["result"]["artist"])
        print("Release Date: " + json_data["result"]["release_date"])
        print("Timecode: " + json_data["result"]["timecode"])
        print("Album: " + json_data["result"]["album"])
        print("Song Link: " + json_data["result"]["song_link"])

        for s in source:
            print_data(s, json_data)

    return errors


def unique_filename(filename: str):
    """Generates a unique filename if there is a copy of a file."""
    count = 0

    filename_split = filename.rsplit('.', 1)
    new_filename = filename

    while os.path.isfile(new_filename):
        count += 1
        new_filename = filename_split[0] + ' (' + str(count) + ').' + filename_split[1]

    if count > 0:
        error_print('WARNING: File "' + filename + '" already exists. Renaming to "' + new_filename + '".')

    return new_filename


class Date:
    """A simple date class."""
    year = -1
    month = -1
    day = -1

    def __init__(self, date_str: str):
        self.str_to_date(date_str)

    def str_to_date(self, date_str: str):
        """Convert a string in the format YYYY-MM-DD to a Date object."""
        date_split = date_str.split('-')
        self.year = int(date_split[0])
        self.month = int(date_split[1])
        self.day = int(date_split[2])


class SongData:
    """A class to hold necessary song data. Each element in list is from a different source."""
    # All necessary attributes that will be used
    title = dict()
    titleShort = dict()
    artist = dict()
    composer = dict()
    releaseDate = dict()  # Date object
    duration = dict()  # In milliseconds
    genre = dict()
    explicit = dict()
    foundAt = dict()  # Not used, maybe in the future
    album = dict()
    albumArtist = dict()
    disc = dict()
    track = dict()
    rating = dict()
    link = dict()
    art = dict()
    authorArt = dict()
    preview = dict()
    authorURL = dict()  # A list, will have to iterate
    ISRC = dict()

    def data_from_source(self, source: str, data):
        """Fill in the data of the SongData object accordingly."""
        # Default
        if 'audd.io' == source:
            self.title['audd.io'] = data["result"]["title"]
            self.artist['audd.io'] = data["result"]["artist"]
            self.releaseDate['audd.io'] = Date(data["result"]["release_date"])
            self.foundAt['audd.io'] = data["result"]["timecode"]
            self.album['audd.io'] = data["result"]["album"]
            self.link['audd.io'] = data["result"]["song_link"]

        # Apple Music
        if 'apple_music' == source:
            self.title['apple_music'] = data["result"]["apple_music"]["name"]
            self.artist['apple_music'] = data["result"]["apple_music"]["artistName"]
            self.composer['apple_music'] = data["result"]["apple_music"]["composerName"]
            self.releaseDate['apple_music'] = Date(data["result"]["apple_music"]["releaseDate"])
            self.duration['apple_music'] = data["result"]["apple_music"]["durationInMillis"]
            self.genre['apple_music'] = gen_genre_string(data["result"]["apple_music"]["genreNames"])
            self.album['apple_music'] = data["result"]["apple_music"]["albumName"]
            self.disc['apple_music'] = data["result"]["apple_music"]["discNumber"]
            self.track['apple_music'] = data["result"]["apple_music"]["trackNumber"]
            self.link['apple_music'] = data["result"]["apple_music"]["url"]
            self.art['apple_music'] = fmt_apple_art(data["result"]["apple_music"]["artwork"])
            self.preview['apple_music'] = data["result"]["apple_music"]["previews"][0][
                "url"]  # Only need one preview link, ignore the rest
            self.ISRC['apple_music'] = data["result"]["apple_music"]["isrc"]

        # Spotify
        if 'spotify' == source:
            self.title['spotify'] = data["result"]["spotify"]["name"]
            self.artist['spotify'] = str_artists(
                data["result"]["spotify"]["artists"])  # We don't need to keep them separate, just combine them
            self.releaseDate['spotify'] = Date(data["result"]["spotify"]["album"]["release_date"])
            self.duration['spotify'] = data["result"]["spotify"]["duration_ms"]
            self.explicit['spotify'] = data["result"]["spotify"]["explicit"]
            self.album['spotify'] = data["result"]["spotify"]["album"]["name"]
            self.disc['spotify'] = data["result"]["spotify"]["disc_number"]
            self.track['spotify'] = data["result"]["spotify"]["track_number"]
            self.ISRC['spotify'] = data["result"]["spotify"]["external_ids"]["isrc"]
            self.rating['spotify'] = data["result"]["spotify"]["popularity"]  # Out of 100
            self.link['spotify'] = data["result"]["spotify"]["external_urls"]["spotify"]
            self.authorURL['spotify'] = artist_url_list(data["result"]["spotify"]["artists"])
            self.art['spotify'] = data["result"]["spotify"]["album"]["images"][0][
                "url"]  # Just grab the first one, it's the biggest

        # Napster
        if 'napster' == source:
            self.title['napster'] = data["result"]["napster"]["name"]
            self.artist['napster'] = data["result"]["napster"]["artistName"]
            self.duration['napster'] = parse_time(data["result"]["napster"]["playbackSeconds"])
            self.album['napster'] = data["result"]["napster"]["albumName"]
            self.explicit['napster'] = data["result"]["napster"]["isExplicit"]
            self.disc['napster'] = data["result"]["napster"]["disc"]
            self.track['napster'] = data["result"]["napster"]["index"]
            self.preview['napster'] = data["result"]["napster"]["previewURL"]
            self.ISRC['napster'] = data["result"]["napster"]["isrc"]

        # Deezer
        if 'deezer' == source:
            self.title['deezer'] = data["result"]["deezer"]["title"]
            self.titleShort['deezer'] = data["result"]["deezer"]["title_short"]
            self.artist['deezer'] = data["result"]["deezer"]["artist"]["name"]
            self.duration['deezer'] = parse_time(data["result"]["deezer"]["duration"])
            self.explicit['deezer'] = data["result"]["deezer"]["explicit_lyrics"]
            self.album['deezer'] = data["result"]["deezer"]["album"]["title"]
            self.rating['deezer'] = data["result"]["deezer"]["rank"]
            self.authorURL['deezer'] = data["result"]["deezer"]["artist"]["link"]
            self.preview['deezer'] = data["result"]["deezer"]["preview"]
            self.art['deezer'] = data["result"]["deezer"]["album"]["cover"]
            self.authorArt['deezer'] = data["result"]["deezer"]["artist"]["picture"]


def gen_genre_string(genres: list):
    """Return a pretty genre string to look at given a list of genres (strings)."""
    genre_string = ''

    # Iterate through all genres
    for g in genres:
        genre_string += g + ', '

    # Remove trailing comma
    genre_string = genre_string.rstrip(', ')

    return genre_string


def fmt_filename(song_data: SongData, fmt: str, filename: str):
    """Return a filename according to a format string, excluding the file extension."""
    # Probably won't happen, but just to be safe
    if '\0' in fmt:
        error_print('WARNING: Illegal character in filename. Character will be removed.')
        fmt = fmt.replace('\0', '')

    # Replace double percents with a placeholder that is an invalid filename. Has to go first.
    if '%%' in fmt:
        fmt = fmt.replace('%%', '\0')

    # The easy stuff, cast to str in case of numbers
    if '%a' in fmt:
        fmt = fmt.replace('%a', index_dictionary_none(song_data.artist) or '')
    if '%b' in fmt:
        fmt = fmt.replace('%b', index_dictionary_none(song_data.album) or '')
    if '%T' in fmt:
        fmt = fmt.replace('%T', index_dictionary_none(song_data.title) or '')
    if '%t' in fmt:
        fmt = fmt.replace('%t', index_dictionary_none(song_data.titleShort) or '')
    if '%#' in fmt:
        fmt = fmt.replace('%#', str(index_dictionary_none(song_data.track) or ''))
    if '%k' in fmt:
        fmt = fmt.replace('%k', str(index_dictionary_none(song_data.disc) or ''))
    if '%x' in fmt:
        fmt = fmt.replace('%x', 'Explicit' if index_dictionary_none(song_data.explicit) else 'Clean')
    if '%f' in fmt:
        fmt = fmt.replace('%f', filename)  # add param
    if '%i' in fmt:
        fmt = fmt.replace('%i', index_dictionary_none(song_data.ISRC) or '')
    if '%c' in fmt:
        fmt = fmt.replace('%c', index_dictionary_none(song_data.composer) or '')
    if '%g' in fmt:
        fmt = fmt.replace('%g', index_dictionary_none(song_data.genre) or '')

    # Year
    if '%Y' in fmt:
        fmt = fmt.replace('%Y', str(index_dictionary(song_data.releaseDate).year))
    if '%y' in fmt:
        fmt = fmt.replace('%y', str(index_dictionary(song_data.releaseDate).year)[2:4])

    # Month
    if '%M' in fmt:
        fmt = fmt.replace('%M', "{:02d}".format(index_dictionary(song_data.releaseDate).month))
    if '%m' in fmt:
        fmt = fmt.replace('%m', str(index_dictionary(song_data.releaseDate).month))

    # Day
    if '%D' in fmt:
        fmt = fmt.replace('%D', "{:02d}".format(index_dictionary(song_data.releaseDate).day))
    if '%d' in fmt:
        fmt = fmt.replace('%d', str(index_dictionary(song_data.releaseDate).day))

    # Replace the placeholder
    if '\0' in fmt:
        fmt = fmt.replace('\0', '%')

    # Clean up the string
    return re.sub(r'\s+', ' ', fmt.strip())


def error_print(error):
    """Print an error to stderr if not quiet."""
    if not error_print.silent:
        print(error, file=sys.stderr)


# Store if quiet or not, default is no
error_print.silent = False


def artist_url_list(artists):
    """Get all URLs for the artist, returns a list."""
    artist_list = list()
    for _ in artists:
        for url in ["external_urls"]:
            artist_list.append(url)

    return artist_list


def str_artists(artists):
    """Generate a pretty string from multiple artists (a list) from Spotify."""
    artist_string = ''
    for artist in artists:
        artist_string += artist["name"] + ', '

    artist_string = artist_string.rstrip(', ')

    return artist_string


def download_file(url: str, filename: str):
    """Download a file given a URL and save to the location specified by the format string; extension added
    automatically. """
    # Download the file
    r = requests.get(url)

    # Get the file extension
    # Probably not good, but it works for all of them so w/e
    extension = r.headers['Content-Type'].split('/')[-1].split('-')[-1]

    # Check for duplicate filename
    full_filename = unique_filename(filename + '.' + extension)

    # Save it
    with open(full_filename, 'wb') as f:
        f.write(r.content)


def parse_time(time):
    """Convert a string in the format "m:ss.ms", "m:s", "s.ms", or "s"."""
    time = str(time)

    milliseconds = 0
    minutes = 0

    try:
        # Get milliseconds
        split_ms = time.split('.')
        if len(split_ms) == 2:
            milliseconds = int(split_ms[1])

        # Get minutes
        split_min = split_ms[0].split(':')
        if len(split_min) == 2:
            minutes = int(split_min[0])
            seconds = int(split_min[1])
        else:
            seconds = int(split_min[0])
    except ValueError:
        error_print('WARNING: Invalid time entered. Make sure it is in the format "m:ss.ms", "m:ss", "s.ms", '
                    'or "s". Will use default time value instead.')
        return parse_time('0:18')

    return milliseconds + seconds * 1000 + minutes * 60 * 1000


def fmt_apple_art(data):
    """Put the Apple art into a list. Also reformat URL with usable width and height."""
    width = data["width"]
    height = data["height"]
    url = data["url"]

    url = url.replace("{w}", str(width))
    url = url.replace("{h}", str(height))

    return url


def print_data(source, json_data):
    """Print info about the data given a source and the JSON response."""
    # Lyrics
    if 'lyrics' == source:
        print("\nLyrics:")
        print(json_data["result"]["lyrics"]["lyrics"])

    # Apple Music
    if 'apple_music' == source:
        print("\nApple Music:")
        print("Kind: " + json_data["result"]["apple_music"]["playParams"]["kind"].title())
        print("Title: " + json_data["result"]["apple_music"]["name"])
        print("Artist: " + json_data["result"]["apple_music"]["artistName"])
        print("Composer: " + json_data["result"]["apple_music"]["composerName"])
        print("Release Date: " + json_data["result"]["apple_music"]["releaseDate"])
        print("Genre: " + gen_genre_string(json_data["result"]["apple_music"]["genreNames"]))
        print("Duration: " + fmt_ms(json_data["result"]["apple_music"]["durationInMillis"]))
        print("Album: " + json_data["result"]["apple_music"]["albumName"])
        print("Disc: " + str(json_data["result"]["apple_music"]["discNumber"]))
        print("Track: " + str(json_data["result"]["apple_music"]["trackNumber"]))
        print("Link: " + json_data["result"]["apple_music"]["url"])
        print("Artwork: " + fmt_apple_art(json_data["result"]["apple_music"]["artwork"]))

        print("Preview Links: ")
        for link in json_data["result"]["apple_music"]["previews"]:
            print("\t" + link["url"])

        print("ISRC: " + json_data["result"]["apple_music"]["isrc"])

    # Spotify
    if 'spotify' == source:
        print("\nSpotify:")
        print("Type: " + json_data["result"]["spotify"]["type"].title())
        print("Title: " + json_data["result"]["spotify"]["name"])
        print("Artists: " + str_artists(json_data["result"]["spotify"]["artists"]))
        print("Release Date: " + json_data["result"]["spotify"]["album"]["release_date"])
        print("Duration: " + fmt_ms(json_data["result"]["spotify"]["duration_ms"]))
        print("Explicit: " + str(json_data["result"]["spotify"]["explicit"]))
        print("Album: " + json_data["result"]["spotify"]["album"]["name"])
        print("Disc: " + str(json_data["result"]["spotify"]["disc_number"]))
        print("Track: " + str(json_data["result"]["spotify"]["track_number"]))
        print("Popularity out of 100: " + str(json_data["result"]["spotify"]["popularity"]))

        for key in json_data["result"]["spotify"]["external_ids"]:
            print(key.title() + ": " + json_data["result"]["spotify"]["external_ids"][key])
        print("External URLs:")

        for key in json_data["result"]["spotify"]["external_urls"]:
            print("\t" + key.title() + ": " + json_data["result"]["spotify"]["external_urls"][key])

        print("Artist URLs:")
        for artist in json_data["result"]["spotify"]["artists"]:
            print("\t" + artist["name"] + ":")
            for url in artist["external_urls"]:
                print("\t\t" + url.title() + ": " + artist["external_urls"][url])

        print("Album URLs:")
        for key in json_data["result"]["spotify"]["album"]["external_urls"]:
            print("\t" + key.title() + ": " + json_data["result"]["spotify"]["album"]["external_urls"][key])

        print("Tracks in Album: " + str(json_data["result"]["spotify"]["album"]["total_tracks"]))

        print("Album Art:")
        for key in json_data["result"]["spotify"]["album"]["images"]:
            print("\t" + key["url"])

        print("Available Markets: " + ("N/A" if json_data["result"]["spotify"]["available_markets"] is None else str(
            json_data["result"]["spotify"]["available_markets"])))

    # Napster
    if 'napster' == source:
        print("\nNapster:")
        print("Type: " + json_data["result"]["napster"]["type"].title())
        print("Title: " + json_data["result"]["napster"]["name"])
        print("Artist: " + json_data["result"]["napster"]["artistName"])
        print("Duration in Seconds: " + fmt_sec(json_data["result"]["napster"]["playbackSeconds"]))
        print("Explicit: " + str(json_data["result"]["napster"]["isExplicit"]))
        print("Album: " + json_data["result"]["napster"]["albumName"])
        print("Disc: " + str(json_data["result"]["napster"]["disc"]))
        print("Track: " + str(json_data["result"]["napster"]["index"]))
        print("Is Streamable: " + str(json_data["result"]["napster"]["isStreamable"]))
        print("Available in High Resolution: " + str(json_data["result"]["napster"]["isAvailableInHiRes"]))
        print("Preview URL: " + json_data["result"]["napster"]["previewURL"])
        print("ISRC: " + json_data["result"]["napster"]["isrc"])

    # Deezer
    if 'deezer' == source:
        print("\nDeezer:")
        print("Type: " + json_data["result"]["deezer"]["type"].title())
        print("Title: " + json_data["result"]["deezer"]["title"])
        print("Short Title: " + json_data["result"]["deezer"]["title_short"])
        print("Artist: " + json_data["result"]["deezer"]["artist"]["name"])
        print("Duration: " + fmt_sec(json_data["result"]["deezer"]["duration"]))
        print("Explicit: " + str(json_data["result"]["deezer"]["explicit_lyrics"]))
        print("Track Version: " + json_data["result"]["deezer"]["title_version"])
        print("Album: " + json_data["result"]["deezer"]["album"]["title"])
        print("Rank: " + str(json_data["result"]["deezer"]["rank"]))
        print("Album Art: " + json_data["result"]["deezer"]["album"]["cover"])
        print("Artist Photo: " + json_data["result"]["deezer"]["artist"]["picture"])
        print("Artist URL: " + json_data["result"]["deezer"]["artist"]["link"])
        print("Link to Album Tracklist: " + json_data["result"]["deezer"]["album"]["tracklist"])


def index_dictionary(dictionary: dict, n=0):
    """Get the value given a dictionary and an index. Raises an IndexError if out of bounds."""
    if n < 0:
        n += len(dictionary)
    for i, key in enumerate(dictionary.keys()):
        if i == n:
            return dictionary[key]
    raise IndexError('ERROR: Index out of bounds in dictionary.')


def index_dictionary_none(dictionary: dict, n=0):
    """Same as index_dictionary(), but returns None if IndexError is raised."""
    try:
        return index_dictionary(dictionary, n)
    except IndexError:
        return None


def fmt_sec(sec):
    """Take a time in seconds and convert it to mm:ss.ms"""
    return fmt_ms(int(sec) * 1000)


def fmt_ms(ms):
    """Take a time in milliseconds and convert it to mm:ss.ms"""
    time = int(ms)

    minutes = int(time / (60 * 1000))
    time -= minutes * (60 * 1000)

    seconds = time / 1000

    return str(minutes) + ':' + "{seconds:.3f}".format(seconds=seconds)


# Run the program
if __name__ == '__main__':
    # Return how many errors there were when we exit
    sys.exit(cli())
