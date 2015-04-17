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
        self._capacity = capacity
        self.cache = collections.OrderedDict()
        self._insert_count = 0

    def __len__(self):
        return len(self.cache)

    def __contains__(self, key):
        return key in self.cache

    def __getitem__(self, key):
        value = self.cache.pop(key)
        self.cache[key] = value
        return value

    def __setitem__(self, key, value):
        try:
            self.cache.pop(key)
        except KeyError:
            if len(self.cache) >= self._capacity:
                self.cache.popitem(last=False)
        self.cache[key] = value
        self._insert_count += 1

    @property
    def capacity(self):
        return self._capacity

    @capacity.setter
    def capacity(self, cap):
        self._capacity = cap
        cap_list = list(self.cache.items())[:cap]
        self.cache = collections.OrderedDict(cap_list)

    @property
    def insert_count(self):
        return self._insert_count

    def reset_insert_count(self):
        self._insert_count = 0

    def load(self, path):
        try:
            if os.path.exists(path):
                with io.open(path, encoding="utf-8") as fd:
                    cache_list = json.load(fd, encoding="UTF-8")
                    if len(cache_list) > self._capacity:
                        cache_list = cache_list[:self._capacity]
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

