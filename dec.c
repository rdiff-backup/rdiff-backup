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
#include "inhale.h"
#include "protocol.h"

static int
_hs_copy(const uint32_t length,
         hs_read_fn_t read_fn, void *read_priv,
         hs_write_fn_t write_fn, void *write_priv, hs_mdfour_t * newsum)
{
    ssize_t         ret;
    byte_t  *buf;

    buf = malloc(length);
    if (!buf)
        goto fail;

    ret = _hs_read_loop(read_fn, read_priv, buf, length);
    if (ret >= 0 && (ret < (int32_t) length)) {
        errno = ENODATA;
        goto fail;
    }

    if (newsum)
        hs_mdfour_update(newsum, buf, ret);

    ret = _hs_write_loop(write_fn, write_priv, buf, ret);
    if ((unsigned) ret != length)
        goto fail;

    free(buf);
    return length;

  fail:
    if (buf)
        free(buf);
    return -1;
}



static int
_hs_check_gd_header(hs_read_fn_t ltread_fn, void *ltread_priv)
{
    int             ret;
    uint32_t        remote_magic, expect;

    expect = HS_LT_MAGIC;

    ret = _hs_read_netint(ltread_fn, ltread_priv, &remote_magic);
    assert(ret == 4);
    if (remote_magic != expect) {
        _hs_fatal("version mismatch: %#010x != %#010x", remote_magic, expect);
        errno = EBADMSG;
        return -1;
    }
    _hs_trace("got version %#010x", remote_magic);
    return 0;
}


static int
_hs_check_filesum(hs_read_fn_t ltread_fn, void *ltread_priv,
                   int length, hs_mdfour_t * newsum)
{
    byte_t           *buf;
    int             ret;
    byte_t            actual_result[MD4_LENGTH];

    assert(length == MD4_LENGTH);
    buf = malloc(length);
    assert(buf);

    ret = _hs_read_loop(ltread_fn, ltread_priv, buf, length);
    assert(ret == length);

    hs_mdfour_result(newsum, actual_result);

    assert(memcmp(actual_result, buf, MD4_LENGTH) == 0);
    _hs_trace("file checksum matches");
    free(buf);

    return 1;
}


static int
_hs_dec_copy(uint32_t offset, uint32_t length, hs_map_t *old_map,
             hs_write_fn_t write_fn, void *write_priv, hs_mdfour_t * newsum)
{
    int             ret;
    byte_t const            *buf;
    int             at_eof;
    size_t          mapped_len;

    if (length > INT32_MAX) {
        _hs_fatal("length %u is too big", length);
        return -1;
    }

    mapped_len = length;
    buf = hs_map_ptr(old_map, offset, &mapped_len, &at_eof);

    if (buf == 0) {
        _hs_error("error in read callback: off=%d, len=%d", offset, length);
        goto fail;
    } else if (mapped_len < length) {
        _hs_error("short read: off=%d, len=%d, result=%d",
                  offset, length, mapped_len);
        errno = ENODATA;
        goto fail;
    }

    if (newsum)
        hs_mdfour_update(newsum, buf, length);

    ret = _hs_write_loop(write_fn, write_priv, buf, length);
    if (ret != (int) length) {
        _hs_error("error in write callback: off=%d, len=%d", offset, length);
        goto fail;
    }

    return length;

  fail:
    return -1;
}


ssize_t
hs_decode(int oldread_fd,
          hs_write_fn_t write_fn, void *write_priv,
          hs_read_fn_t ltread_fn, void *ltread_priv,
          hs_write_fn_t newsig_fn, void *newsig_priv, hs_stats_t * stats)
{
    int             ret;
    uint32_t        length, offset;
    int             kind;
    hs_mdfour_t     newsum;
    hs_map_t       *old_map;
    char                stats_str[256];

    _hs_trace("**** begin");
    hs_bzero(stats, sizeof *stats);
    if (_hs_check_gd_header(ltread_fn, ltread_priv) < 0)
        return -1;

    stats->op = "decode";
    stats->algorithm = "decode";

    old_map = hs_map_file(oldread_fd);

    hs_mdfour_begin(&newsum);

    /* TODO: Rewrite this to use map_ptr on the littok stream.  This
     * is not such a priority as the encoding algorithm, but it would
     * still be nice and would improve efficiency, I think. */

    while (1) {
        ret = _hs_inhale_command(ltread_fn, ltread_priv, &kind, &length,
                                 &offset);
        if (ret < 0) {
            _hs_error("error while trying to read command byte");
            goto out;
        }

        if (kind == op_kind_eof) {
            _hs_trace("EOF");
            break;              /* We're done! Cool bananas */
        } else if (kind == op_kind_literal) {
            _hs_trace("LITERAL(len=%d)", length);
            ret = _hs_copy(length, ltread_fn, ltread_priv, write_fn,
                           write_priv, &newsum);
            if (ret < 0)
                goto out;
            stats->lit_cmds++;
            stats->lit_bytes += length;
        } else if (kind == op_kind_signature) {
            _hs_trace("SIGNATURE(len=%d)", length);
            ret = _hs_copy(length,
                           ltread_fn, ltread_priv,
                           newsig_fn, newsig_priv, NULL);
            if (ret < 0)
                goto out;
            stats->sig_cmds++;
            stats->sig_bytes += length;
        } else if (kind == op_kind_copy) {
            _hs_trace("COPY(offset=%d, len=%d)", offset, length);
            ret = _hs_dec_copy(offset, length, old_map,
                               write_fn, write_priv, &newsum);
            if (ret < 0)
                goto out;
            stats->copy_cmds++;
            stats->copy_bytes += length;
        } else if (kind == op_kind_checksum) {
            _hs_trace("CHECKSUM(len=%d)", length);
            ret = _hs_check_filesum(ltread_fn, ltread_priv, length, &newsum);
            if (ret < 0)
                goto out;
        } else {
            _hs_fatal("unexpected op kind %d!", kind);
            ret = -1;
            goto out;
        }
    }

    if (ret >= 0) {
        hs_format_stats(stats, stats_str, sizeof stats_str);
        _hs_trace("completed: %s", stats_str);
    }

 out:
    _hs_unmap_file(old_map);

    return 1;
}
