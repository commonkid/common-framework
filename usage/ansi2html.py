#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ansi2html.py — turn truecolor ANSI output into a standalone HTML page."""

import html
import re
import sys

TOK = re.compile(r"\x1b\[([0-9;]*)m")
PAGE_BG = "#1c1c1e"


def convert(text, default_fg="#e8ecf2"):
    out = []
    fg = bg = None
    bold = False
    rev = False
    open_span = False

    def close():
        nonlocal open_span
        if open_span:
            out.append("</span>")
            open_span = False

    def open_():
        nonlocal open_span
        st = []
        f, b = (fg or default_fg), bg
        if rev:
            f, b = (b or PAGE_BG), (fg or default_fg)
        st.append("color:%s" % f)
        if b:
            st.append("background:%s" % b)
        if bold:
            st.append("font-weight:700")
        out.append('<span style="%s">' % ";".join(st))
        open_span = True

    i = 0
    while i < len(text):
        m = TOK.search(text, i)
        if not m:
            close()
            out.append(html.escape(text[i:]))
            break
        if m.start() > i:
            close()
            open_()
            out.append(html.escape(text[i:m.start()]))
            close()
        params = [p for p in m.group(1).split(";") if p != ""]
        if not params or params[0] == "0":
            fg = bg = None
            bold = False
            rev = False
        else:
            j = 0
            while j < len(params):
                p = params[j]
                if p == "1":
                    bold = True
                elif p == "7":
                    rev = True
                elif p == "27":
                    rev = False
                elif p == "38" and j + 4 < len(params) and params[j + 1] == "2":
                    fg = "#%02x%02x%02x" % tuple(int(x) for x in params[j + 2:j + 5])
                    j += 4
                elif p == "48" and j + 4 < len(params) and params[j + 1] == "2":
                    bg = "#%02x%02x%02x" % tuple(int(x) for x in params[j + 2:j + 5])
                    j += 4
                j += 1
        i = m.end()
    close()
    body = "".join(out)
    return """<!doctype html><meta charset="utf-8">
<style>
  html,body{background:%s;margin:0;padding:22px 24px}
  pre{font-family:"SF Mono","JetBrains Mono","DejaVu Sans Mono",monospace;
      font-size:15px;line-height:1.28;letter-spacing:0;margin:0;
      color:%s;white-space:pre}
  span{display:inline}
</style><pre>%s</pre>""" % (PAGE_BG, default_fg, body)


if __name__ == "__main__":
    sys.stdout.write(convert(sys.stdin.read()))
