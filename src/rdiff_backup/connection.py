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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA
"""Support code for remote execution and data transfer"""

import pickle
import sys
import traceback
# we need those imports because they are used through the connection
import gzip  # noqa: F401
import os  # noqa: F401
import platform  # noqa: F401
import shutil  # noqa: F401
import socket  # noqa: F401
import tempfile  # noqa: F401
import types  # noqa: F401

# The following EA and ACL modules may be used if available
try:  # compat200
    import xattr.pyxattr_compat as xattr  # noqa: F401
except ImportError:
    try:
        import xattr  # noqa: F401
    except ImportError:
        pass
try:  # compat200
    import posix1e  # noqa: F401
except ImportError:
    pass
try:  # compat200
    import win32security  # noqa: F401
except ImportError:
    pass


class ConnectionError(Exception):
    pass


class ConnectionReadError(ConnectionError):
    pass


class ConnectionWriteError(ConnectionError):
    pass


class ConnectionQuit(Exception):
    pass


class Connection:
    """Connection class - represent remote execution

    The idea is that, if c is an instance of this class, c.foo will
    return the object on the remote side.  For functions, c.foo will
    return a function that, when called, executes foo on the remote
    side, sending over the arguments and sending back the result.

    """

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return "Simple Connection"  # override later

    def __bool__(self):
        return True


class LocalConnection(Connection):
    """Local connection

    This is a dummy connection class, so that LC.foo just evaluates to
    foo using global scope.

    """

    def __init__(self):
        """This prevents two instances of LocalConnection"""
        assert not Globals.local_connection, (
            "Local connection has already been initialized with {conn}.".format(
                conn=Globals.local_connection))
        self.conn_number = 0  # changed by SetConnections for server

    def __getattr__(self, name):
        if name in globals():
            return globals()[name]
        elif isinstance(__builtins__, dict):
            return __builtins__[name]
        else:
            return __builtins__.__dict__[name]

    def __setattr__(self, name, value):
        globals()[name] = value

    def __delattr__(self, name):
        del globals()[name]

    def __str__(self):
        return "LocalConnection"

    def reval(self, function_string, *args):
        return eval(function_string)(*args)

    def quit(self):
        pass


class ConnectionRequest:
    """Simple wrapper around a PipeConnection request"""

    def __init__(self, function_string, num_args):
        self.function_string = function_string
        self.num_args = num_args

    def __str__(self):
        return "ConnectionRequest: %s with %d arguments" % \
            (self.function_string, self.num_args)


class LowLevelPipeConnection(Connection):
    """Routines for just sending objects from one side of pipe to another

    Each thing sent down the pipe is paired with a request number,
    currently limited to be between 0 and 255.  The size of each thing
    should be less than 2^56.

    Each thing also has a type, indicated by one of the following
    characters:

    o - generic object
    i - iterator/generator of RORPs
    f - file object
    b - string
    q - quit signal
    R - RPath
    Q - QuotedRPath
    r - RORPath only
    c - PipeConnection object

    """

    def __init__(self, inpipe, outpipe):
        """inpipe is a file-type open for reading, outpipe for writing"""
        self.inpipe = inpipe
        self.outpipe = outpipe

    def __str__(self):
        """Return string version

        This is actually an important function, because otherwise
        requests to represent this object would result in "__str__"
        being executed on the other side of the connection.

        """
        return "LowLevelPipeConnection"

    def _put(self, obj, req_num):
        """Put an object into the pipe (will send raw if string)"""
        log.Log.conn("sending", obj, req_num)
        if type(obj) is bytes:
            self._putbuf(obj, req_num)
        elif isinstance(obj, Connection):
            self._putconn(obj, req_num)
        elif isinstance(obj, FilenameMapping.QuotedRPath):  # compat200
            self._putqrpath(obj, req_num)
        elif isinstance(obj, map_filenames.QuotedRPath):
            self._putqrpath(obj, req_num)
        elif isinstance(obj, rpath.RPath):
            self._putrpath(obj, req_num)
        elif isinstance(obj, rpath.RORPath):
            self._putrorpath(obj, req_num)
        elif ((hasattr(obj, "read") or hasattr(obj, "write"))
              and hasattr(obj, "close")):
            self._putfile(obj, req_num)
        elif hasattr(obj, "__next__") and hasattr(obj, "__iter__"):
            self._putiter(obj, req_num)
        else:
            self._putobj(obj, req_num)

    def _putobj(self, obj, req_num):
        """Send a generic python obj down the outpipe"""
        self._write("o", pickle.dumps(obj, Globals.PICKLE_PROTOCOL), req_num)

    def _putbuf(self, buf, req_num):
        """Send buffer buf down the outpipe"""
        self._write("b", buf, req_num)

    def _putfile(self, fp, req_num):
        """Send a file to the client using virtual files"""
        self._write("f", self._i2b(VirtualFile.new(fp)), req_num)

    def _putiter(self, iterator, req_num):
        """Put an iterator through the pipe"""
        self._write(
            "i", self._i2b(VirtualFile.new(iterfile.MiscIterToFile(iterator))),
            req_num)

    def _putrpath(self, rpath, req_num):
        """Put an rpath into the pipe

        The rpath's connection will be encoded as its conn_number.  It
        and the other information is put in a tuple.

        """
        rpath_repr = (rpath.conn.conn_number, rpath.base, rpath.index,
                      rpath.data)
        self._write("R", pickle.dumps(rpath_repr,
                                      Globals.PICKLE_PROTOCOL), req_num)

    def _putqrpath(self, qrpath, req_num):
        """Put a quoted rpath into the pipe (similar to _putrpath above)"""
        qrpath_repr = (qrpath.conn.conn_number, qrpath.base, qrpath.index,
                       qrpath.data)
        self._write("Q", pickle.dumps(qrpath_repr,
                                      Globals.PICKLE_PROTOCOL), req_num)

    def _putrorpath(self, rorpath, req_num):
        """Put an rorpath into the pipe

        This is only necessary because if there is a .file attached,
        it must be excluded from the pickling

        """
        rorpath_repr = (rorpath.index, rorpath.data)
        self._write("r", pickle.dumps(rorpath_repr,
                                      Globals.PICKLE_PROTOCOL), req_num)

    def _putconn(self, pipeconn, req_num):
        """Put a connection into the pipe

        A pipe connection is represented just as the integer (in
        string form) of its connection number it is *connected to*.

        """
        self._write("c", self._i2b(pipeconn.conn_number), req_num)

    def _putquit(self):
        """Send a string that takes down server"""
        self._write("q", b"", 255)

    def _write(self, headerchar, data, req_num):
        """Write header and then data to the pipe"""
        assert len(headerchar) == 1, (
            "Header type {hdr} can only have one letter/byte".format(
                hdr=headerchar))
        if isinstance(headerchar, str):  # it can only be an ASCII character
            headerchar = headerchar.encode('ascii')
        try:
            self.outpipe.write(headerchar + self._i2b(req_num, 1) + self._i2b(len(data), 7))
            self.outpipe.write(data)
            self.outpipe.flush()
        except (OSError, AttributeError):
            raise ConnectionWriteError()

    def _read(self, length):
        """Read length bytes from inpipe, returning result"""
        try:
            return self.inpipe.read(length)
        except OSError:
            raise ConnectionReadError()

    def _b2i(self, b):
        """Convert bytes to int using big endian byteorder"""
        return int.from_bytes(b, byteorder='big')

    def _i2b(self, i, size=0):
        """Convert int to string using big endian byteorder"""
        if (size == 0):
            size = (i.bit_length() + 7) // 8
        return i.to_bytes(size, byteorder='big')

    def _get(self):
        """
        Read an object from the pipe and return (req_num, value)
        """
        header_string = self.inpipe.read(9)
        if not len(header_string) == 9:
            raise ConnectionReadError(
                "Truncated header <{hdr}> "
                "(problem probably originated remotely)".format(
                    hdr=header_string))
        format_string = header_string[0:1]
        req_num = self._b2i(header_string[1:2])
        length = self._b2i(header_string[2:])

        if format_string == b"q":
            raise ConnectionQuit("Received quit signal")

        try:
            data = self._read(length)
        except MemoryError:
            raise ConnectionReadError(
                "Impossibly high data amount evaluated in header <{hdr}> "
                "(problem probably originated remotely)".format(
                    hdr=header_string))

        if format_string == b"o":
            result = pickle.loads(data)
        elif format_string == b"b":
            result = data
        elif format_string == b"f":
            result = VirtualFile(self, self._b2i(data))
        elif format_string == b"i":
            result = iterfile.FileToMiscIter(
                VirtualFile(self, self._b2i(data)))
        elif format_string == b"r":
            result = self._getrorpath(data)
        elif format_string == b"R":
            result = self._getrpath(data)
        elif format_string == b"Q":
            result = self._getqrpath(data)
        elif format_string == b"c":
            result = Globals.connection_dict[self._b2i(data)]
        else:
            raise ConnectionReadError(
                "Format character '{form}' invalid in <{hdr}> "
                "(problem probably originated remotely)".format(
                    hdr=header_string, form=format_string))

        log.Log.conn("received", result, req_num)
        return (req_num, result)

    def _getrorpath(self, raw_rorpath_buf):
        """Reconstruct RORPath object from raw data"""
        index, data = pickle.loads(raw_rorpath_buf)
        return rpath.RORPath(index, data)

    def _getrpath(self, raw_rpath_buf):
        """Return RPath object indicated by raw_rpath_buf"""
        conn_number, base, index, data = pickle.loads(raw_rpath_buf)
        return rpath.RPath(Globals.connection_dict[conn_number], base, index,
                           data)

    def _getqrpath(self, raw_qrpath_buf):
        """Return QuotedRPath object from raw buffer"""
        conn_number, base, index, data = pickle.loads(raw_qrpath_buf)
        if Globals.get_api_version() < 201:  # compat200
            return FilenameMapping.QuotedRPath(
                Globals.connection_dict[conn_number], base, index, data)
        else:
            return map_filenames.QuotedRPath(
                Globals.connection_dict[conn_number], base, index, data)

    def _close(self):
        """Close the pipes associated with the connection"""
        self.outpipe.close()
        self.inpipe.close()


class PipeConnection(LowLevelPipeConnection):
    """Provide server and client functions for a Pipe Connection

    Both sides act as modules that allows for remote execution.  For
    instance, self.connX.pow(2,8) will execute the operation on the
    server side.

    The only difference between the client and server is that the
    client makes the first request, and the server listens first.

    """

    def __init__(self, inpipe, outpipe, conn_number=0):
        """Init PipeConnection

        conn_number should be a unique (to the session) integer to
        identify the connection.  For instance, all connections to the
        client have conn_number 0.  Other connections can use this
        number to route commands to the correct process.

        """
        LowLevelPipeConnection.__init__(self, inpipe, outpipe)
        self.conn_number = conn_number
        self.unused_request_numbers = set(range(256))

    def __str__(self):
        return "PipeConnection %d" % self.conn_number

    def __getattr__(self, name):
        """Intercept attributes to allow for . invocation"""
        return EmulateCallable(self, name)

    def Server(self):
        """Start server's read eval return loop"""
        Globals.server = 1
        Globals.connections.append(self)
        log.Log("Starting server", log.INFO)
        self._get_response(-1)
        return Globals.RET_CODE_OK

    def reval(self, function_string, *args):
        """
        Execute command on remote side

        The first argument should be a string that evaluates to a
        function, like "pow", and the remaining are arguments to that
        function.
        """
        req_num = self._get_new_req_num()
        self._put(ConnectionRequest(function_string, len(args)), req_num)
        for arg in args:
            self._put(arg, req_num)
        result = self._get_response(req_num)
        self.unused_request_numbers.add(req_num)
        if isinstance(result, Exception):
            raise result
        elif isinstance(result, SystemExit):
            raise result
        elif isinstance(result, KeyboardInterrupt):
            raise result
        else:
            return result

    def quit(self):
        """Close the associated pipes and tell server side to quit"""
        assert not Globals.server, "This function shouldn't run as server."
        self._putquit()
        self._get()
        self._close()

    def _get_response(self, desired_req_num):
        """Read from pipe, responding to requests until req_num.

        Sometimes after a request is sent, the other side will make
        another request before responding to the original one.  In
        that case, respond to the request.  But return once the right
        response is given.

        """
        while 1:
            try:
                req_num, object = self._get()
            except ConnectionQuit:
                self._put("quitting", self._get_new_req_num())
                self._close()
                return
            if req_num == desired_req_num:
                return object
            else:
                assert isinstance(object, ConnectionRequest), (
                    "Object '{obj}' isn't a connection request but "
                    "a '{otype}'.".format(obj=object, otype=type(object)))
                self._answer_request(object, req_num)

    def _answer_request(self, request, req_num):
        """Put the object requested by request down the pipe"""
        self.unused_request_numbers.remove(req_num)
        argument_list = []
        for i in range(request.num_args):
            arg_req_num, arg = self._get()
            assert arg_req_num == req_num, (
                "Object {rnum} and argument {anum} numbers should be "
                "the same.".object(rnum=req_num, anum=arg_req_num))
            argument_list.append(arg)
        try:
            Security.vet_request(request, argument_list)
            result = eval(request.function_string)(*argument_list)
        except BaseException:
            result = self._extract_exception()
        self._put(result, req_num)
        self.unused_request_numbers.add(req_num)

    def _extract_exception(self):
        """Return active exception"""
        if robust.is_routine_fatal(sys.exc_info()[1]):
            raise  # Fatal error--No logging necessary, but connection down
        if log.Log.verbosity >= 5 or log.Log.term_verbosity >= 5:
            log.Log("Sending back exception '{ex}' of type {ty} with "
                    "traceback {tb}".format(
                        ex=sys.exc_info()[1], ty=sys.exc_info()[0],
                        tb="".join(traceback.format_tb(sys.exc_info()[2]))),
                    log.INFO)
        return sys.exc_info()[1]

    def _get_new_req_num(self):
        """Allot a new request number and return it"""
        if not self.unused_request_numbers:
            raise ConnectionError("Exhausted possible connection numbers")
        return self.unused_request_numbers.pop()


class RedirectedConnection(Connection):
    """Represent a connection more than one move away

    For instance, suppose things are connected like this: S1---C---S2.
    If Server1 wants something done by Server2, it will have to go
    through the Client.  So on S1's side, S2 will be represented by a
    RedirectedConnection.

    """

    def __init__(self, conn_number, routing_number=0):
        """RedirectedConnection initializer

        Returns a RedirectedConnection object for the given
        conn_number, where commands are routed through the connection
        with the given routing_number.  0 is the client, so the
        default shouldn't have to be changed.

        """
        self.conn_number = conn_number
        self.routing_number = routing_number
        self.routing_conn = Globals.connection_dict[routing_number]

    def reval(self, function_string, *args):
        """Evaluation function_string on args on remote connection"""
        return self.routing_conn.reval("RedirectedRun", self.conn_number,
                                       function_string, *args)

    def __str__(self):
        return "RedirectedConnection %d,%d" % (self.conn_number,
                                               self.routing_number)

    def __getattr__(self, name):
        return EmulateCallableRedirected(self.conn_number, self.routing_conn,
                                         name)


class EmulateCallable:
    """This is used by PipeConnection in calls like conn.os.chmod(foo)"""

    def __init__(self, connection, name):
        self.connection = connection
        self.call_name = name

    def __call__(self, *args):
        return self.connection.reval(*(self.call_name, ) + args)

    def __getattr__(self, attr_name):
        return EmulateCallable(self.connection,
                               "%s.%s" % (self.call_name, attr_name))


class EmulateCallableRedirected:
    """Used by RedirectedConnection in calls like conn.os.chmod(foo)"""

    def __init__(self, conn_number, routing_conn, name):
        self.conn_number, self.routing_conn = conn_number, routing_conn
        self.call_name = name

    def __call__(self, *args):
        return self.routing_conn.reval(
            *("RedirectedRun", self.conn_number, self.call_name) + args)

    def __getattr__(self, attr_name):
        return EmulateCallableRedirected(self.conn_number, self.routing_conn,
                                         "%s.%s" % (self.call_name, attr_name))


class VirtualFile:
    """When the client asks for a file over the connection, it gets this

    The returned instance then forwards requests over the connection.
    The class's dictionary is used by the server to associate each
    with a unique file number.

    """
    # The following are used by the server
    _vfiles = {}
    _counter = -1

    # @API(VirtualFile.readfromid, 200)
    @classmethod
    def readfromid(cls, id, length):
        if length is None:
            return cls._vfiles[id].read()
        else:
            return cls._vfiles[id].read(length)

    # @API(VirtualFile.writetoid, 200)
    @classmethod
    def writetoid(cls, id, buffer):
        return cls._vfiles[id].write(buffer)

    # @API(VirtualFile.closebyid, 200)
    @classmethod
    def closebyid(cls, id):
        fp = cls._vfiles[id]
        del cls._vfiles[id]
        return fp.close()

    @classmethod
    def new(cls, fileobj):
        """Associate a new VirtualFile with a read fileobject, return id"""
        cls._counter += 1
        cls._vfiles[cls._counter] = fileobj
        return cls._counter

    # And these are used by the client
    def __init__(self, connection, id):
        self.connection = connection
        self.id = id

    def read(self, length=None):
        return self.connection.VirtualFile.readfromid(self.id, length)

    def write(self, buf):
        return self.connection.VirtualFile.writetoid(self.id, buf)

    def close(self):
        return self.connection.VirtualFile.closebyid(self.id)


# @API(RedirectedRun, 200)
def RedirectedRun(conn_number, func, *args):
    """Run func with args on connection with conn number conn_number

    This function is meant to redirect requests from one connection to
    another, so conn_number must not be the local connection (and also
    for security reasons since this function is always made
    available).

    """
    conn = Globals.connection_dict[conn_number]
    assert conn is not Globals.local_connection, (
        "A redirected run shouldn't be required locally for {fnc}.".format(
            fnc=func.__name__))
    return conn.reval(func, *args)


# everything has to be available here for remote connection's use, but
# put at bottom to reduce circularities.
from rdiff_backup import (  # noqa: E402,F401
    Globals, Time, Rdiff, Hardlink, FilenameMapping, Security,
    Main, rorpiter, selection, increment, statistics, manage,
    iterfile, rpath, robust, restore, backup,
    SetConnections, librsync, log, regress, fs_abilities,
    user_group, compare
)
from rdiffbackup.locations import _dir_shadow, _repo_shadow  # noqa: E402,F401
from rdiffbackup.locations.map import filenames as map_filenames  # noqa: E402,F401

Globals.local_connection = LocalConnection()
Globals.connections.append(Globals.local_connection)
# Following changed by server in SetConnections
Globals.connection_dict[0] = Globals.local_connection
