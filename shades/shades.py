#!/usr/bin/python3
# vim:fileencoding=utf-8:sw=4:et
#
# Darken bright background of web page
#
# Copyright (C) 2015 Mozbugbox <mozbugbox@yahoo.com.au>
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

from gi.repository import GObject, Gtk, Gdk, PeasGtk, Liferea
from gi.repository import WebKit

UI_FILE_PATH = os.path.join(os.path.dirname(__file__), "shades.ui")

# config settings sort by type
CONFIG_TYPES = {
        bool:  ["use-color",],
        float: ["threshold", "lightness"],
        str:   [],

        "colorbutton": ["color"],
        }


MAIN_SECTION = "main" # configparse section name
CONFIG_SECTIONS = [MAIN_SECTION]
# Default values for ConfigParser
CONFIG_DEFAULTS = {
        "threshold": "0.80",
        "lightness": "0.66",
        "use-color": "False",
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
        ConfigParser.__init__(self, CONFIG_DEFAULTS)
        self.changed = False # Flag for self.config changed status
        self.delay_save_timeout = 10
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
            self.changed == False

    def set(self, sec, k, v):
        """Set config value and save it in a timeout"""
        ret = ConfigParser.set(self, sec, k, str(v))
        self.changed = True
        GObject.timeout_add_seconds(self.delay_save_timeout, self.save_config)
        return ret

class ShadesPlugin (GObject.Object,
        Liferea.ShellActivatable, PeasGtk.Configurable):
    object = GObject.property (type=GObject.Object)
    shell = GObject.property (type=Liferea.Shell)
    config = ConfigManager()

    def __init__(self):
        GObject.Object.__init__(self)

    def webkit_view_from_container(self, container):
        """fetch webkit_view from a LifereaHtmlView container"""
        kids = container.get_children()
        webkit_view = kids[1].get_child()
        return webkit_view

    def get_main_webkit_view(self):
        """Return the webkit webview in the item_view"""
        shell = self.props.shell
        item_view = shell.props.item_view
        if not item_view:
            return None
        htmlv = item_view.props.html_view
        #print(itemv_webkit_view)
        container = htmlv.get_widget()
        webkit_view = self.webkit_view_from_container(container)
        return webkit_view

    def get_current_webviews(self):
        """Get all the available webviews """
        views = []
        webkit_view = self.get_main_webkit_view()
        if webkit_view is None:
            return views
        views.append(webkit_view)

        browser_tabs = self.props.shell.props.browser_tabs

        html_in_tabs = [x.htmlview for x in browser_tabs.props.tab_info_list]
        view_in_tabs = [self.webkit_view_from_container(x.get_widget())
                for x in html_in_tabs]
        views.extend(view_in_tabs)
        return views

    def get_browser_notebook(self):
        """Return the notebook of browser_tabs"""
        browser_tabs = self.props.shell.props.browser_tabs
        bt_notebook = browser_tabs.props.notebook
        return bt_notebook

    def do_activate (self):
        """Override Peas Plugin entry point"""
        if not hasattr(self, "config"):
            ShadesPlugin.config = ConfigManager()
        #print(self.plugin_info)
        #window = self.shell.get_window()

        current_views = self.get_current_webviews()
        for v in current_views:
            self.hook_webkit_view(v)

        # watch new webkit view in browser_tabs
        bt_notebook = self.get_browser_notebook()
        cid = bt_notebook.connect("page-added", self.on_tab_added)
        bt_notebook.shades_page_added_cid = cid

    def do_deactivate (self):
        """Peas Plugin exit point"""
        current_views = self.get_current_webviews()
        if current_views:
            for v in current_views:
                self.unhook_webkit_view(v)

        bt_notebook = self.get_browser_notebook()
        bt_notebook.disconnect(bt_notebook.shades_page_added_cid)
        del bt_notebook.shades_page_added_cid

        self.config.save_config()

    def on_tab_added(self, noteb, child, page_num, *user_data_dummy):
        """callback for new webview tab creation"""
        webkit_view = self.webkit_view_from_container(child)
        #print(webkit_view)
        self.hook_webkit_view(webkit_view)

    def hook_webkit_view(self, wk_view):
        cid = wk_view.connect("notify::load-status",
                self.on_load_status_changed)
        wk_view.shades_load_status_cid = cid
        wk_view.shades_timeout_shade_cid = -1

    def unhook_webkit_view(self, wk_view):
        if hasattr(wk_view, "shades_load_status_cid"):
            wk_view.disconnect(wk_view.shades_load_status_cid)
            del wk_view.shades_load_status_cid
        self.stop_periodic_shade(wk_view)

    def do_shades(self, wk_view):
        """run the javascript function that shades web page"""
        #print("shading", wk_view.props.load_status)
        sec = MAIN_SECTION
        conf = self.config
        threshold = conf.get(sec, "threshold")
        if conf.getboolean(sec, "use-color"):
            color = '"{}"'.format(conf.get(sec, "color"))
            bgcolor = color
        else:
            color = conf.getfloat(sec, "lightness")
            bgcolor = '"hsl(0, 0%, {}%)"'.format(color*100)
        call_content = """
            // webkit default to solid white!
            LifereaShades.set_background({});
            LifereaShades.shade_window(window, {}, {});
            """.format(bgcolor, threshold, color)
        #print(threshold, color)
        wk_view.execute_script(call_content)

    def on_load_status_changed(self, wid, gparamstring):
        """handle load status change for WebView"""
        status = wid.props.load_status
        if status == WebKit.LoadStatus.FIRST_VISUALLY_NON_EMPTY_LAYOUT:
            wid.execute_script(self.config.shades_script)
            self.do_shades(wid)
            self.start_periodic_shade(wid)
        elif status in [WebKit.LoadStatus.FINISHED, WebKit.LoadStatus.FAILED]:
            self.do_shades(wid)
            self.stop_periodic_shade(wid)
        #print(status)

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

