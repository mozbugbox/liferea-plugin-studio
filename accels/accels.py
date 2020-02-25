#!/usr/bin/python3
# vim:fileencoding=utf-8:sw=4:et
#
# Extra Accels Plugin
#
# Copyright (C) 2014-2018 Mozbugbox <mozbugbox@yahoo.com.au>
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
Change accels/shortcuts:

    Dump a list of available action from the plugin preference dialog.
    Edit the dumped action list and restart Liferea to enable the shortcuts

"""

import io
import pathlib
from gi.repository import GObject, Gtk, Gdk, PeasGtk, Liferea

"""
Plugin dev help:
  http://lzone.de/Writing-Liferea-Plugins-Tutorial-Part-1
  https://developer.gnome.org/libpeas/1.10/pt01.html
  https://wiki.gnome.org/Apps/Gedit/PythonPluginHowTo
  https://github.com/lwindolf/liferea/tree/master/plugins
"""

def liferea_symbols():
    """Print out symbols exported by `Liferea` module"""
    gobj_attrs = set(dir(GObject.Object))
    def _print_it(obj):
        klasses = []
        if hasattr(obj, "__name__"):
            print(obj.__name__ + ":")
        else:
            print(str(obj) + ":")
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
    # print(ks) # print class attributes
    for v in ks:
        _print_it(v)
    import sys
    sys.stdout.flush()
# liferea_symbols() # uncomment to print out export symbols

def get_accel_path(data_dir=None):
    """return path for the accels data file"""
    if data_dir is None:
        mypath = pathlib.Path(__file__)
        data_dir = mypath.parent / "data"
        data_dir.mkdir(0o700, True, True)
    else:
        data_dir = pathlib.Path(data_dir)
    accel_path = data_dir / "accels.txt"
    return accel_path

class AccelsPlugin (GObject.Object, Liferea.ShellActivatable):
    __gtype_name__ = 'AccelsPlugin'

    object = GObject.property(type=GObject.Object)
    shell = GObject.property(type=Liferea.Shell)

    @property
    def item_list(self):
        """Return TreeView for item list"""
        for view_name in ["wideViewItems", "normalViewItems"]:
            item_viewport = self.shell.lookup(view_name)
            if item_viewport.get_mapped():
                break
        scrolled_window = item_viewport.get_child()
        item_list = scrolled_window.get_child()
        return item_list

    def do_activate(self):
        # print(self.plugin_info)
        accels = self.load_accels()
        GObject.idle_add(self.set_accels, accels)
        accelsConfigure.plugin = self

    def set_accels(self, accels):
        # print(f"accels: {accels}")
        shell = Liferea.Shell
        mainwin = shell.get_window()
        app = mainwin.props.application
        single_key = False
        for item in accels:
            app.set_accels_for_action(item[0], item[1])
            if not single_key and [len(x) for x in item[1]].count(1) > 0:
                single_key = True

        if single_key:
            # turn off "search_enable" which start search by single key
            feed_list = shell.lookup("feedlist")
            feed_list.props.enable_search = False
            self.item_list.props.enable_search = False

    def do_deactivate(self):
        pass

    def load_accels(self):
        """Load accelaration data from data file"""
        accels = []
        accel_path = get_accel_path(self.plugin_info.get_data_dir())
        if not accel_path.exists():
            return

        import json
        with io.open(accel_path) as fh:
            for line in fh:
                if line.startswith("#") or line.isspace(): continue
                try:
                    item = json.loads(line)
                    accels.append(item)
                except json.decoder.JSONDecodeError:
                    print(f"accels: Failed to parse: {line}")
        return accels

class accelsConfigure(GObject.Object, PeasGtk.Configurable):
    __gtype_name__ = 'accelsConfigure'
    def do_create_configure_widget(self):
        """Setup configuration widget"""
        # print(self.plugin_info)
        grid = Gtk.Grid()
        grid_top = 0

        label = Gtk.Label("Path:")
        label.props.tooltip_text= "Config file path"
        label.props.xalign = 0
        label.props.margin = 6
        label.props.expand = False
        grid.attach(label, 0, grid_top, 1, 1)

        label = Gtk.Label()
        label.props.xalign = 0
        label.props.margin = 6
        label.props.expand = False
        label.props.selectable = True
        label.props.label = f"{self.accel_path}"
        grid.attach(label, 1, 0, 2, 1)
        grid_top += 1

        tooltip = "Press a key to find out its keyname for acceleration"
        entry = Gtk.Entry()
        entry.props.width_chars = 24
        entry.props.tooltip_text = tooltip
        entry.connect("key-press-event", self.on_show_keyname_keypress_event)
        grid.attach(entry, 1, grid_top, 1, 1)

        label = Gtk.Label("_Keyname:")
        label.props.tooltip_text = tooltip
        label.props.xalign = 0
        label.props.margin = 6
        label.props.expand = False
        label.props.use_underline = True
        label.props.mnemonic_widget = entry
        grid.attach(label, 0, grid_top, 1, 1)
        grid_top += 1

        button_dump = Gtk.Button("_Dump Accels")
        button_dump.props.tooltip_text = "Dump all the Liferea actions along with accelerations to the config file."
        button_dump.props.use_underline = True
        button_dump.props.expand = False
        button_dump.props.halign = Gtk.Align.START
        button_dump.props.margin = 6
        button_dump.connect("clicked", self._on_dump_button_clicked)
        grid.attach(button_dump, 1, grid_top, 1, 1)
        grid_top += 1

        button_reload = Gtk.Button("_Reload Accels")
        button_reload.props.tooltip_text = "Reload the action config file."
        button_reload.props.use_underline = True
        button_reload.props.expand = False
        button_reload.props.halign = Gtk.Align.START
        button_reload.props.margin = 6
        button_reload.connect("clicked", self._on_reload_button_clicked)
        grid.attach(button_reload, 1, grid_top, 1, 1)
        grid_top += 1

        grid.show_all()
        return grid

    def on_show_keyname_keypress_event(self, entry, evt, *args):
        entry.set_text(Gdk.keyval_name(evt.keyval))
        return True

    def get_actions(self):
        """collect actions for the GtkApplication"""
        shell = Liferea.Shell
        mainwin = shell.get_window()
        app = mainwin.props.application
        app_actions = app.list_actions()
        win_actions = mainwin.list_actions()
        app_actions.sort()
        win_actions.sort()
        # print(app_actions, win_actions)

        action_desc = app.list_action_descriptions()
        # print(action_desc)
        result = []
        def do_aname(aname):
            accels = []
            if aname in action_desc:
                accels = app.get_accels_for_action(aname)
            item = [aname, accels]
            result.append(item)

        for a in app_actions:
            name = f"app.{a}"
            do_aname(name)

        for a in win_actions:
            name = f"win.{a}"
            do_aname(name)

        return result

    @property
    def accel_path(self):
        return get_accel_path(self.plugin_info.get_data_dir())

    def _on_dump_button_clicked(self, wid):
        actions = self.get_actions()

        accel_path = self.accel_path
        if accel_path.exists():
            mtime = accel_path.stat().st_mtime
            import time
            timestamp = time.strftime("%Y%m%d%H%M%S", time.localtime(mtime))
            accel_path.rename(f"{accel_path}.{timestamp}")

        header = """\
# Generated by Accels Plugin.
#
# * Remove the "#" at the beginning of the line.
# * Add shortcuts to the actions.
# * Multiple shortcuts can be bind to the same action.
# * Restart or reload actions
# * Check command line for shortcut syntax errors
#
"""
        import json
        with io.open(accel_path, "w") as fh:
            fh.write(header)
            for item in actions:
                d = json.dumps(item)
                leader = "# " if len(item[1]) == 0 else ""
                fh.write(f"{leader}{d}\n")

        dlg = Gtk.MessageDialog(wid.get_toplevel(),
                Gtk.DialogFlags.DESTROY_WITH_PARENT,
                Gtk.MessageType.INFO, Gtk.ButtonsType.CLOSE,
                f"""Acceleration data were written to "{accel_path}".

Please edit the file and restart Liferea.""")
        dlg.props.title = "Accels created"
        dlg.run()
        dlg.destroy()

    def _on_reload_button_clicked(self, wid):
        accels = self.plugin.load_accels()
        self.plugin.set_accels(accels)

