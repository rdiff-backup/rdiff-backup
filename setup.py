#!/usr/bin/env python3

import sys
import os

from setuptools import setup, Extension

from src.rdiff_backup import Version

version_string = Version.version

# Defaults
lflags_arg = []
libname = ["rsync"]
incdir_list = libdir_list = None
extra_options = {}

if os.name == "posix" or os.name == "nt":
    LIBRSYNC_DIR = os.environ.get("LIBRSYNC_DIR", "")
    LFLAGS = os.environ.get("LFLAGS", [])
    LIBS = os.environ.get("LIBS", [])

    # Handle --librsync-dir=[PATH] and --lflags=[FLAGS]
    args = sys.argv[:]
    for arg in args:
        if arg.startswith("--librsync-dir="):
            LIBRSYNC_DIR = arg.split("=")[1]
            sys.argv.remove(arg)
        elif arg.startswith("--lflags="):
            LFLAGS = arg.split("=")[1].split()
            sys.argv.remove(arg)
        elif arg.startswith("--libs="):
            LIBS = arg.split("=")[1].split()
            sys.argv.remove(arg)

        if LFLAGS or LIBS:
            lflags_arg = LFLAGS + LIBS

        if LIBRSYNC_DIR:
            incdir_list = [os.path.join(LIBRSYNC_DIR, "include")]
            libdir_list = [os.path.join(LIBRSYNC_DIR, "lib")]
        if "-lrsync" in LIBS:
            libname = []

setup(
    name="rdiff-backup",
    version=version_string,
    description="Local/remote mirroring+incremental backup",
    author="The rdiff-backup project",
    author_email="rdiff-backup-users@nongnu.org",
    url="https://rdiff-backup.net/",
    python_requires='~=3.5',
    packages=["rdiff_backup"],
    package_dir={"": "src"},  # tell distutils packages are under src
    ext_modules=[
        Extension("rdiff_backup.C", ["src/cmodule.c"]),
        Extension(
            "rdiff_backup._librsync",
            ["src/_librsyncmodule.c"],
            include_dirs=incdir_list,
            library_dirs=libdir_list,
            libraries=libname,
            extra_link_args=lflags_arg,
        ),
    ],
    scripts=["src/rdiff-backup", "src/rdiff-backup-statistics"],
    data_files=[
        ("share/man/man1", ["docs/rdiff-backup.1", "docs/rdiff-backup-statistics.1"]),
        (
            "share/doc/rdiff-backup-%s" % (version_string,),
            [
                "CHANGELOG",
                "COPYING",
                "README.md",
                "docs/FAQ.md",
                "docs/examples.md",
                "docs/DEVELOP.md",
                "docs/Windows-README.md",
            ],
        ),
        ("share/bash-completion/completions", ["tools/bash-completion/rdiff-backup"]),
    ],
    **extra_options
)
