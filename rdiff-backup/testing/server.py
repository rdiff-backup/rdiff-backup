#!/usr/bin/env python

import sys
execfile("commontest.py")
rbexec("setconnections.py")

def Test_SetConnGlobals(conn, name, val):
	"""Used in unittesting - set one of specified connection's Global vars"""
	conn.Globals.set(name, val)

Log.setverbosity(9)
PipeConnection(sys.stdin, sys.stdout).Server()
