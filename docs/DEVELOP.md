# Development Guide for rdiff-backup

Some notes for developers and other people willing to help development.

## INSTALLATION FROM SOURCE CODE

Thank you for trying rdiff-backup.  To install, run:

	python3 setup.py install

The build process can be also be run separately:

	python3 setup.py build

The default prefix is generally /usr, so files would be put in /usr/bin,
/usr/share/man/, etc.  An alternate prefix can be specified using the
--prefix=<prefix> option.  For example:

	python3 setup.py install --prefix=/usr/local

The default prefix depends on how you (or your distribution) installed and
configured Python. Suggested reading is "How installation works" from the
Python docs, which includes commands to determine your default prefix:
https://docs.python.org/3/install/index.html#how-installation-works

The setup script expects to find librsync headers and libraries in the
default location, usually /usr/include and /usr/lib.  If you want the
setup script to check different locations, use the --librsync-dir
switch or the LIBRSYNC_DIR environment variable.  For instance,

	python3 setup.py --librsync-dir=/usr/local build

instructs the setup program to look in /usr/local/include and
/usr/local/lib for the librsync files.

Finally, the --lflags and --libs options, and the LFLAGS and LIBS
environment variables are also recognized.  Running setup.py with no
arguments will display some help. Additional help is displayed by the
command:

	python3 setup.py install --help

More information about using setup.py and how rdiff-backup is installed
is available from the Python guide, Installing Python Modules for System
Administrators, located at https://docs.python.org/3/install/index.html

NB: There is no uninstall command provided by the Python distutils system.
One strategy is to use the python3 setup.py install --record <file> option
to save a list of the files installed to <file>.

To build from source on Windows, check the [Windows tools](tools/windows)
to build a single executable file which contains Python, librsync, and
all required modules.

 Pylibacl and pyxattr can be
downloaded from http://pylibacl.sourceforge.net/ and
http://pyxattr.sourceforge.net/. Mac OS X users need a different
pyxattr module, which can be downloaded from
https://pypi.org/project/xattr/

### REQUIREMENTS

Remember that you must have Python 3.5 or later and librsync 1.0.0 or
later installed.  For Python, see https://www.python.org/.  The
rdiff-backup homepage at https://rdiff-backup.net/ should
have a recent version of librsync; otherwise see the librsync homepage
at http://librsync.sourceforge.net/. On Windows, you must have the
Python for Windows extensions installed if you are building from source.
The extensions can be downloaded from: https://github.com/mhammond/pywin32
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
https://pypi.org/project/xattr/

In order to build rdiff-backup, you need python3-devel and librsync-devel, as
well as a C compiler (gcc).


## Testing rdiff-backup

* Install:
    * tox
    * libacl-devel (for sys/acl.h)
    * rdiff
    * python3-setuptools (for setup.py)
    * setuptools-scm (also for setup.py, to gather all source files in sdist)
* unpack the test files previously available from
https://download-mirror.savannah.gnu.org/releases/rdiff-backup/testfiles.tar.gz and now temporarily available as
release under https://github.com/ericzolf/rdiff-backup/releases[]:
    * The extraction as root (e.g. `sudo tar xvzf rdiff-backup_testfiles_ISORELEASEDATE.tar.gz`) is sadly necessary
because else the device files won't be extracted as normal user. This needs to happen in the _parent_ directory
of the Git directory.
    * You then possibly need to fix (again as root) the access rights so that the user/group you're using normally in your
daily development life is set instead of my user and group with ID 1000. For this you may use the helper script
provided in the archive and call `sudo ./rdiff-backup_testfiles.fix.sh`.

That's it, you can now run the tests:

* run `tox` to use the default `tox.ini`
* or `tox -c tox_slow.ini` for long tests
* or `sudo tox -c tox_root.ini` for the few tests needing root rights

> **NOTE:** if you plan to use `./setup.py bdist_rpm` to create an RPM, you would need rpm-build but be aware that it will currently fail due to a [known bug in setuptools with compressed man pages](https://github.com/pypa/setuptools/issues/1277).

## How to debug rdiff-backup?

### Trace back a coredump

As I write those notes, I have an issue where calling the program generates a `Segmentation fault (core dumped)`. At this stage, this document is just some notes taken as I'm trying to debug this problem under Fedora (29).

References:

* https://ask.fedoraproject.org/en/question/98776/where-is-core-dump-located/
* Adventures in Python core dumping: https://gist.github.com/toolness/d56c1aab317377d5d17a
* Debugging dynamically loaded extensions: https://www.oreilly.com/library/view/python-cookbook/0596001673/ch16s08.html
* Debugging Memory Problems: https://www.oreilly.com/library/view/python-cookbook/0596001673/ch16s09.html

NOTE: I assume gdb was already installed.

```
sudo dnf install python3-debug
sudo dnf debuginfo-install python3-debug-3.7.3-1.fc29.x86_64 #<1>
sudo dnf debuginfo-install bzip2-libs-1.0.6-28.fc29.x86_64 glibc-2.28-27.fc29.x86_64 \
	librsync-1.0.0-8.fc29.x86_64 libxcrypt-4.4.4-2.fc29.x86_64 \
	openssl-libs-1.1.1b-3.fc29.x86_64 popt-1.16-15.fc29.x86_64 \
	sssd-client-2.1.0-2.fc29.x86_64 xz-libs-5.2.4-3.fc29.x86_64 zlib-1.2.11-14.fc29.x86_64
```

1. see below for the purpose of this and the following lines

Then calling:

```
python3 ./setup.py clean --all  #<1>
python3-debug ./setup.py clean --all
CFLAGS='-Wall -O0 -g' python3-debug ./setup.py build  #<2>
PATH=$PWD/build/scripts-3.7:$PATH PYTHONPATH=$PWD/build/lib.linux-x86_64-3.7-pydebug/ rdiff-backup -v 10 \
	/some/dir1 /some/dir2
[...]
Segmentation fault (core dumped)
```

1. just to be sure
2. the CFLAGS avoids optimizations making debugging more complicated

At this stage `coredumpctl list` shows me that my coredump is the last one, so that I can
call `coredumpctl gdb`, which itself tells me (in multiple steps) that I'm missing some
more debug information, hence the above `debuginfo-install` statements (I guess you could install
the packages without version information if you're sure they fit the installed package versions).

So now back into `coredumpctl gdb`, with some commands because I'm no gdb specialist:

```
help
help stack
backtrace  #<1>
bt full    #<2>
py-bt      #<3>
frame <FrameNumber>   #<4>
p <SomeVar> #<5>
```
1. get a backtrace of all function calls leading to the coredump (also `bt`)
2. backtrace with local vars
3. py-bt is the Python version of backtrace
4. jump between frames as listed by bt using their `#FrameNumber`
5. print some variable/expression in the context of the selected frame

Jumping between frames and printing the different variables, we can recognize that:

1. the core dump is due to a seek on a null file pointer
2. that the file pointer comes from the job pointer handed over to the function rs_job_iter
3. the job pointer itself comes from the self variable handed over to _librsync_patchmaker_cycle
4. reading through the https://librsync.github.io/rdiff.html[librsync documentation], it appears that the job type is opaque, i.e. I can't directly influence and it has been created via the `rs_patch_begin` function within the function `_librsync_new_patchmaker` in `rdiff_backup/_librsyncmodule.c`.

At this stage, it seems to me that the core file has given most of its secrets and I need to debug the live program:

```
$ PYTHONTRACEMALLOC=1 PATH=$PWD/build/scripts-3.7:$PATH PYTHONPATH=$PWD/build/lib.linux-x86_64-3.7-pydebug/ gdb python3-debug
(gdb) break rdiff_backup/_librsyncmodule.c:_librsync_new_patchmaker
(gdb) run build/scripts-3.7/rdiff-backup /some/source/dir /some/target/dir
```

The debugger runs until the breakpoint is reached, after which a succession of `next` and `print <SomeVar>` allows me to analyze the code step by step, and to come to the conclusion that my
quickly `cfile = fdopen(python_fd, ...` is somehow wrong as it creates a null file pointer
whereas python_fd looks like a valid file descriptor (an integer equal to 5).

### ResourceWarning unclosed file

```
/home/ericl/Public/rdiff-backup/build/lib.linux-x86_64-3.7-pydebug/rdiff_backup/robust.py:32: ResourceWarning: unclosed file <_io.BufferedReader name='/var/tmp/rdiff/rdiff-backup-data/increments/bla.2019-04-20T11:59:45+02:00.diff.gz'>
  try: return function(*args)
ResourceWarning: Enable tracemalloc to get the object allocation traceback

/home/ericl/Public/rdiff-backup/build/lib.linux-x86_64-3.7-pydebug/rdiff_backup/rorpiter.py:99: ResourceWarning: unclosed file <_io.BufferedReader name='/var/tmp/rdiff/rdiff-backup-data/mirror_metadata.2019-04-20T11:59:45+02:00.snapshot.gz'>
  try: relem2 = next(riter2)
ResourceWarning: Enable tracemalloc to get the object allocation traceback

/home/ericl/Public/rdiff-backup/build/lib.linux-x86_64-3.7-pydebug/rdiff_backup/robust.py:32: ResourceWarning: unclosed file <_io.BufferedReader name='/var/tmp/rdiff/bla'>
  try: return function(*args)
ResourceWarning: Enable tracemalloc to get the object allocation traceback

/home/ericl/Public/rdiff-backup/build/lib.linux-x86_64-3.7-pydebug/rdiff_backup/rpath.py:1202: ResourceWarning: unclosed file <_io.BufferedWriter name='/var/tmp/rdiff/rdiff-backup-data/increments/bla.2019-04-20T11:59:45+02:00.diff.gz'>
  if outfp.close(): raise RPathException("Error closing file")
ResourceWarning: Enable tracemalloc to get the object allocation traceback
```

> **Reference:** https://docs.python.org/3/library/tracemalloc.html

```
PYTHONTRACEMALLOC=1 PATH=$PWD/build/scripts-3.7:$PATH PYTHONPATH=$PWD/build/lib.linux-x86_64-3.7-pydebug/ \
	rdiff-backup -v 10 /tmp/äłtèr /var/tmp/rdiff
```

This tells you indeed where the file was opened: `Object allocated at (most recent call last)` but it didn't really help me get rid of the warning, hence https://github.com/ericzolf/rdiff-backup/issues/18 until further notice.

### Debug client / server mode

In order to make sure the debug messages are properly sorted, you need to have the verbosity
level 9 set-up, mix stdout and stderr, and then use the date/time output to properly sort
the lines coming both from server and client, while making sure that lines belonging together
stay together. The result command line might look as follows:

```
rdiff-backup -v9 localhost::/sourcedir /backupdir 2>&1 | awk \
	'/^2019-09-16/ { if (line) print line; line = $0 } ! /^2019-09-16/ { line = line " ## " $0 }' \
	| sort | sed 's/ ## /\n/g'
```
