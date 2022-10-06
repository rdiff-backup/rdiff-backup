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

DEPRECATION_MESSAGE = (
    "WARNING: this command line interface is deprecated and will "
    "disappear, start using the new one as described with '--new --help'."
)

# === FUNCTIONS ===


def parse(args, version_string, generic_parsers, parent_parsers, actions_dict=None):
    """
    Parse the given command-line arguments.

    Parses the given arguments, using the version string for --version,
    the generic_parsers is a list of argument parsers common to all actions,
    parent_parsers is a concanated list of all parsers used by all actions
    so that the compatibility command line can be simulated.
    And actions is a dictionary of the form `{"action_name": ActionClass}`.

    Returns an argparse Namespace containing the parsed parameters.
    """
    # we try to recognize if the user wants the old or the new parameters
    # it's the case if --new is explicitly given, or if any parameter starts
    # with an @ (meaning read from file), or if api-version or help is used,
    # or if any of the action names is found in the parameters,
    # without `--no-new` being found. We also explicitly check `complete`
    # because it could be _followed_ by `--no-new`.
    # note: `set1 & set2` is the intersection of two sets
    if ('--new' in args or 'complete' in args
            or (any(map(lambda x: x.startswith('@'), args)))
            or ('--no-new' not in args
                and ('--api-version' in args or '--help' in args
                     or (set(actions_dict.keys()) & set(args))))):
        return _parse_new(args, version_string, generic_parsers, actions_dict)
    else:
        return _parse_compat200(args, version_string, generic_parsers + parent_parsers)


def get_parser_new(version_string, parent_parsers, actions_dict):
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


def _parse_new(args, version_string, parent_parsers, actions_dict):
    """
    Parse arguments according to new parameters of rdiff-backup, i.e.

        rdiff-backup <opt(ions)> <act(ion)> <sub(-options)> <paths>
    """
    parser = get_parser_new(version_string, parent_parsers, actions_dict)
    parsed_args = parser.parse_args(args)

    if not (sys.version_info.major >= 3 and sys.version_info.minor >= 7):
        # we need a work-around as long as Python 3.6 doesn't know about required
        if not parsed_args.action:
            parser.error(message="the following arguments are required: action")

    return parsed_args


def get_parser_compat200(version_string, parent_parsers=[]):
    """
    Get a parser according to old parameters of rdiff-backup.
    """

    parser = argparse.ArgumentParser(
        description="local/remote mirror and incremental backup "
                    "(deprecated interface)",
        epilog=DEPRECATION_MESSAGE,
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
        dest="action", action="store_const", const="test",
        help="[act] test communication to one or multiple remote servers")
    action_group.add_argument(
        "--verify", dest="action", action="store_const", const="verify",
        help="[act] verify hash values in backup repo (at time now)")
    action_group.add_argument(
        "--verify-at-time", type=str, metavar="AT_TIME",
        help="[act=] verify hash values in backup repo (at given time)")

    parser.add_argument(
        "locations", nargs='*',
        help="[args] locations remote and local to be handled by chosen action")

    return parser


def _parse_compat200(args, version_string, parent_parsers=[]):
    """
    Parse arguments according to old parameters of rdiff-backup.

    The hint in square brackets at the beginning of the help are in preparation
    for the new way of parsing:

        rdiff-backup <opt(ions)> <act(ion)> <sub(-options)> <paths>

    Note that actions are mutually exclusive and that '[act=]' will need to be
    split into an action and a sub-option.
    """

    parser = get_parser_compat200(version_string, parent_parsers)
    values = parser.parse_args(args)

    _make_values_like_new_compat200(values)
    _validate_number_locations_compat200(values, parser)

    if "--no-new" not in args:
        sys.stderr.write(DEPRECATION_MESSAGE + "\n")

    return values


def _make_values_like_new_compat200(values):  # noqa C901 "too complex"
    """
    Return the Namespace values transformed into new model.

    A helper function which returns the Namespace values parsed by the old CLI
    as if they had been parsed by the new CLI.
    """

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
            values.changed_since = None
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
            values.size = False
        elif values.action == "list-increment-sizes":
            values.action = "list"
            values.entity = "increments"
            values.size = True
        elif values.action == "restore":
            values.increment = True
            values.at = None
        elif values.action == "verify":
            values.at = "now"

    # those are a bit critical because they are duplicates between
    # new and old options
    if values.ssh_no_compression is True:
        values.ssh_compression = False
    if values.action == "server" and not values.restrict_path:
        # if restrict_path would have been set, it would have had priority
        if values.restrict:
            values.restrict_path = values.restrict
            values.restrict_mode = "read-write"
        elif values.restrict_read_only:
            values.restrict_path = values.restrict_read_only
            values.restrict_mode = "read-only"
        elif values.restrict_update_only:
            values.restrict_path = values.restrict_update_only
            values.restrict_mode = "update-only"

    return values


def _validate_number_locations_compat200(values, parser):
    """
    Validate the expected number of locations for each action.

    Because the traditional argument parsing doesn't allow to validate the
    number of locations for each action, we need to do it ourselves
    """

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
        "test": -1,
        "verify": 1,
    }

    locs_len = len(values.locations)
    if (locs_action_lens[values.action] >= 0
            and locs_action_lens[values.action] != locs_len):
        parser.error(message="Action {act} requires {nr} location(s) "
                     "instead of {locs}.".format(
                         act=values.action, nr=locs_action_lens[values.action],
                         locs=values.locations))
    elif (locs_action_lens[values.action] < 0
            and -locs_action_lens[values.action] > locs_len):
        parser.error(message="Action {act} requires at least {nr} location(s) "
                     "instead of {locs}.".format(
                         act=values.action, nr=-locs_action_lens[values.action],
                         locs=values.locations))


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
    Call `python3 arguments.py [--new] --help` for usage.
    """
    from rdiffbackup import actions_mgr
    disc_actions = actions_mgr.get_actions_dict()
    values = parse(sys.argv[1:], "british-agent 0.0.7",
                   actions_mgr.get_generic_parsers(),
                   actions_mgr.get_parent_parsers_compat200(),
                   disc_actions)
    action_object = disc_actions[values.action](values)
    action_object.print_values()
    # in real life, the action_object would then do the action for which
    # it's been created
