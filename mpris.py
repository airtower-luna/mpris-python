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

import gi.repository
import pydbus
import sys
from datetime import timedelta


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


def _list_commands():
    print("The following commands are supported:")
    print("\tstatus\tshow player status")
    print("\ttoggle\ttoggle play/pause state")
    print("\tstop\tstop playback")
    print("\tplay\tstart playback")
    print("\tpause\tpause playback")
    print("\tnext\tplay next track")
    print("\tprev[ious]\tplay previous track")
    print("\topen URI\topen media from URI and start playback")
    print("\tservices\tlist available players")


def _open_service(services, select):
    # try to open a service from the given list "services" by number
    # or dbus name in "select"
    service = None
    try:
        no = int(select)
        service = MprisService(services[no])
    except IndexError:
        print(f'MPRIS2 service no. {no} not found.')
    except ValueError:
        # no number provided, try name matching
        for s in services:
            if s.endswith(select):
                service = MprisService(s)
        if service is None:
            print(f'MPRIS2 service "{args.service}" not found.')
    return service


if __name__ == "__main__":
    import argparse
    from collections import deque

    # get available services via dbus
    services = get_services()

    parser = argparse.ArgumentParser(description="Manage an MPRIS2 "
                                     "compatible music player")
    parser.add_argument("command",
                        help='player command to execute, default: "status"',
                        nargs="?", default="status",
                        choices=('status', 'toggle', 'stop', 'play', 'pause',
                                 'next', 'prev', 'open', 'services'))
    parser.add_argument("args", help='arguments for the command, if any',
                        nargs="*")
    service_arg = parser.add_argument(
        '-s', '--service', default=services[0],
        help='Access the specified service, either by number as provided '
        'by the "services" command, or by name. Names are matched from the '
        f'end, so the last part is enough. default: {services[0]}')
    parser.add_argument("-v", "--verbose", action="store_true",
                        help='enable extra output, useful for debugging')
    parser.add_argument("--commands", action="store_true",
                        help='list supported commands, then exit')

    # enable bash completion if argcomplete is available
    try:
        import argcomplete
        from argcomplete.completers import ChoicesCompleter
        service_arg.completer = ChoicesCompleter(services)
        argcomplete.autocomplete(parser)
    except ImportError:
        pass

    args = parser.parse_args()

    if (args.commands):
        _list_commands()
        exit(0)

    # if the command is "services", list available services and exit
    if (args.command == "services"):
        for i, s in enumerate(services):
            print(f'{i}: {s}')
            if args.verbose:
                service = _open_service(services, s)
                print(f'  playlists support:\t{bool(service.playlists)}')
                print(f'  tracklist support:\t{bool(service.tracklist)}')
                prop = service.base_properties()
                for s in prop.keys():
                    print(f'  {s}\t= {prop.get(s)}')
        exit(0)

    # try to access the service via dbus
    service = _open_service(services, args.service)
    if not service:
        exit(1)

    if args.verbose:
        print("selected service", service.name)
        print(f'  playlists support:\t{bool(service.playlists)}')
        print(f'  tracklist support:\t{bool(service.tracklist)}')
        prop = service.base_properties()
        for s in prop.keys():
            print(f'  {s}\t= {prop.get(s)}')
        print("player properties:")
        prop = service.player_properties()
        for k, v in prop.items():
            if k == 'Metadata':
                print('  current track metadata:')
                for mk, mv in v.items():
                    print(f'    {mk}\t= {mv}')
            else:
                print(f'  {k}\t= {v}')

    # regular commands: run and exit
    if (args.command == "status"):
        status = service.player.PlaybackStatus
        if status == 'Playing' or status == 'Paused':
            meta = service.player.Metadata
            try:
                pos = service.player.Position
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
        else:
            print(status)

    # check if the player allows control commands before attempting any
    elif not service.player.CanControl:
        print(f'Player {service.name} does not provide control access.')
        exit(1)

    elif (args.command == "toggle"):
        if service.player.CanPause:
            service.player.PlayPause()
        else:
            print("not supported")
            exit(2)

    elif (args.command == "stop"):
        # for some reason, there's no 'CanStop' property
        service.player.Stop()

    elif (args.command == "play"):
        if service.player.CanPlay:
            service.player.Play()
        else:
            print("not supported")
            exit(2)

    elif (args.command == "next"):
        if service.player.CanGoNext:
            service.player.Next()
        else:
            print("not supported")
            exit(2)

    elif (args.command == "prev" or args.command == "previous"):
        if service.player.CanGoPrevious:
            service.player.Previous()
        else:
            print("not supported")
            exit(2)

    elif (args.command == "pause"):
        if service.player.CanPause:
            service.player.Pause()
        else:
            print("not supported")
            exit(2)

    elif (args.command == "open"):
        try:
            print(f'opening {args.args[0]}')
            service.player.OpenUri(args.args[0])
        except gi.repository.GLib.GError as ex:
            if 'org.freedesktop.DBus.Error.NotSupported' in ex.message:
                print(f'Error: Service {service.name} does not support '
                      'opening URIs via MPRIS2.')
            else:
                print('Unexpected error!')
                raise

    else:
        print("unknown command:", args.command)
        exit(1)
