#!/usr/bin/python3
# vim:fileencoding=utf-8:sw=4:et
#
# Parse date string
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
from __future__ import print_function, unicode_literals, absolute_import
import sys

import datetime
import email.utils
import time
def parse_date(date_str):
    """Convert date string into time stamp"""
    try:
        dtuple = email.utils.parsedate_tz(date_str)
        if dtuple is not None:
            timestamp = time.mktime(dtuple[:9])
            return timestamp
    except TypeError:
        #raise
        pass

    parts = date_str.split()
    ddict = {}
    used = set()
    for i, p in enumerate(parts):
        if ":" in p:
            ddict["time"] = p
            used.add(i)
            break

    for i, p in enumerate(parts):
        if i in used: continue
        if "-" in p and not p.startswith("-"):
            ddict["date"] = p
            used.add(i)
        elif "/" in p and not p.startswith("-"):
            ddict["date"] = p
            used.add(i)
        elif p.startswith(("+", "-")):
            ddict["tz"] = p
            used.add(i)

    adate = {}
    attr_names = ["hour", "minute", "second"]
    if "time" in ddict:
        v = ddict["time"]
        pre, s, tz = v.partition("+")
        if not s:
            pre, s, tz = v.partition("+")
        if s:
            ddict["tz"] = s + tz
            v = pre
        tparts = v.split(":")
        for i, d in enumerate(tparts):
            adate[attr_names[i]] = int(d)

    attr_names = ["day", "month", "year"]
    now = datetime.datetime.today()
    if "date" in ddict:
        v = ddict["date"]
        parts = v.split("/")
        if len(parts) < 2:
            parts = v.split("-")
        if len(parts[0]) == 4:
            parts.reverse() # year first
        if int(parts[1]) > 12:
            parts.reverse()
        for i, d in enumerate(parts):
            d = int(d)
            if i == 2 and d < 100:
                d += 2000
            adate[attr_names[i]] = int(d)
    if "tz" in ddict:
        v = ddict["tz"]
        tz = datetime.timedelta(hours=int(v[:3]))
        # FIXME: only valid for python3
        #adate["tzinfo"] = datetime.timezone(tz)
    if "year" not in adate:
        adate["year"] = now.year
    try:
        adate = datetime.datetime(**adate)
        timestamp = time.mktime(adate.timetuple())
    except ValueError:
        timestamp = None

    return timestamp

def main():
    parse_date(sys.argv[1])

if __name__ == '__main__':
    main()

