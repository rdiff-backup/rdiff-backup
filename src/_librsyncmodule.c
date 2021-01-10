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
 *   Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
 *   02110-1301, USA
 *
 * ----------------------------------------------------------------------- */
#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <librsync.h>
#define RSM_JOB_BLOCKSIZE 65536

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
  PyObject *x_attr;
  rs_job_t *sig_job;
} _librsync_SigMakerObject;

static PyObject*
_librsync_new_sigmaker(PyObject* self, PyObject* args)
{
  _librsync_SigMakerObject* sm;
  Py_ssize_t blocklen;

  if (!PyArg_ParseTuple(args, "l:new_sigmaker", &blocklen))
	return NULL;

  sm = PyObject_New(_librsync_SigMakerObject, &_librsync_SigMakerType);
  if (sm == NULL) return NULL;
  sm->x_attr = NULL;

#ifdef RS_DEFAULT_STRONG_LEN
  sm->sig_job = rs_sig_begin((size_t)blocklen,
                (size_t)RS_DEFAULT_STRONG_LEN);
#else
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
   is true if there is no more data coming and bytes_used is the
   number of bytes of the input string processed.
*/
static PyObject *
_librsync_sigmaker_cycle(_librsync_SigMakerObject *self, PyObject *args)
{
  char *inbuf, outbuf[RSM_JOB_BLOCKSIZE];
  Py_ssize_t inbuf_length;
  rs_buffers_t buf;
  rs_result result;

  if (!PyArg_ParseTuple(args, "y#:cycle", &inbuf, &inbuf_length))
	return NULL;

  buf.next_in = inbuf;
  buf.avail_in = (size_t)inbuf_length;
  buf.next_out = outbuf;
  buf.avail_out = (size_t)RSM_JOB_BLOCKSIZE;
  buf.eof_in = (inbuf_length == 0);

  result = rs_job_iter(self->sig_job, &buf);

  if (result != RS_DONE && result != RS_BLOCKED) {
	_librsync_seterror(result, "signature cycle");
	return NULL;
  }

  return Py_BuildValue("(iny#)", (result == RS_DONE),
		  (Py_ssize_t)inbuf_length - (Py_ssize_t)buf.avail_in,
		  outbuf, (Py_ssize_t)RSM_JOB_BLOCKSIZE - (Py_ssize_t)buf.avail_out);
}

static PyMethodDef _librsync_sigmaker_methods[] = {
  {"cycle", (PyCFunction)_librsync_sigmaker_cycle, METH_VARARGS},
  {NULL, NULL, 0, NULL}  /* sentinel */
};

static PyObject *
_librsync_sigmaker_getattro(_librsync_SigMakerObject *sm, PyObject *nameobj)
{
  /* transform bitearray object into string */
  char *name = "";
  if (PyByteArray_Check(nameobj))
    name = PyByteArray_AsString(nameobj);

  if (sm->x_attr != NULL) {
	PyObject *v = PyDict_GetItemString(sm->x_attr, name);
	if (v != NULL) {
	  Py_INCREF(v);
	  return v;
	}
  }
  return PyObject_GenericGetAttr((PyObject*) sm, nameobj);
}

static int
_librsync_sigmaker_setattr(_librsync_SigMakerObject *sm,
									   char *name, PyObject *v)
{
  if (sm->x_attr == NULL) {
	sm->x_attr = PyDict_New();
	if (sm->x_attr == NULL) return -1;
  }
  if (v == NULL) {
	int rv = PyDict_DelItemString(sm->x_attr, name);
	if (rv < 0)
	  PyErr_SetString(PyExc_AttributeError,
					  "delete non-existing sigmaker attribute");
	return rv;
  }
  else return PyDict_SetItemString(sm->x_attr, name, v);
}

static PyTypeObject _librsync_SigMakerType = {
  PyVarObject_HEAD_INIT(NULL, 0)
  "sigmaker",
  sizeof(_librsync_SigMakerObject),
  0,
  _librsync_sigmaker_dealloc, /*tp_dealloc*/
  0,          /*tp_print*/
  0,          /*tp_getattr*/
  (setattrfunc)_librsync_sigmaker_setattr, /*tp_setattr*/
  0,          /*tp_compare*/
  0,          /*tp_repr*/
  0,          /*tp_as_number*/
  0,          /*tp_as_sequence*/
  0,          /*tp_as_mapping*/
  0,          /*tp_hash */
  0,          /* tp_call */
  0,          /* tp_str */
  (getattrofunc)_librsync_sigmaker_getattro, /* tp_getattro */
  0,          /* tp_setattro */
  0,          /* tp_as_buffer */
  Py_TPFLAGS_DEFAULT, /* tp_flags */
  0,          /* tp_doc */
  0,          /* tp_traverse */
  0,          /* tp_clear */
  0,          /* tp_richcompare */
  0,          /* tp_weaklistoffset */
  0,          /* tp_iter */
  0,          /* tp_iternext */
  _librsync_sigmaker_methods, /* tp_methods */
  0,          /* tp_members */
};


/* --------------- DeltaMaker Object for incremental deltas */

static PyTypeObject _librsync_DeltaMakerType;

typedef struct {
  PyObject_HEAD
  PyObject *x_attr;
  rs_job_t *delta_job;
  rs_signature_t *sig_ptr;
} _librsync_DeltaMakerObject;

/* Call with the entire signature loaded into one big string */
static PyObject*
_librsync_new_deltamaker(PyObject* self, PyObject* args)
{
  _librsync_DeltaMakerObject* dm;
  char *sig_string, outbuf[RSM_JOB_BLOCKSIZE];
  Py_ssize_t sig_length;
  rs_job_t *sig_loader;
  rs_signature_t *sig_ptr;
  rs_buffers_t buf;
  rs_result result;
  if (!PyArg_ParseTuple(args,"y#:new_deltamaker", &sig_string, &sig_length))
	return NULL;
  dm = PyObject_New(_librsync_DeltaMakerObject, &_librsync_DeltaMakerType);
  if (dm == NULL) return NULL;
  dm->x_attr = NULL;
  /* Put signature at sig_ptr and build hash */
  sig_loader = rs_loadsig_begin(&sig_ptr);
  buf.next_in = sig_string;
  buf.avail_in = (size_t)sig_length;
  buf.next_out = outbuf;
  buf.avail_out = (size_t)RSM_JOB_BLOCKSIZE;
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
  char *inbuf, outbuf[RSM_JOB_BLOCKSIZE];
  Py_ssize_t inbuf_length;
  rs_buffers_t buf;
  rs_result result;

  if (!PyArg_ParseTuple(args, "y#:cycle", &inbuf, &inbuf_length))
	return NULL;

  buf.next_in = inbuf;
  buf.avail_in = (size_t)inbuf_length;
  buf.next_out = outbuf;
  buf.avail_out = (size_t)RSM_JOB_BLOCKSIZE;
  buf.eof_in = (inbuf_length == 0);

  result = rs_job_iter(self->delta_job, &buf);
  if (result != RS_DONE && result != RS_BLOCKED) {
	_librsync_seterror(result, "delta cycle");
	return NULL;
  }

  return Py_BuildValue("(iny#)", (result == RS_DONE),
		  (Py_ssize_t)inbuf_length - (Py_ssize_t)buf.avail_in,
		  outbuf, (Py_ssize_t)RSM_JOB_BLOCKSIZE - (Py_ssize_t)buf.avail_out);
}

static PyMethodDef _librsync_deltamaker_methods[] = {
  {"cycle", (PyCFunction)_librsync_deltamaker_cycle, METH_VARARGS},
  {NULL, NULL, 0, NULL}  /* sentinel */
};

static PyObject *
_librsync_deltamaker_getattro(_librsync_DeltaMakerObject *dm, PyObject *nameobj)
{
  /* transform bytearray object into string */
  char *name = "";
  if (PyByteArray_Check(nameobj))
    name = PyByteArray_AsString(nameobj);

  if (dm->x_attr != NULL) {
	PyObject *v = PyDict_GetItemString(dm->x_attr, name);
	if (v != NULL) {
	  Py_INCREF(v);
	  return v;
	}
  }
  return PyObject_GenericGetAttr((PyObject*) dm, nameobj);
}

static int
_librsync_deltamaker_setattr(_librsync_DeltaMakerObject *dm,
							 char *name, PyObject *v)
{
  if (dm->x_attr == NULL) {
	dm->x_attr = PyDict_New();
	if (dm->x_attr == NULL) return -1;
  }
  if (v == NULL) {
	int rv = PyDict_DelItemString(dm->x_attr, name);
	if (rv < 0)
	  PyErr_SetString(PyExc_AttributeError,
					  "delete non-existing deltamaker attribute");
	return rv;
  }
  else return PyDict_SetItemString(dm->x_attr, name, v);
}

static PyTypeObject _librsync_DeltaMakerType = {
  PyVarObject_HEAD_INIT(NULL, 0)
  "deltamaker",
  sizeof(_librsync_DeltaMakerObject),
  0,
  _librsync_deltamaker_dealloc, /*tp_dealloc*/
  0,          /*tp_print*/
  0,          /*tp_getattr*/
  (setattrfunc)_librsync_deltamaker_setattr, /*tp_setattr*/
  0,          /*tp_compare*/
  0,          /*tp_repr*/
  0,          /*tp_as_number*/
  0,          /*tp_as_sequence*/
  0,          /*tp_as_mapping*/
  0,          /*tp_hash */
  0,          /* tp_call */
  0,          /* tp_str */
  (getattrofunc)_librsync_deltamaker_getattro, /* tp_getattro */
  0,          /* tp_setattro */
  0,          /* tp_as_buffer */
  Py_TPFLAGS_DEFAULT, /* tp_flags */
  0,          /* tp_doc */
  0,          /* tp_traverse */
  0,          /* tp_clear */
  0,          /* tp_richcompare */
  0,          /* tp_weaklistoffset */
  0,          /* tp_iter */
  0,          /* tp_iternext */
  _librsync_deltamaker_methods, /* tp_methods */
  0,          /* tp_members */
};


/* --------------- PatchMaker Object for incremental patching 

   Librsync needs a FILE* handle, but Python only gives us file
   descriptors (int); we need fdopen() to convert a fd to a FILE*
   handle.  Such handle will have to be closed with fclose().
*/


static PyTypeObject _librsync_PatchMakerType;

typedef struct {
  PyObject_HEAD
  PyObject *x_attr;
  rs_job_t *patch_job;
  FILE *patch_file;
  PyObject *basis_file;
} _librsync_PatchMakerObject;

/* Call with the basis file */
static PyObject*
_librsync_new_patchmaker(PyObject* self, PyObject* args)
{
  _librsync_PatchMakerObject* pm;
  PyObject *python_file;

  if (!PyArg_ParseTuple(args, "O:new_patchmaker", &python_file))
	return NULL;
  int python_fd = PyObject_AsFileDescriptor(python_file);
  if (python_fd < 0) {
	PyErr_SetString(PyExc_TypeError, "Need true file object");
	return NULL;
  }
  Py_INCREF(python_file);

  pm = PyObject_New(_librsync_PatchMakerObject, &_librsync_PatchMakerType);
  if (pm == NULL) return NULL;
  pm->x_attr = NULL;

  pm->basis_file = python_file;
  /* We duplicate python_fd so that we will be able to call fclose()
     on our FILE* handle, avoiding any conflicts with the destruction
     of python_file. */
  int dup_fd = dup(python_fd);
  if (dup_fd < 0) {
      return PyErr_SetFromErrno(librsyncError);
  }
  pm->patch_file = fdopen(dup_fd, "rb"); /* same mode as in the Python code */
  if (pm->patch_file == NULL) {
      return PyErr_SetFromErrno(librsyncError);
  }
  pm->patch_job = rs_patch_begin(rs_file_copy_cb, pm->patch_file);

  return (PyObject*)pm;
}

static void
_librsync_patchmaker_dealloc(PyObject* self)
{
  _librsync_PatchMakerObject *pm = (_librsync_PatchMakerObject *)self;
  Py_DECREF(pm->basis_file);
  rs_job_free(pm->patch_job);
  fclose(pm->patch_file);
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
  char *inbuf, outbuf[RSM_JOB_BLOCKSIZE];
  Py_ssize_t inbuf_length;
  rs_buffers_t buf;
  rs_result result;

  if (!PyArg_ParseTuple(args, "y#:cycle", &inbuf, &inbuf_length))
	return NULL;

  buf.next_in = inbuf;
  buf.avail_in = (size_t)inbuf_length;
  buf.next_out = outbuf;
  buf.avail_out = (size_t)RSM_JOB_BLOCKSIZE;
  buf.eof_in = (inbuf_length == 0);

  result = rs_job_iter(self->patch_job, &buf);
  if (result != RS_DONE && result != RS_BLOCKED) {
	_librsync_seterror(result, "patch cycle");
	return NULL;
  }

  return Py_BuildValue("(iny#)", (result == RS_DONE),
		  (Py_ssize_t)inbuf_length - (Py_ssize_t)buf.avail_in,
		  outbuf, (Py_ssize_t)RSM_JOB_BLOCKSIZE - (Py_ssize_t)buf.avail_out);
}

static PyMethodDef _librsync_patchmaker_methods[] = {
  {"cycle", (PyCFunction)_librsync_patchmaker_cycle, METH_VARARGS},
  {NULL, NULL, 0, NULL}  /* sentinel */
};

static PyObject *
_librsync_patchmaker_getattro(_librsync_PatchMakerObject *pm, PyObject *nameobj)
{
  /* transform bytearray object into string */
  char *name = "";
  if (PyByteArray_Check(nameobj))
    name = PyByteArray_AsString(nameobj);

  if (pm->x_attr != NULL) {
	PyObject *v = PyDict_GetItemString(pm->x_attr, name);
	if (v != NULL) {
	  Py_INCREF(v);
	  return v;
	}
  }
  return PyObject_GenericGetAttr((PyObject*) pm, nameobj);
}

static int
_librsync_patchmaker_setattr(_librsync_PatchMakerObject *pm,
							 char *name, PyObject *v)
{
  if (pm->x_attr == NULL) {
	pm->x_attr = PyDict_New();
	if (pm->x_attr == NULL) return -1;
  }
  if (v == NULL) {
	int rv = PyDict_DelItemString(pm->x_attr, name);
	if (rv < 0)
	  PyErr_SetString(PyExc_AttributeError,
					  "delete non-existing patchmaker attribute");
	return rv;
  }
  else return PyDict_SetItemString(pm->x_attr, name, v);
}

static PyTypeObject _librsync_PatchMakerType = {
  PyVarObject_HEAD_INIT(NULL, 0)
  "patchmaker",
  sizeof(_librsync_PatchMakerObject),
  0,
  _librsync_patchmaker_dealloc, /*tp_dealloc*/
  0,          /*tp_print*/
  0,          /*tp_getattr*/
  (setattrfunc)_librsync_patchmaker_setattr, /*tp_setattr*/
  0,          /*tp_compare*/
  0,          /*tp_repr*/
  0,          /*tp_as_number*/
  0,          /*tp_as_sequence*/
  0,          /*tp_as_mapping*/
  0,          /*tp_hash */
  0,          /* tp_call */
  0,          /* tp_str */
  (getattrofunc)_librsync_patchmaker_getattro, /* tp_getattro */
  0,          /* tp_setattro */
  0,          /* tp_as_buffer */
  Py_TPFLAGS_DEFAULT, /* tp_flags */
  0,          /* tp_doc */
  0,          /* tp_traverse */
  0,          /* tp_clear */
  0,          /* tp_richcompare */
  0,          /* tp_weaklistoffset */
  0,          /* tp_iter */
  0,          /* tp_iternext */
  _librsync_patchmaker_methods, /* tp_methods */
  0,          /* tp_members */
};


/* --------------- _librsync module definition */

static PyMethodDef _librsyncMethods[] = {
  {"new_sigmaker", _librsync_new_sigmaker, METH_VARARGS,
   "Return a sigmaker object, for finding the signature of an object"},
  {"new_deltamaker", _librsync_new_deltamaker, METH_VARARGS,
   "Return a deltamaker object, for computing deltas"},
  {"new_patchmaker", _librsync_new_patchmaker, METH_VARARGS,
   "Return a patchmaker object, for patching basis files"},
  {NULL, NULL, 0, NULL}
};

PyMODINIT_FUNC PyInit__librsync(void)
{
  PyObject *m, *d;

  Py_TYPE(&_librsync_SigMakerType) = &PyType_Type;
  Py_TYPE(&_librsync_DeltaMakerType) = &PyType_Type;
  static struct PyModuleDef librsync_def = {
            PyModuleDef_HEAD_INIT, "_librsync", "RSync Lib", -1, _librsyncMethods, };
  m = PyModule_Create(&librsync_def);
  if (m == NULL)
    return NULL;

  d = PyModule_GetDict(m);
  librsyncError = PyErr_NewException("_librsync.librsyncError", NULL, NULL);
  PyDict_SetItemString(d, "librsyncError", librsyncError);
  PyDict_SetItemString(d, "RSM_JOB_BLOCKSIZE",
		  Py_BuildValue("n", (Py_ssize_t)RSM_JOB_BLOCKSIZE));
  PyDict_SetItemString(d, "RS_DEFAULT_BLOCK_LEN",
		  Py_BuildValue("n", (Py_ssize_t)RS_DEFAULT_BLOCK_LEN));

  return m;
}
