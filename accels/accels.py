#!/usr/bin/python3
# vim:fileencoding=utf-8:sw=4:et
#
# Extra Accels Plugin
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
        if not accels:
            return
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
    Group_Names = ['Item', 'Feed', 'WebKit', 'New', 'Link', 'Misc', 'Help']
    def do_create_configure_widget(self):
        """Setup configuration widget"""
        margin = 6

        grid = Gtk.Grid()
        grid.props.expand = False
        grid_top = 0

        label = Gtk.Label("Path:")
        label.props.tooltip_text = "Config file path"
        label.props.xalign = 0
        label.props.margin = margin
        label.props.expand = False
        grid.attach(label, 0, grid_top, 1, 1)

        label = Gtk.Label()
        label.props.xalign = 0
        label.props.margin = margin
        label.props.expand = False
        label.props.selectable = True
        label.props.label = f"{self.accel_path}"
        grid.attach(label, 1, 0, 2, 1)
        grid_top += 1

        tooltip = "Press a key to find out its keyname for acceleration"
        entry = Gtk.Entry()
        entry.props.max_width_chars = 32
        entry.props.expand = False
        entry.props.tooltip_text = tooltip
        entry.props.overwrite_mode = True
        entry.connect("key-press-event",
                EditShortCutDialog.on_show_keyname_keypress_event)
        grid.attach(entry, 1, grid_top, 2, 1)

        label = Gtk.Label("_Keyname:")
        label.props.tooltip_text = tooltip
        label.props.xalign = 0
        label.props.margin = margin
        label.props.expand = False
        label.props.use_underline = True
        label.props.mnemonic_widget = entry
        grid.attach(label, 0, grid_top, 1, 1)
        grid_top += 1

        button_edit_accels = Gtk.Button("_Edit Accels")
        button_edit_accels.props.tooltip_text = "Edit accelerations."
        button_edit_accels.props.use_underline = True
        button_edit_accels.props.expand = False
        button_edit_accels.props.halign = Gtk.Align.START
        button_edit_accels.props.margin = margin
        button_edit_accels.connect("clicked",
                self._on_edit_accels_button_clicked)
        grid.attach(button_edit_accels, 1, grid_top, 1, 1)

        button_show_accels = Gtk.Button("_Show Accels")
        button_show_accels.props.tooltip_text = "Show current accelerations."
        button_show_accels.props.use_underline = True
        button_show_accels.props.expand = False
        button_show_accels.props.halign = Gtk.Align.START
        button_show_accels.props.margin = margin
        button_show_accels.connect("clicked",
                self._on_show_accels_button_clicked)
        grid.attach(button_show_accels, 2, grid_top, 1, 1)
        grid_top += 1

        button_dump = Gtk.Button("_Dump Accels")
        button_dump.props.tooltip_text = "Dump all the Liferea actions along with accelerations to the config file."
        button_dump.props.use_underline = True
        button_dump.props.expand = False
        button_dump.props.halign = Gtk.Align.START
        button_dump.props.margin = margin
        button_dump.connect("clicked", self._on_dump_button_clicked)
        grid.attach(button_dump, 1, grid_top, 1, 1)
        grid_top += 1

        button_reload = Gtk.Button("_Reload Accels")
        button_reload.props.tooltip_text = "Reload the action config file."
        button_reload.props.use_underline = True
        button_reload.props.expand = False
        button_reload.props.halign = Gtk.Align.START
        button_reload.props.margin = margin
        button_reload.connect("clicked", self._on_reload_button_clicked)
        grid.attach(button_reload, 1, grid_top, 1, 1)
        grid_top += 1

        grid.show_all()
        return grid

    def get_actions(self):
        """collect actions for the GtkApplication
        @return: a list of [[action-name, [keynames,...]], ...]
        """
        shell = Liferea.Shell
        mainwin = shell.get_window()
        app = mainwin.props.application
        app_actions = app.list_actions()
        win_actions = mainwin.list_actions()
        app_actions.sort()
        win_actions.sort()
        # print(app_actions, win_actions)

        # action_desc = app.list_action_descriptions()
        # print(action_desc)
        result = []
        def do_aname(aname):
            accels = []
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

    def group_actions(self, action_list=None):
        import itertools
        if action_list is None:
            action_list = self.get_actions()

        def action_keys(action_name):
            scope, s, name = action_name[0].partition(".")
            if name.startswith("new"):
                return "New"
            elif name.startswith("update"):
                return "Feed"
            elif "about" in name:
                return "Help"
            for gname in self.Group_Names:
                if gname.lower() in name:
                    return gname
            return "Misc"

        action_list.sort(key=action_keys)
        items = itertools.groupby(action_list, action_keys)
        return items


    def _on_dump_button_clicked(self, wid):
        actions = self.get_actions()
        self.save_actions(actions)

        dlg = Gtk.MessageDialog(wid.get_toplevel(),
                Gtk.DialogFlags.DESTROY_WITH_PARENT,
                Gtk.MessageType.INFO, Gtk.ButtonsType.CLOSE,
                f"""Acceleration data were written to "{self.accel_path}".

Please edit the file and restart Liferea.""")
        dlg.props.title = "Accels created"
        dlg.run()
        dlg.destroy()

    def _on_show_accels_button_clicked(self, wid):
        action_groups = self.group_actions(self.get_actions())
        sc_win = build_shortcut_window(action_groups, self.Group_Names)
        sc_win.props.transient_for = wid.get_toplevel()
        sc_win.show_all()

    def save_actions(self, actions):
        if not actions:
            return
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

    def _on_reload_button_clicked(self, wid):
        accels = self.plugin.load_accels()
        self.plugin.set_accels(accels)

    def _on_edit_accels_button_clicked(self, wid):
        actions = self.get_actions()
        action_groups = self.group_actions(actions)
        dialog = EditShortCutDialog(wid.get_toplevel(), action_groups)
        dialog.Group_Names = self.Group_Names
        dialog.connect("response", self._on_edit_dialog_response)
        dialog.show()

    def _on_edit_dialog_response(self, dlg, resp_id):
        if resp_id == Gtk.ResponseType.APPLY and dlg.changed:
            actions = dlg.fetch_actions()
            self.save_actions(actions)
            self.plugin.set_accels(actions)

        dlg.destroy()

def build_shortcut_window(action_groups, group_names):
    """Generate show xml text
    @action_groups: list of actions grouped by group names
    @group_names: list of group names in display order
    """
    import gtkshortcutgen as sgen
    sshort = sgen.shortcut_entry
    sgroup = sgen.group_entry

    action_maps = {x[0]: list(x[1]) for x in action_groups}
    group_names = [x for x in group_names if x in action_maps]
    group_names += [x for x in action_maps.keys() if x not in group_names]

    groups = {}
    for k in action_maps:
        groups[k] = [sshort(
            x[0].partition(".")[2].replace("-", " ").title(),
            " ".join(x[1]))
            for x in action_maps[k]]

    shortcut_groups = [sgroup(x, groups[x]) for x in group_names]
    shortcut_sections = [
            sgen.section_entry("shortcut", shortcut_groups)
            ]
    win_entry = sgen.shortcut_window_entry("window-shortcut",
            shortcut_sections, modal=1)
    content = sgen.shortcut_xml_gen(win_entry)

    builder = Gtk.Builder()
    builder.add_from_string(content)
    sc_win = builder.get_object("window-shortcut")

    return sc_win

class EditShortCutDialog(Gtk.Dialog):
    """A dialog for editing shortcuts for action"""
    # Name of action groups in display order
    Group_Names = ['Item', 'Feed', 'WebKit', 'New', 'Link', 'Misc', 'Help']
    def __init__(self, parent, action_groups):
        """ A dialog for editing shortcuts for action

        @action_groups: list of pair of actions grouped by catalog.
                        [[group_name, [action-list, ...]], ...]

                        Action can have 0 or multiple bindings
                        action-list: [[action, [keybind, ...]], ...]

        """
        self.action_groups = action_groups
        self.entry_list = []
        self.changed = False

        flags = Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT
        super().__init__("Edit Shortcuts", parent, flags,
                (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                    Gtk.STOCK_APPLY, Gtk.ResponseType.APPLY))
        self.setup_ui()
        self.connect("delete-event", lambda *x: True)
        self.connect("response", self._on_response)

    def _on_response(self, dlg, resp_id):
        if resp_id == Gtk.ResponseType.DELETE_EVENT and dlg.changed:
            ask = Gtk.MessageDialog(dlg, 0, Gtk.MessageType.QUESTION,
                    Gtk.ButtonsType.YES_NO,
                    "Shortcut changed, Close without save?")
            ret = ask.run()
            ask.destroy()
            if ret != Gtk.ResponseType.YES:
                self.stop_emission_by_name("response")

    def setup_ui(self):
        sc = Gtk.ScrolledWindow()
        sc.props.min_content_width = 800
        sc.props.min_content_height = 600
        sc.props.expand = True
        self.get_content_area().add(sc)

        flowbox = Gtk.FlowBox()
        sc.add(flowbox)
        flowbox.props.orientation = Gtk.Orientation.VERTICAL
        flowbox.props.max_children_per_line = 999
        flowbox.props.margin = 12
        action_maps = {x[0]: list(x[1]) for x in self.action_groups}
        group_names = [x for x in self.Group_Names if x in action_maps]
        group_names += [x for x in action_maps.keys() if x not in group_names]

        spacing = 4
        for gname in group_names:
            label = Gtk.Label(f"<<< {gname} >>>")
            flowbox.insert(label, -1)
            for action, accels in action_maps[gname]:
                accels_text = " ".join(accels)
                box = Gtk.Box(Gtk.Orientation.HORIZONTAL, spacing)
                box.props.expand = False
                box.props.valign = Gtk.Align.START

                action_title = action.partition(".")[2].replace("-", " ").title()
                label = Gtk.Label(action_title)
                label.props.xalign = 0
                label.props.hexpand = True
                label.props.vexpand = False
                box.pack_start(label, False, True, spacing)

                entry = Gtk.Entry()
                entry.props.width_chars = 24
                entry.props.tooltip_text = "Enter Accelration Keys"
                entry.props.expand = False
                entry.props.overwrite_mode = True

                entry.action_name = action
                entry.accels = accels_text
                entry.set_text(accels_text)
                entry.set_position(-1)
                self.entry_list.append(entry)
                entry.connect("key-press-event",
                        self.on_show_keyname_keypress_event)
                entry.connect("populate-popup",
                        self._on_edit_entry_populate_popup)
                entry.connect("changed",
                        self._on_edit_entry_changed)
                box.pack_start(entry, False, False, spacing)

                button = Gtk.Button.new_from_icon_name("edit-clear",
                        Gtk.IconSize.SMALL_TOOLBAR)
                button.props.tooltip_text = "Clear Last shortcut"
                button.props.expand = False
                button.props.can_focus = False
                button.connect("clicked",
                        self._on_button_clear_shortcut_clicked, entry)
                box.pack_start(button, False, False, 0)

                button = Gtk.Button.new_from_icon_name("list-add",
                        Gtk.IconSize.LARGE_TOOLBAR)
                button.props.tooltip_text = "Add multiple shortcuts to the same action, seperated by space"
                button.props.expand = False
                button.props.can_focus = False
                # Add extra space to the entry
                button.connect("clicked",
                        self._on_button_multiple_shortcut_clicked, entry)
                box.pack_start(button, False, False, 0)

                flowbox.insert(box, -1)

        sc.show_all()

    @staticmethod
    def split_comma(txt):
        """Split txt with comma space seperated parts"""
        ret = txt.strip(" \t\n,").replace(",", " ").split()
        return ret

    @staticmethod
    def on_show_keyname_keypress_event(entry, evt, *args):
        """Show keyname on keypress event
        Allow multiple keynames seperated by ", "

        """
        # remove <Mode2> Which is NumLock ON
        # https://developer.gnome.org/gtk3/stable/checklist-modifiers.html
        modifier = evt.state & Gtk.accelerator_get_default_mod_mask()
        accel_name = Gtk.accelerator_name(evt.keyval, modifier)

        # single modifier keys not allowed
        pure_modifiers = set()
        mbases = ["Control", "Alt", "Super", "Shift"]
        for base in mbases:
            pure_modifiers.add(base)
            pure_modifiers.add(base + "_L")
            pure_modifiers.add(base + "_R")

        if accel_name in pure_modifiers:
            return True

        # Action can be bind to multiple shortcuts, seperated by space.
        old_text = entry.get_text()
        if old_text.rstrip().endswith(","):
            old_text = EditShortCutDialog.split_comma(old_text)
            accel_name = ", ".join(old_text + [accel_name])
        elif "," in old_text:
            old_text = EditShortCutDialog.split_comma(old_text)
            old_text.pop()  # replace last entry
            accel_name = ", ".join(old_text + [accel_name])

        entry.set_text(accel_name)
        entry.set_position(-1)
        return True

    def fetch_actions(self):
        """Return actions on current state
        @return Action list in [[action, [shortcut, ...]]...]
        """
        actions = [[e.action_name,
            EditShortCutDialog.split_comma(e.get_text())]
            for e in self.entry_list]

        return actions

    def _on_edit_entry_changed(self, entry):
        if not self.changed:
            self.changed = True

    def _on_edit_entry_populate_popup(self, entry, menu):
        """Add context menu"""
        mitems = {}
        for label in ["_Reset", "Clear _Last", "_Multiple keys"]:
            menu_item = Gtk.MenuItem()
            menu_item.show()
            menu_item.props.label = "Shortcut " + label
            menu_item.props.use_underline = True
            menu.append(menu_item)
            mitems[label.split()[0].replace("_", "")] = menu_item

        mitems["Reset"].connect("activate",
                self._on_button_reset_shortcut_clicked, entry)
        mitems["Clear"].connect("activate",
                self._on_button_clear_shortcut_clicked, entry)
        mitems["Multiple"].connect("activate",
                self._on_button_multiple_shortcut_clicked, entry)

    def _on_button_multiple_shortcut_clicked(self, wid, entry):
        old_text = entry.get_text().strip()
        if not old_text:
            return
        entry.set_text(old_text + ", ")
        entry.set_position(-1)

    def _on_button_reset_shortcut_clicked(self, wid, entry):
        entry.set_text(entry.accels)
        entry.set_position(-1)

    def _on_button_clear_shortcut_clicked(self, wid, entry):
        old_text = entry.get_text()
        old_keys = self.split_comma(old_text)
        if len(old_keys) > 0:
            old_keys.pop()
        entry.set_text(", ".join(old_keys))
        entry.set_position(-1)

