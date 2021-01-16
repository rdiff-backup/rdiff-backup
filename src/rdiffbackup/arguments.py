# Copyright 2021 the rdiff-backup project
#
# This file is part of rdiff-backup.
#
# rdiff-backup is free software; you can redistribute it and/or modify
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; either version 2 of the License, or (at your
# option) any later version.
#
# rdiff-backup is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with rdiff-backup; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA
"""
This module offers mainly a function `parse` to parse command line
arguments using Python's argparse module and return an
argparse.Namespace object with the parsed arguments.
The main section at the very end of this module offers an example on how
to use it.
NOTE: the BaseAction class and derived action classes are here only for
      now.
"""

import argparse
import sys
import yaml


# The default regexp for not compressing those files
# COMPAT200: it is also used by Main.py to avoid having a 2nd default
DEFAULT_NOT_COMPRESSED_REGEXP = (
        "(?i).*\\.("
        "gz|z|bz|bz2|tgz|zip|zst|rpm|deb|"
        "jpg|jpeg|gif|png|jp2|mp3|mp4|ogg|ogv|oga|ogm|avi|wmv|"
        "mpeg|mpg|rm|mov|mkv|flac|shn|pgp|"
        "gpg|rz|lz4|lzh|lzo|zoo|lharc|rar|arj|asc|vob|mdf|tzst|webm"
        ")$"
    )

try:
    from argparse import BooleanOptionalAction
except ImportError:
    # the class exists only since Python 3.9
    class BooleanOptionalAction(argparse.Action):
        def __init__(self,
                     option_strings,
                     dest,
                     default=None,
                     type=None,
                     choices=None,
                     required=False,
                     help=None,
                     metavar=None):

            _option_strings = []
            for option_string in option_strings:
                _option_strings.append(option_string)

                if option_string.startswith('--'):
                    option_string = '--no-' + option_string[2:]
                    _option_strings.append(option_string)

            if help is not None and default is not None:
                help += f" (default: {default})"

            super().__init__(
                option_strings=_option_strings,
                dest=dest,
                nargs=0,
                default=default,
                type=type,
                choices=choices,
                required=required,
                help=help,
                metavar=metavar)

        def __call__(self, parser, namespace, values, option_string=None):
            if option_string in self.option_strings:
                setattr(namespace, self.dest, not option_string.startswith('--no-'))

        def format_usage(self):
            return ' | '.join(self.option_strings)


class SelectAction(argparse.Action):
    """
    argparse Action class which can handle placeholder options, adding them all
    together under one destination and keeping the same order as the arguments
    on the command line.
    e.g. '--exclude value1 --include-perhaps --max 10' is interpreted as
    selections=[('exclude', value1), ('include-perhaps', True), ('max', 10)]
    by just defining the arguments '--SELECT', '--SELECT-perhaps' and '--max'.
    """

    placeholder = 'SELECT'
    default_dest = 'selections'

    def __init__(self, option_strings, dest,
                 type=str, nargs=None, help=None, default=None, **kwargs):
        """
        Initialize the placeholder-argument object, making sure that both
        exclude and include arguments are allowed, that booleans have
        a meaningful True value, and that all values are by default are
        gathered under the same 'selections' destination.
        """
        # because the argparse framework always sets 'dest',
        # we need to guess if dest was explicitly set, and if not,
        # we can overwrite it with the default value
        if ('--' + dest.replace('_', '-')) in option_strings:
            dest = self.default_dest
        # we want to make sure that toggles/booleans have a correct value
        if type is bool and nargs is None:
            nargs = 0
            if default is None:
                default = True
        # replace placeholder with both include and exclude options
        include_opts = list(map(
            lambda x: x.replace(self.placeholder, 'include'), option_strings))
        exclude_opts = list(map(
            lambda x: x.replace(self.placeholder, 'exclude'), option_strings))
        if exclude_opts != include_opts:
            # SELECT was found hence we need to duplicate the options
            # and update accordingly the help text
            option_strings = exclude_opts + include_opts
            if help:
                help = help.replace(self.placeholder, 'exclude/include')
                if default is None:
                    help += " (no default)"
                elif default:
                    help += " (default is include)"
                else:
                    help += " (default is exclude)"
        super().__init__(option_strings, dest,
                         type=type, nargs=nargs, help=help, default=default,
                         **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        """
        append the selection criteria (option_string, values) to the
        ordered list of selection criteria.
        """

        old_list = getattr(namespace, self.dest, [])
        # namespace is "too intelligent", it always returns None even if
        # the parameter isn't previously defined
        if old_list is None:
            old_list = []
        # append the option string and values to the selections list
        if values == [] and self.default is not None:
            values = self.default
        setattr(namespace, self.dest,
                old_list + [(option_string.replace('--', ''), values)])


# === DEFINE PARENT PARSERS ===


COMMON_PARSER = argparse.ArgumentParser(
    add_help=False,
    description="[parent] common options to all actions")
COMMON_PARSER.add_argument(
    "--api-version", type=int,
    help="[opt] integer to set the API version forcefully used")
COMMON_PARSER.add_argument(
    "--current-time", type=int,
    help="[opt] fake the current time in seconds (for testing)")
COMMON_PARSER.add_argument(
    "--force", action="store_true",
    help="[opt] force action (caution, the result might be dangerous)")
COMMON_PARSER.add_argument(
    "--fsync", default=True, action=BooleanOptionalAction,
    help="[opt] do (or not) often sync the file system (_not_ doing it is faster but can be dangerous)")
COMMON_PARSER.add_argument(
    "--null-separator", action="store_true",
    help="[opt] use null instead of newline in input and output files")
COMMON_PARSER.add_argument(
    "--new", default=False, action=BooleanOptionalAction,
    help="[opt] enforce (or not) the usage of the new parameters")
COMMON_PARSER.add_argument(
    "--chars-to-quote", "--override-chars-to-quote",
    type=str, metavar="CHARS",
    help="[opt] string of characters to quote for safe storing")
COMMON_PARSER.add_argument(
    "--parsable-output", action="store_true",
    help="[opt] output in computer parsable format")
COMMON_PARSER.add_argument(
    "--remote-schema", type=str,
    help="[opt] alternative command to call remotely rdiff-backup")
COMMON_PARSER.add_argument(
    "--remote-tempdir", type=str, metavar="DIR_PATH",
    help="[opt] use path as temporary directory on the remote side")
COMMON_PARSER.add_argument(
    "--restrict-path", type=str, metavar="DIR_PATH",
    help="[opt] restrict remote access to given path")
COMMON_PARSER.add_argument(
    "--restrict-mode", type=str,
    choices=["read-write", "read-only", "update-only"], default="read-write",
    help="[opt] restriction mode for directory (default is 'read-write')")
COMMON_PARSER.add_argument(
    "--ssh-compression", default=True, action=BooleanOptionalAction,
    help="[opt] use SSH without compression with default remote-schema")
COMMON_PARSER.add_argument(
    "--tempdir", type=str, metavar="DIR_PATH",
    help="[opt] use given path as temporary directory")
COMMON_PARSER.add_argument(
    "--terminal-verbosity", type=int, choices=range(0, 10),
    help="[opt] verbosity on the terminal, default given by --verbosity")
COMMON_PARSER.add_argument(
    "--use-compatible-timestamps", action="store_true",
    help="[sub] use hyphen '-' instead of colon ':' to represent time")
COMMON_PARSER.add_argument(
    "-v", "--verbosity", type=int, choices=range(0, 10), default=3,
    help="[opt] overall verbosity on terminal and in logfiles (default is 3)")

COMMON_COMPAT200_PARSER = argparse.ArgumentParser(
    add_help=False,
    description="[parent] common options to all actions (compat200)")
restrict_group = COMMON_COMPAT200_PARSER.add_mutually_exclusive_group()
restrict_group.add_argument(
    "--restrict", type=str, metavar="DIR_PATH",
    help="[deprecated] restrict remote access to given path, in read-write mode")
restrict_group.add_argument(
    "--restrict-read-only", type=str, metavar="DIR_PATH",
    help="[deprecated] restrict remote access to given path, in read-only mode")
restrict_group.add_argument(
    "--restrict-update-only", type=str, metavar="DIR_PATH",
    help="[deprecated] restrict remote access to given path, in backup update mode")
COMMON_COMPAT200_PARSER.add_argument(
    "--ssh-no-compression", action="store_true",
    help="[deprecated] use SSH without compression with default remote-schema")

SELECTION_PARSER = argparse.ArgumentParser(
    add_help=False,
    description="[parent] options related to file selection")
SELECTION_PARSER.add_argument(
    "--SELECT", action=SelectAction, metavar="GLOB",
    help="[sub] SELECT files according to glob pattern")
SELECTION_PARSER.add_argument(
    "--SELECT-device-files", action=SelectAction, type=bool, default=True,
    help="[sub] SELECT device files")
SELECTION_PARSER.add_argument(
    "--SELECT-fifos", action=SelectAction, type=bool, default=True,
    help="[sub] SELECT fifo files")
SELECTION_PARSER.add_argument(
    "--SELECT-filelist", action=SelectAction, metavar="LIST_FILE",
    help="[sub] SELECT files according to list in given file")
SELECTION_PARSER.add_argument(
    "--SELECT-filelist-stdin", action=SelectAction, type=bool,
    help="[sub] SELECT files according to list from standard input")
SELECTION_PARSER.add_argument(
    "--SELECT-symbolic-links", action=SelectAction, type=bool, default=True,
    help="[sub] SELECT symbolic links")
SELECTION_PARSER.add_argument(
    "--SELECT-sockets", action=SelectAction, type=bool, default=True,
    help="[sub] SELECT socket files")
SELECTION_PARSER.add_argument(
    "--SELECT-globbing-filelist", action=SelectAction, metavar="GLOBS_FILE",
    help="[sub] SELECT files according to glob list in given file")
SELECTION_PARSER.add_argument(
    "--SELECT-globbing-filelist-stdin", action=SelectAction, type=bool,
    help="[sub] SELECT files according to glob list from standard input")
SELECTION_PARSER.add_argument(
    "--SELECT-other-filesystems", action=SelectAction, type=bool, default=True,
    help="[sub] SELECT files from other file systems than the source one")
SELECTION_PARSER.add_argument(
    "--SELECT-regexp", action=SelectAction, metavar="REGEXP",
    help="[sub] SELECT files according to regexp pattern")
SELECTION_PARSER.add_argument(
    "--SELECT-if-present", action=SelectAction, metavar="FILENAME",
    help="[sub] SELECT directory if it contains the given file")
SELECTION_PARSER.add_argument(
    "--SELECT-special-files", action=SelectAction, type=bool, default=True,
    help="[sub] SELECT all device, fifo, socket files, and symbolic links")
SELECTION_PARSER.add_argument(
    "--max-file-size", action=SelectAction, metavar="SIZE", type=int,
    help="[sub] exclude files larger than given size in bytes")
SELECTION_PARSER.add_argument(
    "--min-file-size", action=SelectAction, metavar="SIZE", type=int,
    help="[sub] exclude files smaller than given size in bytes")

FILESYSTEM_PARSER = argparse.ArgumentParser(
    add_help=False,
    description="[parent] options related to file system capabilities")
FILESYSTEM_PARSER.add_argument(
    "--acls", default=True, action=BooleanOptionalAction,
    help="[sub] handle (or not) Access Control Lists")
FILESYSTEM_PARSER.add_argument(
    "--carbonfile", default=True, action=BooleanOptionalAction,
    help="[sub] handle (or not) carbon files on MacOS X")
FILESYSTEM_PARSER.add_argument(
    "--compare-inode", default=True, action=BooleanOptionalAction,
    help="[sub] compare (or not) inodes to decide if hard-linked files have changed")
FILESYSTEM_PARSER.add_argument(
    "--eas", default=True, action=BooleanOptionalAction,
    help="[sub] handle (or not) Extended Attributes")
FILESYSTEM_PARSER.add_argument(
    "--hard-links", default=True, action=BooleanOptionalAction,
    help="[sub] preserve (or not) hard links.")
FILESYSTEM_PARSER.add_argument(
    "--resource-forks", default=True, action=BooleanOptionalAction,
    help="[sub] preserve (or not) resource forks on MacOS X.")
FILESYSTEM_PARSER.add_argument(
    "--never-drop-acls", action="store_true",
    help="[sub] exit with error instead of dropping acls or acl entries.")

CREATION_PARSER = argparse.ArgumentParser(
    add_help=False,
    description="[parent] options related to creation of directories")
CREATION_PARSER.add_argument(
    "--create-full-path", action="store_true",
    help="[sub] create full necessary path to backup repository")

COMPRESSION_PARSER = argparse.ArgumentParser(
    add_help=False,
    description="[parent] options related to compression")
COMPRESSION_PARSER.add_argument(
    "--compression", default=True, action=BooleanOptionalAction,
    help="[sub] compress (or not) snapshot and diff files")
COMPRESSION_PARSER.add_argument(
    "--not-compressed-regexp", "--no-compression-regexp", metavar="REGEXP",
    default=DEFAULT_NOT_COMPRESSED_REGEXP,
    help="[sub] regexp to select files not being compressed")

STATISTICS_PARSER = argparse.ArgumentParser(
    add_help=False,
    description="[parent] options related to backup statistics")
STATISTICS_PARSER.add_argument(
    "--file-statistics", default=True, action=BooleanOptionalAction,
    help="[sub] do (or not) generate statistics file during backup")
STATISTICS_PARSER.add_argument(
    "--print-statistics", default=False, action=BooleanOptionalAction,
    help="[sub] print (or not) statistics after a successful backup")

TIMESTAMP_PARSER = argparse.ArgumentParser(
    add_help=False,
    description="[parent] options related to regress timestamps")
TIMESTAMP_PARSER.add_argument(
    "--allow-duplicate-timestamps", action="store_true",
    help="[sub] ignore duplicate metadata while checking repository")

USER_GROUP_PARSER = argparse.ArgumentParser(
    add_help=False,
    description="[parent] options related to user and group mapping")
USER_GROUP_PARSER.add_argument(
    "--group-mapping-file", type=str, metavar="MAP_FILE",
    help="[sub] map groups according to file")
USER_GROUP_PARSER.add_argument(
    "--preserve-numerical-ids", action="store_true",
    help="[sub] preserve user and group IDs instead of names")
USER_GROUP_PARSER.add_argument(
    "--user-mapping-file", type=str, metavar="MAP_FILE",
    help="[sub] map users according to file")

PARENT_PARSERS = [
    COMMON_PARSER, COMMON_COMPAT200_PARSER,
    CREATION_PARSER, COMPRESSION_PARSER, SELECTION_PARSER,
    FILESYSTEM_PARSER, USER_GROUP_PARSER, STATISTICS_PARSER,
    TIMESTAMP_PARSER
]


# === CLASSES ===
# NOTE: those classes are only a place holder for now and will move to their
#       own package/modules.


class BaseAction:
    """
    Base rdiff-backup Action, knows about all available rdiff-backup
    actions, and is to be used as base class for all these actions.
    """

    # name of the action as a string
    name = None
    # list of parent parsers
    parent_parsers = []

    @classmethod
    def get_actions(cls):
        """
        Return a list of all rdiff-backup actions in the form of a
        dictionary `{"action_name": SomeAction}`, SomeAction being a class
        derived from BaseAction.
        """
        # the actions can't be defined as class variable because the *Action
        # classes wouldn't yet be known.
        actions = {
            "backup": BackupAction,
            "calculate": CalculateAction,
            "compare": CompareAction,
            "info": InfoAction,
            "list": ListAction,
            "regress": RegressAction,
            "remove": RemoveAction,
            "restore": RestoreAction,
            "server": ServerAction,
            "verify": VerifyAction,
        }
        return actions

    @classmethod
    def add_action_subparser(cls, sub_handler):
        """
        Given a subparsers handle as returned by argparse.add_subparsers,
        creates the subparser corresponding to the current Action class
        (as inherited).
        Most Action classes will need to extend this function with their
        own subparsers.
        Returns the computed subparser.
        """
        subparser = sub_handler.add_parser(cls.name,
                                           parents=cls.parent_parsers,
                                           description=cls.__doc__)
        subparser.set_defaults(action=cls.name)  # TODO cls instead of name!

        return subparser

    @classmethod
    def _get_subparsers(cls, parser, sub_dest, *sub_names):
        """
        This method can be used to add 2nd level subparsers to the action
        subparser (named here parser). sub_dest would typically be the name
        of the action, and sub_names are the names for the sub-subparsers.
        Returns the computed subparsers as dictionary with the sub_names as
        keys, so that arguments can be added to those subparsers as values.
        """
        if sys.version_info.major >= 3 and sys.version_info.minor >= 7:
            sub_handler = parser.add_subparsers(
                title="possible {dest}s".format(dest=sub_dest),
                required=True, dest=sub_dest)
        else:  # required didn't exist in Python 3.6
            sub_handler = parser.add_subparsers(
                title="possible {dest}s".format(dest=sub_dest),
                dest=sub_dest)

        subparsers = {}
        for sub_name in sub_names:
            subparsers[sub_name] = sub_handler.add_parser(sub_name)
            subparsers[sub_name].set_defaults(**{sub_dest: sub_name})
        return subparsers

    def __init__(self, values):
        """
        Dummy initialization method
        """
        self.values = values

    def print_values(self, explicit=True):
        """
        Dummy output method
        """
        print(yaml.safe_dump(self.values.__dict__,
                             explicit_start=explicit, explicit_end=explicit))


class BackupAction(BaseAction):
    """
    Backup a source directory to a target backup repository.
    """
    name = "backup"
    parent_parsers = [
        CREATION_PARSER, COMPRESSION_PARSER, SELECTION_PARSER,
        FILESYSTEM_PARSER, USER_GROUP_PARSER, STATISTICS_PARSER,
    ]

    @classmethod
    def add_action_subparser(cls, sub_handler):
        subparser = super().add_action_subparser(sub_handler)
        subparser.add_argument(
            "locations", metavar="[[USER@]SERVER::]PATH", nargs=2,
            help="locations of SOURCE_DIR and to which REPOSITORY to backup")
        return subparser


class CalculateAction(BaseAction):
    """
    Calculate values (average by default) across multiple statistics files.
    """
    name = "calculate"

    @classmethod
    def add_action_subparser(cls, sub_handler):
        subparser = super().add_action_subparser(sub_handler)
        subparser.add_argument(
            "--method", choices=["average"], default="average",
            help="what to calculate from the different statistics")
        subparser.add_argument(
            "locations", metavar="STATISTIC_FILE", nargs="+",
            help="locations of the statistic files to calculate from")
        return subparser


class CompareAction(BaseAction):
    """
    Compare the content of a source directory with a backup repository
    at a given time, using multiple methods.
    """
    name = "compare"
    parent_parsers = [SELECTION_PARSER]

    @classmethod
    def add_action_subparser(cls, sub_handler):
        subparser = super().add_action_subparser(sub_handler)
        subparser.add_argument(
            "--method", choices=["meta", "full", "hash"], default="meta",
            help="use metadata, complete file or hash to compare directories")
        subparser.add_argument(
            "--at", metavar="TIME", default="now",
            help="compare with the backup at the given time, default is 'now'")
        subparser.add_argument(
            "locations", metavar="[[USER@]SERVER::]PATH", nargs=2,
            help="locations of SOURCE_DIR and backup REPOSITORY to compare"
                 " (same order as for a backup)")
        return subparser


class InfoAction(BaseAction):
    """
    Output information about the current system, so that it can be used in
    in a bug report, and exits.
    """
    name = "info"
    # information has no specific sub-options


class ListAction(BaseAction):
    """
    List files at a given time, files changed since a certain time, or
    increments, with or without size, in a given backup repository.
    """
    name = "list"

    @classmethod
    def add_action_subparser(cls, sub_handler):
        subparser = super().add_action_subparser(sub_handler)
        entity_parsers = cls._get_subparsers(
            subparser, "entity", "files", "increments")
        time_group = entity_parsers["files"].add_mutually_exclusive_group()
        time_group.add_argument(
            "--changed-since", metavar="TIME",
            help="list files modified since given time")
        time_group.add_argument(
            "--at", metavar="TIME", default="now",
            help="list files at given time (default is now/latest)")
        entity_parsers["files"].add_argument(
            "locations", metavar="[[USER@]SERVER::]PATH", nargs=1,
            help="location of repository to list files from")
        entity_parsers["increments"].add_argument(
            "--size", action=BooleanOptionalAction, default=False,
            help="also output size of each increment (might take longer)")
        entity_parsers["increments"].add_argument(
            "locations", metavar="[[USER@]SERVER::]PATH", nargs=1,
            help="location of repository to list increments from")
        return subparser


class RegressAction(BaseAction):
    """
    Regress a backup repository, i.e. remove the last (failed) incremental
    backup and reverse to the last known good mirror.
    """
    name = "regress"
    parent_parsers = [COMPRESSION_PARSER, TIMESTAMP_PARSER, USER_GROUP_PARSER]

    @classmethod
    def add_action_subparser(cls, sub_handler):
        subparser = super().add_action_subparser(sub_handler)
        subparser.add_argument(
            "locations", metavar="[[USER@]SERVER::]PATH", nargs=1,
            help="location of repository to check and possibly regress")
        return subparser


class RemoveAction(BaseAction):
    """
    Remove the oldest increments from a backup repository.
    """
    name = "remove"

    @classmethod
    def add_action_subparser(cls, sub_handler):
        subparser = super().add_action_subparser(sub_handler)
        entity_parsers = cls._get_subparsers(
            subparser, "entity", "increments")
        entity_parsers["increments"].add_argument(
            "--older-than", metavar="TIME",
            help="remove increments older than given time")
        entity_parsers["increments"].add_argument(
            "locations", metavar="[[USER@]SERVER::]PATH", nargs=1,
            help="location of repository to remove increments from")
        return subparser


class RestoreAction(BaseAction):
    """
    Restore a backup at a given time (default is latest) from a repository
    to a target directory.
    """
    name = "restore"
    parent_parsers = [
        CREATION_PARSER, COMPRESSION_PARSER, SELECTION_PARSER,
        FILESYSTEM_PARSER, USER_GROUP_PARSER,
    ]

    @classmethod
    def add_action_subparser(cls, sub_handler):
        subparser = super().add_action_subparser(sub_handler)
        restore_group = subparser.add_mutually_exclusive_group()
        restore_group.add_argument(
            "--at", metavar="TIME",
            help="restore files as of a specific time")
        restore_group.add_argument(
            "--increment", action="store_true",
            help="restore from a specific increment as first parameter")
        subparser.add_argument(
            "locations", metavar="[[USER@]SERVER::]PATH", nargs=2,
            help="locations of backup REPOSITORY/INCREMENT and to which TARGET_DIR to restore")
        return subparser


class ServerAction(BaseAction):
    """
    Start rdiff-backup in server mode (only meant for internal use).
    """
    name = "server"
    # server has no specific sub-options


class VerifyAction(BaseAction):
    """
    Verify that files in a backup repository correspond to their stored hash,
    or that servers are properly reachable.
    """
    name = "verify"

    @classmethod
    def add_action_subparser(cls, sub_handler):
        subparser = super().add_action_subparser(sub_handler)
        entity_parsers = cls._get_subparsers(
            subparser, "entity", "files", "servers")
        entity_parsers["files"].add_argument(
            "--at", metavar="TIME", default="now",
            help="as of which time to check the files' hashes (default is now/latest)")
        entity_parsers["files"].add_argument(
            "locations", metavar="[[USER@]SERVER::]PATH", nargs=1,
            help="location of repository where to check files' hashes")
        entity_parsers["servers"].add_argument(
            "locations", metavar="[[USER@]SERVER::]PATH", nargs="+",
            help="location of remote repositories to check for connection")
        return subparser


# === FUNCTIONS ===


def parse(args, version_string, parent_parsers, actions=None):
    """
    Parses the given arguments, using the version string for --version,
    parents is a list of parent parsers, where the first one is assumed to
    be the commone one, sole one required by the new parser.
    And actions is a dictionary of the form `{"action_name": ActionClass}`.
    Returns an argparse Namespace containing the parsed parameters.
    """
    # we try to recognize if the user wants the old or the new parameters
    # it's the case if --new is explicitly given, or if any parameter starts
    # with an @ (meaning read from file), or if api-version is used, or if
    # any of the action names is found in the parameters, without `--no-new`
    # being found.
    # note: `set1 & set2` is the intersection of two sets
    if ('--new' in args
            or (any(map(lambda x: x.startswith('@'), args)))
            or ('--no-new' not in args
                and ('--api-version' in args
                     or (set(actions.keys()) & set(args))))):
        return _parse_new(args, version_string, parent_parsers[0:1], actions)
    else:
        return _parse_compat200(args, version_string, parent_parsers)


def _parse_new(args, version_string, parent_parsers, actions):
    """
    Parse arguments according to new parameters of rdiff-backup, i.e.
        rdiff-backup <opt(ions)> <act(ion)> <sub(-options)> <paths>
    """
    parser = argparse.ArgumentParser(
        description="local/remote mirror and incremental backup",
        parents=parent_parsers, fromfile_prefix_chars='@')

    _add_version_option_to_parser(parser, version_string)

    if sys.version_info.major >= 3 and sys.version_info.minor >= 7:
        sub_handler = parser.add_subparsers(
            title="possible actions", required=True, dest='action',
            help="call '%(prog)s <action> --help' for more information")
    else:  # required didn't exist in Python 3.6
        sub_handler = parser.add_subparsers(
            title="possible actions", dest='action',
            help="call '%(prog)s <action> --help' for more information")

    for action in actions.values():
        action.add_action_subparser(sub_handler)

    parsed_args = parser.parse_args(args)

    if not (sys.version_info.major >= 3 and sys.version_info.minor >= 7):
        # we need a work-around as long as Python 3.6 doesn't know about required
        if not parsed_args.action:
            parser.error(message="the following arguments are required: action")

    return parsed_args


def _parse_compat200(args, version_string, parent_parsers=[]):
    """
    Parse arguments according to old parameters of rdiff-backup.
    The hint in square brackets at the beginning of the help are in preparation
    for the new way of parsing:
        rdiff-backup <opt(ions)> <act(ion)> <sub(-options)> <paths>
    Note that actions are mutually exclusive and that '[act=]' will need to be
    split into an action and a sub-option.
    """

    parser = argparse.ArgumentParser(
        description="local/remote mirror and incremental backup",
        parents=parent_parsers
    )

    _add_version_option_to_parser(parser, version_string)

    action_group = parser.add_mutually_exclusive_group()
    action_group.add_argument(
        "-b", "--backup-mode",
        dest="action", action="store_const", const="backup",
        help="[act] back-up directory into back-up repository")
    action_group.add_argument(
        "--calculate-average",
        dest="action", action="store_const", const="calculate-average",
        help="[act] calculate average across multiple statistic files")
    action_group.add_argument(
        "--check-destination-dir",
        dest="action", action="store_const", const="check-destination-dir",
        help="[act] check-destination-dir")
    action_group.add_argument(
        "--compare", dest="action", action="store_const", const="compare",
        help="[act] compare normal (at time now)")
    action_group.add_argument(
        "--compare-at-time", type=str, metavar="AT_TIME",
        help="[act=] compare normal at given time")
    action_group.add_argument(
        "--compare-hash",
        dest="action", action="store_const", const="compare-hash",
        help="[act] compare by hash (at time now)")
    action_group.add_argument(
        "--compare-hash-at-time", type=str, metavar="AT_TIME",
        help="[act=] compare by hash at given time")
    action_group.add_argument(
        "--compare-full",
        dest="action", action="store_const", const="compare-full",
        help="[act] compare full (at time now)")
    action_group.add_argument(
        "--compare-full-at-time", type=str, metavar="AT_TIME",
        help="[act=] compare full at given time")
    action_group.add_argument(
        "--info", action="store_const", const="info",
        help="[act] output information e.g. for bug reports")
    action_group.add_argument(
        "--list-at-time", type=str, metavar="AT_TIME",
        help="[act=] list files and directories at given time")
    action_group.add_argument(
        "--list-changed-since", type=str, metavar="AT_TIME",
        help="[act=] list changed files and directories since given time")
    action_group.add_argument(
        "-l", "--list-increments",
        dest="action", action="store_const", const="list-increments",
        help="[act] list increments in backup repository")
    action_group.add_argument(
        "--list-increment-sizes",
        dest="action", action="store_const", const="list-increment-sizes",
        help="[act] list increments and their size in backup repository")
    action_group.add_argument(
        "--remove-older-than", type=str, metavar="AT_TIME",
        help="[act=] remove increments older than given time")
    action_group.add_argument(
        "-r", "--restore-as-of", type=str, metavar="AT_TIME",
        help="[act=] restore files from repo as of given time")
    action_group.add_argument(
        "--restore", dest="action", action="store_const", const="restore",
        help="[act] restore a specific increment")
    action_group.add_argument(
        "-s", "--server", dest="action", action="store_const", const="server",
        help="[act] start rdiff-backup in server mode")
    action_group.add_argument(
        "--test-server",
        dest="action", action="store_const", const="test-server",
        help="[act] test communication to multiple remote servers")
    action_group.add_argument(
        "--verify", dest="action", action="store_const", const="verify",
        help="[act] verify hash values in backup repo (at time now)")
    action_group.add_argument(
        "--verify-at-time", type=str, metavar="AT_TIME",
        help="[act=] verify hash values in backup repo (at given time)")

    parser.add_argument(
        "locations", nargs='*',
        help="[args] locations remote and local to be handled by chosen action")

    values = parser.parse_args(args)

    # compatibility layer with new parameter handling
    if not values.action:
        if values.compare_at_time:
            values.action = "compare"
            values.method = "meta"
            values.at = values.compare_at_time
        elif values.compare_hash_at_time:
            values.action = "compare"
            values.method = "hash"
            values.at = values.compare_hash_at_time
        elif values.compare_full_at_time:
            values.action = "compare"
            values.method = "full"
            values.at = values.compare_full_at_time
        elif values.list_at_time:
            values.action = "list"
            values.entity = "files"
            values.at = values.list_at_time
        elif values.list_changed_since:
            values.action = "list"
            values.entity = "files"
            values.changed_since = values.list_changed_since
        elif values.remove_older_than:
            values.action = "remove"
            values.entity = "increments"
            values.older_than = values.remove_older_than
        elif values.restore_as_of:
            values.action = "restore"
            values.at = values.restore_as_of
            values.increment = False
        elif values.verify_at_time:
            values.action = "verify"
            values.entity = "files"
            values.at = values.verify_at_time
        # if there is still no action defined, we set the default
        if not values.action:
            values.action = "backup"
    else:
        if values.action == "calculate-average":
            values.action = "calculate"
            values.method = "average"
        elif values.action == "check-destination-dir":
            values.action = "regress"
        elif values.action == "compare":
            values.method = "meta"
            values.at = "now"
        elif values.action == "compare-hash":
            values.action = "compare"
            values.method = "hash"
            values.at = "now"
        elif values.action == "compare-full":
            values.action = "compare"
            values.method = "full"
            values.at = "now"
        elif values.action == "list-increments":
            values.action = "list"
            values.entity = "increments"
            values.sizes = False
        elif values.action == "list-increment-sizes":
            values.action = "list"
            values.entity = "increments"
            values.size = True
        elif values.action == "restore":
            values.increment = True
            values.at = None
        elif values.action == "test-server":
            values.action = "verify"
            values.entity = "servers"
        elif values.action == "verify":
            values.entity = "files"
            values.at = "now"

    # those are a bit critical because they are duplicates between
    # new and old options
    if values.ssh_no_compression == True:
        values.ssh_compression = False
    if values.restrict and not values.restrict_path:
        values.restrict_path = values.restrict
        values.restrict_mode = "read-write"
    elif values.restrict_read_only and not values.restrict_path:
        values.restrict_path = values.restrict_read_only
        values.restrict_mode = "read-only"
    elif values.restrict_update_only and not values.restrict_path:
        values.restrict_path = values.restrict_update_only
        values.restrict_mode = "update-only"

    # Because the traditional argument parsing doesn't allow to validate the
    # number of locations for each action, we need to do it ourselves

    # number of locations for each action, a negative value represents a minimum
    locs_action_lens = {
            "backup": 2,
            "calculate": -1,
            "compare": 2,
            "info": 0,
            "list": 1,
            "regress": 1,
            "remove": 1,
            "restore": 2,
            "server": 0,
            "verify": -1,
        }

    locs_len = len(values.locations)
    if locs_action_lens[values.action] >= 0 and locs_action_lens[values.action] != locs_len:
        parser.error(message="Action {act} requires {nr} location(s) instead of {locs}.".format(
            act=values.action, nr=locs_action_lens[values.action], locs=values.locations))
    elif locs_action_lens[values.action] < 0 and -locs_action_lens[values.action] > locs_len:
        parser.error(message="Action {act} requires at least {nr} location(s) instead of {locs}.".format(
            act=values.action, nr=-locs_action_lens[values.action], locs=values.locations))
    elif values.action == "verify" and values.entity == "files" and locs_len != 1:
        parser.error(message="Action verify/files requires 1 location instead of {locs}.".format(
            locs=values.locations))

    return values


def _add_version_option_to_parser(parser, version_string):
    """
    Adds the version option to the given parser, setup with the given
    version string.
    """

    parser.add_argument(
        "-V", "--version", action="version", version=version_string,
        help="[opt] output the rdiff-backup version and exit")


# === MAIN ===


if __name__ == "__main__":
    """
    We simulate the usage of arguments parsing in rdiff-backup.
    Call `python3 arguments.py [--new] --help` for usage.
    """
    actions = BaseAction.get_actions()
    values = parse(sys.argv[1:], "british-agent 0.0.7",
                   PARENT_PARSERS, actions)
    action_object = actions[values.action](values)
    action_object.print_values()
    # in real life, the action_object would then do the action for which
    # it's been created
