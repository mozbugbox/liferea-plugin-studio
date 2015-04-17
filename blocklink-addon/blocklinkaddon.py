#!/usr/bin/python3
# vim:fileencoding=utf-8:sw=4:et
#
# Block Selected URL Links Plugin
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
Block Webview links
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
import json
import time
import threading
import parsedate
try:
    from urllib.error import URLError
    from urllib import request
    from urllib import parse as urlparse
except ImportError:
    from urllib2 import URLError
    import urllib2 as request
    import urlparse

from gi.repository import GObject, Gtk, Gdk, PeasGtk, Liferea
from gi.repository import WebKit

from adblockparserlite import AdblockRulesLite as AdblockRules
#from adblockparser import AdblockRules

FILTER_LIST_URL = "https://raw.githubusercontent.com/gorhill/uBlock/master/assets/ublock/filter-lists.json"

TIME_UNIT = {
        "second": 1,
        "minute": 60,
        "hour": 3600,
        "day": 3600*24,
        }

CONFIG_TYPES = {
        bool:  [],
        int:   ["cache-size-block", "cache-size-unblock"],
        float: [],
        str:   ["filters"],
        }


MAIN_SECTION = "main" # configparse section name
CONFIG_SECTIONS = [MAIN_SECTION]
# Default values for ConfigParser
CONFIG_DEFAULTS = {
        "cache-size-block": "8192",
        "cache-size-unblock": "4096",
        "filters": "",
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

def download_file(url, output_name, cb=None, *args):
    """Download a file and optionally call a callback function with args"""
    if not url.startswith(("http://", "https://")):
        url = "https://{}".format(url)
    try:
        fd = request.urlopen(url)
        content = fd.read()
        fd.close()
    except  URLError as err:
        print("Err: {} {}".format(url, err.reason))
        return
    content = content.decode("UTF-8").strip()
    with io.open(output_name, "w", encoding="UTF-8") as fdw:
        fdw.write(content)
    if cb is not None:
        cb(*args)
    return

def force_alnum(txt):
    """replace non-alphanumeric char with hyphen """
    x = []
    for c in txt:
        if c.isalnum():
            x.append(c)
        else:
            x.append("-")
    return ''.join(x)

try:
    from configparser import ConfigParser
except ImportError:
    from ConfigParser import ConfigParser

class ConfigManager(ConfigParser):
    """Hold ConfigParser for the plugin"""
    config_fname = "blocklink.ini"
    config_dir = os.path.expandvars("$HOME/.config/liferea/plugins/blocklink")

    def __init__(self, config_dir=None):
        ConfigParser.__init__(self, CONFIG_DEFAULTS)
        self.changed = False # Flag for self.config changed status
        self.delay_save_timeout = 10

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

class BlockCache:
    filename_unblock = "lookup-cache-unblock.json"
    filename_block = "lookup-cache-block.json"
    def __init__(self, cache_dir,
            cache_size_unblock=4096, cache_size_block=8192):
        """Cache for block test result.

        Two caches for block/unblock are used, so we can set different
        cache size for blocked or unblocked url cache.
        """
        self.save_trigger = 64
        self.cache_dir = cache_dir
        self.cache_filename_unblock = os.path.join(cache_dir,
                self.filename_unblock)
        self.cache_filename_block = os.path.join(cache_dir, self.filename_block)

        from lrucache import LRUCache
        self.cache_unblock = LRUCache(cache_size_unblock)
        self.cache_block = LRUCache(cache_size_block)

    def load(self):
        self.cache_unblock.load(self.cache_filename_unblock)
        self.cache_block.load(self.cache_filename_block)

    def make_key(self, url, *args):
        key = url + json.dumps(args, sort_keys=True, indent=None,
                separators= (',', ':'))
        return key

    def save(self, force=False):
        trigger = 0 if force == True else self.save_trigger
        if self.cache_unblock.insert_count > trigger:
            self.cache_unblock.save(self.cache_filename_unblock)
            self.cache_unblock.reset_insert_count()
        if self.cache_block.insert_count > trigger:
            self.cache_block.save(self.cache_filename_block)
            self.cache_unblock.reset_insert_count()

    def __getitem__(self, key):
        if key in self.cache_unblock:
            ret = self.cache_unblock[key]
        else:
            ret = self.cache_block[key]
        return ret

    def __setitem__(self, key, value):
        if value:
            self.cache_block[key] = value
        else:
            self.cache_unblock[key] = value

    def __contains__(self, key):
        return key in self.cache_block or key in self.cache_unblock

class FilterManager(GObject.GObject):
    filter_list_fname = "filter-lists.json"
    cache_fname = "lookup-cache.json"
    cache_dir = os.path.expandvars("$HOME/.cache/liferea/blocklink/")

    __gsignals__ = {
            "filter-list-updated": (GObject.SIGNAL_RUN_FIRST, None, ())
            }
    def __init__(self):
        GObject.Object.__init__(self)
        if not os.path.isdir(self.cache_dir):
            os.makedirs(self.cache_dir)

        self.config = ConfigManager()
        self.filter_list = None
        self.filename2filter = None
        self.thread_download_filter_list = None
        self.refresh_interval = 60*60*24*7 # 1 week
        self.refresh_timeout_id = -1
        self.filters = {}
        self.filter_list_update_time = -1
        self.filter_list_fullname = os.path.join(self.cache_dir,
                self.filter_list_fname)

        self.load_filter_list()

        sec = MAIN_SECTION
        cache_size_block = self.config.getint(sec, "cache-size-block")
        cache_size_unblock = self.config.getint(sec, "cache-size-unblock")
        self.cache = BlockCache(self.cache_dir,
                cache_size_unblock, cache_size_block)
        def _idle_do():
            self.cache.load()
            self.load_filters()

        GObject.idle_add(_idle_do)
        #self.load_filters()

    @property
    def active_filters(self):
        """Get a list of active filter for current config"""
        sec = MAIN_SECTION
        filter_str = self.config.get(sec, "filters", "")
        filter_str = filter_str.decode("UTF-8")
        if len(filter_str) == 0 or filter_str.isspace():
            return []
        filter_list = [x.strip() for x in filter_str.split(",")]
        return filter_list

    @active_filters.setter
    def active_filters(self, filters):
        """set active filters for current config"""
        if not isinstance(filters, str):
            filters = ",".join(filters)
        filters = filters.encode("UTF-8")
        sec = MAIN_SECTION
        self.config.set(sec, "filters", filters)

    def get_filter_list(self):
        """Get available filters"""
        if self.filter_list != None:
            return self.filter_list

    def load_filter_list(self, force_download=False):
        """load available filter list either from disk or internet"""
        filename = self.filter_list_fname
        full_path = os.path.join(self.cache_dir, filename)
        if os.path.exists(full_path) and not force_download:
            with io.open(full_path, encoding="UTF-8") as fd:
                filter_list = json.load(fd)
                filename2filter = {}
                for k, v in filter_list.items():
                    filename = force_alnum(v["title"]) + "-filter.txt"
                    v["filename"] = filename
                    filename2filter[filename] = k
                    self.filename2filter = filename2filter
                self.filter_list = filter_list
            self.emit("filter-list-updated")

        elif (self.thread_download_filter_list is None or
            not self.thread_download_filter_list.is_alive() or force_download):
            def _update_filter_list():
                """Update filter list in main thread"""
                GObject.idle_add(self.load_filter_list)

            url = FILTER_LIST_URL
            t = threading.Thread(target=download_file,
                    args=(url, full_path, _update_filter_list))
            self.thread_download_filter_list = t
            t.start()
            time.sleep(0.01)

        return False

    @on_idle
    def _update_filters(self, k, v):
        """Update filters in main thread"""
        if k in self.filters:
            self.filters[k] = v

    def _load_filters(self, filter_list):
        """Load filter rules to filter manager"""
        need_download = []
        for f in filter_list:
            full_path = os.path.join(self.cache_dir, f)
            if not os.path.exists(full_path):
                need_download.append((f, full_path))
                continue
            self._load_filter(f, full_path)
            time.sleep(0.01)

        if len(need_download) > 0:
            # wait for self.filename2filter
            while self.filename2filter is None:
                time.sleep(5)

        for f, full_path in need_download:
            try:
                url = self.filename2filter[f]
                download_file(url, full_path, self._load_filter, f, full_path)
            except  URLError as err:
                print("Err: {} {}".format(url, err.reason))

    def load_filters(self):
        """load filter into rules by using threading"""
        filter_list = self.active_filters
        for f in filter_list:
            self.filters[f] = None
        t = threading.Thread(target=self._load_filters,
                args=(filter_list,))
        t.start()
        time.sleep(0.01)

    def _load_filter(self, f, full_path):
        """Use lower case key"""
        rinfo = {}
        with io.open(full_path, encoding="UTF-8") as fd:
            rules = AdblockRules(fd, supported_options=["third-party"],
                    skip_unsupported_rules=False)
            rinfo["__rules"] = rules
            fd.seek(0, os.SEEK_SET)
            for i in range(20):
                line = fd.readline().strip()
                if line and not line.startswith(("!", "[Adblock")):
                    break
                line = line.lstrip("!").lstrip()
                k, s, v = line.partition(":")
                if not s: continue
                klow = k.lower()
                if klow == "last modified":
                    lmdate = parsedate.parse_date(v)
                    if lmdate:
                        v = lmdate
                    else:
                        v = time.time()
                elif klow == "expires":
                    parts = v.strip().split()
                    exdate = float(parts[0])
                    exunit = parts[1].lower().rstrip("s")
                    v = exdate * TIME_UNIT[exunit]
                rinfo[klow] = v

        if "last modified" not in rinfo:
            rinfo["last modified"] = time.time()
        if "expires" not in rinfo:
            rinfo["expires"] = self.refresh_interval

        # 2 extra hours
        rinfo["update_time"] = rinfo["last modified"] + rinfo["expires"] + 7200

        self._update_filters(f, rinfo)
        return rules

    def load_filter(self, url, force_download=False):
        """Load filter rules by thread"""
        f = self.filter_list[url]["filename"]
        full_path = os.path.join(self.cache_dir, f)
        def _load_again():
            self._load_filter(f, full_path)

        #self.filters[f] = None
        if os.path.exists(full_path) and force_download == False:
            t = threading.Thread(target=self._load_filter,
                    args=(f, full_path))
        else:
            t = threading.Thread(target=download_file,
                    args=(url, full_path, self._load_filter, f, full_path))
        t.start()
        time.sleep(0.01)

    def unload_filter(self, url):
        """remove rules of an active filter"""
        f = self.filter_list[url]["filename"]
        del self.filters[f]

    def _should_block(self, url, *args):
        """Worker for test if a url should be blocked"""
        max_url_length = 2048 # max length of url before treat as garbage
        ret = False

        if len(url) > max_url_length: return ret

        for rinfo in self.filters.values():
            if rinfo is None: continue
            rules = rinfo["__rules"]
            ret = rules.should_block(url, *args)
            if ret:
                break

        key = self.cache.make_key(url, *args)
        self.cache[key] = ret
        self.cache.save()
        return ret

    def should_block(self, url, *args):
        """Test if a  url should be blocked with cache"""
        key = self.cache.make_key(url, *args)
        try:
            ret = self.cache[key]
            #print("cached")
        except KeyError:
            #print("NO cached0")
            ret = self._should_block(url, *args)
            #print("NO cached1")
        return ret

    def refresh_filters(self):
        """Update expired filter files"""
        now = time.time()

        # update filter list file
        fullname = self.filter_list_fullname
        has_filter_list_file = os.path.exists(fullname)
        if self.filter_list_update_time < 0 and has_filter_list_file:
            time_stamp = os.path.getmtime(fullname)
            self.filter_list_update_time = time_stamp + self.refresh_interval

        if self.filter_list_update_time < now:
            self.filter_list_update_time = -1
            self.load_filter_list(True)

        if self.filename2filter is None:
            return True

        # update filter files
        for f, rinfo in self.filters.items():
            if not rinfo: continue
            fullname = os.path.join(self.cache_dir, f)
            fexists = os.path.exists(fullname)
            if "update_time" not in rinfo and fexists:
                time_stamp = os.path.getmtime(fullname)
                rinfo["update_time"] = time_stamp + self.refresh_interval
            if rinfo["update_time"] < now:
                self.load_filter(self.filename2filter[f], True)

        return True

    def start(self):
        refresh_check_timeout = 60*60*6 # 6 hours
        GObject.timeout_add_seconds(300, add_once, self.refresh_filters)
        if self.refresh_timeout_id < 0:
            self.refresh_timeout_id = GObject.timeout_add_seconds(
                    refresh_check_timeout, self.refresh_filters)

    def stop(self):
        if self.refresh_timeout_id > 0:
            GObject.source_remove(self.refresh_timeout_id)
            self.refresh_timeout_id = -1
        self.cache.save(force=True)
        self.config.save_config()

class BlockLinkAddonPlugin (GObject.Object,
        Liferea.ShellActivatable, PeasGtk.Configurable):
    shell = GObject.property (type=Liferea.Shell)
    filter_manager = FilterManager()

    def __init__(self):
        GObject.Object.__init__(self)

    def webkit_view_from_container(self, container):
        """fetch webkit_view from LifereaHtmlView container"""
        kids = container.get_children()
        webkit_view = kids[1].get_child()
        return webkit_view

    @property
    def main_webkit_view(self):
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

    @property
    def current_webviews(self):
        """Get all the available webviews """
        views = []
        webkit_view = self.main_webkit_view
        if webkit_view is None:
            return views
        views.append(webkit_view)

        browser_tabs = self.props.shell.props.browser_tabs

        html_in_tabs = [x.htmlview for x in browser_tabs.props.tab_info_list]
        view_in_tabs = [self.webkit_view_from_container(x.get_widget())
                for x in html_in_tabs]
        views.extend(view_in_tabs)
        return views

    @property
    def browser_notebook(self):
        """Return the notebook of browser_tabs"""
        browser_tabs = self.props.shell.props.browser_tabs
        bt_notebook = browser_tabs.props.notebook
        return bt_notebook

    def do_activate (self):
        """Plugin entry point"""
        if not hasattr(self, "filter_manager"):
            BlockLinkAddonPlugin.filter_manager = FilterManager()
        self.filter_manager.start()
        #print(self.plugin_info)
        #window = self.props.shell.get_window()
        current_views = self.current_webviews
        for v in current_views:
            self.hook_webkit_view(v)

        # watch new webkit view in browser_tabs
        bt_notebook = self.browser_notebook
        cid = bt_notebook.connect("page-added", self.on_tab_added)
        bt_notebook.blocklink_page_added_cid = cid

    def do_deactivate (self):
        """Plugin exit point"""
        current_views = self.current_webviews
        if current_views:
            for v in current_views:
                self.unhook_webkit_view(v)

        bt_notebook = self.browser_notebook
        bt_notebook.disconnect(bt_notebook.blocklink_page_added_cid)
        del bt_notebook.blocklink_page_added_cid

        self.filter_manager.stop()

    def on_tab_added(self, noteb, child, page_num, *user_data_dummy):
        """Handle new tab event"""
        webkit_view = self.webkit_view_from_container(child)
        #print(webkit_view)
        self.hook_webkit_view(webkit_view)

    def hook_webkit_view(self, wk_view):
        """on new webkit_view, deal with it"""
        cid = wk_view.connect("resource-request-starting",
                self.on_resource_request_starting)
        wk_view.blocklink_resource_request_start_cid = cid
        wk_view.cache_miss = 0

    def unhook_webkit_view(self, wk_view):
        """ clean hooks on webkit_view"""
        cid = "blocklink_resource_request_start_cid"
        if hasattr(wk_view, cid):
            wk_view.disconnect(getattr(wk_view, cid))
        for k in [cid, "cache_miss"]:
            if hasattr(wk_view, k):
                delattr(wk_view, k)

    def on_resource_request_starting(self, web_view, web_frame,
            web_resource, request, response, *user_data_dummy):
        """webkit_view resouce-request-starting event handler"""
        max_cache_miss = -1 # per page max cache missing/new url
        #print(request, dir(request))
        ret = False
        uri = request.props.uri
        #print(uri)
        #request.props.uri = "about:blank"
        filter_schemes = ("http:", "https:")
        if not uri.startswith(filter_schemes): return ret
        third_party = (
                web_view.props.load_status != WebKit.LoadStatus.PROVISIONAL)
        if third_party:
            urlobj = urlparse.urlparse(web_view.props.uri)
            domain = urlobj.hostname
        else:
            web_view.cache_miss = 0
            domain = ""

        options = {"third-party": third_party}
        key = self.filter_manager.cache.make_key(uri, options)
        try:
            ret = self.filter_manager.cache[key]
            #print("cached")
        except KeyError:
            if 0 < max_cache_miss < web_view.cache_miss:
                ret = False
            else:
                ret = self.filter_manager._should_block(uri,options)
                web_view.cache_miss += 1
                #print(web_view.cache_miss)

        if ret:
            #print("blocked: {}".format(uri))
            request.props.uri = "about:blank"
        return ret

    def do_create_configure_widget(self):
        if not hasattr(self, "filter_manager"):
            BlockLinkAddonPlugin.filter_manager = FilterManager()
        #print(self.plugin_info)
        grid = Gtk.Grid()
        self.setup_ui(grid)
        return grid

    def setup_ui(self, grid):
        GMARGIN = 6
        tree = Gtk.TreeView()
        self.tree = tree
        model = Gtk.ListStore(str, str, str, bool)
        tree.set_model(model)

        renderer_text = Gtk.CellRendererText(xalign=0.0, yalign=0.0)
        from gi.repository import Pango
        renderer_text.props.wrap_width = 300
        renderer_text.props.wrap_mode = Pango.WrapMode.WORD_CHAR
        renderer_text1 = Gtk.CellRendererText(xalign=0.0, yalign=0.0)

        column_text0 = Gtk.TreeViewColumn("Title", renderer_text, text=0)
        column_text0.props.expand = True
        column_text1 = Gtk.TreeViewColumn("URL", renderer_text1, text=1)
        column_text1.props.expand = True
        column_text2 = Gtk.TreeViewColumn("Group", renderer_text1, text=2)
        column_text2.props.expand = True
        renderer_toggle = Gtk.CellRendererToggle(xalign=0.0, yalign=0.0)
        column_toggle0 = Gtk.TreeViewColumn("", renderer_toggle, active=3)

        renderer_toggle.connect("toggled", self.on_filter_toggled)

        tree.append_column(column_text2)
        tree.append_column(column_text0)
        tree.append_column(column_toggle0)
        tree.append_column(column_text1)
        column_text0.props.sort_column_id = 0
        column_text1.props.sort_column_id = 1
        column_text2.props.sort_column_id = 2
        column_toggle0.props.sort_column_id = 3

        column_text0.props.resizable = True
        column_text1.props.resizable = True
        column_text2.props.resizable = True

        tree.props.search_column = 0
        tree.set_search_equal_func(treeview_equal_func)

        GObject.idle_add(self.fill_tree)
        self.filter_manager.connect("filter-list-updated", self.fill_tree)

        swin = Gtk.ScrolledWindow()
        swin.props.expand = True
        swin.props.margin = GMARGIN
        screen = Gdk.Screen.get_default()
        w = screen.get_width()
        h = screen.get_height()
        swin.set_size_request(int(w*3/5), int(h*3/5))
        swin.add(tree)
        grid.attach(swin, 0, 0, 1, 1)

    def fill_tree(self, *args):
        """Fill filter list treeview"""
        filter_list = self.filter_manager.get_filter_list()
        if not filter_list:
            return
        model = self.tree.get_model()
        if filter_list is None:
            return

        list_by_group = {}
        for k, v in filter_list.items():
            group = v["group"]
            if group not in list_by_group:
                list_by_group[group] = []
            list_by_group[group].append((k, v))

        active_filters = self.filter_manager.active_filters
        model.clear()
        for g in sorted(list_by_group.keys()):
            items = list_by_group[g]
            for k, v in sorted(items, key = lambda x: x[1]["title"]):
                url = k
                title = v["title"]
                status = v["filename"] in active_filters
                group = v["group"]
                data = (title, url, group, status)
                model.append(data)
        return False

    def on_filter_toggled(self, renderer, path, *args):
        model = self.tree.get_model()
        miter = model.get_iter(path)
        url = model.get_value(miter, 1)
        status = not model.get_value(miter, 3)
        model.set_value(miter, 3, status)
        active_filters = self.filter_manager.active_filters
        fname = self.filter_manager.filter_list[url]["filename"]
        if status:
            self.filter_manager.load_filter(url)
            if fname not in active_filters:
                active_filters.append(fname)
        else:
            self.filter_manager.unload_filter(url)
            if fname in active_filters:
                active_filters.remove(fname)
        self.filter_manager.active_filters = active_filters

def treeview_equal_func(model, col, akey, aiter, *data):
    """For treeview search, search for 'in'. """
    val = model.get_value(aiter, col)
    ret = True
    if akey.lower() in val.lower():
        ret = False
    return ret

