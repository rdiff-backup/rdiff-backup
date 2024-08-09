# Copyright 2021-2022 the rdiff-backup project
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
A built-in rdiff-backup action plug-in to output which options are possible
so that they can be used for e.g. bash completion
"""

import argparse

from rdiff_backup import Globals, log
from rdiffbackup import actions, actions_mgr, arguments
from rdiffbackup.singletons import consts
from rdiffbackup.utils.argopts import BooleanOptionalAction


class CompleteAction(actions.BaseAction):
    """
    Output possible options given the current command line state
    """

    name = "complete"
    security = None

    @classmethod
    def add_action_subparser(cls, sub_handler):
        subparser = super().add_action_subparser(sub_handler)
        # argument names aligned with bash completion
        subparser.add_argument(
            "--cword",
            type=int,
            default="-1",
            help="An index on the words where the cursor is",
        )
        subparser.add_argument(
            "--unique",
            default=True,
            action=BooleanOptionalAction,
            help="Only output options which haven't been entered yet",
        )
        subparser.add_argument(
            "words",
            type=str,
            nargs="*",
            help="list of words already typed on the command line (after --)",
        )
        return subparser

    def pre_check(self):
        ret_code = super().pre_check()

        if not self.values["words"]:
            log.Log(
                "There must be at least one word, "
                "the command rdiff-backup itself, to complete",
                log.ERROR,
            )
            ret_code |= consts.RET_CODE_ERR

        try:
            self.values["words"][self.values["cword"]]
        except IndexError:
            log.Log(
                "The word count {wc} isn't within range of the "
                "words list {wl}".format(
                    wc=self.values["cword"], wl=self.values["words"]
                ),
                log.ERROR,
            )
            ret_code |= consts.RET_CODE_ERR

        return ret_code

    def setup(self):
        # there is nothing to setup for the complete action
        return consts.RET_CODE_OK

    def run(self):
        ret_code = super().run()
        if ret_code & consts.RET_CODE_ERR:
            return ret_code

        # get a dictionary of discovered action plugins
        discovered_actions = actions_mgr.get_actions_dict()
        generic_parsers = actions_mgr.get_generic_parsers()
        version_string = "rdiff-backup {ver}".format(ver=Globals.version)

        parser = arguments.get_parser(
            version_string, generic_parsers, discovered_actions
        )

        possible_options = self._get_possible_options(
            parser, self.values["words"], self.values["cword"], self.values["unique"]
        )

        for option in possible_options:
            print(option)

        return ret_code

    def _get_possible_options(self, parser, words, cword, unique):
        # a negative index needs to be made positive
        # this can only happen when calling directly the complete action
        if cword < 0:
            cword += len(words)
            if cword < 0:
                log.Log("Word index is too negative, can't complete", log.ERROR)
                return []
        # a condition which can only happen
        # this can only happen when calling directly the complete action
        if len(words) == 1 or cword == 0:
            return [words[0]]

        log.Log(
            "Words '{ws}' with index '{cw}' being completed".format(ws=words, cw=cword),
            log.DEBUG,
        )
        opts, subs, args = self._get_options_dict(parser)
        opts_and_subs = dict(**opts, **subs)  # FIXME use | starting with 3.9

        # the simple case, the first option is being entered
        if len(words) == 2:
            return self._get_matching_options(opts_and_subs, args, words, cword, unique)

        # we try to identify the action used with the new CLI
        action_idx = None
        for idx, word in enumerate(words):
            if word in subs:
                action_idx = idx
                break

        if action_idx is None:
            return self._get_matching_options(opts_and_subs, args, words, cword, unique)
        else:  # an action has been recognized
            if cword == action_idx:
                return [word]
            elif cword > action_idx:
                return self._get_possible_sub_options(
                    subs[word], words[action_idx:], cword - action_idx, unique
                )
            else:
                return self._get_matching_options(opts, args, words, cword, unique)

    def _get_possible_sub_options(self, parser, words, cword, unique):
        log.Log(
            "Words '{ws}' with index '{cw}' being completed".format(ws=words, cw=cword),
            log.DEBUG,
        )
        opts, subs, args = self._get_options_dict(parser)

        # the simple case, the first option is being entered
        if len(words) == 2:
            options = dict(opts, **subs)
            return self._get_matching_options(options, args, words, cword, unique)

        # identify the sub-action used if there is one
        action_idx = None
        for idx, word in enumerate(words):
            if word in subs:
                action_idx = idx
                break

        if action_idx is not None:
            if cword == action_idx:
                return {word}
            elif cword > action_idx:
                return self._get_possible_sub_options(
                    subs[word], words[action_idx:], cword - action_idx, unique
                )
        else:
            return self._get_matching_options(
                dict(opts, **subs), args, words, cword, unique
            )

    def _get_matching_options(self, options, args, words, cword, unique=True):
        """
        Return a sorted sequence of options matching the words given

        If files should be matched, a placeholder '::file::' is added at the
        end of the sequence.
        """
        word = words[cword]
        prev_word = words[cword - 1]
        # first check if the previous option has a parameter
        if prev_word in options:
            prev_option = options[prev_word]
            # the type is just a trick to recognize options with parameters
            if (
                hasattr(prev_option, "type")
                and prev_option.type
                and prev_option.type != bool
            ):
                if hasattr(prev_option, "choices") and prev_option.choices:
                    return prev_option.choices
                elif isinstance(prev_option.type, argparse.FileType) or (
                    prev_option.type == str
                    and isinstance(prev_option.metavar, str)
                    and prev_option.metavar.endswith("_FILE")
                ):
                    return ["::file::"]
                else:  # we can't make any statement about the parameter
                    return []
        is_matched = False
        if word:
            options = {opt: options[opt] for opt in options if opt.startswith(word)}
            if options:
                is_matched = True
        if unique:  # remove options already listed
            options_set = set(options) - set(words)
            if word and word in options:
                options_set |= {word}
        # we sort the options without taking care of dashes
        options_list = sorted(options_set, key=lambda x: x.replace("-", ""))
        if (
            not is_matched
            and "locations" in args
            and (
                args["locations"].nargs == "*"
                or cword >= (len(words) - args["locations"].nargs)
            )
        ):
            options_list.append("::file::")
        return options_list

    def _get_options_dict(self, parser):
        """
        Extract the options as dictionary from an argparse parser

        Returns three dictionaries, one with the options, one with the
        sub-commands/actions/parsers, and one with the arguments
        (mainly locations).
        """
        opts = {}
        subs = {}
        args = {}
        for action in parser._actions:  # internals of argparse!
            if isinstance(action, argparse._SubParsersAction):
                subs.update(action.choices)
            elif action.option_strings:
                for opt in action.option_strings:
                    opts[opt] = action
            else:
                args[action.dest] = action
        return opts, subs, args


def get_plugin_class():
    return CompleteAction
