/* -*- mode: c; c-file-style: "bsd" -*-
 * $Id$
 *
 * hsencode.c -- Command-line tool to generate combined encoded form 
   
   Copyright (C) 2000 by Martin Pool.

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
   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA */


#include "includes.h"

static void usage(char *progname)
{
     fprintf(stderr, "Usage: %s NEWFILE [LT_FILE [SIG_FILE [NEW_BLOCK_LEN]]]\n"
	     "\n"
	     "Compute differences between NEWFILE and the signature SIG_FILE\n"
	     "(default stdin), and write a literal/token/signature description \n"
	     "of them to LT_FILE (default stdout).\n", progname);
     exit(1);
}


int main(int argc, char *argv[])
{
     int ret;
     hs_filebuf_t *ltfb = 0, *sigfb = 0, *newfb = 0;
     hs_stats_t stats;
     int new_block_len = 256;
     int c;

     hs_trace_to(NULL);

     while ((c = getopt(argc, argv, "D")) != -1) {
	  switch (c) {
	  case '?':
	  case ':':
	       return 1;
	  case 'D':
	       hs_trace_to(hs_trace_to_stderr);
	       break;
	  }
     }

     switch (argc - optind) {
     case 4:
	  new_block_len = atoi(argv[3 + optind]);
	  if (new_block_len <= 0) {
	       fprintf(stderr, "unreasonable new_block_len\n");
	       return 2;
	  }
	  /* fall through */
     case 3:			/* LT_FILE */
	  sigfb = hs_filebuf_open(argv[2 + optind], O_RDONLY);
	  if (!sigfb)
	       return 1;
	  /* Drop through */
     case 2:
	  if (!(ltfb = hs_filebuf_open(argv[1 + optind],
				       O_WRONLY | O_TRUNC | O_CREAT)))
	       return 1;
     case 1:
	  if (!(newfb = hs_filebuf_open(argv[optind], O_RDONLY)))
	       return 1;
	  break;
     default:
	  usage(argv[0]);
	  return 1;
     }

     if (!ltfb)
	  ltfb = hs_filebuf_from_fd(STDOUT_FILENO);
     if (!sigfb)
	  sigfb = hs_filebuf_from_fd(STDIN_FILENO);

     ret = hs_encode(hs_filebuf_read, newfb,
		     hs_filebuf_write, ltfb,
		     hs_filebuf_read, sigfb,
		     new_block_len, &stats);

     if (ret < 0) {
	  _hs_fatal("Failed to encode: %s\n", strerror(errno));
	  exit(1);
     }

     hs_filebuf_close(ltfb);
     hs_filebuf_close(sigfb);
     hs_filebuf_close(newfb);

     return 0;
}
