/* -*- mode: c; c-file-style: "k&r" -*-  */

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


extern char const * const hs_libhsync_version;


/* ========================================

   Callback function prototypes */
typedef int (*hs_read_fn_t) (void *readprivate, char *buf, size_t len);

typedef int (*hs_readofs_fn_t) (void *readprivate, char *buf,
				size_t len, off_t offset);

typedef int (*hs_write_fn_t) (void *writeprivate, char const *buf,
			      size_t len);


typedef void _hs_trace_fn(char const *fmt, va_list);
void hs_trace_to(_hs_trace_fn *);
void _hs_trace_to_stderr(char const *fmt, va_list va);


/* ========================================

   Decode */

typedef struct hs_stats {
     int lit_cmds, lit_bytes;
     int copy_cmds, copy_bytes;
     int sig_cmds, sig_bytes;
     int false_matches;
} hs_stats_t;

ssize_t
hs_decode(hs_readofs_fn_t oldread_fn, void *oldread_priv,
	  hs_write_fn_t write_fn, void *write_priv,
	  hs_read_fn_t ltread_fn, void *ltread_priv,
	  hs_write_fn_t newsig_fn, void *newsig_priv, hs_stats_t * stats);




/* ========================================

   Encode */


ssize_t hs_encode(hs_read_fn_t read_fn, void *readprivate,
	  hs_write_fn_t write_fn, void *write_priv,
	  hs_read_fn_t sigread_fn, void *sigreadprivate,
	  int new_block_len, hs_stats_t * stats);

/* ========================================

   File buffers
*/

/* FILE* IO buffers */
struct file_buf;


/* This is the preferred name for new code: */
typedef struct file_buf hs_filebuf_t;

ssize_t hs_filebuf_read(void *private, char *buf, size_t len);
ssize_t hs_filebuf_zread(void *private, char *buf, size_t len);
ssize_t hs_filebuf_write(void *private, char const *buf, size_t len);
ssize_t hs_filebuf_zwrite(void *private, char const *buf, size_t len);
ssize_t hs_filebuf_read_ofs(void *private, char *buf, size_t len,
			    off_t ofs);

hs_filebuf_t *hs_filebuf_open(char const *filename, char const *mode);
void hs_filebuf_close(hs_filebuf_t *fbuf);
void hs_filebuf_add_cache(hs_filebuf_t *fb, FILE *fp);

hs_filebuf_t *hs_filebuf_from_file(FILE * fp);



/* ========================================

   Memory buffers
*/

typedef struct hs_membuf hs_membuf_t;

off_t hs_membuf_tell(void *private);
ssize_t hs_membuf_write(void *private, char const *buf, size_t len);
ssize_t hs_membuf_read(void *private, char *buf, size_t len);
ssize_t hs_membuf_read_ofs(void *private, char *buf, size_t len,
			   off_t ofs);
ssize_t hs_choose_block_size(ssize_t file_len);
hs_membuf_t *hs_membuf_new(void);
void hs_membuf_free(hs_membuf_t *);
void hs_membuf_truncate(hs_membuf_t * mb);
size_t hs_membuf_getbuf(hs_membuf_t const *mb, char const **buf);
hs_membuf_t *hs_membuf_on_buffer(char *buf, int len);


typedef struct hs_ptrbuf hs_ptrbuf_t;

off_t hs_ptrbuf_tell(void *private);
ssize_t hs_ptrbuf_write(void *private, char const *buf, size_t len);
ssize_t hs_ptrbuf_read(void *private, char *buf, size_t len);
ssize_t hs_ptrbuf_read_ofs(void *private, char *buf, size_t len,
			   off_t ofs);
ssize_t hs_choose_block_size(ssize_t file_len);
hs_ptrbuf_t *hs_ptrbuf_on_buffer(char *buf, int len);
void hs_ptrbuf_truncate(hs_ptrbuf_t * mb);
size_t hs_ptrbuf_getbuf(hs_ptrbuf_t const *mb, char const **buf);
hs_ptrbuf_t *hs_ptrbuf_on_buffer(char *buf, int len);


/* ============================================================

   MD4 hash
*/

struct hs_mdfour {
    uint32_t A, B, C, D;
    uint32_t totalN;
};

void hs_mdfour(unsigned char *out, unsigned char const *in, int n);
void hs_mdfour_begin(struct hs_mdfour *md);
void hs_mdfour_update(struct hs_mdfour *md, unsigned char const *in, int n);
void hs_mdfour_result(struct hs_mdfour *md, unsigned char *out);

void
hs_hexify_buf(char *to_buf, unsigned char const *from_buf, int from_len);


char * hs_format_stats(hs_stats_t const * stats);
