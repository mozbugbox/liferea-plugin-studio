#!/usr/bin/python3
# vim:fileencoding=utf-8:sw=4:et

from __future__ import print_function, unicode_literals, absolute_import
import sys
import os
import io
import logging as log

NATIVE=sys.getfilesystemencoding()

# http://www.kunxi.org/blog/2014/05/lru-cache-in-python/
import collections
import json
class LRUCache:
    """A Least Recently Used Cache"""
    def __init__(self, capacity):
        self.capacity = capacity
        self.cache = collections.OrderedDict()

    def get(self, key):
        value = self.cache.pop(key)
        self.cache[key] = value
        return value

    def set(self, key, value):
        try:
            self.cache.pop(key)
        except KeyError:
            if len(self.cache) >= self.capacity:
                self.cache.popitem(last=False)
        self.cache[key] = value

    def load(self, path):
        try:
            if os.path.exists(path):
                with io.open(path, encoding="utf-8") as fd:
                    cache_list = json.load(fd, encoding="UTF-8")
                    self.cache = collections.OrderedDict(cache_list)
        except ValueError:
            pass

    def save(self, path):
        cache_list = list(self.cache.items())
        cache_str = json.dumps(cache_list,
                encoding="utf-8", ensure_ascii=False)
        if not isinstance(cache_str, unicode):
            cache_str = unicode(cache_str, "UTF-8")
        try:

            with io.open(path, "w", encoding="utf-8") as fdw:
                fdw.write(cache_str)
        except IOError as e:
            print(e)

def main():
    def set_stdio_encoding(enc=NATIVE):
        import codecs; stdio = ["stdin", "stdout", "stderr"]
        for x in stdio:
            obj = getattr(sys, x)
            if not obj.encoding: setattr(sys,  x, codecs.getwriter(enc)(obj))
    set_stdio_encoding()

    log_level = log.INFO
    log.basicConfig(format="%(levelname)s>> %(message)s", level=log_level)

if __name__ == '__main__':
    main()

