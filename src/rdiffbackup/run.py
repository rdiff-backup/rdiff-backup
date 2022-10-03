# Copyright 2002, 2003, 2004, 2005 Ben Escoto
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
"""Start (and end) here - read arguments, set global settings, etc."""

import os
import sys
from rdiff_backup import Globals, log
from rdiffbackup import arguments, actions_mgr, actions

try:
    import msvcrt

    # make sure line endings are kept under Windows like under Linux
    msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
    msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
except ImportError:
    pass


def main():
    sys.exit(main_run(sys.argv[1:]))


def main_run(arglist, security_override=False):
    """
    Main function to be called with arguments list without the
    name of the program, aka $0 resp. sys.argv[0].

    The security override is only meant for test purposes.

    Returns with an error code depending on the result.
    Check the man-page of the rdiff-backup binary for possible values
    and their meaning.
    """

    # get a dictionary of discovered action plugins
    discovered_actions = actions_mgr.get_actions_dict()

    # parse accordingly the arguments
    parsed_args = arguments.parse(
        arglist, "rdiff-backup {ver}".format(ver=Globals.version),
        actions_mgr.get_generic_parsers(),
        actions_mgr.get_parent_parsers_compat200(),
        discovered_actions)

    # we need verbosity set properly asap
    if parsed_args.terminal_verbosity is not None:
        log.Log.setterm_verbosity(parsed_args.terminal_verbosity)
    log.Log.setverbosity(parsed_args.verbosity)

    # compatibility plug
    _parse_cmdlineoptions_compat200(parsed_args)

    # instantiate the action object from the dictionary, handing over the
    # parsed arguments
    action = discovered_actions[parsed_args.action](parsed_args)

    log.Log("Runtime information =>{ri}<=".format(
        ri=Globals.get_runtime_info(parsed=vars(parsed_args))), log.DEBUG)

    # validate that everything looks good before really starting
    ret_val = action.pre_check()
    if ret_val & Globals.RET_CODE_ERR:
        log.Log("Action {ac} failed on step {st}".format(
            ac=parsed_args.action, st="pre_check"), log.ERROR)
        return ret_val

    # now start for real, conn_act and action are the same object
    with action.connect() as conn_act:

        # For test purposes only, hence we allow ourselves to overwrite a
        # "private" variable
        if security_override:
            from rdiff_backup import Security
            Security._security_level = "override"

        ret_val |= conn_act.check()
        if ret_val & Globals.RET_CODE_ERR:
            log.Log("Action {ac} failed on step {st}".format(
                ac=parsed_args.action, st="check"), log.ERROR)
            return ret_val

        ret_val |= conn_act.setup()
        if ret_val & Globals.RET_CODE_ERR:
            log.Log("Action {ac} failed on step {st}".format(
                ac=parsed_args.action, st="setup"), log.ERROR)
            return ret_val

        ret_val |= conn_act.run()
        if ret_val & Globals.RET_CODE_ERR:
            log.Log("Action {ac} failed on step {st}".format(
                ac=parsed_args.action, st="run"), log.ERROR)
            return ret_val

    # Give a final summary of what might have happened to the user
    if ret_val & Globals.RET_CODE_WARN:
        log.Log("Action {ac} emitted warnings, "
                "see previous messages for details".format(
                    ac=parsed_args.action), log.WARNING)
    if ret_val & Globals.RET_CODE_FILE_ERR:
        log.Log("Action {ac} failed on one or more files, "
                "see previous messages for details".format(
                    ac=parsed_args.action), log.WARNING)
    if ret_val & Globals.RET_CODE_FILE_WARN:
        log.Log("Action {ac} emitted a warning on one or more files, "
                "see previous messages for details".format(
                    ac=parsed_args.action), log.WARNING)

    return ret_val


def _parse_cmdlineoptions_compat200(arglist):  # noqa: C901
    """
    Parse argument list and set global preferences, compatibility function
    between old and new way of parsing parameters.
    """

    if arglist.action in ('backup', 'restore'):
        Globals.set("acls_active", arglist.acls)
        Globals.set("win_acls_active", arglist.acls)
        Globals.set("carbonfile_active", arglist.carbonfile)
        Globals.set("compare_inode", arglist.compare_inode)
        Globals.set("eas_active", arglist.eas)
        Globals.set("preserve_hardlinks", arglist.hard_links)
        Globals.set("resource_forks_active", arglist.resource_forks)
        Globals.set("never_drop_acls", arglist.never_drop_acls)
    if arglist.action in ('backup', 'regress', 'restore'):
        Globals.set("compression", arglist.compression)
        Globals.set("no_compression_regexp_string",
                    os.fsencode(arglist.not_compressed_regexp))
    else:
        Globals.set("no_compression_regexp_string",
                    os.fsencode(actions.DEFAULT_NOT_COMPRESSED_REGEXP))
    if arglist.action in ('server'):
        Globals.server = True
    if arglist.action in ('backup'):
        Globals.set("file_statistics", arglist.file_statistics)
        Globals.set("print_statistics", arglist.print_statistics)
    if arglist.action in ('regress'):
        Globals.set("allow_duplicate_timestamps",
                    arglist.allow_duplicate_timestamps)
    Globals.set("null_separator", arglist.null_separator)
    Globals.set("use_compatible_timestamps", arglist.use_compatible_timestamps)
    Globals.set("do_fsync", arglist.fsync)
    if arglist.current_time is not None:
        Globals.set_integer('current_time', arglist.current_time)
    if arglist.chars_to_quote is not None:
        Globals.set('chars_to_quote', os.fsencode(arglist.chars_to_quote))
    if arglist.api_version is not None:  # FIXME
        Globals.set_api_version(arglist.api_version)


if __name__ == "__main__":
    main()
