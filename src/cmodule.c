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


/* choose the appropriate stat and fstat functions and return structs */
/* This code taken from Python's posixmodule.c */
#if defined(MS_WIN64) || defined(MS_WIN32)
#	define SYNC _flushall
#else
#	define SYNC sync
#endif

static PyObject *UnknownFileTypeError;
static PyObject *my_sync(PyObject *self, PyObject *args);


/* Run sync() and return None */
static PyObject *my_sync(self, args)
	 PyObject *self;
	 PyObject *args;
{
  if (!PyArg_ParseTuple(args, "")) return NULL;
  SYNC();
  return Py_BuildValue("");
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

  if (!PyArg_ParseTuple(args, "y", &s)) return NULL;
  return Py_BuildValue("y", quote(s));
}

/* Translate unquote above into python */
static PyObject *acl_unquote(PyObject *self, PyObject *args)
{
  char *s;

  if (!PyArg_ParseTuple(args, "y", &s)) return NULL;
  return Py_BuildValue("y", unquote(s));
}

/* ------------- Python export lists -------------------------------- */

static PyMethodDef CMethods[] = {
  {"sync", my_sync, METH_VARARGS, "sync buffers to disk"},
  {"acl_quote", acl_quote, METH_VARARGS,
   "Quote string, escaping non-printables"},
  {"acl_unquote", acl_unquote, METH_VARARGS,
   "Unquote string, producing original input to quote"},
  {NULL, NULL, 0, NULL}
};

static struct PyModuleDef CModuledef = {
  PyModuleDef_HEAD_INIT,
  "C",                 /* m_name */
  "C wrapper module",  /* m_doc */
  -1,                  /* m_size */
  CMethods,            /* m_methods */
  NULL,                /* m_reload */
  NULL,                /* m_traverse */
  NULL,                /* m_clear */
  NULL,                /* m_free */
};

PyMODINIT_FUNC PyInit_C(void)
{
  PyObject *m, *d;

  m = PyModule_Create(&CModuledef);
  if (m == NULL)
    return NULL;

  d = PyModule_GetDict(m);
  UnknownFileTypeError = PyErr_NewException("C.UnknownFileTypeError",
											NULL, NULL);
  PyDict_SetItemString(d, "UnknownFileTypeError", UnknownFileTypeError);

  return m;
}
