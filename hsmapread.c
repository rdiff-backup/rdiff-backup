/* -*- mode: c; c-file-style: "stroustrup" -*- */
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
     int saw_eof;
     
     for (; argc > 0; argc--, argv++) {
/*  	  fprintf(stderr, "chunk %s\n", *argv); */

	  if (sscanf(*argv, "%d,%d", &off, &len) != 2) {
	       _hs_error("error interpreting argument `%s'\n", *argv);
	       return 1;
	  }

	  p = _hs_map_ptr(map, (hs_off_t) off, &len, &saw_eof);
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


static int
open_source(char const *filename, int *fd, size_t *file_len)
{
#if 0
     struct stat statbuf;
#endif

     if (strcmp(filename, "-")) {
	 *fd = open(filename, O_RDONLY);
	 if (*fd < 0) {
	     _hs_fatal("can't open %s: %s", filename, strerror(errno));
	     return 1;
	 }
     } else {
	 *fd = STDIN_FILENO;
     }

#if 0
     if (fstat(*fd, &statbuf)) {
	  _hs_fatal("can't stat %s: %s", filename, strerror(errno));
	  return 1;
     }
     *file_len = statbuf.st_size;
#else /* true */
     *file_len = (off_t) 0x7fffffff;
#endif /* ! 0 */

     return 0;
}



int
main(int argc, char **argv)
{
     hs_map_t *map;
     int ret;
     size_t      file_len;
     int	 infd;

     if (argc < 3) {
	  usage();
	  return 0;
     }

     if ((ret = open_source(argv[1], &infd, &file_len)) != 0)
	 return ret;

     map = hs_map_file(infd, file_len);

     ret = read_chunks(map, argc-2, argv+2); /* skip argv[0:1] */
     
     hs_unmap_file(map);
     close(infd);

     return ret;
}
