#!/usr/bin/python3
# vim:fileencoding=utf-8:sw=4:et
#
# Mobile mode for mobile phone
#
# Copyright (C) 2015 - 2021 Mozbugbox <mozbugbox@yahoo.com.au>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Library General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Library General Public License for more details.
#
# You should have received a copy of the GNU Library General Public License
# along with this library; see the file COPYING.LIB.  If not, write to
# the Free Software Foundation, Inc., 59 Temple Place - Suite 330,
# Boston, MA 02111-1307, USA.
#
"""
A mode for help using Liferea on mobile phone:
    * Single pane mode: Show only one pane at a time
    * swipe from lower screen to change window among feedlist/itemlist/item
"""

"""
Plugin dev help:
  http://lzone.de/Writing-Liferea-Plugins-Tutorial-Part-1
  https://developer.gnome.org/libpeas/1.10/pt01.html
  https://wiki.gnome.org/Apps/Gedit/PythonPluginHowTo
  https://github.com/lwindolf/liferea/tree/master/plugins
"""

import os
import io
import sys
import enum
import gi

gi.require_version('Gtk', '3.0')
gi.require_version('PeasGtk', '1.0')
gi.require_version('WebKit2', '4.0')

from gi.repository import GLib, Gio, GObject, Gtk, Gdk, PeasGtk
from gi.repository import Liferea, WebKit2, Soup

UI_FILE_PATH = os.path.join(os.path.dirname(__file__), "mobilemode.ui")

def liferea_symbols():
    """Print out symbols exported by `Liferea` module"""
    gobj_attrs = set(dir(GObject.Object))
    def _print_it(obj):
        klasses = []
        if hasattr(obj, "__name__"):
            print(obj.__name__ + ":")
        else:
            print("obj" + ":")
        for k in dir(obj):
            # ignore noise
            if k.startswith("__"): continue
            if k in gobj_attrs and k != "props": continue

            ko = getattr(obj, k)
            func_tag = "()" if callable(ko) else ""
            print("  " + k + func_tag)
            if k == "props" and dir(ko):
                print("    " + str(dir(ko)))

            # accumulate class item
            if isinstance(ko, type) and not k.endswith(("Class", "Private",
                    "Interface", "Ptr")):
                klasses.append(ko)
        return klasses

    ks = _print_it(Liferea)
    #print(ks) # print class attributes
    for v in ks:
        _print_it(v)
    sys.stdout.flush()
#liferea_symbols() # uncomment to print out export symbols

def get_widget_by_name(root, name):
    """Return a widget by name"""
    children_list = []
    widget_list = root.get_children()
    children_list.append(widget_list)
    while len(children_list) > 0:
        widget_list = children_list.pop(0)
        for widget in widget_list:
            wname = widget.props.name
            if not wname:
                wname = Gtk.Buildable.get_name(widget)
            if wname == name:
                return widget
            elif isinstance(widget, Gtk.Container):
                sub_widget_list = widget.get_children()
                children_list.append(sub_widget_list)

def log_error(*args, **kwargs):
    """Print to stderr"""
    print(*args, file=sys.stderr, **kwargs)

def on_idle(func):
    """Decorator to run func on GObject.idle_add """
    def _idle_run(*args):
        GObject.idle_add(func, *args)
    return _idle_run

def add_once(func, *args):
    """run the timeout_add/idle_add func once"""
    func(*args)
    return False

def marshall_variant(variant_type, val):
    """Marshall a python val to GLib.Variant"""
    if isinstance(val, GLib.Variant):
        return val
    if variant_type and variant_type.is_basic():
        val = GLib.Variant(variant_type.dup_string(), val)
    return val

def add_action_entries(gaction_map, entries, *user_data):
    """Add action entries to GActionMap,
    GActionMap's are Gtk.Application, Gtk.ApplicationWindow"""
    def _process_action(name, activate=None, parameter_type=None,
            state=None, change_state=None):
        if state is None:
            action = Gio.SimpleAction.new(name, parameter_type)
        else:
            state = marshall_variant(parameter_type, state)
            action = Gio.SimpleAction.new_stateful(name,
                    parameter_type, state)
        if activate is not None:
            action.connect('activate', activate, *user_data)
        elif change_state is not None:
            action.connect('change-state', change_state, *user_data)
        else:
            log_error(f'No method connected to action "{name}"')

        gaction_map.add_action(action)
    for e in entries:
        try:
            _process_action(*e)
        except Exception as e:
            log_error(e)

class ViewMode(enum.Enum):
    FEED_LIST = 1
    ITEM_LIST = 2
    ITEM = 3

class MobileModePlugin (GObject.Object,
        Liferea.ShellActivatable, PeasGtk.Configurable):
    __gtype_name__ = "MobileModePlugin"

    shell = GObject.property(type=Liferea.Shell)

    _shell = None

    def __init__(self):
        GObject.Object.__init__(self)
        self.valid_region = 0.3  # valid region for drag start

    def do_activate(self):
        """Override Peas Plugin entry point"""
        if self._shell is None:
            MobileModePlugin._shell = self.props.shell
        left_pane = get_widget_by_name(self.main_win, "leftpane")
        normal_view_pane = get_widget_by_name(self.main_win, "normalViewPane")

        self.left_pane = left_pane
        self.normal_view_pane = normal_view_pane

        self.drag_gesture = Gtk.GestureDrag.new(self.main_win)
        self.drag_gesture.props.propagation_phase = Gtk.PropagationPhase.CAPTURE
        self.drag_end_cid = self.drag_gesture.connect("drag-end", self.on_main_win_drag_end)

        self.load_actions()

    def show_feed_list(self):
        """Show the feedlist widget"""
        pane_width = self.left_pane.get_allocated_width()
        if self.left_pane.props.position != pane_width:
            self.left_pane.props.position = pane_width

    def show_item_list(self):
        """Show the itemlist widget"""
        if self.left_pane.props.position != 0:
            self.left_pane.props.position = 0

        pane_height = self.normal_view_pane.get_allocated_height()
        if self.normal_view_pane.props.position != pane_height:
            self.normal_view_pane.props.position = pane_height

    def show_item(self):
        """Show the item view widget"""
        if self.left_pane.props.position != 0:
            self.left_pane.props.position = 0

        if self.normal_view_pane.props.position != 0:
            self.normal_view_pane.props.position = 0

    def show_left(self):
        """Show the view to the left of current view"""
        if self.view_mode == ViewMode.ITEM:
            self.show_item_list()
        elif self.view_mode == ViewMode.ITEM_LIST:
            self.show_feed_list()

    def show_right(self):
        """Show the view to the right of current view"""
        if self.view_mode == ViewMode.FEED_LIST:
            self.show_item_list()
        elif self.view_mode == ViewMode.ITEM_LIST:
            self.show_item()

    def reset_panes(self):
        """Reset the panes to a proper default position"""
        pane_width = self.left_pane.get_allocated_width()
        self.left_pane.props.position = pane_width // 3
        pane_height = self.normal_view_pane.get_allocated_height()
        self.normal_view_pane.props.position = pane_height * 2 // 5

    def on_main_win_drag_end(self, gesture, offset_x, offset_y, *udata):
        """Handler for drag-end event."""
        res, start_x, start_y = gesture.get_start_point()
        main_height = self.main_win.get_allocated_height()
        # print(main_height, start_y, main_height - start_y, main_height * self.valid_region)
        if (main_height - start_y) > int(main_height * self.valid_region):
            return

        if abs(offset_x) < abs(offset_y):
            # vertical drag
            if offset_y < 0:  # up
                pass
            else:
                pass
        elif offset_x > 0:
            self.show_right()
        else:
            self.show_left()

    def do_deactivate(self):
        """Peas Plugin exit point"""
        self.drag_gesture.disconnect(self.drag_end_cid)
        self.drag_end_cid = -1
        self.reset_panes()

    @property
    def view_mode(self):
        mode = ViewMode.FEED_LIST
        if self.left_pane.props.position == self.normal_view_pane.props.position == 0:
            mode = ViewMode.ITEM
        elif self.left_pane.props.position == 0:
            mode = ViewMode.ITEM_LIST
        elif self.normal_view_pane == 0:
            mode = ViewMode.FEED_LIST
        return mode

    @property
    def main_win(self):
        window = self._shell.get_window()
        return window

    @property
    def gapp(self):
        app = self.main_win.get_application()
        return app

    @property
    def main_webkit_view(self):
        """Return the webkit webview in the item_view"""
        shell = self._shell
        item_view = shell.props.item_view
        if not item_view:
            print("Item view not found!")
            return None

        htmlv = item_view.props.html_view
        if not htmlv:
            print("HTML view not found!")
            return None

        return htmlv.props.renderwidget

    @property
    def current_webviews(self):
        """Get all the available webviews """
        views = []
        webkit_view = self.main_webkit_view
        if webkit_view is None:
            return views
        views.append(webkit_view)

        browser_tabs = self._shell.props.browser_tabs
        tab_infos = browser_tabs.props.tab_info_list
        if tab_infos:
            box_in_tabs = [x.htmlview for x in tab_infos]
            html_in_tabs = [x.get_widget() for x in box_in_tabs]
            views.extend(html_in_tabs)
        return views

    def load_actions(self):
        """Setup actions and add default shortcuts"""
        window = self.main_win
        simple_action_names = [
                "mobile_modes_show_feed_list",
                "mobile_modes_show_item_list",
                "mobile_modes_show_item",
        ]

        accel_maps = [
                # ["win.webkit_page_up", ["BackSpace"]],
        ]

        # action name cannot have "-" in it.
        # action callbacks prefixed with "action_"
        action_entries = [[x.replace("_", "-"),
            getattr(self, "action_" + x, None)] for x in simple_action_names]

        add_action_entries(window, action_entries)
        for act, accels in accel_maps:
            try:
                act = act.replace("_", "-")
                self.gapp.set_accels_for_action(act, accels)
            except Exception as e:
                log_error(e)

    def action_mobile_modes_show_feed_list(self, action, param):
        """action to show feed list in mobile mode"""
        self.show_feed_list()

    def action_mobile_modes_show_item_list(self, action, param):
        """action to show item list in mobile mode"""
        self.show_feed_list()

    def action_mobile_modes_show_item(self, action, param):
        """action to show item in mobile mode"""
        self.show_feed_list()
