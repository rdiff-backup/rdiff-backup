/* ----------------------------------------------------------------------- *
 *   
 *   Copyright 2002 2003 Ben Escoto
 *
 *   This file is part of rdiff-backup.
 *
 *   rdiff-backup is free software; you can redistribute it and/or
 *   modify it under the terms of the GNU General Public License as
 *   published by the Free Software Foundation; either version 2 of
 *   the License, or (at your option) any later version.
 *
 *   rdiff-backup is distributed in the hope that it will be useful,
 *   but WITHOUT ANY WARRANTY; without even the implied warranty of
 *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 *   General Public License for more details.
 *
 *   You should have received a copy of the GNU General Public License
 *   along with rdiff-backup; if not, write to the Free Software
 *   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA
 *   02111-1307 USA
 *
 * ----------------------------------------------------------------------- */

#include <Python.h>
#include <sys/types.h>
#include <sys/stat.h>
#if !defined(MS_WIN64) && !defined(MS_WIN32)
#include <unistd.h>
#endif
#include <errno.h>


/* Some of the following code to define major/minor taken from code by
 * Jörg Schilling's star archiver.
 */
#if !defined(major) && (defined(sgi) || defined(__sgi) || defined(__SVR4)) && !defined(__CYGWIN32__)
#include <sys/mkdev.h>
#endif

#ifndef major
#	define major(dev)		(((dev) >> 8) & 0xFF)
#	define minor(dev)		((dev) & 0xFF)
#	define makedev(majo, mino)	(((majo) << 8) | (mino))
#endif
/* End major/minor section */

/* choose the appropriate stat and fstat functions and return structs */
/* This code taken from Python's posixmodule.c */
#undef STAT
#if defined(MS_WIN64) || defined(MS_WIN32)
#	define SYNC _flushall
#else
#	define LSTAT lstat
#	define STAT stat
#	define FSTAT fstat
#	define STRUCT_STAT struct stat
#	define SYNC sync
#endif
#ifndef PY_LONG_LONG 
    #define PY_LONG_LONG LONG_LONG 
#endif

/* The following section is by Jeffrey A. Marshall and compensates for
 * a bug in Mac OS X's S_ISFIFO and S_ISSOCK macros.
 * Note: Starting in Mac OS X 10.3, the buggy macros were changed to be
 * the same as the ones below.
 */
#ifdef __APPLE__
/* S_ISFIFO/S_ISSOCK macros from <sys/stat.h> on mac osx are bogus */
#undef S_ISSOCK               /* their definition of a socket includes fifos */
#undef S_ISFIFO               /* their definition of a fifo includes sockets */
#define S_ISSOCK(mode)        (((mode) & S_IFMT) == S_IFSOCK)
#define S_ISFIFO(mode)        (((mode) & S_IFMT) == S_IFIFO)
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
#if defined(MS_WINDOWS)
	PyErr_SetString(PyExc_AttributeError, "This function is not implemented on Windows.");
	return NULL;
#else
  PyObject *size, *inode, *mtime, *atime, *ctime, *devloc, *return_val;
  char *filename, filetype[5];
  STRUCT_STAT sbuf;
  long int mode, perms;
  int res;

  if (!PyArg_ParseTuple(args, "s", &filename)) return NULL;

  Py_BEGIN_ALLOW_THREADS
  res = LSTAT(filename, &sbuf);
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
  size = PyLong_FromLongLong((PY_LONG_LONG)sbuf.st_size);
  inode = PyLong_FromLongLong((PY_LONG_LONG)sbuf.st_ino);
#else
  size = PyInt_FromLong(sbuf.st_size);
  inode = PyInt_FromLong((long)sbuf.st_ino);
#endif /* HAVE_LARGEFILE_SUPPORT */
  mode = (long)sbuf.st_mode;
  perms = mode & 07777;
#if defined(HAVE_LONG_LONG)
  devloc = PyLong_FromLongLong((PY_LONG_LONG)sbuf.st_dev);
#else
  devloc = PyInt_FromLong((long)sbuf.st_dev);
#endif
#if SIZEOF_TIME_T > SIZEOF_LONG
  mtime = PyLong_FromLongLong((PY_LONG_LONG)sbuf.st_mtime);
  atime = PyLong_FromLongLong((PY_LONG_LONG)sbuf.st_atime);
  ctime = PyLong_FromLongLong((PY_LONG_LONG)sbuf.st_ctime);
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
#if defined(HAVE_LONG_LONG)
	PY_LONG_LONG devnums = (PY_LONG_LONG)sbuf.st_rdev;
	PyObject *major_num = PyLong_FromLongLong(major(devnums));
#else
	long int devnums = (long)sbuf.st_dev;
	PyObject *major_num = PyInt_FromLong(major(devnums));
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
#endif /* defined(MS_WINDOWS) */
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
  SYNC();
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


/* --------------------------------------------------------------------- *
 * This section is still GPL'd, but was copied from the libmisc
 * section of getfacl by Andreas Gruenbacher
 * <a.gruenbacher@computer.org>.  I'm just copying the code to
 * preserve quoting compatibility between (get|set)f(acl|attr) and
 * rdiff-backup.  Taken on 8/24/2003.
 * --------------------------------------------------------------------- */

#include <stdio.h>
#include <stdlib.h>
#include <ctype.h>

int high_water_alloc(void **buf, size_t *bufsize, size_t newsize)
{
#define CHUNK_SIZE	256
	/*
	 * Goal here is to avoid unnecessary memory allocations by
	 * using static buffers which only grow when necessary.
	 * Size is increased in fixed size chunks (CHUNK_SIZE).
	 */
	if (*bufsize < newsize) {
		void *newbuf;

		newsize = (newsize + CHUNK_SIZE-1) & ~(CHUNK_SIZE-1);
		newbuf = realloc(*buf, newsize);
		if (!newbuf)
			return 1;
		
		*buf = newbuf;
		*bufsize = newsize;
	}
	return 0;
}

const char *quote(const char *str)
{
	static char *quoted_str = NULL;
	static size_t quoted_str_len = 0;
	const unsigned char *s;
	char *q;
	size_t nonpr, total_len;

	if (!str)
		return str;

	for (nonpr = 0, s = (unsigned char *)str, total_len = 0;
		 *s != '\0'; s++, total_len++) {
	  if (!isprint(*s) || isspace(*s) || *s == '\\' || *s == '=')
		nonpr++;
	}
	if (nonpr == 0)
		return str;

	if (high_water_alloc((void **)&quoted_str, &quoted_str_len,
			     nonpr * 3 + total_len + 1))
		return NULL;
	for (s = (unsigned char *)str, q = quoted_str; *s != '\0'; s++) {
		if (!isprint(*s) || isspace(*s) || *s == '\\' || *s == '=') {
			*q++ = '\\';
			*q++ = '0' + ((*s >> 6)    );
			*q++ = '0' + ((*s >> 3) & 7);
			*q++ = '0' + ((*s     ) & 7);
		} else
			*q++ = *s;
	}
	*q++ = '\0';

	return quoted_str;
}

char *unquote(char *str)
{
	unsigned char *s, *t;

	if (!str)
		return str;

	for (s = (unsigned char *)str; *s != '\0'; s++)
		if (*s == '\\')
			break;
	if (*s == '\0')
		return str;

#define isoctal(c) \
	((c) >= '0' && (c) <= '7')

	t = s;
	do {
		if (*s == '\\' &&
		    isoctal(*(s+1)) && isoctal(*(s+2)) && isoctal(*(s+3))) {
			*t++ = ((*(s+1) - '0') << 6) +
			       ((*(s+2) - '0') << 3) +
			       ((*(s+3) - '0')     );
			s += 3;
		} else
			*t++ = *s;
	} while (*s++ != '\0');

	return str;
}

/* ------------- End Gruenbach section --------------------------------- */

/* Translate quote above into python */
static PyObject *acl_quote(PyObject *self, PyObject *args)
{
  char *s;

  if (!PyArg_ParseTuple(args, "s", &s)) return NULL;
  return Py_BuildValue("s", quote(s));
}

/* Translate unquote above into python */
static PyObject *acl_unquote(PyObject *self, PyObject *args)
{
  char *s;

  if (!PyArg_ParseTuple(args, "s", &s)) return NULL;
  return Py_BuildValue("s", unquote(s));
}

/* ------------- lchown taken from Python's posixmodule.c -------------- */
/* duplicate here to avoid v2.3 requirement */

#ifdef HAVE_LCHOWN
static PyObject *
posix_error_with_allocated_filename(char* name)
{
	PyObject *rc = PyErr_SetFromErrnoWithFilename(PyExc_OSError, name);
	PyMem_Free(name);
	return rc;
}

static PyObject *
posix_lchown(PyObject *self, PyObject *args)
{
	char *path = NULL;
	int uid, gid;
	int res;
	if (!PyArg_ParseTuple(args, "etii:lchown",
	                      Py_FileSystemDefaultEncoding, &path,
	                      &uid, &gid))
		return NULL;
	Py_BEGIN_ALLOW_THREADS
	res = lchown(path, (uid_t) uid, (gid_t) gid);
	Py_END_ALLOW_THREADS
	if (res < 0)
		return posix_error_with_allocated_filename(path);
	PyMem_Free(path);
	Py_INCREF(Py_None);
	return Py_None;
}
#endif /* HAVE_LCHOWN */

/* ------------- Python export lists -------------------------------- */

static PyMethodDef CMethods[] = {
  {"make_file_dict", c_make_file_dict, METH_VARARGS,
   "Make dictionary from file stat"},
  {"long2str", long2str, METH_VARARGS, "Convert python long to 7 byte string"},
  {"str2long", str2long, METH_VARARGS, "Convert 7 byte string to python long"},
  {"sync", my_sync, METH_VARARGS, "sync buffers to disk"},
  {"acl_quote", acl_quote, METH_VARARGS,
   "Quote string, escaping non-printables"},
  {"acl_unquote", acl_unquote, METH_VARARGS,
   "Unquote string, producing original input to quote"},
#ifdef HAVE_LCHOWN
  {"lchown", posix_lchown, METH_VARARGS,
   "Like chown, but don't follow symlinks"},
#endif /* HAVE_LCHOWN */
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
