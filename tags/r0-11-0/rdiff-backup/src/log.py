# Copyright 2002 Ben Escoto
#
# This file is part of rdiff-backup.
#
# rdiff-backup is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, Inc., 675 Mass Ave, Cambridge MA
# 02139, USA; either version 2 of the License, or (at your option) any
# later version; incorporated herein by reference.

"""Manage logging, displaying and recording messages with required verbosity"""

import time, sys, traceback, types


class LoggerError(Exception): pass

class Logger:
	"""All functions which deal with logging"""
	def __init__(self):
		self.log_file_open = None
		self.log_file_local = None
		self.verbosity = self.term_verbosity = 3
		# termverbset is true if the term_verbosity has been explicity set
		self.termverbset = None

	def setverbosity(self, verbosity_string):
		"""Set verbosity levels.  Takes a number string"""
		try: self.verbosity = int(verbosity_string)
		except ValueError:
			Log.FatalError("Verbosity must be a number, received '%s' "
						   "instead." % verbosity_string)
		if not self.termverbset: self.term_verbosity = self.verbosity

	def setterm_verbosity(self, termverb_string):
		"""Set verbosity to terminal.  Takes a number string"""
		try: self.term_verbosity = int(termverb_string)
		except ValueError:
			Log.FatalError("Terminal verbosity must be a number, received "
						   "'%s' instead." % termverb_string)
		self.termverbset = 1

	def open_logfile(self, rpath):
		"""Inform all connections of an open logfile.

		rpath.conn will write to the file, and the others will pass
		write commands off to it.

		"""
		assert not self.log_file_open
		rpath.conn.Log.open_logfile_local(rpath)
		for conn in Globals.connections:
			conn.Log.open_logfile_allconn(rpath.conn)

	def open_logfile_allconn(self, log_file_conn):
		"""Run on all connections to signal log file is open"""
		self.log_file_open = 1
		self.log_file_conn = log_file_conn

	def open_logfile_local(self, rpath):
		"""Open logfile locally - should only be run on one connection"""
		assert rpath.conn is Globals.local_connection
		try: self.logfp = rpath.open("a")
		except (OSError, IOError), e:
			raise LoggerError("Unable to open logfile %s: %s"
							  % (rpath.path, e))
		self.log_file_local = 1
		self.logrp = rpath

	def close_logfile(self):
		"""Close logfile and inform all connections"""
		if self.log_file_open:
			for conn in Globals.connections:
				conn.Log.close_logfile_allconn()
			self.log_file_conn.Log.close_logfile_local()

	def close_logfile_allconn(self):
		"""Run on every connection"""
		self.log_file_open = None

	def close_logfile_local(self):
		"""Run by logging connection - close logfile"""
		assert self.log_file_conn is Globals.local_connection
		assert not self.logfp.close()
		self.log_file_local = None

	def format(self, message, verbosity):
		"""Format the message, possibly adding date information"""
		if verbosity < 9: return message + "\n"
		else: return "%s  %s\n" % (time.asctime(time.localtime(time.time())),
								   message)

	def __call__(self, message, verbosity):
		"""Log message that has verbosity importance

		message can be a string, which is logged as-is, or a function,
		which is then called and should return the string to be
		logged.  We do it this way in case producing the string would
		take a significant amount of CPU.
		
		"""
		if verbosity > self.verbosity and verbosity > self.term_verbosity:
			return

		if not type(message) is types.StringType:
			assert type(message) is types.FunctionType
			message = message()

		if verbosity <= self.verbosity: self.log_to_file(message)
		if verbosity <= self.term_verbosity:
			self.log_to_term(message, verbosity)

	def log_to_file(self, message):
		"""Write the message to the log file, if possible"""
		if self.log_file_open:
			if self.log_file_local:
				self.logfp.write(self.format(message, self.verbosity))
			else: self.log_file_conn.Log.log_to_file(message)

	def log_to_term(self, message, verbosity):
		"""Write message to stdout/stderr"""
		if verbosity <= 2 or Globals.server: termfp = sys.stderr
		else: termfp = sys.stdout
		termfp.write(self.format(message, self.term_verbosity))

	def conn(self, direction, result, req_num):
		"""Log some data on the connection

		The main worry with this function is that something in here
		will create more network traffic, which will spiral to
		infinite regress.  So, for instance, logging must only be done
		to the terminal, because otherwise the log file may be remote.

		"""
		if self.term_verbosity < 9: return
		if type(result) is types.StringType: result_repr = repr(result)
		else: result_repr = str(result)
		if Globals.server: conn_str = "Server"
		else: conn_str = "Client"
		self.log_to_term("%s %s (%d): %s" %
						 (conn_str, direction, req_num, result_repr), 9)

	def FatalError(self, message):
		self("Fatal Error: " + message, 1)
		Main.cleanup()
		sys.exit(1)

	def exception_to_string(self, arglist = []):
		"""Return string version of current exception plus what's in arglist"""
		type, value, tb = sys.exc_info()
		s = ("Exception '%s' raised of class '%s':\n%s" %
			 (value, type, "".join(traceback.format_tb(tb))))
		if arglist:
			s += "__Arguments:\n" + "\n".join(map(str, arglist))
		return s

	def exception(self, only_terminal = 0, verbosity = 5):
		"""Log an exception and traceback

		If only_terminal is None, log normally.  If it is 1, then only
		log to disk if log file is local (self.log_file_open = 1).  If
		it is 2, don't log to disk at all.

		"""
		assert only_terminal in (0, 1, 2)
		if (only_terminal == 0 or
			(only_terminal == 1 and self.log_file_open)):
			logging_func = self.__call__
		else: logging_func = self.log_to_term

		logging_func(self.exception_to_string(), verbosity)

Log = Logger()
import Globals, Main
