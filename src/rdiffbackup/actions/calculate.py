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
A built-in rdiff-backup action plug-in to calculate average across multiple
statistics files.
"""

from rdiff_backup import Time
from rdiffbackup import actions
from rdiffbackup.singletons import consts, log, stats


class CalculateAction(actions.BaseAction):
    """
    Calculate values (average by default) across multiple statistics files.
    """

    name = "calculate"
    security = "validate"

    @classmethod
    def add_action_subparser(cls, sub_handler):
        subparser = super().add_action_subparser(sub_handler)
        entity_parsers = cls._get_subparsers(
            subparser, "method", "average", "statistics"
        )
        entity_parsers["average"].add_argument(
            "locations",
            metavar="STATISTIC_FILE",
            nargs="+",
            help="locations of the session statistic files to calculate from",
        )
        entity_parsers["statistics"].add_argument(
            "--begin-time",
            "--begin",
            help="Date/time string when to start calculating",
        )
        entity_parsers["statistics"].add_argument(
            "--end-time",
            "--end",
            help="Date/time string when to stop calculating",
        )
        entity_parsers["statistics"].add_argument(
            "--minimum-ratio",
            type=float,
            default=0.05,
            help="When to consider a file based on changes ratio (default 0.05)",
        )
        entity_parsers["statistics"].add_argument(
            "locations",
            metavar="[[USER@]SERVER::]PATH",
            nargs="+",
            help="locations of repositories to create statistics for",
        )
        return subparser

    def pre_check(self):
        """
        Validate that the values are correct
        """
        ret_code = super().run()

        if self.values["method"] == "statistics":
            try:
                if self.values["begin_time"] is not None:
                    self.values["begin_time"] = Time.genstrtotime(
                        self.values["begin_time"]
                    )
                if self.values["end_time"] is not None:
                    self.values["end_time"] = Time.genstrtotime(self.values["end_time"])
            except Time.TimeException as exc:
                log.Log(
                    "Begin or end date/time has wrong format: {ex}".format(ex=exc),
                    log.ERROR,
                )
                ret_code |= consts.RET_CODE_ERR

            if self.values["minimum_ratio"] < 0 or self.values["minimum_ratio"] > 1:
                log.Log("The minimum ratio must be between 0 and 1", log.ERROR)
                ret_code |= consts.RET_CODE_ERR

        return ret_code

    def run(self):
        """
        Print out the calculation of the given statistics files, according
        to calculation method.
        """
        ret_code = super().run()
        if ret_code & consts.RET_CODE_ERR:
            return ret_code

        if self.values["method"] == "average":
            return ret_code | self._calculate_average(self.connected_locations)
        elif self.values["method"] == "statistics":
            return ret_code | self._calculate_statistics(self.connected_locations)

        return ret_code

    def _calculate_average(self, session_stats_files):
        sess_stats = [
            stats.SessionStatsCalc().read_stats(loc.open("r"))
            for loc in session_stats_files
        ]
        calc_stats = stats.SessionStatsCalc().calc_average(sess_stats)
        log.Log(
            calc_stats.get_stats_as_string(
                "Average of %d stat files" % len(session_stats_files)
            ),
            log.NONE,
        )
        return consts.RET_CODE_OK

    def _calculate_statistics(self, repositories):
        log.Log("STATISTICS TODO", log.ERROR)  # TODO
        return consts.RET_CODE_OK


def get_plugin_class():
    return CalculateAction
