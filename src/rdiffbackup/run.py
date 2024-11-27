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
from rdiff_backup import log
from rdiffbackup import arguments, actions_mgr
from rdiffbackup.singletons import consts, generics, specifics

if os.name == "nt":
    import msvcrt


def main():
    if os.name == "nt":
        # make sure line endings are kept under Windows like under Linux
        msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
        msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
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
        arglist,
        "rdiff-backup {ver}".format(ver=specifics.version),
        actions_mgr.get_generic_parsers(),
        discovered_actions,
    )

    # setup the system settings globally
    ret_val = _system_setup(parsed_args)
    if ret_val & consts.RET_CODE_ERR:
        return ret_val

    # instantiate the action object from the dictionary, handing over the
    # parsed arguments
    action = discovered_actions[parsed_args["action"]](parsed_args)

    log.Log(
        "Runtime information =>{ri}<=".format(
            ri=action.get_runtime_info(parsed=parsed_args)
        ),
        log.DEBUG,
    )

    # validate that everything looks good before really starting
    ret_val |= action.pre_check()
    if ret_val & consts.RET_CODE_ERR:
        log.Log(
            "Action {ac} failed on step {st}".format(
                ac=parsed_args["action"], st="pre_check"
            ),
            log.ERROR,
        )
        return ret_val

    # now start for real, conn_act and action are the same object
    with action.connect() as conn_act:
        if not conn_act.is_connection_ok():
            log.Log(
                "Action {ac} failed on step {st}".format(
                    ac=parsed_args["action"], st="connect"
                ),
                log.ERROR,
            )
            return conn_act.conn_status

        # For test purposes only, hence we allow ourselves to overwrite a
        # "private" variable
        if security_override:
            from rdiff_backup import Security

            Security._security_level = "override"

        ret_val |= conn_act.check()
        if ret_val & consts.RET_CODE_ERR:
            log.Log(
                "Action {ac} failed on step {st}".format(
                    ac=parsed_args["action"], st="check"
                ),
                log.ERROR,
            )
            return ret_val

        ret_val |= conn_act.setup()
        if ret_val & consts.RET_CODE_ERR:
            log.Log(
                "Action {ac} failed on step {st}".format(
                    ac=parsed_args["action"], st="setup"
                ),
                log.ERROR,
            )
            return ret_val

        ret_val |= conn_act.run()
        if ret_val & consts.RET_CODE_ERR:
            log.Log(
                "Action {ac} failed on step {st}".format(
                    ac=parsed_args["action"], st="run"
                ),
                log.ERROR,
            )
            return ret_val

    # Give a final summary of what might have happened to the user
    if ret_val & consts.RET_CODE_WARN:
        log.Log(
            "Action {ac} emitted warnings, "
            "see previous messages for details".format(ac=parsed_args["action"]),
            log.WARNING,
        )
    if ret_val & consts.RET_CODE_FILE_ERR:
        log.Log(
            "Action {ac} failed on one or more files, "
            "see previous messages for details".format(ac=parsed_args["action"]),
            log.WARNING,
        )
    if ret_val & consts.RET_CODE_FILE_WARN:
        log.Log(
            "Action {ac} emitted a warning on one or more files, "
            "see previous messages for details".format(ac=parsed_args["action"]),
            log.WARNING,
        )

    return ret_val


def _system_setup(arglist):
    """
    Parse argument list and set global preferences, compatibility function
    between old and new way of parsing parameters.
    """
    # we need verbosity set properly asap
    ret_val = log.Log.set_verbosity(
        arglist.get("verbosity"), arglist.get("terminal_verbosity")
    ) | log.Log.set_parsable(arglist.get("parsable_output"))
    if ret_val & consts.RET_CODE_ERR:
        return ret_val
    if arglist.get("api_version") is not None:  # FIXME catch also env variable?
        specifics.set_api_version(arglist.get("api_version"))

    # if action in ("backup", "restore"):
    generics.set("compare_inode", arglist.get("compare_inode"))
    generics.set("never_drop_acls", arglist.get("never_drop_acls"))
    # if action in ("backup", "regress", "restore"):
    generics.set("compression", arglist.get("compression"))
    # if action in ("regress"):
    generics.set(
        "allow_duplicate_timestamps", arglist.get("allow_duplicate_timestamps")
    )
    # generic settings
    generics.set("null_separator", arglist.get("null_separator"))
    generics.set("use_compatible_timestamps", arglist.get("use_compatible_timestamps"))
    generics.set("do_fsync", arglist.get("fsync"))
    if arglist.get("chars_to_quote") is not None:
        generics.set("chars_to_quote", os.fsencode(arglist.get("chars_to_quote")))
    return ret_val


if __name__ == "__main__":
    main()
