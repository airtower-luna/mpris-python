#!/usr/bin/python3
# PYTHON_ARGCOMPLETE_OK
"""command line client for MPRIS2 compatible media players"""

# The MIT License (MIT)
#
# Copyright (c) 2015 Fiona Klute
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import dbus

class MprisService:
    """Class representing an MPRIS2 compatible media player"""

    mpris_base = 'org.mpris.MediaPlayer2'
    player_interface = mpris_base + '.Player'
    tracklist_interface = mpris_base + '.TrackList'
    playlists_interface = mpris_base + '.Playlists'
    # see http://dbus.freedesktop.org/doc/dbus-specification.html#standard-interfaces-properties
    properties_interface = 'org.freedesktop.DBus.Properties'

    def __init__(self, servicename):
        """Initialize an MprisService object for the specified service name"""
        bus = dbus.SessionBus()
        self.name = servicename
        self.proxy = bus.get_object(self.name, '/org/mpris/MediaPlayer2')
        self.player = dbus.Interface(self.proxy,
                                     dbus_interface=self.player_interface)
        # tracklist is an optional interface, may be None depending on service
        self.tracklist = dbus.Interface(self.proxy,
                                        dbus_interface=self.tracklist_interface)
        # playlists is an optional interface, may be None depending on service
        self.playlists = dbus.Interface(self.proxy,
                                        dbus_interface=self.playlists_interface)
        self.properties = dbus.Interface(self.proxy,
                                         dbus_interface=self.properties_interface)
        # check if optional interfaces are available
        try:
            self.get_playlists_property('PlaylistCount')
        except dbus.exceptions.DBusException:
            self.playlists = None
        try:
            self.get_tracklist_property('CanEditTracks')
        except dbus.exceptions.DBusException:
            self.tracklist = None

    def base_properties(self):
        """Get all basic service properties"""
        return self.properties.GetAll(self.mpris_base)
    def player_properties(self):
        """Get all player properties"""
        return self.properties.GetAll(self.player_interface)
    def get_player_property(self, name):
        """Get the player property described by name"""
        return self.properties.Get(self.player_interface, name)
    def get_playlists_property(self, name):
        """Get the playlists property described by name"""
        return self.properties.Get(self.playlists_interface, name)
    def get_tracklist_property(self, name):
        """Get the tracklist property described by name"""
        return self.properties.Get(self.tracklist_interface, name)

def get_services():
    """Get the list of available MPRIS2 services

    :returns: a list of strings
    """
    services = []
    bus = dbus.SessionBus()
    for s in bus.list_names():
        if s.startswith(MprisService.mpris_base):
            services.append(s)
    return services

def track_length_string(length):
    """Convert track length in microseconds into human readable format

    :param length: track length in microseconds
    :returns: formatted string
    """
    us = length % 1000
    ms = int((length / 1000) % 1000)
    s = int(length / 1000000)
    minutes = int(s / 60)
    s = s - minutes * 60
    if us != 0:
        return "%d:%02d.%03d%03d" % (minutes, s, ms, us)
    elif ms != 0:
        return "%d:%02d.%03d" % (minutes, s, ms)
    else:
        return "%d:%02d" % (minutes, s)

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
        print("MPRIS2 service no. %d not found." % no)
    except ValueError:
        # no number provided, try name matching
        for s in services:
            if s.endswith(select):
                service = MprisService(s)
        if service == None:
            print("MPRIS2 service \"%s\" not found." % args.service)
    return service



if __name__ == "__main__":
    import argparse
    from collections import deque
    parser = argparse.ArgumentParser(description="Manage an MPRIS2 "
                                     "compatible music player")
    parser.add_argument("command",
                        help='player command to execute, default: "status"',
                        nargs="?", default="status",
                        choices=('status', 'toggle', 'stop', 'play', 'pause',
                                 'next', 'prev', 'open', 'services'))
    parser.add_argument("args", help='arguments for the command, if any',
                        nargs="*")
    parser.add_argument("-s", "--service",
                        help='Access the specified service, either by number '
                        'as provided by the "services" command, or by name. '
                        'Names are matched from the end, so the last part is '
                        'enough. default: 0', default='0')
    parser.add_argument("-v", "--verbose", action="store_true",
                        help='enable extra output, useful for debugging')
    parser.add_argument("--commands", action="store_true",
                        help='list supported commands, then exit')

    # enable bash completion if argcomplete is available
    try:
        import argcomplete
        argcomplete.autocomplete(parser)
    except ImportError:
        pass

    args = parser.parse_args()

    if (args.commands):
        _list_commands()
        exit(0)

    # if the command is "services", list services available via dbus and exit
    services = get_services()
    if (args.command == "services"):
        i = 0
        for s in services:
            print("%d: %s" % (i, s))
            if args.verbose:
                service = _open_service(services, s)
                print("  playlists support:\t%s" % (service.playlists != None))
                print("  tracklist support:\t%s" % (service.tracklist != None))
                prop = service.base_properties()
                for s in prop.keys():
                    print("  %s\t= %s" % (s, prop.get(s)))
            i = i + 1
        exit(0)

    # try to access the service via dbus
    service = _open_service(services, args.service)
    if not service:
        exit(1)

    if args.verbose:
        print("selected service", service.name)
        print("  playlists support:\t%s" % (service.playlists != None))
        print("  tracklist support:\t%s" % (service.tracklist != None))
        prop = service.base_properties()
        for s in prop.keys():
            print("  %s\t= %s" % (s, prop.get(s)))
        print("player properties:")
        prop = service.player_properties()
        for s in prop.keys():
            if s == 'Metadata':
                print('  current track metadata:')
                meta = prop.get(s)
                for k in meta.keys():
                    print("    %s\t= %s" % (k, meta.get(k)))
            else:
                print("  %s\t= %s" % (s, prop.get(s)))

    # regular commands: run and exit
    if (args.command == "status"):
        status = service.get_player_property('PlaybackStatus')
        if status == 'Playing' or status == 'Paused':
            meta = service.get_player_property('Metadata')
            pos = service.get_player_property('Position')
            # length might not be defined, e.g. in case of a live stream
            length = meta.get('mpris:length')
            len_str = ''
            if length:
                len_str = "(%s/%s)" % (track_length_string(pos),
                                       track_length_string(length))
            title = meta.get('xesam:title') or meta.get('xesam:url')
            artist = '[Unknown]'
            artists = meta.get('xesam:artist')
            if artists:
                artists = deque(artists)
                artist = artists.popleft()
                while len(artists) > 0:
                    artist = artist + ', ' + artists.popleft()
            print("%s: \"%s\" by %s %s"
                  % (status, title, artist, len_str))
        else:
            print(status)

    # check if the player allows control commands before attempting any
    elif not service.get_player_property('CanControl'):
        print("Player %s does not provide control access." % (service.name))
        exit(1)

    elif (args.command == "toggle"):
        if service.get_player_property('CanPause'):
            service.player.PlayPause()
        else:
            print("not supported")
            exit(2)

    elif (args.command == "stop"):
        # for some reason, there's no 'CanStop' property
        service.player.Stop()

    elif (args.command == "play"):
        if service.get_player_property('CanPlay'):
            service.player.Play()
        else:
            print("not supported")
            exit(2)

    elif (args.command == "next"):
        if service.get_player_property('CanGoNext'):
            service.player.Next()
        else:
            print("not supported")
            exit(2)

    elif (args.command == "prev" or args.command == "previous"):
        if service.get_player_property('CanGoPrevious'):
            service.player.Previous()
        else:
            print("not supported")
            exit(2)

    elif (args.command == "pause"):
        if service.get_player_property('CanPause'):
            service.player.Pause()
        else:
            print("not supported")
            exit(2)

    elif (args.command == "open"):
        try:
            print("opening %s" % (args.args[0]))
            service.player.OpenUri(args.args[0])
        except dbus.exceptions.DBusException as ex:
            if (ex.get_dbus_name().endswith('UnknownMethod')):
                print("Error: Service %s does not support opening URIs via "
                      "MPRIS2." % (service.name))
            else:
                print('Unexpected error:', ex)
            exit(1)

    else:
        print("unknown command:", args.command)
        exit(1)
