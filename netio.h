/*				       	-*- c-file-style: "bsd" -*-
 * rproxy -- dynamic caching and delta update in HTTP
 * $Id$
 * 
 * Copyright (C) 1999, 2000 by Martin Pool <mbp@humbug.org.au>
 * Copyright (C) 1999 by Andrew Tridgell
 * 
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU Lesser General Public License as published by
 * the Free Software Foundation; either version 2.1 of the License, or
 * (at your option) any later version.
 * 
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU Lesser General Public License for more details.
 * 
 * You should have received a copy of the GNU Lesser General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 */

/* =====================================================================
 * Net IO functions
 * ===================================================================== */

int             _hs_read_loop(hs_read_fn_t, void *readprivate,
			      byte_t *buf, size_t len);

size_t          _hs_write_loop(hs_write_fn_t, void *writeprivate,
			       byte_t const *buf, size_t len);

int             hs_must_write(hs_write_fn_t write_fn, void *write_priv,
			      void const *buf, int len);
int            _hs_must_read(hs_read_fn_t, void *, byte_t *, ssize_t);

int             _hs_read_netint(hs_read_fn_t read_fn, void *read_priv,
				/* @out@ */ uint32_t * result);

int             _hs_read_netshort(hs_read_fn_t read_fn, void *read_priv,
				  /* @out@ */ uint16_t * result);


int             _hs_read_netbyte(hs_read_fn_t read_fn, void *read_priv,
				 /* @out@ */ uint8_t * result);

int             _hs_write_netint(hs_write_fn_t write_fn, void *write_priv,
				 uint32_t out);

int             _hs_write_netshort(hs_write_fn_t write_fn, void *write_priv,
				   uint16_t out);

int             _hs_write_netbyte(hs_write_fn_t write_fn, void *write_priv,
				  uint8_t out);

int             _hs_write_netvar(hs_write_fn_t write_fn, void *write_priv,
				 uint32_t value, int type);
