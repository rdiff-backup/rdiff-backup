/* -*- mode: c; c-file-style: "k&r" -*- */
/* 
   Copyright (C) 2000 by Martin Pool
   Copyright (C) 1998 by Andrew Tridgell 
   
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

/* Originally from rsync */

#include "includes.h"

static char last_byte;
static int last_sparse;
int sparse_files;

#define SPARSE_WRITE_SIZE (1024)
#define WRITE_SIZE (32*1024)
#define CHUNK_SIZE (32*1024)
#define MAX_MAP_SIZE (256*1024)
#define IO_BUFFER_SIZE (4092)

int sparse_end(int f)
{
     if (last_sparse) {
	  lseek(f,-1,SEEK_CUR);
	  return (write(f,&last_byte,1) == 1 ? 0 : -1);
     }
     last_sparse = 0;
     return 0;
}


static int write_sparse(int f,char *buf,int len)
{
     int l1=0,l2=0;
     int ret;

     for (l1=0;l1<len && buf[l1]==0;l1++) ;
     for (l2=0;l2<(len-l1) && buf[len-(l2+1)]==0;l2++) ;

     last_byte = buf[len-1];

     if (l1 == len || l2 > 0)
	  last_sparse=1;

     if (l1 > 0) {
	  lseek(f,l1,SEEK_CUR);  
     }

     if (l1 == len) 
	  return len;

     if ((ret=write(f,buf+l1,len-(l1+l2))) != len-(l1+l2)) {
	  if (ret == -1 || ret == 0) return ret;
	  return (l1+ret);
     }

     if (l2 > 0)
	  lseek(f,l2,SEEK_CUR);
	
     return len;
}



int write_file(int f,char *buf,int len)
{
     int ret = 0;

     if (!sparse_files) {
	  return write(f,buf,len);
     }

     while (len>0) {
	  int len1 = MIN(len, SPARSE_WRITE_SIZE);
	  int r1 = write_sparse(f, buf, len1);
	  if (r1 <= 0) {
	       if (ret > 0) return ret;
	       return r1;
	  }
	  len -= r1;
	  buf += r1;
	  ret += r1;
     }
     return ret;
}



