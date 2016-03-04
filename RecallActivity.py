#Copyright (c) 2012 Walter Bender

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# You should have received a copy of the GNU General Public License
# along with this library; if not, write to the Free Software
# Foundation, 51 Franklin Street, Suite 500 Boston, MA 02110-1335 USA

from gi.repository import Gtk
from gi.repository import Gdk

import dbus
import telepathy
import logging
from gettext import gettext as _
from dbus.service import signal
from dbus.gobject_service import ExportedGObject

from toolbar_utils import button_factory, radio_factory, label_factory, \
    separator_factory
from utils import json_load, json_dump

from sugar3 import profile
from sugar3.activity import activity
from sugar3.presence import presenceservice
from sugar3.presence.tubeconn import TubeConnection

try:
    from sugar3.presence.wrapper import CollabWrapper
    logging.error('USING SUGAR COLLAB WRAPPER!')
except ImportError:
    from collabwrapper.collabwrapper import CollabWrapper

from sugar3.graphics.toolbarbox import ToolbarBox
from sugar3.activity.widgets import ActivityToolbarButton
from sugar3.activity.widgets import StopButton

from game import Game

import logging
_logger = logging.getLogger('recall-activity')


SERVICE = 'org.sugarlabs.RecallActivity'
IFACE = SERVICE


class RecallActivity(activity.Activity):
    """ A memory game """

    def __init__(self, handle):
        """ Initialize the toolbars and the game board """
        super(RecallActivity, self).__init__(handle)

        self.path = activity.get_bundle_path()

        self.nick = profile.get_nick_name()
        if profile.get_color() is not None:
            self.colors = profile.get_color().to_string().split(',')
        else:
            self.colors = ['#A0FFA0', '#FF8080']

        self._restoring = False
        self._setup_toolbars(True)

        # Create a canvas
        canvas = Gtk.DrawingArea()
        canvas.set_size_request(Gdk.Screen.width(), \
                                Gdk.Screen.height())
        self.set_canvas(canvas)
        canvas.show()
        self.show_all()

        self._game = Game(canvas, parent=self, path=self.path,
                          colors=self.colors)
        self._setup_collab()
        if 'dotlist' in self.metadata:
            self._restore()
        else:
            self._game.new_game()

    def _setup_toolbars(self, have_toolbox):
        """ Setup the toolbars. """

        self.max_participants = 4
        toolbox = ToolbarBox()

        # Activity toolbar
        activity_button = ActivityToolbarButton(self)

        toolbox.toolbar.insert(activity_button, 0)
        activity_button.show()

        self.set_toolbar_box(toolbox)
        toolbox.show()
        self.toolbar = toolbox.toolbar

        self.radio = []
        self.radio.append(radio_factory(
            'game-1', self.toolbar, self._new_game_cb,
            cb_arg=0, tooltip=_('Play attention game (repeated symbol).'),
            group=None))
        self.radio.append(radio_factory(
            'game-2', self.toolbar, self._new_game_cb,
            cb_arg=1, tooltip=_('Play attention game (missing symbol).'),
            group=self.radio[0]))
        self.radio.append(radio_factory(
            'game-4', self.toolbar, self._new_game_cb,
            cb_arg=2, tooltip=_('Play n-back game.'),
            group=self.radio[0]))
        """
        # Game mode disabled
        self.radio.append(radio_factory(
            'game-3', self.toolbar, self._new_game_cb,
            cb_arg=3, tooltip=_('Play attention game (color symbols).'),
            group=self.radio[0]))
        """

        self.status = label_factory(self.toolbar, '')

        separator_factory(toolbox.toolbar, True, False)

        stop_button = StopButton(self)
        stop_button.props.accelerator = '<Ctrl>q'
        toolbox.toolbar.insert(stop_button, -1)
        stop_button.show()

    def _new_game_cb(self, button=None, game=0):
        ''' Reload a new level. '''
        self._game.new_game(game=game, restart=(not self._restoring))

    def write_file(self, file_path):
        """ Write the grid status to the Journal """
        dot_list, correct, level, game = self._game.save_game()
        self.metadata['dotlist'] = ''
        for dot in dot_list:
            self.metadata['dotlist'] += str(dot)
            if dot_list.index(dot) < len(dot_list) - 1:
                self.metadata['dotlist'] += ' '
        self.metadata['correct'] = str(correct)
        self.metadata['level'] = str(level)
        self.metadata['game'] = str(game)

    def _restore(self):
        """ Restore the game state from metadata """
        self._restoring = True
        dot_list = []
        dots = self.metadata['dotlist'].split()
        for dot in dots:
            dot_list.append(int(dot))
        if 'correct' in self.metadata:
            correct = int(self.metadata['correct'])
        else:
            correct = 0
        if 'level' in self.metadata:
            level = int(self.metadata['level'])
        else:
            level = 0
        if 'game' in self.metadata:
            game = int(self.metadata['game'])
            self.radio[game].set_active(True)
        else:
            game = 0
        self._game.restore_game(dot_list, correct, level, game)
        self._restoring = False

    # Collaboration-related methods

    def _setup_collab(self):
        """ Setup the Collab Wrapper. """
        self.initiating = None  # sharing (True) or joining (False)
        self._collab = CollabWrapper(self)
        self._collab.connect('message', self.__message_cb)

        owner = self._collab._leader
        self.owner = owner

        self._game.set_sharing(True)

    def __message_cb(self, collab, buddy, message):
        action = message.get('action')
        payload = message.get('payload')
        if action == 'n':
            '''Get a new game grid'''
            self._receive_new_game(payload)
        elif action == 'p':
            '''Get a dot click'''
            self._receive_dot_click(payload)

    def send_new_game(self):
        ''' Send a new grid to all players '''
        self._collab.post(dict(
                action = 'n',
                payload = json_dump(self._game.save_game())
            ))

    def _receive_new_game(self, payload):
        ''' Sharer can start a new game. '''
        dot_list, correct, level, game = json_load(payload)
        self._game.restore_game(dot_list, correct, level, game)

    def send_dot_click(self, dot, color):
        ''' Send a dot click to all the players '''
        self._collab.post(dict(
                action = 'p',
                payload = json_dump([dot, color])
            ))

    def _receive_dot_click(self, payload):
        ''' When a dot is clicked, everyone should change its color. '''
        (dot, color) = json_load(payload)
        self._game.remote_button_press(dot, color)

