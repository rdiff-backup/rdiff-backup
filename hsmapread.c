/* -*- mode: c; c-file-style: "bsd" -*- */
/* -------------------------------------------------------------------

   $Id$

   hsmapread -- test harness for hs_map_ptr

   Copyright (C) 2000 by Martin Pool

   This program is free software; you can redistribute it and/or modify it
   under the terms of the GNU General Public License as published by the Free 
   Software Foundation; either version 2 of the License, or (at your option)
   any later version.

   This program is distributed in the hope that it will be useful, but
   WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY 
   or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License
   for more details.

   You should have received a copy of the GNU General Public License along
   with this program; if not, write to the Free Software Foundation, Inc.,
   675 Mass Ave, Cambridge, MA 02139, USA.

   ------------------------------------------------------------------- */


/* The intention is that this program will completely exercise the hs_map_ptr 
   read interface.  The results are such that they can be easily compared to
   sections extracted from the file using for example dd. */

#include "includes.h"

static void
usage(void)
{
    printf("Usage: hsmapread [OPTIONS] FILENAME OFFSET,SIZE ...\n"
	   "Reads sections from a file and writes to standard output.\n"
	   "A filename of `-' means standard input.\n"
	   "\n"
	   "  -k             keep trying to map whole blocks\n"
	   "  -n             read in nonblocking mode\n"
	   "  -s             use select(2)\n"
	   "\n"
	   "Note that -n without -s will busy-wait.\n"
	);
}



/* Block until FD is ready to supply data. */
static int
select_for_read(int fd)
{
    fd_set          read_set;
    int             ret;

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


/* argv, argc refer to the offset, size counts */
static int
read_chunks(int fd,
	    hs_map_t * map, int argc, char **argv,
	    int use_select, int keep_trying)
{
    char const     *p;
    int             off, len;
    int             want_len;
    int             written;
    int             saw_eof;

    for (; argc > 0; argc--, argv++) {
	/* fprintf(stderr, "chunk %s\n", *argv); */

	if (sscanf(*argv, "%d,%d", &off, &want_len) != 2) {
	    _hs_error("error interpreting argument `%s'\n", *argv);
	    return 1;
	}


    try_read:
	len = want_len;
	p = _hs_map_ptr(map, (hs_off_t) off, &len, &saw_eof);
	if (!p) {
	    _hs_error("hs_map_ptr failed: %s\n", strerror(errno));
	    return 2;
	}
	_hs_trace("got back %ld bytes, wanted %ld, keep_trying=%s, "
		  "at eof=%s",
		  (long) len,
		  (long) want_len,
		  keep_trying ? "true" : "false",
		  saw_eof ? "true" : "false");
	
	if (len < want_len && keep_trying && !saw_eof) {
	    if (use_select) {
		if (select_for_read(fd) < 0)
		    return 2;
	    }
	
	    goto try_read;
	}

	written = write(STDOUT_FILENO, p, len);
	if (written < 0) {
	    _hs_error("error writing out chunk: %s\n", strerror(errno));
	    return 3;
	}

	if (written != len) {
	    _hs_error("expected to write %d bytes, actually wrote %d\n",
		      len, written);
	    return 4;
	}
    }

    return 0;
}


static int
open_source(char const *filename, int *fd, int nonblocking)
{
    int             flags = O_RDONLY;

    if (nonblocking)
	flags |= O_NONBLOCK;

    if (strcmp(filename, "-")) {
	*fd = open(filename, flags);
	if (*fd < 0) {
	    _hs_fatal("can't open %s: %s", filename, strerror(errno));
	    return 1;
	}
    } else {
	*fd = STDIN_FILENO;
    }

    return 0;
}


int
chew_options(int argc, char **argv, int *nonblocking,
	     int *use_select, int *keep_trying)
{
    int             c;

    while ((c = getopt(argc, argv, "kns")) != -1) {
	switch (c) {
	case '?':
	case ':':
	    return -1;
	case 'k':
	    *keep_trying = 1;
	    break;
	case 'n':
	    *nonblocking = 1;
	    break;
	case 's':
	    *use_select = 1;
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
    int             infd;
    int             ind;
    int             nonblocking = 0;
    int             use_select = 0;
    int             keep_trying = 0;

    ind = chew_options(argc, argv, &nonblocking, &use_select, &keep_trying);
    if (ind < 0)
	return 1;
    argc -= ind;
    argv += ind;		/* skip options */

    if (argc < 2) {
	usage();
	return 0;
    }

    if ((ret = open_source(argv[0], &infd, nonblocking)) != 0)
	return ret;
    argc--;
    argv++;			/* skip filename */

    map = _hs_map_file(infd);

    ret = read_chunks(infd, map, argc, argv, use_select, keep_trying);

    _hs_unmap_file(map);
    close(infd);

    return ret;
}
