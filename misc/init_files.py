#!/usr/bin/env python3
"""init_smallfiles.py

This program makes a number of files of the given size in the
specified directory.

"""

import os
import sys
import math


if len(sys.argv) > 5 or len(sys.argv) < 4:
    print("Usage: init_files [directory name] [file size] [file count] [base]")
    print()
    print("Creates file_count files in directory_name of size file_size.")
    print("The created directory has a tree type structure where each level")
    print("has at most base files or directories in it.  Default is 50.")
    sys.exit(1)


dirname = sys.argv[1]
filesize = int(sys.argv[2])
filecount = int(sys.argv[3])
block_size = 16384
block = "." * block_size
block_change = "." * (filesize % block_size)
if len(sys.argv) == 4:
    base = 50
else:
    base = int(sys.argv[4])


def make_file(path):
    """Make the file at path"""
    fp = open(path, "w")
    for i in range(int(math.floor(filesize / block_size))):
        fp.write(block)
    fp.write(block_change)
    fp.close()


def find_sublevels(count):
    """Return number of sublevels required for count files"""
    return int(math.ceil(math.log(count) / math.log(base)))


def make_dir(dir, count):
    """Make count files in the directory, making subdirectories if necessary"""
    print("Making directory %s with %d files" % (dir, count))
    os.mkdir(dir)
    level = find_sublevels(count)
    assert count <= pow(base, level)
    if level == 1:
        for i in range(count):
            make_file(os.path.join(dir, "file%d" % i))
    else:
        files_per_subdir = pow(base, level - 1)
        full_dirs = int(count / files_per_subdir)
        assert full_dirs <= base
        for i in range(full_dirs):
            make_dir(os.path.join(dir, "subdir%d" % i), files_per_subdir)

        change = count - full_dirs * files_per_subdir
        assert change >= 0
        if change > 0:
            make_dir(os.path.join(dir, "subdir%d" % full_dirs), change)


def start(dir):
    try:
        os.stat(dir)
    except os.error:
        pass
    else:
        print("Directory %s already exists, exiting." % dir)
        sys.exit(1)

    make_dir(dirname, filecount)


start(dirname)
