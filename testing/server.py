#!/usr/bin/env python3

import sys

__doc__ = """

This starts an rdiff-backup server using the existing source files.
If not run from the source directory, the only argument should be
the directory the source files are in.
"""


def print_usage():
    print("Usage: server.py  [path to source files]", __doc__)


if len(sys.argv) > 2:
    print_usage()
    sys.exit(1)

try:
    if len(sys.argv) == 2:
        sys.path.insert(0, sys.argv[1])
    from rdiff_backup import connection, Security
except (OSError, ImportError):
    print_usage()
    raise

Security._security_level = "override"
sys.exit(connection.PipeConnection(sys.stdin.buffer, sys.stdout.buffer).Server())
