#!/usr/bin/env python3

# This script compiles and bundles together librsync and rdiff-backup

import sys
import os
import os.path
import shutil
import subprocess

def runCommand(*args):
    """Launch a command and abort if not successful.

    The first parameter must be the executable. Arguments must be
    passed as additional parameters."""
    a = subprocess.call(args)
    if a != 0:
        sys.stderr.write("The command gave an error:\n  %s\n" % " ".join(args))
        sys.exit(1)

# Compilation of librsync
os.chdir("librsync")
runCommand("cmake", "-DCMAKE_BUILD_TYPE=Release",
            "-DCMAKE_INSTALL_PREFIX=../librsync-bin")
runCommand("make")
runCommand("make", "install")
os.chdir("..")
# Build of rdiff-backup
runCommand(sys.executable, os.path.join(".", "setup.py"),
           "--librsync-dir=librsync-bin", "build")
# TODO
