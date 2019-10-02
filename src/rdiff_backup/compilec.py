#!/usr/bin/env python3

import sys
import os
from distutils.core import setup, Extension

assert len(sys.argv) == 1
sys.argv.append("build")

setup(
    name="CModule",
    version="0.9.0",
    description="rdiff-backup's C component",
    ext_modules=[
        Extension("C", ["cmodule.c"]),
        Extension("_librsync", ["_librsyncmodule.c"], libraries=["rsync"])
    ])


def get_libraries():
    """Return filename of C.so and _librsync.so files"""
    build_files = os.listdir("build")
    lib_dirs = [x for x in build_files if x.startswith("lib")]
    assert len(lib_dirs) == 1, "No library directory or too many"
    libdir = lib_dirs[0]
    if sys.platform == "cygwin" or os.name == "nt":
        libext = "dll"
    else:
        libext = "so"
    clib = os.path.join("build", libdir, "C." + libext)
    rsynclib = os.path.join("build", libdir, "_librsync." + libext)
    try:
        os.lstat(clib)
        os.lstat(rsynclib)
    except os.error:
        print("Library file missing")
        sys.exit(1)
    return clib, rsynclib


for filename in get_libraries():
    assert not os.system("mv '%s' ." % (filename, ))
assert not os.system("rm -rf build")
