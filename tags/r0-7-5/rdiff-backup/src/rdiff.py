execfile("iterfile.py")
import os, popen2

#######################################################################
#
# rdiff - Invoke rdiff utility to make signatures, deltas, or patch
#

class RdiffException(Exception): pass

class Rdiff:
	"""Contains static methods for rdiff operations

	All these operations should be done in a relatively safe manner
	using RobustAction and the like.

	"""
	def get_signature(rp):
		"""Take signature of rpin file and return in file object"""
		Log("Getting signature of %s" % rp.path, 7)
		return rp.conn.RdiffPopen(['rdiff', 'signature', rp.path])

	def get_delta_sigfileobj(sig_fileobj, rp_new):
		"""Like get_delta but signature is in a file object"""
		sig_tf = TempFileManager.new(rp_new, None)
		sig_tf.write_from_fileobj(sig_fileobj)
		rdiff_popen_obj = Rdiff.get_delta(sig_tf, rp_new)
		rdiff_popen_obj.set_thunk(sig_tf.delete)
		return rdiff_popen_obj

	def get_delta(rp_signature, rp_new):
		"""Take signature rp and new rp, return delta file object"""
		assert rp_signature.conn is rp_new.conn
		Log("Getting delta of %s with signature %s" %
			(rp_new.path, rp_signature.path), 7)
		return rp_new.conn.RdiffPopen(['rdiff', 'delta',
									   rp_signature.path, rp_new.path])

	def write_delta_action(basis, new, delta, compress = None):
		"""Return action writing delta which brings basis to new

		If compress is true, the output of rdiff will be gzipped
		before written to delta.

		"""
		sig_tf = TempFileManager.new(new, None)
		delta_tf = TempFileManager.new(delta)
		def init():
			Log("Writing delta %s from %s -> %s" %
				(basis.path, new.path, delta.path), 7)
			sig_tf.write_from_fileobj(Rdiff.get_signature(basis))
			delta_tf.write_from_fileobj(Rdiff.get_delta(sig_tf, new), compress)
			sig_tf.delete()
		return Robust.make_tf_robustaction(init, (sig_tf, delta_tf),
										   (None, delta))

	def write_delta(basis, new, delta, compress = None):
		"""Write rdiff delta which brings basis to new"""
		Rdiff.write_delta_action(basis, new, delta, compress).execute()

	def patch_action(rp_basis, rp_delta, rp_out = None,
					 out_tf = None, delta_compressed = None):
		"""Return RobustAction which patches rp_basis with rp_delta

		If rp_out is None, put output in rp_basis.  Will use TempFile
		out_tf it is specified.  If delta_compressed is true, the
		delta file will be decompressed before processing with rdiff.

		"""
		if not rp_out: rp_out = rp_basis
		else: assert rp_out.conn is rp_basis.conn
		if (delta_compressed or
			not (isinstance(rp_delta, RPath) and isinstance(rp_basis, RPath)
				 and rp_basis.conn is rp_delta.conn)):
			if delta_compressed:
				assert isinstance(rp_delta, RPath)
				return Rdiff.patch_fileobj_action(rp_basis,
												  rp_delta.open('rb', 1),
												  rp_out, out_tf)
			else: return Rdiff.patch_fileobj_action(rp_basis,
													rp_delta.open('rb'),
													rp_out, out_tf)

		# Files are uncompressed on same connection, run rdiff
		if out_tf is None: out_tf = TempFileManager.new(rp_out)
		def init():
			Log("Patching %s using %s to %s via %s" %
				(rp_basis.path, rp_delta.path, rp_out.path, out_tf.path), 7)
			cmdlist = ["rdiff", "patch", rp_basis.path,
					   rp_delta.path, out_tf.path]
			return_val = rp_basis.conn.os.spawnvp(os.P_WAIT, 'rdiff', cmdlist)
			out_tf.setdata()
			if return_val != 0 or not out_tf.lstat():
				RdiffException("Error running %s" % cmdlist)
		return Robust.make_tf_robustaction(init, (out_tf,), (rp_out,))

	def patch_fileobj_action(rp_basis, delta_fileobj, rp_out = None,
							 out_tf = None, delta_compressed = None):
		"""Like patch_action but diff is given in fileobj form

		Nest a writing of a tempfile with the actual patching to
		create a new action.  We have to nest so that the tempfile
		will be around until the patching finishes.

		"""
		if not rp_out: rp_out = rp_basis
		delta_tf = TempFileManager.new(rp_out, None)
		def init(): delta_tf.write_from_fileobj(delta_fileobj)
		return Robust.chain_nested([RobustAction(init, delta_tf.delete,
												 lambda exc: delta_tf.delete),
									Rdiff.patch_action(rp_basis, delta_tf,
													   rp_out, out_tf)])

	def patch_with_attribs_action(rp_basis, rp_delta, rp_out = None):
		"""Like patch_action, but also transfers attributs from rp_delta"""
		if not rp_out: rp_out = rp_basis
		tf = TempFileManager.new(rp_out)
		return Robust.chain_nested(
			[Rdiff.patch_action(rp_basis, rp_delta, rp_out, tf),
			 Robust.copy_attribs_action(rp_delta, tf)])

	def copy_action(rpin, rpout):
		"""Use rdiff to copy rpin to rpout, conserving bandwidth"""
		if not rpin.isreg() or not rpout.isreg() or rpin.conn is rpout.conn:
			# rdiff not applicable, fallback to regular copying
			return Robust.copy_action(rpin, rpout)

		Log("Rdiff copying %s to %s" % (rpin.path, rpout.path), 6)		
		delta_tf = TempFileManager.new(rpout, None)
		return Robust.chain(Rdiff.write_delta_action(rpout, rpin, delta_tf),
							Rdiff.patch_action(rpout, delta_tf),
							RobustAction(lambda: None, delta_tf.delete,
										 lambda exc: delta_tf.delete))

MakeStatic(Rdiff)


class RdiffPopen:
	"""Spawn process and treat stdout as file object

	Instead of using popen, which evaluates arguments with the shell
	and thus may lead to security holes (thanks to Jamie Heilman for
	this point), use the popen2 class and discard stdin.

	When closed, this object checks to make sure the process exited
	cleanly, and executes closing_thunk.

	"""
	def __init__(self, cmdlist, closing_thunk = None):
		"""RdiffFilehook initializer

		fileobj is the file we are emulating
		thunk is called with no parameters right after the file is closed

		"""
		assert type(cmdlist) is types.ListType
		self.p3obj = popen2.Popen3(cmdlist)
		self.fileobj = self.p3obj.fromchild
		self.closing_thunk = closing_thunk
		self.cmdlist = cmdlist

	def set_thunk(self, closing_thunk):
		"""Set closing_thunk if not already"""
		assert not self.closing_thunk
		self.closing_thunk = closing_thunk

	def read(self, length = -1): return self.fileobj.read(length)

	def close(self):
		closeval = self.fileobj.close()
		if self.closing_thunk: self.closing_thunk()
		exitval = self.p3obj.poll()
		if exitval == 0: return closeval
		elif exitval == 256:
			Log("Failure probably because %s couldn't be found in PATH."
				% self.cmdlist[0], 2)
			assert 0, "rdiff not found"
		elif exitval == -1:
			# There may a race condition where a process closes
			# but doesn't provide its exitval fast enough.
			Log("Waiting for process to close", 8)
			time.sleep(0.2)
			exitval = self.p3obj.poll()
			if exitval == 0: return closeval
		raise RdiffException("%s exited with non-zero value %d" %
							 (self.cmdlist, exitval))




