/*                                      -*- c-file-style: "bsd" -*-
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
                                         | `Try to look guileless'
                                         */


/* hsmapread -- extract sections of files, as a test case for
 * mapptr. */


/* The intention is that this program will completely exercise the hs_map_ptr 
   read interface.  The results are such that they can be easily compared to
   sections extracted from the file using for example dd. */

#include "includes.h"

#include <unistd.h>
#include <fcntl.h>
#include <stdio.h>
#include <sys/file.h>
#include <string.h>

#include "mapptr.h"

/* The `walker' algorithm is not released yet. */
#undef USE_WALKER

enum mapread_options
{
    keep_trying = 1,
    nonblocking = 2,
    use_select = 4,
    walker = 8,
    use_map_copy = 16
};

static void
usage(void)
{
    printf("Usage: hsmapread [OPTIONS] OFFSET,SIZE ...\n"
           "Reads sections from a file or socket on standard input\n"
           "and writes to standard output.\n"
           "\n"
           "  -k             keep trying to map whole blocks\n"
           "  -n             read in nonblocking mode\n"
           "  -s             use select(2)\n"
#ifdef USE_WALKER
           "  -w             use walker algorithm\n"
#endif
           "  -D             turn on trace, if enabled in library\n"
           "  -c             use _hs_map_copy\n"
           "\n"
           "Note that -n without -s will busy-wait.\n"
           "Ranges may be given either as a series of parameters, or separated\n"
           "by colons.\n"
           "For example: 0,5:5,5:10,100000\n"
        );
}



/* Block until FD is ready to supply data. */
static int
select_for_read(int fd)
{
    fd_set          read_set;
    int             ret;

    _hs_trace("select fd%d for read...", fd);
    
    FD_ZERO(&read_set);
    FD_SET(fd, &read_set);

    do {
        ret = select(1, &read_set, NULL, NULL, NULL);
        if (ret < 0) {
            _hs_error("error in select: %s", strerror(errno));
            return -1;
        }
    } while (ret == 0  ||  (ret == -1  &&  errno == EINTR));

    assert(ret == 1);

    return 1;
}


static int
copy_one_chunk(int from_fd, hs_map_t * map, off_t off, size_t want_len,
               int options)
{
    byte_t const   *p;
    size_t          len;
    int             written;
    int             saw_eof;
    size_t          out_pos = 0;

  try_read:
    len = want_len;
#ifdef USE_WALKER
    if (options & walker)
        p = _hs_map_walk(map, (off_t) off, &len, &saw_eof);
    else
#endif
        p = hs_map_ptr(map, (off_t) off, &len, &saw_eof);

    assert((long) len >= 0);

    if (!p) {
        _hs_error("hs_map_ptr failed!\n");
        return 2;
    }
    _hs_trace("got back %ld bytes, wanted %ld, "
              "at eof=%s",
              (long) len, (long) want_len, saw_eof ? "true" : "false");

    if (len < want_len && (options & keep_trying) && !saw_eof) {
        _hs_trace("keep trying");
        if (options & use_select) {
            if (select_for_read(from_fd) < 0)
                return 2;
        }

        goto try_read;
    }

    /* mapread may have opportunistically given us more bytes than * we
     * wanted.  In this case, it would be really bad to write * them out,
     * because they're not expected.  It's harmless to * ignore them. */
    if (len > want_len)
        len = want_len;

    _hs_trace("write %ld bytes at output position %ld",
              (long) len, (long) out_pos);
    written = write(STDOUT_FILENO, p, len);
    if (written < 0) {
        _hs_error("error writing out chunk: %s\n", strerror(errno));
        return 3;
    }

    out_pos += len;
    if ((size_t) written != len) {
        _hs_error("expected to write %d bytes, actually wrote %d\n",
                  len, written);
        return 4;
    }

    return 0;
}


/*
 * Copy the chunks specified by the command strings in ARGV from MAP
 * onto the file FD, obeying OPTIONS.
 */
static int
read_chunks(int from_fd, hs_map_t * map, int argc, char **argv, const int options)
{
    off_t                   off;
    size_t                  want_len;
    int                     rc;
    char                   *o;
    hs_filebuf_t           *out_fb = NULL;

    if (options & use_map_copy) {
        out_fb = hs_filebuf_from_fd(STDOUT_FILENO);
    }

    for (; argc > 0; argc--, argv++) {
        o = *argv;
        do {
            off = strtoul(o, &o, 10);
            if (*o != ',')
                goto failed;
            want_len = strtoul(o + 1, &o, 10);
            if (!(*o == '\0' || *o == ':'))
                goto failed;
            if (options & use_map_copy) {
                rc = _hs_map_copy(map, want_len, &off,
                                  hs_filebuf_write, out_fb, NULL);
                if (rc != HS_DONE)
                    _hs_fatal("map_copy didn't!");
            } else { 
                if ((rc = copy_one_chunk(from_fd, map, off, want_len, options)))
                    return rc;
            }
        } while (*o++ == ':');
    }

    return 0;

  failed:
    _hs_error("argument `%s' doesn't look like an OFFSET,LENGTH "
              "tuple\n", *argv);
    return 1;
}


/*
 * If the user specified they wanted nonblocking input, then set that
 * flag on stdin.
 */
static int
set_nonblock_flag(int desc, int options)
{
    int oldflags = fcntl (desc, F_GETFL, 0);
    /* If reading the flags failed, return error indication now. */
    if (oldflags == -1)
        return -1;
    /* Set just the flag we want to set. */
    if (options & nonblocking)
        oldflags |= O_NONBLOCK;
    else
        oldflags &= ~O_NONBLOCK;
    /* Store modified flag word in the descriptor. */
    return fcntl (desc, F_SETFL, oldflags);
}


static int
chew_options(int argc, char **argv, int *options) 
{
    int             c;

    while ((c = getopt(argc, argv, "cknswD")) != -1)
    {
        switch (c)
        {
        case '?':
        case ':':
            return -1;
        case 'c':
            *options |= use_map_copy;
            break;
        case 'k':
            *options |= keep_trying;
            break;
        case 'n':
            *options |= nonblocking;
            break;
        case 's':
            *options |= use_select;
            break;
#ifdef USE_WALKER
        case 'w':
            *options |= walker;
            break;
#endif
        case 'D':
            if (!hs_supports_trace()) {
                _hs_error("library does not support trace");
            }
            hs_trace_set_level(LOG_DEBUG);
            break;
        }
    }

    return optind;
}


int
main(int argc, char **argv)
{
    hs_map_t       *map;
    int             ret;
    int             infd = STDIN_FILENO;
    int             ind;
    int             options = 0;

    ind = chew_options(argc, argv, &options);
    if (ind < 0)
        return 1;
    argc -= ind;
    argv += ind;                /* skip options */

    if (argc < 1) {
        usage();
        return 0;
    }

    if ((ret = set_nonblock_flag(infd, options)) != 0)
        return ret;

    map = hs_map_file(infd);

    ret = read_chunks(infd, map, argc, argv, options);

    _hs_unmap_file(map);
    close(infd);

    return ret;
}
