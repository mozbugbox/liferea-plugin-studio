#!/usr/bin/python3
# vim:fileencoding=utf-8:sw=4:et
#
# Show item status as text too
#
# Copyright (C) 2014-2023 Mozbugbox <mozbugbox@yahoo.com.au>
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
Show item read/flagged state as text too
"""

import logging
import enum

import gi

gi.require_version('Gtk', '3.0')
gi.require_version('PeasGtk', '1.0')

from gi.repository import GObject, Gtk, Gdk, Gio, GLib
from gi.repository import PeasGtk, Liferea

"""
Plugin dev help:
  http://lzone.de/Writing-Liferea-Plugins-Tutorial-Part-1
  https://developer.gnome.org/libpeas/1.10/pt01.html
  https://wiki.gnome.org/Apps/Gedit/PythonPluginHowTo
  https://github.com/lwindolf/liferea/tree/master/plugins
"""

# https://github.com/lwindolf/liferea/blob/master/src/ui/item_list_view.c#L64
# ListView liststore columns
class is_columns(enum.IntEnum):
    IS_TIME = 0                     # Time of item creation
    IS_TIME_STR = enum.auto()       # Time of item creation as a string
    IS_LABEL = enum.auto()          # Displayed name
    IS_STATEICON = enum.auto()      # Pixbuf reference to the item's state icon
    IS_NR = enum.auto()             # Item id, to lookup item ptr from parent feed
    IS_PARENT = enum.auto()         # Parent node pointer
    IS_FAVICON = enum.auto()        # Pixbuf reference to the item's feed's icon
    IS_SOURCE = enum.auto()         # Source node pointer
    IS_STATE = enum.auto()          # Original item state (unread, flagged...) for sorting
    ITEMSTORE_WEIGHT = enum.auto()  # Flag whether weight is to be bold and "unread" icon is to be shown
    ITEMSTORE_ALIGN = enum.auto()   # How to align title (RTL support)
    ITEMSTORE_LEN = enum.auto()     # Number of columns in the itemstore

IS_STATE_TEXT = 11

DEBUG = True

def state2text(state):
    """Convert item state to text"""
    msg_list = []
    # flag += 2, unread += 1
    if state in [1, 3]:
        msg_list.append("unread")
    else:
        msg_list.append("read")

    if state in [2, 3]:
        msg_list.append("flagged")
    msg = msg_list[-1]
    return msg

class TextItemStatePlugin (GObject.Object,
        Liferea.ShellActivatable, PeasGtk.Configurable):
    __gtype_name__ = "TextItemStatePlugin"

    shell = GObject.property(type=Liferea.Shell)
    _shell = None

    def __init__(self):
        GObject.Object.__init__(self)
        self.state_column = None
        self.cid_model = -1
        self.connection_ids = []

    def do_activate(self):
        """Override Peas Plugin entry point"""
        if DEBUG:
            setup_log(logging.DEBUG)
        else:
            setup_log()

        if self._shell is None:
            TextItemStatePlugin._shell = self.props.shell

        self.setup_itemlist_tree()
        self.setup_itemlist_model()
        cid = self.itemlist_treeview.connect("notify::model", self.on_itemlist_model_changed)
        self.cid_model = cid

        self.load_actions()

    def do_deactivate(self):
        """Peas Plugin exit point"""
        if self.cid_model > 0:
            self.itemlist_treeview.disconnect(self.cid_model)
            self.cid_model = -1

        state_column = self.get_state_column(self.itemlist_treeview)
        if not state_column:
            return

        for cell in state_column.get_cells():
            if isinstance(cell, Gtk.CellRendererPixbuf):
                cell.props.visible = True
            if isinstance(cell, Gtk.CellRendererText):
                state_column.props.cell_area.remove(cell)

    def do_action(self, action_name, param):
        win = self._shell.get_window()
        gapp = win.props.application
        for action_map in [win, gapp]:
            action = action_map.lookup_action(action_name)
            if action is not None:
                break
        if action is None:
            log.error(f"Unknown action: {action_name=}")
            return
        log.debug(f"doing {action_name=}")

        action.activate(param)

    def on_itemlist_model_changed(self, tree, gparamstring):
        if gparamstring.name == "model" and not tree.props.model:
            return
        self.setup_itemlist_model()

    def get_state_column(self, tree):
        """Find the state column in itemlist tree"""
        state_column = None
        for column in tree.get_columns():
            for cell in column.get_cells():
                if isinstance(cell, Gtk.CellRendererPixbuf):
                    cell_area = column.props.cell_area
                    gicon_col = cell_area.attribute_get_column(cell, "gicon")
                    if gicon_col == is_columns.IS_STATEICON:
                        state_column = column
                        break
            if state_column is not None:
                break
        return state_column

    def setup_itemlist_tree(self):
        """Add a text renderer to the state column"""
        tree = self.itemlist_treeview
        if not tree:
            return

        state_column = self.get_state_column(tree)
        if not state_column:
            return
        self.state_column = state_column
        cells = state_column.get_cells()
        if len(cells) < 2:
            renderer = Gtk.CellRendererText()
            state_column.pack_end(renderer, False)
            state_column.add_attribute(renderer, "text", IS_STATE_TEXT)

            for cell in cells:
                if isinstance(cell, Gtk.CellRendererPixbuf):
                    cell.props.visible = False

    def setup_itemlist_model(self):
        """Extend itemlist store with a IS_STATE_TEXT column"""
        tree = self.itemlist_treeview
        if not tree:
            return
        model = tree.get_model()
        if not model:
            return
        new_model = None
        if model.get_n_columns() > is_columns.ITEMSTORE_LEN:
            return

        column_types = [GObject.TYPE_INT64, str, str, Gio.Icon, GObject.TYPE_ULONG,
                        GObject.TYPE_POINTER, Gio.Icon, GObject.TYPE_POINTER,
                        GObject.TYPE_UINT, int, float]
        column_types.append(str)
        new_model = Gtk.TreeStore(*column_types)

        # need to copy from old model since the old model might already
        # filled as batch_itemstore before tree.set_model
        for row in model:
            state = model[row.iter][is_columns.IS_STATE]
            state_text = state2text(state)

            if new_model is None:
                row[IS_STATE_TEXT] = state_text
            else:
                data = list(row) + [state_text]

                # FIXME: pygobject GType_POINTER don't take GPointer, only took integer
                # what's the API to take the address from a GPointer?
                data[5] = int(str(data[5]).partition("x")[2].strip(">"), 16)
                data[7] = int(str(data[7]).partition("x")[2].strip(">"), 16)
                try:
                    new_model.append(None, data)
                except TypeError:
                    log.exception(f"{data}")
                    return

        new_model.connect("row-changed", self.on_model_row_changed)
        new_model.connect("row-inserted", self.on_model_row_inserted)
        tree.set_model(new_model)

    def update_row_state_text(self, model, miter):
        """Set state text according to the item state"""
        state = model[miter][is_columns.IS_STATE]
        state_text = model[miter][IS_STATE_TEXT]

        new_state_text = state2text(state)
        if state_text != new_state_text:
            model[miter][IS_STATE_TEXT] = new_state_text

    def on_model_row_changed(self, model, path, miter):
        self.update_row_state_text(model, miter)

    def on_model_row_inserted(self, model, path, miter):
        # row still empty?
        self.update_row_state_text(model, miter)

    def temp_status_msg(self, msg, timeout_s=3):
        """Show msg on status bar and remove it on timeout"""
        TEMP_STATUS_CONTEXT = "temp_msg"
        statusbar = self._shell.lookup("statusbar")
        cid = statusbar.get_context_id(TEMP_STATUS_CONTEXT)
        mid = statusbar.push(cid, msg)
        GLib.timeout_add_seconds(timeout_s, lambda: statusbar.remove(cid, mid))

    def load_actions(self):
        """Setup actions and add default shortcuts"""
        window = self.shell.get_window()
        simple_action_names = [
                ]

        accel_maps = [
                # ["win.webkit_page_up", ["BackSpace"]],
            ]

        # action name cannot have "_" in it.
        # action callbacks prefixed with "action_"
        action_entries = [[x.replace("_", "-"),
            getattr(self, "action_" + x, None)] for x in simple_action_names]
        action_entries += [
        ]

        TextItemStatePlugin.action_list = [x[0] for x in action_entries]
        window.add_action_entries(action_entries)
        for act, accels in accel_maps:
            try:
                act = act.replace("_", "-")
                self.gapp.set_accels_for_action(act, accels)
            except Exception as e:
                log.error(e)

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
        if not self._shell.props.item_view:
            return
        itemlist_view = self._shell.props.item_view.props.item_list_view
        tview = itemlist_view.get_widget().get_child()
        return tview

    @property
    def feedlist_treeview(self):
        tview = self._shell.lookup("feedlist")
        return tview

def setup_log(log_level=None):
    global log
    rlog = logging.getLogger()

    ch = logging.StreamHandler()
    formatter = logging.Formatter("%(levelname)s:%(module)s:%(lineno)d:: %(message)s")
    ch.setFormatter(formatter)
    if __name__ == "__main__" and not rlog.hasHandlers():
        # setup root logger
        rlog.addHandler(ch)

    log = logging.getLogger(__name__)
    if not log.hasHandlers():
        log.addHandler(ch)

    if log_level is not None:
        log.setLevel(log_level)
        #rlog.setLevel(log_level)

