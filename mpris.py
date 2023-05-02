#!/usr/bin/python3
# PYTHON_ARGCOMPLETE_OK
"""command line client for MPRIS2 compatible media players"""

# The MIT License (MIT)
#
# Copyright (c) 2015-2023 Fiona Klute
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import functools
import gi.repository
import pydbus
import sys
from datetime import timedelta
from pathlib import Path


class UnsupportedOperation(Exception):
    """Raised when calling an MPRIS operation the player does not support."""
    pass


class MprisService:
    """Class representing an MPRIS2 compatible media player"""

    mpris_base = 'org.mpris.MediaPlayer2'
    player_interface = mpris_base + '.Player'
    tracklist_interface = mpris_base + '.TrackList'
    playlists_interface = mpris_base + '.Playlists'
    # see http://dbus.freedesktop.org/doc/dbus-specification.html#standard-interfaces-properties # noqa
    properties_interface = 'org.freedesktop.DBus.Properties'

    def __init__(self, servicename):
        """Initialize an MprisService object for the specified service name"""
        bus = pydbus.SessionBus()
        self.name = servicename
        self._proxy = bus.get(self.name, '/org/mpris/MediaPlayer2')
        self.player = self._proxy[self.player_interface]
        self.properties = self._proxy[self.properties_interface]
        # tracklist is an optional interface
        try:
            self.tracklist = self._proxy[self.tracklist_interface]
        except KeyError:
            self.tracklist = None
        # playlists is an optional interface
        try:
            self.playlists = self._proxy[self.playlists_interface]
        except KeyError:
            self.playlists = None

    def base_properties(self):
        """Get all basic service properties"""
        return self.properties.GetAll(self.mpris_base)

    def player_properties(self):
        """Get all player properties"""
        return self.properties.GetAll(self.player_interface)

    def _assert_control(self):
        if not self.player.CanControl:
            raise UnsupportedOperation(
                f'{self.name} does not provide control access')

    def open(self, uri):
        """open media from URI and start playback"""
        try:
            self.player.OpenUri(uri)
        except AttributeError as ex:
            raise UnsupportedOperation(
                f'{self.name} does not support opening URIs') from ex

    def next(self):
        self._assert_control()
        if not self.player.CanGoNext:
            raise UnsupportedOperation(
                f'{self.name} does not support switching to next track')
        self.player.Next()

    def previous(self):
        self._assert_control()
        if not self.player.CanGoPrevious:
            raise UnsupportedOperation(
                f'{self.name} does not support switching to previous track')
        self.player.Previous()

    def pause(self):
        self._assert_control()
        if not self.player.CanPause:
            raise UnsupportedOperation(
                f'{self.name} does not support pausing')
        self.player.Pause()

    def play(self):
        self._assert_control()
        if not self.player.CanPlay:
            raise UnsupportedOperation(
                f'{self.name} does not support playing')
        self.player.Play()

    def stop(self):
        self._assert_control()
        self.player.Stop()

    def toggle(self):
        self._assert_control()
        if not self.player.CanPause:
            raise UnsupportedOperation(
                f'{self.name} does not support pausing')
        self.player.PlayPause()


def get_services():
    """Get the list of available MPRIS2 services

    :returns: a list of strings
    """
    services = []
    bus = pydbus.SessionBus()
    for s in bus.get('.DBus').ListNames():
        if s.startswith(MprisService.mpris_base):
            services.append(s)
    return services


def track_length_string(length):
    """Convert track length in microseconds into human readable format

    :param length: track length in microseconds
    :returns: formatted string
    """
    return str(timedelta(microseconds=length))


def _next(args):
    """play next track"""
    args.service.next()


def _open(args):
    """open media from URI and start playback"""
    p = Path(args.uri)
    if p.is_file():
        uri = p.resolve().as_uri()
    else:
        # hope the user has provided a valid URI
        uri = args.uri

    print(f'opening {uri}')
    args.service.open(uri)


def _pause(args):
    """pause playback"""
    args.service.pause()


def _play(args):
    """start playback"""
    args.service.play()


def _prev(args):
    """play previous track"""
    args.service.previous()


def _services(args, services):
    """list available services"""
    for i, s in enumerate(services):
        print(f'{i}: {s}')
        if args.verbose:
            service = MprisService(s)
            print(f'  playlists support:\t{bool(service.playlists)}')
            print(f'  tracklist support:\t{bool(service.tracklist)}')
            prop = service.base_properties()
            for s in prop.keys():
                print(f'  {s}\t= {prop.get(s)}')


def _status(args):
    """show player status"""
    status = args.service.player.PlaybackStatus
    if status not in {'Playing', 'Paused'}:
        print(status)
        return

    meta = args.service.player.Metadata
    try:
        pos = args.service.player.Position
    except gi.repository.GLib.GError as ex:
        if 'org.freedesktop.DBus.Error.NotSupported' in ex.message:
            # player doesn't suport position request
            pos = None
        else:
            print('Error while retrieving playback position!',
                  file=sys.stderr)
            raise
    # length might not be defined, e.g. in case of a live stream
    length = meta.get('mpris:length')
    len_str = ''
    if length:
        pos_str = track_length_string(pos) if pos else '???'
        len_str = f'({pos_str}/{track_length_string(length)})'
    title = meta.get('xesam:title') or meta.get('xesam:url')
    artist = '[Unknown]'
    artists = meta.get('xesam:artist')
    if artists:
        artists = deque(artists)
        artist = artists.popleft()
        while len(artists) > 0:
            artist = artist + ', ' + artists.popleft()
    print(f'{status}: "{title}" by {artist} {len_str}')


def _stop(args):
    """stop playback"""
    args.service.stop()


def _toggle(args):
    """toggle play/pause state"""
    args.service.toggle()


def _open_service(services, select):
    # try to open a service from the given list "services" by number
    # or dbus name in "select"
    service = None
    try:
        no = int(select)
        service = MprisService(services[no])
    except IndexError:
        raise ValueError(f'MPRIS2 service no. {no} not found')
    except ValueError:
        # no number provided, try name matching
        for s in services:
            if s.endswith(select):
                service = MprisService(s)
        if service is None:
            raise ValueError(f'MPRIS2 service "{select}" not found')
    return service


if __name__ == "__main__":
    import argparse
    from collections import deque

    # get available services via dbus
    services = get_services()

    def mpris_service(s):
        return _open_service(services, s)

    parser = argparse.ArgumentParser(description="Manage an MPRIS2 "
                                     "compatible music player")
    service_arg = parser.add_argument(
        '-s', '--service', default=services[0], type=mpris_service,
        help='Access the specified service, either by number as provided '
        'by the "services" command, or by name. Names are matched from the '
        f'end, so the last part is enough. default: {services[0]}')
    parser.add_argument("-v", "--verbose", action="store_true",
                        help='enable extra output, useful for debugging')
    subparsers = parser.add_subparsers(description='What to do?')
    subparsers.add_parser(
        'next', help=_next.__doc__).set_defaults(func=_next)
    subparsers.add_parser(
        'pause', help=_pause.__doc__).set_defaults(func=_pause)
    subparsers.add_parser(
        'play', help=_play.__doc__).set_defaults(func=_play)
    subparsers.add_parser(
        'prev', help=_prev.__doc__).set_defaults(func=_prev)
    subparsers.add_parser(
        'services', help=_services.__doc__).set_defaults(
            func=functools.partial(_services, services=services))
    subparsers.add_parser(
        'status', help=_status.__doc__).set_defaults(func=_status)
    subparsers.add_parser(
        'stop', help=_stop.__doc__).set_defaults(func=_stop)
    subparsers.add_parser(
        'toggle', help=_toggle.__doc__).set_defaults(func=_toggle)
    parser_open = subparsers.add_parser('open', help=_open.__doc__)
    parser_open.set_defaults(func=_open)
    parser_open.add_argument('uri', help='file or URI to open')

    # enable bash completion if argcomplete is available
    try:
        import argcomplete
        from argcomplete.completers import ChoicesCompleter
        service_arg.completer = ChoicesCompleter(services)
        argcomplete.autocomplete(parser)
    except ImportError:
        pass

    args = parser.parse_args()

    if args.verbose:
        print("selected service", args.service.name)
        print(f'  playlists support:\t{bool(args.service.playlists)}')
        print(f'  tracklist support:\t{bool(args.service.tracklist)}')
        prop = args.service.base_properties()
        for s in prop.keys():
            print(f'  {s}\t= {prop.get(s)}')
        print("player properties:")
        prop = args.service.player_properties()
        for k, v in prop.items():
            if k == 'Metadata':
                print('  current track metadata:')
                for mk, mv in v.items():
                    print(f'    {mk}\t= {mv}')
            else:
                print(f'  {k}\t= {v}')

    try:
        args.func(args)
    except UnsupportedOperation as ex:
        print(ex, file=sys.stderr)
        sys.exit(2)
