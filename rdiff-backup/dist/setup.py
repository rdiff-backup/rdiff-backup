#!/usr/bin/env python

import sys
from distutils.core import setup, Extension

if sys.version_info[:2] < (2,2):
	print "Sorry, rdiff-backup requires version 2.2 or later of python"
	sys.exit(1)

setup(name="rdiff-backup",
	  version="0.9.0",
	  description="Local/remote mirroring+incremental backup",
	  author="Ben Escoto",
	  author_email="bescoto@stanford.edu",
	  url="http://rdiff-backup.stanford.edu",
	  packages = ['rdiff_backup'],
	  ext_modules=[Extension("rdiff_backup.C", ["cmodule.c"])])

