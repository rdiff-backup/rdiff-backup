#!/usr/bin/env python

import sys, os

__doc__ = """

This starts an rdiff-backup server using the existing source files.
If not run from the source directory, the only argument should be 
the directory the source files are in.
"""

def Test_SetConnGlobals(conn, setting, value):
	"""This is used in connectiontest.py"""
	conn.Globals.set(setting, value)

def print_usage():
	print "Usage: server.py  [path to source files]", __doc__

if len(sys.argv) > 2:
	print_usage()
	sys.exit(1)

try:
	if len(sys.argv) == 2: sys.path.insert(0, sys.argv[1])
	import rdiff_backup.Globals
	from rdiff_backup.connection import *
except (OSError, IOError, ImportError):
	print_usage()
	raise

#Log.setverbosity(9)
PipeConnection(sys.stdin, sys.stdout).Server()
