#!/usr/bin/env python3

import filecmp
import os
import shlex
import shutil
import subprocess
import sys
import time

# we need all this to extend the distutils/setuptools commands
from setuptools import setup, Extension, Command
import setuptools.command.build_py
import setuptools.command.sdist
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

    if LFLAGS or LIBS:
        lflags_arg = LFLAGS + LIBS
        if "-lrsync" in LIBS:
            libname = []
    if LIBRSYNC_DIR:
        incdir_list = [os.path.join(LIBRSYNC_DIR, "include")]
        libdir_list = [os.path.join(LIBRSYNC_DIR, "lib")]

        if os.name == "nt":
            rsyncdll_src = os.path.join(LIBRSYNC_DIR, "bin", "rsync.dll")
            rsyncdll_dst = os.path.join("src", "rdiff_backup", "rsync.dll")
            # rather ugly workaround, but it should be good enough
            if "clean" in sys.argv:
                if os.path.exists(rsyncdll_dst) and "--all" in sys.argv:
                    print(f"removing {rsyncdll_dst}")
                    if "--dry-run" not in sys.argv:
                        os.remove(rsyncdll_dst)
            elif (
                "--version" not in sys.argv
                and "-V" not in sys.argv
                and "--help" not in sys.argv
            ):
                if not os.path.exists(rsyncdll_dst) or not filecmp.cmp(
                    rsyncdll_src, rsyncdll_dst
                ):
                    print(f"copying {rsyncdll_src} -> {rsyncdll_dst}")
                    if "--dry-run" not in sys.argv:
                        shutil.copyfile(rsyncdll_src, rsyncdll_dst)

if os.name == "nt":
    # We rely on statically linked librsync
    librsync_macros = [("rsync_EXPORTS", None)]


# --- extend the build command to execute a command ---


class pre_build_exec(Command):
    description = "build template files executing a shell command"
    user_options = [
        # The format is (long option, short option, description).
        ("commands=", None, "list of command strings"),
    ]

    def initialize_options(self):
        """Set default values for options."""
        # Each user option must be listed here with their default value.
        self.commands = []

    def finalize_options(self):
        """Post-process options."""
        # we would need to do more if we would want to support command line
        # and/or setup.cfg as we would need to parse a string into a list of tuples
        if self.commands:
            assert all(map(lambda x: len(x) == 3, self.commands)), (
                "Each element of the list '{}' must be a tuple of "
                "command, source and target".format(self.commands)
            )

    def _make_exec(self, cmd, infile, outfile, repl_dict={}):
        self.mkpath(os.path.dirname(outfile))
        full_cmd = cmd.format(infile=infile, outfile=outfile, **repl_dict)
        # for security reasons, we split with shlex and call without shell
        subprocess.call(shlex.split(full_cmd))

    def run(self):
        if DEBUG:
            self.debug_print(self.distribution.dump_option_dicts())
        build_time = int(os.environ.get("SOURCE_DATE_EPOCH", time.time()))
        replacement_dict = {
            "ver": self.distribution.get_version(),
            "date": time.strftime("%B %Y", time.gmtime(build_time)),
        }
        for command in self.commands:
            cmd = command[0]
            inpath = os.path.join(*command[1])
            outpath = os.path.join(*command[2])
            self.make_file(
                (inpath),
                outpath,
                self._make_exec,
                (cmd, inpath, outpath, replacement_dict),
                exec_msg="executing {}".format(command),
            )


# --- extend the build command to do templating of files ---


class pre_build_templates(Command):
    description = "build template files replacing {{ }} placeholders"
    user_options = [
        # The format is (long option, short option, description).
        (
            "template-files=",
            None,
            "list of tuples of source template and destination files",
        ),
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
                "Each element of the list '{}' must be a tuple of source "
                "template and target files".format(self.template_files)
            )

    def _make_template(self, infile, outfile, repl_dict={}):
        """A helper function replacing {{ place_holders }} defined in repl_dict,
        creating the outfile out of the source template file infile."""
        self.mkpath(os.path.dirname(outfile))
        with open(infile, "r") as infp, open(outfile, "w") as outfp:
            for line in infp:
                if "{{" in line:
                    for key, value in repl_dict.items():
                        line = line.replace("{{ %s }}" % key, value)
                outfp.write(line)

    def run(self):
        if DEBUG:
            self.debug_print(self.distribution.dump_option_dicts())
        build_time = int(os.environ.get("SOURCE_DATE_EPOCH", time.time()))
        replacement_dict = {
            "version": self.distribution.get_version(),
            "month_year": time.strftime("%B %Y", time.gmtime(build_time)),
        }
        for template in self.template_files:
            self.make_file(
                (template[0]),
                template[1],
                self._make_template,
                (template[0], template[1], replacement_dict),
                exec_msg="templating %s -> %s" % (template[0], template[1]),
            )


class build_py(setuptools.command.build_py.build_py):
    """Inject our build sub-command in the build_py step"""

    def run(self):
        self.run_command("pre_build_exec")
        self.run_command("pre_build_templates")
        setuptools.command.build_py.build_py.run(self)


class sdist(setuptools.command.sdist.sdist):
    """Inject our build sub-command in the sdist step"""

    def run(self):
        self.run_command("pre_build_exec")
        self.run_command("pre_build_templates")
        setuptools.command.sdist.sdist.run(self)


# --- extend the clean command to remove templated and exec files ---


class clean(distutils.command.clean.clean):
    """Extend the clean class to also delete templated and exec files"""

    def initialize_options(self):
        self.template_files = None
        self.commands = None
        super().initialize_options()

    def finalize_options(self):
        """Post-process options."""
        # take over the option from our pre_build_templates command
        self.set_undefined_options(
            "pre_build_templates", ("template_files", "template_files")
        )
        self.set_undefined_options("pre_build_exec", ("commands", "commands"))
        super().finalize_options()

    def run(self):
        if self.all:
            for outfile in self.template_files:
                if os.path.isfile(outfile[-1]):
                    if not self.dry_run:
                        os.remove(outfile[-1])
                    log.info("removing '%s'", outfile[-1])
            for outfile in self.commands:
                outpath = os.path.join(*outfile[-1])
                if os.path.isfile(outpath):
                    if not self.dry_run:
                        os.remove(outpath)
                    log.info("removing '%s'", outpath)
        super().run()


setup(
    use_scm_version=True,
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
    # options is a hash of hash with command -> option -> value
    # the value happens here to be a list of file couples/tuples
    options={
        "pre_build_exec": {
            "commands": [
                (
                    'asciidoctor -b manpage -a revdate="{date}" '
                    '-a revnumber="{ver}" -o {outfile} {infile}',
                    ("docs", "rdiff-backup.1.adoc"),
                    ("dist", "rdiff-backup.1"),
                ),
                (
                    'asciidoctor -b manpage -a revdate="{date}" '
                    '-a revnumber="{ver}" -o {outfile} {infile}',
                    ("docs", "rdiff-backup-statistics.1.adoc"),
                    ("dist", "rdiff-backup-statistics.1"),
                ),
                (
                    'asciidoctor -b manpage -a revdate="{date}" '
                    '-a revnumber="{ver}" -o {outfile} {infile}',
                    ("docs", "rdiff-backup-delete.1.adoc"),
                    ("dist", "rdiff-backup-delete.1"),
                ),
            ]
        },
    },
    cmdclass={
        "pre_build_exec": pre_build_exec,
        "pre_build_templates": pre_build_templates,
        "build_py": build_py,
        "sdist": sdist,
        "clean": clean,
    },
)
