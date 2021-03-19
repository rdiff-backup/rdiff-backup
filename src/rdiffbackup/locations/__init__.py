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
Generic classes for locations
"""

class Location():

    def __init__(self, base_dir, log, force):
        self.base_dir = base_dir
        self.log = log
        self.force = force


class ReadLocation(Location):
    pass


class WriteLocation(Location):

    def __init__(self, base_dir, log, force, create_full_path):
        super().__init__(base_dir, log, force)
        self.create_full_path = create_full_path
