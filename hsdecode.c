/*				       	-*- c-file-style: "bsd" -*-
 *
 * $Id$
 * 
 * Copyright (C) 2000 by Martin Pool
 * 
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 * 
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 * 
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 */


#include "includes.h"

int show_stats = 0;

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
     hs_filebuf_t *outfb = 0, *ltfb = 0, *newsigfb;
     hs_stats_t stats;
     int c;
     int old_fd;

     while ((c = getopt(argc, argv, "DS")) != -1) {
	  switch (c) {
	  case '?':
	  case ':':
	       return 1;
	  case 'D':
	       hs_trace_set_level(LOG_DEBUG);
	       break;
	 case 'S':
	     show_stats = 1;
	  }
     }

     switch (argc - optind) {
     case 4:
	  ltfb = hs_filebuf_open(argv[3 + optind], O_RDONLY);
	  if (!ltfb)
	       return 1;
	  /* Drop through */
     case 3:			/* LT_FILE */
	  outfb = hs_filebuf_open(argv[2 + optind],
				  O_WRONLY | O_TRUNC | O_CREAT);
	  if (!outfb)
	       return 1;
	  /* Drop through */
     case 2:
	  newsigfb = hs_filebuf_open(argv[1 + optind],
				     O_WRONLY | O_TRUNC | O_CREAT);
	  if (!newsigfb)
	       return 1;
	  old_fd = _hs_file_open(argv[optind], O_RDONLY);
	  if (old_fd == -1)
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

     ret = hs_decode(old_fd,
		     hs_filebuf_write, outfb,
		     hs_filebuf_read, ltfb,
		     hs_filebuf_write, newsigfb, &stats);

     if (ret < 0) {
	  _hs_fatal("%s: Failed to decode/extract: %s\n",
		    argv[0], strerror(errno));
	  exit(1);
     }

     hs_filebuf_close(ltfb);
     hs_filebuf_close(outfb);
     hs_filebuf_close(newsigfb);

     if (show_stats)
	 hs_print_stats(stderr, &stats);

     return 0;
}
