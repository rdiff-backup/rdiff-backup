/*=                                     -*- c-file-style: "bsd" -*-
 * rproxy -- dynamic caching and delta update in HTTP
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
                                         | I think if you've ordered
                                         | somebody to do something
                                         | you should probably resist
                                         | the urge to thank them.
                                         |  -- abc.net.au/thegames/
                                         */

/*
 * TODO: Inhale from a mapptr, rather than doing hard IO because bad
 * things happen if it stops short.
 */

#include "includes.h"
#include "command.h"
#include "protocol.h"
#include "prototab.h"
#include "mapptr.h"
#include "inhale.h"

#ifndef __LCLINT__
/* On Linux/glibc this file contains constructs that confuse lclint. */
#  include <netinet/in.h>		/* ntohs, etc */
#endif /* __LCLINT__ */


/* For debugging porpoises, here are some human-readable forms. */
struct hs_op_kind_name const _hs_op_kind_names[] = {
    {"EOF",       op_kind_eof },
    {"COPY",      op_kind_copy },
    {"LITERAL",   op_kind_literal },
    {"SIGNATURE", op_kind_signature },
    {"CHECKSUM",  op_kind_checksum },
    {"INVALID",   op_kind_invalid },
    {NULL,        0 }
};


/*
 * Return a human-readable name for KIND.
 */
char const *
_hs_op_kind_name(hs_op_kind_t kind)
{
    const struct hs_op_kind_name *k;

    for (k = _hs_op_kind_names; k->kind; k++) {
        if (k->kind == kind) {
            return k->name;
        }
    }

    return NULL;
}


int
_hs_read_varint(byte_t const *p, int len)
{
    switch (len) {
    case 1:
        return *p;
    case 2:
        return ntohs(* (uint16_t const *) p);
    case 4:
        return ntohl(* (uint32_t const *) p);
    default:
        _hs_fatal("don't know how to read integer of length %d", len);
        return 0;               /* UNREACHABLE */
    }
}


/*
 * Extract parameters from a command starting in memory at P,
 * and with format described by ENT.
 */
static void
_hs_parse_command(byte_t const *p,
                  hs_prototab_ent_t const *ent,
                  int *param1, int *param2)
{
    p++;                        /* skip command byte */

    *param1 = _hs_read_varint(p, ent->len_1);
    p += ent->len_1;

    if (ent->len_2) {
        *param2 = _hs_read_varint(p, ent->len_2);
    }
}


/*
 * Try to map LEN bytes.  If we succeed, *P points to the data and
 * LEN is the amount mapped.
 *
 * If there is not enough data yet, or if we hit EOF, or if something
 * breaks, then return HS_FAILED or HS_AGAIN
 */
static hs_result_t
_hs_inhale_map_cmd(hs_map_t *map, off_t input_pos, byte_t const **p,
                   size_t *len)
{
    size_t require_len;
    int reached_eof;

    require_len = *len;
    *p = hs_map_ptr(map, input_pos, len, &reached_eof);

    if (!*p) {
        _hs_error("couldn't map command byte");
        return HS_FAILED;
    } else if (*len < require_len && reached_eof) {
        /* This is a warning condition, because we shouldn't just run
         * off the end of the file; instead we should get an EOF
         * command and stop smoothly. */
        _hs_error("reached eof when trying to read command byte");
        return HS_FAILED;
    } else if (*len < require_len) {
        /* Perhaps we just couldn't get enough data this time? */
        _hs_trace("only mapped %d bytes towards a command header, require %d",
                  *len, require_len);
        return HS_AGAIN;
    }

    return HS_DONE;
}


/*
 * Read a command from MAP, containing a token sequence.  The input
 * cursor is currently at *INPUT_POS, which is updated to reflect the
 * amount of data read.
 *
 * KIND identifies the kind of command, and if applicable LEN and OFF
 * describe the parameters to the command.
 *
 * If the input routine indicates that it would block, then we return
 * without updating the file cursor.  Then when we come back later, we
 * can try and map at the same position.  We know that that data will
 * still be available, so we can re-read the whole command.
 * Rescanning it is slightly redundant, but easier than worrying about
 * finding a place to explicitly store the state.
 *
 * We first try to map at least one byte, being the command byte.
 * This tells us how many bytes will be required for the command and
 * its parameters, so if necessary we then try to map that many bytes.
 * Then we have the whole command and can interpret it.
 *
 * Returns HS_DONE, HS_AGAIN or HS_FAILED.
 */
hs_result_t
_hs_inhale_command_map(hs_map_t *map, off_t *input_pos,
                       hs_op_kind_t *kind,
                       int *param1, int *param2)
{
    const byte_t *cmd;
    hs_result_t result;
    const hs_prototab_ent_t *ent;
    size_t len;

    /* First, map at least one byte to find the command type. */
    len = 1;
    result = _hs_inhale_map_cmd(map, *input_pos, &cmd, &len);
    if (result != HS_DONE)
        return result;

    /* Now find out what this command means */
    ent = &_hs_prototab[*cmd];
    *kind = ent->kind;

    _hs_trace("inhaled initial byte %#04x, kind=%s, total length will be %d",
              *cmd, _hs_op_kind_name(*kind), ent->total_size);

    if (ent->total_size == 1) {
        /* this is an immediate-parameter command byte: really easy */
        *param1 = ent->immediate;
        *input_pos += 1;
        return HS_DONE;
    }

    if (len < ent->total_size) {
        /* read in enough input data to cover all the parameters */
        len = ent->total_size;
        result = _hs_inhale_map_cmd(map, *input_pos, &cmd, &len);
        if (result != HS_DONE)
            return result;
    }

    /* otherwise, we have to make sure we map the whole command header
     * now that we know the length */
    _hs_parse_command(cmd, ent, param1, param2);
    *input_pos += ent->total_size;

    /* Now we know we have at least one command byte */
    return HS_DONE;
}

