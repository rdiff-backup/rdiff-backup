#!/usr/bin/env python

import sys, os, getopt
from distutils.core import setup, Extension

version_string = "$version"

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
	  ext_modules = [Extension("rdiff_backup.C", ["cmodule.c"]),
					 Extension("rdiff_backup._librsync",
							   ["_librsyncmodule.c"],
							   libraries=["rsync"])],
	  scripts = ['rdiff-backup'],
	  data_files = [('share/man/man1', ['rdiff-backup.1']),
					('share/doc/rdiff-backup-%s' % version_string,
					 ['CHANGELOG', 'COPYING', 'README', 'FAQ.html'])])



