#!/usr/bin/env python
#
# rdiff-backup -- Mirror files while keeping incremental changes
# Version 0.7.6 released May 31, 2002
# Copyright (C) 2001, 2002 Ben Escoto <bescoto@stanford.edu>
#
# This program is licensed under the GNU General Public License (GPL).
# Distributions of rdiff-backup usually include a copy of the GPL in a
# file called COPYING.  The GPL is also available online at
# http://www.gnu.org/copyleft/gpl.html.
#
# See http://www.stanford.edu/~bescoto/rdiff-backup for more
# information.  Please send mail to me or the mailing list if you find
# bugs or have any suggestions.

from __future__ import nested_scopes, generators
import os, stat, time, sys, getopt, re, cPickle, types, shutil, sha, marshal, traceback, popen2, tempfile, gzip, UserList, errno, signal


