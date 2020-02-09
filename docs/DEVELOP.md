# Development Guide for rdiff-backup

> Suggest [improvements to this documentation](https://github.com/rdiff-backup/rdiff-backup/issues/new?title=Docs%20feedback:%20/docs/DEVELOP.md)!


## GETTING THE SOURCE

Simply clone the source with:

	git clone https://github.com/rdiff-backup/rdiff-backup.git

> **NOTE:** If you plan to provide your own code, you should first fork
our repo and clone your own forked repo. How is described at
https://help.github.com/en/github/collaborating-with-issues-and-pull-requests/working-with-forks


## GENERAL GUIDELINES

- Before committing to a lot of writing or coding, please file an issue on Github and discuss your plans and gather feedback. Eventually it will be much easier to merge your change request if the idea and design has been agreed upon, and there will be less work for you as a contributor if you implement your idea along the correct lines to begin with.
- Please check out [existing issues](https://github.com/rdiff-backup/rdiff-backup/issues) and [existing merge requests](https://github.com/rdiff-backup/rdiff-backup/pulls) and browse the [git history](https://github.com/rdiff-backup/rdiff-backup/commits/master) to see if somebody already tried to address the thing you have are interested in. It might provide useful insight why the current state is as it is.
- Changes can be submitted using the typical Github workflow: clone this repository, make your changes, test and verify, and submit a Pull Request.
- Each change (= pull request) should focus on some topic and resist changing anything else. Keeping the scope clear also makes it easier to review the pull request. A good pull request has only one or a few commits, with each commit having a good commit subject and if needed also a body that explains the change.
- For all code changes, please remember also to include inline comments and update tests where needed.

### License

Rdiff-backup is licensed with GNU General Public License v2.0 or later. By
contributing to this repository you agree that your work is licensed using the
chosen project license.

### Branching model and pull requests

The *master* branch is always kept in a clean state. Anybody can at any time
clone this repository and branch off from *master* and expect test suite to pass
and the code and other contents to be of good quality and a reasonable
foundation for them to continue development on.

Each pull request has only one author, but anybody can give feedback. The
original author should be given time to address the feedback – reviewers should
not do the fixes for the author, but instead let the author keep the authorship.
Things can always be iterated and extended in future commits once the PR has
been merged, or even in parallel if the changes are in different files or at
least on different lines and do not cause merge conflicts if worked on.

If a pull requests for whatever reason is not quickly merged, should it be
refreshed by [rebasing](https://git-scm.com/docs/git-rebase) it on latest
upstream master.

Ideally each pull request gets some feedback within 24 hours from it having been
filed, and is merged within days or a couple of weeks. Each author should
facilitate quick reviews and merges by making clean and neat commits and pull
requests that are quick to review and do not spiral out in long discussions.

#### Merging changes to master

Currently the rdiff-backup Github repository is configured so that merging a
pull request is possible only if it:
- passes the CI testing
- has at least one approving review

While anybody can make forks, pull requests and comment them, only a developer
with write access to the main repository can merge and land commits in the
master branch. To get write access, the person mush exhibit commitment to high
standards and have a track record of meaningful contributions over several
months.

### Coding style

This project is written in Python, and must follow the official [PEP 8 coding
standard](https://www.python.org/dev/peps/pep-0008/) as enforced via the CI
system.

### Versioning

In versioning we utilize git tags as understood by
[setuptools_scm](https://github.com/pypa/setuptools_scm/#default-versioning-scheme).
Version strings follow the [PEP-440
standard](https://www.python.org/dev/peps/pep-0440/).

## Releases

There is no prior release schedule – they are made when deemed fit.


## BUILD AND INSTALL

### Pre-requisites

The same pre-requisites as for the installation of rdiff-backup also apply for building:

* Python 3.5 or higher
* librsync 1.0.0 or higher
* pylibacl (optional, to support ACLs)
* pyxattr (optional, to support extended attributes) - even if the xattr library (without py) isn't part of our CI/CD pipeline, feel free to use it for your development

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

### Build and install using Makefile

The project has a [Makefile](../Makefile) that defines steps like `all`,
`build`, `test` and others. You can view the contents to see what it exactly
does. Using the `Makefile` is the easiest way to quickly build and test the
source code.

By default the `Makefile` runs all of it's command in a clean Docker container,
thus making sure all the build dependencies are correctly defined and also
protecting the host system from having to install them.

The [Travis-CI](https://travis-ci.org/rdiff-backup/rdiff-backup) integration
also uses the `Makefile`, so if all commands in the `Makefile` succeed locally,
the CI is most likely to pass as well.

### Build and install with setup.py

To install, simply run:

	python3 setup.py install

The build process can be also be run separately:

	python3 setup.py build

The setup script expects to find librsync headers and libraries in the
default location, usually /usr/include and /usr/lib.  If you want the
setup script to check different locations, use the --librsync-dir
switch or the LIBRSYNC_DIR environment variable.  For instance to instruct
the setup program to look in `/usr/local/include` and `/usr/local/lib`
for the librsync files run:

	python3 setup.py --librsync-dir=/usr/local build

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

> **NOTE:** if you plan to use `./setup.py bdist_rpm` to create an RPM, you
> would need rpm-build but be aware that it will currently fail due to a [known
> bug in setuptools with compressed man
> pages](https://github.com/pypa/setuptools/issues/1277).

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

For more details on testing, see the `test` sections in the [Makefile](../Makefile)
and the [.travis-ci.yml definitions](../.travis-ci.yml).

## DEBUGGING

### Trace back a coredump

At the time of writing these notes, there was an issue where calling the program
generates a `Segmentation fault (core dumped)`. This chapter is based on this
experience debugging under Fedora 29.

References:

* https://ask.fedoraproject.org/en/question/98776/where-is-core-dump-located/
* Adventures in Python core dumping: https://gist.github.com/toolness/d56c1aab317377d5d17a
* Debugging dynamically loaded extensions: https://www.oreilly.com/library/view/python-cookbook/0596001673/ch16s08.html
* Debugging Memory Problems: https://www.oreilly.com/library/view/python-cookbook/0596001673/ch16s09.html

> **NOTE:** This assumes gdb was already installed.

1. First install:

		sudo dnf install python3-debug
		sudo dnf debuginfo-install python3-debug-3.7.3-1.fc29.x86_64
		sudo dnf debuginfo-install bzip2-libs-1.0.6-28.fc29.x86_64 glibc-2.28-27.fc29.x86_64 \
			librsync-1.0.0-8.fc29.x86_64 libxcrypt-4.4.4-2.fc29.x86_64 \
			openssl-libs-1.1.1b-3.fc29.x86_64 popt-1.16-15.fc29.x86_64 \
			sssd-client-2.1.0-2.fc29.x86_64 xz-libs-5.2.4-3.fc29.x86_64 zlib-1.2.11-14.fc29.x86_64

2. Then run:

		python3 ./setup.py clean --all
		python3-debug ./setup.py clean --all
		CFLAGS='-Wall -O0 -g' python3-debug ./setup.py build
		PATH=$PWD/build/scripts-3.7:$PATH PYTHONPATH=$PWD/build/lib.linux-x86_64-3.7-pydebug/ rdiff-backup -v 10 \
			/some/dir1 /some/dir2
		[...]
		Segmentation fault (core dumped)

> **NOTE:** The CFLAGS avoids optimizations making debugging too complicated

At this stage `coredumpctl list` shows that coredump is the last one, so that
one can call `coredumpctl gdb`, which itself tells (in multiple steps) that we
missing some more debug information, hence the above `debuginfo-install`
statements (assuming guess you could install the packages without version
information if you're sure they fit the installed package versions).

So now back into `coredumpctl gdb`, with some commands:

	help
	help stack
	backtrace
	bt full
	py-bt
	frame <FrameNumber>
	p <SomeVar>

1. get a backtrace of all function calls leading to the coredump (also `bt`)
2. backtrace with local vars
3. py-bt is the Python version of backtrace
4. jump between frames as listed by bt using their `#FrameNumber`
5. print some variable/expression in the context of the selected frame

Jumping between frames and printing the different variables, we can recognize that:

1. the core dump is due to a seek on a null file pointer
2. that the file pointer comes from the job pointer handed over to the function rs_job_iter
3. the job pointer itself comes from the self variable handed over to `_librsync_patchmaker_cycle`
4. reading through the https://librsync.github.io/rdiff.html[librsync documentation], it appears that the job type is opaque, i.e. I can't directly influence and it has been created via the `rs_patch_begin` function within the function `_librsync_new_patchmaker` in `rdiff_backup/_librsyncmodule.c`.

At this stage, it seems that the core file has given most of its secrets and we need to debug the live program:

	$ PYTHONTRACEMALLOC=1 PATH=$PWD/build/scripts-3.7:$PATH PYTHONPATH=$PWD/build/lib.linux-x86_64-3.7-pydebug/ gdb python3-debug
	(gdb) break rdiff_backup/_librsyncmodule.c:_librsync_new_patchmaker
	(gdb) run build/scripts-3.7/rdiff-backup /some/source/dir /some/target/dir

The debugger runs until the breakpoint is reached, after which a succession of `next` and `print <SomeVar>` allows me to analyze the code step by step, and to come to the conclusion that `cfile = fdopen(python_fd, ...` is somehow wrong as it creates a null file pointer whereas `python_fd` looks like a valid file descriptor (an integer equal to 5).

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
