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
#include <rsync.h>
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
staticforward PyTypeObject _librsync_SigMakerType;

typedef struct {
  PyObject_HEAD
  PyObject *x_attr;
  rs_job_t *sig_job;
} _librsync_SigMakerObject;

static PyObject*
_librsync_new_sigmaker(PyObject* self, PyObject* args)
{
  _librsync_SigMakerObject* sm;
  
  if (!PyArg_ParseTuple(args,":new_sigmaker"))
	return NULL;

  sm = PyObject_New(_librsync_SigMakerObject, &_librsync_SigMakerType);
  if (sm == NULL) return NULL;
  sm->x_attr = NULL;

  sm->sig_job = rs_sig_begin((size_t)RS_DEFAULT_BLOCK_LEN,
							 (size_t)RS_DEFAULT_STRONG_LEN);
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
  long inbuf_length;
  rs_buffers_t buf;
  rs_result result;

  if (!PyArg_ParseTuple(args, "s#:cycle", &inbuf, &inbuf_length))
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

  return Py_BuildValue("(ils#)", (result == RS_DONE),
					   inbuf_length - (long)buf.avail_in,
					   outbuf, RS_JOB_BLOCKSIZE - (long)buf.avail_out);
}

static PyMethodDef _librsync_sigmaker_methods[] = {
  {"cycle", (PyCFunction)_librsync_sigmaker_cycle, METH_VARARGS},
  {NULL, NULL, 0, NULL}  /* sentinel */
};

static PyObject *
_librsync_sigmaker_getattr(_librsync_SigMakerObject *sm,
											 char *name)
{
  if (sm->x_attr != NULL) {
	PyObject *v = PyDict_GetItemString(sm->x_attr, name);
	if (v != NULL) {
	  Py_INCREF(v);
	  return v;
	}
  }
  return Py_FindMethod(_librsync_sigmaker_methods, (PyObject *)sm, name);
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
  PyObject_HEAD_INIT(NULL)
  0,
  "sigmaker",
  sizeof(_librsync_SigMakerObject),
  0,
  _librsync_sigmaker_dealloc, /*tp_dealloc*/
  0,          /*tp_print*/
  (getattrfunc)_librsync_sigmaker_getattr, /*tp_getattr*/
  (setattrfunc)_librsync_sigmaker_setattr, /*tp_setattr*/
  0,          /*tp_compare*/
  0,          /*tp_repr*/
  0,          /*tp_as_number*/
  0,          /*tp_as_sequence*/
  0,          /*tp_as_mapping*/
  0,          /*tp_hash */
};


/* --------------- DeltaMaker Object for incremental deltas */

staticforward PyTypeObject _librsync_DeltaMakerType;

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
  char *sig_string, outbuf[RS_JOB_BLOCKSIZE];
  long sig_length;
  rs_job_t *sig_loader;
  rs_signature_t *sig_ptr;
  rs_buffers_t buf;
  rs_result result;

  if (!PyArg_ParseTuple(args,"s#:new_deltamaker", &sig_string, &sig_length))
	return NULL;

  dm = PyObject_New(_librsync_DeltaMakerObject, &_librsync_DeltaMakerType);
  if (dm == NULL) return NULL;
  dm->x_attr = NULL;

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
  long inbuf_length;
  rs_buffers_t buf;
  rs_result result;

  if (!PyArg_ParseTuple(args, "s#:cycle", &inbuf, &inbuf_length))
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

  return Py_BuildValue("(ils#)", (result == RS_DONE),
					   inbuf_length - (long)buf.avail_in,
					   outbuf, RS_JOB_BLOCKSIZE - (long)buf.avail_out);
}

static PyMethodDef _librsync_deltamaker_methods[] = {
  {"cycle", (PyCFunction)_librsync_deltamaker_cycle, METH_VARARGS},
  {NULL, NULL, 0, NULL}  /* sentinel */
};

static PyObject *
_librsync_deltamaker_getattr(_librsync_DeltaMakerObject *dm, char *name)
{
  if (dm->x_attr != NULL) {
	PyObject *v = PyDict_GetItemString(dm->x_attr, name);
	if (v != NULL) {
	  Py_INCREF(v);
	  return v;
	}
  }
  return Py_FindMethod(_librsync_deltamaker_methods, (PyObject *)dm, name);
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
  PyObject_HEAD_INIT(NULL)
  0,
  "deltamaker",
  sizeof(_librsync_DeltaMakerObject),
  0,
  _librsync_deltamaker_dealloc, /*tp_dealloc*/
  0,          /*tp_print*/
  (getattrfunc)_librsync_deltamaker_getattr, /*tp_getattr*/
  (setattrfunc)_librsync_deltamaker_setattr, /*tp_setattr*/
  0,          /*tp_compare*/
  0,          /*tp_repr*/
  0,          /*tp_as_number*/
  0,          /*tp_as_sequence*/
  0,          /*tp_as_mapping*/
  0,          /*tp_hash */
};


/* --------------- PatchMaker Object for incremental patching */


staticforward PyTypeObject _librsync_PatchMakerType;

typedef struct {
  PyObject_HEAD
  PyObject *x_attr;
  rs_job_t *patch_job;
  PyObject *basis_file;
} _librsync_PatchMakerObject;

/* Call with the basis file */
static PyObject*
_librsync_new_patchmaker(PyObject* self, PyObject* args)
{
  _librsync_PatchMakerObject* pm;
  PyObject *python_file;
  FILE *cfile;

  if (!PyArg_ParseTuple(args, "O:new_patchmaker", &python_file))
	return NULL;
  if (!PyFile_Check(python_file)) {
	PyErr_SetString(PyExc_TypeError, "Need true file object");
	return NULL;
  }
  Py_INCREF(python_file);
  
  pm = PyObject_New(_librsync_PatchMakerObject, &_librsync_PatchMakerType);
  if (pm == NULL) return NULL;
  pm->x_attr = NULL;

  pm->basis_file = python_file;
  cfile = PyFile_AsFile(python_file);
  pm->patch_job = rs_patch_begin(rs_file_copy_cb, cfile);

  return (PyObject*)pm;
}

static void
_librsync_patchmaker_dealloc(PyObject* self)
{
  _librsync_PatchMakerObject *pm = (_librsync_PatchMakerObject *)self;
  Py_DECREF(pm->basis_file);
  rs_job_free(pm->patch_job);
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
  long inbuf_length;
  rs_buffers_t buf;
  rs_result result;

  if (!PyArg_ParseTuple(args, "s#:cycle", &inbuf, &inbuf_length))
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

  return Py_BuildValue("(ils#)", (result == RS_DONE),
					   inbuf_length - (long)buf.avail_in,
					   outbuf, RS_JOB_BLOCKSIZE - (long)buf.avail_out);
}

static PyMethodDef _librsync_patchmaker_methods[] = {
  {"cycle", (PyCFunction)_librsync_patchmaker_cycle, METH_VARARGS},
  {NULL, NULL, 0, NULL}  /* sentinel */
};

static PyObject *
_librsync_patchmaker_getattr(_librsync_PatchMakerObject *pm, char *name)
{
  if (pm->x_attr != NULL) {
	PyObject *v = PyDict_GetItemString(pm->x_attr, name);
	if (v != NULL) {
	  Py_INCREF(v);
	  return v;
	}
  }
  return Py_FindMethod(_librsync_patchmaker_methods, (PyObject *)pm, name);
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
  PyObject_HEAD_INIT(NULL)
  0,
  "patchmaker",
  sizeof(_librsync_PatchMakerObject),
  0,
  _librsync_patchmaker_dealloc, /*tp_dealloc*/
  0,          /*tp_print*/
  (getattrfunc)_librsync_patchmaker_getattr, /*tp_getattr*/
  (setattrfunc)_librsync_patchmaker_setattr, /*tp_setattr*/
  0,          /*tp_compare*/
  0,          /*tp_repr*/
  0,          /*tp_as_number*/
  0,          /*tp_as_sequence*/
  0,          /*tp_as_mapping*/
  0,          /*tp_hash */
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

void init_librsync(void)
{
  PyObject *m, *d;

  _librsync_SigMakerType.ob_type = &PyType_Type;
  _librsync_DeltaMakerType.ob_type = &PyType_Type;
  m = Py_InitModule("_librsync", _librsyncMethods);
  d = PyModule_GetDict(m);
  librsyncError = PyErr_NewException("_librsync.librsyncError", NULL, NULL);
  PyDict_SetItemString(d, "librsyncError", librsyncError);
  PyDict_SetItemString(d, "RS_JOB_BLOCKSIZE",
					   Py_BuildValue("l", (long)RS_JOB_BLOCKSIZE));
  PyDict_SetItemString(d, "RS_DEFAULT_BLOCK_LEN",
					   Py_BuildValue("l", (long)RS_DEFAULT_BLOCK_LEN));
}
