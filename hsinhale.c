/* -*- mode: c; c-file-style: "bsd" -*-  */
/* hsemit -- Convert a text stream of commands into hsync encoding.
   The output doesn't include literal data, since the point is just to
   test that command emit/inhale works well.
   
   Copyright (C) 2000 by Martin Pool <mbp@humbug.org.au>

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
   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307
   USA */

#include "includes.h"


static void
print_cmd(int kind, uint32_t len, uint32_t off)
{
     char const *kind_str;
     
     switch (kind) {
     case op_kind_eof:
	  printf("EOF\n");
	  return;
     case op_kind_copy:
	  printf("COPY %d %d\n", off, len);
	  return;
     }

     switch (kind) {
     case op_kind_signature:
	  kind_str = "SIGNATURE";
	  break;
     case op_kind_literal:
	  kind_str = "LITERAL";
	  break;
     case op_kind_checksum:
	  kind_str = "CHECKSUM";
	  break;
     default:
	  fprintf(stderr, "bugger!  unexpected opcode kind\n");
	  abort();
     }

     printf("%s %d\n", kind_str, len);
}


static int
parse_args(int argc, char **argv)
{
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

     return 0;     
}
     


int
main(int argc, char **argv)
{
     int ret, kind;
     uint32_t off, len;
     hs_filebuf_t * infb;

     if ((ret = parse_args(argc, argv)) != 0)
	  return ret;
     
     setvbuf(stdout, NULL, _IONBF, 0);
     
     infb = hs_filebuf_from_fd(STDIN_FILENO);
     
     do {
	  ret = _hs_inhale_command(hs_filebuf_read, infb,
				   &kind, &len, &off);

	  if (ret < 0)
	       return 1;
	  else if (ret == 0)
	       return 1;

	  print_cmd(kind, len, off);
     } while (kind != op_kind_eof);

     return 0;
}
