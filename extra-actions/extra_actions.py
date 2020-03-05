#!/usr/bin/python3
# vim:fileencoding=utf-8:sw=4:et
#
# Add some extra actions to Liferea
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
Extra Actions for Liferea
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

UI_FILE_PATH = os.path.join(os.path.dirname(__file__), "extra_actions.ui")

# Config properties group by type
CONFIG_PROPERTY_TYPE = {
    bool: [],
    int: [],
    str: [
        "next-page-pattern",
        "prev-page-pattern",
    ],
}

MAIN_SECTION = "Main"  # configparse section name
CONFIG_SECTIONS = [MAIN_SECTION]

# Default values for ConfigParser
CONFIG_DEFAULTS = {
    "next-page-pattern": "^(next|newer)\\b|»|>>|more",
    "prev-page-pattern": "^(prev(ious)?|older)\\b|«|<<",
}

javascript_lib = """\
(function (lp$) {
    // lp$ is our local namespace
    function incrementUrl(url, count) {
        // Find the final number in a URL
        const matches = url.match(/(.*?)(\d+)(\D*)$/)

        // no number in URL - nothing to do here
        if (matches === null) {
            return null
        }

        const [, pre, number, post] = matches
        const newNumber = parseInt(number, 10) + count
        let newNumberStr = String(newNumber > 0 ? newNumber : 0)

        // Re-pad numbers that were zero-padded to be the same length:
        // 0009 + 1 => 0010
        if (number.match(/^0/)) {
            while (newNumberStr.length < number.length) {
                newNumberStr = "0" + newNumberStr
            }
        }

        return pre + newNumberStr + post
    }

    lp$.urlincrement = function (count = 1) {
        const newUrl = incrementUrl(window.location.href, count)

        if (newUrl !== null) {
            window.location.href = newUrl
        }
    }

    lp$.mouseEvent = function ( element, type, modifierKeys = {}) {
        let events = []
        switch (type) {
            case "unhover":
                events = ["mousemove", "mouseout", "mouseleave"]
                break
            case "click":
                events = ["mousedown", "mouseup", "click"]
            case "hover":
                events = ["mouseover", "mouseenter", "mousemove"].concat(events)
                break
        }
        events.forEach(type => {
            const event = new MouseEvent(type, {
                bubbles: true,
                cancelable: true,
                view: window,
                detail: 1, // usually the click count
                ...modifierKeys,
            })
            element.dispatchEvent(event)
        })
    }
})(window.LifereaPS = window.LifereaPS || {});
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
# liferea_symbols()  # uncomment to print out export symbols

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

try:
    from configparser import ConfigParser
except ImportError:
    from ConfigParser import ConfigParser

class ConfigManager(ConfigParser):
    """Hold ConfigParser for the plugin"""
    config_fname = "extra_actions.ini"
    config_dir = os.path.expandvars(
            "$HOME/.config/liferea/plugins/extra_actions")
    cache_dir = os.path.expandvars(
            "$HOME/.cache/liferea/extra_actions")
    data_dir = os.path.expandvars(
            "$HOME/.local/share/liferea/plugin-data/extra_actions")

    def __init__(self, config_dir=None):
        self.changed = False  # Flag for self.config changed status
        self.delay_save_timeout = 10
        ConfigParser.__init__(self, CONFIG_DEFAULTS)

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
            self.changed = False

    def set(self, sec, k, v):
        """Set config value and save it in a timeout"""
        ret = ConfigParser.set(self, sec, k, str(v))
        self.changed = True
        GObject.timeout_add_seconds(self.delay_save_timeout, self.save_config)
        return ret

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

class ExtraActionsPlugin (GObject.Object,
        Liferea.ShellActivatable, PeasGtk.Configurable):
    __gtype_name__ = "ExtraActionsPlugin"

    shell = GObject.property(type=Liferea.Shell)

    _shell = None
    config = ConfigManager()

    def __init__(self):
        GObject.Object.__init__(self)

    def do_activate(self):
        """Override Peas Plugin entry point"""
        if not hasattr(self, "config"):
            ExtraActionsPlugin.config = ConfigManager()
        if self._shell is None:
            ExtraActionsPlugin._shell = self.props.shell

        self.load_actions()

    def do_action(self, action_name, *args):
        win = self._shell.get_window()
        gapp = win.props.application
        for action_map in [win, gapp]:
            action = action_map.lookup_action(action_name)
            if action is not None:
                break
        if action is None:
            log_error("Unknown action", action_name)
            return
        # log_error("doing", action_name)

        args_new = []
        vtype = action.get_parameter_type()
        if len(args) > 0:
            for arg in args:
                args_new.append(marshall_variant(vtype, arg))

        action.activate(*args_new)

    @on_timeout(100)
    def do_action_100ms_later(self, action_name, *args):
        """Do action after timeout 100ms"""
        self.do_action(action_name, *args)

    def load_actions(self):
        """Setup actions and add default shortcuts"""
        window = self.shell.get_window()
        simple_action_names = [
                "webkit_step_up", "webkit_step_down",
                "webkit_page_up", "webkit_page_down",
                "webkit_half_page_up", "webkit_half_page_down",
                "webkit_step_left", "webkit_step_right",
                "webkit_scroll_home", "webkit_scroll_end",
                "webkit_clear_cache", "webkit_open_inspector",
                "webkit_go_back", "webkit_go_forward",
                "webkit_follow_previous_page", "webkit_follow_next_page",
                "search_focused_list",
                "skim_over_up_item", "skim_over_down_item",
                "skim_over_up_unread_item", "skim_over_down_unread_item",
                ]

        accel_maps = [
                ["win.webkit_page_up", ["BackSpace"]],
            ]

        # action name cannot have "-" in it.
        # action callbacks prefixed with "action_"
        action_entries = [[x.replace("_", "-"),
            getattr(self, "action_" + x, None)] for x in simple_action_names]

        ExtraActionsPlugin.action_list = [x[0] for x in action_entries]
        add_action_entries(window, action_entries)
        for act, accels in accel_maps:
            try:
                act = act.replace("_", "-")
                self.gapp.set_accels_for_action(act, accels)
            except Exception as e:
                log_error(e)

    def webkit_scroll_by(self, percent_x, percent_y):
        """WebKit scroll by percentage"""
        javascript_content = f"""\
                var dist_x = Math.round(window.innerWidth * {percent_x});
                var dist_y = Math.round(window.innerHeight * {percent_y});
                window.scrollBy(dist_x, dist_y);
            """
        main_view = self.main_webkit_view.props.renderwidget
        main_view.run_javascript(javascript_content)

    def webkit_scroll_to_x(self, x, y):
        """WebKit scroll horizontally to absolute pixels"""
        javascript_content = f"""\
                window.scrollTo({x}, window.scrollY);
            """
        main_view = self.main_webkit_view.props.renderwidget
        main_view.run_javascript(javascript_content)

    def webkit_scroll_to_y(self, y):
        """WebKit scroll vertically to absolute pixels"""
        javascript_content = f"""\
                window.scrollTo(window.scrollX, {y});
            """
        main_view = self.main_webkit_view.props.renderwidget
        main_view.run_javascript(javascript_content)

    def webkit_scroll_to_bottom(self):
        """WebKit scroll to bottom"""
        javascript_content = f"""\
                window.scrollTo(window.scrollX, document.body.scrollHeight);
            """
        main_view = self.main_webkit_view.props.renderwidget
        main_view.run_javascript(javascript_content)

    def action_webkit_step_up(self, action, param):
        self.webkit_scroll_by(0, -0.1)

    def action_webkit_step_down(self, action, param):
        self.webkit_scroll_by(0, 0.1)

    def action_webkit_page_up(self, action, param):
        page_percent = 0.9
        self.webkit_scroll_by(0, -page_percent)

    def action_webkit_page_down(self, action, param):
        page_percent = 0.9
        self.webkit_scroll_by(0, page_percent)

    def action_webkit_half_page_up(self, action, param):
        self.webkit_scroll_by(0, -0.5)

    def action_webkit_half_page_down(self, action, param):
        self.webkit_scroll_by(0, 0.5)

    def action_webkit_step_left(self, action, param):
        self.webkit_scroll_by(-0.1, 0)

    def action_webkit_step_right(self, action, param):
        self.webkit_scroll_by(0.1, 0)

    def action_webkit_scroll_home(self, action, param):
        self.webkit_scroll_to_y(0)

    def action_webkit_scroll_end(self, action, param):
        self.webkit_scroll_to_bottom()

    def action_webkit_clear_cache(self, action, param):
        """Clear webkit2 cache.
        Currently cannot set a cache quota on webkit2 gtk(?).
        Cache could grow into GB.
        """
        web_view = self.main_webkit_view.props.renderwidget
        web_context = web_view.get_context()
        web_context.clear_cache()

    def action_webkit_open_inspector(self, action, param):
        web_view = self.main_webkit_view.props.renderwidget
        settings = web_view.get_settings()
        settings.props.enable_developer_extras = True
        inspector = web_view.get_inspector()
        inspector.show()

    def action_webkit_go_back(self, action, param):
        web_view = self.main_webkit_view.props.renderwidget
        web_view.go_back()

    def action_webkit_go_forward(self, action, param):
        web_view = self.main_webkit_view.props.renderwidget
        web_view.go_forward()

    def action_webkit_follow_next_page(self, action, param):
        """Find the link with "next>" like pattern in page and load it"""
        self.webkit_go_following_page("next")

    def action_webkit_follow_previous_page(self, action, param):
        """Find the link with "< previous" like pattern in page and load it"""
        self.webkit_go_following_page("prev")

    def webkit_go_following_page(self, rel="next"):
        """Find the link with "next>" like pattern in page and load it
        @rel: accept "next" | "prev"

        """
        if rel == "previous": rel = "prev"
        rel_pattern = self.config[MAIN_SECTION][f"{rel}-page-pattern"]
        javascript_content = """// borrow from tridactyl/excmds.ts
(function (lp$) {
    // lp$ is our local namespace
    function selectLast(selector) {
        const nodes = document.querySelectorAll(selector)
        return nodes.length ? nodes[nodes.length - 1] : null
    }

    function findRelLink(pattern) {
        // querySelectorAll returns a "non-live NodeList" which is just a shit
        // array without working reverse() or find() calls, so convert it.
        const links = Array.from(document.querySelectorAll("a[href]"))

        // Find the last link that matches the test
        return links.reverse().find(link => pattern.test(link.innerText))

        // Note:
        // `innerText` gives better (i.e. less surprising) results than
        // `textContent` at the expense of being much slower, but that
        // shouldn't be an issue here as it's a one-off operation that's
        // only performed when we're leaving a page
    }

    lp$.followpage = function (rel = "%(rel)s") {
        const link = selectLast(`link[rel~=${rel}][href]`)

        if (link) {
            window.location.href = link.href
            return
        }

        // Many page use Font Awesome style forward/backward code
        const dir = rel === "next" ? "right" : "left"
        const faNames = ["angle", "arrow-alt-circle", "arrow-circle",
            "arrow", "caret", "caret-square", "chevron-circle", "chevron"]
        const faStyle = faNames.map(t => `a > i.fa-${t}-${dir}`).join(", ")
        // console.log(faStyle)

        const rel_pat = new RegExp("%(rel_pattern)s", "i")
        let anchor = (selectLast(`a[rel~=${rel}][href], ${faStyle}`) || findRelLink(rel_pat))

        if (anchor) {
            lp$.mouseEvent(anchor, "click")
        } else {
            lp$.urlincrement(rel === "%(rel)s" ? 1 : -1)
        }
    }
})(window.LifereaPS = window.LifereaPS || {});

LifereaPS.followpage("%(rel)s")
        """ % {"rel_pattern": rel_pattern, "rel": rel}

        main_view = self.main_webkit_view.props.renderwidget
        javascript_content = javascript_lib + javascript_content
        # log_error(f"running javascript:\n{javascript_content}")
        main_view.run_javascript(javascript_content)

    def action_search_focused_list(self, action, param):
        """Start interactive search on the focused treeivew
        Gtk default bind it to "slash".

        """
        focused = self.main_win.get_focus()
        if (isinstance(focused, Gtk.TreeView)):
            # Fix itemlist search column id
            col_id = 2
            pro = focused.props
            if (pro.name == "itemlist" and pro.search_column != col_id):
                focused.props.search_column = col_id

            focused.emit("start-interactive-search")

    def action_skim_over_up_item(self, action, param):
        """Go up unread items without mark the item read"""
        self._skim_without_change_read_status("up", False)

    def action_skim_over_down_item(self, action, param):
        """Go down unread items without mark the item read"""
        self._skim_without_change_read_status("down", False)

    def action_skim_over_up_unread_item(self, action, param):
        """Go up unread items without mark the item read"""
        self._skim_without_change_read_status("up", True)

    def action_skim_over_down_unread_item(self, action, param):
        """Go down unread items without mark the item read"""
        self._skim_without_change_read_status("down", True)

    def _skim_without_change_read_status(self, direct="down",
            unread_only=False):
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
        if not miter: return

        IS_STATE = 10
        ITEMSTORE_WEIGHT = 11
        weight = model.get_value(miter, ITEMSTORE_WEIGHT)
        is_unread = weight == 700
        # for i in range(13): log_error(i, model.get_value(miter, i))
        while unread_only and not is_unread and miter:
            if direct == "down":
                miter = model.iter_next(miter)
            else:
                miter = model.iter_previous(miter)

            if miter is None:
                break

            # for i in range(13): log_error(i, model.get_value(miter, i))
            state = model.get_value(miter, IS_STATE)
            # log_error("IS_STATE", state)

            # FIXME: hack. Liferea does not update IS_STATE when it changed
            # But the weight changes (400, 700), so we take that!
            # src/ui/item_list_view.c/item_list_view_update_item()
            weight = model.get_value(miter, ITEMSTORE_WEIGHT)
            # log_error("ITEM", state)
            is_unread = weight == 700

        if miter:
            tree.grab_focus()
            path = model.get_path(miter)
            tree.set_cursor(path, None, False)
            if is_unread:
                self.do_action("toggle-selected-item-read-status")

    def on_button_clear_cache_clicked(self, wid):
        self.do_action("webkit-clear-cache")

    def do_deactivate(self):
        """Peas Plugin exit point"""
        self.config.save_config()

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

    def do_create_configure_widget(self):
        """Peas Plugin Configurable entry point"""
        if not hasattr(self, "config"):
            ExtraActionsPlugin.config = ConfigManager()
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
        swin.set_size_request(min(600, int(w * 3 / 5)), int(h * 3 / 5))
        swin.add(stack)
        grid.attach(stack_switcher, 0, 0, 1, 1)
        grid.attach(swin, 0, 1, 1, 1)

        grid_extra_actions = builder.get_object("grid_extra_actions")
        parent = grid_extra_actions.get_parent()
        parent.remove(grid_extra_actions)
        stack.add_titled(grid_extra_actions, "grid_extra_actions",
                "Extra Actions")
        stack.props.visible_child = grid_extra_actions

        sw_action_list = builder.get_object("scrolledwindow_action_list")
        parent = sw_action_list.get_parent()
        parent.remove(sw_action_list)
        stack.add_titled(sw_action_list, "scrolledwindow_action_list",
                "Action List")

        handlers = {
            "spinbutton_int_value_changed_cb":
                self.on_spinbutton_int_value_changed,
            "entry_editing_done_cb": self.on_entry_editing_done,
            "entry_focus_out_event_cb": self.on_entry_editing_done,
            "entry_changed_cb": self.on_entry_changed,
            "checkbutton_toggled_cb": self.on_checkbutton_toggled,
            "on_button_clear_cache_clicked":
                self.on_button_clear_cache_clicked,
        }
        self.config_gui()
        builder.connect_signals(handlers)

    def set_property(self, pname, pvalue, gobj=None):
        """Set a property for gobject"""
        pname = pname.replace("_", "-")
        sec = None

        for ptype, pnames in CONFIG_PROPERTY_TYPE.items():
            if pname not in pnames: continue
            sec = MAIN_SECTION
            if gobj is not None:
                gobj.set_property(pname, pvalue)
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
        sec = MAIN_SECTION
        config = self.config
        for k in CONFIG_PROPERTY_TYPE[bool]:
            ku = k.replace("-", "_")
            val = config.getboolean(sec, k, fallback=CONFIG_DEFAULTS[k])
            wname = "checkbutton_" + ku
            widget = self.builder.get_object(wname)
            widget.props.active = val

        for k in CONFIG_PROPERTY_TYPE[int]:
            ku = k.replace("-", "_")
            val = config.getint(sec, k, fallback=CONFIG_DEFAULTS[k])
            wname = "spinbutton_" + ku
            widget = self.builder.get_object(wname)
            widget.props.value = val

        for k in CONFIG_PROPERTY_TYPE[str]:
            ku = k.replace("-", "_")
            val = config.get(sec, k, fallback=CONFIG_DEFAULTS[k])
            wname = "entry_" + ku
            widget = self.builder.get_object(wname)
            widget.props.text = val

        tview_action_list = self.builder.get_object("textview_action_list")
        tbuff = tview_action_list.get_buffer()
        msg = '# "Edit Accels" plugin can be used to bind the following additional actions\n'
        msg += "\n".join([f"win.{x}" for x in self.action_list])
        tbuff.props.text = msg

