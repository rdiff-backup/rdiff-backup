/*=                                     -*- c-file-style: "bsd" -*-
 *
 * $Id$
 *
 * Copyright (C) 2000 by Martin Pool <mbp@humbug.org.au>
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

                                /*
                                 | Let's climb to the TOP of that
                                 | MOUNTAIN and think about STRIP
                                 | MINING!!
                                 */

/*=
 *
 * Here's a diagram of the decoding process:
 *
 *                         /---- OLDBODY <--- BODYCACHE
 *                        v                    ^
 * UPSTREAM -chunked-> LTSTREAM ----> BODY ----+----> CLIENT
 *              \
 *               -> SIGNATURE ---> SIGCACHE
 *
 *
 * As we read input from upstream, we split the chunked encoding into
 * the literal-token stream, and the server-generated signature.  We
 * combine the ltstream with the old body to get the new value of the
 * body.  This is sent downstream, and also written back into the
 * cache.  The signature is extracted and written into the signature
 * cache so that we can send it up in the next request.
 */

/*
 * TODO: Rewrite this to use a mapptr buffer for input from the network.
 *
 * When we're decoding and reading a literal if we get a short read
 * then pass it through anyhow.
 */


#include "includes.h"
#include "command.h"
#include "mapptr.h"
#include "inhale.h"
#include "protocol.h"
#include "vtr.h"


static int
_hs_check_gd_header(hs_map_t *map, off_t *lt_pos)
{
    uint32_t        remote_magic, expect;
    byte_t const    *p;
    size_t map_len = 4;
    int reached_eof;

    expect = HS_LT_MAGIC;

    p = hs_map_ptr(map, *lt_pos, &map_len, &reached_eof);
    assert(p);
    assert(map_len >= 4);

    remote_magic = _hs_read_varint(p, 4);
    if (remote_magic != expect) {
        _hs_fatal("version mismatch: %#010x != %#010x", remote_magic, expect);
        errno = EBADMSG;
        return -1;
    }
    _hs_trace("got version %#010x", remote_magic);

    *lt_pos += 4;
    return 0;
}


static int
_hs_check_filesum_vtr(hs_map_t *map, off_t *pos, size_t length, hs_mdfour_t * newsum)
{
    byte_t const *p;
    byte_t            actual_result[MD4_LENGTH];
    size_t map_len = length;
    int reached_eof;

    p = hs_map_ptr(map, *pos, &map_len, &reached_eof);
    assert(map_len >= length);
    
    hs_mdfour_result(newsum, actual_result);

    assert(length == MD4_LENGTH);
    assert(memcmp(actual_result, p, MD4_LENGTH) == 0);
    _hs_trace("file checksum matches");

    *pos += length;

    return 1;
}


ssize_t
hs_decode_vtr(int oldread_fd, int ltread_fd, 
              hs_write_fn_t write_fn, void *write_priv,
              hs_write_fn_t newsig_fn, void *newsig_priv, hs_stats_t * stats)
{
    int             result;
    int             param1, param2;
    hs_op_kind_t    kind;
    hs_mdfour_t     newsum;
    hs_map_t       *old_map, *lt_map;
    char            stats_str[256];
    off_t           lt_pos = 0;

    _hs_trace("**** begin");
    hs_bzero(stats, sizeof *stats);

    stats->op = "decode";
    stats->algorithm = "decode";

    old_map = hs_map_file(oldread_fd);
    lt_map = hs_map_file(ltread_fd);

    if (_hs_check_gd_header(lt_map, &lt_pos) < 0)
        return -1;
    hs_mdfour_begin(&newsum);

    /* TODO: Rewrite this to use map_ptr on the littok stream.  This
     * is not such a priority as the encoding algorithm, but it would
     * still be nice and would improve efficiency, I think. */

    /* TODO: Change this to a job/callback structure like nad. */

    while (1) {
        result = _hs_inhale_command_map(lt_map, &lt_pos, &kind,
                                     &param1, &param2);
        if (result != HS_DONE) {
            _hs_error("error while trying to read command byte");
            goto out;
        }

        if (kind == op_kind_eof) {
            _hs_trace("EOF");
            break;              /* We're done! Cool bananas */
        } else if (kind == op_kind_literal) {
            _hs_trace("LITERAL(len=%d)", param1);
            result = _hs_map_copy(lt_map, param1, &lt_pos, write_fn, write_priv, &newsum);
            if (result != HS_DONE)
                goto out;
            stats->lit_cmds++;
            stats->lit_bytes += param1;
        } else if (kind == op_kind_signature) {
            _hs_trace("SIGNATURE(len=%d)", param1);
            result = _hs_map_copy(lt_map, param1, &lt_pos, newsig_fn, newsig_priv, NULL);
            if (result != HS_DONE)
                goto out;
            stats->sig_cmds++;
            stats->sig_bytes += param1;
        } else if (kind == op_kind_copy) {
            off_t copy_off = param1;
            
            _hs_trace("COPY(offset=%d, len=%d)", param1, param2);
            result = _hs_map_copy(old_map, param2, &copy_off, 
                                  write_fn, write_priv, &newsum);
            if (result != HS_DONE)
                goto out;
            stats->copy_cmds++;
            stats->copy_bytes += param2;
        } else if (kind == op_kind_checksum) {
            _hs_trace("CHECKSUM(len=%d)", param1);
            result = _hs_check_filesum_vtr(lt_map, &lt_pos, param1, &newsum);
            if (result < 0)
                goto out;
        } else {
            _hs_fatal("unexpected op kind %d!", kind);
            result = -1;
            goto out;
        }
    }

    if (result >= 0) {
        hs_format_stats(stats, stats_str, sizeof stats_str);
        _hs_trace("completed: %s", stats_str);
    }

 out:
    _hs_unmap_file(lt_map);
    _hs_unmap_file(old_map);

    return 1;
}
