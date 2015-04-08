#!/usr/bin/python
# vim:fileencoding=utf-8:sw=4:et

from __future__ import print_function, unicode_literals, absolute_import
import sys
import os
import io
import re
import logging as log

import adblockparser

NATIVE=sys.getfilesystemencoding()

class AdblockRuleLite(adblockparser.AdblockRule):
    __slots__ = adblockparser.AdblockRule.__slots__ + ["regex_re"]
    def __init__(self, *args):
        adblockparser.AdblockRule.__init__(self, *args)
        self.regex_re = None

    def _url_matches(self, url):
        if self.regex_re is None:
            self.regex_re = re.compile(self.regex)
        return bool(self.regex_re.search(url))

class AdblockRulesLite(adblockparser.AdblockRules):
    """
    AdblockRules is a class for checking URLs against multiple AdBlock rules.

    It is more efficient to use AdblockRules instead of creating AdblockRule
    instances manually and checking them one-by-one because AdblockRules
    optimizes some common cases.
    """

    def __init__(self, rules, supported_options=None,
            skip_unsupported_rules=True,
            use_re2='auto', max_mem=256*1024*1024, rule_cls=AdblockRuleLite):
        adblockparser.AdblockRules.__init__(self, rules, supported_options,
                skip_unsupported_rules,
                use_re2, max_mem, rule_cls=AdblockRuleLite)

def main():
    def set_stdio_encoding(enc=NATIVE):
        import codecs; stdio = ["stdin", "stdout", "stderr"]
        for x in stdio:
            obj = getattr(sys, x)
            if not obj.encoding: setattr(sys,  x, codecs.getwriter(enc)(obj))
    set_stdio_encoding()

    log_level = log.INFO
    log.basicConfig(format="%(levelname)s>> %(message)s", level=log_level)

    with io.open(sys.argv[1], encoding="UTF-8") as fd:
        #adfilter = AdblockRulesLite(fd, supported_options=["third-party"], skip_unsupported_rules=False)
        adfilter = adblockparser.AdblockRules(fd, supported_options=["third-party"], skip_unsupported_rules=False)
    import time
    n = 1000
    a = time.time()
    for i in range(n):
        adfilter.should_block("http://www.events.kaloooga.com/stom", {"third-party": False})
    b = time.time()
    total = b - a
    print(total, total/n)

    ret = adfilter.should_block("http://www.events.kaloooga.com/stom",
            {"third-party": False})
    #print(ret); return

if __name__ == '__main__':
    main()

