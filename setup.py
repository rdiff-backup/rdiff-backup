#!/usr/bin/env python3

import sys, os, getopt
from distutils.core import setup, Extension

version_string = "1.3.4"

if sys.version_info[:2] < (3,5):
	print("Sorry, rdiff-backup requires version 3.5 or later of Python")
	sys.exit(1)

# Defaults
lflags_arg = []
libname = ['rsync']
incdir_list = libdir_list = None
extra_options = {}

if os.name == 'posix' or os.name == 'nt':
	LIBRSYNC_DIR = os.environ.get('LIBRSYNC_DIR', '')
	LFLAGS = os.environ.get('LFLAGS', [])
	LIBS = os.environ.get('LIBS', [])

	# Handle --librsync-dir=[PATH] and --lflags=[FLAGS]
	args = sys.argv[:]
	for arg in args:
		if arg.startswith('--librsync-dir='):
			LIBRSYNC_DIR = arg.split('=')[1]
			sys.argv.remove(arg)
		elif arg.startswith('--lflags='):
			LFLAGS = arg.split('=')[1].split()
			sys.argv.remove(arg)
		elif arg.startswith('--libs='):
			LIBS = arg.split('=')[1].split()
			sys.argv.remove(arg)

		if LFLAGS or LIBS:
			lflags_arg = LFLAGS + LIBS

		if LIBRSYNC_DIR:
			incdir_list = [os.path.join(LIBRSYNC_DIR, 'include')]
			libdir_list = [os.path.join(LIBRSYNC_DIR, 'lib')]
		if '-lrsync' in LIBS:
			libname = []

if os.name == 'nt':
	try:
		import py2exe
	except ImportError:
		pass
	else:
		extra_options = {
			'console': ['rdiff-backup'],
		}
		if '--single-file' in sys.argv[1:]:
			sys.argv.remove('--single-file')
			extra_options.update({
				'options': {'py2exe': {'bundle_files': 1}},
				'zipfile': None
			})

setup(name="rdiff-backup",
	  version=version_string,
	  description="Local/remote mirroring+incremental backup",
	  author="The rdiff-backup project",
	  author_email="rdiff-backup-users@nongnu.org",
	  url="http://rdiff-backup.net/",
	  packages = ['rdiff_backup'],
	  package_dir={'':'src'},  # tell distutils packages are under src
	  ext_modules = [Extension("rdiff_backup.C", ["src/cmodule.c"]),
                         Extension("rdiff_backup._librsync", ["src/_librsyncmodule.c"],
                                           include_dirs=incdir_list,
                                           library_dirs=libdir_list,
                                           libraries=libname,
                                           extra_link_args=lflags_arg)],
	  scripts = ['rdiff-backup', 'rdiff-backup-statistics'],
	  data_files = [('share/man/man1', ['rdiff-backup.1', 'rdiff-backup-statistics.1']),
					('share/doc/rdiff-backup-%s' % (version_string,),
					 ['CHANGELOG', 'COPYING', 'README.md', 'FAQ-body.html'])],
					**extra_options) # FIXME improve FAQ.html vs. body
