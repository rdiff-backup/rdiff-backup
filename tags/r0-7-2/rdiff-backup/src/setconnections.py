execfile("highlevel.py")

#######################################################################
#
# setconnections - Parse initial arguments and establish connections
#

class SetConnectionsException(Exception): pass

class SetConnections:
	"""Parse args and setup connections

	The methods in this class are used once by Main to parse file
	descriptions like bescoto@folly.stanford.edu:/usr/bin/ls and to
	set up the related connections.

	"""
	# This is the schema that determines how rdiff-backup will open a
	# pipe to the remote system.  If the file is given as A:B, %s will
	# be substituted with A in the schema.
	__cmd_schema = 'ssh %s rdiff-backup --server'

	# This is a list of remote commands used to start the connections.
	# The first is None because it is the local connection.
	__conn_remote_cmds = [None]

	def InitRPs(cls, arglist, remote_schema = None, remote_cmd = None):
		"""Map the given file descriptions into rpaths and return list"""
		if remote_schema: cls.__cmd_schema = remote_schema
		if not arglist: return []
		desc_pairs = map(cls.parse_file_desc, arglist)

		if filter(lambda x: x[0], desc_pairs): # True if any host_info found
			if remote_cmd:
				Log.FatalError("The --remote-cmd flag is not compatible "
							   "with remote file descriptions.")
		elif remote_schema:
			Log("Remote schema option ignored - no remote file "
				"descriptions.", 2)

		cmd_pairs = map(cls.desc2cmd_pairs, desc_pairs)
		if remote_cmd: # last file description gets remote_cmd
			cmd_pairs[-1] = (remote_cmd, cmd_pairs[-1][1])
		return map(cls.cmdpair2rp, cmd_pairs)

	def cmdpair2rp(cls, cmd_pair):
		"""Return RPath from cmd_pair (remote_cmd, filename)"""
		cmd, filename = cmd_pair
		if cmd: conn = cls.init_connection(cmd)
		else: conn = Globals.local_connection
		return RPath(conn, filename)

	def desc2cmd_pairs(cls, desc_pair):
		"""Return pair (remote_cmd, filename) from desc_pair"""
		host_info, filename = desc_pair
		if not host_info: return (None, filename)
		else: return (cls.fill_schema(host_info), filename)

	def parse_file_desc(cls, file_desc):
		"""Parse file description returning pair (host_info, filename)

		In other words, bescoto@folly.stanford.edu::/usr/bin/ls =>
		("bescoto@folly.stanford.edu", "/usr/bin/ls").  The
		complication is to allow for quoting of : by a \.  If the
		string is not separated by :, then the host_info is None.

		"""
		def check_len(i):
			if i >= len(file_desc):
				raise SetConnectionsException(
					"Unexpected end to file description %s" % file_desc)
				
		host_info_list, i, last_was_quoted = [], 0, None
		while 1:
			if i == len(file_desc):
				return (None, file_desc)

			if file_desc[i] == '\\':
				i = i+1
				check_len(i)
				last_was_quoted = 1
			elif (file_desc[i] == ":" and i > 0 and file_desc[i-1] == ":"
				  and not last_was_quoted):
				host_info_list.pop() # Remove last colon from name
				break
			else: last_was_quoted = None
			host_info_list.append(file_desc[i])
			i = i+1
				
		check_len(i+1)
		return ("".join(host_info_list), file_desc[i+1:])

	def fill_schema(cls, host_info):
		"""Fills host_info into the schema and returns remote command"""
		return cls.__cmd_schema % host_info

	def init_connection(cls, remote_cmd):
		"""Run remote_cmd, register connection, and then return it

		If remote_cmd is None, then the local connection will be
		returned.  This also updates some settings on the remote side,
		like global settings, its connection number, and verbosity.

		"""
		if not remote_cmd: return Globals.local_connection

		Log("Executing " + remote_cmd, 4)
		stdin, stdout = os.popen2(remote_cmd)
		conn_number = len(Globals.connections)
		conn = PipeConnection(stdout, stdin, conn_number)

		cls.check_connection_version(conn, remote_cmd)
		Log("Registering connection %d" % conn_number, 7)
		cls.init_connection_routing(conn, conn_number, remote_cmd)
		cls.init_connection_settings(conn)
		return conn

	def check_connection_version(cls, conn, remote_cmd):
		"""Log warning if connection has different version"""
		try: remote_version = conn.Globals.get('version')
		except ConnectionReadError, exception:
			Log.FatalError("""%s

Couldn't start up the remote connection by executing

    %s

Remember that, under the default settings, rdiff-backup must be
installed in the PATH on the remote system.  See the man page for more
information.""" % (exception, remote_cmd))
		
		if remote_version != Globals.version:
			Log("Warning: Local version %s does not match remote version %s."
				% (Globals.version, remote_version), 2)

	def init_connection_routing(cls, conn, conn_number, remote_cmd):
		"""Called by init_connection, establish routing, conn dict"""
		Globals.connection_dict[conn_number] = conn

		conn.SetConnections.init_connection_remote(conn_number)
		for other_remote_conn in Globals.connections[1:]:
			conn.SetConnections.add_redirected_conn(
				other_remote_conn.conn_number)
			other_remote_conn.SetConnections.add_redirected_conn(conn_number)

		Globals.connections.append(conn)
		cls.__conn_remote_cmds.append(remote_cmd)

	def init_connection_settings(cls, conn):
		"""Tell new conn about log settings and updated globals"""
		conn.Log.setverbosity(Log.verbosity)
		conn.Log.setterm_verbosity(Log.term_verbosity)
		for setting_name in Globals.changed_settings:
			conn.Globals.set(setting_name, Globals.get(setting_name))

	def init_connection_remote(cls, conn_number):
		"""Run on server side to tell self that have given conn_number"""
		Globals.connection_number = conn_number
		Globals.local_connection.conn_number = conn_number
		Globals.connection_dict[0] = Globals.connections[1]
		Globals.connection_dict[conn_number] = Globals.local_connection

	def add_redirected_conn(cls, conn_number):
		"""Run on server side - tell about redirected connection"""
		Globals.connection_dict[conn_number] = \
			   RedirectedConnection(conn_number)

	def UpdateGlobal(cls, setting_name, val):
		"""Update value of global variable across all connections"""
		for conn in Globals.connections:
			conn.Globals.set(setting_name, val)

	def BackupInitConnections(cls, reading_conn, writing_conn):
		"""Backup specific connection initialization"""
		reading_conn.Globals.set("isbackup_reader", 1)
		writing_conn.Globals.set("isbackup_writer", 1)
		cls.UpdateGlobal("backup_reader", reading_conn)
		cls.UpdateGlobal("backup_writer", writing_conn)


	def CloseConnections(cls):
		"""Close all connections.  Run by client"""
		assert not Globals.server
		for conn in Globals.connections: conn.quit()
		del Globals.connections[1:] # Only leave local connection
		Globals.connection_dict = {0: Globals.local_connection}
		Globals.backup_reader = Globals.isbackup_reader = \
			  Globals.backup_writer = Globals.isbackup_writer = None

	def TestConnections(cls):
		"""Test connections, printing results"""
		if len(Globals.connections) == 1:
			print "No remote connections specified"
		else:
			for i in range(1, len(Globals.connections)):
				cls.test_connection(i)

	def test_connection(cls, conn_number):
		"""Test connection.  conn_number 0 is the local connection"""
		print "Testing server started by: ", \
			  cls.__conn_remote_cmds[conn_number]
		conn = Globals.connections[conn_number]
		try:
			assert conn.pow(2,3) == 8
			assert conn.os.path.join("a", "b") == "a/b"
			version = conn.reval("lambda: Globals.version")
		except:
			sys.stderr.write("Server tests failed\n")
			raise
		if not version == Globals.version:
			print """Server may work, but there is a version mismatch:
Local version: %s
Remote version: %s""" % (Globals.version, version)
		else: print "Server OK"

MakeClass(SetConnections)