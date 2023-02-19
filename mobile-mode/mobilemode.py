#!/usr/bin/python3
# vim:fileencoding=utf-8:sw=4:et
#
# Mobile mode for mobile phone
#
# Copyright (C) 2015 - 2023 Mozbugbox <mozbugbox@yahoo.com.au>
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
import math
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
    UNKNOWN = 0
    FEED_LIST = 1
    ITEM_LIST = 2
    ITEM = 3


HORI_THESHOLD = math.pi / 9  # 20deg
TAN_HORI = math.tan(HORI_THESHOLD)  # tangent horizontal
TAN_VERT = 1 / TAN_HORI  # tangent for vertical

class MobileModePlugin (GObject.Object,
        Liferea.ShellActivatable, PeasGtk.Configurable):
    __gtype_name__ = "MobileModePlugin"

    shell = GObject.property(type=Liferea.Shell)

    _shell = None

    def __init__(self):
        GObject.Object.__init__(self)
        self.gesture_valid_region = 0.3  # valid region for drag start
        self.gesture_threshold = 10

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

        self.build_compact_menu()
        self.load_actions()

    def do_deactivate(self):
        """Peas Plugin exit point"""
        self.drag_gesture.disconnect(self.drag_end_cid)
        self.drag_end_cid = -1
        self.reset_panes()

        builder = self.shell.get_property("builder")
        status_bar = builder.get_object("statusbar")
        Gtk.Container.remove(status_bar, self.menu_dropdown)
        self.main_win.set_show_menubar(True)

    def build_compact_menu(self):
        """Hide main menubar while create a hamburg button on status bar
        Borrowed from the Header Bar plugin

        """
        # hamburg button
        button = Gtk.MenuButton()
        icon = Gio.ThemedIcon(name="open-menu-symbolic")
        image = Gtk.Image.new_from_gicon(icon, Gtk.IconSize.BUTTON)
        builder = self.shell.get_property("builder")
        button.set_menu_model(builder.get_object("menubar"))
        button.add(image)
        button.show_all()

        self.main_win.set_show_menubar(False)
        status_bar = builder.get_object("statusbar")
        status_bar.pack_end(button, False, False, 0)

        self.menu_dropdown = button

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
        else:
            self.show_feed_list()

    def show_right(self):
        """Show the view to the right of current view"""
        if self.view_mode == ViewMode.FEED_LIST:
            self.show_item_list()
        elif self.view_mode == ViewMode.ITEM_LIST:
            self.show_item()
        else:
            self.show_item_list()

    def reset_panes(self):
        """Reset the panes to a proper default position"""
        pane_width = self.left_pane.get_allocated_width()
        self.left_pane.props.position = pane_width // 3
        pane_height = self.normal_view_pane.get_allocated_height()
        self.normal_view_pane.props.position = pane_height * 2 // 5

    def on_main_win_drag_end(self, gesture, offset_x, offset_y, *udata):
        """Handler for drag-end event."""

        # too close for a drag
        if (abs(offset_x) < self.gesture_threshold and
                abs(offset_y) < self.gesture_threshold):
            return

        res, start_x, start_y = gesture.get_start_point()
        main_height = self.main_win.get_allocated_height()
        # print(main_height, start_y, main_height - start_y, main_height * self.valid_region)
        if (main_height - start_y) > int(main_height * self.gesture_valid_region):
            return

        if offset_x != 0:
            tan = abs(offset_y / offset_x)
        else:
            tan = 57  # 89deg
        if tan > TAN_VERT:  # vertical
            if offset_y < 0:
                # vertical up drag
                if self.view_mode == ViewMode.ITEM:
                    self.do_action("next-unread-item")
                else:
                    pass
        elif tan < TAN_HORI:  # horizontal
            if offset_x > 0:
                self.show_left()
            else:
                self.show_right()
        elif offset_y < 0:  # angle up
            if offset_x < 0:
                self._step_item("up")
            else:
                self._step_item("down")

    @property
    def view_mode(self):
        if self.left_pane.props.position == self.normal_view_pane.props.position == 0:
            mode = ViewMode.ITEM
        elif self.left_pane.props.position == 0:
            mode = ViewMode.ITEM_LIST
        elif self.normal_view_pane == 0:
            mode = ViewMode.FEED_LIST
        else:
            mode = ViewMode.UNKNOWN
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
    def itemlist_treeview(self):
        itemlist_view = self._shell.props.item_view.props.item_list_view
        tview = itemlist_view.get_widget().get_child()
        return tview

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

    def do_action(self, action_name, values=None):
        """
        values: action parameters as a single value: 1, "some text", (1, True)
        """
        win = self._shell.get_window()
        gapp = win.props.application
        for action_map_group in [win, gapp]:
            action = action_map_group.lookup_action(action_name)
            if action is None:
                action = action_map_group.lookup_action(action_name.replace("_", "-"))

            if action is not None:
                break
        if action is None:
            log_error(f"Unknown action {action_name}")
            return
        # log_error("doing", action_name)
        vtype = action.get_parameter_type()
        if (vtype is None) != (values is None):
            log_error(f"Action {action_name} param type don't confirm values")
            return

        param = None
        if vtype:
            param = GLib.Variant(vtype.dup_string(), values)
        action.activate(param)

    def load_actions(self):
        """Setup actions and add default shortcuts"""
        window = self.main_win
        simple_action_names = [
                "mobile_mode_show_feed_list",
                "mobile_mode_show_item_list",
                "mobile_mode_show_item",
                "mobile_mode_show_left",
                "mobile_mode_show_right",
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

    def action_mobile_mode_show_feed_list(self, action, param):
        """action to show feed list in mobile mode"""
        self.show_feed_list()

    def action_mobile_mode_show_item_list(self, action, param):
        """action to show item list in mobile mode"""
        self.show_feed_list()

    def action_mobile_mode_show_item(self, action, param):
        """action to show item in mobile mode"""
        self.show_feed_list()

    def action_mobile_mode_show_left(self, action, param):
        """action to show left view in mobile mode"""
        self.show_left()

    def action_mobile_mode_show_right(self, action, param):
        """action to show right view in mobile mode"""
        self.show_right()

    def _get_next_iter(self, direct="down"):
        tree = self.itemlist_treeview
        model = tree.props.model
        path, col = tree.get_cursor()
        if path is None:
            if direct == "down":
                miter = model.get_iter_first()
            else:
                num_kids = model.iter_n_children(None)
                miter = model.iter_nth_child(None, num_kids - 1)
        else:
            miter = model.get_iter(path)
            if not miter: return
            if direct == "down":
                miter = model.iter_next(miter)
            else:
                miter = model.iter_previous(miter)
        return miter

    def _step_item(self, direct="down"):
        miter = self._get_next_iter(direct)
        if miter:
            tree = self.itemlist_treeview
            model = tree.props.model
            tree.grab_focus()
            path = model.get_path(miter)
            tree.set_cursor(path, None, False)
