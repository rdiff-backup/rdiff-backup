/* -*- mode: c; c-file-style: "gnu" -*-  */

/* libhsync
   Copyright (C) 2000 by Martin Pool <mbp@humbug.org.au>

   This program is free software; you can redistribute it and/or modify
   it under the terms of the GNU General Public License as published by
   the Free Software Foundation; either version 2 of the License, or
   (at your option) any later version.
   
   This program is distributed in the hope that it will be useful,
   but WITHOUT ANY WARRANTY; without even the implied warranty of
   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
   GNU General Public License for more details.
   
   You should have received a copy of the GNU General Public License
   along with this program; if not, write to the Free Software
   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307
   USA
*/

/* ========================================

   Callback function prototypes */
typedef int (*rs_read_fn_t)(void *readprivate, char *buf, size_t len);

typedef int (*rs_readofs_fn_t)(void *readprivate, char *buf,
			       size_t len, off_t offset);

typedef int (*rs_write_fn_t)(void *writeprivate, char const *buf,
			     size_t len);

extern char const * hs_log_domain;


/* ========================================

   Decode */

typedef struct hs_stats {
  int lit_cmds, lit_bytes;
  int copy_cmds, copy_bytes;
  int sig_cmds, sig_bytes;
} hs_stats_t;

ssize_t
hs_decode (rs_readofs_fn_t oldread_fn, void *oldread_priv,
	   rs_write_fn_t write_fn, void *write_priv,
	   rs_read_fn_t ltread_fn, void *ltread_priv,
	   rs_write_fn_t newsig_fn, void *newsig_priv,
	   hs_stats_t * stats);




/* ========================================

   Encode */


ssize_t
hs_encode (rs_read_fn_t read_fn, void *readprivate,
	   rs_write_fn_t write_fn, void *write_priv,
	   rs_read_fn_t sigread_fn, void *sigreadprivate,
	   hs_stats_t *stats);

/* ========================================

   File buffers
*/

/* FILE* IO buffers */
struct file_buf;


/* This is the preferred name for new code: */
typedef struct file_buf hs_filebuf_t;

ssize_t hs_filebuf_read (void *private, char *buf, size_t len);
ssize_t hs_filebuf_zread (void *private, char *buf, size_t len);
ssize_t hs_filebuf_write (void *private, char const *buf, size_t len);
ssize_t hs_filebuf_zwrite (void *private, char const *buf, size_t len);
ssize_t hs_filebuf_read_ofs (void *private, char *buf, size_t len,
				   off_t ofs);

hs_filebuf_t *
hs_filebuf_open (char const *filename, char const *mode);

hs_filebuf_t *
hs_filebuf_from_file (FILE * fp);



/* ========================================

   Memory buffers
*/

typedef struct hs_membuf hs_membuf_t;

off_t hs_membuf_tell (void *private);
ssize_t hs_membuf_write(void *private, char const *buf, size_t len);
ssize_t hs_membuf_read(void *private, char *buf, size_t len);
ssize_t hs_membuf_read_ofs (void *private, char *buf, size_t len, off_t ofs);
ssize_t hs_choose_block_size(ssize_t file_len);

hs_membuf_t *hs_membuf_new (void);

void hs_membuf_truncate (hs_membuf_t *mb);
