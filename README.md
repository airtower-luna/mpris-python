# MPRIS2 client in Python

mpris-python is a simple command line
[MPRIS2](https://specifications.freedesktop.org/mpris-spec/latest/)
client which doubles as a rudimentary MPRIS client library. It allows
you to send commands to any MPRIS2 compatible media player from the
command line. The [pydbus library](https://github.com/LEW21/pydbus) is
used to communicate with the media player.

## Usage

Check `mpris.py -h` for available commands and options.

Note that media players can restrict what commands MPRIS clients may
send them, and some MPRIS interfaces and methods are
optional. Audacious 4.2 is known not to support opening media via
MPRIS, and none of the players I use support
**org.mpris.MediaPlayer2.TrackList** or
**org.mpris.MediaPlayer2.Playlists**.
