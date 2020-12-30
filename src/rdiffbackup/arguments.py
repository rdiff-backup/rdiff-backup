import argparse
import sys

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


def _parse_old(args):
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
    parser.add_argument("--old", action="store_true",
        help="[opt] enforce the usage of the old parameters")
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
    parser.add_argument("-v", "--verbosity", type=int,
        choices=range(0,10), default=3,
        help="[opt] overall verbosity on terminal and in logfiles (default is 3)")

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
    action_group.add_argument("--remove-older-than", type=str, metavar="AT_TIME",
        help="[act] remove increments older than given time")
    action_group.add_argument("-r", "--restore-as-of", type=str, metavar="AT_TIME",
        help="[act] restore files from repo as of given time")
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
        help="[act] verify hash values in backup repo (at given time)")
    action_group.add_argument("-V", "--version",
        dest="action", action="store_const", const="version",
        help="[act] output the rdiff-backup version and exit")

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
        default= (b"(?i).*\\.("
                  b"gz|z|bz|bz2|tgz|zip|zst|rpm|deb|"
                  b"jpg|jpeg|gif|png|jp2|mp3|mp4|ogg|ogv|oga|ogm|avi|wmv|"
                  b"mpeg|mpg|rm|mov|mkv|flac|shn|pgp|"
                  b"gpg|rz|lz4|lzh|lzo|zoo|lharc|rar|arj|asc|vob|mdf|tzst|webm"
                  b")$"),
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
    parser.add_argument("--use-compatible-timestamps", action="store_true",
        help="[sub] use hyphen instead of colon to represent time")
    parser.add_argument("--user-mapping-file", type=str, metavar="MAP_FILE",
        help="[sub] map users according to file")

    parser.add_argument("paths", nargs='*',
        help="[args] paths to be handled by the chosen action")

    values = parser.parse_args(args)

    if (not values.action):
        if (values.restore_as_of):
            values.action = "restore"

    return values


def _parse_new(args):
    parser = argparse.ArgumentParser(
        description="local/remote mirror and incremental backup")
    parser.add_argument(
        "-v", "--verbose",
        type=int, default=3, choices=range(1,10),
        help="Set the verbosity from 1 (low) to 9 (debug)")
    parser.add_argument(
        "-V", "--version", action="store_true",
        help="Output the version and exit")
    parser.add_argument(
        "--current-time",
        type=int,
        help="fake the current time instead of using the real one")
    parser.add_argument(
        "--force", action="store_true",
        help="enforces certain risky behaviors, like overwriting existing files, use with care!")

    subparsers = parser.add_subparsers(
        title="actions", help="possible actions")

    parsers = {}

    parsers["backup"] = subparsers.add_parser("backup")
    parsers["backup"].set_defaults(action="backup")

    parsers["calculate-average"] = subparsers.add_parser("calculate-average", aliases=["ca"])
    parsers["calculate-average"].set_defaults(action="calculate-average")

    parsers["check-destination-dir"] = subparsers.add_parser("check-destination-dir", aliases=["cdd"])
    parsers["check-destination-dir"].set_defaults(action="check-destination-dir")
    parsers["check-destination-dir"].add_argument(
        "--allow-duplicate-timestamps",
        action="store_true", default=False,
        help="use this option only if you encounter duplicate metadata mirrors")

    parsers["compare"] = subparsers.add_parser("compare")
    parsers["compare"].set_defaults(action="compare")
    parsers["compare"].add_argument(
            "--method",
            type=str, default="meta", choices=["meta","full","hash"],
            help="use metadata, complete file or hash to compare directories")
    parsers["compare"].add_argument(
            "--at-time",
            type=str, default="now",
            help="compare with the backup at the given time, default is 'now'")

    parsers["list"] = subparsers.add_parser("list")
    parsers["list"].set_defaults(action="list")
    # at-time, changed-since, increments, increment-sizes [repo] [subdir]

    parsers["verify"] = subparsers.add_parser("verify")
    parsers["verify"].set_defaults(action="verify")
    parsers["verify"].add_argument(
            "--at-time",
            type=str, default="now",
            help="verify the backup at the given time, default is 'now'")

    # --carbonfile Enable backup of MacOS X carbonfile information.
    # --create-full-path
    # --group-mapping-file, --user-mapping-file

    # PARENT: --exclude... --include... --max-file-size --min-file-size

    values = parser.parse_args(args)
    return values


def parse(args):
    if ('--new' in args
            or ('--api-version' in args and not '--old' in args)
            or (any(map(lambda x: x.startswith('@'), args)))):
        return _parse_new(args)
    else:
        return _parse_old(args)


if __name__ == "__main__":
    print(parse(sys.argv[1:]))
