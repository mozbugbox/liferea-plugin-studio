#!/usr/bin/python3
# vim:fileencoding=utf-8:sw=4:et
"""
Search Chinese text using InputMethod initials

Copyright (C) 2016 copyright <mozbugbox@yahoo.com.au>

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, see <http://www.gnu.org/licenses/>.

Usage:
    im_matcher = create_matcher("immatcher_table.json")
    txt = "红花不是,随便的花草鱼虫"
    index = im_matcher.find(txt, "hh")
    if index >= 0:
        print("found")
    else:
        print("not found")
"""

from __future__ import print_function, unicode_literals, absolute_import, division
import sys
import os
import io
import logging
import functools
import re

__version__ = "0.2"
CACHE_SIZE = 512

NATIVE = sys.getfilesystemencoding()

TABLE_SEPERATOR = '|'
UNICODE_REGION = {
        "hani_comp": [0XF900, 0XFAFF],
        "hani_comp_sup": [0X2F800, 0X2FA1F],
        "hani_bmp": [0X4E00, 0X9FFF],
        "hani_exta": [0X3400, 0X4DBF],
        "hani_extb": [0X20000, 0X2A6DF],
        "hani_extc": [0X2A700, 0X2B73F],
        "hani_extd": [0X2B740, 0X2B81F],
        "hani_exte": [0X2B820, 0X2CEAF],
        }
NUMS_ZH = "零一二三四五六七八九"

def decode_im_table(im_table_data):
    """decode a string of im_table to list of im codes"""
    # decode RLE
    def _expand_rle(m):
        seg = m.group()
        return seg[-1] * int(seg[:-1])
    result = re.sub(r"\d+[A-Za-z{}]".format(TABLE_SEPERATOR),
            _expand_rle, im_table_data)

    # convert "A" => "a|"
    result = re.sub(r"[A-Z]",
            lambda x: x.group().lower() + TABLE_SEPERATOR, result)
    im_list = result.split(TABLE_SEPERATOR)
    return im_list

class IMMatcher:
    """ Search Chinese text using InputMethod initials """
    def __init__(self, im_table_dict=None):
        self.im_table = None
        if im_table_dict is not None:
            self.im_table = {}
            for k, v in im_table_dict.items():
                self.im_table[k] = decode_im_table(v)

    def match_charcode_region(self, tcode, key_char, reg):
        """Match charcode to a unicode region"""
        ret = False
        start, end = UNICODE_REGION[reg]
        try:
            if start <= tcode <= end:
                ret = key_char in self.im_table[reg][tcode - start]
        except IndexError:
            ret = False
        return ret

    @functools.lru_cache(maxsize=CACHE_SIZE)
    def match_char(self, target, key_char):
        """Match a input keycode to IM codes of target"""
        if target == key_char:
            return True
        if self.im_table is None:
            return False

        if "0" <= target <= "9":
            target = NUMS_ZH[int(target)]

        tcode = ord(target)
        im_table = self.im_table

        match_charcode_region = self.match_charcode_region
        for region in im_table.keys():
            res = match_charcode_region(tcode, key_char, region)
            if res:
                break
        return res

    def find(self, txt, sub, start=0, end=None):
        """Customized version of string.find to match IM code"""
        if end is None:
            end = len(txt)
        elif end < 0:
            end = len(txt) + end

        matched = txt.find(sub, start, end)
        if matched >= 0:
            return matched
        if self.im_table is None:
            return -1

        sub_len = len(sub)
        match_char = self.match_char
        for n in range(start, end - sub_len + 1):
            matched = n
            for i in range(sub_len):
                if not match_char(txt[n + i], sub[i]):
                    matched = -1
                    break
            if matched >= 0:
                break
        return matched

    def contains(self, txt, sub):
        """test if a string contains substring, include IM code"""
        return self.find(txt, sub) >= 0

def create_matcher(default_im_filename=None):
    """Create a IMMatcher from json file of im data
    Try immatcher_table.json in user home dir first."""
    matcher = None

    fname = "${HOME}/.local/share/im-matcher/immatcher_table.json"
    im_filename = os.path.expandvars(fname)

    if not os.path.exists(im_filename) and default_im_filename is not None:
        im_filename = default_im_filename

    if not os.path.exists(im_filename):
        log.warning("im-matcher data not found: {}".format(im_filename))
        return matcher

    import json
    log.debug("im-matcher data: {}".format(im_filename))
    try:
        with io.open(im_filename) as fh:
            im_dict = json.load(fh)
        matcher = IMMatcher(im_dict["im_table"])
        #print(matcher.im_table, len(matcher.im_table))
    except json.JSONDecodeError as e:
        log.error("{} @{}.{}".format(e.msg, e.lineno, e.colno))
    except KeyError as e:
        log.error(str(e))
    return matcher

def setup_log(log_level=None):
    global log
    rlog = logging.getLogger()
    if __name__ == "__main__" and not rlog.hasHandlers():
        # setup root logger
        ch = logging.StreamHandler()
        formatter = logging.Formatter("%(levelname)s:%(name)s:: %(message)s")
        ch.setFormatter(formatter)
        rlog.addHandler(ch)

    log = logging.getLogger(__name__)

    if log_level is not None:
        log.setLevel(log_level)
        rlog.setLevel(log_level)
setup_log()

def main():
    def set_stdio_encoding(enc=NATIVE):
        import codecs; stdio = ["stdin", "stdout", "stderr"]
        for x in stdio:
            obj = getattr(sys, x)
            if not obj.encoding: setattr(sys,  x, codecs.getwriter(enc)(obj))
    set_stdio_encoding()

    log_level = logging.INFO
    setup_log(log_level)

    im_data_filename = sys.argv[1]
    im_matcher = create_matcher(im_data_filename)
    txt = "红花不是,随便的\ufeab花草鱼虫"
    print(im_matcher.find(txt, "abc"), -1)
    print(im_matcher.find(txt, "hhb"), 0)
    print(im_matcher.find(txt, ",sbd"), 4)
    print(im_matcher.find(txt, "spd"), 5)
    print(im_matcher.find(txt, "cyi"), 10)
    print(im_matcher.find(txt, "h", 3), 9)
    print(im_matcher.find("now新闻台:", "jl"), -1)
    print(im_matcher.find("一二三", "y"), 0)
    print(im_matcher.find("damn 1 03 0923", "lj"), 10);

if __name__ == '__main__':
    main()

