/* -*- mode: c; c-file-style: "gnu" -*-  */

/* hsencode.c -- Generate combined encoded form
   
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

static void
usage (char *progname)
{
  fprintf(stderr, "Usage: %s NEWFILE [LT_FILE [SIG_FILE]]\n"
	  "\n"
	  "Compute differences between NEWFILE and the signature SIG_FILE\n"
	  "(default stdin), and write a literal/token/signature description \n"
	  "of them to LT_FILE (default stdout).\n", progname);
  exit (1);
}


int
main (int argc, char *argv[])
{
  int ret;
  hs_filebuf_t *ltfb = 0, *sigfb = 0, *newfb = 0;
  hs_stats_t stats;

  switch (argc)
    {
    case 4:			/* LT_FILE */
      sigfb = hs_filebuf_open (argv[3], "rb");
      if (!sigfb)
	return 1;
      /* Drop through */
    case 3:
      if (!(ltfb = hs_filebuf_open (argv[2], "wb")))
	return 1;
    case 2:
      if (!(newfb = hs_filebuf_open (argv[1], "rb")))
	return 1;
      break;
    case 1:
    default:
      usage (argv[0]);
      return 1;
    }

  if (!ltfb)
    ltfb = hs_filebuf_from_file (stdout);
  if (!sigfb)
    sigfb = hs_filebuf_from_file (stdin);

  ret = hs_encode(hs_filebuf_read, newfb,
		  hs_filebuf_write, ltfb,
		  hs_filebuf_read, sigfb,
		  &stats);
  
  if (ret < 0)
    {
      _hs_error ("Failed to encode: %s\n", strerror (errno));
      exit (1);
    }

  return 0;
}
