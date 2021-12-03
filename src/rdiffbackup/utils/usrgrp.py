# Copyright 2002, 2003 Ben Escoto
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
This module deal with users and groups

On each connection we may need to map unames and gnames to uids and
gids, and possibly vice-versa.  So maintain a separate dictionary for
this.
"""

try:
    import pwd
    import grp
except ImportError:
    pass

# ----------- "Private" section - don't use outside usrgrp -----------

# Used to cache by uid2uname and gid2gname below
_uid2uname = {}
_gid2gname = {}

# Used to cache by uname2uid and gname2gid below
_uname2uid = {}
_gname2gid = {}


def uid2uname(uid):
    """
    Given uid, return uname from passwd file, or None if cannot find
    """
    if uid in _uid2uname:
        return _uid2uname[uid]
    else:
        try:
            uname = pwd.getpwuid(uid).pw_name
            _uname2uid[uname] = uid
        except (KeyError, OverflowError, NameError):
            uname = None
        _uid2uname[uid] = uname
        return uname


def gid2gname(gid):
    """
    Given gid, return group name from group file or None if cannot find
    """
    if gid in _gid2gname:
        return _gid2gname[gid]
    else:
        try:
            gname = grp.getgrgid(gid).gr_name
            _gname2gid[gname] = gid
        except (KeyError, OverflowError, NameError):
            gname = None
        _gid2gname[gid] = gname
        return gname


def uname2uid(uname):
    """
    Given uname, return uid or None if cannot find
    """
    if uname in _uname2uid:
        return _uname2uid[uname]
    else:
        try:
            uid = pwd.getpwnam(uname).pw_uid
            _uid2uname[uid] = uname
        except (KeyError, NameError):
            uid = None
        _uname2uid[uname] = uid
        return uid


def gname2gid(gname):
    """
    Given gname, return gid or None if cannot find
    """
    if gname in _gname2gid:
        return _gname2gid[gname]
    else:
        try:
            gid = grp.getgrnam(gname).gr_gid
            _gid2gname[gid] = gname
        except (KeyError, NameError):
            gid = None
        _gname2gid[gname] = gid
        return gid
