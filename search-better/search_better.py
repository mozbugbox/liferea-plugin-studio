#!/usr/bin/python3
# vim:fileencoding=utf-8:sw=4:et
#
# Use better treeview search function for Liferea feedlist and itemlist
#
# Copyright (C) 2014-2020 Mozbugbox <mozbugbox@yahoo.com.au>
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
Search Better for Liferea
"""

import os
import io
import sys
import functools
import gi

gi.require_version('Gtk', '3.0')
gi.require_version('PeasGtk', '1.0')
gi.require_version('WebKit2', '4.0')

from gi.repository import GObject, Gtk, Gdk, Gio, GLib
from gi.repository import PeasGtk, Liferea

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
#liferea_symbols()  # uncomment to print out export symbols

def log_error(*args, **kwargs):
    """Print to stderr"""
    print(*args, file=sys.stderr, **kwargs)

def on_idle(func):
    """Decorator to run func on GObject.idle_add """
    @functools.wraps(func)
    def _idle_run(*args):
        GObject.idle_add(func, *args)
    return _idle_run

def on_timeout(timeout_ms=100):
    """Decorator to run func once after a timeout"""
    def decorator(func):
        @functools.wraps(func)
        def timeout_run(*args):
            hid = GObject.timeout_add(timeout_ms,
                    add_once, func, *args)
            return hid
        return timeout_run
    return decorator

def add_once(func, *args):
    """run the timeout_add/idle_add func once"""
    func(*args)
    return False

def model_search_func(model, cid, key, miter, *args):
    """Search function for Gtk.TreeStore, return False if matched"""
    value = model.get_value(miter, cid)
    return key.lower() not in value.lower()

class SearchBetterPlugin (GObject.Object, Liferea.ShellActivatable):
    __gtype_name__ = "SearchBetterPlugin"

    shell = GObject.property(type=Liferea.Shell)

    _shell = None

    def __init__(self):
        GObject.Object.__init__(self)

    def do_activate(self):
        """Override Peas Plugin entry point"""
        if self._shell is None:
            SearchBetterPlugin._shell = self.props.shell

        for tview in [self.feedlist_treeview, self.itemlist_treeview]:
            tview.set_search_equal_func(model_search_func)

    def do_deactivate(self):
        """Peas Plugin exit point"""
        pass

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
    def feedlist_treeview(self):
        tview = self._shell.lookup("feedlist")
        return tview

