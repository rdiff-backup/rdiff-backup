#!/usr/bin/env python
# delete recursively created directories (and files)

import os

SOMEDIR = "somedir"
SOMEFILE = "somefile"

try:
    while os.path.exists(SOMEDIR):
        os.chdir(SOMEDIR)
except OSError:
    pass

i = 0

while os.path.basename(os.getcwd()) == SOMEDIR:
    print(i)
    if os.path.exists(SOMEFILE):
        os.unlink(SOMEFILE)
    if os.path.exists(SOMEDIR):
        os.rmdir(SOMEDIR)
    os.chdir("..")
    i += 1

if os.path.exists(SOMEDIR):
    os.rmdir(SOMEDIR)
