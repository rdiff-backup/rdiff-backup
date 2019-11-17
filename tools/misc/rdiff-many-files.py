#!/usr/bin/env python3
"""Run rdiff to transform everything in one dir to another"""

import sys
import os

dir1, dir2 = sys.argv[1:3]
for i in range(1000):
    assert not os.system("rdiff signature %s/%s sig" % (dir1, i))
    assert not os.system("rdiff delta sig %s/%s diff" % (dir2, i))
    assert not os.system(
        "rdiff patch %s/%s diff %s/%s.out" % (dir1, i, dir1, i))
