/* -*- mode: c; c-file-style: "k&r" -*-  */
/* hsfilebufcat.c -- Write results of reading from a filebuf
   to stdout.
   
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


int main(int argc, char *argv[])
{
     hs_filebuf_t *infb;
     int buf_len = 1000;
     char *buf;
     char *tail_ptr;
     int len;
     int c;

     while ((c = getopt(argc, argv, "b:")) != -1) {
	  switch (c) {
	  case '?':
	  case ':':
	       return 1;
	  case 'b':
	       buf_len = strtol(optarg, &tail_ptr, 10);
	       if (*tail_ptr  ||  buf_len < 1) {
		    fprintf(stderr, "-b must have an integer argument\n");
		    return 1;
	       }
	       break;
	  }
     }

     buf = malloc(buf_len);
     assert(buf);

     infb = hs_filebuf_from_fd(STDIN_FILENO);
     assert(infb);

     while (1) {
	  len = hs_filebuf_read(infb, buf, buf_len);
	  if (len < 0) {
	       perror("error in read");
	       return 1;
	  } else if (len == 0) {
	       break;
	  } else {
	       write(STDOUT_FILENO, buf, len);
	  }
     }

     return 0;
}
