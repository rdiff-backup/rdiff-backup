/* -*- mode: c; c-file-style: "k&r" -*-  */

/* hs-decode.c -- Apply changes, extract signature stream.
   
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
#include "hsync.h"
#include "private.h"

static void usage(char *progname)
{
     fprintf(stderr, "Usage: %s OLDFILE NEWSIGFILE [OUTFILE [LT_FILE]]\n"
	     "\n"
	     "Apply the changes specified in LT_FILE (default stdin)\n"
	     "to OLDFILE to produce OUTFILE (default stdout).\n"
	     "OLDFILE must be seekable.  Write a server-generated signature\n"
	     "into NEWSIGFILE\n", progname);
     exit(1);
}


int main(int argc, char *argv[])
{
     int ret;
     hs_filebuf_t *oldfb, *outfb = 0, *ltfb = 0, *newsigfb;
     hs_stats_t stats;
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
     case 3:
	  ltfb = hs_filebuf_open(argv[3 + optind], O_RDONLY);
	  if (!ltfb)
	       return 1;
	  /* Drop through */
     case 2:			/* LT_FILE */
	  outfb = hs_filebuf_open(argv[2 + optind],
				  O_WRONLY | O_TRUNC | O_CREAT);
	  if (!outfb)
	       return 1;
	  /* Drop through */
     case 1:
	  newsigfb = hs_filebuf_open(argv[1 + optind],
				     O_WRONLY | O_TRUNC | O_CREAT);
	  if (!newsigfb)
	       return 1;
	  oldfb = hs_filebuf_open(argv[optind], O_RDONLY);
	  if (!oldfb)
	       return 1;
	  break;
     default:
	  usage(argv[0]);
	  return 1;
     }

     if (!ltfb)
	  ltfb = hs_filebuf_from_fd(STDIN_FILENO);
     if (!outfb)
	  outfb = hs_filebuf_from_fd(STDOUT_FILENO);

     ret = hs_decode(hs_filebuf_read_ofs, oldfb,
		     hs_filebuf_write, outfb,
		     hs_filebuf_read, ltfb,
		     hs_filebuf_write, newsigfb, &stats);

     if (ret < 0) {
	  _hs_fatal("%s: Failed to decode/extract: %s\n",
		    argv[0], strerror(errno));
	  exit(1);
     }

     return 0;
}
