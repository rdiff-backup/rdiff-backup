# Copyright 2002 Ben Escoto
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
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307
# USA

"""Functions to make sure remote requests are kosher"""

import sys, tempfile
import Globals, Main, rpath

class Violation(Exception):
	"""Exception that indicates an improper request has been received"""
	pass


# This will store the list of functions that will be honored from
# remote connections.
allowed_requests = None

# This stores the list of global variables that the client can not
# set on the server.
disallowed_server_globals = ["server", "security_level", "restrict_path"]

def initialize(action, cmdpairs):
	"""Initialize allowable request list and chroot"""
	global allowed_requests
	set_security_level(action, cmdpairs)
	set_allowed_requests(Globals.security_level)

def set_security_level(action, cmdpairs):
	"""If running client, set security level and restrict_path

	To find these settings, we must look at the action to see what is
	supposed to happen, and then look at the cmdpairs to see what end
	the client is on.

	"""
	def islocal(cmdpair): return not cmdpair[0]
	def bothlocal(cp1, cp2): return islocal(cp1) and islocal(cp2)
	def bothremote(cp1, cp2): return not islocal(cp1) and not islocal(cp2)
	def getpath(cmdpair): return cmdpair[1]

	if Globals.server: return
	cp1 = cmdpairs[0]
	if len(cmdpairs) > 1: cp2 = cmdpairs[1]
	else: cp2 = cp1

	if action == "backup" or action == "check-destination-dir":
		if bothlocal(cp1, cp2) or bothremote(cp1, cp2):
			sec_level = "minimal"
			rdir = tempfile.gettempdir()
		elif islocal(cp1):
			sec_level = "read-only"
			rdir = getpath(cp1)
		else:
			assert islocal(cp2)
			sec_level = "update-only"
			rdir = getpath(cp2)
	elif action == "restore" or action == "restore-as-of":
		if len(cmdpairs) == 1 or bothlocal(cp1, cp2) or bothremote(cp1, cp2):
			sec_level = "minimal"
			rdir = tempfile.gettempdir()
		elif islocal(cp1):
			sec_level = "read-only"
			Main.restore_set_root(rpath.RPath(Globals.local_connection,
											  getpath(cp1)))
			rdir = Main.restore_root.path
		else:
			assert islocal(cp2)
			sec_level = "all"
			rdir = getpath(cp2)
	elif action == "mirror":
		if bothlocal(cp1, cp2) or bothremote(cp1, cp2):
			sec_level = "minimal"
			rdir = tempfile.gettempdir()
		elif islocal(cp1):
			sec_level = "read-only"
			rdir = getpath(cp1)
		else:
			assert islocal(cp2)
			sec_level = "all"
			rdir = getpath(cp2)
	elif action in ["test-server", "list-increments", 'list-increment-sizes',
					 "list-at-time", "list-changed-since",
					 "calculate-average", "remove-older-than"]:
		sec_level = "minimal"
		rdir = tempfile.gettempdir()
	else: assert 0, "Unknown action %s" % action

	Globals.security_level = sec_level
	Globals.restrict_path = rpath.RPath(Globals.local_connection,
										rdir).normalize().path

def set_allowed_requests(sec_level):
	"""Set the allowed requests list using the security level"""
	global allowed_requests
	if sec_level == "all": return
	allowed_requests = ["VirtualFile.readfromid", "VirtualFile.closebyid",
						"Globals.get", "Globals.is_not_None",
						"Globals.get_dict_val",
						"log.Log.open_logfile_allconn",
						"log.Log.close_logfile_allconn",
						"Log.log_to_file",
						"SetConnections.add_redirected_conn",
						"RedirectedRun",
						"sys.stdout.write"]
	if sec_level == "minimal": pass
	elif sec_level == "read-only" or sec_level == "update-only":
		allowed_requests.extend(
			["C.make_file_dict",
			 "log.Log.log_to_file",
			 "os.getuid",
			 "os.listdir",
			 "Time.setcurtime_local",
			 "robust.Resume.ResumeCheck",
			 "backup.SourceStruct.split_initial_dsiter",
			 "backup.SourceStruct.get_diffs_and_finalize",
			 "rpath.gzip_open_local_read",
			 "rpath.open_local_read"])
		if sec_level == "update-only":
			allowed_requests.extend(
				["Log.open_logfile_local", "Log.close_logfile_local",
				 "Log.close_logfile_allconn", "Log.log_to_file",
				 "log.Log.log_to_file",
				 "robust.SaveState.init_filenames",
				 "robust.SaveState.touch_last_file",
				 "backup.DestinationStruct.get_sigs",
				 "backup.DestinationStruct.patch_w_datadir_writes",
				 "backup.DestinationStruct.patch_and_finalize",
				 "backup.DestinationStruct.patch_increment_and_finalize",
				 "Main.backup_touch_curmirror_local",
				 "Globals.ITRB.increment_stat",
				 "statistics.record_error",
				 "log.ErrorLog.write_if_open"])
	if Globals.server:
		allowed_requests.extend(
			["SetConnections.init_connection_remote",
			 "log.Log.setverbosity",
			 "log.Log.setterm_verbosity",
			 "Time.setprevtime_local",
			 "FilenameMapping.set_init_quote_vals_local",
			 "Globals.postset_regexp_local",
			 "Globals.set_select",
			 "backup.SourceStruct.set_session_info",
			 "backup.DestinationStruct.set_session_info"])

def vet_request(request, arglist):
	"""Examine request for security violations"""
	#if Globals.server: sys.stderr.write(str(request) + "\n")
	security_level = Globals.security_level
	if Globals.restrict_path:
		for arg in arglist:
			if isinstance(arg, rpath.RPath): vet_rpath(arg)
	if security_level == "all": return
	if request.function_string in allowed_requests: return
	if request.function_string == "Globals.set":
		if Globals.server and arglist[0] not in disallowed_server_globals:
			return
	raise Violation("\nWarning Security Violation!\n"
					"Bad request for function: %s\n"
					"with arguments: %s\n" % (request.function_string,
											  arglist))

def vet_rpath(rpath):
	"""Require rpath not to step outside retricted directory"""
	if Globals.restrict_path and rpath.conn is Globals.local_connection:
		normalized, restrict = rpath.normalize().path, Globals.restrict_path
		components = normalized.split("/")
		# 3 cases for restricted dir /usr/foo:  /var, /usr/foobar, /usr/foo/..
		if (not normalized.startswith(restrict) or
			(len(normalized) > len(restrict) and
			 normalized[len(restrict)] != "/") or
			".." in components):
			raise Violation("\nWarning Security Violation!\n"
							"Request to handle path %s\n"
							"which doesn't appear to be within "
							"restrict path %s.\n" % (normalized, restrict))

			 
		   
			
