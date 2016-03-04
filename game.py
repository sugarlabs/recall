# -*- coding: utf-8 -*-
#Copyright (c) 2012 Walter Bender

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# You should have received a copy of the GNU General Public License
# along with this library; if not, write to the Free Software
# Foundation, 51 Franklin Street, Suite 500 Boston, MA 02110-1335 USA

'''
Three different games:
(0) find the repeated image
(1) find the image not shown in the collection
(2) recall the image shown previously
'''

import cairo
import os
from random import uniform

from gettext import gettext as _
from gettext import ngettext

import logging
_logger = logging.getLogger('search-activity')

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GObject
from gi.repository import GdkPixbuf

from sugar3.graphics import style
GRID_CELL_SIZE = style.GRID_CELL_SIZE

DOT_SIZE = 40


from sprites import Sprites, Sprite


def glob(path, end):
    files = []
    for name in os.listdir(path):
        if name.endswith(end):
            files.append(os.path.join(path, name))

    return files


class Game():

    def __init__(self, canvas, parent=None, path=None,
                 colors=['#A0FFA0', '#FF8080']):
        self._canvas = canvas
        self._parent = parent
        self._parent.show_all()
        self._path = path

        self._colors = ['#FFFFFF']
        self._colors.append(colors[0])
        self._colors.append(colors[1])

        self._canvas.set_can_focus(True)
        self._canvas.connect("draw", self._draw_cb)
        self._canvas.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self._canvas.connect("button-press-event", self._button_press_cb)

        self._width = Gdk.Screen.width()
        self._height = Gdk.Screen.height() - (GRID_CELL_SIZE * 1.5)
        self._scale = self._height / (4 * DOT_SIZE * 1.3)
        self._dot_size = int(DOT_SIZE * self._scale)
        self._space = int(self._dot_size / 5.)
        self.we_are_sharing = False

        self._start_time = 0
        self._timeout_id = None

        self._level = 3
        self._game = 0
        self._correct = 0

        # Find the image files
        self._PATHS = glob(os.path.join(self._path, 'images'), '.png')
        self._CPATHS = glob(os.path.join(self._path, 'color-images'), '*.svg')

        # Generate the sprites we'll need...
        self._sprites = Sprites(self._canvas)
        self._dots = []
        self._opts = []
        yoffset = int(self._space / 2.)

        self._line = Sprite(
            self._sprites, 0,
            int(3 * (self._dot_size + self._space) + yoffset / 2.),
            self._line(vertical=False))

        for y in range(3):
            for x in range(6):
                xoffset = int((self._width - 6 * self._dot_size - \
                                   5 * self._space) / 2.)
                self._dots.append(
                    Sprite(self._sprites,
                           xoffset + x * (self._dot_size + self._space),
                           y * (self._dot_size + self._space) + yoffset,
                           self._new_dot_surface(color=self._colors[0])))
                self._dots[-1].type = -1  # No image
                self._dots[-1].set_label_attributes(72)

        y = 3
        for x in range(3):
            self._opts.append(
                Sprite(self._sprites,
                       xoffset + x * (self._dot_size + self._space),
                       y * (self._dot_size + self._space) + yoffset,
                       self._new_dot_surface(color=self._colors[0])))
            self._opts[-1].type = -1  # No image
            self._opts[-1].set_label_attributes(72)
            self._opts[-1].hide()

    def _all_clear(self):
        ''' Things to reinitialize when starting up a new game. '''
        if self._timeout_id is not None:
            GObject.source_remove(self._timeout_id)

        # Auto advance levels
        if self._correct > 3 and self._level < len(self._dots):
            self._level += 3
            self._correct = 0

        self._set_label('')
        for i in range(3):
            self._opts[i].hide()
            self._opts[i].type = -1
            self._opts[i].set_label('')

        for dot in self._dots:
            dot.type = -1
            if self._game == 2 or self._dots.index(dot) < self._level:
                dot.set_shape(self._new_dot_surface(
                            self._colors[abs(dot.type)]))
                dot.set_label('?')
                dot.set_layer(100)
            else:
                dot.hide()

        self._dance_counter = 0
        self._dance_step()

    def _dance_step(self):
        ''' Short animation before loading new game '''
        if self._game == 2:
            for i in range(len(self._dots)):
                self._dots[i].set_shape(self._new_dot_surface(
                        self._colors[int(uniform(0, 3))]))
        else:
            for i in range(self._level):
                self._dots[i].set_shape(self._new_dot_surface(
                        self._colors[int(uniform(0, 3))]))
        self._dance_counter += 1
        if self._dance_counter < 10:
            self._timeout_id = GObject.timeout_add(500, self._dance_step)
        else:
            self._new_game()

    def new_game(self, game=None, restart=True):
        ''' Start a new game. '''
        if game is not None:
            self._game = game
            self._level = 3
            self._correct = 0
        if restart:
            self._all_clear()

    def _image_in_dots(self, n):
        for i in range(self._level):
            if self._dots[i].type == n:
                return True
        return False

    def _image_in_opts(self, n):
        for i in range(3):
            if self._opts[i].type == n:
                return True
        return False

    def _choose_random_images(self):
        ''' Choose images at random '''
        if self._game == 3:
            maxi = len(self._CPATHS)
        else:
            maxi = len(self._PATHS)
        for i in range(self._level):
            if self._dots[i].type == -1:
                n = int(uniform(0, maxi))
                while self._image_in_dots(n):
                    n = int(uniform(0, maxi))
                self._dots[i].type = n
            if self._game == 3:
                self._dots[i].set_shape(self._new_dot_surface(
                        color_image=self._dots[i].type))
            else:
                self._dots[i].set_shape(self._new_dot_surface(
                        image=self._dots[i].type))
            self._dots[i].set_layer(100)
            self._dots[i].set_label('')

    def _load_image_from_list(self):
        if self._recall_counter == len(self._recall_list):
            self._timeout_id = GObject.timeout_add(
                1000, self._ask_the_question)
            return
        for dot in self._dots:
            dot.type = self._recall_list[self._recall_counter]
            dot.set_shape(self._new_dot_surface(image=dot.type))
            dot.set_layer(100)
            dot.set_label('')
        self._recall_counter += 1
        self._timeout_id = GObject.timeout_add(
            1000, self._load_image_from_list)

    def _find_repeat(self):
        ''' Find an image that repeats '''
        for i in range(self._level):
            for j in range(self._level - i - 1):
                if self._dots[i].type == self._dots[j].type:
                    return i
        return None

    def _new_game(self, restore=False):
        ''' Load game images and then ask a question... '''
        if self._game in [0, 1, 3]:
            self._choose_random_images()
        else:  # game 2
            # generate a random list
            self._recall_list = []
            for i in range(12):
                n = int(uniform(0, len(self._PATHS)))
                while n in self._recall_list:
                    n = int(uniform(0, len(self._PATHS)))
                self._recall_list.append(n)
            self._recall_counter = 0
            self._load_image_from_list()

        if self._game == 0:
            if not restore:
                # Repeat at least one of the images
                self._repeat = int(uniform(0, self._level))
                n = (self._repeat + int(uniform(1, self._level))) % self._level
                _logger.debug('repeat=%d, n=%d' % (self._repeat, n))
                self._dots[self._repeat].set_shape(self._new_dot_surface(
                        image=self._dots[n].type))
                self._dots[self._repeat].type = self._dots[n].type
            else:  # Find repeated image, as that is the answer
                self._repeat = self._find_repeat()
                if self._repeat is None:
                    _logger.debug('could not find repeat')
                    self._repeat = 0

        if self.we_are_sharing:
            _logger.debug('sending a new game')
            self._parent.send_new_game()

        if self._game in [0, 1, 3]:
            self._timeout_id = GObject.timeout_add(
                3000, self._ask_the_question)

    def _ask_the_question(self):
        ''' Each game has a challenge '''
        self._timeout_id = None
        # Hide the dots
        if self._game == 2:
            for dot in self._dots:
                dot.hide()
        else:
            for i in range(self._level):
                self._dots[i].hide()

        if self._game == 0:
            self._set_label(_('Recall which image was repeated.'))
            # Show the possible solutions
            for i in range(3):
                n = int(uniform(0, len(self._PATHS)))
                if self._level == 3:
                    while(n == self._dots[self._repeat].type or \
                          self._image_in_opts(n)):
                        n = int(uniform(0, len(self._PATHS)))
                else:
                    while(n == self._dots[self._repeat].type or \
                          not self._image_in_dots(n) or \
                          self._image_in_opts(n)):
                        n = int(uniform(0, len(self._PATHS)))
                self._opts[i].type = n
            self._answer = int(uniform(0, 3))
            self._opts[self._answer].type = self._dots[self._repeat].type
            for i in range(3):
                self._opts[i].set_shape(self._new_dot_surface(
                        image=self._opts[i].type))
                self._opts[i].set_layer(100)
        elif self._game == 1:
            self._set_label(_('Recall which image was not shown.'))
            # Show the possible solutions
            for i in range(3):
                n = int(uniform(0, len(self._PATHS)))
                while(not self._image_in_dots(n) or \
                      self._image_in_opts(n)):
                    n = int(uniform(0, len(self._PATHS)))
                self._opts[i].type = n
            self._answer = int(uniform(0, 3))
            n = int(uniform(0, len(self._PATHS)))
            while(self._image_in_dots(n)):
                n = int(uniform(0, len(self._PATHS)))
            self._opts[self._answer].type = n
            for i in range(3):
                self._opts[i].set_shape(self._new_dot_surface(
                        image=self._opts[i].type))
                self._opts[i].set_layer(100)
        elif self._game == 3:
            self._set_label(_('Recall which image was not shown.'))
            # Show the possible solutions
            for i in range(3):
                n = int(uniform(0, len(self._CPATHS)))
                while(not self._image_in_dots(n) or \
                      self._image_in_opts(n)):
                    n = int(uniform(0, len(self._CPATHS)))
                self._opts[i].type = n
            self._answer = int(uniform(0, 3))
            n = int(uniform(0, len(self._CPATHS)))
            while(self._image_in_dots(n)):
                n = int(uniform(0, len(self._CPATHS)))
            self._opts[self._answer].type = n
            for i in range(3):
                self._opts[i].set_shape(self._new_dot_surface(
                        color_image=self._opts[i].type))
                self._opts[i].set_layer(100)
        elif self._game == 2:
            self._set_label(ngettext(
                    'Recall which image was displayed %d time ago',
                    'Recall which image was displayed %d times ago',
                    (int(self._level / 3))) % \
                                (int(self._level / 3)))
            # Show the possible solutions
            for i in range(3):
                self._answer = len(self._recall_list) - int(self._level / 3) - 1
                n = int(uniform(0, len(self._recall_list)))
                while n == self._answer:
                    n = int(uniform(0, len(self._recall_list)))
                self._opts[i].type = n
            i = int(uniform(0, 3))
            self._opts[i].type = self._recall_list[self._answer]
            for i in range(3):
                self._opts[i].set_shape(self._new_dot_surface(
                        image=self._opts[i].type))
                self._opts[i].set_layer(100)

    def restore_game(self, dot_list, correct=0, level=3, game=0):
        ''' Restore a game from the Journal or share '''
        # TODO: Save/restore recall list for game 2
        self._correct = correct
        self._level = level
        self._game = game
        for i, dot in enumerate(dot_list):
            self._dots[i].type = dot
            if dot == -1:
                self._dots[i].hide()
        self._new_game(restore=True)

    def save_game(self):
        ''' Return dot list for saving to Journal or sharing '''
        dot_list = []
        for dot in self._dots:
            dot_list.append(dot.type)
        return dot_list, self._correct, self._level, self._game

    def _set_label(self, string):
        ''' Set the label in the toolbar or the window frame. '''
        self._parent.status.set_label(string)

    def _button_press_cb(self, win, event):
        if self._timeout_id is not None:
            _logger.debug('still in timeout... ignoring click')
            return

        win.grab_focus()
        x, y = map(int, event.get_coords())

        spr = self._sprites.find_sprite((x, y), inverse=True)
        if spr == None:
            return

        if self._game in [0, 1, 3]:
            for i in range(3):
                if self._opts[i] == spr:
                    break
            self._opts[i].set_shape(self._new_dot_surface(
                    color=self._colors[0]))
            if i == self._answer:
                self._opts[i].set_label('☻')
                self._correct += 1
            else:
                self._opts[i].set_label('☹')
                self._correct = 0
        else:
            for i in range(3):
                if self._opts[i] == spr:
                    break
            self._opts[i].set_shape(self._new_dot_surface(
                    color=self._colors[0]))
            if self._opts[i].type == self._recall_list[self._answer]:
                self._opts[i].set_label('☻')
                self._correct += 1
            else:
                self._opts[i].set_label('☹')
                self._correct = 0

        if self._game in [0, 1, 3]:
            for i in range(self._level):
                self._dots[i].set_layer(100)
        else:
            for dot in self._dots:
                dot.set_shape(self._new_dot_surface(
                        image=self._recall_list[self._answer]))
                dot.set_layer(100)

        if self._correct == 0:
            self._timeout_id = GObject.timeout_add(5000, self.new_game)
        else:
            self._timeout_id = GObject.timeout_add(3000, self.new_game)
        return True

    def remote_button_press(self, dot, color):
        ''' Receive a button press from a sharer '''
        self._dots[dot].type = color
        self._dots[dot].set_shape(self._new_dot_surface(
                color=self._colors[color]))

    def set_sharing(self, share=True):
        _logger.debug('enabling sharing')
        self.we_are_sharing = share

    def _draw_cb(self, win, context):
        self.do_draw(win, context)

    def do_draw(self, win, cr):
        ''' Handle the draw-event by drawing '''
        # Restrict Cairo to the exposed area
        alloc = win.get_allocation()
        cr.rectangle(0, 0, alloc.width, alloc.height)
        cr.set_source_rgb(1, 1, 1)
        cr.fill()

        cr.rectangle(0, 0, alloc.width, alloc.height)
        cr.clip()
        # Refresh sprite list
        self._sprites.redraw_sprites(cr=cr)

    def _destroy_cb(self, win, event):
        Gtk.main_quit()

    def _new_dot_surface(self, color='#000000', image=None, color_image=None):
        ''' generate a dot of a color color '''
        self._dot_cache = {}
        if color_image is not None:
            if color_image + 10000 in self._dot_cache:
                return self._dot_cache[color_image + 10000]
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(
                os.path.join(self._path, self._CPATHS[color_image]),
                self._svg_width, self._svg_height)
        elif image is not None:
            if image in self._dot_cache:
                return self._dot_cache[image]
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(
                os.path.join(self._path, self._PATHS[image]),
                self._svg_width, self._svg_height)
        else:
            if color in self._dot_cache:
                return self._dot_cache[color]
            self._stroke = color
            self._fill = color
            self._svg_width = self._dot_size
            self._svg_height = self._dot_size

            i = self._colors.index(color)
            pixbuf = svg_str_to_pixbuf(
                self._header() + \
                    self._circle(self._dot_size / 2., self._dot_size / 2.,
                                 self._dot_size / 2.) + \
                    self._footer())
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32,
                                     self._svg_width, self._svg_height)
        context = cairo.Context(surface)
        Gdk.cairo_set_source_pixbuf(context, pixbuf, 0, 0)
        context.rectangle(0, 0, self._svg_width, self._svg_height)
        context.fill()
        if color_image is not None:
            self._dot_cache[color_image + 10000] = surface
        elif image is not None:
            self._dot_cache[image] = surface
        else:
            self._dot_cache[color] = surface
        return surface

    def _line(self, vertical=True):
        ''' Generate a center line '''
        if vertical:
            self._svg_width = 3
            self._svg_height = self._height
            return svg_str_to_pixbuf(
                self._header() + \
                self._rect(3, self._height, 0, 0) + \
                self._footer())
        else:
            self._svg_width = self._width
            self._svg_height = 3
            return svg_str_to_pixbuf(
                self._header() + \
                self._rect(self._width, 3, 0, 0) + \
                self._footer())

    def _header(self):
        return '<svg\n' + 'xmlns:svg="http://www.w3.org/2000/svg"\n' + \
            'xmlns="http://www.w3.org/2000/svg"\n' + \
            'xmlns:xlink="http://www.w3.org/1999/xlink"\n' + \
            'version="1.1"\n' + 'width="' + str(self._svg_width) + '"\n' + \
            'height="' + str(self._svg_height) + '">\n'

    def _rect(self, w, h, x, y):
        svg_string = '       <rect\n'
        svg_string += '          width="%f"\n' % (w)
        svg_string += '          height="%f"\n' % (h)
        svg_string += '          rx="%f"\n' % (0)
        svg_string += '          ry="%f"\n' % (0)
        svg_string += '          x="%f"\n' % (x)
        svg_string += '          y="%f"\n' % (y)
        svg_string += 'style="fill:#000000;stroke:#000000;"/>\n'
        return svg_string

    def _circle(self, r, cx, cy):
        return '<circle style="fill:' + str(self._fill) + ';stroke:' + \
            str(self._stroke) + ';" r="' + str(r - 0.5) + '" cx="' + \
            str(cx) + '" cy="' + str(cy) + '" />\n'

    def _footer(self):
        return '</svg>\n'


def svg_str_to_pixbuf(svg_string):
    """ Load pixbuf from SVG string """
    pl = GdkPixbuf.PixbufLoader.new_with_type('svg')
    pl.write(svg_string)
    pl.close()
    pixbuf = pl.get_pixbuf()
    return pixbuf
