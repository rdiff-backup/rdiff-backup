#!/usr/bin/env python3

import sys
import os
import time

# we need all this to extend the distutils/setuptools commands
from setuptools import setup, Extension, Command
import setuptools.command.build_py
from distutils.debug import DEBUG
import distutils.command.clean
from distutils import log

# --- handling compilation and linking with librsync ---

lflags_arg = []
libname = ["rsync"]
librsync_macros = []
incdir_list = libdir_list = None

if os.name == "posix" or os.name == "nt":
    LIBRSYNC_DIR = os.environ.get("LIBRSYNC_DIR", "")
    LFLAGS = os.environ.get("LFLAGS", [])
    LIBS = os.environ.get("LIBS", [])

    # Handle --librsync-dir=[PATH] and --lflags=[FLAGS]
    args = sys.argv[:]
    for arg in args:
        if arg.startswith("--librsync-dir="):
            LIBRSYNC_DIR = arg.split("=")[1]
            sys.argv.remove(arg)
        elif arg.startswith("--lflags="):
            LFLAGS = arg.split("=")[1].split()
            sys.argv.remove(arg)
        elif arg.startswith("--libs="):
            LIBS = arg.split("=")[1].split()
            sys.argv.remove(arg)

        if LFLAGS or LIBS:
            lflags_arg = LFLAGS + LIBS

        if LIBRSYNC_DIR:
            incdir_list = [os.path.join(LIBRSYNC_DIR, "include")]
            libdir_list = [os.path.join(LIBRSYNC_DIR, "lib")]
        if "-lrsync" in LIBS:
            libname = []

if os.name == "nt":
    # We rely on statically linked librsync
    librsync_macros = [("rsync_EXPORTS", None)]


# --- extend the build command to do templating of files ---

class build_templates(Command):
    description = 'build template files replacing {{ }} placeholders'
    user_options = [
        # The format is (long option, short option, description).
        ('template-files=', None, 'list of tuples of source template and destination files'),
        # TODO we could add the replacement dict as well but not for now
    ]

    def initialize_options(self):
        """Set default values for options."""
        # Each user option must be listed here with their default value.
        self.template_files = []

    def finalize_options(self):
        """Post-process options."""
        # we would need to do more if we would want to support command line
        # and/or setup.cfg as we would need to parse a string into a list of tuples
        if self.template_files:
            assert all(map(lambda x: len(x) == 2, self.template_files)), (
                'Each element of the list must be a tuple of source template and target files'
                % self.template_files)

    def make_template(self, infile, outfile, repl_dict={}):
        """A helper function replacing {{ place_holders }} defined in repl_dict,
        creating the outfile out of the source template file infile."""
        self.mkpath(os.path.dirname(outfile))
        with open(infile, "r") as infp, open(outfile, "w") as outfp:
            for line in infp:
                if ("{{" in line):
                    for key, value in repl_dict.items():
                        line = line.replace("{{ %s }}" % key, value)
                outfp.write(line)

    def run(self):
        if DEBUG:
            self.debug_print(self.distribution.dump_option_dicts())
        replacement_dict = {
            "version": self.distribution.get_version(),
            "month_year": time.strftime("%B %Y", time.localtime(time.time()))
        }
        for template in self.template_files:
            self.make_file(
                (template[0]), template[1],
                self.make_template, (template[0], template[1], replacement_dict),
                exec_msg='templating %s -> %s' % (template[0], template[1])
            )


class build_py(setuptools.command.build_py.build_py):
    """Inject our build sub-command in the build step"""

    def run(self):
        self.run_command('build_templates')
        setuptools.command.build_py.build_py.run(self)


# --- extend the clean command to remove templated files ---

class clean(distutils.command.clean.clean):
    """Extend the clean class to also delete templated files"""

    def initialize_options(self):
        self.template_files = None
        super().initialize_options()

    def finalize_options(self):
        """Post-process options."""
        # take over the option from our build_templates command
        self.set_undefined_options('build_templates', ('template_files', 'template_files'))
        super().finalize_options()

    def run(self):
        if self.all:
            for template in self.template_files:
                if os.path.isfile(template[1]):
                    if not self.dry_run:
                        os.remove(template[1])
                    log.info("removing '%s'", template[1])
        super().run()


setup(
    name="rdiff-backup",
    use_scm_version=True,
    description="Backup and Restore utility, easy to use, efficient, locally and remotely usable",
    long_description="""
        rdiff-backup is a simple backup tool which can be used locally and remotely,
        on Linux and Windows, and even cross-platform between both.
        Users have reported using it successfully on FreeBSD and MacOS X.

        Beside it's ease of use, one of the main advantages of rdiff-backup is that it
        does use the same efficient protocol as rsync to transfer and store data.
        Because rdiff-backup only stores the differences from the previous backup to
        the next one (a so called reverse incremental backup),
        the latest backup is always a full backup, making it easiest
        and fastest to restore the most recent backups, combining the space
        advantages of incremental backups while keeping the speed advantages of full
        backups (at least for recent ones).

        If the optional dependencies pylibacl and pyxattr are installed,
        rdiff-backup will support Access Control Lists and Extended Attributes
        provided the file system(s) also support these features.""",
    keywords=['backup', 'simple', 'easy', 'remote', 'incremental', 'efficient', 'cross-platform'],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: End Users/Desktop',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)',
        'Natural Language :: English',
        'Operating System :: POSIX :: Linux',
        'Operating System :: POSIX',  # generic because users reported FreeBSD to work
        'Operating System :: Microsoft :: Windows',
        'Programming Language :: Python :: 3',
        'Topic :: System :: Archiving :: Backup',
    ],
    license="GPLv2+",
    author="The rdiff-backup project",
    author_email="rdiff-backup-users@nongnu.org",
    # maintainer and maintainer_email could be used to differentiate the package owner
    url="https://rdiff-backup.net/",
    download_url="https://github.com/rdiff-backup/rdiff-backup/releases",
    python_requires='~=3.5',
    platforms=['linux', 'win32'],
    packages=["rdiff_backup"],
    package_dir={"": "src"},  # tell distutils packages are under src
    ext_modules=[
        Extension("rdiff_backup.C", ["src/cmodule.c"]),
        Extension(
            "rdiff_backup._librsync",
            ["src/_librsyncmodule.c"],
            define_macros=librsync_macros,
            include_dirs=incdir_list,
            library_dirs=libdir_list,
            libraries=libname,
            extra_link_args=lflags_arg,
        ),
    ],
    scripts=["src/rdiff-backup", "src/rdiff-backup-statistics"],
    data_files=[
        ("share/man/man1", ["build/rdiff-backup.1", "build/rdiff-backup-statistics.1"]),
        (
            "share/doc/rdiff-backup",
            [
                "CHANGELOG",
                "COPYING",
                "README.md",
                "docs/FAQ.md",
                "docs/examples.md",
                "docs/DEVELOP.md",
                "docs/Windows-README.md",
            ],
        ),
        ("share/bash-completion/completions", ["tools/bash-completion/rdiff-backup"]),
    ],
    # options is a hash of hash with command -> option -> value
    # the value happens here to be a list of file couples/tuples
    options={'build_templates': {'template_files': [
        ("tools/rdiff-backup.spec.template", "build/rdiff-backup.spec"),
        ("tools/rdiff-backup.spec.template-fedora", "build/rdiff-backup.fedora.spec"),
        ("docs/rdiff-backup.1", "build/rdiff-backup.1"),
        ("docs/rdiff-backup-statistics.1", "build/rdiff-backup-statistics.1"),
    ]}},
    cmdclass={
        'build_templates': build_templates,
        'build_py': build_py,
        'clean': clean,
    },
    setup_requires=['setuptools_scm'],
)
