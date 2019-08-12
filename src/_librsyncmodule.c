/* ----------------------------------------------------------------------- *
 *
 *   Copyright 2002 2003 Ben Escoto <ben@emerose.org>
 *   Copyright 2007 Kenneth Loafman <kenneth@loafman.com>
 *
 *   This file is part of duplicity.
 *
 *   duplicity is free software; you can redistribute it and/or modify
 *   it under the terms of the GNU General Public License as published
 *   by the Free Software Foundation; either version 2 of the License,
 *   or (at your option) any later version.
 *
 *   duplicity is distributed in the hope that it will be useful, but
 *   WITHOUT ANY WARRANTY; without even the implied warranty of
 *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 *   General Public License for more details.
 *
 *   You should have received a copy of the GNU General Public License
 *   along with duplicity; if not, write to the Free Software
 *   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA
 *   02111-1307 USA
 *
 * ----------------------------------------------------------------------- */

#include <Python.h>
#include <errno.h>
#include <librsync.h>
#define RS_JOB_BLOCKSIZE 65536

static PyObject *librsyncError;

/* Sets python error string from result */
static void
_librsync_seterror(rs_result result, char *location)
{
  char error_string[200];
  sprintf(error_string, "librsync error %d while in %s", result, location);
  PyErr_SetString(librsyncError, error_string);
}


/* --------------- SigMaker Object for incremental signatures */
static PyTypeObject _librsync_SigMakerType;

typedef struct {
  PyObject_HEAD
  rs_job_t *sig_job;
} _librsync_SigMakerObject;

static PyObject*
_librsync_new_sigmaker(PyObject* self, PyObject* args)
{
  _librsync_SigMakerObject* sm;
  long blocklen;

  if (!PyArg_ParseTuple(args, "l:new_sigmaker", &blocklen))
    return NULL;

  sm = PyObject_New(_librsync_SigMakerObject, &_librsync_SigMakerType);
  if (sm == NULL) return NULL;

#ifdef RS_DEFAULT_STRONG_LEN /* librsync < 1.0.0 */
  sm->sig_job = rs_sig_begin((size_t)blocklen,
                             (size_t)RS_DEFAULT_STRONG_LEN);
#else /* librsync >= 1.0.0 */
  sm->sig_job = rs_sig_begin((size_t)blocklen,
                             (size_t)8, RS_MD4_SIG_MAGIC);
#endif
  return (PyObject*)sm;
}

static void
_librsync_sigmaker_dealloc(PyObject* self)
{
  rs_job_free(((_librsync_SigMakerObject *)self)->sig_job);
  PyObject_Del(self);
}

/* Take an input string, and generate a signature from it.  The output
   will be a triple (done, bytes_used, signature_string), where done
   is true iff there is no more data coming and bytes_used is the
   number of bytes of the input string processed.
*/
static PyObject *
_librsync_sigmaker_cycle(_librsync_SigMakerObject *self, PyObject *args)
{
  char *inbuf, outbuf[RS_JOB_BLOCKSIZE];
  int inbuf_length;
  rs_buffers_t buf;
  rs_result result;

#if PY_MAJOR_VERSION >= 3
  if (!PyArg_ParseTuple(args, "y#:cycle", &inbuf, &inbuf_length))
#else
  if (!PyArg_ParseTuple(args, "s#:cycle", &inbuf, &inbuf_length))
#endif
    return NULL;

  buf.next_in = inbuf;
  buf.avail_in = (size_t)inbuf_length;
  buf.next_out = outbuf;
  buf.avail_out = (size_t)RS_JOB_BLOCKSIZE;
  buf.eof_in = (inbuf_length == 0);

  result = rs_job_iter(self->sig_job, &buf);

  if (result != RS_DONE && result != RS_BLOCKED) {
    _librsync_seterror(result, "signature cycle");
    return NULL;
  }

#if PY_MAJOR_VERSION >= 3
  return Py_BuildValue("(ily#)", (result == RS_DONE),
#else
  return Py_BuildValue("(ils#)", (result == RS_DONE),
#endif
                       (long)inbuf_length - (long)buf.avail_in,
                       outbuf, RS_JOB_BLOCKSIZE - (long)buf.avail_out);
}

static PyMethodDef _librsync_sigmaker_methods[] = {
  {"cycle", (PyCFunction)_librsync_sigmaker_cycle, METH_VARARGS},
  {NULL, NULL, 0, NULL}  /* sentinel */
};

static PyTypeObject _librsync_SigMakerType = {
  PyVarObject_HEAD_INIT(NULL, 0)
  "sigmaker",
  sizeof(_librsync_SigMakerObject),
  0,
  _librsync_sigmaker_dealloc, /*tp_dealloc*/
  0,          /*tp_print*/
  0,          /*tp_getattr*/
  0,          /*tp_setattr*/
  0,          /*tp_compare*/
  0,          /*tp_repr*/
  0,          /*tp_as_number*/
  0,          /*tp_as_sequence*/
  0,          /*tp_as_mapping*/
  0,          /*tp_hash */
  0,          /*tp_call*/
  0,          /*tp_str*/
  PyObject_GenericGetAttr, /*tp_getattro*/
  PyObject_GenericSetAttr, /*tp_setattro*/
  0,          /*tp_as_buffer*/
  Py_TPFLAGS_DEFAULT, /*tp_flags*/
  0,          /*tp_doc*/
  0,          /*tp_traverse*/
  0,          /*tp_clear*/
  0,          /*tp_richcompare*/
  0,          /*tp_weaklistoffset*/
  0,          /*tp_iter*/
  0,          /*tp_iternext*/
  _librsync_sigmaker_methods, /*tp_methods*/
};


/* --------------- DeltaMaker Object for incremental deltas */

static PyTypeObject _librsync_DeltaMakerType;

typedef struct {
  PyObject_HEAD
  rs_job_t *delta_job;
  rs_signature_t *sig_ptr;
} _librsync_DeltaMakerObject;

/* Call with the entire signature loaded into one big string */
static PyObject*
_librsync_new_deltamaker(PyObject* self, PyObject* args)
{
  _librsync_DeltaMakerObject* dm;
  char *sig_string, outbuf[RS_JOB_BLOCKSIZE];
  int sig_length;
  rs_job_t *sig_loader;
  rs_signature_t *sig_ptr;
  rs_buffers_t buf;
  rs_result result;

#if PY_MAJOR_VERSION >= 3
  if (!PyArg_ParseTuple(args,"y#:new_deltamaker", &sig_string, &sig_length))
#else
  if (!PyArg_ParseTuple(args,"s#:new_deltamaker", &sig_string, &sig_length))
#endif
    return NULL;

  dm = PyObject_New(_librsync_DeltaMakerObject, &_librsync_DeltaMakerType);
  if (dm == NULL) return NULL;

  /* Put signature at sig_ptr and build hash */
  sig_loader = rs_loadsig_begin(&sig_ptr);
  buf.next_in = sig_string;
  buf.avail_in = (size_t)sig_length;
  buf.next_out = outbuf;
  buf.avail_out = (size_t)RS_JOB_BLOCKSIZE;
  buf.eof_in = 1;
  result = rs_job_iter(sig_loader, &buf);
  rs_job_free(sig_loader);
  if (result != RS_DONE) {
    _librsync_seterror(result, "delta rs_signature_t builder");
    return NULL;
  }
  if ((result = rs_build_hash_table(sig_ptr)) != RS_DONE) {
    _librsync_seterror(result, "delta rs_build_hash_table");
    return NULL;
  }

  dm->sig_ptr = sig_ptr;
  dm->delta_job = rs_delta_begin(sig_ptr);
  return (PyObject*)dm;
}

static void
_librsync_deltamaker_dealloc(PyObject* self)
{
  _librsync_DeltaMakerObject *dm = (_librsync_DeltaMakerObject *)self;
  rs_signature_t *sig_ptr = dm->sig_ptr;

  rs_free_sumset(sig_ptr);
  rs_job_free(dm->delta_job);
  PyObject_Del(self);
}

/* Take a chunk of the new file in an input string, and return a
   triple (done bytes_used, delta_string), where done is true iff no
   more data is coming and bytes_used is the number of bytes of the
   input string processed.
*/
static PyObject *
_librsync_deltamaker_cycle(_librsync_DeltaMakerObject *self, PyObject *args)
{
  char *inbuf, outbuf[RS_JOB_BLOCKSIZE];
  int inbuf_length;
  rs_buffers_t buf;
  rs_result result;

#if PY_MAJOR_VERSION >= 3
  if (!PyArg_ParseTuple(args, "y#:cycle", &inbuf, &inbuf_length))
#else
  if (!PyArg_ParseTuple(args, "s#:cycle", &inbuf, &inbuf_length))
#endif
    return NULL;

  buf.next_in = inbuf;
  buf.avail_in = (size_t)inbuf_length;
  buf.next_out = outbuf;
  buf.avail_out = (size_t)RS_JOB_BLOCKSIZE;
  buf.eof_in = (inbuf_length == 0);

  result = rs_job_iter(self->delta_job, &buf);
  if (result != RS_DONE && result != RS_BLOCKED) {
    _librsync_seterror(result, "delta cycle");
    return NULL;
  }

#if PY_MAJOR_VERSION >= 3
  return Py_BuildValue("(ily#)", (result == RS_DONE),
#else
  return Py_BuildValue("(ils#)", (result == RS_DONE),
#endif
                       (long)inbuf_length - (long)buf.avail_in,
                       outbuf, RS_JOB_BLOCKSIZE - (long)buf.avail_out);
}

static PyMethodDef _librsync_deltamaker_methods[] = {
  {"cycle", (PyCFunction)_librsync_deltamaker_cycle, METH_VARARGS},
  {NULL, NULL, 0, NULL}  /* sentinel */
};

static PyTypeObject _librsync_DeltaMakerType = {
  PyVarObject_HEAD_INIT(NULL, 0)
  "deltamaker",
  sizeof(_librsync_DeltaMakerObject),
  0,
  _librsync_deltamaker_dealloc, /*tp_dealloc*/
  0,          /*tp_print*/
  0,          /*tp_getattr*/
  0,          /*tp_setattr*/
  0,          /*tp_compare*/
  0,          /*tp_repr*/
  0,          /*tp_as_number*/
  0,          /*tp_as_sequence*/
  0,          /*tp_as_mapping*/
  0,          /*tp_hash */
  0,          /*tp_call*/
  0,          /*tp_str*/
  PyObject_GenericGetAttr, /*tp_getattro*/
  PyObject_GenericSetAttr, /*tp_setattro*/
  0,          /*tp_as_buffer*/
  Py_TPFLAGS_DEFAULT, /*tp_flags*/
  0,          /*tp_doc*/
  0,          /*tp_traverse*/
  0,          /*tp_clear*/
  0,          /*tp_richcompare*/
  0,          /*tp_weaklistoffset*/
  0,          /*tp_iter*/
  0,          /*tp_iternext*/
  _librsync_deltamaker_methods, /*tp_methods*/
};


/* --------------- PatchMaker Object for incremental patching */


static PyTypeObject _librsync_PatchMakerType;

typedef struct {
  PyObject_HEAD
  rs_job_t *patch_job;
  PyObject *basis_file;
  FILE *cfile;
} _librsync_PatchMakerObject;

/* Call with the basis file */
static PyObject*
_librsync_new_patchmaker(PyObject* self, PyObject* args)
{
  _librsync_PatchMakerObject* pm;
  PyObject *python_file;
  int fd;

  if (!PyArg_ParseTuple(args, "O:new_patchmaker", &python_file))
    return NULL;
  fd = PyObject_AsFileDescriptor(python_file);
  if (fd == -1) {
    PyErr_SetString(PyExc_TypeError, "Need true file object");
    return NULL;
  }
  /* get our own private copy of the file, so we can close it later. */
  fd = dup(fd);
  if (fd == -1) {
    char buf[256];
    strerror_r(errno, buf, sizeof(buf));
    PyErr_SetString(PyExc_TypeError, buf);
    return NULL;
  }
  Py_INCREF(python_file);

  pm = PyObject_New(_librsync_PatchMakerObject, &_librsync_PatchMakerType);
  if (pm == NULL) return NULL;

  pm->basis_file = python_file;
  pm->cfile = fdopen(fd, "rb");
  pm->patch_job = rs_patch_begin(rs_file_copy_cb, pm->cfile);

  return (PyObject*)pm;
}

static void
_librsync_patchmaker_dealloc(PyObject* self)
{
  _librsync_PatchMakerObject *pm = (_librsync_PatchMakerObject *)self;
  Py_DECREF(pm->basis_file);
  rs_job_free(pm->patch_job);
  if (pm->cfile) {
    fclose(pm->cfile);
  }
  PyObject_Del(self);
}

/* Take a chunk of the delta file in an input string, and return a
   triple (done, bytes_used, patched_string), where done is true iff
   there is no more data coming out and bytes_used is the number of
   bytes of the input string processed.
*/
static PyObject *
_librsync_patchmaker_cycle(_librsync_PatchMakerObject *self, PyObject *args)
{
  char *inbuf, outbuf[RS_JOB_BLOCKSIZE];
  int inbuf_length;
  rs_buffers_t buf;
  rs_result result;

#if PY_MAJOR_VERSION >= 3
  if (!PyArg_ParseTuple(args, "y#:cycle", &inbuf, &inbuf_length))
#else
  if (!PyArg_ParseTuple(args, "s#:cycle", &inbuf, &inbuf_length))
#endif
    return NULL;

  buf.next_in = inbuf;
  buf.avail_in = (size_t)inbuf_length;
  buf.next_out = outbuf;
  buf.avail_out = (size_t)RS_JOB_BLOCKSIZE;
  buf.eof_in = (inbuf_length == 0);

  result = rs_job_iter(self->patch_job, &buf);
  if (result != RS_DONE && result != RS_BLOCKED) {
    _librsync_seterror(result, "patch cycle");
    return NULL;
  }

#if PY_MAJOR_VERSION >= 3
  return Py_BuildValue("(ily#)", (result == RS_DONE),
#else
  return Py_BuildValue("(ils#)", (result == RS_DONE),
#endif
                       (long)inbuf_length - (long)buf.avail_in,
                       outbuf, RS_JOB_BLOCKSIZE - (long)buf.avail_out);
}

static PyMethodDef _librsync_patchmaker_methods[] = {
  {"cycle", (PyCFunction)_librsync_patchmaker_cycle, METH_VARARGS},
  {NULL, NULL, 0, NULL}  /* sentinel */
};

static PyTypeObject _librsync_PatchMakerType = {
  PyVarObject_HEAD_INIT(NULL, 0)
  "patchmaker",
  sizeof(_librsync_PatchMakerObject),
  0,
  _librsync_patchmaker_dealloc, /*tp_dealloc*/
  0,          /*tp_print*/
  0,          /*tp_getattr*/
  0,          /*tp_setattr*/
  0,          /*tp_compare*/
  0,          /*tp_repr*/
  0,          /*tp_as_number*/
  0,          /*tp_as_sequence*/
  0,          /*tp_as_mapping*/
  0,          /*tp_hash */
  0,          /*tp_call*/
  0,          /*tp_str*/
  PyObject_GenericGetAttr, /*tp_getattro*/
  PyObject_GenericSetAttr, /*tp_setattro*/
  0,          /*tp_as_buffer*/
  Py_TPFLAGS_DEFAULT, /*tp_flags*/
  0,          /*tp_doc*/
  0,          /*tp_traverse*/
  0,          /*tp_clear*/
  0,          /*tp_richcompare*/
  0,          /*tp_weaklistoffset*/
  0,          /*tp_iter*/
  0,          /*tp_iternext*/
  _librsync_patchmaker_methods, /*tp_methods*/
};


/* --------------- _librsync module definition */

#if PY_MAJOR_VERSION >= 3
#define MOD_DEF(ob, name, doc, methods) \
  static struct PyModuleDef moduledef = { \
    PyModuleDef_HEAD_INIT, name, doc, -1, methods, }; \
  ob = PyModule_Create(&moduledef);
#else
#define MOD_DEF(ob, name, doc, methods) \
  ob = Py_InitModule3(name, methods, doc);
#endif

static PyMethodDef _librsyncMethods[] = {
  {"new_sigmaker", _librsync_new_sigmaker, METH_VARARGS,
   "Return a sigmaker object, for finding the signature of an object"},
  {"new_deltamaker", _librsync_new_deltamaker, METH_VARARGS,
   "Return a deltamaker object, for computing deltas"},
  {"new_patchmaker", _librsync_new_patchmaker, METH_VARARGS,
   "Return a patchmaker object, for patching basis files"},
  {NULL, NULL, 0, NULL}
};

static PyObject *
moduleinit(void)
{
  PyObject *m, *d;

  Py_TYPE(&_librsync_SigMakerType) = &PyType_Type;
  Py_TYPE(&_librsync_DeltaMakerType) = &PyType_Type;

  MOD_DEF(m, "_librsync", "", _librsyncMethods)
  if (m == NULL)
      return NULL;

  d = PyModule_GetDict(m);
  librsyncError = PyErr_NewException("_librsync.librsyncError", NULL, NULL);
  PyDict_SetItemString(d, "librsyncError", librsyncError);
  PyDict_SetItemString(d, "RS_JOB_BLOCKSIZE",
                       Py_BuildValue("l", (long)RS_JOB_BLOCKSIZE));
  PyDict_SetItemString(d, "RS_DEFAULT_BLOCK_LEN",
                       Py_BuildValue("l", (long)RS_DEFAULT_BLOCK_LEN));

  return m;
}

#if PY_MAJOR_VERSION < 3
void init_librsync(void)
{
  moduleinit();
}
#else
PyObject *PyInit__librsync(void)
{
  return moduleinit();
}
#endif
