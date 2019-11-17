#!/usr/bin/env python3
"""Make 10000 files consisting of data

Syntax:  test.py directory_name number_of_files character filelength"""

import sys
import os

dirname = sys.argv[1]
num_files = int(sys.argv[2])
character = sys.argv[3]
filelength = int(sys.argv[4])

os.mkdir(dirname)
for i in range(num_files):
    fp = open("%s/%s" % (dirname, i), "w")
    fp.write(character * filelength)
    fp.close()

fp = open("%s.big" % dirname, "w")
fp.write(character * (filelength * num_files))
fp.close()
