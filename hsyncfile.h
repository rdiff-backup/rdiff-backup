/*=                    -*- c-basic-offset: 4; indent-tabs-mode: nil; -*-
 *
 * libhsync -- the library for network deltas
 * $Id$
 * 
 * Copyright (C) 2000, 2001 by Martin Pool <mbp@samba.org>
 * 
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU Lesser General Public License
 * as published by the Free Software Foundation; either version 2.1 of
 * the License, or (at your option) any later version.
 * 
 * This program is distributed in the hope that it will be useful, but
 * WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * Lesser General Public License for more details.
 * 
 * You should have received a copy of the GNU Lesser General Public
 * License along with this program; if not, write to the Free Software
 * Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 */


/*!
 * \file hsyncfile.h
 * \brief High-level file-based interfaces.
 * \author Martin Pool <mbp@samba.org>
 * $Id$
 */


/*!
 * Buffer sizes for file IO.
 *
 * You probably only need to change these in testing.
 */
extern int hs_inbuflen, hs_outbuflen;


/**
 * Calculate the MD4 sum of a file.
 *
 * \param result Binary (not hex) MD4 of the whole contents of the
 * file.
 */
void hs_mdfour_file(FILE *in_file, char *result);

hs_result hs_sig_file(FILE *old_file, FILE *sig_file, size_t, size_t); 

hs_result hs_loadsig_file(FILE *sig_file, hs_signature_t **sumset);

hs_result hs_file_copy_cb(void *arg, size_t *len, void **buf);

hs_result hs_delta_file(hs_signature_t *, FILE *new_file, FILE *delta_file);
