#!/usr/bin/python3
# vim:fileencoding=utf-8:sw=4:et
"""
GtkShortcutsWindow helper for generating GtkBuilder XML file.

```
    shortcuts1 = [
        shortcut_entry("Quit", gesture="gesture-two-finger-swipe-left"),
    ]

    shortcuts2 = [
        shortcut_entry("Import channels from file", "<ctrl>o"),
        shortcut_entry("Export channels to file", "<ctrl>e"),
    ]

    groups = [
            group_entry("Application", shortcuts1),
            group_entry("Import/Export Channels", shortcuts2),
            ]
    sections = [
            section_entry("shortcut", groups)
            ]

    entry = shortcut_window_entry("shortcut-window", sections, modal=1)

    shortcuts_xml_string = shortcut_xml_gen(entry)
    builder = Gtk.Builder()
    builder.add_from_string(shortcuts_xml_string)

```

"""

from __future__ import print_function, unicode_literals, absolute_import, division
import sys
import os
import io
import logging as log

NATIVE=sys.getfilesystemencoding()

from lxml import etree

def shortcut_xml_gen(shortcut_entries):
    root = etree.Element("interface")
    root.append(create_object_tree(shortcut_entries))
    content = etree.tostring(root, xml_declaration=True, encoding="UTF-8",
            pretty_print=True)
    content = content.decode("UTF-8")
    return content

def create_object_tree(base_entry):
    def objnode(adict):
        prefix = "GtkShortcuts"
        if not adict["klass"].startswith(prefix):
            adict["klass"] = prefix + adict["klass"]
        if "attrib" not in adict:
            adict["attrib"]= {}
        aobj = etree.Element ("object", attrib=adict["attrib"])
        aobj.attrib["class"] = adict["klass"]
        return aobj

    def propnode(name, value):
        aobj = etree.Element ("property", attrib={"name": name})
        if name == "title":
            aobj.attrib["translatable"] = "yes"
        aobj.text = str(value)
        return aobj

    def append_props(parent, item):
        if "properties" in item:
            props = [propnode(x, y) for x, y in item["properties"].items()]
            [parent.append(x) for x in props]

    def do_object_tree(entry):
        eroot = objnode(entry)
        append_props(eroot, entry)
        if "childs" in entry:
            for kid in entry["childs"]:
                ke = etree.Element("child")
                eroot.append(ke)
                subroot = do_object_tree(kid)
                ke.append(subroot)
        return eroot
    return do_object_tree(base_entry)

def shortcut_entry(title, accel=None, gesture=None, **kwargs):
    props = { "title": title, "visible": 1, }
    if accel:
        props["accelerator"] = accel
    if gesture:
        props["shortcut-type"] = gesture
    props.update(kwargs)
    entry = {
            "klass": "Shortcut",
            "properties": props,
            }
    return entry

def group_entry(title, shortcuts, **kwargs):
    entry = {
            "klass":"Group",
            "properties": {
                "visible": 1,
                "title": title,
                },
            "childs": shortcuts,
            }
    entry["properties"].update(kwargs)
    return entry

def section_entry(name, groups, **kwargs):
    entry = {
            "klass": "Section",
            "properties": {
                "visible": 1,
                "section-name": name,
                },
            "childs": groups,
            }
    entry["properties"].update(kwargs)
    return entry

def shortcut_window_entry(id_, sections, **kwargs):
    entry = {
            "klass": "Window",
            "attrib": {"id": id_},
            "properties": {"modal": "1"},
            "childs": sections,
            }
    entry["properties"].update(kwargs)
    return entry


def main():
    def set_stdio_encoding(enc=NATIVE):
        import codecs; stdio = ["stdin", "stdout", "stderr"]
        for x in stdio:
            obj = getattr(sys, x)
            if not obj.encoding: setattr(sys,  x, codecs.getwriter(enc)(obj))
    set_stdio_encoding()

    log_level = log.INFO
    log.basicConfig(format="%(levelname)s>> %(message)s", level=log_level)

    shortcuts1 = [
        shortcut_entry("Quit", gesture="gesture-two-finger-swipe-left"),
    ]

    shortcuts2 = [
        shortcut_entry("Import channels from file", "<ctrl>o"),
        shortcut_entry("Export channels to file", "<ctrl>e"),
    ]

    groups = [
            group_entry("Application", shortcuts1),
            group_entry("Import/Export Channels", shortcuts2),
            ]
    sections = [
            section_entry("shortcut", groups)
            ]

    entry = shortcut_window_entry("shortcut-window", sections, modal=1)

    content = shortcut_xml_gen(entry)
    print(content)

    def test_gui(shortcut_xml):
        import gi
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk
        builder = Gtk.Builder()
        builder.add_from_string(shortcut_xml)
        win = builder.get_object("shortcut-window")
        win.connect("delete-event", lambda *w: Gtk.main_quit())
        win.show_all()
        Gtk.main()
    test_gui(content)


if __name__ == '__main__':
    import signal; signal.signal(signal.SIGINT, signal.SIG_DFL)
    main()

