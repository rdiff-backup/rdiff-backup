/* ----------------------------------------------------------------------- *
 *   
 *   Copyright 2002 Ben Escoto
 *
 *   This file is part of rdiff-backup.
 *
 *   rdiff-backup is free software; you can redistribute it and/or
 *   modify it under the terms of the GNU General Public License as
 *   published by the Free Software Foundation, Inc., 675 Mass Ave,
 *   Cambridge MA 02139, USA; either version 2 of the License, or (at
 *   your option) any later version; incorporated herein by reference.
 *
 * ----------------------------------------------------------------------- */


#include <Python.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <unistd.h>
#include <errno.h>

/* choose the appropriate stat and fstat functions and return structs */
/* This code taken from Python's posixmodule.c */
#undef STAT
#if defined(MS_WIN64) || defined(MS_WIN32)
#	define STAT _stati64
#	define FSTAT _fstati64
#	define STRUCT_STAT struct _stati64
#else
#	define STAT stat
#	define FSTAT fstat
#	define STRUCT_STAT struct stat
#endif

static PyObject *UnknownFileTypeError;
static PyObject *c_make_file_dict(PyObject *self, PyObject *args);
static PyObject *long2str(PyObject *self, PyObject *args);
static PyObject *str2long(PyObject *self, PyObject *args);
static PyObject *my_sync(PyObject *self, PyObject *args);


/* Turn a stat structure into a python dictionary.  The preprocessor
   stuff taken from Python's posixmodule.c */
static PyObject *c_make_file_dict(self, args)
	 PyObject *self;
	 PyObject *args;
{
  PyObject *size, *inode, *mtime, *atime, *ctime, *devloc, *return_val;
  char *filename, filetype[5];
  STRUCT_STAT sbuf;
  long int mode, perms;
  int res;

  if (!PyArg_ParseTuple(args, "s", &filename)) return NULL;

  Py_BEGIN_ALLOW_THREADS
  res = lstat(filename, &sbuf);
  Py_END_ALLOW_THREADS

  if (res != 0) {
	if (errno == ENOENT || errno == ENOTDIR)
	  return Py_BuildValue("{s:s}", "type", NULL);
	else {
	  PyErr_SetFromErrnoWithFilename(PyExc_OSError, filename);
	  return NULL;
	}
  }
#ifdef HAVE_LARGEFILE_SUPPORT
  size = PyLong_FromLongLong((LONG_LONG)sbuf.st_size);
  inode = PyLong_FromLongLong((LONG_LONG)sbuf.st_ino);
#else
  size = PyInt_FromLong(sbuf.st_size);
  inode = PyInt_FromLong((long)sbuf.st_ino);
#endif
  mode = (long)sbuf.st_mode;
  perms = mode & 07777;
#if defined(HAVE_LONG_LONG) && !defined(MS_WINDOWS)
  devloc = PyLong_FromLongLong((LONG_LONG)sbuf.st_dev);
#else
  devloc = PyInt_FromLong((long)sbuf.st_dev);
#endif
#if SIZEOF_TIME_T > SIZEOF_LONG
  mtime = PyLong_FromLongLong((LONG_LONG)sbuf.st_mtime);
  atime = PyLong_FromLongLong((LONG_LONG)sbuf.st_atime);
  ctime = PyLong_FromLongLong((LONG_LONG)sbuf.st_ctime);
#else
  mtime = PyInt_FromLong((long)sbuf.st_mtime);
  atime = PyInt_FromLong((long)sbuf.st_atime);
  ctime = PyInt_FromLong((long)sbuf.st_ctime);
#endif

  /* Build return dictionary from stat struct */
  if (S_ISREG(mode) || S_ISDIR(mode) || S_ISSOCK(mode) || S_ISFIFO(mode)) {
	/* Regular files, directories, sockets, and fifos */
	if S_ISREG(mode) strcpy(filetype, "reg");
	else if S_ISDIR(mode) strcpy(filetype, "dir");
	else if S_ISSOCK(mode) strcpy(filetype, "sock");
	else strcpy(filetype, "fifo");
	return_val =  Py_BuildValue("{s:s,s:O,s:l,s:l,s:l,s:O,s:O,s:l,s:O,s:O,s:O}",
								"type", filetype,
								"size", size,
								"perms", perms,
								"uid", (long)sbuf.st_uid,
								"gid", (long)sbuf.st_gid,
								"inode", inode,
								"devloc", devloc,
								"nlink", (long)sbuf.st_nlink,
								"mtime", mtime,
								"atime", atime,
								"ctime", ctime);
  } else if S_ISLNK(mode) {
	/* Symbolic links */
	char linkname[1024];
	int len_link = readlink(filename, linkname, 1023);
	if (len_link < 0) {
	  PyErr_SetFromErrno(PyExc_OSError);
	  return_val = NULL;
	} else {
	  linkname[len_link] = '\0';
	  return_val = Py_BuildValue("{s:s,s:O,s:l,s:l,s:l,s:O,s:O,s:l,s:s}",
								 "type", "sym",
								 "size", size,
								 "perms", perms,
								 "uid", (long)sbuf.st_uid,
								 "gid", (long)sbuf.st_gid,
								 "inode", inode,
								 "devloc", devloc,
								 "nlink", (long)sbuf.st_nlink,
								 "linkname", linkname);
	}
  } else if (S_ISCHR(mode) || S_ISBLK(mode)) {
	/* Device files */
	char devtype[2];
#if defined(HAVE_LONG_LONG) && !defined(MS_WINDOWS)
	LONG_LONG devnums = (LONG_LONG)sbuf.st_rdev;
	PyObject *major_num = PyLong_FromLongLong(major(devnums));
#else
	long int devnums = (long)sbuf.st_dev;
	PyObject *major_num = PyInt_FromLong(devnums >> 8);
#endif
	int minor_num = (int)(minor(devnums));
	if S_ISCHR(mode) strcpy(devtype, "c");
	else strcpy(devtype, "b");
	return_val = Py_BuildValue("{s:s,s:O,s:l,s:l,s:l,s:O,s:O,s:l,s:N}",
							   "type", "dev",
							   "size", size,
							   "perms", perms,
							   "uid", (long)sbuf.st_uid,
							   "gid", (long)sbuf.st_gid,
							   "inode", inode,
							   "devloc", devloc,
							   "nlink", (long)sbuf.st_nlink,
							   "devnums", Py_BuildValue("(s,O,i)", devtype,
														major_num, minor_num));
	Py_DECREF(major_num);
  } else {
	/* Unrecognized file type - raise exception */
	PyErr_SetString(UnknownFileTypeError, filename);
	return_val = NULL;
  }
  Py_DECREF(size);
  Py_DECREF(inode);
  Py_DECREF(devloc);
  Py_DECREF(mtime);
  Py_DECREF(atime);
  Py_DECREF(ctime);
  return return_val;
}


/* Convert python long into 7 byte string */
static PyObject *long2str(self, args)
	 PyObject *self;
	 PyObject *args;
{
  unsigned char s[7];
  PyLongObject *pylong;
  PyObject *return_val;

  if (!PyArg_ParseTuple(args, "O!", &PyLong_Type, &pylong)) return NULL;
  if (_PyLong_AsByteArray(pylong, s, 7, 0, 0) != 0) return NULL;
  else return Py_BuildValue("s#", s, 7);
  return return_val;
}


/* Run sync() and return None */
static PyObject *my_sync(self, args)
	 PyObject *self;
	 PyObject *args;
{
  if (!PyArg_ParseTuple(args, "")) return NULL;
  sync();
  return Py_BuildValue("");
}


/* Reverse of above; convert 7 byte string into python long */
static PyObject *str2long(self, args)
	 PyObject *self;
	 PyObject *args;
{
  unsigned char *s;
  int ssize;

  if (!PyArg_ParseTuple(args, "s#", &s, &ssize)) return NULL;
  if (ssize != 7) {
	PyErr_SetString(PyExc_TypeError, "Single argument must be 7 char string");
	return NULL;
  }
  return _PyLong_FromByteArray(s, 7, 0, 0);
}


static PyMethodDef CMethods[] = {
  {"make_file_dict", c_make_file_dict, METH_VARARGS,
   "Make dictionary from file stat"},
  {"long2str", long2str, METH_VARARGS, "Convert python long to 7 byte string"},
  {"str2long", str2long, METH_VARARGS, "Convert 7 byte string to python long"},
  {"sync", my_sync, METH_VARARGS, "sync buffers to disk"},
  {NULL, NULL, 0, NULL}
};

void initC(void)
{
  PyObject *m, *d;

  m = Py_InitModule("C", CMethods);
  d = PyModule_GetDict(m);
  UnknownFileTypeError = PyErr_NewException("C.UnknownFileTypeError",
											NULL, NULL);
  PyDict_SetItemString(d, "UnknownFileTypeError", UnknownFileTypeError);
}

