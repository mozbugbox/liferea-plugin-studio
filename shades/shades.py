#!/usr/bin/python3
# vim:fileencoding=utf-8:sw=4:et
#
# Darken bright background of web page
#
# Copyright (C) 2015-2023 Mozbugbox <mozbugbox@yahoo.com.au>
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
Darken bright background
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

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('PeasGtk', '1.0')
gi.require_version('WebKit2', '4.0')

from gi.repository import GObject, Gtk, Gdk, PeasGtk, Liferea
from gi.repository import WebKit2

UI_FILE_PATH = os.path.join(os.path.dirname(__file__), "shades.ui")

# config settings sort by type
CONFIG_TYPES = {
        bool: ["use-color",],
        float: ["threshold", "lightness"],
        str: [],

        "colorbutton": ["color", "text-color"],
        }


MAIN_SECTION = "main" # configparse section name
CONFIG_SECTIONS = [MAIN_SECTION]
# Default values for ConfigParser
CONFIG_DEFAULTS = {
        "threshold": "0.80",
        "lightness": "0.66",
        "use-color": "False",
        "text-color": "rgb(0, 0, 0)",
        "color": "rgb(100, 190, 170)"
        }

def on_idle(func):
    """Decorator to run func on GObject.idle_add """
    def _idle_run(*args):
        GObject.idle_add(func, *args)
    return _idle_run

def add_once(func, *args):
    """run the timeout_add/idle_add func once"""
    func(*args)
    return False

def add_forever(func, *args):
    """run the timeout_add/idle_add func repeatedly"""
    func(*args)
    return True

try:
    from configparser import ConfigParser
except ImportError:
    from ConfigParser import ConfigParser

class ConfigManager(ConfigParser):
    """Hold ConfigParser for the plugin"""
    config_fname = "shades.ini"
    config_dir = os.path.expandvars(
            "$HOME/.config/liferea/plugins/shades")

    def __init__(self, config_dir=None):
        self.changed = False # Flag for self.config changed status
        self.delay_save_timeout = 10
        ConfigParser.__init__(self, CONFIG_DEFAULTS)
        self.shades_script = ""

        if config_dir is not None:
            self.config_dir = config_dir

        if not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir)
        self.config_fname = os.path.join(self.config_dir, self.config_fname)
        self.load_config()
        self.load_script()

    def load_script(self):
        fname = "shades-script.js"
        fullname = os.path.join(os.path.dirname(__file__), fname)
        with io.open(fullname, "r", encoding="UTF-8") as fd:
            content = fd.read()
            self.shades_script = content

    def load_config(self):
        """Initialize configparser"""
        for sec in CONFIG_SECTIONS:
            self.add_section(sec)
        if os.path.exists(self.config_fname):
            self.read(self.config_fname)

    def save_config(self):
        """Save config to file"""
        if self.changed:
            with open(self.config_fname, "w") as fdw:
                self.write(fdw)
            self.changed = False

    def set(self, sec, k, v):
        """Set config value and save it in a timeout"""
        ret = ConfigParser.set(self, sec, k, str(v))
        self.changed = True
        GObject.timeout_add_seconds(self.delay_save_timeout, self.save_config)
        return ret

class InspectorWindow:
    """Embed WebKitInspector for a WebKit WebView"""
    def __init__(self, wk_view):
        settings = wk_view.get_settings()
        self.old_developer_extras = settings.props.enable_developer_extras
        settings.props.enable_developer_extras = True

        self.window = Gtk.Window()
        self.window.props.title = "Liferea Inspector"
        screen = Gdk.Screen.get_default()
        w = screen.get_width()
        h = screen.get_height()
        self.window.resize(int(w*2/3), int(h*2/3))
        inspector = wk_view.get_inspector()
        #inspector.connect("inspect-web-view", self.on_inspect_web_view)
        #inspector.connect("show-window", self.on_show_window)
        #inspector.connect("close-window", self.on_close_window)
        #inspector.connect("finished", self.on_finished)

        wk_view.connect("context-menu", self.on_context_menu)
        self.inspector = inspector
        self.wk_view = wk_view

    def on_context_menu(self, wk_view, context_menu, event, hit_test_result):
        menuitem = WebKit2.ContextMenuItem.new_from_stock_action(
                WebKit2.ContextMenuAction.INSPECT_ELEMENT)
        menuitem.show()
        menuitem.get_action.connect("activate", self.on_menu_activate)
        context_menu.append(menuitem)
        return False

    def detach_webview(self):
        """On unhook webview, remove signal connections"""
        #inspector = self.inspector
        wk_view = self.wk_view

        #inspector.disconnect_by_func(self.on_inspect_web_view)
        #inspector.disconnect_by_func(self.on_show_window)
        #inspector.disconnect_by_func(self.on_close_window)
        #inspector.disconnect_by_func(self.on_finished)

        wk_view.disconnect_by_func(self.on_context_menu)

        settings = self.wk_view.get_settings()
        settings.props.enable_developer_extras = self.old_developer_extras
        self.inspector = None
        self.wk_view = None

    def on_menu_activate(self, *args):
        self.show()

    def on_inspect_web_view(self, inspector, wk_view, *data):
        myview = WebKit2.WebView()
        self.window.add(myview)
        return myview

    def on_show_window(self, inspector, *data):
        self.window.show_all()

    def on_close_window(self, inspector, *data):
        self.window.hide()

    def on_finished(self, inspector, *data):
        self.window.destroy()
        self.inspector = None

    def show(self):
        if self.inspector:
            self.inspector.show()

class ShadesPlugin (GObject.Object,
        Liferea.ShellActivatable, PeasGtk.Configurable):
    __gtype_name__ = "ShadesPlugin"

    object = GObject.property(type=GObject.Object)
    shell = GObject.property(type=Liferea.Shell)

    _shell = None
    config = ConfigManager()

    def __init__(self):
        GObject.Object.__init__(self)

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

        return htmlv

    @property
    def current_webviews(self):
        """Get all the available webviews """
        views = []
        webkit_view = self.main_webkit_view
        if webkit_view is None:
            return views
        views.append(webkit_view.props.renderwidget)

        browser_tabs = self._shell.props.browser_tabs
        tab_infos = browser_tabs.props.tab_info_list
        if tab_infos:
            box_in_tabs = [x.htmlview for x in tab_infos]
            html_in_tabs = [x.get_widget() for x in box_in_tabs]
            views.extend(html_in_tabs)
        return views

    @property
    def browser_notebook(self):
        """Return the notebook of browser_tabs"""
        browser_tabs = self._shell.props.browser_tabs
        bt_notebook = browser_tabs.props.notebook
        return bt_notebook

    def do_activate(self):
        """Override Peas Plugin entry point"""
        if not hasattr(self, "config"):
            ShadesPlugin.config = ConfigManager()
        if self._shell is None:
            ShadesPlugin._shell = self.props.shell
        #print(self.plugin_info)
        #window = self._shell.get_window()

        current_views = self.current_webviews
        for v in current_views:
            self.hook_webkit_view(v)

        # watch new webkit view in browser_tabs
        bt_notebook = self.browser_notebook
        cid = bt_notebook.connect("page-added", self.on_tab_added)
        bt_notebook.shades_page_added_cid = cid

    def do_deactivate(self):
        """Peas Plugin exit point"""
        current_views = self.current_webviews
        if current_views:
            for v in current_views:
                self.unhook_webkit_view(v)

        bt_notebook = self.browser_notebook
        bt_notebook.disconnect(bt_notebook.shades_page_added_cid)
        del bt_notebook.shades_page_added_cid

        self.config.save_config()

    def on_tab_added(self, noteb, child, page_num, *user_data_dummy):
        """callback for new webview tab creation"""
        # A notebook tab holds a GtkBox with another GtkBox that separates
        # location bar and LifereaHtmlView
        self.hook_webkit_view(child.get_children()[1])

    def hook_webkit_view(self, wk_view):
        cid = wk_view.connect("load-changed",
                self.on_load_status_changed)
        failed_id = wk_view.connect("load-failed",
                self.on_load_failed)
        wk_view.shades_load_status_cid = cid
        wk_view.shades_load_failed_id = failed_id
        wk_view.shades_timeout_shade_cid = -1
        #wk_view.inspector_window = InspectorWindow(wk_view)
        #wk_view.inspector_window.show()

    def unhook_webkit_view(self, wk_view):
        if hasattr(wk_view, "shades_load_status_cid"):
            wk_view.disconnect(wk_view.shades_load_status_cid)
            del wk_view.shades_load_status_cid
        if hasattr(wk_view, "shades_load_faild_id"):
            wk_view.disconnect(wk_view.shades_load_failed_id)
            del wk_view.shades_load_failed_id
        self.stop_periodic_shade(wk_view)

        #wk_view.inspector_window.detach_webview()
        #del wk_view.inspector_window

    def do_shades(self, wk_view):
        """run the javascript function that shades web page"""
        #print("shading", wk_view.props.load_status)
        sec = MAIN_SECTION
        conf = self.config
        threshold = conf.get(sec, "threshold")
        text_color = '"{}"'.format(conf.get(sec, "text-color"))
        if conf.getboolean(sec, "use-color"):
            color = '"{}"'.format(conf.get(sec, "color"))
            bgcolor = color
        else:
            color = conf.getfloat(sec, "lightness")
            bgcolor = '"hsl(0, 0%, {}%)"'.format(color*100)
        call_content = """
            // webkit default to solid white!
            LifereaShades.set_background({}, {});
            LifereaShades.do_shade({}, {});
            """.format(text_color, bgcolor, threshold, color)
        #print(threshold, color)
        wk_view.run_javascript(call_content)

    def on_load_status_changed(self, wid, load_event):
        """handle load status change for WebView"""
        if load_event == WebKit2.LoadEvent.COMMITTED:
            wid.run_javascript(self.config.shades_script)
            self.do_shades(wid)
            self.start_periodic_shade(wid)
        elif load_event in [WebKit2.LoadEvent.FINISHED]:
            self.do_shades(wid)
            self.stop_periodic_shade(wid)
        #print(status)

    def on_load_failed(self, wid, load_event, failed_url, error):
        self.stop_periodic_shade(wid)

    def stop_periodic_shade(self, wk_view):
        """Stop the periodic shade update on a webview"""
        if wk_view.shades_timeout_shade_cid > 0:
            GObject.source_remove(wk_view.shades_timeout_shade_cid)
            wk_view.shades_timeout_shade_cid = -1

    def _on_shades_timeout(self, wk_view, current_timeout):
        """Do shades with incremental timeout intervals

        Stop further update when page loading take too long
        """
        max_interval = 30

        wk_view.shades_timeout_shade_cid = -1
        self.do_shades(wk_view)

        # increase periodic update interval
        if current_timeout < max_interval:
            current_timeout *= 2
            self.start_periodic_shade(wk_view, current_timeout)
        return False

    def start_periodic_shade(self, wk_view, timeout=1):
        """Start the periodic shade update on a webview"""
        self.stop_periodic_shade(wk_view)
        cid = GObject.timeout_add_seconds(timeout,
                self._on_shades_timeout, wk_view, timeout)
        wk_view.shades_timeout_shade_cid = cid

    def do_create_configure_widget(self):
        """Peas Plugin Configurable entry point"""
        if not hasattr(self, "config"):
            ShadesPlugin.config = ConfigManager()
        #print(self.plugin_info)
        #grid = Gtk.Grid()
        grid = self.setup_ui()
        return grid

    def setup_ui(self):
        """Actually setup the configure dialog"""
        builder = self.builder = Gtk.Builder()
        builder.add_from_file(UI_FILE_PATH)

        # reparent
        grid_config = builder.get_object("grid_config")
        parent = grid_config.get_parent()
        parent.remove(grid_config)

        handlers = {
            "on_scale_float_value_changed": self.on_scale_float_value_changed,
            "on_colorbutton_color_set": self.on_colorbutton_color_set,
            "on_checkbutton_toggled": self.on_checkbutton_toggled
        }
        self.config_gui()
        builder.connect_signals(handlers)

        screen = Gdk.Screen.get_default()
        w = screen.get_width()
        grid_config.set_size_request(int(w*1/2), -1)

        return grid_config

    def set_property(self, pname, pvalue):
        """Set a property for WebView or SoupSession """
        pname = pname.replace("_", "-")
        sec = None
        for ptype, pnames in CONFIG_TYPES.items():
            if pname not in pnames: continue
            sec = MAIN_SECTION
            break

        if sec is not None:
            self.config.set(sec, pname, pvalue)

    def on_scale_float_value_changed(self, widget, *data):
        """Callback for spinbutton which return a Int"""
        wid = Gtk.Buildable.get_name(widget)
        wtype, s, wname = wid.partition("_")
        #value = widget.props.value
        value = widget.get_value()
        self.set_property(wname, value)

    def on_colorbutton_color_set(self, widget, *data):
        """Callback for colorbutton widget"""
        wid = Gtk.Buildable.get_name(widget)
        wtype, s, wname = wid.partition("_")
        rgba = widget.props.rgba
        css_color = rgba.to_string()
        self.set_property(wname, css_color)

    def on_checkbutton_toggled(self, widget, *data):
        """Callback for CheckButton widget"""
        wid = Gtk.Buildable.get_name(widget)
        wtype, s, wname = wid.partition("_")
        value = widget.props.active
        self.set_property(wname, value)
        if wname == "use_color":
            colorb = self.builder.get_object("colorbutton_color")
            colorb.props.sensitive = value

    def config_gui(self, *args):
        """Set configure dialog state with config values"""
        sec = MAIN_SECTION
        config = self.config
        for k in CONFIG_TYPES[bool]:
            ku = k.replace("-", "_")
            val = config.getboolean(sec, k)
            wname = "checkbutton_" + ku
            widget = self.builder.get_object(wname)
            widget.props.active = val
            if k == "use-color":
                cwid = self.builder.get_object("colorbutton_color")
                cwid.props.sensitive = val

        for k in CONFIG_TYPES[float]:
            ku = k.replace("-", "_")
            val = config.getfloat(sec, k)
            wname = "scale_" + ku
            widget = self.builder.get_object(wname)
            widget.set_value(val)

        for k in CONFIG_TYPES["colorbutton"]:
            ku = k.replace("-", "_")
            val = config.get(sec, k)
            rgba = Gdk.RGBA()
            rgba.parse(val)
            val = rgba
            wname = "colorbutton_" + ku
            widget = self.builder.get_object(wname)
            widget.props.rgba = val

        for k in CONFIG_TYPES[str]:
            ku = k.replace("-", "_")
            val = config.get(sec, k)
            wname = "entry_" + ku
            widget = self.builder.get_object(wname)
            widget.props.text = val

