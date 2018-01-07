#!/usr/bin/python3
# vim:fileencoding=utf-8:sw=4:et
#
# Change WebKit setting for WebView in Liferea
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
Change WebKit settings
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
gi.require_version('WebKit', '3.0')

from gi.repository import GObject, Gtk, Gdk, PeasGtk, Liferea
from gi.repository import WebKit, Soup

UI_FILE_PATH = os.path.join(os.path.dirname(__file__), "webkitsetting.ui")

# WebKit WebView->Settings properties sort by type
WEBVIEW_PROPERTY_TYPE = {
        bool: [
            "enable-dns-prefetching",
            "enable-accelerated-compositing",
            "enable-frame-flattening",
            "enable-smooth-scrolling",
            ],
        int: ["minimum-font-size"],
        str: ["user-agent"],
        }

# SoupSession properties sort by type
SOUP_PROPERTY_TYPE = {
        bool: [
            "enable-disk-cache",
            "enable-persistent-cookie",
            "enable-do-not-track",
            ],
        int: [
            "max-conns",
            "max-conns-per-host",
            "cache-size",
            ],
        str: [],
        }

WEBKIT_SECTION = "WebKit" # configparse section name
SOUP_SECTION = "Soup" # configparse section name
CONFIG_SECTIONS = [WEBKIT_SECTION, SOUP_SECTION]

# Default values for ConfigParser
CONFIG_DEFAULTS = {
        # webview
        "enable-dns-prefetching": "False",
        "enable-accelerated-compositing": "False",
        "enable-frame-flattening": "False",
        "enable-smooth-scrolling": "False",
        "minimum-font-size": "7",
        "user-agent": "",

        # Soup
        "max-conns": "60",
        "max-conns-per-host": "6",
        "enable-disk-cache": "False",
        "cache-size": "32",
        "enable-persistent-cookie": "False",
        "enable-do-not-track": "False",
        }

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
    sys.stdout.flush()
#liferea_symbols() # uncomment to print out export symbols

def on_idle(func):
    """Decorator to run func on GObject.idle_add """
    def _idle_run(*args):
        GObject.idle_add(func, *args)
    return _idle_run

def add_once(func, *args):
    """run the timeout_add/idle_add func once"""
    func(*args)
    return False

try:
    from configparser import ConfigParser
except ImportError:
    from ConfigParser import ConfigParser

class ConfigManager(ConfigParser):
    """Hold ConfigParser for the plugin"""
    config_fname = "webkitsetting.ini"
    config_dir = os.path.expandvars(
            "$HOME/.config/liferea/plugins/webkitsetting")
    cache_dir = os.path.expandvars(
            "$HOME/.cache/liferea/webkitsetting")
    data_dir = os.path.expandvars(
            "$HOME/.local/share/liferea/plugin-data/webkitsetting")

    def __init__(self, config_dir=None):
        ConfigParser.__init__(self, CONFIG_DEFAULTS)
        self.changed = False # Flag for self.config changed status
        self.delay_save_timeout = 10

        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)

        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)

        if config_dir is not None:
            self.config_dir = config_dir

        if not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir)
        self.config_fname = os.path.join(self.config_dir, self.config_fname)
        self.load_config()

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

    @property
    def http_cache_dir(self):
        cache_dir = os.path.join(self.cache_dir, "httpcache")
        return cache_dir

    @property
    def cookiejar_filename(self):
        cookiejar_fname = "cookiejar.db"
        cookiejar_fullname = os.path.join(self.data_dir, cookiejar_fname)
        return cookiejar_fullname


class WebKitSettingPlugin (GObject.Object,
        Liferea.ShellActivatable, PeasGtk.Configurable):
    __gtype_name__ = "WebKitSettingPlugin"

    shell = GObject.property (type=Liferea.Shell)

    _shell = None
    config = ConfigManager()

    def __init__(self):
        GObject.Object.__init__(self)

    def do_activate (self):
        """Override Peas Plugin entry point"""
        if not hasattr(self, "config"):
            WebKitSettingPlugin.config = ConfigManager()
        if self._shell is None:
            WebKitSettingPlugin._shell = self.props.shell

        current_views = self.current_webviews
        for v in current_views:
            self.hook_webkit_view(v)
            self.config_webkit_view(v)
        self.config_soup()

        # watch new webkit view in browser_tabs
        browser_tabs = self._shell.props.browser_tabs
        self.tabs = browser_tabs
        bt_notebook = browser_tabs.props.notebook
        bt_notebook.connect("page-added", self.on_tab_added)

    def do_deactivate (self):
        """Peas Plugin exit point"""
        self.unconfig_soup()
        self.config.save_config()

    def on_tab_added(self, noteb, child, page_num, *user_data_dummy):
        """callback for new webview tab creation"""
        webkit_view = self.webkit_view_from_container(child)
        #print(webkit_view)
        self.hook_webkit_view(webkit_view)

    def hook_webkit_view(self, wk_view):
        self.config_webkit_view(wk_view)

    def webkit_view_from_container(self, container):
        """fetch webkit_view from a LifereaHtmlView container"""
        kids = container.get_children()
        webkit_view = kids[1].get_child()
        return webkit_view

    @property
    def main_webkit_view(self):
        """Return the webkit webview in the item_view"""
        shell = self._shell
        item_view = shell.props.item_view
        if not item_view:
            return None
        htmlv = item_view.props.html_view
        #print(itemv_webkit_view)
        container = htmlv.get_widget()
        webkit_view = self.webkit_view_from_container(container)
        return webkit_view

    @property
    def current_webviews(self):
        """Get all the available webviews """
        views = []
        webkit_view = self.main_webkit_view
        if webkit_view is None:
            return views
        views.append(webkit_view)

        browser_tabs = self._shell.props.browser_tabs

        html_in_tabs = [x.htmlview for x in browser_tabs.props.tab_info_list]
        view_in_tabs = [self.webkit_view_from_container(x.get_widget())
                for x in html_in_tabs]
        views.extend(view_in_tabs)
        return views

    def config_webkit_view(self, wk_view):
        """Load config values to a webkit webview"""
        wk_settings = wk_view.get_settings()
        sec = WEBKIT_SECTION
        config = self.config
        for k in WEBVIEW_PROPERTY_TYPE[bool]:
            val = config.getboolean(sec, k)
            wk_settings.set_property(k, val)

        for k in WEBVIEW_PROPERTY_TYPE[int]:
            val = config.getint(sec, k)
            wk_settings.set_property(k, val)

        for k in WEBVIEW_PROPERTY_TYPE[str]:
            val = config.get(sec, k)
            wk_settings.set_property(k, val)

    def load_soup_cache(self, soup_session):
        sec = SOUP_SECTION
        cache_size = self.config.getint(sec, "cache-size")
        cache_size = cache_size * 1024 * 1024
        cache_dir = self.config.http_cache_dir
        cache = Soup.Cache.new(cache_dir,
                Soup.CacheType.SINGLE_USER)
        cache.set_max_size(cache_size)
        cache.load()
        soup_session.add_feature(cache)
        return cache

    def get_soup_cache(self, soup_session):
        """Get soup cache for the given soup session"""
        caches = soup_session.get_features(Soup.Cache)
        cache_dir = self.config.http_cache_dir
        for cache in caches:
            if cache_dir == cache.props.cache_dir:
                return cache

    def unload_soup_cache(self, soup_session):
        cache = self.get_soup_cache(soup_session)
        if not cache:
            return
        soup_session.remove_feature(cache)
        cache.dump()

    def load_soup_cookiejar(self, soup_session):
        fname = self.config.cookiejar_filename
        cookiejar = Soup.CookieJarDB.new(fname, False)
        soup_session.add_feature(cookiejar)
        return cookiejar

    def get_soup_cookiejar(self, soup_session):
        """Get soup cookiejar for the given soup session"""
        cookiejars = soup_session.get_features(Soup.CookieJarDB)
        fname = self.config.cookiejar_filename
        for cookiejar in cookiejars:
            if fname == cookiejar.props.filename:
                return cookiejar

    def unload_soup_cookiejar(self, soup_session):
        cookiejar = self.get_soup_cookiejar(soup_session)
        if not cookiejar:
            return
        soup_session.remove_feature(cookiejar)

    def on_soup_request_queued(self, soup_session, msg, *user_data):
        sec = SOUP_SECTION
        if self.config.getboolean(sec, "enable-do-not-track"):
            headers = msg.props.request_headers
            headers.replace("DNT", "1")
        #print(msg.props.request_headers.get("DNT"))

    def config_soup(self):
        """Load config values to a soup session"""
        soup_session = WebKit.get_default_session()
        cid = soup_session.connect("request_queued",
                self.on_soup_request_queued)
        soup_session.request_queued_cid = cid

        sec = SOUP_SECTION
        for k in SOUP_PROPERTY_TYPE [int]:
            if k in ["cache-size"]:
                continue
            val = self.config.getint(sec, k)
            soup_session.set_property(k, val)
        for k in SOUP_PROPERTY_TYPE [bool]:
            val = self.config.getboolean(sec, k)
            if k == "enable-disk-cache":
                if val:
                    self.load_soup_cache(soup_session)
                else:
                    self.unload_soup_cache(soup_session)
            elif k == "enable-persistent-cookie":
                if val:
                    self.load_soup_cookiejar(soup_session)
                else:
                    self.unload_soup_cookiejar(soup_session)
            elif k in ["enable-do-not-track"]:
                pass
            else:
                soup_session.set_property(k, val)

    def unconfig_soup(self):
        """Load config values to a soup session"""
        soup_session = WebKit.get_default_session()
        soup_session.disconnect(soup_session.request_queued_cid)

        self.unload_soup_cache(soup_session)

    def do_create_configure_widget(self):
        """Peas Plugin Configurable entry point"""
        if not hasattr(self, "config"):
            WebKitSettingPlugin.config = ConfigManager()
        #print(self.plugin_info)
        grid = Gtk.Grid()
        self.setup_ui(grid)
        return grid

    def setup_ui(self, grid):
        """Actually setup the configure dialog"""
        GMARGIN = 6

        builder = self.builder = Gtk.Builder()
        builder.add_from_file(UI_FILE_PATH)

        stack = Gtk.Stack()
        stack_switcher = Gtk.StackSwitcher()
        stack_switcher.props.stack = stack

        swin = Gtk.ScrolledWindow()
        swin.props.expand = True
        swin.props.margin = GMARGIN
        screen = Gdk.Screen.get_default()
        w = screen.get_width()
        h = screen.get_height()
        swin.set_size_request(int(w*3/5), int(h*3/5))
        swin.add(stack)
        grid.attach(stack_switcher, 0, 0, 1, 1)
        grid.attach(swin, 0, 1, 1, 1)

        grid_webview = builder.get_object("grid_webview")
        parent = grid_webview.get_parent()
        parent.remove(grid_webview)
        stack.add_titled(grid_webview, "webview", "Web Page")
        grid_soup = builder.get_object("grid_soup")
        parent = grid_soup.get_parent()
        parent.remove(grid_soup)
        stack.add_titled(grid_soup, "soup", "Network")
        stack.props.visible_child = grid_webview
        handlers = {
            "spinbutton_int_value_changed_cb":
                self.on_spinbutton_int_value_changed,
            "entry_editing_done_cb": self.on_entry_editing_done,
            "entry_focus_out_event_cb": self.on_entry_editing_done,
            "entry_changed_cb": self.on_entry_changed,
            "checkbutton_toggled_cb": self.on_checkbutton_toggled
        }
        self.config_gui()
        builder.connect_signals(handlers)

    def set_property(self, pname, pvalue):
        """Set a property for WebView or SoupSession """
        pname = pname.replace("_", "-")
        sec = None
        for ptype, pnames in WEBVIEW_PROPERTY_TYPE.items():
            if pname not in pnames: continue
            sec = WEBKIT_SECTION
            wk_views = self.current_webviews
            for wk_view in wk_views:
                wk_settings = wk_view.get_settings()
                wk_settings.set_property(pname, pvalue)
            break
        if sec is None:
            for ptype, pnames in SOUP_PROPERTY_TYPE.items():
                if pname not in pnames: continue
                sec = SOUP_SECTION
                soup_session = WebKit.get_default_session()
                if pname == "enable-disk-cache":
                    if pvalue:
                        self.load_soup_cache(soup_session)
                    else:
                        self.unload_soup_cache(soup_session)
                    sb = self.builder.get_object("spinbutton_cache_size")
                    sb.props.sensitive = pvalue
                elif pname == "enable-persistent-cookie":
                    if pvalue:
                        self.load_soup_cookiejar(soup_session)
                    else:
                        self.unload_soup_cookiejar(soup_session)
                elif pname == "cache-size":
                    cache = self.get_soup_cache(soup_session)
                    if cache:
                        cache.set_max_size(pvalue * 1024 * 1024)
                elif pname in ["enable-do-not-track"]:
                    pass
                else:
                    soup_session.set_property(pname, pvalue)
                break

        if sec is not None:
            self.config.set(sec, pname, pvalue)

    def on_spinbutton_int_value_changed(self, widget, *data):
        """Callback for spinbutton which return a Int"""
        wid = Gtk.Buildable.get_name(widget)
        wtype, s, wname = wid.partition("_")
        value = widget.props.value
        value = int(value)
        self.set_property(wname, value)

    def on_entry_changed(self, widget, *data):
        """Callback for Entry widget"""
        widget.changed = True

    def on_entry_editing_done(self, widget, *data):
        """Callback for Entry widget"""
        if not hasattr(widget, "changed") or not widget.changed:
            return

        wid = Gtk.Buildable.get_name(widget)
        wtype, s, wname = wid.partition("_")
        value = widget.get_text()
        self.set_property(wname, value)

        widget.changed = False

    def on_checkbutton_toggled(self, widget, *data):
        """Callback for CheckButton widget"""
        wid = Gtk.Buildable.get_name(widget)
        wtype, s, wname = wid.partition("_")
        value = widget.props.active
        self.set_property(wname, value)

    def config_gui(self, *args):
        """Set configure dialog state with config values"""
        sec = WEBKIT_SECTION
        config = self.config
        for k in WEBVIEW_PROPERTY_TYPE[bool]:
            ku = k.replace("-", "_")
            val = config.getboolean(sec, k)
            wname = "checkbutton_" + ku
            widget = self.builder.get_object(wname)
            widget.props.active = val

        for k in WEBVIEW_PROPERTY_TYPE[int] + SOUP_PROPERTY_TYPE[int]:
            ku = k.replace("-", "_")
            val = config.getint(sec, k)
            wname = "spinbutton_" + ku
            widget = self.builder.get_object(wname)
            widget.props.value = val

        for k in WEBVIEW_PROPERTY_TYPE[str]:
            ku = k.replace("-", "_")
            val = config.get(sec, k)
            wname = "entry_" + ku
            widget = self.builder.get_object(wname)
            widget.props.text = val

        sec = SOUP_SECTION
        for k in SOUP_PROPERTY_TYPE[bool]:
            ku = k.replace("-", "_")
            val = config.getboolean(sec, k)
            wname = "checkbutton_" + ku
            widget = self.builder.get_object(wname)
            widget.props.active = val
            if k == "enable-disk-cache":
                sb = self.builder.get_object("spinbutton_cache_size")
                sb.props.sensitive = val

        for k in SOUP_PROPERTY_TYPE[int]:
            ku = k.replace("-", "_")
            val = config.getint(sec, k)
            wname = "spinbutton_" + ku
            widget = self.builder.get_object(wname)
            widget.props.value = val

        for k in SOUP_PROPERTY_TYPE[str]:
            ku = k.replace("-", "_")
            val = config.get(sec, k)
            wname = "entry_" + ku
            widget = self.builder.get_object(wname)
            widget.props.text = val

