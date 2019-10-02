#!/usr/bin/env python

# This script compiles and bundles together librsync and rdiff-backup

import sys
import os
import os.path
import subprocess
import zipfile
import PyInstaller.__main__

def runCommand(*args):
    """Launch a command and abort if not successful.

    The first parameter must be the executable. Arguments must be
    passed as additional parameters."""
    a = subprocess.call(args)
    if a != 0:
        sys.stderr.write("The command gave an error:\n  %s\n" % " ".join(args))
        sys.exit(1)

if "--help" in sys.argv:
    sys.stderr.write("Usage: %s [version]\n" % sys.argv[0])
    sys.exit(1)
if len(sys.argv) > 1:
    version = sys.argv[1]
else:
    from src.rdiff_backup.Version import version
# Compilation of librsync
os.chdir("librsync")
runCommand("cmake", "-DCMAKE_INSTALL_PREFIX=../librsync-bin", "-A", "Win32", ".")
runCommand("cmake", "--build", ".", "--config", "Release")
runCommand("cmake", "--install", ".", "--config", "Release")
os.chdir("..")
# Build of rdiff-backup
# runCommand(sys.executable, os.path.join(".", "dist", "makedist"), "--no-tar",
#           version)
# os.chdir("rdiff-backup-%s" % version)
if "VS160COMNTOOLS" not in os.environ:
    sys.stderr.write("VS160COMNTOOLS environment variable not set.\n")
    sys.exit(1)
os.putenv("LIBRSYNC_DIR", "librsync-bin")
runCommand(sys.executable, "setup.py", "build")
PyInstaller.__main__.run(["--onefile",
                          "--distpath=%s" % os.path.join("dist", "win32"),
                          "--onefile",
                          "--paths=%s" % os.path.join("build", "lib.win32-3.7"),
                          "--paths=%s" % os.path.join("librsync-bin", "bin"),
                          "--console", "rdiff-backup"])

# Packaging of rdiff-backup
with zipfile.ZipFile("rdiff-backup-%s.zip" % version, "w",
                     zipfile.ZIP_DEFLATED) as z:
    # All files under directory dist
    for f in os.listdir(os.path.join("dist", "win32")):
        fWithPath = os.path.join("dist", "win32", f)
        if os.path.isfile(fWithPath):
            z.write(fWithPath, f)
    # Doc files (list taken from setup.py)
    for f in ['CHANGELOG', 'COPYING', 'README.md', 'FAQ-body.html']:
        z.write(f, f)
