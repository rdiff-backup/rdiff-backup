#!/usr/bin/env python

import sys, os, getopt
from distutils.core import setup, Extension

version_string = "0.9.0"

if sys.version_info[:2] < (2,2):
	print "Sorry, rdiff-backup requires version 2.2 or later of python"
	sys.exit(1)


setup(name="rdiff-backup",
	  version=version_string,
	  description="Local/remote mirroring+incremental backup",
	  author="Ben Escoto",
	  author_email="bescoto@stanford.edu",
	  url="http://rdiff-backup.stanford.edu",
	  packages = ['rdiff_backup'],
	  ext_modules=[Extension("rdiff_backup.C", ["cmodule.c"])])

install = 0
prefix = "/usr"
for arg in sys.argv[1:]: # check for "install" and --prefix arg
	if arg == "install": install = 1
	elif arg.startswith("--prefix="):
		prefix = arg[len("--prefix="):]

if install:
	print "Copying rdiff-backup to %s/bin" % prefix
	assert not os.system("install -D -m0755 rdiff-backup "
						 "%s/bin/rdiff-backup" % prefix)
	print "Copying rdiff-backup.1 to %s/share/man/man1" % prefix
	assert not os.system("install -D -m0644 rdiff-backup.1 "
						 "%s/share/man/man1/rdiff-backup" % prefix)
	print ("Copying CHANGELOG, COPYING, README, and FAQ.html to "
		   "%s/share/doc/rdiff-backup-%s" % (prefix, version_string))
	assert not os.system("install -d %s/share/doc/rdiff-backup-%s" %
						 (prefix, version_string))
	assert not os.system("install -m0644 CHANGELOG COPYING README FAQ.html "
						 "%s/share/doc/rdiff-backup-%s" %
						 (prefix, version_string))
