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
Definition of custom argparse options actions.
"""

import argparse
import sys


class SelectAction(argparse.Action):
    """
    argparse Action class which can handle placeholder selection options

    It adds all options of the type together under one default destination
    and keeps the same order as the arguments on the command line. E.g.

        --exclude value1 --include-perhaps --max 10

    is interpreted as

        selections=[('exclude', value1), ('include-perhaps', True), ('max', 10)]

    by just defining the arguments '--SELECT', '--SELECT-perhaps' and '--max'
    with the action 'SelectAction'.
    In this example, 'SELECT' is the placeholder, and 'selections' the default
    destination.
    """

    #: placeholder name to be used for creating the different options
    placeholder = "SELECT"
    #: name of the default namespace key holding the sorted list of options
    default_dest = "selections"

    def __init__(
        self,
        option_strings,
        dest,
        type=str,
        nargs=None,
        help=None,
        default=None,
        **kwargs,
    ) -> None:
        """
        Initialize the placeholder-argument object

        It makes sure that both exclude and include arguments are allowed,
        that booleans have a meaningful True value, and that all values are
        by default gathered under the same 'selections' destination.
        """
        # because the argparse framework always sets 'dest',
        # we need to guess if dest was explicitly set, and if not,
        # we can overwrite it with the default value
        if ("--" + dest.replace("_", "-")) in option_strings:
            dest = self.default_dest
        # we want to make sure that toggles/booleans have a correct value
        if type is bool and nargs is None:
            nargs = 0
            if default is None:
                default = True
        # replace placeholder with both include and exclude options
        include_opts = list(
            map(lambda x: x.replace(self.placeholder, "include"), option_strings)
        )
        exclude_opts = list(
            map(lambda x: x.replace(self.placeholder, "exclude"), option_strings)
        )
        if exclude_opts != include_opts:
            # SELECT was found hence we need to duplicate the options
            # and update accordingly the help text
            option_strings = exclude_opts + include_opts
            if help:
                help = help.replace(self.placeholder, "exclude/include")
                if default is None:
                    help += " (no default)"
                elif default:
                    help += " (default is include)"
                else:
                    help += " (default is exclude)"
        super().__init__(
            option_strings,
            dest,
            type=type,
            nargs=nargs,
            help=help,
            default=default,
            **kwargs,
        )

    def __call__(self, parser, namespace, values, option_string=None):
        """
        Append the selection criteria (option_string, values)

        They are added to the ordered list of selection criteria.
        """

        old_list = getattr(namespace, self.dest, [])
        # namespace is "too intelligent", it always returns None even if
        # the parameter isn't previously defined
        if old_list is None:
            old_list = []
        if "filelist" in option_string:  # we read the values from the file
            try:
                if option_string.endswith("-stdin"):
                    filename = "standard input"
                    fp = sys.stdin.buffer
                else:
                    filename = values
                    fp = open(filename, "rb")
                content = fp.read()
                fp.close()
            except OSError as exc:
                raise argparse.ArgumentError(self, exc)
            else:
                if option_string.endswith("-stdin"):
                    option_string = option_string[:-6]
                values = {"filename": filename, "content": content}
        # append the option string and values to the selections list
        if values == [] and self.default is not None:
            values = self.default
        setattr(
            namespace, self.dest, old_list + [(option_string.replace("--", ""), values)]
        )
