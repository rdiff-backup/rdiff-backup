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
A built-in rdiff-backup action plug-in to compare with multiple means
a back-up repository with the current state of a directory.
Comparaison can be done using metadata, file content or hashes.
"""

import yaml
from rdiff_backup import (compare, Globals, log, selection)
from rdiffbackup import actions
from rdiffbackup.locations import (directory, repository)


class CompareAction(actions.BaseAction):
    """
    Compare the content of a source directory with a backup repository
    at a given time, using multiple methods.
    """
    name = "compare"
    security = "validate"
    parent_parsers = [actions.SELECTION_PARSER]

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

    def connect(self):
        conn_value = super().connect()
        if conn_value:
            self.dir = directory.ReadDir(self.connected_locations[0],
                                         self.values.force)
            self.repo = repository.Repo(
                self.connected_locations[1], self.values.force,
                must_be_writable=False, must_exist=True, can_be_sub_path=True
            )
        return conn_value

    def check(self):
        # we try to identify as many potential errors as possible before we
        # return, so we gather all potential issues and return only the final
        # result
        ret_code = super().check()

        # we verify that source directory and target repository are correct
        ret_code |= self.dir.check()
        ret_code |= self.repo.check()

        return ret_code

    def setup(self):
        # in setup we return as soon as we detect an issue to avoid changing
        # too much
        ret_code = super().setup()
        if ret_code & Globals.RET_CODE_ERR:
            return ret_code

        ret_code = self.dir.setup()
        if ret_code & Globals.RET_CODE_ERR:
            return ret_code

        ret_code = self.repo.setup(self.dir)
        if ret_code & Globals.RET_CODE_ERR:
            return ret_code

        # set the filesystem properties of the repository
        if Globals.get_api_version() < 201:  # compat200
            self.repo.base_dir.conn.fs_abilities.single_set_globals(
                self.repo.base_dir, 1)  # read_only=True
            self.repo.setup_quoting()

        (select_opts, select_data) = selection.get_prepared_selections(
            self.values.selections)
        self.dir.set_select(select_opts, select_data)

        self.action_time = self.repo.get_parsed_time(self.values.at)
        if self.action_time is None:
            return ret_code & Globals.RET_CODE_ERR

        return ret_code

    def run(self):
        ret_code = super().run()
        if ret_code & Globals.RET_CODE_ERR:
            return ret_code

        # call the right comparaison function for the chosen method
        if Globals.get_api_version() < 201:  # compat200
            compare_funcs = {
                "meta": compare.Compare,
                "hash": compare.Compare_hash,
                "full": compare.Compare_full
            }
            ret_code |= compare_funcs[self.values.method](self.dir.base_dir,
                                                          self.repo.ref_path,
                                                          self.repo.ref_inc,
                                                          self.action_time)
        else:
            compare_funcs = {
                "meta": self._compare_meta,
                "hash": self._compare_hash,
                "full": self._compare_full
            }
            reports_iter = compare_funcs[self.values.method](self.action_time)
            ret_code |= self._print_reports(reports_iter,
                                            self.values.parsable_output)
            self.repo.finish_loop()

        return ret_code

    def _compare_meta(self, compare_time):
        """
        Compares metadata in directory with metadata in mirror_rp at time
        """
        repo_iter = self.repo.init_and_get_loop(compare_time)
        report_iter = self.dir.compare_meta(repo_iter)
        return report_iter

    def _compare_hash(self, compare_time):
        """
        Compare files in directory with repo at compare_time

        Note metadata differences, but also check to see if file data is
        different.  If two regular files have the same size, hash the
        source and compare to the hash presumably already present in repo.
        """
        repo_iter = self.repo.init_and_get_loop(compare_time)
        report_iter = self.dir.compare_hash(repo_iter)
        return report_iter

    def _compare_full(self, compare_time):
        """
        Compare full data of files in directory with repo at compare_time

        Like Compare_hash, but do not rely on hashes, instead copy full
        data over.
        """
        src_iter = self.dir.get_select()
        repo_iter = self.repo.init_and_get_loop(compare_time, src_iter)
        report_iter = self.dir.compare_full(repo_iter)
        return report_iter

    def _print_reports(self, report_iter, parsable=False):
        """
        Given an iter of CompareReport objects, print them to screen.

        Output a list in YAML format if parsable is True.
        """
        assert not Globals.server, "This function shouldn't run as server."
        changed_files_found = 0
        reason_verify_list = []
        for report in report_iter:
            changed_files_found += 1
            indexpath = report.index and b"/".join(report.index) or b"."
            indexpath = indexpath.decode(errors="replace")
            if parsable:
                reason_verify_list.append({"reason": report.reason,
                                           "path": indexpath})
            else:
                print("{rr}: {ip}".format(rr=report.reason, ip=indexpath))

        if parsable:
            print(yaml.safe_dump(reason_verify_list,
                                 explicit_start=True, explicit_end=True))
        if not changed_files_found:
            log.Log("No changes found. Directory matches backup data", log.NOTE)
            return Globals.RET_CODE_OK
        else:
            log.Log("Directory has {fd} file differences to backup".format(
                fd=changed_files_found), log.WARNING)
            return Globals.RET_CODE_FILE_WARN


def get_plugin_class():
    return CompareAction
