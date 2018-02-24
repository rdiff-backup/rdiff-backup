INSTALLATION:

Thank you for trying rdiff-backup.  To install, run:

	python setup.py install

The build process can be also be run separately:

	python setup.py build

The default prefix is generally /usr, so files would be put in /usr/bin,
/usr/share/man/, etc.  An alternate prefix can be specified using the
--prefix=<prefix> option.  For example:

	python setup.py install --prefix=/usr/local

The default prefix depends on how you (or your distribution) installed and
configured Python. Suggested reading is "How installation works" from the
Python docs, which includes commands to determine your default prefix:
http://docs.python.org/install/index.html#how-installation-works

The setup script expects to find librsync headers and libraries in the
default location, usually /usr/include and /usr/lib.  If you want the
setup script to check different locations, use the --librsync-dir
switch or the LIBRSYNC_DIR environment variable.  For instance,

	python setup.py --librsync-dir=/usr/local build

instructs the setup program to look in /usr/local/include and
/usr/local/lib for the librsync files.

Finally, the --lflags and --libs options, and the LFLAGS and LIBS
environment variables are also recognized.  Running setup.py with no
arguments will display some help. Additional help is displayed by the
command:

	python setup.py install --help

More information about using setup.py and how rdiff-backup is installed
is available from the Python guide, Installing Python Modules for System
Administrators, located at http://docs.python.org/install/index.html

NB: There is no uninstall command provided by the Python distutils system.
One strategy is to use the python setup.py install --record <file> option
to save a list of the files installed to <file>.

To build from source on Windows, you can use the command:

	python setup.py py2exe --single-file

to build a single executable file which contains Python, librsync, and
all required modules.

REQUIREMENTS:

Remember that you must have Python 2.2 or later and librsync 0.9.7 or
later installed.  For Python, see http://www.python.org.  The
rdiff-backup homepage at http://rdiff-backup.nongnu.org/ should
have a recent version of librsync; otherwise see the librsync homepage
at http://librsync.sourceforge.net/. On Windows, you must have the
Python for Windows extensions installed if you are building from source.
The extensions can be downloaded from: http://pywin32.sourceforge.net/
If you are not building from source on Windows, you do not need Python
or librsync; they are bundled with the executable.

For remote operation, rdiff-backup should be installed and in the
PATH on remote system(s) (see man page for more information). On
Windows, if you are using the provided .exe binary, you must have an
SSH package installed for remote operation.

The python modules pylibacl and pyxattr are optional.  If they are
installed and in the default pythonpath, rdiff-backup will support
access control lists and user extended attributes, provided the file
system(s) also support these features.  Pylibacl and pyxattr can be
downloaded from http://pylibacl.sourceforge.net/ and
http://pyxattr.sourceforge.net/. Mac OS X users need a different
pyxattr module, which can be downloaded from
http://cheeseshop.python.org/pypi/xattr

If you want to use rdiff-backup-statistics, you must have Python 2.4
or later.

TROUBLESHOOTING:

If you have everything installed properly, and it still doesn't work,
see the enclosed FAQ.html, the web page at http://rdiff-backup.nongnu.org,
the Wiki at: http://wiki.rdiff-backup.org, and/or the mailing list.

The FAQ in particular is an important reference, especially if you are
using smbfs/CIFS, Windows, or have compiled by hand on Mac OS X.
