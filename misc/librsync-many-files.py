#!/usr/bin/env python3
"""Use librsync to transform everything in one dir to another"""

import sys
import librsync

dir1, dir2 = sys.argv[1:3]
for i in range(1000):
    dir1fn = "%s/%s" % (dir1, i)
    dir2fn = "%s/%s" % (dir2, i)

    # Write signature file
    f1 = open(dir1fn, "rb")
    sigfile = open("sig", "wb")
    librsync.filesig(f1, sigfile, 2048)
    f1.close()
    sigfile.close()

    # Write delta file
    f2 = open(dir2fn, "r")
    sigfile = open("sig", "rb")
    deltafile = open("delta", "wb")
    librsync.filerdelta(sigfile, f2, deltafile)
    f2.close()
    sigfile.close()
    deltafile.close()

    # Write patched file
    f1 = open(dir1fn, "rb")
    newfile = open("%s/%s.out" % (dir1, i), "wb")
    deltafile = open("delta", "rb")
    librsync.filepatch(f1, deltafile, newfile)
    f1.close()
    deltafile.close()
    newfile.close()
