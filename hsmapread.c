/* -*- mode: c; c-file-style: "k&r" -*- */
/*
  hsmapread -- test harness for hs_map_ptr
  
   Copyright (C) 2000 by Martin Pool
   
   This program is free software; you can redistribute it and/or modify
   it under the terms of the GNU General Public License as published by
   the Free Software Foundation; either version 2 of the License, or
   (at your option) any later version.
   
   This program is distributed in the hope that it will be useful,
   but WITHOUT ANY WARRANTY; without even the implied warranty of
   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
   GNU General Public License for more details.
   
   You should have received a copy of the GNU General Public License
   along with this program; if not, write to the Free Software
   Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
*/


/* The intention is that this program will completely exercise the
   hs_map_ptr read interface.  The results are such that they can be
   easily compared to sections extracted from the file using for
   example dd. */

#include "includes.h"
#include "hsync.h"
#include "private.h"

static const char *_rcsid UNUSED = "$Id$";

static void
usage(void)
{
     printf("usage: hsmapread FILENAME OFFSET,SIZE ...\n"
	    "Reads sections from a file and writes to STDOUT.\n"
	  );
}


/* argv, argc refer to the offset, size counts */
static int
read_chunks(hs_map_t *map, int argc, char **argv)
{
     char const *p;
     int off, len;
     int written;
     
     for (; argc > 0; argc--, argv++) {
/*  	  fprintf(stderr, "chunk %s\n", *argv); */

	  if (sscanf(*argv, "%d,%d", &off, &len) != 2) {
	       _hs_error("error interpreting argument `%s'\n", *argv);
	       return 1;
	  }

	  p = hs_map_ptr(map, (hs_off_t) off, len);
	  if (!p) {
	       _hs_error("hs_map_ptr failed: %s\n", strerror(errno));
	       return 2;
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


int
main(int argc, char **argv)
{
     hs_map_t *map;
     int infd, ret;
     struct stat statbuf;
     
     if (argc < 3) {
	  usage();
	  return 0;
     }

     infd = open(argv[1], O_RDONLY);
     if (infd < 0) {
	  _hs_fatal("can't open %s: %s", argv[1], strerror(errno));
	  return 1;
     }

     if (fstat(infd, &statbuf)) {
	  _hs_fatal("can't stat %s: %s", argv[1], strerror(errno));
	  return 1;
     }

     map = hs_map_file(infd, statbuf.st_size);

     ret = read_chunks(map, argc-2, argv+2); /* skip argv[0:1] */
     
     hs_unmap_file(map);
     close(infd);

     return ret;
}
