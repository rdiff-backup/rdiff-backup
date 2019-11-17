#!/usr/bin/env python3
"""remove-comments.py

Given a python program on standard input, spit one out on stdout that
should work the same, but has blank and comment lines removed.

"""

import sys
import re

triple_regex = re.compile('"""')


def eattriple(initial_line_stripped):
    """Keep reading until end of doc string"""
    assert initial_line_stripped.startswith('"""')
    if triple_regex.search(initial_line_stripped[3:]):
        return
    while 1:
        line = sys.stdin.readline()
        if not line or triple_regex.search(line):
            break


while 1:
    line = sys.stdin.readline()
    if not line:
        break
    stripped = line.strip()
    if not stripped:
        continue
    if stripped[0] == "#":
        continue
    if stripped.startswith('"""'):
        eattriple(stripped)
        continue
    sys.stdout.write(line)
