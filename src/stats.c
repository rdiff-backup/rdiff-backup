/*= -*- c-basic-offset: 4; indent-tabs-mode: nil; -*-
 *
 * Copyright (C) 2000, 2001 by Martin Pool <mbp@sourcefrog.net>
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

/** \file stats.c stats reporting functions.
 *
 * \todo Other things to show in statistics: number of input and output bytes,
 * number of times we blocked waiting for input or output, number of blocks. */

#include "config.h"

#include <stdlib.h>
#include <stdio.h>
#ifdef HAVE_UNISTD_H
#  include <unistd.h>
#endif
#ifdef HAVE_SYS_FILE_H
#  include <sys/file.h>
#endif
#include <string.h>

#include "librsync.h"
#include "trace.h"

int rs_log_stats(rs_stats_t const *stats)
{
    char buf[1000];

    rs_format_stats(stats, buf, sizeof buf - 1);
    rs_log(RS_LOG_INFO | RS_LOG_NONAME, "%s", buf);
    return 0;
}

char *rs_format_stats(rs_stats_t const *stats, char *buf, size_t size)
{
    char const *op = stats->op;
    int len, sec;
    double mbps_in, mbps_out;

    if (!op)
        op = "noop";

    len = snprintf(buf, size, "%s statistics: ", op);

    if (stats->lit_cmds) {
        len +=
            snprintf(buf + len, size - len,
                     "literal[%d cmds, " FMT_LONG " bytes, " FMT_LONG
                     " cmdbytes] ", stats->lit_cmds, stats->lit_bytes,
                     stats->lit_cmdbytes);
    }

    if (stats->sig_cmds) {
        len +=
            snprintf(buf + len, size - len,
                     "in-place-signature[" FMT_LONG " cmds, " FMT_LONG
                     " bytes] ", stats->sig_cmds, stats->sig_bytes);
    }

    if (stats->copy_cmds || stats->false_matches) {
        len +=
            snprintf(buf + len, size - len,
                     "copy[" FMT_LONG " cmds, " FMT_LONG " bytes, " FMT_LONG
                     " cmdbytes, %d false]", stats->copy_cmds,
                     stats->copy_bytes, stats->copy_cmdbytes,
                     stats->false_matches);
    }

    if (stats->sig_blocks) {
        len +=
            snprintf(buf + len, size - len,
                     "signature[" FMT_LONG " blocks, " FMT_SIZE
                     " bytes per block]", stats->sig_blocks, stats->block_len);
    }

    sec = (stats->end - stats->start);
    if (sec == 0)
        sec = 1;                // avoid division by zero
    mbps_in = stats->in_bytes / 1e6 / sec;
    mbps_out = stats->out_bytes / 1e6 / sec;
    len +=
        snprintf(buf + len, size - len,
                 " speed[%.1f MB (%.1f MB/s) in, %.1f MB (%.1f MB/s) out, %d sec]",
                 (stats->in_bytes / 1e6), mbps_in, (stats->out_bytes / 1e6),
                 mbps_out, sec);

    return buf;
}
