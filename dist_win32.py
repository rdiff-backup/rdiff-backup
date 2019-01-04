#!/usr/bin/env python

# This script compiles and bundles together librsync and rdiff-backup

import sys
import os
import os.path
import subprocess
import zipfile

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
runCommand("nmake")
runCommand("nmake", "install")
os.chdir("..")
# Build of rdiff-backup
os.chdir("rdiff-backup")
runCommand(sys.executable, os.path.join(".", "dist", "makedist"), "--no-tar",
           version)
os.chdir("rdiff-backup-%s" % version)
if "VS90COMNTOOLS" not in os.environ:
    if "VCINSTALLDIR" not in os.environ:
        sys.stderr.write("Need either the VS90COMNTOOLS or VCINSTALLDIR "
                         "environment variable.\n")
        sys.exit(1)
    os.putenv("VS90COMNTOOLS", os.path.join(os.environ["VCINSTALLDIR"], "bin"))
os.putenv("LIBRSYNC_DIR", os.path.join("..", "..", "librsync-bin"))
runCommand(sys.executable, "setup.py", "build")
runCommand(sys.executable, "setup.py", "py2exe", "--single-file")
# Packaging of rdiff-backup
with zipfile.ZipFile(os.path.join("..", "..", "rdiff-backup-%s.zip" % version),
                     "w", zipfile.ZIP_DEFLATED) as z:
    # All files in dist\
    for f in os.listdir("dist"):
        fWithPath = os.path.join("dist", f)
        if os.path.isfile(fWithPath):
            z.write(fWithPath, f)
    # All files under dist\share\doc without path information
    for dirpath, dirnames, filenames in os.walk(os.path.join("dist", "share",
                                                             "doc")):
        for f in filenames:
            z.write(os.path.join(dirpath, f), f) # Forget about path
