import argparse
import sys
import yaml


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

#### DEFINE PARENT PARSERS ####

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

#    parser.add_argument("--acls", default=True,
#        action=argparse.BooleanOptionalAction,
#        help="[sub] handle (or not) Access Control Lists")
#    parser.add_argument("--carbonfile", default=True,
#        action=argparse.BooleanOptionalAction,
#        help="[sub] handle (or not) carbon files on MacOS X")
#    parser.add_argument("--compare-inode", default=True,
#        action=argparse.BooleanOptionalAction,
#        help="[sub] compare (or not) inodes to decide if hard-linked files have changed")
#    parser.add_argument("--eas", default=True,
#        action=argparse.BooleanOptionalAction,
#        help="[sub] handle (or not) Extended Attributes")
#    parser.add_argument("--hard-links", default=True,
#        action=argparse.BooleanOptionalAction,
#        help="[sub] preserve (or not) hard links.")
#    parser.add_argument("--never-drop-acls", action="store_true",
#        help="[sub] exit with error instead of dropping acls or acl entries.")

#    parser.add_argument("--create-full-path", action="store_true",
#        help="[sub] create full necessary path to backup repository")
#    parser.add_argument("--compression", default=True,
#        action=argparse.BooleanOptionalAction,
#        help="[sub] compress (or not) snapshot and diff files")
#    parser.add_argument("--no-compression-regexp", type=str, metavar="REGEXP",
#        default= ("(?i).*\\.("
#                  "gz|z|bz|bz2|tgz|zip|zst|rpm|deb|"
#                  "jpg|jpeg|gif|png|jp2|mp3|mp4|ogg|ogv|oga|ogm|avi|wmv|"
#                  "mpeg|mpg|rm|mov|mkv|flac|shn|pgp|"
#                  "gpg|rz|lz4|lzh|lzo|zoo|lharc|rar|arj|asc|vob|mdf|tzst|webm"
#                  ")$"),
#        help="[sub] regexp to select files not being compressed")

STATISTICS_PARSER = argparse.ArgumentParser(
    add_help=False,
    description="[parent] options related to backup statistics")
STATISTICS_PARSER.add_argument(
    "--file-statistics", default=True, action=argparse.BooleanOptionalAction,
    help="[sub] do (or not) generate statistics file during backup")
STATISTICS_PARSER.add_argument(
    "--print-statistics", default=False, action=argparse.BooleanOptionalAction,
    help="[sub] print (or not) statistics after a successful backup")

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

#### END DEFINE PARENT PARSERS ####


def _add_common_options_to_parser(parser, version_string):
    """
    adds all common options to the given parser
    """
    parser.add_argument("--api-version", type=int,
        help="[opt] integer to set the API version forcefully used")
    parser.add_argument("--current-time", type=int,
        help="[opt] fake the current time in seconds (for testing)")
    parser.add_argument("--force", action="store_true",
        help="[opt] force action")
    parser.add_argument("--fsync", default=True,
        action=argparse.BooleanOptionalAction,
        help="[opt] do (or not) often sync the file system (_not_ doing it is faster but can be dangerous)")
    parser.add_argument("--null-separator", action="store_true",
        help="[opt] use null instead of newline in input and output files")
    parser.add_argument("--new", default=False,
        action=argparse.BooleanOptionalAction,
        help="[opt] enforce (or not) the usage of the new parameters")
    parser.add_argument("--override-chars-to-quote", type=str,
        metavar="CHARS_TO_QUOTE",
        help="[opt] string of characters to quote for safe storing")
    parser.add_argument("--parsable-output", action="store_true",
        help="[opt] output in computer parsable format")
    parser.add_argument("--remote-schema", "--remote-cmd", type=str,
        help="[opt] alternative command to call remotely rdiff-backup")
    parser.add_argument("--remote-tempdir", type=str, metavar="DIR_PATH",
        help="[opt] use path as temporary directory on the remote side")
    parser.add_argument("--restrict", type=str, metavar="DIR_PATH",
        help="[opt] restrict remote access to given path")
    parser.add_argument("--restrict-read-only", type=str, metavar="DIR_PATH",
        help="[opt] restrict remote access to given path, in read-only mode")
    parser.add_argument("--restrict-update-only", type=str, metavar="DIR_PATH",
        help="[opt] restrict remote access to given path, in backup update mode")
    parser.add_argument("--ssh-no-compression", action="store_true",
        help="[opt] use SSH without compression with default remote-schema")
    parser.add_argument("--tempdir", type=str, metavar="DIR_PATH",
        help="[opt] use given path as temporary directory")
    parser.add_argument("--terminal-verbosity", type=int,
        choices=range(0,10),
        help="[opt] verbosity on the terminal, default given by --verbosity")
    parser.add_argument("--use-compatible-timestamps", action="store_true",
        help="[sub] use hyphen '-' instead of colon ':' to represent time")
    parser.add_argument("-v", "--verbosity", type=int,
        choices=range(0,10), default=3,
        help="[opt] overall verbosity on terminal and in logfiles (default is 3)")
    parser.add_argument("-V", "--version",
        action="version", version=version_string,
        help="[opt] output the rdiff-backup version and exit")


def _parse_old(args, version_string):
    """
    Parse arguments according to old parameters of rdiff-backup.
    The hint in square brackets at the beginning of the help are in preparation
    for the new way of parsing:
        rdiff-backup <opt(ions)> <act(ion)> <sub(-options)> <paths>
    Note that actions are mutually exclusive and that '[act=]' will need to be
    split into an action and a sub-option.
    """

    parser = argparse.ArgumentParser(
        description="local/remote mirror and incremental backup")

    _add_common_options_to_parser(parser, version_string)

    action_group = parser.add_mutually_exclusive_group()
    action_group.add_argument(
        "-b", "--backup-mode",
        dest="action", action="store_const", const="backup",
        help="[act] back-up directory into back-up repository")
    action_group.add_argument("--calculate-average",
        dest="action", action="store_const", const="calculate-average",
        help="[act] calculate average across multiple statistic files")
    action_group.add_argument("--check-destination-dir",
        dest="action", action="store_const", const="check-destination-dir",
        help="[act] check-destination-dir")
    action_group.add_argument("--compare",
        dest="action", action="store_const", const="compare",
        help="[act] compare normal (at time now)")
    action_group.add_argument("--compare-at-time", type=str, metavar="AT_TIME",
        help="[act=] compare normal at given time")
    action_group.add_argument("--compare-hash",
        dest="action", action="store_const", const="compare-hash",
        help="[act] compare by hash (at time now)")
    action_group.add_argument("--compare-hash-at-time",
        type=str, metavar="AT_TIME",
        help="[act=] compare by hash at given time")
    action_group.add_argument("--compare-full",
        dest="action", action="store_const", const="compare-full",
        help="[act] compare full (at time now)")
    action_group.add_argument(
        "--compare-full-at-time", type=str, metavar="AT_TIME",
        help="[act=] compare full at given time")
    action_group.add_argument("--list-at-time", type=str, metavar="AT_TIME",
        help="[act=] list files and directories at given time")
    action_group.add_argument("--list-changed-since", type=str, metavar="AT_TIME",
        help="[act=] list changed files and directories since given time")
    action_group.add_argument("-l", "--list-increments",
        dest="action", action="store_const", const="list-increments",
        help="[act] list increments in backup repository")
    action_group.add_argument("--list-increment-sizes",
        dest="action", action="store_const", const="list-increment-sizes",
        help="[act] list increments and their size in backup repository")
    action_group.add_argument(
        "--remove-older-than", type=str, metavar="AT_TIME",
        help="[act=] remove increments older than given time")
    action_group.add_argument(
        "-r", "--restore-as-of", type=str, metavar="AT_TIME",
        help="[act=] restore files from repo as of given time")
    action_group.add_argument("-s", "--server",
        dest="action", action="store_const", const="server",
        help="[act] start rdiff-backup in server mode")
    action_group.add_argument("--test-server",
        dest="action", action="store_const", const="test-server",
        help="[act] test communication to multiple remote servers")
    action_group.add_argument("--verify",
        dest="action", action="store_const", const="verify",
        help="[act] verify hash values in backup repo (at time now)")
    action_group.add_argument("--verify-at-time", type=str, metavar="AT_TIME",
        help="[act=] verify hash values in backup repo (at given time)")

    parser.add_argument("--allow-duplicate-timestamps", action="store_true",
        help="[sub] ignore duplicate metadata while checking destination dir")
    parser.add_argument("--create-full-path", action="store_true",
        help="[sub] create full necessary path to backup repository")
    parser.add_argument("--SELECT", action=SelectAction, metavar="GLOB",
        help="[sub] SELECT files according to glob pattern")
    parser.add_argument("--SELECT-device-files",
        action=SelectAction, type=bool, default=True,
        help="[sub] SELECT device files")
    parser.add_argument("--SELECT-fifos",
        action=SelectAction, type=bool, default=True,
        help="[sub] SELECT fifo files")
    parser.add_argument("--SELECT-filelist",
        action=SelectAction, metavar="LIST_FILE",
        help="[sub] SELECT files according to list in given file")
    parser.add_argument("--SELECT-filelist-stdin",
        action=SelectAction, type=bool,
        help="[sub] SELECT files according to list from standard input")
    parser.add_argument("--SELECT-symbolic-links",
        action=SelectAction, type=bool, default=True,
        help="[sub] SELECT symbolic links")
    parser.add_argument("--SELECT-sockets",
        action=SelectAction, type=bool, default=True,
        help="[sub] SELECT socket files")
    parser.add_argument("--SELECT-globbing-filelist",
        action=SelectAction, metavar="GLOBS_FILE",
        help="[sub] SELECT files according to glob list in given file")
    parser.add_argument("--SELECT-globbing-filelist-stdin",
        action=SelectAction, type=bool,
        help="[sub] SELECT files according to glob list from standard input")
    parser.add_argument("--SELECT-other-filesystems",
        action=SelectAction, type=bool, default=True,
        help="[sub] SELECT files from other file systems than the source one")
    parser.add_argument("--SELECT-regexp",
        action=SelectAction, metavar="REGEXP",
        help="[sub] SELECT files according to regexp pattern")
    parser.add_argument("--SELECT-if-present",
        action=SelectAction, metavar="FILENAME",
        help="[sub] SELECT directory if it contains the given file")
    parser.add_argument("--SELECT-special-files",
        action=SelectAction, type=bool, default=True,
        help="[sub] SELECT all device, fifo, socket files, and symbolic links")
    parser.add_argument("--group-mapping-file", type=str, metavar="MAP_FILE",
        help="[sub] map groups according to file")
    parser.add_argument("--never-drop-acls", action="store_true",
        help="[sub] exit with error instead of dropping acls or acl entries.")
    parser.add_argument("--max-file-size",
        action=SelectAction, metavar="SIZE", type=int,
        help="[sub] exclude files larger than given size in bytes")
    parser.add_argument("--min-file-size",
        action=SelectAction, metavar="SIZE", type=int,
        help="[sub] exclude files smaller than given size in bytes")
    parser.add_argument("--acls", default=True,
        action=argparse.BooleanOptionalAction,
        help="[sub] handle (or not) Access Control Lists")
    parser.add_argument("--carbonfile", default=True,
        action=argparse.BooleanOptionalAction,
        help="[sub] handle (or not) carbon files on MacOS X")
    parser.add_argument("--compare-inode", default=True,
        action=argparse.BooleanOptionalAction,
        help="[sub] compare (or not) inodes to decide if hard-linked files have changed")
    parser.add_argument("--compression", default=True,
        action=argparse.BooleanOptionalAction,
        help="[sub] compress (or not) snapshot and diff files")
    parser.add_argument("--no-compression-regexp", type=str, metavar="REGEXP",
        default= ("(?i).*\\.("
                  "gz|z|bz|bz2|tgz|zip|zst|rpm|deb|"
                  "jpg|jpeg|gif|png|jp2|mp3|mp4|ogg|ogv|oga|ogm|avi|wmv|"
                  "mpeg|mpg|rm|mov|mkv|flac|shn|pgp|"
                  "gpg|rz|lz4|lzh|lzo|zoo|lharc|rar|arj|asc|vob|mdf|tzst|webm"
                  ")$"),
        help="[sub] regexp to select files not being compressed")
    parser.add_argument("--eas", default=True,
        action=argparse.BooleanOptionalAction,
        help="[sub] handle (or not) Extended Attributes")
    parser.add_argument("--file-statistics", default=True,
        action=argparse.BooleanOptionalAction,
        help="[sub] do (or not) generate statistics file during backup")
    parser.add_argument("--hard-links", default=True,
        action=argparse.BooleanOptionalAction,
        help="[sub] preserve (or not) hard links.")
    parser.add_argument("--preserve-numerical-ids", action="store_true",
        help="[sub] preserve user and group IDs instead of names")
    parser.add_argument("--print-statistics", action="store_true",
        help="[sub] print statistics after a successful backup")
    parser.add_argument("--user-mapping-file", type=str, metavar="MAP_FILE",
        help="[sub] map users according to file")

    parser.add_argument("locations", nargs='*',
        help="[args] locations remote and local to be handled by chosen action")

    values = parser.parse_args(args)

    # compatibility layer with new parameter handling
    if not values.action:
        if values.compare_at_time:
            values.action = "compare"
            values.method = "normal"
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
            values.changed_since_time = values.list_changed_since
        elif values.remove_older_than:
            values.action = "remove"
            values.entity = "increments"
            values.older_than = values.remove_older_than
        elif values.restore_as_of:
            values.action = "restore"
            values.at = values.restore_as_of
        elif values.verify_at_time:
            values.action = "verify"
            values.entity = "files"
            values.at = values.verify_at_time
        # if there is still no action defined, we set the default
        if not values.action:
            values.action = "backup"
    else:
        if values.action == "calculate-average":
            value.action = "calculate"
            values.method = "average"
        if values.action == "check-destination-dir":
            value.action = "regress"
        if values.action == "compare":
            values.method = "normal"
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
            values.sizes = True
        elif values.action == "test-server":
            value.action = "verify"
            values.entity = "servers"
        elif values.action == "verify":
            values.entity = "files"
            values.at = "now"

    return values


def _parse_new(args, version_string):
    parser = argparse.ArgumentParser(
        description="local/remote mirror and incremental backup",
        fromfile_prefix_chars='@')

    _add_common_options_to_parser(parser, version_string)

    sub_handler = parser.add_subparsers(
        title="possible actions",
        help="call '{bin} <action> --help' for more information".format(
            bin=sys.argv[0]))

    for action in BaseAction.get_actions():
        action.add_action_subparser(sub_handler)

    values = parser.parse_args(args)
    return values


class BaseAction:
    # name of the action
    name = "base"
    # list of parent parsers
    parent_parsers = []

    @classmethod
    def get_actions(cls):
        actions = {
                    "backup": BackupAction,
                    "calculate": CalculateAction,
                    "compare": CompareAction,
                    "list": ListAction,
                    "remove": RemoveAction,
                    "regress": RegressAction,
                    "restore": RestoreAction,
                    "server": ServerAction,
                    "verify": VerifyAction,
                  }
        return actions.values()

    @classmethod
    def add_action_subparser(cls, sub_handler):
        subparser = sub_handler.add_parser(cls.name,
                                           parents=cls.parent_parsers)
        subparser.set_defaults(action=cls.name)  # TODO cls instead of name!

        return subparser

    @classmethod
    def _get_subparsers(cls, parser, sub_dest, *sub_names):
        sub_handler = parser.add_subparsers()
        subparsers = {}
        for sub_name in sub_names:
            subparsers[sub_name] = sub_handler.add_parser(sub_name)
            subparsers[sub_name].set_defaults(**{sub_dest: sub_name})
        return subparsers

class BackupAction(BaseAction):
    name = "backup"
    parent_parsers = [SELECTION_PARSER, USER_GROUP_PARSER, STATISTICS_PARSER]

    @classmethod
    def add_action_subparser(cls, sub_handler):
        subparser = super().add_action_subparser(sub_handler)
        subparser.add_argument(
            "locations", metavar="LOCATION", nargs=2,
            help="locations of SOURCE_DIR and to which REPOSITORY to backup")
        return subparser

class CalculateAction(BaseAction):
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
    name = "compare"
    parent_parsers = [SELECTION_PARSER]

    @classmethod
    def add_action_subparser(cls, sub_handler):
        subparser = super().add_action_subparser(sub_handler)
        subparser.add_argument(
            "--method", choices=["meta", "full", "hash"], default="meta",
            help="use metadata, complete file or hash to compare directories")
        subparser.add_argument(
            "--at", metavar="TIME",
            help="compare with the backup at the given time, default is 'now'")
        subparser.add_argument(
            "locations", metavar="LOCATION", nargs=2,
            help="locations of SOURCE_DIR and backup REPOSITORY to compare"
                 " (same order as for a backup)")
        return subparser


class ListAction(BaseAction):
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
            "--at", metavar="TIME",
            help="list files at given time")
        entity_parsers["files"].add_argument(
            "locations", metavar="REPOSITORY_LOCATION", nargs=1,
            help="location of repository to list files from")
        entity_parsers["increments"].add_argument(
            "--sizes", action=argparse.BooleanOptionalAction, default=False,
            help="also output size of each increment (might take longer)")
        entity_parsers["increments"].add_argument(
            "locations", metavar="REPOSITORY_LOCATION", nargs=1,
            help="location of repository to list increments from")
        return subparser


class RegressAction(BaseAction):
    name = "regress"
    parent_parsers = [USER_GROUP_PARSER]

    @classmethod
    def add_action_subparser(cls, sub_handler):
        subparser = super().add_action_subparser(sub_handler)
        subparser.add_argument(
            "--allow-duplicate-timestamps", action="store_true",
            help="[sub] ignore duplicate metadata while checking repository")
        subparser.add_argument(
            "locations", metavar="REPOSITORY_LOCATION", nargs=1,
            help="location of repository to check and possibly regress")
        return subparser


class RemoveAction(BaseAction):
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
            "locations", metavar="REPOSITORY_LOCATION", nargs=1,
            help="location of repository to remove increments from")
        return subparser


class RestoreAction(BaseAction):
    name = "restore"
    parent_parsers = [SELECTION_PARSER, USER_GROUP_PARSER]

    @classmethod
    def add_action_subparser(cls, sub_handler):
        subparser = super().add_action_subparser(sub_handler)
        subparser.add_argument(
            "--at", default="now", metavar="TIME",
            help="as of which time to restore the files (default is now)")
        subparser.add_argument(
            "locations", metavar="LOCATION", nargs=2,
            help="locations of backup REPOSITORY and to which TARGET_DIR to restore")
        return subparser

class ServerAction(BaseAction):
    name = "server"
    # server has no specific sub-options

class VerifyAction(BaseAction):
    name = "verify"

    @classmethod
    def add_action_subparser(cls, sub_handler):
        subparser = super().add_action_subparser(sub_handler)
        entity_parsers = cls._get_subparsers(
            subparser, "entity", "files", "servers")
        entity_parsers["files"].add_argument(
            "--at", default="now", metavar="TIME",
            help="at which time to check the files' hashes (default is now)")
        entity_parsers["files"].add_argument(
            "locations", metavar="REPOSITORY_LOCATION", nargs=1,
            help="location of repository where to check files' hashes")
        entity_parsers["servers"].add_argument(
            "locations", metavar="REPOSITORY_LOCATIONS", nargs="+",
            help="location of remote repositories to check for connection")
        return subparser


def parse(args, version_string):
    if ('--new' in args
            or ('--api-version' in args and not '--no-new' in args)
            or (any(map(lambda x: x.startswith('@'), args)))):
        return _parse_new(args, version_string)
    else:
        return _parse_old(args, version_string)


if __name__ == "__main__":
    parsed_args = parse(sys.argv[1:], "british-agent 0.0.7")
    print(yaml.safe_dump(parsed_args.__dict__,
                         explicit_start=True, explicit_end=True))
