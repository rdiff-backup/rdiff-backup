/* -*- mode: c; c-file-style: "k&r" -*-  */

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
#include "hsync.h"
#include "hsyncproto.h"
#include "private.h"


#ifdef __GNUC__
#define UNUSED __attribute__((unused))
#else
#define UNUSED
#endif				/* ! __GNUC__ */


static void
print_cmd(int kind, uint32_t len, uint32_t off)
{
     switch (kind) {
     case op_kind_eof:
	  printf("EOF\n");
	  break;
     case op_kind_copy:
	  printf("COPY %d %d\n", off, len);
	  break;
     case op_kind_signature:
     case op_kind_literal:
	  printf("%s %d\n",
		 kind == op_kind_signature ? "SIGNATURE" : "LITERAL",
		 len);
	  break;
     default:
	  fprintf(stderr, "bugger!  unexpected opcode kind\n");
	  abort();
     }
}
     

int
main(int argc UNUSED, char **argv UNUSED)
{
     int ret, kind;
     uint32_t off, len;
     hs_filebuf_t * infb;

     setvbuf(stdout, NULL, _IONBF, 0);
     
     infb = hs_filebuf_from_file(stdin);
     
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
