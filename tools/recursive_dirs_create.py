#!/usr/bin/env python
# create recursively directories with optionally a certain limit as parameter

import os
import sys

SOMEDIR = "somedir"
SOMEFILE = "somefile"

if len(sys.argv) > 1:
    imax = int(sys.argv[1])
else:
    imax = sys.getrecursionlimit() + 1

i = 0
while i < imax:
    print(i)
    os.mkdir(SOMEDIR)
    os.chdir(SOMEDIR)
    with open(SOMEFILE, "w"):
        pass
    i += 1
