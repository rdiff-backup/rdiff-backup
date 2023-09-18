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
Command-line arguments parsing module.

This module offers mainly a function `parse` to parse command line
arguments using Python's argparse module and return an
argparse.Namespace object with the parsed arguments.
The main section at the very end of this module offers an example on how
to use it.
"""

import argparse
import sys

# === WORKAROUND ===


def parse_args(parser, args):
    """
    Function overwriting the default exit code for parsing errors

    Once we're only supporting Python 3.9+ we can use the exit_on_error=False
    option and simply catch ArgumentError
    """
    try:
        parsed_args = parser.parse_args(args)
    except SystemExit as exc:
        if exc.code != 0:
            exc.code = 1
        raise
    return parsed_args

# === FUNCTIONS ===


def parse(args, version_string, generic_parsers, actions_dict=None):
    """
    Parse the given command-line arguments.

    Parses the given arguments, using the version string for --version,
    the generic_parsers is a list of argument parsers common to all actions,
    actions_dict is a dictionary of the form `{"action_name": ActionClass}`.

    Returns an argparse Namespace containing the parsed parameters.
    """
    parser = get_parser(version_string, generic_parsers, actions_dict)
    parsed_args = parse_args(parser, args)

    if not (sys.version_info.major >= 3 and sys.version_info.minor >= 7):
        # we need a work-around as long as Python 3.6 doesn't know about required
        if not parsed_args.action:
            parser.error(message="the following arguments are required: action")

    return parsed_args


def get_parser(version_string, parent_parsers, actions_dict):
    """
    Generates an argparse parser from the given parameters
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

    for action in actions_dict.values():
        action.add_action_subparser(sub_handler)

    return parser


def _add_version_option_to_parser(parser, version_string):
    """
    Adds the version option to the given parser

    The option is setup with the given version string.

    Returns nothing, the parser is modified "in-place".
    """

    parser.add_argument(
        "-V", "--version", action="version", version=version_string,
        help="[opt] output the rdiff-backup version and exit")


# === MAIN ===


if __name__ == "__main__":
    """
    We simulate the usage of arguments parsing in rdiff-backup.
    Call `python3 arguments.py --help` for usage.
    """
    from rdiffbackup import actions_mgr
    disc_actions = actions_mgr.get_actions_dict()
    values = parse(sys.argv[1:], "british-agent 0.0.7",
                   actions_mgr.get_generic_parsers(),
                   disc_actions)
    action_object = disc_actions[values.action](values)
    action_object.print_values()
    # in real life, the action_object would then do the action for which
    # it's been created
