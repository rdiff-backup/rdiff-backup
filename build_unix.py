#!/usr/bin/env python

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

if len(sys.argv) != 2:
    sys.stderr.write("Usage: %s version\n" % sys.argv[0])
    sys.exit(1)
version = sys.argv[1]
# Compilation of librsync
os.chdir("librsync")
runCommand("cmake", "-DCMAKE_BUILD_TYPE=Release",
            "-DCMAKE_INSTALL_PREFIX=../librsync-bin")
runCommand("make")
runCommand("make", "install")
os.chdir("..")
# Build of rdiff-backup
os.chdir("rdiff-backup")
runCommand(sys.executable, os.path.join(".", "dist", "makedist"), "--no-tar",
           version)
versionedDir = "rdiff-backup-%s" % version
shutil.move(versionedDir, os.path.join(".."))
os.chdir(os.path.join("..", versionedDir))
runCommand(sys.executable, "setup.py", "build")

print ("\n\nrdiff-backup is now ready to be installed from directory\n  %s\n"
       "with command\n  ./setup.py install\n" % os.getcwd())
