/*= -*- c-basic-offset: 4; indent-tabs-mode: nil; -*-
 *
 * librsync -- the library for network deltas
 * $Id$
 * 
 * Copyright (C) 2001 by Martin Pool <mbp@sourcefrog.net>
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

#define HAVE_UINT64 1 /* assume success, but might be undefined below */

#if defined(HAVE_STDINT_H)
#  include <stdint.h>
#else
# if SIZEOF_UNSIGNED_INT == 4
#  define uint32_t unsigned int
# elif SIZEOF_UNSIGNED_LONG == 4
#  define uint32_t unsigned long
# elif SIZEOF_UNSIGNED_SHORT == 4
#  define uint32_t unsigned short
# else
#  error "can't find an appropriate 32-bit integer type"
# endif
# if SIZEOF_UNSIGNED_INT == 8
#  define uint64_t unsigned int
# elif SIZEOF_UNSIGNED_LONG == 8
#  define uint64_t unsigned long
# elif SIZEOF_UNSIGNED_SHORT == 8
#  define uint64_t unsigned short
# elif SIZEOF_LONG_LONG == 8
#  define uint64_t unsigned long long
# else
#  undef HAVE_UINT64
# endif
#endif
