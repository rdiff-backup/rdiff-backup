/*=                    -*- c-basic-offset: 4; indent-tabs-mode: nil; -*-
 *
 * librsync -- library for network deltas
 * 
 * Copyright (C) 2000, 2001 by Martin Pool <mbp@samba.org>
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

/** \file librsync-config.h
 *
 * \brief System-specific configuration for librsync.h.
 */

#ifndef _LIBRSYNC_CONFIG_H
#define _LIBRSYNC_CONFIG_H

/**
 * \brief A long integer type that can handle the largest file
 * offsets.
 *
 * Perhaps this might have to be configured to be 'long long', 'long',
 * or something else depending on the platform.  On WIN32, many config.h's
 * define LONG_LONG as "__int64".
 */
typedef long    rs_long_t;

#endif /* _LIBRSYNC_CONFIG_H */
