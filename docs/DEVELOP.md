# Development Guide for rdiff-backup

Some notes for developers and other people willing to help development,
or simply compile rdiff-backup from source code.


## PRE-REQUISITES

The same pre-requisites as for the installation of rdiff-backup are
required as well:

* Python 3.5 or higher
* librsync 1.0.0 or higher
* pylibacl (optional, to support ACLs)
* pyxattr (optional, to support extended attributes)

Additionally are following pre-requisites needed:

* python3-dev (or -devel)
* librsync-dev (or -devel)
* a C compiler (gcc)
* python3-setuptools (for setup.py)
* setuptools-scm (also for setup.py, to gather all source files in sdist)
* libacl-devel (for sys/acl.h)
* tox (for testing)
* rdiff (for testing)

All of those should come packaged with your system or available from 
https://pypi.org/ but if you need them otherwise, here are some sources:

* Python - https://www.python.org/
* Librsync - http://librsync.sourceforge.net/
* Pywin32 - https://github.com/mhammond/pywin32
* Pylibacl - http://pylibacl.sourceforge.net/
* Pyxattr - http://pyxattr.sourceforge.net/


## BUILD AND INSTALL

Once you have fulfilled all pre-requisites, you can just clone the git repo
with the source code:

	git clone git@github.com:rdiff-backup/rdiff-backup.git

> **NOTE:** if you plan to provide your own code, you should first fork
our repo and clone your own forked repo. How is described at
https://help.github.com/en/github/collaborating-with-issues-and-pull-requests/working-with-forks

To install, simply run:

	python3 setup.py install

The build process can be also be run separately:

	python3 setup.py build

The setup script expects to find librsync headers and libraries in the
default location, usually /usr/include and /usr/lib.  If you want the
setup script to check different locations, use the --librsync-dir
switch or the LIBRSYNC_DIR environment variable.  For instance,

	python3 setup.py --librsync-dir=/usr/local build

instructs the setup program to look in `/usr/local/include` and
`/usr/local/lib` for the librsync files.

Finally, the `--lflags` and `--libs` options, and the `LFLAGS` and `LIBS`
environment variables are also recognized.  Running setup.py with no
arguments will display some help. Additional help is displayed by the
command:

	python3 setup.py install --help

More information about using setup.py and how rdiff-backup is installed
is available from the Python guide, Installing Python Modules for System
Administrators, located at https://docs.python.org/3/install/index.html

> **NOTE:** There is no uninstall command provided by the Python
distutils/setuptools system. One strategy is to use the `python3 setup.py
install --record <file>` option to save a list of the files installed to <file>,
another is to created a wheel package with `python3 setup.py bdist_wheel`,
as it can be installed and deinstalled.

> **NOTE:** if you plan to use `./setup.py bdist_rpm` to create an RPM, you would need rpm-build but be aware that it will currently fail due to a [known bug in setuptools with compressed man pages](https://github.com/pypa/setuptools/issues/1277).

To build from source on Windows, check the [Windows tools](../tools/windows)
to build a single executable file which contains Python, librsync, and
all required modules.


## TESTING

Clone, unpack and prepare the testfiles by calling the script `tools/setup-testfiles.sh`
from the cloned source Git repo. You will most probably be asked for your password
so that sudo can extract and prepare the testfiles (else the tests will fail).

That's it, you can now run the tests:

* run `tox` to use the default `tox.ini`
* or `tox -c tox_slow.ini` for long tests
* or `sudo tox -c tox_root.ini` for the few tests needing root rights

You might want to use the available `Dockerfile` and it's corresponding `Makefile`
to do the tests in a container, leaving your own environment alone.


## DEBUGGING

### Trace back a coredump

As I write those notes, I have an issue where calling the program generates a `Segmentation fault (core dumped)`. This chapter is based on this experience debugging under Fedora 29.

References:

* https://ask.fedoraproject.org/en/question/98776/where-is-core-dump-located/
* Adventures in Python core dumping: https://gist.github.com/toolness/d56c1aab317377d5d17a
* Debugging dynamically loaded extensions: https://www.oreilly.com/library/view/python-cookbook/0596001673/ch16s08.html
* Debugging Memory Problems: https://www.oreilly.com/library/view/python-cookbook/0596001673/ch16s09.html

> **NOTE:** I assume gdb was already installed.

sudo dnf install python3-debug
sudo dnf debuginfo-install python3-debug-3.7.3-1.fc29.x86_64 #<1>
sudo dnf debuginfo-install bzip2-libs-1.0.6-28.fc29.x86_64 glibc-2.28-27.fc29.x86_64 \
	librsync-1.0.0-8.fc29.x86_64 libxcrypt-4.4.4-2.fc29.x86_64 \
	openssl-libs-1.1.1b-3.fc29.x86_64 popt-1.16-15.fc29.x86_64 \
	sssd-client-2.1.0-2.fc29.x86_64 xz-libs-5.2.4-3.fc29.x86_64 zlib-1.2.11-14.fc29.x86_64

1. see below for the purpose of this and the following lines

Then calling:

	python3 ./setup.py clean --all  #<1>
	python3-debug ./setup.py clean --all
	CFLAGS='-Wall -O0 -g' python3-debug ./setup.py build  #<2>
	PATH=$PWD/build/scripts-3.7:$PATH PYTHONPATH=$PWD/build/lib.linux-x86_64-3.7-pydebug/ rdiff-backup -v 10 \
		/some/dir1 /some/dir2
	[...]
	Segmentation fault (core dumped)

1. just to be sure
2. the CFLAGS avoids optimizations making debugging more complicated

At this stage `coredumpctl list` shows me that my coredump is the last one, so that I can
call `coredumpctl gdb`, which itself tells me (in multiple steps) that I'm missing some
more debug information, hence the above `debuginfo-install` statements (I guess you could install
the packages without version information if you're sure they fit the installed package versions).

So now back into `coredumpctl gdb`, with some commands because I'm no gdb specialist:

	help
	help stack
	backtrace  #<1>
	bt full    #<2>
	py-bt      #<3>
	frame <FrameNumber>   #<4>
	p <SomeVar> #<5>

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

	$ PYTHONTRACEMALLOC=1 PATH=$PWD/build/scripts-3.7:$PATH PYTHONPATH=$PWD/build/lib.linux-x86_64-3.7-pydebug/ gdb python3-debug
	(gdb) break rdiff_backup/_librsyncmodule.c:_librsync_new_patchmaker
	(gdb) run build/scripts-3.7/rdiff-backup /some/source/dir /some/target/dir

The debugger runs until the breakpoint is reached, after which a succession of `next` and `print <SomeVar>` allows me to analyze the code step by step, and to come to the conclusion that my
quickly `cfile = fdopen(python_fd, ...` is somehow wrong as it creates a null file pointer
whereas `python_fd` looks like a valid file descriptor (an integer equal to 5).

### ResourceWarning unclosed file

If you get something looking like a `ResourceWarning: Enable tracemalloc to get the object allocation traceback`

	PYTHONTRACEMALLOC=1 PATH=$PWD/build/scripts-3.7:$PATH \
	PYTHONPATH=$PWD/build/lib.linux-x86_64-3.7-pydebug/ \
		rdiff-backup -v 10 /tmp/äłtèr /var/tmp/rdiff

This tells you indeed where the file was opened: `Object allocated at (most recent call last)` but it still requires deeper analysis to understand the reason.

> **Reference:** https://docs.python.org/3/library/tracemalloc.html

### Debug client / server mode

In order to make sure the debug messages are properly sorted, you need to have the verbosity
level 9 set-up, mix stdout and stderr, and then use the date/time output to properly sort
the lines coming both from server and client, while making sure that lines belonging together
stay together. The result command line might look as follows:

	rdiff-backup -v9 localhost::/sourcedir /backupdir 2>&1 | awk \
		'/^2019-09-16/ { if (line) print line; line = $0 } ! /^2019-09-16/ { line = line " ## " $0 }' \
		| sort | sed 's/ ## /\n/g'
