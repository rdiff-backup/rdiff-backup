#include <sys/types.h>
#include <sys/stat.h>
#include <unistd.h>
#include <Python.h>
#include <errno.h>

static PyObject *c_make_file_dict(self, args)
	 PyObject *self;
	 PyObject *args;
{
  char *filename, filetype[5];
  struct stat sbuf;
  mode_t mode;

  if (!PyArg_ParseTuple(args, "s", &filename)) return NULL;
  if (lstat(filename, &sbuf) != 0) {
	if (errno == ENOENT || errno == ENOTDIR)
	  return Py_BuildValue("{s:s}", "type", NULL);
	else {
	  PyErr_SetFromErrno(PyExc_OSError);
	  return NULL;
	}
  }
  mode = sbuf.st_mode;

  /* Build return dictionary from stat struct */
  if (S_ISREG(mode) || S_ISDIR(mode) || S_ISSOCK(mode) || S_ISFIFO(mode)) {
	/* Regular files, directories, sockets, and fifos */
	if S_ISREG(mode) strcpy(filetype, "reg");
	else if S_ISDIR(mode) strcpy(filetype, "dir");
	else if S_ISSOCK(mode) strcpy(filetype, "sock");
	else strcpy(filetype, "fifo");
	return Py_BuildValue("{s:s,s:l,s:i,s:i,s:i,s:l,s:i,s:i,s:l,s:l}",
						 "type", filetype,
						 "size", (long int)sbuf.st_size,
						 "perms", (int)(mode & S_IRWXU),
						 "uid", (int)sbuf.st_uid,
						 "gid", (int)sbuf.st_gid,
						 "inode", (long int)sbuf.st_ino,
						 "devloc", (int)sbuf.st_dev,
						 "nlink", (int)sbuf.st_nlink,
						 "mtime", (long int)sbuf.st_mtime,
						 "atime", (long int)sbuf.st_atime);
  } else if S_ISLNK(mode) {
	/* Symbolic links */
	char linkname[1024];
	int len_link = readlink(filename, linkname, 1023);
	if (len_link < 0) {
	  PyErr_SetFromErrno(PyExc_OSError);
	  return NULL;
	}

	linkname[len_link] = '\0';
	return Py_BuildValue("{s:s,s:l,s:i,s:i,s:i,s:l,s:i,s:i,s:s}",
						 "type", "sym",
						 "size", (long int)sbuf.st_size,
						 "perms", (int)(mode & S_IRWXU),
						 "uid", (int)sbuf.st_uid,
						 "gid", (int)sbuf.st_gid,
						 "inode", (long int)sbuf.st_ino,
						 "devloc", (int)sbuf.st_dev,
						 "nlink", (int)sbuf.st_nlink,
						 "linkname", linkname);
  } else if (S_ISCHR(mode) || S_ISBLK(mode)) {
	/* Device files */
	char devtype[2];
	int devnums = (int)sbuf.st_rdev;
	if S_ISCHR(mode) strcpy(devtype, "c");
	else strcpy(devtype, "b");
	return Py_BuildValue("{s:s,s:l,s:i,s:i,s:i,s:l,s:i,s:i,s:O}",
						 "type", "dev",
						 "size", (long int)sbuf.st_size,
						 "perms", (int)(mode & S_IRWXU),
						 "uid", (int)sbuf.st_uid,
						 "gid", (int)sbuf.st_gid,
						 "inode", (long int)sbuf.st_ino,
						 "devloc", (int)sbuf.st_dev,
						 "nlink", (int)sbuf.st_nlink,
						 "devnums", Py_BuildValue("(s,i,i)", devtype,
												  devnums >> 8,
												  devnums & 0xff),
						 "mtime", (long int)sbuf.st_mtime,
						 "atime", (long int)sbuf.st_atime);
  } else {
	/* Unrecognized file type - pretend it isn't there */
	errno = ENOENT;
	PyErr_SetFromErrno(PyExc_OSError);
	return NULL;
  }
}

static PyObject *long2str(self, args)
	 PyObject *self;
	 PyObject *args;
{
  unsigned char s[7];
  int sindex;
  unsigned long long int l;
  PyObject *pylong;

  if (!PyArg_ParseTuple(args, "O", &pylong)) return NULL;
  l = PyLong_AsUnsignedLongLong(pylong);
  for(sindex = 0; sindex <= 6; sindex++) {
	s[sindex] = l % 256;
	l /= 256;
  }
  return Py_BuildValue("s#", s, 7);
}

static PyObject *str2long(self, args)
	 PyObject *self;
	 PyObject *args;
{
  unsigned char *s;
  unsigned long long int l = 0;
  int sindex, ssize;

  if (!PyArg_ParseTuple(args, "s#", &s, &ssize)) return NULL;
  if (ssize != 7) return Py_BuildValue("i", -1);
  for(sindex=6; sindex >= 0; sindex--)
	l = l*256 + s[sindex];
  return PyLong_FromLongLong(l);
}

static PyMethodDef CMethods[] = {
  {"make_file_dict", c_make_file_dict, METH_VARARGS,
   "Make dictionary from file stat"},
  {"long2str", long2str, METH_VARARGS,
   "Convert long int to 7 byte string"},
  {"str2long", str2long, METH_VARARGS,
   "Convert 7 byte string to long int"},
  {NULL, NULL, 0, NULL}
};

void initC(void)
{
  (void) Py_InitModule("C", CMethods);
}

