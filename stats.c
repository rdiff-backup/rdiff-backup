/*= -*- c-basic-offset: 4; indent-tabs-mode: nil; -*-
 *
 * $Id$
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


#include <config.h>

#include <assert.h>
#include <stdlib.h>
#include <stdio.h>
#include <unistd.h>
#include <sys/file.h>
#include <string.h>

#include "rsync.h"
#include "trace.h"

/*
 * TODO: Other things to show in statistics:
 *
 * Number of input and output bytes.
 *
 * Number of times we blocked waiting for input or output.
 *
 * Number of blocks.
 */

int
rs_log_stats(rs_stats_t const *stats)
{
    char buf[1000];

    rs_format_stats(stats, buf, sizeof buf - 1);
    rs_log(RS_LOG_INFO|RS_LOG_NONAME, "%s", buf);
    return 0;
}



/**
 * \brief Return a human-readable representation of statistics.
 *
 * The string is truncated if it does not fit.  100 characters should
 * be sufficient space.
 *
 * \param stats Statistics from an encoding or decoding operation.
 *
 * \param buf Buffer to receive result.
 * \param size Size of buffer.
 * \return buf
 */
char *
rs_format_stats(rs_stats_t const * stats,
		char *buf, size_t size)
{
    char const *op = stats->op;
    int len;

    if (!op)
        op = "noop";
    
    len = snprintf(buf, size, "%s statistics: ", op);

    if (stats->lit_cmds) {
        len += snprintf(buf+len, size-len,
                        "literal[%d cmds, %.0f bytes, %.0f cmdbytes] ",
                        stats->lit_cmds,
                        (double) stats->lit_bytes,
                        (double) stats->lit_cmdbytes);
    }

    if (stats->sig_cmds) {
        len += snprintf(buf+len, size-len,
                        "in-place-signature[%.0f cmds, %.0f bytes] ",
                        (double) stats->sig_cmds,
                        (double) stats->sig_bytes);
    }

    if (stats->copy_cmds || stats->false_matches) {
        len += snprintf(buf+len, size-len, 
                        "copy[%.0f cmds, %.0f bytes, %.0f false, %.0f cmdbytes]",
                        (double) stats->copy_cmds,
                        (double) stats->copy_bytes,
                        (double) stats->false_matches,
                        (double) stats->copy_cmdbytes);
    }
        

    if (stats->sig_blocks) {
        len  += snprintf(buf+len, size-len,
                         "signature[%.0f blocks, %.0f bytes per block]",
                         (double) stats->sig_blocks,
                         (double) stats->block_len);
    }
    
    return buf;
}
