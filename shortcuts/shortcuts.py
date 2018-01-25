#!/usr/bin/python3
# vim:fileencoding=utf-8:sw=4:et
#
# Extra Shortcuts Plugin
#
# Copyright (C) 2014 Mozbugbox <mozbugbox@yahoo.com.au>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Library General Public
# License as published by the Free Software Foundation; either
# version 2 of the License, or (at your option) any later version.
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
Extra shortcuts:

        m:  more to display by load the link
        f:  forward to the next item in the current feed
        n:  next unread item
        x:  load the link to the eXternal browser
    space:  skim through the unread items, scroll content if more

"""
"""
Plugin dev help:
  http://lzone.de/Writing-Liferea-Plugins-Tutorial-Part-1
  https://developer.gnome.org/libpeas/1.10/pt01.html
  https://wiki.gnome.org/Apps/Gedit/PythonPluginHowTo
  https://github.com/lwindolf/liferea/tree/master/plugins
"""

from gi.repository import GObject, Gtk, Gdk, PeasGtk, Liferea

def liferea_symbols():
    """Print out symbols exported by `Liferea` module"""
    gobj_attrs = set(dir(GObject.Object))
    def _print_it(obj):
        klasses = []
        if hasattr(obj, "__name__"):
            print(obj.__name__+":")
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
    import sys
    sys.stdout.flush()
#liferea_symbols() # uncomment to print out export symbols

class ShortcutPlugin (GObject.Object, Liferea.ShellActivatable):
    __gtype_name__ = 'ShortcutPlugin'

    object = GObject.property (type=GObject.Object)
    shell = GObject.property (type=Liferea.Shell)

    def do_activate (self):
        #print(self.plugin_info)
        window = self.shell.get_window()
        window.connect("key-press-event",
                self.on_key_press_event)
        window.connect_after("key-press-event",
                self.on_key_press_event_after)

    def on_key_press_event(self, widget, event):
        window = self.shell.get_window()
        focusw = window.get_focus()
        if not focusw or isinstance(focusw, Gtk.Entry):
            return False
        wtype = GObject.type_name(focusw)
        if wtype == "WebKitWebView":
            return False

        # handle our shortcuts
        ret = self.my_key_handler(widget, event)

        return ret

    def on_key_press_event_after(self, widget, event):
        ret = self.my_key_handler(widget, event)
        return ret

    def my_key_handler(self, widget, event):
        itemview = self.shell.props.item_view
        itemlistview = itemview.props.item_list_view
        tree = itemlistview.get_widget()

        # for single key press, do `! &` mask keys
        mod_masks = (
                Gdk.ModifierType.SHIFT_MASK
                | Gdk.ModifierType.CONTROL_MASK
                | Gdk.ModifierType.MOD1_MASK
                | Gdk.ModifierType.SUPER_MASK
                )
        single_key = not (event.state & mod_masks)

        if single_key and event.keyval == Gdk.KEY_m:
            if isinstance(tree, Gtk.TreeView):
                tree.grab_focus()
                path, col = tree.get_cursor()
                if path:
                    tree.row_activated(path, col)
            return True

        elif single_key and event.keyval == Gdk.KEY_space:
            if isinstance(tree, Gtk.TreeView):
                path, col = tree.get_cursor()
                tree.grab_focus()
                # if no item in current treeview, scroll to next
                path2, col2 = tree.get_cursor()
                if not path and path2:
                    return True
            itemview.scroll()
            return True

        elif single_key and event.keyval == Gdk.KEY_f:
            if isinstance(tree, Gtk.TreeView):
                tree.grab_focus()
            itemview.move_cursor(1)

        elif single_key and event.keyval == Gdk.KEY_n:
            if isinstance(tree, Gtk.TreeView):
                tree.grab_focus()
            Liferea.ItemList.select_next_unread()

        """
        elif single_key and event.keyval == Gdk.KEY_x:
            Liferea.on_popup_launch_item_external_selected()
            return True
        """

        return False

    def do_deactivate (self):
        pass

class ShortcutConfigure(GObject.Object, PeasGtk.Configurable):
    __gtype_name__ = 'ShortcutConfigure'
    def do_create_configure_widget(self):
        #print(self.plugin_info)
        grid = Gtk.Grid()

        # show help info
        textview = Gtk.TextView()

        textview.props.editable = False
        textview.props.cursor_visible = False
        textview.props.margin = 6
        textview.props.left_margin = 4
        textview.props.right_margin = 6
        textview.props.pixels_above_lines = 4
        textview.props.pixels_below_lines = 6

        help_prelog = "Useful Shortcuts:\n"
        help_content01 = """\
        m:  more to display by load the link
        f:  forward to the next item in the current feed
        n:  next unread item
        x:  load the link to the eXternal browser
    space:  skim through the unread items, scroll content if more
"""
        text_buff = textview.get_buffer()
        text_buff.set_text(help_prelog)

        # monospace table
        tag = text_buff.create_tag("code")
        tag.props.family = "monospace"
        titer = text_buff.get_end_iter()
        text_buff.insert_with_tags(titer, help_content01, tag)

        grid.attach(textview, 0, 0, 1, 1)
        grid.show_all()
        return grid
