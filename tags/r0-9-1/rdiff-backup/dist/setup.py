#!/usr/bin/env python

import sys, os, getopt
from distutils.core import setup, Extension

version_string = "0.9.0"

if sys.version_info[:2] < (2,2):
	print "Sorry, rdiff-backup requires version 2.2 or later of python"
	sys.exit(1)

def install(cmd):
	if os.system("install " + cmd) != 0:
		print "Error running 'install %s'" % cmd
		sys.exit(1)

setup(name="rdiff-backup",
	  version=version_string,
	  description="Local/remote mirroring+incremental backup",
	  author="Ben Escoto",
	  author_email="bescoto@stanford.edu",
	  url="http://rdiff-backup.stanford.edu",
	  packages = ['rdiff_backup'],
	  ext_modules=[Extension("rdiff_backup.C", ["cmodule.c"])])

copy_files = 0
prefix = "/usr"
for arg in sys.argv[1:]: # check for "install" and --prefix= arg
	if arg == "install": copy_files = 1
	elif arg.startswith("--prefix="): prefix = arg[len("--prefix="):]

if copy_files:
	bindir = prefix + "/bin"
	print "Copying rdiff-backup to " + bindir
	install("-d " + bindir)
	install("-m0755 rdiff-backup " + bindir)

	mandir = prefix + "/share/man/man1"
	print "Copying rdiff-backup.1 to " + mandir
	install("-d " + mandir)
	install("-m0644 rdiff-backup.1 " + mandir)

	docdir = "%s/share/doc/rdiff-backup-%s" % (prefix, version_string)
	print ("Copying CHANGELOG, COPYING, README, and FAQ.html to " + docdir)
	install("-d " + docdir)
	install("-m0644 CHANGELOG COPYING README FAQ.html " + docdir)

